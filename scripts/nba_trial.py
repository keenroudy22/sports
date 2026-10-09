"""NBA Trial admission policy and separate append-only record, disabled pending first-card review.

This module makes no feed or social call. Football's publication and record paths
never read this ledger. Opening-night posting integration remains a separate gate.
"""
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import boxscores
import espn_props
import nba_capture

STORE=Path(__file__).resolve().parents[1]/'data'/'nba-trial'
OPENING=date(2026,10,20)
EASTERN=ZoneInfo('America/New_York')


def snapshot(rows):
    published={r['id']:r for r in rows if r.get('type')=='publish'}
    settled={r['id']:r for r in rows if r.get('type')=='settle' and r.get('source') and r.get('result') in ('win','loss','push','void')}
    wins=losses=pushes=0;net=0
    for key,play in published.items():
        final=settled.get(key)
        if not final:continue
        result=final['result']
        wins+=result=='win';losses+=result=='loss';pushes+=result=='push'
        odds=play['odds']
        net += (100/-odds if odds<0 else odds/100) if result=='win' else -1 if result=='loss' else 0
    net=round(net,6)
    graded=wins+losses+pushes
    return {'label':'NBA Trial','win':wins,'loss':losses,'push':pushes,'graded':graded,
            'units':round(net,3),'paused':graded>=30 and net<=-5,
            'promotionReview':graded>=30 and net>=0}


def evaluate(offer, rows, now=None, preview_sent=None, calibration_verified=False):
    now=now or datetime.now(timezone.utc);problems=[]
    try:
        kickoff=boxscores.instant(offer['kickoff']);quoted=boxscores.instant(offer['retrievedAt'])
        game_day=kickoff.astimezone(EASTERN).date()
        if now.astimezone(EASTERN).date()<OPENING or game_day<OPENING:problems.append('opening-night hold')
        if game_day!=now.astimezone(EASTERN).date() or kickoff<=now:problems.append('game-day hold')
        if not timedelta(0)<=now-quoted<=timedelta(hours=4) or quoted>=kickoff:problems.append('price freshness hold')
        if offer.get('league')!='NBA' or offer.get('seasonType') not in (2,'regular-season'):problems.append('NBA regular-season only')
        if offer.get('marketType') not in ('total','prop') or offer.get('book') not in ('DraftKings','FanDuel'):problems.append('market/book hold')
        line=espn_props.number(offer['line'])
        if line<=0 or not offer.get('source'):problems.append('line/source hold')
        odds=espn_props.price(offer['odds']);opposite=espn_props.price(offer['oppositeOdds'])
        if not .99<=espn_props.implied(odds)+espn_props.implied(opposite)<=1.15:problems.append('price-pair hold')
        if offer.get('sideVerified') is not True or offer.get('exactLineVerified') is not True:problems.append('exact-side hold')
        if offer.get('roleChecked') is not True or offer.get('roleHold') or offer.get('priceHold') or offer.get('injuryHold'):problems.append('role/price hold')
        if isinstance(offer.get('riskUnits'),bool) or offer.get('riskUnits')!=1:problems.append('1u only')
        calibrated=calibration_verified and offer.get('calibrated') is True
        chance=offer['chance'] if calibrated else offer['rawChance']
        if isinstance(chance,bool) or not isinstance(chance,(float,int)) or not math.isfinite(chance) or not 0<=chance<=1:
            raise ValueError('missing probability')
        if chance-espn_props.implied(odds) < (.04 if calibrated else .06)-1e-9:problems.append('edge hold')
        if not calibrated and chance<.56:problems.append('chance hold')
        for row in rows:
            if row.get('type')=='publish' and row.get('id')==offer.get('id'):problems.append('published ID is immutable')
            if row.get('type')=='publish' and boxscores.instant(row['kickoff']).astimezone(EASTERN).date()==game_day:
                problems.append('one play per day');break
        if snapshot(rows)['paused']:problems.append('30-graded loss pause')
        if not preview_sent or now-boxscores.instant(preview_sent)<timedelta(hours=2):problems.append('first-card veto hold')
        if offer.get('ownerVeto'):problems.append('owner veto')
    except (KeyError,ValueError,TypeError,OverflowError):problems.append('missing verified evidence')
    return sorted(set(problems))


def record_publish(offer,now,root=STORE,preview_sent=None,calibration_verified=False):
    rows=[r for p in root.glob('*.jsonl') for r in boxscores.read_store(p)]
    problems=evaluate(offer,rows,now,preview_sent,calibration_verified)
    if problems:raise ValueError('; '.join(problems))
    required=('id','league','season','seasonType','kickoff','marketType','line','odds','oppositeOdds','book',
              'retrievedAt','rawChance','riskUnits','source')
    row={key:offer[key] for key in required}
    row.update(type='publish',series='NBA Trial',publishedAt=boxscores.stamp(now))
    return nba_capture.append_changed([row],root,lambda r:(r['type'],r['id']))


def preview_svg(game, quote):
    """Real stored total quote, clearly labeled layout preview; no admission or invented chance."""
    import ticket_cards
    import ticket_kit
    home,away=game['teams']['home'],game['teams']['away']
    total=quote['current']['total']
    over,under=espn_props.price(total['over']),espn_props.price(total['under'])
    if not .99<=espn_props.implied(over)+espn_props.implied(under)<=1.15:
        raise ValueError('Preview needs two genuine matching prices')
    data={'kind':'game','featured':False,'seriesLabel':'NBA TRIAL PREVIEW',
          'away':away['abbreviation'],'home':home['abbreviation'],'team':home['abbreviation'],
          'away_name':away['name'],'home_name':home['name'],'away_logo':None,'home_logo':None,
          'when':'Opening night · Oct 20','when_caps':'OPENING NIGHT · OCT 20',
          'market':'total','line':f"{total['line']:g}",'odds':under,'book':quote['book'],
          'chance':None,'needs':None,'calibrated':False,
          'reason':'Layout preview only. No play posted. Price seen '+quote['retrievedAt'][:10]+'.',
          'units':1.,'photo':None,'team_logo':None,
          'team_colors':{home['abbreviation']:('#17241f','#eef4ec'),away['abbreviation']:('#17241f','#eef4ec')},
          'side':'UNDER'}
    card=ticket_cards.play_card(data)
    problems=ticket_kit.qa(card,'NBA Trial preview')
    if problems:raise ValueError('; '.join(problems))
    return card.svg()
