"""Observed shortlist performance used by the October 9 selection plan."""
import json
from collections import defaultdict
from pathlib import Path

import pricing

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'learning'
SINCE = '2026-09-17'
MIN_N = 30


def key(row):
    game = (row.get('gameIds') or [None])[0]
    subject = str(row.get('athleteId') or '')
    market = row.get('market') or row.get('marketType') or 'unknown'
    return game, subject, market, row.get('direction')


def market_kind(row):
    if row.get('athleteId'):
        return 'prop'
    return {'total': 'total', 'spread': 'spread', 'moneyline': 'ML'}.get(row.get('marketType'),
                                                                         row.get('marketType') or 'unknown')


def gap_band(gap):
    if gap < 6:
        return '3-6'
    if gap < 12:
        return '6-12'
    if gap < 20:
        return '12-20'
    return '20-25'


def distinct(rows):
    """Latest decision per game/player/market/side, after the dated window."""
    latest = {}
    for row in rows:
        if str(row.get('decidedAt') or '')[:10] < SINCE or row.get('kind') == 'parlay':
            continue
        if not isinstance(row.get('odds'), (int, float)) or not -160 <= row['odds'] <= 150:
            continue
        prior = latest.get(key(row))
        if prior is None or str(row.get('decidedAt') or '') >= str(prior.get('decidedAt') or ''):
            latest[key(row)] = row
    return list(latest.values())


def load(root=STORE):
    candidates, grades = [], {}
    for path in sorted(Path(root).glob('candidates-*.jsonl')):
        candidates.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
    for path in sorted(Path(root).glob('graded-*.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row = json.loads(line)
                grades[row['id']] = row
    out = []
    for row in distinct(candidates):
        grade = grades.get(row.get('id'))
        if not grade or grade.get('result') not in ('win', 'loss'):
            continue
        fair = row.get('fairChance')
        if not isinstance(fair, (int, float)):
            fair = row.get('breakEven')
        raw = row.get('rawChance')
        if not isinstance(fair, (int, float)) or not isinstance(raw, (int, float)):
            continue
        out.append(dict(row, result=grade['result'], gradedAt=grade.get('gradedAt'),
                        fairChance=float(fair), gap=100 * (float(raw) - float(fair))))
    return out


def levels(row):
    league, market, side = row.get('league'), row.get('market') or row.get('marketType'), row.get('direction')
    kind = market_kind(row)
    return ((league, market, side, gap_band(float(row.get('gap') or 0))),
            (league, market, side), (league, market), (league, kind))


def summarize(rows, candidate, minimum=MIN_N):
    """First fallback level with enough graded rows, with a fair-anchored prior."""
    for wanted in levels(candidate):
        group = [row for row in rows if wanted in levels(row)]
        if len(group) < minimum:
            continue
        wins = sum(row['result'] == 'win' for row in group)
        fair = sum(row['fairChance'] for row in group) / len(group)
        hit = (wins + 20 * fair) / (len(group) + 20)
        edge = max(-8.0, min(8.0, 100 * (hit - pricing.break_even(candidate['odds']))))
        return {'level': list(wanted), 'n': len(group), 'wins': wins, 'meanFair': fair,
                'spotHit': hit, 'spotEdge': edge}
    return None


_CACHE = None


def for_candidate(candidate, rows=None):
    global _CACHE
    if rows is None:
        if _CACHE is None:
            _CACHE = load()
        rows = _CACHE
    return summarize(rows, candidate)
