import math
import random
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import hoops_model as hm
import model_v2

OFFENSE = {'A': 6.0, 'B': 2.0, 'C': 0.0, 'D': -3.0, 'E': -5.0}
DEFENSE = {'A': -4.0, 'B': 1.0, 'C': 3.0, 'D': 0.0, 'E': 0.0}
MEAN, HOME = 110.0, 2.5
EXACT = {'margin': {'halfLife': 100000, 'ridge': 1e-4, 'carry': 1.0},
         'total': {'halfLife': 100000, 'ridge': 1e-4, 'carry': 1.0}, 'refitDays': 1}


def game(n, season, start, home, away, home_score, away_score, neutral=False, close=None, opening=None):
    return {'id': f'NBA-{n}', 'eventId': str(n), 'league': 'NBA', 'season': season, 'type': 2,
            'kickoff': (start + timedelta(hours=12 * n)).strftime('%Y-%m-%dT%H:%MZ'), 'neutral': neutral,
            'home': {'id': home, 'abbreviation': home}, 'away': {'id': away, 'abbreviation': away},
            'homeScore': home_score, 'awayScore': away_score, 'state': 'post', 'close': close, 'open': opening}


def league(rounds=4, season=2025, start=datetime(2024, 10, 22, 23, tzinfo=timezone.utc), noise=0.0, seed=1):
    """Every pair meets home and away each round; scores follow the model exactly (plus optional noise)."""
    rng, games, n = random.Random(seed), [], 0
    teams = sorted(OFFENSE)
    for _ in range(rounds):
        for home in teams:
            for away in teams:
                if home == away:
                    continue
                neutral = n % 11 == 0
                h = MEAN + (0 if neutral else HOME) + OFFENSE[home] + DEFENSE[away] + rng.gauss(0, noise)
                a = MEAN + OFFENSE[away] + DEFENSE[home] + rng.gauss(0, noise)
                games.append(game(n, season, start, home, away, h, a, neutral))
                n += 1
    return games


class SolverTests(unittest.TestCase):
    def test_conjugate_gradients_match_a_direct_solve(self):
        rng = random.Random(4)
        size, rows = 12, 60
        offense = [2 + 2 * rng.randrange(5) for _ in range(rows)]
        defense = [3 + 2 * rng.randrange(5) for _ in range(rows)]
        home = [rng.random() < 0.5 for _ in range(rows)]
        weights = [0.3 + rng.random() for _ in range(rows)]
        targets = [100 + 10 * rng.random() for _ in range(rows)]
        penalty = [0.0, 0.0] + [1.5] * (size - 2)
        centre = [0.0, 0.0] + [rng.uniform(-3, 3) for _ in range(size - 2)]
        iterative = hm.solve(offense, defense, home, weights, targets, penalty, centre, tolerance=1e-12)
        matrix = [[penalty[i] if i == j else 0.0 for j in range(size)] for i in range(size)]
        vector = [penalty[i] * centre[i] for i in range(size)]
        for o, d, h, w, y in zip(offense, defense, home, weights, targets):
            columns = [0, o, d] + ([1] if h else [])
            for i in columns:
                vector[i] += w * y
                for j in columns:
                    matrix[i][j] += w
        direct = model_v2.solve(matrix, vector)
        self.assertLess(max(abs(a - b) for a, b in zip(iterative, direct)), 1e-6)

    def test_a_warm_start_reaches_the_same_answer(self):
        games, params = hm.prepare(league(noise=5.0)), hm.PARAMS['NBA']
        cutoff = games[-1].t + 1
        cold = hm.Model('NBA', games, cutoff, 2025, params)
        warm = hm.Model('NBA', games, cutoff, 2025, params, warm=hm.Model('NBA', games, games[30].t, 2025, params))
        for a, b in zip(cold.fits['margin'].beta, warm.fits['margin'].beta):
            self.assertAlmostEqual(a, b, places=4)

    def test_known_ratings_are_recovered_on_a_tiny_league(self):
        games = hm.prepare(league())
        model = hm.Model('NBA', games, games[-1].t + 1, 2025, EXACT)
        ratings = model.fits['margin']
        self.assertAlmostEqual(ratings.beta[0], MEAN, places=2)
        self.assertAlmostEqual(ratings.beta[1], HOME, places=2)
        for team in OFFENSE:
            off, dfn = ratings.team(team)
            self.assertAlmostEqual(off, OFFENSE[team], places=2)
            self.assertAlmostEqual(dfn, DEFENSE[team], places=2)
        forecast = model.predict('A', 'E')
        self.assertAlmostEqual(forecast['margin'], HOME + (6 + 0) - (-5 - 4), places=2)
        self.assertAlmostEqual(forecast['total'], 2 * MEAN + HOME + 6 + 0 - 5 - 4, places=2)
        self.assertAlmostEqual(model.predict('A', 'E', neutral=True)['margin'], 6 + 0 - (-5 - 4), places=2)
        self.assertLess(forecast['sdMargin'], 0.01)  # noise-free games leave no residual

    def test_residual_spread_follows_the_noise(self):
        games = hm.prepare(league(rounds=20, noise=8.0))
        forecast = hm.Model('NBA', games, games[-1].t + 1, 2025, EXACT).predict('A', 'B')
        self.assertTrue(8.0 < forecast['sdMargin'] < 13.0)  # margin noise is sqrt(2) * 8 = 11.3
        self.assertTrue(8.0 < forecast['sdTotal'] < 13.0)
        self.assertTrue(0.5 < forecast['homeWinProb'] < 1.0)


class PriorTests(unittest.TestCase):
    def setUp(self):
        last = league(season=2024, start=datetime(2023, 10, 24, 23, tzinfo=timezone.utc))
        self.games = hm.prepare(last + league())
        self.opening = datetime(2024, 10, 22, 8, tzinfo=timezone.utc).timestamp()

    def params(self, carry):
        return {**EXACT, 'margin': {**EXACT['margin'], 'carry': carry}, 'total': {**EXACT['total'], 'carry': carry}}

    def test_a_new_season_starts_from_last_season_shrunk_by_carry(self):
        for carry in (0.0, 0.5, 1.0):
            params = self.params(carry)
            prior = hm.season_prior('NBA', self.games, 2025, params)
            model = hm.Model('NBA', self.games, self.opening, 2025, params, prior)
            self.assertEqual(model.used, [])
            full = HOME + OFFENSE['A'] + DEFENSE['E'] - OFFENSE['E'] - DEFENSE['A']
            self.assertAlmostEqual(model.predict('A', 'E')['margin'], HOME + carry * (full - HOME), places=2)

    def test_no_prior_for_the_first_stored_season(self):
        self.assertIsNone(hm.season_prior('NBA', self.games, 2024, EXACT))
        with self.assertRaises(ValueError):
            hm.Model('NBA', self.games, datetime(2023, 10, 1, tzinfo=timezone.utc).timestamp(), 2024, EXACT)


class WalkForwardTests(unittest.TestCase):
    def test_no_game_at_or_after_the_cutoff_is_used(self):
        games = hm.prepare(league(noise=6.0))
        cutoff = games[20].t  # a game tips off exactly at the cutoff
        model = hm.Model('NBA', games, cutoff, 2025, hm.PARAMS['NBA'])
        self.assertEqual(len(model.used), 20)
        self.assertLess(model.through, cutoff)
        # Rewriting every score from the cutoff on changes nothing the model knows.
        changed = hm.prepare([dict(r, homeScore=0, awayScore=300) if i >= 20 else r
                              for i, r in enumerate(league(noise=6.0))])
        again = hm.Model('NBA', changed, cutoff, 2025, hm.PARAMS['NBA'])
        self.assertEqual(model.fits['margin'].beta, again.fits['margin'].beta)
        self.assertEqual(model.fits['total'].beta, again.fits['total'].beta)

    def test_a_backtest_forecast_never_sees_its_own_or_later_games(self):
        records = league(rounds=3, noise=6.0)
        full = hm.backtest('NBA', 2025, records=records)
        for stop in (15, 31, 50):
            truncated = hm.backtest('NBA', 2025, records=records[:stop])
            self.assertEqual(truncated, full[:stop])
        # Changing a game's own result does not change its forecast.
        changed = [dict(r, homeScore=r['homeScore'] + 40) if i == 31 else r for i, r in enumerate(records)]
        self.assertEqual(hm.backtest('NBA', 2025, records=changed)[31]['margin'], full[31]['margin'])

    def test_refit_points_are_mornings_at_or_before_the_tip(self):
        tip = datetime(2025, 1, 15, 0, 30, tzinfo=timezone.utc).timestamp()
        point = hm.refit_point(tip, 2025, 1)
        self.assertEqual(datetime.fromtimestamp(point, timezone.utc), datetime(2025, 1, 14, 8, tzinfo=timezone.utc))
        weekly = hm.refit_point(tip, 2025, 7)
        self.assertLessEqual(weekly, tip)
        self.assertGreater(weekly, tip - 7 * 86400)
        self.assertEqual(hm.refit_point(point, 2025, 1), point)

    def test_small_schools_share_one_rating(self):
        records = league(rounds=3)
        records.append(game(900, 2025, datetime(2024, 12, 20, tzinfo=timezone.utc), 'A', 'DIV2', 130, 60))
        games = hm.prepare(records)
        model = hm.Model('CBB', games, games[-1].t + 1, 2025, hm.PARAMS['CBB'])
        self.assertEqual(model.key('DIV2'), hm.SMALL)
        self.assertEqual(model.key('A'), 'A')
        self.assertIn(hm.SMALL, model.fits['margin'].index)
        self.assertNotIn('DIV2', model.fits['margin'].index)


def row(ours, close, opening, actual, market='total', sd=10.0):
    cap = market.capitalize()
    other = 'margin' if market == 'total' else 'total'
    return {market: ours, f'close{cap}': close, f'open{cap}': opening, f'actual{cap}': actual,
            other: None, f'close{other.capitalize()}': None, f'open{other.capitalize()}': None,
            f'actual{other.capitalize()}': 0, f'sd{cap}': sd, f'sd{other.capitalize()}': None}


class GradingTests(unittest.TestCase):
    def test_buckets(self):
        edges = hm.BUCKETS['NBA']
        self.assertEqual([hm.bucket_of(g, edges) for g in (0.2, 1.0, 1.9, 2.0, 3.99, 4.0, 11)],
                         ['0-1', '1-2', '1-2', '2-4', '2-4', '4+', '4+'])
        self.assertEqual(hm.bucket_of(2.5, hm.BUCKETS['CBB']), '1.5-3')

    def test_our_side_is_taken_at_the_open_and_graded_at_the_close(self):
        rows = [row(224.0, 223.0, 220.0, 226),   # over (4 above the open): wins at the close and the open
                row(224.0, 225.0, 220.0, 224),   # over: loses at the close 225, wins at the open 220
                row(218.5, 219.0, 220.0, 219),   # under (1.5 below): pushes at the close
                row(220.5, 222.0, 220.0, 215),   # over by 0.5: loses both
                row(220.0, 222.0, 220.0, 230)]   # no gap to the open: no side
        grade = hm.by_opening_gap(rows, 'total', hm.BUCKETS['NBA'], hm.LEAN['NBA'])
        self.assertEqual(grade['4+']['atClose'], {**grade['4+']['atClose'], 'won': 1, 'lost': 1, 'push': 0})
        self.assertEqual((grade['4+']['atOpen']['won'], grade['4+']['atOpen']['lost']), (2, 0))
        self.assertEqual(grade['1-2']['atClose']['push'], 1)
        self.assertEqual(grade['0-1']['atClose']['lost'], 1)
        self.assertEqual(grade['lean 2+']['n'], 2)
        self.assertEqual(grade['all']['n'], 4)
        self.assertNotIn('2-4', grade)
        # The market moved 3 and 5 toward our over, 1 toward our under and 2 toward our small over:
        # the value a bet at the opening number had.
        self.assertEqual(grade['4+']['lineMove'], {'toward': 1.0, 'away': 0.0, 'mean': 4.0})
        self.assertEqual(grade['1-2']['lineMove'], {'toward': 1.0, 'away': 0.0, 'mean': 1.0})
        self.assertEqual(grade['0-1']['lineMove'], {'toward': 1.0, 'away': 0.0, 'mean': 2.0})

    def test_sides_use_the_home_margin(self):
        # Close home -3.5 is a margin of 3.5; our 6 likes the home side; home won by 5: a cover.
        rows = [row(6.0, 3.5, 2.5, 5, market='margin'), row(1.0, 3.5, 2.5, 5, market='margin')]
        grade = hm.by_opening_gap(rows, 'margin', hm.BUCKETS['NBA'], hm.LEAN['NBA'])
        self.assertEqual(grade['2-4']['atClose']['won'], 1)
        self.assertEqual(grade['1-2']['atClose']['lost'], 1)

    def test_calibration_shrink(self):
        rng = random.Random(9)
        # The favoured side wins 55% whatever the raw chance says: k lands well below 1.
        samples = [(0.5 + 0.4 * rng.random(), rng.random() < 0.55) for _ in range(4000)]
        k = hm.fit_k(samples)
        self.assertTrue(0.05 < k < 0.6)
        self.assertGreater(hm.loglik(samples, k), hm.loglik(samples, 0.0))
        self.assertEqual(hm.fit_k([(0.8, False)] * 50 + [(0.8, True)] * 50), 0.0)

    def test_wilson_interval_brackets_the_rate(self):
        low, high = hm.wilson(55, 100)
        self.assertTrue(low < 0.55 < high)
        self.assertIsNone(hm.wilson(0, 0))

    def test_grade_on_a_backtest(self):
        records = league(rounds=6, noise=8.0)
        for r in records:
            r['close'] = {'total': round(r['homeScore'] + r['awayScore']) + 0.5, 'spread': -3.5, 'books': 1}
            r['open'] = {'total': 220.5, 'spread': -2.5, 'books': 1}
        rows = hm.backtest('NBA', 2025, records=records)
        grade = hm.grade(rows, 'NBA')
        forecast = [r for r in rows if r['total'] is not None]
        self.assertEqual(grade['games'], len(records))
        self.assertEqual(rows[0]['total'], None)  # the first stored season's first day has nothing to rate from
        self.assertEqual(grade['total']['priced'], len(forecast))
        self.assertGreaterEqual(len(forecast), len(records) - 2)
        self.assertLess(grade['total']['closeMiss'], 1.0)  # this close knew the result
        self.assertAlmostEqual(grade['total']['closerThanClose'],
                               sum(r['closerTotal'] for r in forecast) / len(forecast), places=4)
        for r in rows:
            self.assertEqual(r['closeMargin'], 3.5)
            self.assertEqual(r['openMargin'], 2.5)


class RecordTests(unittest.TestCase):
    def test_shipped_parameters_are_the_recorded_tuning(self):
        """Changing PARAMS without a new tuning record (and its look at the holdout) fails here."""
        for league in ('NBA', 'CBB'):
            path = hm.OUT / f'hoops-{league.lower()}.json'
            if not path.exists():
                continue
            record = hm.json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(hm.params_hash(hm.PARAMS[league]), record['paramsHash'], league)
            self.assertEqual(record['chosen'], hm.PARAMS[league])
            self.assertGreaterEqual(len(record['looks']), 1)


if __name__ == '__main__':
    unittest.main()
