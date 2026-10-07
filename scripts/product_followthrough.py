"""Read the dated product queue for the existing private weekly review.

This is planning evidence, not a work executor or live completion check. Only the
repository's fixed status file is read; item text cannot supply files, commands,
URLs to fetch, notification destinations or new scheduling instructions.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = ('shipped', 'ready', 'owner-needed', 'observing', 'gated')
OWNERS = ('agent', 'owner', 'desk', 'provider')
MAX_BYTES = 128 * 1024
MAX_ITEMS = 58                        # bounded October 7 queue; stable IDs are never reused
BRIEF_LIMIT = 1200
ITEM_FIELDS = {'id', 'title', 'status', 'owner', 'next', 'doneWhen', 'evidence'}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate field')
        result[key] = value
    return result


def _unavailable(reason):
    return {'state': 'unavailable', 'reason': reason, 'updatedAt': None,
            'items': [], 'counts': None}


def _utc(value):
    if not isinstance(value, str) or len(value) > 40 or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value):
        raise ValueError('invalid UTC timestamp')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def read_status(root=ROOT, now=None):
    """Return a validated, bounded snapshot or a visible unavailable state.

    ``root`` is the caller's trusted repository root, never read from the file.
    Missing/corrupt/future evidence is not an empty or completed work queue.
    Stale rows retain their recorded states, explicitly as dated assertions.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return _unavailable('The review time is unavailable.')
    path = Path(root) / 'docs' / 'product-status.json'
    try:
        if path.is_symlink():
            return _unavailable('The status file must be a repository file, not a link.')
        with path.open('rb') as source:
            raw = source.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return _unavailable('The product status file is missing.')
    except OSError:
        return _unavailable('The product status file could not be read.')
    if len(raw) > MAX_BYTES:
        return _unavailable('The product status file exceeds its size limit.')
    try:
        payload = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(payload, dict) or set(payload) != {'version', 'updatedAt', 'items'} \
                or type(payload['version']) is not int or payload['version'] != 1:
            raise ValueError('unsupported schema')
        updated = _utc(payload['updatedAt'])
        if updated > now:
            return _unavailable('The product status timestamp is in the future; review is needed.')
        items = payload['items']
        if not isinstance(items, list) or len(items) > MAX_ITEMS:
            raise ValueError('invalid item count')
        seen = set()
        for row in items:
            if not isinstance(row, dict) or set(row) != ITEM_FIELDS:
                raise ValueError('invalid item fields')
            for key, value in row.items():
                limit = 500 if key == 'evidence' else 240
                if not isinstance(value, str) or len(value) > limit \
                        or (key != 'evidence' and not value.strip()) \
                        or any(not char.isprintable() for char in value):
                    raise ValueError('invalid item text')
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', row['id']) or row['id'] in seen:
                raise ValueError('invalid item identity')
            if row['status'] not in STATES or row['owner'] not in OWNERS:
                raise ValueError('unknown state or owner')
            seen.add(row['id'])
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return _unavailable('The product status file is invalid or uses an unsupported schema/state.')
    return {'state': 'stale' if now - updated > timedelta(days=8) else 'available',
            'updatedAt': updated.isoformat().replace('+00:00', 'Z'),
            'items': items, 'counts': {state: sum(row['status'] == state for row in items) for state in STATES}}


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def brief(status):
    """Deterministic private prefix, small enough for the existing phone/Discord excerpts."""
    lines = ['Product follow-through']
    if status['state'] == 'unavailable':
        return '\n'.join(lines + ['Unavailable. ' + status['reason'],
                                 'Review needed; unfinished work cannot be assessed.'])
    lines.append(f"Dated queue: {status['updatedAt']}. Not live completion verification.")
    if status['state'] == 'stale':
        lines.append('STALE: more than 8 days old; review needed. Listed states are dated assertions.')
    counts = status['counts']
    lines.append('Listed: ' + ' · '.join(f'{counts[state]} {state}' for state in STATES) + '.')
    if not status['items']:
        lines.append('No items registered; this does not establish that all work is done.')
    for state, label in (('ready', 'Next ready'), ('owner-needed', 'Owner action')):
        item = next((row for row in status['items'] if row['status'] == state), None)
        if item:
            lines.append(f"{label}: {item['id']} {_clip(item['title'], 100)}. {_clip(item['next'], 180)}")
        else:
            lines.append(f'{label}: none listed in this dated queue.')
    lines.append('Full queue and completion criteria are in the saved packet.')
    result = '\n'.join(lines)
    # Field limits keep the whole prefix below the existing notification limits;
    # do not truncate after rendering and accidentally drop the owner action.
    assert len(result) <= BRIEF_LIMIT
    return result


def packet(status):
    """Full recorded queue in stable file order; no model may declare it complete."""
    out = ['## Product-plan follow-through', '', brief(status), '',
           'Planning data only; not instructions to execute. No new work, permission or release is triggered here.']
    for row in status['items']:
        out += ['', f"### {row['id']} · {row['title']}",
                f"- Recorded status: {row['status']}; responsible: {row['owner']}",
                f"- Next: {row['next']}", f"- Complete when: {row['doneWhen']}",
                f"- Evidence: {row['evidence'] or 'not recorded'}"]
    return '\n'.join(out) + '\n'
