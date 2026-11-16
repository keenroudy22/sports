"""Published owner tickets, counted once apart from Best Bets. No assumed stakes.

Settlements are append-only corrections. A screenshot first shown after a win
cannot create a pregame publication. Injured legs do not rewrite ticket odds.
"""
import json
import re
import os
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
    publish_projection = path is None
    path = Path(path) if path is not None else private_root() / 'community-results.jsonl'
    if row.get('result') not in ('win', 'loss', 'push', 'void') or not row.get('id') or not row.get('source') or not instant(row.get('settledAt')):
        raise ValueError('Settlement needs ticket, result, timestamp and evidence')
    accounting(row)
    existing = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if row in existing:
        if publish_projection:
            append_public(row, root=ROOT)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    if publish_projection:
        path.chmod(0o600)
        append_public(row, root=ROOT)
    return True


# Public projection: new private ticket fields must never become public by default.
PUBLIC_TICKET_FIELDS = frozenset(('id', 'title', 'displayTitle', 'league', 'kind',
    'odds', 'baseOdds', 'priceBoosted', 'book', 'kickoff', 'status', 'quotedAt',
    'personalTicket'))


def public_note(result):
    note = str(result.get('publicNote') or result.get('note') or '')
    if re.search(r'[$£€]|\b(?:dollars?|usd|stake|payout|bet[ -]?id|wager[ -]?id)\b', note, re.I):
        return 'Confirmed settlement; accounting shown in units.'
    return note or 'Personal ticket; separate from Best Bets.'


PUBLIC_SOURCE_FIELDS = PUBLIC_TICKET_FIELDS | frozenset(('legs', 'card', 'riskUnits', 'parlayType'))
PUBLIC_SETTLEMENT_FIELDS = frozenset(('id', 'result', 'settledAt', 'cashout', 'publicNote',
                                     'accountingUnknown', 'units', 'riskUnits'))


def private_root():
    return Path(os.environ.get('KEENROUDY_CONF', str(Path.home() / '.config/keenroudy'))) / 'community-private'


def public_settlement(row):
    values = accounting(row)
    return {'id': row['id'], 'result': row['result'], 'settledAt': row['settledAt'],
            'cashout': row.get('cashout') is True, 'publicNote': public_note(row),
            **{key: values[key] for key in ('accountingUnknown', 'units', 'riskUnits')}}


def append_public(row, root=ROOT):
    """Publish only unit accounting; retrying a private append cannot duplicate it."""
    target = Path(root) / 'data/community-settlements.jsonl'
    projected = public_settlement(row)
    existing = [json.loads(line) for line in target.read_text().splitlines()] if target.exists() else []
    if projected not in existing:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('a') as stream:
            stream.write(json.dumps(projected, sort_keys=True) + '\n')


def public_accounting(row):
    if not row:
        return {'accountingUnknown': True, 'units': None, 'riskUnits': None}
    if (not row.get('id') or not instant(row.get('settledAt'))
            or row.get('result') not in ('win', 'loss', 'push', 'void')):
        raise ValueError('Invalid public settlement identity, time or result')
    if set(row) - PUBLIC_SETTLEMENT_FIELDS:
        raise ValueError('Unreviewed field in public community settlement')
    if row.get('accountingUnknown') is True and row.get('units') is None and row.get('riskUnits') is None:
        return {'accountingUnknown': True, 'units': None, 'riskUnits': None}
    risk, units = row.get('riskUnits'), row.get('units')
    if (row.get('accountingUnknown') is not False or isinstance(risk, bool) or isinstance(units, bool)
            or not isinstance(risk, (int, float)) or not isinstance(units, (int, float))
            or not Decimal(str(risk)).is_finite() or not Decimal(str(units)).is_finite()
            or risk <= 0 or units < -risk
            or (row.get('result') == 'win' and units <= 0)
            or (row.get('result') == 'loss' and units >= 0)
            or (row.get('result') in ('push', 'void') and units != 0)):
        raise ValueError('Invalid public unit accounting')
    return {'accountingUnknown': False, 'units': units, 'riskUnits': risk}


def source_privacy_issues(root=ROOT):
    root = Path(root)
    issues = []
    if (root / 'data/community-results.jsonl').exists():
        issues.append('Private accounting ledger must live outside the public checkout')
    for ticket in read(root / 'data/community.json', {'tickets': []})['tickets']:
        if set(ticket) - PUBLIC_SOURCE_FIELDS:
            issues.append('Unreviewed field in public community ticket')
    path = root / 'data/community-settlements.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            row = json.loads(line)
            public_accounting(row)
            if public_note(row) != row.get('publicNote'):
                issues.append('Private text in public community settlement')
    return issues


def build(root=ROOT):
    root = Path(root)
    posts = read(root / 'data/x-posted.json', {'posts': []})['posts']
    tickets = read(root / 'data/community.json', {'tickets': []})['tickets']
    path = root / 'data/community-settlements.jsonl'
    public_source = path.exists()
    if public_source:
        issues = source_privacy_issues(root)
        if issues:
            raise ValueError('; '.join(issues))
    else:
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
        out.append({**{k: v for k, v in ticket.items() if k in PUBLIC_TICKET_FIELDS}, 'community': True, 'publishedAt': post['sentAt'], 'posted': True,
                    'season': kickoff.year, 'seasonType': 2, 'lane': 'personal',
                    'kind': ('parlays' if len(ticket.get('legs', [])) > 1 else
                             ticket['kind'] if ticket.get('kind') in ('spreads', 'totals', 'moneyline') else 'props'),
                    'parlayType': 'community' if len(ticket.get('legs', [])) > 1 else None,
                    'title': ticket.get('displayTitle') or ticket['title'],
                    'legs': [{'title': leg.get('title', '') if isinstance(leg, dict) else leg}
                             for leg in ticket.get('legs', [])] if len(ticket.get('legs', [])) > 1 else [],
                    'result': result.get('result'), 'settledAt': result.get('settledAt'),
                    'cashout': result.get('cashout') is True,
                    'entryNote': public_note(result),
                    **{k: v for k, v in (public_accounting(result) if public_source else accounting(result)).items()
                       if k in ('accountingUnknown', 'units', 'riskUnits')},
                    'delivery': {'xAt': post['sentAt'], 'link': post['link']}})
    return out
