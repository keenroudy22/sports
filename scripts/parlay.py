"""A longshot parlay for the day, assembled from the board's priced lines at one book.

One leg per game, three to five legs, every leg priced at the same book at the number its
read was graded at, so the combined price is that book's own parlay arithmetic: decimal
odds multiplied. The legs are the lines our number likes most. The ticket's chance is the
product of the legs' calibrated chances, which treats the games as independent; that is
why the legs come from different games. Its stake is a quarter unit and it is tracked
apart from the straight picks. A fun ticket with a high miss rate, not a favorite.

Usage: python scripts/parlay.py [--target 500] [--day YYYY-MM-DD] [--league NFL|CFB]
Reads site/data/app/lines.json, so build the site first. Prints the ticket as JSON, or a
line saying why there is none.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features
import pricing
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / 'site' / 'data' / 'app' / 'lines.json'
MIN_CHANCE = 0.52          # a game line's calibrated chance: the side our number takes, with a little room
MIN_LEGS, MAX_LEGS = 3, 5
LEAD = timedelta(minutes=30)
STAKE = 0.25


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


def build(rows, now, day=None, target=500, league=None, exclude=()):
    """The best ticket on the board for the day: None with a reason when there is none.

    exclude: game ids the research run has a sourced reason to leave off, such as weather.
    """
    day = day or eastern_date(now).isoformat()
    picks = [r for r in rows if eligible(r, now, day, league) and r['gameId'] not in set(exclude)]
    best_per_game = {}
    for row in sorted(picks, key=lambda r: -r['grade']['chance']):
        best_per_game.setdefault(row['gameId'], row)
    candidates = list(best_per_game.values())
    if len(candidates) < MIN_LEGS:
        return None, f'only {len(candidates)} games with a line our number likes on {day}; a ticket needs {MIN_LEGS}'
    tickets = []
    books = {q['book'] for row in candidates for q in row.get('books') or []} | {row['book'] for row in candidates}
    for book in books:
        legs = []
        for row in candidates:
            quotes = row.get('books') or [{'book': row['book'], 'line': row['line'], 'odds': row['odds']}]
            quote = next((q for q in quotes if q['book'] == book and q['line'] == row['line'] and q.get('odds') is not None), None)
            if quote:   # a leg is taken only at the number its read was graded at
                legs.append({'id': row['id'], 'title': retitle(row, quote['line']), 'gameId': row['gameId'],
                             'market': row['market'], 'side': row.get('direction') or row.get('side'),
                             'line': quote['line'], 'odds': quote['odds'], 'chance': row['grade']['chance'],
                             'kickoff': row['kickoff'], 'observedAt': row.get('observedAt'), 'marketWindow': 'Full game'})
        legs.sort(key=lambda l: -l['chance'])
        for count in range(MIN_LEGS, min(MAX_LEGS, len(legs)) + 1):
            chosen = legs[:count]
            dec = 1.0
            fair = 1.0
            for leg in chosen:
                dec *= decimal(leg['odds'])
                fair *= leg['chance']
            price = american(dec)
            tickets.append({'book': book, 'legs': chosen, 'odds': price, 'decimal': round(dec, 3), 'fairChance': round(fair, 4),
                            'breakEven': round(1 / dec, 4), 'evPerUnit': round(fair * (dec - 1) - (1 - fair), 3),
                            'riskUnits': STAKE, 'gameIds': [l['gameId'] for l in chosen],
                            'quotedAt': max(l['observedAt'] or '' for l in chosen), 'firstKickoff': min(l['kickoff'] for l in chosen)})
    if not tickets:
        return None, 'no book carries three of those lines at the graded numbers'
    reaching = [t for t in tickets if t['odds'] >= target]
    pool = reaching or tickets
    # The best expected value at the fewest legs that reach the target; failing the target, the longest price.
    pool.sort(key=lambda t: (-t['evPerUnit'], len(t['legs'])) if reaching else (-t['odds'],))
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
    rows = json.loads(LINES.read_text(encoding='utf-8'))['lines']
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
