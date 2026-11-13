"""Read-only men's college research from existing schedules, finals and paper quotes."""
import json
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo
import boxscores
import hoops_store
import paper
from sports_refresh import timestamp

ROOT = Path(__file__).resolve().parents[1]


def build(now=None, root=ROOT, records=None, model_factory=None):
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    try:
        slate = json.loads((root/'site/data/sports.json').read_text())['leagues']['CBB']
    except (OSError, ValueError, KeyError):
        slate = {}
    records = records if records is not None else hoops_store.load('CBB')
    records = [r for r in records if boxscores.instant(r['kickoff']) < now
               and r.get('retrievedAt') and boxscores.instant(r['retrievedAt']) <= now]
    stats = defaultdict(lambda: dict(games=0, wins=0, losses=0, points=0, allowed=0))
    for r in records:
        if r.get('type') != 2:
            continue
        for side, other in (('home','away'),('away','home')):
            s = stats[(r['season'],r[side]['id'])]
            pf, pa = r[side+'Score'], r[other+'Score']
            s['games'] += 1; s['wins'] += pf > pa; s['losses'] += pf < pa
            s['points'] += pf; s['allowed'] += pa
    quotes = {}
    for p in (root/'data/paper').glob('cbb-*.jsonl'):
        for q in boxscores.read_store(p):
            if q.get('type') == 'record' and q.get('capturedAt') and boxscores.instant(q['capturedAt']) <= now:
                quotes.setdefault(q['gameId'],q)
    def summary(season, team):
        s = stats[(season,team)]
        return dict(season=season, games=s['games'], wins=s['wins'], losses=s['losses'],
                    ppg=round(s['points']/s['games'],1) if s['games'] else None,
                    allowed=round(s['allowed']/s['games'],1) if s['games'] else None)
    checked = slate.get('checkedAt')
    fresh = bool(checked and timedelta(0) <= now-boxscores.instant(checked) <= timedelta(hours=24)
                 and slate.get('status') == 'ok')
    games=[]; models={}
    for g in slate.get('games',[]):
        if g.get('status') != 'scheduled' or boxscores.instant(g['kickoff']) <= now:
            continue
        row = {k:g[k] for k in ('id','kickoff','teams','season','date','source') if k in g}
        season=g['season']; row['stats']={side:dict(current=summary(season,g['teams'][side]['id']),
            prior=summary(season-1,g['teams'][side]['id'])) for side in ('home','away')}
        row['hold']=None
        if not fresh:row['hold']='Schedule update needed'
        elif type(g.get('neutral')) is not bool:row['hold']='Venue verification needed'
        elif not g.get('timeConfirmed', True):row['hold']='Tip time not confirmed'
        else:
            try:
                if season not in models:
                    models[season]=(model_factory or paper.model_for)('CBB',season,now.timestamp(),records=records)
                m=models[season]; home=g['teams']['home']['id']; away=g['teams']['away']['id']
                if m.key(home)=='~small' or m.key(away)=='~small':
                    row['hold']='Insufficient team history for a matchup projection'
                else:
                    p=m.predict(home,away,g['neutral'])
                    if not all(type(p.get(k)) in (float,int) and math.isfinite(p[k]) for k in ('margin','total')):
                        raise ValueError('Missing score')
                    row['projection']=dict(home=round((p['total']+p['margin'])/2,1),
                        away=round((p['total']-p['margin'])/2,1),total=round(p['total'],1),
                        margin=round(p['margin'],1),sparse=p.get('sparse',True),neutral=g['neutral'])
                    # Display the existing score model's own win probability;
                    # never invent one from the rounded score or missing variance.
                    chance=p.get('homeWinProb')
                    if type(chance) in (float,int) and math.isfinite(chance) and 0 <= chance <= 1:
                        row['projection']['winProb']=round(chance,6)
            except (ValueError,KeyError,TypeError,ArithmeticError):row['hold']='Projection unavailable'
        spread = g.get('spreadQuote')
        if fresh and g.get('timeConfirmed', True) and isinstance(spread, dict):
            try:
                observed = timestamp(spread['observedAt'])
                if timedelta(0) <= now - observed <= timedelta(hours=4):
                    row['spreadQuote'] = {key: spread[key] for key in
                                          ('book', 'observedAt', 'homeLine', 'awayLine', 'homeOdds', 'awayOdds')}
            except (AttributeError, KeyError, ValueError):
                pass
        q=quotes.get(g['id'])
        if q and boxscores.instant(q['capturedAt']) < boxscores.instant(g['kickoff']):
            row['firstTotal']=dict(line=q['line'],book=q['book'],capturedAt=q['capturedAt'])
        games.append(row)
    games.sort(key=lambda g:(g['kickoff'],g['id']))
    return dict(generatedAt=boxscores.stamp(now),checkedAt=checked,scheduleFresh=fresh,games=games,
                note="Team-rating research, not picks. Early-season scores rely on prior-season ratings; no current roster, injury or transfer adjustment. Stats are regular-season finals received before this update. DraftKings spreads are time-stamped scoreboard quotes. First recorded totals are historical.")


def sheet(rows, day, page, pages, as_of=""):
    """Readable research-only export. Integer scores for social reuse, no picks/EV."""
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">',
         '<rect width="1080" height="1350" fill="#071219"/>',
         '<path d="M0 5H1080" stroke="#56e4ad" stroke-width="10"/>',
         '<g fill="#f4f7fa" font-family="Arial,sans-serif">',
         '<text x="42" y="62" fill="#56e4ad" font-size="25" font-weight="bold">KOOK’N · RESEARCH</text>',
         '<text x="42" y="126" font-size="49" font-weight="bold">CBB PROJECTIONS</text>',
         f'<text x="42" y="169" font-size="24">{escape(day)} · Page {page} of {pages} · Bars: model win chance (away / home)</text>']
    for i,g in enumerate(rows):
        y=204+i*81; p=g['projection']; a=g['teams']['away'];h=g['teams']['home']
        chance=p.get('winProb')
        bar=''
        if type(chance) in (int,float) and math.isfinite(chance) and 0 <= chance <= 1:
            hp=math.floor(100*chance+.5);ap=100-hp;aw=300*(1-chance)
            bar=(f'<text x="476" y="{y+59}" text-anchor="end" fill="#f4f7fa" font-size="18">{ap}%</text>'
                 f'<rect x="490" y="{y+44}" width="300" height="14" rx="7" fill="#56e4ad"/>'
                 f'<rect x="490" y="{y+44}" width="{aw:.2f}" height="14" fill="#69b6ee"/>'
                 f'<text x="804" y="{y+59}" fill="#f4f7fa" font-size="18">{hp}%</text>')
        out += [f'<rect x="36" y="{y}" width="1008" height="72" rx="10" fill="#10222c"/>',bar,
                f'<text x="52" y="{y+29}" font-size="22">{escape(a.get("abbreviation") or a["shortName"])} at {escape(h.get("abbreviation") or h["shortName"])}</text>',
                f'<text x="52" y="{y+57}" fill="#a9bcb7" font-size="18">{escape(boxscores.instant(g["kickoff"]).astimezone(ZoneInfo("America/New_York")).strftime("%I:%M %p ET"))} · {"Neutral court" if p["neutral"] else "Home court included"}</text>',
                f'<text x="1018" y="{y+34}" text-anchor="end" font-size="30" font-weight="bold">{round(p["away"])} – {round(p["home"])}</text>',
                f'<text x="1018" y="{y+59}" text-anchor="end" fill="#56e4ad" font-size="19">Total {round(p["away"])+round(p["home"])}</text>']
    out += [f'<text x="42" y="1202" fill="#a9bcb7" font-size="18">Generated {escape(as_of)} · UTC</text>', '<text x="42" y="1238" font-size="22">Baseline team ratings · not injury/roster adjusted</text>',
            '<text x="42" y="1276" font-size="22">Research, not picks · Scores rounded · 21+ only</text>',
            '<text x="42" y="1314" fill="#56e4ad" font-size="22">keenroudy.com/sports/#today?sport=CBB</text></g></svg>']
    return ''.join(out)


def exports(data):
    groups=defaultdict(list)
    for g in data['games']:
        if g.get('projection'):groups[g['date']].append(g)
    out={};links=[]
    for day,rows in sorted(groups.items()):
        pages=(len(rows)+11)//12
        for i in range(pages):
            name=f'cbb-sheet-{day}-{i+1}.svg'
            out[name]=sheet(rows[i*12:(i+1)*12],day,i+1,pages,data.get("generatedAt", ""))
            links.append(dict(file=name,date=day,page=i+1,pages=pages,games=len(rows[i*12:(i+1)*12])))
    return out,links
