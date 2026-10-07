import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LessonTests(unittest.TestCase):
    def test_guarded_lessons_name_real_deterministic_tests(self):
        text = (ROOT / 'docs/LESSONS.md').read_text()
        entries = re.split(r'(?=^### L-)', text, flags=re.M)[1:]
        self.assertTrue(entries)
        ids = [entry.split(' · ', 1)[0].strip() for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in entries:
            for field in ('What:', 'Why', 'Guard:', 'State:'):
                self.assertIn(field, entry)
            if re.search(r'State: guarded\.', entry):
                names = re.findall(r'test_[a-z_]+', entry)
                self.assertTrue(names)
                known = set()
                for file in (ROOT / 'tests').glob('test_*.py'):
                    known.update(node.name for node in ast.walk(ast.parse(file.read_text())) if isinstance(node, ast.FunctionDef))
                self.assertTrue(any(name in known for name in names), entry.splitlines()[0])


if __name__ == '__main__':
    unittest.main()
