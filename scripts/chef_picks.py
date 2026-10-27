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
    import inspect
    if candidate.get('legs') or not isinstance(getattr(ctx,'policy',None),dict):
        return None
    league = candidate.get('league') or candidate.get('_league') or (gates.game_of(candidate, ctx) or {}).get('league')
    market = gates.market_key(candidate)
    family = 'prop' if candidate.get('athleteId') else market
    fitted = (ctx.policy.get('calibration') or {}).get(f'{league}/{family}', {})
    definition = dict(policy=VERSION, league=league, market=market,
                      model=candidate.get('modelVersion'), learnedK=fitted.get('k'),
                      fixedK=pricing.CALIBRATION.get((league, market)),
                      # Fingerprint probability definitions, not unrelated admission/UI edits.
                      selection=hashlib.sha256(''.join(inspect.getsource(f) for f in
                          (gates.selection_numbers,gates.calibrated_desk,gates.desk_for)).encode()).hexdigest(),
                      code={name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                            for name in ('pricing.py', 'model_v2.py', 'features.py', 'continuity.py', 'starters.py')})
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


def price_comparison(pick, quotes, now):
    """Latest stored exact-line, same-book price near tip; never invent a close."""
    import role_sanity
    kickoff=instant(pick.get('kickoff'));posted=instant(pick.get('quotedAt') or pick.get('publishedAt'))
    if not kickoff or now<kickoff or not posted or not pick.get('book') or not finite(pick.get('odds')) or abs(pick['odds'])<100:return None
    valid=[]
    for q in quotes:
        clock=instant(q.get('retrievedAt'))
        if (not clock or not posted<=clock<kickoff or kickoff-clock>timedelta(hours=1)
            or role_sanity.book_key(q.get('book'))!=role_sanity.book_key(pick.get('book'))
            or q.get('line')!=pick.get('line') or q.get('direction')!=pick.get('direction')
            or not finite(q.get('odds')) or abs(q['odds'])<100
            or not finite(q.get('otherOdds')) or abs(q['otherOdds'])<100):continue
        if not .99<=pricing.break_even(q['odds'])+pricing.break_even(q['otherOdds'])<=1.15:continue
        valid.append(q)
    if not valid:return None
    clock=max(instant(q['retrievedAt']) for q in valid)
    latest=[q for q in valid if instant(q['retrievedAt'])==clock]
    if len({q['odds'] for q in latest})!=1:return None
    q=latest[0]
    return dict(odds=q['odds'],book=pick['book'],retrievedAt=q['retrievedAt'],source=q.get('source'),
        minutesBeforeKickoff=round((kickoff-clock).total_seconds()/60),
        edgePoints=round(100*(pricing.break_even(q['odds'])-pricing.break_even(pick['odds'])),3),
        scope='Latest stored same-book exact-line price within60minutes of tip; not a verified market close')


def stored_price_comparison(pick, now, root=learning.ROOT):
    """Reuse free/native stored quotes. No requests and no settlement changes."""
    import build_site
    import boxscores
    league,season=pick.get('league'),pick.get('season')
    kind='prop-odds' if pick.get('athleteId') else 'odds'
    folder=Path(root)/'data'/kind
    if boxscores.verify(folder):return None
    path=folder/f'{league}-{season}.jsonl'
    quotes=[]
    for row in boxscores.read_store(path):
        if row.get('gameId') not in (pick.get('gameIds') or []):continue
        side=pick.get('direction');market=pick.get('market') or pick.get('marketType')
        if pick.get('athleteId'):
            import re
            name=pick.get('player') or re.split(r'\s+(?:OVER|UNDER)\b',pick.get('title',''),flags=re.I)[0]
            for book,line,over,under in build_site.price_quotes(row,market,name,pick.get('line')):
                odds,other=(over,under) if side=='over' else (under,over)
                quotes.append(dict(book=book,line=line,direction=side,odds=odds,otherOdds=other,
                    retrievedAt=row.get('retrievedAt'),source=row.get('source')))
        else:
            for book,b in (row.get('books') or {}).items():
                q=b.get(market) or {}
                if market=='total':
                    line=q.get('line');odds=q.get(side);other=q.get('under' if side=='over' else 'over')
                elif market=='spread' and finite(q.get('home')):
                    line=q['home'] if side=='home' else -q['home']
                    odds=q.get(side+'Price');other=q.get(('away' if side=='home' else 'home')+'Price')
                elif market=='moneyline':
                    line=0;odds=q.get(side);other=q.get('away' if side=='home' else 'home')
                else:continue
                quotes.append(dict(book=book,line=line,direction=side,odds=odds,otherOdds=other,
                    retrievedAt=row.get('retrievedAt'),source=row.get('source')))
    return price_comparison(pick,quotes,now)


def publication_issues(pick):
    """Final caption guard complements the live selection/release recheck."""
    if pick.get('lane')!='chef_pick':return []
    probability=pick.get('probabilityAtPublication') or {}
    clock=instant(pick.get('publishedAt')) or instant(probability.get('evaluatedAt')) or instant(pick.get('quotedAt'))
    if clock and clock<FROM:return []
    proof=pick.get('chefEvidence') or {}
    valid=(proof.get('policy')==VERSION and proof.get('ok') is True
           and finite(proof.get('n')) and proof['n']>=MINIMUM
           and proof.get('probabilitySpec') and proof.get('probabilitySpec')==probability.get('probabilitySpec')
           and finite(proof.get('conservativeChance')) and finite(pick.get('odds')) and abs(pick['odds'])>=100
           and proof['conservativeChance']>pricing.break_even(pick['odds'])
           and finite(proof.get('modelBrier')) and finite(proof.get('marketBrier'))
           and proof['modelBrier']<proof['marketBrier']
           and instant(proof.get('evaluatedAt')) and clock and instant(proof['evaluatedAt'])<=clock)
    return [] if valid else ['Chef forward probability evidence is missing or does not support this price']
