"""DraftKings Indiana primary NBA full-game prop settlement, not admission.

Rules checked in the operator's Indiana browser October28. Individual pregame
points/rebounds/assists only; quarters, combined players and paid protection
remain unsupported. Missing facts hold, never imply an injury void.
"""
from datetime import datetime,timedelta,timezone
from urllib.parse import urlparse,parse_qs
import math
import boxscores

VERSION='dk-in-nba-primary-2026-10-28'
VERIFIED_AT=datetime(2026,10,28,14,30,tzinfo=timezone.utc)
SPORT_RULES='https://sportsbook.draftkings.com/help/sport-rules/basketball'
GENERAL_RULES='https://sportsbook.draftkings.com/help/general-betting-rules'


def numeric(x):
    return type(x) in (int,float) and math.isfinite(x)


def evaluate(play,final,now,injury_review=None):
    """Return a typed grading decision; official public ledgers are untouched."""
    def decision(state,reason,actual=None,result=None):
        return dict(state=state,reason=reason,actual=actual,result=result,policy=VERSION,
            rulesSource=SPORT_RULES,scope='Book-rule research decision, not a public settlement')
    try:
        if (str(play.get('book','')).replace(' ','').lower()!='draftkings'
            or play.get('league')!='NBA' or play.get('stat') not in ('pts','reb','ast')
            or play.get('period','full_game')!='full_game' or play.get('direction',play.get('side')) not in ('over','under')
            or play.get('paidProtection') or play.get('allAction')):
            return decision('held','Unsupported market/book/protection terms')
        quoted=boxscores.instant(play['retrievedAt']);kick=boxscores.instant(play['kickoff'])
        if not VERIFIED_AT<=quoted<kick<=now:return decision('held','No applicable pregame rule snapshot')
        if (final.get('league')!='NBA' or final.get('seasonType')!=2
            or str(final['eventId']).removeprefix('NBA-')!=str(play['eventId']).removeprefix('NBA-')
            or boxscores.instant(final['kickoff'])!=kick
            or not kick<=boxscores.instant(final['retrievedAt'])<=now):
            return decision('held','Final identity or observation clock mismatch')
        source=urlparse(final.get('source',''))
        if source.scheme!='https' or source.hostname!='site.api.espn.com' or '/basketball/nba/summary' not in source.path or parse_qs(source.query).get('event')!=[str(play['eventId']).removeprefix('NBA-')]:
            return decision('held','Official final source unavailable')
        people=[p for p in final['players'] if str(p['id'])==str(play['athleteId']) and str(p['team'])==str(play['team'])]
        if len(people)!=1:return decision('held','Player/team identity unavailable')
        player=people[0]
        if player.get('dnp') is True:return decision('settled','Did not participate; general rule',result='void')
        if player.get('dnp') is not False:return decision('held','Participation unknown')
        actual=player.get('stats',{}).get(play['stat']);line=play['line'];side=play.get('direction',play.get('side'))
        if not numeric(actual) or actual<0 or not numeric(line) or line<0:return decision('held','Actual statistic/threshold unavailable')
        result='push' if actual==line else 'win' if (actual>line)==(side=='over') else 'loss'
        if result=='win':return decision('settled','Full-game result including overtime',actual,result)
        review=injury_review or {}
        if review.get('checked') is not True or not review.get('source'):
            return decision('held','Postgame injury check required',actual)
        if (str(review.get('eventId','')).removeprefix('NBA-')!=str(play['eventId']).removeprefix('NBA-')
            or str(review.get('athleteId'))!=str(play['athleteId'])
            or not kick<=boxscores.instant(review['checkedAt'])<=now):
            return decision('held','Injury review identity/clock mismatch',actual)
        if review.get('status')=='no-injury':return decision('settled','Injury check clear; full-game statistics',actual,result)
        if side=='over' and review.get('status')=='injured':
            periods=player.get('quarters',{})
            needed={q for p in final['players'] for q in p.get('quarters',{})}
            complete=(final.get('quarterWorkloadEvidence',{}).get('status')=='reconciled'
                and {'1','2','3','4'}<=set(periods) and needed<=set(periods)
                and all(numeric(periods[q].get('minutes')) for q in needed))
            if not complete:return decision('held','Second-half participation not reconciled',actual)
            second_half=any(periods[q]['minutes']>0 for q in needed if int(q)>=3)
            statement=urlparse(review.get('statementSource',''))
            official=(statement.scheme=='https' and (statement.hostname=='nba.com' or (statement.hostname or '').endswith('.nba.com')))
            ended=boxscores.instant(review['gameEndedAt']);issued=boxscores.instant(review['statementAt'])
            if (not second_half and official and review.get('cause') in ('injury','illness')
                and kick<ended<=now and kick<=issued<=min(now,ended+timedelta(hours=2))):
                return decision('settled','DraftKings NBA over: no second-half play and timely official injury statement',actual,'void')
        if review.get('status') not in ('no-injury','injured','unverified','failed'):
            return decision('held','Injury review unresolved',actual)
        if now<kick+timedelta(hours=12):return decision('held','Injury/official-book review window still open',actual)
        return decision('settled','12-hour reviewed fallback to official stats; append later book corrections if verified',actual,result)
    except (KeyError,TypeError,ValueError,OverflowError):
        return decision('held','Missing or invalid settlement evidence')
