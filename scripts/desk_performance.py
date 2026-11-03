"""Read-only current-season captured-price straight results, never a new record."""
from collections import defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import math
import record_scope
import x_post
from statistics import mean


def probability_review(rows):
 scored=[];excluded=defaultdict(int)
 for r in rows:
  p=r.get('probabilityAtPublication') or {};chance=p.get('chance')
  if not p:excluded['missingSnapshot']+=1;continue
  published=record_scope.instant(r.get('publishedAt'));at=record_scope.instant(p.get('evaluatedAt'));kick=record_scope.instant(r.get('kickoff'))
  if not at or not published or not kick or not at<=published<kick:excluded['unverifiedPregameClock']+=1;continue
  if type(chance) not in (int,float) or not math.isfinite(chance) or not 0<chance<1:excluded['invalidChance']+=1;continue
  if r.get('earlyExit') or r['result'] not in ('win','loss') or p.get('push',0)!=0:excluded['pushOrEarlyExit']+=1;continue
  scored.append((r,chance,int(r['result']=='win')))
 groups=defaultdict(list)
 for r,p,y in scored:
  key=r.get('gameId') or (r.get('gameIds') or [None])[0]
  if key:groups[key].append((p-y)**2)
 return dict(scored=len(scored),independentGames=len(groups),excluded=dict(excluded),
  meanForecast=round(mean(p for r,p,y in scored),4) if scored else None,
  hitRate=round(mean(y for r,p,y in scored),4) if scored else None,
  brier=round(mean((p-y)**2 for r,p,y in scored),4) if scored else None,
  gameBalancedBrier=round(mean(mean(v) for v in groups.values()),4) if groups else None,
  scope='Frozen pre-publication binary claims only; pooled changing specifications, correlated games and small samples are diagnostic, not validation or new admission.')


def report(rows,now=None):
 now=now or datetime.now(timezone.utc);groups=defaultdict(list);seen=set()
 for row in record_scope.current_rows(rows,now):
  if row.get('id') in seen:continue
  seen.add(row.get('id'))
  if (not record_scope.is_headline(row) or record_scope.is_parlay(row) or row.get('community')
      or row.get('priceAssumed') or row.get('priceEstimated')
      or row.get('result') not in record_scope.RESULTS):continue
  odds=row.get('odds');settled=record_scope.instant(row.get('settledAt') or row.get('publishedAt'))
  if type(odds) not in (int,float) or not math.isfinite(odds) or abs(odds)<100 or not settled or settled>now:continue
  # Use the public record arithmetic for legacy priced rows without a saved net.
  units=0 if row['result']=='void' else x_post.units_for(row)
  if type(units) not in (int,float) or not math.isfinite(units):continue
  kickoff=record_scope.instant(row.get('kickoff'))
  if not kickoff:continue
  weekday=kickoff.astimezone(ZoneInfo('America/Indiana/Indianapolis')).weekday()
  market=row.get('market') or row.get('marketType') or ('prop' if row.get('athleteId') else 'unknown')
  tier='Chef' if row.get('lane')=='chef_pick' else 'Ordinary'
  key=(record_scope.league_of(row),market,tier,'weekday' if weekday<5 else 'weekend')
  # Promotions remain outside captured-price performance, matching the main record.
  stake=row.get('riskUnits') or 1
  captured=-float(stake) if row.get('earlyExit') and type(stake) in (int,float) else units
  groups[key].append((row,captured))
 result=[]
 for key,items in sorted(groups.items()):
  result.append(dict(zip(('league','market','tier','dayGroup'),key),
   wins=sum(r['result']=='win' for r,u in items),losses=sum(r['result']=='loss' for r,u in items),
   pushes=sum(r['result']=='push' for r,u in items),voids=sum(r['result']=='void' for r,u in items),
   units=round(sum(u for r,u in items),3),plays=len(items),
   recordUnits=round(sum(0 if r['result']=='void' else x_post.units_for(r) for r,u in items),3),
   marketFamily='prop' if all(r.get('athleteId') or r.get('kind')=='props' for r,u in items) else 'game',
   deliveryBacked=sum(record_scope.reached_public(r) for r,u in items),
   riskedUnits=round(sum((r.get('riskUnits') or 1) for r,u in items if r['result']!='void'),3),
   legacyUnitCalculations=sum(r.get('units') is None for r,u in items)))
 return dict(asOf=now.isoformat(),segments=result,probabilityReview=probability_review([r for items in groups.values() for r,u in items]),scope='Current-season official captured-price straights; original stakes/results; no assumed prices, personal/fun tickets, Climb or NBA Trial',
             action='Diagnostic only. No automatic threshold, stake or model changes.')
