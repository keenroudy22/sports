"""Private next-day Climb shortlist from current captured evidence; never a release."""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import boxscores
import gates
import game_alternates
import ladder
import pricing


def prepare(ctx, now, day=None):
    day = day or gates.eastern_date(now)+timedelta(days=1)
    out=[]
    for game in sorted(ctx.games.values(),key=lambda g:(g['kickoff'],g['id'])):
        if game.get('league') not in ('NFL','CFB') or gates.eastern_date(gates.when(game['kickoff'])) != day:
            continue
        snap=ctx.snapshot(game['id'])
        quotes=[]
        for book,side,line,price,at,_ in game_alternates.quotes(ctx.prop_odds.get(game['id']) or {}):
            try:
                desk=pricing.price(snap,'spread',side,line,price) if snap else None
            except (KeyError,TypeError,ValueError):
                desk=None
            rate=ladder.segment_hit_rate(ctx,game['league'],'spread',ladder.BOOKS.get(book),price,side)
            holds=[]
            if not desk: holds.append('No usable current model snapshot')
            elif desk['rawChance'] < ladder.MANUAL_RAW_CHANCE: holds.append('Model support below Climb requirement')
            if rate is None: holds.append('Alternate-spread results have not established an open segment')
            try:
                if not timedelta(0) <= now-gates.when(at) <= ladder.GAME_FRESH: holds.append('Quote needs refresh')
            except (TypeError,ValueError): holds.append('Quote time missing')
            quotes.append(dict(team=game[side]['short'],line=line,odds=price,book=book,observedAt=at,
                projection=desk['projection'] if desk else None,holds=holds))
        supported=ladder.alternate_spread_legs(game,ctx,now)
        props=ladder.legs_for_game(game,ctx.prop_odds.get(game['id']),ctx,now,ladder.confirmed_at(),proven=True)
        out.append(dict(gameId=game['id'],matchup=f"{game['away']['name']} at {game['home']['name']}",
            kickoff=game['kickoff'],alternateSpreads=quotes,supportedSpreadLegs=len(supported),
            supportedPropLegs=len(props),coverageHold=None if quotes else 'No complete current two-sided alternate spread ladder captured'))
    return dict(asOf=gates.stamp(now),targetDate=day.isoformat(),planningOnly=True,games=out,
                nextAction='Refresh prices, news and models at existing game-day morning checks; release only through normal admission and delivery.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='work/climb-prep.json')
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    report=prepare(gates.Stores().as_of(now),now)
    boxscores.write_json(Path(args.output),report)
    print(json.dumps(dict(path=args.output,targetDate=report['targetDate'],games=len(report['games']),
        alternateSpreads=sum(len(g['alternateSpreads']) for g in report['games']),
        supported=sum(g['supportedSpreadLegs']+g['supportedPropLegs'] for g in report['games']))))
