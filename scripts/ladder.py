"""The Kook'n 80/20 Climb: a $50-to-$1,000 bankroll ladder, one rung at a time. Stdlib only.

The owner's call (2026-09-26): "50 -> 1000 on 1-2 leg safe bets", with alternate lines. On October 10 the owner
set the rung band to -300 through -200 and asked the automatic builder to consider one or two exact main
moneylines as well as safer player alternates. Every leg still needs model agreement, fresh two-sided pricing and
a saved factual reason before it can post. A person may also supply exact, fresh sportsbook quotes for alternate
spreads or totals; those legs have to clear the same guards. After a win the
ladder banks 20% of the return and rides the other 80% on the next rung. A miss ends that climb but cannot take what
was banked. The climb reaches $1,000 when its bank plus the next stake reaches the goal; the next rung then starts a
new climb at $50. Money is whole dollars: a rung pays round(stake x the ticket's decimal price), the bank gets
round(return x 20%), and the remainder rides.

Like the easy parlay, a rung is never called value. Our player chances are tuned against main lines (and learning
found them too confident even there), so easier-line probabilities are anchored to the sportsbook price and are
never presented as raw model certainty. The market's own price carries most of the safety; our number has to agree
with room to spare. A player needs five current-season appearances, or an established same-team role from last
season. A quarterback passing leg needs five actual starts for that team unless that same-team role is established.

The ladder's state is never stored. state() reads it from the published rungs and their results, so it can not
drift from the record. One rung is open at a time. After it settles, the next scheduled scan may publish another
qualifying rung—including a new $50 climb after a loss—but a rung is never forced. A rung pulled before its post
still counts and is not replaced. A rung with a void leg is settled by a person
(run.settle reports it), and the ladder waits for that.

Prices: SharpAPI's DraftKings and FanDuel alternate player lines in data/prop-odds (scripts/sharp_odds.py), no
credits. NFL legs now; college legs (legal pregame in Indiana, gates.INDIANA_BOOKS) once learning has calibrated
college player numbers, as for college props. A rung is built only from prices read within FRESH. The ladder is kept apart from the record, in dollars, on the site and on X.

  python scripts/ladder.py [--now ISO]      where the ladder stands, and the rung the desk would build now
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import easy_parlay
import gates
import parlay
import pricing
import role_sanity
import sharp_odds
from sports_refresh import eastern_date

START, GOAL = 50, 1000              # dollars
BANK_RATE = 0.20                    # "Bank 20. Ride 80." (owner, 2026-09-28)
BOOKS = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}
SLUGS = {'DraftKings': 'dk', 'FanDuel': 'fd'}
MARKETS = ('recYds', 'rushYds', 'rec', 'passYds')     # lines a follower reads at a glance
LEG_PRICES = (-900, -180)           # safer favored legs; two around -400 is the preferred shape
RAW_MIN_CHANCE = 0.85               # the uncalibrated projection still has to clear the easier line comfortably
MIN_CHANCE = 0.83                   # conservative, market-anchored chance used to compare eligible legs
MODEL_LIFT_CAP = 0.06               # an alternate-line model cannot claim more than six points above its price
MIN_GAP = 0.04                      # safety comes from the price; our number still has to agree
MAX_GAP = 0.18                      # and no further: a book that far off an easy line is a data or role problem, not a gift
MAIN_RATIO = (0.6, 1.6)             # the book's main line against our projection: outside this, the market is another one
TARGET = (-300, -200)               # one or two safer legs in the owner's current rung band (owner, 2026-10-10)
MANUAL_RAW_CHANCE = 0.72             # exact game alternates: the unshrunk model must still agree comfortably
MONEYLINE_MIN_CHANCE = 0.70         # strong-favorite floor; the exact two-sided market still anchors the check
MONEYLINE_MIN_GAP = 0.03            # our win estimate must clear the book's fair chance by three points
MONEYLINE_PAIR_BAND = (0.99, 1.15)  # broken or mismatched two-sided captures never become a rung
LEAD = timedelta(minutes=15)        # a late admission still needs a real pre-kickoff posting window
FRESH = timedelta(hours=12)         # prices older than this are not used
GAME_FRESH = timedelta(hours=2)     # main moneylines are re-read on game day before admission
WINDOW = timedelta(minutes=90)      # one rung settles before a later part of the slate can become the next rung
STAKE = parlay.STAKE                # the ticket's size in the desk's own terms; the ladder itself counts dollars
SOURCE = 'https://sharpapi.io/'


def stable_role(ctx, athlete, team, league, stat):
    """Ladder roles need more evidence than an ordinary research row.

    Five appearances keeps three-game hot starts and newly promoted roles out. Passing yards additionally require
    five games as that team's primary passer; relief appearances are not a quarterback workload sample. An
    established same-team role from the prior season remains eligible early in a new season.
    """
    athlete, team = str(athlete), str(team)
    established = (athlete, team) in (getattr(ctx, 'established', set()) or set())
    if not established and (getattr(ctx, 'appearances', {}).get(athlete, 0) or 0) < 5:
        return False
    if stat != 'passYds' or established:
        return True
    starts = (getattr(ctx, 'passers', {}) or {}).get(gates.team_key(league, team), [])
    return sum(str(starter) == athlete for starter in starts) >= 5


def rungs(first, latest):
    """Every published rung, oldest first, merged with its latest revision."""
    out = [dict(pick, **latest.get(key, {})) for key, pick in first.items() if pick.get('parlayType') == 'ladder']
    return sorted(out, key=lambda p: (str(p.get('publishedAt') or ''), str(p.get('id'))))


def played(rung):
    """A rung that counts: graded, still open, or pulled before its post. The owner counts every published ladder
    decision (2026-09-28), so a pulled ungraded rung stays open and blocks the next one until its result."""
    if rung.get('result'):
        return True
    if 'before its post went out' in str(rung.get('entryNote') or '') or str(rung.get('entryNote') or '').startswith('Pulled before posting:'):
        return True
    return not rung.get('entryNote') and (rung.get('status') or 'active') == 'active'


def state(first, latest):
    """Where the ladder stands, from the rungs themselves:
    {'run', 'step', 'stake', 'banked', 'saved', 'open', 'history', 'climbs', 'start', 'goal'}.

    A win banks 20% of its return and rides 80%; reaching the goal with the bank plus the next stake finishes the
    climb. A loss starts a new climb at START while the already saved money stays saved; a push or void keeps the
    stake, bank and step."""
    run, step, stake, banked, saved, open_rung = 1, 1, START, 0, 0, None
    history, climbs = [], []
    wagered = returned_total = wins = losses = pushes = voids = 0
    for rung in rungs(first, latest):
        if not played(rung):
            continue
        info = rung.get('ladder') or {}
        result = rung.get('result')
        if not result:
            open_rung = rung
            continue
        rung_stake = int(info.get('stake') or stake)
        wagered += rung_stake
        item = {'id': rung['id'], 'run': info.get('run'), 'step': info.get('step'), 'stake': info.get('stake'),
                'payout': info.get('payout'), 'odds': rung.get('odds'), 'result': result,
                'settledAt': rung.get('settledAt')}
        if result == 'win':
            returned = int(info.get('payout') or stake)
            returned_total += returned
            wins += 1
            before = int(info.get('banked') if info.get('banked') is not None else banked)
            cut, next_stake = split_return(returned)
            after = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else before + cut)
            next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else next_stake)
            saved += max(0, after - before)
            banked, stake, step = after, next_stake, step + 1
            item.update({'banked': before, 'bankedAfter': after, 'nextStake': next_stake})
            if banked + stake >= GOAL:
                climbs.append({'run': run, 'steps': int(info.get('step') or step - 1), 'final': banked + stake,
                               'banked': banked, 'id': rung['id']})
                run, step, stake, banked = run + 1, 1, START, 0
        elif result == 'loss':
            losses += 1
            run, step, stake, banked = run + 1, 1, START, 0
        elif result == 'push':
            returned_total += rung_stake
            pushes += 1
        elif result == 'void':
            returned_total += rung_stake
            voids += 1
        item['ladderTotal'] = {'wagered': wagered, 'returned': returned_total,
                               'net': returned_total - wagered}
        history.append(item)
    accounting = {'wagered': wagered, 'returned': returned_total, 'net': returned_total - wagered,
                  'atRisk': int((open_rung.get('ladder') or {}).get('stake') or stake) if open_rung else 0,
                  'wins': wins, 'losses': losses, 'pushes': pushes, 'voids': voids}
    return {'run': run, 'step': step, 'stake': stake, 'open': open_rung, 'history': history, 'climbs': climbs,
            'banked': banked, 'saved': saved, 'bankPercent': int(BANK_RATE * 100),
            'ridePercent': 100 - int(BANK_RATE * 100), 'start': START, 'goal': GOAL,
            'accounting': accounting}


def saved_through(first, latest, target):
    """Lifetime protected dollars immediately after one rung, for immutable result artwork."""
    saved = 0
    for rung in rungs(first, latest):
        if not played(rung):
            continue
        info = rung.get('ladder') or {}
        if rung.get('result') == 'win':
            before = int(info.get('banked') or 0)
            if info.get('bankedAfter') is not None:
                after = int(info['bankedAfter'])
            else:
                # Early rungs predate the explicit bank fields. Reconstruct the same
                # whole-dollar 80/20 split used by state() so immutable result art and
                # the live feed retain the lifetime bank from those wins.
                cut, _ = split_return(info.get('payout') or info.get('stake') or 0)
                after = before + cut
            saved += max(0, after - before)
        if rung.get('id') == target:
            break
    return saved


def payout(stake, odds):
    return int(round(stake * parlay.decimal(odds)))


def split_return(returned):
    """Whole-dollar 80/20 split: bank 20% of the return and ride the remainder."""
    returned = int(returned)
    bank = int(round(returned * BANK_RATE))
    return bank, returned - bank


def todays_games(games, now, league, exclude=()):
    """The league's games today (Eastern), far enough from kickoff to post a rung before them."""
    day = eastern_date(now)
    return [g for g in games.values() if g.get('league') == league and g.get('state', 'pre') == 'pre' and g['id'] not in set(exclude)
            and eastern_date(gates.when(g['kickoff'])) == day and gates.when(g['kickoff']) > now + LEAD]


def kickoff_windows(games):
    """Chronological, non-overlapping kickoff groups.

    A rung may use one or two games, but it must settle as one part of the slate.  Mixing an early game with a
    night game would keep the rung open all day and make a later step impossible.  A one-game window remains
    useful only for a supported one-leg rung; the one-leg-per-game rule still prevents a same-game parlay.
    """
    remaining = sorted(games, key=lambda game: (gates.when(game['kickoff']), game['id']))
    out = []
    while remaining:
        start = gates.when(remaining[0]['kickoff'])
        window = [game for game in remaining if gates.when(game['kickoff']) <= start + WINDOW]
        out.append(window)
        used = {game['id'] for game in window}
        remaining = [game for game in remaining if game['id'] not in used]
    return out


def confirmed_at(root=None):
    """gameId -> when the prop feed last read the game's numbers, changed or not (data/prop-odds/sharp-status.json)."""
    path = Path(root or Path(__file__).resolve().parents[1]) / 'data' / 'prop-odds' / 'sharp-status.json'
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('confirmed') or {}
    except (OSError, ValueError):
        return {}


def legs_for_game(game, record, ctx, now, confirmed=None):
    """Every easier line in this game our projection clears comfortably, at a price worth a rung, from each book. The
    prices are as of the last time the feed read them (`confirmed`), or when they were stored."""
    snapshot = ctx.snapshot(game['id'])
    if not snapshot or not record:
        return []
    seen = max([record['retrievedAt']] + [at for at in [(confirmed or {}).get(game['id'])] if at and gates.when(at) <= now],
               key=gates.when)
    if now - gates.when(seen) > FRESH:
        return []
    ids = [p['id'] for side in ('home', 'away') for p in ((snapshot.get('players') or {}).get(side) or {}).get('players', [])]
    by_name = {easy_parlay.name_key(ctx.names.get(str(i))): str(i) for i in ids if ctx.names.get(str(i))}
    out = []
    for book_key, book in (record.get('books') or {}).items():
        if book_key not in BOOKS:
            continue
        for stat, players in (book.get('markets') or {}).items():
            if stat not in MARKETS:
                continue
            for name, quote in (players or {}).items():
                athlete = by_name.get(easy_parlay.name_key(name))
                side, player = pricing.player_line(snapshot, athlete) if athlete else (None, None)
                projected = (player or {}).get(pricing.PROJECTED[stat])
                if not projected or player.get('limited') or not side:
                    continue
                if role_sanity.assess(player, getattr(ctx, 'player_logs', {}).get(str(athlete)),
                                      game[side]['id'], stat, game.get('season')):
                    continue
                if not stable_role(ctx, athlete, game[side]['id'], game['league'], stat):
                    continue
                if gates.listed_status(athlete, str(game[side]['id']), ctx) in gates.LISTED:
                    continue
                mean, low, high = projected
                sd = (high - mean) / pricing.Z80
                main = quote.get('line')
                if sd <= 0 or not isinstance(main, (int, float)) or not MAIN_RATIO[0] <= main / max(mean, 1.0) <= MAIN_RATIO[1]:
                    continue
                # Only the main line's own ladder: the feed files some period ladders under the full-game market.
                offers = [(main, quote.get('over'))] + [(a['line'], a['over']) for a in sharp_odds.consistent(quote)]
                for point, price in offers:
                    if not isinstance(point, (int, float)) or not isinstance(price, (int, float)):
                        continue
                    price = int(price)
                    if not LEG_PRICES[0] <= price <= LEG_PRICES[1] or float(point) != int(point) + 0.5:
                        continue            # a half point, so the leg can not push
                    raw, _, _ = pricing.chances(mean, sd, float(point))
                    implied = pricing.break_even(price)
                    if raw < RAW_MIN_CHANCE or not MIN_GAP <= raw - implied <= MAX_GAP:
                        continue
                    chance = min(raw, implied + MODEL_LIFT_CAP)
                    if chance < MIN_CHANCE:
                        continue
                    shown = ctx.names.get(athlete) or name
                    out.append({'id': f"ladder-{game['id']}-{athlete}-{stat}-{float(point):g}",
                                'title': f"{shown} {int(point + 0.5)}+ {pricing.WORDS[stat]}",
                                'gameId': game['id'], 'athleteId': athlete, 'player': shown, 'market': stat, 'direction': 'over',
                                'line': float(point), 'book': BOOKS[book_key], 'odds': price,
                                'chance': round(chance, 3), 'rawChance': round(raw, 3),
                                'implied': round(implied, 3), 'projection': round(mean, 1), 'kickoff': game['kickoff'],
                                'observedAt': seen, 'marketWindow': 'Full game',
                                'alternate': float(point) != float(main)})
    return out


def moneyline_legs(game, ctx, now):
    """A fresh exact favorite moneyline whose two-sided price and our winner estimate agree.

    ESPN supplies the current DraftKings pair without an added paid request.  The fair chance is computed from
    both sides at that same book; a one-sided, stale or abnormal pair is unusable.  The stored model may support
    the market, but the run still requires a separate saved factual reason before publishing the rung.
    """
    snapshot = ctx.snapshot(game['id'])
    market = game.get('market') or {}
    observed = game.get('marketRetrievedAt')
    if not snapshot or not observed:
        return []
    try:
        age = now - gates.when(observed)
    except (TypeError, ValueError):
        return []
    if not timedelta(minutes=-1) <= age <= GAME_FRESH:
        return []
    provider = str(market.get('provider') or '').strip()
    provider = build_site.BOOKS.get(provider, provider)
    book = next((name for name in SLUGS if name.lower() == provider.lower()), None)
    if not book:
        return []
    home, away = build_site.american(market.get('homeML')), build_site.american(market.get('awayML'))
    if home is None or away is None:
        return []
    total = pricing.break_even(home) + pricing.break_even(away)
    if not MONEYLINE_PAIR_BAND[0] <= total <= MONEYLINE_PAIR_BAND[1]:
        return []
    out = []
    for side, price, other in (('home', home, away), ('away', away, home)):
        if not LEG_PRICES[0] <= price <= LEG_PRICES[1]:
            continue
        try:
            raw = pricing.price(snapshot, 'moneyline', side, 0, price)['rawChance']
            fair = pricing.fair_chance(price, other)
        except (KeyError, TypeError, ValueError):
            continue
        gap = raw - fair
        if raw < MONEYLINE_MIN_CHANCE or not MONEYLINE_MIN_GAP <= gap <= MAX_GAP:
            continue
        chance = min(raw, fair + MODEL_LIFT_CAP)
        team = game[side]
        out.append({'id': f"ladder-{game['id']}-moneyline-{side}",
                    'title': f"{team.get('short') or team.get('abbreviation')} moneyline",
                    'gameId': game['id'], 'marketType': 'moneyline', 'direction': side, 'line': 0,
                    'team': str(team.get('id') or ''), 'book': book, 'odds': int(price),
                    'chance': round(chance, 3), 'rawChance': round(raw, 3),
                    'fairChance': round(fair, 3), 'implied': round(pricing.break_even(price), 3),
                    'projection': round(raw, 3), 'kickoff': game['kickoff'], 'observedAt': observed,
                    'marketWindow': 'Full game', 'alternate': False})
    return out


def strict_legs(legs, policy, now, league):
    """The stricter Climb pool (direction rules, owner 2026-10-07): only the legs whose segment is neither paused nor
    carrying a raised edge bar (`direction.flagged`). The leg chance, leg prices and TARGET are unchanged, so it can
    only remove legs, never add or loosen one, and it lets a segment back in as soon as its own flag clears."""
    import direction
    return [leg for leg in legs if not direction.flagged(policy, direction.leg_segment(leg, league), now)]


def pairs(legs):
    """Every eligible rung: (book, leg, leg, decimal, price) for two legs from different games at one book whose
    price multiplies inside TARGET."""
    for book in sorted({leg['book'] for leg in legs}):
        mine = [l for l in legs if l['book'] == book]
        for a, b in combinations(mine, 2):
            if a['gameId'] == b['gameId']:
                continue
            dec = parlay.decimal(a['odds']) * parlay.decimal(b['odds'])
            price = parlay.american(dec)
            if TARGET[0] <= price <= TARGET[1]:
                yield book, a, b, dec, price


def tickets(legs):
    """Every eligible one- or two-leg rung in the owner's current price band."""
    for leg in legs:
        if TARGET[0] <= leg['odds'] <= TARGET[1]:
            yield leg['book'], (leg,), parlay.decimal(leg['odds']), leg['odds']
    for book, a, b, dec, price in pairs(legs):
        yield book, (a, b), dec, price


def build(legs):
    """The safest supported one- or two-leg rung inside TARGET.

    Safety is the conservative joint chance above the ticket's price, then the joint chance itself.  This keeps a
    merely shorter one-leg price from automatically beating a stronger two-game combination.
    """
    best = None
    for book, chosen, dec, price in tickets(legs):
        chance = 1.0
        for leg in chosen:
            chance *= leg['chance']
        chance = round(chance, 4)
        key = (round(chance - pricing.break_even(price), 4), chance, price)
        if best is None or key > best[0]:
            selected = sorted(chosen, key=lambda l: (l['kickoff'], l['title']))
            best = (key, {'book': book, 'legs': selected, 'odds': price, 'decimal': round(dec, 3),
                          'gameIds': [l['gameId'] for l in selected],
                          'quotedAt': min(l['observedAt'] for l in selected),
                          'firstKickoff': min(l['kickoff'] for l in selected), 'chance': chance})
    if not best:
        return None, f'no book has one or two supported legs that pay {TARGET[0]:+d} to {TARGET[1]:+d}'
    return best[1], None


def ticket_pick(ticket, league, where, now, games):
    """Attach the climb's dollars and public fields to a validated ticket."""
    first = games.get(ticket['gameIds'][0]) or {}
    day = eastern_date(now)
    stake, banked = where['stake'], where['banked']
    returned = payout(stake, ticket['odds'])
    bank_cut, next_stake = split_return(returned)
    info = {'run': where['run'], 'step': where['step'], 'stake': stake, 'payout': returned,
            'banked': banked, 'bankThisWin': bank_cut, 'bankedAfter': banked + bank_cut,
            'nextStake': next_stake, 'totalAfter': banked + returned,
            'bankPercent': int(BANK_RATE * 100), 'ridePercent': 100 - int(BANK_RATE * 100),
            'start': START, 'goal': GOAL}
    base = (f"{league}-{first.get('season', day.year)}-W{first.get('week', 0)}-ladder-{day:%m%d}-"
            f"c{info['run']}s{info['step']}-{SLUGS[ticket['book']]}")
    sources = set(ticket.get('sources') or [])
    if ticket.get('quoteType', 'capture') == 'capture':
        sources.add(SOURCE)
    sources.update(games[g]['source'] for g in ticket['gameIds'] if g in games and games[g].get('source'))
    return {'id': base,
            'title': f"Ladder step {info['step']}: {len(ticket['legs'])} legs at {ticket['book']}",
            'status': 'active', 'favorite': False, 'parlayType': 'ladder', 'riskUnits': STAKE,
            'ladder': info, 'legs': ticket['legs'], '_league': league,
            'correlation': 'One leg per game, so the book prices the ticket as the legs multiplied.',
            'gameIds': ticket['gameIds'], 'book': ticket['book'], 'odds': ticket['odds'],
            'quotedAt': ticket['quotedAt'], 'priceEstimated': ticket.get('priceEstimated', True),
            'expiresAt': gates.stamp(min(gates.next_slot(now), gates.when(ticket['firstKickoff']))),
            'quoteType': ticket.get('quoteType', 'capture'), 'confidence': 1,
            'edge': (f"For fun, not value: {len(ticket['legs'])} protected lines with stable roles that our model "
                     f"direction agrees with, at {ticket['book']}'s exact prices, multiplied to "
                     f"{ticket['odds']:+d}. ${stake} rides with ${banked} already banked. A win returns "
                     f"${returned}: ${bank_cut} goes to the bank and ${next_stake} rides next. Bank 20, ride 80."),
            'cutoff': 'A ladder rung is not re-entered. It stands or falls as posted.',
            'sources': sorted(sources)}


def manual_candidate(ctx, games, now, spec):
    """Build one rung from exact sportsbook game-alternate quotes a person just verified.

    This is deliberately not a scraper. The spec records the visible book, line, price, source URL and quote time;
    the model supplies the chance and refuses a leg it does not independently support.
    """
    where = state(ctx.first, ctx.latest)
    if where['open']:
        return None, f"{where['open']['id']} is still open; the next rung waits for its result"
    if not isinstance(spec, dict) or len(spec.get('legs') or []) not in (1, 2):
        return None, 'a manual rung needs one or two quoted legs'
    book = spec.get('book')
    if book not in SLUGS:
        return None, 'the manual rung needs one supported book'
    quoted = spec.get('quotedAt')
    try:
        age = now - gates.when(quoted)
    except (TypeError, ValueError):
        return None, 'the manual rung needs a valid quote time'
    if not timedelta(minutes=-1) <= age <= FRESH:
        return None, 'the manual sportsbook quotes are stale'
    legs, leagues, game_ids, sources = [], set(), set(), set()
    for row in spec['legs']:
        game = games.get(row.get('gameId'))
        if not game or game.get('state', 'pre') != 'pre' or gates.when(game['kickoff']) <= now + LEAD:
            return None, f"{row.get('gameId')} is missing, started, or too close to kickoff"
        if game['id'] in game_ids:
            return None, 'a rung uses one leg per game'
        market, side = row.get('marketType'), row.get('direction')
        line, price = row.get('line'), row.get('odds')
        allowed = ('home', 'away') if market == 'spread' else ('over', 'under')
        if market not in ('spread', 'total') or side not in allowed:
            return None, 'a manual game leg needs a spread side or total direction'
        # ``int()`` truncates toward zero, so ``int(-1.5) + .5`` is -0.5.
        # Check the doubled value instead so favorite spreads such as -1.5
        # receive the same no-push treatment as +1.5 and game totals.
        twice = float(line) * 2 if isinstance(line, (int, float)) else 0
        if not isinstance(line, (int, float)) or not twice.is_integer() or int(twice) % 2 == 0:
            return None, 'manual game alternates use half-point lines so they cannot push'
        if not isinstance(price, (int, float)) or not LEG_PRICES[0] <= int(price) <= LEG_PRICES[1]:
            return None, f'each manual leg must be priced {LEG_PRICES[0]:+d} to {LEG_PRICES[1]:+d}'
        snapshot = ctx.snapshot(game['id'])
        if not snapshot:
            return None, f"no model snapshot for {game['id']}"
        try:
            desk = pricing.price(snapshot, market, side, float(line), int(price))
        except (ValueError, KeyError):
            return None, f"the model cannot price {game['id']} {market}"
        if desk['rawChance'] < MANUAL_RAW_CHANCE:
            return None, f"the raw model only gives {100 * desk['rawChance']:.1f}% to {game['id']} {market}"
        team = game[side]['short'] if market == 'spread' else f"{game['away']['short']} at {game['home']['short']}"
        title = f"{team} {pricing.signed(float(line))}" if market == 'spread' else f"{team} {side} {pricing.fmt(float(line))}"
        source = row.get('source') or spec.get('source')
        if not str(source or '').startswith('https://'):
            return None, 'every manual quote needs its sportsbook page'
        sources.add(source)
        game_ids.add(game['id'])
        leagues.add(game['league'])
        legs.append({'id': f"ladder-{game['id']}-{market}-{side}-{float(line):g}", 'title': title,
                     'gameId': game['id'], 'marketType': market, 'direction': side, 'line': float(line),
                     'book': book, 'odds': int(price), 'chance': desk['rawChance'], 'implied': desk['breakEven'],
                     'projection': desk['projection'], 'kickoff': game['kickoff'], 'observedAt': quoted,
                     'marketWindow': 'Full game', 'alternate': True})
    if len(leagues) != 1:
        return None, 'a rung stays inside one league'
    kickoffs = [gates.when(games[game_id]['kickoff']) for game_id in game_ids]
    if max(kickoffs) - min(kickoffs) > WINDOW:
        return None, 'a rung stays inside one kickoff window so a later step can follow after it settles'
    dec = 1.0
    for leg in legs:
        dec *= parlay.decimal(leg['odds'])
    price = parlay.american(dec)
    if not TARGET[0] <= price <= TARGET[1]:
        return None, f'the quoted ticket is {price:+d}; the climb targets {TARGET[0]:+d} to {TARGET[1]:+d}'
    chance = 1.0
    for leg in legs:
        chance *= leg['chance']
    ticket = {'book': book, 'legs': legs, 'odds': price, 'decimal': round(dec, 3),
              'gameIds': [leg['gameId'] for leg in legs], 'quotedAt': quoted,
              'firstKickoff': min(l['kickoff'] for l in legs), 'chance': round(chance, 4),
              'priceEstimated': False, 'quoteType': 'sportsbook', 'sources': sorted(sources)}
    return ticket_pick(ticket, leagues.pop(), where, now, games), None


def candidate(ctx, games, now, exclude=()):
    """The next rung as a pick, or (None, reason). Games in `exclude` (the desk has a reason against them) are left off.
    NFL first, then college: a rung stays inside one league, as a report does."""
    where = state(ctx.first, ctx.latest)
    if where['open']:
        return None, f"{where['open']['id']} is still open; the next rung waits for its result"
    import direction
    # Two climbs in a row lost at step 1 or 2: the next climb takes the stricter pool (owner, 2026-10-07): no leg from
    # a segment that is paused or has a raised edge bar, with the same leg chance, leg prices and TARGET.
    policy = getattr(ctx, 'policy', None)
    strict = direction.climb_rules(policy, now)
    reasons = []
    for league in ('NFL', 'CFB'):
        today = todays_games(games, now, league, exclude)
        if not today:
            reasons.append(f'{league}: {len(today)} games left today')
            continue
        seen = confirmed_at()
        calibrated = league not in gates.OWN_CALIBRATION or bool(
            ((getattr(ctx, 'policy', None) or {}).get('calibration') or {}).get(f'{league}/prop'))
        if not calibrated:
            reasons.append(f'{league}: player alternates wait for their own calibration; game moneylines still checked')
        for window in kickoff_windows(today):
            legs = [leg for game in window for leg in moneyline_legs(game, ctx, now)]
            if calibrated:
                legs += [leg for game in window
                         for leg in legs_for_game(game, ctx.prop_odds.get(game['id']), ctx, now, seen)]
            if strict:
                legs = strict_legs(legs, policy, now, league)
            ticket, reason = build(gates.without_straight_players(legs, ctx))
            label = gates.when(window[0]['kickoff']).astimezone(gates.EASTERN).strftime('%-I:%M %p ET')
            if not ticket:
                reasons.append(f'{league} {label}: {reason}' + ('; the stricter Climb pool is on' if strict else ''))
                continue
            return ticket_pick(ticket, league, where, now, games), None
    return None, '; '.join(reasons) or 'no games today'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--now', help='UTC instant; default now')
    args = parser.parse_args(argv)
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    ctx = gates.Stores().as_of(now)
    where = state(ctx.first, ctx.latest)
    print(f"run {where['run']}, step {where['step']}, ${where['stake']} riding, ${where['banked']} banked; "
          f"{len(where['history'])} rungs played, "
          f"{len(where['climbs'])} climbs finished" + (f"; open: {where['open']['id']}" if where['open'] else ''))
    pick, reason = candidate(ctx, ctx.games, now)
    if pick:
        info = pick['ladder']
        print(f"next rung: {pick['title']} {pick['odds']:+d}: ${info['stake']} to ${info['payout']}; "
              f"a win banks ${info['bankThisWin']} and rides ${info['nextStake']}")
        for leg in pick['legs']:
            print(f"  {leg['title']} {leg['odds']:+d} (ours {100 * leg['chance']:.0f}%, the price {100 * leg['implied']:.0f}%)")
    else:
        print(f'no rung now: {reason}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
