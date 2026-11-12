"""Generate public, one-click Gambly betslips for already-official Kook'n plays.

The Unabated key is server-only.  This module writes only the returned public
HTTPS URL and a deterministic fingerprint of the immutable posted selection to
``data/betslips.json``.  Site builds are network-free and attach a link only
when that fingerprint still matches the pick.  Partial matches never publish.

The API never places a wager.  A reader still reviews the sportsbook's current
line and price and confirms the wager there.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'betslips.json'
CONF = Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy'))
PENDING = CONF / 'betslip-pending.json'
BASE_URL = 'https://data.unabated.com'
GAMBLY_CHAT = 'https://gambly.com/chat'
REFRESH_AFTER = timedelta(minutes=20)
POLL_SECONDS = 2
POLL_DEADLINE = 24

BOOKS = {
    'draftkings': 'DraftKings', 'draft kings': 'DraftKings',
    'fanduel': 'FanDuel', 'fan duel': 'FanDuel',
    'betmgm': 'BetMGM', 'bet mgm': 'BetMGM',
    'caesars': 'Caesars', 'betrivers': 'BetRivers', 'bet rivers': 'BetRivers',
    'espn bet': 'ESPN BET', 'thescore bet': 'ESPN BET',
    'fanatics': 'Fanatics', 'hard rock': 'Hard Rock', 'hard rock bet': 'Hard Rock',
}
BOOK_KEYS = {
    'DraftKings': 'draftkings', 'FanDuel': 'fanduel', 'BetMGM': 'betmgm', 'Caesars': 'caesars',
    'BetRivers': 'betrivers', 'ESPN BET': 'espnbet', 'Fanatics': 'fanatics', 'Hard Rock': 'hardrockbet',
}


class BetslipError(RuntimeError):
    """A provider response cannot safely become a public betslip."""


def stamp(moment=None):
    moment = moment or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def when(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def canonical_book(value):
    name = re.sub(r'\s+', ' ', str(value or '').strip())
    return BOOKS.get(name.casefold(), name or None)


def odds_text(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ''
    return f'{number:+d}'


def leg_text(value):
    if isinstance(value, str):
        return re.sub(r'\s+', ' ', value).strip()
    if not isinstance(value, dict):
        return ''
    title = value.get('title') or value.get('displayTitle')
    if title:
        return re.sub(r'\s+', ' ', str(title)).strip()
    player = value.get('player') or value.get('team') or ''
    direction = value.get('direction') or value.get('side') or ''
    line = value.get('line')
    market = value.get('market') or value.get('stat') or ''
    return re.sub(r'\s+', ' ', f'{player} {direction} {line if line is not None else ""} {market}').strip()


def requested_legs(pick):
    legs = [leg_text(leg) for leg in pick.get('legs') or []]
    legs = [leg for leg in legs if leg]
    return legs or [leg_text(pick.get('displayTitle') or pick.get('title') or pick)]


def prompt_for(pick):
    """Exact public handoff text.  It contains no stake, account or secret."""
    legs = requested_legs(pick)
    book = canonical_book(pick.get('book')) or 'the listed sportsbook'
    price = odds_text(pick.get('odds'))
    start = str(pick.get('kickoff') or '').strip()
    kind = 'parlay' if len(legs) > 1 else 'single bet'
    lines = [f'Build this exact {book} {kind}. Do not substitute a player, market, period, side, or line.']
    lines.extend(f'{index}. {leg}' for index, leg in enumerate(legs, 1))
    if price:
        lines.append(f'Kook\'n captured the original ticket at {price}; show the current sportsbook price for review.')
    if start:
        lines.append(f'Event time reference: {start}.')
    lines.append('Return a one-click sportsbook betslip. If every requested leg is not available exactly, say so instead of replacing it.')
    return '\n'.join(lines)


def fingerprint(pick):
    payload = {
        'id': pick.get('id'), 'book': canonical_book(pick.get('book')),
        'odds': pick.get('odds'), 'line': pick.get('line'),
        'direction': pick.get('direction'), 'market': pick.get('market') or pick.get('marketType'),
        'gameIds': pick.get('gameIds') or ([pick.get('gameId')] if pick.get('gameId') else []),
        'legs': requested_legs(pick),
    }
    raw = json.dumps(payload, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def safe_url(value):
    try:
        parsed = urlsplit(str(value or ''))
    except ValueError:
        return None
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.hostname in {'localhost', '127.0.0.1', '::1'}:
        return None
    return parsed.geturl()


def _same_number(left, right):
    try:
        return abs(float(left) - float(right)) < 0.0001
    except (TypeError, ValueError):
        return False


def _player_name(pick):
    name = str(pick.get('player') or '').strip()
    if name:
        return name
    title = str(pick.get('displayTitle') or pick.get('title') or '')
    return re.split(r'\s+(?:OVER|UNDER)\s+', title, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def _matched_link(book, side, line, row, checked_at=None):
    if not isinstance(row, dict) or not _same_number(row.get('line'), line):
        return None
    url = safe_url(row.get(f'{side}Link'))
    if not url:
        return None
    return {
        'status': 'ready', 'provider': 'The Odds API', 'book': book, 'url': url,
        'legsRequested': 1, 'legsMatched': 1, 'currentOdds': row.get(side),
        'generatedAt': checked_at,
        'note': 'Exact sportsbook, market, side and line matched. Review the current price before placing.',
    }


def direct_from_odds(pick, odds=None, props=None):
    """Return one verified sportsbook deep link for an exact straight selection.

    Captured URLs are never guessed. Parlays, missing links, a different line, player,
    market, side or sportsbook all fail closed.
    """
    if not isinstance(pick, dict) or pick.get('legs') or not pick.get('gameId'):
        return None
    book = canonical_book(pick.get('book'))
    book_key = BOOK_KEYS.get(book)
    side = str(pick.get('direction') or '').casefold()
    if not book_key or side not in {'home', 'away', 'over', 'under'}:
        return None
    game_id = str(pick['gameId'])
    market_type = str(pick.get('marketType') or '').casefold()
    if market_type == 'prop' or pick.get('market'):
        record = (props or {}).get(game_id) or {}
        entry = ((record.get('books') or {}).get(book_key) or {})
        market = str(pick.get('market') or '')
        players = (entry.get('markets') or {}).get(market) or {}
        wanted = re.sub(r'[^a-z0-9]+', '', _player_name(pick).casefold())
        player_row = next((row for name, row in players.items()
                           if re.sub(r'[^a-z0-9]+', '', str(name).casefold()) == wanted), None)
        return _matched_link(book, side, pick.get('line'), player_row, entry.get('updatedAt') or record.get('retrievedAt'))
    record = (odds or {}).get(game_id) or {}
    entry = ((record.get('books') or {}).get(book_key) or {})
    if market_type == 'total' and side in {'over', 'under'}:
        return _matched_link(book, side, pick.get('line'), entry.get('total'), entry.get('updatedAt') or record.get('retrievedAt'))
    if market_type == 'spread' and side in {'home', 'away'}:
        spread = entry.get('spread') or {}
        selected_line = spread.get('home') if side == 'home' else -spread.get('home') if isinstance(spread.get('home'), (int, float)) else None
        row = {'line': selected_line, side: spread.get(f'{side}Price'), f'{side}Link': spread.get(f'{side}Link')}
        return _matched_link(book, side, pick.get('line'), row, entry.get('updatedAt') or record.get('retrievedAt'))
    return None


def load(path=STORE, fallback=None):
    path = Path(path)
    if not path.exists():
        return fallback if fallback is not None else {'version': 1, 'slips': {}}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return fallback if fallback is not None else {'version': 1, 'slips': {}}
    return value if isinstance(value, dict) else (fallback if fallback is not None else {'version': 1, 'slips': {}})


def save(payload, path=STORE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


class Client:
    def __init__(self, key=None, base=None, opener=None):
        self.key = (key if key is not None else os.environ.get('UNABATED_API_KEY', '')).strip()
        self.base = (base if base is not None else os.environ.get('UNABATED_API_BASE_URL', BASE_URL)).rstrip('/')
        self.opener = opener or urllib.request.urlopen
        if not self.key:
            raise BetslipError('UNABATED_API_KEY is not configured')
        if self.base != BASE_URL:
            raise BetslipError('UNABATED_API_BASE_URL must be https://data.unabated.com')

    def request(self, method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + path, data=body, method=method,
                                         headers={'X-Api-Key': self.key, 'Accept': 'application/json',
                                                  'Content-Type': 'application/json'})
        try:
            with self.opener(request, timeout=20) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            # Never include provider response bodies: they may echo request data.
            raise BetslipError(f'Unabated returned HTTP {error.code}') from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise BetslipError(f'Unabated request failed: {type(error).__name__}') from error

    def submit(self, text):
        response = self.request('POST', '/api/v1/bet/generate', {
            'type': 'text', 'generateMobileLinks': True, 'content': {'text': text},
        })
        request_id = response.get('requestId') if isinstance(response, dict) else None
        if str(response.get('status') if isinstance(response, dict) else '').casefold() == 'error' or not request_id:
            raise BetslipError('Unabated did not accept betslip generation')
        return str(request_id)

    def status(self, request_id):
        if not re.fullmatch(r'[A-Za-z0-9-]{16,80}', str(request_id)):
            raise BetslipError('Invalid betslip request id')
        return self.request('GET', f'/api/v1/bet/status/{request_id}')


def complete_result(result, pick, generated_at=None):
    """Return the exact-book, full-match public row or reject the response."""
    if str(result.get('status') or '').casefold() != 'complete':
        raise BetslipError('Betslip generation is not complete')
    need = len(requested_legs(pick))
    wanted_book = canonical_book(pick.get('book'))
    complete = []
    for slip in result.get('betSlips') or []:
        book = canonical_book(slip.get('book'))
        requested = slip.get('legsRequested')
        matched = slip.get('legsMatched')
        bets = slip.get('betslipBets') or []
        url = safe_url(slip.get('deepLink'))
        if book == wanted_book and requested == need and matched == need and len(bets) >= need and url:
            complete.append((slip, url, book))
    if not complete:
        raise BetslipError(f'No full {wanted_book or "sportsbook"} match for all {need} requested leg(s)')
    slip, url, book = complete[0]
    summaries = []
    for bet in (slip.get('betslipBets') or [])[:need]:
        summaries.append({key: bet.get(key) for key in ('event', 'eventName', 'player', 'description', 'betType',
                                                        'period', 'points', 'odds') if bet.get(key) is not None})
    return {
        'status': 'ready', 'provider': 'Gambly', 'book': book, 'url': url,
        'shareUrl': safe_url(result.get('shareUrl')), 'legsRequested': need, 'legsMatched': need,
        'overallOdds': slip.get('overallOdds'), 'generatedAt': generated_at or stamp(),
        'selectionHash': fingerprint(pick), 'selections': summaries,
        'note': 'Every requested leg matched. Review the current sportsbook line and price before placing.',
    }


def _poll(client, request_id, deadline=POLL_DEADLINE, sleeper=time.sleep):
    until = time.monotonic() + max(0, deadline)
    while True:
        result = client.status(request_id)
        status = str(result.get('status') or '').casefold()
        if status in {'complete', 'error'}:
            return result
        if status != 'processing':
            raise BetslipError(f'Unexpected betslip status: {status or "missing"}')
        if time.monotonic() + POLL_SECONDS > until:
            return result
        sleeper(POLL_SECONDS)


def eligible(pick, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(pick, dict) or not pick.get('id') or pick.get('community') or pick.get('result'):
        return False
    if (pick.get('status') or 'active') not in ('active', 'expired') or pick.get('entryNote'):
        return False
    if not canonical_book(pick.get('book')) or not requested_legs(pick):
        return False
    kickoff = pick.get('kickoff')
    try:
        return not kickoff or when(kickoff) > now
    except (TypeError, ValueError):
        return False


def public_for(pick, now=None, store=None):
    """Network-free public fields for a current immutable pick."""
    now = now or datetime.now(timezone.utc)
    if not eligible(pick, now):
        return None
    item = ((store if store is not None else load()).get('slips') or {}).get(str(pick.get('id')))
    if not isinstance(item, dict) or item.get('status') != 'ready' or item.get('selectionHash') != fingerprint(pick):
        return None
    url = safe_url(item.get('url'))
    if not url or item.get('legsMatched') != item.get('legsRequested') or item.get('legsRequested') != len(requested_legs(pick)):
        return None
    return {key: item.get(key) for key in ('status', 'provider', 'book', 'url', 'shareUrl', 'legsRequested',
                                           'legsMatched', 'overallOdds', 'generatedAt', 'note') if item.get(key) is not None}


def decorate(pick, now=None, store=None, odds=None, props=None):
    """Add only an exact, captured sportsbook action; unsupported rows stay quiet."""
    row = dict(pick)
    if eligible(row, now):
        direct = direct_from_odds(row, odds=odds, props=props)
        if direct:
            row['betslip'] = direct
    return row


def refresh_pick(pick, now=None, client=None, store_path=STORE, pending_path=PENDING,
                 deadline=POLL_DEADLINE, sleeper=time.sleep):
    """Generate or resume one exact slip. Provider failures never change the pick."""
    now = now or datetime.now(timezone.utc)
    if not eligible(pick, now):
        return {'state': 'ineligible'}
    client = client or Client()
    store = load(store_path)
    store.setdefault('version', 1)
    slips = store.setdefault('slips', {})
    key, digest = str(pick['id']), fingerprint(pick)
    old = slips.get(key) or {}
    try:
        age = now - when(old.get('generatedAt'))
    except (TypeError, ValueError):
        age = REFRESH_AFTER
    if old.get('status') == 'ready' and old.get('selectionHash') == digest and age < REFRESH_AFTER:
        return {'state': 'current', 'slip': public_for(pick, now=now, store=store)}

    pending = load(pending_path, {'version': 1, 'requests': {}})
    requests = pending.setdefault('requests', {})
    request = requests.get(key) or {}
    request_id = request.get('requestId') if request.get('selectionHash') == digest else None
    if not request_id:
        request_id = client.submit(prompt_for(pick))
        requests[key] = {'requestId': request_id, 'selectionHash': digest, 'submittedAt': stamp(now)}
        save(pending, pending_path)

    result = _poll(client, request_id, deadline=deadline, sleeper=sleeper)
    status = str(result.get('status') or '').casefold()
    if status == 'processing':
        return {'state': 'processing'}
    if status == 'error':
        requests.pop(key, None)
        save(pending, pending_path)
        raise BetslipError('Unabated could not generate this exact betslip')
    row = complete_result(result, pick, generated_at=stamp(now))
    slips[key] = row
    store['updatedAt'] = stamp(now)
    save(store, store_path)
    requests.pop(key, None)
    save(pending, pending_path)
    return {'state': 'ready', 'slip': public_for(pick, now=now, store=store)}


def current_picks(root=ROOT):
    """Open official rows from the latest local site build, deduplicated by id."""
    rows = []
    for name, keys in [('today.json', ('picks',)), ('record.json', ('picks', 'cbbPicks', 'nbaPicks'))]:
        payload = load(Path(root) / 'site' / 'data' / 'app' / name, {})
        for key in keys:
            rows.extend(payload.get(key) or [])
    return list({row['id']: row for row in rows if isinstance(row, dict) and row.get('id')}.values())


def refresh_current(now=None, logger=print, **kwargs):
    now = now or datetime.now(timezone.utc)
    if not os.environ.get('UNABATED_API_KEY', '').strip():
        return {'configured': False, 'ready': 0, 'processing': 0, 'failed': 0}
    result = {'configured': True, 'ready': 0, 'processing': 0, 'failed': 0}
    client = kwargs.pop('client', None) or Client()
    for pick in current_picks():
        if not eligible(pick, now):
            continue
        try:
            state = refresh_pick(pick, now=now, client=client, **kwargs)['state']
            result['ready' if state in ('ready', 'current') else 'processing'] += 1
        except BetslipError as error:
            result['failed'] += 1
            logger(f'betslip: {pick.get("id")}: {error}')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='refresh', choices=('refresh', 'status'))
    args = parser.parse_args(argv)
    if args.command == 'status':
        payload = load()
        print(json.dumps({'configured': bool(os.environ.get('UNABATED_API_KEY', '').strip()),
                          'ready': sum(row.get('status') == 'ready' for row in (payload.get('slips') or {}).values()),
                          'updatedAt': payload.get('updatedAt')}, indent=2))
        return 0
    print(json.dumps(refresh_current(), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
