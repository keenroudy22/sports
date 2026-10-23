import io
import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, call
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import refresh


class ScoreboardTransportTests(unittest.TestCase):
    def test_tls_alert_recovers_with_bounded_backoff(self):
        error = URLError(ssl.SSLError('TLSV1_ALERT_INTERNAL_ERROR'))
        with patch.object(refresh, 'urlopen', side_effect=[error, error, io.BytesIO(b'{"events": []}')]) as request, patch.object(refresh.time, 'sleep') as sleep:
            self.assertEqual(refresh.scoreboard_json('https://example.test'), {'events': []})
            self.assertEqual(request.call_count, 3)
            self.assertEqual(sleep.call_args_list, [call(1), call(2)])
            request.assert_called_with('https://example.test', timeout=45)

    def test_exhausted_transport_still_fails(self):
        with patch.object(refresh, 'urlopen', side_effect=URLError('unavailable')) as request, patch.object(refresh.time, 'sleep'):
            with self.assertRaises(URLError):
                refresh.scoreboard_json('https://example.test')
            self.assertEqual(request.call_count, 3)

    def test_certificate_failure_is_not_retried(self):
        with patch.object(refresh, 'urlopen', side_effect=URLError(ssl.SSLCertVerificationError('bad certificate'))), patch.object(refresh.time, 'sleep') as sleep:
            with self.assertRaises(URLError):
                refresh.scoreboard_json('https://example.test')
            sleep.assert_not_called()

    def test_bad_request_preserves_existing_week_fallback(self):
        with patch.object(refresh, 'urlopen', side_effect=HTTPError('https://example.test', 400, 'bad request', {}, None)) as request, patch.object(refresh.time, 'sleep') as sleep:
            with self.assertRaises(HTTPError):
                refresh.scoreboard_json('https://example.test')
            self.assertEqual(request.call_count, 1)
            sleep.assert_not_called()

    def test_server_error_recovers(self):
        error = HTTPError('https://example.test', 503, 'unavailable', {}, io.BytesIO())
        with patch.object(refresh, 'urlopen', side_effect=[error, io.BytesIO(b'{}')]), patch.object(refresh.time, 'sleep'):
            self.assertEqual(refresh.scoreboard_json('https://example.test'), {})
            self.assertTrue(error.fp.closed)

    def test_invalid_json_is_not_hidden_by_retry(self):
        with patch.object(refresh, 'urlopen', return_value=io.BytesIO(b'invalid')), patch.object(refresh.time, 'sleep') as sleep:
            with self.assertRaises(ValueError):
                refresh.scoreboard_json('https://example.test')
            sleep.assert_not_called()

    def test_prior_season_validation_still_rejects_incomplete_feed(self):
        with patch.object(refresh, 'scoreboard_json', return_value={'events': []}):
            with self.assertRaisesRegex(ValueError, 'incomplete prior-season'):
                refresh.prior_season('NFL', 2025)
