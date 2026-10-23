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
        groups[(row['model'], row['stat'])].append((row, outcome))
    segments = []
    graded = []
    for (model, stat), pairs in sorted(groups.items()):
        graded.extend(pairs)
        segments.append(dict(model=model, stat=stat, observations=len(pairs),
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
    lines.append('- '+report['decision'])
    return '\n'.join(lines)+'\n'
