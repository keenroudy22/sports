"""Separate quarter research inputs. No forecast, admission or public settlement.

Sharp's props alias excludes period-prefixed markets. The October23 catalog and
live free-tier response verify 1st_quarter_player_points. Fetch that exact ID
inside the existing NBA allowance; do not invent a second-quarter endpoint.
"""
import re
from collections import defaultdict

import market_periods

REQUEST_MARKET = '1st_quarter_player_points'


def period_market(row):
    match = re.fullmatch(r'(1st|2nd)_quarter_(player_points)', str(row.get('market_type', '')))
    if not match:
        return None
    quarter = 1 if match[1] == '1st' else 2
    # A quarter in the market name never overrides contradictory metadata.
    for key in market_periods.FIELDS:
        value = row.get(key)
        if value is None or value == '':
            continue
        allowed = {str(quarter), f'q{quarter}', f'{quarter}q', f'quarter {quarter}',
                   f'{match[1]} quarter', 'first quarter' if quarter == 1 else 'second quarter'}
        if key == 'half' or isinstance(value, bool) or re.sub(r'[_-]+', ' ', str(value).lower().strip()) not in allowed:
            return None
    return quarter, match[2]


def fold(rows, games, rosters, now):
    import nba_player_props
    grouped = defaultdict(list)
    for raw in rows:
        scope = period_market(raw)
        if not scope:
            continue
        row = {k: v for k, v in raw.items() if k not in market_periods.FIELDS}
        row['market_type'] = scope[1]
        alternate = raw.get('is_alternate_line') is True
        row['is_alternate_line'] = False
        # Retain every explicitly priced rung, not just the nearest-even main.
        grouped[(scope[0], str(raw.get('line')), alternate)].append(row)
    quotes = []
    for (quarter, _, alternate), group in sorted(grouped.items()):
        paired, _ = nba_player_props.fold(group, games, rosters, now)
        quotes.extend(dict(r, quarter=quarter, kind='quarter-alternate' if alternate else 'quarter-main',
                           researchOnly=True) for r in paired)
    return quotes


def points(payload, box):
    """Quarter scoring only when every player's full-game points reconcile.

    Use official scoring participants and period numbers, never text-name
    guesses or full-game totals divided by four. OT participates in the
    reconciliation but is never assigned to Q1/Q2. Missing/ambiguous play data
    holds the whole game's quarter evidence. This does not establish quarter
    participation/void rules or minutes, so it cannot settle a sportsbook bet.
    """
    players = {p['id']: p for p in box['players'] if not p.get('dnp')}
    totals = {key: defaultdict(int) for key in players}
    seen, periods = {}, set()
    plays = payload.get('plays') or []
    if not plays:
        return {}, 'play-by-play unavailable'
    for play in plays:
        key = play.get('id')
        if not key or key in seen and seen[key] != play:
            return {}, 'missing or conflicting play identity'
        if key in seen:
            continue
        seen[key] = play
        quarter = (play.get('period') or {}).get('number')
        if type(quarter) is not int or not 1 <= quarter <= 20:
            return {}, 'period identity unavailable'
        periods.add(quarter)
        if not play.get('scoringPlay'):
            continue
        value = play.get('scoreValue')
        participants = play.get('participants') or []
        athlete = str((participants[0].get('athlete') or {}).get('id')) if participants else None
        if (type(value) is not int or value not in (1, 2, 3) or athlete not in players
                or str((play.get('team') or {}).get('id')) != players[athlete]['team']):
            return {}, 'scoring identity unavailable'
        totals[athlete][quarter] += value
    if not {1, 2, 3, 4} <= periods:
        return {}, 'incomplete period coverage'
    for athlete, player in players.items():
        if player['stats'].get('pts') != sum(totals[athlete].values()):
            return {}, 'play-by-play does not reconcile to final points'
    if sum(sum(p.values()) for p in totals.values()) != sum(t['score'] for t in box['teams'].values()):
        return {}, 'play-by-play does not reconcile to final score'
    return {athlete: {str(q): {'pts': totals[athlete][q]} for q in sorted(periods)} for athlete in players}, None


def compare(quote, box, side):
    """Exact-threshold research outcome; deliberately not a ticket settlement."""
    if (quote.get('quarter') not in (1, 2) or quote.get('stat') != 'pts' or side not in ('over', 'under')
            or str(box.get('eventId')).removeprefix('NBA-') != quote.get('eventId')
            or box.get('season') != quote.get('season') or box.get('seasonType') != 2
            or box.get('quarterEvidence', {}).get('status') != 'reconciled'
            or box.get('source') != 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+str(quote.get('eventId'))):
        return None
    import boxscores
    try:
        kickoff = boxscores.instant(box['kickoff'])
        if (boxscores.instant(quote['kickoff']) != kickoff
                or not boxscores.instant(quote['retrievedAt']) < kickoff < boxscores.instant(box['retrievedAt'])):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    people = [p for p in box.get('players', []) if p['id'] == quote.get('athleteId') and p['team'] == quote.get('team')]
    if len(people) != 1 or people[0].get('dnp'):
        return None
    value = people[0].get('quarters', {}).get(str(quote['quarter']), {}).get('pts')
    line = quote.get('line')
    if type(value) not in (int, float) or type(line) not in (int, float):
        return None
    import math
    if not math.isfinite(value) or not math.isfinite(line):
        return None
    return {'actual': value, 'result': 'push' if value == line else 'hit' if (value > line) == (side == 'over') else 'miss',
            'quarter': quote['quarter'], 'researchOnly': True}
