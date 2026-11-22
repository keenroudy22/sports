"""Attended result review for a pregame fun ticket with an explicit unit stake.

This records performance at the published allocation, never personal cash or a
claimed sportsbook payout. Legacy tickets without a published unit stake keep
their existing cash-evidence accounting. Removed/protected legs remain held.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import community_record as record
import gates
import prop_ticket_review as tickets
from prop_ticket_settlement import identity
from fun_ticket_review import https

BASIS = 'published-unit-stake-v1'


def review(ticket, evidence, posts, now):
    try:
        return _review(ticket, evidence, posts, now)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return None, 'Malformed unit settlement evidence; result held'


def _review(ticket, evidence, posts, now):
    legs = ticket.get('legs')
    league = ticket.get('league')
    stats = tickets.STATS.get('NFL' if league == 'CFB' else league, {})
    if (not stats or not isinstance(legs, list) or not 1 <= len(legs) <= 8
            or any(not isinstance(leg, dict) for leg in legs)
            or ticket.get('riskUnits') != .25 or isinstance(ticket.get('riskUnits'), bool)
            or ticket.get('book') not in ('DraftKings', 'FanDuel')
            or not tickets.price(ticket.get('odds')) or ticket.get('priceBoosted')
            or ticket.get('paidProtection')):
        return None, 'Structured original ticket with explicit 0.25u allocation and unboosted price required'
    kickoff = gates.when(ticket['kickoff'])
    original = evidence['original']
    if (original.get('ticket') != ticket or not original.get('quoteReceipt')
            or not https(original.get('quoteSource'), ticket['book'])
            or not gates.when(original['checkedAt']) < kickoff < now):
        return None, 'Frozen pregame ticket, unit allocation and exact book quote required'
    publications = [p for p in posts if p.get('id') == ticket['id']
                    and not p.get('cancelledAt') and not p.get('deletedAt')
                    and p.get('sentAt') and p.get('link')
                    and gates.when(original['checkedAt']) <= gates.when(p['sentAt']) < kickoff]
    if not publications:
        return None, 'Confirmed pregame original publication required; never add a ticket after its result'
    checked = gates.when(evidence['checkedAt'])
    if not kickoff < checked <= now:
        return None, 'Result review must follow kickoff and cannot be future-dated'
    rules = evidence['rules']
    if (rules.get('verified') is not True or rules.get('book') != ticket['book']
            or rules.get('jurisdiction') != 'IN' or not rules.get('receipt')
            or not rules.get('ruleVersion') or not https(rules.get('source'), ticket['book'])
            or not tickets.fresh(rules.get('checkedAt'), checked, 1440)
            or any(not isinstance(rules.get(k), str) or len(rules[k].strip()) < 20
                   for k in ('participation', 'period', 'earlyExit', 'pushVoid'))):
        return None, 'Reviewed Indiana book participation, period, early-exit and void rules required'
    if (evidence.get('differentBookDecisionKnown') is not False
            or evidence.get('cashout') or evidence.get('paidProtection')
            or evidence.get('reducedQuote') or evidence.get('bookAdjusted')):
        return None, 'Adjusted, protected or unresolved book decisions require separate settlement evidence'
    rows = evidence['legs']
    if not isinstance(rows, list) or len(rows) != len(legs):
        return None, 'One exact final evidence row per original leg required'
    results, actuals, seen = [], [], set()
    for leg, row in zip(legs, rows):
        key = json.dumps(identity(leg), sort_keys=True)
        if key in seen:
            return None, 'Duplicate original leg'
        seen.add(key)
        period = leg.get('period')
        team_market = league in ('NFL', 'CFB') and leg.get('market') in ('moneyline', 'total')
        if team_market:
            if (period != 'full_game' or leg.get('book') != ticket['book']
                    or leg.get('kickoff') != ticket['kickoff'] or not leg.get('gameId')
                    or leg.get('milestone') is not None
                    or leg.get('market') == 'moneyline' and
                       (leg.get('direction') not in ('home', 'away') or leg.get('line') is not None)
                    or leg.get('market') == 'total' and
                       (leg.get('direction') not in ('over', 'under') or not tickets.numeric(leg.get('line'))
                        or leg['line'] <= 0 or not float(leg['line']*2).is_integer())):
                return None, 'Unsupported original team market terms'
        elif (leg.get('market') not in stats
                or period not in (('full_game', '1Q') if league == 'NFL' else ('full_game',))
                or leg.get('book') != ticket['book'] or not str(leg.get('athleteId') or '')
                or leg.get('kickoff') != ticket['kickoff']
                or not tickets.numeric(leg.get('line')) or leg['line'] <= 0
                or not float(leg['line']*2).is_integer()
                or leg.get('direction') not in ('over', 'under')):
            return None, 'Unsupported original player, market, period or kickoff'
        if leg.get('milestone') is not None and (not tickets.numeric(leg['milestone'])
                or leg['direction'] != 'over' or leg['line'] != leg['milestone']-.5):
            return None, 'Published milestone must match the exact original half-point threshold'
        if (row.get('terms') != identity(leg) or row.get('final') is not True
                or row.get('completedPeriod') != period or not https(row.get('source'))
                or not kickoff < gates.when(row['checkedAt']) <= checked
                or row.get('participation') != 'played' or row.get('injuryReview') != 'clear'):
            return None, 'Exact completed-period stats, participation and clear injury review required'
        value = row.get('actual')
        if (not tickets.numeric(value) or not float(value).is_integer()
                or leg['market'] not in ('rushYds', 'recYds', 'passYds', 'moneyline') and value < 0):
            return None, 'Official numeric actual required; missing stats cannot become zero'
        if team_market:
            scores = row.get('scores')
            if (not isinstance(scores, dict) or set(scores) != {'home', 'away'}
                    or any(not tickets.numeric(v) or v < 0 or not float(v).is_integer() for v in scores.values())):
                return None, 'Official final home and away scores required for team markets'
            expected = (scores['home'] + scores['away'] if leg['market'] == 'total'
                        else scores[leg['direction']] - scores['away' if leg['direction'] == 'home' else 'home'])
            if value != expected:
                return None, 'Team actual contradicts official final scores'
        threshold = 0 if leg['market'] == 'moneyline' else leg['line']
        if value == threshold or row.get('result') in ('push', 'void'):
            return None, 'Removed leg needs an actual book decision and verified revised ticket price'
        result = 'win' if (value > threshold) == (leg['direction'] in ('over', 'home', 'away')) else 'loss'
        if row.get('result') != result:
            return None, 'Leg outcome contradicts its original threshold'
        results.append(result)
        label = leg.get('title', leg['market']) if team_market else leg['player']
        stat = leg['market'] if team_market else stats[leg['market']]
        actuals.append(f"{label}: {value:g} {stat} ({period}; {result})")
    result = 'loss' if 'loss' in results else 'win'
    odds = ticket['odds']
    units = -.25 if result == 'loss' else round(.25 * (odds / 100 if odds > 0 else 100 / -odds), 6)
    return {'id': ticket['id'], 'result': result, 'settledAt': gates.stamp(checked),
            'cashout': False, 'publicNote': 'Result at the published unit allocation.',
            'settlementBasis': BASIS, 'actual': '; '.join(actuals),
            'settlementLegResults': results, 'settlementLegActuals': [r['actual'] for r in rows],
            'accountingUnknown': False,
            'riskUnits': .25, 'units': units}, None


def append(ticket_id, evidence, now, *, root=record.ROOT, private=None):
    """Caller owns run.Lock. Validate before either append; retries repair projection."""
    root = Path(root)
    ticket = next((t for t in record.read(root/'data/community.json', {'tickets': []})['tickets']
                   if t['id'] == ticket_id), None)
    posts = record.read(root/'data/x-posted.json', {'posts': []})['posts']
    projected, held = review(ticket, evidence, posts, now)
    if held:
        raise ValueError(held)
    record.public_accounting(projected)
    target = root/'data/community-settlements.jsonl'
    current = [json.loads(line) for line in target.read_text().splitlines()] if target.exists() else []
    existing = [row for row in current if row.get('id') == ticket_id]
    if (projected not in current and existing
            and gates.when(projected['settledAt']) <= max(gates.when(row['settledAt']) for row in existing)):
        raise ValueError('A correction must have a later verified review; never overwrite or backdate results')
    private_path = Path(private or record.private_root())/'community-unit-results.jsonl'
    saved = {'id': ticket_id, 'evidence': evidence, 'publicSettlement': projected}
    previous = [json.loads(line) for line in private_path.read_text().splitlines()] if private_path.exists() else []
    added = saved not in previous
    if added:
        private_path.parent.mkdir(parents=True, exist_ok=True)
        with private_path.open('a') as stream:
            stream.write(json.dumps(saved, sort_keys=True)+'\n')
        private_path.chmod(0o600)
    if projected not in current:
        with target.open('a') as stream:
            stream.write(json.dumps(projected, sort_keys=True)+'\n')
    return projected, added


def main():
    import argparse
    import run
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--append', action='store_true')
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    with run.Lock(run.CONF/'run.lock', wait=run.RUN_LOCK_WAIT):
        now = datetime.now(timezone.utc)
        if args.append:
            result, added = append(args.id, evidence, now)
            committed = run.commit_log(now)
            print(json.dumps({'result': result, 'added': added, 'git': committed}))
        else:
            ticket = next(t for t in record.read(record.ROOT/'data/community.json', {})['tickets'] if t['id'] == args.id)
            posts = record.read(record.ROOT/'data/x-posted.json', {})['posts']
            result, held = review(ticket, evidence, posts, now)
            print(json.dumps({'result': result, 'held': held}))


if __name__ == '__main__':
    main()
