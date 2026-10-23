"""Dated, sourced operator role reviews; research only, never play admission.

An analyst minutes estimate is explicitly not a coach-announced restriction.
Existing price, roster, injury and historical-role holds always take precedence.
"""
import math
import statistics
from datetime import timedelta
from urllib.parse import urlsplit

import boxscores
import nba_capture


def current_role(quote, boxes, now):
    """Observed current-season rotation, not a claim about tonight's starters.

    Include DNPs for role checks; only played minutes enter the displayed
    workload. One appearance never becomes a confirmed expected-minutes number.
    """
    games = sorted({b['eventId']: b for b in boxes}.values(), key=lambda b: b['kickoff'])
    current, prior = [], []
    for b in games:
        if b.get('league', 'NBA') != 'NBA' or b.get('seasonType') != 2 or boxscores.instant(b['kickoff']) >= now:
            continue
        people = [p for p in b.get('players', []) if p.get('id') == quote['athleteId']]
        if len(people) != 1:
            continue
        p = people[0]
        if b['season'] == quote['season']:
            current.append(dict(p, date=b['kickoff'], source=b.get('source')))
        elif b['season'] == quote['season']-1 and p.get('team') == quote['team'] and not p.get('dnp'):
            prior.append(p)
    if not current:
        return {'games': 0, 'note': 'No current-season regular-season appearance recorded.'}, None
    if current[-1]['team'] != quote['team']:
        return {'games': 0, 'asOf': current[-1]['date']}, 'Current team changed; workload review needed'
    own = [p for p in current if p['team'] == quote['team']]
    recent = own[-3:]
    played = [p for p in recent if not p.get('dnp') and isinstance(p.get('stats', {}).get('min'), (int, float))
              and not isinstance(p['stats']['min'], bool) and math.isfinite(p['stats']['min'])
              and 0 < p['stats']['min'] <= 60]
    role = {'games': len(played), 'asOf': recent[-1]['date'], 'source': recent[-1].get('source'),
            'minutes': [p['stats']['min'] for p in played],
            'starts': sum(p['starter'] for p in played) if played and all(type(p.get('starter')) is bool for p in played) else None,
            'note': 'Observed minutes and starts, not a confirmed lineup or minutes limit.'}
    if played:
        role['medianMinutes'] = round(statistics.median(p['stats']['min'] for p in played), 1)
    if recent[-1].get('dnp'):
        return role, 'Did not play in latest game; current workload review needed'
    # A changed starting job is material even before five new appearances exist.
    old = [p['starter'] for p in prior[-5:] if type(p.get('starter')) is bool]
    new = [p['starter'] for p in played if type(p.get('starter')) is bool]
    if len(old) >= 3 and new and (all(old) and not any(new) or not any(old) and all(new)):
        return role, 'Starting role changed this season; current workload review needed'
    return role, None


def validate(row):
    for key in ('eventId', 'athleteId', 'team'):
        if not isinstance(row.get(key), str) or not row[key].isdigit():
            raise ValueError('Role review identity unavailable')
    if type(row.get('season')) is not int or row.get('kind') not in ('role-only', 'analyst-estimate', 'reported-minutes'):
        raise ValueError('Role review type unavailable')
    if boxscores.instant(row['checkedAt']) >= boxscores.instant(row['kickoff']):
        raise ValueError('Role review must precede kickoff')
    for key in ('headline', 'explanation'):
        if not isinstance(row.get(key), str) or not 1 <= len(row[key]) <= 500:
            raise ValueError('Role review explanation unavailable')
    if 'hold' in row and (not isinstance(row['hold'],str) or not 1 <= len(row['hold']) <= 240):
        raise ValueError('Invalid news role hold')
    sources = row.get('sources')
    if not isinstance(sources, list) or not 1 <= len(sources) <= 4:
        raise ValueError('Role review needs sources')
    for source in sources:
        url = urlsplit(source['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or not source.get('label'):
            raise ValueError('Invalid role source')
    minutes = row.get('minutes')
    if row['kind'] == 'role-only':
        if minutes is not None:
            raise ValueError('Role-only review cannot set minutes')
    elif (isinstance(minutes, bool) or not isinstance(minutes, (int, float))
          or not math.isfinite(minutes) or not 1 <= minutes <= 48):
        raise ValueError('Invalid reviewed minutes')


def record(row, now, root=nba_capture.STORE):
    validate(row)
    if not timedelta(0) <= now-boxscores.instant(row['checkedAt']) <= timedelta(hours=24):
        raise ValueError('Role review check is stale or future')
    return nba_capture.append_changed([row], root/'role-reviews',
                                     lambda r: (r['eventId'], r['athleteId']))


def reviews(root, now):
    folder = root/'role-reviews'
    if boxscores.verify(folder):
        raise ValueError('Role review integrity failure')
    latest = {}
    for path in sorted(folder.glob('*.jsonl')):
        for row in boxscores.read_store(path):
            validate(row)
            if boxscores.instant(row['checkedAt']) > now:
                continue
            key = (row['eventId'], row['athleteId'])
            if key not in latest or row['checkedAt'] > latest[key]['checkedAt']:
                latest[key] = row
    return latest


def apply(projection, quote, review, now):
    if not review:
        return projection, None, None
    if (any(review[k] != quote[k] for k in ('eventId', 'athleteId', 'team', 'season', 'kickoff'))
            or not timedelta(0) <= now-boxscores.instant(review['checkedAt']) <= timedelta(hours=24)
            or now >= boxscores.instant(review['kickoff'])):
        return projection, None, 'Current role review needs renewal'
    if review.get('hold'):
        return None, review, review['hold']
    if not projection or review['kind'] == 'role-only':
        return projection, review, None
    minutes = review['minutes']
    ratio = minutes/projection['minutes']
    updated = dict(projection, baselineValue=projection['value'], baselineMinutes=projection['minutes'],
                   minutes=minutes, value=round(minutes*projection['rate'], 1),
                   low=round(projection['low']*ratio, 1), high=round(projection['high']*ratio, 1),
                   minutesBasis=review['kind'], model='nba-minutes-rate-reviewed-v1')
    return updated, review, None
