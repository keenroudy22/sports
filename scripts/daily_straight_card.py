"""One prospective summary of already delivered official straights, never a new admission.

The accepted Buffer log freezes membership and original terms. The existing daily
Final links back only after X confirms this summary. No network calls or records
are written here; the ordinary publishers retain their budgets and send guards.
"""
import copy
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone

import gates
import pick_card
import record_scope
import x_post

EFFECTIVE = datetime(2026, 10, 28, 11, 45, tzinfo=timezone.utc)
PREFIX = 'receipt:card:'
TERMS = ('id', 'title', 'league', 'season', 'seasonType', 'gameIds', 'kickoff',
         'publishedAt', 'marketType', 'market', 'direction', 'line', 'athleteId',
         'player', 'book', 'odds', 'riskUnits', 'lane')
RESULT_FIELDS = ('result', 'settledAt', 'actual', 'actualValue', 'earlyExit',
                 'injuryPlayers', 'injuryReview', 'settlementSource')


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def key(day):
    return PREFIX + str(day)


def accepted(log_book, day):
    """A single accepted snapshot is permanent, including cancelled/unknown drafts."""
    return next((p for p in log_book.get('posts', []) if p.get('id') == key(day)), None)


def terms(pick):
    if (not number(pick.get('odds')) or not number(pick.get('riskUnits'))
            or pick['riskUnits'] <= 0 or abs(pick['odds']) < 100
            or not pick.get('book') or not pick.get('title')):
        return None
    return copy.deepcopy({field: pick[field] for field in TERMS if field in pick})


def signature(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


def row_label(pick, games):
    import receipts
    return receipts.label(pick, games)


def price(pick):
    return f"{pick['odds']:+g} {x_post.public_book(pick['book'])} · {pick['riskUnits']:g}u"


def proposal(first, latest, games, log_book, now):
    """Wait for each active official straight's actual X receipt, before first kickoff."""
    import receipts
    day = gates.eastern_date(now)
    if now < EFFECTIVE or accepted(log_book, day):
        return None
    rows, starts = [], []
    for ident, original in sorted(first.items()):
        merged = dict(original, **latest.get(ident, {}))
        if (receipts.game_day(original, games) != day or original.get('historicalImport')
                or pick_card.play_kind(original) not in ('player', 'team')
                or not record_scope.is_headline(dict(original, posted=True))):
            continue
        if merged.get('result') or merged.get('entryNote') or (merged.get('status') or 'active') != 'active':
            continue
        start = min((gates.when(games[g]['kickoff']) for g in original.get('gameIds') or [] if g in games), default=None)
        # Never omit an active held/unreleased official from the day's summary.
        delivery = next((p for p in log_book.get('posts', []) if p.get('id') == ident
                         and p.get('kind') == 'buffer:play' and p.get('sentAt')
                         and not p.get('cancelledAt') and not p.get('deletedAt')), None)
        if (not start or start <= now or not delivery
                or not record_scope.instant(delivery['sentAt'])
                or record_scope.instant(delivery['sentAt']) > now):
            return None
        frozen = terms(original)
        if not frozen:
            return None
        frozen['kickoff'] = gates.stamp(start)
        rows.append(frozen)
        starts.append(start)
    if not 2 <= len(rows) <= 10:
        return None
    fingerprint = signature(rows)
    heading = f"{day:%A}'s Best Bets: {len(rows)} straights."
    body = '\n'.join(f"{row_label(r, games)} ({price(r)})" for r in rows)
    tail = 'Copy the bet 👇 @Playbook\n\n21+ only'
    text = f'{heading}\n\n{body}\n\n{tail}'
    if x_post.tweet_length(text) > x_post.LIMIT:
        # Every exact row remains on the required image. Never truncate wager terms.
        text = f"{heading}\n\nMy posted prices and units are on the card.\n\n{tail}"
    due = now + timedelta(minutes=2)
    stale = min(starts) - timedelta(minutes=5)
    if due >= stale:
        return None
    return {'key': key(day), 'kind': 'receipt', 'card': f'straight-card-{day}-{fingerprint}',
            'text': text, 'due': due, 'stale': stale,
            'straightCard': {'version': 1, 'day': str(day), 'rows': rows, 'fingerprint': fingerprint}}


def history(first, latest, games, log_book, now):
    """Retain frozen accepted art; proposed art is generated before Buffer acceptance."""
    out = []
    for entry in log_book.get('posts', []):
        data = entry.get('straightCard') or {}
        rows = data.get('rows') or []
        if data.get('version') != 1 or not rows or signature(rows) != data.get('fingerprint'):
            continue
        try:
            day = datetime.fromisoformat(data['day']).date()
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= (gates.eastern_date(now) - day).days <= 8:
            continue
        out.append({'card': f"straight-card-{day}-{data['fingerprint']}", 'straightCard': data})
    pending = proposal(first, latest, games, log_book, now)
    if pending:
        out.append(pending)
    return out


def linked(log_book, day, latest):
    """Only actual X proof links a settled Final to frozen original terms."""
    entry = accepted(log_book, day) or {}
    data = entry.get('straightCard') or {}
    link = str(entry.get('link') or '')
    if (not entry.get('sentAt') or not re.fullmatch(r'https://(?:x|twitter)\.com/keenkooks/status/\d+', link)
            or data.get('version') != 1 or not data.get('rows')
            or signature(data['rows']) != data.get('fingerprint')):
        return None
    rows = []
    for frozen in data['rows']:
        result = latest.get(frozen['id'], {})
        if result.get('result') not in ('win', 'loss', 'push', 'void'):
            return None
        merged = dict(frozen, **{k: result[k] for k in RESULT_FIELDS if k in result}, posted=True)
        # Recompute from the frozen price/risk: later quote/stake/units cannot change this card.
        # Match run.lock_units and the public record's three-decimal settlement.
        # No latest quote/stake or unrelated saved-unit override enters this row.
        merged['units'] = x_post.units_for(merged) or 0.0
        merged['combinedOriginalTerms'] = True
        rows.append(merged)
    summary = x_post.summarize(rows)
    net = sum(x_post.units_for(r) or 0 for r in rows)
    detail = f"Card: {summary['win']}W/{summary['loss']}L/{summary['push']}P/{summary['void']}V · {net:+.2f}u"
    return {'rows': rows, 'link': link, 'text': detail + '\n' + link}


def link_final(receipt, log_book, latest, games):
    """Enhance the existing daily Final; never create a second result category."""
    if not receipt or not str(receipt.get('key', '')).startswith('receipt:day:'):
        return receipt
    day = receipt['key'].removeprefix('receipt:day:')
    proof = linked(log_book, day, latest)
    if not proof:
        return receipt
    import receipts
    result = dict(receipt)
    text = f"{receipt['text']}\n\n{proof['text']}\n21+ only"
    if x_post.tweet_length(text) > x_post.LIMIT:
        text = f"{day}: {receipt['title']}.\n\n{proof['text']}\nEvery result is on the card.\n21+ only"
    result.update(text=text, linkedStraightRows=proof['rows'], straightCardLink=proof['link'])
    return result


def discord_eligible(entry):
    """Narrowly authorize combined official cards and their linked daily Finals."""
    if entry.get('kind') != 'buffer:receipt':
        return False
    data = entry.get('straightCard') or {}
    if str(entry.get('id') or '') == key(data.get('day')) and data.get('version') == 1:
        return bool(data.get('rows')) and signature(data['rows']) == data.get('fingerprint')
    result = entry.get('straightCardResult') or {}
    return (entry.get('id') == 'receipt:day:' + str(result.get('day'))
            and result.get('version') == 1 and bool(result.get('pickIds'))
            and bool(re.fullmatch(r'https://(?:x|twitter)\.com/keenkooks/status/\d+', str(result.get('source') or ''))))
