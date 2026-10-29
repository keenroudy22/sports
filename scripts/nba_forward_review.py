"""Read-only forward prop comparison. No fitting, bet selection or policy changes.

Choose the earliest pregame forecast per player/game/stat/model BEFORE looking
for its outcome. Multiple books cannot inflate the sample or select a winner.
Report each stat separately; different stats for one player remain correlated.
"""
import math
from collections import defaultdict
from itertools import combinations
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import boxscores

EASTERN = ZoneInfo('America/New_York')


def game_day(row):
    """Use the desk's Eastern kickoff day, including games after UTC midnight."""
    return boxscores.instant(row['kickoff']).astimezone(EASTERN).date().isoformat()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def paired_models(graded):
    """Compare model errors on identical pregame capture cohorts, not separate samples.

    Sides and wins never select the cohort. Missing pairs, different quote clocks,
    and disagreeing actuals are excluded; no significance or promotion is inferred.
    """
    subjects = defaultdict(dict)
    for row, outcome in graded:
        key = (row['eventId'], row['athleteId'], row['stat'], row.get('season', 0))
        subjects[key][row['model']] = (row, outcome)
    groups = defaultdict(list)
    for key, models in subjects.items():
        for a, b in combinations(sorted(models), 2):
            left, right = models[a], models[b]
            fields = ('retrievedAt', 'kickoff', 'book', 'line')
            if any(left[0].get(f) != right[0].get(f) for f in fields):
                continue
            if left[1]['actual'] != right[1]['actual']:
                continue
            groups[(a, b, key[2], key[3])].append((left, right))
    result = []
    for (a, b, stat, season), pairs in sorted(groups.items()):
        error = lambda item: abs(item[1]['actual'] - item[0]['projection']['value'])
        result.append(dict(modelA=a, modelB=b, stat=stat, season=season,
            comparisons=len(pairs), games=len({p[0][0]['eventId'] for p in pairs}),
            playerGames=len({(p[0][0]['eventId'], p[0][0]['athleteId']) for p in pairs}),
            modelAMAE=round(mean(error(p[0]) for p in pairs), 3),
            modelBMAE=round(mean(error(p[1]) for p in pairs), 3)))
    return result


def reviewed_minutes(graded):
    """The reviewed forecast already freezes its unchanged baseline at that clock.

    Compare those exact saved values; never reconstruct an earlier baseline using
    today's boxes or invent the baseline's side/price/return.
    """
    groups = defaultdict(list)
    for row, outcome in graded:
        p = row['projection']
        if row['model'] not in ('nba-minutes-rate-reviewed-v1', 'nba-current-role-minutes-shadow-v1') or not number(p.get('baselineValue')):
            continue
        if not number(p.get('baselineMinutes')) or not 0 < p['baselineMinutes'] <= 60:
            continue
        groups[(row['model'], row['stat'], row.get('season', 0))].append((row, outcome))
    out = []
    for (model, stat, season), pairs in sorted(groups.items()):
        out.append(dict(model=model, stat=stat, season=season, comparisons=len(pairs),
            games=len({r['eventId'] for r, _ in pairs}),
            baselineMAE=round(mean(abs(o['actual']-r['projection']['baselineValue']) for r,o in pairs), 3),
            reviewedMAE=round(mean(abs(o['actual']-r['projection']['value']) for r,o in pairs), 3)))
    return out


def priced_check(pairs):
    """A flat 1u shadow check at the frozen side/price, never a public record."""
    hits = misses = pushes = excluded = 0
    net = 0.0
    for row, outcome in pairs:
        odds, side = row.get('odds'), row.get('side')
        if (side not in ('over', 'under') or not number(odds) or abs(odds) < 100
                or outcome.get('side') != side or outcome.get('odds') != odds):
            excluded += 1
            continue
        result = 'push' if outcome['actual'] == row['line'] else (
            'hit' if (outcome['actual'] > row['line']) == (side == 'over') else 'miss')
        if outcome['result'] != result:
            excluded += 1
            continue
        if result == 'hit':
            hits += 1
            net += odds / 100 if odds > 0 else 100 / -odds
        elif result == 'miss':
            misses += 1
            net -= 1
        else:
            pushes += 1
    n = hits + misses + pushes
    return dict(hits=hits, misses=misses, pushes=pushes, excluded=excluded,
                netPerUnitStaked=round(net / n, 4) if n else None,
                shadowNetUnits=round(net, 3), observations=n)


def independent_check(pairs):
    """One equal-weight observation per game; correlated players cannot inflate confidence."""
    by_game = defaultdict(list)
    for row, outcome in pairs:
        by_game[row['eventId']].append((row, outcome))
    differences = []
    priced = []
    days = set()
    for group in by_game.values():
        days.add(game_day(group[0][0]))
        differences.append(mean(abs(o['actual']-r['line'])-abs(o['actual']-r['projection']['value']) for r,o in group))
        checks = [priced_check([(r,o)]) for r,o in group]
        values = [c['shadowNetUnits'] for c in checks if c['observations']]
        if values:
            priced.append(mean(values))
    return dict(games=len(by_game),gameDays=len(days),
        meanErrorImprovement=round(mean(differences),3) if differences else None,
        pricedGames=len(priced),gameBalancedShadowReturn=round(mean(priced),4) if priced else None,
        trialEligible=False,holds=['No validated NBA prop probability or approved prop admission adapter',
          'Independent forward evidence must support each market and model before promotion'],
        scope='Equal game weights, not independent players or a placed-bet portfolio')


def summarize(forecasts, outcomes, now=None):
    now = now or datetime.now(timezone.utc)
    chosen, final = {}, {}
    rejected = 0
    for row in forecasts:
        try:
            at, kickoff = boxscores.instant(row['retrievedAt']), boxscores.instant(row['kickoff'])
            if not at < kickoff or at > now or not number(row['projection']['value']) or not number(row['line']):
                raise ValueError('invalid pregame forecast')
            key = (row['eventId'], row['athleteId'], row['stat'], row['model'])
            rank = (at, row['book'], row['id'])
            if key not in chosen or rank < chosen[key][0]:
                chosen[key] = (rank, row)
        except (KeyError, TypeError, ValueError):
            rejected += 1
    for row in outcomes:
        try:
            at = boxscores.instant(row['retrievedAt'])
            if at <= now and (row['id'] not in final or at > final[row['id']][0]):
                final[row['id']] = (at, row)
        except (KeyError, TypeError, ValueError):
            rejected += 1
    groups = defaultdict(list)
    missing = 0
    for _, row in chosen.values():
        entry = final.get(row['id'])
        if not entry:
            missing += 1
            continue
        at, outcome = entry
        if (at < boxscores.instant(row['kickoff']) or not outcome.get('source')
                or outcome.get('forecastAt') != row['retrievedAt']
                or outcome.get('model') != row['model']
                or outcome.get('line') != row['line'] or outcome.get('book') != row['book']
                or outcome.get('projection') != row['projection']['value']
                or not number(outcome.get('actual'))
                or outcome.get('result') not in ('hit', 'miss', 'push')):
            missing += 1
            continue
        groups[(row['model'], row['stat'], row.get('season', 0))].append((row, outcome))
    segments = []
    graded = []
    for (model, stat, season), pairs in sorted(groups.items()):
        graded.extend(pairs)
        segments.append(dict(model=model, stat=stat, season=season, observations=len(pairs),
            pricedShadow=priced_check(pairs), independentCheck=independent_check(pairs),
            games=len({r['eventId'] for r, _ in pairs}),
            gameDays=len({game_day(r) for r, _ in pairs}),
            modelMAE=round(mean(abs(o['actual']-r['projection']['value']) for r, o in pairs), 3),
            lineMAE=round(mean(abs(o['actual']-r['line']) for r, o in pairs), 3)))
    return dict(selected=len(chosen), graded=len(graded), missingOrUnusable=missing,
        rejected=rejected, games=len({r['eventId'] for r, _ in graded}),
        playerGames=len({(r['eventId'], r['athleteId']) for r, _ in graded}),
        segments=segments, pairedModels=paired_models(graded), reviewedMinutes=reviewed_minutes(graded),
        decision='Research only; no automatic promotion or weight change.')


def from_stores(root, now=None):
    def read(folder):
        return [r for p in sorted((Path(root)/folder).glob('*.jsonl')) for r in boxscores.read_store(p)]
    report = summarize(read('player-forecasts'), read('player-outcomes'), now)
    import nba_prop_probability
    report['probabilityStudy'] = nba_prop_probability.review(Path(root), now or datetime.now(timezone.utc))
    return report


def markdown(report):
    lines = ['## NBA prop forward check — research, not bets',
        f"- {report['graded']} player/game/stat comparisons from {report['games']} games and {report['playerGames']} player-games; {report['missingOrUnusable']} selected forecasts have no usable outcome.",
        '- Earliest pregame quote chosen before grading; repeated books excluded. Stats within a player/game remain correlated.',
        '- Average absolute error below is in each stat’s own units; smaller is better. A line is a market benchmark, not necessarily a mean forecast. This is not profitability or proof of an edge.']
    for row in report['segments']:
        lines.append(f"- {row['stat']} ({row['model']}): {row['observations']} comparisons / {row['games']} games; model error {row['modelMAE']:g}, quoted-line error {row['lineMAE']:g}.")
        check = row['independentCheck']
        lines.append(f"  Equal-game check: {check['games']} games / {check['gameDays']} Eastern dates; line-error improvement {check['meanErrorImprovement']}; game-balanced frozen-price return {check['gameBalancedShadowReturn']}. No approved prop probability/admission adapter; research only.")
        price = row['pricedShadow']
        lines.append(f"  Season {row['season'] or 'unknown'} · frozen-side shadow {price['hits']}-{price['misses']}-{price['pushes']}, {price['shadowNetUnits']:+g} hypothetical units at 1u each; {price['excluded']} lack consistent side/price evidence. Not placed bets; overlapping player exposure is not a staking portfolio.")
    for row in report.get('pairedModels', []):
        lines.append(f"- Matched {row['stat']} / season {row['season']}: {row['modelA']} error {row['modelAMAE']:g} vs {row['modelB']} {row['modelBMAE']:g}; {row['comparisons']} comparisons across {row['games']} games. Same pregame capture time, book and line; sides/results did not select the cohort. Small and correlated samples do not establish improvement.")
    if not report.get('pairedModels'):
        lines.append('- No identical-capture model pairs available; separate model samples do not establish improvement.')
    for row in report.get('reviewedMinutes', []):
        lines.append(f"- Frozen minutes comparison {row['stat']} / season {row['season']} / {row['model']}: unchanged baseline error {row['baselineMAE']:g}, reviewed minutes error {row['reviewedMAE']:g}; {row['comparisons']} comparisons / {row['games']} games. Both values saved inside the same pregame forecast; no reconstructed baseline price or returns. Not promotion evidence by itself.")
    for row in report.get('probabilityStudy', []):
        lines.append(f"- Prospective probability study {row['stat']}: {row['games']} untouched games / {row['easternDates']} Eastern dates; equal-game squared-probability error improvement vs fair market {row['brierImprovement']} (date-cluster lower estimate {row.get('brierImprovementLower95')}). Frozen positive-price raw-stat benchmark: {row.get('pricedGames',0)} games, return {row.get('rawStatShadowReturn')}, lower estimate {row.get('rawStatReturnLower95')}. Holds: {'; '.join(row.get('evidenceHolds',[])) or 'Official settlement and reviewed publishing adapter still required'}. Not settled bets or public admission.")
    lines.append('- '+report['decision'])
    return '\n'.join(lines)+'\n'
