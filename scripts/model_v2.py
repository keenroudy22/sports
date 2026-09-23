"""Model v2: team scores from the box-score store. Deterministic, stdlib only.

Each forecast refits two sets of team ratings from games that kicked off before
its cutoff, as recency-weighted ridge regressions of points scored on offense,
defense and home field:

  margin ratings  fit to points actually scored
  total ratings   fit to a blend of points and efficiency-implied points
                  (success rate, explosive plays, pace, turnovers, red-zone
                  drives), which carries less scoring luck

The margin can also blend in v1's Elo margin (the same code, replayed over the
stored games); tuning sets that weight per league and leaves it at zero where
it did not help. College FCS opponents share a group rating, so a lightly
observed FCS team is not treated as an average FBS team.

Games age in football days: the offseason is skipped and last season carries
over through priorWeight. Uncertainty comes from walk-forward residuals: every
forecast carries a margin and total standard deviation, 80% ranges and a home
win probability. No market, injury or weather input; the market is only the
yardstick.

Usage:
  python scripts/model_v2.py backtest NFL 2025      walk-forward results vs the close
  python scripts/model_v2.py tune CFB --out FILE    grid search on 2024, holdout 2025
"""
import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuity
import features
import starters
from refresh import Model as Elo

VERSION = 'v2.0'
# Chosen by `tune` on the full 2024 season (with 2023 as its prior) and checked
# once on the untouched 2025 season; see data/model/v2-tuning-*.json.
# Standard deviations are the 2024 walk-forward residuals.
PARAMS = {
    'NFL': {'margin': {'halfLife': 180, 'ridge': 10.0, 'priorWeight': 0.6, 'eloWeight': 0.5},
            'total': {'halfLife': 45, 'ridge': 3.0, 'priorWeight': 0.3, 'blend': 0.3},
            'sdMargin': 13.21, 'sdTotal': 12.79, 'pace': 65.0},
    'CFB': {'margin': {'halfLife': 90, 'ridge': 1.0, 'priorWeight': 0.3, 'eloWeight': 0.0},
            'total': {'halfLife': 90, 'ridge': 10.0, 'priorWeight': 0.6, 'blend': 1.0},
            'sdMargin': 16.31, 'sdTotal': 16.18, 'pace': 70.0},
}
# Parameters are fixed per version, so a snapshot names its version instead of
# copying them. Changing PARAMS without releasing a new VERSION fails the tests.
RELEASED = {'v2.0': 'bb945057fd1d'}
FBS_MIN_GAMES = 6  # a college team with this many stored games in a season is FBS
Z80 = 1.2815515655446004


# ------------------------------------------------------------------ inputs

def params_hash(params=None):
    return hashlib.sha256(json.dumps(params or PARAMS, sort_keys=True).encode()).hexdigest()[:12]


def efficiency(stats, pace):
    """[1, success rate, explosive rate, plays/pace, turnovers, red-zone drives] or None."""
    pbp = stats.get('pbp') or {}
    plays, tries = pbp.get('plays'), pbp.get('successPlays')
    if not plays or not tries or stats.get('turnovers') is None:
        return None
    return [1.0, pbp['successes'] / tries, pbp.get('explosive', 0) / plays, plays / pace,
            float(stats['turnovers']), float(pbp.get('rzDrives', 0))]


def solve(matrix, vector):
    """Gauss-Jordan elimination with partial pivoting for small dense systems."""
    n = len(vector)
    rows = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        lead = rows[col][col]
        if abs(lead) < 1e-12:
            raise ValueError('Singular system')
        rows[col] = [value / lead for value in rows[col]]
        for r in range(n):
            if r != col and rows[r][col]:
                factor = rows[r][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][n] for i in range(n)]


def implied_points(rows):
    """Least-squares map from efficiency to points, fit only on the rows given."""
    data = [(r['efficiency'], r['points']) for r in rows if r['efficiency']]
    if len(data) < 50:
        return None
    k = len(data[0][0])
    matrix = [[sum(x[i] * x[j] for x, _ in data) + (1e-6 if i == j else 0.0) for j in range(k)] for i in range(k)]
    return solve(matrix, [sum(x[i] * y for x, y in data) for i in range(k)])


def observations(records, pace):
    """One row per offense per game, oldest first."""
    rows = []
    for game in records:
        for side, other in (('home', 'away'), ('away', 'home')):
            team = game[side]['id']
            rows.append({'eventId': game['eventId'], 'kickoff': features.when(game['kickoff']), 'season': game['season'],
                         'team': team, 'opp': game[other]['id'], 'home': side == 'home' and not game['neutral'],
                         'points': game[side]['score'], 'efficiency': efficiency(game['teams'].get(team, {}), pace)})
    return rows


def offseason_days(records, season, cutoff):
    """Days without games between each earlier season and `season`, keyed by season.

    Measured from each season's last game to the next season's first game; the
    current season starts at its first scheduled game or the cutoff, whichever
    is earlier. Schedules are public in advance, so this uses no results.
    """
    first, last = {}, {}
    for game in records:
        moment = features.when(game['kickoff'])
        first[game['season']] = min(first.get(game['season'], moment), moment)
        last[game['season']] = max(last.get(game['season'], moment), moment)
    starts = dict(first)
    starts[season] = min(first.get(season, cutoff), cutoff)
    gaps, total = {}, 0.0
    for year in sorted((y for y in last if y < season), reverse=True):
        following = starts.get(year + 1)
        if following is None:
            break
        total += max((following - last[year]).total_seconds() / 86400, 0.0)
        gaps[year] = total
    return gaps


def fbs_teams(records):
    counts = defaultdict(int)
    for game in records:
        for side in ('home', 'away'):
            counts[(game['season'], game[side]['id'])] += 1
    return {team for (_, team), n in counts.items() if n >= FBS_MIN_GAMES}


# ------------------------------------------------------------------ fitting

def ridge(targets, weights, active, size, penalty, start=None, tolerance=1e-10, limit=None):
    """Weighted ridge regression over 0/1 indicator features.

    Solves (X'WX + P) b = X'Wy by conjugate gradients with a diagonal
    preconditioner, stopping on the true relative residual. Exact in principle
    within `size` steps and robust on sparse schedules such as college
    conferences, where coordinate methods creep. `start` warm-starts a refit;
    parameters no observation touches stay at zero.
    """
    used = [False] * size
    diagonal = list(penalty)
    for columns, w in zip(active, weights):
        for j in columns:
            used[j] = True
            diagonal[j] += w
    diagonal = [d if u and d > 0 else 1.0 for d, u in zip(diagonal, used)]

    def apply(vector):
        out = [p * v if u else v for p, v, u in zip(penalty, vector, used)]
        for columns, w in zip(active, weights):
            s = w * sum(vector[j] for j in columns)
            for j in columns:
                out[j] += s
        return out

    rhs = [0.0] * size
    for columns, y, w in zip(active, targets, weights):
        for j in columns:
            rhs[j] += w * y
    beta = [b if u else 0.0 for b, u in zip(start, used)] if start else [0.0] * size
    residual = [r - a for r, a in zip(rhs, apply(beta))]
    scale = math.sqrt(sum(r * r for r in rhs)) or 1.0
    z = [r / d for r, d in zip(residual, diagonal)]
    direction = list(z)
    rz = sum(r * q for r, q in zip(residual, z))
    for _ in range(limit or 4 * size):
        if math.sqrt(sum(r * r for r in residual)) <= tolerance * scale:
            break
        product = apply(direction)
        step = rz / sum(d * p for d, p in zip(direction, product))
        beta = [b + step * d for b, d in zip(beta, direction)]
        residual = [r - step * p for r, p in zip(residual, product)]
        z = [r / d for r, d in zip(residual, diagonal)]
        updated = sum(r * q for r, q in zip(residual, z))
        direction = [q + (updated / rz) * d for q, d in zip(z, direction)]
        rz = updated
    return beta


class Ratings:
    """Offense/defense ratings for one target. Parameters 0-3 are the base
    points, home field, FCS offense and FCS defense."""

    def __init__(self, beta, index, fcs):
        self.beta, self.index, self.fcs = beta, index, fcs

    def points(self, team, opponent, home):
        b, i = self.beta, self.index
        value = b[0] + (b[1] if home else 0.0)
        value += b[i['off', team]] if ('off', team) in i else 0.0
        value += b[i['def', opponent]] if ('def', opponent) in i else 0.0
        return value + (b[2] if self.fcs(team) else 0.0) + (b[3] if self.fcs(opponent) else 0.0)

    def team(self, team):
        return {side: round(self.beta[self.index[side, team]], 2) if (side, team) in self.index else 0.0
                for side in ('off', 'def')}

    def start_for(self, index):
        start = self.beta[:4] + [0.0] * len(index)
        for key, position in index.items():
            if key in self.index:
                start[position] = self.beta[self.index[key]]
        return start


def carry_for(row, params, roster, league_mean):
    """Last season's weight for one offense row: priorWeight, bent by how much of both teams is still here.

    carry = priorWeight * exp(continuity * (c - mean)), with c the average of the offense's returning
    usage and the defense's (a side that is not measured reads as the league mean). A team that kept
    its people keeps more of last season; a rebuilt one keeps less. continuity = 0 is v2.0 exactly.
    """
    gamma = params.get('continuity', 0.0)
    if not gamma or league_mean is None or row['season'] >= params.get('_season', row['season'] + 1):
        return params['priorWeight']
    sides = [(roster.get(row['team']) or {}).get('off'), (roster.get(row['opp']) or {}).get('def')]
    known = [league_mean if value is None else value for value in sides]
    return params['priorWeight'] * math.exp(gamma * (statistics.mean(known) - league_mean))


def fit(rows, cutoff, season, params, fcs, target, warm=None, offseason=None, roster=None):
    """Ratings from observation rows, all before the cutoff. target(row) is the response.

    Age is counted in football days: the offseason between a game's season and
    the cutoff's season is skipped, so carryover from last season is set by
    priorWeight rather than by how long the summer was. roster is the continuity
    table (scripts/continuity.py) when the parameters ask for it.
    """
    index = {}
    for row in rows:
        for key in (('off', row['team']), ('def', row['opp'])):
            if key not in index:
                index[key] = 4 + len(index)
    penalty = [0.0] * 4 + [params['ridge']] * len(index)
    targets, weights, active = [], [], []
    mean_c = continuity.league_mean(roster) if roster and params.get('continuity') else None
    bent = {**params, '_season': season}
    for row in rows:
        age = (cutoff - row['kickoff']).total_seconds() / 86400 - (offseason or {}).get(row['season'], 0.0)
        carry = carry_for(row, bent, roster or {}, mean_c) if row['season'] < season else params['priorWeight']
        weight = 0.5 ** (max(age, 0.0) / params['halfLife']) * carry ** (season - row['season'])
        columns = [0, index['off', row['team']], index['def', row['opp']]]
        if row['home']:
            columns.append(1)
        if fcs(row['team']):
            columns.append(2)
        if fcs(row['opp']):
            columns.append(3)
        targets.append(target(row))
        weights.append(weight)
        active.append(columns)
    start = warm.start_for(index) if warm else None
    return Ratings(ridge(targets, weights, active, 4 + len(index), penalty, start), index, fcs)


def elo_as_of(league, past, season):
    """v1's Elo (refresh.Model, unchanged) replayed over earlier games, regressed into `season`."""
    elo = Elo(league)
    for game in past:
        elo.train({'season': game['season'], 'neutral': game['neutral'],
                   'home': {'id': game['home']['id'], 'score': game['home']['score']},
                   'away': {'id': game['away']['id'], 'score': game['away']['score']}})
    elo.advance(season)
    return elo


class Model:
    """Both rating sets as of one cutoff, from games that kicked off before it."""

    def __init__(self, league, records, cutoff, season, params=None, warm=None, targets=('margin', 'total'), context=None):
        self.league, self.cutoff, self.season = league, cutoff, season
        self.params = params or PARAMS[league]
        # Inputs beyond the box scores (snap counts, venues, weather, injuries) arrive here. Every term
        # that reads them is off when the context is empty, so a model built without one is v2.0 exactly.
        self.context = context or {}
        past = [g for g in records if features.when(g['kickoff']) < cutoff]
        self.games, self.through = len(past), past[-1]['kickoff'] if past else None
        self.inputs = hashlib.sha256(json.dumps([(g['eventId'], g['hash']) for g in past]).encode()).hexdigest()[:16]
        rows = observations(past, self.params['pace'])
        self.counts = defaultdict(int)
        for row in rows:
            self.counts[row['team']] += row['season'] == season
        self.offseason = offseason_days(records, season, cutoff)
        fbs = fbs_teams(past) if league == 'CFB' else None
        self.fcs = (lambda team: team not in fbs) if fbs is not None else (lambda team: False)
        self.implied = implied_points(rows)
        # Per-team continuity is measured only when a target asks for it, so v2.0 parameters never read it.
        wants = any(self.params[t].get('continuity') for t in ('margin', 'total'))
        self.roster = continuity.continuity(past, season, cutoff) if wants else {}
        blend = self.params['total']['blend'] if self.implied else 1.0

        def total_target(row):
            if not row['efficiency'] or not self.implied:
                return row['points']
            return blend * row['points'] + (1 - blend) * sum(a * b for a, b in zip(self.implied, row['efficiency']))

        self.margin = self.total = None
        if 'margin' in targets:
            self.margin = fit(rows, cutoff, season, self.params['margin'], self.fcs, lambda row: row['points'],
                              warm.margin if warm else None, self.offseason, self.roster)
        if 'total' in targets:
            self.total = fit(rows, cutoff, season, self.params['total'], self.fcs, total_target,
                             warm.total if warm else None, self.offseason, self.roster)
        self.elo = elo_as_of(league, past, season) if self.params['margin'].get('eloWeight') else None
        # Team-level effects fitted from the same past games, in points scored and allowed. Each is
        # off unless the parameters ask for it; a forecast records which ones moved it.
        self.effects = {}
        shrink = (self.params.get('qbOut') or {}).get('shrink')
        if shrink is not None and self.margin is not None:
            self.effects['qbOut'] = self.qb_effects(rows, past, shrink)

    def qb_effects(self, rows, past, shrink):
        """Points scored and allowed when the usual starting quarterback did not play, as residuals.

        From the stored games before the cutoff, the mean margin-fit residual of a team's points in
        games its usual starter (known from earlier games only) did not throw in, and of the points
        scored against such a team. Each mean is shrunk toward zero by `shrink` pseudo-games. The
        extra spread of those residuals over all residuals widens the forecast's uncertainty.
        """
        flags = starters.qb_out_flags(past)
        residuals, scored, allowed = [], [], []
        for row in rows:
            residual = row['points'] - self.margin.points(row['team'], row['opp'], row['home'])
            residuals.append(residual)
            if flags.get((row['eventId'], row['team']), {}).get('out'):
                scored.append(residual)
            if flags.get((row['eventId'], row['opp']), {}).get('out'):
                allowed.append(residual)

        def shrunk(values):
            return sum(values) / (len(values) + shrink) if values else 0.0

        spread_all = statistics.pstdev(residuals) if len(residuals) > 1 else 0.0
        spread_out = statistics.pstdev(scored) if len(scored) > 4 else spread_all
        return {'for': round(shrunk(scored), 2), 'against': round(shrunk(allowed), 2),
                'n': {'for': len(scored), 'against': len(allowed)}, 'shrink': shrink,
                'sdExtra': round(max(0.0, spread_out - spread_all), 2)}

    def elo_margin(self, home, away, neutral):
        ratings = self.elo.ratings
        margin = ratings.get(home, 0.0) - ratings.get(away, 0.0) + (0.0 if neutral else self.elo.home)
        return max(-42.0, min(42.0, margin))

    def predict(self, home, away, neutral=False, game=None):
        """The forecast for one game. `game` carries per-game inputs (venue, weather, quarterback status) for
        the terms that read them; with none, the answer is the ratings alone and `adjustments` is empty."""
        at_home, p = not neutral, self.params
        margin = total = 0.0
        if self.margin:
            margin = self.margin.points(home, away, at_home) - self.margin.points(away, home, False)
            weight = p['margin'].get('eloWeight', 0.0)
            if weight:
                margin = (1 - weight) * margin + weight * self.elo_margin(home, away, neutral)
        if self.total:
            total = self.total.points(home, away, at_home) + self.total.points(away, home, False)
        sd_margin, sd_total, adjustments = p['sdMargin'], p['sdTotal'], {}
        qb, effect = (game or {}).get('qbOut') or {}, self.effects.get('qbOut')
        if effect and (qb.get('home') or qb.get('away')):
            home_pts, away_pts = (total + margin) / 2, (total - margin) / 2
            if qb.get('home'):
                home_pts, away_pts = home_pts + effect['for'], away_pts + effect['against']
            if qb.get('away'):
                away_pts, home_pts = away_pts + effect['for'], home_pts + effect['against']
            margin, total = home_pts - away_pts, home_pts + away_pts
            sd_margin = math.sqrt(sd_margin ** 2 + effect['sdExtra'] ** 2)
            sd_total = math.sqrt(sd_total ** 2 + effect['sdExtra'] ** 2)
            adjustments['qbOut'] = {'home': bool(qb.get('home')), 'away': bool(qb.get('away')),
                                    'points': {'for': effect['for'], 'against': effect['against']}, 'sdExtra': effect['sdExtra']}
        return {'margin': margin, 'total': total, 'home': (total + margin) / 2, 'away': (total - margin) / 2,
                'sdMargin': round(sd_margin, 2), 'sdTotal': round(sd_total, 2),
                'homeWinProb': 0.5 * (1 + math.erf(margin / (sd_margin * math.sqrt(2)))),
                'sparse': min(self.counts.get(home, 0), self.counts.get(away, 0)) < 3, 'adjustments': adjustments}


# ------------------------------------------------------------------ backtest

def week_start(moment):
    """Walk-forward refit point: the Tuesday 08:00 UTC at or before a kickoff."""
    base = moment.replace(hour=8, minute=0, second=0, microsecond=0)
    start = base - timedelta(days=(base.weekday() - 1) % 7)
    return start if start <= moment else start - timedelta(days=7)


def backtest(league, season, params=None, records=None, from_week=None, targets=('margin', 'total')):
    """Walk-forward forecasts for a season, each from games before its week's refit."""
    records = records if records is not None else features.load(leagues=(league,))
    games = [g for g in records if g['season'] == season
             and (from_week is None or g['seasonType'] == 3 or (g['week'] or 0) >= from_week)]
    # The quarterback flag for a backtest is read after the fact (the usual starter did not throw), a
    # stand-in for the injury report the live forecast reads; the fit itself never sees the game.
    flags = starters.qb_out_flags(records) if (params or PARAMS[league]).get('qbOut') else {}
    out, model, current = [], None, None
    for game in games:
        refit = week_start(features.when(game['kickoff']))
        if refit != current:
            model, current = Model(league, records, refit, season, params, warm=model, targets=targets), refit
        qb = {side: flags.get((game['eventId'], game[side]['id']), {}).get('out', False) for side in ('home', 'away')}
        forecast = model.predict(game['home']['id'], game['away']['id'], game['neutral'], game={'qbOut': qb} if flags else None)
        lines = features.market_lines(game)
        out.append({'eventId': game['eventId'], 'week': game['week'], 'seasonType': game['seasonType'],
                    'kickoff': game['kickoff'], 'margin': game['home']['score'] - game['away']['score'],
                    'total': game['home']['score'] + game['away']['score'], 'forecast': forecast,
                    'closeMargin': -lines['closeSpread'] if lines['closeSpread'] is not None else None,
                    'closeTotal': lines['closeTotal']})
    return out


def score(rows):
    """Average misses against the result, and records against the close."""
    def mean(values):
        values = list(values)
        return round(statistics.mean(values), 2) if values else None

    priced = [r for r in rows if r['closeMargin'] is not None and r['closeTotal'] is not None]
    side = [(r['forecast']['margin'] > r['closeMargin']) == (r['margin'] > r['closeMargin']) for r in priced
            if r['forecast']['margin'] != r['closeMargin'] and r['margin'] != r['closeMargin']]
    total = [(r['forecast']['total'] > r['closeTotal']) == (r['total'] > r['closeTotal']) for r in priced
             if r['forecast']['total'] != r['closeTotal'] and r['total'] != r['closeTotal']]
    margin_errors = [r['forecast']['margin'] - r['margin'] for r in rows]
    total_errors = [r['forecast']['total'] - r['total'] for r in rows]
    return {'games': len(rows), 'priced': len(priced),
            'marginMiss': mean(abs(r['forecast']['margin'] - r['margin']) for r in priced),
            'closeMarginMiss': mean(abs(r['closeMargin'] - r['margin']) for r in priced),
            'totalMiss': mean(abs(r['forecast']['total'] - r['total']) for r in priced),
            'closeTotalMiss': mean(abs(r['closeTotal'] - r['total']) for r in priced),
            'sideVsClose': [sum(side), len(side) - sum(side)], 'totalVsClose': [sum(total), len(total) - sum(total)],
            'within80': {'margin': mean(abs(e) <= Z80 * r['forecast']['sdMargin'] for e, r in zip(margin_errors, rows)),
                         'total': mean(abs(e) <= Z80 * r['forecast']['sdTotal'] for e, r in zip(total_errors, rows))},
            'residualSd': {'margin': round(statistics.pstdev(margin_errors), 2),
                           'total': round(statistics.pstdev(total_errors), 2)} if len(rows) > 1 else None}


def compare(rows_old, rows_new, target, draws=1000, seed=7, early_weeks=4):
    """Did a change help, on the same priced games? Paired per-game |miss| difference, new minus old.

    A negative mean is an improvement. The 90% interval is a seeded bootstrap of that mean. The verdict is
    WINS when the whole interval is below zero, LOSES when it is above zero or the mean is worse, and NOISE
    otherwise. Weeks 1 to `early_weeks` are shown apart because the prior-season terms matter most there.
    """
    close = f"close{target.capitalize()}"
    old_by = {r['eventId']: r for r in rows_old}
    pairs = []
    for new in rows_new:
        old = old_by.get(new['eventId'])
        if not old or new[close] is None or old[close] is None:
            continue
        pairs.append((new.get('week') or 0, new.get('seasonType'),
                      abs(new['forecast'][target] - new[target]) - abs(old['forecast'][target] - old[target])))
    diffs = [d for _, _, d in pairs]
    if not diffs:
        return {'n': 0, 'verdict': 'NO DATA'}
    mean = statistics.mean(diffs)
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choices(diffs, k=len(diffs))) for _ in range(draws))
    low, high = boots[int(0.05 * draws)], boots[min(int(0.95 * draws), draws - 1)]
    early = [d for w, st, d in pairs if st == 2 and w <= early_weeks]
    later = [d for w, st, d in pairs if not (st == 2 and w <= early_weeks)]
    verdict = 'WINS' if high < 0 else 'LOSES' if low > 0 or mean > 0 else 'NOISE'
    return {'n': len(diffs), 'meanDelta': round(mean, 3), 'interval90': [round(low, 3), round(high, 3)],
            'earlyWeeks': {'n': len(early), 'meanDelta': round(statistics.mean(early), 3)} if early else None,
            'laterWeeks': {'n': len(later), 'meanDelta': round(statistics.mean(later), 3)} if later else None,
            'verdict': verdict}


def ships(comparison, min_gain=0.10):
    """The ship rule: a clear win, or a gain of at least min_gain points that the bootstrap calls noise."""
    return comparison.get('verdict') == 'WINS' or (comparison.get('verdict') == 'NOISE' and comparison['meanDelta'] <= -min_gain)


def set_path(params, path, value):
    node = params
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    return params


def tune_knob(league, path, grid, base=None, tune_season=2024, holdout=2025, records=None, off=None, log=print):
    """Sweep one parameter on the tuning season with everything else held at `base`; score the holdout once.

    path is a tuple such as ('margin', 'continuity'); grid the values to try; `off` the value that means
    the knob is not there (ties go to it, and the holdout comparison is against `base`, which has it off).
    Returns everything a tuning file needs, including a `looks` entry: the holdout season is consulted once
    per feature, and the file should say how often it has been looked at.
    """
    records = records if records is not None else features.load(leagues=(league,))
    base = deepcopy(base or PARAMS[league])
    off = grid[0] if off is None else off
    targets = (path[0],) if path[0] in ('margin', 'total') else ('margin', 'total')
    trials = []
    for value in grid:
        params = set_path(deepcopy(base), path, value)
        result = score(backtest(league, tune_season, params, records, targets=targets))
        miss = {t: result[f'{t}Miss'] for t in targets}
        trials.append({'value': value, 'miss': miss, 'sum': sum(miss.values())})
        log(f"{league} {'.'.join(path)}={value}: {miss}")
    chosen = min(trials, key=lambda t: (t['sum'], 0 if t['value'] == off else 1))['value']
    tuned = set_path(deepcopy(base), path, chosen)
    old_rows = backtest(league, holdout, base, records)
    new_rows = backtest(league, holdout, tuned, records)
    comparison = {t: compare(old_rows, new_rows, t) for t in ('margin', 'total')}
    return {'league': league, 'version': VERSION, 'knob': '.'.join(path), 'grid': list(grid), 'off': off,
            'tuneSeason': tune_season, 'holdoutSeason': holdout, 'trials': trials, 'chosen': chosen,
            'base': base, 'tuned': tuned,
            'holdout': {'base': score(old_rows), 'tuned': score(new_rows), 'compare': comparison,
                        'ships': {t: ships(comparison[t]) for t in targets}},
            'looks': [{'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'knob': '.'.join(path),
                       'season': holdout}]}


def write_tuning(path, result):
    """Write a tuning file, carrying forward the holdout looks an earlier file recorded."""
    path = Path(path)
    if path.exists():
        try:
            earlier = json.loads(path.read_text(encoding='utf-8')).get('looks') or []
        except ValueError:
            earlier = []
        result = dict(result, looks=earlier + result.get('looks', []))
    path.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
    return result


GRID = {'halfLife': (45, 90, 180), 'ridge': (1.0, 3.0, 10.0), 'priorWeight': (0.3, 0.6, 1.0),
        'eloWeight': (0.0, 0.3, 0.5), 'blend': (0.3, 0.6, 1.0)}


def tune(league, tune_season=2024, holdout=2025, log=print):
    """Grid search the margin, then the total, on one full season; score the holdout once.

    The tuning season has a stored prior season, so its early weeks count too.
    Ties go to the simpler setting (no Elo, pure points).
    """
    records = features.load(leagues=(league,))
    defaults = {'halfLife': 90, 'ridge': 3.0, 'priorWeight': 0.6}
    trials, chosen = {'margin': [], 'total': []}, {}
    for target, knob in (('margin', 'eloWeight'), ('total', 'blend')):
        for half_life in GRID['halfLife']:
            for penalty in GRID['ridge']:
                for prior in GRID['priorWeight']:
                    for value in GRID[knob]:
                        candidate = {'halfLife': half_life, 'ridge': penalty, 'priorWeight': prior, knob: value}
                        params = {**PARAMS[league], 'margin': chosen.get('margin', {**defaults, 'eloWeight': 0.0}),
                                  'total': {**defaults, 'blend': 1.0}, target: candidate}
                        miss = score(backtest(league, tune_season, params, records, targets=(target,)))[f'{target}Miss']
                        trials[target].append({'params': candidate, 'miss': miss})
                        log(f'{league} {target} {candidate}: {miss}')
        simplest = (lambda t: t['params']['eloWeight']) if target == 'margin' else (lambda t: -t['params']['blend'])
        chosen[target] = min(trials[target], key=lambda t: (t['miss'], simplest(t)))['params']
    final = {**PARAMS[league], 'margin': chosen['margin'], 'total': chosen['total']}
    tuned = score(backtest(league, tune_season, final, records))
    final['sdMargin'], final['sdTotal'] = tuned['residualSd']['margin'], tuned['residualSd']['total']
    return {'league': league, 'version': VERSION, 'tuneSeason': tune_season, 'holdoutSeason': holdout,
            'chosen': final, 'tuning': tuned, 'holdout': score(backtest(league, holdout, final, records)),
            'trials': trials}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('backtest')
    run.add_argument('league')
    run.add_argument('season', type=int)
    run.add_argument('--from-week', type=int)
    grid = sub.add_parser('tune', help='the full grid, or one knob with --knob and --grid')
    grid.add_argument('league')
    grid.add_argument('--out')
    grid.add_argument('--knob', help='one nested parameter, such as margin.continuity')
    grid.add_argument('--grid', help='comma-separated values for --knob; the first means off')
    grid.add_argument('--tune-season', type=int, default=2024)
    grid.add_argument('--holdout', type=int, default=2025)
    diff = sub.add_parser('compare', help='candidate parameters against the current ones on one season')
    diff.add_argument('league')
    diff.add_argument('season', type=int)
    diff.add_argument('--params', required=True, help='JSON file holding the candidate PARAMS[league] block')
    args = parser.parse_args(argv)
    league = args.league.upper()
    if args.command == 'backtest':
        print(json.dumps(score(backtest(league, args.season, from_week=args.from_week)), indent=1))
        return
    if args.command == 'compare':
        candidate = json.loads(Path(args.params).read_text(encoding='utf-8'))
        records = features.load(leagues=(league,))
        old_rows, new_rows = backtest(league, args.season, None, records), backtest(league, args.season, candidate, records)
        out = {'current': score(old_rows), 'candidate': score(new_rows),
               'compare': {t: compare(old_rows, new_rows, t) for t in ('margin', 'total')}}
        out['ships'] = {t: ships(out['compare'][t]) for t in ('margin', 'total')}
        print(json.dumps(out, indent=1))
        return
    if args.knob:
        values = [float(v) if v.lower() not in ('none', 'off') else None for v in args.grid.split(',')]
        values = [int(v) if isinstance(v, float) and v.is_integer() and 'e' not in str(v) else v for v in values]
        result = tune_knob(league, tuple(args.knob.split('.')), values, tune_season=args.tune_season,
                           holdout=args.holdout, log=lambda *_: None)
    else:
        result = tune(league, log=lambda *_: None)
    if args.out:
        result = write_tuning(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, indent=1))


if __name__ == '__main__':
    main()
