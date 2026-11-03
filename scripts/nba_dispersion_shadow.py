"""Prospective volume-scaled residual experiment; cannot approve or publish bets.

Exposed baseline outcomes train once. Only later physical pregame forecasts test.
Sqrt(1+mean) scaling is fixed before test outcomes; no volume-band tuning. It
changes uncertainty, not the historical mean or injury/teammate assumptions.
"""
import hashlib,json,math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo
import boxscores,nba_capture
import nba_prop_probability as baseline

VERSION='nba-volume-residual-shadow-v1'
STATS=baseline.STATS


def implementation_hash():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def fit(pairs,stat,now):
    groups=defaultdict(list);evidence=[]
    for row,outcome in pairs:
        if row['stat']!=stat:continue
        value=row['projection']['value']
        if not baseline.numeric(value) or value<0:continue
        groups[row['eventId']].append((outcome['actual']-value)/math.sqrt(1+value))
        evidence.append(dict(forecastId=row['id'],forecastHash=baseline.digest(row),outcomeHash=baseline.digest(outcome)))
    if len(groups)<30:return None
    spec=dict(id=VERSION+':'+stat,model=VERSION,stat=stat,season=now.year,
        createdAt=boxscores.stamp(now),retrievedAt=boxscores.stamp(now),
        implementationHash=implementation_hash(),trainingEvents=sorted(groups),trainingEvidence=evidence,
        standardizedResiduals={k:sorted(v) for k,v in sorted(groups.items())},
        scale='sqrt(1+baseline_mean)',marketAnchor=.5,minimumGames=30,minimumDates=5,
        admissionReady=False,analysisOnly=True)
    spec['specHash']=baseline.digest(spec);return spec


def valid(spec):
    try:
        return (spec['model']==VERSION and spec['stat'] in STATS and spec['implementationHash']==implementation_hash()
            and spec['specHash']==baseline.digest({k:v for k,v in spec.items() if k!='specHash'})
            and spec['scale']=='sqrt(1+baseline_mean)' and spec['marketAnchor']==.5
            and spec['minimumGames']==30 and spec['minimumDates']==5
            and len(set(spec['trainingEvents']))>=30 and set(spec['trainingEvents'])==set(spec['standardizedResiduals'])
            and all(values and all(baseline.numeric(v) for v in values) for values in spec['standardizedResiduals'].values()))
    except (KeyError,ValueError,TypeError):return False


def predict(row,spec,now):
    try:
        if (not valid(spec) or row.get('model')!=baseline.BASELINE or row.get('hold') or row['stat']!=spec['stat']
            or row['eventId'] in spec['trainingEvents'] or not boxscores.instant(spec['createdAt'])<=boxscores.instant(row['retrievedAt'])<=now<boxscores.instant(row['kickoff'])):return None
        value,line,over,under=row['projection']['value'],row['line'],row['over'],row['under']
        if not all(baseline.numeric(v) for v in (value,line,over,under)) or value<0 or line%1!=.5 or min(abs(over),abs(under))<100:return None
        implied=lambda odds:100/(100+odds) if odds>0 else -odds/(100-odds)
        a,b=implied(over),implied(under)
        if not .99<=a+b<=1.15:return None
        empirical=mean(mean(value+z*math.sqrt(1+value)>line for z in group) for group in spec['standardizedResiduals'].values())
        return dict(id=':'.join((VERSION,row['stat'],row['eventId'],row['athleteId'])),model=VERSION,season=row['season'],
            eventId=row['eventId'],athleteId=row['athleteId'],stat=row['stat'],specHash=spec['specHash'],forecastId=row['id'],
            originalHash=baseline.digest(row),forecastAt=row['retrievedAt'],retrievedAt=boxscores.stamp(now),kickoff=row['kickoff'],
            line=line,book=row['book'],over=over,under=under,chanceOver=.5*empirical+.5*a/(a+b),marketOver=a/(a+b),
            analysisOnly=True,admissionReady=False)
    except (KeyError,ValueError,TypeError,ZeroDivisionError):return None


def review(root,now):
    root=Path(root)
    if any(boxscores.verify(root/f) for f in ('dispersion-specs','dispersion-forecasts','player-forecasts','player-outcomes')):
        raise ValueError('NBA experiment evidence integrity failure')
    specs={s['specHash']:s for s in baseline.read(root/'dispersion-specs') if valid(s)}
    originals={}
    for r in baseline.read(root/'player-forecasts'):originals.setdefault(r['id'],r)
    outcomes={}
    for o in baseline.read(root/'player-outcomes'):
        try:
            at=boxscores.instant(o['retrievedAt'])
            if at<=now and (o['id'] not in outcomes or at>boxscores.instant(outcomes[o['id']]['retrievedAt'])):outcomes[o['id']]=o
        except (KeyError,ValueError,TypeError):continue
    groups=defaultdict(lambda:defaultdict(list))
    first={}
    for p in baseline.read(root/'dispersion-forecasts'):
        try:
            if boxscores.instant(p['retrievedAt'])>now:continue
            key=(p['eventId'],p['athleteId'],p['stat'],p['specHash'])
            if key not in first or (p['retrievedAt'],p['id'])<(first[key]['retrievedAt'],first[key]['id']):first[key]=p
        except (KeyError,ValueError,TypeError):continue
    for p in first.values():
        try:
            spec=specs.get(p['specHash']);original=originals.get(p['forecastId']);outcome=outcomes.get(p['forecastId'])
            if (not spec or not original or not outcome or not boxscores.instant(p['retrievedAt'])<boxscores.instant(p['kickoff'])<=boxscores.instant(outcome['retrievedAt'])<=now
                or predict(original,spec,boxscores.instant(p['retrievedAt']))!=p
                or outcome.get('forecastAt')!=original['retrievedAt'] or outcome.get('model')!=baseline.BASELINE
                or not outcome.get('source') or not baseline.numeric(outcome.get('actual'))
                or any(outcome.get(k)!=original.get(k) for k in ('line','book','side','odds'))
                or outcome.get('projection')!=original['projection']['value']):continue
            y=float(outcome['actual']>p['line']);expected='hit' if bool(y)==(original['side']=='over') else 'miss'
            if outcome.get('result')!=expected:continue
            groups[(p['stat'],p['specHash'])][p['eventId']].append((p,y))
        except (KeyError,ValueError,TypeError):continue
    result=[]
    for spec in specs.values():
        games=groups[(spec['stat'],spec['specHash'])];days=defaultdict(list);errors=[]
        for group in games.values():
            day=boxscores.instant(group[0][0]['kickoff']).astimezone(ZoneInfo('America/New_York')).date().isoformat()
            error=mean((p['marketOver']-y)**2-(p['chanceOver']-y)**2 for p,y in group);days[day].append(error);errors.append(error)
        lower=baseline.lower95([mean(v) for v in days.values()]);holds=[]
        if len(games)<30:holds.append('Fewer than30 new independent test games')
        if len(days)<5:holds.append('Fewer than5 new Eastern dates')
        if lower is None or lower<=0:holds.append('Probability improvement unproven')
        result.append(dict(model=VERSION,stat=spec['stat'],specHash=spec['specHash'],games=len(games),easternDates=len(days),
            brierImprovement=mean(errors) if errors else None,descriptiveLower95=lower,
            probabilityEvidenceReady=not holds,evidenceHolds=holds,admissionReady=False,analysisOnly=True,
            note='Unpromoted uncertainty experiment; no current-opportunity conversion, injury redistribution or official-book profit proof.'))
    return result


def capture(root,now):
    root=Path(root)
    for family in ('player-forecasts','player-outcomes','dispersion-specs','dispersion-forecasts'):
        if boxscores.verify(root/family):raise ValueError('NBA experiment evidence integrity failure')
    specs={s['stat']:s for s in baseline.read(root/'dispersion-specs') if s.get('model')==VERSION}
    training=baseline.pairs(baseline.read(root/'player-forecasts'),baseline.read(root/'player-outcomes'),now)
    new=[s for stat in STATS if stat not in specs and (s:=fit(training,stat,now))]
    nba_capture.append_changed(new,root/'dispersion-specs',lambda r:r['id']);specs.update({s['stat']:s for s in new})
    ids={r['id'] for r in baseline.read(root/'dispersion-forecasts')};rows=[]
    for row in sorted(baseline.read(root/'player-forecasts'),key=lambda r:(r.get('retrievedAt',''),r.get('book',''),r.get('id',''))):
        spec=specs.get(row.get('stat'));p=predict(row,spec,now) if spec else None
        if p and p['id'] not in ids:rows.append(p);ids.add(p['id'])
    count=nba_capture.append_changed(rows,root/'dispersion-forecasts',lambda r:r['id'])
    return dict(model=VERSION,recorded=count,specifications=len(specs),review=review(root,now),admissionReady=False)
