"""Owner-approved NBA team and player research, frozen before delivery.

No feed calls or play admission. Team cards plus one fresh, roster-verified player
research card; football research and shared delivery caps remain separate.
"""
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boxscores
import gates
import hoops_store
import pick_card
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data/nba-editorial'
START = '2026-10-20'
REVIEW = Path(os.environ.get('KEENROUDY_CONF') or Path.home()/'.config/keenroudy')/'nba-editorial-review.json'
PROP_REVIEW = REVIEW.with_name('nba-props-review.json')


def prop_text(rows, book, window):
    return '\n'.join([f'NBA prop looks · {book}', *[r['caption'] for r in rows],
                      f'{window} · last 10 recorded games.', 'Research, not a bet.', '#NBA'])


def prop_choice(data,now,preview=False):
    """One early exact-price player research card, separate from team cards.

    Freeze only after the game-day 8:30 refresh, not on overnight prices. First
    preview can be rendered earlier, but is never a publishable post.
    """
    import x_post
    day=eastern_date(now)
    rows=[]; seen=set(); evidence=[]
    for r in (data.get('playerProps') or {}).get('rows',[]):
        if not r.get('favorite') or r.get('hold') or not r.get('projection') or r['athleteId'] in seen:
            continue
        if r.get('stat') not in ('pts','reb','ast','fg3m'):continue
        kickoff=boxscores.instant(r['kickoff']);target=eastern_date(kickoff)
        if (not preview and (target!=day or (now.astimezone(gates.EASTERN).hour,now.astimezone(gates.EASTERN).minute)<(8,30))) or kickoff<=now+timedelta(hours=2):
            continue
        if evidence and eastern_date(boxscores.instant(evidence[0]['kickoff']))!=target:continue
        if not timedelta(0)<=now-boxscores.instant(r['sourceAt'])<=timedelta(hours=4):continue
        p=r['projection'];h=r['last10'];side=r['side']
        item={'subject':r['name'],'line':f"{side.title()} {r['line']:g} {r['statName']} {r['odds']:+d}",
              'right':f"{p['value']:g}",'logo':r.get('photo'),
              'detail':f"{r['teamAbbr']} · {r['book']} · {h['hits']}/{h['games']} {p['window'].lower()}",
              'caption':f"{r['name']} · {r['teamName']}\n{side.title()} {r['line']:g} {r['statName']} {r['odds']:+d} · I have {p['value']:g}"+
                        (f" at {p['minutes']:g} estimated min" if p.get('minutesBasis')=='analyst-estimate' else '')+
                        f" · {h['hits']}/{h['games']}"}
        if rows and (r['book']!=evidence[0]['book'] or p['window']!=evidence[0]['projection']['window']):continue
        proposed=rows+[item]
        proposed_text=prop_text(proposed,r['book'],p['window'])
        if x_post.tweet_length(proposed_text)>x_post.LIMIT or x_post.x_style(proposed_text):continue
        text=proposed_text
        rows=proposed;evidence.append(r);seen.add(r['athleteId'])
        if len(rows)==3:break
    if len(rows)<2:return None
    target=eastern_date(boxscores.instant(evidence[0]['kickoff']))
    due=datetime(target.year,target.month,target.day,9,15,tzinfo=gates.EASTERN).astimezone(timezone.utc)
    cutoff=min(min(boxscores.instant(r['kickoff']) for r in evidence)-timedelta(hours=2),
               min(boxscores.instant(r['sourceAt']) for r in evidence)+timedelta(hours=4))
    if not preview and now>=cutoff:return None
    return {'key':f'nba-props-{target}' if not preview else 'nba-props-preview','family':'props','day':target.isoformat(),
            'capturedAt':boxscores.stamp(now),'sourceAt':data['sourceAt'],'due':boxscores.stamp(due),
            'stale':boxscores.stamp(cutoff),'rows':rows,'evidence':evidence,'text':text,
            'title':'NBA PROP PREVIEW' if preview else 'NBA PROP LOOKS',
            'preview':bool(preview),'kicker':f"{eastern_date(now):%b %-d} · PREVIEW" if preview else f"{target:%b %-d} · PLAYER RESEARCH",'right_label':'MY NUMBER'}


def props_current(snapshot,now):
    import nba_player_props
    current=nba_player_props.build(now)['rows']
    for old in snapshot.get('evidence',[]):
        if not any(all(r.get(k)==old.get(k) for k in ('eventId','athleteId','stat','book','line','over','under'))
                   and r.get('projection')==old.get('projection')
                   and not r.get('hold') and r.get('favorite') for r in current):return False
    return bool(snapshot.get('evidence'))


def team_trends(games, now, history=None):
    history = hoops_store.load('NBA') if history is None else history
    out = []
    for game in games:
        for side in ('away', 'home'):
            team = game['teams'][side]
            current = int(game['season'])
            own = [r for r in history if r.get('type') == 2 and r.get('season') in (current, current-1)
                   and r.get('state') == 'post' and boxscores.instant(r['kickoff']) < now
                   and any(str((r.get(s) or {}).get('id')) == str(team['id']) for s in ('home', 'away'))
                   and all(isinstance(r.get(s+'Score'), (int, float)) for s in ('home', 'away'))]
            season = current if sum(r['season'] == current for r in own) >= 5 else current-1
            window = sorted((r for r in own if r['season'] == season), key=lambda r:r['kickoff'])[-10:]
            if len(window) < 5:
                continue
            points, allowed = [], []
            for row in window:
                home = str(row['home']['id']) == str(team['id'])
                points.append(row['homeScore' if home else 'awayScore'])
                allowed.append(row['awayScore' if home else 'homeScore'])
            out.append({'team': team, 'season': season, 'games':len(window),
                        'points':round(sum(points)/len(points),1), 'allowed':round(sum(allowed)/len(allowed),1),
                        'first':window[0]['kickoff'], 'last':window[-1]['kickoff'],
                        'window': 'CURRENT SEASON' if season == current else 'LAST SEASON',
                        'source':'ESPN stored regular-season finals'})
    return out


def choices(data, now, history=None):
    """Today or tomorrow only; no stale schedule, preseason or begun game."""
    try:
        if not timedelta(0) <= now-boxscores.instant(data['sourceAt']) <= timedelta(hours=24):
            return []
    except (KeyError, TypeError, ValueError):
        return []
    day = eastern_date(now)
    games = [g for g in data.get('games',[]) if g.get('status') == 'scheduled'
             and g.get('seasonType') == 'regular-season'
             and day <= eastern_date(boxscores.instant(g['kickoff'])) <= day+timedelta(days=1)
             and boxscores.instant(g['kickoff']) > now+timedelta(hours=2)
             and all(isinstance((g.get('projection') or {}).get(s), (int,float))
                     and math.isfinite(g['projection'][s]) for s in ('home','away','total'))]
    if not games:
        return []
    target = min(eastern_date(boxscores.instant(g['kickoff'])) for g in games)
    if target.isoformat() < START:
        return []
    games = sorted((g for g in games if eastern_date(boxscores.instant(g['kickoff'])) == target),key=lambda g:g['kickoff'])
    # A large slate is explicitly a selection, with the full board linked.
    projected = []
    names = lambda g: ' at '.join(g['teams'][s].get('name') or g['teams'][s].get('displayName') or g['teams'][s]['abbreviation'] for s in ('away','home'))
    for g in games[:5]:
        p=g['projection'];a=g['teams']['away'];h=g['teams']['home']
        projected.append({'subject':f"{a['abbreviation']} at {h['abbreviation']}",
                          'line':f"My score {p['away']:g} - {p['home']:g}", 'right':f"{p['total']:g}",
                          'detail':'', 'logo':a.get('logo'),
                          'caption':f"{names(g)}: {p['away']:g}-{p['home']:g}"})
    if len(games)==1:
        g=games[0]
        projected=[{'subject':g['teams'][s]['abbreviation'],'line':'My projected points',
                    'right':f"{g['projection'][s]:g}",'detail':'',
                    'logo':g['teams'][s].get('logo'),
                    'caption':f"{g['teams'][s].get('name') or g['teams'][s].get('displayName') or g['teams'][s]['abbreviation']}: {g['projection'][s]:g}"}
                   for s in ('away','home')]
    trends = team_trends(games,now,history)
    # Keep one window per card. Never blend last season with this season.
    chosen = [r for r in trends if r['season']==max((t['season'] for t in trends),default=0)][:5]
    trend_rows=[{'subject':r['team']['abbreviation'], 'line':f"Gave up {r['allowed']:g} per game",
                 'right':f"{r['points']:g}", 'detail':f"Last {r['games']} games · {r['window'].lower()}", 'logo':r['team'].get('logo'),
                 'caption':f"{r['team'].get('name') or r['team'].get('displayName') or r['team']['abbreviation']}: {r['points']:g} scored / {r['allowed']:g} given up per game",
                 'history':r} for r in chosen]
    out=[]
    for family,rows,hour,title in [('projections',projected,8,'NBA PROJECTIONS'),('trends',trend_rows,10,'NBA TEAM TRENDS')]:
        if len(rows)<2:
            continue
        due=datetime(target.year,target.month,target.day,hour,tzinfo=gates.EASTERN).astimezone(timezone.utc)
        cutoff=min(due+timedelta(hours=2),boxscores.instant(games[0]['kickoff'])-timedelta(hours=2))
        if now>=cutoff:
            continue
        import x_post
        prefix=(f"NBA {target:%b %-d}: my scores" if family=='projections' else
                f"NBA · Last {chosen[0]['games']} games, {chosen[0]['window'].lower()}")
        note=('Research, not a bet.' if family=='projections' else
              'Scoring context, not a forecast. Research, not a bet.')
        # All rows on the graphic also appear in the caption; shorten the card,
        # never use +N more or silently drop a displayed team from the words.
        while len(rows)>=2:
            text='\n'.join([prefix,*[r['caption'] for r in rows],note,'#NBA'])
            if x_post.tweet_length(text)<=x_post.LIMIT:
                break
            rows=rows[:-1]
        else:
            continue
        out.append({'key':f'nba-{family}-{target}', 'family':family, 'day':target.isoformat(),
                    'capturedAt':boxscores.stamp(now),'sourceAt':data['sourceAt'],
                    'due':boxscores.stamp(due),'stale':boxscores.stamp(cutoff),'rows':rows,'text':text,
                    'title':title,'kicker':(f"{target:%b %-d} · TEAM RESEARCH" if family=='projections' else
                        ('LAST SEASON · NEW ROSTERS MAY DIFFER' if chosen[0]['window']=='LAST SEASON' else
                         'THIS SEASON · SCORING CONTEXT')),
                    'right_label':'MY TOTAL' if family=='projections' else 'AVG POINTS'})
    return out


def prepare(now, root=STORE, data=None, history=None):
    if data is None:
        import nba_today
        data=nba_today.build(now)
    import x_post
    attempted={r.get('id') for r in x_post.load_log().get('posts',[]) if r.get('bufferPostId') or r.get('sentAt')}
    previous={r['key']:r for r in stored(root)}
    created=[]
    prop=prop_choice(data,now)
    for row in choices(data,now,history)+([prop] if prop else []):
        old=previous.get(row['key'])
        if old:
            current_draft=(old.get('family')!='props' or props_current(old,now))
            # Never rewrite a frozen/queued publication. A never-queued invalid or expired
            # draft may get a new immutable revision under the same deduplicated post ID.
            if row['key'] in attempted or (current_draft and boxscores.instant(old['stale'])>now
                    and not x_post.x_style(old['text'])
                    and x_post.tweet_length(old['text'])<=x_post.LIMIT):
                continue
        path=Path(root)/f"{row['key']}.json"
        if old:
            path=Path(root)/f"{row['key']}.r{now:%Y%m%dT%H%M%S%f}.json"
            row=dict(row,supersedesCapturedAt=old['capturedAt'])
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with path.open('x') as f:
                json.dump(row,f,ensure_ascii=False,indent=2);f.write('\n')
            created.append(row['key'])
        except FileExistsError:
            pass
    return created


def stored(root=STORE):
    rows=[json.loads(p.read_text()) for p in sorted(Path(root).glob('nba-*.json'))]
    latest={}
    for row in sorted(rows,key=lambda r:r['capturedAt']):
        latest[row['key']]=row
    return list(latest.values())


def review_ready(due, review=None, path=None):
    if review is None:
        try:
            review=json.loads((path or REVIEW).read_text())
        except (OSError,ValueError):
            return False
    try:
        return (review.get('delivered') is True and not review.get('vetoed')
                and due-boxscores.instant(review['sentAt'])>=timedelta(hours=2))
    except (KeyError,TypeError,ValueError):
        return False


def posts(now, root=STORE, review=None):
    return [dict(key=r['key'],kind='research',text=r['text'],due=boxscores.instant(r['due']),
                 stale=boxscores.instant(r['stale']),card=r['key']) for r in stored(root)
            if not r.get('preview') and now<boxscores.instant(r['stale']) and boxscores.instant(r['due'])-now<=timedelta(days=1)
            and review_ready(boxscores.instant(r['due']),review,PROP_REVIEW if r.get('family')=='props' else REVIEW)
            and (r.get('family')!='props' or props_current(r,now))]


def veto_pending(entry, now=None):
    if (not re.fullmatch(r'nba-(?:projections|trends|props)-\d{4}-\d{2}-\d{2}',str(entry.get('id') or ''))
            or not entry.get('bufferPostId') or any(entry.get(k) for k in ('sentAt','cancelledAt','deletedAt'))):
        return False
    try:
        due=boxscores.instant(entry['dueAt'])
    except (KeyError,TypeError,ValueError):
        return False
    # Never issue a delete against a post that may already have gone live.
    now=now or datetime.now(timezone.utc)
    if due<=now:return False
    if str(entry['id']).startswith('nba-props-'):
        snapshot=next((r for r in stored() if r['key']==entry['id']),None)
        return not review_ready(due,path=PROP_REVIEW) or not snapshot or not props_current(snapshot,now)
    return not review_ready(due)


def render_due(now, folder, root=STORE, fetch=None, log=print, posted_keys=(), restore=None):
    import ticket_cards,ticket_kit,check_svg
    out={};fetch=fetch or pick_card.fetch_data_uri
    for row in stored(root):
        if not timedelta(0)<=now-boxscores.instant(row['capturedAt'])<=timedelta(days=8):
            continue
        path=Path(folder)/f"{row['key']}.png"
        if row['key'] in posted_keys:
            if restore:
                restore(folder, [row['key']])
            if not path.is_file():
                raise ValueError(f"Original posted NBA art missing: {row['key']}")
            out[row['key']]=path
            continue
        rows=[]
        for item in row['rows']:
            art=None
            if str(item.get('logo') or '').startswith('https://a.espncdn.com/'):
                try:
                    art=fetch(item['logo'])
                except (OSError,ValueError):
                    pass
            rows.append(dict(item,art=art))
        card=ticket_cards.research_list_card(dict(row,rows=rows,stub='RESEARCH · NOT A BET'))
        problems=ticket_kit.qa(card,row['key'])+check_svg.issues(card.svg())
        if problems:
            raise ValueError('; '.join(problems))
        path=Path(folder)/f"{row['key']}.png"
        pick_card.render(card.svg(),path);out[row['key']]=path
    return out
