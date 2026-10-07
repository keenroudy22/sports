import copy
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import felt_cards
import pick_card
import research_art
import sheet


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
        self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'legacy')
        with mock.patch.object(pick_card, 'FELT_FROM', '2026-10-07T04:00:00Z'):
            self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'felt')
        with mock.patch.object(pick_card, 'FELT_FROM', '2026-10-07'):
            self.assertTrue(pick_card.felt_enabled(PICK), 'a date-only cutover is timezone-safe')
            self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'felt')
        with mock.patch.dict(os.environ, {'KEENROUDY_FELT_FROM': '2026-10-01'}, clear=False):
            self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'legacy',
                             'a Mac-only override cannot relabel the hosted renderer')

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

    def test_open_ticket_stub_is_neutral_and_receipt_uses_the_supplied_straight_headline(self):
        with self.felt():
            play = pick_card.modern_svg(PICK, GAME, record={'wins': 35, 'losses': 35})
            receipt = pick_card.receipt_svg({
                'title': '2-3', 'when': 'Sunday, Oct 4', 'season': '35–35',
                'rows': [('loss', 'One under 1.5 receptions', 'Final: 2', 'player'),
                         ('win', 'Two under 2.5 receptions', 'Final: 1', 'player'),
                         ('win', 'Three over 3.5 receptions', 'Final: 4', 'player'),
                         ('loss', 'Four under 48', 'Final: 57', 'team'),
                         ('loss', 'Five under 48.5', 'Final: 55', 'team'),
                         ('win', '80/20 Climb step 2', '$75 → $117', 'ladder'),
                         ('loss', '3-leg parlay', '2/3 legs hit', 'parlay')],
            })
        self.assertIn('data-zone="open-stub"', play)
        self.assertIn(f'data-zone="open-stub" x="826"', play)
        self.assertIn(f'fill="{felt_cards.FELT_RAISED}"', play)
        self.assertIn('SEASON 35–35', play)
        self.assertIn('>BEST BETS<', receipt)
        self.assertIn('>2–3<', receipt)
        self.assertIn('SEASON 35–35', receipt)
        self.assertIn('FUN TICKETS 0–1 · CLIMB STEP 2 ✓ · TRACKED APART', receipt)
        self.assertNotIn('+2 MORE ON THE PUBLIC RECORD', receipt)
        self.assertNotIn('SEASON 2-3', receipt)

    def test_research_climb_and_longshot_preserve_public_rules(self):
        ticket = {'id': 't', 'parlayType': 'longshot', 'odds': 700, 'book': 'FanDuel',
                  'gameIds': ['g', 'g2', 'g3', 'g4', 'g5'],
                  'legs': [{'title': 'Game over 40.5'}]}
        choice = {'kind': 'matchup', 'title': 'MATCHUP TRENDS', 'kicker': 'EXACT LINE + OPPONENT DEFENSE',
                  'rows': [{'title': 'Bucky Irving over 13.5 carries', 'price': '-107 DK',
                            'metric': '8/10 exact-line trend', 'detail': 'DAL allows 24.2 carries/game to RBs',
                            'kickoff': '2026-10-09T00:15:00Z', 'matchupLabel': 'TB at DAL',
                            'opponentAbbr': 'DAL', 'statLabel': 'carries', 'hits': 8, 'games': 10,
                            'seasonHits': 3, 'seasonGames': 4,
                            'historyValues': [16, 18, 12, 20, 15, 22, 14, 19, 8, 17],
                            'matchup': {'rank': 23, 'of': 32, 'pos': 'RB', 'stat': 'car',
                                        'value': 24.2, 'supports': True}}]}
        climb = {'id': 'c', 'parlayType': 'ladder', 'odds': -173, 'book': 'FanDuel',
                 '_allClimbsBanked': 42, 'legs': [{'title': 'One 10+ yards'}, {'title': 'Two 10+ yards'}],
                 'ladder': {'run': 3, 'step': 1, 'stake': 50, 'payout': 79, 'banked': 0, 'start': 50},
                 'result': 'loss', 'actual': 'legs: loss, win'}
        with self.felt():
            longshot = pick_card.ticket_svg(ticket, GAME, art=[{'kind': 'logos', 'uris': ['data:image/png;base64,AA', 'data:image/png;base64,BB']}])
            research = research_art.svg(choice)
            open_climb = pick_card.ladder_svg(dict(climb, result=None))
            result = pick_card.ladder_result_svg(climb)
        self.assertNotIn('#B49BE0', longshot)
        self.assertEqual(longshot.count('<image href="data:image/png;base64,'), 2)
        self.assertIn('5 games · Wed Oct 7', longshot)
        self.assertIn('Over 13.5 in 8 of his last 10 games', research)
        self.assertIn('DAL allows 24.2 carries a game to RBs, 23rd of 32', research)
        self.assertIn('LAST 10 GAMES', research)
        self.assertIn('fill="' + felt_cards.BURNT + '"', research)
        self.assertIn('3 of 4 this season', research)
        self.assertNotIn('8 of 10 this season', research)
        self.assertEqual(research.count('8/10'), 0)
        self.assertNotIn('EXACT-LINE PROOF', research)
        self.assertNotIn('PROOF POINT', research)
        self.assertNotIn('POSITIVE RESEARCH LABEL', research)
        self.assertIn('ALL CLIMBS  $42 BANKED', open_climb)
        self.assertIn('NEXT  $50 RESTART', result)
        self.assertIn('$1,000', result)
        self.assertIn('>✗<', result)
        self.assertIn('>✓<', result)

    def test_weekly_receipt_uses_category_records_without_push_badges(self):
        weekly = {
            'title': '7-7', 'when': 'Sep 30 to Oct 6', 'season': '35–35',
            'rows': [(None, 'Player props 6-2', '', 'player'),
                     (None, 'Game lines 1-5', '', 'team'),
                     (None, 'Fun parlays 0-5', '', 'parlay'),
                     (None, 'Ladder 1-2', '', 'ladder')],
        }
        with self.felt():
            card = pick_card.receipt_svg(weekly)
        self.valid(card)
        self.assertIn('>BEST BETS<', card)
        self.assertIn('>7–7<', card)
        self.assertEqual(card.count('data-zone="category-record"'), 4)
        self.assertIn('>PLAYER PROPS<', card)
        self.assertIn('>GAME LINES<', card)
        self.assertIn('>FUN TICKETS<', card)
        self.assertIn('>80/20 CLIMB<', card)
        self.assertNotIn('PUSH', card)
        self.assertNotIn('>LADDER<', card)

    def test_daily_receipt_without_best_bets_uses_the_matching_public_label(self):
        with self.felt():
            fun = pick_card.receipt_svg({
                'title': 'Fun parlays 0-3', 'when': 'Monday, Oct 5',
                'rows': [('loss', 'Three-leg ticket', '2/3 legs hit', 'parlay')],
            })
            climb = pick_card.receipt_svg({
                'title': 'Ladder 1-2', 'when': 'Monday, Oct 5',
                'rows': [('loss', '80/20 Climb step 1', 'One leg hit', 'ladder')],
            })
        self.assertIn('>FUN TICKETS<', fun)
        self.assertIn('>0–3<', fun)
        self.assertNotIn('>BEST BETS<', fun)
        self.assertIn('>80/20 CLIMB<', climb)
        self.assertIn('>1–2<', climb)
        self.assertNotIn('>BEST BETS<', climb)
        self.assertNotIn('>LADDER<', climb)

    def test_felt_projection_sheet_is_native_and_uses_the_real_date(self):
        game = {'id': 'g', 'league': 'CFB', 'week': 6,
                'away': {'abbr': 'NMSU'}, 'home': {'abbr': 'FIU'},
                'v2': {'away': 20.1, 'home': 27.3, 'margin': 7.2, 'total': 47.4},
                'market': {'spread': -6.5, 'total': 48.5},
                'value': {'spread': {'side': 'home', 'line': -3.5, 'odds': 100,
                                     'book': 'theScore Bet', 'edge': 3.8, 'chance': .538, 'needs': .5,
                                     'tier': 'lean', 'thin': False,
                                     'observedAt': '2026-10-10T13:00:00Z'}}}
        from datetime import date
        with self.felt():
            card = sheet.svg([game], 'CFB', date(2026, 10, 10), 6,
                             now=datetime(2026, 10, 10, 14, tzinfo=timezone.utc))
        self.valid(card)
        self.assertIn('Saturday, October 10', card)
        self.assertIn('LIKE #1  FIU -3.5 +100 theScore Bet', card)
        self.assertIn('20.1–27.3', card)
        self.assertIn('rings name the lines we like · watches, not picks', card)
        self.assertIn('theScore Bet', card)
        self.assertNotIn('ESPN', card)
        self.assertNotIn('Mint:', card)
        self.assertNotIn('January 3', card)
        self.assertIn(f'fill="{felt_cards.CHALK}"', card)

    def test_compact_projection_sheet_keeps_ring_caution_and_text_inside_tiles(self):
        from datetime import date
        template = {'league': 'CFB', 'week': 6,
                    'away': {'abbr': 'UNC'}, 'home': {'abbr': 'PITT'},
                    'v2': {'away': 19.2, 'home': 31.1, 'margin': 11.9, 'total': 50.3},
                    'lean': {'spread': 11.1},
                    'market': {'spread': -3.5, 'total': 49.5},
                    'value': {}}
        games = []
        for index in range(16):
            row = copy.deepcopy(template)
            row['id'] = f'g{index}'
            row['away']['abbr'] = 'HAW' if index == 15 else f'A{index}'
            row['home']['abbr'] = 'ASU' if index == 15 else f'H{index}'
            games.append(row)
        games[0]['away']['abbr'] = 'UNC'
        games[0]['home']['abbr'] = 'PITT'
        games[0]['value']['spread'] = {'side': 'home', 'line': -3.5, 'odds': -105,
                                             'book': 'theScore Bet', 'edge': 4.2, 'chance': .552,
                                             'needs': .512, 'tier': 'lean', 'thin': False,
                                             'observedAt': '2026-10-10T13:00:00Z'}
        with self.felt():
            card = sheet.svg(games, 'CFB', date(2026, 10, 10), 6,
                             now=datetime(2026, 10, 10, 14, tzinfo=timezone.utc))
        self.valid(card)
        self.assertIn('LIKE #1  PITT -3.5 −105 theScore Bet', card)
        self.assertIn('11.1-PT COLLEGE GAP · CAUTION', card)
        self.assertIn(f'fill="{felt_cards.KOOKD}"', card)
        self.assertIn(f'>19.2–31.1</text>', card)
        self.assertNotIn('>SCORE<', card)
        self.assertNotIn('>BR<', card)
        self.assertLessEqual(felt_cards.fit_size('SPREAD  OUR PITT −11.9  ·  MARKET PITT -3.5 −105 theScore Bet',
                                                 23, 430), 23)

    def test_four_letter_team_fallback_fits_its_badge(self):
        chip = felt_cards.team_chip(40, 40, {'abbr': 'NMSU'}, 34)
        self.assertIn('font-size="19"', chip)


if __name__ == '__main__':
    unittest.main()
