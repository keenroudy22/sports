"""Kook'n felt card templates for X and Discord (1080x1350). Python standard library only.

Prototype for Codex to port into scripts/pick_card.py, scripts/sheet.py and scripts/research_art.py:
same SVG-string approach, rasterized by pick_card.render (headless Chrome). Rules baked in:
  * one hook line first; nothing that must be read in the feed is smaller than 40px (footer floor 26px)
  * the chance-vs-needed meter only when the read is calibrated
  * a proof strip (season record) on play cards, the same numbers as the site
  * player photo on props and team logos on game lines (owner's call 2026-10-06), passed in as data URIs from
    pick_card.artwork(); team-color chips with abbreviations are the fallback when an image is missing
  * green = hit/support, red = miss, always with a ✓ / ✗ and a word
  * no dashes as punctuation, no "!", no "lock", no units on straight plays (POSTS.md voice rules)
"""
from html import escape

W, H = 1080, 1350
FELT_NIGHT, FELT, FELT_RAISED, LINE = '#07120D', '#0E2219', '#15301F', '#21412F'
CHALK, DIM, KOOKD, KOOKD_INK = '#F2F7F4', '#A9C0B3', '#20C774', '#062B1C'
BURNT, BURNT_TEXT, TICKET, TICKET_INK, TICKET_DIM, TICKET_RULE = '#F2414E', '#FF6B75', '#F2F7F4', '#07120D', '#3D5447', '#C9D8D0'
DISPLAY = "'Barlow Condensed', 'Arial Narrow', sans-serif"
BODY = "'DM Sans', 'Helvetica Neue', Arial, sans-serif"
FOOTER = '21+ · Entertainment only · Gambling problem? 1-800-MY-RESET'
SITE = 'keenroudy.com/sports'
FLOORS = {'hero': 96, 'hook': 64, 'number': 56, 'row': 40, 'label': 30, 'footer': 26}


def t(x, y, text, size, color=CHALK, family=BODY, weight=600, anchor='start', spacing=0):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" letter-spacing="{spacing}">{escape(str(text))}</text>')


def odds(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ''
    return f'+{n}' if n > 0 else f'−{abs(n)}'


def pct(x):
    return f'{int(100 * x + 0.5)}%' if isinstance(x, (int, float)) else ''


def luminance(hex_color):
    try:
        r, g, b = (int(hex_color.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, AttributeError):
        return 0
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def team_chip(x, y, team, r=34, logo=None):
    if logo:
        return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{FELT_RAISED}" stroke="rgba(255,255,255,.18)" stroke-width="3"/>'
                f'<image href="{logo}" x="{x - r * 0.78:.0f}" y="{y - r * 0.78:.0f}" width="{r * 1.56:.0f}" height="{r * 1.56:.0f}" preserveAspectRatio="xMidYMid meet"/>')
    color = (team or {}).get('color') or '#3D5447'
    ink = TICKET_INK if luminance(color) > 0.45 else '#FFFFFF'
    abbr = str((team or {}).get('abbr') or (team or {}).get('abbreviation') or '?')[:4]
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" stroke="rgba(255,255,255,.18)" stroke-width="3"/>'
            + t(x, y + r * 0.32, abbr, int(r * 0.8), ink, BODY, 700, 'middle'))


def mark(x, y, s=1.0):
    """The winning-ticket mark (120-unit grid)."""
    return (f'<g transform="translate({x} {y}) scale({s})"><rect x="10" y="38" width="100" height="62" rx="9" fill="{CHALK}"/>'
            f'<path d="M82 38 L101 38 Q110 38 110 47 L110 91 Q110 100 101 100 L82 100 Z" fill="{KOOKD}"/>'
            f'<circle cx="10" cy="69" r="8" fill="{FELT_NIGHT}"/><circle cx="110" cy="69" r="8" fill="{FELT_NIGHT}"/>'
            f'<path d="M82 44 L82 94" stroke="{FELT_NIGHT}" stroke-width="3" stroke-dasharray="4 4"/>'
            f'<rect x="28" y="51" width="12" height="36" rx="2" fill="{TICKET_INK}"/><path d="M45 69 L61 52" stroke="{TICKET_INK}" stroke-width="11"/>'
            f'<path d="M45 69 L63 87" stroke="{TICKET_INK}" stroke-width="11"/><path d="M88 70 L93 76 L101 63" stroke="{CHALK}" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
            f'<g transform="rotate(-14 34 30) translate(16.8 14.7) scale(0.32)" fill="{CHALK}" stroke="{FELT_NIGHT}" stroke-width="6"><circle cx="38" cy="44" r="17"/>'
            '<circle cx="60" cy="33" r="22"/><circle cx="82" cy="44" r="17"/><rect x="31" y="44" width="58" height="18" stroke="none"/><rect x="31" y="66" width="58" height="13" rx="3"/></g></g>')


def frame(chip, body, chip_color=KOOKD, chip_ink=KOOKD_INK):
    """Brand bar (0-140), body, footer (1230-1350)."""
    width = 40 + 21 * len(chip)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<rect width="{W}" height="{H}" fill="{FELT_NIGHT}"/><rect x="24" y="24" width="{W - 48}" height="{H - 48}" rx="36" fill="{FELT}" stroke="{LINE}" stroke-width="2"/>'
            + mark(56, 34, 0.8) + t(170, 98, 'KOOK’N', 52, CHALK, DISPLAY, 700, spacing=3)
            + f'<rect x="{W - 64 - width}" y="58" width="{width}" height="56" rx="28" fill="{chip_color}"/>'
            + t(W - 64 - width / 2, 97, chip.upper(), 30, chip_ink, BODY, 700, 'middle', 1.5)
            + body
            + f'<line x1="64" y1="1232" x2="{W - 64}" y2="1232" stroke="{LINE}" stroke-width="2"/>'
            + t(64, 1276, FOOTER, 26, DIM) + t(64, 1314, SITE, 26, KOOKD, BODY, 700)
            + '</svg>')


def wrap(text, size, width, family_ratio=0.46):
    """Greedy word wrap for condensed display type (about 0.46em per character)."""
    words, lines, line = str(text).split(), [], ''
    for word in words:
        trial = f'{line} {word}'.strip()
        if len(trial) * size * family_ratio > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def meter(x, y, w, chance, needs, on_paper=True):
    track = '#D5E2DA' if on_paper else LINE
    tick = TICKET_INK if on_paper else CHALK
    return (f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="13" fill="{track}"/>'
            f'<rect x="{x}" y="{y}" width="{max(26, w * chance):.0f}" height="26" rx="13" fill="{KOOKD}"/>'
            f'<rect x="{x + w * needs - 4:.0f}" y="{y - 12}" width="8" height="50" rx="4" fill="{tick}"/>')


def photo(cx, cy, r, uri):
    return (f'<defs><clipPath id="photo"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{FELT_RAISED}"/>'
            f'<image href="{uri}" x="{cx - r * 1.3:.0f}" y="{cy - r * 0.95:.0f}" width="{r * 2.6:.0f}" height="{r * 1.95:.0f}" clip-path="url(#photo)" preserveAspectRatio="xMidYMax meet"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{KOOKD}" stroke-width="6"/>')


def play_card(pick, game=None, record=None, featured=False, art=None):
    """Straight best bet / Pick of the Day. Port target: pick_card.modern_svg (same filename contract)."""
    pap = pick.get('probabilityAtPublication') or {}
    chance, needs = pap.get('chance'), pap.get('breakEven')
    title = str(pick.get('displayTitle') or pick.get('title') or '')
    player = pick.get('player') or (title.split(' OVER ')[0].split(' UNDER ')[0] if pick.get('athleteId') else None)
    selection = title[len(player):].strip() if player and title.startswith(player) else title
    import re
    total = None if player else re.match(r'^(.*?)\s+(over|under)\s+([\d.]+)$', selection, re.I)
    if total:
        player, selection = total.group(1), f'{total.group(2)} {total.group(3)} points'
    selection = selection.replace('receiving yards', 'rec yds').replace('rushing yards', 'rush yds').replace('passing yards', 'pass yds').upper()
    body = ''
    logos = (art or {}).get('uris') if (art or {}).get('kind') == 'logos' else None
    if game:
        body += team_chip(98, 196, game.get('away'), logo=(logos or [None, None])[0] if logos and len(logos) == 2 else None)
        body += team_chip(170, 196, game.get('home'), logo=(logos or [None, None])[-1] if logos and len(logos) == 2 else None)
        body += t(222, 210, f"{game['away'].get('abbr')} at {game['home'].get('abbr')} · {pick.get('_when', '')}", 36, DIM, BODY, 600)
    y = 330
    if (art or {}).get('kind') == 'photo' and art.get('uri'):
        body += photo(W - 150, 205, 86, art['uri'])
    if player:
        for line in wrap(player.upper(), 72, W - 128)[:2]:
            body += t(64, y, line, 72, CHALK, DISPLAY, 700, spacing=1)
            y += 80
        y += 32
    for line in wrap(selection, 120, W - 128)[:2]:
        body += t(64, y, line, 120, KOOKD, DISPLAY, 700)
        y += 118
    top = max(y + 30, 520)
    body += f'<rect x="64" y="{top}" width="{W - 128}" height="410" rx="28" fill="{TICKET}"/>'
    body += f'<rect x="{W - 64 - 170}" y="{top}" width="170" height="410" rx="28" fill="{KOOKD}"/><rect x="{W - 64 - 170}" y="{top}" width="40" height="410" fill="{KOOKD}"/>'
    body += f'<line x1="{W - 64 - 170}" y1="{top + 20}" x2="{W - 64 - 170}" y2="{top + 390}" stroke="{FELT}" stroke-width="5" stroke-dasharray="14 12"/>'
    body += f'<circle cx="64" cy="{top + 205}" r="20" fill="{FELT}"/><circle cx="{W - 64}" cy="{top + 205}" r="20" fill="{FELT}"/>'
    body += t(104, top + 92, odds(pick.get('odds')), 88, TICKET_INK, DISPLAY, 700) + t(104 + 52 * len(odds(pick.get('odds'))), top + 92, str(pick.get('book') or '').upper(), 40, TICKET_DIM, BODY, 700)
    if isinstance(chance, (int, float)) and isinstance(needs, (int, float)) and pap.get('calibrated', True):
        body += t(104, top + 170, f'We make it {pct(chance)}. Price needs {pct(needs)}.', 42, TICKET_INK, BODY, 600)
        body += meter(104, top + 206, W - 128 - 170 - 80, chance, needs)
        fair = round(-100 * chance / (1 - chance)) if chance >= 0.5 else round(100 * (1 - chance) / chance)
        edge = round(100 * (chance - needs), 1)
        body += t(104, top + 320, 'FAIR PRICE', 30, TICKET_DIM, BODY, 700, spacing=1) + t(104, top + 380, odds(fair), 60, TICKET_INK, DISPLAY, 700)
        body += t(420, top + 320, 'EDGE', 30, TICKET_DIM, BODY, 700, spacing=1) + t(420, top + 380, f'+{edge} pts' if edge > 0 else f'{edge} pts', 60, TICKET_INK, DISPLAY, 700)
        body += t(W - 64 - 85, top + 215, pct(chance), 64, KOOKD_INK, DISPLAY, 700, 'middle') + t(W - 64 - 85, top + 258, 'OUR CHANCE', 24, KOOKD_INK, BODY, 700, 'middle')
    else:
        body += t(104, top + 170, str(pick.get('_number') or ''), 42, TICKET_INK, BODY, 600)
    if record:
        body += t(64, min(1170, top + 500), f"SEASON {record}  ·  EVERY PLAY GRADED", 40, CHALK, DISPLAY, 700, spacing=1.5)
    return frame('Pick of the day' if featured else 'Best bet', body)


def receipt_card(day_label, rows, season=None):
    """Morning receipt. Port target: pick_card.receipt_svg (receipt-day-<date>)."""
    wins = sum(1 for r in rows if r.get('result') == 'win')
    losses = sum(1 for r in rows if r.get('result') == 'loss')
    body = t(64, 230, day_label.upper(), 44, DIM, BODY, 700, spacing=2) + t(64, 380, f'{wins}–{losses}', 170, CHALK, DISPLAY, 700)
    y = 460
    tall = 150 if len(rows) <= 2 else 120
    for r in rows[:5]:
        hit = r.get('result') == 'win'
        miss = r.get('result') == 'loss'
        color, mark_text, ink = (KOOKD, '✓ HIT', KOOKD_INK) if hit else (BURNT, '✗ MISS', TICKET_INK) if miss else ('#C9D8D0', '– PUSH', TICKET_INK)
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="{tall}" rx="22" fill="{TICKET}"/><rect x="{W - 64 - 190}" y="{y}" width="190" height="{tall}" rx="22" fill="{color}"/><rect x="{W - 64 - 190}" y="{y}" width="30" height="{tall}" fill="{color}"/>'
        body += t(W - 64 - 95, y + tall / 2 + 13, mark_text, 38, ink, BODY, 700, 'middle')
        title = str(r.get('displayTitle') or r.get('title') or '')
        body += t(96, y + tall / 2 - 4, title[:40], 46 if tall > 120 else 40, TICKET_INK, DISPLAY, 700)
        body += t(96, y + tall / 2 + 40, f"{odds(r.get('odds'))} {r.get('book') or ''}  {r.get('_final') or ''}".strip(), 30, TICKET_DIM, BODY, 600)
        y += tall + 20
    if season:
        body += t(64, 1170, f'SEASON {season}  ·  THE MISSES STAY ON THE RECORD', 40, CHALK, DISPLAY, 700, spacing=1.5)
    return frame('Receipt', body, chip_color=FELT_RAISED, chip_ink=CHALK)


def fun_ticket_card(pick, label='Fun ticket'):
    """Longshot / lotto ticket. Port target: pick_card.ticket_svg (keep the sha256(id) % 3 style rotation)."""
    legs = pick.get('legs') or []
    body = t(64, 300, odds(pick.get('odds')), 190, KOOKD, DISPLAY, 700) + t(64, 380, str(pick.get('_hook') or label).upper(), 64, CHALK, DISPLAY, 700, spacing=1)
    y = 470
    for leg in legs[:6]:
        text = str(leg.get('title') or leg.get('displayTitle') or leg.get('selection') or '')
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="96" rx="20" fill="{FELT_RAISED}"/>' + t(100, y + 62, text[:46], 42, CHALK, DISPLAY, 700)
        y += 112
    body += t(64, 1170, f"{str(pick.get('book') or '').upper()}  ·  TRACKED APART FROM BEST BETS", 38, DIM, BODY, 700, spacing=1)
    return frame(label, body, chip_color='#B49BE0', chip_ink='#1C0F33')


def research_card(row):
    """Research hit-rate card at 4:5 (was 1200x675). Port target: research_art.svg."""
    history = [h.get('value') for h in (row.get('history') or [])][-8:]
    line = row.get('line')
    body = t(64, 230, 'RESEARCH · NOT A PLAY', 36, DIM, BODY, 700, spacing=2) + t(64, 330, str(row.get('player') or '').upper(), 76, CHALK, DISPLAY, 700)
    direction = 'UNDER' if row.get('direction') == 'under' else 'OVER'
    body += t(64, 440, f"{direction} {line} {str(row.get('statWord') or '').upper()}", 92, KOOKD, DISPLAY, 700)
    if history:
        top, base, left, width = 520, 980, 96, W - 192
        hi = max([v for v in history if isinstance(v, (int, float))] + [line or 0]) * 1.15 or 1
        bw = width / len(history)
        for i, v in enumerate(history):
            if not isinstance(v, (int, float)):
                continue
            h = (base - top) * v / hi
            hit = (v < line) if direction == 'UNDER' else (v > line)
            body += f'<rect x="{left + i * bw + 10:.0f}" y="{base - h:.0f}" width="{bw - 20:.0f}" height="{h:.0f}" rx="10" fill="{KOOKD if hit else BURNT}"/>'
            body += t(left + i * bw + bw / 2, base - h - 14, f'{v:g}', 40, CHALK, DISPLAY, 700, 'middle')
        ly = base - (base - top) * line / hi
        body += f'<line x1="{left}" y1="{ly:.0f}" x2="{left + width}" y2="{ly:.0f}" stroke="{CHALK}" stroke-width="4" stroke-dasharray="16 12"/>'
        body += f'<line x1="{left}" y1="{base}" x2="{left + width}" y2="{base}" stroke="{LINE}" stroke-width="3"/>'
    need = None
    try:
        o = int(row.get('odds'))
        need = 100 / (o + 100) if o > 0 else -o / (-o + 100)
    except (TypeError, ValueError):
        pass
    body += t(64, 1080, f"{row.get('hits')} of {row.get('games')} this season" + (f' · price needs {pct(need)}' if need else ''), 44, CHALK, BODY, 700)
    body += t(64, 1150, f"{odds(row.get('odds'))} {row.get('book') or ''}  ·  history, not a probability", 34, DIM, BODY, 600)
    return frame('Research', body, chip_color=FELT_RAISED, chip_ink=CHALK)


def climb_card(pick, run, step, stake, payout, banked):
    """80/20 Climb rung. Port target: pick_card.ladder_svg. Facts only (no hype hook), per the 10-03 rule."""
    legs = pick.get('legs') or []
    body = t(64, 240, f'CLIMB #{run} · STEP {step}', 56, DIM, DISPLAY, 700, spacing=2)
    body += t(64, 400, f'${stake} → ${payout}', 150, CHALK, DISPLAY, 700)
    body += t(64, 470, f'{odds(pick.get("odds"))} {pick.get("book") or ""}  ·  ${banked} banked', 40, DIM, BODY, 600)
    y = 540
    for leg in legs[:3]:
        text = str(leg.get('title') or leg.get('displayTitle') or '')
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="100" rx="20" fill="{FELT_RAISED}"/>' + t(100, y + 64, text[:46], 44, CHALK, DISPLAY, 700)
        y += 118
    import math
    frac = max(0.03, min(1, math.log(max(50, banked + stake) / 50) / math.log(20)))
    body += f'<rect x="64" y="1000" width="{W - 128}" height="34" rx="17" fill="{LINE}"/><rect x="64" y="1000" width="{(W - 128) * frac:.0f}" height="34" rx="17" fill="{KOOKD}"/>'
    body += t(64, 1090, '$50', 34, DIM) + t(W - 64, 1090, '$1,000', 34, DIM, anchor='end')
    body += t(64, 1170, 'WIN: BANK 20%, RIDE 80%  ·  TRACKED APART FROM THE RECORD', 36, CHALK, DISPLAY, 700, spacing=1)
    return frame('80/20 Climb', body, chip_color=FELT_RAISED, chip_ink=CHALK)
