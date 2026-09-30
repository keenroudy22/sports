"""Deliver approved posts into the Kook'n Discord.

Official plays use the Buffer schedule as their clock but arrive in Discord first. Other copy remains deliberately
downstream of Buffer and waits until X says the post was sent. The exact text and public card URL are saved with a
newly scheduled Buffer entry, then marked sent here so a later desk run cannot duplicate it.
"""
import json
import hashlib
import os
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path

import gates


class DiscordError(RuntimeError):
    pass


def webhook(env=None):
    return ((env if env is not None else os.environ).get('DISCORD_WEBHOOK_URL') or '').strip()


def arb_webhook(env=None):
    """Use a dedicated Arb Radar channel when configured, otherwise the existing plays channel."""
    values = env if env is not None else os.environ
    return (values.get('DISCORD_ARB_WEBHOOK_URL') or values.get('DISCORD_WEBHOOK_URL') or '').strip()


def http_send(url, body, headers):
    request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise DiscordError(f'Discord network error: {type(error).__name__}') from error


def send_message(url, text, image_url=None, send=http_send, username="Kook'n Sports"):
    """Send one webhook message without ever putting the secret URL in an error or log."""
    body = {'username': username, 'avatar_url': 'https://keenroudy.com/sports/kookn.jpg', 'content': text}
    if image_url:
        body['embeds'] = [{'image': {'url': image_url}}]
    status, raw = send(url, body, {'Content-Type': 'application/json', 'User-Agent': 'KooknSports/1.0'})
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


def mirror_sent(log_book, now, url=None, send=http_send, log=print):
    """Deliver each Discord payload once.

    Confirmed plays carry ``readyAt`` and go to Discord before X. House, news and engagement posts keep the old
    downstream rule and wait for Buffer to confirm X. Return only newly changed failures, so ntfy does not repeat.
    """
    url = url if url is not None else webhook()
    if not url:
        return []
    failed = []
    for entry in log_book.get('posts', []):
        mirror = entry.get('discord') or {}
        ready = mirror.get('readyAt') and gates.when(mirror['readyAt']) <= now
        if mirror.get('state') != 'pending' or not (ready or entry.get('sentAt')) \
                or entry.get('cancelledAt') or entry.get('deletedAt'):
            continue
        try:
            send_message(url, mirror.get('text') or '', mirror.get('image'), send=send)
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
        try:
            send_message(url, followup.get('text') or '', send=send)
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
