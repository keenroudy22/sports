"""Reviewed prop tickets through the existing football release and result workers.

Evidence stays private. NFL MNF/TNF uses the normal append-only report, native
card, Discord-first release and Buffer workflow. NBA candidate validation shares
this contract; NBA public ledger/delivery integration is not enabled here.
"""
import copy
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gates
import prop_ticket_review as review
import prop_ticket_settlement as settlement
from fun_ticket_review import https

METHOD = review.METHOD
CONF = Path(os.environ.get('KEENROUDY_CONF', str(Path.home() / '.config/keenroudy')))
PUBLIC_LEG_FIELDS = ('gameId', 'athleteId', 'player', 'market', 'direction', 'line',
                     'period', 'book', 'odds', 'alternate', 'kickoff')


def path(key, conf=None):
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9-]+', key):
        raise ValueError('Invalid prop-ticket identity')
    return Path(conf or CONF) / 'prop-ticket-releases' / (key + '.json')


def load(key, conf=None):
    try:
        value = json.loads(path(key, conf).read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(key, packet, conf=None):
    target = path(key, conf)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(packet, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(target)


def evaluate(spec, ctx, now):
    try:
        return review.review(spec, ctx.games, now, first=ctx.first, latest=ctx.latest,
                             risk_external=getattr(ctx, 'risk_external', {}))
    except (AttributeError, KeyError, TypeError, ValueError):
        return {'state': 'held', 'holds': ['Malformed private prop-ticket evidence; review required']}


def candidate(spec, ctx, now):
    checked = evaluate(spec, ctx, now)
    if checked['state'] != 'reviewed-private':
        return None, '; '.join(checked['holds'])
    policy = spec.get('settlementPolicy') or {}
    if (not isinstance(policy, dict) or policy.get('verified') is not True
            or policy.get('book') != spec['book'] or policy.get('jurisdiction') != 'IN'
            or not https(policy.get('source'), spec['book'])
            or not policy.get('ruleVersion') or not policy.get('receipt')
            or not review.fresh(policy.get('checkedAt'), now, 1440)
            or any(not isinstance(policy.get(k), str) or len(policy[k].strip()) < 20
                   for k in ('participation', 'pushVoid', 'earlyExit', 'reprice'))):
        return None, 'Reviewed Indiana book-specific participation, push/void, early-exit and SGP repricing rules required'
    league = review.FAMILIES[spec['family']][0]
    digest = checked['termsFingerprint']
    key = f"{league}-{gates.eastern_date(now)}-prop-ticket-{digest[:16]}"
    legs = [{**{k: leg.get(k) for k in PUBLIC_LEG_FIELDS},
             'id': f"{key}-leg-{i}",
             'title': f"{leg['player']} {leg['direction']} {leg['line']:g} {review.STATS[league][leg['market']]}"}
            for i, leg in enumerate(spec['legs'], 1)]
    first = min(gates.when(leg['kickoff']) for leg in legs)
    quoted = gates.when(spec['ticketQuote']['checkedAt'])
    pick = {'id': key, 'league': league, 'kind': 'parlays', 'family': spec['family'],
            'selectionMethod': METHOD, 'parlayType': 'longshot', 'parlayStyle': spec['parlayStyle'],
            'status': 'active', 'favorite': False, 'riskUnits': .25,
            'book': spec['book'], 'odds': spec['odds'], 'legs': legs,
            'gameIds': list(dict.fromkeys(leg['gameId'] for leg in legs)),
            'title': ('Daily Double' if spec['parlayStyle'] == 'daily-double'
                      else f"{len(legs)}-leg {spec['family']} parlay at {spec['book']}"),
            'quotedAt': gates.stamp(quoted), 'firstKickoff': gates.stamp(first),
            'expiresAt': gates.stamp(min(quoted + timedelta(hours=1), first-timedelta(minutes=30))),
            'quoteType': 'sportsbook', 'priceEstimated': False,
            'ticketReceipt': digest, 'propTicketFingerprint': digest,
            'confidence': 1, 'cutoff': 'Exact posted ticket; no substitutions or re-entry.',
            'edge': 'Sourced fun ticket; no calibrated probability or positive-EV claim.',
            'why': ' '.join(leg['review']['why'] for leg in spec['legs']),
            'risk': ' '.join(leg['review']['countercase'] for leg in spec['legs']),
            'sources': sorted({spec['ticketQuote']['source']} |
                              {fact['url'] for leg in spec['legs'] for fact in leg['review']['sources']}),
            'correlation': 'Observed same-book combined price; never multiplied leg prices or probabilities.'}
    return pick, None


def refusal(pick, ctx, now=None, *, packet=None, conf=None, phase='send'):
    """Every release checks the original identity and latest attended evidence."""
    if pick.get('selectionMethod') != METHOD:
        return None
    try:
        return _refusal(pick, ctx, now, packet=packet, conf=conf, phase=phase)
    except (AttributeError, KeyError, TypeError, ValueError):
        return 'Malformed private prop-ticket evidence; release held'


def _refusal(pick, ctx, now=None, *, packet=None, conf=None, phase='send'):
    now = now or ctx.now
    packet = packet if packet is not None else load(pick.get('id'), conf)
    original = packet.get('originalSpec') or {}
    frozen = packet.get('originalReview') or {}
    checks = packet.get('checks') or []
    if (not isinstance(original, dict) or not isinstance(frozen, dict)
            or not original or not isinstance(checks, list) or (phase == 'send' and not checks)):
        return 'Exact private prop-ticket review and send check required'
    if (review.terms(pick) != review.terms(original)
            or frozen.get('state') != 'reviewed-private'
            or frozen.get('termsFingerprint') != review.fingerprint(pick)
            or pick.get('propTicketFingerprint') != review.fingerprint(pick)):
        return 'Prop-ticket original terms changed; never substitute or reprice a published ticket'
    latest = checks[-1] if checks else original
    if not isinstance(latest, dict) or review.terms(latest) != review.terms(original):
        return 'Send-time combined quote differs from the exact original ticket'
    try:
        if phase == 'send' and gates.when(latest['ticketQuote']['checkedAt']) < gates.when(packet['admittedAt']):
            return 'An attended exact-ticket quote recheck after admission is required before sending'
    except (KeyError, TypeError, ValueError):
        return 'Valid admission and send-check clocks required'
    result = evaluate(dict(latest, id=pick['id']), ctx, now)
    if result['state'] != 'reviewed-private':
        return '; '.join(result['holds'])
    if len({row.get('parlayStyle') for row in (original, latest, pick)}) != 1:
        return 'Original reviewed ticket style must remain unchanged'
    if pick.get('family') != original.get('family') or pick.get('riskUnits') != .25:
        return 'Original prop-ticket family and 0.25u allocation must remain unchanged'
    if pick.get('family') == 'NBA-alts':
        held = review.nba_participation(latest, ctx.games, ctx.root, now)
        if held:
            return held
    _, held = candidate(dict(latest, id=pick['id']), ctx, now)
    if held:
        return held
    return gates.staking.check(pick, ctx)


def recheck(key, spec, ctx, now, conf=None):
    packet = load(key, conf)
    if not packet or review.terms(spec) != review.terms(packet.get('originalSpec') or {}):
        raise ValueError('Recheck must retain every original term and combined price')
    result = evaluate(dict(spec, id=key), ctx, now)
    if result['state'] != 'reviewed-private':
        raise ValueError('; '.join(result['holds']))
    if spec.get('family') == 'NBA-alts':
        held = review.nba_participation(spec, ctx.games, ctx.root, now)
        if held:
            raise ValueError(held)
    admitted = gates.when(packet['admittedAt'])
    if gates.when(spec['ticketQuote']['checkedAt']) < admitted:
        raise ValueError('Recheck cannot predate admission')
    packet.setdefault('checks', []).append(copy.deepcopy(spec))
    save(key, packet, conf)
    return result


def enqueue(spec, ctx, now, conf=None):
    import release_queue
    import run
    import x_post
    conf = Path(conf or CONF)
    pick, held = candidate(spec, ctx, now)
    if held:
        return None, held
    key = pick['id']
    if (key in ctx.first or key in getattr(ctx, 'risk_external', {})
            or any(row.get('id') == key for row in release_queue.load(conf)['plays'])):
        return None, 'This exact prop ticket is already reserved or published'
    if pick['league'] == 'NBA':
        held = review.nba_participation(spec, ctx.games, ctx.root, now)
        if held:
            return None, held
    packet = {'originalSpec': copy.deepcopy(spec), 'originalReview': evaluate(spec, ctx, now),
              'admittedAt': gates.stamp(now), 'checks': [], 'settlementEvidence': None}
    # Initial admission uses the reviewed quote; public release requires an
    # independently recorded post-admission recheck. No receipt path is public.
    save(key, packet, conf)
    ok, decisions = gates.admit(pick, ctx, 'longshot')
    if not ok:
        return None, '; '.join(d.reason for d in decisions if not d.ok)
    folder = Path(conf) / 'x-drafts'
    folder.mkdir(parents=True, exist_ok=True)
    first = dict(ctx.first, **{key: dict(pick, publishedAt=gates.stamp(now))})
    x_post.do_draft(key, now, first, ctx.latest, ctx.games, out=folder)
    target = folder / f'{key}.png'
    try:
        run.render_private_play_card(key, dict(pick, publishedAt=gates.stamp(now)),
                                    ctx.games[pick['gameIds'][0]], ctx.games, ctx, now, target)
    except (OSError, RuntimeError, run.ReleaseArtifactError):
        pass  # Existing artifact recovery owns this reserved row.
    added = release_queue.enqueue(conf, [(pick['league'], 'parlays', pick)], {}, [], folder, now, games=ctx.games)
    return (pick, None) if added else (None, 'No duplicate admission')


def settlement_revision(original, now, *, packet=None, conf=None):
    """A typed book/official review is mandatory; never use independent SGP math."""
    try:
        return _settlement_revision(original, now, packet=packet, conf=conf)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None, 'Malformed private prop-ticket settlement evidence; result held'


def _settlement_revision(original, now, *, packet=None, conf=None):
    packet = packet if packet is not None else load(original.get('id'), conf)
    spec = packet.get('originalSpec') or {}
    if not isinstance(spec, dict) or spec.get('family') not in review.FAMILIES:
        return None, 'Supported original prop-ticket packet required'
    league = review.FAMILIES[spec['family']][0]
    if original.get('league') != league or original.get('family') != spec['family']:
        return None, 'Original prop-ticket league and family must match the reviewed packet'
    if review.terms(original) != review.terms(spec):
        return None, 'Original prop-ticket terms do not match private settlement evidence'
    evidence = packet.get('settlementEvidence')
    if not evidence:
        return None, 'Attended book settlement, official actuals and participation/injury review required'
    result = settlement.review(spec, dict(evidence, originalReview=packet.get('originalReview')), now)
    if result['state'] != 'settled-private':
        return None, '; '.join(result['holds'])
    rows = evidence['legs']
    details = []
    for leg, row in zip(spec['legs'], rows):
        stat = review.STATS[league][leg['market']]
        if row['result'] == 'void':
            details.append(f"{leg['player']}: {stat} void")
        else:
            details.append(f"{leg['player']}: {row['actual']} {stat} ({row['result']})")
    actual = '; '.join(details)
    rules_based = result['settlementBasis'] == 'official-stats-and-rules'
    receipt = evidence['statSettlement' if rules_based else 'bookSettlement']
    revision = dict(original, status='settled', result=result['result'], actual=actual,
                    settledAt=gates.stamp(now), resultSource=rows[0]['source'],
                    units=round(result['units'], 3), settledOdds=result.get('settledOdds'),
                    settlementLegResults=[row['result'] for row in rows],
                    settlementLegActuals=[row.get('actual') for row in rows],
                    settlementBasis=result['settlementBasis'],
                    settlementReason=('Official final stats, clear participation/injury checks and original reviewed book rules.'
                                      if rules_based else 'Exact original ticket and official leg actuals reconciled with the listed book.'),
                    settlementReviewSources=sorted({row['source'] for row in rows} |
                        {receipt['rulesSource']}))
    if result.get('injuryNotes'):
        revision['settlementReason'] = ('Official final stats after the 12-hour injury review; '
            'no different book decision known. ' + ' '.join(result['injuryNotes']))
        revision['settlementReviewSources'] = sorted(set(revision['settlementReviewSources']) |
                                                    set(result['injurySources']))
        revision['injuryPlayers'] = result['injuryPlayers']
    return revision, None


def main():
    import argparse
    import release_queue
    import run
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec')
    parser.add_argument('--queue', action='store_true')
    parser.add_argument('--recheck', help='Existing ticket ID; append a fresh exact-terms check')
    parser.add_argument('--settlement', help='Private settlement evidence JSON; requires --id')
    parser.add_argument('--id')
    args = parser.parse_args()
    if args.settlement and not args.id:
        parser.error('--settlement requires --id')
    if not args.settlement and not args.spec:
        parser.error('--spec is required for a preview, admission or recheck')
    with run.Lock(run.CONF/'run.lock', wait=run.RUN_LOCK_WAIT):
        now = datetime.now(timezone.utc)
        ctx = gates.Stores().as_of(now)
        release_queue.merge_context(ctx, run.CONF)
        if args.spec:
            spec = json.loads(Path(args.spec).read_text())
            if spec.get('family') == 'NBA-alts':
                ctx.games.update(review.nba_fixtures(ctx.root))
        if args.settlement:
            packet = load(args.id, run.CONF)
            if not packet:
                raise ValueError('Original private packet missing')
            packet['settlementEvidence'] = json.loads(Path(args.settlement).read_text())
            original = ctx.first.get(args.id) or ctx.risk_external.get(args.id)
            if not original or original.get('_pendingRelease'):
                raise ValueError('Only a published original may receive settlement evidence')
            revised, held = settlement_revision(original, now, packet=packet)
            if held:
                raise ValueError(held)
            packet.setdefault('settlementHistory', []).append(copy.deepcopy(packet['settlementEvidence']))
            if original.get('family') == 'NBA-alts':
                import nba_fun_record
                import x_post
                posts = x_post.load_log()['posts']
                if not nba_fun_record.delivery(original, posts, now):
                    raise ValueError('NBA ticket settlement requires a delivered original')
                save(args.id, packet, run.CONF)
                added = nba_fun_record.settle(run.ROOT, args.id, posts, packet, now)
                run.commit_log(now)
                print(json.dumps({'state':'settlement-appended' if added else 'already-settled','id':args.id}))
                return
            save(args.id, packet, run.CONF)
            print(json.dumps({'state':'reviewed-settlement-awaiting-normal-worker','id':args.id}))
        elif args.recheck:
            recheck(args.recheck, spec, ctx, now, run.CONF)
            print(json.dumps({'state':'rechecked-private','id':args.recheck}))
        else:
            pick, held = enqueue(spec,ctx,now,run.CONF) if args.queue else candidate(spec,ctx,now)
            print(json.dumps({'state':'held' if held else 'admitted-private' if args.queue else 'reviewed-preview',
                              'id':pick.get('id') if pick else None,'reason':held}))


if __name__ == '__main__':
    main()
