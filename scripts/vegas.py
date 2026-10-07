"""Vegas vs reality: how often the closing line was right, by league. No network.

Builds site/data/app/vegas.json at build time from the committed stores only:

  data/boxscores/{nfl,cfb}-*.jsonl   football finals with one book's closing spread, total and moneylines
  data/hoops/{nba,cbb}-*.jsonl       basketball finals with the closing spread and total (no moneylines)
  data/soccer/{epl,mls}.jsonl        soccer finals with decimal 1X2, Asian handicap and 2.5-goal prices

Conventions, checked against known games (see the reference scorecard):
  - every spread and handicap is the HOME line; negative means the home side was favored
  - the last stored line for an event wins, the stores' own revision rule
  - a football or basketball line is invalid when |spread| > 70 or the total is outside the sport's
    plausible range (football 15-120); some early-2023 football rows hold an odds price in the line field
  - rows from a projections service (AccuScore) are not a sportsbook, so their lines are skipped
  - an exact 50/50 no-vig moneyline has no favorite and stays out of the favorite stats
  - a pick'em spread or level-ball handicap has no favorite and stays out of the cover stats, but still
    counts toward the average miss
  - pushes are counted and stay in the cover and over denominators; a tie stays out of the win rate

It describes past games for entertainment. It changes no play, gate or record and is not betting advice.
"""
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
from soccer_model import settle
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
LEAGUES = ('NFL', 'CFB', 'NBA', 'CBB', 'EPL', 'MLS')
NAMES = {'NFL': 'NFL', 'CFB': 'College football', 'NBA': 'NBA', 'CBB': 'College basketball',
         'EPL': 'Premier League', 'MLS': 'MLS'}
IN_SENTENCE = {'CFB': 'college football', 'CBB': 'college basketball'}
SPORT = {'NFL': 'football', 'CFB': 'football', 'NBA': 'basketball', 'CBB': 'basketball',
         'EPL': 'soccer', 'MLS': 'soccer'}
MAX_SPREAD = 70
TOTAL_RANGE = {'football': (15, 120), 'basketball': (90, 320)}
WITHIN = {'football': {'spread': (3, 7), 'total': (3, 7)},
          'basketball': {'spread': (5, 10), 'total': (5, 10)},
          'soccer': {'spread': (1, 2)}}
UNIT = {'football': 'points', 'basketball': 'points', 'soccer': 'goals'}
# Favorite size by the absolute closing line. A quarter-point consensus line falls into the next bin up.
SIZES = {'football': ((3, 'Up to 3'), (7, '3.5 to 7'), (14, '7.5 to 14'), (None, '14.5 or more')),
         'basketball': ((3, 'Up to 3'), (7, '3.5 to 7'), (14, '7.5 to 14'), (None, '14.5 or more')),
         'soccer': ((0.5, '¼ to ½ goal'), (1.0, '¾ to 1 goal'), (1.5, '1¼ to 1½ goals'), (None, '1¾ goals or more'))}
CALIBRATION = {'two-way': ((50, 60), (60, 70), (70, 80), (80, 90), (90, 100)),
               'three-way': ((0, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 100))}
BIG = {'NFL': 14.5, 'CFB': 30, 'NBA': 18, 'CBB': 30, 'EPL': 1.75}
LONGSHOT = 300
BREAK_EVEN_110 = round(100 * 110 / 210, 1)     # the win rate a standard -110 price needs: 52.4%
READ_N = 100                                    # fewer games than this get numbers, not a verdict
SKIP_PROVIDERS = ('accuscore',)
BOOKS = {'espnbet': 'ESPN BET', 'draftkings': 'DraftKings', 'pinnacle': 'Pinnacle', 'average': 'Market average'}


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def mean(values, places=1):
    return round(sum(values) / len(values), places) if values else None


def instant(value):
    try:
        moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def implied(american):
    """The break-even chance of American odds, with the book's cut still in it."""
    return -american / (-american + 100) if american < 0 else 100 / (american + 100)


def american(value):
    value = number(value)
    return value if value is not None and abs(value) >= 100 else None


def decimal(value):
    value = number(value)
    return value if value is not None and value > 1 else None


def book_name(value):
    key = ''.join(ch for ch in str(value or '').lower() if ch.isalnum())
    return BOOKS.get(key, str(value or '').strip() or 'Unnamed book')


def valid_spread(value):
    value = number(value)
    return value if value is not None and abs(value) <= MAX_SPREAD else None


def valid_total(value, sport):
    value = number(value)
    low, high = TOTAL_RANGE[sport]
    return value if value is not None and low <= value <= high else None


def season_label(league, season):
    if SPORT[league] == 'basketball':
        # ESPN names a basketball season by the year it ends: 2024 is 2023-24.
        year = int(season)
        return f'{year - 1}-{str(year)[-2:]}'
    return str(season)


# ---------- one normalized row per final game ----------

def latest_rows(paths, key):
    games = {}
    for path in paths:
        for row in boxscores.read_store(path):
            games[row[key]] = row
    return list(games.values())


def football_row(game):
    home, away = game.get('home') or {}, game.get('away') or {}
    hs, as_ = number(home.get('score')), number(away.get('score'))
    if hs is None or as_ is None:
        return None
    market = game.get('market') or {}
    provider = str(market.get('provider') or '')
    skipped = any(name in provider.lower() for name in SKIP_PROVIDERS)
    close = {} if skipped else (market.get('close') or {})
    raw_spread = number(close.get('spread'))
    raw_total = number(close.get('total'))
    return {'league': game['league'], 'season': game.get('season'), 'kickoff': game.get('kickoff'),
            'home': hs, 'away': as_, 'homeName': home.get('abbreviation'), 'awayName': away.get('abbreviation'),
            'neutral': bool(game.get('neutral')),
            'spread': valid_spread(raw_spread), 'total': valid_total(raw_total, 'football'),
            'badLine': (raw_spread is not None and valid_spread(raw_spread) is None)
            or (raw_total is not None and valid_total(raw_total, 'football') is None),
            'homeML': american(close.get('homeML')), 'awayML': american(close.get('awayML')),
            'source': book_name(provider) if close else None, 'skipped': skipped}


def hoops_row(game):
    hs, as_ = number(game.get('homeScore')), number(game.get('awayScore'))
    if hs is None or as_ is None or game.get('state') not in (None, 'post'):
        return None
    close = game.get('close') or {}
    raw_spread, raw_total = number(close.get('spread')), number(close.get('total'))

    def name(team):
        team = team or {}
        return team.get('school') if game.get('league') == 'CBB' else ' '.join(
            part for part in (team.get('school'), team.get('short')) if part) or team.get('abbreviation')
    books = number(close.get('books'))
    return {'league': game['league'], 'season': game.get('season'), 'kickoff': game.get('kickoff'),
            'home': hs, 'away': as_, 'homeName': name(game.get('home')), 'awayName': name(game.get('away')),
            'neutral': bool(game.get('neutral')),
            'spread': valid_spread(raw_spread), 'total': valid_total(raw_total, 'basketball'),
            'badLine': (raw_spread is not None and valid_spread(raw_spread) is None)
            or (raw_total is not None and valid_total(raw_total, 'basketball') is None),
            'source': None if not close else 'Multi-book consensus' if books and books > 1 else 'One book'}


def soccer_row(game):
    hs, as_ = number(game.get('homeGoals')), number(game.get('awayGoals'))
    if hs is None or as_ is None:
        return None
    close = game.get('close') or {}
    prices = [decimal(close.get(k)) for k in ('home', 'draw', 'away')]
    ah = number(close.get('ahLine'))
    if ah is not None and abs(ah * 4 - round(ah * 4)) > 1e-9:
        ah = None
    over, under = decimal(close.get('over25')), decimal(close.get('under25'))
    books = close.get('books') or {}
    return {'league': game['league'], 'season': game.get('season'), 'kickoff': game.get('kickoff') or game.get('date'),
            'date': game.get('date'), 'home': hs, 'away': as_, 'homeName': game.get('home'),
            'awayName': game.get('away'), 'neutral': False,
            'x12': prices if all(prices) else None, 'ah': ah,
            'ou': (over, under) if over and under else None,
            'source': book_name(books.get('1x2')) if all(prices) else None}


def load(league, root=DATA, football=None):
    """Normalized final games for one league, the last stored line per event."""
    sport = SPORT[league]
    if sport == 'football':
        games = ([g for g in football if g.get('league') == league] if football is not None else
                 latest_rows(sorted((root / 'boxscores').glob(f'{league.lower()}-*.jsonl')), 'eventId'))
        rows = [football_row(g) for g in games]
    elif sport == 'basketball':
        rows = [hoops_row(g) for g in latest_rows(sorted((root / 'hoops').glob(f'{league.lower()}-*.jsonl')), 'eventId')]
    else:
        rows = [soccer_row(g) for g in latest_rows([root / 'soccer' / f'{league.lower()}.jsonl'], 'id')]
    return sorted((r for r in rows if r), key=lambda r: (str(r['kickoff'] or ''), str(r['homeName'] or '')))


# ---------- the measures ----------

def favorite_side(row):
    """The no-vig favorite: ('home' | 'away', chance), or None for a missing price or an exact 50/50."""
    if row.get('x12'):
        home, draw, away = (1 / p for p in row['x12'])
        total = home + draw + away
        if abs(home - away) < 1e-12:
            return None
        return ('home', home / total) if home > away else ('away', away / total)
    if row.get('homeML') is None or row.get('awayML') is None:
        return None
    home, away = implied(row['homeML']), implied(row['awayML'])
    chance = home / (home + away)
    if abs(chance - .5) < 1e-12:
        return None
    return ('home', chance) if chance > .5 else ('away', 1 - chance)


def margin_for(row, side):
    return (row['home'] - row['away']) * (1 if side == 'home' else -1)


def calibration_bins(points, kind):
    out = []
    for low, high in CALIBRATION[kind]:
        # Whole-percent floor with a tiny tolerance, so an exact price (-500/+380 is 80%) lands in the same bin
        # whether the favorite was home or away; the top bin includes 100%.
        inside = [(p, won) for p, won in points
                  if low <= math.floor(100 * p + 1e-9) < high or (high == 100 and math.floor(100 * p + 1e-9) >= 100)]
        if inside:
            out.append({'low': low, 'high': high, 'n': len(inside), 'priced': pct(sum(p for p, _ in inside), len(inside)),
                        'won': pct(sum(1 for _, won in inside if won), len(inside)),
                        'wins': sum(1 for _, won in inside if won)})
    return out


def priced_favorites(rows, three_way):
    """Favorite straight-up record by price, plus the priced-vs-won calibration table."""
    won = lost = tied = 0
    priced, points = [], []
    for row in rows:
        favorite = favorite_side(row)
        if not favorite:
            continue
        margin = margin_for(row, favorite[0])
        if margin == 0:
            tied += 1
            if not three_way:
                continue          # a football tie stays out of the win rate and the table
        elif margin > 0:
            won += 1
        else:
            lost += 1
        priced.append(favorite[1])
        points.append((favorite[1], margin > 0))
    decided = won + lost + (tied if three_way else 0)
    block = {'won': won, 'lost': lost, 'n': won + lost + tied, 'decided': decided,
             'pct': pct(won, decided), 'priced': pct(sum(priced), len(priced))}
    block['drew' if three_way else 'tied'] = tied
    return block, calibration_bins(points, 'three-way' if three_way else 'two-way')


def cover(row, line):
    """('favorite' | 'dog' | 'push', favorite side, straight-up margin) for a non-zero home line."""
    side = 'home' if line < 0 else 'away'
    margin = margin_for(row, side)
    if SPORT[row['league']] == 'soccer':
        won, lost = settle(margin, -abs(line))
        result = 'favorite' if won > 0 else 'dog' if lost > 0 else 'push'
    else:
        edge = margin - abs(line)
        result = 'favorite' if edge > 0 else 'dog' if edge < 0 else 'push'
    return result, side, margin


def spread_block(rows, league):
    sport = SPORT[league]
    key = 'ah' if sport == 'soccer' else 'spread'
    lined = [r for r in rows if r.get(key) is not None]
    if not lined:
        # A league or season with no closing line yet (a new basketball season stores `close: null` until a
        # book posts) still needs the straight-up counter the basketball favorite block reads.
        return None, [], Counter()
    errors = [abs(r['home'] - r['away'] + r[key]) for r in lined]
    counts, sizes = Counter(), []
    su = Counter()
    bins = [dict(label=label, top=top, n=0, won=0, lost=0, tied=0, covered=0, dog=0, push=0)
            for top, label in SIZES[sport]]
    for row in lined:
        line = row[key]
        if line == 0:
            continue
        result, _, margin = cover(row, line)
        counts[result] += 1
        su['won' if margin > 0 else 'lost' if margin < 0 else 'tied'] += 1
        size = abs(line)
        target = next(b for b in bins if b['top'] is None or size <= b['top'] + 1e-9)
        target['n'] += 1
        target['won' if margin > 0 else 'lost' if margin < 0 else 'tied'] += 1
        target['covered' if result == 'favorite' else result] += 1
    n = sum(counts.values())
    for b in bins:
        b.pop('top')
        decided = b['n'] if sport == 'soccer' else b['won'] + b['lost']
        b['wonPct'] = pct(b['won'], decided)
        b['coverPct'] = pct(b['covered'], b['n'])
        if sport == 'soccer':
            b['drew'] = b.pop('tied')
    block = {'n': n, 'favorite': counts['favorite'], 'dog': counts['dog'], 'push': counts['push'],
             'favoritePct': pct(counts['favorite'], n), 'dogPct': pct(counts['dog'], n),
             'pushPct': pct(counts['push'], n), 'missN': len(lined), 'mae': mean(errors), 'unit': UNIT[sport],
             'within': [{'within': w, 'pct': pct(sum(1 for e in errors if e <= w + 1e-9), len(errors))}
                        for w in WITHIN[sport]['spread']]}
    return block, [b for b in bins if b['n']], su


def total_block(rows, league):
    sport = SPORT[league]
    if sport == 'soccer':
        lined = [r for r in rows if r.get('ou')]
        if not lined:
            return None
        over = sum(1 for r in lined if r['home'] + r['away'] > 2.5)
        priced = [(1 / r['ou'][0]) / (1 / r['ou'][0] + 1 / r['ou'][1]) for r in lined]
        return {'n': len(lined), 'over': over, 'under': len(lined) - over, 'push': 0, 'line': 2.5,
                'overPct': pct(over, len(lined)), 'underPct': pct(len(lined) - over, len(lined)), 'pushPct': 0.0,
                'priced': pct(sum(priced), len(priced)), 'mae': None, 'within': [], 'unit': UNIT[sport]}
    lined = [r for r in rows if r.get('total') is not None]
    if not lined:
        return None
    points = [(r['home'] + r['away'], r['total']) for r in lined]
    over = sum(1 for p, t in points if p > t)
    under = sum(1 for p, t in points if p < t)
    push = len(points) - over - under
    errors = [abs(p - t) for p, t in points]
    return {'n': len(points), 'over': over, 'under': under, 'push': push, 'line': None,
            'overPct': pct(over, len(points)), 'underPct': pct(under, len(points)), 'pushPct': pct(push, len(points)),
            'priced': None, 'mae': mean(errors), 'unit': UNIT[sport],
            'within': [{'within': w, 'pct': pct(sum(1 for e in errors if e <= w + 1e-9), len(errors))}
                       for w in WITHIN[sport]['total']]}


def spread_favorites(su):
    decided = su['won'] + su['lost']
    return {'won': su['won'], 'lost': su['lost'], 'tied': su['tied'], 'n': decided + su['tied'],
            'decided': decided, 'pct': pct(su['won'], decided), 'priced': None}


def favorite_block(rows, league, su):
    sport = SPORT[league]
    if sport == 'basketball':
        return {**spread_favorites(su), 'basis': 'spread'}, []
    block, table = priced_favorites(rows, sport == 'soccer')
    return {**block, 'basis': '1x2' if sport == 'soccer' else 'moneyline'}, table


# ---------- plain-words facts, every number computed ----------

def long_date(value):
    moment = instant(value)
    if not moment:
        return str(value)
    day = eastern_date(moment) if 'T' in str(value) else moment.date()
    return f"{day.strftime('%b')} {day.day}, {day.year}"


def number_text(value):
    return f'{value:,}' if isinstance(value, int) else f'{value:g}'


def facts(rows, league, spread_key):
    sport, name, title = SPORT[league], IN_SENTENCE.get(league, NAMES[league]), NAMES[league]
    out = []
    if sport == 'football':
        margins = Counter(abs(r['home'] - r['away']) for r in rows if r['home'] != r['away'])
        if margins:
            top = min(margins.items(), key=lambda item: (-item[1], item[0]))
            out.append(f'{number_text(int(top[0]))} points is the most common {name} final margin: '
                       f'{top[1]:,} of {len(rows):,} games ({pct(top[1], len(rows))}%).')
    big = BIG.get(league)
    if big is not None:
        heavy = [r for r in rows if r.get(spread_key) is not None and r[spread_key] != 0 and abs(r[spread_key]) >= big]
        if heavy:
            results = [cover(r, r[spread_key]) for r in heavy]
            won = sum(1 for _, _, margin in results if margin > 0)
            covered = sum(1 for result, _, _ in results if result == 'favorite')
            unit = 'goals' if sport == 'soccer' else 'points'
            record = f'won all {len(heavy):,}' if won == len(heavy) else f'won {won:,} of {len(heavy):,}'
            out.append(f'{title} favorites of {number_text(big)}+ {unit} {record} straight up, '
                       f'but covered only {covered:,} ({pct(covered, len(heavy))}%).')
    if sport == 'football':
        dogs = []
        for r in rows:
            favorite = favorite_side(r)
            if favorite:
                dog_price = r['awayML'] if favorite[0] == 'home' else r['homeML']
                if dog_price >= LONGSHOT:
                    dogs.append(margin_for(r, favorite[0]) < 0)
        if dogs:
            out.append(f'Underdogs at +{LONGSHOT} or longer won {sum(dogs):,} of {len(dogs):,} {name} games '
                       f'({pct(sum(dogs), len(dogs))}%).')
    if sport == 'basketball':
        upsets = [r for r in rows if r.get('spread') and margin_for(r, 'home' if r['spread'] < 0 else 'away') < 0]
        if upsets:
            r = max(upsets, key=lambda r: (abs(r['spread']), str(r['kickoff'])))
            dog_home = r['spread'] > 0
            dog, fav = (r['homeName'], r['awayName']) if dog_home else (r['awayName'], r['homeName'])
            score = f"{int(max(r['home'], r['away']))}-{int(min(r['home'], r['away']))}"
            place = 'vs' if r['neutral'] or dog_home else 'at'
            out.append(f'Biggest upset in the stored lines: {dog} (+{number_text(abs(r["spread"]))}) won {score} '
                       f'{place} {fav} on {long_date(r["kickoff"])}.')
    if sport == 'soccer':
        priced = [r for r in rows if r.get('x12')]
        if priced:
            draws = sum(1 for r in priced if r['home'] == r['away'])
            chance = sum((1 / r['x12'][1]) / sum(1 / p for p in r['x12']) for r in priced)
            out.append(f'Draws were priced at {pct(chance, len(priced))}% and happened {pct(draws, len(priced))}% '
                       f'of the time ({draws:,} of {len(priced):,}).')
        if league == 'MLS' and priced:
            home = sum(1 for r in priced if r['home'] > r['away'])
            away = sum(1 for r in priced if r['home'] < r['away'])
            out.append(f'Home teams won {pct(home, len(priced))}% of {len(priced):,} games; '
                       f'away teams won {pct(away, len(priced))}%.')
        shocks = []
        for r in priced:
            favorite = favorite_side(r)
            if favorite and margin_for(r, favorite[0]) < 0:
                winner = 0 if r['home'] > r['away'] else 2
                shocks.append(((1 / r['x12'][winner]) / sum(1 / p for p in r['x12']), str(r['kickoff']), r))
        if shocks:
            chance, _, r = min(shocks, key=lambda item: (item[0], item[1]))
            winner, loser = (r['homeName'], r['awayName']) if r['home'] > r['away'] else (r['awayName'], r['homeName'])
            score = f"{int(max(r['home'], r['away']))}-{int(min(r['home'], r['away']))}"
            # The kickoff's Eastern date: an MLS row's `date` is the UK calendar day, often the day after.
            out.append(f'Biggest upset in the stored prices: {winner} beat {loser} {score} on {long_date(r["kickoff"])}. '
                       f'The closing price gave {winner} a {pct(chance, 1)}% chance to win.')
    return out


def games_text(count):
    return f'{count:,} game' + ('' if count == 1 else 's')


def meaning(block, break_even):
    """The plain-words reading of one league, from that league's own numbers only.

    The favorite sentence always gives the actual win rate; the price comparison appears only when the league
    stores a price (never for basketball), and the spread/total sentence only when the league has those lines
    (never for MLS). Words such as "usually" or "coin flip" need at least READ_N games behind them, and "coin
    flip" only when every rate it covers sits between 47% and 53%; a smaller sample gets its numbers only."""
    sport, favorite, spread, total = block['sport'], block['favorite'], block['spread'], block['total']
    out, small = [], False
    rate = favorite.get('pct')
    if rate is not None:
        decided = favorite['decided']
        read = decided >= READ_N
        small = small or not read
        who = {'moneyline': 'closing moneyline favorite', 'spread': 'closing spread favorite'}.get(
            favorite.get('basis'), 'closing favorite')
        how = ('won' if not read else 'usually won:' if rate >= 60 else 'won more often than not:' if rate >= 52 else
               'won about half the time:' if rate >= 48 else 'won less than half the time:')
        draw = ', a draw counting as not won' if sport == 'soccer' else ''
        out.append(f'The {who} {how} {rate}% of {games_text(decided)}{draw}.')
        priced = favorite.get('priced')
        if priced is not None:
            gap = rate - priced
            verdict = ('' if not read else ', close to what happened' if abs(gap) <= 2 else
                       ', so it won more often than its price said' if gap > 0 else
                       ', so it won less often than its price said')
            out.append(f"With the book's cut removed, its closing odds said {priced}%{verdict}.")
    cover = spread if spread and spread['n'] else None
    if sport == 'soccer':
        if cover:
            small = small or cover['n'] < READ_N
            out.append(f'Against the handicap the favorite covered {cover["favoritePct"]}% of {games_text(cover["n"])}, '
                       'a half win counting as a cover.')
        if total:
            small = small or total['n'] < READ_N
            out.append(f'Over 2.5 goals hit {total["overPct"]}% of {games_text(total["n"])}; '
                       f'the closing prices said {total["priced"]}%.')
    else:
        markets, details, samples = [], [], []
        if cover:
            markets.append('against the spread')
            details.append(f'the favorite covered {cover["favoritePct"]}% of {games_text(cover["n"])}')
            samples.append((cover['favoritePct'], cover['n']))
        if total:
            markets.append('on totals')
            details.append(f'the over hit {total["overPct"]}% of {games_text(total["n"])}')
            samples.append((total['overPct'], total['n']))
        if markets:
            small = small or any(n < READ_N for _, n in samples)
            where = ' and '.join(markets)
            where = where[0].upper() + where[1:]
            if all(value is not None and 47 <= value <= 53 and n >= READ_N for value, n in samples):
                out.append(f'{where} it was close to a coin flip: {" and ".join(details)}.')
            else:
                out.append(f'{where}, {", and ".join(details)}.')
            out.append(f'At −110 you need {break_even}% just to break even.')
    if out and small:
        out.append('Some of these samples are small, so read those rates loosely.')
    return ' '.join(out) or None


def notes(rows, league):
    sport = SPORT[league]
    out = []
    bad = sum(1 for r in rows if r.get('badLine'))
    skipped = sum(1 for r in rows if r.get('skipped'))
    if sport == 'football':
        no_ml = sum(1 for r in rows if r.get('homeML') is None or r.get('awayML') is None)
        even = sum(1 for r in rows if r.get('homeML') is not None and r.get('awayML') is not None and not favorite_side(r))
        parts = [f'{bad:,} games whose stored line is really an odds price'] if bad else []
        if skipped:
            parts.append(f'{skipped:,} rows from a projections service, not a sportsbook')
        if even:
            parts.append(f'{even:,} exact 50/50 moneylines (no favorite)')
        if parts:
            out.append('Left out: ' + ', '.join(parts) + '.')
        out.append(f'{no_ml:,} games have no closing moneyline; the spread and total tables still use them '
                   'when their lines are there. A tie stays out of the win rate.')
    elif sport == 'basketball':
        missing = sum(1 for r in rows if r.get('spread') is None)
        out.append('No basketball moneylines are stored, so the favorite is the spread favorite and there is '
                   'no priced-chance table.')
        if missing:
            out.append(f'{missing:,} games with no closing spread are left out of the spread numbers.')
    else:
        with_ah = sum(1 for r in rows if r.get('ah') is not None)
        if with_ah:
            out.append(f'Handicap and total prices are stored for {with_ah:,} games. Quarter-goal handicaps split '
                       'the stake, so a half win counts as a cover and a half loss as a miss.')
            out.append('The 2.5-goal total is a fixed line, not a predicted score, so it has no average miss.')
        else:
            out.append('Only win/draw/loss prices are stored for this league: no handicap or total.')
    out.append('Pushes are rare because most stored lines are half points, which cannot push.'
               if sport != 'soccer' else 'Win rates count draws as games the favorite did not win.')
    return out


def by_season(rows, league):
    groups = defaultdict(list)
    for row in rows:
        groups[row['season']].append(row)
    out = []
    for season in sorted(groups, key=str):
        part = groups[season]
        spread, _, su = spread_block(part, league)
        favorite, _ = favorite_block(part, league, su)
        total = total_block(part, league)
        out.append({'season': season_label(league, season), 'games': len(part),
                    'favorite': {k: favorite[k] for k in ('won', 'decided', 'pct')},
                    'cover': {'favorite': spread['favorite'], 'n': spread['n'], 'pct': spread['favoritePct']}
                    if spread and spread['n'] else None,
                    'over': {'over': total['over'], 'n': total['n'], 'pct': total['overPct']} if total else None})
    return out


def league_block(league, rows):
    if not rows:
        return None
    sport = SPORT[league]
    spread_key = 'ah' if sport == 'soccer' else 'spread'
    spread, sizes, su = spread_block(rows, league)
    favorite, table = favorite_block(rows, league, su)
    seasons = sorted({r['season'] for r in rows}, key=str)
    last = max((r for r in rows if r.get('kickoff')), key=lambda r: instant(r['kickoff']) or datetime.min.replace(
        tzinfo=timezone.utc), default=None)
    through = None
    if last:
        moment = instant(last['kickoff'])
        through = (eastern_date(moment) if 'T' in str(last['kickoff']) else moment.date()).isoformat()
    sources = Counter(r['source'] for r in rows if r.get('source'))
    first_label, last_label = season_label(league, seasons[0]), season_label(league, seasons[-1])
    block = {'league': league, 'name': NAMES[league], 'sport': sport, 'games': len(rows),
            'seasons': {'first': first_label, 'last': last_label, 'count': len(seasons),
                        'label': first_label if len(seasons) == 1 else f'{first_label} to {last_label}'},
            'through': through,
            'sources': [[name, count] for name, count in sorted(sources.items(), key=lambda item: (-item[1], item[0]))],
            'favorite': favorite, 'calibration': table, 'sizes': sizes, 'spread': spread,
            'total': total_block(rows, league), 'bySeason': by_season(rows, league),
            'facts': facts(rows, league, spread_key), 'notes': notes(rows, league)}
    block['meaning'] = meaning(block, BREAK_EVEN_110)
    return block


def compute(league, root=DATA, football=None, through=None):
    """One league's scorecard. `through` keeps games that started at or before that instant."""
    rows = load(league, root, football)
    if through is not None:
        cutoff = instant(through) if isinstance(through, str) else through
        rows = [r for r in rows if r.get('kickoff') and instant(r['kickoff']) and instant(r['kickoff']) <= cutoff]
    return league_block(league, rows)


def build(now=None, root=DATA, football=None):
    now = now or datetime.now(timezone.utc)
    leagues = [block for block in (compute(league, root, football) for league in LEAGUES) if block]
    return {'generatedAt': now.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'label': 'Closing lines', 'breakEven110': BREAK_EVEN_110,
            'leagues': leagues}


if __name__ == '__main__':
    print(json.dumps(build(), indent=1, ensure_ascii=False)[:20000])
