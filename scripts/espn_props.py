"""NBA-only ESPN prop parsing and bounded capture. Not wired into the desk yet.

Array order never proves a side. A same-read, exact-price labeled milestone
must identify exactly one over. Unknown sides retain the line without prices.
This module neither selects plays nor publishes anything.
"""
import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import boxscores

STORE = Path(__file__).resolve().parents[1] / 'data' / 'sport-props'
MARKETS = {
    'Total Points': 'pts', 'Total Rebounds': 'reb', 'Total Assists': 'ast',
    'Total 3-Point Field Goals': 'fg3m', 'Total Steals': 'stl', 'Total Blocks': 'blk',
    'Total Points, Rebounds, and Assists': 'pra', 'Total Points and Rebounds': 'pr',
    'Total Points and Assists': 'pa', 'Total Assists and Rebounds': 'ra',
    'Total Steals and Blocks': 'sb',
}
MILESTONES = {
    'Points Milestones': 'pts', 'Rebounds Milestones': 'reb',
    'Assists Milestones': 'ast', '3-Point Field Goals Milestones': 'fg3m',
    'Steals Milestones': 'stl', 'Blocks Milestones': 'blk',
    'Points + Assists + Rebounds Milestones': 'pra',
    'Points + Rebounds Milestones': 'pr', 'Points + Assists Milestones': 'pa',
}
MAX_BOARDS, MAX_PAGES, GAP, TIMEBOX = 30, 3, 0.5, 150


def number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a number')
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('Nonfinite number')
    return parsed


def price(value):
    parsed = number(value)
    if parsed != int(parsed) or abs(parsed) < 100:
        raise ValueError('Invalid American price')
    return int(parsed)


def implied(odds):
    return -odds / (100 - odds) if odds < 0 else 100 / (100 + odds)


def parse(payload):
    """Return main-line rows and diagnostics from one complete DK NBA board."""
    groups, milestones, ignored = defaultdict(list), defaultdict(set), Counter()
    for item in payload.get('items', []):
        name = (item.get('type') or {}).get('name')
        athlete = re.search(r'/nba/(?:seasons/\d+/)?athletes/(\d+)(?:\?|$)',
                            (item.get('athlete') or {}).get('$ref', ''))
        provider = re.search(r'/nba/casinos/100(?:\?|$)',
                             (item.get('provider') or {}).get('$ref', ''))
        if not athlete or not provider:
            ignored['identity'] += 1
            continue
        try:
            target = item['current']['target']
            line = number(target['value'])
            odds = price(item['odds']['american']['value'])
            if line < 0:
                raise ValueError('Negative player line')
        except (KeyError, TypeError, ValueError, OverflowError):
            ignored['invalid-number'] += 1
            continue
        if name in MARKETS:
            groups[(athlete[1], MARKETS[name], line)].append((odds, item))
        elif name in MILESTONES and re.fullmatch(r'\d+\+', str(target.get('displayValue', ''))):
            if line == int(target['displayValue'][:-1]):
                milestones[(athlete[1], MILESTONES[name], line)].add(odds)
        else:
            ignored[str(name)] += 1
    rows, malformed, contradictions = [], 0, 0
    for (athlete, stat, line), items in sorted(groups.items()):
        if len(items) != 2 or line % 1 != .5:
            malformed += 1
            continue
        prices = [item[0] for item in items]
        proof = milestones.get((athlete, stat, math.floor(line) + 1), set())
        matches = [i for i, odds in enumerate(prices) if odds in proof]
        row = {'athleteId': athlete, 'stat': stat, 'kind': 'main',
               'line': line, 'book': 'DraftKings', 'sideVerified': False}
        if len(proof) == 1 and len(matches) == 1 and prices[0] != prices[1]:
            over = matches[0]
            if .99 <= sum(implied(p) for p in prices) <= 1.15:
                row.update(over=prices[over], under=prices[1-over], sideVerified=True,
                           sideMethod='milestone-exact', orderAgrees=over == 0)
                contradictions += over != 0
        updates = sorted({str(item.get('lastUpdated')) for _, item in items if item.get('lastUpdated')})
        if updates:
            row['providerUpdatedAt'] = updates
        rows.append(row)
    return rows, {'verifiedPairs': sum(r['sideVerified'] for r in rows),
                  'unverifiedPairs': sum(not r['sideVerified'] for r in rows),
                  'malformedGroups': malformed, 'orderContradictions': contradictions,
                  'ignored': dict(ignored)}


def endpoint(event_id, page=1):
    if not str(event_id).isdigit():
        raise ValueError('Invalid NBA event ID')
    return ('https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/'
            f'{event_id}/competitions/{event_id}/odds/100/propBets?limit=1000&page={page}')


def fetch_json(url):
    with urlopen(url, timeout=20) as response:
        return json.load(response)


def persist(rows, root=STORE):
    """Append changes only; refuse to bless a changed ledger prefix."""
    problems = boxscores.verify(root)
    if problems:
        raise ValueError('; '.join(problems))
    added = 0
    for season in sorted({r['season'] for r in rows}):
        path = root / f'nba-{season}.jsonl'
        key = lambda r: (r['eventId'], r['athleteId'], r['stat'], r['kind'], r['line'])
        latest = {key(r): r for r in boxscores.read_store(path)}
        changed = []
        for row in rows:
            if row['season'] != season:
                continue
            if boxscores.content_hash(row) != boxscores.content_hash(latest.get(key(row), {})):
                changed.append(row)
                latest[key(row)] = row
        boxscores.append(path, changed)
        added += len(changed)
    if added:
        boxscores.write_json(root / 'ledger.json', boxscores.ledger(root))
    return added


def capture(games, fetch=fetch_json, clock=lambda: datetime.now(timezone.utc),
            monotonic=time.monotonic, sleep=time.sleep, root=STORE,
            limit=MAX_BOARDS, seconds=TIMEBOX):
    """Complete boards only, before kickoff, capped requests/time; last-good rows survive errors.

    Caller supplies the scheduled slate. No enumeration, name lookup, retries,
    live pricing, social send or model call occurs here.
    """
    from zoneinfo import ZoneInfo
    eastern = ZoneInfo('America/New_York')
    deadline = monotonic() + min(seconds, TIMEBOX)
    status = dict(boards=0, requests=0, late=0, errors=0, captured=0, orderContradictions=0)
    consecutive = 0
    for game in sorted(games, key=lambda g: str(g.get('kickoff', ''))):
        if status['boards'] >= min(limit, MAX_BOARDS) or monotonic() >= deadline or consecutive >= 3:
            break
        try:
            start = boxscores.instant(game['kickoff'])
            now = clock()
            if start.tzinfo is None or now.tzinfo is None:
                continue
            if (game.get('league') != 'NBA' or game.get('status') != 'scheduled'
                    or not game.get('timeConfirmed', True)
                    or not isinstance(game.get('season'), int) or isinstance(game['season'], bool)
                    or not 0 < (start-now).total_seconds() <= 36000
                    or start.astimezone(eastern).date() != now.astimezone(eastern).date()):
                continue
            event = str(game['providerId'])
            status['boards'] += 1
            items = []
            pages = 1
            page = 1
            total = None
            while page <= pages:
                if monotonic() >= deadline:
                    raise TimeoutError('NBA capture timebox')
                sleep(GAP)
                status['requests'] += 1
                payload = fetch(endpoint(event, page))
                count = payload.get('pageCount', 1)
                if (not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_PAGES
                        or payload.get('pageIndex', page) != page
                        or (page > 1 and count != pages) or not isinstance(payload.get('items'), list)):
                    raise ValueError('Incomplete NBA board')
                pages = count
                if 'count' in payload:
                    advertised = payload['count']
                    if (not isinstance(advertised, int) or isinstance(advertised, bool)
                            or advertised < 0 or (total is not None and advertised != total)):
                        raise ValueError('NBA board count changed')
                    total = advertised
                items.extend(payload['items'])
                page += 1
            if total is not None and len(items) != total:
                raise ValueError('NBA board rows missing')
            retrieved = clock()  # own clock AFTER every page; provider time never sets freshness
            if retrieved >= start or monotonic() >= deadline:
                status['late'] += 1
                continue
            # Refuse prices from a different competition, including mislabeled NBA IDs.
            competition = re.compile(rf'/nba/events/{event}/competitions/{event}(?:\?|$)')
            if any(not competition.search((r.get('competition') or {}).get('$ref', '')) for r in items):
                raise ValueError('Wrong NBA competition')
            rows, diagnostics = parse({'items': items})
            rows = [{**r, 'league': 'NBA', 'eventId': event, 'season': game['season'],
                     'seasonType': game.get('seasonType'), 'kickoff': game['kickoff'],
                     'retrievedAt': boxscores.stamp(retrieved), 'source': endpoint(event)} for r in rows]
            status['captured'] += persist(rows, root)
            status['orderContradictions'] += diagnostics['orderContradictions']
            consecutive = 0
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            consecutive += 1
            status['errors'] += 1
    return status
