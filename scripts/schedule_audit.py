"""Offline schedule ownership audit. No provider calls or scheduler changes."""
import json
import plistlib
from pathlib import Path
import nba_readiness

OWNERS={
 'run':('Capture, research, selection and release','Scheduled game-day windows','status.json and run log'),
 'ladder':('Settle/prepare one current Climb; reuse13:30 NBA capture','10:00/13:30/16:00/20:00 Eastern','run log, Climb state and delivery receipts'),
 'results':('Official finals and settlement recovery','Minute25/55','Immutable result reports and delivery log'),
 'precheck':('Final checks on scheduled private tickets','Minute05/35 before send','Saved precheck or explicit veto'),
 'discord':('Reconcile delivery and mirror approved messages','Every5minutes','Provider IDs, sent timestamps and Discord IDs'),
 'heartbeat':('Change-only operational alerts','07:15 Eastern','heartbeat-state.json and material alerts'),
 'review':('Evidence-only weekly evaluation','Tuesday10:30 Eastern','Dated local review packet')}


def audit(root,installed=None):
 root=Path(root);installed=Path(installed or Path.home()/'Library/LaunchAgents')
 jobs=[];issues=[]
 for name,(purpose,deadline,receipt) in OWNERS.items():
  filename=f'com.keenroudy.sports.{name}.plist'
  source=root/'deployment/mac'/filename;target=installed/filename
  if not source.exists():issues.append(f'Missing source job {name}');continue
  expected=plistlib.loads(source.read_bytes())
  current=plistlib.loads(target.read_bytes()) if target.exists() else None
  if current!=expected:issues.append(f'Installed schedule differs: {name}')
  jobs.append(dict(name=name,purpose=purpose,deadline=deadline,receipt=receipt,installedMatches=current==expected))
 config=nba_readiness.policy(root/'data/policy/nba.json')
 actual={'06:45','08:30','11:45','13:30','17:30','21:00'}
 if nba_readiness.capture_slots('2026-10-28',config)!=actual:issues.append('NBA readiness and current capture windows disagree')
 workflow=(root/'.github/workflows/publish.yml').read_text()
 if "if: github.event_name != 'push'" not in workflow:issues.append('Hosted push must not recapture feeds')
 return dict(jobs=jobs,issues=issues,networkCalls=0,
  hosted=dict(purpose='Stored-evidence push publication; scheduled free score/forecast updates',receipt='Successful run plus live artifact'),
  app=dict(daily='07:45 delivery failures and highest-priority repair',overnight='00:45 settlement and current Eastern-day preparation',
           weekly='Tuesday11:00 measured changes after local review',
           rule='Existing jobs only. Resume repairs, no duplicate capture or broad repeated audit.'))

if __name__=='__main__':
 root=Path(__file__).resolve().parents[1];result=audit(root)
 print(json.dumps(result,indent=2));raise SystemExit(bool(result['issues']))
