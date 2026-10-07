"""One fail-closed gate for every metered Odds API request. No secrets in the journal.

The free /sports endpoint reports account-wide usage across the Mac and hosted jobs.
Existing caller cadence/daily caps still apply. A 24-credit reserve covers overlapping
hosts; local callers serialize through a lock and reserve before sending. Failed calls
remain charged conservatively. This never changes a subscription or enables overages.
"""
import fcntl
import json
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
SHARP_PER_MINUTE = 12


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


def count_request(provider, root=STATE, now=None):
    """Reserve one free-plan request before sending it; fail closed at local caps."""
    if provider not in ('sharp', 'buffer'):
        raise ValueError('unknown free-plan request counter')
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
            if provider == 'buffer' and sum(row['count'] for row in rows if row.get('month') == month) >= BUFFER_STOP:
                raise QuotaBlocked('Buffer local free-plan request cap reached')
            if provider == 'sharp':
                recent = [row for row in rows if 0 <= (now - datetime.fromisoformat(row['at'])).total_seconds() < 60]
                if len(recent) >= SHARP_PER_MINUTE:
                    raise QuotaBlocked('SharpAPI 12-per-minute free-plan cap reached')
        except (OSError, ValueError, TypeError, KeyError):
            raise QuotaBlocked('free-plan request journal unavailable') from None
        with (root / f'{provider}.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'month': now.astimezone(timezone.utc).strftime('%Y-%m'),
                                     'at': now.astimezone(timezone.utc).isoformat(),
                                     'provider': provider, 'count': 1}, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())


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
