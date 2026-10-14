"""Private player-projection variants; never changes a public number or play.

The live projection is preserved beside alternatives that use current-team
games, the current quarterback, partial-game removal, medians and the exact
book's two-sided market.  Results and same-book closes are appended later so
the variants can earn promotion with replay and forward evidence.
"""
import hashlib
import statistics
from datetime import datetime, timezone
from pathlib import Path

import features
import gates
import learn
import pricing
import reasoned_edges

ROOT = Path.home() / '.config' / 'keenroudy' / 'projection-shadows'
LEDGER = ROOT / 'observations.jsonl'
MANIFEST = ROOT / 'ledger.json'
STAT = {'rec': 'rec', 'car': 'car', 'recYds': 'recYds', 'rushYds': 'rushYds',
        'att': 'att', 'cmp': 'cmp', 'passYds': 'passYds'}
VOLUME = {'rec': 'targets', 'recYds': 'targets', 'car': 'car', 'rushYds': 'car',
          'att': 'att', 'cmp': 'att', 'passYds': 'att'}


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def game_id(game):
    return f"{game.get('league')}-{game.get('eventId')}"


def team_games(ctx, team, league):
    rows = [game for game in ctx.records if game.get('league') == league and
            team in (str((game.get('home') or {}).get('id')), str((game.get('away') or {}).get('id')))]
    return sorted(rows, key=lambda row: features.when(row['kickoff']), reverse=True)


def player_row(game, athlete):
    return next((row for row in game.get('players', []) if str(row.get('id')) == str(athlete)), None)


def values(game, row):
    if not row:
        return {}
    return {**row, **features.unified(row, game.get('league'), (game.get('quality') or {}).get('plays') == 'ok')}


def team_attempts(game, team):
    return sum(float((row.get('att') or 0)) for row in game.get('players', [])
               if str(row.get('team')) == str(team))


def main_qb(game, team):
    passers = [row for row in game.get('players', []) if str(row.get('team')) == str(team) and
               isinstance(row.get('att'), (int, float))]
    return str(max(passers, key=lambda row: row.get('att') or 0).get('id')) if passers else None


def full_current_games(ctx, athlete, team, league, market, limit=8):
    """Latest current-team games, with partial appearances excluded.

    A missed team game remains a zero-volume role observation.  A played game
    is full when the relevant volume is at least 60% of that player's current-
    team median.  Quarterback games additionally require 60% of team attempts.
    """
    stat, volume = STAT.get(market), VOLUME.get(market)
    if not stat or not volume:
        return []
    games = team_games(ctx, str(team), league)[:limit]
    seen = []
    for game in games:
        row = player_row(game, athlete)
        data = values(game, row)
        seen.append({'game': game, 'row': row, 'value': float(data.get(stat) or 0),
                     'volume': float(data.get(volume) or 0)})
    played = [row['volume'] for row in seen if row['row'] is not None and row['volume'] > 0]
    median = statistics.median(played) if played else 0
    out = []
    for item in seen:
        if item['row'] is None:
            out.append(item)  # missed recent game: zero share
            continue
        if median and item['volume'] < .60 * median:
            continue
        if volume == 'att':
            attempts = team_attempts(item['game'], team)
            if attempts and item['volume'] < .60 * attempts:
                continue
        out.append(item)
    return out


def forecast_player(candidate, ctx):
    snapshot = ctx.snapshot((candidate.get('gameIds') or [None])[0])
    _, player = pricing.player_line(snapshot, str(candidate.get('athleteId') or '')) if snapshot else (None, None)
    return snapshot, player


def same_qb_projection(candidate, ctx, rows, player):
    market = gates.market_key(candidate)
    if market not in ('rec', 'recYds') or not player or not rows:
        return None
    team = str(ctx.player_team.get(str(candidate.get('athleteId'))) or '')
    league = candidate.get('league') or ''
    qb = ctx.starters.get(f'{league}-{team}')
    target = player.get('targets')
    targets = target[0] if isinstance(target, list) else (target or {}).get('mean') if isinstance(target, dict) else None
    if not qb or not isinstance(targets, (int, float)):
        return None
    eligible = [item for item in rows if main_qb(item['game'], team) == str(qb)]
    # College target bookkeeping before 2025 is known to be incomplete.
    eligible = [item for item in eligible if league != 'CFB' or item['game'].get('season', 0) >= 2025]
    target_total = catch_total = yards = 0.0
    for item in eligible:
        data = values(item['game'], item['row'])
        weight = .5 ** (eligible.index(item) / 3)
        target_total += weight * float(data.get('targets') or 0)
        catch_total += weight * float(data.get('rec') or 0)
        yards += weight * float(data.get('recYds') or 0)
    if not target_total:
        return None
    rate = catch_total / target_total if market == 'rec' else yards / target_total
    return round(float(targets) * rate, 1)


def receiver_cap(candidate, ctx, player, value):
    if gates.market_key(candidate) != 'recYds' or not isinstance(value, (int, float)):
        return value
    snapshot, _ = forecast_player(candidate, ctx)
    if not snapshot or not player:
        return value
    side, _ = pricing.player_line(snapshot, str(candidate.get('athleteId') or ''))
    roster = ((((snapshot.get('players') or {}).get(side) or {}).get('players')) or [])
    receiving = sum((p.get('recYds') or [0])[0] for p in roster if isinstance(p.get('recYds'), list))
    passing = max(((p.get('passYds') or [0])[0] for p in roster if isinstance(p.get('passYds'), list)), default=0)
    return round(value * min(1.0, passing / receiving), 1) if receiving and passing else value


def shadow(candidate, ctx):
    athlete = str(candidate.get('athleteId') or '')
    market = gates.market_key(candidate)
    stat = STAT.get(market)
    game = ctx.games.get((candidate.get('gameIds') or [None])[0]) or {}
    team = str(ctx.player_team.get(athlete) or '')
    if not athlete or not stat or not team:
        return None
    snapshot, player = forecast_player(candidate, ctx)
    rows = full_current_games(ctx, athlete, team, candidate.get('league') or game.get('league'), market)
    actuals = [row['value'] for row in rows]
    current = statistics.mean(actuals[:3]) if actuals else None
    if VOLUME.get(market) == 'att':
        recent = team_games(ctx, team, candidate.get('league') or game.get('league'))
        if recent and main_qb(recent[0], team) != athlete:
            current = 0.0
    median = statistics.median(actuals) if actuals else None
    same_qb = same_qb_projection(candidate, ctx, rows, player)
    same_qb = receiver_cap(candidate, ctx, player, same_qb)
    numbers = gates.selection_numbers(candidate, ctx)
    live = candidate.get('projection')
    if not isinstance(live, (int, float)) and player:
        saved = player.get(pricing.PROJECTED.get(market, stat))
        live = saved[0] if isinstance(saved, list) else (saved or {}).get('mean') if isinstance(saved, dict) else None
    source = candidate.get('quotedAt') or (snapshot or {}).get('publishedAt') or stamp(ctx.now)
    raw = '|'.join((str(candidate.get('id')), str(candidate.get('book')), str(candidate.get('line')), str(source)))
    return {'type': 'shadow', 'id': hashlib.sha256(raw.encode()).hexdigest()[:20],
            'candidate': {key: candidate.get(key) for key in
                          ('id', 'league', 'season', 'title', 'athleteId', 'market', 'direction', 'line',
                           'odds', 'book', 'gameIds', 'kickoff')},
            'observedAt': stamp(ctx.now), 'sourceAt': source, 'publicEffect': False,
            'liveProjection': live, 'currentTeamFullGame': round(current, 1) if current is not None else None,
            'walkForwardMedian': round(median, 1) if median is not None else None,
            'sameQBProjection': same_qb, 'fullOrMissedGames': len(rows),
            'marketAnchoredChance': numbers.get('chance') if numbers else None,
            'marketFairChance': numbers.get('fairChance') if numbers else None,
            'sameBookClose': None, 'result': None}


def capture(candidates, ctx, path=LEDGER, manifest=MANIFEST):
    found = [row for candidate in candidates if (row := shadow(candidate, ctx))]
    return reasoned_edges.append(found, path, manifest)


def settle(ctx, now, path=LEDGER, manifest=MANIFEST):
    existing = reasoned_edges.rows(path)
    done = {row.get('shadowId') for row in existing if row.get('type') == 'grade'}
    finals = {game_id(game): game for game in ctx.records}
    new = []
    for row in existing:
        if row.get('type') != 'shadow' or row.get('id') in done:
            continue
        candidate = row.get('candidate') or {}
        game = finals.get((candidate.get('gameIds') or [None])[0])
        if not game:
            continue
        graded = learn.grade_row(candidate, {candidate['gameIds'][0]: game}, {})
        if not graded:
            continue
        close = reasoned_edges.same_book_close({'candidate': candidate}, ctx)
        actual = graded.get('value')
        errors = {name: round(abs(float(value) - float(actual)), 2)
                  for name, value in (('liveProjection', row.get('liveProjection')),
                                      ('currentTeamFullGame', row.get('currentTeamFullGame')),
                                      ('walkForwardMedian', row.get('walkForwardMedian')),
                                      ('sameQBProjection', row.get('sameQBProjection')))
                  if isinstance(value, (int, float)) and isinstance(actual, (int, float))}
        new.append({'type': 'grade', 'id': 'grade-' + row['id'], 'shadowId': row['id'],
                    'gradedAt': stamp(now), 'result': graded.get('result'), 'actual': actual,
                    'sameBookClose': close[1][0] if close else None, 'absoluteError': errors})
    reasoned_edges.append(new, path, manifest)
    return len(new)


def report(path=LEDGER):
    rows = [row for row in reasoned_edges.rows(path) if row.get('type') == 'shadow']
    grades = [row for row in reasoned_edges.rows(path) if row.get('type') == 'grade']
    errors = {}
    for name in ('liveProjection', 'currentTeamFullGame', 'walkForwardMedian', 'sameQBProjection'):
        values = [(row.get('absoluteError') or {}).get(name) for row in grades]
        values = [value for value in values if isinstance(value, (int, float))]
        errors[name] = round(statistics.mean(values), 2) if values else None
    return {'rows': len(rows), 'graded': len(grades), 'meanAbsoluteError': errors,
            'status': 'inconclusive',
            'promotion': 'owner approval required after replay and forward evidence'}


def step(candidates, ctx, now=None, path=LEDGER, manifest=MANIFEST):
    now = now or ctx.now
    graded = settle(ctx, now, path, manifest)
    return {'captured': capture(candidates, ctx, path, manifest), 'gradedThisRun': graded, **report(path)}
