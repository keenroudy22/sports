"""Basketball final-summary extractor and bounded hosted scheduled writer.

Season and stage are retained so preseason/postseason cannot masquerade as
current regular-season history. Missing numbers stay absent; DNP is not zero.
"""
import boxscores

LEAGUES = {
    'NBA': {'id': '46', 'slug': 'nba'},
    'CBB': {'id': '41', 'slug': 'mens-college-basketball'},
}

STATS = {'minutes': 'min', 'points': 'pts', 'rebounds': 'reb', 'assists': 'ast',
         'turnovers': 'tov', 'steals': 'stl', 'blocks': 'blk',
         'offensiveRebounds': 'oreb', 'defensiveRebounds': 'dreb',
         'fouls': 'pf', 'plusMinus': 'plusMinus'}
PAIRS = {'fieldGoalsMade-fieldGoalsAttempted': ('fgm', 'fga'),
         'threePointFieldGoalsMade-threePointFieldGoalsAttempted': ('fg3m', 'fg3a'),
         'freeThrowsMade-freeThrowsAttempted': ('ftm', 'fta')}
COMBINED = {'pra': ('pts', 'reb', 'ast'), 'pr': ('pts', 'reb'),
            'pa': ('pts', 'ast'), 'ra': ('reb', 'ast'), 'sb': ('stl', 'blk')}


def extract(payload, event_id, retrieved_at, league='NBA'):
    league = str(league).upper()
    spec = LEAGUES.get(league)
    if not spec:
        raise ValueError('Unsupported basketball league')
    header = payload.get('header') or {}
    if str(header.get('id')) != str(event_id):
        raise ValueError(f'{league} summary event mismatch')
    # ESPN's header league identity is mandatory; never ingest another sport.
    if (str((header.get('league') or {}).get('id')) != spec['id']
            or (header.get('league') or {}).get('slug') != spec['slug']):
        raise ValueError(f'{league} summary league mismatch')
    season = header['season']
    competition = header['competitions'][0]
    status = (competition.get('status') or {}).get('type') or {}
    if not status.get('completed') or status.get('state') != 'post' or status.get('name') != 'STATUS_FINAL':
        raise ValueError(f'{league} box is not final')
    teams = {}
    for side in competition['competitors']:
        info = side['team']
        teams[str(info['id'])] = {'abbr': info.get('abbreviation'),
                                'home': side.get('homeAway') == 'home',
                                'score': boxscores.num(side.get('score'))}
    if len(teams) != 2:
        raise ValueError(f'{league} box needs two teams')
    players, seen = [], set()
    for team in (payload.get('boxscore') or {}).get('players', []):
        team_id = str(team['team']['id'])
        if team_id not in teams:
            raise ValueError(f'{league} box team mismatch')
        for group in team.get('statistics', []):
            keys = group.get('keys') or []
            if len(set(keys)) != len(keys):
                raise ValueError(f'Duplicate {league} stat keys')
            for row in group.get('athletes', []):
                athlete = row['athlete']
                athlete_id = str(athlete['id'])
                if athlete_id in seen:
                    raise ValueError(f'Duplicate {league} athlete')
                seen.add(athlete_id)
                pos = (athlete.get('position') or {}).get('abbreviation')
                stats = {}
                if not row.get('didNotPlay'):
                    values = row.get('stats') or []
                    if len(values) != len(keys):
                        raise ValueError(f'{league} stat columns do not match')
                    for key, value in zip(keys, values):
                        if key in STATS:
                            parsed = boxscores.num(value)
                            if key == 'minutes' and ':' in str(value):
                                seconds = boxscores.seconds(value)
                                parsed = seconds / 60 if seconds is not None else None
                            if parsed is not None:
                                stats[STATS[key]] = parsed
                        elif key in PAIRS:
                            made, attempted = boxscores.pair(value)
                            if made is not None and made <= attempted:
                                stats.update(zip(PAIRS[key], (made, attempted)))
                    for key, parts in COMBINED.items():
                        if all(p in stats for p in parts):
                            stats[key] = sum(stats[p] for p in parts)
                players.append({'id': athlete_id, 'name': athlete.get('displayName'),
                                'team': team_id, 'pos': pos,
                                'group': {'PG': 'G', 'SG': 'G', 'G': 'G', 'SF': 'F',
                                          'PF': 'F', 'F': 'F', 'C': 'C'}.get(pos),
                                'starter': bool(row.get('starter')), 'dnp': bool(row.get('didNotPlay')),
                                'stats': stats})
    if not players:
        raise ValueError(f'{league} box has no player evidence')
    result = {'league': league, 'season': int(season['year']), 'seasonType': int(season['type']),
            'eventId': f'{league}-{event_id}', 'kickoff': competition['date'], 'teams': teams,
            'players': players, 'retrievedAt': retrieved_at, 'extractor': 2,
            'source': f"https://site.api.espn.com/apis/site/v2/sports/basketball/{spec['slug']}/summary?event={event_id}"}
    if league != 'NBA':
        return result
    import nba_quarters
    quarters, hold = nba_quarters.points(payload, result)
    result['quarterEvidence'] = {'status': 'held' if hold else 'reconciled', 'reason': hold,
                                 'scope': 'points only; no minutes or quarter participation/void rule'}
    for player in players:
        if player['id'] in quarters:
            player['quarters'] = quarters[player['id']]
    import nba_quarter_workload
    workload, workload_hold = nba_quarter_workload.extract(payload, result)
    result['quarterWorkloadEvidence'] = {
        'status': 'held' if workload_hold else 'reconciled', 'reason': workload_hold,
        'method': 'play-by-play lineup reconstruction reconciled to final box minutes',
        'scope': 'observed workload only; not expected minutes, a void policy or ticket settlement'}
    for player in players:
        if player['id'] in workload:
            for quarter, values in workload[player['id']].items():
                player.setdefault('quarters', {}).setdefault(quarter, {}).update(values)
    return result


def cbb_capture_order(games, history, saved, now):
    """Give upcoming teams comparable recent-game coverage within the request cap."""
    from collections import defaultdict
    from datetime import timedelta

    horizon = now + timedelta(days=2)
    upcoming = sorted((game for game in games if game.get('status') == 'scheduled'
                       and game.get('kickoff') and now < boxscores.instant(game['kickoff']) <= horizon),
                      key=lambda game: (game['kickoff'], game['id']))
    team_order = {}
    for game in upcoming:
        for side in ('away', 'home'):
            team = (game.get('teams', {}).get(side) or {}).get('id')
            if team and game.get('season') is not None:
                team_order.setdefault((game['season'], str(team)), len(team_order))

    by_team = defaultdict(list)
    for row in history:
        for side in ('away', 'home'):
            team = (row['season'], str((row.get(side) or {}).get('id')))
            if team in team_order and len(by_team[team]) < 5:
                by_team[team].append(str(row['eventId']))

    priority = []
    for team, events in by_team.items():
        remaining = [event for event in events if f'CBB-{event}' not in saved]
        covered = len(events) - len(remaining)
        priority.extend((covered + position, team_order[team], event)
                        for position, event in enumerate(remaining))
    return list(dict.fromkeys(event for _, _, event in sorted(priority)))


def refresh(root=None, fetch=None, now=None, limit=20, league='NBA'):
    """Hosted scheduled-only bounded writer: current finals then recent regular boxes."""
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    import hoops_store
    import nba_capture
    league = str(league).upper()
    spec = LEAGUES.get(league)
    if not spec:
        raise ValueError('Unsupported basketball league')
    project = Path(__file__).resolve().parents[1]
    root = Path(root) if root is not None else project/'data'/'sport-box'
    now = now or datetime.now(timezone.utc)
    budget = nba_capture.Budget(requests=min(limit,60),seconds=150,fetch=fetch)
    problems = boxscores.verify(root)
    if problems:
        raise ValueError('; '.join(problems))
    old = {r['eventId']:r for p in root.glob('*.jsonl') for r in boxscores.read_store(p)}
    if league == 'NBA':
        slate = nba_capture.STORE/'slate.json'
        games = json.loads(slate.read_text()).get('games',[]) if slate.exists() else []
        final_ids = [str(g['providerId']) for g in games if g['status']=='final']
    else:
        slate = project/'site/data/sports.json'
        try:
            games = json.loads(slate.read_text())['leagues']['CBB']['games']
        except (OSError, ValueError, KeyError):
            games = []
        final_ids = [str(g['id']).removeprefix('CBB-') for g in games if g.get('status')=='final']
    history = sorted((r for r in hoops_store.load(league) if r['type']==2),key=lambda r:r['kickoff'],reverse=True)
    priority = cbb_capture_order(games, history, old, now) if league == 'CBB' else []
    final_ids = priority + final_ids + [r['eventId'] for r in history]
    result={'captured':0,'errors':0,'requests':0}
    for event in dict.fromkeys(final_ids):
        saved=old.get(f'{league}-{event}')
        # One genuine post-final recheck, 24 hours later; immutable prefix remains intact.
        if saved and (saved.get('rechecked') or (now-boxscores.instant(saved['retrievedAt'])).total_seconds()<86400):
            continue
        try:
            url=f"https://site.api.espn.com/apis/site/v2/sports/basketball/{spec['slug']}/summary?event={event}"
            row=extract(budget(url),event,boxscores.stamp(datetime.now(timezone.utc)),league)
            if saved:
                row['rechecked']=True
            result['captured'] += nba_capture.append_changed([row],root,lambda r:r['eventId'],prefix=league.lower())
        except (OSError, ValueError, KeyError, TypeError):
            result['errors']+=1
        if budget.requests>=budget.limit or budget.errors>=3 or budget.clock()>=budget.deadline:
            break
    result['requests']=budget.requests
    return result


if __name__ == '__main__':
    import json
    print(json.dumps({'NBA':refresh(limit=20,league='NBA'),
                      'CBB':refresh(limit=40,league='CBB')}))
