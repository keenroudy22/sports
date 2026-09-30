import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import discord_post


NOW = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)


class DiscordPostTests(unittest.TestCase):
    def test_only_new_eligible_sent_posts_are_mirrored_once_with_the_same_card(self):
        sent = []
        log_book = {'posts': [
            {'id': 'new', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'The play', 'image': 'https://example.com/card.png'}},
            {'id': 'old', 'sentAt': '2026-09-28T12:00:00Z'},
            {'id': 'waiting', 'discord': {'state': 'pending', 'text': 'Not on X yet'}},
            {'id': 'done', 'sentAt': '2026-09-28T12:00:00Z', 'discord': {'state': 'sent', 'text': 'Already there'}},
        ]}

        def send(url, body, headers):
            sent.append((url, body, headers))
            return 204, b''

        self.assertEqual(discord_post.mirror_sent(log_book, NOW, url='secret', send=send, log=lambda *_: None), [])
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1]['content'], 'The play')
        self.assertEqual(sent[0][1]['embeds'][0]['image']['url'], 'https://example.com/card.png')
        self.assertEqual(log_book['posts'][0]['discord']['state'], 'sent')
        discord_post.mirror_sent(log_book, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual(len(sent), 1, 'a later desk run cannot duplicate it')

    def test_a_failure_retries_but_only_reports_a_changed_error(self):
        entry = {'id': 'a', 'sentAt': '2026-09-28T15:59:00Z', 'discord': {'state': 'pending', 'text': 'Play'}}
        fail = lambda *a: (429, b'rate limited')
        first = discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=fail, log=lambda *_: None)
        second = discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=fail, log=lambda *_: None)
        self.assertEqual(first, [{'id': 'a', 'error': 'Discord returned HTTP 429: rate limited'}])
        self.assertEqual(second, [])
        self.assertEqual(entry['discord']['attempts'], 2)
        self.assertEqual(entry['discord']['state'], 'pending')

    def test_a_due_play_posts_before_x_but_other_copy_still_waits(self):
        sent = []
        log_book = {'posts': [
            {'id': 'play', 'dueAt': '2026-09-28T16:15:00Z',
             'discord': {'state': 'pending', 'readyAt': '2026-09-28T16:00:00Z', 'text': 'The play'}},
            {'id': 'later', 'discord': {'state': 'pending', 'readyAt': '2026-09-28T16:01:00Z', 'text': 'Too soon'}},
            {'id': 'house', 'discord': {'state': 'pending', 'text': 'Wait for X'}},
        ]}
        send = lambda url, body, headers: (sent.append(body) or (204, b''))
        discord_post.mirror_sent(log_book, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual([body['content'] for body in sent], ['The play'])
        self.assertTrue(log_book['posts'][0]['discord']['beforeX'])
        self.assertEqual(log_book['posts'][2]['discord']['state'], 'pending')

    def test_a_pull_followup_is_sent_once(self):
        sent = []
        entry = {'id': 'a', 'cancelledAt': '2026-09-28T16:00:00Z', 'discord': {
            'state': 'sent', 'followup': {'state': 'pending', 'text': 'Pulled after confirmed news'}}}
        send = lambda url, body, headers: (sent.append(body) or (204, b''))
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual([body['content'] for body in sent], ['Pulled after confirmed news'])
        self.assertEqual(entry['discord']['followup']['state'], 'sent')

    def test_no_webhook_is_a_quiet_noop(self):
        entry = {'id': 'a', 'sentAt': '2026-09-28T15:59:00Z', 'discord': {'state': 'pending', 'text': 'Play'}}
        self.assertEqual(discord_post.mirror_sent({'posts': [entry]}, NOW, url='', log=lambda *_: None), [])
        self.assertEqual(entry['discord']['state'], 'pending')

    def test_an_arb_alert_uses_discord_only_and_is_deduplicated(self):
        sent = []
        send = lambda url, body, headers: (sent.append((url, body)) or (204, b''))
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'arb-discord-alerts.json'
            self.assertTrue(discord_post.send_arb_alert('MOVE FAST', 'market-a', NOW, state,
                                                        url='discord-secret', send=send))
            self.assertFalse(discord_post.send_arb_alert('MOVE FAST', 'market-a', NOW, state,
                                                         url='discord-secret', send=send))
            later = datetime(2026, 9, 28, 22, 1, tzinfo=timezone.utc)
            self.assertTrue(discord_post.send_arb_alert('MOVE FAST', 'market-a', later, state,
                                                        url='discord-secret', send=send))
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0][0], 'discord-secret')
        self.assertEqual(sent[0][1]['username'], "Kook'n Arb Radar")
        self.assertEqual(sent[0][1]['content'], 'MOVE FAST')

    def test_arb_webhook_can_have_its_own_channel_and_falls_back_to_plays(self):
        self.assertEqual(discord_post.arb_webhook({'DISCORD_ARB_WEBHOOK_URL': 'arb',
                                                   'DISCORD_WEBHOOK_URL': 'plays'}), 'arb')
        self.assertEqual(discord_post.arb_webhook({'DISCORD_WEBHOOK_URL': 'plays'}), 'plays')
        self.assertFalse(discord_post.send_arb_alert('x', 'y', NOW, '/unused', url=''))


if __name__ == '__main__':
    unittest.main()
