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


class QuotaBlocked(RuntimeError):
    pass


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
