"""Real current-team evidence for the October 7 projection/price hold."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import features
import gates
import role_sanity
import run


class RoleSanityTests(unittest.TestCase):
    def test_current_team_qb_change_holds_new_starter_and_teammate_receiving(self):
        logs = features.player_logs(features.load(seasons={2026}))
        damante = {'id': '5152503', 'pos': 'QB', 'att': [30]}
        changed = role_sanity.quarterback_change([damante], logs, '166', 2026, 'CFB', '2026-10-08T00:00:00Z')
        self.assertEqual(changed['expectedQB'], '5152503')
        self.assertTrue(role_sanity.affected_by_qb_change('5152503', 'QB', 'passYds', changed))
        self.assertTrue(role_sanity.affected_by_qb_change('4869443', 'WR', 'recYds', changed),
                        'TK King has only two Damante full games, so Hedden-era targets cannot justify a fresh grade')
        self.assertFalse(role_sanity.affected_by_qb_change('4869443', 'WR', 'rushYds', changed))
        daniels = {'id': '4596472', 'pos': 'QB', 'att': [30]}
        changed = role_sanity.quarterback_change([daniels], logs, '27', 2026, 'NFL', '2026-10-09T00:00:00Z')
        self.assertTrue(role_sanity.affected_by_qb_change('4596472', 'QB', 'rushYds', changed),
                        'the four-snap cameo must not establish Jalon Daniels rushing')
        self.assertTrue(role_sanity.affected_by_qb_change('4596448', 'RB', 'rec', changed),
                        'Bucky Irving receptions still lean on Mayfield-era targets')
        stable = role_sanity.quarterback_change([{'id': '2577417', 'pos': 'QB', 'att': [35]}],
                                                logs, '6', 2026, 'NFL', '2026-10-09T00:00:00Z')
        self.assertIsNone(stable, 'the CFB team with numeric id 6 must not contaminate Dallas')

    def test_split_projected_qb_attempts_hold_even_without_recent_game_change(self):
        logs = {'one': []}
        result = role_sanity.quarterback_change([
            {'id': 'new', 'pos': 'QB', 'att': [24]}, {'id': 'other', 'pos': 'QB', 'att': [8]}],
            logs, 'team', 2026, 'CFB')
        self.assertIn('below 85%', result['reason'])

    def test_jj_kohl_current_fiu_full_games_exclude_partial_and_old_team(self):
        logs = features.player_logs(features.load())['4870883']
        found = role_sanity.assess({'att': [23.7, 6.7, 40.7]}, logs, '2229', 'passYds', 2026)
        self.assertEqual(found, {'volume': 'att', 'projected': 23.7,
                                 'recentFullAverage': 43.0, 'fullGames': 3})
        self.assertIsNone(role_sanity.assess({'att': [34.0, 20.0, 48.0]}, logs, '2229', 'passYds', 2026))

    def test_egbuka_plus_1800_main_price_cannot_receive_a_grade(self):
        self.assertTrue(role_sanity.price_suspect(1800, .508))
        self.assertTrue(role_sanity.price_suspect(-110, .80))
        self.assertFalse(role_sanity.price_suspect(-110, .54))
        self.assertFalse(role_sanity.price_suspect(None, .54))
        capture = {'books': {
            'draftkings': {'markets': {'recYds': {'Emeka Egbuka': {'line': 34.5, 'over': 1800, 'under': -114}}}},
            'fanduel': {'markets': {'recYds': {'Emeka Egbuka': {'line': 33.5, 'over': -114, 'under': -114}}}}}}
        self.assertEqual(build_site.price_quotes(capture, 'recYds', 'Emeka Egbuka'),
                         [('fanduel', 33.5, -114, -114)])

    def test_exact_two_sided_price_and_other_book_check(self):
        pair = [('draftkings', 49.5, -105, -105)]
        self.assertIsNone(role_sanity.quote_issue(pair, 'DraftKings', 49.5, 'over', -105))
        self.assertIn('two-sided', role_sanity.quote_issue([('draftkings', 49.5, -102, None)],
                                                          'DraftKings', 49.5, 'over', -102))
        self.assertIn('exact line', role_sanity.quote_issue(pair, 'DraftKings', 50.5, 'over', -105))
        self.assertIn('another book', role_sanity.quote_issue(
            pair + [('fanduel', 49.5, +180, -230)], 'DraftKings', 49.5, 'over', -105))
        self.assertIsNone(role_sanity.quote_issue(
            pair + [('fanduel', 49.5, -110, -110)], 'DraftKings', 49.5, 'over', -105))

    def test_damante_under_is_held_with_split_attempts(self):
        logs = features.player_logs(features.load(seasons={2026}))
        players = [{'id': '5152503', 'pos': 'QB', 'att': [30]},
                   {'id': 'hed', 'pos': 'QB', 'att': [16]},
                   {'id': '4869443', 'pos': 'WR', 'targets': [8]}]
        changed = role_sanity.quarterback_change(players, logs, '166', 2026, 'CFB',
                                                 '2026-10-08T23:00:00Z')
        self.assertIsNotNone(changed)
        self.assertTrue(role_sanity.affected_by_qb_change('5152503', 'QB', 'passYds', changed))
        self.assertTrue(role_sanity.affected_by_qb_change('4869443', 'WR', 'recYds', changed))
        now = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)
        game = {'id': 'CFB-nmsu', 'league': 'CFB', 'season': 2026,
                'kickoff': '2026-10-08T23:00:00Z', 'home': {'id': '166'}, 'away': {'id': '1'}}
        snap = {'gameId': game['id'], 'publishedAt': '2026-10-07T17:00:00Z',
                'players': {'home': {'players': players}, 'away': {'players': []}}}
        ctx = gates.Context(now=now, games={game['id']: game}, snapshots={game['id']: [snap]},
                            player_logs=logs)
        damante_under = {'athleteId': '5152503', 'market': 'passYds', 'gameIds': [game['id']],
                         'line': 206.5, 'odds': -110, 'direction': 'under'}
        self.assertFalse(gates.player_projection_sanity(damante_under, ctx).ok)

    def test_five_corrupted_september_draftkings_quotes_fail_price_guard(self):
        source = Path(__file__).resolve().parents[1] / 'data/learning/candidates-2026.jsonl'
        found = {}
        with source.open(encoding='utf-8') as stream:
            for raw in stream:
                row = json.loads(raw)
                if row.get('book') != 'DraftKings' or row.get('decidedAt', '')[:10] not in ('2026-09-26', '2026-09-27'):
                    continue
                if row.get('kind') == 'player' and row.get('odds') in (1200, 1500, 1300, 950, 700):
                    found[row['odds']] = row
        self.assertEqual(set(found), {1200, 1500, 1300, 950, 700})
        for odds, row in found.items():
            with self.subTest(odds=odds, title=row['title']):
                self.assertTrue(role_sanity.price_suspect(row['odds'], row.get('chance')))
                self.assertIn('two-sided', role_sanity.quote_issue([], row['book'], row['line'],
                                                                  row['direction'], row['odds']))

    def test_build_marks_suspect_player_lines_and_logs_once_per_row(self):
        now = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)
        game = {'id': 'CFB-test', 'league': 'CFB', 'season': 2026,
                'kickoff': '2026-10-08T23:00:00Z', 'home': {'id': '2229'}, 'away': {'id': '166'}}
        logs = features.player_logs(features.load())['4870883']
        snap = {'publishedAt': '2026-10-07T17:00:00Z', 'players': {
            'home': {'players': [{'id': '4870883', 'att': [23.7, 6.7, 40.7]}]},
            'away': {'players': []}}}
        rows = [{'id': 'kohl-under', 'gameId': game['id'], 'athleteId': '4870883',
                 'stat': 'passYds', 'odds': -110, 'grade': {'chance': .54}},
                {'id': 'bad-price', 'gameId': game['id'], 'athleteId': 'other',
                 'stat': 'recYds', 'odds': 1800, 'grade': {'chance': .508}}]
        notices = []
        build_site.guard_player_lines(rows, {game['id']: game}, {game['id']: [snap]},
                                      {'CFB': {'player_logs': {'4870883': logs}}}, now, notices.append)
        self.assertTrue(rows[0]['roleSuspect'])
        self.assertEqual(rows[0]['gradeNote'], 'Projection under review')
        self.assertIsNone(rows[0]['grade'])
        self.assertTrue(rows[1]['priceSuspect'])
        self.assertIsNone(rows[1]['grade'])
        self.assertEqual(len(notices), 2)

    def test_build_holds_receiver_after_qb_change_without_a_low_target_projection(self):
        now = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)
        game = {'id': 'CFB-nmsu', 'league': 'CFB', 'season': 2026,
                'kickoff': '2026-10-08T23:00:00Z', 'home': {'id': '166'}, 'away': {'id': '1'}}
        logs = features.player_logs(features.load(seasons={2026}))
        snap = {'publishedAt': '2026-10-07T17:00:00Z', 'players': {
            'home': {'players': [{'id': '5152503', 'pos': 'QB', 'att': [30]},
                                 {'id': '4869443', 'pos': 'WR', 'targets': [8]}]},
            'away': {'players': []}}}
        row = {'id': 'king-over', 'gameId': game['id'], 'athleteId': '4869443',
               'stat': 'recYds', 'odds': -110, 'grade': {'chance': .54}}
        notices = []
        build_site.guard_player_lines([row], {game['id']: game}, {game['id']: [snap]},
                                      {'CFB': {'player_logs': logs}}, now, notices.append)
        self.assertTrue(row['roleSuspect'])
        self.assertIsNone(row['grade'])
        self.assertEqual(row['gradeNote'], 'Projection under review')
        self.assertEqual(len(notices), 1)
        self.assertIn('current QB', notices[0])

    def test_official_gate_refuses_kohl_even_if_an_old_board_still_has_a_grade(self):
        now = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)
        game = {'id': 'CFB-test', 'league': 'CFB', 'season': 2026,
                'kickoff': '2026-10-08T23:00:00Z', 'home': {'id': '2229'}, 'away': {'id': '166'}}
        snap = {'gameId': 'CFB-test', 'publishedAt': '2026-10-07T17:00:00Z',
                'players': {'home': {'players': [{'id': '4870883', 'att': [23.7, 6.7, 40.7]}]},
                            'away': {'players': []}}}
        ctx = gates.Context(now=now, games={game['id']: game}, snapshots={game['id']: [snap]},
                            player_logs={'4870883': features.player_logs(features.load())['4870883']})
        candidate = {'athleteId': '4870883', 'market': 'passYds', 'gameIds': [game['id']],
                     'line': 261.5, 'odds': -114, 'direction': 'under'}
        result = gates.player_projection_sanity(candidate, ctx)
        self.assertFalse(result.ok)
        self.assertIn('23.7 att', result.reason)
        stale_row = {'id': 'kohl', 'gameId': game['id'], 'athleteId': '4870883',
                     'stat': 'passYds', 'state': 'open', 'grade': None, 'odds': -114}
        self.assertEqual(run.candidates([stale_row], ctx.games, now), [])

    def test_official_gate_refuses_qb_change_receiver_even_with_normal_targets(self):
        now = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)
        game = {'id': 'CFB-nmsu', 'league': 'CFB', 'season': 2026,
                'kickoff': '2026-10-08T23:00:00Z', 'home': {'id': '166'}, 'away': {'id': '1'}}
        snap = {'gameId': game['id'], 'publishedAt': '2026-10-07T17:00:00Z',
                'players': {'home': {'players': [{'id': '5152503', 'pos': 'QB', 'att': [30]},
                                                 {'id': '4869443', 'pos': 'WR', 'targets': [8]}]},
                            'away': {'players': []}}}
        ctx = gates.Context(now=now, games={game['id']: game}, snapshots={game['id']: [snap]},
                            player_logs=features.player_logs(features.load(seasons={2026})))
        candidate = {'athleteId': '4869443', 'market': 'recYds', 'gameIds': [game['id']],
                     'line': 49.5, 'odds': -110, 'direction': 'over'}
        result = gates.player_projection_sanity(candidate, ctx)
        self.assertFalse(result.ok)
        self.assertIn('QB-change role under review', result.reason)


if __name__ == '__main__':
    unittest.main()
