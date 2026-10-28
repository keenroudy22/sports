"""NBA primary-prop delivery adapter; no feed calls and no model promotion.

Frozen probability error and official-book returns must both pass before a live
candidate exists. Public admission and final-send checks recompute this proof.
"""
import json
import hashlib
import inspect
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from statistics import mean
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import boxscores
import espn_props
import nba_capture
import nba_player_props as props
import nba_prop_probability as probability
import nba_prop_settlement as settlement
import nba_roles

VERSION = 'nba-primary-prop-release-v1'
STATS = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists'}
EASTERN = ZoneInfo('America/New_York')
ROLE_REASON = 'Same starting role across the last three games.'


def read_json(path):
    return json.loads(path.read_text())


def implementation_hash():
    """Freeze admission/evidence math, allowing unrelated card-format repairs."""
    source='\n'.join(inspect.getsource(f) for f in (implementation_hash,proof,candidates,verify))
    policy=json.dumps([VERSION,STATS,probability.VERSION,settlement.VERSION],sort_keys=True)
    return hashlib.sha256((source+policy).encode()).hexdigest()


def freeze(root, now):
    """Existing natural prop captures preregister this adapter before outcomes."""
    root=Path(root); folder=root/'prop-release-protocol'
    if boxscores.verify(folder):
        raise ValueError('NBA prop release protocol integrity failure')
    old=probability.read(folder)
    if any(r.get('id')==VERSION for r in old):
        return 0
    row=dict(id=VERSION, season=now.year, createdAt=boxscores.stamp(now),
        retrievedAt=boxscores.stamp(now), implementationHash=implementation_hash(),
        probabilityModel=probability.VERSION, settlementPolicy=settlement.VERSION,
        scope='DraftKings full-game pts/reb/ast; original frozen prices; independent book outcomes; no model promotion')
    return nba_capture.append_changed([row],folder,lambda r:r['id'])


def proof(stat, now, root=nba_capture.STORE):
    """One independent game weight; unresolved priced cases cannot disappear."""
    root = Path(root)
    if stat not in STATS:
        return None
    protocols=probability.read(root/'prop-release-protocol')
    matches=[r for r in protocols if r.get('id')==VERSION]
    protocol=matches[0] if len(matches)==1 else None
    if (not protocol or not protocol.get('createdAt') or boxscores.verify(root/'prop-release-protocol')
            or protocol.get('implementationHash')!=implementation_hash()
            or protocol.get('probabilityModel')!=probability.VERSION or protocol.get('settlementPolicy')!=settlement.VERSION
            or boxscores.instant(protocol['createdAt'])>now):
        return None
    studies = [r for r in probability.review(root, now) if r['stat'] == stat and r['evidenceReady']]
    if not studies:
        return None
    if (boxscores.verify(root.parent/'sport-box') or any(boxscores.verify(root/family)
            for family in ('probability-specs','probability-forecasts','player-forecasts','player-outcomes'))):
        return None
    specs = {r['specHash']: r for r in probability.read(root/'probability-specs') if probability.valid_spec(r)}
    originals = {}
    for r in probability.read(root/'player-forecasts'):
        originals.setdefault(r['id'], r)
    finals = {str(b['eventId']).removeprefix('NBA-'): b for b in nba_roles.available_boxes(
        probability.read(root.parent/'sport-box'), now)}
    for study in studies:
        spec = specs.get(study['specHash'])
        if not spec:
            continue
        first = {}
        for p in probability.read(root/'probability-forecasts'):
            if p.get('specHash') != study['specHash']:
                continue
            key = (p['eventId'], p['athleteId'], p['stat'])
            if key not in first or p['retrievedAt'] < first[key]['retrievedAt']:
                first[key] = p
        games = defaultdict(list); days = {}; evidence = []; unresolved = False
        for p in first.values():
            try:
                original = originals[p['forecastId']]
                if p['book'] != 'DraftKings' or p['eventId'] in spec['trainingEvents']:
                    continue
                at = boxscores.instant(p['retrievedAt']); kick = boxscores.instant(p['kickoff'])
                if not at < kick <= now or kick<=boxscores.instant(protocol['createdAt']):
                    continue
                expected = probability.predict(original, spec, at)
                if not expected or any(p.get(k) != v for k, v in expected.items()):
                    return None
                chosen = probability.shadow_price(p, 0)  # Choice never depends on the result.
                if not chosen:
                    continue
                final = finals.get(p['eventId'])
                if not final:
                    if now >= kick+timedelta(hours=6):
                        unresolved = True
                    continue
                if final.get('season') != original.get('season'):
                    return None
                terms = dict(original, side=chosen['side'], direction=chosen['side'])
                decision = settlement.evaluate(terms, final, now)
                if decision['state'] != 'settled':
                    unresolved = True
                    continue
                odds = p[chosen['side']]
                net = (odds/100 if odds > 0 else 100/-odds) if decision['result'] == 'win' else -1 if decision['result'] == 'loss' else 0
                games[p['eventId']].append(net)
                days[p['eventId']] = kick.astimezone(EASTERN).date().isoformat()
                evidence.append([p['id'], probability.digest(p), probability.digest(final), decision])
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                return None
        clusters = defaultdict(list)
        for event, values in games.items():
            clusters[days[event]].append(mean(values))
        lower = probability.lower95([mean(v) for v in clusters.values()])
        if (unresolved or len(games) < probability.MIN_TEST or len(clusters) < probability.MIN_DAYS
                or lower is None or lower <= 0):
            continue
        result = dict(adapter=VERSION, stat=stat, specHash=study['specHash'], games=len(games),
            easternDates=len(clusters), bookReturnLower95=lower,
            probabilityAllowance=.02+abs(study['meanProbabilityBias']),
            settlementPolicy=settlement.VERSION, study=study,
            protocolHash=probability.digest(protocol),
            bookEvidenceHash=probability.digest(evidence))
        result['evidenceHash'] = probability.digest(result)
        return result
    return None


def candidates(now, root=nba_capture.STORE, lead_minutes=60, diagnostics=None):
    root = Path(root)
    # Failed, absent or future evidence never becomes a candidate or a post.
    approvals = {s: p for s in STATS if (p := proof(s, now, root))}
    if diagnostics is not None:
        diagnostics.update(approvedMarkets=sorted(approvals),offers=0)
    if not approvals:
        return []
    slate = read_json(root/'slate.json'); injury = read_json(root/'injuries-current.json')
    if not props.fresh(injury.get('retrievedAt'), now, 1):
        return []
    games = {str(g['providerId']): g for g in slate['games']}
    specs = {s['specHash']: s for s in probability.read(root/'probability-specs') if probability.valid_spec(s)}
    out = []
    for r in props.build(now, root, limit=None)['rows']:
        try:
            stat = r['stat']; approved = approvals.get(stat); review = r.get('roleReview')
            role = r.get('currentRole') or {}
            if not review and role.get('games', 0) >= 3 and role.get('starts') in (0,3):
                review = dict(eventId=r['eventId'], athleteId=r['athleteId'], team=r['team'],
                    season=games[r['eventId']]['season'], kickoff=r['kickoff'], kind='role-only',
                    checkedAt=boxscores.stamp(max(boxscores.instant(injury['retrievedAt']),boxscores.instant(role['receivedAt']))),
                    headline='Stable observed current-season role',
                    explanation=ROLE_REASON,
                    sources=[dict(url=role['source'],label='ESPN official game summary'),
                        dict(url=r['availabilitySource'],label='Official NBA participation report')])
            if (not approved or r.get('hold') or r['book'] != 'DraftKings' or not r.get('projection')
                    or r['projection']['model'] != probability.BASELINE
                    or not review or review['kind'] != 'role-only'
                    or type(role.get('starts')) is not int or role['starts'] not in (0,3)
                    or r['projection'].get('window') != 'This season'
                    or r.get('currentRole', {}).get('games', 0) < 3
                    or not props.fresh(r['sourceAt'], now, 2)
                    or boxscores.instant(r['sourceAt']) < settlement.VERIFIED_AT
                    or any(abs(r[s])>400 for s in ('over','under'))):
                continue
            nba_roles.validate(review)
            if any(not (urlsplit(s['url']).hostname in ('nba.com','espn.com','site.api.espn.com')
                or (urlsplit(s['url']).hostname or '').endswith(('.nba.com','.espn.com'))) for s in review['sources']):
                continue
            game = games[r['eventId']]; kick = boxscores.instant(r['kickoff'])
            if kick <= now+timedelta(minutes=lead_minutes) or kick.astimezone(EASTERN).date() != now.astimezone(EASTERN).date():
                continue
            availability, holds = nba_capture.availability_for_game(injury, game, now, max_hours=1)
            # The baseline cannot redistribute a missing teammate's workload.
            if holds or any(nba_capture.blocks_availability(a.get('status')) for a in availability):
                continue
            reported = (injury.get('official') or {}).get('reportedAt')
            if not reported or boxscores.instant(review['checkedAt']) < boxscores.instant(reported):
                continue
            raw = dict(r, id='live-prop', model=probability.BASELINE, retrievedAt=r['sourceAt'], season=game['season'])
            predicted = probability.predict(raw, specs[approved['specHash']], now)
            if not predicted:
                continue
            choice = probability.shadow_price(predicted, 0)
            if not choice:
                continue
            side = choice['side']; chance = predicted['chanceOver'] if side == 'over' else 1-predicted['chanceOver']
            conservative = max(0, chance-approved['probabilityAllowance'])
            if (conservative-espn_props.implied(r[side]) < .04-1e-9
                    or (r['projection']['value'] > r['line']) != (side == 'over')):
                continue
            from social_copy import projection_free_reason
            reason = projection_free_reason(review['explanation'])
            if not reason:
                continue
            out.append(dict(id=f"NBA-prop-{r['eventId']}-{r['athleteId']}-{stat}-{side}-dk",
                eventId=game['id'], athleteId=r['athleteId'], team=r['team'], player=r['name'],
                stat=stat, period='full_game', league='NBA', season=game['season'], seasonType=2,
                kickoff=r['kickoff'], marketType='player', direction=side, line=r['line'], odds=r[side],
                oppositeOdds=r['under' if side=='over' else 'over'], book=r['book'], retrievedAt=r['sourceAt'],
                source=review['sources'][0]['url'], rawChance=chance, chance=conservative, calibrated=True,
                riskUnits=.5, roleChecked=True, sideVerified=True, exactLineVerified=True,
                game=game, reasons=list(dict.fromkeys([reason,ROLE_REASON])), projection=r['projection']['value'], model=probability.VERSION,
                propEvidence=approved, roleReview=review, availabilitySource=r['availabilitySource']))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
    if diagnostics is not None:
        diagnostics['offers']=len(out)
    return out


def verify(offer, now):
    try:
        return any(all(c.get(k) == offer.get(k) for k in (
            'id','eventId','athleteId','team','player','stat','period','league','season','seasonType',
            'kickoff','marketType','direction','line','odds','oppositeOdds','book','retrievedAt','source',
            'rawChance','chance','calibrated','projection','model','propEvidence','roleReview','reasons',
            'riskUnits','lane','legs','parlayType','paidProtection','allAction'))
            for c in candidates(now, lead_minutes=0))
    except (OSError, ValueError, TypeError, KeyError):
        return False


def selection(play):
    return f"{play['player']} {play['direction'].upper()} {play['line']:g} {STATS[play['stat']]}"


def card(play):
    import ticket_cards, ticket_kit
    teams = play['game']['teams']; home = teams['home']['abbreviation']; away = teams['away']['abbreviation']
    own = next(t['abbreviation'] for t in teams.values() if str(t['id']) == str(play['team']))
    data = dict(kind='player', player=play['player'], featured=False, seriesLabel='BEST BET',
        away=away, home=home, team=own, team_colors={a:('#17241f','#eef4ec') for a in (home,away)},
        when=boxscores.instant(play['kickoff']).astimezone(EASTERN).strftime('%b %-d · %-I:%M %p'),
        side=play['direction'].upper(), line=f"{play['line']:g}", market=play['stat'],
        odds=play['odds'], book=play['book'], units=play['riskUnits'], reason=play['reasons'][0],
        photo=None, team_logo=None, away_logo=None, home_logo=None, chance=None, needs=None)
    rendered = ticket_cards.play_card(data)
    issues = ticket_kit.qa(rendered, 'NBA primary prop')
    if issues:
        raise ValueError('; '.join(issues))
    return rendered.svg()


def injury_review(play, final, now, root=nba_capture.STORE, check=None):
    """Reuse the existing postgame researcher only for a published losing prop."""
    folder = Path(root)/'prop-injury-reviews'
    if boxscores.verify(folder):
        raise ValueError('NBA prop injury-review integrity failure')
    key = f"{play['eventId']}:{play['athleteId']}"
    previous = [r for r in probability.read(folder) if r.get('id') == key
        and boxscores.instant(r['checkedAt']) <= now]
    prior = previous[-1] if previous else None
    if prior and (prior.get('status') == 'no-injury' or now>=boxscores.instant(play['kickoff'])+timedelta(hours=12)
            or now-boxscores.instant(prior['checkedAt']) < timedelta(hours=6)):
        return prior
    if check is None:
        import researcher
        check = researcher.settlement_injury if researcher.enabled() else None
    try:
        game=dict(play['game'],league='NBA',away=play['game']['teams']['away'],home=play['game']['teams']['home'])
        answer = check(game, play['player'], now=now) if check else {}
    except Exception:
        answer = {}
    facts = answer.get('facts') or []; dropped = answer.get('dropped') or []
    checked = answer.get('checked') is True
    status = 'injured' if facts else 'unverified' if dropped else 'no-injury' if checked else 'failed'
    review = dict(id=key, season=play['season'], eventId=play['eventId'], athleteId=play['athleteId'],
        checkedAt=boxscores.stamp(now), retrievedAt=boxscores.stamp(now), checked=checked,
        status=status, source=(facts[0].get('source') if facts else None) or final['source'],
        facts=facts, dropped=dropped)
    nba_capture.append_changed([review], folder, lambda r:r['id'])
    return review


def grade(play, final, now, root=nba_capture.STORE, check=None):
    """Public, original-term grade; raw losses retain the desk's injury window."""
    if (play.get('stat') not in STATS or play.get('period') != 'full_game'
            or play.get('model') != probability.VERSION or play.get('book') != 'DraftKings'
            or final.get('season') != play.get('season')
            or boxscores.instant(play['publishedAt']) > now):
        return None
    decision = settlement.evaluate(play, final, now)
    actual = decision.get('actual'); review = None
    loss = (probability.numeric(actual) and actual != play['line']
            and (actual > play['line']) != (play['direction'] == 'over'))
    if loss:
        review = injury_review(play, final, now, root, check)
        decision = settlement.evaluate(play, final, now, review)
        deadline = boxscores.instant(play['kickoff'])+timedelta(hours=12)
        if decision.get('result') != 'void' and review['status'] != 'no-injury':
            if now < deadline:
                return None
            # Public desk fallback is explicit, not a claim of book-confirmed
            # settlement. Prospective book-return proof never uses this fallback.
            decision = dict(decision, state='fallback', result='loss', actual=actual,
                reason='12-hour desk fallback to official stats; injury/book evidence remains correctable')
    if decision['state'] not in ('settled','fallback') or decision.get('result') not in ('win','loss','push','void'):
        return None
    return dict(type='settle', id=play['id'], season=play['season'], seasonType=2, league='NBA',
        actual=decision.get('actual'), result=decision['result'], source=final['source'],
        settledAt=boxscores.stamp(now), retrievedAt=boxscores.stamp(now),
        bookSettlement=decision, injuryReview=review, settlementReason=decision['reason'])
