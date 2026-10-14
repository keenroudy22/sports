"""One evidence-first research post per calendar day.

This is editorial packaging, never candidate selection. It reads the same built
page payloads visitors see and refuses stale prices. The public priority is:
fresh outright underdogs, priced underdog spreads, fresh main-line season trends,
exact-line trends supported by opponent defense, then observed end-zone work. A missing view produces
no post. On a football off-day, or when the priced families are honestly held,
the fallback is a next-slate numbers card made only from stored projections and
fresh book lines. Nothing is invented merely to fill a calendar.
"""
import json
import os
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


def next_slate_games(data, now, horizon=timedelta(days=7)):
    """The nearest unstarted football game day, including today."""
    future = [g for g in data.get('games') or [] if g.get('league') in ('NFL', 'CFB')
              and g.get('state') == 'pre' and when(g.get('kickoff'))
              and now < when(g['kickoff']) <= now + horizon]
    if not future:
        return []
    day = min(game_day(game) for game in future)
    return sorted((game for game in future if game_day(game) == day),
                  key=lambda game: (when(game['kickoff']), game['id']))


def prep_row_hold(row, league, now):
    """The first failing Prep List rule, shared by selection and private diagnostics."""
    if row.get('league') != league:
        return 'league mismatch'
    if row.get('book') not in PUBLIC_BOOKS:
        return 'unsupported public book'
    if not isinstance(row.get('odds'), (int, float)) or row['odds'] < -200:
        return 'missing price or shorter than -200'
    if row.get('clears') is not True or not isinstance(row.get('projection'), (int, float)):
        return 'model and price do not agree'
    if not current(row.get('observedAt'), now, timedelta(hours=4)):
        return 'price missing, future or older than four hours'
    if not when(row.get('kickoff')) or when(row['kickoff']) <= now + timedelta(minutes=45):
        return 'missing kickoff or inside 45-minute cutoff'
    adjustment = row.get('opponentAdjustment') or {}
    if league == 'CFB' and adjustment and (not adjustment.get('supports') or adjustment.get('against')):
        return 'opponent-adjusted history does not support the side'
    return None


def prep_diagnostics(data, now):
    day = eastern_date(now).isoformat()
    messages = []
    for league in ('NFL', 'CFB'):
        block = (data.get('prep') or {}).get(league) or {}
        if block.get('day') != day:
            messages.append(f'{league}: no current-day Prep List')
            continue
        holds, eligible = {}, 0
        for row in block.get('rows') or []:
            reason = prep_row_hold(row, league, now)
            if reason:
                holds[reason] = holds.get(reason, 0) + 1
            else:
                eligible += 1
        messages.append(f'{league}: {eligible} eligible rows; requires 3' +
                        ''.join(f'; {count} {reason}' for reason, count in sorted(holds.items())))
    return ' | '.join(messages)


def prep_candidate(data, now):
    """First-choice research slot when three checked, fresh player lines survive."""
    from x_post import LIMIT, tweet_length
    day = eastern_date(now).isoformat()
    choices = []
    for league, block in (data.get('prep') or {}).items():
        if league not in ('NFL', 'CFB') or not isinstance(block, dict) or block.get('day') != day:
            continue
        rows = [row for row in block.get('rows') or [] if prep_row_hold(row, league, now) is None]
        if len(rows) >= 3:
            choices.append((len(rows), league, rows[:4]))
    if not choices:
        return None
    _count, league, rows = sorted(choices, key=lambda choice: (-choice[0], choice[1]))[0]
    import voice_pick
    lines = []
    for row in rows:
        stat = STAT_LABEL.get(row.get('stat'), str(row.get('stat') or 'yards')).replace('receptions', 'catches')
        play = f"{row['player']} {str(row.get('direction') or '').lower()} {float(row['line']):g} {stat}"
        dvp = row.get('dvp') or {}
        opponent = f" · defense #{dvp['rank']} of {dvp['of']}" if dvp.get('rank') and dvp.get('of') else ''
        fill = ' · incl. 2025' if row.get('includesPriorSeason') else ''
        lines.append(f"{play} {price(row['odds'])} {book_short(row['book'])} · my number {row['projection']:g}, line {float(row['line']):g}"
                     f" · {row['hits']}/{row['games']}{opponent}{fill}")
    save = voice_pick.choose_slot('save', f'prep:{day}:{league}', day, series='prep', history=[])
    caption = '\n'.join(part for part in ['Lines that keep clearing today:', *lines, save, f'#{league}'] if part)
    while tweet_length(caption) > LIMIT and len(lines) > 1:
        lines.pop()
        caption = '\n'.join(part for part in ['Lines that keep clearing today:', *lines, save, f'#{league}'] if part)
    return {'kind': 'prep', 'league': league, 'rows': rows, 'prep': {'day': day, 'rows': rows},
            'text': caption}


def price(odds):
    return f'{int(odds):+d}' if isinstance(odds, (int, float)) else 'price unavailable'


def book_short(book):
    return {'DraftKings': 'DK', 'FanDuel': 'FD', 'BetMGM': 'MGM', 'ESPN BET': 'theScore Bet', 'theScore Bet': 'theScore Bet',
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
            f"We give them {round(100 * watch['modelChance'])}%. The price says {round(100 * watch['marketChanceNoVig'])}%."
        gap = watch.get('spreadGap')
        comparison = f"We give them {round(100 * watch['modelChance'])}%. The price says {round(100 * watch['marketChanceNoVig'])}%."
        if isinstance(gap, (int, float)):
            comparison += f" | {gap:g}-pt gap vs spread"
        rows.append({'league': game.get('league'), 'gameId': game['id'], 'kickoff': game['kickoff'],
                     'title': watch.get('team') or team.get('name'), 'team': team, 'opponent': opponent,
                     'price': price(watch['odds']) + ' ML', 'book': watch.get('book'),
                     'metric': score, 'detail': comparison,
                     'copyMetric': f"we give them {round(100 * watch['modelChance'])}%. The price says {round(100 * watch['marketChanceNoVig'])}%.",
                     'reason': ((watch.get('reasons') or [None])[-1]),
                     'score': watch['modelChance'] - watch['marketChanceNoVig'], 'observedAt': watch['observedAt']})
    rows.sort(key=lambda row: (-row['score'], row['kickoff'], row['gameId']))
    if not rows:
        return None
    shown = rows[:3]
    lines = [f"{row['title']} {row['price']} ({book_short(row['book'])}) | {row['copyMetric'].lower()}" for row in shown]
    return {'kind': 'upset', 'title': 'UNDERDOG WATCH', 'kicker': 'OUTRIGHT WINNERS', 'accent': MINT,
            'rows': shown, 'text': '\n'.join(['🐕 UNDERDOG WATCH', 'Dogs whose numbers deserve a closer look:',
                                             *lines, '', tags(shown)])}


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
                     'book': line.get('book'), 'metric': f"We give it {round(100 * chance)}%. The price needs {round(100 * needs)}%.",
                     'detail': detail, 'score': grade.get('edge') or 0, 'observedAt': line.get('observedAt')})
    rows.sort(key=lambda row: (-row['score'], row['kickoff'], row['gameId']))
    if not rows:
        return None
    shown = rows[:3]
    copy = [f"{row['title']} {row['price']} {book_short(row['book'])} | {row['metric'].lower()}" for row in shown]
    return {'kind': 'spread-dog', 'title': 'UNDERDOG SPREAD WATCH', 'kicker': 'COVER VALUE · NOT OUTRIGHT', 'accent': CYAN,
            'rows': shown, 'text': '\n'.join(['🐕 UNDERDOG SPREAD WATCH', 'Dogs whose spread numbers deserve a closer look:',
                                             *copy, '', tags(shown)])}


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
        if isinstance(observed, (int, float)) and observed >= 3 and isinstance(allowed, (int, float)):
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
    caution = ['CFB big-underdog usage is ranked down.' if any(row['scriptRisk'] for row in shown) else None]
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
                                             *lines, '', tags(shown)])}


def season_candidate(games, details, now):
    rows = []
    for game in games:
        for row in (details.get(game['id']) or {}).get('seasonTrends') or []:
            adjusted = row.get('opponentAdjustment') or {}
            projection_agrees = isinstance(row.get('projection'), (int, float)) and isinstance(row.get('line'), (int, float)) \
                and ((row.get('direction') == 'over' and row['projection'] > row['line'])
                     or (row.get('direction') == 'under' and row['projection'] < row['line']))
            if (row.get('kind') != 'main' or row.get('games', 0) < 5
                    or row.get('roleSuspect') or row.get('priceSuspect')
                    or row.get('injuryStatus')
                    or not projection_agrees or row.get('priceClears') is not True
                    or (row.get('league') == 'CFB' and (adjusted.get('against') or not adjusted.get('supports')))
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
              'detail': (f"My number {r['projection']:g} · {price(r['odds'])} {r['book']} · defense "
                         f"#{(r.get('dvp') or {}).get('rank')} of {(r.get('dvp') or {}).get('of')}"
                         f"{' · incl. 2025' if r.get('includesPriorSeason') else ''}")
              if (r.get('dvp') or {}).get('rank') else
              f"My number {r['projection']:g} · {price(r['odds'])} {r['book']} · {r['season']} regular season"} for r in unique]
    def caption_row(row):
        dvp = row.get('dvp') or {}
        defense = f" defense #{dvp['rank']} of {dvp['of']}" if dvp.get('rank') and dvp.get('of') else ''
        fill = ' incl. 2025' if row.get('includesPriorSeason') else ''
        return (f"{row['player']}: {row['title']}. My number {row['projection']:g}, line {row['line']:g}; "
                f"{row['hits']}/{row['games']};{defense}{fill}")
    return {'kind': 'season', 'title': f'{bucket_label} TREND BOARD', 'kicker': 'CURRENT MAIN LINES · FULL-SEASON HISTORY',
            'accent': CYAN, 'rows': shown,
            'text': '\n'.join([f'📈 KOOK\'N {bucket_label} TREND BOARD',
                               *[caption_row(r) for r in unique],
                               'keenroudy.com/sports/#trends', tags(unique)])}


def numbers_candidate(games, now):
    """A casual, non-pick look at the nearest slate from public site numbers."""
    rows = []
    for game in games:
        model, away, home = game.get('v2') or {}, game.get('away') or {}, game.get('home') or {}
        if not all(isinstance(model.get(key), (int, float)) for key in ('away', 'home', 'total')):
            continue
        away_name = away.get('abbr') or away.get('name')
        home_name = home.get('abbr') or home.get('name')
        if not away_name or not home_name:
            continue
        market = game.get('market') or {}
        seen = market.get('retrievedAt')
        fresh = current(seen, now, timedelta(hours=12))
        vegas = market.get('total') if fresh else None
        has_vegas = isinstance(vegas, (int, float))
        price_text = f"Vegas total {vegas:g}" if has_vegas else f"My score {model['away']:g}–{model['home']:g}"
        gap = model['total'] - vegas if has_vegas else None
        detail = f"My total {model['total']:g}"
        if isinstance(gap, (int, float)):
            detail += f" · {'+' if gap >= 0 else ''}{gap:.1f} vs Vegas"
        rows.append({'league': game.get('league'), 'gameId': game['id'], 'kickoff': game['kickoff'],
                     'title': f'{away_name} at {home_name}', 'team': home,
                     'price': price_text,
                     'book': (market.get('displayBook') or market.get('book')) if has_vegas else None,
                     'metric': f"Mine {model['total']:g}", 'detail': detail,
                     'observedAt': seen if has_vegas else None, 'hasVegas': has_vegas,
                     'score': abs(gap) if isinstance(gap, (int, float)) else 0})
    if not rows:
        return None
    rows.sort(key=lambda row: (-int(row['hasVegas']), -row['score'], row['kickoff'], row['gameId']))
    shown = rows[:4]
    openers = ('A few numbers I keep coming back to:',
               'Here’s what I’m circling on the next football slate:',
               'Early look. These are the numbers that caught my eye:')
    opener = openers[eastern_date(now).toordinal() % len(openers)]
    lines = []
    for row in shown[:3]:
        if row['hasVegas']:
            lines.append(f"{row['title']} — my total {row['metric'].removeprefix('Mine ')}, Vegas {row['price'].removeprefix('Vegas total ')}.")
        else:
            lines.append(f"{row['title']} — {row['price'].lower()}.")
    league = shown[0].get('league')
    from x_post import LIMIT, tweet_length
    footer = ['Not picks yet. Just where my numbers start.', f'#{league}']
    text = '\n'.join([opener, *lines, *footer])
    while len(lines) > 1 and tweet_length(text) > LIMIT:
        lines.pop()
        text = '\n'.join([opener, *lines, *footer])
    if tweet_length(text) > LIMIT:
        text = '\n'.join(['Early look at the next football slate.', 'The numbers are on the card.', *footer])
    return {'kind': 'numbers', 'title': 'MY NUMBER VS VEGAS' if any(row['hasVegas'] for row in shown) else 'NEXT SLATE',
            'kicker': 'EARLY LOOK · NOT A BEST BET', 'accent': CYAN, 'rows': shown, 'text': text,
            'usesPrice': any(row['hasVegas'] for row in shown)}


def already_posted(log_book, day):
    posts = log_book.get('posts') or []
    keys = posts if isinstance(posts, dict) else (row.get('id', '') for row in posts)
    return any(part.startswith('research:') and part.endswith(day.isoformat())
               for key in keys for part in str(key).split('+'))


def bounded_caption(choice):
    """Write a short, evidence-first caption while the card carries the full detail."""
    from x_post import LIMIT, tweet_length
    rows, kind = choice.get('rows') or [], choice.get('kind')
    if not rows or kind not in ('upset', 'spread-dog', 'matchup', 'season', 'end-zone', 'numbers'):
        return choice['text']
    if kind == 'numbers' and tweet_length(choice.get('text') or '') <= LIMIT:
        return choice['text']
    row = rows[0]
    headings = {'upset': '🐕 UNDERDOG WATCH', 'spread-dog': '🐕 SPREAD WATCH',
                'matchup': '📊 MATCHUP TREND', 'season': '📈 TREND BOARD',
                'end-zone': '🎯 END-ZONE WORK', 'numbers': '👀 MY NUMBER VS VEGAS'}
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
    elif kind == 'numbers':
        evidence = ' · '.join(value for value in (str(row.get('price') or ''), str(row.get('metric') or '')) if value)
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


def select(data, details, now, lines=None, teams=None, order=None, log=None):
    today_games = slate_games(data, now)
    games = today_games or next_slate_games(data, now)
    if not games:
        return None
    prepared = prep_candidate(data, now) if today_games else None
    if log and not prepared:
        log('research rules: prep held — ' + prep_diagnostics(data, now))
    usable = lambda choice: choice if choice and len(choice.get('rows') or []) >= 2 else None
    if os.environ.get('KEENROUDY_RESEARCH_FALLBACK', '1').strip().lower() in ('0', 'false', 'off', 'no'):
        chosen = prepared
        if log:
            log('research fallback: disabled; prep ' + ('eligible' if chosen else 'held: no eligible card'))
    else:
        # One deterministic football-day chain. A mature category may move
        # only through the two-week-confirmed learner; sparse categories keep
        # this written order. Spread dogs remain inside Upset Watch.
        factories = {
            'prep': lambda: prepared,
            'season': lambda: usable(season_candidate(games, details, now)),
            'upset': lambda: usable(upset_candidate(games, now)) or usable(spread_dog_candidate(games, lines, now)),
            'matchup': lambda: usable(matchup_candidate(games, details, now, teams)),
            'end-zone': lambda: usable(scorer_candidate(games, details, now)),
        }
        wanted = [kind for kind in (order or factories) if kind in factories]
        wanted += [kind for kind in factories if kind not in wanted]
        chosen = None
        for kind in wanted:
            choice = factories[kind]()
            if log:
                log(f'research fallback: {kind} ' +
                    (f'eligible: {len(choice.get("rows") or [])} rows' if choice else 'held: no eligible card'))
            if choice:
                chosen = choice
                break
        if not chosen:
            chosen = numbers_candidate(games, now)
            if log:
                log('research fallback: numbers ' +
                    (f'eligible: {len(chosen.get("rows") or [])} rows' if chosen else 'held: no stored projections'))
    if not chosen:
        return None
    day = eastern_date(now)
    chosen.update(day=day, key=f"research-{chosen['kind']}-{day.isoformat()}", offDay=not bool(today_games),
                  firstKickoff=min(when(row['kickoff']) for row in chosen['rows']))
    chosen['text'] = bounded_caption(chosen)
    return chosen


def at(day, hm):
    return datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)


def post(games, now, data_path=TODAY, detail_root=DETAILS, lines_path=LINES, log=print):
    data = load(data_path, {'games': []})
    import tnf_early_look
    if tnf_early_look.ENABLED:
        early = tnf_early_look.select(data, load_lines(lines_path), now)
        if early:
            caption = tnf_early_look.caption(early)
            if caption:
                log(f"research: scheduled TNF Early Look for {early['due'].astimezone(gates.EASTERN):%-I:%M %p} ET")
                return {'key': early['key'], 'kind': 'research',
                        'card': f"tnf-early-look-{early['researchDay'].isoformat()}",
                        'text': caption, 'due': early['due'].astimezone(timezone.utc),
                        'stale': early['stale'].astimezone(timezone.utc),
                        'countsFor': early['researchDay']}
    cards = data.get('games') or []
    import learning
    order = ((learning.load_policy().get('twoWay') or {}).get('researchOrder') or None)
    choice = select(data, details_for(cards, detail_root), now,
                    load_lines(lines_path), teams_for(cards), order=order, log=log)
    if not choice:
        reason = ('no stored football game in the next seven days' if not next_slate_games(data, now)
                  else 'no verified research family or stored projection was usable')
        log(f'research: skipped — {reason}')
        return None
    deadlines = {'daily research window ended': at(choice['day'], POST_UNTIL),
                 '45-minute kickoff cutoff': choice['firstKickoff'] - timedelta(minutes=45)}
    if choice['kind'] in ('season', 'matchup', 'prep'):
        deadlines['four-hour price expiry'] = min(when(r['observedAt']) + timedelta(hours=4) for r in choice['rows'])
    if choice['kind'] == 'numbers' and choice.get('usesPrice'):
        deadlines['twelve-hour market expiry'] = min(when(r['observedAt']) + timedelta(hours=12)
                                                     for r in choice['rows'] if r.get('hasVegas'))
    stale = min(deadlines.values())
    due = max(at(choice['day'], (9, 30) if choice['kind'] == 'prep' else POST_AT),
              now + timedelta(minutes=2))
    if now >= stale or due >= stale:
        blocked = ', '.join(reason for reason, deadline in deadlines.items() if max(now, due) >= deadline)
        log(f"research: skipped {choice['kind']} — {blocked}")
        return None
    log(f"research: scheduled {choice['kind']} for {due.astimezone(gates.EASTERN):%-I:%M %p} ET")
    return {'key': f"research:{choice['kind']}:{choice['day'].isoformat()}", 'kind': 'research',
            # A one-game slate is useful as a short conversation post, but the
            # approved list art needs at least two honest rows. Never pad it.
            'card': (None if choice['kind'] == 'numbers' and len(choice['rows']) < 2 else choice['key']),
            'text': choice['text'],
            'due': due, 'stale': stale}


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
    if choice.get('kind') == 'numbers' and len(choice.get('rows') or []) < 2:
        return early_cards
    fetch = fetch or pick_card.fetch_data_uri
    path = Path(folder) / f"{choice['key']}.png"
    try:
        if choice['kind'] == 'prep':
            import ticket_card
            picture = ticket_card.prep_svg(choice['prep'], fetch=fetch)
        else:
            games = {g['id']: g for g in data.get('games') or []}
            images = {i: art_for(row, games.get(row['gameId']) or {}, fetch) for i, row in enumerate(choice['rows'])}
            import ticket_card
            picture = ticket_card.research_list_svg(choice, art=images)
        pick_card.render(picture, path)
    except Exception as error:
        log(f"research card {choice['key']} not drawn: {error}")
        return early_cards
    return {**early_cards, choice['key']: path}
