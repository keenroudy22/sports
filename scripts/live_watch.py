"""Silent live-game observer for already-public football plays.

The five-minute Discord job calls this in shadow mode. It uses ESPN's free game
summary once per tracked game, never an odds feed or an LLM. Events are written
outside the repository for later pilot review; this module does not post.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boxscores
import gates
import pricing
import run as desk_run
import scoreboard
import x_post

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = Path.home() / '.config' / 'keenroudy' / 'live-watch.json'
CADENCE = timedelta(minutes=4)
WINDOW_AFTER = timedelta(hours=7)
MAX_GAMES = 8
MAX_EVENTS = 500


def read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    temp.replace(path)


def public_ids(log_book):
    """Only plays followers have actually seen on X or in Discord."""
    out = set()
    for entry in log_book.get('posts') or []:
        mirror = entry.get('discord') or {}
        if entry.get('kind') != 'buffer:play' or entry.get('cancelledAt') or entry.get('deletedAt'):
            continue
        if entry.get('sentAt') or mirror.get('state') == 'sent':
            out.add(entry.get('id'))
    return out


def tracked(ctx, games, log_book, now):
    rows = []
    for key in public_ids(log_book):
        pick = dict(ctx.first.get(key) or {}, **ctx.latest.get(key, {}))
        if not pick or pick.get('result') or pick.get('historicalImport'):
            continue
        starts = [gates.when(games[gid]['kickoff']) for gid in pick.get('gameIds') or [] if gid in games]
        if starts and min(starts) - timedelta(minutes=15) <= now <= max(starts) + WINDOW_AFTER:
            rows.append(pick)
    return rows


def live_record(summary, league, event_id, observed_at):
    header = summary.get('header') or {}
    competition = next(iter(header.get('competitions') or []), {})
    sides = {row.get('homeAway'): row for row in competition.get('competitors') or []}
    if set(sides) != {'home', 'away'}:
        return None
    teams = {}
    for side in ('away', 'home'):
        row = sides[side]
        score = boxscores.num(row.get('score'))
        teams[side] = {'id': str((row.get('team') or {}).get('id') or ''), 'score': score,
                       'short': (row.get('team') or {}).get('abbreviation')}
    status = (competition.get('status') or {})
    kind = status.get('type') or {}
    players = list(boxscores.box_players(summary).values())
    return {'league': league, 'eventId': str(event_id), 'away': teams['away'], 'home': teams['home'],
            'players': players, 'completed': bool(kind.get('completed')), 'state': kind.get('state'),
            'status': kind.get('shortDetail') or kind.get('detail'), 'period': status.get('period'),
            'clock': (status.get('displayClock') or status.get('clock')), 'observedAt': observed_at,
            'source': boxscores.urls(league, event_id)['summary']}


def current_value(pick, record):
    if pick.get('marketType') in ('spread', 'total'):
        graded = desk_run.grade_game_pick(pick, record)
        return graded[2] if graded else None
    athlete = str(pick.get('athleteId') or '')
    player = next((row for row in record.get('players') or [] if str(row.get('id')) == athlete), None)
    return scoreboard.settle_value(player, pricing.market_of(pick)) if player else None


def threshold(pick):
    market = pricing.market_of(pick)
    return {'passYds': 25, 'rushYds': 10, 'recYds': 10, 'rec': 1,
            'car': 2, 'att': 2, 'cmp': 2}.get(market, 5)


def progress(pick, record):
    value = current_value(pick, record)
    if value is None or not isinstance(pick.get('line'), (int, float)):
        return {'state': 'waiting-for-stat', 'value': value}
    line = float(pick['line'])
    direction = str(pick.get('direction') or '').lower()
    completed = record.get('completed')
    if pick.get('marketType') in ('spread', 'total'):
        graded = desk_run.grade_game_pick(pick, record)
        result = graded[0] if graded else None
        state = f"final-{result}" if completed and result else f"currently-{result}" if result else 'live'
        return {'state': state, 'value': value, 'line': line, 'remaining': None}
    won = value > line if direction == 'over' else value < line
    if completed:
        result = 'win' if won else 'push' if value == line else 'loss'
        return {'state': f'final-{result}', 'value': value, 'line': line, 'remaining': 0 if won else abs(line - value)}
    if direction == 'over' and value > line:
        state = 'hit-early'
    else:
        distance = math.floor(line) + 1 - value if direction == 'over' else value - line
        state = 'close' if 0 <= distance <= threshold(pick) else 'live'
    return {'state': state, 'value': value, 'line': line,
            'remaining': max(0, math.floor(line) + 1 - value) if direction == 'over' else max(0, value - line)}


def shaped_legs(pick):
    if not pick.get('legs'):
        return [(pick.get('id'), (pick.get('gameIds') or [None])[0], pick)]
    return [(leg.get('id') or f"{pick.get('id')}:leg:{i}", leg.get('gameId'),
             {**desk_run.leg_pick(leg), 'title': leg.get('title')})
            for i, leg in enumerate(pick.get('legs') or [])]


def event(kind, pick, leg_id, game_id, status, record, now):
    stamp = boxscores.stamp(now)
    return {'id': f"{pick['id']}:{leg_id}:{kind}:{stamp}", 'kind': kind, 'pickId': pick['id'], 'legId': leg_id,
            'gameId': game_id, 'at': boxscores.stamp(now), 'status': status,
            'gameStatus': record.get('status'), 'sourceObservedAt': record.get('observedAt'),
            'source': record.get('source')}


def run_shadow(ctx=None, games=None, log_book=None, now=None, state_path=DEFAULT_STATE, fetch=boxscores.fetch_json,
               persist=True, log=print):
    now = now or datetime.now(timezone.utc)
    state = read(state_path)
    last = gates.when(state['lastPollAt']) if state.get('lastPollAt') else None
    if last and timedelta(0) <= now - last < CADENCE:
        return {'polled': 0, 'events': [], 'reason': 'cadence'}
    ctx = ctx or gates.Stores().as_of(now)
    games = games or ctx.games
    log_book = log_book or x_post.load_log()
    picks = tracked(ctx, games, log_book, now)
    wanted = []
    for pick in picks:
        wanted += [gid for gid in pick.get('gameIds') or [] if gid in games]
    wanted = list(dict.fromkeys(wanted))[:MAX_GAMES]
    records = {}
    for gid in wanted:
        game = games[gid]
        try:
            summary = fetch(boxscores.urls(game['league'], gid.split('-', 1)[1])['summary'])
            record = live_record(summary, game['league'], gid.split('-', 1)[1], boxscores.stamp(now))
            if record:
                records[gid] = record
        except Exception as error:
            log(f'live shadow: {gid} unavailable ({type(error).__name__})')
    previous = state.get('picks') if isinstance(state.get('picks'), dict) else {}
    active={p['id'] for p in picks}
    # A feed outage is not a state transition. Retain the last observation so a
    # restored feed cannot emit the same early hit a second time.
    current_state = {key:row for key,row in previous.items() if row.get('pickId') in active}
    emitted = []
    for pick in picks:
        for leg_id, gid, shaped in shaped_legs(pick):
            record = records.get(gid)
            if not record:
                continue
            status = progress(shaped, record)
            key = f"{pick['id']}:{leg_id}"
            before = previous.get(key) or {}
            current_state[key] = {**status, 'pickId': pick['id'], 'legId': leg_id, 'gameId': gid,
                                  'observedAt': record['observedAt'], 'gameStatus': record.get('status'),
                                  'previousObservedAt': before.get('observedAt'),
                                  'previousGameStatus': before.get('gameStatus'),
                                  'previousValue': before.get('value'),
                                  'live': record.get('state') == 'in' and not record.get('completed'),
                                  'source': record['source']}
            if status['state'] != before.get('state') and status['state'] in ('close', 'hit-early', 'final-win', 'final-loss', 'final-push'):
                emitted.append(event(status['state'], pick, leg_id, gid, status, record, now))
            if before.get('state') == 'hit-early' and status['state'] not in ('hit-early', 'final-win'):
                emitted.append(event('correction', pick, leg_id, gid, status, record, now))
    known = {row.get('id') for row in state.get('events') or []}
    emitted = [row for row in emitted if row['id'] not in known]
    reconciled=state.get('settlements') or {}
    for key in public_ids(log_book):
        final=ctx.latest.get(key) or {}
        if final.get('result') in ('win','loss','push','void'):
            reconciled[key]={'result':final['result'],'settledAt':final.get('settledAt'),
                             'source':'append-only published settlement'}
    state.update({'mode': 'shadow', 'lastPollAt': boxscores.stamp(now), 'gamesPolled': len(records),
                  'health':{'requested':len(wanted),'successful':len(records),'unavailable':len(wanted)-len(records)},
                  'settlements':reconciled,
                  'picks': current_state, 'events': ((state.get('events') or []) + emitted)[-MAX_EVENTS:]})
    if persist:
        write(state_path, state)
    for row in emitted:
        log(f"live shadow: {row['pickId']} {row['kind']} ({row['gameStatus'] or 'live'})")
    return {'polled': len(records), 'events': emitted, 'tracked': len(current_state)}


if __name__ == '__main__':
    result = run_shadow()
    print(json.dumps(result, indent=1, default=str))
