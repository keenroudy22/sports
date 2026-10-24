import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import next_day_prep as prep


class PrepTests(unittest.TestCase):
    def test_eastern_tomorrow_balances_families_without_admitting_or_hiding_holds(self):
        now=datetime(2026,10,24,2,tzinfo=timezone.utc)
        games={'CFB-1':{'league':'CFB','state':'pre','kickoff':'2026-10-24T16:00:00Z'}}
        base=dict(gameId='CFB-1',state='open',kickoff=games['CFB-1']['kickoff'],freshness='stale',
                  grade={'edge':5},book='FanDuel',odds=-110,line=7.5)
        lines=[dict(base,id='a',title='Side',market='point spread'),
               dict(base,id='b',title='Total',market='total points'),
               dict(base,id='c',title='Player',athleteId='123')]
        nba={'games':[{'status':'scheduled','kickoff':'2026-10-25T00:00:00Z'}]}
        props={'rows':[{'kickoff':'2026-10-25T00:00:00Z','hold':'Role review needed'}]}
        report=prep.prepare(games,lines,nba,props,now)
        self.assertEqual(report['targetDate'],'2026-10-24')
        self.assertEqual(report['football']['pricedRowsByFamily'],{'sides':1,'totals':1,'props':1})
        self.assertEqual(len(report['football']['watchByFamily']),3)
        self.assertIn('Price needs refresh',report['football']['watchByFamily']['sides'][0]['holds'])
        self.assertEqual(report['nba']['freshPropRows'],1)
        self.assertEqual(report['nba']['watch'][0]['hold'],'Role review needed')
        self.assertFalse(report['releaseReady'])
        self.assertEqual(report['morningChecksEastern'],['06:45','08:30'])

    def test_missing_grades_never_become_ranked_candidates(self):
        now=datetime(2026,10,24,2,tzinfo=timezone.utc)
        games={'one':{'league':'CFB','state':'pre','kickoff':'2026-10-24T16:00:00Z'}}
        lines=[{'gameId':'one','state':'open','market':'point spread','grade':{'edge':float('nan')}}]
        report=prep.prepare(games,lines,{}, {},now)
        self.assertEqual(report['football']['watchByFamily'],{})
        self.assertEqual(report['nba']['watch'],[])

