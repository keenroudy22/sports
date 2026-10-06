"""One evidence-first research graphic per football slate.

This is editorial packaging, never candidate selection. It reads the same built
page payloads visitors see and refuses stale prices. The public priority is:
fresh outright underdogs, priced underdog spreads, fresh main-line season trends,
exact-line matchup history, then observed end-zone work. A missing view produces
no post; nothing is invented to fill a calendar.
"""
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gates
import pick_card
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
TODAY = ROOT / 'site' / 'data' / 'app' / 'today.json'
LINES = ROOT / 'site' / 'data' / 'app' / 'lines.json'
DETAILS = ROOT / 'site' / 'data' / 'app' / 'games'
PUBLIC_BOOKS = {'DraftKings', 'FanDuel', 'BetMGM', 'ESPN BET', 'Caesars', 'BetRivers', 'Fanatics'}
POST_AT, POST_UNTIL = (10, 30), (14, 0)
WIDTH, HEIGHT = 1080, 1350
BG, PANEL, LINE = '#071018', '#102330', '#294657'
TEXT, DIM, MINT, CYAN, VIOLET = '#f5faff', '#a7c1cf', '#5eeaa4', '#6adfff', '#c2a2ff'


def when(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def load(path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return fallback


def details_for(cards, root=DETAILS):
    return {card['id']: load(Path(root) / f"{card['id']}.json", {}) for card in cards}


def current(value, now, age):
    seen = when(value)
    return bool(seen and timedelta(0) <= now - seen <= age)


def game_day(game):
    start = when(game.get('kickoff'))
    return eastern_date(start) if start else None


def slate_games(data, now):
    day = eastern_date(now)
    return [g for g in data.get('games') or [] if game_day(g) == day and g.get('state') == 'pre'
            and when(g.get('kickoff')) and when(g['kickoff']) > now]


def price(odds):
    return f'{int(odds):+d}' if isinstance(odds, (int, float)) else 'price unavailable'


def book_short(book):
    return {'DraftKings': 'DK', 'FanDuel': 'FD', 'BetMGM': 'MGM', 'ESPN BET': 'ESPN',
            'Caesars': 'CZR', 'BetRivers': 'BR', 'Fanatics': 'FAN'}.get(book, str(book or ''))


def tags(rows):
    leagues = {row.get('league') for row in rows}
    return ' '.join(f'#{league}' for league in ('CFB', 'NFL') if league in leagues)


def upset_candidate(games, now):
    rows = []
    for game in games:
        watch = game.get('upsetWatch') or {}
        if not watch or not current(watch.get('observedAt'), now, timedelta(hours=4)):
            continue
        if not all(isinstance(watch.get(key), (int, float)) for key in ('odds', 'opponentOdds', 'modelChance', 'marketChanceNoVig')):
            continue
        side = watch.get('side')
        team = game.get(side) or {}
        opponent = game.get('away' if side == 'home' else 'home') or {}
        projected_for, projected_against = watch.get('projectedFor'), watch.get('projectedAgainst')
        score = f"Our score {team.get('abbr') or team.get('name')} {projected_for:g}–{projected_against:g} {opponent.get('abbr') or opponent.get('name')}" \
            if isinstance(projected_for, (int, float)) and isinstance(projected_against, (int, float)) else \
            f"Model {round(100 * watch['modelChance'])}% | market {round(100 * watch['marketChanceNoVig'])}%"
        gap = watch.get('spreadGap')
        comparison = f"Model {round(100 * watch['modelChance'])}% | market {round(100 * watch['marketChanceNoVig'])}%"
        if isinstance(gap, (int, float)):
            comparison += f" | {gap:g}-pt gap vs spread"
        rows.append({'league': game.get('league'), 'gameId': game['id'], 'kickoff': game['kickoff'],
                     'title': watch.get('team') or team.get('name'), 'team': team, 'opponent': opponent,
                     'price': price(watch['odds']) + ' ML', 'book': watch.get('book'),
                     'metric': score, 'detail': comparison,
                     'copyMetric': f"Model {round(100 * watch['modelChance'])}% | market {round(100 * watch['marketChanceNoVig'])}%",
                     'reason': ((watch.get('reasons') or [None])[-1]),
                     'score': watch['modelChance'] - watch['marketChanceNoVig'], 'observedAt': watch['observedAt']})
    rows.sort(key=lambda row: (-row['score'], row['kickoff'], row['gameId']))
    if not rows:
        return None
    shown = rows[:3]
    lines = [f"{row['title']} {row['price']} ({book_short(row['book'])}) | {row['copyMetric'].lower()}" for row in shown]
    return {'kind': 'upset', 'title': 'UNDERDOG WATCH', 'kicker': 'OUTRIGHT WINNERS', 'accent': MINT,
            'rows': shown, 'text': '\n'.join(['🐕 UNDERDOG WATCH', 'Our raw model sees these outright underdogs differently:',
                                             *lines, '', 'Research only, not official plays. Check current prices.', tags(shown)])}


def spread_dog_candidate(games, lines, now):
    cards = {game['id']: game for game in games}
    rows = []
    for line in lines or []:
        grade = line.get('grade') or {}
        if line.get('gameId') not in cards or not line.get('gameMarket') or line.get('market') != 'point spread' \
                or line.get('state') != 'open' or not isinstance(line.get('line'), (int, float)) or line['line'] <= 0 \
                or grade.get('tier') not in ('lean', 'strong') or grade.get('thin') \
                or line.get('book') not in PUBLIC_BOOKS or not current(line.get('observedAt'), now, timedelta(hours=12)):
            continue
        game = cards[line['gameId']]
        side = line.get('side')
        team = game.get(side) or {}
        opponent = game.get('away' if side == 'home' else 'home') or {}
        chance, needs = grade.get('chance'), grade.get('needs')
        if not isinstance(chance, (int, float)) or not isinstance(needs, (int, float)):
            continue
        projection = grade.get('projection')
        model_line = -projection if side == 'home' and isinstance(projection, (int, float)) else projection
        detail = f"vs {opponent.get('name') or opponent.get('abbr')}"
        if isinstance(model_line, (int, float)):
            detail += f" | our spread {team.get('abbr') or team.get('name')} {model_line:+g}"
        rows.append({'league': game.get('league'), 'gameId': game['id'], 'kickoff': game['kickoff'],
                     'title': team.get('name') or team.get('abbr'), 'team': team, 'opponent': opponent,
                     'price': f"{line['line']:+g} ({price(line.get('odds'))})",
                     'book': line.get('book'), 'metric': f"Model {round(100 * chance)}% | price needs {round(100 * needs)}%",
                     'detail': detail, 'score': grade.get('edge') or 0, 'observedAt': line.get('observedAt')})
    rows.sort(key=lambda row: (-row['score'], row['kickoff'], row['gameId']))
    if not rows:
        return None
    shown = rows[:3]
    copy = [f"{row['title']} {row['price']} {book_short(row['book'])} | {row['metric'].lower()}" for row in shown]
    return {'kind': 'spread-dog', 'title': 'UNDERDOG SPREAD WATCH', 'kicker': 'COVER VALUE · NOT OUTRIGHT', 'accent': CYAN,
            'rows': shown, 'text': '\n'.join(['🐕 UNDERDOG SPREAD WATCH', 'These dogs grade as cover value at current prices:',
                                             *copy, '', 'Cover research, not an upset call or official play. Check current prices.', tags(shown)])}


def matchup_candidate(games, details, now):
    rows = []
    for game in games:
        for line in (details.get(game['id']) or {}).get('favoriteLines') or []:
            history = (line.get('history') or {}).get('last') or {}
            if history.get('games', 0) < 5 or history.get('rate', 0) < 80 \
                    or not current(line.get('observedAt'), now, timedelta(hours=12)) \
                    or line.get('book') not in PUBLIC_BOOKS:
                continue
            rows.append({'league': game.get('league'), 'gameId': game['id'], 'kickoff': game['kickoff'],
                         'title': line.get('title'), 'team': None, 'athleteId': line.get('athleteId'),
                         'price': f"{price(line.get('odds'))} {book_short(line.get('book'))}",
                         'book': line.get('book'), 'metric': f"{history['hits']}/{history['games']} last games",
                         'detail': f"Projection {line.get('projection'):g} | exact main line",
                         'hits': history['hits'], 'games': history['games'], 'pushes': history.get('pushes', 0),
                         'score': (history.get('rate', 0), line.get('edge') or 0), 'observedAt': line.get('observedAt')})
    rows.sort(key=lambda row: (-row['score'][0], -row['score'][1], row['title']))
    if not rows:
        return None
    shown = rows[:4]
    lines = [f"{row['title']} | {row['metric']} | {row['price']}" for row in shown]
    return {'kind': 'matchup', 'title': 'MATCHUP MENU', 'kicker': 'EXACT-LINE HISTORY', 'accent': CYAN,
            'rows': shown, 'text': '\n'.join(['📊 MATCHUP MENU', "Historical results at today's exact main lines:",
                                             *lines, '', 'History does not predict the next game. Research, not official plays. Save this.', tags(shown)])}


def scorer_candidate(games, details, now):
    rows = []
    for game in games:
        for player in (details.get(game['id']) or {}).get('scorerResearch') or []:
            if not current(player.get('roleSnapshotAt'), now, timedelta(days=7)) or player.get('games', 0) < 3:
                continue
            rows.append({'league': game.get('league'), 'gameId': game['id'], 'kickoff': game['kickoff'],
                         'title': player.get('player'), 'team': None, 'athleteId': player.get('athleteId'),
                         'price': f"{player.get('inside10', 0)} inside the 10", 'book': None,
                         'metric': f"{player.get('redZone', 0)} red-zone opportunities",
                         'detail': f"{player.get('touchdowns', 0)} rush/rec TDs | {player.get('games')}/{player.get('teamGames')} games observed",
                         'score': (player.get('inside10', 0) / player['games'], player.get('redZone', 0) / player['games']),
                         'observedAt': player.get('roleSnapshotAt')})
    rows.sort(key=lambda row: (-row['score'][0], -row['score'][1], row['title']))
    if not rows:
        return None
    shown = rows[:4]
    lines = [f"{row['title']} | {row['metric']} | {row['price']}" for row in shown]
    return {'kind': 'end-zone', 'title': 'END-ZONE WORK', 'kicker': 'SCORING-AREA OPPORTUNITY', 'accent': VIOLET,
            'rows': shown, 'text': '\n'.join(['🎯 END-ZONE WORK', 'Players seeing the most scoring-area work:',
                                             *lines, '', 'Opportunity, not TD probability or an official play.', tags(shown)])}


def season_candidate(games, details, now):
    rows = []
    for game in games:
        for row in (details.get(game['id']) or {}).get('seasonTrends') or []:
            if (row.get('kind') != 'main' or row.get('games', 0) < 5
                    or row.get('injuryStatus')
                    or row.get('hits', 0) * 100 < row['games'] * 80 or row.get('book') not in PUBLIC_BOOKS
                    or not current(row.get('observedAt'), now, timedelta(hours=4))):
                continue
            rows.append(row)
    unique = []
    used = set()
    for row in sorted(rows, key=lambda r: (-r['hits'] / r['games'], -r['games'], r['player'])):
        key = (row['league'], row['athleteId'])
        if key not in used:
            unique.append(row)
            used.add(key)
        if len(unique) == 3:
            break
    if not unique:
        return None
    floor = min(100 * r['hits'] / r['games'] for r in unique)
    bucket = 100 if floor == 100 else 90 if floor >= 90 else 80
    bucket_label = '100%' if bucket == 100 else f'{bucket}%+'
    shown = [{**r, 'title': r['player'], 'price': r['title'],
              'metric': f"{r['hits']}/{r['games']} this season · {r['rate']:g}% historical",
              'detail': f"{price(r['odds'])} {r['book']} · {r['season']} regular season"} for r in unique]
    return {'kind': 'season', 'title': f'{bucket_label} TREND BOARD', 'kicker': 'CURRENT MAIN LINES · FULL-SEASON HISTORY',
            'accent': CYAN, 'rows': shown,
            'text': '\n'.join([f'📈 KOOK\'N {bucket_label} TREND BOARD',
                               *[f"{r['player']} · {r['title']} · {r['hits']}/{r['games']}" for r in unique],
                               'Fresh main lines on the graphic.', 'History, not a prediction or official play. Check current prices.',
                               'keenroudy.com/sports/#trends', tags(unique)])}


def already_posted(log_book, day):
    posts = log_book.get('posts') or []
    keys = posts if isinstance(posts, dict) else (row.get('id', '') for row in posts)
    return any(part.startswith('research:') and part.endswith(day.isoformat())
               for key in keys for part in str(key).split('+'))


def bounded_caption(choice):
    """Keep exact evidence on the attached graphic; shorten copy without truncating a fact.

    Existing short captions are unchanged. A long sheet gets whole, exact preview
    rows that fit plus a family-specific research caution. No row on the graphic,
    eligibility rule, category or posting limit changes.
    """
    from x_post import LIMIT, tweet_length
    original = choice['text']
    if tweet_length(original) <= LIMIT:
        return original
    families = {
        'upset': ('UNDERDOG WATCH', 'Raw-model research, not official plays. Check current prices.'),
        'spread-dog': ('UNDERDOG SPREAD WATCH', 'Cover research, not an upset call or official play. Check current prices.'),
        'matchup': ('MATCHUP MENU', 'History, not a prediction or official play. Check current prices.'),
        'season': (choice['title'], 'History, not a prediction or official play. Check current prices.'),
        'end-zone': ('END-ZONE WORK', 'Opportunity, not TD probability or an official play.'),
    }
    heading, caution = families[choice['kind']]
    # Season's title contains a computed bucket, not provider-controlled prose.
    if tweet_length(heading) > 60:
        heading = 'KOOK\'N RESEARCH'
    footer = '\n'.join(['Full details and samples on the graphic.', caution, tags(choice['rows'])])
    preview = []
    for row in choice['rows']:
        fields = [str(row['title']), str(row['price'])]
        if choice['kind'] in ('matchup', 'season'):
            fields.append(str(row['metric']))
        elif choice['kind'] in ('upset', 'spread-dog'):
            fields.append(book_short(row['book']))
        exact = ' | '.join(fields)
        proposed = '\n'.join([heading, *preview, exact, '', footer])
        if tweet_length(proposed) <= LIMIT:
            preview.append(exact)
    return '\n'.join([heading, *preview, '', footer])


def select(data, details, now, lines=None):
    games = slate_games(data, now)
    if not games:
        return None
    season = season_candidate(games, details, now)
    # Alternate days share the existing editorial slot; never add another daily post.
    chosen = (season if eastern_date(now).day % 2 == 0 else None) or (
        upset_candidate(games, now) or spread_dog_candidate(games, lines, now)
        or matchup_candidate(games, details, now) or season or scorer_candidate(games, details, now))
    if not chosen:
        return None
    day = eastern_date(now)
    chosen.update(day=day, key=f"research-{chosen['kind']}-{day.isoformat()}",
                  firstKickoff=min(when(row['kickoff']) for row in chosen['rows']))
    chosen['text'] = bounded_caption(chosen)
    return chosen


def at(day, hm):
    return datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)


def post(games, now, data_path=TODAY, detail_root=DETAILS, lines_path=LINES):
    data = load(data_path, {'games': []})
    choice = select(data, details_for(data.get('games') or [], detail_root), now,
                    (load(lines_path, {'lines': []}) or {}).get('lines') or [])
    if not choice:
        return None
    stale = min(at(choice['day'], POST_UNTIL), choice['firstKickoff'] - timedelta(minutes=45))
    if choice['kind'] == 'season':
        stale = min(stale, *(when(r['observedAt']) + timedelta(hours=4) for r in choice['rows']))
    if now >= stale:
        return None
    return {'key': f"research:{choice['kind']}:{choice['day'].isoformat()}", 'kind': 'research',
            'card': choice['key'], 'text': choice['text'],
            'due': max(at(choice['day'], POST_AT), now + timedelta(minutes=2)), 'stale': stale}


def art_for(row, game, fetch):
    if row.get('athleteId'):
        league = row.get('league')
        url = pick_card.HEADSHOT.format(sport='nfl' if league == 'NFL' else 'college-football', athlete=row['athleteId'])
    else:
        team = dict(row.get('team') or {})
        team.setdefault('abbreviation', team.get('abbr'))
        url = pick_card.logo_url(team, row.get('league'))
    return fetch(url) if url else None


def svg(choice, art=None):
    import research_art
    return research_art.svg(choice, art)


def legacy_svg(choice, art=None):
    esc = lambda value: html.escape(str(value or ''))
    accent = choice['accent']
    rows, art = choice['rows'], art or {}
    top = 300
    gap = 18
    row_h = int((870 - gap * (len(rows) - 1)) / max(1, len(rows)))
    blocks = []
    for index, row in enumerate(rows):
        y = top + index * (row_h + gap)
        uri = art.get(index)
        image_size = min(300, row_h - 24)
        image_x = 1010 - image_size
        image_y = y + (row_h - image_size) / 2
        image = (f'<image href="{uri}" x="{image_x}" y="{image_y}" width="{image_size}" height="{image_size}" '
                 'preserveAspectRatio="xMidYMid meet"/>') if uri else ''
        title_size = max(26, min(34, int(650 / max(1, .56 * len(str(row['title']))))))
        title_y, price_y, metric_y, detail_y = ((45, 98, 140, 178) if row_h < 230 else (64, 130, 178, 216))
        blocks += [f'<rect x="44" y="{y}" width="992" height="{row_h}" rx="24" fill="{PANEL}" stroke="{LINE}" stroke-width="2"/>',
                   f'<rect x="44" y="{y}" width="7" height="{row_h}" rx="4" fill="{accent}"/>',
                   f'<text x="80" y="{y + title_y}" fill="{TEXT}" font-size="{title_size}" font-weight="850">{esc(row["title"])}</text>',
                   f'<text x="80" y="{y + price_y}" fill="{accent}" font-size="43" font-weight="900">{esc(row["price"])}</text>',
                   f'<text x="80" y="{y + metric_y}" fill="{TEXT}" font-size="25" font-weight="700">{esc(row["metric"])}</text>',
                   f'<text x="80" y="{y + detail_y}" fill="{DIM}" font-size="21">{esc(row["detail"])}</text>', image]
    footer = 1230
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset=".72" stop-color="#0a1926"/><stop offset="1" stop-color="#102f3a"/></linearGradient></defs>
<rect width="1080" height="1350" fill="url(#bg)"/><rect x="0" y="0" width="1080" height="10" fill="{accent}"/>
<circle cx="62" cy="74" r="14" fill="none" stroke="{accent}" stroke-width="5"/><circle cx="62" cy="74" r="5" fill="{accent}"/><path d="M76 74h28" stroke="{accent}" stroke-width="5" stroke-linecap="round"/>
<text x="118" y="92" fill="{TEXT}" font-size="35" font-weight="850" letter-spacing="5">KOOK’N</text>
<text x="1032" y="89" text-anchor="end" fill="{DIM}" font-size="20" font-weight="750" letter-spacing="3">RESEARCH · NOT A PLAY</text>
<text x="44" y="165" fill="{accent}" font-size="22" font-weight="850" letter-spacing="4">{esc(choice['kicker'])}</text>
<text x="44" y="247" fill="{TEXT}" font-size="67" font-weight="950">{esc(choice['title'])}</text>
{''.join(blocks)}
<text x="44" y="{footer}" fill="{TEXT}" font-size="25" font-weight="800">THE PRICE AND THE UNCERTAINTY BOTH MATTER.</text>
<text x="44" y="{footer + 42}" fill="{accent}" font-size="24" font-weight="750">keenroudy.com/sports</text>
<text x="1036" y="{footer + 42}" text-anchor="end" fill="{DIM}" font-size="19">Entertainment only. Check current prices.</text>
</svg>'''


def render_due(now, folder, data_path=TODAY, detail_root=DETAILS, lines_path=LINES, fetch=None, log=print):
    data = load(data_path, {'games': []})
    choice = select(data, details_for(data.get('games') or [], detail_root), now,
                    (load(lines_path, {'lines': []}) or {}).get('lines') or [])
    if not choice:
        return {}
    fetch = fetch or pick_card.fetch_data_uri
    games = {g['id']: g for g in data.get('games') or []}
    images = {i: art_for(row, games.get(row['gameId']) or {}, fetch) for i, row in enumerate(choice['rows'])}
    path = Path(folder) / f"{choice['key']}.png"
    try:
        pick_card.render(svg(choice, images), path)
    except Exception as error:
        log(f"research card {choice['key']} not drawn: {error}")
        return {}
    return {choice['key']: path}
