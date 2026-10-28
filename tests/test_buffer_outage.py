"""No live calls: Buffer exhaustion must not swallow an eligible Discord receipt."""
import sys
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post
import run


class BufferOutageTests(unittest.TestCase):
    def exercise(self, plans, optional_hold=None, discovery_blocked=True):
        now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        book = {'posts': [{'id': 'released', 'discord': {'state': 'pending'}}]}
        status = {'errors': [], 'x': {}}
        ctx = SimpleNamespace(first={}, latest={}, player_team={})
        def deliver(*args, **kwargs):
            book['posts'][0]['discord'].update(state='sent', messageId='confirmed')
            return []
        with ExitStack() as stack:
            stack.enter_context(patch.dict(run.os.environ, {'BUFFER_TOKEN': 'test'}))
            for target, result in (
                ('x_post.load_log', book), ('buffer_post.reconcile', []),
                ('discord_post.queue_results', 0), ('run.now_quotes', {}),
                ('run.line_payload.load', []), ('run.features.load', {}),
                ('news_posts.candidates', []), ('buffer_post.plan', plans),
                ('nba_trial_runtime.social_plans', []), ('run.pending_ladder_result_cards', {}),
                ('buffer_post.chosen_not_posted', []), ('run.ladder_schedule_pings', []),
                ('run.lotto_pings', []), ('run.feature_scheduled', None),
                ('run.upgrade_ladder_result_cards', None), ('buffer_post.collect_metrics', None)):
                stack.enter_context(patch(target, return_value=result))
            stack.enter_context(patch('buffer_post.quota.buffer_block_reason', return_value=optional_hold))
            mirror = stack.enter_context(patch('discord_post.mirror_sent', side_effect=deliver))
            save = stack.enter_context(patch('x_post.save_log'))
            channel = stack.enter_context(patch('buffer_post.x_channel',
                side_effect=buffer_post.BufferError('Buffer local free-plan request cap reached') if discovery_blocked else None,
                return_value={'id':'ch'}))
            limit = stack.enter_context(patch('buffer_post.daily_limit',return_value=None))
            schedule = stack.enter_context(patch('buffer_post.schedule'))
            run.buffer_posts(now, ctx, {}, [], status)
        return book, status, mirror, save, channel, limit, schedule

    def test_discord_receipt_saved_even_when_buffer_discovery_is_blocked(self):
        book, status, mirror, save, channel, limit, schedule = self.exercise(
            [('new', 'play', 'caption', datetime(2026, 10, 26, 13, tzinfo=timezone.utc), None)])
        mirror.assert_called_once()
        self.assertEqual(book['posts'][0]['discord']['state'], 'sent')
        save.assert_called_once_with(book)
        channel.assert_called_once()
        limit.assert_not_called()
        schedule.assert_not_called()
        self.assertIn('cap reached', status['errors'][0])

    def test_empty_plan_spends_no_channel_or_daily_limit_request(self):
        book, status, mirror, save, channel, limit, schedule = self.exercise([])
        channel.assert_not_called()
        limit.assert_not_called()
        mirror.assert_called_once()
        save.assert_called_once_with(book)
        self.assertEqual(status['errors'], [])

    def test_optional_quota_hold_spends_no_discovery_but_keeps_discord(self):
        due=datetime(2026,10,26,13,tzinfo=timezone.utc)
        book,status,mirror,save,channel,limit,schedule=self.exercise(
            [('research','research','caption',due,None)],optional_hold='Buffer local free-plan request cap reached')
        channel.assert_not_called();limit.assert_not_called();schedule.assert_not_called()
        mirror.assert_called_once();save.assert_called_once_with(book)
        self.assertEqual(book['posts'][0]['discord']['state'],'sent')
        self.assertEqual(status['errors'],[])

    def test_optional_hold_retains_essential_plans_and_normal_discovery(self):
        due=datetime(2026,10,26,13,tzinfo=timezone.utc)
        essential=('released','play','caption',due,None)
        _,_,mirror,_,channel,limit,schedule=self.exercise(
            [('research','research','caption',due,None),essential],
            optional_hold='Buffer local free-plan request cap reached',discovery_blocked=False)
        channel.assert_called_once();limit.assert_called_once();mirror.assert_called_once()
        self.assertEqual(schedule.call_args.args[0],[essential])
