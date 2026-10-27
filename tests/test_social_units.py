"""New delivery never exposes private cash; original ledger inputs remain unchanged."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import social_units
import social_style
import x_post
import receipts
import ticket_card
import ticket_cards
import ticket_kit
import discord_post

class SocialUnitsTests(unittest.TestCase):
    def rung(self):
        return dict(id='NFL-rung', parlayType='ladder', publishedAt='2026-10-27T15:00:00Z',
            odds=-160, book='FanDuel', riskUnits=.25,
            legs=[dict(title='Bills +3.5', odds=-110),dict(title='Ravens +7.5',odds=-110)],
            ladder=dict(run=4,step=1,stake=50,payout=81,banked=0,start=50,goal=1000,bankPercent=20,ridePercent=80))

    def test_new_climb_caption_uses_actual_exposure_and_preserves_private_size(self):
        pick=self.rung();before=copy.deepcopy(pick)
        text=x_post.draft(pick, {'league':'NFL'}, history=[])
        self.assertIn('2u (-160, FanDuel)',text)
        self.assertIn('\n\nBills +3.5\nRavens +7.5',text)
        self.assertNotIn('$',text)
        self.assertEqual(x_post.guard(text,pick),[])
        self.assertEqual(pick,before)

    def test_results_convert_same_saved_amounts_without_rewriting_results(self):
        for result in ('win','loss','push','void'):
            pick=dict(self.rung(),result=result,settledAt='2026-10-28T02:00:00Z')
            before=copy.deepcopy(pick)
            text=' '.join(receipts.ladder_result(pick))
            self.assertNotIn('$',text)
            self.assertIn('u',text)
            self.assertEqual(pick,before)

    def test_current_native_climb_graphic_contains_only_exact_units(self):
        pick=self.rung();before=copy.deepcopy(pick)
        data=ticket_card.climb_data(pick,{},art=[{},{}])
        card=ticket_cards.climb_card(data)
        self.assertEqual(ticket_kit.qa(card,'units-climb'),[])
        text=' '.join(n['text'] for n in card.texts)
        self.assertIn('2u',text);self.assertIn('3.24u',text);self.assertIn('40u',text)
        self.assertNotIn('$',text)
        self.assertEqual(pick,before)

    def test_private_personal_stake_is_never_assumed(self):
        pick=dict(self.rung(),personalTicket=True,parlayType='longshot',riskUnits=None)
        data=ticket_card.fun_data(pick,{},art=[{},{}])
        self.assertIsNone(data['units'])
        card=ticket_cards.ticket_card(data)
        self.assertEqual(ticket_kit.qa(card,'personal'),[])
        text=' '.join(n['text'] for n in card.texts)
        self.assertNotIn('$',text);self.assertNotIn('0.25u',text)

    def test_old_caption_is_preserved_but_current_send_refuses_private_cash(self):
        old=dict(self.rung(),publishedAt='2026-10-01T15:00:00Z')
        text=x_post.draft(old,{'league':'NFL'},history=[])
        self.assertIn('$50',text)
        self.assertTrue(social_style.privacy_issues(text))
        send=Mock()
        for private in ('$50 → $81', 'Bet ID: ABC123456', '50 dollars riding'):
            self.assertTrue(social_style.issues(private))
            with self.assertRaises(discord_post.DiscordError):
                discord_post.send_message('https://example.com/hook',private,send=send)
        send.assert_not_called()

    def test_units_reject_missing_or_invalid_amounts(self):
        for value in (None,True,float('nan'),-5):
            with self.assertRaises(ValueError):social_units.climb(value)
