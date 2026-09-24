"""Receipts: what the plays posted to @keenkooks did, one post the morning after each game day and one on
Wednesday for the week. Stdlib only.

The desk posts plays only, and the brand is that every one of them is graded in public, win or lose. So every
morning after a game day, once every play that went out on X is settled, the desk posts the receipt: each play
with its result, the day's record and units, in the same card frame as the plays. On Wednesday morning the
week's receipt sums up the seven days before it by kind. Together with the plays that makes a post every day
of the season.

Only plays that actually went out count: `buffer:play` entries in data/x-posted.json with a `sentAt`, not
cancelled and not deleted. Records and units follow site/core.js exactly (x_post.summarize): one unit a straight
play, riskUnits for a parlay, push and void score zero.

  python scripts/receipts.py [--now ISO]      print the receipts that are ready and their text
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates
import pick_card
import x_post
from sports_refresh import eastern_date

MORNING = (9, 0)                  # Eastern: when a receipt posts
LATEST = (20, 0)                  # Eastern, the day after: a receipt not scheduled by then is stale and skipped
WEEKDAY = 2                       # Wednesday: the week's receipt
MARKS = {'win': '✅', 'loss': '❌', 'push': '➖', 'void': '➖'}
KIND_NAMES = {'player': 'Player props', 'team': 'Team props', 'parlay': 'Parlays'}


def served(log_book):
    """Ids of the plays that went out on X: sent through Buffer, or posted by hand before the desk posted (the
    two seeded 2026-09-19 plays count; the book is every play we posted, win or lose). A cancelled or deleted
    post was never served."""
    out = set()
    for p in log_book.get('posts', []):
        if p.get('cancelledAt') or p.get('deletedAt'):
            continue
        if (p.get('kind') == 'buffer:play' and p.get('sentAt')) or (p.get('kind') == 'pick' and p.get('postedAt')):
            out.add(p['id'])
    return out


def game_day(pick, games):
    """The Eastern date of a play's first kickoff: the day it was served."""
    starts = sorted(games[g]['kickoff'] for g in (pick.get('gameIds') or []) if g in games)
    return eastern_date(gates.when(starts[0])) if starts else None


def label(pick, games=None):
    """A play as its post and card named it: schools by name, over and under as the post says them."""
    if pick_card.play_kind(pick) == 'parlay':
        return f"{len(pick.get('legs') or [])}-leg parlay"
    return pick_card.display_title(pick, (games or {}).get((pick.get('gameIds') or [None])[0]))


def record_text(summary):
    text = f"{summary['win']}-{summary['loss']}" + (f"-{summary['push']}" if summary['push'] else '')
    return f"{text} · {summary['units']:+.2f}u"


def morning(day):
    return datetime(day.year, day.month, day.day, MORNING[0], MORNING[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)


def plays_between(first, latest, games, ids, start, end):
    """Served plays whose game day falls in [start, end], merged with their latest revision."""
    rows = []
    for key in ids:
        if key not in first:
            continue
        pick = dict(first[key], **latest.get(key, {}))
        day = game_day(pick, games)
        if day and start <= day <= end:
            rows.append(pick)
    order = {'player': 0, 'team': 1, 'parlay': 2}           # the order the plays posted in
    return sorted(rows, key=lambda p: (game_day(p, games), order[pick_card.play_kind(p)], str(p.get('title'))))


def settled(rows):
    return bool(rows) and all(r.get('result') in MARKS for r in rows)


def leagues(rows):
    found = {str(r.get('id', '')).split('-')[0] for r in rows}
    return ' '.join(x_post.TAGS[l] for l in ('NFL', 'CFB') if l in found)


def fit(lines, head, tail, head_sep='\n\n'):
    """Drop rows from the end until the post fits, saying how many were left off."""
    rows = list(lines)
    while True:
        more = len(lines) - len(rows)
        body = rows + ([f'and {more} more on the site'] if more else [])
        text = head_sep.join(part for part in (head, '\n'.join(body)) if part)
        text = '\n\n'.join(part for part in (text, tail) if part)
        if x_post.tweet_length(text) <= x_post.LIMIT or not rows:
            return text
        rows.pop()


def day_receipt(day, first, latest, games, ids):
    rows = plays_between(first, latest, games, ids, day, day)
    if not settled(rows):
        return None
    summary = x_post.summarize(rows)
    name = f'{day:%A}'
    head = f"🍳 RECEIPTS · {name.upper()}\n{record_text(summary)}"
    tail = 'Graded in public, win or lose.\n' + leagues(rows)
    text = fit([f"{MARKS[r['result']]} {label(r, games)}" for r in rows], head, tail.strip())
    return {'key': f'receipt:day:{day.isoformat()}', 'card': f'receipt-day-{day.isoformat()}', 'kind': 'receipt',
            'title': record_text(summary), 'label': 'YESTERDAY’S PLATES', 'when': f'{day:%A, %b %-d}',
            'rows': [(r['result'], label(r, games)) for r in rows], 'text': text, 'due': morning(day + timedelta(days=1)),
            'stale': datetime(day.year, day.month, day.day, LATEST[0], LATEST[1], tzinfo=gates.EASTERN).astimezone(timezone.utc) + timedelta(days=1)}


def week_receipt(wednesday, first, latest, games, ids):
    start, end = wednesday - timedelta(days=7), wednesday - timedelta(days=1)
    rows = plays_between(first, latest, games, ids, start, end)
    if not settled(rows):
        return None
    summary = x_post.summarize(rows)
    by_kind = []
    for kind in ('player', 'team', 'parlay'):
        group = [r for r in rows if pick_card.play_kind(r) == kind]
        if group:
            by_kind.append((KIND_NAMES[kind], record_text(x_post.summarize(group))))
    # The dates keep two weeks with the same record from posting the same words; one kind of play shows only the total.
    head = f"🍳 RECEIPTS · THE WEEK\n{start:%b} {start.day} to {end:%b} {end.day}: {record_text(summary)}"
    tail = 'Graded in public, win or lose.\n' + leagues(rows)
    text = fit([f'{name} {rec}' for name, rec in by_kind] if len(by_kind) > 1 else [], head, tail.strip())
    return {'key': f'receipt:week:{end.isoformat()}', 'card': f'receipt-week-{end.isoformat()}', 'kind': 'receipt',
            'title': record_text(summary), 'label': 'THIS WEEK’S PLATES', 'when': f'{start:%b %-d} to {end:%b %-d}',
            'rows': [(None, f'{name}  {rec}') for name, rec in by_kind], 'text': text, 'due': morning(wednesday),
            'stale': datetime(wednesday.year, wednesday.month, wednesday.day, LATEST[0], LATEST[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)}


def ready(first, latest, games, log_book, now):
    """The receipts that can go out now: yesterday's (or the day before's, if it settled late) and, on Wednesday,
    the week's. Each only when every play it covers is settled, and none after its evening."""
    ids = served(log_book)
    if not ids:
        return []
    today = eastern_date(now)
    out = []
    for back in (2, 1):
        receipt = day_receipt(today - timedelta(days=back), first, latest, games, ids)
        if receipt:
            out.append(receipt)
    if today.weekday() == WEEKDAY:
        receipt = week_receipt(today, first, latest, games, ids)
        if receipt:
            out.append(receipt)
    return [r for r in out if r['stale'] > now]


# ------------------------------------------------------------------ the rest of the day's posts

HOUSE_CARDS = x_post.SITE + 'img/'           # static cards in the kitchen's frame, deployed with the site
MENU_AT, MENU_UNTIL = (8, 45), (11, 30)      # Eastern: the game-day menu goes out before the first plate
BOOK_FROM, BOOK_AT, BOOK_UNTIL = (17, 0), (18, 0), (21, 0)   # Eastern: the book fills a day that had nothing else


def at(day, hm):
    return datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)


def todays_plays(first, latest, games, now):
    """Open, postable plays whose first game is today, Eastern."""
    import feed
    today = eastern_date(now)
    out = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if pick.get('historicalImport') or not feed.postable(merged) or merged.get('result') or merged.get('entryNote'):
            continue
        if (merged.get('status') or 'active') != 'active':
            continue
        if game_day(merged, games) == today:
            out.append(merged)
    return out


def menu(first, latest, games, log_book, now):
    """Game-day morning: what is on the stove today and when, by game, never the side. A reason to come back."""
    today = eastern_date(now)
    plays = todays_plays(first, latest, games, now)
    if not plays:
        return None
    rows, seen, parlay = [], set(), False
    for pick in sorted(plays, key=lambda p: min(games[g]['kickoff'] for g in p['gameIds'] if g in games)):
        if pick_card.play_kind(pick) == 'parlay':
            parlay = True
            continue
        game = games.get(pick['gameIds'][0])
        if not game or game['id'] in seen:
            continue
        seen.add(game['id'])
        league = game.get('league')
        kick = gates.when(game['kickoff']).astimezone(gates.EASTERN)
        rows.append(f"{pick_card.team_label(game.get('away'), league)} at {pick_card.team_label(game.get('home'), league)}, {kick:%-I:%M %p}")
    count = len(plays)
    head = f"🍳 TODAY'S MENU\n{count} plate{'s' if count != 1 else ''} on the stove today:"
    lines = [f'• {r}' for r in rows] + (['• the fun parlay'] if parlay else [])
    tail = 'Plates go out around noon.\n' + leagues(plays)
    return {'key': f'menu:day:{today.isoformat()}', 'card': HOUSE_CARDS + 'kitchen-menu.png', 'kind': 'menu',
            'text': fit(lines, head, tail.strip(), head_sep='\n'), 'due': at(today, MENU_AT), 'stale': at(today, MENU_UNTIL)}


def book(first, latest, games, log_book, now):
    """A day with nothing else on it gets the book: the season record of every play that went out on X, graded
    through yesterday so the numbers hold all day."""
    today = eastern_date(now)
    if now < at(today, BOOK_FROM):
        return None
    for entry in log_book.get('posts', []):
        if entry.get('cancelledAt') or entry.get('deletedAt') or not entry.get('dueAt'):
            continue
        if eastern_date(gates.when(entry['dueAt'])) == today:
            return None                    # the day already has a post
    ids = served(log_book)
    rows = [r for r in plays_between(first, latest, games, ids, datetime(2000, 1, 1).date(), today - timedelta(days=1))
            if r.get('result') in MARKS]
    if not rows:
        return None
    lines = []
    for kind in ('player', 'team', 'parlay'):
        group = [r for r in rows if pick_card.play_kind(r) == kind]
        if group:
            lines.append(f'{KIND_NAMES[kind]} {record_text(x_post.summarize(group))}')
    if len(lines) < 2:
        lines = []                         # one kind only: its line would repeat the season's
    through = today - timedelta(days=1)
    # The day it is graded through is named, so two quiet days in a row never post the same text (X refuses a
    # repeated post, and the same words twice read like a bot).
    head = f"🍳 THE BOOK\nSeason through {through:%b} {through.day}: {record_text(x_post.summarize(rows))}"
    tail = 'Every play we post, graded in public, win or lose.\n' + leagues(rows)
    return {'key': f'book:day:{today.isoformat()}', 'card': HOUSE_CARDS + 'kitchen-book.png', 'kind': 'book',
            'text': fit(lines, head, tail.strip()), 'due': max(at(today, BOOK_AT), now + timedelta(minutes=2)),
            'stale': at(today, BOOK_UNTIL)}


def house_posts(first, latest, games, log_book, now):
    """Everything the kitchen posts besides the plays: receipts, the game-day menu, and the book on an empty day."""
    out = [dict(r, kind='receipt') for r in ready(first, latest, games, log_book, now)]
    for build in (menu, book):
        post = build(first, latest, games, log_book, now)
        if post and post['stale'] > now:
            out.append(post)
    return out


def guard(receipt):
    problems = x_post.x_style(receipt['text'])
    if x_post.tweet_length(receipt['text']) > x_post.LIMIT:
        problems.append(f"{x_post.tweet_length(receipt['text'])} characters")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--now', help='UTC instant; default now')
    args = parser.parse_args(argv)
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    ctx = gates.Stores().as_of(now)
    found = ready(ctx.first, ctx.latest, ctx.games, x_post.load_log(), now)
    for receipt in found:
        print(f"{receipt['key']}  due {receipt['due'].astimezone(gates.EASTERN):%a %-I:%M %p} ET  card {receipt['card']}.png")
        print(receipt['text'] + '\n')
    if not found:
        print('no receipt is ready')
    return 0


if __name__ == '__main__':
    sys.exit(main())
