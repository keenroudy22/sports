import copy
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import boxscores,nba_capture,nba_official_availability as official,nba_report_intake as intake
import test_nba_official_availability as f
import nba_trial_runtime


class IntakeSelectionTests(unittest.TestCase):
    def test_recovery_rechecks_admission_at_actual_completion_without_recapture_or_false_send(self):
        now=datetime(2026,11,5,13,36,tzinfo=timezone.utc)
        for state in ('admitted','no-play','held'):
            with self.subTest(state=state),patch.object(nba_trial_runtime,'admission',return_value={'state':state}) as admit,patch.object(nba_capture,'step',side_effect=AssertionError('extra capture')):
                result=intake.select_after_intake(nba_capture.STORE,clock=lambda:now)
                admit.assert_called_once_with(now,capture=False)
                self.assertEqual(result['requests'],0)
                self.assertFalse(result['sent'])
                self.assertEqual(result['delivery'],'pending-existing-worker' if state=='admitted' else 'no-new-play')

    def test_alternate_root_cannot_accidentally_admit_against_production(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(nba_trial_runtime,'admission') as admit:
            with self.assertRaisesRegex(ValueError,'canonical'):
                intake.select_after_intake(folder)
            admit.assert_not_called()

    def test_real_admission_remains_held_with_no_approval_and_never_captures(self):
        # Exercise the actual admission boundary: recovering a source does not
        # bypass the reviewed opening/kill switch or create a publish record.
        with patch.object(nba_trial_runtime,'review_ready',return_value=False),patch.object(nba_capture,'step',side_effect=AssertionError('extra capture')):
            result=intake.select_after_intake(nba_capture.STORE)
        self.assertEqual(result['admission']['state'],'held')
        self.assertEqual(result['delivery'],'no-new-play')
        self.assertFalse(result['sent'])


class BrowserReportTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder)/'nba-capture';(root/'rosters').mkdir(parents=True)
        games,rosters=f.fixtures()
        for team,r in rosters.items():boxscores.write_json(root/'rosters'/f'{team}.json',r)
        boxscores.write_json(root/'slate.json',dict(retrievedAt='2026-10-27T11:30:00Z',games=games))
        boxscores.write_json(root/'injuries-current.json',dict(league='NBA',season=2027,retrievedAt='2026-10-27T11:00:00Z',rows=[],official=dict(state='unavailable',reason='Transport timeout')))
        image=Path(folder)/'page.jpg';image.write_bytes(b'\xff\xd8\xff'+b'test-only-screenshot-fixture'*2)
        text=f.TEXT.split('Page 1 of 2')[0]+'Page 1 of 1\n'
        packet=dict(source=f.SOURCE,retrievedAt='2026-10-27T12:20:00Z',allPagesReviewed=True,
            listing=dict(source=official.index_url(f.NOW),retrievedAt='2026-10-27T12:10:00Z',html=f'<a href="{f.SOURCE}">report</a>'),
            pages=[dict(number=1,totalPages=1,text=text,screenshot=str(image),sha256=hashlib.sha256(image.read_bytes()).hexdigest())])
        return root,games,packet

    def test_official_listing_trailing_slash_preserves_actual_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root,_,p=self.fixture(folder)
            p['listing']['source']+='/'
            result=intake.build(p,f.NOW,root)
            self.assertEqual(result['discovery']['source'],p['listing']['source'])
            for suffix in ('//','?redirect=other','#other'):
                p['listing']['source']=official.index_url(f.NOW)+suffix
                with self.assertRaises(ValueError):intake.build(p,f.NOW,root)

    def test_downloaded_pdf_bytes_replace_transcription_without_changing_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            _,_,p=self.fixture(folder);original=copy.deepcopy(p)
            actual=p['pages'][0]['text'];p['pages'][0]['text']='invented status'
            with patch.object(official,'extract',return_value=actual+'\f'):
                result=intake.with_pdf(p,b'%PDF-test-only')
            self.assertEqual(result['pages'][0]['text'],actual)
            self.assertEqual(result['retrievedAt'],original['retrievedAt'])
            self.assertEqual(p['pages'][0]['text'],'invented status')
            self.assertEqual(result['pdfSha256'],hashlib.sha256(b'%PDF-test-only').hexdigest())
            with patch.object(official,'extract',return_value=actual+'\f'+actual):
                with self.assertRaises(ValueError):intake.with_pdf(original,b'%PDF-test-only')
            with self.assertRaises(ValueError):intake.with_pdf(original,b'not a PDF')

    def test_browser_source_reuses_strict_parser_and_preserves_provider_clock_and_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root,games,p=self.fixture(folder);r=intake.ingest(p,f.NOW,root)
            self.assertEqual(r['teams'],2);self.assertEqual(r['submitted'],2)
            self.assertEqual(intake.ingest(p,f.NOW,root)['ingested'],0)
            snapshot=json.loads((root/'injuries-current.json').read_text())
            self.assertEqual(snapshot['retrievedAt'],'2026-10-27T11:00:00Z')
            self.assertEqual(snapshot['lastOfficialTransportFailure']['reason'],'Transport timeout')
            rows,holds=nba_capture.availability_for_game(snapshot,games[0],f.NOW)
            self.assertFalse(holds);self.assertEqual({r['status'] for r in rows},{'Out','Available'})
            self.assertEqual(boxscores.verify(root/'official-availability'),[])
            self.assertEqual(snapshot['official']['retrievedAt'],p['retrievedAt'])

    def test_missing_page_tamper_wrong_source_and_stale_future_clocks_are_not_ingested(self):
        for case in ('not-reviewed','missing-footer','image-hash','wrong-source','not-newest','future','stale','wrong-header'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as folder:
                root,_,p=self.fixture(folder)
                if case=='not-reviewed':p['allPagesReviewed']=False
                elif case=='missing-footer':p['pages'][0]['text']=p['pages'][0]['text'].replace('Page 1 of 1','')
                elif case=='image-hash':p['pages'][0]['sha256']='bad'
                elif case=='wrong-source':p['source']='https://example.com/report.pdf'
                elif case=='not-newest':p['listing']['html']+='<a href="'+f.SOURCE.replace('08_00','08_15')+'">newer</a>';p['listing']['retrievedAt']='2026-10-27T12:19:00Z'
                elif case=='future':p['retrievedAt']='2026-10-27T12:31:00Z'
                elif case=='stale':p['retrievedAt']='2026-10-27T09:00:00Z'
                elif case=='wrong-header':p['pages'][0]['text']=p['pages'][0]['text'].replace('08:00 AM','08:15 AM')
                with self.assertRaises(ValueError):intake.ingest(p,f.NOW,root)
                self.assertFalse((root/'official-availability').exists())

    def test_unsubmitted_teams_and_unmapped_players_stay_held(self):
        with tempfile.TemporaryDirectory() as folder:
            root,games,p=self.fixture(folder)
            p['pages'][0]['text']=p['pages'][0]['text'].replace('Player, Test    Out    G League - Two-Way','NOT YET SUBMITTED').replace('Other, Real','Other, Unknown')
            intake.ingest(p,f.NOW,root)
            snapshot=json.loads((root/'injuries-current.json').read_text())
            self.assertEqual(set(nba_capture.availability_for_game(snapshot,games[0],f.NOW)[1]),{'17','2'})

    def test_old_browser_report_never_replaces_a_newer_captured_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root,_,p=self.fixture(folder)
            snapshot=json.loads((root/'injuries-current.json').read_text());snapshot['official']={'reportedAt':'2026-10-27T12:15:00Z'}
            boxscores.write_json(root/'injuries-current.json',snapshot)
            with self.assertRaisesRegex(ValueError,'newer official report'):intake.ingest(p,f.NOW,root)
            self.assertFalse((root/'official-availability').exists())

if __name__=='__main__':unittest.main()

class BrowserCacheTests(unittest.TestCase):
    fixture=BrowserReportTests.fixture
    def test_only_exact_newest_browser_observation_can_avoid_a_second_pdf_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root,games,p=self.fixture(folder);intake.ingest(p,f.NOW,root)
            cached=official.browser_observation(root,f.SOURCE,f.REPORTED,games,f.NOW)
            self.assertTrue(cached['_from_verified_browser_cache'])
            self.assertEqual(cached['retrievedAt'],p['retrievedAt'])
            self.assertIsNone(official.browser_observation(root,f.SOURCE.replace('08_00','08_15'),f.REPORTED,games,f.NOW))
            self.assertIsNone(official.browser_observation(root,f.SOURCE,f.REPORTED,games,f.NOW+timedelta(hours=2)))
            moved=copy.deepcopy(games);moved[0]['kickoff']='2026-10-27T23:45:00Z'
            self.assertIsNone(official.browser_observation(root,f.SOURCE,f.REPORTED,moved,f.NOW))
            roster=json.loads((root/'rosters/17.json').read_text());roster['players']=[]
            boxscores.write_json(root/'rosters/17.json',roster)
            self.assertIsNone(official.browser_observation(root,f.SOURCE,f.REPORTED,games,f.NOW))
