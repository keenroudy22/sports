"""Posting to @keenkooks through Buffer, whose free plan carries the cost of X's API. Stdlib only.

X meters posting through its own API. Buffer (buffer.com) connects an X account to its own developer
access and lets a free plan schedule posts through a GraphQL API: 3,000 requests a month, a public
image URL per post, an exact `dueAt` per post, and a `deletePost` to take one back. That is enough for
a desk that posts a handful of plays a day at set times.

  python scripts/buffer_post.py channels          list the connected channels (find @keenkooks)
  python scripts/buffer_post.py limits             today's posting limit for the X channel
  python scripts/buffer_post.py plan               what the run would schedule right now, without posting
  python scripts/buffer_post.py post PICK_ID [--at ISO]   schedule one pick's post (needs --confirm)

The run (scripts/run.py) schedules each play once inside its posting window (game day, 9:00 AM ET
until 45 minutes before kickoff, spaced eight minutes apart), the recap for the next morning and the
scoreboard for Tuesday morning, and logs every post in data/x-posted.json so nothing goes out twice.
A play that closes to new entries before its time is cancelled. The token lives in the environment
(BUFFER_TOKEN) and never in a log.
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
import x_post
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.buffer.com'
CARDS = x_post.SITE + 'data/cards/'
SPACING = timedelta(minutes=8)       # between plays scheduled into the same window
SOON = timedelta(minutes=2)          # a post scheduled "now" goes out this far ahead
RECAP_AT = (8, 0)                    # Eastern, the morning after a game day
SCOREBOARD_AT = (9, 0)               # Eastern, Tuesdays
MAX_PER_DAY = 8                      # our own ceiling; Buffer's channel limit is queried as well


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
    data = graphql('query($org: String!) { channels(input: {organizationId: $org}) { id name displayName service avatar isQueuePaused } }',
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
    data = graphql('query($ids: [String!]!, $date: String!) { dailyPostingLimits(input: {channelIds: $ids, date: $date}) { channelId limit count remaining } }',
                   {'ids': [channel_id], 'date': day}, key=key, send=send)
    rows = data.get('dailyPostingLimits') or []
    return rows[0] if rows else None


CREATE = '''mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt text } }
    ... on MutationError { message }
  }
}'''

DELETE = '''mutation($id: String!) {
  deletePost(input: {id: $id}) {
    ... on PostActionSuccess { post { id } }
    ... on MutationError { message }
  }
}'''


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def create_post(text, channel_id, due_at, image_url=None, key=None, send=http_send):
    """Schedule one post for an exact time. Returns Buffer's post id."""
    payload = {'text': text, 'channelId': channel_id, 'schedulingType': 'automatic', 'mode': 'customScheduled', 'dueAt': stamp(due_at)}
    if image_url:
        payload['assets'] = [{'image': {'url': image_url}}]
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


def plan(first, latest, games, now, log_book, scoreboard=None, player_team=None):
    """The posts the run should schedule now: [(key, kind, text, due_at, card_key)].

    Plays: open, postable, game today (Eastern), not yet in the log; due at the later of now plus two
    minutes and the window's open, spaced eight minutes apart, never inside 45 minutes of kickoff.
    Recap: once every pick of a day is settled, due the next morning at 8:00 ET. Scoreboard: Tuesdays 9:00 ET.
    """
    posted = {p['id'] for p in log_book.get('posts', [])}
    today = eastern_date(now)
    out = []
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
        text = x_post.draft(merged, game)
        if x_post.guard(text, merged):
            continue
        plays.append((gates.when(starts[0]), key, text, merged, game))
    plays.sort()
    slot = max(now + SOON, window_open(today))
    scheduled = 0
    for kickoff, key, text, merged, game in plays:
        if scheduled >= MAX_PER_DAY:
            break
        due = slot
        last = kickoff - feed.LEAD
        if due > last:
            continue                    # this one's window has passed; the next play may still fit
        out.append((key, 'play', text, due, key))
        slot = due + SPACING
        scheduled += 1
    for back in (1, 0):
        day = today - timedelta(days=back)
        key = f'recap:day:{day.isoformat()}'
        if key in posted:
            continue
        items = feed.recap_items(first, latest, games, now)
        match = next((i for i in items if i['guid'] == key), None)
        if match:
            morning = datetime(day.year, day.month, day.day, RECAP_AT[0], RECAP_AT[1], tzinfo=gates.EASTERN) + timedelta(days=1)
            due = max(morning.astimezone(timezone.utc), now + SOON)
            out.append((key, 'recap', match['text'], due, None))
    weekly = feed.scoreboard_item(scoreboard or {}, now) if scoreboard else None
    if weekly and weekly['guid'] not in posted:
        local = now.astimezone(gates.EASTERN)
        due = max(local.replace(hour=SCOREBOARD_AT[0], minute=SCOREBOARD_AT[1], second=0, microsecond=0).astimezone(timezone.utc), now + SOON)
        out.append((weekly['guid'], 'scoreboard', weekly['text'], due, None))
    return out


def schedule(plans, channel_id, log_book, now, key=None, send=http_send, opener=None, log=print):
    """Create the planned posts in Buffer and record each in the log. Returns the log."""
    for guid, kind, text, due, card_key in plans:
        image = None
        if card_key:
            url = f'{CARDS}{card_key}.png'
            image = url if reachable(url, opener) else None
        try:
            post_id = create_post(text, channel_id, due, image, key=key, send=send)
        except BufferError as error:
            log(f'buffer: {guid} not scheduled: {error}')
            continue
        log_book.setdefault('posts', []).append({'id': guid, 'postedAt': gates.stamp(now), 'dueAt': gates.stamp(due), 'bufferPostId': post_id,
                                                 'textHash': x_post.text_hash(text), 'kind': f'buffer:{kind}', 'card': bool(image)})
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
                log(f"buffer: {entry['id']} cancelled, the pick closed before its post went out")
            except BufferError as error:
                log(f"buffer: could not cancel {entry['id']}: {error}")
    return log_book


# ------------------------------------------------------------------ command line

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('channels', 'limits', 'plan', 'post'))
    parser.add_argument('pick_id', nargs='?')
    parser.add_argument('--at', help='UTC instant for the post; default now plus two minutes')
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args(argv)
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
        stores = gates.Stores()
        ctx = stores.as_of(now)
        log_book = x_post.load_log()
        if args.command == 'plan':
            import build_site
            scoreboard = build_site.read(ROOT / 'site' / 'data' / 'scoreboard.json', {})
            plans = plan(ctx.first, ctx.latest, ctx.games, now, log_book, scoreboard)
            for guid, kind, text, due, card in plans:
                print(f"{due.astimezone(gates.EASTERN):%a %-I:%M %p} ET  {kind:<10} {guid}" + (f"  card {CARDS}{card}.png" if card else ''))
                print('    ' + text.replace('\n', ' / ')[:200])
            print(f'{len(plans)} posts would be scheduled')
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
