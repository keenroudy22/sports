"""Read-only game context for the college slate and explained model differences.

Every number comes from the existing forecast, slate, stored box scores or captured lines.
These fields organize research; they do not admit a play or change a grade.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo('America/New_York')
FRESH = timedelta(hours=4)


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


def navigator(game, card, rows, picks, now):
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
    if not upcoming:
        plain = None
    elif not fresh or gap is None:
        plain = 'The book line is older than four hours; check a current spread.' if spread is not None else None
    elif abs(model) <= 3 and abs(book_margin) <= 3:
        plain = f'Even matchup by my numbers (gap {_fmt(abs(model))}) and the book is close ({_fmt(abs(book_margin))}).'
    else:
        leader = card['home']['name'] if model >= 0 else card['away']['name']
        book_leader = card['home']['name'] if book_margin >= 0 else card['away']['name']
        plain = f'I have {leader} by {_fmt(abs(model))}; the book has {book_leader} by {_fmt(abs(book_margin))}.'
        if spread is not None and abs(spread) >= 21:
            plain += ' Starters may sit early.'
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
            'conference': {side: game.get(side, {}).get('conference') for side in ('home', 'away')},
            'ranked': {side: game.get(side, {}).get('rank') for side in ('home', 'away')},
            'bettable': bettable, 'bettableParts': parts, 'plainGap': plain,
            'garbageTime': spread is not None and abs(spread) >= 21}


def why_differ(game, card, snapshot, team_logs, ratings, injuries, rows, now, weather_row=None):
    """Specific, sourced-in-data drivers for a fresh 3+ point model/book difference."""
    if game.get('state') != 'pre':
        return None
    market, v2 = card.get('market') or {}, card.get('v2') or {}
    spread, total = _number(market.get('spread')), _number(market.get('total'))
    margin, ours_total = _number(v2.get('margin')), _number(v2.get('total'))
    spread_gap = round(margin + spread, 1) if margin is not None and spread is not None else None
    total_gap = round(ours_total - total, 1) if ours_total is not None and total is not None else None
    kind = 'spread' if spread_gap is not None and abs(spread_gap) >= 3 else 'total' if total_gap is not None and abs(total_gap) >= 3 else None
    if not kind:
        return None
    if not _fresh(market.get('retrievedAt'), now):
        return {'stale': True, 'text': 'The book line is older than four hours; check a current price.',
                'drivers': []}
    gap = spread_gap if kind == 'spread' else total_gap
    book = -spread if kind == 'spread' else total
    ours = margin if kind == 'spread' else ours_total
    lead = f'I have {_fmt(ours)}, the book has {_fmt(book)}.'
    drivers = []

    def add(text, direction, weight, flag=None):
        drivers.append({'text': text, 'direction': direction, 'weight': round(weight, 2),
                        **({'flag': flag} if flag else {})})

    # The forecast's own rating table determines the ranks; no external power ranking is inferred.
    if kind == 'spread':
        fav = 'home' if gap > 0 else 'away'
        other = 'away' if fav == 'home' else 'home'
        off = (card.get(fav) or {}).get('strength') or {}
        defense = (card.get(other) or {}).get('strength') or {}
        if off.get('offense') and defense.get('defense') and off.get('teams'):
            add(f"{card[fav]['name']}'s offense ranks {off['offense']} of {off['teams']}; "
                f"{card[other]['name']}'s defense ranks {defense['defense']}.", 1,
                abs(defense['defense'] - off['offense']) / 15)
    else:
        side = min(('home', 'away'), key=lambda key: ((card.get(key) or {}).get('strength') or {}).get('defense', 999)) \
            if gap < 0 else max(('home', 'away'), key=lambda key: ((card.get(key) or {}).get('strength') or {}).get('defense', -1))
        strength = (card.get(side) or {}).get('strength') or {}
        if strength.get('defense') and strength.get('teams'):
            add(f"{card[side]['name']}'s defense ranks {strength['defense']} of {strength['teams']} in my model.",
                1, abs(strength['defense'] - strength['teams'] / 2) / 15)

    for side in ('home', 'away'):
        team = card[side]
        recent = [r for r in team_logs.get(str(team['id']), []) if _time(r.get('kickoff'))
                  and _time(r['kickoff']) < _time(game['kickoff'])][-3:]
        totals = [r.get('pointsFor', 0) + r.get('pointsAgainst', 0) for r in recent
                  if isinstance(r.get('pointsFor'), (int, float)) and isinstance(r.get('pointsAgainst'), (int, float))]
        if kind == 'total' and len(totals) == 3 and (sum(totals) / 3 - total) * gap > 0:
            add(f"{team['name']}'s last three games totaled {', '.join(map(str, totals))}.", 1,
                abs(sum(totals) / 3 - total) / 3)
        if kind == 'spread' and len(recent) == 3:
            margins = [r['pointsFor'] - r['pointsAgainst'] for r in recent]
            if sum(margins) / 3 * (1 if side == 'home' else -1) * gap > 0:
                add(f"{team['name']}'s last three margins were {', '.join(f'{m:+g}' for m in margins)}.", 1,
                    abs(sum(margins) / 3) / 5)
            if any(abs(m) >= 28 for m in margins):
                add(f"{team['name']} had a 28-point-or-larger result in its last three games.", -1, 1, 'blowout')
        opponents = [ratings.get(str(r.get('opp'))) for r in recent]
        opponents = [(p['offense'] + p['defense']) / 2 for p in opponents if p and p.get('offense') and p.get('defense')]
        n = (ratings.get(str(team['id'])) or {}).get('teams')
        if kind == 'spread' and n and len(opponents) == 3 and sum(opponents) / 3 >= .75 * n:
            add(f"{team['name']}'s last three opponents averaged about {round(sum(opponents) / 3)} of {n} "
                'by combined offense and defense rank.', -1, 1.5, 'soft_schedule')

    open_line = _number(market.get('spreadOpen' if kind == 'spread' else 'totalOpen'))
    current_line = spread if kind == 'spread' else total
    if open_line is not None and current_line is not None and open_line != current_line:
        add(f"{market.get('displayBook') or market.get('book') or 'The book'} moved "
            f"{'the home spread' if kind == 'spread' else 'the total'} from {_fmt(open_line)} to {_fmt(current_line)}.",
            1 if (current_line - open_line) * (-gap if kind == 'spread' else gap) > 0 else -1,
            abs(current_line - open_line))

    if any(r.get('roleHold') == 'qb' for r in rows if r.get('gameId') == card['id']):
        add('Recent quarterback changes put receiving roles in this game under review.', -1, 2, 'qb_change')
    if game.get('league') == 'NFL':
        for side in ('home', 'away'):
            for player in injuries.get(str(card[side]['id']), []):
                if player.get('position') in ('QB', 'RB', 'WR', 'TE') and str(player.get('status', '')).lower() == 'out':
                    add(f"{player.get('name') or player['position']} is listed out for {card[side]['name']}.",
                        -1, 1.5, 'injury')
                    break
    forecast = (weather_row or {}).get('forecast') or {}
    issued = _time(forecast.get('issuedAt'))
    period = _time(forecast.get('periodStart'))
    if kind == 'total' and issued and period and timedelta(0) <= now - issued <= timedelta(hours=24) \
            and abs(period - _time(game['kickoff'])) <= timedelta(hours=1):
        wind, rain = _number(forecast.get('windMph')), _number(forecast.get('precipProb'))
        if wind is not None and wind >= 15:
            add(f"The stored kickoff forecast has {wind:g} mph wind.", 1 if gap < 0 else -1,
                wind / 5, 'weather')
        if rain is not None and rain >= 60:
            add(f"The stored kickoff forecast has a {rain:g}% chance of rain.", 1 if gap < 0 else -1,
                rain / 20, 'weather')

    drivers.sort(key=lambda d: (-d['weight'], d['text']))
    picked = [d for d in drivers if d['direction'] > 0][:2]
    summary = lead
    for driver in picked:
        candidate = summary + ' ' + driver['text']
        if len(candidate) <= 220:
            summary = candidate
    caution = next((d['text'] for d in drivers if d.get('flag')), None)
    return {'stale': False, 'kind': kind, 'ours': ours, 'book': book, 'gap': gap,
            'text': summary if picked else None, 'drivers': drivers, 'caution': caution}
