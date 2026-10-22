import copy
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import game_alternates as a
import climb_validation as v
import ladder
import climb_prep

NOW=datetime(2026,10,22,18,tzinfo=timezone.utc)
GAME=dict(id='CFB-1', league='CFB', season=2026, kickoff='2026-10-22T23:00:00Z',
          home=dict(name='Home Team',short='HOME'), away=dict(name='Away Team',short='AWAY'))


def rows():
    out=[]
    for home,hp,ap,main in [(-7.5,-110,-110,True),(-1.5,-400,290,False),(1.5,-500,350,False)]:
        for side,price in [('home',hp),('away',ap)]:
            out.append((GAME,dict(market_type='point_spread',sportsbook='fanduel',
                selection_type=side,selection=GAME[side]['name'],line=home if side=='home' else -home,
                odds_american=price,is_main_line=main,is_alternate_line=not main,
                is_live=False,is_active=True,timestamp='2026-10-22T17:59:00Z')))
    return out


def record():
    return dict(gameId='CFB-1',retrievedAt='2026-10-22T18:00:00Z',
                books={'fanduel':dict(gameMarkets=a.parse(rows(),NOW)['CFB-1']['fanduel'])})


class GameAlternateTests(unittest.TestCase):
    def test_next_day_packet_is_planning_only_with_exact_holds(self):
        game=copy.deepcopy(GAME)
        game['kickoff']='2026-10-23T23:00:00Z'
        ctx=SimpleNamespace(games={'CFB-1':game},prop_odds={},snapshot=lambda _:None,
                            policy={},now=NOW)
        report=climb_prep.prepare(ctx,NOW)
        self.assertEqual(report['targetDate'],'2026-10-23')
        self.assertTrue(report['planningOnly'])
        self.assertEqual(report['games'][0]['supportedSpreadLegs'],0)
        self.assertIn('No complete',report['games'][0]['coverageHold'])

    def test_exact_two_sided_alternates_and_no_main_relabel(self):
        quotes=list(a.quotes(record()))
        self.assertEqual([(r[1],r[2],r[3]) for r in quotes],[('home',-1.5,-400),('home',1.5,-500)])

    def test_period_suspended_stale_unmatched_and_ambiguous_main_hold(self):
        for change in [dict(is_live=True),dict(is_active=False),dict(market_type='1st_half_point_spread'),
                       dict(timestamp='2026-10-22T15:00:00Z'),dict(selection='Unknown'),dict(is_main_line=False)]:
            source=[(g,dict(r,**change)) for g,r in rows()]
            self.assertEqual(a.parse(source,NOW),{},change)
        self.assertEqual(a.parse(rows()[::2],NOW),{})

    def test_conflicting_and_nonmonotone_prices_hold(self):
        source=rows()
        source.append((GAME,dict(source[0][1],odds_american=-120)))
        self.assertEqual(a.parse(source,NOW),{})
        source=rows()
        source[2][1]['odds_american']=150
        source[3][1]['odds_american']=-170
        self.assertEqual(a.parse(source,NOW),{})

    def test_validation_deduplicates_games_and_grades_spread_sign(self):
        game=dict(GAME,home={'score':20},away={'score':19},retrievedAt='2026-10-23T03:00:00Z')
        end=NOW+timedelta(days=1)
        offers=v.offers([record()]*10,{'CFB-1':game},end)
        self.assertEqual(len(offers),2) # distinct price bands, never ten repeated captures
        graded=v.grade(offers,{'CFB-1':game},end)
        self.assertEqual({r['line']:r['result'] for r in graded},{-1.5:'loss',1.5:'win'})
        self.assertTrue(all(not r['open'] for r in v.summarize(graded,end).values()))
        game['home']={}
        self.assertTrue(all(r['result'] is None for r in v.grade(offers,{'CFB-1':game},end)))

    def test_builder_requires_actual_open_segment_and_fresh_quote(self):
        ctx=SimpleNamespace(prop_odds={'CFB-1':record()},snapshot=lambda _: {},policy={},now=NOW)
        ctx.snapshot=lambda _: {'present':True}
        with patch.object(ladder.pricing,'price',return_value=dict(rawChance=.95,breakEven=.8,projection=-10)):
            self.assertEqual(ladder.alternate_spread_legs(GAME,ctx,NOW),[])
            with patch.object(ladder,'segment_hit_rate',return_value=.9):
                legs=ladder.alternate_spread_legs(GAME,ctx,NOW)
                self.assertTrue(legs)
                self.assertTrue(all(r['alternate'] is True for r in legs))
                self.assertEqual(ladder.alternate_spread_legs(GAME,ctx,NOW+timedelta(days=1)),[])
