"""Attended Buffer-web receipt handoff, not an unattended X browser publisher.

The caller holds the ordinary desk lock and saves the returned log before using
Buffer's normal composer. Unknown attempts remain duplicate-protected. No API
quota, journal or provider backoff is reset. Already-public plays require the
real release path's current review; this never admits a new play.
"""
import re
from datetime import timedelta

import buffer_post as bp
import gates
import x_post


class WebHold(ValueError):
    pass


class _Staged(Exception):
    def __init__(self, value):
        self.value = value


def reserve_receipt(guid, first, latest, games, log_book, now, *, opener=None):
    """Recompute the normal plan and its caption/art gates, then reserve once.

    Only an actual Buffer UI observation may complete this reservation. The
    reservation itself is neither Buffer acceptance nor X publication.
    """
    if bp.rate_backoff(now):
        raise WebHold('Provider backoff active; do not route around it')
    if any(p.get('id') == guid for p in log_book.get('posts', [])):
        raise WebHold('Existing or ambiguous attempt; reconcile instead of retrying')
    plans = bp.plan(first, latest, games, now, log_book, log=lambda *_: None)
    chosen = next((p for p in plans if p[0] == guid and p[1] == 'receipt'), None)
    if chosen is None:
        raise WebHold('No current qualifying receipt in the normal plan')
    def stage(url, body, headers):
        if body['query'] != bp.CREATE:
            raise WebHold('Unexpected API operation')
        raise _Staged(body['variables']['input'])
    try:
        bp.schedule([chosen], 'attended-web', log_book, now, key='not-a-credential',
                    send=stage, opener=opener, log=lambda *_: None)
    except _Staged as staged:
        value = staged.value
    else:
        raise WebHold('Receipt failed normal caption, art or queue checks')
    text = value['text']
    if '$' in text or re.search(r'\bbet\s*id\b', text, re.I):
        raise WebHold('Public receipt must contain units, not personal money or bet IDs')
    image = ((value.get('assets') or [{}])[0].get('image') or {}).get('url')
    entry = dict(id=guid, kind='buffer:receipt', postedAt=gates.stamp(now),
                 dueAt=value['dueAt'], queuedText=text, textHash=x_post.text_hash(text),
                 card=bool(image), webDelivery=dict(state='reserved',
                 reservedAt=gates.stamp(now), image=image))
    log_book.setdefault('posts', []).append(entry)
    return entry


def confirm_scheduled(entry, *, observed_text, due_at, now):
    """Record the exact matching queued item observed in Buffer, not an X send."""
    web = entry.get('webDelivery') or {}
    if web.get('state') != 'reserved' or entry.get('sentAt'):
        raise WebHold('Not an unresolved attended-web reservation')
    if x_post.text_hash(observed_text) != entry.get('textHash'):
        raise WebHold('Observed caption does not match the checked receipt')
    if gates.when(due_at) != gates.when(entry['dueAt']) or gates.when(due_at) <= now:
        raise WebHold('Observed scheduled time does not match the checked plan')
    web.update(state='scheduled', verifiedAt=gates.stamp(now), evidence='Buffer Queue UI')


def reserve_public_play(guid, log_book, now, *, reviewer=None):
    """Reserve a checked already-public play for attended Buffer UI delivery.

    Caller holds the run lock. The real release validator rechecks current
    price/news/exposure/art/caption/tests before this reservation; no live gate
    or request cap is bypassed. Never supplies a fabricated Buffer post ID.
    """
    if bp.rate_backoff(now):
        raise WebHold('Provider backoff active; do not route around it')
    entry = next((p for p in log_book.get('posts', []) if p.get('id') == guid), None)
    if (not entry or entry.get('kind') != 'buffer:play'
            or (entry.get('discord') or {}).get('state') != 'sent'
            or entry.get('bufferPostId') or entry.get('sentAt') or entry.get('webDelivery')
            or any(entry.get(k) for k in ('error', 'cancelledAt', 'deletedAt'))):
        raise WebHold('Requires one public play with no prior or ambiguous X attempt')
    if reviewer is None:
        import run
        reviewer = lambda: run.release_private(now, only={guid}, review_only=True)
    checked = reviewer()
    if len(checked) != 1 or checked[0].get('id') != guid:
        raise WebHold('Current public-play release checks did not clear')
    row = checked[0]
    if gates.when(row['reviewedAt']) != now or gates.when(row['dueAt']) <= now:
        raise WebHold('Current reviewed release window unavailable')
    if x_post.text_hash(row['text']) != entry.get('textHash'):
        raise WebHold('Reviewed caption differs from the original public release')
    if '$' in row['text'] or re.search(r'\bbet\s*id\b', row['text'], re.I):
        raise WebHold('Public play must contain units, not personal money or bet IDs')
    entry.update(dueAt=row['dueAt'], queuedText=row['text'])
    entry['webDelivery'] = dict(state='reserved', reservedAt=gates.stamp(now),
        reviewedAt=row['reviewedAt'], image=row['card'], evidence='normal public-play release review')
    return entry


def confirm_sent(entry, *, observed_text, link, sent_at, now):
    """Record a matching Buffer Sent observation; never infer success from a click.

    An unknown/failed click leaves the reservation intact and blocks a duplicate.
    The operator supplies the exact observed post, its link and actual timestamp.
    """
    web = entry.get('webDelivery') or {}
    if web.get('state') not in ('reserved', 'scheduled') or entry.get('sentAt'):
        raise WebHold('Not an unresolved attended-web reservation')
    if x_post.text_hash(observed_text) != entry.get('textHash'):
        raise WebHold('Observed caption does not match the checked receipt')
    if not re.fullmatch(r'https://(?:x|twitter)\.com/(?:[A-Za-z0-9_]+|i/web)/status/\d+', link):
        raise WebHold('Missing actual X publication link')
    at = gates.when(sent_at)
    if not gates.when(web['reservedAt']) <= at <= now or now-at > timedelta(days=1):
        raise WebHold('Invalid actual publication time')
    entry.update(sentAt=gates.stamp(at), link=link, tweetId=link.rsplit('/', 1)[-1])
    web.update(state='sent', verifiedAt=gates.stamp(now), evidence='Buffer Sent UI')
