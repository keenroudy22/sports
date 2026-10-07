"""Deliver approved posts into the Kook'n Discord.

Official plays use the Buffer schedule as their clock but arrive in Discord first. Other copy remains deliberately
downstream of Buffer and waits until X says the post was sent. The exact text and public card URL are saved with a
newly scheduled Buffer entry, then marked sent here so a later desk run cannot duplicate it.
"""
import json
import hashlib
import os
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

import gates
from social_copy import without_playbook


class DiscordError(RuntimeError):
    pass


def webhook(env=None):
    return ((env if env is not None else os.environ).get('DISCORD_WEBHOOK_URL') or '').strip()


def arb_webhook(env=None):
    """Use a dedicated Arb Radar channel when configured, otherwise the existing plays channel."""
    values = env if env is not None else os.environ
    return (values.get('DISCORD_ARB_WEBHOOK_URL') or values.get('DISCORD_WEBHOOK_URL') or '').strip()


def wins_webhook(env=None):
    """Dedicated community-win destination; never fall back to the official plays feed."""
    return ((env if env is not None else os.environ).get('DISCORD_WINS_WEBHOOK_URL') or '').strip()


def http_send(url, body, headers):
    data = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise DiscordError(f'Discord network error: {type(error).__name__}') from error


MAX_IMAGE_BYTES = 8 * 1024 * 1024


def download_image(url, opener=urllib.request.urlopen):
    """Fetch a public card for a durable Discord attachment, never a short-lived external embed."""
    request = urllib.request.Request(url, headers={'User-Agent': 'KooknSports/1.0'})
    try:
        with opener(request, timeout=30) as response:
            data = response.read(MAX_IMAGE_BYTES + 1)
            content_type = (response.headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError) as error:
        raise DiscordError(f'card download failed: {type(error).__name__}') from error
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise DiscordError('card download failed: invalid size')
    if content_type not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
        content_type = mimetypes.guess_type(urllib.parse.urlparse(url).path)[0] or ''
    if content_type not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
        raise DiscordError('card download failed: unsupported image type')
    extension = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif'}[content_type]
    return data, content_type, f'kookn-card.{extension}'


def multipart(payload, image):
    """Discord's payload_json plus one uploaded image."""
    data, content_type, filename = image
    boundary = '----KooknDiscord' + hashlib.sha256(data).hexdigest()[:20]
    chunks = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
        'Content-Type: application/json\r\n\r\n'.encode('utf-8'),
        json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'.encode('utf-8'),
        data,
        f'\r\n--{boundary}--\r\n'.encode('utf-8'),
    ]
    return b''.join(chunks), f'multipart/form-data; boundary={boundary}'


def send_message(url, text, image_url=None, send=http_send, username="Kook'n Sports", fetch=download_image):
    """Send one webhook message without ever putting the secret URL in an error or log.

    Cards are uploaded to Discord so an old post cannot break when the generated site card rolls out of the
    current build. If the card cannot be downloaded, the external embed remains a safe delivery fallback.
    """
    body = {'username': username, 'avatar_url': 'https://keenroudy.com/sports/kookn-mark.png',
            'content': without_playbook(text)}
    headers = {'Content-Type': 'application/json', 'User-Agent': 'KooknSports/1.0'}
    if image_url:
        try:
            image = fetch(image_url)
        except DiscordError:
            body['embeds'] = [{'image': {'url': image_url}}]
        else:
            body['attachments'] = [{'id': 0, 'filename': image[2]}]
            body, content_type = multipart(body, image)
            headers['Content-Type'] = content_type
    status, raw = send(url, body, headers)
    if status not in (200, 204):
        detail = raw.decode('utf-8', 'replace')[:240] if isinstance(raw, bytes) else str(raw)[:240]
        raise DiscordError(f'Discord returned HTTP {status}: {detail}')


ARB_QUIET = timedelta(hours=6)


def send_arb_alert(text, alert_id, now, state_path, url=None, send=None):
    """Post one time-sensitive arb to Discord once per six hours; never to X or the public record."""
    url = url if url is not None else arb_webhook()
    if not url:
        return False
    path = Path(state_path)
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    key = hashlib.sha256(str(alert_id).encode('utf-8')).hexdigest()[:20]
    if key in state and now - gates.when(state[key]) < ARB_QUIET:
        return False
    kwargs = {'username': "Kook'n Arb Radar"}
    if send is not None:
        kwargs['send'] = send
    send_message(url, text, **kwargs)
    state = {k: v for k, v in state.items() if now - gates.when(v) < timedelta(days=2)}
    state[key] = gates.stamp(now)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(state, indent=1) + '\n', encoding='utf-8')
    temporary.replace(path)
    return True


def mirror_sent(log_book, now, url=None, wins_url=None, send=http_send, fetch=download_image, log=print):
    """Deliver each Discord payload once.

    Confirmed plays carry ``readyAt`` and go to Discord before X. House, news and engagement posts keep the old
    downstream rule and wait for Buffer to confirm X. Return only newly changed failures, so ntfy does not repeat.
    """
    url = url if url is not None else webhook()
    wins_url = wins_url if wins_url is not None else wins_webhook()
    if not url and not wins_url:
        return []
    failed = []
    for entry in log_book.get('posts', []):
        mirror = entry.get('discord') or {}
        ready = mirror.get('readyAt') and gates.when(mirror['readyAt']) <= now
        if mirror.get('state') != 'pending' or not (ready or entry.get('sentAt')) \
                or entry.get('cancelledAt') or entry.get('deletedAt'):
            continue
        target = wins_url if mirror.get('destination') == 'wins' else url
        if not target:
            message = 'Discord destination is not configured'
            changed = mirror.get('error') != message
            mirror['error'] = message
            mirror['lastAttemptAt'] = gates.stamp(now)
            mirror['attempts'] = int(mirror.get('attempts') or 0) + 1
            entry['discord'] = mirror
            log(f"discord: {entry['id']} not mirrored: {message}")
            if changed:
                failed.append({'id': entry['id'], 'error': message})
            continue
        try:
            send_message(target, mirror.get('text') or '', mirror.get('image'), send=send, fetch=fetch)
        except DiscordError as error:
            message = str(error)
            changed = mirror.get('error') != message
            mirror['error'] = message
            mirror['lastAttemptAt'] = gates.stamp(now)
            mirror['attempts'] = int(mirror.get('attempts') or 0) + 1
            entry['discord'] = mirror
            log(f"discord: {entry['id']} not mirrored: {message}")
            if changed:
                failed.append({'id': entry['id'], 'error': message})
            continue
        mirror['state'] = 'sent'
        mirror['sentAt'] = gates.stamp(now)
        mirror['beforeX'] = not bool(entry.get('sentAt'))
        mirror.pop('error', None)
        mirror.pop('lastAttemptAt', None)
        entry['discord'] = mirror
        log(f"discord: {entry['id']} " + ('posted before X' if mirror['beforeX'] else 'mirrored after X'))
    for entry in log_book.get('posts', []):
        mirror = entry.get('discord') or {}
        followup = mirror.get('followup') or {}
        if followup.get('state') != 'pending':
            continue
        target = wins_url if mirror.get('destination') == 'wins' else url
        if not target:
            continue
        try:
            send_message(target, followup.get('text') or '', send=send)
        except DiscordError as error:
            message = str(error)
            changed = followup.get('error') != message
            followup['error'] = message
            followup['lastAttemptAt'] = gates.stamp(now)
            followup['attempts'] = int(followup.get('attempts') or 0) + 1
            mirror['followup'] = followup
            entry['discord'] = mirror
            log(f"discord: {entry['id']} update not sent: {message}")
            if changed:
                failed.append({'id': entry['id'], 'error': message})
            continue
        followup['state'] = 'sent'
        followup['sentAt'] = gates.stamp(now)
        followup.pop('error', None)
        followup.pop('lastAttemptAt', None)
        mirror['followup'] = followup
        entry['discord'] = mirror
        log(f"discord: {entry['id']} pull update sent")
    return failed
