"""Posting researched favorites to X as @keenkooks, behind a review gate. Stdlib only.

  python scripts/x_post.py draft PICK_ID            write the draft to the sports config folder and print it
  python scripts/x_post.py post PICK_ID --confirm   post that draft (the refusals run again at post time)
  python scripts/x_post.py recap --day YYYY-MM-DD   draft the day's results; add --confirm to post it
  python scripts/x_post.py auto --i-understand      post every open favorite that passes; also needs
                                                    KEENROUDY_X_AUTONOMOUS=1 in the environment

Only researched favorites go to X. Model leans, prop leans and longshots never do. A post is refused
when the game has started, the pick has expired or closed, it is not a favorite, or its id or its
exact text is already in data/x-posted.json, which lives in the repo so a double post cannot depend
on anyone's memory. Credentials come from the environment and are never printed; a log line names
which keys are set, never their values. OAuth 1.0a is signed here with hmac and sha1.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import gates
import llm
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
CONF = Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy'))
LOG = ROOT / 'data' / 'x-posted.json'
API = 'https://api.x.com/2/tweets'
SITE = 'https://keenroudy.com/sports/'
LIMIT = 280
URL_LENGTH = 23           # X counts every link as 23 characters
CRED_KEYS = {'consumer_key': 'X_API_KEY', 'consumer_secret': 'X_API_SECRET', 'token': 'X_ACCESS_TOKEN', 'token_secret': 'X_ACCESS_SECRET'}
OPENERS = ("Kitchen's open.", "Plate's up.", "Fresh out of the kitchen.", "One plate tonight.", "Serving one.")


class Refused(Exception):
    """A post that must not go out, with the reason."""


class MissingCredentials(RuntimeError):
    pass


# ------------------------------------------------------------------ OAuth 1.0a

def percent_encode(value):
    return urllib.parse.quote(str(value), safe='-._~')


def signature_base(method, url, params):
    pairs = sorted((percent_encode(k), percent_encode(v)) for k, v in params.items())
    normalized = '&'.join(f'{k}={v}' for k, v in pairs)
    return '&'.join((method.upper(), percent_encode(url), percent_encode(normalized)))


def sign(base, consumer_secret, token_secret):
    key = f'{percent_encode(consumer_secret)}&{percent_encode(token_secret)}'.encode()
    return base64.b64encode(hmac.new(key, base.encode(), hashlib.sha1).digest()).decode()


def oauth_header(method, url, creds, extra_params=None, nonce=None, timestamp=None):
    """The Authorization header for one request. extra_params are query or form fields; a JSON body adds none."""
    oauth = {'oauth_consumer_key': creds['consumer_key'], 'oauth_nonce': nonce or secrets.token_hex(16),
             'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(timestamp or int(time.time())),
             'oauth_token': creds['token'], 'oauth_version': '1.0'}
    base = signature_base(method, url, {**(extra_params or {}), **oauth})
    oauth['oauth_signature'] = sign(base, creds['consumer_secret'], creds['token_secret'])
    return 'OAuth ' + ', '.join(f'{percent_encode(k)}="{percent_encode(v)}"' for k, v in sorted(oauth.items()))


def credentials(env=None):
    env = env if env is not None else os.environ
    creds = {name: (env.get(key) or '').strip() for name, key in CRED_KEYS.items()}
    missing = [CRED_KEYS[name] for name, value in creds.items() if not value]
    if missing:
        raise MissingCredentials(f"missing in the environment: {', '.join(missing)}")
    return creds


def http_send(url, body, headers):
    request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def post_tweet(text, creds, send=http_send):
    """The new post's id, or Refused when X turns it down (a duplicate is a 403)."""
    status, raw = send(API, {'text': text}, {'Authorization': oauth_header('POST', API, creds)})
    if status == 201:
        return json.loads(raw)['data']['id']
    detail = raw.decode('utf-8', 'replace')[:300] if isinstance(raw, bytes) else str(raw)[:300]
    if status == 403 and 'duplicate' in detail.lower():
        raise Refused('X refused a duplicate post')
    raise Refused(f'X returned HTTP {status}: {detail}')


# ------------------------------------------------------------------ the posted log

def load_log(path=LOG):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'posts': []}


def save_log(log, path=LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')


def text_hash(text):
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()[:16]


def record(log, key, text, tweet_id, kind, now):
    log['posts'].append({'id': key, 'postedAt': gates.stamp(now), 'tweetId': tweet_id, 'textHash': text_hash(text), 'kind': kind})
    return log


# ------------------------------------------------------------------ drafts and refusals

def tweet_length(text):
    """X's count: every URL is 23 characters."""
    words = text.split()
    return len(text) - sum(len(w) - URL_LENGTH for w in words if w.startswith(('http://', 'https://')))


def sentences(text):
    return [s.strip() for s in llm.re.split(r'(?<=[.!?])\s+', text or '') if s.strip()]


def opener_for(key):
    return OPENERS[int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(OPENERS)]


def draft(pick, game=None, opener=None):
    """The post text: an opener, the line at its price, one or two sentences from the pick's own why, and the link."""
    link = f"{SITE}#pick/{pick['id']}"
    head = f"{pick.get('title')} ({int(pick['odds']):+d}, {pick.get('book')})"
    lead_ins = ('model lean', 'prop lean', 'researched pick', 'longshot')
    reasons = [s for s in sentences(pick.get('why')) if not s.lower().startswith(lead_ins)]
    for count in (2, 1, 0):
        body = ' '.join(reasons[:count])
        text = '\n\n'.join(part for part in ((opener or opener_for(pick['id'])), head, body, link) if part)
        if tweet_length(text) <= LIMIT:
            return text
    return '\n\n'.join(((opener or opener_for(pick['id'])), head, link))


def guard(text, pick):
    problems = llm.check_style(text.replace(SITE, ''))
    ok, strays = llm.numbers_ok(text, pick)
    if not ok:
        problems.append(f"numbers not in the pick: {', '.join(strays)}")
    if tweet_length(text) > LIMIT:
        problems.append(f'{tweet_length(text)} characters')
    return problems


def refuse(pick, game, log, now, text=None):
    """The reason this pick must not be posted now, or None."""
    if pick.get('favorite') is not True:
        raise Refused('not a favorite; model leans, prop leans and longshots never go to X')
    if pick.get('result') or pick.get('status') not in (None, 'active'):
        raise Refused(f"the pick is {pick.get('status') or 'settled'}, not open")
    if pick.get('entryNote'):
        raise Refused('the pick is closed to new entries')
    if not game:
        raise Refused('the game is not in the slate')
    if gates.when(game['kickoff']) <= now:
        raise Refused(f"the game kicked off at {game['kickoff']}")
    if pick.get('expiresAt') and gates.when(pick['expiresAt']) <= now:
        raise Refused(f"the quote expired at {pick['expiresAt']}")
    posted = {p['id'] for p in log['posts']}
    if pick['id'] in posted:
        raise Refused('already posted')
    if text and text_hash(text) in {p.get('textHash') for p in log['posts']}:
        raise Refused('this exact text was already posted')
    return None


# ------------------------------------------------------------------ recaps

def payout(odds):
    return odds / 100 if odds > 0 else 100 / -odds


def units_for(pick):
    """core.js unitsFor: one unit a pick (riskUnits for a parlay); push, void and early exit score zero; no price, no units."""
    odds, result = pick.get('odds'), pick.get('result')
    if not isinstance(odds, (int, float)) or result not in ('win', 'loss', 'push'):
        return None
    stake = pick.get('riskUnits') or 1
    if result == 'win':
        return round(payout(odds) * stake, 3)
    if result == 'loss':
        return 0.0 if pick.get('earlyExit') else -stake
    return 0.0


def summarize(picks):
    counts = {'win': 0, 'loss': 0, 'push': 0, 'void': 0}
    units = 0.0
    for pick in picks:
        if pick.get('result') in counts:
            counts[pick['result']] += 1
        value = units_for(pick)
        if value is not None:
            units += value
    return {**counts, 'units': round(units, 2)}


def recap(day, first, latest, games, now):
    """The day's settled picks as a post: what hit, what missed, units, favorites apart."""
    rows = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        game = games.get((pick.get('gameIds') or [None])[0])
        if pick.get('historicalImport') or not merged.get('result') or not game:
            continue
        if eastern_date(gates.when(game['kickoff'])).isoformat() != day:
            continue
        rows.append(merged)
    if not rows:
        return None
    favorites = [r for r in rows if r.get('favorite') is True or key in build_site.FAVORITES_BEFORE_FLAG]
    everything = summarize(rows)
    lines = [f"Kitchen's closed for {datetime.fromisoformat(day):%A}."]
    if favorites:
        fav = summarize(favorites)
        lines.append(f"Favorites {fav['win']}-{fav['loss']}" + (f"-{fav['push']}" if fav['push'] else '') + f" ({fav['units']:+.2f}u).")
    lines.append(f"Everything on the record {everything['win']}-{everything['loss']}" + (f"-{everything['push']}" if everything['push'] else '') + f" ({everything['units']:+.2f}u).")
    hits = [r['title'] for r in rows if r.get('result') == 'win'][:3]
    misses = [r['title'] for r in rows if r.get('result') == 'loss'][:3]
    if hits:
        lines.append('Hit: ' + '; '.join(hits) + '.')
    if misses:
        lines.append('Missed: ' + '; '.join(misses) + '.')
    text = '\n'.join(lines) + f'\n\n{SITE}#record'
    while tweet_length(text) > LIMIT and (hits or misses):
        if misses:
            misses.pop()
        elif hits:
            hits.pop()
        lines = lines[:3 if favorites else 2] + (['Hit: ' + '; '.join(hits) + '.'] if hits else []) + (['Missed: ' + '; '.join(misses) + '.'] if misses else [])
        text = '\n'.join(lines) + f'\n\n{SITE}#record'
    return text


def scoreboard_text(scoreboard, model='v2.0'):
    """The weekly model post: our number against the closing line, season to date, from scoreboard.json only."""
    rows = [g for g in (scoreboard or {}).get('live') or [] if g.get('model') == model]
    if not rows:
        return None
    lines = ['Our number vs the closing line, season to date.']
    for row in sorted(rows, key=lambda g: g['league']):
        s = row.get('summary') or {}
        side, ou = s.get('side') or [0, 0, 0], s.get('ou') or [0, 0, 0]
        closer = s.get('closerTotal') or [0, 0]
        name = 'NFL' if row['league'] == 'NFL' else 'College'
        record = lambda r: f"{r[0]}-{r[1]}" + (f"-{r[2]}" if len(r) > 2 and r[2] else '')
        graded = s.get('games') if s.get('games') is not None else closer[0] + closer[1]    # a number the scoreboard itself holds
        lines.append(f"{name}: sides {record(side)}, totals {record(ou)}. Closer on {closer[0]} of {graded} totals, "
                     f"miss {s.get('totalMiss')} vs {s.get('closeTotalMiss')}.")
    lines.append('The close is the yardstick. When it wins, it says so here.')
    text = '\n'.join(lines) + f'\n\n{SITE}#model'
    if tweet_length(text) > LIMIT:
        lines = lines[:-1]
        text = '\n'.join(lines) + f'\n\n{SITE}#model'
    return text


# ------------------------------------------------------------------ command line

def load_picks(now):
    stores = gates.Stores()
    ctx = stores.as_of(now)
    return ctx.first, ctx.latest, ctx.games


def env_report():
    present = [key for key in CRED_KEYS.values() if os.environ.get(key)]
    return f"credentials set: {', '.join(present) or 'none'}"


def do_draft(pick_id, now, first, latest, games, out=None):
    pick = first.get(pick_id)
    if not pick:
        raise Refused(f'{pick_id} is not in research/')
    merged = dict(pick, **latest.get(pick_id, {}))
    game = games.get((pick.get('gameIds') or [None])[0])
    text = draft(merged, game)
    problems = guard(text, merged)
    if problems:
        raise Refused(f"the draft fails the guards: {'; '.join(problems)}")
    refuse(merged, game, load_log(), now, text)
    folder = out or CONF / 'x-drafts'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{pick_id}.txt').write_text(text + '\n', encoding='utf-8')
    return text, merged, game


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('draft', 'post', 'recap', 'scoreboard', 'auto'))
    parser.add_argument('pick_id', nargs='?')
    parser.add_argument('--confirm', action='store_true', help='actually post')
    parser.add_argument('--day', help='Eastern date for a recap')
    parser.add_argument('--i-understand', action='store_true', help='required for auto, with KEENROUDY_X_AUTONOMOUS=1')
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    print(env_report())
    try:
        first, latest, games = load_picks(now)
        if args.command in ('draft', 'post'):
            if not args.pick_id:
                sys.exit('a pick id is required')
            text, pick, game = do_draft(args.pick_id, now, first, latest, games)
            print(f'\n{text}\n\n{tweet_length(text)} characters')
            if args.command == 'post':
                if not args.confirm:
                    print('\nnot posted: add --confirm to post this text')
                    return 0
                log = load_log()
                refuse(pick, game, log, now, text)
                tweet_id = post_tweet(text, credentials())
                save_log(record(log, pick['id'], text, tweet_id, 'pick', now))
                print(f'\nposted: {tweet_id}; logged in {LOG.relative_to(ROOT)}')
        elif args.command in ('recap', 'scoreboard'):
            day = args.day or eastern_date(now).isoformat()
            if args.command == 'recap':
                text, key = recap(day, first, latest, games, now), f'recap:day:{day}'
            else:
                scoreboard = json.loads((ROOT / 'site' / 'data' / 'scoreboard.json').read_text(encoding='utf-8'))
                text, key = scoreboard_text(scoreboard), f'scoreboard:week:{day}'
            if not text:
                print(f"nothing to post for {args.command} on {day}")
                return 0
            print(f'\n{text}\n\n{tweet_length(text)} characters')
            log = load_log()
            if key in {p['id'] for p in log['posts']}:
                print('\nalready posted')
                return 0
            if args.confirm:
                tweet_id = post_tweet(text, credentials())
                save_log(record(log, key, text, tweet_id, args.command, now))
                print(f'\nposted: {tweet_id}')
            else:
                print('\nnot posted: add --confirm to post this text')
        else:
            if os.environ.get('KEENROUDY_X_AUTONOMOUS') != '1' or not args.i_understand:
                sys.exit('autonomous posting is off: it needs KEENROUDY_X_AUTONOMOUS=1 and --i-understand')
            log = load_log()
            posted = 0
            for key, pick in first.items():
                merged = dict(pick, **latest.get(key, {}))
                if merged.get('favorite') is not True or merged.get('result') or key in {p['id'] for p in log['posts']}:
                    continue
                try:
                    text, merged, game = do_draft(key, now, first, latest, games)
                    tweet_id = post_tweet(text, credentials())
                    record(log, key, text, tweet_id, 'pick', now)
                    posted += 1
                    print(f'posted {key}: {tweet_id}')
                except Refused as why:
                    print(f'skipped {key}: {why}')
            save_log(log)
            print(f'{posted} posted')
    except (Refused, MissingCredentials) as error:
        print(f'\nrefused: {error}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
