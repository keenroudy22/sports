"""Roster-conditioned team residuals, not invented individual point penalties.

An estimated rotation is built before the forecast. Historical comparison games
must have similar observed minutes and the same known core absences. Their
opponent-adjusted score residuals supply features for a small ridge correction.
No game plus/minus, actual target-game lineup or target outcome enters a feature.
"""
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import boxscores
import nba_capture
import nba_roles
import paper
import hoops_model

VERSION='nba-roster-residual-v1'
MIN_MATCHES=5
MIN_OVERLAP=.90
SHRINK_GAMES=10
MAX_HISTORY=30
POLICY=dict(version=VERSION,minMatches=MIN_MATCHES,minOverlap=MIN_OVERLAP,
            shrinkGames=SHRINK_GAMES,maxHistory=MAX_HISTORY,rotationGames=3,
            ridge=10,minimumTrainGames=30,minimumTestGames=30,minimumCoverage=.25,
            bootstrapReplicates=1000,bootstrapSeed=20261027)


def number(value):
    return type(value) in (int,float) and math.isfinite(value)


def point_boxes(boxes,now,retrospective=False):
    if not retrospective:return nba_roles.available_boxes(boxes,now)
    # Backfilled history is explicitly retrospective. A six-hour completion lag
    # prevents a target or same-evening in-progress result entering its features.
    return sorted(
        (r for r in _latest(boxes) if r.get('seasonType')==2
         and boxscores.instant(r['kickoff'])+timedelta(hours=6)<=now),
        key=lambda r:(r['kickoff'],r['eventId']))


def _latest(boxes):
    latest={};conflicts=set()
    for b in boxes:
        key=str(b['eventId']);at=boxscores.instant(b['retrievedAt'])
        if key not in latest or at>latest[key][0]:latest[key]=(at,b);conflicts.discard(key)
        elif at==latest[key][0] and b!=latest[key][1]:conflicts.add(key)
    return [row for k,(_,row) in latest.items() if k not in conflicts]


def minutes(player):
    if player.get('dnp') is True:return 0.
    value=player.get('stats',{}).get('min')
    return float(value) if number(value) and 0<value<=60 else None


def complete_team(box,team):
    people={p['id']:p for p in box['players'] if p['team']==team}
    values={pid:minutes(p) for pid,p in people.items()}
    if any(v is None for v in values.values()):return None
    total=sum(values.values())
    if min(abs(total-(240+25*i)) for i in range(4))>3:return None
    points=[0 if p.get('dnp') else p.get('stats',{}).get('pts') for p in people.values()]
    if not all(number(v) for v in points) or abs(sum(points)-box['teams'][team]['score'])>1e-8:return None
    return values,total


def rotation(team,season,boxes,roster,rows,now,*,retrospective=False):
    """Observed role estimates plus an explicit, bounded reserve bucket.

    Missing player rows are never zero-filled. Unmodeled reserve roles remain
    named and may explain at most10% of recent recorded eligible workload.
    Established rotation players with missing/stale role evidence still hold.
    """
    available=point_boxes(boxes,now,retrospective)
    history=[b for b in available if b['season']==season and team in b.get('teams',{})][-10:]
    prior=history[-3:]
    if len(prior)!=3:return None,'Three current-season team boxes needed'
    if now-boxscores.instant(prior[-1]['kickoff'])>timedelta(days=8):return None,'Current rotation evidence is stale'
    complete=[complete_team(b,team) for b in prior]
    if any(row is None for row in complete):return None,'Incomplete recent team minute/point accounting'
    if retrospective:
        people={p['id']:p for p in prior[-1]['players'] if p['team']==team}
    else:
        try:roster_fresh=timedelta(0)<=now-boxscores.instant(roster.get('retrievedAt'))<=timedelta(hours=24)
        except (TypeError,ValueError):roster_fresh=False
        if roster.get('team')!=team or roster.get('season')!=season or not roster_fresh:
            return None,'Current roster needs verification'
        people={p['id']:p for p in roster.get('players',[]) if p.get('active') is True}
    statuses={p['athleteId']:p['status'] for p in rows if p['team']==team}
    out={pid for pid,s in statuses.items() if s=='Out'}
    unresolved={pid for pid,s in statuses.items() if nba_capture.blocks_availability(s) and s!='Out'}
    if not retrospective and any(pid not in people for pid,s in statuses.items() if s in ('Available','Active')):
        return None,'Official eligibility conflicts with the current roster'
    # Research backtests may estimate a conditional available rotation without
    # clearing these statuses. Live admissions always retain the unresolved hold;
    # only resolved test games can satisfy the promotion checks.
    if unresolved and not retrospective:return None,'Unresolved official participation status'
    weights={};observations={};unknown=[];material_unknown=[]
    for pid,p in people.items():
        if pid in out:continue
        values=[];dates=[]
        for b in history:
            mine=[x for x in b['players'] if x['id']==pid and x['team']==team]
            value=minutes(mine[0]) if len(mine)==1 else None
            if value is not None:values.append(value);dates.append(boxscores.instant(b['kickoff']))
        career=[minutes(x) for b in available if b['season'] in (season,season-1) for x in b['players'] if x['id']==pid and (minutes(x) or 0)>0]
        established=len(career)>=3 and statistics.median(career[-10:])>=12
        recent=len(values)>=3 and now-dates[-1]<=timedelta(days=8)
        value=statistics.median(values[-3:]) if recent else None
        if value is None or value==0:
            unknown.append(pid)
            if established:material_unknown.append(p.get('name') or pid)
            continue
        weights[pid]=value;observations[pid]=values[-3:]
    if material_unknown:return None,'Unverified rotation-player workload: '+', '.join(material_unknown[:4])
    reserves=[];shares=[]
    eligible=set(people)-out
    for values,total in complete:
        denominator=sum(v for pid,v in values.items() if pid in eligible)
        reserve=sum(v for pid,v in values.items() if pid in eligible and pid not in weights)
        if not denominator:return None,'No supported eligible rotation minutes'
        shares.append(reserve/denominator);reserves.append(reserve*240/total)
    if max(shares)>1-MIN_OVERLAP+1e-9:return None,'Unmodeled reserve workload exceeds supported share'
    reserve=statistics.median(reserves)
    total=sum(weights.values())+reserve
    if not 160<=total<=275:return None,'Observed rotation cannot support a 240-minute estimate'
    weights={pid:240*m/total for pid,m in weights.items() if m>0}
    if any(m>42 for m in weights.values()):return None,'Replacement workload exceeds supported minutes'
    core_out=set()
    for pid in out:
        for year in (season,season-1):
            values=[minutes(p) for b in available if b['season']==year and team in b.get('teams',{}) for p in b['players']
                    if p['id']==pid and p['team']==team and (minutes(p) or 0)>0]
            if len(values)>=3 and statistics.median(values[-10:])>=12:core_out.add(pid)
    return dict(team=team,weights=weights,knownOut=sorted(out),coreOut=sorted(core_out),
        unresolved=sorted(unresolved),conditionalAvailable=bool(unresolved),
        reserveMinutes=240*reserve/total,unmodeledReserveIds=unknown,maxRecentReserveShare=max(shares),
        sourceGames=[b['eventId'] for b in prior],sourceReceipts=[b['retrievedAt'] for b in prior],
        observedMinutes=observations,scope='Estimated rotation, not a confirmed lineup or coach minutes limit'),None


def matched(team,season,rotation,boxes,residuals,now,*,retrospective=False):
    residual_index={(str(r['eventId']).removeprefix('NBA-'),r['team']):r for r in residuals}
    matches=[]
    for b in point_boxes(boxes,now,retrospective):
        if b['season'] not in (season,season-1) or team not in b.get('teams',{}):continue
        players={p['id']:p for p in b['players'] if p['team']==team}
        key=(str(b['eventId']).removeprefix('NBA-'),team);r=residual_index.get(key)
        if not r:continue
        verified_out=set()
        if (str(r.get('absenceSource','')).startswith('https://ak-static.cms.nba.com/referee/injury/')
                and r.get('absenceReportAt') and boxscores.instant(r['absenceReportAt'])<boxscores.instant(b['kickoff'])):
            verified_out=set(r.get('verifiedOut',[]))
        # A missing row remains unknown unless the pregame official report
        # independently named that exact player Out. No absence-as-zero shortcut.
        if any(pid in players and (minutes(players[pid]) or 0)>0 for pid in rotation['coreOut']):continue
        if any(not (pid in players and players[pid].get('dnp') is True or pid in verified_out)
               for pid in rotation['coreOut']):continue
        accounting=complete_team(b,team)
        if accounting is None:continue
        played,total=accounting
        reserve=sum(v for pid,v in played.items() if pid not in rotation['weights'])
        overlap=(sum(min(m,240*played.get(pid,0)/total) for pid,m in rotation['weights'].items())
                 +min(rotation.get('reserveMinutes',0),240*reserve/total))/240
        if overlap<MIN_OVERLAP:continue
        if boxscores.instant(r['forecastAt'])>=boxscores.instant(b['kickoff']):continue
        if not all(number(r.get(k)) for k in ('scoreResidual','allowedResidual')):continue
        matches.append(dict(eventId=b['eventId'],kickoff=b['kickoff'],overlap=overlap,
                            scoreResidual=r['scoreResidual'],allowedResidual=r['allowedResidual']))
    matches=matches[-MAX_HISTORY:]
    if len(matches)<MIN_MATCHES:return None,f'Only {len(matches)} comparable past rotations; {MIN_MATCHES} needed'
    shrink=len(matches)/(len(matches)+SHRINK_GAMES)
    return dict(score=shrink*statistics.mean(r['scoreResidual'] for r in matches),
                allowed=shrink*statistics.mean(r['allowedResidual'] for r in matches),
                scoreSE=shrink*statistics.stdev(r['scoreResidual'] for r in matches)/math.sqrt(len(matches)),
                allowedSE=shrink*statistics.stdev(r['allowedResidual'] for r in matches)/math.sqrt(len(matches)),
                sample=len(matches),matches=matches),None


def features(game,report,rosters,boxes,residuals,now,*,retrospective=False):
    event=str(game['providerId']);records={(str(r['eventId']),str(r['team'])):r for r in report.get('teams',[])}
    teams={};holds=[]
    if report.get('archive') and not retrospective:return None,['Archived report cannot clear a current game']
    try:reported=boxscores.instant(report['reportedAt'])
    except (KeyError,ValueError,TypeError):return None,['Official report clock unavailable']
    if not reported<=now:return None,['Future injury report']
    if not retrospective:
        try:
            reported=boxscores.instant(report['reportedAt']);received=boxscores.instant(report['retrievedAt'])
            if not timedelta(0)<=now-reported<=timedelta(hours=1) or not reported<=received<=now:
                return None,['Official injury report is stale or future-received']
            expected='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+reported.astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d_%I_%M%p')+'.pdf'
            if report.get('source')!=expected or report.get('season')!=game['season']:
                return None,['Official report source or season mismatch']
        except (KeyError,ValueError,TypeError):return None,['Official report metadata unavailable']
    for side,t in game['teams'].items():
        tid=str(t['id']);record=records.get((event,tid))
        if not record or record.get('submitted') is not True or record.get('unmapped'):
            holds.append(t.get('abbreviation',tid)+': Official team report/identity incomplete');continue
        rot,hold=rotation(tid,game['season'],boxes,rosters.get(tid,{}),record['rows'],now,retrospective=retrospective)
        if hold:holds.append(t.get('abbreviation',tid)+': '+hold);continue
        match,hold=matched(tid,game['season'],rot,boxes,residuals,now,retrospective=retrospective)
        if hold:holds.append(t.get('abbreviation',tid)+': '+hold);continue
        teams[side]=dict(rotation=rot,comparison=match)
    return (dict(teams=teams,reportedAt=report['reportedAt'],source=report['source']) if not holds else None),holds


def residual_history(records,now,only_events=None):
    """Retrospective baseline reconstruction, never an original frozen forecast."""
    models={};out=[];prepared=hoops_model.prepare(records);params=paper.chosen_params('NBA');priors={}
    regular=[r for r in records if r.get('type')==2]
    for r in regular:
        if only_events is not None and str(r['eventId']) not in only_events:continue
        kickoff=boxscores.instant(r['kickoff'])
        if kickoff+timedelta(hours=6)>now:continue
        day=kickoff.astimezone(ZoneInfo('America/New_York')).date()
        clock=min(kickoff-timedelta(hours=6),datetime(day.year,day.month,day.day,18,tzinfo=timezone.utc))
        key=(r['season'],clock)
        if key not in models:
            past=[x for x in prepared if x.t+6*3600<=clock.timestamp()]
            try:
                if r['season'] not in priors:priors[r['season']]=hoops_model.season_prior('NBA',prepared,r['season'],params)
                models[key]=hoops_model.Model('NBA',past,clock.timestamp(),r['season'],params,priors[r['season']])
            except ValueError:models[key]=None
        if models[key] is None:continue
        p=models[key].predict(r['home']['id'],r['away']['id'])
        for side,sign in (('home',1),('away',-1)):
            own=(p['total']+sign*p['margin'])/2;opp=(p['total']-sign*p['margin'])/2
            out.append(dict(eventId=r['eventId'],team=r[side]['id'],forecastAt=boxscores.stamp(clock),
                scoreResidual=r[side+'Score']-own,allowedResidual=r['awayScore' if side=='home' else 'homeScore']-opp,
                reconstructed=True))
    return out


def vectors(feature):
    t=feature['teams'];h=t['home']['comparison'];a=t['away']['comparison']
    return ((h['score'],a['allowed']),(a['score'],h['allowed']))


def fit(rows):
    # Fixed penalty and feature definition are declared before the test cohort.
    scale=[math.sqrt(statistics.mean(x[j]**2 for x,y in rows)) or 1 for j in (0,1)]
    xx=yy=10.;xy=rx=ry=0.
    for x,y in rows:
        a,b=x[0]/scale[0],x[1]/scale[1]
        xx+=a*a;yy+=b*b;xy+=a*b;rx+=a*y;ry+=b*y
    determinant=xx*yy-xy*xy
    return dict(coefficients=[(rx*yy-ry*xy)/determinant/scale[0],(ry*xx-rx*xy)/determinant/scale[1]],
                featureBounds=[[min(x[j] for x,y in rows),max(x[j] for x,y in rows)] for j in (0,1)],
                policy=POLICY,version=VERSION)


def predict(baseline,feature,model):
    beta=model['coefficients'];hs,aws=vectors(feature)
    for x in (hs,aws):
        if any(not low-1e-9<=v<=high+1e-9 for v,(low,high) in zip(x,model['featureBounds'])):
            raise ValueError('Roster features outside the training support')
    delta=lambda x:sum(a*b for a,b in zip(x,beta))
    dh,da=delta(hs),delta(aws)
    if not all(number(v) and abs(v)<=12 for v in (dh,da)):
        raise ValueError('Roster correction outside the supported score range')
    comparisons=[t['comparison'] for t in feature['teams'].values()]
    # An upper covariance bound for the four estimated correction features;
    # never reduce the old forecast's spread to manufacture confidence.
    se=sum(abs(beta[0])*t['scoreSE']+abs(beta[1])*t['allowedSE'] for t in comparisons)
    spread=math.sqrt(baseline['sdMargin']**2+se**2)
    total_spread=math.sqrt(baseline['sdTotal']**2+se**2)
    return dict(baseline,homeAdjustment=dh,awayAdjustment=da,
        total=baseline['total']+dh+da,margin=baseline['margin']+dh-da,
        sdMargin=spread,sdTotal=total_spread,
        homeWinProb=.5*(1+math.erf((baseline['margin']+dh-da)/(spread*math.sqrt(2)))),
        model=VERSION,feature=feature)
