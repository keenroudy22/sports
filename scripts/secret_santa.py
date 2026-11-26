"""Derive the site-only rollover from exact reviewed singles and stored finals."""

from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import boxscores

START_CENTS = 2000
LAST_DAY = date(2026, 12, 25)
EASTERN = ZoneInfo('America/New_York')


def return_on_win(cents, odds):
    return cents + int((Decimal(cents) * 100 / abs(odds)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


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
    if play['market'] == 'total':
        margin = (home + away - play['line']) * (1 if side == 'over' else -1)
    else:
        margin = (home - away if side == 'home' else away - home) + play.get('line', 0)
    return ('win' if margin > 0 else 'loss' if margin < 0 else 'push', f'{away}–{home}')


def build(entries, football, basketball, now):
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
        if (market not in ('spread', 'moneyline', 'total')
                or side not in (('over', 'under') if market == 'total' else ('home', 'away'))
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
