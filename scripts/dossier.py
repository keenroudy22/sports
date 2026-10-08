"""A sourced, partial-safe case file for a published play. No network or model calls.

The run supplies only information it already captured or checked. Missing evidence is
left missing; it is never replaced with a confident-sounding explanation.
"""

from datetime import datetime, timezone

import features
import gates
import pricing


def _stamp(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    return str(value) if value else None


def _item(text, numbers=None, source=None, time=None):
    return {'text': text, 'numbers': numbers or {}, 'source': source, 'time': _stamp(time)}


def _source(label, url, time, found):
    if not isinstance(url, str) or not url.startswith('https://'):
        return
    key = (url, _stamp(time))
    if key not in found:
        found[key] = {'label': label, 'url': url, 'time': _stamp(time)}


def _main_quote(capture, market, direction, book):
    books = (capture or {}).get('books') or {}
    slug = {'DraftKings': 'draftkings', 'FanDuel': 'fanduel'}.get(book)
    block = books.get(slug) or {}
    market_block = block.get('total' if market == 'total' else 'spread') or {}
    if not market_block:
        return None
    if market == 'total':
        line = market_block.get('line')
        price = market_block.get(direction)
    else:
        home = market_block.get('home')
        if home is None:
            return None
        line = home if direction == 'home' else -home
        price = market_block.get('homePrice' if direction == 'home' else 'awayPrice')
    if line is None or price is None:
        return None
    return {'line': line, 'price': price, 'time': _stamp(capture.get('retrievedAt'))}


def _prop_quote(capture, market, player, direction, book):
    slug = {'DraftKings': 'draftkings', 'FanDuel': 'fanduel'}.get(book)
    block = (((capture or {}).get('books') or {}).get(slug) or {}).get('markets') or {}
    row = ((block.get(market) or {}).get(player) or {})
    if row.get('line') is None or row.get(direction) is None:
        return None
    return {'line': row['line'], 'price': row[direction], 'time': _stamp(capture.get('retrievedAt'))}


def _line_history(candidate, game, captures, now):
    market = gates.market_key(candidate)
    direction = gates.side_of(candidate)
    player = candidate.get('player') or candidate.get('_player')
    rows = sorted((r for r in captures if r.get('gameId') == game['id'] and r.get('retrievedAt')
                   and gates.when(r['retrievedAt']) <= now
                   and gates.when(r['retrievedAt']) < gates.when(game['kickoff'])),
                  key=lambda r: r.get('retrievedAt') or '')
    out = {}
    for book in ('DraftKings', 'FanDuel'):
        quotes = [q for row in rows if (q := (_prop_quote(row, market, player, direction, book)
                   if candidate.get('athleteId') else _main_quote(row, market, direction, book)))]
        # The first capture is not the sportsbook's true opener. Never print it
        # as "open" merely because it is the first row our store saw.
        out[book] = {'open': None, 'firstCaptured': quotes[0], 'now': quotes[-1]} if quotes else None
    return {'books': out, 'best': {'book': candidate.get('book'), 'line': candidate.get('line'),
                                  'price': candidate.get('odds'), 'time': _stamp(candidate.get('quotedAt'))}}


def empty(candidate):
    """Safe partial result when a stored source cannot be decoded."""
    return {'reasons': [], 'risks': [_item('Some details are unavailable right now.')], 'reports': [],
            'weather': None, 'line': {'books': {'DraftKings': None, 'FanDuel': None},
                                      'best': {'book': candidate.get('book'), 'line': candidate.get('line'),
                                               'price': candidate.get('odds'), 'time': _stamp(candidate.get('quotedAt'))}},
            'ours': None, 'history': None, 'sources': [], 'partial': True}


def ticket(candidate, now):
    """A bounded case file for a multi-leg post; never invent a leg's hit rate."""
    lines = []
    for leg in candidate.get('legs') or []:
        lines.append({'gameId': leg.get('gameId'), 'title': leg.get('title'), 'line': leg.get('line'),
                      'price': leg.get('odds'), 'book': leg.get('book') or candidate.get('book')})
    sources = {}
    for url in candidate.get('sources') or []:
        _source('Published source', url, now, sources)
    return {'reasons': [_item(str(candidate['why']), source='Published ticket detail', time=now)]
            if candidate.get('why') else [],
            'risks': [_item(str(candidate['risk']), source='Published ticket risk', time=now)]
            if candidate.get('risk') else [], 'reports': [], 'weather': None,
            'line': {'legs': lines, 'best': {'book': candidate.get('book'), 'price': candidate.get('odds'),
                                           'time': _stamp(candidate.get('quotedAt'))}},
            'ours': None, 'history': None, 'sources': list(sources.values()), 'partial': True}


def build(candidate, game, ctx, records, now, *, captures=(), weather_row=None, headline_reason=None):
    """Build the case file from stores and the run's existing verified research facts.

    `captures` may include odds and prop-odds history. This function does not fetch
    anything. A partial dossier is valid and must never delay an admitted play.
    """
    reasons, risks, reports, sources = [], [], [], {}
    if headline_reason:
        reasons.append(_item(headline_reason, source='Game box scores or verified report', time=now))
    market = gates.market_key(candidate)
    side = gates.side_of(candidate)
    line = candidate.get('line')
    projection = candidate.get('projection')
    snap = ctx.snapshot(game['id'])
    if projection is not None and line is not None:
        units = pricing.WORDS.get(market, 'points')
        phrase = ('total' if market == 'total' else 'spread' if market == 'spread' else units)
        text = f"My {phrase} is {projection:g}; the book's line is {float(line):g}."
        item = _item(text, {'projection': projection, 'line': line},
                     "Kook'n projection", candidate.get('snapshotAt') or (snap or {}).get('retrievedAt'))
        if market != 'spread' and side in ('over', 'under'):
            (reasons if (projection - line) * (1 if side == 'over' else -1) > 0 else risks).append(item)
        else:
            reasons.append(item)

    athlete = candidate.get('athleteId')
    if athlete and line is not None:
        logs = [r for r in (ctx.player_logs.get(str(athlete)) or []) if r.get('season') == game.get('season')]
        values = [features.value(r, market) for r in logs[-5:]]
        values = [v for v in values if isinstance(v, (int, float))]
        if len(values) >= 3:
            hits = sum((v > line if side == 'over' else v < line) for v in values)
            text = f"{hits} of his last {len(values)} games finished {side} {float(line):g} {pricing.WORDS.get(market, '')}."
            item = _item(text, {'values': values, 'hits': hits, 'games': len(values), 'line': line},
                         'ESPN box scores', logs[-1].get('kickoff'))
            (reasons if hits / len(values) >= .6 else risks).append(item)

    for fact in [*(candidate.get('_evidence') or []), *(candidate.get('_research') or [])]:
        if fact.get('verified') is not True or fact.get('direction') not in ('for', 'against') or not fact.get('claim'):
            continue
        text = str(fact['claim']).strip()
        item = _item(text, fact.get('numbers'), fact.get('source'), fact.get('retrievedAt'))
        (reasons if fact['direction'] == 'for' else risks).append(item)
        _source(fact.get('kind') or 'Report', fact.get('source'), fact.get('retrievedAt'), sources)
        if fact.get('kind') in ('injury', 'role', 'availability'):
            reports.append(item)

    for team_side in ('home', 'away'):
        team = game.get(team_side) or {}
        block = ctx.injuries.get(gates.team_key(game['league'], team.get('id'))) or {}
        for player in block.values():
            if str(player.get('status') or '').lower() not in ('out', 'doubtful', 'questionable'):
                continue
            text = f"{player.get('name') or 'Player'} ({team.get('abbreviation') or team.get('name')}) is listed {player['status']}."
            reports.append(_item(text, {'status': player['status']}, player.get('source'), player.get('reportedAt')))
            _source('ESPN injury report', player.get('source'), player.get('reportedAt'), sources)
    if game.get('league') == 'CFB' and not reports:
        reports.append(_item('College injury news is thin; no verified status report is stored.'))

    forecast = (weather_row or {}).get('forecast') or {}
    weather = None
    if forecast:
        weather = {key: forecast.get(key) for key in ('tempF', 'windMph', 'windDirection', 'precipProb',
                                                     'periodStart', 'issuedAt')}
        weather['source'] = forecast.get('source') or (weather_row or {}).get('source')
        _source('National Weather Service', weather['source'], forecast.get('issuedAt'), sources)
        if forecast.get('windMph') is not None and forecast['windMph'] >= 15 and market == 'total':
            item = _item(f"The kickoff forecast calls for {forecast['windMph']} mph wind.",
                         {'windMph': forecast['windMph']}, weather['source'], forecast.get('issuedAt'))
            (reasons if side == 'under' else risks).append(item)

    if candidate.get('risk'):
        risks.append(_item(str(candidate['risk']), source='Published risk note', time=now))
    if not risks:
        risks.append(_item('Roles, prices and game conditions can change before kickoff.'))
    for url in candidate.get('sources') or []:
        _source('Published source', url, now, sources)
    ours = {'projection': projection, 'line': line, 'market': market,
            'text': reasons[0]['text'] if projection is not None and reasons else None,
            'snapshotAt': _stamp(candidate.get('snapshotAt'))}
    return {'reasons': reasons[:3], 'risks': risks[:2], 'reports': reports, 'weather': weather,
            'line': _line_history(candidate, game, captures, now), 'ours': ours,
            'history': (candidate.get('reasoning') or {}).get('history'),
            'sources': list(sources.values()), 'partial': len(reasons) == 0}
