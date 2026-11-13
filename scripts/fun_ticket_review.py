"""Exact reviewed short-parlay and lotto admission; never wager placement.

Planning drafts are not public tickets. This route accepts a fresh, visibly
verified same-book combined price plus sourced reasoning for every football
alternate, then hands the ticket to the ordinary private release queue.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import gates
import ladder
import parlay
import pricing

METHOD = 'sourced-fun-ticket-review-v1'
EFFECTIVE = datetime(2026, 11, 13, 16, 0, tzinfo=timezone.utc)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def https(value, book=None):
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ''
        domain = {'DraftKings': 'draftkings.com', 'FanDuel': 'fanduel.com'}.get(book)
        return parsed.scheme == 'https' and bool(host) and not parsed.username and not parsed.password \
            and (not book or bool(domain and (host == domain or host.endswith('.' + domain))))
    except (TypeError, ValueError):
        return False


def refusal(ticket, ctx):
    now = ctx.now
    if now < EFFECTIVE:
        return 'Reviewed fun-ticket route is not effective at this historical clock'
    review = ticket.get('researchReview') or {}
    if review.get('method') != METHOD or review.get('reviewer') != 'kookn-desk':
        return 'Fun ticket needs its explicit sourced desk review'
    try:
        reviewed = gates.when(review.get('reviewedAt'))
        quoted = gates.when(ticket.get('quotedAt'))
    except (TypeError, ValueError):
        return 'Fun-ticket review and quote clocks are required'
    if not timedelta(0) <= now-reviewed <= timedelta(hours=1) or not quoted <= reviewed <= now \
            or now-quoted > timedelta(hours=1):
        return 'Fun-ticket review or exact combined price needs refresh'
    if review.get('ticketVerified') is not True or not https(review.get('ticketSource'), ticket.get('book')):
        return 'Fun ticket needs a visibly verified same-book combined ticket'
    if not isinstance(review.get('receipt'), str) or not review['receipt'].strip():
        return 'Fun ticket needs its private ticket verification receipt'
    if any(ticket.get(key) is not None for key in ('chance', 'rawChance', 'fairOdds', 'expectedValue')):
        return 'Fun ticket cannot claim a validated probability or EV'
    shape = gates.longshot_shape(ticket, ctx)
    if not shape.ok:
        return shape.reason
    legs = ticket.get('legs') or []
    ids = set()
    product = 1.0
    for leg in legs:
        if any(leg.get(key) is not None for key in ('chance', 'rawChance', 'fairOdds', 'expectedValue')):
            return 'Fun-ticket legs cannot claim a validated probability or EV'
        game = ctx.games.get(leg.get('gameId')) or {}
        if game.get('league') not in ('NFL', 'CFB') or game.get('state') != 'pre':
            return 'Reviewed fun tickets currently require upcoming NFL or CFB games'
        try:
            kickoff = gates.when(game.get('kickoff'))
        except (TypeError, ValueError):
            return 'Fun-ticket kickoff is missing'
        if kickoff <= now + timedelta(minutes=30) or gates.eastern_date(kickoff) != gates.eastern_date(now):
            return 'Fun-ticket legs need current-day games and a real release window'
        if leg.get('gameId') in ids:
            return 'Reviewed fun tickets use one leg per game'
        ids.add(leg['gameId'])
        if leg.get('book') != ticket.get('book') or leg.get('alternate') is not True:
            return 'Every fun-ticket leg must be a real alternate at the same book'
        price, line = leg.get('odds'), leg.get('line')
        if not number(price) or not -900 <= price <= 1000 or int(price) != price:
            return 'Every fun-ticket leg needs an exact American price'
        if leg.get('marketType') != 'spread' or leg.get('direction') not in ('home', 'away'):
            return 'Reviewed football fun tickets currently support alternate spreads'
        if not number(line) or not float(line * 2).is_integer() or int(line * 2) % 2 == 0:
            return 'Reviewed alternate spreads need half-point lines'
        team = game[leg['direction']]
        name = team.get('school') or team.get('short') or team.get('name')
        title = f'{name} {pricing.signed(float(line))}'
        if leg.get('title') != title or leg.get('kickoff') != game.get('kickoff'):
            return f'Fun-ticket display must match the exact game, side, line and kickoff: {title}'
        main = leg.get('mainLine')
        if not number(main) or line <= main:
            return 'Reviewed spread alternate must be cushioned versus the observed main line'
        if leg.get('marketWindow') != 'Full game' or not https(leg.get('source'), ticket.get('book')):
            return 'Fun-ticket leg needs its exact full-game sportsbook source'
        try:
            observed = gates.when(leg.get('observedAt'))
        except (TypeError, ValueError):
            return 'Fun-ticket leg quote clock is missing'
        if not quoted <= observed <= reviewed:
            return 'Fun-ticket leg quote does not match its ticket verification window'
        case = leg.get('researchCase') or {}
        if any(not isinstance(case.get(key), str) or not case[key].strip()
               for key in ('why', 'risk', 'availability')):
            return 'Every fun-ticket leg needs reasoning, countercase and availability review'
        facts = case.get('sources')
        if not isinstance(facts, list) or not facts:
            return 'Every fun-ticket leg needs sourced matchup evidence'
        for fact in facts:
            if not isinstance(fact, dict) or not https(fact.get('url')) or not fact.get('fact'):
                return 'Fun-ticket matchup evidence needs an HTTPS source and factual summary'
            try:
                checked = gates.when(fact.get('checkedAt'))
            except (TypeError, ValueError):
                return 'Fun-ticket evidence check clock is missing'
            if not reviewed - timedelta(hours=24) <= checked <= reviewed:
                return 'Fun-ticket evidence must be checked before review and within one day'
        product *= parlay.decimal(price)
    if ids != set(ticket.get('gameIds') or []):
        return 'Fun-ticket games do not match its legs'
    odds = ticket.get('odds')
    if not number(odds) or abs(parlay.decimal(odds) - product) > .08:
        return 'Exact combined fun-ticket price must match its same-book legs'
    return None


def candidate(ctx, now, spec):
    ticket = dict(spec, selectionMethod=METHOD, favorite=False, status='active',
                  parlayType='longshot', riskUnits=.25, quoteType='sportsbook', priceEstimated=False)
    ticket['gameIds'] = [leg.get('gameId') for leg in ticket.get('legs') or []]
    held = refusal(ticket, ctx)
    if held:
        return None, held
    style = ticket['parlayStyle']
    first = min(gates.when(ctx.games[gid]['kickoff']) for gid in ticket['gameIds'])
    ticket.update(id=f"{ctx.games[ticket['gameIds'][0]]['league']}-{gates.eastern_date(now)}-{style}-{ticket['book'].lower().replace(' ', '-')}",
                  title=f"{len(ticket['legs'])}-leg {'parlay' if style == 'short' else 'lotto'} at {ticket['book']}",
                  firstKickoff=gates.stamp(first), ticketReceipt=ticket['researchReview']['receipt'],
                  expiresAt=gates.stamp(min(first - timedelta(minutes=30),
                                            gates.when(ticket['quotedAt']) + timedelta(hours=1))),
                  sources=sorted({ticket['researchReview']['ticketSource']} |
                      {fact['url'] for leg in ticket['legs'] for fact in leg['researchCase']['sources']}),
                  edge='Desk-researched fun ticket. No validated win probability or positive-EV claim.',
                  why=[leg['researchCase']['why'] for leg in ticket['legs']],
                  risks=[leg['researchCase']['risk'] for leg in ticket['legs']],
                  correlation='One leg per game; the sportsbook combined price is preserved exactly.')
    return ticket, None


def enqueue(spec, ctx, now, conf):
    import dossier
    import release_queue
    import run
    import x_post
    pick, held = candidate(ctx, now, spec)
    if held:
        return None, held
    run.write_prose(pick, ctx, [])
    league = ctx.games[pick['gameIds'][0]]['league']
    ok, decisions = gates.admit(dict(pick, league=league), ctx)
    if not ok:
        return None, '; '.join(decision.reason for decision in decisions if not decision.ok)
    pick['jurisdictionVerified'] = any(decision.rule == 'cfb_jurisdiction' and
        (decision.data or {}).get('jurisdictionVerified') for decision in decisions)
    pick['dossier'] = dossier.ticket(pick, now)
    folder = Path(conf) / 'x-drafts'
    folder.mkdir(parents=True, exist_ok=True)
    first = dict(ctx.first)
    first[pick['id']] = dict(pick, league=league, publishedAt=gates.stamp(now), kind='parlays')
    x_post.do_draft(pick['id'], now, first, ctx.latest, ctx.games, out=folder)
    target = folder / f"{pick['id']}.png"
    target.unlink(missing_ok=True)
    try:
        run.render_private_play_card(pick['id'], dict(pick, publishedAt=gates.stamp(now)),
                                     ctx.games[pick['gameIds'][0]], ctx.games, ctx, now, target)
    except (OSError, RuntimeError, run.ReleaseArtifactError) as error:
        run.log(f'Reviewed fun-ticket card awaits normal artifact recovery ({type(error).__name__})')
    added = release_queue.enqueue(conf, [(league, 'parlays', pick)], {}, [], folder, now, games=ctx.games)
    if not added:
        return None, 'Reviewed fun ticket was already queued; no duplicate admission'
    return pick, None


def main():
    import argparse
    import run
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--spec', required=True, help='exact sourced sportsbook ticket JSON')
    parser.add_argument('--queue', action='store_true', help='reserve through ordinary private release; never wager')
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    if args.queue:
        with run.Lock(run.CONF / 'run.lock', wait=run.RUN_LOCK_WAIT):
            run.sync()
            now = datetime.now(timezone.utc)
            ctx = gates.Stores().as_of(now)
            pick, held = enqueue(spec, ctx, now, run.CONF)
    else:
        now = datetime.now(timezone.utc)
        ctx = gates.Stores().as_of(now)
        pick, held = candidate(ctx, now, spec)
    print(json.dumps({'state': 'held' if held else 'admitted-private' if args.queue else 'reviewed-preview',
                      'id': pick.get('id') if pick else None, 'reason': held}))
    return 1 if held else 0


if __name__ == '__main__':
    raise SystemExit(main())
