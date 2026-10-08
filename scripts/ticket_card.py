"""Map immutable published plays into the reviewed Kitchen Ticket artwork."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pick_card
import ticket_cards
import ticket_kit
import x_post


def _name(pick):
    title = str(pick.get('title') or '')
    match = re.match(r'^(.*?)\s+(?:OVER|UNDER)\s+\d', title, re.I)
    return match.group(1) if match else str(pick.get('player') or title)


def _logo(team, league, fetch):
    url = pick_card.logo_url(team or {}, league)
    return fetch(url) if url else None


def _colors(team):
    return (team.get('color') or '#2A2F33', team.get('alternateColor') or '#0B0D0F')


def _player_side(pick, game, player_side=None):
    if player_side in ('away', 'home'):
        return player_side
    athlete = str(pick.get('athleteId') or '')
    player = next((row for row in game.get('players') or [] if str(row.get('id')) == athlete), None)
    if player:
        for side in ('away', 'home'):
            if str((game.get(side) or {}).get('id')) == str(player.get('team')):
                return side
    raise ValueError(f"Cannot verify team for player-prop card {pick.get('id')}")


def supporting_reason(pick):
    """Use only saved evidence that actually supports this side; otherwise omit WHY."""
    evidence = pick.get('reasoning') or {}
    direction = str(pick.get('direction') or '').lower()
    line = pick.get('line')
    history = str(evidence.get('history') or '').strip()
    match = re.search(r'(\d+) of (\d+)\s+(over|under)\s+(\d+(?:\.\d+)?)', history, re.I)
    if match and line is not None:
        hits, games, side, threshold = match.groups()
        if int(games) >= 5 and int(hits) / int(games) >= .60 and side.lower() == direction and float(threshold) == float(line):
            return history
    for context in evidence.get('context') or []:
        row = str(context)
        rank = re.search(r'(\d+) of (\d+) this season \(1 is stingiest\)', row, re.I)
        if rank:
            place, total = map(int, rank.groups())
            if total >= 12 and ((direction == 'over' and place / total >= 2 / 3) or
                                (direction == 'under' and place / total <= 1 / 3)):
                return row
        rising = re.search(r'(?:targets|carries|share) up from (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)', row, re.I)
        if rising and float(rising.group(2)) > float(rising.group(1)):
            return row
    return None


def straight_data(pick, game, *, featured=False, player_side=None, art=None, fetch=None, reason=None):
    """Only source numbers from the posted pick; missing calibration stays absent."""
    fetch = fetch or pick_card.fetch_data_uri
    league = game.get('league') or str(pick.get('id') or '').split('-')[0]
    away, home = game.get('away') or {}, game.get('home') or {}
    away_code = away.get('abbreviation') or 'AWAY'
    home_code = home.get('abbreviation') or 'HOME'
    logos = (_logo(away, league, fetch), _logo(home, league, fetch))
    prop = pick_card.play_kind(pick) == 'player'
    if prop:
        player_side = _player_side(pick, game, player_side)
    art = art if art is not None else pick_card.artwork(pick, game, player_side=player_side)
    side = pick_card.side_for(pick, game, player_side)
    team = game.get(side) or home
    team_code = team.get('abbreviation') or home_code
    chance_row = pick.get('probabilityAtPublication') or {}
    calibrated = bool(chance_row.get('calibrated') and isinstance(chance_row.get('chance'), (int, float))
                      and isinstance(chance_row.get('breakEven'), (int, float)))
    if reason is None:
        reason = supporting_reason(pick)
    units = pick.get('riskUnits', pick.get('units', 1))
    if not isinstance(units, (int, float)) or units <= 0:
        units = 1
    output = {
        'kind': 'player' if prop else 'game', 'featured': bool(featured),
        'player': _name(pick) if prop else '', 'team': team_code,
        'away': away_code, 'home': home_code,
        'away_name': pick_card.team_label(away, league),
        'home_name': pick_card.team_label(home, league),
        'away_logo': logos[0], 'home_logo': logos[1],
        'when': pick_card.felt_when(game), 'when_caps': pick_card.felt_when(game).upper(),
        'market': pick.get('market') or pick.get('marketType'),
        'line': f"{float(pick['line']):g}", 'odds': pick['odds'], 'book': pick['book'],
        'chance': chance_row.get('chance') if calibrated else None,
        'needs': chance_row.get('breakEven') if calibrated else None,
        'calibrated': calibrated, 'reason': reason,
        'units': float(units), 'photo': (art or {}).get('uri') if (art or {}).get('kind') == 'photo' else None,
        'team_logo': (art or {}).get('uris', [None])[0] if prop and (art or {}).get('kind') == 'logos' else _logo(team, league, fetch),
        'team_colors': {away_code: _colors(away), home_code: _colors(home), team_code: _colors(team)},
    }
    direction = str(pick.get('direction') or '').lower()
    if direction in ('over', 'under'):
        output['side'] = direction.upper()
    elif pick.get('marketType') == 'spread':
        number = float(pick['line'])
        output['side'] = f'{pick_card.team_label(team, league).upper()} {number:+g}'
        output['side_short'] = f'{team_code} {number:+g}'
    else:
        output['side'] = str(pick.get('title') or '').upper()
    return output


def straight_svg(pick, game, **kwargs):
    data = straight_data(pick, game, **kwargs)
    card = ticket_cards.play_card(data)
    problems = ticket_kit.qa(card, str(pick.get('id') or 'play'))
    if problems:
        raise ValueError('; '.join(problems))
    return card.svg()


def fun_data(pick, games, player_team=None, *, fetch=None, art=None):
    """Build a Chef's Special from the exact published ticket and its priced legs."""
    fetch = fetch or pick_card.fetch_data_uri
    normalized = dict(pick, legs=[{'title': leg} if isinstance(leg, str) else leg for leg in pick.get('legs') or []])
    art = art if art is not None else pick_card.ticket_art(normalized, games, player_team, fetch)
    legs = []
    for leg, image in zip(normalized['legs'], art):
        if not isinstance(leg, dict) or not isinstance(leg.get('odds'), (int, float)):
            raise ValueError('fun ticket leg lacks its published price')
        uris = (image or {}).get('uris') or []
        visual = (('photo', image['uri']) if (image or {}).get('kind') == 'photo' else
                  ('logos', *uris[:2]) if len(uris) >= 2 else
                  ('logo', uris[0]) if uris else None)
        legs.append({'title': leg['title'], 'odds': int(leg['odds']), 'art': visual})
    if len(legs) != len(normalized['legs']):
        raise ValueError('fun ticket art/leg count mismatch')
    starts = [str(leg.get('kickoff')) for leg in normalized['legs'] if leg.get('kickoff')]
    date = ''
    if starts:
        date = datetime.fromisoformat(min(starts).replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York')).strftime('%a %b %-d').upper()
    ranked = sorted(range(len(normalized['legs'])),
                    key=lambda index: (str(normalized['legs'][index].get('kickoff') or ''), -index), reverse=True)
    hero_index = next((index for index in ranked if (art[index] or {}).get('kind') == 'photo'), None)
    hero_photo = art[hero_index]['uri'] if hero_index is not None else None
    hero_logo = next((((art[index] or {}).get('uris') or [None])[0] for index in ranked
                      if (art[index] or {}).get('kind') == 'logos' and (art[index] or {}).get('uris')), None)
    hero_team = None
    if hero_index is not None:
        leg = normalized['legs'][hero_index]
        game = games.get(leg.get('gameId')) or {}
        athlete_team = str((player_team or {}).get(pick_card.leg_athlete_id(leg)) or '')
        hero_team = next((team for team in (game.get('away'), game.get('home'))
                          if team and str(team.get('id')) == athlete_team), None)
    return {'odds': int(pick['odds']), 'book': pick['book'], 'date': date, 'stake': 10,
            'units': float(pick.get('riskUnits', .25)), 'price_estimated': bool(pick.get('priceEstimated')),
            'photo': hero_photo, 'hero_logo': hero_logo, 'hero_team': _colors(hero_team or {}),
            'hero_team_name': (hero_team or {}).get('abbreviation') or 'K', 'legs': legs}


def fun_svg(pick, games, player_team=None, **kwargs):
    card = ticket_cards.ticket_card(fun_data(pick, games, player_team, **kwargs))
    problems = ticket_kit.qa(card, str(pick.get('id') or 'fun'))
    if problems:
        raise ValueError('; '.join(problems))
    return card.svg()


def climb_data(pick, games, player_team=None, **kwargs):
    if pick.get('parlayType') != 'ladder':
        raise ValueError('80/20 Climb card needs a published rung')
    info = pick.get('ladder') or {}
    legs = fun_data(pick, games, player_team, **kwargs)['legs']
    stake, payout = int(info['stake']), int(info['payout'])
    bank_this = int(info.get('bankThisWin', round(payout * .2)))
    return {'run': int(info['run']), 'step': int(info['step']), 'stake': stake, 'payout': payout,
            'banked': int(info.get('banked') or 0), 'bank_this': bank_this,
            'next_stake': int(info.get('nextStake', payout - bank_this)),
            'goal': int(info.get('goal') or 1000), 'odds': int(pick['odds']), 'book': pick['book'], 'legs': legs}


def climb_svg(pick, games, player_team=None, **kwargs):
    card = ticket_cards.climb_card(climb_data(pick, games, player_team, **kwargs))
    problems = ticket_kit.qa(card, str(pick.get('id') or 'climb'))
    if problems:
        raise ValueError('; '.join(problems))
    return card.svg()


def climb_result_svg(pick, games, player_team=None, **kwargs):
    """Settle a rung from recorded leg results; never infer a miss from the headline."""
    data = climb_data(pick, games, player_team, **kwargs)
    info = pick.get('ladder') or {}
    result = str(pick.get('result') or '').lower()
    if result not in ('win', 'loss', 'push', 'void'):
        raise ValueError('Climb result card needs a recorded result')
    actual = str(pick.get('actual') or '')
    if actual.lower().startswith('legs:'):
        marks = [part.strip().lower() for part in actual.split(':', 1)[1].split(',')]
    else:
        marks = ['win'] * len(data['legs']) if result == 'win' else []
    data['leg_results'] = {index: {'win': 'hit', 'loss': 'miss'}.get(mark)
                           for index, mark in enumerate(marks[:len(data['legs'])])}
    data['result'] = result
    data['start'] = int(info.get('start') or 50)
    if result == 'win':
        data['banked'] = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else data['banked'] + data['bank_this'])
        data['complete'] = int(info.get('totalAfter') if info.get('totalAfter') is not None else data['banked'] + data['next_stake']) >= data['goal']
    card = ticket_cards.climb_card(data)
    problems = ticket_kit.qa(card, str(pick.get('id') or 'climb-result'))
    if problems:
        raise ValueError('; '.join(problems))
    return card.svg()


def cooked_data(pick, game, *, art=None, fetch=None, player_side=None):
    """A won player prop, using the immutable grading value and site's unit rule."""
    if pick_card.play_kind(pick) != 'player' or pick.get('result') != 'win':
        raise ValueError('Cooked preview needs a won player prop')
    if not isinstance(pick.get('actualValue'), (int, float)):
        raise ValueError('Cooked preview needs a recorded numeric final')
    fetch = fetch or pick_card.fetch_data_uri
    player_side = _player_side(pick, game, player_side)
    art = art if art is not None else pick_card.artwork(pick, game, player_side=player_side)
    side = player_side
    team = game.get(side) or {}
    won = x_post.units_for(pick)
    if won is None or won <= 0:
        raise ValueError('Cooked preview needs priced won units')
    return {'player': _name(pick), 'side': str(pick['direction']).upper(),
            'line': f"{float(pick['line']):g}", 'market': pick['market'],
            'odds': pick['odds'], 'book': pick['book'],
            'final': pick['actualValue'], 'margin': f"{abs(pick['actualValue'] - pick['line']):g}",
            'photo': (art or {}).get('uri') if (art or {}).get('kind') == 'photo' else None,
            'team_logo': _logo(team, game.get('league'), fetch), 'units_won': won,
            'close_line': None}


def cooked_svg(pick, game, **kwargs):
    card = ticket_cards.cooked_card(cooked_data(pick, game, **kwargs))
    problems = ticket_kit.qa(card, str(pick.get('id') or 'cooked'))
    if problems:
        raise ValueError('; '.join(problems))
    return card.svg()


def final_detail(pick):
    """A final stat and exact-line margin, only when the stored result supports the arithmetic."""
    import receipts
    import result_display
    if pick.get('marketType') == 'prop':
        rich = result_display.detail(pick)
        if rich:
            return rich
    actual = result_display.clean_actual(pick)
    market = str(pick.get('market') or '')
    market_type = str(pick.get('marketType') or '')
    value = pick.get('actualValue')
    if market_type == 'prop':
        match = re.search(r':\s*(-?\d+(?:\.\d+)?)\b', actual)
        value = float(match.group(1)) if match else value
        stat = {'recYds': 'rec yds', 'rec': 'recs', 'passYds': 'pass yds', 'rushYds': 'rush yds',
                'passTD': 'pass TDs', 'rushTD': 'rush TDs', 'recTD': 'rec TDs', 'car': 'carries',
                'att': 'attempts', 'cmp': 'completions', 'targets': 'targets'}.get(market)
        base = f'{float(value):g} {stat}' if isinstance(value, (int, float)) and stat else receipts.result_detail(pick)
    elif market_type == 'total':
        scores = re.findall(r'\b\d+\b', actual)
        if len(scores) == 2:
            value = sum(map(int, scores))
        base = f'Final: {actual}' if actual else receipts.result_detail(pick)
    else:
        base = re.sub(r'^Final: [^:]+: ', 'Final: ', receipts.result_detail(pick))
    line = pick.get('line')
    if pick.get('result') in ('win', 'loss') and isinstance(value, (int, float)) and isinstance(line, (int, float)):
        return f"{base} · {'cleared' if pick['result'] == 'win' else 'missed'} by {abs(float(value) - float(line)):g}"
    return base


def final_data(rows, day):
    """One settled day, best bets only; fun tickets and Climb are tracked apart."""
    import receipts
    straight = [pick for pick in rows if pick_card.play_kind(pick) not in ('parlay', 'ladder')]
    if not straight or any(pick.get('result') not in ('win', 'loss', 'push', 'void') for pick in straight):
        raise ValueError('Final preview needs a settled slate of best bets')
    wins = sum(pick['result'] == 'win' for pick in straight)
    losses = sum(pick['result'] == 'loss' for pick in straight)
    result_names = {'win': 'hit', 'loss': 'miss', 'push': 'push', 'void': 'void'}
    net = sum(x_post.units_for(pick) or 0 for pick in straight)
    body = [{'result': result_names[pick['result']], 'title': re.sub(r'\s+', ' ', receipts.label(pick)).strip(),
             'detail': final_detail(pick), 'unit_text':
             (f"{x_post.units_for(pick):+.2f}u" if x_post.units_for(pick) is not None else '—')}
            for pick in straight]
    return {'headline': f'{wins}-{losses}', 'day': day, 'rows': body, 'net_units': net}


def final_svg(rows, day):
    card = ticket_cards.final_card(final_data(rows, day))
    problems = ticket_kit.qa(card, 'final')
    if problems:
        raise ValueError('; '.join(problems))
    return card.svg()


def prep_svg(prep, *, fetch=None):
    """Render a research-only Prep List from the site's already checked rows."""
    from datetime import date
    fetch = fetch or pick_card.fetch_data_uri
    rows = []
    for source in prep.get('rows') or []:
        league = source.get('league')
        athlete = str(source.get('athleteId') or '')
        sport = 'nfl' if league == 'NFL' else 'college-football' if league == 'CFB' else None
        photo = fetch(pick_card.HEADSHOT.format(sport=sport, athlete=athlete)) if sport and athlete else None
        units = ' '.join(ticket_kit.STAT_UNITS.get(source.get('stat'), (source.get('stat') or 'STAT',)))
        games, hits = source.get('games'), source.get('hits')
        if not isinstance(games, int) or not isinstance(hits, int) or games < 1 or not 0 <= hits <= games:
            raise ValueError('Prep List requires an exact stored hit count')
        rows.append({'player': source['player'],
                     'selection': f"{str(source['direction']).upper()} {float(source['line']):g} {units}",
                     'hits': f'{hits}/{games}', 'odds': source['odds'], 'book': source['book'],
                     'clears': bool(source.get('clears')), 'photo': photo,
                     'team_color': source.get('teamColor') or '#2A2F33'})
    if not rows:
        raise ValueError('Prep List has no checked rows')
    day = date.fromisoformat(prep['day'])
    card = ticket_cards.prep_card({'day': f'{day:%a %b} {day.day}', 'rows': rows,
                                   'stub': 'RESEARCH · NOT A BEST BET'})
    problems = ticket_kit.qa(card, 'prep-list')
    if problems:
        raise ValueError('; '.join(problems))
    return card.svg()
