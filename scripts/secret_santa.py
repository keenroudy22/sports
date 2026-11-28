"""Derive the site-only rollover from reviewed selections and stored finals."""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import boxscores
from fun_ticket_review import https

START_CENTS = 2000
LAST_DAY = date(2026, 12, 25)
EASTERN = ZoneInfo('America/New_York')
FOOTBALL_PROPS = {'recYds': 'receiving yards', 'rec': 'receptions',
                  'rushYds': 'rushing yards', 'passYds': 'passing yards'}


def return_on_win(cents, odds):
    profit = Decimal(cents) * 100 / abs(odds) if odds < 0 else Decimal(cents) * odds / 100
    return cents + int(profit.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def grade(play, game, now):
    if not game or boxscores.instant(game['kickoff']) != boxscores.instant(play['startsAt']):
        return None
    observed = boxscores.instant(game['retrievedAt'])
    if not boxscores.instant(play['startsAt']) <= observed <= now:
        return None
    if any(str(game[side]['id']) != play[f'{side}Id'] for side in ('home', 'away')):
        return None
    if play['league'] in ('NBA', 'CBB'):
        if game.get('type') != 2:
            return None
        away, home = game.get('awayScore'), game.get('homeScore')
    else:
        away, home = game['away'].get('score'), game['home'].get('score')
    if any(type(score) is not int or score < 0 for score in (away, home)):
        return None
    side = play['side']
    detail = f'{away}–{home}'
    if play['market'] == 'player':
        players = [p for p in game.get('players', []) if str(p.get('id')) == play['athleteId']]
        if len(players) != 1 or str(players[0].get('team')) != play['teamId']:
            return None
        actual = players[0].get(play['stat'])
        if type(actual) is not int or players[0].get('dnp'):
            return None
        margin = (actual - play['line']) * (1 if side == 'over' else -1)
        detail = f"{actual} {FOOTBALL_PROPS[play['stat']]}"
    elif play['market'] == 'total':
        margin = (home + away - play['line']) * (1 if side == 'over' else -1)
    else:
        margin = (home - away if side == 'home' else away - home) + play.get('line', 0)
    return ('win' if margin > 0 else 'loss' if margin < 0 else 'push', detail)


def build_singles(entries, football, basketball, now):
    finals = {(game['league'], str(game['eventId'])): game for game in football}
    finals.update({(league, str(game['eventId'])): game for league, games in basketball.items() for game in games})
    balance, history, current = START_CENTS, [], None
    count = Counter()
    seen = set()
    previous = None
    settled = None
    last_event = None
    run, step = 1, 0
    pass_today = None
    withdrawal_index = None
    for index, play in enumerate(entries):
        if 'withdrawBeforeKickoff' in play:
            if index == withdrawal_index:
                continue
            raise ValueError('Secret Santa withdrawal must immediately follow its original')
        if 'restartAfter' in play:
            if balance or last_event != play['restartAfter']:
                break
            run, step, balance = run + 1, 0, START_CENTS
            continue
        league, event = play['league'], play['eventId']
        key = league, event
        if (league not in ('NFL', 'CFB', 'NBA', 'CBB') or not event.isdigit()
                or key in seen or type(play['odds']) is not int or not -450 <= play['odds'] <= -350):
            raise ValueError('Secret Santa needs a distinct supported single near −400')
        seen.add(key)
        market, side = play['market'], play['side']
        if market == 'player' and (league not in ('NFL', 'CFB') or play.get('stat') not in FOOTBALL_PROPS
                or not isinstance(play.get('athleteId'), str) or not play['athleteId'].isdigit()
                or play.get('teamId') not in (play['homeId'], play['awayId'])):
            raise ValueError('Secret Santa player prop requires an exact supported athlete, team and stat')
        if (market not in ('spread', 'moneyline', 'total', 'player')
                or side not in (('over', 'under') if market in ('total', 'player') else ('home', 'away'))
                or market != 'moneyline' and type(play.get('line')) not in (int, float)
                or market == 'moneyline' and play.get('line', 0) != 0):
            raise ValueError('Invalid Secret Santa market')
        checked, start = (boxscores.instant(play[field]) for field in ('checkedAt', 'startsAt'))
        day = start.astimezone(EASTERN).date()
        count[day] += 1
        if (checked >= start or checked.astimezone(EASTERN).date() != day or day > LAST_DAY
                or count[day] > 2 or previous and checked <= previous):
            raise ValueError('Invalid Secret Santa review or kickoff order')
        previous = start
        sources = play['sources']
        if not sources or any(urlsplit(source['url']).scheme != 'https' for source in sources):
            raise ValueError('Secret Santa requires published research and book evidence')
        if checked > now or not balance or settled and checked < settled:
            break
        ticket = {field: play[field] for field in ('selection', 'matchup', 'startsAt', 'book', 'checkedAt',
                  'odds', 'reason', 'countercase', 'sources')}
        ticket.update(run=run, step=step + 1, balance=balance, winReturn=return_on_win(balance, play['odds']))
        action = entries[index + 1] if index + 1 < len(entries) else {}
        if 'withdrawBeforeKickoff' in action:
            withdrawn = boxscores.instant(action['withdrawnAt'])
            reason = action['reason']
            if (action['withdrawBeforeKickoff'] != event or not checked < withdrawn < start
                    or not isinstance(reason, str) or not reason.strip()):
                raise ValueError('Secret Santa withdrawal needs the exact original and a pregame reason')
            if withdrawn <= now:
                history.append(dict(ticket, result='withdrawn', withdrawnAt=action['withdrawnAt'],
                                    withdrawalReason=reason, after=balance))
                if withdrawn.astimezone(EASTERN).date() == now.astimezone(EASTERN).date():
                    pass_today = reason
                previous = withdrawn
                count[day] -= 1
                withdrawal_index = index + 1
                continue
        step += 1
        if day == now.astimezone(EASTERN).date():
            pass_today = None
        final = grade(play, finals.get(key), now)
        if not final:
            current = ticket
            break
        result, score = final
        after = {'win': ticket['winReturn'], 'loss': 0, 'push': balance}[result]
        final_game = finals[key]
        result_url = (final_game.get('sources') or {}).get('page') or final_game.get('source')
        if not result_url and league in ('NBA', 'CBB') and final_game.get('state') == 'post':
            # The official hoops store retains ESPN event IDs, not page URLs.
            sport = 'nba' if league == 'NBA' else 'mens-college-basketball'
            result_url = f'https://www.espn.com/{sport}/boxscore/_/gameId/{event}'
        if not isinstance(result_url, str) or urlsplit(result_url).scheme != 'https':
            current = ticket
            break
        history.append(dict(ticket, result=result, score=score, after=after, resultUrl=result_url))
        balance = after
        settled = boxscores.instant(final_game['retrievedAt'])
        last_event = event
    results = Counter(row['result'] for row in history if row['run'] == run)
    return dict(run=run, balance=balance, current=current, history=history, passToday=pass_today,
                wins=results['win'], losses=results['loss'], pushes=results['push'],
                closed=not balance or (not current and now.astimezone(EASTERN).date() > LAST_DAY))


PAIR_FORMAT = 'two-player-rollover-v1'
GOAL_CENTS = 1_000_000
PLAN_WINS = 14
MIN_PAIR_ODDS = -178
HOOPS_PROPS = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', 'fg3m': 'made threes'}
REVIEW_FIELDS = ('workload', 'availability', 'matchup', 'countercase')


def american_price(value):
    return type(value) is int and abs(value) >= 100


def pair_ticket(play, day, balance, run, step):
    """Validate the prospective paper original before deriving anything public."""
    legs = play.get('legs', [])
    book, odds = play.get('book'), play.get('odds')
    if (len(legs) != 2 or book not in ('DraftKings', 'FanDuel') or not american_price(odds)
            or odds < MIN_PAIR_ODDS or play.get('unboosted') is not True or play.get('quoteVerified') is not True
            or not https(play.get('quoteUrl'), book)):
        raise ValueError('Two researched players and an exact qualifying unboosted book ticket are required')
    checked = boxscores.instant(play['checkedAt'])
    starts = []
    keys = set()
    players = set()
    public = []
    for leg in legs:
        league, event = leg['league'], leg['eventId']
        athlete = leg['athleteId']
        key = league, event
        start = boxscores.instant(leg['startsAt'])
        stat_names = FOOTBALL_PROPS if league in ('NFL', 'CFB') else HOOPS_PROPS
        if (leg.get('book') != book or league not in ('NFL', 'CFB', 'NBA', 'CBB') or not isinstance(event, str) or not event.isdigit()
                or not isinstance(athlete, str) or not athlete.isdigit() or key in keys or (league, athlete) in players
                or leg['homeId'] == leg['awayId'] or leg['teamId'] not in (leg['homeId'], leg['awayId'])
                or leg['stat'] not in stat_names or leg['side'] not in ('over', 'under')
                or type(leg['line']) not in (int, float) or not 0 <= leg['line'] < 2000
                or leg['line'] * 2 != int(leg['line'] * 2) or not american_price(leg.get('odds'))):
            raise ValueError('Each leg needs a distinct fixture and an exact supported player prop')
        if start.astimezone(EASTERN).date() != day or checked >= start:
            raise ValueError('Both legs must be reviewed before the first start on the same slate')
        review = leg['review']
        reviewed = boxscores.instant(review['checkedAt'])
        if (not timedelta(0) <= checked - reviewed <= timedelta(minutes=90)
                or not all(isinstance(review.get(k), str) and review[k].strip() for k in REVIEW_FIELDS)
                or not all(https(review.get(k)) for k in ('roleSource', 'matchupSource', 'availabilitySource'))
                or not https(leg.get('quoteUrl'), book) or not leg.get('selection') or not leg.get('matchup')):
            raise ValueError('Fresh sourced role, opponent, availability, countercase and same-book price required for each leg')
        starts.append(start)
        keys.add(key)
        players.add((league, athlete))
        public.append({k: leg[k] for k in ('selection', 'matchup', 'startsAt', 'odds')})
    if not isinstance(play.get('reason'), str) or not play['reason'].strip():
        raise ValueError('Missing reviewed ticket rationale')
    return dict(run=run, step=step, selection='Two-player parlay', legs=public,
                startsAt=min(starts).isoformat(), checkedAt=play['checkedAt'], balance=balance,
                winReturn=return_on_win(balance, odds), odds=odds, book=book, reason=play['reason'])


def pair_leg_final(leg, finals, player_boxes, now):
    league, event = leg['league'], leg['eventId']
    game = finals.get((league, event))
    start = boxscores.instant(leg['startsAt'])
    if (not game or boxscores.instant(game['kickoff']) != start
            or any(str(game[s]['id']) != leg[s + 'Id'] for s in ('home', 'away'))):
        return None
    source = (game.get('sources') or {}).get('page')
    box = game
    if league in ('NBA', 'CBB'):
        if game.get('state') != 'post' or game.get('type') != 2:
            return None
        box = player_boxes.get((league, event))
        if not box or boxscores.instant(box['kickoff']) != start:
            return None
        if set(box.get('teams', {})) != {leg['homeId'], leg['awayId']}:
            return None
        source = box.get('source')
    elif any(type(game[s].get('score')) is not int for s in ('home', 'away')):
        return None
    clocks = [boxscores.instant(row['retrievedAt']) for row in (game, box)]
    if not https(source) or min(clocks) < start or max(clocks) > now:
        return None
    found = [p for p in box.get('players', []) if str(p.get('id')) == leg['athleteId']]
    if len(found) != 1 or str(found[0].get('team')) != leg['teamId']:
        return None
    player = found[0]
    if player.get('dnp') is True:
        result, detail = 'void', 'Did not play'
    else:
        actual = player.get('stats', player).get(leg['stat'])
        if type(actual) is not int:
            return None
        margin = (actual - leg['line']) * (1 if leg['side'] == 'over' else -1)
        result = 'win' if margin > 0 else 'loss' if margin < 0 else 'push'
        detail = f"{actual} {(FOOTBALL_PROPS | HOOPS_PROPS)[leg['stat']]}"
    return dict(result=result, score=detail, resultUrl=source, observed=max(clocks))


def build(entries, football, basketball, now, basketball_boxes=()):
    split = next((i for i, p in enumerate(entries) if p.get('format') == PAIR_FORMAT), len(entries))
    old = build_singles(entries[:split], football, basketball, now)
    if split == len(entries):
        return old
    marker = entries[split]
    if not split or marker.get('restartAfter') != entries[split-1].get('eventId'):
        raise ValueError('The new paper run must identify its preceding original')
    opened = boxscores.instant(marker['openedAt'])
    if opened > now or old['balance'] or old['current'] or old['history'][-1]['result'] != 'loss':
        return old
    finals = {(g['league'], str(g['eventId'])): g for g in football}
    finals.update({(league, str(g['eventId'])): g for league, games in basketball.items() for g in games})
    boxes = {(g['league'], str(g['eventId']).split('-')[-1]): g for g in basketball_boxes}
    history = old['history'].copy()
    balance, run, step = START_CENTS, old['run'] + 1, 0
    ready = opened
    current = None
    days = Counter()
    totals = Counter()
    seen = set()
    for play in entries[split+1:]:
        checked = boxscores.instant(play['checkedAt'])
        if checked > now:
            break
        day = checked.astimezone(EASTERN).date()
        if not balance or balance >= GOAL_CENTS or day > LAST_DAY or checked < ready or days[day] >= 2:
            raise ValueError('Ticket falls outside the open paper rollover')
        step += 1
        ticket = pair_ticket(play, day, balance, run, step)
        keys = {(leg['league'], leg['eventId']) for leg in play['legs']}
        if keys & seen:
            raise ValueError('A new rollover step must use new games')
        seen.update(keys)
        days[day] += 1
        grades = [pair_leg_final(leg, finals, boxes, now) for leg in play['legs']]
        if any(g is None for g in grades):
            current = ticket
            break
        results = [g['result'] for g in grades]
        if 'loss' in results:
            result, after = 'loss', 0
        elif results == ['win', 'win']:
            result, after = 'win', ticket['winReturn']
        elif 'win' in results:
            result = 'win'
            after = return_on_win(balance, play['legs'][results.index('win')]['odds'])
        else:
            result, after = 'push', balance
        ready = max(g['observed'] for g in grades)
        for public, grade_row in zip(ticket['legs'], grades):
            public.update({k: grade_row[k] for k in ('result', 'score', 'resultUrl')})
        history.append(dict(ticket, result=result, after=after))
        totals[result] += 1
        balance = after
    return dict(run=run, balance=balance, current=current, history=history, passToday=None,
                wins=totals['win'], losses=totals['loss'], pushes=totals['push'], goalCents=GOAL_CENTS,
                planWins=PLAN_WINS, targetOdds=MIN_PAIR_ODDS, format=PAIR_FORMAT,
                closed=not balance or balance >= GOAL_CENTS or (not current and now.astimezone(EASTERN).date() > LAST_DAY))
