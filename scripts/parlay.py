"""A longshot parlay for the day, assembled from priced board lines and vetted feed alternates at one book.

One leg per game, three to five legs, every leg priced at the same book at the number its
read was graded at, so the combined price is that book's own parlay arithmetic: decimal
odds multiplied. An alternate comes only from its own market ladder and competes with the board's main lines; straight
plays are unchanged. The legs are the lines our number likes most. The ticket's chance is the
product of the legs' calibrated chances, which treats the games as independent; that is
why the legs come from different games. Its stake is a quarter unit and it is tracked
apart from the straight picks. A fun ticket with a high miss rate, not a favorite.

Usage: python scripts/parlay.py [--target 500] [--day YYYY-MM-DD] [--league NFL|CFB]
Reads the built line manifest and league shards, so build the site first. Prints the ticket as JSON, or a
line saying why there is none.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from itertools import combinations, product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features
import line_payload
import pricing
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / 'site' / 'data' / 'app' / 'lines.json'
MIN_CHANCE = 0.52          # a game line's calibrated chance: the side our number takes, with a little room
MIN_LEGS, MAX_LEGS = 3, 5
LEAD = timedelta(minutes=30)
STAKE = 0.25
ALT_GAME_POOL = 10          # bound the alternate search on a large college slate


def decimal(odds):
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def american(dec):
    return int(round((dec - 1) * 100)) if dec >= 2 else -int(round(100 / (dec - 1)))


def eligible(row, now, day, league=None):
    """A priced, graded line on the day, not about to start, that our number likes enough to carry."""
    grade = row.get('grade') or {}
    if row.get('state') != 'open' or not isinstance(row.get('odds'), (int, float)) or grade.get('chance') is None:
        return False
    if league and row.get('league') != league:
        return False
    kickoff = features.when(row['kickoff'])
    if kickoff <= now + LEAD or eastern_date(kickoff).isoformat() != day:
        return False
    if row.get('athleteId'):
        return grade.get('tier') == 'lean'          # props: 60%+ on three or more games, never thinner
    return grade['chance'] >= MIN_CHANCE            # a fun ticket rides the model's side; the price says how far


def retitle(row, line):
    """The row's title at another book's number."""
    return re.sub(re.escape(f"{row['line']:g}"), f'{line:g}', row['title'], count=1)


def extra_eligible(leg, now, day, exclude):
    """A feed-priced alternate safe to mix into a fun ticket.

    The caller supplies only rungs accepted by the SharpAPI ladder reader; these checks keep the parlay boundary
    strict too: full-game, half-point, fresh enough to post, and never a made-up price.
    """
    return leg.get('alternate') is True and leg.get('gameId') not in set(exclude) \
        and leg.get('marketWindow') == 'Full game' and isinstance(leg.get('line'), (int, float)) \
        and float(leg['line']) == int(leg['line']) + 0.5 and isinstance(leg.get('odds'), (int, float)) \
        and isinstance(leg.get('chance'), (int, float)) and 0 < leg['chance'] < 1 \
        and bool(leg.get('book')) and bool(leg.get('kickoff')) \
        and features.when(leg['kickoff']) > now + LEAD and eastern_date(features.when(leg['kickoff'])).isoformat() == day


def priced_ticket(book, legs):
    """Price one same-book, one-leg-per-game combination."""
    chosen = sorted(legs, key=lambda l: (l['kickoff'], l['title']))
    dec = 1.0
    fair = 1.0
    for leg in chosen:
        dec *= decimal(leg['odds'])
        fair *= leg['chance']
    price = american(dec)
    return {'book': book, 'legs': chosen, 'odds': price, 'decimal': round(dec, 3), 'fairChance': round(fair, 4),
            'breakEven': round(1 / dec, 4), 'evPerUnit': round(fair * (dec - 1) - (1 - fair), 3),
            'riskUnits': STAKE, 'gameIds': [l['gameId'] for l in chosen],
            'quotedAt': min(l.get('observedAt') or '' for l in chosen),
            'priceEstimated': True,
            'firstKickoff': min(l['kickoff'] for l in chosen)}


def build(rows, now, day=None, target=500, league=None, exclude=(), extra_legs=(), max_legs=MAX_LEGS, price_range=None):
    """The best ticket on the board for the day: None with a reason when there is none.

    exclude: game ids the research run has a sourced reason to leave off, such as weather.
    extra_legs: already-vetted, feed-priced alternate player lines. They may mix with the board, but a ticket still
    has one book and at most one leg from any game.
    max_legs, price_range: a narrower shape (the direction rules' shorter fun tickets); never wider than the default.
    """
    max_legs = min(max(int(max_legs), MIN_LEGS), MAX_LEGS)
    day = day or eastern_date(now).isoformat()
    picks = [r for r in rows if eligible(r, now, day, league) and r['gameId'] not in set(exclude)]
    best_per_game = {}
    for row in sorted(picks, key=lambda r: -r['grade']['chance']):
        best_per_game.setdefault(row['gameId'], row)
    candidates = list(best_per_game.values())
    extras = [dict(leg) for leg in extra_legs if extra_eligible(leg, now, day, exclude)]
    available_games = {r['gameId'] for r in candidates} | {l['gameId'] for l in extras}
    if len(available_games) < MIN_LEGS:
        return None, f'only {len(available_games)} games with a line our number likes on {day}; a ticket needs {MIN_LEGS}'
    tickets = []
    books = ({q['book'] for row in candidates for q in row.get('books') or []} | {row['book'] for row in candidates}
             | {leg['book'] for leg in extras})
    for book in books:
        board = []
        for row in candidates:
            quotes = row.get('books') or [{'book': row['book'], 'line': row['line'], 'odds': row['odds']}]
            quote = next((q for q in quotes if q['book'] == book and q['line'] == row['line'] and q.get('odds') is not None), None)
            if quote:   # a leg is taken only at the number its read was graded at
                board.append({'id': row['id'], 'title': retitle(row, quote['line']), 'gameId': row['gameId'],
                              'market': row['market'], 'athleteId': row.get('athleteId'), 'side': row.get('direction') or row.get('side'),
                              'line': quote['line'], 'odds': quote['odds'], 'book': book, 'chance': row['grade']['chance'],
                              'kickoff': row['kickoff'], 'observedAt': row.get('observedAt'), 'marketWindow': 'Full game',
                              'alternate': False})
        board.sort(key=lambda l: -l['chance'])
        # Preserve the board-only candidates exactly; alternates are additional choices, not a new requirement.
        for count in range(MIN_LEGS, min(max_legs, len(board)) + 1):
            tickets.append(priced_ticket(book, board[:count]))

        # Search a bounded set of the strongest games. Each game contributes at most its best board leg and best
        # alternate, which keeps a full college slate deterministic and small while allowing genuinely mixed tickets.
        by_game = {}
        for leg in board:
            by_game.setdefault(leg['gameId'], {})['board'] = leg
        for leg in (l for l in extras if l['book'] == book):
            choices = by_game.setdefault(leg['gameId'], {})
            old = choices.get('alternate')
            edge = leg['chance'] - pricing.break_even(int(leg['odds']))
            old_edge = old['chance'] - pricing.break_even(int(old['odds'])) if old else -1
            if old is None or (edge, leg['chance']) > (old_edge, old['chance']):
                choices['alternate'] = leg
        groups = sorted(by_game.values(), key=lambda choices: -max(l['chance'] for l in choices.values()))[:ALT_GAME_POOL]
        for count in range(MIN_LEGS, min(max_legs, len(groups)) + 1):
            for selected in combinations(groups, count):
                for chosen in product(*(tuple(group.values()) for group in selected)):
                    if any(l.get('alternate') for l in chosen):
                        tickets.append(priced_ticket(book, chosen))
    if not tickets:
        return None, 'no book carries three of those lines at the graded numbers'
    if price_range:
        tickets = [t for t in tickets if price_range[0] <= t['odds'] <= price_range[1]]
        if not tickets:
            return None, f'no {MIN_LEGS}-{max_legs} leg ticket prices {price_range[0]:+d} to {price_range[1]:+d}'
    reaching = [t for t in tickets if t['odds'] >= target]
    pool = reaching or tickets
    # The best expected value at the fewest legs that reach the target; failing the target, the longest price.
    if reaching:
        pool.sort(key=lambda t: (-t['evPerUnit'], len(t['legs'])))
    else:
        pool.sort(key=lambda t: (-t['odds'],))
    ticket = pool[0]
    ticket['reachedTarget'] = bool(reaching)
    return ticket, None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--target', type=int, default=500, help='combined American price to reach (default +500)')
    parser.add_argument('--day', help='Eastern date, default today')
    parser.add_argument('--league', choices=('NFL', 'CFB'))
    parser.add_argument('--exclude', nargs='*', default=(), metavar='GAME', help='game ids with a sourced reason against them')
    args = parser.parse_args()
    rows = line_payload.load(LINES)
    ticket, reason = build(rows, datetime.now(timezone.utc), args.day, args.target, args.league, args.exclude)
    if ticket is None:
        print(f'No ticket: {reason}')
        return
    print(json.dumps(ticket, indent=1))
    print(f"\n{len(ticket['legs'])} legs at {ticket['book']}: {ticket['odds']:+d} (decimal {ticket['decimal']}); "
          f"our chance {100 * ticket['fairChance']:.1f}% against {100 * ticket['breakEven']:.1f}% break-even, "
          f"{ticket['evPerUnit']:+.3f}u per unit staked; stake {STAKE}u", file=sys.stderr)


if __name__ == '__main__':
    main()
