import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import parlay_caption
import buffer_post
import x_post
from unittest.mock import patch
from datetime import datetime, timedelta, timezone


class ParlayCaptionTests(unittest.TestCase):
    def test_schedule_sends_identical_leg_lines_to_x_and_discord(self):
        now = datetime(2026, 10, 22, 18, tzinfo=timezone.utc)
        key = 'community:personal-ticket:test'
        item = dict(odds=500, book='FanDuel', personalTicket=True,
                    legs=['A 20+ points', 'B 6+ rebounds'])
        expected = parlay_caption.owner_ticket(item)
        with patch.object(buffer_post, 'create_post', return_value='test-id') as send:
            log = buffer_post.schedule([(key, 'community', 'A 20+, B 6+', now + timedelta(hours=1), None)],
                                      'channel', {'posts': []}, now, items={key: item}, log=lambda *_: None)
        self.assertEqual(send.call_args.args[0], expected)
        self.assertEqual(log['posts'][0]['discord']['text'], expected)
        self.assertEqual(log['posts'][0]['discord']['destination'], 'plays')

    def test_oversized_ticket_never_sent_as_partial_or_paragraph(self):
        now = datetime(2026, 10, 22, 18, tzinfo=timezone.utc)
        key = 'community:personal-ticket:test'
        item = dict(odds=500, book='FanDuel', legs=[f'Long Player Name {i} 200+ passing yards' for i in range(10)])
        with patch.object(buffer_post, 'create_post') as send:
            log = buffer_post.schedule([(key, 'community', 'All legs on card', now + timedelta(hours=1), None)],
                                      'channel', {'posts': []}, now, items={key: item}, log=lambda *_: None)
        send.assert_not_called()
        self.assertEqual(log['posts'], [])

    def test_each_leg_and_blank_heading(self):
        legs = ['A 20+ points', 'B 6+ rebounds', 'C 4+ assists']
        text = parlay_caption.layout('My lotto +500', legs, '#NBA')
        self.assertEqual(text, 'My lotto +500\n\nA 20+ points\nB 6+ rebounds\nC 4+ assists\n\n#NBA')
        self.assertEqual(buffer_post.without_playbook(text), text)

    def test_owner_period_boost_and_all_legs_preserved(self):
        item = dict(odds=668, book='FanDuel', priceBoosted=True, baseOdds=446,
                    legs=['Hunter Henry over 0.5 first-quarter receiving yards', 'B 6+ rebounds'])
        text = parlay_caption.owner_ticket(item)
        self.assertIn('+668 FanDuel boosted (+446 before boost)', text)
        self.assertIn('\n\nHunter Henry over 0.5 1Q rec yds\nB 6+ rebounds', text)

    def test_long_ticket_not_truncated(self):
        legs = [f'Player Number {i} 200+ passing yards' for i in range(10)]
        text = parlay_caption.owner_ticket(dict(odds=2013, book='FanDuel', legs=legs))
        self.assertGreater(x_post.tweet_length(text), x_post.LIMIT)
        self.assertEqual(len(text.split('\n\n')[1].splitlines()), 10)

    def test_invalid_leg_rejected(self):
        for leg in ('', 'A\nB', 'A\rB'):
            with self.assertRaises(ValueError):
                parlay_caption.layout('ticket', [leg])
