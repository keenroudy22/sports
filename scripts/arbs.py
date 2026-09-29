"""Private pregame arbitrage radar over the desk's already captured prices.

This never places a wager and never creates a public post. It accepts only exact two-way complements at the same
line, from different books, with recently updated prices. The scheduled desk sends qualifying results privately
through its existing ntfy topic; this module only reads stores and performs arithmetic.

Usage:
  python scripts/arbs.py
  python scripts/arbs.py boost +298 50 -195

The boost command explains both an equal-profit hedge and a no-loss free roll. Promo boosts are account-specific and
are not expected to appear in an odds feed, so their offered price and maximum stake must come from the owner.
"""
import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores

ROOT = Path(__file__).resolve().parents[1]
RECORD_FRESH = timedelta(minutes=15)
QUOTE_FRESH = timedelta(minutes=10)
MIN_ROI = 1.0
REFERENCE_STAKE = 100.0
MARKETS = {'passYds': 'passing yards', 'rushYds': 'rushing yards', 'recYds': 'receiving yards',
           'rec': 'receptions', 'car': 'carries', 'att': 'pass attempts', 'cmp': 'completions'}


def when(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def decimal(price):
    """American odds to total-return decimal odds."""
    price = int(price)
    if price == 0:
        raise ValueError('American odds cannot be zero')
    return 1 + (price / 100 if price > 0 else 100 / abs(price))


def allocation(first, second, total=REFERENCE_STAKE):
    """Rounded stakes whose returns are as equal as cents allow."""
    d1, d2 = decimal(first), decimal(second)
    implied = 1 / d1 + 1 / d2
    stake1 = round(total * (1 / d1) / implied, 2)
    stake2 = round(total - stake1, 2)
    returned = min(stake1 * d1, stake2 * d2)
    profit = returned - total
    return {'firstStake': stake1, 'secondStake': stake2, 'return': round(returned, 2),
            'profit': round(profit, 2), 'roi': round(100 * profit / total, 2), 'implied': implied}


def boost(primary_price, primary_stake, hedge_price):
    """Two useful hedges for an account-specific boost: equal profit, and break-even downside."""
    primary_stake = float(primary_stake)
    primary_return = primary_stake * decimal(primary_price)
    # Round the hedge upward: ordinary rounding can leave that outcome a fraction of a cent below the stated lock.
    equal_hedge = math.ceil(primary_return / decimal(hedge_price) * 100) / 100
    locked = primary_return - primary_stake - equal_hedge
    hedge_profit_per_dollar = decimal(hedge_price) - 1
    free_roll_hedge = primary_stake / hedge_profit_per_dollar
    free_roll_upside = primary_return - primary_stake - free_roll_hedge
    return {'primaryReturn': round(primary_return, 2), 'equalHedge': round(equal_hedge, 2),
            'lockedProfit': round(locked, 2), 'lockedRoi': round(100 * locked / (primary_stake + equal_hedge), 2),
            'freeRollHedge': round(free_roll_hedge, 2), 'freeRollDownside': 0.0,
            'freeRollUpside': round(free_roll_upside, 2)}


def fresh(value, now, limit):
    try:
        age = now - when(value)
        return -timedelta(minutes=1) <= age <= limit
    except (TypeError, ValueError):
        return False


def quote(book, entry, side, price, now):
    if not isinstance(price, (int, float)) or not fresh(entry.get('updatedAt'), now, QUOTE_FRESH):
        return None
    return {'bookKey': book, 'book': entry.get('title') or book, 'side': side, 'price': int(price),
            'updatedAt': entry['updatedAt']}


def opportunity(kind, game_id, label, line, first, second, retrieved, minimum=MIN_ROI):
    if not first or not second or first['bookKey'] == second['bookKey']:
        return None
    split = allocation(first['price'], second['price'])
    if split['roi'] < minimum:
        return None
    return {'kind': kind, 'gameId': game_id, 'label': label, 'line': line, 'first': first, 'second': second,
            'retrievedAt': retrieved, **split}


def best_pair(kind, game_id, label, line, firsts, seconds, retrieved, minimum):
    found = [hit for a in firsts for b in seconds
             if (hit := opportunity(kind, game_id, label, line, a, b, retrieved, minimum))]
    return max(found, key=lambda h: h['roi'], default=None)


def game_arbs(record, now, name=None, minimum=MIN_ROI):
    """Exact-line totals and spreads. Middles are intentionally excluded: both sides must be complementary."""
    if not fresh(record.get('retrievedAt'), now, RECORD_FRESH) or when(record['kickoff']) <= now:
        return []
    books, hits = record.get('books') or {}, []
    total_lines = sorted({b['total']['line'] for b in books.values() if b.get('total')})
    for line in total_lines:
        overs, unders = [], []
        for key, book in books.items():
            total = book.get('total') or {}
            if total.get('line') != line:
                continue
            if q := quote(key, book, f'over {line:g}', total.get('over'), now): overs.append(q)
            if q := quote(key, book, f'under {line:g}', total.get('under'), now): unders.append(q)
        if hit := best_pair('game total', record['gameId'], f'{name or record["gameId"]} total', line,
                            overs, unders, record['retrievedAt'], minimum):
            hits.append(hit)
    spread_lines = sorted({b['spread']['home'] for b in books.values() if b.get('spread')})
    for line in spread_lines:
        homes, aways = [], []
        for key, book in books.items():
            spread = book.get('spread') or {}
            if spread.get('home') != line:
                continue
            if q := quote(key, book, f'home {line:+g}', spread.get('homePrice'), now): homes.append(q)
            if q := quote(key, book, f'away {-line:+g}', spread.get('awayPrice'), now): aways.append(q)
        if hit := best_pair('game spread', record['gameId'], f'{name or record["gameId"]} spread', line,
                            homes, aways, record['retrievedAt'], minimum):
            hits.append(hit)
    return hits


def prop_arbs(record, now, name=None, minimum=MIN_ROI):
    """Player over/under pairs at the identical half-point line and market."""
    if not fresh(record.get('retrievedAt'), now, RECORD_FRESH) or when(record['kickoff']) <= now:
        return []
    groups = {}
    for key, book in (record.get('books') or {}).items():
        for market, players in ((book.get('markets') or {}).items()):
            for player, row in players.items():
                line = row.get('line')
                if not isinstance(line, (int, float)) or float(line) % 1 != .5:
                    continue
                group = groups.setdefault((market, player, line), {'over': [], 'under': []})
                for side in ('over', 'under'):
                    if q := quote(key, book, f'{side} {line:g}', row.get(side), now):
                        group[side].append(q)
    hits = []
    for (market, player, line), sides in groups.items():
        label = f'{player} {MARKETS.get(market, market)}'
        if name:
            label += f' ({name})'
        if hit := best_pair('player prop', record['gameId'], label, line, sides['over'], sides['under'],
                            record['retrievedAt'], minimum):
            hits.append(hit)
    return hits


def latest_records(folder):
    latest = {}
    for path in sorted(Path(folder).glob('*.jsonl')):
        for row in boxscores.read_store(path):
            latest[row['gameId']] = row
    return latest


def game_names(root=ROOT):
    try:
        slate = json.loads((Path(root) / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {g['id']: f"{g['away']['name']} at {g['home']['name']}" for g in slate.get('games', [])}


def scan(root=ROOT, now=None, minimum=None, allowed=None):
    now = now or datetime.now(timezone.utc)
    try:
        minimum = float(os.environ.get('KEENROUDY_ARB_MIN_ROI', MIN_ROI)) if minimum is None else float(minimum)
    except (TypeError, ValueError):
        minimum = MIN_ROI
    if allowed is None:
        setting = os.environ.get('KEENROUDY_ARB_BOOKS', '').strip()
        allowed = {b.strip().lower() for b in setting.split(',') if b.strip()} or None
    names, hits = game_names(root), []
    for row in latest_records(Path(root) / 'data' / 'odds').values():
        hits += game_arbs(row, now, names.get(row['gameId']), minimum)
    for row in latest_records(Path(root) / 'data' / 'prop-odds').values():
        hits += prop_arbs(row, now, names.get(row['gameId']), minimum)
    if allowed:
        hits = [h for h in hits if h['first']['bookKey'].lower() in allowed and h['second']['bookKey'].lower() in allowed]
    return sorted(hits, key=lambda h: -h['roi'])


def message(hit):
    return (f"VERIFY BOTH BEFORE PLACING\n{hit['label']}\n"
            f"{hit['first']['side']} {hit['first']['price']:+d} at {hit['first']['book']} · ${hit['firstStake']:.2f}\n"
            f"{hit['second']['side']} {hit['second']['price']:+d} at {hit['second']['book']} · ${hit['secondStake']:.2f}\n"
            f"$100.00 in → at least ${hit['return']:.2f} · ${hit['profit']:.2f} ({hit['roi']:.2f}%)\n"
            "Confirm the same event, market, line, limits and settlement rules in both apps first.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command')
    boost_parser = sub.add_parser('boost')
    boost_parser.add_argument('primary_price', type=int)
    boost_parser.add_argument('primary_stake', type=float)
    boost_parser.add_argument('hedge_price', type=int)
    args = parser.parse_args(argv)
    if args.command == 'boost':
        print(json.dumps(boost(args.primary_price, args.primary_stake, args.hedge_price), indent=2))
        return 0
    hits = scan()
    if not hits:
        print('No fresh exact-line arbitrage in the captured prices.')
    for hit in hits:
        print(message(hit), end='\n\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
