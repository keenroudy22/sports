import io
import json
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import quota


class Response(io.StringIO):
    def __init__(self, headers):
        super().__init__('[]')
        self.headers = headers


class QuotaTests(unittest.TestCase):
    def test_observed_buffer_usage_preserves_journal_and_counts_new_attempts(self):
        now=datetime(2026,11,8,15,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'buffer.jsonl'
            old=''.join(json.dumps(dict(provider='buffer',count=1,month='2026-11',at=now.isoformat()))+'\n' for _ in range(2900))
            path.write_text(old)
            quota.observe_buffer_usage(629,1000,root=root,now=now)
            self.assertEqual(path.read_text(),old)
            quota.count_request('buffer',root,now,essential=True)
            rows=[json.loads(l) for l in path.read_text().splitlines()]
            self.assertEqual(quota.observed_buffer_usage(root,rows,now),630)
            self.assertEqual(len(rows),2901)
            with mock.patch.dict(quota.os.environ, {'BUFFER_TOKEN':'different-account-key'}):
                with self.assertRaisesRegex(quota.QuotaBlocked,'observation needs review'):
                    quota.count_request('buffer',root,now)
            path.write_text(path.read_text().replace('"month": "2026-11"','"month": "2026-10"',1))
            with self.assertRaisesRegex(quota.QuotaBlocked,'observation needs review'):
                quota.count_request('buffer',root,now)

    def test_observed_buffer_reserve_survives_month_rollover_and_expiry_holds(self):
        now=datetime(2026,11,30,15,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as root:
            quota.observe_buffer_usage(948,1000,root=root,now=now)
            with self.assertRaises(quota.QuotaBlocked):quota.count_request('buffer',root,now)
            quota.count_request('buffer',root,now,essential=True)
            quota.count_request('buffer',root,now+timedelta(days=1),essential=True)
            with self.assertRaises(quota.QuotaBlocked):quota.count_request('buffer',root,now+timedelta(days=1),essential=True)
            with self.assertRaisesRegex(quota.QuotaBlocked,'observation needs review'):
                quota.count_request('buffer',root,now+timedelta(days=31),essential=True)
            with self.assertRaisesRegex(quota.QuotaBlocked,'observation needs review'):
                quota.count_request('buffer',root,now-timedelta(seconds=1),essential=True)

    def test_protected_delivery_lane_is_bounded_and_delivery_only(self):
        now = quota.BUFFER_TEMP_END + timedelta(days=1)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'buffer.jsonl'
            row = json.dumps(dict(at=now.isoformat(), month='2026-10', provider='buffer', count=1)) + '\n'
            path.write_text(row * quota.BUFFER_STOP)
            original = path.read_bytes()
            for kwargs in ({'operation': 'publish'}, {'optional': True}, {'operation': 'analytics'}):
                with self.assertRaises(quota.QuotaBlocked):
                    quota.count_request('buffer', root, now, **kwargs)
            self.assertEqual(path.read_bytes(), original)
            quota.count_request('buffer', root, now, operation='publish', essential=True)
            self.assertTrue(json.loads(path.read_text().splitlines()[-1])['essentialDelivery'])
            quota.count_request('buffer', root, now, operation='status')
            path.write_text(row * quota.BUFFER_ESSENTIAL_STOP)
            with self.assertRaises(quota.QuotaBlocked):
                quota.count_request('buffer', root, now, operation='publish', essential=True)
            path.write_text(row * quota.BUFFER_STOP)
            quota.count_request('buffer', root, now, essential=True)

    def test_daily_analytics_ceiling_preserves_delivery_and_next_day(self):
        now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as root:
            for _ in range(quota.BUFFER_ANALYTICS_PER_DAY):
                quota.count_request('buffer', root, now, optional=True)
            journal = Path(root) / 'buffer.jsonl'
            original = journal.read_bytes()
            with self.assertRaisesRegex(quota.QuotaBlocked, 'daily analytics'):
                quota.count_request('buffer', root, now, optional=True)
            self.assertEqual(journal.read_bytes(), original)
            quota.count_request('buffer', root, now, operation='publish')
            quota.count_request('buffer', root, now + timedelta(days=1), optional=True)
            self.assertEqual(len(journal.read_text().splitlines()), quota.BUFFER_ANALYTICS_PER_DAY + 2)

    def test_preflight_does_not_spend_and_keeps_historical_journal(self):
        now = datetime(2026, 10, 26, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(quota.buffer_block_reason(root, now))
            path = Path(root) / 'buffer.jsonl'
            self.assertFalse(path.exists())
            quota.count_request('buffer', root, now, operation='status')
            original = path.read_bytes()
            self.assertIsNone(quota.buffer_block_reason(root, now))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(json.loads(original)['operation'], 'status')
            path.write_bytes(original * quota.BUFFER_STOP)
            original = path.read_bytes()
            self.assertIn('cap reached', quota.buffer_block_reason(root, now))
            self.assertEqual(path.read_bytes(), original)
            path.write_text('broken journal')
            self.assertIn('unavailable', quota.buffer_block_reason(root, now))

    def test_buffer_rolling_window_and_delivery_reserve(self):
        now=datetime(2026,12,1,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as root:
            journal=Path(root)/'buffer.jsonl'
            previous=now-timedelta(days=1)
            row=json.dumps(dict(at=previous.isoformat(),month='2026-11',provider='buffer',count=1))+'\n'
            journal.write_text(row*(quota.BUFFER_STOP-quota.BUFFER_DELIVERY_RESERVE))
            with self.assertRaisesRegex(quota.QuotaBlocked,'delivery reserve'):
                quota.count_request('buffer',root,now,optional=True)
            quota.count_request('buffer',root,now)
            journal.write_text(row*quota.BUFFER_STOP)
            with self.assertRaisesRegex(quota.QuotaBlocked,'rolling 30-day'):
                quota.count_request('buffer',root,now)
            quota.count_request('buffer',root,now+timedelta(days=30))

    def test_month_rollover_discards_old_reserve_and_counters_store_counts_only(self):
        now = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.assertEqual(quota.current_month_usage({'at': '2026-10-31T23:00:00Z', 'remaining': 24}, now), {})
        self.assertEqual(quota.current_month_usage({'at': now.isoformat(), 'remaining': 24}, now)['remaining'], 24)
        with tempfile.TemporaryDirectory() as root:
            quota.count_request('sharp', root, now)
            quota.count_request('buffer', root, now)
            self.assertEqual(quota.monthly_counts(root, now), {'sharp': 1, 'buffer': 1})
            row = json.loads((Path(root) / 'sharp.jsonl').read_text())
            self.assertEqual(set(row), {'at', 'month', 'provider', 'count'})

    def test_buffer_and_sharp_requests_stop_before_free_limits(self):
        now = datetime(2026, 10, 7, 16, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as root:
            journal = Path(root) / 'buffer.jsonl'
            journal.write_text(''.join(json.dumps({'at': now.isoformat(), 'month': '2026-10',
                             'provider': 'buffer', 'count': 1}) + '\n' for _ in range(quota.BUFFER_STOP)))
            with self.assertRaisesRegex(quota.QuotaBlocked, 'Buffer local free-plan'):
                quota.count_request('buffer', root, now)
            self.assertEqual(len(journal.read_text().splitlines()), quota.BUFFER_STOP)
            for minute in range(quota.SHARP_PER_MINUTE):
                quota.count_request('sharp', root, now)
            with self.assertRaisesRegex(quota.QuotaBlocked, '12-per-minute'):
                quota.count_request('sharp', root, now)
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
