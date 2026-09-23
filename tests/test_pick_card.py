import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pick_card

PICK = {'id': 'CFB-2026-W5-iowa-michigan-under-38-5-fd', 'title': 'Iowa at Michigan under 38.5', 'favorite': True,
        'marketType': 'total', 'direction': 'under', 'book': 'FanDuel', 'odds': -105, 'projection': 31.2, 'line': 38.5, 'confidence': 6}
GAME = {'league': 'CFB', 'kickoff': '2026-09-26T19:30Z',
        'home': {'id': '130', 'short': 'Michigan', 'abbreviation': 'MICH', 'color': '#00274c', 'alternateColor': '#ffcb05'},
        'away': {'id': '2294', 'short': 'Iowa', 'abbreviation': 'IOWA', 'color': '#231f20', 'alternateColor': '#fcd116'}}


class CardTests(unittest.TestCase):
    def test_the_svg_carries_the_picks_fields_the_kitchen_and_the_teams_colours(self):
        text = pick_card.svg(PICK, GAME, {'wins': 3, 'losses': 1, 'units': 1.98})
        for needle in ('Iowa at Michigan under 38.5', '-105', 'FanDuel', 'Our number 31.2 vs the 38.5', 'FAVORITE', 'KOOK’N',
                       'TODAY’S PLATE', 'Served at', 'Iowa at Michigan', 'Sat 3:30 PM ET', 'Record 3-1', '+1.98u',
                       'Confidence 6 of 10', 'keenroudy.com/sports', 'Graded in public'):
            self.assertIn(needle, text, needle)
        self.assertIn('#00274c', text, "a total wears the home team's colour")
        self.assertIn('#ffcb05', text, 'with its alternate as the accent')
        self.assertIn('#231f20', text, "and the away team's colour at the edge")
        nasty = pick_card.svg(dict(PICK, title='A&M <script> under 40', book='B&B'))
        self.assertIn('A&amp;M &lt;script&gt; under 40', nasty)
        self.assertNotIn('<script>', nasty)
        self.assertIn('TEAM PROP · FAVORITE', text)
        self.assertIn('>TEAM PROP<', pick_card.svg(dict(PICK, favorite=False, modelLean=True)))
        self.assertIn('>PLAYER PROP<', pick_card.svg(dict(PICK, favorite=False, modelLean=True, athleteId='1')))

    def test_a_parlay_card_lists_its_legs_and_serves_the_price_on_the_plate(self):
        ticket = {'title': '3-leg longshot at DraftKings', 'parlayType': 'longshot', 'odds': 650, 'book': 'DraftKings', 'confidence': 1,
                  'legs': [{'title': 'Bills at Lions over 44.5'}, {'title': 'Jets +3'}, {'title': 'Player Seven over 4.5 receptions'}]}
        text = pick_card.svg(ticket, GAME)
        for needle in ('FUN PARLAY', '3-leg parlay', '• Bills at Lions over 44.5', '• Jets +3', '• Player Seven over 4.5 receptions',
                       '+650', 'DraftKings', 'QUARTER UNIT · FOR FUN', 'KOOK’N'):
            self.assertIn(needle, text, needle)
        self.assertNotIn('Confidence', text)
        self.assertNotIn('Served at', text)
        many = pick_card.svg(dict(ticket, legs=[{'title': f'Leg {i}'} for i in range(7)]), GAME)
        self.assertIn('and 2 more', many)
        self.assertEqual(pick_card.play_kind(ticket), 'parlay')
        self.assertEqual(pick_card.play_kind({'market': 'rec'}), 'player')
        self.assertEqual(pick_card.play_kind({'marketType': 'spread'}), 'team')

    def test_the_side_the_play_is_on_picks_the_palette(self):
        spread_away = pick_card.svg({'title': 'Iowa +7', 'marketType': 'spread', 'direction': 'away', 'odds': -110, 'book': 'DK'}, GAME)
        self.assertLess(spread_away.index('#231f20'), spread_away.index('#00274c'), "the away spread leads with Iowa's colour")
        prop_home = pick_card.svg({'title': 'X over 4.5 receptions', 'athleteId': '9', 'odds': -110, 'book': 'DK'}, GAME, player_side='home')
        self.assertLess(prop_home.index('#00274c'), prop_home.index('#231f20'))
        self.assertEqual(pick_card.side_for({'athleteId': '9'}, GAME, 'away'), 'away')
        self.assertEqual(pick_card.side_for({'marketType': 'total', 'direction': 'over'}, GAME), 'home')

    def test_colours_fall_back_and_text_flips_on_a_light_team(self):
        primary, alternate = pick_card.team_colors({'league': 'CFB', 'home': {'abbreviation': 'ZZZ'}}, 'home', {})
        self.assertEqual(primary, pick_card.NEUTRAL)
        self.assertNotEqual(alternate, primary)
        light = pick_card.svg(dict(PICK), {'league': 'NFL', 'kickoff': GAME['kickoff'], 'home': {'short': 'Team', 'color': '#f5f5dc'}, 'away': {'short': 'Other', 'color': '#111111'}})
        self.assertIn(f'fill="{pick_card.INK}"', light, 'dark ink on a light background')
        self.assertGreater(pick_card.luminance('#ffffff'), pick_card.luminance('#000000'))
        self.assertEqual(pick_card.shade('#808080', 0.5), '#404040')

    def test_the_avatar_badge_rides_when_the_picture_exists_and_the_pan_otherwise(self):
        with_avatar = pick_card.svg(PICK, GAME, avatar='data:image/jpeg;base64,AAAA')
        self.assertIn('<image href="data:image/jpeg;base64,AAAA"', with_avatar)
        self.assertIn('clip-path="url(#badge)"', with_avatar)
        without = pick_card.svg(PICK, GAME, avatar='')
        self.assertNotIn('<image', without)
        self.assertIn('stroke-linecap="round"', without, 'the pan stands in')
        self.assertIsNone(pick_card.avatar_uri(Path('/nonexistent/kookn.jpg')))

    def test_long_titles_wrap_to_two_lines_and_only_then_trim(self):
        self.assertEqual(pick_card.title_lines('Courtland Sutton OVER 3.5 receptions'), ['Courtland Sutton', 'OVER 3.5 receptions'])
        self.assertEqual(pick_card.title_lines('Iowa at Michigan OVER 38.5'), ['Iowa at Michigan OVER 38.5'])
        text = pick_card.svg(dict(PICK, title='Courtland Sutton OVER 3.5 receptions'))
        self.assertIn('>Courtland Sutton<', text)
        self.assertIn('>OVER 3.5 receptions<', text)
        self.assertNotIn('…', text)
        text = pick_card.svg(dict(PICK, title='A very long pick title that would never fit on one line of a card, not even on two of them'))
        self.assertIn('…', text)
        ticket = pick_card.svg({'title': 't', 'parlayType': 'longshot', 'odds': 650, 'book': 'DK', 'gameIds': ['a', 'b'],
                                'legs': [{'title': 'x over 1'}, {'title': 'y under 2'}]}, GAME)
        self.assertIn('2 games · Sat Sep 26', ticket, 'a ticket names its game count and day, not one game')
        self.assertIn('Sep 26, 2026', ticket, "the corner carries the game's day, not the render day")
        self.assertNotIn('Iowa at Michigan', ticket)

    @unittest.skipUnless(os.environ.get('KEENROUDY_CARD_LIVE') == '1' and pick_card.chrome_path(), 'needs a browser and KEENROUDY_CARD_LIVE=1')
    def test_render_makes_a_png_with_the_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            out = pick_card.render(pick_card.svg(PICK, GAME), Path(folder) / 'card.png')
            self.assertGreater(out.stat().st_size, 10_000)
            self.assertEqual(out.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')


if __name__ == '__main__':
    unittest.main()
