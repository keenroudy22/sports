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


def capture_slots(day, config):
    """Use the schedule actually assigned to that Eastern day, never today's retroactively."""
    slots = config['captureSlotsEastern']
    for change in sorted(config.get('captureScheduleHistory', []), key=lambda r: r['effectiveDate']):
        if day >= change['effectiveDate']:
            slots = change['slots']
    return set(slots)


def clean_days(root=nba_capture.STORE, config=None, now=None):
    """Count real completed scheduled captures available at the evaluation clock."""
    config = config or policy()
    now = now or datetime.now(timezone.utc)
    by_day = defaultdict(set)
    for row in observations(root):
        if row.get('scheduled') is not True or row.get('errors') or (row.get('props') or {}).get('errors'):
            continue
        try:
            at = boxscores.instant(row['slot'])
            received = boxscores.instant(row['retrievedAt'])
            if at > now or received > now or received < at:
                continue
            local = at.astimezone(EASTERN)
            expected = capture_slots(local.date().isoformat(), config)
            if not expected:
                continue
            clock = min(expected, key=lambda value: abs((local.hour * 60 + local.minute) -
                         (int(value[:2]) * 60 + int(value[3:]))))
            target = int(clock[:2]) * 60 + int(clock[3:])
            if abs(local.hour * 60 + local.minute - target) <= 20:
                by_day[local.date().isoformat()].add(clock)
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(day for day, slots in by_day.items() if slots == capture_slots(day, config))


def paper_rows(root=paper.STORE, now=None):
    """Join only evidence already available, retaining earlier grades before later corrections."""
    now = now or datetime.now(timezone.utc)
    out = []
    for path in sorted(Path(root).glob('*.jsonl')):
        rows = boxscores.read_store(path)
        grades = {}
        for row in rows:
            if row.get('type') != 'grade':
                continue
            try:
                clock = boxscores.instant(row['gradedAt'])
                if clock <= now and (row['gameId'] not in grades or clock >= grades[row['gameId']][0]):
                    grades[row['gameId']] = (clock, row)
            except (KeyError, TypeError, ValueError):
                continue
        for row in rows:
            if row.get('type') != 'record' or row.get('league') != 'NBA' or not row.get('lean'):
                continue
            try:
                captured = boxscores.instant(row['capturedAt'])
                kickoff = boxscores.instant(row['kickoff'])
                if captured > now or captured >= kickoff:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            grade = grades.get(row['gameId'])
            if grade and grade[0] >= kickoff:
                out.append(dict(row, **{k:v for k,v in grade[1].items() if k not in ('type','gameId')}))
            else:
                out.append(row)
    return out


def status(now=None, capture_root=nba_capture.STORE, paper_root=paper.STORE, config=None):
    now = now or datetime.now(timezone.utc)
    config = config or policy()
    days = clean_days(capture_root, config, now)
    rows = paper_rows(paper_root, now)
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
