import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import test_live_watch as fixture_module
from test_live_watch import NOW, summary
import live_progress as P
import live_watch as L


class ProgressTests(unittest.TestCase):
    def setUp(self):
        fixture = fixture_module.LiveWatchTests()
        fixture.setUp()
        self.ctx, self.book = fixture.ctx, fixture.log
        self.ctx.games = fixture.games
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / 'sent.json'
        self.watch = Path(self.temp.name) / 'watch.json'
        self.pick = fixture.pick
        self.row = {'state': 'close', 'value': 41, 'remaining': 9, 'live': True,
                    'observedAt': L.boxscores.stamp(NOW), 'gameStatus': '4:10 - 2nd',
                    'previousObservedAt': L.boxscores.stamp(NOW - timedelta(minutes=5)),
                    'previousValue': 39, 'previousGameStatus': '9:10 - 2nd'}
        self.save()
        self.sent = []
        self.opts = dict(now=NOW, state_path=self.state, watch_path=self.watch,
                         ctx=self.ctx, book=self.book, fetch=lambda _: summary(42),
                         choose=lambda *a, **kw: {'id': 'p:p', 'style': 'plain'},
                         send=lambda url, text: self.sent.append(text), clock=lambda: NOW,
                         env={'DISCORD_WEBHOOK_URL': 'test-only'}, log=lambda *_: None)

    def save(self):
        L.write(self.watch, {'picks': {'p:p': self.row}})

    def run_pilot(self, **overrides):
        return P.run(**{**self.opts, **overrides})

    def test_exact_rechecked_integer_target_and_once_only(self):
        self.assertEqual(self.run_pilot(), 'sent')
        self.assertIn('42 so far. 8 more receiving yards to reach 50.', self.sent[0])
        self.assertNotIn('@', self.sent[0])
        self.assertEqual(self.run_pilot(), 'spacing')
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(L.read(self.state)['attempts'][0]['state'], 'sent')

    def test_whole_number_line_needs_one_more_and_normalized_rec_threshold(self):
        leg = {**self.pick, 'line': 50}
        self.assertEqual(P.close_status(leg, {'value': 49})['remaining'], 2)
        self.assertEqual(L.threshold({'market': 'rec'}), 1)
        self.assertEqual(L.threshold({'market': 'car'}), 2)
        status = L.progress(self.pick, L.live_record(summary(41), 'NFL', '1', 'x'))
        self.assertEqual(status['remaining'], 9)

    def test_stale_missing_or_not_moving_is_quiet(self):
        for changes in ({'observedAt': None}, {'previousObservedAt': None},
                        {'observedAt': L.boxscores.stamp(NOW - timedelta(minutes=3))},
                        {'previousGameStatus': '4:10 - 2nd'}, {'previousValue': 45},
                        {'live': False}, {'value': float('nan')}):
            with self.subTest(changes=changes):
                original = dict(self.row)
                self.row.update(changes)
                self.save()
                self.assertEqual(self.run_pilot(), 'no-candidate')
                self.row = original

    def test_never_post_under_unpublished_or_settled(self):
        for patcher in (patch.dict(self.pick, direction='under'),
                        patch.dict(self.ctx.latest, p={'result': 'loss'}),
                        patch.dict(self.book, posts=[])):
            with patcher:
                self.assertEqual(self.run_pilot(), 'no-candidate')

    def test_live_recheck_holds_final_crossed_corrected_missing(self):
        for data in (summary(42, True), summary(55), summary(35), {}):
            with self.subTest(data=data):
                L.write(self.state, {})
                self.assertIn(self.run_pilot(fetch=lambda _: data), ('changed', 'not-live'))
        self.assertEqual(self.sent, [])

    def test_local_model_skip_failure_or_invention_cannot_post(self):
        for decision in ({'id': 'skip', 'style': 'plain'}, {'id': 'fake', 'style': 'plain'},
                         {'id': 'p:p', 'style': 'guaranteed'}):
            L.write(self.state, {})
            self.assertEqual(self.run_pilot(choose=lambda *a, **kw: decision), 'editor-skipped')
        L.write(self.state, {})
        def offline(*a, **kw): raise RuntimeError('offline')
        self.assertEqual(self.run_pilot(choose=offline), 'held')
        self.assertEqual(self.sent, [])

    def test_slow_inference_cannot_publish_old_update(self):
        self.assertEqual(self.run_pilot(clock=lambda: NOW + timedelta(seconds=91)), 'too-late')
        self.assertEqual(self.sent, [])

    def test_ambiguous_send_never_retries_and_halts_pilot(self):
        def lost_response(*a):
            self.sent.append('possibly delivered')
            raise TimeoutError()
        self.assertEqual(self.run_pilot(send=lost_response), 'held')
        self.assertEqual(self.run_pilot(now=NOW + timedelta(hours=1)), 'pilot-review-required')
        self.assertEqual(len(self.sent), 1)

    def test_caps_spacing_and_kill_switch(self):
        self.assertEqual(self.run_pilot(env={'DISCORD_WEBHOOK_URL': 'test', 'KEENROUDY_LIVE_PROGRESS': '0'}), 'disabled')
        prior = {'state': 'sent', 'day': '2026-10-03', 'at': L.boxscores.stamp(NOW - timedelta(hours=1)), 'pickId': 'old'}
        L.write(self.state, {'attempts': [prior, prior]})
        self.assertEqual(self.run_pilot(), 'daily-cap')
        L.write(self.state, {'attempts': [prior, prior, prior]})
        self.assertEqual(self.run_pilot(), 'pilot-review-required')
        L.write(self.state, {})
        self.book['posts'][0]['discord']['sentAt'] = L.boxscores.stamp(NOW - timedelta(minutes=5))
        self.assertEqual(self.run_pilot(), 'official-spacing')

    def test_review_notice_is_once_and_same_ticket_stays_suppressed(self):
        prior = {'state': 'sent', 'day': '2026-10-02', 'at': L.boxscores.stamp(NOW - timedelta(days=1)), 'pickId': 'p'}
        L.write(self.state, {'attempts': [prior]})
        self.assertEqual(self.run_pilot(), 'no-candidate')
        L.write(self.state, {'attempts': [prior, prior, prior]})
        notices = []
        self.assertEqual(self.run_pilot(notify=notices.append), 'pilot-review-required')
        self.assertEqual(self.run_pilot(notify=notices.append), 'pilot-review-required')
        self.assertEqual(len(notices), 1)

    def test_game_total_points_math(self):
        self.pick.update(marketType='total', title='AWY/HME over 29.5', line=29.5)
        self.row.update(value=24, previousValue=21, state='currently-loss', remaining=None)
        self.save()
        self.assertEqual(self.run_pilot(), 'sent')
        self.assertIn('6 more points to reach 30', self.sent[0])

    def test_ticket_label_and_dead_leg_suppression(self):
        leg = {**self.pick, 'id': 'leg', 'gameId': 'NFL-1'}
        self.pick['legs'] = [leg]
        L.write(self.watch, {'picks': {'p:leg': self.row}})
        self.assertEqual(self.run_pilot(choose=lambda *a, **kw: {'id': 'p:leg', 'style': 'sweat'}), 'sent')
        self.assertIn('Ticket leg:', self.sent[0])
        self.assertIn('8 to go. Come on!', self.sent[0])
        self.assertIn('42/50 receiving yards', self.sent[0])
        self.assertNotIn('cashed', self.sent[0])
        L.write(self.state, {})
        self.pick['legs'].append({**leg, 'id': 'lost'})
        L.write(self.watch, {'picks': {'p:leg': self.row, 'p:lost': {'state': 'final-loss'}}})
        self.assertEqual(self.run_pilot(), 'no-candidate')

    def test_casual_style_is_not_repeated_on_consecutive_updates(self):
        L.write(self.state, {'attempts': [{'state': 'sent', 'style': 'sweat', 'pickId': 'other',
                 'day': '2026-10-02', 'at': L.boxscores.stamp(NOW - timedelta(days=1))}]})
        self.assertEqual(self.run_pilot(choose=lambda *a, **kw: {'id': 'p:p', 'style': 'sweat'}), 'sent')
        self.assertNotIn('Come on!', self.sent[0])
        self.assertNotIn('Posted play:', self.sent[0])
        self.assertIn('8 more receiving yards', self.sent[0])


if __name__ == '__main__':
    unittest.main()
