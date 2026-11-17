"""Private MNF/TNF and NBA-alt ticket workbench. No network, admission or posting.

Stage exact, sourced ticket reviews on the existing desk-health clock. Passing
this review is not release authority: joint-price rechecks and sportsbook SGP
void/reprice settlement still need their own production integration and proof.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import gates
import parlay_caption
import x_post
from fun_ticket_review import https

VERSION = 'prop-ticket-workbench-v1'
STATS = {'NFL': {'car': 'carries', 'rec': 'receptions', 'rushYds': 'rushing yards',
                 'recYds': 'receiving yards', 'passYds': 'passing yards',
                 'att': 'passing attempts', 'cmp': 'completions'},
         'NBA': {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists'}}
FAMILIES = {'MNF': ('NFL', 0), 'TNF': ('NFL', 3), 'NBA-alts': ('NBA', None)}
RELEASE_HOLDS = ['Production admission and send-time joint-quote recheck not enabled',
                 'Book-specific parlay void/reprice and injury settlement proof required']


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def price(value):
    return numeric(value) and int(value) == value and 100 <= abs(value) <= 20000


def fresh(value, now, minutes=60):
    try:
        return timedelta(0) <= now - gates.when(value) <= timedelta(minutes=minutes)
    except (TypeError, ValueError):
        return False


def terms(spec):
    """Exact identity shared by the visible book receipt and reviewed packet."""
    return {'book': spec.get('book'), 'odds': spec.get('odds'),
            'legs': [{key: leg.get(key) for key in
                      ('gameId', 'athleteId', 'player', 'market', 'direction', 'line',
                       'period', 'book', 'odds', 'alternate')}
                     for leg in spec.get('legs', [])]}


def fingerprint(spec):
    return hashlib.sha256(json.dumps(terms(spec), sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def review(spec, games, now, *, first=None, latest=None, risk_external=None):
    """Validate a private proposal without turning a review into a public pick."""
    holds = []
    family = spec.get('family')
    league, weekday = FAMILIES.get(family, (None, None))
    legs = spec.get('legs')
    if not league or not isinstance(legs, list) or not legs or any(not isinstance(l, dict) for l in legs):
        return {'version': VERSION, 'state': 'held', 'releaseReady': False,
                'holds': ['Supported family and structured player legs required']}
    ctx = SimpleNamespace(now=now, games=games, first=first or {}, latest=latest or {},
                          risk_external=risk_external or {})
    candidate = dict(spec, league=league, parlayType='longshot', riskUnits=.25)
    shape = gates.longshot_shape(candidate, ctx)
    if not shape.ok:
        holds.append(shape.reason)
    if spec.get('book') not in ('DraftKings', 'FanDuel') or not price(spec.get('odds')):
        holds.append('Exact supported sportsbook and American combined price required')
    if spec.get('riskUnits', .25) != .25:
        holds.append('Existing fun-ticket stake is 0.25u')
    if any(spec.get(k) is not None for k in ('chance', 'rawChance', 'fairOdds', 'expectedValue')):
        holds.append('No probability or expected-value claim is supported')
    if any(spec.get(k) for k in ('priceBoosted', 'paidProtection', 'allAction')):
        holds.append('Boosts and special protection terms need a separate verified adapter')
    quote = spec.get('ticketQuote') or {}
    if (quote.get('verified') is not True or not quote.get('receipt')
            or not https(quote.get('source'), spec.get('book'))
            or quote.get('terms') != terms(spec) or not fresh(quote.get('checkedAt'), now)):
        holds.append('Fresh visible same-book combined ticket receipt matching every exact leg required')
    if spec.get('priceEstimated') is not False:
        holds.append('A multiplied or estimated price is not a sportsbook combined quote')
    seen, game_ids, captions = set(), set(), []
    for index, leg in enumerate(legs, 1):
        issues = []
        game = games.get(leg.get('gameId')) or {}
        kickoff = game.get('kickoff')
        try:
            kick = gates.when(kickoff)
            valid_time = (kick > now + timedelta(minutes=30)
                          and gates.eastern_date(kick) == gates.eastern_date(now)
                          and (weekday is None or kick.astimezone(gates.EASTERN).weekday() == weekday))
        except (TypeError, ValueError):
            valid_time = False
        if (game.get('league') != league or game.get('state') != 'pre'
                or not valid_time or leg.get('kickoff') != kickoff):
            issues.append('current-day scheduled fixture and release window required')
        identity = (leg.get('gameId'), str(leg.get('athleteId') or ''))
        if not identity[1] or identity in seen or not str(leg.get('player') or '').strip():
            issues.append('unique named player/game identity required')
        seen.add(identity)
        game_ids.add(leg.get('gameId'))
        if (leg.get('market') not in STATS.get(league, {}) or leg.get('period') != 'full_game'
                or leg.get('direction') not in ('over', 'under') or not numeric(leg.get('line'))
                or leg.get('line', 0) <= 0 or not float(leg.get('line', 0) * 2).is_integer()):
            issues.append('supported exact full-game player threshold required')
        if leg.get('book') != spec.get('book') or not price(leg.get('odds')):
            issues.append('exact leg price at the ticket sportsbook required')
        if (not https(leg.get('source'), spec.get('book')) or not fresh(leg.get('observedAt'), now)):
            issues.append('fresh exact sportsbook leg source required')
        if family == 'NBA-alts' and leg.get('alternate') is not True:
            issues.append('NBA alternate must be an observed priced alternate, not an invented milestone')
        if leg.get('alternate'):
            main = leg.get('mainLine')
            if not numeric(main) or not numeric(leg.get('line')) or not (
                    leg['line'] < main if leg.get('direction') == 'over' else leg['line'] > main):
                issues.append('alternate must cushion the same observed main-line market')
        evidence = leg.get('review') or {}
        if (evidence.get('reviewer') != 'kookn-desk' or evidence.get('approved') is not True
                or not fresh(evidence.get('checkedAt'), now)
                or any(not isinstance(evidence.get(k), str) or len(evidence[k].strip()) < 20
                       for k in ('role', 'matchup', 'why', 'countercase'))):
            issues.append('fresh sourced role, matchup, reason and countercase review required')
        facts = evidence.get('sources') or []
        if (not isinstance(facts, list) or not {'role', 'matchup', 'availability'} <=
                {f.get('kind') for f in facts if isinstance(f, dict)}
                or any(not isinstance(f, dict) or not https(f.get('url'))
                       or not f.get('fact') or not fresh(f.get('checkedAt'), now, 1440) for f in facts)):
            issues.append('role, matchup and availability facts need current source evidence')
        availability = evidence.get('availability') or {}
        if (availability.get('status') != 'active' or not fresh(availability.get('checkedAt'), now)
                or str(availability.get('athleteId')) != identity[1]
                or availability.get('gameId') != identity[0] or not https(availability.get('source'))):
            issues.append('current exact-player availability must be resolved')
        if any(leg.get(k) is not None for k in ('chance', 'rawChance', 'fairOdds', 'expectedValue')):
            issues.append('leg probabilities cannot be multiplied into an SGP claim')
        holds.extend(f'Leg {index}: {issue}' for issue in issues)
        if not issues:
            captions.append(f"{leg['player']} {leg['direction']} {leg['line']:g} {STATS[league][leg['market']]}")
    if league == 'NFL' and len(game_ids) != 1:
        holds.append('MNF/TNF review must describe one exact primetime game')
    if len(game_ids) < len(legs):
        correlation = spec.get('correlationReview') or {}
        if (not fresh(correlation.get('checkedAt'), now)
                or any(not isinstance(correlation.get(k), str) or len(correlation[k].strip()) < 20
                       for k in ('sharedScript', 'failureCase'))):
            holds.append('Same-game ticket needs a shared-game-script and correlated failure review')
    for rule in (gates.player_overlap, gates.alternate_parlay_frequency, gates.longshot_one_per_day):
        decision = rule(candidate, ctx)
        if not decision.ok:
            holds.append(decision.reason)
    # The shared straight occupancy helper deliberately excludes tickets.
    # This workbench also checks open tickets and private reservations.
    for key, existing in (first or {}).items():
        if key == spec.get('id'):
            continue
        existing = dict(existing, **(latest or {}).get(key, {}))
        if existing.get('result') or existing.get('status') in ('settled', 'withdrawn', 'historical'):
            continue
        if seen & {gates.player_exposure(l) for l in existing.get('legs') or [existing]}:
            holds.append(f'{key} already reserves this player/game; repeated exposure held')
    result = {'version': VERSION, 'family': family, 'checkedAt': gates.stamp(now),
              'state': 'held' if holds else 'reviewed-private', 'releaseReady': False,
              'holds': list(dict.fromkeys(holds)), 'releaseHolds': RELEASE_HOLDS,
              'termsFingerprint': fingerprint(spec), 'riskUnits': .25,
              'jointPriceBasis': 'Observed sportsbook ticket only; no multiplication'}
    if not holds:
        result['caption'] = parlay_caption.layout(
            f"My {family} parlay · {int(spec['odds']):+d} {spec['book']}", captions, '21+ only')
        if x_post.tweet_length(result['caption']) > x_post.LIMIT or x_post.x_style(result['caption']):
            result['state'] = 'held'
            result['holds'].append('Complete one-leg-per-line caption needs voice or length review')
    return result


def summary(conf, games, now):
    """Bounded private inputs; never expose receipts or captions in health output."""
    folder = Path(conf) / 'prop-ticket-reviews'
    paths = sorted(folder.glob('*.json'))[:20]
    counts = {'reviewed-private': 0, 'held': 0, 'invalid': 0}
    fixtures = {family: 0 for family in FAMILIES}
    for game in games.values():
        try:
            kick = gates.when(game.get('kickoff'))
            if game.get('state') != 'pre' or not now < kick <= now + timedelta(days=7):
                continue
            for family, (league, weekday) in FAMILIES.items():
                if game.get('league') == league and (weekday is None or kick.astimezone(gates.EASTERN).weekday() == weekday):
                    fixtures[family] += 1
        except (TypeError, ValueError):
            continue
    for path in paths:
        try:
            if path.stat().st_size > 256_000:
                raise ValueError('oversize')
            spec = json.loads(path.read_text())
            result = review(spec, games, now)
            counts[result['state']] += 1
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            counts['invalid'] += 1
    return {'version': VERSION, 'checkedAt': gates.stamp(now), 'planningOnly': True,
            'releaseReady': False, 'counts': counts, 'providerRequests': 0,
            'storedUpcomingGames7d': fixtures,
            'nextAction': ('Review held private packets and complete production release/settlement adapters'
                           if paths else 'Capture a fresh exact combined sportsbook ticket and sourced player review'),
            'releaseHolds': RELEASE_HOLDS}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    ctx = gates.Stores().as_of(now)
    nba_path = Path(__file__).resolve().parents[1] / 'data/nba-capture/slate.json'
    if nba_path.exists():
        nba_slate = json.loads(nba_path.read_text())
        ctx.games.update({f"NBA-{g['providerId']}": dict(g, league='NBA',
            state='pre' if g.get('status') == 'scheduled' else g.get('status'))
            for g in nba_slate.get('games', []) if g.get('providerId')})
    print(json.dumps(review(json.loads(Path(args.spec).read_text()), ctx.games, now,
                            first=ctx.first, latest=ctx.latest), indent=2))
