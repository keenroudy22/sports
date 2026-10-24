"""Private overnight coverage/watch packet; no future-clock admission or posting."""
from collections import Counter, defaultdict
from datetime import timedelta
import math

import gates


def prepare(games, lines, nba_slate, nba_props, now):
    target=gates.eastern_date(now)+timedelta(days=1)
    def tomorrow(at):
        try:return gates.eastern_date(gates.when(at))==target
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
    return dict(asOf=gates.stamp(now),targetDate=target.isoformat(),planningOnly=True,releaseReady=False,
        morningChecksEastern=['06:45','08:30'],
        football=dict(games=len(football),pricedRowsByFamily=dict(counts),watchByFamily=watches),
        nba=dict(games=len(nba_games),freshPropRows=len(nba_rows),
                 watch=nba_rows[:12],availabilityAt=nba_props.get('availabilityAt'),
                 hold='NBA props remain research only; current role and forward validation required'),
        nextAction='Existing morning workers refresh quotes/news, evaluate the full board and release only admitted plays. This packet is not a selected card.')


if __name__=='__main__':
    import argparse
    import json
    from datetime import datetime,timezone
    from pathlib import Path
    import boxscores,build_site,line_payload,nba_player_props
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='work/next-day-prep.json')
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    ctx=gates.Stores().as_of(now)
    slate_path=nba_player_props.STORE/'slate.json'
    slate=json.loads(slate_path.read_text()) if slate_path.exists() else {}
    report=prepare(ctx.games,line_payload.load(build_site.OUT/'lines.json'),slate,
                   nba_player_props.build(now,limit=None),now)
    boxscores.write_json(Path(args.output),report)
    print(json.dumps(dict(path=args.output,targetDate=report['targetDate'],
        footballGames=report['football']['games'],footballPrices=report['football']['pricedRowsByFamily'],
        nbaGames=report['nba']['games'],nbaPropRows=report['nba']['freshPropRows'],releaseReady=False)))
