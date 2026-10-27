"""Unpromoted minutes experiment using only role evidence frozen at capture.

No injury redistribution, coach restriction, probability, admission or feed call.
The control is saved inside each candidate so different capture clocks cannot
masquerade as an improvement. Replays are diagnostics, never forward records.
"""
import math
import statistics
from datetime import timedelta

import boxscores

VERSION = 'nba-current-role-minutes-shadow-v1'
BASELINE = 'nba-minutes-rate-v1'


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def adjust(row, captured_at):
    p, role = row.get('projection') or {}, row.get('currentRole') or {}
    if row.get('hold') or p.get('model') != BASELINE:
        return None
    try:
        at = boxscores.instant(captured_at)
        kickoff = boxscores.instant(row['kickoff'])
        received = boxscores.instant(role['receivedAt'])
        played = boxscores.instant(role['asOf'])
        if not played < received <= at < kickoff or at-played > timedelta(days=7):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    minutes = role.get('minutes')
    if (not isinstance(minutes, list) or len(minutes) != 3 or role.get('games') != 3
            or any(not finite(v) or not 12 <= v <= 48 for v in minutes)
            or type(role.get('starts')) is not int or role['starts'] not in (0, 3)):
        return None  # A changed/unknown starting role needs an actual review.
    old = p.get('minutes')
    if (not finite(old) or not 12 <= old <= 40
            or any(not finite(p.get(k)) or p[k] < 0 for k in ('value','low','high'))):
        return None
    estimate = min(40, statistics.median(minutes))
    ratio = estimate/old
    if not .7 <= ratio <= 1.3:
        return None  # Do not automate a major change in role.
    return dict(p, model=VERSION, minutes=estimate,
        value=round(p['value']*ratio,1), low=round(p['low']*ratio,1),
        high=round(p['high']*ratio,1), baselineValue=p['value'],
        baselineMinutes=old, baselineModel=BASELINE,
        minutesBasis='observed-recent-median', roleEvidenceAt=role['receivedAt'],
        analysisOnly=True, admissionReady=False)
