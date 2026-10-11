"""Descriptive full-season thresholds, never probabilities or pick selection. No network."""
import math
import re
from datetime import datetime, timedelta

import features
import sharp_odds
import starters

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


def history(logs, stat, season, now, team=None, records=None, athlete=None):
    # Unknown is not a zero, nor silently dropped from a flattering denominator.
    appearances = {str(r['eventId']): r for r in logs if r.get('season') == season
                   and r.get('seasonType') == 2 and when(r.get('kickoff'))
                   and when(r['kickoff']) < now and (team is None or str(r.get('team')) == str(team))}
    current = sorted(appearances.values(), key=lambda r: r['kickoff'])
    if len(current) < 2 or any(not numeric((r.get('stats') or {}).get(stat)) for r in current):
        return []
    rows = current
    if len(current) < 5 and team is not None:
        prior = {str(r['eventId']): r for r in logs if r.get('season') == season - 1 and r.get('seasonType') == 2
                 and when(r.get('kickoff')) and when(r['kickoff']) < now and str(r.get('team')) == str(team)
                 and numeric((r.get('stats') or {}).get(stat))}
        prior = sorted(prior.values(), key=lambda r: r['kickoff'])
        if stat in ('rec', 'recYds') and records:
            current_qb = starters.usual_starter(records, team, now)
            games = {str(g['eventId']): g for g in records}
            if current_qb:
                prior = [r for r in prior if games.get(str(r['eventId']))
                         and str(starters.starter(games[str(r['eventId'])], team)) == str(current_qb)]
            else:
                prior = []
        rows = prior[-(10 - len(current)):] + current
    if len(rows) < 3:
        return []
    return [{'eventId': r['eventId'], 'date': r['kickoff'][:10], 'kickoff': r['kickoff'],
             'season': r['season'], 'priorSeason': r['season'] != season,
             'opponent': str(r['opp']), 'value': r['stats'][stat]} for r in rows[-10:]]


def defense_ranks(logs, position, stat, season, before, eligible=None, minimum=3):
    """FBS-only (when eligible is provided) defense-vs-position ranks as they stood before a game."""
    values = []
    for defense, rows in logs.items():
        if eligible is not None and str(defense) not in eligible:
            continue
        seen = [((r.get('allowed', {}).get(position) or {}).get(stat)) for r in rows
                if r.get('season') == season and r.get('seasonType') == 2 and when(r.get('kickoff'))
                and when(r['kickoff']) < before]
        seen = [v for v in seen if numeric(v)]
        if len(seen) >= minimum:
            values.append((sum(seen) / len(seen), str(defense), len(seen)))
    values.sort()
    return {team: {'rank': rank, 'of': len(values), 'average': round(avg, 1), 'games': games,
                   'position': position, 'stat': stat}
            for rank, (avg, team, games) in enumerate(values, 1)}


def quality(league, opponent, ranks, fbs):
    opponent = str(opponent)
    if league == 'CFB' and opponent not in fbs:
        return 'fcs'
    row = ranks.get(opponent)
    if not row:
        return 'unknown'
    if league == 'CFB':
        return 'fbsTopHalf' if row['rank'] <= math.ceil(row['of'] / 2) else 'fbsBottomHalf'
    if row['rank'] <= 10:
        return 'top10'
    if row['rank'] > max(10, row['of'] - 10):
        return 'bottom10'
    return 'middle'


def opponent_context(hist, line, direction, league, defense_logs, position, stat, season, kickoff, opponent, fbs,
                     rank_cache=None):
    rank_cache = rank_cache if rank_cache is not None else {}
    eligible = fbs if league == 'CFB' else None
    def ranks_for(year, before):
        key = (league, position, stat, year, before.isoformat())
        if key not in rank_cache:
            rank_cache[key] = defense_ranks(defense_logs, position, stat, year, before, eligible)
        return rank_cache[key]
    tonight_ranks = ranks_for(season, kickoff)
    dvp = tonight_ranks.get(str(opponent))
    tonight_quality = quality(league, opponent, tonight_ranks, fbs)
    tagged = []
    for row in hist:
        ranks = ranks_for(row['season'], when(row['kickoff']))
        tag = quality(league, row['opponent'], ranks, fbs)
        tagged.append({**row, 'opponentQuality': tag, 'opponentDefense': ranks.get(row['opponent'])})
    groups = {}
    labels = ('fbsTopHalf', 'fbsBottomHalf', 'fcs') if league == 'CFB' else ('top10', 'middle', 'bottom10')
    for label in labels:
        rows = [r for r in tagged if r['opponentQuality'] == label]
        groups[label] = result(rows, line, direction) if rows else {'hits': 0, 'games': 0, 'pushes': 0, 'rate': None}
    comparable = groups.get(tonight_quality) or {'hits': 0, 'games': 0, 'pushes': 0, 'rate': None}
    supports = comparable['games'] >= 2 and comparable['rate'] >= 70
    if league == 'CFB' and tonight_quality == 'fbsBottomHalf' and groups['fbsTopHalf']['games'] >= 2 \
            and groups['fbsTopHalf']['rate'] >= 70:
        supports = True
    hits = [r for r in tagged if (r['value'] >= line if direction == 'at-least' else
                                  r['value'] > line if direction == 'over' else r['value'] < line)]
    padded = [r for r in hits if r['opponentQuality'] == 'fcs' or
              ((r.get('opponentDefense') or {}).get('rank', 0) > max(0, (r.get('opponentDefense') or {}).get('of', 0) - 30))]
    against = bool(league == 'CFB' and dvp and dvp['rank'] <= 30 and hits and len(padded) * 2 >= len(hits))
    return tagged, dvp, groups, {'tonight': tonight_quality, 'supports': supports and not against,
                                 'against': against, 'comparable': comparable}


def result(history_rows, line, direction):
    hits = sum(r['value'] >= line if direction == 'at-least' else
               r['value'] > line if direction == 'over' else r['value'] < line for r in history_rows)
    pushes = sum(r['value'] == line for r in history_rows) if direction != 'at-least' else 0
    return {'hits': hits, 'games': len(history_rows), 'pushes': pushes,
            'rate': round(100 * hits / len(history_rows), 1)}


def build(games, league_data, lines, prices, now, injuries=None):
    out = []
    rank_cache = {}
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
                hist = history(logs, stat, season, now, last.get('team'), info.get('records'), pid)
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
                    position = features.GROUP.get(last.get('pos')) or (
                        'QB' if stat in ('att', 'cmp', 'passYds') else 'RB' if stat in ('car', 'rushYds') else 'WR')
                    tagged, dvp, splits, adjusted = opponent_context(
                        hist, n, direction, league, info.get('defense_logs') or {}, position, stat, season,
                        when(game['kickoff']), next(t for t in teams if t != str(last['team'])),
                        {str(t) for t in info.get('fbs') or []}, rank_cache)
                    proof = [row for row in tagged if league != 'CFB' or row.get('opponentQuality') != 'fcs']
                    if len(proof) < 2:
                        continue
                    score = result(proof, n, direction)
                    if score['hits'] * 100 < score['games'] * 70:
                        continue
                    key = (n, direction, offer['kind'], offer.get('book'))
                    if key in seen:
                        continue
                    seen.add(key)
                    title = f'{n:g}+ {label}' if direction == 'at-least' else f'{direction.title()} {n:g} {label}'
                    out.append({**base, **score, 'stat': stat, 'title': title, 'line': n, 'direction': direction,
                                'kind': offer['kind'], 'book': offer.get('book'), 'odds': offer.get('odds'),
                                'observedAt': offer.get('observedAt'), 'history': tagged,
                                'includesPriorSeason': any(r.get('priorSeason') for r in tagged),
                                'dvp': dvp, 'vsQuality': splits, 'opponentAdjustment': adjusted})
    return out
