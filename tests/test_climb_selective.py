import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import ladder
import parlay
import post_windows
import run
import ticket_cards
import ticket_kit
from test_ladder import ctx, game, GAMES, NOW, record, snapshot

THU = datetime(2026, 10, 22, 10, 45, tzinfo=timezone.utc)


def leg(n, price=-600, chance=.90, book='FanDuel'):
    return dict(id=f'l{n}', title=f'Team {n} moneyline', gameId=f'g{n}', book=book,
                odds=price, chance=chance, rawChance=chance, fairChance=chance-.05, marketType='moneyline',
                kickoff='2026-10-22T23:00Z', observedAt='2026-10-22T10:40Z')


def past(count):
    return {f'r{i}': dict(id=f'r{i}', parlayType='ladder', publishedAt=f'2026-10-{19+i:02d}T12:00Z',
                         ladder=dict(run=i+1, step=1, stake=50, payout=75), status='settled', result='loss')
            for i in range(count)}


class SelectiveClimbTests(unittest.TestCase):
    def test_three_supported_legs_make_ticket_without_cross_book_or_same_game(self):
        legs = [leg(i) for i in range(3)]
        ticket, reason = ladder.build(legs)
        self.assertIsNone(reason)
        self.assertEqual(len(ticket['legs']), 3)
        self.assertEqual(ticket['odds'], parlay.american((1+100/600)**3))
        self.assertIsNone(ladder.build(legs[:2])[0])
        self.assertIsNone(ladder.build([legs[0], legs[0], legs[1]])[0])
        self.assertIsNone(ladder.build([*legs[:2], dict(legs[2], book='DraftKings')])[0])
        self.assertTrue(all(len(chosen)<=3 for _,chosen,_,_ in ladder.tickets([leg(i) for i in range(5)])))

    def test_joint_chance_first_fewer_legs_for_tie_and_positive_price_edge_required(self):
        self.assertGreater(ladder.ticket_rank(.75,.03,[leg(0)],-175),
                           ladder.ticket_rank(.72,.10,[leg(0),leg(1)],-135))
        self.assertGreater(ladder.ticket_rank(.75,.03,[leg(0)],-175),
                           ladder.ticket_rank(.75,.03,[leg(0),leg(1)],-175))
        self.assertIsNone(ladder.build([leg(0, -175, .60)])[0])

    def test_week_counts_losses_across_restarts_once_and_includes_private_reservation(self):
        rows = past(2)
        rows['pending'] = dict(id='pending', parlayType='ladder', publishedAt='2026-10-21T13:00Z', _pendingRelease=True)
        week = ladder.weekly_status(rows, THU)
        self.assertEqual((week['posted'],week['remaining'],week['weekStart'],week['weekEnd']),
                         (3,0,'2026-10-19','2026-10-25'))
        self.assertEqual(ladder.weekly_status(rows, THU, exclude='pending')['posted'],2)
        self.assertIn('weekly Climb limit', ladder.weekly_refusal(SimpleNamespace(first=rows), THU))
        self.assertIsNone(ladder.weekly_refusal(SimpleNamespace(first=past(1)), THU))

    def test_eastern_monday_boundary_and_future_admissions(self):
        rows = past(1)
        rows['sunday'] = dict(parlayType='ladder', publishedAt='2026-10-26T03:59Z')
        rows['future'] = dict(parlayType='ladder', publishedAt='2026-10-27T12:00Z')
        self.assertEqual(ladder.weekly_status(rows,gates.when('2026-10-26T03:59Z'))['posted'],2)
        self.assertEqual(ladder.weekly_status(rows,gates.when('2026-10-26T04:00Z'))['posted'],0)

    def test_auto_and_manual_stop_at_weekly_cap_without_building_or_reading_bad_spec(self):
        world=ctx(first=past(3),latest=past(3))
        for call in (lambda:ladder.candidate(world,{},THU), lambda:ladder.manual_candidate(world,{},THU,{})):
            ticket,reason=call()
            self.assertIsNone(ticket)
            self.assertIn('weekly Climb limit',reason)

    def test_gate_and_release_recheck_shape_cap_and_unready_nba(self):
        games={f'g{i}':game(f'g{i}','Away','Home','2026-10-22T23:00Z') for i in range(3)}
        pick=dict(id='new', parlayType='ladder', legs=[leg(i) for i in range(3)], gameIds=list(games),book='FanDuel',
                  odds=parlay.american((1+100/600)**3),quotedAt='2026-10-22T10:40Z',expiresAt='2026-10-22T12:00Z')
        world=SimpleNamespace(now=THU,first=past(2),games=games)
        self.assertTrue(gates.ladder_selective(pick,world).ok)
        self.assertIsNone(run.private_release_refusal(dict(pick=pick,league='NFL'),world,THU))
        world.first=past(3)
        self.assertIn('weekly Climb limit',run.private_release_refusal(dict(pick=pick,league='NFL'),world,THU))
        world.first={}
        for changed in (dict(pick,legs=[]),dict(pick,legs=[*pick['legs'],leg(4)]),
                        dict(pick,legs=[leg(0),leg(0)]),dict(pick,book='DraftKings')):
            self.assertFalse(gates.ladder_selective(changed,world).ok)
        world.games={k:dict(g,league='NBA') for k,g in games.items()}
        self.assertIn('NBA',gates.ladder_selective(pick,world).reason)

    def test_discretionary_last_rung_pattern_cannot_bypass_proven_support(self):
        world=SimpleNamespace(now=THU,policy={},games={'g0':dict(league='CFB')})
        ticket=dict(odds=-210,legs=[dict(leg(0,-210,.702),marketType='spread',fairChance=None)])
        self.assertIn('cannot bypass',ladder.support_refusal(ticket,world))
        self.assertFalse(gates.ladder_supported(ticket,world).ok)
        self.assertIn(gates.ladder_supported,gates.RULES['ladder'])

    def test_manual_three_legs_retains_model_proven_segment_news_and_quote_boundaries(self):
        games={f'g{i}':game(f'g{i}','Away','Home',league='CFB') for i in range(3)}
        world=ctx();world.snapshot=lambda gid:snapshot('g1')
        spec=dict(book='FanDuel',quotedAt='2026-09-27T12:20Z',source='https://sportsbook.fanduel.com/',
                  legs=[dict(gameId=k,marketType='spread',direction='home',line=-1.5,odds=-600) for k in games])
        world.policy['ladderSegments']['CFB/spread/FanDuel']['hitRate']=.92
        with patch.object(ladder.pricing,'price',return_value=dict(rawChance=.92,breakEven=600/700,projection=-8)):
            ticket,reason=ladder.manual_candidate(world,games,NOW,spec)
            self.assertIsNone(reason);self.assertEqual(len(ticket['legs']),3)
            broken=copy.deepcopy(spec);broken['legs'].append(broken['legs'][0])
            self.assertIn('one to three',ladder.manual_candidate(world,games,NOW,broken)[1])
            broken=copy.deepcopy(spec);broken['legs'][1]['gameId']='g0'
            self.assertIn('one leg per game',ladder.manual_candidate(world,games,NOW,broken)[1])
            world.policy['ladderSegments']={}
            self.assertIn('not an open proven',ladder.manual_candidate(world,games,NOW,spec)[1])

    def test_under_prop_uses_actual_consistent_ladder_and_retains_role_holds(self):
        r=record('g1')
        quote=r['books']['draftkings']['markets']['recYds']['Player G1']
        quote['alternates']=[dict(line=99.5,over=300,under=-450)]
        found=ladder.legs_for_game(GAMES['g1'],r,ctx(),NOW)
        self.assertEqual([(l['direction'],l['line'],l['odds']) for l in found],[('under',99.5,-450)])
        self.assertIn('under 99.5',found[0]['title'])
        world=ctx(injuries={'NFL-g1h':{'g1p':{'status':'Questionable'}}})
        self.assertFalse(ladder.legs_for_game(GAMES['g1'],r,world,NOW))

    def test_spread_total_pool_needs_fresh_real_price_and_proven_segment(self):
        world=ctx();world.odds={'g1':dict(retrievedAt='2026-09-27T12:10Z',books={
            'fanduel':dict(spread=dict(home=-1.5,homePrice=-200,awayPrice=150))})}
        with patch.object(ladder.pricing,'price',return_value=dict(rawChance=.84,breakEven=2/3,projection=-8)):
            self.assertEqual([l['marketType'] for l in ladder.game_line_legs(GAMES['g1'],world,NOW)],['spread'])
            world.policy['ladderSegments']={}
            self.assertFalse(ladder.game_line_legs(GAMES['g1'],world,NOW))
            world.odds['g1']['retrievedAt']='2026-09-26T12:10Z'
            self.assertFalse(ladder.game_line_legs(GAMES['g1'],world,NOW))

    def test_thursday_opens_at_first_morning_check_without_rewriting_old_windows(self):
        self.assertEqual(post_windows.target('NFL','2026-10-23T00:15Z'),THU)
        self.assertEqual(post_windows.target('CFB','2026-10-22T23:00Z'),THU)
        self.assertEqual(post_windows.target('NFL','2026-10-19T00:20Z'),gates.when('2026-10-18T13:30Z'))

    def test_three_leg_current_ticket_art_fits_and_shows_every_leg(self):
        p=dict(run=4,step=1,stake=50,payout=79,banked=0,odds=-170,book='FanDuel',start=50,goal=1000,
               bank_this=16,next_stake=63,legs=[dict(title=f'Team {i} moneyline',odds=-600) for i in range(3)])
        card=ticket_cards.climb_card(p)
        self.assertEqual(ticket_kit.qa(card,'three-leg-climb'),[])
        for i in range(3):self.assertIn(f'Team {i}',card.svg())


if __name__=='__main__':unittest.main()
