"""Receipts: what the desk's plays did, one post the morning after each game day and one on Wednesday for the
week. Stdlib only.

The brand is that every play is graded in public, win or lose. So every morning after a game day, once every
play of that day is settled, the desk posts the receipt: each play with its result and the day's record, in the
same card frame as the plays. On Wednesday morning the week's receipt sums up the seven days before it by kind.
Together with the plays that makes a post every day of the season.

One record, the same on the site and on X (the owner's call, 2026-09-25): every play the desk published counts,
whether or not its post went out (a play pulled before its post stays in the record and is graded as posted),
apart from the Week 1 legs imported without prices. The record is wins and losses of the straight plays; fun
parlays get their own line. Straight-play units live on the site. A fun ticket's smaller stake is shown on the
receipt so nobody mistakes a 0.25u parlay for a full-unit straight play.

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
CARD_HISTORY_DAYS = 8             # Discord embeds and retrying publishers need recent generated URLs to survive
MARKS = {'win': '✅', 'loss': '❌', 'push': '➖', 'void': '➖'}
KIND_NAMES = {'player': 'Player props', 'team': 'Game lines', 'parlay': 'Fun parlays', 'ladder': 'Ladder'}


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
    """A play as its post named it: "Iowa/Michigan over 38.5", "5-leg lotto", "80/20 Climb step 2"."""
    if pick_card.play_kind(pick) == 'ladder':
        info = pick.get('ladder') or {}
        return f"80/20 Climb step {info.get('step', 1)} ({pick_card.dollars(info.get('stake'))} → {pick_card.dollars(info.get('payout'))})"
    if pick_card.play_kind(pick) == 'parlay':
        odds = pick.get('odds')
        return f"{len(pick.get('legs') or [])}-leg {'lotto' if isinstance(odds, (int, float)) and odds >= x_post.LOTTO else 'parlay'}"
    return pick_card.short_title(pick, (games or {}).get((pick.get('gameIds') or [None])[0]))


def stake_text(pick):
    """The deliberately smaller fun-ticket stake, only when the stored play supplies one."""
    stake = pick.get('riskUnits')
    if not isinstance(stake, (int, float)):
        return ''
    return f'{stake:g}u'


def leg_results(pick):
    """The settled result of each parlay leg from the immutable settlement text, when it was recorded."""
    actual = str(pick.get('actual') or '')
    if not actual.lower().startswith('legs:'):
        return []
    results = [part.strip().lower() for part in actual.split(':', 1)[1].split(',')]
    return [result for result in results if result in MARKS]


def injury_detail(pick):
    """A compact, factual receipt note only when grading preserved a verified in-game injury report."""
    names = [str(name).strip() for name in pick.get('injuryPlayers') or [] if str(name).strip()]
    if not names:
        return ''
    if pick_card.play_kind(pick) != 'parlay':
        return 'injured in-game · checked before grading'
    who = names[0] + (f' +{len(names) - 1}' if len(names) > 1 else '')
    return f'{who} injured in-game · checked before grading'


def result_detail(pick):
    """One factual line that makes a receipt worth reading without manufacturing a stat.

    Parlays say how many live legs hit, identify protected voids, and call out a one-leg miss. Straight plays use
    the preserved final result.
    """
    injury = injury_detail(pick)
    if pick_card.play_kind(pick) == 'parlay':
        results = leg_results(pick)
        stake = stake_text(pick)
        pieces = [injury] if injury else []
        if stake:
            pieces.append(stake)
        if results:
            won = results.count('win')
            voided = results.count('void') + results.count('push')
            live = len(results) - voided
            pieces.append(f'{won}/{live} live legs hit' if voided else f'{won}/{len(results)} legs hit')
            if voided:
                pieces.append(f"{voided} leg{'s' if voided != 1 else ''} voided")
            if pick.get('result') == 'loss' and results.count('loss') == 1:
                pieces.append('missed by one leg')
            elif pick.get('result') == 'win' and not voided:
                pieces.append('clean sweep')
        return ' · '.join(pieces)
    actual = str(pick.get('actual') or '').strip()
    return ' · '.join(part for part in (injury, f'Final: {actual}' if actual else '') if part)


def result_line(pick, games=None):
    """The compact public receipt row, with the result first and a useful second line when one exists."""
    main = f"{MARKS[pick['result']]} {label(pick, games)}"
    detail = result_detail(pick)
    return f'{main} · {detail}' if detail else main


def record_text(summary):
    """Wins and losses (and pushes), as the site shows them. No units: followers never see a stake."""
    return f"{summary['win']}-{summary['loss']}" + (f"-{summary['push']}" if summary['push'] else '')


def accounting(rows):
    """Price provenance, without changing outcomes or advertising straight stakes on X."""
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder')]
    captured = [r for r in straight if not r.get('priceAssumed') and isinstance(r.get('odds'), (int, float))]
    assumed = [r for r in straight if r.get('priceAssumed')]
    return {'captured': record_text(x_post.summarize(captured)) if captured else None,
            'assumed': record_text(x_post.summarize(assumed)) if assumed else None,
            'promotionalCredits': sum(bool(r.get('earlyExit')) for r in straight),
            'note': 'Historical assumed prices kept separate; promotional credits are not wins.'}


def headline(rows):
    """The record a receipt leads with: the straight plays; fun parlays, then the ladder, only when there is nothing else."""
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder')]
    if straight:
        return record_text(x_post.summarize(straight))
    fun = [r for r in rows if pick_card.play_kind(r) == 'parlay']
    if fun:
        return f"Fun parlay{'s' if len(fun) != 1 else ''} {record_text(x_post.summarize(fun))}"
    return f"Ladder {record_text(x_post.summarize(rows))}"


def by_kind(rows):
    """[(name, record)] for each kind of play among the rows: player props, game lines, fun parlays."""
    out = []
    for kind in ('player', 'team', 'parlay', 'ladder'):
        group = [r for r in rows if pick_card.play_kind(r) == kind]
        if group:
            out.append((KIND_NAMES[kind], record_text(x_post.summarize(group))))
    return out


def kind_line(name, rec, rows):
    """A category line; fun parlays name their stored smaller stake instead of looking like full-unit plays."""
    if name != KIND_NAMES['parlay']:
        return f'{name} {rec}'
    stakes = {stake_text(r) for r in rows if pick_card.play_kind(r) == 'parlay' and stake_text(r)}
    if len(stakes) == 1:
        stake = next(iter(stakes))
        count = len([r for r in rows if pick_card.play_kind(r) == 'parlay'])
        return f"{name} {rec} · {stake}{' each' if count > 1 else ''}"
    return f'{name} {rec}'


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
    order = {'player': 0, 'team': 1, 'ladder': 2, 'parlay': 3}           # the order the plays posted in
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
    head = f"{name}: {headline(rows)}"
    tail = leagues(rows)
    text = fit([result_line(r, games) for r in rows], head, tail.strip(), head_sep='\n')
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder')]
    fun = [r for r in rows if pick_card.play_kind(r) == 'parlay']
    return {'key': f'receipt:day:{day.isoformat()}', 'card': f'receipt-day-{day.isoformat()}', 'kind': 'receipt',
            'title': headline(rows), 'label': 'YESTERDAY’S PLATES', 'when': f'{day:%A, %b %-d}',
            'summary': {'straight': record_text(x_post.summarize(straight)) if straight else None,
                        'fun': record_text(x_post.summarize(fun)) if fun else None},
            'accounting': accounting(rows),
            'rows': [(r['result'], label(r, games), result_detail(r)) for r in rows], 'text': text,
            'due': morning(day + timedelta(days=1)),
            'stale': datetime(day.year, day.month, day.day, LATEST[0], LATEST[1], tzinfo=gates.EASTERN).astimezone(timezone.utc) + timedelta(days=1)}


def week_receipt(wednesday, first, latest, games, ids):
    start, end = wednesday - timedelta(days=7), wednesday - timedelta(days=1)
    rows = plays_between(first, latest, games, ids, start, end)
    if not settled(rows):
        return None
    kinds = by_kind(rows)
    # The dates keep two weeks with the same record from posting the same words; one kind of play shows only the total.
    head = f"The week ({start:%b} {start.day} to {end:%b} {end.day}): {headline(rows)}"
    tail = leagues(rows)
    detail_rows = [kind_line(name, rec, rows) for name, rec in kinds]
    text = fit(detail_rows if len(kinds) > 1 else [], head, tail.strip(), head_sep='\n')
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder')]
    fun = [r for r in rows if pick_card.play_kind(r) == 'parlay']
    return {'key': f'receipt:week:{end.isoformat()}', 'card': f'receipt-week-{end.isoformat()}', 'kind': 'receipt',
            'title': headline(rows), 'label': 'THIS WEEK’S PLATES', 'when': f'{start:%b %-d} to {end:%b %-d}',
            'summary': {'straight': record_text(x_post.summarize(straight)) if straight else None,
                        'fun': record_text(x_post.summarize(fun)) if fun else None},
            'accounting': accounting(rows),
            'rows': [(None, kind_line(name, rec, rows), '') for name, rec in kinds], 'text': text, 'due': morning(wednesday),
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


def card_history(first, latest, games, now, days=CARD_HISTORY_DAYS):
    """Recently settled receipt cards, even after their posting window.

    Discord now uploads cards, but this short public history also repairs an embed when Discord had to fall back
    to the image URL and gives Buffer a stable retry window.
    """
    ids = counted(first, latest)
    today = eastern_date(now)
    out = []
    for back in range(days + 1):
        day = today - timedelta(days=back)
        receipt = day_receipt(day, first, latest, games, ids)
        if receipt:
            out.append(receipt)
        if day.weekday() == WEEKDAY:
            receipt = week_receipt(day, first, latest, games, ids)
            if receipt:
                out.append(receipt)
    return out


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
    """Game-day morning: what is already approved today and when, by game, never the side.

    The reusable card deliberately promises no market category; the live text below is the source of truth for the
    exact count and schedule. That keeps a screened-out prop or fun ticket from being advertised before it exists.
    """
    today = eastern_date(now)
    plays = todays_plays(first, latest, games, now)
    if not plays:
        return None
    rows, seen, parlay, rung = [], set(), False, None
    for pick in sorted(plays, key=lambda p: min(games[g]['kickoff'] for g in p['gameIds'] if g in games)):
        if pick_card.play_kind(pick) == 'parlay':
            parlay = True
            continue
        if pick_card.play_kind(pick) == 'ladder':
            rung = pick
            continue
        game = games.get(pick['gameIds'][0])
        if not game or game['id'] in seen:
            continue
        seen.add(game['id'])
        league = game.get('league')
        kick = gates.when(game['kickoff']).astimezone(gates.EASTERN)
        rows.append(f"{pick_card.team_label(game.get('away'), league)}/{pick_card.team_label(game.get('home'), league)} {kick:%-I:%M %p}")
    count = len(plays)
    head = f"Today: {count} play{'s' if count != 1 else ''}"
    lines = (rows + (['a lotto'] if parlay else [])
             + ([f"ladder step {(rung.get('ladder') or {}).get('step', 1)}"] if rung else []))
    tail = leagues(plays)
    return {'key': f'menu:day:{today.isoformat()}', 'card': HOUSE_CARDS + 'kitchen-menu-approved.png', 'kind': 'menu',
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
    lines = [kind_line(name, rec, rows) for name, rec in by_kind(rows)]
    if len(lines) < 2:
        lines = []                         # one kind only: its line would repeat the season's
    through = today - timedelta(days=1)
    # The day it is graded through is named, so two quiet days in a row never post the same text (X refuses a
    # repeated post, and the same words twice read like a bot).
    head = f"Season through {through:%b} {through.day}: {headline(rows)}"
    tail = leagues(rows)
    return {'key': f'book:day:{today.isoformat()}', 'card': HOUSE_CARDS + 'kitchen-book-neon.png', 'kind': 'book',
            'text': fit(lines, head, tail.strip(), head_sep='\n'), 'due': max(at(today, BOOK_AT), now + timedelta(minutes=2)),
            'stale': at(today, BOOK_UNTIL)}


CASHED_FRESH = timedelta(hours=3)          # a win settled longer ago than this is left to the morning receipt
LADDER_CASHED_FRESH = timedelta(hours=24)  # the Climb is a continuing story; an overnight final advances next morning
LADDER_MORNING = (9, 5)                    # never wake the feed overnight; the 6:45 run can still queue the card
QUIET = ((0, 30), (9, 0))                  # Eastern: no cashed post overnight; the morning receipt carries those wins
HANDLE = 'keenkooks'


def ladder_result_card_key(key):
    return f'ladder-result-{key}'


def ladder_result_cards(first, latest, now, days=CARD_HISTORY_DAYS):
    """Recently settled Climb rungs whose result graphics must remain live for Buffer and Discord."""
    cutoff = now - timedelta(days=days)
    out = []
    for key, original in first.items():
        pick = dict(original, **latest.get(key, {}))
        if pick_card.play_kind(pick) != 'ladder' or not pick.get('result') or not pick.get('settledAt'):
            continue
        try:
            if gates.when(pick['settledAt']) < cutoff:
                continue
        except (TypeError, ValueError):
            continue
        out.append({'card': ladder_result_card_key(key), 'pick': pick})
    return out


def cashed(first, latest, games, log_book, now):
    """A winning play that went out on X gets its own post when it settles: "✅ CASHED", the play and its price, and
    the original post quoted (its X link in the text shows the post under it). Ordinary wins stay text-only because
    the quoted post carries the card. Every Climb result is its own continuing-story post: a win advances it, a loss
    shows what stayed banked and starts the next climb at $50, and a push keeps the rung open. The result card remains
    eligible through the next morning, so a late final cannot silently miss the story. Ordinary losses still wait for
    the honest morning receipt."""
    local = now.astimezone(gates.EASTERN)
    minute = local.hour * 60 + local.minute
    quiet = QUIET[0][0] * 60 + QUIET[0][1] <= minute < QUIET[1][0] * 60 + QUIET[1][1]
    out = []
    for entry in log_book.get('posts', []):
        key = entry.get('id')
        if entry.get('kind') != 'buffer:play' or not entry.get('tweetId') or entry.get('cancelledAt') or entry.get('deletedAt') or key not in first:
            continue
        pick = dict(first[key], **latest.get(key, {}))
        result = str(pick.get('result') or '').lower()
        ladder = pick_card.play_kind(pick) == 'ladder'
        if not pick.get('settledAt') or (result != 'win' and not ladder):
            continue
        settled_at = gates.when(pick['settledAt'])
        fresh = LADDER_CASHED_FRESH if ladder else CASHED_FRESH
        if not now - fresh < settled_at <= now or (quiet and not ladder):
            continue
        parlay = pick_card.play_kind(pick) == 'parlay'
        price = f"({int(pick['odds']):+d}, {pick.get('book')})"
        head = f"✅ {'POTD cashed' if entry.get('featured') else 'Cashed'}: {label(pick, games)} {price}"
        what = ''
        if parlay:
            head, what = f"✅ {int(pick['odds']):+d} {label(pick, games)} cashed ({pick.get('book')})", ''
        card = None
        post_key = f'cashed:{key}'
        due = now
        if ladder:
            head, what = ladder_result(pick)
            card = ladder_result_card_key(key)
            if result != 'win':
                post_key = f'ladder-{result}:{key}'
            if local.hour < LADDER_MORNING[0]:
                due = at(eastern_date(now), LADDER_MORNING)
        league = str(key).split('-')[0]
        tag = x_post.TAGS.get(league, '')
        text = '\n'.join(x for x in (head, what, tag, f"https://x.com/{HANDLE}/status/{entry['tweetId']}") if x)
        out.append({'key': post_key, 'kind': 'cashed', 'card': card, 'text': text, 'due': due,
                    'stale': settled_at + fresh})
    return out


def ladder_result(pick):
    """(head, body) for one settled rung: advance, restart with the bank protected, or keep riding."""
    info = pick.get('ladder') or {}
    result = str(pick.get('result') or 'win').lower()
    returned = int(info.get('payout') or 0)
    bank_this = int(info.get('bankThisWin') if info.get('bankThisWin') is not None else round(returned * 0.20))
    banked_after = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else (info.get('banked') or 0) + bank_this)
    next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else returned - bank_this)
    total = int(info.get('totalAfter') if info.get('totalAfter') is not None else banked_after + next_stake)
    stake, won = pick_card.dollars(info.get('stake')), pick_card.dollars(returned)
    if result == 'win' and total >= (info.get('goal') or 1000):
        return (f"🪜 80/20 Climb complete: {pick_card.dollars(info.get('start', 50))} → {pick_card.dollars(total)} in {info.get('step', 1)} steps",
                f"{pick_card.dollars(banked_after)} banked along the way.")
    if result == 'win':
        return (f"✅ 80/20 Climb step {info.get('step', 1)} cashed: {stake} → {won}",
                f"{pick_card.dollars(banked_after)} banked. {pick_card.dollars(next_stake)} rides step {info.get('step', 1) + 1}.")
    if result == 'loss':
        marks = leg_results(pick)
        legs = pick.get('legs') or []
        lines = [f"{pick_card.short_leg(str(leg.get('title') or 'Leg'))} {MARKS.get(marks[index], '•')}"
                 for index, leg in enumerate(legs) if index < len(marks)]
        body = '\n'.join(lines + [f"{pick_card.dollars(info.get('banked', 0))} stays banked. Climb {int(info.get('run') or 1) + 1} restarts at "
                                   f"{pick_card.dollars(info.get('start', 50))}.",
                                   "That’s why we bank 20%: one miss can’t take it back."])
        return f"❌ 80/20 Climb step {info.get('step', 1)} missed", body
    return (f"➖ 80/20 Climb step {info.get('step', 1)} {result}",
            f"{stake} rides the same step. {pick_card.dollars(info.get('banked', 0))} stays banked.")


def ladder_cashed(pick):
    """Compatibility name for callers and old tests; all rung outcomes now use ladder_result()."""
    return ladder_result(pick)


def with_menu(receipt, post, plays_today):
    """One morning post instead of two: yesterday's receipt with a line for what is on the stove today. Its key names
    both, so neither goes out again on its own."""
    rows = receipt.get('rows') or []
    count = len(plays_today)
    today = f"Today: {count} play{'s' if count != 1 else ''}."
    tags = ' '.join(t for t in (x_post.TAGS[l] for l in ('NFL', 'CFB')) if t in receipt['text'] + ' ' + post['text'])
    if receipt['key'].startswith('receipt:day:'):
        lines = [f"{MARKS.get(row[0], '•')} {row[1]}" + (f" · {row[2]}" if len(row) > 2 and row[2] else '') for row in rows]
    else:
        lines = [row[1] for row in rows]
    head = receipt['text'].split('\n')[0]           # "Saturday: 5-3"
    text = fit(lines, head, f'{today}\n{tags}'.strip(), head_sep='\n')
    return dict(receipt, key=f"{receipt['key']}+{post['key']}", text=text, stale=min(receipt['stale'], post['stale']))


def climb_checkin(first, latest, games, now):
    """A weekend status, not a promised ticket. Existing run/Buffer limits deliver it once per day."""
    import ladder
    day = eastern_date(now)
    if day.weekday() not in (5, 6) or not at(day, (11, 45)) <= now < at(day, (14, 0)):
        return None
    state = ladder.state(first, latest)
    opened = state['open']
    if opened and game_day(opened, games) == day:
        return None  # The actual ticket is the check-in; never add a conflicting "waiting" post.
    head = f"80/20 Climb · {day:%a %b} {day.day}"
    if opened:
        body = f"Step {(opened.get('ladder') or {}).get('step', state['step'])} is still open. Next step waits for its result."
    else:
        body = f"Step {state['step']} is next, not scheduled yet. ${state['stake']} riding; ${state['banked']} banked."
    text = head + '\n' + body + ('\nTicket scans: 10 AM, 1:30 PM, 4 PM and 8 PM ET, plus the regular desk runs.'
                                 '\nDiscord gets a qualifying ticket first; X follows about 10-15 minutes later. No forced step.')
    return {'key': f'climb:checkin:{day.isoformat()}', 'kind': 'book', 'card': None,
            'text': text, 'due': now + timedelta(minutes=2), 'stale': at(day, (14, 0))}


def house_posts(first, latest, games, log_book, now):
    """Everything the kitchen posts besides the plays: receipts, the game-day menu (riding on the morning's receipt when
    there is one), the book on an empty day, a cashed post for each winning play as it settles, and the weekly
    projections sheet (scripts/sheet.py) on college Saturday and NFL Sunday."""
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
    climb = climb_checkin(first, latest, games, now)
    if climb:
        out.append(climb)
    import sheet
    weekly = sheet.post(games, now)          # the weekly projections sheet, on its league's day
    if weekly and weekly['stale'] > now:
        out.append(weekly)
    import research_posts
    research = research_posts.post(games, now)  # one stale-safe editorial research card at most
    if research and research['stale'] > now:
        out.append(research)
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
