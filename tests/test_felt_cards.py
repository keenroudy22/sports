import os
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import felt_cards
import pick_card
import research_art


GAME = {
    'league': 'NFL',
    'kickoff': '2026-10-08T00:15:00Z',
    'away': {'id': '1', 'abbreviation': 'BUF', 'short': 'Bills', 'color': '#00338D'},
    'home': {'id': '2', 'abbreviation': 'LAR', 'short': 'Rams', 'color': '#003594'},
}
PICK = {
    'id': 'NFL-2026-W5-buf-lar-under-54-5-dk',
    'title': 'Buffalo at Los Angeles under 54.5',
    'displayTitle': 'Buffalo at Los Angeles under 54.5',
    'marketType': 'total',
    'direction': 'under',
    'line': 54.5,
    'projection': 49.8,
    'odds': -110,
    'book': 'DraftKings',
    'publishedAt': '2026-10-07T04:05:00Z',
    'probabilityAtPublication': {'chance': .57, 'breakEven': .524, 'calibrated': True},
}


class FeltCardTests(unittest.TestCase):
    def felt(self):
        return mock.patch.dict(os.environ, {'KEENROUDY_CARD_THEME': 'felt'})

    def valid(self, text):
        ET.fromstring(text)
        self.assertEqual(pick_card.svg_size(text), (1080, 1350))
        self.assertIn('@font-face', text)
        self.assertIn('Barlow Condensed', text)
        self.assertIn('DM Sans', text)
        self.assertIn(felt_cards.FELT_NIGHT, text)
        self.assertIn('21+ · Entertainment only', text)

    def test_cutover_uses_publication_time_and_has_a_preview_override(self):
        with mock.patch.object(pick_card, 'FELT_FROM', '2026-10-07T04:00:00Z'):
            self.assertFalse(pick_card.felt_enabled({'publishedAt': '2026-10-07T03:59:59Z'}))
            self.assertTrue(pick_card.felt_enabled(PICK))
        with self.felt():
            self.assertTrue(pick_card.felt_enabled({}))
        self.assertIsNone(pick_card.FELT_FROM, 'renders are review-only until the dated cutover is approved')

    def test_every_felt_builder_renders_with_embedded_ofl_fonts(self):
        ticket = {
            'id': 'ticket', 'parlayType': 'longshot', 'odds': 750, 'book': 'FanDuel',
            'publishedAt': PICK['publishedAt'],
            'legs': [{'title': 'Josh Allen 225+ passing yards'}, {'title': 'Puka Nacua 50+ receiving yards'}],
        }
        climb = {
            'id': 'climb', 'parlayType': 'ladder', 'odds': 105, 'book': 'FanDuel',
            'publishedAt': PICK['publishedAt'], 'result': 'win',
            'legs': ticket['legs'],
            'ladder': {'run': 1, 'step': 2, 'stake': 75, 'payout': 154, 'banked': 19, 'bankedAfter': 50},
        }
        receipt = {
            'key': 'receipt:day:2026-10-07', 'due': '2026-10-08T13:00:00Z',
            'title': '1-1', 'when': 'Wednesday, Oct 7',
            'rows': [('win', 'Josh Allen over 224.5 passing yards', 'Final 267'),
                     ('loss', 'Puka Nacua over 69.5 receiving yards', 'Final 62')],
        }
        research = {
            'day': '2026-10-07', 'title': 'MATCHUP RESEARCH', 'kicker': 'EXACT MAIN LINES',
            'kind': 'matchup', 'accent': '#20C774',
            'rows': [{'title': 'Josh Allen over 224.5 passing yards', 'price': '-110 FanDuel',
                      'metric': '4/5 this season', 'detail': 'Fresh exact line'}],
        }
        with self.felt():
            cards = [
                pick_card.modern_svg(PICK, GAME, record={'wins': 2, 'losses': 4},
                                     art={'kind': 'logos', 'uris': ['data:image/png;base64,AA',
                                                                    'data:image/png;base64,BB']}),
                pick_card.ticket_svg(ticket),
                pick_card.ladder_svg(climb),
                pick_card.ladder_result_svg(dict(climb, settledAt='2026-10-08T03:30:00Z')),
                pick_card.receipt_svg(receipt),
                research_art.svg(research, {0: 'data:image/png;base64,AA'}),
            ]
        for card in cards:
            self.valid(card)

    def test_font_files_ship_with_their_ofl_licenses(self):
        for name in ('BarlowCondensed-Bold.ttf', 'DMSans-Variable.ttf',
                     'OFL-BarlowCondensed.txt', 'OFL-DMSans.txt'):
            self.assertGreater((ROOT / 'scripts' / 'fonts' / name).stat().st_size, 1000)


if __name__ == '__main__':
    unittest.main()
