import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import learning

NOW = datetime(2026, 9, 29, 10, 45, tzinfo=timezone.utc)


class PolicyTests(unittest.TestCase):
    def test_defaults_are_the_written_rules(self):
        policy = learning.default_policy()
        self.assertEqual(learning.threshold(policy, 'lean.minEdge', 'NFL/total'), 1.0)
        self.assertEqual(learning.threshold(policy, 'prop.minEdge', 'NFL/prop:rec'), 5.0)
        self.assertEqual(learning.threshold(policy, 'prop.minRaw', 'NFL/prop:rec'), 0.60)
        self.assertFalse(learning.paused(policy, 'NFL/prop:rec'))

    def test_moves_stay_between_the_written_floor_and_the_cap_and_are_recorded(self):
        policy = learning.default_policy()
        self.assertIsNone(learning.move(policy, 'NFL/total', 'minEdge', 'lean.minEdge', -1, 'x', {}, NOW), 'never below the written rule')
        change = learning.move(policy, 'NFL/total', 'minEdge', 'lean.minEdge', +1, 'losing to the close', {'n': 31}, NOW)
        self.assertEqual((change['from'], change['to']), (1.0, 1.5))
        self.assertEqual(learning.threshold(policy, 'lean.minEdge', 'NFL/total'), 1.5)
        self.assertEqual(learning.threshold(policy, 'lean.minEdge', 'CFB/total'), 1.0, 'one segment at a time')
        for _ in range(10):
            learning.move(policy, 'NFL/total', 'minEdge', 'lean.minEdge', +1, 'x', {}, NOW)
        self.assertEqual(learning.threshold(policy, 'lean.minEdge', 'NFL/total'), 3.0, 'the cap holds')
        self.assertEqual(policy['history'][0]['why'], 'losing to the close')
        self.assertTrue(learning.set_paused(policy, 'NFL/total', True, 'still losing at the cap', {}, NOW))
        self.assertTrue(learning.paused(policy, 'NFL/total'))

    def test_a_hand_edited_policy_cannot_go_below_the_floor(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'policy.json'
            path.write_text(json.dumps({'knobs': {'lean.minEdge': {'value': 0.2}}, 'segments': {'NFL/total': {'minEdge': 0.1}}}))
            policy = learning.load_policy(path)
            self.assertEqual(policy['knobs']['lean.minEdge']['value'], 1.0)
            self.assertEqual(learning.threshold(policy, 'lean.minEdge', 'NFL/total'), 1.0)
            learning.save_policy(policy, path)
            self.assertEqual(learning.load_policy(path)['knobs']['lean.minEdge']['value'], 1.0)
        self.assertEqual(learning.load_policy(Path('/nonexistent/policy.json'))['knobs'], learning.default_policy()['knobs'])


class ArithmeticTests(unittest.TestCase):
    def test_closing_line_value_toward_our_side(self):
        self.assertEqual(learning.clv('total', 'over', 44.5, 46.0), 1.5)
        self.assertEqual(learning.clv('total', 'under', 44.5, 46.0), -1.5)
        self.assertEqual(learning.clv('spread', 'home', -3.0, -4.5), 1.5, 'home -3 closing -4.5 is a better number')
        self.assertEqual(learning.clv('spread', 'away', 7.0, 6.0), 1.0)
        self.assertEqual(learning.clv('prop', 'over', 4.5, 5.5), 1.0)
        self.assertIsNone(learning.clv('total', 'over', 44.5, None))

    def test_the_interval_is_seeded_and_brackets_the_mean(self):
        values = [1.0, -0.5, 0.5, 2.0, -1.0, 0.0, 1.5, 0.5] * 5
        a, b = learning.interval(values), learning.interval(values)
        self.assertEqual(a, b)
        self.assertLessEqual(a['low'], a['mean'])
        self.assertLessEqual(a['mean'], a['high'])
        self.assertEqual(a['n'], 40)
        self.assertIsNone(learning.interval([]))

    def test_segments(self):
        self.assertEqual(learning.segment_of({'id': 'NFL-2026-W4-x', 'marketType': 'total'}), 'NFL/total')
        self.assertEqual(learning.segment_of({'id': 'CFB-2026-W5-x', 'marketType': 'spread'}), 'CFB/spread')
        self.assertEqual(learning.segment_of({'id': 'NFL-2026-W4-x', 'athleteId': '7', 'market': 'recYds'}), 'NFL/prop:recYds')
        self.assertEqual(learning.segment_of({'id': 'NFL-2026-W4-x', 'legs': [{}]}), 'NFL/parlay')


class StoreTests(unittest.TestCase):
    def test_append_only_with_a_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            learning.append('candidates', 2026, [{'id': 'a'}], root)
            learning.append('candidates', 2026, [{'id': 'b'}], root)
            self.assertEqual([r['id'] for r in learning.read('candidates', 2026, root)], ['a', 'b'])
            path = learning.path_for('candidates', 2026, root)
            path.write_text(path.read_text().replace('"a"', '"z"'))
            with self.assertRaises(ValueError):
                learning.append('candidates', 2026, [{'id': 'c'}], root)


if __name__ == '__main__':
    unittest.main()
