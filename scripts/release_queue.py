"""Private admissions which become public only when Discord releases them.

The queue lives outside the repository.  Selection can reserve a future play,
but neither ``research/`` nor the public post log sees it until delivery.
"""
import json
import shutil
from pathlib import Path

import gates


def path(conf):
    return Path(conf) / 'pending' / 'play-releases.json'


def cards(conf):
    return Path(conf) / 'pending' / 'release-cards'


def load(conf):
    try:
        value = json.loads(path(conf).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'plays': []}
    return value if isinstance(value, dict) and isinstance(value.get('plays'), list) else {'plays': []}


def save(conf, book):
    target = path(conf)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(book, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(target)


def merge_context(ctx, conf):
    """Make private admissions visible to duplicate/cap gates, never the site."""
    for row in load(conf).get('plays', []):
        pick = dict(row.get('pick') or {})
        key = pick.get('id')
        if not key or row.get('releasedAt') or key in ctx.first:
            continue
        pick['_pendingRelease'] = True
        pick['admittedAt'] = row.get('admittedAt')
        # Existing gates order and cap public rows by publishedAt.  This copy is
        # process-local; it is never written to research/.
        pick['publishedAt'] = row.get('admittedAt')
        ctx.first[key] = pick
        ctx.latest[key] = dict(pick)


def enqueue(conf, rows, reasons, decisions, draft_dir, now, games=None):
    """Save newly selected rows and their rendered art outside Git."""
    book = load(conf)
    known = {row.get('id') for row in book['plays']}
    added = []
    decision_by_id = {row.get('id'): row for row in decisions if row.get('decision') == 'published'}
    card_dir = cards(conf)
    card_dir.mkdir(parents=True, exist_ok=True)
    for league, kind, candidate in rows:
        key = candidate.get('id')
        if not key or key in known:
            continue
        source = Path(draft_dir) / f'{key}.png'
        copy_source = Path(draft_dir) / f'{key}.txt'
        if not source.exists():
            raise RuntimeError(f'private release card was not rendered: {key}')
        if not copy_source.exists():
            raise RuntimeError(f'private release caption was not rendered: {key}')
        target = card_dir / f'{key}.png'
        shutil.copyfile(source, target)
        pick = {k: v for k, v in candidate.items() if not str(k).startswith('_')}
        pick.pop('publishedAt', None)
        row = {'id': key, 'league': league, 'kind': kind, 'admittedAt': gates.stamp(now),
               'pick': pick, 'reason': reasons.get(key), 'decision': decision_by_id.get(key),
               'kickoffs': [games[g]['kickoff'] for g in pick.get('gameIds') or [] if games and g in games],
               'caption': copy_source.read_text(encoding='utf-8').strip(), 'card': str(target)}
        book['plays'].append(row)
        known.add(key)
        added.append(key)
    save(conf, book)
    return added


def remove(conf, key):
    book = load(conf)
    book['plays'] = [row for row in book['plays'] if row.get('id') != key]
    save(conf, book)


def update(conf, key, **changes):
    book = load(conf)
    row = next((row for row in book['plays'] if row.get('id') == key), None)
    if row is None:
        raise KeyError(key)
    row.update(changes)
    save(conf, book)
    return row
