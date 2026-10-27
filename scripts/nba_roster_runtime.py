"""Current-game roster research and strict, per-family Trial eligibility.

Historical experiment success is checked from measured fields, not a manually
flipped ready flag. Missing support yields a specific hold and retains baseline.
"""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

import boxscores
import hoops_store
import nba_capture
import nba_roles
import nba_roster_model as model
import nba_roster_validation as validation

ROOT=Path(__file__).resolve().parents[1]
STORE=validation.STORE


def next_runtime(root):
    # Keep the frozen v1 study; the new experiment remains per-family gated.
    if Path(root) != STORE: return None
    import nba_roster_runtime_v3 as newer
    return newer if (newer.STORE/'validation.json').exists() else None


def read(path,fallback):
    try:
        value=json.loads(Path(path).read_text())
        return value if isinstance(value,type(fallback)) else fallback
    except (OSError,ValueError):return fallback


def quality(packet):
    """Reject thin/negative tests even if validatedFamilies was hand-set."""
    if not isinstance(packet,dict):return []
    if packet.get('version')!=model.VERSION or packet.get('policy')!=model.POLICY:return []
    if packet.get('qualityGates')!=validation.QUALITY_GATES:return []
    coefficients=packet.get('coefficients',[])
    if not isinstance(coefficients,list) or len(coefficients)!=2 or not all(model.number(x) for x in coefficients):return []
    if not isinstance(packet.get('checks'),dict):return []
    allowed=[]
    for family in ('margin','total'):
        c=packet.get('checks',{}).get(family,{})
        if not isinstance(c,dict):continue
        try:
            if (c['trainGames']>=30 and c['testGames']>=30 and c['quotedGames']>=30
                and c['trainCoreAbsenceGames']>=10 and c['testCoreAbsenceGames']>=10
                and c['testGames']/max(1,c['scheduledTestGames'])>=.25
                and model.number(c['improvement95'][0]) and c['improvement95'][0]>0
                and model.number(c['adjustedMAEOnQuotedGames']) and model.number(c['quotedLineMAE'])
                and c['adjustedMAEOnQuotedGames']<c['quotedLineMAE']
                and model.number(c['baselineBrier']) and model.number(c['adjustedBrier'])
                and c['adjustedBrier']<=c['baselineBrier']
                and (family!='margin' or model.number(c['baselineWinnerBrier'])
                     and model.number(c['adjustedWinnerBrier']) and c['adjustedWinnerBrier']<=c['baselineWinnerBrier'])):allowed.append(family)
        except (KeyError,TypeError,ValueError,IndexError,ZeroDivisionError):continue
    return allowed


def _current(game,baseline,now,capture_root=nba_capture.STORE,root=STORE,*,boxes=None):
    root=Path(root);capture_root=Path(capture_root)
    packet=read(root/'validation.json',{})
    if not packet:return dict(holds=['Roster model has no completed validation'],validatedFamilies=[],prediction=None)
    expected_hash=hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest()
    if packet.get('sourceHash')!=expected_hash:return dict(holds=['Roster model source changed since validation'],validatedFamilies=[],prediction=None)
    study_hash=hashlib.sha256(Path(model.__file__).read_bytes()+Path(validation.__file__).read_bytes()).hexdigest()
    if packet.get('studySourceHash')!=study_hash:return dict(holds=['Roster experiment changed since validation'],validatedFamilies=[],prediction=None)
    try:clock_valid=boxscores.instant(packet.get('createdAt'))<=now
    except (ValueError,TypeError):clock_valid=False
    if not clock_valid:
        return dict(holds=['Roster validation is future-dated'],validatedFamilies=[],prediction=None)
    injury=read(capture_root/'injuries-current.json',{})
    rows,source_holds=nba_capture.availability_for_game(injury,game,now,max_hours=1)
    if source_holds:return dict(holds=sorted(set(source_holds.values())),validatedFamilies=[],prediction=None)
    try:
        for (event,athlete),review in nba_roles.reviews(capture_root,now).items():
            if event!=str(game['providerId']):continue
            if review.get('hold') or review['kind'] in ('reported-minutes','analyst-estimate'):
                return dict(holds=[review.get('hold') or 'Game-specific minutes review requires a separately supported rotation'],validatedFamilies=[],prediction=None)
    except (OSError,ValueError,KeyError,TypeError):return dict(holds=['Role-review source integrity unavailable'],validatedFamilies=[],prediction=None)
    if boxes is None:boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    rosters={p.stem:read(p,{}) for p in (capture_root/'rosters').glob('*.json')}
    context=read(root/'residual-context.json',{}).get('rows',[])
    if hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()!=packet.get('contextHash'):
        return dict(holds=['Roster comparison context integrity mismatch'],validatedFamilies=[],prediction=None)
    if boxscores.verify(root/'residual-forward'):
        return dict(holds=['Forward roster context integrity failure'],validatedFamilies=[],prediction=None)
    for path in (root/'residual-forward').glob('*.jsonl'):
        context.extend(r for r in boxscores.read_store(path) if r.get('sourceHash')==expected_hash
                       and boxscores.instant(r['computedAt'])<=now)
    try:
        feature,holds=model.features(game,injury['official'],rosters,boxes,context,now)
        if holds:return dict(holds=holds,validatedFamilies=[],prediction=None)
        p=model.predict(baseline,feature,packet)
    except (KeyError,TypeError,ValueError,OverflowError) as error:
        return dict(holds=['Roster evidence unavailable: '+str(error)[:160]],validatedFamilies=[],prediction=None)
    archives={r['day']:r for p in (root/'availability').glob('*.jsonl') for r in boxscores.read_store(p)}
    verified=(packet.get('trainingHash')==validation.training_hash(hoops_store.load('NBA'),boxes,packet['plan'])
              and not boxscores.verify(root/'availability')
              and packet.get('archiveHash')==hashlib.sha256(json.dumps(archives,sort_keys=True).encode()).hexdigest())
    families=quality(packet) if verified else []
    return dict(holds=[] if families else ['Roster experiment has not passed the held-out quality checks'],
        validatedFamilies=families,prediction=p,analysisOnly=not bool(families),
        validationAt=packet['createdAt'],reportedAt=feature['reportedAt'],source=feature['source'])


def record_forward(now=None,capture_root=nba_capture.STORE,root=STORE):
    newer=next_runtime(root)
    if newer:return newer.record_forward(now,capture_root=capture_root)
    now=now or datetime.now(timezone.utc);root=Path(root)
    slate=read(Path(capture_root)/'slate.json',{});old={r['eventId'] for p in (root/'forward').glob('*.jsonl') for r in boxscores.read_store(p)}
    out=[];holds=[];models={}
    import paper
    for game in slate.get('games',[]):
        if game['status']!='scheduled' or not now<boxscores.instant(game['kickoff']):continue
        if game['season'] not in models:models[game['season']]=paper.model_for('NBA',game['season'],now.timestamp())
        baseline=models[game['season']].predict(game['teams']['home']['id'],game['teams']['away']['id'])
        result=current(game,baseline,now,capture_root,root)
        if not result.get('prediction'):
            holds.append(dict(eventId=game['providerId'],holds=result['holds']));continue
        if game['providerId'] in old:continue
        captured=datetime.now(timezone.utc)
        if captured>=boxscores.instant(game['kickoff']):continue
        out.append(dict(league='NBA',season=game['season'],eventId=game['providerId'],kickoff=game['kickoff'],
            capturedAt=boxscores.stamp(captured),model=model.VERSION,baseline=baseline,**result,
            scope='Frozen forward roster research, not an official bet or public record'))
    count=nba_capture.append_changed(out,root/'forward',lambda r:r['eventId'])
    return dict(newForecasts=count,holds=holds)


def grade(now=None,root=STORE,boxes=None):
    newer=next_runtime(root)
    newer_count=newer.grade(now,boxes=boxes) if newer else 0
    now=now or datetime.now(timezone.utc);root=Path(root)
    if boxes is None:boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    finals={str(b['eventId']).removeprefix('NBA-'):b for b in nba_roles.available_boxes(boxes,now)}
    old={r['eventId']:r for p in (root/'outcomes').glob('*.jsonl') for r in boxscores.read_store(p)};rows=[]
    for path in (root/'forward').glob('*.jsonl'):
        for forecast in boxscores.read_store(path):
            final=finals.get(forecast['eventId'])
            if not final:continue
            teams=list(final['teams'].values())
            home=[t for t in teams if t['home']];away=[t for t in teams if not t['home']]
            if len(home)!=1 or len(away)!=1:continue
            actual=dict(total=home[0]['score']+away[0]['score'],margin=home[0]['score']-away[0]['score'])
            if old.get(forecast['eventId'],{}).get('actual')==actual:continue
            rows.append(dict(league='NBA',season=forecast['season'],eventId=forecast['eventId'],
                forecastAt=forecast['capturedAt'],model=model.VERSION,actual=actual,gradedAt=boxscores.stamp(now),
                baselineErrors={k:abs(v-forecast['baseline'][k]) for k,v in actual.items()},
                adjustedErrors={k:abs(v-forecast['prediction'][k]) for k,v in actual.items()},
                analysisOnly=True,source=final.get('source')))
    return newer_count+nba_capture.append_changed(rows,root/'outcomes',lambda r:r['eventId'])


def extend_context(now=None,root=STORE,capture_root=nba_capture.STORE):
    """Add only new completed games; no refitting, new calls or old-row rewrites."""
    newer=next_runtime(root)
    if newer:return newer.extend_context(now,capture_root=capture_root)
    now=now or datetime.now(timezone.utc);root=Path(root)
    packet=read(root/'validation.json',{})
    try:
        if packet.get('sourceHash')!=hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest():return 0
        if boxscores.instant(packet.get('createdAt'))>now:return 0
    except (ValueError,TypeError):return 0
    frozen=read(root/'residual-context.json',{}).get('rows',[])
    existing=frozen+[r for p in (root/'residual-forward').glob('*.jsonl') for r in boxscores.read_store(p)]
    known={str(r['eventId']) for r in existing}
    records=hoops_store.load('NBA')
    new={str(r['eventId']) for r in records if r['season']>=2027 and r.get('type')==2
         and str(r['eventId']) not in known and boxscores.instant(r['kickoff']).timestamp()+21600<=now.timestamp()}
    if not new:return 0
    rows=model.residual_history(records,now,only_events=new)
    packets=[r for p in (Path(capture_root)/'official-availability').glob('*.jsonl') for r in boxscores.read_store(p)]
    by_id={str(r['eventId']):r for r in records}
    for row in rows:
        game=by_id[row['eventId']];kickoff=boxscores.instant(game['kickoff'])
        available=sorted((p for p in packets if boxscores.instant(p['retrievedAt'])<kickoff),key=lambda p:p['retrievedAt'])
        for packet in available:
            for team in packet.get('teams',[]):
                if team['eventId']==row['eventId'] and team['team']==row['team'] and team['submitted'] is True and not team['unmapped']:
                    row.update(verifiedOut=[p['athleteId'] for p in team['rows'] if p['status']=='Out'],absenceSource=packet['source'],absenceReportAt=packet['reportedAt'])
        row.update(league='NBA',season=game['season'],computedAt=boxscores.stamp(now),sourceHash=hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest())
    return nba_capture.append_changed(rows,root/'residual-forward',lambda r:(r['eventId'],r['team']))


def summary(root=STORE):
    newer=next_runtime(root)
    if newer:return newer.summary()
    root=Path(root);forecasts={r['eventId']:r for p in (root/'forward').glob('*.jsonl') for r in boxscores.read_store(p)}
    outcomes={r['eventId']:r for p in (root/'outcomes').glob('*.jsonl') for r in boxscores.read_store(p)}
    pairs=[r for key,r in outcomes.items() if key in forecasts]
    return dict(model=model.VERSION,forecasts=len(forecasts),gradedGames=len(pairs),
        errors={k:dict(baseline=sum(r['baselineErrors'][k] for r in pairs)/len(pairs),
                       adjusted=sum(r['adjustedErrors'][k] for r in pairs)/len(pairs)) for k in ('margin','total')} if pairs else {},
        scope='Frozen forward research errors, not an official or hypothetical profit record')


def current(game,baseline,now,capture_root=nba_capture.STORE,root=STORE,*,boxes=None):
    """Malformed evidence holds this experiment, never crashes the normal desk."""
    newer=next_runtime(root)
    if newer:return newer.current(game,baseline,now,capture_root,boxes=boxes)
    try:return _current(game,baseline,now,capture_root,root,boxes=boxes)
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError,OverflowError):
        return dict(holds=['Roster evidence integrity unavailable'],validatedFamilies=[],prediction=None)


def apply_validated(baseline,result):
    """One shared forecast for website and selection; failed tests never alter it."""
    out=dict(baseline);p=result.get('prediction') or {}
    families=set(result.get('validatedFamilies',[])) & {'margin','total'}
    for family,sd in (('margin','sdMargin'),('total','sdTotal')):
        if family not in families:continue
        if not all(model.number(p.get(k)) for k in (family,sd)) or p[sd]<=0:
            families.discard(family);continue
        if family=='margin' and (not model.number(p.get('homeWinProb')) or not 0<=p['homeWinProb']<=1):
            families.discard(family);continue
        out[family]=p[family];out[sd]=p[sd]
        if family=='margin':out['homeWinProb']=p['homeWinProb']
    return out,sorted(families)


def public_context(result,families):
    """Compact research scope, never expose archive internals as live evidence."""
    return dict(adjustedMarkets=families,
        note=('Roster-adjusted '+', '.join(families)+'. Research, not a bet.' if families else
              'Baseline score model. No validated roster adjustment is applied.'),
        holds=list(result.get('holds',[]))[:2],reportedAt=result.get('reportedAt'),source=result.get('source'))
