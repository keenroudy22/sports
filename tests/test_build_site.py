import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
from fakegames import game

ROOT = Path(__file__).resolve().parents[1]


def slate_game(game_id, kickoff, state='pre', **market):
    return {'id': game_id, 'league': 'NFL', 'kickoff': kickoff, 'state': state, 'marketRetrievedAt': '2026-09-18T12:00:00Z',
            'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'},
            'market': {'provider': 'Draft Kings', 'spread': '-3.5', 'spreadOdds': '-112', 'spreadOpen': '-2.5',
                       'total': 44.5, 'totalOpen': 'o45.5', 'overOdds': '-108', 'underOdds': '-112', **market}}


class ModelReadTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, 15, tzinfo=timezone.utc)
        self.game = dict(slate_game('NFL-test', '2026-10-05T00:20:00Z'), season=2026)
        self.snapshot = {'publishedAt': '2026-10-04T14:00:00Z'}
        self.row = {'id': 'p', 'gameId': 'NFL-test', 'state': 'open', 'athleteId': '1',
                    'title': 'Player over 25.5 receiving yards', 'stat': 'recYds', 'market': 'receiving yards',
                    'direction': 'over', 'line': 25.5, 'odds': -110, 'book': 'FanDuel',
                    'observedAt': '2026-10-04T14:00:00Z',
                    'grade': {'projection': 35.0, 'performanceCaution': True, 'performanceNeed': 5.0,
                              'calibrated': True, 'view': 'pass'}}

    def test_performance_caution_is_visible_but_not_a_favorite_below_the_higher_bar(self):
        reads = build_site.model_reads(self.game, self.snapshot, [self.row], self.now)
        self.assertEqual(len(reads), 1)
        self.assertIn('at least 5 adjusted points', reads[0]['warnings'][0])
        self.assertIn('9.5 receiving yards above', reads[0]['comparison'])
        self.assertNotIn('chance', reads[0])
        self.assertEqual(build_site.favorite_lines(self.game, self.snapshot, [self.row], self.now), [])

    def test_never_flip_a_quote_to_the_other_side(self):
        self.row['direction'] = 'under'
        self.assertEqual(build_site.model_reads(self.game, self.snapshot, [self.row], self.now), [])

    def test_stale_price_hidden_and_limited_role_omitted(self):
        self.row['observedAt'] = '2026-10-03T14:00:00Z'
        read = build_site.model_reads(self.game, self.snapshot, [self.row], self.now)[0]
        self.assertIsNone(read['odds'])
        self.assertTrue(any('Older' in w for w in read['warnings']))
        self.row['grade']['limited'] = True
        self.assertEqual(build_site.model_reads(self.game, self.snapshot, [self.row], self.now), [])

    def test_spread_sign_for_both_sides(self):
        row = dict(self.row, gameMarket=True, market='point spread', side='home', line=3.5,
                   grade={'projection': -1.4})
        self.assertIn('2.1 points', build_site.model_reads(self.game, self.snapshot, [row], self.now)[0]['comparison'])
        row.update(side='away', line=-3.5)
        self.assertEqual(build_site.model_reads(self.game, self.snapshot, [row], self.now), [])

    def test_no_current_recommendation_after_kickoff_or_without_snapshot(self):
        self.game['state'] = 'in'
        self.assertEqual(build_site.model_reads(self.game, self.snapshot, [self.row], self.now), [])
        self.assertEqual(build_site.model_reads(self.game, None, [self.row], self.now), [])

    def test_archive_uses_only_pregame_lines_and_forecasts(self):
        self.game['state'] = 'in'
        snapshot = dict(self.snapshot, players={'home': {'players': [
            {'id': '1', 'recYds': [35, 10, 60]}]}, 'away': {'players': []}})
        captures = [{'retrievedAt': '2026-10-04T14:00:00Z', 'lines': {'1': {'recYds': [25.5, 24.5]}}},
                    {'retrievedAt': '2026-10-05T01:00:00Z', 'lines': {'1': {'recYds': [40.5, 25.5]}}}]
        reads = build_site.archived_model_reads(self.game, snapshot, captures, {'1': 'Player'}, self.now)
        self.assertEqual(reads[0]['line'], 25.5)
        self.assertTrue(reads[0]['archived'])
        self.assertIsNone(reads[0]['odds'])
        self.assertIn('not a live line', reads[0]['warnings'][0])
        snapshot['publishedAt'] = '2026-10-05T01:00:00Z'
        self.assertEqual(build_site.archived_model_reads(self.game, snapshot, captures, {}, self.now), [])


class PickTests(unittest.TestCase):
    def test_delivery_payload_is_whitelisted_and_cancellation_is_not_delivery(self):
        row = build_site.public_delivery({'dueAt': '2026-10-02T16:00:00Z', 'cancelledAt': '2026-10-02T15:00:00Z',
            'token': 'secret', 'discord': {'state': 'pending', 'sentAt': None, 'text': 'private'}})
        self.assertIsNone(row['xDue'])
        self.assertTrue(row['cancelled'])
        self.assertIsNone(row['discordAt'])
        self.assertIsNone(row['restoredAt'])
        self.assertNotIn('secret', str(row))
        self.assertNotIn('private', str(row))

    def test_a_restored_delivery_is_open_on_the_site_without_erasing_the_audit_note(self):
        import tempfile
        from unittest import mock
        pick = {'id': 'step', 'title': 'Ladder step 3', 'gameIds': ['CFB-1'], 'status': 'active',
                'parlayType': 'ladder', 'legs': [{'title': 'A'}, {'title': 'B'}], 'publishedAt': '2026-10-03T13:00:00Z'}
        latest = {'step': dict(pick, status='expired', entryNote='Closed before its post went out: false alarm')}
        game = {'id': 'CFB-1', 'league': 'CFB', 'kickoff': '2026-10-03T20:00:00Z'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'data' / 'x-posted.json').write_text(json.dumps({'posts': [{
                'id': 'step', 'restoredAt': '2026-10-03T19:00:00Z', 'sentAt': '2026-10-03T19:05:00Z'}]}))
            with mock.patch.object(build_site, 'ROOT', root):
                [row] = build_site.board_picks({'step': pick}, latest, {'CFB-1': game}, {})
        self.assertEqual(row['status'], 'active')
        self.assertIsNone(row['entryNote'])
        self.assertEqual(row['delivery']['restoredAt'], '2026-10-03T19:00:00Z')

    def test_the_site_uses_the_same_safe_public_title_as_posts_and_cards(self):
        game = {'id': 'CFB-1', 'league': 'CFB', 'kickoff': '2026-09-26T22:30:00Z',
                'away': {'id': '2117', 'short': 'C Michigan', 'abbreviation': 'CMU', 'school': 'Central Michigan'},
                'home': {'id': '2390', 'short': 'Miami', 'abbreviation': 'MIA', 'school': 'Miami'}}
        pick = {'id': 'x', 'title': 'Central Michigan at Miami (FL) (FL) under 53.5', 'marketType': 'total',
                'gameIds': ['CFB-1'], 'historicalImport': True}
        [row] = build_site.board_picks({'x': pick}, {}, {'CFB-1': game}, {})
        self.assertEqual(row['displayTitle'], 'Central Michigan at Miami (FL) under 53.5')
        self.assertEqual(row['title'], pick['title'], 'the append-only published title remains untouched')

    def test_board_rows_keep_the_first_published_price(self):
        reports = [{'league': 'NFL', 'publishedAt': '2026-09-01T12:00:00Z',
                    'props': [{'id': 'a', 'odds': -110, 'line': 60.5, 'gameIds': ['NFL-1']}]},
                   {'league': 'NFL', 'publishedAt': '2026-09-02T12:00:00Z',
                    'props': [{'id': 'a', 'odds': 120, 'line': 58.5, 'result': 'win', 'actual': 71}]}]
        first, latest = build_site.first_publications(reports)
        rows = build_site.board_picks(first, latest, {'NFL-1': {'kickoff': '2026-09-03T17:00:00Z'}}, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['odds'], rows[0]['line'], rows[0]['result'], rows[0]['actual']), (-110, 60.5, 'win', 71))
        self.assertEqual(rows[0]['publishedAt'], '2026-09-01T12:00:00Z')
        self.assertEqual(rows[0]['kickoff'], '2026-09-03T17:00:00Z')

    def test_board_rows_publish_frozen_display_fields_and_structured_copy(self):
        pick = {'id': 'x', 'league': 'NFL', 'title': 'Bills at Lions over 44.5', 'direction': 'over',
                'gameIds': ['NFL-1'], 'book': 'ESPN BET', 'odds': -110,
                'quotedAt': '2026-09-01T11:45:00Z', 'publishedAt': '2026-09-01T12:00:00Z',
                'probabilityAtPublication': {'chance': .55, 'calibrated': True},
                'why': 'Weather: calm indoors. Projection supports the over.', 'risk': 'A slow pace can hurt.'}
        [row] = build_site.board_picks({'x': pick}, {}, {'NFL-1': {'kickoff': '2026-09-03T17:00:00Z'}}, {})
        self.assertEqual(row['book'], 'ESPN BET')
        self.assertEqual(row['displayBook'], 'theScore Bet')
        self.assertEqual(row['marketType'], 'total')
        self.assertEqual(row['quoteAgeMinutes'], 15)
        self.assertEqual(row['fairOddsAtPublication'], -122)
        self.assertEqual(row['reasons'], ['Weather: calm indoors.', 'Projection supports the over.'])
        self.assertEqual(row['cautions'], ['A slow pace can hurt.'])
        self.assertEqual(row['recordAsOfPublication'], {'wins': 0, 'losses': 0, 'pushes': 0, 'voids': 0})

    def test_card_record_includes_priced_week_one_imports_like_the_site_headline(self):
        old = {'id': 'NFL-2026-W1-import', 'league': 'NFL', 'title': 'Old line', 'gameIds': [],
               'historicalImport': True, 'priceAssumed': True, 'odds': -115, 'result': 'win',
               'season': 2026, 'seasonType': 2, 'publishedAt': '2026-09-26T12:00:00Z'}
        new = {'id': 'NFL-2026-W4-new', 'league': 'NFL', 'title': 'Bills at Lions over 44.5',
               'gameIds': ['NFL-1'], 'odds': -110, 'season': 2026, 'seasonType': 2,
               'publishedAt': '2026-09-28T12:00:00Z'}
        rows = {row['id']: row for row in build_site.board_picks(
            {old['id']: old, new['id']: new}, {old['id']: {'result': 'win'}}, {'NFL-1': {'kickoff': '2026-09-29T00:00:00Z',
                                                              'league': 'NFL', 'season': 2026, 'seasonType': 2}}, {})}
        self.assertEqual(rows[new['id']]['recordAsOfPublication'],
                         {'wins': 1, 'losses': 0, 'pushes': 0, 'voids': 0})

    def test_board_rows_keep_season_stage_and_week_for_the_record_archive(self):
        pick = {'id': 'NFL-2026-W19-playoff', 'league': 'NFL', 'gameIds': ['NFL-1'],
                'publishedAt': '2027-01-10T12:00:00Z'}
        game = {'id': 'NFL-1', 'league': 'NFL', 'season': 2026, 'seasonType': 3, 'week': 1,
                'kickoff': '2027-01-10T18:00:00Z'}
        [row] = build_site.board_picks({'x': pick}, {}, {'NFL-1': game}, {})
        self.assertEqual((row['season'], row['seasonType'], row['week']), (2026, 3, 1))
        self.assertEqual(row['gameIds'], ['NFL-1'])
        manual = dict(pick, id='CFB-2025-W1-manual', gameIds=[])
        [row] = build_site.board_picks({'CFB-2025-W1-manual': manual}, {}, {}, {})
        self.assertEqual(row['season'], 2025, 'dated public ids keep manual historical imports in their season')

    def test_favorite_status_is_fixed_at_first_publication(self):
        reports = [{'league': 'NFL', 'publishedAt': '2026-09-01T12:00:00Z',
                    'props': [{'id': 'a', 'favorite': True}, {'id': 'b'}, {'id': 'w1-otton-rec'}]},
                   {'league': 'NFL', 'publishedAt': '2026-09-02T12:00:00Z',
                    'props': [{'id': 'a', 'favorite': False}, {'id': 'b', 'favorite': True}]}]
        rows = {r['id']: r for r in build_site.board_picks(*build_site.first_publications(reports), {}, {})}
        self.assertEqual({k: r['favorite'] for k, r in rows.items()}, {'a': True, 'b': False, 'w1-otton-rec': True})

    def test_the_published_record_keeps_week_one_favorites_and_the_flag(self):
        reports = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'research').glob('*.json'))]
        rows = build_site.board_picks(*build_site.first_publications(reports), {}, {})
        favorites = {r['id'] for r in rows if r['favorite']}
        self.assertTrue(build_site.FAVORITES_BEFORE_FLAG <= favorites, 'the five Week 1 favorites predate the flag')
        self.assertIn('NFL-2026-W2-gibbs-over-29-5-recyd-dk', favorites)
        self.assertNotIn('NFL-2026-W2-det-buf-volume-fun-sgp-dk', favorites, 'favorite: false stays false')


class GameLineTests(unittest.TestCase):
    now = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)

    def test_each_row_carries_the_price_quoted_for_that_side(self):
        rows = {r['id']: r for r in build_site.game_market_lines({'games': [slate_game('NFL-1', '2026-09-20T17:00:00Z')]},
                                                                  self.now)}
        self.assertEqual(sorted(rows), ['game-NFL-1-over', 'game-NFL-1-spread', 'game-NFL-1-under'])
        self.assertEqual((rows['game-NFL-1-spread']['title'], rows['game-NFL-1-spread']['odds']), ('ATL -3.5', -112))
        self.assertEqual((rows['game-NFL-1-over']['title'], rows['game-NFL-1-over']['odds']), ('CAR @ ATL over 44.5', -108))
        self.assertEqual((rows['game-NFL-1-under']['direction'], rows['game-NFL-1-under']['odds']), ('under', -112))

    def test_a_fresh_multi_book_capture_prices_every_side_at_its_best_book(self):
        game = slate_game('NFL-1', '2026-09-20T17:00:00Z')
        record = {'retrievedAt': '2026-09-19T11:00:00Z', 'books': {
            'draftkings': {'spread': {'home': -3.5, 'homePrice': -112, 'awayPrice': -108}, 'total': {'line': 44.5, 'over': -108, 'under': -112}},
            'fanduel': {'spread': {'home': -3.0, 'homePrice': -115, 'awayPrice': -105}, 'total': {'line': 44.5, 'over': -105, 'under': -115}}}}
        rows = {r['id']: r for r in build_site.game_market_lines({'games': [game]}, self.now, {'NFL-1': record})}
        self.assertEqual(sorted(rows), ['game-NFL-1-away', 'game-NFL-1-home', 'game-NFL-1-over', 'game-NFL-1-under'])
        self.assertEqual((rows['game-NFL-1-home']['title'], rows['game-NFL-1-home']['book'], rows['game-NFL-1-home']['odds']), ('ATL -3', 'FanDuel', -115))
        self.assertEqual((rows['game-NFL-1-away']['title'], rows['game-NFL-1-away']['book'], rows['game-NFL-1-away']['odds']), ('CAR +3.5', 'DraftKings', -108))
        self.assertEqual((rows['game-NFL-1-over']['book'], rows['game-NFL-1-over']['odds']), ('FanDuel', -105))
        self.assertEqual(len(rows['game-NFL-1-home']['books']), 2)
        self.assertEqual([rows[k]['side'] for k in ('game-NFL-1-home', 'game-NFL-1-away', 'game-NFL-1-over')], ['home', 'away', None])
        stale = dict(record, retrievedAt='2026-09-18T11:00:00Z')
        old = {r['id'] for r in build_site.game_market_lines({'games': [game]}, self.now, {'NFL-1': stale})}
        self.assertEqual(old, {'game-NFL-1-spread', 'game-NFL-1-over', 'game-NFL-1-under'}, 'a day-old capture falls back to the feed')

    def test_started_games_and_games_without_a_line_are_left_out(self):
        games = [slate_game('NFL-1', '2026-09-19T11:00:00Z'), slate_game('NFL-2', '2026-09-20T17:00:00Z', state='in'),
                 slate_game('NFL-3', '2026-09-20T17:00:00Z', spread=None, total=None)]
        self.assertEqual(build_site.game_market_lines({'games': games}, self.now), [])


class DepthRoleUsageTests(unittest.TestCase):
    def test_second_back_usage_comes_from_each_games_actual_snap_order(self):
        records = [
            {'eventId': '1', 'league': 'NFL', 'season': 2026, 'seasonType': 2, 'kickoff': '2026-09-01T17:00:00Z',
             'teams': {'23': {}, '5': {}}, 'players': [
                 {'id': 'a', 'team': '23', 'name': 'Lead One', 'pos': 'RB', 'car': 10, 'tgt': 2, 'rzCar': 2, 'i10Car': 1, 'rushTD': 1},
                 {'id': 'b', 'team': '23', 'name': 'Second One', 'pos': 'RB', 'car': 5, 'tgt': 3}]},
            {'eventId': '2', 'league': 'NFL', 'season': 2026, 'seasonType': 2, 'kickoff': '2026-09-08T17:00:00Z',
             'teams': {'23': {}, '6': {}}, 'players': [
                 {'id': 'a', 'team': '23', 'name': 'Lead One', 'pos': 'RB', 'car': 12, 'tgt': 2},
                 {'id': 'c', 'team': '23', 'name': 'Next Up', 'pos': 'RB', 'car': 7, 'tgt': 1, 'rzCar': 1}]},
        ]
        snaps = {
            '1': {'a': {'id': 'a', 'team': '23', 'pos': 'RB', 'name': 'Lead One', 'snaps': 42, 'pct': .70},
                  'b': {'id': 'b', 'team': '23', 'pos': 'RB', 'name': 'Second One', 'snaps': 18, 'pct': .30}},
            '2': {'a': {'id': 'a', 'team': '23', 'pos': 'RB', 'name': 'Lead One', 'snaps': 36, 'pct': .60},
                  'c': {'id': 'c', 'team': '23', 'pos': 'RB', 'name': 'Next Up', 'snaps': 24, 'pct': .40}},
        }
        usage = build_site.depth_role_usage(records, snaps, '23', 'RB', 2, '2026-09-15T17:00:00Z', 2026, 'c')
        self.assertEqual((usage['role'], usage['definition']), ('RB2', 'No. 2 RB by offensive snaps in each game'))
        self.assertEqual(usage['roleUsage'], {'games': 2, 'snapPct': .35, 'volume': {'car': 6.0, 'tgt': 2.0},
            'redZone': 1, 'redZoneGames': 1, 'inside10': None, 'touchdowns': None,
            'coverage': {'car': 2, 'tgt': 2, 'rzCar': 1, 'i10Car': 0, 'rushTD': 0, 'recTD': 0},
            'redZoneObserved': 1, 'touchdownObserved': 0})
        self.assertEqual(usage['playerUsage']['redZoneObserved'], 1)
        self.assertIsNone(usage['playerUsage']['inside10'], 'missing play-by-play is not zero')
        self.assertEqual(usage['playerUsage']['volume'], {'car': 7.0, 'tgt': 1.0})

    def test_role_usage_never_looks_past_the_game_being_built(self):
        records = [{'eventId': 'late', 'league': 'NFL', 'season': 2026, 'seasonType': 2,
                    'kickoff': '2026-09-20T17:00:00Z', 'teams': {'23': {}, '5': {}}, 'players': []}]
        snaps = {'late': {'x': {'id': 'x', 'team': '23', 'pos': 'RB', 'snaps': 30, 'pct': .5},
                          'y': {'id': 'y', 'team': '23', 'pos': 'RB', 'snaps': 20, 'pct': .3}}}
        self.assertIsNone(build_site.depth_role_usage(records, snaps, '23', 'RB', 2,
                                                       '2026-09-20T17:00:00Z', 2026, 'y'))


class GradeTests(unittest.TestCase):
    snapshot = {'gameId': 'CFB-1', 'league': 'CFB', 'model': 'v2.0', 'publishedAt': '2026-09-19T10:00:00Z', 'margin': 5.0, 'total': 30.0,
                'sd': {'margin': 13.0, 'total': 12.0}, 'range80': {'margin': [-11.7, 21.7], 'total': [25.6, 56.4]},
                'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}}}

    def line(self, **extra):
        return {'state': 'open', 'odds': -110, 'line': 44.5, 'gameMarket': True, 'market': 'total points',
                'direction': 'under', **extra}

    def test_a_game_line_is_graded_with_the_desk_arithmetic(self):
        grade = build_site.grade_line(self.line(), self.snapshot, thin=False)
        self.assertEqual(grade['tier'], 'strong')
        self.assertGreater(grade['chance'], grade['needs'])
        self.assertEqual(grade['needs'], round(110 / 210, 3))
        spread = build_site.grade_line(self.line(market='point spread', line=-2.5, direction=None), self.snapshot, False)
        self.assertGreater(spread['chance'], 0.5, 'v2 has the home side by 5 against -2.5')
        self.assertLess(grade['chance'], grade['raw'], 'the shown chance is the calibrated one')
        self.assertTrue(grade['calibrated'])
        self.assertEqual(grade['fairOdds'], build_site.fair_american(grade['chance']))
        self.assertAlmostEqual(grade['ev'], grade['chance'] * (1 + 100 / 110) - 1, places=3)
        self.assertEqual(grade['chanceDisplay'], grade['chance'])
        self.assertEqual(grade['range80'], [25.6, 56.4])

    def test_public_line_fields_drop_unknown_books_and_exclude_comparison_only_prices(self):
        now = datetime(2026, 9, 19, 13, tzinfo=timezone.utc)
        rows = build_site.public_lines([
            {'id': 'missing', 'book': 'Book unavailable'},
            {'id': 'x', 'book': 'ESPN BET', 'line': 44.5, 'odds': -110, 'observedAt': '2026-09-19T12:30:00Z',
             'books': [{'book': 'Hard Rock Bet', 'line': 44.5, 'odds': 105},
                       {'book': 'FanDuel', 'line': 44.5, 'odds': -105}]},
        ], now)
        self.assertEqual([row['id'] for row in rows], ['x'])
        self.assertEqual((rows[0]['book'], rows[0]['ageMinutes'], rows[0]['freshness']),
                         ('ESPN BET', 30, 'fresh'))
        self.assertNotIn('displayBook', rows[0])
        self.assertEqual(rows[0]['bestSameLine'], {'book': 'FanDuel', 'odds': -105})
        self.assertNotIn('displayBook', rows[0]['books'][0])

    def test_an_away_spread_row_is_graded_as_the_away_side(self):
        home = build_site.grade_line(self.line(market='point spread', line=-2.5, direction=None), self.snapshot, False)
        away = build_site.grade_line(self.line(market='point spread', line=2.5, direction=None, side='away'), self.snapshot, False)
        self.assertLess(away['raw'], 0.5, 'v2 has the home side by 5, so the visitor at +2.5 is the wrong side')
        self.assertAlmostEqual(home['raw'] + away['raw'], 1.0, places=2)
        self.assertEqual(away['tier'], 'pass')

    def test_a_game_page_gets_every_priced_main_line_the_board_likes_with_hit_rates(self):
        now = datetime(2026, 9, 19, 13, tzinfo=timezone.utc)
        game = {'id': 'NFL-1', 'league': 'NFL', 'season': 2026, 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.0, 100.0]}]},
                                'away': {'players': []}}}
        lines = [
            {'id': 'prop-1', 'gameId': 'NFL-1', 'state': 'open', 'gameMarket': False,
             'title': 'Player Ten over 55.5 receiving yards', 'player': 'Player Ten', 'athleteId': '10',
             'position': 'WR', 'stat': 'recYds', 'market': 'receiving yards', 'direction': 'over', 'line': 55.5,
             'odds': -110, 'book': 'FanDuel', 'observedAt': '2026-09-19T12:40:00Z',
             'grade': {'view': 'lean', 'chance': .58, 'needs': .524, 'edge': 5.6, 'projection': 70.0,
                       'calibrated': True, 'thin': False, 'limited': False}},
            {'id': 'prop-2', 'gameId': 'NFL-1', 'state': 'open', 'gameMarket': False,
             'title': 'Player Ten over 5.5 receptions', 'player': 'Player Ten', 'athleteId': '10',
             'position': 'WR', 'stat': 'rec', 'market': 'receptions', 'direction': 'over', 'line': 5.5,
             'odds': +120, 'book': 'DraftKings', 'observedAt': '2026-09-19T12:40:00Z',
             'grade': {'view': 'lean', 'chance': .50, 'needs': .455, 'edge': 4.5, 'projection': 6.2,
                       'calibrated': True, 'thin': False, 'limited': False}},
        ]
        history = {'10': [
            {'kickoff': '2026-09-01T17:00:00Z', 'season': 2026, 'seasonType': 2,
             'stats': {'recYds': 40, 'rec': 4}},
            {'kickoff': '2026-09-08T17:00:00Z', 'season': 2026, 'seasonType': 2,
             'stats': {'recYds': 60, 'rec': 6}},
            {'kickoff': '2026-09-15T17:00:00Z', 'season': 2026, 'seasonType': 2,
             'stats': {'recYds': 70, 'rec': 7}},
        ]}
        rows = build_site.favorite_lines(game, snapshot, lines, now, history)
        self.assertEqual([row['title'] for row in rows],
                         ['Player Ten over 55.5 receiving yards', 'Player Ten over 5.5 receptions'])
        self.assertEqual(rows[0]['line'], 55.5, 'the listed favorite is the main value line, not an alternate')
        self.assertFalse(rows[0]['alternate'])
        self.assertEqual(rows[0]['sourceId'], 'prop-1')
        self.assertEqual(rows[0]['team'], '1')
        self.assertEqual(rows[0]['teamAbbr'], 'ATL')
        self.assertEqual(rows[0]['opponent'], '2')
        self.assertEqual(rows[0]['opponentAbbr'], 'CAR')
        self.assertEqual(rows[0]['position'], 'WR')
        self.assertEqual(rows[0]['stat'], 'recYds')
        self.assertEqual(rows[0]['history'], {'last': {'hits': 2, 'games': 3, 'rate': 67,
                                                       'values': [40, 60, 70]},
                                              'season': {'hits': 2, 'games': 3, 'rate': 67,
                                                         'values': [40, 60, 70]}})

    def test_favorites_do_not_force_a_thin_role_or_an_unpriced_read(self):
        now = datetime(2026, 9, 19, 13, tzinfo=timezone.utc)
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.0, 100.0]}]},
                                'away': {'players': []}}}
        base = {'id': 'prop-1', 'gameId': 'NFL-1', 'state': 'open', 'gameMarket': False,
                'title': 'Player Ten over 55.5 receiving yards', 'athleteId': '10', 'stat': 'recYds',
                'market': 'receiving yards', 'direction': 'over', 'line': 55.5, 'odds': -110,
                'book': 'FanDuel', 'observedAt': '2026-09-19T12:40:00Z',
                'grade': {'view': 'lean', 'chance': .58, 'needs': .524, 'edge': 5.6, 'projection': 70.0,
                          'thin': True, 'limited': False}}
        self.assertEqual(build_site.favorite_lines(game, snapshot, [base], now), [])
        stale = dict(base, observedAt='2026-09-18T12:00:00Z', grade=dict(base['grade'], thin=False))
        self.assertEqual(build_site.favorite_lines(game, snapshot, [stale], now), [])
        unpriced = dict(base, odds=None, grade=dict(base['grade'], thin=False))
        self.assertEqual(build_site.favorite_lines(game, snapshot, [unpriced], now), [])

    def test_a_thin_sample_never_reads_strong_and_closed_or_unpriced_lines_get_no_grade(self):
        self.assertEqual(build_site.grade_line(self.line(), self.snapshot, thin=True)['tier'], 'lean')
        self.assertIsNone(build_site.grade_line(self.line(state='closed'), self.snapshot, False))
        self.assertIsNone(build_site.grade_line(self.line(odds=None), self.snapshot, False))
        self.assertIsNone(build_site.grade_line(self.line(), None, False))

    def test_a_prop_needs_a_v2_projection_for_that_player(self):
        prop = {'state': 'open', 'odds': -115, 'line': 55.5, 'direction': 'OVER', 'athleteId': '10',
                'title': 'Player Ten OVER 55.5 receiving yards'}
        self.assertEqual(build_site.grade_line(prop, self.snapshot, False)['projection'], 70.0)
        self.assertIsNone(build_site.grade_line(dict(prop, athleteId='99'), self.snapshot, False))

    def test_projection_sheet_values_keep_the_best_real_price_and_its_gate_state(self):
        lines = [
            {'gameId': 'NFL-1', 'gameMarket': True, 'state': 'open', 'market': 'point spread', 'side': 'home',
             'line': -3.5, 'odds': -110, 'book': 'DraftKings', 'observedAt': '2026-09-19T12:00:00Z',
             'grade': {'chance': .54, 'needs': .524, 'edge': 1.6, 'tier': 'pass', 'thin': False}},
            {'gameId': 'NFL-1', 'gameMarket': True, 'state': 'open', 'market': 'point spread', 'side': 'away',
             'line': 4.0, 'odds': -105, 'book': 'FanDuel', 'observedAt': '2026-09-19T12:00:00Z',
             'grade': {'chance': .56, 'needs': .512, 'edge': 4.8, 'tier': 'lean',
                       'performanceCaution': True, 'performanceNeed': 3.0, 'thin': False}},
            {'gameId': 'NFL-1', 'gameMarket': True, 'state': 'open', 'market': 'total points', 'direction': 'under',
             'line': 44.5, 'odds': 100, 'book': 'BetMGM', 'observedAt': '2026-09-19T12:00:00Z',
             'grade': {'chance': .55, 'needs': .5, 'edge': 5.0, 'tier': 'strong', 'thin': False}},
            {'gameId': 'NFL-1', 'gameMarket': True, 'state': 'open', 'market': 'total points', 'direction': 'over',
             'line': 43.5, 'odds': -120, 'book': 'Caesars', 'grade': None},
        ]
        values = build_site.sheet_values(lines, datetime(2026, 9, 19, 18, tzinfo=timezone.utc))['NFL-1']
        self.assertEqual((values['spread']['side'], values['spread']['odds'], values['spread']['book']),
                         ('away', -105, 'FanDuel'))
        self.assertTrue(values['spread']['performanceCaution'])
        self.assertEqual(values['spread']['performanceNeed'], 3.0)
        self.assertEqual((values['total']['side'], values['total']['line'], values['total']['edge']),
                         ('under', 44.5, 5.0))
        self.assertEqual(build_site.sheet_values(lines, datetime(2026, 9, 20, 1, tzinfo=timezone.utc)), {},
                         'a price older than twelve hours cannot earn a sheet highlight')


class PropRowTests(unittest.TestCase):
    def test_player_lines_become_board_rows_with_the_models_lean(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': None}}
        capture = {'retrievedAt': '2026-09-19T12:05:00Z', 'source': 'https://example.test/props',
                   'lines': {'10': {'recYds': [55.5, 57.5], 'recLong': [18.5, 18.5]}, '99': {'rec': [3.5, 3.5]}}}
        now = datetime(2026, 9, 19, 13, tzinfo=timezone.utc)
        rows = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {'10': 'Player Ten'},
                                    {'10': 3, '99': 1}, {}, now)
        by_id = {r['id']: r for r in rows}
        self.assertEqual(sorted(by_id), ['prop-NFL-1-10-recYds', 'prop-NFL-1-99-rec'], 'recLong has no projection market')
        row = by_id['prop-NFL-1-10-recYds']
        self.assertEqual((row['title'], row['state'], row['odds'], row['position']), ('Player Ten over 55.5 receiving yards', 'unpriced', None, 'WR'))
        self.assertEqual(row['grade']['tier'], 'lean')
        self.assertGreater(row['grade']['chance'], 0.6)
        self.assertIsNone(row['grade']['needs'])
        self.assertFalse(row['grade']['calibrated'])
        other = by_id['prop-NFL-1-99-rec']
        self.assertIsNone(other['grade'])
        self.assertEqual(other['gradeNote'], 'no v2 projection for this player')

    def test_a_priced_player_line_takes_the_best_book_and_is_graded_against_it(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': None}}
        capture = {'retrievedAt': '2026-09-19T12:05:00Z', 'source': 'https://example.test/props',
                   'lines': {'10': {'recYds': [55.5, 57.5]}}}
        prices = {'NFL-1': {'retrievedAt': '2026-09-19T12:40:00Z', 'source': 'https://example.test/odds', 'books': {
            'draftkings': {'markets': {'recYds': {'Player Ten Jr.': {'line': 55.5, 'over': -115, 'under': -105}}}},
            'fanduel': {'markets': {'recYds': {'Player Ten': {'line': 54.5, 'over': -118, 'under': -104}}}}}}}
        rows = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {'10': 'Player Ten'},
                                    {'10': 3}, {}, datetime(2026, 9, 19, 13, tzinfo=timezone.utc), prices)
        row = rows[0]
        self.assertEqual((row['state'], row['book'], row['line'], row['odds']), ('open', 'FanDuel', 54.5, -118),
                         'the over takes the lowest number on offer')
        self.assertEqual(row['title'], 'Player Ten over 54.5 receiving yards')
        self.assertEqual(len(row['books']), 2, 'a suffix does not hide the same player at another book')
        self.assertEqual(row['grade']['needs'], round(118 / 218, 3), 'a price means the chance has something to beat')
        self.assertGreater(row['grade']['edge'], 0)
        self.assertEqual(row['grade']['tier'], 'pass', 'raw-only value is not a calibrated lean')
        self.assertEqual(row['observedAt'], '2026-09-19T12:40:00Z', 'the row is as fresh as the price on it')

    def test_the_board_shows_the_calibrated_chance_the_desk_acts_on(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': None}}
        capture = {'retrievedAt': '2026-09-19T12:05:00Z', 'source': 'https://example.test/props',
                   'lines': {'10': {'recYds': [55.5, 57.5]}}}
        prices = {'NFL-1': {'retrievedAt': '2026-09-19T12:40:00Z', 'source': 'https://example.test/odds', 'books': {
            'fanduel': {'markets': {'recYds': {'Player Ten': {'line': 54.5, 'over': -118, 'under': -104}}}}}}}
        args = ({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {'10': 'Player Ten'}, {'10': 3}, {},
                datetime(2026, 9, 19, 13, tzinfo=timezone.utc), prices)
        raw = build_site.prop_rows(*args)[0]['grade']
        shrunk = build_site.prop_rows(*args, calibration={'NFL': (0.13, 0.0)})[0]['grade']
        self.assertAlmostEqual(shrunk['chance'], round(0.5 + 0.13 * (raw['raw'] - 0.5), 3), places=3)
        self.assertTrue(shrunk['calibrated'])
        self.assertEqual(shrunk['raw'], raw['raw'], 'the raw number is kept beside it')
        self.assertLess(shrunk['edge'], 0, 'shrunk toward a coin flip, it no longer clears -118')
        self.assertEqual((raw['view'], shrunk['view']), ('pass', 'pass'), 'raw-only and negative learned value both fail')
        self.assertEqual(shrunk['tier'], 'pass')
        self.assertEqual(shrunk['rawTier'], 'lean', 'the desk still records its refusal for learning')
        gentle = build_site.prop_rows(*args, calibration={'NFL': (0.9, 0.0)})[0]['grade']
        self.assertEqual(gentle['view'], 'lean', 'a calibrated chance that still clears the price stays a lean')
        self.assertEqual(build_site.prop_rows(*args, calibration={'CFB': (0.13, 0.0)})[0]['grade']['chance'], raw['chance'],
                         'another league\'s calibration does not apply')

    def test_college_player_lines_come_from_the_priced_feed_and_are_graded_before_they_are_played(self):
        game = {'id': 'CFB-1', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-03T16:00:00Z',
                'home': {'id': '1', 'abbreviation': 'MICH'}, 'away': {'id': '2', 'abbreviation': 'IOWA'}}
        snapshot = {'gameId': 'CFB-1', 'league': 'CFB', 'model': 'v2.0', 'publishedAt': '2026-10-02T12:00:00Z', 'kickoff': game['kickoff'],
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': None}}
        record = {'gameId': 'CFB-1', 'retrievedAt': '2026-10-03T12:00:00Z', 'source': 'x', 'books': {
            'fanduel': {'markets': {'recYds': {'Player Ten': {'line': 56.5, 'over': -110, 'under': -110}}}},
            'draftkings': {'markets': {'recYds': {'Player Ten Jr.': {'line': 55.5, 'over': -115, 'under': -105}},
                                       'rec': {'Nobody Known': {'line': 3.5, 'over': -110, 'under': -110}}}}}}
        captures = build_site.feed_captures({'CFB-1': [record]}, {'CFB-1': game}, {'CFB-1': [snapshot]}, {'10': 'Player Ten'})
        self.assertEqual(captures['CFB-1'][0]['lines'], {'10': {'recYds': [55.5, None]}}, "DraftKings' main number, matched by name")
        self.assertEqual(captures['CFB-1'][0]['provider'], 'DraftKings')
        rows = build_site.prop_rows(captures, {'CFB-1': game}, {'CFB-1': [snapshot]}, {'10': 'Player Ten'}, {'10': 3}, {},
                                    datetime(2026, 10, 3, 13, tzinfo=timezone.utc), {'CFB-1': record})
        grade = rows[0]['grade']
        self.assertEqual((rows[0]['state'], rows[0]['league']), ('open', 'CFB'))
        self.assertEqual((grade['tier'], grade['view'], grade.get('unproven')), ('pass', 'pass', True),
                         'the desk judges it (and learning grades it); the site says it is graded before it is played')
        calibrated = build_site.prop_rows(captures, {'CFB-1': game}, {'CFB-1': [snapshot]}, {'10': 'Player Ten'}, {'10': 3}, {},
                                          datetime(2026, 10, 3, 13, tzinfo=timezone.utc), {'CFB-1': record}, calibration={'CFB': (0.9, 0.0)})
        self.assertNotIn('unproven', calibrated[0]['grade'])

    def test_a_role_settled_last_season_is_not_thin_on_one_game(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': None}}
        capture = {'retrievedAt': '2026-09-19T12:05:00Z', 'source': 'https://example.test/props', 'lines': {'10': {'recYds': [55.5, 55.5]}}}
        now = datetime(2026, 9, 19, 13, tzinfo=timezone.utc)
        veteran = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {'10': 'Player Ten'}, {'10': 1}, {}, now,
                                       None, {('10', '1')})
        self.assertEqual(veteran[0]['grade']['tier'], 'lean', 'sixteen games in this role last season settle it')
        self.assertFalse(veteran[0]['grade']['thin'])
        moved = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {'10': 'Player Ten'}, {'10': 1}, {}, now,
                                     None, {('10', '9')})
        self.assertTrue(moved[0]['grade']['thin'], 'the same player on a new team is a new role')

    def test_a_price_is_taken_at_the_number_the_feed_shows(self):
        record = {'retrievedAt': '2026-09-21T09:00:00Z', 'source': 'https://example.test/odds', 'books': {
            'draftkings': {'markets': {'cmp': {'Jaxson Dart': {'line': 34.5, 'over': -114, 'under': -113,
                                                              'alternates': [{'line': 19.5, 'over': -125, 'under': -102}]}}}}}}
        self.assertEqual(build_site.price_quotes(record, 'cmp', 'Jaxson Dart', 19.5), [('draftkings', 19.5, -125, -102)],
                         "the rung matching the feed's number is the one priced")
        self.assertEqual(build_site.price_quotes(record, 'cmp', 'Jaxson Dart', 24.5), [('draftkings', 34.5, -114, -113)],
                         'with no matching rung the book keeps its own number')
        self.assertEqual(build_site.price_quotes(record, 'cmp', 'Nobody', 19.5), [])

    def test_a_questionable_player_never_reads_as_a_lean(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        player = {'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5], 'limited': True}
        snapshot = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [player]}, 'away': None}}
        capture = {'retrievedAt': '2026-09-19T12:05:00Z', 'source': 'https://example.test/props', 'lines': {'10': {'recYds': [55.5, 55.5]}}}
        now = datetime(2026, 9, 19, 13, tzinfo=timezone.utc)
        row = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {'10': 'Player Ten'}, {'10': 5}, {}, now)[0]
        self.assertTrue(row['grade']['limited'])
        self.assertEqual(row['grade']['tier'], 'pass', 'five games of role does not outrank a questionable tag')
        healthy = dict(snapshot, players={'home': {'players': [{k: v for k, v in player.items() if k != 'limited'}]}, 'away': None})
        ok = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [healthy]}, {'10': 'Player Ten'}, {'10': 5}, {}, now)[0]
        self.assertEqual(ok['grade']['tier'], 'lean')

    def test_a_prop_row_names_the_stat_behind_its_market(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'gameId': 'NFL-1', 'league': 'NFL', 'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': None}}
        capture = {'retrievedAt': '2026-09-19T12:05:00Z', 'source': 'https://example.test/props', 'lines': {'10': {'recYds': [55.5, 55.5]}}}
        now = datetime(2026, 9, 19, 13, tzinfo=timezone.utc)
        rows = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {'10': 'Player Ten'}, {'10': 3}, {}, now)
        self.assertEqual(rows[0]['stat'], 'recYds', 'the site reads the stat off the row, never off the words')
        self.assertEqual(rows[0]['market'], 'receiving yards')

    def test_a_thin_sample_prop_stays_grey(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-20T17:00:00Z',
                'home': {'id': '1', 'abbreviation': 'ATL'}, 'away': {'id': '2', 'abbreviation': 'CAR'}}
        snapshot = {'model': 'v2.0', 'publishedAt': '2026-09-19T12:00:00Z',
                    'players': {'home': {'players': [{'id': '10', 'pos': 'RB', 'carries': [7.0, 3.0, 11.0]}]}, 'away': None}}
        capture = {'retrievedAt': '2026-09-19T12:05:00Z', 'source': 'https://example.test/props', 'lines': {'10': {'car': [13.5, 13.5]}}}
        rows = build_site.prop_rows({'NFL-1': [capture]}, {'NFL-1': game}, {'NFL-1': [snapshot]}, {}, {'10': 1}, {},
                                    datetime(2026, 9, 19, 13, tzinfo=timezone.utc))
        self.assertEqual(rows[0]['direction'], 'under')
        self.assertGreater(rows[0]['grade']['chance'], 0.9)
        self.assertEqual(rows[0]['grade']['tier'], 'pass', 'one game this season cannot set a role')
        self.assertTrue(rows[0]['grade']['thin'])


class ForecastTests(unittest.TestCase):
    def test_model_strength_ranks_put_best_offense_and_defense_first(self):
        ranks = build_site.rating_ranks({'A': {'off': 4.0, 'def': 1.5},
                                         'B': {'off': -1.0, 'def': -3.0},
                                         'C': {'off': 4.0, 'def': 0.0}})
        self.assertEqual(ranks['A'], {'offense': 1, 'defense': 3, 'teams': 3})
        self.assertEqual(ranks['B'], {'offense': 3, 'defense': 1, 'teams': 3})
        self.assertEqual(ranks['C'], {'offense': 1, 'defense': 2, 'teams': 3}, 'ties share first place')

    def test_game_card_keeps_each_teams_current_model_ranks(self):
        game = dict(slate_game('NFL-test', '2026-10-05T00:20:00Z'), season=2026)
        strength = {'1': {'offense': 8, 'defense': 20, 'teams': 32},
                    '2': {'offense': 14, 'defense': 4, 'teams': 32}}
        card = build_site.game_card(game, {}, None, {}, {}, strength=strength)
        self.assertEqual(card['home']['strength'], strength['1'])
        self.assertEqual(card['away']['strength'], strength['2'])

    def test_a_snapshot_published_after_kickoff_is_never_the_forecast(self):
        snaps = [{'publishedAt': '2026-09-20T12:00:00Z'}, {'publishedAt': '2026-09-20T16:30:00Z'}]
        self.assertEqual(build_site.pregame(snaps, '2026-09-20T17:00:00Z'), snaps)
        self.assertEqual(build_site.pregame(snaps, '2026-09-20T16:00:00Z'), snaps[:1])
        self.assertEqual(build_site.pregame(snaps, '2026-09-20T11:00:00Z'), [])

    def test_lean_is_model_margin_against_the_market_margin(self):
        market = {'spread': -3.0, 'total': 44.5}
        self.assertEqual(build_site.lean({'margin': 5.0, 'total': 42.0}, market), {'spread': 2.0, 'side': 'home', 'total': -2.5})
        with_chance = build_site.lean({'margin': 5.0, 'total': 42.0}, market, 'CFB', {'margin': 16.31, 'total': 16.18})
        self.assertGreater(with_chance['spreadChance'], 0.5)
        self.assertLess(with_chance['spreadChance'], 0.55, 'a 2-point gap is worth little after calibration')
        self.assertGreater(with_chance['totalChance'], 0.5)
        nfl = build_site.lean({'margin': 5.0, 'total': 42.0}, market, 'NFL', {'margin': 13.21, 'total': 12.79})
        self.assertEqual(nfl['spreadChance'], 0.5, 'NFL spreads carry no information after calibration')
        self.assertEqual(build_site.lean({'margin': 1.0, 'total': 44.5}, market)['side'], 'away')
        self.assertIsNone(build_site.lean({'margin': 1.0, 'total': 44.5}, None))
        self.assertIsNone(build_site.lean({'margin': 3.0, 'total': 44.5}, market)['side'])
        cautious = build_site.lean({'margin': 5.0, 'total': 42.0}, market, 'NFL', {'margin': 13.21, 'total': 12.79}, {'NFL/total'})
        self.assertTrue(cautious['totalCaution'], 'poor performance is a visible higher-bar caution')
        self.assertNotIn('spreadCaution', cautious)
        self.assertEqual(cautious['totalChance'], nfl['totalChance'], 'the number is kept; only the label changes')


class TableTests(unittest.TestCase):
    def wr(self, pid, team, rec, yds):
        return {'id': pid, 'team': team, 'name': f'Player {pid}', 'pos': 'WR', 'rec': rec, 'recYds': yds, 'tgt': rec + 2}

    def test_player_rows_keep_the_log_layout_and_home_flags(self):
        records = [game('1', datetime(2025, 9, 7, 17, tzinfo=timezone.utc), 'A', 'B', 24, 17, players=[self.wr('10', 'A', 5, 70)]),
                   game('2', datetime(2025, 9, 14, 17, tzinfo=timezone.utc), 'B', 'A', 20, 13, players=[self.wr('10', 'A', 3, 30)]),
                   game('3', datetime(2025, 9, 21, 17, tzinfo=timezone.utc), 'A', 'C', 21, 20, neutral=True,
                        players=[self.wr('10', 'A', 8, 101)])]
        index, shards, leaders, season = build_site.build_players('NFL', records, {'3': {'10': (61, 0.92)}}, {('NFL', 'A'): {'abbr': 'AAA'}})
        self.assertEqual(index, [['10', 'Player 10', 'WR', 'A', 'AAA', '2025-09-21', 3]])
        self.assertEqual(season, 2025)
        self.assertEqual(leaders['recYds'], [['10', 'Player 10', 'AAA', 201.0, 3]], 'the season leader board adds the stored games')
        self.assertEqual(leaders['passYds'], [], 'a stat nobody recorded has no leaders')
        rows = shards[10 % build_site.SHARDS['NFL']]['10']['rows']
        keys = list(build_site.LOG_KEYS)
        self.assertEqual([r[:8] for r in rows], [['1', '2025-09-07', 2025, 1, 2, 'A', 'B', 1],
                                                 ['2', '2025-09-14', 2025, 1, 2, 'A', 'B', 0],
                                                 ['3', '2025-09-21', 2025, 1, 2, 'A', 'C', -1]])
        self.assertEqual([r[8 + keys.index('recYds')] for r in rows], [70, 30, 101])
        self.assertEqual(rows[2][8 + keys.index('snaps')], 61)
        self.assertIsNone(rows[0][8 + keys.index('snapPct')], 'no snap count is unknown, not zero')

    def test_player_charts_keep_all_stats_for_upcoming_roles_in_a_compact_payload(self):
        now = datetime(2026, 10, 4, 15, tzinfo=timezone.utc)
        upcoming = dict(slate_game('NFL-next', '2026-10-05T00:20:00Z'), season=2026)
        upcoming['home'].update(name='Falcons')
        upcoming['away'].update(name='Panthers')
        snapshot = {'model': 'v2.0', 'publishedAt': '2026-10-04T14:00:00Z', 'players': {
            'home': {'players': [{'id': '10', 'name': 'Player Ten', 'pos': 'WR',
                                  'receptions': [4.2, 1, 8], 'recYds': [61.5, 10, 110]}]},
            'away': {'players': []}}}
        logs = {'10': [
            {'kickoff': '2026-09-20T17:00:00Z', 'season': 2026, 'seasonType': 2, 'opp': '9', 'home': True,
             'team': '1', 'name': 'Player Ten', 'pos': 'WR',
             'stats': {'rec': 5, 'recYds': 72, 'recTD': 1, 'rzTgt': 2}},
            {'kickoff': '2025-09-20T17:00:00Z', 'season': 2025, 'seasonType': 2, 'opp': '8', 'home': False,
             'team': '1', 'name': 'Player Ten', 'pos': 'WR', 'stats': {'rec': 9, 'recYds': 140}}],
                '11': [{'kickoff': '2026-09-20T17:00:00Z', 'season': 2026, 'seasonType': 2, 'opp': '9', 'home': True,
                        'team': '1', 'name': 'Kicker Eleven', 'pos': 'PK', 'stats': {'fgm': 2, 'fga': 3, 'xpm': 3, 'kPts': 9}}]}
        line = {'gameId': 'NFL-next', 'athleteId': '10', 'stat': 'recYds', 'state': 'open', 'line': 59.5,
                'odds': -110, 'book': 'FanDuel', 'direction': 'over', 'observedAt': '2026-10-04T14:00:00Z'}
        payload = build_site.build_player_charts('NFL', [upcoming], {'NFL-next': [snapshot]}, logs, 2026, [line], now)
        self.assertEqual(len(payload['games']), 1)
        self.assertEqual(len(payload['players']), 2)
        player = next(p for p in payload['players'] if p['id'] == '10')
        self.assertEqual(player['projection'], {'rec': 4.2, 'recYds': 61.5})
        self.assertEqual(player['lines']['recYds']['line'], 59.5)
        self.assertEqual(player['rows'][0]['stats']['recTD'], 1, 'touchdowns and role stats stay available')
        self.assertEqual(player['rows'][0]['stats']['rzTgt'], 2)
        self.assertEqual(len(player['rows']), 1, 'prior seasons do not enter the current chart')
        kicker = next(p for p in payload['players'] if p['id'] == '11')
        self.assertEqual(kicker['rows'][0]['stats']['kPts'], 9, 'unprojected kickers still reach the all-stat chart')

    def test_dates_are_eastern_calendar_dates(self):
        self.assertEqual(build_site.day('2026-09-18T00:15Z'), '2026-09-17')
        self.assertEqual(build_site.day('2026-12-01T01:15Z'), '2026-11-30')
        self.assertEqual(build_site.day('2026-09-13T17:00Z'), '2026-09-13')

    def test_defense_table_averages_regular_season_games_allowed(self):
        logs = {'A': [{'season': 2026, 'seasonType': 1, 'allowed': {'WR': {'recYds': 500}}},
                      {'season': 2026, 'seasonType': 2, 'allowed': {'WR': {'recYds': 150, 'rec': 12}, 'QB': {'rushTD': 2}}},
                      {'season': 2026, 'seasonType': 2, 'allowed': {'WR': {'recYds': 90, 'rec': 8}, 'QB': {'rushTD': 1}}},
                      {'season': 2025, 'seasonType': 2, 'allowed': {'WR': {'recYds': 10}}}]}
        table = build_site.defense_table('NFL', logs, 2026)
        self.assertEqual(table['A']['g'], 2)
        self.assertEqual((table['A']['WR']['recYds'], table['A']['WR']['rec']), (120.0, 10.0))
        self.assertIsNone(table['A']['QB']['att'], 'unobserved is not a zero-yard/attempt game')
        self.assertEqual(table['A']['coverage']['QB']['att'], 0)
        self.assertEqual(table['A']['coverage']['WR']['recYds'], 2)
        self.assertEqual(table['A']['QB']['rushTD'], 1.5)
        self.assertEqual(build_site.defense_table('NFL', logs, 2026, last=1)['A']['WR']['recYds'], 90.0)
        self.assertEqual(build_site.defense_table('NFL', logs, 2024), {})

    def test_defense_missing_values_do_not_inflate_a_defenses_rank(self):
        logs = {'A': [
            {'season': 2026, 'seasonType': 2, 'allowed': {'WR': {'recYds': 0}}},
            {'season': 2026, 'seasonType': 2, 'allowed': {'WR': {'recYds': 100}}},
            {'season': 2026, 'seasonType': 2, 'allowed': {'WR': {}}},
            {'season': 2026, 'seasonType': 2, 'allowed': {'WR': {'recYds': None}}},
            {'season': 2026, 'seasonType': 2, 'allowed': {'WR': {'recYds': float('nan')}}},
        ]}
        row = build_site.defense_table('NFL', logs, 2026)['A']
        self.assertEqual(row['g'], 5)
        self.assertEqual(row['WR']['recYds'], 50.0)
        self.assertEqual(row['coverage']['WR']['recYds'], 2)
        self.assertIsNone(row['TE']['recYds'])

    def test_chart_season_is_complete_and_excludes_future_or_unknown_stats(self):
        now = datetime(2026, 10, 4, 15, tzinfo=timezone.utc)
        upcoming = dict(slate_game('NFL-next', '2026-10-05T00:20:00Z'), season=2026)
        snapshot = {'model': 'v2.0', 'publishedAt': '2026-10-04T14:00:00Z', 'players': {
            'home': {'players': [{'id': '10', 'name': 'Player Ten', 'pos': 'WR'}]}, 'away': {'players': []}}}
        rows = [{'kickoff': f'2026-09-{day:02}T17:00:00Z', 'season': 2026, 'seasonType': 2,
                 'team': '1', 'opp': '2', 'home': False, 'name': 'Player Ten', 'pos': 'WR',
                 'stats': {'recYds': day - 2, 'rec': None, 'recTD': float('nan')}} for day in range(1, 23)]
        rows.append(dict(rows[0], kickoff='2026-10-05T17:00:00Z', stats={'recYds': 999}))
        payload = build_site.build_player_charts('NFL', [upcoming], {'NFL-next': [snapshot]},
                                                 {'10': list(reversed(rows))}, 2026, [], now)
        history = payload['players'][0]['rows']
        self.assertEqual(len(history), 22, 'Season must not silently mean last 20')
        self.assertEqual(history[0]['stats'], {'recYds': -1})
        self.assertEqual(history[1]['stats'], {'recYds': 0})
        self.assertEqual(history[-1]['stats'], {'recYds': 20})

class PayloadSplitTests(unittest.TestCase):
    def test_trend_history_is_stored_once_per_player_stat(self):
        history = [{'date': '2026-09-01', 'value': 10}]
        payload = build_site.trend_payload([
            {'league': 'NFL', 'season': 2026, 'athleteId': '1', 'stat': 'rec', 'line': 2.5, 'history': history},
            {'league': 'NFL', 'season': 2026, 'athleteId': '1', 'stat': 'rec', 'line': 3.5, 'history': history},
        ])
        self.assertEqual(len(payload['histories']), 1)
        self.assertEqual(payload['rows'][0]['contextKey'], payload['rows'][1]['contextKey'])
        self.assertEqual(payload['contexts'][payload['rows'][0]['contextKey']]['stat'], 'rec')
        self.assertNotIn('history', payload['rows'][0])

    def test_today_keeps_open_and_last_72_hours(self):
        now = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
        rows = [{'id': 'open'},
                {'id': 'recent', 'result': 'win', 'settledAt': '2026-10-04T12:00:00Z'},
                {'id': 'old', 'result': 'loss', 'settledAt': '2026-10-01T12:00:00Z'}]
        self.assertEqual([row['id'] for row in build_site.recent_picks(rows, now)], ['open', 'recent'])


if __name__ == '__main__':
    unittest.main()
