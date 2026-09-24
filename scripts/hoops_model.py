"""Basketball team ratings (NBA and men's college): points from offense, defense and home court.

Each side's points in a game are modelled as

    points = league mean + home edge (zero at a neutral site) + own offense + opponent's defense

fitted by weighted ridge regression on the season's games before a cutoff. Two things set the
weights:

  halfLife  a game's weight halves every this many days before the cutoff
  ridge     how many games' worth of evidence last season's number counts for; each team's
            offense and defense are pulled toward it with this strength
  carry     last season's closing ratings are shrunk toward zero (an average team) by this
            factor before they become this season's starting point

So a team starts the season at `carry` times where it finished last season and moves off that
number as its games come in. A team with no rating last season starts at average. College
teams outside Division I (fewer than SMALL_GAMES stored games in every season before the
cutoff) share one rating, so a lightly observed small school is not treated as an average
Division I team. Margin and total are fitted separately, each with its own three knobs.

The system is solved by preconditioned conjugate gradients on the sparse design (each row
touches the mean, maybe the home edge, one offense and one defense), warm-started from the
previous refit, so a 360-team college league refits in well under a second. Every forecast
carries a margin and total standard deviation from the fit's own residuals (recency-weighted,
blended at the start of a season with last season's), and a home win probability.

Walk-forward: ratings are refit every `refitDays` days at 08:00 UTC, when the previous US
evening is final, from games that tipped off before that moment only, and forecast every game
until the next refit. No market input: the market is the yardstick, not an input.

Evaluation mirrors model_v2: knobs are tuned on one season (2024-25, with 2023-24 as history)
and the chosen setting is scored once on an untouched season (2025-26). The grade reports the
average miss against the result beside the close's, how often our number was closer, the
record of our side against the closing line bucketed by our gap to the opening line (where
the desk would usually bet), and the calibration shrink k (calibrated = 50% + k * (raw - 50%))
fitted on the tuning season and checked on the holdout.

Usage:
  python scripts/hoops_model.py backtest NBA 2026           walk-forward grade of one season
  python scripts/hoops_model.py tune CBB [--workers 8]      grid on 2025, holdout 2026 once
Stdlib only.
"""
import argparse
import bisect
import hashlib
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hoops_store
import model_v2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'model'
VERSION = 'hoops-v1'
# Chosen by `tune` on 2024-25 (with 2023-24 as history) and scored once on the untouched
# 2025-26 season; see data/model/hoops-nba.json and hoops-cbb.json.
PARAMS = {
    'NBA': {'margin': {'halfLife': 45, 'ridge': 5.0, 'carry': 1.0},
            'total': {'halfLife': 30, 'ridge': 5.0, 'carry': 1.0}, 'refitDays': 1},
    'CBB': {'margin': {'halfLife': 60, 'ridge': 10.0, 'carry': 0.6},
            'total': {'halfLife': 60, 'ridge': 10.0, 'carry': 0.6}, 'refitDays': 1},
}
# The untuned starting point: the grid's other target is held here, and the holdout
# comparison asks whether the tuned setting beat it.
DEFAULTS = {league: {'margin': {'halfLife': 60, 'ridge': 10.0, 'carry': 0.6},
                     'total': {'halfLife': 60, 'ridge': 10.0, 'carry': 0.6}, 'refitDays': 1}
            for league in ('NBA', 'CBB')}
GRID = {league: {'halfLife': (20, 30, 45, 60, 90, 120, 180, 365), 'ridge': (2.0, 5.0, 10.0, 20.0, 40.0),
                 'carry': (0.3, 0.45, 0.6, 0.75, 0.9, 1.0)} for league in ('NBA', 'CBB')}
SMALL_GAMES = {'NBA': 0, 'CBB': 5}   # below this many games in every stored season, a team is a small school
SMALL = '~small'                      # the shared rating of small schools
ANCHOR = 2.0                          # games' worth of pull toward last season's mean and home edge
SD_PRIOR_GAMES = 20.0                 # games' worth of last season's residual spread in this season's
REFIT_HOUR = 8                        # UTC hour of each refit
# Gap between our number and the opening line (points), for the records by bucket. College
# numbers disagree with the market more, so its buckets are wider. The lean is the top two.
BUCKETS = {'NBA': (0.0, 1.0, 2.0, 4.0), 'CBB': (0.0, 1.5, 3.0, 6.0)}
LEAN = {'NBA': 2.0, 'CBB': 3.0}
BREAK_EVEN = 0.5238  # -110 on both sides
Z90 = 1.6448536269514722
DAY = 86400.0


# ------------------------------------------------------------------ inputs

class Game:
    """One stored final, reduced to what the model and the grade read."""
    __slots__ = ('id', 't', 'season', 'type', 'kickoff', 'home', 'away', 'neutral', 'hs', 'as_',
                 'close', 'open', 'label')

    def __init__(self, rec):
        self.id, self.season, self.type, self.kickoff = rec['id'], rec['season'], rec.get('type', 2), rec['kickoff']
        self.t = when(rec['kickoff']).timestamp()
        self.home, self.away = rec['home']['id'], rec['away']['id']
        self.neutral = bool(rec.get('neutral'))
        self.hs, self.as_ = rec['homeScore'], rec['awayScore']
        self.close, self.open = rec.get('close') or {}, rec.get('open') or {}
        self.label = (rec['home'].get('abbreviation'), rec['away'].get('abbreviation'))


def when(text):
    return datetime.fromisoformat(str(text).replace('Z', '+00:00'))


def prepare(records):
    return sorted((Game(r) for r in records), key=lambda g: (g.t, g.id))


def params_hash(params):
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]


def known_teams(games, league):
    """Teams with at least SMALL_GAMES games in some season among `games`; None means everyone is known."""
    need = SMALL_GAMES[league]
    if not need:
        return None
    counts = defaultdict(int)
    for g in games:
        counts[g.season, g.home] += 1
        counts[g.season, g.away] += 1
    return {team for (_, team), n in counts.items() if n >= need}


# ------------------------------------------------------------------ solving

def solve(offense, defense, home, weights, targets, penalty, centre, start=None, tolerance=1e-8, limit=None):
    """Weighted ridge regression of points on [mean, home, offense, defense], pulled toward `centre`.

    Minimises sum w (y - x.b)^2 + sum penalty_j (b_j - centre_j)^2, where row r's x has ones at
    column 0 (the mean), column 1 when home[r], offense[r] and defense[r]. Solved for the
    deviation from the centre by conjugate gradients with a diagonal preconditioner, stopping
    on the relative residual; `start` warm-starts it. A column no row touches and no penalty
    holds stays at its centre.
    """
    size = len(centre)
    diagonal = list(penalty)
    rhs = [0.0] * size
    for o, d, h, w, y in zip(offense, defense, home, weights, targets):
        fitted = centre[0] + centre[o] + centre[d] + (centre[1] if h else 0.0)
        s = w * (y - fitted)
        rhs[0] += s
        rhs[o] += s
        rhs[d] += s
        diagonal[0] += w
        diagonal[o] += w
        diagonal[d] += w
        if h:
            rhs[1] += s
            diagonal[1] += w
    free = [value > 0 for value in diagonal]
    diagonal = [value if value > 0 else 1.0 for value in diagonal]

    def apply(v):
        out = [p * x for p, x in zip(penalty, v)]
        v0, v1, a0, a1 = v[0], v[1], 0.0, 0.0
        for o, d, h, w in zip(offense, defense, home, weights):
            s = w * (v0 + v[o] + v[d] + (v1 if h else 0.0))
            out[o] += s
            out[d] += s
            a0 += s
            if h:
                a1 += s
        out[0] += a0
        out[1] += a1
        return [x if f else 0.0 for x, f in zip(out, free)]

    delta = [(s - c) if f else 0.0 for s, c, f in zip(start, centre, free)] if start else [0.0] * size
    residual = [r - a for r, a in zip(rhs, apply(delta))] if start else list(rhs)
    scale = math.sqrt(sum(r * r for r in rhs)) or 1.0
    z = [r / q for r, q in zip(residual, diagonal)]
    direction = list(z)
    rz = sum(r * q for r, q in zip(residual, z))
    for _ in range(limit or 4 * size):
        if math.sqrt(sum(r * r for r in residual)) <= tolerance * scale:
            break
        product_ = apply(direction)
        curvature = sum(d * p for d, p in zip(direction, product_))
        if curvature <= 0:
            break
        step = rz / curvature
        delta = [x + step * d for x, d in zip(delta, direction)]
        residual = [r - step * p for r, p in zip(residual, product_)]
        z = [r / q for r, q in zip(residual, diagonal)]
        updated = sum(r * q for r, q in zip(residual, z))
        direction = [q + (updated / rz) * d for q, d in zip(z, direction)]
        rz = updated
    return [c + x for c, x in zip(centre, delta)]


class Ratings:
    """One fitted target: mean, home edge, and offense/defense per team key."""

    def __init__(self, beta, index, residual_var, weight, games):
        self.beta, self.index, self.var, self.weight, self.games = beta, index, residual_var, weight, games

    def points(self, team, opponent, at_home):
        b, i = self.beta, self.index
        return (b[0] + (b[1] if at_home else 0.0) + (b[i[team]] if team in i else 0.0)
                + (b[i[opponent] + 1] if opponent in i else 0.0))

    def team(self, key):
        position = self.index.get(key)
        return (self.beta[position], self.beta[position + 1]) if position is not None else (0.0, 0.0)

    def as_prior(self):
        """What next season starts from (before `carry` shrinks it)."""
        return {'mean': self.beta[0], 'home': self.beta[1], 'var': self.var,
                'teams': {key: self.team(key) for key in self.index}}


def fit(games, cutoff, knobs, key, prior=None, warm=None):
    """Ratings from `games` (all before the cutoff, one season), toward last season's shrunk ratings.

    key(team) maps a team to its rating key (small schools share one). prior is the previous
    season's Ratings.as_prior() or None; warm an earlier Ratings of the same season.
    """
    index = {}
    # Every team rated last season keeps a place, so a team yet to play still starts from its prior.
    for team in list((prior or {}).get('teams', {})) + [key(t) for g in games for t in (g.home, g.away)]:
        if team not in index:
            index[team] = 2 + 2 * len(index)
    if not index and not prior:
        raise ValueError('no games before the cutoff and no prior season to start from')
    size = 2 + 2 * len(index)
    carry = knobs['carry']
    centre = [0.0] * size
    penalty = [0.0] * size
    if prior:
        centre[0], centre[1] = prior['mean'], prior['home']
        penalty[0] = penalty[1] = ANCHOR
    for team, position in index.items():
        off, dfn = prior['teams'].get(team, (0.0, 0.0)) if prior else (0.0, 0.0)
        centre[position], centre[position + 1] = carry * off, carry * dfn
        penalty[position] = penalty[position + 1] = knobs['ridge']
    offense, defense, home, weights, targets = [], [], [], [], []
    half = knobs['halfLife'] * DAY
    for g in games:
        w = 0.5 ** (max(cutoff - g.t, 0.0) / half)
        h, a = index[key(g.home)], index[key(g.away)]
        offense += [h, a]
        defense += [a + 1, h + 1]
        home += [not g.neutral, False]
        weights += [w, w]
        targets += [g.hs, g.as_]
    start = None
    if warm is not None:
        start = list(centre)
        start[0], start[1] = warm.beta[0], warm.beta[1]
        for team, position in index.items():
            if team in warm.index:
                start[position], start[position + 1] = warm.team(team)
    beta = solve(offense, defense, home, weights, targets, penalty, centre, start)
    ratings = Ratings(beta, index, {}, 0.0, len(games))
    # In-sample residual spread of margins and totals, recency-weighted like the fit.
    sums, total_weight = {'margin': 0.0, 'total': 0.0}, 0.0
    for g, w in zip(games, weights[::2]):
        ph = ratings.points(key(g.home), key(g.away), not g.neutral)
        pa = ratings.points(key(g.away), key(g.home), False)
        sums['margin'] += w * ((g.hs - g.as_) - (ph - pa)) ** 2
        sums['total'] += w * ((g.hs + g.as_) - (ph + pa)) ** 2
        total_weight += w
    residual_var = {}
    for target in ('margin', 'total'):
        earlier = (prior or {}).get('var', {}).get(target)
        if earlier is not None:
            residual_var[target] = (sums[target] + SD_PRIOR_GAMES * earlier) / (total_weight + SD_PRIOR_GAMES)
        elif total_weight:
            residual_var[target] = sums[target] / total_weight
    ratings.var, ratings.weight = residual_var, total_weight
    return ratings


# ------------------------------------------------------------------ the model

class Model:
    """Margin and total ratings as of one cutoff, from the season's games that tipped off before it."""

    def __init__(self, league, games, cutoff, season, params=None, prior=None, warm=None, targets=('margin', 'total')):
        self.league, self.season, self.params = league, season, params or PARAMS[league]
        self.cutoff = cutoff.timestamp() if isinstance(cutoff, datetime) else float(cutoff)
        stop = bisect.bisect_left([g.t for g in games], self.cutoff)
        before = games[:stop]
        self.used = [g for g in before if g.season == season]
        self.through = max((g.t for g in self.used), default=None)
        known = known_teams(before, league)
        self.key = (lambda team: team) if known is None else (lambda team: team if team in known else SMALL)
        self.counts = defaultdict(int)
        for g in self.used:
            self.counts[g.home] += 1
            self.counts[g.away] += 1
        self.fits = {}
        for target in targets:
            self.fits[target] = fit(self.used, self.cutoff, self.params[target], self.key,
                                    (prior or {}).get(target), (warm.fits.get(target) if warm else None))

    def predict(self, home, away, neutral=False):
        """Margin (home minus away) and total with standard deviations, and the home win probability."""
        out = {}
        h, a = self.key(home), self.key(away)
        if 'margin' in self.fits:
            m = self.fits['margin']
            out['margin'] = m.points(h, a, not neutral) - m.points(a, h, False)
            out['sdMargin'] = math.sqrt(m.var.get('margin', 0.0)) or None
        if 'total' in self.fits:
            t = self.fits['total']
            out['total'] = t.points(h, a, not neutral) + t.points(a, h, False)
            out['sdTotal'] = math.sqrt(t.var.get('total', 0.0)) or None
        if 'margin' in out and out.get('sdMargin'):
            out['homeWinProb'] = 0.5 * (1 + math.erf(out['margin'] / (out['sdMargin'] * math.sqrt(2))))
        out['sparse'] = min(self.counts.get(home, 0), self.counts.get(away, 0)) < 3
        return out

    def as_prior(self):
        return {target: ratings.as_prior() for target, ratings in self.fits.items()}


def season_prior(league, games, season, params, targets=('margin', 'total')):
    """Last season's closing ratings, each season started from the one before it (none for the first)."""
    prior = None
    for year in sorted({g.season for g in games if g.season < season}):
        last = max(g.t for g in games if g.season == year)
        if prior is not None and not any(g.season == year - 1 for g in games):
            prior = None  # a missing season breaks the chain rather than carrying across it
        prior = Model(league, games, last + 1.0, year, params, prior, targets=targets).as_prior()
    return prior


def refit_point(t, season, days):
    """The refit moment at or before a tip-off: every `days` days at REFIT_HOUR UTC from 1 July before the season."""
    anchor = datetime(season - 1, 7, 1, REFIT_HOUR, tzinfo=timezone.utc).timestamp()
    return anchor + math.floor((t - anchor) / (days * DAY)) * days * DAY


# ------------------------------------------------------------------ walk-forward

def backtest(league, season, params=None, records=None, targets=('margin', 'total'), games=None):
    """Walk-forward forecasts for every stored game of a season, each from games before its refit."""
    params = params or PARAMS[league]
    games = games if games is not None else prepare(records if records is not None else hoops_store.load(league))
    prior = season_prior(league, games, season, params, targets)
    rows, model, current = [], None, None
    for g in (g for g in games if g.season == season):
        cutoff = refit_point(g.t, season, params['refitDays'])
        if cutoff != current:
            try:
                model = Model(league, games, cutoff, season, params, prior, warm=model, targets=targets)
            except ValueError:  # the first stored season's opening day: nothing to rate from yet
                model = None
            current = cutoff
        rows.append(row(league, g, model.predict(g.home, g.away, g.neutral) if model else {}))
    return rows


def row(league, g, forecast):
    """One backtest row, in the shape of data/model/backtest-v2.json."""
    def r2(value):
        return round(value, 2) if isinstance(value, (int, float)) else value

    close_margin = -g.close['spread'] if 'spread' in g.close else None
    open_margin = -g.open['spread'] if 'spread' in g.open else None
    actual_margin, actual_total = g.hs - g.as_, g.hs + g.as_
    out = {'gameId': g.id, 'league': league, 'season': g.season, 'type': g.type, 'kickoff': g.kickoff,
           'model': VERSION, 'home': g.label[0], 'away': g.label[1], 'neutral': g.neutral,
           'margin': r2(forecast.get('margin')), 'total': r2(forecast.get('total')),
           'sdMargin': r2(forecast.get('sdMargin')), 'sdTotal': r2(forecast.get('sdTotal')),
           'closeMargin': close_margin, 'closeTotal': g.close.get('total'),
           'openMargin': open_margin, 'openTotal': g.open.get('total'), 'books': g.close.get('books'),
           'actualMargin': actual_margin, 'actualTotal': actual_total, 'sparse': forecast.get('sparse')}
    for target, actual in (('Margin', actual_margin), ('Total', actual_total)):
        ours, close = out[target.lower()], out[f'close{target}']
        out[f'closer{target}'] = (abs(ours - actual) < abs(close - actual)) if None not in (ours, close) else None
    return out


# ------------------------------------------------------------------ grading

def mean(values):
    values = list(values)
    return round(statistics.mean(values), 3) if values else None


def wilson(won, n, z=Z90):
    """A 90% interval for a win rate."""
    if not n:
        return None
    p = won / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(centre - half, 4), round(centre + half, 4)]


def outcome(side, line, actual):
    """'W', 'L' or 'P' for a side (+1 over/home, -1 under/away) against a line, in the model's units."""
    if actual == line:
        return 'P'
    return 'W' if (actual > line) == (side > 0) else 'L'


def record(results):
    won, lost, push = results.count('W'), results.count('L'), results.count('P')
    return {'won': won, 'lost': lost, 'push': push, 'rate': round(won / (won + lost), 4) if won + lost else None,
            'interval90': wilson(won, won + lost)}


def bucket_of(gap, edges):
    """The bucket label for a gap: edges (0, 1, 2, 4) give '0-1', '1-2', '2-4' and '4+'."""
    for low, high in zip(edges, edges[1:]):
        if low <= gap < high:
            return f'{low:g}-{high:g}'
    return f'{edges[-1]:g}+'


def by_opening_gap(rows, market, edges, lean):
    """Our side taken against the opening line, graded at the close (and at the open), by the gap.

    Our side is over (home) when our number is above the opening total (home margin). The
    closing-line grade is the conservative one: it is what the side would have done had the
    desk only got the closing number. `lineMove` is how the market went from open to close
    in our side's favour (points; positive when it moved toward our number), the closing-line
    value a bet at the opening number would have had.
    """
    cap = market.capitalize()
    buckets = defaultdict(lambda: {'close': [], 'open': [], 'move': []})
    for r in rows:
        ours, close, opening, actual = r[market], r[f'close{cap}'], r[f'open{cap}'], r[f'actual{cap}']
        if None in (ours, close, opening) or ours == opening:
            continue
        side = 1 if ours > opening else -1
        label = bucket_of(abs(ours - opening), edges)
        for name in (label, f'lean {lean:g}+' if abs(ours - opening) >= lean else None, 'all'):
            if name:
                buckets[name]['close'].append(outcome(side, close, actual))
                buckets[name]['open'].append(outcome(side, opening, actual))
                buckets[name]['move'].append(side * (close - opening))
    order = [bucket_of(e, edges) for e in edges] + [f'lean {lean:g}+', 'all']
    return {name: {'n': len(b['close']), 'atClose': record(b['close']), 'atOpen': record(b['open']),
                   'lineMove': {'toward': round(sum(m > 0 for m in b['move']) / len(b['move']), 4),
                                'away': round(sum(m < 0 for m in b['move']) / len(b['move']), 4),
                                'mean': mean(b['move'])}}
            for name in order if name in buckets for b in [buckets[name]]}


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def chance_samples(rows, market, against='close'):
    """[(raw chance of the side our number favours against the line, whether it won)], pushes left out.

    `against` is 'close' (the grade a calibration ships on, as in scripts/calibrate.py) or 'open'.
    """
    out = []
    cap = market.capitalize()
    sd_key = 'sdMargin' if market == 'margin' else 'sdTotal'
    for r in rows:
        ours, line, actual, sd = r[market], r[f'{against}{cap}'], r[f'actual{cap}'], r[sd_key]
        if None in (ours, line, sd) or not sd or actual == line or ours == line:
            continue
        raw = 1 - phi((line - ours) / sd)  # chance the home side (or the over) beats the line
        high = raw >= 0.5
        out.append((raw if high else 1 - raw, (actual > line) == high))
    return out


def loglik(samples, k):
    return sum(math.log(max(1e-9, p if won else 1 - p)) for c, won in samples for p in [0.5 + k * (c - 0.5)])


def fit_k(samples, steps=100):
    """The k in [0, 1] that maximises the log-likelihood (scripts/calibrate.py's rule)."""
    return max((i / steps for i in range(steps + 1)), key=lambda k: loglik(samples, k)) if samples else None


def reliability(samples, k, edges=(0.5, 0.52, 0.54, 0.57, 1.01)):
    """Calibrated chance against how often that side won, in bins."""
    out = []
    for low, high in zip(edges, edges[1:]):
        inside = [(0.5 + k * (c - 0.5), won) for c, won in samples if low <= 0.5 + k * (c - 0.5) < high]
        if inside:
            out.append({'bin': f'{100 * low:.0f}-{min(100 * high, 100):.0f}%', 'n': len(inside),
                        'expected': round(statistics.mean(p for p, _ in inside), 4),
                        'won': round(statistics.mean(w for _, w in inside), 4)})
    return out


def calibration(tune_rows, holdout_rows, market, against='close'):
    """k fitted on the tuning season and checked on the holdout: does it predict better than a coin?

    `fits` asks two things of the holdout: k is above zero (k = 0 says the raw chance carries no
    information against the line), and the tuning season's k beats 50% on log-likelihood.
    """
    fitted, check = chance_samples(tune_rows, market, against), chance_samples(holdout_rows, market, against)
    k = fit_k(fitted)
    if k is None or not check:
        return {'k': k, 'n': len(fitted), 'holdout': None}
    gain = loglik(check, k) - loglik(check, 0.0)
    return {'k': k, 'n': len(fitted), 'tuneWon': round(statistics.mean(w for _, w in fitted), 4),
            'holdout': {'n': len(check), 'won': round(statistics.mean(w for _, w in check), 4),
                        'kRefit': fit_k(check), 'logLikGainOverCoin': round(gain, 2),
                        'logLikGainRaw': round(loglik(check, 1.0) - loglik(check, 0.0), 2),
                        'reliability': reliability(check, k), 'fits': bool(k > 0 and gain > 0)}}


def grade(rows, league):
    """Everything the desk needs to know about one season's walk-forward, per market."""
    out = {'games': len(rows)}
    for market in ('margin', 'total'):
        cap = market.capitalize()
        priced = [r for r in rows if r[f'close{cap}'] is not None and r[market] is not None]
        closer = [r[f'closer{cap}'] for r in priced]
        sides = [outcome(1 if r[market] > r[f'close{cap}'] else -1, r[f'close{cap}'], r[f'actual{cap}'])
                 for r in priced if r[market] != r[f'close{cap}']]
        errors = [r[market] - r[f'actual{cap}'] for r in rows if r[market] is not None]
        sds = [r['sdMargin' if market == 'margin' else 'sdTotal'] for r in rows
               if r['sdMargin' if market == 'margin' else 'sdTotal']]
        with_open = [r for r in priced if r[f'open{cap}'] is not None]
        out[market] = {
            'priced': len(priced),
            'miss': mean(abs(r[market] - r[f'actual{cap}']) for r in priced),
            'closeMiss': mean(abs(r[f'close{cap}'] - r[f'actual{cap}']) for r in priced),
            'openMiss': mean(abs(r[f'open{cap}'] - r[f'actual{cap}']) for r in with_open),
            'closerThanClose': round(sum(closer) / len(closer), 4) if closer else None,
            'vsClose': record(sides),
            'byOpeningGap': by_opening_gap(rows, market, BUCKETS[league], LEAN[league]),
            'residualSd': round(statistics.pstdev(errors), 2) if len(errors) > 1 else None,
            'meanForecastSd': mean(sds),
        }
    return out


def paired(rows_old, rows_new, market):
    """model_v2.compare on hoops rows: the per-game |miss| of new minus old on the same priced games."""
    first = {}
    for r in rows_old + rows_new:
        first[r['season']] = min(first.get(r['season'], when(r['kickoff'])), when(r['kickoff']))

    def shaped(rows):
        # Weeks count from the season's first game, so model_v2's early-weeks split is the first month.
        return [{'eventId': r['gameId'], 'week': (when(r['kickoff']) - first[r['season']]).days // 7 + 1,
                 'seasonType': r['type'],
                 'forecast': {market: r[market]}, market: r[f'actual{market.capitalize()}'],
                 f'close{market.capitalize()}': r[f'close{market.capitalize()}']} for r in rows]
    return model_v2.compare(shaped(rows_old), shaped(rows_new), market)


def as_close(rows):
    """The same rows with the close as the forecast, to put our misses beside the market's."""
    return [dict(r, margin=r['closeMargin'], total=r['closeTotal']) for r in rows]


# ------------------------------------------------------------------ tuning

_GAMES = None


def _load(league):
    global _GAMES
    _GAMES = prepare(hoops_store.load(league))


def _trial(job):
    league, season, target, knobs, base = job
    params = deepcopy(base)
    params[target] = dict(knobs)
    rows = backtest(league, season, params, targets=(target,), games=_GAMES)
    priced = [r for r in rows if r[f'close{target.capitalize()}'] is not None]
    return {'params': knobs, 'miss': mean(abs(r[target] - r[f'actual{target.capitalize()}']) for r in priced),
            'n': len(priced)}


def simplicity(knobs):
    """Ties go to the longest memory, the strongest pull and the most carry (the plainest model)."""
    return (-knobs['halfLife'], -knobs['ridge'], -knobs['carry'])


def tune(league, tune_season=2025, holdout=2026, workers=None, note=None, log=print):
    """Grid search each target on the tuning season; score the chosen setting once on the holdout.

    Every run is a look at the holdout and is recorded as one in the tuning file (with `note`).
    """
    games = prepare(hoops_store.load(league))
    base = deepcopy(DEFAULTS[league])
    grid = GRID[league]
    combos = [dict(zip(('halfLife', 'ridge', 'carry'), values))
              for values in product(grid['halfLife'], grid['ridge'], grid['carry'])]
    trials, chosen = {}, {}
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    with ProcessPoolExecutor(max_workers=workers, initializer=_load, initargs=(league,)) as pool:
        for target in ('margin', 'total'):
            jobs = [(league, tune_season, target, knobs, base) for knobs in combos]
            trials[target] = list(pool.map(_trial, jobs))
            for trial in trials[target]:
                log(f"{league} {target} {trial['params']}: {trial['miss']}")
            chosen[target] = min(trials[target], key=lambda t: (t['miss'], simplicity(t['params'])))['params']
    final = {**base, 'margin': chosen['margin'], 'total': chosen['total']}
    tune_rows = backtest(league, tune_season, final, games=games)
    holdout_rows = backtest(league, holdout, final, games=games)       # the one look at the holdout
    default_rows = backtest(league, holdout, base, games=games)
    result = {
        'league': league, 'version': VERSION, 'tuneSeason': tune_season, 'holdoutSeason': holdout,
        'store': store_hash(league), 'grid': grid, 'defaults': base, 'chosen': final,
        'paramsHash': params_hash(final),
        'tuning': grade(tune_rows, league),
        'holdout': grade(holdout_rows, league),
        'compare': {
            'tunedVsDefaults': {m: paired(default_rows, holdout_rows, m) for m in ('margin', 'total')},
            'oursVsClose': {m: paired(as_close(holdout_rows), holdout_rows, m) for m in ('margin', 'total')},
        },
        'calibration': {'spread': calibration(tune_rows, holdout_rows, 'margin'),
                        'total': calibration(tune_rows, holdout_rows, 'total'),
                        'atOpen': {'spread': calibration(tune_rows, holdout_rows, 'margin', 'open'),
                                   'total': calibration(tune_rows, holdout_rows, 'total', 'open')}},
        'trials': trials,
        'looks': [{'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'what': 'tuned setting, once',
                   'season': holdout, **({'note': note} if note else {})}],
    }
    result['compare']['tunedVsDefaults']['ships'] = {m: model_v2.ships(result['compare']['tunedVsDefaults'][m])
                                                     for m in ('margin', 'total')}
    return result, tune_rows + holdout_rows


def store_hash(league):
    ledger = json.loads((hoops_store.STORE / 'ledger.json').read_text(encoding='utf-8'))
    entries = {k: v for k, v in sorted(ledger.items()) if k.startswith(league.lower() + '-')}
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()[:12]


def write_results(league, result, rows, out=OUT):
    """The tuning record (carrying forward earlier holdout looks) and the walk-forward rows."""
    path = out / f'hoops-{league.lower()}.json'
    model_v2.write_tuning(path, result)
    cache = {'key': {'version': VERSION, 'params': result['paramsHash'], 'store': result['store']}, 'rows': rows}
    (out / f'hoops-backtest-{league.lower()}.json').write_text(
        json.dumps(cache, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('backtest', help='walk-forward grade of one season with the shipped parameters')
    run.add_argument('league', choices=sorted(PARAMS))
    run.add_argument('season', type=int)
    grid = sub.add_parser('tune', help='grid on the tuning season, then the holdout once; writes data/model/')
    grid.add_argument('league', choices=sorted(PARAMS))
    grid.add_argument('--tune-season', type=int, default=2025)
    grid.add_argument('--holdout', type=int, default=2026)
    grid.add_argument('--workers', type=int)
    grid.add_argument('--note', help='recorded with this look at the holdout')
    args = parser.parse_args(argv)
    if args.command == 'backtest':
        print(json.dumps(grade(backtest(args.league, args.season), args.league), indent=1))
        return
    result, rows = tune(args.league, args.tune_season, args.holdout, args.workers, args.note, log=lambda *_: None)
    write_results(args.league, result, rows)
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, indent=1))


if __name__ == '__main__':
    main()
