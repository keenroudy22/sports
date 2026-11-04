"""Cached proof of the morning NBA capture, never model approval or a new job."""
import json
from datetime import datetime,time,timedelta
from pathlib import Path
import boxscores
from gates import EASTERN


def status(root,now):
    root=Path(root);day=now.astimezone(EASTERN).date()
    start=datetime.combine(day,time(8,30),EASTERN)
    deadline=datetime.combine(day,time(9),EASTERN)
    result=dict(state='unknown',deadline=boxscores.stamp(deadline),issues=[],
                scope='Real morning capture and source recovery only; not prop validation or delivery proof')
    def issue(state,code,message):
        result.update(state=state)
        if now>=deadline:result['issues'].append(dict(code=code,message=message))
        return result
    try:
        if (root/'slate.json').stat().st_size>1_000_000:return dict(result,state='unavailable')
        slate=json.loads((root/'slate.json').read_text())
        if not any(boxscores.instant(g['kickoff']).astimezone(EASTERN).date()==day for g in slate.get('games',[])):
            return dict(result,state='no-current-slate')
        if any(boxscores.verify(root/f) for f in ('observations','source-completions')):
            return issue('invalid','nba-morning-integrity','NBA morning capture evidence failed integrity checks.')
        read=lambda f:[r for p in sorted((root/f).glob('*.jsonl')) for r in boxscores.read_store(p)]
        captures=[]
        for r in read('observations'):
            try:
                at=boxscores.instant(r['slot']);received=boxscores.instant(r['retrievedAt'])
                if r.get('scheduled') is True and start<=at<=start+timedelta(minutes=20) and at<=received<=now:
                    captures.append(r)
            except (ValueError,TypeError,KeyError):continue
        if not captures:
            return issue('missing' if now>=deadline else 'awaiting','nba-morning-missing','No actual 8:30 AM NBA capture is recorded by the 9 AM deadline.')
        capture=max(captures,key=lambda r:(r['slot'],r['retrievedAt']))
        result.update(slot=capture['slot'],capturedAt=capture['retrievedAt'],attempts=len(captures))
        errors=set(capture.get('errors') or [])
        if errors-{'official-availability-unavailable'} or (capture.get('props') or {}).get('errors'):
            return issue('capture-failed','nba-morning-failed','The morning NBA capture recorded source errors; an overall successful job is not recovery proof.')
        if not errors:
            if boxscores.instant(capture['retrievedAt'])>deadline:
                return issue('capture-late','nba-morning-late','NBA morning capture completed after the 9 AM deadline.')
            return dict(result,state='capture-recorded')
        completions=[]
        for r in read('source-completions'):
            try:
                if (r.get('state')=='completed' and r.get('scheduledSlot')==capture['slot']
                        and boxscores.instant(capture['retrievedAt'])<=boxscores.instant(r['reportObservedAt'])
                        <=boxscores.instant(r['retrievedAt'])<=now):completions.append(r)
            except (KeyError,TypeError,ValueError):continue
        if not completions:
            return issue('source-recovery-needed','nba-morning-source','Morning NBA official-report recovery has no completion receipt by 9 AM.')
        done=min(completions,key=lambda r:r['retrievedAt'])
        result.update(completedAt=done['retrievedAt'],forwardRecorded=done.get('forwardRecorded'),
                      probabilityRecorded=done.get('probabilityRecorded'))
        if boxscores.instant(done['retrievedAt'])>deadline:
            return issue('recovered-late','nba-morning-late','NBA morning source recovery completed after the 9 AM deadline.')
        return dict(result,state='recovered')
    except (OSError,ValueError,KeyError,TypeError):
        return dict(result,state='unavailable')
