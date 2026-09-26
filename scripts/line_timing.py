"""What waiting costs: every play's number and price when the desk published it, when its post went out on X (or
would have, at the posting rule's time), and in the last capture before kickoff, at the play's own book. Stdlib only.

  python scripts/line_timing.py [--since YYYY-MM-DD] [--json PATH]

The owner asked (2026-09-25) whether posting around noon still gets followers the numbers the desk liked. The desk
publishes a play when its number beats the line, often at 6:45 or 8:30 AM, and the site shows it right away; X gets
it around noon. This measures how the number moved in between, from the odds captures the desk already keeps
(data/odds, data/prop-odds). A capture is a snapshot, so "at post time" means the latest capture before it, and its
time is shown.

The rule it serves: if on most measured plays the post-time price is worse than at publish by at least half a point
or, at the same number, ten cents, posts move earlier (buffer_post.POST_AT); otherwise noon stays.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buffer_post
import gates
import x_post
from sports_refresh import eastern_date

WORSE_POINTS = 0.5          # half a point on the number
WORSE_CENTS = 10            # or ten cents on the price at the same number
CLOSE_LEAD = timedelta(minutes=1)


def cents(odds):
    """A price on a line where -110 and +110 are 20 cents apart: -110 is -10, +110 is +10, -105 and +105 are 10 apart."""
    odds = int(odds)
    return odds + 100 if odds < 0 else odds - 100


def moved_against(pick, before, after):
    """(points, cents): how far the number moved against the play (positive is worse: a higher line for an over, a
    lower one for an under or a side), and at the same number how many cents the price moved against it."""
    move = float(after[0]) - float(before[0])
    points = move if gates.side_of(pick) == 'over' else -move
    same = abs(move) < 1e-9
    return round(points, 1), (cents(before[1]) - cents(after[1])) if same else None


def verdict(points, cents_off):
    if points >= WORSE_POINTS or (points == 0 and (cents_off or 0) >= WORSE_CENTS):
        return 'worse'
    if points <= -WORSE_POINTS or (points == 0 and (cents_off or 0) <= -WORSE_CENTS):
        return 'better'
    return 'about the same'


def post_time(entry, kickoff):
    """When the play went out (sentAt), was due (dueAt), or would have gone out under the posting rule."""
    for key, kind in (('sentAt', 'posted'), ('dueAt', 'scheduled')):
        if entry and entry.get(key):
            return gates.when(entry[key]), kind
    day = eastern_date(kickoff)
    noon = datetime(day.year, day.month, day.day, *buffer_post.POST_AT, tzinfo=gates.EASTERN).astimezone(timezone.utc)
    return max(min(noon, kickoff - buffer_post.EARLY_LEAD), buffer_post.window_open(day)), 'rule'


def at_book(pick, ctx):
    """(line, odds, capturedAt) at the play's own book in the latest capture as of ctx.now, or None."""
    game_id = (pick.get('gameIds') or [None])[0]
    record = (ctx.prop_odds if pick.get('athleteId') else ctx.odds).get(game_id) or {}
    for book, line, odds in gates.quotes_for(dict(pick, _quotes=None), ctx, priced_only=True):
        if book == pick.get('book') and isinstance(line, (int, float)):
            return float(line), int(odds), record.get('retrievedAt')
    return None


def measure(stores, now, since=None, log_book=None):
    """One row per single play published since `since` (an Eastern date): the published number, the number at post
    time and at the close, at the play's own book, with how each moved against the play."""
    ctx = stores.as_of(now)
    log_book = log_book if log_book is not None else x_post.load_log()
    posts = {}
    for entry in log_book.get('posts', []):
        if entry.get('kind') == 'buffer:play' and not entry.get('cancelledAt'):
            posts[entry['id']] = entry
    rows = []
    for key, pick in sorted(ctx.first.items(), key=lambda item: item[1].get('publishedAt') or ''):
        if pick.get('historicalImport') or pick.get('legs') or pick.get('parlayType') or not pick.get('publishedAt'):
            continue
        if not isinstance(pick.get('line'), (int, float)) or not isinstance(pick.get('odds'), (int, float)):
            continue
        published = gates.when(pick['publishedAt'])
        if since and eastern_date(published).isoformat() < since:
            continue
        game = ctx.games.get((pick.get('gameIds') or [None])[0])
        if not game:
            continue
        kickoff = gates.when(game['kickoff'])
        posted, kind = post_time(posts.get(key), kickoff)
        row = {'id': key, 'title': pick.get('title'), 'league': pick.get('league') or key.split('-')[0], 'book': pick.get('book'),
               'publishedAt': gates.stamp(published), 'postAt': gates.stamp(posted), 'postKind': kind,
               'published': [float(pick['line']), int(pick['odds'])]}
        if published < posted <= now and posted < kickoff:              # a post still to come is not measured
            quote = at_book(pick, stores.as_of(posted))
            if quote and quote[2] and gates.when(quote[2]) > published:      # a capture taken after the play went up
                points, cents_off = moved_against(pick, row['published'], quote)
                row['atPost'] = {'line': quote[0], 'odds': quote[1], 'capturedAt': quote[2], 'points': points, 'cents': cents_off,
                                 'verdict': verdict(points, cents_off)}
        close = at_book(pick, stores.as_of(kickoff - CLOSE_LEAD)) if kickoff <= now else None
        if close:
            points, cents_off = moved_against(pick, row['published'], close)
            row['atClose'] = {'line': close[0], 'odds': close[1], 'capturedAt': close[2], 'points': points, 'cents': cents_off,
                              'verdict': verdict(points, cents_off)}
        rows.append(row)
    return rows


def summary(rows):
    """The counts the rule reads, and what it says."""
    measured = [r for r in rows if r.get('atPost')]
    count = {v: sum(1 for r in measured if r['atPost']['verdict'] == v) for v in ('worse', 'about the same', 'better')}
    points = [r['atPost']['points'] for r in measured]
    out = {'plays': len(rows), 'measured': len(measured), **count,
           'averagePointsAgainst': round(sum(points) / len(points), 2) if points else None}
    if not measured:
        out['says'] = 'Nothing to measure yet: no capture was taken between a play going up and its post.'
    elif count['worse'] * 2 > len(measured):
        out['says'] = (f"Waiting is costing us: {count['worse']} of {len(measured)} plays were worse by the time they posted. "
                       f"Post earlier (about 10 AM).")
    else:
        out['says'] = (f"Noon is fine: {count['worse']} of {len(measured)} plays were worse by the time they posted, "
                       f"{count['better']} better, the rest about the same.")
    return out


def show(row):
    def fmt(line, odds):
        return f"{line:g} {int(odds):+d}"
    parts = [f"{row['publishedAt'][5:16]}  {row['title']}  ({row['book']})", f"published {fmt(*row['published'])}"]
    if row.get('atPost'):
        p = row['atPost']
        parts.append(f"at post ({row['postKind']}, capture {p['capturedAt'][11:16]}Z) {fmt(p['line'], p['odds'])}: {p['verdict']}")
    elif gates.when(row['postAt']) > datetime.now(timezone.utc):
        parts.append(f"posts {gates.when(row['postAt']).astimezone(gates.EASTERN):%a %-I:%M %p} ET: not measured yet")
    else:
        parts.append(f"at post ({row['postKind']}): no capture in between")
    if row.get('atClose'):
        parts.append(f"at close {fmt(row['atClose']['line'], row['atClose']['odds'])}: {row['atClose']['verdict']}")
    return '\n    '.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--since', help='Eastern date, inclusive (default: all)')
    parser.add_argument('--json', help='also write the rows and the summary here')
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    rows = measure(gates.Stores(), now, args.since)
    for row in rows:
        print(show(row))
    result = summary(rows)
    print(f"\n{result['measured']} of {result['plays']} plays measured: {result['worse']} worse at post time, "
          f"{result['about the same']} about the same, {result['better']} better. {result['says']}")
    if args.json:
        Path(args.json).write_text(json.dumps({'rows': rows, 'summary': result}, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
