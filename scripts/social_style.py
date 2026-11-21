"""Owner's prospective caption/art policy, including already queued private posts."""
import html
import re
import struct
import zlib
from datetime import datetime, timezone

VERSION = 'units-only-no-decimal-20261027'
PRIVACY_EFFECTIVE = datetime(2026, 10, 25, tzinfo=timezone.utc)
EFFECTIVE = datetime(2026, 10, 22, tzinfo=timezone.utc)
MARKER = b'KooknSocial\x00' + VERSION.encode()
CLIMB_MARKER = b'KooknClimb\x00full-rollover-dollars'


def active(now):
    return now >= EFFECTIVE


def marked_png(raw, *, challenge=()):
    return (raw.startswith(b'\x89PNG\r\n\x1a\n') and MARKER in raw
            and (not challenge or CLIMB_MARKER in raw))


def current_png(path, *, challenge=()):
    try:
        with path.open('rb') as source:
            raw = source.read(256)
        return marked_png(raw, challenge=challenge)
    except OSError:
        return False


def release_issues(text, path, *, challenge=()):
    found = issues(text, challenge=challenge)
    if not current_png(path, challenge=challenge):
        found.append('private house card lacks current source-render attestation')
    return found


def challenge_amounts(pick):
    """Public tracking balances from the full-rollover Climb ledger only."""
    info = pick.get('ladder') or {}
    if pick.get('parlayType') != 'ladder' or info.get('fullRollover') is not True:
        return ()
    from ticket_kit import money
    values = (info.get(key) for key in ('start', 'goal', 'stake', 'payout', 'nextStake', 'totalAfter'))
    return tuple(sorted({'$0', *(money(value) for value in values if type(value) in (int, float))}))


def privacy_issues(text, *, challenge=()):
    text = str(text)
    found = []
    if challenge:
        if re.search(r'(?<![\w.])\d+(?:\.\d+)?\s*u\b', text, re.I):
            found.append('full-rollover Climb must use its posted dollar balance')
        text = re.sub(r'\$\d[\d,]*(?:\.\d+)?',
                      lambda match: '' if match[0] in challenge else match[0], text)
    if re.search(r'[$＄]\s*\d|\b(?:USD|dollars?)\b', text, re.I):
        found.append('personal dollar amounts: use known units only')
    if re.search(r'\b(?:bet|wager|ticket)\s*(?:id|number|#)\s*[:#-]?\s*[A-Za-z0-9-]{4,}', str(text), re.I):
        found.append('private bet identifier')
    return found


def issues(text, graphic=False, *, challenge=()):
    if graphic and challenge:
        from check_svg import text_nodes
        text = '\n'.join(text_nodes(text))
    else:
        text = html.unescape(re.sub(r'<[^>]+>', ' ', str(text or '')))
    found = privacy_issues(text, challenge=challenge)
    from social_copy import decimal_projection
    if decimal_projection(text):
        found.append('decimal projection: keep forecasts off bet copy and preserve exact wager lines')
    if not graphic and re.search(r'next climb target|when it qualifies|reviewing the (?:college )?slate|ticket isn.t picked yet', text, re.I):
        found.append('operational status-report voice: rewrite as a casual target-day update')
    if re.search(r'separate from kook[’\x27]?n', text, re.I):
        found.append('owner identity split: use My card, not a separate Kookn identity')
    if not graphic and re.search(r'(?:https?://)?(?:www\.)?keenroudy\.com/sports\b', text, re.I):
        found.append('routine website link')
    if re.search(r'early (?:score )?estimates?|new rosters (?:can change|may differ)', text, re.I):
        found.append('generic estimate/roster boilerplate')
    if re.search(r'entertainment only', text, re.I):
        found.append('graphic/caption entertainment footer')
    return found


def mark(path, svg, *, challenge=()):
    """Attest only a fresh native render whose actual SVG passed this policy."""
    if issues(svg, graphic=True, challenge=challenge):
        return False
    raw = path.read_bytes()
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or raw[12:16] != b'IHDR':
        raise ValueError('Social style marker requires a PNG render')
    end = 20 + int.from_bytes(raw[8:12], 'big')
    markers = (MARKER, CLIMB_MARKER) if challenge else (MARKER,)
    chunks = []
    for marker in markers:
        chunk = b'tEXt' + marker
        chunks.append(struct.pack('>I', len(marker)) + chunk
                      + struct.pack('>I', zlib.crc32(chunk) & 0xffffffff))
    path.write_bytes(raw[:end] + b''.join(chunks) + raw[end:])
    return True
