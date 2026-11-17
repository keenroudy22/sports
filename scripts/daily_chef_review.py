"""Private all-sports favorite review; never admits, relabels or sends a play.

The football selector and basketball ledgers have different evidence contracts.
Collect their current admissions without translating sourced judgment into a
probability. A desk comparison must cover every reviewable admission and the
current slate. Publication designation is a separate, still-required step.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gates
import staking

VERSION = 'daily-chef-review-v1'
SPORTS = ('NFL', 'CFB', 'NBA', 'CBB')
AGE = timedelta(minutes=30)


def instant(value):
    try:
        result = gates.when(value)
        return result if result.tzinfo else None
    except (TypeError, ValueError, AttributeError):
        return None


def terms(play):
    """Exact stored identity, not a price reconstructed from a rounded title."""
    return {key: play.get(key) for key in (
        'id', 'league', 'athleteId', 'marketType', 'stat', 'period', 'direction',
        'line', 'odds', 'oppositeOdds', 'book', 'riskUnits')} | {
        'gameIds': play.get('gameIds') or [play.get('eventId')],
        'quoteAt': play.get('quotedAt') or (play.get('quote') or {}).get('checkedAt')
                   or play.get('retrievedAt'),
    }


def delivery_state(key, posts):
    import receipts
    attempts = [row for row in posts if row.get('id') == key]
    if any(row.get('sentAt') or receipts.confirmed_discord(row.get('discord') or {}) for row in attempts):
        return 'public; original designation frozen'
    # Even an intended or failed send is not safe to silently replace. Recovery
    # owns cancellation and reconciliation; this review cannot infer it away.
    if attempts:
        return 'delivery attempt exists; reconcile before designation'
    return None


def current_refusal(play, ctx, now, pending=None):
    """Reuse each sport's stored-input checks; none of these paths captures odds."""
    if play['league'] == 'CBB':
        import cbb_picks
        return cbb_picks.refusal(play, now)
    if play['league'] == 'NBA':
        import nba_trial_runtime
        return None if nba_trial_runtime.current_match(play, now) else 'NBA current price, role or participation check held'
    import run
    return run.private_release_refusal(pending or {'pick': play, 'league': play['league']}, ctx, now)


def snapshot(ctx, now, *, posts, pending=(), nba=None, cbb=None, check=current_refusal):
    """All current-day admissions plus honest coverage gaps, from stored inputs.

    This is not all lines on the market. Unreviewed markets remain work for the
    ordinary research pass; already delivered picks remain visible references.
    Dependency injection keeps replay tests isolated from provider/private state.
    """
    if nba is None:
        import nba_trial_runtime
        nba = nba_trial_runtime.public_rows(Path(ctx.root) / 'data/nba-trial')
    if cbb is None:
        import cbb_picks
        cbb = cbb_picks.public_rows(Path(ctx.root) / 'data/cbb-picks')
    day = now.astimezone(gates.EASTERN).date()
    games = {**getattr(ctx, 'risk_games', {}), **ctx.games}
    private = {row.get('id'): row for row in pending}
    originals = {key: {**pick, **ctx.latest.get(key, {})} for key, pick in ctx.first.items()}
    for key, row in private.items():
        if key and key not in originals:
            originals[key] = dict(row.get('pick') or {}, league=row.get('league'))
    for play in [*nba, *cbb]:
        if play.get('id') in originals:
            raise ValueError('Duplicate admission identity across sport stores')
        originals[play['id']] = play
    coverage = {sport: {'games': 0, 'admissions': 0, 'reviewable': 0, 'public': 0, 'held': 0}
                for sport in SPORTS}
    slate = []
    for game_id, game in sorted(games.items()):
        start = instant(game.get('kickoff'))
        if game.get('league') in coverage and start and start.astimezone(gates.EASTERN).date() == day:
            coverage[game['league']]['games'] += 1
            teams = game.get('teams') or game
            slate.append({'id': game_id, 'league': game['league'],
                          'kickoff': gates.stamp(start), 'status': game.get('status'),
                          'teams': {side: str((teams.get(side) or {}).get('id') or '')
                                    for side in ('home', 'away')}})
    rows = []
    for key, play in sorted(originals.items()):
        league = play.get('league') or key.split('-')[0]
        if league not in coverage or play.get('legs') or play.get('parlayType'):
            continue
        play = dict(play, league=league)
        game = games.get((play.get('gameIds') or [play.get('eventId')])[0], {})
        start = instant(play.get('kickoff') or game.get('kickoff') or (play.get('game') or {}).get('kickoff'))
        if not start or start.astimezone(gates.EASTERN).date() != day:
            continue
        coverage[league]['admissions'] += 1
        delivery = delivery_state(key, posts)
        state = 'public' if delivery and delivery.startswith('public;') else 'held'
        reason = delivery
        private_row = private.get(key)
        if private_row and (private_row.get('discordSentAt') or private_row.get('publicPath')):
            state, reason = 'public', 'private queue confirms publication; original designation frozen'
        if not reason:
            if play.get('result') or play.get('entryNote') or play.get('status', 'active') != 'active':
                reason = 'Settled or closed original'
            elif start <= now + timedelta(minutes=15):
                reason = 'Pregame designation window ended'
            elif private_row and (private_row.get('held') or private_row.get('releasedAt')):
                reason = 'Private release is held or already released'
            else:
                reason = check(play, ctx, now, private_row)
                if not reason:
                    state = 'reviewable'
        coverage[league][state] += 1
        source = play.get('sourceReview') or play.get('review') or {}
        dossier = play.get('dossier') or {}
        rows.append({
            'terms': terms(play), 'kickoff': gates.stamp(start), 'state': state,
            'hold': reason, 'title': play.get('title') or play.get('player') or key,
            'selectionMethod': play.get('selectionMethod') or play.get('selectionPolicy') or 'model',
            'evidenceKind': 'sourced judgment' if str(play.get('selectionMethod', '')).startswith('sourced-') else 'model',
            'why': source.get('why') or (private_row or {}).get('reason') or play.get('reason') or play.get('why')
                   or next((r.get('text') for r in dossier.get('reasons', []) if r.get('text')), None),
            'countercase': source.get('countercase') or play.get('risk'),
            'sources': source.get('sources') or play.get('sources') or [],
        })
    for block in coverage.values():
        block['coverage'] = ('no stored games today' if not block['games'] else
                             'admissions only; unreviewed markets remain' if block['admissions'] else
                             'no current-day straight admission; research still required')
    result = {'version': VERSION, 'day': day.isoformat(), 'asOf': gates.stamp(now),
              'scope': 'stored admissions across supported sports; not an exhaustive market scan',
              'coverage': coverage, 'slate': slate, 'rows': rows,
              'dailyCapUnits': staking.limit(day, games, now),
              'publicationAuthority': False}
    # Bind the comparison to actual terms, source facts, holds and coverage.
    # The observation clock alone need not invalidate an unchanged comparison.
    result['fingerprint'] = hashlib.sha256(json.dumps(
        {k: v for k, v in result.items() if k != 'asOf'}, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return result


def validate_review(packet, current, now):
    """Accept an explicit comparative judgment, never synthesize a winner."""
    if not isinstance(packet, dict):
        raise ValueError('An explicit desk review is required')
    reviewed = instant(packet.get('reviewedAt'))
    observed = instant(current.get('asOf'))
    if not reviewed or not observed or not timedelta(0) <= now-reviewed <= AGE or not timedelta(0) <= now-observed <= AGE:
        raise ValueError('Current comparative review required')
    if packet.get('version') != VERSION or packet.get('reviewer') != 'kookn-desk' or packet.get('approved') is not True:
        raise ValueError('Explicit comparative desk approval required')
    if packet.get('fingerprint') != current.get('fingerprint') or packet.get('day') != current.get('day'):
        raise ValueError('Slate, terms, source facts or holds changed; repeat comparison')
    if not isinstance(packet.get('coverage'), dict) or set(packet['coverage']) != set(SPORTS):
        raise ValueError('Review must account for all four supported sports')
    if any(not isinstance(note, str) or len(note.strip()) < 20 for note in packet['coverage'].values()):
        raise ValueError('Specific coverage notes required, including unsupported or held markets')
    eligible = {row['terms']['id'] for row in current['rows'] if row['state'] == 'reviewable'}
    ranking = packet.get('ranking')
    if not isinstance(ranking, list) or any(not isinstance(key, str) for key in ranking) or len(set(ranking)) != len(ranking) or set(ranking) != eligible:
        raise ValueError('Compare every reviewable admission exactly once')
    selected = packet.get('selectedId')
    if selected is not None and (not ranking or selected != ranking[0]):
        raise ValueError('Favorite must lead the reviewed ranking')
    for field in ('why', 'countercase'):
        if not isinstance(packet.get(field), str) or len(packet[field].strip()) < 20:
            raise ValueError('Comparative reason and strongest countercase required')
    if selected is None and (not isinstance(packet.get('hold'), str) or len(packet['hold'].strip()) < 20):
        raise ValueError('A held favorite needs its exact remaining blocker')
    # No implied calibrated probability/EV for a sourced decision.
    if any(key in packet for key in ('chance', 'fairOdds', 'expectedValue', 'edge')):
        raise ValueError('Comparative review cannot manufacture a common probability score')
    return {'state': 'reviewed' if selected else 'held', 'selectedId': selected,
            'why': packet['why'], 'countercase': packet['countercase'],
            'hold': packet.get('hold') if not selected else None,
            'designation': 'pending; this review grants no publication or relabeling authority'}


def save_snapshot(report, conf):
    return save_private(report, Path(conf) / 'pending/daily-chef-review.json')


def save_private(value, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    temp.replace(target)
    return target


def comparison(current, now, conf):
    """A previous review is reusable only while its exact evidence still matches."""
    target = Path(conf) / 'pending/daily-chef-comparison.json'
    if not target.exists():
        return {'state': 'comparison-required', 'selectedId': None,
                'hold': 'Explicit all-sports comparison and publication designation remain required'}
    try:
        if target.stat().st_size > 64 * 1024:
            raise ValueError('Comparative packet exceeds its bounded size')
        return validate_review(json.loads(target.read_text()), current, now)
    except (OSError, ValueError, TypeError, KeyError) as error:
        return {'state': 'held', 'selectedId': None, 'hold': str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--review', type=Path, help='Validate a private comparative review; never publishes')
    args = parser.parse_args()
    import run, release_queue, x_post
    with run.Lock(run.CONF/'run.lock', wait=run.RUN_LOCK_WAIT):
        now = datetime.now(timezone.utc)
        ctx = gates.Stores().as_of(now)
        report = snapshot(ctx, now, posts=x_post.load_log()['posts'], pending=release_queue.load(run.CONF)['plays'])
        if args.review:
            packet = json.loads(args.review.read_text())
            validate_review(packet, report, now)
            save_private(packet, run.CONF/'pending/daily-chef-comparison.json')
        report['comparison'] = comparison(report, now, run.CONF)
        path = save_snapshot(report, run.CONF)
        print(json.dumps({'path': str(path), 'coverage': report['coverage'],
                          'comparison': report.get('comparison'), 'publicationAuthority': False}))


if __name__ == '__main__':
    main()
