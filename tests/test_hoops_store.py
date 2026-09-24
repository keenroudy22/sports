import io
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import boxscores
import hoops_store as hs


def competitor(side, team_id, abbreviation, location, short, score, color='112233'):
    return {'homeAway': side, 'score': str(score) if score is not None else None,
            'team': {'id': team_id, 'abbreviation': abbreviation, 'location': location, 'shortDisplayName': short,
                     'displayName': f'{location} {short}', 'color': color, 'alternateColor': 'ffffff'}}


def event(event_id='401705127', when='2025-01-16T00:00Z', year=2025, season_type=2, neutral=False, state='post',
          completed=True, name='STATUS_FINAL', kind='STD', home=('20', 'PHI', 'Philadelphia', '76ers', 119),
          away=('18', 'NY', 'New York', 'Knicks', 125)):
    status = {'type': {'name': name, 'state': state, 'completed': completed}}
    return {'id': event_id, 'date': when, 'season': {'year': year, 'type': season_type}, 'status': status,
            'competitions': [{'neutralSite': neutral, 'type': {'abbreviation': kind}, 'status': status,
                              'competitors': [competitor('home', *home), competitor('away', *away)]}]}


def item(pid, name, close=None, opening=None):
    """One provider in ESPN's core odds shape: (total, home spread, away spread) at each moment."""
    out = {'provider': {'id': pid, 'name': name, 'priority': 0}, 'overUnder': close[0] if close else None,
           'homeTeamOdds': {}, 'awayTeamOdds': {}}
    for when, values in (('close', close), ('open', opening)):
        if not values:
            continue
        total, home, away = values
        out[when] = {'total': {'american': str(total)}} if total is not None else {}
        if home is not None:
            out['homeTeamOdds'][when] = {'pointSpread': {'american': home}}
        if away is not None:
            out['awayTeamOdds'][when] = {'pointSpread': {'american': away}}
    return out


# Trimmed from a real 2023-24 NBA game (401585183): twelve providers, three of them one Caesars.
REAL = {'count': 14, 'items': [
    item('50', 'BetfairSportsbook', (229, '-8', '+8'), (228.5, '-7.5', '+7.5')),
    item('52', 'Caesars Sportsbook (Colorado)', (228.5, '-8', '+8'), (227, '-7', '+7')),
    item('45', 'Caesars Sportsbook (New Jersey)', (228.5, '-8', '+8'), (227, '-7', '+7')),
    item('46', 'Caesars Sportsbook (New Jersey) - Live Odds', None, (228.5, '-8.5', '+8.5')),
    item('57', 'Caesars Sportsbook (Tennessee)', (228.5, '-8', '+8'), (227, '-7', '+7')),
    item('40', 'DraftKings', (228, '-8.5', '+8.5'), (224.5, None, None)),
    item('58', 'ESPN BET', (227.5, '-8.5', '+8.5'), (211.5, '-5.5', '+5.5')),
    item('47', 'MGM', (227.5, '-8.5', '+8.5'), (226.5, '-6.5', '+6.5')),
    item('41', 'SugarHouse', (228.5, '-7.5', '+7.5'), (228, '-7.5', '+7.5')),
    item('53', 'Titanbets', (228, '-8.5', '+8.5'), (227, '-7', '+7')),
    item('36', 'Unibet', (226.5, '-7.5', '+7.5'), (227.5, '-7.5', '+7.5')),
    item('1001', 'accuscore', (240, '-20', '+20'), (240, '-20', '+20')),
]}


class NormalizeTests(unittest.TestCase):
    def test_a_final_becomes_a_compact_record(self):
        game = hs.final_game(event(), 'NBA')
        self.assertEqual(game['id'], 'NBA-401705127')
        self.assertEqual((game['season'], game['type'], game['kickoff'], game['state']), (2025, 2, '2025-01-16T00:00Z', 'post'))
        self.assertEqual(game['home'], {'id': '20', 'abbreviation': 'PHI', 'school': 'Philadelphia', 'short': '76ers',
                                        'color': '112233'})
        self.assertEqual((game['homeScore'], game['awayScore'], game['neutral']), (119, 125, False))

    def test_neutral_site_and_college_postseason(self):
        game = hs.final_game(event(neutral=True, season_type=3, year=2024,
                                   home=('153', 'UNC', 'North Carolina', 'North Carolina', 90),
                                   away=('2681', 'WAG', 'Wagner', 'Wagner', 62)), 'CBB')
        self.assertTrue(game['neutral'])
        self.assertEqual((game['id'][:4], game['type'], game['home']['school']), ('CBB-', 3, 'North Carolina'))

    def test_what_is_not_stored(self):
        self.assertIsNone(hs.final_game(event(season_type=1), 'NBA'))                       # preseason
        self.assertIsNone(hs.final_game(event(kind='ALLSTAR'), 'NBA'))                      # all-star game
        self.assertIsNone(hs.final_game(event(home=('31', 'EAST', 'Eastern Conf', 'EAST', 211),
                                              away=('32', 'WEST', 'Western Conf', 'WEST', 186)), 'NBA'))
        self.assertIsNone(hs.final_game(event(state='in', completed=False), 'NBA'))         # in progress
        self.assertIsNone(hs.final_game(event(name='STATUS_POSTPONED'), 'NBA'))
        self.assertIsNone(hs.final_game(event(name='STATUS_CANCELED'), 'NBA'))
        self.assertIsNone(hs.final_game(event(home=('20', 'PHI', 'Philadelphia', '76ers', None)), 'NBA'))
        self.assertEqual(hs.final_game(event(season_type=5), 'NBA')['type'], 5)              # the play-in counts

    def test_a_team_without_a_colour_leaves_it_out(self):
        game = hs.final_game(event(away=('9999', 'DIV2', 'Small College', 'Small', 50)), 'CBB')
        game_event = event()
        game_event['competitions'][0]['competitors'][1]['team'].pop('color')
        self.assertNotIn('color', hs.final_game(game_event, 'NBA')['away'])
        self.assertEqual(game['away']['id'], '9999')


class ConsensusTests(unittest.TestCase):
    def test_median_of_books_without_live_feeds_projections_or_state_duplicates(self):
        books = hs.book_items(REAL)
        self.assertEqual(len(books), 8)
        self.assertNotIn('accuscore', books)
        self.assertEqual(sum(1 for name in books if name.startswith('Caesars')), 1)
        lines = hs.consensus(REAL)
        # Eight books. Close totals 226.5 to 229 -> 228; spreads four at -8.5, two at -8, two at -7.5 -> -8.25.
        self.assertEqual(lines['close'], {'total': 228.0, 'spread': -8.25, 'books': 8})
        # Open totals include ESPN BET's stray 211.5; the median shrugs it off. DraftKings posted no open spread.
        self.assertEqual(lines['open'], {'total': 227.0, 'spread': -7.0, 'books': 8})

    def test_even_count_takes_the_midpoint(self):
        payload = {'items': [item('40', 'DraftKings', (220.5, '-3', '+3')), item('58', 'ESPN BET', (221, '-3.5', '+3.5'))]}
        self.assertEqual(hs.consensus(payload)['close'], {'total': 220.75, 'spread': -3.25, 'books': 2})

    def test_away_only_lines_pick_em_and_disagreement(self):
        payload = {'items': [item('100', 'DraftKings', (145.5, None, '-4.5'), (146, 'PK', 'PK'))]}
        lines = hs.consensus(payload)
        self.assertEqual(lines['close'], {'total': 145.5, 'spread': 4.5, 'books': 1})
        self.assertEqual(lines['open'], {'total': 146.0, 'spread': 0.0, 'books': 1})
        broken = {'items': [item('100', 'DraftKings', (145.5, '-4.5', '+3.5'))]}
        self.assertEqual(hs.consensus(broken)['close'], {'total': 145.5, 'books': 1})

    def test_missing_odds_is_no_line_not_an_estimate(self):
        self.assertEqual(hs.consensus({'count': 0, 'items': []}), {'close': None, 'open': None})
        self.assertEqual(hs.consensus(None), {'close': None, 'open': None})
        live_only = {'items': [item('59', 'ESPN Bet - Live Odds', (242.5, '-7.5', '+7.5'))]}
        self.assertEqual(hs.consensus(live_only), {'close': None, 'open': None})
        open_only = {'items': [item('58', 'ESPN BET', None, (219.5, '+6.5', '-6.5'))]}
        self.assertEqual(hs.consensus(open_only), {'close': None, 'open': {'total': 219.5, 'spread': 6.5, 'books': 1}})

    def test_implausible_numbers_are_dropped(self):
        payload = {'items': [item('100', 'DraftKings', (2.5, '-75', '+75'))]}
        self.assertEqual(hs.consensus(payload)['close'], None)


class FakeFeed:
    """Scoreboards by day and odds by event; an odds entry that is a number is that HTTP error (404 by default)."""

    def __init__(self, days, odds):
        self.days, self.odds, self.calls = days, odds, []

    def __call__(self, url):
        self.calls.append(url)
        if '/scoreboard?' in url:
            day = url.split('dates=')[1][:8]
            return {'events': self.days.get(day, [])}
        answer = self.odds.get(url.split('/events/')[1].split('/')[0], 404)
        if isinstance(answer, int):
            raise HTTPError(url, answer, 'unavailable', None, None)
        return answer


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.days = {'20250115': [event('1', '2025-01-16T00:00Z'), event('2', '2025-01-16T01:00Z', state='in', completed=False)],
                     '20250116': [event('3', '2025-01-17T00:30Z', neutral=True), event('4', '2025-01-17T01:00Z')],
                     '20250117': [event('1', '2025-01-16T00:00Z')]}  # listed again the next day
        self.odds = {'1': REAL, '3': {'count': 0, 'items': []}, '4': 503}
        self.clock = lambda: datetime(2026, 9, 24, 12, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def run_once(self, feed):
        days = [date(2025, 1, 15), date(2025, 1, 16), date(2025, 1, 17)]
        games = hs.finals_on('NBA', days, feed, pause=0, log=lambda *_: None)
        return hs.collect('NBA', games, feed, pause=0, workers=2, root=self.root, clock=self.clock, log=lambda *_: None)

    def test_finals_are_stored_once_with_their_lines_and_a_ledger(self):
        written, failures = self.run_once(FakeFeed(self.days, self.odds))
        self.assertEqual(written, {'nba-2025.jsonl': 2})
        self.assertEqual(set(failures), {'4'})  # odds unreadable: left for the next run, not stored bare
        records = hs.load('NBA', root=self.root)
        self.assertEqual([r['eventId'] for r in records], ['1', '3'])
        first, second = records
        self.assertEqual(first['close'], {'total': 228.0, 'spread': -8.25, 'books': 8})
        self.assertEqual(first['retrievedAt'], '2026-09-24T12:00:00Z')
        self.assertTrue(second['neutral'])
        self.assertIsNone(second['close'])  # no book priced it: no line
        self.assertIsNone(second['open'])
        self.assertEqual(boxscores.verify(self.root), [])
        ledger = json.loads((self.root / 'ledger.json').read_text())
        self.assertEqual(ledger['nba-2025.jsonl']['lines'], 2)

    def test_a_rerun_skips_what_is_stored_and_retries_what_failed(self):
        self.run_once(FakeFeed(self.days, self.odds))
        self.odds['4'] = REAL
        feed = FakeFeed(self.days, self.odds)
        written, failures = self.run_once(feed)
        self.assertEqual((written, failures), ({'nba-2025.jsonl': 1}, {}))
        self.assertEqual([u for u in feed.calls if '/odds' in u], [hs.odds_url('NBA', '4')])
        self.assertEqual(self.run_once(FakeFeed(self.days, self.odds)), ({}, {}))
        self.assertEqual(len(boxscores.read_lines(self.root / 'nba-2025.jsonl')), 3)

    def test_a_changed_line_stops_the_next_append(self):
        self.run_once(FakeFeed(self.days, self.odds))
        path = self.root / 'nba-2025.jsonl'
        path.write_text(path.read_text().replace('"homeScore":119', '"homeScore":120'))
        self.assertEqual(boxscores.verify(self.root), ['nba-2025.jsonl: a recorded line was changed'])
        with self.assertRaises(SystemExit):
            self.run_once(FakeFeed(self.days, self.odds))

    def test_requests_use_single_days_and_the_default_user_agent(self):
        self.assertEqual(hs.scoreboard_url('CBB', date(2026, 1, 15)),
                         'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/'
                         'scoreboard?dates=20260115&groups=50&limit=1000')
        self.assertEqual(hs.odds_url('NBA', '401705127'),
                         'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401705127/'
                         'competitions/401705127/odds')
        # A bare URL, not a Request carrying headers: the feed refuses custom User-Agent strings.
        seen = []

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        original = boxscores.urlopen
        boxscores.urlopen = lambda url, timeout=None: seen.append(url) or Response(b'{"events": []}')
        try:
            self.assertEqual(hs.fetch_json(hs.scoreboard_url('NBA', date(2026, 1, 15))), {'events': []})
        finally:
            boxscores.urlopen = original
        self.assertIsInstance(seen[0], str)

    def test_season_window(self):
        days = hs.season_days('NBA', 2026)
        self.assertEqual((days[0], days[-1]), (date(2025, 10, 1), date(2026, 6, 30)))
        cbb = hs.season_days('CBB', 2027, today=date(2026, 12, 1))
        self.assertEqual((cbb[0], cbb[-1]), (date(2026, 11, 1), date(2026, 11, 30)))

    def test_backfill_keeps_only_its_season(self):
        days = {'20251021': [event('10', '2025-10-21T23:30Z', year=2026)],
                '20251001': [event('11', '2025-10-01T23:30Z', year=2025, season_type=3)]}
        feed = FakeFeed(days, {'10': REAL})
        written, failures = hs.backfill('NBA', 2026, feed, pause=0, workers=1, root=self.root,
                                        today=date(2025, 10, 23), log=lambda *_: None)
        self.assertEqual((written, failures), ({'nba-2026.jsonl': 1}, {}))

    def test_refresh_reads_the_last_days(self):
        feed = FakeFeed({'20250116': [event('3', '2025-01-17T00:30Z')]}, {'3': REAL})
        result = hs.refresh(['NBA'], 2, feed, pause=0, workers=1, root=self.root,
                            now=datetime(2025, 1, 17, 15, tzinfo=timezone.utc), log=lambda *_: None)
        self.assertEqual(result, {'NBA': ({'nba-2025.jsonl': 1}, {})})
        self.assertEqual([u.split('dates=')[1][:8] for u in feed.calls if 'scoreboard' in u], ['20250116', '20250117'])


class RealStoreTests(unittest.TestCase):
    def test_no_recorded_line_has_changed(self):
        self.assertEqual(boxscores.verify(hs.STORE), [],
                         'A hoops store line was rewritten. Restore it and append a revision instead.')

    def test_every_stored_record_is_a_final_with_a_consistent_line(self):
        for path in sorted(hs.STORE.glob('*.jsonl')):
            for rec in boxscores.read_store(path):
                self.assertEqual(rec['state'], 'post', rec['id'])
                self.assertEqual(rec['id'], f"{rec['league']}-{rec['eventId']}")
                self.assertTrue(path.name.startswith(f"{rec['league'].lower()}-{rec['season']}"), rec['id'])
                for when in ('close', 'open'):
                    if rec[when]:
                        self.assertGreaterEqual(rec[when]['books'], 1)


if __name__ == '__main__':
    unittest.main()
