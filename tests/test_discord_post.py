import sys
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

    def test_no_webhook_is_a_quiet_noop(self):
        entry = {'id': 'a', 'sentAt': '2026-09-28T15:59:00Z', 'discord': {'state': 'pending', 'text': 'Play'}}
        self.assertEqual(discord_post.mirror_sent({'posts': [entry]}, NOW, url='', log=lambda *_: None), [])
        self.assertEqual(entry['discord']['state'], 'pending')


if __name__ == '__main__':
    unittest.main()
