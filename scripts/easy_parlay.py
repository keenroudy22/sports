"""The easy fun parlay: player props at their easier alternate lines ("Drake London 40+ receiving yards"), one leg
per game, where our projection clears the line with room to spare, priced leg by leg at the book's own
alternate-line prices, at a quarter unit.

It is never called value. Our player chances are tuned against main lines (and learning found them too confident
even there), so on these easier lines they can say "clears comfortably", not "beats the price". The ticket says it
is for fun, and its record is kept with the longshots, apart from the straight picks.

Prices: The Odds API's DraftKings and FanDuel alternate lines, two markets, one fetch per NFL game per day (two
credits a game), cached for a few hours in ~/.config/keenroudy/alt-props/, and only while the month's credits clear
a reserve. A ticket is only ever built from a fetch younger than FRESH.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import gates
import parlay
import pricing
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl'
SOURCE = 'https://the-odds-api.com/'
CACHE = Path.home() / '.config' / 'keenroudy' / 'alt-props'
MARKETS = {'player_reception_yds_alternate': 'recYds', 'player_rush_yds_alternate': 'rushYds'}   # two credits a game
BOOKS = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}
MIN_CHANCE = 0.80              # our projection's chance the player clears the easier line
PRICE_RANGE = (-350, -150)     # a leg worth its place on the ticket: not a near-certainty, not a coin flip
MIN_GAP = 0.08                 # our chance at least this far above the chance the price implies
LEGS = 3
TARGET = (150, 700)            # a nice parlay pays +150 to +700
STAKE = 0.25
RESERVE = 120                  # credits this ticket never spends: the line captures the model runs on come first
FRESH = timedelta(hours=4)     # prices older than this are not published
LEAD = timedelta(minutes=90)   # a game this close to kickoff is left off


def name_key(name):
    """'Kenneth Walker III' and 'Kenneth Walker' are the same player to the matcher."""
    words = re.sub(r"[^a-z ]", '', str(name or '').lower().replace('-', ' ')).split()
    return ' '.join(w for w in words if w not in ('jr', 'sr', 'ii', 'iii', 'iv', 'v'))


def http_get(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        headers = {h: response.headers.get(h) for h in ('x-requests-remaining', 'x-requests-used', 'x-requests-last')}
        return json.load(response), headers


def credits_left(root=ROOT):
    try:
        return int(json.loads((root / 'data' / 'odds' / 'status.json').read_text())['usage']['remaining'])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def todays_games(games, now):
    """NFL games today (Eastern) that are far enough from kickoff to post a ticket before them."""
    day = eastern_date(now)
    return [g for g in games.values() if g.get('league') == 'NFL' and g.get('state', 'pre') == 'pre'
            and eastern_date(gates.when(g['kickoff'])) == day and gates.when(g['kickoff']) > now + LEAD]


def match_event(event, games):
    """Our game for an Odds API event: the same kickoff and both teams' names."""
    start = gates.when(event['commence_time'])
    for game in games:
        if abs((gates.when(game['kickoff']) - start).total_seconds()) > 3600:
            continue
        names = [str(t.get('short') or t.get('name') or '').lower() for t in (game['away'], game['home'])]
        teams = f"{event.get('away_team', '')} {event.get('home_team', '')}".lower()
        if all(n and n in teams for n in names):
            return game
    return None


def fetch_day(games, now, key=None, get=None, cache=None, remaining=None, log=print, spend=True, clock=None):
    """{game id: Odds API bookmakers} for today's games, from a fresh cache or one fetch per game (never when
    spend is False: a rehearsal reads the cache only)."""
    cache = Path(cache or CACHE)
    day = eastern_date(now).isoformat()
    path = cache / f'{day}.json'
    wall = (clock or (lambda: datetime.now(timezone.utc)))()      # freshness is real time, never the run's --now
    try:
        stored = json.loads(path.read_text())
        if wall - gates.when(stored['fetchedAt']) < FRESH:
            return stored['games']
    except (OSError, ValueError, KeyError):
        pass
    key = key or os.environ.get('ODDS_API_KEY', '').strip()
    if not spend or not key or not games:
        return {}
    remaining = credits_left() if remaining is None else remaining
    cost = len(MARKETS) * len(games)
    if remaining is not None and remaining - cost < RESERVE:
        log(f'easy parlay: {remaining} credits left; keeping the reserve')
        return {}
    get = get or http_get
    events, _ = get(f"{API}/events?{urllib.parse.urlencode({'apiKey': key})}")
    out, last = {}, {}
    for event in events:
        game = match_event(event, games)
        if not game:
            continue
        query = urllib.parse.urlencode({'apiKey': key, 'regions': 'us', 'markets': ','.join(MARKETS),
                                        'bookmakers': ','.join(BOOKS), 'oddsFormat': 'american'})
        data, last = get(f"{API}/events/{event['id']}/odds?{query}")
        out[game['id']] = data.get('bookmakers') or []
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'fetchedAt': gates.stamp(wall), 'games': out}))
    log(f"easy parlay: alternate lines for {len(out)} games; credits left {last.get('x-requests-remaining')}")
    return out


def legs_for_game(game, bookmakers, ctx, now):
    """Every easier line in this game our projection clears comfortably, at a sane price."""
    snapshot = ctx.snapshot(game['id'])
    if not snapshot:
        return []
    ids = [p['id'] for side in ('home', 'away') for p in ((snapshot.get('players') or {}).get(side) or {}).get('players', [])]
    by_name = {name_key(ctx.names.get(str(i))): str(i) for i in ids if ctx.names.get(str(i))}
    out = []
    for book in bookmakers:
        if book.get('key') not in BOOKS:
            continue
        for market in book.get('markets') or []:
            stat = MARKETS.get(market.get('key'))
            if not stat:
                continue
            for outcome in market.get('outcomes') or []:
                if outcome.get('name') != 'Over' or not isinstance(outcome.get('point'), (int, float)):
                    continue
                athlete = by_name.get(name_key(outcome.get('description')))
                side, player = pricing.player_line(snapshot, athlete) if athlete else (None, None)
                projected = (player or {}).get(pricing.PROJECTED[stat])
                if not projected or player.get('limited'):
                    continue
                mean, low, high = projected
                sd = (high - mean) / pricing.Z80
                price = int(outcome['price'])
                if sd <= 0 or not PRICE_RANGE[0] <= price <= PRICE_RANGE[1]:
                    continue
                over, _, _ = pricing.chances(mean, sd, float(outcome['point']))
                implied = pricing.break_even(price)
                if over < MIN_CHANCE or over - implied < MIN_GAP:
                    continue
                if not build_site.settled_role(athlete, game[side]['id'], ctx.appearances, ctx.established):
                    continue
                name = ctx.names.get(athlete) or outcome.get('description')
                point = float(outcome['point'])
                out.append({'id': f"alt-{game['id']}-{athlete}-{stat}-{point:g}", 'title': f"{name} {int(point + 0.5)}+ {pricing.WORDS[stat]}",
                            'gameId': game['id'], 'athleteId': athlete, 'player': name, 'market': stat, 'direction': 'over',
                            'line': point, 'book': BOOKS[book['key']], 'odds': price, 'chance': round(over, 3),
                            'implied': round(implied, 3), 'projection': round(mean, 1), 'kickoff': game['kickoff'],
                            'observedAt': book.get('last_update') or gates.stamp(now), 'marketWindow': 'Full game'})
    return out


def build(legs):
    """The ticket: one leg per game at one book, the games whose easy line our number clears by the most, three
    legs (four when three pay under the target), priced as the book multiplies them. None with a reason."""
    tickets = []
    for book in sorted({leg['book'] for leg in legs}):
        best = {}
        for leg in sorted((l for l in legs if l['book'] == book), key=lambda l: -(l['chance'] - l['implied'])):
            best.setdefault(leg['gameId'], leg)
        chosen = sorted(best.values(), key=lambda l: -(l['chance'] - l['implied']))
        for count in (LEGS, LEGS + 1):
            if len(chosen) < count:
                break
            dec = 1.0
            for leg in chosen[:count]:
                dec *= parlay.decimal(leg['odds'])
            price = parlay.american(dec)
            if TARGET[0] <= price <= TARGET[1]:
                tickets.append({'book': book, 'legs': chosen[:count], 'odds': price, 'decimal': round(dec, 3),
                                'gameIds': [l['gameId'] for l in chosen[:count]], 'quotedAt': max(l['observedAt'] for l in chosen[:count]),
                                'firstKickoff': min(l['kickoff'] for l in chosen[:count]),
                                'room': round(sum(l['chance'] - l['implied'] for l in chosen[:count]), 3)})
                break
    if not tickets:
        return None, f'no book has {LEGS} games with an easy line our numbers clear comfortably at a price that makes a ticket'
    return max(tickets, key=lambda t: (t['room'], -len(t['legs']))), None


def candidate(ctx, games, now, key=None, get=None, cache=None, remaining=None, log=print, spend=True, exclude=()):
    """The day's easy parlay as a pick, or (None, reason). Games in `exclude` (the desk has a reason against them)
    are left off."""
    today = [g for g in todays_games(games, now) if g['id'] not in set(exclude)]
    if len(today) < LEGS:
        return None, f'only {len(today)} NFL games left today; a ticket needs {LEGS}'
    fetched = fetch_day(today, now, key, get, cache, remaining, log, spend)
    legs = [leg for game in today for leg in legs_for_game(game, fetched.get(game['id']) or [], ctx, now)]
    ticket, reason = build(legs)
    if not ticket:
        return None, reason
    first = games.get(ticket['gameIds'][0]) or {}
    day = eastern_date(now)
    lows = min(l['chance'] for l in ticket['legs'])
    return {'id': f"NFL-{first.get('season', day.year)}-W{first.get('week', 0)}-easy-{day:%m%d}-{'dk' if ticket['book'] == 'DraftKings' else 'fd'}",
            'title': f"{len(ticket['legs'])}-leg easy props at {ticket['book']}", 'status': 'active', 'favorite': False,
            'parlayType': 'easyProps', 'riskUnits': STAKE, 'legs': ticket['legs'],
            'correlation': 'One leg per game, so the book prices the ticket as the legs multiplied.',
            'gameIds': ticket['gameIds'], 'book': ticket['book'], 'odds': ticket['odds'], 'quotedAt': ticket['quotedAt'],
            'expiresAt': gates.stamp(min(gates.next_slot(now), gates.when(ticket['firstKickoff']))),
            'quoteType': 'capture', 'confidence': 1,
            'edge': (f"For fun, not value: each leg is an easier line our projection clears comfortably ({100 * lows:.0f}% or better "
                     f"on our numbers, which are tuned for main lines), priced at {ticket['book']}'s own alternate-line price and "
                     f"multiplied to {ticket['odds']:+d}. A quarter unit, kept with the longshots."),
            'cutoff': 'A fun parlay is not re-entered. It stands or falls as posted.',
            'sources': sorted({SOURCE} | {games[g]['source'] for g in ticket['gameIds'] if g in games and games[g].get('source')})}, None
