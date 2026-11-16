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
        self.assertIn('Discord', receipts.prior_individual_results_hold([row], book, 'all'))
        original['discord']['result'] = {'state': 'sent', 'sentAt': '2026-11-16T13:06:00Z'}
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
                                  'sentAt': '2026-11-16T12:00:00Z', 'tweetId': '2123456789012345679'})
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

    def test_attended_recovery_cannot_jump_results(self):
        for reserve in (buffer_web.reserve_public_play, buffer_web.reserve_nba_pick,
                        buffer_web.reserve_cbb_pick):
            with self.subTest(route=reserve.__name__), \
                    patch.object(receipts, 'current_results_hold', return_value='missing Final'):
                with self.assertRaisesRegex(buffer_web.WebHold, 'Results first'):
                    reserve('new-pick', {'posts': []}, NOW)


if __name__ == '__main__':
    unittest.main()
