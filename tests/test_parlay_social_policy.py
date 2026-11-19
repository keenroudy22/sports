from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import receipts
import morning_brief
import ticket_card


class ParlaySocialPolicy(unittest.TestCase):
    def test_mixed_card_keeps_all_units_and_straight_losses(self):
        rows = [
            dict(id='a', title='Home spread', odds=-110, riskUnits=1, result='loss', actual='lost by 3'),
            dict(id='b', title='Two-leg ticket', odds=213, book='DraftKings', riskUnits=.25,
                 result='loss', legs=[{}, {}], settledAt='2026-11-20T04:00:00Z'),
        ]
        self.assertTrue(receipts.quiet_parlay_result(rows[1]))
        self.assertFalse(receipts.quiet_parlay_result(dict(rows[1], result='win')))
        self.assertFalse(receipts.quiet_parlay_result(dict(rows[1], parlayType='ladder')))
        self.assertFalse(receipts.quiet_parlay_result(dict(rows[1], settledAt='2026-11-19T03:00:00Z')))
        self.assertIsNone(receipts.prior_individual_results_hold(rows[1:], {'posts': [
            dict(id='b', sentAt='2026-11-19T18:00Z', tweetId='123456789')]}, 'x'))
        svg=ticket_card.daily_result_svg(rows, '2026-11-19')
        self.assertIn('NET -1.25u',svg)
        self.assertIn('2 PLAYS TOTAL',svg)
        self.assertNotIn('Two-leg ticket',svg)

    def test_private_screening_notes_do_not_become_morning_posts(self):
        now=datetime(2026,11,19,13,tzinfo=timezone.utc)
        with patch.object(morning_brief, 'current',return_value={'text':'Missing: no supporting reason'}):
            self.assertIsNone(morning_brief.post(now))
            self.assertIsNone(morning_brief.public_brief(now))
