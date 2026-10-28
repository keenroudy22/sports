"""Guarded NBA Trial totals runtime. Free stored ESPN evidence; never football's record.

No feed or social action before opening day or a delivered first-card preview.
Unresolved team injuries hold totals; player props wait for a verified player model.
"""
import json
import math
import os
from datetime import datetime,timedelta,timezone
from pathlib import Path

import boxscores
import nba_capture
import nba_trial
import paper
import hoops_store
import nba_readiness
import nba_roster_runtime

ROOT=Path(__file__).resolve().parents[1]
CONF=Path(os.environ.get('KEENROUDY_CONF') or Path.home()/'.config/keenroudy')
REVIEW=CONF/'nba-trial-review.json'


def rows(root=nba_trial.STORE):
 return [r for p in root.glob('*.jsonl') for r in boxscores.read_store(p)]


def review_ready(now,review=None,readiness=None):
 if review is None and datetime.now(timezone.utc).astimezone(nba_trial.EASTERN).date()<nba_trial.OPENING:return False
 if os.environ.get('KEENROUDY_NBA_TRIAL','1')=='0' or os.environ.get('KEENROUDY_SPORTS_CAPTURE','1')=='0':return False
 if now.astimezone(nba_trial.EASTERN).date()<nba_trial.OPENING:return False
 if review is None:
  try:review=json.loads(REVIEW.read_text())
  except (OSError,ValueError):return False
 try:
  import hashlib
  expected=hashlib.sha256((ROOT/'design/final/nba-trial-preview.png').read_bytes()).hexdigest()
  evidence_ready = nba_readiness.live_ready(now) if readiness is None else readiness
  return (evidence_ready is True and review.get('delivered') is True and not review.get('vetoed')
          and review.get('pngSHA256')==expected
          and now-boxscores.instant(review['sentAt'])>=timedelta(hours=2))
 except (KeyError,ValueError,TypeError,OSError):return False


def total_chance(mean,sd,line,side):
 if not all(isinstance(n,(float,int)) and not isinstance(n,bool) and math.isfinite(n) for n in (mean,sd,line)) or sd<=0:raise ValueError('No probability evidence')
 # Full-game scores are integers: at an integer line exclude the push from wins.
 cutoff=line-.5 if line%1==0 and side=='under' else line+.5 if line%1==0 else line
 cdf=.5*(1+math.erf((cutoff-mean)/(sd*math.sqrt(2))))
 return cdf if side=='under' else 1-cdf


def normal_chance(mean,sd,threshold,side='over'):
 if not all(isinstance(n,(float,int)) and not isinstance(n,bool) and math.isfinite(n) for n in (mean,sd,threshold)) or sd<=0:
  raise ValueError('No probability evidence')
 cdf=.5*(1+math.erf((threshold-mean)/(sd*math.sqrt(2))))
 return 1-cdf if side=='over' else cdf


def price_pair(block,key):
 """The selected and opposite side of one exact, two-sided ESPN market."""
 first,second=block.get('home',{}).get(key),block.get('away',{}).get(key)
 if first is None or second is None:return None
 try:
  first,second=__import__('espn_props').price(first),__import__('espn_props').price(second)
  total=__import__('espn_props').implied(first)+__import__('espn_props').implied(second)
  return (first,second) if .99<=total<=1.15 else None
 except (TypeError,ValueError):return None


def support(game,line,side,history,now,minimum=5):
 reasons=[];averages=[]
 for team in (game['teams']['away'],game['teams']['home']):
  mine=[r for r in history if r['type']==2 and boxscores.instant(r['kickoff'])<now and str(team['id']) in (r['home']['id'],r['away']['id'])]
  current=[r for r in mine if r['season']==game['season']]
  window=sorted(current if len(current)>=minimum else [r for r in mine if r['season']==game['season']-1],key=lambda r:r['kickoff'])[-minimum:]
  if len(window)<minimum:return []
  values=[r['homeScore'] if r['home']['id']==team['id'] else r['awayScore'] for r in window]
  average=sum(values)/len(values);averages.append(average)
  period='This season' if window[0]['season']==game['season'] else 'Last season'
  reasons.append(f"{period}, {team['abbreviation']} scored {average:.1f} a game across its last {len(window)} recorded regular-season games.")
 if (sum(averages)<line if side=='under' else sum(averages)>line):return reasons
 return []  # opposing history is never dressed up as support


def side_support(game,which,line,chance,history,now,market,minimum=5):
 team=game['teams'][which];mine=[]
 for row in history:
  if row['type']!=2 or boxscores.instant(row['kickoff'])>=now:continue
  if str(team['id']) not in (row['home']['id'],row['away']['id']):continue
  scored=row['homeScore'] if row['home']['id']==team['id'] else row['awayScore']
  allowed=row['awayScore'] if row['home']['id']==team['id'] else row['homeScore']
  mine.append((row['season'],scored-allowed))
 current=[v for year,v in mine if year==game['season']]
 window=current[-minimum:] if len(current)>=minimum else [v for year,v in mine][-5:]
 if len(window)<minimum:return []
 if market=='moneyline':
  hits=sum(value>0 for value in window)
  if hits<math.ceil(.6*len(window)):return []
  history_reason=f"{team['abbreviation']} won {hits} of its last {len(window)} recorded regular-season games."
 else:
  # `line` is this team's signed spread; margin + line above zero covers.
  hits=sum(value+line>0 for value in window)
  if hits<math.ceil(.6*len(window)):return []
  history_reason=f"{team['abbreviation']} covered this number in {hits} of its last {len(window)} recorded regular-season games."
 return [f"My score model gives {team['abbreviation']} a {100*chance:.1f}% chance here.",history_reason]


def candidates(now,root=nba_capture.STORE,model_factory=paper.model_for,history=None,lead_minutes=60,diagnostics=None):
 summary=diagnostics if diagnostics is not None else {}
 summary.update(games=0,eligibleGames=0,offers=0,holds={})
 def held(reason):summary['holds'][reason]=summary['holds'].get(reason,0)+1
 try:
  slate=json.loads((root/'slate.json').read_text());inj=json.loads((root/'injuries-current.json').read_text())
 except (OSError,ValueError):
  held('missing slate or injury snapshot');return []
 summary['games']=len(slate.get('games',[]))
 summary['injuriesCheckedAt']=inj.get('retrievedAt')
 if not 0<=(now-boxscores.instant(inj['retrievedAt'])).total_seconds()<=60*60:
  held('injury snapshot outside sixty-minute window');return []
 quotes={}
 for p in (root/'quotes').glob('*.jsonl'):
  for q in boxscores.read_store(p):quotes[(q['eventId'],q['book'])]=q
 history=hoops_store.load('NBA') if history is None else history
 models={};out=[]
 for g in slate.get('games',[]):
  if (g['status']!='scheduled' or g['seasonType']!='regular-season' or not g.get('timeConfirmed',True)
      or boxscores.instant(g['kickoff']).astimezone(nba_trial.EASTERN).date()!=now.astimezone(nba_trial.EASTERN).date()
      or boxscores.instant(g['kickoff'])<=now+timedelta(minutes=lead_minutes)):
   held('not an eligible upcoming game today');continue
  if inj.get('season')!=g['season']:
   held('injury snapshot season mismatch');continue
  game_rows,team_holds=nba_capture.availability_for_game(inj,g,now,max_hours=1)
  if team_holds:
   for reason in set(team_holds.values()):held(reason)
   continue
  holds={r['team'] for r in game_rows if nba_capture.blocks_availability(r.get('status'))}
  affected=any(t['id'] in holds for t in g['teams'].values())
  unresolved=any(nba_capture.blocks_availability(r.get('status')) and r.get('status')!='Out' for r in game_rows)
  if affected and (unresolved or now.date()<datetime(2026,10,27).date()):
   held('unresolved team injury status');continue
  summary['eligibleGames']+=1
  if g['season'] not in models:models[g['season']]=model_factory('NBA',g['season'],now.timestamp())
  baseline=models[g['season']].predict(g['teams']['home']['id'],g['teams']['away']['id'])
  result=nba_roster_runtime.current(g,baseline,now,root) if now.date()>=datetime(2026,10,27).date() else {}
  prediction,families=nba_roster_runtime.apply_validated(baseline,result)
  if affected and not families:
   for reason in result.get('holds') or ['No validated roster adjustment for known absences']:held(reason)
   continue
  allowed=set(families) if affected else {'total','margin'}
  for book in ('DraftKings',):
   q=quotes.get((g['providerId'],book))
   if not q:
    held('no stored DraftKings quote');continue
   if families:
    try:
     report_clock=boxscores.instant(result['reportedAt'])
     if not report_clock<=boxscores.instant(q['retrievedAt'])<=now:raise ValueError('price predates news')
    except (KeyError,TypeError,ValueError):
     held('Roster forecast requires a price captured after the injury report');continue
   try:
    if 'total' not in allowed:raise ValueError('Roster total adjustment not validated')
    total=q['current']['total'];line=total['line'];side='under' if prediction['total']<line else 'over'
    chance=total_chance(prediction['total'],prediction['sdTotal'],line,side)
    if any(abs(total[k])>400 for k in ('over','under')):raise ValueError('extreme total price')
    reasons=support(g,line,side,history,now,minimum=3 if 'total' in families else 5)
    if len(reasons)==2:out.append({'id':f"NBA-trial-{now.astimezone(nba_trial.EASTERN):%Y-%m-%d}-{g['providerId']}-total",
                'eventId':g['id'],'league':'NBA','season':g['season'],'seasonType':2,'kickoff':g['kickoff'],
                'marketType':'total','direction':side,'line':line,'odds':total[side],
                'oppositeOdds':total['over' if side=='under' else 'under'],'book':book,
                'retrievedAt':q['retrievedAt'],'source':q['source'],'rawChance':chance,
                'riskUnits':1,'roleChecked':True,'sideVerified':True,'exactLineVerified':True,
                'game':g,'reasons':reasons,'projection':round(prediction['total'],1),'model':(result.get('prediction') or {}).get('model',nba_roster_runtime.model.VERSION) if 'total' in families else 'hoops-v1'})
   except (KeyError,TypeError,ValueError):pass
   try:
    if 'margin' not in allowed:raise ValueError('Roster margin adjustment not validated')
    pair=price_pair(q['current'],'moneyline')
    chance=prediction.get('homeWinProb')
    if pair and isinstance(chance,(int,float)):
     which='home' if chance>=.5 else 'away';raw=chance if which=='home' else 1-chance
     odds,other=(pair[0],pair[1]) if which=='home' else (pair[1],pair[0])
     reasons=side_support(g,which,0,raw,history,now,'moneyline',minimum=3 if 'margin' in families else 5)
     if len(reasons)==2:
      out.append({'id':f"NBA-trial-{now.astimezone(nba_trial.EASTERN):%Y-%m-%d}-{g['providerId']}-moneyline",
                  'eventId':g['id'],'league':'NBA','season':g['season'],'seasonType':2,'kickoff':g['kickoff'],
                  'modelSnapshot':{'homeWinProb':prediction.get('homeWinProb'),'margin':prediction.get('margin')},
                  'marketType':'moneyline','direction':which,'line':0,'odds':odds,'oppositeOdds':other,'book':book,
                  'retrievedAt':q['retrievedAt'],'source':q['source'],'rawChance':raw,'riskUnits':1,
                  'roleChecked':True,'sideVerified':True,'exactLineVerified':True,'game':g,'reasons':reasons,
                  'projection':round(prediction['margin'],1),'model':(result.get('prediction') or {}).get('model',nba_roster_runtime.model.VERSION) if 'margin' in families else 'hoops-v1'})
   except (KeyError,TypeError,ValueError):pass
   try:
    if 'margin' not in allowed:raise ValueError('Roster margin adjustment not validated')
    pair=price_pair(q['current'],'spreadPrice')
    home=q['current']['home'];away=q['current']['away']
    if pair and home.get('spreadLine') is not None and away.get('spreadLine') is not None:
     if abs(float(home['spreadLine'])+float(away['spreadLine']))>1e-9:
      held('spread pair has different thresholds');continue
     home_line=float(home['spreadLine']);home_chance=normal_chance(prediction['margin'],prediction['sdMargin'],-home_line)
     which='home' if home_chance>=.5 else 'away';raw=home_chance if which=='home' else 1-home_chance
     line=home_line if which=='home' else float(away['spreadLine'])
     odds,other=(pair[0],pair[1]) if which=='home' else (pair[1],pair[0])
     reasons=side_support(g,which,line,raw,history,now,'spread',minimum=3 if 'margin' in families else 5)
     if len(reasons)==2:
      out.append({'id':f"NBA-trial-{now.astimezone(nba_trial.EASTERN):%Y-%m-%d}-{g['providerId']}-spread",
                  'eventId':g['id'],'league':'NBA','season':g['season'],'seasonType':2,'kickoff':g['kickoff'],
                  'marketType':'spread','direction':which,'line':line,'odds':odds,'oppositeOdds':other,'book':book,
                  'retrievedAt':q['retrievedAt'],'source':q['source'],'rawChance':raw,'riskUnits':1,
                  'roleChecked':True,'sideVerified':True,'exactLineVerified':True,'game':g,'reasons':reasons,
                  'projection':round(prediction['margin'],1),'model':(result.get('prediction') or {}).get('model',nba_roster_runtime.model.VERSION) if 'margin' in families else 'hoops-v1'})
   except (KeyError,TypeError,ValueError):pass
 summary['offers']=len(out)
 return sorted(out,key=lambda r:(-(r['rawChance']-__import__('espn_props').implied(r['odds'])),r['kickoff'],r['id']))


def admission(now,root=nba_trial.STORE,log_book=None,review=None,capture=True):
 if not review_ready(now,review):return {'state':'held','reason':'opening/review/kill-switch gate'}
 if not os.environ.get('BUFFER_TOKEN'):return {'state':'held','reason':'delivery not configured'}
 import buffer_post,x_post
 book=log_book if log_book is not None else x_post.load_log()
 day=now.astimezone(nba_trial.EASTERN).date()
 if buffer_post.pending_scheduled(book,now)>=buffer_post.BUFFER_OPTIONAL_AT:return {'state':'held','reason':'football queue reserve'}
 if buffer_post.day_count(book,day)>=buffer_post.MAX_PER_DAY:return {'state':'held','reason':'daily post cap'}
 for e in book.get('posts',[]):
  if e.get('kind') in ('buffer:nba-trial','buffer:sports-slate','buffer:sports-research') and boxscores.instant(e.get('dueAt') or e['postedAt']).astimezone(nba_trial.EASTERN).date()==day:return {'state':'held','reason':'one other-sport post per day'}
 stored=rows(root)
 if any(r.get('type')=='publish' and boxscores.instant(r['kickoff']).astimezone(nba_trial.EASTERN).date()==day for r in stored):return {'state':'held','reason':'one NBA Trial per day'}
 if capture:
  nba_capture.step(now,budget=nba_capture.Budget(requests=10,seconds=60))
 now=max(now,datetime.now(timezone.utc))
 if review is None:review=json.loads(REVIEW.read_text())
 coverage={};refusals={}
 for offer in candidates(now,diagnostics=coverage):
  nba_trial.staking.apply(offer,now)
  problems=nba_trial.evaluate(offer,stored,now,preview_sent=review['sentAt'])
  if problems:
   for reason in problems:refusals[reason]=refusals.get(reason,0)+1
   continue
  try:nba_trial.record_publish(offer,now,root,preview_sent=review['sentAt'])
  except ValueError as error:
   if str(error).startswith('shared exposure:'):return {'state':'held','reason':str(error)}
   raise
  return {'state':'admitted','id':offer['id'],'coverage':coverage,'refusals':refusals}
 return {'state':'no-play','reason':'no fresh, supported, role-clear NBA market passes every gate',
         'coverage':coverage,'refusals':refusals}


def public_rows(root=nba_trial.STORE):
 saved=rows(root);published={r['id']:r for r in saved if r.get('type')=='publish'}
 settled={r['id']:r for r in saved if r.get('type')=='settle'}
 return [{**r,**({'result':settled[key]['result'],'actual':settled[key]['actual']} if key in settled else {})} for key,r in published.items()]


def grade(now,root=nba_trial.STORE,boxroot=None):
 boxroot=boxroot or ROOT/'data'/'sport-box'
 finals={r['eventId']:r for p in boxroot.glob('*.jsonl') for r in boxscores.read_store(p)}
 added=0
 for play in public_rows(root):
  final=finals.get(play['eventId'])
  if not final or final['seasonType']!=2 or boxscores.instant(final['kickoff'])!=boxscores.instant(play['kickoff']):continue
  teams=final['teams'];scores=[t.get('score') for t in teams.values()]
  if len(scores)!=2 or any(not isinstance(s,(int,float)) for s in scores):continue
  market=play.get('marketType','total')
  if market=='total':
   actual=sum(scores);won=actual<play['line'] if play['direction']=='under' else actual>play['line'];push=actual==play['line']
  else:
   chosen=str(play['game']['teams'][play['direction']]['id']);mine=teams.get(chosen)
   other=next((team for key,team in teams.items() if str(key)!=chosen),None)
   if not mine or not other:continue
   actual=mine['score']-other['score'];settled=actual+(play['line'] if market=='spread' else 0)
   won=settled>0;push=settled==0
  result='push' if push else 'win' if won else 'loss'
  row={'type':'settle','id':play['id'],'season':play['season'],'seasonType':2,'league':'NBA',
       'actual':actual,'result':result,'source':final['source'],'settledAt':boxscores.stamp(now),'retrievedAt':boxscores.stamp(now)}
  # Ignore a new check time alone, but append real official-score corrections.
  latest=next((r for r in reversed(rows(root)) if r.get('type')=='settle' and r['id']==play['id']),None)
  if latest and all(latest.get(k)==row[k] for k in ('actual','result','source')):continue
  added+=nba_capture.append_changed([row],root,lambda r:(r['type'],r['id']))
 return added


def social_plans(now,log_book,root=nba_trial.STORE,reserved=()):
 import buffer_post,x_post
 if not review_ready(now):return []
 pending=[p for p in public_rows(root) if not p.get('result') and not any(e['id']==p['id'] for e in log_book.get('posts',[]))]
 if not pending:return []
 nba_capture.step(now,budget=nba_capture.Budget(requests=10,seconds=60))
 now=max(now,datetime.now(timezone.utc))
 busy=buffer_post.taken(log_book,now)+[p[3] for p in reserved]
 plans=[]
 for play in pending:
  if not current_match(play,now):continue
  if play.get('result') or any(e['id']==play['id'] for e in log_book.get('posts',[])):continue
  game_day=boxscores.instant(play['kickoff']).astimezone(nba_trial.EASTERN).date()
  if game_day!=now.astimezone(nba_trial.EASTERN).date():continue
  early=boxscores.instant(play['kickoff']).astimezone(nba_trial.EASTERN).hour<10 or (boxscores.instant(play['kickoff']).astimezone(nba_trial.EASTERN).hour==10 and boxscores.instant(play['kickoff']).astimezone(nba_trial.EASTERN).minute<30)
  target=datetime.combine(game_day,datetime.min.time(),nba_trial.EASTERN).replace(hour=8 if early else 9,minute=30)
  due=buffer_post.free_slot(max(target,now+timedelta(minutes=15)),busy)
  if due>=boxscores.instant(play['kickoff'])-timedelta(minutes=15):continue
  teams=play['game']['teams']
  name=lambda side: teams[side].get('displayName') or teams[side].get('name') or teams[side]['abbreviation']
  title=f"{name('away')} at {name('home')}"
  if play.get('marketType')=='total': selection=f"{play['direction'].upper()} {play['line']:g}"
  else:
   team=name(play['direction'])
   selection=f"{team} MONEYLINE" if play['marketType']=='moneyline' else f"{team} {play['line']:+g}"
  projection=''
  text=None
  for reason in play['reasons']:
   from social_copy import projection_free_reason
   reason=projection_free_reason(reason)
   if not reason:continue
   candidate=f"🏀 NBA Trial\n{title}\n{selection} ({play['odds']:+d}, {play['book']})\n{projection}\n{reason}\n#NBA"
   if x_post.tweet_length(candidate)<=x_post.LIMIT and not x_post.x_style(candidate):
    text=candidate;break
  if not text:continue
  plans.append((play['id'],'nba-trial',text,due,play['id'].lower()))
 return plans


def render_due(now,folder,log=print,root=nba_trial.STORE):
 import ticket_cards,ticket_kit,pick_card,x_post
 posted={e['id'] for e in x_post.load_log().get('posts',[]) if e.get('bufferPostId') or e.get('sentAt')}
 visible=sorted(current_plays(root),key=lambda p:p['publishedAt'])[-20:]
 referenced={p['id'] for p in visible}
 for play in public_rows(root):
  path=Path(folder)/(play['id'].lower()+'.png')
  if path.exists():continue
  if play['id'] in posted:
   if play['id'] in referenced or not play.get('result') or now-boxscores.instant(play['publishedAt'])<=timedelta(days=8):
    raise ValueError('Referenced NBA Trial original card missing: '+play['id'])
   log('Old unreferenced NBA Trial card missing; preserved attachment, skipped site art: '+play['id']);continue
  if play.get('marketType')=='total':
   current={'total':{'line':play['line'],'under':play['odds'] if play['direction']=='under' else play['oppositeOdds'],'over':play['odds'] if play['direction']=='over' else play['oppositeOdds']}}
  else:
   other='away' if play['direction']=='home' else 'home';price_key='moneyline' if play['marketType']=='moneyline' else 'spreadPrice'
   current={play['direction']:{price_key:play['odds']},other:{price_key:play['oppositeOdds']}}
   if play['marketType']=='spread':
    current[play['direction']]['spreadLine']=play['line'];current[other]['spreadLine']=-play['line']
  quote={'book':play['book'],'retrievedAt':play['retrievedAt'],'current':current}
  # Same reviewed layout; actual play label and real supporting reason replace preview wording.
  svg=nba_trial.preview_svg(play['game'],quote,preview=False,direction=play['direction'],reason=play['reasons'][0],
                            market=play.get('marketType','total'),line=play['line'],odds=play['odds'],units=play.get('riskUnits',1))
  pick_card.render(svg,path)


def current_match(play,now):
 for candidate in candidates(now,lead_minutes=0):
  nba_trial.staking.apply(candidate,now)
  if candidate['id']==play['id'] and all(candidate[k]==play[k] for k in ('book','line','odds','direction')):
   try:review=json.loads(REVIEW.read_text())
   except (OSError,ValueError):return False
   other=[r for r in rows() if r.get('id')!=play['id']]
   return not nba_trial.evaluate(candidate,other,now,preview_sent=review['sentAt'])
 return False


def precheck(now,log_book,refresh=True,delete=None):
 import buffer_post
 due=[e for e in log_book.get('posts',[]) if e.get('kind')=='buffer:nba-trial' and e.get('bufferPostId')
      and not e.get('sentAt') and not e.get('cancelledAt')
      and 0<=(boxscores.instant(e['dueAt'])-now).total_seconds()<=45*60]
 if not due:return False
 if refresh and review_ready(now):
  nba_capture.step(now,budget=nba_capture.Budget(requests=10,seconds=60))
  now=max(now,datetime.now(timezone.utc))
 plays={p['id']:p for p in public_rows()};changed=False
 for entry in due:
  play=plays.get(entry['id'])
  okay=bool(play and review_ready(now) and current_match(play,now))
  entry['nbaPrecheck']={'at':boxscores.stamp(now),'result':'clear' if okay else 'held'};changed=True
  if not okay:
   (delete or buffer_post.delete_post)(entry['bufferPostId'])
   entry['cancelledAt']=boxscores.stamp(now)
   entry['nbaHold']='Role or exact-price check did not clear. The published play stays in its record.'
 return changed


def reserve_delivery(guid,now,root=nba_trial.STORE):
 """At-most-once create attempt; an ambiguous Buffer reply waits for reconciliation."""
 saved=rows(root)
 if any(r.get('type')=='send-attempt' and r['id']==guid for r in saved):return False
 play=next((r for r in saved if r.get('type')=='publish' and r['id']==guid),None)
 if not play:return False
 nba_capture.append_changed([{'type':'send-attempt','id':guid,'season':play['season'],
                             'retrievedAt':boxscores.stamp(now),'source':'Buffer create intent'}],root,lambda r:(r['type'],r['id']))
 return True


def current_plays(root=nba_trial.STORE):
 plays=public_rows(root)
 if not plays:return []
 latest=max(plays,key=lambda p:(p['season'],boxscores.instant(p['kickoff'])))
 return [p for p in plays if (p['season'],p['seasonType'])==(latest['season'],latest['seasonType'])]


def delivery_failed(guid,now):
 import run
 run.alert('NBA Trial delivery needs reconciliation',
           f'{guid}: Buffer did not confirm the create attempt. Automatic retry is held to prevent a duplicate; the published NBA record remains intact.',now=now)
