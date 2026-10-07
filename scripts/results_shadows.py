"""Silent R0-R7 evidence snapshots. No feed calls and no public decisions.

Every row is append-only learning evidence. These observations never change a
play, card, post, record, gate, request budget or public payload.
"""
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import learning
import market_review

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = tuple(f'R{i}' for i in range(8))


def when(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def record(rows):
    out = {'graded': 0, 'win': 0, 'loss': 0, 'push': 0}
    values = []
    for row in rows:
        result = row.get('result')
        if result in ('win', 'loss', 'push'):
            out['graded'] += 1
            out[result] += 1
        if isinstance(row.get('clv'), (int, float)):
            values.append(float(row['clv']))
    out['closingLine'] = {
        'n': len(values), 'beat': sum(v > 0 for v in values), 'tied': sum(v == 0 for v in values),
        'lost': sum(v < 0 for v in values), 'interval': learning.interval(values),
    }
    return out


def loglik(rows, k):
    total = 0.0
    for row in rows:
        chance = min(max(0.5 + k * (row['raw'] - 0.5), 1e-4), 1 - 1e-4)
        total += math.log(chance if row['won'] else 1 - chance)
    return total


def fit_k(rows):
    return max((i / 100 for i in range(101)), key=lambda k: loglik(rows, k))


def calibration(props, policy):
    groups = defaultdict(list)
    for row in props:
        groups[f"{row.get('league')}/prop:{row.get('market')}"].append(row)
    out = []
    for market, group in sorted(groups.items()):
        train, test = market_review.split_dates(group)
        league = market.split('/', 1)[0]
        pooled = ((policy.get('calibration') or {}).get(f'{league}/prop') or {}).get('k')
        item = {'market': market, 'n': len(group), 'trainN': len(train), 'testN': len(test),
                'ready': len(group) >= 300, 'pooledK': pooled}
        if train and test:
            fitted = fit_k(train)
            item.update(k=fitted, heldOutMarket=round(loglik(test, fitted), 3),
                        heldOutPooled=round(loglik(test, pooled), 3) if isinstance(pooled, (int, float)) else None,
                        heldOutRaw=round(loglik(test, 1.0), 3))
            item['betterHeldOut'] = (item['heldOutPooled'] is not None
                                     and item['heldOutMarket'] > item['heldOutPooled'])
        out.append(item)
    return out


def quote_age(rows):
    observed = []
    for row in rows:
        quoted, decided = when(row.get('quotedAt')), when(row.get('decidedAt'))
        if quoted and decided:
            age = (decided - quoted).total_seconds() / 3600
            if age >= 0:
                observed.append((age, row))
    return {
        'available': len(observed),
        'missing': len(rows) - len(observed),
        'propsOver3h': record([row for age, row in observed if row.get('athleteId') and age > 3]),
        'gamesOver6h': record([row for age, row in observed if not row.get('athleteId') and age > 6]),
    }


def heavy_alternates(trends_dir):
    total = heavy = 0
    for path in sorted(Path(trends_dir).glob('*.json')):
        if path.name == 'index.json' or path.name.endswith('-milestones.json'):
            continue
        try:
            rows = json.loads(path.read_text(encoding='utf-8')).get('rows') or []
        except (OSError, ValueError, AttributeError):
            continue
        for row in rows:
            if row.get('kind') == 'alternate':
                total += 1
                if isinstance(row.get('odds'), (int, float)) and row['odds'] < -300:
                    heavy += 1
    return {'alternateRows': total, 'wouldHide': heavy, 'mainLinesChanged': 0, 'defaultChanged': False}


def snapshots(policy, raw_rows, distinct_rows, props, now, trends_dir=None):
    """One daily evidence row for every enabled proposal. All actions remain `observe`."""
    settings = policy.get('shadows') or {}
    day = now.astimezone(timezone.utc).date().isoformat()
    published = [r for r in distinct_rows if r.get('decision') == 'published']
    r1 = [r for r in distinct_rows if r.get('segment') == 'CFB/total']
    r2 = [r for r in published if r.get('segment') == 'NFL/total']
    evidence = {
        'R0': {'before': len(raw_rows), 'after': len(distinct_rows),
               'duplicatesRemoved': len(raw_rows) - len(distinct_rows)},
        'R1': {'retrospective': True, 'candidateTotals': len(r1), 'withQuoteTime': sum(bool(r.get('quotedAt')) for r in r1),
               'results': record(r1), 'successBar': {'forwardRows': 150, 'hitRate': .535, 'clvLowAbove': 0}},
        'R2': {'publicCardChanged': False, 'publishedNflTotals': record(r2),
               'reopenBar': {'graded': 40, 'hitRate': .524, 'clvLowAbove': 0}},
        'R3': {'publicCalibrationChanged': False, 'markets': calibration(props, policy), 'minimumPerMarket': 300},
        'R4': {'freshnessGateChanged': False, **quote_age(distinct_rows)},
        'R5': {'trendsDefaultChanged': False,
               **heavy_alternates(trends_dir or ROOT / 'site/data/app/trends')},
        'R6': {'requestsMade': 0, 'budgetChanged': False, 'publishedClosingLine': record(published)['closingLine'],
               'successBar': {'plays': 60, 'beatCloseRate': .5}},
        'R7': {'headlineChanged': False, 'publishedClosingLine': record(published)['closingLine']},
    }
    return [{'id': f'results-shadow:{day}:{proposal}', 'proposal': proposal,
             'at': learning.stamp(now), 'mode': 'silent', 'action': 'observe',
             'publicEffects': 0, 'meteredRequests': 0, 'evidence': evidence[proposal]}
            for proposal in PROPOSALS if settings.get(proposal) is True]


def append(rows, now, root=learning.STORE):
    season = now.year
    known = {row.get('id') for row in learning.read('shadow', season, root)}
    fresh = [row for row in rows if row.get('id') not in known]
    return learning.append('shadow', season, fresh, root)
