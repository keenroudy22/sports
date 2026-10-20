"""Published owner tickets, counted once apart from Best Bets. No assumed stakes.

Settlements are append-only corrections. A screenshot first shown after a win
cannot create a pregame publication. Injured legs do not rewrite ticket odds.
"""
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation

ROOT = Path(__file__).resolve().parents[1]


def instant(value):
    try:
        when = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return when if when.tzinfo else None
    except (TypeError, ValueError):
        return None


def read(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def accounting(row):
    """Use confirmed cash returns, including returned stake, not original voided odds."""
    names = ('stakeDollars', 'returnDollars', 'unitDollars')
    if not any(name in row for name in names):
        return {'accountingUnknown': True, 'units': None, 'riskUnits': None}
    try:
        if any(isinstance(row.get(name), bool) for name in names):
            raise ValueError('Boolean is not money')
        stake, returned, unit = [Decimal(str(row[name])) for name in names]
        if not all(n.is_finite() for n in (stake, returned, unit)) or stake <= 0 or unit <= 0 or returned < 0:
            raise ValueError('Invalid money')
        result = row.get('result')
        if result == 'win' and returned <= stake or result == 'loss' and returned >= stake or result in ('push', 'void') and returned != stake:
            raise ValueError('Cash return contradicts result')
        if result not in ('win', 'loss', 'push', 'void'):
            raise ValueError('Cash settlement needs a result')
    except (KeyError, InvalidOperation, ValueError) as error:
        raise ValueError('Confirmed stake, total return, unit size and consistent result required') from error
    return {'accountingUnknown': False, 'stakeDollars': float(stake), 'returnDollars': float(returned),
            'unitDollars': float(unit), 'units': float((returned-stake)/unit), 'riskUnits': float(stake/unit)}


def append(row, path=None):
    path = path or ROOT / 'data/community-results.jsonl'
    if row.get('result') not in ('win', 'loss', 'push', 'void') or not row.get('id') or not row.get('source') or not instant(row.get('settledAt')):
        raise ValueError('Settlement needs ticket, result, timestamp and evidence')
    accounting(row)
    existing = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if row in existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    return True


def build(root=ROOT):
    root = Path(root)
    posts = read(root / 'data/x-posted.json', {'posts': []})['posts']
    tickets = read(root / 'data/community.json', {'tickets': []})['tickets']
    path = root / 'data/community-results.jsonl'
    results = {r['id']: r for r in (json.loads(line) for line in path.read_text().splitlines())} if path.exists() else {}
    out, seen = [], set()
    for ticket in tickets:
        key = ticket.get('id')
        if key in seen:
            raise ValueError('Duplicate community ticket')
        seen.add(key)
        kickoff = instant(ticket.get('kickoff'))
        releases = [p for p in posts if p.get('id') == key and instant(p.get('sentAt')) and kickoff
                    and instant(p['sentAt']) < kickoff and p.get('link')]
        if not releases:
            continue
        post = min(releases, key=lambda p: p['sentAt'])
        result = results.get(key, {})
        out.append({**ticket, 'community': True, 'publishedAt': post['sentAt'], 'posted': True,
                    'season': kickoff.year, 'seasonType': 2, 'lane': 'personal',
                    'kind': 'parlays' if len(ticket.get('legs', [])) > 1 else 'props',
                    'parlayType': 'community' if len(ticket.get('legs', [])) > 1 else None,
                    'title': ticket.get('displayTitle') or ticket['title'],
                    'legs': [{'title': leg} for leg in ticket.get('legs', [])] if len(ticket.get('legs', [])) > 1 else [],
                    'result': result.get('result'), 'settledAt': result.get('settledAt'),
                    'entryNote': result.get('note') or 'Personal ticket; separate from Best Bets.',
                    'resultSource': result.get('source'), **accounting(result),
                    'delivery': {'xAt': post['sentAt'], 'link': post['link']}})
    return out
