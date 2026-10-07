import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import record_scope


class RecordScopeTests(unittest.TestCase):
    def test_priced_imports_join_the_site_headline_when_they_became_public(self):
        rows = [
            {'id': 'NFL-old', 'league': 'NFL', 'season': 2026, 'seasonType': 2,
             'historicalImport': True, 'odds': -115, 'result': 'win', 'publishedAt': '2026-09-26T12:00:00Z'},
            {'id': 'NFL-unpriced', 'league': 'NFL', 'season': 2026, 'seasonType': 2,
             'historicalImport': True, 'odds': None, 'result': 'win', 'publishedAt': '2026-09-26T12:00:00Z'},
            {'id': 'CFB-new', 'league': 'CFB', 'season': 2026, 'seasonType': 2, 'odds': -110,
             'result': 'loss', 'publishedAt': '2026-09-27T12:00:00Z', 'settledAt': '2026-09-27T22:00:00Z'},
        ]
        self.assertEqual(record_scope.summary(rows, '2026-09-28T12:00:00Z'),
                         {'wins': 1, 'losses': 1, 'pushes': 0, 'voids': 0})
        self.assertEqual(record_scope.summary(rows, '2026-09-26T11:59:00Z'),
                         {'wins': 0, 'losses': 0, 'pushes': 0, 'voids': 0})

    def test_current_stage_matches_the_site_default(self):
        rows = [
            {'id': 'regular', 'league': 'NFL', 'season': 2026, 'seasonType': 2, 'odds': -110,
             'result': 'win', 'publishedAt': '2026-12-01T12:00:00Z', 'settledAt': '2026-12-01T22:00:00Z'},
            {'id': 'playoff', 'league': 'NFL', 'season': 2026, 'seasonType': 3, 'odds': -110,
             'result': 'loss', 'publishedAt': '2027-01-10T12:00:00Z', 'settledAt': '2027-01-10T22:00:00Z'},
            {'id': 'old-season', 'league': 'NFL', 'season': 2025, 'seasonType': 2, 'odds': -110,
             'result': 'win', 'publishedAt': '2025-12-01T12:00:00Z', 'settledAt': '2025-12-01T22:00:00Z'},
        ]
        self.assertEqual(record_scope.summary(rows, '2027-01-11T12:00:00Z'),
                         {'wins': 0, 'losses': 1, 'pushes': 0, 'voids': 0})


if __name__ == '__main__':
    unittest.main()
