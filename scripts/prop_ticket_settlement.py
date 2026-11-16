"""Private SGP settlement review. No network, publication or ledger writes.

Require exact original terms and a sportsbook settlement receipt. Reduced-leg
SGP prices come from the book, never independent-odds arithmetic. This module
cannot establish receipt authenticity or replace the future admission adapter.
"""
import gates
import prop_ticket_review as tickets
from fun_ticket_review import https

VERSION = 'prop-ticket-settlement-review-v1'
TERMINAL = {'win', 'loss', 'push', 'void'}


def identity(leg):
    return {key: leg.get(key) for key in
            ('gameId', 'athleteId', 'market', 'direction', 'line', 'period', 'book')}


def clock(value, now):
    try:
        return gates.when(value) <= now
    except (TypeError, ValueError):
        return False


def review(spec, evidence, now):
    """Return a private settlement proposal, or explicit holds, without side effects."""
    invalid = {'version': VERSION, 'state': 'held', 'releaseReady': False,
               'holds': ['Valid original 0.25u ticket and exact combined price required']}
    if not isinstance(spec, dict) or not isinstance(evidence, dict):
        return invalid
    holds = []
    legs = spec.get('legs') or []
    receipt = evidence.get('bookSettlement') or {}
    frozen = evidence.get('originalReview') or {}
    if (not isinstance(legs, list) or not 1 <= len(legs) <= 8
            or any(not isinstance(leg, dict) for leg in legs)
            or spec.get('family') not in tickets.FAMILIES
            or spec.get('book') not in ('DraftKings', 'FanDuel')
            or not tickets.price(spec.get('odds')) or spec.get('riskUnits', .25) != .25
            or spec.get('priceEstimated') is not False):
        return invalid
    fingerprint = tickets.fingerprint(spec)
    if not isinstance(receipt, dict) or not isinstance(frozen, dict):
        return invalid
    quote = spec.get('ticketQuote') or {}
    if not isinstance(quote, dict):
        return invalid
    if (quote.get('verified') is not True or not quote.get('receipt')
            or quote.get('terms') != tickets.terms(spec)
            or not https(quote.get('source'), spec['book'])
            or not clock(quote.get('checkedAt'), now)):
        holds.append('Original combined book quote and exact terms required')
    if (frozen.get('state') != 'reviewed-private' or frozen.get('termsFingerprint') != fingerprint
            or not clock(frozen.get('checkedAt'), now)):
        holds.append('Original frozen private review must match these exact terms')
    if (receipt.get('verified') is not True or not receipt.get('receipt')
            or receipt.get('termsFingerprint') != fingerprint
            or receipt.get('book') != spec['book'] or not https(receipt.get('source'), spec['book'])
            or not clock(receipt.get('checkedAt'), now)
            or not str(receipt.get('jurisdiction') or '').strip()
            or not str(receipt.get('ruleVersion') or '').strip()
            or not https(receipt.get('rulesSource'))):
        holds.append('Verified exact-ticket book settlement, jurisdiction and rules required')
    rows = evidence.get('legs') or []
    if not isinstance(rows, list) or len(rows) != len(legs) or any(not isinstance(r, dict) for r in rows):
        rows = []
        holds.append('One terminal evidence row per original leg required')
    results, removed, seen = [], [], set()
    for index, leg in enumerate(legs):
        key = str(identity(leg))
        if key in seen:
            holds.append('Duplicate original leg identity')
        seen.add(key)
        if (leg.get('book') != spec['book'] or leg.get('period') != 'full_game'
                or leg.get('market') not in tickets.STATS.get('NBA' if spec.get('family') == 'NBA-alts' else 'NFL', {})
                or leg.get('direction') not in ('over', 'under') or not tickets.numeric(leg.get('line'))):
            holds.append(f'Leg {index + 1}: unsupported original market or period')
            continue
        try:
            if (gates.when(quote.get('checkedAt')) > gates.when(frozen.get('checkedAt'))
                    or gates.when(quote.get('checkedAt')) >= gates.when(leg.get('kickoff'))
                    or gates.when(frozen.get('checkedAt')) >= gates.when(leg.get('kickoff'))
                    or gates.when(leg.get('kickoff')) >= now):
                holds.append(f'Leg {index + 1}: original review must precede kickoff and settlement follow it')
        except (TypeError, ValueError):
            holds.append(f'Leg {index + 1}: valid original kickoff and review clocks required')
        row = rows[index] if index < len(rows) else {}
        result = row.get('result')
        if (row.get('terms') != identity(leg) or result not in TERMINAL
                or row.get('final') is not True or not https(row.get('source'))
                or not clock(row.get('checkedAt'), now)):
            holds.append(f'Leg {index + 1}: exact terminal identity and source required')
            continue
        try:
            if (gates.when(row.get('checkedAt')) < gates.when(leg.get('kickoff'))
                    or gates.when(receipt.get('checkedAt')) < gates.when(leg.get('kickoff'))):
                holds.append(f'Leg {index + 1}: terminal evidence cannot predate kickoff')
        except (TypeError, ValueError):
            holds.append(f'Leg {index + 1}: settlement evidence clocks required')
        results.append(result)
        if result in ('void', 'push'):
            removed.append(index)
        participation = row.get('participation')
        if participation not in ('played', 'did-not-play'):
            holds.append(f'Leg {index + 1}: participation unresolved')
        if row.get('injuryReview') not in ('clear', 'book-resolved'):
            holds.append(f'Leg {index + 1}: injury/early-exit review unresolved')
        if result == 'void':
            if not row.get('bookDecisionReceipt') or not str(row.get('voidReason') or '').strip():
                holds.append(f'Leg {index + 1}: book-confirmed void reason required')
        elif (participation != 'played' or not tickets.numeric(row.get('actual'))
              or not float(row['actual']).is_integer()
              or leg['market'] not in ('rushYds', 'recYds', 'passYds') and row['actual'] < 0):
            holds.append(f'Leg {index + 1}: played status and official actual required')
        else:
            actual, line = row['actual'], leg['line']
            expected = 'push' if actual == line else (
                'win' if (actual > line) == (leg['direction'] == 'over') else 'loss')
            if result != expected:
                holds.append(f'Leg {index + 1}: result contradicts exact original threshold')
        if row.get('injuryReview') == 'book-resolved' and not row.get('bookDecisionReceipt'):
            holds.append(f'Leg {index + 1}: injury protection needs its actual book decision')
    result, odds = None, None
    if len(results) == len(legs):
        if 'loss' in results:
            result = 'loss'
        elif all(r in ('push', 'void') for r in results):
            result = 'void'
        elif all(r == 'win' for r in results):
            result, odds = 'win', spec['odds']
        else:
            result = 'win'
            reduced = evidence.get('reducedQuote') or {}
            if not isinstance(reduced, dict):
                reduced = {}
            remaining = [identity(leg) for i, leg in enumerate(legs) if i not in removed]
            if (reduced.get('verified') is not True or not reduced.get('receipt')
                    or reduced.get('originalTermsFingerprint') != fingerprint
                    or reduced.get('book') != spec['book'] or reduced.get('remainingLegs') != remaining
                    or not https(reduced.get('source'), spec['book'])
                    or not clock(reduced.get('checkedAt'), now) or not tickets.price(reduced.get('odds'))
                    or reduced.get('priceEstimated') is not False):
                holds.append('Reduced SGP requires the actual book-repriced remaining ticket')
            else:
                odds = reduced['odds']
        if receipt.get('result') != result:
            holds.append('Book result does not match the sourced leg outcomes')
        if result == 'win' and receipt.get('settledOdds') != odds:
            holds.append('Book settled price must match the original or verified reduced combined quote')
    answer = {'version': VERSION, 'state': 'held' if holds else 'settled-private',
              'releaseReady': False, 'holds': list(dict.fromkeys(holds)),
              'termsFingerprint': fingerprint, 'riskUnits': .25,
              'recordWriteAllowed': False, 'providerRequests': 0}
    if not holds:
        answer.update(result=result, settledOdds=odds,
                      units=round(-.25 if result == 'loss' else 0 if result == 'void'
                                  else .25 * (odds / 100 if odds > 0 else 100 / -odds), 6))
    return answer
