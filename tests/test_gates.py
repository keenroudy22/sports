import sys
import unittest
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import build_site
from gates import Context

NOW = datetime(2026, 9, 27, 13, 0, tzinfo=timezone.utc)          # Sunday 9:00 ET, four hours before kickoff
KICKOFF = '2026-09-27T17:00Z'                                        # Sunday 1:00 PM ET
GAME = {'id': 'NFL-1', 'league': 'NFL', 'kickoff': KICKOFF, 'state': 'pre',
        'home': {'id': '10', 'abbreviation': 'DET'}, 'away': {'id': '20', 'abbreviation': 'BUF'}}
SNAPSHOT = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-27T10:00:00Z', 'kickoff': KICKOFF,
            'margin': 3.0, 'total': 48.0, 'sd': {'margin': 13.0, 'total': 12.0},
            'range80': {'margin': [-13.7, 19.7], 'total': [32.6, 63.4]},
            'players': {'home': {'players': [{'id': '77', 'pos': 'WR', 'recYds': [60.0, 30.5, 89.5]}]}, 'away': None}}
ODDS = {'gameId': 'NFL-1', 'retrievedAt': '2026-09-27T13:00:00Z',
        'books': {'draftkings': {'total': {'line': 44.5, 'over': -110, 'under': -110}, 'spread': {'home': -3, 'homePrice': -110, 'awayPrice': -110}},
                  'fanduel': {'total': {'line': 45.5, 'over': -105, 'under': -115}}}}
PROP_ODDS = {'gameId': 'NFL-1', 'retrievedAt': '2026-09-27T13:00:00Z',
             'books': {'draftkings': {'markets': {'recYds': {'Player Seven': {'line': 49.5, 'over': -115, 'under': -105}}}},
                       'fanduel': {'markets': {'recYds': {'Player Seven': {'line': 50.5, 'over': -110, 'under': -110}}}}}}


def total_lean(**over):
    pick = {'id': 'NFL-2026-W4-buf-det-over-44-5-dk', 'title': 'Bills at Lions over 44.5', 'status': 'active',
            'favorite': False, 'modelLean': True, 'marketType': 'total', 'line': 44.5, 'direction': 'over',
            'gameIds': ['NFL-1'], 'book': 'DraftKings', 'odds': -110, 'quotedAt': '2026-09-27T13:00:00Z',
            'quoteType': 'capture', 'expiresAt': '2026-09-27T15:45:00Z', 'confidence': 3, 'why': 'w', 'risk': 'r',
            'sources': ['https://www.espn.com/nfl/game/_/gameId/1'], 'league': 'NFL'}
    pick.update(over)
    return pick


def prop_lean(**over):
    pick = {'id': 'NFL-2026-W4-seven-over-49-5-recyds-dk', 'title': 'Player Seven OVER 49.5 receiving yards',
            'status': 'active', 'favorite': False, 'modelLean': True, 'position': 'WR', 'athleteId': '77',
            'market': 'recYds', 'line': 49.5, 'direction': 'over', 'gameIds': ['NFL-1'], 'book': 'DraftKings',
            'odds': -115, 'quotedAt': '2026-09-27T13:00:00Z', 'quoteType': 'capture',
            'expiresAt': '2026-09-27T15:45:00Z', 'confidence': 2, 'why': 'w', 'risk': 'r',
            'sources': ['https://www.espn.com/nfl/game/_/gameId/1'], 'league': 'NFL'}
    pick.update(over)
    return pick


def favorite_context(**over):
    """The same board with v2's total at 49: the 44.5 over clears the favorites bar."""
    return context(snapshots={'NFL-1': [dict(SNAPSHOT, total=49.0)]}, **over)


def context(**over):
    fields = dict(now=NOW, games={'NFL-1': GAME}, odds={'NFL-1': ODDS}, prop_odds={'NFL-1': PROP_ODDS},
                  odds_history={'NFL-1': [ODDS]}, passers={'NFL-10': ['5', '5', '5']},
                  snapshots={'NFL-1': [SNAPSHOT]}, names={'77': 'Player Seven', '5': 'Quarterback Five'},
                  appearances=defaultdict(int, {'77': 3}), player_team={'77': '10', '5': '10'}, starters={'NFL-10': '5'},
                  scoreboard={'props': {'markets': [{'market': 'recYds', 'graded': 158, 'closerThanLine': [66, 92]},
                                                    {'market': 'rec', 'graded': 158, 'closerThanLine': [80, 78]},
                                                    {'market': 'att', 'graded': 12, 'closerThanLine': [4, 8]}]}})
    fields.update(over)
    return Context(**fields)


def decision(rule, candidate, ctx):
    return rule(candidate, ctx)


class TwoSidedPriceTests(unittest.TestCase):
    def test_player_straight_requires_both_sides_at_exact_book_and_line(self):
        self.assertTrue(gates.two_sided_straight(prop_lean(), context()).ok)
        one_sided = {'NFL-1': {'books': {'draftkings': {'markets': {
            'recYds': {'Player Seven': {'line': 49.5, 'over': -115}}}}}}}
        self.assertFalse(gates.two_sided_straight(prop_lean(), context(prop_odds=one_sided)).ok)
        wrong_line = {'NFL-1': {'books': {'draftkings': {'markets': {
            'recYds': {'Player Seven': {'line': 50.5, 'over': -115, 'under': -105}}}}}}}
        self.assertFalse(gates.two_sided_straight(prop_lean(), context(prop_odds=wrong_line)).ok)

    def test_game_straight_requires_both_prices_too(self):
        self.assertTrue(gates.two_sided_straight(total_lean(), context()).ok)
        one_sided = {'NFL-1': {'books': {'draftkings': {'total': {'line': 44.5, 'over': -110}}}}}
        self.assertFalse(gates.two_sided_straight(total_lean(), context(odds=one_sided)).ok)


class NoForcedBestBetTests(unittest.TestCase):
    def test_four_point_floor_is_inclusive_and_requires_calibration(self):
        from unittest.mock import patch
        pick = prop_lean()
        with patch.object(gates, 'desk_for', return_value={'calibrated': True, 'edgePoints': 3.9}):
            self.assertFalse(gates.bar_4(pick, context()).ok)
        with patch.object(gates, 'desk_for', return_value={'calibrated': True, 'edgePoints': 4.0}):
            self.assertTrue(gates.bar_4(pick, context()).ok)
        with patch.object(gates, 'desk_for', return_value={'calibrated': False, 'edgePoints': 12.0}):
            self.assertFalse(gates.bar_4(pick, context()).ok)

    def test_recent_qb_change_holds_receiving_and_passing_props(self):
        stable = context(passers={'NFL-10': ['5', '5', '5']})
        changed = context(passers={'NFL-10': ['4', '5', '5']})
        self.assertTrue(gates.qb_change_recent(prop_lean(), stable).ok)
        self.assertFalse(gates.qb_change_recent(prop_lean(), changed).ok)
        self.assertTrue(gates.qb_change_recent(prop_lean(market='rushYds'), changed).ok)

    def test_nfl_total_paused_and_cfb_total_weekend_only_without_adverse_move(self):
        self.assertFalse(gates.totals_policy(total_lean(), context()).ok)
        cfb_game = dict(GAME, id='CFB-1', league='CFB', kickoff='2026-09-27T17:00:00Z')
        cfb_pick = total_lean(id='CFB-test', league='CFB', gameIds=['CFB-1'])
        first = dict(ODDS, gameId='CFB-1')
        ctx = context(games={'CFB-1': cfb_game}, odds_history={'CFB-1': [first]})
        self.assertTrue(gates.totals_policy(cfb_pick, ctx).ok)
        self.assertFalse(gates.bar_4(cfb_pick, ctx).ok, 'college totals need five, not four')
        self.assertFalse(gates.totals_policy(dict(cfb_pick, line=45.5), ctx).ok)
        monday = dict(cfb_game, kickoff='2026-09-28T17:00:00Z')
        self.assertFalse(gates.totals_policy(cfb_pick, context(games={'CFB-1': monday}, odds_history={'CFB-1': [first]})).ok)
        prior = dict(cfb_pick, id='CFB-prior', publishedAt='2026-09-26T15:00:00Z')
        self.assertFalse(gates.totals_policy(cfb_pick, context(games={'CFB-1': cfb_game},
                          odds_history={'CFB-1': [first]}, first={'CFB-prior': prior})).ok)


class KindTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(gates.kind_of(total_lean()), 'modelLean')
        self.assertEqual(gates.kind_of(prop_lean()), 'propLean')
        self.assertEqual(gates.kind_of(total_lean(favorite=True, modelLean=False)), 'favorite')
        self.assertEqual(gates.kind_of(total_lean(modelLean=False)), 'researched')
        self.assertEqual(gates.kind_of({'id': 'x', 'legs': [{}], 'parlayType': 'longshot'}), 'longshot')
        self.assertEqual(gates.kind_of(total_lean(status='settled', result='win')), 'revision')
        self.assertEqual(gates.kind_of(total_lean(entryNote='closed')), 'revision')


class ScheduleTests(unittest.TestCase):
    def test_next_slot_follows_the_prompt_table(self):
        sunday_10am = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)
        self.assertEqual(gates.next_slot(sunday_10am).isoformat(), '2026-09-27T15:45:00+00:00')        # 11:45 ET
        sunday_noon = datetime(2026, 9, 27, 16, 0, tzinfo=timezone.utc)
        self.assertEqual(gates.next_slot(sunday_noon).isoformat(), '2026-09-27T18:45:00+00:00')        # 14:45 Sunday only
        tuesday_noon = datetime(2026, 9, 29, 16, 0, tzinfo=timezone.utc)
        self.assertEqual(gates.next_slot(tuesday_noon).isoformat(), '2026-09-29T21:30:00+00:00')       # 17:30, no 14:45
        tuesday_6pm = datetime(2026, 9, 29, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(gates.next_slot(tuesday_6pm).isoformat(), '2026-09-30T01:00:00+00:00')        # 21:00 late-slate check
        monday_6pm = datetime(2026, 9, 28, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(gates.next_slot(monday_6pm).isoformat(), '2026-09-28T22:50:00+00:00')         # 18:50 Monday
        late = datetime(2026, 9, 28, 3, 45, tzinfo=timezone.utc)                                          # 23:45 ET Sunday
        self.assertEqual(gates.next_slot(late).isoformat(), '2026-09-28T10:45:00+00:00')               # 6:45 Monday

    def test_next_slot_across_the_dst_change(self):
        # 2026-11-01 02:00 EDT -> 01:00 EST. 6:45 ET on Nov 1 is 11:45Z.
        self.assertEqual(gates.next_slot(datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)).isoformat(), '2026-11-01T11:45:00+00:00')
        # 2026-03-08 springs forward; 6:45 ET on Mar 8 is 10:45Z.
        self.assertEqual(gates.next_slot(datetime(2026, 3, 8, 6, 0, tzinfo=timezone.utc)).isoformat(), '2026-03-08T10:45:00+00:00')

    def test_windows(self):
        self.assertEqual(gates.window('2026-09-27T17:00Z'), 'early')    # 1 PM ET
        self.assertEqual(gates.window('2026-09-27T20:25Z'), 'late')     # 4:25 PM ET
        self.assertEqual(gates.window('2026-09-28T00:20Z'), 'night')    # 8:20 PM ET


class CommonRuleTests(unittest.TestCase):
    def test_not_started_refuses_a_kicked_off_or_imminent_game(self):
        ctx = context()
        self.assertTrue(gates.not_started(total_lean(), ctx).ok)
        late = context(now=datetime(2026, 9, 27, 16, 57, tzinfo=timezone.utc))
        self.assertFalse(gates.not_started(total_lean(), late).ok)
        self.assertFalse(gates.not_started(total_lean(gameIds=['NFL-9']), ctx).ok)

    def test_expiry_is_the_next_run_or_kickoff(self):
        ctx = context()
        self.assertTrue(gates.expiry_ok(total_lean(expiresAt='2026-09-27T15:45:00Z'), ctx).ok)
        self.assertFalse(gates.expiry_ok(total_lean(expiresAt='2026-09-27T17:00:00Z'), ctx).ok, 'past the 11:45 run')
        night = dict(GAME, kickoff='2026-09-27T15:30Z')      # kickoff before the next run
        ctx = context(games={'NFL-1': night})
        self.assertTrue(gates.expiry_ok(total_lean(expiresAt='2026-09-27T15:30:00Z'), ctx).ok)
        self.assertFalse(gates.expiry_ok(total_lean(expiresAt='2026-09-27T15:45:00Z'), ctx).ok, 'past kickoff')
        self.assertFalse(gates.expiry_ok(total_lean(quotedAt='2026-09-27T15:00:00Z'), context()).ok, 'quoted in the future')

    def test_price_present(self):
        ctx = context()
        self.assertTrue(gates.price_present(total_lean(), ctx).ok)
        self.assertFalse(gates.price_present(total_lean(odds=-50), ctx).ok)
        self.assertFalse(gates.price_present(total_lean(book=None), ctx).ok)
        self.assertFalse(gates.price_present(total_lean(quoteType='guess'), ctx).ok)

    def test_data_sanity(self):
        ctx = context()
        self.assertTrue(gates.data_sanity(total_lean(), ctx).ok)
        self.assertFalse(gates.data_sanity(total_lean(line=210), ctx).ok)
        self.assertFalse(gates.data_sanity(total_lean(marketType='spread', line=-88, direction='home'), ctx).ok)
        record = {'gameId': 'NFL-1', 'retrievedAt': '2026-09-27T13:00:00Z',
                  'books': {'draftkings': {'markets': {'att': {'Quarterback Five': {'line': 30.5, 'over': -110, 'under': -110}},
                                                       'cmp': {'Quarterback Five': {'line': 34.5, 'over': -110, 'under': -110}}}}}}
        ctx = context(prop_odds={'NFL-1': record})
        bad = prop_lean(athleteId='5', market='cmp', line=34.5, direction='under', title='Quarterback Five UNDER 34.5 completions')
        self.assertFalse(gates.data_sanity(bad, ctx).ok, 'completions above attempts is a data error')
        self.assertTrue(gates.data_sanity(dict(bad, line=19.5), ctx).ok)

    def test_sources_https(self):
        self.assertTrue(gates.sources_https(total_lean(), context()).ok)
        self.assertFalse(gates.sources_https(total_lean(sources=[]), context()).ok)
        self.assertFalse(gates.sources_https(total_lean(sources=['http://x']), context()).ok)

    def test_not_duplicate(self):
        existing = total_lean(id='earlier', publishedAt='2026-09-27T11:00:00Z')
        ctx = context(first={'earlier': existing}, latest={'earlier': existing})
        self.assertFalse(gates.not_duplicate(total_lean(), ctx).ok)
        self.assertTrue(gates.not_duplicate(total_lean(direction='under'), ctx).ok)
        closed = dict(existing, status='expired', entryNote='Closed to new entries at 5:30 PM ET: total moved 1.5 against')
        refused = gates.not_duplicate(total_lean(), context(first={'earlier': existing}, latest={'earlier': closed}))
        self.assertFalse(refused.ok, 'a bet the desk closed is not published again at another number')
        self.assertIn('already published', refused.reason)
        elsewhere = dict(existing, gameIds=['NFL-2'])
        self.assertTrue(gates.not_duplicate(total_lean(), context(first={'earlier': elsewhere}, latest={'earlier': elsewhere})).ok,
                        'another game is another bet')
        prop = prop_lean(id='p1', publishedAt='2026-09-27T11:00:00Z')
        ctx = context(first={'p1': prop}, latest={'p1': prop})
        self.assertFalse(gates.not_duplicate(prop_lean(), ctx).ok)
        self.assertTrue(gates.not_duplicate(prop_lean(market='rec', title='Player Seven OVER 4.5 receptions'), ctx).ok)

    def test_cfb_jurisdiction(self):
        ctx = context(games={'CFB-1': dict(GAME, id='CFB-1', league='CFB')})
        pick = total_lean(league='CFB', gameIds=['CFB-1'])
        self.assertTrue(gates.cfb_jurisdiction(pick, ctx).ok)
        self.assertTrue(pick.get('jurisdictionVerified'))
        self.assertFalse(gates.cfb_jurisdiction(total_lean(league='CFB', gameIds=['CFB-1'], book='Bovada'), ctx).ok)
        self.assertTrue(gates.cfb_jurisdiction(prop_lean(league='CFB', gameIds=['CFB-1']), ctx).ok,
                        'pregame college player props are legal in Indiana (the Gaming Commission kept them on 2026-09-24)')

    def test_cfb_jurisdiction_uses_provider_identity_not_the_public_rebrand(self):
        [line] = build_site.public_lines([{'id': 'game-CFB-1-over', 'book': 'theScore Bet', 'line': 52.5,
                                           'odds': -110, 'observedAt': NOW.isoformat()}], NOW)
        self.assertEqual(line['book'], 'ESPN BET')
        self.assertNotIn('displayBook', line, 'the display rename belongs only in the browser')
        ctx = context(games={'CFB-1': dict(GAME, id='CFB-1', league='CFB')})
        pick = total_lean(league='CFB', gameIds=['CFB-1'], book=line['book'])
        self.assertTrue(gates.cfb_jurisdiction(pick, ctx).ok)


class ShoppingRuleTests(unittest.TestCase):
    def test_one_book_refuses_a_lone_book_unless_kickoff_is_inside_three_hours(self):
        lone = dict(PROP_ODDS, books={'draftkings': PROP_ODDS['books']['draftkings']})
        ctx = context(prop_odds={'NFL-1': lone})
        refused = gates.one_book(prop_lean(), ctx)
        self.assertFalse(refused.ok)
        self.assertIn('DraftKings', refused.reason)
        self.assertTrue(gates.one_book(prop_lean(), context()).ok, 'two books quote it')
        close = context(prop_odds={'NFL-1': lone}, now=datetime(2026, 9, 27, 14, 30, tzinfo=timezone.utc))
        passed = gates.one_book(prop_lean(), close)
        self.assertTrue(passed.ok)
        self.assertTrue(passed.data.get('quoteNoteRequired'))

    def test_one_book_reads_game_lines_from_the_odds_capture(self):
        lone = dict(ODDS, books={'draftkings': ODDS['books']['draftkings']})
        self.assertFalse(gates.one_book(total_lean(), context(odds={'NFL-1': lone})).ok)
        self.assertTrue(gates.one_book(total_lean(), context()).ok)

    def test_best_quote_prefers_expected_value_over_the_number(self):
        # Under: BetRivers 53 at -113 shows a better number than ESPN BET 52.5 at -105, but is worth less.
        snapshot = dict(SNAPSHOT, total=48.0)
        odds = {'gameId': 'NFL-1', 'retrievedAt': '2026-09-27T13:00:00Z',
                'books': {'betrivers': {'total': {'line': 53, 'over': -107, 'under': -113}},
                          'espnbet': {'total': {'line': 52.5, 'over': -115, 'under': -105}}}}
        ctx = context(odds={'NFL-1': odds}, snapshots={'NFL-1': [snapshot]})
        worse = total_lean(book='BetRivers', line=53, odds=-113, direction='under')
        decision = gates.best_quote_by_ev(worse, ctx)
        self.assertFalse(decision.ok)
        self.assertEqual(decision.data['best']['book'], 'ESPN BET')
        better = total_lean(book='ESPN BET', line=52.5, odds=-105, direction='under')
        self.assertTrue(gates.best_quote_by_ev(better, ctx).ok)

    def test_best_quote_passes_when_nothing_can_be_compared(self):
        self.assertTrue(gates.best_quote_by_ev(total_lean(), context(snapshots={})).ok)


class ModelLeanRuleTests(unittest.TestCase):
    def test_lean_is_total(self):
        self.assertTrue(gates.lean_is_total(total_lean(), context()).ok)
        self.assertFalse(gates.lean_is_total(total_lean(marketType='spread', direction='home', line=-3), context()).ok)

    def test_lean_edge_and_confidence(self):
        ctx = context()
        over = total_lean()                     # v2 total 48 against 44.5: calibrated chance clears break-even
        edge = gates.lean_edge(over, ctx)
        self.assertTrue(edge.ok, edge.reason)
        self.assertGreaterEqual(edge.data['edgePoints'], gates.LEAN_EDGE)
        self.assertFalse(gates.lean_edge(total_lean(direction='under'), ctx).ok)
        want = 3 if edge.data['edgePoints'] >= 2 else 2
        self.assertTrue(gates.lean_confidence(total_lean(confidence=want), ctx).ok)
        self.assertFalse(gates.lean_confidence(total_lean(confidence=5), ctx).ok)
        self.assertFalse(gates.lean_edge(total_lean(marketType='spread', direction='home', line=-3), context()).ok,
                         'NFL spreads are calibrated to zero information')

    def test_lean_edge_refuses_without_a_snapshot(self):
        self.assertFalse(gates.lean_edge(total_lean(), context(snapshots={})).ok)

    def test_game_performance_caution_raises_the_bar_without_vetoing_a_strong_line(self):
        policy = gates.learning.default_policy()
        policy['segments']['NFL/total'] = {'paused': True}
        ordinary = gates.lean_edge(total_lean(), context(policy=policy))
        self.assertFalse(ordinary.ok)
        self.assertIn('needs +3.0', ordinary.reason)
        strong = gates.lean_edge(total_lean(), context(policy=policy, snapshots={'NFL-1': [dict(SNAPSHOT, total=49.0)]}))
        self.assertTrue(strong.ok, strong.reason)

    def test_lean_daily_cap(self):
        leans = {f'l{i}': total_lean(id=f'l{i}', publishedAt='2026-09-27T12:00:00Z', direction='under') for i in range(4)}
        self.assertFalse(gates.lean_daily_cap(total_lean(), context(first=leans, latest=leans)).ok)
        three = dict(list(leans.items())[:3])
        self.assertTrue(gates.lean_daily_cap(total_lean(), context(first=three, latest=three)).ok)
        yesterday = {k: dict(v, publishedAt='2026-09-26T12:00:00Z') for k, v in leans.items()}
        self.assertTrue(gates.lean_daily_cap(total_lean(), context(first=yesterday, latest=yesterday)).ok)

    def test_lean_nothing_against(self):
        facts = [{'id': 'f1', 'kind': 'injury', 'direction': 'against', 'claim': 'QB1 is out'}]
        self.assertFalse(gates.lean_nothing_against(total_lean(_evidence=facts), context()).ok)
        self.assertTrue(gates.lean_nothing_against(total_lean(_evidence=[dict(facts[0], direction='for')]), context()).ok)

    def test_qb_gate_refuses_a_doubtful_starter_and_can_be_switched_off(self):
        injuries = {'NFL-10': {'5': {'status': 'Doubtful', 'position': 'QB', 'name': 'Quarterback Five'}}}
        ctx = context(injuries=injuries)
        refused = gates.qb_available(total_lean(), ctx)
        self.assertFalse(refused.ok)
        self.assertIn('Quarterback Five', refused.reason)
        fine = context(injuries={'NFL-10': {'5': {'status': 'Questionable', 'position': 'QB'}}})
        self.assertTrue(gates.qb_available(total_lean(), fine).ok, 'questionable is not doubtful')
        off = context(injuries=injuries, flags={'QB_GATE': False})
        self.assertTrue(gates.qb_available(total_lean(), off).ok)
        self.assertTrue(gates.qb_available(total_lean(), context()).ok, 'no report, nothing to refuse on')
        self.assertFalse(gates.qb_available(total_lean(), context()).data['checked'])


class BestNowTests(unittest.TestCase):
    def test_the_best_number_for_the_side_then_the_best_price(self):
        ctx = context()
        over = gates.best_now(total_lean(), ctx)
        under = gates.best_now(total_lean(direction='under'), ctx)
        self.assertIsNotNone(over)
        lines = [q[1] for q in gates.quotes_for(dict(total_lean(), _quotes=None), ctx, priced_only=True)]
        self.assertEqual(over[1], min(lines), 'an over wants the lowest number')
        self.assertEqual(under[1], max(lines), 'an under wants the highest')
        stale = context(now=NOW + timedelta(hours=13))
        self.assertIsNone(gates.best_now(total_lean(), stale), 'a capture half a day old says nothing about now')


class PropLeanRuleTests(unittest.TestCase):
    def test_prop_raw_edge(self):
        ctx = context()
        # Projection 60 against 49.5 at -115: raw chance well over 60% and clear of the price.
        self.assertTrue(gates.prop_raw_edge(prop_lean(), ctx).ok)
        self.assertFalse(gates.prop_raw_edge(prop_lean(direction='under', odds=-105), ctx).ok)
        self.assertFalse(gates.prop_raw_edge(prop_lean(athleteId='99', title='Nobody OVER 49.5 receiving yards'), ctx).ok)

    def test_prop_settled_role(self):
        self.assertTrue(gates.prop_settled_role(prop_lean(), context()).ok)
        thin = context(appearances=defaultdict(int, {'77': 2}))
        self.assertFalse(gates.prop_settled_role(prop_lean(), thin).ok)
        last_year = context(appearances=defaultdict(int, {'77': 1}), established={('77', '10')})
        self.assertTrue(gates.prop_settled_role(prop_lean(), last_year).ok)

    def test_prop_price_floor(self):
        self.assertTrue(gates.prop_price_floor(prop_lean(odds=-200), context()).ok)
        self.assertFalse(gates.prop_price_floor(prop_lean(odds=-205), context()).ok)

    def test_prop_window_cap_counts_the_kickoff_window(self):
        picks = {f'p{i}': prop_lean(id=f'p{i}', athleteId=str(80 + i), publishedAt='2026-09-27T12:00:00Z') for i in range(3)}
        self.assertFalse(gates.prop_window_cap(prop_lean(), context(first=picks, latest=picks)).ok)
        night = dict(GAME, id='NFL-2', kickoff='2026-09-28T00:20Z')
        ctx = context(first=picks, latest=picks, games={'NFL-1': GAME, 'NFL-2': night})
        self.assertTrue(gates.prop_window_cap(prop_lean(gameIds=['NFL-2']), ctx).ok, 'a different window')

    def test_prop_one_per_player_and_not_in_longshot(self):
        earlier = prop_lean(id='p0', market='rec', publishedAt='2026-09-27T12:00:00Z')
        self.assertFalse(gates.prop_one_per_player(prop_lean(), context(first={'p0': earlier}, latest={'p0': earlier})).ok)
        self.assertTrue(gates.prop_one_per_player(prop_lean(), context()).ok)
        ticket = {'id': 'ls', 'parlayType': 'longshot', 'publishedAt': '2026-09-27T12:00:00Z',
                  'legs': [{'id': 'prop-NFL-1-77-recYds', 'title': 'Player Seven over 49.5 receiving yards'}]}
        self.assertFalse(gates.prop_not_in_longshot(prop_lean(), context(first={'ls': ticket}, latest={'ls': ticket})).ok)
        self.assertTrue(gates.prop_not_in_longshot(prop_lean(athleteId='78'), context(first={'ls': ticket}, latest={'ls': ticket})).ok)

    def test_prop_injury_clear(self):
        listed = context(injuries={'NFL-10': {'77': {'status': 'Questionable', 'position': 'WR'}}})
        self.assertFalse(gates.prop_injury_clear(prop_lean(), listed).ok)
        active = context(injuries={'NFL-10': {'77': {'status': 'Active', 'position': 'WR'}}})
        self.assertTrue(gates.prop_injury_clear(prop_lean(), active).ok)
        self.assertTrue(gates.prop_injury_clear(prop_lean(), context()).ok)

    def test_market_gate_reads_the_live_scoreboard_and_can_be_switched_off(self):
        ctx = context()
        caution = gates.prop_market_not_trailing(prop_lean(), ctx)
        self.assertTrue(caution.ok, 'poor performance raises the bar rather than vetoing the market')
        self.assertIn('performance caution', caution.reason)
        self.assertTrue(caution.data['performanceCaution'])
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(market='rec', title='Player Seven OVER 4.5 receptions'), ctx).ok)
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(market='att', title='Quarterback Five OVER 30.5 pass attempts'), ctx).ok,
                        'too few graded to close a market')
        off = context(flags={'MARKET_GATE': False})
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(), off).ok)
        reopened = context(scoreboard={'props': {'markets': [{'market': 'recYds', 'graded': 200, 'closerThanLine': [110, 90]}]}})
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(), reopened).ok, 'reopens when the projection improves')


    def test_college_props_wait_for_their_own_calibration_and_skip_the_nfl_scoreboard(self):
        college = prop_lean(league='CFB', id='CFB-2026-W5-seven-over-49-5-recyds-dk')
        waiting = gates.prop_calibrated_value(college, context())
        self.assertFalse(waiting.ok)
        self.assertIn('own calibration', waiting.reason)
        self.assertFalse(gates.prop_calibrated_value(prop_lean(), context()).ok, 'every league needs learned calibration')
        import learning
        calibrated = context(policy=dict(learning.default_policy(), calibration={'CFB/prop': {'k': 0.5, 'n': 320}}))
        self.assertNotIn('own calibration', gates.prop_calibrated_value(college, calibrated).reason)
        skipped = gates.prop_market_not_trailing(college, context())
        self.assertTrue(skipped.ok, "the scoreboard's closer-than-line rows are the NFL's")
        self.assertIn('CFB', skipped.reason)


class FavoriteLongshotRevisionTests(unittest.TestCase):
    def test_favorite_needs_a_verified_reason(self):
        pick = total_lean(favorite=True, modelLean=False)
        self.assertFalse(gates.favorite_needs_reason(pick, context()).ok)
        fact = {'id': 'f', 'kind': 'injury', 'direction': 'for', 'claim': 'two starting corners out',
                'source': 'https://www.espn.com/nfl/injuries', 'retrievedAt': '2026-09-27T12:30:00Z', 'verified': True}
        self.assertTrue(gates.favorite_needs_reason(dict(pick, _evidence=[fact]), context()).ok)
        self.assertFalse(gates.favorite_needs_reason(dict(pick, _evidence=[dict(fact, verified=False)]), context()).ok)
        self.assertFalse(gates.favorite_needs_reason(dict(pick, _evidence=[dict(fact, source='http://x')]), context()).ok)
        self.assertTrue(gates.favorite_needs_reason(total_lean(), context()).ok, 'not a favorite')

    def test_longshot_one_per_day(self):
        ticket = {'id': 'ls', 'parlayType': 'longshot', 'publishedAt': '2026-09-27T12:00:00Z', 'legs': [{}, {}, {}]}
        new = {'id': 'ls2', 'parlayType': 'longshot', 'legs': [{}, {}, {}], 'gameIds': ['NFL-1']}
        self.assertFalse(gates.longshot_one_per_day(new, context(first={'ls': ticket}, latest={'ls': ticket})).ok)
        self.assertTrue(gates.longshot_one_per_day(new, context()).ok)

    def test_a_published_ticket_is_never_written_again(self):
        """The 6:45 and 8:30 runs both wrote the Sep 25 longshot: its id is fixed by the date and the book."""
        ticket = {'id': 'CFB-2026-W4-longshot-0925-espnbet', 'parlayType': 'longshot', 'legs': [{}, {}, {}],
                  'publishedAt': '2026-09-27T10:45:05Z'}
        ctx = context(first={ticket['id']: ticket}, latest={ticket['id']: ticket})
        again = {k: v for k, v in ticket.items() if k != 'publishedAt'}
        refused = gates.not_republished(again, ctx)
        self.assertFalse(refused.ok)
        self.assertIn('already published', refused.reason)
        self.assertIn('not_republished', [r.__name__ for r in gates.RULES['longshot']])
        self.assertTrue(gates.not_republished(ticket, ctx).ok, 'a replay of the publication itself is not a second write')
        self.assertTrue(gates.not_republished(dict(again, id='another'), ctx).ok)
        earlier = context(first={ticket['id']: ticket}, now=datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc))
        self.assertTrue(gates.not_republished(again, earlier).ok, 'published later than this moment')
        single = total_lean(publishedAt='2026-09-27T12:00:00Z')
        self.assertFalse(gates.not_republished(total_lean(), context(first={single['id']: single})).ok, 'a single play too')

    def test_revision_frozen(self):
        original = total_lean(publishedAt='2026-09-27T12:00:00Z')
        ctx = context(first={original['id']: original}, latest={original['id']: original})
        settled = dict(original, status='settled', result='win', actual='Bills 27, Lions 24', actualValue=51)
        self.assertTrue(gates.revision_frozen(settled, ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, line=45.5), ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, odds=-105), ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, favorite=True), ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, id='never-published'), ctx).ok)


class CardTests(unittest.TestCase):
    def test_evening_slate_keeps_one_place_without_increasing_card(self):
        picks={k: total_lean(id=k,gameIds=[gid],publishedAt='2026-09-26T12:00:00Z') for k,gid in [('a','NFL-2'),('b','NFL-3')]}
        picks.update({k:prop_lean(id=k,athleteId=k,market='rushYds',gameIds=[gid],publishedAt='2026-09-26T12:00:00Z') for k,gid in [('c','NFL-4'),('d','NFL-5')]})
        games={**self.GAMES,'late':dict(GAME,id='late',kickoff='2026-09-28T02:30:00Z')}
        ctx=context(games=games,first=picks,latest=picks)
        self.assertIn('4 PM',gates.card_cap(total_lean(),ctx).reason)
        ctx.now=datetime(2026,9,27,20,0,tzinfo=timezone.utc)
        self.assertTrue(gates.card_cap(total_lean(),ctx).ok)
    GAMES = {gid: dict(GAME, id=gid) for gid in ('NFL-1', 'NFL-2', 'NFL-3', 'NFL-4', 'NFL-5', 'NFL-6')}          # Sunday
    GAMES['MNF'] = dict(GAME, id='MNF', kickoff='2026-09-29T00:15Z')                                              # Monday night
    GAMES['CFB-M'] = dict(GAME, id='CFB-M', league='CFB', kickoff='2026-09-28T23:00Z')                          # Monday, college

    def card(self, picks):
        return context(games=self.GAMES, first=picks, latest=picks)

    def test_third_same_prop_market_requires_stronger_value(self):
        from unittest.mock import patch
        picks = {k: prop_lean(id=k, athleteId=k, market='rec', gameIds=[gid], publishedAt='2026-09-26T12:00:00Z')
                 for k, gid in (('a', 'NFL-2'), ('b', 'NFL-3'))}
        with patch.object(gates, 'desk_for', return_value={'calibrated': True, 'edgePoints': 2.1}):
            self.assertFalse(gates.card_cap(prop_lean(market='rec'), self.card(picks)).ok)
            self.assertTrue(gates.card_cap(prop_lean(market='rushYds'), self.card(picks)).ok)
        with patch.object(gates, 'desk_for', return_value={'calibrated': True, 'edgePoints': 5.1}):
            self.assertTrue(gates.card_cap(prop_lean(market='rec'), self.card(picks)).ok)

    def test_a_weekend_card_is_five_plays_with_three_of_a_kind_at_most(self):
        team = lambda key, gid: total_lean(id=key, gameIds=[gid], publishedAt='2026-09-25T12:00:00Z')
        prop = lambda key, gid: prop_lean(id=key, gameIds=[gid], athleteId=key, publishedAt='2026-09-26T12:00:00Z')
        three = {k: team(k, g) for k, g in (('a', 'NFL-2'), ('b', 'NFL-3'), ('c', 'NFL-4'))}
        refused = gates.card_cap(total_lean(), self.card(three))
        self.assertFalse(refused.ok, 'three game lines already on Sunday, published days before')
        self.assertIn('3 of a kind at most', refused.reason)
        self.assertTrue(gates.card_cap(prop_lean(), self.card(three)).ok, 'a player prop still fits: the mix')
        five = dict(three, d=prop('d', 'NFL-5'), e=prop('e', 'NFL-6'))
        self.assertIn('the card is 5', gates.card_cap(prop_lean(), self.card(five)).reason)
        pulled = dict(five, e=dict(five['e']))
        latest = dict(pulled, e=dict(five['e'], status='expired', entryNote='Closed to new entries at 10:05 AM ET, before its post went out: x'))
        self.assertTrue(gates.card_cap(prop_lean(), context(games=self.GAMES, first=pulled, latest=latest)).ok,
                        'a play pulled before its post never reached anyone; the card takes another')
        fun = {'t': {'id': 't', 'legs': [{}, {}], 'parlayType': 'longshot', 'gameIds': ['NFL-4'], 'publishedAt': '2026-09-26T12:00:00Z'}}
        self.assertTrue(gates.card_cap(prop_lean(), self.card(fun)).ok, 'fun parlays are not on the card')

    def test_a_weeknight_card_is_one_play_and_on_an_nfl_night_the_nfl_games(self):
        monday = total_lean(gameIds=['MNF'])
        self.assertTrue(gates.card_cap(monday, self.card({})).ok)
        college = total_lean(id='cfb', gameIds=['CFB-M'], league='CFB')
        self.assertIn("the NFL game's", gates.card_cap(college, self.card({})).reason)
        one = {'m': total_lean(id='m', gameIds=['MNF'], publishedAt='2026-09-26T12:00:00Z')}
        self.assertIn('the card is 1', gates.card_cap(prop_lean(gameIds=['MNF']), self.card(one)).reason)

    def test_a_pulled_fun_ticket_is_replaced_under_a_new_id(self):
        base = 'NFL-2026-W3-ladder-0927-fd'
        picks = {base: {'id': base, 'parlayType': 'ladder', 'publishedAt': '2026-09-27T10:45:06Z'}}
        latest = {base: dict(picks[base], status='expired', entryNote='Closed to new entries at 8:46 AM ET, before its post went out: x')}
        ctx = context(first=picks, latest=latest)
        self.assertTrue(gates.pulled_before_post(base, ctx))
        self.assertEqual(gates.fresh_id(base, ctx), base + '-2')
        self.assertEqual(gates.fresh_id('other', ctx), 'other')


class AdmitTests(unittest.TestCase):
    def test_a_clean_model_lean_is_admitted(self):
        ok, decisions = gates.admit(total_lean(confidence=3), favorite_context())     # DraftKings 44.5 at -110 is the best value on the board
        self.assertFalse(ok, 'NFL totals stay on the research board, not the official card')
        self.assertIn('totals_policy', {d.rule for d in gates.refusals(decisions)})
        self.assertEqual({d.rule for d in decisions},
                         {r.__name__ for r in gates.RULES['modelLean']} - {'bar_4', 'qb_change_recent'}
                         | {'bar-4', 'qb-change-recent'})

    def test_a_clean_prop_lean_is_admitted_when_the_market_gate_allows(self):
        ctx = context(scoreboard={'props': {'markets': []}}, policy={**gates.learning.default_policy(), 'calibration': {'NFL/prop': {'k': 0.9, 'n': 500}}})
        ok, decisions = gates.admit(prop_lean(), ctx)
        self.assertTrue(ok, [str(d) for d in decisions if not d.ok])

    def test_evaluate_runs_every_rule_and_names_every_refusal(self):
        lone = dict(PROP_ODDS, books={'draftkings': PROP_ODDS['books']['draftkings']})
        ctx = context(prop_odds={'NFL-1': lone})
        ok, decisions = gates.admit(prop_lean(odds=-250), ctx)
        self.assertFalse(ok)
        # One book, a price past the floor, a market the scoreboard has closed, an edge that -250 eats,
        # and a better quote (-115) sitting in the capture: every one of them is named.
        self.assertEqual({d.rule for d in gates.refusals(decisions)},
                         {'one_book', 'two_sided_straight', 'prop_price_floor', 'prop_raw_edge', 'best_quote_by_ev',
                          'prop_calibrated_value', 'bar-4'})

    def test_underperforming_segment_raises_the_bar_but_does_not_veto_a_strong_price(self):
        ctx = context(policy={**gates.learning.default_policy(), 'calibration': {'NFL/prop': {'k': 0.13, 'n': 500}},
                              'segments': {'NFL/prop:recYds': {'paused': True}}})
        for kind in ('propLean', 'favorite', 'researched'):
            ok, decisions = gates.admit(prop_lean(), ctx, kind)
            self.assertFalse(ok)
            self.assertNotIn('learned_pause', {d.rule for d in gates.refusals(decisions)})
            self.assertIn('prop_calibrated_value', {d.rule for d in gates.refusals(decisions)})
        strong = gates.learning.default_policy()
        strong['calibration']['NFL/prop'] = {'k': 1.0, 'n': 500}
        strong['segments']['NFL/prop:recYds'] = {'paused': True}
        verdict = gates.prop_calibrated_value(prop_lean(), context(policy=strong))
        self.assertTrue(verdict.ok)
        self.assertIn('raised the bar', verdict.reason)

    def test_expiry_does_not_refresh_a_stale_quote(self):
        self.assertFalse(gates.fresh_quote(total_lean(quotedAt='2026-09-26T13:00:00Z'), context()).ok)
        self.assertTrue(gates.fresh_quote(total_lean(), context()).ok)


class ReplayTests(unittest.TestCase):
    """Runs against the real research/ folder, read only."""

    @classmethod
    def setUpClass(cls):
        import replay_gates
        cls.replay = replay_gates
        cls.stores = gates.Stores()

    def test_replay_refuses_the_monday_props_on_the_one_book_rule(self):
        ids = {'NFL-2026-W2-ferguson-under-32-5-recyds-dk', 'NFL-2026-W2-theo-johnson-over-8-5-recyds-dk',
               'NFL-2026-W2-singletary-over-15-5-rush-dk'}
        rows = self.replay.replay(self.stores, only=ids)
        self.assertEqual({r[0] for r in rows}, ids)
        for key, kind, _, failures in rows:
            self.assertEqual(kind, 'propLean', key)
            self.assertIn('one_book', {d.rule for d in failures}, key)

    def test_the_two_x_posted_favorites_replay_as_favorites(self):
        ids = {'CFB-2026-W3-tamu-minus-16-5-vs-uk-dk', 'CFB-2026-W3-duke-minus-10-vs-stan-dk'}
        rows = self.replay.replay(self.stores, only=ids)
        self.assertEqual({r[1] for r in rows}, {'favorite'})


if __name__ == '__main__':
    unittest.main()
