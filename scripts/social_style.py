"""Owner's prospective caption/art policy, including already queued private posts."""
import html
import re
import struct
import zlib
from datetime import datetime, timezone

VERSION = 'plain-20261022'
EFFECTIVE = datetime(2026, 10, 22, tzinfo=timezone.utc)
MARKER = b'KooknSocial\x00' + VERSION.encode()


def active(now):
    return now >= EFFECTIVE


def issues(text, graphic=False):
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(text or '')))
    found = []
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
