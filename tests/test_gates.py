import sys
import unittest
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
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


def context(**over):
    fields = dict(now=NOW, games={'NFL-1': GAME}, odds={'NFL-1': ODDS}, prop_odds={'NFL-1': PROP_ODDS},
                  snapshots={'NFL-1': [SNAPSHOT]}, names={'77': 'Player Seven', '5': 'Quarterback Five'},
                  appearances=defaultdict(int, {'77': 3}), player_team={'77': '10', '5': '10'}, starters={'NFL-10': '5'},
                  scoreboard={'props': {'markets': [{'market': 'recYds', 'graded': 158, 'closerThanLine': [66, 92]},
                                                    {'market': 'rec', 'graded': 158, 'closerThanLine': [80, 78]},
                                                    {'market': 'att', 'graded': 12, 'closerThanLine': [4, 8]}]}})
    fields.update(over)
    return Context(**fields)


def decision(rule, candidate, ctx):
    return rule(candidate, ctx)


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
        self.assertEqual(gates.next_slot(tuesday_6pm).isoformat(), '2026-09-30T03:30:00+00:00')        # 23:30, no 18:50 Tue
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
        settled = dict(existing, status='settled', result='win')
        self.assertTrue(gates.not_duplicate(total_lean(), context(first={'earlier': existing}, latest={'earlier': settled})).ok)
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
        self.assertFalse(gates.cfb_jurisdiction(prop_lean(league='CFB', gameIds=['CFB-1']), ctx).ok, 'no college props in Indiana')


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
        self.assertGreaterEqual(edge.data['edgePoints'], 1.0)
        self.assertFalse(gates.lean_edge(total_lean(direction='under'), ctx).ok)
        want = 3 if edge.data['edgePoints'] >= 2 else 2
        self.assertTrue(gates.lean_confidence(total_lean(confidence=want), ctx).ok)
        self.assertFalse(gates.lean_confidence(total_lean(confidence=5), ctx).ok)
        self.assertFalse(gates.lean_edge(total_lean(marketType='spread', direction='home', line=-3), context()).ok,
                         'NFL spreads are calibrated to zero information')

    def test_lean_edge_refuses_without_a_snapshot(self):
        self.assertFalse(gates.lean_edge(total_lean(), context(snapshots={})).ok)

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
        refused = gates.prop_market_not_trailing(prop_lean(), ctx)
        self.assertFalse(refused.ok, 'receiving yards: the line was closer in 92 of 158')
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(market='rec', title='Player Seven OVER 4.5 receptions'), ctx).ok)
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(market='att', title='Quarterback Five OVER 30.5 pass attempts'), ctx).ok,
                        'too few graded to close a market')
        off = context(flags={'MARKET_GATE': False})
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(), off).ok)
        reopened = context(scoreboard={'props': {'markets': [{'market': 'recYds', 'graded': 200, 'closerThanLine': [110, 90]}]}})
        self.assertTrue(gates.prop_market_not_trailing(prop_lean(), reopened).ok, 'reopens when the projection improves')


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

    def test_revision_frozen(self):
        original = total_lean(publishedAt='2026-09-27T12:00:00Z')
        ctx = context(first={original['id']: original}, latest={original['id']: original})
        settled = dict(original, status='settled', result='win', actual='Bills 27, Lions 24', actualValue=51)
        self.assertTrue(gates.revision_frozen(settled, ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, line=45.5), ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, odds=-105), ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, favorite=True), ctx).ok)
        self.assertFalse(gates.revision_frozen(dict(settled, id='never-published'), ctx).ok)


class AdmitTests(unittest.TestCase):
    def test_a_clean_model_lean_is_admitted(self):
        ok, decisions = gates.admit(total_lean(), context())     # DraftKings 44.5 at -110 is the best value on the board
        self.assertTrue(ok, [str(d) for d in decisions if not d.ok])
        self.assertEqual({d.rule for d in decisions}, {r.__name__ for r in gates.RULES['modelLean']})

    def test_a_clean_prop_lean_is_admitted_when_the_market_gate_allows(self):
        ctx = context(scoreboard={'props': {'markets': []}})
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
                         {'one_book', 'prop_price_floor', 'prop_market_not_trailing', 'prop_raw_edge', 'best_quote_by_ev'})


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
