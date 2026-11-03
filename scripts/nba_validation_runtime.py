"""Complete a real scheduled quote capture after late browser source recovery.

No feed requests, retroactive forecasts, model tuning or approval changes. An
actual fresh official-report observation can complete this capture only within
its original hour; old or replayed evidence cannot manufacture a missing slot.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import boxscores
import nba_capture
import nba_player_props as props
import nba_prop_probability as probability

START=datetime(2026,11,3,22,tzinfo=timezone.utc)


def finish(root,now):
    root=Path(root)
    def held(reason):return dict(state='held',reason=reason,admissionReady=False,requests=0)
    def fresh(value,hours=1):
        try:return timedelta(0)<=now-boxscores.instant(value)<=timedelta(hours=hours)
        except (ValueError,TypeError):return False
    if now<START:return held('Source-completion route not active at this clock')
    families=('observations','player-quotes','player-forecasts','player-outcomes','official-availability','source-completions')
    if any(boxscores.verify(root/family) for family in families):return held('NBA evidence integrity failure')
    try:
        injury=json.loads((root/'injuries-current.json').read_text());report=injury['official']
        if (report.get('observedMethod')!='Reviewed ordinary-browser official PDF'
                or not report.get('browserPdfSha256') or not fresh(report.get('reportedAt'))
                or not fresh(report.get('retrievedAt')) or not fresh(injury.get('retrievedAt'),4)
                or boxscores.instant(report['retrievedAt'])<START):
            return held('Fresh actual report/PDF and provider observation required')
        def latest_received(rows,key):
            latest={};conflicts=set()
            for row in rows:
                try:
                    at=boxscores.instant(row['retrievedAt']);identity=key(row)
                    if at>now:continue
                    if identity not in latest or at>boxscores.instant(latest[identity]['retrievedAt']):
                        latest[identity]=row;conflicts.discard(identity)
                    elif at==boxscores.instant(latest[identity]['retrievedAt']) and row!=latest[identity]:conflicts.add(identity)
                except (ValueError,KeyError,TypeError):continue
            return {k:r for k,r in latest.items() if k not in conflicts}
        captures=[r for r in latest_received(probability.read(root/'observations'),lambda r:r['slot']).values()
                  if r.get('scheduled') is True and fresh(r.get('slot'),1.5) and fresh(r.get('retrievedAt'))
                  and boxscores.instant(r['slot'])<=boxscores.instant(r['retrievedAt'])<=boxscores.instant(report['retrievedAt'])]
        if not captures:return held('No recent actual scheduled NBA capture to complete')
        capture=max(captures,key=lambda r:boxscores.instant(r['retrievedAt']))
        slot=boxscores.instant(capture['slot']);received=boxscores.instant(report['retrievedAt'])
        receipt_id='browser-source-completion:'+boxscores.stamp(received)
        previous=[r for r in probability.read(root/'source-completions') if r.get('id')==receipt_id]
        if previous:return dict(previous[-1],state='already-completed')
        latest=latest_received(probability.read(root/'player-quotes'),lambda q:tuple(q[k] for k in ('eventId','athleteId','stat','book')))
        latest={key:q for key,q in latest.items() if fresh(q.get('retrievedAt')) and fresh(q.get('sourceAt'))
                and slot<=boxscores.instant(q['retrievedAt'])<=received
                and boxscores.instant(report['reportedAt'])<=boxscores.instant(q['retrievedAt'])
                and boxscores.instant(injury['retrievedAt'])<=boxscores.instant(q['retrievedAt'])
                and q.get('source')=='https://sharpapi.io' and q.get('sideVerified') is True
                and q.get('kind')=='main' and q.get('stat') in probability.STATS}
        eligible={(*key,q['sourceAt']) for key,q in latest.items()}
        if not eligible:return held('No fresh paired primary quotes from that scheduled capture')
    except (OSError,ValueError,KeyError,TypeError):return held('Source completion evidence unavailable')
    # Selection still goes through every unchanged roster/participation/role
    # check. Record only the actual current computation, never the missing slot.
    added=props.record_forward(now,root,eligible_quotes=eligible)
    graded=props.grade(now,root)
    import nba_prop_release
    frozen=nba_prop_release.freeze(root,now)
    study=probability.capture(root,now)
    import nba_dispersion_shadow
    experiment=nba_dispersion_shadow.capture(root,now)
    receipt=dict(id=receipt_id,league='NBA',season=injury['season'],
        retrievedAt=boxscores.stamp(now),scheduledSlot=capture['slot'],reportObservedAt=report['retrievedAt'],
        reportSource=report['source'],eligibleQuotes=len(eligible),forwardRecorded=added,forwardGraded=graded,
        releaseProtocolRecorded=frozen,probabilityRecorded=study['recorded'],volumeExperimentRecorded=experiment['recorded'],
        state='completed',requests=0,admissionReady=False)
    nba_capture.append_changed([receipt],root/'source-completions',lambda r:r['id'])
    return receipt
