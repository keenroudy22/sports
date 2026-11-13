"""Sourced CBB straight decisions, separate from unvalidated model probabilities.

No feed calls, automatic model promotion or wager placement. A reviewed exact
main-line offer is admitted under the shared cap; normal builds and delivery
workers publish its immutable terms and later append official-score grades.
"""
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import boxscores
import gates
import post_windows
import nba_capture
import staking

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT/'data/cbb-picks'
METHOD = 'sourced-cbb-straight-v1'


def rows(root=STORE):
    if boxscores.verify(root):
        raise ValueError('CBB pick ledger integrity failure')
    return [r for p in sorted(Path(root).glob('*.jsonl')) for r in boxscores.read_store(p)]


def public_rows(root=STORE):
    saved=rows(root)
    original={r['id']:r for r in saved if r.get('type')=='publish'}
    finals={r['id']:r for r in saved if r.get('type')=='settle'}
    return [{**r, **{k:v for k,v in finals.get(key,{}).items()
                     if k in ('result','actual','settledAt','resultSource')}} for key,r in original.items()]


def finite(n):
    return type(n) in (float,int) and math.isfinite(n)


def web(url, book=None):
    try:
        p=urlparse(url)
        host=p.hostname or ''
        return p.scheme=='https' and bool(host) and not p.username and not p.password and (
            not book or host=='draftkings.com' or host.endswith('.draftkings.com'))
    except (TypeError,ValueError):
        return False


def refusal(play, now, *, check_day=True):
    try:
        g=play['game']; review=play['review']; quote=play['quote']
        if not re.fullmatch(r'CBB-[A-Za-z0-9-]{1,120}',str(play.get('id',''))):return 'Invalid CBB pick ID'
        tip=boxscores.instant(g['kickoff']); checked=boxscores.instant(review['checkedAt'])
        seen=boxscores.instant(quote['checkedAt'])
        if (play.get('league')!='CBB' or play.get('selectionMethod')!=METHOD
                or g.get('id')!=play.get('eventId') or not str(g['id']).startswith('CBB-')
                or g.get('status')!='scheduled' or g.get('seasonType')!='regular-season'
                or g.get('timeConfirmed') is not True or type(g.get('neutral')) is not bool):
            return 'Verified CBB regular-season fixture required'
        if tip<=now+timedelta(minutes=15) or check_day and tip.astimezone(gates.EASTERN).date()!=now.astimezone(gates.EASTERN).date():
            return 'Current-day pregame release window required'
        if not timedelta(0)<=now-seen<=timedelta(hours=1) or not seen<=checked<=now or now-checked>timedelta(hours=1):
            return 'Exact quote and current review need renewal'
        if (quote.get('verified') is not True or quote.get('book')!='DraftKings'
                or not web(quote.get('source'),quote['book']) or not quote.get('receipt')):
            return 'Visible exact DraftKings quote receipt required'
        if play.get('marketType') not in ('total','spread') or play.get('period')!='full_game' or play.get('alternate') is not False:
            return 'Main full-game spreads and totals only'
        if any(play.get(k) is not None for k in ('chance','rawChance','fairOdds','expectedValue','calibrated')):
            return 'Sourced decision cannot claim validated probability or EV'
        market=play['marketType'];side=play['direction'];line=play['line'];odds=play['odds'];opposite=play['oppositeOdds']
        if side not in (('over','under') if market=='total' else ('home','away')) or not finite(line) or market=='total' and line<=0:
            return 'Exact market side and line required'
        if any(not finite(v) or int(v)!=v or not 100<=abs(v)<=10000 for v in (odds,opposite)):
            return 'Two exact American prices required'
        import espn_props
        if not .99<=espn_props.implied(odds)+espn_props.implied(opposite)<=1.15:
            return 'Two-sided price pair inconsistent'
        if any(quote.get(k)!=play.get(k) for k in ('marketType','direction','line','odds','oppositeOdds')):
            return 'Original terms differ from the reviewed quote'
        if play.get('riskUnits')!=1 or type(play['riskUnits']) is bool or play.get('stakingPolicy')!=staking.CURRENT_VERSION:
            return 'Ordinary one-unit CBB straight only'
        if review.get('reviewer')!='kookn-desk' or review.get('approved') is not True:
            return 'Explicit sourced desk approval required'
        if any(not isinstance(review.get(k),str) or not review[k].strip() for k in ('why','countercase','availability')):
            return 'Reason, countercase and availability check required'
        facts=review.get('sources')
        teams={str(t['id']) for t in g['teams'].values()}
        if not isinstance(facts,list) or {str(f.get('teamId')) for f in facts}!=teams:
            return 'Current source packet must cover both teams'
        for fact in facts:
            at=boxscores.instant(fact['checkedAt'])
            if not web(fact['url']) or not fact.get('fact') or not timedelta(0)<=now-at<=timedelta(hours=24):
                return 'Fresh sourced team facts required'
        import social_style
        if social_style.privacy_issues(review['why']):return 'Private information in public reason'
    except (KeyError,TypeError,ValueError,OverflowError):
        return 'Incomplete reviewed CBB evidence'
    return None


def admit(play, ctx, now, root=STORE):
    held=refusal(play,now)
    if held:raise ValueError(held)
    canonical={**getattr(ctx,'risk_games',{}),**ctx.games}.get(play['eventId'])
    if not canonical or any(canonical.get(k)!=play['game'].get(k) for k in ('kickoff','season','neutral','teams','status','seasonType','timeConfirmed')):
        raise ValueError('Reviewed fixture differs from the current stored CBB slate')
    import x_post,social_style
    text=caption(dict(play,book='DraftKings'))
    if x_post.x_style(text) or social_style.issues(text) or x_post.tweet_length(text)>x_post.LIMIT:
        raise ValueError('CBB caption must pass public style and length checks')
    saved=rows(root)
    if any(r.get('id')==play['id'] for r in saved):raise ValueError('Published CBB ID is immutable')
    if any(r.get('type')=='publish' and r['eventId']==play['eventId'] for r in saved):
        raise ValueError('One CBB straight per game')
    play=dict(play,kickoff=play['game']['kickoff'],gameIds=[play['eventId']])
    held=staking.check(play,ctx)
    if held:raise ValueError(held)
    row=dict(play,type='publish',publishedAt=boxscores.stamp(now),retrievedAt=boxscores.stamp(now),book='DraftKings',
             kickoff=play['game']['kickoff'],season=play['game']['season'],series='CBB Pick')
    return nba_capture.append_changed([row],Path(root),lambda r:(r['type'],r['id']))


def selection(p):
    return (f"{p['direction'].upper()} {p['line']:g}" if p['marketType']=='total' else
            f"{p['game']['teams'][p['direction']]['abbreviation']} {p['line']:+g}")


def caption(p):
    import social_voice, buffer_post
    teams=p['game']['teams']
    return buffer_post.x_ticket_copy(social_voice.finish(
        f"🏀 CBB PICK\n{teams['away']['abbreviation']} at {teams['home']['abbreviation']}\n"
        f"{selection(p)} ({p['odds']:+d}, DraftKings) · 1u\n\n{p['review']['why']}\n#CBB"),'play',p['id'])


def current_match(play,now,root=STORE):
    # Current exact terms must be renewed explicitly; a build cannot fabricate
    # another sportsbook observation or turn the historical quote into live odds.
    return not play.get('result') and refusal(play,now) is None


def plans(now,log_book,root=STORE,reserved=()):
    import buffer_post,x_post
    busy=buffer_post.taken(log_book,now)+[p[3] for p in reserved]
    result=[]
    for p in public_rows(root):
        entry=next((e for e in log_book.get('posts',[]) if e['id']==p['id']),None)
        if entry and (not entry.get('cbbDiscordOnly') or entry.get('bufferPostId') or entry.get('sentAt') or entry.get('webDelivery')):continue
        if not current_match(p,now) or delivery_pending(p['id'],root):continue
        text=caption(p)
        if x_post.x_style(text) or x_post.tweet_length(text)>x_post.LIMIT:continue
        due=buffer_post.free_slot(post_windows.play_due(now,now),busy)
        if due>=min(boxscores.instant(p['game']['kickoff'])-timedelta(minutes=15),boxscores.instant(p['quote']['checkedAt'])+timedelta(hours=1)):continue
        result.append((p['id'],'cbb-pick',text,due,p['id'].lower()));busy.append(due)
    for p in public_rows(root):
        if not p.get('result') or not now-timedelta(days=3)<=boxscores.instant(p['settledAt'])<=now:continue
        original=next((e for e in reversed(log_book.get('posts',[])) if e.get('id')==p['id']
                       and e.get('sentAt') and e.get('tweetId') and not e.get('cancelledAt')
                       and not e.get('deletedAt')),None)
        if not original:continue
        guid=result_key(p)
        if any(e['id']==guid for e in log_book.get('posts',[])):continue
        due=buffer_post.free_slot(now,busy)
        result.append((guid,'receipt',result_text(p),due,guid.replace(':','-').lower()));busy.append(due)
    return result


def result_key(p):
    import hashlib
    signature=hashlib.sha256(f"{p['result']}:{p['actual']}".encode()).hexdigest()[:10]
    return f"receipt:cbb:{p['id']}:{signature}"


def result_detail(p):
    if p['marketType']=='total':return f"Game total: {p['actual']:g}"
    team=p['game']['teams'][p['direction']]['abbreviation']
    return f"{team} scoring margin: {p['actual']:+g}"


def result_text(p):
    net=(100/-p['odds'] if p['odds']<0 else p['odds']/100) if p['result']=='win' else -1 if p['result']=='loss' else 0
    day=boxscores.instant(p.get('kickoff') or p['game']['kickoff']).astimezone(gates.EASTERN).strftime('%b %d')
    return (f"{'✅' if p['result']=='win' else '❌' if p['result']=='loss' else '➖'} CBB FINAL · {day}\n"
            f"{p['game']['teams']['away']['abbreviation']} at {p['game']['teams']['home']['abbreviation']}\n"
            f"{selection(p)} ({p['odds']:+d}, DraftKings)\n{result_detail(p)} · {net:+.2f}u")


def queue_discord(now,log_book,root=STORE,opener=None):
    import buffer_post,x_post
    count=0
    for guid,kind,text,due,key in plans(now,log_book,root):
        if kind!='cbb-pick':continue
        if any(e['id']==guid for e in log_book.get('posts',[])):continue
        image=buffer_post.live_card_url(key,opener)
        if not image or not buffer_post.ticket_art_live(image) or not buffer_post.plain_art_live(image):continue
        log_book.setdefault('posts',[]).append(dict(id=guid,kind='buffer:cbb-pick',cbbPick=True,cbbDiscordOnly=True,
            postedAt=boxscores.stamp(now),dueAt=boxscores.stamp(due),queuedText=text,textHash=x_post.text_hash(text),
            card=True,cardKey=key,discord=dict(state='pending',destination='plays',text=buffer_post.without_playbook(text),
            image=image,readyAt=boxscores.stamp(now))))
        count+=1
    return count


def grade(now,root=STORE,finals=None):
    import hoops_store
    finals=hoops_store.load('CBB') if finals is None else finals
    available={str(r['eventId']):r for r in finals if r.get('retrievedAt') and boxscores.instant(r['retrievedAt'])<=now}
    count=0
    for p in public_rows(root):
        f=available.get(p['eventId']) or available.get(p['eventId'].removeprefix('CBB-'))
        if not f or boxscores.instant(p['kickoff'])>=now or f.get('type')!=2 or f.get('season')!=p['season'] or boxscores.instant(f['kickoff'])!=boxscores.instant(p['kickoff']):continue
        if str(f['home']['id'])!=str(p['game']['teams']['home']['id']) or str(f['away']['id'])!=str(p['game']['teams']['away']['id']):continue
        h,a=f['homeScore'],f['awayScore']
        if not finite(h) or not finite(a):continue
        actual=h+a if p['marketType']=='total' else (h-a if p['direction']=='home' else a-h)
        margin=(actual-p['line'])*(1 if p['direction']=='over' else -1) if p['marketType']=='total' else actual+p['line']
        result='win' if margin>0 else 'loss' if margin<0 else 'push'
        if p.get('result')==result and p.get('actual')==actual:continue
        count+=nba_capture.append_changed([dict(type='settle',id=p['id'],league='CBB',season=p['season'],result=result,
            actual=actual,resultSource=f.get('source') or ('https://www.espn.com/mens-college-basketball/boxscore/_/gameId/'+str(f['eventId'])),settledAt=boxscores.stamp(now),retrievedAt=boxscores.stamp(now))],Path(root),lambda r:(r['type'],r['id']))
    return count


def payload(root=STORE, *, delivered):
    receipts = {row['id']: row for row in delivered}
    plays = [{**play, **{key: receipts[play['id']].get(key) for key in ('result', 'actual', 'settledAt')}}
             for play in public_rows(root) if play['id'] in receipts]
    net=sum((100/-p['odds'] if p['odds']<0 else p['odds']/100) if p.get('result')=='win' else -1 if p.get('result')=='loss' else 0 for p in plays)
    public=[{k:p[k] for k in ('id','eventId','game','publishedAt','kickoff','marketType','direction','line','odds','oppositeOdds','book','riskUnits','series','result','actual','settledAt','resultSource') if k in p} | dict(reason=p['review']['why'],countercase=p['review']['countercase'],sources=[dict(url=f['url'],fact=f['fact']) for f in p['review']['sources']]) for p in plays]
    return dict(plays=public,win=sum(p.get('result')=='win' for p in plays),loss=sum(p.get('result')=='loss' for p in plays),
                push=sum(p.get('result')=='push' for p in plays),units=round(net,6),
                note='Sourced desk picks; separate from baseline model accuracy, fun tickets and Climbs.')


def render(folder,root=STORE):
    import nba_trial,pick_card
    for p in public_rows(root):
        target=Path(folder)/(p['id'].lower()+'.png')
        if target.exists():
            if p.get('result'):render_result(p,folder)
            continue
        q=p['quote'];market=p['marketType'];side=p['direction']
        current=({'total':dict(line=p['line'],**{side:p['odds'],('under' if side=='over' else 'over'):p['oppositeOdds']})}
                 if market=='total' else {side:dict(spreadPrice=p['odds'],spreadLine=p['line']),
                    ('away' if side=='home' else 'home'):dict(spreadPrice=p['oppositeOdds'],spreadLine=-p['line'])})
        # Keep immutable fixture names; use the provider's compact names on art.
        game=dict(p['game'],teams={side:dict(team,name=team.get('shortName') or team['abbreviation'])
                                  for side,team in p['game']['teams'].items()})
        svg=nba_trial.preview_svg(game,dict(book='DraftKings',retrievedAt=q['checkedAt'],current=current),
            preview=False,direction=side,market=market,line=p['line'],odds=p['odds'],units=1,
            reason=p['review']['why'],series_label='CBB PICK')
        pick_card.render(svg,target)
        if p.get('result'):render_result(p,folder)


def render_result(p,folder):
    import ticket_cards,pick_card
    key=result_key(p).replace(':','-').lower();target=Path(folder)/(key+'.png')
    # Win/loss art was upgraded from a recap row to the owner-approved
    # individual Final. Re-render those keys so an old cached layout cannot
    # survive a normal hosted build.
    if target.exists() and p.get('result') not in ('win','loss'):return
    t=p['game']['teams']
    net=(100/-p['odds'] if p['odds']<0 else p['odds']/100) if p['result']=='win' else -1 if p['result']=='loss' else 0
    if p['result'] in ('win','loss'):
        try:
            import hoops_store
            final=next((r for r in reversed(hoops_store.load('CBB'))
                        if str(r.get('eventId'))==str(p['eventId']).removeprefix('CBB-') and r.get('type')==2),None)
        except (OSError,ValueError,TypeError):
            final=None
        away_score=(final or {}).get('awayScore');home_score=(final or {}).get('homeScore')
        score=(f'{away_score:g}-{home_score:g}' if finite(away_score) and finite(home_score)
               else f'{p["actual"]:g}')
        selected=t[p['direction']] if p['marketType']=='spread' else t['away']
        logo=None
        try:
            logo=pick_card.fetch_data_uri(selected.get('logo')) if selected.get('logo') else None
        except (OSError,ValueError,TypeError):
            pass
        logo=logo or str(ROOT/'site/kookn-chef.png')
        margin=abs(p['actual']-p['line']) if p['marketType']=='total' else abs(p['actual']+p['line'])
        close=(f"FINAL: {t['away']['abbreviation']} {away_score:g}, {t['home']['abbreviation']} {home_score:g}"
               if finite(away_score) and finite(home_score) else result_detail(p))
        data=dict(player=(selected.get('shortName') or selected['abbreviation']).upper(),
            side=selection(p),line='',market=p['marketType'],odds=p['odds'],book=p['book'],final=score,
            margin=f'{margin:g}',photo=None,team_logo=logo,close_line=close,
            chip='CBB PICK · FINAL',**({'units_won':net} if p['result']=='win' else {'units_lost':net}))
        card=ticket_cards.cooked_card(data) if p['result']=='win' else ticket_cards.burnt_card(data)
        pick_card.render(card.svg(),target)
        return
    day=boxscores.instant(p.get('kickoff') or p['game']['kickoff']).astimezone(gates.EASTERN).strftime('%b %d')
    matchup=' AT '.join((t[s].get('shortName') or t[s]['abbreviation']).upper() for s in ('away','home'))
    data=dict(headline='CBB '+p['result'].upper(),row_label='CBB PICKS',net_units=net,
        rows=[dict(title=selection(p),detail=f"{day} · {matchup} · {p['odds']:+d} {p['book']} · {result_detail(p)}",
                   result={'win':'hit','loss':'miss'}.get(p['result'],'push'),unit_text=f'{net:+.2f}u')])
    pick_card.render(ticket_cards.final_card(data).svg(),target)


def queue_results(log_book,now,root=STORE):
    saved={p['id']:p for p in public_rows(root)};count=0
    for entry in log_book.get('posts',[]):
        p=saved.get(entry['id']);mirror=entry.get('discord') or {}
        if entry.get('kind')!='buffer:cbb-pick' or entry.get('cbbPick') is not True or not p or not p.get('result') or mirror.get('state')!='sent':continue
        signature=f"{p['result']}:{p['actual']}";old=mirror.get('result')
        if old and (old.get('gradeHash')==signature or old.get('state')!='sent'):continue
        if old:mirror.setdefault('previousResults',[]).append(dict(old))
        import social_voice,social_copy
        text=social_copy.with_age_notice(social_voice.finish(result_text(p)))
        mirror['result']=dict(state='pending',text=text,gradeHash=signature,settledAt=p['settledAt'])
        entry['discord']=mirror;count+=1
    return count




def delivery_pending(guid,root=STORE):
    latest=next((r for r in reversed(rows(root)) if r.get('type')=='delivery' and r['id']==guid),None)
    return bool(latest and latest['state']=='reserved')


def reserve_delivery(guid,now,root=STORE):
    p=next((p for p in public_rows(root) if p['id']==guid),None)
    if not p or not current_match(p,now) or delivery_pending(guid,root):return False
    nba_capture.append_changed([dict(type='delivery',id=guid,season=p['season'],state='reserved',
        retrievedAt=boxscores.stamp(now))],Path(root),lambda r:(r['type'],r['id']))
    return True


def delivery_failed(guid,now,root=STORE):
    p=next((p for p in public_rows(root) if p['id']==guid),None)
    if p:nba_capture.append_changed([dict(type='delivery',id=guid,season=p['season'],state='failed',
        retrievedAt=boxscores.stamp(now))],Path(root),lambda r:(r['type'],r['id']))


def discord_delivery_due(now,log_book,root=STORE):
    known={e['id'] for e in log_book.get('posts',[])}
    return any(p['id'] not in known and current_match(p,now) for p in public_rows(root))


def precheck(now,log_book,root=STORE,delete=None):
    import buffer_post
    originals={p['id']:p for p in public_rows(root)};changed=False
    for e in log_book.get('posts',[]):
        if e.get('kind')!='buffer:cbb-pick' or not e.get('bufferPostId') or e.get('sentAt') or e.get('cancelledAt'):continue
        if not 0<=(boxscores.instant(e['dueAt'])-now).total_seconds()<=45*60:continue
        p=originals.get(e['id']);okay=bool(p and current_match(p,now))
        e['cbbPrecheck']=dict(at=boxscores.stamp(now),result='clear' if okay else 'held');changed=True
        if not okay:
            (delete or buffer_post.delete_post)(e['bufferPostId'])
            e['cancelledAt']=boxscores.stamp(now)
            e['cbbHold']='Current quote/review expired. Original public terms and record are retained.'
    return changed


if __name__=='__main__':
    import argparse,run,release_queue
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',required=True)
    parser.add_argument('--admit',action='store_true')
    args=parser.parse_args();spec=json.loads(Path(args.spec).read_text())
    if not args.admit:
        held=refusal(spec,datetime.now(timezone.utc));print(json.dumps(dict(state='held' if held else 'preview',reason=held)))
    else:
        with run.Lock(run.CONF/'run.lock',wait=run.RUN_LOCK_WAIT):
            run.sync();now=datetime.now(timezone.utc);ctx=gates.Stores().as_of(now)
            release_queue.merge_context(ctx,run.CONF)
            print(json.dumps(dict(admitted=admit(spec,ctx,now))))
