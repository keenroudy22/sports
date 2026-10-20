"""Published owner tickets, counted once apart from Best Bets. No assumed stakes.

Settlements are append-only corrections. A screenshot first shown after a win
cannot create a pregame publication. Injured legs do not rewrite ticket odds.
"""
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


def instant(value):
    try:
        when = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return when if when.tzinfo else None
    except (TypeError, ValueError):
        return None


def read(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def append(row, path=None):
    path = path or ROOT / 'data/community-results.jsonl'
    if row.get('result') not in ('win', 'loss', 'push', 'void') or not row.get('id') or not row.get('source') or not instant(row.get('settledAt')):
        raise ValueError('Settlement needs ticket, result, timestamp and evidence')
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
                    'resultSource': result.get('source'), 'accountingUnknown': True,
                    'units': None, 'riskUnits': None,
                    'delivery': {'xAt': post['sentAt'], 'link': post['link']}})
    return out
