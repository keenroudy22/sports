"""Prospective owner-approved stakes and shared game-day exposure. No network calls."""
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

VERSION = '2026-10-23-half-unit-shared-cap'
EFFECTIVE = datetime.fromisoformat('2026-10-23T17:40:00+00:00')
EASTERN = ZoneInfo('America/New_York')
OWNER_UNIT = 25  # Private Climb dollar-to-exposure conversion; never rescale old results.


def active(now):
    return now >= EFFECTIVE


def instant(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def expected(pick):
    if pick.get('stakingPolicy') == VERSION:
        return 1 if pick.get('lane') == 'chef_pick' else .5
    return 2 if pick.get('lane') == 'chef_pick' else 1


def apply(pick, now):
    if active(now) and not (pick.get('legs') or pick.get('parlayType')):
        pick.update(stakingPolicy=VERSION)
        pick['riskUnits'] = expected(pick)
    return pick


def day(pick, games):
    times = [instant(pick.get('kickoff'))]
    times += [instant(games.get(key, {}).get('kickoff')) for key in pick.get('gameIds') or []]
    times = [value for value in times if value]
    return min(times).astimezone(EASTERN).date() if times else None


def units(pick):
    climb = pick.get('parlayType') == 'ladder'
    value = ((pick.get('ladder') or {}).get('stake') if climb else pick.get('riskUnits', 1))
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        return None
    return float(value) / OWNER_UNIT if climb else float(value)


def limit(on, games):
    # Eight eligible-sport games is the existing definition of a large slate.
    count = sum(g.get('league') in ('NFL', 'CFB', 'NBA') and day(g, {}) == on for g in games.values())
    return 5 if on.weekday() in (5, 6) or count >= 8 else 3


def check(candidate, ctx):
    if not active(ctx.now):
        return None
    games = {**ctx.games, **getattr(ctx, 'risk_games', {})}
    on = day(candidate, games)
    if on is None:
        return 'shared exposure: missing game day'
    rows = {**getattr(ctx, 'risk_external', {}), **ctx.first}
    used = 0
    day_rows=[]
    for key, row in rows.items():
        if key == candidate.get('id') or day(row, games) != on:
            continue
        # Settlements/expired quotes NEVER replenish the day's budget.
        if row.get('_pendingRelease') and (row.get('held') or row.get('withdrawn')):
            continue
        value = units(row)
        if value is None:
            return f'shared exposure: stake unknown for {key}'
        used += value
        day_rows.append(row)
    value = units(candidate)
    ceiling = limit(on, games)
    if value is None:
        return 'shared exposure: candidate stake unknown'
    if used + value > ceiling + 1e-9:
        return f'shared exposure: {used:g}u reserved + {value:g}u exceeds {ceiling:g}u on {on}'
    # Once NBA joins the ordinary card, its separate ledger must not create a
    # second straight allowance beside football's existing five/eight ceiling.
    import nba_pick_policy
    def league(row):
        return row.get('league') or games.get((row.get('gameIds') or [None])[0],{}).get('league')
    def straight(row):
        return (league(row) in ('NFL','CFB','NBA') and not row.get('legs')
                and not row.get('parlayType') and not row.get('personalTicket')
                and not row.get('historicalImport'))
    if (nba_pick_policy.active(ctx.now) and straight(candidate)
            and (league(candidate)=='NBA' or any(league(r)=='NBA' for r in day_rows))):
        maximum=8 if ceiling==5 else 5
        count=sum(straight(r) for r in day_rows)
        if count>=maximum:
            return f'shared exposure: {count} straights already reserved; daily straight-count cap is {maximum}'
    return None


def external(root, now):
    """Read other lanes once when constructing a live/rehearsal context."""
    root = Path(root)
    rows, games = {}, {}
    def read(path, fallback):
        return json.loads(path.read_text()) if path.exists() else fallback
    for path in (root / 'data/nba-trial').glob('*.jsonl'):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get('type') == 'publish' and (instant(row.get('publishedAt')) or now) <= now:
                rows[row['id']] = row
    for row in read(root / 'data/community.json', {'tickets': []}).get('tickets', []):
        # Owner-supplied already-placed tickets consume exposure, even before social delivery.
        rows[row['id']] = dict(row, riskUnits=row.get('riskUnits'))
    sports = read(root / 'site/data/sports.json', {})
    for league, block in sports.get('leagues', {}).items():
        if league == 'NBA':
            for game in block.get('games', []):
                games['NBA-' + str(game['id'])] = dict(game, league='NBA')
    return rows, games
