"""Vegas vs reality: closing lines against finals, built from the stores at site-build time.

tests/fixtures/vegas.json is the exact payload the fixture stores below produce. When the builder's output
changes on purpose, regenerate it with:
  python3 -c "import sys; sys.path[:0] = ['tests', 'scripts']; import test_vegas; test_vegas.regenerate()"
"""
import json
import sys
import contextlib
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_site
import publication_guard
import vegas

FIXTURE = ROOT / 'tests' / 'fixtures' / 'vegas.json'
NOW = datetime(2026, 10, 7, 16, 0, tzinfo=timezone.utc)
# The reference scorecard (owner decision 7, Oct 7) was computed from the stores through this instant.
SCORECARD_THROUGH = '2026-10-07T12:00Z'


def football(event, home_score, away_score, spread=None, total=None, home_ml=None, away_ml=None,
             provider='ESPN BET', league='NFL', season=2025, kickoff='2025-10-05T17:00Z'):
    close = {k: v for k, v in (('spread', spread), ('total', total), ('homeML', home_ml), ('awayML', away_ml))
             if v is not None}
    return {'eventId': event, 'league': league, 'season': season, 'kickoff': kickoff, 'neutral': False,
            'home': {'abbreviation': 'HOM', 'score': home_score}, 'away': {'abbreviation': 'AWY', 'score': away_score},
            'market': {'provider': provider, 'close': close} if provider else None, 'players': []}


def hoops(event, home_score, away_score, spread=None, total=None, league='NBA', season=2025, books=1,
          kickoff='2025-01-10T00:30Z', home='Home City', away='Away Town'):
    close = None if spread is None and total is None else {'spread': spread, 'total': total, 'books': books}
    return {'eventId': event, 'id': f'{league}-{event}', 'league': league, 'season': season, 'kickoff': kickoff,
            'state': 'post', 'type': 2, 'neutral': False, 'homeScore': home_score, 'awayScore': away_score,
            'home': {'school': home, 'short': 'Homers', 'abbreviation': 'HOM'},
            'away': {'school': away, 'short': 'Visitors', 'abbreviation': 'AWY'}, 'close': close, 'open': close}


def soccer(ident, home_goals, away_goals, x12, ah=None, ou=None, league='EPL', season='2024-25',
           date='2024-09-14', home='Norwich', away='Man City', kickoff=None):
    close = {'home': x12[0], 'draw': x12[1], 'away': x12[2], 'books': {'1x2': 'Pinnacle'}}
    if ah is not None:
        close.update({'ahLine': ah, 'ahHome': 1.9, 'ahAway': 1.95})
    if ou is not None:
        close.update({'over25': ou[0], 'under25': ou[1]})
    return {'id': f'{league}-{ident}', 'league': league, 'season': season, 'date': date,
            'kickoff': kickoff or f'{date}T14:00:00Z', 'home': home, 'away': away,
            'homeGoals': home_goals, 'awayGoals': away_goals, 'close': close}


def write_store(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows), encoding='utf-8')


def fixture_stores(root):
    root = Path(root)
    write_store(root / 'boxscores' / 'nfl-2025.jsonl', [
        football('1', 27, 17, -7, 44.5, -300, 250),               # home favorite covers, under
        football('2', 20, 24, 3.5, 47.5, 150, -175),              # away favorite (home line +3.5) covers
        football('3', 24, 21, -3, 41.5, -160, 135),               # push on the spread, over
        football('4', 30, 10, -125, -115, -150, 130, season=2023, kickoff='2023-09-10T17:00Z'),  # odds in the line
        football('5', 17, 20, 0, 40.5, -110, -110),               # exact 50/50 moneyline, pick'em spread
        football('6', 10, 13, -2.5, 40.5, -140, 120),             # first version, revised below
        football('7', 20, 20, -4.5, 43.5, -200, 170),             # a tie
        football('8', 31, 10, -10.5, 45.5, -500, 380),            # exactly 80%, home favorite
        football('9', 3, 28, 10.5, 45.5, 380, -500),              # exactly 80%, away favorite
        football('10', 23, 20, 8.5, 47.5, 320, -400),             # +320 underdog wins
        football('11', 21, 14, provider=None),                    # no market at all
        football('6', 13, 10, -2.5, 40.5, -140, 120),             # the revision wins: home won by 3
    ])
    write_store(root / 'boxscores' / 'cfb-2025.jsonl', [
        football('20', 45, 10, -10, 60.5, -500, 400, provider='accuscore', league='CFB'),  # projections service
        football('21', 52, 14, -31, 58.5, None, None, league='CFB'),                       # 30+ favorite covers
        football('22', 21, 24, -3.5, 48.5, -170, 145, league='CFB'),
    ])
    write_store(root / 'hoops' / 'nba-2025.jsonl', [
        hoops('1', 110, 100, -5.5, 220.5),                        # favorite covers, under, within 5
        hoops('2', 100, 110, 18.5, 230, books=7),                 # away favorite of 18.5 wins, dog covers
        hoops('3', 101, 99),                                      # no line
        hoops('4', 99, 101, -3, 199.5),                           # first version, revised below
        hoops('4', 103, 100, -3, 199.5),                          # revision: a push at -3
        hoops('5', 120, 118, -1.5, 500),                          # impossible total, spread kept
    ])
    write_store(root / 'hoops' / 'cbb-2024.jsonl', [
        hoops('9', 59, 60, -26, 130.5, league='CBB', season=2024, kickoff='2023-12-04T01:00Z',
              home='Mississippi State', away='Southern'),         # 26-point underdog wins
        hoops('10', 80, 50, -30, 140.5, league='CBB', season=2024),
    ])
    write_store(root / 'soccer' / 'epl.jsonl', [
        soccer('a', 1, 0, (1.5, 4.2, 6.5), ah=-0.75, ou=(1.9, 1.95)),    # half win on -0.75 counts as cover
        soccer('b', 1, 1, (2.1, 3.4, 3.6), ah=-0.25, ou=(2.0, 1.85)),    # draw: half loss, dog covers
        soccer('c', 2, 1, (2.7, 3.3, 2.7), ah=0, ou=(1.95, 1.9)),        # pick'em and level ball
        soccer('d', 0, 2, (5.0, 3.8, 1.6), season='2016-17', date='2016-08-13'),  # no handicap or total stored
        soccer('e', 3, 2, (20.0, 9.0, 1.09), ah=3.0, ou=(1.5, 2.6), date='2019-09-14'),  # big upset
    ])
    write_store(root / 'soccer' / 'mls.jsonl', [
        soccer('m1', 2, 1, (1.8, 3.9, 4.5), league='MLS', season='2025', date='2025-05-03',
               home='Vancouver Whitecaps', away='LA Galaxy'),
        soccer('m2', 0, 0, (2.2, 3.4, 3.2), league='MLS', season='2025', date='2025-05-10'),
    ])
    return root


def regenerate():
    with tempfile.TemporaryDirectory() as folder:
        payload = vegas.build(NOW, root=fixture_stores(folder))
    FIXTURE.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')


class VegasFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = fixture_stores(cls.folder.name)
        cls.payload = vegas.build(NOW, root=cls.root)
        cls.by = {block['league']: block for block in cls.payload['leagues']}

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_home_line_sign_convention_names_the_right_favorite(self):
        rows = vegas.load('NFL', self.root)
        home_fav = next(r for r in rows if r['spread'] == -7)
        away_fav = next(r for r in rows if r['spread'] == 3.5)
        self.assertEqual(vegas.cover(home_fav, home_fav['spread']), ('favorite', 'home', 10))
        self.assertEqual(vegas.cover(away_fav, away_fav['spread']), ('favorite', 'away', 4))
        self.assertEqual(vegas.favorite_side(away_fav)[0], 'away')

    def test_last_row_per_event_wins(self):
        nfl = vegas.load('NFL', self.root)
        self.assertEqual(len(nfl), 11)
        revised = next(r for r in nfl if r['spread'] == -2.5)
        self.assertEqual((revised['home'], revised['away']), (13, 10))
        self.assertEqual(self.by['NBA']['games'], 5)
        self.assertEqual(self.by['NBA']['spread']['push'], 1)

    def test_odds_in_the_line_field_are_invalid_but_moneylines_still_count(self):
        nfl = self.by['NFL']
        corrupt = next(r for r in vegas.load('NFL', self.root) if r['season'] == 2023)
        self.assertIsNone(corrupt['spread'])
        self.assertIsNone(corrupt['total'])
        self.assertTrue(corrupt['badLine'])
        self.assertEqual(corrupt['homeML'], -150)
        self.assertEqual(nfl['spread']['missN'], 9)            # 11 games - no market - odds-in-line
        self.assertEqual(nfl['total']['n'], 9)
        self.assertEqual(nfl['favorite']['n'], 9)              # 10 with moneylines, minus the exact 50/50
        self.assertIsNone(vegas.valid_spread(70.5))
        self.assertEqual(vegas.valid_spread(-70), -70)
        self.assertIsNone(vegas.valid_total(14.5, 'football'))
        self.assertIsNone(vegas.valid_total(120.5, 'football'))
        self.assertEqual(vegas.valid_total(120, 'football'), 120)
        self.assertEqual(self.by['NBA']['total']['n'], 3)      # the impossible 500 total is out
        self.assertEqual(self.by['NBA']['spread']['missN'], 4)  # its spread stays

    def test_projection_service_rows_are_skipped(self):
        cfb = self.by['CFB']
        self.assertEqual(cfb['games'], 3)
        self.assertEqual(cfb['spread']['missN'], 2)
        self.assertEqual(cfb['favorite']['n'], 1)
        self.assertEqual(cfb['sources'], [['ESPN BET', 2]])
        self.assertTrue(any('projections service' in note for note in cfb['notes']))

    def test_exact_even_moneyline_has_no_favorite_and_pickem_has_no_cover(self):
        even = next(r for r in vegas.load('NFL', self.root) if r['homeML'] == -110)
        self.assertIsNone(vegas.favorite_side(even))
        nfl = self.by['NFL']
        self.assertEqual(nfl['spread']['n'], 8)                # 9 lined games minus the pick'em
        self.assertEqual(nfl['spread']['missN'], 9)            # the pick'em still counts toward the miss
        self.assertTrue(any('50/50' in note for note in nfl['notes']))

    def test_pushes_and_ties_are_counted_with_the_published_conventions(self):
        nfl = self.by['NFL']
        spread = nfl['spread']
        self.assertEqual((spread['favorite'], spread['dog'], spread['push']), (5, 2, 1))
        self.assertEqual(spread['favoritePct'], 62.5)          # pushes stay in the denominator
        self.assertEqual(spread['pushPct'], 12.5)
        favorite = nfl['favorite']
        self.assertEqual((favorite['won'], favorite['lost'], favorite['tied']), (7, 1, 1))
        self.assertEqual(favorite['decided'], 8)
        self.assertEqual(favorite['pct'], 87.5)                # the tie stays out of the win rate
        self.assertEqual(nfl['total']['over'] + nfl['total']['under'] + nfl['total']['push'], nfl['total']['n'])

    def test_calibration_bins_compare_the_no_vig_price_with_the_result(self):
        bins = {b['low']: b for b in self.by['NFL']['calibration']}
        # -500/+380 is exactly 80% with the cut removed; home or away, both land in the 80-90 bin.
        self.assertEqual(bins[80]['n'], 2)
        self.assertEqual(bins[80]['priced'], 80.0)
        self.assertEqual(bins[80]['won'], 100.0)
        self.assertEqual(bins[70]['n'], 2)                     # -300/+250 (72.4%) won, +320/-400 (77.1%) lost
        self.assertEqual(bins[70]['wins'], 1)
        self.assertEqual(sum(b['n'] for b in bins.values()), self.by['NFL']['favorite']['decided'])
        self.assertEqual(self.by['NBA']['calibration'], [])    # no basketball moneylines, so no priced table
        self.assertEqual([b['low'] for b in self.by['EPL']['calibration']], [40, 50, 60, 80])

    def test_basketball_uses_the_spread_favorite_and_five_and_ten_point_windows(self):
        nba = self.by['NBA']
        self.assertEqual(nba['favorite']['basis'], 'spread')
        self.assertEqual((nba['favorite']['won'], nba['favorite']['lost']), (4, 0))
        self.assertEqual([w['within'] for w in nba['spread']['within']], [5, 10])
        self.assertEqual([w['within'] for w in nba['total']['within']], [5, 10])
        self.assertEqual(nba['sources'], [['One book', 3], ['Multi-book consensus', 1]])
        self.assertEqual(nba['seasons']['label'], '2024-25')
        self.assertIn('Biggest upset in the stored lines: Southern (+26) won 60-59 at Mississippi State on '
                      'Dec 3, 2023.', self.by['CBB']['facts'])

    def test_soccer_handicap_quarter_lines_split_and_draws_are_not_wins(self):
        epl = self.by['EPL']
        self.assertEqual(epl['favorite']['basis'], '1x2')
        self.assertEqual((epl['favorite']['won'], epl['favorite']['drew'], epl['favorite']['lost']), (2, 1, 1))
        self.assertEqual(epl['favorite']['n'], 4)              # the equal-price pick'em has no favorite
        self.assertEqual(epl['favorite']['pct'], 50.0)         # the draw counts as not won
        spread = epl['spread']
        self.assertEqual((spread['favorite'], spread['dog'], spread['push']), (1, 2, 0))
        self.assertEqual(spread['missN'], 4)                   # level ball counts toward the miss
        self.assertEqual(epl['total']['line'], 2.5)
        self.assertIsNone(epl['total']['mae'])
        self.assertEqual((epl['total']['n'], epl['total']['over']), (4, 2))
        self.assertIsNone(self.by['MLS']['spread'])
        self.assertIsNone(self.by['MLS']['total'])
        self.assertTrue(any(f.startswith('Biggest upset in the stored prices: Norwich beat Man City 3-2 on Sep 14, 2019.')
                            for f in epl['facts']))

    def test_facts_are_computed_sentences(self):
        nfl = self.by['NFL']['facts']
        self.assertIn('3 points is the most common NFL final margin: 4 of 11 games (36.4%).', nfl)
        self.assertIn('Underdogs at +300 or longer won 1 of 3 NFL games (33.3%).', nfl)
        self.assertIn('College football favorites of 30+ points won all 1 straight up, but covered only 1 (100.0%).',
                      self.by['CFB']['facts'])

    def test_a_basketball_season_with_no_closing_lines_still_builds(self):
        # The hoops store writes `close: null` until a book posts, so a new season can start with no lines.
        # Its spread block must still hand the favorite block a straight-up counter, not a bare dict.
        self.assertEqual(vegas.spread_block([], 'NBA'), (None, [], {}))
        self.assertEqual(vegas.spread_block([], 'NBA')[2]['won'], 0)
        with tempfile.TemporaryDirectory() as folder:
            root = fixture_stores(folder)
            write_store(root / 'hoops' / 'nba-2027.jsonl', [hoops('30', 101, 99, season=2027, kickoff='2026-10-21T23:30Z')])
            write_store(root / 'hoops' / 'cbb-2027.jsonl', [hoops('31', 70, 60, league='CBB', season=2027,
                                                                    kickoff='2026-11-04T00:00Z')])
            (root / 'hoops' / 'cbb-2024.jsonl').unlink()       # a whole league with no line at all
            payload = vegas.build(NOW, root=root)
        by = {block['league']: block for block in payload['leagues']}
        new = next(row for row in by['NBA']['bySeason'] if row['season'] == '2026-27')
        self.assertEqual(new['favorite'], {'won': 0, 'decided': 0, 'pct': None})
        self.assertIsNone(new['cover'])
        self.assertIsNone(new['over'])
        self.assertEqual(by['NBA']['favorite']['decided'], 4)  # the lined seasons are unchanged
        cbb = by['CBB']
        self.assertIsNone(cbb['spread'])
        self.assertIsNone(cbb['total'])
        self.assertEqual((cbb['favorite']['decided'], cbb['favorite']['pct']), (0, None))
        self.assertIsNone(cbb['meaning'])                      # nothing to say, so no claim is made
        self.assertTrue(any('no closing spread' in note for note in cbb['notes']))

    def test_soccer_upset_date_is_the_eastern_kickoff_day_not_the_uk_date(self):
        # football-data.co.uk dates an MLS evening game by the UK day: 7:30 PM ET on Sep 29 is "Sep 30" there.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_store(root / 'soccer' / 'mls.jsonl', [
                soccer('m9', 4, 3, (11.0, 6.5, 1.25), league='MLS', season='2019', date='2019-09-30',
                       kickoff='2019-09-29T23:30:00Z', home='Vancouver Whitecaps', away='LA Galaxy')])
            block = vegas.compute('MLS', root=root)
        self.assertEqual(block['through'], '2019-09-29')
        self.assertTrue(any(f.startswith('Biggest upset in the stored prices: Vancouver Whitecaps beat LA Galaxy 4-3 '
                                         'on Sep 29, 2019.') for f in block['facts']), block['facts'])
        self.assertFalse(any('Sep 30' in f for f in block['facts']))

    def test_meaning_is_built_from_each_leagues_own_numbers(self):
        nfl, nba, epl, mls = (self.by[league]['meaning'] for league in ('NFL', 'NBA', 'EPL', 'MLS'))
        # Football: the actual win rate, its price, then the spread and total, with the -110 break-even.
        self.assertIn('The closing moneyline favorite won 87.5% of 8 games.', nfl)
        self.assertIn("With the book's cut removed, its closing odds said 68.0%.", nfl)
        self.assertIn('the favorite covered 62.5% of 8 games, and the over hit 11.1% of 9 games.', nfl)
        self.assertIn('At −110 you need 52.4% just to break even.', nfl)
        self.assertIn('0.0% of 1 game.', self.by['CFB']['meaning'])
        # Basketball stores no price, so there is no price comparison.
        self.assertIn('The closing spread favorite won 100.0% of 4 games.', nba)
        self.assertNotIn('price', nba)
        self.assertNotIn('odds', nba)
        # Soccer: a draw is not a win; no American break-even; MLS has no handicap or total sentence.
        self.assertIn('a draw counting as not won', epl)
        self.assertIn('Against the handicap the favorite covered 33.3% of 3 games', epl)
        self.assertIn('Over 2.5 goals hit 50.0% of 4 games; the closing prices said 52.9%.', epl)
        self.assertNotIn('−110', epl)
        for phrase in ('handicap', 'spread', 'total', 'Over', 'coin flip', '−110'):
            self.assertNotIn(phrase, mls)
        # A handful of fixture games never earns a verdict word, even a 50.0% "coin flip".
        for block in self.payload['leagues']:
            for phrase in ('usually', 'coin flip', 'close to what happened', 'more often than', 'about half'):
                self.assertNotIn(phrase, block['meaning'], block['league'])
            self.assertIn('samples are small', block['meaning'])

    def test_payload_is_labeled_and_matches_the_committed_view_fixture(self):
        self.assertEqual(self.payload['label'], 'Closing lines')
        self.assertEqual(self.payload['breakEven110'], 52.4)
        self.assertEqual([b['league'] for b in self.payload['leagues']], list(vegas.LEAGUES))
        for block in self.payload['leagues']:
            self.assertTrue(block['seasons']['label'] and block['through'] and block['games'])
        committed = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.assertEqual(committed, json.loads(json.dumps(self.payload)))

    def test_build_site_passes_preloaded_football_records_without_changing_the_result(self):
        records = vegas.latest_rows(sorted((self.root / 'boxscores').glob('*.jsonl')), 'eventId')
        self.assertEqual(vegas.build(NOW, root=self.root, football=records), self.payload)

    def test_only_the_exact_public_path_passes_the_publication_guard(self):
        self.assertTrue(publication_guard.allowed_path(Path('data/app/vegas.json')))
        for path in ('data/vegas.json', 'data/app/vegas/NFL.json', 'data/app/vegas-NFL.json', 'vegas.json'):
            self.assertFalse(publication_guard.allowed_path(Path(path)), path)
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / 'index.html').write_text('<title>Site</title>')
            (site / 'data' / 'app').mkdir(parents=True)
            (site / 'data' / 'app' / 'vegas.json').write_text(json.dumps(self.payload))
            self.assertEqual(publication_guard.audit(site)['issues'], [])

    def test_a_vegas_failure_drops_only_its_file_and_never_blocks_the_site_build(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(build_site, 'OUT', Path(folder)):
            with mock.patch.object(build_site.vegas, 'build', side_effect=KeyError('won')), \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertFalse(build_site.write_vegas(NOW, []))
            self.assertFalse((Path(folder) / 'vegas.json').exists())
            self.assertIn('Vegas vs reality skipped: KeyError', err.getvalue())
            with mock.patch.object(build_site.vegas, 'build', return_value=self.payload):
                self.assertTrue(build_site.write_vegas(NOW, []))
            self.assertEqual(json.loads((Path(folder) / 'vegas.json').read_text(encoding='utf-8')),
                             json.loads(json.dumps(self.payload)))

    def test_a_missing_store_simply_leaves_that_league_out(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = vegas.build(NOW, root=Path(folder))
        self.assertEqual(payload['leagues'], [])


class VegasScorecardTests(unittest.TestCase):
    """The committed stores reproduce the reference "How often is Vegas right?" headline (Oct 7, 2026)."""

    def close(self, actual, expected):
        self.assertIsNotNone(actual)
        self.assertLessEqual(abs(actual - expected), 0.5, f'{actual} vs {expected}')

    def test_football_headline_numbers(self):
        expected = {'NFL': (67.8, 890, 50.1, 51.5), 'CFB': (75.1, 2747, 50.3, 51.6)}
        for league, (won, decided, covered, over) in expected.items():
            block = vegas.compute(league, through=SCORECARD_THROUGH)
            self.assertEqual(block['favorite']['basis'], 'moneyline')
            self.close(block['favorite']['pct'], won)
            self.assertEqual(block['favorite']['decided'], decided)
            self.close(block['spread']['favoritePct'], covered)
            self.close(block['total']['overPct'], over)
        nfl = vegas.compute('NFL', through=SCORECARD_THROUGH)
        self.assertEqual((nfl['favorite']['won'], nfl['favorite']['lost'], nfl['favorite']['tied']), (603, 287, 1))
        self.assertEqual((nfl['spread']['favorite'], nfl['spread']['dog'], nfl['spread']['push']), (434, 429, 4))
        self.close(nfl['spread']['mae'], 9.7)

    def test_basketball_and_soccer_headline_numbers(self):
        expected = {'NBA': (68.8, 49.7, 50.4), 'CBB': (73.1, 49.5, 50.0), 'EPL': (55.5, 45.0, 54.9)}
        for league, (won, covered, over) in expected.items():
            block = vegas.compute(league, through=SCORECARD_THROUGH)
            self.close(block['favorite']['pct'], won)
            self.close(block['spread']['favoritePct'], covered)
            self.close(block['total']['overPct'], over)
        self.close(vegas.compute('MLS', through=SCORECARD_THROUGH)['favorite']['pct'], 50.1)

    def test_real_meaning_lines_do_not_overclaim(self):
        nfl = vegas.compute('NFL', through=SCORECARD_THROUGH)['meaning']
        self.assertIn('usually won: 67.8% of 890 games', nfl)
        self.assertIn('close to a coin flip', nfl)
        self.assertIn('52.4%', nfl)
        for league in ('NBA', 'CBB'):
            text = vegas.compute(league, through=SCORECARD_THROUGH)['meaning']
            self.assertIn('closing spread favorite usually won', text)
            self.assertNotIn('price', text)
            self.assertNotIn('odds', text)
        mls = vegas.compute('MLS', through=SCORECARD_THROUGH)['meaning']
        self.assertIn('won about half the time: 50.1%', mls)
        for phrase in ('usually', 'spread', 'handicap', 'total', 'coin flip'):
            self.assertNotIn(phrase, mls)
        epl = vegas.compute('EPL', through=SCORECARD_THROUGH)['meaning']
        self.assertNotIn('coin flip', epl)                     # the handicap favorite covered only 45%
        self.assertIn('Sep 29, 2019', ' '.join(vegas.compute('MLS', through=SCORECARD_THROUGH)['facts']))


if __name__ == '__main__':
    unittest.main()
