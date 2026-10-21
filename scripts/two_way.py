"""Autopilot's bounded two-way weekly learning (owner, 2026-10-11).

Only clean, deduplicated candidate rows count. A signal must repeat on two
consecutive weekly runs before it changes anything. Every change carries an
undo key and evidence; this module cannot edit the record or a published play.
"""
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import learning
import pricing

BLOCKING_RULES = {
    'price_sanity', 'role_sanity', 'injury', 'injury_gate', 'qb_available',
    'cross_book', 'gap_sanity', 'broken_price', 'started', 'stale_price',
}
SHADOW_LANES = {'NFL/spread', 'NFL/moneyline', 'NFL/total', 'upset', 'NBA/trial', 'soccer/trial'}
MIN_TRUST_N = 8
RESEARCH_ORDER = ('prep', 'season', 'upset', 'matchup', 'end-zone')


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def week_key(moment):
    year, week, _ = moment.isocalendar()
    return f'{year}-W{week:02d}'


def previous_week(key):
    try:
        year, week = key.split('-W')
        monday = datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=timezone.utc)
        return week_key(monday - timedelta(days=7))
    except (TypeError, ValueError):
        return None


def state(policy):
    raw = policy.setdefault('twoWay', {})
    for key in ('pending', 'segments', 'promotions', 'reasons'):
        if not isinstance(raw.get(key), dict):
            raw[key] = {}
    if not isinstance(raw.get('researchOrder'), list):
        raw['researchOrder'] = []
    return raw


def clean(row):
    rules = {str(rule).lower().replace('-', '_') for rule in row.get('rules') or []}
    if row.get('result') not in ('win', 'loss', 'push', 'void'):
        return False
    if not isinstance(row.get('odds'), (int, float)) or abs(row['odds']) < 100:
        return False
    if rules & BLOCKING_RULES or any('role' in rule or ('price' in rule and 'bar' not in rule) for rule in rules):
        return False
    gap = row.get('gap')
    return not isinstance(gap, (int, float)) or abs(gap) < 25


def distinct(rows):
    chosen = {}
    ordered = sorted((r for r in rows if clean(r)), key=lambda r: (str(r.get('decidedAt') or ''), str(r.get('id') or '')))
    for row in ordered:
        games = tuple(row.get('gameIds') or ())
        key = (row.get('segment'), games[0] if games else row.get('id'),
               row.get('direction') or row.get('side'), row.get('athleteId'))
        old = chosen.get(key)
        if old is None or row.get('decision') == 'published' and old.get('decision') != 'published':
            chosen[key] = row
    return list(chosen.values())


def outcome(row):
    if row.get('result') == 'win':
        return pricing.payout(int(row['odds']))
    return -1.0 if row.get('result') == 'loss' else 0.0


def summary(rows):
    values = [outcome(row) for row in rows]
    needs = [pricing.break_even(int(row['odds'])) for row in rows]
    wins = sum(row.get('result') == 'win' for row in rows)
    decided = sum(row.get('result') in ('win', 'loss') for row in rows)
    clvs = [float(row['clv']) for row in rows if isinstance(row.get('clv'), (int, float))]
    interval = learning.interval(values, level=.80) if values else None
    return {'n': len(rows), 'wins': wins, 'losses': sum(row.get('result') == 'loss' for row in rows),
            'roi': round(statistics.fmean(values), 4) if values else None, 'roi80': interval,
            'hitRate': round(wins / decided, 4) if decided else None,
            'need': round(statistics.fmean(needs), 4) if needs else None,
            'clv': round(statistics.fmean(clvs), 3) if clvs and 2 * len(clvs) >= len(rows) else None,
            'clvN': len(clvs)}


def signal(key, kind, segment, direction, value, evidence, sentence):
    return {'key': key, 'kind': kind, 'segment': segment, 'direction': direction,
            'value': value, 'evidence': evidence, 'sentence': sentence}


def signals(policy, rows):
    current = state(policy)
    by_segment = defaultdict(list)
    for row in distinct(rows):
        if row.get('segment'):
            by_segment[row['segment']].append(row)
    found = []
    for segment, sample in sorted(by_segment.items()):
        evidence = summary(sample)
        n, roi = evidence['n'], evidence['roi']
        saved = current['segments'].get(segment) or {}
        trust = float(saved.get('trust', 1.0))
        if n >= MIN_TRUST_N and roi is not None:
            target = min(1.25, max(.75, 1 + 2 * roi * n / (n + 150)))
            step = min(.05, abs(target - trust))
            if step >= .005:
                direction = 1 if target > trust else -1
                value = round(trust + direction * step, 3)
                found.append(signal(f'trust:{segment}', 'trust', segment, direction, value, evidence,
                                    f'{segment} trust {trust:.2f} to {value:.2f}'))
        floor = float(saved.get('gapFloor', 0.0))
        if n >= 50 and evidence['hitRate'] is not None and evidence['need'] is not None:
            if evidence['hitRate'] <= evidence['need'] - .07 and evidence['clv'] is not None and evidence['clv'] <= 0 and floor < 10:
                found.append(signal(f'gap:{segment}', 'gap', segment, 1, min(10.0, floor + 2), evidence,
                                    f'{segment} gap floor +2 points'))
            elif evidence['hitRate'] >= evidence['need'] and floor > 0:
                found.append(signal(f'gap:{segment}', 'gap', segment, -1, max(0.0, floor - 2), evidence,
                                    f'{segment} gap floor -2 points'))
        paused = bool(saved.get('paused'))
        upper = (evidence.get('roi80') or {}).get('high')
        if not paused and n >= 60 and roi is not None and roi <= -.10 and upper is not None and upper < 0 \
                and evidence['clv'] is not None and evidence['clv'] <= 0:
            found.append(signal(f'pause:{segment}', 'pause', segment, 1, True, evidence,
                                f'Pause {segment}; research and shadow continue'))
        if paused:
            ghost = summary([r for r in sample if r.get('decision') == 'refused'][-40:])
            if ghost['n'] >= 40 and ghost['hitRate'] is not None and ghost['need'] is not None \
                    and ghost['hitRate'] >= ghost['need'] and ghost['clv'] is not None and ghost['clv'] > 0:
                found.append(signal(f'pause:{segment}', 'pause', segment, -1, False, ghost,
                                    f'Restore {segment} at a raised bar'))
        if segment in SHADOW_LANES and not current['promotions'].get(segment):
            forward = [r for r in sample if r.get('decision') == 'refused'][-30:]
            ghost = summary(forward)
            lower = learning.interval([1.0 if r.get('result') == 'win' else 0.0 for r in forward], level=.80)
            if ghost['n'] >= 30 and ghost['clv'] is not None and ghost['clv'] > 0 and lower \
                    and ghost['need'] is not None and lower['low'] >= ghost['need']:
                found.append(signal(f'promote:{segment}', 'promote', segment, 1, True, ghost,
                                    f'Promote {segment} for 30 plays at a +2 point bar'))
    reason_rows = defaultdict(list)
    for row in distinct(rows):
        for reason in row.get('reasons') or row.get('planReasons') or []:
            if isinstance(reason, dict) and reason.get('type') in learning.REASON_KINDS:
                reason_rows[reason['type']].append(row)
    for kind, sample in sorted(reason_rows.items()):
        evidence = summary(sample)
        old = float((policy.get('reasonWeights') or {}).get(kind, 1.0))
        target = old
        if evidence['n'] >= 80 and evidence['roi'] is not None and evidence['roi'] <= -.15:
            target = 0.0
        elif evidence['n'] >= 60 and evidence['roi'] is not None:
            target = round(min(1.5, max(.5, 1 + 2 * evidence['roi'])), 2)
        if target != old:
            found.append(signal(f'reason:{kind}', 'reason', f'reason/{kind}',
                                1 if target > old else -1, target, evidence,
                                f'{kind} reason weight {old:.2f} to {target:.2f}'))
    return found


def research_signal(policy, log_book, grades):
    """Rank mature research families by outcomes first and engagement second.

    A family needs eight posted cards and eight graded rows. Missing views or
    grades hold the existing fallback order instead of turning unknown into 0.
    """
    posts = defaultdict(list)
    for row in (log_book or {}).get('posts', []):
        key = str(row.get('id') or '')
        if not key.startswith('research:'):
            continue
        kind = key.split(':', 2)[1]
        metrics = row.get('metrics') or {}
        views = metrics.get('impressions') or metrics.get('views') or 0
        if not views:
            continue
        likes = metrics.get('reactions') if metrics.get('reactions') is not None else metrics.get('likes') or 0
        replies = metrics.get('comments') or 0
        public = ' '.join(str(v or '') for v in (row.get('text'), row.get('caption'))).lower()
        if '@playbook' in public and replies:
            replies -= 1
        acts = likes + replies + sum(metrics.get(name) or 0 for name in ('reposts', 'quotes', 'clicks'))
        posts[kind].append(1000 * acts / views)
    outcomes = defaultdict(list)
    for row in grades or []:
        kind = row.get('type') or row.get('researchType')
        if not kind and str(row.get('id') or '').startswith('research:'):
            kind = str(row['id']).split(':', 2)[1]
        result = row.get('result')
        if kind and (result in ('win', 'loss') or isinstance(row.get('hit'), bool)):
            outcomes[str(kind)].append(1 if result == 'win' or row.get('hit') is True else 0)
    eligible = [kind for kind in RESEARCH_ORDER if len(posts[kind]) >= 8 and len(outcomes[kind]) >= 8]
    if len(eligible) < 2:
        return None
    ranked = sorted(eligible, key=lambda kind: (-statistics.fmean(outcomes[kind]),
                                                -statistics.fmean(posts[kind]), RESEARCH_ORDER.index(kind)))
    old = list(state(policy).get('researchOrder') or RESEARCH_ORDER)
    target = list(old)
    slots = [i for i, kind in enumerate(old) if kind in eligible]
    for index, kind in zip(slots, ranked):
        target[index] = kind
    if target == old:
        return None
    evidence = {kind: {'posts': len(posts[kind]), 'graded': len(outcomes[kind]),
                       'hitRate': round(statistics.fmean(outcomes[kind]), 4),
                       'perThousand': round(statistics.fmean(posts[kind]), 2)} for kind in eligible}
    return signal('research-order', 'research_order', 'research', 1, target, evidence,
                  f"Research fallback order {' > '.join(target)}")


def apply_signal(policy, item, now):
    current = state(policy)
    segment = current['segments'].setdefault(item['segment'], {})
    before = None
    if item['kind'] == 'trust':
        before, segment['trust'] = float(segment.get('trust', 1.0)), item['value']
    elif item['kind'] == 'gap':
        before, segment['gapFloor'] = float(segment.get('gapFloor', 0.0)), item['value']
    elif item['kind'] == 'pause':
        before, segment['paused'] = bool(segment.get('paused')), bool(item['value'])
        if item['value'] is False:
            segment['promotionBar'] = max(2.0, float(segment.get('promotionBar', 0.0)))
    elif item['kind'] == 'promote':
        before, current['promotions'][item['segment']] = False, {'at': stamp(now), 'first30Bar': 2.0}
    elif item['kind'] == 'reason':
        kind = item['segment'].split('/', 1)[1]
        weights = policy.setdefault('reasonWeights', {})
        before, weights[kind] = float(weights.get(kind, 1.0)), item['value']
    elif item['kind'] == 'research_order':
        before, current['researchOrder'] = list(current.get('researchOrder') or RESEARCH_ORDER), list(item['value'])
    change = {'at': stamp(now), 'engine': 'two-way', 'key': item['key'], 'undoKey': item['key'],
              'segment': item['segment'], 'knob': f"twoWay.{item['kind']}", 'from': before, 'to': item['value'],
              'why': item['sentence'], 'evidence': item['evidence']}
    policy.setdefault('history', []).append(change)
    return change


def step(policy, rows, now, dry=False, log_book=None, research_grades=None):
    found = signals(policy, rows)
    research = research_signal(policy, log_book, research_grades)
    if research:
        found.append(research)
    if os.environ.get('KEENROUDY_TWO_WAY_LEARNING', '1') == '0' or dry:
        return found, []
    current = state(policy)
    this_week, previous = week_key(now), previous_week(week_key(now))
    active = {item['key']: item for item in found}
    applied = []
    for key in list(current['pending']):
        if key not in active:
            del current['pending'][key]
    for item in found:
        old = current['pending'].get(item['key']) or {}
        if old.get('direction') == item['direction'] and old.get('week') == previous:
            applied.append(apply_signal(policy, item, now))
            current['pending'].pop(item['key'], None)
        elif old.get('week') != this_week or old.get('direction') != item['direction']:
            current['pending'][item['key']] = {'week': this_week, 'direction': item['direction'],
                                                'firstSeenAt': stamp(now), 'sentence': item['sentence']}
    return found, applied


def trust(policy, segment):
    value = ((policy or {}).get('twoWay') or {}).get('segments', {}).get(segment or '', {}).get('trust', 1.0)
    return min(1.25, max(.75, float(value))) if isinstance(value, (int, float)) else 1.0


def gap_floor(policy, segment):
    value = ((policy or {}).get('twoWay') or {}).get('segments', {}).get(segment or '', {}).get('gapFloor', 0.0)
    return min(10.0, max(0.0, float(value))) if isinstance(value, (int, float)) else 0.0


def paused(policy, segment):
    return ((policy or {}).get('twoWay') or {}).get('segments', {}).get(segment or '', {}).get('paused') is True


def promoted(policy, segment):
    """A shadow lane is promoted only by the confirmed two-week learner."""
    return bool(((policy or {}).get('twoWay') or {}).get('promotions', {}).get(segment or ''))
