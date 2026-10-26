import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_web as web
import buffer_post as bp


class WebReceiptTests(unittest.TestCase):
    now = datetime(2026, 10, 26, 13, tzinfo=timezone.utc)

    def reserve(self, book, kind='receipt', text='Sunday: 2-3. -0.5u.\n\n21+ only'):
        plan = [('receipt:day:2026-10-25', kind, text, self.now+timedelta(minutes=3), None)]
        with patch.object(bp, 'rate_backoff', return_value=None), \
                patch.object(bp, 'plan', return_value=plan), \
                patch.object(bp, 'http_send') as network:
            result = web.reserve_receipt(plan[0][0], {}, {}, {}, book, self.now)
            network.assert_not_called()
            return result

    def test_reservation_is_not_acceptance_and_stays_deduplicated(self):
        book = {'posts': []}
        entry = self.reserve(book)
        self.assertNotIn('bufferPostId', entry)
        self.assertNotIn('sentAt', entry)
        self.assertEqual(entry['webDelivery']['state'], 'reserved')
        original = copy.deepcopy(book)
        with self.assertRaises(web.WebHold):
            self.reserve(book)
        self.assertEqual(book, original)

    def test_pregame_money_and_failed_captions_never_reserve(self):
        for kind, text in [('play', 'A bet'), ('receipt', '$50 payout'), ('receipt', 'early estimate')]:
            book = {'posts': []}
            with self.assertRaises(web.WebHold):
                self.reserve(book, kind, text)
            self.assertEqual(book['posts'], [])

    def test_provider_backoff_is_not_evaded(self):
        with patch.object(bp, 'rate_backoff', return_value=True), patch.object(bp, 'plan') as plan:
            with self.assertRaises(web.WebHold):
                web.reserve_receipt('x', {}, {}, {}, {}, self.now)
            plan.assert_not_called()

    def test_only_matching_observed_sent_receipt_can_complete(self):
        entry = self.reserve({'posts': []})
        kwargs = dict(observed_text=entry['queuedText'], link='https://x.com/keenkooks/status/123',
                      sent_at=bp.stamp(self.now+timedelta(minutes=3)), now=self.now+timedelta(minutes=4))
        for key, value in [('observed_text', 'wrong'), ('link', 'https://x.com/home'),
                           ('sent_at', bp.stamp(self.now-timedelta(seconds=1)))]:
            changed = dict(kwargs, **{key: value})
            with self.assertRaises(web.WebHold):
                web.confirm_sent(entry, **changed)
            self.assertNotIn('sentAt', entry)
        web.confirm_sent(entry, **kwargs)
        self.assertEqual(entry['tweetId'], '123')
        self.assertEqual(entry['webDelivery']['state'], 'sent')
        with self.assertRaises(web.WebHold):
            web.confirm_sent(entry, **kwargs)

    def test_observed_queue_is_not_a_sent_post(self):
        entry = self.reserve({'posts': []})
        with self.assertRaises(web.WebHold):
            web.confirm_scheduled(entry, observed_text=entry['queuedText'],
                                  due_at=bp.stamp(self.now+timedelta(minutes=4)), now=self.now)
        self.assertEqual(entry['webDelivery']['state'], 'reserved')
        web.confirm_scheduled(entry, observed_text=entry['queuedText'], due_at=entry['dueAt'], now=self.now)
        self.assertEqual(entry['webDelivery']['state'], 'scheduled')
        self.assertNotIn('sentAt', entry)

    def test_web_sent_receipt_does_not_enter_api_metrics_without_provider_id(self):
        entry = self.reserve({'posts': []})
        web.confirm_sent(entry, observed_text=entry['queuedText'],
                         link='https://x.com/keenkooks/status/123',
                         sent_at=bp.stamp(self.now), now=self.now)
        with patch.object(bp, 'graphql') as api:
            self.assertEqual(bp.collect_metrics({'posts': [entry]}, self.now+timedelta(days=1)), 0)
            api.assert_not_called()
