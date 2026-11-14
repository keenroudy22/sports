"""Duplicate-safe X backup for revalidated releases during a local Buffer cap.

Eligibility remains with the calling release path: reviewed football, NBA and
CBB straights may use the reserved straight/recap capacity, while only the
explicitly supported Climb and fun-ticket families may use ticket capacity.
"""
import json
import re
from datetime import timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import gates
import x_post


def config(conf):
    path = conf / 'typefully.json'
    try:
        if path.stat().st_mode & 0o077:
            return None
        data = json.loads(path.read_text())
        if data.get('apiKey') and type(data.get('socialSetId')) is int:
            return data
    except (OSError, ValueError, AttributeError):
        pass
    return None


def request(settings, suffix='', payload=None):
    url = f"https://api.typefully.com/v2/social-sets/{settings['socialSetId']}/drafts{suffix}"
    req = Request(url, data=json.dumps(payload).encode() if payload else None,
                  headers={'Authorization': 'Bearer ' + settings['apiKey'],
                           'Content-Type': 'application/json'})
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def media_request(settings, suffix='', payload=None):
    """Use Typefully's documented v2 media route, separate from drafts."""
    url = f"https://api.typefully.com/v2/social-sets/{settings['socialSetId']}/media{suffix}"
    req = Request(url, data=json.dumps(payload).encode() if payload else None,
                  headers={'Authorization': 'Bearer ' + settings['apiKey'],
                           'Content-Type': 'application/json'})
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def fetch_media(url):
    """Fetch only a bounded HTTPS image that is already public on Kook'n."""
    if not isinstance(url, str) or not url.startswith('https://'):
        raise ValueError('Typefully media must use a public HTTPS card')
    req = Request(url, headers={'User-Agent': 'KooknResearch/1.0'})
    with urlopen(req, timeout=15) as response:
        body = response.read(10 * 1024 * 1024 + 1)
    if len(body) > 10 * 1024 * 1024:
        raise ValueError('Typefully card exceeds the 10 MB safety ceiling')
    if not body.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Typefully backup card is not a PNG')
    return body


def upload_media(settings, url):
    """Allocate and upload one image; a duplicate media object is harmless."""
    name = Path(urlparse(url).path).name or 'kookn-card.png'
    if not name.lower().endswith('.png'):
        name += '.png'
    allocated = media_request(settings, '/upload', {'file_name': name})
    media_id = allocated.get('media_id') or allocated.get('id')
    upload_url = allocated.get('upload_url')
    if not media_id or not isinstance(upload_url, str) or not upload_url.startswith('https://'):
        raise ValueError('Typefully returned no usable media upload')
    # Typefully's signed upload explicitly requires raw bytes and no headers.
    with urlopen(Request(upload_url, data=fetch_media(url), method='PUT'), timeout=20):
        pass
    return media_id


def confirm_attended_sent(entry, *, observed_text, link, sent_at, now,
                          evidence='X Composer UI'):
    """Reconcile one owned attended fallback with an actual observed X post.

    The attended browser is a last-resort transport when the free schedulers
    cannot upload the required card.  Reserving the post still happens before
    the browser opens; this function only turns that existing ownership record
    into a Sent receipt after the exact caption and public X URL are visible.
    Unknown clicks remain owned and therefore duplicate-protected.
    """
    attempt = entry.get('typefullyDelivery') or {}
    if not attempt.get('at') or entry.get('sentAt'):
        raise ValueError('Not an unresolved attended X reservation')
    if x_post.text_hash(observed_text) != entry.get('textHash'):
        raise ValueError('Observed caption does not match the checked release')
    if not re.fullmatch(r'https://(?:x|twitter)\.com/keenkooks/status/\d+', link, re.I):
        raise ValueError('Missing actual Kookn X publication link')
    at = gates.when(sent_at)
    reserved = gates.when(attempt['at'])
    if not reserved <= at <= now or now - at > timedelta(days=1):
        raise ValueError('Invalid actual publication time')
    entry.update(sentAt=gates.stamp(at), link=link,
                 tweetId=link.rsplit('/', 1)[-1])
    attempt.update(state='sent', verifiedAt=gates.stamp(now), evidence=evidence)
    return entry


def deliver(entry, book, settings, now, save, *, text=None, expires=None, media_url=None):
    """Persist ownership before sending. An unknown response requires reconciliation."""
    text = text or entry.get('queuedText')
    attempt = entry.get('typefullyDelivery')
    if not attempt:
        if not text or any(entry.get(k) for k in (
                'sentAt', 'bufferPostId', 'bufferAttemptAt', 'webDelivery',
                'error', 'cancelledAt', 'deletedAt')):
            return False
        if expires is None or expires <= now + timedelta(minutes=2):
            return False
        active = [e['typefullyDelivery'] for e in book['posts'] if e.get('typefullyDelivery')]
        if sum(gates.when(a['at']) > now - timedelta(days=31) for a in active) >= 10:
            return False
        attempt = entry['typefullyDelivery'] = {'at': gates.stamp(now)}
        save(book)
    if media_url and not attempt.get('draftId') and not attempt.get('mediaId'):
        try:
            attempt['mediaId'] = upload_media(settings, media_url)
            attempt['mediaUrl'] = media_url
            save(book)
        except (OSError, URLError, ValueError):
            # The hosted card may still be deploying.  Keep the owned post
            # attempt and retry the image later; never fall back to text-only.
            return False
    if attempt.get('mediaId') and not attempt.get('mediaReadyAt'):
        try:
            status = media_request(settings, f"/{attempt['mediaId']}")
        except (OSError, URLError, ValueError):
            return False
        if status.get('status') == 'failed':
            attempt['mediaError'] = 'processing failed'
            save(book)
            return False
        if status.get('status') != 'ready':
            return False
        attempt['mediaReadyAt'] = gates.stamp(now)
        save(book)
    if not attempt.get('draftId'):
        if not text:
            return False
        if attempt.get('draftAttemptAt'):
            # An unknown create response may have published.  Reconcile the
            # original attempt instead of risking a second X post.
            return False
        attempt['draftAttemptAt'] = gates.stamp(now)
        save(book)
        post = {'text': text}
        if attempt.get('mediaId'):
            post['media_ids'] = [attempt['mediaId']]
        result = request(settings, payload={
            'draft_title': entry['id'],
            'platforms': {'x': {'enabled': True, 'posts': [post]}},
            'publish_at': 'now',
        })
        if type(result.get('id')) is not int:
            return False
        attempt['draftId'] = result['id']
        save(book)
    else:
        result = request(settings, f"/{attempt['draftId']}")
    link = result.get('x_published_url') or ''
    sent = result.get('x_post_published_at')
    if result.get('status') != 'published' or not sent or not re.fullmatch(
            r'https://(?:x|twitter)\.com/keenkooks/status/\d+', link, re.I):
        return False
    entry.update(sentAt=gates.stamp(gates.when(sent)), link=link, tweetId=link.rsplit('/', 1)[-1])
    save(book)
    return True
