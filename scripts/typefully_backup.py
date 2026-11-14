"""Duplicate-safe X backup for revalidated releases during a local Buffer cap.

Eligibility remains with the calling release path: reviewed football, NBA and
CBB straights may use the reserved straight/recap capacity, while only the
explicitly supported Climb and fun-ticket families may use ticket capacity.
"""
import json
import re
from datetime import timedelta
from urllib.request import Request, urlopen

import gates


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


def deliver(entry, book, settings, now, save, *, text=None, expires=None):
    """Persist ownership before sending. An unknown response requires reconciliation."""
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
        result = request(settings, payload={
            'draft_title': entry['id'],
            'platforms': {'x': {'enabled': True, 'posts': [{'text': text}]}},
            'publish_at': 'now',
        })
        if type(result.get('id')) is not int:
            return False
        attempt['draftId'] = result['id']
        save(book)
    elif attempt.get('draftId'):
        result = request(settings, f"/{attempt['draftId']}")
    else:
        return False
    link = result.get('x_published_url') or ''
    sent = result.get('x_post_published_at')
    if result.get('status') != 'published' or not sent or not re.fullmatch(
            r'https://(?:x|twitter)\.com/keenkooks/status/\d+', link, re.I):
        return False
    entry.update(sentAt=gates.stamp(gates.when(sent)), link=link, tweetId=link.rsplit('/', 1)[-1])
    save(book)
    return True
