import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import run
import typefully_backup
import x_post


class BasketballBackupTests(unittest.TestCase):
    now = datetime(2026, 11, 13, 18, tzinfo=timezone.utc)

    def test_both_routes_require_confirmed_discord_and_no_other_x_attempt(self):
        for kind in ('buffer:nba-trial', 'buffer:cbb-pick'):
            entry = dict(kind=kind, dueAt='2026-11-13T17:59:00Z',
                         discord=dict(state='sent', sentAt='2026-11-13T17:40:00Z'))
            self.assertTrue(run.basketball_backup_due(entry, self.now))
            for key in ('bufferAttemptAt', 'bufferPostId', 'webDelivery', 'sentAt'):
                self.assertFalse(run.basketball_backup_due(dict(entry, **{key: True}), self.now))
            self.assertFalse(run.basketball_backup_due(dict(entry, discord={'state': 'queued'}), self.now))
            self.assertTrue(run.basketball_backup_due(
                dict(entry, typefullyDelivery={'at': '2026-11-13T17:50:00Z'}), self.now))

    def test_timeout_does_not_create_second_draft(self):
        entry = {'id': 'pick'}
        book = {'posts': [entry]}
        with patch.object(typefully_backup, 'request', side_effect=TimeoutError) as request:
            kwargs = dict(text='Original', expires=self.now + timedelta(minutes=30))
            with self.assertRaises(TimeoutError):
                typefully_backup.deliver(entry, book, {}, self.now, lambda _: None, **kwargs)
            self.assertFalse(typefully_backup.deliver(entry, book, {}, self.now, lambda _: None, **kwargs))
            self.assertEqual(request.call_count, 1)

    def test_media_is_ready_and_attached_before_draft_creation(self):
        entry = {'id': 'pick', 'queuedText': 'Original'}
        book = {'posts': [entry]}
        published = {'id': 7, 'status': 'published',
                     'x_post_published_at': '2026-11-13T18:00:00Z',
                     'x_published_url': 'https://x.com/keenkooks/status/2123456789012345678'}
        with patch.object(typefully_backup, 'upload_media', return_value='media-1'), \
             patch.object(typefully_backup, 'media_request', return_value={'status': 'ready'}), \
             patch.object(typefully_backup, 'request', return_value=published) as request:
            self.assertTrue(typefully_backup.deliver(
                entry, book, {}, self.now, lambda _: None,
                expires=self.now + timedelta(minutes=30),
                media_url='https://keenroudy.com/sports/data/cards/pick.png'))
        post = request.call_args.kwargs['payload']['platforms']['x']['posts'][0]
        self.assertEqual(post, {'text': 'Original', 'media_ids': ['media-1']})

    def test_processing_media_retries_without_creating_a_second_post(self):
        entry = {'id': 'pick', 'queuedText': 'Original'}
        book = {'posts': [entry]}
        published = {'id': 8, 'status': 'published',
                     'x_post_published_at': '2026-11-13T18:01:00Z',
                     'x_published_url': 'https://twitter.com/keenkooks/status/2123456789012345679'}
        with patch.object(typefully_backup, 'upload_media', return_value='media-2') as upload, \
             patch.object(typefully_backup, 'media_request', side_effect=[
                 {'status': 'processing'}, {'status': 'ready'}]), \
             patch.object(typefully_backup, 'request', return_value=published) as request:
            kwargs = dict(expires=self.now + timedelta(minutes=30),
                          media_url='https://keenroudy.com/sports/data/cards/pick.png')
            self.assertFalse(typefully_backup.deliver(
                entry, book, {}, self.now, lambda _: None, **kwargs))
            self.assertTrue(typefully_backup.deliver(
                entry, book, {}, self.now + timedelta(seconds=10), lambda _: None, **kwargs))
        self.assertEqual(upload.call_count, 1)
        self.assertEqual(request.call_count, 1)

    def test_attended_x_receipt_requires_owned_exact_observation(self):
        entry = {
            'id': 'receipt:day:2026-11-13',
            'queuedText': 'Friday: 1-2.',
            'textHash': x_post.text_hash('Friday: 1-2.'),
            'typefullyDelivery': {'at': '2026-11-13T17:55:00Z'},
        }
        observed = self.now - timedelta(minutes=1)
        link = 'https://x.com/keenkooks/status/2123456789012345680'
        typefully_backup.confirm_attended_sent(
            entry, observed_text='Friday: 1-2.', link=link,
            sent_at=observed, now=self.now)
        self.assertEqual(entry['link'], link)
        self.assertEqual(entry['tweetId'], '2123456789012345680')
        self.assertEqual(entry['typefullyDelivery']['state'], 'sent')
        self.assertEqual(entry['typefullyDelivery']['evidence'], 'X Composer UI')
        with self.assertRaises(ValueError):
            typefully_backup.confirm_attended_sent(
                entry, observed_text='Friday: 1-2.', link=link,
                sent_at=observed, now=self.now)

    def test_attended_x_receipt_rejects_caption_or_account_mismatch(self):
        base = {
            'id': 'receipt:day:2026-11-13',
            'textHash': x_post.text_hash('Friday: 1-2.'),
            'typefullyDelivery': {'at': '2026-11-13T17:55:00Z'},
        }
        observed = self.now - timedelta(minutes=1)
        with self.assertRaises(ValueError):
            typefully_backup.confirm_attended_sent(
                dict(base), observed_text='Friday: 2-1.',
                link='https://x.com/keenkooks/status/2123456789012345681',
                sent_at=observed, now=self.now)
        with self.assertRaises(ValueError):
            typefully_backup.confirm_attended_sent(
                dict(base), observed_text='Friday: 1-2.',
                link='https://x.com/notkookn/status/2123456789012345681',
                sent_at=observed, now=self.now)

    def test_settled_prior_day_recap_can_release_before_morning_clock(self):
        now = datetime(2026, 11, 14, 5, 15, tzinfo=timezone.utc)
        recap = {'key': 'receipt:day:2026-11-13', 'card': 'receipt-card',
                 'text': 'Thursday: 3-1.', 'due': datetime(2026, 11, 14, 14, tzinfo=timezone.utc),
                 'stale': datetime(2026, 11, 15, 1, tzinfo=timezone.utc)}
        book = {'posts': []}
        stores = SimpleNamespace(first={}, latest={})
        with patch.object(run.gates, 'Stores', return_value=SimpleNamespace(as_of=lambda _now: stores)), \
             patch.object(run, 'load_json', return_value={'games': []}), \
             patch('receipts.ready', return_value=[recap]), \
             patch('x_post.save_log'), \
             patch('buffer_post.card_url', return_value='https://keenroudy.com/card.png'), \
             patch.object(typefully_backup, 'deliver', return_value=False) as deliver:
            run.retry_typefully_recap(now, book, {})
        self.assertEqual(book['posts'][0]['discord']['readyAt'], '2026-11-14T05:15:00Z')
        self.assertEqual(deliver.call_args.kwargs['media_url'], 'https://keenroudy.com/card.png')

    def test_owned_recap_with_incorrect_record_is_reconciled_before_draft(self):
        now = datetime(2026, 11, 14, 8, tzinfo=timezone.utc)
        key = 'receipt:day:2026-11-13'
        entry = {'id': key, 'kind': 'buffer:receipt', 'discordRecapPrepared': True,
                 'fullDailyRecap': True, 'cardKey': 'receipt-card',
                 'queuedText': 'Friday: 1-2.\n✅ Cedric Coward OVER 6.5 rebounds · Final: 7 rebounds\n\n21+ only',
                 'discord': {'state': 'sent', 'sentAt': '2026-11-14T07:33:07Z'},
                 'typefullyDelivery': {'at': '2026-11-14T07:33:07Z'}}
        recap = {'key': key, 'card': 'receipt-card', 'text': 'Friday: 0-2.\n❌ Sengun OVER 6.5 assists · Final: 5 assists',
                 'pickIds': ['sengun'],
                 'stale': now + timedelta(hours=5)}
        book = {'posts': [entry]}
        stores = SimpleNamespace(first={}, latest={})
        with patch.object(run.gates, 'Stores', return_value=SimpleNamespace(as_of=lambda _now: stores)), \
             patch.object(run, 'load_json', return_value={'games': []}), \
             patch('receipts.ready', return_value=[recap]), \
             patch('x_post.save_log') as save, \
             patch('buffer_post.card_url', return_value='https://keenroudy.com/card.png'), \
             patch.object(typefully_backup, 'deliver', return_value=False) as deliver:
            run.retry_typefully_recap(now, book, {})
        self.assertEqual(entry['queuedText'], 'Friday: 0-2.\n❌ Sengun OVER 6.5 assists · Final: 5 assists\n\n21+ only')
        self.assertEqual(entry['resultPickIds'], ['sengun'])
        self.assertEqual(entry['discord']['followup']['state'], 'pending')
        self.assertIn('Coward OVER 6.5 rebounds was never posted as an official play',
                      entry['discord']['followup']['text'])
        self.assertEqual(entry['discord']['followup']['image'], 'https://keenroudy.com/card.png')
        self.assertTrue(entry['supersededRecaps'])
        save.assert_called()
        deliver.assert_called_once()

    def test_settled_prior_day_recap_wakes_mirror_before_morning_clock(self):
        now = datetime(2026, 11, 14, 5, 15, tzinfo=timezone.utc)
        recap = {'key': 'receipt:day:2026-11-13',
                 'stale': datetime(2026, 11, 15, 1, tzinfo=timezone.utc)}
        book = {'posts': []}
        stores = SimpleNamespace(first={}, latest={})
        with patch.object(run.gates, 'Stores', return_value=SimpleNamespace(as_of=lambda _now: stores)), \
             patch.object(run, 'load_json', return_value={'games': []}), \
             patch('receipts.ready', return_value=[recap]):
            self.assertTrue(run.typefully_recap_due(now, book))

    def test_incomplete_prior_day_recap_does_not_wake_mirror_early(self):
        now = datetime(2026, 11, 14, 5, 15, tzinfo=timezone.utc)
        book = {'posts': []}
        stores = SimpleNamespace(first={}, latest={})
        with patch.object(run.gates, 'Stores', return_value=SimpleNamespace(as_of=lambda _now: stores)), \
             patch.object(run, 'load_json', return_value={'games': []}), \
             patch('receipts.ready', return_value=[]):
            self.assertFalse(run.typefully_recap_due(now, book))

    def test_private_backup_reserves_six_slots_for_straights_and_recaps(self):
        straight = {'id': 'straight'}
        nba_straight = {'id': 'nba', 'league': 'NBA', 'selectionMethod': 'sourced-nba-primary-prop-v1'}
        cbb_straight = {'id': 'cbb', 'league': 'CBB', 'selectionMethod': 'sourced-cbb-straight-v1'}
        climb = {'id': 'climb', 'parlayType': 'ladder', 'legs': [{'title': 'A'}, {'title': 'B'}]}
        fun = {'id': 'fun', 'parlayType': 'longshot', 'legs': [{'title': 'A'}] * 4}
        unknown = {'id': 'unknown', 'parlayType': 'community', 'legs': [{'title': 'A'}]}
        book = {'posts': []}
        self.assertTrue(run.typefully_private_fallback_eligible(straight, book, self.now))
        self.assertTrue(run.typefully_private_fallback_eligible(nba_straight, book, self.now))
        self.assertTrue(run.typefully_private_fallback_eligible(cbb_straight, book, self.now))
        self.assertTrue(run.typefully_private_fallback_eligible(climb, book, self.now))
        self.assertTrue(run.typefully_private_fallback_eligible(fun, book, self.now))
        self.assertFalse(run.typefully_private_fallback_eligible(unknown, book, self.now))
        book['posts'] = [
            {'typefullyDelivery': {'at': f'2026-11-{day:02d}T18:00:00Z'}}
            for day in range(10, 14)
        ]
        self.assertFalse(run.typefully_private_fallback_eligible(climb, book, self.now))
        self.assertTrue(run.typefully_private_fallback_eligible(straight, book, self.now))
        self.assertFalse(run.typefully_private_fallback_eligible(
            climb, {'posts': [{'typefullyDelivery': {'at': 'not-a-time'}}]}, self.now))
