"""What the market says about a game, as evidence beside our number and never inside it. Stdlib only.

If the market were blended into the score model, the model could no longer be graded against the
market: closing-line value, the record against the close and the whole scoreboard would be grading a
number that contains the thing it is graded against. So the score model stays market-free and this
module builds the market read as a separate, visible layer:

  open_to_now     the book's opening number, the current number, and the size and direction of the move
  disagreement    which books differ on the spread and the total, and by how much
  gap_percentile  where our gap against the line sits among the model's historical gaps, and how often
                  gaps at least that large beat the close (a large gap is more often our error)
  read            all of the above for one game, plus any sourced events the research run attaches

  python scripts/market_read.py GAME_ID
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import features

ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / 'data' / 'model' / 'backtest-v2.json'


def open_to_now(game):
    """The book's opening and current spread (home side) and total, with the move since open."""
    m = build_site.market(game)
    if not m:
        return None
    out = {'book': m.get('book'), 'asOf': m.get('retrievedAt')}
    for key, opened, now in (('spread', m.get('spreadOpen'), m.get('spread')), ('total', m.get('totalOpen'), m.get('total'))):
        block = {'open': opened, 'now': now, 'move': None}
        if opened is not None and now is not None:
            block['move'] = round(now - opened, 1)
            if key == 'spread':
                block['toward'] = 'home' if now < opened else 'away' if now > opened else None
            else:
                block['toward'] = 'over' if now > opened else 'under' if now < opened else None
        out[key] = block
    return out


def disagreement(record):
    """Per book, the home spread and the total from a multi-book capture, with the range and the median."""
    if not record or not record.get('books'):
        return None
    out = {'asOf': record.get('retrievedAt')}
    for key, pick in (('spread', lambda b: (b.get('spread') or {}).get('home')), ('total', lambda b: (b.get('total') or {}).get('line'))):
        lines = {build_site.BOOK_NAMES.get(book, book): pick(entry) for book, entry in record['books'].items() if pick(entry) is not None}
        if not lines:
            continue
        values = sorted(lines.values())
        median = values[len(values) // 2] if len(values) % 2 else (values[len(values) // 2 - 1] + values[len(values) // 2]) / 2
        out[key] = {'books': dict(sorted(lines.items())), 'min': values[0], 'max': values[-1],
                    'range': round(values[-1] - values[0], 1), 'consensus': median}
    return out


def load_rows(path=BACKTEST):
    if not Path(path).exists():
        return []
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    return payload.get('rows') or [] if isinstance(payload, dict) else payload


def gap_percentile(rows, league, market, gap):
    """Where |gap| sits among the model's walk-forward gaps against the close for a league and market.

    market is 'margin' or 'total'. Returns the percentile of our gap, the sample, and the record against
    the close of the side the model took in games where its gap was at least this large: the evidence the
    calibration rests on, shown rather than assumed.
    """
    key, verdict = ('closeMargin', 'side') if market == 'margin' else ('closeTotal', 'ou')
    gaps = []
    for row in rows:
        if row.get('league') != league or row.get(key) is None or row.get(market) is None:
            continue
        gaps.append((abs(row[market] - row[key]), row.get(verdict)))
    if not gaps or gap is None:
        return None
    size = abs(gap)
    below = sum(1 for g, _ in gaps if g < size)
    at_least = [v for g, v in gaps if g >= size]
    return {'gap': round(gap, 1), 'percentile': round(100 * below / len(gaps)), 'n': len(gaps),
            'gapsThisLargeVsClose': [at_least.count('W'), at_least.count('L')]}


def read(game, snapshot=None, record=None, rows=None, events=()):
    """The market read for one game: moves, disagreement, our gap in context, and sourced events."""
    rows = rows if rows is not None else load_rows()
    out = {'gameId': game['id'], 'moves': open_to_now(game), 'books': disagreement(record), 'ourGap': None,
           'events': [dict(e) for e in events]}
    m = build_site.market(game) or {}
    if snapshot and m:
        gap = {}
        if m.get('spread') is not None:
            our_margin, close_margin = snapshot['margin'], -m['spread']
            gap['margin'] = gap_percentile(rows, game['league'], 'margin', our_margin - close_margin)
            if gap['margin']:
                gap['margin']['ours'], gap['margin']['line'] = round(our_margin, 1), close_margin
        if m.get('total') is not None:
            gap['total'] = gap_percentile(rows, game['league'], 'total', snapshot['total'] - m['total'])
            if gap['total']:
                gap['total']['ours'], gap['total']['line'] = round(snapshot['total'], 1), m['total']
        out['ourGap'] = gap or None
    return out


def sentences(block):
    """The read in plain words, for a report or a card. Every number comes from the block."""
    parts = []
    moves = block.get('moves') or {}
    for key in ('spread', 'total'):
        m = moves.get(key) or {}
        if m.get('move') is not None and m['move'] != 0:
            parts.append(f"The {key} opened {m['open']:+g} and is {m['now']:+g} at {moves.get('book')}, a move of {abs(m['move']):g} toward the {m['toward']}."
                         if key == 'spread' else
                         f"The total opened {m['open']:g} and is {m['now']:g} at {moves.get('book')}, {abs(m['move']):g} toward the {m['toward']}.")
    books = block.get('books') or {}
    for key in ('spread', 'total'):
        b = books.get(key)
        if b and b['range'] > 0:
            parts.append(f"{len(b['books'])} books span {b['min']:g} to {b['max']:g} on the {key}; the middle is {b['consensus']:g}.")
    gap = block.get('ourGap') or {}
    for key, word in (('margin', 'spread'), ('total', 'total')):
        g = gap.get(key)
        if g:
            w, l = g['gapsThisLargeVsClose']
            parts.append(f"Our {word} gap of {abs(g['gap']):g} points is at the {g['percentile']}th percentile of the model's gaps; "
                         f"gaps this large went {w}-{l} against the close in {g['n']} graded games.")
    return ' '.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('game_id')
    args = parser.parse_args(argv)
    slate = json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
    game = next((g for g in slate.get('games', []) if g['id'] == args.game_id), None)
    if not game:
        sys.exit(f'{args.game_id} is not in the slate')
    import desk
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    snapshot = desk.current(desk.snapshots().get(game['id'], []), game['kickoff'], now)
    record = (build_site.load_store('odds').get(game['id']) or [None])[-1]
    block = read(game, snapshot, record)
    print(json.dumps(block, indent=1))
    print('\n' + (sentences(block) or 'Nothing to say: no market for this game yet.'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
