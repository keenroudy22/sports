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
import soccer_store as ss

RETRIEVED = '2026-09-24T12:00:00Z'

# The 2016-17 layout: two-digit years, no kick-off time, Pinnacle's close for 1X2 only, and
# Betbrain's pre-close average for the total and the handicap.
OLD = '\n'.join([
    'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HS,AS,HST,AST,PSH,PSD,PSA,BbAvH,BbAvD,BbAvA,BbAv>2.5,BbAv<2.5,'
    'BbAHh,BbAvAHH,BbAvAHA,PSCH,PSCD,PSCA',
    'E0,13/08/16,Burnley,Swansea,0,1,A,10,17,3,9,2.47,3.32,3.19,2.43,3.21,3.1,2.3,1.61,-0.25,2.06,1.81,2.79,3.16,2.89',
    ',,,,,,,,,,,,,,,,,,,,,,,,',
])

# The current layout, with a byte-order mark, four-digit years and UK kick-off times. The second
# match has no Pinnacle prices (the average stands in), the third has not been played.
NEW = '﻿' + '\n'.join([
    'Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HxG,AxG,HS,AS,HST,AST,PSH,PSD,PSA,AvgH,AvgD,AvgA,P>2.5,P<2.5,'
    'Avg>2.5,Avg<2.5,AHh,PAHH,PAHA,AvgAHH,AvgAHA,PSCH,PSCD,PSCA,AvgCH,AvgCD,AvgCA,PC>2.5,PC<2.5,AvgC>2.5,AvgC<2.5,'
    'AHCh,PCAHH,PCAHA,AvgCAHH,AvgCAHA',
    'E0,15/08/2025,20:00,Liverpool,Bournemouth,4,2,H,2.1,0.9,19,10,10,3,1.3,6.0,9.5,1.28,5.8,9.0,1.5,2.7,1.48,2.6,'
    '-1.75,1.95,1.95,1.9,1.93,1.28,6.2,10.5,1.26,5.9,10.0,1.52,2.6,1.5,2.55,-1.75,2.0,1.9,1.94,1.9',
    'E0,21/12/2025,14:00,Fulham,Chelsea,1,1,D,,,12,14,4,5,,,,3.4,3.6,2.1,,,1.8,2.0,0.25,,,1.92,1.94,,,,3.5,3.6,'
    '2.05,,,1.85,1.95,0.5,,,1.99,1.87',
    'E0,24/05/2026,16:00,Arsenal,Everton,,,,,,,,,,1.2,7.0,13.0,1.2,6.8,12.0,1.4,3.0,1.4,2.9,-2,1.9,2.0,1.88,1.98,'
    ',,,,,,,,,,,,,,',
])

MLS = '﻿' + '\n'.join([
    'Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA',
    'USA,MLS,2015,07/03/2015,20:00,Chicago Fire,LA Galaxy,0,1,A,2.4,3.4,3.0,2.5,3.5,3.1,2.3,3.3,2.9',
    'USA,MLS,2025,20/09/2025,02:30,Real Salt Lake,CF Montreal,2,0,H,1.9,3.8,4.0,1.95,3.9,4.2,1.85,3.7,3.9',
    'USA,MLS,2025,26/10/2025,21:30,Philadelphia Union,Chicago Fire,2,2,D,,,,1.95,4,4,1.86,3.73,3.73',
])


def parse_old():
    return ss.parse_csv(OLD, 'EPL', 'https://example/1617/E0.csv', RETRIEVED, start_year=2016)


def parse_new():
    return ss.parse_csv(NEW, 'EPL', 'https://example/2526/E0.csv', RETRIEVED, start_year=2025)


class DateTests(unittest.TestCase):
    def test_both_date_formats(self):
        self.assertEqual(ss.parse_date('13/08/16'), date(2016, 8, 13))
        self.assertEqual(ss.parse_date('11/08/2017'), date(2017, 8, 11))
        self.assertEqual(ss.parse_date(' 1/2/2020 '), date(2020, 2, 1))

    def test_bad_dates_are_missing(self):
        for text in ('2016-08-13', '31/02/20', '', None, '13/08'):
            self.assertIsNone(ss.parse_date(text))

    def test_uk_time_becomes_utc(self):
        # British Summer Time in 2026 runs from 29 March to 25 October.
        self.assertEqual(ss.uk_to_utc(date(2026, 3, 28), '15:00'), datetime(2026, 3, 28, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(ss.uk_to_utc(date(2026, 3, 29), '15:00'), datetime(2026, 3, 29, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(ss.uk_to_utc(date(2026, 10, 24), '20:00'), datetime(2026, 10, 24, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(ss.uk_to_utc(date(2026, 10, 25), '20:00'), datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc))
        self.assertIsNone(ss.uk_to_utc(date(2026, 10, 25), ''))

    def test_season_labels_and_urls(self):
        self.assertEqual(ss.season_label('EPL', 2025), '2025-26')
        self.assertEqual(ss.season_label('EPL', 2099), '2099-00')
        self.assertEqual(ss.season_label('MLS', 2025), '2025')
        self.assertEqual(ss.season_url('EPL', 2016), 'https://www.football-data.co.uk/mmz4281/1617/E0.csv')
        self.assertEqual(ss.season_url('MLS', 2016), 'https://www.football-data.co.uk/new/USA.csv')
        self.assertEqual(ss.current_start_year('EPL', date(2026, 9, 24)), 2026)
        self.assertEqual(ss.current_start_year('EPL', date(2026, 3, 1)), 2025)
        self.assertEqual(ss.current_start_year('MLS', date(2026, 3, 1)), 2026)


class ParseTests(unittest.TestCase):
    def test_old_layout(self):
        records = parse_old()
        self.assertEqual(len(records), 1, 'the blank row is skipped')
        record = records[0]
        self.assertEqual(record['id'], 'EPL-2016-08-13-burnley-swansea')
        self.assertEqual((record['season'], record['date'], record['home'], record['away']),
                         ('2016-17', '2016-08-13', 'Burnley', 'Swansea'))
        self.assertEqual((record['homeGoals'], record['awayGoals']), (0, 1))
        self.assertNotIn('kickoff', record, 'no time in the file, no kickoff invented')
        self.assertEqual(record['shots'], {'home': 10, 'away': 17, 'homeTarget': 3, 'awayTarget': 9})
        self.assertEqual(record['close'], {'home': 2.79, 'draw': 3.16, 'away': 2.89, 'books': {'1x2': 'Pinnacle'}})
        self.assertNotIn('closeAvg', record, 'the old files have no closing average')
        self.assertEqual(record['open']['books'], {'1x2': 'Pinnacle', 'total': 'Average', 'ah': 'Average'})
        self.assertEqual((record['open']['home'], record['open']['over25'], record['open']['ahLine']), (2.47, 2.3, -0.25))
        self.assertEqual(record['openAvg'], {'home': 2.43, 'draw': 3.21, 'away': 3.1, 'over25': 2.3, 'under25': 1.61,
                                             'ahLine': -0.25, 'ahHome': 2.06, 'ahAway': 1.81})
        self.assertEqual(record['hash'], boxscores.content_hash(record))

    def test_new_layout_with_missing_prices(self):
        records = parse_new()
        self.assertEqual([r['id'] for r in records],
                         ['EPL-2025-08-15-liverpool-bournemouth', 'EPL-2025-12-21-fulham-chelsea'], 'the unplayed match is skipped')
        first, second = records
        self.assertEqual((first['time'], first['kickoff']), ('20:00', '2025-08-15T19:00:00Z'))
        self.assertEqual(second['kickoff'], '2025-12-21T14:00:00Z', 'winter: UK time is UTC')
        self.assertEqual(first['xg'], {'home': 2.1, 'away': 0.9})
        self.assertNotIn('xg', second, 'blank xG is missing, not zero')
        self.assertEqual(first['close'], {'home': 1.28, 'draw': 6.2, 'away': 10.5, 'over25': 1.52, 'under25': 2.6,
                                          'ahLine': -1.75, 'ahHome': 2.0, 'ahAway': 1.9,
                                          'books': {'1x2': 'Pinnacle', 'total': 'Pinnacle', 'ah': 'Pinnacle'}})
        self.assertEqual(first['closeAvg']['home'], 1.26)
        self.assertEqual(first['open']['ahLine'], -1.75)
        self.assertEqual(second['close'], {'home': 3.5, 'draw': 3.6, 'away': 2.05, 'over25': 1.85, 'under25': 1.95,
                                           'ahLine': 0.5, 'ahHome': 1.99, 'ahAway': 1.87,
                                           'books': {'1x2': 'Average', 'total': 'Average', 'ah': 'Average'}})
        self.assertEqual(second['open']['ahLine'], 0.25)

    def test_missing_columns_leave_markets_out(self):
        text = 'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,PSCH,PSCD,PSCA\nE0,01/09/19,A Town,B City,2,0,1.5,4.0,0\n'
        record = ss.parse_csv(text, 'EPL', 'u', RETRIEVED, start_year=2019)[0]
        self.assertNotIn('close', record, 'a zero price is not a price')
        self.assertNotIn('open', record)
        self.assertNotIn('shots', record)
        text = 'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,AvgCH,AvgCD,AvgCA,AHCh\nE0,01/09/19,A,B,2,0,1.5,4.0,6.0,-0.3\n'
        record = ss.parse_csv(text, 'EPL', 'u', RETRIEVED, start_year=2019)[0]
        self.assertEqual(record['close'], {'home': 1.5, 'draw': 4.0, 'away': 6.0, 'books': {'1x2': 'Average'}},
                         'a handicap off the quarter-goal grid, or without prices, is dropped')

    def test_mls_single_file(self):
        records = ss.parse_csv(MLS, 'MLS', ss.season_url('MLS', None), RETRIEVED, seasons={2025})
        self.assertEqual([r['season'] for r in records], ['2025', '2025'])
        first, second = records
        self.assertEqual(first['id'], 'MLS-2025-09-20-real-salt-lake-cf-montreal')
        self.assertEqual(first['kickoff'], '2025-09-20T01:30:00Z', 'the file dates MLS games in UK time')
        self.assertEqual(first['close']['books'], {'1x2': 'Pinnacle'})
        self.assertNotIn('open', first, 'MLS has closing prices only')
        self.assertEqual(second['close'], {'home': 1.86, 'draw': 3.73, 'away': 3.73, 'books': {'1x2': 'Average'}})
        self.assertEqual(len(ss.parse_csv(MLS, 'MLS', 'u', RETRIEVED)), 3, 'no filter keeps every season')

    def test_slug(self):
        self.assertEqual(ss.slug("Nott'm Forest"), 'nott-m-forest')
        self.assertEqual(ss.slug('CF Montréal'), 'cf-montreal')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def fetcher(self, pages):
        calls = []

        def fetch(url):
            calls.append(url)
            return pages[url]
        return fetch, calls

    def test_collect_reads_one_file_per_season(self):
        fetch, calls = self.fetcher({ss.season_url('EPL', 2016): OLD, ss.season_url('EPL', 2025): NEW})
        records = ss.collect('EPL', [2016, 2025], fetch=fetch, clock=lambda: datetime(2026, 9, 24, tzinfo=timezone.utc))
        self.assertEqual(calls, [ss.season_url('EPL', 2016), ss.season_url('EPL', 2025)])
        self.assertEqual([r['season'] for r in records], ['2016-17', '2025-26', '2025-26'])
        self.assertEqual(records[0]['source'], ss.season_url('EPL', 2016))
        self.assertEqual(records[0]['retrievedAt'], '2026-09-24T00:00:00Z')

    def test_update_is_append_only_and_idempotent(self):
        records = parse_old() + parse_new()
        self.assertEqual(ss.update('EPL', records, self.root), (3, 0))
        self.assertEqual(boxscores.verify(self.root), [])
        again = ss.parse_csv(NEW, 'EPL', 'https://example/2526/E0.csv', '2026-09-25T00:00:00Z', start_year=2025)
        self.assertEqual(ss.update('EPL', again, self.root), (0, 0), 'a new retrieval time alone is not a change')
        corrected = ss.parse_csv(NEW.replace('Liverpool,Bournemouth,4,2', 'Liverpool,Bournemouth,4,3'),
                                 'EPL', 'https://example/2526/E0.csv', RETRIEVED, start_year=2025)
        self.assertEqual(ss.update('EPL', corrected, self.root), (0, 1))
        lines = boxscores.read_store(ss.store_path('EPL', self.root))
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[-1]['revision'], 2)
        current = {r['id']: r for r in ss.load('EPL', self.root)}
        self.assertEqual(current['EPL-2025-08-15-liverpool-bournemouth']['awayGoals'], 3, 'the last line wins')
        self.assertEqual(boxscores.verify(self.root), [])
        ledger = json.loads((self.root / 'ledger.json').read_text())
        self.assertEqual(ledger['epl.jsonl']['lines'], 4)

    def test_a_changed_line_is_caught(self):
        ss.update('EPL', parse_old(), self.root)
        path = ss.store_path('EPL', self.root)
        path.write_text(path.read_text().replace('"homeGoals":0', '"homeGoals":1'))
        self.assertEqual(boxscores.verify(self.root), ['epl.jsonl: a recorded line was changed'])

    def test_load_orders_by_kickoff(self):
        ss.update('EPL', parse_new() + parse_old(), self.root)
        self.assertEqual([r['season'] for r in ss.load('EPL', self.root)], ['2016-17', '2025-26', '2025-26'])


def espn_team(team_id, name, short, abbreviation, color='ff0000'):
    return {'id': team_id, 'displayName': name, 'shortDisplayName': short, 'name': name, 'location': name,
            'abbreviation': abbreviation, 'color': color, 'alternateColor': 'FFFFFF',
            'logo': f'https://a.espncdn.com/{team_id}.png'}


TEAMS = {
    'eng.1': [espn_team('364', 'Liverpool', 'Liverpool', 'LIV'), espn_team('349', 'AFC Bournemouth', 'Bournemouth', 'BOU'),
              espn_team('393', 'Nottingham Forest', 'Nottm Forest', 'NFO'), espn_team('360', 'Manchester United', 'Man United', 'MAN')],
    'usa.1': [espn_team('9720', 'CF Montréal', 'CF Montréal', 'MTL'), espn_team('4771', 'Real Salt Lake', 'Salt Lake', 'RSL'),
              espn_team('190', 'Red Bull New York', 'Red Bull NY', 'RBNY')],
    'uefa.champions': [espn_team('364', 'Liverpool', 'Liverpool', 'LIV'), espn_team('86', 'Real Madrid', 'Real Madrid', 'RMA')],
}


def teams_payload(teams):
    return {'sports': [{'leagues': [{'teams': [{'team': t} for t in teams]}]}]}


class TeamMapTests(unittest.TestCase):
    def test_aliases_accents_and_unmatched(self):
        matched, unmatched = ss.match_names('EPL', {'Liverpool', 'Bournemouth', "Nott'm Forest", 'Man United', 'Wrexham'},
                                            TEAMS['eng.1'])
        self.assertEqual({k: v['id'] for k, v in matched.items()},
                         {'Liverpool': '364', 'Bournemouth': '349', "Nott'm Forest": '393', 'Man United': '360'})
        self.assertEqual(unmatched, ['Wrexham'])
        matched, _ = ss.match_names('MLS', {'CF Montreal', 'Real Salt Lake', 'New York Red Bulls'}, TEAMS['usa.1'])
        self.assertEqual({k: v['id'] for k, v in matched.items()},
                         {'CF Montreal': '9720', 'Real Salt Lake': '4771', 'New York Red Bulls': '190'})

    def test_team_map_from_the_teams_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            epl = ss.parse_csv(NEW.replace('15/08/2025', '15/08/2026').replace('21/12/2025', '21/12/2026'),
                               'EPL', 'u', RETRIEVED, start_year=2026)
            epl[1] = dict(epl[1], home="Nott'm Forest", away='Wrexham', id='EPL-x')
            ss.update('EPL', epl, root)
            ss.update('MLS', ss.parse_csv(MLS.replace('2025', '2026'), 'MLS', 'u', RETRIEVED), root)
            urls = []

            def fetch(url):
                urls.append(url)
                slug = url.split('/soccer/')[1].split('/')[0]
                return teams_payload(TEAMS[slug])
            result = ss.team_map(root, fetch=fetch, today=date(2026, 9, 24))
        self.assertEqual(len(urls), 3, 'one teams list per league')
        epl_teams = result['leagues']['EPL']['teams']
        self.assertEqual(sorted(epl_teams), ['Bournemouth', 'Liverpool', "Nott'm Forest"])
        self.assertEqual(epl_teams['Liverpool'], {'espnId': '364', 'abbreviation': 'LIV', 'espnName': 'Liverpool',
                                                  'shortName': 'Liverpool', 'color': '#ff0000', 'alternateColor': '#ffffff',
                                                  'logo': 'https://a.espncdn.com/364.png'})
        self.assertEqual(result['unmatched'], {'EPL': ['Wrexham'], 'MLS': ['Chicago Fire', 'Philadelphia Union']})
        self.assertEqual(result['leagues']['UCL']['teams']['364']['footballData'], {'EPL': 'Liverpool'})
        self.assertNotIn('footballData', result['leagues']['UCL']['teams']['86'])
        self.assertEqual(ss.from_espn(result, 'EPL', 393), "Nott'm Forest")
        self.assertEqual(ss.from_espn(result, 'UCL', '364'), 'Liverpool')
        self.assertIsNone(ss.from_espn(result, 'MLS', '1'))

    def test_scoreboards_stand_in_when_the_teams_list_fails(self):
        seen = []

        def fetch(url):
            seen.append(url)
            if url.endswith('/teams'):
                raise HTTPError(url, 500, 'down', None, io.BytesIO())
            day = url.rsplit('=', 1)[1]
            if day != '20260920':
                return {'events': []}
            return {'events': [{'competitions': [{'competitors': [{'team': TEAMS['eng.1'][0]}, {'team': TEAMS['eng.1'][1]}]}]}]}
        teams = ss.espn_teams('EPL', fetch, days=5, today=date(2026, 9, 21))
        self.assertEqual(sorted(t['id'] for t in teams), ['349', '364'])
        self.assertEqual(len(seen), 6, 'the teams list, then one scoreboard a day')
        self.assertTrue(seen[1].endswith('scoreboard?dates=20260921'))


if __name__ == '__main__':
    unittest.main()
