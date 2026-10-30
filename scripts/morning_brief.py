"""One sourced morning research decision; no feed calls or official admission."""
import json
import re
import math
from datetime import timedelta
from pathlib import Path
import boxscores,gates,x_post
from sports_refresh import eastern_date
ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/'data/morning-brief'

def fresh(value,now):
    try:return timedelta(0)<=now-boxscores.instant(value)<=timedelta(hours=4)
    except (ValueError,TypeError):return False

def normal(value):return re.sub(r'[^a-z0-9]','',str(value).lower())

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def same_line(row, screen):
    if screen.get('gameId') != row.get('gameId'):
        return False
    if screen.get('lineId'):
        return (screen['lineId'] == row.get('id') and screen.get('line') == row.get('line')
                and screen.get('book') == row.get('book'))
    # Legacy captured screens have no catalog identity; never fuzzy-match teams.
    return normal(screen.get('title')) == normal(row.get('title'))

def has_official_straight(admitted):
    return any(not pick.get('parlayType') and not pick.get('legs') for _,_,pick in admitted)

def choose(now,lines,screened,nba,official=False):
    import coverage_priority
    if official:return None
    options=[];day=eastern_date(now)
    for row in lines:
        if not isinstance(row,dict):continue
        grade=row.get('grade') or {};projection=grade.get('projection')
        if (not fresh(row.get('observedAt'),now) or not number(projection)
            or not isinstance(row.get('odds'),int) or not grade.get('calibrated')
            or any(grade.get(k) for k in ('thin','limited','unproven')) or (grade.get('edge') or 0)<=0):continue
        try:
            kickoff=boxscores.instant(row['kickoff'])
            if eastern_date(kickoff)!=day or kickoff<=now+timedelta(minutes=45):continue
        except (KeyError,TypeError,ValueError):continue
        hold=next((s for s in screened if same_line(row,s)),None)
        if not hold:continue
        reason=hold.get('reason') or ''
        if any(word in reason.lower() for word in ('ruled out','injured reserve','inactive','suspended')):continue
        missing=('Player/QB availability still needs verification.' if hold.get('rule')=='held'
                 else 'The daily total-play limit is already filled.' if hold.get('rule')=='totals_policy' else reason[:120])
        if missing:options.append((float(grade['edge']),dict(league=row['league'],title=row['title'],line=row['line'],
            odds=row['odds'],book=row['book'],projection=projection,observedAt=row['observedAt'],kickoff=row['kickoff'],missing=missing)))
    primary = [item for item in options if coverage_priority.tier(
        item[1]['league'], item[1]['kickoff'], now) == 0]
    if primary:return max(primary,key=lambda x:x[0])[1]
    if any(not p.get('result') for p in (nba.get('trial') or {}).get('plays',[])):return None
    for row in (nba.get('playerProps') or {}).get('rows',[]):
        review=row.get('roleReview') or {};p=row.get('projection') or {}
        if (row.get('hold') or not row.get('favorite') or not review or review.get('hold') or not p
            or not fresh(review.get('checkedAt'),now) or not fresh(row.get('sourceAt'),now)
            or not fresh((nba.get('playerProps') or {}).get('availabilityAt'),now)):continue
        if not all(number(row.get(k)) for k in ('line','odds')) or not all(number(p.get(k)) for k in ('value','minutes')):continue
        try:kickoff=boxscores.instant(row['kickoff'])
        except (KeyError,TypeError,ValueError):continue
        if eastern_date(kickoff)!=day or kickoff<=now+timedelta(minutes=45):continue
        return dict(league='NBA',title=f"{row['name']} {row['side']} {row['line']:g} {row['statName']}",line=row['line'],
            odds=row['odds'],book=row['book'],projection=p['value'],observedAt=row['sourceAt'],kickoff=row['kickoff'],
            minutes=p['minutes'],missing='NBA prop forecasts still need testing against actual results.')
    return max(options,key=lambda x:x[0])[1] if options else None

def text(row):
    return (f"Morning lean · not a Best Bet\n{row['title']} ({row['odds']:+d}, {row['book']})\n"
            f"Missing: {row['missing']}\n#{row['league']}")

def prepare(now,screened,official=False,root=STORE):
    local=now.astimezone(gates.EASTERN)
    if not (6,45)<=(local.hour,local.minute)<(12,0):return False
    import line_payload,nba_today
    row=choose(now,line_payload.load(ROOT/'site/data/app/lines.json',strict=False),screened,nba_today.build(now),official)
    if not row:return False
    caption=text(row)
    if x_post.tweet_length(caption)>x_post.LIMIT or x_post.x_style(caption):return False
    snapshot=dict(row,day=eastern_date(now).isoformat(),text=caption,capturedAt=boxscores.stamp(now))
    path=Path(root)/f"{snapshot['day']}-{now.strftime('%H%M%S%f')}.json";path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('x') as f:json.dump(snapshot,f,ensure_ascii=False,indent=2);f.write('\n')
    except FileExistsError:return False
    return True

def current(now,root=STORE):
    for path in sorted(Path(root).glob(f'{eastern_date(now)}*.json'),reverse=True):
        try:
            row=json.loads(path.read_text())
            if not isinstance(row,dict) or not fresh(row.get('observedAt'),now):continue
            if boxscores.instant(row['kickoff'])<=now+timedelta(minutes=45):continue
            if not all(row.get(k) for k in ('text','capturedAt','day','league')):continue
            return row
        except (OSError,ValueError,TypeError,KeyError):continue
    return None

def post(now,root=STORE):
    row=current(now,root)
    if not row:return None
    return dict(key=f"research:morning:{row['day']}",kind='research',text=row['text'],due=boxscores.instant(row['capturedAt']),
        stale=min(boxscores.instant(row['observedAt'])+timedelta(hours=4),boxscores.instant(row['kickoff'])-timedelta(minutes=45)),card=None)
