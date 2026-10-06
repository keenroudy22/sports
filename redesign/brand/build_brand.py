"""Build the Kook'n brand kit: vector logo files and PNG exports. Python standard library only.

The letterforms are drawn as paths (no font needed), so the wordmark renders the same everywhere.
PNGs are rasterized with the desk's own headless-Chrome renderer (scripts/pick_card.render).

  python3 redesign/brand/build_brand.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'scripts'))

FELT_NIGHT, FELT, CHALK, KOOKD, INK = '#07120D', '#0E2219', '#F2F7F4', '#20C774', '#07120D'


def rounded(x, y, w, h, r):
    return (f'M{x + r},{y} H{x + w - r} A{r},{r} 0 0 1 {x + w},{y + r} V{y + h - r} A{r},{r} 0 0 1 {x + w - r},{y + h} '
            f'H{x + r} A{r},{r} 0 0 1 {x},{y + h - r} V{y + r} A{r},{r} 0 0 1 {x + r},{y} Z')


def letter_k(x):
    pts = [(0, 0), (18, 0), (18, 40), (44, 0), (66, 0), (36, 46), (68, 100), (46, 100), (18, 56), (18, 100), (0, 100)]
    return 'M' + ' L'.join(f'{x + a},{b}' for a, b in pts) + ' Z', 68


def letter_o(x):
    return rounded(x, 0, 56, 100, 26) + ' ' + rounded(x + 18, 18, 20, 64, 10), 56


def letter_n(x):
    pts = [(0, 0), (18, 0), (44, 62), (44, 0), (62, 0), (62, 100), (44, 100), (18, 38), (18, 100), (0, 100)]
    return 'M' + ' L'.join(f'{x + a},{b}' for a, b in pts) + ' Z', 62


def flame(x, y=0, s=1.0):
    """The green flame apostrophe."""
    return (f'<path transform="translate({x} {y}) scale({s})" fill="{KOOKD}" '
            'd="M8 0 C14 9 17 15 13.5 23 C11 29 3.5 29 1.5 23 C0 18 4 13 8 0 Z"/>')


def wordmark(ink=CHALK, sports=True, x0=0, y0=0, scale=1.0):
    """KOOK'N over SPORTS. Returns (svg group, width, height) in local units scaled by `scale`."""
    parts, x = [], 0
    for fn in (letter_k, letter_o, letter_o, letter_k):
        d, w = fn(x)
        parts.append(d)
        x += w + 8
    x -= 2
    apostrophe_x = x
    x += 20
    d, w = letter_n(x)
    parts.append(d)
    width = x + w
    body = f'<path fill="{ink}" fill-rule="evenodd" d="{" ".join(parts)}"/>' + flame(apostrophe_x, 0, 1.0)
    height = 100
    if sports:
        body += (f'<text x="0" y="146" textLength="{width}" lengthAdjust="spacing" fill="{KOOKD}" '
                 'font-family="DM Sans, Helvetica Neue, Arial, sans-serif" font-size="30" font-weight="700">SPORTS</text>')
        height = 152
    return f'<g transform="translate({x0} {y0}) scale({scale})">{body}</g>', width * scale, height * scale


def mark(x0=0, y0=0, scale=1.0, background=None):
    """The winning-ticket K with the chef hat and a green ✓ stub, on a 120-unit grid."""
    bg = f'<rect width="120" height="120" rx="24" fill="{background}"/>' if background else ''
    cut = background or FELT_NIGHT
    return (f'<g transform="translate({x0} {y0}) scale({scale})">{bg}'
            f'<rect x="10" y="38" width="100" height="62" rx="9" fill="{CHALK}"/>'
            f'<path d="M82 38 L101 38 Q110 38 110 47 L110 91 Q110 100 101 100 L82 100 Z" fill="{KOOKD}"/>'
            f'<circle cx="10" cy="69" r="8" fill="{cut}"/><circle cx="110" cy="69" r="8" fill="{cut}"/>'
            f'<path d="M82 44 L82 94" stroke="{cut}" stroke-width="3" stroke-dasharray="4 4"/>'
            f'<rect x="28" y="51" width="12" height="36" rx="2" fill="{INK}"/>'
            f'<path d="M45 69 L61 52" stroke="{INK}" stroke-width="11"/><path d="M45 69 L63 87" stroke="{INK}" stroke-width="11"/>'
            f'<path d="M88 70 L93 76 L101 63" stroke="{CHALK}" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<g transform="rotate(-14 34 30) translate(16.8 14.7) scale(0.32)" fill="{CHALK}" stroke="{cut}" stroke-width="6">'
            '<circle cx="38" cy="44" r="17"/><circle cx="60" cy="33" r="22"/><circle cx="82" cy="44" r="17"/>'
            '<rect x="31" y="44" width="58" height="18" stroke="none"/><rect x="31" y="66" width="58" height="13" rx="3"/></g></g>')


def svg(width, height, body, background=None, title="Kook'n"):
    bg = f'<rect width="{width}" height="{height}" fill="{background}"/>' if background else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">'
            f'<title>{title}</title>{bg}{body}</svg>')


def build():
    files = {}
    files['kookn-mark.svg'] = svg(120, 120, mark(background=FELT_NIGHT), title="Kook'n mark")
    files['kookn-mark-clear.svg'] = svg(120, 120, mark(), title="Kook'n mark (transparent)")
    wm, w, h = wordmark()
    files['kookn-wordmark.svg'] = svg(int(w) + 2, int(h) + 2, wm, title="Kook'n wordmark")
    wm_ink, w2, h2 = wordmark(ink=INK)
    files['kookn-wordmark-light-bg.svg'] = svg(int(w2) + 2, int(h2) + 2, wm_ink, title="Kook'n wordmark for light backgrounds")
    # Horizontal lockup: mark + wordmark.
    wm_h, ww, wh = wordmark(x0=168, y0=14, scale=0.62)
    files['kookn-lockup-horizontal.svg'] = svg(int(168 + ww + 16), 124, mark(0, 2, 1.0) + wm_h, background=FELT_NIGHT, title="Kook'n lockup")
    # Stacked lockup.
    wm_s, sw, sh = wordmark(scale=0.7)
    width = int(max(sw, 168) + 48)
    files['kookn-lockup-stacked.svg'] = svg(width, 330, mark((width - 168) / 2, 18, 1.4) + wordmark(x0=(width - sw) / 2, y0=200, scale=0.7)[0], background=FELT_NIGHT, title="Kook'n stacked lockup")
    # Card watermark (small, for the corner of social cards).
    files['kookn-watermark.svg'] = svg(260, 64, mark(0, 2, 0.5) + wordmark(x0=70, y0=10, scale=0.42, sports=False)[0], title="Kook'n watermark")
    # X avatar (400x400): the mark centered on felt, kept inside the circular crop.
    files['x-avatar-400.svg'] = svg(400, 400, mark(60, 60, 2.33), background=FELT_NIGHT, title="Kook'n X avatar")
    # X banner (1500x500). Key content sits in the safe band: clear of the avatar (bottom-left) and mobile crop (top/bottom).
    chips = ''.join(f'<rect x="{1346 + i * 40}" y="{440 - h}" width="28" height="{h}" rx="14" fill="{FELT}"/>' for i, h in enumerate((110, 170, 150, 250)))
    banner = (f'<rect width="1500" height="500" fill="{FELT_NIGHT}"/>{chips}'
              + mark(420, 128, 1.75)
              + wordmark(x0=660, y0=150, scale=0.95)[0]
              + f'<text x="662" y="360" fill="{CHALK}" font-family="Barlow Condensed, Arial Narrow, sans-serif" font-size="46" font-weight="700" letter-spacing="1">EVERY PLAY GRADED IN PUBLIC</text>'
              + f'<text x="664" y="400" fill="#A9C0B3" font-family="DM Sans, Helvetica Neue, Arial, sans-serif" font-size="24">Free best bets with the price, the book and our chance · 21+</text>')
    files['x-banner-1500x500.svg'] = svg(1500, 500, banner, title="Kook'n X banner")
    for name, text in files.items():
        (HERE / name).write_text(text + '\n', encoding='utf-8')
    return files


def export(files):
    import pick_card
    fonts = ('<style>@import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700'
             '&amp;family=DM+Sans:wght@400;700&amp;display=block");</style>')
    out = HERE / 'png'
    jobs = [('x-avatar-400.svg', 'x-avatar-400.png', (400, 400)), ('x-banner-1500x500.svg', 'x-banner-1500x500.png', (1500, 500)),
            ('kookn-lockup-horizontal.svg', 'kookn-lockup-horizontal.png', None), ('kookn-lockup-stacked.svg', 'kookn-lockup-stacked.png', None)]
    for src, dst, size in jobs:
        text = files[src].replace('role="img">', 'role="img">' + fonts, 1)
        pick_card.render(text, out / dst, size=size)
    for px in (16, 32, 180, 512):
        scaled = files['kookn-mark.svg'].replace('width="120" height="120"', f'width="{px}" height="{px}"', 1)
        pick_card.render(scaled, out / f'favicon-{px}.png', size=(px, px))
    return sorted(p.name for p in out.glob('*.png'))


if __name__ == '__main__':
    built = build()
    print('vectors:', ', '.join(sorted(built)))
    if '--no-png' not in sys.argv:
        print('png:', ', '.join(export(built)))
