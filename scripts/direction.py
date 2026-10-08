"""Kook'n direction rules: bounded course corrections the weekly learning run makes on its own. Stdlib only.

The owner, 2026-10-07: "If ... trends / bets aren't hitting at the rate we want we change directions after x."
DIRECTION-RULES is their standing approval for the moves below, and only these. A move may tighten, pause, shift
weight between already-approved categories, or restore what it tightened once results recover. It never loosens a
gate below its Oct 7 baseline, never adds a market, sport, category, post slot or paid service, never changes how
the record counts and never touches a published play: it writes only data/learning/policy.json.

  evaluate(policy, evidence, now)   pure: the moves the evidence calls for, each with its trigger numbers, the
                                    action, its undo condition or expiry and one plain sentence for the owner
  apply(policy, moves, now)         records them in policy['direction'] with dated entries in policy['history']
  edge_raise / paused / priority / weekend_cap / fun_shape / fun_legs / climb_rules / flagged / prep_rules
                                    the readers the gates, the card ranking, the fun tickets and the Climb use; each
                                    clamps what it reads, so even a hand-edited policy cannot go below the baseline

Windows count graded plays at captured prices from the learning store. Closing line value (CLV) is how far the
market moved toward our side by kickoff; a rule that names CLV acts only when CLV was measured on at least half of
its window. Each family is judged only on what came after its own last change, so a second run on the same
evidence moves nothing. Each owner ping names the move's key. The ping is a one-way phone notification and cannot
take a reply: the owner undoes a move by telling Codex "undo KEY", and Codex runs `direction.py veto KEY` and deploys.

  python scripts/direction.py status          what the next weekly run would change (read-only)
  python scripts/direction.py veto KEY        undo one move and block it for four weeks
"""
import argparse
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pricing

EASTERN = ZoneInfo('America/New_York')
APPROVED = '2026-10-07'
REPORT_LINK = 'https://github.com/keenroudy22/sports/blob/main/data/learning/REPORT.md'

# Best bets, per segment (league x market).
RAISE_MIN_N, RAISE_GAP, RAISE_STEP, RAISE_MAX = 20, 0.05, 2.0, 6.0
PAUSE_MIN_N, PAUSE_UNITS = 30, -5.0
RESTORE_MIN_N = 30
PRIORITY_MIN_N, PRIORITY_UNITS = 30, 3.0
# Rules that say a refused candidate was a near miss in shadow; mirrors learn.THRESHOLD_RULES plus the card cap.
SHADOW_RULES = {'straight_value', 'lean_edge', 'prop_raw_edge', 'prop_calibrated_value', 'learned_pause', 'bar-4', 'card_cap'}
# The whole card.
CARD_WINDOW, CARD_UNITS, CARD_CAP, CARD_DAYS, CARD_RESTORE_N, CARD_FRESH = 60, -8.0, 3, 14, 30, 10
# Fun tickets (0.25u each).
FUN_STAKE, FUN_ZERO, FUN_UNITS_N, FUN_UNITS, FUN_DAYS, FUN_UNDO_N, FUN_UNDO_WINS, FUN_FRESH = 0.25, 12, 20, -3.0, 14, 10, 2, 4
FUN_SHAPE = {'odds': (300, 800), 'legs': (3, 4), 'skipPausedSegments': True}
# The Climb. The stricter pool keeps the ladder's own leg chance (0.83), leg prices and ticket price (-180 to -130)
# and leaves out every leg from a segment that is paused or carries a raised edge bar (`flagged`). An earlier draft
# raised the leg chance to 0.86 with two books agreeing; with the ladder's six-point model cap that left only legs at
# -400 to -411 and built no rung on the stored prices, so a strict Climb could never reach step 3 and end itself.
CLIMB_EARLY_STEP, CLIMB_UNDO_STEP, CLIMB_DRY_DAYS = 2, 3, 5
CLIMB_MARKETS = ('recYds', 'rushYds', 'rec', 'passYds')        # ladder.MARKETS (a test keeps the two equal)
CLIMB_LEAGUES = ('NFL', 'CFB')
CLIMB_POOL = 'no leg from a segment that is paused or has a raised edge bar; still -180 to -130 together'
# The Prep List (computed now; its builder reads prep_rules() once it ships).
PREP_N, PREP_LOW, PREP_RESTORE = 40, 0.60, 0.70
PREP_STAT_N, PREP_STAT_LOW, PREP_STAT_RESTORE, PREP_STAT_DAYS = 20, 0.50, 0.65, 28
PREP_GROUP_MIN, PREP_GAP, PREP_GAP_END = 10, 0.10, 0.05
PREP_BASE = {'short': 0.80, 'lastTen': 8, 'season': 0.70,
             'floors': {'rec': 2.5, 'recYds': 29.5, 'rushYds': 39.5, 'passYds': 189.5}}
PREP_RAISED = {'short': 0.85, 'lastTen': 9, 'season': 0.75}
PREP_FLOOR_STEP = {'rec': 1.0, 'recYds': 10.0, 'rushYds': 10.0, 'passYds': 25.0}
# Calibration drift (report and flag; the shrink itself already re-fits weekly).
CAL_MIN_N, CAL_GAP = 50, 0.05
VETO_DAYS = 28
RESULTS = ('win', 'loss', 'push')
MARKET_WORDS = {'total': 'totals', 'spread': 'spreads', 'moneyline': 'moneylines', 'rec': 'receptions',
                'recYds': 'rec yds', 'rushYds': 'rush yds', 'passYds': 'pass yds', 'car': 'carries',
                'att': 'pass attempts', 'cmp': 'completions'}


# ------------------------------------------------------------------ small helpers

def when(value):
    try:
        moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def started(since, now):
    """A move counts from its own stamp on: an evaluation (or a replay) before it never sees it."""
    moment = when(since)
    return now is None or moment is None or moment <= now


def expired(until, now, missing=False):
    """Has a timed move run out? A timed move without a readable end counts as ended when `missing` says so."""
    moment = when(until)
    return missing if moment is None else moment <= now


def after(rows, since, field='decidedAt'):
    if not since:
        return list(rows)
    return [r for r in rows if str(r.get(field) or '') >= since]


def label(segment):
    """'NFL/total' -> 'NFL totals'; 'CFB/prop:recYds' -> 'CFB rec yds'."""
    league, _, market = str(segment).partition('/')
    market = market.split(':', 1)[1] if market.startswith('prop:') else market
    return f"{league} {MARKET_WORDS.get(market, market)}"


def priced(row):
    odds = row.get('odds')
    return isinstance(odds, (int, float)) and abs(odds) >= 100


def tally(rows, stake=1.0):
    """W-L-P, units at the captured prices, hit rate, the average break-even and CLV (None when under half measured)."""
    wins = losses = pushes = 0
    units, evens, clvs = 0.0, [], []
    for row in rows:
        result, odds = row.get('result'), row.get('odds')
        if priced(row):
            evens.append(pricing.break_even(int(odds)))
        if result == 'win':
            wins += 1
            units += stake * pricing.payout(int(odds)) if priced(row) else 0.0
        elif result == 'loss':
            losses += 1
            units -= stake
        elif result in ('push', 'void'):
            pushes += 1
        if isinstance(row.get('clv'), (int, float)):
            clvs.append(float(row['clv']))
    decided = wins + losses
    return {'n': len(rows), 'win': wins, 'loss': losses, 'push': pushes, 'units': round(units, 2),
            'hitRate': round(wins / decided, 3) if decided else None,
            'breakEven': round(statistics.fmean(evens), 3) if evens else None,
            'clv': round(statistics.fmean(clvs), 2) if clvs and 2 * len(clvs) >= len(rows) else None,
            'clvN': len(clvs)}


def record_text(t):
    text = f"{t['win']}-{t['loss']}" + (f"-{t['push']}" if t['push'] else '')
    return text


def pct(value):
    return f"{100 * value:.0f}%" if isinstance(value, (int, float)) else 'n/a'


def clv_text(value):
    return f"CLV {value:+.2f}" if isinstance(value, (int, float)) else 'CLV unmeasured'


def official(rows):
    """Graded best bets at captured prices: published, straight, priced."""
    return [r for r in rows if r.get('decision') == 'published' and r.get('result') in RESULTS and priced(r)
            and not r.get('legs') and r.get('segment') and not str(r['segment']).endswith('/parlay')]


def shadow(rows):
    """Graded candidates a direction pause refused that otherwise only missed a threshold or the card: one per
    segment, game, side and player (the earliest), so a line seen at every run counts once."""
    chosen = {}
    for row in sorted(rows, key=lambda r: (str(r.get('decidedAt') or ''), str(r.get('id') or ''))):
        rules = set(row.get('rules') or [])
        if row.get('decision') != 'refused' or row.get('result') not in RESULTS or not priced(row) \
                or 'learned_pause' not in rules or not rules <= SHADOW_RULES:
            continue
        games = tuple(row.get('gameIds') or ())
        key = (row.get('segment'), games[0] if games else row.get('id'), row.get('direction') or row.get('side'),
               row.get('athleteId'))
        chosen.setdefault(key, row)
    return list(chosen.values())


def ordered(rows):
    return sorted(rows, key=lambda r: (str(r.get('kickoff') or r.get('decidedAt') or ''), str(r.get('id') or '')))


def state_of(policy):
    """policy['direction'] with every part present; never None."""
    stored = (policy or {}).get('direction')
    state = dict(stored) if isinstance(stored, dict) else {}
    for key in ('segments', 'card', 'funTickets', 'climb', 'prepList', 'calibrationFlags', 'vetoes'):
        if not isinstance(state.get(key), dict):
            state[key] = {}
    return state


def vetoed(state, key, now):
    entry = state['vetoes'].get(key)
    return isinstance(entry, dict) and started(entry.get('at'), now) and not expired(entry.get('until'), now, missing=True)


def move(key, rule, segment, knob, start, end, trigger, action, undo, sentence, tightens, expires=None, **extra):
    return dict({'key': key, 'rule': rule, 'segment': segment, 'knob': knob, 'from': start, 'to': end,
                 'trigger': trigger, 'action': action, 'undo': undo, 'expires': expires, 'sentence': sentence,
                 'tightens': tightens}, **extra)


def veto_tail(key):
    """How the owner undoes a move. The ping is a one-way notification, so it names who acts and never asks for a
    reply to the ping itself."""
    return f' To undo, tell Codex: undo {key}.'


# ------------------------------------------------------------------ 1. best bets, per segment

def segment_moves(state, rows, now):
    best = defaultdict(list)
    for row in official(rows):
        best[row['segment']].append(row)
    refused = defaultdict(list)
    for row in rows:
        if row.get('decision') == 'refused' and row.get('segment'):
            refused[row['segment']].append(row)
    moves = []
    for segment in sorted(set(best) | set(state['segments'])):
        seg = state['segments'].get(segment) if isinstance(state['segments'].get(segment), dict) else {}
        name, raised = label(segment), clamp_raise(seg.get('raise'))
        is_paused = bool(seg.get('paused')) and started(seg.get('pauseSince'), now)
        long = tally(after(best[segment], seg.get('pauseSince')))
        pausing = False
        if not is_paused:
            if long['n'] >= PAUSE_MIN_N and long['units'] <= PAUSE_UNITS and long['clv'] is not None and long['clv'] < 0 \
                    and not vetoed(state, f'pause:{segment}', now):
                pausing = True
                moves.append(move(f'pause:{segment}', 'segment-pause', segment, 'direction.paused', False, True, long,
                                  f'Stop {name} as a best bet; it stays on the board and the Prep List as research and '
                                  f'keeps running in shadow.',
                                  f'{RESTORE_MIN_N} shadow plays at or above break-even with CLV above 0 restore it at a raised bar.',
                                  f"Paused {name} as a best bet ({record_text(long)}, {long['units']:+.1f}u, "
                                  f"{clv_text(long['clv'])}). Still on the board as research."
                                  f"{veto_tail('pause:' + segment)}", True))
        else:
            # Window first, then one row per game and side: older refusals never stand in for newer evidence.
            ghost = tally(shadow(after(refused[segment], seg.get('pauseSince'))))
            if ghost['n'] >= RESTORE_MIN_N and ghost['hitRate'] is not None and ghost['breakEven'] is not None \
                    and ghost['hitRate'] >= ghost['breakEven'] and ghost['clv'] is not None and ghost['clv'] > 0:
                bar = min(max(raised, RAISE_STEP), RAISE_MAX)
                moves.append(move(f'pause:{segment}', 'segment-restore', segment, 'direction.paused', True, False, ghost,
                                  f'Restore {name} as a best bet at a +{bar:g} point edge bar.',
                                  'The edge bar steps back 2 points after 20 more at or above break-even with CLV of at least 0.',
                                  f"Restored {name} as a best bet at a +{bar:g} edge bar (shadow {record_text(ghost)}, "
                                  f"{pct(ghost['hitRate'])} vs {pct(ghost['breakEven'])} break-even, {clv_text(ghost['clv'])}).",
                                  False, raiseTo=bar))
        if not is_paused and not pausing:
            window = tally(after(best[segment], seg.get('raiseSince')))
            ready = window['n'] >= RAISE_MIN_N and None not in (window['hitRate'], window['breakEven'], window['clv'])
            if ready and window['hitRate'] <= window['breakEven'] - RAISE_GAP and window['clv'] <= 0 and raised < RAISE_MAX \
                    and not vetoed(state, f'raise:{segment}', now):
                bar = min(raised + RAISE_STEP, RAISE_MAX)
                moves.append(move(f'raise:{segment}', 'edge-raise', segment, 'direction.edgeRaise', raised, bar, window,
                                  f'Require {name} best bets to clear their price by {bar:g} more points than the Oct 7 rule.',
                                  'The next 20 at or above break-even with CLV of at least 0 step it back 2 points.',
                                  f"Raised {name}' edge bar to +{bar:g} points ({record_text(window)}, {pct(window['hitRate'])} "
                                  f"vs {pct(window['breakEven'])} break-even, {clv_text(window['clv'])})."
                                  f"{veto_tail('raise:' + segment)}", True))
            elif ready and raised > 0 and window['hitRate'] >= window['breakEven'] and window['clv'] >= 0:
                bar = max(raised - RAISE_STEP, 0.0)
                moves.append(move(f'raise:{segment}', 'edge-step-back', segment, 'direction.edgeRaise', raised, bar, window,
                                  f'Step {name} back to +{bar:g} points over the Oct 7 rule.',
                                  'A new 20-play slump under break-even raises it again.',
                                  f"Stepped {name}' edge bar back to +{bar:g} ({record_text(window)}, {pct(window['hitRate'])} "
                                  f"vs {pct(window['breakEven'])} break-even, {clv_text(window['clv'])}).", False))
        first = bool(seg.get('priority'))
        good = long['n'] >= PRIORITY_MIN_N and long['units'] >= PRIORITY_UNITS and long['clv'] is not None and long['clv'] >= 0
        if not first and good and not is_paused and not pausing and not vetoed(state, f'priority:{segment}', now):
            moves.append(move(f'priority:{segment}', 'segment-priority', segment, 'direction.priority', False, True, long,
                              f'{name} ranks first when the card fills, inside the existing caps (caps never rise).',
                              f'It ends when the segment falls under +{PRIORITY_UNITS:g}u or its CLV turns negative.',
                              f"{name} now ranks first when the card fills ({record_text(long)}, {long['units']:+.1f}u, "
                              f"{clv_text(long['clv'])}). Caps unchanged.{veto_tail('priority:' + segment)}", False))
        elif first and (not good or is_paused or pausing):
            moves.append(move(f'priority:{segment}', 'segment-priority-end', segment, 'direction.priority', True, False, long,
                              f'{name} goes back to ordinary ranking.', 'It returns at +3u with CLV of at least 0 over 30.',
                              f"{name} no longer ranks first ({record_text(long)}, {long['units']:+.1f}u, "
                              f"{clv_text(long['clv'])}).", False))
    return moves


def clamp_raise(value):
    return min(max(float(value), 0.0), RAISE_MAX) if isinstance(value, (int, float)) else 0.0


# ------------------------------------------------------------------ 1b. the whole card

def card_moves(state, rows, now):
    plays = ordered(official(rows))
    last = tally(plays[-CARD_WINDOW:])
    card = state['card']
    active = isinstance(card.get('weekendCap'), (int, float))
    since = card.get('since')
    post = tally(after(plays, since)) if since else None
    fresh = since is None or (post['n'] >= CARD_FRESH and post['units'] < 0)
    slump = bool(plays) and last['units'] <= CARD_UNITS
    until = stamp(now + timedelta(days=CARD_DAYS))
    day = (now + timedelta(days=CARD_DAYS)).astimezone(EASTERN)
    cut = lambda rule, start: move('card', rule, 'card', 'direction.weekendCap', start, CARD_CAP, last,
                                   f'Weekend card ceiling {CARD_CAP} instead of 5 until {day:%b %-d}; weekdays unchanged.',
                                   f'The next {CARD_RESTORE_N} straight plays at or above break-even restore 5 early.',
                                   f"Cut the weekend card from 5 to {CARD_CAP} best bets until {day:%b %-d} (last "
                                   f"{last['n']} straight plays {record_text(last)}, {last['units']:+.1f}u). "
                                   f"Weekdays unchanged.{veto_tail('card')}", True, expires=until)
    if not active:
        return [cut('card-cap', 5)] if slump and fresh and not vetoed(state, 'card', now) else []
    if post and post['n'] >= CARD_RESTORE_N and post['hitRate'] is not None and post['breakEven'] is not None \
            and post['hitRate'] >= post['breakEven']:
        return [move('card', 'card-cap-restore', 'card', 'direction.weekendCap', CARD_CAP, 5, post,
                     'Weekend card ceiling back to 5.', 'A new -8u slump over 60 cuts it again.',
                     f"Weekend card back to 5 best bets (since the cut {record_text(post)}, {pct(post['hitRate'])} vs "
                     f"{pct(post['breakEven'])} break-even).", False)]
    if expired(card.get('until'), now, missing=True):
        if slump and fresh and not vetoed(state, 'card', now):
            return [cut('card-cap-extend', CARD_CAP)]
        return [move('card', 'card-cap-restore', 'card', 'direction.weekendCap', CARD_CAP, 5, post or last,
                     'Weekend card ceiling back to 5: the two weeks are up.', 'A new -8u slump over 60 cuts it again.',
                     'Weekend card back to 5 best bets: the two weeks are up.', False)]
    return []


# ------------------------------------------------------------------ 2. fun tickets and the Climb

def fun_moves(state, tickets, now):
    settled = sorted((t for t in tickets if t.get('result') in RESULTS + ('void',)),
                     key=lambda t: (str(t.get('publishedAt') or ''), str(t.get('id') or '')))
    twelve, twenty = settled[-FUN_ZERO:], tally(settled[-FUN_UNITS_N:], FUN_STAKE)
    zero = len(twelve) >= FUN_ZERO and not any(t['result'] == 'win' for t in twelve)
    losing = zero or (bool(settled) and twenty['units'] <= FUN_UNITS)
    fun = state['funTickets']
    since = fun.get('since')
    post = after(settled, since, 'publishedAt') if since else []
    wins = lambda rows: sum(1 for t in rows if t['result'] == 'win')
    fresh = since is None or (len(post) >= FUN_FRESH and wins(post) < FUN_UNDO_WINS)
    trigger = dict(tally(twelve, FUN_STAKE), last12Wins=wins(twelve), last20Units=twenty['units'], last20N=twenty['n'])
    until = stamp(now + timedelta(days=FUN_DAYS))
    day = (now + timedelta(days=FUN_DAYS)).astimezone(EASTERN)
    why = f"0 wins in the last {FUN_ZERO}" if zero else f"{twenty['units']:+.2f}u over the last {twenty['n']}"
    shorten = lambda rule: move('fun', rule, 'funTickets', 'direction.funTickets', 'standard', 'shorter', trigger,
                                f'Until {day:%b %-d} a longshot is +300 to +800 with 3-4 legs, and no fun-ticket leg '
                                f'(longshot or easy parlay) comes from a segment paused as a best bet; none that fits '
                                f'means none that day.',
                                f'{FUN_UNDO_WINS} wins in the next {FUN_UNDO_N} tickets end it early.',
                                f"Fun tickets go shorter until {day:%b %-d}: +300 to +800, 3-4 legs ({why})."
                                f"{veto_tail('fun')}",
                                True, expires=until)
    if not fun.get('active'):
        return [shorten('fun-short')] if losing and fresh and not vetoed(state, 'fun', now) else []
    if wins(post[:FUN_UNDO_N]) >= FUN_UNDO_WINS:
        return [move('fun', 'fun-short-end', 'funTickets', 'direction.funTickets', 'shorter', 'standard',
                     tally(post, FUN_STAKE), 'Fun tickets back to their usual shape.', 'A new cold run shortens them again.',
                     f"Fun tickets back to their usual shape ({wins(post[:FUN_UNDO_N])} wins in the next "
                     f"{min(len(post), FUN_UNDO_N)}).", False)]
    if expired(fun.get('until'), now, missing=True):
        if losing and fresh and not vetoed(state, 'fun', now):
            return [shorten('fun-short-extend')]
        return [move('fun', 'fun-short-end', 'funTickets', 'direction.funTickets', 'shorter', 'standard', trigger,
                     'Fun tickets back to their usual shape: the two weeks are up.', 'A new cold run shortens them again.',
                     'Fun tickets back to their usual shape: the two weeks are up.', False)]
    return []


def climb_moves(state, climbs, rungs, now, policy=None):
    climb = state['climb']
    since = climb.get('since')
    if not climb.get('strict'):
        ended = sorted((c for c in climbs if c.get('endedAt') and (not since or str(c['endedAt']) >= since)),
                       key=lambda c: str(c['endedAt']))[-2:]
        early = len(ended) == 2 and all(isinstance(c.get('lostAt'), int) and c['lostAt'] <= CLIMB_EARLY_STEP for c in ended)
        if early and not vetoed(state, 'climb', now):
            steps = ' and '.join(str(c['lostAt']) for c in ended)
            held = climb_held_back(policy, now)
            today = (f"today that leaves out {', '.join(label(s) for s in held)}" if held
                     else 'no Climb segment is paused or raised today, so today\'s pool is unchanged')
            return [move('climb', 'climb-strict', 'climb', 'direction.climbPool', 'standard', 'strict',
                         {'climbs': ended, 'heldBack': held},
                         f'The next Climb takes {CLIMB_POOL}; leg chance and prices stay at the ladder\'s own rules.',
                         'It ends when a climb reaches step 3.',
                         f"The next Climb uses the stricter leg pool: no leg from a paused or raised segment, still "
                         f"-180 to -130 together ({today}; the last two climbs lost at step {steps})."
                         f"{veto_tail('climb')}", True)]
        return []
    reached = [r for r in rungs if isinstance(r.get('step'), int) and r['step'] >= CLIMB_UNDO_STEP
               and since and str(r.get('publishedAt') or '') >= since]
    if reached:
        return [move('climb', 'climb-strict-end', 'climb', 'direction.climbPool', 'strict', 'standard',
                     {'reached': reached[0].get('id'), 'step': reached[0]['step']}, 'The Climb leg pool returns to normal.',
                     'Two early losses in a row make it stricter again.',
                     f"The Climb leg pool is back to normal: a climb reached step {reached[0]['step']}.", False)]
    return []


def climb_held_back(policy, now=None):
    """The Climb's segments (its leagues and markets) the stricter pool would leave out right now."""
    return [f'{league}/prop:{market}' for league in CLIMB_LEAGUES for market in CLIMB_MARKETS
            if flagged(policy, f'{league}/prop:{market}', now)]


def climb_dry_spell(days, today=None):
    """Report only (no automatic loosening): consecutive days with 2+ games in a league the Climb may use, counted
    back from the latest, on which no rung was published and none was open. A day with a rung ends the count."""
    count = 0
    for day in sorted(days, key=lambda d: d['date'], reverse=True):
        if today and day['date'] >= today:
            continue
        if day.get('rung'):
            break
        if day.get('blocked') or max((day.get('games') or {}).values() or [0]) < 2:
            continue
        count += 1
    return count


# ------------------------------------------------------------------ 3. the Prep List

def hit_rate(rows):
    return sum(1 for r in rows if r.get('hit')) / len(rows) if rows else None


def prep_moves(state, rows, now):
    prep = state['prepList']
    visible = sorted((r for r in rows if not r.get('shadow')), key=lambda r: str(r.get('at') or ''))
    everything = sorted(rows, key=lambda r: str(r.get('at') or ''))
    moves = []
    if not prep.get('raised'):
        last = visible[-PREP_N:]
        rate = hit_rate(last)
        if len(last) >= PREP_N and rate < PREP_LOW and not vetoed(state, 'prep', now):
            moves.append(move('prep', 'prep-raise', 'prepList', 'direction.prepList', 'baseline', 'raised',
                              {'n': len(last), 'hitRate': round(rate, 3)},
                              'Prep List rows need 85% (5-9 games) or 9 of 10 and 75% for the season, and each line floor rises one step.',
                              f'{pct(PREP_RESTORE)} or better over the next {PREP_N} rows restores the baseline.',
                              f"Raised the Prep List bar: 85% or 9 of 10, higher line floors (last {len(last)} rows hit "
                              f"{pct(rate)}).{veto_tail('prep')}", True))
    else:
        later = after(visible, prep.get('since'), 'at')
        rate = hit_rate(later)
        if len(later) >= PREP_N and rate >= PREP_RESTORE:
            moves.append(move('prep', 'prep-restore', 'prepList', 'direction.prepList', 'raised', 'baseline',
                              {'n': len(later), 'hitRate': round(rate, 3)}, 'Prep List thresholds back to the baseline.',
                              f'Under {pct(PREP_LOW)} over 40 raises them again.',
                              f"Prep List thresholds back to baseline (next {len(later)} rows hit {pct(rate)}).", False))
    dropped = prep.get('dropped') if isinstance(prep.get('dropped'), dict) else {}
    for stat in sorted({r.get('stat') for r in everything if r.get('stat')} | set(dropped)):
        entry = dropped.get(stat) if isinstance(dropped.get(stat), dict) else None
        key = f'prep-stat:{stat}'
        if entry is None:
            last = [r for r in visible if r.get('stat') == stat][-PREP_STAT_N:]
            rate = hit_rate(last)
            if len(last) >= PREP_STAT_N and rate < PREP_STAT_LOW and not vetoed(state, key, now):
                day = (now + timedelta(days=PREP_STAT_DAYS)).astimezone(EASTERN)
                moves.append(move(key, 'prep-drop-stat', 'prepList', 'direction.prepDropped', False, True,
                                  {'stat': stat, 'n': len(last), 'hitRate': round(rate, 3)},
                                  f'Leave {MARKET_WORDS.get(stat, stat)} off the Prep List until {day:%b %-d}; keep grading it in shadow.',
                                  f'{pct(PREP_STAT_RESTORE)} in shadow over {PREP_STAT_N} brings it back early.',
                                  f"Dropped {MARKET_WORDS.get(stat, stat)} from the Prep List for 4 weeks (last {len(last)} "
                                  f"hit {pct(rate)}).{veto_tail(key)}", True, expires=stamp(now + timedelta(days=PREP_STAT_DAYS))))
            continue
        ghost = [r for r in after(everything, entry.get('since'), 'at') if r.get('stat') == stat]
        rate = hit_rate(ghost)
        recovered = len(ghost) >= PREP_STAT_N and rate >= PREP_STAT_RESTORE
        if recovered or expired(entry.get('until'), now):
            moves.append(move(key, 'prep-restore-stat', 'prepList', 'direction.prepDropped', True, False,
                              {'stat': stat, 'n': len(ghost), 'hitRate': round(rate, 3) if rate is not None else None},
                              f'{MARKET_WORDS.get(stat, stat)} returns to the Prep List.', 'Under 50% over 20 drops it again.',
                              f"{MARKET_WORDS.get(stat, stat).capitalize()} back on the Prep List "
                              f"({'shadow hit ' + pct(rate) if recovered else 'four weeks are up'}).",
                              False))
    window = everything[-PREP_N:] if prep.get('clearsOnly') is not True else after(everything, prep.get('clearsSince'), 'at')
    clears = [r for r in window if r.get('priceCheck') == 'clears']
    history = [r for r in window if r.get('priceCheck') == 'history']
    if len(window) >= PREP_N and len(clears) >= PREP_GROUP_MIN and len(history) >= PREP_GROUP_MIN:
        gap = hit_rate(clears) - hit_rate(history)
        numbers = {'n': len(window), 'clears': round(hit_rate(clears), 3), 'historyOnly': round(hit_rate(history), 3)}
        if not prep.get('clearsOnly') and gap >= PREP_GAP and not vetoed(state, 'prep-clears', now):
            moves.append(move('prep-clears', 'prep-clears-only', 'prepList', 'direction.prepClearsOnly', False, True, numbers,
                              'Show only Prep List rows where my price check clears; grade the rest in shadow.',
                              'A gap under 5 points over the next 40 shows both again.',
                              f"Prep List shows only rows my price check clears (clears {pct(numbers['clears'])} vs "
                              f"history only {pct(numbers['historyOnly'])}).{veto_tail('prep-clears')}", True))
        elif prep.get('clearsOnly') and gap < PREP_GAP_END:
            moves.append(move('prep-clears', 'prep-clears-end', 'prepList', 'direction.prepClearsOnly', True, False, numbers,
                              'Prep List shows both kinds of rows again.', 'A 10-point gap over 40 narrows it again.',
                              f"Prep List shows history-only rows again (gap {100 * gap:+.0f} points).", False))
    return moves


# ------------------------------------------------------------------ calibration drift (flag only)

def calibration_moves(state, props, calibration):
    """Said-vs-hit gaps over 5 points in any 10-point band with 50+ graded projections, per league and market."""
    groups = defaultdict(list)
    for row in props or []:
        league = row.get('league')
        k = ((calibration or {}).get(f'{league}/prop') or {}).get('k')
        raw = row.get('raw')
        if not isinstance(raw, (int, float)):
            continue
        chance = 0.5 + k * (raw - 0.5) if isinstance(k, (int, float)) else raw
        band = min(int(chance * 10), 9) * 10
        groups[(f"{league}/prop:{row.get('market')}", band)].append((chance, bool(row.get('won'))))
    flags = {}
    for (segment, band), values in sorted(groups.items()):
        if len(values) < CAL_MIN_N:
            continue
        said = statistics.fmean(v[0] for v in values)
        hit = sum(v[1] for v in values) / len(values)
        if abs(said - hit) > CAL_GAP and segment not in flags:
            flags[segment] = {'band': f'{band}-{band + 10}%', 'said': round(said, 3), 'hit': round(hit, 3), 'n': len(values)}
    old = state['calibrationFlags']
    bands = lambda found: {segment: (flag or {}).get('band') for segment, flag in (found or {}).items()}
    if bands(flags) == bands(old):          # the same bands still off: no new entry just because the figures moved
        return []
    named = '; '.join(f"{label(s)} said {pct(f['said'])}, hit {pct(f['hit'])} in the {f['band']} band (n {f['n']})"
                      for s, f in flags.items()) or 'no band is off by more than 5 points'
    return [move('calibration', 'calibration-drift', 'calibration', 'direction.calibrationFlags', old, flags,
                 {'flags': flags}, 'Flag in the Monday review; the shrink already re-fits every week.',
                 'Automatic.', f"Calibration check: {named}.", False, notify=False)]


# ------------------------------------------------------------------ vetoes

def veto_moves(state, now):
    """Undo any move the owner vetoed after it was made."""
    moves = []
    for key, entry in sorted(state['vetoes'].items()):
        if not vetoed(state, key, now):
            continue
        family, _, rest = key.partition(':')
        seg = state['segments'].get(rest) if isinstance(state['segments'].get(rest), dict) else {}
        current = {'raise': (clamp_raise(seg.get('raise')) > 0, seg.get('raiseSince'), clamp_raise(seg.get('raise')), 0.0),
                   'pause': (bool(seg.get('paused')), seg.get('pauseSince'), True, False),
                   'priority': (bool(seg.get('priority')), seg.get('prioritySince'), True, False),
                   'card': (isinstance(state['card'].get('weekendCap'), (int, float)), state['card'].get('since'), CARD_CAP, 5),
                   'fun': (bool(state['funTickets'].get('active')), state['funTickets'].get('since'), 'shorter', 'standard'),
                   'climb': (bool(state['climb'].get('strict')), state['climb'].get('since'), 'strict', 'standard'),
                   'prep': (bool(state['prepList'].get('raised')), state['prepList'].get('since'), 'raised', 'baseline'),
                   'prep-clears': (state['prepList'].get('clearsOnly') is True, state['prepList'].get('clearsSince'), True, False),
                   'prep-stat': (rest in (state['prepList'].get('dropped') or {}),
                                 ((state['prepList'].get('dropped') or {}).get(rest) or {}).get('since'), True, False)}.get(family)
        if not current or not current[0] or str(current[1] or '') > str(entry.get('at') or ''):
            continue
        moves.append(move(key, 'owner-veto', rest or family, f'direction.{family}', current[2], current[3],
                          {'vetoedAt': entry.get('at')}, 'The owner vetoed this move; it is undone and blocked for four weeks.',
                          f"Blocked until {str(entry.get('until') or '')[:10]}.",
                          f"Undid {key} on the owner's veto.", False, raiseTo=0.0 if family == 'raise' else None))
    return moves


# ------------------------------------------------------------------ the whole step

def evaluate(policy, evidence, now):
    """Every move today's evidence calls for. Pure: reads the policy and the evidence, changes nothing."""
    state = state_of(policy)
    evidence = evidence or {}
    moves = veto_moves(state, now)
    undone = {m['key'] for m in moves}
    for found in (segment_moves(state, evidence.get('rows') or [], now),
                  card_moves(state, evidence.get('rows') or [], now),
                  fun_moves(state, evidence.get('tickets') or [], now),
                  climb_moves(state, evidence.get('climbs') or [], evidence.get('rungs') or [], now, policy),
                  prep_moves(state, evidence.get('prep') or [], now),
                  calibration_moves(state, evidence.get('props'), (policy or {}).get('calibration'))
                  if evidence.get('props') is not None else []):
        moves += [m for m in found if m['key'] not in undone]
    spell = climb_dry_spell(evidence.get('climbDays') or [], eastern_day(now))
    if spell >= CLIMB_DRY_DAYS:
        moves.append(move('climb-dry', 'climb-dry-spell', 'climb', None, None, None, {'days': spell},
                          'Report only: nothing loosens.', 'n/a',
                          f"No Climb rung for {spell} straight days with 2+ games. Nothing was loosened.", False,
                          reportOnly=True, notify=False))
    return moves


def eastern_day(now):
    return now.astimezone(EASTERN).date().isoformat()


def apply(policy, moves, now):
    """Record the moves in policy['direction'] and policy['history']. Bounds are enforced here as well as in the
    readers, and a key outside the listed families is refused, so nothing else can be changed through this path."""
    state = state_of(policy)
    policy['direction'] = state
    policy.setdefault('history', [])
    at = stamp(now)
    applied = []
    for m in moves:
        if m.get('reportOnly'):
            continue
        family, _, rest = m['key'].partition(':')
        if family in ('raise', 'pause', 'priority'):
            seg = state['segments'].setdefault(rest, {})
            if family == 'raise':
                seg['raise'], seg['raiseSince'] = clamp_raise(m['to']), at
            elif family == 'pause':
                seg['paused'], seg['pauseSince'] = bool(m['to']), at
                if m.get('raiseTo') is not None:
                    seg['raise'], seg['raiseSince'] = clamp_raise(m['raiseTo']), at
            else:
                seg['priority'], seg['prioritySince'] = bool(m['to']), at
        elif family == 'card':
            if m['to'] == CARD_CAP:
                state['card'] = {'weekendCap': CARD_CAP, 'since': at, 'until': m['expires']}
            else:
                state['card'] = {'since': state['card'].get('since'), 'endedAt': at}
        elif family == 'fun':
            if m['to'] == 'shorter':
                state['funTickets'] = {'active': True, 'since': at, 'until': m['expires'], 'shape': dict(FUN_SHAPE)}
            else:
                state['funTickets'] = {'active': False, 'since': state['funTickets'].get('since'), 'endedAt': at}
        elif family == 'climb':
            state['climb'] = {'strict': m['to'] == 'strict', 'since': at}
        elif family == 'prep':
            state['prepList']['raised'], state['prepList']['since'] = m['to'] == 'raised', at
        elif family == 'prep-clears':
            state['prepList']['clearsOnly'], state['prepList']['clearsSince'] = bool(m['to']), at
        elif family == 'prep-stat':
            dropped = state['prepList'].setdefault('dropped', {})
            if m['to']:
                dropped[rest] = {'since': at, 'until': m['expires']}
            else:
                dropped.pop(rest, None)
        elif family == 'calibration':
            state['calibrationFlags'] = dict(m['to'] or {})
        else:
            raise ValueError(f'direction rules cannot change {m["key"]}')
        entry = {'at': at, 'engine': 'direction', 'key': m['key'], 'rule': m['rule'], 'segment': m['segment'],
                 'knob': m['knob'], 'from': m['from'], 'to': m['to'], 'why': m['sentence'], 'action': m['action'],
                 'undo': m['undo'], 'expires': m.get('expires'), 'evidence': m['trigger'],
                 'notify': m.get('notify', True)}
        policy['history'].append(entry)
        applied.append(entry)
    return applied


# ------------------------------------------------------------------ the readers

def _segment(policy, segment):
    entry = state_of(policy)['segments'].get(segment or '')
    return entry if isinstance(entry, dict) else {}


def edge_raise(policy, segment, now=None):
    """Extra points this segment's best bets must clear their price by, 0 to +6. Never negative."""
    seg = _segment(policy, segment)
    return clamp_raise(seg.get('raise')) if started(seg.get('raiseSince'), now) else 0.0


def paused(policy, segment, now=None):
    """Paused as a best bet by the direction rules (not the older performance caution, which only raises the bar)."""
    seg = _segment(policy, segment)
    return seg.get('paused') is True and started(seg.get('pauseSince'), now)


def pause_since(policy, segment, now=None):
    return _segment(policy, segment).get('pauseSince') if paused(policy, segment, now) else None


def priority(policy, segment, now=None):
    seg = _segment(policy, segment)
    return seg.get('priority') is True and not paused(policy, segment, now) and started(seg.get('prioritySince'), now)


def weekend_cap(policy, now, base):
    """The weekend card's ceiling: the base, or 3 while a cut is in force. Never above the base, never below 3."""
    card = state_of(policy)['card']
    cap = card.get('weekendCap')
    if not isinstance(cap, (int, float)) or not started(card.get('since'), now):
        return base
    if now is not None and expired(card.get('until'), now, missing=True):
        return base
    return min(base, max(CARD_CAP, int(cap)))


def fun_shape(policy, now):
    """The shorter longshot shape while it is in force, else None."""
    fun = state_of(policy)['funTickets']
    if fun.get('active') is not True or not started(fun.get('since'), now):
        return None
    if now is not None and expired(fun.get('until'), now, missing=True):
        return None
    return dict(FUN_SHAPE)


def fun_legs(policy, legs, now, league=None):
    """While the shorter fun-ticket shape is in force, every fun ticket (the longshot and the easy parlay alike) takes
    no leg from a segment paused as a best bet. Otherwise the legs come back unchanged. It only ever removes legs."""
    if not fun_shape(policy, now):
        return list(legs)
    return [leg for leg in legs if not paused(policy, leg_segment(leg, league), now)]


def climb_rules(policy, now):
    """{'pool': ...} while the stricter Climb pool is on, else None. The stricter pool only removes legs (see
    `flagged`); the ladder's leg chance, leg prices and ticket price are unchanged, so it can never loosen them."""
    climb = state_of(policy)['climb']
    if climb.get('strict') is not True or not started(climb.get('since'), now):
        return None
    return {'pool': CLIMB_POOL, 'skipFlaggedSegments': True}


def flagged(policy, segment, now=None):
    """Why a segment is held back from the stricter Climb pool, or None: paused as a best bet or carrying a raised
    edge bar under these rules, or the older learner's performance caution or raised learned edge
    (learn.learn_segments). Reading never changes anything."""
    if paused(policy, segment, now):
        return 'paused as a best bet'
    if edge_raise(policy, segment, now):
        return 'raised edge bar'
    seg = ((policy or {}).get('segments') or {}).get(segment or '')
    if not isinstance(seg, dict):
        return None
    if seg.get('paused'):
        return 'performance caution'
    knob = ((policy or {}).get('knobs') or {}).get('prop.minEdge' if '/prop:' in str(segment) else 'lean.minEdge') or {}
    own, base = seg.get('minEdge'), knob.get('value')
    if isinstance(own, (int, float)) and isinstance(base, (int, float)) and own > base:
        return 'raised learned edge'
    return None


def prep_rules(policy, now=None):
    """The Prep List thresholds and floors in force (baseline unless raised), dropped stats and the clears-only flag."""
    prep = state_of(policy)['prepList']
    raised = prep.get('raised') is True and started(prep.get('since'), now)
    rules = dict(PREP_BASE, floors=dict(PREP_BASE['floors']))
    if raised:
        rules.update(PREP_RAISED)
        rules['floors'] = {stat: floor + PREP_FLOOR_STEP[stat] for stat, floor in PREP_BASE['floors'].items()}
    dropped = prep.get('dropped') if isinstance(prep.get('dropped'), dict) else {}
    rules['dropped'] = sorted(stat for stat, entry in dropped.items() if isinstance(entry, dict)
                              and started(entry.get('since'), now)
                              and (now is None or not expired(entry.get('until'), now, missing=True)))
    rules['clearsOnly'] = prep.get('clearsOnly') is True and started(prep.get('clearsSince'), now)
    rules['raised'] = raised
    return rules


def leg_segment(leg, league=None):
    """A ticket leg's segment in the learning store's terms."""
    league = leg.get('league') or league
    market = leg.get('marketType') or leg.get('market')
    if market in ('total points', 'total'):
        return f'{league}/total'
    if market in ('point spread', 'spread'):
        return f'{league}/spread'
    if leg.get('athleteId'):
        words = {v: k for k, v in pricing.WORDS.items()}
        return f"{league}/prop:{leg.get('stat') or words.get(market, market)}"
    return f'{league}/{market}'


# ------------------------------------------------------------------ evidence and reporting

def evidence(rows, first=None, latest=None, games=(), props=None, prep=None, policy=None, now=None, lookback=21):
    """The engine's inputs from the stores: graded learning rows, settled fun tickets and Climb history from the
    official record, and the recent game days the Climb could have used."""
    import ladder
    first, latest = first or {}, latest or {}
    tickets = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if merged.get('historicalImport') or merged.get('parlayType') == 'ladder' \
                or not (merged.get('legs') or merged.get('parlayType')):
            continue
        tickets.append({'id': key, 'publishedAt': merged.get('publishedAt'), 'settledAt': merged.get('settledAt'),
                        'result': merged.get('result'), 'odds': merged.get('odds'), 'legs': len(merged.get('legs') or [])})
    where = ladder.state(first, latest)
    settled_at = {item['id']: item.get('settledAt') for item in where['history']}
    climbs = [{'run': item.get('run'), 'lostAt': item.get('step'), 'endedAt': item.get('settledAt'), 'id': item['id']}
              for item in where['history'] if item['result'] == 'loss']
    climbs += [{'run': c['run'], 'lostAt': None, 'endedAt': settled_at.get(c['id']), 'id': c['id']} for c in where['climbs']]
    played = [r for r in ladder.rungs(first, latest) if ladder.played(r)]
    rungs = [{'id': r['id'], 'step': (r.get('ladder') or {}).get('step'), 'publishedAt': r.get('publishedAt'),
              'settledAt': r.get('settledAt')} for r in played]
    days = []
    if now is not None:
        leagues = {'NFL'} | ({'CFB'} if ((policy or {}).get('calibration') or {}).get('CFB/prop') else set())
        counts = defaultdict(lambda: defaultdict(int))
        for game in games or ():
            moment = when(game.get('kickoff'))
            if moment and game.get('league') in leagues:
                counts[moment.astimezone(EASTERN).date().isoformat()][game['league']] += 1
        today = now.astimezone(EASTERN).date()
        for back in range(1, lookback + 1):
            day = today - timedelta(days=back)
            start = datetime(day.year, day.month, day.day, tzinfo=EASTERN)
            noon = start + timedelta(hours=12)          # still open at the 11:45 AM desk run: the scans could not post
            published = [r for r in rungs if (when(r['publishedAt']) or now).astimezone(EASTERN).date() == day]
            blocked = any((when(r['publishedAt']) or now) < start and ((when(r['settledAt']) or now) > noon)
                          for r in rungs)
            days.append({'date': day.isoformat(), 'games': dict(counts.get(day.isoformat(), {})),
                         'rung': bool(published), 'blocked': blocked})
    return {'rows': rows, 'tickets': tickets, 'climbs': climbs, 'rungs': rungs, 'climbDays': days,
            'props': props, 'prep': prep or []}


def ping(entries):
    """The weekly owner ping: one line per change, plus a single link. Empty when nothing changed."""
    lines = [e.get('why') or e.get('sentence') for e in entries if e.get('notify', True) and not e.get('reportOnly')]
    return '\n'.join(lines + [f'Details: {REPORT_LINK}']) if lines else ''


def in_force(policy, now=None):
    """The keys of the moves in force now, as the owner pings name them (what a veto can undo)."""
    state = state_of(policy)
    keys = []
    for segment, seg in sorted(state['segments'].items()):
        if not isinstance(seg, dict):
            continue
        keys += [f'{family}:{segment}' for family, on in (('pause', paused(policy, segment, now)),
                                                          ('raise', edge_raise(policy, segment, now) > 0),
                                                          ('priority', priority(policy, segment, now))) if on]
    if now is not None and weekend_cap(policy, now, 5) < 5:
        keys.append('card')
    if now is not None and fun_shape(policy, now):
        keys.append('fun')
    if climb_rules(policy, now):
        keys.append('climb')
    rules = prep_rules(policy, now)
    keys += ['prep'] * rules['raised'] + ['prep-clears'] * rules['clearsOnly'] + [f'prep-stat:{s}' for s in rules['dropped']]
    return keys


def standing(policy, now=None):
    """Plain lines for every move currently in force."""
    state = state_of(policy)
    out = []
    for segment, seg in sorted(state['segments'].items()):
        if not isinstance(seg, dict):
            continue
        parts = []
        if paused(policy, segment, now):
            parts.append(f"paused as a best bet since {str(seg.get('pauseSince'))[:10]} (research and shadow only)")
        if edge_raise(policy, segment, now):
            parts.append(f"edge bar +{edge_raise(policy, segment, now):g} since {str(seg.get('raiseSince'))[:10]}")
        if priority(policy, segment, now):
            parts.append('ranks first when the card fills')
        if parts:
            out.append(f"{label(segment)}: {'; '.join(parts)}")
    if now is not None and weekend_cap(policy, now, 5) < 5:
        out.append(f"Weekend card: {weekend_cap(policy, now, 5)} best bets until {str(state['card'].get('until'))[:10]}")
    if now is not None and fun_shape(policy, now):
        out.append(f"Fun tickets: +300 to +800, 3-4 legs until {str(state['funTickets'].get('until'))[:10]}")
    if climb_rules(policy, now):
        held = climb_held_back(policy, now)
        out.append(f"Climb: stricter leg pool until a climb reaches step 3 ({CLIMB_POOL}; "
                   + (f"leaving out {', '.join(label(s) for s in held)})" if held else 'nothing is left out right now)'))
    rules = prep_rules(policy, now)
    if rules['raised']:
        out.append('Prep List: raised thresholds and line floors')
    if rules['dropped']:
        out.append(f"Prep List: {', '.join(rules['dropped'])} dropped for now")
    if rules['clearsOnly']:
        out.append('Prep List: price-check-clears rows only')
    for segment, flag in sorted(state['calibrationFlags'].items()):
        out.append(f"Calibration flag: {label(segment)} said {pct(flag.get('said'))}, hit {pct(flag.get('hit'))} "
                   f"in the {flag.get('band')} band (n {flag.get('n')})")
    return out


def describe(m):
    numbers = m.get('evidence') if 'evidence' in m else m.get('trigger')
    if isinstance(numbers, dict) and 'n' in numbers and 'win' in numbers:
        trigger = (f"n {numbers['n']}, {record_text(numbers)}, {numbers['units']:+.2f}u, hit {pct(numbers.get('hitRate'))} "
                   f"vs break-even {pct(numbers.get('breakEven'))}, {clv_text(numbers.get('clv'))}")
    else:
        trigger = ', '.join(f'{k} {v}' for k, v in (numbers or {}).items() if not isinstance(v, (list, dict)))
    when_ = f" Expires {str(m['expires'])[:10]}." if m.get('expires') else ''
    return (f"{m.get('why') or m.get('sentence')} Trigger: {trigger or 'see the sentence'}. "
            f"Does: {m['action']} Undo: {m['undo']}{when_}")


def markdown(applied, preview=None, standing_lines=None, notes=None, title='Direction changes'):
    """The "Direction changes" box for REPORT.md and the Monday review: each move, its trigger numbers, what it does
    and when it would undo; what would change next; what is in force; report-only notes; the owner ping."""
    lines = [f'## {title}', '',
             f'Owner-approved bounded moves ({APPROVED}): they only tighten, pause, shift weight between approved '
             'categories, or restore what they tightened. Nothing loosens below the Oct 7 baseline, no market is '
             'added, and the record and published plays are untouched.', '']
    lines.append('Applied:')
    lines += [f'- {str(e.get("at"))[:10]} · {describe(e)}' for e in applied] or ['- none']
    if preview is not None:
        lines += ['', 'Would change at the next weekly learning run, on the evidence as it stands now:']
        lines += [f'- {describe(m)}' for m in preview] or ['- nothing']
    if standing_lines is not None:
        lines += ['', 'In force now:']
        lines += [f'- {line}' for line in standing_lines] or ['- every rule is at its Oct 7 baseline']
    if notes:
        lines += ['', 'Report only (nothing loosens):'] + [f"- {m.get('sentence') or m.get('why')}" for m in notes]
    text = ping(applied)
    if text:
        lines += ['', 'Owner ping:', ''] + [f'    {line}' for line in text.splitlines()]
    return '\n'.join(lines) + '\n'


def step(policy, evidence_, now, dry=False):
    """Evaluate and (unless dry) apply. Returns (moves, applied)."""
    moves = evaluate(policy, evidence_, now)
    return moves, ([] if dry else apply(policy, moves, now))


# ------------------------------------------------------------------ command line

def main(argv=None):
    import learning
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('status', 'veto'))
    parser.add_argument('key', nargs='?', help="veto: the move's key as the owner ping names it, e.g. pause:NFL/total, "
                                               "raise:CFB/total, card, fun, climb")
    parser.add_argument('--policy', default=str(learning.POLICY))
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    policy = learning.load_policy(args.policy)
    if args.command == 'veto':
        if not args.key:
            parser.error('veto needs a key')
        key = args.key.strip().rstrip('.')          # copied from the ping's "undo KEY." sentence
        family = key.split(':', 1)[0]
        if family not in ('raise', 'pause', 'priority', 'card', 'fun', 'climb', 'prep', 'prep-stat', 'prep-clears'):
            parser.error(f'unknown move key {key}')
        before = in_force(policy, now)
        state = state_of(policy)
        policy['direction'] = state
        state['vetoes'][key] = {'at': stamp(now), 'until': stamp(now + timedelta(days=VETO_DAYS))}
        applied = apply(policy, veto_moves(state, now), now)
        learning.save_policy(policy, args.policy)
        print(f"vetoed {key} until {state['vetoes'][key]['until'][:10]}; {len(applied)} move(s) undone")
        if not any(entry['key'] == key for entry in applied):
            # A typo such as pause:NFL/totals would otherwise look like it worked.
            print(f"warning: {key} matches no move in force, so nothing was undone; the veto only blocks that exact "
                  f"key for {VETO_DAYS} days. In force now: {', '.join(before) or 'nothing'}.", file=sys.stderr)
        return 0
    import gates
    import learn
    stores = gates.Stores()
    ctx = stores.as_of(now)
    found = evaluate(policy, evidence(learn.joined(), ctx.first, ctx.latest, stores.records, policy=policy, now=now), now)
    print(markdown([], [m for m in found if not m.get('reportOnly')], standing(policy, now),
                   [m for m in found if m.get('reportOnly')], 'Direction status'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
