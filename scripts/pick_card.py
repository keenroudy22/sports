"""A card for one play in the kitchen's colours: the team we lean on, as SVG from the pick's own fields.

The repo stays standard library: the SVG is plain text written here. Turning it into the PNG that X
will show is done by a headless browser on the machine (Chrome on the Mac Studio or a GitHub runner),
which is a system tool, not a Python package. The PNG is never committed.

The card wears the colours of the side the play is on: the team a spread backs, the player's team for a
prop, the home team for a total with the away team's colour at the edge. Colours come from the slate
(ESPN's team colours) with the site's own table as the fallback. The theme is the kitchen: KOOK'N, the
pan, a plate served at a book.

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
NEUTRAL = '#2b3440'
CREAM, INK = '#f6f1e6', '#141414'
CHROME_CANDIDATES = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                     '/Applications/Chromium.app/Contents/MacOS/Chromium', 'google-chrome', 'google-chrome-stable',
                     'chromium', 'chromium-browser')


def chrome_path():
    override = os.environ.get('KEENROUDY_CHROME')
    if override:
        return override
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def esc(text):
    return html.escape(str(text if text is not None else ''), quote=True)


def fit(text, limit):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


# ------------------------------------------------------------------ colour

def hex_rgb(value):
    value = str(value or '').lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return hex_rgb(NEUTRAL)


def luminance(value):
    r, g, b = (c / 255 for c in hex_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def shade(value, factor):
    """The colour scaled toward black (factor < 1) or white (factor > 1)."""
    r, g, b = hex_rgb(value)
    if factor <= 1:
        r, g, b = (int(c * factor) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * (factor - 1)) for c in (r, g, b))
    return '#{:02x}{:02x}{:02x}'.format(*(max(0, min(255, c)) for c in (r, g, b)))


def team_colors(game, side, identities=None):
    """(primary, alternate) for one side of a game: the slate's colours, else the site's table, else neutral."""
    team = (game or {}).get(side) or {}
    primary = team.get('color')
    if not primary:
        try:
            import build_site
            primary = build_site.color((game or {}).get('league'), team.get('abbreviation'), identities or {})
        except Exception:
            primary = None
    primary = primary if primary and primary.lower() not in ('#64748b',) else NEUTRAL
    return primary, team.get('alternateColor') or shade(primary, 0.55)


def side_for(pick, game, player_side=None):
    """Which side the play is on: the spread's team, the player's team, or the home team for a total."""
    if pick.get('athleteId'):
        return player_side or 'home'
    direction = str(pick.get('direction') or '').lower()
    if pick.get('marketType') == 'spread' and direction in ('home', 'away'):
        return direction
    return 'home'


# ------------------------------------------------------------------ the card

PAN = ('<g transform="translate({x},{y}) scale({s})" fill="none" stroke="{c}" stroke-width="7" stroke-linecap="round">'
       '<circle cx="34" cy="34" r="26"/><path d="M60 34 H108"/><circle cx="34" cy="34" r="12" stroke-width="4" stroke-opacity="0.6"/></g>')
AVATAR = ROOT / 'site' / 'kookn.jpg'     # the @keenkooks profile picture, the kitchen's face
CHEF = ROOT / 'site' / 'kookn-chef.png'  # the same chef cut out of that picture (macOS subject lifting), served on the plate


def avatar_uri(path=AVATAR):
    """The avatar as a data URI, so the SVG renders anywhere; None when the file is not there."""
    import base64
    path = Path(path)
    if not path.exists():
        return None
    mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def badge(x, y, r, uri, ring):
    """A round badge holding the avatar, with a ring in the accent colour."""
    return (f'<defs><clipPath id="badge"><circle cx="{x}" cy="{y}" r="{r}"/></clipPath></defs>'
            f'<image href="{uri}" x="{x - r}" y="{y - r}" width="{2 * r}" height="{2 * r}" clip-path="url(#badge)" preserveAspectRatio="xMidYMid slice"/>'
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{ring}" stroke-width="4"/>')


def plate(cx, cy, uri, light):
    """The plate every card serves on, with the chef in it: the cutout scaled past the rim so the edges of the
    source picture (the hat's top, the shoulders) fall outside, and the rim drawn over it."""
    r, size = 178, 380
    parts = [f'<circle cx="{cx}" cy="{cy}" r="215" fill="{CREAM}" fill-opacity="{0.10 if not light else 0.35}"/>',
             f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{CREAM}" fill-opacity="{0.16 if not light else 0.45}"/>']
    if uri:
        parts += [f'<defs><clipPath id="plate"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>',
                  f'<image href="{uri}" x="{cx - 195}" y="{cy - r - 22}" width="{size}" height="{size}" clip-path="url(#plate)"/>']
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CREAM}" stroke-opacity="{0.35 if not light else 0.6}" stroke-width="4"/>')
    return parts


FRACTIONS = {0.25: '¼', 0.5: '½', 0.75: '¾'}


def stake(pick):
    """Units at risk, as the site's record counts them (site/core.js stakeOf): riskUnits, else one."""
    try:
        risk = float(pick.get('riskUnits'))
    except (TypeError, ValueError):
        return 1.0
    return risk if risk > 0 else 1.0


def units_label(pick):
    amount = stake(pick)
    if amount in FRACTIONS:
        return f'{FRACTIONS[amount]} unit'
    return f'{amount:g} unit' + ('' if amount == 1 else 's')


def number_line(pick):
    """Our number against the line, the same words on the card and in the post."""
    projection, line = pick.get('projection'), pick.get('line')
    if isinstance(projection, (int, float)) and isinstance(line, (int, float)):
        return f"Our number {pricing.fmt(float(projection))} vs the {pricing.fmt(float(line))}"
    return ''


KINDS = {'player': 'PLAYER PROP', 'team': 'TEAM PROP', 'parlay': 'FUN PARLAY'}


def play_kind(pick):
    """What goes to X, in the owner's words: player props, team props (sides and totals) and fun parlays."""
    if pick.get('legs') or pick.get('parlayType'):
        return 'parlay'
    return 'player' if pick.get('athleteId') or pick.get('market') else 'team'


def kicker(pick):
    """The label every card and every post leads with; a researched favorite says so."""
    label = KINDS[play_kind(pick)]
    return f'{label} · FAVORITE' if pick.get('favorite') is True and play_kind(pick) != 'parlay' else label


def svg(pick, game=None, record=None, when=None, player_side=None, identities=None, avatar=None):
    """The card. Every number on it is a field of the pick or the record handed in."""
    chef = avatar_uri(CHEF) if avatar is None else avatar
    side = side_for(pick, game, player_side)
    primary, alternate = team_colors(game, side, identities)
    other, _ = team_colors(game, 'away' if side == 'home' else 'home', identities)
    light = luminance(primary) > 0.55
    ink = INK if light else CREAM
    soft = shade(INK, 1.35) if light else shade(CREAM, 0.82)
    accent = alternate if abs(luminance(alternate) - luminance(primary)) > 0.25 else (INK if light else CREAM)
    title = pick.get('title') or ''
    price = f"{int(pick['odds']):+d}" if isinstance(pick.get('odds'), (int, float)) else ''
    book = pick.get('book') or ''
    label = kicker(pick)
    parlay = play_kind(pick) == 'parlay'
    legs = [str(l.get('title') or '') for l in (pick.get('legs') or []) if l.get('title')]
    if parlay:
        title = f"{len(pick.get('legs') or [])}-leg parlay"
    matchup = ''
    if game:
        away, home = game.get('away') or {}, game.get('home') or {}
        matchup = f"{away.get('short') or away.get('abbreviation') or ''} at {home.get('short') or home.get('abbreviation') or ''}".strip()
        if game.get('kickoff'):
            try:
                moment = datetime.fromisoformat(str(game['kickoff']).replace('Z', '+00:00'))
                from zoneinfo import ZoneInfo
                local = moment.astimezone(ZoneInfo('America/New_York'))
                matchup += f" · {local:%a %-I:%M %p} ET"
                if parlay:          # a ticket spans games: say how many and which day, not one game's name
                    matchup = f"{len(set(pick.get('gameIds') or [])) or len(legs)} games · {local:%a %b %-d}"
            except ValueError:
                pass
    ours = number_line(pick)
    units = units_label(pick)
    record_line = ''
    if record:
        record_line = f"Record {record.get('wins', 0)}-{record.get('losses', 0)}" + (f"-{record['pushes']}" if record.get('pushes') else '')
        if record.get('units') is not None:
            record_line += f" · {record['units']:+.2f}u"
    lines = title_lines(title)
    title_size = 66 if len(lines) == 1 and len(title) <= 24 else 56 if len(lines) == 1 else 50
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">',
        '<defs>',
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{primary}"/><stop offset="0.72" stop-color="{shade(primary, 0.8)}"/><stop offset="1" stop-color="{other}"/></linearGradient>',
        '</defs>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>',
        # the plate the play is served on, the chef in it: the same on every card
        *plate(WIDTH - 250, HEIGHT // 2 + 20, chef, light),
        f'<rect x="36" y="36" width="{WIDTH - 72}" height="{HEIGHT - 72}" rx="30" fill="none" stroke="{accent}" stroke-opacity="0.55" stroke-width="3"/>',
        PAN.format(x=72, y=78, s=0.5, c=accent),
        f'<text x="140" y="116" fill="{ink}" font-size="34" font-weight="800" letter-spacing="5">KOOK’N</text>',
        f'<text x="{WIDTH - 80}" y="116" fill="{soft}" font-size="26" font-weight="700" letter-spacing="3" text-anchor="end">{esc(label)}</text>',
        f'<text x="80" y="212" fill="{soft}" font-size="32">{esc(matchup)}</text>',
        f'<text x="80" y="262" fill="{accent}" font-size="24" font-weight="700" letter-spacing="4">TODAY’S PLATE</text>',
        *[f'<text x="80" y="{262 + (title_size + 6) * (i + 1) - 2}" fill="{ink}" font-size="{title_size}" font-weight="800">{esc(text)}</text>'
          for i, text in enumerate(lines)],
        *(parlay_body(legs, price, book, units, ink, soft, accent, title_size) if parlay else [
        f'<text x="80" y="418" fill="{soft}" font-size="26" letter-spacing="1">Served at</text>',
        f'<text x="80" y="470" fill="{ink}" font-size="50" font-weight="800">{esc(price)}<tspan fill="{soft}" font-size="34" font-weight="600" dx="18">{esc(book)}</tspan>'
        f'<tspan fill="{soft}" font-size="26" font-weight="400" dx="14">· {esc(units)}</tspan></text>',
        f'<text x="80" y="530" fill="{ink}" font-size="32">{esc(ours)}</text>']),
        f'<text x="80" y="{HEIGHT - 62}" fill="{ink}" font-size="26" font-weight="700">Graded in public, win or lose. <tspan fill="{soft}" font-weight="400">keenroudy.com/sports</tspan></text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 62}" fill="{soft}" font-size="19" text-anchor="end">Entertainment only. Not advice.</text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 94}" fill="{soft}" font-size="22" text-anchor="end">{esc(record_line)}</text>' if record_line else '',
        '</svg>']
    return '\n'.join(parts)


def title_lines(title, width=26, limit=30):
    """The play on one line, or on two when it is long: a player's name above the line he is on
    ("Courtland Sutton" / "OVER 3.5 receptions"), else split at the word nearest the middle."""
    if len(title) <= limit:
        return [title]
    words = title.split()
    cut = next((i for i, w in enumerate(words) if w.lower() in ('over', 'under') and i > 0), None)
    if cut is None:
        best, cut = None, 1
        for i in range(1, len(words)):
            gap = abs(len(' '.join(words[:i])) - len(' '.join(words[i:])))
            if best is None or gap < best:
                best, cut = gap, i
    return [fit(' '.join(words[:cut]), width + 6), fit(' '.join(words[cut:]), width + 6)]


def parlay_body(legs, price, book, units, ink, soft, accent, title_size):
    """A parlay in the same frame as every other card: its legs where a single play's numbers go, and its
    price on the "Served at" line."""
    top = 262 + title_size + 4 + 44
    shown = legs if len(legs) <= 5 else legs[:4]
    rows = [f'<text x="80" y="{top + 34 * i}" fill="{ink}" font-size="26">• {esc(fit(leg, 40))}</text>' for i, leg in enumerate(shown)]
    if len(legs) > len(shown):
        rows.append(f'<text x="80" y="{top + 34 * len(shown)}" fill="{soft}" font-size="24">and {len(legs) - len(shown)} more</text>')
    rows.append(f'<text x="80" y="562" fill="{soft}" font-size="26" letter-spacing="1">Served at <tspan fill="{ink}" font-size="44" '
                f'font-weight="800" letter-spacing="0" dx="8">{esc(price)}</tspan><tspan fill="{soft}" font-size="30" font-weight="600" '
                f'letter-spacing="0" dx="14">{esc(book)}</tspan><tspan fill="{soft}" font-size="26" letter-spacing="0" dx="14">· {esc(units)}</tspan></text>')
    return rows


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
        page.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;background:{NEUTRAL}}}'
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
    player_side = None
    if pick.get('athleteId') and game:
        team = ctx.player_team.get(str(pick['athleteId']))
        player_side = 'home' if team == str(game['home']['id']) else 'away' if team == str(game['away']['id']) else None
    text = svg(pick, game, player_side=player_side)
    if args.svg:
        print(text)
        return 0
    out = Path(args.out) if args.out else Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy')) / 'x-drafts' / f'{args.pick_id}.png'
    print(render(text, out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
