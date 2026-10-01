import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sheet


def card(gid, kickoff, gap=0.0, league='NFL', week=3, **over):
    base = {'id': gid, 'league': league, 'kickoff': kickoff, 'state': 'pre', 'fcs': False, 'week': week,
            'away': {'abbr': f'A{gid}', 'id': '1', 'color': '#002244', 'alt': '#b0b7bc'},
            'home': {'abbr': f'H{gid}', 'id': '2', 'color': '#ffb612', 'alt': '#000000'},
            'v2': {'away': 20.4, 'home': 24.0, 'margin': 3.6, 'total': 44.4, 'winProb': 0.62, 'sparse': False},
            'market': {'spread': -2.5, 'total': 41.5},
            'value': {'spread': {'side': 'home', 'line': -2.5, 'odds': -105, 'book': 'FanDuel',
                                 'chance': .58, 'needs': .512, 'edge': 6.8, 'tier': 'strong', 'thin': False},
                      'total': {'side': 'over', 'line': 41.5, 'odds': -110, 'book': 'BetMGM',
                                'chance': .52, 'needs': .524, 'edge': -.4, 'tier': 'pass', 'thin': False}},
            'lean': {'side': 'home', 'spread': gap, 'spreadChance': 0.58, 'total': 2.9, 'totalChance': 0.52}}
    base.update(over)
    return base


SUNDAY = date(2026, 9, 27)


class PickTests(unittest.TestCase):
    def test_the_nfl_sheet_is_the_strongest_sunday_games_in_kickoff_order(self):
        cards = [card('late', '2026-09-27T20:25Z', gap=4), card('early', '2026-09-27T17:00Z', gap=5), card('mon', '2026-09-29T00:15Z'),
                 card('nov2', '2026-09-27T17:00Z', v2=None), card('started', '2026-09-27T17:00Z', state='in')]
        self.assertEqual([c['id'] for c in sheet.pick_games(cards, 'NFL', SUNDAY)], ['early', 'late'])

    def test_college_takes_the_biggest_gaps_and_no_fcs_game(self):
        cards = [card(f'g{i}', '2026-09-26T16:00Z', gap=float(i), league='CFB') for i in range(20)]
        cards.append(card('fcs', '2026-09-26T16:00Z', gap=40.0, league='CFB', fcs=True))
        picked = sheet.pick_games(cards, 'CFB', date(2026, 9, 26))
        self.assertEqual(len(picked), sheet.MOST)
        self.assertNotIn('fcs', [c['id'] for c in picked])
        self.assertNotIn('g0', [c['id'] for c in picked], 'the smallest gaps are left off')


class DrawTests(unittest.TestCase):
    def test_the_sheet_says_save_this_and_shows_every_number_the_games_page_does(self):
        games = [card('a', '2026-09-27T17:00Z', gap=2.4), card('b', '2026-09-27T20:25Z')]
        text = sheet.svg(games, 'NFL', SUNDAY, 3, {('a', 'away'): 'data:image/png;base64,x'})
        for needle in ('SAVE THIS', 'WEEK 3 NFL PROJECTIONS', 'Sunday, September 27', 'mint rings = real price value', 'Aa', 'Ha',
                       '20.4', '24.0', '62%', '38%', 'OUR NUMBER / MARKET', 'Ha -3.6', 'Ha -2.5 -105 FD', '44.4', 'O41.5 -110 MGM',
                       'Left: model · Right: market', 'data:image/png;base64,x', 'Entertainment only.'):
            self.assertIn(needle, text, needle)
        self.assertIn(sheet.ACCENT + '" font-size="31" font-weight="800">Ha -3.6', text,
                      'a spread our number leans to clearly is mint')
        self.assertIn('Mint: our chance clears the captured price.', text)
        self.assertIn('stroke="' + sheet.ACCENT + '" stroke-width="4"', text, 'watch games get a mint ring')

    def test_a_full_slate_uses_compact_tiles_and_numbers_the_four_best_priced_edges(self):
        games = [card(str(i), f'2026-09-27T{17 + i // 6:02d}:00Z', gap=float(i),
                      value={'spread': {'side': 'home', 'line': -2.5, 'odds': -105, 'book': 'FanDuel',
                                        'chance': .55 + i / 100, 'needs': .512, 'edge': float(i),
                                        'tier': 'lean' if i else 'pass', 'thin': False}}) for i in range(16)]
        text = sheet.svg(games, 'NFL', SUNDAY, 3)
        self.assertEqual(text.count('stroke="' + sheet.ACCENT + '" stroke-width="4"'), 4)
        for rank in ('>1</text>', '>2</text>', '>3</text>', '>4</text>'):
            self.assertIn(rank, text)
        self.assertIn('>SPREAD</text>', text)
        self.assertIn('-2.5 -105 FD', text)
        self.assertNotIn('OUR NUMBER / MARKET', text, 'compact tiles keep the comparison on one line')

    def test_the_watch_badge_names_the_market_with_value_after_price(self):
        total = card('total', '2026-09-27T17:00Z', gap=20.0,
                     value={'total': {'side': 'under', 'line': 44.5, 'odds': 100, 'book': 'BetMGM',
                                      'chance': .56, 'needs': .5, 'edge': 6.0, 'tier': 'strong', 'thin': False}})
        spread = card('spread', '2026-09-27T20:25Z', gap=7.0)
        text = sheet.svg([total, spread], 'NFL', SUNDAY, 3)
        self.assertIn('>TOTAL</text>', text)
        self.assertIn('>SPREAD</text>', text)
        self.assertEqual(sheet.priced_watch(total)[1], 'TOTAL')

    def test_an_unpriced_gap_and_a_paused_market_are_not_highlighted(self):
        unpriced = card('gap', '2026-09-27T17:00Z', gap=30, value=None)
        paused = card('paused', '2026-09-27T20:25Z', gap=30,
                      value={'total': {'side': 'over', 'line': 41.5, 'odds': -105, 'book': 'FanDuel',
                                       'chance': .60, 'needs': .512, 'edge': 8.8, 'tier': 'strong',
                                       'paused': True, 'thin': False}})
        text = sheet.svg([unpriced, paused], 'NFL', SUNDAY, 3)
        self.assertNotIn('stroke="' + sheet.ACCENT + '" stroke-width="4"', text)

    def test_a_dark_team_colour_gives_way_to_one_that_shows(self):
        self.assertEqual(sheet.readable({'color': '#5a1414', 'alt': '#ffb612'}), '#ffb612')
        self.assertEqual(sheet.readable({'color': '#d50a0a', 'alt': '#34302b'}), '#d50a0a')
        light = sheet.readable({'color': '#241773', 'alt': '#ffffff'})
        self.assertNotIn(light, ('#241773', '#ffffff'), 'lightened, never plain white')
        self.assertEqual(sheet.readable({}), sheet.ACCENT)


class PostTests(unittest.TestCase):
    GAMES = {f'g{i}': {'id': f'g{i}', 'league': 'NFL', 'week': 3, 'kickoff': '2026-09-27T17:00Z'} for i in range(5)}

    def test_the_sheet_posts_at_ten_on_its_day_with_the_ask_first(self):
        early = datetime(2026, 9, 27, 10, 45, tzinfo=timezone.utc)       # 6:45 AM ET Sunday
        post = sheet.post(self.GAMES, early)
        self.assertEqual((post['key'], post['kind'], post['card']), ('sheet:NFL:2026-09-27', 'sheet', 'sheet-nfl-2026-09-27'))
        self.assertEqual(post['text'], '📌 Full NFL projections for the slate.\n'
                                       'Mint rings mark up to 4 real-price value spots (not official plays). Save this one.\n#NFL')
        self.assertEqual(post['due'], datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc))
        import receipts
        self.assertEqual(receipts.guard(post), [])
        self.assertIsNone(sheet.post(self.GAMES, datetime(2026, 9, 27, 16, 0, tzinfo=timezone.utc)), 'past 11:45 AM it is too late')
        self.assertIsNone(sheet.post(self.GAMES, datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)), 'Monday is not the NFL sheet day')
        few = dict(list(self.GAMES.items())[:3])
        self.assertIsNone(sheet.post(few, early), 'a thin slate gets no sheet')


if __name__ == '__main__':
    unittest.main()
