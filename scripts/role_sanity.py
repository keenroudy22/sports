"""Conservative, stored-data-only checks for implausibly small player roles.

This does not refit or change a projection. It withholds a grade until the
current-team role can be reviewed; missing usage evidence is not treated as a
zero or as proof of a problem.
"""
import statistics


VOLUME = {'passYds': ('att', 'att'), 'att': ('att', 'att'), 'cmp': ('att', 'att'),
          'recYds': ('targets', 'pbpTgt'), 'rec': ('targets', 'pbpTgt'),
          'rushYds': ('carries', 'car'), 'car': ('carries', 'car')}


def assess(forecast, logs, team, market, season=None):
    """Return a factual caution when forecast usage is <70% of last 3 full games."""
    pair = VOLUME.get(market)
    if not pair or not forecast or not team:
        return None
    projection = forecast.get(pair[0])
    if not isinstance(projection, (list, tuple)) or not projection or not isinstance(projection[0], (int, float)):
        return None
    current = [row for row in logs or [] if str(row.get('team')) == str(team)
               and row.get('seasonType') == 2 and (season is None or row.get('season') == season)
               and isinstance((row.get('stats') or {}).get(pair[1]), (int, float))]
    current.sort(key=lambda row: row.get('kickoff') or '')
    volumes = [row['stats'][pair[1]] for row in current]
    if len(volumes) < 3:
        return None
    median = statistics.median(volumes)
    full = [value for value in volumes if value >= .6 * median]
    if len(full) < 3:
        return None
    reference = sum(full[-3:]) / 3
    if reference <= 0 or projection[0] >= .7 * reference:
        return None
    return {'volume': pair[0], 'projected': round(projection[0], 1),
            'recentFullAverage': round(reference, 1), 'fullGames': 3}


def price_suspect(odds, chance, player=True):
    """A main player price outside the plausible range or wildly apart from our chance."""
    if not player or not isinstance(odds, (int, float)):
        return False
    if odds < -400 or odds > 400:
        return True
    if not isinstance(chance, (int, float)):
        return False
    implied = -odds / (-odds + 100) if odds < 0 else 100 / (odds + 100)
    return abs(chance - implied) > .25
