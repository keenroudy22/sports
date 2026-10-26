"""The actual private admission path must publish independently of X discovery."""
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post
import release_queue
import run


class PrivateReleaseBufferHoldTests(unittest.TestCase):
    def test_channel_quota_failure_does_not_preempt_release_or_duplicate_discord(self):
        now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        key = 'NFL-test-release'
        game = dict(id='NFL-game', kickoff='2026-10-27T00:15:00Z', league='NFL')
        pick = dict(id=key, title='Player over 2.5 receptions', odds=-110,
                    book='FanDuel', gameIds=['NFL-game'], lane='best_bet')
        ctx = SimpleNamespace(games={'NFL-game': game}, first={}, latest={}, player_team={}, now=now)
        delivery_book = {'posts': []}
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            (root / 'research').mkdir()
            row = dict(id=key, pick=pick, league='NFL', kind='props', caption='Exact caption',
                       card=str(root / 'card.png'), precheckedAt=run.stamp(now))
            release_queue.save(root, {'plays': [row]})
            patches = [
                ('run.ROOT', root), ('run.CONF', root), ('run.features.load', []),
                ('run.gates.Stores', SimpleNamespace(as_of=lambda _: ctx, reports=[])),
                ('run.live_games', ctx.games), ('run.load_json', {'games': [game]}),
                ('run.normalize_private_stake', lambda r, *_: r),
                ('run.private_release_refusal', None),
                ('run.recover_private_release_artifacts', lambda r, *_: r),
                ('run.post_windows.public_release_open', True),
                ('run.post_windows.target', now), ('run.post_windows.jitter', now-now),
                ('x_post.load_log', delivery_book), ('x_post.save_log', None),
                ('social_copy.x_ticket_copy', 'Exact caption'), ('x_post.guard', []),
                ('run.validate', None), ('social_style.release_issues', []),
                ('run.run_tests', None), ('run.commit_push', {'pushed': True}), ('run.commit_log', None),
                ('buffer_post.yield_optional', 0),
                ('release_queue.archive_card', None), ('discord_post.webhook', 'test-webhook'),
            ]
            for target, value in patches:
                if callable(value):
                    stack.enter_context(mock.patch(target, side_effect=value))
                elif target in ('run.ROOT', 'run.CONF'):
                    stack.enter_context(mock.patch(target, value))
                else:
                    stack.enter_context(mock.patch(target, return_value=value))
            channel = stack.enter_context(mock.patch('buffer_post.x_channel',
                side_effect=buffer_post.BufferError('Buffer local free-plan request cap reached')))
            blocked = stack.enter_context(mock.patch('buffer_post.quota.buffer_block_reason',
                return_value='Buffer local free-plan request cap reached'))
            stack.enter_context(mock.patch('buffer_post.rate_backoff', return_value=None))
            send = stack.enter_context(mock.patch('discord_post.send_message',
                return_value={'id': 'message', 'image': 'https://example.com/card.png'}))
            create = stack.enter_context(mock.patch('buffer_post.create_post', return_value='buffer-id'))
            for _ in range(2):
                self.assertEqual(run.release_private(now, log=lambda *_: None), [])
            saved = release_queue.load(root)['plays'][0]
            self.assertEqual(saved['discordSentAt'], run.stamp(now))
            self.assertTrue((root / saved['publicPath']).is_file())
            self.assertNotIn('bufferPostId', saved)
            send.assert_called_once()
            create.assert_not_called()
            self.assertEqual(channel.call_count, 1, 'already-public X hold must not rediscover the channel')
            self.assertEqual(len(delivery_book['posts']), 1)
            entry = delivery_book['posts'][0]
            self.assertEqual(entry['discord']['state'], 'sent')
            self.assertNotIn('bufferPostId', entry)
            self.assertNotIn('dueAt', entry)
            # Attended review runs the same guards without provider discovery,
            # another Discord send, or another public report.
            checked = run.release_private(now, log=lambda *_: None, review_only=True)
            self.assertEqual([r['id'] for r in checked], [key])
            self.assertEqual(checked[0]['text'], 'Exact caption')
            self.assertEqual(channel.call_count, 1)
            send.assert_called_once()
            create.assert_not_called()
            entry['webDelivery'] = {'state': 'reserved'}
            self.assertEqual(run.release_private(now, log=lambda *_: None), [])
            self.assertEqual(channel.call_count, 1, 'unknown attended attempt blocks API duplicate')
            entry.pop('webDelivery')
            # Actual recovery resumes X only; the already-public play is not sent twice.
            channel.side_effect = None
            channel.return_value = {'id': 'channel'}
            blocked.return_value = None
            self.assertEqual(run.release_private(now, log=lambda *_: None), [key])
            send.assert_called_once()
            create.assert_called_once()
            self.assertEqual(release_queue.load(root)['plays'], [])
            self.assertEqual(len(delivery_book['posts']), 1)
            self.assertEqual(entry['bufferPostId'], 'buffer-id')
            self.assertIn('dueAt', entry)

