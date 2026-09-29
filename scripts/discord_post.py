"""Mirror posts that Buffer confirmed on X into the Kook'n Discord.

The Discord webhook is deliberately downstream of Buffer: nothing reaches Discord until X says the
post was sent. The exact X text and public card URL are saved with a newly scheduled Buffer entry,
then marked sent here so a later desk run cannot duplicate it.
"""
import json
import os
import urllib.error
import urllib.request

import gates


class DiscordError(RuntimeError):
    pass


def webhook(env=None):
    return ((env if env is not None else os.environ).get('DISCORD_WEBHOOK_URL') or '').strip()


def http_send(url, body, headers):
    request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise DiscordError(f'Discord network error: {type(error).__name__}') from error


def send_message(url, text, image_url=None, send=http_send):
    """Send one webhook message without ever putting the secret URL in an error or log."""
    body = {'username': "Kook'n Sports", 'avatar_url': 'https://keenroudy.com/sports/kookn.jpg', 'content': text}
    if image_url:
        body['embeds'] = [{'image': {'url': image_url}}]
    status, raw = send(url, body, {'Content-Type': 'application/json', 'User-Agent': 'KooknSports/1.0'})
    if status not in (200, 204):
        detail = raw.decode('utf-8', 'replace')[:240] if isinstance(raw, bytes) else str(raw)[:240]
        raise DiscordError(f'Discord returned HTTP {status}: {detail}')


def mirror_sent(log_book, now, url=None, send=http_send, log=print):
    """Mirror eligible sent X posts once. Return only newly changed failures, so ntfy does not repeat them."""
    url = url if url is not None else webhook()
    if not url:
        return []
    failed = []
    for entry in log_book.get('posts', []):
        mirror = entry.get('discord') or {}
        if mirror.get('state') != 'pending' or not entry.get('sentAt') or entry.get('cancelledAt') or entry.get('deletedAt'):
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
        mirror.pop('error', None)
        mirror.pop('lastAttemptAt', None)
        entry['discord'] = mirror
        log(f"discord: {entry['id']} mirrored after X")
    return failed
