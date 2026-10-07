"""Wednesday-night, next-day TNF research from the public, priced main-line board.

This is not official-play selection. It consumes already-built public payloads,
never requests a new price, and refuses thin, stale, uncalibrated or held rows.
"""
from datetime import datetime, timedelta

import gates
import role_sanity

PUBLIC_BOOKS = {'DraftKings', 'FanDuel', 'BetMGM', 'ESPN BET', 'theScore Bet',
                'Caesars', 'BetRivers', 'Fanatics'}
MAX_AGE = timedelta(hours=4)
# The owner approved the category, but the first real cards still need Claude's review.
# Keep delivery off until that review and a separate gated release.
ENABLED = False


def _when(value):
    try:
        instant = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return instant if instant.tzinfo else None
    except (TypeError, ValueError):
        return None


def target(now):
    """Wednesday 7 PM Eastern; no late catch-up post."""
    local = now.astimezone(gates.EASTERN)
    if local.weekday() != 2:
        return None
    return local.replace(hour=19, minute=0, second=0, microsecond=0)


def game_for(data, now):
    due = target(now)
    if due is None or now >= due + timedelta(minutes=10):
        return None
    tomorrow = due.date() + timedelta(days=1)
    options = [game for game in data.get('games') or []
               if game.get('league') == 'NFL' and game.get('state') == 'pre'
               and _when(game.get('kickoff'))
               and _when(game['kickoff']).astimezone(gates.EASTERN).date() == tomorrow
               and _when(game['kickoff']).astimezone(gates.EASTERN).hour >= 19]
    return min(options, key=lambda game: game['kickoff']) if options else None


def qualified(row, game, due):
    if row.get('gameId') != game['id'] or row.get('state') != 'open' or row.get('league') != 'NFL':
        return False
    if row.get('marketWindow') != 'Full game' or row.get('book') not in PUBLIC_BOOKS:
        return False
    if type(row.get('odds')) not in (int, float) or type(row.get('line')) not in (int, float):
        return False
    observed = _when(row.get('observedAt'))
    if not observed or not timedelta(0) <= due - observed <= MAX_AGE:
        return False
    grade = row.get('grade')
    if not isinstance(grade, dict):
        return False
    if not grade.get('calibrated') or grade.get('thin') or grade.get('limited') \
            or grade.get('tier') != 'pass' or row.get('roleSuspect') or row.get('underReview') \
            or row.get('priceSuspect') or row.get('gradeNote'):
        return False
    chance, needs, edge = (grade.get(key) for key in ('chance', 'needs', 'edge'))
    if not all(type(value) in (int, float) for value in (chance, needs, edge)) \
            or not (0 < chance < 1 and 0 < needs < 1) or edge <= 0:
        return False
    snapshot = _when(grade.get('snapshotAt'))
    if not snapshot or not timedelta(0) <= due - snapshot <= MAX_AGE:
        return False
    return not role_sanity.price_suspect(row['odds'], chance, player=bool(row.get('athleteId')))


def select(data, lines, now):
    """Up to four positive-value main lines; fewer than two means no post."""
    game = game_for(data, now)
    due = target(now)
    if not game or not due:
        return None
    eligible = [row for row in lines if qualified(row, game, due)]
    eligible.sort(key=lambda row: (-row['grade']['edge'], str(row.get('id') or '')))
    rows = eligible[:4]
    if len(rows) < 2:
        return None
    return {'game': game, 'rows': rows, 'due': due, 'stale': due + timedelta(minutes=10),
            'researchDay': due.date() + timedelta(days=1),
            'key': f"research:tnf-early:{(due.date() + timedelta(days=1)).isoformat()}"}


def caption(choice):
    """Short, factual X copy; the card carries chance and break-even."""
    from x_post import LIMIT, tweet_length
    game = choice['game']
    away = (game.get('away') or {}).get('name') or (game.get('away') or {}).get('abbr') or 'Away'
    home = (game.get('home') or {}).get('name') or (game.get('home') or {}).get('abbr') or 'Home'
    row = choice['rows'][0]
    odds = f"{int(row['odds']):+d}"
    text = (f"👀 TNF Early Look: {away} at {home}\n"
            f"{row['title']} ({odds}, {row['book']})\n"
            f"{len(choice['rows']) - 1} more on the card. Best bets drop tomorrow. #NFL")
    return text if tweet_length(text) <= LIMIT else None


def _art(row, game, fetch):
    import pick_card
    if row.get('athleteId'):
        url = pick_card.HEADSHOT.format(sport='nfl', athlete=row['athleteId'])
        return fetch(url) or fetch(url)
    return None


def _logo(team, fetch):
    import pick_card
    url = pick_card.logo_url({'abbreviation': team.get('abbr') or team.get('abbreviation')}, 'NFL')
    return fetch(url) if url else None


def _row_title(row, game):
    if row.get('player'):
        short = {'receptions': 'RECS', 'receiving yards': 'REC YDS', 'rushing yards': 'RUSH YDS',
                 'passing yards': 'PASS YDS', 'pass attempts': 'PASS ATT', 'completions': 'COMPLETIONS',
                 'carries': 'CARRIES', 'targets': 'TARGETS'}
        market = short.get(str(row.get('market') or '').lower(), str(row.get('market') or '').upper())
        return f"{row['player']} {str(row.get('direction') or '').upper()} {row['line']:g} {market}".upper()
    title = str(row.get('title') or '').upper()
    away = (game.get('away') or {}).get('abbr') or ''
    home = (game.get('home') or {}).get('abbr') or ''
    return title.replace(f'{away} @ {home}'.upper(), f'{away} @ {home}'.upper())


def list_card(choice, fetch=None):
    """The reviewed Kitchen Ticket layout, filled only with qualified live rows."""
    import pick_card
    import ticket_cards
    import ticket_kit as kit
    fetch = fetch or pick_card.fetch_data_uri
    game, rows = choice['game'], choice['rows']
    card = kit.Card()
    panel_bottom, top, row_h = 450, 550, 140
    perf, bottom = 1138, 1230
    inner = kit.panel_rect(card, kit.PANEL_TOP, panel_bottom, hot=(760, 300))
    chip, _ = kit.series_chip(card, kit.COL_X, 204, 'TNF EARLY LOOK')
    inner += chip
    matchup = f"{(game.get('away') or {}).get('abbr') or 'AWAY'} AT {(game.get('home') or {}).get('abbr') or 'HOME'}".upper()
    inner += card.text(kit.COL_X, 352, matchup, kit.fit(matchup, 106, 590, floor=72), kit.CHALK)
    kickoff = _when(game['kickoff']).astimezone(gates.EASTERN)
    inner += card.text(kit.COL_X, 420, kickoff.strftime('THU %-I:%M %p ET · RESEARCH'), 40, kit.CHALK)
    for x, side in ((750, 'away'), (905, 'home')):
        team = game.get(side) or {}
        logo = _logo(team, fetch)
        inner += (kit.logo_disc(card, logo, x, 310, 58) if logo else
                  kit.initials_badge(card, x, 310, 58, team.get('abbr') or side[:3].upper(), team.get('color') or kit.CHARCOAL[0]))
    inner += card.text(kit.X1, 522, 'THE LINE', 40, kit.INK_SOFT, tracking=1)
    inner += card.text(kit.X2, 522, 'I HAVE IT', 40, kit.INK_SOFT, anchor='end', tracking=1)
    inner += kit.dashed(kit.X1, kit.X2, 535)
    for index, row in enumerate(rows):
        y = top + index * row_h
        if index:
            inner += f'<line x1="{kit.X1}" y1="{y}" x2="{kit.X2}" y2="{y}" stroke="{kit.RULE}" stroke-width="2"/>'
        photo = _art(row, game, fetch)
        color = row.get('color') or kit.CHARCOAL[0]
        inner += (kit.face_thumb(card, photo, 157, y + 69, 34) if photo else
                  kit.initials_badge(card, 157, y + 69, 34,
                                     kit.initials(row.get('player') or (game.get('away') or {}).get('abbr') or ''), color))
        title = _row_title(row, game)
        lines = kit.wrap(title, 42, 600, max_lines=2)
        if not lines:
            raise ValueError(f"TNF Early Look line does not fit: {title}")
        for li, line in enumerate(lines):
            inner += card.text(207, y + 55 + li * 43, line, 42, kit.INK)
        chance = kit.pct1(row['grade']['chance'])
        inner += card.text(kit.X2, y + 61, chance, 56, kit.INK, anchor='end')
        detail = f"{kit.price(row['odds'])} {row['book']} · PRICE NEEDS {kit.pct1(row['grade']['needs'])}"
        inner += card.text(207, y + 125, detail, kit.fit(detail, 40, kit.X2 - 207, family='d', weight=600, floor=40),
                           kit.INK_SOFT, family='d', weight=600)
    observed = min(_when(row['observedAt']) for row in rows).astimezone(gates.EASTERN)
    label = f"LINES AS OF WED {observed.strftime('%-I:%M %p')} ET · PRICES MOVE"
    inner += card.text(kit.X1, 1190, label, kit.fit(label, 40, kit.X2 - kit.X1, floor=40), kit.INK_SOFT)
    ticket_cards.frame(card, kit.HOUSE, kit.CHALK, perf, bottom, inner)
    problems = kit.qa(card, 'TNF Early Look list')
    if problems:
        raise ValueError('; '.join(problems))
    return card


def spotlight_card(choice, fetch=None):
    """Single strongest research line, a different visual from an official-play card."""
    import pick_card
    import ticket_cards
    import ticket_kit as kit
    fetch = fetch or pick_card.fetch_data_uri
    game, row = choice['game'], choice['rows'][0]
    card = kit.Card()
    panel_bottom, perf, bottom = 610, 1170, 1230
    inner = kit.panel_rect(card, kit.PANEL_TOP, panel_bottom, hot=(790, 325))
    photo = _art(row, game, fetch)
    breakout = ''
    if photo:
        inside, breakout = kit.hero_photo(card, photo, kit.PANEL_TOP, panel_bottom, face_x=800, height=500)
        inner += inside
        inner += f'<rect x="{kit.PANEL_X1}" y="{kit.PANEL_TOP}" width="{kit.PANEL_X2-kit.PANEL_X1}" height="{panel_bottom-kit.PANEL_TOP}" rx="14" fill="url(#scrim)"/>'
    else:
        team = (game.get('away') or {}) if row.get('player') else (game.get('home') or {})
        logo = _logo(team, fetch)
        inner += (kit.logo_disc(card, logo, 800, 385, 115) if logo else
                  kit.initials_badge(card, 800, 385, 115, kit.initials(row.get('player') or team.get('abbr') or ''),
                                     row.get('color') or kit.CHARCOAL[0]))
    chip, _ = kit.series_chip(card, kit.COL_X, 204, 'TNF EARLY LOOK')
    inner += chip
    subject = (row.get('player') or
               f"{(game.get('away') or {}).get('abbr') or 'AWAY'} AT {(game.get('home') or {}).get('abbr') or 'HOME'}")
    name_lines = kit.wrap(subject.upper(), 88, 540, max_lines=2)
    if not name_lines:
        name_lines = kit.wrap(subject.upper(), 72, 540, max_lines=2)
    if not name_lines:
        raise ValueError('TNF Early Look subject does not fit')
    for index, line in enumerate(name_lines):
        inner += card.text(kit.COL_X, 365 + index * 87, line, 88 if len(name_lines) == 1 else 72, kit.CHALK)
    kickoff = _when(game['kickoff']).astimezone(gates.EASTERN)
    inner += card.text(kit.COL_X, 570, kickoff.strftime('THU %-I:%M %p ET · RESEARCH'), 40, kit.CHALK)
    selection = _row_title(row, game)
    if row.get('player'):
        selection = selection.removeprefix(str(row['player']).upper()).strip()
    sel_lines = kit.wrap(selection, 104, kit.X2 - kit.X1, max_lines=2)
    if not sel_lines:
        sel_lines = kit.wrap(selection, 84, kit.X2 - kit.X1, max_lines=2)
    if not sel_lines:
        raise ValueError('TNF Early Look wager does not fit')
    for index, line in enumerate(sel_lines):
        inner += card.text(kit.X1, 760 + index * 102, line, 104 if len(sel_lines) == 1 else 84, kit.INK)
    price = f"{kit.price(row['odds'])} {row['book'].upper()}"
    inner += card.text(kit.X1, 930, price, kit.fit(price, 76, kit.X2-kit.X1, floor=56), kit.INK)
    inner += kit.dashed(kit.X1, kit.X2, 960)
    chance = f"I HAVE IT AT {kit.pct1(row['grade']['chance'])} · PRICE NEEDS {kit.pct1(row['grade']['needs'])}"
    inner += card.text(kit.X1, 1030, chance, kit.fit(chance, 48, kit.X2-kit.X1, floor=40), kit.INK_SOFT)
    observed = _when(row['observedAt']).astimezone(gates.EASTERN)
    note = f"WED {observed.strftime('%-I:%M %p')} ET · RESEARCH · PRICES MOVE"
    inner += card.text(kit.X1, 1135, note, kit.fit(note, 42, kit.X2-kit.X1, floor=40), kit.INK_SOFT)
    ticket_cards.frame(card, kit.HOUSE, kit.CHALK, perf, bottom, inner, breakout)
    problems = kit.qa(card, 'TNF Early Look spotlight')
    if problems:
        raise ValueError('; '.join(problems))
    return card


def render(choice, folder, fetch=None):
    """Return the list graphic; the spotlight is review-only until separately selected."""
    from pathlib import Path
    import pick_card
    path = Path(folder) / f"tnf-early-look-{choice['researchDay'].isoformat()}.png"
    pick_card.render(list_card(choice, fetch).svg(), path)
    return path
