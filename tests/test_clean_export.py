import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clean_export_tests


class CleanExportTests(unittest.TestCase):
    def test_export_contains_current_sources_but_no_built_app_payloads(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = clean_export_tests.export(ROOT, Path(folder))
            self.assertTrue((destination / 'site/app.js').is_file())
            self.assertTrue((destination / 'tests/test_run.py').is_file())
            self.assertFalse((destination / 'site/data/app').exists())

    def test_agents_requires_the_clean_export_gate(self):
        instructions = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertGreaterEqual(instructions.count('scripts/clean_export_tests.py'), 2)


if __name__ == '__main__':
    unittest.main()
