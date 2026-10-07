"""Kitchen Ticket v2 preview: exact pick facts and ESPN art routing."""
import base64
import sys
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pick_card
import ticket_card
import ticket_climb_map
import feed


GAME = {
    'league': 'CFB', 'kickoff': '2026-10-07T23:30:00Z',
    'away': {'id': '166', 'abbreviation': 'NMSU', 'school': 'New Mexico State',
             'color': '#7E141B', 'alternateColor': '#231F20'},
    'home': {'id': '2229', 'abbreviation': 'FIU', 'school': 'Florida International',
             'color': '#091F3F', 'alternateColor': '#C3993F'},
}
PROP = {
    'id': 'CFB-2026-W6-king-over-49-5-recyds-dk', 'title': 'TK King OVER 49.5 receiving yards',
    'athleteId': '4869443', 'market': 'recYds', 'direction': 'over', 'line': 49.5,
    'odds': -102, 'book': 'DraftKings', 'riskUnits': 1,
    'probabilityAtPublication': {'chance': .537, 'breakEven': .505, 'calibrated': True},
    'reasoning': {'history': 'Last 10 games: 5 of 10 over 49.5.'},
}


class TicketCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = ('data:image/png;base64,' + base64.b64encode((ROOT / 'site' / 'kookn-mark.png').read_bytes()).decode('ascii'))
        cls.logo = ('data:image/png;base64,' + base64.b64encode((ROOT / 'site' / 'kookn-chef.png').read_bytes()).decode('ascii'))

    def test_player_photo_comes_from_espn_id_and_survives_one_failed_fetch(self):
        calls = []
        def fetch(url):
            calls.append(url)
            return None if len(calls) == 1 else self.image
        art = pick_card.artwork(PROP, GAME, fetch=fetch, player_side='away')
        self.assertEqual(art['kind'], 'photo')
        self.assertEqual(calls, [pick_card.HEADSHOT.format(sport='college-football', athlete='4869443')] * 2)

    def test_real_prop_shape_shows_exact_price_units_and_photo_without_season_or_helpline(self):
        data = ticket_card.straight_data(PROP, GAME, player_side='away',
                                         art={'kind': 'photo', 'uri': self.image}, fetch=lambda _: self.logo)
        self.assertEqual(data['team'], 'NMSU')
        self.assertEqual(data['photo'], self.image)
        svg = ticket_card.straight_svg(PROP, GAME, player_side='away',
                                       art={'kind': 'photo', 'uri': self.image}, fetch=lambda _: self.logo)
        for exact in ('OVER 49.5', 'DRAFTKINGS', '53.7%', '50.5%', '1u', '21+ · Entertainment only',
                      'ORDER UP'):
            self.assertIn(exact, svg)
        self.assertNotIn('LAST 10 GAMES: 5 OF 10', svg, '50% history does not support a 50.5%-needed side')
        self.assertNotIn('>WHY<', svg)
        self.assertNotIn('BEST BETS THIS SEASON', svg)
        self.assertNotIn('1-800-', svg)
        self.assertEqual(svg.count(self.image), 1, 'the headshot is embedded once and reused')

    def test_why_requires_supporting_saved_evidence(self):
        self.assertIsNone(ticket_card.supporting_reason(PROP))
        strong = dict(PROP, reasoning={'history': 'Last 10 games: 7 of 10 over 49.5.'})
        self.assertEqual(ticket_card.supporting_reason(strong), 'Last 10 games: 7 of 10 over 49.5.')
        opposite = dict(PROP, reasoning={'history': 'Last 10 games: 8 of 10 under 49.5.'})
        self.assertIsNone(ticket_card.supporting_reason(opposite))
        thin = dict(PROP, reasoning={'history': 'Last 4 games: 4 of 4 over 49.5.'})
        self.assertIsNone(ticket_card.supporting_reason(thin))

    def test_featured_card_uses_hot_plate_potd_chip(self):
        svg = ticket_card.straight_svg(PROP, GAME, featured=True, player_side='away',
                                       art={'kind': 'photo', 'uri': self.image}, fetch=lambda _: self.logo)
        self.assertIn('HOT PLATE (POTD)', svg)
        self.assertNotIn('>BEST BET<', svg)

    def test_game_line_uses_both_team_logos_not_a_player_photo(self):
        pick = dict(PROP, athleteId=None, market=None, marketType='total',
                    title='NMSU at FIU over 46.5', line=46.5, odds=-110)
        data = ticket_card.straight_data(pick, GAME, fetch=lambda _: self.image)
        self.assertEqual(data['kind'], 'game')
        self.assertEqual((data['away_logo'], data['home_logo']), (self.image, self.image))
        svg = ticket_card.straight_svg(pick, GAME, fetch=lambda _: self.image)
        self.assertIn('TOTAL', svg)
        self.assertIn('OVER 46.5', svg)

    def test_climb_map_uses_ledger_rows_and_labels_the_future_plan(self):
        first = {'r1': {'id': 'r1', 'parlayType': 'ladder', 'publishedAt': '2026-10-01T15:00:00Z',
                        'ladder': {'run': 1, 'step': 1, 'stake': 50, 'payout': 81, 'banked': 0},
                        'odds': -160}}
        latest = {'r1': {'result': 'win', 'settledAt': '2026-10-02T02:00:00Z'}}
        data = ticket_climb_map.from_ledger(first, latest)
        self.assertEqual(data['rows'][0]['bet'], 50)
        self.assertEqual(data['rows'][0]['cashes'], 81)
        self.assertEqual(data['rows'][0]['bank'], 16)
        self.assertEqual(data['rows'][0]['ride'], 65)
        self.assertFalse(data['rows'][0]['planned'])
        self.assertTrue(data['rows'][1]['planned'])
        svg = ticket_climb_map.climb_map(data).svg()
        self.assertIn('The plan at a typical −160 a step.', svg)
        self.assertNotIn('1-800-', svg)

    def test_cooked_uses_recorded_units_and_player_team_badge(self):
        game = dict(GAME, players=[{'id': PROP['athleteId'], 'team': GAME['away']['id']}])
        won = dict(PROP, result='win', actualValue=64, units=1.02)
        data = ticket_card.cooked_data(won, game, art={'kind': 'photo', 'uri': self.image},
                                       fetch=lambda url: url)
        self.assertIn('/166.png', data['team_logo'])
        self.assertEqual(data['units_won'], 1.02)
        self.assertEqual(data['margin'], '14.5')
        svg = ticket_card.cooked_svg(won, game, art={'kind': 'photo', 'uri': self.image},
                                     fetch=lambda _: self.logo)
        self.assertIn('+1.02u WON', svg)
        self.assertNotIn('SEASON', svg)

    def test_final_has_every_result_and_same_units_as_record(self):
        rows = [dict(PROP, result='win', actual='TK King: 64 receiving yards', odds=100, units=1.0),
                dict(PROP, id='other', title='Other Player UNDER 4.5 receptions', result='loss',
                     actual='Other Player: 6 receptions', units=-1.0)]
        data = ticket_card.final_data(rows, '2026-10-03')
        self.assertEqual(data['headline'], '1-1')
        self.assertEqual([row['unit_text'] for row in data['rows']], ['+1.00u', '-1.00u'])
        self.assertEqual(data['net_units'], 0)
        svg = ticket_card.final_svg(rows, '2026-10-03')
        self.assertIn('HIT', svg)
        self.assertIn('MISS', svg)
        self.assertIn('NET +0.00u', svg)

    def test_missing_espn_photo_retries_then_warns_in_desk_log(self):
        calls = []
        def fetch(url):
            calls.append(url)
            return None if '/headshots/' in url else self.logo
        art = pick_card.artwork(PROP, GAME, fetch=fetch, player_side='away')
        self.assertEqual(art['fallback'], 'no-headshot')
        self.assertEqual(len([url for url in calls if '/headshots/' in url]), 2)
        messages = []
        with TemporaryDirectory() as folder, patch.object(pick_card, 'chrome_path', return_value='chrome'), \
                patch.object(pick_card, 'artwork', return_value=art), \
                patch.object(pick_card, 'modern_svg', return_value='<svg/>'), \
                patch.object(pick_card, 'render'):
            feed.render_cards([{'guid': 'photo-test', 'pick': PROP, 'game': GAME, 'side': 'away'}],
                              folder, log=messages.append)
        self.assertTrue(any('headshot unavailable after retry' in message for message in messages))


if __name__ == '__main__':
    unittest.main()
