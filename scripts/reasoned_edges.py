"""Private, stored-data-only evidence shadows for named market reasons.

These rows never select, publish, or alter a play.  They answer a narrower
question: when a checkable reason appeared before a move, did that signal beat
the same book's closing line and the eventual result?  The ledger lives outside
Git and has its own checksum; a changed historical line stops the writer.
"""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import boxscores
import features
import gates
import learning
import weather

CONF = Path.home() / '.config' / 'keenroudy'
ROOT = CONF / 'reasoned-edges'
LEDGER = ROOT / 'observations.jsonl'
MANIFEST = ROOT / 'ledger.json'
TYPES = ('cfb_opener_move', 'news_not_in_number', 'receiving_role_overreaction',
         'wind_not_in_total', 'projection_vs_first_capture')
OUT = {'out', 'doubtful', 'injured reserve', 'suspension', 'inactive'}


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


def rows(path=LEDGER):
    try:
        return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    except FileNotFoundError:
        return []


def verify(path=LEDGER, manifest=MANIFEST):
    if not Path(manifest).exists():
        return
    saved = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if saved.get('sha256') != digest(path):
        raise ValueError('reasoned-edges ledger changed after it was recorded')


def append(new, path=LEDGER, manifest=MANIFEST):
    if not new:
        return 0
    verify(path, manifest)
    known = {(row.get('type'), row.get('id') or row.get('triggerId')) for row in rows(path)}
    fresh = [row for row in new if (row.get('type'), row.get('id') or row.get('triggerId')) not in known]
    if not fresh:
        return 0
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('a', encoding='utf-8') as handle:
        for row in fresh:
            handle.write(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n')
    Path(manifest).write_text(json.dumps({'version': 1, 'sha256': digest(path)}, indent=2) + '\n', encoding='utf-8')
    return len(fresh)


def book_block(capture, book):
    wanted = str(book or '').lower().replace(' ', '')
    for key, block in (capture.get('books') or {}).items():
        title = str(block.get('title') or key).lower().replace(' ', '')
        if wanted in (str(key).lower().replace(' ', ''), title):
            return block
    return None


def game_quote(capture, candidate):
    block = book_block(capture, candidate.get('book'))
    market = candidate.get('marketType')
    if not block or market not in ('total', 'spread', 'moneyline'):
        return None
    raw = block.get(market) or {}
    direction = candidate.get('direction')
    if market == 'total':
        return raw.get('line'), raw.get(direction)
    if market == 'spread':
        line = raw.get('home')
        return ((line if direction == 'home' else -line) if isinstance(line, (int, float)) else None,
                raw.get('homePrice' if direction == 'home' else 'awayPrice'))
    return raw.get(direction), raw.get(direction)


def prop_quote(capture, candidate):
    block = book_block(capture, candidate.get('book'))
    if not block:
        return None
    market = ((block.get('markets') or {}).get(candidate.get('market')) or {})
    name = candidate.get('player') or str(candidate.get('title') or '').split(' OVER ')[0].split(' UNDER ')[0]
    quote = market.get(name) or {}
    return quote.get('line'), quote.get(candidate.get('direction'))


def history(ctx, candidate):
    game_id = (candidate.get('gameIds') or [None])[0]
    source = ctx.prop_odds_history if candidate.get('athleteId') else ctx.odds_history
    return [row for row in source.get(game_id, []) if gates.when(row.get('retrievedAt')) <= ctx.now]


def quote(capture, candidate):
    return prop_quote(capture, candidate) if candidate.get('athleteId') else game_quote(capture, candidate)


def movement(ctx, candidate):
    quoted = [(capture, quote(capture, candidate)) for capture in history(ctx, candidate)]
    quoted = [(capture, pair) for capture, pair in quoted if pair and isinstance(pair[0], (int, float))]
    return (quoted[0], quoted[-1]) if quoted else (None, None)


def target_share_change(ctx, candidate):
    pid = str(candidate.get('athleteId') or '')
    logs = [row for row in ctx.player_logs.get(pid, []) if row.get('seasonType') == 2 and
            isinstance((row.get('stats') or {}).get('targets'), (int, float))]
    if len(logs) < 6:
        return None
    totals = {}
    for game in ctx.records:
        team_targets = defaultdict(float)
        for player in game.get('players', []):
            value = features.unified(player, game.get('league'), (game.get('quality') or {}).get('plays') == 'ok').get('targets')
            if isinstance(value, (int, float)):
                team_targets[str(player.get('team'))] += value
        totals[str(game.get('eventId'))] = team_targets
    shares = []
    for row in logs:
        total = totals.get(str(row.get('eventId')), {}).get(str(row.get('team')))
        if total:
            shares.append(float(row['stats']['targets']) / total)
    if len(shares) < 6:
        return None
    recent = sum(shares[-3:]) / 3
    prior = sum(shares[-6:-3]) / 3
    return round(recent - prior, 4)


def injury_trigger(ctx, candidate):
    game = ctx.games.get((candidate.get('gameIds') or [None])[0]) or {}
    flagged = []
    for side in ('home', 'away'):
        team = str((game.get(side) or {}).get('id') or '')
        for item in ctx.injuries.get(gates.team_key(candidate.get('league'), team), {}).values():
            if str(item.get('status') or '').lower() not in OUT:
                continue
            if str(item.get('position') or '').upper() not in ('QB', 'RB', 'WR', 'TE'):
                continue
            if item.get('reportedAt'):
                flagged.append(item)
    return min(flagged, key=lambda row: str(row.get('reportedAt'))) if flagged else None


def trigger_row(kind, candidate, now, trigger, source_at):
    raw = '|'.join((kind, str(candidate.get('id')), str(candidate.get('book')), str(candidate.get('line')), str(source_at)))
    key = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return {'type': 'trigger', 'id': key, 'reasonType': kind, 'candidate': {
                k: candidate.get(k) for k in ('id', 'league', 'season', 'title', 'marketType', 'market', 'athleteId',
                                               'direction', 'line', 'odds', 'book', 'gameIds', 'projection')},
            'trigger': trigger, 'sourceAt': source_at, 'observedAt': stamp(now),
            'status': 'shadow', 'publicEffect': False}


def detect(candidates, ctx, weather_rows=None):
    """Return silent triggers from candidate rows and cached stores only."""
    weather_rows = weather_rows if weather_rows is not None else weather.stored()
    out = []
    for candidate in candidates:
        if candidate.get('legs') or not candidate.get('id') or not candidate.get('gameIds'):
            continue
        first, current = movement(ctx, candidate)
        first_line = first[1][0] if first else None
        current_line = current[1][0] if current else candidate.get('line')
        source_at = (current[0].get('retrievedAt') if current else candidate.get('quotedAt')) or stamp(ctx.now)
        if candidate.get('league') == 'CFB' and candidate.get('marketType') == 'total' \
                and isinstance(first_line, (int, float)) and isinstance(current_line, (int, float)):
            move = float(current_line) - float(first_line)
            aligned = (move >= 3 and candidate.get('direction') == 'over') or (move <= -3 and candidate.get('direction') == 'under')
            if aligned:
                out.append(trigger_row(TYPES[0], candidate, ctx.now,
                                       {'opener': first_line, 'current': current_line, 'move': round(move, 2)}, source_at))
        injury = injury_trigger(ctx, candidate)
        if injury and first and current and abs(float(current_line) - float(first_line)) < 1:
            out.append(trigger_row(TYPES[1], candidate, ctx.now,
                                   {'player': injury.get('name'), 'position': injury.get('position'),
                                    'status': injury.get('status'), 'lineMove': round(float(current_line) - float(first_line), 2)},
                                   injury.get('reportedAt') or source_at))
        if candidate.get('market') in ('rec', 'recYds') and candidate.get('direction') == 'under':
            change = target_share_change(ctx, candidate)
            if change is not None and change >= .05:
                out.append(trigger_row(TYPES[2], candidate, ctx.now,
                                       {'last3TargetShareChange': change}, source_at))
        forecast = (weather_rows.get(candidate['gameIds'][0]) or {}).get('forecast') or {}
        if candidate.get('marketType') == 'total' and candidate.get('direction') == 'under' \
                and (forecast.get('windMph') or 0) >= 15 and first and current \
                and abs(float(current_line) - float(first_line)) < 1:
            out.append(trigger_row(TYPES[3], candidate, ctx.now,
                                   {'windMph': forecast['windMph'], 'lineMove': round(float(current_line) - float(first_line), 2)},
                                   (weather_rows.get(candidate['gameIds'][0]) or {}).get('retrievedAt') or source_at))
        projection = candidate.get('projection')
        if candidate.get('market') in ('recYds', 'rushYds') and isinstance(projection, (int, float)) \
                and isinstance(first_line, (int, float)) and first_line > 0:
            gap = (float(projection) - float(first_line)) / float(first_line)
            aligned = (candidate.get('market') == 'recYds' and candidate.get('direction') == 'over' and gap >= .10) or \
                      (candidate.get('market') == 'rushYds' and candidate.get('direction') == 'under' and gap <= -.10)
            if aligned:
                out.append(trigger_row(TYPES[4], candidate, ctx.now,
                                       {'firstLine': first_line, 'medianProjection': projection,
                                        'gapPercent': round(gap * 100, 2)}, first[0].get('retrievedAt')))
    return out


def same_book_close(trigger, ctx):
    candidate = trigger.get('candidate') or {}
    game = ctx.games.get((candidate.get('gameIds') or [None])[0]) or {}
    if not game.get('kickoff'):
        return None
    kickoff = gates.when(game['kickoff'])
    usable = [capture for capture in history(ctx, candidate) if gates.when(capture.get('retrievedAt')) <= kickoff]
    priced = [(capture, quote(capture, candidate)) for capture in usable]
    priced = [(capture, pair) for capture, pair in priced if pair and isinstance(pair[0], (int, float))]
    return priced[-1] if priced else None


def settle(ctx, now, path=LEDGER, manifest=MANIFEST):
    existing = rows(path)
    done = {row.get('triggerId') for row in existing if row.get('type') == 'grade'}
    # scoreboard.game_id's shape is simply LEAGUE-eventId; avoid another public-data dependency here.
    finals = {f"{game.get('league')}-{game.get('eventId')}": game for game in ctx.records}
    new = []
    for trigger in existing:
        if trigger.get('type') != 'trigger' or trigger.get('id') in done:
            continue
        candidate = trigger.get('candidate') or {}
        game = finals.get((candidate.get('gameIds') or [None])[0])
        if not game:
            continue
        import learn
        graded = learn.grade_row(candidate, {candidate['gameIds'][0]: game}, {})
        closing = same_book_close(trigger, ctx)
        if not graded:
            continue
        close_line = closing[1][0] if closing else None
        new.append({'type': 'grade', 'id': 'grade-' + trigger['id'], 'triggerId': trigger['id'],
                    'reasonType': trigger['reasonType'], 'gradedAt': stamp(now), 'result': graded['result'],
                    'actual': graded.get('value'), 'close': close_line,
                    'clv': learning.clv('spread' if candidate.get('marketType') == 'spread' else 'total',
                                        candidate.get('direction'), candidate.get('line'), close_line)})
    append(new, path, manifest)
    return new


def report(path=LEDGER):
    data = rows(path)
    triggers = {row['id']: row for row in data if row.get('type') == 'trigger'}
    grades = {row['triggerId']: row for row in data if row.get('type') == 'grade'}
    table = []
    for kind in TYPES:
        ids = [key for key, row in triggers.items() if row.get('reasonType') == kind]
        sample = [grades[key] for key in ids if key in grades]
        wins = sum(row.get('result') == 'win' for row in sample)
        losses = sum(row.get('result') == 'loss' for row in sample)
        pushes = sum(row.get('result') == 'push' for row in sample)
        clv = [row['clv'] for row in sample if isinstance(row.get('clv'), (int, float))]
        table.append({'type': kind, 'rows': len(ids), 'graded': len(sample),
                      'record': f'{wins}-{losses}' + (f'-{pushes}' if pushes else ''),
                      'avgClv': round(sum(clv) / len(clv), 2) if clv else None,
                      'finding': 'inconclusive' if len(sample) < 150 else 'owner review required'})
    return table


def step(candidates, ctx, now=None, path=LEDGER, manifest=MANIFEST, weather_rows=None):
    now = now or ctx.now
    graded = settle(ctx, now, path, manifest)
    found = detect(candidates, ctx, weather_rows)
    captured = append(found, path, manifest)
    return {'captured': captured, 'graded': len(graded), 'table': report(path)}
