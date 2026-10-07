"""Conservative, stored-data-only checks for implausibly small player roles.

This does not refit or change a projection. It withholds a grade until the
current-team role can be reviewed; missing usage evidence is not treated as a
zero or as proof of a problem.
"""
import statistics


VOLUME = {'passYds': ('att', 'att'), 'att': ('att', 'att'), 'cmp': ('att', 'att'),
          'recYds': ('targets', 'pbpTgt'), 'rec': ('targets', 'pbpTgt'),
          'rushYds': ('carries', 'car'), 'car': ('carries', 'car')}
QB_MARKETS = {'passYds', 'att', 'cmp', 'rushYds', 'car'}
QB_DEPENDENT_MARKETS = {'recYds', 'rec'}


def quarterback_change(players, player_logs, team, season, league, before=None):
    """Flag a new/split starter using only earlier current-team box scores.

    This is a hold, not a projection change. After three full games with the
    same expected QB, it clears automatically. Missing QB evidence never
    becomes a guessed starter or a zero.
    """
    qbs = [(str(p.get('id')), p['att'][0]) for p in players or []
           if p.get('pos') == 'QB' and isinstance(p.get('att'), (list, tuple))
           and p['att'] and isinstance(p['att'][0], (int, float))]
    if not qbs or not player_logs or not team:
        return None
    expected, projected = max(qbs, key=lambda item: (item[1], item[0]))
    total = sum(max(0, attempts) for _, attempts in qbs)
    if total > 0 and projected / total < .85:
        return {'expectedQB': expected, 'reason': 'projected QB attempts are split below 85%'}
    games = {}
    for athlete, logs in player_logs.items():
        for row in logs:
            if row.get('pos') != 'QB' or row.get('league') != league or str(row.get('team')) != str(team) \
                    or row.get('seasonType') != 2 or (season is not None and row.get('season') != season) \
                    or (before and str(row.get('kickoff') or '') >= str(before)):
                continue
            attempts = (row.get('stats') or {}).get('att')
            if not isinstance(attempts, (int, float)) or attempts <= 0:
                continue
            key = row.get('eventId')
            if key:
                games.setdefault(key, {'kickoff': row.get('kickoff') or '', 'qbs': []})['qbs'].append((str(athlete), attempts))
    starters = []
    for game in sorted(games.values(), key=lambda item: item['kickoff']):
        athlete, attempts = max(game['qbs'], key=lambda item: (item[1], item[0]))
        if attempts >= .6 * sum(value for _, value in game['qbs']):
            starters.append(athlete)
    if len(starters) < 2:
        return None
    if expected != starters[-1]:
        return {'expectedQB': expected, 'reason': 'projected QB differs from the last full-game starter'}
    if len(set(starters[-3:])) > 1:
        return {'expectedQB': expected, 'reason': 'fewer than three full games with the current QB'}
    return None


def affected_by_qb_change(athlete, position, market, change):
    """Only the QB's own lines and teammates' receiving lines inherit this hold."""
    return bool(change and ((position == 'QB' and str(athlete) == change['expectedQB'] and market in QB_MARKETS)
                            or market in QB_DEPENDENT_MARKETS and position in {'RB', 'WR', 'TE'}))


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
