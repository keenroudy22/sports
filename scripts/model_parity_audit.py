"""Read-only formula and minutes evaluation. No admission, feed or model promotion.

2026 football is after the fixed 2024/25 coefficient-fitting seasons. It is an
observed-candidate sample, not an unbiased betting trial. Stored fair probabilities
are rounded. NBA comparison is chronological walk-forward on the available
Jan-Apr 2026 boxes; it cannot validate an October early-season rollover.
"""
import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import boxscores
import nba_player_props as nba
import pricing

ROOT = Path(__file__).resolve().parents[1]


def recent_minutes_candidate(logs, team, season, stat):
    """Rejected experimental replacement; never imported by production paths."""
    projection, hold = nba.forecast(logs, team, season, stat)
    if not projection:
        return projection, hold
    current = [h for h in logs if h['team'] == team and h['season'] == season
               and isinstance(h['stats'].get('min'), (int, float))
               and not isinstance(h['stats']['min'], bool)
               and math.isfinite(h['stats']['min']) and 0 < h['stats']['min'] <= 60]
    recent = current[-3:]
    if len(recent) < 2:
        return projection, hold
    minutes = min(40, statistics.median(h['stats']['min'] for h in recent))
    return dict(projection, minutes=round(minutes, 1),
                value=round(minutes*projection['rate'], 1), minutesBasis='recent-games'), None


def nba_comparison(boxes):
    history, groups = defaultdict(list), defaultdict(list)
    for b in sorted({b['eventId']: b for b in boxes}.values(), key=lambda b: b['kickoff']):
        if b.get('seasonType') != 2:
            continue
        for p in b['players']:
            if p.get('dnp'):
                continue
            logs = history[p['id']]
            for stat in ('min', 'pts', 'reb', 'ast'):
                target = 'pts' if stat == 'min' else stat
                old, _ = nba.forecast(logs, p['team'], b['season'], target)
                new, _ = recent_minutes_candidate(logs, p['team'], b['season'], target)
                if not old or not new or new.get('minutesBasis') != 'recent-games' or stat not in p['stats']:
                    continue
                field = 'minutes' if stat == 'min' else 'value'
                groups[(b['season'], stat)].append((abs(old[field]-p['stats'][stat]), abs(new[field]-p['stats'][stat])))
            logs.append(dict(p, season=b['season'], date=b['kickoff']))
    return [{'season': season, 'stat': stat, 'n': len(rows),
             'releasedMAE': round(statistics.mean(r[0] for r in rows), 4),
             'candidateMAE': round(statistics.mean(r[1] for r in rows), 4)}
            for (season, stat), rows in sorted(groups.items())]


def football_comparison(candidates, grades):
    outcomes = {r['id']: r for r in grades}
    groups, seen = defaultdict(list), set()
    for row in sorted(candidates, key=lambda r: r.get('decidedAt', '')):
        market = row.get('marketType')
        k = pricing.CALIBRATION.get((row.get('league'), market))
        result = outcomes.get(row['id'], {}).get('result')
        if (k is None or result not in ('win', 'loss') or row.get('athleteId')
                or row.get('rawChance') is None or row.get('fairChance') is None
                or not row.get('kickoff') or row.get('decidedAt', '') >= row['kickoff']):
            continue
        key = (tuple(row.get('gameIds', [])), market, row.get('direction'), row.get('line'))
        if key in seen:
            continue
        seen.add(key)
        raw, fair, won = row['rawChance'], row['fairChance'], int(result == 'win')
        neutral = pricing.neutral_chance(raw, k)
        anchored = fair + k*(raw-fair)
        groups[(row['league'], market)].append(((neutral-won)**2, (anchored-won)**2))
    return [{'league': league, 'market': market, 'n': len(rows),
             'neutralBrier': round(statistics.mean(r[0] for r in rows), 6),
             'anchorBrier': round(statistics.mean(r[1] for r in rows), 6)}
            for (league, market), rows in sorted(groups.items())]


def run():
    paths = sorted((ROOT/'data/sport-box').glob('nba-*.jsonl'))
    candidates = ROOT/'data/learning/candidates-2026.jsonl'
    grades = ROOT/'data/learning/graded-2026.jsonl'
    return {'nba': nba_comparison([r for p in paths for r in boxscores.read_store(p)]),
            'football': football_comparison(boxscores.read_store(candidates), boxscores.read_store(grades)),
            'inputDigests': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in paths+[candidates, grades]},
            'decision': 'Reject automatic last-three-minutes replacement. Repair football formula consistency without refitting coefficients.',
            'limits': 'Retrospective diagnostics, not proof of improved returns. Football differences are small and mixed. '
                      'No usable NBA October early-season holdout with two prior current-season games exists in these inputs. '
                      'Current roster/role checks and sourced review adjustments are operational controls, not a new team score model.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('work/model-parity-evaluation.json'))
    args = parser.parse_args()
    result = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
