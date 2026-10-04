"""Descriptive full-season thresholds, never probabilities or pick selection. No network."""
import math
import re
from datetime import datetime, timedelta

import sharp_odds

STATS = {'rec': ('receptions', 1), 'recYds': ('receiving yards', 5),
         'rushYds': ('rushing yards', 5), 'passYds': ('passing yards', 25),
         'car': ('carries', 1), 'att': ('pass attempts', 5), 'cmp': ('completions', 5)}
BOOKS = {'fanduel': 'FanDuel', 'draftkings': 'DraftKings', 'betmgm': 'BetMGM',
         'espnbet': 'ESPN BET', 'caesars': 'Caesars', 'betrivers': 'BetRivers', 'fanatics': 'Fanatics'}


def when(value):
    try:
        at = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return at if at.tzinfo else None
    except ValueError:
        return None


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def name_key(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower())


def history(logs, stat, season, now):
    # Unknown is not a zero, nor silently dropped from a flattering denominator.
    appearances = {str(r['eventId']): r for r in logs if r.get('season') == season
                   and r.get('seasonType') == 2 and when(r.get('kickoff'))
                   and when(r['kickoff']) < now}
    rows = sorted(appearances.values(), key=lambda r: r['kickoff'])
    if len(rows) < 3 or any(not numeric((r.get('stats') or {}).get(stat)) for r in rows):
        return []
    return [{'eventId': r['eventId'], 'date': r['kickoff'][:10], 'opponent': str(r['opp']),
             'value': r['stats'][stat]} for r in rows]


def result(history_rows, line, direction):
    hits = sum(r['value'] >= line if direction == 'at-least' else
               r['value'] > line if direction == 'over' else r['value'] < line for r in history_rows)
    pushes = sum(r['value'] == line for r in history_rows) if direction != 'at-least' else 0
    return {'hits': hits, 'games': len(history_rows), 'pushes': pushes,
            'rate': round(100 * hits / len(history_rows), 1)}


def build(games, league_data, lines, prices, now, injuries=None):
    out = []
    for game in games:
        if game.get('state') != 'pre' or not when(game.get('kickoff')) or when(game['kickoff']) <= now:
            continue
        league = game['league']
        info = league_data[league]
        season = game.get('season') or info['current']
        teams = {str(game[s]['id']): game[s] for s in ('home', 'away')}
        players = {}
        for pid, logs in info['player_logs'].items():
            recent = sorted((r for r in logs if when(r.get('kickoff')) and when(r['kickoff']) < now), key=lambda r: r['kickoff'])
            if recent and str(recent[-1]['team']) in teams and recent[-1]['season'] == season:
                players[str(pid)] = (recent[-1], logs)
        names = {}
        for pid, (last, _) in players.items():
            names.setdefault(name_key(last['name']), []).append(pid)
        offers = []
        for row in lines:
            stat = row.get('stat') or next((k for k, (label, _) in STATS.items() if row.get('market') in (k, label)), None)
            if (row.get('gameId') != game['id'] or stat not in STATS or row.get('state') != 'open'
                    or row.get('marketWindow') not in (None, '', 'Full game', 'full game')):
                continue
            offers.append(dict(row, stat=stat, kind='main'))
        capture = prices.get(game['id']) or {}
        for book_key, book in (capture.get('books') or {}).items():
            if book_key not in BOOKS:
                continue
            for stat, quotes in (book.get('markets') or {}).items():
                if stat not in STATS:
                    continue
                for name, quote in quotes.items():
                    matched = names.get(name_key(name), [])
                    if len(matched) != 1:
                        continue
                    for rung in [quote, *sharp_odds.consistent(quote)]:
                        for side in ('over', 'under'):
                            offers.append({'athleteId': matched[0], 'stat': stat, 'line': rung.get('line'),
                                           'direction': side, 'odds': rung.get(side), 'book': BOOKS[book_key],
                                           'observedAt': capture.get('retrievedAt'),
                                           'kind': 'main' if rung is quote else 'alternate'})
        for pid, (last, logs) in players.items():
            team = teams[str(last['team'])]
            team_games = len({str(r['eventId']) for r in info['records'] if r.get('season') == season
                              and r.get('seasonType') == 2 and str(last['team']) in r.get('teams', {})
                              and when(r.get('kickoff')) and when(r['kickoff']) < now})
            base = {'athleteId': pid, 'player': last['name'], 'league': league, 'season': season,
                    'gameId': game['id'], 'kickoff': game['kickoff'], 'team': team,
                    'matchup': f"{game['away'].get('name', '')} at {game['home'].get('name', '')}",
                    'teamGames': team_games, 'rosterAsOf': last['kickoff']}
            base['injuryStatus'] = next((r.get('status') for r in (injuries or {}).get(league, {}).get(str(last['team']), [])
                                         if str(r.get('id')) == pid and str(r.get('status') or '').lower() != 'active'), None)
            for stat, (label, step) in STATS.items():
                hist = history(logs, stat, season, now)
                if not hist:
                    continue
                candidates = [o for o in offers if str(o.get('athleteId')) == pid and o['stat'] == stat]
                # Strongest milestone clearing each requested bucket; not every trivial rung.
                values = sorted((h['value'] for h in hist), reverse=True)
                milestones = {math.floor(values[math.ceil(len(values) * rate / 100) - 1] / step) * step
                              for rate in (70, 80, 90, 100)}
                candidates += [{'line': n, 'direction': 'at-least', 'kind': 'milestone'} for n in milestones if n > 0]
                seen = set()
                for offer in candidates:
                    n, direction = offer.get('line'), offer.get('direction')
                    if not numeric(n) or direction not in ('over', 'under', 'at-least'):
                        continue
                    observed = when(offer.get('observedAt'))
                    if offer['kind'] != 'milestone' and (not numeric(offer.get('odds')) or abs(offer['odds']) < 100
                            or not observed or not timedelta(0) <= now - observed <= timedelta(hours=4)):
                        continue
                    score = result(hist, n, direction)
                    if score['hits'] * 100 < score['games'] * 70:
                        continue
                    key = (n, direction, offer['kind'], offer.get('book'))
                    if key in seen:
                        continue
                    seen.add(key)
                    title = f'{n:g}+ {label}' if direction == 'at-least' else f'{direction.title()} {n:g} {label}'
                    out.append({**base, **score, 'stat': stat, 'title': title, 'line': n, 'direction': direction,
                                'kind': offer['kind'], 'book': offer.get('book'), 'odds': offer.get('odds'),
                                'observedAt': offer.get('observedAt'), 'history': hist})
    return out
