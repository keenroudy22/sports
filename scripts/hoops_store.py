"""Append-only store of every completed NBA and men's college basketball game, with its lines.

Each final is read from two public ESPN endpoints:
  scoreboard  one day of games, teams, scores, neutral site    site.api.espn.com
  odds        every pregame provider's open and close lines    sports.core.api.espn.com
and reduced to one compact JSON line in data/hoops/<league>-<season>.jsonl:

  {id, league, eventId, season, type, kickoff, neutral, home, away, homeScore, awayScore,
   state, close: {total, spread, books}, open: {total, spread, books}, retrievedAt}

`spread` is the home team's line, negative when the home team is favoured. The close and
open are the consensus across books: the median of each book's closing (or opening) total
and home spread. With an even number of books the median is the midpoint of the middle two,
so it can land on a quarter point that no book offered; it is a yardstick for grading, never
a quote to bet. In-game ("Live Odds") feeds and projection services (ESPN provider IDs of
1000 and up, such as accuscore) are not books and are left out. One sportsbook listed once per
state (Caesars in Colorado, New Jersey and Tennessee) counts once. A game with no pregame book
has no line: `close` and `open` are null, never an estimate.

ESPN names a season by the year it ends: 2025-26 is season 2026. `type` is ESPN's season
type: 2 regular season (college conference tournaments included), 3 postseason, 5 the NBA
play-in. Preseason games and all-star games are not team results and are not stored.

Lines are never edited. The last line for an event is current, and ledger.json hashes the
lines each file already holds (the same store helpers as scripts/boxscores.py); the tests
fail if a recorded line changes. A backfill is resumable: games already stored are skipped,
and a game whose odds could not be read this time is left for the next run rather than
stored without its line.

The feed refuses custom User-Agent strings, so requests go out with Python's default one,
one day at a time (date ranges are refused), with a short pause between requests.

Usage:
  python scripts/hoops_store.py backfill NBA 2025     every final of the 2024-25 season
  python scripts/hoops_store.py refresh               new finals from the last three days
  python scripts/hoops_store.py refresh --days 7 --league CBB
Stdlib only.
"""
import argparse
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
from boxscores import line
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'hoops'
SLUG = {'NBA': 'nba', 'CBB': 'mens-college-basketball'}
SITE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/'
CORE = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/'
# Groups=50 is all of Division I; without it the college scoreboard lists only featured games.
EXTRA = {'NBA': '&limit=1000', 'CBB': '&groups=50&limit=1000'}
# Calendar days searched for a season named by its end year: from the first possible
# regular-season day through the last possible postseason day.
WINDOW = {'NBA': ((10, 1), (6, 30)), 'CBB': ((11, 1), (4, 12))}
SEASON_TYPES = (2, 3, 5)
PAUSE = 0.25          # seconds after every request, per worker
WORKERS = 4           # odds requests in flight at once
FLUSH_EVERY = 200     # a long backfill writes its progress this often
PLAUSIBLE = {'total': (50.0, 400.0), 'spread': 60.0}


def fetch_json(url):
    """Python's default User-Agent (the feed answers custom ones with 403); retries as boxscores does."""
    return boxscores.fetch_json(url)


def scoreboard_url(league, day):
    return f'{SITE}{SLUG[league]}/scoreboard?dates={day:%Y%m%d}{EXTRA[league]}'


def odds_url(league, event_id):
    return f'{CORE}{SLUG[league]}/events/{event_id}/competitions/{event_id}/odds'


def store_path(league, season, root=STORE):
    return root / f'{league.lower()}-{season}.jsonl'


# ---------------------------------------------------------------- normalizing

def team(competitor):
    """The few fields the site and the model need about one side."""
    info = competitor.get('team') or {}
    out = {'id': str(info.get('id', '')), 'abbreviation': info.get('abbreviation'),
           'school': info.get('location'), 'short': info.get('shortDisplayName'), 'color': info.get('color')}
    return {k: v for k, v in out.items() if v not in (None, '')}


def score(competitor):
    value = competitor.get('score')
    if isinstance(value, dict):
        value = value.get('value', value.get('displayValue'))
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def final_game(event, league):
    """The parts of a scoreboard event worth storing, or None when it is not a stored final.

    Stored: a completed regular-season, postseason or play-in game between two teams with both
    scores. Not stored: anything unfinished, postponed, cancelled or forfeited, preseason games
    and all-star games.
    """
    competition = (event.get('competitions') or [{}])[0]
    status = (competition.get('status') or event.get('status') or {}).get('type') or {}
    name = str(status.get('name', '')).upper()
    season = event.get('season') or {}
    if season.get('type') not in SEASON_TYPES or not status.get('completed') or status.get('state') != 'post':
        return None
    if any(word in name for word in ('CANCEL', 'POSTPONE', 'FORFEIT', 'SUSPEND')):
        return None
    if str((competition.get('type') or {}).get('abbreviation', '')).upper() == 'ALLSTAR':
        return None
    sides = {c.get('homeAway'): c for c in competition.get('competitors', [])}
    if set(sides) != {'home', 'away'}:
        return None
    home, away = sides['home'], sides['away']
    if {team(home).get('abbreviation'), team(away).get('abbreviation')} & {'EAST', 'WEST'}:
        return None
    if score(home) is None or score(away) is None or not team(home).get('id') or not team(away).get('id'):
        return None
    event_id = str(event['id'])
    return {'id': f'{league}-{event_id}', 'league': league, 'eventId': event_id, 'season': int(season['year']),
            'type': int(season['type']), 'kickoff': event.get('date') or competition.get('date'),
            'neutral': bool(competition.get('neutralSite')), 'home': team(home), 'away': team(away),
            'homeScore': score(home), 'awayScore': score(away), 'state': status.get('state')}


def book_items(payload):
    """One pregame item per sportsbook: live feeds and projection services left out, a book listed per state once."""
    books = {}
    for item in (payload or {}).get('items', []):
        provider = item.get('provider') or {}
        name, pid = str(provider.get('name') or ''), str(provider.get('id') or '')
        if 'live' in name.lower() or not pid.isdigit() or int(pid) >= 1000:
            continue
        book = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip() or pid
        books.setdefault(book, item)
    return books


def book_line(item, when):
    """(total, home spread) one book posted at the open or the close; either can be None.

    The home spread is the home team's own line; with only the away line posted, its negative.
    When a book's home and away lines disagree the spread is left out rather than guessed.
    """
    total = line(((item.get(when) or {}).get('total')))
    home = line((((item.get('homeTeamOdds') or {}).get(when) or {}).get('pointSpread')))
    away = line((((item.get('awayTeamOdds') or {}).get(when) or {}).get('pointSpread')))
    spread = home if home is not None else (-away if away is not None else None)
    if home is not None and away is not None and home != -away:
        spread = None
    low, high = PLAUSIBLE['total']
    if total is not None and not low <= total <= high:
        total = None
    if spread is not None and abs(spread) > PLAUSIBLE['spread']:
        spread = None
    return total, spread


def consensus(payload):
    """{'close': {...}, 'open': {...}}: the median total and home spread across books at each moment.

    Each side of the result is None when no book posted a number for that moment. `books`
    counts the books that contributed either number.
    """
    books = book_items(payload)
    out = {}
    for when in ('close', 'open'):
        totals, spreads, used = [], [], 0
        for item in books.values():
            total, spread = book_line(item, when)
            if total is not None:
                totals.append(total)
            if spread is not None:
                spreads.append(spread)
            used += total is not None or spread is not None
        snapshot = {'total': statistics.median(totals) if totals else None,
                    'spread': statistics.median(spreads) if spreads else None, 'books': used}
        snapshot = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in snapshot.items() if v is not None}
        out[when] = snapshot if used else None
    return out


def record(game, odds_payload, retrieved_at):
    """The stored line for one final: the scoreboard's game and the books' consensus."""
    lines = consensus(odds_payload)
    return {**game, 'close': lines['close'], 'open': lines['open'], 'retrievedAt': retrieved_at}


# ---------------------------------------------------------------- the store

def stored_ids(league, root=STORE):
    return {r['eventId'] for path in sorted(root.glob(f'{league.lower()}-*.jsonl')) for r in boxscores.read_store(path)}


def load(league, seasons=None, root=STORE):
    """The current line for every stored game of a league, oldest kickoff first."""
    latest = {}
    for path in sorted(root.glob(f'{league.lower()}-*.jsonl')):
        for rec in boxscores.read_store(path):
            if seasons is None or rec['season'] in seasons:
                latest[rec['eventId']] = rec
    return sorted(latest.values(), key=lambda r: (r['kickoff'], int(r['eventId'])))


def season_days(league, season, today=None):
    """Every calendar day a season named by its end year can have games, up to yesterday."""
    (m1, d1), (m2, d2) = WINDOW[league]
    first, last = date(season - 1, m1, d1), date(season, m2, d2)
    if today is not None:
        last = min(last, today - timedelta(days=1))
    return [first + timedelta(days=n) for n in range((last - first).days + 1)]


def finals_on(league, days, fetch=fetch_json, pause=PAUSE, log=print):
    """Stored-kind finals listed on the scoreboard for each day, by event ID."""
    games = {}
    for number, day in enumerate(days, 1):
        payload = fetch(scoreboard_url(league, day))
        for event in payload.get('events', []):
            game = final_game(event, league)
            if game:
                games[game['eventId']] = game
        if pause:
            time.sleep(pause)
        if number % 30 == 0:
            log(f'  {league}: {number}/{len(days)} days listed, {len(games)} finals')
    return games


def collect(league, games, fetch=fetch_json, pause=PAUSE, workers=WORKERS, root=STORE, clock=None, log=print):
    """Read the odds for each new final and append it. Returns (lines appended per file, failures)."""
    problems = boxscores.verify(root)
    if problems:
        raise SystemExit('Refusing to append to a store whose recorded lines changed:\n  ' + '\n  '.join(problems))
    have = stored_ids(league, root)
    work = sorted((g for g in games.values() if g['eventId'] not in have), key=lambda g: (g['kickoff'], int(g['eventId'])))
    clock = clock or (lambda: datetime.now(timezone.utc))
    pending, written, failures = [], {}, {}

    def task(game):
        payload, failure = None, None
        try:
            payload = fetch(odds_url(league, game['eventId']))
        except HTTPError as error:
            if error.code != 404:  # 404: ESPN has no odds for this game, which is no line
                failure = f'HTTPError: {error}'
            error.close()
        except Exception as error:  # one unreadable game is retried next run, never fatal
            failure = f'{type(error).__name__}: {error}'
        if pause:
            time.sleep(pause)
        return game, payload, failure, boxscores.stamp(clock())

    def flush():
        by_file = {}
        for rec in pending:
            by_file.setdefault(store_path(league, rec['season'], root), []).append(rec)
        for path, records in sorted(by_file.items()):
            records.sort(key=lambda r: (r['kickoff'], int(r['eventId'])))
            boxscores.append(path, records)
            written[path.name] = written.get(path.name, 0) + len(records)
        pending.clear()
        root.mkdir(parents=True, exist_ok=True)
        boxscores.write_json(root / 'ledger.json', boxscores.ledger(root))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for done, (game, payload, failure, retrieved) in enumerate(pool.map(task, work), 1):
            if failure:
                failures[game['eventId']] = failure[:160]
            else:
                pending.append(record(game, payload, retrieved))
            if done % FLUSH_EVERY == 0:
                flush()
                log(f'  {league}: {done}/{len(work)} games read')
    if pending or not (root / 'ledger.json').exists():
        flush()
    return written, failures


def backfill(league, season, fetch=fetch_json, pause=PAUSE, workers=WORKERS, root=STORE, today=None, log=print):
    days = season_days(league, season, today or eastern_date(datetime.now(timezone.utc)))
    games = {k: g for k, g in finals_on(league, days, fetch, pause, log).items() if g['season'] == season}
    log(f'{league} {season}: {len(games)} finals listed over {len(days)} days')
    return collect(league, games, fetch, pause, workers, root, log=log)


def refresh(leagues, days_back=3, fetch=fetch_json, pause=PAUSE, workers=WORKERS, root=STORE, now=None, log=print):
    """New finals from the last `days_back` Eastern days (today included) for each league."""
    today = eastern_date(now or datetime.now(timezone.utc))
    days = [today - timedelta(days=n) for n in range(days_back - 1, -1, -1)]
    out = {}
    for league in leagues:
        out[league] = collect(league, finals_on(league, days, fetch, pause, log), fetch, pause, workers, root, log=log)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    fill = sub.add_parser('backfill', help='every final of one season (resumable)')
    fill.add_argument('league', choices=sorted(SLUG))
    fill.add_argument('season', type=int, help='the year the season ends: 2025 is 2024-25')
    recent = sub.add_parser('refresh', help='new finals from the last few days')
    recent.add_argument('--days', type=int, default=3)
    recent.add_argument('--league', choices=sorted(SLUG))
    args = parser.parse_args(argv)
    if args.command == 'backfill':
        results = {args.league: backfill(args.league, args.season)}
    else:
        results = refresh([args.league] if args.league else sorted(SLUG), args.days)
    for league, (written, failures) in results.items():
        files = ', '.join(f'{name} {count}' for name, count in sorted(written.items()))
        text = f'{league}: appended {sum(written.values())} lines' + (f' ({files})' if files else '') + '.'
        if failures:
            text += f' {len(failures)} could not be read ({", ".join(sorted(failures)[:5])}); run it again to retry them.'
        print(text)
    if any(failures for _, failures in results.values()):
        sys.exit(1)


if __name__ == '__main__':
    main()
