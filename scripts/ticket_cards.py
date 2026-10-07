#!/usr/bin/env python3
"""Kitchen Ticket SVG builders; data is mapped from the stored record by ticket_card."""
import ticket_kit as kit
from ticket_kit import (CAP, CHALK, CHARCOAL, CHECK, CROSS, COL_MAX, COL_X, DIM, GREEN, GREEN_INK, HOUSE, INK, INK_SOFT,
                 MINUS, PANEL_TOP, PANEL_X1, PANEL_X2, RED, RULE, W, X1, X2, fit, width)

# The owner approved both accents on October 7, 2026.
ORDER_UP = True
CHEF_CLIP = True


def frame(card, panel_colors, glow, perf, bottom, inner, breakout=''):
    """Felt, brand, tilted paper with its printed content, rail, breakout head, chef clip, footer."""
    kit.base_defs(card, panel_colors, glow)
    kit.felt(card)
    kit.brand(card, 218 if CHEF_CLIP else 52)
    card.add(kit.tilt(kit.paper(card, perf, bottom) + inner))
    kit.rail(card)
    if breakout:
        card.add(kit.tilt(breakout))
    if CHEF_CLIP:
        kit.chef_clip(card)
    kit.footer(card)


def stake_stub(card, y, units):
    label = 'RISK'
    lw = width(label, 44, tracking=1)
    return card.text(X1, y, label, 44, INK_SOFT, tracking=1) + card.text(X1 + lw + 18, y + 2, f'{units:g}u', 62, INK)


def bet_line(card, side_line, units, baseline, max_size=204, floor=120):
    """'OVER 49.5' in huge ink plus a stacked unit ('REC' over 'YDS'). The set fits X1..X2."""
    def unit_w(size):
        u = round(size * 0.38)
        return max((width(x, u) for x in units), default=0), u
    size = max_size
    while size > floor:
        uw, _ = unit_w(size)
        if width(side_line, size) + (uw + 22 if units else 0) <= X2 - X1:
            break
        size -= 2
    uw, u = unit_w(size)
    s = card.text(X1 - 4, baseline, side_line, size, INK)
    bx = X1 - 4 + width(side_line, size) + 22
    if len(units) == 2:
        s += card.text(bx, baseline - round(u * 0.95), units[0], u, INK) + card.text(bx, baseline, units[1], u, INK)
    elif units:
        s += card.text(bx, baseline, units[0], u, INK)
    return s, size


def reason_lines(reason, room):
    """The saved reason in Barlow 52 caps on at most two lines. Too long: keep its first clause (before ', and',
    ';' or ' and '); still too long: None, and the WHY row is left off rather than shrunk or cut mid-sentence."""
    text = str(reason or '').upper().rstrip('.')
    for candidate in (text, *(text.split(sep)[0] for sep in (', AND ', '; ', ' AND ', ', '))):
        lines = kit.wrap(candidate.strip(), 52, room, max_lines=2)
        if lines:
            return lines
    return None


def why_block(card, y, reason, max_w=X2 - X1):
    """WHY tag plus the saved reason as a hook: Barlow 52 caps, at most two lines (else the caller passes a
    shorter saved reason)."""
    tag_w = width('WHY', 40, tracking=2) + 26
    lines = reason_lines(reason, max_w - tag_w - 18)
    s = (f'<rect x="{X1}" y="{y - 44}" width="{tag_w:.0f}" height="56" rx="6" fill="{INK}"/>'
         + card.text(X1 + 13, y - 2, 'WHY', 40, CHALK, tracking=2))
    for i, line in enumerate(lines):
        s += card.text(X1 + tag_w + 18, y + i * 56, line, 52, INK)
    return s, len(lines)


def name_block(card, name, top, bottom, max_w=COL_MAX - COL_X):
    """Player or team name: one line when it fits at >= 104 px and has <= 9 letters, else two lines (first word /
    the rest). Size is the largest that fits both the width and the space between top and bottom."""
    name = name.upper()
    words = name.split()
    one = len(name.replace(' ', '')) <= 9 and fit(name, 136, max_w, floor=104) >= 104 and width(name, 104) <= max_w
    if one:
        size = min(fit(name, 136, max_w, floor=72), int((bottom - top) / CAP))
        base = top + (bottom - top) / 2 + size * CAP / 2
        return card.text(COL_X - 4, base, name, size, CHALK), size
    if len(words) == 1:                       # one long word: a single line, shrunk to fit (floor 72)
        size = min(fit(name, 136, max_w, floor=72), int((bottom - top) / CAP))
        return card.text(COL_X - 4, top + (bottom - top) / 2 + size * CAP / 2, name, size, CHALK), size
    lines = [words[0], ' '.join(words[1:])]
    size = min(min(fit(l, 104, max_w, floor=72) for l in lines), int((bottom - top) / (CAP + 0.95)))
    block = size * (CAP + 0.95)
    base = top + (bottom - top - block) / 2 + size * CAP
    return (card.text(COL_X - 4, base, lines[0], size, CHALK) + card.text(COL_X - 4, base + size * 0.95, lines[1], size, CHALK)), size


def meta_block(card, p, cy):
    """Logo pair (r40 discs, abbreviation bugs as the fallback) plus 'NMSU at FIU' and the kickoff."""
    s = ''
    cx1, cx2 = COL_X + 40, COL_X + 40 + 88
    for cx, logo, team in ((cx1, p.get('away_logo'), p['away']), (cx2, p.get('home_logo'), p['home'])):
        if logo:
            s += kit.logo_disc(card, logo, cx, cy, 40)
        else:
            s += kit.initials_badge(card, cx, cy, 40, team[:3], p.get('team_colors', {}).get(team, (CHARCOAL[0],))[0])
    tx = cx2 + 40 + 18
    s += card.text(tx, cy - 6, f"{p['away']} at {p['home']}", 40, CHALK, 'd', 700)
    s += card.text(tx, cy + 40, p['when'], 40, CHALK, 'd', 500, extra=' opacity="0.88"')
    return s


# ---------------------------------------------------------------------------- straight plays
def play_card(p):
    """Hot Plate (POTD) or best bet: player prop with photo, player prop without photo, or game line."""
    card = kit.Card()
    calibrated = p.get('chance') is not None and p.get('calibrated', True)
    tag_w = width('WHY', 40, tracking=2) + 26
    why = reason_lines(p.get('reason'), X2 - X1 - tag_w - 18) if p.get('reason') else None
    if not why:
        p = dict(p, reason=None)
    n_reason = len(why or [])
    # 584 is the panel bottom with a chance row and a one-line reason. A missing row gives its 74 px to the panel
    # (and so to the photo); a second reason line takes 56 px from it. Capped at 640 so the head still breaks out.
    panel_bottom = 584 + (0 if calibrated else 74) + (0 if n_reason else 74) - (56 if n_reason == 2 else 0)
    panel_bottom = min(panel_bottom, 640)

    game = p['kind'] == 'game'
    if game:
        left = kit.team_panel(*p['team_colors'][p['away']])
        right = kit.team_panel(*p['team_colors'][p['home']])
        colors, glow = (left[0], left[1]), CHALK
    else:
        top, bottom, glow = kit.team_panel(*p['team_colors'][p['team']])
        colors = (top, bottom)

    # ---- the panel
    inner = ''
    breakout = ''
    if game:
        inner += kit.split_panel(card, PANEL_TOP, panel_bottom, left[:2], right[:2])
    else:
        inner += kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=(790, 330))
    if p.get('photo') and not game:
        height = min(580, (panel_bottom - PANEL_TOP) * 1.37)
        in_panel, breakout = kit.hero_photo(card, p['photo'], PANEL_TOP, panel_bottom, face_x=800, height=height)
        inner += in_panel
        inner += f'<rect x="{PANEL_X1}" y="{PANEL_TOP}" width="{PANEL_X2 - PANEL_X1}" height="{panel_bottom - PANEL_TOP}" rx="14" fill="url(#scrim)"/>'
    elif not game:
        # no photo: the team logo at 260 px on a chalk disc with a 6 px team-deep ring; abbreviation bug if no logo
        logo = p.get('team_logo')
        cy = (PANEL_TOP + panel_bottom) / 2 + 6
        if logo:
            inner += kit.logo_disc(card, logo, 790, cy, 130, ring=colors[1])
        else:
            inner += kit.initials_badge(card, 790, cy, 130, p['team'][:4], p['team_colors'][p['team']][0])
    chip, _ = kit.series_chip(card, COL_X, 204, 'HOT PLATE (POTD)' if p.get('featured') else 'BEST BET', flame=p.get('featured'))
    inner += chip
    if game:
        inner += _game_panel(card, p, panel_bottom, left, right)
    else:
        meta_cy = panel_bottom - 26 - 44
        nb, _ = name_block(card, p['player'], 260 + 26, meta_cy - 40 - 22)
        inner += nb + meta_block(card, p, meta_cy)

    # ---- the printed ticket
    side_line = f"{p['side']} {p['line']}" if p['side'] in ('OVER', 'UNDER') else p['side']
    units = kit.STAT_UNITS.get(p.get('market'), ())
    if p.get('side_short') and width(side_line, 120) > X2 - X1:
        side_line = p['side_short']          # spread: 'CENTRAL MICHIGAN +13.5' -> 'CMU +13.5'
    base = panel_bottom + 34 + round(204 * CAP)
    b, bet_size = bet_line(card, side_line, units, base)
    inner += b
    y = base + 36
    inner += kit.dashed(X1, X2, y)
    y += 108
    pr, book = kit.price(p['odds']), p['book'].upper()
    inner += (card.text(X1 - 2, y, pr, 116, INK) + card.text(X2, y, book, 62, INK, anchor='end')
              + kit.dots(X1 + width(pr, 116) + 22, X2 - width(book, 62) - 22, y - 4))
    if calibrated:
        y += 74
        lw1, vw1 = width('I have it at', 42, 'd', 600), width(kit.pct1(p['chance']), 56)
        lw2, vw2 = width('the price needs', 42, 'd', 600), width(kit.pct1(p['needs']), 56)
        x2l = X2 - vw2 - 12 - lw2
        inner += (card.text(X1, y, 'I have it at', 42, INK_SOFT, 'd', 600) + card.text(X1 + lw1 + 12, y, kit.pct1(p['chance']), 56, INK)
                  + kit.dots(X1 + lw1 + 12 + vw1 + 18, x2l - 18, y - 6)
                  + card.text(x2l, y, 'the price needs', 42, INK_SOFT, 'd', 600) + card.text(X2, y, kit.pct1(p['needs']), 56, INK, anchor='end'))
    if why:
        y += 74
        wb, n = why_block(card, y, p['reason'])
        inner += wb
        y += 56 * (n - 1)
    perf = max(1100, y + 44)
    bottom = 1196
    inner += stake_stub(card, perf + 64, float(p.get('units', 1)))
    if ORDER_UP:
        inner += kit.order_up(card, X2, perf + 48)
    frame(card, colors, glow, perf, bottom, inner, breakout)
    return card


def _game_panel(card, p, panel_bottom, left, right):
    """Split panel for a game line: kickoff top right, both logos at r90 on their team halves with the team
    names under them, and 'AT' on the seam."""
    s = card.text(PANEL_X2 - 24, 204 + 28 + 44 * CAP / 2, p['when_caps'], 44, CHALK, anchor='end', tracking=1)
    cy = 372
    for cx, logo, team, name, deep in ((322, p['away_logo'], p['away'], p['away_name'], left[1]),
                                       (758, p['home_logo'], p['home'], p['home_name'], right[1])):
        if logo:
            s += kit.logo_disc(card, logo, cx, cy, 90, ring=deep)
        else:
            s += kit.initials_badge(card, cx, cy, 90, team[:3], p['team_colors'][team][0])
        label = name.upper()
        s += card.text(cx, panel_bottom - 32, label, fit(label, 56, 320, floor=40, tracking=1), CHALK, anchor='middle', tracking=1)
    s += f'<circle cx="540" cy="{cy}" r="36" fill="{kit.NIGHT}" stroke="{CHALK}" stroke-width="4"/>'
    s += card.text(540, cy + 40 * CAP / 2, 'AT', 40, CHALK, anchor='middle', tracking=1)
    return s


# ---------------------------------------------------------------------------- tickets (Chef's Special)
def leg_rows(card, legs, top, row, compact=False, settled=None):
    """One receipt line per leg: checkbox, art, subject (soft ink) + selection (ink) as one fitted set, price."""
    psize = 40 if compact else 44
    pw = max(width(kit.price(l['odds']), psize) for l in legs) if all('odds' in l for l in legs) else 0
    tx = 252 if not compact else 238
    sel_right = X2 - (pw + 22 if pw else 0)
    parts = [kit.leg_parts(l['title']) for l in legs]
    room = sel_right - tx
    size = 48 if not compact else 44
    def need(sz, subj, sel):
        return width(subj, sz) + (18 + width(sel, sz) if sel else 0)
    while size > 40 and any(need(size, a, b) > room for a, b in parts):
        size -= 2
    out = ''
    r = 30 if not compact else 24          # single thumb radius
    pr = 21 if not compact else 18         # each disc of a game leg's logo pair
    ax = 198 if not compact else 192       # art zone centre: x 160..236 (compact 160..224)
    for i, (leg, (subj, sel)) in enumerate(zip(legs, parts)):
        cy = top + row * i + row / 2
        if i:
            out += f'<line x1="{X1}" y1="{top + row * i:.0f}" x2="{X2}" y2="{top + row * i:.0f}" stroke="{RULE}" stroke-width="2"/>'
        out += kit.checkbox(X1, cy - 19, 38, (settled or {}).get(i))
        art = leg.get('art') or ()
        if art and art[0] == 'photo':
            out += kit.face_thumb(card, art[1], ax, cy, r)
        elif art and art[0] == 'logos':
            out += (kit.logo_disc(card, art[1], ax - pr * 0.8, cy, pr, ring=kit.LINE)
                    + kit.logo_disc(card, art[2], ax + pr * 0.8, cy, pr, ring=kit.LINE))
        elif art and art[0] == 'logo':
            out += kit.logo_disc(card, art[1], ax, cy, r, ring=kit.LINE)
        else:   # no photo: team-colour badge with the player's initials
            out += kit.initials_badge(card, ax, cy, r, kit.initials(subj), leg.get('team_color', CHARCOAL[0]))
        s_name = subj
        if need(size, s_name, sel) > room:   # last resort before a two-line row: first name to an initial
            first, _, rest = s_name.partition(' ')
            s_name = f'{first[0]}. {rest}' if rest else s_name
        base = cy + size * CAP / 2
        out += card.text(tx, base, s_name, size, INK_SOFT)
        sw = width(sel, size)
        out += kit.dots(tx + width(s_name, size) + 14, sel_right - sw - 14, base - 6)
        out += card.text(sel_right, base, sel, size, INK, anchor='end')
        if pw:
            out += card.text(X2, cy + psize * CAP / 2, kit.price(leg['odds']), psize, INK_SOFT, anchor='end')
    return out, size


def ticket_card(p):
    """Chef's Special: odds hook, one dominant player, the stake chip and payout, and the actual slip."""
    n = len(p['legs'])
    compact = n >= 7
    extra = max(0, n - 8) * 60                # nine or more legs: the canvas grows, a leg is never dropped
    card = kit.Card(kit.H + extra)
    top, bottom, glow = kit.team_panel(*p['hero_team'])
    hero_size, sub_size = (160, 42) if compact else (232, 46)
    hero_base = 260 + (14 if compact else 20) + round(hero_size * CAP)
    sub_base = hero_base + (50 if compact else 58)
    panel_bottom = sub_base + (22 if compact else 26)
    inner = kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=(790, 300))
    height = min(560, (panel_bottom - PANEL_TOP) * (1.6 if compact else 1.42))
    breakout = ''
    if p.get('photo'):
        in_panel, breakout = kit.hero_photo(card, p['photo'], PANEL_TOP, panel_bottom, face_x=830, height=height)
        inner += in_panel + f'<rect x="{PANEL_X1}" y="{PANEL_TOP}" width="{PANEL_X2 - PANEL_X1}" height="{panel_bottom - PANEL_TOP}" rx="14" fill="url(#scrim)"/>'
    elif p.get('hero_logo'):
        inner += kit.logo_disc(card, p['hero_logo'], 790, (PANEL_TOP + panel_bottom) / 2 + 8, 130, ring=bottom)
    else:
        inner += kit.initials_badge(card, 790, (PANEL_TOP + panel_bottom) / 2 + 8, 130,
                                    p.get('hero_team_name', 'K'), top)
    chip, _ = kit.series_chip(card, COL_X, 204, 'CHEF’S SPECIAL')
    inner += chip
    inner += card.text(COL_X - 6, hero_base, kit.price(p['odds']), hero_size, CHALK)
    sub = f"{p['book'].upper()} · {n} LEGS · {p['date']}"
    inner += card.text(COL_X, sub_base, sub, kit.fit(sub, sub_size, COL_MAX + 20 - COL_X, tracking=1), CHALK, tracking=1)

    # stake chip, payout, estimated-price note
    r = 44 if compact else 54
    cy = panel_bottom + 18 + r
    pay = kit.money(p['stake'] * kit.decimal(p['odds']))
    psize = 84 if compact else 104
    inner += kit.poker_chip(card, X1 + r, cy, r, kit.money(p['stake']))
    lx = X1 + 2 * r + 20
    inner += card.text(lx, cy + 14, 'pays', 42, INK_SOFT, 'd', 600)
    inner += card.text(lx, cy + 58, f"{float(p.get('units', .25)):g}u", 40, INK_SOFT)
    inner += kit.dots(lx + width('pays', 42, 'd', 600) + 16, X2 - width(pay, psize) - 18, cy + 8)
    inner += card.text(X2, cy + psize * CAP / 2, pay, psize, INK, anchor='end')
    y = cy + r
    if p.get('price_estimated'):
        y += 40
        inner += card.text(X2, y, 'Combined from leg prices', 40, INK_SOFT, 'd', 500, anchor='end')
    y += 18 if compact else 22
    inner += kit.dashed(X1, X2, y)
    legs_top = y + 8
    perf = (1116 if compact else 1104) + extra
    row = max(60, min(82, (perf - 16 - legs_top) / n))
    rows, _ = leg_rows(card, p['legs'], legs_top, row, compact)
    inner += rows
    label = 'FUN TICKET · TRACKED APART FROM BEST BETS'
    inner += card.text(X1, perf + 58 if not compact else perf + 54, label, kit.fit(label, 40, X2 - X1, tracking=1), INK_SOFT, tracking=1)
    frame(card, (top, bottom), glow, perf, 1196 + extra, inner, breakout)
    return card


# ---------------------------------------------------------------------------- 80/20 Climb
def climb_card(p):
    card = kit.Card()
    panel_bottom = 568
    inner = kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=(540, 380))
    chip, _ = kit.series_chip(card, COL_X, 204, '80/20 CLIMB')
    inner += chip
    cy, r = 396, 104
    a, b = 316, 764
    inner += kit.poker_chip(card, a, cy, r, kit.money(p['stake']))
    inner += kit.poker_chip(card, b, cy, r, kit.money(p['payout']))
    inner += (f'<path d="M{a + r + 34} {cy} H{b - r - 46}" stroke="{CHALK}" stroke-width="12" stroke-linecap="round"/>'
              f'<path d="M{b - r - 70} {cy - 30} L{b - r - 34} {cy} L{b - r - 70} {cy + 30}" fill="none" stroke="{CHALK}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>')
    sub = f"CLIMB #{p['run']} · STEP {p['step']} · {kit.price(p['odds'])} {p['book'].upper()}"
    inner += card.text(COL_X, panel_bottom - 30, sub, 46, CHALK, tracking=1)
    # legs
    top = panel_bottom + 24
    rows, _ = leg_rows(card, p['legs'], top, 84)
    inner += rows
    y = top + 84 * len(p['legs']) + 20
    inner += kit.dashed(X1, X2, y)
    y += 70
    inner += kit.leader(card, y, 'Banked so far', kit.money(p['banked']))
    y += 70
    inner += kit.leader(card, y, 'If it cashes', f"{kit.money(p['bank_this'])} BANKED · {kit.money(p['next_stake'])} RIDES")
    perf = y + 44
    inner += climb_route(card, p, perf)
    frame(card, HOUSE, CHALK, perf, 1196, inner)
    return card


def climb_route(card, p, perf):
    """Printed route: cashed steps get green checks, the current step is outlined, the future is a muted line
    to the $1,000 flag. No future step count and no guessed amounts."""
    cy = perf + 92
    xs = [X1 + 38 + i * 132 for i in range(p['step'])]
    flag_x = X2 - 70
    s = f'<line x1="{xs[0]}" y1="{cy}" x2="{xs[-1]}" y2="{cy}" stroke="{INK}" stroke-width="8"/>'
    s += f'<line x1="{xs[-1] + 40}" y1="{cy}" x2="{flag_x - 20}" y2="{cy}" stroke="{kit.MUTED}" stroke-width="6" stroke-dasharray="4 14" stroke-linecap="round"/>'
    for i, x in enumerate(xs, 1):
        if i < p['step']:
            s += (f'<circle cx="{x}" cy="{cy}" r="32" fill="{GREEN}"/>'
                  f'<path transform="translate({x - 17} {cy - 15}) scale(0.66)" d="{CHECK}" fill="none" stroke="{GREEN_INK}" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>')
            s += card.text(x, cy + 86, f'STEP {i}', 40, INK_SOFT, anchor='middle')
        else:
            s += (f'<circle cx="{x}" cy="{cy}" r="36" fill="{CHALK}" stroke="{INK}" stroke-width="8"/>'
                  + card.text(x, cy + 40 * CAP / 2, str(i), 40, INK, anchor='middle'))
            s += card.text(x, cy + 86, 'NOW', 40, INK, anchor='middle', tracking=1)
    # the $1,000 flag, printed in ink (a goal marker, never a result colour)
    s += (f'<path d="M{flag_x} {cy + 34} V{cy - 60}" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'
          f'<path d="M{flag_x + 3} {cy - 60} h64 l-16 21 l16 21 h-64 z" fill="{INK}"/>')
    s += card.text(flag_x + 20, cy + 86, kit.money(p['goal']), 40, INK, anchor='middle')
    return s


# ---------------------------------------------------------------------------- Cooked (win)
def cooked_card(p):
    card = kit.Card()
    panel_bottom = 548
    inner = kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=None)
    inner += f'<circle cx="790" cy="330" r="360" fill="url(#halo)"/>'
    height = min(580, (panel_bottom - PANEL_TOP) * 1.42)
    breakout = ''
    if p.get('photo'):
        in_panel, breakout = kit.hero_photo(card, p['photo'], PANEL_TOP, panel_bottom, face_x=790, height=height)
        inner += in_panel + f'<rect x="{PANEL_X1}" y="{PANEL_TOP}" width="{PANEL_X2 - PANEL_X1}" height="{panel_bottom - PANEL_TOP}" rx="14" fill="url(#scrim)"/>'
    elif p.get('team_logo'):
        inner += kit.logo_disc(card, p['team_logo'], 790, 342, 126)
    chip, _ = kit.series_chip(card, COL_X, 204, 'BEST BET · FINAL')
    inner += chip
    nb, _ = name_block(card, p['player'], 286, 452)
    inner += nb
    inner += card.text(COL_X, 506, f"{kit.price(p['odds'])} · {p['book'].upper()}", 46, CHALK, tracking=1, extra=' opacity="0.92"')
    side_line = f"{p['side']} {p['line']}"
    base = 772
    b, _ = bet_line(card, side_line, kit.STAT_UNITS[p['market']], base, max_size=176)
    inner += b
    inner += kit.dashed(X1, X2, base + 38)
    inner += card.text(X1, base + 98, 'FINAL', 48, INK_SOFT, tracking=2)
    fb = base + 266
    inner += card.text(X1 - 4, fb, str(p['final']), 176, INK)
    fx = X1 - 4 + width(str(p['final']), 176) + 22
    u = kit.STAT_UNITS[p['market']]
    if len(u) == 2:
        inner += card.text(fx, fb - 68, u[0], 70, INK) + card.text(fx, fb, u[1], 70, INK)
    elif u:
        inner += card.text(fx, fb, u[0], 70, INK)
    inner += kit.pill(card, X2, fb - 62, f"CLEARED BY {p['margin']}", GREEN, GREEN_INK, 52, CHECK)
    if p.get('close_line'):
        inner += card.text(X1, fb + 60, p['close_line'], 40, INK_SOFT, 'd', 600)
    perf = 1100
    inner += card.text(X1, perf + 64, f"+{float(p.get('units_won', 0)):.2f}u WON", 62, INK)
    inner += kit.logo_disc(card, p['team_logo'], X2 - 40, perf + 46, 36, ring=kit.LINE)
    stamp = kit.big_stamp(card, 742, panel_bottom - 16, 'COOKED', GREEN, GREEN_INK, CHECK, angle=-6)
    frame(card, CHARCOAL, GREEN, perf, 1196, inner, breakout + stamp)
    return card


# ---------------------------------------------------------------------------- Final receipt
def final_card(p):
    panel_bottom, row = 474, 112
    perf = max(1100, panel_bottom + 20 + row * len(p['rows']) + 34)
    card = kit.Card(perf + 96 + 154)          # 1350 up to five rows, then +112 per row
    inner = kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=(760, 300))
    chip, _ = kit.series_chip(card, COL_X, 204, 'FINAL')
    inner += chip
    head = p['headline'].upper()
    size = fit(head, 140, PANEL_X2 - 24 - COL_X, floor=96)
    inner += card.text(COL_X - 4, 268 + round(size * CAP) + 18, head, size, CHALK)
    wins = sum(r['result'] == 'hit' for r in p['rows'])
    misses = sum(r['result'] == 'miss' for r in p['rows'])
    pushes = sum(r['result'] in ('push', 'void') for r in p['rows'])
    sub = f"{len(p['rows'])} BEST BETS · {wins} HIT · {misses} MISSED" + (f" · {pushes} PUSH" if pushes else '')
    inner += card.text(COL_X, panel_bottom - 30, sub, 46, CHALK, tracking=1)
    top = panel_bottom + 20
    for i, r in enumerate(p['rows']):
        y = top + row * i
        if i:
            inner += f'<line x1="{X1}" y1="{y}" x2="{X2}" y2="{y}" stroke="{RULE}" stroke-width="2"/>'
        subj, sel = kit.leg_parts(r['title'])
        tw = X2 - 176 - 24 - X1
        size_r = 46
        while size_r > 40 and width(f'{subj} {sel}', size_r) > tw:
            size_r -= 2
        inner += card.text(X1, y + 50, subj, size_r, INK_SOFT) + card.text(X1 + width(subj + ' ', size_r), y + 50, sel, size_r, INK)
        unit_text = str(r.get('unit_text') or '—')
        detail = str(r['detail'])
        unit_x = X2 - 194
        detail_room = unit_x - X1 - 28
        detail_size = 40
        while detail_size > 24 and width(detail, detail_size) > detail_room:
            detail_size -= 2
        if width(detail, detail_size) > detail_room:
            raise ValueError(f'Final detail will not fit: {detail}')
        inner += card.text(X1, y + 96, detail, detail_size, INK_SOFT, 'd', 500)
        inner += card.text(unit_x, y + 99, unit_text, 40, INK if unit_text.startswith('+') else RED if unit_text.startswith('-') else INK_SOFT, anchor='end')
        inner += kit.result_stamp(card, X2, y + row / 2, r['result'])
    inner += card.text(X1, perf + 64, f"NET {float(p.get('net_units', 0)):+.2f}u", 62, INK)
    frame(card, HOUSE, CHALK, perf, perf + 96, inner)
    return card


# ---------------------------------------------------------------------------- Prep List (research)
def prep_card(p):
    rows = p['rows']
    row = 114
    panel_bottom = 474
    head_y = panel_bottom + 56
    top = head_y + 22
    perf = top + row * len(rows) + 30
    bottom = perf + 96
    height = bottom + 154
    card = kit.Card(height)
    inner = kit.panel_rect(card, PANEL_TOP, panel_bottom, hot=(760, 300))
    chip, _ = kit.series_chip(card, COL_X, 204, 'RESEARCH')
    inner += chip
    head_size = fit('PREP LIST', 140, 652 - 28 - COL_X, floor=96)
    inner += card.text(COL_X - 4, 268 + 22 + round(head_size * CAP), 'PREP LIST', head_size, CHALK)
    inner += card.text(COL_X, panel_bottom - 30, f"{p['day']} · {len(rows)} LINES", 46, CHALK, tracking=1)
    # the faces, a 3 x 2 grid on the right of the panel
    for i, r in enumerate(rows[:6]):
        cx, cy = 704 + (i % 3) * 102, 254 + (i // 3) * 108
        if r.get('photo'):
            inner += kit.face_thumb(card, r['photo'], cx, cy, 46, ring=CHALK)
        else:
            inner += kit.initials_badge(card, cx, cy, 46, kit.initials(r['player']), r.get('team_color', CHARCOAL[0]))
    inner += card.text(X1, head_y, 'THE LINE', 40, INK_SOFT, tracking=2) + card.text(X2, head_y, 'HIT', 40, INK_SOFT, anchor='end', tracking=2)
    inner += kit.dashed(X1, X2, head_y + 18)
    for i, r in enumerate(rows):
        y = top + row * i
        if i:
            inner += f'<line x1="{X1}" y1="{y}" x2="{X2}" y2="{y}" stroke="{RULE}" stroke-width="2"/>'
        cy = y + row / 2
        inner += (kit.face_thumb(card, r['photo'], X1 + 34, cy, 34) if r.get('photo')
                  else kit.initials_badge(card, X1 + 34, cy, 34, kit.initials(r['player']), r.get('team_color', CHARCOAL[0])))
        tx = X1 + 84
        hits = r['hits'].upper()
        hw = width(hits, 56)
        subj, sel = r['player'], r['selection']
        room = X2 - hw - 24 - tx
        size = 46
        while size > 40 and width(f'{subj} {sel}', size) > room:
            size -= 2
        inner += card.text(tx, y + 54, subj, size, INK_SOFT) + card.text(tx + width(subj + ' ', size), y + 54, sel, size, INK)
        inner += card.text(X2, y + 58, hits, 56, INK, anchor='end')
        check = 'My price check: clears' if r['clears'] else 'History only · no edge at this price'
        line2 = f"{kit.price(r['odds'])} {r['book']} · {check}"
        inner += card.text(tx, y + 100, line2, kit.fit(line2, 40, X2 - tx), INK_SOFT)
    note = p['stub']
    inner += card.text(X1, perf + 60, note, kit.fit(note, 40, X2 - X1, tracking=1), INK_SOFT, tracking=1)
    frame(card, HOUSE, CHALK, perf, bottom, inner)
    return card
