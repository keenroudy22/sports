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
import pick_card
import pricing
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
CONF = Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy'))
LOG = ROOT / 'data' / 'x-posted.json'
API = 'https://api.x.com/2/tweets'
SITE = 'https://keenroudy.com/sports/'
LIMIT = 280
URL_LENGTH = 23           # X counts every link as 23 characters
CRED_KEYS = {'consumer_key': 'X_API_KEY', 'consumer_secret': 'X_API_SECRET', 'token': 'X_ACCESS_TOKEN', 'token_secret': 'X_ACCESS_SECRET'}
LEAD_INS = ('model lean', 'prop lean', 'researched pick', 'longshot from', 'nothing sourced', 'the market:', 'the day',
            'published', 'this rests', 'settled from', 'graded', 'active on the', 'inactives post', 'the role is settled')
# The post says what the play is and one plain reason; the arithmetic lives on the site, not in the timeline.
JARGON = ('calibrat', 'percentile', 'raw', 'shrunk', 'break-even', 'break even', 'graded', 'closing line', 'the close',
          'model', 'our number', 'our total', 'our margin', 'projection', 'curve', 'expected value', 'per unit', 'backtest', 'voided', "book's rule", 'chance', 'than that',
          # the line's move and the books' spread are the price's story, not a reason, and often point the other way
          'opened', 'a move of', 'toward the', 'books range', 'books span', 'the middle is')
REASON_MAX = 150
NOT_REASONS = ('checked before publishing',)   # the web check's lineup notes: diligence for the site, not a reason to play

DANGLING = {'is', 'are', 'was', 'were', 'has', 'have', 'had', 'will', 'would', 'can', 'could', 'does', 'do', 'did',
            'which', 'that', 'it', 'this', 'these', 'those', 'so', 'but', 'and', 'or', 'he', 'she', 'they', 'his', 'her',
            'their', 'its', 'him', 'them'}
TAGS = {'NFL': '#NFL', 'CFB': '#CFB'}


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


def post_tweet(text, creds, send=http_send, media_ids=None):
    """The new post's id, or Refused when X turns it down (a duplicate is a 403)."""
    body = {'text': text}
    if media_ids:
        body['media'] = {'media_ids': [str(m) for m in media_ids]}
    status, raw = send(API, body, {'Authorization': oauth_header('POST', API, creds)})
    if status == 201:
        return json.loads(raw)['data']['id']
    detail = raw.decode('utf-8', 'replace')[:300] if isinstance(raw, bytes) else str(raw)[:300]
    if status == 403 and 'duplicate' in detail.lower():
        raise Refused('X refused a duplicate post')
    raise Refused(f'X returned HTTP {status}: {detail}')


# ------------------------------------------------------------------ media

MEDIA_V2 = 'https://api.x.com/2/media/upload'
MEDIA_V1 = 'https://upload.twitter.com/1.1/media/upload.json'


def multipart(fields, files):
    """(content type, body) for a multipart form; files is {name: (filename, bytes, mime)}."""
    boundary = '----keenroudy' + secrets.token_hex(12)
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, (filename, data, mime) in files.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                     f'Content-Type: {mime}\r\n\r\n'.encode() + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return f'multipart/form-data; boundary={boundary}', b''.join(parts)


def http_send_raw(url, body, headers):
    """POST raw bytes (multipart or JSON already encoded) and return (status, bytes)."""
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def upload_media(png, creds, send_raw=http_send_raw):
    """Upload one PNG and return its media id, over the v2 chunked flow with the v1.1 endpoint as the fallback.

    A multipart body adds nothing to the OAuth signature, so the header signs the URL and the OAuth
    parameters alone. Refused when neither endpoint takes the image.
    """
    def call(url, body, content_type):
        headers = {'Authorization': oauth_header('POST', url, creds), 'Content-Type': content_type}
        return send_raw(url, body, headers)

    init_url = f'{MEDIA_V2}/initialize'
    status, raw = call(init_url, json.dumps({'media_type': 'image/png', 'total_bytes': len(png), 'media_category': 'tweet_image'}).encode(),
                       'application/json')
    if status in (200, 201, 202):
        payload = json.loads(raw)
        media_id = str((payload.get('data') or payload).get('id') or (payload.get('data') or payload).get('media_id'))
        content_type, body = multipart({'segment_index': '0'}, {'media': ('card.png', png, 'image/png')})
        status, raw = call(f'{MEDIA_V2}/{media_id}/append', body, content_type)
        if status in (200, 201, 204):
            status, raw = call(f'{MEDIA_V2}/{media_id}/finalize', b'{}', 'application/json')
            if status in (200, 201):
                return media_id
    v2_detail = raw.decode('utf-8', 'replace')[:200] if isinstance(raw, bytes) else str(raw)[:200]
    content_type, body = multipart({'media_category': 'tweet_image'}, {'media': ('card.png', png, 'image/png')})
    status, raw = call(MEDIA_V1, body, content_type)
    if status in (200, 201):
        payload = json.loads(raw)
        return str(payload.get('media_id_string') or payload.get('media_id'))
    v1_detail = raw.decode('utf-8', 'replace')[:200] if isinstance(raw, bytes) else str(raw)[:200]
    raise Refused(f'media upload refused: v2 said {v2_detail!r}; v1.1 said HTTP {status} {v1_detail!r}')


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


ABBREVIATIONS = ('Jr.', 'Sr.', 'St.', 'vs.', 'Mr.', 'Dr.', 'No.', 'Mt.', 'Ft.', 'Jan.', 'Feb.', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.')


def sentences(text):
    """Sentences, without breaking on a name's suffix or an initial ("Marvin Mims Jr.", "A.J. Brown")."""
    out = []
    for part in llm.re.split(r'(?<=[.!?])\s+', text or ''):
        part = part.strip()
        if not part:
            continue
        if out and (out[-1].endswith(ABBREVIATIONS) or llm.re.search(r'\b[A-Z]\.$', out[-1])):
            out[-1] = f'{out[-1]} {part}'
        else:
            out.append(part)
    return out


def kind_label(pick):
    """The feed's item title prefix: the same label the card and the post lead with."""
    return pick_card.kicker(pick).capitalize().replace('· favorite', '· Favorite')


def specificity(sentence):
    """How much a sentence names: numbers, and capitalised words after its first (players, teams, places)."""
    numbers = len(llm.re.findall(r'\d+(?:[.-]\d+)?', sentence))
    names = len(llm.re.findall(r'(?<=\s)[A-Z][A-Za-z.\']+', sentence))
    return numbers + names


def reasons_for(pick):
    """The pick's own reasoning, most specific first. A sentence that opens with one of the desk's lead-ins keeps
    what follows its colon ("The market: the total opened 50.5" keeps the move) and is dropped otherwise."""
    said = []
    player = pick_card.play_kind(pick) == 'player'      # "He" is the player in the title; on a team play it is no one
    for sentence in sentences(pick.get('why')):
        low = sentence.lower()
        if low.startswith(NOT_REASONS) or (not player and low.split(' ', 1)[0] in DANGLING):
            continue
        if low.startswith(LEAD_INS):
            if ':' not in sentence:
                continue
            sentence = sentence.split(':', 1)[1].strip()
            if not sentence:
                continue
            sentence = sentence[0].upper() + sentence[1:]
        said.append(sentence)
    return sorted(said, key=lambda s: (-specificity(s), len(s)))


def plain(sentence):
    """Short, none of the desk's arithmetic words, and within the house style (no dashes, no model names). Words
    match from their start ("raw" is not in "drawn", "calibrat" is in "calibrated")."""
    low = sentence.lower()
    return (len(sentence) <= REASON_MAX and not any(llm.re.search(r'\b' + llm.re.escape(word), low) for word in JARGON)
            and not x_style(sentence))


REASON_WORDS = (      # weather first: "no wind called out" is about the weather, not an injury
    ('weather', ('wind', 'rain', 'snow', 'forecast', 'degrees', 'mph', 'weather', 'storm', 'cold')),
    ('injury', (' out', 'doubtful', 'questionable', 'injur', 'inactive', 'without', 'listed', 'ruled', 'return')),
    ('market', ('opened', 'moved', 'books', 'on the board', 'price', 'draftkings', 'fanduel', 'betmgm', 'espn bet',
                'caesars', 'betrivers', 'number', 'market')),
    ('role', ('role', 'targets', 'snaps', 'starter', 'share', 'touches', 'carries', 'receiver', 'tight end', 'backfield')),
    ('stats', ('last', 'average', 'allowed', 'per game', 'a game', 'season', 'held', 'scored')),
)


def reason_kind(sentence):
    """What a reason is about, for learning which kinds of reasons people engage with."""
    low = f' {str(sentence or "").lower()} '
    for kind, words in REASON_WORDS:
        if any(word in low for word in words):
            return kind
    return 'other' if sentence else 'none'


def reason_in(text):
    """The reason sentence of a drafted play post: the line after its number line, when there is one."""
    lines = str(text or '').split('\n')
    for i, line in enumerate(lines[:-1]):
        if line.startswith('Our number') and lines[i + 1].strip() and not lines[i + 1].startswith(('@', '#')):
            return lines[i + 1]
    return None


def reason_for(pick, weights=None):
    """One plain sentence from the pick's own reasoning: short, free of the desk's arithmetic words, the most
    specific first. A long sentence may give one clean clause ("Saturday in Ann Arbor is forecast sunny and 68
    with no wind called out, so ..." gives the forecast). None when every sentence is arithmetic; the post then
    stands on the play and the number."""
    ranked = reasons_for(pick)
    if weights:
        ranked = sorted(ranked, key=lambda s: (-(specificity(s) + 1) * float(weights.get(reason_kind(s), 1.0)), len(s)))
    for sentence in ranked:
        if plain(sentence):
            return sentence
        for clause in llm.re.split(r',\s+(?:so|which|while|but|and)\s+|;\s+|:\s+', sentence):
            clause = clause.strip().rstrip(',.;: ')
            if len(clause) < 30 or clause == sentence.rstrip('.'):
                continue
            if clause.split()[0].lower() in DANGLING:
                continue                # "is the kind that held up" is half a sentence
            clause = clause[0].upper() + clause[1:] + '.'
            if plain(clause):
                return clause
    return None


PLAYBOOK = '@Playbook'     # the betslip bot (Action Network): tagged on a bet, it replies with the slip pre-loaded
REASONS = ROOT / 'data' / 'x-reasons.json'   # the reason each play's post gives, chosen when the play is published


def load_reasons(path=None):
    try:
        return json.loads(Path(path or REASONS).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_reasons(reasons, path=None):
    target = Path(path or REASONS)
    target.write_text(json.dumps(dict(sorted(reasons.items())), indent=1, ensure_ascii=False) + '\n', encoding='utf-8')


def draft(pick, game=None, weights=None, reason=None, now_quote=None):
    """The post, the same shape every time:

        🍳 PLAYER PROP | TEAM PROP | FUN PARLAY   (· FAVORITE for a researched pick)
        the play
        price at book · units

        Our number n vs the line
        one plain reason from the pick

        @Playbook #league

    A parlay lists its legs and says it is just for fun. No link and no stat line: the card carries the site,
    and @Playbook answers with the betslip. Every number comes from the pick; the units are the site's own
    count (one for a straight play, the ticket's riskUnits for a parlay).

    The reason is the one the desk chose from structured facts when it published the play (data/x-reasons.json,
    see run.post_reason): the player's own record at the line, a verified fact or a weather flag that points the
    same way as the play. It is never mined from the finished prose, which the local model rewrites; with no
    stored reason the post stands on the play and the number.
    """
    league = (game or {}).get('league') or str(pick.get('id', '')).split('-')[0]
    tail = ' '.join(x for x in (PLAYBOOK, TAGS.get(league, '')) if x)
    head = f"🍳 {pick_card.kicker(pick)}"
    price = f"{int(pick['odds']):+d} at {pick.get('book')} · {pick_card.units_label(pick)}"
    if pick_card.play_kind(pick) == 'parlay':
        legs = [str(l.get('title') or '') for l in pick.get('legs') or [] if l.get('title')]
        count = f"{len(pick.get('legs') or [])} legs · {price}"
        top = '\n'.join([head, count, *[f'• {leg}' for leg in legs]])
        options = ([top, 'Just for fun.', tail], [top, tail], [head, count, tail])
    else:
        top = '\n'.join([head, pick_card.display_title(pick, game), price] + ([now_line(pick, now_quote)] if now_line(pick, now_quote) else []))
        number = pick_card.number_line(pick)
        if reason is None:
            reason = load_reasons().get(str(pick.get('id')))
        if reason and not plain(reason):
            reason = None
        options = ([top, '\n'.join(x for x in (number, reason) if x), tail], [top, number, tail], [top, tail])
    for parts in options:
        text = '\n\n'.join(part for part in parts if part)
        if tweet_length(text) <= LIMIT and not guard(text, pick, reason, now_quote):
            return text                 # a reason that trips a guard costs the reason, never the post
    return top[:LIMIT]


def pricing_fmt(value):
    return f'{float(value):g}'


def x_style(text):
    """The house style for a post: everything check_style asks for except that a post may carry an emoji."""
    return [p for p in llm.check_style(text) if 'emoji' not in p]


def now_line(pick, quote):
    """'Now: 52 at -110, DraftKings' when the best number available as the post goes out is not the published one."""
    if not quote or pick.get('legs'):
        return ''
    book, line, odds = quote
    if float(line) == float(pick['line']) and int(odds) == int(pick['odds']) and book == pick.get('book'):
        return ''
    shown = pricing.signed(float(line)) if pick.get('marketType') == 'spread' else pricing.fmt(float(line))
    return f'Now: {shown} at {int(odds):+d}, {book}'


def guard(text, pick, reason=None, now_quote=None):
    problems = x_style(text.replace(SITE, ''))
    extra = [{'legCount': len(pick['legs'])}] if pick.get('legs') else []      # "3 legs" is a count of the pick's own legs
    if reason:
        extra.append({'reason': reason})       # a stored reason's numbers come from a verified fact or the player's own games
    if now_quote:
        extra.append({'now': list(now_quote)})  # the number available now comes from the latest capture
    extra.append({'stake': pick_card.stake(pick)})                              # "1 unit" is the stake the record counts
    ok, strays = llm.numbers_ok(text, pick, extra)
    if not ok:
        problems.append(f"numbers not in the pick: {', '.join(strays)}")
    if tweet_length(text) > LIMIT:
        problems.append(f'{tweet_length(text)} characters')
    return problems


def refuse(pick, game, log, now, text=None):
    """The reason this pick must not be posted now, or None."""
    if pick.get('favorite') is not True and not pick.get('modelLean') and not (pick.get('legs') or pick.get('parlayType')):
        raise Refused('only favorites, model leans, prop leans and the longshot go to X')
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
    parser.add_argument('--card', action='store_true', help='render the pick card (scripts/pick_card.py) and attach it')
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
            card = None
            if args.card:
                import pick_card
                card = pick_card.render(pick_card.svg(pick, game), CONF / 'x-drafts' / f"{pick['id']}.png")
                print(f'card: {card}')
            if args.command == 'post':
                if not args.confirm:
                    print('\nnot posted: add --confirm to post this text')
                    return 0
                log = load_log()
                refuse(pick, game, log, now, text)
                creds = credentials()
                media = [upload_media(card.read_bytes(), creds)] if card else None
                tweet_id = post_tweet(text, creds, media_ids=media)
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
                if (merged.get('favorite') is not True and not merged.get('modelLean') and not merged.get('legs')) \
                        or merged.get('result') or key in {p['id'] for p in log['posts']}:
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
