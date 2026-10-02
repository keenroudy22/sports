"""Offline preregistered CFB experiments. Never changes weights, policies or forecasts.

Development season 2024; report 2025 separately. Weeks, not individual rows, are
bootstrap blocks. Opposing teams and markets in a game always share the same fold.
The existing baseline previously used 2025 for validation: this is comparative
retrospective evidence, NOT a new untouched holdout or authority to promote.
"""
import argparse
import hashlib
import json
import random
import statistics
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import features
import model_v2


def variants():
    base = deepcopy(model_v2.PARAMS['CFB'])
    out = {'released': base}
    for name in ('blowout', 'continuity', 'efficiency'):
        p = deepcopy(base)
        if name == 'efficiency':
            p['total']['blend'] = .7
        else:
            for target in ('margin', 'total'):
                p[target]['blowoutWeight' if name == 'blowout' else 'continuity'] = .35 if name == 'blowout' else 1.0
        out[name] = p
    return out


def paired_weeks(base, candidate, target, draws=1000):
    old = {r['eventId']: r for r in base}
    weeks = defaultdict(list)
    for row in candidate:
        prior = old.get(row['eventId'])
        if not prior or row['kickoff'] != prior['kickoff']:
            continue
        week = model_v2.week_start(features.when(row['kickoff'])).isoformat()
        weeks[week].append(abs(row['forecast'][target] - row[target]) - abs(prior['forecast'][target] - prior[target]))
    if len(weeks) < 4:
        return {'status': 'insufficient weeks', 'weeks': len(weeks)}
    blocks, rng = list(weeks.values()), random.Random(7)
    boots = sorted(statistics.mean(v for block in rng.choices(blocks, k=len(blocks)) for v in block) for _ in range(draws))
    lo, hi = boots[int(.05 * draws)], boots[min(draws - 1, int(.95 * draws))]
    return {'games': sum(map(len, blocks)), 'weeks': len(blocks),
            'meanErrorDelta': round(statistics.mean(v for b in blocks for v in b), 3),
            'interval90': [round(lo, 3), round(hi, 3)],
            'status': 'improvement' if hi < 0 else 'worse' if lo > 0 else 'uncertain'}


def run():
    records = sorted(features.load(leagues=('CFB',)), key=lambda g: (g['kickoff'], g['eventId']))
    plan = variants()
    output = {'purpose': 'offline evaluation only', 'promotion': False, 'variants': plan,
              'caveat': 'Retrospective holdout already examined for the released baseline. Prospective shadow required.',
              'inputDigest': hashlib.sha256(json.dumps([(g['eventId'], g['hash']) for g in records]).encode()).hexdigest(),
              'seasons': {}}
    for season in (2024, 2025):
        forecasts = {}
        for name, params in plan.items():
            print(f'Evaluating {season} {name}', flush=True)
            forecasts[name] = model_v2.backtest('CFB', season, params=params, records=records)
        base = forecasts['released']
        # Classification comes only from seasons already completed before evaluation.
        # This is the model's stored-coverage heuristic, not an official FBS membership claim.
        fbs = model_v2.fbs_teams([g for g in records if g['season'] < season])
        known_fbs = {g['eventId'] for g in records if {g['home']['id'], g['away']['id']} <= fbs}
        output['seasons'][season] = {name: {'score': model_v2.score(rows),
            'comparison': {target: paired_weeks(base, rows, target) for target in ('margin', 'total')},
            'scheduleCoverage': {'bothPreviouslyFbsCoverage': sum(r['eventId'] in known_fbs for r in rows),
                                 'fcsOrUncertainCoverage': sum(r['eventId'] not in known_fbs for r in rows)},
            'fbsOnlyComparison': {target: paired_weeks([r for r in base if r['eventId'] in known_fbs],
                [r for r in rows if r['eventId'] in known_fbs], target) for target in ('margin', 'total')}}
            for name, rows in forecasts.items()}
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('work/audit-evaluation.json'))
    args = parser.parse_args()
    result = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Saved {args.out}; no live model changes.')
