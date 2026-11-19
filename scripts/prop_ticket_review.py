"""Private MNF/TNF and NBA-alt ticket workbench. No network, admission or posting.

Stage exact, sourced ticket reviews on the existing desk-health clock. The
release worker separately verifies admission, the latest exact combined quote,
and current participation. Settlement requires its own evidence.
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
METHOD = 'sourced-prop-ticket-v1'
STATS = {'NFL': {'car': 'carries', 'rec': 'receptions', 'rushYds': 'rushing yards',
                 'recYds': 'receiving yards', 'passYds': 'passing yards',
                 'att': 'passing attempts', 'cmp': 'completions'},
         'NBA': {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists'}}
FAMILIES = {'MNF': ('NFL', 0), 'TNF': ('NFL', 3), 'NBA-alts': ('NBA', None)}
RELEASE_HOLDS = ['Private admission and attended exact combined-price recheck required before release',
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


def nba_fixtures(root):
    """Use the ordinary NBA capture's event IDs and original kickoff clocks."""
    path = Path(root) / 'data/nba-capture/slate.json'
    if not path.is_file():
        return {}
    games = json.loads(path.read_text())['games']
    return {game['id']: dict(game, **{side: game['teams'][side] for side in ('home', 'away')},
                            league='NBA', state='pre' if game.get('status') == 'scheduled'
                            else game.get('status')) for game in games
            if game.get('id') == f"NBA-{game.get('providerId')}" and game.get('providerId')}


def nba_participation(spec, games, root, now):
    """Cross-check attended evidence with the ordinary stored NBA intake."""
    import nba_capture
    import nba_player_props
    folder = Path(root) / 'data/nba-capture'
    try:
        snapshot = json.loads((folder / 'injuries-current.json').read_text())
        report_time = gates.when(snapshot['official']['reportedAt'])
        reports, rosters = {}, {}
        for leg in spec['legs']:
            game = games[leg['gameId']]
            if game.get('seasonType') != 'regular-season' or game.get('state') != 'pre':
                return 'Stored NBA fixture is outside the supported pregame regular-season scope'
            if game['id'] not in reports:
                reports[game['id']] = nba_capture.availability_for_game(snapshot, game, now, max_hours=1)
            rows, holds = reports[game['id']]
            name = leg['player']
            athlete = str(leg['athleteId'])
            if holds or any(str(row.get('athleteId') or row.get('id')) == athlete
                            and nba_capture.blocks_availability(row.get('status')) for row in rows):
                return f'{name}: current official NBA participation is unresolved'
            if gates.when(leg['review']['availability']['checkedAt']) < report_time:
                return f'{name}: attended participation review predates the latest official report'
            players = []
            for team in game['teams'].values():
                team_id = str(team['id'])
                if team_id not in rosters:
                    rosters[team_id] = json.loads((folder / 'rosters' / f'{team_id}.json').read_text())
                roster = rosters[team_id]
                if (str(roster.get('team')) != team_id or roster.get('season') != game['season']
                        or not nba_player_props.fresh(roster.get('retrievedAt'), now, 24)):
                    return f'{name}: current NBA roster evidence for both teams is required'
                players.extend(p for p in roster['players'] if str(p['id']) == athlete)
            if (len(players) != 1 or players[0].get('active') is not True
                    or nba_capture.blocks_availability(players[0].get('status'))
                    or nba_player_props.normal(players[0]['name']) != nba_player_props.normal(name)):
                return f'{name}: active player identity could not be confirmed on the current NBA roster'
    except (OSError, KeyError, ValueError, TypeError, AttributeError):
        return 'Current NBA roster or official participation snapshot unavailable'
    return None


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
    candidate = dict(spec, league=league, parlayType='longshot', riskUnits=.25,
                     selectionMethod=METHOD)
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
    external_tickets = {key: row for key, row in (risk_external or {}).items() if row.get('legs')}
    for key, existing in {**external_tickets, **(first or {})}.items():
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
        if len(legs) >= 6:
            captions = [parlay_caption.compact_prop(leg) for leg in legs]
        title = 'Daily Double' if spec.get('parlayStyle') == 'daily-double' else f'My {family} parlay'
        result['caption'] = parlay_caption.layout(
            f"{title} · {int(spec['odds']):+d} {spec['book']}", captions, '21+ only')
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
            'nextAction': ('Resolve the recorded holds, then use the reviewed-ticket admission and recheck'
                           if paths else 'Capture a fresh exact combined sportsbook ticket and sourced player review'),
            'releaseHolds': RELEASE_HOLDS}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    ctx = gates.Stores().as_of(now)
    ctx.games.update(nba_fixtures(ctx.root))
    print(json.dumps(review(json.loads(Path(args.spec).read_text()), ctx.games, now,
                            first=ctx.first, latest=ctx.latest, risk_external=ctx.risk_external), indent=2))
