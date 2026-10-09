"""Bounded NBA-only free ESPN collection. Mac owns pregame stores; hosted owns boxes."""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

import boxscores
import espn_props
import hoops_store
import market_lab
import sports_refresh

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'nba-capture'
INJURIES = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'


class Budget:
    def __init__(self, requests=40, seconds=150, fetch=None, sleep=time.sleep, clock=time.monotonic):
        self.limit, self.deadline = min(requests, 60), clock() + min(seconds, 150)
        self.requests, self.errors = 0, 0
        self.fetch, self.sleep, self.clock = fetch, sleep, clock

    def __call__(self, url):
        if self.requests >= self.limit or self.errors >= 3 or self.clock() >= self.deadline:
            raise TimeoutError('NBA free capture budget exhausted')
        if not url.startswith(('https://site.api.espn.com/', 'https://sports.core.api.espn.com/')):
            raise ValueError('NBA capture requires free ESPN source')
        self.sleep(.5)
        if self.clock() >= self.deadline:
            raise TimeoutError('NBA capture timebox exhausted')
        self.requests += 1
        try:
            if self.fetch:
                result = self.fetch(url)
            else:
                with urlopen(url, timeout=max(1, min(20, self.deadline-self.clock()))) as response:
                    result = json.load(response)
            self.errors = 0
            return result
        except (OSError, ValueError):
            self.errors += 1
            raise


def append_changed(rows, root, key):
    problems = boxscores.verify(root)
    if problems:
        raise ValueError('; '.join(problems))
    latest = {key(r): r for p in root.glob('*.jsonl') for r in boxscores.read_store(p)}
    changed = []
    for row in rows:
        if boxscores.content_hash(row) != boxscores.content_hash(latest.get(key(row), {})):
            changed.append(row); latest[key(row)] = row
    for season in sorted({r['season'] for r in changed}):
        boxscores.append(root / f'nba-{season}.jsonl', [r for r in changed if r['season']==season])
    if changed:
        boxscores.write_json(root / 'ledger.json', boxscores.ledger(root))
    return len(changed)


def injuries(payload, season, retrieved):
    rows = []
    for team in payload.get('injuries', []):
        for injury in team.get('injuries', []):
            athlete = injury.get('athlete') or {}
            ids = {m[1] for link in athlete.get('links', []) if (m := re.search(r'/nba/player/(?:[^/]+/)?_/id/(\d+)(?:/|$)', link.get('href', '')))}
            athlete_id = str(athlete.get('id')) if athlete.get('id') else (next(iter(ids)) if len(ids)==1 else None)
            if not athlete_id or not team.get('id') or not injury.get('status'):
                continue
            rows.append({'league': 'NBA', 'season': season, 'athleteId': athlete_id,
                         'name': athlete.get('displayName'), 'team': str(team['id']),
                         'status': injury['status'], 'date': injury.get('date'),
                         'retrievedAt': retrieved, 'source': INJURIES})
    return rows


def step(now=None, root=STORE, budget=None, clock=lambda: datetime.now(timezone.utc), scheduled=False):
    now = now or clock(); budget = budget or Budget()
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    result = {'captured': 0, 'quotes': 0, 'injuries': 0, 'errors': [], 'requests': 0}
    games = {}
    dates = {sports_refresh.eastern_date(now), sports_refresh.eastern_date(now+timedelta(days=1))}
    # The approved opening slate is fetched daily before launch, within the same bounded budget.
    from datetime import date
    opening = date(2026, 10, 20)
    if sports_refresh.eastern_date(now) <= opening <= sports_refresh.eastern_date(now)+timedelta(days=14):
        dates.add(opening)
    sources = []
    try:
        for day in sorted(dates):
            url = sports_refresh.endpoint('NBA', day)
            games.update({g['id']: g for g in sports_refresh.normalize(budget(url), 'NBA', boxscores.stamp(now), url)})
            sources.append(url)
        stamp = boxscores.stamp(clock())
        boxscores.write_json(root/'slate.json', {'league':'NBA','retrievedAt':stamp,'games':list(games.values()),'sources':sources})
    except (OSError, ValueError, KeyError, TypeError):
        result['errors'].append('schedule-unavailable')
        games = {}  # keep last good snapshot on disk; never capture from a failed partial slate
    try:
        payload = budget(INJURIES)
        if not isinstance(payload.get('injuries'), list):
            raise ValueError('NBA injury coverage unavailable')
        season = (payload.get('season') or {}).get('year') or max((g['season'] for g in games.values()), default=now.year+1)
        stamp = boxscores.stamp(clock())
        rows = injuries(payload, season, stamp)
        expected = sum(len(t.get('injuries', [])) for t in payload['injuries'])
        if len(rows) != expected:
            raise ValueError('NBA injury identities incomplete')
        result['injuries'] = append_changed(rows, root/'injuries', lambda r:(r['athleteId'], r['team']))
        boxscores.write_json(root/'injuries-current.json', {'retrievedAt':stamp,'season':season,'rows':rows,'source':INJURIES})
    except (OSError, ValueError, KeyError, TypeError):
        result['errors'].append('injuries-unavailable')
    for game in sorted(games.values(), key=lambda g:g['kickoff']):
        try:
            kickoff = boxscores.instant(game['kickoff'])
            if game['status']!='scheduled' or not game.get('timeConfirmed', True) or not now < kickoff <= now+timedelta(days=14):
                continue
            payload = budget(hoops_store.odds_url('NBA', game['providerId']))
            available = market_lab.books(payload)
            for book in ('DraftKings','FanDuel'):
                if book not in available:
                    continue
                snapshot = market_lab.snapshot(available[book])
                retrieved = clock()
                if retrieved >= kickoff:
                    break
                row = {'league':'NBA','season':game['season'],'eventId':game['providerId'],
                       'kickoff':game['kickoff'],'seasonType':game['seasonType'],'book':book,
                       'current':snapshot,'retrievedAt':boxscores.stamp(retrieved),
                       'source':hoops_store.odds_url('NBA',game['providerId'])}
                result['quotes'] += append_changed([row],root/'quotes',lambda r:(r['eventId'],r['book']))
        except (OSError, ValueError, KeyError, TypeError):
            result['errors'].append('quote-unavailable')
            if budget.errors >=3 or budget.requests>=budget.limit:
                break
    result['props'] = espn_props.capture(list(games.values()), fetch=budget, clock=clock,
                                        seconds=max(0,budget.deadline-budget.clock()),root=root/'props', limit=10)
    result['captured'] = result['props']['captured']
    result['requests'] = budget.requests
    result['retrievedAt'] = boxscores.stamp(clock())
    # Real scheduled-slot evidence, never backfilled from fixtures or another date.
    append_changed([{'league':'NBA','season':now.year+1,'slot':boxscores.stamp(now), 'scheduled':bool(scheduled),
                     'requests':budget.requests,'quotes':result['quotes'],'props':result['props'],
                     'errors':result['errors'],'retrievedAt':result['retrievedAt']}],root/'observations',lambda r:r['slot'])
    return result


if __name__ == '__main__':
    print(json.dumps(step()))
