"""Explicitly sourced NBA decisions, never a promotion of the probability study.

Only a reviewed packet can enter this route. Current stored identity, exact
two-sided prices, official participation and current-role holds still apply.
No feed call, inferred probability, expected return or automatic selection.
"""
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import boxscores
import nba_capture
import nba_player_props

METHOD = 'sourced-nba-primary-prop-v1'
EFFECTIVE = datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc)
STATS = {'pts', 'reb', 'ast'}


def source(url):
    try:
        p = urlsplit(url)
        return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password
    except (TypeError, ValueError):
        return False


def refusal(play, now, *, root=nba_capture.STORE, current=None, send_recheck=False):
    try:
        if now < EFFECTIVE or play.get('selectionMethod') != METHOD:
            return 'Sourced NBA method is not effective'
        if (play.get('league') != 'NBA' or play.get('marketType') != 'player'
                or play.get('book') != 'DraftKings' or play.get('stat') not in STATS
                or play.get('period') != 'full_game' or play.get('direction') not in ('over', 'under')
                or not re.fullmatch(r'NBA-reviewed-[A-Za-z0-9-]{1,120}', str(play.get('id', '')))):
            return 'Unsupported sourced NBA identity or market'
        if any(play.get(k) is not None for k in ('chance', 'rawChance', 'fairOdds', 'expectedValue', 'propEvidence')) or play.get('calibrated') is not False:
            return 'Sourced decisions cannot claim model probability or EV'
        if play.get('model') != METHOD:
            return 'Sourced model label required'
        if any(play.get(k) for k in ('legs', 'parlayType', 'paidProtection', 'allAction', 'alternate')):
            return 'Primary unboosted straight terms only'
        review = play['sourceReview']
        at = boxscores.instant(review['checkedAt'])
        if send_recheck and not at<=boxscores.instant(play['publishedAt'])<=now:
            return 'Original reviewed publication clock required'
        kick = boxscores.instant(play['kickoff'])
        # Initial admission needs a recent human review. A delayed send keeps
        # that immutable original review and proves the current exact price,
        # role and official availability again below. A deployment delay must
        # not make an unchanged original permanently impossible to deliver.
        if ((not send_recheck and not timedelta(0) <= now-at <= timedelta(hours=1))
                or kick <= now+timedelta(minutes=15)
                or kick.astimezone(ZoneInfo('America/New_York')).date() != now.astimezone(ZoneInfo('America/New_York')).date()):
            return 'Current-day review or release window expired'
        if review.get('approved') is not True or review.get('reviewer') != 'kookn-desk':
            return 'Explicit sourced review required'
        for field in ('role', 'matchup', 'countercase', 'why'):
            if not isinstance(review.get(field), str) or len(review[field].strip()) < 20:
                return 'Specific role, matchup, reason and countercase required'
        facts = review.get('sources')
        if not isinstance(facts, list) or not {'role', 'matchup'} <= {r.get('kind') for r in facts}:
            return 'Role and matchup source evidence required'
        for fact in facts:
            seen = boxscores.instant(fact['checkedAt'])
            host = urlsplit(fact['url']).hostname or ''
            if (not source(fact['url']) or not isinstance(fact.get('fact'), str)
                    or not (host in ('nba.com', 'espn.com') or host.endswith(('.nba.com', '.espn.com')))
                    or len(fact['fact'].strip()) < 20 or not timedelta(0) <= now-seen <= timedelta(hours=24)):
                return 'Fresh specific source facts required'
        quote = review['quote']
        if not quote.get('receipt') or not source(quote.get('url')) or quote.get('verified') is not True:
            return 'Visible exact sportsbook receipt required'
        host = urlsplit(quote['url']).hostname or ''
        if host != 'draftkings.com' and not host.endswith('.draftkings.com'):
            return 'DraftKings quote source required'
        seen = boxscores.instant(quote['checkedAt'])
        if ((not send_recheck and not timedelta(0) <= now-seen <= timedelta(hours=1))
                or seen > at):
            return 'Visible quote needs renewal'
        for key in ('athleteId', 'stat', 'line', 'direction', 'odds', 'oppositeOdds'):
            if quote.get(key) != play.get(key):
                return 'Reviewed quote and original terms differ'
        if not source(play.get('source')) or play.get('reasons') != [review['why']]:
            return 'Original source and exact reason required'
        slate = json.loads((Path(root)/'slate.json').read_text())
        g = next((g for g in slate['games'] if g['id'] == play['eventId']), None)
        if not g or any(g.get(k) != play['game'].get(k) for k in ('id', 'providerId', 'season', 'seasonType', 'kickoff', 'teams', 'status')):
            return 'Current fixture differs from reviewed fixture'
        if g.get('status') != 'scheduled' or g['season'] != play['season']:
            return 'Current regular-season fixture required'
        data = nba_player_props.build(now, root, limit=None)['rows'] if current is None else current
        r = next((r for r in data if str(r['eventId']).removeprefix('NBA-') == str(play['eventId']).removeprefix('NBA-')
                  and all(r.get(k) == play.get(k) for k in ('athleteId', 'team', 'stat', 'line', 'book'))), None)
        if not r or r.get('hold') or r.get('name') != play['player']:
            return 'Current player identity, availability or workload is held'
        role = r.get('currentRole') or {}
        if role.get('games', 0) < 3 or type(role.get('medianMinutes')) not in (int, float) or role['medianMinutes'] < 15:
            return 'Three current role observations and meaningful minutes required'
        if role.get('receivedAt') and at < boxscores.instant(role['receivedAt']):
            return 'Review must follow the latest observed role'
        if not nba_player_props.fresh(r.get('sourceAt'), now, 1):
            return 'Stored exact price needs renewal'
        side = play['direction']
        if r[side] != play['odds'] or r['under' if side == 'over' else 'over'] != play['oppositeOdds']:
            return 'Current exact two-sided prices changed'
        if any(type(play[k]) not in (int, float) or not math.isfinite(play[k]) for k in ('line', 'odds', 'oppositeOdds')):
            return 'Finite terms required'
        injury = json.loads((Path(root)/'injuries-current.json').read_text())
        rows, holds = nba_capture.availability_for_game(injury, g, now, max_hours=1)
        if holds or any(nba_capture.blocks_availability(a.get('status')) for a in rows if str(a.get('athleteId') or a.get('id')) == str(play['athleteId'])):
            return 'Official participation unresolved'
        reported = (injury.get('official') or {}).get('reportedAt')
        # Initial review follows its source report. A stored original may remain
        # eligible after a newer report only because current identities/statuses,
        # roles and exact prices have all passed the checks above again.
        if not reported or (not send_recheck and at < boxscores.instant(reported)):
            return 'Review must follow the current official report'
        import social_style
        if social_style.issues(review['why']):
            return 'Public reason fails current caption policy'
    except (OSError, KeyError, ValueError, TypeError, OverflowError, StopIteration):
        return 'Incomplete sourced NBA evidence'
    return None


def verify(play, now):
    return refusal(play, now) is None


def audit_original(play):
    """Audit immutable sourced terms without using today's role/price for yesterday."""
    try:
        at=boxscores.instant(play['publishedAt']);review=play['sourceReview'];quote=review['quote']
        return (at>=EFFECTIVE and play.get('model')==METHOD and play.get('selectionMethod')==METHOD
                and play.get('calibrated') is False
                and all(play.get(k) is None for k in ('chance','rawChance','fairOdds','expectedValue','propEvidence'))
                and play.get('stat') in STATS and play.get('period')=='full_game' and play.get('book')=='DraftKings'
                and review.get('approved') is True and review.get('reviewer')=='kookn-desk'
                and play.get('reasons')==[review['why']]
                and timedelta(0)<=at-boxscores.instant(review['checkedAt'])<=timedelta(hours=1)
                and timedelta(0)<=at-boxscores.instant(quote['checkedAt'])<=timedelta(hours=1)
                and quote.get('verified') is True and bool(quote.get('receipt'))
                and all(quote.get(k)==play.get(k) for k in ('athleteId','stat','line','direction','odds','oppositeOdds'))
                and {'role','matchup'}<={f.get('kind') for f in review['sources']}
                and all(source(f['url']) and f.get('fact') for f in review['sources'])
                and all(len(review[k].strip())>=20 for k in ('role','matchup','countercase','why')))
    except (KeyError,TypeError,ValueError):
        return False


def proposal(row, game, review, now):
    """Build exact terms from a stored row, never from a model-written price."""
    import staking
    side = review['quote']['direction']
    play = dict(id=f"NBA-reviewed-{game['providerId']}-{row['athleteId']}-{row['stat']}-{side}-dk",
        selectionMethod=METHOD, model=METHOD, league='NBA', season=game['season'], seasonType=2,
        eventId=game['id'], game=game, kickoff=game['kickoff'], athleteId=row['athleteId'],
        team=row['team'], player=row['name'], stat=row['stat'], period='full_game',marketType='player',
        direction=side, line=row['line'], odds=row[side], oppositeOdds=row['under' if side=='over' else 'over'],
        book=row['book'], retrievedAt=row['sourceAt'], rawChance=None, chance=None, calibrated=False,
        roleChecked=True, sideVerified=True, exactLineVerified=True, source=review['sources'][0]['url'],
        reasons=[review['why']], projection=None, sourceReview=review)
    staking.apply(play,now)
    return play


def main():
    import argparse
    import run
    import nba_trial
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--admit', action='store_true')
    args = parser.parse_args()
    with run.Lock(run.CONF/'run.lock', wait=run.RUN_LOCK_WAIT):
        if args.admit:
            run.sync()
        now = datetime.now(timezone.utc)
        offer = json.loads(args.spec.read_text())
        held = refusal(offer, now)
        if held:
            raise ValueError(held)
        if args.admit:
            nba_trial.record_publish(offer, now)
            print(json.dumps({'state': 'admitted', 'id': offer['id'], 'commit': run.commit_log(now)}))
        else:
            print(json.dumps({'state': 'reviewed-preview', 'id': offer['id']}))


if __name__ == '__main__':
    main()
