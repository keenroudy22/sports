import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_capture
import nba_official_availability as official

NOW=datetime(2026,10,27,12,30,tzinfo=timezone.utc)
REPORTED=datetime(2026,10,27,12,tzinfo=timezone.utc)
SOURCE='https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-27_08_00AM.pdf'
TEXT='''Injury Report: 10/27/26 08:00 AM
Game Date    Game Time    Matchup    Team    Player Name    Current Status    Reason
10/27/2026    07:30 (ET)    BKN@BOS    Brooklyn Nets    Player, Test    Out    G League - Two-Way
    Boston Celtics    Other, Real    Available    Injury/Illness - Finger
Page 1 of 2
Injury Report: 10/27/26 08:00 AM
Game Date    Game Time    Matchup    Team    Player Name    Current Status    Reason
10/28/2026    07:30 (ET)    BKN@BOS    Brooklyn Nets    NOT YET SUBMITTED
    Boston Celtics    NOT YET SUBMITTED
'''


def fixtures():
    games=[dict(providerId=str(day),season=2027,kickoff=f'2026-10-{day}T23:30:00Z',teams={
        'away':dict(id='17',name='Brooklyn Nets',abbreviation='BKN'),
        'home':dict(id='2',name='Boston Celtics',abbreviation='BOS')}) for day in (27,28)]
    rosters={t:dict(team=t,season=2027,retrievedAt='2026-10-27T11:00:00Z',players=[dict(id=p,name=n)])
             for t,p,n in [('17','1','Test Player'),('2','2','Real Other')]}
    return games,rosters


class OfficialAvailabilityTests(unittest.TestCase):
    def report(self,text=TEXT):
        games,rosters=fixtures()
        r=official.parse(text,games,rosters,REPORTED,NOW,SOURCE)
        r.update(league='NBA',season=2027)
        return r

    def test_report_time_selects_one_completed_quarter_with_no_probing(self):
        url,at=official.report_url(NOW)
        self.assertTrue(url.endswith('_08_15AM.pdf'))
        self.assertEqual(at,datetime(2026,10,27,12,15,tzinfo=timezone.utc))
        url,at=official.report_url(datetime(2026,11,2,5,5,tzinfo=timezone.utc))
        self.assertTrue(url.endswith('2026-11-01_11_45PM.pdf'))
        self.assertLess(at,datetime(2026,11,2,5,5,tzinfo=timezone.utc))

    def test_todays_submitted_report_is_separate_from_tomorrows_unsubmitted_report(self):
        games,_=fixtures();report=self.report();merged=official.merge([],report,games)
        self.assertFalse(merged['27']['teamHolds'])
        self.assertEqual(len(merged['27']['rows']),2)
        self.assertEqual(set(merged['28']['teamHolds']),{'17','2'})
        snapshot=dict(rows=[],official=report,gameAvailability=merged)
        self.assertFalse(nba_capture.availability_for_game(snapshot,games[0],NOW)[1])
        self.assertTrue(nba_capture.availability_for_game(snapshot,games[1],NOW)[1])

    def test_available_can_supersede_older_out_but_not_newer_or_undated_disagreement(self):
        games,_=fixtures();report=self.report()
        old=dict(team='2',athleteId='2',status='Out',date='2026-10-27T10:00:00Z')
        self.assertFalse(official.merge([old],report,games)['27']['teamHolds'])
        for stamp in ('2026-10-27T12:15:00Z',None,'bad'):
            self.assertTrue(official.merge([dict(old,date=stamp)],report,games)['27']['teamHolds'])
        missing=dict(old,athleteId='missing')
        self.assertTrue(official.merge([missing],report,games)['27']['teamHolds'])

    def test_clock_identity_future_stale_and_missing_columns_hold(self):
        games,rosters=fixtures()
        for text,at,now,source in ((TEXT,REPORTED+timedelta(minutes=15),NOW,SOURCE),
            (TEXT,REPORTED,REPORTED-timedelta(seconds=1),SOURCE),
            (TEXT,REPORTED,NOW+timedelta(hours=2),SOURCE),
            (TEXT.replace('Current Status','Missing'),REPORTED,NOW,SOURCE),
            (TEXT,REPORTED,NOW,'https://example.com/fake.pdf'),
            (TEXT.replace('07:30','08:00'),REPORTED,NOW,SOURCE)):
            with self.assertRaises(ValueError):official.parse(text,games,rosters,at,now,source)
        broken=copy.deepcopy(rosters);broken['2']['players']*=2
        r=official.parse(TEXT,games,broken,REPORTED,NOW,SOURCE)
        self.assertTrue(official.merge([],r,games)['27']['teamHolds'])

    def test_malformed_status_blank_submission_and_missing_reader_fail_closed(self):
        with self.assertRaises(ValueError):self.report(TEXT.replace('Available','Something Else'))
        r=self.report(TEXT.replace('Other, Real    Available    Injury/Illness - Finger',''))
        games,_=fixtures();self.assertTrue(official.merge([],r,games)['27']['teamHolds'])
        with patch.object(official.shutil,'which',return_value=None):
            with self.assertRaises(ValueError):official.extract(b'%PDF-1.4')
        with patch.object(official.shutil,'which',return_value='/usr/bin/pdftotext'):
            with self.assertRaises(ValueError):official.extract(b'not PDF')

    def test_official_pdf_shares_the_same_budget_and_domain_guard(self):
        b=nba_capture.Budget(requests=1,fetch=lambda _:b'%PDF-1.4',sleep=lambda _:None)
        self.assertEqual(b.raw(SOURCE),b'%PDF-1.4')
        with self.assertRaises(TimeoutError):b(nba_capture.INJURIES)
        b=nba_capture.Budget(fetch=lambda _:b'%PDF-1.4',sleep=lambda _:None)
        with self.assertRaises(ValueError):b.raw('https://example.com/report.pdf')
        self.assertEqual(b.requests,0)

    def test_unavailable_tampered_or_future_official_snapshot_is_not_healthy(self):
        games,_=fixtures();report=self.report();snapshot=dict(rows=[],official=report,gameAvailability=official.merge([],report,games))
        for change in ({'state':'unavailable'},{'reportedAt':'2026-10-27T13:00:00Z'},
                       {'source':'https://example.com/fake.pdf'},{'season':2026}):
            bad=copy.deepcopy(snapshot);bad['official'].update(change)
            self.assertTrue(nba_capture.availability_for_game(bad,games[0],NOW)[1])
        self.assertTrue(nba_capture.availability_for_game({'rows':[]},games[0],NOW)[1])

    def test_capture_to_trial_keeps_official_report_and_fails_closed_on_reader_error(self):
        import nba_trial_runtime
        games,rosters=fixtures()
        for g in games:
            g.update(id='NBA-'+g['providerId'],status='scheduled',seasonType='regular-season')
        # Available is an explicit status; no injuries inferred from an empty feed.
        text=TEXT.replace('08:00 AM','08:15 AM').replace('Player, Test    Out','Player, Test    Available')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'rosters').mkdir()
            for team,roster in rosters.items():
                (root/'rosters'/f'{team}.json').write_text(json.dumps(roster))
            urls=[]
            def fetch(url):
                urls.append(url)
                if url.endswith('.pdf'):return b'%PDF-1.4'
                return {'injuries':[],'season':{'year':2027}} if url==nba_capture.INJURIES else {}
            def run():
                with patch.object(nba_capture.sports_refresh,'normalize',return_value=games):
                    return nba_capture.step(NOW,root,budget=nba_capture.Budget(fetch=fetch,sleep=lambda _:None),clock=lambda:NOW)
            with patch.object(official,'extract',return_value=text):result=run()
            self.assertNotIn('official-availability-unavailable',result['errors'])
            self.assertEqual(sum(u.endswith('.pdf') for u in urls),1)
            snapshot=json.loads((root/'injuries-current.json').read_text())
            self.assertFalse(nba_capture.availability_for_game(snapshot,games[0],NOW)[1])
            coverage={}
            nba_trial_runtime.candidates(NOW,root,history=[],diagnostics=coverage)
            self.assertEqual(coverage['eligibleGames'],1)
            self.assertNotIn('Official NBA availability unavailable',coverage['holds'])
            self.assertEqual(len(list((root/'official-availability').glob('*.jsonl'))),1)
            # A fresh, empty ESPN response cannot turn a failed official read healthy.
            with patch.object(official,'extract',side_effect=ValueError('reader unavailable')):result=run()
            self.assertIn('official-availability-unavailable',result['errors'])
            snapshot=json.loads((root/'injuries-current.json').read_text())
            self.assertTrue(nba_capture.availability_for_game(snapshot,games[0],NOW)[1])
            coverage={}
            nba_trial_runtime.candidates(NOW,root,history=[],diagnostics=coverage)
            self.assertEqual(coverage['eligibleGames'],0)


    def test_http_failure_is_actionable_without_leaking_exception_content_or_retrying(self):
        from urllib.error import HTTPError
        games, _ = fixtures()
        for game in games:
            game.update(id='NBA-'+game['providerId'],status='scheduled',seasonType='regular-season')
        calls=[]
        def fetch(url):
            calls.append(url)
            if url.endswith('.pdf'):
                raise HTTPError('https://private.invalid/?token=secret',403,'secret response',{},None)
            return {'injuries':[],'season':{'year':2027}} if url==nba_capture.INJURIES else {}
        with tempfile.TemporaryDirectory() as folder, patch.object(nba_capture.sports_refresh,'normalize',return_value=games):
            root=Path(folder)
            result=nba_capture.step(NOW,root,budget=nba_capture.Budget(fetch=fetch,sleep=lambda _:None),clock=lambda:NOW)
            snapshot=json.loads((root/'injuries-current.json').read_text())
            failed=snapshot['official']
            self.assertEqual(failed['state'],'unavailable')
            self.assertEqual(failed['httpStatus'],403)
            self.assertEqual(failed['attemptedAt'],'2026-10-27T12:30:00Z')
            self.assertEqual(failed['source'],official.report_url(NOW)[0])
            self.assertNotIn('secret',json.dumps(result))
            self.assertNotIn('private.invalid',json.dumps(snapshot))
            self.assertEqual(sum(url.endswith('.pdf') for url in calls),1)
            self.assertEqual(result['officialAvailability'],failed)
            self.assertTrue(nba_capture.availability_for_game(snapshot,games[0],NOW)[1])
            self.assertEqual(list((root/'official-availability').glob('*.jsonl')),[])

    def test_reader_and_parse_failures_do_not_become_participation_evidence(self):
        import subprocess
        for error, reason in [(ValueError('private body'),'Official report could not be verified'),
                              (ValueError('Official injury PDF reader unavailable'),'Official report PDF reader unavailable'),
                              (subprocess.TimeoutExpired('private command',10),'Official report PDF extraction failed'),
                              (TimeoutError('private URL'),'Official report connection or capture budget unavailable')]:
            result=official.failure(error,NOW)
            self.assertEqual(result['state'],'unavailable')
            self.assertEqual(result['reason'],reason)
            self.assertNotIn('private',json.dumps(result))


if __name__=='__main__':unittest.main()
