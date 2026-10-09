import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OwnerPlanTests(unittest.TestCase):
    def test_agents_points_to_the_current_owner_plan(self):
        agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('docs/KOOKN-PLAN.md', agents)
        self.assertIn('owner, 2026-10-09', agents)

    def test_owner_plan_is_tracked_by_every_numbered_task(self):
        import json
        status = json.loads((ROOT / 'docs/product-status.json').read_text(encoding='utf-8'))
        ids = {item['id'] for item in status['items']}
        expected = {f'KP-T{n}' for n in range(28)} | {'KP-T-SITE', 'KP-T-ART'}
        self.assertTrue(expected <= ids)


if __name__ == '__main__':
    unittest.main()
