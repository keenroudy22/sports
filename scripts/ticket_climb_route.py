#!/usr/bin/env python3
"""A dated, clearly labelled 80/20 Climb map from the real rung ledger and stored slate.

This builder is review-only until the first real render is approved. It does not
schedule a post, change a rung, or read the incomplete Today ladder summary.
"""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import gates
import ladder
import pick_card
import ticket_cards
import ticket_climb_map
import ticket_kit as kit
from ticket_kit import (CAP, CHALK, CHECK, COL_X, DIM, GREEN, GREEN_INK, HOUSE,
                        INK, INK_SOFT, MINUS, NIGHT, PANEL_TOP, RULE, X1, X2,
                        fit, width)


ET = ZoneInfo('America/New_York')
LEAGUES = ('NFL', 'CFB')
LEAD = ladder.LEAD
CLUSTER = timedelta(minutes=90)
SETTLE = timedelta(hours=3, minutes=30)  # planning allowance, not a desk settlement promise
PLAN_ODDS = -160
GOAL = ladder.GOAL
DAILY = ('06:45', '08:30', '10:00', '11:45', '13:30', '16:00', '17:30',
         '20:00', '21:00', '23:30')
EXTRA = {6: ('14:45', '18:50'), 0: ('18:50',), 3: ('18:50',)}


def when(value):
    return gates.when(value)


def scans(start, days=21):
    """The already-scheduled desk and Climb scans, in Eastern civil time."""
    if start.tzinfo is None:
        raise ValueError('scan start must have a timezone')
    day0 = start.astimezone(ET).date()
    for offset in range(days + 1):
        day = day0 + timedelta(days=offset)
        for hhmm in sorted(DAILY + EXTRA.get(day.weekday(), ())):
            hour, minute = map(int, hhmm.split(':'))
            instant = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)
            if instant >= start:
                yield instant


def load_games(slate):
    """Only confirmed pregame football kickoffs from the stored ESPN slate."""
    rows = slate.get('games', []) if isinstance(slate, dict) else slate
    return sorted(({'id': game['id'], 'league': game['league'], 'kickoff': when(game['kickoff'])}
                   for game in rows if game.get('league') in LEAGUES
                   and game.get('state') == 'pre' and game.get('timeValid') is True
                   and game.get('kickoff')),
                  key=lambda game: (game['kickoff'], game['id']))


def window_at(games, scan):
    """Earliest two-or-more-game, one-league cluster available at this scan."""
    day = scan.astimezone(ET).date()
    for league in LEAGUES:
        pool = [game for game in games if game['league'] == league
                and game['kickoff'].astimezone(ET).date() == day
                and game['kickoff'] > scan + LEAD]
        for i, first in enumerate(pool):
            group = [game for game in pool[i:]
                     if game['kickoff'] - first['kickoff'] <= CLUSTER]
            if len(group) >= 2:
                return {'league': league, 'games': group, 'scan': scan,
                        'first': first['kickoff'], 'last': group[-1]['kickoff']}
    return None


def windows(games, now, count, free_at=None):
    """Non-overlapping future windows; the prior last kickoff must settle first."""
    out, ready = [], max(now, free_at or now)
    for scan in scans(now):
        if len(out) >= count:
            break
        if scan < ready:
            continue
        found = window_at(games, scan)
        if found:
            out.append(found)
            ready = found['last'] + SETTLE
    return out


def window_label(window):
    if not window:
        return 'NO SLATE YET', ''
    instant = window['first'].astimezone(ET)
    day = f'{instant:%a}'.upper() + f' {instant.month}/{instant.day}'
    if instant.hour == 12 and instant.minute == 0:
        clock = 'NOON'
    else:
        hour = instant.hour % 12 or 12
        clock = f'{hour}:{instant.minute:02d}' if instant.minute else str(hour)
        clock += ' PM' if instant.hour >= 12 else ' AM'
    return day, clock


def leg_times(pick):
    """Use both ticket legs; the pick-level kickoff is not a reliable boundary."""
    times = [when(leg['kickoff']) for leg in pick.get('legs') or [] if leg.get('kickoff')]
    if not times:
        times = [when(pick['kickoff'])]
    return min(times), max(times)


def from_stores(stores, now):
    """Read ladder.state over gates.Stores().as_of(now), never today.json."""
    ctx = stores.as_of(now)
    state = ladder.state(ctx.first, ctx.latest)
    by_id = {key: dict(pick, **ctx.latest.get(key, {})) for key, pick in ctx.first.items()}
    cashed = []
    for rung in state['history']:
        if int(rung.get('run') or 0) != state['run'] or rung.get('result') != 'win':
            continue
        pick = by_id[rung['id']]
        first, last = leg_times(pick)
        before = int(rung.get('banked') or 0)
        banked = int(rung.get('bankedAfter') if rung.get('bankedAfter') is not None
                     else before + ladder.split_return(rung['payout'])[0])
        cashes = int(rung['payout'])
        cashed.append({'step': int(rung['step']), 'bet': int(rung['stake']),
                       'cashes': cashes, 'bank': banked - before, 'banked': banked,
                       'ride': int(rung.get('nextStake') or ladder.split_return(cashes)[1]),
                       'league': pick['league'], 'first': first, 'last': last, 'id': rung['id']})
    cashed.sort(key=lambda row: row['step'])
    opened = None
    if state['open']:
        pick = state['open']
        info = pick.get('ladder') or {}
        first, last = leg_times(pick)
        stake = int(info.get('stake') or state['stake'])
        cashes = int(info.get('payout') or ladder.payout(stake, pick['odds']))
        bank, ride = ladder.split_return(cashes)
        opened = {'id': pick['id'], 'step': state['step'], 'league': pick['league'],
                  'first': first, 'last': last, 'odds': pick['odds'], 'bet': stake,
                  'cashes': cashes, 'bank': int(info.get('bankThisWin') if info.get('bankThisWin') is not None else bank),
                  'banked': int(info.get('bankedAfter') if info.get('bankedAfter') is not None else state['banked'] + bank),
                  'ride': int(info.get('nextStake') if info.get('nextStake') is not None else ride)}
    missed = next((rung for rung in reversed(state['history']) if rung.get('result') == 'loss'
                   and int(rung.get('run') or 0) == state['run'] - 1), None)
    return {'run': int(state['run']), 'step': int(state['step']), 'stake': int(state['stake']),
            'banked': int(state['banked']), 'saved': int(state['saved']), 'cashed': cashed,
            'open': opened, 'missed': missed}, load_games(stores.slate)


def plan_from(step, stake, banked):
    """The approved map's exact whole-dollar payout/split from the current real state."""
    return ticket_climb_map.plan(PLAN_ODDS, start=stake, goal=GOAL,
                                 banked=banked, step_start=step)


def route_rows(state, now, games):
    rows = [('cashed', row, {'league': row['league'], 'first': row['first'], 'last': row['last']})
            for row in state['cashed']]
    opened = state.get('open')
    if opened:
        rows.append(('open', opened, {'league': opened['league'],
                                      'first': opened['first'], 'last': opened['last']}))
        plan = [] if opened['banked'] + opened['ride'] >= GOAL else plan_from(
            opened['step'] + 1, opened['ride'], opened['banked'])
        available = windows(games, now, len(plan), opened['last'] + SETTLE)
        kinds = ['plan'] * len(plan)
    else:
        plan = plan_from(state['step'], state['stake'], state['banked'])
        available = windows(games, now, len(plan))
        kinds = ['next'] + ['plan'] * (len(plan) - 1)
    rows.extend((kind, row, available[i] if i < len(available) else None)
                for i, (kind, row) in enumerate(zip(kinds, plan)))
    return rows


DISC_CX, DISC_R = X1 + 22, 22
TAG_X = X1 + 58
COLS = (('BET', 712, 52, 'bet'), ('CASHES', 860, 46, 'cashes'),
        ('KEEP', X2, 40, 'bank'))
BAR_HEAD, BAR_PAD, BOTTOM_MAX = 50, 10, 1212
PLAN_LABEL = f'PLAN AT A TYPICAL {MINUS}{abs(PLAN_ODDS)}'


def _disc(card, cy, kind, step, ink, soft):
    if kind == 'cashed':
        return (f'<circle cx="{DISC_CX}" cy="{cy}" r="{DISC_R}" fill="{GREEN}"/>'
                f'<path transform="translate({DISC_CX - 13} {cy - 11}) scale(0.5)" d="{CHECK}" fill="none" '
                f'stroke="{GREEN_INK}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>')
    color = ink if kind in ('next', 'open') else soft
    return (f'<circle cx="{DISC_CX}" cy="{cy}" r="{DISC_R}" fill="none" stroke="{color}" stroke-width="4"/>'
            + card.text(DISC_CX, cy + 40 * CAP / 2, str(step), 40, color, anchor='middle'))


def _row(card, cy, kind, row, window, ink, soft):
    svg = _disc(card, cy, kind, row['step'], ink, soft)
    if window:
        league = window['league']
        tag_w = width(league, 40, tracking=1) + 16
        svg += (f'<rect x="{TAG_X}" y="{cy - 22}" width="{tag_w:.0f}" height="44" rx="7" fill="none" '
                f'stroke="{ink}" stroke-width="3"/>'
                + card.text(TAG_X + 8, cy + 40 * CAP / 2, league, 40, ink, tracking=1))
        day, clock = window_label(window)
        x = TAG_X + tag_w + 14
        svg += card.text(x, cy + 44 * CAP / 2, day, 44, ink)
        svg += card.text(x + width(day, 44) + 12, cy + 40 * CAP / 2, clock, 40, soft)
    else:
        svg += card.text(TAG_X, cy + 40 * CAP / 2, 'NO SLATE YET', 40, soft, tracking=1)
    real = {'cashed': ('bet', 'cashes', 'bank'), 'open': ('bet', 'cashes', 'bank'),
            'next': ('bet',)}.get(kind, ())
    for _, right, size, key in COLS:
        svg += card.text(right, cy + size * CAP / 2, kit.money(row[key]), size,
                         ink if key in real else soft, anchor='end')
    return svg


def bank_line(state):
    missed = state.get('missed')
    saved = kit.money(state['saved'])
    if missed:
        text = f'CLIMB #{missed["run"]} MISSED {kit.money(missed["stake"])} STEP {missed["step"]} · ALL CLIMBS {saved} KEPT'
        if width(text, 40, tracking=1) > X2 - X1 - 54:
            text = f'CLIMB #{missed["run"]} MISSED {kit.money(missed["stake"])} STEP {missed["step"]} · {saved} KEPT'
        return text
    if state['banked']:
        return f'THIS CLIMB {kit.money(state["banked"])} · ALL CLIMBS {saved} BANKED AND KEPT'
    return f'ALL CLIMBS {saved} BANKED AND KEPT'


def climb_route(state, now, games, fixture=False):
    """The 1080×1350 review card; the labelled future is a plan, not a post schedule."""
    rows = route_rows(state, now, games)
    if not rows:
        raise ValueError('Climb route has no real or planned steps')
    card = kit.Card()
    panel_bottom = 400
    inner = kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=(780, 290))
    label = (f'FIXTURE · CLIMB #{state["run"]} ROUTE MAP' if fixture
             else f'80/20 CLIMB #{state["run"]} · ROUTE MAP')
    chip, _ = kit.series_chip(card, COL_X, 172, label)
    inner += chip
    inner += card.text(COL_X, 340, '$50 → $1,000', 136, CHALK)
    inner += card.text(COL_X, 384, 'Bank 20% of every win. Ride 80%.', 40, CHALK, 'd', 600)

    hy = panel_bottom + 52
    stamp_w = width(PLAN_LABEL, 40, tracking=1) + 28
    inner += (f'<rect x="{X1}" y="{hy - 38}" width="{stamp_w:.0f}" height="50" rx="8" fill="none" '
              f'stroke="{INK}" stroke-width="3"/>'
              + card.text(X1 + 14, hy, PLAN_LABEL, 40, INK, tracking=1))
    for name, right, _, _ in COLS:
        inner += card.text(right, hy, name, 40, INK_SOFT, anchor='end', tracking=1)
    inner += f'<line x1="{X1}" y1="{hy + 18}" x2="{X2}" y2="{hy + 18}" stroke="{INK}" stroke-width="3"/>'
    top = hy + 22
    bars = sum(kind in ('next', 'open') for kind, _, _ in rows)
    after = 56 + 30 + 124
    pitch = int(min(60, (BOTTOM_MAX - after - top - bars * (BAR_HEAD + BAR_PAD)) // len(rows)))
    if pitch < 50:
        raise ValueError(f'route does not fit: pitch {pitch} for {len(rows)} rows')
    y, previous_week = top, None
    for i, (kind, row, window) in enumerate(rows):
        week = (window['first'].astimezone(ET).date() -
                timedelta(days=window['first'].astimezone(ET).weekday())) if window else None
        if previous_week is not None and week != previous_week and kind not in ('next', 'open'):
            inner += f'<line x1="{X1}" y1="{y}" x2="{X2}" y2="{y}" stroke="{INK_SOFT}" stroke-width="4"/>'
        previous_week = week
        if kind in ('next', 'open'):
            height = BAR_HEAD + pitch + BAR_PAD
            inner += (f'<rect x="{X1 - 10}" y="{y + 4}" width="{X2 - X1 + 20}" height="{height - 6}" '
                      f'rx="12" fill="{NIGHT}"/>')
            words = ('NEXT · NOT POSTED YET' if kind == 'next'
                     else f'OPEN · POSTED AT {kit.price(row["odds"])} · NOT SETTLED YET')
            inner += card.text(X1 + 2, y + 50, words, 40, CHALK, tracking=1)
            inner += _row(card, y + BAR_HEAD + pitch / 2 + 4, kind, row, window, CHALK, DIM)
            y += height
        else:
            inner += _row(card, y + pitch / 2, kind, row, window, INK, INK_SOFT)
            y += pitch
            nxt = rows[i + 1] if i + 1 < len(rows) else None
            if nxt and nxt[0] not in ('next', 'open'):
                inner += f'<line x1="{X1}" y1="{y}" x2="{X2}" y2="{y}" stroke="{RULE}" stroke-width="2"/>'

    last = rows[-1][1]
    flag_x, fy = X1 + 14, y + 56
    inner += (f'<path d="M{flag_x} {fy + 6} V{fy - 50}" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'
              f'<path d="M{flag_x + 3} {fy - 50} h44 l-12 15 l12 15 h-44 z" fill="{INK}"/>')
    inner += card.text(flag_x + 66, fy, '$1,000', 56, INK)
    summary = (f'{kit.money(last["banked"])} banked + {kit.money(last["ride"])} riding = '
               f'{kit.money(last["banked"] + last["ride"])}')
    room = X2 - (flag_x + 66 + width('$1,000', 56) + 20)
    inner += card.text(X2, fy, summary, fit(summary, 40, room, 'd', 600),
                       INK_SOFT, 'd', 600, anchor='end')
    perf = fy + 30
    saved = bank_line(state)
    if state.get('missed'):
        inner += kit.checkbox(X1, perf + 22, 40, 'miss')
        inner += card.text(X1 + 54, perf + 56, saved,
                           fit(saved, 40, X2 - X1 - 54, tracking=1), INK, tracking=1)
    else:
        inner += card.text(X1, perf + 56, saved,
                           fit(saved, 40, X2 - X1, tracking=1), INK, tracking=1)
    rule = 'NO STEP IS FORCED. EACH NEEDS 2 LEGS IN 2 GAMES.'
    inner += card.text(X1, perf + 100, rule, fit(rule, 40, X2 - X1, tracking=1),
                       INK_SOFT, tracking=1)
    ticket_cards.frame(card, HOUSE, CHALK, perf, perf + 124, inner)
    if fixture:
        badge = card.text(540, 820, 'FIXTURE', 220, INK, anchor='middle', tracking=8, role='badge')
        card.add(f'<g transform="rotate(-24 540 760)" opacity="0.07" pointer-events="none">{badge}</g>')
        tag = card.text(X2 - 16, 86, 'FIXTURE', 44, CHALK, anchor='end', tracking=3)
        card.add(tag)
    return card


def render(path, now=None, stores=None):
    """Render the real current route; no public card or posting store is touched."""
    now = now or datetime.now(timezone.utc)
    stores = stores or gates.Stores()
    state, games = from_stores(stores, now)
    card = climb_route(state, now, games)
    problems = kit.qa(card, 'climb-route')
    if problems:
        raise ValueError('; '.join(problems))
    path = Path(path)
    pick_card.render(card.svg(), path)
    if path.stat().st_size >= 8_000_000:
        raise ValueError('route PNG exceeds Discord 8 MB limit')
    return path, state, route_rows(state, now, games)


def fixture_states(now, games):
    """Three explicitly fictional stress states, never substituted for the real ledger."""
    early = windows(games, now, 3)
    if len(early) < 3:
        raise ValueError('fixture slate needs at least three non-overlapping windows')
    first_pay = ladder.payout(50, -150)
    first_bank, first_ride = ladder.split_return(first_pay)
    second_pay = ladder.payout(first_ride, -170)
    second_bank, second_ride = ladder.split_return(second_pay)
    cashed = [
        {'step': 1, 'bet': 50, 'cashes': first_pay, 'bank': first_bank,
         'banked': first_bank, 'ride': first_ride, 'league': early[0]['league'],
         'first': early[0]['first'], 'last': early[0]['last'], 'id': 'FIXTURE-1'},
        {'step': 2, 'bet': first_ride, 'cashes': second_pay, 'bank': second_bank,
         'banked': first_bank + second_bank, 'ride': second_ride,
         'league': early[1]['league'], 'first': early[1]['first'],
         'last': early[1]['last'], 'id': 'FIXTURE-2'},
    ]
    banked = first_bank + second_bank
    mid = {'run': 3, 'step': 3, 'stake': second_ride, 'banked': banked,
           'saved': 42 + banked, 'cashed': cashed, 'open': None, 'missed': None}
    restart = {'run': 4, 'step': 1, 'stake': 50, 'banked': 0,
               'saved': 42 + banked, 'cashed': [], 'open': None,
               'missed': {'run': 3, 'step': 3, 'stake': second_ride}}
    open_pay = ladder.payout(50, -173)
    open_bank, open_ride = ladder.split_return(open_pay)
    opened = {'run': 3, 'step': 1, 'stake': 50, 'banked': 0,
              'saved': 42, 'cashed': [], 'missed': None,
              'open': {'id': 'FIXTURE-OPEN', 'step': 1, 'league': early[0]['league'],
                       'first': early[0]['first'], 'last': early[0]['last'],
                       'odds': -173, 'bet': 50, 'cashes': open_pay, 'bank': open_bank,
                       'banked': open_bank, 'ride': open_ride}}
    return {'midclimb': (mid, early[1]['last'] + SETTLE),
            'restart': (restart, early[2]['last'] + SETTLE),
            'open': (opened, early[0]['scan'] + timedelta(minutes=5))}


def render_fixtures(directory, now, games):
    """Render three watermark-labelled test cards to a private review directory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, (state, instant) in fixture_states(now, games).items():
        card = climb_route(state, instant, games, fixture=True)
        problems = kit.qa(card, f'climb-route-FIXTURE-{name}')
        if problems:
            raise ValueError('; '.join(problems))
        path = directory / f'climb-route-fixture-{name}.png'
        pick_card.render(card.svg(), path)
        if path.stat().st_size >= 8_000_000:
            raise ValueError(f'{path.name} exceeds Discord 8 MB limit')
        paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--now', help='ISO UTC instant; defaults to now')
    parser.add_argument('--fixtures', action='store_true', help='also render three clearly labelled fictional states')
    args = parser.parse_args(argv)
    now = when(args.now) if args.now else datetime.now(timezone.utc)
    stores = gates.Stores()
    path, state, rows = render(args.out, now, stores)
    print(f'{path} · Climb #{state["run"]} step {state["step"]}; {len(rows)} rows')
    if args.fixtures:
        for fixture in render_fixtures(args.out.parent, now, load_games(stores.slate)):
            print(fixture)


if __name__ == '__main__':
    main()
