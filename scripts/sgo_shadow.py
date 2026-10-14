"""SportsGameOdds free-tier evaluation feed for the Discord-only Arb Radar.

This is deliberately shadow-only: it never alerts, publishes, changes a play, or places a wager. It samples a
small number of upcoming football events, records only a compact local evaluation summary, and fails closed unless
the API reports the Amateur plan's 2,500-object monthly ceiling.

The key comes from SPORTSGAMEODDS_API_KEY and is sent only in the x-api-key header. It is never put in a URL,
written to disk, or logged. The usage endpoint is checked before every odds request.
"""
import json
import hashlib
import os
import re
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
TEAM_TOTAL_LEDGER = CONF / 'team-total-shadow.jsonl'
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


def implied(price):
    price = american(price)
    if price is None:
        return None
    return (-price / (-price + 100)) if price < 0 else (100 / (price + 100))


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


def main_team_totals(rows):
    """Keep the closest-to-balanced two-sided line for each sampled team and book.

    SportsGameOdds includes every alternate in the same response. The balanced pair is the useful approximation of
    the book's main team total; retaining hundreds of alternates would make the forward calibration look much larger
    than the number of independent market observations.
    """
    best = {}
    for row in rows:
        if row.get('book') not in {'DraftKings', 'FanDuel'}:
            continue
        key = (row.get('eventID'), row.get('team'), row.get('book'))
        over, under = implied(row.get('over')), implied(row.get('under'))
        if over is None or under is None:
            continue
        score = (abs(over - under), abs((over + under) - 1), abs(row['line']))
        if key not in best or score < best[key][0]:
            best[key] = (score, row)
    return [best[key][1] for key in sorted(best)]


def clean_name(value):
    return re.sub(r'[^a-z0-9]+', '', str(value or '').lower())


def side_names(side):
    names = (side or {}).get('names') or {}
    return {clean_name(value) for value in names.values() if clean_name(value)}


def slate_names(side):
    return {clean_name((side or {}).get(key)) for key in ('name', 'short', 'school', 'abbreviation')
            if clean_name((side or {}).get(key))}


def same_team(event_side, slate_side):
    provider, local = side_names(event_side), slate_names(slate_side)
    if provider & local:
        return True
    # Long provider names commonly include a mascot while the ESPN short name does not.
    return any(len(name) >= 5 and (name in other or other in name) for name in provider for other in local)


def matched_game(event, slate):
    """Match one provider event to the stored ESPN slate without an extra API request."""
    league = 'CFB' if event.get('leagueID') == 'NCAAF' else event.get('leagueID')
    try:
        starts = features.when((event.get('status') or {}).get('startsAt'))
    except (TypeError, ValueError):
        return None
    candidates = []
    for game in slate.get('games', []):
        if game.get('league') != league:
            continue
        try:
            gap = abs(features.when(game.get('kickoff')) - starts)
        except (TypeError, ValueError):
            continue
        if gap <= timedelta(minutes=10):
            candidates.append(game)
    teams = event.get('teams') or {}
    matches = [game for game in candidates if same_team(teams.get('home'), game.get('home'))
               and same_team(teams.get('away'), game.get('away'))]
    return matches[0] if len(matches) == 1 else None


def load_forecasts(path=None):
    path = Path(path or (ROOT / 'site' / 'data' / 'forecasts.json'))
    try:
        rows = json.loads(path.read_text(encoding='utf-8'))
        return {row['gameId']: row for row in rows if isinstance(row, dict) and row.get('gameId')}
    except (OSError, ValueError, TypeError):
        return {}


def team_total_observations(events, rows, slate, now, forecasts=None):
    """Build compact private forward observations from the already-budgeted event response."""
    events_by_id = {event.get('eventID'): event for event in events}
    forecasts = forecasts or {}
    observations = []
    for row in main_team_totals(rows):
        event = events_by_id.get(row.get('eventID'))
        game = matched_game(event or {}, slate)
        side = row.get('team')
        if not game or side not in {'home', 'away'}:
            continue
        team = game.get(side) or {}
        forecast = forecasts.get(game['id']) or {}
        projection = number(forecast.get(side))
        raw_id = '|'.join(str(row.get(key)) for key in ('eventID', 'team', 'book', 'line', 'over', 'under',
                                                         'updatedAt'))
        observations.append({
            'type': 'quote', 'id': hashlib.sha256(raw_id.encode()).hexdigest()[:20], 'observedAt': stamp(now),
            'eventID': row['eventID'], 'gameId': game['id'], 'league': game['league'],
            'kickoff': game['kickoff'], 'side': side, 'teamId': team.get('id'),
            'team': team.get('short') or team.get('school') or team.get('name'), 'book': row['book'],
            'line': row['line'], 'over': row['over'], 'under': row['under'],
            'quoteUpdatedAt': row['updatedAt'], 'projection': projection,
        })
    return observations


def ledger_rows(path):
    try:
        return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def append_ledger(path, rows):
    path = Path(path)
    existing = ledger_rows(path)
    quote_ids = {row.get('id') for row in existing if row.get('type') == 'quote'}
    grade_ids = {row.get('quoteId') for row in existing if row.get('type') == 'grade'}
    fresh = [row for row in rows if (row.get('type') == 'grade' and row.get('quoteId') not in grade_ids)
             or (row.get('type') == 'quote' and row.get('id') not in quote_ids)]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        for row in fresh:
            handle.write(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n')
    return len(fresh)


def settle_team_totals(slate, now, ledger_path):
    rows = ledger_rows(ledger_path)
    graded = {row.get('quoteId') for row in rows if row.get('type') == 'grade'}
    games = {game.get('id'): game for game in slate.get('games', [])}
    # Grade the latest captured main line only. Earlier snapshots stay in the append-only ledger for movement
    # analysis, but must not inflate the independent record for one team/book/game.
    closing = {}
    for row in rows:
        if row.get('type') != 'quote':
            continue
        key = (row.get('gameId'), row.get('side'), row.get('book'))
        if key not in closing or str(row.get('quoteUpdatedAt') or '') > str(closing[key].get('quoteUpdatedAt') or ''):
            closing[key] = row
    new = []
    for quote in closing.values():
        if quote.get('id') in graded:
            continue
        game = games.get(quote.get('gameId'))
        if not game or game.get('state') != 'post':
            continue
        actual = number((game.get(quote.get('side')) or {}).get('score'))
        projection, line = number(quote.get('projection')), number(quote.get('line'))
        if actual is None or projection is None or line is None or projection == line:
            continue
        direction = 'over' if projection > line else 'under'
        price = american(quote.get(direction))
        if price is None:
            continue
        outcome = 'push' if actual == line else ('win' if (actual > line) == (direction == 'over') else 'loss')
        units = 0 if outcome == 'push' else ((price / 100 if price > 0 else 100 / -price) if outcome == 'win' else -1)
        new.append({'type': 'grade', 'quoteId': quote['id'], 'gradedAt': stamp(now), 'gameId': quote['gameId'],
                    'team': quote['team'], 'book': quote['book'], 'line': line, 'projection': projection,
                    'direction': direction, 'price': price, 'actual': actual, 'outcome': outcome,
                    'units': round(units, 4)})
    append_ledger(ledger_path, new)
    return new


def team_total_report(path):
    rows = ledger_rows(path)
    grades = [row for row in rows if row.get('type') == 'grade']
    wins = sum(row.get('outcome') == 'win' for row in grades)
    losses = sum(row.get('outcome') == 'loss' for row in grades)
    pushes = sum(row.get('outcome') == 'push' for row in grades)
    return {'quotes': sum(row.get('type') == 'quote' for row in rows), 'graded': len(grades),
            'record': f'{wins}-{losses}' + (f'-{pushes}' if pushes else ''),
            'units': round(sum(number(row.get('units')) or 0 for row in grades), 2)}


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
    ledger_path = Path(state_path).with_name('team-total-shadow.jsonl')
    settled = settle_team_totals(slate, now, ledger_path)
    if not key:
        return {'sampled': False, 'reason': 'SPORTSGAMEODDS_API_KEY is not configured',
                'teamTotals': team_total_report(ledger_path), 'teamTotalsGradedNow': len(settled)}
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
    observations = team_total_observations(events, team_totals, slate, now, load_forecasts())
    captured = append_ledger(ledger_path, observations)
    calibration = team_total_report(ledger_path)
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
                 usage={'usedBefore': used, 'maximum': maximum, 'endsAt': end}, last=last,
                 teamTotals=calibration)
    state['history'] = (state.get('history') or [])[-59:] + [summary]
    save(state, state_path)
    return {'sampled': True, 'events': len(events), 'candidates': len(hits), 'bestRoi': summary['bestRoi'],
            'teamTotalPairs': len(team_totals),
            'teamTotalsCaptured': captured, 'teamTotalsGradedNow': len(settled), 'teamTotals': calibration,
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
