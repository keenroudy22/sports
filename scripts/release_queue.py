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


def archive_card(source, root, key):
    """Copy exact released art into the commit that first publishes the play.

    The hosted build cannot recover a card from the live site before that first
    build has published it.  This tracked bootstrap is byte-for-byte input, not
    a request to render posted art again.
    """
    if not isinstance(key, str) or not key or any(part in key for part in ('/', '\\', '..')):
        raise ValueError(f'invalid release card key: {key!r}')
    data = Path(source).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or not 64 <= len(data) <= 10 * 1024 * 1024:
        raise ValueError(f'release card is not a valid PNG: {key}')
    folder = Path(root) / 'data' / 'release-cards'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{key}.png'
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(data)
    temporary.replace(target)
    return target


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


def reopen_expired(conf, now, log=print):
    """Drop unreleased admissions whose price window ended so a fresh pass can reconsider them.

    A pending row reserves duplicate/cap space only while its saved quote is usable.  Once
    that quote expires, keeping it in the private queue makes the next selection pass skip
    the same market instead of checking the newly captured price.
    """
    book = load(conf)
    kept, reopened = [], []
    for row in book['plays']:
        pick = row.get('pick') or {}
        if row.get('discordSentAt') or row.get('publicPath') or row.get('releasedAt'):
            kept.append(row)
            continue
        try:
            expired = gates.when(pick.get('expiresAt')) <= now
        except (TypeError, ValueError):
            expired = False
        if not expired:
            kept.append(row)
            continue
        reopened.append(row.get('id'))
        log(f"private admission reopened for a fresh price: {row.get('id')}")
    if reopened:
        book['plays'] = kept
        save(conf, book)
    return reopened


def enqueue(conf, rows, reasons, decisions, draft_dir, now, games=None, log=print):
    """Save newly selected rows and their rendered art outside Git.

    An incomplete private draft is still queued.  The five-minute release worker
    owns artifact recovery, so a card-rendering problem cannot make a selected
    play disappear from both delivery and the chosen-but-not-posted checks.
    """
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
        target = card_dir / f'{key}.png'
        if source.exists():
            shutil.copyfile(source, target)
        pick = {k: v for k, v in candidate.items() if not str(k).startswith('_')}
        pick.pop('publishedAt', None)
        row = {'id': key, 'league': league, 'kind': kind, 'admittedAt': gates.stamp(now),
               'pick': pick, 'reason': reasons.get(key), 'decision': decision_by_id.get(key),
               'kickoffs': [games[g]['kickoff'] for g in pick.get('gameIds') or [] if games and g in games],
               'caption': copy_source.read_text(encoding='utf-8').strip() if copy_source.exists() else None,
               'card': str(target)}
        missing = []
        if not source.exists():
            missing.append('card')
        if not copy_source.exists():
            missing.append('caption')
        if missing:
            row['artifactState'] = 'recovery-needed'
            row['artifactMissing'] = missing
            log(f"private admission queued for artifact recovery: {key}: missing {', '.join(missing)}")
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
