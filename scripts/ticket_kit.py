"""Kook'n v2 'Kitchen Ticket' card kit. Python standard library only.

Every card is a chalk-paper kitchen order ticket hanging from a steel rail on casino felt. This module holds the
tokens, the font metrics, text fitting, the image bank and every shared drawing primitive. cards.py composes them.
The spec for porting this into scripts/pick_card.py and scripts/felt_cards.py is SPEC.md next to this file.
"""
import base64
import colorsys
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / 'site'

# ------------------------------------------------------------------ tokens (casino felt, owner approved 2026-10-06)
NIGHT, FELT, RAISED, LINE = '#07120D', '#0E2219', '#15301F', '#21412F'
CHALK, DIM, GREEN, RED, RED_TEXT, GREEN_INK = '#F2F7F4', '#A9C0B3', '#20C774', '#F2414E', '#FF6B75', '#062B1C'
INK, INK_SOFT = '#07120D', '#3E5448'          # print ink on chalk paper (INK_SOFT is 7.9:1 on chalk)
PAPER_TOP_TONE, PAPER_LOW_TONE = '#F4F8F5', '#E7EEEA'
RULE = '#C9D8D0'                               # hairlines printed on paper
MUTED = '#8FA197'                              # muted route line on paper (non-text)
CHARCOAL = ('#2A2F33', '#0B0D0F')              # neutral panel: win cards, unknown teams
HOUSE = ('#173A2A', '#0A1B13')                 # felt house panel: Climb, Final, Prep List

W, H = 1080, 1350
MINUS = '−'                               # true minus for prices; the [–—] guard never sees it
DOT = '·'

# ------------------------------------------------------------------ grid
PAPER_X1, PAPER_X2 = 84, 996                   # 84 px of felt shows on each side
PANEL_X1, PANEL_X2 = 104, 976                  # printed panel, 20 px inside the paper
X1, X2 = 112, 968                              # printed text margins on paper (28 px inside)
COL_X = 128                                    # text column inside the panel
COL_MAX = 600                                  # right edge of the panel text column when a photo is present
RAIL_Y = 122                                   # rail 122..160
PAPER_TOP = 136
PANEL_TOP = 160
FOOT_1, FOOT_2 = 1262, 1300                    # footer baselines (for H = 1350; both move with H)
TILT = -0.4                                    # degrees; printed paper and breakout photo, around (540, 140)
PAPER_GRAIN = False                            # paper turbulence adds ~0.4 MB per PNG for no visible gain at 50%
PIVOT = (540, 140)
CAP = 0.70                                     # cap height / em for Barlow Condensed Bold and DM Sans

# ------------------------------------------------------------------ font metrics (measured in Chrome: widths.json)
_W = json.loads((HERE / 'fonts' / 'widths.json').read_text(encoding='utf-8'))
BARLOW = _W['Barlow Condensed|700']


def _table(family, weight):
    if family == 'b':
        return BARLOW
    weight = min((400, 500, 600, 700, 800), key=lambda w: abs(w - (weight or 500)))
    return _W[f'DM Sans|{weight}']


def width(text, size, family='b', weight=700, tracking=0.0):
    """Advance width in px. Per-character advances measured at 1000 px; no kerning (within 1%)."""
    table = _table(family, weight)
    total = sum(table.get(ch, 550) for ch in str(text))
    return total * size / 1000 + tracking * max(len(str(text)) - 1, 0)


def fit(text, size, max_w, family='b', weight=700, tracking=0.0, floor=40, step=2):
    """Largest size <= size (in `step` px steps) whose width fits max_w; never below floor."""
    while size > floor and width(text, size, family, weight, tracking) > max_w:
        size -= step
    return max(size, floor)


def wrap(text, size, max_w, family='b', weight=700, tracking=0.0, max_lines=2):
    """Greedy word wrap at one size. Returns lines, or None when it needs more than max_lines."""
    words, lines, line = str(text).split(), [], ''
    for word in words:
        trial = f'{line} {word}'.strip()
        if width(trial, size, family, weight, tracking) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines if len(lines) <= max_lines and all(width(l, size, family, weight, tracking) <= max_w for l in lines) else None


# ------------------------------------------------------------------ colour helpers
def rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(r, g, b):
    return '#{:02X}{:02X}{:02X}'.format(*(max(0, min(255, int(round(c)))) for c in (r, g, b)))


def shade(color, factor):
    """Scale toward black (factor < 1) or white (factor > 1)."""
    r, g, b = rgb(color)
    if factor <= 1:
        return hexc(r * factor, g * factor, b * factor)
    return hexc(r + (255 - r) * (factor - 1), g + (255 - g) * (factor - 1), b + (255 - b) * (factor - 1))


def luminance(color):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(color)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def banned_hue(color):
    """Orange, amber, gold, tan, bronze, copper, brown: never a house or panel fill."""
    r, g, b = (c / 255 for c in rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return 8 / 360 <= h <= 58 / 360 and s >= 0.22 and 0.08 <= l <= 0.9


def reddish(color):
    r, g, b = (c / 255 for c in rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (h < 15 / 360 or h > 335 / 360) and s >= 0.35


def greenish(color):
    r, g, b = (c / 255 for c in rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return 85 / 360 <= h <= 175 / 360 and s >= 0.3


def team_panel(primary, alternate=None):
    """(top, bottom, glow) for a team panel. Gold/orange/brown primaries fall back to the alternate (navy or
    black); red primaries are darkened so they never read as chip red; chalk text keeps >= 4.5:1."""
    color = primary or CHARCOAL[0]
    if banned_hue(color):
        color = alternate if alternate and not banned_hue(alternate) else CHARCOAL[0]
    if luminance(color) > 0.6:                   # white or silver primaries: use the alternate, else charcoal
        color = alternate if alternate and luminance(alternate) < 0.4 and not banned_hue(alternate) else CHARCOAL[0]
    if luminance(color) < 0.012:                 # black primaries: a lifted near-black so the stripes still read
        return '#1C1F23', '#060708', CHALK
    glow = color
    top = shade(color, 0.78) if reddish(color) and luminance(color) > 0.07 else color
    while contrast(CHALK, top) < 4.5:
        top = shade(top, 0.92)
    while greenish(top) and luminance(top) > 0.06:   # a team green must never pass for Kook'n green
        top = shade(top, 0.9)
    bottom = shade(top, 0.34)
    if luminance(glow) < luminance(FELT) * 1.6:   # darker than the felt: the rim light and glow go chalk
        glow = CHALK
    return top, bottom, glow


# ------------------------------------------------------------------ SVG primitives
class Card:
    """Collects defs (images once, gradients, filters) and body markup; records every text node for QA."""

    def __init__(self, height=H):
        self.h = height
        self.defs = []
        self.body = []
        self.texts = []
        self._images = {}
        self._ids = 0

    def uid(self, stem):
        self._ids += 1
        return f'{stem}{self._ids}'

    def add(self, *parts):
        self.body.extend(p for p in parts if p)

    def image(self, name):
        """Each raster is embedded once as a <symbol>; placements reuse it with <use>."""
        if name not in self._images:
            sid = f'img{len(self._images) + 1}'
            if str(name).startswith('data:image/png;base64,'):
                raw = base64.b64decode(str(name).split(',', 1)[1])
                kind = 'image/png'
            else:
                path = Path(name) if Path(name).is_absolute() else ASSETS / name
                raw = path.read_bytes()
                kind = 'image/svg+xml' if path.suffix == '.svg' else 'image/png'
            w, h = png_size(raw) if kind == 'image/png' else (120, 120)
            uri = f'data:{kind};base64,' + base64.b64encode(raw).decode('ascii')
            self.defs.append(f'<symbol id="{sid}" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet">'
                             f'<image href="{uri}" width="{w}" height="{h}"/></symbol>')
            self._images[name] = (sid, w, h)
        return self._images[name]

    def use(self, name, x, y, w, h, extra=''):
        sid, _, _ = self.image(name)
        return f'<use href="#{sid}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"{extra}/>'

    def text(self, x, y, s, size, fill=INK, family='b', weight=None, anchor='start', tracking=0.0, extra='', role='read'):
        weight = weight or (700 if family == 'b' else 600)
        fam = "'Barlow Condensed'" if family == 'b' else "'DM Sans'"
        w = width(s, size, family, weight, tracking)
        x0 = x - (w if anchor == 'end' else w / 2 if anchor == 'middle' else 0)
        self.texts.append(dict(text=str(s), size=size, x0=x0, x1=x0 + w, y=y, role=role))
        ls = f' letter-spacing="{tracking}"' if tracking else ''
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-weight="{weight}" font-size="{size}" '
                f'fill="{fill}" text-anchor="{anchor}"{ls} data-role="{role}"{extra}>{escape(str(s))}</text>')

    def svg(self):
        from felt_cards import font_face
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" viewBox="0 0 {W} {self.h}">'
                f'<defs>{font_face()}{"".join(self.defs)}</defs>{"".join(self.body)}</svg>')


def png_size(raw):
    return int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')


def money(value):
    return f'${value:,.2f}' if abs(value - round(value)) > 0.004 else f'${int(round(value)):,}'


def price(odds):
    n = int(odds)
    return f'+{n}' if n > 0 else f'{MINUS}{abs(n)}'


def decimal(odds):
    n = int(odds)
    return 1 + (n / 100 if n > 0 else 100 / abs(n))


def american(dec):
    return round((dec - 1) * 100) if dec >= 2 else -round(100 / (dec - 1))


def pct1(x):
    return f'{100 * x:.1f}%'


# ------------------------------------------------------------------ shared defs
def base_defs(card, panel=None, glow=CHALK, sweep=None):
    """Gradients and filters every card uses. panel = (top, bottom); glow = rim/halo colour; sweep = felt light."""
    top, bottom = panel or HOUSE
    sweep = sweep or glow
    rim_alpha = 0.5 if glow == CHALK else 0.8
    card.defs.append(f'''
<radialGradient id="feltLight" cx="50%" cy="30%" r="80%"><stop offset="0" stop-color="{RAISED}"/><stop offset="0.5" stop-color="{FELT}"/><stop offset="1" stop-color="{NIGHT}"/></radialGradient>
<linearGradient id="sweepGrad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{sweep}" stop-opacity="0"/><stop offset="0.45" stop-color="{sweep}" stop-opacity="1"/><stop offset="1" stop-color="{sweep}" stop-opacity="0"/></linearGradient>
<radialGradient id="bokeh" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{CHALK}" stop-opacity="1"/><stop offset="1" stop-color="{CHALK}" stop-opacity="0"/></radialGradient>
<linearGradient id="panel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>
<linearGradient id="scrim" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{bottom}" stop-opacity="0.80"/><stop offset="0.45" stop-color="{bottom}" stop-opacity="0.62"/><stop offset="0.66" stop-color="{bottom}" stop-opacity="0"/></linearGradient>
<radialGradient id="panelHot" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.22"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>
<radialGradient id="halo" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{glow}" stop-opacity="0.55"/><stop offset="0.6" stop-color="{glow}" stop-opacity="0.16"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>
<linearGradient id="rail" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E8EEEA"/><stop offset="0.28" stop-color="#B9C4BE"/><stop offset="0.62" stop-color="#78857E"/><stop offset="1" stop-color="#3B4641"/></linearGradient>
<linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PAPER_TOP_TONE}"/><stop offset="1" stop-color="{PAPER_LOW_TONE}"/></linearGradient>
<linearGradient id="railShade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0.30"/><stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>
<pattern id="speed" width="34" height="34" patternUnits="userSpaceOnUse" patternTransform="rotate(-24)"><rect width="9" height="34" fill="#FFFFFF" fill-opacity="0.06"/></pattern>
<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="7"/><feColorMatrix type="matrix" values="0 0 0 0 0.75  0 0 0 0 0.9  0 0 0 0 0.8  0 0 0 0.06 0"/></filter>
<filter id="paperGrain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.6" numOctaves="2" seed="11"/><feColorMatrix type="matrix" values="0 0 0 0 0.03  0 0 0 0 0.10  0 0 0 0 0.06  0.05 0 0 0 -0.01"/></filter>
<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="16"/></filter>
<filter id="blur18" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="18"/></filter>
<filter id="blur40" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>
<filter id="rim" x="-15%" y="-15%" width="130%" height="130%"><feMorphology in="SourceAlpha" operator="dilate" radius="4" result="fat"/><feFlood flood-color="{glow}" flood-opacity="{rim_alpha}"/><feComposite in2="fat" operator="in"/><feGaussianBlur stdDeviation="6" result="glow"/><feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="drop" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000" flood-opacity="0.5"/></filter>
<filter id="stampInk" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.4" result="d"/><feTurbulence type="fractalNoise" baseFrequency="1.3" numOctaves="2" seed="9" result="m"/><feColorMatrix in="m" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -14 10.5" result="mask"/><feComposite in="d" in2="mask" operator="in"/></filter>
''')


# ------------------------------------------------------------------ felt, brand, rail, paper, footer
def felt(card, sweep=True, bokeh=True):
    h = card.h
    parts = [f'<rect width="{W}" height="{h}" fill="{NIGHT}"/>', f'<rect width="{W}" height="{h}" fill="url(#feltLight)"/>']
    if sweep:
        # one team light sweep at -14 degrees, 30% opacity, over a near-black under-band so team colour over green
        # felt never mixes toward brown
        parts.append('<g transform="rotate(-14 760 210)" filter="url(#blur40)">'
                     f'<rect x="200" y="60" width="1300" height="300" fill="#030806" opacity="0.6"/></g>')
        parts.append('<g transform="rotate(-14 760 210)" filter="url(#blur18)">'
                     '<rect x="260" y="120" width="1200" height="170" fill="url(#sweepGrad)" opacity="0.30"/></g>')
    if bokeh:
        for cx, cy in ((520, 34), (884, 14)):
            dots = ''.join(f'<circle cx="{cx - 60 + c * 24}" cy="{cy - 8 + r * 20}" r="6.5" fill="{CHALK}"/>'
                           for r in range(2) for c in range(6))
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="150" fill="url(#bokeh)" opacity="0.16" filter="url(#blur18)"/>'
                         f'<g filter="url(#blur18)" opacity="0.25">{dots}</g>')
    # grain only where felt shows: the top band, the side margins and the band under the paper
    for x, y, w, hh in ((0, 0, W, PANEL_TOP), (0, PANEL_TOP, PAPER_X1, h - PANEL_TOP), (PAPER_X2, PANEL_TOP, W - PAPER_X2, h - PANEL_TOP),
                        (PAPER_X1, h - 150, PAPER_X2 - PAPER_X1, 150)):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" filter="url(#grain)"/>')
    card.add(*parts)


MARK = ('<rect x="10" y="38" width="100" height="62" rx="9" fill="#F2F7F4"/>'
        '<path d="M82 38 L101 38 Q110 38 110 47 L110 91 Q110 100 101 100 L82 100 Z" fill="#20C774"/>'
        '<circle cx="10" cy="69" r="8" fill="#07120D"/><circle cx="110" cy="69" r="8" fill="#07120D"/>'
        '<path d="M82 44 L82 94" stroke="#07120D" stroke-width="3" stroke-dasharray="4 4"/>'
        '<rect x="28" y="51" width="12" height="36" rx="2" fill="#07120D"/>'
        '<path d="M45 69 L61 52" stroke="#07120D" stroke-width="11"/><path d="M45 69 L63 87" stroke="#07120D" stroke-width="11"/>'
        '<path d="M88 70 L93 76 L101 63" stroke="#F2F7F4" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        '<g transform="rotate(-14 34 30) translate(16.8 14.7) scale(0.32)" fill="#F2F7F4" stroke="#07120D" stroke-width="6">'
        '<circle cx="38" cy="44" r="17"/><circle cx="60" cy="33" r="22"/><circle cx="82" cy="44" r="17"/>'
        '<rect x="31" y="44" width="58" height="18" stroke="none"/><rect x="31" y="66" width="58" height="13" rx="3"/></g>')
WORD = ('M0,0 L18,0 L18,40 L44,0 L66,0 L36,46 L68,100 L46,100 L18,56 L18,100 L0,100 Z M102,0 H106 A26,26 0 0 1 132,26 '
        'V74 A26,26 0 0 1 106,100 H102 A26,26 0 0 1 76,74 V26 A26,26 0 0 1 102,0 Z M104,18 H104 A10,10 0 0 1 114,28 V72 '
        'A10,10 0 0 1 104,82 H104 A10,10 0 0 1 94,72 V28 A10,10 0 0 1 104,18 Z M166,0 H170 A26,26 0 0 1 196,26 V74 '
        'A26,26 0 0 1 170,100 H166 A26,26 0 0 1 140,74 V26 A26,26 0 0 1 166,0 Z M168,18 H168 A10,10 0 0 1 178,28 V72 '
        'A10,10 0 0 1 168,82 H168 A10,10 0 0 1 158,72 V28 A10,10 0 0 1 168,18 Z M204,0 L222,0 L222,40 L248,0 L270,0 '
        'L240,46 L272,100 L250,100 L222,56 L222,100 L204,100 Z M298,0 L316,0 L342,62 L342,0 L360,0 L360,100 L342,100 '
        'L316,38 L316,100 L298,100 Z')
FLAME = 'M8 0 C14 9 17 15 13.5 23 C11 29 3.5 29 1.5 23 C0 18 4 13 8 0 Z'          # wordmark apostrophe flame
CHIP_FLAME = ('M0 -26 C10 -14 16 -6 14 6 C12 18 4 24 -2 24 C-12 24 -17 15 -16 6 C-15 -2 -10 -6 -8 -12 '
              'C-5 -6 -4 -2 -1 0 C2 -8 2 -16 0 -26 Z')                         # 50 units tall, centred on (0, 0)
CHECK = 'M0 26 L18 44 L52 6'
CROSS = 'M4 4 L44 44 M44 4 L4 44'


def brand(card, x=218, y=34):
    """Ticket mark plus the KOOK'N wordmark, to the right of the chef clip."""
    card.add(f'<g transform="translate({x} {y}) scale(0.62)">{MARK}</g>'
             f'<g transform="translate({x + 88} {y + 26}) scale(0.46)"><path fill="{CHALK}" fill-rule="evenodd" d="{WORD}"/>'
             f'<path transform="translate(278 0)" fill="{GREEN}" d="{FLAME}"/></g>')


def chef_clip(card, cx=128, cy=136, r=54, angle=-8):
    """The clay chef as a die-cut sticker magnet pinning the ticket to the rail (owner-gated: CHEF_CLIP)."""
    _, w, h = card.image('kookn-chef.png')
    cid = card.uid('chefClip')
    card.defs.append(f'<clipPath id="{cid}"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>')
    card.add(f'<g transform="rotate({angle} {cx} {cy})" filter="url(#drop)">'
             f'<circle cx="{cx}" cy="{cy}" r="{r + 6}" fill="{CHALK}"/>'
             f'<g clip-path="url(#{cid})">{card.use("kookn-chef.png", cx - r * 1.06, cy - r * 1.0, r * 2.12, r * 2.12)}</g>'
             f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{LINE}" stroke-width="2"/></g>')


def rail(card):
    y = RAIL_Y
    card.add(f'<rect x="18" y="{y + 30}" width="{W - 36}" height="22" fill="url(#railShade)"/>'
             f'<rect x="18" y="{y}" width="{W - 36}" height="38" rx="9" fill="url(#rail)"/>'
             f'<rect x="18" y="{y + 30}" width="{W - 36}" height="3" fill="#2A332F" opacity="0.7"/>'
             f'<rect x="30" y="{y + 4}" width="{W - 60}" height="3" rx="1.5" fill="#FFFFFF" opacity="0.55"/>'
             + ''.join(f'<circle cx="{cx}" cy="{y + 19}" r="6" fill="#5C6862"/><circle cx="{cx}" cy="{y + 17.5}" r="3.5" fill="#D4DDD8"/>'
                       for cx in (44, W - 44)))


def ticket_path(x1, x2, top, perf, bottom, tooth=24, depth=13, notch=20):
    """Chalk ticket outline with side notches at the perforation (the Kook'n mark) and a torn zigzag bottom."""
    d = [f'M{x1},{top} H{x2} V{perf - notch} A{notch},{notch} 0 0 0 {x2},{perf + notch} V{bottom}']
    n = int(round((x2 - x1) / tooth))
    step = (x2 - x1) / n
    for i in range(n):
        d.append(f'L{x2 - step * (i + 0.5):.1f},{bottom + depth} L{x2 - step * (i + 1):.1f},{bottom}')
    d.append(f'V{perf + notch} A{notch},{notch} 0 0 0 {x1},{perf - notch} Z')
    return ' '.join(d)


def paper(card, perf, bottom):
    path = ticket_path(PAPER_X1, PAPER_X2, PAPER_TOP, perf, bottom)
    cid = card.uid('paperClip')
    card.defs.append(f'<clipPath id="{cid}"><path d="{path}"/></clipPath>')
    return (f'<g transform="translate(10 20)"><path d="{path}" fill="#000" opacity="0.55" filter="url(#soft)"/></g>'
            f'<path d="{path}" fill="url(#paper)"/>'
            f'<g clip-path="url(#{cid})">' + (f'<rect x="{PAPER_X1}" y="{PAPER_TOP}" width="{PAPER_X2 - PAPER_X1}" height="{bottom - PAPER_TOP + 20}" filter="url(#paperGrain)"/>' if PAPER_GRAIN else '')
            + f'<rect x="{PAPER_X1}" y="{PAPER_TOP}" width="{PAPER_X2 - PAPER_X1}" height="54" fill="url(#railShade)"/></g>'
            f'<line x1="{PAPER_X1 + 30}" y1="{perf}" x2="{PAPER_X2 - 30}" y2="{perf}" stroke="{INK_SOFT}" stroke-width="3" stroke-dasharray="3 11" stroke-linecap="round"/>')


def footer(card):
    y1, y2 = card.h - (H - FOOT_1), card.h - (H - FOOT_2)
    card.add(card.text(56, y1, '21+ · Entertainment only', 24, DIM, 'd', 500, role='footer'),
             card.text(56, y2, 'keenroudy.com/sports', 24, GREEN, 'd', 700, role='footer'),
             card.text(W - 56, y2, '@keenkooks', 24, DIM, 'd', 600, 'end', role='footer'))


def tilt(markup):
    return f'<g transform="rotate({TILT} {PIVOT[0]} {PIVOT[1]})">{markup}</g>' if TILT else markup


# ------------------------------------------------------------------ panel, photo, logos
def panel_rect(card, top, bottom, hot=(790, 330), stripes=True):
    s = f'<rect x="{PANEL_X1}" y="{top}" width="{PANEL_X2 - PANEL_X1}" height="{bottom - top}" rx="14" fill="url(#panel)"/>'
    if stripes:
        s += f'<rect x="{PANEL_X1}" y="{top}" width="{PANEL_X2 - PANEL_X1}" height="{bottom - top}" rx="14" fill="url(#speed)"/>'
    if hot:
        s += f'<circle cx="{hot[0]}" cy="{hot[1]}" r="330" fill="url(#panelHot)"/>'
    return s


def split_panel(card, top, bottom, left, right, seam_x=540, skew=46):
    """Two team panels split by a slanted seam (game lines and the no-photo template)."""
    lg, rg = card.uid('lp'), card.uid('rp')
    card.defs.append(f'<linearGradient id="{lg}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{left[0]}"/><stop offset="1" stop-color="{left[1]}"/></linearGradient>'
                     f'<linearGradient id="{rg}" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{right[0]}"/><stop offset="1" stop-color="{right[1]}"/></linearGradient>')
    cid = card.uid('panelClip')
    card.defs.append(f'<clipPath id="{cid}"><rect x="{PANEL_X1}" y="{top}" width="{PANEL_X2 - PANEL_X1}" height="{bottom - top}" rx="14"/></clipPath>')
    a, b = seam_x + skew, seam_x - skew
    return (f'<g clip-path="url(#{cid})">'
            f'<polygon points="{PANEL_X1},{top} {a},{top} {b},{bottom} {PANEL_X1},{bottom}" fill="url(#{lg})"/>'
            f'<polygon points="{a},{top} {PANEL_X2},{top} {PANEL_X2},{bottom} {b},{bottom}" fill="url(#{rg})"/>'
            f'<rect x="{PANEL_X1}" y="{top}" width="{PANEL_X2 - PANEL_X1}" height="{bottom - top}" fill="url(#speed)"/>'
            f'<line x1="{a}" y1="{top}" x2="{b}" y2="{bottom}" stroke="{CHALK}" stroke-opacity="0.85" stroke-width="5"/></g>')


FACE = {}   # name -> (face_cx, head_top) in source pixels, from the cutout's alpha profile


def face_of(name):
    """Face centre x and head top y of an ESPN 600x436 cutout. Falls back to ESPN's standard framing (300, 40)."""
    if name not in FACE:
        try:
            import ticket_pngalpha
            if str(name).startswith('data:image/png;base64,'):
                from tempfile import NamedTemporaryFile
                with NamedTemporaryFile(suffix='.png') as image_file:
                    image_file.write(base64.b64decode(str(name).split(',', 1)[1]))
                    image_file.flush()
                    w, h, prof, bbox = ticket_pngalpha.profile(Path(image_file.name))
            else:
                path = Path(name) if Path(name).is_absolute() else ASSETS / name
                w, h, prof, bbox = ticket_pngalpha.profile(path)
            top = bbox[1]
            rows = [prof[y] for y in range(top + 60, min(top + 140, h)) if prof[y]]
            cx = sum((a + b) / 2 for a, b in rows) / len(rows) if rows else w / 2
            FACE[name] = (cx, top)
        except Exception:
            FACE[name] = (300, 40)
    return FACE[name]


def hero_photo(card, name, panel_top, panel_bottom, face_x=780, height=580):
    """Returns (in_panel, breakout) markup. The cutout's bottom sits on the panel bottom; its shoulders are clipped
    to the panel and its head rises past the rail. The image is embedded once and used twice."""
    _, sw, sh = card.image(name)
    scale = height / sh
    fx, _ = face_of(name)
    x, y, w = face_x - fx * scale, panel_bottom - height, sw * scale
    inside, outside = card.uid('phIn'), card.uid('phOut')
    card.defs.append(f'<clipPath id="{inside}"><rect x="{PANEL_X1}" y="{panel_top}" width="{PANEL_X2 - PANEL_X1}" height="{panel_bottom - panel_top}" rx="14"/></clipPath>'
                     f'<clipPath id="{outside}"><rect x="{PANEL_X1}" y="-400" width="{PANEL_X2 - PANEL_X1}" height="{panel_top + 400 + 16}"/></clipPath>')
    pic = card.use(name, x, y, w, height)
    return (f'<g clip-path="url(#{inside})"><g filter="url(#rim)">{pic}</g></g>',
            f'<g clip-path="url(#{outside})"><g filter="url(#rim)">{pic}</g></g>')


def logo_disc(card, name, cx, cy, r=40, ring=None):
    s = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{CHALK}"/>'
    if ring:
        s = f'<circle cx="{cx}" cy="{cy}" r="{r + 6}" fill="{ring}"/>' + s
    return s + card.use(name, cx - r * 0.78, cy - r * 0.78, r * 1.56, r * 1.56)


def initials_badge(card, cx, cy, r, initials, color):
    """Missing photo: a team-colour disc with the player's initials (Barlow, chalk or ink by contrast)."""
    top, bottom, _ = team_panel(color)
    gid = card.uid('badge')
    card.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>')
    label = str(initials)
    while len(label) > 1 and width(label, 40) > r * 1.7:      # 40 px floor: drop letters before shrinking
        label = label[:-1]
    size = max(40, fit(label, int(r * 1.05), r * 1.6, floor=40))
    return (f'<circle cx="{cx}" cy="{cy}" r="{r + 3}" fill="{LINE}"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{gid})"/>'
            + card.text(cx, cy + size * CAP / 2, label, size, CHALK, 'b', anchor='middle', role='badge'))


def face_thumb(card, name, cx, cy, r=30, ring=LINE):
    """A circle crop of the cutout's face."""
    _, sw, sh = card.image(name)
    fx, top = face_of(name)
    crop = 190                                  # source px across the face
    scale = 2 * r / crop
    cid = card.uid('thumb')
    card.defs.append(f'<clipPath id="{cid}"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>')
    x = cx - fx * scale
    y = cy - (top + 92) * scale
    return (f'<circle cx="{cx}" cy="{cy}" r="{r + 3}" fill="{ring}"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="#DCE6E0"/>'
            f'<g clip-path="url(#{cid})">{card.use(name, x, y, sw * scale, sh * scale)}</g>')


# ------------------------------------------------------------------ chips, stamps, rows
def series_chip(card, x, y, label, flame=False, size=40, h=56):
    pad, fw = 22, (32 if flame else 0)
    w = width(label, size, tracking=1.5) + pad * 2 + fw
    s = f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{h}" rx="8" fill="{NIGHT}"/>'
    if flame:   # chalk flame, 40 px tall, 12 px left of the words
        s += f'<path transform="translate({x + pad + 10} {y + h / 2 + 1}) scale(0.8)" fill="{CHALK}" d="{CHIP_FLAME}"/>'
    s += card.text(x + pad + fw, y + h / 2 + size * CAP / 2, label, size, CHALK, tracking=1.5)
    return s, w


def poker_chip(card, cx, cy, r, label, size=None):
    """A casino chip for stakes: chalk face, felt edge inserts, dashed dim inner ring, ink amount."""
    circ = 2 * 3.14159 * r * 0.9
    seg = circ / 16
    size = size or fit(label, int(r * 0.9), r * 1.36)
    return (f'<g filter="url(#drop)"><circle cx="{cx}" cy="{cy}" r="{r}" fill="{CHALK}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.9:.1f}" fill="none" stroke="{FELT}" stroke-width="{r * 0.17:.1f}" stroke-dasharray="{seg:.1f} {seg:.1f}" transform="rotate(-6 {cx} {cy})"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.79:.1f}" fill="{CHALK}" stroke="{FELT}" stroke-width="3"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.71:.1f}" fill="none" stroke="{DIM}" stroke-width="2.5" stroke-dasharray="6 6"/></g>'
            + card.text(cx, cy + size * CAP / 2, label, size, INK, anchor='middle'))


def dashed(x1, x2, y):
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{INK_SOFT}" stroke-width="3" stroke-dasharray="12 9"/>'


def dots(x1, x2, y):
    if x2 - x1 < 30:
        return ''
    return (f'<line x1="{x1:.0f}" y1="{y}" x2="{x2:.0f}" y2="{y}" stroke="{INK_SOFT}" stroke-width="4" '
            f'stroke-dasharray="1 12" stroke-linecap="round"/>')


def checkbox(x, y, size=38, state=None):
    """Open: an empty gray box. Hit: green box, dark-ink check. Miss: red box, ink cross."""
    if state == 'hit':
        return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="6" fill="{GREEN}"/>'
                f'<path transform="translate({x + 7} {y + 8}) scale(0.46)" d="{CHECK}" fill="none" stroke="{GREEN_INK}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>')
    if state == 'miss':
        return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="6" fill="{RED}"/>'
                f'<path transform="translate({x + 9} {y + 9}) scale(0.42)" d="{CROSS}" fill="none" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>')
    return f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="6" fill="none" stroke="{INK_SOFT}" stroke-width="4"/>'


def result_stamp(card, x2, cy, result, w=176, h=64, size=40):
    """Row-end result stamp: identical size for HIT and MISS, symbol plus word, never colour alone."""
    hit = result == 'hit'
    x = x2 - w
    if result in ('push', 'void'):            # gray, a drawn bar (never a dash character), the word
        fill, ink, word = RULE, INK, result.upper()
        sym = f'<path d="M{x + 24} {cy} H{x + 52}" stroke="{ink}" stroke-width="8" stroke-linecap="round"/>'
    else:
        fill, ink, mark, word = (GREEN, GREEN_INK, CHECK, 'HIT') if hit else (RED, INK, CROSS, 'MISS')
        sym = (f'<path transform="translate({x + 22} {cy - 14}) scale({0.56 if hit else 0.6})" d="{mark}" fill="none" stroke="{ink}" '
               f'stroke-width="{11 if hit else 10}" stroke-linecap="round" stroke-linejoin="round"/>')
    tw = width(word, size, tracking=2)
    return (f'<rect x="{x}" y="{cy - h / 2}" width="{w}" height="{h}" rx="8" fill="{fill}"/>'
            f'<rect x="{x + 6}" y="{cy - h / 2 + 6}" width="{w - 12}" height="{h - 12}" rx="5" fill="none" stroke="{ink}" stroke-width="2.5" opacity="0.55"/>'
            + sym + card.text(x + 74 + (w - 74 - 16 - tw) / 2, cy + size * CAP / 2, word, size, ink, tracking=2))


def big_stamp(card, cx, cy, label, fill, ink, mark, angle=-6, size=112):
    tw = width(label, size, tracking=3)
    sym_w, gap, pad = 56, 22, 40
    w, h = pad + sym_w + gap + tw + pad, size * 1.34
    x, y = cx - w / 2, cy - h / 2
    sym = (f'<path transform="translate({x + pad:.0f} {cy - 25:.0f}) scale(1.06)" d="{mark}" fill="none" stroke="{ink}" '
           f'stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>')
    return (f'<g transform="rotate({angle} {cx} {cy})"><g filter="url(#drop)"><g filter="url(#stampInk)">'
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="14" fill="{fill}"/>'
            f'<rect x="{x + 12:.0f}" y="{y + 12:.0f}" width="{w - 24:.0f}" height="{h - 24:.0f}" rx="7" fill="none" stroke="{ink}" stroke-width="5"/>'
            + sym + card.text(x + pad + sym_w + gap, cy + size * 0.35, label, size, ink, tracking=3) + '</g></g></g>')


def order_up(card, x2, cy, size=40, label='ORDER UP'):
    """Neutral ink rubber stamp on open plays (owner-gated: ORDER_UP)."""
    w = width(label, size, tracking=2) + 36
    x = x2 - w
    return (f'<g transform="rotate(-4 {x + w / 2:.0f} {cy})" filter="url(#stampInk)" opacity="0.92">'
            f'<rect x="{x:.0f}" y="{cy - size * 0.78:.0f}" width="{w:.0f}" height="{size * 1.5:.0f}" rx="6" fill="none" stroke="{INK}" stroke-width="5"/>'
            + card.text(x + 18, cy + size * CAP / 2, label, size, INK, tracking=2) + '</g>')


def pill(card, x2, cy, label, fill, ink, size=50, mark=None):
    lw = width(label, size, tracking=1)
    extra = 52 if mark else 0
    w = lw + 48 + extra
    x = x2 - w
    s = f'<rect x="{x:.0f}" y="{cy - size * 0.72:.0f}" width="{w:.0f}" height="{size * 1.44:.0f}" rx="{size * 0.72:.0f}" fill="{fill}"/>'
    if mark:
        s += (f'<path transform="translate({x + 24:.0f} {cy - 14:.0f}) scale(0.62)" d="{mark}" fill="none" stroke="{ink}" '
              f'stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>')
    return s + card.text(x + 24 + extra, cy + size * CAP / 2, label, size, ink, tracking=1)


def leader(card, y, left, right, lsize=42, rsize=56, lfam='d', rfill=INK, x1=X1, x2=X2):
    """Receipt row: label left, dotted leader, value right."""
    lw = width(left, lsize, lfam, 600)
    rw = width(right, rsize)
    return (card.text(x1, y, left, lsize, INK_SOFT, lfam, 600) + dots(x1 + lw + 14, x2 - rw - 14, y - 6)
            + card.text(x2, y, right, rsize, rfill, anchor='end'))


# ------------------------------------------------------------------ copy helpers
STAT_UNITS = {   # stacked unit labels for the bet line
    'recYds': ('REC', 'YDS'), 'rushYds': ('RUSH', 'YDS'), 'passYds': ('PASS', 'YDS'), 'passTD': ('PASS', 'TDS'),
    'rec': ('RECS',), 'car': ('CARRIES',), 'cmp': ('COMP',), 'att': ('PASS', 'ATT'), 'rushRecYds': ('RUSH+REC', 'YDS'),
    'total': ('TOTAL', 'PTS'),
}
SHORT_WORDS = (('rushing + receiving yards', 'rush+rec yds'), ('receiving yards', 'rec yds'), ('rushing yards', 'rush yds'),
               ('passing yards', 'pass yds'), ('passing touchdowns', 'pass TDs'), ('pass attempts', 'pass att'),
               ('receptions', 'recs'), ('completions', 'comp'), ('anytime touchdown', 'anytime TD'))


def short_words(text):
    out = str(text)
    for long, short in SHORT_WORDS:
        out = re.sub(long, short, out, flags=re.I)
    return out


def leg_parts(title):
    """(subject, selection) from a leg title: 'Packers at Buccaneers over 38.5' -> ('Packers at Buccaneers',
    'OVER 38.5'); 'Malik Willis 125+ passing yards' -> ('Malik Willis', '125+ PASS YDS'); 'Pitt +10.5' -> ('Pitt', '+10.5')."""
    t = str(title).strip()
    m = re.match(r'^(.*?)\s+(over|under)\s+(\d+(?:\.\d+)?)\s*(.*)$', t, re.I)
    if m:
        return m.group(1), f'{m.group(2).upper()} {m.group(3)} {short_words(m.group(4)).upper()}'.strip()
    m = re.match(r'^(.*?)\s+(\d+(?:\.\d+)?\+)\s+(.+)$', t)
    if m:
        return m.group(1), f'{m.group(2)} {short_words(m.group(3)).upper()}'
    m = re.match(r'^(.*?)\s+([+\-−]\d+(?:\.\d+)?)$', t)
    if m:
        return m.group(1), m.group(2).replace('-', MINUS)
    m = re.match(r'^(.*?)\s+(anytime touchdown|moneyline|to win)$', t, re.I)
    if m:
        return m.group(1), short_words(m.group(2)).upper().replace('MONEYLINE', 'TO WIN')
    return t, ''


def initials(name):
    parts = [p for p in re.split(r'[\s\-]+', str(name)) if p and p.lower().rstrip('.') not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return ''.join(p[0].upper() for p in parts[:2]) or '?'


# ------------------------------------------------------------------ QA (run on every build; port into tests)
GUARANTEE = re.compile(r'\b(lock|locks|free money|can.?t lose|guarantee[ds]?|sure thing|no.?brainer|max bet)\b', re.I)


def qa(card, name):
    """Every readable text >= 40 px (footer 24 px), inside the canvas, no en/em dash, no guarantee words,
    and 'plate' only inside 'HOT PLATE (POTD)'."""
    problems = []
    for node in card.texts:
        s, size, role = node['text'], node['size'], node['role']
        floor = 24 if role == 'footer' else 40
        if size < floor:
            problems.append(f'{name}: {size}px < {floor}px: {s!r}')
        if re.search('[–—]', s):
            problems.append(f'{name}: dash in {s!r}')
        if GUARANTEE.search(s):
            problems.append(f'{name}: guarantee word in {s!r}')
        if re.search(r'plate', s.replace('HOT PLATE (POTD)', '').replace('Hot Plate (POTD)', ''), re.I):
            problems.append(f'{name}: plate outside Hot Plate (POTD): {s!r}')
        if node['x0'] < 40 - 0.5 or node['x1'] > W - 40 + 0.5:
            problems.append(f'{name}: outside the 40 px safe margin: {s!r} ({node["x0"]:.0f}..{node["x1"]:.0f})')
        if role != 'footer' and (node['x0'] < X1 - 16 or node['x1'] > X2 + 16) and role not in ('badge',):
            problems.append(f'{name}: outside the printed margins: {s!r} ({node["x0"]:.0f}..{node["x1"]:.0f})')
    return problems
