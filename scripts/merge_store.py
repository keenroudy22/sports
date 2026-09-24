"""Resolve a git rebase or merge that stopped on the append-only price stores. Stdlib only.

Two writers append to the stores (data/odds, data/prop-odds and the others in STORES): the hosted workflow and the desk on the owner's
machine. When both capture inside the same few minutes, whichever pushes second is rejected, and its
rebase onto the other stops on the same three files: the .jsonl records (both sides appended), the
ledger (each side's byte-exact prefix commitment) and the status file (each side's count of the day).
Every capture script refuses to write while the ledger disagrees with the file, so a half-resolved
store would stop all captures. This resolves the stop without losing a record:

  *.jsonl        every line from both sides, once, in retrievedAt order
  ledger.json    recomputed from the merged files, exactly as every capture script writes it
  status*.json   the later side's status; a day's capture count is the larger of the two and the
                 remaining budget the smaller, so a merge never buys an extra request

Anything unmerged outside those stores is left alone and named; the caller aborts the rebase.

  python scripts/merge_store.py        resolve, `git add` what it resolved; exit 1 if anything is still unmerged
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores

ROOT = Path(__file__).resolve().parents[1]
STORES = ('data/odds', 'data/prop-odds', 'data/props', 'data/forecasts', 'data/weather', 'data/boxscores')
# Every append-only store two runs can both extend. A conflict anywhere else still stops the rebase for a person.


def git(*args, cwd=ROOT):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)


def unmerged(cwd=ROOT):
    return [p for p in git('diff', '--name-only', '--diff-filter=U', cwd=cwd).stdout.splitlines() if p.strip()]


def stage(path, number, cwd=ROOT):
    """The file's content at an index stage (1 base, 2 ours, 3 theirs), or None when that side has none."""
    result = git('show', f':{number}:{path}', cwd=cwd)
    return result.stdout if result.returncode == 0 else None


def lines_of(text):
    return [line.rstrip('\r\n') for line in (text or '').splitlines() if line.strip()]


STAMPS = ('retrievedAt', 'publishedAt', 'capturedAt', 'observedAt')


def retrieved(line):
    """The moment a store line was taken, whichever of the stores' timestamp fields it carries."""
    try:
        record = json.loads(line)
    except ValueError:
        return ''
    if not isinstance(record, dict):
        return ''
    return str(next((record[k] for k in STAMPS if record.get(k)), '') or '')


def merge_lines(base, ours, theirs):
    """Every line from both sides once, in the order the records were retrieved (a stable sort, so lines
    without a retrievedAt keep their place among their neighbours)."""
    seen, out = set(), []
    for block in (lines_of(base), lines_of(ours), lines_of(theirs)):
        for line in block:
            if line not in seen:
                seen.add(line)
                out.append(line)
    if all(retrieved(line) for line in out):
        out.sort(key=retrieved)
    return out


def parse(text):
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def moment(status):
    usage = status.get('usage') if isinstance(status.get('usage'), dict) else {}
    return str(usage.get('at') or status.get('at') or '')


def merge_status(ours, theirs):
    """The later side's status, never more generous than either side about the day's budget."""
    a, b = parse(ours), parse(theirs)
    if not isinstance(a, dict):
        return b
    if not isinstance(b, dict):
        return a
    later, other = (b, a) if moment(b) >= moment(a) else (a, b)
    merged = json.loads(json.dumps(later))
    for league, row in (other.get('leagues') or {}).items():
        mine = (merged.setdefault('leagues', {})).setdefault(league, {})
        if isinstance(row, dict) and isinstance(mine, dict) and row.get('day') == mine.get('day') and 'count' in row and 'count' in mine:
            mine['count'] = max(int(mine['count']), int(row['count']))
    if isinstance(merged.get('usage'), dict) and isinstance(other.get('usage'), dict):
        if merged['usage'].get('remaining') is not None and other['usage'].get('remaining') is not None:
            merged['usage']['remaining'] = min(int(merged['usage']['remaining']), int(other['usage']['remaining']))
        if merged['usage'].get('used') is not None and other['usage'].get('used') is not None:
            merged['usage']['used'] = max(int(merged['usage']['used']), int(other['usage']['used']))
    return merged


def store_of(path):
    return next((s for s in STORES if path.startswith(s + '/')), None)


def resolve(cwd=ROOT, log=print):
    """Resolve every unmerged path inside the stores and stage the result. Returns (resolved, left)."""
    cwd = Path(cwd)
    resolved, left, touched = [], [], set()
    for path in unmerged(cwd):
        store = store_of(path)
        if not store:
            left.append(path)
            continue
        target = cwd / path
        name = Path(path).name
        if name.endswith('.jsonl'):
            merged = merge_lines(stage(path, 1, cwd), stage(path, 2, cwd), stage(path, 3, cwd))
            target.write_text('\n'.join(merged) + ('\n' if merged else ''), encoding='utf-8', newline='\n')
            log(f'merge_store: {path}: {len(merged)} records from both sides')
        elif name == 'ledger.json':
            pass                                  # recomputed below, once the records are settled
        elif name.endswith('.json'):
            status = merge_status(stage(path, 2, cwd), stage(path, 3, cwd))
            if status is None:
                left.append(path)
                continue
            boxscores.write_json(target, status)
            log(f'merge_store: {path}: later status, budget from the stricter side')
        else:
            left.append(path)
            continue
        touched.add(store)
        resolved.append(path)
    for store in sorted(touched):
        ledger = cwd / store / 'ledger.json'
        boxscores.write_json(ledger, boxscores.ledger(cwd / store))
        rel = f'{store}/ledger.json'
        if rel not in resolved:
            resolved.append(rel)
        log(f'merge_store: {rel}: recomputed over the merged records')
    if resolved:
        git('add', '--', *resolved, cwd=cwd)
    return resolved, left


def main(argv=None):
    resolved, left = resolve()
    if left:
        print('merge_store: still unmerged, not a store: ' + ', '.join(left))
        return 1
    if not resolved:
        print('merge_store: nothing to resolve')
    return 0


if __name__ == '__main__':
    sys.exit(main())
