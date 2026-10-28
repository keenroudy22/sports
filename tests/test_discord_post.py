import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import discord_post
import result_display


NOW = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)


class DiscordPostTests(unittest.TestCase):
    def test_regular_nba_checks_original_then_sends_play_and_real_result_once(self):
        import nba_trial_runtime as nba
        now=datetime(2026,10,28,19,tzinfo=timezone.utc)
        original={'id':'NBA-new','game':{'teams':{'home':{'name':'Detroit'},'away':{'name':'Boston'}}},
                  'marketType':'total','direction':'over','line':221.5,'odds':-110,'book':'DraftKings','riskUnits':.5}
        entry={'id':'NBA-new','kind':'buffer:nba-trial','nbaPick':True,
               'discord':{'state':'pending','destination':'plays','readyAt':'2026-10-28T18:59:00Z','text':'NBA Picks\nOVER 221.5 (-110, DraftKings)'}}
        book={'posts':[entry]}
        with patch.object(nba,'public_rows',return_value=[original]),patch.object(nba,'current_match',return_value=False),patch.object(discord_post,'send_message') as send:
            discord_post.mirror_sent(book,now,url='plays',wins_url='wins',log=lambda *_:None)
            send.assert_not_called()
        with patch.object(nba,'public_rows',return_value=[original]),patch.object(nba,'current_match',return_value=True),patch.object(discord_post,'send_message') as send:
            discord_post.mirror_sent(book,now,url='plays',wins_url='wins',log=lambda *_:None)
            discord_post.mirror_sent(book,now,url='plays',wins_url='wins',log=lambda *_:None)
            self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.args[0],'plays')
        final=dict(original,result='loss',actual=210,settledAt='2026-10-29T02:00:00Z')
        moment=datetime(2026,10,29,2,5,tzinfo=timezone.utc)
        self.assertEqual(nba.queue_discord_results(book,moment,[final]),1)
        self.assertEqual(nba.queue_discord_results(book,moment,[final]),0)
        self.assertIn('-0.50u',entry['discord']['result']['text'])
        with patch.object(discord_post,'send_message') as send:
            discord_post.mirror_sent(book,moment,url='plays',wins_url='wins',log=lambda *_:None)
            discord_post.mirror_sent(book,moment,url='plays',wins_url='wins',log=lambda *_:None)
            self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.args[0],'plays')
        self.assertEqual(entry['discord']['result']['state'],'sent')
    def test_old_nba_x_post_cannot_bypass_current_discord_relevance(self):
        import nba_editorial
        now = datetime(2026, 10, 23, 19, tzinfo=timezone.utc)
        for family in ('trends', 'props'):
            entry = {'id': f'nba-{family}-2026-10-23', 'kind': 'buffer:research',
                     'sentAt': '2026-10-23T14:00:00Z', 'link': 'https://x.com/keenkooks/status/123',
                     'discord': {'state': 'pending', 'destination': 'research', 'text': 'Old research'}}
            snapshot = {'key': entry['id'], 'family': family, 'rows': [], 'evidence': []}
            with patch.object(nba_editorial, 'stored', return_value=[snapshot]), \
                 patch.object(discord_post, 'send_message') as send:
                discord_post.mirror_sent({'posts': [entry]}, now, research_url='research', log=lambda *_: None)
                discord_post.mirror_sent({'posts': [entry]}, now, research_url='research', log=lambda *_: None)
                send.assert_not_called()
            self.assertEqual(entry['discord']['state'], 'skipped')
            self.assertIn('Current research policy', entry['discord']['reason'])
            self.assertEqual(entry['sentAt'], '2026-10-23T14:00:00Z')
            self.assertEqual(entry['discord']['text'], 'Old research')

    def test_current_nba_research_mirrors_once_but_sent_history_is_untouched(self):
        import buffer_post
        now = datetime(2026, 10, 23, 19, tzinfo=timezone.utc)
        entry = {'id': 'nba-trends-2026-10-23', 'kind': 'buffer:research',
                 'sentAt': '2026-10-23T18:59:00Z',
                 'discord': {'state': 'pending', 'destination': 'research', 'text': 'Current comparison'}}
        with patch.object(buffer_post, 'queued_relevance_issues', return_value=[]) as review, \
             patch.object(discord_post, 'send_message') as send:
            discord_post.mirror_sent({'posts': [entry]}, now, research_url='research', log=lambda *_: None)
            self.assertEqual(entry['discord']['state'], 'sent')
            review.return_value = ['now stale']
            discord_post.mirror_sent({'posts': [entry]}, now, research_url='research', log=lambda *_: None)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(review.call_count, 1)
            self.assertEqual(entry['discord']['state'], 'sent')

    def test_nba_prop_mirror_rechecks_latest_projection_and_role(self):
        import buffer_post, nba_editorial
        now = datetime(2026, 10, 23, 19, tzinfo=timezone.utc)
        entry = {'id': 'nba-props-2026-10-23'}
        snapshot = {'key': entry['id'], 'family': 'props'}
        with patch.object(nba_editorial, 'stored', return_value=[snapshot]), \
             patch.object(nba_editorial, 'relevance_issues', return_value=[]), \
             patch.object(nba_editorial, 'watch_current', return_value=True), \
             patch.object(nba_editorial, 'props_current', return_value=False):
            self.assertIn('current price, projection or role', buffer_post.queued_relevance_issues(entry, now)[0])

    def test_playbook_is_removed_at_delivery_even_for_an_old_pending_mirror(self):
        text = 'Player over 4.5 (-110)\n\n@Playbook #NFL'
        entry = {'id': 'play', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z',
                 'discord': {'state': 'pending', 'text': text}}
        sent = []
        send = lambda url, body, headers: (sent.append(body) or (204, b''))
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual(sent[0]['content'], 'Player over 4.5 (-110)\n\n#NFL\n\n21+ only')
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

    def test_a_waited_discord_upload_returns_its_durable_attachment(self):
        raw = b'{"id":"message-1","attachments":[{"url":"https://cdn.discord/card.png"}]}'
        sent = []
        send = lambda url, body, headers: (sent.append(url) or (200, raw))
        receipt = discord_post.send_message('secret', 'Released', 'private:play', send=send,
                                             fetch=lambda _: (b'png', 'image/png', 'card.png'),
                                             return_receipt=True)
        self.assertEqual(receipt, {'id': 'message-1', 'image': 'https://cdn.discord/card.png'})

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
        self.assertEqual([body['content'] for body in sent], ['The play\n\n21+ only'])
        self.assertTrue(log_book['posts'][0]['discord']['beforeX'])
        self.assertEqual(log_book['posts'][2]['discord']['state'], 'skipped', 'old house copy never mirrors')

    def test_a_pull_followup_is_sent_once(self):
        sent = []
        entry = {'id': 'a', 'kind': 'buffer:play', 'cancelledAt': '2026-09-28T16:00:00Z', 'discord': {
            'state': 'sent', 'followup': {'state': 'pending', 'text': 'Pulled after confirmed news'}}}
        send = lambda url, body, headers: (sent.append(body) or (204, b''))
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='secret', send=send, log=lambda *_: None)
        self.assertEqual([body['content'] for body in sent], ['Pulled after confirmed news\n\n21+ only'])
        self.assertEqual(entry['discord']['followup']['state'], 'sent')

    def test_settled_official_plays_get_one_factual_result_update(self):
        entry = {'id': 'NFL-ty', 'kind': 'buffer:play', 'discord': {'state': 'sent', 'text': 'The play'}}
        first = {'NFL-ty': {'id': 'NFL-ty', 'title': 'Ty Johnson OVER 13.5 receiving yards',
                            'player': 'Ty Johnson', 'athleteId': '1', 'market': 'recYds',
                            'direction': 'over', 'line': 13.5, 'gameIds': ['NFL-game']}}
        latest = {'NFL-ty': {'result': 'win', 'settledAt': '2026-09-28T15:50:00Z',
                             'actual': 'Ty Johnson: 72 receiving yards', 'actualValue': 72}}
        games = {'NFL-game': {'id': 'NFL-game', 'home': 'Rams', 'away': 'Bills'}}
        self.assertEqual(discord_post.queue_results({'posts': [entry]}, first, latest, games, NOW), 1)
        self.assertEqual(discord_post.queue_results({'posts': [entry]}, first, latest, games, NOW), 0)
        self.assertEqual(entry['discord']['result']['state'], 'pending')
        self.assertIn('Ty Johnson', entry['discord']['result']['text'])
        self.assertNotRegex(entry['discord']['result']['text'], r'\b\d{5,}:')
        sent = []
        send = lambda url, body, headers: (sent.append(body['content']) or (204, b''))
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='plays', send=send, log=lambda *_: None)
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='plays', send=send, log=lambda *_: None)
        self.assertEqual(len(sent), 1)
        self.assertIn('FINAL · HIT', sent[0])
        self.assertEqual(entry['discord']['result']['state'], 'sent')

    def test_settled_updates_wait_during_result_quiet_hours(self):
        entry = {'id': 'NFL-ty', 'kind': 'buffer:play', 'discord': {'state': 'sent'}}
        first = {'NFL-ty': {'id': 'NFL-ty', 'title': 'Ty Johnson OVER 13.5 receiving yards'}}
        latest = {'NFL-ty': {'result': 'win', 'settledAt': '2026-09-28T05:05:00Z'}}
        quiet = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)  # 2 AM Eastern
        self.assertEqual(discord_post.queue_results({'posts': [entry]}, first, latest, {}, quiet), 0)
        self.assertNotIn('result', entry['discord'])

    def test_an_overtime_flip_is_sent_as_a_bad_beat_not_a_plain_miss(self):
        entry = {'id': 'NFL-kyren', 'kind': 'buffer:play', 'discord': {'state': 'sent'}}
        first = {'NFL-kyren': {'id': 'NFL-kyren', 'title': 'Kyren Williams UNDER 14.5 carries',
                               'player': 'Kyren Williams', 'athleteId': '4430737', 'market': 'car',
                               'direction': 'under', 'line': 14.5, 'gameIds': ['NFL-game']}}
        latest = {'NFL-kyren': {'result': 'loss', 'settledAt': '2026-09-28T15:50:00Z',
                                'actualValue': 16}}
        game = {'home': {'periods': [0, 7, 7, 20, 0]}, 'away': {'periods': [6, 7, 6, 15, 3]},
                'players': [{'id': '4430737', 'car': 16, 'otCar': 2}]}
        with patch.object(result_display, 'stored_games', return_value={'NFL-game': game}):
            self.assertEqual(discord_post.queue_results({'posts': [entry]}, first, latest,
                                                        {'NFL-game': game}, NOW), 1)
        text = entry['discord']['result']['text']
        self.assertIn('OT BAD BEAT', text)
        self.assertIn('14 carries through regulation', text)
        self.assertIn('OT added 2 carries', text)

    def test_no_webhook_is_a_quiet_noop(self):
        entry = {'id': 'a', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z', 'discord': {'state': 'pending', 'text': 'Play'}}
        self.assertEqual(discord_post.mirror_sent({'posts': [entry]}, NOW, url='',
                                                wins_url='', research_url='', log=lambda *_: None), [])
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
        self.assertEqual(sent[0][1]['content'], 'MOVE FAST\n\n21+ only')

    def test_arb_webhook_can_have_its_own_channel_and_falls_back_to_plays(self):
        self.assertEqual(discord_post.arb_webhook({'DISCORD_ARB_WEBHOOK_URL': 'arb',
                                                   'DISCORD_WEBHOOK_URL': 'plays'}), 'arb')
        self.assertEqual(discord_post.arb_webhook({'DISCORD_WEBHOOK_URL': 'plays'}), 'plays')
        self.assertFalse(discord_post.send_arb_alert('x', 'y', NOW, '/unused', url=''))

    def test_community_win_uses_dedicated_destination_without_public_fallback(self):
        sent = []
        entry = {'id': 'community:win', 'kind': 'buffer:community', 'sentAt': '2026-09-28T15:59:00Z',
                 'discord': {'state': 'pending', 'destination': 'wins', 'communityType': 'result', 'text': 'MODEL COOKED'}}
        send = lambda url, body, headers: (sent.append((url, body)) or (204, b''))
        self.assertEqual(discord_post.mirror_sent({'posts': [entry]}, NOW, url='plays', wins_url='wins',
                                                  send=send, log=lambda *_: None), [])
        self.assertEqual(sent[0][0], 'wins')
        self.assertEqual(sent[0][1]['content'], 'MODEL COOKED\n\n21+ only')

        held = {'id': 'community:held', 'kind': 'buffer:community', 'sentAt': '2026-09-28T15:59:00Z',
                'discord': {'state': 'pending', 'destination': 'wins', 'communityType': 'result', 'text': 'WIN'}}
        failures = discord_post.mirror_sent({'posts': [held]}, NOW, url='plays', wins_url='',
                                            send=send, log=lambda *_: None)
        self.assertEqual(failures, [{'id': 'community:held', 'error': 'Discord destination is not configured'}])
        self.assertEqual(held['discord']['state'], 'pending')
        self.assertEqual(len(sent), 1, 'a community win must never leak into the official plays channel')

    def test_actual_nba_ticket_cannot_follow_legacy_pending_wins_route(self):
        row = {'id': 'community:personal-ticket:2026-10-21-nba-lotto', 'kind': 'buffer:community',
               'sentAt': '2026-09-28T15:59:00Z',
               'discord': {'state': 'pending', 'destination': 'wins', 'text': 'NBA FUN LOTTO',
                           'image': 'https://example.com/ticket.png'}}
        sent = []
        send = lambda url, body, headers: (sent.append((url, body)) or (204, b''))
        fetch = lambda _: (b'original screenshot', 'image/png', 'ticket.png')
        discord_post.mirror_sent({'posts': [row]}, NOW, url='plays', wins_url='wins', send=send,
                                 fetch=fetch, log=lambda *_: None)
        self.assertEqual([s[0] for s in sent], ['plays'])
        self.assertIn(b'original screenshot', sent[0][1])
        self.assertEqual(row['discord']['destination'], 'plays')
        self.assertEqual(row['kind'], 'buffer:community')
        discord_post.mirror_sent({'posts': [row]}, NOW, url='plays', wins_url='wins', send=send,
                                 fetch=fetch, log=lambda *_: None)
        self.assertEqual(len(sent), 1)

    def test_unknown_community_and_unsettled_result_never_default_to_wins(self):
        self.assertIsNone(discord_post.community_type('community:unknown'))
        self.assertIsNone(discord_post.community_type('community:unknown', {
            'community:unknown': {'communityResult': True, 'result': 'win'}}))
        self.assertIsNone(discord_post.community_type('community:ordinary-loss', {
            'community:ordinary-loss': {'communityResult': True, 'result': 'loss', 'settledAt': NOW.isoformat()}}))
        row = {'id': 'community:unknown', 'kind': 'buffer:community', 'sentAt': NOW.isoformat(),
               'discord': {'state': 'pending', 'destination': 'wins', 'text': 'A new ticket'}}
        sent = []
        discord_post.mirror_sent({'posts': [row]}, NOW, url='plays', wins_url='wins',
                                 send=lambda *a: (sent.append(a) or (204, b'')), log=lambda *_: None)
        self.assertFalse(sent)
        self.assertEqual(row['discord']['state'], 'skipped')

    def test_wins_webhook_never_falls_back(self):
        self.assertEqual(discord_post.wins_webhook({'DISCORD_WINS_WEBHOOK_URL': 'wins'}), 'wins')
        self.assertEqual(discord_post.wins_webhook({'DISCORD_WEBHOOK_URL': 'plays'}), '')

    def test_research_webhook_never_falls_back(self):
        self.assertEqual(discord_post.research_webhook({'DISCORD_RESEARCH_WEBHOOK_URL': 'research'}), 'research')
        self.assertEqual(discord_post.research_webhook({'DISCORD_WEBHOOK_URL': 'plays'}), '')

    def test_research_mirrors_after_x_with_label_and_link(self):
        sent = []
        entry = {'id': 'research:trend', 'kind': 'buffer:research',
                 'sentAt': '2026-09-28T15:59:00Z', 'link': 'https://x.com/keenkooks/status/123',
                 'discord': {'state': 'pending', 'destination': 'research', 'text': 'MATCHUP TRENDS'}}
        send = lambda url, body, headers: (sent.append((url, body['content'])) or (204, b''))
        discord_post.mirror_sent({'posts': [entry]}, NOW, url='plays', research_url='research',
                                 send=send, log=lambda *_: None)
        self.assertEqual(sent, [('research', 'MATCHUP TRENDS\n\nRESEARCH · NOT A BEST BET\n'
                                         'https://x.com/keenkooks/status/123\n\n21+ only')])

        waiting = {'id': 'research:waiting', 'kind': 'buffer:research',
                   'discord': {'state': 'pending', 'destination': 'research', 'text': 'WAIT'}}
        discord_post.mirror_sent({'posts': [waiting]}, NOW, url='plays', research_url='research',
                                 send=send, log=lambda *_: None)
        self.assertEqual(len(sent), 1, 'research must not reach Discord before X is confirmed live')

        held = {'id': 'research:held', 'kind': 'buffer:research',
                'sentAt': '2026-09-28T15:59:00Z',
                'discord': {'state': 'pending', 'destination': 'research', 'text': 'HELD'}}
        failures = discord_post.mirror_sent({'posts': [held]}, NOW, url='plays', research_url='',
                                            send=send, log=lambda *_: None)
        self.assertEqual(failures, [{'id': 'research:held', 'error': 'Discord destination is not configured'}])
        self.assertEqual(len(sent), 1, 'research must never leak into the official plays channel')

    def test_official_play_and_win_reach_plays_while_community_stays_separate(self):
        sent = []
        rows = [
            {'id': 'play', 'kind': 'buffer:play', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'The play'}},
            {'id': 'cashed:play', 'kind': 'buffer:cashed', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'Cooked'}},
            {'id': 'ladder-loss:play', 'kind': 'buffer:cashed', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'A miss'}},
            {'id': 'receipt:day:test', 'kind': 'buffer:receipt', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'Old receipt'}},
            {'id': 'research:test', 'kind': 'buffer:research', 'sentAt': '2026-09-28T15:59:00Z',
             'discord': {'state': 'pending', 'text': 'Old research'}},
        ]
        send = lambda url, body, headers: (sent.append((url, body['content'])) or (204, b''))
        discord_post.mirror_sent({'posts': rows}, NOW, url='plays', wins_url='wins', research_url='',
                                 send=send, log=lambda *_: None)
        self.assertEqual(sent, [('plays', 'The play\n\n21+ only'), ('plays', 'Cooked\n\n21+ only')])
        self.assertTrue(all(row['discord']['state'] == 'skipped' for row in rows[2:]))

    def test_official_cooked_result_does_not_need_the_community_webhook(self):
        row = {'id': 'cashed:play', 'kind': 'buffer:cashed', 'sentAt': '2026-09-28T15:59:00Z',
               'discord': {'state': 'pending', 'text': 'Cooked'}}
        sent = []
        send = lambda url, body, headers: (sent.append((url, body['content'])) or (204, b''))
        self.assertEqual(discord_post.mirror_sent({'posts': [row]}, NOW, url='plays', wins_url='',
                                                  send=send, log=lambda *_: None), [])
        self.assertEqual(sent, [('plays', 'Cooked\n\n21+ only')])
        self.assertEqual(row['discord']['state'], 'sent')

    def test_official_burnt_result_also_reaches_plays_and_results(self):
        row = {'id': 'burnt:play', 'kind': 'buffer:cashed', 'sentAt': '2026-09-28T15:59:00Z',
               'discord': {'state': 'pending', 'text': 'Overtime got it. Pain.'}}
        sent = []
        send = lambda url, body, headers: (sent.append((url, body['content'])) or (204, b''))
        self.assertEqual(discord_post.mirror_sent({'posts': [row]}, NOW, url='plays', wins_url='',
                                                  send=send, log=lambda *_: None), [])
        self.assertEqual(sent, [('plays', 'Overtime got it. Pain.\n\n21+ only')])


if __name__ == '__main__':
    unittest.main()
