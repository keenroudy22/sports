import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import season_trends as T
import research_posts as R
import receipts

NOW = datetime(2026, 10, 4, 14, tzinfo=timezone.utc)


def logs(values):
    return [{'eventId': str(i), 'kickoff': f'2026-09-{i+1:02d}T17:00:00Z', 'season': 2026,
             'seasonType': 2, 'team': '1', 'opp': '3', 'name': 'A Player', 'stats': {'rec': n}}
            for i, n in enumerate(values)]


class SeasonTrendsTests(unittest.TestCase):
    def test_whole_season_and_missing_not_dropped(self):
        rows = logs([2, 3, 0, 2])
        hist = T.history(rows, 'rec', 2026, NOW)
        self.assertEqual(T.result(hist, 2, 'at-least')['hits'], 3)
        self.assertEqual(T.result(hist, 2, 'over')['hits'], 1)
        self.assertEqual(T.result(hist, 2, 'over')['pushes'], 2)
        self.assertEqual(T.result(hist, 2, 'under')['hits'], 1)
        rows[-1]['stats'] = {}
        self.assertEqual(T.history(rows, 'rec', 2026, NOW), [])

    def test_exclude_previous_season_preseason_future_and_duplicates(self):
        rows = logs([1, 2, 3])
        extra = [dict(rows[0], season=2025), dict(rows[0], eventId='pre', seasonType=1),
                 dict(rows[0], eventId='future', kickoff='2026-11-01T17:00:00Z'), rows[0]]
        self.assertEqual(len(T.history(rows + extra, 'rec', 2026, NOW)), 3)
        self.assertEqual(T.history(rows[:2], 'rec', 2026, NOW), [])

    def test_early_season_fill_uses_prior_year_only_after_two_current_games(self):
        current = logs([3, 4])
        prior = [dict(row, eventId=f'old-{i}', season=2025, kickoff=f'2025-09-{i+1:02d}T17:00:00Z')
                 for i, row in enumerate(logs([1, 2, 5]))]
        filled = T.history(prior + current, 'rec', 2026, NOW, team='1')
        self.assertEqual([row['value'] for row in filled], [1, 2, 5, 3, 4])
        self.assertEqual(sum(row['priorSeason'] for row in filled), 3)
        self.assertEqual(T.history(prior + current[:1], 'rec', 2026, NOW, team='1'), [])

    def test_cfb_dvp_rank_and_fcs_padded_streak_become_a_reason_against(self):
        def allowed(team, opponent, date, value):
            return {'eventId': f'{team}-{date}', 'kickoff': f'2026-09-{date:02d}T17:00:00Z', 'season': 2026,
                    'seasonType': 2, 'team': team, 'opp': opponent,
                    'allowed': {'WR': {'recYds': value}}}
        defense = {
            'A': [allowed('A', 'X', i, 20) for i in (1, 2, 3)],
            'B': [allowed('B', 'X', i, 60) for i in (1, 2, 3)],
            'C': [allowed('C', 'X', i, 90) for i in (1, 2, 3)],
        }
        kickoff = datetime(2026, 10, 4, 17, tzinfo=timezone.utc)
        ranks = T.defense_ranks(defense, 'WR', 'recYds', 2026, kickoff, {'A', 'B', 'C'})
        self.assertEqual(ranks['A']['rank'], 1)
        self.assertEqual(ranks['A']['average'], 20.0)
        hist = [
            {'eventId': '1', 'date': '2026-09-01', 'kickoff': '2026-09-20T17:00:00Z', 'season': 2026,
             'priorSeason': False, 'opponent': 'FCS-1', 'value': 80},
            {'eventId': '2', 'date': '2026-09-02', 'kickoff': '2026-09-21T17:00:00Z', 'season': 2026,
             'priorSeason': False, 'opponent': 'FCS-2', 'value': 75},
            {'eventId': '3', 'date': '2026-09-03', 'kickoff': '2026-10-01T17:00:00Z', 'season': 2026,
             'priorSeason': False, 'opponent': 'C', 'value': 30},
        ]
        tagged, dvp, splits, adjusted = T.opponent_context(
            hist, 49.5, 'over', 'CFB', defense, 'WR', 'recYds', 2026, kickoff, 'A', {'A', 'B', 'C'})
        self.assertEqual(dvp['rank'], 1)
        self.assertEqual([row['opponentQuality'] for row in tagged[:2]], ['fcs', 'fcs'])
        self.assertEqual(splits['fcs']['hits'], 2)
        self.assertTrue(adjusted['against'])
        self.assertFalse(adjusted['supports'])

    def fixture(self):
        game = {'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'season': 2026,
                'kickoff': '2026-10-04T17:00:00Z', 'home': {'id': '1', 'name': 'Home'},
                'away': {'id': '2', 'name': 'Away'}}
        info = {'NFL': {'current': 2026, 'player_logs': {'123': logs([3, 4, 5, 6, 3])}, 'records': []}}
        quote = {'retrievedAt': '2026-10-04T13:00:00Z', 'books': {'fanduel': {'markets': {'rec': {
            'A Player': {'line': 3.5, 'over': -110, 'under': -110,
                         'alternates': [{'line': 2.5, 'over': -300, 'under': 200}]}}}}}}
        return game, info, quote

    def test_alternate_exact_rung_and_stale_quotes(self):
        g, info, q = self.fixture()
        rows = T.build([g], info, [], {'NFL-1': q}, NOW)
        alt = next(r for r in rows if r['kind'] == 'alternate')
        self.assertEqual((alt['line'], alt['hits'], alt['games'], alt['odds']), (2.5, 5, 5, -300))
        self.assertTrue(any(r['kind'] == 'milestone' and r['line'] == 3 for r in rows))
        q['retrievedAt'] = '2026-10-03T13:00:00Z'
        self.assertTrue(all(r['kind'] == 'milestone' for r in T.build([g], info, [], {'NFL-1': q}, NOW)))
        g['state'] = 'in'
        self.assertEqual(T.build([g], info, [], {'NFL-1': q}, NOW), [])

    def test_ambiguous_name_refuses_feed_match(self):
        g, info, q = self.fixture()
        info['NFL']['player_logs']['456'] = logs([3, 4, 5])
        self.assertTrue(all(r['kind'] == 'milestone' for r in T.build([g], info, [], {'NFL-1': q}, NOW)))

    def test_social_full_season_priced_five_games_and_guard(self):
        g, info, q = self.fixture()
        rows = T.build([g], info, [], {'NFL-1': q}, NOW)
        # Social trend boards use current main lines, never easy alternates.
        main = dict(next(r for r in rows if r['kind'] == 'alternate'), kind='main',
                    projection=4.8, priceClears=True)
        rows.append(main)
        card = R.season_candidate([g], {'NFL-1': {'seasonTrends': rows}}, NOW)
        self.assertEqual(card['kind'], 'season')
        self.assertEqual(card['title'], '100% TREND BOARD')
        self.assertTrue(all(r['kind'] == 'main' for r in card['rows']))
        self.assertIn('5/5', card['text'])
        self.assertIn("KOOK'N 100% TREND BOARD", card['text'])
        self.assertNotIn('@Playbook', card['text'])
        self.assertEqual(receipts.guard({'text': card['text']}), [])
        self.assertIn('5/5 this season', R.svg(card))
        for r in rows:
            r['injuryStatus'] = 'Out'
        self.assertIsNone(R.season_candidate([g], {'NFL-1': {'seasonTrends': rows}}, NOW))
        for r in rows:
            r['injuryStatus'] = None
            r['games'] = 3
        self.assertIsNone(R.season_candidate([g], {'NFL-1': {'seasonTrends': rows}}, NOW))

    def test_cfb_social_trend_refuses_opponent_padded_evidence(self):
        g, info, q = self.fixture()
        g['league'] = 'CFB'
        row = dict(next(r for r in T.build([dict(g, league='NFL')], info, [], {'NFL-1': q}, NOW)
                        if r['kind'] == 'alternate'), kind='main', league='CFB', games=5, hits=5,
                   projection=4.8, priceClears=True,
                   opponentAdjustment={'against': True, 'supports': False})
        self.assertIsNone(R.season_candidate([g], {'NFL-1': {'seasonTrends': [row]}}, NOW))

    def test_one_editorial_per_day_across_families(self):
        self.assertTrue(R.already_posted({'posts': [{'id': 'research:upset:2026-10-04'}]}, NOW.date()))
        self.assertTrue(R.already_posted({'posts': {'research:upset:2026-10-04': {}}}, NOW.date()))
        self.assertFalse(R.already_posted({'posts': {'research:season:2026-10-03': {}}}, NOW.date()))


if __name__ == '__main__':
    unittest.main()
