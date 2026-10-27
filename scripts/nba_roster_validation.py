"""Fixed chronological, retrospective roster experiment. No odds/profit fitting.

The date plan is selected from schedule times and box coverage before outcomes
are evaluated. First half fits two fixed ridge features; second half is tested
once. Archive retrieval is labeled retrospective, never an old capture receipt.
"""
import argparse
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import boxscores
import hoops_store
import nba_capture
import nba_official_availability as official
import nba_roster_model as model
import paper

ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/'data/nba-roster-research'
EASTERN=ZoneInfo('America/New_York')
MAX_DATES=32
QUALITY_GATES=dict(minimumTrainCoreAbsenceGames=10,minimumTestCoreAbsenceGames=10)
ARCHIVE_IDENTITIES=[
    dict(id='NBA:1641801',name='Emanuel Miller',source='https://www.nba.com/stats/player/1641801'),
    dict(id='NBA:1626179',name='Terry Rozier',source='https://www.nba.com/player/1626179/terry-rozier/bio'),
    dict(id='NBA:1631262',name='Jules Bernard',source='https://www.nba.com/player/1631262/jules-bernard/profile'),
    dict(id='4397450',name='Darius Brown',canonicalName='Darius Brown II',source='https://gleague.nba.com/player/1642468'),
    dict(id='5217746',name='Hansen Yang',canonicalName='Yang Hansen',source='https://www.nba.com/player/1642905/hansen-yang/bio')]


def game(row):
    return dict(providerId=str(row['eventId']),id=row['id'],season=row['season'],kickoff=row['kickoff'],
        teams={s:dict(id=row[s]['id'],name=row[s]['school']+' '+row[s]['short'],abbreviation=row[s]['abbreviation']) for s in ('home','away')})


def date_plan(records,boxes):
    first=min(boxscores.instant(b['kickoff']) for b in boxes if b['season']==2026 and b['seasonType']==2)
    start=(first+timedelta(days=25)).astimezone(EASTERN).date()
    days=defaultdict(list)
    for r in records:
        if r['season']==2026 and r.get('type')==2:
            local=boxscores.instant(r['kickoff']).astimezone(EASTERN)
            days[local.date()].append(local)
    return [str(day) for day,rows in sorted(days.items()) if day>=start and min(r.hour for r in rows)>=19][:MAX_DATES]


def identity_maps(boxes,season):
    # Names identify athletes only. These are not historical roster claims and
    # do not carry minutes, status, score or future starting roles into features.
    identities={}
    for b in boxes:
        for p in b['players']:identities[(p['id'],p['name'])]=dict(id=p['id'],name=p['name'])
    for path in (ROOT/'data/nba-capture/rosters').glob('*.json'):
        for p in json.loads(path.read_text()).get('players',[]):
            identities[(p['id'],p['name'])]=dict(id=p['id'],name=p['name'])
    for p in ARCHIVE_IDENTITIES:identities[(p['id'],p['name'])]=p
    return {str(t):dict(team=str(t),season=season,identityOnly=True,players=list(identities.values()))
            for t in range(1,31)}


def collect(now=None,root=STORE,repair=False):
    now=now or datetime.now(timezone.utc);root=Path(root)
    boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    records=hoops_store.load('NBA');dates=date_plan(records,boxes)
    plan=dict(policy=model.POLICY,dates=dates,split=len(dates)//2,selectedAt=boxscores.stamp(now),
        selection='First32 eligible dates after25days box warmup, first tip19ET or later; schedule/coverage only',
        scope='Retrospective archive experiment; no original forecast or capture reconstruction claimed')
    root.mkdir(parents=True,exist_ok=True)
    existing=root/'plan.json'
    if existing.exists():
        old=json.loads(existing.read_text())
        if any(old[k]!=plan[k] for k in ('dates','split','policy')):raise ValueError('Archive experiment plan is immutable')
    else:boxscores.write_json(existing,plan)
    saved={r['day']:r for p in (root/'availability').glob('*.jsonl') for r in boxscores.read_store(p)}
    budget=nba_capture.Budget(requests=MAX_DATES,seconds=150)
    for day in dates:
        if day in saved and not repair:continue
        expected=datetime.fromisoformat(day+'T18:00:00').replace(tzinfo=EASTERN).astimezone(timezone.utc)
        url='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+expected.astimezone(EASTERN).strftime('%Y-%m-%d_%I_%M%p')+'.pdf'
        entry=dict(league='NBA',season=2026,day=day,source=url,archive=True,analysisOnly=True)
        try:
            # The first PDF was already observed in this attended audit. Its
            # original file-save clock stays distinct from this parsing clock.
            cached=ROOT/'work/nba-roster-archive-first.pdf'
            if day=='2026-02-20' and cached.exists():
                pdf=cached.read_bytes();entry['fileSavedAt']=datetime.fromtimestamp(cached.stat().st_mtime,timezone.utc).isoformat()
            else:pdf=budget.raw(url)
            observed=datetime.now(timezone.utc)
            digest=hashlib.sha256(pdf).hexdigest();raw=root/'pdfs'/(day+'-'+digest[:12]+'.pdf')
            raw.parent.mkdir(parents=True,exist_ok=True)
            if not raw.exists():raw.write_bytes(pdf)
            entry.update(sha256=digest,pdfFile=str(raw.relative_to(root)))
            slate=[game(r) for r in records if r['season']==2026 and str(boxscores.instant(r['kickoff']).astimezone(EASTERN).date())==day]
            packet=official.parse(official.extract(pdf),slate,identity_maps(boxes,2026),expected,observed,url,archive=True)
            entry.update(packet,state='observed',retrievedAt=boxscores.stamp(observed))
        except (OSError,ValueError,KeyError,TypeError) as error:
            entry.update(state='unavailable',retrievedAt=boxscores.stamp(datetime.now(timezone.utc)),reason=type(error).__name__+': '+str(error)[:180])
        nba_capture.append_changed([entry],root/'availability',lambda r:r['day'])
    return dict(newRequests=budget.requests,dates=len(dates),archiveOnly=True)


def reparse(root=STORE):
    """Correct archive identities from preserved bytes with zero source requests."""
    root=Path(root);records=hoops_store.load('NBA')
    boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    saved={r['day']:r for p in (root/'availability').glob('*.jsonl') for r in boxscores.read_store(p)}
    count=0
    for day,old in saved.items():
        path=root/old['pdfFile'];pdf=path.read_bytes()
        if hashlib.sha256(pdf).hexdigest()!=old['sha256']:raise ValueError('Archived PDF integrity failure')
        expected=boxscores.instant(old['expectedAt']) if old.get('expectedAt') else datetime.fromisoformat(day+'T18:00:00').replace(tzinfo=EASTERN).astimezone(timezone.utc)
        slate=[game(r) for r in records if r['season']==2026 and str(boxscores.instant(r['kickoff']).astimezone(EASTERN).date())==day]
        report=official.parse(official.extract(pdf),slate,identity_maps(boxes,2026),expected,
            boxscores.instant(old['retrievedAt']),old['source'],archive=True)
        entry=dict(old,**{k:v for k,v in report.items() if k!='retrievedAt'},state='observed',
                   parsedAt=boxscores.stamp(datetime.now(timezone.utc)),identityRevision=1,
                   identitySources=ARCHIVE_IDENTITIES,identityScope='ESPN box identities plus explicitly namespaced NBA-only historical identities; not roster verification')
        entry.pop('reason',None)
        count+=nba_capture.append_changed([entry],root/'availability',lambda r:r['day'])
    return dict(correctedArchives=count,newRequests=0)


def support(root=STORE):
    """All available pre-study dates, selected without outcomes, one report/date."""
    root=Path(root);plan=json.loads((root/'plan.json').read_text());records=hoops_store.load('NBA')
    boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    first=min(boxscores.instant(b['kickoff']).astimezone(EASTERN).date() for b in boxes if b['season']==2026 and b['seasonType']==2)
    groups=defaultdict(list)
    for r in records:
        if r['season']==2026 and r.get('type')==2:
            day=str(boxscores.instant(r['kickoff']).astimezone(EASTERN).date())
            if str(first)<=day<plan['dates'][0]:groups[day].append(r)
    if len(groups)>32:raise ValueError('Support collection exceeds unchanged pass bound')
    targets={day:min(datetime.fromisoformat(day+'T18:00:00').replace(tzinfo=EASTERN).astimezone(timezone.utc),
        min(boxscores.instant(r['kickoff']) for r in rows)-timedelta(hours=1)) for day,rows in sorted(groups.items())}
    manifest=dict(selectedAt=boxscores.stamp(datetime.now(timezone.utc)),targets={k:boxscores.stamp(v) for k,v in targets.items()},
        scope='Pre-study absence comparison evidence only; train/test dates and parameters unchanged')
    boxscores.write_json(root/'support-plan.json',manifest)
    old={r['day'] for p in (root/'availability').glob('*.jsonl') for r in boxscores.read_store(p)}
    budget=nba_capture.Budget(requests=32,seconds=150)
    for day,expected in targets.items():
        if day in old:continue
        source='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+expected.astimezone(EASTERN).strftime('%Y-%m-%d_%I_%M%p')+'.pdf'
        entry=dict(league='NBA',season=2026,day=day,source=source,archive=True,analysisOnly=True,expectedAt=boxscores.stamp(expected),supportOnly=True)
        try:
            pdf=budget.raw(source);observed=datetime.now(timezone.utc);digest=hashlib.sha256(pdf).hexdigest()
            path=root/'pdfs'/(day+'-'+digest[:12]+'.pdf');path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists():path.write_bytes(pdf)
            entry.update(sha256=digest,pdfFile=str(path.relative_to(root)),retrievedAt=boxscores.stamp(observed))
            packet=official.parse(official.extract(pdf),[game(r) for r in groups[day]],identity_maps(boxes,2026),expected,observed,source,archive=True)
            entry.update(packet,state='observed')
        except (OSError,ValueError,KeyError,TypeError) as error:
            entry.update(state='unavailable',retrievedAt=boxscores.stamp(datetime.now(timezone.utc)),reason=type(error).__name__+': '+str(error)[:180])
        nba_capture.append_changed([entry],root/'availability',lambda r:r['day'])
    return dict(requests=budget.requests,supportDates=len(targets),trainTestUnchanged=True)


def confidence(values,days):
    groups=defaultdict(list)
    for value,day in zip(values,days):groups[day].append(value)
    if len(groups)<5:return [None,None]
    rng=random.Random(model.POLICY['bootstrapSeed']);keys=sorted(groups);means=[]
    for _ in range(model.POLICY['bootstrapReplicates']):
        sample=[v for key in rng.choices(keys,k=len(keys)) for v in groups[key]]
        means.append(statistics.mean(sample))
    means.sort();return [round(means[int(.025*len(means))],4),round(means[int(.975*len(means))],4)]


def training_hash(records,boxes,plan):
    last=plan['dates'][-1]
    records=[r for r in records if str(boxscores.instant(r['kickoff']).astimezone(EASTERN).date())<=last]
    boxes=[b for b in boxes if str(boxscores.instant(b['kickoff']).astimezone(EASTERN).date())<=last]
    return hashlib.sha256(json.dumps([records,boxes],sort_keys=True).encode()+Path(paper.__file__).read_bytes()+
        (ROOT/'scripts/hoops_model.py').read_bytes()+(ROOT/'data/model/hoops-nba.json').read_bytes()).hexdigest()


def evaluate(root=STORE,coverage_only=False):
    root=Path(root);plan=json.loads((root/'plan.json').read_text());now=datetime.now(timezone.utc)
    if plan['policy']!=model.POLICY:raise ValueError('Experiment policy changed; no re-tuning the old test cohort')
    records=hoops_store.load('NBA');boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    packets={r['day']:r for p in (root/'availability').glob('*.jsonl') for r in boxscores.read_store(p)}
    cache=root/'baseline-residuals.json'
    # Cache is private reconstructed input, keyed to exact source records/model.
    fingerprint=hashlib.sha256(json.dumps(records,sort_keys=True).encode()+Path(paper.__file__).read_bytes()+
        (ROOT/'scripts/hoops_model.py').read_bytes()+(ROOT/'data/model/hoops-nba.json').read_bytes()).hexdigest()
    if cache.exists() and (old:=json.loads(cache.read_text())).get('inputHash')==fingerprint:residuals=old['rows']
    else:
        residuals=model.residual_history(records,now)
        boxscores.write_json(cache,dict(inputHash=fingerprint,rows=residuals,reconstructed=True))
    by_event={}
    for packet in packets.values():
        if packet.get('state')!='observed':continue
        for t in packet['teams']:
            if t['submitted'] is True and not t['unmapped']:
                by_event[(t['eventId'],t['team'])]=dict(verifiedOut=[p['athleteId'] for p in t['rows'] if p['status']=='Out'],
                    absenceSource=packet['source'],absenceReportAt=packet['reportedAt'])
    for r in residuals:r.update(by_event.get((str(r['eventId']),r['team']),{}))
    boxscores.write_json(root/'residual-context.json',dict(inputHash=fingerprint,rows=residuals,reconstructed=True))
    cohorts={'train':[],'test':[]};holds=defaultdict(int);eligible={'train':0,'test':0};day_models={}
    for day in plan['dates']:
        cohort='train' if plan['dates'].index(day)<plan['split'] else 'test'
        packet=packets.get(day,{})
        for r in records:
            if r['season']!=2026 or r.get('type')!=2 or str(boxscores.instant(r['kickoff']).astimezone(EASTERN).date())!=day:continue
            eligible[cohort]+=1
            if packet.get('state')!='observed':holds['archive unavailable']+=1;continue
            clock=boxscores.instant(packet['reportedAt'])
            feature,reasons=model.features(game(r),packet,{},boxes,residuals,clock,retrospective=True)
            if reasons:
                for reason in reasons:holds[reason.split(': ',1)[-1]]+=1
                continue
            if day not in day_models:
                past=[x for x in records if boxscores.instant(x['kickoff'])+timedelta(hours=6)<=clock]
                day_models[day]=paper.model_for('NBA',2026,clock.timestamp(),records=past)
            baseline=day_models[day].predict(r['home']['id'],r['away']['id'])
            cohorts[cohort].append(dict(eventId=r['eventId'],day=day,feature=feature,baseline=baseline,
                actualHome=r['homeScore'],actualAway=r['awayScore'],close=r.get('close',{})))
    if coverage_only:
        return dict(coverageOnly=True,cohorts={k:len(rows) for k,rows in cohorts.items()},
            coreAbsenceGames={k:sum(any(t['rotation']['coreOut'] for t in r['feature']['teams'].values()) for r in rows) for k,rows in cohorts.items()},
            holds=dict(holds),eligible=eligible)
    study_hash=hashlib.sha256(Path(model.__file__).read_bytes()+Path(__file__).read_bytes()).hexdigest()
    if (root/'validation.json').exists():
        prior=json.loads((root/'validation.json').read_text())
        if prior.get('studySourceHash')!=study_hash:
            raise ValueError('Test cohort already exposed; a changed model needs a new study/cohort')
        return prior
    training=[]
    for r in cohorts['train']:
        baseline=r['baseline'];xs=model.vectors(r['feature'])
        training.extend((x,actual-(baseline['total']+sign*baseline['margin'])/2)
                        for x,actual,sign in zip(xs,(r['actualHome'],r['actualAway']),(1,-1)))
    fitted=model.fit(training) if training else dict(coefficients=[0.,0.],featureBounds=[[0,0],[0,0]],policy=model.POLICY,version=model.VERSION)
    checks={};validated=[];tested=[]
    for r in cohorts['test']:
        try:adjusted=model.predict(r['baseline'],r['feature'],fitted)
        except ValueError:holds['correction outside support']+=1;continue
        tested.append(dict(r,adjusted={k:v for k,v in adjusted.items() if k!='feature'}))
    tested_all=tested
    # Research training can carry a conditional-available estimate without
    # claiming a Questionable player cleared. Promotion is measured exclusively
    # on the resolved-report population eligible for live admission.
    tested=[r for r in tested_all if not any(t['rotation'].get('unresolved') for t in r['feature']['teams'].values())]
    for family in ('margin','total'):
        actual=lambda r:r['actualHome']-r['actualAway'] if family=='margin' else r['actualHome']+r['actualAway']
        differences=[abs(actual(r)-r['baseline'][family])-abs(actual(r)-r['adjusted'][family]) for r in tested]
        ci=confidence(differences,[r['day'] for r in tested]) if tested else [None,None]
        base=statistics.mean(abs(actual(r)-r['baseline'][family]) for r in tested) if tested else None
        adjusted=statistics.mean(abs(actual(r)-r['adjusted'][family]) for r in tested) if tested else None
        quoted=[r for r in tested if model.number(r['close'].get('spread' if family=='margin' else 'total'))]
        key='spread' if family=='margin' else 'total'
        quoted_error=statistics.mean(abs(actual(r)-(-r['close'][key] if family=='margin' else r['close'][key])) for r in quoted) if quoted else None
        adjusted_on_quotes=statistics.mean(abs(actual(r)-r['adjusted'][family]) for r in quoted) if quoted else None
        briers=[]
        for r in quoted:
            line=-r['close'][key] if family=='margin' else r['close'][key]
            if actual(r)==line:continue
            outcome=actual(r)>line
            def chance(p):return .5*(1+math.erf((p[family]-line)/(p['sdMargin' if family=='margin' else 'sdTotal']*math.sqrt(2))))
            briers.append(((chance(r['baseline'])-outcome)**2,(chance(r['adjusted'])-outcome)**2))
        base_brier=statistics.mean(x for x,y in briers) if briers else None
        adjusted_brier=statistics.mean(y for x,y in briers) if briers else None
        absences=lambda rows:sum(any(t['rotation']['coreOut'] for t in r['feature']['teams'].values()) for r in rows)
        train_absences=absences(cohorts['train']);test_absences=absences(tested)
        winner_baseline=statistics.mean((r['baseline']['homeWinProb']-(r['actualHome']>r['actualAway']))**2 for r in tested) if tested else None
        winner_adjusted=statistics.mean((r['adjusted']['homeWinProb']-(r['actualHome']>r['actualAway']))**2 for r in tested) if tested else None
        passed=(len(cohorts['train'])>=30 and len(tested)>=30 and len(quoted)>=30
                and train_absences>=10 and test_absences>=10
                and len(tested)/max(1,eligible['test'])>=.25 and ci[0] is not None and ci[0]>0
                and adjusted_on_quotes<quoted_error and base_brier is not None and adjusted_brier<=base_brier
                and (family!='margin' or winner_adjusted<=winner_baseline))
        checks[family]=dict(passed=passed,trainGames=len(cohorts['train']),testGames=len(tested),conditionalResearchTestGames=len(tested_all),scheduledTestGames=eligible['test'],
            baselineMAE=base,adjustedMAE=adjusted,improvement95=ci,quotedGames=len(quoted),quotedLineMAE=quoted_error,
            adjustedMAEOnQuotedGames=adjusted_on_quotes,baselineBrier=base_brier,adjustedBrier=adjusted_brier)
        checks[family].update(trainCoreAbsenceGames=train_absences,testCoreAbsenceGames=test_absences,
            baselineWinnerBrier=winner_baseline,adjustedWinnerBrier=winner_adjusted)
        if passed:validated.append(family)
    report=dict(fitted,createdAt=boxscores.stamp(now),analysisOnly=not bool(validated),validatedFamilies=validated,
        checks=checks,holds=dict(holds),eligible=eligible,plan=plan,inputHash=fingerprint,
        sourceHash=hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest(),
        studySourceHash=study_hash,
        trainingHash=training_hash(records,boxes,plan),
        qualityGates=QUALITY_GATES,
        contextHash=hashlib.sha256(json.dumps(residuals,sort_keys=True).encode()).hexdigest(),
        archiveHash=hashlib.sha256(json.dumps(packets,sort_keys=True).encode()).hexdigest(),
        scope='Retrospective chronological development/test; not untouched forward validation or a profit record')
    boxscores.write_json(root/'validation.json',report)
    nba_capture.append_changed([dict(report,league='NBA',season=2026)],root/'validation-runs',lambda r:r['createdAt'])
    boxscores.write_json(root/'test-comparisons.json',dict(rows=tested,analysisOnly=True))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('collect','reparse','support','coverage','evaluate'));parser.add_argument('--repair',action='store_true');args=parser.parse_args()
    result=collect(repair=args.repair) if args.action=='collect' else reparse() if args.action=='reparse' else support() if args.action=='support' else evaluate(coverage_only=args.action=='coverage')
    print(json.dumps(result if args.action!='evaluate' else {k:result[k] for k in ('validatedFamilies','checks','holds','eligible')},indent=2))
