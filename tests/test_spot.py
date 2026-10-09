import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import spot


def row(i, market='rushYds', side='under', result='win', gap=8, fair=.52, athlete=True):
    return {'id': str(i), 'gameIds': [f'CFB-{i}'], 'athleteId': str(i) if athlete else None,
            'league': 'CFB', 'market': market if athlete else None,
            'marketType': None if athlete else market, 'direction': side,
            'odds': -110, 'gap': gap, 'fairChance': fair, 'result': result}


class SpotTests(unittest.TestCase):
    def test_latest_decision_is_kept_after_the_since_filter(self):
        rows = [dict(row(1), decidedAt='2026-09-18T10:00:00Z'),
                dict(row(1), decidedAt='2026-09-18T11:00:00Z', odds=-120)]
        self.assertEqual(spot.distinct(rows)[0]['odds'], -120)

    def test_fallback_and_fair_anchored_shrink(self):
        rush = [row(i, result='win' if i < 22 else 'loss') for i in range(30)]
        rec = [row(100 + i, market='rec', result='loss') for i in range(30)]
        good = spot.summarize(rush + rec, row(999), minimum=30)
        bad = spot.summarize(rush + rec, row(998, market='rec'), minimum=30)
        self.assertEqual(good['level'][:3], ['CFB', 'rushYds', 'under'])
        self.assertGreater(good['spotHit'], .52)
        self.assertLess(bad['spotHit'], .52)


if __name__ == '__main__':
    unittest.main()
