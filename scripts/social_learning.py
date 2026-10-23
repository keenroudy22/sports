"""Comparable-age editorial evidence. Never changes wagers, stakes or results."""
from statistics import median
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
