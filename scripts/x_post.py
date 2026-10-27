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
import social_units
import voice
import voice_pick
import re
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
    problems = x_style(text)
    if problems:
        raise Refused('; '.join(problems))
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


def record(log, key, text, tweet_id, kind, now, card_theme='none'):
    log['posts'].append({'id': key, 'postedAt': gates.stamp(now), 'tweetId': tweet_id, 'textHash': text_hash(text),
                         'kind': kind, 'cardTheme': card_theme if card_theme in ('legacy', 'felt', 'ticket') else 'none'})
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
    """The factual reason line in any owner-approved caption shape."""
    skip = ('@Playbook', 'Copy the bet 👇 @Playbook', '21+ only', '#', '❤️', 'Book says ', 'Now ', "I'm at ", "I've got ", "My number's ",
            'I have ', 'Book has them losing.', '🍳 ', '🐕 ', '👨‍🍳 ', 'TNF: ', 'MNF: ', 'Saturday night: ')
    lines = [line.strip() for line in str(text or '').splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.startswith(("I've got ", "I'm at ", "My number's ", 'Book says ', 'I have ')):
            sentences = llm.re.split(r'(?<=[.!?])\s+', line)
            skip_count = 2 if line.startswith('Book says ') else 1
            if len(sentences) > skip_count:
                return ' '.join(sentences[skip_count:]).strip()
            continue
        if line in voice_pick.pools()['asks'] or line.startswith(skip) or llm.re.search(r'\([+-]\d+,\s*(?:DraftKings|FanDuel|DK|FD)\)$', line):
            continue
        if index and lines[index - 1].startswith(('🍳 ', '🐕 ', '👨‍🍳 ')) and index + 1 < len(lines) \
                and llm.re.match(r'^[+-]\d+', lines[index + 1]):
            continue
        if llm.re.search(r'\b(?:OVER|UNDER)\s+[+-]?\d', line) or line.startswith('Our number '):
            continue
        if llm.re.match(r'^[+-]\d+(?:\s+at\s+|$)', line):
            continue
        if any(token in line for token in (' over ', ' under ', ' +', ' -')) and '(' in line:
            continue
        return line
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
    return strip_reason(pick)


def strip_reason(pick):
    """A supporting exact-line sentence only when the stored hit strip backs this side."""
    strip = pick.get('hitStrip') or {}
    season, last = strip.get('season') or (), strip.get('last10') or ()
    if (len(season) == 2 and season[1] >= 5 and season[0] / season[1] >= 0.6
            and isinstance(pick.get('line'), (int, float))):
        side = str(pick.get('direction') or '').lower()
        if side in ('over', 'under'):
            text = f"{side.title()} {pricing.fmt(pick['line'])} in {season[0]} of {season[1]} this season"
            text += '.'
            if plain(text):
                return text
    return None


PLAYBOOK = '@Playbook'     # the betslip bot (Action Network): tagged on a bet, it replies with the slip pre-loaded
ASK = "❤️ if you're tailing"                   # the ask the big accounts close on (docs/X-NOTES.md): a like is a vote to tail
LADDER_ASK = "Still climbing? ❤️"
LOTTO = 1000                                   # a fun parlay paying this or more is a lotto, and its post says so first
REASONS = ROOT / 'data' / 'x-reasons.json'   # the reason each play's post gives, chosen when the play is published


def load_reasons(path=None):
    try:
        return json.loads(Path(path or REASONS).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_reasons(reasons, path=None):
    target = Path(path or REASONS)
    target.write_text(json.dumps(dict(sorted(reasons.items())), indent=1, ensure_ascii=False) + '\n', encoding='utf-8')


def parlay_head(pick, league):
    """A fun ticket leads with its exact posted price, leg count and public book."""
    odds = int(pick['odds'])
    return f"🎰 {odds:+d} Chef's Special ({public_book(pick.get('book'))})"


def public_book(value):
    """The current bettor-facing brand; provider keys never reach public copy."""
    text = str(value or '').strip()
    key = re.sub(r'[^a-z0-9]', '', text.lower())
    names = {'espnbet': 'theScore Bet', 'thescorebet': 'theScore Bet',
             'draftkings': 'DraftKings', 'fanduel': 'FanDuel',
             'betmgm': 'BetMGM', 'betrivers': 'BetRivers',
             'caesars': 'Caesars', 'fanatics': 'Fanatics'}
    return names.get(key, text)


def ladder_text(pick):
    """The three money lines for the Kook'n 80/20 Climb: stake, return, bank and next ride."""
    info = pick.get('ladder') or {}
    if social_units.active(pick):
        head = (f"80/20 CLIMB · STEP {info.get('step', 1)}\n"
                f"{social_units.climb(info.get('stake'))} ({int(pick['odds']):+d}, {public_book(pick.get('book'))})")
        return head, '', ''
    head = (f"{pick_card.dollars(info.get('start', 50))} → {pick_card.dollars(info.get('goal', 1000))} · "
            f"80/20 CLIMB · STEP {info.get('step', 1)}\n"
            f"{pick_card.dollars(info.get('stake'))} → {pick_card.dollars(info.get('payout'))} "
            f"({int(pick['odds']):+d}, {public_book(pick.get('book'))})")
    bank = (f"Step {max(1, int(info.get('step') or 1) - 1)} cashed. " if int(info.get('step') or 1) > 1 else '')
    if info.get('banked', 0):
        bank += f"{pick_card.dollars(info.get('banked'))} in the bank."
    else:
        bank = bank.strip()
    money = ''
    return head, money, bank


def safer_text(pick, legs, league):
    """The owner-written Safer combo shape, filled only from the stored ticket."""
    head = f"🛡️ Safer combo ({int(pick['odds']):+d}, {public_book(pick.get('book'))})"
    facts = []
    for leg in pick.get('legs') or []:
        facts.extend(str(value).strip() for value in leg.get('reasons') or [] if str(value).strip())
    fact = _short_reason(facts[0]) if facts else ''
    import parlay_caption
    return parlay_caption.layout(head, legs, '\n'.join(part for part in (fact, '@Playbook #' + str(league)) if part))


def _caption_day(pick, game):
    value = (game or {}).get('kickoff') or pick.get('publishedAt') or datetime.now(timezone.utc)
    return eastern_date(gates.when(value)).isoformat()


def _short_reason(text):
    """Keep a verified reason short without turning it into a fragment."""
    value = str(text or '').strip()
    words = value.split()
    # A complete, sourced sentence is better public copy than a shorter noun
    # phrase.  Fourteen words still keeps the post compact and preserves facts
    # such as "X and Y are out with hamstring injuries" whole.
    if len(words) <= 14:
        return ' '.join(words)
    # Never manufacture a dangling half-sentence merely to hit the public
    # word limit (for example, "... Saturday and has.").  Prefer a complete
    # leading clause already present in the verified source; if there is no
    # safe clause, omit this candidate and let _choose_reason try the next
    # stored fact.  The send guard will hold when no complete reason survives.
    for clause in llm.re.split(r'\s+(?:and|but|which|while|so)\s+|[;:]', value, maxsplit=1):
        clause = clause.strip().rstrip(',;: ')
        if 4 <= len(clause.split()) <= 12:
            return clause + ('' if clause.endswith(('.', '!', '?')) else '.')
    return ''


def _choose_reason(pick, supplied, history, day):
    # The saved publication reason wins. If it is absent, recover the strongest
    # verified supporting sentence already stored on the pick. If neither is
    # usable, the caller's guard holds the post; a reason is never stripped and
    # sent blank.
    import market_support
    structured = []
    for row in [*((pick.get('dossier') or {}).get('reasons') or []), *(pick.get('reasons') or [])]:
        value = row.get('text') if isinstance(row, dict) else row
        shortened = _short_reason(value) if value else ''
        if shortened and plain(shortened):
            structured.append(shortened)
    choices = [supplied, strip_reason(pick), *structured]
    from social_copy import projection_free_reason
    choices = list(dict.fromkeys(projection_free_reason(_short_reason(choice)) for choice in choices if choice))
    # The fixed model-vs-book sentence is already its own caption line.  It is
    # not the required factual reason and repeating it makes reason_in() (and
    # readers) see a number-only post.
    player = pick_card.play_kind(pick) == 'player'
    choices = [choice for choice in choices if plain(choice) and choice.split()
               and not choice.startswith('Book says ')
               and market_support.allowed(pick, choice)
               and (player or choice.split()[0].lower() not in DANGLING)]
    recent = [row for row in history or [] if (row.get('series') or row.get('kind')) in ('play', 'buffer:play')]
    recent_kinds = [row.get('reasonKind') for row in recent if row.get('reasonKind') not in (None, 'none')]
    today_kinds = [row.get('reasonKind') for row in recent if str(row.get('postedAt') or row.get('dueAt') or '').startswith(day)]
    for choice in choices:
        kind = reason_kind(choice)
        if len(recent_kinds) >= 2 and recent_kinds[-2:] == [kind, kind]:
            continue
        if today_kinds.count(kind) >= 2:
            continue
        return choice
    return choices[0] if choices else None


def _number_line(pick, game, day, history, salt=0):
    return ''  # Social bets lead with the exact wager and factual support, not a forecast.


def _play_prefix(pick, game, featured):
    if pick.get('lane') == 'chef_pick':
        return "🍳 Chef's Pick: "
    if pick.get('selectionPolicy') == gates.TIER_POLICY and pick.get('lane') == 'best_bet':
        return 'Best Bet: '
    if featured:
        return '🍳 Hot Plate (POTD): '
    if pick.get('lane') == 'upset':
        return '🐕 Upset pick: '
    if pick.get('lane') == 'gut_call':
        return '🔥 Full Send: '
    kickoff = (game or {}).get('kickoff')
    if not kickoff or gates.when(kickoff).astimezone(gates.EASTERN).hour < 19:
        return ''
    day = gates.when(kickoff).astimezone(gates.EASTERN).weekday()
    league = (game or {}).get('league') or pick.get('league')
    return 'TNF: ' if league == 'NFL' and day == 3 else 'MNF: ' if league == 'NFL' and day == 0 \
        else 'Saturday night: ' if league == 'CFB' and day == 5 else ''


def _searchable_matchup(game):
    """Full human team names for search/discovery, never logo or abbreviation only."""
    if not game:
        return ''
    league = game.get('league')
    def name(team):
        team = team or {}
        if league == 'CFB':
            return team.get('school') or team.get('short') or team.get('name') or ''
        return team.get('name') or team.get('short') or ''
    away, home = name(game.get('away')), name(game.get('home'))
    return f'{away} at {home}' if away and home else away or home


def _searchable_play_title(pick, game):
    """Keep the bettor-style play while spelling out the people and teams people search."""
    title = pick_card.short_title(pick, game)
    matchup = _searchable_matchup(game)
    if not matchup:
        return title
    # Player props need the player's full stored name plus a searchable team matchup.
    # Game totals already contain the matchup; rebuild them with the full names.
    if pick.get('athleteId') or pick.get('market'):
        return f'{title} · {matchup}'
    if pick.get('marketType') == 'total':
        direction = str(pick.get('direction') or '').lower()
        line = pick.get('line')
        if direction in ('over', 'under') and isinstance(line, (int, float)):
            return f'{matchup} {direction} {pricing.fmt(float(line))}'
    return title if all(part.lower() in title.lower() for part in matchup.split(' at ')) else f'{title} · {matchup}'


def copy_variant(text):
    return voice_pick.detect_shape(text)


def draft(pick, game=None, weights=None, reason=None, now_quote=None, featured=False, history=None):
    """The post, short and plain, the way a bettor types it (the owner, 2026-09-26: "Not so AI looking. And straight
    to the point on the tweets"):

        POTD: Iowa/Michigan over 38.5 (-105, ESPN BET)      ("POTD: " on the Pick of the Day only)
        We have it at 47.

        ❤️ if you're tailing
        @Playbook #CFB

    A fun parlay leads with its price and book, "🎰 +2506 COLLEGE LOTTO (ESPN BET)", then its legs one a line; a
    ladder rung "🪜 KOOK'N 80/20 CLIMB · STEP 2", "$75 → $146", the bank/ride split, then its legs. No filler slogans;
    the card carries the site and "Entertainment only". No units. One saved supporting reason may follow the number.
    It was selected from structured evidence at publication; never select an arbitrary sentence as support.
    """
    league = (game or {}).get('league') or str(pick.get('id', '')).split('-')[0]
    day = _caption_day(pick, game)
    history = history if history is not None else load_log().get('posts', [])
    tail = ' '.join(x for x in (PLAYBOOK, TAGS.get(league, '')) if x)
    kind = pick_card.play_kind(pick)
    legs = [pick_card.short_leg(l.get('title')) for l in pick.get('legs') or [] if l.get('title')]
    night = False
    if (game or {}).get('kickoff'):
        try:
            night = gates.when(game['kickoff']).astimezone(gates.EASTERN).hour >= 19
        except (TypeError, ValueError):
            pass
    if kind == 'ladder':
        head, money, bank = ladder_text(pick)
        import parlay_caption
        top = parlay_caption.layout('\n'.join(x for x in (head, money, bank) if x), legs)
        options = ([top, f'{LADDER_ASK}\n{tail}'], [top, tail])
    elif kind == 'parlay':
        if pick.get('parlayType') == 'comfort' or pick.get('lane') == 'safer_combo':
            options = ([safer_text(pick, legs, league)],)
            # The Safer shape carries its own fixed tail and no engagement ask.
            for parts in options:
                text = '\n\n'.join(part for part in parts if part)
                if tweet_length(text) <= LIMIT and not guard(text, pick, None, now_quote):
                    return text
            return '\n\n'.join(options[-1])
        odds = int(pick['odds'])
        payout = 10 * (1 + odds / 100) if odds > 0 else 10 * (1 + 100 / abs(odds))
        import parlay_caption
        stake = (social_units.label(pick['riskUnits']) if pick.get('riskUnits') is not None else '') if social_units.active(pick) else f"$10 → {pick_card.dollars(payout)}"
        top = parlay_caption.layout(parlay_head(pick, league), legs, stake)
        options = ([top, f'{ASK}\n{tail}'], [top, tail])
    else:
        prefix = _play_prefix(pick, game, featured)
        play_text = f"{prefix}{_searchable_play_title(pick, game)}"
        play = f"{play_text} ({int(pick['odds']):+d}, {public_book(pick.get('book'))})"
        now = now_line(pick, now_quote)
        projection, line = pick.get('projection'), pick.get('line')
        number = ''
        saved_reason = reason if reason is not None else load_reasons().get(pick.get('id'))
        reason = _choose_reason(pick, saved_reason, history, day)
        for salt in range(1, 5):
            if not voice_pick.five_word_overlap(' '.join(part for part in (number, reason) if part), history):
                break
            # The model-vs-book sentence is intentionally fixed owner voice; vary the verified reason instead.
        required = ('C' if isinstance(projection, (int, float)) and isinstance(line, (int, float)) and line
                    and abs(projection - line) / abs(line) > .25 else None)
        shape = voice_pick.choose_shape(pick.get('id'), day, history=history, required=required)
        asks = voice_pick.pools()['asks']
        if featured or pick.get('lane') in ('upset', 'special'):
            asks = [ask for ask in asks if ask]
        ask = voice_pick.choose_slot('ask', pick.get('id'), day, history=history, values=asks)
        if not (featured or pick.get('lane') in ('upset', 'special')) and voice_pick.index(f"{pick.get('id')}:{day}:ask-use", 2):
            ask = ''
        if reason and voice_pick.index(f"{pick.get('id')}:{day}:reason-wrap", 3) == 0:
            side = 'higher' if not isinstance(projection, (int, float)) or not isinstance(line, (int, float)) or projection >= line else 'lower'
            reason = voice_pick.pools()['reasonWrappers'][side][0].format(reason=reason)
        fields = {'play': play_text, 'odds': f"{int(pick['odds']):+d}", 'book': public_book(pick.get('book')),
                  'number': number, 'reason': reason or '', 'ask': ask, 'L': league,
                  'line': pricing.fmt(float(line)) if isinstance(line, (int, float)) else '',
                  'proj': ''}
        shapes = [shape] if required else [shape, *[candidate for candidate in ('A', 'B', 'C', 'D') if candidate != shape]]
        options = []
        for candidate in shapes:
            # Empty template rows are deliberate paragraph breaks. Omit empty
            # optional fields without flattening the owner's caption spacing.
            shape_lines = [rendered for part in voice_pick.pools()['playShapes'][candidate]
                           if (rendered := part.format(**fields).strip()) or part == '']
            top = llm.re.sub(r'\n{3,}', '\n\n', '\n'.join(shape_lines)).strip()
            if now:
                bits = top.splitlines()
                price_at = next((i for i, bit in enumerate(bits) if llm.re.search(r'\([+-]\d+,\s*[^)]+\)$', bit)), 0)
                bits.insert(price_at + 1, now); top = '\n'.join(bits)
            options.append([top])
        # Optional conversation copy must not strand an otherwise valid ticket.
        # Preserve the full wager, matchup, current price and sourced reason;
        # shorten only the repeated projection sentence and omit the extra ask.
        compact_number = ''
        if reason:
            options.append(['\n\n'.join(part for part in (
                play, now, '\n'.join(part for part in (compact_number, reason) if part), tail) if part)])
    for parts in options:
        text = '\n\n'.join(part for part in parts if part)
        if tweet_length(text) <= LIMIT and not guard(text, pick, reason, now_quote):
            return text
    return '\n\n'.join(part for part in options[-1] if part)


def pricing_fmt(value):
    return f'{float(value):g}'


def x_style(text):
    """The house style for a post: everything check_style asks for except that a post may carry an emoji."""
    return list(dict.fromkeys([p for p in llm.check_style(text) if 'emoji' not in p] + voice.lint(text)))


def now_line(pick, quote):
    """'Now 52 (-110, DraftKings)' when the best number available as the post goes out is not the published one."""
    if not quote or pick.get('legs'):
        return ''
    book, line, odds = quote
    if float(line) == float(pick['line']) and int(odds) == int(pick['odds']) and book == pick.get('book'):
        return ''
    shown = pricing.signed(float(line)) if pick.get('marketType') == 'spread' else pricing.fmt(float(line))
    return f'Now {shown} ({int(odds):+d}, {book})'


def guard(text, pick, reason=None, now_quote=None):
    problems = x_style(text.replace(SITE, ''))
    # A formatter may omit an unsafe suffix from the final shape.  Refuse the
    # source title anyway so a malformed saved play cannot slip through merely
    # because this particular caption template did not repeat the bad glyph.
    problems += [problem for problem in x_style(str(pick.get('title') or '')) if 'dash' in problem]
    problems = list(dict.fromkeys(problems))
    extra = [{'legCount': len(pick['legs'])}] if pick.get('legs') else []      # "3 legs" is a count of the pick's own legs
    if reason:
        extra.append({'reason': reason})       # a stored reason's numbers come from a verified fact or the player's own games
    if now_quote:
        extra.append({'now': list(now_quote)})  # the number available now comes from the latest capture
    extra.append({'stake': pick_card.stake(pick)})
    if social_units.active(pick) and pick.get('ladder'):
        extra.append({'climbUnits': [social_units.climb(v) for k, v in pick['ladder'].items() if k in ('stake', 'payout', 'banked', 'bankThisWin', 'nextStake', 'start', 'goal') and isinstance(v, (int, float))]})
    if pick.get('ladder'):          # "$1,062" reads as 1 and 62: the rung's dollars as the post writes them
        extra.append({k: pick_card.dollars(v) for k, v in pick['ladder'].items() if isinstance(v, int)})
    elif pick.get('legs') and isinstance(pick.get('odds'), (int, float)):
        odds = int(pick['odds'])
        example = 10 * (1 + odds / 100) if odds > 0 else 10 * (1 + 100 / abs(odds))
        extra.append({'exampleStake': 10, 'exampleReturn': pick_card.dollars(example)})
    if isinstance(pick.get('projection'), (int, float)):     # "We have it at 47": the projection as the post rounds it
        extra.append({'said': [pick_card.plain_number(abs(pick['projection'])), str(int(round(abs(pick['projection']))))]})
    # The exact standalone age notice is policy, not a wager statistic. Other
    # 21s (including a player's threshold) still need ordinary number evidence.
    wager_text = re.sub(r'(?m)^21\+ only$', '', text)
    ok, strays = llm.numbers_ok(wager_text, pick, extra)
    if not ok:
        problems.append(f"numbers not in the pick: {', '.join(strays)}")
    from social_copy import x_ticket_copy
    final_length = tweet_length(x_ticket_copy(text, 'play', pick.get('id', ''), pick))
    if final_length > LIMIT:
        problems.append(f'{final_length} characters including ticket tag and age notice')
    if social_units.active(pick):
        import social_style
        problems += social_style.privacy_issues(text)
    lane = pick.get('lane')
    if lane in ('best_bet', 'chef_pick', 'hot_plate', 'gut_call', 'upset') and not reason:
        problems.append('play has no supporting reason')
    probability = pick.get('probabilityAtPublication') or {}
    if lane in ('best_bet', 'chef_pick', 'hot_plate', 'gut_call', 'upset') and not pick.get('legs'):
        chance, needed = probability.get('chance'), probability.get('breakEven')
        if not all(isinstance(value, (int, float)) for value in (chance, needed)):
            problems.append('play has no shared market-anchored chance')
        elif chance <= needed:
            problems.append(f'play chance {chance:.1%} does not beat the price need {needed:.1%}')
    import chef_picks
    problems += chef_picks.publication_issues(pick)
    if pick.get('selectionPolicy') == gates.TIER_POLICY or lane == 'chef_pick':
        expected = gates.staking.expected(pick) if lane in ('best_bet', 'chef_pick') else None
        if expected is None or pick.get('riskUnits') != expected or pick.get('selectionPolicy') != gates.TIER_POLICY:
            problems.append('play tier and published stake do not match')
    return problems


def cancelled_private_draft(entry):
    """Only a successfully removed, provider-verified private style draft is retryable.

    The queue auditor records this state after confirming scheduled status and
    successful deletion. Generic cancellations, unknown states and public receipts
    remain duplicate-protected. Keep the original row as delivery history.
    """
    audit = entry.get('socialStyleAudit') or {}
    return bool(entry.get('bufferPostId') and entry.get('cancelledAt')
                and audit.get('state') == 'cancelled-private'
                and audit.get('needsRevision') is True and audit.get('checkedAt')
                and not any(entry.get(k) for k in ('sentAt', 'tweetId', 'link')))


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
    protected = [p for p in log['posts'] if not cancelled_private_draft(p)]
    posted = {p['id'] for p in protected}
    if pick['id'] in posted:
        raise Refused('already posted')
    if text and text_hash(text) in {p.get('textHash') for p in protected}:
        raise Refused('this exact text was already posted')
    return None


# ------------------------------------------------------------------ recaps

def payout(odds):
    return odds / 100 if odds > 0 else 100 / -odds


def units_for(pick):
    """core.js unitsFor: saved riskUnits, default one; push/early exit zero; no price, no units."""
    odds, result = pick.get('odds'), pick.get('result')
    if not isinstance(odds, (int, float)) or result not in ('win', 'loss', 'push'):
        return None
    saved = pick.get('units')
    if isinstance(saved, (int, float)) and not pick.get('earlyExit'):
        return saved
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
    """The day's settled picks as a plain public result, win or lose."""
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
    everything = summarize(rows)
    head = f"{datetime.fromisoformat(day):%A} went {everything['win']}-{everything['loss']}" + (f"-{everything['push']}" if everything['push'] else '')
    def public_title(row):
        if pick_card.play_kind(row) == 'ladder':
            return f"80/20 Climb step {(row.get('ladder') or {}).get('step', 1)}"
        import result_display
        detail = result_display.detail(row)
        return f"{row['title']} · {detail}" if detail else str(row['title'])
    outcomes = [(r.get('result'), f"{'✅' if r.get('result') == 'win' else '❌' if r.get('result') == 'loss' else '➖'} {public_title(r)}") for r in rows]
    kept = list(range(len(outcomes)))
    while True:
        omitted = [outcomes[i][0] for i in range(len(outcomes)) if i not in kept]
        more = f"+{omitted.count('win')} wins, {omitted.count('loss')} misses on the site" if omitted else ''
        text = '\n'.join(x for x in (head, *(outcomes[i][1] for i in kept), more) if x)
        if tweet_length(text) <= LIMIT or not kept:
            return text
        wins = [i for i in kept if outcomes[i][0] == 'win']
        kept.remove(wins[-1] if wins else kept[-1])


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
    text = '\n'.join(lines)
    if tweet_length(text) > LIMIT:
        lines = lines[:-1]
        text = '\n'.join(lines)
    return text


# ------------------------------------------------------------------ command line

def load_picks(now):
    stores = gates.Stores()
    ctx = stores.as_of(now)
    return ctx.first, ctx.latest, ctx.games


def env_report():
    present = [key for key in CRED_KEYS.values() if os.environ.get(key)]
    return f"credentials set: {', '.join(present) or 'none'}"


def do_draft(pick_id, now, first, latest, games, out=None, reason=None):
    pick = first.get(pick_id)
    if not pick:
        raise Refused(f'{pick_id} is not in research/')
    merged = dict(pick, **latest.get(pick_id, {}))
    game = games.get((pick.get('gameIds') or [None])[0])
    # A newly admitted play is not in the public reason store yet.  Its
    # verified release reason must travel with the private draft instead of
    # disappearing between selection and the release queue.
    text = draft(merged, game, reason=reason)
    problems = guard(text, merged, reason=reason)
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
                card = pick_card.render(pick_card.modern_svg(pick, game, art=pick_card.artwork(pick, game)), CONF / 'x-drafts' / f"{pick['id']}.png")
                print(f'card: {card}')
            if args.command == 'post':
                if not args.confirm:
                    print('\nnot posted: add --confirm to post this text')
                    return 0
                log = load_log()
                refuse(pick, game, log, now, text)
                creds = credentials()
                media = [upload_media(card.read_bytes(), creds)] if card else None
                theme = pick_card.card_theme(item=pick) if card else 'none'
                tweet_id = post_tweet(text, creds, media_ids=media)
                save_log(record(log, pick['id'], text, tweet_id, 'pick', now, theme))
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
