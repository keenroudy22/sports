"""Prospective NBA residual-probability study, never public bet admission.

The first natural capture freezes training and method. Exposed past games train;
only later physical pregame observations may test. No refit, extra feed or stake.
Game weights keep repeated books and players from inflating the sample.
"""
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, stdev
from pathlib import Path
from zoneinfo import ZoneInfo

import boxscores
import nba_capture

VERSION = 'nba-residual-market-shadow-v2'
BASELINE = 'nba-minutes-rate-v1'
STATS = ('pts', 'reb', 'ast')
MIN_TRAIN = 30
MIN_TEST = 30
MIN_DAYS = 5


def numeric(x):
    return type(x) in (int, float) and math.isfinite(x)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read(root):
    return [r for p in sorted(root.glob('*.jsonl')) for r in boxscores.read_store(p)]


def pairs(forecasts, outcomes, now):
    """Select first book/capture before consulting outcomes; exact saved terms only."""
    chosen, finals = {}, {}
    for r in forecasts:
        try:
            at, kick = boxscores.instant(r['retrievedAt']), boxscores.instant(r['kickoff'])
            if r['model'] != BASELINE or r['stat'] not in STATS or not at < kick or at > now:
                continue
            if not numeric(r['projection']['value']) or not numeric(r['line']):
                continue
            key = (r['eventId'], r['athleteId'], r['stat'])
            rank = (at, r['book'], r['id'])
            if key not in chosen or rank < chosen[key][0]:
                chosen[key] = (rank, r)
        except (KeyError, TypeError, ValueError):
            continue
    for o in outcomes:
        try:
            at = boxscores.instant(o['retrievedAt'])
            if at <= now and (o['id'] not in finals or at > finals[o['id']][0]):
                finals[o['id']] = (at, o)
        except (KeyError, TypeError, ValueError):
            continue
    result = []
    for _, r in chosen.values():
        item = finals.get(r['id'])
        if not item:
            continue
        at, o = item
        if (at < boxscores.instant(r['kickoff']) or not o.get('source') or not numeric(o.get('actual'))
                or o.get('forecastAt') != r['retrievedAt'] or o.get('model') != BASELINE
                or any(o.get(k) != r.get(k) for k in ('line', 'book', 'side', 'odds'))
                or o.get('projection') != r['projection']['value'] or o.get('result') not in ('hit', 'miss', 'push')):
            continue
        result.append((r, o))
    return result


def fit(training, stat, created):
    groups = defaultdict(list)
    for r, o in training:
        if r['stat'] == stat:
            groups[r['eventId']].append(o['actual'] - r['projection']['value'])
    if len(groups) < MIN_TRAIN:
        return None
    spec = dict(id=VERSION + ':' + stat, model=VERSION, stat=stat,
        createdAt=boxscores.stamp(created), retrievedAt=boxscores.stamp(created), season=created.year,
        trainingEvidence=[dict(forecastId=r['id'], forecastHash=digest(r), outcomeHash=digest(o))
            for r, o in training if r['stat'] == stat],
        trainingEvents=sorted(groups), residuals={k: sorted(v) for k, v in sorted(groups.items())},
        implementationHash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        marketAnchor=.5, probabilityAllowance=.02,
        method='Equal-game residual CDF, half-point lines, 50% fair-market anchor; no refit',
        minimumTestGames=MIN_TEST, minimumEasternDates=MIN_DAYS,
        admissionReady=False, analysisOnly=True)
    spec['specHash'] = digest(spec)
    return spec



def valid_spec(spec):
    """Method changes cannot borrow the earlier experiment's observations."""
    try:
        return (spec['model'] == VERSION and spec['stat'] in STATS
            and spec['implementationHash'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            and spec['specHash'] == digest({k:v for k,v in spec.items() if k != 'specHash'})
            and spec['marketAnchor'] == .5 and spec['probabilityAllowance'] == .02
            and spec['minimumTestGames'] == MIN_TEST and spec['minimumEasternDates'] == MIN_DAYS
            and len(set(spec['trainingEvents'])) >= MIN_TRAIN
            and set(spec['trainingEvents']) == set(spec['residuals'])
            and all(v and all(numeric(x) for x in v) for v in spec['residuals'].values()))
    except (KeyError, TypeError, ValueError):
        return False


def predict(row, spec, now):
    try:
        if not valid_spec(spec):
            return None
        at, kick, frozen = boxscores.instant(row['retrievedAt']), boxscores.instant(row['kickoff']), boxscores.instant(spec['createdAt'])
        if (not frozen <= at <= now < kick or row.get('hold') or row.get('model') != BASELINE
                or row['stat'] != spec['stat'] or row['eventId'] in spec['trainingEvents']):
            return None
        value, line = row['projection']['value'], row['line']
        over, under = row['over'], row['under']
        if not all(numeric(v) for v in (value, line, over, under)) or line % 1 != .5 or min(abs(over), abs(under)) < 100:
            return None
        implied = lambda p: 100 / (100 + p) if p > 0 else -p / (100 - p)
        a, b = implied(over), implied(under)
        if not .99 <= a + b <= 1.15:
            return None
        residuals = spec['residuals']
        empirical = mean(mean(value + e > line for e in group) for group in residuals.values())
        fair = a / (a + b)
        chance = .5 * empirical + .5 * fair
        return dict(id=':'.join((VERSION, row['stat'], row['eventId'], row['athleteId'])),
            season=row['season'], retrievedAt=boxscores.stamp(now), forecastAt=row['retrievedAt'],
            kickoff=row['kickoff'], eventId=row['eventId'], athleteId=row['athleteId'], stat=row['stat'],
            forecastId=row['id'], specHash=spec['specHash'], book=row['book'], line=line,
            over=over, under=under, chanceOver=chance, marketOver=fair,
            baselineProjection=value, baselineSide=row.get('side'), baselineOdds=row.get('odds'),
            admissionReady=False, analysisOnly=True)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def capture(root, now):
    """Called only by a natural real-feed capture; replay clocks cannot write proof."""
    forecasts, outcomes = read(root / 'player-forecasts'), read(root / 'player-outcomes')
    specs = {s['stat']: s for s in read(root / 'probability-specs') if s.get('model') == VERSION}
    training = pairs(forecasts, outcomes, now)
    new_specs = [s for stat in STATS if stat not in specs and (s := fit(training, stat, now))]
    nba_capture.append_changed(new_specs, root / 'probability-specs', lambda r: r['id'])
    specs.update({s['stat']: s for s in new_specs})
    old = {r['id'] for r in read(root / 'probability-forecasts')}
    rows = []
    # Earliest quote, deterministic book tie-break; never choose after outcomes.
    for r in sorted(forecasts, key=lambda r: (r.get('retrievedAt', ''), r.get('book', ''), r.get('id', ''))):
        spec = specs.get(r.get('stat'))
        p = predict(r, spec, now) if spec else None
        if p and p['id'] not in old:
            rows.append(p)
            old.add(p['id'])
    count = nba_capture.append_changed(rows, root / 'probability-forecasts', lambda r: r['id'])
    return dict(specifications=len(specs), recorded=count, admissionReady=False,
                review=review(root, now))


def shadow_price(p, y):
    """Choose side using frozen odds/probability only; raw-stat benchmark, not a bet."""
    choices = []
    for side, chance in (('over',p['chanceOver']), ('under',1-p['chanceOver'])):
        price = p[side]
        if not numeric(price) or abs(price) < 100:
            return None
        decimal = 1 + (price/100 if price > 0 else 100/-price)
        conservative = max(0, chance-.02)*decimal-1
        choices.append((conservative, side, decimal))
    edge, side, decimal = max(choices)
    if edge <= 0:
        return None
    won = bool(y) == (side == 'over')
    return dict(side=side, conservativeEV=edge, net=decimal-1 if won else -1)


def lower95(values):
    # Independent Eastern-day clusters, fixed normal approximation; not a
    # guarantee or a confidence interval for a single wager's probability.
    return mean(values)-1.96*stdev(values)/math.sqrt(len(values)) if len(values)>1 else None


def review(root, now):
    specs = {s['specHash']:s for s in read(root/'probability-specs') if valid_spec(s)}
    finals = {}
    for o in read(root/'player-outcomes'):
        try:
            at=boxscores.instant(o['retrievedAt'])
            if at<=now and (o['id'] not in finals or at>finals[o['id']][0]):
                finals[o['id']]=(at,o)
        except (KeyError,TypeError,ValueError):
            continue
    # Choose the first physical observation before examining a result. A later
    # book/player quote cannot replace a loss; one player/stat per game is one case.
    chosen={}
    for p in read(root/'probability-forecasts'):
        try:
            at=boxscores.instant(p['retrievedAt'])
            if at>now:continue
            key=(p['eventId'],p['athleteId'],p['stat'],p['specHash'])
            if key not in chosen or (at,p['id'])<chosen[key][0]:chosen[key]=((at,p['id']),p)
        except (KeyError,TypeError,ValueError):
            continue
    groups=defaultdict(lambda:defaultdict(list))
    for _,p in chosen.values():
        s=specs.get(p.get('specHash')); entry=finals.get(p.get('forecastId'))
        if not s or not entry:continue
        _,o=entry
        if not numeric(o.get('actual')) or not o.get('source'):continue
        try:
            if not boxscores.instant(s['createdAt'])<=boxscores.instant(p['forecastAt'])<=boxscores.instant(p['retrievedAt'])<boxscores.instant(p['kickoff'])<=boxscores.instant(o['retrievedAt'])<=now:continue
            if (p['eventId'] in s['trainingEvents'] or o.get('forecastAt')!=p['forecastAt']
                or o.get('line')!=p['line'] or o.get('book')!=p['book'] or o.get('model')!=BASELINE
                or o.get('projection')!=p['baselineProjection']
                or o.get('side')!=p['baselineSide'] or o.get('odds')!=p['baselineOdds']
                or not all(numeric(p.get(k)) and 0<p[k]<1 for k in ('chanceOver','marketOver'))):continue
            y=float(o['actual']>p['line'])
            expected='hit' if bool(y)==(p['baselineSide']=='over') else 'miss'
            if o.get('result')!=expected:continue
            groups[(p['stat'],p['specHash'])][p['eventId']].append((p,y))
        except (KeyError,TypeError,ValueError):continue
    result=[]
    for (stat,spec_hash),games in sorted(groups.items()):
        days=defaultdict(list); price_days=defaultdict(list); errors=[]; returns=[]
        calibration=[]
        for group in games.values():
            day=boxscores.instant(group[0][0]['kickoff']).astimezone(ZoneInfo('America/New_York')).date().isoformat()
            improvement=mean((p['marketOver']-y)**2-(p['chanceOver']-y)**2 for p,y in group)
            errors.append(improvement);days[day].append(improvement)
            calibration.append(mean(p['chanceOver']-y for p,y in group))
            priced=[shadow_price(p,y) for p,y in group]
            priced=[p['net'] for p in priced if p is not None]
            if priced:
                net=mean(priced);returns.append(net);price_days[day].append(net)
        error_lower=lower95([mean(v) for v in days.values()])
        price_lower=lower95([mean(v) for v in price_days.values()])
        holds=[]
        if len(games)<MIN_TEST:holds.append('Fewer than30 untouched test games')
        if len(days)<MIN_DAYS:holds.append('Fewer than5 independent Eastern dates')
        if error_lower is None or error_lower<=0:holds.append('Probability error improvement is unproven')
        if len(returns)<MIN_TEST or len(price_days)<MIN_DAYS:holds.append('Insufficient games/dates with frozen positive-price candidates')
        if price_lower is None or price_lower<=0:holds.append('Conservative frozen-price return is unproven')
        result.append(dict(stat=stat,specHash=spec_hash,games=len(games),easternDates=len(days),
            brierImprovement=mean(errors),brierImprovementLower95=error_lower,
            pricedGames=len(returns),pricedEasternDates=len(price_days),
            rawStatShadowReturn=mean(returns) if returns else None,rawStatReturnLower95=price_lower,
            meanProbabilityBias=mean(calibration),evidenceReady=not holds,evidenceHolds=holds,
            admissionReady=False,analysisOnly=True,
            hold='Research only; official book settlement and a reviewed prop publishing adapter remain required. Raw-stat returns are not settled bets.'))
    return result
