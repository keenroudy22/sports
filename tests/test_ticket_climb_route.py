"""Stored-fixture checks for the dated 80/20 Climb route; no feed or post calls."""
import struct
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ladder
import ticket_climb_map
import ticket_climb_route as route
import ticket_kit as kit


NOW = datetime(2026, 10, 7, 20, 40, tzinfo=timezone.utc)


def frozen_slate():
    games = []
    for offset in range(1, 13):
        day = NOW.astimezone(route.ET).date() + timedelta(days=offset)
        league = 'NFL' if day.weekday() == 6 else 'CFB'
        for minute in (0, 30):
            kickoff = datetime(day.year, day.month, day.day, 19, minute, tzinfo=route.ET)
            games.append({'id': f'{league}-{offset}-{minute}', 'league': league,
                          'kickoff': kickoff.isoformat(), 'state': 'pre', 'timeValid': True})
    return {'games': games}


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.games = route.load_games(frozen_slate())

    def test_plan_is_the_approved_map_and_continues_from_real_money(self):
        self.assertEqual(route.plan_from(1, 50, 0), ticket_climb_map.plan(-160))
        continued = route.plan_from(3, 94, 42)
        self.assertEqual(continued, ticket_climb_map.plan(-160, start=94, banked=42, step_start=3))
        self.assertEqual(continued[0]['bet'], 94)
        self.assertGreaterEqual(continued[-1]['banked'] + continued[-1]['ride'], 1000)

    def test_window_requires_two_games_one_league_more_than_ninety_minutes_out(self):
        scan = datetime(2026, 10, 8, 16, 0, tzinfo=route.ET)
        first = {'id': 'only', 'league': 'CFB', 'kickoff': scan + timedelta(minutes=91)}
        self.assertIsNone(route.window_at([first], scan))
        self.assertIsNone(route.window_at([first, dict(first, id='nfl', league='NFL')], scan))
        boundary = dict(first, id='boundary', kickoff=scan + timedelta(minutes=90))
        self.assertIsNone(route.window_at([first, boundary], scan))
        pair = dict(first, id='pair', kickoff=scan + timedelta(minutes=150))
        self.assertEqual([game['id'] for game in route.window_at([first, pair], scan)['games']], ['only', 'pair'])

    def test_windows_do_not_overlap_or_scan_before_last_kickoff_plus_settle(self):
        found = route.windows(self.games, NOW, 4)
        self.assertEqual(len(found), 4)
        for earlier, later in zip(found, found[1:]):
            self.assertGreaterEqual(later['scan'], earlier['last'] + route.SETTLE)
            self.assertGreater(later['first'], earlier['last'])
        blocked = route.windows(self.games, NOW, 1, free_at=found[0]['last'] + route.SETTLE)
        self.assertEqual(blocked[0]['first'], found[1]['first'])

    def test_nfl_is_considered_before_cfb_and_dst_labels_use_eastern(self):
        scan = datetime(2026, 10, 11, 8, 30, tzinfo=route.ET)
        both = [
            {'id': 'cfb-a', 'league': 'CFB', 'kickoff': scan + timedelta(hours=3)},
            {'id': 'cfb-b', 'league': 'CFB', 'kickoff': scan + timedelta(hours=3, minutes=30)},
            {'id': 'nfl-a', 'league': 'NFL', 'kickoff': scan + timedelta(hours=4)},
            {'id': 'nfl-b', 'league': 'NFL', 'kickoff': scan + timedelta(hours=4, minutes=30)},
        ]
        self.assertEqual(route.window_at(both, scan)['league'], 'NFL')
        self.assertEqual(route.window_label({'first': datetime(2026, 11, 2, 0, tzinfo=timezone.utc)}),
                         ('SUN 11/1', '7 PM'))

    def test_window_label_names_kickoff_not_a_scan_clock(self):
        window = {'first': datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc),
                  'scan': datetime(2026, 10, 10, 13, 30, tzinfo=timezone.utc)}
        self.assertEqual(route.window_label(window), ('SAT 10/10', '3 PM'))
        self.assertEqual(route.window_label(None), ('NO SLATE YET', ''))

    def test_invalid_tbd_and_finished_kickoffs_are_excluded(self):
        slate = frozen_slate()
        slate['games'] += [{'id': 'tbd', 'league': 'CFB', 'kickoff': '2026-10-08T00:00Z',
                            'state': 'pre', 'timeValid': False},
                           {'id': 'finished', 'league': 'NFL', 'kickoff': '2026-10-08T19:00Z',
                            'state': 'post', 'timeValid': True}]
        ids = {game['id'] for game in route.load_games(slate)}
        self.assertNotIn('tbd', ids)
        self.assertNotIn('finished', ids)

    def test_ladder_state_comes_from_as_of_and_uses_both_leg_times(self):
        first = {
            'win': {'id': 'win', 'parlayType': 'ladder', 'publishedAt': '2026-10-07T12:00Z',
                    'league': 'CFB', 'odds': -150, 'status': 'active',
                    'ladder': {'run': 1, 'step': 1, 'stake': 50, 'payout': 83, 'banked': 0,
                               'bankedAfter': 17, 'nextStake': 66},
                    'legs': [{'kickoff': '2026-10-08T23:00Z', 'title': 'Iowa +4.5', 'odds': -120,
                              'book': 'FanDuel'}, {'kickoff': '2026-10-09T00:30Z', 'title': 'Under 52.5',
                                                  'odds': -110, 'book': 'FanDuel'}]},
            'open': {'id': 'open', 'parlayType': 'ladder', 'publishedAt': '2026-10-09T01:00Z',
                     'league': 'CFB', 'odds': -173, 'status': 'active',
                     'ladder': {'run': 1, 'step': 2, 'stake': 66, 'payout': 104,
                                'bankThisWin': 21, 'bankedAfter': 38, 'nextStake': 83},
                     'legs': [{'kickoff': '2026-10-09T23:30Z'}, {'kickoff': '2026-10-09T23:00Z'}]},
        }
        latest = {'win': {'result': 'win', 'settledAt': '2026-10-09T00:50Z'}}
        class Stores:
            slate = frozen_slate()
            def as_of(self, now):
                self.called_with = now
                return SimpleNamespace(first=first, latest=latest)
        stores = Stores()
        state, games = route.from_stores(stores, NOW)
        self.assertEqual(stores.called_with, NOW)
        self.assertEqual(state['cashed'][0]['bet'], 50)
        self.assertEqual(state['cashed'][0]['cashes'], 83)
        self.assertEqual(state['cashed'][0]['bank'], 17)
        self.assertEqual(state['cashed'][0]['first'], route.when('2026-10-08T23:00Z'))
        self.assertEqual(state['cashed'][0]['last'], route.when('2026-10-09T00:30Z'))
        self.assertEqual(state['cashed'][0]['legs'][0]['href'], '#pick/win')
        self.assertEqual(state['cashed'][0]['legs'][0]['title'], 'Iowa +4.5')
        self.assertEqual(state['open']['bet'], 66)
        self.assertEqual(state['open']['cashes'], 104)
        self.assertEqual(state['open']['first'], route.when('2026-10-09T23:00Z'))
        self.assertEqual(route.route_rows(state, NOW, games)[-1][1]['planned'], True)
        public = route.public_route(state, NOW, games)
        self.assertEqual(public['image'], 'data/cards/climb-route.png')
        self.assertEqual(public['rows'][0]['kind'], 'cashed')
        self.assertEqual(public['rows'][0]['bet'], 50)
        self.assertEqual(public['rows'][0]['cashes'], 83)
        self.assertEqual(public['rows'][0]['legs'][0]['href'], '#pick/win')
        self.assertEqual(public['rows'][1]['kind'], 'open')
        self.assertEqual(public['rows'][2]['plannedAt'], 'typical -160')
        with TemporaryDirectory() as folder:
            path, rendered_state, rendered_rows = route.render(Path(folder) / 'climb-route.png', NOW, stores)
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(rendered_state['saved'], public['saved'])
            self.assertEqual(len(rendered_rows), len(public['rows']))

    def test_open_fixture_uses_real_minus_173_not_typical_price(self):
        opened, instant = route.fixture_states(NOW, self.games)['open']
        rows = route.route_rows(opened, instant, self.games)
        self.assertEqual((rows[0][0], rows[0][1]['bet'], rows[0][1]['cashes']), ('open', 50, 79))
        self.assertEqual((rows[1][1]['bet'], rows[1][1]['banked']), (63, 36))
        self.assertEqual(opened['open']['banked'], 16)

    def test_unfilled_window_slides_without_changing_cashed_rows(self):
        mid, instant = route.fixture_states(NOW, self.games)['midclimb']
        before = route.route_rows(mid, instant, self.games)
        after = route.route_rows(mid, instant + timedelta(days=1), self.games)
        self.assertEqual(before[:2], after[:2])
        self.assertNotEqual(before[2][2]['first'], after[2][2]['first'])

    def test_labels_symbol_contrast_and_no_result_green_on_open_rows(self):
        mid, instant = route.fixture_states(NOW, self.games)['midclimb']
        card = route.climb_route(mid, instant, self.games, fixture=True)
        svg = card.svg()
        for text in (route.PLAN_LABEL, '21+ · Entertainment only', 'ALL CLIMBS', 'FIXTURE'):
            self.assertIn(text, svg)
        self.assertNotIn('1-800-', svg)
        self.assertNotIn('SEASON', svg)
        self.assertNotIn('DraftKings', svg)
        self.assertNotIn('ESPN', svg)
        self.assertEqual(kit.qa(card, 'fixture-route'), [])
        next_row = route._row(card, 500, 'next', route.plan_from(1, 50, 0)[0], None, kit.CHALK, kit.DIM)
        self.assertNotIn(kit.GREEN, next_row)
        self.assertGreaterEqual(kit.contrast(kit.INK_SOFT, kit.PAPER_LOW_TONE), 6.9)
        self.assertGreaterEqual(kit.contrast(kit.DIM, kit.NIGHT), 9.8)

    def test_png_and_all_three_explicit_fixture_cards(self):
        with TemporaryDirectory() as folder:
            paths = route.render_fixtures(folder, NOW, self.games)
            self.assertEqual(len(paths), 3)
            for path in paths:
                raw = path.read_bytes()
                self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual(struct.unpack('>II', raw[16:24]), (1080, 1350))
                self.assertLess(len(raw), 8_000_000)


if __name__ == '__main__':
    unittest.main()
