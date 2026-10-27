"""Prospective Chef probability evidence; never relabel published history.

Only frozen pregame decisions from the same probability specification qualify.
The error allowance is a cohort estimate, not a confidence bound on one game.
No new feeds, stakes, or model fitting. Existing selection/release gates remain.
"""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
import learning
import pricing

VERSION = 'chef-forward-ev-v1'
FROM = datetime(2026, 10, 27, 19, 40, tzinfo=timezone.utc)
MINIMUM = 30
MIN_BUFFER = .02


def instant(value):
    try:
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value if value.tzinfo else None
    except (TypeError, ValueError):
        return None


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def specification(candidate, ctx):
    import gates
    if candidate.get('legs') or not isinstance(getattr(ctx,'policy',None),dict):
        return None
    league = candidate.get('league') or candidate.get('_league') or (gates.game_of(candidate, ctx) or {}).get('league')
    market = gates.market_key(candidate)
    family = 'prop' if candidate.get('athleteId') else market
    fitted = (ctx.policy.get('calibration') or {}).get(f'{league}/{family}', {})
    definition = dict(policy=VERSION, league=league, market=market,
                      model=candidate.get('modelVersion'), learnedK=fitted.get('k'),
                      fixedK=pricing.CALIBRATION.get((league, market)),
                      # Changes to selection/pricing require fresh forward proof.
                      code={name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                            for name in ('gates.py', 'pricing.py', 'model_v2.py', 'features.py', 'continuity.py')})
    return hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()


def evidence(candidate, ctx, numbers, candidates=None, grades=None):
    """Point-in-time, deduplicated forward cohort near this estimated chance."""
    if candidate.get('league') not in ('NFL','CFB'):
        return dict(ok=False,reason='This sport remains in its separate trial',n=0,policy=VERSION)
    token = specification(candidate, ctx)
    if not token:
        return dict(ok=False,reason='Chef probability specification unavailable',n=0,policy=VERSION)
    season = (ctx.games.get((candidate.get('gameIds') or [None])[0]) or {}).get('season', ctx.now.year)
    if candidates is None:
        if learning.boxscores.verify(learning.STORE):
            return dict(ok=False, reason='Chef forward evidence integrity failed', n=0, policy=VERSION)
        candidates = learning.read('candidates', season)
    if grades is None:
        grades = learning.read('graded', season)
    latest_grades = {}
    for row in grades:
        clock = instant(row.get('gradedAt'))
        if clock and clock <= ctx.now and row.get('result') in ('win', 'loss'):
            if clock >= instant(latest_grades.get(row.get('id'), {}).get('gradedAt') or '1900-01-01T00:00Z'):
                latest_grades[row['id']] = row
    distinct = {}
    chance = numbers.get('anchoredChance')
    if not finite(chance) or not 0 < chance < 1:
        return dict(ok=False, reason='Chef probability is unavailable', n=0, policy=VERSION)
    for row in candidates:
        decided, kickoff = instant(row.get('decidedAt')), instant(row.get('kickoff'))
        quoted = instant(row.get('quotedAt'))
        grade = latest_grades.get(row.get('id'))
        probability, fair = row.get('chance'), row.get('fairChance')
        if (row.get('probabilitySpec') != token or not candidate.get('modelVersion')
                or not decided or not kickoff or not quoted or not FROM <= decided < kickoff < ctx.now
                or not quoted <= decided or decided-quoted > timedelta(hours=2)
                or not grade or instant(grade['gradedAt']) < kickoff
                or not finite(probability) or not 0 < probability < 1
                or not finite(fair) or not 0 < fair < 1
                or abs(probability-chance) > .10 or row.get('direction') != candidate.get('direction')
                or row.get('legs') or row.get('historicalImport')):
            continue
        # One outcome per game: correlated players/books cannot manufacture n.
        key = tuple(row.get('gameIds') or [])
        if not key: continue
        old = distinct.get(key)
        if old is None or decided < instant(old['decidedAt']):
            distinct[key] = dict(row, outcome=int(grade['result'] == 'win'))
    rows = list(distinct.values())
    result = dict(policy=VERSION, probabilitySpec=token, n=len(rows), minimum=MINIMUM,
                  evaluatedAt=ctx.now.isoformat(), ok=False)
    if len(rows) < MINIMUM:
        return dict(result, reason=f'Chef needs {MINIMUM} matching forward game grades; has {len(rows)}')
    errors = [r['chance']-r['outcome'] for r in rows]
    brier = statistics.mean(e*e for e in errors)
    market_brier = statistics.mean((r['fairChance']-r['outcome'])**2 for r in rows)
    buffer = max(MIN_BUFFER, statistics.mean(errors)+1.645*statistics.stdev(errors)/math.sqrt(len(errors)))
    conservative = max(0, chance-buffer)
    even = pricing.break_even(candidate['odds'])
    result.update(modelBrier=brier, marketBrier=market_brier, errorAllowance=buffer,
                  conservativeChance=conservative, breakEven=even,
                  evPerUnit=conservative*pricing.payout(candidate['odds'])-(1-conservative))
    result['ok'] = brier < market_brier and conservative > even
    result['reason'] = ('Chef forward probability and buffered price checks passed' if result['ok']
                        else 'Chef forward probability or buffered price check failed')
    return result
