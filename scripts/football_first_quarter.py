"""Observed NFL Q1 rushing/receiving only; reconcile full feed to official boxes.

No projection, wager settlement, price or betting approval is inferred here.
"""
from collections import Counter, defaultdict

STATS = ('car', 'rushYds', 'rec', 'recYds')


def extract(payload, official, teams, supplements=None, counts=None):
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
    replay_snaps, unknown_stats = set(), set()
    seen_q1 = set()
    for p in items:
        # Provider replay corrections sometimes have a second ID for the same snap.
        # Require identical real timestamp, drive, clock, states, primary roles and
        # positive rushing yardage plus an explicit replay-spot note.
        if p.get('wallclock') and 'ball spot was assisted by replay' in str(p.get('text', '')).lower():
            import json
            roles_key = sorted((v.get('type'), bx.ref_id(v.get('athlete'), 'athletes'))
                               for v in p.get('participants', []) if v.get('type') in ('passer','rusher','receiver'))
            key = json.dumps([p['wallclock'], p.get('drive'), p.get('period'), p.get('clock'), p.get('start'), p.get('end'), p.get('statYardage'), roles_key], sort_keys=True)
            if p.get('type', {}).get('text') == 'Rush' and type(p.get('statYardage')) is int and p['statYardage'] > 0:
                if key in replay_snaps:
                    continue
                replay_snaps.add(key)
        supplement = (supplements or {}).get(str(p.get('id')))
        if supplement:
            q = (p.get('period') or {}).get('number')
            team = bx.ref_id(p.get('start', {}).get('team'), 'teams') or bx.ref_id(p.get('team'), 'teams')
            if type(q) is not int or not 1 <= q <= 20 or team not in teams or supplement['team'] != team:
                return {}
            if not supplement['plays']:
                continue
            plays[team] += 1
            if q == 1:
                seen_q1.add(team)
            for aid, keys in supplement.get('unknown', {}).items():
                unknown_stats.update((aid, k) for k in keys)
            for aid, stats in supplement['players'].items():
                full[aid].update(stats)
                if q == 1:
                    first[aid].update(stats)
            continue
        kind = str(p.get('type', {}).get('text', '')).lower()
        # ESPN may append PAT prose to a touchdown. Its typed TD/yardage and
        # passer/receiver/rusher roles describe the scoring play; pat* roles do not.
        combined_td = (kind in ('passing touchdown', 'rushing touchdown')
                       and (p.get('scoringType') or {}).get('name') == 'touchdown'
                       and 'no play' not in str(p.get('text', '')).lower())
        if (not bx.scrimmage(p) and not combined_td) or kind in ('two-minute warning', 'end of regulation'):
            continue
        roles = defaultdict(set)
        for participant in p.get('participants', []):
            aid = bx.ref_id(participant.get('athlete'), 'athletes')
            if aid:
                roles[participant.get('type')].add(aid)
        passers, rushers = roles['passer'], roles['rusher']
        if not passers and not rushers and (roles['punter'] or roles['kicker']):
            continue  # return fumbles are special teams, not offensive snaps
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
    if counts is not None:
        counts.update(plays)
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
            if not any((aid,k) in unknown_stats for k in family) and all(full[aid][k] == p.get(k, 0) for k in family):
                values.update({k: first[aid][k] for k in family})
        if values:
            result[aid] = values
    return result


def complete(official, observed):
    expected = [str(aid) for aid, row in official.items() if any(k in row for k in STATS)]
    return bool(expected) and all(all(k in observed.get(aid, {}) for k in STATS) for aid in expected)


def resolve(payload, official, teams, fetch, diagnostics=None):
    """Use exact provider play statistics only when the basic feed cannot reconcile.

    Bounded to 192 supplemental reads per game, no retries. Original play identities,
    full-game team counts and independent player-family totals still must agree.
    """
    import boxscores as bx
    import hashlib
    import json
    import re
    from urllib.parse import urlparse
    observed = extract(payload, official, teams)
    if complete(official, observed):
        return observed, {}
    supplements, cache = {}, {}
    def read(ref, play_id, owner_kind, owner_id):
        u = urlparse(ref)
        if u.hostname != 'sports.core.api.espn.com' or not re.search(
                rf'/events/(\d+)/competitions/\1/plays/{re.escape(play_id)}/{owner_kind}/{re.escape(owner_id)}/statistics/0$', u.path):
            raise ValueError('Not a matching provider play-stat reference')
        url = 'https://' + u.netloc + u.path + ('?' + u.query if u.query else '')
        if url not in cache:
            if len(cache) >= 192:
                raise ValueError('Quarter supplement request limit')
            data = fetch(url)
            # Mark attempted reads too: failures never cause an unbounded retry loop.
            cache[url] = data
        data = cache[url]
        if (data.get('splits') or {}).get('name') != 'play' or bx.ref_id(data.get('play'), 'plays') != play_id:
            raise ValueError('Wrong play-stat response')
        owner = 'athlete' if owner_kind == 'participants' else 'team'
        if bx.ref_id(data.get(owner), 'athletes' if owner == 'athlete' else 'teams') != owner_id:
            raise ValueError('Wrong play-stat owner')
        values = {s['name']: s.get('value') for c in data['splits'].get('categories', []) for s in c.get('stats', [])}
        return values, url, hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    try:
        mismatch, missing_players = set(), set()
        for phase in range(2):
            for p in (payload or {}).get('items', []):
                roles = {v.get('type') for v in p.get('participants', [])}
                kind, text = str(p.get('type', {}).get('text', '')).lower(), str(p.get('text', '')).lower()
                offensive = bool(roles & {'passer', 'rusher'})
                typed_td = (kind in ('passing touchdown','rushing touchdown') and (p.get('scoringType') or {}).get('name') == 'touchdown' and 'no play' not in text)
                suspect = ('fumble' in kind or 'reversed.' in text or 'pnlty' in text or 'lateral' in text or {'passer','rusher'} <= roles
                           or (p.get('isPenalty') and offensive) or (offensive and not bx.scrimmage(p) and not typed_td))
                if str(p.get('id')) in supplements:
                    continue
                team = bx.ref_id(p.get('start', {}).get('team'), 'teams') or bx.ref_id(p.get('team'), 'teams')
                family_play = bool(missing_players & {bx.ref_id(v.get('athlete'), 'athletes') for v in p.get('participants', []) if v.get('type') in ('rusher','receiver','other','recoverer','scorer')})
                if not suspect and not (phase and family_play and not typed_td):
                    continue
                pid = str(p.get('id', ''))
                team = bx.ref_id(p.get('start', {}).get('team'), 'teams') or bx.ref_id(p.get('team'), 'teams')
                participant = next((v for v in p.get('teamParticipants', [])
                                    if v.get('type') == 'offense' and bx.ref_id(v.get('team'), 'teams') == team), None)
                ref = ((participant or {}).get('playStatistics') or {}).get('$ref')
                if not ref:
                    continue
                values, url, digest = read(ref, pid, 'teams', team)
                n = values.get('totalOffensivePlays', values.get('totalPlays'))
                if type(n) not in (float, int) or n not in (0, 1):
                    continue
                if not suspect and n == 1 and not family_play:
                    continue
                item = {'team': team, 'plays': int(n), 'players': {}, 'sources': [url], 'hashes': [digest]}
                if n:
                    for v in p.get('participants', []):
                        aid = bx.ref_id(v.get('athlete'), 'athletes')
                        own_other = (v.get('type') in ('other','recoverer','scorer') and str(official.get(aid, {}).get('team')) == team and any(k in official.get(aid, {}) for k in STATS))
                        if v.get('type') not in ('passer', 'rusher', 'receiver') and not own_other:
                            continue
                        ref = (v.get('playStatistics') or {}).get('$ref')
                        if aid in item['players']:
                            continue
                        if not ref:
                            raise ValueError('Counted offensive play lacks player statistics')
                        values, url, digest = read(ref, pid, 'participants', aid)
                        names = {'car':'rushingAttempts','rushYds':'rushingYards','rec':'receptions','recYds':'receivingYards'}
                        stats = {}
                        for family in (('car','rushYds'),('rec','recYds')):
                            if all(type(values.get(names[k])) in (float,int) and int(values[names[k]]) == values[names[k]] for k in family):
                                stats.update({k:int(values[names[k]]) for k in family})
                            elif all(k not in official.get(aid,{}) for k in family):
                                stats.update({k:0 for k in family})  # official whole-game family is absent
                            else:
                                item.setdefault('unknown',{}).setdefault(aid,[]).extend(family)
                        item['players'][aid] = stats
                        item['sources'].append(url); item['hashes'].append(digest)
                supplements[pid] = item
            observed_counts = {}
            result = extract(payload, official, teams, supplements, observed_counts)
            if complete(official, result):
                return result, supplements
            mismatch = {t for t in teams if observed_counts.get(t, 0) != teams[t].get('plays')}
            missing_players = {str(aid) for aid, row in official.items() if any(k in row for k in STATS) and not all(k in result.get(str(aid), {}) for k in STATS)} if result else set()
            if mismatch:
                if diagnostics is not None:
                    diagnostics['teamPlayCounts'] = dict(observed_counts)
                    diagnostics['expectedTeamPlays'] = {t:teams[t].get('plays') for t in teams}
                break
            if not missing_players:
                break
    except Exception as error:
        if diagnostics is not None:
            diagnostics['error'] = f'{type(error).__name__}: {error}'[:160]
        # Partial exact supplements may resolve other families; remaining gaps stay held.
        pass
    if diagnostics is not None:
        diagnostics['reads'] = len(cache)
    return extract(payload, official, teams, supplements), supplements

def append_enrichment(old, payload, observed, evidence, root, now):
    """Append a reproducible quarter-only revision, preserving official capture age."""
    import copy
    import boxscores as bx
    if not observed or extract(payload, {p['id']:p for p in old['players']}, old['teams'], evidence) != observed:
        raise ValueError('Quarter evidence does not reproduce the split')
    if observed == old.get('firstQuarter'):
        return False
    if any(not set(stats).issubset(observed.get(aid, {})) for aid, stats in old.get('firstQuarter', {}).items()):
        return False
    record = copy.deepcopy(old)
    history = [r for r in bx.read_store(bx.store_path('NFL', old['season'], root))
               if r['eventId'] == old['eventId'] and r['players'] == old['players'] and r['teams'] == old['teams']]
    record['officialRetrievedAt'] = old.get('officialRetrievedAt') or min(r['retrievedAt'] for r in history)
    record.update(firstQuarter=observed, quarterCapturedAt=bx.stamp(now),
                  revision=int(old.get('revision',1))+1)
    if evidence:
        record['quarterPlayStats'] = evidence
    record['hash'] = bx.content_hash(record)
    bx.append(bx.store_path('NFL', old['season'], root), [record])
    return True


def repair(status, now, root=None, limit=2, fetch=None, log=print):
    """Existing final-capture job repairs at most two current-season gaps/day/game."""
    import boxscores as bx
    from datetime import timedelta
    root = root or bx.STORE
    fetch = fetch or (lambda url: bx.fetch_json(url, attempts=1))
    rows = bx.stored(root)
    nfl = [r for r in rows.values() if r['league']=='NFL' and r.get('seasonType')==2]
    season = max((r['season'] for r in nfl), default=0)
    attempts = status.setdefault('quarterRepair', {})
    todo = [r for r in nfl if r['season']==season and bx.instant(r['kickoff']) < now
            and not complete({p['id']:p for p in r['players']}, r.get('firstQuarter', {}))
            and (r['eventId'] not in attempts or now-bx.instant(attempts[r['eventId']]['at']) >= timedelta(days=1))]
    todo.sort(key=lambda r:(attempts.get(r['eventId'],{}).get('at',''), r['kickoff'], r['eventId']))
    written = 0
    for old in todo[:max(0,min(limit,2))]:
        state, diagnostic = 'held', {}
        try:
            payload = fetch(old['sources']['plays'])
            diagnostic = {}
            observed = extract(payload, {p['id']:p for p in old['players']}, old['teams'])
            evidence = {}
            if observed and append_enrichment(old,payload,observed,evidence,root,now):
                written += 1
            state = 'complete' if complete({p['id']:p for p in old['players']},observed) else 'held'
        except Exception as error:
            state = 'error:' + type(error).__name__
        attempts[old['eventId']] = {'at':bx.stamp(now),'state':state}
        if state != 'complete':
            attempts[old['eventId']]['diagnostics'] = diagnostic
        log(f"1Q repair {old['eventId']}: {state}")
    return written


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
        if complete({p['id']: p for p in old['players']}, old.get('firstQuarter', {})):
            result.append({'eventId': str(event), 'state': 'already-stored'})
            continue
        payload = bx.fetch_json(old['sources']['plays'], attempts=1)
        # No pagination probing/backfill fanout: leave unsupported pages missing.
        if payload.get('pageCount', 1) != 1:
            result.append({'eventId': str(event), 'state': 'held-pagination'})
            continue
        observed, evidence = resolve(payload, {p['id']: p for p in old['players']}, old['teams'], lambda url: bx.fetch_json(url, attempts=1))
        if not observed:
            result.append({'eventId': str(event), 'state': 'held-reconciliation'})
            continue
        append_enrichment(old, payload, observed, evidence, root, datetime.now(timezone.utc))
        result.append({'eventId': str(event), 'state': 'appended', 'players': len(observed)})
    bx.write_json(root / 'ledger.json', bx.ledger(root))
    return result


if __name__ == '__main__':
    import json
    import sys
    print(json.dumps(backfill(sys.argv[1:]), indent=2))
