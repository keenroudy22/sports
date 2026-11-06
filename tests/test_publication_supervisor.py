import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publication_supervisor as P


NOW = datetime(2026, 11, 6, 18, 30, tzinfo=timezone.utc)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class PublicationSupervisorTests(unittest.TestCase):
    def payload(self, generated, odds=114):
        return {'generatedAt': generated, 'picks': [{
            'id': 'play', 'displayTitle': 'South Florida MONEYLINE', 'line': 0,
            'odds': odds, 'book': 'DraftKings', 'status': 'active', 'riskUnits': 1,
            'kickoff': '2026-11-07T00:30:00Z', 'expiresAt': '2026-11-06T16:45:00Z',
            'entryNote': None, 'posted': True, 'result': None}]}

    def opener(self, value):
        return lambda *_args, **_kwargs: Response(json.dumps(value).encode())

    def root(self, folder, payload):
        root = Path(folder)
        path = root / 'site/data/app/today.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload))
        return root

    def test_exact_current_terms_are_healthy(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = self.payload('2026-11-06T17:30:00Z')
            def hosted(request, **_kwargs):
                self.assertEqual(request.get_header('User-agent'), 'KooknSports/1.0')
                return Response(json.dumps(payload).encode())
            result = P.inspect(self.root(folder, payload), NOW, hosted)
            self.assertEqual(result['state'], 'healthy')

    def test_a_newer_local_card_gets_deployment_grace_before_repair(self):
        with tempfile.TemporaryDirectory() as folder:
            local = self.payload('2026-11-06T18:25:00Z')
            remote = self.payload('2026-11-06T17:30:00Z', odds=110)
            result = P.inspect(self.root(folder, local), NOW, self.opener(remote))
            self.assertEqual(result['state'], 'deploying')

    def test_an_old_exact_term_mismatch_dispatches_only_twice_per_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            local = self.payload('2026-11-06T17:30:00Z')
            remote = self.payload('2026-11-06T16:00:00Z', odds=110)
            root, conf, calls = self.root(folder, local), Path(folder) / 'private', []
            run = lambda args, **_kwargs: calls.append(args) or subprocess.CompletedProcess(args, 0, '', '')
            head = lambda *_args, **_kwargs: 'abc123\n'
            first = P.supervise(root, conf, NOW, self.opener(remote), run, head)
            waiting = P.supervise(root, conf, NOW + timedelta(minutes=30), self.opener(remote), run, head)
            second = P.supervise(root, conf, NOW + timedelta(minutes=46), self.opener(remote), run, head)
            exhausted = P.supervise(root, conf, NOW + timedelta(minutes=92), self.opener(remote), run, head)
            self.assertEqual([first['state'], waiting['state'], second['state'], exhausted['state']],
                             ['repair-dispatched', 'repair-waiting', 'repair-dispatched', 'repair-exhausted'])
            self.assertEqual(len(calls), 2)
            self.assertIn('publish_only=true', calls[0])

    def test_a_host_outage_or_stale_local_source_never_republishes(self):
        with tempfile.TemporaryDirectory() as folder:
            local = self.payload('2026-11-06T12:00:00Z')
            root, conf, calls = self.root(folder, local), Path(folder) / 'private', []
            failed = P.supervise(root, conf, NOW, lambda *_a, **_k: (_ for _ in ()).throw(OSError()),
                                 lambda *a, **k: calls.append(a), lambda *_a, **_k: 'abc')
            stale = P.supervise(root, conf, NOW, self.opener(local),
                                lambda *a, **k: calls.append(a), lambda *_a, **_k: 'abc')
            self.assertEqual((failed['state'], stale['state']), ('host-unreachable', 'source-stale'))
            self.assertEqual(calls, [])

    def test_operator_notifications_are_change_only_and_report_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = self.payload('2026-11-06T17:30:00Z')
            root, conf = self.root(folder, payload), Path(folder) / 'private'
            outage = lambda *_a, **_k: (_ for _ in ()).throw(OSError())
            first = P.supervise(root, conf, NOW, outage)
            repeated = P.supervise(root, conf, NOW + timedelta(minutes=30), outage)
            recovered = P.supervise(root, conf, NOW + timedelta(minutes=60), self.opener(payload))
            quiet = P.supervise(root, conf, NOW + timedelta(minutes=90), self.opener(payload))
            self.assertEqual([first['notify'], repeated['notify'], recovered['notify'], quiet['notify']],
                             [True, False, True, False])
            self.assertIn('matches production again', recovered['issue'])


if __name__ == '__main__':
    unittest.main()
