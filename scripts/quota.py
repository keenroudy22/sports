"""One fail-closed gate for every metered Odds API request. No secrets in the journal.

The free /sports endpoint reports account-wide usage across the Mac and hosted jobs.
Existing caller cadence/daily caps still apply. A 24-credit reserve covers overlapping
hosts; local callers serialize through a lock and reserve before sending. Failed calls
remain charged conservatively. This never changes a subscription or enables overages.
"""
import fcntl
import json
import hashlib
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'work' / 'quota'
CEILING = 500
RESERVE = 24
BUFFER_STOP = 2700
BUFFER_ESSENTIAL_STOP = 2900
# Kept as a compatibility name for historical reports/tests that describe the
# former dated trial.  The ceiling itself is now the permanent delivery lane.
BUFFER_TEMP_STOP = BUFFER_ESSENTIAL_STOP
BUFFER_TEMP_START = datetime(2026, 10, 26, 13, 55, tzinfo=timezone.utc)
BUFFER_TEMP_END = datetime(2026, 11, 6, 13, 5, tzinfo=timezone.utc)
BUFFER_DELIVERY_RESERVE = 300
BUFFER_ANALYTICS_PER_DAY = 3  # Sample engagement without crowding out actual publication.
SHARP_PER_MINUTE = 12


def observe_buffer_usage(used, limit, *, root=STATE, now=None):
    """Save an attended official Usage observation without deleting reservations.

    Caller must have read the signed-in Buffer API Usage page. Every subsequent
    reservation adds to this conservative baseline, even after calendar rollover.
    """
    now = now or datetime.now(timezone.utc)
    if type(used) is not int or type(limit) is not int or limit != 1000 or not 0 <= used <= limit:
        raise ValueError('Expected the observed single-channel Free allowance')
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    with (root/'buffer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        raw = (root/'buffer.jsonl').read_bytes() if (root/'buffer.jsonl').exists() else b''
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        value = dict(version=1, used=used, limit=limit, observedAt=now.isoformat(),
                     accountIdentity=hashlib.sha256((os.environ.get('BUFFER_CHANNEL','')+'|'+os.environ.get('BUFFER_TOKEN','')).encode()).hexdigest(),
                     source='https://publish.buffer.com/settings/api',
                     method='attended-official-usage', journalBytes=len(raw), journalRows=len(rows),
                     journalHash=hashlib.sha256(raw).hexdigest())
        path=root/'buffer-observation.json'; temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value)+'\n'); temporary.replace(path)
    return value


def observed_buffer_usage(root, rows, now):
    """Conservative provider baseline plus all appended local attempts. No reset."""
    path=Path(root)/'buffer-observation.json'
    if not path.exists(): return None
    try:
        value=json.loads(path.read_text()); at=datetime.fromisoformat(value['observedAt'])
        raw=(Path(root)/'buffer.jsonl').read_bytes() if (Path(root)/'buffer.jsonl').exists() else b''
        size=value['journalBytes']; count=value['journalRows']
        if (value['version'] != 1 or value['method'] != 'attended-official-usage'
                or value.get('accountIdentity') != hashlib.sha256((os.environ.get('BUFFER_CHANNEL','')+'|'+os.environ.get('BUFFER_TOKEN','')).encode()).hexdigest()
                or value['source'] != 'https://publish.buffer.com/settings/api'
                or type(value['used']) is not int or value['limit'] != 1000
                or not 0 <= value['used'] <= 1000
                or type(size) is not int or not 0 <= size <= len(raw)
                or type(count) is not int or not 0 <= count <= len(rows)
                or len([line for line in raw[:size].splitlines() if line.strip()]) != count
                or hashlib.sha256(raw[:size]).hexdigest() != value['journalHash']
                or not 0 <= (now-at).total_seconds() < 30*86400):
            raise ValueError('Invalid observation anchor')
        return value['used'] + sum(r['count'] for r in rows[count:])
    except (OSError, ValueError, KeyError, TypeError):
        raise QuotaBlocked('Buffer usage observation needs review') from None


class QuotaBlocked(RuntimeError):
    pass


def current_month_usage(value, now=None):
    """A stored provider balance only applies to the UTC month that produced it.

    Returning an empty mapping makes callers fall through to the live, fail-closed
    usage probe after a month rolls over instead of carrying the old reserve into
    the new allowance.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(value, dict) or not value.get('at'):
        return {}
    try:
        observed = datetime.fromisoformat(str(value['at']).replace('Z', '+00:00'))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return {}
    return value if observed.astimezone(timezone.utc).strftime('%Y-%m') == now.astimezone(timezone.utc).strftime('%Y-%m') else {}


def temporary_buffer_allowance(now):
    """Whether the historical owner trial was active (reporting only)."""
    return BUFFER_TEMP_START <= now < BUFFER_TEMP_END


def buffer_request_stop(essential=False, operation=None):
    """Return the fail-closed stop for this Buffer request.

    Official publication and the control-plane reads needed to reconcile it may
    use the protected 2700-2899 lane.  Optional/editorial work never can, and
    the final 100 requests of the free allowance remain untouched.
    """
    control = operation in ('status', 'channels', 'limits', 'cancel')
    return BUFFER_ESSENTIAL_STOP if essential or control else BUFFER_STOP


def count_request(provider, root=STATE, now=None, optional=False, reserve=True, operation=None, essential=False):
    """Reserve one free-plan request before sending it; fail closed at local caps."""
    if provider not in ('sharp', 'buffer'):
        raise ValueError('unknown free-plan request counter')
    if operation not in (None, 'publish', 'status', 'analytics', 'channels', 'limits', 'cancel', 'other'):
        raise ValueError('unknown request operation')
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / f'{provider}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal = root / f'{provider}.jsonl'
        try:
            rows = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()] if journal.exists() else []
            if not all(isinstance(row, dict) and row.get('provider') == provider and
                       isinstance(row.get('count'), int) and row['count'] == 1 and row.get('at') for row in rows):
                raise ValueError('invalid journal')
            month = now.astimezone(timezone.utc).strftime('%Y-%m')
            stop = buffer_request_stop(essential, operation) if provider == 'buffer' else BUFFER_STOP
            if provider == 'buffer':
                # The provider also enforces a rolling window. Calendar rollover
                # must not reset the local protection or spend delivery reserves
                # on optional analytics. Historical journals remain unchanged.
                rolling = sum(row['count'] for row in rows
                              if 0 <= (now - datetime.fromisoformat(row['at'])).total_seconds() < 30 * 86400)
                monthly = sum(row['count'] for row in rows if row.get('month') == month)
                observed = observed_buffer_usage(root, rows, now)
                if observed is not None:
                    rolling = monthly = observed
                    stop = 950 if essential or operation in ('status','channels','limits','cancel') else 900
                if monthly >= stop:
                    raise QuotaBlocked('Buffer local free-plan request cap reached')
                if rolling >= stop:
                    raise QuotaBlocked('Buffer local free-plan rolling 30-day cap reached')
                if optional and max(rolling, monthly) >= min(BUFFER_STOP - BUFFER_DELIVERY_RESERVE, stop-100):
                    raise QuotaBlocked('Buffer delivery reserve protected; optional analytics deferred')
                if optional and sum(row['count'] for row in rows
                        if row.get('operation') == 'analytics'
                        and datetime.fromisoformat(row['at']).astimezone(timezone.utc).date()
                        == now.astimezone(timezone.utc).date()) >= BUFFER_ANALYTICS_PER_DAY:
                    raise QuotaBlocked('Buffer daily analytics reserve protected; optional analytics deferred')
            if provider == 'sharp':
                recent = [row for row in rows if 0 <= (now - datetime.fromisoformat(row['at'])).total_seconds() < 60]
                if len(recent) >= SHARP_PER_MINUTE:
                    raise QuotaBlocked('SharpAPI 12-per-minute free-plan cap reached')
        except (OSError, ValueError, TypeError, KeyError):
            raise QuotaBlocked('free-plan request journal unavailable') from None
        if not reserve:
            return
        row = {'month': now.astimezone(timezone.utc).strftime('%Y-%m'),
                                     'at': now.astimezone(timezone.utc).isoformat(),
                                     'provider': provider, 'count': 1}
        if provider == 'buffer' and optional:
            row['operation'] = 'analytics'
        elif operation is not None:
            row['operation'] = operation
        if provider == 'buffer' and essential:
            row['essentialDelivery'] = True
        with (root / f'{provider}.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())


def buffer_block_reason(root=STATE, now=None, optional=False, essential=False):
    """Local read-only preflight; never a reservation or provider balance claim.

    The send path still reserves atomically. This prevents an exhausted transport
    from waking an expensive whole-desk result rebuild on every retry.
    """
    try:
        count_request('buffer', root, now, optional=optional, reserve=False, essential=essential)
    except QuotaBlocked as error:
        return str(error)
    return None


def monthly_counts(root=STATE, now=None):
    """Current UTC-month request totals. Corrupt rows are unknown, never secrets."""
    now = now or datetime.now(timezone.utc)
    month = now.astimezone(timezone.utc).strftime('%Y-%m')
    out = {'sharp': 0, 'buffer': 0}
    for provider in out:
        path = Path(root) / f'{provider}.jsonl'
        try:
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        except (OSError, ValueError, TypeError):
            continue
        out[provider] = sum(int(row.get('count') or 0) for row in rows
                            if isinstance(row, dict) and row.get('provider') == provider and row.get('month') == month)
    return out


def usage(headers):
    try:
        used = int(headers['x-requests-used'])
        remaining = int(headers['x-requests-remaining'])
    except (KeyError, TypeError, ValueError):
        raise QuotaBlocked('account usage unavailable') from None
    if min(used, remaining) < 0 or used + remaining != CEILING:
        raise QuotaBlocked('free 500-credit allowance not confirmed')
    return used, remaining


def guarded_json(request, cost, reserve=RESERVE, opener=None, root=STATE, now=None, timeout=60):
    opener = opener or urllib.request.urlopen
    now = now or datetime.now(timezone.utc)
    if not isinstance(cost, int) or isinstance(cost, bool) or not 1 <= cost <= 12:
        raise QuotaBlocked('unexpected request cost')
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    parsed = urllib.parse.urlsplit(url)
    key = urllib.parse.parse_qs(parsed.query).get('apiKey', [])
    if parsed.scheme != 'https' or parsed.hostname != 'api.the-odds-api.com' or not key:
        raise QuotaBlocked('unexpected provider')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'odds.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal = root / 'odds.jsonl'
        try:
            rows = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
            probe = 'https://api.the-odds-api.com/v4/sports/?' + urllib.parse.urlencode({'apiKey': key[0]})
            with opener(probe, timeout=timeout) as response:
                used, remaining = usage(response.headers)
            # Never reclaim a locally reserved request merely because the service's counter lags.
            month = now.strftime('%Y-%m')
            floor = max([used] + [int(r['reservedThrough']) for r in rows if r['month'] == month])
            if CEILING - floor - cost < max(RESERVE, reserve):
                raise QuotaBlocked('free reserve reached')
            row = {'month': month, 'at': now.isoformat(), 'provider': 'odds-api',
                   'cost': cost, 'accountUsed': used, 'reservedThrough': floor + cost}
            with journal.open('a') as handle:
                handle.write(json.dumps(row, sort_keys=True) + '\n')
                handle.flush()
                os.fsync(handle.fileno())
        except QuotaBlocked:
            raise
        except Exception:
            raise QuotaBlocked('usage check or reservation failed') from None
        # Exceptions never include a URL/key in this module's public error text.
        try:
            with opener(request, timeout=timeout) as response:
                headers = {h: response.headers.get(h) for h in
                           ('x-requests-remaining', 'x-requests-used', 'x-requests-last')}
                return json.load(response), headers
        except Exception:
            raise QuotaBlocked('request failed; reservation retained') from None
