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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates
import pick_card
import record_scope
import re
import x_post
from sports_refresh import eastern_date

MORNING = (9, 0)                  # Eastern: when a receipt posts
LATEST = (20, 0)                  # Eastern, the day after: a receipt not scheduled by then is stale and skipped
WEEKDAY = 2                       # Wednesday: the week's receipt
CARD_HISTORY_DAYS = 8             # Discord embeds and retrying publishers need recent generated URLs to survive
MARKS = {'win': '✅', 'loss': '❌', 'push': '➖', 'void': '➖'}
KIND_NAMES = {'player': 'Player props', 'team': 'Game lines', 'parlay': 'Fun parlays', 'ladder': '80/20 Climb'}


def served(log_book):
    """Ids of plays released to X or Discord. Cancelled/deleted posts were never served."""
    out = set()
    for p in log_book.get('posts', []):
        if p.get('cancelledAt') or p.get('deletedAt'):
            continue
        discord = p.get('discord') or {}
        if (p.get('kind') == 'buffer:play' and (p.get('sentAt') or (discord.get('state') == 'sent' and discord.get('sentAt')))) \
                or (p.get('kind') == 'pick' and p.get('postedAt')):
            out.add(p['id'])
    return out


def released_first(first, log_book, games=None):
    """Copy first publications with the shared delivery fact used by every public count."""
    released = served(log_book)
    out = {}
    for key, pick in first.items():
        item = dict(pick, posted=key in released)
        if games and not item.get('kickoff'):
            starts = [games[game_id].get('kickoff') for game_id in item.get('gameIds') or []
                      if games.get(game_id, {}).get('kickoff')]
            if starts:
                item['kickoff'] = min(starts)
        out[key] = item
    return out


def counted(first, latest=None):
    """Ids in the public record, using record_scope's shared release/count rule."""
    latest = latest or {}
    def priced(key, pick):
        return pick.get('odds') is not None or (latest.get(key) or {}).get('odds') is not None
    return {key for key, pick in first.items()
            if (not pick.get('historicalImport') or priced(key, pick)) and record_scope.counts_public(pick)}


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
        return 'left hurt'
    who = names[0] + (f' +{len(names) - 1}' if len(names) > 1 else '')
    return f'{who} left hurt'


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
    import result_display
    rich = result_display.detail(pick)
    if rich:
        return ' · '.join(part for part in (rich, injury) if part)
    actual = result_display.clean_actual(pick)
    actual = re.sub(r'^.*?:\s*(\d+(?:\.\d+)?)\s+(?:receptions?|carries|attempts?)$', r'had \1', actual)
    actual = re.sub(r'^all 2 legs won$', 'both legs hit', actual)
    return ' · '.join(part for part in (actual if actual.startswith('had ') else f'Final: {actual}' if actual else '', injury) if part)


def result_line(pick, games=None):
    """The compact public receipt row, with the result first and a useful second line when one exists."""
    main = f"{MARKS[pick['result']]} {label(pick, games)}"
    detail = result_detail(pick)
    return f'{main} · {detail}' if detail else main


def record_text(summary):
    """Wins and losses (and pushes), as the site shows them. No units: followers never see a stake."""
    return f"{summary['win']}-{summary['loss']}" + (f"-{summary['push']}" if summary['push'] else '')


def season_as_of(first, latest, at):
    """The same current-season/current-stage straight headline the website showed at ``at``."""
    return record_scope.merged_summary(first, latest, at)


def accounting(rows):
    """Price provenance, without changing outcomes or advertising straight stakes on X."""
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder') and record_scope.is_headline(r)]
    captured = [r for r in straight if not r.get('priceAssumed') and isinstance(r.get('odds'), (int, float))]
    assumed = [r for r in straight if r.get('priceAssumed')]
    return {'captured': record_text(x_post.summarize(captured)) if captured else None,
            'assumed': record_text(x_post.summarize(assumed)) if assumed else None,
            'promotionalCredits': sum(bool(r.get('earlyExit')) for r in straight),
            'note': 'Historical assumed prices kept separate; promotional credits are not wins.'}


def headline(rows):
    """The results-post record: every released straight lane; tickets and Climb stay separate."""
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder')]
    if straight:
        return record_text(x_post.summarize(straight))
    fun = [r for r in rows if pick_card.play_kind(r) == 'parlay']
    if fun:
        return f"Fun parlay{'s' if len(fun) != 1 else ''} {record_text(x_post.summarize(fun))}"
    return f"80/20 Climb {record_text(x_post.summarize(rows))}"


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


def fit_result_rows(rows, head, tail, games=None):
    """Keep every miss visible before shortening a win on a daily recap."""
    full = [result_line(row, games) for row in rows]
    text = '\n'.join((head, *full)) + ('\n\n' + tail if tail else '')
    if x_post.tweet_length(text) <= x_post.LIMIT:
        return text
    # Margins and explanatory detail go first. The attached receipt still holds
    # every full row; X never shows a win while concealing a loss for length.
    short = [f"{MARKS[row['result']]} {label(row, games)}" for row in rows]
    kept = list(range(len(rows)))
    while True:
        omitted = [rows[index]['result'] for index in range(len(rows)) if index not in kept]
        suffix = []
        if omitted:
            suffix.append(f"+{omitted.count('win')} wins, {omitted.count('loss')} losses on card")
        text = '\n'.join((head, *(short[index] for index in kept), *suffix)) + ('\n\n' + tail if tail else '')
        if x_post.tweet_length(text) <= x_post.LIMIT or not kept:
            return text
        wins = [index for index in kept if rows[index]['result'] == 'win']
        kept.remove(wins[-1] if wins else kept[-1])


def day_receipt(day, first, latest, games, ids, as_of=None):
    rows = plays_between(first, latest, games, ids, day, day)
    if not settled(rows):
        return None
    if not rows:
        return None
    name = f'{day:%A}'
    due = morning(day + timedelta(days=1))
    late = as_of is not None and as_of > due + timedelta(minutes=30)
    opener = f"Late, but here's {name}.\n\n" if late else ''
    head = f"{opener}{name}: {headline(rows)}."
    tail = leagues(rows)
    text = fit_result_rows(rows, head, tail.strip(), games)
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder') and record_scope.is_headline(r)]
    fun = [r for r in rows if pick_card.play_kind(r) == 'parlay']
    return {'key': f'receipt:day:{day.isoformat()}', 'card': f'receipt-day-{day.isoformat()}', 'kind': 'receipt',
            'title': headline(rows), 'label': 'FINAL',
            'when': f'{day:%A, %b %-d}',
            # Retained art keeps the record followers saw when the receipt became
            # due, even when its image is rebuilt several days later.
            'season': record_scope.text(season_as_of(first, latest, due)),
            'summary': {'straight': record_text(x_post.summarize(straight)) if straight else None,
                        'fun': record_text(x_post.summarize(fun)) if fun else None},
            'accounting': accounting(rows),
            'rows': [(r['result'], label(r, games), result_detail(r), pick_card.play_kind(r)) for r in rows], 'text': text,
            'due': due,
            'stale': datetime(day.year, day.month, day.day, LATEST[0], LATEST[1], tzinfo=gates.EASTERN).astimezone(timezone.utc) + timedelta(days=1)}


def week_receipt(wednesday, first, latest, games, ids, as_of=None):
    start, end = wednesday - timedelta(days=7), wednesday - timedelta(days=1)
    rows = plays_between(first, latest, games, ids, start, end)
    if not settled(rows):
        return None
    if not rows:
        return None
    kinds = by_kind(rows)
    # The dates keep two weeks with the same record from posting the same words; one kind of play shows only the total.
    head = f"The week ({start:%b} {start.day} to {end:%b} {end.day}): {headline(rows)}"
    tail = leagues(rows)
    detail_rows = [kind_line(name, rec, rows) for name, rec in kinds]
    text = fit(detail_rows if len(kinds) > 1 else [], head, tail.strip(), head_sep='\n')
    straight = [r for r in rows if pick_card.play_kind(r) not in ('parlay', 'ladder') and record_scope.is_headline(r)]
    fun = [r for r in rows if pick_card.play_kind(r) == 'parlay']
    due = morning(wednesday)
    return {'key': f'receipt:week:{end.isoformat()}', 'card': f'receipt-week-{end.isoformat()}', 'kind': 'receipt',
            'title': headline(rows), 'label': 'LAST 7 DAYS', 'when': f'{start:%b %-d} to {end:%b %-d}',
            'season': record_scope.text(season_as_of(first, latest, due)),
            'summary': {'straight': record_text(x_post.summarize(straight)) if straight else None,
                        'fun': record_text(x_post.summarize(fun)) if fun else None},
            'accounting': accounting(rows),
            'rows': [(None, kind_line(name, rec, rows), '', name.lower()) for name, rec in kinds], 'text': text, 'due': due,
            'stale': datetime(wednesday.year, wednesday.month, wednesday.day, LATEST[0], LATEST[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)}


def ready(first, latest, games, log_book, now):
    """The receipts that can go out now: yesterday's (or the day before's, if it settled late) and, on Wednesday,
    the week's. Each only when every play it covers is settled, and none after its evening."""
    first = released_first(first, log_book, games)
    ids = counted(first, latest)
    if not ids:
        return []
    today = eastern_date(now)
    out = []
    for back in (2, 1):
        receipt = day_receipt(today - timedelta(days=back), first, latest, games, ids, now)
        if receipt:
            out.append(receipt)
    if today.weekday() == WEEKDAY:
        receipt = week_receipt(today, first, latest, games, ids, now)
        if receipt:
            out.append(receipt)
    import daily_straight_card
    return [daily_straight_card.link_final(r, log_book, latest, games) for r in out if r['stale'] > now]


def card_history(first, latest, games, now, days=CARD_HISTORY_DAYS, log_book=None):
    """Recently settled receipt cards, even after their posting window.

    Discord now uploads cards, but this short public history also repairs an embed when Discord had to fall back
    to the image URL and gives Buffer a stable retry window.
    """
    try:
        first = released_first(first, log_book if log_book is not None else x_post.load_log(), games)
    except (OSError, ValueError):
        first = released_first(first, {'posts': []}, games)
    ids = counted(first, latest)
    today = eastern_date(now)
    out = []
    for back in range(days + 1):
        day = today - timedelta(days=back)
        receipt = day_receipt(day, first, latest, games, ids, now)
        if receipt:
            out.append(receipt)
        if day.weekday() == WEEKDAY:
            receipt = week_receipt(day, first, latest, games, ids, now)
            if receipt:
                out.append(receipt)
    import daily_straight_card
    return [daily_straight_card.link_final(r, log_book or {}, latest, games) for r in out]


# ------------------------------------------------------------------ the rest of the day's posts

HOUSE_CARDS = x_post.SITE + 'img/'           # historical house-card URLs remain live for older posts
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
LADDER_MORNING = (9, 5)                    # a result first verified during quiet hours joins the morning sweep
QUIET = ((1, 0), (9, 0))                   # Eastern: after 1:00 AM, the morning receipt carries those wins
HANDLE = 'keenkooks'


def ladder_result_card_key(key):
    return f'ladder-result-{key}'


def near_miss(pick):
    """The owner-approved honest bad-beat band; a normal loss stays on the Final only."""
    if str(pick.get('result') or '').lower() != 'loss':
        return False
    value, line = pick.get('actualValue'), pick.get('line')
    if not isinstance(value, (int, float)) or not isinstance(line, (int, float)):
        return False
    miss = abs(float(value) - float(line))
    market = str(pick.get('market') or '')
    if market in ('recYds', 'rushYds', 'passYds'):
        return miss <= 3
    if market in ('rec', 'car', 'att', 'cmp'):
        # Half-point count markets settle on whole-number stats. A 1.5 margin
        # is one outcome beyond the winning threshold (for example UNDER
        # 14.5 finishing on 16), which is the owner's "one catch" band.
        return miss <= 1.5
    if str(pick.get('marketType') or '').lower() in ('spread', 'total'):
        return miss <= 2
    return False


def result_card_key(pick):
    return f"{'cooked' if pick.get('result') == 'win' else 'burnt'}-{pick['id']}"


def result_cards(first, latest, games, now, log_book=None, days=CARD_HISTORY_DAYS):
    """Cooked/Burnt cards still needed by a fresh or already-recorded result post.

    This intentionally does not backfill art for old text-only reactions. Posted
    attachments are immutable, and a historical result must never acquire new art
    merely because the site was rebuilt.
    """
    cutoff = now - timedelta(days=days)
    posted = set()
    for entry in (log_book or {}).get('posts', []):
        key = str(entry.get('id') or '')
        if key.startswith(('cashed:', 'burnt:')) and (entry.get('card') or entry.get('cardKey')) \
                and not entry.get('cancelledAt') and not entry.get('deletedAt'):
            posted.add(key.split(':', 1)[1])
    out = []
    for key, original in first.items():
        pick = dict(original, **latest.get(key, {}))
        if pick_card.play_kind(pick) not in ('player', 'team') or not pick.get('settledAt'):
            continue
        if pick.get('result') != 'win' and not near_miss(pick):
            continue
        try:
            settled = gates.when(pick['settledAt'])
            if settled < cutoff or (key not in posted and settled < now - CASHED_FRESH):
                continue
        except (TypeError, ValueError):
            continue
        game = games.get((pick.get('gameIds') or [None])[0])
        if game and isinstance(pick.get('actualValue'), (int, float)):
            out.append({'card': result_card_key(pick), 'pick': pick, 'game': game})
    return out


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


def win_reaction(pick, games=None):
    """Owner-written win copy selected only from the stored result and settled margin."""
    import hashlib
    import result_display
    play = label(pick, games)
    stat = result_display.stat_line(pick)
    direction = str(pick.get('direction') or '').lower()
    value, line = pick.get('actualValue'), pick.get('line')
    market_type = pick.get('marketType')
    if market_type == 'total' and not stat:
        scores = re.findall(r'\b(\d{1,3})\b', result_display.clean_actual(pick))
        return f"✅ {play}. Went {scores[-2]}-{scores[-1]}." if len(scores) >= 2 else f'✅ {play}.'
    if not stat:
        return f'✅ {play}.'
    if pick.get('lateCrossing') or str(pick.get('crossedAt') or '').lower() in ('4', 'q4', '4th'):
        return f'Took till the 4th. ✅ {play}. He had {stat}.'
    if direction == 'under':
        return f'✅ {play}. He had {stat}.'
    margin = abs(float(value) - float(line)) if isinstance(value, (int, float)) and isinstance(line, (int, float)) else None
    if margin is not None and (margin >= 10 or (line and margin / abs(float(line)) >= .40)):
        return f'Not close. ✅ {play}. He had {stat}.'
    if margin is not None and line and margin / abs(float(line)) <= .10:
        return f'Sweated that one. ✅ {play}. Finished with {stat}.'
    opener = ('CASH IT.', 'There we go.')[int(hashlib.sha1(str(pick.get('id')).encode()).hexdigest(), 16) % 2]
    return f'{opener} ✅ {play}. He had {stat}.'


def burnt_reaction(pick, games=None):
    """Plain, factual near-miss copy; overtime is named only when stored play-by-play proves it."""
    import result_display
    play = label(pick, games)
    overtime = result_display.overtime_detail(pick)
    if overtime:
        return f'{play}. {overtime}. Pain.'
    detail = result_display.detail(pick)
    if not detail and isinstance(pick.get('actualValue'), (int, float)) and isinstance(pick.get('line'), (int, float)):
        detail = f"missed by {pick_card.plain_number(abs(float(pick['actualValue']) - float(pick['line'])))}"
    return f'{play}. {detail}. Pain.' if detail else f'{play}. One short. Pain.'


def cashed(first, latest, games, log_book, now):
    """A win or owner-defined near miss that went out on X gets its reviewed result card and quotes the original.
    Every Climb result is its own continuing-story post: a win advances it, a loss
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
        if not pick.get('settledAt') or (result != 'win' and not ladder and not near_miss(pick)):
            continue
        settled_at = gates.when(pick['settledAt'])
        fresh = LADDER_CASHED_FRESH if ladder else CASHED_FRESH
        if not now - fresh < settled_at <= now:
            continue
        parlay = pick_card.play_kind(pick) == 'parlay'
        price = f"({int(pick['odds']):+d}, {pick.get('book')})"
        head = win_reaction(pick, games)
        import result_display
        what = ''
        if parlay:
            head, what = f"✅ {int(pick['odds']):+d} {label(pick, games)} cashed ({pick.get('book')})", ''
        card = (result_card_key(pick) if not ladder and isinstance(pick.get('actualValue'), (int, float))
                and pick_card.play_kind(pick) in ('player', 'team') else None)
        post_key = f'cashed:{key}'
        due = now
        if ladder:
            head, what = ladder_result(pick)
            card = ladder_result_card_key(key)
            if result != 'win':
                post_key = f'ladder-{result}:{key}'
            # A late game verified before the owner's 1:00 AM cutoff is still
            # a live result and goes out now. Only a result first seen during
            # quiet hours waits for the morning sweep.
            if quiet:
                due = at(eastern_date(now), LADDER_MORNING)
        elif result == 'loss':
            post_key = f'burnt:{key}'
            head = burnt_reaction(pick, games)
        if quiet and not ladder:
            # Quiet hours hold delivery, not admission. Queue a fresh morning
            # result before the play batch takes every slot until it expires.
            due = at(eastern_date(now), LADDER_MORNING)
            if due >= settled_at + fresh:
                continue
        league = str(key).split('-')[0]
        tag = x_post.TAGS.get(league, '')
        text = '\n'.join(x for x in (head, what, tag, f"https://x.com/{HANDLE}/status/{entry['tweetId']}") if x)
        out.append({'key': post_key, 'kind': 'cashed', 'card': card, 'text': text, 'due': due,
                    'stale': settled_at + fresh})
    return out


def ladder_result(pick):
    """(head, body) for one settled rung: advance, restart with the bank protected, or keep riding."""
    import social_units
    money = social_units.climb if social_units.active(pick) else pick_card.dollars
    info = pick.get('ladder') or {}
    result = str(pick.get('result') or 'win').lower()
    returned = int(info.get('payout') or 0)
    bank_this = int(info.get('bankThisWin') if info.get('bankThisWin') is not None else round(returned * 0.20))
    banked_after = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else (info.get('banked') or 0) + bank_this)
    next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else returned - bank_this)
    total = int(info.get('totalAfter') if info.get('totalAfter') is not None else banked_after + next_stake)
    stake, won = money(info.get('stake')), money(returned)
    if result == 'win' and total >= (info.get('goal') or 1000):
        return (f"🪜 80/20 Climb complete: {money(info.get('start', 50))} → {money(total)} in {info.get('step', 1)} steps",
                f"{money(banked_after)} banked along the way.")
    if result == 'win':
        return (f"Step {info.get('step', 1)} cashed ✅ {won} back.",
                f"{money(bank_this)} to the bank, {money(next_stake)} rides on step {info.get('step', 1) + 1}.")
    if result == 'loss':
        marks = leg_results(pick)
        legs = pick.get('legs') or []
        miss = next((leg for index, leg in enumerate(legs) if index < len(marks) and marks[index] == 'loss'), None)
        if miss:
            import result_display
            stat = result_display.stat_line(dict(miss, result='loss'))
            player = (miss.get('player') or result_display.player_name(miss)) if miss.get('athleteId') else ''
            needed = pick_card.plain_number(miss.get('line')) if isinstance(miss.get('line'), (int, float)) else None
            miss_line = ' '.join(part for part in (player, stat or pick_card.short_leg(miss.get('title'))) if part)
            if needed:
                miss_line += f", needed {needed}"
            miss_line += '.'
        else:
            miss_line = 'One leg missed.'
        head = f"The climb stopped at step {info.get('step', 1)}. {miss_line} Back to {money(info.get('start', 50))}."
        body = f"{money(info['banked'])} stays in the bank." if info.get('banked', 0) else ''
        return head, body
    bank = f" {money(info.get('banked'))} stays in the bank." if info.get('banked', 0) else ''
    return (f"➖ 80/20 Climb step {info.get('step', 1)} {result}", f"{stake} rides the same step.{bank}")


def ladder_cashed(pick):
    """Compatibility name for callers and old tests; all rung outcomes now use ladder_result()."""
    return ladder_result(pick)


def house_posts(first, latest, games, log_book, now, log=print):
    """Approved receipts, research and the owner's weekly projection sheet."""
    first = released_first(first, log_book, games)
    out = [dict(r, kind='receipt') for r in ready(first, latest, games, log_book, now)]
    import daily_straight_card
    combined = daily_straight_card.proposal(first, latest, games, log_book, now)
    if combined:
        out.append(combined)
    extra = book(first, latest, games, log_book, now)
    if extra and extra['stale'] > now:
        out.append(extra)
    out += cashed(first, latest, games, log_book, now)
    import research_posts
    out += research_posts.touchdown_followups(log_book, now)
    import morning_brief
    morning=morning_brief.post(now)
    import sheet
    projection = sheet.post(games, now)
    posted_ids = {row.get('id') for row in log_book.get('posts', [])
                  if not row.get('cancelledAt') and not row.get('deletedAt')}
    if projection and projection['key'] not in posted_ids:
        out.append(projection)
    research = research_posts.post(games, now, log=log)  # one stale-safe editorial research card at most
    # The Wednesday-night TNF preview consumes Thursday's research slot, not
    # Wednesday's ordinary slate research slot.
    research_already = research_posts.already_posted(log_book, research.get('countsFor', eastern_date(now))
                                                     if research else eastern_date(now))
    if morning and morning['stale'] > now and not research_posts.already_posted(log_book,eastern_date(now)):
        out.append(morning)
    elif research and research['stale'] > now and not research_already:
        out.append(research)
    import sports_posts
    sports = sports_posts.post(now)
    if sports:
        out.append(sports)
    import nba_editorial
    out += nba_editorial.posts(now)
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
