import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import review


class ReviewTests(unittest.TestCase):
    def test_private_delivery_is_disabled_without_separately_verified_destination(self):
        never = lambda *a, **k: self.fail('no network without private setup')
        self.assertEqual(review.private_weekly_delivery('private', '2026-10-05', env={'DISCORD_WEBHOOK_URL': 'public'}, metadata=never, send=never), 'not-configured')
        self.assertEqual(review.private_weekly_delivery('private', '2026-10-05', env={'DISCORD_REVIEW_WEBHOOK_URL': 'private'}, metadata=never, send=never), 'private-destination-not-verified')

    def test_private_delivery_checks_identity_disables_mentions_and_never_retries_ambiguous_send(self):
        channel = '1555684007285489805'
        env = {'DISCORD_REVIEW_WEBHOOK_URL': 'https://discord.com/api/webhooks/1555684007285489806/fake-test-token',
               'DISCORD_REVIEW_CHANNEL_ID': channel, 'KEENROUDY_REVIEW_DISCORD_PRIVATE_VERIFIED': '1'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'review.json'
            calls = []
            def send(url, body, headers):
                calls.append(body)
                self.assertEqual(body['allowed_mentions'], {'parse': []})
                self.assertLessEqual(len(body['content']), 2000)
                return 200, json.dumps({'id': 'message', 'channel_id': channel}).encode()
            identify = lambda _: {'channel_id': channel, 'guild_id': 'server'}
            self.assertEqual(review.private_weekly_delivery('a\n' * 2000, '2026-10-05', env, path, identify, send), 'sent')
            self.assertEqual(review.private_weekly_delivery('private', '2026-10-05', env, path, identify, send), 'already-sent')
            self.assertEqual(len(calls), 1)
            self.assertNotIn('fake-test-token', path.read_text())
            self.assertEqual(review.private_weekly_delivery('private', '2026-10-12', env, path, identify,
                             lambda *a: (500, b'failed secret')), 'delivery-review-required')
            self.assertEqual(review.private_weekly_delivery('private', '2026-10-19', env, path, identify, send), 'delivery-review-required')
            self.assertEqual(len(calls), 1)

    def test_private_destination_mismatch_and_public_webhook_are_refused(self):
        env = {'DISCORD_REVIEW_WEBHOOK_URL': 'https://discord.com/api/webhooks/1555684007285489806/fake',
               'DISCORD_REVIEW_CHANNEL_ID': '1555684007285489805', 'KEENROUDY_REVIEW_DISCORD_PRIVATE_VERIFIED': '1'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'review.json'
            self.assertEqual(review.private_weekly_delivery('private', '2026-10-05', env, path,
                             lambda _: {'channel_id': 'other', 'guild_id': 'server'}), 'private-destination-mismatch')
            self.assertFalse(path.exists())
            env['DISCORD_WEBHOOK_URL'] = env['DISCORD_REVIEW_WEBHOOK_URL']
            self.assertEqual(review.private_weekly_delivery('private', '2026-10-05', env, path), 'private-destination-refused')
            env['DISCORD_WEBHOOK_URL'] = 'https://discord.com/api/webhooks/1555684007285489807/different-token'
            self.assertEqual(review.private_weekly_delivery('private', '2026-10-05', env, path,
                             lambda _: {'channel_id': env['DISCORD_REVIEW_CHANNEL_ID'], 'guild_id': 'server'}),
                             'private-destination-refused', 'different tokens do not make the same channel private')
            self.assertFalse(path.exists())

    def test_corrupt_private_delivery_reservation_never_resends(self):
        env = {'DISCORD_REVIEW_WEBHOOK_URL': 'https://discord.com/api/webhooks/1555684007285489806/fake',
               'DISCORD_REVIEW_CHANNEL_ID': '1555684007285489805', 'KEENROUDY_REVIEW_DISCORD_PRIVATE_VERIFIED': '1'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'review.json'
            path.write_text('partial write')
            self.assertEqual(review.private_weekly_delivery('private', '2026-10-05', env, path,
                             lambda _: self.fail('do not send without readable reservation state')),
                             'delivery-review-required')

    def test_hosted_runs_reads_the_whole_week_and_names_each_failed_step(self):
        commands = []

        class Result:
            def __init__(self, payload):
                self.stdout = json.dumps(payload)

        def github(command, **kwargs):
            commands.append(command)
            if command[1:3] == ['run', 'list']:
                return Result([
                    {'databaseId': 11, 'conclusion': 'success', 'createdAt': '2026-09-22T10:00:00Z',
                     'event': 'schedule', 'displayTitle': 'Refresh', 'url': 'https://github.test/runs/11'},
                    {'databaseId': 12, 'conclusion': 'failure', 'createdAt': '2026-09-23T10:00:00Z',
                     'event': 'schedule', 'displayTitle': 'Publish', 'url': 'https://github.test/runs/12'},
                    {'databaseId': 9, 'conclusion': 'failure', 'createdAt': '2026-09-20T10:00:00Z',
                     'event': 'schedule', 'displayTitle': 'Old', 'url': 'https://github.test/runs/9'},
                ])
            return Result({'url': 'https://github.test/runs/12', 'jobs': [
                {'name': 'build-and-deploy', 'steps': [
                    {'name': 'Build site', 'conclusion': 'success'},
                    {'name': 'Publish pages', 'conclusion': 'failure'},
                ]},
            ]})

        hosted = review.hosted_runs(date(2026, 9, 21), runner=github)
        self.assertEqual(hosted[0], {'success': 1, 'failure': 1})
        self.assertEqual(len(hosted[1]), 1)
        self.assertIn('build-and-deploy / Publish pages', hosted[1][0])
        self.assertIn('https://github.test/runs/12', hosted[1][0])
        self.assertIn('--created', commands[0])
        self.assertEqual(commands[0][commands[0].index('-L') + 1], '1000')
        self.assertEqual(sum(command[1:3] == ['run', 'view'] for command in commands), 1)

    def test_the_packet_carries_the_runs_the_posts_the_record_and_problems(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'run-2026-09-27.log').write_text(
                '[10:45:06] run for the 6:45 AM ET slot at 6:45 AM ET\n[10:53:13] done: 4 settled, 0 closed, 3 published, 191 screened\n'
                '[12:46:43] precheck: NFL-x closed before its post: soft news\n[13:00:00] nothing to see\n')
            runs = review.run_lines(date(2026, 9, 27), date(2026, 9, 27), logs=folder)
        self.assertEqual(runs[date(2026, 9, 27)]['runs'], 1)
        self.assertEqual(len(runs[date(2026, 9, 27)]['problems']), 1)
        log_book = {'posts': [
            {'id': 'a', 'kind': 'buffer:play', 'dueAt': '2026-09-27T15:00:00Z', 'tweetId': '1', 'sentAt': '2026-09-27T15:00:02Z'},
            {'id': 'b', 'kind': 'buffer:play', 'dueAt': '2026-09-27T15:10:00Z', 'cancelledAt': '2026-09-27T12:48:53Z',
             'precheck': {'reason': 'soft news'}},
            {'id': 'old', 'kind': 'buffer:play', 'dueAt': '2026-09-01T15:00:00Z'}]}
        posts = review.post_rows(log_book, date(2026, 9, 21), date(2026, 9, 28))
        self.assertEqual([p[1] for p in posts], ['a', 'b'])
        self.assertIn('pulled before posting: soft news', posts[1][3])
        first = {'w': {'title': 'Iowa/Michigan over 38.5', 'odds': -105, 'book': 'ESPN BET', 'publishedAt': '2026-09-26T10:45:00Z'},
                 'l': {'title': 'X under 44.5', 'odds': -110, 'book': 'FanDuel', 'publishedAt': '2026-09-26T10:45:00Z'},
                 'p': {'title': '3-leg longshot', 'legs': [{}, {}, {}], 'parlayType': 'longshot', 'odds': 600, 'riskUnits': 0.25}}
        latest = {'w': {'result': 'win', 'settledAt': '2026-09-27T03:00:00Z', 'units': 0.952},
                  'l': {'result': 'loss', 'settledAt': '2026-09-27T03:00:00Z', 'units': -1.0},
                  'p': {'result': 'loss', 'settledAt': '2026-09-27T03:00:00Z'}}
        week = review.record(first, latest, date(2026, 9, 21), date(2026, 9, 28))
        self.assertEqual(week[0], {'win': 1, 'loss': 1, 'push': 0, 'units': -0.05})
        self.assertEqual(week[1], {'win': 0, 'loss': 1})
        text = review.packet(date(2026, 9, 21), date(2026, 9, 28), runs, posts, week, ({'success': 3}, []), '', 'climb 1, step 1',
                             Path('/nonexistent/ALERT.txt'))
        for needle in ('## Desk runs', 'PROBLEM: [12:46:43]', '## X posts', 'Straight plays: 1-1-0, -0.05 units', 'Fun parlays: 0-1',
                       "{'success': 3}", 'ALERT.txt present: no'):
            self.assertIn(needle, text)

    def test_weekly_reach_uses_settled_buffer_rates_and_says_how_small_the_sample_is(self):
        log_book = {'posts': [
            {'kind': 'buffer:play', 'sentAt': '2026-09-24T16:00:00Z',
             'metrics': {'impressions': 100, 'engagementRate': 4.0, 'reactions': 1}},
            {'kind': 'buffer:play', 'sentAt': '2026-09-25T16:00:00Z',
             'metrics': {'impressions': 300, 'engagementRate': 2.0, 'reactions': 1}},
            {'kind': 'buffer:receipt', 'sentAt': '2026-09-26T13:00:00Z',
             'metrics': {'impressions': 50, 'engagementRate': 6.0}},
            {'kind': 'buffer:menu', 'sentAt': '2026-09-27T13:00:00Z'},
            {'kind': 'buffer:play', 'sentAt': '2026-09-10T16:00:00Z',
             'metrics': {'impressions': 999, 'engagementRate': 99.0}},
        ]}
        reach = review.post_metrics(log_book, date(2026, 9, 21), date(2026, 9, 28))
        self.assertEqual(reach['all'], {'posts': 3, 'impressions': 450, 'engagementRate': 2.89})
        self.assertEqual(reach['play'], {'posts': 2, 'impressions': 400, 'engagementRate': 2.5})
        self.assertEqual(reach['receipt'], {'posts': 1, 'impressions': 50, 'engagementRate': 6.0})
        themed = review.post_theme_metrics(log_book, date(2026, 9, 21), date(2026, 9, 28))
        self.assertEqual([(r['category'], r['theme'], r['posts']) for r in themed],
                         [('play', 'legacy', 2), ('receipt', 'legacy', 1)])
        self.assertTrue(all(r['smallSample'] for r in themed))

    def test_learning_packet_carries_latest_theme_and_silent_shadow_status(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / 'report.json'
            report.write_text(json.dumps({'at': '2026-10-06T12:30:00Z', 'changes': [], 'candidates': 10,
                                          'distinctCandidates': 7, 'cardThemes': [
                                              {'category': 'play', 'theme': 'felt', 'posts': 2,
                                               'perThousand': 12.5, 'smallSample': True}]}))
            (root / 'shadow-2026.jsonl').write_text(json.dumps({
                'id': 's', 'at': '2026-10-07T03:30:00Z', 'proposal': 'R0'}) + '\n')
            text = review.learning_packet(report, root)
        self.assertIn('10 raw; 7 distinct', text)
        self.assertIn('play / felt: 2 posts', text)
        self.assertIn('proposals R0; no public effects', text)

    def test_codex_reads_only(self):
        seen = {}

        def codex(command, **kwargs):
            seen['command'] = command
            Path(command[command.index('--output-last-message') + 1]).write_text('The week ran cleanly.')
        with tempfile.TemporaryDirectory() as folder:
            text = review.ask_codex('packet', Path(folder) / 'review.md', runner=codex)
        self.assertEqual(text, 'The week ran cleanly.')
        command = seen['command']
        self.assertEqual(command[command.index('--model') + 1], review.DEFAULT_CODEX_MODEL)
        self.assertIn(f'model_reasoning_effort="{review.DEFAULT_CODEX_REASONING}"', command)
        self.assertEqual(command[command.index('--sandbox') + 1], 'read-only')
        self.assertNotIn('web_search="live"', command, 'the review reads the packet, not the web')
        self.assertTrue(command[-1].startswith(review.PROMPT[:40]) and command[-1].endswith('packet'))


if __name__ == '__main__':
    unittest.main()
