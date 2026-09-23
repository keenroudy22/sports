import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fakegames
import model_v2

STRENGTH = {'A': 8, 'B': 3, 'C': 0, 'D': -3, 'E': -8, 'F': 0}
EXACT = {'margin': {'halfLife': 10000, 'ridge': 0.01, 'priorWeight': 1.0, 'eloWeight': 0.0},
         'total': {'halfLife': 10000, 'ridge': 0.01, 'priorWeight': 1.0, 'blend': 1.0},
         'sdMargin': 13.0, 'sdTotal': 13.0, 'pace': 65.0}


def after(games):
    return model_v2.features.when(games[-1]['kickoff']) + timedelta(days=1)


class SolverTests(unittest.TestCase):
    def test_gauss_seidel_matches_a_direct_solve(self):
        size, rows = 8, 40
        active = [[0, 1 + i % 3, 4 + (i * 5) % 4] for i in range(rows)]
        targets = [20 + 7 * math.sin(i * 1.7) for i in range(rows)]
        weights = [0.5 + (i % 4) / 4 for i in range(rows)]
        penalty = [0.0] + [2.0] * (size - 1)
        iterative = model_v2.ridge(targets, weights, active, size, penalty, tolerance=1e-10)
        matrix = [[penalty[i] if i == j else 0.0 for j in range(size)] for i in range(size)]
        vector = [0.0] * size
        for columns, y, w in zip(active, targets, weights):
            for i in columns:
                vector[i] += w * y
                for j in columns:
                    matrix[i][j] += w
        direct = model_v2.solve(matrix, vector)
        self.assertLess(max(abs(a - b) for a, b in zip(iterative, direct)), 1e-6)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.games = fakegames.season(STRENGTH, weeks=10, home_field=3)
        self.model = model_v2.Model('NFL', self.games, after(self.games), 2025, EXACT)

    def test_ratings_recover_known_strengths_and_home_field(self):
        forecast = self.model.predict('A', 'E')
        self.assertAlmostEqual(forecast['margin'], 8 - (-8) + 3, delta=0.6)
        self.assertAlmostEqual(forecast['total'], 40, delta=0.6)
        self.assertAlmostEqual(self.model.predict('A', 'E', neutral=True)['margin'], 16, delta=0.6)
        offense = {team: self.model.margin.team(team)['off'] for team in STRENGTH}
        self.assertEqual(sorted(offense, key=offense.get, reverse=True)[:2], ['A', 'B'])

    def test_probability_and_ranges_follow_the_margin(self):
        even = self.model.predict('C', 'F', neutral=True)
        self.assertAlmostEqual(even['homeWinProb'], 0.5, delta=0.03)
        self.assertGreater(self.model.predict('A', 'E')['homeWinProb'], 0.9)
        self.assertEqual((even['sdMargin'], even['sdTotal']), (13.0, 13.0))

    def test_a_cutoff_uses_only_earlier_games(self):
        cutoff = model_v2.features.when(self.games[12]['kickoff'])
        model = model_v2.Model('NFL', self.games, cutoff, 2025, EXACT)
        self.assertEqual(model.games, 12)
        self.assertEqual(model.through, self.games[11]['kickoff'])
        changed = [dict(g) for g in self.games]
        changed[20] = {**changed[20], 'hash': 'different'}
        self.assertEqual(model_v2.Model('NFL', changed, cutoff, 2025, EXACT).inputs, model.inputs,
                         'a later game cannot change an earlier forecast')

    def test_the_elo_blend_is_off_unless_tuned_on(self):
        self.assertIsNone(self.model.elo)
        blended = model_v2.Model('NFL', self.games, after(self.games), 2025,
                                 {**EXACT, 'margin': {**EXACT['margin'], 'eloWeight': 0.5}})
        self.assertIsNotNone(blended.elo)
        self.assertNotAlmostEqual(blended.predict('A', 'E')['margin'], self.model.predict('A', 'E')['margin'], places=2)


class SeasonTests(unittest.TestCase):
    def test_offseason_days_skip_the_summer(self):
        last = fakegames.season(STRENGTH, weeks=2, year=2024, start=datetime(2024, 12, 29, 18, tzinfo=timezone.utc))
        this = fakegames.season(STRENGTH, weeks=2, year=2025, first_event=100)
        gaps = model_v2.offseason_days(last + this, 2025, datetime(2025, 9, 20, tzinfo=timezone.utc))
        expected = (model_v2.features.when(this[0]['kickoff']) - model_v2.features.when(last[-1]['kickoff'])).total_seconds() / 86400
        self.assertAlmostEqual(gaps[2024], expected, places=3)

    def test_last_season_carries_over_through_prior_weight_not_the_calendar(self):
        last = fakegames.season(STRENGTH, weeks=10, year=2024, start=datetime(2024, 9, 8, 17, tzinfo=timezone.utc))
        params = {**EXACT, 'margin': {'halfLife': 30, 'ridge': 1.0, 'priorWeight': 1.0, 'eloWeight': 0.0}}
        opening = datetime(2025, 9, 1, tzinfo=timezone.utc)
        model = model_v2.Model('NFL', last, opening, 2025, params)
        # Seven months without games must not erase last season's ratings.
        self.assertGreater(model.predict('A', 'E', neutral=True)['margin'], 12)

    def test_college_fcs_opponents_share_a_group_rating(self):
        fbs = fakegames.season({t: 0 for t in 'ABCDEFGH'}, weeks=8, league='CFB')
        fcs = [fakegames.game(900 + i, fakegames.START + timedelta(days=3 + 7 * i), team, f'FCS{i}', 45, 10,
                              league='CFB', week=i + 1) for i, team in enumerate('ABCD')]
        games = sorted(fbs + fcs, key=lambda g: g['kickoff'])
        model = model_v2.Model('CFB', games, after(games), 2025, {**EXACT, 'margin': {**EXACT['margin'], 'ridge': 2.0}})
        self.assertTrue(model.fcs('FCS0') and model.fcs('Unseen') and not model.fcs('A'))
        self.assertGreater(model.predict('E', 'Unseen')['margin'], 20, 'an unseen opponent is treated as FCS')


class VersionTests(unittest.TestCase):
    def test_parameters_change_only_with_a_new_version(self):
        self.assertEqual(model_v2.RELEASED.get(model_v2.VERSION), model_v2.params_hash(),
                         'PARAMS changed: release a new VERSION and register its hash in RELEASED')


class ScoreTests(unittest.TestCase):
    def test_records_against_the_close_and_average_misses(self):
        def row(model_margin, close_margin, margin, model_total=45, close_total=44, total=50):
            forecast = {'margin': model_margin, 'total': model_total, 'sdMargin': 13.0, 'sdTotal': 13.0}
            return {'forecast': forecast, 'closeMargin': close_margin, 'closeTotal': close_total,
                    'margin': margin, 'total': total}
        result = model_v2.score([row(5, 3, 10), row(1, 3, 10), row(5, 3, 3), row(2, 3, -4, 40, 44, 41)])
        self.assertEqual(result['sideVsClose'], [2, 1], 'a push on the close is not graded')
        self.assertEqual(result['totalVsClose'], [4, 0])
        self.assertEqual((result['marginMiss'], result['closeMarginMiss']), (5.5, 5.25))

    def test_week_start_is_the_tuesday_morning_before(self):
        sunday = datetime(2025, 9, 7, 17, tzinfo=timezone.utc)
        self.assertEqual(model_v2.week_start(sunday), datetime(2025, 9, 2, 8, tzinfo=timezone.utc))
        self.assertEqual(model_v2.week_start(datetime(2025, 9, 9, 9, tzinfo=timezone.utc)),
                         datetime(2025, 9, 9, 8, tzinfo=timezone.utc))
        self.assertEqual(model_v2.week_start(datetime(2025, 9, 9, 7, tzinfo=timezone.utc)),
                         datetime(2025, 9, 2, 8, tzinfo=timezone.utc))


if __name__ == '__main__':
    unittest.main()


class CloseSanityTests(unittest.TestCase):
    def test_backtest_reads_a_price_stored_as_a_line_as_no_close(self):
        games = fakegames.season(STRENGTH, weeks=8)
        games[-1]['market'] = {'close': {'spread': -115, 'total': -110}}
        games[-2]['market'] = {'close': {'spread': -3.5, 'total': 44.5}}
        rows = {r['eventId']: r for r in model_v2.backtest('NFL', 2025, EXACT, games)}
        self.assertIsNone(rows[games[-1]['eventId']]['closeMargin'])
        self.assertIsNone(rows[games[-1]['eventId']]['closeTotal'])
        self.assertEqual(rows[games[-2]['eventId']]['closeMargin'], 3.5)
        self.assertEqual(rows[games[-2]['eventId']]['closeTotal'], 44.5)


class CompareTests(unittest.TestCase):
    def rows(self, offset):
        games = fakegames.season(STRENGTH, weeks=8)
        for game in games:
            game['market'] = {'close': {'spread': -3.0, 'total': 40.0}}
        rows = model_v2.backtest('NFL', 2025, EXACT, games)
        for row in rows:
            row['forecast'] = dict(row['forecast'], margin=row['margin'] + offset, total=row['total'] + offset)
        return rows

    def test_identical_forecasts_are_noise_and_a_uniform_gain_wins(self):
        same = model_v2.compare(self.rows(2.0), self.rows(2.0), 'margin')
        self.assertEqual(same['verdict'], 'NOISE')
        self.assertEqual(same['meanDelta'], 0.0)
        better = model_v2.compare(self.rows(3.0), self.rows(1.0), 'margin')
        self.assertEqual(better['verdict'], 'WINS')
        self.assertAlmostEqual(better['meanDelta'], -2.0, places=3)
        self.assertTrue(model_v2.ships(better))
        worse = model_v2.compare(self.rows(1.0), self.rows(3.0), 'total')
        self.assertEqual(worse['verdict'], 'LOSES')
        self.assertFalse(model_v2.ships(worse))
        self.assertTrue(model_v2.ships({'verdict': 'NOISE', 'meanDelta': -0.12}))
        self.assertFalse(model_v2.ships({'verdict': 'NOISE', 'meanDelta': -0.05}))

    def test_rows_without_a_close_are_left_out(self):
        rows = self.rows(1.0)
        for row in rows:
            row['closeMargin'] = None
        self.assertEqual(model_v2.compare(rows, rows, 'margin')['verdict'], 'NO DATA')


class TuneKnobTests(unittest.TestCase):
    def test_tune_knob_sweeps_one_parameter_and_holds_the_rest(self):
        games = fakegames.season(STRENGTH, weeks=8)
        for game in games:
            game['market'] = {'close': {'spread': -3.0, 'total': 40.0}}
        loose = {**EXACT, 'margin': {**EXACT['margin'], 'ridge': 50.0}}
        result = model_v2.tune_knob('NFL', ('margin', 'ridge'), (50.0, 0.01), base=loose, tune_season=2025, holdout=2025,
                                    records=games, log=lambda *_: None)
        self.assertEqual(result['knob'], 'margin.ridge')
        self.assertEqual(result['chosen'], 0.01, 'the exact data rewards the lightest penalty')
        self.assertEqual(result['tuned']['margin']['ridge'], 0.01)
        self.assertEqual(result['tuned']['total'], EXACT['total'], 'the other target is untouched')
        self.assertEqual(result['holdout']['compare']['margin']['verdict'], 'WINS')
        self.assertTrue(result['holdout']['ships']['margin'])
        self.assertEqual(len(result['looks']), 1)
        self.assertEqual(model_v2.set_path({}, ('a', 'b'), 1), {'a': {'b': 1}})

    def test_predict_without_context_carries_no_adjustments(self):
        games = fakegames.season(STRENGTH, weeks=8)
        model = model_v2.Model('NFL', games, after(games), 2025, EXACT)
        self.assertEqual(model.predict('A', 'B')['adjustments'], {})
        self.assertEqual(model.context, {})
