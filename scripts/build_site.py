"""Page payloads for the site, built from the stores. No network.

Each page loads only what it shows:

  app/today.json              games from three days back to eight ahead, with the
                              market, v1 and the latest v2 forecast; recent/open picks
  app/today-hero.json         Today's first paint (under 4 KB): today's best bets with
                              price, book, kickoff and card, the Climb status, last W-L
  app/record.json             the complete public pick history
  app/lines.json              small line-catalog manifest
  app/lines-NFL.json          NFL line catalog and current game markets
  app/lines-CFB.json          CFB line catalog and current game markets
  app/games/<id>.json         one game: forecast history, player projections next
                              to DraftKings lines, both teams' form and defense
                              ranks, injuries, picks and lines, the final
  app/players/<L>.json        player directory for a league
  app/players/<L>/<n>.json    game logs, sharded by athlete ID
  app/player-charts/<L>.json  compact upcoming-matchup player charts
  app/teams/<L>.json          team metadata (NFL also carries its defense table)
  app/teams/CFB-defense.json  the college defense table
  app/teams/<L>/<id>.json     one team's games, defense log and roster usage
  app/research.json           injury report, status changes, analyst notes
  app/vegas.json              Vegas vs reality: closing lines against finals, by league
                              (football, basketball and soccer stores; scripts/vegas.py)

Everything is derived from committed data, so site/data/app/ is not committed;
the hosted workflow rebuilds it before each deploy.

Usage: python scripts/build_site.py
"""
import json
import math
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import asset_versions
import features
import line_payload
import market_read
import model_v2
import odds_api
import pricing
import record_scope
import sharp_odds
import research_views
import role_sanity
import season_trends
import sport_research
import vegas
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'site' / 'data'
OUT = DATA / 'app'
SHARDS = {'NFL': 32, 'CFB': 128}
WINDOW_BACK, WINDOW_AHEAD = timedelta(days=3), timedelta(days=8)
LOG_KEYS = ('cmp', 'att', 'passYds', 'passTD', 'int', 'sacks', 'car', 'rushYds', 'rushTD', 'rushLong',
            'targets', 'rec', 'recYds', 'recTD', 'recLong', 'rzTgt', 'i10Tgt', 'rzCar', 'i10Car', 'i5Car',
            'scrambles', 'fumLost', 'fgm', 'fga', 'xpm', 'kPts', 'snaps', 'snapPct')
ALLOWED_KEYS = {'QB': ('att', 'cmp', 'passYds', 'passTD', 'int', 'sacks', 'car', 'rushYds', 'rushTD'),
                'RB': ('car', 'rushYds', 'rushTD', 'targets', 'rec', 'recYds', 'recTD'),
                'WR': ('targets', 'rec', 'recYds', 'recTD'), 'TE': ('targets', 'rec', 'recYds', 'recTD')}


def read(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(',', ':'), sort_keys=True, ensure_ascii=False) + '\n',
                    encoding='utf-8', newline='\n')


def number(value):
    try:
        return float(str(value).replace('+', ''))
    except (TypeError, ValueError):
        return None


def rnd(value, places=1):
    return None if value is None else round(value, places)


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


@lru_cache(maxsize=None)
def day(kickoff):
    """A kickoff's Eastern calendar date. A Thursday 8:15 PM game is Thursday, though it is Friday in UTC."""
    return eastern_date(kickoff).isoformat()


def american(value):
    """Odds arrive as '+102' or '-110' strings, or 'OFF'; pages want integers or nothing."""
    try:
        return int(str(value).replace('+', ''))
    except (TypeError, ValueError):
        return None


def instant(value):
    """A timestamp as an aware instant, naive ones read as UTC; unreadable is None."""
    try:
        moment = features.when(value) if value else None
    except ValueError:
        return None
    return moment if moment is None or moment.tzinfo else moment.replace(tzinfo=timezone.utc)


PROVIDER_BOOKS = {
    'draft kings': 'DraftKings', 'draftkings': 'DraftKings',
    'fan duel': 'FanDuel', 'fanduel': 'FanDuel',
    'bet mgm': 'BetMGM', 'betmgm': 'BetMGM',
    'espn bet': 'ESPN BET', 'thescore bet': 'ESPN BET',
}


def provider_book(value):
    """Canonical provider identity used by gates, selection and stable ids."""
    name = str(value or '').strip()
    if not name or name.casefold() == 'book unavailable':
        return None
    return PROVIDER_BOOKS.get(name.casefold(), name)


def display_book(value):
    """Public-facing book name, kept separate from the provider identity."""
    name = provider_book(value)
    return 'theScore Bet' if name == 'ESPN BET' else name


def fair_american(chance):
    if not isinstance(chance, (int, float)) or not 0 < chance < 1:
        return None
    return round(-100 * chance / (1 - chance)) if chance >= .5 else round(100 * (1 - chance) / chance)


COMPARISON_ONLY_BOOKS = {'hardrockbet'}


def public_lines(rows, now):
    """Add quote-age and exact-line shopping fields without changing provider identity.

    Public JavaScript owns the ESPN BET -> theScore Bet label.  Repeating a
    display-only name on every row and nested quote cost about 96 KB on a large
    slate and once leaked back into selection, so it is deliberately absent.
    """
    out = []
    for source in rows:
        book = provider_book(source.get('book'))
        if not book:
            continue
        row = dict(source, book=book)
        row.pop('displayBook', None)
        quotes = []
        for quote in source.get('books') or []:
            named = provider_book(quote.get('book'))
            if named:
                item = {**quote, 'book': named}
                item.pop('displayBook', None)
                quotes.append(item)
        if 'books' in source:
            row['books'] = quotes
        observed = instant(row.get('observedAt'))
        age = max(0, round((now - observed).total_seconds() / 60)) if observed and observed <= now else None
        row['ageMinutes'] = age
        row['freshness'] = ('fresh' if age is not None and age <= 60 else
                            'aging' if age is not None and age <= 240 else 'stale')
        same = [{'book': row['book'], 'odds': row.get('odds')}]
        same += [{'book': q['book'], 'odds': q.get('odds')} for q in quotes
                 if number(q.get('line')) == number(row.get('line'))]
        same = [q for q in same if american(q.get('odds')) is not None
                and re.sub(r'[^a-z0-9]', '', q['book'].casefold()) not in COMPARISON_ONLY_BOOKS]
        if same:
            best = max(same, key=lambda q: american(q['odds']))
            row['bestSameLine'] = {'book': best['book'], 'odds': american(best['odds'])}
        else:
            row['bestSameLine'] = None
        out.append(row)
    return out


# Primary team colours, used only for accents. College colours come from the followed-player identities.
NFL_COLORS = {
    'ARI': '#97233F', 'ATL': '#A71930', 'BAL': '#241773', 'BUF': '#00338D', 'CAR': '#0085CA', 'CHI': '#0B162A',
    'CIN': '#FB4F14', 'CLE': '#FF3C00', 'DAL': '#003594', 'DEN': '#FB4F14', 'DET': '#0076B6', 'GB': '#203731',
    'HOU': '#03202F', 'IND': '#002C5F', 'JAX': '#006778', 'KC': '#E31837', 'LAC': '#0080C6', 'LAR': '#003594',
    'LV': '#A5ACAF', 'MIA': '#008E97', 'MIN': '#4F2683', 'NE': '#002244', 'NO': '#D3BC8D', 'NYG': '#0B2265',
    'NYJ': '#125740', 'PHI': '#004C54', 'PIT': '#FFB612', 'SEA': '#002244', 'SF': '#AA0000', 'TB': '#D50A0A',
    'TEN': '#4B92DB', 'WSH': '#5A1414'}
NEUTRAL = '#64748B'
# Provider names as the feed spells them, mapped to the books' own spelling.
BOOKS = {'Draft Kings': 'DraftKings', 'DraftKings': 'DraftKings', 'Fan Duel': 'FanDuel', 'FanDuel': 'FanDuel',
         'Bet MGM': 'BetMGM', 'BetMGM': 'BetMGM', 'ESPN BET': 'ESPN BET', 'theScore Bet': 'ESPN BET'}


def identity_colors(identity):
    """Team colours seen in the followed-player identities, by abbreviation."""
    out = {}
    for row in (identity or {}).get('players', {}).values():
        team = row.get('team') or {}
        if team.get('abbreviation') and team.get('color'):
            out.setdefault(team['abbreviation'], '#' + team['color'].lstrip('#'))
    return out


def first_publications(reports):
    """Each pick as first published, plus its latest settlement, by id.

    The original price and projection come from first publication. A later
    report may add a result; it never rewrites what was published.
    """
    first, latest = {}, {}
    for report in sorted(reports or [], key=lambda r: r.get('publishedAt') or ''):
        league, published = report.get('league'), report.get('publishedAt')
        for kind in ('props', 'riskyProps', 'gamePicks', 'parlays'):
            for pick in report.get(kind) or []:
                key = pick.get('id')
                if not key:
                    continue
                if key not in first:
                    first[key] = dict(pick, league=league, kind=kind, publishedAt=pick.get('publishedAt') or published,
                                      historicalImport=bool(report.get('historicalImport')))
                latest[key] = dict(latest.get(key, {}), **pick)
    return first, latest


def catalog_lines(catalog, games, identities, now):
    """Every catalogued line, with the state the board sorts and filters on."""
    out = []
    for row in (catalog or {}).get('lines', []):
        game = games.get(row.get('gameId')) or {}
        kickoff = instant(row.get('kickoff') or game.get('kickoff'))
        expires = instant(row.get('expiresAt'))
        if game.get('completed') or (game.get('state') or 'pre') != 'pre' or (kickoff and kickoff <= now):
            state = 'closed'
        elif row.get('status') in ('expired', 'stale') or (expires and expires <= now):
            state = 'stale'
        elif row.get('odds') is None or row.get('status') == 'missing-price':
            state = 'unpriced'
        elif row.get('quoteType') != 'sportsbook':
            state = 'reference'
        else:
            state = 'open'
        abbr = row.get('team') or (game.get('home') or {}).get('abbreviation')
        out.append({**{k: row.get(k) for k in ('id', 'league', 'gameId', 'player', 'athleteId', 'position', 'market',
                                               'direction', 'line', 'odds', 'book', 'observedAt', 'expiresAt', 'source',
                                               'marketWindow', 'title')},
                    'state': state, 'kickoff': row.get('kickoff') or game.get('kickoff'),
                    'color': color(row.get('league'), abbr, identities)})
    return out


# ------------------------------------------------------------------ inputs

def load_store(folder):
    out = {}
    for path in sorted((ROOT / 'data' / folder).glob('*.jsonl')):
        for line in boxscores.read_store(path):
            out.setdefault(line.get('gameId') or f"{line['league']}-{line['eventId']}", []).append(line)
    return out


def snap_players_by_event():
    """eventId -> athlete ID -> nflverse player line, including team, position and snap share."""
    out = {}
    for path in sorted((ROOT / 'data' / 'nflverse').glob('nfl-*.jsonl')):
        for event, line in boxscores.latest(boxscores.read_store(path)).items():
            out[event] = {p['id']: p for p in line['players'] if p.get('id')}
    return out


def snaps_by_event(players=None):
    """eventId -> athlete ID -> (snaps, share), the compact player-page form."""
    players = players if players is not None else snap_players_by_event()
    return {event: {pid: (p['snaps'], p['pct']) for pid, p in rows.items()} for event, rows in players.items()}


ROLE_STATS = {
    'QB': {'volume': ('att', 'car'), 'red': 'rzAtt', 'inside10': None, 'td': ('passTD', 'rushTD')},
    'RB': {'volume': ('car', 'tgt'), 'red': 'rzCar', 'inside10': 'i10Car', 'td': ('rushTD', 'recTD')},
    'FB': {'volume': ('car', 'tgt'), 'red': 'rzCar', 'inside10': 'i10Car', 'td': ('rushTD', 'recTD')},
    'WR': {'volume': ('tgt',), 'red': 'rzTgt', 'inside10': 'i10Tgt', 'td': ('rushTD', 'recTD')},
    'TE': {'volume': ('tgt',), 'red': 'rzTgt', 'inside10': 'i10Tgt', 'td': ('rushTD', 'recTD')},
}


def depth_role_usage(records, snap_players, team, group, role, before, season, athlete=None):
    """Actual usage for a team's Nth player at a position by offensive snaps.

    This is descriptive, not a projection: each past game ranks the active
    position group by offensive snap share, then measures the player in that
    slot.  The named next-up player's own line is kept separately so a depth
    promotion cannot imply that he has already handled the full role.
    """
    spec = ROLE_STATS.get(group)
    if not spec or not isinstance(role, int) or role < 1:
        return None
    cutoff = features.when(before) if isinstance(before, str) else before
    selected, personal = [], []
    for game in records:
        if game.get('league') != 'NFL' or game.get('season') != season or game.get('seasonType') != 2 \
                or features.when(game.get('kickoff')) >= cutoff or str(team) not in game.get('teams', {}):
            continue
        snap_rows = [p for p in (snap_players.get(str(game.get('eventId'))) or {}).values()
                     if str(p.get('team')) == str(team)
                     and p.get('pos') == group
                     and isinstance(p.get('pct'), (int, float))]
        snap_rows.sort(key=lambda p: (-p['pct'], -p.get('snaps', 0), str(p.get('id'))))
        if len(snap_rows) < role:
            continue
        box = {str(p.get('id')): p for p in game.get('players', []) if str(p.get('team')) == str(team)}

        def line(snap):
            stats = box.get(str(snap.get('id')), {})
            pbp_ok = (game.get('quality') or {}).get('plays') == 'ok'
            keys = (*spec['volume'], spec['red'], spec['inside10'], *spec['td'])
            values = {key: stats.get(key, 0 if pbp_ok and stats else None) for key in keys if key}
            return {'player': str(snap.get('id')), 'name': snap.get('name') or stats.get('name'),
                    'snapPct': snap.get('pct'), **values}

        selected.append(line(snap_rows[role - 1]))
        if athlete:
            own = next((p for p in snap_rows if str(p.get('id')) == str(athlete)), None)
            if own:
                personal.append(line(own))
    if not selected:
        return None

    def summarize(rows):
        red, inside = spec['red'], spec['inside10']
        keys = [k for k in (*spec['volume'], red, inside, *spec['td']) if k]
        coverage = {k: sum(isinstance(r.get(k), (int, float)) for r in rows) for k in keys}
        def total(key):
            return sum(r[key] for r in rows if isinstance(r.get(key), (int, float))) if coverage.get(key) else None
        td_rows = [r for r in rows if all(isinstance(r.get(k), (int, float)) for k in spec['td'])]
        return {'games': len(rows),
                'snapPct': round(sum(r['snapPct'] for r in rows) / len(rows), 3),
                'volume': {key: round(total(key) / coverage[key], 1) if coverage[key] else None for key in spec['volume']},
                'redZone': total(red),
                'redZoneGames': sum(1 for r in rows if (r.get(red) or 0) > 0) if coverage[red] else None,
                'inside10': total(inside) if inside else None,
                'touchdowns': sum(sum(r[k] for k in spec['td']) for r in td_rows) if td_rows else None,
                'coverage': coverage, 'redZoneObserved': coverage[red], 'touchdownObserved': len(td_rows)}

    return {'role': f'{group}{role}', 'group': group, 'season': season, 'roleUsage': summarize(selected),
            'playerUsage': summarize(personal) if personal else None,
            'player': str(athlete) if athlete else None,
            'definition': f'No. {role} {group} by offensive snaps in each game',
            'sources': ['nflverse offensive snaps', 'ESPN play-by-play']}


def team_names(records, slate):
    """ESPN team ID -> abbreviation, display name and FBS flag, from what we store."""
    teams = {}
    for game in slate.get('games', []):
        for side in ('home', 'away'):
            team = game[side]
            teams[(game['league'], str(team['id']))] = {'abbr': team.get('abbreviation'), 'name': team.get('name'),
                                                        'short': team.get('short')}
    for game in records:
        for side in ('home', 'away'):
            key = (game['league'], game[side]['id'])
            teams.setdefault(key, {'abbr': game[side]['abbreviation'], 'name': game[side]['abbreviation'],
                                   'short': game[side]['abbreviation']})
    return teams


@lru_cache(maxsize=1)
def cfb_colours():
    """ESPN's colours for every college team, fetched once (data/team-colors-cfb.json): {team id: {color, alternateColor}}."""
    return read(ROOT / 'data' / 'team-colors-cfb.json', {}).get('teams') or {}


def team_colours(league, team):
    """(primary, alternate) for a team: the slate's own ESPN colours, else the stored college table; None when unknown."""
    def fix(c):
        c = str(c or '').strip().lower()
        return ('#' + c.lstrip('#')) if len(c.lstrip('#')) == 6 else None
    primary, alternate = fix(team.get('color')), fix(team.get('alternateColor'))
    if not primary and league == 'CFB':
        stored = cfb_colours().get(str(team.get('id'))) or {}
        primary, alternate = fix(stored.get('color')), fix(stored.get('alternateColor'))
    return primary, alternate


def color(league, abbr, identities):
    return NFL_COLORS.get(abbr, NEUTRAL) if league == 'NFL' else identities.get(abbr, NEUTRAL)


# ------------------------------------------------------------------ today and games

def market(game):
    """The book's current spread (home side) and total, next to the book's own opening numbers.

    Our first observation is not the open: on this slate it differs from the
    book's opener on more than half the games, so it is never labelled one.
    """
    raw = game.get('market') or {}
    if not raw:
        return None
    spread, opened = number(raw.get('spread')), number(raw.get('spreadOpen'))
    book = provider_book(BOOKS.get((raw.get('provider') or '').strip(), raw.get('provider')))
    return {'book': book, 'displayBook': display_book(book), 'spread': spread,
            'spreadOpen': opened, 'spreadMove': round(spread - opened, 1) if spread is not None and opened is not None
            else None, 'total': number(raw.get('total')), 'totalOpen': number(str(raw.get('totalOpen') or '').lstrip('ou')),
            'spreadOdds': american(raw.get('spreadOdds')), 'overOdds': american(raw.get('overOdds')),
            'underOdds': american(raw.get('underOdds')), 'homeML': american(raw.get('homeML')),
            'awayML': american(raw.get('awayML')), 'retrievedAt': game.get('marketRetrievedAt')}


def v2_summary(snapshot):
    if not snapshot:
        return None
    return {'home': snapshot['home']['points'], 'away': snapshot['away']['points'],
            'margin': rnd(snapshot['margin']), 'total': rnd(snapshot['total']),
            'winProb': snapshot['homeWinProb'], 'range': snapshot['range80'], 'sparse': snapshot.get('sparse'),
            'publishedAt': snapshot['publishedAt'], 'model': snapshot['model']}


def lean(v2, mkt, league=None, sd=None, paused=()):
    """How far v2 sits from the market, from the home side and on the total, with the calibrated chance of each lean.

    The chances use pricing.CALIBRATION, so a chip on a game card means the same thing as a grade on the board.
    """
    if not v2 or not mkt:
        return None
    out = {}
    if mkt.get('spread') is not None:
        points = round(v2['margin'] - (-mkt['spread']), 1)
        out['spread'] = points
        out['side'] = 'home' if points > 0 else 'away' if points < 0 else None
        if sd and out['side']:
            home, push, away = pricing.chances(v2['margin'], sd['margin'], -mkt['spread'])
            out['spreadChance'] = calibrated(league, 'spread', home if out['side'] == 'home' else away)
    if mkt.get('total') is not None:
        out['total'] = round(v2['total'] - mkt['total'], 1)
        if sd and out['total']:
            over, push, under = pricing.chances(v2['total'], sd['total'], mkt['total'])
            out['totalChance'] = calibrated(league, 'total', over if out['total'] > 0 else under)
    for market in ('spread', 'total'):
        if f'{league}/{market}' in paused:
            out[f'{market}Caution'] = True       # recent performance raises the bar; it does not erase the read
    return out


def calibrated(league, market, raw):
    k = pricing.CALIBRATION.get((league, market))
    return round(0.5 + k * (raw - 0.5), 3) if k is not None else round(raw, 3)


def rating_ranks(ratings):
    """Current model offense/defense rank within a league; No. 1 is strongest.

    Offense adds to points scored, so larger is better. Defense is the opponent-points effect,
    so smaller is better. Ties share a rank and the next rank skips the tied positions.
    """
    if not ratings:
        return {}

    def places(field, reverse):
        ordered = sorted(((float(row[field]), str(team)) for team, row in ratings.items()),
                         key=lambda item: ((-item[0] if reverse else item[0]), item[1]))
        out, previous, place = {}, None, 0
        for index, (value, team) in enumerate(ordered, 1):
            if previous is None or value != previous:
                place = index
                previous = value
            out[team] = place
        return out

    offense, defense = places('off', True), places('def', False)
    total = len(ratings)
    return {team: {'offense': offense[team], 'defense': defense[team], 'teams': total}
            for team in ratings}


def game_card(game, forecasts_v1, snapshot, names, identities, market_block=None, paused=(), values=None,
              strength=None):
    league = game['league']

    def side(key):
        team = game[key]
        return {**card_side(league, team, identities), 'score': team.get('score'),
                'strength': (strength or {}).get(str(team['id']))}

    v1 = forecasts_v1.get(game['id'])
    mkt = market(game)
    v2 = v2_summary(snapshot)
    return {'id': game['id'], 'league': league, 'week': game.get('week'), 'seasonType': game.get('seasonType'),
            'season': game.get('season'), 'kickoff': game['kickoff'], 'state': game.get('state'),
            'completed': bool(game.get('completed')), 'status': game.get('status'), 'neutral': bool(game.get('neutral')),
            'home': side('home'), 'away': side('away'), 'market': mkt,
            'v1': {'home': v1['home'], 'away': v1['away'], 'publishedAt': v1['publishedAt']} if v1 else None,
            'v2': v2, 'lean': lean(v2, mkt, league, snapshot.get('sd') if snapshot else None, paused),
            # Best captured, price-aware spread and total reads for the weekly projection sheet. These are built
            # from the same multi-book rows as the Board; no price means no highlighted value.
            'value': values or None,
            # The market as evidence beside our number, never inside it (scripts/market_read.py).
            'marketRead': market_block}


def recent_form(team, league, logs, before, count=5):
    rows = [r for r in logs.get(team, []) if features.when(r['kickoff']) < before][-count:]
    out = []
    for r in reversed(rows):
        off, dfn = r['offense'], r['defense']
        pbp = off.get('pbp') or {}
        out.append({'gameId': f"{league}-{r['eventId']}", 'date': day(r['kickoff']), 'opp': r['opp'], 'home': r['home'],
                    'pf': r['pointsFor'], 'pa': r['pointsAgainst'], 'yards': off.get('yards'),
                    'yardsAllowed': dfn.get('yards'), 'plays': pbp.get('plays'),
                    'success': rnd(pbp['successes'] / pbp['successPlays'], 3) if pbp.get('successPlays') else None,
                    'turnovers': off.get('turnovers'), 'close': r['close']})
    return out


def defense_table(league, defense_logs, season, last=None):
    """Per defense: observed averages and denominators for each position/stat.

    An absent field is not a shutout. These are display summaries only; neither
    the forecast model nor the append-only result ledgers are changed here.
    """
    out = {}
    for team, rows in defense_logs.items():
        rows = [r for r in rows if r['season'] == season and r['seasonType'] == 2]
        rows = rows[-last:] if last else rows
        if not rows:
            continue
        entry = {'g': len(rows), 'coverage': {}}
        for pos, keys in ALLOWED_KEYS.items():
            entry[pos], entry['coverage'][pos] = {}, {}
            for key in keys:
                values = [(r.get('allowed', {}).get(pos) or {}).get(key) for r in rows]
                values = [v for v in values if isinstance(v, (int, float))
                          and not isinstance(v, bool) and math.isfinite(v)]
                entry[pos][key] = rnd(sum(values) / len(values)) if values else None
                entry['coverage'][pos][key] = len(values)
        out[team] = entry
    return out


def pregame(snapshots, kickoff):
    """Snapshots published before kickoff. One published after (a kickoff moved earlier) is never the forecast."""
    start = features.when(kickoff)
    return [s for s in snapshots if features.when(s['publishedAt']) < start]


def game_detail(card, game, record, snapshots, captures, lines, picks, names, team_logs, defense, injuries, depth_charts,
                records, snap_players, now, grading, favorites=None, trends=None, reads=None):
    """snapshots: this game's pregame v2 snapshots, oldest first."""
    league = card['league']
    detail = dict(card)
    final = snapshots[-1] if snapshots else None
    kickoff = features.when(game['kickoff'])
    if final:
        people = {}
        for side in ('home', 'away'):
            block = final['players'].get(side) or {}
            people[side] = {'volume': block.get('volume'), 'players': [
                {**p, 'name': names.get(p['id'], p['id'])} for p in block.get('players', [])]}
        detail['forecast'] = {'publishedAt': final['publishedAt'], 'why': final['why'], 'range': final['range80'],
                              'sd': final['sd'], 'inputs': {k: final['inputs'][k] for k in
                                                            ('games', 'through', 'ratings', 'ruledOut', 'injuryCoverage')},
                              'players': people,
                              'history': [{'at': s['publishedAt'], 'margin': rnd(s['margin']), 'total': rnd(s['total']),
                                           **({'late': True} if s.get('late') else {})}
                                          for s in snapshots]}
    capture = captures[-1] if captures else None
    if capture:
        detail['props'] = {'capturedAt': capture['retrievedAt'], 'lines': capture['lines'],
                           'source': capture['source'], 'provider': capture['provider']}
    detail['market'] = card['market']
    detail['marketHistory'] = [{'at': h.get('retrievedAt'), 'spread': number(h.get('spread')), 'total': number(h.get('total')),
                                'phase': h.get('phase')} for h in game.get('marketHistory') or []]
    detail['teams'] = {}
    for side in ('home', 'away'):
        team = card[side]['id']
        opponent = card['away' if side == 'home' else 'home']['id']
        chart = depth_charts.get(team)
        unavailable = {str(p.get('id')) for p in injuries.get(team, [])
                       if re.search(r'out|doubtful|suspension', str(p.get('status', '')), re.I)}
        usage = {}
        if game.get('league') == 'NFL' and not card.get('completed') and chart:
            for slot in chart.get('positions') or []:
                for index, player in enumerate(slot.get('players') or []):
                    if str(player.get('id')) not in unavailable:
                        continue
                    next_player = next((p for p in slot['players'][index + 1:]
                                        if str(p.get('id')) not in unavailable), None)
                    if next_player:
                        summary = depth_role_usage(records, snap_players, team, slot.get('group'), index + 1,
                                                   game['kickoff'], game.get('season'), next_player.get('id'))
                        if summary:
                            usage[str(player.get('id'))] = summary
        detail['teams'][side] = {'form': recent_form(team, league, team_logs, kickoff),
                                 'defense': defense.get(team), 'opponentDefense': defense.get(opponent),
                                 'injuries': injuries.get(team, []), 'depthChart': chart,
                                 'depthUsage': usage}
    detail['lines'] = [l for l in lines if l.get('gameId') == card['id'] and not l.get('gameMarket')]
    detail['picks'] = [p for p in picks if p.get('gameId') == card['id']]
    detail['favoriteLines'] = favorites or []
    detail['modelReads'] = reads or []
    detail['seasonTrends'] = trends or []
    for row in detail['modelReads'] + detail['favoriteLines']:
        if row.get('stat') in ('passYds', 'att', 'cmp', 'recYds', 'rec'):
            row['qbNews'] = qb_news(injuries.get(str(row.get('team')), [])) or None
            if row.get('qbNews') and row.get('comparison'):
                row['comparison'] += ' QB news: ' + row['qbNews'] + '.'
    detail['scorerResearch'] = research_views.scorer_research(game, final, records, names, now)
    detail['researchStatus'] = {'moneyline': 'Winner research only; moneyline value not calibrated.',
                               'teamTotals': 'Research trial only; no validated public team-total prices.',
                               'touchdowns': 'Scoring opportunities, not TD probabilities or priced recommendations.'}
    if record:
        detail['final'] = {'home': record['home']['score'], 'away': record['away']['score'],
                           'periods': {'home': record['home'].get('periods'), 'away': record['away'].get('periods')},
                           'close': (record.get('market') or {}).get('close'), 'open': (record.get('market') or {}).get('open'),
                           'provider': (record.get('market') or {}).get('provider'),
                           'leaders': leaders(record, names), 'source': record['sources']['page']}
        detail['grades'] = grading.get(card['id'], [])
    return detail


def leaders(record, names):
    """Top passer, rushers and receivers from the stored box score."""
    out = []
    players = record['players']
    for key, label, count in (('passYds', 'passing', 1), ('rushYds', 'rushing', 2), ('recYds', 'receiving', 3)):
        for team in (record['away']['id'], record['home']['id']):
            best = sorted((p for p in players if p.get('team') == team and p.get(key)), key=lambda p: -p[key])[:count]
            for p in best:
                out.append({'id': p['id'], 'name': p.get('name') or names.get(p['id'], p['id']), 'team': team,
                            'pos': p.get('pos'), 'kind': label,
                            'line': {k: p[k] for k in ('cmp', 'att', 'passYds', 'passTD', 'int', 'car', 'rushYds',
                                                       'rushTD', 'rec', 'tgt', 'recYds', 'recTD') if k in p}})
    return out


# ------------------------------------------------------------------ players and teams

LEADER_KEYS = ('passYds', 'rushYds', 'recYds', 'rec')


def season_leaders(logs, index, season):
    """This season's top eight in a few headline stats, so the players page can be browsed.

    Regular season only, and only what the box-score store already holds.
    """
    totals, games = defaultdict(lambda: defaultdict(float)), defaultdict(int)
    for pid, rows in logs.items():
        for r in rows:
            if r['season'] != season or r.get('seasonType') != 2:
                continue
            games[pid] += 1
            for key in LEADER_KEYS:
                value = r['stats'].get(key)
                if isinstance(value, (int, float)):
                    totals[pid][key] += value
    meta = {row[0]: row for row in index}
    out = {}
    for key in LEADER_KEYS:
        ranked = sorted((pid for pid in totals if totals[pid].get(key) and pid in meta),
                        key=lambda pid: -totals[pid][key])[:8]
        out[key] = [[pid, meta[pid][1], meta[pid][4] or meta[pid][2] or '', round(totals[pid][key], 1), games[pid]]
                    for pid in ranked]
    return out


def build_players(league, records, snaps, teams_meta):
    logs = features.player_logs(records)
    index, shards = [], defaultdict(dict)
    latest_season = max((g['season'] for g in records), default=None)
    for pid, rows in logs.items():
        last = rows[-1]
        if not last.get('name') or last['season'] < latest_season - 1:
            continue
        name = next((r['name'] for r in reversed(rows) if r.get('name')), None)
        pos = next((r['pos'] for r in reversed(rows) if r.get('pos')), None)
        table = []
        for r in rows:
            stats = dict(r['stats'])
            if league == 'NFL' and r['eventId'] in snaps and pid in snaps[r['eventId']]:
                stats['snaps'], stats['snapPct'] = snaps[r['eventId']][pid]
            table.append([r['eventId'], day(r['kickoff']), r['season'], r['week'], r['seasonType'], r['team'], r['opp'],
                          1 if r['home'] is True else 0 if r['home'] is False else -1]
                         + [stats.get(k) for k in LOG_KEYS])
        team = last['team']
        index.append([pid, name, pos, team, teams_meta.get((league, team), {}).get('abbr'), day(last['kickoff']), len(rows)])
        shards[int(pid) % SHARDS[league]][pid] = {'name': name, 'pos': pos, 'rows': table}
    index.sort(key=lambda row: (row[1] or '', row[0]))
    return index, shards, season_leaders(logs, index, latest_season), latest_season


def build_player_charts(league, games, forecasts, player_logs, season, lines, now):
    """Compact current-slate player histories for the visual cheat sheet.

    The full directory remains sharded for player pages.  This payload only keeps
    players in the latest pregame role forecast for an upcoming game, their
    current regular-season rows, and one current main line per stat.  That makes
    a college slate practical on a phone without another request or data feed.
    """
    games = sorted((g for g in games if g.get('league') == league and g.get('state') == 'pre'
                    and features.when(g['kickoff']) > now), key=lambda g: (g['kickoff'], g['id']))
    game_ids = {g['id'] for g in games}
    word_to_key = {word: key for key, word in pricing.WORDS.items()}
    current_lines = {}
    state_rank = {'open': 0, 'reference': 1, 'unpriced': 2}
    for row in lines:
        if row.get('gameId') not in game_ids or not row.get('athleteId') or row.get('state') not in state_rank:
            continue
        key = row.get('stat') or word_to_key.get(str(row.get('market') or '').lower())
        if key not in LOG_KEYS:
            continue
        slot = (row['gameId'], str(row['athleteId']), key)
        prior = current_lines.get(slot)
        score = (state_rank[row['state']], -int(instant(row.get('observedAt')).timestamp()) if instant(row.get('observedAt')) else 0)
        prior_score = (state_rank[prior['state']], -int(instant(prior.get('observedAt')).timestamp()) if instant(prior.get('observedAt')) else 0) if prior else None
        if prior is None or score < prior_score:
            current_lines[slot] = row

    projection_key = {value: key for key, value in pricing.PROJECTED.items()}
    roster = defaultdict(list)
    for pid, rows in player_logs.items():
        latest = next((r for r in reversed(rows) if r.get('season') == season and r.get('seasonType') == 2), None)
        if latest and latest.get('team') is not None and latest.get('pos') in {'QB', 'RB', 'FB', 'WR', 'TE', 'PK'}:
            roster[str(latest['team'])].append({'id': str(pid), 'name': latest.get('name'), 'pos': latest.get('pos')})
    out_games, out_players = [], []
    seen = set()
    for game in games:
        snapshot = (pregame(forecasts.get(game['id'], []), game['kickoff']) or [None])[-1]
        if not snapshot:
            continue
        out_games.append({'id': game['id'], 'kickoff': game['kickoff'], 'day': day(game['kickoff']),
                          'away': {k: game['away'].get(k) for k in ('id', 'name', 'abbreviation', 'color', 'alternateColor')},
                          'home': {k: game['home'].get(k) for k in ('id', 'name', 'abbreviation', 'color', 'alternateColor')}})
        for side in ('away', 'home'):
            team = str(game[side]['id'])
            opponent = str(game['home' if side == 'away' else 'away']['id'])
            projected = (((snapshot.get('players') or {}).get(side) or {}).get('players') or [])
            qb_change = role_sanity.quarterback_change(projected, player_logs, team, season, league, game['kickoff'])
            projected_ids = {str(player.get('id')) for player in projected}
            active = list(projected) + [player for player in roster.get(team, []) if str(player.get('id')) not in projected_ids]
            for forecast in active:
                pid = str(forecast.get('id') or '')
                if not pid or (game['id'], pid) in seen:
                    continue
                seen.add((game['id'], pid))
                log_rows = player_logs.get(pid, [])
                history = []
                for record in log_rows:
                    if record.get('season') != season or record.get('seasonType') != 2 \
                            or features.when(record['kickoff']) >= min(now, features.when(game['kickoff'])):
                        continue
                    values = {key: record['stats'][key] for key in LOG_KEYS
                              if isinstance(record.get('stats', {}).get(key), (int, float))
                              and not isinstance(record['stats'][key], bool) and math.isfinite(record['stats'][key])}
                    if values:
                        history.append({'date': day(record['kickoff']), 'opp': str(record['opp']),
                                        'home': 1 if record.get('home') is True else 0 if record.get('home') is False else -1,
                                        'stats': values})
                # Keep the complete observed regular season. A rolling-window
                # control must never silently shorten the Season sample.
                history.sort(key=lambda row: row['date'])
                projections = {}
                under_review = []
                for source, key in projection_key.items():
                    value = forecast.get(source)
                    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (int, float)):
                        caution = role_sanity.assess(forecast, log_rows, team, key, season)
                        if caution or role_sanity.affected_by_qb_change(pid, forecast.get('pos'), key, qb_change):
                            under_review.append(key)
                        else:
                            projections[key] = round(value[0], 1)
                player_lines = {}
                for key in LOG_KEYS:
                    row = current_lines.get((game['id'], pid, key))
                    if row:
                        player_lines[key] = {k: row.get(k) for k in ('line', 'odds', 'book', 'direction', 'state', 'observedAt')}
                if not history and not projections and not player_lines:
                    continue
                quote = next((current_lines.get((game['id'], pid, key)) for key in LOG_KEYS
                              if current_lines.get((game['id'], pid, key))), None)
                name = forecast.get('name') or next((r.get('name') for r in reversed(log_rows) if r.get('name')), None) \
                    or (quote or {}).get('player') or f'Player {pid}'
                pos = forecast.get('pos') or next((r.get('pos') for r in reversed(log_rows) if r.get('pos')), None) \
                    or (quote or {}).get('position')
                out_players.append({'id': pid, 'name': name, 'pos': pos,
                                    'team': team, 'opp': opponent, 'gameId': game['id'], 'side': side,
                                    'rows': history, 'projection': projections, 'underReview': under_review,
                                    'lines': player_lines})
    return {'generatedAt': stamp(now), 'season': season, 'keys': list(LOG_KEYS),
            'games': out_games, 'players': out_players}


def build_teams(league, records, team_logs, defense_logs, teams_meta, identities, current):
    fbs = {team for team, rows in team_logs.items() if sum(1 for r in rows if r['season'] >= current - 1) >= 8} \
        if league == 'CFB' else set(team_logs)
    directory = {}
    for team in sorted(team_logs):
        meta = teams_meta.get((league, team), {})
        directory[team] = {'abbr': meta.get('abbr'), 'name': meta.get('name'), 'short': meta.get('short'),
                           'color': color(league, meta.get('abbr'), identities), 'fbs': team in fbs}
    table = {'season': current, 'rows': defense_table(league, defense_logs, current),
             'last5': defense_table(league, defense_logs, current, 5),
             'prior': {'season': current - 1, 'rows': defense_table(league, defense_logs, current - 1)}}
    files = {}
    for team in fbs:
        games = [{'gameId': f"{league}-{r['eventId']}", 'date': day(r['kickoff']), 'season': r['season'], 'week': r['week'],
                  'seasonType': r['seasonType'], 'opp': r['opp'], 'home': r['home'], 'pf': r['pointsFor'],
                  'pa': r['pointsAgainst'], 'close': r['close'],
                  'off': {k: r['offense'].get(k) for k in ('yards', 'passYds', 'rushYds', 'turnovers', 'plays')},
                  'def': {k: r['defense'].get(k) for k in ('yards', 'passYds', 'rushYds', 'turnovers')}}
                 for r in team_logs[team] if r['season'] >= current - 1]
        allowed = [{'gameId': f"{league}-{r['eventId']}", 'date': day(r['kickoff']), 'season': r['season'],
                    'week': r['week'], 'opp': r['opp'], 'allowed': r['allowed']}
                   for r in defense_logs.get(team, []) if r['season'] >= current - 1]
        files[team] = {'id': team, **directory[team], 'games': games, 'defense': allowed}
    return {'teams': directory, 'defense': table}, files


def trend_payload(rows):
    """One history and one player/game context per player/stat; threshold rows point to them."""
    histories, contexts, compact = {}, {}, []
    shared = ('league', 'season', 'athleteId', 'player', 'team', 'gameId', 'kickoff', 'matchup',
              'teamGames', 'rosterAsOf', 'injuryStatus', 'stat', 'projection', 'uncertainGap', 'qbNews')
    for source in rows:
        row = dict(source)
        key = '|'.join(str(row.get(name) or '') for name in ('league', 'season', 'athleteId', 'stat'))
        if key not in histories:
            histories[key] = row.get('history') or []
        contexts.setdefault(key, {name: row.get(name) for name in shared if row.get(name) is not None})
        row.pop('history', None)
        for name in shared:
            row.pop(name, None)
        row['contextKey'] = key
        compact.append(row)
    return {'rows': compact, 'contexts': contexts, 'histories': histories}


def write_trends(rows, now):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['league'], day(row['kickoff']), row.get('kind') == 'milestone')].append(row)
    files = []
    for (league, game_day, milestones), values in sorted(grouped.items()):
        suffix = '-milestones' if milestones else ''
        # Split complete player/stat groups before the two-megabyte warning.
        # No threshold or history is dropped, and the index already supports many files per day.
        groups = defaultdict(list)
        for row in values:
            groups[(row.get('athleteId'), row.get('stat'))].append(row)
        chunks, chunk = [], []
        for group in groups.values():
            trial = chunk + group
            size = len(json.dumps({'generatedAt': stamp(now), **trend_payload(trial)}, separators=(',', ':'),
                                  sort_keys=True, ensure_ascii=False).encode('utf-8')) + 1
            if chunk and size > 1024 * 1024:
                chunks.append(chunk)
                chunk = list(group)
            else:
                chunk = trial
        if chunk:
            chunks.append(chunk)
        for index, chunk in enumerate(chunks, 1):
            part = f'-part-{index}' if len(chunks) > 1 else ''
            name = f'{league}-{game_day}{suffix}{part}.json'
            write(OUT / 'trends' / name, {'generatedAt': stamp(now), **trend_payload(chunk)})
            files.append({'league': league, 'date': game_day, 'kind': 'milestone' if milestones else 'priced',
                          'file': name, 'rows': len(chunk)})
    write(OUT / 'trends' / 'index.json', {'generatedAt': stamp(now), 'files': files})


def recent_picks(picks, now):
    cutoff = now - timedelta(hours=72)
    return [pick for pick in picks if not pick.get('result') or
            (instant(pick.get('settledAt') or pick.get('publishedAt')) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]


def cutoff_fields(pick):
    """Display limits parsed from the original pricing cutoff, never a new entry rule."""
    text = str(pick.get('cutoff') or '')
    price = re.search(r'or at ([+-]\d+) or worse at ([+-]?\d+(?:\.\d+)?)', text)
    boundary = re.search(r'Closed to new entries at ([+-]?\d+(?:\.\d+)?)', text)
    if not price:
        return {'cutoffOdds': None, 'cutoffLine': None, 'cutoffBoundary': None}
    cents = pricing.cents(int(price[1])) + 1
    return {'cutoffOdds': cents - 100 if cents < 0 else cents + 100,
            'cutoffLine': float(price[2]), 'cutoffBoundary': float(boundary[1]) if boundary else None}


def qb_news(injuries):
    return '; '.join(f"{row.get('name') or row.get('player') or 'Quarterback'} {row['status']}" for row in injuries
                     if str(row.get('position') or row.get('pos') or '').upper() == 'QB'
                     and re.search(r'out|doubtful|questionable|inactive', str(row.get('status') or ''), re.I))


# ------------------------------------------------------------------ Today's first paint

HERO_BYTES = 3584          # the hero stays a few kilobytes so a cold phone paints the bet before today.json arrives
HERO_ROWS = 6              # the weekend card cap is five straight plays; one spare covers a late addition
HERO_FIELDS = ('id', 'league', 'kind', 'displayTitle', 'market', 'marketType', 'athleteId', 'position', 'line',
               'direction', 'odds', 'book', 'kickoff', 'featured', 'status', 'entryNote', 'expiresAt',
               'cutoffOdds', 'cutoffLine', 'gameId', 'side', 'ticketWhy', 'ticketBut', 'hitStrip')


def hero_parlay(pick):
    return pick.get('kind') == 'parlays' or bool(pick.get('legs')) or bool(pick.get('parlayType'))


def hero_pulled(pick):
    """Withdrawn, or pulled over news before its post went out (the same test as Today's "Pulled before kickoff")."""
    return pick.get('status') == 'withdrawn' or 'before its post went out' in str(pick.get('entryNote') or '')


def hero_card(pick, now, potd=None):
    """The share card the hosted feed draws for this play (feed.card_items), or None when it draws none.

    feed.py runs after this build, so this is the card's published path, not proof the image exists yet."""
    postable = (pick.get('favorite') is True or bool(pick.get('modelLean')) or bool(pick.get('legs'))
                or pick.get('parlayType') == 'longshot')
    kickoff = instant(pick.get('kickoff'))
    if (not postable or pick.get('historicalImport') or pick.get('result') or pick.get('entryNote')
            or (pick.get('status') or 'active') != 'active' or not kickoff or kickoff <= now):
        return None
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', str(pick.get('id') or '')):
        return None
    return f"data/cards/{pick['id']}{'-potd' if pick['id'] == potd else ''}.png"


def hero_bet(pick, now, potd=None, teams=None):
    row = {key: pick.get(key) for key in HERO_FIELDS}
    # Both teams' names and colours, as the game card carries them, so the first paint draws the same team panel.
    row['teams'] = (teams or {}).get(pick.get('gameId'))
    row['displayTitle'] = pick.get('displayTitle') or pick.get('title')
    row['featured'] = pick.get('featured') is True or None
    row['status'] = None if (pick.get('status') or 'active') == 'active' else pick.get('status')
    probability = pick.get('probabilityAtPublication') if isinstance(pick.get('probabilityAtPublication'), dict) else {}
    chance = {key: probability.get(key) for key in ('chance', 'breakEven')
              if isinstance(probability.get(key), (int, float))}
    if chance:
        if probability.get('calibrated') is False:
            chance['calibrated'] = False
        row['probabilityAtPublication'] = chance
    row['card'] = hero_card(pick, now, potd)
    return {key: value for key, value in row.items() if value is not None}


def hero_units(pick):
    """Units as core.js unitsFor counts them: saved units stand; older plays are summed at the posted price."""
    odds = pick.get('odds')
    if not isinstance(odds, (int, float)) or not odds or pick.get('result') not in ('win', 'loss', 'push'):
        return None
    if isinstance(pick.get('units'), (int, float)) and not pick.get('earlyExit'):
        return pick['units']
    risk = pick.get('riskUnits')
    stake = risk if isinstance(risk, (int, float)) and risk > 0 else 1
    if pick['result'] == 'win':
        return stake * (odds / 100 if odds > 0 else 100 / abs(odds))
    if pick['result'] == 'loss':
        return 0 if pick.get('earlyExit') else -stake
    return 0


def hero_last_slate(picks, today):
    """The most recent graded game day before today: straight best bets only, as Today's "Last game day" counts."""
    graded = [p for p in picks if p.get('result') and not p.get('historicalImport') and not hero_parlay(p)
              and p.get('kickoff') and day(p['kickoff']) < today]
    if not graded:
        return None
    last = max(day(p['kickoff']) for p in graded)
    rows = [p for p in graded if day(p['kickoff']) == last]
    priced = [u for u in (hero_units(p) for p in rows) if u is not None]
    return {'day': last, 'kickoff': max(str(p['kickoff']) for p in rows), 'wins': sum(p['result'] == 'win' for p in rows),
            'losses': sum(p['result'] == 'loss' for p in rows), 'pushes': sum(p['result'] == 'push' for p in rows),
            'units': round(sum(priced), 4) if priced else None}


def hero_climb(picks):
    """Where the 80/20 Climb stands, walked from the rungs exactly as ladder.state and core.js theLadder walk them."""
    def counts(rung):
        if rung.get('result') or 'before its post went out' in str(rung.get('entryNote') or ''):
            return True
        return not rung.get('entryNote') and (rung.get('status') or 'active') == 'active'
    rungs = sorted((p for p in picks if p.get('parlayType') == 'ladder' and counts(p)),
                   key=lambda p: (str(p.get('publishedAt') or ''), str(p.get('id'))))
    start, goal = 50, 1000
    run, step, stake, banked, open_rung, last, settled = 1, 1, start, 0, None, None, 0
    wagered = paid = saved = 0       # lifetime dollars, as core.js theLadder's accounting counts them
    for rung in rungs:
        info = rung.get('ladder') or {}
        if not rung.get('result'):
            open_rung = rung
            continue
        settled += 1
        last = {'result': rung['result'], 'step': info.get('step') or step}
        wagered += number(info.get('stake')) or stake
        if rung['result'] == 'win':
            returned = int(info.get('payout') or stake)
            paid += number(info.get('payout')) or stake
            cut = int(round(returned * .2))
            before = int(info['banked']) if info.get('banked') is not None else banked
            banked = int(info['bankedAfter']) if info.get('bankedAfter') is not None else before + cut
            saved += max(0, banked - before)
            stake = int(info['nextStake']) if info.get('nextStake') is not None else returned - cut
            step += 1
            if banked + stake >= goal:
                run, step, stake, banked = run + 1, 1, start, 0
        elif rung['result'] == 'loss':
            run, step, stake, banked = run + 1, 1, start, 0
        elif rung['result'] in ('push', 'void'):
            paid += number(info.get('stake')) or stake
    info = (open_rung or {}).get('ladder') or {}
    out = {'run': run, 'step': step, 'riding': stake, 'banked': banked, 'settled': settled, 'last': last,
           'saved': round(saved), 'net': round(paid - wagered)}
    if open_rung:
        out['open'] = {'step': info.get('step') or step, 'league': open_rung.get('league')}
        out['riding'] = int(info.get('stake') or stake)
        out['banked'] = int(info['banked']) if info.get('banked') is not None else banked
    return {key: value for key, value in out.items() if value is not None}


def hero_next_day(rows):
    """The earliest later game day's plays still on the card (a play closed after its line moved is off it)."""
    on_card = [p for p in rows if not p.get('entryNote')]
    first = min((day(p['kickoff']) for p in on_card), default=None)
    return [p for p in on_card if day(p['kickoff']) == first]


def today_hero(picks, now, potd=None, teams=None, runs=None):
    """app/today-hero.json: the few facts Today paints first, while the full today.json is still loading.

    Today's unsettled best bets (or, with none today, the next game day's still-on-the-card ones), the Climb's
    status and the last graded game day's W-L. A league with no bet today also gets its own next game day, so a
    visitor whose saved filter is NFL or CFB sees the same play the full card leads with. Everything is copied from
    the published rows; nothing is new."""
    today = eastern_date(now).isoformat()
    straight = [p for p in picks if not p.get('result') and not p.get('historicalImport') and not hero_parlay(p)
                and not hero_pulled(p) and p.get('kickoff') and day(p['kickoff']) >= today]
    order = lambda p: (not p.get('featured'), str(p.get('kickoff')), str(p.get('id')))
    bets = sorted((p for p in straight if day(p['kickoff']) == today), key=order)
    later = [p for p in straight if day(p['kickoff']) > today]
    extra = [] if bets else hero_next_day(later)
    for league in ('NFL', 'CFB'):
        if not any(p.get('league') == league for p in bets):
            seen = {p.get('id') for p in extra}
            extra += [p for p in hero_next_day([p for p in later if p.get('league') == league]) if p.get('id') not in seen]
    extra.sort(key=order)
    # Today's plays come first, so a size trim drops another day's play before any of today's.
    chosen = bets[:HERO_ROWS] + extra[:HERO_ROWS]
    rows = [hero_bet(p, now, potd, teams) for p in chosen]
    payload = {'generatedAt': stamp(now), 'day': today, 'bets': rows, 'more': len(bets) + len(extra) - len(rows),
               'climb': hero_climb(picks), 'last': last_slates(picks, today), 'season': season_records(picks, now),
               'deskRuns': runs if runs is not None else desk_runs()}
    # Never let a crowded slate grow the first paint: the full card still lists every play.
    while payload['bets'] and len(json.dumps(payload, separators=(',', ':'), sort_keys=True,
                                             ensure_ascii=False).encode('utf-8')) > HERO_BYTES:
        payload['bets'].pop()
        payload['more'] += 1
    return payload


# ------------------------------------------------------------------ Kitchen Ticket fields (OWNER-DECISIONS item 22)
#
# Everything the Today ticket, the Prep List and the date line need is chosen here, at build time, from saved
# fields. The browser lays it out; it never writes a reason, picks a research row or re-implements a hold.

RUN_PLIST = ROOT / 'deployment' / 'mac' / 'com.keenroudy.sports.run.plist'
TICKET_TEXT = 84           # about two lines beside the WHY/BUT tag on a 375 px ticket
VOLUME_WORDS = {'targets': 'targets', 'carries': 'carries', 'att': 'pass attempts'}
ROLE_RANKED = re.compile(r'^Role: (\d+)(?:st|nd|rd|th) of \d+ (\S+) (QB|RB|FB|WR|TE)s by projected (\w+), ([\d.]+) a game\.$')
ROLE_PLAIN = re.compile(r'^Role: projected for ([\d.]+) (\w+) a game\.$')
LABEL_PREFIX = re.compile(r'^(?:Defense|Matchup|Weather|Usage|Volume|Injury|Checked before publishing|'
                          r'Statistical counterpoint|Prop lean): ')
POSITION_AGAINST = re.compile(r"^(?:The opponent's positional allowance points against this side|"
                              r'The defense leans against this side)\b')
NO_MORE_THAN = re.compile(r'^(.+?) is allowing [\d.]+ points per game and has not allowed more than (\d+) points '
                          r'in a game this season\.$')
FEW_HITS = re.compile(r'^Only (\d+) of the last (\d+) games cleared this side of the line; recent results oppose it\.$')
THIN_HISTORY = 'Fewer than five stored games at this line; history is limited.'
NOT_TICKET_TEXT = re.compile(r'guarantee|\block\b|\d+(?:\.\d+)?% likely|uncalibrated|breaks even at', re.I)


def first_sentence_of(text):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“])', ' '.join(str(text or '').split()), maxsplit=1)
    return parts[0] if parts and parts[0] else ''


def fit_ticket_text(text, limit=TICKET_TEXT):
    """The saved words as they are, else their first clause (the card's WHY rule, SPEC 5.1); never cut mid-word."""
    text = ' '.join(str(text or '').split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    for sep in (', and ', '; ', ' and ', ', '):
        if sep in text:
            head = text.split(sep, 1)[0].rstrip(' .,;')
            if 20 <= len(head) < limit:
                return head + '.'
    return None


def ticket_safe(text):
    """The public-copy guard every caption passes (scripts/voice.py), plus no chance claims on the ticket."""
    import voice
    return text if text and not voice.lint(text) and not NOT_TICKET_TEXT.search(text) else None


def ticket_why(pick):
    """WHY: the play's saved reason, else the first saved context line, else nothing (decision 8)."""
    reasoning = pick.get('reasoning') if isinstance(pick.get('reasoning'), dict) else {}
    reason = pick.get('reason')
    source = reason if isinstance(reason, str) and reason.strip() else next(iter(reasoning.get('context') or []), None)
    if not isinstance(source, str) or not source.strip():
        return None
    text = ' '.join(source.split())
    ranked, plain = ROLE_RANKED.match(text), ROLE_PLAIN.match(text)
    if ranked:
        rank, team, position, volume, value = ranked.groups()
        place = f"{team}'s top {position}" if rank == '1' else f'No. {rank} among {team} {position}s'
        text = f'I project {float(value):g} {VOLUME_WORDS.get(volume, volume)}, {place}.'
    elif plain:
        value, volume = plain.groups()
        text = f'I project {float(value):g} {VOLUME_WORDS.get(volume, volume)}.'
    else:
        text = LABEL_PREFIX.sub('', text)
    return ticket_safe(fit_ticket_text(text))


def ticket_but(pick, teams=None):
    """BUT: the first saved counterpoint (reasoning.cautions[0]), else nothing (decision 8)."""
    reasoning = pick.get('reasoning') if isinstance(pick.get('reasoning'), dict) else {}
    source = next(iter(reasoning.get('cautions') or []), None)
    if not isinstance(source, str) or not source.strip():
        return None
    text = ' '.join(source.split())
    side = pick.get('side')
    opponent = ((teams or {}).get('away' if side == 'home' else 'home') or {}).get('abbr') if side in ('home', 'away') else None
    direction = str(pick.get('direction') or '').lower()
    if POSITION_AGAINST.match(text):
        if opponent and pick.get('position') and direction in ('over', 'under'):
            return ticket_safe(f"{opponent}'s {pick['position']} defense points against the {direction}.")
        text = first_sentence_of(text)
    elif NO_MORE_THAN.match(text):
        team, most = NO_MORE_THAN.match(text).groups()
        text = f'No team has scored over {most} on {team}.'
    elif FEW_HITS.match(text):
        hits, games = FEW_HITS.match(text).groups()
        text = f'Only {hits} of his last {games} games cleared this line.'
    elif text == THIN_HISTORY:
        text = 'Fewer than five games at this line.'
    else:
        text = first_sentence_of(LABEL_PREFIX.sub('', text))
    return ticket_safe(fit_ticket_text(text))


def card_side(league, team, identities):
    """One team as the game card names and colours it (shared by today.json games and the hero rows)."""
    colours = team_colours(league, team)
    return {'id': str(team.get('id')), 'abbr': team.get('abbreviation'), 'name': team.get('short') or team.get('name'),
            'color': colours[0] or color(league, team.get('abbreviation'), identities), 'alt': colours[1]}


def player_side(pick, game, forecasts, player_logs):
    """'home' or 'away' for a prop: the latest pregame forecast's roster, else the player's last stored team."""
    snapshots = pregame(forecasts.get(game['id'], []), game['kickoff'])
    if snapshots:
        side, _ = pricing.player_line(snapshots[-1], pick['athleteId'])
        if side:
            return side
    last = next((r for r in reversed(player_logs.get(str(pick['athleteId']), [])) if r.get('team') is not None), None)
    if last:
        for side in ('home', 'away'):
            if str((game.get(side) or {}).get('id')) == str(last['team']):
                return side
    return None


def hit_strip(pick, game, logs):
    """The ticket's compact hit strip: the last five current-season regular-season values before kickoff, plus
    the season and last-ten counts against the posted line. Stored box scores only; None when unknown."""
    words = {word: key for key, word in pricing.WORDS.items()}
    market = pick.get('market') if pick.get('market') in LOG_KEYS else words.get(str(pick.get('market') or '').lower())
    line, side = number(pick.get('line')), str(pick.get('direction') or '').lower()
    kickoff = str(pick.get('kickoff') or game.get('kickoff') or '')
    if not market or line is None or side not in ('over', 'under') or not kickoff:
        return None
    rows = sorted((r for r in logs if r.get('seasonType') == 2 and str(r.get('kickoff') or '') < kickoff
                   and isinstance((r.get('stats') or {}).get(market), (int, float))), key=lambda r: r.get('kickoff') or '')
    season = [r['stats'][market] for r in rows if r.get('season') == game.get('season')]
    if not season:
        return None
    hit = lambda v: v > line if side == 'over' else v < line
    recent = [r['stats'][market] for r in rows[-10:]]
    return {'v': season[-5:], 'season': [sum(map(hit, season)), len(season)], 'last10': [sum(map(hit, recent)), len(recent)]}


def annotate_tickets(picks, by_id, forecasts, league_data, identities):
    """side, ticketWhy and ticketBut on each straight play; returns {gameId: teams} for the first paint."""
    teams = {}
    for pick in picks:
        if hero_parlay(pick):
            continue
        game = by_id.get(pick.get('gameId'))
        if game and game.get('home') and game.get('away') and pick.get('gameId') not in teams:
            teams[pick['gameId']] = {key: card_side(game.get('league'), game[key], identities) for key in ('away', 'home')}
        if pick.get('athleteId') and game:
            logs = (league_data.get(game.get('league')) or {}).get('player_logs', {})
            pick['side'] = player_side(pick, game, forecasts, logs)
            pick['hitStrip'] = hit_strip(pick, game, logs.get(str(pick['athleteId']), []))
        elif pick.get('marketType') == 'spread' and pick.get('direction') in ('home', 'away'):
            pick['side'] = pick['direction']
        pick['ticketWhy'] = ticket_why(pick)
        pick['ticketBut'] = ticket_but(pick, teams.get(pick.get('gameId')))
    return teams


def last_slates(picks, today):
    """The last graded game day's W-L for the date line, for all sports and each football league."""
    out = {}
    for league in ('ALL', 'NFL', 'CFB'):
        slate = hero_last_slate([p for p in picks if league == 'ALL' or p.get('league') == league], today)
        if slate:
            out[league] = slate
    return out


def season_records(picks, now=None):
    """The stub's best-bet record: the site's current-season, current-stage headline (record_scope mirrors core.js)."""
    out = {}
    for league in ('ALL', 'NFL', 'CFB'):
        rows = [p for p in picks if league == 'ALL' or p.get('league') == league]
        # No as-of cut: the stub shows the record as the site's Record page counts it now.
        summary = record_scope.summary(rows, None)
        phases = {record_scope.phase_of(p) for p in record_scope.current_rows(rows, None)}
        out[league] = {key: summary.get(key, 0) for key in ('wins', 'losses', 'pushes')}
        out[league]['playoffs'] = phases == {'playoffs'}
    return out


def desk_runs(path=RUN_PLIST):
    """The desk run times (Eastern) from the launchd job itself, for "I look again at ..." on an empty rail.

    Read with a narrow pattern, not plistlib: launchd accepts the file's comments, which a strict XML parser rejects."""
    try:
        text = Path(path).read_text(encoding='utf-8')
    except OSError:
        return []
    block = re.search(r'<key>StartCalendarInterval</key>\s*<array>(.*?)</array>', re.sub(r'<!--.*?-->', '', text, flags=re.S), re.S)
    runs = []
    for item in re.findall(r'<dict>(.*?)</dict>', block.group(1) if block else '', re.S):
        values = dict((key, int(value)) for key, value in re.findall(r'<key>(\w+)</key>\s*<integer>(\d+)</integer>', item))
        if 'Hour' in values and 'Minute' in values:
            runs.append({'h': values['Hour'], 'm': values['Minute'], **({'wd': values['Weekday']} if 'Weekday' in values else {})})
    return sorted(runs, key=lambda r: (r['h'], r['m'], r.get('wd', -1)))


# The Prep List on the site (decision 6): the playbook's section 7 exclusions plus the role and price holds.
PREP_ROLE = {'WR': (('pbpTgt', 'targets'), 5), 'TE': (('pbpTgt', 'targets'), 5), 'RB': (('car',), 12), 'FB': (('car',), 12)}
PREP_ROWS = 6
PREP_PRICE_FLOOR = -200


def prep_history_ok(row, rules):
    """5-9 games at the short-sample rate; 10 or more at the last-ten count and the season rate."""
    values = [h.get('value') for h in row.get('history') or [] if isinstance(h.get('value'), (int, float))]
    line, side = row.get('line'), row.get('direction')
    if len(values) < 5 or not isinstance(line, (int, float)) or side not in ('over', 'under'):
        return False
    hit = [(v > line) if side == 'over' else (v < line) for v in values]
    if len(values) < 10:
        return sum(hit) >= rules['short'] * len(values)
    return sum(hit[-10:]) >= rules['lastTen'] and sum(hit) >= rules['season'] * len(values)


def prep_role_ok(athlete, team, league_info, season, kickoff):
    """The playbook's role floor from stored box scores; missing usage is unknown, so the row stays off."""
    logs = league_info.get('player_logs', {})
    rows = sorted((r for r in logs.get(str(athlete), []) if str(r.get('team')) == str(team) and r.get('seasonType') == 2
                   and r.get('season') == season and str(r.get('kickoff') or '') < str(kickoff)),
                  key=lambda r: r.get('kickoff') or '')[-3:]
    if len(rows) < 3:
        return False
    position = rows[-1].get('pos')
    snaps = [(r.get('stats') or {}).get('snapPct') for r in rows]
    if all(isinstance(v, (int, float)) for v in snaps) and sum(snaps) / 3 < 0.6:
        return False
    if position in PREP_ROLE:
        keys, floor = PREP_ROLE[position]
        values = [next((r['stats'][k] for k in keys if isinstance((r.get('stats') or {}).get(k), (int, float))), None)
                  for r in rows]
        return all(v is not None for v in values) and sum(values) / 3 >= floor
    if position == 'QB':
        # The usual starter: the team's top passer in at least two of its last three games before this one.
        games = defaultdict(list)
        for player, player_rows in logs.items():
            for r in player_rows:
                attempts = (r.get('stats') or {}).get('att')
                if (str(r.get('team')) == str(team) and r.get('seasonType') == 2 and r.get('season') == season
                        and str(r.get('kickoff') or '') < str(kickoff) and isinstance(attempts, (int, float)) and attempts > 0):
                    games[(r.get('kickoff'), r.get('eventId'))].append((attempts, str(player)))
        recent = [max(games[key])[1] for key in sorted(games)[-3:]]
        return len(recent) == 3 and recent.count(str(athlete)) >= 2
    return False


def prep_list(trends, lines, picks, league_data, now, rules=None):
    """{league: {'day', 'rows'}}: up to six Prep List rows on the next football game day that has any.

    Every row is a fresh main line already in the trend shards, so no request or price is new."""
    import research_posts
    if rules is None:
        try:
            import direction
            import learning
            rules = direction.prep_rules(learning.load_policy(), now)
        except Exception:                                  # a missing or unreadable policy keeps the baseline
            import direction
            rules = dict(direction.PREP_BASE, dropped=[], clearsOnly=False)
    floors, dropped = rules.get('floors') or {}, set(rules.get('dropped') or [])
    held = {(r.get('gameId'), str(r.get('athleteId')), r.get('stat')) for r in lines
            if r.get('athleteId') and (r.get('roleSuspect') or r.get('priceSuspect'))}
    graded = {(r.get('gameId'), str(r.get('athleteId')), r.get('stat'), r.get('direction'), r.get('line'),
               r.get('book'), r.get('odds')): r.get('grade') or {} for r in lines if r.get('athleteId')}
    words = {word: key for key, word in pricing.WORDS.items()}
    on_card = {(p.get('gameId'), str(p.get('athleteId')), p.get('market') if p.get('market') in pricing.WORDS
                else words.get(str(p.get('market') or '').lower()))
               for p in picks if p.get('athleteId') and not p.get('result') and not p.get('historicalImport')
               and not hero_parlay(p) and not hero_pulled(p)}
    today = eastern_date(now).isoformat()
    by_league = defaultdict(list)
    for row in trends:
        athlete, stat, line, odds = str(row.get('athleteId')), row.get('stat'), row.get('line'), row.get('odds')
        seen, kickoff = instant(row.get('observedAt')), instant(row.get('kickoff'))
        team = (row.get('team') or {}).get('id')
        key = (row.get('gameId'), athlete, stat)
        if (row.get('kind') != 'main' or row.get('league') not in ('NFL', 'CFB') or not kickoff or kickoff <= now
                or day(row['kickoff']) < today or row.get('roleSuspect') or row.get('priceSuspect') or key in held
                or row.get('injuryStatus') or key in on_card or stat in dropped
                or not isinstance(line, (int, float)) or line == 0.5 or line < floors.get(stat, 0)
                or not isinstance(odds, (int, float)) or abs(odds) < 100 or odds < PREP_PRICE_FLOOR
                or row.get('book') not in research_posts.PUBLIC_BOOKS
                or not seen or seen > now or now - seen > timedelta(hours=4)
                or not prep_history_ok(row, rules)
                or not prep_role_ok(athlete, team, league_data.get(row['league'], {}), row.get('season'), row['kickoff'])):
            continue
        grade = graded.get((row.get('gameId'), athlete, stat, row.get('direction'), line, row.get('book'), odds)) or {}
        clears = (grade.get('calibrated') is True and (grade.get('view') or grade.get('tier')) in ('lean', 'strong')
                  and not grade.get('thin') and not grade.get('limited') and (grade.get('edge') or 0) > 0)
        if rules.get('clearsOnly') and not clears:
            continue
        logs = (league_data.get(row['league']) or {}).get('player_logs', {}).get(athlete, [])
        position = next((r.get('pos') for r in reversed(logs) if r.get('pos')), None)
        values = [h['value'] for h in row.get('history') or [] if isinstance(h.get('value'), (int, float))]
        hits = sum(1 for v in values if (v > line if row['direction'] == 'over' else v < line))
        by_league[row['league']].append({
            'league': row['league'], 'gameId': row.get('gameId'), 'kickoff': row['kickoff'], 'athleteId': athlete,
            'player': row.get('player'), 'team': (row.get('team') or {}).get('abbreviation'),
            'teamColor': (row.get('team') or {}).get('color'), 'pos': position, 'stat': stat,
            'direction': row['direction'], 'line': line, 'odds': odds, 'book': row.get('book'),
            'observedAt': row.get('observedAt'), 'hits': hits, 'games': len(values), 'clears': clears})
    out = {}
    for league, rows in by_league.items():
        first = min(day(r['kickoff']) for r in rows)
        chosen, players = [], set()
        for row in sorted((r for r in rows if day(r['kickoff']) == first),
                          key=lambda r: (-r['hits'] / r['games'], -r['games'], str(r['player']), -r['odds'])):
            if row['athleteId'] not in players:
                players.add(row['athleteId'])
                chosen.append(row)
        out[league] = {'day': first, 'rows': chosen[:PREP_ROWS]}
    return out


# ------------------------------------------------------------------ research

def build_research(context, reports, now):
    out = {'injuries': {}, 'changes': [], 'notes': []}
    for league in ('NFL', 'CFB'):
        block = (context.get('leagues') or {}).get(league) or {}
        teams = {}
        for team, data in (block.get('teams') or {}).items():
            listed = []
            for p in data.get('players', []):
                if str(p.get('status', '')).lower() == 'active':
                    continue
                try:
                    fresh = p.get('reportedAt') and now - features.when(p['reportedAt']) <= timedelta(days=21)
                except ValueError:
                    fresh = False
                if fresh:
                    listed.append({k: p.get(k) for k in ('id', 'name', 'position', 'status', 'injury', 'reportedAt', 'source')})
            if listed:
                teams[team] = {'name': data.get('name'), 'players': listed}
        out['injuries'][league] = {'teams': teams, 'checkedAt': block.get('checkedAt'), 'status': block.get('status'),
                                   'coverage': block.get('coverage')}
        out['changes'] += [{'league': league, **c} for c in (block.get('changes') or [])][-40:]
    recent = sorted(reports, key=lambda r: r.get('publishedAt') or '', reverse=True)[:12]
    for report in recent:
        note = {'league': report.get('league'), 'publishedAt': report.get('publishedAt'),
                'title': report.get('title') or report.get('headline'),
                'takeaways': report.get('takeaways') or [], 'weeklyReview': report.get('weeklyReview') or [],
                'watch': [{k: w.get(k) for k in ('id', 'title', 'gameId', 'why', 'needs', 'nextReviewAt', 'player')}
                          for w in report.get('gameWatch') or []]}
        if note['takeaways'] or note['weeklyReview'] or note['watch']:
            out['notes'].append(note)
    return out


# ------------------------------------------------------------------ build

def build(now=None):
    asset_versions.sync(ROOT / 'site', check=True)
    now = now or datetime.now(timezone.utc)
    slate = read(DATA / 'slate.json', {'games': []})
    reports = read(DATA / 'research.json', [])
    catalog = read(DATA / 'market-lines.json', {})
    identities = identity_colors(read(DATA / 'player-identity.json', {}))
    context = read(DATA / 'research-context.json', {})
    depth_charts = read(DATA / 'depth-charts.json', {}).get('teams', {})
    scoreboard = read(DATA / 'scoreboard.json', {})
    forecasts_v1 = {f['gameId']: f for f in read(DATA / 'forecasts.json', [])}
    records = features.load()
    stored = {f"{g['league']}-{g['eventId']}": g for g in records}
    forecasts = load_store('forecasts')
    captures = load_store('props')
    snap_players = snap_players_by_event()
    snaps = snaps_by_event(snap_players)
    names = {}
    for game in records:
        for p in game['players']:
            if p.get('name'):
                names[p['id']] = p['name']
    teams_meta = team_names(records, slate)
    # The current slate eventually rolls to the next season. Keep completed historical games available so an
    # older published play never loses its season/week/postseason identity when that happens.
    by_id = {key: {**game, 'id': key} for key, game in stored.items()}
    by_id.update({g['id']: g for g in slate.get('games', [])})
    first, latest = first_publications(reports)
    picks = [p for p in board_picks(first, latest, by_id, identities)]
    books = {gid: rows[-1] for gid, rows in load_store('odds').items()}
    lines = catalog_lines(catalog, by_id, identities, now) + game_market_lines(slate, now, books)

    if OUT.exists():
        shutil.rmtree(OUT)
    window = [g for g in slate.get('games', []) if g.get('league') in ('NFL', 'CFB')
              and now - WINDOW_BACK <= features.when(g['kickoff']) <= now + WINDOW_AHEAD]
    grading = defaultdict(list)
    for row in (read(DATA / 'scoreboard-games.json', {}) or {}).values():
        for r in row:
            grading[r['gameId']].append({k: r.get(k) for k in ('model', 'margin', 'total', 'side', 'ou', 'closeMargin',
                                                                'closeTotal', 'closerMargin', 'closerTotal')})
    cards = []
    league_data = {}
    for league in ('NFL', 'CFB'):
        league_records = [g for g in records if g['league'] == league]
        current = max((g['season'] for g in league_records), default=now.year)
        team_logs = features.team_logs(league_records)
        defense_logs = features.defense_logs(league_records)
        rank_model = model_v2.Model(league, league_records, now, current, targets=('margin',))
        active = [team for team, games in rank_model.counts.items() if games and not rank_model.fcs(team)]
        strength = rating_ranks({str(team): rank_model.margin.team(team) for team in active})
        league_data[league] = {'team_logs': team_logs, 'player_logs': features.player_logs(league_records),
                               'defense': defense_table(league, defense_logs, current),
                               'defense_logs': defense_logs, 'strength': strength,
                               'current': current, 'records': league_records}
    ticket_teams = annotate_tickets(picks, by_id, forecasts, league_data, identities)
    injuries = {}
    for league in ('NFL', 'CFB'):
        block = ((context.get('leagues') or {}).get(league) or {}).get('teams') or {}
        for team, data in block.items():
            injuries[team] = [{k: p.get(k) for k in ('id', 'name', 'position', 'status', 'injury', 'reportedAt')}
                              for p in data.get('players', []) if str(p.get('status', '')).lower() != 'active']
    # Grade every open line before anything is written, so the board and the game pages agree.
    appearances = defaultdict(int)
    last_season = defaultdict(int)     # (player, team) -> games the season before this one
    for game in records:
        current = league_data[game['league']]['current']
        for player in game['players']:
            if game['season'] == current:
                appearances[player['id']] += 1
            elif game['season'] == current - 1 and player.get('team') is not None:
                last_season[(player['id'], str(player['team']))] += 1
    # A role is thin when this season has under three games AND last season did not settle it either:
    # a player with eight or more games for the same team last year is not a one-game guess.
    established = {key for key, n in last_season.items() if n >= ESTABLISHED_GAMES}
    cfb = league_data['CFB']
    fbs = model_v2.fbs_teams([g for g in cfb['records'] if g['season'] >= cfb['current'] - 1])
    paused = learned_pauses()
    for line in lines:
        game = by_id.get(line.get('gameId'))
        snapshot = (pregame(forecasts.get(game['id'], []), game['kickoff']) or [None])[-1] if game else None
        fcs = bool(game) and game['league'] == 'CFB' and not {str(game['home']['id']), str(game['away']['id'])} <= fbs
        thin = bool(snapshot and snapshot.get('sparse')) \
            or bool(line.get('athleteId')) and appearances[str(line['athleteId'])] < 3
        # v2 compresses FBS-FCS blowouts badly enough that any chance it gives there would mislead.
        line['grade'] = None if fcs else grade_line(line, snapshot, thin)
        if line['grade'] and f"{game['league']}/{'spread' if line.get('market') == 'point spread' else 'total'}" in paused:
            line['grade']['performanceCaution'] = True
            line['grade']['performanceNeed'] = 3.0
            if (line['grade'].get('edge') or 0) < 3.0:
                line['grade']['tier'] = 'pass'
        line['gradeNote'] = 'FBS vs FCS: v2 is not reliable here' if fcs and line.get('state') == 'open' else None
    prop_store = load_store('prop-odds')
    prop_prices = {gid: rows[-1] for gid, rows in prop_store.items()}
    # College players have no ESPN feed of main lines: their board rows come from the priced feed's own main numbers.
    captures = {**feed_captures(prop_store, by_id, forecasts, names), **captures}
    # A stored capture can hold a line the game cannot produce; clean it before it reaches the board.
    for record in prop_prices.values():
        for book in (record.get('books') or {}).values():
            sharp_odds.drop_impossible(book.get('markets') or {})
    lines += prop_rows(captures, by_id, forecasts, names, appearances, identities, now, prop_prices, established,
                       calibration=learned_prop_calibration())
    for row in lines:
        if row.get('athleteId') and row.get('grade'):
            segment = f"{row['league']}/prop:{row.get('stat')}"
            market_record = next((r for r in (scoreboard.get('props') or {}).get('markets', [])
                                  if r.get('market') == row.get('stat')), {})
            closeness = market_record.get('closerThanLine') or [0, 0]
            behind = row['league'] == 'NFL' and market_record.get('graded', 0) >= 30 and closeness[0] < closeness[1]
            if segment in paused or behind:
                row['grade']['performanceCaution'] = True
                row['grade']['performanceNeed'] = 5.0
                if (row['grade'].get('edge') or 0) < 5.0:
                    row['grade']['tier'] = 'pass'
                    row['grade']['view'] = 'pass'
    guard_player_lines(lines, by_id, forecasts, league_data, now, prop_prices=prop_prices)
    for row in lines:
        if not row.get('roleSuspect'):
            continue
        game = by_id.get(row.get('gameId')) or {}
        snapshots = pregame(forecasts.get(row.get('gameId'), []), game.get('kickoff')) if game else []
        _, player = pricing.player_line(snapshots[-1], row.get('athleteId')) if snapshots else (None, None)
        role = role_sanity.VOLUME.get(row.get('stat'))
        if player and role:
            for stat, volume in role_sanity.VOLUME.items():
                field = pricing.PROJECTED.get(stat)
                if volume == role and field and field not in player.setdefault('underReview', []):
                    player['underReview'].append(field)
    lines = public_lines(lines, now)
    for row in lines:
        if row.get('athleteId') and row.get('stat') in ('passYds', 'att', 'cmp', 'recYds', 'rec'):
            game = by_id.get(row.get('gameId')) or {}
            snapshots = forecasts.get(row.get('gameId')) or []
            if game and snapshots:
                context_row = player_matchup_context(game, snapshots[-1], row)
                row['qbNews'] = qb_news(injuries.get(str(context_row.get('team')), [])) or None
    values = sheet_values(lines, now)
    trend_injuries = {league: {team: block.get('players', []) for team, block in
                      ((context.get('leagues') or {}).get(league, {}).get('teams') or {}).items()}
                      for league in ('NFL', 'CFB')}
    trends = season_trends.build(window, league_data, lines, prop_prices, now, trend_injuries)
    line_lookup = {(row.get('gameId'), str(row.get('athleteId')), row.get('stat'), row.get('direction'),
                    row.get('line'), row.get('book'), row.get('odds')): row for row in lines}
    for row in trends:
        matched = line_lookup.get((row.get('gameId'), str(row.get('athleteId')), row.get('stat'), row.get('direction'),
                                   row.get('line'), row.get('book'), row.get('odds')))
        if matched and (matched.get('roleSuspect') or matched.get('priceSuspect')):
            row['roleSuspect'] = bool(matched.get('roleSuspect'))
            row['priceSuspect'] = bool(matched.get('priceSuspect'))
        grade = (matched or {}).get('grade') or {}
        if isinstance(grade.get('projection'), (int, float)):
            row['projection'] = grade['projection']
            history_values = [h['value'] for h in (row.get('history') or [])[-10:] if isinstance(h.get('value'), (int, float))]
            average = sum(history_values) / len(history_values) if history_values else None
            row['uncertainGap'] = bool(average and abs(row['projection'] - average) / average > .3)
        if row.get('stat') in ('passYds', 'att', 'cmp', 'recYds', 'rec'):
            team = str((row.get('team') or {}).get('id') or '')
            row['qbNews'] = qb_news(trend_injuries.get(row['league'], {}).get(team, [])) or None
    prep = prep_list(trends, lines, picks, league_data, now)
    write_trends(trends, now)
    gap_rows = market_read.load_rows()
    for game in sorted(window, key=lambda g: (g['kickoff'], g['id'])):
        snaps_for = pregame(forecasts.get(game['id'], []), game['kickoff'])
        latest_snap = snaps_for[-1] if snaps_for else None
        block = market_read.read(game, latest_snap, books.get(game['id']), gap_rows) if game.get('state') == 'pre' else None
        card = game_card(game, forecasts_v1, latest_snap, names, identities, block, paused, values.get(game['id']),
                         league_data[game['league']]['strength'])
        card['fcs'] = game['league'] == 'CFB' and not {str(game['home']['id']), str(game['away']['id'])} <= fbs
        card['upsetWatch'] = research_views.upset_watch(card, now, latest_snap)
        cards.append(card)
        info = league_data[game['league']]
        favorites = favorite_lines(game, latest_snap, lines, now, info['player_logs'])
        write(OUT / 'games' / f"{game['id']}.json",
              game_detail(card, game, stored.get(game['id']), snaps_for, captures.get(game['id'], []), lines, picks,
                          names, info['team_logs'], info['defense'], injuries, depth_charts, info['records'],
                          snap_players, now, grading, favorites,
                          [r for r in trends if r['gameId'] == game['id']],
                          model_reads(game, latest_snap, lines, now, info['player_logs'])
                          if game.get('state') == 'pre' and features.when(game['kickoff']) > now else
                          archived_model_reads(game, latest_snap, captures.get(game['id'], []), names,
                                               now, info['player_logs'])))
    summary = {'live': [{k: g[k] for k in ('league', 'model', 'season', 'summary')} for g in scoreboard.get('live', [])],
               'backtest': [{k: g[k] for k in ('league', 'model', 'season', 'summary')} for g in scoreboard.get('backtest', [])],
               'picks': (scoreboard.get('picks') or {}).get('summary')}
    freshness = {'slate': slate.get('updatedAt'),
                 'boxscores': max((g['retrievedAt'] for g in records), default=None),
                 'forecasts': max((s['publishedAt'] for rows in forecasts.values() for s in rows), default=None),
                 'injuries': ((context.get('leagues') or {}).get('NFL') or {}).get('checkedAt'),
                 'props': max((c['retrievedAt'] for rows in captures.values() for c in rows), default=None)}
    runs = desk_runs()
    write(OUT / 'today.json', {'generatedAt': stamp(now), 'freshness': freshness,
                               'health': research_views.health(freshness, now), 'games': cards,
                               'picks': recent_picks(picks, now), 'historyFile': 'record.json', 'model': summary,
                               # Kitchen Ticket Today (decision 22): Prep List rows, the date line's last W-L, the
                               # stub's season record and the desk run times, all chosen here, never in the browser.
                               'prep': prep, 'lastSlate': last_slates(picks, eastern_date(now).isoformat()),
                               'season': season_records(picks, now), 'deskRuns': runs})
    import featured as featured_store     # the day's Pick of the Day, whose card feed.py draws under its -potd name
    write(OUT / 'today-hero.json', today_hero(picks, now, featured_store.of_day(eastern_date(now).isoformat()),
                                              ticket_teams, runs))
    write(OUT / 'record.json', {'generatedAt': stamp(now), 'picks': picks})
    generated = stamp(now)
    line_index = line_payload.manifest(lines, generated)
    write(OUT / 'lines.json', line_index)
    for league, name in line_index['files'].items():
        write(OUT / name, {'generatedAt': generated, 'league': league,
                           'lines': [row for row in lines if row.get('league') == league]})
    for league in ('NFL', 'CFB'):
        info = league_data[league]
        write(OUT / 'player-charts' / f'{league}.json',
              build_player_charts(league, window, forecasts, info['player_logs'], info['current'], lines, now))
        index, shards, leaders, leader_season = build_players(league, info['records'], snaps if league == 'NFL' else {}, teams_meta)
        write(OUT / 'players' / f'{league}.json', {'keys': list(LOG_KEYS), 'shards': SHARDS[league], 'players': index,
                                                   'leaders': leaders, 'season': leader_season})
        for shard, players in shards.items():
            write(OUT / 'players' / league / f'{shard}.json', {'keys': list(LOG_KEYS), 'players': players})
        directory, files = build_teams(league, info['records'], info['team_logs'], info['defense_logs'], teams_meta,
                                       identities, info['current'])
        if league == 'CFB':
            defense = directory.pop('defense')
            directory['defenseFile'] = 'teams/CFB-defense.json'
            write(OUT / 'teams' / 'CFB-defense.json', {'generatedAt': stamp(now), 'defense': defense})
        write(OUT / 'teams' / f'{league}.json', directory)
        for team, payload in files.items():
            write(OUT / 'teams' / league / f'{team}.json', payload)
    write(OUT / 'research.json', {'generatedAt': stamp(now), **build_research(context, reports, now)})
    write(OUT / 'sport-research.json', sport_research.build(now))
    write_vegas(now, records)
    return len(cards)


def write_vegas(now, records):
    """Vegas vs reality is one optional history panel. A failure drops only its file, so payload_budget reports
    vegas:missing and the view shows its retry state; it never blocks the publish of the record and the site."""
    try:
        payload = vegas.build(now, football=records)
    except Exception as error:
        print(f'Vegas vs reality skipped: {type(error).__name__}: {error}', file=sys.stderr)
        return False
    write(OUT / 'vegas.json', payload)
    return True


# Week 1's "My final five", from the screenshot import, which predates the favorite flag. The report is
# part of the record and is never edited, so the five are named here, as the old site named them.
FAVORITES_BEFORE_FLAG = {'w1-loveland-rec', 'w1-mayfield-pass', 'w1-otton-rec', 'w1-pollard-carries', 'w1-bateman-rec'}


def first_of(pick, recent, field):
    """A published field as first published; only when the first publication left it empty, a later report's."""
    return pick.get(field) if pick.get(field) is not None else recent.get(field)


def public_delivery(entry):
    """Only public delivery clocks, never captions, webhook URLs or platform IDs."""
    discord = entry.get('discord') or {}
    cancelled = bool(entry.get('cancelledAt') or entry.get('deletedAt'))
    return {'discordAt': discord.get('sentAt') if discord.get('state') == 'sent' else None,
            'xAt': entry.get('sentAt'), 'xDue': None if cancelled or entry.get('error') else entry.get('dueAt'),
            'restoredAt': entry.get('restoredAt'), 'cancelled': cancelled, 'failed': bool(entry.get('error'))}


def public_sentences(*values, limit=4):
    """Small structured display lists from already-published prose; never generates a new claim."""
    out = []
    for value in values:
        if isinstance(value, list):
            pieces = value
        else:
            pieces = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“])|[\r\n]+', str(value or ''))
        for piece in pieces:
            text = re.sub(r'^\s*[-•]\s*', '', str(piece)).strip()
            if text and text not in out:
                out.append(text)
            if len(out) >= limit:
                return out
    return out


def pick_market_type(pick, recent):
    current = pick.get('marketType') or recent.get('marketType')
    if current:
        return current
    if pick.get('athleteId'):
        return 'prop'
    text = f"{pick.get('market') or ''} {pick.get('title') or ''}".lower()
    direction = str(first_of(pick, recent, 'direction') or '').lower()
    if 'team total' in text:
        return 'teamTotal'
    if 'total' in text or direction in ('over', 'under'):
        return 'total'
    if 'spread' in text or re.search(r'\b[+-]\d', text):
        return 'spread'
    if 'moneyline' in text or ' winner' in text:
        return 'moneyline'
    return None


def board_picks(first, latest, by_id, identities):
    """The board's pick rows (first publication plus latest settlement), newest first.

    A pick is a favorite if it was one when first published; a later report cannot promote or demote it.
    """
    import featured as featured_store
    import pick_card
    try:
        reasons = json.loads((ROOT / 'data' / 'x-reasons.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        reasons = {}
    named = {entry.get('id') for entry in featured_store.load().values() if isinstance(entry, dict)}   # Picks of the Day
    try:                                  # the plays whose post went out on X: the Pick of the Day record counts those
        import receipts
        post_log = json.loads((ROOT / 'data' / 'x-posted.json').read_text(encoding='utf-8'))
        went_out = receipts.served(post_log)
        deliveries = {entry['id']: public_delivery(entry) for entry in post_log.get('posts', []) if entry.get('id')}
    except (OSError, ValueError):
        went_out = set()
        deliveries = {}
    rows = []
    for key, pick in first.items():
        recent = latest.get(key, {})
        game_ids = pick.get('gameIds') or ([pick.get('gameId')] if pick.get('gameId') else [])
        games = [by_id[game_id] for game_id in game_ids if game_id in by_id]
        game = games[0] if games else {}

        def common(field):
            values = {item.get(field) for item in games if item.get(field) is not None}
            return values.pop() if len(values) == 1 else pick.get(field)

        season = common('season')
        if season is None:
            match = re.match(r'^(?:NFL|CFB)-(20\d{2})(?:-|$)', str(key))
            season = int(match.group(1)) if match else None
        delivery = deliveries.get(key)
        restored = bool(delivery and delivery.get('restoredAt') and not recent.get('result'))
        entry_note = None if restored else recent.get('entryNote') or pick.get('entryNote')
        status = 'active' if restored else recent.get('status') or pick.get('status')
        reasoning = pick.get('reasoning') if isinstance(pick.get('reasoning'), dict) else {}
        probability = pick.get('probabilityAtPublication') or {}
        published_at = instant(pick.get('publishedAt'))
        quoted_at = instant(pick.get('quotedAt'))
        chance = probability.get('chance') if isinstance(probability, dict) else None
        calibrated = probability.get('calibrated') is not False if isinstance(probability, dict) else False
        rows.append({'id': key, 'league': pick.get('league'), 'kind': pick.get('kind'), 'title': pick.get('title'),
                     # The same title and one-line reason the play's X post carries, so the site reads like the post.
                     'displayTitle': pick_card.display_title(pick, game) if game else pick.get('title'),
                     'reason': reasons.get(key) if isinstance(reasons, dict) and isinstance(reasons.get(key), str) else None,
                     # A Pick of the Day pulled before its post went out never wears the star.
                     'featured': key in named and (key in went_out or not (recent.get('entryNote') or pick.get('entryNote'))),
                     'posted': key in went_out,
                     'delivery': delivery,
                     'market': pick.get('market') or recent.get('market') or (pricing.market_of(pick) if pick.get('athleteId') else None),
                     'riskUnits': pick.get('riskUnits'), 'modelLean': pick.get('modelLean') is True,
                     'earlyExit': recent.get('earlyExit') is True,
                     'player': pick.get('player'), 'athleteId': pick.get('athleteId'), 'position': pick.get('position'),
                     # The first publication's line and price; a play imported without them takes the ones a later
                     # report filled in (the Week 1 prices, marked assumed), never a change to one that had them.
                     'gameId': game_ids[0] if game_ids else None, 'gameIds': game_ids,
                     'season': season, 'seasonType': common('seasonType'), 'week': common('week'),
                     'line': first_of(pick, recent, 'line'),
                     'direction': first_of(pick, recent, 'direction'), 'book': provider_book(pick.get('book')),
                     'displayBook': display_book(pick.get('book')), 'odds': first_of(pick, recent, 'odds'),
                     'priceAssumed': pick.get('odds') is None and recent.get('priceAssumed') is True,
                     'priceNote': recent.get('priceNote') if pick.get('odds') is None else None,
                     'priceEstimated': pick.get('priceEstimated') is True,
                     'probabilityAtPublication': pick.get('probabilityAtPublication'),
                     'reasoning': pick.get('reasoning'),
                     'reasons': public_sentences(reasons.get(key) if isinstance(reasons, dict) else None,
                                                 reasoning.get('context'), pick.get('why'), limit=4),
                     'cautions': public_sentences(reasoning.get('cautions'), pick.get('risk'), limit=4),
                     'fairOddsAtPublication': fair_american(chance) if calibrated else None,
                     'quoteAgeMinutes': (max(0, round((published_at - quoted_at).total_seconds() / 60))
                                         if published_at and quoted_at and quoted_at <= published_at else None),
                     'projection': pick.get('projection'), 'confidence': pick.get('confidence'),
                     'favorite': pick.get('favorite') is True or key in FAVORITES_BEFORE_FLAG,
                     'marketType': pick_market_type(pick, recent), 'parlayType': pick.get('parlayType'),
                     'ladder': pick.get('ladder'),                         # a ladder rung's run, step and dollars (scripts/ladder.py)
                     'cutoff': pick.get('cutoff'), **cutoff_fields(pick), 'why': pick.get('why'),
                     'risk': pick.get('risk'), 'edge': pick.get('edge'), 'quotedAt': pick.get('quotedAt'),
                     'expiresAt': pick.get('expiresAt'), 'publishedAt': pick.get('publishedAt'),
                     'historicalImport': pick.get('historicalImport'), 'sources': pick.get('sources') or [],
                     'legs': pick.get('legs'), 'correlation': pick.get('correlation'), 'riskTier': pick.get('riskTier'),
                     'marketWindow': pick.get('marketWindow'), 'entryNote': entry_note,
                     'status': status,
                     'result': recent.get('result'), 'actual': recent.get('actual'), 'settledAt': recent.get('settledAt'),
                     'units': recent.get('units'),                         # saved when the play was graded
                     'settlementReason': recent.get('settlementReason'),
                     'settlementReviewSources': recent.get('settlementReviewSources'),
                     'injuryPlayers': recent.get('injuryPlayers'), 'resultSource': recent.get('resultSource'),
                     'kickoff': game.get('kickoff'),
                     'color': color(pick.get('league'), (game.get('home') or {}).get('abbreviation'), identities)})
    rows.sort(key=lambda p: p.get('publishedAt') or '', reverse=True)
    for row in rows:
        row['recordAsOfPublication'] = record_scope.summary(rows, row.get('publishedAt'))
    return rows


def grade_line(line, snapshot, thin):
    """v2's read on one open, priced line: its chance at the line, what the price needs, and a tier.

    The same arithmetic as the research desk (scripts/pricing.py). thin: the game or the player has
    too little this season for v2 to read as strong. None when v2 has no number for the line.
    """
    odds = line.get('odds')
    if line.get('state') != 'open' or not snapshot or not isinstance(odds, (int, float)) or abs(odds) < 100 \
            or not isinstance(line.get('line'), (int, float)):
        return None
    if line.get('gameMarket'):
        # A spread row is the home side unless it names the away side; its line is that side's own number.
        market, side, athlete = ('spread', line.get('side') or 'home', None) if line['market'] == 'point spread' \
            else ('total', line.get('direction'), None)
    else:
        market, side, athlete = pricing.market_of(line), str(line.get('direction') or '').lower(), line.get('athleteId')
        if not market or side not in ('over', 'under') or not athlete:
            return None
    try:
        p = pricing.price(snapshot, market, side, float(line['line']), int(odds), athlete)
    except ValueError:  # no projection for this player or market
        return None
    chance_display = p['chance'] if p['calibrated'] and not thin and not line.get('limited') else None
    return {'chance': p['chance'], 'raw': p['rawChance'], 'calibrated': p['calibrated'], 'push': p['push'],
            'needs': p['breakEven'], 'edge': p['edgePoints'],
            'projection': p['projection'], 'thin': thin, 'tier': pricing.tier(p['edgePoints'], thin),
            'model': p['model'], 'snapshotAt': p['snapshotAt'], 'fairOdds': fair_american(p['chance']) if p['calibrated'] else None,
            'ev': round(p['chance'] * (1 + pricing.payout(int(odds))) - 1, 3), 'chanceDisplay': chance_display,
            'range80': p.get('range80')}


def guard_player_lines(lines, games, forecasts, league_data, now, logger=print, prop_prices=None):
    """Withhold misleading player grades without changing forecasts or history."""
    qb_changes = {}
    for row in lines:
        athlete = str(row.get('athleteId') or '')
        if not athlete:
            continue
        game = games.get(row.get('gameId')) or {}
        snapshots = pregame(forecasts.get(row.get('gameId'), []), game.get('kickoff')) if game else []
        snapshot = snapshots[-1] if snapshots else None
        side, forecast = pricing.player_line(snapshot, athlete) if snapshot else (None, None)
        team = (game.get(side) or {}).get('id') if side else None
        league = game.get('league')
        market = row.get('stat') or pricing.market_of(row)
        all_logs = (league_data.get(league) or {}).get('player_logs', {})
        logs = all_logs.get(athlete, [])
        caution = role_sanity.assess(forecast, logs, team, market, game.get('season'))
        qb_key = (row.get('gameId'), side)
        if qb_key not in qb_changes:
            players = (((snapshot or {}).get('players') or {}).get(side) or {}).get('players') or []
            qb_changes[qb_key] = role_sanity.quarterback_change(players, all_logs, team, game.get('season'), league, game.get('kickoff'))
        qb_caution = qb_changes[qb_key] if forecast and role_sanity.affected_by_qb_change(athlete, forecast.get('pos'), market, qb_changes[qb_key]) else None
        grade = row.get('grade') or {}
        chance = grade.get('chance') if grade.get('calibrated') else None
        bad_price = role_sanity.price_suspect(row.get('odds'), chance)
        quote_problem = None
        if row.get('state') == 'open' and prop_prices is not None:
            quotes = price_quotes(prop_prices.get(row.get('gameId')), market, row.get('player'), row.get('line'))
            quote_problem = role_sanity.quote_issue(quotes, row.get('book'), row.get('line'),
                                                    row.get('direction'), row.get('odds'))
        if caution or qb_caution:
            row['roleSuspect'] = True
            row['grade'] = None
            row['gradeNote'] = 'Projection under review'
            # Which hold, and for a workload hold the real recent full-game volumes (never the held projection).
            row['roleHold'] = 'workload' if caution else 'qb'
            if caution:
                row['recentFull'] = caution['recentFull']
                row['recentVolume'] = caution['volume']
            reason = (f"{caution['projected']:g} {caution['volume']} vs "
                      f"{caution['recentFullAverage']:g} last-three full-game average") if caution else qb_caution['reason']
            logger(f"role-sanity: {row.get('id') or row.get('title')}: {reason}")
        if bad_price or quote_problem:
            row['priceSuspect'] = True
            row['grade'] = None
            row['gradeNote'] = 'Price check failed' if not (caution or qb_caution) else 'Projection and price under review'
            logger(f"price-sanity: {row.get('id') or row.get('title')}: "
                   f"{quote_problem or str(row.get('odds')) + ' outside main-line check'}")


def sheet_values(lines, now=None):
    """game -> best priced side for its spread and total, using the already graded Board rows.

    The line, price and named book stay together. A projection gap alone never becomes a value marker.
    """
    out = defaultdict(dict)
    for row in lines:
        grade = row.get('grade') or {}
        if not row.get('gameMarket') or row.get('state') != 'open' or not grade \
                or not isinstance(row.get('odds'), (int, float)):
            continue
        seen = instant(row.get('observedAt'))
        if now is not None and (seen is None or now - seen > ODDS_FRESH):
            continue
        market = ('spread' if row.get('market') == 'point spread' else
                  'total' if row.get('market') == 'total points' else None)
        side = row.get('side') if market == 'spread' else row.get('direction') if market == 'total' else None
        if not market or side not in ('home', 'away', 'over', 'under'):
            continue
        value = {'side': side, 'line': row.get('line'), 'odds': int(row['odds']), 'book': row.get('book'),
                 'observedAt': row.get('observedAt'),
                 **{k: grade.get(k) for k in ('chance', 'needs', 'edge', 'tier', 'performanceCaution',
                                               'performanceNeed', 'thin')}}
        old = out[row['gameId']].get(market)
        score = value.get('edge') if isinstance(value.get('edge'), (int, float)) else -999
        old_score = old.get('edge') if old and isinstance(old.get('edge'), (int, float)) else -999
        if old is None or score > old_score:
            out[row['gameId']][market] = value
    return dict(out)


def person(name):
    """A player's name, flattened enough to match one book feed against another."""
    text = re.sub(r"[^a-z ]", ' ', str(name or '').lower())
    words = [w for w in text.split() if w not in ('jr', 'sr', 'ii', 'iii', 'iv', 'v')]
    return ' '.join(words)


def price_quotes(record, market, name, anchor=None):
    """Every book's quote for one player's market: [(book, line, over, under)].

    ESPN's feed carries the book's main number, so when a book's ladder holds that same
    number it is the rung we price, whatever the odds feed flagged as its main line. One
    feed said a quarterback's main completions line was 34.5 with 19.5 as the alternate.
    """
    if not record:
        return []
    want = person(name)
    out = []
    for book, entry in (record.get('books') or {}).items():
        players = (entry.get('markets') or {}).get(market) or {}
        match = next((q for who, q in players.items() if person(who) == want), None)
        if not match or not isinstance(match.get('line'), (int, float)):
            continue
        if anchor is not None and match['line'] != anchor:
            rung = next((a for a in match.get('alternates') or [] if a.get('line') == anchor), None)
            if rung:
                match = rung
        over, under = match.get('over'), match.get('under')
        if any(role_sanity.price_suspect(odds, None) for odds in (over, under)
               if isinstance(odds, (int, float))):
            continue
        if isinstance(over, (int, float)) and isinstance(under, (int, float)) \
                and not .99 <= pricing.break_even(over) + pricing.break_even(under) <= 1.15:
            continue
        out.append((book, match['line'], match.get('over'), match.get('under')))
    return out


ESTABLISHED_GAMES = 8


def settled_role(athlete, team, appearances, established):
    """Three games this season, or the same job for the same team last season."""
    return appearances[str(athlete)] >= 3 or (str(athlete), str(team)) in (established or set())


def learned_pauses():
    """Legacy `paused` policy flags now mean performance caution and a higher admission threshold."""
    try:
        import learning
        return {segment for segment, entry in (learning.load_policy().get('segments') or {}).items()
                if isinstance(entry, dict) and entry.get('paused')}
    except Exception:
        return set()


def learned_prop_calibration():
    """What the learning loop shipped for each league's player chances (data/learning/policy.json):
    {league: (k, minimum calibrated edge in points)}. The board then shows the chance the desk acts on."""
    try:
        import learning
        policy = learning.load_policy()
    except Exception:                      # no policy yet: the board reads raw, as it always did
        return {}
    need = float(((policy.get('knobs') or {}).get('prop.minCalibratedEdge') or {}).get('value') or 0.0)
    return {key.split('/')[0]: (float(entry['k']), need) for key, entry in (policy.get('calibration') or {}).items()
            if key.endswith('/prop') and isinstance(entry, dict) and entry.get('k') is not None}


PROP_OWN_CALIBRATION = {'CFB'}   # leagues whose player chances wait for their own calibration (gates.OWN_CALIBRATION)
FEED_SOURCE = 'https://sharpapi.io/'


def feed_captures(prop_store, by_id, forecasts, names, leagues=('CFB',)):
    """gameId -> captures in the shape of ESPN's (retrievedAt, source, provider, lines) for games ESPN's feed does not
    carry: one per prop-odds record, each player's main number (sharp_odds.main_lines), matched to the forecast's
    players by name."""
    out = {}
    for gid, rows in prop_store.items():
        game = by_id.get(gid)
        if not game or game.get('league') not in leagues:
            continue
        snapshot = (pregame(forecasts.get(gid, []), game['kickoff']) or [None])[-1]
        if not snapshot:
            continue
        ids = {person(names.get(p['id'])): p['id'] for side in ('home', 'away')
               for p in ((snapshot.get('players') or {}).get(side) or {}).get('players', []) if names.get(p['id'])}
        caps = []
        for record in rows:
            lines = sharp_odds.main_lines(record, lambda name: ids.get(person(name)))
            if lines:
                caps.append({'retrievedAt': record['retrievedAt'], 'source': FEED_SOURCE, 'lines': lines,
                             'provider': 'DraftKings' if 'draftkings' in (record.get('books') or {}) else 'FanDuel'})
        if caps:
            out[gid] = caps
    return out


def prop_rows(captures, by_id, forecasts, names, appearances, identities, now, prices=None, established=None, calibration=None):
    """DraftKings' main player lines for upcoming NFL games as board rows, with v2's lean at each.

    ESPN relays the lines without prices, so the rows carry no odds and cannot join a ticket. They
    are graded on v2's raw chance alone: 60% or better on the lean side reads as a slight lean and
    never stronger, because player projections have no graded history against a line yet. A player
    with under three games this season stays grey: a role set by one or two games is the model's
    most common error, and the biggest early-season gaps are those.

    calibration ({league: (k, minimum edge)}, from learned_prop_calibration) shrinks each raw chance the way the
    graded record says it should (50% + k * (raw - 50%)); the site then shows a priced prop as a lean (grade
    'view') only when that calibrated chance also clears its price, the rule the desk's gates apply before
    publishing. grade 'tier' stays the written raw rule: it chooses what the gates judge, and the refusals it
    produces are the evidence learning uses to ease or tighten.
    """
    calibration = calibration or {}
    rows = []
    for gid, caps in captures.items():
        game = by_id.get(gid)
        if not game or game.get('state') != 'pre' or features.when(game['kickoff']) <= now:
            continue
        capture = caps[-1]
        priced = (prices or {}).get(gid)
        snapshot = (pregame(forecasts.get(gid, []), game['kickoff']) or [None])[-1]
        for athlete, markets in capture['lines'].items():
            side, player = pricing.player_line(snapshot, athlete) if snapshot else (None, None)
            for key, (main, opening) in markets.items():
                if key not in pricing.PROJECTED:
                    continue
                grade, lean = None, 'over'
                if player and pricing.PROJECTED[key] in player:
                    mean, low, high = player[pricing.PROJECTED[key]]
                    sd = (high - mean) / pricing.Z80
                    if sd > 0:
                        over, push, under = pricing.chances(mean, sd, main)
                        lean = 'over' if over >= under else 'under'
                        chance = max(over, under)
                        thin = not settled_role(athlete, game[side]['id'] if side else None, appearances, established)
                        limited = bool(player.get('limited'))
                        k = (calibration.get(game['league']) or (None, 0.0))[0]
                        shown = 0.5 + k * (chance - 0.5) if k is not None else chance
                        grade = {'chance': round(shown, 3), 'raw': round(chance, 3), 'calibrated': k is not None,
                                 'push': round(push, 3), 'needs': None, 'edge': round(100 * (shown - 0.5), 1),
                                 'projection': round(mean, 1), 'thin': thin, 'games': appearances[str(athlete)],
                                 'limited': limited,
                                 # A questionable player is a coin flip on snaps before it is a read on volume.
                                 'tier': 'lean' if chance >= 0.6 and not thin and not limited else 'pass',
                                 'model': snapshot['model'], 'snapshotAt': snapshot['publishedAt']}
                        if k is None and game['league'] in PROP_OWN_CALIBRATION:
                            grade['unproven'] = True        # graded against the line before it is played
                name = names.get(athlete, f'Athlete {athlete}')
                team = game[side]['abbreviation'] if side else None
                # A price turns a read into a line that can be graded against what it needs.
                quotes = price_quotes(priced, key, name, main)
                row = {'id': f'prop-{gid}-{athlete}-{key}', 'league': game['league'], 'gameId': gid,
                       'player': name, 'athleteId': str(athlete), 'position': player['pos'] if player else None,
                       'market': pricing.WORDS[key], 'direction': lean, 'line': main, 'odds': None,
                       'book': 'DraftKings', 'state': 'unpriced', 'kickoff': game['kickoff'],
                       'observedAt': capture['retrievedAt'], 'source': capture['source'],
                       'title': f'{name} {lean} {main:g} {pricing.WORDS[key]}', 'gameMarket': False,
                       'color': color(game['league'], team, identities), 'grade': grade,
                       'gradeNote': None if grade else 'no v2 projection for this player',
                       'opened': opening, 'stat': key}
                side_quotes = [(book, line, over if lean == 'over' else under)
                               for book, line, over, under in quotes if (over if lean == 'over' else under) is not None]
                if side_quotes:
                    # Shop the adjusted expected return, as the desk does. Without a projection we can only
                    # order the reference quotes by line and price; they cannot become an official lean.
                    book, line, odds = sorted(side_quotes, key=lambda q: (q[1] if lean == 'over' else -q[1],
                                                                          -pricing.cents(q[2])))[0]
                    if snapshot and player and pricing.PROJECTED[key] in player:
                        def quote_value(q):
                            try:
                                value = pricing.price(snapshot, key, lean, float(q[1]), int(q[2]), athlete)
                                k = (calibration.get(game['league']) or (None, 0.0))[0]
                                return pricing.calibrated_prop(value, {'k': k})['evPerUnit'], q[0]
                            except (ValueError, KeyError):
                                return float('-inf'), q[0]
                        book, line, odds = max(side_quotes, key=quote_value)
                    row.update({'line': line, 'odds': odds, 'book': BOOK_NAMES.get(book, book), 'state': 'open',
                                'observedAt': priced['retrievedAt'], 'source': priced['source'],
                                'title': f'{name} {lean} {line:g} {pricing.WORDS[key]}',
                                'books': [{'book': BOOK_NAMES.get(b, b), 'line': l, 'odds': o}
                                          for b, l, o in sorted(side_quotes)]})
                    if snapshot and player and pricing.PROJECTED[key] in player:
                        try:
                            p = pricing.price(snapshot, key, lean, float(line), int(odds), athlete)
                            settled = settled_role(athlete, game[side]['id'] if side else None, appearances, established)
                            limited = bool(player.get('limited'))
                            k, need = calibration.get(game['league']) or (None, 0.0)
                            p = pricing.calibrated_prop(p, {'k': k})
                            chance, edge = p['chance'], p['edgePoints']
                            calibrated = p['calibrated'] or k is not None
                            row['grade'] = {'chance': chance, 'raw': p['rawChance'], 'calibrated': calibrated,
                                            'push': p['push'], 'needs': p['breakEven'], 'edge': edge,
                                            'projection': p['projection'], 'thin': not settled, 'limited': limited,
                                            'fairOdds': fair_american(chance) if calibrated else None,
                                            'ev': round(chance * (1 + pricing.payout(int(odds))) - 1, 3),
                                            'chanceDisplay': chance if calibrated and settled and not limited else None,
                                            'range80': p.get('range80'),
                                            'games': appearances[str(athlete)],
                                            'rawTier': 'lean' if p['rawChance'] >= 0.6 and settled and not limited else 'pass',
                                            # Raw candidates still reach the gates for an auditable refusal.
                                            # Both public labels require positive learned value.
                                            'tier': 'lean' if p['rawChance'] >= 0.6 and settled and not limited
                                                    and k is not None and edge > 0 and edge >= need else 'pass',
                                            'view': 'lean' if p['rawChance'] >= 0.6 and settled and not limited
                                                    and k is not None and edge > 0 and edge >= need else 'pass',
                                            'model': p['model'], 'snapshotAt': p['snapshotAt']}
                            if k is None and game['league'] in PROP_OWN_CALIBRATION:
                                row['grade']['unproven'] = True     # the site says it is being graded before it is played
                        except ValueError:
                            pass
                rows.append(row)
    return rows


BOOK_NAMES = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel', 'betmgm': 'BetMGM', 'caesars': 'Caesars',
              'betrivers': 'BetRivers', 'espnbet': 'ESPN BET', 'fanatics': 'Fanatics'}
ODDS_FRESH = timedelta(hours=12)   # an older multi-book capture is history, not a board row

def favorite_hit_rates(game, row, player_logs):
    """Recent and season-to-date results against this exact player line, before this game's kickoff."""
    athlete, stat = str(row.get('athleteId') or ''), row.get('stat')
    if not athlete or stat not in LOG_KEYS or not isinstance(row.get('line'), (int, float)):
        return None
    before = features.when(game['kickoff'])
    played = sorted((r for r in (player_logs or {}).get(athlete, [])
                     if features.when(r['kickoff']) < before and r.get('seasonType') == 2
                     and isinstance((r.get('stats') or {}).get(stat), (int, float))),
                    key=lambda r: features.when(r['kickoff']))
    direction, line = str(row.get('direction') or '').lower(), float(row['line'])

    def block(rows):
        values = [(r.get('stats') or {})[stat] for r in rows]
        hits = sum(value < line if direction == 'under' else value > line for value in values)
        return {'hits': hits, 'games': len(values), 'rate': round(100 * hits / len(values)),
                'values': values} if values else None

    last = block(played[-10:])
    season = block([r for r in played if r.get('season') == game.get('season')])
    return {'last': last, 'season': season} if last or season else None


def player_matchup_context(game, snapshot, row):
    """Team/opponent context for one projected player, using only this game's stored snapshot."""
    athlete = str(row.get('athleteId') or '')
    position = row.get('position')
    for side in ('home', 'away'):
        players = ((((snapshot or {}).get('players') or {}).get(side) or {}).get('players') or [])
        player = next((candidate for candidate in players if str(candidate.get('id')) == athlete), None)
        if not player:
            continue
        other = 'away' if side == 'home' else 'home'
        return {'team': str(game[side].get('id') or ''),
                'teamAbbr': game[side].get('abbreviation'),
                'opponent': str(game[other].get('id') or ''),
                'opponentAbbr': game[other].get('abbreviation'),
                'position': position or player.get('pos')}
    return {'position': position}


def archived_model_reads(game, snapshot, captures, names, now, player_logs=None):
    """Reconstruct comparisons only from pregame captures, never live offers or postgame stats."""
    cutoff = features.when(game['kickoff'])
    eligible = [c for c in captures if instant(c.get('retrievedAt')) and instant(c['retrievedAt']) < cutoff]
    if not snapshot or not eligible or instant(snapshot.get('publishedAt')) is None \
            or instant(snapshot['publishedAt']) >= cutoff:
        return []
    capture = max(eligible, key=lambda c: c['retrievedAt'])
    rows = []
    for athlete, markets in capture.get('lines', {}).items():
        _, player = pricing.player_line(snapshot, athlete)
        if not player or player.get('limited'):
            continue
        for stat, values in markets.items():
            projected = player.get(pricing.PROJECTED.get(stat))
            if not projected or not values or not isinstance(values[0], (int, float)):
                continue
            mean, line = projected[0], values[0]
            direction = 'over' if mean > line else 'under'
            rows.append({'id': f"archive-{athlete}-{stat}", 'gameId': game['id'], 'state': 'unpriced',
                         'athleteId': str(athlete), 'stat': stat, 'market': pricing.WORDS[stat],
                         'line': line, 'direction': direction, 'observedAt': capture['retrievedAt'],
                         'title': f"{names.get(str(athlete), athlete)} {direction} {line:g} {pricing.WORDS[stat]}",
                         'grade': {'projection': mean}})
    return model_reads(game, snapshot, rows, now, player_logs, archived=True)


def model_reads(game, snapshot, lines, now, player_logs=None, archived=False):
    """Descriptive projection-side research, deliberately independent of official/value admission.

    Never turn a performance warning into false confidence or a mean gap into a win probability.
    Keep the exact quote's side, and omit limited roles and unavailable projections.
    """
    if not snapshot or (not archived and (game.get('state') != 'pre' or features.when(game['kickoff']) <= now)):
        return []
    out, seen_keys = [], set()
    for row in lines:
        grade = row.get('grade') or {}
        mean, line = grade.get('projection'), row.get('line')
        if row.get('gameId') != game['id'] or row.get('state') not in ('open', 'unpriced') \
                or grade.get('limited') or not isinstance(mean, (int, float)) \
                or not isinstance(line, (int, float)):
            continue
        spread = row.get('market') == 'point spread'
        if spread:
            projected_line = -mean if row.get('side', 'home') == 'home' else mean
            gap = line - projected_line
            comparison = f"Our spread {projected_line:+g} vs line {line:+g}: {gap:.1f} points toward this side."
        else:
            gap = (mean - line) * (-1 if row.get('direction') == 'under' else 1)
            comparison = f"We project {mean:g} vs {line:g}: {abs(mean - line):.1f} {row.get('market', '')} {'below' if mean < line else 'above'} the line."
        if gap <= 0:
            continue
        key = (row.get('athleteId'), row.get('market'), row.get('side'), row.get('direction'))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        warnings = ['Pregame comparison only—not a live line or a previously posted pick.'] if archived else []
        if grade.get('performanceCaution'):
            warnings.append(f"Performance caution: an official pick needs at least {grade.get('performanceNeed', 5):g} adjusted points above its price.")
        if grade.get('thin'):
            warnings.append('Small sample: the player role or team history is not established.')
        if grade.get('unproven') or not grade.get('calibrated'):
            warnings.append('No validated price advantage yet.')
        if game.get('league') == 'CFB' and spread and gap >= 7:
            warnings.append('Large college disagreement: opponent strength and changing roles add uncertainty.')
        observed = instant(row.get('observedAt'))
        fresh = observed is not None and timedelta(0) <= now - observed <= timedelta(hours=4)
        priced = isinstance(row.get('odds'), (int, float)) and fresh and not archived
        if not fresh:
            warnings.append('Older or unverified line snapshot; check the current line at your book.')
        elif not priced:
            warnings.append('Line captured without a verified price; value cannot be assessed.')
        context = player_matchup_context(game, snapshot, row) if row.get('athleteId') else {}
        out.append({'id': f"read-{row['id']}", 'sourceId': row['id'], 'title': row['title'],
                    'kind': 'game' if row.get('gameMarket') else 'player',
                    'athleteId': row.get('athleteId'), 'market': row.get('market'), 'stat': row.get('stat'),
                    'direction': row.get('direction'), 'position': context.get('position'),
                    'team': context.get('team'), 'teamAbbr': context.get('teamAbbr'),
                    'opponent': context.get('opponent'), 'opponentAbbr': context.get('opponentAbbr'),
                    'line': line, 'projection': mean, 'comparison': comparison,
                    'chance': grade.get('chance') if priced and grade.get('calibrated') else None,
                    'needs': grade.get('needs') if priced else None,
                    'edge': grade.get('edge') if priced and grade.get('calibrated') else None,
                    'clearsPrice': bool(priced and grade.get('calibrated') and not grade.get('thin')
                                        and not grade.get('limited') and not grade.get('unproven')
                                        and (grade.get('view') == 'lean' or grade.get('tier') in ('lean', 'strong'))
                                        and isinstance(grade.get('edge'), (int, float)) and grade['edge'] > 0),
                    'book': row.get('book'), 'odds': row.get('odds') if priced else None,
                    'observedAt': row.get('observedAt'), 'snapshotAt': snapshot['publishedAt'],
                    'warnings': warnings, 'performanceCaution': bool(grade.get('performanceCaution')), 'archived': archived,
                    'history': None if row.get('gameMarket') else favorite_hit_rates(game, row, player_logs)})
    return sorted(out, key=lambda r: (r['performanceCaution'], r['kind'] != 'game', r['market'] or '', r['title']))


def favorite_lines(game, snapshot, lines, now, player_logs=None):
    """Every current main line the calibrated Board actually likes for one game, best price edge first.

    These are not extra published plays. A player line qualifies only when the Board's learned/calibrated view says
    lean; a spread or total uses the same lean/strong tier shown on the Board. Alternates are a reader's optional
    choice and never replace the main line in this list.
    """
    if not snapshot or game.get('state') != 'pre' or features.when(game['kickoff']) <= now:
        return []
    out = []
    for row in lines:
        grade = row.get('grade') or {}
        seen = instant(row.get('observedAt'))
        liked = grade.get('tier') in ('lean', 'strong') if row.get('gameMarket') else grade.get('view') == 'lean'
        if row.get('gameId') != game['id'] or row.get('state') != 'open' or not liked \
                or grade.get('limited') or grade.get('thin') \
                or not isinstance(row.get('odds'), (int, float)) or seen is None or now - seen > ODDS_FRESH:
            continue
        history = None if row.get('gameMarket') else favorite_hit_rates(game, row, player_logs)
        context = player_matchup_context(game, snapshot, row) if row.get('athleteId') else {}
        out.append({'id': f"favorite-{row['id']}", 'sourceId': row['id'], 'kind': 'game' if row.get('gameMarket') else 'player',
                    'title': row['title'], 'player': row.get('player'), 'athleteId': row.get('athleteId'),
                    'position': context.get('position'), 'stat': row.get('stat'),
                    'team': context.get('team'), 'teamAbbr': context.get('teamAbbr'),
                    'opponent': context.get('opponent'), 'opponentAbbr': context.get('opponentAbbr'),
                    'book': row['book'], 'odds': int(row['odds']), 'line': row.get('line'),
                    'market': row.get('market'), 'direction': row.get('direction'), 'side': row.get('side'),
                    'chance': grade.get('chance'), 'needs': grade.get('needs'), 'edge': grade.get('edge'),
                    'calibrated': grade.get('calibrated'),
                    'projection': grade.get('projection'), 'observedAt': row.get('observedAt'),
                    'source': row.get('source'), 'alternate': False, 'history': history,
                    'score': grade.get('edge') or 0.0})
    return [{k: v for k, v in row.items() if k != 'score'} for row in
            sorted(out, key=lambda row: (-row['score'], -float(row.get('chance') or 0), row['title']))]


def book_rows(game, record):
    """Four board rows from a multi-book capture: each side at its best number and price, all books listed."""
    home, away = game['home']['abbreviation'], game['away']['abbreviation']
    rows = []
    for side, kind, name in (('home', 'spread', 'point spread'), ('away', 'spread', 'point spread'),
                             ('over', 'total', 'total points'), ('under', 'total', 'total points')):
        top = odds_api.best(record, side)
        if not top:
            continue
        key, line, price = top
        quotes = []
        for book, entry in record['books'].items():
            block = entry.get(kind)
            if not block:
                continue
            if kind == 'spread':
                quotes.append({'book': BOOK_NAMES.get(book, book), 'line': block['home'] if side == 'home' else -block['home'],
                               'odds': block['homePrice'] if side == 'home' else block['awayPrice']})
            else:
                quotes.append({'book': BOOK_NAMES.get(book, book), 'line': block['line'],
                               'odds': block['over'] if side == 'over' else block['under']})
        title = (f"{home if side == 'home' else away} {line:+g}" if kind == 'spread'
                 else f"{away} @ {home} {side} {line:g}")
        rows.append({'id': f"game-{game['id']}-{side}", 'league': game['league'], 'gameId': game['id'],
                     'market': name, 'line': line, 'odds': price if price != -1000 else None,
                     'direction': side if kind == 'total' else None, 'side': side if kind == 'spread' else None,
                     'book': BOOK_NAMES.get(key, key),
                     'books': sorted(quotes, key=lambda q: q['book']), 'state': 'open', 'kickoff': game['kickoff'],
                     'observedAt': record['retrievedAt'], 'title': title, 'gameMarket': True,
                     'marketWindow': 'Full game', 'move': None})
    return rows


def game_market_lines(slate, now, captures=None):
    """Current spread and total for each upcoming game, as board rows.

    With a fresh multi-book capture, each side gets its best number and price and the
    book is named. Otherwise ESPN's DraftKings feed prices the home side of the spread
    and both sides of the total, so those are the rows; the away spread has no quoted
    price and is left out.
    """
    out = []
    for game in slate.get('games', []):
        m = market(game)
        if not m or game.get('state') != 'pre' or features.when(game['kickoff']) <= now:
            continue
        record = (captures or {}).get(game['id'])
        if record and now - features.when(record['retrievedAt']) <= ODDS_FRESH:
            out += book_rows(game, record)
            continue
        home, away = game['home']['abbreviation'], game['away']['abbreviation']
        rows = []
        if m['spread'] is not None:
            rows.append(('spread', 'point spread', m['spread'], m['spreadOdds'], f"{home} {m['spread']:+g}", None))
        if m['total'] is not None:
            rows += [('over', 'total points', m['total'], m['overOdds'], f"{away} @ {home} over {m['total']:g}", 'over'),
                     ('under', 'total points', m['total'], m['underOdds'], f"{away} @ {home} under {m['total']:g}",
                      'under')]
        for kind, name, value, odds, title, direction in rows:
            out.append({'id': f"game-{game['id']}-{kind}", 'league': game['league'], 'gameId': game['id'],
                        'market': name, 'line': value, 'odds': odds, 'direction': direction,
                        'book': m['book'], 'state': 'open', 'kickoff': game['kickoff'],
                        'observedAt': game.get('marketRetrievedAt'), 'title': title, 'gameMarket': True,
                        'marketWindow': 'Full game', 'move': m['spreadMove'] if kind == 'spread' else None})
    return out


def main():
    count = build()
    size = sum(p.stat().st_size for p in OUT.rglob('*.json'))
    files = sum(1 for _ in OUT.rglob('*.json'))
    print(f'Built {files} page files ({size // 1024} KB) covering {count} games in the window.')


if __name__ == '__main__':
    main()
