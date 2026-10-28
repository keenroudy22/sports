"""Read-only current-season captured-price straight results, never a new record."""
from collections import defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import math
import record_scope


def report(rows,now=None):
 now=now or datetime.now(timezone.utc);groups=defaultdict(list);seen=set()
 for row in record_scope.current_rows(rows,now):
  if row.get('id') in seen:continue
  seen.add(row.get('id'))
  if (not record_scope.is_headline(row) or record_scope.is_parlay(row) or row.get('community')
      or row.get('historicalImport') and row.get('priceAssumed')
      or row.get('result') not in record_scope.RESULTS):continue
  odds=row.get('odds');settled=record_scope.instant(row.get('settledAt') or row.get('publishedAt'))
  if type(odds) not in (int,float) or not math.isfinite(odds) or abs(odds)<100 or not settled or settled>now:continue
  units=row.get('units')
  if type(units) not in (int,float) or not math.isfinite(units):continue
  kickoff=record_scope.instant(row.get('kickoff'))
  if not kickoff:continue
  weekday=kickoff.astimezone(ZoneInfo('America/Indiana/Indianapolis')).weekday()
  market=row.get('market') or row.get('marketType') or ('prop' if row.get('athleteId') else 'unknown')
  tier='Chef' if row.get('lane')=='chef_pick' else 'Ordinary'
  key=(record_scope.league_of(row),market,tier,'weekday' if weekday<5 else 'weekend')
  # Promotions remain outside captured-price performance, matching the main record.
  stake=row.get('riskUnits')
  captured=-float(stake) if row.get('earlyExit') and type(stake) in (int,float) else units
  groups[key].append((row,captured))
 result=[]
 for key,items in sorted(groups.items()):
  result.append(dict(zip(('league','market','tier','dayGroup'),key),
   wins=sum(r['result']=='win' for r,u in items),losses=sum(r['result']=='loss' for r,u in items),
   pushes=sum(r['result']=='push' for r,u in items),voids=sum(r['result']=='void' for r,u in items),
   units=round(sum(u for r,u in items),3),plays=len(items),
   deliveryBacked=sum(record_scope.reached_public(r) for r,u in items)))
 return dict(asOf=now.isoformat(),segments=result,scope='Current-season official captured-price straights; original stakes/results; no assumed prices, personal/fun tickets, Climb or NBA Trial',
             action='Diagnostic only. No automatic threshold, stake or model changes.')
