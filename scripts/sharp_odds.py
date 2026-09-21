"""Player prop prices from DraftKings and FanDuel through SharpAPI, for every game inside two days.

SharpAPI's free tier serves pre-match odds from DraftKings and FanDuel at twelve requests a
minute with no credit budget, player props included, alternate lines marked. That covers
what The Odds API capture cannot afford: props for the whole slate rather than three games.
The two feeds share one store, data/prop-odds, in one shape: a record per game with each
book's markets, so the board needs no idea which feed a price came from. When a game already
has a record, this capture merges its two books into the other books that record holds,
so the board keeps its best-of-five shopping.

Only the markets the desk prices are kept: passing, rushing and receiving yards, receptions,
carries, attempts and completions. Alternate lines ride along under `alternates` for the
longshot builder. Records are appended only when a book's numbers change, with the retrieval
time, and frozen by the store's ledger. The key comes from SHARP_API (or SHARP_API_KEY), is
sent in a header, never written to the store, a URL or a log, and without it the script says
so and exits 0.

Usage: python scripts/sharp_odds.py [--probe]
  --probe   list the market types and books seen for the next games, write nothing.
Stdlib only.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import features
import odds_api

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'prop-odds'
BASE = 'https://api.sharpapi.io/api/v1'
LEAGUES = {'NFL': 'nfl', 'CFB': 'ncaaf'}
BOOKS = ('draftkings', 'fanduel')
WINDOW = timedelta(days=2)
PAGE = 200
MAX_PAGES = 8                        # pages per game
RUN_REQUESTS = 60                    # requests per run, about five minutes at the free tier's pace
GAP = 5.2                            # seconds between requests: under twelve a minute
FRESH = timedelta(hours=12)          # other books' quotes older than this are not merged forward


def market_key(market_type):
    """SharpAPI's market type -> the projection key the desk prices, or None."""
    m = str(market_type or '').lower()
    if not m.startswith('player_'):
        return None
    if 'pass' in m and ('yard' in m or 'yds' in m):
        return 'passYds'
    if 'rush' in m and ('yard' in m or 'yds' in m):
        return 'rushYds'
    if ('recei' in m or 'rec_' in m) and ('yard' in m or 'yds' in m):
        return 'recYds'
    if 'reception' in m and 'yard' not in m and 'longest' not in m:
        return 'rec'
    if ('rush' in m and ('attempt' in m or 'att' in m.split('_'))) or 'carries' in m:
        return 'car'
    if 'pass' in m and 'attempt' in m:
        return 'att'
    if 'completion' in m:
        return 'cmp'
    return None


def team_words(name):
    return odds_api.normal(name).split()


def same_team(a, b):
    """SharpAPI writes "LV Raiders" or "Las Vegas Raiders"; the slate writes the full name.

    Equal once normalised, or the same mascot with a first word that matches, abbreviates,
    or shares four letters with the other's. The caller also requires the kickoff to match.
    """
    x, y = team_words(a), team_words(b)
    if not x or not y:
        return False
    if x == y or x[-1] != y[-1]:
        return x == y
    if len(x) == 1 or len(y) == 1:
        return True                                   # a bare mascot
    fx, fy = x[0], y[0]
    if fx == fy or (len(fx) <= 3 and fy.startswith(fx[0])) or (len(fy) <= 3 and fx.startswith(fy[0])):
        return True
    short, long_ = (fx, fy) if len(fx) <= len(fy) else (fy, fx)
    return any(short[i:i + 4] in long_ for i in range(len(short) - 3))


def find_game(row, games):
    """The slate game a SharpAPI row belongs to, by both teams and a kickoff within six hours."""
    start = features.when(row['event_start_time']) if row.get('event_start_time') else None
    for game in games:
        if start and abs(features.when(game['kickoff']) - start) > timedelta(hours=6):
            continue
        if same_team(game['home']['name'], row.get('home_team')) and same_team(game['away']['name'], row.get('away_team')):
            return game
        if same_team(game['home']['name'], row.get('away_team')) and same_team(game['away']['name'], row.get('home_team')):
            return game
    return None


def fetch(path, key, opener=urllib.request.urlopen, sleep=time.sleep, **params):
    """One request; on a 429 it waits the seconds the reply asks for, once, and tries again."""
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    request = urllib.request.Request(f'{BASE}{path}?{query}', headers={'X-API-Key': key, 'User-Agent': 'keenroudy-sports'})
    for attempt in (1, 2):
        try:
            with opener(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 2:
                raise
            wait = 15.0
            try:
                wait = float(json.loads(error.read().decode() or '{}').get('retry_after') or error.headers.get('Retry-After') or wait)
            except (ValueError, TypeError):
                pass
            sleep(min(max(wait, 1.0), 60.0))


def pages(league, key, fetch=fetch, sleep=time.sleep, log=print, budget=None, event_id=None):
    """Pre-match player-prop rows from the two books, one game at a time when event_id is given.

    budget is a one-item list of requests left for the run, shared across games.
    """
    cursor, count = None, 0
    while count < MAX_PAGES and (budget is None or budget[0] > 0):
        try:
            payload = fetch('/odds', key, league=league, market='props', sportsbook=','.join(BOOKS), is_live='false',
                            event_id=event_id, limit=PAGE, cursor=cursor)
        except Exception as error:      # the key never reaches the log
            log(f'sharp: request failed for {league} ({type(error).__name__})')
            return
        count += 1
        if budget is not None:
            budget[0] -= 1
        for row in payload.get('data') or []:
            yield row
        pagination = payload.get('pagination') or {}
        cursor = pagination.get('next_cursor')
        if not pagination.get('has_more') or not cursor:
            return
        sleep(GAP)


def events(league, key, fetch=fetch, log=print):
    """SharpAPI's upcoming events for a league: id, teams and start time."""
    try:
        payload = fetch('/events', key, league=league, limit=PAGE)
    except Exception as error:
        log(f'sharp: event list failed for {league} ({type(error).__name__})')
        return []
    return payload.get('data') or []


def quotes_from(rows):
    """gameId -> book -> projection key -> player -> {line, over, under, alternates}."""
    out = {}
    for game, row in rows:
        key = market_key(row.get('market_type'))
        side = str(row.get('selection_type') or row.get('selection') or '').lower()
        name, point, price = row.get('player_name'), row.get('line'), row.get('odds_american')
        book = str(row.get('sportsbook') or '').lower()
        if not key or side not in ('over', 'under') or not name or book not in BOOKS \
                or not isinstance(point, (int, float)) or not isinstance(price, (int, float)):
            continue
        players = out.setdefault(game['id'], {}).setdefault(book, {}).setdefault(key, {})
        ladder = players.setdefault(name, {})
        rung = ladder.setdefault(f'{point:g}', {'line': point, 'flagged': False})
        rung[side] = int(price)
        if not (row.get('is_alternate_line') or row.get('is_main_line') is False):
            rung['flagged'] = True
    # The main number is the rung priced on both sides closest to even money; the feed's own flag
    # has marked a +235 alternate as main, so the flag only decides when no rung has two sides.
    for game_books in out.values():
        for book_key, book in list(game_books.items()):
            for market_key_, market in list(book.items()):
                for name, ladder in list(market.items()):
                    rungs = sorted(ladder.values(), key=lambda r: r['line'])
                    two_sided = [r for r in rungs if 'over' in r and 'under' in r]
                    main = (min(two_sided, key=lambda r: abs(pricing_cents(r['over']) - pricing_cents(r['under']))) if two_sided
                            else next((r for r in rungs if r['flagged']), None))
                    if main is None:
                        del market[name]
                        continue
                    entry = {k: v for k, v in main.items() if k in ('line', 'over', 'under')}
                    alternates = [{k: v for k, v in r.items() if k in ('line', 'over', 'under')} for r in rungs if r is not main]
                    if alternates:
                        entry['alternates'] = alternates
                    market[name] = entry
                if not market:
                    del book[market_key_]
            drop_impossible(book)
            if not book:
                del game_books[book_key]
    return out


def drop_impossible(book):
    """Remove a player's quote that cannot be true next to another market at the same book.

    A completions line above the same player's attempts line is a mislabeled row, and the model
    reads it as a free 99% under. When the ladder holds a rung below attempts, that rung is the
    main number instead; otherwise the market goes.
    """
    cmp_, att = book.get('cmp') or {}, book.get('att') or {}
    for name, quote in list(cmp_.items()):
        limit = (att.get(name) or {}).get('line')
        if limit is None or quote.get('line', 0) < limit:
            continue
        below = [a for a in quote.get('alternates') or [] if a['line'] < limit]
        if below:
            best = max(below, key=lambda a: a['line'])
            others = [a for a in quote.get('alternates') if a is not best] + [{k: v for k, v in quote.items() if k in ('line', 'over', 'under')}]
            cmp_[name] = {**best, 'alternates': sorted(others, key=lambda a: a['line'])}
        else:
            del cmp_[name]
    if not cmp_:
        book.pop('cmp', None)


def pricing_cents(odds):
    """American odds on one scale so -105 and +105 are ten cents apart."""
    return odds + 100 if odds < 0 else odds - 100


def merge(previous, fresh_books, now):
    """This feed's books over the record's other books, when those are still fresh."""
    books = {}
    if previous and now - features.when(previous['retrievedAt']) <= FRESH:
        books = {k: v for k, v in (previous.get('books') or {}).items() if k not in BOOKS}
    for book, markets in fresh_books.items():
        books[book] = {'title': {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}.get(book, book), 'markets': markets}
    return books


def capture(slate, now, key, fetch=fetch, sleep=time.sleep, root=STORE, log=print, probe=False):
    games = [g for g in slate.get('games', []) if g.get('league') in LEAGUES and g.get('state') == 'pre'
             and now < features.when(g['kickoff']) <= now + WINDOW]
    if not games:
        log('sharp: no game inside two days')
        return 0
    latest = {}
    for path in sorted(root.glob('*.jsonl')):
        for line in boxscores.read_store(path):
            latest[line['gameId']] = line
    written = 0
    budget = [RUN_REQUESTS]
    status = {'at': boxscores.stamp(now), 'leagues': {}}
    for league, code in LEAGUES.items():
        mine = [g for g in games if g['league'] == league]
        if not mine:
            continue
        listing = events(code, key, fetch=fetch, log=log)
        budget[0] -= 1
        # Each slate game to its SharpAPI event, so one filtered request covers one game.
        ids = {}
        unmatched_events = []
        for event in listing:
            home = event.get('home_team') or (event.get('home') or {}).get('name') if isinstance(event.get('home'), dict) else event.get('home_team') or event.get('home')
            away = event.get('away_team') or (event.get('away') or {}).get('name') if isinstance(event.get('away'), dict) else event.get('away_team') or event.get('away')
            start = event.get('event_start_time') or event.get('start_time') or event.get('commence_time') or event.get('starts_at')
            game = find_game({'home_team': home, 'away_team': away, 'event_start_time': start}, mine)
            if game and game['id'] not in ids and event.get('id'):
                ids[game['id']] = event['id']
            elif not game and len(unmatched_events) < 12:
                unmatched_events.append({'home': home, 'away': away, 'start': start, 'type': event.get('event_type'),
                                         'external': event.get('external_ids'), 'sample': {k: event.get(k) for k in ('home_team', 'away_team', 'markets') if k in event}})
        matched, types, books_seen = [], {}, {}
        for game in mine:
            if game['id'] not in ids or budget[0] <= 0:
                continue
            for row in pages(code, key, fetch=fetch, sleep=sleep, log=log, budget=budget, event_id=ids[game['id']]):
                types[row.get('market_type')] = types.get(row.get('market_type'), 0) + 1
                books_seen[row.get('sportsbook')] = books_seen.get(row.get('sportsbook'), 0) + 1
                matched.append((game, row))
            sleep(GAP)
        status['leagues'][league] = {'games': len(mine), 'eventsListed': len(listing), 'eventsMatched': len(ids), 'rows': len(matched),
                                     'slateGames': [f"{g['away']['name']} at {g['home']['name']} {g['kickoff']}" for g in mine],
                                     'unmatchedEvents': unmatched_events,
                                     'books': books_seen, 'marketTypes': dict(sorted(types.items(), key=lambda kv: -kv[1])[:40]),
                                     'requestsLeft': budget[0]}
        if probe:
            log(f'sharp {league}: {len(ids)} of {len(mine)} games found, {len(matched)} rows, books {books_seen}; market types: '
                + ', '.join(f'{k} x{v}' for k, v in sorted(types.items(), key=lambda kv: -kv[1])[:30]))
            continue
        by_game = quotes_from(matched)
        for game in mine:
            fresh_books = by_game.get(game['id'])
            if not fresh_books:
                continue
            previous = latest.get(game['id'])
            books = merge(previous, fresh_books, now)
            if previous and previous.get('books') == books:
                continue
            record = {'league': league, 'gameId': game['id'], 'season': game.get('season'), 'kickoff': game['kickoff'],
                      'retrievedAt': boxscores.stamp(now), 'source': f'{BASE}/odds (key withheld)', 'books': books}
            record['hash'] = boxscores.content_hash(record)
            boxscores.append(boxscores.store_path(league, game['season'], root), [record])
            latest[game['id']] = record
            written += 1
        counted = sum(len(p) for b in by_game.values() for m in b.values() for p in m.values())
        log(f'sharp {league}: {len(by_game)} of {len(mine)} games priced, {counted} player lines, {written} records changed, '
            f'books {books_seen}')
    if not probe:
        boxscores.write_json(root / 'sharp-status.json', status)   # what the feed carried, readable without the runner's log
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--probe', action='store_true', help='list what the feed carries and write nothing')
    args = parser.parse_args()
    key = (os.environ.get('SHARP_API') or os.environ.get('SHARP_API_KEY') or '').strip()
    if not key:
        print('No SHARP_API in the environment; SharpAPI prop prices skipped.')
        return
    problems = boxscores.verify(STORE)
    if problems:
        sys.exit('Refusing to append to a prop-price store whose recorded lines changed:\n  ' + '\n  '.join(problems))
    STORE.mkdir(parents=True, exist_ok=True)
    slate = json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
    written = capture(slate, datetime.now(timezone.utc), key, probe=args.probe)
    if not args.probe:
        boxscores.write_json(STORE / 'ledger.json', boxscores.ledger(STORE))
        print(f'sharp: {written} records appended')


if __name__ == '__main__':
    main()
