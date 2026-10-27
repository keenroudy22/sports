import fcntl
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import deploy
import deployment_lock


class ReleaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prod = self.root/'prod'
        self.dev = self.root/'dev'
        self.prod.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Release fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.commit(self.prod, 'base', 'base')
        self.git('worktree', 'add', '-q', '-b', 'dev', str(self.dev))
        self.commit(self.dev, 'code', 'tested code')
        self.verified = []
        self.promoted = []

    def git(self, *args, cwd=None):
        return subprocess.check_output(['git', *args], cwd=cwd or self.prod,
                                       stderr=subprocess.STDOUT, text=True).strip()

    def commit(self, path, name, value):
        (path/name).write_text(value)
        self.git('add', name, cwd=path)
        self.git('commit', '-qm', value, cwd=path)

    def sync(self, prod, dev):
        self.git('rebase', deployment_lock.head(prod), cwd=dev)

    def verify(self, dev):
        # This is a real independent descriptor: full verification must allow
        # the scheduled publisher to acquire the posting lock.
        with (self.root/'run.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.verified.append(deployment_lock.head(dev))

    def promote(self, prod, sha):
        self.assertEqual(sha, self.verified[-1])
        self.git('merge', '--ff-only', sha)
        self.promoted.append(sha)

    def release(self, **kwargs):
        return deploy.release(self.prod, self.dev, self.root, synchronize=self.sync,
                              verify=kwargs.pop('verify', self.verify),
                              promote=kwargs.pop('promote', self.promote), **kwargs)

    def test_exact_tested_commit_promotes_with_suites_outside_lock(self):
        result = self.release()
        self.assertEqual(result['state'], 'pushed-needs-hosted-live')
        self.assertEqual(self.promoted, self.verified)
        self.assertEqual(deployment_lock.head(self.prod), result['testedCandidate'])

    def test_production_writer_during_checks_survives_and_repeats_every_gate(self):
        def check(dev):
            self.verify(dev)
            if len(self.verified) == 1:
                self.commit(self.prod, 'capture', 'official final')
        result = self.release(verify=check)
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(len(self.verified), 2)
        self.assertNotEqual(*self.verified)
        self.assertEqual((self.prod/'capture').read_text(), 'official final')
        self.assertEqual((self.prod/'code').read_text(), 'tested code')

    def test_candidate_writer_requires_reverification(self):
        def check(dev):
            self.verify(dev)
            if len(self.verified) == 1:
                self.commit(self.dev, 'more-code', 'new source')
        result = self.release(verify=check)
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(self.promoted, self.verified[-1:])

    def test_failed_gate_preserves_candidate_and_never_promotes(self):
        before = deployment_lock.head(self.prod)
        candidate = deployment_lock.head(self.dev)
        def fail(dev):
            raise subprocess.CalledProcessError(1, ['test'])
        with self.assertRaises(subprocess.CalledProcessError):
            self.release(verify=fail)
        self.assertEqual(deployment_lock.head(self.prod), before)
        self.assertEqual(deployment_lock.head(self.dev), candidate)
        self.assertEqual(self.promoted, [])

    def test_rejected_push_preserves_merge_and_rechecks(self):
        def push(prod, sha):
            self.promote(prod, sha)
            if len(self.promoted) == 1:
                raise subprocess.CalledProcessError(1, ['git', 'push', 'origin', 'main'])
        result = self.release(promote=push)
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(len(self.verified), 2)

    def test_three_races_stop_without_promotion(self):
        before = deployment_lock.head(self.prod)
        def check(dev):
            self.verify(dev)
            self.commit(self.dev, 'moving-code', str(len(self.verified)))
        with self.assertRaisesRegex(RuntimeError, 'Three release races'):
            self.release(verify=check)
        self.assertEqual(deployment_lock.head(self.prod), before)
        self.assertEqual(self.promoted, [])

    def test_uncommitted_changes_stop_without_discarding(self):
        (self.dev/'code').write_text('owner work')
        with self.assertRaisesRegex(RuntimeError, 'dirty'):
            self.release()
        self.assertEqual((self.dev/'code').read_text(), 'owner work')
        self.assertEqual(self.verified, [])


class GateAndLockTests(unittest.TestCase):
    def test_occupied_lock_times_out_without_stealing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'lock'
            with path.open('a') as owner:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(TimeoutError):
                    with deployment_lock.bounded_lock(path, timeout=1,
                            clock=iter([0, 0, 2]).__next__, sleep=lambda _: None):
                        self.fail('stole occupied lock')
                with path.open('a') as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_gate_plan_keeps_full_clean_build_record_and_boundary_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'tests').mkdir()
            (root/'tests/frontend.test.js').touch()
            with patch.object(deploy, 'command') as execute, patch.object(deploy, 'clean'):
                deploy.verify(root)
            commands = [call.args[0] for call in execute.call_args_list]
            self.assertIn([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], commands)
            self.assertIn(['node', '--test', 'tests/frontend.test.js'], commands)
            for name in ('clean_export_tests', 'materialize_research', 'build_site', 'feed',
                         'payload_budget', 'nba_trial_audit', 'publication_guard'):
                self.assertIn([sys.executable, f'scripts/{name}.py'], commands)
            self.assertIn([sys.executable, 'scripts/record_audit.py', '--today', 'site/data/app/record.json'], commands)
            self.assertIn([sys.executable, 'scripts/asset_versions.py', '--check'], commands)

    def test_actual_midnight_uses_previous_real_settlement_slot(self):
        self.assertEqual(deploy.rehearsal_slot(datetime(2026, 10, 27, 4, 10, tzinfo=timezone.utc)), '2355')
        self.assertEqual(deploy.rehearsal_slot(datetime(2026, 10, 27, 4, 45, tzinfo=timezone.utc)), '0025')
