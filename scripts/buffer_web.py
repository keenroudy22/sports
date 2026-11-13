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
import post_windows
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
    individual_final = guid.startswith(('cashed:', 'burnt:'))
    kind = 'cashed' if individual_final else 'receipt'
    plans = bp.plan(first, latest, games, now, log_book, log=lambda *_: None,
                    results_only=individual_final)
    chosen = next((p for p in plans if p[0] == guid and p[1] == kind), None)
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
    if individual_final:
        quote_id = value.get('metadata', {}).get('twitter', {}).get('retweet', {}).get('id')
        if not quote_id or not image:
            raise WebHold('Individual Final requires the original X quote and result card')
        entry.update(kind='buffer:cashed', quoteTweetId=quote_id, quoteSourceId=bp.quote_source_id(guid))
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


def reserve_cbb_pick(guid, log_book, now, *, opener=None, validate_only=False):
    """Attended recovery for an admitted, delivered CBB pick; no API call."""
    import cbb_picks, social_style
    if bp.rate_backoff(now):
        raise WebHold('Provider backoff active; do not route around it')
    entry=next((e for e in log_book.get('posts',[]) if e.get('id')==guid),None)
    if (not entry or entry.get('kind')!='buffer:cbb-pick' or not entry.get('cbbPick')
            or (entry.get('discord') or {}).get('state')!='sent'
            or any(entry.get(k) for k in ('bufferPostId','sentAt','webDelivery','typefullyDelivery','bufferAttemptAt','error','cancelledAt','deletedAt'))):
        raise WebHold('Requires one public CBB play with no prior or ambiguous X attempt')
    play=next((p for p in cbb_picks.public_rows() if p['id']==guid),None)
    if not play or not cbb_picks.current_match(play,now):
        raise WebHold('Current CBB quote/review did not clear')
    text=cbb_picks.caption(play)
    if x_post.text_hash(text)!=entry.get('textHash') or x_post.x_style(text) or social_style.issues(text) or x_post.tweet_length(text)>x_post.LIMIT:
        raise WebHold('CBB caption differs from the original public release or fails style')
    image=bp.live_card_url(guid.lower(),opener)
    if not image or not bp.ticket_art_live(image) or not bp.plain_art_live(image):
        raise WebHold('CBB original branded card is not verified live')
    # Replacing this play's unsent intent consumes no second queue slot.
    other_posts=dict(log_book,posts=[e for e in log_book.get('posts',[]) if e is not entry])
    due=bp.free_slot(post_windows.play_due(now,now),bp.taken(other_posts,now))
    if due>=min(gates.when(play['kickoff'])-timedelta(minutes=15),gates.when(play['quote']['checkedAt'])+timedelta(hours=1)):
        raise WebHold('No current reviewed CBB release window')
    if bp.day_count(other_posts,now.astimezone(gates.EASTERN).date())>=bp.MAX_PER_DAY:
        raise WebHold('Daily social cap reached')
    if validate_only:
        return entry
    entry.update(dueAt=gates.stamp(due),queuedText=text)
    entry['webDelivery']=dict(state='reserved',reservedAt=gates.stamp(now),reviewedAt=gates.stamp(now),image=image,
                               evidence='CBB original ledger, current source/quote, caption and hosted-card checks')
    return entry


def reserve_nba_pick(guid, log_book, now, *, opener=None, validate_only=False):
    """Attended handoff for an admitted NBA pick already delivered to Discord.

    Reuse the actual NBA planner with capture disabled and its final-send
    evidence checks. This never admits a play, calls an odds/API endpoint or
    marks a reservation as sent. Caller holds the ordinary desk writer lock.
    """
    import nba_trial_runtime as nba, social_style, social_voice
    if bp.rate_backoff(now):
        raise WebHold('Provider backoff active; do not route around it')
    entry=next((e for e in log_book.get('posts',[]) if e.get('id')==guid),None)
    if (not entry or entry.get('kind')!='buffer:nba-trial' or entry.get('nbaPick') is not True
            or entry.get('nbaDiscordOnly') is not True
            or (entry.get('discord') or {}).get('state')!='sent'
            or any(entry.get(k) for k in ('bufferPostId','sentAt','webDelivery','typefullyDelivery','bufferAttemptAt','error','cancelledAt','deletedAt'))):
        raise WebHold('Requires one public NBA play with no prior or ambiguous X attempt')
    play=next((p for p in nba.public_rows() if p['id']==guid),None)
    if not play or play.get('result') or not nba.review_ready(now) or not nba.current_match(play,now):
        raise WebHold('Current NBA evidence/price/availability did not clear')
    plans=nba.social_plans(now,log_book,refresh=False)
    plan=next((p for p in plans if p[0]==guid and p[1]=='nba-trial'),None)
    if not plan:
        raise WebHold('No current NBA release plan')
    text=bp.x_ticket_copy(social_voice.finish(plan[2]),'play',guid)
    if (x_post.text_hash(text)!=entry.get('textHash') or x_post.x_style(text)
            or social_style.issues(text) or x_post.tweet_length(text)>x_post.LIMIT
            or '$' in text or re.search(r'\bbet\s*id\b',text,re.I)):
        raise WebHold('NBA caption differs from the original public release or fails style')
    image=bp.live_card_url(plan[4],opener)
    if not image or not bp.ticket_art_live(image) or not bp.plain_art_live(image):
        raise WebHold('NBA original branded card is not verified live')
    others=dict(log_book,posts=[e for e in log_book.get('posts',[]) if e is not entry])
    due=plan[3]
    web_slots=sum(1 for e in others['posts'] if not e.get('bufferPostId')
                  and not any(e.get(k) for k in ('sentAt','cancelledAt','deletedAt','error'))
                  and (e.get('webDelivery') or {}).get('state') in ('reserved','scheduled'))
    expiry = min(gates.when(play['kickoff'])-timedelta(minutes=15),
                 # Typefully validation is an immediate attended backup after
                 # a fresh sourced recheck; its current quote clock is enforced
                 # by nba.current_match rather than the immutable original.
                 (gates.when(play['kickoff']) if validate_only
                  else gates.when(play['retrievedAt'])+timedelta(hours=2)))
    release_time = now if validate_only else due
    if ((not validate_only and due<=now) or release_time>=expiry
            or bp.day_count(others,now.astimezone(gates.EASTERN).date())>=bp.MAX_PER_DAY
            or bp.pending_scheduled(others,now)+web_slots>=bp.BUFFER_NORMAL_LIMIT):
        raise WebHold('No current NBA release capacity or quote window')
    # Same append-only at-most-once intent used by the API publisher. An old
    # unknown create attempt cannot become a second attempt through the UI.
    if not validate_only and not nba.reserve_delivery(guid,now):
        raise WebHold('Existing or ambiguous NBA delivery intent')
    if validate_only:
        return entry
    entry.update(dueAt=gates.stamp(due),queuedText=text)
    entry['webDelivery']=dict(state='reserved',reservedAt=gates.stamp(now),reviewedAt=gates.stamp(now),
        image=image,evidence='NBA original ledger, frozen proof, current sources, caption and hosted-card checks')
    return entry
