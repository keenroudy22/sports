"""Frozen-model confirmation on previously unsupported, later-source cases.

No refit or parameter change. Exclude every case forecastable in the first v2
study. Use one deterministic report per tip-time group, one hour before tip;
never probe timestamps. All retrieval is explicitly retrospective.
"""
import argparse,hashlib,json,math,statistics
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
import boxscores,hoops_store,nba_capture,paper
import nba_official_availability as official
import nba_roster_model_v2 as model
import nba_roster_validation_v2 as base
ROOT=base.ROOT
STORE=ROOT/'data/nba-roster-confirmation-v2'
QUALITY_GATES=base.QUALITY_GATES
EASTERN=base.EASTERN
training_hash=base.training_hash
confidence=base.confidence


def read(path):return json.loads(Path(path).read_text())
def boxes():return [r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
def packets(root=STORE):
    out={p['source']:p for p in base.packets().values()}
    for path in (Path(root)/'availability').glob('*.jsonl'):
        for row in boxscores.read_store(path):out[row['source']]=row
    return out

def archive_errors(root=STORE):return base.archive_errors()+boxscores.verify(Path(root)/'availability')


def prepare(root=STORE):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    fitted=read(base.STORE/'validation.json')
    if hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest()!=fitted['sourceHash']:raise ValueError('Frozen fitted source changed')
    plan=fitted['plan'];test_dates=set(plan['dates'][plan['split']:])
    records=hoops_store.load('NBA');bs=boxes();context=read(base.STORE/'residual-context.json')['rows'];sources=base.packets()
    excluded=[];targets={};models={}
    for r in records:
        day=str(boxscores.instant(r['kickoff']).astimezone(EASTERN).date())
        if r['season']!=2026 or r.get('type')!=2 or day not in test_dates:continue
        packet=sources[day];clock=boxscores.instant(packet['reportedAt'])
        feature,holds=model.features(base.game(r),packet,{},bs,context,clock,retrospective=True)
        if not holds:
            if day not in models:
                past=[x for x in records if boxscores.instant(x['kickoff'])+timedelta(hours=6)<=clock]
                models[day]=paper.model_for('NBA',2026,clock.timestamp(),records=past)
            baseline=models[day].predict(r['home']['id'],r['away']['id'])
            try:model.predict(baseline,feature,fitted);excluded.append(str(r['eventId']));continue
            except ValueError:pass
        kickoff=boxscores.instant(r['kickoff']);at=kickoff-timedelta(hours=1)
        at=at.replace(minute=15*(at.minute//15),second=0,microsecond=0)
        source='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+at.astimezone(EASTERN).strftime('%Y-%m-%d_%I_%M%p')+'.pdf'
        targets[str(r['eventId'])]=dict(day=day,reportedAt=boxscores.stamp(at),source=source,kickoff=r['kickoff'])
    result=dict(selectedAt=boxscores.stamp(datetime.now(timezone.utc)),policy=model.POLICY,
        dates=sorted(test_dates),split=0,targets=targets,excludedPreviouslyForecastable=sorted(excluded),
        fittedArtifactHash=hashlib.sha256((base.STORE/'validation.json').read_bytes()).hexdigest(),
        modelSourceHash=hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest(),
        selection='All previously unsupported v2 test-date games; fixed one-hour pre-tip reports. No outcome selection.',
        scope='Sequential retrospective confirmation, not untouched forward validation; frozen coefficients, v1/v2 results preserved')
    path=root/'plan.json'
    if path.exists():
        old=read(path)
        if any(old[k]!=result[k] for k in ('targets','excludedPreviouslyForecastable','fittedArtifactHash','modelSourceHash','policy')):
            raise ValueError('Frozen confirmation plan changed')
        return old
    boxscores.write_json(path,result);return result


def collect(root=STORE):
    root=Path(root);plan=prepare(root);saved=packets(root);budget=nba_capture.Budget(requests=32,seconds=150)
    records=hoops_store.load('NBA');bs=boxes();unique={t['source']:t for t in plan['targets'].values()}
    for source,t in sorted(unique.items()):
        if source in saved:continue
        if budget.requests>=budget.limit:break
        entry=dict(league='NBA',season=2026,day=t['day'],source=source,archive=True,analysisOnly=True,expectedAt=t['reportedAt'])
        try:
            pdf=budget.raw(source);at=datetime.now(timezone.utc);digest=hashlib.sha256(pdf).hexdigest()
            path=root/'pdfs'/(t['day']+'-'+digest[:12]+'.pdf');path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists():path.write_bytes(pdf)
            slate=[base.game(r) for r in records if r['season']==2026 and str(boxscores.instant(r['kickoff']).astimezone(EASTERN).date())==t['day']]
            report=official.parse(official.extract(pdf),slate,base.identity_maps(bs,2026),boxscores.instant(t['reportedAt']),at,source,archive=True)
            entry.update(report,state='observed',sha256=digest,pdfFile=str(path.relative_to(root)))
        except (OSError,ValueError,KeyError,TypeError) as error:
            entry.update(state='unavailable',retrievedAt=boxscores.stamp(datetime.now(timezone.utc)),reason=type(error).__name__+': '+str(error)[:160])
        nba_capture.append_changed([entry],root/'availability',lambda r:r['source'])
    remaining=sum(source not in packets(root) for source in unique)
    return dict(newRequests=budget.requests,uniqueReports=len(unique),remaining=remaining,excluded=len(plan['excludedPreviouslyForecastable']))


def context_rows(root=STORE):
    rows=read(base.STORE/'residual-context.json')['rows'];records={str(r['eventId']):r for r in hoops_store.load('NBA')}
    by_event={}
    for p in sorted(packets(root).values(),key=lambda p:p.get('reportedAt','')):
        if p.get('state')!='observed':continue
        for team in p['teams']:
            r=records.get(team['eventId'])
            if (not r or boxscores.instant(p['reportedAt'])>=boxscores.instant(r['kickoff'])
                    ):continue
            by_event[(team['eventId'],team['team'])]=dict(verifiedOut=([x['athleteId'] for x in team['rows'] if x['status']=='Out'] if team['submitted'] is True and not team['unmapped'] else []),
                absenceSource=p['source'],absenceReportAt=p['reportedAt'])
    for row in rows:row.update(by_event.get((str(row['eventId']),row['team']),{}))
    return rows


def evaluate(root=STORE,coverage_only=False):
    root=Path(root);plan=prepare(root);fitted=read(base.STORE/'validation.json')
    if hashlib.sha256((base.STORE/'validation.json').read_bytes()).hexdigest()!=plan['fittedArtifactHash']:raise ValueError('Refitting prohibited')
    if hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest()!=plan['modelSourceHash']:raise ValueError('Model changed after confirmation selection')
    ps=packets(root);records=hoops_store.load('NBA');bs=boxes();context=context_rows(root);models={};tested=[];holds=defaultdict(int)
    for r in records:
        t=plan['targets'].get(str(r['eventId']))
        if not t:continue
        packet=ps.get(t['source'],{})
        if packet.get('state')!='observed':holds['source unavailable']+=1;continue
        clock=boxscores.instant(packet['reportedAt'])
        feature,reasons=model.features(base.game(r),packet,{},bs,context,clock,retrospective=True)
        if reasons:
            for reason in reasons:holds[reason.split(': ',1)[-1]]+=1
            continue
        if any(x['rotation']['unresolved'] for x in feature['teams'].values()):holds['unresolved participation']+=1;continue
        if clock not in models:
            past=[x for x in records if boxscores.instant(x['kickoff'])+timedelta(hours=6)<=clock]
            models[clock]=paper.model_for('NBA',2026,clock.timestamp(),records=past)
        baseline=models[clock].predict(r['home']['id'],r['away']['id'])
        try:adjusted=model.predict(baseline,feature,fitted)
        except ValueError:holds['features/correction outside training support']+=1;continue
        tested.append(dict(eventId=str(r['eventId']),day=t['day'],baseline=baseline,adjusted=adjusted,
            feature=feature,actualHome=r['homeScore'],actualAway=r['awayScore'],close=r.get('close',{})))
    if coverage_only:return dict(coverageOnly=True,testGames=len(tested),scheduled=len(plan['targets']),holds=dict(holds))
    study_hash=hashlib.sha256(Path(model.__file__).read_bytes()+Path(__file__).read_bytes()).hexdigest()
    if (root/'validation.json').exists():
        old=read(root/'validation.json')
        if old['studySourceHash']!=study_hash:raise ValueError('Confirmation already exposed; changes need new cases')
        return old
    checks={};families=[]
    core=sum(any(t['rotation']['coreOut'] for t in r['feature']['teams'].values()) for r in tested)
    for family in ('margin','total'):
        actual=lambda r:r['actualHome']-r['actualAway'] if family=='margin' else r['actualHome']+r['actualAway']
        differences=[abs(actual(r)-r['baseline'][family])-abs(actual(r)-r['adjusted'][family]) for r in tested]
        ci=confidence(differences,[r['day'] for r in tested]);key='spread' if family=='margin' else 'total'
        quoted=[r for r in tested if model.number(r['close'].get(key))]
        line=lambda r:-r['close'][key] if family=='margin' else r['close'][key]
        avg=lambda xs:statistics.mean(xs) if xs else None
        briers=[]
        for r in quoted:
            if actual(r)==line(r):continue
            outcome=actual(r)>line(r)
            chance=lambda p:.5*(1+math.erf((p[family]-line(r))/(p['sdMargin' if family=='margin' else 'sdTotal']*math.sqrt(2))))
            briers.append(((chance(r['baseline'])-outcome)**2,(chance(r['adjusted'])-outcome)**2))
        c=dict(trainGames=fitted['checks'][family]['trainGames'],trainCoreAbsenceGames=fitted['checks'][family]['trainCoreAbsenceGames'],
            testGames=len(tested),quotedGames=len(quoted),testCoreAbsenceGames=core,scheduledTestGames=len(plan['targets']),
            improvement95=ci,baselineMAE=avg([abs(actual(r)-r['baseline'][family]) for r in tested]),
            adjustedMAE=avg([abs(actual(r)-r['adjusted'][family]) for r in tested]),
            adjustedMAEOnQuotedGames=avg([abs(actual(r)-r['adjusted'][family]) for r in quoted]),quotedLineMAE=avg([abs(actual(r)-line(r)) for r in quoted]),
            baselineBrier=avg([x for x,y in briers]),adjustedBrier=avg([y for x,y in briers]),
            baselineWinnerBrier=avg([(r['baseline']['homeWinProb']-(r['actualHome']>r['actualAway']))**2 for r in tested]),
            adjustedWinnerBrier=avg([(r['adjusted']['homeWinProb']-(r['actualHome']>r['actualAway']))**2 for r in tested]))
        c['passed']=(c['trainGames']>=30 and c['testGames']>=30 and c['quotedGames']>=30 and c['trainCoreAbsenceGames']>=10 and core>=10
            and len(tested)/max(1,len(plan['targets']))>=.25 and ci[0] is not None and ci[0]>0
            and c['adjustedMAEOnQuotedGames']<c['quotedLineMAE'] and c['adjustedBrier']<=c['baselineBrier']
            and (family!='margin' or c['adjustedWinnerBrier']<=c['baselineWinnerBrier']))
        checks[family]=c
        if c['passed']:families.append(family)
    report={**{k:fitted[k] for k in ('coefficients','featureBounds','policy','version')},'checks':checks,'qualityGates':QUALITY_GATES,
        'validatedFamilies':families,'analysisOnly':not bool(families),'createdAt':boxscores.stamp(datetime.now(timezone.utc)),
        'sourceHash':plan['modelSourceHash'],'studySourceHash':study_hash,'plan':plan,'trainingHash':training_hash(records,bs,plan),
        'contextHash':hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest(),
        'archiveHash':hashlib.sha256(json.dumps(ps,sort_keys=True).encode()).hexdigest(),'holds':dict(holds),
        'scope':plan['scope'],'fittedArtifactHash':plan['fittedArtifactHash']}
    boxscores.write_json(root/'residual-context.json',{'rows':context,'reconstructed':True})
    boxscores.write_json(root/'validation.json',report)
    nba_capture.append_changed([dict(report,league='NBA',season=2026)],root/'validation-runs',lambda r:r['createdAt'])
    boxscores.write_json(root/'test-comparisons.json',{'rows':tested,'analysisOnly':True})
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','collect','coverage','evaluate'));args=parser.parse_args()
    result=prepare() if args.action=='prepare' else collect() if args.action=='collect' else evaluate(coverage_only=args.action=='coverage')
    print(json.dumps(result if args.action!='evaluate' else {k:result[k] for k in ('checks','validatedFamilies','holds')},indent=2))
