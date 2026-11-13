import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import hosted_rebase_verify as verify


class HostedRebaseTests(unittest.TestCase):
    def test_no_rebase_does_not_repeat_work(self):
        self.assertEqual(verify.commands([]), [])

    def test_data_rebase_rebuilds_and_audits_without_new_capture_or_suites(self):
        plan = verify.commands(['research/new.json', 'data/odds/cfb.jsonl'], python='python')
        self.assertEqual(plan[:2], [['python', 'scripts/materialize_research.py'],
                                   ['python', 'scripts/build_site.py']])
        self.assertIn(['python','scripts/record_audit.py','--today','site/data/app/record.json'], plan)
        self.assertEqual(plan[-1], ['python','scripts/publication_guard.py'])
        self.assertFalse(any('unittest' in c or 'scripts/odds_api.py' in c for c in plan))

    def test_source_or_policy_rebase_repeats_suites_before_build(self):
        for path in ('scripts/run.py', 'site/app.js', 'data/policy/nba.json', '.github/workflows/publish.yml'):
            plan=verify.commands([path],python='python',node_tests=['tests/core.test.js'])
            self.assertEqual(plan[:2],[['python','-m','unittest','discover','-s','tests'],['node','--test','tests/core.test.js']])

    def test_failed_revalidation_stops_before_artifact_can_deploy(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def run(command,**kw):
                calls.append(command)
                raise subprocess.CalledProcessError(1,command)
            with self.assertRaises(subprocess.CalledProcessError):
                verify.verify('a'*40,folder,lambda *a,**k:'scripts/run.py\n',run)
            self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):verify.verify('--bad-ref')
