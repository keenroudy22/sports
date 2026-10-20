"""NBA-only, free-feed prop research. No football coefficients or play admission.

Prices are paired within one read/book/line. Names must resolve uniquely against
the two current ESPN rosters. A minutes × per-minute baseline is research, not a
calibrated probability; historical hit counts never become a claimed win chance.
"""
import json
import math
import os
import statistics
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boxscores
import espn_props
import nba_capture
import sharp_odds

ROOT = Path(__file__).resolve().parents[1]
STORE = nba_capture.STORE
MARKETS = {'player_points':'pts', 'player_rebounds':'reb', 'player_assists':'ast',
           'player_made_threes':'fg3m', 'player_points_+_rebounds_+_assists':'pra',
           'player_points_+_assists':'pa', 'player_points_+_rebounds':'pr',
           'player_rebounds_+_assists':'ra'}
NAMES = {'pts':'points','reb':'rebounds','ast':'assists','fg3m':'threes',
         'pra':'points + rebounds + assists','pa':'points + assists',
         'pr':'points + rebounds','ra':'rebounds + assists'}
BOOKS = {'draftkings':'DraftKings','fanduel':'FanDuel'}
VERSION = 'nba-minutes-rate-v1'


def normal(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(name)).lower() if c.isalnum())


def fresh(stamp, now, hours=4):
    try:
        return timedelta(0) <= now-boxscores.instant(stamp) <= timedelta(hours=hours)
    except (ValueError, TypeError):
        return False


def roster(payload, team, season, retrieved):
    if (str((payload.get('team') or {}).get('id')) != str(team)
            or (payload.get('season') or {}).get('year') != season
            or not isinstance(payload.get('athletes'),list) or not payload['athletes']):
        raise ValueError('NBA roster identity/season unavailable')
    players=[]
    for p in payload['athletes']:
        if not str(p.get('id','')).isdigit() or not p.get('displayName'):
            raise ValueError('NBA roster player identity unavailable')
        players.append({'id':str(p['id']),'name':p['displayName'],
                        'active':p.get('active') is not False and (p.get('active') is True or (p.get('status') or {}).get('type')=='active'),
                        'status':(p.get('status') or {}).get('type'),
                        'photo':(p.get('headshot') or {}).get('href')})
    if len({p['id'] for p in players}) != len(players):
        raise ValueError('Duplicate NBA roster identity')
    return {'league':'NBA','season':season,'team':str(team),'players':players,
            'retrievedAt':retrieved,'source':f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/roster'}


def fold(rows, games, rosters, now):
    """Reject ambiguous identities and unpaired/contradictory same-read quotes."""
    groups=defaultdict(lambda:defaultdict(set)); meta={}; ignored=defaultdict(int)
    for r in rows:
        try:
            if (r.get('league')!='nba' or r.get('is_live') is not False
                    or r.get('is_active') is not True or r.get('is_player_prop') is not True
                    or any(r.get(k) for k in ('is_stale_pregame_price','is_impossible_scoreline','is_alternate_line'))
                    or r.get('market_type') not in MARKETS or r.get('sportsbook') not in BOOKS
                    or not fresh(r.get('timestamp'),now,.25)):
                raise ValueError('unsupported')
            matches=[g for g in games if g.get('status')=='scheduled' and g.get('seasonType')=='regular-season'
                     and now < boxscores.instant(g['kickoff']) <= now+timedelta(days=2)
                     and abs(boxscores.instant(g['kickoff'])-boxscores.instant(r['event_start_time']))<=timedelta(minutes=10)
                     and normal(g['teams']['home']['name'])==normal(r['home_team'])
                     and normal(g['teams']['away']['name'])==normal(r['away_team'])]
            if len(matches)!=1:raise ValueError('event')
            g=matches[0]; people=[]
            for t in g['teams'].values():
                own=rosters.get(str(t['id']),{})
                if own.get('season')!=g['season'] or not fresh(own.get('retrievedAt'),now,24):
                    raise ValueError('roster')
                people += [(p,t) for p in own['players'] if normal(p['name'])==normal(r['player_name'])]
            if len(people)!=1:raise ValueError('identity')
            p,t=people[0]
            if not p['active'] or str(p.get('status','')).lower() in ('inactive','suspended','injured-reserve'):
                raise ValueError('inactive')
            line=espn_props.number(r['line']); price=espn_props.price(r['odds_american'])
            side=str(r.get('selection_type') or '').lower()
            label=str(r.get('selection') or '').lower()
            if (side not in ('over','under') or (label in ('over','under') and side!=label)
                    or line<0 or line%1!=.5 or abs(price)>400):
                raise ValueError('price')
            key=(str(g['providerId']),p['id'],MARKETS[r['market_type']],BOOKS[r['sportsbook']],line)
            groups[key][side].add(price)
            meta[key]={'league':'NBA','season':g['season'],'eventId':str(g['providerId']),
                       'athleteId':p['id'],'name':p['name'],'team':str(t['id']),
                       'teamName':t['name'],'teamAbbr':t['abbreviation'],'photo':p.get('photo'),
                       'kickoff':g['kickoff'],'stat':key[2],'book':key[3],'line':line,
                       'sourceAt':r['timestamp'],'retrievedAt':boxscores.stamp(now),
                       'source':'https://sharpapi.io','sideVerified':True,'kind':'main'}
        except (KeyError,TypeError,ValueError,OverflowError) as error:
            ignored[str(error) if str(error) in ('identity','roster','event','inactive','price') else 'unsupported']+=1
    paired=defaultdict(list)
    for key,sides in groups.items():
        if set(sides)!= {'over','under'} or any(len(v)!=1 for v in sides.values()):
            ignored['unpaired-or-conflicting']+=1;continue
        over=next(iter(sides['over']));under=next(iter(sides['under']))
        if not .99<=espn_props.implied(over)+espn_props.implied(under)<=1.15:
            ignored['pair-price']+=1;continue
        paired[key[:4]].append(dict(meta[key],over=over,under=under))
    # Providers sometimes mark every rung main. Use the two-sided, nearest-even
    # rung, not array order or a one-sided alternate disguised as a main line.
    result=[min(v,key=lambda r:(abs(espn_props.implied(r['over'])-espn_props.implied(r['under'])),r['line'])) for v in paired.values()]
    return result,dict(ignored)


def capture(now=None, root=STORE, fetch=None, budget=None, sleep=time.sleep, key=None):
    """At most 12 free Sharp reads, 5.2s apart; six ESPN roster reads on opener.

    Per-book cursors prevent one book from starving the other. Partial coverage
    stays partial. No Odds API/SGO calls and no changes to football stores.
    """
    now=now or datetime.now(timezone.utc); root=Path(root)
    key=key if key is not None else os.environ.get('SHARP_API') or os.environ.get('SHARP_API_KEY')
    if not key:return {'requests':0,'captured':0,'reason':'NBA prop key unavailable'}
    slate=json.loads((root/'slate.json').read_text())
    if not fresh(slate.get('retrievedAt'),now,24):return {'requests':0,'captured':0,'reason':'NBA schedule stale'}
    games=[g for g in slate['games'] if g['status']=='scheduled' and g['seasonType']=='regular-season'
           and now<boxscores.instant(g['kickoff'])<=now+timedelta(days=2)]
    if not games:return {'requests':0,'captured':0,'reason':'No upcoming NBA games'}
    budget=budget or nba_capture.Budget(requests=30); rosters={}; errors=[]
    (root/'rosters').mkdir(parents=True,exist_ok=True)
    for team,season in sorted({(str(t['id']),g['season']) for g in games for t in g['teams'].values()}):
        path=root/'rosters'/f'{team}.json'
        try:
            previous=json.loads(path.read_text()) if path.exists() else {}
            if previous.get('season')==season and fresh(previous.get('retrievedAt'),now,4):
                rosters[team]=previous;continue
            row=roster(budget(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/roster'),team,season,boxscores.stamp(now))
            nba_capture.append_changed([row],root/'roster-history',lambda r:r['team'])
            boxscores.write_json(path,row);rosters[team]=row
        except (OSError,ValueError,KeyError,TypeError):errors.append('roster-unavailable')
    fetch=fetch or sharp_odds.fetch; count=0; rows=[]; cursors={b:None for b in BOOKS};done=set()
    deadline=time.monotonic()+150
    for _ in range(6):
        for book in BOOKS:
            if book in done:continue
            if time.monotonic()+sharp_odds.GAP>=deadline:break
            sleep(sharp_odds.GAP)
            count+=1
            try:
                payload=fetch('/odds',key,league='nba',market='props',sportsbook=book,is_live='false',limit=200,cursor=cursors[book])
                rows.extend(payload.get('data') or [])
                page=payload.get('pagination') or {};cursor=page.get('next_cursor')
                if not page.get('has_more') or not cursor or cursor==cursors[book]:done.add(book)
                cursors[book]=cursor
            except (OSError,ValueError,KeyError,TypeError):
                errors.append('prop-feed-unavailable');done.add(book)
        if len(done)==len(BOOKS):break
    stamp=datetime.now(timezone.utc) if fetch is sharp_odds.fetch else now
    quotes,ignored=fold(rows,games,rosters,stamp)
    captured=nba_capture.append_changed(quotes,root/'player-quotes',lambda r:(r['eventId'],r['athleteId'],r['stat'],r['book']),keep_observations=True)
    recorded=record_forward(stamp,root)
    graded=grade(stamp,root)
    return {'requests':count,'espnRequests':budget.requests,'captured':captured,'paired':len(quotes),
            'partial':len(done)<len(BOOKS),'ignored':ignored,'errors':errors,'forwardRecorded':recorded,'forwardGraded':graded}


def history(boxes, athlete, now):
    out=[]
    for b in sorted({b['eventId']:b for b in boxes}.values(),key=lambda b:b['kickoff']):
        if b['seasonType']!=2 or boxscores.instant(b['kickoff'])>=now:continue
        for p in b.get('players',[]):
            if p['id']==athlete and not p.get('dnp'):
                out.append(dict(p,season=b['season'],date=b['kickoff'],eventId=b['eventId']))
    return out


def forecast(logs, team, season, stat):
    """Freeze a transparent same-team baseline; never silently blend seasons."""
    if logs and logs[-1]['team']!=team:return None,'Changed teams; current-role history needed'
    own=[h for h in logs if h['team']==team]
    selected=season if sum(h['season']==season for h in own)>=5 else season-1
    own=[h for h in own if h['season']==selected]
    eligible=[h for h in own if stat in h['stats'] and 0<h['stats'].get('min',0)<=60
              and all(isinstance(h['stats'][s],(int,float)) and not isinstance(h['stats'][s],bool)
                      and math.isfinite(h['stats'][s]) and h['stats'][s]>=0 for s in (stat,'min'))]
    if len(eligible)<5:return None,'Needs five same-team regular-season appearances'
    recent=eligible[-10:];median=statistics.median(h['stats']['min'] for h in recent)
    # Check the genuinely new role too, even while the baseline still uses last
    # season. No offseason injury boost or old minutes can override a collapse.
    current=[h for h in logs if h['team']==team and h['season']==season and 'min' in h['stats']]
    if len(current)>=2 and statistics.mean(h['stats']['min'] for h in current[-3:])<.7*median:
        return None,'Current-season minutes fell; role needs review'
    if median<12:return None,'Limited minutes; role too thin'
    if len(recent)>=5 and statistics.mean(h['stats']['min'] for h in recent[-3:])<.7*median:
        return None,'Recent minutes fell; role needs review'
    full=[h for h in recent if h['stats']['min']>=.6*median]
    if len(full)<5:return None,'Too few full-role appearances'
    minutes=min(40,statistics.median(h['stats']['min'] for h in full[-5:]))
    rate=sum(h['stats'][stat] for h in full)/sum(h['stats']['min'] for h in full)
    value=minutes*rate
    scaled=sorted(h['stats'][stat]/h['stats']['min']*minutes for h in full)
    return {'value':round(value,1),'minutes':round(minutes,1),'rate':round(rate,4),'model':VERSION,
            'season':selected,'sample':len(full),'historyGames':len(eligible),
            'window':'This season' if selected==season else 'Last season',
            'low':round(scaled[int((len(scaled)-1)*.1)],1),'high':round(scaled[math.ceil((len(scaled)-1)*.9)],1),
            'first':full[0]['date'],'last':full[-1]['date']},None


def hit_rate(logs,stat,line,side,n=None):
    values=[h['stats'][stat] for h in logs if stat in h['stats'] and isinstance(h['stats'][stat],(int,float))
            and math.isfinite(h['stats'][stat]) and h['stats'][stat]>=0]
    values=values[-n:] if n else values
    hits=sum(v>line if side=='over' else v<line for v in values);push=sum(v==line for v in values)
    return {'hits':hits,'games':len(values),'push':push,'values':values}


def build(now, root=STORE, boxes=None, limit=60):
    root=Path(root)
    def read(path,fallback):
        try:return json.loads(path.read_text())
        except (OSError,ValueError):return fallback
    slate=read(root/'slate.json',{});injury=read(root/'injuries-current.json',{})
    if boxes is None:
        boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    quotes={}
    for p in (root/'player-quotes').glob('*.jsonl'):
        for r in boxscores.read_store(p):quotes[(r['eventId'],r['athleteId'],r['stat'],r['book'])]=r
    games={str(g['providerId']):g for g in slate.get('games',[]) if g['status']=='scheduled'
           and g['seasonType']=='regular-season' and now<boxscores.instant(g['kickoff'])<=now+timedelta(days=2)}
    holds={r['athleteId']:r['status'] for r in injury.get('rows',[]) if r.get('status')}
    out=[]
    for q in quotes.values():
        if q['eventId'] not in games or not fresh(q.get('sourceAt'),now) or not fresh(q.get('retrievedAt'),now):continue
        g=games[q['eventId']];own=read(root/'rosters'/f"{q['team']}.json",{})
        p=[p for p in own.get('players',[]) if p['id']==q['athleteId']]
        reason=None
        if not fresh(slate.get('retrievedAt'),now,24):reason='Schedule update needed'
        # This read-only baseline uses the established four-hour research
        # freshness window. The separate official NBA Trial keeps its 60-minute
        # availability gate; research does not change admission or publish odds.
        elif not fresh(injury.get('retrievedAt'),now,4):reason='Availability update needed'
        elif q['athleteId'] in holds:reason=f"Availability: {holds[q['athleteId']]}"
        elif (not fresh(own.get('retrievedAt'),now,24) or own.get('season')!=q['season']
              or len(p)!=1 or not p[0]['active']
              or str(p[0].get('status','')).lower() in ('inactive','suspended','injured-reserve')
              or q['team'] not in {str(t['id']) for t in g['teams'].values()}):
            reason='Current roster verification needed'
        fair=espn_props.implied(q['over'])/(espn_props.implied(q['over'])+espn_props.implied(q['under']))
        peers=[other for other in quotes.values() if other['book']!=q['book']
               and all(other[k]==q[k] for k in ('eventId','athleteId','stat','line'))
               and fresh(other.get('sourceAt'),now)]
        if any(abs(fair-espn_props.implied(o['over'])/(espn_props.implied(o['over'])+espn_props.implied(o['under'])))>=.15 for o in peers):
            reason='Books disagree sharply at this exact line; price needs review'
        logs=history(boxes,q['athleteId'],now)
        projection=None
        if not reason:projection,reason=forecast(logs,q['team'],q['season'],q['stat'])
        row={k:q[k] for k in ('eventId','athleteId','name','team','teamName','teamAbbr','photo','kickoff','stat','line','book','over','under','sourceAt')}
        row['statName']=NAMES[q['stat']];row['projection']=projection;row['hold']=reason
        if projection:
            side='over' if projection['value']>q['line'] else 'under'
            samples=[h for h in logs if h['team']==q['team'] and h['season']==projection['season']]
            row.update(side=side,odds=q[side],gap=round(projection['value']-q['line'],1),
                       last5=hit_rate(samples,q['stat'],q['line'],side,5),
                       last10=hit_rate(samples,q['stat'],q['line'],side,10),
                       seasonHistory=hit_rate(samples,q['stat'],q['line'],side))
            row['why']=f"{projection['minutes']:g} projected minutes × {projection['rate']:g} {NAMES[q['stat']]}/minute from {projection['sample']} full-role games."
            row['caution']='Minutes baseline, not opponent-adjusted. Teammate absences are not redistributed.'
            # Research favorites require direction/history agreement, never a
            # fabricated calibrated chance or a proven-profit claim.
            h=row['last10'];row['favorite']=h['games']>=5 and h['hits']/h['games']>=.6 and abs(row['gap'])>=max(.5,.1*q['line'])
        out.append(row)
    out.sort(key=lambda r:(not r.get('favorite'),
                          -abs(r.get('gap',0))/max(1,(r.get('projection') or {}).get('high',1)-(r.get('projection') or {}).get('low',0)),
                          -r.get('odds',0),r['kickoff'],r['name'],r['stat'],r['book']))
    # Keep complete per-game coverage visible; a large slate is explicitly capped
    # for the lazy page payload rather than silently claiming full feed coverage.
    held={r['athleteId']:r['hold'] for r in out if r.get('hold')}
    return {'rows':out[:limit] if limit is not None else out,'availableRows':len(out),
            'availabilityAt':injury.get('retrievedAt'),
            'holds':[{'name':next(r['name'] for r in out if r['athleteId']==a),'reason':reason} for a,reason in held.items()],
            'note':'Research baselines, not NBA Best Bets. Up to 60 fresh comparisons, favorites first. Hit rates are at this exact line in the labeled recorded sample; they are not forecast probabilities.'}


def saved(root):
    return [r for p in Path(root).glob('*.jsonl') for r in boxscores.read_store(p)]


def record_forward(now,root=STORE,boxes=None):
    """First verified pregame quote/forecast per player-market-book, immutable."""
    root=Path(root); old={r['id'] for r in saved(root/'player-forecasts')};rows=[]
    for r in build(now,root,boxes,limit=None)['rows']:
        if not r.get('projection') or r.get('hold'):continue
        identity=':'.join((r['eventId'],r['athleteId'],r['stat'],r['book'],VERSION))
        if identity in old:continue
        rows.append(dict(r,id=identity,league='NBA',season=r['projection']['season']+int(r['projection']['window']=='Last season'),
                         retrievedAt=boxscores.stamp(now),model=VERSION))
    return nba_capture.append_changed(rows,root/'player-forecasts',lambda r:r['id'])


def grade(now,root=STORE,boxes=None):
    """Forward research outcomes only; never writes official NBA/football records."""
    root=Path(root)
    if boxes is None:boxes=saved(ROOT/'data/sport-box')
    finals={str(b['eventId']).removeprefix('NBA-'):b for b in boxes
            if b.get('league')=='NBA' and b.get('seasonType')==2 and boxscores.instant(b['kickoff'])<now}
    old={r['id'] for r in saved(root/'player-outcomes')};rows=[]
    for r in saved(root/'player-forecasts'):
        if r['id'] in old or r['eventId'] not in finals:continue
        final=finals[r['eventId']]
        if boxscores.instant(r['retrievedAt'])>=boxscores.instant(final['kickoff']):continue
        people=[p for p in final['players'] if p['id']==r['athleteId'] and p['team']==r['team']]
        if len(people)!=1:continue
        p=people[0];actual=p['stats'].get(r['stat'])
        if p.get('dnp'):result='dnp';actual=None
        elif not isinstance(actual,(int,float)) or not math.isfinite(actual):continue
        else:result='push' if actual==r['line'] else ('hit' if (actual>r['line'])==(r['side']=='over') else 'miss')
        rows.append({'id':r['id'],'league':'NBA','season':r['season'],'actual':actual,'result':result,
                     'projection':r['projection']['value'],'line':r['line'],'side':r['side'],
                     'odds':r['odds'],'book':r['book'],'source':final.get('source'),
                     'retrievedAt':boxscores.stamp(now),'forecastAt':r['retrievedAt'],'model':VERSION})
    return nba_capture.append_changed(rows,root/'player-outcomes',lambda r:r['id'])


def evaluate(boxes):
    """Walk-forward sanity comparison, not a historical-price/profit backtest."""
    players=defaultdict(list);errors=[];baseline=[]
    for b in sorted({b['eventId']:b for b in boxes}.values(),key=lambda r:r['kickoff']):
        if b.get('seasonType')!=2:continue
        for p in b['players']:
            if p.get('dnp'):continue
            previous=players[p['id']]
            for stat in ('pts','reb','ast','fg3m'):
                if stat not in p['stats']:continue
                forecasted,_=forecast(previous,p['team'],b['season'],stat)
                if not forecasted:continue
                same=[h['stats'][stat] for h in previous if h['team']==p['team'] and h['season']==b['season'] and stat in h['stats']][-5:]
                if len(same)<5:continue
                errors.append(abs(forecasted['value']-p['stats'][stat]));baseline.append(abs(statistics.mean(same)-p['stats'][stat]))
            previous.append(dict(p,season=b['season'],date=b['kickoff']))
    return {'predictions':len(errors),'meanAbsoluteError':round(statistics.mean(errors),3) if errors else None,
            'lastFiveMeanError':round(statistics.mean(baseline),3) if baseline else None,
            'scope':'Walk-forward regular-season box scores; no historical prices, profit or calibrated probabilities.'}
