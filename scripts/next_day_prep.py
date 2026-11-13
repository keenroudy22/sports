"""Private overnight coverage/watch packet; no future-clock admission or posting."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import math

import gates


def attach_team_context(packet, now, root, builder=None):
    """An unavailable NBA evidence reader must not erase ordinary preparation."""
    if builder is None:
        import nba_team_context
        builder = nba_team_context.from_stores
    try:
        context = builder(now, root=root, target_date=packet['targetDate'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        context = dict(state='unavailable', reason=type(error).__name__,
                       analysisOnly=True, admissionReady=False)
    packet['nba']['teamRoleContext'] = context
    return packet


def attach_opportunities(packet, now, root, builder=None):
    """Use stored point-in-time role/tracking data without a new request."""
    if builder is None:
        import nba_opportunities
        builder = nba_opportunities.from_stores
    try:
        context = builder(now, root=root, target_date=packet['targetDate'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        context = dict(state='unavailable', reason=type(error).__name__,
                       analysisOnly=True, admissionReady=False)
    packet['nba']['opportunityResearch'] = context
    return packet


def cbb_watch_rows(research, target, now):
    """Stage fresh priced comparisons without turning model gaps into picks."""
    rows=[]
    for game in (research or {}).get('games',[]):
        try:
            if gates.eastern_date(gates.when(game['kickoff'])) != target or gates.when(game['kickoff']) <= now:
                continue
            projection=game['projection']; quote=game['spreadQuote']
            margin=projection['margin']; home_line=quote['homeLine']
            if not all(type(value) in (int,float) and math.isfinite(value)
                       for value in (margin,home_line,quote['homeOdds'],quote['awayOdds'])):
                continue
            home=game['teams']['home']; away=game['teams']['away']
            # Positive model margin means home by N. The home book spread is
            # negative when favored, so margin + homeLine is the same-side gap.
            gap=round(margin+home_line,1)
            rows.append(dict(id=game['id'],kickoff=game['kickoff'],book=quote['book'],
                observedAt=quote['observedAt'],home=dict(name=home['name'],line=home_line,
                    odds=quote['homeOdds']),away=dict(name=away['name'],line=quote['awayLine'],
                    odds=quote['awayOdds']),kooknHomeMargin=margin,gapTowardHome=gap,
                holds=['Both team source packets and current availability review are still required',
                       'Exact live price and full sourced CBB admission must pass on game day'],
                planningOnly=True))
        except (KeyError,TypeError,ValueError):
            continue
    rows.sort(key=lambda row:(-abs(row['gapTowardHome']),row['kickoff'],row['id']))
    return rows[:5]


def prepare(games, lines, nba_slate, nba_props, now, *, target_date=None, sports=None,
            cbb_research=None):
    target=date.fromisoformat(target_date) if isinstance(target_date,str) else target_date
    if target is None:target=gates.eastern_date(now)+timedelta(days=1)
    if target < gates.eastern_date(now):raise ValueError("Preparation target is in the past")
    def tomorrow(at):
        try:return gates.when(at)>now and gates.eastern_date(gates.when(at))==target
        except (TypeError,ValueError):return False
    football={key:g for key,g in games.items() if g.get('league') in ('NFL','CFB')
              and g.get('state')=='pre' and tomorrow(g['kickoff'])}
    groups=defaultdict(list)
    counts=Counter()
    for row in lines:
        if row.get('gameId') not in football or row.get('state')!='open':continue
        if type(row.get('odds')) not in (int,float) or not math.isfinite(row['odds']):continue
        family='props' if row.get('athleteId') else 'sides' if row.get('market') in ('point spread','moneyline') else 'totals'
        counts[family]+=1
        grade=row.get('grade') or {}
        edge=grade.get('edge')
        if type(edge) not in (int,float) or not math.isfinite(edge):continue
        holds=['Fresh game-day quote, current news and full admission still required']
        if row.get('freshness')!='fresh':holds.append('Price needs refresh')
        groups[family].append({**{k:row.get(k) for k in
            ('id','gameId','title','league','book','odds','line','observedAt','kickoff','grade','gradeNote')},
            'holds':holds,'planningOnly':True})
    watches={}
    for family,rows in groups.items():
        rows.sort(key=lambda r:(-r['grade']['edge'],str(r['id'])))
        # Different market families get a turn; one repeated player/side cannot
        # occupy the entire prep list through alternate books or prices.
        chosen=[];seen=set()
        for row in rows:
            key=(row['gameId'],row['title'])
            if key in seen:continue
            seen.add(key);chosen.append(row)
            if len(chosen)==5:break
        watches[family]=chosen
    nba_games=[g for g in nba_slate.get('games',[]) if g.get('status')=='scheduled' and tomorrow(g.get('kickoff'))]
    nba_rows=[r for r in nba_props.get('rows',[]) if tomorrow(r.get('kickoff'))]
    sports=sports or {}
    cbb_block=(sports.get('leagues') or {}).get('CBB') or {}
    cbb_games=[g for g in cbb_block.get('games',[]) if g.get('status')=='scheduled' and tomorrow(g.get('kickoff'))]
    cbb_watch=cbb_watch_rows(cbb_research,target,now)
    return dict(asOf=gates.stamp(now),targetDate=target.isoformat(),planningOnly=True,releaseReady=False,
        morningChecksEastern=['06:45','08:30'],
        football=dict(games=len(football),pricedRowsByFamily=dict(counts),watchByFamily=watches),
        cbb=dict(games=len(cbb_games),checkedAt=cbb_block.get('checkedAt'),watch=cbb_watch,
                 hold=('Fresh exact two-sided DraftKings spreads/totals, both team source packets and '
                       'current availability review are required before a sourced CBB straight can release')),
        nba=dict(games=len(nba_games),freshPropRows=len(nba_rows),
                 watch=nba_rows[:12],availabilityAt=nba_props.get('availabilityAt'),
                 hold='NBA props remain research only; current role and forward validation required'),
        nextAction='Existing morning workers refresh quotes/news, evaluate the full board and release only admitted plays. This packet is not a selected card.')


if __name__=='__main__':
    import argparse
    import json
    from datetime import datetime,timezone
    from pathlib import Path
    import boxscores,build_site,cbb_today,line_payload,nba_player_props
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='work/next-day-prep.json')
    parser.add_argument('--target-date',type=date.fromisoformat)
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    ctx=gates.Stores().as_of(now)
    slate_path=nba_player_props.STORE/'slate.json'
    slate=json.loads(slate_path.read_text()) if slate_path.exists() else {}
    sports_path=build_site.OUT.parent/'sports.json'
    sports=json.loads(sports_path.read_text()) if sports_path.exists() else {}
    report=prepare(ctx.games,line_payload.load(build_site.OUT/'lines.json'),slate,
                   nba_player_props.build(now,limit=None),now,target_date=args.target_date,sports=sports,
                   cbb_research=cbb_today.build(now))
    attach_team_context(report, now, nba_player_props.STORE)
    attach_opportunities(report, now, nba_player_props.STORE)
    boxscores.write_json(Path(args.output),report)
    print(json.dumps(dict(path=args.output,targetDate=report['targetDate'],
        footballGames=report['football']['games'],footballPrices=report['football']['pricedRowsByFamily'],
        cbbGames=report['cbb']['games'],
        nbaGames=report['nba']['games'],nbaPropRows=report['nba']['freshPropRows'],releaseReady=False)))
