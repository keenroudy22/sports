"""Free nflverse Q1 fallback; exact game/player identities and full-game checks.

Only observed NFL rushing/receiving. No model, pick, price or wager settlement.
"""
import copy
from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import boxscores as bx

PBP = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz'
PAGE = 'https://github.com/nflverse/nflverse-data/releases/tag/pbp'
ALIASES = {'LA':'LAR', 'WAS':'WSH'}
STATS = ('car','rushYds','rec','recYds','att','cmp','passYds')


def number(value):
    if value in (None,'','NA'):
        return None
    try:
        n=float(value)
        return int(n) if n==int(n) else None
    except (TypeError,ValueError,OverflowError):
        return None


def extract(rows, record, crosswalk, zero_proofs=None, diagnostics=None):
    """Return independently reconciled families; reject partial/wrong game feeds."""
    if not rows:
        return {}, ['missing game']
    norm=lambda t:ALIASES.get(t,t)
    home,away=record['home'],record['away']
    teams={home['abbreviation']:home['id'],away['abbreviation']:away['id']}
    expected={tid:record['teams'][tid]['plays'] for tid in teams.values()}
    ids=[r.get('play_id') for r in rows]
    if not all(ids) or len(set(ids))!=len(ids) or len({r.get('game_id') for r in rows})!=1:
        return {},['duplicate or ambiguous play identities']
    full,first,counts=defaultdict(Counter),defaultdict(Counter),Counter()
    seen=set()
    try:
        for r in rows:
            if (norm(r.get('home_team'))!=home['abbreviation'] or norm(r.get('away_team'))!=away['abbreviation']
                or r.get('game_date')!=bx.instant(record['kickoff']).astimezone(ZoneInfo('America/New_York')).date().isoformat()
                or r.get('season_type')!='REG' or number(r.get('season'))!=record['season']
                or number(r.get('home_score'))!=home['score'] or number(r.get('away_score'))!=away['score']):
                raise ValueError('game identity or final mismatch')
            if number(r.get('two_point_attempt'))==1:
                continue
            rush,passed,sack=(number(r.get(k))==1 for k in ('rush_attempt','pass_attempt','sack'))
            if not (rush or passed or sack):
                continue
            q=number(r.get('qtr'));team=teams.get(norm(r.get('posteam')))
            if q is None or not 1<=q<=20 or team is None:
                raise ValueError('unknown period or offense')
            counts[team]+=1
            if q==1:seen.add(team)
            values=[]
            if passed and not sack:
                completed=number(r.get('complete_pass'))
                if completed not in (0,1):
                    raise ValueError('unknown pass completion')
                yards=number(r.get('passing_yards')) if completed else 0
                values.append(('passer_player_id',{'att':1,'cmp':completed,'passYds':yards}))
            if rush:values.append(('rusher_player_id',{'car':1,'rushYds':number(r.get('rushing_yards'))}))
            if number(r.get('complete_pass'))==1:
                values.append(('receiver_player_id',{'rec':1,'recYds':number(r.get('receiving_yards'))}))
            if number(r.get('lateral_reception'))==1:
                values.append(('lateral_receiver_player_id',{'rec':0,'recYds':number(r.get('lateral_receiving_yards'))}))
            if number(r.get('lateral_rush'))==1:
                values.append(('lateral_rusher_player_id',{'car':0,'rushYds':number(r.get('lateral_rushing_yards'))}))
            for field,stats in values:
                aid=crosswalk.get(r.get(field))
                if not aid or any(v is None for v in stats.values()):
                    raise ValueError('unknown credited player or yards')
                official=next((p for p in record['players'] if p['id']==aid),None)
                if official is None or str(official['team'])!=team:
                    raise ValueError('credited player/team mismatch')
                full[aid].update(stats)
                if q==1:first[aid].update(stats)
        if dict(counts)!=expected or seen!=set(expected):
            raise ValueError('full-game team plays mismatch')
    except ValueError as error:
        return {},[str(error)]
    out,holds={},[]
    for p in record['players']:
        if not any(k in p for k in STATS):continue
        values={}
        for family in (('car','rushYds'),('rec','recYds'),('att','cmp','passYds')):
            if family[0]=='att' and not any(k in p for k in family):
                continue
            if all(full[p['id']][k]==p.get(k,0) for k in family):
                values.update({k:first[p['id']][k] for k in family})
            elif (family[0] in ('car','rec') and (p['id'],family[0]) in (zero_proofs or set()) and full[p['id']][family[0]]==p.get(family[0],0) and first[p['id']][family[0]]==0 and first[p['id']][family[1]]==0):
                values.update({k:0 for k in family})
                if diagnostics is not None:
                    diagnostics.setdefault('zeroActivityExceptions',[]).append(f"{p['id']}:{family[0]} later-game yards {full[p['id']][family[1]]} vs official {p.get(family[1],0)}; independent Q1 zero activity")
            else:holds.append(f"{p['id']}:{family[0]} full-game mismatch")
        if values:out[p['id']]=values
    return out,holds


def no_first_quarter_activity(payload, record, aid, family):
    """Independent zero proof: complete ESPN feed, exact team plays, no Q1 actor.

    Used only with nflverse's exact full-game attempt/catch count and zero Q1
    attempts, yards and laterals. Never excuses a nonzero quarter or count mismatch.
    """
    import football_first_quarter as fq
    counts={}
    out=fq.extract(payload,{p['id']:p for p in record['players']},record['teams'],counts=counts)
    if not out or dict(counts)!={t:v['plays'] for t,v in record['teams'].items()}:
        return False
    relevant={'rusher','other','recoverer','scorer'} if family=='car' else {'receiver','other','recoverer','scorer'}
    for p in payload['items']:
        if (p.get('period') or {}).get('number')!=1:continue
        if any(bx.ref_id(v.get('athlete'),'athletes')==aid and v.get('type') in relevant for v in p.get('participants',[])):
            return False
    return True


def refresh(season, pbp, players, schedule, root=bx.STORE, now=None, proof_fetch=None):
    """Append only: use one season artifact, never one request per player/game."""
    import hashlib,json
    now=now or datetime.now(timezone.utc)
    if bx.verify(root):raise ValueError('Box-score store failed integrity')
    cross={}
    for p in players:
        aid=number(p.get('espn_id'));gid=p.get('gsis_id')
        if gid and aid is not None:
            if gid in cross and cross[gid]!=str(aid):raise ValueError('Ambiguous player crosswalk')
            cross[gid]=str(aid)
    mapping={str(r['espn']):r['game_id'] for r in schedule if r.get('espn') and r.get('game_id')}
    groups=defaultdict(list)
    for r in pbp:
        if number(r.get('season'))==season:groups[r.get('game_id')].append(r)
    digest=hashlib.sha256(json.dumps(pbp,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result=[]
    proof_reads=0
    for old in bx.stored(root).values():
        if old['league']!='NFL' or old['season']!=season or old.get('seasonType')!=2 or bx.instant(old['kickoff'])>=now:continue
        rows=groups.get(mapping.get(old['eventId']),[])
        observed,holds=extract(rows,old,cross)
        diagnostic={}
        saved_proof=old.get('quarterDiagnostics',{})
        if holds and old.get('quarterProvider')=='nflverse' and saved_proof.get('zeroActivitySourceHash'):
            # Reuse the independent zero receipt only while the CURRENT bulk feed
            # still proves zero Q1 activity and the exact official full-game count.
            proofs=set()
            for note in saved_proof.get('zeroActivityExceptions',[]):
                identity=note.split(' ',1)[0].split(':')
                if len(identity)==2 and identity[1] in ('car','rec'):
                    proofs.add(tuple(identity))
            observed,holds=extract(rows,old,cross,proofs,diagnostic)
            if diagnostic.get('zeroActivityExceptions'):
                for key in ('zeroActivitySource','zeroActivitySourceHash'):
                    diagnostic[key]=saved_proof[key]
        if holds and proof_fetch is not None and proof_reads<2 and observed:
            import football_first_quarter as fq
            proof_reads+=1
            try:
                payload=proof_fetch(old['sources']['plays'])
                proofs={(p['id'],family) for p in old['players'] for family in ('car','rec') if no_first_quarter_activity(payload,old,p['id'],family)}
                observed,holds=extract(rows,old,cross,proofs,diagnostic)
                if diagnostic.get('zeroActivityExceptions'):
                    diagnostic['zeroActivitySource']=old['sources']['plays']
                    diagnostic['zeroActivitySourceHash']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
            except (OSError,ValueError):
                pass
        if not observed:
            result.append({'eventId':old['eventId'],'state':'held','reasons':holds});continue
        if observed!=old.get('firstQuarter') or old.get('quarterProvider')!='nflverse' or old.get('quarterHolds')!=holds or old.get('quarterDiagnostics',{})!=diagnostic:
            line=copy.deepcopy(old)
            history=[r for r in bx.read_store(bx.store_path('NFL',season,root)) if r['eventId']==old['eventId'] and r['players']==old['players'] and r['teams']==old['teams']]
            line['officialRetrievedAt']=old.get('officialRetrievedAt') or min(r['retrievedAt'] for r in history)
            line.update(firstQuarter=observed,quarterCapturedAt=bx.stamp(now),quarterProvider='nflverse',quarterSource=PAGE,
                        quarterArtifact=PBP.format(season=season),quarterArtifactHash=digest,quarterHolds=holds,quarterDiagnostics=diagnostic,
                        revision=old.get('revision',1)+1)
            line['hash']=bx.content_hash(line);bx.append(bx.store_path('NFL',season,root),[line])
        result.append({'eventId':old['eventId'],'state':'partial' if holds else 'complete','players':len(observed),'reasons':holds})
    bx.write_json(root/'ledger.json',bx.ledger(root))
    return result
