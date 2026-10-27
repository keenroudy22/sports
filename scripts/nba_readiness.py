"""NBA Trial activation and evidence gates.

The owner approved the labeled NBA Trial for opening night. Clean capture days
and private paper grades build promotion evidence; they do not delay that start.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import boxscores
import nba_capture
import paper

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'data' / 'policy' / 'nba.json'
EASTERN = ZoneInfo('America/New_York')


def policy(path=POLICY):
    return json.loads(Path(path).read_text())


def observations(root=nba_capture.STORE):
    return [row for path in (Path(root) / 'observations').glob('*.jsonl') for row in boxscores.read_store(path)]


def clean_days(root=nba_capture.STORE, config=None):
    """Count natural Eastern days containing every scheduled slot with clean free-feed evidence."""
    config = config or policy()
    expected = set(config['captureSlotsEastern'])
    by_day = defaultdict(set)
    for row in observations(root):
        if row.get('scheduled') is not True or row.get('errors') or (row.get('props') or {}).get('errors'):
            continue
        try:
            local = boxscores.instant(row['slot']).astimezone(EASTERN)
        except (KeyError, TypeError, ValueError):
            continue
        # Give the scheduler a small launch-delay tolerance but never backfill a missing slot.
        clock = min(expected, key=lambda value: abs((local.hour * 60 + local.minute) -
                                                     (int(value[:2]) * 60 + int(value[3:]))))
        target = int(clock[:2]) * 60 + int(clock[3:])
        if abs(local.hour * 60 + local.minute - target) <= 20:
            by_day[local.date().isoformat()].add(clock)
    return sorted(day for day, slots in by_day.items() if slots == expected)


def paper_rows(root=paper.STORE):
    return [row for row in paper.joined(root) if row.get('league') == 'NBA' and row.get('lean')]


def status(now=None, capture_root=nba_capture.STORE, paper_root=paper.STORE, config=None):
    now = now or datetime.now(timezone.utc)
    config = config or policy()
    days = clean_days(capture_root, config)
    rows = paper_rows(paper_root)
    graded = [row for row in rows if row.get('result') in ('win', 'loss', 'push')]
    clean_need = int(config['cleanCaptureDaysRequired'])
    paper_need = int(config['paperGradesRequired'])
    evidence_stage = 'log'
    if len(days) >= clean_need:
        evidence_stage = 'paper'
    if len(days) >= clean_need and len(graded) >= paper_need:
        evidence_stage = 'promotion-evidence'
    opening = datetime.fromisoformat(config['openingDate']).date()
    trial_open = now.astimezone(EASTERN).date() >= opening
    return {
        'stage': 'live-trial' if trial_open else evidence_stage,
        'evidenceStage': evidence_stage,
        'asOf': boxscores.stamp(now),
        'cleanCaptureDays': len(days),
        'cleanCaptureDaysRequired': clean_need,
        'lastCleanCaptureDay': days[-1] if days else None,
        'paperCandidates': len(rows),
        'paperGraded': len(graded),
        'paperGradesRequired': paper_need,
        'readyForLiveTrial': trial_open,
        'playerPropsReady': False,
        'quarterTicketsReady': False,
        'climbReady': False,
        'scope': 'Trial activation for qualified team markets; not proof that a bet qualifies or that player/quarter/Climb models are validated.',
        'readyForPromotionEvidence': evidence_stage == 'promotion-evidence',
        'trialOpensOn': config['openingDate'],
        'source': config['source'],
        'books': config['books'],
        'markets': config['markets'],
    }


def live_ready(now=None, **kwargs):
    return status(now, **kwargs)['readyForLiveTrial']
