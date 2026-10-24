import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_checks
import run


class ReleaseChecksTests(unittest.TestCase):
    def test_required_tests_cannot_silently_disappear(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, 'Missing mandatory'):
                release_checks.suite(folder)

    def test_runtime_is_bounded_and_runs_both_checks(self):
        ok = SimpleNamespace(returncode=0, stdout='', stderr='')
        with patch.object(run.subprocess, 'run', return_value=ok) as call:
            run.run_tests()
        self.assertEqual(call.call_count, 2)
        self.assertIn('scripts/release_checks.py', call.call_args_list[0].args[0])
        self.assertEqual([c.kwargs['timeout'] for c in call.call_args_list], [120,60])

    def test_failure_or_timeout_never_allows_release(self):
        for failure in (SimpleNamespace(returncode=1, stdout='', stderr='failure'),
                        subprocess.TimeoutExpired('release checks', 120)):
            with self.subTest(failure=str(failure)):
                kwargs = {'side_effect':failure} if isinstance(failure, Exception) else {'return_value':failure}
                with patch.object(run.subprocess, 'run', **kwargs), self.assertRaises(run.RunError):
                    run.run_tests()
