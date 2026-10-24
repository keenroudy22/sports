"""Read-only forward prop comparison. No fitting, bet selection or policy changes.

Choose the earliest pregame forecast per player/game/stat/model BEFORE looking
for its outcome. Multiple books cannot inflate the sample or select a winner.
Report each stat separately; different stats for one player remain correlated.
"""
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import boxscores


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


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
            pricedShadow=priced_check(pairs),
            games=len({r['eventId'] for r, _ in pairs}),
            gameDays=len({r['kickoff'][:10] for r, _ in pairs}),
            modelMAE=round(mean(abs(o['actual']-r['projection']['value']) for r, o in pairs), 3),
            lineMAE=round(mean(abs(o['actual']-r['line']) for r, o in pairs), 3)))
    return dict(selected=len(chosen), graded=len(graded), missingOrUnusable=missing,
        rejected=rejected, games=len({r['eventId'] for r, _ in graded}),
        playerGames=len({(r['eventId'], r['athleteId']) for r, _ in graded}),
        segments=segments, decision='Research only; no automatic promotion or weight change.')


def from_stores(root, now=None):
    def read(folder):
        return [r for p in sorted((Path(root)/folder).glob('*.jsonl')) for r in boxscores.read_store(p)]
    return summarize(read('player-forecasts'), read('player-outcomes'), now)


def markdown(report):
    lines = ['## NBA prop forward check — research, not bets',
        f"- {report['graded']} player/game/stat comparisons from {report['games']} games and {report['playerGames']} player-games; {report['missingOrUnusable']} selected forecasts have no usable outcome.",
        '- Earliest pregame quote chosen before grading; repeated books excluded. Stats within a player/game remain correlated.',
        '- Average absolute error below is in each stat’s own units; smaller is better. A line is a market benchmark, not necessarily a mean forecast. This is not profitability or proof of an edge.']
    for row in report['segments']:
        lines.append(f"- {row['stat']} ({row['model']}): {row['observations']} comparisons / {row['games']} games; model error {row['modelMAE']:g}, quoted-line error {row['lineMAE']:g}.")
        price = row['pricedShadow']
        lines.append(f"  Season {row['season'] or 'unknown'} · frozen-side shadow {price['hits']}-{price['misses']}-{price['pushes']}, {price['shadowNetUnits']:+g} hypothetical units at 1u each; {price['excluded']} lack consistent side/price evidence. Not placed bets; overlapping player exposure is not a staking portfolio.")
    lines.append('- '+report['decision'])
    return '\n'.join(lines)+'\n'
