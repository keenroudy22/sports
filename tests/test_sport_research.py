import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sport_research as S

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


class SportResearchTests(unittest.TestCase):
    def row(self, **extra):
        return {'league':'NBA','gameId':'NBA-1','capturedAt':'2026-10-23T12:00:00Z',
                'season':2027,'seasonType':2,'kickoff':'2026-10-24T00:00:00Z','ours':210,'line':215.5,'lean':True,
                'result':'win','gradedAt':'2026-10-24T04:00:00Z', **extra}

    def test_only_original_pregame_trial_leans_count_once(self):
        rows=[self.row(),self.row(capturedAt='2026-10-23T13:00:00Z',result='loss'),
              self.row(gameId='NBA-2',lean=False),self.row(gameId='NBA-3',result='push')]
        r=S.build(NOW,rows)['leagues']['NBA']
        self.assertEqual(r['recorded'],3)
        self.assertEqual(r['record'],dict(win=1,loss=0,push=1))

    def test_late_or_future_records_and_invalid_numbers_never_inflate_record(self):
        for changes in ({'capturedAt':'2026-10-24T00:00:00Z'}, {'capturedAt':'2026-10-26T00:00:00Z'},
                        {'league':'MLB'}, {'ours':None}, {'ours':float('nan')}, {'line':True}):
            with self.subTest(changes=changes):
                self.assertEqual(S.build(NOW,[self.row(**changes)])['leagues']['NBA']['recorded'],0)
        for graded in ('2026-10-26T00:00:00Z','2026-10-23T00:00:00Z',None):
            r=S.build(NOW,[self.row(gradedAt=graded)])['leagues']['NBA']
            self.assertEqual(sum(r['record'].values()),0)

    def test_upcoming_saved_projections_are_not_new_picks_or_profit_claims(self):
        r=S.build(NOW,[self.row(kickoff='2026-10-26T00:00:00Z',result=None)])
        self.assertEqual(r['scope'],'paper-trials-only')
        self.assertEqual(r['leagues']['NBA']['upcoming'][0]['projection'],210)
        self.assertNotIn('units',r['leagues']['NBA'])
        self.assertEqual(r['leagues']['CBB']['recorded'],0)

    def test_regular_season_and_playoffs_have_separate_browsable_trial_records(self):
        rows=[self.row(),self.row(gameId='NBA-2',seasonType=3,result='loss')]
        seasons=S.build(NOW,rows)['leagues']['NBA']['seasons']
        self.assertEqual([(row['phase'],row['record']) for row in seasons],
                         [('regular',dict(win=1,loss=0,push=0)),('playoffs',dict(win=0,loss=1,push=0))])


if __name__ == '__main__': unittest.main()
