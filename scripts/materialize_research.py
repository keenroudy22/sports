"""Rebuild the public report index from validated immutable reports, offline.

A hosted rebase can add a Discord-released report after refresh.py ran. Rebuild
that derived index before rendering pages; do not capture prices or change history.
"""
import json
from pathlib import Path

import refresh

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT):
    root = Path(root)
    paths = sorted((root / 'research').glob('*.json'))
    if not paths:
        raise ValueError('No source reports; refusing to replace the public report index')
    data = root / 'site' / 'data'
    slate = json.loads((data / 'slate.json').read_text())
    games = {g['id']: g for g in slate['games']}
    reports = [refresh.validate_report(json.loads(p.read_text()), games) for p in paths]
    reports.sort(key=lambda r: refresh.datetime.fromisoformat(r['publishedAt'].replace('Z', '+00:00')))
    refresh.validate_ledger(reports)
    target = data / 'research.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(reports, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
    return {'reports': len(reports), 'source': 'validated immutable research reports', 'networkCalls': 0}


if __name__ == '__main__':
    print(json.dumps(build()))
