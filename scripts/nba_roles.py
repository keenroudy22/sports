"""Dated, sourced operator role reviews; research only, never play admission.

An analyst minutes estimate is explicitly not a coach-announced restriction.
Existing price, roster, injury and historical-role holds always take precedence.
"""
import math
from datetime import timedelta
from urllib.parse import urlsplit

import boxscores
import nba_capture


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
