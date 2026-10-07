#!/usr/bin/env python3
"""80/20 Climb map: real ledger rows, then a clearly labeled typical-price plan."""
import ticket_kit as kit
from ticket_kit import CHALK, GREEN, GREEN_INK, HOUSE, INK, INK_SOFT, MINUS, PANEL_TOP, RULE, X1, X2, COL_X, CAP
import ticket_cards
import ladder

START, GOAL, BANK = 50, 1000, 0.20


def plan(odds, start=START, goal=GOAL, banked=0, step_start=1):
    """Whole-dollar 80/20 path at one price, the same rounding as scripts/ladder.py (payout, split_return)."""
    stake, rows = start, []
    for step in range(step_start, 40):
        ret = ladder.payout(stake, odds)
        cut, ride = ladder.split_return(ret)
        rows.append(dict(step=step, bet=stake, cashes=ret, bank=cut, banked=banked + cut, ride=ride,
                         planned=True))
        banked += cut
        stake = ride
        if banked + stake >= goal:
            break
    return rows


def from_ledger(first, latest, *, plan_odds=-160):
    """The current climb's settled wins are exact; only future rows use the typical price."""
    state = ladder.state(first, latest)
    real = []
    for rung in state['history']:
        if int(rung.get('run') or 0) != state['run'] or rung.get('result') != 'win':
            continue
        banked_before = int(rung.get('banked') or 0)
        returned = int(rung['payout'])
        bank, ride = ladder.split_return(returned)
        real.append(dict(step=int(rung['step']), bet=int(rung['stake']), cashes=returned,
                         bank=bank, banked=int(rung.get('bankedAfter', banked_before + bank)),
                         ride=int(rung.get('nextStake', ride)), planned=False))
    real.sort(key=lambda row: row['step'])
    rows = real + plan(plan_odds, start=int(state['stake']), goal=int(state['goal']),
                       banked=int(state['banked']), step_start=int(state['step']))
    older = [r for r in state['history'] if int(r.get('run') or 0) < state['run']]
    furthest = max(older, key=lambda rung: (int(rung.get('step') or 0), -int(rung.get('run') or 0)), default=None)
    stub = (f'CLIMB #{int(furthest["run"])} REACHED STEP {int(furthest["step"])} · ${int(state["saved"]):,} BANKED AND KEPT'
            if older else f'CLIMB #{state["run"]} · ${int(state["saved"]):,} BANKED AND KEPT')
    return {'run': int(state['run']), 'step': int(state['step']), 'plan_odds': plan_odds,
            'rows': rows, 'stub': stub, 'saved': int(state['saved'])}


def climb_map(state):
    rows = state['rows']
    n = len(rows)
    row_h = 66
    panel_bottom = 452
    head_y = panel_bottom + 92
    first_y = head_y + 84
    flag_y = first_y + n * row_h + 30
    note_y = flag_y + 136
    perf = note_y + 70
    bottom = perf + 120
    card = kit.Card(height=bottom + 154)

    inner = kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=(540, 330))
    chip, _ = kit.series_chip(card, COL_X, 204, '80/20 CLIMB')
    inner += chip
    inner += card.text(COL_X, 372, f'${START} → ${GOAL:,}', 150, CHALK)
    inner += card.text(COL_X, 430, 'Bank 20% of every win. Ride 80%.', 44, CHALK, 'd', 600)

    # column right edges for the money columns; step numbers sit in circles on the left
    cols = [('BET', 336), ('CASHES', 498), ('BANK', 630), ('BANKED', 790), ('NEXT BET', X2)]
    inner += card.text(X1, head_y, 'STEP', 40, INK_SOFT, tracking=1)
    for label, right in cols:
        inner += card.text(right, head_y, label, 40, INK_SOFT, anchor='end', tracking=1)
    inner += f'<line x1="{X1}" y1="{head_y + 22}" x2="{X2}" y2="{head_y + 22}" stroke="{INK}" stroke-width="3"/>'

    now = state['step']
    for i, r in enumerate(rows):
        y = first_y + i * row_h
        cx, cy = X1 + 30, y - 16
        if r['step'] < now:        # cashed on the real record
            inner += (f'<circle cx="{cx}" cy="{cy}" r="27" fill="{GREEN}"/>'
                      f'<path transform="translate({cx - 14} {cy - 12}) scale(0.55)" d="{kit.CHECK}" fill="none" stroke="{GREEN_INK}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>')
        elif r['step'] == now:     # the step being looked for now
            inner += (f'<rect x="{X1 - 10}" y="{y - 52}" width="{X2 - X1 + 20}" height="{row_h - 6}" rx="10" fill="none" stroke="{INK}" stroke-width="4"/>'
                      f'<circle cx="{cx}" cy="{cy}" r="27" fill="{INK}"/>' + card.text(cx, cy + 40 * CAP / 2, str(r['step']), 40, CHALK, anchor='middle'))
            inner += card.text(cx + 46, y, 'NOW', 40, INK, tracking=1)
        else:
            inner += (f'<circle cx="{cx}" cy="{cy}" r="27" fill="none" stroke="{INK_SOFT}" stroke-width="4"/>'
                      + card.text(cx, cy + 40 * CAP / 2, str(r['step']), 40, INK_SOFT, anchor='middle'))
        vals = [kit.money(r['bet']), kit.money(r['cashes']), '+' + kit.money(r['bank']), kit.money(r['banked']), kit.money(r['ride'])]
        for (label, right), v in zip(cols, vals):
            inner += card.text(right, y, v, 46, INK if not r['planned'] else INK_SOFT, anchor='end')
        if i < n - 1:
            inner += f'<line x1="{X1}" y1="{y + 18}" x2="{X2}" y2="{y + 18}" stroke="{RULE}" stroke-width="2"/>'

    last = rows[-1]
    total = last['banked'] + last['ride']
    flag_x = X1 + 18
    inner += (f'<path d="M{flag_x} {flag_y + 8} V{flag_y - 58}" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'
              f'<path d="M{flag_x + 3} {flag_y - 58} h52 l-13 18 l13 18 h-52 z" fill="{INK}"/>')
    inner += card.text(flag_x + 80, flag_y - 12, '$1,000 REACHED', 56, INK, tracking=1)
    sub = f'{kit.money(last["banked"])} banked + {kit.money(last["ride"])} riding = {kit.money(total)}'
    inner += card.text(flag_x + 80, flag_y + 46, sub, kit.fit(sub, 42, X2 - flag_x - 80, 'd', 600), INK_SOFT, 'd', 600)

    note = f'The plan at a typical {MINUS}{abs(state["plan_odds"])} a step. Real prices vary, so each real step replaces its row as it settles.'
    lines = kit.wrap(note, 40, X2 - X1, 'd', 500, max_lines=2)
    for j, line in enumerate(lines if isinstance(lines, list) else [lines]):
        inner += card.text(X1, note_y + j * 52 - 26, line if isinstance(line, str) else line[0], 40, INK_SOFT, 'd', 500)

    stub = state['stub']
    inner += card.text(X1, perf + 70, stub, kit.fit(stub, 44, X2 - X1, tracking=1), INK, tracking=1)
    ticket_cards.frame(card, HOUSE, CHALK, perf, bottom, inner)
    return card
