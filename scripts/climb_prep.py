"""Private next-day Climb shortlist from current captured evidence; never a release."""
import argparse
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import boxscores
import gates
import game_alternates
import ladder
import pricing
import parlay
from itertools import combinations


def two_leg_options(legs, now, supported=False, limit=8):
    """Bounded private shortlist. Derived cross-game odds are not a book receipt.

    Never join same-game legs or mix books/leagues. Watch-list model support is
    not established performance, admission or permission to publish.
    """
    grouped={}
    for leg in legs:
        if (leg.get('alternate') is not True or leg.get('book') not in ladder.SLUGS
                or not ladder.LEG_PRICES[0] <= leg['odds'] <= ladder.LEG_PRICES[1]):
            continue
        grouped.setdefault((leg['league'],leg['book'],leg['gameId']),[]).append(leg)
    pool=[]
    for rows in grouped.values():
        rows.sort(key=lambda r:(len(r.get('holds',[])),-r.get('rawChance',0),r['title'],r['odds']))
        pool.extend(rows[:4])
    options=[]
    for a,b in combinations(pool,2):
        if a['gameId']==b['gameId'] or a['book']!=b['book'] or a['league']!=b['league']:
            continue
        price=parlay.american(parlay.decimal(a['odds'])*parlay.decimal(b['odds']))
        if not ladder.TARGET[0] <= price <= ladder.TARGET[1]:continue
        if supported and a['chance']*b['chance'] <= pricing.break_even(price):continue
        holds=sorted(set(a.get('holds',[])+b.get('holds',[])))
        options.append(dict(book=a['book'],league=a['league'],derivedOdds=price,
            priceBasis='Product of separate cross-game prices; final ticket price needs confirmation',
            status='supported-watch' if supported else 'evidence-held-watch',planningOnly=True,
            legs=[a,b],holds=holds,
            releaseChecks=['Fresh game-day prices and news','Exact ticket price',
                           'Normal admission, exposure and one-open-step checks']))
    options.sort(key=lambda r:(len(r['holds']),abs(r['derivedOdds']+175),
                               r['book'],tuple(l['title'] for l in r['legs'])))
    return options[:limit]


def prepare(ctx, now, day=None):
    day = day or gates.eastern_date(now)+timedelta(days=1)
    out=[];supported_legs=[];watch_legs=[]
    confirmed=ladder.confirmed_at()
    for game in sorted(ctx.games.values(),key=lambda g:(g['kickoff'],g['id'])):
        if game.get('state') != 'pre' or gates.when(game['kickoff']) <= now:
            continue
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
            if not ladder.LEG_PRICES[0] <= price <= ladder.LEG_PRICES[1]:holds.append('Outside individual Climb price band')
            if desk and rate is not None and min(desk['rawChance'],rate)<=desk['breakEven']:
                holds.append('Supported chance does not cover price')
            row=dict(team=game[side]['short'],line=line,odds=price,book=book,observedAt=at,
                projection=desk['projection'] if desk else None,holds=holds)
            quotes.append(row)
            if desk and desk['rawChance']>=ladder.MANUAL_RAW_CHANCE:
                watch_legs.append(dict(row,book=ladder.BOOKS.get(book),gameId=game['id'],league=game['league'],
                    kickoff=game['kickoff'],title=f"{game[side]['short']} {pricing.signed(line)}",
                    alternate=True,rawChance=desk['rawChance']))
        supported=ladder.alternate_spread_legs(game,ctx,now)
        props=ladder.legs_for_game(game,ctx.prop_odds.get(game['id']),ctx,now,confirmed,proven=True)
        raw_props=ladder.legs_for_game(game,ctx.prop_odds.get(game['id']),ctx,now,confirmed,proven=False)
        for leg in raw_props:
            if leg.get('alternate') is not True:continue
            rate=ladder.segment_hit_rate(ctx,game['league'],leg['market'],leg['book'],leg['odds'],leg['direction'])
            holds=[]
            if rate is None:holds.append('Alternate-prop results have not established an open segment')
            elif min(leg['rawChance'],rate)<=leg['implied']:holds.append('Supported chance does not cover price')
            if not ladder.strict_legs([leg],getattr(ctx,'policy',{}),now,game['league']):
                holds.append('Learned direction safety flag remains active')
            watch_legs.append(dict(leg,league=game['league'],holds=holds))
        eligible=ladder.strict_legs(supported+props,getattr(ctx,'policy',{}),now,game['league'])
        supported_legs.extend(dict(leg,league=game['league']) for leg in eligible)
        out.append(dict(gameId=game['id'],matchup=f"{game['away']['name']} at {game['home']['name']}",
            kickoff=game['kickoff'],alternateSpreads=quotes,supportedSpreadLegs=len(supported),
            supportedPropLegs=len(props),roleEligiblePropWatch=len(raw_props),
            coverageHold=None if quotes else 'No complete current two-sided alternate spread ladder captured'))
    supported_options=two_leg_options(supported_legs,now,supported=True)
    return dict(asOf=gates.stamp(now),targetDate=day.isoformat(),planningOnly=True,games=out,
                twoLegOptions=supported_options,
                evidenceHeldOptions=two_leg_options(watch_legs,now) if not supported_options else [],
                releaseReady=False,
                nextAction='Refresh prices, news and models at existing game-day morning checks; release only through normal admission and delivery.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='work/climb-prep.json')
    parser.add_argument('--target-date',type=date.fromisoformat)
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    report=prepare(gates.Stores().as_of(now),now,day=args.target_date)
    boxscores.write_json(Path(args.output),report)
    print(json.dumps(dict(path=args.output,targetDate=report['targetDate'],games=len(report['games']),
        alternateSpreads=sum(len(g['alternateSpreads']) for g in report['games']),
        supported=sum(g['supportedSpreadLegs']+g['supportedPropLegs'] for g in report['games']))))
