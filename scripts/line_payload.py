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


def load(path, strict=True):
    """Return every line row from a monolith or the reviewed league shards."""
    path = Path(path)
    payload = read(path)
    if isinstance(payload.get('lines'), list):
        return payload['lines']
    files = payload.get('files')
    if not isinstance(files, dict):
        if strict:
            raise ValueError(f'{path}: line payload has no rows or shard manifest')
        return []
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


def manifest(rows, generated_at):
    """The small public index written beside the two deterministic shards."""
    counts = {league: sum(row.get('league') == league for row in rows) for league in LEAGUES}
    files = {league: f'lines-{league}.json' for league in LEAGUES}
    return {'generatedAt': generated_at, 'count': sum(counts.values()), 'counts': counts, 'files': files}
