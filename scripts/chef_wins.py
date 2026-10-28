"""Post the owner's winning-slip screenshots to the community wins channel.

This private intake is deliberately separate from X, official Plays & Results
and the public record.  Files are deduplicated by bytes and capped at three per
Eastern day; a missing webhook holds them and alerts only once per day.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import discord_post
import gates
import social_style
from social_copy import with_age_notice

INBOX = Path('/Users/keen/Documents/ChatGPT/Kook\'n/chef-wins')
STATE = Path.home() / '.config' / 'keenroudy' / 'work' / 'chef-wins-seen.json'
TEXT = with_age_notice("🧑‍🍳 The chef's own ticket cashed ✅ Personal ticket, not a Kook'n best bet.")
MAX_DAY = 3
MIME = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.webp': 'image/webp', '.gif': 'image/gif'}


def is_image(path):
    """Accept only files whose bytes match their supported image extension."""
    try:
        head = Path(path).read_bytes()[:12]
    except OSError:
        return False
    suffix = Path(path).suffix.lower()
    if suffix == '.png':
        return head.startswith(b'\x89PNG\r\n\x1a\n')
    if suffix in ('.jpg', '.jpeg'):
        return head.startswith(b'\xff\xd8\xff')
    if suffix == '.gif':
        return head.startswith((b'GIF87a', b'GIF89a'))
    if suffix == '.webp':
        return len(head) >= 12 and head[:4] == b'RIFF' and head[8:12] == b'WEBP'
    return False


def load(path=STATE):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save(value, path=STATE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    temp.chmod(0o600)
    temp.replace(path)


def images(folder=INBOX):
    try:
        return sorted((path for path in Path(folder).iterdir()
                       if path.is_file() and path.suffix.lower() in MIME and is_image(path)),
                      key=lambda path: (path.stat().st_mtime, path.name.lower()))
    except OSError:
        return []


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pending(folder=INBOX, state_path=STATE):
    seen = set((load(state_path).get('seen') or {}).keys())
    return [path for path in images(folder) if digest(path) not in seen]


def send_file(url, path, send=discord_post.http_send, now=None):
    # Raw slips can expose dollars and bet IDs; keep originals private and pending.
    if (now or datetime.now(timezone.utc)) >= social_style.PRIVACY_EFFECTIVE and not social_style.current_png(Path(path)):
        raise discord_post.DiscordError("owner slip needs a privacy-checked native graphic; original held")
    data = Path(path).read_bytes()
    if not data or len(data) > discord_post.MAX_IMAGE_BYTES:
        raise discord_post.DiscordError('owner slip has an invalid image size')
    payload = {'username': "Kook'n Sports",
               'avatar_url': 'https://keenroudy.com/sports/kookn-chef.png?v=20261007',
               'content': TEXT, 'attachments': [{'id': 0, 'filename': path.name}]}
    body, content_type = discord_post.multipart(payload, (data, MIME[path.suffix.lower()], path.name))
    status, raw = send(url, body, {'Content-Type': content_type, 'User-Agent': 'KooknSports/1.0'})
    if status not in (200, 204):
        raise discord_post.DiscordError(f'Discord returned HTTP {status}')
    return raw


def run(now=None, folder=INBOX, state_path=STATE, url=None, send=discord_post.http_send,
        notify=lambda *_: None, log=print):
    now = now or datetime.now(timezone.utc)
    local_day = now.astimezone(gates.EASTERN).date().isoformat()
    state = load(state_path)
    state.setdefault('seen', {})
    waiting = pending(folder, state_path)
    if not waiting:
        return {'posted': 0, 'held': 0}
    url = url if url is not None else discord_post.wins_webhook()
    if not url:
        if state.get('webhookAlertDate') != local_day:
            notify("Kook'n chef wins held", 'A winning-slip image is waiting, but the wins Discord webhook is not configured.')
            state['webhookAlertDate'] = local_day
            save(state, state_path)
        return {'posted': 0, 'held': len(waiting)}
    already = sum(row.get('day') == local_day
                  for row in state['seen'].values() if isinstance(row, dict))
    posted = 0
    for path in waiting:
        if posted >= max(0, MAX_DAY - already):
            break
        if now >= social_style.PRIVACY_EFFECTIVE and not social_style.current_png(path):
            log(f'chef wins: {path.name} held: original needs a privacy-checked native graphic')
            continue
        key = digest(path)
        try:
            send_file(url, path, send, now=now)
        except (OSError, discord_post.DiscordError) as error:
            log(f'chef wins: {path.name} held ({type(error).__name__})')
            break
        state['seen'][key] = {'name': path.name, 'sentAt': gates.stamp(now), 'day': local_day}
        posted += 1
        log(f'chef wins: {path.name} posted to the community wins channel')
    state.pop('webhookAlertDate', None)
    save(state, state_path)
    return {'posted': posted, 'held': max(0, len(waiting) - posted)}
