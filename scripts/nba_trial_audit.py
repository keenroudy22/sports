"""Reconcile the separate NBA Trial public record against its append-only publications."""
import json
from pathlib import Path
import boxscores
import nba_trial
import nba_trial_runtime as runtime


def audit(payload,root=nba_trial.STORE):
 issues=list(boxscores.verify(root));saved=runtime.rows(root)
 pub=[r for r in saved if r.get('type')=='publish'];ids=set();days={};events=set()
 for p in pub:
  day=boxscores.instant(p['kickoff']).astimezone(nba_trial.EASTERN).date()
  if p['id'] in ids:issues.append('published ID rewritten')
  published=boxscores.instant(p['publishedAt'])
  ordinary=nba_trial.nba_pick_policy.active(published)
  days.setdefault(day,[]).append(p)
  if ordinary and (day,p.get('eventId')) in events:issues.append('more than one NBA pick per game')
  if ordinary and p.get('series')!='NBA Picks':issues.append('new NBA pick category mismatch')
  if p.get('riskUnits')!=nba_trial.staking.expected(p) or p.get('league')!='NBA':issues.append('stake/league mismatch')
  ids.add(p['id']);events.add((day,p.get('eventId')))
 for day,plays in days.items():
  limit=max(nba_trial.nba_pick_policy.daily_cap(boxscores.instant(p['publishedAt'])) for p in plays)
  if len(plays)>limit:issues.append('NBA daily pick cap exceeded')
 focus=runtime.current_plays(root);focusids={p['id'] for p in focus}
 expected=nba_trial.snapshot([r for r in saved if r.get('id') in focusids])
 actual=payload.get('trial',{}).get('record',{})
 for key in ('win','loss','push','graded','units'):
  if actual.get(key)!=expected[key]:issues.append('public NBA Trial '+key+' differs')
 visible={p['id'] for p in sorted(focus,key=lambda p:p['publishedAt'])[-20:]}
 if {p['id'] for p in payload.get('trial',{}).get('plays',[])}!=visible:issues.append('public NBA Trial IDs differ')
 return {'publicationsChecked':len(pub),'issues':issues}


if __name__=='__main__':
 path=Path(__file__).resolve().parents[1]/'site/data/app/nba.json'
 result=audit(json.loads(path.read_text()));print(json.dumps(result));raise SystemExit(bool(result['issues']))
