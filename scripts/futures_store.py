"""Append-only PAPER futures quotes, movements and book-sourced settlements.

No feed requests, automatic selection or official-play admission. Import an exact
sourced JSON observation with `python scripts/futures_store.py add observation.json`.
`report` prints current paper watches. Source/price absence is an error, not a guess.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import boxscores

STORE=Path(__file__).resolve().parents[1]/'data/futures'
LEAGUES={'NFL','CFB','NBA','WNBA','CBB','MLB','NHL','EPL','MLS'}


def read(root=STORE):
    problems=boxscores.verify(Path(root)) if Path(root).exists() else []
    if problems: raise ValueError('Futures integrity check failed: '+'; '.join(problems))
    return boxscores.read_store(Path(root)/'paper.jsonl') if (Path(root)/'paper.jsonl').exists() else []


def append(row, root=STORE, now=None):
    now=now or datetime.now(timezone.utc)
    old=read(root)
    if not isinstance(row,dict) or row.get('type') not in ('quote','settlement'): raise ValueError('quote or settlement required')
    required=('watchId','league','season','market','selection','book','jurisdiction','source','observedAt')
    if any(not isinstance(row.get(k),str) or not row[k].strip() for k in required): raise ValueError('Complete source and market identity required')
    if row['league'] not in LEAGUES or not row['source'].startswith('https://'): raise ValueError('Supported league and HTTPS evidence required')
    seen=datetime.fromisoformat(row['observedAt'].replace('Z','+00:00'))
    if seen.tzinfo is None or seen>now: raise ValueError('Observation must be timestamped and not in the future')
    mine=[r for r in old if r['watchId']==row['watchId']]
    identity=('league','season','market','selection','book','jurisdiction')
    if mine and any(row[k]!=mine[0][k] for k in identity): raise ValueError('Watch identity cannot change')
    if any(r['type']=='settlement' for r in mine): raise ValueError('Settled watch cannot be changed')
    if row['type']=='quote':
        odds=row.get('odds')
        if isinstance(odds,bool) or not isinstance(odds,(int,float)) or not math.isfinite(odds) or abs(odds)<100: raise ValueError('Exact American price required')
        if not isinstance(row.get('researchSnapshot'),dict) or not row['researchSnapshot']: raise ValueError('Save the research snapshot with the quote')
    elif not mine or row.get('result') not in ('win','loss','void') or not row.get('settlementEvidence'):
        raise ValueError('Existing watch and documented book settlement required; special cases stay pending')
    if mine and seen<datetime.fromisoformat(mine[-1]['observedAt'].replace('Z','+00:00')): raise ValueError('Observations must be chronological')
    item={k:row[k] for k in required+('type',)}
    for key in ('odds','researchSnapshot','result','settlementEvidence'):
        if key in row:item[key]=row[key]
    item['paper']=True
    digest=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()
    if any(r.get('id')==digest for r in old): return False
    item.update(id=digest,recordedAt=boxscores.stamp(now))
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    boxscores.append(root/'paper.jsonl',[item])
    boxscores.write_json(root/'ledger.json',boxscores.ledger(root))
    return True


def report(root=STORE):
    groups={}
    for row in read(root): groups.setdefault(row['watchId'],[]).append(row)
    return [{'watchId':key,'first':rows[0],'latest':rows[-1],'observations':len(rows)} for key,rows in groups.items()]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('add','report'));parser.add_argument('file',nargs='?')
    args=parser.parse_args()
    if args.action=='add':
        if not args.file: parser.error('an observation JSON file is required')
        print('appended' if append(json.loads(Path(args.file).read_text())) else 'already recorded')
    else: print(json.dumps(report(),indent=2))
