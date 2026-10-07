"""The weekly projection sheet: "📌 SAVE THIS", the NFL slate or 16 college games. Stdlib only.

The most saved data posts among the accounts we follow are cheat sheets with the ask in the first line (Jimmy's
"Save this post now", Toad's "Bookmark this sheet"; docs/X-NOTES.md). The owner said yes on 2026-09-26. Once a week
per league, on its big day (college Saturday, NFL Sunday), the morning post is one image: each game's logos, our
projected score, how often we think each team wins, and our spread and total beside the betting line, the same numbers
as the Games page (built from the site's own game cards, site/data/app/today.json). NFL shows the whole slate; college
shows the 16 largest disagreements. A mint ring marks up to four lines where our calibrated chance clears the actual
captured price. A projection gap alone is never highlighted.

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
MOST, WATCH, FEWEST = 16, 4, 4          # a full NFL slate; four model/market disagreements get a mint ring
WIDTH, HEIGHT = 1080, 1350              # 4:5, the tallest image X shows whole in the feed
BG, CARD, LINE, TEXT, DIM, ACCENT = '#071018', '#101c28', '#2a3a49', '#f4f7fa', '#94a3b4', '#5eeaa4'
WORDS = {'CFB': 'COLLEGE', 'NFL': 'NFL'}
SMALL_LOGO = 'https://a.espncdn.com/combiner/i?img={path}&h=96&w=96'


def key(league, day):
    return f'sheet-{league.lower()}-{day.isoformat()}'


def sheet_day(league, day):
    return day.weekday() == DAYS[league]


def disagreement(card):
    lean = card.get('lean') or {}
    return max(abs(lean.get('spread') or 0), abs(lean.get('total') or 0))


def priced_value(card, market):
    """A usable real-price edge for one market, or None."""
    value = (card.get('value') or {}).get(market) or {}
    if value.get('tier') not in ('lean', 'strong') or value.get('thin') \
            or not isinstance(value.get('odds'), (int, float)):
        return None
    return value


def watch_label(card, market, value):
    """Name the wager itself, not merely its market family: OVER 44.5, HA -2.5, or HA ML."""
    side, line = value.get('side'), value.get('line')
    if market == 'total':
        return f"{'OVER' if side == 'over' else 'UNDER'} {line:g}"
    team = card.get(side) or {}
    abbr = team.get('abbr') or str(side or '').upper()
    if market == 'moneyline':
        return f'{abbr} ML'
    return f'{abbr} {line:+g}'


def priced_watch(card):
    """The strongest usable price edge, or None. Missing, thin and pass prices never get a mint ring."""
    rows = []
    for market in ('spread', 'total'):
        value = priced_value(card, market)
        if value:
            rows.append((value.get('edge') or -999, market, watch_label(card, market, value), value))
    return max(rows, default=None, key=lambda row: row[0])


def watches(games):
    """game id -> (rank, market, bet label, priced row) for the strongest real-price edges on the sheet."""
    rows = [(priced_watch(card), card['id']) for card in games]
    rows = [(watch, gid) for watch, gid in rows if watch]
    rows.sort(key=lambda row: (-row[0][0], row[1]))
    return {gid: (rank, watch[1], watch[2], watch[3]) for rank, (watch, gid) in enumerate(rows[:WATCH], 1)}


def book_short(name):
    return {'BetMGM': 'MGM', 'BetRivers': 'BR', 'DraftKings': 'DK', 'ESPN BET': 'ESPN',
            'FanDuel': 'FD', 'Fanatics': 'FAN', 'Caesars': 'CZR'}.get(name, str(name or '')[:5].upper())


def priced_text(card, market):
    """The chosen side, exact captured line, price and book in a compact label."""
    value = (card.get('value') or {}).get(market) or {}
    line, odds, side = value.get('line'), value.get('odds'), value.get('side')
    if not isinstance(line, (int, float)) or not isinstance(odds, (int, float)):
        return '-'
    if market == 'spread':
        team = card.get(side) or {}
        pick = f"{team.get('abbr') or ''} {line:+g}"
    else:
        pick = f"{'OVER' if side == 'over' else 'UNDER'} {line:g}"
    return f"{pick} {odds:+d} {book_short(value.get('book'))}".strip()


def pick_games(cards, league, day):
    """The games on the sheet: the league's games that day with our number and a line, none against an FCS school.
    The MOST where our number and the line differ most, returned in kickoff order."""
    games = [c for c in cards if c.get('league') == league and c.get('v2') and (c.get('market') or {}).get('total') is not None
             and not c.get('fcs') and c.get('state', 'pre') == 'pre' and eastern_date(gates.when(c['kickoff'])) == day]
    games = sorted(games, key=lambda c: -disagreement(c))[:MOST]
    return sorted(games, key=lambda c: (c['kickoff'], c['id']))


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
    return pick_card.shade(colours[0], 1.45) if colours else ACCENT


def card_svg(card, x, y, w, h, logos, watch=None):
    v2, market, lean = card['v2'], card.get('market') or {}, card.get('lean') or {}
    esc = pick_card.esc
    home_chance = v2.get('winProb')
    rows = []
    for i, side in enumerate(('away', 'home')):
        team = card[side]
        top = y + 24 + 62 * i
        chance = None if home_chance is None else (home_chance if side == 'home' else 1 - home_chance)
        uri = logos.get((card['id'], side))
        rows.append(f'<image href="{uri}" x="{x + 16}" y="{top}" width="48" height="48" preserveAspectRatio="xMidYMid meet"/>' if uri else
                    f'<circle cx="{x + 40}" cy="{top + 24}" r="22" fill="{readable(team)}"/>')
        rows.append(f'<text x="{x + 78}" y="{top + 37}" fill="{TEXT}" font-size="33" font-weight="800">{esc(team.get("abbr") or "")}</text>')
        points = v2.get(side)
        rows.append(f'<text x="{x + 254}" y="{top + 38}" fill="{TEXT}" font-size="40" font-weight="800" text-anchor="end">'
                    f'{esc(f"{points:.1f}" if isinstance(points, (int, float)) else "-")}</text>')
        if chance is not None:
            bar = max(4, round(125 * chance))
            rows.append(f'<rect x="{x + 276}" y="{top + 15}" width="125" height="20" rx="10" fill="{LINE}"/>')
            rows.append(f'<rect x="{x + 276}" y="{top + 15}" width="{bar}" height="20" rx="10" fill="{readable(team)}"/>')
            rows.append(f'<text x="{x + w - 18}" y="{top + 34}" fill="{TEXT}" font-size="24" font-weight="700" text-anchor="end">{round(100 * chance)}%</text>')
    # Mint the selected wager, not the model projection, so the opinion cannot be mistaken for the market line.
    watch_market = watch[1] if watch else None
    spread_tone = ACCENT if watch_market == 'spread' else TEXT
    total_tone = ACCENT if watch_market == 'total' else TEXT
    ours_spread, line_spread = spread_text(card, v2.get('margin')), spread_text(card, -market['spread'] if market.get('spread') is not None else None)
    rows.append(f'<line x1="{x + 16}" y1="{y + 158}" x2="{x + w - 16}" y2="{y + 158}" stroke="{LINE}" stroke-width="2"/>')
    rows.append(f'<text x="{x + 18}" y="{y + 205}" fill="{ACCENT}" font-size="19" font-weight="800" letter-spacing="3">OUR NUMBER / MARKET</text>')
    rows.append(f'<text x="{x + 18}" y="{y + 266}" fill="{DIM}" font-size="21">SPREAD</text>')
    rows.append(f'<text x="{x + 18}" y="{y + 307}" fill="{TEXT}" font-size="31" font-weight="800">{esc(ours_spread)}</text>')
    spread_price = priced_text(card, 'spread')
    spread_price = ('LIKE: ' if watch_market == 'spread' else '') + spread_price
    rows.append(f'<text x="{x + w - 18}" y="{y + 307}" fill="{spread_tone}" font-size="23" font-weight="800" text-anchor="end">'
                f'{esc(spread_price if spread_price != "-" else line_spread)}</text>')
    total = v2.get('total')
    rows.append(f'<text x="{x + 18}" y="{y + 365}" fill="{DIM}" font-size="21">TOTAL</text>')
    rows.append(f'<text x="{x + 18}" y="{y + 406}" fill="{TEXT}" font-size="31" font-weight="800">'
                f'{esc(f"{total:.1f}" if isinstance(total, (int, float)) else "-")}</text>')
    total_price = priced_text(card, 'total')
    total_price = ('LIKE: ' if watch_market == 'total' else '') + total_price
    rows.append(f'<text x="{x + w - 18}" y="{y + 406}" fill="{total_tone}" font-size="23" font-weight="800" text-anchor="end">'
                f'{esc(total_price if total_price != "-" else pricing_fmt(market["total"]))}</text>')
    rows.append(f'<text x="{x + 18}" y="{y + h - 22}" fill="{DIM}" font-size="18">Left: model · Right: market</text>')
    ring = ACCENT if watch else LINE
    rank, market_name, bet_label, value = watch if watch else (None, None, None, None)
    badge = ([f'<circle cx="{x + w - 24}" cy="{y + 24}" r="16" fill="{ACCENT}"/>',
              f'<text x="{x + w - 24}" y="{y + 30}" fill="{BG}" font-size="16" font-weight="900" text-anchor="middle">{rank}</text>']
             if watch else [])
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{CARD}" stroke="{ring}" stroke-width="{4 if watch else 2}"/>'] + badge + rows


def compact_card_svg(card, x, y, w, h, logos, watch=None):
    """One complete matchup tile for a saveable full-slate sheet."""
    v2, market, lean = card['v2'], card.get('market') or {}, card.get('lean') or {}
    esc = pick_card.esc
    home_chance = v2.get('winProb')
    rows = []
    for i, side in enumerate(('away', 'home')):
        team = card[side]
        top = y + 10 + 35 * i
        chance = None if home_chance is None else (home_chance if side == 'home' else 1 - home_chance)
        uri = logos.get((card['id'], side))
        rows.append(f'<image href="{uri}" x="{x + 14}" y="{top}" width="28" height="28" preserveAspectRatio="xMidYMid meet"/>' if uri else
                    f'<circle cx="{x + 28}" cy="{top + 14}" r="13" fill="{readable(team)}"/>')
        rows.append(f'<text x="{x + 51}" y="{top + 23}" fill="{TEXT}" font-size="23" font-weight="800">{esc(team.get("abbr") or "")}</text>')
        points = v2.get(side)
        rows.append(f'<text x="{x + 218}" y="{top + 24}" fill="{TEXT}" font-size="26" font-weight="800" text-anchor="end">'
                    f'{esc(f"{points:.1f}" if isinstance(points, (int, float)) else "-")}</text>')
        if chance is not None:
            bar = max(3, round(104 * chance))
            rows.append(f'<rect x="{x + 232}" y="{top + 7}" width="104" height="15" rx="8" fill="{LINE}"/>')
            rows.append(f'<rect x="{x + 232}" y="{top + 7}" width="{bar}" height="15" rx="8" fill="{readable(team)}"/>')
            rows.append(f'<text x="{x + w - (46 if watch else 14)}" y="{top + 21}" fill="{TEXT}" font-size="17" font-weight="750" text-anchor="end">{round(100 * chance)}%</text>')
    ours_spread = spread_text(card, v2.get('margin'))
    total = v2.get('total')
    total_text = f'{total:.1f}' if isinstance(total, (int, float)) else '-'
    watch_market = watch[1] if watch else None
    spread_tone = ACCENT if watch_market == 'spread' else DIM
    total_tone = ACCENT if watch_market == 'total' else DIM
    spread_price, total_price = priced_text(card, 'spread'), priced_text(card, 'total')
    spread_price = ('LIKE: ' if watch_market == 'spread' else '') + spread_price
    total_price = ('LIKE: ' if watch_market == 'total' else '') + total_price
    rows += [f'<line x1="{x + 14}" y1="{y + h - 45}" x2="{x + w - 14}" y2="{y + h - 45}" stroke="{LINE}"/>',
             f'<text x="{x + 14}" y="{y + h - 27}" fill="{DIM}" font-size="12">SPREAD <tspan fill="{TEXT}" font-weight="800">{esc(ours_spread)}</tspan> · <tspan fill="{spread_tone}" font-weight="800">{esc(spread_price)}</tspan></text>',
             f'<text x="{x + 14}" y="{y + h - 9}" fill="{DIM}" font-size="12">TOTAL <tspan fill="{TEXT}" font-weight="800">{esc(total_text)}</tspan> · <tspan fill="{total_tone}" font-weight="800">{esc(total_price)}</tspan></text>']
    ring = ACCENT if watch else LINE
    rank, market_name, bet_label, value = watch if watch else (None, None, None, None)
    badge = ([f'<circle cx="{x + w - 23}" cy="{y + 22}" r="15" fill="{ACCENT}"/>',
              f'<text x="{x + w - 23}" y="{y + 27}" fill="{BG}" font-size="14" font-weight="900" text-anchor="middle">{rank}</text>']
             if watch else [])
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="15" fill="{CARD}" stroke="{ring}" stroke-width="{4 if watch else 2}"/>'] + badge + rows


def svg(games, league, day, week=None, logos=None):
    """The sheet: a header with the ask, two columns of game cards, the house line at the foot."""
    esc = pick_card.esc
    logos = logos or {}
    rows = (len(games) + 1) // 2
    top, foot, gap = 196, 96, 12
    pitch = (HEIGHT - top - foot) / max(rows, 1)
    h = min(480, pitch - gap)
    w = (WIDTH - 72 - 20) // 2
    title = f"WEEK {week} {WORDS[league]} PROJECTIONS" if week else f"{WORDS[league]} PROJECTIONS"
    when = f"{day:%A, %B} {day.day}"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
             f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif">',
             f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>',
             f'<rect width="{WIDTH}" height="8" fill="{ACCENT}"/>',
             f'<circle cx="46" cy="62" r="9" fill="{ACCENT}"/>',
             f'<text x="64" y="71" fill="{ACCENT}" font-size="26" font-weight="800" letter-spacing="5">SAVE THIS</text>',
             f'<text x="{WIDTH - 36}" y="71" fill="{DIM}" font-size="24" font-weight="700" letter-spacing="4" text-anchor="end">KOOK’N</text>',
             f'<text x="36" y="132" fill="{TEXT}" font-size="54" font-weight="800">{esc(title)}</text>',
             f'<text x="36" y="172" fill="{DIM}" font-size="22">{esc(when)} · rings name the lines we like · not picks</text>']
    watch = watches(games)
    for i, card in enumerate(games):
        col, row = i % 2, i // 2
        drawer = compact_card_svg if len(games) > 4 else card_svg
        parts += drawer(card, 36 + col * (w + 20), round(top + row * pitch), w, round(h), logos, watch.get(card['id']))
    parts += [f'<text x="36" y="{HEIGHT - 52}" fill="{TEXT}" font-size="22" font-weight="700">Graded in public, win or lose. '
              f'<tspan fill="{DIM}" font-weight="400">keenroudy.com/sports</tspan></text>',
              f'<text x="36" y="{HEIGHT - 22}" fill="{DIM}" font-size="17">Not picks: our plays go out on their own. '
              f'Mint: the labeled line clears its captured price. Entertainment only.</text>',
              '</svg>']
    output = '\n'.join(parts)
    if pick_card.felt_enabled({'day': day}, day):
        import felt_cards
        for old, new in ((BG, felt_cards.FELT_NIGHT), (CARD, felt_cards.FELT_RAISED),
                         (LINE, felt_cards.LINE), (TEXT, felt_cards.CHALK),
                         (DIM, felt_cards.DIM), (ACCENT, felt_cards.KOOKD)):
            output = output.replace(old, new)
        output = output.replace('font-family="Helvetica Neue, Helvetica, Arial, sans-serif"',
                                'font-family="DM Sans, Arial, sans-serif"')
        output = output.replace('>', '>' + felt_cards.font_face(), 1)
    return output


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
    (gameId -> game), so the desk can schedule it without the site's files."""
    day = eastern_date(now)
    for league in DAYS:
        if not sheet_day(league, day) or now >= at(day, POST_UNTIL):
            continue
        todays = [g for g in games.values() if g.get('league') == league and eastern_date(gates.when(g['kickoff'])) == day]
        if len(todays) < FEWEST:
            continue
        name = 'college' if league == 'CFB' else 'NFL'
        lead = (f"📌 Full {name} projections for the slate." if league == 'NFL' else
                f"📌 16 {name} projections for the slate.")
        text = lead + "\nMint rings name up to 4 lines we like at the listed price (not official plays). Save this one." + f"\n#{league}"
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
