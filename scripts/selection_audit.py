"""Read-only owner research audit. Never changes picks, models, staking or feeds."""
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import desk_performance,nba_forward_review,social_learning
ROOT=Path(__file__).resolve().parents[1]

def audit(root=ROOT,now=None):
 root=Path(root);now=now or datetime.now(timezone.utc)
 record=json.loads((root/'site/data/app/record.json').read_text())
 official=desk_performance.report(record['picks'],now)
 totals=defaultdict(lambda:dict(wins=0,losses=0,units=0.,recordUnits=0.,riskedUnits=0.,plays=0))
 for s in official['segments']:
  for key in ('ALL',s['league'],s['marketFamily'],s['league']+'/'+s['market']):
   a=totals[key]
   for field in a:a[field]+=s[field]
 for a in totals.values():
  for field in ('units','recordUnits','riskedUnits'):a[field]=round(a[field],3)
  a['capturedPriceROI']=round(a['units']/a['riskedUnits'],5) if a['riskedUnits'] else None
 learning=json.loads((root/'data/learning/report.json').read_text())
 return dict(asOf=now.isoformat(),sourceGeneratedAt=record.get('generatedAt'),official=official,
  aggregates=dict(totals),nba=nba_forward_review.from_stores(root/'data/nba-capture',now),
  social=social_learning.comparable_themes(json.loads((root/'data/x-posted.json').read_text()),now),
  calibrationResearch=learning.get('calibration',[]),calibrationResearchAt=learning.get('at'),
  limits=['Captured-price units exclude promotions; recordUnits retain the existing public arithmetic.',
          'Priced historical imports are record history, not timestamped prospective model validation.',
          'Segments and creative comparisons are observational, often small and correlated; no automatic selection changes.',
          'NBA actual-minutes attribution uses postgame information, never a deployable forecast or admission proof.'])

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path)
 args=p.parse_args();report=audit(args.root)
 if args.out:
  target=args.out.resolve()
  # Research diagnostics never replace any public/authoritative input family.
  allowed=ROOT/'work'
  if not target.is_relative_to(allowed):p.error('--out must be inside the development work/ directory')
  target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2)+'\n')
 else:print(json.dumps(report,indent=2))
