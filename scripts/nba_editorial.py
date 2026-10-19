"""Owner-approved NBA projection and team-trend research, frozen before delivery.

No feed calls, player model, price claims or play admission. Two early research
posts per NBA game day; football research and all delivery caps remain separate.
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
                        'window': 'THIS SEASON' if season == current else 'LAST SEASON',
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
                          'detail':'Early team ratings · research', 'logo':a.get('logo'),
                          'caption':f"{names(g)}: {p['away']:g}-{p['home']:g}"})
    if len(games)==1:
        g=games[0]
        projected=[{'subject':g['teams'][s]['abbreviation'],'line':'My projected points',
                    'right':f"{g['projection'][s]:g}",'detail':'Team research',
                    'logo':g['teams'][s].get('logo'),
                    'caption':f"{g['teams'][s].get('name') or g['teams'][s].get('displayName') or g['teams'][s]['abbreviation']}: {g['projection'][s]:g}"}
                   for s in ('away','home')]
    trends = team_trends(games,now,history)
    # Keep one window per card. Never blend last season with this season.
    chosen = [r for r in trends if r['season']==max((t['season'] for t in trends),default=0)][:5]
    trend_rows=[{'subject':r['team']['abbreviation'], 'line':f"Scored {r['points']:g} · allowed {r['allowed']:g}",
                 'right':f"{r['games']} G", 'detail':f"{r['window']} · regular season", 'logo':r['team'].get('logo'),
                 'caption':f"{r['team'].get('name') or r['team'].get('displayName') or r['team']['abbreviation']}: {r['points']:g} scored / {r['allowed']:g} allowed",
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
                f"NBA {target:%b %-d}: {chosen[0]['window'].lower()}, last {chosen[0]['games']} recorded games")
        note='Early team ratings; not player projections.' if family=='projections' else 'Regular season. Team history, not prop picks.'
        # All rows on the graphic also appear in the caption; shorten the card,
        # never use +N more or silently drop a displayed team from the words.
        while len(rows)>=2:
            text='\n'.join([prefix,*[r['caption'] for r in rows],note,'Full board: keenroudy.com/sports/#today?sport=NBA','#NBA'])
            if x_post.tweet_length(text)<=x_post.LIMIT:
                break
            rows=rows[:-1]
        else:
            continue
        out.append({'key':f'nba-{family}-{target}', 'family':family, 'day':target.isoformat(),
                    'capturedAt':boxscores.stamp(now),'sourceAt':data['sourceAt'],
                    'due':boxscores.stamp(due),'stale':boxscores.stamp(cutoff),'rows':rows,'text':text,
                    'title':title,'kicker':f"{target:%b %-d} · TEAM RESEARCH",'right_label':'MY TOTAL' if family=='projections' else 'SAMPLE'})
    return out


def prepare(now, root=STORE, data=None, history=None):
    if data is None:
        import nba_today
        data=nba_today.build(now)
    created=[]
    for row in choices(data,now,history):
        path=Path(root)/f"{row['key']}.json"
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with path.open('x') as f:
                json.dump(row,f,ensure_ascii=False,indent=2);f.write('\n')
            created.append(row['key'])
        except FileExistsError:
            pass
    return created


def stored(root=STORE):
    return [json.loads(p.read_text()) for p in sorted(Path(root).glob('nba-*.json'))]


def review_ready(due, review=None):
    if review is None:
        try:
            review=json.loads(REVIEW.read_text())
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
            if now<boxscores.instant(r['stale']) and boxscores.instant(r['due'])-now<=timedelta(days=1)
            and review_ready(boxscores.instant(r['due']),review)]


def veto_pending(entry, now=None):
    if (not re.fullmatch(r'nba-(?:projections|trends)-\d{4}-\d{2}-\d{2}',str(entry.get('id') or ''))
            or not entry.get('bufferPostId') or any(entry.get(k) for k in ('sentAt','cancelledAt','deletedAt'))):
        return False
    try:
        due=boxscores.instant(entry['dueAt'])
    except (KeyError,TypeError,ValueError):
        return False
    # Never issue a delete against a post that may already have gone live.
    return due>(now or datetime.now(timezone.utc)) and not review_ready(due)


def render_due(now, folder, root=STORE, fetch=None, log=print):
    import ticket_cards,ticket_kit
    out={};fetch=fetch or pick_card.fetch_data_uri
    for row in stored(root):
        if not timedelta(0)<=now-boxscores.instant(row['capturedAt'])<=timedelta(days=8):
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
        card=ticket_cards.research_list_card(dict(row,rows=rows,stub='RESEARCH · NOT A BEST BET'))
        problems=ticket_kit.qa(card,row['key'])
        if problems:
            raise ValueError('; '.join(problems))
        path=Path(folder)/f"{row['key']}.png"
        pick_card.render(card.svg(),path);out[row['key']]=path
    return out
