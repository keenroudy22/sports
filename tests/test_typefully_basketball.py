import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import run
import typefully_backup


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

    def test_timeout_does_not_create_second_draft(self):
        from datetime import timedelta
        entry = {'id': 'pick'}
        book = {'posts': [entry]}
        with patch.object(typefully_backup, 'request', side_effect=TimeoutError) as request:
            kwargs = dict(text='Original', expires=self.now + timedelta(minutes=30))
            with self.assertRaises(TimeoutError):
                typefully_backup.deliver(entry, book, {}, self.now, lambda _: None, **kwargs)
            self.assertFalse(typefully_backup.deliver(entry, book, {}, self.now, lambda _: None, **kwargs))
            self.assertEqual(request.call_count, 1)
