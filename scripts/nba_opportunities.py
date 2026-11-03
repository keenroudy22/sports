"""Official rendered NBA tracking intake and observed-role research, never admission.

Browser observations are captured by the existing research task, not a hidden
browser or an undocumented stats API. Imported clocks remain their original
observation time. Unknown identities, absent tracking and unsubmitted reports
never become zeroes or clearance. Nothing here changes frozen forecasts.
"""
import argparse
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import boxscores
import gates
import nba_capture
import nba_official_availability as official
import nba_roles

HEADERS = {
 'passing': ['PLAYER','TEAM','GP','W','L','MIN','PassesMade','PassesReceived','AST','SecondaryAST','PotentialAST','ASTPTSCreated','ASTAdj','ASTToPass%','ASTToPass%Adj'],
 'rebounding': ['PLAYER','TEAM','GP','W','L','MIN','REB','ContestedREB','ContestedREB%','REBChances','REBChance%','DeferredREBChances','AdjustedREBChance%','AVGREBDistance']}
FIELDS = {'passing': {'assists':8, 'potentialAssists':10},
          'rebounding': {'rebounds':6, 'reboundChances':9}}


def fresh(at, now, hours=24):
    try:
        return timedelta(0) <= now-boxscores.instant(at) <= timedelta(hours=hours)
    except (ValueError, TypeError):
        return False


def normalize(packet, now):
    """Strict complete visible-table contract, including actually selected filters."""
    source=packet['source'];url=urlsplit(source)
    kind=url.path.rsplit('/',1)[-1]
    if (url.scheme!='https' or url.netloc!='www.nba.com' or url.path!=f'/stats/players/{kind}'
            or kind not in HEADERS or url.fragment or url.username):
        raise ValueError('Official tracking source unavailable')
    query=parse_qs(url.query,keep_blank_values=True)
    window='last3' if query=={'LastNGames':['3']} else 'season' if not query else None
    if not window: raise ValueError('Unsupported tracking window')
    controls=packet['controls']
    season=controls['season']
    if (not re.fullmatch(r'20\d{2}-\d{2}',season) or int(season[-2:])!=(int(season[:4])+1)%100
            or controls['seasonType']!='Regular Season' or controls['perMode']!='Per Game'
            or controls['segment']!=('Last 3 Games' if window=='last3' else 'All Season Segments')
            or controls['page']!='All' or packet['headers']!=HEADERS[kind]
            or not fresh(packet.get('observedAt'),now)):
        raise ValueError('Tracking filters, columns or observation clock unavailable')
    year=int(season[:4])+1
    local=now.astimezone(official.EASTERN)
    if year != local.year+(local.month>=10): raise ValueError('Tracking season is not current')
    raw=packet['rows']
    if not isinstance(raw,list) or not 1<=len(raw)<=700:raise ValueError('Tracking table missing or oversized')
    rows=[];seen=set()
    for entry in raw:
        cells=entry['cells'];path=urlsplit(entry['playerUrl'])
        identity=re.fullmatch(r'/stats/player/(\d+)/'+('rebounds-dash/' if kind=='rebounding' else ''),path.path)
        params=parse_qs(path.query)
        if (not identity or path.netloc or path.fragment or params.get('Season')!=[season]
                or params.get('SeasonType')!=['Regular Season'] or len(cells)!=len(HEADERS[kind])):
            raise ValueError('Tracking player or season identity unavailable')
        if not isinstance(cells[0],str) or not 1<=len(cells[0])<=100 or not re.fullmatch('[A-Z]{2,4}',cells[1]):
            raise ValueError('Tracking name/team unavailable')
        numbers=[]
        for value in cells[2:]:
            if not isinstance(value,str):raise ValueError('Tracking cell is not rendered text')
            number=float(value.replace(',',''))
            if not math.isfinite(number) or not 0<=number<=1000:raise ValueError('Invalid tracking number')
            numbers.append(number)
        gp,w,l,minutes=numbers[:4]
        if (gp!=int(gp) or gp<1 or w!=int(w) or l!=int(l) or w+l!=gp
                or not 0<=minutes<=60 or window=='last3' and gp>3):
            raise ValueError('Tracking sample/minutes unavailable')
        key=(identity[1],cells[1])
        if key in seen:raise ValueError('Duplicate tracking player/team')
        seen.add(key)
        metrics={name:float(cells[i]) for name,i in FIELDS[kind].items()}
        rows.append(dict(nbaId=identity[1],name=cells[0],teamAbbr=cells[1],games=int(gp),
                         minutes=minutes,metrics=metrics))
    return dict(league='NBA',season=year,seasonType=2,kind=kind,window=window,
        retrievedAt=packet['observedAt'],source=source,rows=rows,
        scope='Observed tracking, not expected minutes, probabilities or participation clearance')


def ingest(packets, now, root=nba_capture.STORE):
    rows=[normalize(p,now) for p in packets]
    keys=[(r['kind'],r['window']) for r in rows]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate tracking table in intake')
    # Validate the entire batch before any append; the immutable store records
    # actual source observations, not a new current clock or historical backfill.
    return nba_capture.append_changed(rows,Path(root)/'tracking',
        lambda r:(r['kind'],r['window'],r['retrievedAt']))


def observations(root, now):
    if boxscores.verify(Path(root)/'tracking'):
        raise ValueError('Tracking store integrity failed')
    latest={};conflicts=set()
    for path in (Path(root)/'tracking').glob('*.jsonl'):
        for r in boxscores.read_store(path):
            if not fresh(r.get('retrievedAt'),now):continue
            key=(r['season'],r['kind'],r['window']);at=boxscores.instant(r['retrievedAt'])
            previous=latest.get(key)
            if previous is None or at>boxscores.instant(previous['retrievedAt']):
                latest[key]=r;conflicts.discard(key)
            elif at==boxscores.instant(previous['retrievedAt']) and r!=previous:conflicts.add(key)
    return {k:r for k,r in latest.items() if k not in conflicts}


def context(athlete, team, season, roster, tables, now):
    if (roster.get('team')!=team or roster.get('season')!=season or roster.get('league')!='NBA'
            or not fresh(roster.get('retrievedAt'),now) or roster.get('identityOnly')):return []
    people=[p for p in roster.get('players',[]) if p.get('id')==athlete and p.get('active') is True]
    if len(people)!=1:return []
    name=official.normal(people[0]['name']);abbr=official.ALIASES.get(roster.get('abbreviation'),roster.get('abbreviation'))
    # ESPN roster packets do not all include abbreviation. The caller supplies
    # the fixture's team abbreviation after exact ESPN team/season validation.
    if not abbr:return []
    if sum(official.normal(p.get('name'))==name for p in roster['players'])!=1:return []
    result=[]
    for kind in HEADERS:
        season_table=tables.get((season,kind,'season'));recent_table=tables.get((season,kind,'last3'))
        if not season_table or not recent_table:continue
        pairs=[]
        for table in (season_table,recent_table):
            matches=[r for r in table['rows'] if r['teamAbbr']==abbr and official.normal(r['name'])==name]
            if len(matches)!=1:break
            pairs.append(matches[0])
        if len(pairs)!=2:continue
        base,recent=pairs
        if base['nbaId']!=recent['nbaId'] or recent['games']>base['games']:continue
        warnings=['Recent games overlap the season sample; tracking is not available for every game.']
        if kind=='passing' and any(p['metrics']['assists']>p['metrics']['potentialAssists'] for p in pairs):
            warnings.append('Assist and potential-assist definitions/coverage differ; no conversion probability calculated.')
        result.append(dict(kind=kind,nbaId=base['nbaId'],season={k:base[k] for k in ('games','minutes','metrics')},
            recent={k:recent[k] for k in ('games','minutes','metrics')},
            observedAt=min((season_table['retrievedAt'],recent_table['retrievedAt']),key=boxscores.instant),
            sources=[season_table['source'],recent_table['source']],warnings=warnings,
            analysisOnly=True,admissionReady=False))
    return result


def from_stores(now, root=nba_capture.STORE, target_date=None):
    root=Path(root)
    def read(path):
        try:return json.loads(path.read_text())
        except (OSError,ValueError):return {}
    target=str(target_date or gates.eastern_date(now))
    slate=read(root/'slate.json');injury=read(root/'injuries-current.json');tables=observations(root,now)
    boxes=[r for p in (root.parent/'sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    rows=[];missing=0
    quotes={}
    for p in (root/'player-quotes').glob('*.jsonl'):
        for q in boxscores.read_store(p):
            if (fresh(q.get('sourceAt'),now,4) and fresh(q.get('retrievedAt'),now,4)):
                key=(q['eventId'],q['athleteId'],q['stat'],q['book'])
                if key not in quotes or q['retrievedAt']>quotes[key]['retrievedAt']:quotes[key]=q
    for game in slate.get('games',[]) if fresh(slate.get('retrievedAt'),now) else []:
        if (game.get('status')!='scheduled' or game.get('seasonType')!='regular-season'
                or boxscores.instant(game['kickoff'])<=now or str(gates.eastern_date(boxscores.instant(game['kickoff'])))!=target):continue
        availability,holds=nba_capture.availability_for_game(injury,game,now,max_hours=1)
        if not fresh(injury.get('retrievedAt'),now,1):
            availability=[]
            holds={str(t['id']):'Current injury observation unavailable' for t in game['teams'].values()}
        for t in game['teams'].values():
            tid=str(t['id']);roster=read(root/'rosters'/f'{tid}.json');roster=dict(roster,abbreviation=t.get('abbreviation'))
            for player in roster.get('players',[]):
                evidence=context(player.get('id'),tid,game['season'],roster,tables,now)
                if not evidence:missing+=1;continue
                q=dict(athleteId=player['id'],team=tid,season=game['season'])
                role,role_hold=nba_roles.current_role(q,boxes,now)
                own=[a for a in availability if a.get('team')==tid and a.get('athleteId')==player['id']]
                status=[a.get('status') for a in own if nba_capture.blocks_availability(a.get('status'))]
                teammate_absences=[dict(name=a.get('name'),status=a.get('status')) for a in availability
                    if a.get('team')==tid and a.get('athleteId')!=player['id'] and nba_capture.blocks_availability(a.get('status'))]
                priced=[{k:p.get(k) for k in ('stat','line','over','under','book','sourceAt')}
                    for p in quotes.values() if p['eventId']==str(game['providerId']) and p['athleteId']==player['id']
                    and p['team']==tid and p['season']==game['season'] and p['kickoff']==game['kickoff']]
                rows.append(dict(eventId=str(game['providerId']),athleteId=player['id'],name=player['name'],team=tid,
                    kickoff=game['kickoff'],opportunities=evidence,currentRole=role,roleHold=role_hold,
                    availabilityHold=holds.get(tid) or (' / '.join(status) if status else None),
                    teammateDesignations=teammate_absences,prices=priced,
                    analysisOnly=True,admissionReady=False))
    rows.sort(key=lambda r:(r['kickoff'],r['name'],r['athleteId']))
    return dict(asOf=boxscores.stamp(now),targetDate=target,analysisOnly=True,admissionReady=False,
        sourceTables=len(tables),players=len(rows),unmatchedPlayers=missing,rows=rows,
        note='Observed opportunities and roles. No teammate usage redistribution, conversion probability or automatic bet approval.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('ingest','research'))
    parser.add_argument('--input',action='append',default=[]);parser.add_argument('--root',type=Path,default=nba_capture.STORE)
    parser.add_argument('--target-date');parser.add_argument('--output',type=Path)
    args=parser.parse_args();now=datetime.now(timezone.utc)
    if args.command=='ingest':
        if not args.input:parser.error('ingest requires actual browser observation files')
        import deployment_lock
        packets=[json.loads(Path(p).read_text()) for p in args.input]
        with deployment_lock.bounded_lock(Path.home()/'.config/keenroudy/run.lock'):
            result={'ingested':ingest(packets,now,args.root)}
    else:result=from_stores(now,args.root,args.target_date)
    if args.output:
        destination=args.output.resolve();work=(nba_capture.ROOT/'work').resolve()
        if not destination.is_relative_to(work):parser.error('research output must remain in work')
        destination.parent.mkdir(parents=True,exist_ok=True);boxscores.write_json(destination,result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))

if __name__=='__main__':main()
