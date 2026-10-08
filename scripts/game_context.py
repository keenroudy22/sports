"""Read-only game context for the college slate and explained model differences.

Every number comes from the existing forecast, slate, stored box scores, the stored NWS forecast or captured
lines. These fields organize research; they do not admit a play or change a grade. Public sentences are built
from templates here so code supplies every number (owner, 2026-10-07, items 28 and 30).
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
from pathlib import Path
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo('America/New_York')
FRESH = timedelta(hours=4)
ROOT = Path(__file__).resolve().parents[1]
CONFERENCES = ROOT / 'data' / 'team-conferences-cfb.json'
CARD_TEXT = 220
STALE_TEXT = 'The book line is older than four hours; check a current price.'
TIER_WORD = {'competitive': 'Competitive', 'lean': 'Lean', 'mismatch': 'Mismatch', 'blowout': 'Blowout'}


def _time(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fresh(value, now):
    then = _time(value)
    return bool(then and timedelta(0) <= now - then <= FRESH)


def _fmt(value):
    return f'{value:g}'


def _tier(spread):
    if spread is None:
        return None
    gap = abs(spread)
    return 'competitive' if gap <= 7 else 'lean' if gap < 14 else 'mismatch' if gap < 21 else 'blowout'


def _window(kickoff):
    at = _time(kickoff)
    if not at:
        return None
    hour = at.astimezone(EASTERN).hour
    return 'night' if hour >= 19 else 'afternoon' if hour >= 15 else 'noon'


@lru_cache(maxsize=1)
def stored_conferences(path=str(CONFERENCES)):
    """{team id: conference short name} from the dated ESPN standings table; empty when the file is absent."""
    try:
        table = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    names = {key: (value or {}).get('short') or (value or {}).get('name') for key, value in (table.get('conferences') or {}).items()}
    return {str(team): names.get(str(conf)) for team, conf in (table.get('teams') or {}).items() if names.get(str(conf))}


def _conference(game, side, conferences):
    team = game.get(side) or {}
    if team.get('conference'):
        return team['conference']
    if game.get('league') != 'CFB':
        return None
    table = stored_conferences() if conferences is None else conferences
    return table.get(str(team.get('id')))


def _same_line_pair(rows, market, now):
    """A priced pair at one exact line and book, not two unrelated quotes."""
    sides = {}
    for row in rows:
        if row.get('market') != market or row.get('state') != 'open' or row.get('roleSuspect') \
                or row.get('priceSuspect') or not _fresh(row.get('observedAt'), now) \
                or _number(row.get('odds')) is None:
            continue
        key = (row.get('book'), row.get('line'))
        side = str(row.get('direction') or row.get('side') or '').lower()
        sides.setdefault(key, set()).add(side)
    needed = {'over', 'under'} if market == 'total points' else {'home', 'away'}
    return any(needed <= found for found in sides.values())


def plain_gap(card, model, book_margin, spread, fresh):
    """One sentence on the strength gap and what it means for sides, totals and props."""
    if not fresh or model is None or book_margin is None:
        return 'The book line is older than four hours; check a current spread.' if spread is not None else None
    if abs(model) <= 3 and abs(book_margin) <= 3:
        return (f'Even matchup by my numbers (gap {_fmt(abs(model))}) and the book is close ({_fmt(abs(book_margin))}): '
                'sides and totals are live here.')
    leader = card['home']['name'] if model >= 0 else card['away']['name']
    book_leader = card['home']['name'] if book_margin >= 0 else card['away']['name']
    joiner = 'and the book has them' if leader == book_leader else f'but the book has {book_leader}'
    text = f'{leader} is {_fmt(abs(model))} points better by my numbers {joiner} by {_fmt(abs(book_margin))}.'
    if spread is not None and abs(spread) >= 21:
        text += ' Starters may sit early.'
    return text


def look_line(card, parts, spread, total, model, model_total, fresh, tier):
    """The one thing to look at on the Worth your time strip, from checked parts only."""
    if parts.get('official'):
        return 'Best bet posted'
    if fresh and model_total is not None and total is not None and abs(model_total - total) >= 3:
        return f'Total {_fmt(total)} vs my {_fmt(model_total)}'
    if fresh and model is not None and spread is not None and abs(model + spread) >= 3:
        dog = card['away'] if spread < 0 else card['home']
        book_dog = abs(spread)
        my_dog = -model if spread < 0 else model
        return f"{dog['abbr']} +{_fmt(book_dog)} vs my {'+' if my_dog >= 0 else ''}{_fmt(my_dog)}"
    if parts.get('upset'):
        return 'Upset watch'
    if parts.get('props', 0) >= 3:
        return f"{parts['props']} props priced"
    if tier == 'blowout':
        return 'Props carry garbage-time risk'
    if parts.get('spread') and parts.get('total'):
        return 'Fresh spread and total'
    return 'Even matchup' if tier == 'competitive' else None


def navigator(game, card, rows, picks, now, conferences=None):
    """A stable, descriptive sort score; never a betting recommendation."""
    market, v2 = card.get('market') or {}, card.get('v2') or {}
    spread = _number(market.get('spread'))
    model = _number(v2.get('margin'))
    book_margin = -spread if spread is not None else None
    difference = round(model - book_margin, 1) if model is not None and book_margin is not None else None
    upcoming = game.get('state') == 'pre'
    fresh = upcoming and _fresh(market.get('retrievedAt'), now)
    tier = _tier(spread)
    gap = {'model': model, 'book': book_margin, 'difference': difference} if difference is not None else None
    plain = plain_gap(card, model, book_margin, spread, fresh) if upcoming else None
    game_rows = [r for r in rows if r.get('gameId') == card['id']]
    props = {(str(r.get('athleteId')), r.get('stat')) for r in game_rows
             if r.get('athleteId') and r.get('state') == 'open' and not r.get('roleSuspect')
             and not r.get('priceSuspect') and _number(r.get('odds')) is not None
             and _fresh(r.get('observedAt'), now)}
    parts = {'spread': fresh and _same_line_pair(game_rows, 'point spread', now),
             'total': fresh and _same_line_pair(game_rows, 'total points', now),
             'props': len(props), 'official': any(p.get('gameId') == card['id'] and p.get('publishedAt')
                                             for p in picks), 'upset': bool(card.get('upsetWatch'))}
    competitiveness = {'competitive': 3, 'lean': 2, 'mismatch': 1, 'blowout': 0}.get(tier, 0)
    model_total, book_total = _number(v2.get('total')), _number(market.get('total'))
    total_difference = abs(model_total - book_total) if model_total is not None and book_total is not None else 0
    price_gap = min(2, max(abs(difference or 0), total_difference) // 3) if fresh else 0
    bettable = (2 * int(parts['spread']) + 2 * int(parts['total']) + 2 * int(len(props) >= 3)
                + competitiveness + int(price_gap) + 2 * int(parts['official']) + int(parts['upset']))
    if not upcoming:
        bettable = 0
    return {'gap': gap, 'tier': tier, 'window': _window(game.get('kickoff')),
            'conference': {side: _conference(game, side, conferences) for side in ('home', 'away')},
            'ranked': {side: game.get(side, {}).get('rank') for side in ('home', 'away')},
            'bettable': bettable, 'bettableParts': parts, 'plainGap': plain,
            'look': look_line(card, parts, spread, book_total, model, model_total, fresh, tier) if upcoming else None,
            'garbageTime': spread is not None and abs(spread) >= 21}


def _recent(team_logs, team, before):
    return [r for r in team_logs.get(str(team['id']), []) if _time(r.get('kickoff'))
            and _time(r['kickoff']) < before][-3:]


def _market_drivers(kind, game, card, snapshot, team_logs, ratings, injuries, rows, now, weather_row, gap, book, ours):
    """Drivers for one market, each {text, direction, weight, numbers[, flag]}; code supplies every number."""
    market = card.get('market') or {}
    drivers = []

    def add(text, direction, weight, numbers, flag=None):
        drivers.append({'text': text, 'direction': direction, 'weight': round(weight, 2),
                        'numbers': [n for n in numbers if n is not None], **({'flag': flag} if flag else {})})

    # 1. Ratings: the forecast's own rank table, never an outside power ranking.
    if kind == 'spread':
        fav = 'home' if gap > 0 else 'away'
        other = 'away' if fav == 'home' else 'home'
        off = (card.get(fav) or {}).get('strength') or {}
        defense = (card.get(other) or {}).get('strength') or {}
        if off.get('offense') and defense.get('defense') and off.get('teams'):
            add(f"{card[fav]['name']}'s offense ranks {off['offense']} of {off['teams']}; "
                f"{card[other]['name']}'s defense ranks {defense['defense']}.", 1,
                abs(defense['defense'] - off['offense']) / 15, [off['offense'], off['teams'], defense['defense']])
    else:
        side = min(('home', 'away'), key=lambda key: ((card.get(key) or {}).get('strength') or {}).get('defense', 999)) \
            if gap < 0 else max(('home', 'away'), key=lambda key: ((card.get(key) or {}).get('strength') or {}).get('defense', -1))
        strength = (card.get(side) or {}).get('strength') or {}
        if strength.get('defense') and strength.get('teams'):
            add(f"{card[side]['name']}'s defense ranks {strength['defense']} of {strength['teams']} in my model.",
                1, abs(strength['defense'] - strength['teams'] / 2) / 15, [strength['defense'], strength['teams']])

    # 2. Recent scoring and 3. schedule strength, per team.
    before = _time(game['kickoff'])
    for side in ('home', 'away'):
        team = card[side]
        recent = _recent(team_logs, team, before)
        totals = [r.get('pointsFor', 0) + r.get('pointsAgainst', 0) for r in recent
                  if isinstance(r.get('pointsFor'), (int, float)) and isinstance(r.get('pointsAgainst'), (int, float))]
        if kind == 'total' and len(totals) == 3 and (sum(totals) / 3 - book) * gap > 0:
            add(f"{team['name']}'s last three games totaled {', '.join(map(str, totals))}.", 1,
                abs(sum(totals) / 3 - book) / 3, totals)
        if kind == 'spread' and len(recent) == 3:
            margins = [r['pointsFor'] - r['pointsAgainst'] for r in recent]
            if sum(margins) / 3 * (1 if side == 'home' else -1) * gap > 0:
                add(f"{team['name']}'s last three margins were {', '.join(f'{m:+g}' for m in margins)}.", 1,
                    abs(sum(margins) / 3) / 5, margins)
            if any(abs(m) >= 28 for m in margins):
                add(f"{team['name']} had a 28-point-or-larger result in its last three games.", -1, 1, [28], 'blowout')
        opponents = [ratings.get(str(r.get('opp'))) for r in recent]
        opponents = [(p['offense'] + p['defense']) / 2 for p in opponents if p and p.get('offense') and p.get('defense')]
        n = (ratings.get(str(team['id'])) or {}).get('teams')
        if kind == 'spread' and n and len(opponents) == 3 and sum(opponents) / 3 >= .75 * n:
            add(f"{team['name']}'s last three opponents averaged about {round(sum(opponents) / 3)} of {n} "
                'by combined offense and defense rank.', -1, 1.5, [round(sum(opponents) / 3), n], 'soft_schedule')

    # 4. Roster: a quarterback role hold already computed for this game; NFL top-position players listed out.
    if any(r.get('roleHold') == 'qb' for r in rows if r.get('gameId') == card['id']):
        add('Recent quarterback changes put receiving roles in this game under review.', -1, 2, [], 'qb_change')
    if game.get('league') == 'NFL':
        for side in ('home', 'away'):
            for player in injuries.get(str(card[side]['id']), []):
                if player.get('position') in ('QB', 'RB', 'WR', 'TE') and str(player.get('status', '')).lower() == 'out':
                    add(f"{player.get('name') or player['position']} is listed out for {card[side]['name']}.",
                        -1, 1.5, [], 'injury')
                    break

    # 5. Line movement from the stored captures.
    open_line = _number(market.get('spreadOpen' if kind == 'spread' else 'totalOpen'))
    current_line = _number(market.get('spread' if kind == 'spread' else 'total'))
    if open_line is not None and current_line is not None and open_line != current_line:
        add(f"{market.get('displayBook') or market.get('book') or 'The book'} moved "
            f"{'the home spread' if kind == 'spread' else 'the total'} from {_fmt(open_line)} to {_fmt(current_line)}.",
            1 if (current_line - open_line) * (-gap if kind == 'spread' else gap) > 0 else -1,
            abs(current_line - open_line), [open_line, current_line])

    # 6. Weather from the stored NWS forecast, totals only, when it is recent and covers kickoff.
    forecast = (weather_row or {}).get('forecast') or {}
    issued = _time(forecast.get('issuedAt'))
    period = _time(forecast.get('periodStart'))
    if kind == 'total' and issued and period and timedelta(0) <= now - issued <= timedelta(hours=24) \
            and abs(period - before) <= timedelta(hours=1):
        wind, rain = _number(forecast.get('windMph')), _number(forecast.get('precipProb'))
        if wind is not None and wind >= 15:
            add(f"The stored kickoff forecast has {wind:g} mph wind.", 1 if gap < 0 else -1, wind / 5, [wind], 'weather')
        if rain is not None and rain >= 60:
            add(f"The stored kickoff forecast has a {rain:g}% chance of rain.", 1 if gap < 0 else -1, rain / 20, [rain], 'weather')

    # 7. Pace: my projected plays against the two teams' stored season averages, totals only.
    if kind == 'total' and snapshot:
        players = snapshot.get('players') or {}
        projected = [_number(((players.get(side) or {}).get('volume') or {}).get('plays')) for side in ('home', 'away')]
        season = []
        for side in ('home', 'away'):
            logs = team_logs.get(str(card[side]['id']), [])
            plays = [((r.get('offense') or {}).get('pbp') or {}).get('plays') for r in logs if _time(r.get('kickoff')) and _time(r['kickoff']) < before]
            plays = [p for p in plays if isinstance(p, (int, float))]
            season.append(sum(plays) / len(plays) if len(plays) >= 3 else None)
        if all(p is not None for p in projected) and all(s is not None for s in season):
            mine, usual = round(sum(projected)), round(sum(season))
            if abs(mine - usual) >= 6 and (mine - usual) * gap > 0:
                add(f'I project about {mine} plays; these two teams have averaged {usual} together this season.',
                    1, abs(mine - usual) / 6, [mine, usual])

    drivers.sort(key=lambda d: (-d['weight'], d['text']))
    caution = next((d['text'] for d in drivers if d.get('flag')), None)
    return {'ours': ours, 'book': book, 'gap': gap, 'drivers': drivers, 'caution': caution}


def card_text(lead, drivers):
    """The card's one or two sentences: the lead plus the top two supporting drivers that fit in 220 characters."""
    picked = [d for d in drivers if d['direction'] > 0][:2]
    summary = lead
    for driver in picked:
        candidate = summary + ' ' + driver['text']
        if len(candidate) <= CARD_TEXT:
            summary = candidate
    return summary if picked else None


def why_differ(game, card, snapshot, team_logs, ratings, injuries, rows, now, weather_row=None):
    """Specific, sourced-in-data drivers for every fresh 3+ point model/book difference.

    Returns None when neither market differs by three points. A stale line returns only the staleness line.
    Otherwise the top level describes the larger difference (the card's line) and `markets` holds each
    qualifying market with its own drivers for the game page."""
    if game.get('state') != 'pre':
        return None
    market, v2 = card.get('market') or {}, card.get('v2') or {}
    spread, total = _number(market.get('spread')), _number(market.get('total'))
    margin, ours_total = _number(v2.get('margin')), _number(v2.get('total'))
    gaps = {'spread': round(margin + spread, 1) if margin is not None and spread is not None else None,
            'total': round(ours_total - total, 1) if ours_total is not None and total is not None else None}
    qualifying = [k for k in ('spread', 'total') if gaps[k] is not None and abs(gaps[k]) >= 3]
    if not qualifying:
        return None
    if not _fresh(market.get('retrievedAt'), now):
        return {'stale': True, 'text': STALE_TEXT, 'drivers': []}
    markets = {}
    for kind in ('spread', 'total'):
        if kind not in qualifying:
            markets[kind] = None
            continue
        book = -spread if kind == 'spread' else total
        ours = margin if kind == 'spread' else ours_total
        markets[kind] = _market_drivers(kind, game, card, snapshot, team_logs, ratings, injuries, rows, now, weather_row,
                                        gaps[kind], book, ours)
    primary = max(qualifying, key=lambda k: (abs(gaps[k]), k == 'spread'))
    block = markets[primary]
    if primary == 'spread':
        leader = card['home']['name'] if block['ours'] >= 0 else card['away']['name']
        book_leader = card['home']['name'] if block['book'] >= 0 else card['away']['name']
        lead = (f"I have {leader} by {_fmt(abs(block['ours']))}, the book has "
                f"{'' if leader == book_leader else book_leader + ' by '}{_fmt(abs(block['book']))}.")
    else:
        lead = f"I have {_fmt(block['ours'])}, the book has {_fmt(block['book'])}."
    return {'stale': False, 'kind': primary, 'ours': block['ours'], 'book': block['book'], 'gap': block['gap'],
            'text': card_text(lead, block['drivers']), 'drivers': block['drivers'], 'caution': block['caution'],
            'markets': markets}
