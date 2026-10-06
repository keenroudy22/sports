"""Verify that the public record is exactly the append-only published-pick history.

Personal/social tickets never live in research.json. Requiring an exact ID match prevents one from entering the
official record accidentally, while settlement comparisons catch stale or omitted grades.
"""
import argparse
import json
from pathlib import Path

import build_site

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def audit(reports, public):
    issues = []
    if not isinstance(reports, list) or not isinstance(public, dict) or not isinstance(public.get('picks'), list):
        return ['invalid record input']
    first, latest = build_site.first_publications(reports)
    rows = public['picks']
    ids = [row.get('id') for row in rows]
    if len(ids) != len(set(ids)):
        issues.append('duplicate public pick id')
    expected, actual = set(first), set(ids)
    for pick_id in sorted(expected - actual):
        issues.append(f'missing public pick: {pick_id}')
    for pick_id in sorted(actual - expected):
        issues.append(f'non-official pick in public record: {pick_id}')
    indexed = {row.get('id'): row for row in rows if row.get('id')}
    for pick_id in sorted(expected & actual):
        initial, recent, row = first[pick_id], latest.get(pick_id, {}), indexed[pick_id]
        for field, value in (('league', initial.get('league')), ('publishedAt', initial.get('publishedAt')),
                             ('result', recent.get('result')), ('settledAt', recent.get('settledAt')),
                             ('units', recent.get('units'))):
            if row.get(field) != value:
                issues.append(f'{pick_id}: {field} does not match the append-only record')
        season = row.get('season')
        if not isinstance(season, int) or isinstance(season, bool) or not 1900 <= season <= 2200:
            issues.append(f'{pick_id}: season is missing or invalid')
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, default=ROOT / 'site' / 'data' / 'research.json')
    parser.add_argument('--today', type=Path, default=ROOT / 'site' / 'data' / 'app' / 'today.json')
    args = parser.parse_args(argv)
    issues = audit(load(args.research), load(args.today))
    print(json.dumps({'picksChecked': len(load(args.today).get('picks') or []), 'issues': issues}, sort_keys=True))
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
