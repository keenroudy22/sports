import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post
import buffer_web
import cbb_picks
import daily_straight_card
import discord_post
import receipts

NOW = datetime(2026, 11, 16, 14, tzinfo=timezone.utc)


class ResultsOrderTests(unittest.TestCase):
    def test_morning_recap_replaces_individual_finals_and_covers_loss_only(self):
        now = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)
        start = '2026-11-22T18:00:00Z'
        game = {'id': 'sun', 'kickoff': start, 'league': 'NFL'}
        play = {'id': 'NFL-parlay', 'title': 'Two-leg parlay', 'gameIds': ['sun'], 'parlayType': 'longshot',
                'legs': [{'title': 'One'}, {'title': 'Two'}], 'odds': 230, 'book': 'DraftKings', 'riskUnits': .25,
                'result': 'loss', 'settledAt': '2026-11-22T21:00:00Z'}
        original = {'id': play['id'], 'kind': 'buffer:play', 'tweetId': '2123456789012345678',
                    'sentAt': '2026-11-22T15:00:00Z', 'discord': {'state': 'sent',
                      'sentAt': '2026-11-22T15:00:00Z', 'messageId': '1571995108096745533'}}
        book = {'posts': [original]}
        first = {play['id']: play}
        games = {'sun': game}
        self.assertEqual(receipts.cashed(first, {}, games, book, now), [])
        self.assertEqual(discord_post.queue_results(book, first, {}, games, now), 0)
        with patch.object(receipts, 'nba_daily_rows', return_value=[]), \
                patch.object(receipts, 'cbb_daily_rows', return_value=[]), \
                patch.object(receipts, 'unit_fun_rows', return_value=[]):
            hold = lambda: receipts.prior_day_results_hold(first, {}, games, book, now)
            self.assertIn('ready but not delivered', hold())
            recap = {'id': 'receipt:day:2026-11-22', 'resultPickIds': [play['id']],
                     'sentAt': '2026-11-23T11:46:00Z', 'tweetId': '2123456789012345679',
                     'link': 'https://x.com/keenkooks/status/2123456789012345679'}
            book['posts'].append(recap)
            self.assertIn('ready but not delivered', hold())
            recap['discord'] = {'state': 'sent', 'sentAt': '2026-11-23T11:46:30Z',
                                'messageId': '1571995108096745534'}
            self.assertIsNone(hold())
            self.assertIn('waiting for the complete graded card', receipts.prior_day_results_hold(
                first, {play['id']: {'result': None}}, games, book, now))

    def fixture(self):
        row = {'id': 'NFL-prior', 'result': 'loss'}
        original = {'id': row['id'], 'kind': 'buffer:play',
                    'sentAt': '2026-11-15T14:00:00Z', 'tweetId': '2123456789012345678',
                    'discord': {'state': 'sent', 'sentAt': '2026-11-15T13:50:00Z'}}
        final = {'id': 'burnt:' + row['id'], 'bufferPostId': 'queued',
                 'dueAt': '2026-11-16T15:00:00Z'}
        return row, original, final, {'posts': [original, final]}

    def test_recap_and_queue_do_not_clear_individual_finals(self):
        row, original, final, book = self.fixture()
        book['posts'].append({'id': 'receipt:day:2026-11-15', 'resultPickIds': [row['id']],
                              'sentAt': '2026-11-16T13:00:00Z', 'tweetId': '2123456789012345679'})
        self.assertIn('X Sent', receipts.prior_individual_results_hold([row], book, 'all'))
        final.update(sentAt='2026-11-16T13:05:00Z', tweetId='2123456789012345680')
        self.assertIn('X Sent', receipts.prior_individual_results_hold([row], book, 'all'))
        final['link'] = 'https://x.com/keenkooks/status/2123456789012345679'
        self.assertIn('X Sent', receipts.prior_individual_results_hold([row], book, 'all'))
        final['link'] = 'https://x.com/keenkooks/status/2123456789012345680'
        self.assertIn('Discord', receipts.prior_individual_results_hold([row], book, 'all'))
        original['discord']['result'] = {'state': 'sent', 'sentAt': '2026-11-16T13:06:00Z'}
        self.assertIn('Discord', receipts.prior_individual_results_hold([row], book, 'all'))
        original['discord']['result']['messageId'] = 'pending-provider-id'
        self.assertIn('Discord', receipts.prior_individual_results_hold([row], book, 'all'))
        original['discord']['result']['messageId'] = '1571995108096745533'
        self.assertIsNone(receipts.prior_individual_results_hold([row], book, 'all'))
        final['cancelledAt'] = '2026-11-16T13:07:00Z'
        self.assertIn('X Sent', receipts.prior_individual_results_hold([row], book, 'all'))

    def test_discord_only_original_does_not_invent_a_quote_target(self):
        row, original, final, book = self.fixture()
        original.pop('tweetId')
        original['discord']['result'] = {'state': 'sent', 'sentAt': '2026-11-16T13:06:00Z',
                                         'messageId': '1571995108096745533'}
        self.assertIsNone(receipts.prior_individual_results_hold([row], book, 'all'))
        row.pop('result')
        self.assertIn('final grade', receipts.prior_individual_results_hold([row], book, 'all'))

    def test_cbb_only_day_still_waits_for_its_individual_final(self):
        play = {'id': 'CBB-prior', 'kickoff': '2026-11-15T18:00:00Z', 'result': 'win'}
        book = {'posts': [{'id': play['id'], 'sentAt': '2026-11-15T15:00:00Z',
                           'tweetId': '2123456789012345678'}]}
        with patch.object(cbb_picks, 'public_rows', return_value=[play]), \
                patch.object(receipts, 'nba_daily_rows', return_value=[]):
            self.assertIn('CBB-prior', receipts.prior_day_results_hold({}, {}, {}, book, NOW))
            book['posts'].append({'id': 'receipt:cbb:CBB-prior:0123456789',
                                  'sentAt': '2026-11-16T12:00:00Z', 'tweetId': '2123456789012345679',
                                  'link': 'https://x.com/keenkooks/status/2123456789012345679'})
            self.assertIsNone(receipts.prior_day_results_hold({}, {}, {}, book, NOW))

    def test_combined_pregame_card_is_held_but_result_card_is_not(self):
        self.assertTrue(receipts.is_new_play('receipt:card:2026-11-16', 'receipt'))
        self.assertFalse(receipts.is_new_play('receipt:day:2026-11-15', 'receipt'))
        self.assertFalse(receipts.is_new_play('burnt:NFL-prior', 'cashed'))
        card = {'id': 'receipt:card:2026-11-16', 'kind': 'buffer:receipt',
                'discord': {'state': 'pending', 'destination': 'plays',
                            'readyAt': '2026-11-16T13:00:00Z', 'text': 'Today'}}
        with patch.object(daily_straight_card, 'discord_eligible', return_value=True), \
                patch.object(discord_post, 'send_message') as send:
            discord_post.mirror_sent({'posts': [card]}, NOW, url='plays',
                                     hold_new_plays='Final not sent', log=lambda *_: None)
        send.assert_not_called()
        self.assertEqual(card['discord']['lastHold'], 'Final not sent')

    def test_direct_scheduler_stops_before_any_provider_request(self):
        for guid, kind in [('NFL-new', 'play'), ('NBA-new', 'nba-trial'),
                           ('CBB-new', 'cbb-pick'), ('receipt:card:2026-11-16', 'receipt')]:
            with self.subTest(kind=kind), patch.object(receipts, 'current_results_hold', return_value='missing Final'), \
                    patch.object(buffer_post, 'http_send') as send:
                book = {'posts': []}
                buffer_post.schedule([(guid, kind, 'New pick', NOW, 'card')], 'channel', book, NOW,
                                     send=send, log=lambda *_: None)
                send.assert_not_called()
                self.assertEqual(book['posts'], [])

    def test_overnight_projection_cannot_reserve_next_mornings_provider_slot(self):
        now = datetime(2026, 11, 18, 3, 1, tzinfo=timezone.utc)
        due = datetime(2026, 11, 18, 13, 20, tzinfo=timezone.utc)
        plan = ('nba-projections-2026-11-18', 'research', 'My numbers', due, 'card')
        with patch.object(receipts, 'current_results_hold') as check, patch.object(buffer_post, 'create_post') as create:
            buffer_post.schedule([plan], 'x', {'posts': []}, now, log=lambda *_: None)
            check.assert_not_called()
            create.assert_not_called()
            check.return_value = 'recap missing on Discord'
            buffer_post.schedule([plan], 'x', {'posts': []}, due, log=lambda *_: None)
            check.assert_called_once()
            create.assert_not_called()

    def test_new_content_waits_while_prior_result_routes_remain_open(self):
        now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
        day = receipts.eastern_date(now)
        self.assertEqual(receipts.daily_morning(day).strftime('%H:%M'), '11:45')
        for kind in ('research', 'book', 'sheet', 'sports', 'conversation', 'news', 'play'):
            self.assertTrue(receipts.waits_for_morning_results('new', kind, day))
        self.assertTrue(receipts.waits_for_morning_results('receipt:week:2026-11-17', 'receipt', day))
        for guid in ('receipt:day:2026-11-18', 'receipt:nba:prior', 'receipt:cbb:prior'):
            self.assertFalse(receipts.waits_for_morning_results(guid, 'receipt', day))
        research = {'id': 'nba-projections-2026-11-19', 'kind': 'buffer:research',
                    'sentAt': '2026-11-19T11:50:00Z',
                    'discord': {'state': 'pending', 'destination': 'research', 'text': 'My numbers'}}
        with patch.object(discord_post, 'send_message') as send:
            discord_post.mirror_sent({'posts': [research]}, now, research_url='research',
                                     hold_new_plays='recap missing', log=lambda *_: None)
            send.assert_not_called()
        self.assertEqual(research['discord']['state'], 'pending')
        self.assertEqual(research['discord']['lastHold'], 'recap missing')

    def test_attended_recovery_cannot_jump_results(self):
        for reserve in (buffer_web.reserve_public_play, buffer_web.reserve_nba_pick,
                        buffer_web.reserve_cbb_pick):
            with self.subTest(route=reserve.__name__), \
                    patch.object(receipts, 'current_results_hold', return_value='missing Final'):
                with self.assertRaisesRegex(buffer_web.WebHold, 'Results first'):
                    reserve('new-pick', {'posts': []}, NOW)


if __name__ == '__main__':
    unittest.main()
