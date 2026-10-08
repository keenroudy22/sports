"""Kitchen Ticket v2 preview: exact pick facts and ESPN art routing."""
import base64
import sys
import unittest
from datetime import datetime, timezone
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
    def test_tnf_end_zone_research_uses_kitchen_ticket_without_a_bet_claim(self):
        choice = {'game': 'BUCS AT COWBOYS · THU 8:15 PM', 'rows': [
            {'title': 'Javonte Williams', 'athleteId': '4429111',
             'metric': '21 red-zone opportunities', 'price': '12 inside the 10'},
            {'title': 'CeeDee Lamb', 'athleteId': '4241389',
             'metric': '6 red-zone opportunities', 'price': '3 inside the 10'}]}
        calls = []
        def photo(url):
            calls.append(url)
            return self.image
        svg = ticket_card.end_zone_svg(choice, fetch=photo)
        for exact in ('END-ZONE WORK', 'BUCS AT COWBOYS', 'JAVONTE WILLIAMS',
                      '21 red-zone opportunities', '12 INSIDE THE 10',
                      'NOT A TD PICK OR OFFICIAL BET', '21+ · Entertainment only'):
            self.assertIn(exact, svg)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all('/headshots/nfl/players/full/' in url for url in calls))
        for forbidden in ('BEST BET', 'ORDER UP', '1-800-', 'SEASON 35', '4869443:'):
            self.assertNotIn(forbidden, svg)
        with self.assertRaises(ValueError):
            ticket_card.end_zone_svg({'game': choice['game'], 'rows': [
                dict(choice['rows'][0], metric='unknown')]}, fetch=photo)

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
        rows = [dict(PROP, marketType='prop', result='win', actual='TK King: 64 receiving yards', odds=100, units=1.0),
                dict(PROP, id='other', title='Other Player UNDER 4.5 receptions', result='loss',
                     marketType='prop', market='rec', line=4.5, actual='Other Player: 6 receptions', units=-1.0)]
        data = ticket_card.final_data(rows, '2026-10-03')
        self.assertEqual(data['headline'], '1-1')
        self.assertEqual([row['unit_text'] for row in data['rows']], ['+1.00u', '-1.00u'])
        self.assertEqual(data['net_units'], 0)
        self.assertEqual(data['rows'][0]['detail'], '64 rec yds · cleared by 14.5')
        self.assertEqual(data['rows'][1]['detail'], '6 recs · missed by 1.5')
        svg = ticket_card.final_svg(rows, '2026-10-03')
        self.assertIn('HIT', svg)
        self.assertIn('MISS', svg)
        self.assertIn('NET +0.00u', svg)

    def test_final_total_detail_has_score_and_margin_without_double_space(self):
        pick = {'id': 'navy-total', 'title': 'Navy at Air Force over 46.5', 'marketType': 'total',
                'line': 46.5, 'direction': 'over', 'result': 'loss', 'actual': 'Navy 9, Air Force 14',
                'units': -1.0}
        row = ticket_card.final_data([pick], '2026-10-03')['rows'][0]
        self.assertEqual(row['detail'], 'Final: Navy 9, Air Force 14 · missed by 23.5')
        self.assertNotIn('  ', row['title'])

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

    def test_ticket_cutover_requires_offset_and_keeps_older_art(self):
        self.assertEqual(pick_card.TICKET_FROM, '2026-10-08T12:00:00-04:00')
        with patch.object(pick_card, 'TICKET_FROM', '2026-10-08T11:00:00-04:00'):
            self.assertFalse(pick_card.ticket_enabled({'publishedAt': '2026-10-08T14:59:59Z'}))
            self.assertTrue(pick_card.ticket_enabled({'publishedAt': '2026-10-08T15:00:00Z'}))
            self.assertEqual(pick_card.card_theme(item={'publishedAt': '2026-10-08T15:00:00Z'}), 'ticket')
            self.assertEqual(pick_card.card_theme(item={'publishedAt': '2026-10-08T14:59:59Z'}), 'legacy')
        with patch.object(pick_card, 'TICKET_FROM', '2026-10-08'):
            self.assertFalse(pick_card.ticket_enabled({'publishedAt': '2026-10-09T12:00:00Z'}))

    def test_feed_routes_new_straight_and_leaves_old_attachment_unchanged(self):
        recent = dict(PROP, publishedAt='2026-10-08T15:01:00Z')
        old = dict(PROP, publishedAt='2026-10-08T14:59:00Z')
        with TemporaryDirectory() as folder, patch.object(pick_card, 'TICKET_FROM', '2026-10-08T11:00:00-04:00'), \
                patch.object(pick_card, 'chrome_path', return_value='chrome'), \
                patch.object(pick_card, 'artwork', return_value={'kind': 'photo', 'uri': self.image}), \
                patch.object(pick_card, 'render') as render, \
                patch.object(ticket_card, 'straight_svg', return_value='<svg data-theme="ticket"/>') as kitchen, \
                patch.object(pick_card, 'modern_svg', return_value='<svg data-theme="legacy"/>') as old_svg:
            feed.render_cards([{'guid': 'new', 'pick': recent, 'game': GAME, 'side': 'away'},
                               {'guid': 'old', 'pick': old, 'game': GAME, 'side': 'away'}], folder)
            self.assertEqual(kitchen.call_count, 1)
            self.assertEqual(old_svg.call_count, 1)
            self.assertEqual(render.call_args_list[0].args[0], '<svg data-theme="ticket"/>')
            self.assertEqual(render.call_args_list[1].args[0], '<svg data-theme="legacy"/>')
            existing = Path(folder) / 'existing.png'
            existing.write_bytes(feed.PNG + b'posted-art')
            feed.render_cards([{'guid': 'existing', 'pick': recent, 'game': GAME, 'side': 'away'}], folder,
                              posted_keys={'existing'})
            self.assertEqual(existing.read_bytes(), feed.PNG + b'posted-art')
            self.assertEqual(render.call_count, 2)

            # An unposted legacy preview must become the new ticket when its publication time qualifies.
            preview = Path(folder) / 'preview.png'
            preview.write_bytes(b'old preview')
            feed.render_cards([{'guid': 'preview', 'pick': recent, 'game': GAME, 'side': 'away'}], folder)
            self.assertEqual(render.call_count, 3)
            self.assertEqual(render.call_args.args[0], '<svg data-theme="ticket"/>')

    def test_pre_cutover_unposted_card_refreshes_but_posted_bytes_do_not(self):
        old = dict(PROP, publishedAt='2026-10-08T14:00:00Z')
        at = datetime(2026, 10, 8, 17, 0, tzinfo=timezone.utc)
        with TemporaryDirectory() as folder, patch.object(pick_card, 'TICKET_FROM', '2026-10-08T12:00:00-04:00'), \
                patch.object(pick_card, 'chrome_path', return_value='chrome'), \
                patch.object(pick_card, 'artwork', return_value={'kind': 'photo', 'uri': self.image}), \
                patch.object(ticket_card, 'straight_svg', return_value='<svg data-kookn-theme="ticket"/>') as kitchen, \
                patch.object(pick_card, 'render') as render:
            stale = Path(folder) / 'unposted.png'
            stale.write_bytes(b'legacy preview')
            sent = Path(folder) / 'posted.png'
            sent.write_bytes(feed.PNG + b'original posted attachment')
            feed.render_cards([{'guid': 'unposted', 'pick': old, 'game': GAME, 'side': 'away'},
                               {'guid': 'posted', 'pick': old, 'game': GAME, 'side': 'away'}],
                              folder, render_time=at, posted_keys={'posted'})
            kitchen.assert_called_once()
            render.assert_called_once()
            self.assertEqual(sent.read_bytes(), feed.PNG + b'original posted attachment')

    def test_settled_climb_uses_result_time_and_real_leg_marks(self):
        pick = {'id': 'rung', 'parlayType': 'ladder', 'publishedAt': '2026-10-08T14:00:00Z',
                'settledAt': '2026-10-08T16:00:00Z', 'result': 'win', 'actual': 'all 2 legs won',
                'odds': -160, 'book': 'FanDuel', 'ladder': {'run': 1, 'step': 2, 'stake': 75,
                'payout': 120, 'banked': 16, 'bankThisWin': 24, 'nextStake': 96},
                'legs': [{'title': 'Team A +3.5', 'odds': -110}, {'title': 'Over 42.5', 'odds': -110}]}
        with TemporaryDirectory() as folder, patch.object(pick_card, 'TICKET_FROM', '2026-10-08T11:00:00-04:00'), \
                patch.object(pick_card, 'chrome_path', return_value='chrome'), \
                patch.object(ticket_card, 'climb_result_svg', return_value='<svg data-theme="ticket"/>') as result_svg, \
                patch.object(pick_card, 'render') as render:
            feed.render_cards([{'guid': 'rung-result', 'ladderResult': pick}], folder, games={})
            result_svg.assert_called_once()
            self.assertEqual(render.call_args.args[0], '<svg data-theme="ticket"/>')
        with patch.object(ticket_card, 'climb_data', return_value={'legs': [{'title': 'A', 'odds': -110},
                {'title': 'B', 'odds': -110}], 'banked': 16, 'bank_this': 24, 'next_stake': 96,
                'goal': 1000, 'run': 1, 'step': 2, 'stake': 75, 'payout': 120, 'odds': -160,
                'book': 'FanDuel'}), patch.object(ticket_card.ticket_cards, 'climb_card') as card:
            card.return_value.svg.return_value = '<svg/>'
            ticket_card.climb_result_svg(pick, {})
            self.assertEqual(card.call_args.args[0]['leg_results'], {0: 'hit', 1: 'hit'})
            self.assertEqual(card.call_args.args[0]['banked'], 40)


if __name__ == '__main__':
    unittest.main()
