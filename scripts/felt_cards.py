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


def truncate(text, limit):
    """Shorten display copy without making a clipped word look complete."""
    value = str(text or '')
    return value if len(value) <= limit else value[:max(1, limit - 1)].rstrip() + '…'


def fit_size(text, maximum, width, ratio=.5, minimum=16):
    """Conservatively fit one line inside a known SVG tile width."""
    value = str(text or '')
    if not value:
        return maximum
    return max(minimum, min(maximum, width / (len(value) * ratio)))


def fit_t(x, y, text, maximum, width, color=CHALK, family=DISPLAY, weight=700,
          anchor='start', spacing=0, minimum=16):
    size = fit_size(text, maximum, width, .5 if family == DISPLAY else .54, minimum)
    return t(x, y, text, f'{size:.1f}', color, family, weight, anchor, spacing)


def odds(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ''
    return f'+{n}' if n > 0 else f'−{abs(n)}'


def pct(x):
    return f'{int(100 * x + 0.5)}%' if isinstance(x, (int, float)) else ''


def pct1(x):
    return f'{100 * x:.1f}%' if isinstance(x, (int, float)) else ''


def dollars(value):
    try:
        return f'${int(value):,}'
    except (TypeError, ValueError):
        return '$0'


def luminance(hex_color):
    try:
        r, g, b = (int(hex_color.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, AttributeError):
        return 0
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def team_chip(x, y, team, r=34, logo=None):
    if logo:
        return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{CHALK}" opacity=".94" stroke="{LINE}" stroke-width="3"/>'
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
    # Split only on ordinary spaces so a non-breaking space can keep a team's
    # signed spread attached to the last word of its name.
    words, lines, line = [word for word in str(text).split(' ') if word], [], ''
    for word in words:
        trial = f'{line} {word}'.strip()
        if len(trial) * size * family_ratio > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def wrap_fit(text, maximum, width, max_lines=3, minimum=36, family_ratio=.4):
    """Wrap every word at the largest useful display size.

    Barlow Condensed is materially narrower than the generic fallback estimate
    used by :func:`fit_size`.  Trying the embedded font's conservative ratio at
    successively smaller sizes keeps full wager wording on the card without the
    former ``[:2]`` data loss.
    """
    value = str(text or '').strip()
    if not value:
        return [], float(maximum)
    preferred_lines = min(2, max_lines)
    for wanted_lines in (preferred_lines, max_lines):
        size = float(maximum)
        while size >= minimum:
            lines = wrap(value, size, width, family_ratio)
            if len(lines) <= wanted_lines:
                return lines, size
            size -= 2
    size = float(minimum)
    lines = wrap(value, size, width, family_ratio)
    while len(lines) > max_lines and size > 18:
        size -= 1
        lines = wrap(value, size, width, family_ratio)
    return lines, size


def shrink_then_wrap(text, maximum, width, max_lines=2, minimum=24, family_ratio=.4):
    """Prefer one complete line, then wrap complete words without slicing copy."""
    value = str(text or '').strip()
    if not value:
        return [], float(maximum)
    size = float(maximum)
    while size >= minimum:
        lines = wrap(value, size, width, family_ratio)
        if len(lines) == 1:
            return lines, size
        size -= 1
    size = float(maximum)
    while size >= minimum:
        lines = wrap(value, size, width, family_ratio)
        if len(lines) <= max_lines:
            return lines, size
        size -= 1
    return wrap(value, minimum, width, family_ratio), float(minimum)


def keep_spread_with_team(text):
    """Keep a signed spread with the team word immediately before it."""
    return re.sub(r'(\S)\s+([+\-\u2212]\d+(?:\.\d+)?)\b',
                  lambda found: f'{found.group(1)}\u00a0{found.group(2)}', str(text or ''))


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
        player_lines, player_size = wrap_fit(player.upper(), 72, W - 128,
                                             max_lines=2, minimum=48,
                                             family_ratio=.47)
        body += '<g data-zone="play-subject">'
        for line in player_lines:
            body += t(64, y, line, f'{player_size:.1f}', CHALK, DISPLAY, 700, spacing=1)
            y += player_size + 8
        body += '</g>'
        y += 32
    selection_lines, selection_size = wrap_fit(keep_spread_with_team(selection), 120, W - 128,
                                               max_lines=3, minimum=60,
                                               family_ratio=.46)
    body += '<g data-zone="play-selection">'
    for line in selection_lines:
        body += t(64, y, line, f'{selection_size:.1f}', KOOKD, DISPLAY, 700)
        y += selection_size * .98
    body += '</g>'
    top = max(y + 30, 520)
    ticket_h = 360
    body += f'<rect x="64" y="{top}" width="{W - 128}" height="{ticket_h}" rx="28" fill="{TICKET}"/>'
    # An open ticket is neutral. Brand green carries the read, never a result-colored fill.
    stub_w = 190
    body += f'<rect data-zone="open-stub" x="{W - 64 - stub_w}" y="{top}" width="{stub_w}" height="{ticket_h}" rx="28" fill="{FELT_RAISED}"/><rect x="{W - 64 - stub_w}" y="{top}" width="40" height="{ticket_h}" fill="{FELT_RAISED}"/>'
    body += f'<line x1="{W - 64 - stub_w}" y1="{top + 20}" x2="{W - 64 - stub_w}" y2="{top + ticket_h - 20}" stroke="{TICKET_RULE}" stroke-width="5" stroke-dasharray="14 12"/>'
    body += f'<circle cx="64" cy="{top + ticket_h / 2}" r="20" fill="{FELT}"/><circle cx="{W - 64}" cy="{top + ticket_h / 2}" r="20" fill="{FELT}"/>'
    body += t(104, top + 92, odds(pick.get('odds')), 88, TICKET_INK, DISPLAY, 700) + t(104 + 52 * len(odds(pick.get('odds'))), top + 92, str(pick.get('book') or '').upper(), 40, TICKET_DIM, BODY, 700)
    if isinstance(chance, (int, float)) and isinstance(needs, (int, float)) and pap.get('calibrated', True):
        body += t(104, top + 170, f'We make it {pct1(chance)}. Price needs {pct1(needs)}.', 42, TICKET_INK, BODY, 600)
        body += meter(104, top + 206, W - 128 - stub_w - 80, chance, needs)
        fair = round(-100 * chance / (1 - chance)) if chance >= 0.5 else round(100 * (1 - chance) / chance)
        edge = round(100 * (chance - needs), 1)
        body += t(104, top + 282, 'FAIR PRICE', 30, TICKET_DIM, BODY, 700, spacing=1) + t(104, top + 338, odds(fair), 58, TICKET_INK, DISPLAY, 700)
        body += t(420, top + 282, 'EDGE', 30, TICKET_DIM, BODY, 700, spacing=1) + t(420, top + 338, f'+{edge} pts' if edge > 0 else f'{edge} pts', 54, TICKET_INK, DISPLAY, 700)
        body += t(W - 64 - stub_w / 2, top + 190, pct1(chance), 60, KOOKD, DISPLAY, 700, 'middle')
        body += (f'<g data-zone="chance-label">'
                 + fit_t(W - 64 - stub_w / 2, top + 235, 'OUR CHANCE', 24, stub_w - 40,
                         CHALK, BODY, 700, 'middle', minimum=18)
                 + '</g>')
    else:
        body += t(104, top + 170, str(pick.get('_number') or ''), 42, TICKET_INK, BODY, 600)
    if record:
        body += t(64, min(1170, top + 440), f"SEASON {record}  ·  EVERY PLAY GRADED", 40, CHALK, DISPLAY, 700, spacing=1.5)
    return frame('Pick of the day' if featured else 'Best bet', body)


def receipt_scope(headline):
    """Return the public receipt category and the record used as its hero."""
    value = str(headline or 'RESULTS').strip()
    record = re.search(r'\b\d+[\-\u2013]\d+(?:[\-\u2013]\d+)?\b', value)
    hero = record.group(0).replace('-', '\u2013') if record else value
    lower = value.lower()
    if lower.startswith('fun parlay') or lower.startswith('fun ticket'):
        return 'FUN TICKETS', hero
    if lower.startswith('ladder') or lower.startswith('80/20 climb') or lower.startswith('climb'):
        return '80/20 CLIMB', hero
    return 'BEST BETS', hero


def public_receipt_kind(value):
    """Translate internal receipt families to owner-approved public labels."""
    lower = str(value or '').lower()
    if 'player' in lower:
        return 'PLAYER PROPS'
    if 'team' in lower or 'game' in lower:
        return 'GAME LINES'
    if any(word in lower for word in ('parlay', 'lotto', 'fun')):
        return 'FUN TICKETS'
    if any(word in lower for word in ('ladder', 'climb')):
        return '80/20 CLIMB'
    return str(value or 'BEST BET').upper()


def receipt_tracked(row):
    kind = str(row.get('_kind') or row.get('title') or '').lower()
    return any(word in kind for word in ('parlay', 'lotto', 'fun', 'ladder', 'climb'))


def receipt_outcome(result, words=True):
    result = str(result or '').lower()
    if result == 'win':
        return ('✓ HIT' if words else '✓'), KOOKD, KOOKD_INK
    if result == 'loss':
        return ('✗ MISS' if words else '✗'), BURNT, TICKET_INK
    if result == 'void':
        return ('– VOID' if words else '– VOID'), '#C9D8D0', TICKET_INK
    return ('– PUSH' if words else '– PUSH'), '#C9D8D0', TICKET_INK


def receipt_hidden_best(rows):
    if not rows:
        return ''
    if len(rows) == 1:
        mark_text, _color, _ink = receipt_outcome(rows[0].get('result'), words=False)
        return f'+1 BEST BET {mark_text}'
    labels = []
    for result, label in (('win', 'HIT'), ('loss', 'MISSED'), ('push', 'PUSH'), ('void', 'VOID')):
        count = sum(row.get('result') == result for row in rows)
        if count:
            labels.append(f'{count} {label}')
    return f'+{len(rows)} BEST BETS' + (f" · {' · '.join(labels)}" if labels else '')


def receipt_tracked_summary(rows):
    fun = [row for row in rows if any(word in str(row.get('_kind') or row.get('title') or '').lower()
                                      for word in ('parlay', 'lotto', 'fun'))]
    climb = [row for row in rows if any(word in str(row.get('_kind') or row.get('title') or '').lower()
                                        for word in ('ladder', 'climb'))]
    labels = []
    if fun:
        wins = sum(row.get('result') == 'win' for row in fun)
        losses = sum(row.get('result') == 'loss' for row in fun)
        pushes = sum(row.get('result') == 'push' for row in fun)
        voids = sum(row.get('result') == 'void' for row in fun)
        record = f'{wins}–{losses}' + (f'–{pushes}' if pushes else '')
        labels.append(f'FUN TICKETS {record}' + (f' · {voids} VOID' if voids else ''))
    previous_run = None
    for row in climb:
        title = str(row.get('title') or '')
        run = re.search(r'\bclimb\s*#?\s*(\d+)\b', title, re.I)
        step = re.search(r'\bstep\s*(\d+)\b', str(row.get('title') or ''), re.I)
        mark_text, _color, _ink = receipt_outcome(row.get('result'), words=False)
        run_number = run.group(1) if run else None
        prefix = '' if run_number and run_number == previous_run else 'CLIMB'
        if prefix and run_number:
            prefix += f' #{run_number}'
        labels.append(f'{prefix} STEP {step.group(1) if step else ""} {mark_text}'.strip().replace('  ', ' '))
        previous_run = run_number
    return ' · '.join(labels)


def receipt_card(day_label, rows, headline, season=None):
    """Morning receipt. Port target: pick_card.receipt_svg (receipt-day-<date>)."""
    category, hero = receipt_scope(headline)
    hero_size = 170 if len(hero) <= 7 else 112
    body = (t(64, 220, day_label.upper(), 44, DIM, BODY, 700, spacing=2)
            + t(64, 286, category, 34, DIM, BODY, 800, spacing=2)
            + t(64, 400, hero.upper(), min(hero_size, 142), CHALK, DISPLAY, 700))
    y = 430
    summaries = [row for row in rows if row.get('_summaryRow')]
    best = [row for row in rows if not row.get('_summaryRow') and not receipt_tracked(row)]
    tracked = [row for row in rows if not row.get('_summaryRow') and receipt_tracked(row)]
    best_summaries = [row for row in summaries if not receipt_tracked(row)]
    tracked_summaries = [row for row in summaries if receipt_tracked(row)]
    if summaries:
        shown = best_summaries + tracked_summaries
    elif len(best) + len(tracked) <= 5:
        shown = best + tracked
    else:
        shown = best[:5]
    tall = 140 if len(shown) <= 3 else 116
    crossed_into_tracked = False
    for r in shown:
        is_tracked = receipt_tracked(r)
        if is_tracked and not crossed_into_tracked:
            body += (f'<line data-zone="tracked-divider" x1="64" y1="{y + 4}" x2="{W - 64}" y2="{y + 4}" '
                     f'stroke="{LINE}" stroke-width="2"/>'
                     + t(64, y + 37, 'TRACKED APART FROM BEST BETS', 25, DIM, BODY, 800, spacing=1.2))
            y += 52
            crossed_into_tracked = True
        if r.get('_summaryRow'):
            title = public_receipt_kind(r.get('_kind') or r.get('title'))
            record = re.search(r'\b\d+[\-\u2013]\d+(?:[\-\u2013]\d+)?\b', str(r.get('title') or ''))
            record_text = record.group(0).replace('-', '\u2013') if record else '\u2014'
            body += (f'<rect data-zone="category-record" x="64" y="{y}" width="{W - 128}" height="{tall}" rx="22" fill="{FELT_RAISED}" stroke="{LINE}"/>'
                     + t(96, y + tall / 2 + 12, title, 38, CHALK, DISPLAY, 700)
                     + t(W - 96, y + tall / 2 + 15, record_text, 56, CHALK, DISPLAY, 700, 'end'))
            y += tall + 14
            continue
        mark_text, color, ink = receipt_outcome(r.get('result'))
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="{tall}" rx="22" fill="{TICKET}"/><rect x="{W - 64 - 190}" y="{y}" width="190" height="{tall}" rx="22" fill="{color}"/><rect x="{W - 64 - 190}" y="{y}" width="30" height="{tall}" fill="{color}"/>'
        body += t(W - 64 - 95, y + tall / 2 + 11, mark_text, 34, ink, BODY, 700, 'middle')
        title = str(r.get('displayTitle') or r.get('title') or '')
        kind = str(r.get('_kind') or 'best bet').replace('player', 'best bet').replace('team', 'best bet')
        kind = 'FUN' if 'parlay' in kind or 'lotto' in kind else 'CLIMB' if 'ladder' in kind or 'climb' in kind else 'BEST BET'
        body += t(96, y + (27 if tall > 120 else 22), kind,
                  23 if tall > 120 else 20, TICKET_DIM, BODY, 800, spacing=1.5)
        title_lines, title_size = shrink_then_wrap(
            title, 42 if tall > 120 else 34, 710, max_lines=2,
            minimum=28 if tall > 120 else 24)
        title_start = y + (68 if tall > 120 else 52)
        if len(title_lines) > 1:
            title_start -= (title_size + 1) / 2
        body += '<g data-zone="receipt-title">'
        for line_index, line in enumerate(title_lines):
            body += t(96, title_start + line_index * (title_size + 1), line,
                      f'{title_size:.1f}', TICKET_INK, DISPLAY, 700)
        body += '</g>'
        detail = f"{odds(r.get('odds'))} {r.get('book') or ''}  {r.get('_final') or ''}".strip()
        if detail:
            detail_lines, detail_size = shrink_then_wrap(
                detail, 27 if tall > 120 else 20, 710, max_lines=2,
                minimum=19 if tall > 120 else 16, family_ratio=.52)
            detail_step = detail_size + 1
            detail_start = y + tall - 9 - (len(detail_lines) - 1) * detail_step
            body += '<g data-zone="receipt-detail">'
            for line_index, line in enumerate(detail_lines):
                body += t(96, detail_start + line_index * detail_step, line,
                          f'{detail_size:.1f}', TICKET_DIM, BODY, 600)
            body += '</g>'
        y += tall + 14
    if not summaries:
        hidden_best = best[len([row for row in shown if not receipt_tracked(row)]):]
        hidden_label = receipt_hidden_best(hidden_best)
        if hidden_label:
            body += fit_t(64, min(y + 26, 1092), hidden_label, 31, W - 128, CHALK,
                          DISPLAY, 700, minimum=24)
            y += 42
        hidden_tracked = tracked if not any(receipt_tracked(row) for row in shown) else tracked[len([row for row in shown if receipt_tracked(row)]):]
        tracked_label = receipt_tracked_summary(hidden_tracked)
        if tracked_label:
            divider_y = min(y + 4, 1110)
            body += (f'<line data-zone="tracked-divider" x1="64" y1="{divider_y}" x2="{W - 64}" '
                     f'y2="{divider_y}" stroke="{LINE}" stroke-width="2"/>')
            body += fit_t(64, min(divider_y + 36, 1146), f'TRACKED APART · {tracked_label}', 30,
                          W - 128, DIM, DISPLAY, 700, minimum=22)
    if season:
        body += t(64, 1188, f'SEASON {season}  ·  THE MISSES STAY ON THE RECORD', 38, CHALK, DISPLAY, 700, spacing=1.2)
    return frame('Receipt', body, chip_color=FELT_RAISED, chip_ink=CHALK)


def fun_ticket_card(pick, label='Fun ticket', art=None):
    """Longshot / lotto ticket. Port target: pick_card.ticket_svg (keep the sha256(id) % 3 style rotation)."""
    legs = pick.get('legs') or []
    body = t(64, 285, odds(pick.get('odds')), 178, CHALK, DISPLAY, 700) + t(64, 365, str(pick.get('_hook') or label).upper(), 60, CHALK, DISPLAY, 700, spacing=1)
    timing = str(pick.get('_timing') or '').strip()
    if timing:
        body += t(64, 412, timing, 34, DIM, BODY, 650)
    y = 450
    art = art or []
    for index, leg in enumerate(legs[:6]):
        text = str(leg.get('title') or leg.get('displayTitle') or leg.get('selection') or '')
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="96" rx="20" fill="{FELT_RAISED}"/>' + fit_t(100, y + 64, truncate(text, 52), 49, 720, CHALK, DISPLAY, 700, minimum=37)
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


def sheet_row_geometry(card_h, caution=False):
    """Return non-overlapping baselines for both compact and roomy projection tiles."""
    if card_h < 122:
        return {'spread': 79, 'total': 100, 'caution': 58 if caution else None,
                'cautionSize': 14}
    if card_h < 140:
        return {'spread': 88, 'total': min(119, card_h - 9),
                'caution': 65 if caution else None, 'cautionSize': 14}
    if card_h < 180:
        return {'spread': 101, 'total': 132, 'caution': 70 if caution else None,
                'cautionSize': 16}
    return {'spread': 88, 'total': 128, 'caution': 168 if caution else None,
            'cautionSize': 18}


def projection_sheet(games, league, day, week=None, logos=None, watches=None):
    """Phone-readable felt projection sheet; same 1080x1350 filename and data contract."""
    logos, watches = logos or {}, watches or {}
    title = f"WEEK {week} {'COLLEGE' if league == 'CFB' else league} PROJECTIONS" if week else f"{'COLLEGE' if league == 'CFB' else league} PROJECTIONS"
    rows = max(1, (len(games) + 1) // 2)
    top, bottom = 250, 1198
    gap = 4 if rows >= 7 else 12
    pitch = (bottom - top) / rows
    card_h = pitch - gap
    card_w = 466
    team_size = 40 if rows <= 6 else 32
    info_size = 30 if rows <= 6 else 23

    def public_book(name):
        return {'ESPN BET': 'theScore Bet', 'theScore': 'theScore Bet'}.get(str(name or ''), str(name or ''))

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
        return f'{read} {odds(price_value)} {public_book(value.get("book"))}'

    body = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            + font_face() + f'<rect width="{W}" height="{H}" fill="{FELT_NIGHT}"/>'
            + f'<rect x="24" y="24" width="{W - 48}" height="{H - 48}" rx="36" fill="{FELT}" stroke="{LINE}" stroke-width="2"/>'
            + mark(56, 34, .8) + t(170, 98, 'KOOK’N', 52, CHALK, DISPLAY, 700, spacing=3)
            + t(1016, 94, 'SAVE THIS', 28, KOOKD, BODY, 800, 'end', 2)
            + t(64, 176, title, 58, CHALK, DISPLAY, 700, spacing=.8)
            + t(64, 218, f'{day:%A, %B} {day.day}  ·  rings name the lines we like · watches, not picks', 27, DIM, BODY, 600))
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
        team_width = max(100, x + card_w - 86 - team_x)
        body += fit_t(team_x, y + 45, matchup, team_size, team_width, CHALK, DISPLAY, 700, minimum=22)
        v2 = card.get('v2') or {}
        score = f"{num(v2.get('away'))}–{num(v2.get('home'))}"
        body += t(x + card_w - 18, y + 43, score, info_size + 2, CHALK, DISPLAY, 700, 'end')
        ours_spread = spread(card, v2.get('margin'))
        ours_total = num(v2.get('total'))
        caution = watch and watch[3].get('collegeGapCaution')
        geometry = sheet_row_geometry(card_h, bool(caution))
        sy, ty = y + geometry['spread'], y + geometry['total']
        spread_line = f'SPREAD  OUR {ours_spread}  ·  MARKET {price(card, "spread")}'
        total_line = f'TOTAL  OUR {ours_total}  ·  MARKET {price(card, "total")}'
        if watch and watch[1] == 'spread':
            spread_line = f'LIKE #{watch[0]}  {watch[2]} {odds(watch[3].get("odds"))} {public_book(watch[3].get("book"))}'
        if watch and watch[1] == 'total':
            total_line = f'LIKE #{watch[0]}  {watch[2]} {odds(watch[3].get("odds"))} {public_book(watch[3].get("book"))}'
        if caution:
            caution_text = (f'{caution:g}-PT GAP · CAUTION' if card_h < 122 else
                            f'{caution:g}-PT COLLEGE GAP · CAUTION')
            body += (f'<g data-zone="college-gap-caution">'
                     + fit_t(x + card_w - 18, y + geometry['caution'], caution_text,
                             geometry['cautionSize'], card_w - 36, DIM, BODY, 700, 'end', minimum=12)
                     + '</g>')
        body += fit_t(x + 18, sy, spread_line, info_size, card_w - 36,
                      KOOKD if watch and watch[1] == 'spread' else CHALK, DISPLAY, 700, minimum=15)
        body += fit_t(x + 18, ty, total_line, info_size, card_w - 36,
                      KOOKD if watch and watch[1] == 'total' else CHALK, DISPLAY, 700, minimum=15)
    body += f'<line x1="64" y1="1228" x2="{W - 64}" y2="1228" stroke="{LINE}" stroke-width="2"/>'
    body += t(64, 1270, FOOTER, 26, DIM) + t(64, 1310, SITE, 26, KOOKD, BODY, 700)
    return body + '</svg>'


def climb_path(progress, y=984, current_label='NOW'):
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
        elif current:
            last = index == len(checkpoints) - 1
            label_x = x - 52 if last else x
            label_anchor = 'end' if last else 'middle'
            body += (f'<g data-zone="climb-current-label" data-checkpoint="{amount}">'
                     + t(label_x, y - 50, current_label, 30, KOOKD, BODY, 800,
                         label_anchor, 1)
                     + '</g>')
        body += t(x, y + 76, f'${amount:,}', 30, CHALK if done or current else DIM, DISPLAY, 700, 'middle')
        if index == len(checkpoints) - 1:
            body += (f'<path data-zone="climb-goal-flag" d="M{x} {y - 31}V{y - 108}h52l-13 17 13 17h-52" '
                     f'fill="{KOOKD}" stroke="{CHALK}" stroke-width="3"/>')
    return body


def climb_card(pick, run, step, stake, payout, banked):
    """80/20 Climb rung. Port target: pick_card.ladder_svg. Facts only (no hype hook), per the 10-03 rule."""
    legs = pick.get('legs') or []
    body = t(64, 240, f'CLIMB #{run} · STEP {step}', 56, DIM, DISPLAY, 700, spacing=2)
    body += t(64, 400, f'${stake} → ${payout}', 150, CHALK, DISPLAY, 700)
    all_banked = int(pick.get('_allClimbsBanked') if pick.get('_allClimbsBanked') is not None else banked)
    body += t(64, 470, f'{odds(pick.get("odds"))} {pick.get("book") or ""}', 40, DIM, BODY, 600)
    body += t(64, 520, f'THIS CLIMB  ${banked} BANKED', 34, CHALK, DISPLAY, 700, spacing=.8)
    body += t(442, 520, f'·  ALL CLIMBS  ${all_banked} BANKED', 34, KOOKD, DISPLAY, 700, spacing=.8)
    y = 565
    for leg in legs[:3]:
        text = str(leg.get('title') or leg.get('displayTitle') or '')
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="94" rx="20" fill="{FELT_RAISED}"/>' + fit_t(100, y + 63, truncate(text, 52), 50, W - 240, CHALK, DISPLAY, 700, minimum=37)
        y += 108
    body += climb_path(max(50, int(banked or 0) + int(stake or 0)), 956, 'NOW')
    body += t(64, 1168, 'BANK 20%  ·  RIDE 80%  ·  EVERY STEP STAYS PUBLIC', 34, CHALK, DISPLAY, 700, spacing=1)
    return frame('80/20 Climb', body, chip_color=FELT_RAISED, chip_ink=CHALK)


def receipt_from_existing(receipt):
    """Adapt the append-only receipt presentation without changing any result or accounting."""
    rows = []
    for row in receipt.get('rows') or []:
        result, title = row[:2]
        detail = row[2] if len(row) > 2 else ''
        player = re.split(r'\s+(?:over|under)\s+', str(title), maxsplit=1, flags=re.I)[0]
        detail = re.sub(rf'^(Final:\s*){re.escape(player)}:\s*', r'\1', str(detail), flags=re.I)
        detail = re.sub(r'\b1 receptions\b', '1 reception', detail, flags=re.I)
        detail = re.sub(r'\b1 carries\b', '1 carry', detail, flags=re.I)
        detail = re.sub(r'\b1 targets\b', '1 target', detail, flags=re.I)
        kind = row[3] if len(row) > 3 else ('ladder' if 'climb' in str(title).lower() else
                                           'parlay' if any(word in str(title).lower() for word in ('parlay', 'lotto')) else 'best bet')
        title = re.sub(r'^Fun parlays?\b', 'Fun tickets', str(title), flags=re.I)
        title = re.sub(r'^Ladder\b', '80/20 Climb', title, flags=re.I)
        rows.append({'result': result, 'title': title, '_final': detail, '_kind': kind,
                     '_summaryRow': result is None})
    return receipt_card(receipt.get('when') or 'Results', rows, receipt.get('title'), receipt.get('season'))


def climb_result_card(pick):
    info = pick.get('ladder') or {}
    result = str(pick.get('result') or 'push').lower()
    stake, payout = info.get('stake', 0), info.get('payout', 0)
    start, goal = int(info.get('start') or 50), int(info.get('goal') or 1000)
    bank_this = int(info.get('bankThisWin') if info.get('bankThisWin') is not None else round(float(payout or 0) * .20))
    banked_after = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else int(info.get('banked') or 0) + bank_this)
    next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else int(payout or 0) - bank_this)
    total = int(info.get('totalAfter') if info.get('totalAfter') is not None else banked_after + next_stake)
    complete = result == 'win' and total >= goal
    tone, verdict, ink = ((KOOKD, 'CLIMB COMPLETE' if complete else '✓ HIT', KOOKD_INK) if result == 'win' else
                           (BURNT, '✗ MISS', TICKET_INK) if result == 'loss' else
                           (TICKET_RULE, '– VOID' if result == 'void' else '– PUSH', TICKET_INK))
    this_climb = info.get('bankedAfter', info.get('banked', 0)) if result == 'win' else info.get('banked', 0)
    all_banked = int(pick.get('_allClimbsBanked') if pick.get('_allClimbsBanked') is not None else this_climb or 0)
    body = t(64, 240, f"CLIMB #{info.get('run', 1)} · STEP {info.get('step', 1)}", 56, DIM, DISPLAY, 700, spacing=2)
    body += f'<rect x="64" y="300" width="{W - 128}" height="210" rx="28" fill="{tone}"/>'
    body += t(104, 390, verdict, 64, ink, DISPLAY, 700)
    result_line = (f'{dollars(start)} → {dollars(total)}' if complete else
                   f'{dollars(stake)} → {dollars(payout)}' if result == 'win' else
                   f'NEXT  {dollars(start)} RESTART' if result == 'loss' else f'{dollars(stake)} RETURNS')
    body += t(104, 472, result_line, 82, ink, DISPLAY, 700)
    if complete:
        body += fit_t(W - 100, 390, f'FINAL BANK {dollars(banked_after)}  ·  NEXT {dollars(start)} CLIMB',
                      36, 470, ink, DISPLAY, 700, 'end', minimum=26)
    elif result == 'win':
        body += fit_t(W - 100, 390, f'STEP {int(info.get("step") or 1) + 1} · {dollars(next_stake)} RIDES',
                      40, 410, ink, DISPLAY, 700, 'end', minimum=28)
    elif result in ('push', 'void'):
        body += fit_t(W - 100, 390, f'STEP {int(info.get("step") or 1)} AGAIN · {dollars(stake)} RIDES',
                      40, 420, ink, DISPLAY, 700, 'end', minimum=27)
    leg_results = []
    actual = str(pick.get('actual') or '')
    match = re.search(r'\blegs:\s*([^;]+)', actual, re.I)
    if match:
        leg_results = [value.strip().lower() for value in match.group(1).split(',')]
    elif result == 'win' and re.fullmatch(r'all\s+\d+\s+legs?\s+won', actual.strip(), re.I):
        leg_results = ['win'] * len(pick.get('legs') or [])
    y = 550
    for index, leg in enumerate((pick.get('legs') or [])[:3]):
        leg_result = leg_results[index] if index < len(leg_results) else ''
        leg_hit = leg_result in ('win', 'hit')
        leg_miss = leg_result in ('loss', 'miss')
        leg_color = KOOKD if leg_hit else BURNT_TEXT if leg_miss else DIM
        leg_mark = '✓' if leg_hit else '✗' if leg_miss else '–'
        body += f'<rect x="64" y="{y}" width="{W - 128}" height="92" rx="20" fill="{FELT_RAISED}"/>'
        body += f'<g data-zone="leg-mark" data-result="{leg_result or "unknown"}">' + t(100, y + 61, leg_mark, 48, leg_color, BODY, 800) + '</g>'
        body += fit_t(155, y + 61, truncate(leg.get('title'), 52), 48, W - 275, CHALK, DISPLAY, 700, minimum=35)
        y += 106
    if result == 'win':
        progress = total
    elif result == 'loss':
        progress = int(info.get('start') or 50)
    else:
        progress = int(info.get('banked') or 0) + int(stake or 0)
    path_label = ('NEXT' if result == 'loss' else 'DONE' if complete else
                  'AGAIN' if result in ('push', 'void') else 'NOW')
    body += climb_path(max(50, progress), 926, path_label)
    body += t(64, 1096, f'THIS CLIMB  ${int(this_climb or 0)} BANKED', 36, CHALK, DISPLAY, 700, spacing=1)
    body += t(64, 1148, f'ALL CLIMBS  ${all_banked} BANKED  ·  EVERY STEP STAYS PUBLIC', 34, KOOKD, DISPLAY, 700, spacing=.8)
    return frame('Climb result', body, chip_color=tone, chip_ink=ink)


def research_choice_card(choice, art=None):
    """The existing research category in the felt system; exact rows remain the source of truth."""
    art = art or {}
    rows = (choice.get('rows') or [])[:4]

    def proof_text(row, title):
        selection = re.search(r'\b(over|under)\s+([0-9.]+)', title, re.I)
        hits, games = row.get('hits'), row.get('games')
        if not (isinstance(hits, int) and isinstance(games, int)):
            found = re.search(r'\b(\d+)\s*/\s*(\d+)\b', str(row.get('metric') or ''))
            if found:
                hits, games = int(found.group(1)), int(found.group(2))
        if selection and isinstance(hits, int) and isinstance(games, int):
            return f'{selection.group(1).title()} {selection.group(2)} in {hits} of his last {games} games'
        return str(row.get('metric') or '')

    def defense_text(row, raw_detail):
        matchup = row.get('matchup') or {}
        if isinstance(matchup.get('rank'), int) and isinstance(matchup.get('of'), int):
            rank = int(matchup['rank'])
            suffix = 'th' if 10 <= rank % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(rank % 10, 'th')
            stat = str(row.get('statLabel') or matchup.get('stat') or 'this stat').replace('rush attempts', 'carries')
            allowed = matchup.get('value')
            if isinstance(allowed, (int, float)):
                return (f"{row.get('opponentAbbr') or 'Opponent'} allows {allowed:g} {stat} a game "
                        f"to {matchup.get('pos') or 'position'}s, {rank}{suffix} of {matchup['of']}")
            return (f"{row.get('opponentAbbr') or 'Opponent'}: {rank}{suffix} of {matchup['of']} "
                    f"vs {matchup.get('pos') or 'position'}s")
        if row.get('scriptRisk') and ' · ' in raw_detail:
            return raw_detail.rsplit(' · ', 1)[0]
        return raw_detail

    def caution_text(row, raw_detail):
        if row.get('scriptRisk'):
            caution = raw_detail.rsplit(' · ', 1)[-1] if raw_detail else ''
            return f'GAME-SCRIPT CAUTION · {caution}' if caution else 'GAME-SCRIPT CAUTION'
        return raw_detail if 'caution' in raw_detail.lower() else ''

    body = t(64, 225, str(choice.get('title') or 'RESEARCH').upper(), 58, CHALK, DISPLAY, 700)
    hero = next((uri for uri in art.values() if uri), None)
    if hero and len(rows) == 1:
        body += photo(900, 238, 82, hero)
    top = 300
    row_h = 360 if len(rows) == 1 else min(250, 760 / max(1, len(rows)))
    for index, row in enumerate(rows):
        if len(rows) == 1:
            title = str(row.get('title') or '')
            title_lines, title_size = wrap_fit(title, 76, 760 if hero else W - 192,
                                               max_lines=3, minimum=46)
            y = top
            body += '<g data-zone="research-title">'
            for line_index, line in enumerate(title_lines):
                body += t(64, y + line_index * (title_size + 6), line, f'{title_size:.1f}',
                          CHALK, DISPLAY, 700)
            body += '</g>'
            y += max(1, len(title_lines)) * (title_size + 6) + 18
            price = str(row.get('price') or '')
            if price:
                body += fit_t(64, y, price, 56, W - 128, CHALK, DISPLAY, 700, minimum=36)
                y += 82
            hits, games = row.get('hits'), row.get('games')
            proof = proof_text(row, title)
            raw_detail = str(row.get('detail') or '').strip()
            matchup = row.get('matchup') or {}
            defense = defense_text(row, raw_detail)
            extra_detail = caution_text(row, raw_detail)
            defense_lines, defense_size = wrap_fit(defense, 36, W - 192,
                                                   max_lines=2, minimum=24,
                                                   family_ratio=.54)
            extra_height = 38 if extra_detail else 0
            panel_h = 238 + max(0, len(defense_lines) - 1) * 40 + extra_height
            body += f'<rect x="64" y="{y - 48}" width="{W - 128}" height="{panel_h}" rx="24" fill="{FELT_RAISED}" stroke="{LINE}"/>'
            body += fit_t(96, y + 20, proof, 44, W - 192, CHALK, BODY, 750, minimum=28)
            body += '<g data-zone="research-defense">'
            for line_index, line in enumerate(defense_lines):
                body += t(96, y + 86 + line_index * 40, line, f'{defense_size:.1f}', DIM, BODY, 650)
            body += '</g>'
            context_y = y + 86 + max(1, len(defense_lines)) * 40
            if extra_detail:
                body += (f'<g data-zone="research-detail">'
                         + fit_t(96, context_y, extra_detail, 31, W - 192,
                                 BURNT_TEXT if 'caution' in extra_detail.lower() else DIM,
                                 BODY, 700, minimum=22)
                         + '</g>')
            timing = str(row.get('matchupLabel') or '').upper()
            try:
                local = datetime.fromisoformat(str(row.get('kickoff')).replace('Z', '+00:00')).astimezone(
                    ZoneInfo('America/Indiana/Indianapolis'))
                timing += ('  ·  ' if timing else '') + f'{local:%a %b %-d · %-I:%M %p ET}'
            except (TypeError, ValueError):
                pass
            if timing:
                timing_y = context_y + (48 if extra_detail else 28)
                body += fit_t(96, timing_y, timing, 31,
                              W - 192, KOOKD, BODY, 700, minimum=24)
            if isinstance(hits, int) and isinstance(games, int) and games > 0:
                bar_x, bar_y, bar_w = 64, y + panel_h - 6, W - 128
                body += f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="22" rx="11" fill="{LINE}"/>'
                body += f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w * hits / games:.1f}" height="22" rx="11" fill="{KOOKD}"/>'
                body += t(64, bar_y + 68, f'{hits} HIT  ·  {games - hits} MISSED', 30, DIM, BODY, 700, spacing=.7)
                season_hits = row.get('seasonHits')
                season_games = row.get('seasonGames')
                if isinstance(season_hits, int) and isinstance(season_games, int) and season_games > 0:
                    body += t(W - 64, bar_y + 68, f'{season_hits} of {season_games} this season',
                              30, CHALK, BODY, 750, 'end')
            values = [value for value in (row.get('historyValues') or [])[-10:] if isinstance(value, (int, float))]
            line_match = re.search(r'\b(?:over|under)\s+([0-9.]+)', title, re.I)
            if values and line_match:
                line_value = float(line_match.group(1))
                under = bool(re.search(r'\bunder\b', title, re.I))
                # Keep the game-by-game proof visually separate from the aggregate
                # hit strip above it; both are useful, but they must scan as two
                # distinct evidence blocks on a phone.
                chart_top, chart_base, left, width = max(940, bar_y + 150), 1120, 64, W - 128
                high = max(values + [line_value]) * 1.12 or 1
                bw = width / len(values)
                body += t(left, chart_top - 28, f'LAST {len(values)} GAMES', 28, DIM, BODY, 800, spacing=1.4)
                for game_index, value in enumerate(values):
                    height = max(5, (chart_base - chart_top) * value / high)
                    hit = value < line_value if under else value > line_value
                    body += (f'<rect x="{left + game_index * bw + 7:.1f}" y="{chart_base - height:.1f}" '
                             f'width="{max(10, bw - 14):.1f}" height="{height:.1f}" rx="7" fill="{KOOKD if hit else BURNT}"/>')
                    body += t(left + game_index * bw + bw / 2, chart_base + 35, f'{value:g}', 23, CHALK, DISPLAY, 700, 'middle')
                line_y = chart_base - (chart_base - chart_top) * line_value / high
                body += f'<line x1="{left}" y1="{line_y:.1f}" x2="{left + width}" y2="{line_y:.1f}" stroke="{CHALK}" stroke-width="3" stroke-dasharray="12 10"/>'
            continue
        y = top + index * (row_h + 18)
        body += f'<rect x="64" y="{y:.0f}" width="{W - 128}" height="{row_h:.0f}" rx="22" fill="{FELT_RAISED}" stroke="{LINE}"/>'
        body += f'<rect x="64" y="{y + 20:.0f}" width="6" height="{max(30, row_h - 40):.0f}" rx="3" fill="{KOOKD}"/>'
        title = str(row.get('title') or '')
        price = str(row.get('price') or '')
        metric = str(row.get('metric') or '')
        detail = str(row.get('detail') or '')
        if choice.get('kind') == 'season' and price:
            body += (f'<g data-zone="research-title">'
                     + fit_t(98, y + 46, title, 40, W - 196, CHALK,
                             DISPLAY, 700, minimum=30)
                     + '</g>')
            body += (f'<g data-zone="research-price">'
                     + fit_t(98, y + 90, price, 38, W - 196, KOOKD,
                             DISPLAY, 700, minimum=32)
                     + '</g>')
            body += (f'<g data-zone="research-metric">'
                     + fit_t(98, y + 130, metric, 29, W - 196, CHALK,
                             BODY, 700, minimum=22)
                     + '</g>')
            if row_h >= 160:
                body += (f'<g data-zone="research-detail">'
                         + fit_t(98, y + 163, detail, 24, W - 196, DIM,
                                 BODY, 600, minimum=19)
                         + '</g>')
            continue
        if choice.get('kind') == 'matchup' and len(rows) > 1:
            raw_detail = detail.strip()
            title_lines, title_size = wrap_fit(title, 44, W - 196,
                                               max_lines=2, minimum=32)
            title_y = y + 46
            body += '<g data-zone="research-title">'
            for line_index, line in enumerate(title_lines):
                body += t(98, title_y + line_index * (title_size + 4), line,
                          f'{title_size:.1f}', CHALK, DISPLAY, 700)
            body += '</g>'
            cursor = title_y + max(0, len(title_lines) - 1) * (title_size + 4)
            if price:
                body += (f'<g data-zone="research-price">'
                         + fit_t(98, cursor + 40, price, 36, W - 196, KOOKD,
                                 DISPLAY, 700, minimum=28)
                         + '</g>')
            proof = proof_text(row, title)
            body += (f'<g data-zone="research-metric">'
                     + fit_t(98, cursor + 76, proof, 28, W - 196, CHALK,
                             BODY, 700, minimum=22)
                     + '</g>')
            defense = defense_text(row, raw_detail)
            defense_lines, defense_size = wrap_fit(defense, 22, W - 196,
                                                   max_lines=2, minimum=18,
                                                   family_ratio=.54)
            body += '<g data-zone="research-defense">'
            for line_index, line in enumerate(defense_lines):
                body += t(98, cursor + 110 + line_index * (defense_size + 3), line,
                          f'{defense_size:.1f}', DIM, BODY, 600)
            body += '</g>'
            caution = caution_text(row, raw_detail)
            if caution:
                body += (f'<g data-zone="research-detail">'
                         + fit_t(98, y + row_h - 16, caution, 22, W - 196,
                                 BURNT_TEXT, BODY, 750, minimum=18)
                         + '</g>')
            continue
        title_size = 54 if len(rows) == 1 else 42
        title_width = W - 98 - 96 if not price else 600
        body += (f'<g data-zone="research-title">'
                 + fit_t(98, y + 62, title, title_size, title_width, CHALK, DISPLAY, 700, minimum=22)
                 + '</g>')
        if price:
            body += (f'<g data-zone="research-price">'
                     + fit_t(W - 96, y + 62, price, 48 if len(rows) == 1 else 40, 250,
                             KOOKD, DISPLAY, 700, 'end', minimum=20)
                     + '</g>')
        body += (f'<g data-zone="research-metric">'
                 + fit_t(98, y + (160 if len(rows) == 1 else 108), metric,
                         42 if len(rows) == 1 else 32, W - 196, CHALK, BODY, 700, minimum=20)
                 + '</g>')
        if row_h >= 160:
            body += (f'<g data-zone="research-detail">'
                     + fit_t(98, y + (226 if len(rows) == 1 else 151), detail,
                             34 if len(rows) == 1 else 26, W - 196, DIM, BODY, 600, minimum=18)
                     + '</g>')
        if len(rows) == 1:
            proof_number = metric.split(' ', 1)[0]
            body += t(98, y + 326, proof_number, 96, KOOKD, DISPLAY, 700)
            body += t(295, y + 318, 'EXACT-LINE PROOF', 32, DIM, DISPLAY, 700, spacing=1)
    label = {'upset': 'Underdog research', 'spread-dog': 'Spread research',
             'matchup': 'Matchup research', 'season': 'Trend research',
             'end-zone': 'Scorer research'}.get(choice.get('kind'), 'Slate research')
    return frame(label, body, chip_color=FELT_RAISED, chip_ink=CHALK)
