"""The Kook'n 80/20 Climb: a $50-to-$1,000 bankroll ladder, one rung at a time. Stdlib only.

The owner's call (2026-09-26): "50 -> 1000 on 1-2 leg safe bets", with alternate lines. An automatic rung is a
two-leg ticket at one book, priced as a favorite (TARGET), built from safer player lines ("Bijan Robinson 50+
rushing yards") that our projection clears comfortably, one leg per game. A person may also supply exact, fresh
sportsbook quotes for alternate spreads or totals; those legs have to clear the same model-agreement and ticket
guards. After a win the
ladder banks 20% of the return and rides the other 80% on the next rung. A miss ends that climb but cannot take what
was banked. The climb reaches $1,000 when its bank plus the next stake reaches the goal; the next rung then starts a
new climb at $50. Money is whole dollars: a rung pays round(stake x the ticket's decimal price), the bank gets
round(return x 20%), and the remainder rides.

Like the easy parlay, a rung is never called value. Our player chances are tuned against main lines (and learning
found them too confident even there), so on easier lines they can say "clears comfortably", not "beats the price".
The market's own price carries most of the safety; our number has to agree with room to spare.

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
import sharp_odds
from sports_refresh import eastern_date

START, GOAL = 50, 1000              # dollars
BANK_RATE = 0.20                    # "Bank 20. Ride 80." (owner, 2026-09-28)
BOOKS = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}
SLUGS = {'DraftKings': 'dk', 'FanDuel': 'fd'}
MARKETS = ('recYds', 'rushYds', 'rec', 'passYds')     # lines a follower reads at a glance
LEG_PRICES = (-900, -180)           # safer favored legs; two around -400 is the preferred shape
MIN_CHANCE = 0.85                   # our projection's chance the player clears the easier line
MIN_GAP = 0.04                      # safety comes from the price; our number still has to agree
MAX_GAP = 0.18                      # and no further: a book that far off an easy line is a data or role problem, not a gift
MAIN_RATIO = (0.6, 1.6)             # the book's main line against our projection: outside this, the market is another one
TARGET = (-180, -130)               # enough protection without making the climb take forever (owner, 2026-10-02)
MANUAL_RAW_CHANCE = 0.72             # exact game alternates: the unshrunk model must still agree comfortably
LEAD = timedelta(minutes=90)        # a game this close to kickoff is left off
FRESH = timedelta(hours=12)         # prices older than this are not used
STAKE = parlay.STAKE                # the ticket's size in the desk's own terms; the ladder itself counts dollars
SOURCE = 'https://sharpapi.io/'


def rungs(first, latest):
    """Every published rung, oldest first, merged with its latest revision."""
    out = [dict(pick, **latest.get(key, {})) for key, pick in first.items() if pick.get('parlayType') == 'ladder']
    return sorted(out, key=lambda p: (str(p.get('publishedAt') or ''), str(p.get('id'))))


def played(rung):
    """A rung that counts: graded, still open, or pulled before its post. The owner counts every published ladder
    decision (2026-09-28), so a pulled ungraded rung stays open and blocks the next one until its result."""
    if rung.get('result'):
        return True
    if 'before its post went out' in str(rung.get('entryNote') or ''):
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
    for rung in rungs(first, latest):
        if not played(rung):
            continue
        info = rung.get('ladder') or {}
        result = rung.get('result')
        if not result:
            open_rung = rung
            continue
        item = {'id': rung['id'], 'run': info.get('run'), 'step': info.get('step'), 'stake': info.get('stake'),
                'payout': info.get('payout'), 'odds': rung.get('odds'), 'result': result,
                'settledAt': rung.get('settledAt')}
        if result == 'win':
            returned = int(info.get('payout') or stake)
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
            run, step, stake, banked = run + 1, 1, START, 0
        history.append(item)
    return {'run': run, 'step': step, 'stake': stake, 'open': open_rung, 'history': history, 'climbs': climbs,
            'banked': banked, 'saved': saved, 'bankPercent': int(BANK_RATE * 100),
            'ridePercent': 100 - int(BANK_RATE * 100), 'start': START, 'goal': GOAL}


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
                if not build_site.settled_role(athlete, game[side]['id'], ctx.appearances, ctx.established):
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
                    over, _, _ = pricing.chances(mean, sd, float(point))
                    implied = pricing.break_even(price)
                    if over < MIN_CHANCE or not MIN_GAP <= over - implied <= MAX_GAP:
                        continue
                    shown = ctx.names.get(athlete) or name
                    out.append({'id': f"ladder-{game['id']}-{athlete}-{stat}-{float(point):g}",
                                'title': f"{shown} {int(point + 0.5)}+ {pricing.WORDS[stat]}",
                                'gameId': game['id'], 'athleteId': athlete, 'player': shown, 'market': stat, 'direction': 'over',
                                'line': float(point), 'book': BOOKS[book_key], 'odds': price, 'chance': round(over, 3),
                                'implied': round(implied, 3), 'projection': round(mean, 1), 'kickoff': game['kickoff'],
                                'observedAt': seen, 'marketWindow': 'Full game',
                                'alternate': float(point) != float(main)})
    return out


def build(legs):
    """The rung: two legs from different games at one book, priced inside TARGET, with the best joint chance on our
    numbers (the higher price breaks a tie). None with a reason when no pair fits."""
    best = None
    for book in sorted({leg['book'] for leg in legs}):
        mine = [l for l in legs if l['book'] == book]
        for a, b in combinations(mine, 2):
            if a['gameId'] == b['gameId']:
                continue
            dec = parlay.decimal(a['odds']) * parlay.decimal(b['odds'])
            price = parlay.american(dec)
            if not TARGET[0] <= price <= TARGET[1]:
                continue
            key = (round(a['chance'] * b['chance'], 4), price)
            if best is None or key > best[0]:
                pair = sorted((a, b), key=lambda l: (l['kickoff'], l['title']))
                best = (key, {'book': book, 'legs': pair, 'odds': price, 'decimal': round(dec, 3),
                              'gameIds': [l['gameId'] for l in pair], 'quotedAt': min(l['observedAt'] for l in pair),
                              'firstKickoff': min(l['kickoff'] for l in pair), 'chance': key[0]})
    if not best:
        return None, f'no book has two games with easier lines our numbers clear comfortably that pay {TARGET[0]:+d} to {TARGET[1]:+d} together'
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
    chances = ' and '.join(f"{100 * l['chance']:.0f}%" for l in ticket['legs'])
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
            'edge': (f"For fun, not value: {len(ticket['legs'])} protected lines our model agrees with "
                     f"({chances} on the raw model numbers), at {ticket['book']}'s exact prices, multiplied to "
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
    reasons = []
    for league in ('NFL', 'CFB'):
        # College legs wait for the same thing college props do: player numbers calibrated against that league's lines
        # (and college has no injury feed to catch a benched player).
        if league in gates.OWN_CALIBRATION and not ((getattr(ctx, 'policy', None) or {}).get('calibration') or {}).get(f'{league}/prop'):
            reasons.append(f'{league}: player numbers wait for their own calibration')
            continue
        today = todays_games(games, now, league, exclude)
        if len(today) < 2:
            reasons.append(f'{league}: {len(today)} games left today')
            continue
        seen = confirmed_at()
        legs = [leg for g in today for leg in legs_for_game(g, ctx.prop_odds.get(g['id']), ctx, now, seen)]
        ticket, reason = build(legs)
        if not ticket:
            reasons.append(f'{league}: {reason}')
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
