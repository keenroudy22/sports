import copy
import sys
import unittest
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_minutes_shadow as shadow
import nba_player_props
import nba_capture

AT='2026-10-27T12:00:00Z'


class MinutesShadowTests(unittest.TestCase):
    def row(self):
        return dict(kickoff='2026-10-27T23:30:00Z', hold=None,
            projection=dict(model=shadow.BASELINE,value=20,minutes=30,low=10,high=30),
            currentRole=dict(games=3,minutes=[32,34,33],starts=3,
                asOf='2026-10-26T00:00:00Z',receivedAt='2026-10-26T04:00:00Z'))

    def test_frozen_current_minutes_change_workload_not_rate_or_official_model(self):
        row=self.row();before=copy.deepcopy(row);p=shadow.adjust(row,AT)
        self.assertEqual((p['value'],p['minutes'],p['baselineValue'],p['baselineMinutes']),(22,33,20,30))
        self.assertTrue(p['analysisOnly']);self.assertFalse(p['admissionReady'])
        self.assertEqual(row,before)

    def test_changed_unknown_thin_or_major_role_does_not_get_an_automatic_estimate(self):
        for change in (dict(games=2),dict(starts=1),dict(starts=None),dict(starts=False),
                       dict(minutes=[10,30,30]),dict(minutes=[48,48,48]),dict(minutes=[30,float('nan'),30])):
            row=self.row();row['currentRole'].update(change)
            self.assertIsNone(shadow.adjust(row,AT),change)

    def test_future_stale_and_missing_receipt_evidence_cannot_leak(self):
        for change in (dict(receivedAt='2026-10-27T13:00:00Z'),dict(receivedAt='bad'),
                       dict(asOf='2026-10-01T00:00:00Z'),dict(asOf='2026-10-27T13:00:00Z')):
            row=self.row();row['currentRole'].update(change)
            self.assertIsNone(shadow.adjust(row,AT))
        row=self.row();row['hold']='Questionable'
        self.assertIsNone(shadow.adjust(row,AT))
        row=self.row();row['projection']['model']='nba-minutes-rate-reviewed-v1'
        self.assertIsNone(shadow.adjust(row,AT))

    def test_capture_keeps_control_and_candidate_separate_and_deduplicated(self):
        row=self.row()
        row.update(eventId='1',athleteId='2',stat='pts',book='DraftKings',
                   over=105,under=-115,line=21.5,side='under',odds=-115,
                   favorite=True,last10={'hits':7})
        row['projection'].update(season=2026,window='Last season')
        now=datetime(2026,10,27,12,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp, patch.object(nba_player_props,'build',return_value={'rows':[row]}):
            root=Path(tmp)
            self.assertEqual(nba_player_props.record_forward(now,root),2)
            self.assertEqual(nba_player_props.record_forward(now,root),0)
            rows=nba_player_props.saved(root/'player-forecasts')
            control=next(r for r in rows if r['model']==shadow.BASELINE)
            candidate=next(r for r in rows if r['model']==shadow.VERSION)
            self.assertEqual((control['projection']['value'],control['side'],control['odds']),(20,'under',-115))
            self.assertEqual((candidate['projection']['value'],candidate['side'],candidate['odds']),(22,'over',105))
            self.assertEqual(control['retrievedAt'],candidate['retrievedAt'])
            self.assertFalse(candidate['favorite']);self.assertFalse(candidate['admissionReady'])
            self.assertNotIn('last10',candidate)
            self.assertEqual(candidate['gap'],.5)
            self.assertFalse((root/'nba-trial').exists())

    def test_available_status_is_distinct_from_unresolved_or_absent(self):
        for status in ('Available','Active',' available '):
            self.assertFalse(nba_capture.blocks_availability(status))
        for status in ('Out','Doubtful','Questionable','Probable','Day-To-Day','Unknown','NOT YET SUBMITTED',' '):
            self.assertTrue(nba_capture.blocks_availability(status))


if __name__=='__main__':unittest.main()
