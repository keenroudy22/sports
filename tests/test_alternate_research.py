import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site as b


class AlternateResearchTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 19, 15, tzinfo=timezone.utc)
        self.game = {'id': 'NFL-test', 'league': 'NFL', 'state': 'pre', 'season': 2026,
                     'kickoff': '2026-10-20T00:15:00Z', 'home': {'abbreviation': 'WSH'},
                     'away': {'abbreviation': 'NY'}}
        self.player = {'id': '1', 'pos': 'WR', 'recYds': [60, 20, 100]}
        self.snapshot = {'players': {'home': {'players': [self.player]}, 'away': {'players': []}}}
        self.capture = {'retrievedAt': '2026-10-19T14:30:00Z', 'books': {'draftkings': {'markets': {
            'recYds': {'Real Player': {'line': 59.5, 'over': -110, 'under': -110,
                                     'alternates': [{'line': 39.5, 'over': -240, 'under': 180},
                                                    {'line': 79.5, 'over': 180, 'under': -240}]}}}}}}
        self.logs = {'1': [{'kickoff': f'2026-10-0{i}T17:00:00Z', 'seasonType': 2, 'season': 2026,
                            'stats': {'recYds': value}} for i, value in enumerate([20, 50, 80], 1)]}

    def rows(self, lines=None):
        return b.alternate_research(self.game, self.snapshot, self.capture, {'1': 'Real Player'},
                                    self.logs, self.now, lines)

    def test_exact_prices_projection_and_each_alternate_history(self):
        rows = self.rows()
        self.assertEqual([(r['line'], r['direction'], r['odds']) for r in rows],
                         [(39.5, 'over', -240), (79.5, 'under', -240)])
        self.assertEqual(rows[0]['projection'], 60)
        self.assertEqual(rows[0]['history']['last']['hits'], 2)
        self.assertIn('2 of his last 3', rows[0]['reasons'][1])
        self.assertEqual(rows[0]['observedAt'], self.capture['retrievedAt'])

    def test_stale_held_limited_and_started_never_promoted(self):
        self.capture['retrievedAt'] = '2026-10-19T10:00:00Z'
        self.assertEqual(self.rows(), [])
        self.capture['retrievedAt'] = '2026-10-19T14:30:00Z'
        self.player['underReview'] = ['recYds']
        self.assertEqual(self.rows(), [])
        self.player.pop('underReview')
        self.assertEqual(self.rows([{'athleteId': '1', 'stat': 'recYds', 'injuryHold': True}]), [])
        self.player['limited'] = True
        self.assertEqual(self.rows(), [])

    def test_no_price_is_invented_and_inconsistent_ladder_is_rejected(self):
        quote = self.capture['books']['draftkings']['markets']['recYds']['Real Player']
        quote['alternates'][0]['over'] = None
        quote['alternates'][1]['over'] = -300
        self.assertEqual(self.rows(), [])
