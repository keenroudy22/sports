"""Replay every published pick through the gates as of the moment it was published.

For each first publication in research/, the stores are read as they stood at publishedAt (the
latest odds and prop-odds capture at or before it, the reports published before it, the v2
snapshot it stood on) and every applicable rule runs. The output names each pick, its kind and
each rule it would have failed. Injury statuses are today's, not that day's, so a refusal on an
injury rule is a caveat rather than a finding; the output says so.

Usage: python scripts/replay_gates.py [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--only ID ...]
Stdlib only.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates

INJURY_RULES = {'qb_available', 'prop_injury_clear'}
CAVEATS = {**{rule: "injury statuses are today's" for rule in INJURY_RULES},
           'favorite_needs_reason': 'the record stores source URLs, not the facts a run attaches, so a replay sees none'}


def replay(stores, since=None, until=None, only=None):
    """[(id, kind, publishedAt, [Decision refused])] for every first publication in order."""
    rows = []
    first, _ = gates.build_site.first_publications(stores.reports)
    for key, pick in sorted(first.items(), key=lambda item: item[1].get('publishedAt') or ''):
        if pick.get('historicalImport') or not pick.get('publishedAt'):
            continue
        day = gates.eastern_date(gates.when(pick['publishedAt'])).isoformat()
        if since and day < since or until and day > until or only and key not in only:
            continue
        now = gates.when(pick['publishedAt'])
        ctx = stores.as_of(now)
        candidate = dict(pick)
        candidate.pop('_desk', None)
        kind = gates.kind_of(candidate)
        decisions = gates.evaluate(candidate, ctx, kind)
        rows.append((key, kind, pick['publishedAt'], gates.refusals(decisions)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--since', help='Eastern date, inclusive')
    parser.add_argument('--until', help='Eastern date, inclusive')
    parser.add_argument('--only', nargs='*', help='pick ids')
    args = parser.parse_args(argv)
    stores = gates.Stores()
    rows = replay(stores, args.since, args.until, set(args.only) if args.only else None)
    refused = 0
    for key, kind, published, failures in rows:
        if failures:
            refused += 1
        state = 'passed' if not failures else 'REFUSED'
        print(f'{published}  {kind:<10} {key}  {state}')
        for decision in failures:
            note = f'  (caveat: {CAVEATS[decision.rule]})' if decision.rule in CAVEATS else ''
            print(f'    {decision.rule}: {decision.reason}{note}')
    print(f'\n{len(rows)} picks replayed, {refused} would have been refused by the gates as they stand today.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
