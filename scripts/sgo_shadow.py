"""SportsGameOdds free-tier evaluation feed for the Discord-only Arb Radar.

This is deliberately shadow-only: it never alerts, publishes, changes a play, or places a wager. It samples a
small number of upcoming football events, records only a compact local evaluation summary, and fails closed unless
the API reports the Amateur plan's 2,500-object monthly ceiling.

The key comes from SPORTSGAMEODDS_API_KEY and is sent only in the x-api-key header. It is never put in a URL,
written to disk, or logged. The usage endpoint is checked before every odds request.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arbs
import features
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
CONF = Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy'))
API = 'https://api.sportsgameodds.com/v2'
FREE_MONTHLY_LIMIT = 2500
STOP_AT = 1800                    # keep 700 objects untouched, even if other experiments use the same key
EVENT_LIMIT = 10
DAILY_CAP = 30                    # local backstop; normally the six-hour gap limits this further
MIN_GAP = timedelta(hours=6)
GAME_WINDOW = timedelta(hours=48)
QUOTE_FRESH = timedelta(minutes=15)
LEAGUES = {'NFL', 'CFB'}
SGO_LEAGUES = 'NFL,NCAAF'
STATE = CONF / 'sgo-shadow.json'
BOOK_NAMES = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel', 'betmgm': 'BetMGM', 'caesars': 'Caesars',
              'espnbet': 'ESPN BET', 'bovada': 'Bovada', 'unibet': 'Unibet', 'pointsbet': 'PointsBet',
              'williamhill': 'William Hill'}


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def load(path=STATE):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'version': 1, 'history': []}


def save(state, path=STATE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(state, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def request_json(path, key, params=None, opener=urllib.request.urlopen):
    query = '?' + urllib.parse.urlencode(params) if params else ''
    request = urllib.request.Request(API + path + query,
                                     headers={'x-api-key': key, 'User-Agent': 'keenroudy-sports'})
    with opener(request, timeout=45) as response:
        return json.load(response)


def monthly_usage(payload):
    """Return (used, maximum, end time), or None. Unknown usage always stops the metered events call."""
    try:
        month = payload['data']['rateLimits']['per-month']
        # The live v2 response uses hyphenated names; older docs and some accounts still show the verbose names.
        used = month.get('current-entities', month.get('currentIntervalEntities'))
        maximum = month.get('max-entities', month.get('maxEntitiesPerInterval'))
        end = month.get('interval-end-time', month.get('currentIntervalEndTime'))
        return int(used), int(maximum), end
    except (KeyError, TypeError, ValueError):
        return None


def nearby_games(slate, now):
    return [game for game in slate.get('games', [])
            if game.get('league') in LEAGUES and game.get('state') == 'pre'
            and now < features.when(game['kickoff']) <= now + GAME_WINDOW]


def due(state, slate, now, usage):
    """Return a skip reason, or None when one tightly budgeted sample is allowed."""
    if usage is None:
        return 'usage response did not contain a numeric monthly object limit'
    used, maximum, _ = usage
    if maximum != FREE_MONTHLY_LIMIT:
        return f'monthly ceiling is {maximum}, not the confirmed free-tier ceiling; refusing odds request'
    if used + EVENT_LIMIT > STOP_AT:
        return f'{used}/{maximum} monthly objects used; keeping the 700-object reserve'
    if not nearby_games(slate, now):
        return 'no NFL or college game inside 48 hours'
    if state.get('lastAt'):
        try:
            if now - features.when(state['lastAt']) < MIN_GAP:
                return f"last sample was {state['lastAt']}; keeping the six-hour gap"
        except (TypeError, ValueError):
            pass
    today = eastern_date(now).isoformat()
    day_count = state.get('dayCount', 0) if state.get('day') == today else 0
    if day_count + EVENT_LIMIT > DAILY_CAP:
        return f'{day_count} objects budgeted today; keeping the 30-object daily cap'
    return None


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def american(value):
    value = number(value)
    return int(value) if value and value == int(value) else None


def line_of(book, bet_type):
    if bet_type == 'ou':
        return number(book.get('overUnder'))
    if bet_type == 'sp':
        return number(book.get('spread'))
    return None


def compatible(first, second, bet_type, player):
    a, b = line_of(first, bet_type), line_of(second, bet_type)
    if bet_type == 'ml':
        return True, None
    if a is None or b is None:
        return False, None
    if bet_type == 'ou' and a != b:
        return False, None
    if bet_type == 'sp' and abs(a + b) > .001:
        return False, None
    line = a if bet_type == 'ou' else abs(a)
    if player and (line % 1 != .5):
        return False, None
    return True, line


def quotes(bookmaker, row, now):
    """The main quote and each advertised alternate, with unavailable or stale prices removed."""
    candidates = [row] + list(row.get('altLines') or [])
    out = []
    for quote in candidates:
        price = american(quote.get('odds'))
        try:
            age = now - features.when(quote.get('lastUpdatedAt'))
            fresh = -timedelta(minutes=1) <= age <= QUOTE_FRESH
        except (TypeError, ValueError):
            fresh = False
        if quote.get('available') is not False and price and fresh:
            out.append((bookmaker, quote, price))
    return out


def event_candidates(event, now, minimum=arbs.MIN_ROI):
    """Find exact two-outcome pairs in one response. Results are measurements, never alerts."""
    status = event.get('status') or {}
    if status.get('started') or status.get('cancelled') or status.get('ended'):
        return []
    odds, found, seen = event.get('odds') or {}, [], set()
    for odd_id, first_odd in odds.items():
        opposing_id = first_odd.get('opposingOddID')
        if not opposing_id or opposing_id not in odds or tuple(sorted((odd_id, opposing_id))) in seen:
            continue
        seen.add(tuple(sorted((odd_id, opposing_id))))
        second_odd = odds[opposing_id]
        bet_type = first_odd.get('betTypeID')
        sides = frozenset({first_odd.get('sideID'), second_odd.get('sideID')})
        if first_odd.get('periodID') != 'game' or second_odd.get('periodID') != 'game':
            continue
        if bet_type != second_odd.get('betTypeID') or (bet_type, sides) not in {
                ('ou', frozenset({'over', 'under'})), ('sp', frozenset({'home', 'away'})),
                ('ml', frozenset({'home', 'away'}))}:
            continue
        player = first_odd.get('statEntityID') not in {'all', 'home', 'away'}
        first_rows = [(book, quote, price) for book, row in (first_odd.get('byBookmaker') or {}).items()
                      for book, quote, price in quotes(book, row, now)]
        second_rows = [(book, quote, price) for book, row in (second_odd.get('byBookmaker') or {}).items()
                       for book, quote, price in quotes(book, row, now)]
        label = first_odd.get('marketName') or first_odd.get('statID') or odd_id
        for first_book, first_row, first_price in first_rows:
            for second_book, second_row, second_price in second_rows:
                okay, line = compatible(first_row, second_row, bet_type, player)
                if not okay or first_book == second_book:
                    continue
                a = {'bookKey': first_book, 'book': BOOK_NAMES.get(first_book, first_book),
                     'side': first_odd.get('sideID'), 'price': first_price, 'updatedAt': first_row['lastUpdatedAt']}
                b = {'bookKey': second_book, 'book': BOOK_NAMES.get(second_book, second_book),
                     'side': second_odd.get('sideID'), 'price': second_price, 'updatedAt': second_row['lastUpdatedAt']}
                hit = arbs.opportunity('sgo shadow', event.get('eventID'), label, line, a, b, stamp(now), minimum)
                if hit:
                    found.append(hit)
    return sorted(found, key=lambda hit: -hit['roi'])


def team_total_inventory(events, now):
    """Compact fresh two-sided team-total coverage already present in the sampled response.

    This spends no additional API objects and makes no pick. It only establishes whether the free feed supplies an
    exact line and both prices at one book before a separately calibrated team-total model is considered.
    """
    rows = {}
    for event in events:
        odds = event.get('odds') or {}
        for entity in ('away', 'home'):
            sides = {}
            for odd in odds.values():
                if (odd.get('statID'), odd.get('statEntityID'), odd.get('periodID'), odd.get('betTypeID')) == \
                        ('points', entity, 'game', 'ou') and odd.get('sideID') in {'over', 'under'}:
                    sides[odd['sideID']] = odd
            if set(sides) != {'over', 'under'}:
                continue
            over_books, under_books = sides['over'].get('byBookmaker') or {}, sides['under'].get('byBookmaker') or {}
            for bookmaker in sorted(set(over_books) & set(under_books)):
                overs = quotes(bookmaker, over_books[bookmaker], now)
                unders = quotes(bookmaker, under_books[bookmaker], now)
                for _, over, over_price in overs:
                    for _, under, under_price in unders:
                        okay, line = compatible(over, under, 'ou', False)
                        if not okay:
                            continue
                        key = (event.get('eventID'), entity, bookmaker, line)
                        rows[key] = {'eventID': event.get('eventID'), 'team': entity, 'line': line,
                                     'book': BOOK_NAMES.get(bookmaker, bookmaker),
                                     'over': over_price, 'under': under_price,
                                     'updatedAt': max(over['lastUpdatedAt'], under['lastUpdatedAt'])}
    return [rows[key] for key in sorted(rows)]


def evaluate(events, now):
    hits = [hit for event in events for hit in event_candidates(event, now)]
    # One summary per market; keeping every book permutation would inflate the private state file.
    best = {}
    for hit in hits:
        key = (hit['gameId'], hit['label'], hit['line'])
        if key not in best or hit['roi'] > best[key]['roi']:
            best[key] = hit
    return sorted(best.values(), key=lambda hit: -hit['roi'])


def candidate_summary(hit):
    """Enough private detail to verify a shadow hit later, without retaining the provider's full response."""
    return {'eventID': hit['gameId'], 'market': hit['label'], 'line': hit['line'], 'roi': hit['roi'],
            'first': {key: hit['first'][key] for key in ('book', 'side', 'price', 'updatedAt')},
            'second': {key: hit['second'][key] for key in ('book', 'side', 'price', 'updatedAt')}}


def sample(slate, now=None, key=None, state_path=STATE, opener=urllib.request.urlopen):
    """Take one budgeted shadow sample and return a small status dict suitable for the run log."""
    now = now or datetime.now(timezone.utc)
    key = (key if key is not None else os.environ.get('SPORTSGAMEODDS_API_KEY', '')).strip()
    if not key:
        return {'sampled': False, 'reason': 'SPORTSGAMEODDS_API_KEY is not configured'}
    state = load(state_path)
    usage_payload = request_json('/account/usage', key, opener=opener)
    usage = monthly_usage(usage_payload)
    reason = due(state, slate, now, usage)
    if reason:
        return {'sampled': False, 'reason': reason, 'usage': usage[0] if usage else None,
                'limit': usage[1] if usage else None}
    params = {'leagueID': SGO_LEAGUES, 'oddsAvailable': 'true', 'started': 'false',
              'includeAltLines': 'true', 'includeOpposingOdds': 'true', 'limit': EVENT_LIMIT}
    payload = request_json('/events', key, params=params, opener=opener)
    events = payload.get('data') or []
    if not isinstance(events, list):
        raise ValueError('SportsGameOdds events response did not contain a list')
    hits = evaluate(events, now)
    team_totals = team_total_inventory(events, now)
    used, maximum, end = usage
    today = eastern_date(now).isoformat()
    charged = max(1, len(events))
    day_count = state.get('dayCount', 0) if state.get('day') == today else 0
    summary = {'at': stamp(now), 'events': len(events), 'candidates': len(hits),
               'bestRoi': hits[0]['roi'] if hits else None, 'teamTotalPairs': len(team_totals),
               'usageBefore': used}
    last = {**summary, 'candidateDetails': [candidate_summary(hit) for hit in hits[:10]],
            'teamTotalExamples': team_totals[:12], 'filteredNotice': bool(payload.get('notice'))}
    state.update(version=2, lastAt=stamp(now), day=today, dayCount=day_count + charged,
                 usage={'usedBefore': used, 'maximum': maximum, 'endsAt': end}, last=last)
    state['history'] = (state.get('history') or [])[-59:] + [summary]
    save(state, state_path)
    return {'sampled': True, 'events': len(events), 'candidates': len(hits), 'bestRoi': summary['bestRoi'],
            'teamTotalPairs': len(team_totals),
            'usage': used, 'limit': maximum, 'notice': bool(payload.get('notice'))}


def main():
    try:
        slate = json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
        result = sample(slate)
    except Exception as error:
        print(f'SportsGameOdds shadow unavailable ({type(error).__name__}); no alert or post was made.')
        return 0
    if result['sampled']:
        print(f"SportsGameOdds shadow: {result['events']} events, {result['candidates']} candidates; "
              f"{result['teamTotalPairs']} fresh team-total pairs; "
              f"usage was {result['usage']}/{result['limit']} before this sample.")
    else:
        print('SportsGameOdds shadow skipped: ' + result['reason'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
