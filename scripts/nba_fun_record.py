"""Append-only record of delivered, reviewed NBA prop tickets."""
import re
from pathlib import Path

import boxscores
import gates
import prop_ticket_release as release
import prop_ticket_review as review

PATH = Path('data/nba-fun/tickets.jsonl')
ORIGINAL_FIELDS = ('id', 'league', 'kind', 'family', 'title', 'selectionMethod',
                   'parlayType', 'parlayStyle', 'book', 'odds', 'riskUnits',
                   'gameIds', 'firstKickoff', 'quotedAt', 'expiresAt',
                   'propTicketFingerprint', 'publishedAt')
RESULT_FIELDS = ('result', 'actual', 'settledAt', 'resultSource', 'units',
                 'settledOdds', 'settlementLegResults', 'settlementLegActuals',
                 'settlementBasis', 'settlementReason', 'settlementReviewSources',
                 'injuryPlayers')


def delivery(ticket, posts, now):
    """Require an actual pregame send, even if a later X attempt was cancelled."""
    start = gates.when(ticket['firstKickoff'])
    quote = gates.when(ticket['quotedAt'])
    discord_at, x_at, url = None, None, None
    for post in posts:
        if post.get('id') != ticket['id'] or post.get('kind') != 'buffer:play':
            continue
        mirror = post.get('discord') or {}
        if (mirror.get('state') == 'sent' and mirror.get('sentAt')
                and re.fullmatch(r'\d{15,22}', str(mirror.get('messageId') or ''))
                and mirror.get('attachmentState') == 'attached' and mirror.get('attachmentReceipt')):
            at = gates.when(mirror['sentAt'])
            if quote <= at < start and at <= now and (discord_at is None or at < discord_at):
                discord_at = at
        link = post.get('link') or ''
        match = re.fullmatch(r'https://(?:x|twitter)\.com/(?:keenkooks|1753110091912413184)/status/(\d{15,22})/?', link)
        if (post.get('sentAt') and match and match[1] == str(post.get('tweetId'))
                and not post.get('cancelledAt') and not post.get('deletedAt')):
            at = gates.when(post['sentAt'])
            if quote <= at < start and at <= now and (x_at is None or at < x_at):
                x_at, url = at, link
    if discord_at or x_at:
        return {'discordAt': gates.stamp(discord_at) if discord_at else None,
                'xAt': gates.stamp(x_at) if x_at else None, 'originalX': url}
    return None


def rows(root, now):
    """Project original and latest as-of result without rewriting the original."""
    originals, grades = {}, {}
    for entry in boxscores.read_store(Path(root) / PATH):
        key = entry['id']
        if entry['type'] == 'publish':
            if key in originals:
                raise ValueError(f'Duplicate NBA fun ticket: {key}')
            originals[key] = entry
        elif entry['type'] == 'settle' and key in originals:
            at = gates.when(entry['settledAt'])
            if at <= now and (key not in grades or at > gates.when(grades[key]['settledAt'])):
                grades[key] = entry
        else:
            raise ValueError(f'NBA fun revision without an original: {key}')
    return {key: {**{k: v for k, v in row.items() if k != 'type'},
                  **{k: v for k, v in grades.get(key, {}).items() if k not in ('id', 'type')},
                  'status': 'settled' if key in grades else 'active', 'kickoff': row['firstKickoff']}
            for key, row in originals.items() if gates.when(row['publishedAt']) <= now}


def public_rows(root, posts, now):
    import receipts
    result = []
    for ticket in rows(root, now).values():
        sent = delivery(ticket, posts, now)
        if not sent:
            continue
        kickoff = gates.when(ticket['kickoff']).astimezone(gates.EASTERN)
        card_key = receipts.result_card_key(ticket) if ticket.get('result') else ticket['id']
        result.append(dict(ticket, delivery=sent, posted=True,
                           gameId=ticket['gameIds'][0],
                           season=kickoff.year + (kickoff.month >= 10), seasonType=2,
                           card='data/cards/' + card_key + '.png'))
    return result


def original_row(pick):
    """Validate and project the exact public fields before an external send."""
    if (pick.get('league') != 'NBA' or pick.get('family') != 'NBA-alts'
            or pick.get('selectionMethod') != release.METHOD or pick.get('riskUnits') != .25
            or pick.get('kind') != 'parlays' or pick.get('parlayType') != 'longshot'
            or not review.price(pick.get('odds')) or pick.get('book') not in ('DraftKings', 'FanDuel')
            or review.fingerprint(pick) != pick.get('propTicketFingerprint')):
        raise ValueError('Reviewed NBA alternate ticket with exact original terms required')
    legs = pick['legs']
    if (not legs or pick['gameIds'] != list(dict.fromkeys(leg['gameId'] for leg in legs))
            or gates.when(pick['firstKickoff']) != min(gates.when(leg['kickoff']) for leg in legs)
            or any(leg.get('alternate') is not True or leg.get('period') != 'full_game'
                   or leg.get('market') not in review.STATS['NBA'] for leg in legs)):
        raise ValueError('NBA alternate ticket requires its original full-game fixtures and markets')
    row = {k: pick[k] for k in ORIGINAL_FIELDS}
    row.update(type='publish', legs=[{k: leg[k] for k in (*release.PUBLIC_LEG_FIELDS, 'id', 'title')}
                                    for leg in legs])
    return row


def publish(root, pick, posts, now):
    """Save the exact original after the release worker records confirmation."""
    row = original_row(pick)
    sent = delivery(pick, posts, now)
    if not sent or pick.get('publishedAt') != min(at for at in (sent['discordAt'], sent['xAt']) if at):
        raise ValueError('Actual pregame NBA ticket delivery receipt required')
    target = Path(root) / PATH
    earlier = next((r for r in boxscores.read_store(target) if r['id'] == row['id'] and r['type'] == 'publish'), None)
    if earlier == row:
        return False
    if earlier:
        raise ValueError('Published NBA ticket terms are immutable')
    boxscores.append(target, [row])
    return True


def settle(root, key, posts, packet, now):
    """Use the exact private ticket review to append an initial grade or correction."""
    original = rows(root, now).get(key)
    if not original or not delivery(original, posts, now):
        raise ValueError('NBA ticket settlement requires a delivered original')
    revised, held = release.settlement_revision(original, now, packet=packet)
    if held:
        raise ValueError(held)
    row = {k: revised[k] for k in RESULT_FIELDS if k in revised}
    if original.get('settledAt'):
        if all(original.get(k) == row.get(k) for k in RESULT_FIELDS if k != 'settledAt'):
            return False
        if gates.when(original['settledAt']) >= gates.when(row['settledAt']):
            raise ValueError('NBA ticket correction must be later than the prior grade')
        row['correctedAt'] = row['settledAt']
    boxscores.append(Path(root) / PATH, [dict(row, type='settle', id=key)])
    return True
