"""Owner's prospective caption/art policy, including already queued private posts."""
import html
import re
import struct
import zlib
from datetime import datetime, timezone

VERSION = 'units-only-no-decimal-20261027'
EFFECTIVE = datetime(2026, 10, 22, tzinfo=timezone.utc)
MARKER = b'KooknSocial\x00' + VERSION.encode()


def active(now):
    return now >= EFFECTIVE


def current_png(path):
    try:
        with path.open('rb') as source:
            raw = source.read(256)
        return raw.startswith(b'\x89PNG\r\n\x1a\n') and MARKER in raw
    except OSError:
        return False


def release_issues(text, path):
    found = issues(text)
    if not current_png(path):
        found.append('private house card lacks current source-render attestation')
    return found


def privacy_issues(text):
    found = []
    if re.search(r'[$＄]\s*\d|\b(?:USD|dollars?)\b', str(text), re.I):
        found.append('personal dollar amounts: use known units only')
    if re.search(r'\b(?:bet|wager|ticket)\s*(?:id|number|#)\s*[:#-]?\s*[A-Za-z0-9-]{4,}', str(text), re.I):
        found.append('private bet identifier')
    return found


def issues(text, graphic=False):
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(text or '')))
    found = privacy_issues(text)
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


def mark(path, svg):
    """Attest only a fresh native render whose actual SVG passed this policy."""
    if issues(svg, graphic=True):
        return False
    raw = path.read_bytes()
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or raw[12:16] != b'IHDR':
        raise ValueError('Social style marker requires a PNG render')
    end = 20 + int.from_bytes(raw[8:12], 'big')
    chunk = b'tEXt' + MARKER
    path.write_bytes(raw[:end] + struct.pack('>I', len(MARKER)) + chunk
                     + struct.pack('>I', zlib.crc32(chunk) & 0xffffffff) + raw[end:])
    return True
