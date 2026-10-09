import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import replay_selection


class OctoberPlanReplayTests(unittest.TestCase):
    def test_every_october_1_to_9_football_day_has_a_play(self):
        rows = replay_selection.replay(date(2026, 10, 1), date(2026, 10, 9))
        football = [row for row in rows if row['footballDay']]
        self.assertEqual(len(football), 9)
        self.assertFalse([row['date'] for row in football if row['dark']])
        self.assertTrue(all(play.get('lane') and play.get('reason') for row in football for play in row['plays']))
        tnf = next(row for row in rows if row['date'] == '2026-10-08')
        self.assertTrue(any('ferguson' in play['id'] for play in tnf['plays']))
        for row in football:
            for play in row['plays']:
                if play['exactBookCount'] == 1:
                    self.assertLessEqual(play['gap'], 15)
                    self.assertLessEqual(play['quoteAgeSeconds'], 7200)


if __name__ == '__main__':
    unittest.main()
