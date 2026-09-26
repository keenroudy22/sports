"""The Kook'n Ladder: $50 to $1,000, one rung at a time. Stdlib only.

The owner's call (2026-09-26): "50 -> 1000 on 1-2 leg safe bets", with alternate lines. Each rung is a two-leg
ticket at one book, priced near even money (TARGET), built from easier player lines ("Bijan Robinson 50+ rushing
yards") that our projection clears comfortably, one leg per game. The whole bankroll rides: a win rolls the payout
into the next rung, a miss starts the ladder over at $50, and reaching $1,000 finishes the climb (the next rung starts
a new one). Money is whole dollars: a rung pays round(stake x the ticket's decimal price).

Like the easy parlay, a rung is never called value. Our player chances are tuned against main lines (and learning
found them too confident even there), so on easier lines they can say "clears comfortably", not "beats the price".
The market's own price carries most of the safety; our number has to agree with room to spare.

The ladder's state is never stored. state() reads it from the published rungs and their results, so it can not
drift from the record. One rung is open at a time and one rung is played a day (gates.ladder_one_rung); a rung
closed before its post went out never counts, and the day may try again. A rung with a void leg is settled by a
person (run.settle reports it), and the ladder waits for that.

Prices: SharpAPI's DraftKings and FanDuel alternate player lines in data/prop-odds (scripts/sharp_odds.py), no
credits, both leagues: pregame college player props are legal in Indiana (gates.INDIANA_BOOKS). A rung is built
only from a capture younger than FRESH. The ladder is kept apart from the record, in dollars, on the site and on X.

  python scripts/ladder.py [--now ISO]      where the ladder stands, and the rung the desk would build now
"""
import argparse
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
BOOKS = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}
SLUGS = {'DraftKings': 'dk', 'FanDuel': 'fd'}
MARKETS = ('recYds', 'rushYds', 'rec', 'passYds')     # lines a follower reads at a glance
LEG_PRICES = (-350, -150)           # a leg worth a rung: favored by the book, never a near-certainty
MIN_CHANCE = 0.80                   # our projection's chance the player clears the easier line
MIN_GAP = 0.08                      # our chance at least this far above the chance the price implies
MAX_GAP = 0.18                      # and no further: a book that far off an easy line is a data or role problem, not a gift
MAIN_RATIO = (0.6, 1.6)             # the book's main line against our projection: outside this, the market is another one
TARGET = (-130, 130)                # a rung pays about even money
LEAD = timedelta(minutes=90)        # a game this close to kickoff is left off
FRESH = timedelta(hours=12)         # prices older than this are not used
STAKE = parlay.STAKE                # the ticket's size in the desk's own terms; the ladder itself counts dollars
SOURCE = 'https://sharpapi.io/'


def rungs(first, latest):
    """Every published rung, oldest first, merged with its latest revision."""
    out = [dict(pick, **latest.get(key, {})) for key, pick in first.items() if pick.get('parlayType') == 'ladder']
    return sorted(out, key=lambda p: (str(p.get('publishedAt') or ''), str(p.get('id'))))


def played(rung):
    """A rung that was played: graded, or still open. A rung closed before it went out never counts."""
    if rung.get('result'):
        return True
    return not rung.get('entryNote') and (rung.get('status') or 'active') == 'active'


def state(first, latest):
    """Where the ladder stands, from the rungs themselves:
    {'run', 'step', 'stake', 'open', 'history', 'climbs', 'start', 'goal'}.

    A win rolls the payout into the next rung; reaching the goal finishes the climb and the next rung starts a new
    run at START; a loss starts a new run too; a push or a void keeps the stake and the step."""
    run, step, stake, open_rung = 1, 1, START, None
    history, climbs = [], []
    for rung in rungs(first, latest):
        if not played(rung):
            continue
        info = rung.get('ladder') or {}
        result = rung.get('result')
        if not result:
            open_rung = rung
            continue
        history.append({'id': rung['id'], 'run': info.get('run'), 'step': info.get('step'), 'stake': info.get('stake'),
                        'payout': info.get('payout'), 'odds': rung.get('odds'), 'result': result,
                        'settledAt': rung.get('settledAt')})
        if result == 'win':
            stake, step = int(info.get('payout') or stake), step + 1
            if stake >= GOAL:
                climbs.append({'run': run, 'steps': int(info.get('step') or step - 1), 'final': stake, 'id': rung['id']})
                run, step, stake = run + 1, 1, START
        elif result == 'loss':
            run, step, stake = run + 1, 1, START
    return {'run': run, 'step': step, 'stake': stake, 'open': open_rung, 'history': history, 'climbs': climbs,
            'start': START, 'goal': GOAL}


def payout(stake, odds):
    return int(round(stake * parlay.decimal(odds)))


def todays_games(games, now, league, exclude=()):
    """The league's games today (Eastern), far enough from kickoff to post a rung before them."""
    day = eastern_date(now)
    return [g for g in games.values() if g.get('league') == league and g.get('state', 'pre') == 'pre' and g['id'] not in set(exclude)
            and eastern_date(gates.when(g['kickoff'])) == day and gates.when(g['kickoff']) > now + LEAD]


def legs_for_game(game, record, ctx, now):
    """Every easier line in this game our projection clears comfortably, at a price worth a rung, from each book."""
    snapshot = ctx.snapshot(game['id'])
    if not snapshot or not record or now - gates.when(record['retrievedAt']) > FRESH:
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
                                'observedAt': record['retrievedAt'], 'marketWindow': 'Full game'})
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
                              'gameIds': [l['gameId'] for l in pair], 'quotedAt': max(l['observedAt'] for l in pair),
                              'firstKickoff': min(l['kickoff'] for l in pair), 'chance': key[0]})
    if not best:
        return None, f'no book has two games with easier lines our numbers clear comfortably that pay {TARGET[0]:+d} to {TARGET[1]:+d} together'
    return best[1], None


def candidate(ctx, games, now, exclude=()):
    """The next rung as a pick, or (None, reason). Games in `exclude` (the desk has a reason against them) are left off.
    NFL first, then college: a rung stays inside one league, as a report does."""
    where = state(ctx.first, ctx.latest)
    if where['open']:
        return None, f"{where['open']['id']} is still open; the next rung waits for its result"
    reasons = []
    for league in ('NFL', 'CFB'):
        today = todays_games(games, now, league, exclude)
        if len(today) < 2:
            reasons.append(f'{league}: {len(today)} games left today')
            continue
        legs = [leg for g in today for leg in legs_for_game(g, ctx.prop_odds.get(g['id']), ctx, now)]
        ticket, reason = build(legs)
        if not ticket:
            reasons.append(f'{league}: {reason}')
            continue
        first = games.get(ticket['gameIds'][0]) or {}
        day = eastern_date(now)
        stake = where['stake']
        info = {'run': where['run'], 'step': where['step'], 'stake': stake, 'payout': payout(stake, ticket['odds']),
                'start': START, 'goal': GOAL}
        chances = ' and '.join(f"{100 * l['chance']:.0f}%" for l in ticket['legs'])
        return {'id': f"{league}-{first.get('season', day.year)}-W{first.get('week', 0)}-ladder-{day:%m%d}-{SLUGS[ticket['book']]}",
                'title': f"Ladder step {info['step']}: 2 legs at {ticket['book']}", 'status': 'active', 'favorite': False,
                'parlayType': 'ladder', 'riskUnits': STAKE, 'ladder': info, 'legs': ticket['legs'], '_league': league,
                'correlation': 'One leg per game, so the book prices the ticket as the legs multiplied.',
                'gameIds': ticket['gameIds'], 'book': ticket['book'], 'odds': ticket['odds'], 'quotedAt': ticket['quotedAt'],
                'expiresAt': gates.stamp(min(gates.next_slot(now), gates.when(ticket['firstKickoff']))),
                'quoteType': 'capture', 'confidence': 1,
                'edge': (f"For fun, not value: two easier lines our projections clear comfortably ({chances} on our numbers, "
                         f"which are tuned for main lines), at {ticket['book']}'s own prices, multiplied to {ticket['odds']:+d}. "
                         f"The ladder's whole ${stake} rides to ${info['payout']}."),
                'cutoff': 'A ladder rung is not re-entered. It stands or falls as posted.',
                'sources': sorted({SOURCE} | {games[g]['source'] for g in ticket['gameIds'] if g in games and games[g].get('source')})}, None
    return None, '; '.join(reasons) or 'no games today'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--now', help='UTC instant; default now')
    args = parser.parse_args(argv)
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    ctx = gates.Stores().as_of(now)
    where = state(ctx.first, ctx.latest)
    print(f"run {where['run']}, step {where['step']}, ${where['stake']} riding; {len(where['history'])} rungs played, "
          f"{len(where['climbs'])} climbs finished" + (f"; open: {where['open']['id']}" if where['open'] else ''))
    pick, reason = candidate(ctx, ctx.games, now)
    if pick:
        print(f"next rung: {pick['title']} {pick['odds']:+d}: ${pick['ladder']['stake']} to ${pick['ladder']['payout']}")
        for leg in pick['legs']:
            print(f"  {leg['title']} {leg['odds']:+d} (ours {100 * leg['chance']:.0f}%, the price {100 * leg['implied']:.0f}%)")
    else:
        print(f'no rung now: {reason}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
