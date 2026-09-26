"""The weekly projections sheet: "📌 SAVE THIS", one image of the slate the way the site's game cards show it. Stdlib only.

The most saved data posts among the accounts we follow are cheat sheets with the ask in the first line (Jimmy's
"Save this post now", Toad's "Bookmark this sheet"; docs/X-NOTES.md). The owner said yes on 2026-09-26. Once a week
per league, on its big day (college Saturday, NFL Sunday), the morning post is one image: each game's logos, our
projected score, how often we think each team wins, and our spread and total beside the betting line, the same numbers
as the Games page (built from the site's own game cards, site/data/app/today.json). College shows the day's games
where our number and the line differ most; the NFL shows the whole Sunday slate.

The hosted build draws it (feed.py, into site/data/cards/, like every card) and the desk posts it at 10:00 AM
(receipts.house_posts). Nothing on it is a pick: the plays go out on their own.

  python scripts/sheet.py [--league NFL|CFB] [--day YYYY-MM-DD] [--out PATH]    draw one sheet from today.json
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates
import pick_card
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
TODAY = ROOT / 'site' / 'data' / 'app' / 'today.json'
DAYS = {'CFB': 5, 'NFL': 6}             # Saturday for college, Sunday for the NFL (Monday is 0)
POST_AT, POST_UNTIL = (10, 0), (11, 45)  # Eastern
MOST, FEWEST = 16, 4                    # games on a sheet; a slate thinner than FEWEST gets none
WIDTH, HEIGHT = 1080, 1350              # 4:5, the tallest image X shows whole in the feed
BG, CARD, LINE, TEXT, DIM, ORANGE = '#0d1218', '#161d27', '#2a3441', '#f4f7fa', '#94a3b4', '#f28c28'
WORDS = {'CFB': 'COLLEGE', 'NFL': 'NFL'}
SMALL_LOGO = 'https://a.espncdn.com/combiner/i?img={path}&h=96&w=96'


def key(league, day):
    return f'sheet-{league.lower()}-{day.isoformat()}'


def sheet_day(league, day):
    return day.weekday() == DAYS[league]


def disagreement(card):
    lean = card.get('lean') or {}
    return max(abs(lean.get('spread') or 0), abs(lean.get('total') or 0))


def pick_games(cards, league, day):
    """The games on the sheet: the league's games that day with our number and a line, none against an FCS school.
    College: the MOST where our number and the line differ most. NFL: the slate. Kickoff order either way."""
    games = [c for c in cards if c.get('league') == league and c.get('v2') and (c.get('market') or {}).get('total') is not None
             and not c.get('fcs') and c.get('state', 'pre') == 'pre' and eastern_date(gates.when(c['kickoff'])) == day]
    if league == 'CFB':
        games = sorted(games, key=lambda c: -disagreement(c))[:MOST]
    return sorted(games, key=lambda c: (c['kickoff'], c['id']))[:MOST]


def logo_uri(card, side, fetch=None):
    team = card.get(side) or {}
    league = card.get('league')
    path = (f"/i/teamlogos/nfl/500/{str(team.get('abbr') or '').lower()}.png" if league == 'NFL'
            else f"/i/teamlogos/ncaa/500/{team.get('id')}.png" if team.get('id') else None)
    return (fetch or pick_card.fetch_data_uri)(SMALL_LOGO.format(path=path)) if path else None


def spread_text(card, margin):
    """A line from the home team's point of view as the favourite's: "BUF -7"; "Pick" at zero."""
    if margin is None:
        return '-'
    if abs(margin) < 0.05:
        return 'Pick'
    team = card['home'] if margin > 0 else card['away']
    return f"{team.get('abbr')} -{pricing_fmt(abs(margin))}"


def pricing_fmt(value):
    return f'{round(float(value), 1):g}'


def readable(team):
    """A team colour that shows on the dark card: the primary, else the alternate (the Commanders' gold, the Cowboys'
    silver), else the primary lightened; the house orange when the team has none."""
    ok = lambda c: isinstance(c, str) and c.startswith('#') and len(c) == 7
    colours = [c for c in (team.get('color'), team.get('alt')) if ok(c)]
    for colour in colours:
        if 0.2 <= pick_card.luminance(colour) <= 0.9:
            return colour
    return pick_card.shade(colours[0], 1.45) if colours else ORANGE


def card_svg(card, x, y, w, h, logos):
    v2, market, lean = card['v2'], card.get('market') or {}, card.get('lean') or {}
    esc = pick_card.esc
    home_chance = v2.get('winProb')
    rows = []
    for i, side in enumerate(('away', 'home')):
        team = card[side]
        top = y + 14 + 36 * i
        chance = None if home_chance is None else (home_chance if side == 'home' else 1 - home_chance)
        uri = logos.get((card['id'], side))
        rows.append(f'<image href="{uri}" x="{x + 16}" y="{top}" width="30" height="30" preserveAspectRatio="xMidYMid meet"/>' if uri else
                    f'<circle cx="{x + 31}" cy="{top + 15}" r="13" fill="{readable(team)}"/>')
        rows.append(f'<text x="{x + 56}" y="{top + 24}" fill="{TEXT}" font-size="24" font-weight="800">{esc(team.get("abbr") or "")}</text>')
        points = v2.get(side)
        rows.append(f'<text x="{x + 236}" y="{top + 25}" fill="{TEXT}" font-size="28" font-weight="800" text-anchor="end">'
                    f'{esc(f"{points:.1f}" if isinstance(points, (int, float)) else "-")}</text>')
        if chance is not None:
            bar = max(4, round(150 * chance))
            rows.append(f'<rect x="{x + 256}" y="{top + 8}" width="150" height="16" rx="8" fill="{LINE}"/>')
            rows.append(f'<rect x="{x + 256}" y="{top + 8}" width="{bar}" height="16" rx="8" fill="{readable(team)}"/>')
            rows.append(f'<text x="{x + w - 16}" y="{top + 22}" fill="{TEXT}" font-size="20" font-weight="700" text-anchor="end">{round(100 * chance)}%</text>')
    # Our numbers against the line; the one our number leans to clearly (as the site's chips do) in orange.
    strong = lambda chance, paused: chance is not None and chance >= 0.574 and not paused and not v2.get('sparse')
    spread_tone = ORANGE if strong(lean.get('spreadChance'), lean.get('spreadPaused')) else TEXT
    total_tone = ORANGE if strong(lean.get('totalChance'), lean.get('totalPaused')) else TEXT
    ours_spread, line_spread = spread_text(card, v2.get('margin')), spread_text(card, -market['spread'] if market.get('spread') is not None else None)
    base = y + h - 16
    rows.append(f'<text x="{x + 16}" y="{base}" fill="{DIM}" font-size="15">Spread <tspan fill="{spread_tone}" font-weight="700">'
                f'{esc(ours_spread)}</tspan> vs {esc(line_spread)}</text>')
    total = v2.get('total')
    rows.append(f'<text x="{x + w - 16}" y="{base}" fill="{DIM}" font-size="15" text-anchor="end">Total <tspan fill="{total_tone}" font-weight="700">'
                f'{esc(f"{total:.1f}" if isinstance(total, (int, float)) else "-")}</tspan> vs {esc(pricing_fmt(market["total"]))}</text>')
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{CARD}" stroke="{LINE}" stroke-width="2"/>'] + rows


def svg(games, league, day, week=None, logos=None):
    """The sheet: a header with the ask, two columns of game cards, the house line at the foot."""
    esc = pick_card.esc
    logos = logos or {}
    rows = (len(games) + 1) // 2
    top, foot, gap = 196, 96, 12
    pitch = (HEIGHT - top - foot) / max(rows, 1)
    h = min(150, pitch - gap)
    w = (WIDTH - 72 - 20) // 2
    title = f"WEEK {week} {WORDS[league]} PROJECTIONS" if week else f"{WORDS[league]} PROJECTIONS"
    when = f"{day:%A, %B} {day.day}"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
             f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif">',
             f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>',
             f'<rect width="{WIDTH}" height="8" fill="{ORANGE}"/>',
             f'<circle cx="46" cy="62" r="9" fill="{ORANGE}"/>',
             f'<text x="64" y="71" fill="{ORANGE}" font-size="26" font-weight="800" letter-spacing="5">SAVE THIS</text>',
             f'<text x="{WIDTH - 36}" y="71" fill="{DIM}" font-size="24" font-weight="700" letter-spacing="4" text-anchor="end">KOOK’N</text>',
             f'<text x="36" y="132" fill="{TEXT}" font-size="54" font-weight="800">{esc(title)}</text>',
             f'<text x="36" y="172" fill="{DIM}" font-size="22">{esc(when)} · projected score, win chance, our number vs the line</text>']
    for i, card in enumerate(games):
        col, row = i % 2, i // 2
        parts += card_svg(card, 36 + col * (w + 20), round(top + row * pitch), w, round(h), logos)
    parts += [f'<text x="36" y="{HEIGHT - 52}" fill="{TEXT}" font-size="22" font-weight="700">Graded in public, win or lose. '
              f'<tspan fill="{DIM}" font-weight="400">keenroudy.com/sports</tspan></text>',
              f'<text x="36" y="{HEIGHT - 22}" fill="{DIM}" font-size="17">Not picks: our plays go out on their own. '
              f'{"Orange: our number leans clearly. " if ORANGE in "".join(parts[8:]) else ""}Entertainment only.</text>',
              '</svg>']
    return '\n'.join(parts)


def load_cards(path=TODAY):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8')).get('games') or []
    except (OSError, ValueError):
        return []


def due(now, cards):
    """[(league, day, games)] for the sheets to draw today: a league on its day with a full enough slate."""
    day = eastern_date(now)
    out = []
    for league in DAYS:
        if sheet_day(league, day):
            games = pick_games(cards, league, day)
            if len(games) >= FEWEST:
                out.append((league, day, games))
    return out


def render_due(now, folder, cards=None, fetch=None, log=print):
    """Draw today's sheets into the cards folder (the hosted build). Returns {key: path}."""
    cards = load_cards() if cards is None else cards
    out = {}
    for league, day, games in due(now, cards):
        logos = {(c['id'], side): logo_uri(c, side, fetch) for c in games for side in ('away', 'home')}
        path = Path(folder) / f'{key(league, day)}.png'
        try:
            pick_card.render(svg(games, league, day, games[0].get('week'), logos), path, size=(WIDTH, HEIGHT))
            out[key(league, day)] = path
        except Exception as error:
            log(f'sheet {key(league, day)} not drawn: {error}')
    return out


def at(day, hm):
    return datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)


def post(games, now):
    """The morning post for the day's sheet, or None: {key, kind, card, text, due, stale}. `games` is the slate
    (gameId -> game), so the desk can say which week without the site's files."""
    day = eastern_date(now)
    for league in DAYS:
        if not sheet_day(league, day) or now >= at(day, POST_UNTIL):
            continue
        todays = [g for g in games.values() if g.get('league') == league and eastern_date(gates.when(g['kickoff'])) == day]
        if len(todays) < FEWEST:
            continue
        week = min((g.get('week') for g in todays if g.get('week') is not None), default=None)
        name = 'college' if league == 'CFB' else 'NFL'
        scope = ("today's games where our number and the line differ most" if league == 'CFB' else 'every Sunday game')
        head = f"📌 SAVE THIS\nOur Week {week} {name} projections" if week else f"📌 SAVE THIS\nOur {name} projections"
        text = (f"{head}: the projected score, how often each team wins, and our spread and total next to the line, for {scope}.\n\n"
                f"Graded in public. The plays go out on their own.\n#{league}")
        return {'key': f'sheet:{league}:{day.isoformat()}', 'kind': 'sheet', 'card': key(league, day), 'text': text,
                'due': max(at(day, POST_AT), now + timedelta(minutes=2)), 'stale': at(day, POST_UNTIL)}
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--league', choices=tuple(DAYS), default='NFL')
    parser.add_argument('--day', help='YYYY-MM-DD, Eastern; default the league\'s next day')
    parser.add_argument('--out', help='PNG path; default the sports config folder')
    parser.add_argument('--svg', action='store_true', help='print the SVG instead of drawing it')
    args = parser.parse_args(argv)
    today = eastern_date(datetime.now(timezone.utc))
    day = date.fromisoformat(args.day) if args.day else today + timedelta(days=(DAYS[args.league] - today.weekday()) % 7)
    games = pick_games(load_cards(), args.league, day)
    if not games:
        print(f'no {args.league} games with our number and a line on {day}')
        return 1
    logos = {(c['id'], side): logo_uri(c, side) for c in games for side in ('away', 'home')}
    text = svg(games, args.league, day, games[0].get('week'), logos)
    if args.svg:
        print(text)
        return 0
    out = Path(args.out) if args.out else Path.home() / '.config' / 'keenroudy' / 'x-drafts' / f'{key(args.league, day)}.png'
    print(pick_card.render(text, out, size=(WIDTH, HEIGHT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
