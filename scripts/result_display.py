"""Factual public settlement copy from stored box scores; never edits a report."""
import re
from functools import lru_cache


def player_name(pick, box_player=None):
    for value in ((box_player or {}).get('name'), pick.get('player')):
        if value and not str(value).isdigit():
            return str(value).strip()
    title = str(pick.get('title') or '')
    match = re.match(r'^(.*?)\s+(?:OVER|UNDER)\s+[-+]?\d', title, re.I)
    return match.group(1).strip() if match else 'Player'


def clean_actual(pick):
    actual = str(pick.get('actual') or '').strip()
    return re.sub(r'^\d{5,}:\s*', player_name(pick) + ': ', actual)


@lru_cache(maxsize=1)
def stored_games():
    import features
    return {f"{game['league']}-{game['eventId']}": game for game in features.load()}


def box_player(pick, game=None):
    athlete = str(pick.get('athleteId') or '')
    if not athlete:
        return None
    if game is None:
        game = stored_games().get(pick.get('gameId') or (pick.get('gameIds') or [None])[0])
    return next((row for row in (game or {}).get('players', []) if str(row.get('id')) == athlete), None)


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def stat_line(pick, game=None):
    if not pick.get('result') or not pick.get('athleteId'):
        return None
    row = box_player(pick, game)
    if row is None:
        return None
    market = str(pick.get('market') or '')
    value = _number(pick.get('actualValue'))
    def unit(number, singular, plural=None):
        return f'{number:g} {singular if number == 1 else (plural or singular + "s")}'
    targets = _number(row.get('tgt'))
    if targets is None:
        targets = _number(row.get('pbpTgt'))
    if market in ('recYds', 'rec'):
        catches = _number(row.get('rec'))
        if catches is None and targets is not None:
            catches = 0  # ESPN omitted the zero-catch box row but retained play-by-play targets.
        yards = _number(row.get('recYds'))
        if yards is None and market == 'recYds':
            yards = value
        catches_text = unit(catches, 'catch', 'catches') if catches is not None else None
        targets_text = unit(targets, 'target') if targets is not None else None
        parts = [f'{catches_text} on {targets_text}' if catches_text and targets_text else catches_text or targets_text]
        if market == 'recYds' and yards is not None:
            parts.append(unit(yards, 'yard'))
        return ', '.join(part for part in parts if part) or None
    if market in ('rushYds', 'car'):
        carries = _number(row.get('car'))
        yards = _number(row.get('rushYds'))
        if yards is None and market == 'rushYds':
            yards = value
        carries_text = unit(carries, 'carry', 'carries') if carries is not None else None
        yards_text = unit(yards, 'yard') if yards is not None else None
        if market == 'rushYds' and carries_text and yards_text:
            return f'{yards_text} on {carries_text}'
        return carries_text or yards_text
    if market in ('passYds', 'att', 'cmp'):
        complete, attempts = _number(row.get('cmp')), _number(row.get('att'))
        yards = _number(row.get('passYds'))
        if yards is None and market == 'passYds':
            yards = value
        parts = [f'{complete:g} of {attempts:g}' if complete is not None and attempts is not None else None,
                 unit(yards, 'yard') if yards is not None else None]
        return ', '.join(part for part in parts if part) or None
    return None


def detail(pick, game=None):
    """Stat line plus an exact-line margin when the saved grade agrees with it."""
    base = stat_line(pick, game)
    if not base:
        return None
    value, line = _number(pick.get('actualValue')), _number(pick.get('line'))
    direction, result = str(pick.get('direction') or '').lower(), pick.get('result')
    if value is None or line is None or direction not in ('over', 'under') or result not in ('win', 'loss'):
        return base
    won = value > line if direction == 'over' else value < line
    if won != (result == 'win') or value == line:
        return base
    return f"{base} · {'cleared' if won else 'missed'} by {abs(value - line):g}"
