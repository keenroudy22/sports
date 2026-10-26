"""An X quota hold never wakes a whole-desk build or blocks official Discord grades."""
import sys
import unittest
from contextlib import ExitStack, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run


class RecoveryHoldTests(unittest.TestCase):
    def test_actual_mirror_branch_delivers_discord_without_rebuild_or_buffer(self):
        now = datetime(2026, 10, 26, 13, tzinfo=timezone.utc)
        args = SimpleNamespace(now=run.stamp(now), dry_run=False, no_push=True)
        book = {'posts': []}
        ctx = SimpleNamespace(first={'won': {}}, latest={'won': {'result': 'win'}})
        with ExitStack() as s:
            s.enter_context(patch.dict(run.os.environ, {'KEENROUDY_LIVE_SHADOW': '0', 'BUFFER_TOKEN': 'test'}))
            for name, value in [('run.result_recovery_needed', 1), ('quota.buffer_block_reason', 'local cap reached'),
                    ('chef_wins.pending', []), ('discord_post.webhook', 'test'),
                    ('run.private_release_ready', False), ('run.sync', None),
                    ('x_post.load_log', book), ('run.load_json', {'games': []}),
                    ('run.commit_log', None), ('discord_post.mirror_sent', []),
                    ('gates.Stores', SimpleNamespace(as_of=lambda _: ctx)),
                    ('run.Lock', nullcontext()), ('run.mirror_due', True)]:
                s.enter_context(patch(name, return_value=value))
            full = s.enter_context(patch('run.run'))
            queued = s.enter_context(patch('discord_post.queue_results'))
            sent = s.enter_context(patch('discord_post.mirror_sent', return_value=[]))
            saved = s.enter_context(patch('x_post.save_log'))
            api = s.enter_context(patch('buffer_post.reconcile', return_value=[]))
            s.enter_context(patch('run.log'))
            self.assertEqual(run.mirror(args), 0)
        full.assert_not_called()
        queued.assert_called_once_with(book, ctx.first, ctx.latest, {}, now)
        sent.assert_called_once()
        self.assertTrue(saved.called)
        api.assert_not_called()
        self.assertEqual(book, {'posts': []})
