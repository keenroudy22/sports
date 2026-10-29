"""Observed NFL Q1 rushing/receiving only; reconcile full feed to official boxes.

No projection, wager settlement, price or betting approval is inferred here.
"""
from collections import Counter, defaultdict

STATS = ('car', 'rushYds', 'rec', 'recYds')


def extract(payload, official, teams):
    import boxscores as bx
    if not isinstance(payload, dict) or not payload.get('items'):
        return {}
    items = payload['items']
    expected = payload.get('count')
    if isinstance(expected, int) and expected != len(items):
        return {}
    ids = [str(p.get('id', '')) for p in items]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        return {}
    full, first, plays = defaultdict(Counter), defaultdict(Counter), Counter()
    seen_q1 = set()
    for p in items:
        if not bx.scrimmage(p) or str(p.get('type', {}).get('text', '')).lower() in ('two-minute warning', 'end of regulation'):
            continue
        roles = defaultdict(set)
        for participant in p.get('participants', []):
            aid = bx.ref_id(participant.get('athlete'), 'athletes')
            if aid:
                roles[participant.get('type')].add(aid)
        passers, rushers = roles['passer'], roles['rusher']
        # A play without an offensive participant cannot establish coverage.
        if not passers and not rushers:
            return {}
        q = (p.get('period') or {}).get('number')
        if type(q) is not int or not 1 <= q <= 20:
            return {}
        team = bx.ref_id(p.get('start', {}).get('team'), 'teams') or bx.ref_id(p.get('team'), 'teams')
        if team not in teams or len(passers) > 1 or len(rushers) > 1 or (passers and rushers):
            return {}
        plays[team] += 1
        if q == 1:
            seen_q1.add(team)
        kind = str(p.get('type', {}).get('text', '')).lower()
        gained = p.get('statYardage')
        values = {}
        if rushers:
            if type(gained) is not int:
                return {}
            values[next(iter(rushers))] = {'car': 1, 'rushYds': gained}
        elif not roles['sackedBy'] and not any(word in kind for word in bx.NOT_COMPLETION):
            receivers = roles['receiver']
            if len(receivers) != 1 or type(gained) is not int:
                return {}
            values[next(iter(receivers))] = {'rec': 1, 'recYds': gained}
        for aid, stats in values.items():
            full[aid].update(stats)
            if q == 1:
                first[aid].update(stats)
    if seen_q1 != set(teams) or any(plays[t] != teams[t].get('plays') for t in teams):
        return {}
    # Check each player's family independently: an unresolved lateral for one
    # receiver must not manufacture his split or hide another player's exact log.
    result = {}
    for aid, p in official.items():
        if not any(k in p for k in STATS):
            continue
        values = {}
        for family in (('car', 'rushYds'), ('rec', 'recYds')):
            if all(full[aid][k] == p.get(k, 0) for k in family):
                values.update({k: first[aid][k] for k in family})
        if values:
            result[aid] = values
    return result


def backfill(event_ids, root=None):
    """Explicit, bounded plays-only enrichment of existing NFL finals; append only."""
    import copy
    import json
    from datetime import datetime, timezone
    import boxscores as bx
    root = root or bx.STORE
    if not 1 <= len(event_ids) <= 6 or len(set(event_ids)) != len(event_ids):
        raise ValueError('Supply one to six distinct stored NFL final event IDs')
    if bx.verify(root):
        raise ValueError('Existing box-score ledger failed verification')
    records = bx.stored(root)
    result = []
    for event in event_ids:
        old = records[str(event)]
        if old['league'] != 'NFL' or bx.instant(old['kickoff']) >= datetime.now(timezone.utc):
            raise ValueError('Only stored past NFL finals may be enriched')
        if old.get('firstQuarter'):
            result.append({'eventId': str(event), 'state': 'already-stored'})
            continue
        payload = bx.fetch_json(old['sources']['plays'], attempts=1)
        # No pagination probing/backfill fanout: leave unsupported pages missing.
        if payload.get('pageCount', 1) != 1:
            result.append({'eventId': str(event), 'state': 'held-pagination'})
            continue
        observed = extract(payload, {p['id']: p for p in old['players']}, old['teams'])
        if not observed:
            result.append({'eventId': str(event), 'state': 'held-reconciliation'})
            continue
        record = copy.deepcopy(old)
        record.update(firstQuarter=observed, retrievedAt=bx.stamp(datetime.now(timezone.utc)),
                      revision=int(old.get('revision', 1)) + 1)
        record['hash'] = bx.content_hash(record)
        bx.append(bx.store_path('NFL', old['season'], root), [record])
        result.append({'eventId': str(event), 'state': 'appended', 'players': len(observed)})
    bx.write_json(root / 'ledger.json', bx.ledger(root))
    return result


if __name__ == '__main__':
    import json
    import sys
    print(json.dumps(backfill(sys.argv[1:]), indent=2))
