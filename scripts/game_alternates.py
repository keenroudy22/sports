"""Exact full-game alternate spreads from the existing SharpAPI capture.

No synthetic prices or interpolation. Two opposing prices, main-line identity and
monotone ladders are required; malformed, suspended and period markets hold.
"""
import math
from datetime import timedelta
import features
import pricing
import market_periods


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def parse(rows, now):
    groups = {}
    for game, row in rows:
        if not market_periods.full_game(row):
            continue
        if row.get('market_type') != 'point_spread' or row.get('sportsbook') not in ('draftkings', 'fanduel'):
            continue
        if row.get('is_live') is not False or row.get('is_active') is not True:
            continue
        try:
            at = features.when(row['timestamp'])
            if not timedelta(0) <= now-at <= timedelta(minutes=15):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        side = str(row.get('selection_type') or '').lower()
        # Resolve the actual team name, not the provider's possibly reversed home axis.
        import sharp_odds
        names = [s for s in ('home', 'away') if sharp_odds.team_matches(game[s], row.get('selection'))]
        if len(names) != 1 or side not in ('home', 'away'):
            continue
        side = names[0]
        line, price = row.get('line'), row.get('odds_american')
        if not number(line) or not number(price) or int(price) != price or abs(price) < 100:
            continue
        home_line = line if side == 'home' else -line
        group = groups.setdefault((game['id'], row['sportsbook']), {})
        rung = group.setdefault(home_line, {'home': home_line})
        value = (int(price), row.get('is_main_line') is True, row['timestamp'])
        if side+'Quote' in rung and rung[side+'Quote'] != value:
            rung['conflict'] = True
        rung[side+'Quote'] = value
    out = {}
    for (gid, book), group in groups.items():
        pairs = []
        for line, rung in group.items():
            h, a = rung.get('homeQuote'), rung.get('awayQuote')
            if not h or not a or rung.get('conflict'):
                continue
            if not .99 <= pricing.break_even(h[0])+pricing.break_even(a[0]) <= 1.15:
                continue
            pairs.append(dict(home=line, homePrice=h[0], awayPrice=a[0],
                              main=h[1] and a[1], observedAt=min(h[2], a[2])))
        mains = [r for r in pairs if r['main']]
        if len(mains) != 1:
            continue
        main = mains[0]
        valid = []
        for sign in (-1, 1):
            last = main
            for rung in sorted((r for r in pairs if (r['home']-main['home'])*sign > 0),
                               key=lambda r: sign*r['home']):
                if (pricing.break_even(rung['homePrice'])-pricing.break_even(last['homePrice']))*sign < 0 \
                        or (pricing.break_even(rung['awayPrice'])-pricing.break_even(last['awayPrice']))*sign > 0:
                    break
                valid.append(rung)
                last = rung
        if valid:
            out.setdefault(gid, {})[book] = dict(schemaVersion=1, spread=dict(main, alternates=valid))
    return out


def quotes(record):
    for book, data in (record.get('books') or {}).items():
        markets = data.get('gameMarkets') or {}
        if markets.get('schemaVersion') != 1:
            continue
        spread = markets.get('spread') or {}
        if not number(spread.get('home')):
            continue
        for rung in spread.get('alternates') or []:
            line = rung.get('home')
            if not number(line) or line % 1 != .5 or line == spread.get('home'):
                continue
            hp, ap = rung.get('homePrice'), rung.get('awayPrice')
            if not all(number(p) and abs(p) >= 100 for p in (hp, ap)) or not .99 <= pricing.break_even(hp)+pricing.break_even(ap) <= 1.15:
                continue
            for side in ('home', 'away'):
                price = rung.get(side+'Price')
                if number(price) and int(price) == price and -900 <= price <= -180:
                    yield book, side, line if side == 'home' else -line, int(price), rung.get('observedAt'), spread['home']
