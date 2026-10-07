"""Read the public line catalog without making callers care about its storage layout.

The browser payload is split by league so a large football weekend does not make
every visitor download both slates.  Desk callers still receive the complete row
set and fail closed if a shard is missing or the manifest count does not match.
Legacy monolithic fixtures remain readable for focused tests and old checkouts.
"""
import json
from pathlib import Path

LEAGUES = ('NFL', 'CFB')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _load(path):
    path = Path(path)
    payload = read(path)
    if not isinstance(payload, dict):
        raise ValueError(f'{path}: line payload is not an object')
    if isinstance(payload.get('lines'), list):
        return payload['lines']
    files = payload.get('files')
    if not isinstance(files, dict):
        raise ValueError(f'{path}: line payload has no rows or shard manifest')
    rows = []
    for league in LEAGUES:
        expected = f'lines-{league}.json'
        name = files.get(league)
        if name is None:
            continue
        if name != expected:
            raise ValueError(f'{path}: unexpected {league} line shard {name!r}')
        shard = read(path.with_name(name))
        if shard.get('league') != league or not isinstance(shard.get('lines'), list):
            raise ValueError(f'{name}: invalid line shard')
        if any(row.get('league') != league for row in shard['lines']):
            raise ValueError(f'{name}: row outside {league}')
        rows.extend(shard['lines'])
    count = payload.get('count')
    if isinstance(count, int) and count != len(rows):
        raise ValueError(f'{path}: manifest says {count} rows but shards contain {len(rows)}')
    return rows


def load(path, strict=True, log=None):
    """Return every line row, or an explicit empty optional catalog on any invalid payload."""
    try:
        return _load(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError) as exc:
        if strict:
            raise
        if callable(log):
            log(f'line catalog unavailable; optional use skipped: {exc}')
        return []


def manifest(rows, generated_at):
    """The small public index written beside the two deterministic shards."""
    counts = {league: sum(row.get('league') == league for row in rows) for league in LEAGUES}
    files = {league: f'lines-{league}.json' for league in LEAGUES}
    return {'generatedAt': generated_at, 'count': sum(counts.values()), 'counts': counts, 'files': files}
