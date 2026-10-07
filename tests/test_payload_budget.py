import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import payload_budget

VEGAS = (Path(__file__).resolve().parent / 'fixtures' / 'vegas.json').read_bytes()


class PayloadBudgetTests(unittest.TestCase):
    def site(self, root, today=b'{}'):
        root = Path(root)
        for name in payload_budget.SHELL_FILES:
            (root / name).write_bytes(b'ok')
        (root / 'app-more.js').write_bytes(b'ok')
        app = root / 'data/app'
        (app / 'teams').mkdir(parents=True)
        (app / 'trends').mkdir()
        (app / 'today.json').write_bytes(today)
        (app / 'today-hero.json').write_bytes(b'{"pick":null}')
        (app / 'lines.json').write_text(json.dumps({'count': 0, 'files': {'NFL': 'lines-NFL.json', 'CFB': 'lines-CFB.json'}}))
        (app / 'lines-NFL.json').write_bytes(b'{}')
        (app / 'lines-CFB.json').write_bytes(b'{}')
        (app / 'teams/CFB.json').write_bytes(b'{}')
        (app / 'teams/CFB-defense.json').write_bytes(b'{}')
        (app / 'trends/index.json').write_text(json.dumps({'files': []}))
        (app / 'vegas.json').write_bytes(VEGAS)
        return root

    def test_split_payloads_under_limits_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            result = payload_budget.check(self.site(folder))
            self.assertEqual((result['issues'], result['warnings']), ([], []))

    def test_data_breaches_warn_but_do_not_stop_cards_or_deploy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.site(folder, b'x' * (payload_budget.LIMITS['today'] + 1))
            (root / 'data/app/trends.json').write_bytes(b'{}')
            result = payload_budget.check(root)
            self.assertEqual(result['issues'], [])
            self.assertTrue(any(x.startswith('today:') for x in result['warnings']))
            self.assertIn('trends-monolith:present', result['warnings'])
            self.assertEqual(payload_budget.main(root), 0)

    def test_data_files_warn_before_they_exhaust_their_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            size = int(payload_budget.LIMITS['today'] * .91)
            root = self.site(folder, b'x' * size)
            result = payload_budget.check(root)
            self.assertIn(f'today:{size}/{payload_budget.LIMITS["today"]}:near', result['warnings'])
            self.assertEqual(result['issues'], [])

    def test_vegas_panel_payload_has_its_own_warning_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.site(folder)
            self.assertLess(len(VEGAS), payload_budget.LIMITS['vegas'])
            (root / 'data/app/vegas.json').write_bytes(b'x' * (payload_budget.LIMITS['vegas'] + 1))
            result = payload_budget.check(root)
            self.assertTrue(any(x.startswith('vegas:') for x in result['warnings']))
            self.assertEqual(result['issues'], [])
            (root / 'data/app/vegas.json').unlink()
            self.assertIn('vegas:missing', payload_budget.check(root)['warnings'])

    def test_shell_breach_still_stops_the_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.site(folder)
            (root / 'app.js').write_bytes(os.urandom(payload_budget.LIMITS['shell-gzip'] + 1))
            result = payload_budget.check(root)
            self.assertTrue(any(x.startswith('shell-gzip:') for x in result['issues']))
            self.assertEqual(payload_budget.main(root), 1)

    def test_lazy_bundle_breach_warns_without_blocking(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.site(folder)
            (root / 'app-more.js').write_bytes(os.urandom(payload_budget.LIMITS['lazy-more-gzip'] * 2))
            result = payload_budget.check(root)
            self.assertTrue(any(x.startswith('lazy-more-gzip:') for x in result['warnings']))
            self.assertEqual(result['issues'], [])
            self.assertEqual(payload_budget.main(root), 0)

    def test_hosted_budget_runs_after_build_and_before_upload(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml').read_text()
        self.assertLess(workflow.index('python scripts/build_site.py'), workflow.index('python scripts/payload_budget.py'))
        self.assertLess(workflow.index('python scripts/payload_budget.py'), workflow.index('python scripts/feed.py'))
        self.assertLess(workflow.index('python scripts/payload_budget.py'), workflow.index('actions/upload-pages-artifact@'))


if __name__ == '__main__':
    unittest.main()
