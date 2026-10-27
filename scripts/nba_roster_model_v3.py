"""Recent team residuals plus a learned injury-exposure change.

Explicit recorded zero minutes are observations; missing minutes remain unknown.
Replacement scoring is a regression feature, not an asserted causal point loss,
coach minutes forecast, or redistribution into player/quarter prop forecasts.
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

VERSION='nba-roster-exposure-v3'
MIN_MATCHES=5
MIN_OVERLAP=.90
SHRINK_GAMES=10
MAX_HISTORY=30
POLICY=dict(version=VERSION,rotationGames=3,contextGames=5,minimumContext=3,
            shrinkGames=10,ridge=10,minimumTrainGames=30,minimumTestGames=30,
            minimumCoverage=.25,bootstrapReplicates=1000,bootstrapSeed=20261027,
            features=['ownRecentScore','opponentRecentAllowed','ownExposureChange','opponentExposureChange'])


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
    return float(value) if number(value) and 0<=value<=60 else None


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
    """Verify observed team continuity; do not manufacture a 240-minute lineup.

    This model forecasts team residuals, not each healthy player's minutes.
    Explicit DNPs can establish an already-absent role; an omitted row cannot.
    New core arrivals and documented returns without recent workload still hold.
    """
    available=point_boxes(boxes,now,retrospective)
    history=[b for b in available if b['season']==season and team in b.get('teams',{})][-10:]
    prior=history[-3:]
    if len(prior)!=3:return None,'Three current-season team boxes needed'
    if now-boxscores.instant(prior[-1]['kickoff'])>timedelta(days=8):return None,'Current rotation evidence is stale'
    accounting=[complete_team(b,team) for b in prior]
    if any(r is None for r in accounting):return None,'Incomplete recent team minute/point accounting'
    if retrospective:
        # An omitted bench row is not proof of a roster departure. Use the
        # union of the three prior observed boxes, excluding known transfers.
        last_team={p['id']:p['team'] for b in available for p in b['players'] if (minutes(p) or 0)>0}
        people={p['id']:p for b in prior for p in b['players'] if p['team']==team and last_team.get(p['id'],team)==team}
    else:
        try:fresh=timedelta(0)<=now-boxscores.instant(roster.get('retrievedAt'))<=timedelta(hours=24)
        except (TypeError,ValueError):fresh=False
        if roster.get('team')!=team or roster.get('season')!=season or not fresh:return None,'Current roster needs verification'
        people={p['id']:p for p in roster.get('players',[]) if p.get('active') is True}
    statuses={p['athleteId']:p['status'] for p in rows if p['team']==team}
    out={pid for pid,status in statuses.items() if status=='Out'}
    unresolved={pid for pid,status in statuses.items() if nba_capture.blocks_availability(status) and status!='Out'}
    if unresolved and not retrospective:return None,'Unresolved official participation status'
    if any(pid not in people for pid,status in statuses.items() if status in ('Available','Active')):
        return None,'Official eligibility conflicts with current roster'
    coverage=[sum(v for pid,v in values.items() if pid in people or pid in out)/total for values,total in accounting]
    if min(coverage)<.9:return None,'Current roster differs from recent team workload'
    core=set();returns=[]
    for pid in set(people)|out:
        career=[minutes(p) for b in available if b['season'] in (season,season-1)
                for p in b['players'] if p['id']==pid and (minutes(p) or 0)>0]
        established=len(career)>=3 and statistics.median(career[-10:])>=12
        current=[p for b in history for p in b['players'] if p['team']==team and p['id']==pid and (minutes(p) or 0)>0]
        if pid in out:
            if len(current)>=3 and statistics.median([minutes(p) for p in current[-10:]])>=12:core.add(pid)
            continue
        observed=[values.get(pid) for values,total in accounting]
        important=established and (statistics.median(career[-10:])>=24 or sum(p.get('starter') is True for p in current[-10:])>=max(1,len(current[-10:]))/2)
        if important and len(current)<3:returns.append(people[pid].get('name',pid))
        if important and statuses.get(pid) in ('Available','Active') and (observed[-1] is None or observed[-1] < .7*statistics.median(career[-10:])):
            returns.append(people[pid].get('name',pid))
    if returns:return None,'Unverified arriving/returning core workload: '+', '.join(returns[:4])
    return dict(team=team,knownOut=sorted(out),coreOut=sorted(core),unresolved=sorted(unresolved),
        conditionalAvailable=bool(unresolved),eligibleIds=sorted(set(people)-out),sourceGames=[b['eventId'] for b in prior],
        sourceReceipts=[b['retrievedAt'] for b in prior],minimumRosterCoverage=min(coverage),
        scope='Observed roster continuity, not a projected individual minute allocation'),None


def exposure_context(team,season,rotation,boxes,residuals,now,*,retrospective=False):
    """Recent team residual plus a learned injury-exposure feature, not a penalty.

    An already-absent player's new exposure is zero: recent team residuals
    already reflect that absence. Missing rows remain unknown unless an exact
    pregame official Out observation independently establishes nonparticipation.
    """
    index={(str(r['eventId']).removeprefix('NBA-'),r['team']):r for r in residuals}
    history=[b for b in point_boxes(boxes,now,retrospective) if b['season']==season and team in b['teams']]
    recent=[]
    for b in history[-POLICY['contextGames']:]:
        r=index.get((str(b['eventId']).removeprefix('NBA-'),team))
        if (not r or complete_team(b,team) is None or
            boxscores.instant(r['forecastAt'])>=boxscores.instant(b['kickoff']) or
            not all(number(r.get(k)) for k in ('scoreResidual','allowedResidual'))):
            return None,'Recent team context is incomplete'
        recent.append((b,r))
    if len(recent)<POLICY['minimumContext']:return None,'Three complete recent team contexts needed'
    # Actual bench production supplies a replacement-capacity indicator. It is
    # never assigned to a named teammate or used as a player/quarter projection.
    returned=(set(pid for b,r in recent[-3:] for pid in r.get('verifiedOut',[]))
              -set(rotation['knownOut'])) & set(rotation['eligibleIds'])
    return_features=[];uncertain_bench=[]
    for pid in returned:
        career=[p for b in history for p in b['players'] if p['id']==pid and p['team']==team and (minutes(p) or 0)>0]
        if len(career)<3 or statistics.median([minutes(p) for p in career[-10:]])<12:continue
        workload=[]
        for b,r in recent[-3:]:
            p=next((p for p in b['players'] if p['id']==pid and p['team']==team),None)
            if p is not None and minutes(p) is not None:workload.append(minutes(p));continue
            if pid in r.get('verifiedOut',[]):workload.append(0.);continue
            return None,'Documented core return has unknown recent workload'
        typical=statistics.median([minutes(p) for p in career[-10:]])
        if workload[-1]<.7*typical:
            starting=sum(p.get('starter') is True for p in career[-10:])>=len(career[-10:])/2
            if starting or typical>=24:return None,'Documented core return lacks an observed full-role workload'
            uncertain_bench.append((pid,career,typical));continue
        return_features.append((pid,career,typical-statistics.mean(workload),workload))
    if sum(x[2] for x in uncertain_bench)>24:return None,'Uncertain reserve return workload exceeds ten percent of team minutes'
    bench=[p for b,r in recent[-3:] for p in b['players'] if p['team']==team
           and p.get('starter') is False and p['id'] not in rotation['knownOut'] and (minutes(p) or 0)>0]
    bench_min=sum(minutes(p) for p in bench)
    if bench_min<30:return None,'Recent replacement scoring evidence is incomplete'
    bench_rate=sum(p['stats']['pts'] for p in bench)/bench_min
    exposure=0.;people=[]
    for pid in rotation['coreOut']:
        played=[]
        for b in history[-10:]:
            p=next((p for p in b['players'] if p['id']==pid and p['team']==team),None)
            if p and (minutes(p) or 0)>0:played.append(p)
        if len(played)<3:return None,'Three observed current-team scoring roles needed for a core absence'
        rate=sum(p['stats']['pts'] for p in played)/sum(minutes(p) for p in played)
        load=[]
        for b,r in recent[-3:]:
            p=next((p for p in b['players'] if p['id']==pid and p['team']==team),None)
            if p is not None and minutes(p) is not None:load.append(minutes(p));continue
            verified=(pid in r.get('verifiedOut',[]) and r.get('absenceReportAt') and
                      boxscores.instant(r['absenceReportAt'])<boxscores.instant(b['kickoff']) and
                      str(r.get('absenceSource','')).startswith('https://ak-static.cms.nba.com/referee/injury/'))
            if not verified:return None,'Core-absence recent workload is unknown'
            load.append(0.)
        value=statistics.mean(load)*(bench_rate-rate)
        exposure+=value
        people.append(dict(id=pid,name=played[-1]['name'],recentMinutes=load,scoringRate=rate,
                           replacementRate=bench_rate,exposureFeature=value))
    for pid,played,change,load in return_features:
        rate=sum(p['stats']['pts'] for p in played)/sum(minutes(p) for p in played)
        value=change*(rate-bench_rate);exposure+=value
        people.append(dict(id=pid,name=played[-1]['name'],recentMinutes=load,scoringRate=rate,
            replacementRate=bench_rate,exposureFeature=value,returnAfterObservedFullRole=True))
    unknown_range=sum(typical*abs(sum(p['stats']['pts'] for p in played)/sum(minutes(p) for p in played)-bench_rate) for pid,played,typical in uncertain_bench)
    n=len(recent);shrink=n/(n+10)
    return dict(score=shrink*statistics.mean(r['scoreResidual'] for b,r in recent),
        allowed=shrink*statistics.mean(r['allowedResidual'] for b,r in recent),
        scoreSE=shrink*statistics.stdev(r['scoreResidual'] for b,r in recent)/math.sqrt(n),
        allowedSE=shrink*statistics.stdev(r['allowedResidual'] for b,r in recent)/math.sqrt(n),
        exposure=exposure,exposureSE=abs(exposure)/math.sqrt(3)+unknown_range,sample=n,coreAbsences=people,
        uncertainReserveReturns=[dict(id=pid,priorMinutes=typical) for pid,played,typical in uncertain_bench],
        contextEvents=[b['eventId'] for b,r in recent],scope='Learned team exposure indicator, not individual points removed'),None


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
        match,hold=exposure_context(tid,game['season'],rot,boxes,residuals,now,retrospective=retrospective)
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
    return ((h['score'],a['allowed'],h['exposure'],a['exposure']),
            (a['score'],h['allowed'],a['exposure'],h['exposure']))


def fit(rows):
    """Fixed ridge solved by deterministic coordinate descent; stdlib only."""
    n=4
    scale=[math.sqrt(statistics.mean(x[j]**2 for x,y in rows)) or 1. for j in range(n)]
    design=[([x[j]/scale[j] for j in range(n)],y) for x,y in rows]
    beta=[0.]*n
    for _ in range(200):
        for j in range(n):
            numerator=sum(x[j]*(y-sum(x[k]*beta[k] for k in range(n) if k!=j)) for x,y in design)
            beta[j]=numerator/(POLICY['ridge']+sum(x[j]**2 for x,y in design))
    return dict(coefficients=[b/s for b,s in zip(beta,scale)],
        featureBounds=[[min(x[j] for x,y in rows),max(x[j] for x,y in rows)] for j in range(n)],
        policy=POLICY,version=VERSION)


def predict(baseline,feature,model):
    beta=model['coefficients'];hs,aws=vectors(feature)
    if len(beta)!=4 or len(model['featureBounds'])!=4:raise ValueError('Incomplete exposure model')
    for x in (hs,aws):
        if any(not low-1e-9<=v<=high+1e-9 for v,(low,high) in zip(x,model['featureBounds'])):
            raise ValueError('Roster features outside the training support')
    dh=sum(a*b for a,b in zip(hs,beta));da=sum(a*b for a,b in zip(aws,beta))
    if not all(number(v) and abs(v)<=12 for v in (dh,da)):raise ValueError('Roster correction outside supported range')
    comparisons=[t['comparison'] for t in feature['teams'].values()]
    se=sum(abs(beta[0])*t['scoreSE']+abs(beta[1])*t['allowedSE']+
           (abs(beta[2])+abs(beta[3]))*t['exposureSE'] for t in comparisons)
    spread=math.sqrt(baseline['sdMargin']**2+se**2)
    return dict(baseline,total=baseline['total']+dh+da,margin=baseline['margin']+dh-da,
        sdMargin=spread,sdTotal=math.sqrt(baseline['sdTotal']**2+se**2),
        homeWinProb=.5*(1+math.erf((baseline['margin']+dh-da)/(spread*math.sqrt(2)))),
        homeAdjustment=dh,awayAdjustment=da,model=VERSION,feature=feature)
