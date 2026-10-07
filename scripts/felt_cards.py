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
import base64
import re
from html import escape
from functools import lru_cache
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

W, H = 1080, 1350
FELT_NIGHT, FELT, FELT_RAISED, LINE = '#07120D', '#0E2219', '#15301F', '#21412F'
CHALK, DIM, KOOKD, KOOKD_INK = '#F2F7F4', '#A9C0B3', '#20C774', '#062B1C'
BURNT, BURNT_TEXT, TICKET, TICKET_INK, TICKET_DIM, TICKET_RULE = '#F2414E', '#FF6B75', '#F2F7F4', '#07120D', '#3D5447', '#C9D8D0'
DISPLAY = "'Barlow Condensed', 'Arial Narrow', sans-serif"
BODY = "'DM Sans', 'Helvetica Neue', Arial, sans-serif"
FOOTER = '21+ · Entertainment only · Gambling problem? 1-800-MY-RESET'
SITE = 'keenroudy.com/sports'
FLOORS = {'hero': 96, 'hook': 64, 'number': 56, 'row': 40, 'label': 30, 'footer': 26}
FONT_DIR = Path(__file__).with_name('fonts')


@lru_cache(maxsize=1)
def font_face():
    """Embed the OFL fonts so hosted Chrome renders exactly the same without a network font call."""
    display = base64.b64encode((FONT_DIR / 'BarlowCondensed-Bold.ttf').read_bytes()).decode('ascii')
    body = base64.b64encode((FONT_DIR / 'DMSans-Variable.ttf').read_bytes()).decode('ascii')
    return (f'<style>@font-face{{font-family:"Barlow Condensed";font-weight:700;'
            f'src:url(data:font/ttf;base64,{display})}}'
            f'@font-face{{font-family:"DM Sans";font-weight:100 1000;'
            f'src:url(data:font/ttf;base64,{body})}}</style>')


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
    size = int(r * (0.8 if len(abbr) <= 3 else 0.58))
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" stroke="rgba(255,255,255,.18)" stroke-width="3"/>'
            + t(x, y + size * 0.34, abbr, size, ink, BODY, 700, 'middle'))


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
            + font_face()
            + f'<rect width="{W}" height="{H}" fill="{FELT_NIGHT}"/><rect x="24" y="24" width="{W - 48}" height="{H - 48}" rx="36" fill="{FELT}" stroke="{LINE}" stroke-width="2"/>'
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
    ticket_h = 360
    body += f'<rect x="64" y="{top}" width="{W - 128}" height="{ticket_h}" rx="28" fill="{TICKET}"/>'
    # An open ticket is neutral. Brand green carries the read, never a result-colored fill.
    body += f'<rect data-zone="open-stub" x="{W - 64 - 170}" y="{top}" width="170" height="{ticket_h}" rx="28" fill="{FELT_RAISED}"/><rect x="{W - 64 - 170}" y="{top}" width="40" height="{ticket_h}" fill="{FELT_RAISED}"/>'
    body += f'<line x1="{W - 64 - 170}" y1="{top + 20}" x2="{W - 64 - 170}" y2="{top + ticket_h - 20}" stroke="{TICKET_RULE}" stroke-width="5" stroke-dasharray="14 12"/>'
    body += f'<circle cx="64" cy="{top + ticket_h / 2}" r="20" fill="{FELT}"/><circle cx="{W - 64}" cy="{top + ticket_h / 2}" r="20" fill="{FELT}"/>'
    body += t(104, top + 92, odds(pick.get('odds')), 88, TICKET_INK, DISPLAY, 700) + t(104 + 52 * len(odds(pick.get('odds'))), top + 92, str(pick.get('book') or '').upper(), 40, TICKET_DIM, BODY, 700)
    if isinstance(chance, (int, float)) and isinstance(needs, (int, float)) and pap.get('calibrated', True):
        body += t(104, top + 170, f'We make it {pct(chance)}. Price needs {pct(needs)}.', 42, TICKET_INK, BODY, 600)
        body += meter(104, top + 206, W - 128 - 170 - 80, chance, needs)
        fair = round(-100 * chance / (1 - chance)) if chance >= 0.5 else round(100 * (1 - chance) / chance)
        edge = round(100 * (chance - needs), 1)
        body += t(104, top + 282, 'FAIR PRICE', 30, TICKET_DIM, BODY, 700, spacing=1) + t(104, top + 338, odds(fair), 58, TICKET_INK, DISPLAY, 700)
        body += t(420, top + 282, 'EDGE', 30, TICKET_DIM, BODY, 700, spacing=1) + t(420, top + 338, f'+{edge} pts' if edge > 0 else f'{edge} pts', 58, TICKET_INK, DISPLAY, 700)
        body += t(W - 64 - 85, top + 190, pct(chance), 64, KOOKD, DISPLAY, 700, 'middle') + t(W - 64 - 85, top + 233, 'OUR CHANCE', 24, CHALK, BODY, 700, 'middle')
    else:
        body += t(104, top + 170, str(pick.get('_number') or ''), 42, TICKET_INK, BODY, 600)
    if record:
        body += t(64, min(1170, top + 440), f"SEASON {record}  ·  EVERY PLAY GRADED", 40, CHALK, DISPLAY, 700, spacing=1.5)
    return frame('Pick of the day' if featured else 'Best bet', body)


def receipt_card(day_label, rows, headline, season=None):
    """Morning receipt. Port target: pick_card.receipt_svg (receipt-day-<date>)."""
    headline = str(headline or 'RESULTS')
    hero_size = 170 if len(headline) <= 7 else 112
    body = t(64, 220, day_label.upper(), 44, DIM, BODY, 700, spacing=2) + t(64, 365, headline.upper(), hero_size, CHALK, DISPLAY, 700)
    shown = rows[:5]
    y = 430
    tall = 140 if len(shown) <= 3 else 112
    for r in shown:
        hit = r.get('result') == 'win'
        miss = r.get('result') == 'loss'
        color, mark_text, ink = (KOOKD, '✓ HIT', KOOKD_INK) if hit else (BURNT, '✗ MISS', TICKET_INK) if miss else ('#C9D8D0', '– PUSH', TICKET_INK)
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="{tall}" rx="22" fill="{TICKET}"/><rect x="{W - 64 - 190}" y="{y}" width="190" height="{tall}" rx="22" fill="{color}"/><rect x="{W - 64 - 190}" y="{y}" width="30" height="{tall}" fill="{color}"/>'
        body += t(W - 64 - 95, y + tall / 2 + 11, mark_text, 34, ink, BODY, 700, 'middle')
        title = str(r.get('displayTitle') or r.get('title') or '')
        kind = str(r.get('_kind') or 'best bet').replace('player', 'best bet').replace('team', 'best bet')
        kind = 'FUN' if 'parlay' in kind or 'lotto' in kind else 'CLIMB' if 'ladder' in kind or 'climb' in kind else 'BEST BET'
        body += t(96, y + 27, kind, 23, TICKET_DIM, BODY, 800, spacing=1.5)
        body += t(96, y + (77 if tall > 120 else 67), title[:42], 44 if tall > 120 else 36, TICKET_INK, DISPLAY, 700)
        detail = f"{odds(r.get('odds'))} {r.get('book') or ''}  {r.get('_final') or ''}".strip()
        if detail:
            detail_lines = wrap(detail, 24 if tall <= 120 else 27, 670, .52)
            detail_text = detail_lines[0] + (' …' if len(detail_lines) > 1 else '')
            body += t(96, y + tall - 12, detail_text, 24 if tall <= 120 else 27, TICKET_DIM, BODY, 600)
        y += tall + 14
    if len(rows) > len(shown):
        body += t(64, min(y + 28, 1138), f'+{len(rows) - len(shown)} MORE ON THE PUBLIC RECORD', 34, KOOKD, DISPLAY, 700, spacing=1)
    if season:
        body += t(64, 1188, f'SEASON {season}  ·  THE MISSES STAY ON THE RECORD', 38, CHALK, DISPLAY, 700, spacing=1.2)
    return frame('Receipt', body, chip_color=FELT_RAISED, chip_ink=CHALK)


def fun_ticket_card(pick, label='Fun ticket', art=None):
    """Longshot / lotto ticket. Port target: pick_card.ticket_svg (keep the sha256(id) % 3 style rotation)."""
    legs = pick.get('legs') or []
    body = t(64, 285, odds(pick.get('odds')), 178, KOOKD, DISPLAY, 700) + t(64, 365, str(pick.get('_hook') or label).upper(), 60, CHALK, DISPLAY, 700, spacing=1)
    timing = str(pick.get('_timing') or '').strip()
    if timing:
        body += t(64, 412, timing, 34, DIM, BODY, 650)
    y = 450
    art = art or []
    for index, leg in enumerate(legs[:6]):
        text = str(leg.get('title') or leg.get('displayTitle') or leg.get('selection') or '')
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="96" rx="20" fill="{FELT_RAISED}"/>' + t(100, y + 62, text[:46], 42, CHALK, DISPLAY, 700)
        item = art[index] if index < len(art) else None
        uris = ([item.get('uri')] if item and item.get('kind') == 'photo' else
                (item or {}).get('uris') or [])
        if uris:
            if len(uris) >= 2:
                body += f'<image href="{uris[0]}" x="850" y="{y + 15}" width="68" height="68" preserveAspectRatio="xMidYMid meet"/>'
                body += f'<image href="{uris[1]}" x="928" y="{y + 15}" width="68" height="68" preserveAspectRatio="xMidYMid meet"/>'
            else:
                body += f'<image href="{uris[0]}" x="874" y="{y + 4}" width="120" height="88" preserveAspectRatio="xMidYMax meet"/>'
        y += 112
    body += t(64, 1170, f"{str(pick.get('book') or '').upper()}  ·  TRACKED APART FROM BEST BETS", 38, DIM, BODY, 700, spacing=1)
    return frame(label, body, chip_color=FELT_RAISED, chip_ink=KOOKD)


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


def projection_sheet(games, league, day, week=None, logos=None, watches=None):
    """Phone-readable felt projection sheet; same 1080x1350 filename and data contract."""
    logos, watches = logos or {}, watches or {}
    title = f"WEEK {week} {'COLLEGE' if league == 'CFB' else league} PROJECTIONS" if week else f"{'COLLEGE' if league == 'CFB' else league} PROJECTIONS"
    rows = max(1, (len(games) + 1) // 2)
    top, bottom, gap = 250, 1198, 12
    pitch = (bottom - top) / rows
    card_h = pitch - gap
    card_w = 466
    team_size = 40 if rows <= 6 else 32
    info_size = 30 if rows <= 6 else 23

    def short_book(name):
        return {'DraftKings': 'DK', 'FanDuel': 'FD', 'BetMGM': 'MGM', 'ESPN BET': 'ESPN',
                'theScore Bet': 'SCORE', 'Caesars': 'CZR', 'BetRivers': 'BR', 'Fanatics': 'FAN'}.get(str(name or ''), str(name or '')[:5].upper())

    def num(value):
        return f'{float(value):g}' if isinstance(value, (int, float)) else '–'

    def spread(card, margin):
        if not isinstance(margin, (int, float)):
            return '–'
        if abs(margin) < .05:
            return 'PICK'
        team = card['home'] if margin > 0 else card['away']
        return f"{team.get('abbr') or team.get('abbreviation') or ''} −{num(abs(margin))}"

    def price(card, market):
        value = (card.get('value') or {}).get(market) or {}
        line, price_value, side = value.get('line'), value.get('odds'), value.get('side')
        if not isinstance(line, (int, float)) or not isinstance(price_value, (int, float)):
            if market == 'spread':
                raw = (card.get('market') or {}).get('spread')
                return spread(card, -raw) if isinstance(raw, (int, float)) else '–'
            raw = (card.get('market') or {}).get('total')
            return num(raw)
        if market == 'spread':
            team = card.get(side) or {}
            read = f"{team.get('abbr') or team.get('abbreviation') or ''} {line:+g}"
        else:
            read = f"{str(side or '').upper()} {line:g}"
        return f'{read} {odds(price_value)} {short_book(value.get("book"))}'

    body = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            + font_face() + f'<rect width="{W}" height="{H}" fill="{FELT_NIGHT}"/>'
            + f'<rect x="24" y="24" width="{W - 48}" height="{H - 48}" rx="36" fill="{FELT}" stroke="{LINE}" stroke-width="2"/>'
            + mark(56, 34, .8) + t(170, 98, 'KOOK’N', 52, CHALK, DISPLAY, 700, spacing=3)
            + t(1016, 94, 'SAVE THIS', 28, KOOKD, BODY, 800, 'end', 2)
            + t(64, 176, title, 58, CHALK, DISPLAY, 700, spacing=.8)
            + t(64, 218, f'{day:%A, %B} {day.day}  ·  green outline = current priced line clears the check', 27, DIM, BODY, 600))
    for index, card in enumerate(games):
        col, row = index % 2, index // 2
        x, y = 64 + col * (card_w + 20), top + row * pitch
        watch = watches.get(card.get('id'))
        border = KOOKD if watch else LINE
        body += f'<rect x="{x}" y="{y:.0f}" width="{card_w}" height="{card_h:.0f}" rx="20" fill="{FELT_RAISED}" stroke="{border}" stroke-width="{5 if watch else 2}"/>'
        away, home = card.get('away') or {}, card.get('home') or {}
        aw, hm = logos.get((card.get('id'), 'away')), logos.get((card.get('id'), 'home'))
        logo_y = y + 14
        if aw:
            body += f'<circle cx="{x + 35}" cy="{logo_y + 19:.0f}" r="20" fill="{CHALK}" opacity=".9"/>'
            body += f'<image href="{aw}" x="{x + 16}" y="{logo_y:.0f}" width="38" height="38" preserveAspectRatio="xMidYMid meet"/>'
        if hm:
            body += f'<circle cx="{x + 79}" cy="{logo_y + 19:.0f}" r="20" fill="{CHALK}" opacity=".9"/>'
            body += f'<image href="{hm}" x="{x + 60}" y="{logo_y:.0f}" width="38" height="38" preserveAspectRatio="xMidYMid meet"/>'
        team_x = x + (108 if aw or hm else 20)
        matchup = f"{away.get('abbr') or away.get('abbreviation') or '?'} @ {home.get('abbr') or home.get('abbreviation') or '?'}"
        body += t(team_x, y + 45, matchup, team_size, CHALK, DISPLAY, 700)
        v2 = card.get('v2') or {}
        score = f"{num(v2.get('away'))}–{num(v2.get('home'))}"
        if not watch:
            body += t(x + card_w - 18, y + 43, score, info_size + 2, KOOKD, DISPLAY, 700, 'end')
        if watch:
            badge = f'#{watch[0]} {watch[2]}'
            badge_w = min(214, max(118, 18 + len(badge) * 10))
            body += f'<rect x="{x + card_w - badge_w - 12:.0f}" y="{y + 5:.0f}" width="{badge_w}" height="28" rx="14" fill="{FELT_NIGHT}" stroke="{KOOKD}" stroke-width="2"/>'
            body += t(x + card_w - 22, y + 26, badge, 19, KOOKD, BODY, 800, 'end')
        ours_spread = spread(card, v2.get('margin'))
        ours_total = num(v2.get('total'))
        sy = y + (88 if card_h >= 132 else 72)
        ty = y + (128 if card_h >= 132 else 103)
        body += t(x + 18, sy, f'SPREAD  OUR {ours_spread}  ·  MARKET {price(card, "spread")}', info_size, CHALK, DISPLAY, 700)
        body += t(x + 18, ty, f'TOTAL  OUR {ours_total}  ·  MARKET {price(card, "total")}', info_size, CHALK, DISPLAY, 700)
    body += f'<line x1="64" y1="1228" x2="{W - 64}" y2="1228" stroke="{LINE}" stroke-width="2"/>'
    body += t(64, 1270, FOOTER, 26, DIM) + t(64, 1310, SITE, 26, KOOKD, BODY, 700)
    return body + '</svg>'


def climb_path(progress, y=984):
    """Persistent dollar checkpoints without guessing the number or price of future rungs."""
    checkpoints = (50, 100, 250, 500, 1000)
    xs = (104, 306, 520, 730, 925)
    body = f'<line x1="{xs[0]}" y1="{y}" x2="{xs[-1]}" y2="{y}" stroke="{LINE}" stroke-width="12" stroke-linecap="round"/>'
    current_set = False
    for index, (amount, x) in enumerate(zip(checkpoints, xs)):
        done = progress > amount or (amount == 1000 and progress >= amount)
        current = not done and not current_set
        current_set = current_set or current
        fill = KOOKD if done else FELT_NIGHT
        stroke = KOOKD if done or current else TICKET_DIM
        body += f'<circle cx="{x}" cy="{y}" r="31" fill="{fill}" stroke="{stroke}" stroke-width="{7 if current else 4}"/>'
        if done:
            body += t(x, y + 12, '✓', 40, KOOKD_INK, BODY, 800, 'middle')
        body += t(x, y + 76, f'${amount:,}', 29, CHALK if done or current else DIM, DISPLAY, 700, 'middle')
        if index == len(checkpoints) - 1:
            body += f'<path d="M{x} {y - 31}V{y - 108}h52l-13 17 13 17h-52" fill="{KOOKD}" stroke="{CHALK}" stroke-width="3"/>'
    return body


def climb_card(pick, run, step, stake, payout, banked):
    """80/20 Climb rung. Port target: pick_card.ladder_svg. Facts only (no hype hook), per the 10-03 rule."""
    legs = pick.get('legs') or []
    body = t(64, 240, f'CLIMB #{run} · STEP {step}', 56, DIM, DISPLAY, 700, spacing=2)
    body += t(64, 400, f'${stake} → ${payout}', 150, CHALK, DISPLAY, 700)
    all_banked = int(pick.get('_allClimbsBanked') if pick.get('_allClimbsBanked') is not None else banked)
    body += t(64, 470, f'{odds(pick.get("odds"))} {pick.get("book") or ""}', 40, DIM, BODY, 600)
    body += t(64, 520, f'THIS CLIMB  ${banked} BANKED  ·  ALL CLIMBS  ${all_banked} BANKED', 34, KOOKD, DISPLAY, 700, spacing=.8)
    y = 565
    for leg in legs[:3]:
        text = str(leg.get('title') or leg.get('displayTitle') or '')
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="94" rx="20" fill="{FELT_RAISED}"/>' + t(100, y + 61, text[:46], 42, CHALK, DISPLAY, 700)
        y += 108
    body += climb_path(max(50, int(banked or 0) + int(stake or 0)), 956)
    body += t(64, 1168, 'BANK 20%  ·  RIDE 80%  ·  EVERY STEP STAYS PUBLIC', 34, CHALK, DISPLAY, 700, spacing=1)
    return frame('80/20 Climb', body, chip_color=FELT_RAISED, chip_ink=CHALK)


def receipt_from_existing(receipt):
    """Adapt the append-only receipt presentation without changing any result or accounting."""
    rows = []
    for row in receipt.get('rows') or []:
        result, title = row[:2]
        detail = row[2] if len(row) > 2 else ''
        kind = row[3] if len(row) > 3 else ('ladder' if 'climb' in str(title).lower() else
                                           'parlay' if any(word in str(title).lower() for word in ('parlay', 'lotto')) else 'best bet')
        rows.append({'result': result, 'title': title, '_final': detail, '_kind': kind})
    return receipt_card(receipt.get('when') or 'Results', rows, receipt.get('title'), receipt.get('season'))


def climb_result_card(pick):
    info = pick.get('ladder') or {}
    result = str(pick.get('result') or 'push').lower()
    tone, verdict, ink = ((KOOKD, '✓ HIT', KOOKD_INK) if result == 'win' else
                           (BURNT, '✗ MISS', TICKET_INK) if result == 'loss' else
                           (TICKET_RULE, '– PUSH', TICKET_INK))
    stake, payout = info.get('stake', 0), info.get('payout', 0)
    this_climb = info.get('bankedAfter', info.get('banked', 0)) if result == 'win' else info.get('banked', 0)
    all_banked = int(pick.get('_allClimbsBanked') if pick.get('_allClimbsBanked') is not None else this_climb or 0)
    body = t(64, 240, f"CLIMB #{info.get('run', 1)} · STEP {info.get('step', 1)}", 56, DIM, DISPLAY, 700, spacing=2)
    body += f'<rect x="64" y="300" width="{W - 128}" height="210" rx="28" fill="{tone}"/>'
    body += t(104, 390, verdict, 64, ink, DISPLAY, 700)
    result_line = f'${stake} → ${payout}' if result == 'win' else f'NEXT  ${info.get("start", 50)} RESTART' if result == 'loss' else f'${stake} RETURNS'
    body += t(104, 472, result_line, 82, ink, DISPLAY, 700)
    y = 550
    for leg in (pick.get('legs') or [])[:3]:
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="92" rx="20" fill="{FELT_RAISED}"/>'
        body += t(100, y + 59, str(leg.get('title') or '')[:46], 40, CHALK, DISPLAY, 700)
        y += 106
    if result == 'win':
        progress = int(info.get('totalAfter') or (int(this_climb or 0) + int(info.get('nextStake') or 0)))
    elif result == 'loss':
        progress = int(info.get('start') or 50)
    else:
        progress = int(info.get('banked') or 0) + int(stake or 0)
    body += climb_path(max(50, progress), 926)
    body += t(64, 1096, f'THIS CLIMB  ${int(this_climb or 0)} BANKED', 36, CHALK, DISPLAY, 700, spacing=1)
    body += t(64, 1148, f'ALL CLIMBS  ${all_banked} BANKED  ·  EVERY STEP STAYS PUBLIC', 34, KOOKD, DISPLAY, 700, spacing=.8)
    return frame('Climb result', body, chip_color=tone, chip_ink=ink)


def research_choice_card(choice, art=None):
    """The existing research category in the felt system; exact rows remain the source of truth."""
    art = art or {}
    rows = (choice.get('rows') or [])[:4]
    body = t(64, 225, str(choice.get('title') or 'RESEARCH').upper(), 58, CHALK, DISPLAY, 700)
    hero = next((uri for uri in art.values() if uri), None)
    if hero and len(rows) == 1:
        body += photo(900, 238, 82, hero)
    top = 300
    row_h = 360 if len(rows) == 1 else min(182, 700 / max(1, len(rows)))
    for index, row in enumerate(rows):
        if len(rows) == 1:
            title = str(row.get('title') or '')
            title_lines = wrap(title, 76, 760 if hero else W - 192, .53)[:2]
            y = top
            for line_index, line in enumerate(title_lines):
                body += t(64, y + line_index * 82, line, 76, CHALK, DISPLAY, 700)
            y += max(1, len(title_lines)) * 82 + 18
            price = str(row.get('price') or '')
            if price:
                body += t(64, y, price, 56, KOOKD, DISPLAY, 700)
                y += 82
            hits, games = row.get('hits'), row.get('games')
            selection = re.search(r'\b(over|under)\s+([0-9.]+)', title, re.I)
            if selection and isinstance(hits, int) and isinstance(games, int):
                proof = f'{selection.group(1).title()} {selection.group(2)} in {hits} of the last {games}'
            else:
                proof = str(row.get('metric') or '')
            body += f'<rect x="64" y="{y - 48}" width="{W - 128}" height="238" rx="24" fill="{FELT_RAISED}" stroke="{LINE}"/>'
            body += t(96, y + 20, proof, 44, CHALK, BODY, 750)
            matchup = row.get('matchup') or {}
            if isinstance(matchup.get('rank'), int) and isinstance(matchup.get('of'), int):
                rank = int(matchup['rank'])
                suffix = 'th' if 10 <= rank % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(rank % 10, 'th')
                tone = 'soft' if matchup.get('supports') else 'tough' if matchup.get('opposes') else 'neutral'
                defense = f"{row.get('opponentAbbr') or 'Opponent'}: {rank}{suffix} of {matchup['of']} vs {matchup.get('pos') or 'position'}s ({tone})"
            else:
                defense = str(row.get('detail') or '')
            body += t(96, y + 88, defense, 36, DIM, BODY, 650)
            timing = str(row.get('matchupLabel') or '').upper()
            try:
                local = datetime.fromisoformat(str(row.get('kickoff')).replace('Z', '+00:00')).astimezone(
                    ZoneInfo('America/Indiana/Indianapolis'))
                timing += ('  ·  ' if timing else '') + f'{local:%a %b %-d · %-I:%M %p ET}'
            except (TypeError, ValueError):
                pass
            if timing:
                body += t(96, y + 154, timing, 31, KOOKD, BODY, 700)
            if isinstance(hits, int) and isinstance(games, int) and games > 0:
                bar_x, bar_y, bar_w = 64, y + 232, W - 128
                body += f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="22" rx="11" fill="{LINE}"/>'
                body += f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w * hits / games:.1f}" height="22" rx="11" fill="{KOOKD}"/>'
                body += t(64, bar_y + 68, f'{hits} HIT  ·  {games - hits} MISSED', 30, DIM, BODY, 700, spacing=.7)
            continue
        y = top + index * (row_h + 18)
        body += f'<rect x="64" y="{y:.0f}" width="{W - 128}" height="{row_h:.0f}" rx="22" fill="{FELT_RAISED}" stroke="{LINE}"/>'
        body += f'<rect x="64" y="{y + 20:.0f}" width="6" height="{max(30, row_h - 40):.0f}" rx="3" fill="{KOOKD}"/>'
        title = str(row.get('title') or '')
        price = str(row.get('price') or '')
        metric = str(row.get('metric') or '')
        detail = str(row.get('detail') or '')
        title_size = 54 if len(rows) == 1 else 42
        body += t(98, y + 72, title[:46], title_size, CHALK, DISPLAY, 700)
        body += t(W - 96, y + 72, price[:24], 48 if len(rows) == 1 else 40, KOOKD, DISPLAY, 700, 'end')
        body += t(98, y + (160 if len(rows) == 1 else 108), metric[:52], 42 if len(rows) == 1 else 32, CHALK, BODY, 700)
        if row_h >= 160:
            body += t(98, y + (226 if len(rows) == 1 else 148), detail[:70], 34 if len(rows) == 1 else 26, DIM, BODY, 600)
        if len(rows) == 1:
            proof_number = metric.split(' ', 1)[0]
            body += t(98, y + 326, proof_number, 96, KOOKD, DISPLAY, 700)
            body += t(295, y + 318, 'EXACT-LINE PROOF', 32, DIM, DISPLAY, 700, spacing=1)
    label = {'upset': 'Underdog research', 'spread-dog': 'Spread research',
             'matchup': 'Matchup research', 'season': 'Trend research',
             'end-zone': 'Scorer research'}.get(choice.get('kind'), 'Slate research')
    return frame(label, body, chip_color=FELT_RAISED, chip_ink=CHALK)
