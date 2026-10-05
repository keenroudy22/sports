"""One factual multi-sport evening slate. No picks, odds, inferred injuries or model calls.

The Mac freezes one sourced card per Eastern date. Builds retain eight days of
art for queued posts and Discord retries. A late or stale slate is skipped.
"""
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import gates
import pick_card
import sports_refresh

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data/sports-social'
DATA = ROOT / 'site/data/sports.json'


def choose(data, now):
    day = sports_refresh.eastern_date(now)
    due = datetime(day.year,day.month,day.day,17,50,tzinfo=gates.EASTERN).astimezone(timezone.utc)
    if not due-timedelta(hours=2) <= now <= due+timedelta(minutes=10):
        return None
    games = []
    for league, block in data.get('leagues',{}).items():
        if league not in sports_refresh.LEAGUES or block.get('status') != 'ok':
            continue
        for g in block.get('games',[]):
            try:
                seen = gates.when(g.get('updatedAt') or block.get('updatedAt') or data.get('updatedAt'))
                kickoff = gates.when(g['kickoff'])
                if not timedelta(0) <= now-seen <= timedelta(hours=4): continue
                if g.get('timeConfirmed') is not True or g['status'] != 'scheduled' or not max(now,due)+timedelta(minutes=45) < kickoff <= due+timedelta(hours=12): continue
                if not all(g['teams'][s].get('abbreviation') for s in ('away','home')): continue
                games.append(dict(g,league=league))
            except (ValueError,TypeError,KeyError):
                continue
    games.sort(key=lambda g:(g['kickoff'],g['id']))
    # A little breadth first; never call arbitrary calendar choices model favorites.
    rows, leagues = [], set()
    for g in games:
        if g['league'] not in leagues:
            rows.append(g);leagues.add(g['league'])
    rows=(rows+[g for g in games if g not in rows])[:4]
    rows.sort(key=lambda g:g['kickoff'])
    if not rows: return None
    key='sports-slate-'+day.isoformat()
    text=['Tonight around the leagues 👀']
    for g in rows:
        kickoff=gates.when(g['kickoff']).astimezone(gates.EASTERN)
        text.append(f"{g['league']}: {g['teams']['away']['abbreviation']} at {g['teams']['home']['abbreviation']} · {kickoff.strftime('%-I:%M %p')} ET")
    text+=['','What are you watching?','Scores: keenroudy.com/sports/#scores']
    import x_post
    if x_post.tweet_length('\n'.join(text)) > x_post.LIMIT: return None
    return {'key':key,'capturedAt':gates.stamp(now),'due':gates.stamp(due),
            'stale':gates.stamp(min(due+timedelta(minutes=25), gates.when(rows[0]['kickoff'])-timedelta(minutes=30))),
            'rows':rows,'text':'\n'.join(text)}


def prepare(now, data_path=DATA, root=STORE):
    if os.environ.get('KEENROUDY_SPORTS_SOCIAL', '0') != '1': return False
    try: data=json.loads(Path(data_path).read_text())
    except (OSError,ValueError): return False
    choice=choose(data,now)
    if not choice: return False
    path=Path(root)/f"{choice['key']}.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('x') as f: json.dump(choice,f,indent=2);f.write('\n')
    except FileExistsError: return False
    return True


def post(now, root=STORE):
    if os.environ.get('KEENROUDY_SPORTS_SOCIAL', '0') != '1': return None
    path=Path(root)/f'sports-slate-{sports_refresh.eastern_date(now)}.json'
    try: row=json.loads(path.read_text())
    except (OSError,ValueError): return None
    if gates.when(row['stale']) <= now: return None
    return {'key':row['key'],'kind':'sports','text':row['text'],'due':gates.when(row['due']),
            'stale':gates.when(row['stale']),'card':row['key']}


def svg(row, art=None):
    art=art or {};blocks=[]
    for i,g in enumerate(row['rows']):
        y=270+i*225
        names=f"{g['teams']['away']['abbreviation']}  @  {g['teams']['home']['abbreviation']}"
        time=gates.when(g['kickoff']).astimezone(gates.EASTERN).strftime('%-I:%M %p ET')
        images=''.join(f'<image href="{art[(i,s)]}" x="{815+j*85}" y="{y+76}" width="75" height="75"/>' for j,s in enumerate(('away','home')) if (i,s) in art)
        blocks.append(f'<rect x="44" y="{y}" width="992" height="202" rx="22" fill="#102330" stroke="#294657"/>'
                      f'<text x="78" y="{y+45}" fill="#6adfff" font-size="26">{html.escape(g["league"])}</text>'
                      f'<text x="78" y="{y+112}" fill="#f5faff" font-size="48" font-weight="800">{html.escape(names)}</text>'
                      f'<text x="78" y="{y+162}" fill="#5eeaa4" font-size="32">{time}</text>{images}')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" font-family="Arial,sans-serif"><rect width="1080" height="1350" fill="#071018"/><rect width="1080" height="8" fill="#5eeaa4"/><text x="44" y="82" fill="#5eeaa4" font-size="32" font-weight="800">KOOK’N</text><text x="44" y="164" fill="#f5faff" font-size="64" font-weight="900">TONIGHT’S WATCHLIST</text><text x="44" y="218" fill="#a7c1cf" font-size="28">{html.escape(row["key"].removeprefix("sports-slate-"))} · Schedules, not picks</text>{"".join(blocks)}<text x="44" y="1240" fill="#f5faff" font-size="38" font-weight="800">WHAT ARE YOU WATCHING?</text><text x="44" y="1300" fill="#5eeaa4" font-size="28">keenroudy.com/sports · Scores &amp; schedules</text></svg>'


def render_due(now, folder, root=STORE, fetch=None, log=print):
    out={}; fetch=fetch or pick_card.fetch_data_uri
    for path in sorted(Path(root).glob('sports-slate-*.json')):
        row=json.loads(path.read_text())
        age=now-gates.when(row['capturedAt'])
        if not timedelta(0)<=age<=timedelta(days=8): continue
        target=Path(folder)/f"{row['key']}.png"
        art={}
        for i,g in enumerate(row['rows']):
            for side in ('away','home'):
                logo=g['teams'][side].get('logo')
                if logo and str(logo).startswith('https://a.espncdn.com/'):
                    try:
                        uri=fetch(logo)
                        if uri: art[i,side]=uri
                    except Exception: pass
        try: pick_card.render(svg(row,art),target,size=(1080,1350));out[row['key']]=target
        except Exception as e: log(f'sports slate card unavailable: {type(e).__name__}')
    return out
