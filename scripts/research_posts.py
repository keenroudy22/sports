"""One evidence-first research graphic per football slate.

This is editorial packaging, never candidate selection. It reads the same built
page payloads visitors see and refuses stale prices. The public priority is:
fresh outright underdogs, priced underdog spreads, fresh main-line season trends,
exact-line trends supported by opponent defense, then observed end-zone work. A missing view produces
no post; nothing is invented to fill a calendar.
"""
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gates
import line_payload
import pick_card
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
TODAY = ROOT / 'site' / 'data' / 'app' / 'today.json'
LINES = ROOT / 'site' / 'data' / 'app' / 'lines.json'
DETAILS = ROOT / 'site' / 'data' / 'app' / 'games'
TEAMS = ROOT / 'site' / 'data' / 'app' / 'teams'
PUBLIC_BOOKS = {'DraftKings', 'FanDuel', 'BetMGM', 'ESPN BET', 'theScore Bet', 'Caesars', 'BetRivers', 'Fanatics'}
POST_AT, POST_UNTIL = (10, 30), (14, 0)
WIDTH, HEIGHT = 1080, 1350
BG, PANEL, LINE = '#071018', '#102330', '#294657'
TEXT, DIM, MINT, CYAN, VIOLET = '#f5faff', '#a7c1cf', '#5eeaa4', '#6adfff', '#c2a2ff'
POS_GROUP = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE'}
STAT_LABEL = {'passYds': 'pass yds', 'att': 'pass attempts', 'cmp': 'completions',
              'rushYds': 'rush yds', 'car': 'carries', 'recYds': 'rec yds',
              'rec': 'receptions', 'targets': 'targets'}


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


def load_lines(path):
    try:
        return line_payload.load(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return []


def details_for(cards, root=DETAILS):
    return {card['id']: load(Path(root) / f"{card['id']}.json", {}) for card in cards}


def teams_for(cards, root=TEAMS):
    root = Path(root)
    base = root.parent.resolve()

    def payload_for(league):
        payload = load(root / f'{league}.json', {})
        ref = payload.get('defenseFile') if isinstance(payload, dict) else None
        safe = re.sub(r'[^a-zA-Z0-9/_.-]|\.\.', '', str(ref or ''))
        if not safe:
            return payload
        candidate = (base / safe).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            return payload
        split = load(candidate, {})
        if isinstance(split.get('defense'), dict):
            payload = {**payload, 'defense': split['defense']}
        return payload

    return {league: payload_for(league)
            for league in {card.get('league') for card in cards if card.get('league')}}


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
    return {'DraftKings': 'DK', 'FanDuel': 'FD', 'BetMGM': 'MGM', 'ESPN BET': 'ESPN', 'theScore Bet': 'ESPN',
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


def defense_context(line, payload):
    """Return sourced opponent-by-position context using the site's defense table."""
    rows = (((payload or {}).get('defense') or {}).get('rows') or {})
    opponent, pos, stat = str(line.get('opponent') or ''), POS_GROUP.get(line.get('position')), line.get('stat')
    direction = line.get('direction')
    if not opponent or not pos or not stat or direction not in ('over', 'under'):
        return None
    row = rows.get(opponent) or {}
    value = (row.get(pos) or {}).get(stat)
    games = ((row.get('coverage') or {}).get(pos) or {}).get(stat, row.get('g', 0))
    if not isinstance(value, (int, float)) or not isinstance(games, (int, float)) or games < 3:
        return None
    ranked = []
    for team, defense in rows.items():
        observed = (((defense or {}).get('coverage') or {}).get(pos) or {}).get(stat, (defense or {}).get('g', 0))
        allowed = ((defense or {}).get(pos) or {}).get(stat)
        if isinstance(observed, (int, float)) and observed >= 1 and isinstance(allowed, (int, float)):
            ranked.append((allowed, str(team)))
    ranked.sort()
    if not ranked:
        return None
    rank = 1 + sum(1 for allowed, _team in ranked if allowed < value)
    total = len(ranked)
    tone = 'soft' if rank > total * 2 / 3 else 'tough' if rank <= total / 3 else 'neutral'
    supports = (direction == 'over' and tone == 'soft') or (direction == 'under' and tone == 'tough')
    opposes = (direction == 'over' and tone == 'tough') or (direction == 'under' and tone == 'soft')
    return {'rank': rank, 'of': total, 'value': value, 'games': int(games), 'pos': pos, 'stat': stat,
            'supports': supports, 'opposes': opposes}


def projected_team_margin(game, line):
    """Projected margin for the player's team; descriptive CFB context, never a play input."""
    v2, team = game.get('v2') or {}, str(line.get('team') or '')
    away, home = game.get('away') or {}, game.get('home') or {}
    if not team or not isinstance(v2.get('away'), (int, float)) or not isinstance(v2.get('home'), (int, float)):
        return None
    if team == str(away.get('id')):
        return v2['away'] - v2['home']
    if team == str(home.get('id')):
        return v2['home'] - v2['away']
    return None


def matchup_candidate(games, details, now, teams=None):
    rows = []
    for game in games:
        detail = details.get(game['id']) or {}
        candidates, used = [], set()
        for line in [*(detail.get('favoriteLines') or []), *(detail.get('modelReads') or [])]:
            key = line.get('sourceId') or line.get('id')
            if key in used:
                continue
            used.add(key)
            candidates.append(line)
        for line in candidates:
            all_history = line.get('history') or {}
            history = all_history.get('last') or {}
            season_history = all_history.get('season') or {}
            matchup = defense_context(line, (teams or {}).get(game.get('league')))
            if line.get('kind') not in (None, 'player') or line.get('alternate') \
                    or history.get('games', 0) < 5 or history.get('rate', 0) < 80 \
                    or not isinstance(line.get('odds'), (int, float)) \
                    or not current(line.get('observedAt'), now, timedelta(hours=4)) \
                    or line.get('book') not in PUBLIC_BOOKS or not matchup or not matchup['supports']:
                continue
            margin = projected_team_margin(game, line)
            script_risk = game.get('league') == 'CFB' and isinstance(margin, (int, float)) and margin <= -14
            opponent = line.get('opponentAbbr') or 'Opponent'
            stat = STAT_LABEL.get(matchup['stat'], str(line.get('market') or matchup['stat']).lower())
            detail_text = f"{opponent} allows {matchup['value']:g} {stat}/game to {matchup['pos']}s · #{matchup['rank']} of {matchup['of']}"
            if script_risk:
                detail_text += f" · {line.get('teamAbbr') or 'team'} projected {abs(margin):g}-pt dog"
            away, home = game.get('away') or {}, game.get('home') or {}
            matchup_label = (f"{away.get('abbr') or away.get('abbreviation') or away.get('short') or '?'} at "
                               f"{home.get('abbr') or home.get('abbreviation') or home.get('short') or '?'}")
            rows.append({'league': game.get('league'), 'gameId': game['id'], 'kickoff': game['kickoff'],
                         'matchupLabel': matchup_label,
                         'title': line.get('title'), 'team': None, 'athleteId': line.get('athleteId'),
                         'price': f"{price(line.get('odds'))} {book_short(line.get('book'))}",
                         'book': line.get('book'), 'metric': f"{history['hits']}/{history['games']} exact-line trend",
                         'detail': detail_text,
                         'opponentAbbr': opponent, 'statLabel': stat,
                         'hits': history['hits'], 'games': history['games'], 'pushes': history.get('pushes', 0),
                         'historyValues': list(history.get('values') or []),
                         'seasonHits': season_history.get('hits'), 'seasonGames': season_history.get('games'),
                         'scriptRisk': script_risk, 'projectedMargin': margin, 'matchup': matchup,
                         'score': (history.get('rate', 0), history.get('games', 0), line.get('edge') or 0),
                         'observedAt': line.get('observedAt')})
    rows.sort(key=lambda row: (row['scriptRisk'], -row['score'][0], -row['score'][1],
                               -row['score'][2], row['title']))
    if not rows:
        return None
    shown = rows[:3]
    lines = [f"{row['title']} | {row['hits']}/{row['games']} | {row['detail']}" for row in shown]
    caution = ['CFB big-underdog usage is ranked down.' if any(row['scriptRisk'] for row in shown) else None,
               'Trend + defense context, not a prediction or official play.']
    return {'kind': 'matchup', 'title': 'MATCHUP TRENDS', 'kicker': 'EXACT LINE + OPPONENT DEFENSE', 'accent': CYAN,
            'rows': shown, 'text': '\n'.join(['📊 MATCHUP TRENDS', 'Strong exact-line history supported by the opponent matchup:',
                                             *lines, '', *[row for row in caution if row], tags(shown)])}


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
                    or row.get('roleSuspect') or row.get('priceSuspect')
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
    """Write a short, evidence-first caption while the card carries the full detail."""
    from x_post import LIMIT, tweet_length
    rows, kind = choice.get('rows') or [], choice.get('kind')
    if not rows or kind not in ('upset', 'spread-dog', 'matchup', 'season', 'end-zone'):
        return choice['text']
    row = rows[0]
    headings = {'upset': '🐕 UNDERDOG WATCH', 'spread-dog': '🐕 SPREAD WATCH',
                'matchup': '📊 MATCHUP TREND', 'season': '📈 TREND BOARD',
                'end-zone': '🎯 END-ZONE WORK'}
    headline = str(row.get('title') or '').strip()
    evidence = ''
    if kind == 'matchup':
        matchup = row.get('matchup') or {}
        count = f"{row.get('hits')}/{row.get('games')} at this line"
        if isinstance(matchup.get('rank'), int) and isinstance(matchup.get('of'), int):
            count += (f" · {row.get('opponentAbbr') or 'Opponent'} #{matchup['rank']}/{matchup['of']}"
                      f" vs {matchup.get('pos') or ''} {row.get('statLabel') or ''}").rstrip()
        evidence = count
    elif kind == 'season':
        headline = f"{headline} · {row.get('price') or ''}".rstrip(' ·')
        evidence = str(row.get('metric') or '')
    elif kind == 'end-zone':
        evidence = ' · '.join(value for value in (str(row.get('metric') or ''), str(row.get('price') or '')) if value)
    elif kind == 'upset':
        headline = f"{headline} {row.get('price') or ''} ({book_short(row.get('book'))})".strip()
        evidence = str(row.get('copyMetric') or row.get('metric') or '')
    else:
        headline = f"{headline} {row.get('price') or ''} {book_short(row.get('book'))}".strip()
        evidence = str(row.get('metric') or '')
    league_tags = tags(rows)
    if tweet_length(headline) > 200:
        return '\n'.join([headings[kind], 'Details on the card', *([league_tags] if league_tags else [])])
    lines = [headings[kind], headline, evidence]
    if row.get('price') and kind in ('matchup',):
        lines.append(str(row['price']))
    if len(rows) > 1:
        lines.append(f"+{len(rows) - 1} more on the card")
    if league_tags:
        lines.append(league_tags)
    lines = [line for line in lines if line]
    while len(lines) > 2 and tweet_length('\n'.join(lines)) > LIMIT:
        # Drop the optional count, then evidence, but never cut a name or line in half.
        lines.pop(-2 if league_tags and lines[-1] == league_tags else -1)
    if tweet_length('\n'.join(lines)) > LIMIT:
        lines = [headings[kind], 'Details on the card', *([league_tags] if league_tags else [])]
    return '\n'.join(lines)


def select(data, details, now, lines=None, teams=None):
    games = slate_games(data, now)
    if not games:
        return None
    season = season_candidate(games, details, now)
    # Alternate days share the existing editorial slot; never add another daily post.
    chosen = (season if eastern_date(now).day % 2 == 0 else None) or (
        upset_candidate(games, now) or spread_dog_candidate(games, lines, now)
        or matchup_candidate(games, details, now, teams) or season or scorer_candidate(games, details, now))
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
    import tnf_early_look
    if tnf_early_look.ENABLED:
        early = tnf_early_look.select(data, load_lines(lines_path), now)
        if early:
            caption = tnf_early_look.caption(early)
            if caption:
                return {'key': early['key'], 'kind': 'research',
                        'card': f"tnf-early-look-{early['researchDay'].isoformat()}",
                        'text': caption, 'due': early['due'].astimezone(timezone.utc),
                        'stale': early['stale'].astimezone(timezone.utc),
                        'countsFor': early['researchDay']}
    cards = data.get('games') or []
    choice = select(data, details_for(cards, detail_root), now,
                    load_lines(lines_path), teams_for(cards))
    if not choice:
        return None
    stale = min(at(choice['day'], POST_UNTIL), choice['firstKickoff'] - timedelta(minutes=45))
    if choice['kind'] in ('season', 'matchup'):
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
<text x="1032" y="89" text-anchor="end" fill="{DIM}" font-size="20" font-weight="750" letter-spacing="3">SLATE RESEARCH</text>
<text x="44" y="165" fill="{accent}" font-size="22" font-weight="850" letter-spacing="4">{esc(choice['kicker'])}</text>
<text x="44" y="247" fill="{TEXT}" font-size="67" font-weight="950">{esc(choice['title'])}</text>
{''.join(blocks)}
<text x="44" y="{footer}" fill="{TEXT}" font-size="25" font-weight="800">DATA WORTH A CLOSER LOOK.</text>
<text x="44" y="{footer + 42}" fill="{accent}" font-size="24" font-weight="750">keenroudy.com/sports</text>
<text x="1036" y="{footer + 42}" text-anchor="end" fill="{DIM}" font-size="19">DATA + CONTEXT</text>
</svg>'''


def render_due(now, folder, data_path=TODAY, detail_root=DETAILS, lines_path=LINES, fetch=None, log=print):
    data = load(data_path, {'games': []})
    import tnf_early_look
    early_cards = {}
    if tnf_early_look.ENABLED:
        early = tnf_early_look.select(data, load_lines(lines_path), now)
        if early:
            try:
                path = tnf_early_look.render(early, folder, fetch=fetch)
                early_cards[path.stem] = path
            except Exception as error:
                log(f"TNF Early Look card not drawn: {error}")
    cards = data.get('games') or []
    choice = select(data, details_for(cards, detail_root), now,
                    load_lines(lines_path), teams_for(cards))
    if not choice:
        return early_cards
    fetch = fetch or pick_card.fetch_data_uri
    games = {g['id']: g for g in data.get('games') or []}
    images = {i: art_for(row, games.get(row['gameId']) or {}, fetch) for i, row in enumerate(choice['rows'])}
    path = Path(folder) / f"{choice['key']}.png"
    try:
        pick_card.render(svg(choice, images), path)
    except Exception as error:
        log(f"research card {choice['key']} not drawn: {error}")
        return early_cards
    return {**early_cards, choice['key']: path}
