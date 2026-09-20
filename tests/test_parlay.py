import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import parlay


NOW = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)   # 10 AM ET on a Sunday


def line(gid, title, line_, chance, books, kickoff='2026-09-20T17:00Z', thin=False, athlete=None, tier='lean'):
    best = books[0]
    return {'id': f'row-{gid}-{title}', 'gameId': gid, 'league': 'NFL', 'state': 'open', 'title': title, 'line': line_,
            'odds': best['odds'], 'book': best['book'], 'market': 'total points', 'direction': 'under', 'kickoff': kickoff,
            'observedAt': '2026-09-20T12:00:00Z', 'books': books, 'athleteId': athlete,
            'grade': {'chance': chance, 'tier': tier, 'thin': thin, 'games': 1 if thin else 3}}


DK, FD = 'DraftKings', 'FanDuel'


class BuildTests(unittest.TestCase):
    rows = [
        line('NFL-1', 'A @ B under 43.5', 43.5, 0.56, [{'book': DK, 'line': 43.5, 'odds': -110}, {'book': FD, 'line': 43.5, 'odds': -108}]),
        line('NFL-1', 'A @ B over 43.5', 43.5, 0.44, [{'book': DK, 'line': 43.5, 'odds': -110}]),      # the same game's other side
        line('NFL-2', 'C @ D under 40.5', 40.5, 0.55, [{'book': DK, 'line': 40.5, 'odds': -112}, {'book': FD, 'line': 41, 'odds': -110}]),
        line('NFL-3', 'E @ F under 47', 47, 0.54, [{'book': DK, 'line': 47, 'odds': -105}, {'book': FD, 'line': 47, 'odds': -105}]),
        line('NFL-4', 'G @ H under 50.5', 50.5, 0.535, [{'book': DK, 'line': 50.5, 'odds': -110}, {'book': FD, 'line': 50.5, 'odds': -115}]),
        line('NFL-5', 'I @ J under 39', 39, 0.53, [{'book': DK, 'line': 39, 'odds': -110}], kickoff='2026-09-20T14:15Z'),   # too close
        line('NFL-6', 'K @ L under 44', 44, 0.60, [{'book': DK, 'line': 44, 'odds': -110}], kickoff='2026-09-21T00:20Z', thin=True),
        line('NFL-7', 'Player over 3.5 receptions', 3.5, 0.9, [{'book': DK, 'line': 3.5, 'odds': 120}], thin=True, athlete='9', tier='pass'),
    ]

    def test_one_leg_per_game_at_one_book_at_the_graded_number(self):
        ticket, reason = parlay.build(self.rows, NOW, target=500)
        self.assertIsNone(reason)
        self.assertEqual(ticket['book'], DK, 'DraftKings carries every leg at its graded number; FanDuel moved one to 41')
        games = [l['gameId'] for l in ticket['legs']]
        self.assertEqual(len(games), len(set(games)), 'one leg per game')
        self.assertNotIn('NFL-5', games, 'a game inside the lead is left out')
        self.assertNotIn('NFL-7', games, 'a one-game prop never rides')
        self.assertIn('NFL-6', games, 'a thin game line rides; the ticket chance says what it is worth')
        self.assertTrue(ticket['reachedTarget'])
        self.assertGreaterEqual(ticket['odds'], 500)
        self.assertEqual(ticket['riskUnits'], 0.25)
        chances = 1.0
        dec = 1.0
        for leg in ticket['legs']:
            chances *= leg['chance']
            dec *= parlay.decimal(leg['odds'])
        self.assertAlmostEqual(ticket['fairChance'], round(chances, 4))
        self.assertEqual(ticket['odds'], parlay.american(dec))

    def test_too_few_games_means_no_ticket(self):
        ticket, reason = parlay.build(self.rows[:2], NOW)
        self.assertIsNone(ticket)
        self.assertIn('needs 3', reason)

    def test_price_arithmetic(self):
        self.assertAlmostEqual(parlay.decimal(-110), 1.909, places=3)
        self.assertAlmostEqual(parlay.decimal(150), 2.5)
        self.assertEqual(parlay.american(7.14), 614)
        self.assertEqual(parlay.american(1.5), -200)
        self.assertEqual(parlay.retitle({'title': 'A @ B under 43.5', 'line': 43.5}, 43.0), 'A @ B under 43')


if __name__ == '__main__':
    unittest.main()
