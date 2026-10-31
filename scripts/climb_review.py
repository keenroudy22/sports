"""Sourced discretionary Climb admission, separate from probability validation.

An operator review is evidence of a decision, not proof of positive EV. This
route accepts exact, visibly verified cross-game sportsbook tickets and keeps
the ordinary one-open-step, exposure, jurisdiction and delivery checks.
"""
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import gates
import parlay
import pricing

METHOD = 'sourced-climb-review-v1'
EFFECTIVE = datetime(2026, 10, 31, 12, 10, tzinfo=timezone.utc)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def https(value, book=None):
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or not host or parsed.username or parsed.password:
            return False
        domain = {'DraftKings': 'draftkings.com', 'FanDuel': 'fanduel.com'}.get(book)
        return not book or bool(domain and (host == domain or host.endswith('.' + domain)))
    except (TypeError, ValueError):
        return False


def refusal(ticket, ctx):
    """Recheck the immutable review at admission and every private release."""
    now = ctx.now
    if now < EFFECTIVE:
        return 'Sourced Climb review is not effective at this historical clock'
    review = ticket.get('researchReview')
    if not isinstance(review, dict) or review.get('method') != METHOD or review.get('reviewer') != 'kookn-desk':
        return 'Climb needs its explicit sourced desk review'
    try:
        at = gates.when(review.get('reviewedAt'))
        quote = gates.when(ticket.get('quotedAt'))
    except (TypeError, ValueError):
        return 'Climb review and quote clocks are required'
    if not timedelta(0) <= now-at <= timedelta(hours=2) or not quote <= at <= now or now-quote > timedelta(hours=2):
        return 'Climb review or exact ticket quote needs refresh'
    if review.get('ticketVerified') is not True or not https(review.get('ticketSource'), ticket.get('book')):
        return 'Climb needs a visibly verified combined sportsbook ticket'
    if not isinstance(review.get('receipt'), str) or not review['receipt'].strip():
        return 'Climb needs its saved ticket verification receipt'
    if any(ticket.get(key) is not None for key in ('chance', 'rawChance', 'fairOdds', 'expectedValue')):
        return 'Discretionary Climb cannot claim a validated probability or EV'
    legs = ticket.get('legs') or []
    if len(legs) not in (2, 3):
        return 'Reviewed Climb needs two or three legs'
    product = 1.0
    ids = set()
    for leg in legs:
        game = ctx.games.get(leg.get('gameId')) or {}
        if not game or game.get('league') not in ('NFL', 'CFB') or game.get('state') != 'pre':
            return 'Reviewed Climb needs an eligible upcoming football game'
        try:
            kickoff = gates.when(game.get('kickoff'))
        except (TypeError, ValueError):
            return 'Climb game kickoff is missing'
        if kickoff <= now+timedelta(minutes=15) or gates.eastern_date(kickoff) != gates.eastern_date(now):
            return 'Climb needs current-day games with a real pregame release window'
        if leg['gameId'] in ids:
            return 'Reviewed Climb uses one leg per game'
        ids.add(leg['gameId'])
        price, line = leg.get('odds'), leg.get('line')
        if not number(price) or not -900 <= price <= -180 or int(price) != price:
            return 'Climb leg needs an exact supported American price'
        if leg.get('book') != ticket.get('book') or leg.get('alternate') is not True:
            return 'Climb legs must be real alternates at the same book'
        market = leg.get('marketType')
        side = leg.get('direction')
        if market not in ('spread', 'total') or side not in (('home', 'away') if market == 'spread' else ('over', 'under')):
            return 'Reviewed Climb currently supports full-game spreads and totals'
        if not number(line) or not float(line*2).is_integer() or int(line*2) % 2 == 0:
            return 'Reviewed game alternates need half-point lines'
        main = leg.get('mainLine')
        if not number(main) or not (line < main if market == 'total' and side == 'over' else line > main):
            return 'Reviewed Climb needs a genuinely cushioned alternate versus the observed main line'
        if leg.get('marketWindow') != 'Full game' or not https(leg.get('source'), ticket.get('book')):
            return 'Climb leg needs its exact full-game sportsbook source'
        try:
            observed = gates.when(leg.get('observedAt'))
        except (TypeError, ValueError):
            return 'Climb leg quote clock is missing'
        if not quote <= observed <= at:
            return 'Climb leg quote does not match its ticket verification window'
        case = leg.get('researchCase') or {}
        if any(not isinstance(case.get(key), str) or not case[key].strip() for key in ('why', 'risk', 'availability')):
            return 'Each Climb leg needs reasoning, countercase and current availability review'
        evidence = case.get('sources')
        if not isinstance(evidence, list) or not evidence:
            return 'Each Climb leg needs sourced matchup evidence'
        for fact in evidence:
            if not isinstance(fact, dict) or not https(fact.get('url')) or not fact.get('fact'):
                return 'Climb matchup evidence needs an HTTPS source and factual summary'
            try:
                checked = gates.when(fact.get('checkedAt'))
            except (TypeError, ValueError):
                return 'Climb evidence check clock is missing'
            if not at-timedelta(hours=24) <= checked <= at:
                return 'Climb evidence must be checked before the decision and within one day'
        product *= parlay.decimal(price)
    if ids != set(ticket.get('gameIds') or []):
        return 'Reviewed Climb games do not match its legs'
    odds = ticket.get('odds')
    # The visibly quoted ticket is authoritative. Books may round/reprice a
    # cross-game combo slightly; reject material mismatches, not that rounding.
    if not number(odds) or not -200 <= odds <= -150 or abs(parlay.decimal(odds)-product) > .03:
        return 'Exact combined Climb price must match its same-book legs and target band'
    return None


def candidate(ctx, games, now, spec):
    import ladder
    where = ladder.state(ctx.first, ctx.latest)
    if where['open']:
        return None, 'An existing Climb is still open'
    held = ladder.weekly_refusal(ctx, now)
    if held:
        return None, held
    ticket = dict(spec, selectionMethod=METHOD)
    ticket['gameIds'] = [leg.get('gameId') for leg in ticket.get('legs', [])]
    held = refusal(ticket, ctx)
    if held:
        return None, held
    ticket.update(firstKickoff=min(games[g]['kickoff'] for g in ticket['gameIds']),
                  decimal=parlay.decimal(ticket['odds']), quoteType='sportsbook', priceEstimated=False,
                  sources=sorted({ticket['researchReview']['ticketSource']} |
                      {fact['url'] for leg in ticket['legs'] for fact in leg['researchCase']['sources']}))
    pick = ladder.ticket_pick(ticket, games[ticket['gameIds'][0]]['league'], where, now, games)
    pick.update(selectionMethod=METHOD, researchReview=ticket['researchReview'],
                expiresAt=gates.stamp(min(gates.when(ticket['quotedAt'])+timedelta(hours=2),
                                          gates.when(ticket['firstKickoff'])-timedelta(minutes=15))),
                edge='Desk-researched alternate ticket. No validated win probability or positive-EV claim.',
                why=[leg['researchCase']['why'] for leg in ticket['legs']],
                risks=[leg['researchCase']['risk'] for leg in ticket['legs']])
    return pick, None
