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
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed
import gates
import pick_card
import quota
import post_windows
import receipts
import x_post
import social_style
import parlay_caption
import social_voice
import social_learning
from social_copy import (without_playbook, x_ticket_copy, with_age_notice,
                         age_notice_current, AGE_VERSION, AGE_EFFECTIVE, canonical_caption)
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.buffer.com'
CARDS = x_post.SITE + 'data/cards/'
POST_AT = (9, 30)                    # Eastern game-day target; early international games retain 8:30
SPACING = timedelta(minutes=20)      # owner plan: plays go out about twenty minutes apart
RESULT_SPACING = timedelta(minutes=10)  # settled reactions keep the approved faster cadence
SOON = timedelta(minutes=2)          # a post scheduled "now" goes out this far ahead
ORDER = {'player': 0, 'team': 1, 'ladder': 2, 'parlay': 3}   # inside one kickoff: player props, game lines, the ladder, the parlay
MAX_PER_DAY = 20                     # our ceiling; Buffer's free queue holds only 10 scheduled posts at once
BUFFER_QUEUE = 10
BUFFER_NORMAL_LIMIT = 9              # keep the tenth place free for relabels and reschedules
BUFFER_RESERVED = 3                  # preserve the final places for plays, relabels/reschedules and receipts
BUFFER_OPTIONAL_AT = BUFFER_QUEUE - BUFFER_RESERVED
BUFFER_ESSENTIAL = frozenset(('play', 'receipt', 'cashed', 'community'))
BUFFER_TEMP_ESSENTIAL = frozenset(('play', 'nba-trial', 'receipt', 'cashed'))
DISCORD_PLAY_LEAD = post_windows.DISCORD_PLAY_LEAD  # one admission and scheduling window
DISCORD_DELIVERY_CADENCE = post_windows.DISCORD_DELIVERY_CADENCE
def card_url(card_key):
    """Where a post's card lives: a house card (menu, book) by its full address, a play's or a receipt's under
    data/cards/ by its key."""
    return str(card_key) if str(card_key).startswith('https://') else f'{CARDS}{card_key}.png'


def live_card_url(card_key, opener=None):
    """Return a deployed card URL, retrying through a stable cache-busting URL.

    Cloudflare may retain a short-lived 404 for the canonical path when a new
    result card is probed before Pages finishes. The versioned URL addresses
    the same immutable file without waiting for that negative cache to expire.
    """
    url = card_url(card_key)
    if reachable(url, opener):
        return url
    joiner = '&' if '?' in url else '?'
    version = hashlib.sha256(str(card_key).encode('utf-8')).hexdigest()[:12]
    fresh = f'{url}{joiner}v={version}'
    return fresh if reachable(fresh, opener) else None


class BufferError(RuntimeError):
    pass


class BufferRateLimited(BufferError):
    def __init__(self, retry_at, window='unknown'):
        self.retry_at, self.window = retry_at, window
        super().__init__(f'Buffer rate limit ({window}); retry after {stamp(retry_at)}')


def rate_path():
    return Path(os.environ.get('KEENROUDY_CONF') or Path.home()/'.config/keenroudy')/'buffer-rate-limit.json'


def rate_backoff(now=None):
    now = now or datetime.now(timezone.utc)
    try:
        row = json.loads(rate_path().read_text())
        retry = datetime.fromisoformat(row['retryAt'].replace('Z', '+00:00'))
        if retry > now:
            return BufferRateLimited(retry, row.get('window', 'unknown'))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def remember_rate_limit(raw, headers, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        seconds = max(60, int({k.lower():v for k,v in headers.items()}.get('retry-after') or 900))
    except (TypeError, ValueError):
        seconds = 900
    window = 'unknown'
    try:
        value = json.loads(raw)['errors'][0]['extensions']['window']
        if value in ('15m', '24h', '30d'):
            window = value
    except (ValueError, KeyError, IndexError, TypeError):
        pass
    error = BufferRateLimited(now + timedelta(seconds=seconds), window)
    path = rate_path(); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'retryAt': stamp(error.retry_at), 'window': window})+'\n')
    temporary.replace(path)
    return error


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
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)


def graphql(query, variables=None, key=None, send=http_send, essential=False):
    """One GraphQL call. Raises BufferError on transport or GraphQL errors; returns the data object."""
    key = key or token()
    if send is http_send:
        blocked = rate_backoff()
        if blocked:
            raise blocked
        try:
            operation = ('analytics' if query == METRICS else 'publish' if query == CREATE
                         else 'status' if query == STATUS else 'cancel' if query == DELETE
                         else 'limits' if 'dailyPostingLimits' in query else 'channels'
                         if 'organizations' in query or 'channels(input:' in query else 'other')
            quota.count_request('buffer', optional=query == METRICS, operation=operation, essential=essential)
        except quota.QuotaBlocked as error:
            raise BufferError(str(error)) from None
    response = send(API, {'query': query, 'variables': variables or {}}, {'Authorization': f'Bearer {key}'})
    status, raw = response[:2]
    if status == 429:
        if send is http_send:
            raise remember_rate_limit(raw, response[2] if len(response) > 2 else {})
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
    cache = rate_path().with_name('buffer-channel-cache.json')
    identity = hashlib.sha256(f'{key or token()}|{channel_id}|{wanted}'.encode()).hexdigest() if send is http_send else None
    if identity:
        try:
            saved = json.loads(cache.read_text())
            age = datetime.now(timezone.utc)-gates.when(saved['checkedAt'])
            if saved['identity'] == identity and timedelta(0) <= age < timedelta(hours=1) and saved['channel'].get('id'):
                return saved['channel']
        except (OSError, ValueError, KeyError, TypeError):
            pass
    rows = channels(key, send)
    if channel_id:
        match = next((c for c in rows if c.get('id') == channel_id), None)
        if not match:
            raise BufferError(f'channel {channel_id} is not connected to this Buffer account')
        chosen = match
    else:
        xs = [c for c in rows if str(c.get('service') or '').lower() in ('twitter', 'x')]
        if wanted:
            named = [c for c in xs if wanted.lower().lstrip('@') in f"{c.get('name')} {c.get('displayName')}".lower()]
            xs = named or xs
        if not xs:
            raise BufferError('no X channel is connected to this Buffer account')
        chosen = xs[0]
    if identity:
        cache.parent.mkdir(parents=True,exist_ok=True)
        temporary=cache.with_suffix('.tmp')
        temporary.write_text(json.dumps({'identity':identity,'checkedAt':stamp(datetime.now(timezone.utc)),'channel':chosen})+'\n')
        temporary.replace(cache)
    return chosen


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


def create_post(text, channel_id, due_at, image_url=None, key=None, send=http_send, essential=False):
    """Schedule one post for an exact time. Returns Buffer's post id."""
    text = with_age_notice(text)
    if x_post.tweet_length(text) > x_post.LIMIT:
        raise BufferError('complete caption including age notice exceeds X limit')
    if x_post.x_style(text):
        raise BufferError('outgoing copy fails the public voice check')
    payload = {'text': text, 'channelId': channel_id, 'schedulingType': 'automatic', 'mode': 'customScheduled', 'dueAt': stamp(due_at),
               'needsApproval': False, 'tagIds': [], 'assets': [{'image': {'url': image_url}}] if image_url else []}
    data = graphql(CREATE, {'input': payload}, key=key, send=send, essential=essential)
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


def ticket_art_live(url, timeout=15):
    """Fail closed on a reachable but pre-cutover play image."""
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'KeenRoudySports/1.0',
                                                       'Range': 'bytes=0-255'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            prefix = response.read(256)
        return prefix.startswith(b'\x89PNG\r\n\x1a\n') and b'KooknTheme\x00ticket' in prefix
    except (urllib.error.URLError, OSError, ValueError):
        return False


def plain_art_live(url, timeout=15):
    """Read the native renderer's policy attestation, never guess from file date."""
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'KeenRoudySports/1.0', 'Range': 'bytes=0-255'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            prefix = response.read(256)
        return prefix.startswith(b'\x89PNG\r\n\x1a\n') and social_style.MARKER in prefix
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


def free_slot(due, busy, spacing=SPACING):
    """The first time at or after `due` at least one spacing from every busy time. Plays a later run published used to
    take the same noon slots as the queue (three pairs went out eight seconds apart on 2026-09-26)."""
    moved = True
    while moved:
        moved = False
        for other in busy:
            if abs((due - other).total_seconds()) < spacing.total_seconds():
                due, moved = other + spacing, True
    return due


def day_count(log_book, day):
    """Posts scheduled or sent for an Eastern day, not counting any taken back."""
    return sum(1 for entry in log_book.get('posts', []) if entry.get('dueAt') and not entry.get('cancelledAt')
               and not entry.get('deletedAt') and eastern_date(gates.when(entry['dueAt'])) == day)


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


def discord_first_due(now):
    """Next ten-minute X slot allowing a full Discord lead and one delivery tick."""
    return post_windows.delivery_ready(now)


def yield_optional(log_book, desired, now, channel_id, key=None, send=http_send):
    """Move at most two unsent routine posts, never a public play or sent post.

    Keep copy/art intact and preserve every prior Buffer identity as a receipt.
    Restore the original schedule if its replacement is refused.
    """
    moved=[]
    for entry in sorted(log_book.get('posts',[]),key=lambda r:r.get('dueAt') or ''):
        if len(moved)>=2:break
        if entry.get('kind') not in ('buffer:receipt','buffer:book'):continue
        if any(entry.get(k) for k in ('sentAt','cancelledAt','deletedAt','error')) or not entry.get('bufferPostId'):continue
        old_due=gates.when(entry['dueAt'])
        if old_due<=now+SOON or abs((old_due-desired).total_seconds())>=SPACING.total_seconds():continue
        query='query($id: PostId!) { post(input: {id: $id}) { id status text } }'
        post=graphql(query,{'id':entry['bufferPostId']},key=key,send=send).get('post') or {}
        if post.get('status')!='scheduled' or x_post.text_hash(post.get('text',''))!=entry.get('textHash'):continue
        busy=taken({'posts':[r for r in log_book['posts'] if r is not entry]},now)+[desired]
        due=free_slot(max(old_due,desired+SPACING),busy)
        if eastern_date(due)!=eastern_date(old_due):continue
        # Do not carry a time-sensitive research quote past its existing cutoff.
        import nba_editorial
        snapshot=next((r for r in nba_editorial.stored() if r['key']==entry['id']),None)
        if snapshot and due>=gates.when(snapshot['stale']):continue
        mirror=entry.get('discord') or {}
        image=(mirror.get('image') or card_url(entry.get('cardKey') or entry['id'])) if entry.get('card') else None
        old_id=entry['bufferPostId']
        delete_post(old_id,key=key,send=send)
        entry.setdefault('deliveryHistory',[]).append({'bufferPostId':old_id,'dueAt':gates.stamp(old_due),
            'rescheduledAt':gates.stamp(now),'reason':'Fresh official play takes priority'})
        try:new_id=create_post(post['text'],channel_id,due,image,key=key,send=send)
        except BufferError:
            try:entry['bufferPostId']=create_post(post['text'],channel_id,old_due,image,key=key,send=send)
            except BufferError:
                entry['error']='Optional post rescheduling and restoration failed; operator recovery required'
            raise
        entry.update(bufferPostId=new_id,dueAt=gates.stamp(due),rescheduledAt=gates.stamp(now))
        moved.append(entry['id'])
    return moved


def plan(first, latest, games, now, log_book, player_team=None, soon=None, quotes=None, refused=None, news=None, log=print):
    """The posts the run should schedule now: [(key, kind, text, due_at, card_key)].

    X gets plays and their receipts. Player props,
    game lines and the day's fun parlay use the same shape every time and always carry the card; the morning after,
    the receipt (scripts/receipts.py) goes at 9:00 AM ET,
    ahead of that morning's plays; on Wednesday the week's receipt too. Plays target 9:30 AM Eastern on game
    day (8:30 for a kickoff before 10:30), Hot Plate first, then other plays about twenty minutes apart.
    A play published later than its time uses the next safe Discord-first slot, unless kickoff is inside
    45 minutes. Posted, closed, settled and historical plays are left out.
    `soon` replaces the two-minute lead, for a person who wants time to look at the queue first. A post whose text
    fails its check is left out and, when `refused` is a list, named there with the problems, so it is never silent.
    """
    soon = soon if soon is not None else SOON
    import learning
    weights = learning.load_policy().get('reasonWeights')
    # Legacy merged receipt/menu ids remain recognized, but no new menu is made.
    posted = {part for p in log_book.get('posts', []) if not x_post.cancelled_private_draft(p)
              for part in str(p['id']).split('+')}
    today = eastern_date(now)
    import featured as featured_store
    potd = featured_store.of_day(today.isoformat())     # the day's Pick of the Day: first, its own card
    opens = window_open(today)
    plays = []
    late_card_recoveries = set()
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if key in posted or pick.get('historicalImport') or merged.get('_pendingRelease') or not feed.postable(merged):
            continue
        if merged.get('result') or merged.get('entryNote') or (merged.get('status') or 'active') != 'active':
            continue
        starts = sorted(games[g]['kickoff'] for g in (merged.get('gameIds') or []) if g in games)
        if not starts or eastern_date(gates.when(starts[0])) != today:
            continue
        game = games.get((merged.get('gameIds') or [None])[0])
        kickoff = gates.when(starts[0])
        league = merged.get('league') or (game or {}).get('league')
        normal_reachable = post_windows.reachable(
            league, kickoff, now, replacement=bool(merged.get('replacementOf')),
            late_admission=not bool(merged.get('publishedAt')))
        late_card_recovery = (not normal_reachable and not merged.get('replacementOf')
                              and bool(merged.get('publishedAt')) and now >= post_windows.target(league, kickoff)
                              and post_windows.late_card_reachable(kickoff, now))
        if not normal_reachable and not late_card_recovery:
            if refused is not None:
                refused.append((key, ['replacement has no last-look window'] if merged.get('replacementOf')
                                     else ['has no X window']))
            continue
        now_quote = (quotes or {}).get(key)
        text = x_post.draft(merged, game, weights, now_quote=now_quote, featured=key == potd,
                            history=log_book.get('posts', []))
        problems = x_post.guard(text, merged, x_post.reason_in(text), now_quote)
        if problems:
            if refused is not None:
                refused.append((key, problems))
            continue
        target = post_windows.target(league, kickoff)
        deadline = post_windows.deadline(league, kickoff, now, bool(merged.get('replacementOf')))
        if late_card_recovery:
            # The play was already selected; only its required art missed the
            # ordinary window. Re-enter it until a real 10-minute Discord-first
            # recovery slot remains, rather than silently losing the play.
            target = post_windows.late_card_due(now) - post_windows.jitter(key)
            deadline = kickoff - post_windows.LATE_CARD_LEAD
            late_card_recoveries.add(key)
        if merged.get('replacementOf'):
            # A replacement needs a fresh last look; never rush it out shortly
            # before kickoff just because its normal publication slot passed.
            target = max(target, now + timedelta(minutes=45))
            if target > deadline:
                if refused is not None:
                    refused.append((key, ['replacement has no last-look window']))
                continue
        plays.append((target, -1 if key == potd else ORDER[pick_card.play_kind(merged)],
                      deadline, key, text, 'play', f'{key}-potd' if key == potd else key))
    order = {'receipt': -1, 'book': -1, 'sheet': 0, 'research': 1, 'cashed': 2, 'sports': 3}
    for post in receipts.house_posts(first, latest, games, log_book, now, log=log):
        if set(post['key'].split('+')) & posted:
            continue
        problems = receipts.guard(post)
        if problems:
            if refused is not None:
                refused.append((post['key'], problems))
            continue
        # Weekly category totals read cleanly as text. Do not send the retired
        # summary artwork or hold the existing result category indefinitely.
        # Daily receipts and every official play retain their required cards.
        weekly_text = post['kind'] == 'receipt' and re.fullmatch(r'receipt:week:\d{4}-\d{2}-\d{2}', post['key'])
        card = None if weekly_text else post['card']
        plays.append((post['due'], order[post['kind']], post['stale'], post['key'], post['text'], post['kind'], card))
    # News is useful but optional. Reserve every official play and house post first, then admit no more news than
    # the day's remaining room. A late headline can never crowd a pick or receipt out of the queue.
    essential_today = sum(1 for row in plays if eastern_date(row[0]) == today)
    news_room = max(0, MAX_PER_DAY - day_count(log_book, today) - essential_today)
    for item in (news or [])[:news_room]:
        if item['key'] not in posted:
            plays.append((item['target'], -3, item['deadline'], item['key'], item['text'], 'news', None))
    # Research follows the full morning play batch, even when the batch is longer than six posts.
    latest_play_target = max((row[0] for row in plays if row[5] == 'play'), default=None)
    if latest_play_target is not None:
        plays = [(max(row[0], latest_play_target + SPACING), *row[1:]) if row[5] == 'research' and not row[3].startswith('nba-') else row
                 for row in plays]
    plays.sort(key=lambda row: row)
    # The desk's own ceiling gets the same protection as Buffer's allowance. A research card is useful, but never
    # at the cost of a play, receipt or record post.
    room = max(0, MAX_PER_DAY - day_count(log_book, today))
    todays = [row for row in plays if eastern_date(row[0]) == today]
    overflow = max(0, len(todays) - room)
    if overflow:
        for kind in ('sports', 'research', 'conversation', 'news'):
            for row in list(plays):
                if overflow <= 0:
                    break
                if row[5] == kind and eastern_date(row[0]) == today:
                    plays.remove(row)
                    overflow -= 1
    out, last, busy, counts = [], None, taken(log_book, now), {}
    for target, _, deadline, key, text, kind, card in plays:
        spacing = RESULT_SPACING if kind == 'cashed' else SPACING
        target += post_windows.jitter(key)
        due = max(target, now + soon)
        if kind == 'play':
            due = max(due, post_windows.late_card_due(now) if key in late_card_recoveries else discord_first_due(now))
        if last is not None:
            due = max(due, last + spacing)
        due = free_slot(due, busy, spacing=spacing)
        if due > deadline:
            if kind == 'play' and refused is not None:
                refused.append((key, ['has no X window']))
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


def chosen_not_posted(first, latest, games, log_book, now):
    """IDs selected for today's slate that still have no delivery-log row."""
    posted = {part for row in log_book.get('posts', []) if not x_post.cancelled_private_draft(row)
              for part in str(row.get('id') or '').split('+')}
    today = eastern_date(now)
    missing = []
    for key, original in first.items():
        pick = dict(original, **latest.get(key, {}))
        starts = [gates.when(games[gid]['kickoff']) for gid in pick.get('gameIds') or [] if gid in games]
        if (key in posted or pick.get('_pendingRelease') or not pick.get('publishedAt') or not starts or eastern_date(min(starts)) != today
                or min(starts) <= now or pick.get('result') or pick.get('entryNote')
                or (pick.get('status') or 'active') != 'active'):
            continue
        if feed.postable(pick):
            missing.append(key)
    return sorted(missing)


def pending_scheduled(log_book, now):
    """Known posts still occupying one of Buffer's ten free scheduled places."""
    count = 0
    for entry in log_book.get('posts') or []:
        if not entry.get('bufferPostId') or entry.get('sentAt') or entry.get('cancelledAt') \
                or entry.get('deletedAt') or entry.get('error') or not entry.get('dueAt'):
            continue
        try:
            future = gates.when(entry['dueAt']) > now
        except (TypeError, ValueError):
            future = False
        count += int(future)
    return count


def theme_moment(guid, kind, due, items=None):
    """Use the same stored moment the hosted renderer uses for this artifact."""
    source_id = guid
    if kind == 'cashed':
        source_id = next((guid[len(prefix):] for prefix in ('cashed:', 'burnt:', 'ladder-loss:', 'ladder-push:', 'ladder-void:')
                          if guid.startswith(prefix)), guid)
    item = (items or {}).get(source_id) or {}
    if kind == 'play':
        return due  # The unpublished attachment is built for its outbound publication, not the old play date.
    if kind == 'cashed':
        return next((item.get(field) for field in ('settledAt', 'publishedAt', 'day') if item.get(field)), due)
    return due


def missed_target(guid, due, now, items=None):
    item = (items or {}).get(guid) or {}
    target = post_windows.target(item.get('league'), item['kickoff']) if item.get('kickoff') else due
    return now >= target


def owner_slip_image(guid, kind, card_key, items=None, now=None):
    """Historical exception only; future owner art needs the native privacy check."""
    if (now or datetime.now(timezone.utc)) >= social_style.PRIVACY_EFFECTIVE:
        return False
    item = (items or {}).get(guid) or {}
    path = str(item.get('card') or '')
    return bool(kind == 'community' and guid.startswith('community:personal-ticket:')
                and item.get('personalTicket') is True
                and re.fullmatch(r'img/tickets/[A-Za-z0-9_-]+\.(?:png|jpg)', path)
                and card_key == x_post.SITE + path)


def schedule(plans, channel_id, log_book, now, key=None, send=http_send, opener=None, log=print, stats=None, items=None):
    """Create the planned posts in Buffer and record each in the log; a play whose card is not live yet is left
    for the next run, never posted bare. Returns the log."""
    stats = stats if stats is not None else {}
    stats.setdefault('officialNotScheduled', 0)
    # An owner-submitted ticket is community content even if a caller labels
    # its Buffer tuple "play". The id namespace is authoritative for routing.
    plans = [(guid, 'community' if guid.startswith('community:') else kind, text, due, card_key)
             for guid, kind, text, due, card_key in plans]
    pending = pending_scheduled(log_book, now)
    # Tickets and result follow-ups get queue capacity before optional updates,
    # even before pressure reaches the reserve threshold. Due times stay intact.
    plans = sorted(plans, key=lambda plan: (plan[1] not in BUFFER_ESSENTIAL, plan[3], plan[0]))
    for guid, kind, text, due, card_key in plans:
        prior = next((p for p in reversed(log_book.get('posts', []))
                      if p.get('id') == guid and x_post.cancelled_private_draft(p)), None)
        corrections = (prior or {}).get('captionCorrections') or []
        if (kind == 'play' and prior and (prior.get('discord') or {}).get('state') == 'sent'
                and corrections and corrections[-1].get('observedText') == prior.get('queuedText')
                and x_post.text_hash(prior['queuedText']) == prior.get('textHash')):
            text = prior['queuedText']
        if pending >= BUFFER_NORMAL_LIMIT or (pending >= BUFFER_OPTIONAL_AT and kind not in BUFFER_ESSENTIAL):
            if kind == 'play' and missed_target(guid, due, now, items):
                stats['officialNotScheduled'] += 1
            reason = 'the tenth Buffer place is reserved' if pending >= BUFFER_NORMAL_LIMIT else 'the final three Buffer places are reserved'
            log(f'buffer: {guid} deferred: {reason} ({pending}/{BUFFER_QUEUE} scheduled)')
            continue
        if kind != 'play':
            text = without_playbook(text)
        item = (items or {}).get(guid, {})
        if kind == 'community' and guid.startswith('community:personal-ticket:') and len(item.get('legs') or []) > 1:
            try:
                text = parlay_caption.owner_ticket(item)
            except (KeyError, TypeError, ValueError):
                log(f'buffer: {guid} held: incomplete structured parlay caption')
                continue
            if x_post.tweet_length(text) > x_post.LIMIT:
                log(f'buffer: {guid} held: all parlay legs do not fit X; never omit or merge legs')
                continue
        text = social_voice.finish(text)
        text = x_ticket_copy(text, kind, guid, item)
        if x_post.tweet_length(text) > x_post.LIMIT:
            log(f'buffer: {guid} held: complete caption and Playbook tag exceed X limit')
            continue
        problems = x_post.x_style(text)
        if social_style.active(now):
            problems += social_style.issues(text)
        if problems:
            if kind == 'play' and missed_target(guid, due, now, items):
                stats['officialNotScheduled'] += 1
            log(f'buffer: {guid} not scheduled: outgoing copy fails the public voice check ({", ".join(problems)})')
            continue
        image = None
        if card_key:
            image = live_card_url(card_key, opener)
            if not image:
                if kind == 'play' and missed_target(guid, due, now, items):
                    stats['officialNotScheduled'] += 1
                log(f'buffer: {guid} waits: its card is not live yet (every post carries its card)')
                continue
            # The approved projection sheet has its own renderer, not the
            # Kitchen Ticket renderer. Exempt only its exact namespace and key.
            sheet_match = re.fullmatch(r'sheet:(NFL|CFB):(\d{4}-\d{2}-\d{2})', guid)
            projection_sheet = (kind == 'sheet' and sheet_match is not None
                                and card_key == f'sheet-{sheet_match[1].lower()}-{sheet_match[2]}')
            if pick_card.ticket_enabled(moment=due) and not projection_sheet \
                    and not owner_slip_image(guid, kind, card_key, items, now=now) and not ticket_art_live(image):
                log(f'buffer: {guid} waits: the live card is not Kitchen Ticket art')
                continue
        # Resolve every fallible field before Buffer accepts the post. Otherwise a
        # local labeling error after createPost could leave an unlogged post that a
        # later run schedules again. Text-only posts do not enter card comparisons.
        if image and social_style.active(now) and not owner_slip_image(guid, kind, card_key, items, now=now) and not plain_art_live(image):
            log(f'buffer: {guid} waits: image has no verified current social-style marker')
            if kind == 'play':
                stats['officialNotScheduled'] += 1
            continue
        if image:
            try:
                card_theme = ('owner-screenshot' if owner_slip_image(guid, kind, card_key, items, now=now)
                              else pick_card.card_theme(theme_moment(guid, kind, due, items)))
            except Exception:
                card_theme = 'legacy'
                log(f'buffer: {guid} card theme label fell back to legacy')
        else:
            card_theme = 'none'
        if kind == 'nba-trial':
            import nba_trial_runtime
            if not nba_trial_runtime.reserve_delivery(guid, now):
                log(f'buffer: {guid} held: NBA delivery already attempted; reconcile before retry')
                continue
        try:
            if quota.temporary_buffer_allowance(now):
                post_id = create_post(text, channel_id, due, image, key=key, send=send,
                                      essential=kind in BUFFER_TEMP_ESSENTIAL)
            else:
                post_id = create_post(text, channel_id, due, image, key=key, send=send)
        except BufferError as error:
            if kind == 'nba-trial':
                nba_trial_runtime.delivery_failed(guid, now)
            if kind == 'play' and missed_target(guid, due, now, items):
                stats['officialNotScheduled'] += 1
            log(f'buffer: {guid} not scheduled: {error}')
            continue
        entry = {'id': guid, 'postedAt': gates.stamp(now), 'dueAt': gates.stamp(due), 'bufferPostId': post_id,
                 'textHash': x_post.text_hash(text), 'kind': f'buffer:{kind}', 'card': bool(image),
                 'cardTheme': card_theme}
        if social_style.active(now):
            entry.update(queuedText=text, socialStyleVersion=social_style.VERSION,
                         socialVoiceVersion=social_voice.VERSION, socialAgeVersion=AGE_VERSION)
        if corrections and text == prior.get('queuedText'):
            entry['captionCorrections'] = list(corrections)
        # Official plays and their settled win updates stay together in Plays
        # & Results. Pregame personal tickets belong there too, while remaining
        # community content and separate from the official Best Bet record.
        # Approved research follows its X post into the dedicated research feed.
        if kind in ('play', 'community', 'research') or (kind == 'cashed' and guid.startswith(('cashed:', 'burnt:'))):
            entry['discord'] = {'state': 'pending', 'text': without_playbook(text)}
            # Replacing a private X draft is not a second Discord release. Carry
            # its confirmed public receipt forward, leaving the original intact.
            prior = next((p for p in reversed(log_book.get('posts', []))
                          if p.get('id') == guid and x_post.cancelled_private_draft(p)), None)
            if prior:
                entry['replacesBufferPostId'] = prior['bufferPostId']
                if (prior.get('discord') or {}).get('state') == 'sent':
                    entry['discord'] = dict(prior['discord'])
        if kind == 'community':
            import discord_post
            phase = discord_post.community_type(guid, items)
            entry['discord']['communityType'] = phase
            entry['discord']['destination'] = {'ticket': 'plays', 'result': 'wins'}.get(phase)
        if kind == 'research':
            # There is deliberately no readyAt: research mirrors only after Buffer confirms X.
            entry['discord']['destination'] = 'research'
            import research_posts
            metadata = research_posts.planned_metadata(guid)
            if metadata:
                entry['research'] = metadata
        if kind == 'play' and entry['discord'].get('state') != 'sent':
            # A confirmed play is the reason to join Discord. Schedule it first; the lightweight delivery job runs
            # every five minutes, so a 15-minute target gives members roughly 10-15 minutes before the X post.
            entry['discord']['readyAt'] = gates.stamp(max(now, due - DISCORD_PLAY_LEAD))
        if image and 'discord' in entry and entry['discord'].get('state') != 'sent':
            entry['discord']['image'] = image
        if image and card_key and card_key != guid:
            entry['cardKey'] = card_key            # a Pick of the Day's own card; a requote keeps it
        if str(card_key or '').endswith('-potd'):
            entry['featured'] = True
        if kind == 'play':
            entry['reasonKind'] = x_post.reason_kind(x_post.reason_in(text))      # what learning compares engagement by
            entry['copyVariant'] = x_post.copy_variant(text)
        log_book.setdefault('posts', []).append(entry)
        pending += 1
        log(f"buffer: {guid} scheduled for {due.astimezone(gates.EASTERN):%a %-I:%M %p} ET" + (' with card' if image else ''))
    return log_book


def expedite_cashed(entry, channel_id, now, key=None, send=http_send):
    """Move one unsent result to the next safe Buffer instant.

    Buffer has no edit operation and rejects identical scheduled copy, so the
    old result must be removed before its replacement is created. If creation
    fails, restore the original schedule before returning the error. The saved
    Discord payload is the canonical copy and is released to the wins channel
    now.
    """
    if entry.get('kind') != 'buffer:cashed' or entry.get('sentAt') or entry.get('cancelledAt') \
            or entry.get('deletedAt') or entry.get('error') or not entry.get('bufferPostId'):
        raise BufferError('only an active scheduled result can be expedited')
    mirror = entry.get('discord') or {}
    text = str(mirror.get('text') or '').strip()
    if not text:
        raise BufferError('the saved result copy is missing')
    due = now + SOON
    card = mirror.get('image') if entry.get('card') else None
    old_id = entry['bufferPostId']
    old_due = gates.when(entry['dueAt'])
    delete_post(old_id, key=key, send=send)
    try:
        new_id = create_post(text, channel_id, due, card, key=key, send=send)
    except BufferError as error:
        try:
            entry['bufferPostId'] = create_post(text, channel_id, old_due, card, key=key, send=send)
        except BufferError as restore_error:
            raise BufferError(f'{error}; original result schedule could not be restored: {restore_error}') from error
        raise
    entry['bufferPostId'] = new_id
    entry['dueAt'] = gates.stamp(due)
    entry['rescheduledAt'] = gates.stamp(now)
    if mirror.get('state') == 'pending':
        mirror['readyAt'] = gates.stamp(now)
        entry['discord'] = mirror
    return entry


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


STATUS = 'query($id: PostId!) { post(input: {id: $id}) { id status text sentAt externalLink error { message } } }'
METRICS = 'query($id: PostId!) { post(input: {id: $id}) { id metricsUpdatedAt metrics { type value } } }'
SETTLE_METRICS = timedelta(hours=24)     # owner Autopilot: first read at 24h, within 30h


def collect_metrics(log_book, now, key=None, send=http_send, log=print):
    """Track 24h/72h/7d snapshots under existing quota, prioritizing first reads."""
    read = 0
    # Attended web receipts have real X proof but need no invented developer
    # post ID. Their metrics are unavailable to this API path, not a fatal error.
    candidates = [(entry, social_learning.checkpoint(entry, now)) for entry in log_book.get('posts', [])
                  if entry.get('bufferPostId')]
    candidates = [(entry, point) for entry, point in candidates if point is not None]
    candidates.sort(key=lambda pair:(bool(pair[0].get('metricsAt')),pair[0]['sentAt']))
    # Extra refreshes have their own small ceiling; never expand the provider budget.
    followups = sum(1 for entry in log_book.get('posts', []) for at in entry.get('metricsRefreshAttempts', [])
                    if str(at)[:10] == gates.stamp(now)[:10])
    # First reads used to evade the follow-up ceiling when metrics never arrived.
    # Count every attempt across passes, including failures and unavailable metrics.
    # Keep legacy observations intact and avoid counting the same attempt twice.
    daily_attempts = sum(1 for entry in log_book.get('posts', [])
        for at in set(entry.get('metricsAttempts', []) + entry.get('metricsRefreshAttempts', [])
                      + ([entry['metricsAttemptAt']] if entry.get('metricsAttemptAt') else []))
        if str(at)[:10] == gates.stamp(now)[:10])
    attempts = 0
    for entry, point in candidates:
        attempted = entry.get('metricsAttemptAt')
        if attempted and now - gates.when(attempted) < timedelta(hours=6):
            continue
        if entry.get('metricsAt') and followups >= 8:
            continue
        if attempts >= 12 or daily_attempts >= quota.BUFFER_ANALYTICS_PER_DAY:
            break
        attempts += 1
        daily_attempts += 1
        entry['metricsAttemptAt'] = gates.stamp(now)
        entry.setdefault('metricsAttempts', []).append(gates.stamp(now))
        if entry.get('metricsAt'):
            entry.setdefault('metricsRefreshAttempts', []).append(gates.stamp(now))
            followups += 1
        try:
            post = graphql(METRICS, {'id': entry['bufferPostId']}, key=key, send=send).get('post') or {}
        except BufferError as error:
            if 'insights' in str(error).lower() or 'scope' in str(error).lower():
                log('buffer: engagement not read: the key lacks the insights:read permission')
                return read
            log(f"buffer: engagement for {entry['id']} not read: {error}")
            if isinstance(error, BufferRateLimited) or 'reserve' in str(error).lower() or 'cap reached' in str(error).lower():
                break
            continue
        metrics = {m['type']: m['value'] for m in post.get('metrics') or [] if isinstance(m.get('value'), (int, float))}
        if not metrics or not any(k in metrics for k in ('impressions','views')):
            log(f"buffer: {entry['id']} metrics unavailable; prior observation retained")
            continue
        history = entry.setdefault('metricsHistory', [])
        prior = bool(entry.get('metricsAt'))
        if prior and not history:
            history.append(dict(at=entry['metricsAt'],metrics=dict(entry.get('metrics') or {}),legacy=True))
        history.append(dict(at=gates.stamp(now),checkpointHours=point,metrics=metrics,
                            providerUpdatedAt=post.get('metricsUpdatedAt'),followup=prior))
        entry['metrics'] = metrics
        entry['metricsAt'] = gates.stamp(now)
        read += 1
    return read


def queued_relevance_issues(entry, now):
    import nba_editorial
    if now < nba_editorial.RELEVANCE_START or not re.fullmatch(r'nba-(?:trends|props)-\d{4}-\d{2}-\d{2}',str(entry.get('id') or '')):
        return []
    snapshot=next((r for r in nba_editorial.stored() if r['key']==entry['id']),None)
    if not snapshot:return ['current NBA research evidence unavailable']
    issues=nba_editorial.relevance_issues(snapshot,now)
    if not issues and not nba_editorial.watch_current(snapshot,now):
        issues.append('NBA matchup research no longer matches the latest book quote')
    if not issues and snapshot.get('family') == 'props' and not nba_editorial.props_current(snapshot,now):
        issues.append('NBA player research no longer matches current price, projection or role')
    return issues


def style_audit_due(entry, now):
    if not social_style.active(now) or not entry.get('bufferPostId') or any(entry.get(k) for k in ('sentAt', 'cancelledAt', 'deletedAt', 'error')):
        return False
    audit = entry.get('socialStyleAudit') or {}
    if audit.get('checkedAt') and now - gates.when(audit['checkedAt']) < timedelta(minutes=5):
        return False
    if now >= AGE_EFFECTIVE and entry.get('socialAgeVersion') != AGE_VERSION:
        return True
    if queued_relevance_issues(entry, now):
        return True
    if entry.get('socialStyleVersion') != social_style.VERSION or not entry.get('dueAt'):
        return True
    if entry.get('queuedText') and social_voice.finish(entry['queuedText']) != entry['queuedText']:
        return True
    # One final check in the existing five-minute job, not six extra provider
    # reads per post. A moved due time naturally invalidates an earlier check.
    release_window = gates.when(entry['dueAt']) - timedelta(minutes=5)
    if now < release_window:
        return False
    return not (audit.get('state') == 'clear' and audit.get('checkedAt')
                and gates.when(audit['checkedAt']) >= release_window)


def audit_pending_style(log_book, now, key=None, send=http_send, log=print, art_check=None, items=None):
    """Audit private queue against the current policy. Never delete a sent/unknown-state post."""
    failed = []
    art_check = art_check or plain_art_live
    if items is None:
        try:
            items = {r['id']: r for r in json.loads((ROOT / 'data/community.json').read_text()).get('tickets', [])}
        except (OSError, ValueError, KeyError):
            items = {}
    for entry in log_book.get('posts', []):
        if not style_audit_due(entry, now):
            continue
        try:
            post = graphql(STATUS, {'id': entry['bufferPostId']}, key=key, send=send).get('post') or {}
            if post.get('status') == 'sent' or post.get('sentAt'):
                entry['sentAt'] = post.get('sentAt') or gates.stamp(now)
                entry['link'] = post.get('externalLink') or None
                entry['tweetId'] = (entry['link'] or '').rstrip('/').rsplit('/', 1)[-1] if '/status/' in (entry['link'] or '') else None
                entry['socialStyleAudit'] = {'checkedAt': gates.stamp(now), 'state': 'already-public'}
                continue
            if post.get('status') != 'scheduled':
                raise BufferError('queued style check cannot confirm a private scheduled provider state')
            text = canonical_caption(post.get('text') or entry.get('queuedText') or (entry.get('discord') or {}).get('text'))
            problems = social_style.issues(text) if text else ['caption unavailable for verification']
            if now >= AGE_EFFECTIVE and not age_notice_current(text):
                problems.append('caption needs the owner-approved 21+ only line')
            problems += queued_relevance_issues(entry, now)
            if text and social_voice.finish(text) != text:
                problems.append('retired caption voice; fresh casual revision required')
            card = entry.get('cardKey')
            image = entry.get('bufferImage') or (entry.get('discord') or {}).get('image') or (card_url(card) if card else None)
            owner = owner_slip_image(entry['id'], 'community' if str(entry.get('kind')) == 'buffer:community' else '', card, items, now=now)
            if entry.get('card') and not owner:
                # Discord-first official releases archive the exact attachment
                # before pushing their report. Pages may still be deploying;
                # that lag is not evidence that the actual Buffer art is stale.
                archive_id = str(entry.get('id') or '')
                released_archive = (entry.get('kind') == 'buffer:play'
                    and (entry.get('discord') or {}).get('beforeX')
                    and (entry.get('discord') or {}).get('state') == 'sent'
                    and re.fullmatch(r'[A-Za-z0-9-]{1,150}', archive_id)
                    and social_style.current_png(ROOT / 'data' / 'release-cards' / f'{archive_id}.png'))
                if not released_archive and (not image or not art_check(image)):
                    problems.append('house graphic lacks verified current social-style marker')
            if problems:
                delete_post(entry['bufferPostId'], key=key, send=send)
                entry['cancelledAt'] = gates.stamp(now)
                entry['cancelReason'] = 'Owner social-style correction: ' + '; '.join(problems)
                entry['socialStyleAudit'] = {'checkedAt': gates.stamp(now), 'state': 'cancelled-private', 'issues': problems, 'needsRevision': True}
                # Preserve the original text, card and provider id as evidence, not a silent rewrite.
                log(f"buffer: {entry['id']} private draft cancelled: {'; '.join(problems)}; fresh revision required")
                failed.append({**entry, 'error': entry['cancelReason']})
            else:
                entry['socialStyleVersion'] = social_style.VERSION
                if now >= AGE_EFFECTIVE:
                    entry['socialAgeVersion'] = AGE_VERSION
                entry['queuedText'] = text
                entry['socialStyleAudit'] = {'checkedAt': gates.stamp(now), 'state': 'clear'}
        except BufferError as error:
            previous = (entry.get('socialStyleAudit') or {}).get('error')
            entry['socialStyleAudit'] = {'checkedAt': gates.stamp(now), 'state': 'unverified', 'error': str(error)}
            if previous != str(error):
                failed.append({**entry, 'error': str(error)})
            log(f"buffer: {entry['id']} style audit unavailable; no deletion: {error}")
    return failed


def reconcile(log_book, now, key=None, send=http_send, log=print):
    """Ask Buffer what became of each post whose time has passed, once: the X link when it went out, the
    message when it failed. Returns the entries that failed, for the run to raise."""
    failed = audit_pending_style(log_book, now, key=key, send=send, log=log)
    for entry in log_book.get('posts', []):
        import nba_editorial
        if nba_editorial.veto_pending(entry,now):
            try:
                delete_post(entry['bufferPostId'],key=key,send=send)
                entry['cancelledAt']=gates.stamp(now)
                entry['cancelReason']='NBA research review or current-price/availability hold'
                log(f"buffer: {entry['id']} cancelled before send: NBA research preview hold")
            except BufferError as error:
                log(f"buffer: NBA research veto cancellation failed: {error}")
            continue
        if not entry.get('bufferPostId') or entry.get('cancelledAt') or entry.get('sentAt') or entry.get('error'):
            continue
        if not entry.get('dueAt') or gates.when(entry['dueAt']) > now:
            continue
        try:
            post = graphql(STATUS, {'id': entry['bufferPostId']}, key=key, send=send).get('post') or {}
        except BufferRateLimited as error:
            log(f'buffer: delivery reconciliation waits: {error}')
            break
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
