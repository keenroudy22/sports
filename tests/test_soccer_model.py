import json
import math
import random
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import soccer_model as sm

EXACT = {'halfLife': 100000, 'ridge': 1e-6, 'rho': 0.0, 'seasonCarry': 1.0, 'newcomerPool': 3, 'shotsBlend': 1.0}
ATTACK = {'A': 0.4, 'B': 0.2, 'C': 0.0, 'D': -0.1, 'E': -0.2, 'F': -0.3, 'G': -0.25, 'H': -0.35}
DEFENCE = {'A': 0.3, 'B': 0.1, 'C': 0.0, 'D': 0.0, 'E': -0.1, 'F': -0.3, 'G': -0.2, 'H': -0.25}
SIX = ('A', 'B', 'C', 'D', 'E', 'F')
MU, HOME = 0.1, 0.25


def rates(home, away):
    return (math.exp(MU + HOME + ATTACK[home] - DEFENCE[away]), math.exp(MU + ATTACK[away] - DEFENCE[home]))


def sample_poisson(rng, rate):
    k, p, threshold = 0, 1.0, math.exp(-rate)
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def league(seasons=('2020-21', '2021-22'), teams=SIX, goals=None, start=datetime(2020, 8, 15, 15, tzinfo=timezone.utc)):
    """A double round robin per season, one round every Saturday, with goals from `goals(home, away, rng)`."""
    rng = random.Random(3)
    goals = goals or (lambda h, a, rng: tuple(sample_poisson(rng, r) for r in rates(h, a)))
    records, moment = [], start
    for season in seasons:
        n = len(teams)
        order = list(teams)
        rounds = []
        for r in range(n - 1):
            rounds.append([(order[i], order[n - 1 - i]) for i in range(n // 2)])
            order = [order[0]] + [order[-1]] + order[1:-1]
        rounds += [[(a, h) for h, a in pairs] for pairs in rounds]
        for pairs in rounds:
            for home, away in pairs:
                hg, ag = goals(home, away, rng)
                records.append({'id': f'EPL-{moment.date()}-{home}-{away}', 'league': 'EPL', 'season': season,
                                'date': moment.date().isoformat(), 'kickoff': moment.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                'home': home, 'away': away, 'homeGoals': hg, 'awayGoals': ag,
                                'close': {'home': 2.0, 'draw': 3.5, 'away': 4.0, 'over25': 1.9, 'under25': 1.9,
                                          'ahLine': -0.25, 'ahHome': 1.95, 'ahAway': 1.95}})
            moment += timedelta(days=7)
        moment += timedelta(days=70)
    return records


def centered(values):
    mean = sum(values.values()) / len(values)
    return {k: v - mean for k, v in values.items()}


class GridTests(unittest.TestCase):
    def test_grid_sums_to_one(self):
        for home_rate, away_rate, rho in ((1.4, 1.1, 0.0), (1.4, 1.1, -0.12), (0.3, 3.2, 0.1), (4.5, 0.2, -0.05)):
            grid = sm.score_grid(home_rate, away_rate, rho)
            self.assertEqual((len(grid), len(grid[0])), (11, 11))
            self.assertAlmostEqual(sum(map(sum, grid)), 1.0, places=12)
            self.assertTrue(all(p >= 0 for row in grid for p in row))
            result = sm.result_chances(grid)
            self.assertAlmostEqual(sum(result.values()), 1.0, places=12)
            total = sm.total_chances(grid)
            self.assertAlmostEqual(total['over'] + total['under'], 1.0, places=12)

    def test_independent_poisson_without_rho(self):
        grid = sm.score_grid(1.5, 1.0)
        self.assertAlmostEqual(grid[0][0], math.exp(-2.5), places=6)
        self.assertAlmostEqual(grid[2][1], math.exp(-1.5) * 1.5 ** 2 / 2 * math.exp(-1.0), places=6)
        # Goals are Poisson: the chance of 2 or fewer in all is the Poisson(2.5) sum.
        under = sum(math.exp(-2.5) * 2.5 ** k / math.factorial(k) for k in range(3))
        self.assertAlmostEqual(sm.total_chances(grid)['under'], under, places=6)

    def test_negative_rho_adds_draws(self):
        plain, dc = sm.score_grid(1.3, 1.1, 0.0), sm.score_grid(1.3, 1.1, -0.1)
        self.assertGreater(dc[0][0], plain[0][0])
        self.assertGreater(dc[1][1], plain[1][1])
        self.assertLess(dc[1][0], plain[1][0])
        self.assertGreater(sm.result_chances(dc)['draw'], sm.result_chances(plain)['draw'])


class HandicapTests(unittest.TestCase):
    def test_whole_and_half_lines(self):
        self.assertEqual(sm.settle(1, -0.5), (1.0, 0.0))
        self.assertEqual(sm.settle(0, -0.5), (0.0, 1.0))
        self.assertEqual(sm.settle(1, -1.0), (0.0, 0.0), 'win by exactly one at -1 is a push')
        self.assertEqual(sm.settle(0, 0.0), (0.0, 0.0), 'a draw at level is a push')
        self.assertEqual(sm.settle(-1, 1.5), (1.0, 0.0))

    def test_quarter_lines_split_the_stake(self):
        self.assertEqual(sm.settle(0, -0.25), (0.0, 0.5), '-0.25 on a draw: half pushed, half lost')
        self.assertEqual(sm.settle(0, 0.25), (0.5, 0.0), '+0.25 on a draw: half won, half pushed')
        self.assertEqual(sm.settle(1, -0.75), (0.5, 0.0), '-0.75 winning by one: half won, half pushed')
        self.assertEqual(sm.settle(2, -0.75), (1.0, 0.0))
        self.assertEqual(sm.settle(1, -1.25), (0.0, 0.5), '-1.25 winning by one: half pushed, half lost')
        self.assertEqual(sm.settle(-1, 0.75), (0.0, 0.5), '+0.75 losing by one: half pushed, half lost')
        self.assertEqual(sm.settle(-1, 1.25), (0.5, 0.0))
        self.assertAlmostEqual(sm.profit(1, -0.75, 1.9), 0.45)
        self.assertAlmostEqual(sm.profit(0, -0.25, 1.9), -0.5)
        self.assertAlmostEqual(sm.profit(0, 0.25, 2.1), 0.55)
        with self.assertRaises(ValueError):
            sm.settle(0, -0.3)

    def test_handicap_chances(self):
        grid = sm.score_grid(1.6, 1.0, -0.05)
        result = sm.result_chances(grid)
        level = sm.handicap_chances(grid, 0.0)
        self.assertAlmostEqual(level['chance'], result['home'] / (result['home'] + result['away']), places=12,
                               msg='level ball is draw-no-bet')
        for line in (-1.75, -0.75, -0.25, 0.25, 0.5, 1.0):
            home, away = sm.handicap_chances(grid, line, 'home'), sm.handicap_chances(grid, -line, 'away')
            self.assertAlmostEqual(home['chance'] + away['chance'], 1.0, places=12)
            self.assertAlmostEqual(home['won'], away['lost'], places=12)
        # A quarter line sits between the lines either side of it.
        self.assertLess(sm.handicap_chances(grid, -0.75)['chance'], sm.handicap_chances(grid, -0.5)['chance'])
        self.assertGreater(sm.handicap_chances(grid, -0.75)['chance'], sm.handicap_chances(grid, -1.0)['chance'])


class PriceTests(unittest.TestCase):
    def test_devig(self):
        fair = sm.devig([2.0, 3.5, 4.0])
        self.assertAlmostEqual(sum(fair), 1.0, places=12)
        self.assertAlmostEqual(fair[0] / fair[2], 2.0, places=12, msg='proportional: ratios are kept')
        self.assertEqual(sm.devig([2.0, 2.0]), [0.5, 0.5])

    def test_draw_no_bet_replication(self):
        home, draw = 2.2, 3.4
        dnb = sm.dnb_odds(home, draw)
        on_draw, on_home = 1 / draw, 1 - 1 / draw
        self.assertAlmostEqual(on_draw * draw, 1.0, msg='a draw returns the stake')
        self.assertAlmostEqual(on_home * home, dnb, msg='a home win pays the replicated price')


class FitTests(unittest.TestCase):
    def test_recovers_known_strengths_exactly(self):
        # Each match "scores" its expected goals: the likelihood's maximum is then the truth itself.
        records = league(goals=lambda h, a, rng: rates(h, a))
        cutoff = sm.when(records[-1]) + timedelta(days=1)
        fitted = sm.fit(records, cutoff, '2021-22', EXACT)
        self.assertAlmostEqual(fitted.home, HOME, places=4)
        for truth, found in ((ATTACK, fitted.attack), (DEFENCE, fitted.defence)):
            for team, value in centered({t: truth[t] for t in SIX}).items():
                self.assertAlmostEqual(centered(found)[team], value, places=4)
        for home, away in (('A', 'F'), ('E', 'B')):
            for got, want in zip(fitted.rates(home, away), rates(home, away)):
                self.assertAlmostEqual(got, want, places=4)

    def test_recovers_strengths_from_sampled_scores(self):
        records = league(seasons=[f'{y}-{(y + 1) % 100:02d}' for y in range(1960, 2000)])
        cutoff = sm.when(records[-1]) + timedelta(days=1)
        fitted = sm.fit(records, cutoff, '1999-00', {**EXACT, 'ridge': 0.01})
        self.assertAlmostEqual(fitted.home, HOME, delta=0.05)
        for truth, found in ((ATTACK, fitted.attack), (DEFENCE, fitted.defence)):
            for team, value in centered({t: truth[t] for t in SIX}).items():
                self.assertAlmostEqual(centered(found)[team], value, delta=0.12, msg=team)

    def test_ridge_pulls_toward_zero_and_toward_a_center(self):
        records = league(goals=lambda h, a, rng: rates(h, a))
        cutoff = sm.when(records[-1]) + timedelta(days=1)
        loose = sm.fit(records, cutoff, '2021-22', EXACT)
        tight = sm.fit(records, cutoff, '2021-22', {**EXACT, 'ridge': 50.0})
        self.assertLess(abs(tight.attack['A']), abs(loose.attack['A']))
        centred = sm.fit(records, cutoff, '2021-22', {**EXACT, 'ridge': 1e6}, centers={'A': (-0.5, 0.2)})
        self.assertAlmostEqual(centred.attack['A'], -0.5, places=3)
        self.assertEqual(centred.rating('Z'), (0.0, 0.0), 'an unseen club is league average')
        self.assertEqual(sm.fit([], cutoff, '2021-22', EXACT, centers={'Z': (-0.3, -0.2)}).rating('Z'), (-0.3, -0.2))

    def test_time_decay_follows_the_recent_form(self):
        # A scores at its old rate last season and 0.8 lower (in log terms) this season.
        records = league(goals=lambda h, a, rng: rates(h, a))
        for record in records:
            if record['season'] == '2021-22':
                if record['home'] == 'A':
                    record['homeGoals'] *= math.exp(-0.8)
                if record['away'] == 'A':
                    record['awayGoals'] *= math.exp(-0.8)
        cutoff = sm.when(records[-1]) + timedelta(days=1)
        slow = sm.fit(records, cutoff, '2021-22', {**EXACT, 'halfLife': 100000})
        fast = sm.fit(records, cutoff, '2021-22', {**EXACT, 'halfLife': 30})
        carried = sm.fit(records, cutoff, '2021-22', {**EXACT, 'halfLife': 100000, 'seasonCarry': 0.01})
        self.assertLess(centered(fast.attack)['A'], centered(slow.attack)['A'] - 0.2)
        self.assertLess(centered(carried.attack)['A'], centered(slow.attack)['A'] - 0.2, 'seasonCarry discounts last season')

    def test_rho_is_estimated(self):
        rng = random.Random(11)
        grid = sm.score_grid(1.4, 1.1, -0.12)
        cells = [(i, j, p) for i, row in enumerate(grid) for j, p in enumerate(row)]
        rows = []
        for _ in range(30000):
            u, acc = rng.random(), 0.0
            for i, j, p in cells:
                acc += p
                if u <= acc:
                    break
            rows.append(('H', 'A', i, j, 1.0, None))
        rho = sm.fit_rho(rows, lambda h, a: (1.4, 1.1))
        self.assertAlmostEqual(rho, -0.12, delta=0.04)

    def test_shot_values_and_targets(self):
        # Goals are exactly 0.3 a shot on target and 0.05 a shot off it.
        rows = [('H', 'A', 4, 1, 1.0, {'home': 30, 'away': 20, 'homeTarget': 10, 'awayTarget': 0})] * 60 + \
               [('H', 'A', 2, 3, 1.0, {'home': 15, 'away': 10, 'homeTarget': 5, 'awayTarget': 10})] * 60
        on, off = sm.shot_values(rows)
        self.assertAlmostEqual(on, 0.3, places=9)
        self.assertAlmostEqual(off, 0.05, places=9)
        lucky = rows + [('H', 'A', 5, 0, 1.0, {'home': 10, 'away': 10, 'homeTarget': 5, 'awayTarget': 5})]
        on, off = sm.shot_values(lucky)
        blended = sm.targets(lucky, 0.5)[-1]
        self.assertEqual(blended[:2], ('H', 'A'))
        self.assertAlmostEqual(blended[2], 0.5 * 5 + 0.5 * (on * 5 + off * 5))
        self.assertAlmostEqual(blended[3], 0.5 * 0 + 0.5 * (on * 5 + off * 5))
        self.assertEqual(sm.targets(lucky, 1.0)[-1][2:4], (5, 0), 'blend 1 is goals alone')
        self.assertIsNone(sm.shot_values(rows[:50]), 'too few matches with shots')


class WalkForwardTests(unittest.TestCase):
    PARAMS = {'halfLife': 180, 'ridge': 3.0, 'rho': 'fit', 'seasonCarry': 1.0, 'newcomerPool': 2, 'shotsBlend': 1.0}

    def test_refit_points(self):
        friday = datetime(2026, 9, 25, 19, tzinfo=timezone.utc)
        self.assertEqual(sm.refit_point(friday), datetime(2026, 9, 25, 6, tzinfo=timezone.utc))
        self.assertEqual(sm.refit_point(datetime(2026, 9, 28, 20, tzinfo=timezone.utc)), datetime(2026, 9, 25, 6, tzinfo=timezone.utc))
        self.assertEqual(sm.refit_point(datetime(2026, 9, 25, 5, tzinfo=timezone.utc)), datetime(2026, 9, 22, 6, tzinfo=timezone.utc))
        self.assertEqual(sm.refit_point(datetime(2026, 9, 30, 19, tzinfo=timezone.utc)), datetime(2026, 9, 29, 6, tzinfo=timezone.utc))

    def test_every_forecast_uses_only_earlier_matches(self):
        records = league()
        rows = sm.backtest('EPL', '2021-22', self.PARAMS, records)
        self.assertEqual(len(rows), 30)
        for row in rows:
            self.assertLessEqual(row['refit'], row['kickoff'])
            self.assertLess(row['through'], row['refit'])

    def test_later_results_do_not_change_earlier_forecasts(self):
        records = league()
        before = sm.backtest('EPL', '2021-22', self.PARAMS, records)
        split = datetime.fromisoformat(before[15]['kickoff'])
        changed = [dict(r, homeGoals=9, awayGoals=0) if sm.when(r) >= split else r for r in records]
        after = sm.backtest('EPL', '2021-22', self.PARAMS, changed)
        for old, new in zip(before, after):
            if datetime.fromisoformat(old['refit']) <= split:
                self.assertEqual(old['model'], new['model'], old['id'])
        self.assertNotEqual(before[-1]['model'], after[-1]['model'], 'the later forecasts do see them')

    def test_promoted_clubs_start_from_the_relegated_average(self):
        records = league(seasons=('2020-21',), teams=('A', 'B', 'C', 'D', 'E', 'F'))
        records += league(seasons=('2021-22',), teams=('A', 'B', 'C', 'D', 'G', 'H'),
                          start=datetime(2021, 8, 14, 15, tzinfo=timezone.utc))
        opening = sm.refit_point(sm.when(next(r for r in records if r['season'] == '2021-22')))
        centers, info = sm.newcomer_centers('EPL', records, '2021-22', self.PARAMS, opening)
        self.assertEqual(sorted(centers), ['G', 'H'])
        self.assertEqual(info['from'], ['E', 'F'], 'the clubs that went down')
        base = sm.fit([r for r in records if sm.when(r) < opening], opening, '2021-22', {**self.PARAMS, 'rho': 0.0})
        self.assertAlmostEqual(centers['G'][0], (base.attack['E'] + base.attack['F']) / 2)
        rows = sm.backtest('EPL', '2021-22', self.PARAMS, records)
        first = next(r for r in rows if 'G' in (r['home'], r['away']))
        self.assertTrue(first['model']['sparse'])


class EvaluationTests(unittest.TestCase):
    def row(self, model, goals, close, close_avg=None, open_=None):
        return {'id': f'x{goals}', 'homeGoals': goals[0], 'awayGoals': goals[1], 'model': model, 'close': close,
                **({'closeAvg': close_avg} if close_avg else {}), **({'open': open_} if open_ else {})}

    def test_leans_bet_our_side_at_the_price(self):
        model = {'home': 0.5, 'draw': 0.25, 'away': 0.25, 'over25': 0.6, 'under25': 0.4, 'dnbHome': 2 / 3,
                 'handicap': {-0.25: {'home': 0.6, 'away': 0.4}}}
        close = {'home': 2.5, 'draw': 3.5, 'away': 3.0, 'over25': 2.0, 'under25': 1.8, 'ahLine': -0.25, 'ahHome': 1.9, 'ahAway': 2.0}
        rows = [self.row(model, (2, 0), close, dict(close, home=2.4)), self.row(model, (0, 0), close)]
        result = sm.leans(rows, '1x2', 'close', 4)
        self.assertEqual(result['bets'], 2)
        self.assertEqual(result['primary']['won'], 1)
        self.assertAlmostEqual(result['primary']['units'], 0.5)
        self.assertEqual(result['average']['n'], 1, 'only the first match has an average price')
        self.assertAlmostEqual(result['average']['units'], 1.4)
        handicap = sm.leans(rows, 'ah', 'close', 2)
        self.assertEqual((handicap['primary']['won'], handicap['primary']['lost']), (1, 1))
        self.assertAlmostEqual(handicap['primary']['units'], 0.9 - 0.5, msg='the draw loses half at -0.25')
        self.assertEqual(sm.leans(rows, 'total', 'open', 2)['bets'], 0, 'no opening prices, no bets')
        dnb = sm.leans(rows, 'dnb', 'close', 2)
        self.assertEqual((dnb['primary']['won'], dnb['primary']['pushed']), (1, 1))
        self.assertAlmostEqual(dnb['primary']['units'], sm.dnb_odds(2.5, 3.5) - 1, places=2)

    def test_no_lean_below_the_threshold(self):
        model = {'home': 0.40, 'draw': 0.3, 'away': 0.30, 'over25': 0.5, 'under25': 0.5, 'dnbHome': 4 / 7, 'handicap': {}}
        close = {'home': 2.5, 'draw': 3.4, 'away': 3.3}
        self.assertEqual(sm.leans([self.row(model, (1, 0), close)], '1x2', 'close', 6)['bets'], 0)

    def test_calibration_k(self):
        # The market says 50%, we say 70%, and 7 of 10 go over: our number is right, k = 1.
        model = {'home': 0.4, 'draw': 0.3, 'away': 0.3, 'over25': 0.7, 'under25': 0.3, 'dnbHome': 0.5, 'handicap': {}}
        close = {'home': 2.5, 'draw': 3.4, 'away': 3.3, 'over25': 1.9, 'under25': 1.9}
        rows = [self.row(model, (2, 1), close)] * 7 + [self.row(model, (1, 0), close)] * 3
        self.assertEqual(sm.calibrate(rows, 'total')['k'], 1.0)
        # Half go over: the market was right, k = 0.
        rows = [self.row(model, (2, 1), close)] * 5 + [self.row(model, (1, 0), close)] * 5
        result = sm.calibrate(rows, 'total', at=(1.0,))
        self.assertEqual(result['k'], 0.0)
        self.assertLess(result['gainAt']['1.0'], 0)

    def test_accuracy_compares_with_the_close(self):
        model = {'home': 0.5, 'draw': 0.25, 'away': 0.25, 'over25': 0.5, 'under25': 0.5, 'dnbHome': 2 / 3, 'handicap': {}}
        close = {'home': 2.0, 'draw': 4.0, 'away': 4.0}
        result = sm.accuracy([self.row(model, (1, 0), close)], '1x2', calibration=0.5)
        self.assertAlmostEqual(result['logLoss']['ours'], round(-math.log(0.5), 5))
        self.assertAlmostEqual(result['logLoss']['close'], round(-math.log(0.5), 5))
        self.assertAlmostEqual(result['brier']['ours'], 0.25 + 0.0625 * 2)


class ProtocolTests(unittest.TestCase):
    def test_tune_then_one_holdout_look(self):
        records = league(seasons=('2019-20', '2020-21', '2021-22'))
        grid = {'halfLife': (90, 365), 'ridge': (1.0, 10.0), 'shotsBlend': (1.0,), 'rho': (0.0, 'fit'), 'seasonCarry': (1.0,)}
        seasons = {'tune': '2020-21', 'holdout': '2021-22'}
        result = sm.run_tune('EPL', log=lambda *_: None, records=records, seasons=seasons, grid=grid)
        self.assertEqual((result['tuneSeason'], result['holdoutSeason'], result['history']), ('2020-21', '2021-22', ['2019-20']))
        self.assertIn(result['chosen']['halfLife'], (90, 365))
        self.assertEqual(result['looks'], [])
        self.assertNotIn('holdout', result, 'tuning never reads the holdout season')
        self.assertTrue(all(t['params']['rho'] in (0.0, 'fit') for t in result['trials']))
        looked = sm.run_holdout('EPL', result, records=records)
        self.assertEqual(len(looked['looks']), 1)
        self.assertEqual(looked['holdout']['season'], '2021-22')
        self.assertEqual(looked['holdout']['evaluation']['matches'], 30)
        self.assertEqual(sorted(looked['verdict']), sorted(sm.MARKETS))
        for market, verdict in looked['verdict'].items():
            self.assertIn('publish', verdict)
            self.assertFalse(verdict['publish'], f'{market}: 30 matches is never a sample')
        json.dumps(looked)  # the record is plain JSON


class ParamsTests(unittest.TestCase):
    def test_params_match_the_tuning_files(self):
        for league in ('EPL', 'MLS'):
            path = sm.tuning_path(league)
            if not path.exists():
                continue
            chosen = json.loads(path.read_text(encoding='utf-8'))['chosen']
            self.assertEqual(sm.PARAMS[league], chosen, f'{league}: PARAMS must be the tuned parameters in {path.name}')


if __name__ == '__main__':
    unittest.main()
