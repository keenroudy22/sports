import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import quota


class Response(io.StringIO):
    def __init__(self, headers):
        super().__init__('[]')
        self.headers = headers


class QuotaTests(unittest.TestCase):
    def test_failed_metered_call_keeps_reservation(self):
        with tempfile.TemporaryDirectory() as root:
            def opener(request, **kwargs):
                if '/sports/' in request:
                    return Response({'x-requests-used': '100', 'x-requests-remaining': '400'})
                raise OSError('request with secret URL failed')
            with self.assertRaisesRegex(quota.QuotaBlocked, 'reservation retained'):
                quota.guarded_json('https://api.the-odds-api.com/v4/x/odds?apiKey=SECRET',
                                   2, opener=opener, root=root)
            self.assertEqual(json.loads((Path(root) / 'odds.jsonl').read_text())['reservedThrough'], 102)

    def test_unknown_paid_or_exhausted_plan_never_sends_metered_request(self):
        for headers in ({}, {'x-requests-used': '0', 'x-requests-remaining': '20000'},
                        {'x-requests-used': '475', 'x-requests-remaining': '25'}):
            calls = []
            with tempfile.TemporaryDirectory() as root:
                def opener(request, **kwargs):
                    calls.append(request)
                    return Response(headers)
                with self.assertRaises(quota.QuotaBlocked):
                    quota.guarded_json('https://api.the-odds-api.com/v4/x/odds?apiKey=SECRET',
                                       2, opener=opener, root=root)
                self.assertEqual(len(calls), 1)

    def test_reservations_survive_lagging_counters_and_do_not_store_keys(self):
        calls = []
        with tempfile.TemporaryDirectory() as root:
            def opener(request, **kwargs):
                calls.append(request)
                return Response({'x-requests-used': '472', 'x-requests-remaining': '28'})
            for _ in range(2):
                quota.guarded_json('https://api.the-odds-api.com/v4/x/odds?apiKey=SECRET',
                                   2, opener=opener, root=root)
            with self.assertRaises(quota.QuotaBlocked):
                quota.guarded_json('https://api.the-odds-api.com/v4/x/odds?apiKey=SECRET',
                                   2, opener=opener, root=root)
            self.assertEqual(len(calls), 5)
            journal = (Path(root) / 'odds.jsonl').read_text()
            self.assertNotIn('SECRET', journal)
            self.assertEqual(json.loads(journal.splitlines()[-1])['reservedThrough'], 476)

    def test_bad_journal_and_failed_probe_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'odds.jsonl').write_text('bad')
            with self.assertRaises(quota.QuotaBlocked):
                quota.guarded_json('https://api.the-odds-api.com/v4/x/odds?apiKey=SECRET',
                                   2, opener=lambda *a, **k: self.fail('must not request'), root=root)
