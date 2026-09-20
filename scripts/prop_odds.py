"""Player prop prices across books from The Odds API, for the games closest to kickoff.

ESPN relays DraftKings' player numbers without prices, so a prop could be read but never
priced, and an unpriced line cannot be published as a pick. The Odds API carries the same
markets with prices from every book we follow. Each market costs one credit per game, so
this captures four markets (passing, rushing and receiving yards, receptions) for the few
games nearest kickoff rather than a whole slate.

Budget: the free tier is 500 credits a month and the game-line capture already spends
about 360 of them. A game's props cost 4, so this script takes at most three games a day,
twelve credits, which comes to roughly 130 a month across the Saturday and Sunday slates
and a midweek game: the two together stay under 500. It never captures the same game
inside three hours and never spends below the reserve the game-line capture respects.
The event list itself is free. data/prop-odds/status.json carries the pacing between runs.

Records are appended to data/prop-odds/<league>-<season>.jsonl only when a book's numbers
change, each with its retrieval time, and frozen by the store's ledger. The key comes from
ODDS_API_KEY, is never written to the store, a URL or a log, and without it the script says
so and exits 0.

Usage: python scripts/prop_odds.py
Stdlib only.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import features
import odds_api
import pricing
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'prop-odds'
EVENTS = 'https://api.the-odds-api.com/v4/sports/{sport}/events'
ODDS = 'https://api.the-odds-api.com/v4/sports/{sport}/events/{event}/odds'
# The Odds API market -> the projection key the desk prices against.
MARKETS = {'player_pass_yds': 'passYds', 'player_rush_yds': 'rushYds',
           'player_reception_yds': 'recYds', 'player_receptions': 'rec'}
COST = len(MARKETS)                        # one credit per market returned, one bookmaker group
WINDOW = timedelta(hours=6)                # only games this close to kickoff
LEAD = timedelta(minutes=20)               # and not about to start
RUN_EVENTS = 3                             # games per run
DAY_CREDITS = 12                           # credits a day for props: three games
RESERVE = 24                               # the month's floor, shared with the game-line capture
GAP = timedelta(hours=3)                   # between captures of one game


def spend(status, now):
    """Credits already spent on props today."""
    today = eastern_date(now).isoformat()
    return status.get('spent', 0) if status.get('day') == today else 0


def wanted(slate, status, now, limit=RUN_EVENTS):
    """The games worth pricing now: closest to kickoff first, inside the budget."""
    games = [g for g in slate.get('games', []) if g.get('league') in odds_api.SPORTS and g.get('state') == 'pre'
             and now + LEAD < features.when(g['kickoff']) <= now + WINDOW]
    seen = status.get('events') or {}
    fresh = [g for g in games if not seen.get(g['id']) or now - features.when(seen[g['id']]) >= GAP]
    fresh.sort(key=lambda g: g['kickoff'])
    room = (DAY_CREDITS - spend(status, now)) // COST
    usage = status.get('usage') or {}
    if usage.get('remaining') is not None:
        room = min(room, (usage['remaining'] - RESERVE) // COST)
    return fresh[:max(0, min(limit, room))]


def fetch_events(sport, key, opener=urllib.request.urlopen):
    query = urllib.parse.urlencode({'apiKey': key, 'dateFormat': 'iso'})
    request = urllib.request.Request(EVENTS.format(sport=sport) + '?' + query, headers={'User-Agent': 'keenroudy-sports'})
    with opener(request, timeout=60) as response:
        return json.load(response)


def fetch_odds(sport, event, key, opener=urllib.request.urlopen):
    query = urllib.parse.urlencode({'apiKey': key, 'markets': ','.join(MARKETS), 'bookmakers': ','.join(odds_api.BOOKS),
                                    'oddsFormat': 'american', 'dateFormat': 'iso'})
    url = ODDS.format(sport=sport, event=event) + '?' + query
    request = urllib.request.Request(url, headers={'User-Agent': 'keenroudy-sports'})
    with opener(request, timeout=60) as response:
        headers = {k: response.headers.get(k) for k in ('x-requests-remaining', 'x-requests-used', 'x-requests-last')}
        return json.load(response), headers


def quotes_of(event):
    """book -> projection key -> player -> {line, over, under}, from one event's odds."""
    out = {}
    for book in event.get('bookmakers', []):
        markets = {}
        for market in book.get('markets', []):
            key = MARKETS.get(market.get('key'))
            if not key:
                continue
            players = {}
            for outcome in market.get('outcomes', []):
                name, side, point = outcome.get('description'), str(outcome.get('name', '')).lower(), outcome.get('point')
                price = outcome.get('price')
                if not name or side not in ('over', 'under') or not isinstance(point, (int, float)) \
                        or not isinstance(price, (int, float)):
                    continue
                entry = players.setdefault(name, {'line': point})
                if entry['line'] != point:      # a book showing two numbers for one player: keep the main one
                    continue
                entry[side] = int(price)
            players = {n: e for n, e in players.items() if 'over' in e or 'under' in e}
            if players:
                markets[key] = players
        if markets:
            out[book['key']] = {'title': book.get('title'), 'updatedAt': book.get('last_update'), 'markets': markets}
    return out


def best(record, market, player, side):
    """The best number and price for one side of one player's market: number first, then price."""
    found = []
    for book, entry in (record.get('books') or {}).items():
        quote = ((entry.get('markets') or {}).get(market) or {}).get(player)
        if not quote or side not in quote:
            continue
        found.append((book, quote['line'], quote[side]))
    if not found:
        return None
    # Over wants the lowest number, under the highest; the better price breaks a tie.
    return sorted(found, key=lambda f: (f[1] if side == 'over' else -f[1], -pricing.cents(f[2])))[0]


def capture(slate, now, key, status, events=fetch_events, odds=fetch_odds, root=STORE, log=print):
    """Price the due games; returns the updated status."""
    picks = wanted(slate, status, now)
    if not picks:
        log('props: nothing due (no game inside six hours, or the day\'s budget is spent)')
        return status
    latest = {}
    for path in sorted(root.glob('*.jsonl')):
        for line in boxscores.read_store(path):
            latest[line['gameId']] = line
    listings, written, today = {}, [], eastern_date(now).isoformat()
    status.setdefault('events', {})
    for game in picks:
        league = game['league']
        sport = odds_api.SPORTS[league]
        if sport not in listings:
            try:
                listings[sport] = events(sport, key)
            except Exception as error:      # the key never reaches the log
                log(f'props: event list failed for {league} ({type(error).__name__})')
                listings[sport] = []
        pairs, _ = odds_api.match(listings[sport], [game])
        if not pairs:
            log(f"props: {game['away']['abbreviation']} @ {game['home']['abbreviation']} is not in the API's event list")
            continue
        event_id = pairs[0][0].get('id')
        try:
            payload, headers = odds(sport, event_id, key)
        except Exception as error:
            log(f"props: request failed for {game['id']} ({type(error).__name__})")
            continue
        usage = {k.replace('x-requests-', ''): int(v) for k, v in headers.items() if v and str(v).lstrip('-').isdigit()}
        if usage:
            status['usage'] = {**usage, 'at': boxscores.stamp(now)}
        status['day'], status['spent'] = today, spend(status, now) + (usage.get('last') or COST)
        status['events'][game['id']] = boxscores.stamp(now)
        books = quotes_of(payload)
        if not books:
            log(f"props: no player prices yet for {game['away']['abbreviation']} @ {game['home']['abbreviation']}")
            continue
        record = {'league': league, 'gameId': game['id'], 'season': game.get('season'), 'kickoff': game['kickoff'],
                  'oddsApiId': event_id, 'retrievedAt': boxscores.stamp(now),
                  'source': ODDS.format(sport=sport, event=event_id) + ' (key withheld)', 'books': books}
        previous = latest.get(game['id'])
        if previous and previous.get('books') == books:
            log(f"props: {game['away']['abbreviation']} @ {game['home']['abbreviation']} unchanged")
            continue
        record['hash'] = boxscores.content_hash(record)
        written.append(record)
        counts = sum(len(players) for entry in books.values() for players in entry['markets'].values())
        log(f"props: {game['away']['abbreviation']} @ {game['home']['abbreviation']} {len(books)} books, {counts} player lines; "
            f"credits used {usage.get('used')} remaining {usage.get('remaining')}")
    for season in sorted({r['season'] for r in written}):
        boxscores.append(boxscores.store_path(written[0]['league'], season, root),
                         [r for r in written if r['season'] == season])
    return status


def main():
    key = os.environ.get('ODDS_API_KEY', '').strip()
    if not key:
        print('No ODDS_API_KEY in the environment; prop prices skipped.')
        return
    problems = boxscores.verify(STORE)
    if problems:
        sys.exit('Refusing to append to a prop-price store whose recorded lines changed:\n  ' + '\n  '.join(problems))
    STORE.mkdir(parents=True, exist_ok=True)
    status_path = STORE / 'status.json'
    status = json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
    slate = json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
    status = capture(slate, datetime.now(timezone.utc), key, status)
    boxscores.write_json(status_path, status)
    boxscores.write_json(STORE / 'ledger.json', boxscores.ledger(STORE))


if __name__ == '__main__':
    main()
