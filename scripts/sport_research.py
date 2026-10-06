"""Read-only public view of saved basketball trials. No forecasts, requests or posts are created."""
import math
from datetime import datetime, timezone

import paper


def when(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('A saved trial must have a timezone')
    return parsed


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def phase(row):
    value = str(row.get('seasonType') or '').lower()
    return 'playoffs' if value == '3' or 'post' in value or 'playoff' in value else 'regular'


def record_of(rows, now):
    record = dict(win=0, loss=0, push=0)
    for row in rows:
        if row.get('lean') is True and row.get('result') in record:
            try:
                if when(row['kickoff']) <= when(row['gradedAt']) <= now:
                    record[row['result']] += 1
            except (KeyError, TypeError, ValueError, AttributeError):
                pass
    return record


def build(now=None, rows=None):
    now = now or datetime.now(timezone.utc)
    rows = paper.joined() if rows is None else rows
    valid = {}
    for row in sorted(rows, key=lambda r: str(r.get('capturedAt') or '')):
        try:
            captured, kickoff = when(row['capturedAt']), when(row['kickoff'])
            if not captured < kickoff or captured > now or row.get('league') not in paper.LEAGUES:
                continue
            if not row.get('gameId') or not number(row.get('ours')) or not number(row.get('line')):
                continue
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        valid.setdefault((row['league'], row['gameId']), row)
    leagues = {}
    for league in paper.LEAGUES:
        mine = [row for row in valid.values() if row['league'] == league]
        record = record_of(mine, now)
        upcoming = []
        for row in mine:
            if when(row['kickoff']) > now and not row.get('result'):
                upcoming.append({key: row.get(key) for key in
                                 ('gameId', 'season', 'seasonType', 'kickoff', 'home', 'away', 'line', 'capturedAt', 'sparse')}
                                | {'projection': row['ours']})
        grouped = {}
        for row in mine:
            if not isinstance(row.get('season'), int):
                continue
            grouped.setdefault((row['season'], phase(row)), []).append(row)
        seasons = [{'season': season, 'phase': stage, 'recorded': len(items), 'record': record_of(items, now)}
                   for (season, stage), items in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]), reverse=True)]
        leagues[league] = {'recorded': len(mine), 'record': record,
                           'seasons': seasons, 'upcoming': sorted(upcoming, key=lambda r: r['kickoff'])[:12]}
    return {'generatedAt': now.isoformat(timespec='seconds'), 'scope': 'paper-trials-only', 'leagues': leagues}
