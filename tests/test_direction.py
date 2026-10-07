"""The owner's direction rules (2026-10-07): every trigger and undo on synthetic rows, the bounds, idempotence,
and the gates, the card ranking, the fun tickets and the Climb honoring what the rules recorded; the stricter Climb
pool replayed on the repo's own stored prices."""
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import direction
import easy_parlay
import features
import gates
import ladder
import learn
import learning
import parlay
import review
import run
import scoreboard
import test_gates                   # a module import, so its TestCase classes are not collected (and run) twice
from test_gates import SNAPSHOT, context, prop_lean, total_lean

NOW = datetime(2026, 10, 13, 12, 30, tzinfo=timezone.utc)        # a Tuesday, the weekly learning run
DAY = timedelta(days=1)


def stamp(moment):
    return direction.stamp(moment)


def play(i, segment='NFL/total', result='loss', odds=-110, clv=-0.5, at=None, **over):
    at = at or NOW - timedelta(days=10)
    row = {'id': f'{segment}-{i}-{stamp(at)}', 'segment': segment, 'decision': 'published', 'rules': [],
           'decidedAt': stamp(at + timedelta(minutes=i)), 'kickoff': stamp(at + timedelta(hours=3, minutes=i)),
           'result': result, 'odds': odds, 'clv': clv, 'gameIds': [f'G-{segment}-{i}-{stamp(at)}'], 'direction': 'over'}
    row.update(over)
    return row


def record(wins, losses, segment='NFL/total', clv=-0.5, at=None, odds=-110):
    return [play(i, segment, 'win' if i < wins else 'loss', odds, clv, at) for i in range(wins + losses)]


def keys(moves):
    return [m['key'] for m in moves]


def evaluate(policy, rows=(), at=NOW, **evidence):
    return direction.evaluate(policy, dict({'rows': list(rows)}, **evidence), at)


def settle(policy, rows=(), at=NOW, **evidence):
    moves = evaluate(policy, rows, at, **evidence)
    return moves, direction.apply(policy, moves, at)


class SegmentEdgeBarTests(unittest.TestCase):
    def test_twenty_under_break_even_without_clv_raises_two_points_up_to_six_and_never_twice(self):
        # CLV exactly 0 meets the raise rule (CLV <= 0) but not the pause rule (CLV < 0), so the bar can climb to +6;
        # with negative CLV the season-long pause takes over first (see SegmentPauseTests).
        policy = learning.default_policy()
        rows = record(7, 13, clv=0.0)                     # 35% against 52.4% break-even
        moves, applied = settle(policy, rows)
        self.assertEqual(keys(moves), ['raise:NFL/total'])
        self.assertEqual((moves[0]['from'], moves[0]['to']), (0.0, 2.0))
        self.assertEqual(moves[0]['trigger']['n'], 20)
        self.assertIn('Raised NFL totals', moves[0]['sentence'])
        self.assertTrue(moves[0]['sentence'].endswith(' To undo, tell Codex: undo raise:NFL/total.'), moves[0]['sentence'])
        self.assertNotIn('Reply', moves[0]['sentence'], 'the ping is a one-way notification; it cannot take a reply')
        self.assertIn('step it back 2 points', moves[0]['undo'])
        self.assertEqual(applied[0]['engine'], 'direction')
        self.assertEqual(direction.edge_raise(policy, 'NFL/total', NOW), 2.0)
        self.assertEqual(evaluate(policy, rows), [], 'the same evidence a second time moves nothing')
        for week, expected in ((1, 4.0), (2, 6.0)):
            later = rows + record(7, 13, clv=0.0, at=NOW + (7 * week - 6) * DAY)     # decided after the last move
            settle(policy, later, NOW + 7 * week * DAY)
            self.assertEqual(direction.edge_raise(policy, 'NFL/total', NOW + 7 * week * DAY), expected)
            rows = later
        stuck = rows + record(5, 15, clv=0.0, at=NOW + 15 * DAY)
        found = keys(evaluate(policy, stuck, NOW + 21 * DAY))
        self.assertNotIn('raise:NFL/total', found, '+6 over the Oct 7 rule is the ceiling')
        self.assertIn('card', found, 'the whole-card rule still sees the losing run')

    def test_the_next_twenty_at_break_even_with_clv_step_back_two_points(self):
        policy = learning.default_policy()
        rows = record(7, 13)
        settle(policy, rows)
        recovered = rows + record(12, 8, clv=0.3, at=NOW + DAY)
        moves, _ = settle(policy, recovered, NOW + 7 * DAY)
        self.assertEqual([(m['rule'], m['to']) for m in moves], [('edge-step-back', 0.0)])
        self.assertEqual(direction.edge_raise(policy, 'NFL/total', NOW + 7 * DAY), 0.0)
        self.assertEqual(evaluate(policy, recovered, NOW + 8 * DAY), [])

    def test_no_raise_without_twenty_measured_clv_or_a_five_point_gap(self):
        policy = learning.default_policy()
        self.assertEqual(evaluate(policy, record(6, 13)), [], 'nineteen graded is not twenty')
        self.assertEqual(evaluate(policy, [dict(r, clv=None) for r in record(7, 13)]), [], 'CLV unmeasured')
        self.assertEqual(evaluate(policy, record(7, 13, clv=0.2)), [], 'beating the close')
        self.assertEqual(evaluate(policy, record(10, 10)), [], '50% is under 52.4% by less than five points')

    def test_a_raised_bar_is_honored_by_every_straight_gate_and_the_ranking(self):
        policy = gates.learning.default_policy()
        policy['direction'] = {'segments': {'NFL/total': {'raise': 2.0, 'raiseSince': '2026-09-01T00:00:00Z'}}}
        ordinary = gates.lean_edge(total_lean(), context(policy=policy))
        self.assertFalse(ordinary.ok)
        self.assertIn('needs +3.0', ordinary.reason, 'the 1.0 written rule plus the +2 raise')
        strong = gates.lean_edge(total_lean(), context(policy=policy, snapshots={'NFL-1': [dict(SNAPSHOT, total=49.0)]}))
        self.assertTrue(strong.ok, strong.reason)
        with mock.patch.object(gates, 'desk_for', return_value={'calibrated': True, 'edgePoints': 2.5}):
            researched = total_lean(modelLean=False)
            self.assertTrue(gates.straight_value(researched, context()).ok)
            self.assertTrue(gates.straight_value(researched, context(policy=policy)).ok)
            policy['direction']['segments']['NFL/total']['raise'] = 4.0
            refused = gates.straight_value(researched, context(policy=policy))
            self.assertFalse(refused.ok)
            self.assertIn('direction rules require +4', refused.reason)
        prop_policy = gates.learning.default_policy()
        prop_policy['calibration']['NFL/prop'] = {'k': 1.0, 'n': 500}
        board = {'props': {'markets': []}}                 # no trailing-market caution in this check
        with mock.patch.object(gates, 'desk_for', return_value={'rawChance': 0.60}):      # 6.5 points over -115
            self.assertTrue(gates.prop_calibrated_value(prop_lean(), context(policy=prop_policy, scoreboard=board)).ok)
            prop_policy['direction'] = {'segments': {'NFL/prop:recYds': {'raise': 6.0}}}
            self.assertFalse(gates.prop_calibrated_value(prop_lean(), context(policy=prop_policy, scoreboard=board)).ok,
                             'needs 2 + 6')
            prop_policy['direction']['segments']['NFL/prop:recYds']['raise'] = 4.0
            verdict = gates.prop_calibrated_value(prop_lean(), context(policy=prop_policy, scoreboard=board))
            self.assertTrue(verdict.ok)
            self.assertIn('direction rules raised the bar to +6', verdict.reason)

    def test_a_move_never_reaches_an_evaluation_from_before_it_was_made(self):
        policy = gates.learning.default_policy()
        policy['direction'] = {'segments': {'NFL/total': {'raise': 6.0, 'raiseSince': '2026-10-01T00:00:00Z',
                                                          'paused': True, 'pauseSince': '2026-10-01T00:00:00Z'}}}
        before = context(policy=policy)               # 2026-09-27: a replay of a pick published before the moves
        self.assertTrue(gates.lean_edge(total_lean(), before).ok)
        self.assertTrue(gates.learned_pause(total_lean(), before).ok)
        after = context(policy=policy, now=datetime(2026, 10, 2, tzinfo=timezone.utc))
        self.assertFalse(gates.learned_pause(total_lean(), after).ok)


class SegmentPauseTests(unittest.TestCase):
    def test_thirty_at_minus_five_units_with_negative_clv_pause_the_segment_as_a_best_bet(self):
        policy = learning.default_policy()
        rows = record(12, 18, clv=-0.3)                    # -7.09u
        moves, _ = settle(policy, rows)
        self.assertEqual(keys(moves), ['pause:NFL/total'], 'the pause supersedes a raise in the same week')
        self.assertIn('Paused NFL totals as a best bet (12-18, -7.1u, CLV -0.30). Still on the board as research.',
                      moves[0]['sentence'])
        self.assertTrue(direction.paused(policy, 'NFL/total', NOW))
        self.assertEqual(evaluate(policy, rows), [], 'idempotent')
        self.assertFalse(learning.paused(policy, 'NFL/total'), 'the older performance caution flag is untouched')

    def test_a_direction_pause_refuses_every_straight_kind_but_not_the_older_caution(self):
        policy = gates.learning.default_policy()
        policy['direction'] = {'segments': {'NFL/total': {'paused': True, 'pauseSince': '2026-09-20T00:00:00Z'}}}
        for kind in ('modelLean', 'favorite', 'researched'):
            ok, decisions = gates.admit(total_lean(confidence=3), context(policy=policy, snapshots={'NFL-1': [dict(SNAPSHOT, total=49.0)]}), kind)
            self.assertFalse(ok)
            refusal = next(d for d in gates.refusals(decisions) if d.rule == 'learned_pause')
            self.assertIn('paused as a best bet', refusal.reason)
            self.assertTrue(refusal.data['directionPause'])
        self.assertTrue(gates.learned_pause(prop_lean(), context(policy=policy)).ok, 'other segments are unaffected')
        caution = gates.learning.default_policy()
        caution['segments']['NFL/total'] = {'paused': True}
        self.assertTrue(gates.learned_pause(total_lean(), context(policy=caution)).ok,
                        'the legacy flag stays a caution and a higher bar, never a veto')

    def test_thirty_shadow_plays_at_break_even_with_positive_clv_restore_it_at_a_raised_bar(self):
        policy = learning.default_policy()
        settle(policy, record(12, 18, clv=-0.3))
        shadow = [dict(r, decision='refused', rules=['learned_pause', 'card_cap'])
                  for r in record(18, 12, clv=0.4, at=NOW + DAY)]
        duplicates = [dict(r, id=r['id'] + '-again', decidedAt=stamp(NOW + 2 * DAY)) for r in shadow[:5]]
        other = [dict(r, decision='refused', rules=['learned_pause', 'qb_available']) for r in record(5, 0, at=NOW + DAY)]
        self.assertEqual(direction.tally(direction.shadow(shadow + duplicates + other))['n'], 30,
                         'a line seen at every run counts once; a non-threshold refusal is not a near miss')
        moves, _ = settle(policy, record(12, 18, clv=-0.3) + shadow + duplicates, NOW + 14 * DAY)
        self.assertEqual([(m['rule'], m.get('raiseTo')) for m in moves], [('segment-restore', 2.0)])
        self.assertFalse(direction.paused(policy, 'NFL/total', NOW + 14 * DAY))
        self.assertEqual(direction.edge_raise(policy, 'NFL/total', NOW + 14 * DAY), 2.0)
        self.assertEqual(evaluate(policy, record(12, 18, clv=-0.3) + shadow, NOW + 15 * DAY), [])

    def test_a_shadow_short_of_thirty_or_without_positive_clv_keeps_the_pause(self):
        policy = learning.default_policy()
        settle(policy, record(12, 18, clv=-0.3))
        for rows in (record(18, 11, clv=0.4, at=NOW + DAY), record(18, 12, clv=0.0, at=NOW + DAY)):
            shadow = [dict(r, decision='refused', rules=['learned_pause']) for r in rows]
            self.assertEqual(evaluate(policy, shadow, NOW + 14 * DAY), [])


class PriorityTests(unittest.TestCase):
    def test_a_winning_segment_ranks_first_inside_the_caps_and_ends_below_either_mark(self):
        policy = learning.default_policy()
        rows = record(20, 10, segment='NFL/prop:recYds', clv=0.1)          # +8.18u
        moves, _ = settle(policy, rows)
        self.assertEqual(keys(moves), ['priority:NFL/prop:recYds'])
        self.assertIn('Caps unchanged', moves[0]['sentence'])
        self.assertTrue(direction.priority(policy, 'NFL/prop:recYds', NOW))
        self.assertEqual(gates.CARD, {'weekend': 5, 'weekday': 1}, 'priority never raises a cap')
        self.assertEqual(evaluate(policy, rows), [])
        slump = rows + record(1, 9, segment='NFL/prop:recYds', clv=0.1, at=NOW + DAY)    # +8.18 + 0.91 - 9 = +0.09u
        moves, _ = settle(policy, slump, NOW + 7 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['segment-priority-end'])
        self.assertFalse(direction.priority(policy, 'NFL/prop:recYds', NOW + 7 * DAY))

    def test_rank_card_puts_a_priority_segment_first_and_a_paused_one_last(self):
        def candidate(key, edge, market):
            return {'id': key, '_league': 'NFL', 'marketType': market, '_row': {'id': key, 'grade': {'edge': edge}}}
        policy = gates.learning.default_policy()
        ctx = context(policy=policy, scoreboard={'props': {'markets': []}})
        wanted = [candidate('total', 4.0, 'total'), candidate('spread', 2.0, 'spread')]
        self.assertEqual([c['id'] for c in run.rank_card(wanted, ctx)], ['total', 'spread'])
        policy['direction'] = {'segments': {'NFL/spread': {'priority': True}}}
        self.assertEqual([c['id'] for c in run.rank_card(wanted, ctx)], ['spread', 'total'])
        policy['direction'] = {'segments': {'NFL/total': {'paused': True}}}
        self.assertEqual([c['id'] for c in run.rank_card(wanted, ctx)], ['spread', 'total'])
        policy['direction'] = {'segments': {'NFL/total': {'raise': 6.0}}}
        ranked = run.rank_card(wanted, ctx)
        self.assertEqual([c['id'] for c in ranked], ['spread', 'total'], 'an edge under the raised bar goes behind')
        self.assertEqual(ranked[1]['_rank']['requiredEdge'], 6.0)


def card_rows(wins=26, losses=34, at=None):
    """Sixty straight plays spread over twelve segments, so no single segment moves."""
    rows = []
    for i in range(wins + losses):
        rows.append(play(i, f'NFL/prop:m{i % 12}', 'win' if i < wins else 'loss', -110, 0.0, at))
    return rows


class CardCapTests(unittest.TestCase):
    def test_minus_eight_units_over_the_last_sixty_cuts_the_weekend_card_to_three_for_two_weeks(self):
        policy = learning.default_policy()
        rows = card_rows()                                           # -10.36u
        moves, _ = settle(policy, rows)
        self.assertEqual(keys(moves), ['card'])
        self.assertEqual((moves[0]['from'], moves[0]['to'], moves[0]['expires']), (5, 3, stamp(NOW + 14 * DAY)))
        self.assertIn('Weekdays unchanged', moves[0]['sentence'])
        self.assertEqual(direction.weekend_cap(policy, NOW + DAY, 5), 3)
        self.assertEqual(direction.weekend_cap(policy, NOW + 14 * DAY, 5), 5, 'the cut ends on its own at two weeks')
        self.assertEqual(evaluate(policy, rows, NOW + 3 * DAY), [])
        self.assertEqual(evaluate(policy, card_rows(30, 30)), [], '-2.7u is no slump')

    def test_the_next_thirty_at_break_even_restore_five_early(self):
        policy = learning.default_policy()
        rows = card_rows()
        settle(policy, rows)
        moves, _ = settle(policy, rows + card_rows(17, 13, at=NOW + DAY), NOW + 9 * DAY)
        self.assertEqual([(m['rule'], m['to']) for m in moves], [('card-cap-restore', 5)])
        self.assertEqual(direction.weekend_cap(policy, NOW + 9 * DAY, 5), 5)

    def test_at_two_weeks_it_restores_unless_new_losses_still_agree(self):
        policy = learning.default_policy()
        rows = card_rows()
        settle(policy, rows)
        quiet = copy.deepcopy(policy)
        moves, _ = settle(quiet, rows, NOW + 14 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['card-cap-restore'], 'no new evidence: the two weeks are up')
        self.assertEqual(evaluate(quiet, rows, NOW + 21 * DAY), [], 'old losses alone never cut it again')
        losing = rows + card_rows(3, 7, at=NOW + DAY)
        moves, _ = settle(policy, losing, NOW + 14 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['card-cap-extend'])
        self.assertEqual(direction.weekend_cap(policy, NOW + 20 * DAY, 5), 3)

    def test_card_cap_gate_honors_the_cut_on_weekends_only(self):
        team = lambda key, gid: total_lean(id=key, gameIds=[gid], publishedAt='2026-09-25T12:00:00Z')
        prop = lambda key, gid: prop_lean(id=key, gameIds=[gid], athleteId=key, publishedAt='2026-09-26T12:00:00Z')
        three = {'a': team('a', 'NFL-2'), 'b': team('b', 'NFL-3'), 'c': prop('c', 'NFL-4')}
        policy = gates.learning.default_policy()
        cards = lambda picks: context(games=test_gates.CardTests.GAMES, first=picks, latest=picks, policy=policy)
        self.assertTrue(gates.card_cap(prop_lean(), cards(three)).ok, 'baseline: 3 of 5')
        policy['direction'] = {'card': {'weekendCap': 3, 'since': '2026-09-20T00:00:00Z', 'until': '2026-10-04T00:00:00Z'}}
        refused = gates.card_cap(prop_lean(), cards(three))
        self.assertFalse(refused.ok)
        self.assertIn('the card is 3', refused.reason)
        self.assertTrue(gates.card_cap(total_lean(gameIds=['MNF']), cards({})).ok, 'the weekday card is unchanged')
        policy['direction']['card']['until'] = '2026-09-27T12:00:00Z'
        self.assertTrue(gates.card_cap(prop_lean(), cards(three)).ok, 'expired: back to 5 at once')


def tickets(results, start=None, odds=600):
    start = start or NOW - timedelta(days=40)
    return [{'id': f't{i}-{stamp(start)}', 'publishedAt': stamp(start + i * timedelta(hours=6)), 'result': result,
             'odds': odds} for i, result in enumerate(results)]


class FunTicketTests(unittest.TestCase):
    def test_no_win_in_twelve_shortens_fun_tickets_for_two_weeks_and_two_wins_in_ten_end_it(self):
        policy = learning.default_policy()
        cold = tickets(['loss'] * 12)
        moves, _ = settle(policy, tickets=cold)
        self.assertEqual(keys(moves), ['fun'])
        self.assertIn('+300 to +800, 3-4 legs', moves[0]['sentence'])
        self.assertEqual(direction.fun_shape(policy, NOW + DAY), direction.FUN_SHAPE)
        self.assertIsNone(direction.fun_shape(policy, NOW + 14 * DAY))
        self.assertEqual(evaluate(policy, tickets=cold), [])
        warm = cold + tickets(['loss', 'win', 'loss', 'win'], start=NOW + DAY)
        moves, _ = settle(policy, tickets=warm, at=NOW + 5 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['fun-short-end'])
        self.assertIsNone(direction.fun_shape(policy, NOW + 5 * DAY))

    def test_minus_three_units_over_twenty_also_triggers(self):
        twenty = tickets(['win'] + ['loss'] * 19, odds=300)          # +0.75 - 4.75 = -4.0u at 0.25u
        self.assertEqual(keys(evaluate(learning.default_policy(), tickets=twenty)), ['fun'])
        self.assertEqual(evaluate(learning.default_policy(), tickets=tickets(['loss'] * 11)), [], 'eleven is not twelve')

    def test_the_shorter_shape_bounds_the_longshot_and_skips_paused_segments(self):
        from test_parlay import BuildTests, NOW as SUNDAY
        rows = BuildTests.rows
        ticket, _ = parlay.build(rows, SUNDAY, target=500)
        shaped, reason = parlay.build(rows, SUNDAY, target=300, max_legs=4, price_range=(300, 800))
        self.assertIsNone(reason)
        self.assertTrue(300 <= shaped['odds'] <= 800 and 3 <= len(shaped['legs']) <= 4)
        none, why = parlay.build(rows, SUNDAY, target=300, max_legs=4, price_range=(9000, 9500))
        self.assertIsNone(none)
        self.assertIn('+9000 to +9500', why)
        policy = learning.default_policy()
        policy['direction'] = {'funTickets': {'active': True, 'since': '2026-09-19T00:00:00Z', 'until': '2026-10-03T00:00:00Z'}}
        ctx = SimpleNamespace(now=SUNDAY, first={}, latest={}, policy=policy, prop_odds={})
        pick, _ = run.longshot_candidate(rows, {}, SUNDAY, 'NFL', (), ctx)
        self.assertTrue(300 <= pick['odds'] <= 800 and len(pick['legs']) <= 4, pick['odds'])
        policy['direction']['segments'] = {'NFL/total': {'paused': True}}
        none, why = run.longshot_candidate(rows, {}, SUNDAY, 'NFL', (), ctx)
        self.assertIsNone(none, 'every board leg here is an NFL total, paused as a best bet')
        policy['direction'] = {}
        plain, _ = run.longshot_candidate(rows, {}, SUNDAY, 'NFL', (), ctx)
        self.assertEqual(plain['odds'], ticket['odds'], 'without the move the longshot is unchanged')

    def test_easy_parlays_also_take_no_leg_from_a_paused_segment_while_fun_tickets_are_shorter(self):
        import test_ladder
        gids = ('g1', 'g2', 'g3', 'g4')
        games = {gid: test_ladder.game(gid, f'Away {gid}', f'Home {gid}') for gid in gids}
        world = test_ladder.ctx()
        world.snapshot = test_ladder.snapshot
        for gid in gids:
            world.names[f'{gid}p'] = f'Player {gid.upper()}'
            world.appearances[f'{gid}p'] = 5
        world.prop_odds = {gid: test_ladder.record(gid, price=-350) for gid in gids}      # four legs pay about +173
        plain, why = easy_parlay.sharp_candidate(world, games, test_ladder.NOW, league='NFL')
        self.assertIsNotNone(plain, why)
        pause = {'NFL/prop:recYds': {'paused': True, 'pauseSince': '2026-09-20T00:00:00Z'}}
        fun = {'active': True, 'since': '2026-09-19T00:00:00Z', 'until': '2026-10-03T00:00:00Z'}
        world.policy = {'direction': {'funTickets': fun, 'segments': pause}}
        none, why = easy_parlay.sharp_candidate(world, games, test_ladder.NOW, league='NFL')
        self.assertIsNone(none, 'every leg here is an NFL receiving-yards line, paused as a best bet')
        world.policy = {'direction': {'funTickets': fun, 'segments': {'NFL/prop:rushYds': pause['NFL/prop:recYds']}}}
        other, _ = easy_parlay.sharp_candidate(world, games, test_ladder.NOW, league='NFL')
        self.assertEqual(other['odds'], plain['odds'], 'a pause elsewhere leaves this ticket alone')
        world.policy = {'direction': {'segments': pause}}
        outside, _ = easy_parlay.sharp_candidate(world, games, test_ladder.NOW, league='NFL')
        self.assertEqual(outside['odds'], plain['odds'], 'outside the two weeks the easy parlay is unchanged')


class ClimbTests(unittest.TestCase):
    def test_two_climbs_in_a_row_lost_at_step_one_or_two_make_the_next_pool_stricter_until_step_three(self):
        policy = learning.default_policy()
        climbs = [{'run': 1, 'lostAt': 2, 'endedAt': '2026-10-04T03:00:00Z'},
                  {'run': 2, 'lostAt': 1, 'endedAt': '2026-10-05T00:00:00Z'}]
        moves, _ = settle(policy, climbs=climbs, rungs=[])
        self.assertEqual(keys(moves), ['climb'])
        self.assertEqual((moves[0]['from'], moves[0]['to']), ('standard', 'strict'))
        self.assertIn('no leg from a paused or raised segment, still -180 to -130 together', moves[0]['sentence'])
        self.assertIn("no Climb segment is paused or raised today, so today's pool is unchanged", moves[0]['sentence'])
        self.assertTrue(moves[0]['sentence'].endswith('To undo, tell Codex: undo climb.'))
        self.assertEqual(direction.climb_rules(policy, NOW)['skipFlaggedSegments'], True)
        self.assertEqual(direction.in_force(policy, NOW), ['climb'])
        self.assertEqual(evaluate(policy, climbs=climbs, rungs=[]), [])
        reached = [{'id': 'r', 'step': 3, 'publishedAt': stamp(NOW + 3 * DAY)}]
        moves, _ = settle(policy, climbs=climbs, rungs=reached, at=NOW + 4 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['climb-strict-end'])
        self.assertIsNone(direction.climb_rules(policy, NOW + 4 * DAY))
        self.assertEqual(evaluate(policy, climbs=climbs, rungs=reached, at=NOW + 5 * DAY), [],
                         'the same two losses never trigger it again')

    def test_todays_climbs_one_lost_at_step_three_do_not_trigger(self):
        climbs = [{'run': 1, 'lostAt': 3, 'endedAt': '2026-10-04T03:18:26Z'},
                  {'run': 2, 'lostAt': 1, 'endedAt': '2026-10-05T00:00:05Z'}]
        self.assertEqual(evaluate(learning.default_policy(), climbs=climbs, rungs=[]), [])

    def test_the_stricter_pool_leaves_out_paused_or_raised_segments_and_still_builds_a_rung(self):
        from test_ladder import GAMES, NOW as SUNDAY, ctx
        strict = {'climb': {'strict': True, 'since': '2026-09-20T00:00:00Z'}}
        baseline, _ = ladder.candidate(ctx(), GAMES, SUNDAY)
        world = ctx()
        world.policy = {'direction': copy.deepcopy(strict)}
        pick, reason = ladder.candidate(world, GAMES, SUNDAY)
        self.assertIsNone(reason, 'nothing is paused or raised: the stricter pool still builds the same rung')
        self.assertEqual((pick['odds'], [leg['id'] for leg in pick['legs']]),
                         (baseline['odds'], [leg['id'] for leg in baseline['legs']]))
        self.assertTrue(ladder.TARGET[0] <= pick['odds'] <= ladder.TARGET[1])
        self.assertTrue(all(leg['chance'] >= ladder.MIN_CHANCE for leg in pick['legs']))
        held = {'direction pause': {'direction': dict(copy.deepcopy(strict), segments={'NFL/prop:recYds': {
                    'paused': True, 'pauseSince': '2026-09-20T00:00:00Z'}})},
                'direction raise': {'direction': dict(copy.deepcopy(strict), segments={'NFL/prop:recYds': {
                    'raise': 2.0, 'raiseSince': '2026-09-20T00:00:00Z'}})},
                'older caution': {'direction': copy.deepcopy(strict), 'segments': {'NFL/prop:recYds': {'paused': True}}},
                'older raised edge': {'direction': copy.deepcopy(strict), 'knobs': learning.default_policy()['knobs'],
                                      'segments': {'NFL/prop:recYds': {'minEdge': 6.0}}}}
        for name, policy in held.items():
            world.policy = policy
            none, why = ladder.candidate(world, GAMES, SUNDAY)
            self.assertIsNone(none, name)
            self.assertIn('the stricter Climb pool is on', why, name)
            self.assertEqual(direction.climb_held_back(policy, SUNDAY), ['NFL/prop:recYds'], name)
        world.policy = {'direction': dict(copy.deepcopy(strict), segments={'NFL/prop:rushYds': {
            'paused': True, 'pauseSince': '2026-09-20T00:00:00Z'}})}
        other, _ = ladder.candidate(world, GAMES, SUNDAY)
        self.assertEqual(other['odds'], baseline['odds'], 'another segment held back leaves this pool alone')
        world.policy = {'direction': {'segments': {'NFL/prop:recYds': {'paused': True, 'pauseSince': '2026-09-20T00:00:00Z'}}}}
        normal, _ = ladder.candidate(world, GAMES, SUNDAY)
        self.assertEqual(normal['odds'], baseline['odds'], 'without the Climb move the pool is the ladder\'s own')

    def test_the_stricter_pool_never_changes_the_ladder_rules_it_reads(self):
        self.assertEqual(direction.CLIMB_MARKETS, ladder.MARKETS)
        self.assertEqual((ladder.MIN_CHANCE, ladder.TARGET), (0.83, (-180, -130)))
        legs = [{'id': 'a', 'athleteId': '1', 'market': 'recYds'}, {'id': 'b', 'athleteId': '2', 'market': 'rushYds'}]
        policy = {'direction': {'segments': {'NFL/prop:recYds': {'raise': 2.0}}}}
        self.assertEqual([leg['id'] for leg in ladder.strict_legs(legs, policy, NOW, 'NFL')], ['b'])
        self.assertEqual(ladder.strict_legs(legs, {}, NOW, 'NFL'), legs, 'it only ever removes legs')
        self.assertIsNone(direction.flagged({'segments': {'NFL/prop:rec': {'minEdge': 5.0}},
                                             'knobs': learning.default_policy()['knobs']}, 'NFL/prop:rec'),
                          'a learned edge at its written value is not raised')

    def test_five_straight_game_days_without_a_rung_are_reported_never_loosened(self):
        days = [{'date': f'2026-10-{d:02d}', 'games': {'CFB': 3}, 'rung': False, 'blocked': False} for d in range(6, 13)]
        days[0]['rung'] = True
        days[2]['games'] = {'NFL': 1}                     # one game: not a day the Climb could use
        days[3]['blocked'] = True                         # a rung was still open
        self.assertEqual(direction.climb_dry_spell(days, '2026-10-13'), 4)
        days.append({'date': '2026-10-05', 'games': {'NFL': 14}, 'rung': False, 'blocked': False})
        self.assertEqual(direction.climb_dry_spell(days, '2026-10-13'), 4, 'the published rung on Oct 6 ends the count')
        days[0]['rung'] = False
        policy = learning.default_policy()
        moves = evaluate(policy, climbDays=days)
        self.assertEqual([(m['rule'], m.get('reportOnly')) for m in moves], [('climb-dry-spell', True)])
        self.assertEqual(direction.apply(policy, moves, NOW), [], 'a report changes nothing')
        self.assertEqual(policy['history'], [])


def prep(rows, start=None, stat='recYds', check='clears', shadow=False):
    start = start or NOW - timedelta(days=30)
    return [{'at': stamp(start + i * timedelta(hours=1)), 'stat': stat, 'hit': hit, 'priceCheck': check, 'shadow': shadow}
            for i, hit in enumerate(rows)]


class PrepListTests(unittest.TestCase):
    def test_under_sixty_percent_over_forty_raises_thresholds_and_floors_and_seventy_restores(self):
        policy = learning.default_policy()
        rows = prep([True] * 22 + [False] * 18, stat=None)                # 55%
        moves, _ = settle(policy, prep=rows)
        self.assertEqual(keys(moves), ['prep'])
        rules = direction.prep_rules(policy, NOW)
        self.assertEqual((rules['short'], rules['lastTen'], rules['season']), (0.85, 9, 0.75))
        self.assertEqual(rules['floors'], {'rec': 3.5, 'recYds': 39.5, 'rushYds': 49.5, 'passYds': 214.5})
        self.assertEqual(direction.prep_rules(learning.default_policy())['short'], 0.80, 'the baseline')
        self.assertEqual(evaluate(policy, prep=rows), [])
        better = rows + prep([True] * 29 + [False] * 11, start=NOW + DAY, stat=None)    # 72.5%
        moves, _ = settle(policy, prep=better, at=NOW + 10 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['prep-restore'])
        self.assertFalse(direction.prep_rules(policy, NOW + 10 * DAY)['raised'])

    def test_a_stat_under_half_over_twenty_drops_for_four_weeks_and_returns_on_a_good_shadow(self):
        policy = learning.default_policy()
        rows = prep([True] * 9 + [False] * 11, stat='rec')
        moves, _ = settle(policy, prep=rows)
        self.assertEqual(keys(moves), ['prep-stat:rec'])
        self.assertEqual(direction.prep_rules(policy, NOW + DAY)['dropped'], ['rec'])
        self.assertEqual(direction.prep_rules(policy, NOW + 28 * DAY)['dropped'], [])
        ghost = rows + prep([True] * 14 + [False] * 6, start=NOW + DAY, stat='rec', shadow=True)     # 70%
        moves, _ = settle(policy, prep=ghost, at=NOW + 7 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['prep-restore-stat'])

    def test_clears_rows_beating_history_rows_by_ten_points_shows_only_clears(self):
        rows = prep([True] * 15 + [False] * 5, check='clears', stat=None) + \
            prep([True] * 11 + [False] * 9, check='history', stat=None, start=NOW - timedelta(days=20))   # 75% vs 55%
        policy = learning.default_policy()
        moves, _ = settle(policy, prep=rows)
        self.assertEqual(keys(moves), ['prep-clears'])
        self.assertTrue(direction.prep_rules(policy, NOW)['clearsOnly'])


class CalibrationDriftTests(unittest.TestCase):
    def test_a_five_point_gap_in_a_band_of_fifty_is_flagged_once(self):
        props = [{'league': 'NFL', 'market': 'recYds', 'raw': 0.65, 'won': i % 2 == 0} for i in range(60)]
        policy = learning.default_policy()
        policy['calibration'] = {'NFL/prop': {'k': 1.0}}
        moves, _ = settle(policy, props=props)
        self.assertEqual([m['rule'] for m in moves], ['calibration-drift'])
        self.assertEqual(policy['direction']['calibrationFlags']['NFL/prop:recYds']['band'], '60-70%')
        self.assertFalse(moves[0]['notify'])
        self.assertTrue(moves[0]['action'].startswith('Flag in the Monday review'))
        self.assertNotIn('calibration page', moves[0]['action'], 'there is no calibration page')
        self.assertEqual(evaluate(policy, props=props), [])
        self.assertEqual(evaluate(policy, props=props + props[:20]), [], 'the same band, new figures: no new entry')
        cleared, _ = settle(policy, props=[dict(r, won=i % 3 != 0) for i, r in enumerate(props)], at=NOW + 7 * DAY)
        self.assertEqual(cleared[0]['to'], {}, 'a band back within five points clears its flag')
        fresh = learning.default_policy()
        fresh['calibration'] = {'NFL/prop': {'k': 1.0}}
        self.assertEqual(evaluate(fresh, props=props[:49]), [], 'forty-nine in a band is not fifty')


class BoundsTests(unittest.TestCase):
    def test_the_readers_clamp_whatever_the_policy_says_to_the_approved_range(self):
        policy = {'direction': {'segments': {'A': {'raise': -4}, 'B': {'raise': 20}, 'C': {'raise': 'lots'}},
                                'card': {'weekendCap': 1, 'since': '2026-10-01T00:00:00Z', 'until': '2026-12-01T00:00:00Z'}}}
        self.assertEqual([direction.edge_raise(policy, s, NOW) for s in 'ABC'], [0.0, 6.0, 0.0])
        self.assertEqual(direction.weekend_cap(policy, NOW, 5), 3, 'never below the approved 3')
        policy['direction']['card']['weekendCap'] = 9
        self.assertEqual(direction.weekend_cap(policy, NOW, 5), 5, 'never above the written card')
        self.assertEqual(direction.weekend_cap({}, NOW, 5), 5)
        self.assertEqual(direction.edge_raise(None, 'A'), 0.0)
        self.assertFalse(direction.paused({'direction': {'segments': {'A': {'paused': 'yes'}}}}, 'A'))

    def test_a_negative_raise_can_not_loosen_a_gate_below_the_oct_7_baseline(self):
        policy = gates.learning.default_policy()
        policy['direction'] = {'segments': {'NFL/total': {'raise': -5.0}}}
        baseline = gates.lean_edge(total_lean(), context())
        loosened = gates.lean_edge(total_lean(), context(policy=policy))
        self.assertEqual((loosened.ok, loosened.reason), (baseline.ok, baseline.reason))

    def test_apply_refuses_anything_outside_the_listed_moves(self):
        policy = learning.default_policy()
        with self.assertRaises(ValueError):
            direction.apply(policy, [direction.move('knobs:lean.minEdge', 'x', 'x', 'x', 1.0, 0.5, {}, 'a', 'u', 's', False)], NOW)
        self.assertEqual(policy['knobs']['lean.minEdge']['value'], 1.0)

    def test_moves_only_touch_segments_already_in_the_official_record(self):
        policy = learning.default_policy()
        refused_only = [dict(r, decision='refused', rules=['prop_raw_edge'])
                        for r in record(0, 40, segment='NBA/prop:points', clv=-1.0)]
        self.assertEqual(evaluate(policy, refused_only), [], 'research and refusals never create a market')
        mixed = record(7, 13) + refused_only
        self.assertEqual({m['segment'] for m in evaluate(policy, mixed)}, {'NFL/total'})

    def test_the_learning_rule_set_is_inside_the_shadow_rules(self):
        self.assertLessEqual(learn.THRESHOLD_RULES, direction.SHADOW_RULES)

    def test_an_owner_veto_undoes_a_move_and_blocks_it_for_four_weeks(self):
        policy = learning.default_policy()
        rows = record(12, 18, clv=-0.3)
        settle(policy, rows)
        policy['direction']['vetoes']['pause:NFL/total'] = {'at': stamp(NOW + DAY), 'until': stamp(NOW + 29 * DAY)}
        moves, _ = settle(policy, rows, NOW + 2 * DAY)
        self.assertEqual([m['rule'] for m in moves], ['owner-veto'])
        self.assertFalse(direction.paused(policy, 'NFL/total', NOW + 2 * DAY))
        fresh = rows + record(12, 18, clv=-0.3, at=NOW + 3 * DAY)
        self.assertNotIn('pause:NFL/total', keys(evaluate(policy, fresh, NOW + 10 * DAY)), 'blocked while the veto stands')
        self.assertNotIn('pause:NFL/total', keys(evaluate(policy, rows, NOW + 30 * DAY)), 'the vetoed evidence never returns')
        self.assertIn('pause:NFL/total', keys(evaluate(policy, fresh, NOW + 30 * DAY)), 'thirty new plays after four weeks may')


class ClimbStoredPoolTests(unittest.TestCase):
    """The stricter Climb pool replayed on the repo's own stored prices (data/prop-odds with the stored forecasts,
    box scores and published plays, each as of the scan), on every stored game day through Oct 7 at the desk's Climb
    scan times. Read only. The replaced draft (leg chance 0.86 with two books agreeing) kept none of these rungs."""
    CUTOFF = date(2026, 10, 7)                # stored days only; the stores are append-only, so these never change
    SCANS = ((6, 45), (8, 30), (10, 0), (11, 45), (13, 30), (16, 0), (17, 30), (20, 0))
    # The learning policy as it stood on Oct 7: both leagues' prop calibration and the older NFL totals caution.
    OCT7 = {'knobs': learning.default_policy()['knobs'],
            'calibration': {'NFL/prop': {'k': 0.13, 'n': 538}, 'CFB/prop': {'k': 0.23, 'n': 398}},
            'segments': {'NFL/total': {'paused': True, 'since': '2026-09-24T15:10:33Z'}}}
    STRICT = {'climb': {'strict': True, 'since': '2026-09-01T00:00:00Z'}}

    @classmethod
    def setUpClass(cls):
        eastern = direction.EASTERN
        stores = gates.Stores()
        records = {scoreboard.game_id(g): g for g in features.load()}
        by_day = defaultdict(list)
        for gid in stores.prop_odds:
            if gid in records:
                by_day[gates.when(records[gid]['kickoff']).astimezone(eastern).date()].append(gid)
        cls.scans = []
        for day in sorted(d for d in by_day if d <= cls.CUTOFF):
            games = {gid: dict(records[gid], id=gid, state='pre') for gid in by_day[day]}
            for hour, minute in cls.SCANS:
                now = datetime(day.year, day.month, day.day, hour, minute, tzinfo=eastern).astimezone(timezone.utc)
                # As ladder.candidate does: a league needs two games left today and its own player calibration.
                slate = {league: ladder.todays_games(games, now, league) for league in direction.CLIMB_LEAGUES
                         if cls.OCT7['calibration'].get(f'{league}/prop')}
                slate = {league: today for league, today in slate.items() if len(today) >= 2}
                if not slate:
                    continue
                ctx = stores.as_of(now)
                ctx.games.update(games)             # the stored forecasts are read through the context's games
                ctx.injuries = {}                   # today's injury report is no as-of record: a later listing would
                for league, today in slate.items():  # otherwise shrink these past scans and change the test over time
                    legs = [leg for g in today for leg in ladder.legs_for_game(g, ctx.prop_odds.get(g['id']), ctx, now, {})]
                    cls.scans.append((now, league, gates.without_straight_players(legs, ctx)))

    def pairs(self, policy=None):
        """Every eligible rung on the stored scans: the ladder's own pool, or the stricter pool under `policy`."""
        out = []
        for now, league, legs in self.scans:
            pool = ladder.strict_legs(legs, policy, now, league) if policy is not None else legs
            out += [(now, league, book, a['id'], b['id']) for book, a, b, _, _ in ladder.pairs(pool)]
        return out

    def rungs(self, policy):
        built = []
        for now, league, legs in self.scans:
            ticket, _ = ladder.build(ladder.strict_legs(legs, policy, now, league))
            if ticket:
                built.append(ticket)
        return built

    def test_the_stricter_pool_keeps_at_least_forty_percent_of_the_stored_rungs_and_never_none(self):
        baseline = self.pairs()
        self.assertGreater(len(baseline), 0, 'the stored prices hold eligible rungs')
        policy = dict(copy.deepcopy(self.OCT7), direction=copy.deepcopy(self.STRICT))
        self.assertIsNotNone(direction.climb_rules(policy, NOW))
        kept = self.pairs(policy)
        self.assertGreaterEqual(len(kept), 0.4 * len(baseline))
        self.assertGreater(len(kept), 0)
        built = self.rungs(policy)
        self.assertTrue(built, 'the stricter pool still builds a rung')
        for ticket in built:
            self.assertTrue(ladder.TARGET[0] <= ticket['odds'] <= ladder.TARGET[1])
            self.assertTrue(all(leg['chance'] >= ladder.MIN_CHANCE for leg in ticket['legs']))

    def test_holding_back_any_one_climb_segment_still_leaves_a_stored_rung(self):
        baseline = self.pairs()
        segments = sorted({direction.leg_segment(leg, league) for _, league, legs in self.scans for leg in legs})
        self.assertTrue(segments)
        for segment in segments:
            for how, entry in (('direction pause', {'paused': True, 'pauseSince': '2026-09-01T00:00:00Z'}),
                               ('direction raise', {'raise': 2.0, 'raiseSince': '2026-09-01T00:00:00Z'})):
                policy = dict(copy.deepcopy(self.OCT7),
                              direction=dict(copy.deepcopy(self.STRICT), segments={segment: entry}))
                kept = self.pairs(policy)
                self.assertGreater(len(kept), 0, f'{segment} {how}: never zero')
                self.assertLessEqual(len(kept), len(baseline))
                self.assertTrue(self.rungs(policy), f'{segment} {how}: a rung can still be built')
                held = {leg['id'] for now, league, legs in self.scans for leg in legs
                        if direction.leg_segment(leg, league) == segment}
                self.assertFalse({key for row in kept for key in row[3:]} & held, f'{segment} {how}: none of its legs')
            caution = dict(copy.deepcopy(self.OCT7), direction=copy.deepcopy(self.STRICT))
            caution['segments'][segment] = {'paused': True}
            self.assertEqual(len(self.pairs(caution)), len(self.pairs(policy)), f'{segment}: the older caution counts too')


class WeeklyWiringTests(unittest.TestCase):
    def store(self, root, rows):
        candidates = [{k: v for k, v in r.items() if k not in ('result', 'clv')} for r in rows]
        graded = [{'id': r['id'], 'result': r['result'], 'clv': r['clv'], 'close': None, 'value': None,
                   'gradedAt': r['decidedAt']} for r in rows]
        for row in candidates:
            row['season'] = 2026
        learning.append('candidates', 2026, candidates, root)
        learning.append('graded', 2026, graded, root)

    def test_weekly_applies_moves_to_the_policy_never_to_the_record_and_only_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.store(root, record(12, 18, clv=-0.3))
            digest = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.jsonl')}
            before = digest()
            report = learn.weekly(NOW, root=root, log_book={'posts': []}, games={}, record=({}, {}))
            self.assertEqual(digest(), before, 'the graded store is read, never written')
            self.assertEqual(boxscores.verify(root), [])
            self.assertEqual([e['key'] for e in report['direction']['applied']], ['pause:NFL/total'])
            self.assertIn('Paused NFL totals as a best bet', report['direction']['ping'])
            self.assertIn(direction.REPORT_LINK, report['direction']['ping'])
            policy = learning.load_policy(root / 'policy.json')
            self.assertTrue(direction.paused(policy, 'NFL/total', NOW))
            self.assertEqual([e['rule'] for e in policy['history'] if e.get('engine') == 'direction'], ['segment-pause'])
            text = (root / 'REPORT.md').read_text()
            self.assertIn('## Direction changes', text)
            self.assertIn('Paused NFL totals as a best bet', text)
            again = learn.weekly(NOW + timedelta(hours=1), root=root, log_book={'posts': []}, games={}, record=({}, {}))
            self.assertEqual(again['direction']['applied'], [], 'running twice never doubles a move')
            dry = learn.weekly(NOW, dry=True, root=Path(tempfile.mkdtemp(dir=folder)), log_book={'posts': []}, games={},
                               record=({}, {}))
            self.assertEqual(dry['direction']['applied'], [])

    def test_a_failing_direction_step_never_costs_the_rest_of_the_weeks_learning(self):
        def half_way(policy, moves, now):          # a failure after part of the policy was already changed
            policy['direction'] = {'segments': {'NFL/total': {'paused': True, 'pauseSince': direction.stamp(now)}}}
            raise ValueError('half way')
        for failure in (mock.patch.object(direction, 'step', side_effect=RuntimeError('boom')),
                        mock.patch.object(direction, 'apply', side_effect=half_way)):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.store(root, record(12, 18, clv=-0.3))
                with failure:
                    report = learn.weekly(NOW, root=root, log_book={'posts': []}, games={}, record=({}, {}))
                self.assertIn(report['directionError'], ('RuntimeError', 'ValueError'))
                self.assertIsNone(report['direction'])
                self.assertEqual([c['knob'] for c in report['changes']], ['lean.minEdge'],
                                 "the older segment learner's change still happened")
                policy = learning.load_policy(root / 'policy.json')
                self.assertEqual(policy['segments']['NFL/total']['minEdge'], 1.5, 'and it was saved')
                self.assertFalse(direction.paused(policy, 'NFL/total', NOW), 'no half-applied direction move is kept')
                self.assertEqual([e for e in policy['history'] if e.get('engine') == 'direction'], [])
                self.assertIn('The direction step failed this week', (root / 'REPORT.md').read_text())
                self.assertEqual(json.loads((root / 'report.json').read_text())['directionError'], report['directionError'])

    def test_the_tuesday_run_records_a_direction_error_without_a_ping(self):
        report = {'changes': [], 'direction': None, 'directionError': 'RuntimeError'}
        status = {'errors': []}
        tuesday = datetime(2026, 10, 13, 8, 30, tzinfo=direction.EASTERN)
        with mock.patch.object(learn, 'grade_pending', return_value=0), \
                mock.patch.object(learn, 'weekly', return_value=report), \
                mock.patch.object(run, 'alert') as alert, mock.patch.object(run, 'log'):
            run.remember([], NOW, tuesday, status)
        alert.assert_not_called()
        self.assertEqual(status['learning']['directionError'], 'RuntimeError')
        self.assertEqual(status['errors'], ['learning: direction rules: RuntimeError'])

    def test_the_tuesday_run_pings_the_owner_one_line_per_change(self):
        report = {'changes': [{}], 'direction': {'ping': 'Paused NFL totals as a best bet.\nDetails: x'}}
        status = {'errors': []}
        tuesday = datetime(2026, 10, 13, 8, 30, tzinfo=direction.EASTERN)
        with mock.patch.object(learn, 'grade_pending', return_value=0), \
                mock.patch.object(learn, 'weekly', return_value=report), \
                mock.patch.object(run, 'alert') as alert, mock.patch.object(run, 'log'):
            run.remember([], NOW, tuesday, status)
        alert.assert_called_once()
        self.assertIn('Paused NFL totals', alert.call_args[0][1])
        self.assertEqual(alert.call_args[1]['click'], direction.REPORT_LINK)
        self.assertEqual(status['errors'], [])

    def test_the_monday_review_box_lists_the_week_previews_the_next_run_and_carries_the_ping(self):
        policy = learning.default_policy()
        settle(policy, record(12, 18, clv=-0.3), NOW - 6 * DAY)
        text, ping = review.direction_packet(NOW, (NOW - 6 * DAY).date(), NOW.date(), policy=policy,
                                             rows=record(7, 13, segment='CFB/total'))
        self.assertIn('## Direction changes', text)
        self.assertIn('Paused NFL totals as a best bet', text)
        self.assertIn('Undo:', text)
        self.assertIn('Would change at the next weekly learning run', text)
        self.assertIn("Raised CFB totals' edge bar to +2", text)
        self.assertIn('NFL totals: paused as a best bet', text)
        self.assertEqual(ping.splitlines()[-1], f'Details: {direction.REPORT_LINK}')
        quiet, none = review.direction_packet(NOW + 30 * DAY, (NOW + 24 * DAY).date(), (NOW + 30 * DAY).date(),
                                              policy=learning.default_policy(), rows=[])
        self.assertIn('Applied:\n- none', quiet)
        self.assertIn('every rule is at its Oct 7 baseline', quiet)
        self.assertEqual(none, '')

    def test_the_evidence_comes_from_the_official_record_without_changing_it(self):
        from test_ladder import book_of, rung
        first, latest = book_of(rung('c1s1', '2026-10-01T12:00:00Z', 1, 50, 80, 'win', run=1),
                                rung('c1s2', '2026-10-02T12:00:00Z', 2, 64, 100, 'loss', run=1),
                                rung('c2s1', '2026-10-03T12:00:00Z', 1, 50, 80, 'loss', run=2))
        for i in range(12):
            key = f'NFL-2026-W4-longshot-{i}'
            first[key] = {'id': key, 'parlayType': 'longshot', 'legs': [{}, {}, {}], 'odds': 2000,
                          'publishedAt': f'2026-09-{10 + i:02d}T12:00:00Z'}
            latest[key] = dict(first[key], result='loss', settledAt=f'2026-09-{10 + i:02d}T23:00:00Z')
        first['old'] = {'id': 'old', 'parlayType': 'longshot', 'legs': [{}], 'historicalImport': True, 'publishedAt': '2026-09-01T12:00:00Z'}
        before = copy.deepcopy((first, latest))
        games = [{'league': 'NFL', 'kickoff': '2026-10-05T17:00:00Z'}, {'league': 'NFL', 'kickoff': '2026-10-05T20:00:00Z'},
                 {'league': 'CFB', 'kickoff': '2026-10-06T23:00:00Z'}, {'league': 'CFB', 'kickoff': '2026-10-06T23:30:00Z'}]
        found = direction.evidence([], first, latest, games, policy=learning.default_policy(), now=NOW)
        self.assertEqual((first, latest), before)
        self.assertEqual(len(found['tickets']), 12, 'the historical import never counts')
        self.assertEqual([(c['run'], c['lostAt']) for c in found['climbs']], [(1, 2), (2, 1)])
        days = {d['date']: d for d in found['climbDays']}
        self.assertEqual(days['2026-10-05']['games'], {'NFL': 2})
        self.assertEqual(days['2026-10-06']['games'], {}, 'college waits for its own calibration, as the Climb does')
        self.assertTrue(days['2026-10-03']['rung'])
        self.assertEqual(sorted(keys(direction.evaluate(learning.default_policy(), found, NOW))), ['climb', 'fun'])

    def test_the_command_line_veto_undoes_and_records_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'policy.json'
            policy = learning.default_policy()
            settle(policy, record(12, 18, clv=-0.3), datetime.now(timezone.utc) - DAY)
            learning.save_policy(policy, path)
            with mock.patch('builtins.print'):
                self.assertEqual(direction.main(['veto', 'pause:NFL/total', '--policy', str(path)]), 0)
            saved = learning.load_policy(path)
            self.assertFalse(direction.paused(saved, 'NFL/total'))
            self.assertIn('pause:NFL/total', saved['direction']['vetoes'])
            self.assertEqual(saved['history'][-1]['rule'], 'owner-veto')
            with self.assertRaises(SystemExit), mock.patch('sys.stderr'):
                direction.main(['veto', 'knobs', '--policy', str(path)])

    def test_a_veto_key_that_matches_nothing_in_force_warns_instead_of_looking_done(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'policy.json'
            policy = learning.default_policy()
            settle(policy, record(12, 18, clv=-0.3), datetime.now(timezone.utc) - DAY)
            learning.save_policy(policy, path)
            with mock.patch('builtins.print') as printed:
                self.assertEqual(direction.main(['veto', 'pause:NFL/totals', '--policy', str(path)]), 0)
            said = ' '.join(str(arg) for call in printed.call_args_list for arg in call.args)
            self.assertIn('warning: pause:NFL/totals matches no move in force, so nothing was undone', said)
            self.assertIn('In force now: pause:NFL/total.', said)
            self.assertTrue(direction.paused(learning.load_policy(path), 'NFL/total'), 'the real pause still stands')
            with mock.patch('builtins.print') as printed:
                direction.main(['veto', 'pause:NFL/total.', '--policy', str(path)])     # copied with the ping's period
            said = ' '.join(str(arg) for call in printed.call_args_list for arg in call.args)
            self.assertNotIn('warning', said)
            self.assertFalse(direction.paused(learning.load_policy(path), 'NFL/total'))

    def test_the_policy_loader_keeps_the_direction_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'policy.json'
            policy = learning.default_policy()
            settle(policy, record(7, 13))
            learning.save_policy(policy, path)
            loaded = learning.load_policy(path)
            self.assertEqual(direction.edge_raise(loaded, 'NFL/total', NOW), 2.0)
            self.assertEqual(json.loads(path.read_text())['direction']['segments']['NFL/total']['raise'], 2.0)


if __name__ == '__main__':
    unittest.main()
