"""Conservative, stored-data-only checks for implausibly small player roles.

This does not refit or change a projection. It withholds a grade until the
current-team role can be reviewed; missing usage evidence is not treated as a
zero or as proof of a problem.
"""
import statistics
import re


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
    recent = sorted(games.values(), key=lambda item: item['kickoff'])[-3:]
    if total > 0 and projected / total < .85:
        reason = ('recent QB rotation and projected attempt share below 85%'
                  if any(len(game['qbs']) >= 2 for game in recent)
                  else 'projected QB attempts are split below 85%')
        return {'expectedQB': expected, 'reason': reason}
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


def book_key(book):
    return re.sub(r'[^a-z0-9]', '', str(book or '').lower())


def implied(odds):
    if not isinstance(odds, (int, float)) or abs(odds) < 100:
        return None
    return -odds / (100 - odds) if odds < 0 else 100 / (100 + odds)


def quote_issue(quotes, book, line, side, odds):
    """Why an official player price cannot be trusted at this exact book and line.

    `quotes` are (book, line, over, under) from the stored capture, not a
    sportsbook scrape. One-sided quotes remain research but never a straight.
    """
    if side not in ('over', 'under') or not isinstance(line, (int, float)):
        return 'no two-sided exact line at the listed book'
    opposite = 'under' if side == 'over' else 'over'
    same = [(b, l, o, u) for b, l, o, u in quotes or [] if l == line and book_key(b) == book_key(book)]
    if not same:
        return 'no two-sided exact line at the listed book'
    selected = same[0]
    price = {'over': selected[2], 'under': selected[3]}
    a, b = implied(price.get(side)), implied(price.get(opposite))
    if a is None or b is None or price[side] != odds or not .99 <= a + b <= 1.15:
        return 'no valid two-sided exact line at the listed book'
    for other_book, other_line, over, under in quotes or []:
        if other_line != line or book_key(other_book) == book_key(book):
            continue
        other_side, other_opposite = (over, under) if side == 'over' else (under, over)
        x, y = implied(other_side), implied(other_opposite)
        if x is None or y is None or not .99 <= x + y <= 1.15:
            continue
        if abs(a - x / (x + y)) >= .15:
            return 'listed price differs by 15+ points from another book at the same line'
    return None
