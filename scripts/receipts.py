"""Receipts: what the desk's plays did, one post the morning after each game day and one on Wednesday for the
week. Stdlib only.

The brand is that every play is graded in public, win or lose. So every morning after a game day, once every
play of that day is settled, the desk posts the receipt: each play with its result and the day's record, in the
same card frame as the plays. On Wednesday morning the week's receipt sums up the seven days before it by kind.
Together with the plays that makes a post every day of the season.

One record, the same on the site and on X (the owner's call, 2026-09-25): every play the desk published counts,
whether or not its post went out (a play pulled before its post stays in the record and is graded as posted),
apart from the Week 1 legs imported without prices. The record is wins and losses of the straight plays; fun
parlays get their own line. No units on X: money lives on the site only, at $100 a play (site/core.js).

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
KIND_NAMES = {'player': 'Player props', 'team': 'Team props', 'parlay': 'Fun parlays'}


def served(log_book):
    """Ids of the plays whose post went out on X: sent through Buffer, or posted by hand before the desk posted
    (the two seeded 2026-09-19 plays). A cancelled or deleted post was never served. The record counts every
    published play (counted); this says which ones followers saw, for the Pick of the Day record."""
    out = set()
    for p in log_book.get('posts', []):
        if p.get('cancelledAt') or p.get('deletedAt'):
            continue
        if (p.get('kind') == 'buffer:play' and p.get('sentAt')) or (p.get('kind') == 'pick' and p.get('postedAt')):
            out.add(p['id'])
    return out


def counted(first, latest=None):
    """Ids of every play in the record: everything published, apart from plays imported without a price that no later
    report priced (the Week 1 lines got an assumed price on 2026-09-26). The site's record (site/core.js theRecord)
    counts the same plays."""
    latest = latest or {}
    def priced(key, pick):
        return pick.get('odds') is not None or (latest.get(key) or {}).get('odds') is not None
    return {key for key, pick in first.items() if not pick.get('historicalImport') or priced(key, pick)}


def game_day(pick, games):
    """The Eastern date of a play's first kickoff: the day it was served."""
    starts = sorted(games[g]['kickoff'] for g in (pick.get('gameIds') or []) if g in games)
    return eastern_date(gates.when(starts[0])) if starts else None


def label(pick, games=None):
    """A play as its post and card named it: schools by name, over and under as the post says them."""
    if pick_card.play_kind(pick) == 'parlay':
        return f"{len(pick.get('legs') or [])}-leg fun parlay"
    return pick_card.display_title(pick, (games or {}).get((pick.get('gameIds') or [None])[0]))


def record_text(summary):
    """Wins and losses (and pushes), as the site shows them. No units: followers never see a stake."""
    return f"{summary['win']}-{summary['loss']}" + (f"-{summary['push']}" if summary['push'] else '')


def headline(rows):
    """The record a receipt leads with: the straight plays; fun parlays only when there is nothing else."""
    straight = [r for r in rows if pick_card.play_kind(r) != 'parlay']
    if straight:
        return record_text(x_post.summarize(straight))
    return f"Fun parlay{'s' if len(rows) != 1 else ''} {record_text(x_post.summarize(rows))}"


def by_kind(rows):
    """[(name, record)] for each kind of play among the rows: player props, team props, fun parlays."""
    out = []
    for kind in ('player', 'team', 'parlay'):
        group = [r for r in rows if pick_card.play_kind(r) == kind]
        if group:
            out.append((KIND_NAMES[kind], record_text(x_post.summarize(group))))
    return out


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
    name = f'{day:%A}'
    head = f"🍳 RECEIPTS · {name.upper()}\n{headline(rows)}"
    tail = 'Graded in public, win or lose.\n' + leagues(rows)
    text = fit([f"{MARKS[r['result']]} {label(r, games)}" for r in rows], head, tail.strip())
    return {'key': f'receipt:day:{day.isoformat()}', 'card': f'receipt-day-{day.isoformat()}', 'kind': 'receipt',
            'title': headline(rows), 'label': 'YESTERDAY’S PLATES', 'when': f'{day:%A, %b %-d}',
            'rows': [(r['result'], label(r, games)) for r in rows], 'text': text, 'due': morning(day + timedelta(days=1)),
            'stale': datetime(day.year, day.month, day.day, LATEST[0], LATEST[1], tzinfo=gates.EASTERN).astimezone(timezone.utc) + timedelta(days=1)}


def week_receipt(wednesday, first, latest, games, ids):
    start, end = wednesday - timedelta(days=7), wednesday - timedelta(days=1)
    rows = plays_between(first, latest, games, ids, start, end)
    if not settled(rows):
        return None
    kinds = by_kind(rows)
    # The dates keep two weeks with the same record from posting the same words; one kind of play shows only the total.
    head = f"🍳 RECEIPTS · THE WEEK\n{start:%b} {start.day} to {end:%b} {end.day}: {headline(rows)}"
    tail = 'Graded in public, win or lose.\n' + leagues(rows)
    text = fit([f'{name} {rec}' for name, rec in kinds] if len(kinds) > 1 else [], head, tail.strip())
    return {'key': f'receipt:week:{end.isoformat()}', 'card': f'receipt-week-{end.isoformat()}', 'kind': 'receipt',
            'title': headline(rows), 'label': 'THIS WEEK’S PLATES', 'when': f'{start:%b %-d} to {end:%b %-d}',
            'rows': [(None, f'{name}  {rec}') for name, rec in kinds], 'text': text, 'due': morning(wednesday),
            'stale': datetime(wednesday.year, wednesday.month, wednesday.day, LATEST[0], LATEST[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)}


def ready(first, latest, games, log_book, now):
    """The receipts that can go out now: yesterday's (or the day before's, if it settled late) and, on Wednesday,
    the week's. Each only when every play it covers is settled, and none after its evening."""
    ids = counted(first, latest)
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
    tail = ('Pick of the Day and the rest go out around noon.' if len(plays) > 1 else 'Pick of the Day goes out around noon.') + '\n' + leagues(plays)
    return {'key': f'menu:day:{today.isoformat()}', 'card': HOUSE_CARDS + 'kitchen-menu.png', 'kind': 'menu',
            'text': fit(lines, head, tail.strip(), head_sep='\n'), 'due': at(today, MENU_AT), 'stale': at(today, MENU_UNTIL)}


def book(first, latest, games, log_book, now):
    """A day with nothing else on it gets the book: the season record of every play, graded through yesterday so
    the numbers hold all day."""
    today = eastern_date(now)
    if now < at(today, BOOK_FROM):
        return None
    for entry in log_book.get('posts', []):
        if entry.get('cancelledAt') or entry.get('deletedAt') or not entry.get('dueAt'):
            continue
        if eastern_date(gates.when(entry['dueAt'])) == today:
            return None                    # the day already has a post
    rows = [r for r in plays_between(first, latest, games, counted(first, latest), datetime(2000, 1, 1).date(), today - timedelta(days=1))
            if r.get('result') in MARKS]
    if not rows:
        return None
    lines = [f'{name} {rec}' for name, rec in by_kind(rows)]
    if len(lines) < 2:
        lines = []                         # one kind only: its line would repeat the season's
    through = today - timedelta(days=1)
    # The day it is graded through is named, so two quiet days in a row never post the same text (X refuses a
    # repeated post, and the same words twice read like a bot).
    head = f"🍳 THE BOOK\nSeason through {through:%b} {through.day}: {headline(rows)}"
    tail = 'Every play we post, graded in public, win or lose.\n' + leagues(rows)
    return {'key': f'book:day:{today.isoformat()}', 'card': HOUSE_CARDS + 'kitchen-book.png', 'kind': 'book',
            'text': fit(lines, head, tail.strip()), 'due': max(at(today, BOOK_AT), now + timedelta(minutes=2)),
            'stale': at(today, BOOK_UNTIL)}


CASHED_FRESH = timedelta(hours=3)          # a win settled longer ago than this is left to the morning receipt
QUIET = ((0, 30), (9, 0))                  # Eastern: no cashed post overnight; the morning receipt carries those wins
HANDLE = 'keenkooks'


def cashed(first, latest, games, log_book, now):
    """A winning play that went out on X gets its own post when it settles: "✅ CASHED", the play and its price, and
    the original post quoted (its X link in the text shows the post under it). Text only: the quoted post carries
    the card. Losses are not singled out; the morning receipt lists every play, win or lose. Overnight, or three
    hours after it settled, a win is left to that receipt."""
    local = now.astimezone(gates.EASTERN)
    minute = local.hour * 60 + local.minute
    if QUIET[0][0] * 60 + QUIET[0][1] <= minute < QUIET[1][0] * 60 + QUIET[1][1]:
        return []
    out = []
    for entry in log_book.get('posts', []):
        key = entry.get('id')
        if entry.get('kind') != 'buffer:play' or not entry.get('tweetId') or entry.get('cancelledAt') or entry.get('deletedAt') or key not in first:
            continue
        pick = dict(first[key], **latest.get(key, {}))
        if pick.get('result') != 'win' or not pick.get('settledAt'):
            continue
        settled_at = gates.when(pick['settledAt'])
        if not now - CASHED_FRESH < settled_at <= now:
            continue
        parlay = pick_card.play_kind(pick) == 'parlay'
        head = '✅ ' + ('PICK OF THE DAY ' if entry.get('featured') else 'FUN PARLAY ' if parlay else '') + 'CASHED'
        price = f"{int(pick['odds']):+d} at {pick.get('book')}"
        what = f"{len(pick.get('legs') or [])} legs · {price}" if parlay else f"{label(pick, games)}\n{price}"
        league = str(key).split('-')[0]
        tag = x_post.TAGS.get(league, '')
        text = f"{head}\n{what}\n\n{tag}\nhttps://x.com/{HANDLE}/status/{entry['tweetId']}".replace('\n\n\n', '\n\n')
        out.append({'key': f'cashed:{key}', 'kind': 'cashed', 'card': None, 'text': text, 'due': now,
                    'stale': settled_at + CASHED_FRESH})
    return out


def with_menu(receipt, post, plays_today):
    """One morning post instead of two: yesterday's receipt with a line for what is on the stove today. Its key names
    both, so neither goes out again on its own."""
    rows = receipt.get('rows') or []
    count = len(plays_today)
    today = f"Today: {count} plate{'s' if count != 1 else ''} on the stove. Pick of the Day goes out around noon."
    tags = ' '.join(t for t in (x_post.TAGS[l] for l in ('NFL', 'CFB')) if t in receipt['text'] + ' ' + post['text'])
    lines = [f"{MARKS.get(result, '•')} {name}" for result, name in rows] if receipt['key'].startswith('receipt:day:') else [name for _, name in rows]
    head = receipt['text'].split('\n\n')[0]
    text = fit(lines, head, f'Graded in public, win or lose.\n{today}\n{tags}'.strip())
    return dict(receipt, key=f"{receipt['key']}+{post['key']}", text=text, stale=min(receipt['stale'], post['stale']))


def house_posts(first, latest, games, log_book, now):
    """Everything the kitchen posts besides the plays: receipts, the game-day menu (riding on the morning's receipt when
    there is one), the book on an empty day, and a cashed post for each winning play as it settles."""
    out = [dict(r, kind='receipt') for r in ready(first, latest, games, log_book, now)]
    today = eastern_date(now)
    posted = {part for p in log_book.get('posts', []) for part in str(p.get('id')).split('+')}
    post = menu(first, latest, games, log_book, now)
    if post and post['stale'] > now:
        morning_receipt = next((i for i, r in enumerate(out) if r['key'].startswith('receipt:day:') and r['key'] not in posted
                                and eastern_date(r['due']) == today), None)
        if morning_receipt is not None:
            out[morning_receipt] = with_menu(out[morning_receipt], post, todays_plays(first, latest, games, now))
        else:
            out.append(post)
    extra = book(first, latest, games, log_book, now)
    if extra and extra['stale'] > now:
        out.append(extra)
    out += cashed(first, latest, games, log_book, now)
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
