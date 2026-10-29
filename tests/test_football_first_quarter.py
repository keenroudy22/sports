import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import football_first_quarter as q
import boxscores as bx


def play(pid, quarter, yards, role='rusher', aid='10', kind='Rush'):
    return {'id': str(pid), 'period': {'number': quarter}, 'type': {'text': kind},
            'statYardage': yards, 'start': {'team': {'$ref': '/teams/1'}},
            'participants': [{'type': role, 'athlete': {'$ref': '/athletes/' + aid}}]}


class FirstQuarterTests(unittest.TestCase):
    def setUp(self):
        self.plays = {'count': 4, 'items': [play(1,1,-2), play(2,2,12),
            {**play(3,1,8,'passer','20','Pass Reception'), 'participants': [
                {'type':'passer','athlete':{'$ref':'/athletes/20'}},
                {'type':'receiver','athlete':{'$ref':'/athletes/30'}}]},
            {**play(4,1,0,aid='40'), 'start':{'team':{'$ref':'/teams/2'}}}]}
        self.box = {'10': {'car':2,'rushYds':10}, '30': {'rec':1,'recYds':8},
                    '40': {'car':1,'rushYds':0}}
        self.teams = {'1':{'plays':3},'2':{'plays':1}}

    def test_period_splits_preserve_negative_and_zero_not_full_game(self):
        out=q.extract(self.plays,self.box,self.teams)
        self.assertEqual(out['10']['rushYds'],-2)
        self.assertEqual(out['40']['rushYds'],0)
        self.assertEqual(out['30']['recYds'],8)
        self.assertEqual(out['10']['rec'],0)
        self.assertEqual(self.box['10']['rushYds'],10)

    def test_missing_period_duplicate_partial_and_wrong_team_hold(self):
        for change in ('period','duplicate','partial','team'):
            p=copy.deepcopy(self.plays)
            if change=='period':p['items'][0].pop('period')
            if change=='duplicate':p['items'][1]['id']='1'
            if change=='partial':p['items'].pop()
            if change=='team':p['items'][0]['start']['team']['$ref']='/teams/99'
            self.assertEqual(q.extract(p,self.box,self.teams),{},change)

    def test_failed_player_family_is_unknown_others_remain(self):
        box=copy.deepcopy(self.box);box['10']['rushYds']=11
        out=q.extract(self.plays,box,self.teams)
        self.assertNotIn('rushYds',out['10'])
        self.assertEqual(out['30']['recYds'],8)

    def test_overtime_stays_out_of_first_quarter(self):
        self.plays['items'][1]['period']['number']=5
        self.assertEqual(q.extract(self.plays,self.box,self.teams)['10']['rushYds'],-2)

    def test_unavailable_play_feed_is_not_a_zero_sample(self):
        self.assertEqual(q.extract(None,self.box,self.teams),{})
        p=copy.deepcopy(self.plays);p['items'][3]['period']['number']=2
        self.assertEqual(q.extract(p,self.box,self.teams),{})

    def test_touchdown_with_appended_conversion_counts_only_touchdown(self):
        p=copy.deepcopy(self.plays)
        td=p['items'][2]
        td.update(type={'text':'Passing Touchdown'}, scoringType={'name':'touchdown'},
                  text='Pass for 8 yards, TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. Runner rushes. ATTEMPT SUCCEEDS.')
        td['participants'].append({'type':'patScorer','athlete':{'$ref':'/athletes/10'}})
        out=q.extract(p,self.box,self.teams)
        self.assertEqual(out['30']['recYds'],8)
        self.assertEqual(out['10']['car'],1)
        self.assertEqual(out['10']['rushYds'],-2)
        td['type']={'text':'Two-Point Conversion'}
        self.assertEqual(q.extract(p,self.box,self.teams),{})

    def test_bounded_backfill_rejects_fanout_before_network(self):
        with self.assertRaises(ValueError):q.backfill([str(n) for n in range(7)])
        with self.assertRaises(ValueError):q.backfill(['1','1'])

    def test_player_payload_keeps_q1_separate_from_full_game_and_source_clock(self):
        import build_site
        from datetime import datetime, timezone
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fakegames import game
        g=game('1',datetime(2026,9,7,17,tzinfo=timezone.utc),'A','B',24,17,
               players=[{'id':'10','name':'Player','pos':'RB','team':'A','car':12,'rushYds':70}])
        g['league']='NFL';g['firstQuarter']={'10':{'car':2,'rushYds':-1}}
        g['retrievedAt']='2026-09-08T12:00:00Z'
        _, shards, _, _=build_site.build_players('NFL',[g],{}, {})
        player=shards[10 % build_site.SHARDS['NFL']]['10']
        self.assertEqual(player['firstQuarter'][0]['stats']['rushYds'],-1)
        self.assertEqual(player['firstQuarter'][0]['checkedAt'],g['retrievedAt'])
        self.assertEqual(player['rows'][0][8+list(build_site.LOG_KEYS).index('rushYds')],70)
        self.assertEqual(build_site.build_players('CFB',[{**g,'league':'CFB'}],{}, {})[1][10 % build_site.SHARDS['CFB']]['10']['firstQuarter'], [])
