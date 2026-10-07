import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import discord_post


NOW = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)


class DiscordPostTests(unittest.TestCase):
    def test_playbook_is_removed_at_delivery_even_for_an_old_pending_mirror(self):
        text = 'Player over 4.5 (-110)\n\n@Playbook #NFL'
        entry = {'id': 'play', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z',
                 'discord': {'state': 'pending', 'text': text}}
        sent = []
        send = lambda url, body, headers: (sent.append(body) or (204, b''))
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual(sent[0]['content'], 'Player over 4.5 (-110)\n\n#NFL')
        self.assertEqual(entry['discord']['text'], text, 'do not rewrite the stored original')

    def test_playbook_cleanup_keeps_other_tags_and_links(self):
        from social_copy import without_playbook
        self.assertEqual(without_playbook('@PLAYBOOK\n\nUpdate\n@Playbook #NFL'), 'Update\n#NFL')
        self.assertEqual(without_playbook('Hi @Someone #NFL'), 'Hi @Someone #NFL')
        self.assertEqual(without_playbook('@PlaybookExtra'), '@PlaybookExtra')

    def test_only_new_eligible_sent_posts_are_mirrored_once_with_the_same_card(self):
        sent = []
        log_book = {'posts': [
            {'id': 'new', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'The play', 'image': 'https://example.com/card.png'}},
            {'id': 'old', 'sentAt': '2026-09-28T12:00:00Z'},
            {'id': 'waiting', 'discord': {'state': 'pending', 'text': 'Not on X yet'}},
            {'id': 'done', 'sentAt': '2026-09-28T12:00:00Z', 'discord': {'state': 'sent', 'text': 'Already there'}},
        ]}

        def send(url, body, headers):
            sent.append((url, body, headers))
            return 204, b''

        fetch = lambda _: (b'png bytes', 'image/png', 'kookn-card.png')
        self.assertEqual(discord_post.mirror_sent(log_book, NOW, url='secret', send=send, fetch=fetch, log=lambda *_: None), [])
        self.assertEqual(len(sent), 1)
        self.assertIsInstance(sent[0][1], bytes)
        self.assertIn(b'The play', sent[0][1])
        self.assertIn(b'png bytes', sent[0][1])
        self.assertIn('multipart/form-data', sent[0][2]['Content-Type'])
        self.assertNotIn(b'https://example.com/card.png', sent[0][1])
        self.assertEqual(log_book['posts'][0]['discord']['state'], 'sent')
        discord_post.mirror_sent(log_book, NOW, url='secret', send=send, fetch=fetch, log=lambda *_: None)
        self.assertEqual(len(sent), 1, 'a later desk run cannot duplicate it')

    def test_a_card_download_failure_falls_back_to_the_public_embed(self):
        sent = []
        fail = lambda _: (_ for _ in ()).throw(discord_post.DiscordError('no card'))
        send = lambda url, body, headers: (sent.append((body, headers)) or (204, b''))
        discord_post.send_message('secret', 'Still deliver it', 'https://example.com/card.png', send=send, fetch=fail)
        self.assertEqual(sent[0][0]['embeds'][0]['image']['url'], 'https://example.com/card.png')
        self.assertEqual(sent[0][1]['Content-Type'], 'application/json')

    def test_a_failure_retries_but_only_reports_a_changed_error(self):
        entry = {'id': 'a', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z', 'discord': {'state': 'pending', 'text': 'Play'}}
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
            {'id': 'play', 'kind': 'buffer:play', 'dueAt': '2026-09-28T16:15:00Z',
             'discord': {'state': 'pending', 'readyAt': '2026-09-28T16:00:00Z', 'text': 'The play'}},
            {'id': 'later', 'kind': 'buffer:play', 'discord': {'state': 'pending', 'readyAt': '2026-09-28T16:01:00Z', 'text': 'Too soon'}},
            {'id': 'house', 'discord': {'state': 'pending', 'text': 'Wait for X'}},
        ]}
        send = lambda url, body, headers: (sent.append(body) or (204, b''))
        discord_post.mirror_sent(log_book, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual([body['content'] for body in sent], ['The play'])
        self.assertTrue(log_book['posts'][0]['discord']['beforeX'])
        self.assertEqual(log_book['posts'][2]['discord']['state'], 'skipped', 'old house copy never mirrors')

    def test_a_pull_followup_is_sent_once(self):
        sent = []
        entry = {'id': 'a', 'kind': 'buffer:play', 'cancelledAt': '2026-09-28T16:00:00Z', 'discord': {
            'state': 'sent', 'followup': {'state': 'pending', 'text': 'Pulled after confirmed news'}}}
        send = lambda url, body, headers: (sent.append(body) or (204, b''))
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual([body['content'] for body in sent], ['Pulled after confirmed news'])
        self.assertEqual(entry['discord']['followup']['state'], 'sent')

    def test_no_webhook_is_a_quiet_noop(self):
        entry = {'id': 'a', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z', 'discord': {'state': 'pending', 'text': 'Play'}}
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

    def test_community_win_uses_dedicated_destination_without_public_fallback(self):
        sent = []
        entry = {'id': 'community:win', 'kind': 'buffer:community', 'sentAt': '2026-09-28T15:59:00Z',
                 'discord': {'state': 'pending', 'destination': 'wins', 'text': 'MODEL COOKED'}}
        send = lambda url, body, headers: (sent.append((url, body)) or (204, b''))
        self.assertEqual(discord_post.mirror_sent({'posts': [entry]}, NOW, url='plays', wins_url='wins',
                                                  send=send, log=lambda *_: None), [])
        self.assertEqual(sent[0][0], 'wins')
        self.assertEqual(sent[0][1]['content'], 'MODEL COOKED')

        held = {'id': 'community:held', 'kind': 'buffer:community', 'sentAt': '2026-09-28T15:59:00Z',
                'discord': {'state': 'pending', 'destination': 'wins', 'text': 'WIN'}}
        failures = discord_post.mirror_sent({'posts': [held]}, NOW, url='plays', wins_url='',
                                            send=send, log=lambda *_: None)
        self.assertEqual(failures, [{'id': 'community:held', 'error': 'Discord destination is not configured'}])
        self.assertEqual(held['discord']['state'], 'pending')
        self.assertEqual(len(sent), 1, 'a community win must never leak into the official plays channel')

    def test_wins_webhook_never_falls_back(self):
        self.assertEqual(discord_post.wins_webhook({'DISCORD_WINS_WEBHOOK_URL': 'wins'}), 'wins')
        self.assertEqual(discord_post.wins_webhook({'DISCORD_WEBHOOK_URL': 'plays'}), '')

    def test_only_play_reaches_plays_and_win_reaches_wins_even_for_old_pending_rows(self):
        sent = []
        rows = [
            {'id': 'play', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'The play'}},
            {'id': 'cashed:play', 'kind': 'buffer:cashed', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'destination': 'wins', 'text': 'Cooked'}},
            {'id': 'ladder-loss:play', 'kind': 'buffer:cashed', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'A miss'}},
            {'id': 'receipt:day:test', 'kind': 'buffer:receipt', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'Old receipt'}},
            {'id': 'research:test', 'kind': 'buffer:research', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'Old research'}},
        ]
        send = lambda url, body, headers: (sent.append((url, body['content'])) or (204, b''))
        discord_post.mirror_sent({'posts': rows}, NOW, url='plays', wins_url='wins', send=send, log=lambda *_: None)
        self.assertEqual(sent, [('plays', 'The play'), ('wins', 'Cooked')])
        self.assertTrue(all(row['discord']['state'] == 'skipped' for row in rows[2:]))

    def test_missing_wins_webhook_skips_cooked_without_leaking_to_plays(self):
        row = {'id': 'cashed:play', 'kind': 'buffer:cashed', 'sentAt': '2026-09-28T15:59:00Z',
               'discord': {'state': 'pending', 'destination': 'wins', 'text': 'Cooked'}}
        self.assertEqual(discord_post.mirror_sent({'posts': [row]}, NOW, url='plays', wins_url='',
                                                  send=lambda *args: self.fail('must not send'), log=lambda *_: None), [])
        self.assertEqual(row['discord']['state'], 'skipped')


if __name__ == '__main__':
    unittest.main()
