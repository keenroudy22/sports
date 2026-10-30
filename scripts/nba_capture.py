"""Bounded NBA-only free ESPN collection. Mac owns pregame stores; hosted owns boxes."""
import json
import re
import time
import subprocess
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


def blocks_availability(status):
    """An explicit Available/Active designation is not an absence designation.

    Probable, questionable, unknown and every absence remain blocked. This does
    not clear a separate minutes restriction, role review or team-model hold.
    """
    if status in (None, ''):
        return False
    return not (isinstance(status, str) and status.strip().casefold() in ('available', 'active'))


class Budget:
    def __init__(self, requests=40, seconds=150, fetch=None, sleep=time.sleep, clock=time.monotonic):
        self.limit, self.deadline = min(requests, 60), clock() + min(seconds, 150)
        self.requests, self.errors = 0, 0
        self.fetch, self.sleep, self.clock = fetch, sleep, clock

    def __call__(self, url):
        return self._request(url, raw=False)

    def raw(self, url):
        return self._request(url, raw=True)

    def _request(self, url, raw=False):
        if self.requests >= self.limit or self.errors >= 3 or self.clock() >= self.deadline:
            raise TimeoutError('NBA free capture budget exhausted')
        allowed = (bool(re.fullmatch(r'https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_\d{4}-\d{2}-\d{2}_\d{2}_\d{2}(?:AM|PM)\.pdf', url))
                   if raw else url.startswith(('https://site.api.espn.com/', 'https://sports.core.api.espn.com/')))
        if not allowed:
            raise ValueError('NBA capture requires an approved free source')
        self.sleep(.5)
        if self.clock() >= self.deadline:
            raise TimeoutError('NBA capture timebox exhausted')
        self.requests += 1
        try:
            if self.fetch:
                result = self.fetch(url)
            else:
                with urlopen(url, timeout=max(1, min(20, self.deadline-self.clock()))) as response:
                    result = response.read(3_000_001) if raw else json.load(response)
            if raw and (not isinstance(result, bytes) or len(result)>3_000_000 or not result.startswith(b'%PDF-')):
                raise ValueError('Official injury report is not a bounded PDF')
            self.errors = 0
            return result
        except (OSError, ValueError):
            self.errors += 1
            raise


def append_changed(rows, root, key, *, keep_observations=False):
    problems = boxscores.verify(root)
    if problems:
        raise ValueError('; '.join(problems))
    latest = {key(r): r for p in root.glob('*.jsonl') for r in boxscores.read_store(p)}
    changed = []
    for row in rows:
        previous = latest.get(key(row), {})
        newer_observation = False
        if keep_observations:
            observed = boxscores.instant(row['retrievedAt'])
            if observed.tzinfo is None:
                raise ValueError('Quote observation needs a timezone')
            prior = boxscores.instant(previous['retrievedAt']) if previous else None
            if prior and observed < prior:
                continue  # A delayed response must not roll the latest quote backward.
            newer_observation = prior is not None and observed > prior
        if newer_observation or boxscores.content_hash(row) != boxscores.content_hash(previous):
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


def save_availability_snapshot(rows, season, retrieved, root):
    """Keep complete capture-time evidence, including removal from this feed.

    Changed-player history alone cannot reconstruct what the provider reported
    before a game. Absence from this snapshot is not an official clearance.
    """
    snapshot = dict(league='NBA',season=season,retrievedAt=retrieved,source=INJURIES,
        rows=rows,scope='Complete ESPN observation, not an official team submission or medical clearance')
    return append_changed([snapshot],Path(root)/'availability-snapshots',lambda r:r['retrievedAt'])


def availability_for_game(snapshot, game, now, max_hours=4):
    """Do not collapse a back-to-back team's reports across different fixtures."""
    import nba_official_availability as official
    if now<official.START:
        return snapshot.get('rows',[]),{}
    unknown={str(t['id']):'Official NBA availability unavailable' for t in game.get('teams',{}).values()}
    try:
        report=snapshot['official']
        if report.get('archive') or report.get('analysisOnly'):
            return snapshot.get('rows',[]),unknown
        if report.get('state')=='unavailable' or not timedelta(0)<=now-boxscores.instant(report['reportedAt'])<=timedelta(hours=max_hours):
            return snapshot.get('rows',[]),unknown
        expected_source='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+boxscores.instant(report['reportedAt']).astimezone(official.EASTERN).strftime('%Y-%m-%d_%I_%M%p')+'.pdf'
        if report.get('source')!=expected_source or report.get('season')!=game.get('season'):
            return snapshot.get('rows',[]),unknown
        observed=boxscores.instant(report['retrievedAt'])
        if not boxscores.instant(report['reportedAt'])<=observed<=now:return snapshot.get('rows',[]),unknown
        record=snapshot['gameAvailability'][str(game['providerId'])]
        if boxscores.instant(record['kickoff'])!=boxscores.instant(game['kickoff']):return snapshot.get('rows',[]),unknown
        return record['rows'],record['teamHolds']
    except (KeyError,TypeError,ValueError):
        return snapshot.get('rows',[]),unknown


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
        save_availability_snapshot(rows, season, stamp, root)
        snapshot={'retrievedAt':stamp,'season':season,'rows':rows,'source':INJURIES}
        import nba_official_availability as official
        if now>=official.START:
            official_attempt=clock()
            try:
                report=official.capture(budget,list(games.values()),root,official_attempt,clock=clock)
                report.update(league='NBA',season=season)
                append_changed([report],root/'official-availability',lambda r:r['retrievedAt'])
                snapshot.update(official=report,gameAvailability=official.merge(rows,report,list(games.values())))
            except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
                snapshot['official']=official.failure(error,official_attempt)
                result['officialAvailability']=snapshot['official']
                result['errors'].append('official-availability-unavailable')
        boxscores.write_json(root/'injuries-current.json', snapshot)
    except (OSError, ValueError, KeyError, TypeError):
        result['errors'].append('injuries-unavailable')
    for game in sorted(games.values(), key=lambda g:g['kickoff']):
        try:
            kickoff = boxscores.instant(game['kickoff'])
            if game['status']!='scheduled' or not game.get('timeConfirmed', True) or not now < kickoff <= now+timedelta(days=14):
                continue
            payload = budget(hoops_store.odds_url('NBA', game['providerId']))
            available = market_lab.books(payload)
            # Oct. 11 owner rule: NBA is a free ESPN/DraftKings lane. Do not
            # imply FanDuel coverage or spend prop credits that this feed does not provide.
            for book in ('DraftKings',):
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
                result['quotes'] += append_changed([row],root/'quotes',lambda r:(r['eventId'],r['book']),keep_observations=True)
        except (OSError, ValueError, KeyError, TypeError):
            result['errors'].append('quote-unavailable')
            if budget.errors >=3 or budget.requests>=budget.limit:
                break
    result['props'] = {'boards': 0, 'captured': 0, 'errors': 0, 'late': 0,
                       'orderContradictions': 0, 'requests': 0, 'reason': 'NBA free feed has no player props'}
    result['captured'] = 0
    result['requests'] = budget.requests
    result['retrievedAt'] = boxscores.stamp(clock())
    # Real scheduled-slot evidence, never backfilled from fixtures or another date.
    append_changed([{'league':'NBA','season':now.year+1,'slot':boxscores.stamp(now), 'scheduled':bool(scheduled),
                     'requests':budget.requests,'quotes':result['quotes'],'props':result['props'],
                     'errors':result['errors'],'retrievedAt':result['retrievedAt']}],root/'observations',lambda r:r['slot'])
    return result


if __name__ == '__main__':
    print(json.dumps(step()))
