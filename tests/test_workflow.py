"""Every script the hosted workflow runs must exist and load.

The first deploy of the rebuild failed because scripts/review.cjs still required two
front-end files the rebuild had deleted, and no test ran it. These checks read the
workflow itself, so a step can never point at a missing file or a broken import again.
"""
import importlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
WORKFLOW = (ROOT / '.github' / 'workflows' / 'publish.yml').read_text(encoding='utf-8')


class WorkflowTests(unittest.TestCase):
    def test_push_has_a_fast_current_main_publish_lane(self):
        fast = WORKFLOW[WORKFLOW.index('  push-publish:'):WORKFLOW.index('  publish:')]
        self.assertIn("if: github.event_name == 'push' || inputs.publish_only", fast)
        self.assertIn('ref: main', fast)
        for command in ('materialize_research', 'scoreboard', 'market_lines', 'build_site', 'feed'):
            self.assertIn(f'python scripts/{command}.py', fast)
        self.assertIn('python scripts/publication_guard.py', fast)
        self.assertIn('actions/upload-pages-artifact@', fast)
        self.assertIn('actions/deploy-pages@', fast)
        self.assertNotIn('Preserve the public record', fast)
        for capture in ('refresh.py', 'sports_refresh.py', 'odds_api.py', 'prop_odds.py', 'sharp_odds.py'):
            self.assertNotIn(capture, fast)
        self.assertIn("'football-pages-push'", WORKFLOW)
        self.assertIn("'football-pages-refresh'", WORKFLOW)
        self.assertIn('cancel-in-progress: false', WORKFLOW)
        self.assertNotIn('cancel-in-progress: ${{', WORKFLOW)
        self.assertIn('publish_only:', WORKFLOW)
        self.assertIn("if: github.event_name != 'push' && !inputs.publish_only", WORKFLOW)
        self.assertIn("if: github.event_name == 'push' && github.event.before !=", fast)
        self.assertIn('tests.test_publication_supervisor', fast)

    def test_only_the_serialized_current_main_lane_can_publish_pages(self):
        fast, refresh = WORKFLOW.split('  publish:', 1)
        self.assertEqual(WORKFLOW.count('uses: actions/deploy-pages@'), 1)
        self.assertEqual(WORKFLOW.count('uses: actions/upload-pages-artifact@'), 1)
        self.assertIn('pages: write', fast)
        self.assertNotIn('pages: write', refresh)
        self.assertIn('environment: github-pages', refresh)
        self.assertIn('actions: write', refresh)
        self.assertIn('GH_TOKEN: ${{ github.token }}', refresh)
        self.assertIn("(github.event_name == 'push' || inputs.publish_only) && 'football-pages-push'", fast)
        self.assertLess(refresh.index('python scripts/integrity.py --verify-base HEAD'), refresh.index('git push'))
        self.assertLess(refresh.index('[ -n "$pushed" ]'), refresh.index('gh workflow run publish.yml --ref main -f publish_only=true'))
        self.assertNotIn('if:', refresh.split('      - name: Queue Pages publish from committed main', 1)[1])

    def test_ticket_push_does_not_wait_for_new_capture(self):
        capture = ('refresh', 'sports_refresh', 'boxscores', 'research_context',
                   'depth_charts', 'forecast', 'venues', 'weather', 'prop_lines',
                   'odds_api', 'prop_odds', 'sharp_odds')
        for step in WORKFLOW.split('      - name: '):
            if any(re.search(r'run: python scripts/' + name + r'\.py\b', step) for name in capture):
                self.assertIn("if: github.event_name != 'push'", step)
        self.assertIn('python -m unittest discover -s tests', WORKFLOW)
        self.assertIn('python scripts/publication_guard.py', WORKFLOW)

    def test_every_publish_materializes_reports_before_reading_them(self):
        steps = WORKFLOW.split('      - name: ')
        materialize = next(step for step in steps
                           if 'run: python scripts/materialize_research.py' in step)
        self.assertNotIn('if:', materialize)
        index = WORKFLOW.index('run: python scripts/materialize_research.py')
        for consumer in ('scoreboard', 'market_lines', 'build_site', 'feed'):
            self.assertLess(index, WORKFLOW.index(f'run: python scripts/{consumer}.py'))

    def test_every_python_step_exists_and_imports(self):
        scripts = re.findall(r'python scripts/(\w+)\.py', WORKFLOW)
        self.assertIn('build_site', scripts)
        for name in scripts:
            with self.subTest(script=name):
                self.assertTrue((ROOT / 'scripts' / f'{name}.py').is_file())
                importlib.import_module(name)

    def test_every_node_step_and_its_local_requires_exist(self):
        for name in re.findall(r'node (?:--check )?((?:scripts|site)/[\w./-]+\.c?js)', WORKFLOW):
            path = ROOT / name
            with self.subTest(script=name):
                self.assertTrue(path.is_file())
                for target in re.findall(r"require\(['\"](\.{1,2}/[^'\"]+)['\"]\)", path.read_text(encoding='utf-8')):
                    resolved = (path.parent / target).resolve()
                    self.assertTrue(resolved.is_file() or resolved.with_suffix('.js').is_file(), f'{name} requires {target}')

    def test_the_step_that_broke_the_first_deploy_is_gone(self):
        self.assertNotIn('review.cjs', WORKFLOW)

    def test_hosted_frontend_checks_pin_the_launchd_node_major(self):
        self.assertRegex(WORKFLOW, r'uses:\s*actions/setup-node@v\d+')
        self.assertRegex(WORKFLOW, r"node-version:\s*['\"]22['\"]")


if __name__ == '__main__':
    unittest.main()
