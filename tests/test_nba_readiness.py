import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import boxscores
import nba_capture
import nba_readiness


class NBAReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = self.root / 'capture'
        self.paper = self.root / 'paper'
        self.config = {
            'source': 'ESPN free feeds', 'books': ['DraftKings'],
            'markets': ['moneyline', 'spread', 'total'],
            'captureSlotsEastern': ['11:45', '17:30', '21:00', '23:30'],
            'cleanCaptureDaysRequired': 14, 'paperGradesRequired': 50,
            'openingDate': '2026-10-20',
        }

    def observation(self, moment, clean=True, scheduled=True):
        return {'league': 'NBA', 'season': 2027, 'slot': boxscores.stamp(moment),
                'scheduled': scheduled, 'errors': [] if clean else ['quote-unavailable'],
                'props': {'errors': 0}, 'retrievedAt': boxscores.stamp(moment)}

    def write_days(self, count):
        rows = []
        for day in range(count):
            base = datetime(2026, 10, 1 + day, tzinfo=timezone.utc)
            # October is EDT: these are 11:45, 17:30, 21:00 and 23:30 Eastern.
            for hour, minute in ((15,45),(21,30),(1,0),(3,30)):
                moment = base.replace(hour=hour, minute=minute)
                if hour < 4: moment += timedelta(days=1)
                rows.append(self.observation(moment))
        nba_capture.append_changed(rows, self.capture/'observations', lambda row: row['slot'])

    def write_paper(self, count):
        rows=[]
        for i in range(count):
            game=f'NBA-{i}'
            rows += [
                {'type':'record','gameId':game,'league':'NBA','season':2027,'lean':True,
                 'line':220.5,'capturedAt':'2026-10-20T12:00:00Z','side':'over','price':-110,'kickoff':'2026-10-20T23:00:00Z'},
                {'type':'grade','gameId':game,'result':'win','actual':225,'gradedAt':'2026-10-21T02:00:00Z'},
            ]
        boxscores.append(self.paper/'nba-2027.jsonl', rows)

    def test_promotion_evidence_requires_four_natural_slots_for_fourteen_days_then_fifty_grades(self):
        self.write_days(13); self.write_paper(50)
        first=nba_readiness.status(datetime(2026,10,13,12,tzinfo=timezone.utc),capture_root=self.capture,paper_root=self.paper,config=self.config)
        self.assertEqual(first['stage'],'log'); self.assertFalse(first['readyForLiveTrial'])
        # A partial or manual probe cannot complete a day.
        extra=self.observation(datetime(2026,10,14,15,45,tzinfo=timezone.utc),scheduled=False)
        nba_capture.append_changed([extra],self.capture/'observations',lambda row:row['slot'])
        self.assertEqual(nba_readiness.status(datetime(2026,10,13,12,tzinfo=timezone.utc),capture_root=self.capture,paper_root=self.paper,config=self.config)['stage'],'log')
        # The real four-slot day completes the separate promotion-evidence gate.
        base=datetime(2026,10,14,tzinfo=timezone.utc)
        rows=[self.observation(base.replace(hour=15,minute=45)),
              self.observation(base.replace(hour=21,minute=30)),
              self.observation((base+timedelta(days=1)).replace(hour=1,minute=0)),
              self.observation((base+timedelta(days=1)).replace(hour=3,minute=30))]
        nba_capture.append_changed(rows,self.capture/'observations',lambda row:row['slot'])
        final=nba_readiness.status(datetime(2026,10,22,12,tzinfo=timezone.utc),capture_root=self.capture,paper_root=self.paper,config=self.config)
        self.assertEqual(final['stage'],'live-trial'); self.assertTrue(final['readyForLiveTrial'])
        self.assertTrue(final['readyForPromotionEvidence'])

    def test_opening_night_trial_does_not_wait_for_promotion_evidence(self):
        before=nba_readiness.status(datetime(2026,10,19,12,tzinfo=timezone.utc),capture_root=self.capture,paper_root=self.paper,config=self.config)
        opening=nba_readiness.status(datetime(2026,10,20,12,tzinfo=timezone.utc),capture_root=self.capture,paper_root=self.paper,config=self.config)
        self.assertFalse(before['readyForLiveTrial'])
        self.assertTrue(opening['readyForLiveTrial'])
        self.assertEqual(opening['stage'],'live-trial')
        self.assertFalse(opening['playerPropsReady'])
        self.assertFalse(opening['quarterTicketsReady'])
        self.assertFalse(opening['climbReady'])
        self.assertFalse(opening['readyForPromotionEvidence'])
        self.assertEqual(opening['cleanCaptureDays'],0)
        self.assertEqual(opening['paperGraded'],0)

    def test_bad_or_missing_slot_does_not_count_and_policy_is_free_draftkings_only(self):
        base=datetime(2026,10,1,tzinfo=timezone.utc)
        rows=[self.observation(base.replace(hour=15,minute=45),clean=False),
              self.observation(base.replace(hour=21,minute=30)),
              self.observation((base+timedelta(days=1)).replace(hour=1,minute=0)),
              self.observation((base+timedelta(days=1)).replace(hour=3,minute=30))]
        nba_capture.append_changed(rows,self.capture/'observations',lambda row:row['slot'])
        self.assertEqual(nba_readiness.clean_days(self.capture,self.config),[])
        live=nba_readiness.policy()
        self.assertEqual(live['books'],['DraftKings'])
        self.assertEqual(live['markets'],['moneyline','spread','total'])
        self.assertEqual(live['injuryFreshMinutes'],60)



    def test_dated_schedule_keeps_old_days_and_requires_all_replacement_slots(self):
        self.write_days(1)
        config=dict(self.config,captureScheduleHistory=[{'effectiveDate':'2026-10-24',
            'slots':['06:45','08:30','11:45','13:30','17:30','21:00']}])
        from zoneinfo import ZoneInfo
        day=datetime(2026,10,24,tzinfo=ZoneInfo('America/New_York'))
        rows=[self.observation(day.replace(hour=h,minute=m)) for h,m in
              ((6,45),(8,30),(11,45),(13,30),(17,30),(21,0))]
        nba_capture.append_changed(rows[:-1],self.capture/'observations',lambda r:r['slot'])
        clock=datetime(2026,10,26,tzinfo=timezone.utc)
        self.assertEqual(nba_readiness.clean_days(self.capture,config,clock),['2026-10-01'])
        nba_capture.append_changed(rows[-1:],self.capture/'observations',lambda r:r['slot'])
        self.assertEqual(nba_readiness.clean_days(self.capture,config,clock),['2026-10-01','2026-10-24'])
        self.assertEqual(nba_readiness.clean_days(self.capture,config,day),['2026-10-01'])

    def test_future_receipt_cannot_complete_capture_day(self):
        self.write_days(1)
        clock=datetime(2026,10,2,3,31,tzinfo=timezone.utc)
        self.assertEqual(nba_readiness.clean_days(self.capture,self.config,clock),['2026-10-01'])
        self.assertEqual(nba_readiness.clean_days(self.capture,self.config,clock-timedelta(minutes=2)),[])

    def test_paper_future_correction_does_not_hide_available_grade(self):
        self.write_paper(1)
        later={'type':'grade','gameId':'NBA-0','result':'loss','actual':210,'gradedAt':'2026-10-23T02:00:00Z'}
        boxscores.append(self.paper/'nba-2027.jsonl',[later])
        rows=nba_readiness.paper_rows(self.paper,datetime(2026,10,22,tzinfo=timezone.utc))
        self.assertEqual([r['result'] for r in rows],['win'])
        early=nba_readiness.paper_rows(self.paper,datetime(2026,10,20,13,tzinfo=timezone.utc))
        self.assertNotIn('result',early[0])
        self.assertEqual(nba_readiness.paper_rows(self.paper,datetime(2026,10,19,tzinfo=timezone.utc)),[])


if __name__ == '__main__': unittest.main()
