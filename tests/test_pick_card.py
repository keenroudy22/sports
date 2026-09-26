import os
import sys
import tempfile
import unittest
from unittest import mock
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
        for needle in ('>Iowa at Michigan<', '>under 38.5<', '-105', 'FanDuel', 'We project 31.2 total points', 'FAVORITE', 'KOOK’N',
                       'TODAY’S PLATE', 'Served at', 'Iowa at Michigan', 'Sat 3:30 PM ET', 'Record 3-1',
                       'keenroudy.com/sports', 'Graded in public', 'Entertainment only. Not advice.'):
            self.assertIn(needle, text, needle)
        self.assertNotIn(' unit', text, 'no units on X, the post or the card')
        self.assertNotIn('1.98', text, 'a record on a card is wins and losses, never units')
        self.assertIn('#00274c', text, "a total wears the home team's colour")
        self.assertIn('#ffcb05', text, 'with its alternate as the accent')
        self.assertIn('#231f20', text, "and the away team's colour at the edge")
        nasty = pick_card.svg(dict(PICK, title='A&M <script> under 40', book='B&B'))
        self.assertIn('A&amp;M &lt;script&gt; under 40', nasty)
        self.assertNotIn('<script>', nasty)
        self.assertIn('TEAM PROP · FAVORITE', text)
        self.assertIn('>TEAM PROP<', pick_card.svg(dict(PICK, favorite=False, modelLean=True)))
        self.assertIn('>PLAYER PROP<', pick_card.svg(dict(PICK, favorite=False, modelLean=True, athleteId='1')))

    def test_a_player_prop_wears_his_photo_a_team_prop_the_logos_a_parlay_the_chef(self):
        asked = []
        fetch = lambda url: asked.append(url) or f'data:image/png;base64,{len(asked)}'
        nfl = {'league': 'NFL', 'away': {'id': '1', 'abbreviation': 'ATL'}, 'home': {'id': '9', 'abbreviation': 'GB'}}
        prop = dict(PICK, athleteId='4241389', market='rec', title='Drake London under 5.5 receptions')
        self.assertEqual(pick_card.artwork(prop, nfl, fetch), {'kind': 'photo', 'uri': 'data:image/png;base64,1'})
        self.assertEqual(asked[-1], 'https://a.espncdn.com/i/headshots/nfl/players/full/4241389.png')
        total = pick_card.artwork(dict(PICK, athleteId=None), nfl, fetch)
        self.assertEqual((total['kind'], len(total['uris'])), ('logos', 2))
        self.assertEqual(asked[-2:], ['https://a.espncdn.com/i/teamlogos/nfl/500/atl.png', 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png'])
        spread = pick_card.artwork(dict(PICK, athleteId=None, marketType='spread', direction='home'), dict(GAME, league='CFB'), fetch)
        self.assertEqual(len(spread['uris']), 1, "a spread wears its side's logo")
        self.assertIn('/ncaa/500/', asked[-1])
        self.assertIsNone(pick_card.artwork({'legs': [{'title': 'x'}], 'parlayType': 'longshot'}, nfl, fetch), 'a parlay keeps the chef')
        self.assertIsNone(pick_card.artwork(prop, nfl, lambda url: None), 'a failed fetch keeps the chef')
        with mock.patch.object(pick_card, 'CARD_ART', False):
            self.assertIsNone(pick_card.artwork(prop, nfl, fetch), 'the switch turns every picture off')
        photo = pick_card.svg(prop, nfl, art={'kind': 'photo', 'uri': 'data:image/png;base64,PHOTO'})
        self.assertIn('base64,PHOTO', photo)
        self.assertNotIn(pick_card.avatar_uri(pick_card.CHEF)[:120], photo, 'the chef steps aside for the player')
        logos = pick_card.svg(PICK, GAME, art={'kind': 'logos', 'uris': ['data:image/png;base64,AWAY', 'data:image/png;base64,HOME']})
        self.assertLess(logos.index('base64,AWAY'), logos.index('base64,HOME'), 'away on the left, home on the right, as the title reads')
        self.assertIn(pick_card.avatar_uri(pick_card.CHEF)[:120], pick_card.svg(PICK, GAME), 'no art, the chef')

    def test_a_parlay_card_lists_its_legs_in_the_same_frame(self):
        ticket = {'title': '3-leg longshot at DraftKings', 'parlayType': 'longshot', 'odds': 650, 'book': 'DraftKings', 'confidence': 1, 'riskUnits': 0.25,
                  'legs': [{'title': 'Bills at Lions over 44.5'}, {'title': 'Jets +3'}, {'title': 'Player Seven over 4.5 receptions'}]}
        text = pick_card.svg(ticket, GAME)
        for needle in ('FUN PARLAY', '3-leg parlay', '• Bills at Lions over 44.5', '• Jets +3', '• Player Seven over 4.5 receptions',
                       '+650', 'DraftKings', 'Served at', 'KOOK’N'):
            self.assertIn(needle, text, needle)
        self.assertNotIn(' unit', text)
        many = pick_card.svg(dict(ticket, legs=[{'title': f'Leg {i}'} for i in range(7)]), GAME)
        self.assertIn('and 3 more', many, 'five legs fit; past that, four and a count')
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

    def test_every_card_serves_the_chef_on_the_plate_and_the_pan_in_the_corner(self):
        ticket = {'title': 't', 'parlayType': 'longshot', 'odds': 650, 'book': 'DK', 'legs': [{'title': 'x over 1'}, {'title': 'y under 2'}]}
        prop = dict(PICK, favorite=False, modelLean=True, athleteId='1')
        for pick in (PICK, prop, ticket):
            card = pick_card.svg(pick, GAME, avatar='data:image/png;base64,AAAA')
            self.assertEqual(card.count('<image href="data:image/png;base64,AAAA"'), 1, 'one chef, on the plate')
            self.assertIn('clip-path="url(#plate)"', card)
            self.assertIn('stroke-linecap="round"', card, 'the pan marks the corner')
            self.assertIn('Served at', card, 'every kind prices on the same line')
        self.assertNotIn('<image', pick_card.svg(PICK, GAME, avatar=''), 'no picture, an empty plate')
        self.assertIsNone(pick_card.avatar_uri(Path('/nonexistent/kookn.jpg')))
        self.assertTrue(pick_card.CHEF.exists(), 'the cutout ships with the site')
        self.assertTrue(pick_card.avatar_uri(pick_card.CHEF).startswith('data:image/png;base64,'))

    def test_college_teams_are_named_by_school(self):
        game = {'league': 'CFB', 'kickoff': '2026-09-26T22:30Z',
                'away': {'id': '2117', 'short': 'C Michigan', 'abbreviation': 'CMU', 'school': 'Central Michigan'},
                'home': {'id': '2390', 'short': 'Miami', 'abbreviation': 'MIA', 'school': 'Miami'}}
        pick = {'id': 'CFB-2026-W4-cmu-mia-under-54-br', 'title': 'C Michigan at Miami under 54', 'marketType': 'total'}
        self.assertEqual(pick_card.display_title(pick, game), 'Central Michigan at Miami (FL) under 54')
        self.assertIn('Central Michigan at Miami (FL) · Sat 6:30 PM ET', pick_card.svg(dict(pick, odds=-109, book='BetRivers'), game))
        ohio = dict(game, home={'id': '193', 'short': 'Miami OH', 'abbreviation': 'M-OH', 'school': 'Miami (OH)'})
        self.assertEqual(pick_card.team_label(ohio['home'], 'CFB'), 'Miami (OH)')
        self.assertEqual(pick_card.team_label({'short': 'Bills', 'abbreviation': 'BUF'}, 'NFL'), 'Bills')
        self.assertEqual(pick_card.display_title({'title': 'Player Seven OVER 4.5 receptions', 'athleteId': '7'}, game),
                         'Player Seven OVER 4.5 receptions', 'a player prop is named by the player')
        self.assertEqual(pick_card.display_title({'title': 'Iowa at Michigan OVER 38.5', 'marketType': 'total'}, None),
                         'Iowa at Michigan over 38.5', 'a team play says over in lowercase like every other')

    def test_the_number_line_says_what_we_project_in_plain_words(self):
        total = {'marketType': 'total', 'direction': 'over', 'line': 38.5, 'projection': 47.1}
        self.assertEqual(pick_card.number_line(total), 'We project 47.1 total points')
        self.assertEqual(pick_card.number_line({'direction': 'under', 'line': 38.5, 'projection': 31.0}), 'We project 31 total points')
        prop = {'athleteId': '7', 'market': 'rec', 'direction': 'under', 'line': 5.5, 'projection': 4.6}
        self.assertEqual(pick_card.number_line(prop), 'We project 4.6 receptions')
        self.assertEqual(pick_card.number_line(dict(prop, market='recYds', line=49.5, projection=61.2)), 'We project 61.2 receiving yards')
        side = {'marketType': 'spread', 'direction': 'home', 'line': -10.0, 'projection': -14.2}
        self.assertEqual(pick_card.number_line(side), 'Our number -14.2 vs the -10', 'a side keeps the comparison')
        self.assertEqual(pick_card.number_line({'line': 38.5}), '', 'no projection, no line')

    def test_long_titles_wrap_to_two_lines_and_only_then_trim(self):
        self.assertEqual(pick_card.title_lines('Courtland Sutton OVER 3.5 receptions'), ['Courtland Sutton', 'OVER 3.5 receptions'])
        self.assertEqual(pick_card.title_lines('Iowa at Michigan OVER 38.5'), ['Iowa at Michigan', 'OVER 38.5'], 'long enough to reach the plate: two lines')
        self.assertEqual(pick_card.title_lines('Navy at UAB over 51.5'), ['Navy at UAB over 51.5'])
        text = pick_card.svg(dict(PICK, title='Courtland Sutton OVER 3.5 receptions', athleteId='4', market='rec'))
        self.assertIn('>Courtland Sutton<', text)
        self.assertIn('>OVER 3.5 receptions<', text)
        self.assertNotIn('…', text)
        text = pick_card.svg(dict(PICK, title='A very long pick title that would never fit on one line of a card, not even on two of them'))
        self.assertIn('…', text)
        ticket = pick_card.svg({'title': 't', 'parlayType': 'longshot', 'odds': 650, 'book': 'DK', 'gameIds': ['a', 'b'],
                                'legs': [{'title': 'x over 1'}, {'title': 'y under 2'}]}, GAME)
        self.assertIn('2 games · Sat Sep 26', ticket, 'a ticket names its game count and day, not one game')
        plain = pick_card.svg(PICK, GAME)
        self.assertNotIn('Confidence', plain, 'no confidence score on a card')
        self.assertNotIn('2026', plain, 'no date in the corner: the game line says the day')
        self.assertNotIn('Iowa at Michigan', ticket)

    @unittest.skipUnless(os.environ.get('KEENROUDY_CARD_LIVE') == '1' and pick_card.chrome_path(), 'needs a browser and KEENROUDY_CARD_LIVE=1')
    def test_render_makes_a_png_with_the_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            out = pick_card.render(pick_card.svg(PICK, GAME), Path(folder) / 'card.png')
            self.assertGreater(out.stat().st_size, 10_000)
            self.assertEqual(out.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')


if __name__ == '__main__':
    unittest.main()
