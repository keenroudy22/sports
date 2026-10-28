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
from social_copy import without_playbook, with_age_notice, decimal_projection


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


def research_webhook(env=None):
    """Dedicated research destination; never fall back to the official plays feed."""
    return ((env if env is not None else os.environ).get('DISCORD_RESEARCH_WEBHOOK_URL') or '').strip()


def community_type(guid, items=None):
    """Separate an exact registered ticket from an explicitly verified result.

    The community namespace alone says nothing about whether a wager has settled.
    Unknown announcements must not default into the wins feed.
    """
    item = (items or {}).get(guid) or {}
    if item.get('personalTicket') is True:
        return 'ticket'
    if item.get('communityResult') is True and item.get('settledAt') and (
            item.get('result') == 'win' or item.get('result') == 'loss' and item.get('badBeat') is True):
        return 'result'
    try:
        tickets = json.loads((Path(__file__).resolve().parents[1] / 'data/community.json').read_text())
    except (OSError, ValueError):
        return None
    if any(t.get('id') == guid and t.get('personalTicket') is True for t in tickets.get('tickets', [])):
        return 'ticket'
    return None


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


def send_message(url, text, image_url=None, send=http_send, username="Kook'n Sports", fetch=download_image,
                 return_receipt=False):
    """Send one webhook message without ever putting the secret URL in an error or log.

    Cards are uploaded to Discord so an old post cannot break when the generated site card rolls out of the
    current build. If the card cannot be downloaded, the external embed remains a safe delivery fallback.
    """
    import x_post
    # The owner-approved live pilot has one exact cheering exception.
    final_text = with_age_notice(without_playbook(text))
    import social_style
    if social_style.privacy_issues(final_text):
        raise DiscordError('Private dollar amount or bet identifier in social caption')
    if decimal_projection(final_text):
        raise DiscordError('Decimal forecast in social caption; revise without changing the wager')
    if len(final_text) > 2000:
        raise DiscordError('complete caption including age notice exceeds Discord limit')
    checked = str(final_text or '').replace('Come on!', 'Come on.')
    if x_post.x_style(checked):
        raise DiscordError('outgoing copy fails the public voice check')
    body = {'username': username, 'avatar_url': 'https://keenroudy.com/sports/kookn-chef.png?v=20261007',
            'content': final_text}
    headers = {'Content-Type': 'application/json', 'User-Agent': 'KooknSports/1.0'}
    if image_url:
        # Registered raw owner slips must not bypass privacy through a delayed mirror.
        owner_slip = "/img/tickets/" in str(image_url)
        try:
            image = fetch(image_url)
        except DiscordError:
            if owner_slip:
                raise DiscordError('owner slip unavailable for privacy verification; original held')
            body['embeds'] = [{'image': {'url': image_url}}]
        else:
            if owner_slip and not (image[0].startswith(b'\x89PNG\r\n\x1a\n') and social_style.MARKER in image[0][:256]):
                raise DiscordError('owner slip needs a privacy-checked native graphic; original held')
            body['attachments'] = [{'id': 0, 'filename': image[2]}]
            body, content_type = multipart(body, image)
            headers['Content-Type'] = content_type
    endpoint = url
    if return_receipt and send is http_send:
        separator = '&' if '?' in endpoint else '?'
        endpoint = f'{endpoint}{separator}wait=true'
    status, raw = send(endpoint, body, headers)
    if status not in (200, 204):
        detail = raw.decode('utf-8', 'replace')[:240] if isinstance(raw, bytes) else str(raw)[:240]
        raise DiscordError(f'Discord returned HTTP {status}: {detail}')
    if not return_receipt:
        return None
    try:
        receipt = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        receipt = {}
    attachments = receipt.get('attachments') or [] if isinstance(receipt, dict) else []
    return {'id': receipt.get('id') if isinstance(receipt, dict) else None,
            'image': attachments[0].get('url') if attachments and isinstance(attachments[0], dict) else None}


ARB_QUIET = timedelta(hours=6)
RESULT_QUIET_START = 60       # 1:00 AM Eastern
RESULT_QUIET_END = 8 * 60     # late finals join the morning delivery after 8:00
RESULT_UPDATE_FRESH = timedelta(hours=12)


def queue_results(log_book, first, latest, games, now):
    """Attach one factual settled update to every released official play.

    The original play and its result stay together in Plays & Results. This is
    independent of the later X receipt, so a delayed card cannot hide a grade.
    """
    local = now.astimezone(gates.EASTERN)
    minute = local.hour * 60 + local.minute
    if RESULT_QUIET_START <= minute < RESULT_QUIET_END:
        return 0
    import receipts
    import result_display
    queued = 0
    for entry in log_book.get('posts', []):
        key = entry.get('id')
        mirror = entry.get('discord') or {}
        if entry.get('kind') != 'buffer:play' or mirror.get('state') != 'sent' or key not in first:
            continue
        pick = dict(first[key], **latest.get(key, {}))
        result = str(pick.get('result') or '').lower()
        if result not in ('win', 'loss', 'push', 'void') or not pick.get('settledAt') or mirror.get('result'):
            continue
        try:
            settled_at = gates.when(pick['settledAt'])
        except (TypeError, ValueError):
            continue
        if not now - RESULT_UPDATE_FRESH < settled_at <= now:
            continue
        overtime = result_display.overtime_detail(pick)
        mark = '😩' if overtime else {'win': '✅', 'loss': '❌', 'push': '➖', 'void': '➖'}[result]
        word = 'OT BAD BEAT' if overtime else {'win': 'HIT', 'loss': 'MISS', 'push': 'PUSH', 'void': 'VOID'}[result]
        detail = overtime or result_display.detail(pick) or result_display.clean_actual(pick)
        title = receipts.label(pick, games)
        text = f'{mark} FINAL · {word}: {title}' + (f'\n{detail}' if detail else '')
        mirror['result'] = {'state': 'pending', 'text': text, 'settledAt': pick['settledAt']}
        entry['discord'] = mirror
        queued += 1
    return queued


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


def mirror_sent(log_book, now, url=None, wins_url=None, research_url=None,
                send=http_send, fetch=download_image, log=print):
    """Deliver each Discord payload once.

    Confirmed plays carry ``readyAt`` and go to Discord before X. House, news and engagement posts keep the old
    downstream rule and wait for Buffer to confirm X. Return only newly changed failures, so ntfy does not repeat.
    """
    url = url if url is not None else webhook()
    wins_url = wins_url if wins_url is not None else wins_webhook()
    research_url = research_url if research_url is not None else research_webhook()
    if not url and not wins_url and not research_url:
        return []
    failed = []
    for entry in log_book.get('posts', []):
        mirror = entry.get('discord') or {}
        kind = entry.get('kind')
        destination = mirror.get('destination')
        if kind == 'buffer:community' and mirror.get('state') == 'pending':
            phase = community_type(entry.get('id')) or mirror.get('communityType')
            # Recheck legacy pending payloads at send time as well. Already-sent
            # receipts remain historical; an operator correction preserves them.
            destination = {'ticket': 'plays', 'result': 'wins'}.get(phase)
            if destination:
                mirror['destination'] = destination
                mirror['communityType'] = phase
        import daily_straight_card
        combined = daily_straight_card.discord_eligible(entry) and destination == 'plays'
        allowed = (combined or (kind == 'buffer:play' and destination != 'wins')
                   or (kind == 'buffer:cashed' and str(entry.get('id') or '').startswith(('cashed:', 'burnt:'))
                       and destination != 'wins')
                   or (kind == 'buffer:community' and destination in ('plays', 'wins')
                       and mirror.get('communityType') in ('ticket', 'result'))
                   or (kind == 'buffer:research' and destination == 'research'))
        if not allowed:
            # Older queue entries may still carry a pending mirror payload.
            # The latest plays-only rule wins at send time too.
            if mirror.get('state') == 'pending':
                mirror['state'] = 'skipped'
                mirror['reason'] = 'not an approved Discord category'
                entry['discord'] = mirror
            continue
        ready = mirror.get('readyAt') and gates.when(mirror['readyAt']) <= now
        if mirror.get('state') != 'pending' or not (ready or entry.get('sentAt')) \
                or entry.get('cancelledAt') or entry.get('deletedAt'):
            continue
        if kind == 'buffer:research' and destination == 'research':
            # A sent X post is history, but its delayed Discord copy is still a
            # new publication. Apply current evidence rules before that send.
            import buffer_post
            issues = buffer_post.queued_relevance_issues(entry, now)
            if issues:
                mirror.update(state='skipped', checkedAt=gates.stamp(now),
                              reason='Current research policy: ' + '; '.join(issues))
                entry['discord'] = mirror
                log(f"discord: {entry['id']} not mirrored: {mirror['reason']}")
                continue
        target = (wins_url if destination == 'wins' else
                  research_url if destination == 'research' else url)
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
            text = mirror.get('text') or ''
            if destination == 'research':
                link = str(entry.get('link') or '').strip()
                suffix = 'RESEARCH · NOT A BEST BET'
                text = f'{text.rstrip()}\n\n{suffix}' + (f'\n{link}' if link else '')
            send_message(target, text, mirror.get('image'), send=send, fetch=fetch)
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
        if entry.get('kind') not in ('buffer:play', 'buffer:community') or mirror.get('state') != 'sent':
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
    for entry in log_book.get('posts', []):
        mirror = entry.get('discord') or {}
        result = mirror.get('result') or {}
        if result.get('state') != 'pending' or entry.get('kind') != 'buffer:play' or mirror.get('state') != 'sent':
            continue
        if not url:
            continue
        try:
            send_message(url, result.get('text') or '', send=send)
        except DiscordError as error:
            message = str(error)
            changed = result.get('error') != message
            result['error'] = message
            result['lastAttemptAt'] = gates.stamp(now)
            result['attempts'] = int(result.get('attempts') or 0) + 1
            mirror['result'] = result
            entry['discord'] = mirror
            log(f"discord: {entry['id']} result update not sent: {message}")
            if changed:
                failed.append({'id': entry['id'], 'error': message})
            continue
        result['state'] = 'sent'
        result['sentAt'] = gates.stamp(now)
        result.pop('error', None)
        result.pop('lastAttemptAt', None)
        mirror['result'] = result
        entry['discord'] = mirror
        log(f"discord: {entry['id']} result update sent")
    return failed
