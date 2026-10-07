import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import payload_budget


class PayloadBudgetTests(unittest.TestCase):
    def site(self, root, today=b'{}'):
        root = Path(root)
        for name in ('index.html', 'app.css', 'app.js'):
            (root / name).write_bytes(b'ok')
        app = root / 'data/app'
        (app / 'teams').mkdir(parents=True)
        (app / 'trends').mkdir()
        (app / 'today.json').write_bytes(today)
        (app / 'lines.json').write_bytes(b'{}')
        (app / 'teams/CFB.json').write_bytes(b'{}')
        (app / 'teams/CFB-defense.json').write_bytes(b'{}')
        (app / 'trends/index.json').write_text(json.dumps({'files': []}))
        return root

    def test_split_payloads_under_limits_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(payload_budget.check(self.site(folder))['issues'], [])

    def test_monolith_and_oversize_first_payload_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.site(folder, b'x' * (payload_budget.LIMITS['today'] + 1))
            (root / 'data/app/trends.json').write_bytes(b'{}')
            issues = payload_budget.check(root)['issues']
            self.assertTrue(any(x.startswith('today:') for x in issues))
            self.assertIn('trends-monolith:present', issues)

    def test_hosted_budget_runs_after_build_and_before_upload(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml').read_text()
        self.assertLess(workflow.index('python scripts/build_site.py'), workflow.index('python scripts/payload_budget.py'))
        self.assertLess(workflow.index('python scripts/payload_budget.py'), workflow.index('actions/upload-pages-artifact@'))


if __name__ == '__main__':
    unittest.main()
