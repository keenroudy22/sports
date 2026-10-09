"""Read-only NBA Today payload from free stored evidence; no feed call or play admission."""
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import boxscores
import espn_props
import nba_capture
import paper
import nba_trial

ROOT = Path(__file__).resolve().parents[1]
BOX = ROOT/'data'/'sport-box'
STAT_NAMES={'pts':'points','reb':'rebounds','ast':'assists','fg3m':'threes','pra':'points + rebounds + assists'}
FLOORS={'pts':15,'reb':5,'ast':4,'fg3m':2}


def read_json(path, fallback):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return fallback


def fresh(value, now, hours=4):
    try:
        return 0 <= (now-boxscores.instant(value)).total_seconds() <= hours*3600
    except (TypeError, ValueError):
        return False


def build(now=None, root=nba_capture.STORE, boxes=None, model_factory=None):
    now=now or datetime.now(timezone.utc); root=Path(root)
    slate=read_json(root/'slate.json',{})
    if boxes is None:
        boxes=list({r['eventId']:r for p in BOX.glob('nba-*.jsonl') for r in boxscores.read_store(p)}.values())
    injury_snapshot=read_json(root/'injuries-current.json',{})
    holds={r['athleteId'] for r in injury_snapshot.get('rows',[]) if r.get('status')}
    season=max((g.get('season',now.year+1) for g in slate.get('games',[])),default=now.year+1)
    latest={}
    for p in (root/'quotes').glob('*.jsonl'):
        for row in boxscores.read_store(p): latest[(row['eventId'],row['book'])]=row
    games=[]; models={}
    for game in sorted(slate.get('games',[]),key=lambda g:g['kickoff']):
        row={k:game[k] for k in ('id','providerId','season','seasonType','kickoff','status','teams','scores') if k in game}
        if game.get('status')=='scheduled' and game.get('seasonType') in ('regular-season','post-season'):
            try:
                if game['season'] not in models:
                    models[game['season']] = (model_factory or paper.model_for)('NBA',game['season'],now.timestamp())
                projection=models[game['season']].predict(game['teams']['home']['id'],game['teams']['away']['id'])
                if all(isinstance(projection.get(k),(float,int)) and math.isfinite(projection[k]) for k in ('margin','total')):
                    row['projection']={'home':round((projection['total']+projection['margin'])/2,1),
                                       'away':round((projection['total']-projection['margin'])/2,1),
                                       'total':round(projection['total'],1),'sparse':bool(projection.get('sparse')),
                                       'label':'Research projection'}
            except (OSError, ValueError, KeyError, TypeError):
                pass
        if game.get('status')=='scheduled' and boxscores.instant(game['kickoff'])>now:
            for book in ('DraftKings','FanDuel'):
                quote=latest.get((str(game['providerId']),book),{})
                total=(quote.get('current') or {}).get('total') or {}
                if not fresh(quote.get('retrievedAt'),now): continue
                try:
                    line=espn_props.number(total['line'])
                    if line<=0:continue
                    over,under=espn_props.price(total['over']),espn_props.price(total['under'])
                    if .99<=espn_props.implied(over)+espn_props.implied(under)<=1.15:
                        row['totalQuote']={'line':line,'over':over,'under':under,'book':book,'retrievedAt':quote['retrievedAt']}
                        break
                except (KeyError,TypeError,ValueError): pass
        games.append(row)
    logs=defaultdict(list)
    for box in sorted(boxes,key=lambda b:b['kickoff']):
        if box['seasonType']!=2 or boxscores.instant(box['kickoff'])>=now: continue
        for player in box.get('players',[]):
            if player.get('dnp'): continue
            logs[(box['season'],player['id'])].append({'name':player['name'],'team':player['team'],
                                                      'stats':player['stats'],'date':box['kickoff'][:10]})
    trend_season=season if any(s==season for s,_ in logs) else season-1
    trends=[]
    for (s,athlete),history in sorted(logs.items(),key=lambda p:(-len(p[1]),p[0])):
        if s!=trend_season or len(history)<3: continue
        for stat in ('pts','reb','ast'):
            window=history[-15:]
            if any(stat not in r['stats'] for r in window): continue
            values=[r['stats'][stat] for r in window]
            trends.append({'athleteId':athlete,'name':window[-1]['name'],'stat':stat,'statName':STAT_NAMES[stat],
                           'games':len(values),'average':round(sum(values)/len(values),1),
                           'values':values,'dates':[r['date'] for r in window],'season':s,
                           'window':'This season' if s==season else 'Last season · regular season'})
        if len(trends)>=12: break
    props={}
    for path in (root/'props').glob('*.jsonl'):
        for row in boxscores.read_store(path): props[(row['eventId'],row['athleteId'],row['stat'],row['line'])]=row
    prep=[]
    scheduled={str(g['providerId']):g for g in games if g['status']=='scheduled' and g['seasonType']=='regular-season'}
    for row in props.values():
        history=logs.get((season,row['athleteId']),[])
        if history:
            current_team=history[-1]['team']
            game=scheduled.get(row['eventId'],{})
            if current_team not in {t.get('id') for t in game.get('teams',{}).values()}:continue
            history=[h for h in history if h['team']==current_team]
        if (row['eventId'] not in scheduled or row['athleteId'] in holds or not row.get('sideVerified')
                or not fresh(row.get('retrievedAt'),now) or not fresh(injury_snapshot.get('retrievedAt'),now)
                or len(history)<5 or row['stat'] not in FLOORS or math.floor(row['line'])+1<FLOORS[row['stat']]
                or abs(row.get('over',0))>400 or abs(row.get('under',0))>400): continue
        recent=history[-5:];stat=row['stat']
        if any(stat not in r['stats'] or 'min' not in r['stats'] for r in recent): continue
        hits=sum(r['stats'][stat]>row['line'] for r in recent)
        minutes=[r['stats']['min'] for r in recent]
        if hits<4 or any(r['stats'][stat]<=row['line'] for r in recent[-3:]) or min(minutes[-3:]) < .7*sum(minutes)/5: continue
        if not boxscores.instant(row['kickoff'])>now: continue
        prep.append({'name':recent[-1]['name'],'stat':stat,'statName':STAT_NAMES[stat],'line':row['line'],'over':row['over'],
                     'book':row['book'],'hits':hits,'games':5,'label':'Research','kickoff':row['kickoff']})
    trial_rows=[r for p in nba_trial.STORE.glob('*.jsonl') for r in boxscores.read_store(p)]
    trial_record=nba_trial.snapshot(trial_rows)
    return {'league':'NBA','generatedAt':boxscores.stamp(now),'season':season,
            'heading':'Opening night · October 20' if nba_capture.sports_refresh.eastern_date(now).isoformat() < '2026-10-20' else 'NBA Today',
            'sourceAt':slate.get('retrievedAt'),'scheduleFresh':fresh(slate.get('retrievedAt'),now,24),
            'games':games,'trends':trends[:12],'prep':prep[:10],
            'prepNote':'Current-season games, fresh prices and player availability must clear before a row appears.',
            'trial':{'label':'NBA Trial','state':'preparing','record':trial_record,
                     'note':'Opening-night series is being prepared. No NBA Trial play has been posted.'}}
