"""Posting to @keenkooks through Buffer, whose free plan carries the cost of X's API. Stdlib only.

X meters posting through its own API. Buffer (buffer.com) connects an X account to its own developer
access and lets a free plan schedule posts through a GraphQL API: 3,000 requests a month, a public
image URL per post, an exact `dueAt` per post, and a `deletePost` to take one back. That is enough for
a desk that posts a handful of plays a day at set times.

  python scripts/buffer_post.py channels          list the connected channels (find @keenkooks)
  python scripts/buffer_post.py limits             today's posting limit for the X channel
  python scripts/buffer_post.py plan               what the run would schedule right now, without posting
  python scripts/buffer_post.py schedule [--soon MIN]     schedule exactly that, by hand (needs --confirm)
  python scripts/buffer_post.py post PICK_ID [--at ISO]   schedule one pick's post (needs --confirm)
  python scripts/buffer_post.py reconcile          record the X link, or the error, for every post whose time passed

X gets the plays, their receipts, verified injury angles and one short conversation prompt between plays on a multi-play card. Confirmed
official plays reach Discord about 10-15 minutes before their Buffer time; the rest mirrors after X. Plays use the same shape every time and
always carry the card. The run (scripts/run.py) schedules each play once, three hours before its kickoff and never
before 9:00 AM ET on game day, ten minutes apart, and logs every post in data/x-posted.json so nothing goes
out twice. A play whose card is not live yet waits; a play that closes to new entries before its time is
cancelled. The token lives in the environment (BUFFER_TOKEN) and never in a log.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed
import gates
import pick_card
import receipts
import x_post
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.buffer.com'
CARDS = x_post.SITE + 'data/cards/'
POST_AT = (12, 0)                    # Eastern: plays go out around midday on game day (the owner's call, 2026-09-24)
EARLY_LEAD = timedelta(hours=2)      # a game before 2 PM posts two hours ahead of kickoff instead, never before 9:00 AM
SPACING = timedelta(minutes=10)      # between two posts
SOON = timedelta(minutes=2)          # a post scheduled "now" goes out this far ahead
ORDER = {'player': 0, 'team': 1, 'ladder': 2, 'parlay': 3}   # inside one kickoff: player props, game lines, the ladder, the parlay
MAX_PER_DAY = 20                     # our own ceiling for a day's posts, counting those already scheduled; Buffer allows 50
DISCORD_PLAY_LEAD = timedelta(minutes=15)  # the five-minute delivery job makes plays land about 10-15 minutes before X
CONVERSATION = (
    "First play is out. What are you riding today? 👀",
    "The card is rolling. Which game has your attention?",
    "One play down. Props, sides or totals—what are you looking at?",
)
FUN_TEASERS = (
    "First play is out. The fun ticket is still in the kitchen. 🎰\nWho's riding today?",
    "The card is rolling. The fun ticket comes later. 🎰\nWhat are you riding today?",
)


def card_url(card_key):
    """Where a post's card lives: a house card (menu, book) by its full address, a play's or a receipt's under
    data/cards/ by its key."""
    return str(card_key) if str(card_key).startswith('https://') else f'{CARDS}{card_key}.png'


class BufferError(RuntimeError):
    pass


class MissingToken(RuntimeError):
    pass


def token(env=None):
    value = (env if env is not None else os.environ).get('BUFFER_TOKEN', '').strip()
    if not value:
        raise MissingToken('BUFFER_TOKEN is not set in the environment')
    return value


def http_send(url, body, headers):
    request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def graphql(query, variables=None, key=None, send=http_send):
    """One GraphQL call. Raises BufferError on transport or GraphQL errors; returns the data object."""
    key = key or token()
    status, raw = send(API, {'query': query, 'variables': variables or {}}, {'Authorization': f'Bearer {key}'})
    if status == 429:
        raise BufferError('Buffer rate limit reached (HTTP 429)')
    if status != 200:
        raise BufferError(f'Buffer returned HTTP {status}: {raw[:300]!r}')
    payload = json.loads(raw)
    if payload.get('errors'):
        raise BufferError('; '.join(str(e.get('message')) for e in payload['errors'])[:400])
    return payload.get('data') or {}


def organization_id(key=None, send=http_send):
    data = graphql('query { account { organizations { id } } }', key=key, send=send)
    orgs = ((data.get('account') or {}).get('organizations')) or []
    if not orgs:
        raise BufferError('the token sees no Buffer organization')
    return orgs[0]['id']


def channels(key=None, send=http_send, org=None):
    org = org or organization_id(key, send)
    data = graphql('query($org: OrganizationId!) { channels(input: {organizationId: $org}) { id name displayName service avatar isQueuePaused } }',
                   {'org': org}, key=key, send=send)
    return data.get('channels') or []


def x_channel(key=None, send=http_send, wanted=None, channel_id=None):
    """The X channel to post to: BUFFER_CHANNEL when set, else the X channel named like the account."""
    channel_id = channel_id or os.environ.get('BUFFER_CHANNEL', '').strip()
    rows = channels(key, send)
    if channel_id:
        match = next((c for c in rows if c.get('id') == channel_id), None)
        if not match:
            raise BufferError(f'channel {channel_id} is not connected to this Buffer account')
        return match
    xs = [c for c in rows if str(c.get('service') or '').lower() in ('twitter', 'x')]
    if wanted:
        named = [c for c in xs if wanted.lower().lstrip('@') in f"{c.get('name')} {c.get('displayName')}".lower()]
        xs = named or xs
    if not xs:
        raise BufferError('no X channel is connected to this Buffer account')
    return xs[0]


def daily_limit(channel_id, day, key=None, send=http_send):
    """Buffer's own posting limit for the channel on that day (a date or an ISO instant).

    Buffer answers with what is scheduled and sent; `count` and `remaining` are derived so callers can
    ask how many more posts the day can take (None when the channel has no limit)."""
    when = day if 'T' in str(day) else f'{day}T12:00:00.000Z'
    data = graphql('query($ids: [ChannelId!]!, $date: DateTime) { dailyPostingLimits(input: {channelIds: $ids, date: $date}) { channelId limit scheduled sent isAtLimit } }',
                   {'ids': [channel_id], 'date': when}, key=key, send=send)
    rows = data.get('dailyPostingLimits') or []
    if not rows:
        return None
    row = dict(rows[0])
    row['count'] = int(row.get('scheduled') or 0) + int(row.get('sent') or 0)
    row['remaining'] = max(0, int(row['limit']) - row['count']) if row.get('limit') is not None else None
    return row


CREATE = '''mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt text } }
    ... on MutationError { message }
  }
}'''

DELETE = '''mutation($id: PostId!) {
  deletePost(input: {id: $id}) {
    ... on DeletePostSuccess { id }
    ... on MutationError { message }
  }
}'''


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def create_post(text, channel_id, due_at, image_url=None, key=None, send=http_send):
    """Schedule one post for an exact time. Returns Buffer's post id."""
    payload = {'text': text, 'channelId': channel_id, 'schedulingType': 'automatic', 'mode': 'customScheduled', 'dueAt': stamp(due_at),
               'needsApproval': False, 'tagIds': [], 'assets': [{'image': {'url': image_url}}] if image_url else []}
    data = graphql(CREATE, {'input': payload}, key=key, send=send)
    result = data.get('createPost') or {}
    if result.get('message'):
        raise BufferError(f"createPost refused: {result['message']}")
    post = result.get('post') or {}
    if not post.get('id'):
        raise BufferError(f'createPost returned no post id: {result!r}')
    return post['id']


def delete_post(post_id, key=None, send=http_send):
    data = graphql(DELETE, {'id': post_id}, key=key, send=send)
    result = data.get('deletePost') or {}
    if result.get('message'):
        raise BufferError(f"deletePost refused: {result['message']}")
    return True


def reachable(url, opener=None, timeout=15):
    """Is the card already deployed? Buffer fetches the image itself, so the URL must answer before it is attached."""
    try:
        if opener:
            return bool(opener(url))
        request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'KeenRoudySports/1.0'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200 and 'image' in (response.headers.get('Content-Type') or '')
    except (urllib.error.URLError, OSError, ValueError):
        return False


# ------------------------------------------------------------------ what to schedule

def window_open(day):
    return datetime(day.year, day.month, day.day, feed.WINDOW_OPENS[0], feed.WINDOW_OPENS[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)


def taken(log_book, now):
    """When the posts already in Buffer go out: every scheduled post not cancelled, deleted or failed, from one spacing
    before now on. A new post keeps its distance from these as well as from the others it is planned with."""
    out = []
    for entry in log_book.get('posts', []):
        if entry.get('cancelledAt') or entry.get('deletedAt') or entry.get('error') or not entry.get('dueAt'):
            continue
        due = gates.when(entry['dueAt'])
        if due > now - SPACING:
            out.append(due)
    return sorted(out)


def free_slot(due, busy):
    """The first time at or after `due` at least one spacing from every busy time. Plays a later run published used to
    take the same noon slots as the queue (three pairs went out eight seconds apart on 2026-09-26)."""
    moved = True
    while moved:
        moved = False
        for other in busy:
            if abs((due - other).total_seconds()) < SPACING.total_seconds():
                due, moved = other + SPACING, True
    return due


def day_count(log_book, day):
    """Posts scheduled or sent for an Eastern day, not counting any taken back."""
    return sum(1 for entry in log_book.get('posts', []) if entry.get('dueAt') and not entry.get('cancelledAt')
               and not entry.get('deletedAt') and eastern_date(gates.when(entry['dueAt'])) == day)


def conversation_text(day, play_rows, first, games):
    """One factual, varied prompt for a multi-play card. A ready Climb or fun ticket earns a real teaser; otherwise
    ask a slate question. It goes after the first play, never pretends replies choose the card, and carries only the
    league tags the planned plays actually cover."""
    leagues = set()
    picks = []
    for row in play_rows:
        pick = first.get(row[3]) or {}
        picks.append(pick)
        for gid in pick.get('gameIds') or []:
            league = (games.get(gid) or {}).get('league')
            if league in ('NFL', 'CFB'):
                leagues.add(league)
    tags = ' '.join(f'#{league}' for league in ('CFB', 'NFL') if league in leagues)
    climb = next((p for p in picks if pick_card.play_kind(p) == 'ladder'), None)
    if climb:
        info = climb.get('ladder') or {}
        copy = (f"The 80/20 Climb is back later today. Step {info.get('step', 1)} is already cooked. 🪜\n"
                f"{pick_card.dollars(info.get('stake'))} riding · {pick_card.dollars(info.get('banked', 0))} banked.")
    elif any(pick_card.play_kind(p) == 'parlay' for p in picks):
        copy = FUN_TEASERS[day.toordinal() % len(FUN_TEASERS)]
    else:
        copy = CONVERSATION[day.toordinal() % len(CONVERSATION)]
    return f'{copy}\n\n{tags}'.rstrip()


def fit_limit(plans, remaining):
    """Respect Buffer's live allowance without optional conversation, news or research displacing essentials."""
    if remaining is None or remaining >= len(plans):
        return plans
    remaining = max(0, int(remaining))
    essential = [plan for plan in plans if plan[1] not in ('conversation', 'news', 'research')]
    optional = [plan for plan in plans if plan[1] in ('conversation', 'news', 'research')]
    chosen = essential[:remaining]
    if len(chosen) < remaining:
        chosen += optional[:remaining - len(chosen)]
    return sorted(chosen, key=lambda plan: plan[3])


def plan(first, latest, games, now, log_book, player_team=None, soon=None, quotes=None, refused=None, news=None):
    """The posts the run should schedule now: [(key, kind, text, due_at, card_key)].

    X gets plays, their receipts and one short prompt between the first two plays of a multi-play card. Player props,
    game lines and the day's fun parlay use the same shape every time and always carry the card; the morning after,
    the receipt (scripts/receipts.py) goes at 9:00 AM ET,
    ahead of that morning's plays; on Wednesday the week's receipt too. Plays go out around noon Eastern on game
    day (a game before 2 PM posts two hours ahead of its kickoff, a parlay by its first leg; never before 9:00 AM),
    player props first, then game lines, then the parlay, ten minutes apart. A play published later than its time goes out now, unless kickoff is inside
    45 minutes. Posted, closed, settled and historical plays are left out.
    `soon` replaces the two-minute lead, for a person who wants time to look at the queue first. A post whose text
    fails its check is left out and, when `refused` is a list, named there with the problems, so it is never silent.
    """
    soon = soon if soon is not None else SOON
    import learning
    weights = learning.load_policy().get('reasonWeights')
    # A post can stand for two (the morning receipt that carries the menu is keyed "receipt:...+menu:..."): neither
    # goes out again on its own.
    posted = {part for p in log_book.get('posts', []) for part in str(p['id']).split('+')}
    today = eastern_date(now)
    import featured as featured_store
    potd = featured_store.of_day(today.isoformat())     # the day's Pick of the Day: first, its own card
    opens = window_open(today)
    plays = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if key in posted or pick.get('historicalImport') or not feed.postable(merged):
            continue
        if merged.get('result') or merged.get('entryNote') or (merged.get('status') or 'active') != 'active':
            continue
        starts = sorted(games[g]['kickoff'] for g in (merged.get('gameIds') or []) if g in games)
        if not starts or eastern_date(gates.when(starts[0])) != today:
            continue
        game = games.get((merged.get('gameIds') or [None])[0])
        now_quote = (quotes or {}).get(key)
        text = x_post.draft(merged, game, weights, now_quote=now_quote, featured=key == potd)
        problems = x_post.guard(text, merged, x_post.load_reasons().get(key), now_quote)
        if problems:
            if refused is not None:
                refused.append((key, problems))
            continue
        kickoff = gates.when(starts[0])
        noon = datetime(today.year, today.month, today.day, POST_AT[0], POST_AT[1], tzinfo=gates.EASTERN).astimezone(timezone.utc)
        plays.append((max(min(noon, kickoff - EARLY_LEAD), opens), -1 if key == potd else ORDER[pick_card.play_kind(merged)],
                      kickoff - feed.LEAD, key, text, 'play', f'{key}-potd' if key == potd else key))
    order = {'menu': -2, 'receipt': -1, 'book': -1, 'sheet': 0, 'research': 1, 'cashed': 2}
    for post in receipts.house_posts(first, latest, games, log_book, now):
        if set(post['key'].split('+')) & posted:
            continue
        problems = receipts.guard(post)
        if problems:
            if refused is not None:
                refused.append((post['key'], problems))
            continue
        plays.append((post['due'], order[post['kind']], post['stale'], post['key'], post['text'], post['kind'], post['card']))
    # News is useful but optional. Reserve every official play and house post first, then admit no more news than
    # the day's remaining room. A late headline can never crowd a pick or receipt out of the queue.
    essential_today = sum(1 for row in plays if eastern_date(row[0]) == today)
    news_room = max(0, MAX_PER_DAY - day_count(log_book, today) - essential_today)
    for item in (news or [])[:news_room]:
        if item['key'] not in posted:
            plays.append((item['target'], -3, item['deadline'], item['key'], item['text'], 'news', None))
    # Informational Climb check-ins must never delay the official card or its normal conversation slot.
    plays.sort(key=lambda row: (row[3].startswith('climb:checkin:'), row))
    play_rows = [row for row in plays if row[5] == 'play']
    conversation_key = f'conversation:day:{today.isoformat()}'
    planned_today = sum(1 for row in plays if eastern_date(row[0]) == today)
    room_for_prompt = day_count(log_book, today) + planned_today < MAX_PER_DAY
    if conversation_key not in posted and len(play_rows) >= 2 and room_for_prompt:
        first_index = next(i for i, row in enumerate(plays) if row is play_rows[0])
        prompt = (play_rows[0][0], play_rows[0][1], min(play_rows[0][2], play_rows[1][2]), conversation_key,
                  conversation_text(today, play_rows, first, games), 'conversation', None)
        plays.insert(first_index + 1, prompt)
    # The desk's own ceiling gets the same protection as Buffer's allowance. A research card is useful, but never
    # at the cost of a play, receipt, sheet, menu or record post.
    room = max(0, MAX_PER_DAY - day_count(log_book, today))
    todays = [row for row in plays if eastern_date(row[0]) == today]
    overflow = max(0, len(todays) - room)
    if overflow:
        for kind in ('research', 'conversation', 'news'):
            for row in list(plays):
                if overflow <= 0:
                    break
                if row[5] == kind and eastern_date(row[0]) == today:
                    plays.remove(row)
                    overflow -= 1
    out, last, busy, counts = [], None, taken(log_book, now), {}
    for target, _, deadline, key, text, kind, card in plays:
        due = max(target, now + soon)
        if last is not None:
            due = max(due, last + SPACING)
        due = free_slot(due, busy)
        if due > deadline:
            continue                    # this one's window has passed; a later one may still fit
        day = eastern_date(due)
        counts.setdefault(day, day_count(log_book, day))
        if counts[day] >= MAX_PER_DAY:
            continue
        out.append((key, kind, text, due, card))
        busy.append(due)
        counts[day] += 1
        last = due
    return out


def schedule(plans, channel_id, log_book, now, key=None, send=http_send, opener=None, log=print):
    """Create the planned posts in Buffer and record each in the log; a play whose card is not live yet is left
    for the next run, never posted bare. Returns the log."""
    for guid, kind, text, due, card_key in plans:
        image = None
        if card_key:
            url = card_url(card_key)
            image = url if reachable(url, opener) else None
            if not image:
                log(f'buffer: {guid} waits: its card is not live yet (every post carries its card)')
                continue
        try:
            post_id = create_post(text, channel_id, due, image, key=key, send=send)
        except BufferError as error:
            log(f'buffer: {guid} not scheduled: {error}')
            continue
        entry = {'id': guid, 'postedAt': gates.stamp(now), 'dueAt': gates.stamp(due), 'bufferPostId': post_id,
                 'textHash': x_post.text_hash(text), 'kind': f'buffer:{kind}', 'card': bool(image)}
        # Only entries scheduled after Discord mirroring was introduced carry this payload. That prevents enabling
        # the webhook from replaying the account's older X history into a new server.
        entry['discord'] = {'state': 'pending', 'text': text}
        if kind == 'play':
            # A confirmed play is the reason to join Discord. Schedule it first; the lightweight delivery job runs
            # every five minutes, so a 15-minute target gives members roughly 10-15 minutes before the X post.
            entry['discord']['readyAt'] = gates.stamp(max(now, due - DISCORD_PLAY_LEAD))
        if image:
            entry['discord']['image'] = image
        if image and card_key and card_key != guid:
            entry['cardKey'] = card_key            # a Pick of the Day's own card; a requote keeps it
        if str(card_key or '').endswith('-potd'):
            entry['featured'] = True
        if kind == 'play':
            entry['reasonKind'] = x_post.reason_kind(x_post.reason_in(text))      # what learning compares engagement by
        log_book.setdefault('posts', []).append(entry)
        log(f"buffer: {guid} scheduled for {due.astimezone(gates.EASTERN):%a %-I:%M %p} ET" + (' with card' if image else ''))
    return log_book


def cancel_closed(closed_ids, log_book, now, key=None, send=http_send, log=print):
    """Take back a scheduled post whose pick closed before its time."""
    for entry in log_book.get('posts', []):
        if entry.get('id') in closed_ids and entry.get('bufferPostId') and not entry.get('cancelledAt') \
                and entry.get('dueAt') and gates.when(entry['dueAt']) > now:
            try:
                delete_post(entry['bufferPostId'], key=key, send=send)
                entry['cancelledAt'] = gates.stamp(now)
                mirror = entry.get('discord') or {}
                if mirror.get('state') == 'sent' and not mirror.get('followup'):
                    headline = str(mirror.get('text') or entry['id']).splitlines()[0]
                    mirror['followup'] = {
                        'state': 'pending',
                        'text': (f"⚠️ UPDATE: {headline}\n\nPulled before the X post because of confirmed hard news. "
                                 "It stays in the public record and will be graded."),
                    }
                    entry['discord'] = mirror
                log(f"buffer: {entry['id']} cancelled, the pick closed before its post went out")
            except BufferError as error:
                log(f"buffer: could not cancel {entry['id']}: {error}")
    return log_book


STATUS = 'query($id: PostId!) { post(input: {id: $id}) { id status sentAt externalLink error { message } } }'
METRICS = 'query($id: PostId!) { post(input: {id: $id}) { id metricsUpdatedAt metrics { type value } } }'
SETTLE_METRICS = timedelta(hours=48)     # engagement is read once, two days after a post went out


def collect_metrics(log_book, now, key=None, send=http_send, log=print):
    """Read each sent post's engagement once, two days after it went out, into the log for learning. Needs the
    key's insights:read permission; without it this says so once and leaves everything as it was."""
    read = 0
    for entry in log_book.get('posts', []):
        if not entry.get('bufferPostId') or not entry.get('sentAt') or entry.get('metricsAt') or entry.get('deletedAt'):
            continue
        if gates.when(entry['sentAt']) > now - SETTLE_METRICS:
            continue
        try:
            post = graphql(METRICS, {'id': entry['bufferPostId']}, key=key, send=send).get('post') or {}
        except BufferError as error:
            if 'insights' in str(error).lower() or 'scope' in str(error).lower():
                log('buffer: engagement not read: the key lacks the insights:read permission')
                return read
            log(f"buffer: engagement for {entry['id']} not read: {error}")
            continue
        entry['metrics'] = {m['type']: m['value'] for m in post.get('metrics') or [] if isinstance(m.get('value'), (int, float))}
        entry['metricsAt'] = gates.stamp(now)
        read += 1
    return read


def reconcile(log_book, now, key=None, send=http_send, log=print):
    """Ask Buffer what became of each post whose time has passed, once: the X link when it went out, the
    message when it failed. Returns the entries that failed, for the run to raise."""
    failed = []
    for entry in log_book.get('posts', []):
        if not entry.get('bufferPostId') or entry.get('cancelledAt') or entry.get('sentAt') or entry.get('error'):
            continue
        if not entry.get('dueAt') or gates.when(entry['dueAt']) > now:
            continue
        try:
            post = graphql(STATUS, {'id': entry['bufferPostId']}, key=key, send=send).get('post') or {}
        except BufferError as error:
            log(f"buffer: could not check {entry['id']}: {error}")
            continue
        status = post.get('status')
        if status == 'sent':
            link = post.get('externalLink') or ''
            entry['sentAt'] = post.get('sentAt') or gates.stamp(now)
            entry['link'] = link or None
            entry['tweetId'] = link.rstrip('/').rsplit('/', 1)[-1] if '/status/' in link else None
            log(f"buffer: {entry['id']} went out: {link or 'no link returned'}")
        elif status == 'error':
            entry['error'] = ((post.get('error') or {}).get('message')) or 'Buffer reports an error without a message'
            failed.append(entry)
            log(f"buffer: {entry['id']} FAILED to post: {entry['error']}")
    return failed


# ------------------------------------------------------------------ command line

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('channels', 'limits', 'plan', 'schedule', 'post', 'reconcile'))
    parser.add_argument('pick_id', nargs='?')
    parser.add_argument('--at', help='UTC instant for the post; default now plus two minutes')
    parser.add_argument('--soon', type=int, help='minutes of lead for anything the plan would post right away (default 2)')
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args(argv)
    soon = timedelta(minutes=args.soon) if args.soon else None
    now = datetime.now(timezone.utc)
    try:
        if args.command == 'channels':
            for c in channels():
                print(f"{c['id']}  {c.get('service')}  {c.get('name')}  ({c.get('displayName')})" + ('  [queue paused]' if c.get('isQueuePaused') else ''))
            return 0
        if args.command == 'limits':
            channel = x_channel(wanted='keenkooks')
            print(json.dumps(daily_limit(channel['id'], eastern_date(now).isoformat()), indent=1))
            return 0
        if args.command == 'reconcile':
            log_book = x_post.load_log()
            failed = reconcile(log_book, now)
            x_post.save_log(log_book)
            return 1 if failed else 0
        stores = gates.Stores()
        ctx = stores.as_of(now)
        log_book = x_post.load_log()
        if args.command in ('plan', 'schedule'):
            quotes = {k: q for k in ctx.first if (q := gates.best_now(dict(ctx.first[k], **ctx.latest.get(k, {})), ctx))}
            plans = plan(ctx.first, ctx.latest, ctx.games, now, log_book, ctx.player_team, soon=soon, quotes=quotes)
            for guid, kind, text, due, card in plans:
                print(f"{due.astimezone(gates.EASTERN):%a %-I:%M %p} ET  {kind:<10} {guid}" + (f"  card {CARDS}{card}.png" if card else ''))
                print('    ' + text.replace('\n', ' / '))
            if args.command == 'plan' or not plans:
                print(f'{len(plans)} posts would be scheduled')
                return 0
            if not args.confirm:
                print(f'\n{len(plans)} not scheduled: add --confirm')
                return 0
            channel = x_channel(wanted='keenkooks')
            limit = daily_limit(channel['id'], eastern_date(now).isoformat())
            if limit and limit.get('remaining') is not None and limit['remaining'] < len(plans):
                print(f"the channel can take {limit['remaining']} more posts today; scheduling that many")
                plans = plans[:max(0, limit['remaining'])]
            before = len(log_book.get('posts', []))
            schedule(plans, channel['id'], log_book, now)
            x_post.save_log(log_book)
            print(f"{len(log_book.get('posts', [])) - before} scheduled and logged in data/x-posted.json")
            return 0
        pick = ctx.first.get(args.pick_id)
        if not pick:
            sys.exit(f'{args.pick_id} is not in research/')
        merged = dict(pick, **ctx.latest.get(args.pick_id, {}))
        game = ctx.games.get((pick.get('gameIds') or [None])[0])
        text = x_post.draft(merged, game)
        due = gates.when(args.at) if args.at else now + SOON
        print(f'{text}\n\n{x_post.tweet_length(text)} characters, due {due.astimezone(gates.EASTERN):%a %-I:%M %p} ET')
        if not args.confirm:
            print('\nnot scheduled: add --confirm')
            return 0
        x_post.refuse(merged, game, log_book, now, text)
        channel = x_channel(wanted='keenkooks')
        schedule([(args.pick_id, 'play', text, due, args.pick_id)], channel['id'], log_book, now)
        x_post.save_log(log_book)
        print('scheduled and logged')
        return 0
    except (BufferError, MissingToken, x_post.Refused) as error:
        print(f'refused: {error}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
