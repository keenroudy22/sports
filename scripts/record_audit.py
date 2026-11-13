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


def audit_nba_public(public, expected):
    """The Results adapter must be the exact receipt-backed NBA projection."""
    actual = public.get('nbaPicks') if isinstance(public, dict) else None
    if actual is None:
        return ['NBA picks are missing from the all-sports Results payload'] if expected else []
    return [] if actual == expected else ['NBA Results rows differ from the receipt-backed NBA ledger']


def audit_cbb_public(public, expected):
    """The Results adapter must be the exact receipt-backed CBB projection."""
    actual = public.get('cbbPicks') if isinstance(public, dict) else None
    if actual is None:
        return ['CBB picks are missing from the all-sports Results payload'] if expected else []
    return [] if actual == expected else ['CBB Results rows differ from the receipt-backed CBB ledger']


def audit_all_sports(public):
    """A play may appear in one sport ledger only; duplicates corrupt day and month totals."""
    rows = [row for key in ('picks', 'cbbPicks', 'nbaPicks') for row in (public.get(key) or [])]
    ids = [row.get('id') for row in rows]
    return ['duplicate play id across all-sports Results ledgers'] if len(ids) != len(set(ids)) else []


def audit_cbb_today(public, today):
    fields = ('line', 'odds', 'book', 'riskUnits', 'result', 'actual', 'settledAt')
    def terms(rows):
        return sorted((row['id'], *(row.get(key) for key in fields)) for row in rows)
    return [] if terms(public['cbbPicks']) == terms(today['picks']['plays']) else [
        'CBB Today and Results differ on delivered picks or their terms']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, default=ROOT / 'site' / 'data' / 'research.json')
    parser.add_argument('--today', type=Path, default=ROOT / 'site' / 'data' / 'app' / 'today.json')
    args = parser.parse_args(argv)
    public = load(args.today)
    issues = audit(load(args.research), public)
    issues.extend(audit_all_sports(public))
    issues.extend(audit_cbb_public(public, build_site.cbb_record_picks()))
    issues.extend(audit_nba_public(public, build_site.nba_record_picks()))
    cbb_today = args.today.with_name('cbb.json')
    if cbb_today.is_file():
        issues.extend(audit_cbb_today(public, load(cbb_today)))
    import community_record
    if public.get('communityPicks', []) != community_record.build(ROOT):
        issues.append('personal-ticket record differs from pregame receipts and append-only settlements')
    counts = {key: len(public.get(key) or []) for key in ('picks', 'cbbPicks', 'nbaPicks')}
    print(json.dumps({'picksChecked': sum(counts.values()), 'byLedger': counts, 'issues': issues}, sort_keys=True))
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
