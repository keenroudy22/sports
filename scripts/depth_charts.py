"""Capture ESPN offensive depth charts only where a current injury makes them useful.

The injury report remains the authority for availability.  This file adds the
provider's ordering for QB/RB/FB/WR/TE so a game page can say who is next up
without guessing from a projection or an old box score.  It uses ESPN's public
team endpoint and makes no metered requests.

Usage: python scripts/depth_charts.py
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'site' / 'data'
OUTPUT = DATA / 'depth-charts.json'
# Long-term reserve players already have settled replacements.  Fetch a chart
# only for current game-week statuses where "who moves up?" can change tonight's read.
HARD = {'out', 'doubtful', 'suspension'}
SKILL = {'QB', 'RB', 'FB', 'WR', 'TE'}
POSITION_ORDER = {'qb': 0, 'rb': 1, 'fb': 2, 'wr1': 3, 'wr2': 4, 'wr3': 5, 'te': 6}


def when(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def targets(context, slate, now):
    """Upcoming NFL teams with a hard offensive injury, keyed by team id."""
    upcoming = set()
    for game in slate.get('games', []):
        if game.get('league') != 'NFL' or game.get('state') == 'post':
            continue
        try:
            kickoff = when(game.get('kickoff'))
        except (TypeError, ValueError):
            continue
        if now - timedelta(hours=6) <= kickoff <= now + timedelta(days=8):
            upcoming.update(str(game.get(side, {}).get('id')) for side in ('home', 'away'))
    teams = ((context.get('leagues') or {}).get('NFL') or {}).get('teams') or {}
    return {team: data for team, data in teams.items() if str(team) in upcoming and any(
        str(p.get('status', '')).lower() in HARD and str(p.get('position', '')).upper() in SKILL
        for p in data.get('players', []))}


def normalize(payload, now, source):
    if not isinstance(payload.get('depthchart'), list) or not payload.get('team', {}).get('id'):
        raise ValueError('Provider did not supply a team depth chart')
    offense = next((unit for unit in payload['depthchart']
                    if {'qb', 'rb', 'te'} <= set((unit.get('positions') or {}).keys())), None)
    if not offense:
        raise ValueError('Provider did not supply an offensive depth chart')
    positions = []
    for key, block in (offense.get('positions') or {}).items():
        if key not in POSITION_ORDER:
            continue
        players = []
        for order, athlete in enumerate(block.get('athletes') or [], 1):
            if not athlete.get('id') or not athlete.get('displayName'):
                continue
            players.append({'id': str(athlete['id']), 'name': athlete['displayName'], 'order': order})
        if players:
            group = 'WR' if key.startswith('wr') else key.upper()
            positions.append({'key': key, 'label': block.get('position', {}).get('abbreviation', group),
                              'group': group, 'players': players})
    if not positions:
        raise ValueError('Provider depth chart had no offensive skill positions')
    positions.sort(key=lambda row: POSITION_ORDER[row['key']])
    team = payload['team']
    return {'name': team.get('displayName'), 'abbr': team.get('abbreviation'), 'status': 'ok',
            'checkedAt': now, 'lastAttemptAt': now, 'source': source, 'positions': positions}


def refresh(previous, context, slate, fetch, now):
    moment = when(now) if isinstance(now, str) else now
    stamp = moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    old = previous.get('teams') or {}
    out = {}
    for team, data in targets(context, slate, moment).items():
        api = f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/depthcharts'
        try:
            row = normalize(fetch(api), stamp, api)
            if row.get('abbr'):
                row['source'] = f"https://www.espn.com/nfl/team/depth/_/name/{row['abbr'].lower()}"
            out[str(team)] = row
        except (OSError, ValueError, KeyError, TypeError) as error:
            prior = old.get(str(team), {})
            out[str(team)] = {**prior, 'status': 'failed', 'lastAttemptAt': stamp,
                              'error': type(error).__name__, 'positions': prior.get('positions', [])}
    return {'updatedAt': stamp, 'coverage': 'ESPN offensive depth charts for upcoming teams with a hard skill-position injury.',
            'teams': out}


def main():
    previous = json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else {}
    context = json.loads((DATA / 'research-context.json').read_text(encoding='utf-8'))
    slate = json.loads((DATA / 'slate.json').read_text(encoding='utf-8'))

    def fetch(url):
        with urlopen(url, timeout=25) as response:
            return json.load(response)

    now = datetime.now(timezone.utc)
    result = refresh(previous, context, slate, fetch, now)
    temporary = OUTPUT.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    temporary.replace(OUTPUT)
    print({'teams': len(result['teams']), 'status': {k: v['status'] for k, v in result['teams'].items()}})


if __name__ == '__main__':
    main()
