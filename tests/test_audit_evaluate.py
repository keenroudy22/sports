import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_evaluate as A
import model_v2


class AuditEvaluationTests(unittest.TestCase):
    def test_variants_do_not_mutate_released_weights(self):
        before = model_v2.params_hash()
        variants = A.variants()
        self.assertNotIn('blowoutWeight', variants['released']['margin'])
        self.assertEqual(variants['blowout']['margin']['blowoutWeight'], .35)
        variants['continuity']['margin']['ridge'] = 999
        self.assertEqual(before, model_v2.params_hash())

    def test_games_remain_in_whole_week_blocks_and_match_ids(self):
        rows = [{'eventId': str(i), 'kickoff': f'2026-09-{1 + 7*i:02}T17:00:00Z',
                 'forecast': {'margin': 3}, 'margin': 7} for i in range(4)]
        candidate = [{**r, 'forecast': {'margin': 5}} for r in rows]
        comparison = A.paired_weeks(rows, candidate, 'margin', draws=100)
        self.assertEqual(comparison['weeks'], 4)
        self.assertEqual(comparison['meanErrorDelta'], -2)
        self.assertEqual(comparison['status'], 'improvement')
        self.assertEqual(A.paired_weeks(rows[:1], candidate, 'margin')['status'], 'insufficient weeks')
