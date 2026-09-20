import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prop_odds


NOW = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)   # 11 AM ET


def game(gid, kickoff, league='NFL'):
    return {'id': gid, 'league': league, 'season': 2026, 'state': 'pre', 'kickoff': kickoff,
            'home': {'name': 'Atlanta Falcons', 'abbreviation': 'ATL'},
            'away': {'name': 'Carolina Panthers', 'abbreviation': 'CAR'}}


def outcome(name, side, point, price):
    return {'description': name, 'name': side, 'point': point, 'price': price}


class BudgetTests(unittest.TestCase):
    slate = {'games': [game('NFL-1', '2026-09-20T17:00Z'), game('NFL-2', '2026-09-20T20:05Z'),
                       game('NFL-3', '2026-09-20T17:00Z'), game('NFL-4', '2026-09-21T00:20Z')]}

    def test_games_closest_to_kickoff_come_first_and_the_day_has_a_ceiling(self):
        picks = prop_odds.wanted(self.slate, {}, NOW)
        self.assertEqual([g['id'] for g in picks], ['NFL-1', 'NFL-3', 'NFL-2'], 'the 8:20 PM game is outside the window')
        spent = {'day': '2026-09-20', 'spent': prop_odds.DAY_CREDITS - prop_odds.COST}
        self.assertEqual([g['id'] for g in prop_odds.wanted(self.slate, spent, NOW)], ['NFL-1'], 'one game of budget left')
        self.assertEqual(prop_odds.wanted(self.slate, {'day': '2026-09-20', 'spent': prop_odds.DAY_CREDITS}, NOW), [])

    def test_a_game_is_not_repriced_inside_the_gap_and_the_reserve_holds(self):
        recent = {'events': {'NFL-1': prop_odds.boxscores.stamp(NOW - timedelta(hours=1))}}
        self.assertEqual([g['id'] for g in prop_odds.wanted(self.slate, recent, NOW)], ['NFL-3', 'NFL-2'])
        old = {'events': {'NFL-1': prop_odds.boxscores.stamp(NOW - timedelta(hours=4))}}
        self.assertIn('NFL-1', [g['id'] for g in prop_odds.wanted(self.slate, old, NOW)])
        broke = {'usage': {'remaining': prop_odds.RESERVE + 1}}
        self.assertEqual(prop_odds.wanted(self.slate, broke, NOW), [], 'the reserve is never spent')

    def test_a_started_game_is_never_priced(self):
        started = {'games': [dict(game('NFL-9', '2026-09-20T15:10Z'), state='in')]}
        self.assertEqual(prop_odds.wanted(started, {}, NOW), [])


class ParseTests(unittest.TestCase):
    event = {'bookmakers': [
        {'key': 'draftkings', 'title': 'DraftKings', 'last_update': '2026-09-20T15:00:00Z', 'markets': [
            {'key': 'player_rush_yds', 'outcomes': [outcome('Bijan Robinson', 'Over', 81.5, -110),
                                                    outcome('Bijan Robinson', 'Under', 81.5, -114)]},
            {'key': 'player_receptions', 'outcomes': [outcome('Drake London', 'Over', 5.5, 105)]},
            {'key': 'player_anytime_td', 'outcomes': [outcome('Drake London', 'Yes', None, 150)]}]},
        {'key': 'fanduel', 'title': 'FanDuel', 'last_update': '2026-09-20T15:00:00Z', 'markets': [
            {'key': 'player_rush_yds', 'outcomes': [outcome('Bijan Robinson', 'Over', 79.5, -108),
                                                    outcome('Bijan Robinson', 'Under', 79.5, -112)]}]}]}

    def test_only_the_markets_the_desk_prices_are_kept(self):
        books = prop_odds.quotes_of(self.event)
        self.assertEqual(sorted(books), ['draftkings', 'fanduel'])
        self.assertEqual(sorted(books['draftkings']['markets']), ['rec', 'rushYds'], 'anytime touchdown is not a desk market')
        self.assertEqual(books['draftkings']['markets']['rushYds']['Bijan Robinson'],
                         {'line': 81.5, 'over': -110, 'under': -114})
        self.assertEqual(books['draftkings']['markets']['rec']['Drake London'], {'line': 5.5, 'over': 105})

    def test_the_best_side_takes_the_number_first_then_the_price(self):
        record = {'books': prop_odds.quotes_of(self.event)}
        self.assertEqual(prop_odds.best(record, 'rushYds', 'Bijan Robinson', 'over'), ('fanduel', 79.5, -108),
                         'the over wants the lowest number')
        self.assertEqual(prop_odds.best(record, 'rushYds', 'Bijan Robinson', 'under'), ('draftkings', 81.5, -114),
                         'the under wants the highest number')
        self.assertIsNone(prop_odds.best(record, 'rushYds', 'Nobody', 'over'))


class CaptureTests(unittest.TestCase):
    def test_a_capture_writes_once_and_stops_repeating_itself(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            calls = []

            def events(sport, key):
                return [{'id': 'abc', 'home_team': 'Atlanta Falcons', 'away_team': 'Carolina Panthers',
                         'commence_time': '2026-09-20T17:00:00Z'}]

            def odds(sport, event, key):
                calls.append(event)
                return ParseTests.event, {'x-requests-remaining': '400', 'x-requests-used': '100', 'x-requests-last': '4'}

            slate = {'games': [game('NFL-1', '2026-09-20T17:00Z')]}
            status = prop_odds.capture(slate, NOW, 'secret', {}, events=events, odds=odds, root=root, log=lambda *a: None)
            self.assertEqual(calls, ['abc'])
            self.assertEqual(status['spent'], 4)
            self.assertEqual(status['usage']['remaining'], 400)
            stored = [json.loads(line) for line in (root / 'nfl-2026.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(stored), 1)
            self.assertNotIn('secret', json.dumps(stored), 'the key never reaches the store')
            self.assertEqual(stored[0]['books']['fanduel']['markets']['rushYds']['Bijan Robinson']['line'], 79.5)
            status['events'] = {}   # allow an immediate second look; the numbers have not changed
            prop_odds.capture(slate, NOW, 'secret', status, events=events, odds=odds, root=root, log=lambda *a: None)
            stored = (root / 'nfl-2026.jsonl').read_text(encoding='utf-8').strip().splitlines()
            self.assertEqual(len(stored), 1, 'an unchanged board is not appended twice')


if __name__ == '__main__':
    unittest.main()
