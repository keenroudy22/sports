import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import social_copy
import social_style
import discord_post
import x_post
import ticket_card
import buffer_post


class SocialProjectionPolicyTests(unittest.TestCase):
    def test_actual_lines_stakes_and_historical_stats_are_not_forecasts(self):
        for text in ('Williams over 2.5 catches (+106 FanDuel), 0.5u',
                     'Over 2.5 in 7 of his last 10 games.',
                     'My total about 228. Book total 228.5.',
                     'My rounded score 109 - 119 | book 228.5'):
            self.assertFalse(social_copy.decimal_projection(text), text)
        for text in ('I have it at 2.6.', 'I project 3.4 targets.',
                     'My number 2.6 · line 2.5', 'We project 44.1 points'):
            self.assertTrue(social_copy.decimal_projection(text), text)
            self.assertTrue(social_style.issues(text))

    def test_reason_omits_forecast_instead_of_rounding_into_confidence(self):
        self.assertEqual(social_copy.projection_free_reason(
            'I project 3.4 targets. He leads Dallas running backs in targets.'),
            'He leads Dallas running backs in targets.')

    def test_real_wager_caption_and_art_preserve_line_without_projection(self):
        pick = dict(id='NFL-social-test', title='Javonte Williams over 2.5 catches',
                    athleteId='1', market='rec', direction='over', line=2.5,
                    projection=2.6, odds=106, book='FanDuel', riskUnits=.5,
                    gameIds=[], reasons=['He leads Dallas running backs in targets.'])
        before = copy.deepcopy(pick)
        caption = x_post.draft(pick, reason=pick['reasons'][0], history=[])
        self.assertIn('2.5', caption)
        self.assertNotIn('2.6', caption)
        self.assertNotIn('I have it', caption)
        svg = ticket_card.straight_svg(pick, {'league':'NFL', 'away':{'abbreviation':'DAL'},
                        'home':{'abbreviation':'PHI'}, 'kickoff':'2026-10-27T00:15:00Z'},
                        fetch=lambda _: None, art={}, player_side='away', reason=pick['reasons'][0])
        self.assertIn('2.5', svg)
        self.assertNotIn('2.6', svg)
        self.assertNotIn('I HAVE IT AT', svg)
        self.assertEqual(pick, before)

    def test_discord_rejects_forecast_before_network_send(self):
        send = Mock()
        with self.assertRaises(discord_post.DiscordError):
            discord_post.send_message('https://example.com/webhook',
                'Over 2.5 catches. I project 3.4 targets.', send=send)
        send.assert_not_called()

    def test_private_queue_is_rechecked_and_sent_or_unknown_is_preserved(self):
        from unittest.mock import patch
        now = datetime(2026,10,27,12,tzinfo=timezone.utc)
        for state in ('scheduled','sent','publishing'):
            entry = dict(id='research:test', bufferPostId='draft',
                         dueAt='2026-10-27T13:00:00Z', socialStyleVersion='plain-20261022')
            with patch.object(buffer_post, 'graphql', return_value={'post': {
                    'status':state, 'text':'Over 2.5 catches. I project 3.4 targets.\n\n21+ only'}}), \
                 patch.object(buffer_post, 'delete_post') as delete:
                buffer_post.audit_pending_style({'posts':[entry]},now,items={},log=lambda *_:None)
                self.assertEqual(delete.called, state=='scheduled')


if __name__ == '__main__': unittest.main()
