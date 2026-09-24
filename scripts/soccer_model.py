"""Soccer scores from goals and shots: a Dixon-Coles Poisson model, walk-forward. Stdlib only.

Each club has an attack and a defence rating. A match's expected goals are

  home side   exp(mu + home + attack[home] - defence[away])
  away side   exp(mu + attack[away] - defence[home])

fitted by maximum likelihood (Newton's method) to every stored match before the cutoff. Each
match counts 0.5 ** (age in days / halfLife), and last season's matches a further seasonCarry
per season back. With shotsBlend below 1 the rates are fitted to a blend of goals and the goals
a side's shots on and off target were worth (Premier League files carry shots; MLS's does not),
which carries less finishing luck than goals alone. A ridge penalty pulls every rating toward
zero, the league average, so a club with few matches stays near it. Dixon and Coles' rho, when
on, corrects the four low scores (0-0, 1-0, 0-1, 1-1) that independent Poisson counts get
slightly wrong; it is estimated from the same weighted matches at every refit.

A promoted club (or an MLS expansion club) is pulled toward a prior instead of zero: the average
rating of the clubs that went down, fitted when the season opens. When no club went down (MLS),
the prior is the average of the weakest `newcomerPool` clubs of last season. Which clubs play in
a season is known from the published schedule before it starts; no result is used early.

The score grid (0 to 10 goals a side) gives every market: 1X2, draw-no-bet, over/under 2.5 and
the Asian handicap at any line, a quarter line settled as two half stakes on the lines either side.

Walk-forward: the ratings are refitted at 06:00 UTC every Tuesday and Friday, before a midweek
round and before a weekend round, from matches that kicked off earlier. football-data's first
prices are collected on Tuesday and Friday afternoons, so an opening price and our number are
from the same moment.

Tuning mirrors model_v2: the knobs are chosen on one season (EPL 2024-25, MLS 2024) with every
earlier season as history; the untouched next season (EPL 2025-26, MLS 2025) is scored once and
the look is recorded. data/model/soccer-<league>.json holds both. The market is only the
yardstick: its de-vigged close is compared with ours, and our leans are settled at its prices.

Usage:
  python scripts/soccer_model.py predict EPL Arsenal Chelsea [--line -0.75]
  python scripts/soccer_model.py tune EPL        grid on the tuning season -> data/model/soccer-epl.json
  python scripts/soccer_model.py holdout EPL     the one look at the untouched season, added to that file
"""
import argparse
import bisect
import functools
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import soccer_store

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'data' / 'model'
VERSION = 'soccer-v1'
MAX_GOALS = 10
MIN_WEIGHT = 1e-3          # older matches than this weight are left out of a fit
RHO_BOUNDS = (-0.2, 0.2)
REFIT_WEEKDAYS = (1, 4)    # Tuesday and Friday
REFIT_HOUR = 6
THRESHOLDS = (2, 4, 6)     # points by which our chance beats the de-vigged price
MIN_BETS = 100             # a lean record smaller than this is not a sample
SEASONS = {'EPL': {'tune': '2024-25', 'holdout': '2025-26'}, 'MLS': {'tune': '2024', 'holdout': '2025'}}
# Chosen by `tune` on the tuning season and checked once on the holdout; see data/model/soccer-*.json.
PARAMS = {
    'EPL': {'halfLife': 180, 'ridge': 1.0, 'rho': 'fit', 'seasonCarry': 0.7, 'newcomerPool': 3, 'shotsBlend': 0.5},
    'MLS': {'halfLife': 90, 'ridge': 10.0, 'rho': 0.0, 'seasonCarry': 0.5, 'newcomerPool': 3, 'shotsBlend': 1.0},
}


# ------------------------------------------------------------------ time

def when(record):
    """A match's kickoff in UTC; midday on its date when the file gives no time (2016-17 to 2018-19)."""
    return _instant(record.get('kickoff'), record['date'])


@functools.lru_cache(maxsize=None)
def _instant(kickoff, day):
    return boxscores.instant(kickoff) if kickoff else datetime.fromisoformat(day + 'T12:00:00+00:00')


def refit_point(moment):
    """The last Tuesday or Friday 06:00 UTC at or before a kickoff."""
    day = moment.replace(hour=REFIT_HOUR, minute=0, second=0, microsecond=0)
    for back in range(8):
        candidate = day - timedelta(days=back)
        if candidate.weekday() in REFIT_WEEKDAYS and candidate <= moment:
            return candidate
    raise AssertionError('unreachable')


def season_year(season):
    return int(str(season)[:4])


def previous_season(league, season):
    return soccer_store.season_label(league, season_year(season) - 1)


# ------------------------------------------------------------------ arithmetic

def poisson(rate, top=MAX_GOALS):
    out, term = [], math.exp(-rate)
    for k in range(top + 1):
        out.append(term)
        term *= rate / (k + 1)
    return out


def tau(x, y, home_rate, away_rate, rho):
    """Dixon and Coles' low-score correction."""
    if x == 0 and y == 0:
        return 1 - home_rate * away_rate * rho
    if x == 0 and y == 1:
        return 1 + home_rate * rho
    if x == 1 and y == 0:
        return 1 + away_rate * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def score_grid(home_rate, away_rate, rho=0.0, top=MAX_GOALS):
    """P(home scores i, away scores j) for i, j in 0..top, summing to 1."""
    ph, pa = poisson(home_rate, top), poisson(away_rate, top)
    grid = [[ph[i] * pa[j] * max(tau(i, j, home_rate, away_rate, rho), 0.0) for j in range(top + 1)]
            for i in range(top + 1)]
    total = sum(map(sum, grid))
    return [[p / total for p in row] for row in grid]


def result_chances(grid):
    home = sum(p for i, row in enumerate(grid) for j, p in enumerate(row) if i > j)
    draw = sum(grid[i][i] for i in range(len(grid)))
    return {'home': home, 'draw': draw, 'away': max(0.0, 1 - home - draw)}


def total_chances(grid, line=2.5):
    over = sum(p for i, row in enumerate(grid) for j, p in enumerate(row) if i + j > line)
    push = sum(p for i, row in enumerate(grid) for j, p in enumerate(row) if i + j == line)
    return {'over': over, 'under': max(0.0, 1 - over - push), 'push': push}


def settle(margin, line):
    """(share of stake won, share of stake lost) for a side at an Asian handicap `line` whose own goal
    margin was `margin`. A quarter line is two half stakes on the lines a quarter either side:
    -0.25 is half on 0 and half on -0.5, so a draw loses half the stake and returns the other half."""
    if abs(line * 4 - round(line * 4)) > 1e-9:
        raise ValueError(f'{line} is not a quarter-goal line')
    if abs((line * 4) % 2 - 1) < 1e-9:  # quarter line
        low, high = settle(margin, line - 0.25), settle(margin, line + 0.25)
        return (low[0] + high[0]) / 2, (low[1] + high[1]) / 2
    value = margin + line
    return (1.0, 0.0) if value > 1e-9 else (0.0, 1.0) if value < -1e-9 else (0.0, 0.0)


def profit(margin, line, odds):
    """Profit per unit staked at decimal odds on a handicap bet."""
    won, lost = settle(margin, line)
    return won * (odds - 1) - lost


def handicap_chances(grid, line, side='home'):
    """A handicap bet's expected shares won (A) and lost (B), and its even-money chance A / (A + B),
    the number to set beside a de-vigged price. `line` is the handicap of `side`."""
    won = lost = 0.0
    for i, row in enumerate(grid):
        for j, p in enumerate(row):
            w, l = settle(i - j if side == 'home' else j - i, line)
            won, lost = won + p * w, lost + p * l
    return {'won': won, 'lost': lost, 'chance': won / (won + lost) if won + lost > 0 else 0.5}


def devig(odds):
    """Proportional de-vig: each 1/odds divided by their sum."""
    inverse = [1 / o for o in odds]
    total = sum(inverse)
    return [x / total for x in inverse]


def dnb_odds(side_odds, draw_odds):
    """Draw-no-bet replicated from 1X2 prices at one book: stake 1/draw on the draw and the rest on the
    side, and a draw returns the stake. Not a quoted price; arithmetic on two that were."""
    return side_odds * (draw_odds - 1) / draw_odds


def cholesky_solve(matrix, vector):
    """Solve A x = b for a symmetric positive-definite A."""
    n = len(vector)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        row_i = lower[i]
        for j in range(i + 1):
            row_j = lower[j]
            s = matrix[i][j] - sum(row_i[k] * row_j[k] for k in range(j))
            if i == j:
                if s <= 0:
                    raise ValueError('matrix is not positive definite')
                row_i[j] = math.sqrt(s)
            else:
                row_i[j] = s / row_j[j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (vector[i] - sum(lower[i][k] * y[k] for k in range(i))) / lower[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(lower[k][i] * x[k] for k in range(i + 1, n))) / lower[i][i]
    return x


# ------------------------------------------------------------------ fitting

class Ratings:
    """Fitted ratings as of one cutoff."""

    def __init__(self, mu, home, attack, defence, rho, centers, counts, games, through):
        self.mu, self.home, self.attack, self.defence, self.rho = mu, home, attack, defence, rho
        self.centers, self.counts, self.games, self.through = centers, counts, games, through

    def rating(self, team):
        """(attack, defence); an unseen club gets its prior, or the league average."""
        center = self.centers.get(team, (0.0, 0.0))
        return self.attack.get(team, center[0]), self.defence.get(team, center[1])

    def rates(self, home, away, neutral=False):
        (ah, dh), (aa, da) = self.rating(home), self.rating(away)
        edge = 0.0 if neutral else self.home
        return math.exp(self.mu + edge + ah - da), math.exp(self.mu + aa - dh)

    def predict(self, home, away, lines=(), neutral=False):
        """Expected goals, the score grid's markets, and the handicap at each home line in `lines`."""
        home_rate, away_rate = self.rates(home, away, neutral)
        grid = score_grid(home_rate, away_rate, self.rho)
        result, total = result_chances(grid), total_chances(grid, 2.5)
        out = {'homeRate': home_rate, 'awayRate': away_rate, 'home': result['home'], 'draw': result['draw'],
               'away': result['away'], 'over25': total['over'], 'under25': total['under'],
               'dnbHome': result['home'] / (result['home'] + result['away']),
               'handicap': {}, 'sparse': min(self.counts.get(home, 0), self.counts.get(away, 0)) < 3}
        for line in lines:
            if line is not None and line not in out['handicap']:
                out['handicap'][line] = {'home': handicap_chances(grid, line, 'home')['chance'],
                                         'away': handicap_chances(grid, -line, 'away')['chance']}
        return out


def weighted_rows(matches, cutoff, season, params):
    """(home, away, home goals, away goals, weight, shots) for matches before the cutoff worth counting."""
    rows = []
    carry, half_life, current = params.get('seasonCarry', 1.0), params['halfLife'], season_year(season)
    for match in matches:
        age = (cutoff - when(match)).total_seconds() / 86400
        if age <= 0:
            continue
        weight = 0.5 ** (age / half_life) * carry ** max(current - season_year(match['season']), 0)
        if weight >= MIN_WEIGHT:
            rows.append((match['home'], match['away'], match['homeGoals'], match['awayGoals'], weight,
                         match.get('shots')))
    return rows


def shot_values(rows):
    """Goals per shot on target and per shot off target, by weighted least squares over the rows given
    (both sides of every match with shots). None when too few matches carry shots."""
    xx = [[0.0, 0.0], [0.0, 0.0]]
    xy = [0.0, 0.0]
    used = 0
    for _, _, x, y, w, shots in rows:
        if not shots or 'homeTarget' not in shots or 'awayTarget' not in shots:
            continue
        used += 1
        for goals, total, target in ((x, shots['home'], shots['homeTarget']), (y, shots['away'], shots['awayTarget'])):
            features = (target, max(total - target, 0))
            for i in range(2):
                xy[i] += w * features[i] * goals
                for j in range(2):
                    xx[i][j] += w * features[i] * features[j]
    if used < 100:
        return None
    determinant = xx[0][0] * xx[1][1] - xx[0][1] * xx[1][0]
    if abs(determinant) < 1e-12:
        return None
    on = (xy[0] * xx[1][1] - xy[1] * xx[0][1]) / determinant
    off = (xx[0][0] * xy[1] - xx[1][0] * xy[0]) / determinant
    return max(on, 0.0), max(off, 0.0)


def targets(rows, blend):
    """What each side's rate is fitted to: goals, or `blend` x goals + (1 - blend) x shot-implied goals
    (goals per shot on and off target, fitted on the same rows) where the match has shots."""
    values = shot_values(rows) if blend < 1 else None
    out = []
    for h, a, x, y, w, shots in rows:
        tx, ty = x, y
        if values and shots and 'homeTarget' in shots and 'awayTarget' in shots:
            implied_home = values[0] * shots['homeTarget'] + values[1] * max(shots['home'] - shots['homeTarget'], 0)
            implied_away = values[0] * shots['awayTarget'] + values[1] * max(shots['away'] - shots['awayTarget'], 0)
            tx, ty = blend * x + (1 - blend) * implied_home, blend * y + (1 - blend) * implied_away
        out.append((h, a, tx, ty, w))
    return out


def fit_rho(rows, rate_of, bounds=RHO_BOUNDS, steps=60):
    """Dixon-Coles rho by golden-section search on the weighted low-score likelihood."""
    low_scores = [(x, y, w, *rate_of(h, a)) for h, a, x, y, w, *_ in rows if x <= 1 and y <= 1]
    if not low_scores:
        return 0.0

    def loglik(rho):
        return sum(w * math.log(max(tau(x, y, lh, la, rho), 1e-12)) for x, y, w, lh, la in low_scores)

    lo, hi = bounds
    ratio = (math.sqrt(5) - 1) / 2
    a, b = hi - ratio * (hi - lo), lo + ratio * (hi - lo)
    fa, fb = loglik(a), loglik(b)
    for _ in range(steps):
        if fa < fb:
            lo, a, fa = a, b, fb
            b = lo + ratio * (hi - lo)
            fb = loglik(b)
        else:
            hi, b, fb = b, a, fa
            a = hi - ratio * (hi - lo)
            fa = loglik(a)
    return (lo + hi) / 2


def fit(matches, cutoff, season, params, centers=None, warm=None, tolerance=1e-8, limit=50):
    """Ratings from the matches before `cutoff` (penalised weighted Poisson maximum likelihood).

    `centers` maps a club to the (attack, defence) its ridge pulls toward instead of zero; `warm` is an
    earlier fit to start from. Returns Ratings.
    """
    centers = centers or {}
    rows = weighted_rows(matches, cutoff, season, params)
    teams = sorted({team for h, a, *_ in rows for team in (h, a)})
    n = len(teams)
    position = {team: k for k, team in enumerate(teams)}
    size = 2 + 2 * n
    cells = defaultdict(lambda: [0.0, 0.0])  # (attacking side, defending side, home) -> [sum w*goals, sum w]
    for h, a, x, y, w in targets(rows, params.get('shotsBlend', 1.0)):
        for attacking, defending, home, scored in ((h, a, True, x), (a, h, False, y)):
            cell = cells[position[attacking], position[defending], home]
            cell[0] += w * scored
            cell[1] += w
    cells = [(att, dfn, home, s[0], s[1]) for (att, dfn, home), s in cells.items()]
    ridge = max(params['ridge'], 1e-6)
    target = [0.0, 0.0] + [centers.get(t, (0.0, 0.0))[0] for t in teams] + [centers.get(t, (0.0, 0.0))[1] for t in teams]
    counts = defaultdict(int)
    for match in matches:
        if when(match) < cutoff and match['season'] == season:
            counts[match['home']] += 1
            counts[match['away']] += 1
    if not rows:
        return Ratings(0.0, 0.0, {}, {}, 0.0, centers, dict(counts), 0, None)
    goals = sum(s for *_, s, _ in cells) or 1.0
    weight = sum(w for *_, w in cells) or 1.0
    theta = [math.log(max(goals / weight, 0.05)), 0.2] + target[2:]
    if warm:
        theta[0], theta[1] = warm.mu, warm.home
        for t, k in position.items():
            if t in warm.attack:
                theta[2 + k], theta[2 + n + k] = warm.attack[t], warm.defence[t]

    def loglik(values):
        total = 0.0
        for att, dfn, home, s, w in cells:
            eta = values[0] + (values[1] if home else 0.0) + values[2 + att] - values[2 + n + dfn]
            total += s * eta - w * math.exp(eta)
        return total - 0.5 * ridge * sum((values[j] - target[j]) ** 2 for j in range(2, size))

    current = loglik(theta)
    for _ in range(limit):
        gradient = [0.0] * size
        hessian = [[0.0] * size for _ in range(size)]
        for att, dfn, home, s, w in cells:
            columns = [(0, 1.0), (2 + att, 1.0), (2 + n + dfn, -1.0)] + ([(1, 1.0)] if home else [])
            eta = theta[0] + (theta[1] if home else 0.0) + theta[2 + att] - theta[2 + n + dfn]
            expected = w * math.exp(eta)
            residual = s - expected
            for i, si in columns:
                gradient[i] += si * residual
                row = hessian[i]
                for j, sj in columns:
                    row[j] += si * sj * expected
        for j in range(2, size):
            gradient[j] -= ridge * (theta[j] - target[j])
            hessian[j][j] += ridge
        hessian[0][0] += 1e-9
        hessian[1][1] += 1e-9
        step = cholesky_solve(hessian, gradient)
        scale, improved = 1.0, False
        while scale >= 1e-4:
            candidate = [t + scale * s for t, s in zip(theta, step)]
            value = loglik(candidate)
            if value >= current - 1e-12:
                theta, current, improved = candidate, value, True
                break
            scale /= 2
        if not improved or max(abs(s) for s in step) * scale < tolerance:
            break
    attack = {t: theta[2 + k] for t, k in position.items()}
    defence = {t: theta[2 + n + k] for t, k in position.items()}
    ratings = Ratings(theta[0], theta[1], attack, defence, 0.0, centers, dict(counts), len(rows),
                      max(when(m) for m in matches if when(m) < cutoff))
    rho = params.get('rho', 0.0)
    if rho == 'fit':
        ratings.rho = fit_rho(rows, lambda h, a: ratings.rates(h, a))
    elif rho:
        ratings.rho = float(rho)
    return ratings


def newcomer_centers(league, matches, season, params, cutoff):
    """(attack, defence) prior for each club new to the league this season, from a fit at the opening.

    Clubs that played last season but not this one went down; the newcomers start at their average.
    With none gone (MLS), the prior is the average of last season's weakest `newcomerPool` clubs.
    """
    this = {t for m in matches if m['season'] == season for t in (m['home'], m['away'])}
    last_season = previous_season(league, season)
    last = {t for m in matches if m['season'] == last_season for t in (m['home'], m['away'])}
    newcomers = this - last if last else set()
    if not newcomers:
        return {}, None
    opening = fit([m for m in matches if when(m) < cutoff], cutoff, season, {**params, 'rho': 0.0})
    gone = sorted(t for t in last - this if t in opening.attack)
    pool = gone or sorted((t for t in last if t in opening.attack),
                          key=lambda t: opening.attack[t] + opening.defence[t])[:params.get('newcomerPool', 3)]
    if not pool:
        return {}, None
    prior = (statistics.mean(opening.attack[t] for t in pool), statistics.mean(opening.defence[t] for t in pool))
    return {t: prior for t in newcomers}, {'from': pool, 'attack': round(prior[0], 4), 'defence': round(prior[1], 4),
                                          'newcomers': sorted(newcomers)}


# ------------------------------------------------------------------ walk-forward

def backtest(league, season, params, records):
    """Walk-forward forecasts for every stored match in `season`, each from a refit before its round."""
    records = sorted(records, key=when)
    times = [when(r) for r in records]
    games = [r for r in records if r['season'] == season]
    if not games:
        return []
    opening = refit_point(when(games[0]))
    centers, _ = newcomer_centers(league, records, season, params, opening)
    rows, model, current = [], None, None
    for game in games:
        cutoff = refit_point(when(game))
        if cutoff != current:
            past = records[:bisect.bisect_left(times, cutoff)]
            model, current = fit(past, cutoff, season, params, centers, warm=model), cutoff
        lines = [(game.get(k) or {}).get('ahLine') for k in ('close', 'open')]
        rows.append({'id': game['id'], 'season': season, 'kickoff': when(game).isoformat(), 'refit': cutoff.isoformat(),
                     'through': model.through.isoformat() if model.through else None,
                     'home': game['home'], 'away': game['away'],
                     'homeGoals': game['homeGoals'], 'awayGoals': game['awayGoals'],
                     'model': model.predict(game['home'], game['away'], lines),
                     **{k: game[k] for k in ('close', 'open', 'closeAvg', 'openAvg') if k in game}})
    return rows


# ------------------------------------------------------------------ scoring

def outcome_1x2(row):
    return 'home' if row['homeGoals'] > row['awayGoals'] else 'away' if row['homeGoals'] < row['awayGoals'] else 'draw'


def log_loss(chance):
    return -math.log(min(max(chance, 1e-12), 1.0))


def market_fair(row, timing, market):
    """The de-vigged price of a market at `timing` ('close' or 'open'), or None."""
    prices = row.get(timing) or {}
    if market == '1x2' and all(k in prices for k in ('home', 'draw', 'away')):
        return dict(zip(('home', 'draw', 'away'), devig([prices['home'], prices['draw'], prices['away']])))
    if market == 'total' and 'over25' in prices and 'under25' in prices:
        return dict(zip(('over', 'under'), devig([prices['over25'], prices['under25']])))
    if market == 'ah' and 'ahLine' in prices:
        return dict(zip(('home', 'away'), devig([prices['ahHome'], prices['ahAway']])))
    return None


def ours(row, market, timing='close'):
    m = row['model']
    if market == '1x2':
        return {'home': m['home'], 'draw': m['draw'], 'away': m['away']}
    if market == 'total':
        return {'over': m['over25'], 'under': m['under25']}
    if market == 'dnb':
        return {'home': m['dnbHome'], 'away': 1 - m['dnbHome']}
    line = (row.get(timing) or {}).get('ahLine')
    chances = m['handicap'].get(line) if line is not None else None
    if chances is None:
        chances = m['handicap'].get(str(line)) if line is not None else None
    return dict(chances) if chances else None


def fair(row, market, timing='close'):
    if market == 'dnb':
        x = market_fair(row, timing, '1x2')
        return {'home': x['home'] / (x['home'] + x['away']), 'away': x['away'] / (x['home'] + x['away'])} if x else None
    return market_fair(row, timing, market)


def accuracy(rows, market, calibration=None):
    """Log loss and Brier score of ours (raw, and calibrated when k is given) against the de-vigged close."""
    ll = {'ours': [], 'close': [], 'calibrated': []}
    brier = {'ours': [], 'close': [], 'calibrated': []}
    for row in rows:
        q = fair(row, market, 'close')
        p = ours(row, market, 'close')
        if not q or not p:
            continue
        if market == '1x2':
            actual = {k: 1.0 if k == outcome_1x2(row) else 0.0 for k in q}
        elif market == 'total':
            over = row['homeGoals'] + row['awayGoals'] > 2.5
            actual = {'over': 1.0 if over else 0.0, 'under': 0.0 if over else 1.0}
        else:
            continue
        variants = {'ours': p, 'close': q}
        if calibration is not None:
            variants['calibrated'] = {k: q[k] + calibration * (p[k] - q[k]) for k in q}
        for name, probs in variants.items():
            hit = next(k for k, v in actual.items() if v == 1.0)
            ll[name].append(log_loss(probs[hit]))
            brier[name].append(sum((probs[k] - actual[k]) ** 2 for k in actual))
    n = len(ll['ours'])
    if not n:
        return None
    out = {'n': n, 'logLoss': {k: round(statistics.mean(v), 5) for k, v in ll.items() if v},
           'brier': {k: round(statistics.mean(v), 5) for k, v in brier.items() if v}}
    diffs = [a - b for a, b in zip(ll['ours'], ll['close'])]
    out['oursMinusClose'] = interval(diffs)
    return out


def interval(values, draws=1000, seed=7):
    """Mean and a seeded 90% bootstrap interval."""
    if not values:
        return None
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(draws))
    return {'mean': round(statistics.mean(values), 5), 'interval90': [round(boots[int(0.05 * draws)], 5),
                                                                     round(boots[min(int(0.95 * draws), draws - 1)], 5)]}


def bet_price(row, market, side, timing, book):
    """Decimal price of a side at `timing` from the primary book ('primary') or the market average ('average')."""
    prices = row.get(timing if book == 'primary' else f'{timing}Avg') or {}
    if market == '1x2':
        return prices.get(side)
    if market == 'dnb':
        if all(k in prices for k in ('home', 'draw', 'away')):
            return dnb_odds(prices[side], prices['draw'])
        return None
    if market == 'total':
        return prices.get('over25' if side == 'over' else 'under25')
    if market == 'ah':
        # The average's handicap prices belong to the same line only when both name it.
        line = (row.get(timing) or {}).get('ahLine')
        if prices.get('ahLine') != line:
            return None
        return prices.get('ahHome' if side == 'home' else 'ahAway')
    return None


def bet_profit(row, market, side, odds, timing):
    """Profit per unit at decimal odds, settled on the final score."""
    hg, ag = row['homeGoals'], row['awayGoals']
    if market == '1x2':
        return odds - 1 if outcome_1x2(row) == side else -1.0
    if market == 'dnb':
        if hg == ag:
            return 0.0
        return odds - 1 if (hg > ag) == (side == 'home') else -1.0
    if market == 'total':
        return odds - 1 if (hg + ag > 2.5) == (side == 'over') else -1.0
    line = row[timing]['ahLine']
    return profit(hg - ag if side == 'home' else ag - hg, line if side == 'home' else -line, odds)


def leans(rows, market, timing, threshold, calibration=None):
    """Our side when our chance beats the de-vigged `timing` price by `threshold` points, one bet a match,
    settled at the primary book's price and at the market average's."""
    bets = []
    for row in rows:
        q, p = fair(row, market, timing), ours(row, market, timing)
        if not q or not p:
            continue
        if calibration is not None:
            p = {k: q[k] + calibration * (p[k] - q[k]) for k in q}
        side = max(q, key=lambda k: p[k] - q[k])
        edge = 100 * (p[side] - q[side])
        if edge < threshold:
            continue
        bet = {'id': row['id'], 'side': side, 'edge': edge}
        for book in ('primary', 'average'):
            odds = bet_price(row, market, side, timing, book)
            if odds:
                bet[book] = (odds, bet_profit(row, market, side, odds, timing))
        if 'primary' in bet:
            bets.append(bet)
    out = {'bets': len(bets), 'meanEdge': round(statistics.mean(b['edge'] for b in bets), 2) if bets else None}
    for book in ('primary', 'average'):
        priced = [b[book] for b in bets if book in b]
        if not priced:
            continue
        profits = [pr for _, pr in priced]
        won = sum(1 for pr in profits if pr > 1e-9)
        lost = sum(1 for pr in profits if pr < -1e-9)
        out[book] = {'n': len(priced), 'won': won, 'lost': lost, 'pushed': len(priced) - won - lost,
                     'units': round(sum(profits), 2), 'roi': round(100 * sum(profits) / len(priced), 2),
                     'meanOdds': round(statistics.mean(o for o, _ in priced), 3),
                     'roiInterval90': [round(100 * x, 2) for x in interval(profits)['interval90']]}
    return out


def calibrate(rows, market, steps=100, at=()):
    """k in [0, 1] maximising the likelihood of results under q + k * (ours - q), q the de-vigged close.

    `gain` is the log-likelihood the best k adds over the close alone (k = 0); `at` asks for the same
    gain at other values of k (1 is our raw chance), which is how a tuned k is checked on the holdout.

    The house form, 50% + k * (raw - 50%), is this with the market at 50%, where NFL spreads and totals
    sit. Soccer's 1X2 and 2.5 total are not priced at 50%, so the shrink is toward the price instead;
    on the Asian handicap, priced near 50%, the two agree.
    """
    data = []
    for row in rows:
        q, p = fair(row, market, 'close'), ours(row, market, 'close')
        if not q or not p:
            continue
        hg, ag = row['homeGoals'], row['awayGoals']
        if market == '1x2':
            data.append(((p[outcome_1x2(row)], q[outcome_1x2(row)], 1.0),))
        elif market == 'total':
            side = 'over' if hg + ag > 2.5 else 'under'
            data.append(((p[side], q[side], 1.0),))
        elif market == 'dnb':
            if hg != ag:
                side = 'home' if hg > ag else 'away'
                data.append(((p[side], q[side], 1.0),))
        elif market == 'ah':
            won, lost = settle(hg - ag, row['close']['ahLine'])
            terms = []
            if won:
                terms.append((p['home'], q['home'], won))
            if lost:
                terms.append((p['away'], q['away'], lost))
            if terms:
                data.append(tuple(terms))
    if not data:
        return None

    def loglik(k):
        return sum(weight * math.log(max(qq + k * (pp - qq), 1e-12)) for terms in data for pp, qq, weight in terms)

    best = max((i / steps for i in range(steps + 1)), key=loglik)
    base = loglik(0.0)
    out = {'k': best, 'n': len(data), 'gain': round(loglik(best) - base, 3)}
    if at:
        out['gainAt'] = {str(k): round(loglik(k) - base, 3) for k in at}
    return out


MARKETS = ('1x2', 'dnb', 'total', 'ah')


def evaluate(rows, calibration=None):
    """Everything the tuning file records about one season's walk-forward."""
    out = {'matches': len(rows), 'accuracy': {}, 'leans': {}}
    for market in ('1x2', 'total'):
        result = accuracy(rows, market, (calibration or {}).get(market))
        if result:
            out['accuracy'][market] = result
    for market in MARKETS:
        for timing in ('close', 'open'):
            for threshold in THRESHOLDS:
                result = leans(rows, market, timing, threshold)
                if result['bets']:
                    out['leans'].setdefault(market, {}).setdefault(timing, {})[str(threshold)] = result
    return out


# ------------------------------------------------------------------ tuning

GRID = {'halfLife': (45, 90, 180, 365, 730), 'ridge': (0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0),
        'shotsBlend': (1.0, 0.75, 0.5, 0.25), 'rho': (0.0, 'fit'), 'seasonCarry': (1.0, 0.7, 0.5, 0.3)}
BASE = {'halfLife': 365, 'ridge': 10.0, 'rho': 'fit', 'seasonCarry': 1.0, 'newcomerPool': 3, 'shotsBlend': 1.0}


def quick(rows):
    """The tuning objective alone, without the lean tables."""
    total = 0.0
    for market in ('1x2', 'total'):
        result = accuracy(rows, market)
        if result:
            total += result['logLoss']['ours']
    return total


def tune(league, records, log=print, season=None, grid=None):
    """Grid search on the tuning season, one stage at a time, each holding the others at their best:
    halfLife x ridge (with goals alone and with half shots where the file has shots), then shotsBlend,
    rho and seasonCarry, then halfLife x ridge once more. Each list starts with its simplest value
    (no shots, no rho, no extra season discount) and ties go to it."""
    season, grid = season or SEASONS[league]['tune'], grid or GRID
    has_shots = any(r.get('shots') for r in records if r['season'] == season)
    trials, cache = [], {}

    def run(params):
        key = json.dumps(params, sort_keys=True)
        if key not in cache:
            cache[key] = quick(backtest(league, season, params, records))
            trials.append({'params': dict(params), 'objective': round(cache[key], 6)})
            log(f'{league} {params}: {cache[key]:.5f}')
        return cache[key]

    def best_of(candidates):
        return min(((run(c), i, c) for i, c in enumerate(candidates)), key=lambda t: (round(t[0], 6), t[1]))[2]

    def square(center, blends):
        return [{**center, 'halfLife': h, 'ridge': r, 'shotsBlend': b}
                for b in blends for h in grid['halfLife'] for r in grid['ridge']]

    best = best_of(square(BASE, (1.0, 0.5) if has_shots else (1.0,)))
    for knob in ('shotsBlend', 'rho', 'seasonCarry'):
        if knob == 'shotsBlend' and not has_shots:
            continue
        best = best_of([{**best, knob: value} for value in grid[knob]])
    best = best_of([best] + square(best, (best['shotsBlend'],)))
    return best, trials


def store_state(league):
    path = soccer_store.store_path(league)
    lines = boxscores.read_lines(path)
    return {'file': str(path.relative_to(ROOT)), 'lines': len(lines), 'sha256': boxscores.digest(lines)}


def tuning_path(league):
    return MODEL_DIR / f'soccer-{league.lower()}.json'


def pick_threshold(evaluation, market, timing):
    """The threshold the tuning season liked best at the average price, among those with a sample."""
    table = evaluation['leans'].get(market, {}).get(timing, {})
    best = None
    for threshold, result in table.items():
        priced = result.get('average') or result.get('primary')
        if not priced or priced['n'] < MIN_BETS / 2:
            continue
        if best is None or priced['roi'] > best[1]:
            best = (threshold, priced['roi'])
    return best[0] if best else None


def run_tune(league, log=print, records=None, seasons=None, grid=None):
    """The tuning record: the grid's trials, the chosen knobs, the tuning season's walk-forward against the
    close, the calibration k per market and the lean threshold per market. The holdout is not read."""
    stored = records is None
    records = soccer_store.load(league) if stored else records
    seasons, grid = seasons or SEASONS[league], grid or GRID
    chosen, trials = tune(league, records, log, seasons['tune'], grid)
    rows = backtest(league, seasons['tune'], chosen, records)
    calibration = {m: calibrate(rows, m) for m in MARKETS}
    evaluation = evaluate(rows, {m: c['k'] for m, c in calibration.items() if c})
    thresholds = {m: {t: pick_threshold(evaluation, m, t) for t in ('close', 'open')} for m in MARKETS}
    history = sorted({r['season'] for r in records if season_year(r['season']) < season_year(seasons['tune'])})
    return {'league': league, 'version': VERSION, 'store': store_state(league) if stored else None,
            'objective': 'mean log loss of 1X2 plus over/under 2.5 (1X2 alone where the file has no totals)',
            'tuneSeason': seasons['tune'], 'holdoutSeason': seasons['holdout'], 'history': history,
            'grid': {k: list(v) for k, v in grid.items()}, 'trials': trials, 'chosen': chosen,
            'tuning': evaluation, 'calibration': calibration, 'thresholds': thresholds, 'looks': []}


def verdict(result):
    """Per market: does it clear the bar on the untouched season? A rule, not a feel, and not by itself a
    decision to publish (docs/SOCCER.md weighs the rest):

    - leans: at the threshold the tuning season chose, bets at the market average's price (what a
      typical book offered) return more than they cost over at least MIN_BETS bets, at the opening or
      the closing price;
    - calibration holds: the k fitted on the tuning season is above zero, and on the holdout our chance
      shrunk by that k predicts results better than the de-vigged close alone.
    """
    holdout, out = result['holdout'], {}
    for market in MARKETS:
        k = (result['calibration'].get(market) or {}).get('k')
        checks = {}
        for timing in ('open', 'close'):
            threshold = result['thresholds'][market][timing]
            table = holdout['evaluation']['leans'].get(market, {}).get(timing, {}).get(str(threshold)) if threshold else None
            priced = (table or {}).get('average')
            checks[timing] = {'threshold': threshold, 'bets': priced['n'] if priced else 0,
                              'roi': priced['roi'] if priced else None,
                              'roiInterval90': priced['roiInterval90'] if priced else None,
                              'passes': bool(priced and priced['n'] >= MIN_BETS and priced['roi'] > 0)}
        check = holdout.get('calibrationCheck', {}).get(market) or {}
        holds = bool(k and k > 0 and (check.get('gainAtTunedK') or 0) > 0)
        out[market] = {'k': k, 'calibrationHolds': holds, 'byTiming': checks,
                       'clearsBar': holds and any(c['passes'] for c in checks.values())}
    return out


def run_holdout(league, result, records=None):
    """The one look at the untouched season, with the tuned parameters and calibration."""
    stored = records is None
    records = soccer_store.load(league) if stored else records
    season = result['holdoutSeason']
    rows = backtest(league, season, result['chosen'], records)
    ks = {m: c['k'] for m, c in result['calibration'].items() if c}
    evaluation = evaluate(rows, ks)
    check = {}
    for market in MARKETS:
        tuned = ks.get(market)
        on_holdout = calibrate(rows, market, at=(1.0,) + ((tuned,) if tuned is not None else ()))
        if not on_holdout:
            continue
        check[market] = {'kTuned': tuned, 'kOnHoldout': on_holdout['k'], 'n': on_holdout['n'],
                         'gainAtTunedK': on_holdout['gainAt'].get(str(tuned)) if tuned is not None else None,
                         'gainAtRaw': on_holdout['gainAt']['1.0']}
    result = dict(result, holdout={'season': season, 'store': store_state(league) if stored else None,
                                   'evaluation': evaluation,
                                   'calibrationCheck': check,
                                   'calibratedLeans': {m: {t: leans(rows, m, t, float(th), ks.get(m))
                                                           for t, th in result['thresholds'][m].items() if th}
                                                       for m in MARKETS}})
    result['verdict'] = verdict(result)
    result['looks'] = result.get('looks', []) + [{'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                                  'season': season}]
    return result


def write(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')


# ------------------------------------------------------------------ live

def ratings_now(league, at=None, params=None, records=None):
    """The ratings a forecast made at `at` (default now) would use, for the season in play."""
    records = records if records is not None else soccer_store.load(league)
    at = at or datetime.now(timezone.utc)
    season = soccer_store.season_label(league, soccer_store.current_start_year(league, at.date()))
    params = params or PARAMS[league]
    games = sorted((r for r in records if r['season'] == season), key=when)
    centers = {}
    if games:
        centers, _ = newcomer_centers(league, records, season, params, refit_point(when(games[0])))
    return fit([r for r in records if when(r) < at], at, season, params, centers), season


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('predict')
    one.add_argument('league')
    one.add_argument('home')
    one.add_argument('away')
    one.add_argument('--line', type=float, action='append', default=[], help="the home side's handicap")
    for name in ('tune', 'holdout'):
        sub.add_parser(name).add_argument('league')
    args = parser.parse_args(argv)
    league = args.league.upper()
    if args.command == 'predict':
        ratings, season = ratings_now(league)
        unknown = [t for t in (args.home, args.away) if t not in ratings.attack and t not in ratings.centers]
        if unknown:
            sys.exit(f'No rating for {", ".join(unknown)}: clubs go by football-data names (data/soccer/teams.json).')
        forecast = ratings.predict(args.home, args.away, args.line)
        print(json.dumps({'league': league, 'season': season, 'version': VERSION, 'through': ratings.through.isoformat()
                          if ratings.through else None, **{k: round(v, 4) if isinstance(v, float) else v
                                                           for k, v in forecast.items()}}, indent=1, default=str))
        return
    path = tuning_path(league)
    if args.command == 'tune':
        result = run_tune(league)
        if path.exists():
            earlier = json.loads(path.read_text(encoding='utf-8'))
            result['looks'] = earlier.get('looks', [])
        write(path, result)
        print(json.dumps({'chosen': result['chosen'], 'calibration': result['calibration'],
                          'accuracy': result['tuning']['accuracy'], 'thresholds': result['thresholds']}, indent=1))
        return
    result = json.loads(path.read_text(encoding='utf-8'))
    if result.get('looks'):
        print(f'Note: {path.name} records {len(result["looks"])} earlier look(s) at the holdout; this one is added.')
    result = run_holdout(league, result)
    write(path, result)
    print(json.dumps({'accuracy': result['holdout']['evaluation']['accuracy'], 'verdict': result['verdict']}, indent=1))


if __name__ == '__main__':
    main()
