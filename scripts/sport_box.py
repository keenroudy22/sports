"""NBA final-summary extractor. Pure extraction; scheduled writer is not enabled.

Season and stage are retained so preseason/postseason cannot masquerade as
current regular-season history. Missing numbers stay absent; DNP is not zero.
"""
import boxscores

STATS = {'minutes': 'min', 'points': 'pts', 'rebounds': 'reb', 'assists': 'ast',
         'turnovers': 'tov', 'steals': 'stl', 'blocks': 'blk',
         'offensiveRebounds': 'oreb', 'defensiveRebounds': 'dreb',
         'fouls': 'pf', 'plusMinus': 'plusMinus'}
PAIRS = {'fieldGoalsMade-fieldGoalsAttempted': ('fgm', 'fga'),
         'threePointFieldGoalsMade-threePointFieldGoalsAttempted': ('fg3m', 'fg3a'),
         'freeThrowsMade-freeThrowsAttempted': ('ftm', 'fta')}
COMBINED = {'pra': ('pts', 'reb', 'ast'), 'pr': ('pts', 'reb'),
            'pa': ('pts', 'ast'), 'ra': ('reb', 'ast'), 'sb': ('stl', 'blk')}


def extract(payload, event_id, retrieved_at):
    header = payload.get('header') or {}
    if str(header.get('id')) != str(event_id):
        raise ValueError('NBA summary event mismatch')
    # ESPN's header league identity is mandatory; never ingest a football box.
    if (str((header.get('league') or {}).get('id')) != '46'
            or (header.get('league') or {}).get('slug') != 'nba'):
        raise ValueError('NBA summary league mismatch')
    season = header['season']
    competition = header['competitions'][0]
    status = (competition.get('status') or {}).get('type') or {}
    if not status.get('completed') or status.get('state') != 'post' or status.get('name') != 'STATUS_FINAL':
        raise ValueError('NBA box is not final')
    teams = {}
    for side in competition['competitors']:
        info = side['team']
        teams[str(info['id'])] = {'abbr': info.get('abbreviation'),
                                'home': side.get('homeAway') == 'home',
                                'score': boxscores.num(side.get('score'))}
    if len(teams) != 2:
        raise ValueError('NBA box needs two teams')
    players, seen = [], set()
    for team in (payload.get('boxscore') or {}).get('players', []):
        team_id = str(team['team']['id'])
        if team_id not in teams:
            raise ValueError('NBA box team mismatch')
        for group in team.get('statistics', []):
            keys = group.get('keys') or []
            if len(set(keys)) != len(keys):
                raise ValueError('Duplicate NBA stat keys')
            for row in group.get('athletes', []):
                athlete = row['athlete']
                athlete_id = str(athlete['id'])
                if athlete_id in seen:
                    raise ValueError('Duplicate NBA athlete')
                seen.add(athlete_id)
                pos = (athlete.get('position') or {}).get('abbreviation')
                stats = {}
                if not row.get('didNotPlay'):
                    values = row.get('stats') or []
                    if len(values) != len(keys):
                        raise ValueError('NBA stat columns do not match')
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
        raise ValueError('NBA box has no player evidence')
    return {'league': 'NBA', 'season': int(season['year']), 'seasonType': int(season['type']),
            'eventId': f'NBA-{event_id}', 'kickoff': competition['date'], 'teams': teams,
            'players': players, 'retrievedAt': retrieved_at, 'extractor': 1,
            'source': f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}'}
