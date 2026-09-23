"""A branded card for one pick, as SVG from the pick's own fields; a PNG when a browser is on the machine.

The repo stays standard library: the SVG is plain text written here. Turning it into the PNG that X
will show is done by the machine's own browser in headless mode (Chrome on the Mac Studio), which is a
system tool, not a Python package, and never runs in the hosted workflow. The PNG is never committed.

  python scripts/pick_card.py PICK_ID [--out FILE.png] [--svg]
"""
import argparse
import html
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pricing

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1200, 675
GREEN, DEEP, CREAM, GOLD = '#0f5132', '#0a3622', '#f4f1e8', '#e9c46a'
CHROME_CANDIDATES = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                     '/Applications/Chromium.app/Contents/MacOS/Chromium', 'google-chrome', 'chromium')


def chrome_path():
    override = os.environ.get('KEENROUDY_CHROME')
    if override:
        return override
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate if Path(candidate).exists() else shutil.which(candidate)
    return None


def esc(text):
    return html.escape(str(text if text is not None else ''), quote=True)


def fit(text, limit):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def svg(pick, game=None, record=None, when=None):
    """The card. Every number on it is a field of the pick or the record handed in."""
    title = fit(pick.get('title') or '', 34)
    price = f"{int(pick['odds']):+d}" if isinstance(pick.get('odds'), (int, float)) else ''
    book = pick.get('book') or ''
    projection = pick.get('projection')
    line = pick.get('line')
    kicker = 'FAVORITE' if pick.get('favorite') else 'MODEL LEAN' if pick.get('modelLean') else 'PICK'
    matchup = ''
    if game:
        away, home = game.get('away') or {}, game.get('home') or {}
        matchup = f"{away.get('short') or away.get('abbreviation') or ''} at {home.get('short') or home.get('abbreviation') or ''}".strip()
        if game.get('kickoff'):
            try:
                moment = datetime.fromisoformat(str(game['kickoff']).replace('Z', '+00:00'))
                from zoneinfo import ZoneInfo
                matchup += f" · {moment.astimezone(ZoneInfo('America/New_York')):%a %-I:%M %p} ET"
            except ValueError:
                pass
    number_line = ''
    if isinstance(projection, (int, float)) and isinstance(line, (int, float)):
        number_line = f"Our number {pricing.fmt(float(projection))} · line {pricing.fmt(float(line))}"
    record_line = ''
    if record:
        record_line = f"Record {record.get('wins', 0)}-{record.get('losses', 0)}" + (f"-{record['pushes']}" if record.get('pushes') else '')
        if record.get('units') is not None:
            record_line += f" · {record['units']:+.2f}u"
    stamp = (when or datetime.now(timezone.utc)).strftime('%Y-%m-%d')
    confidence = f"Confidence {pick['confidence']} of 10" if pick.get('confidence') else ''
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">',
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">',
        f'<stop offset="0" stop-color="{GREEN}"/><stop offset="1" stop-color="{DEEP}"/></linearGradient></defs>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#g)"/>',
        f'<rect x="40" y="40" width="{WIDTH - 80}" height="{HEIGHT - 80}" rx="28" fill="none" stroke="{GOLD}" stroke-opacity="0.55" stroke-width="3"/>',
        f'<text x="80" y="118" fill="{GOLD}" font-size="30" font-weight="700" letter-spacing="6">KEENROUDY SPORTS</text>',
        f'<text x="{WIDTH - 80}" y="118" fill="{CREAM}" fill-opacity="0.8" font-size="26" text-anchor="end">{esc(kicker)}</text>',
        f'<text x="80" y="220" fill="{CREAM}" fill-opacity="0.85" font-size="34">{esc(matchup)}</text>',
        f'<text x="80" y="320" fill="{CREAM}" font-size="{64 if len(title) <= 26 else 52}" font-weight="700">{esc(title)}</text>',
        f'<text x="80" y="400" fill="{GOLD}" font-size="54" font-weight="700">{esc(price)}</text>',
        f'<text x="{80 + 60 * max(len(price), 3)}" y="400" fill="{CREAM}" fill-opacity="0.9" font-size="36">{esc(book)}</text>',
        f'<text x="80" y="470" fill="{CREAM}" fill-opacity="0.9" font-size="32">{esc(number_line)}</text>',
        f'<text x="80" y="520" fill="{CREAM}" fill-opacity="0.75" font-size="28">{esc(confidence)}</text>',
        f'<text x="80" y="{HEIGHT - 80}" fill="{CREAM}" fill-opacity="0.9" font-size="28">keenroudy.com/sports</text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 80}" fill="{CREAM}" fill-opacity="0.7" font-size="24" text-anchor="end">{esc(record_line or stamp)}</text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 120}" fill="{CREAM}" fill-opacity="0.55" font-size="20" text-anchor="end">Entertainment only. Not advice.</text>',
        '</svg>']
    return '\n'.join(parts)


def render(svg_text, out, chrome=None, timeout=45):
    """Rasterize the SVG to a PNG with the machine's headless browser. Raises when there is none.

    Chrome writes the screenshot and then, on this machine, does not exit on its own, so the file is
    watched for and the browser is stopped once the file has stopped growing.
    """
    import time
    chrome = chrome or chrome_path()
    if not chrome:
        raise RuntimeError('no headless browser on this machine; set KEENROUDY_CHROME to a Chrome or Chromium binary')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / 'card.html'
        page.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;background:{DEEP}}}'
                        f'svg{{display:block}}</style></head><body>{svg_text}</body></html>', encoding='utf-8')
        process = subprocess.Popen([chrome, '--headless', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                                    '--disable-extensions', '--no-first-run', '--virtual-time-budget=2000',
                                    f'--user-data-dir={folder}/profile', f'--window-size={WIDTH},{HEIGHT}',
                                    f'--screenshot={out}', page.as_uri()],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline, last_size, stable = time.time() + timeout, -1, 0
        try:
            while time.time() < deadline:
                if process.poll() is not None and out.exists():
                    break
                size = out.stat().st_size if out.exists() else -1
                stable = stable + 1 if size > 0 and size == last_size else 0
                last_size = size
                if stable >= 3:            # three checks without growth: the file is complete
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError('browser render failed: no screenshot was written')
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('pick_id')
    parser.add_argument('--out', help='PNG path; default the sports config folder')
    parser.add_argument('--svg', action='store_true', help='print the SVG instead of rendering')
    args = parser.parse_args(argv)
    import gates
    stores = gates.Stores()
    ctx = stores.as_of(datetime.now(timezone.utc))
    pick = ctx.first.get(args.pick_id)
    if not pick:
        sys.exit(f'{args.pick_id} is not in research/')
    game = ctx.games.get((pick.get('gameIds') or [None])[0])
    text = svg(pick, game)
    if args.svg:
        print(text)
        return 0
    out = Path(args.out) if args.out else Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy')) / 'x-drafts' / f'{args.pick_id}.png'
    print(render(text, out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
