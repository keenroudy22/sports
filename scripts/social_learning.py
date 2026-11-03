"""Comparable-age editorial evidence. Never changes wagers, stakes or results."""
from statistics import median
import math
from datetime import timedelta
import gates

CHECKPOINTS = (24, 72, 168)


def checkpoint(entry, now):
    if not entry.get('bufferPostId') or not entry.get('sentAt') or entry.get('deletedAt'):
        return None
    age = (now - gates.when(entry['sentAt'])).total_seconds()/3600
    if age < 24 or age > 192:
        return None
    if not entry.get('metricsAt'):
        return max(h for h in CHECKPOINTS if h <= age)
    previous = (gates.when(entry['metricsAt']) - gates.when(entry['sentAt'])).total_seconds()/3600
    # No backfill pretending a late read was observed at an earlier checkpoint.
    eligible = [h for h in CHECKPOINTS if previous < h <= age]
    return max(eligible) if eligible and age <= 192 else None


def research_order(default, log_book, now):
    """Prefer mature, stronger research families; never replace a qualified ticket."""
    groups = {name: [] for name in default}
    for row in log_book.get('posts', []):
        parts = str(row.get('id','')).split(':')
        if len(parts)<3 or parts[0]!='research' or parts[1] not in groups:
            continue
        if not row.get('sentAt') or now-gates.when(row['sentAt']) > timedelta(days=56):
            continue
        snapshots = row.get('metricsHistory') or [dict(at=row.get('metricsAt'),metrics=row.get('metrics'))]
        for snap in snapshots:
            if not snap.get('at') or not snap.get('metrics'):
                continue
            age=(gates.when(snap['at'])-gates.when(row['sentAt'])).total_seconds()/3600
            value=snap['metrics'].get('impressions',snap['metrics'].get('views'))
            if 24<=age<=48 and isinstance(value,(int,float)) and value>=0:
                groups[parts[1]].append(value)
                break
    mature={name:median(values) for name,values in groups.items() if len(values)>=8}
    ordered=list(default)
    # Move only measured slots; sparse families keep their place for exploration.
    slots=[i for i,name in enumerate(ordered) if name in mature]
    ranked=sorted((ordered[i] for i in slots),key=lambda name:(-mature[name],default.index(name)))
    for i,name in zip(slots,ranked): ordered[i]=name
    return ordered, {name:dict(posts=len(groups[name]),median24hViews=value) for name,value in mature.items()}


def comparable_themes(log_book, now):
    """One actual24–48h read/post; missing or late snapshots stay missing."""
    groups={};seen=set()
    for e in log_book.get('posts',[]):
        if e.get('id') in seen or not e.get('sentAt') or e.get('deletedAt') or e.get('card') is False or e.get('cardTheme')=='none':continue
        if not str(e.get('kind','')).startswith('buffer:'):continue
        sent=gates.when(e['sentAt'])
        snapshots=e.get('metricsHistory') or [dict(at=e.get('metricsAt'),metrics=e.get('metrics'))]
        eligible=[]
        for snap in snapshots:
            try:
                at=gates.when(snap['at']);m=snap['metrics'];views=m.get('impressions',m.get('views'))
                if not sent<=at<=now or not 24<= (at-sent).total_seconds()/3600 <=48:continue
                if type(views) not in (int,float) or not math.isfinite(views) or views<0:continue
                rate=m.get('engagementRate')
                eligible.append((at,views,rate if type(rate) in (int,float) and math.isfinite(rate) else None))
            except (KeyError,TypeError,ValueError,AttributeError):continue
        if not eligible:continue
        seen.add(e['id']);at,views,rate=min(eligible,key=lambda v:v[0])
        key=(e['kind'].removeprefix('buffer:'),e.get('cardTheme') or 'legacy')
        groups.setdefault(key,[]).append((views,rate))
    return [dict(category=key[0],theme=key[1],posts=len(values),median24hViews=median(v[0] for v in values),
        medianEngagementRate=median(r for v,r in values if type(r) in (int,float)) if any(type(r) in (int,float) for v,r in values) else None,
        sampleFloorMet=len(values)>=8,scope='Recorded24–48h read age; provider refresh may lag. Observational, not a causal creative winner.')
        for key,values in sorted(groups.items())]
