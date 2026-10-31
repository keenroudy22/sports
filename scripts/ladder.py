"""The Kook'n 80/20 Climb: a $50-to-$1,000 bankroll ladder, one rung at a time. Stdlib only.

Current policy (2026-10-21): two to three supported alternate-line legs, preferably two, with combined
ticket odds -200 through -150. Main-line and single-leg examples below describe earlier policies only.

The owner's call (2026-09-26): "50 -> 1000 on 1-2 leg safe bets", with alternate lines. On October 10 the owner
set the rung band to -300 through -200 and asked the automatic builder to consider one or two exact main
moneylines as well as safer player alternates. Every leg still needs model agreement, fresh two-sided pricing and
a saved factual reason before it can post. A person may also supply exact, fresh sportsbook quotes for alternate
spreads or totals; those legs have to clear the same guards. After a win the
ladder banks 20% of the return and rides the other 80% on the next rung. A miss ends that climb but cannot take what
was banked. The climb reaches $1,000 when its bank plus the next stake reaches the goal; the next rung then starts a
new climb at $50. Money is whole dollars: a rung pays round(stake x the ticket's decimal price), the bank gets
round(return x 20%), and the remainder rides.

Like the easy parlay, a rung is never called value. Our player chances are tuned against main lines (and learning
found them too confident even there), so easier-line probabilities are anchored to the sportsbook price and are
never presented as raw model certainty. The market's own price carries most of the safety; our number has to agree
with room to spare. A player needs five current-season appearances, or an established same-team role from last
season. A quarterback passing leg needs five actual starts for that team unless that same-team role is established.

The ladder's state is never stored. state() reads it from the published rungs and their results, so it can not
drift from the record. One rung is open at a time. After it settles, the next scheduled scan may publish another
qualifying rung—including a new $50 climb after a loss—but a rung is never forced. A rung pulled before its post
still counts and is not replaced. A rung with a void leg is settled by a person
(run.settle reports it), and the ladder waits for that.

Prices: SharpAPI's DraftKings and FanDuel alternate player lines in data/prop-odds (scripts/sharp_odds.py), no
credits. NFL legs now; college legs (legal pregame in Indiana, gates.INDIANA_BOOKS) once learning has calibrated
college player numbers, as for college props. A rung is built only from prices read within FRESH. The ladder is kept apart from the record, in dollars, on the site and on X.

  python scripts/ladder.py [--now ISO]      where the ladder stands, and the rung the desk would build now
"""
import argparse
import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import easy_parlay
import gates
import parlay
import pricing
import role_sanity
import sharp_odds
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
START, GOAL = 50, 1000              # dollars
BANK_RATE = 0.20                    # "Bank 20. Ride 80." (owner, 2026-09-28)
BOOKS = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}
SLUGS = {'DraftKings': 'dk', 'FanDuel': 'fd'}
MARKETS = ('recYds', 'rushYds', 'rec', 'passYds')     # lines a follower reads at a glance
LEG_PRICES = (-900, -180)           # safer favored legs; two around -400 is the preferred shape
RAW_MIN_CHANCE = 0.85               # the uncalibrated projection still has to clear the easier line comfortably
MIN_CHANCE = 0.83                   # conservative, market-anchored chance used to compare eligible legs
MODEL_LIFT_CAP = 0.06               # an alternate-line model cannot claim more than six points above its price
MIN_GAP = 0.04                      # safety comes from the price; our number still has to agree
MAX_GAP = 0.18                      # and no further: a book that far off an easy line is a data or role problem, not a gift
MAIN_RATIO = (0.6, 1.6)             # the book's main line against our projection: outside this, the market is another one
TARGET = (-200, -150)               # combined ticket, not each leg (owner, 2026-10-21)
LEGACY_TARGET = (-220, -130)        # explicit historical replays only
MANUAL_RAW_CHANCE = 0.72             # exact game alternates: the unshrunk model must still agree comfortably
MONEYLINE_MIN_CHANCE = 0.70         # strong-favorite floor; the exact two-sided market still anchors the check
MONEYLINE_MIN_GAP = 0.03            # our win estimate must clear the book's fair chance by three points
MONEYLINE_PAIR_BAND = (0.99, 1.15)  # broken or mismatched two-sided captures never become a rung
LEAD = timedelta(minutes=15)        # a late admission still needs a real pre-kickoff posting window
FRESH = timedelta(hours=12)         # prices older than this are not used
GAME_FRESH = timedelta(hours=2)     # main moneylines are re-read on game day before admission
RELEASE_QUOTE_FRESH = timedelta(hours=2)  # the morning Discord release must still be inside the verified quote age
STAKE = parlay.STAKE                # the ticket's size in the desk's own terms; the ladder itself counts dollars
SOURCE = 'https://sharpapi.io/'
SHADOW_NAME = 'ladder-shadow-2026.jsonl'
SELECTIVE_FROM = date(2026, 10, 21)
ALT_SHAPE_FROM = date(2026, 10, 21)
MIN_LEGS = 2
MAX_LEGS = 3
MAX_WEEKLY_STEPS = 3


def shape_policy(now=None):
    """Current admission shape; explicit historical replays retain their old envelope."""
    current = eastern_date(now or datetime.now(timezone.utc)) >= ALT_SHAPE_FROM
    return (MIN_LEGS if current else 1, TARGET if current else LEGACY_TARGET, current)


def shape_refusal(ticket, now=None):
    minimum, target, alternates = shape_policy(now)
    legs = ticket.get('legs')
    words = 'two to three alternate' if alternates else 'one to three'
    if not isinstance(legs, list) or not minimum <= len(legs) <= MAX_LEGS or any(not isinstance(l, dict) for l in legs):
        return f'Climb ticket needs {words} valid legs'
    if alternates and any(l.get('alternate') is not True for l in legs):
        return 'Climb needs actual alternate lines, not a main line relabeled as an alternate'
    price = ticket.get('odds')
    if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or not target[0] <= price <= target[1]:
        return f'Climb combined ticket must be priced {target[0]:+d} to {target[1]:+d}'
    return None


def weekly_status(first, now, exclude=None):
    """Count admissions/publications once, across restarts, in the Eastern Monday-Sunday week.

    Private reservations merged by release_queue also count while pending. They disappear
    when an unreleased admission expires; already public rows never disappear with a loss.
    """
    today = eastern_date(now)
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=7)
    ids = []
    for key, pick in first.items():
        if key == exclude or pick.get('parlayType') != 'ladder':
            continue
        try:
            published = gates.when(pick['publishedAt'])
        except (KeyError, TypeError, ValueError):
            continue
        if published <= now and start <= eastern_date(published) < end:
            ids.append(key)
    return {'weekStart': start.isoformat(), 'weekEnd': (end-timedelta(days=1)).isoformat(),
            'posted': len(ids), 'remaining': max(0, MAX_WEEKLY_STEPS-len(ids)),
            'maximum': MAX_WEEKLY_STEPS, 'maxLegs': MAX_LEGS, 'ids': sorted(ids)}


def weekly_refusal(ctx, now):
    if eastern_date(now) < SELECTIVE_FROM:
        return None
    week = weekly_status(ctx.first, now)
    if week['posted'] >= MAX_WEEKLY_STEPS:
        return f"weekly Climb limit reached: {week['posted']}/{MAX_WEEKLY_STEPS} steps since {week['weekStart']}; restarts do not reset it"
    return None


def ticket_rank(chance, edge, chosen, price):
    """Prefer conservative joint chance, then fewer legs; never alter a model or price gate."""
    return (round(chance, 4), -len(chosen), round(edge, 4), price)


def support_refusal(ticket, ctx):
    """Recheck saved conservative support at admission/release; operator tickets cannot bypass it."""
    if ticket.get('selectionMethod') == 'sourced-climb-review-v1':
        import climb_review
        return climb_review.refusal(ticket, ctx)
    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    legs = ticket.get('legs')
    refusal = shape_refusal(ticket, getattr(ctx, 'now', None))
    if refusal:
        return refusal
    product, dec = 1.0, 1.0
    for leg in legs:
        price, raw, chance = leg.get('odds'), leg.get('rawChance'), leg.get('chance')
        if not all(number(value) for value in (price, raw, chance)) or not LEG_PRICES[0] <= price <= LEG_PRICES[1] or not 0 < raw < 1 or not 0 < chance < 1:
            return 'Climb leg needs a supported price and valid saved probability inputs'
        implied = pricing.break_even(price)
        market = leg.get('marketType') or leg.get('market')
        league = ((getattr(ctx, 'games', {}) or {}).get(leg.get('gameId')) or {}).get('league')
        if market == 'moneyline':
            fair = leg.get('fairChance')
            if not number(fair) or not 0 < fair < 1 or raw < MONEYLINE_MIN_CHANCE or not MONEYLINE_MIN_GAP-.0005 <= raw-fair <= MAX_GAP+.0005:
                return 'Climb moneyline needs its saved two-sided fair chance and model support'
            allowed = used_chance(raw, fair, moneyline=True)
        else:
            floor = RAW_MIN_CHANCE if leg.get('athleteId') else MANUAL_RAW_CHANCE
            rate = segment_hit_rate(ctx, league, market, leg.get('book'), int(price), leg.get('direction'))
            allowed = used_chance(raw, implied, rate)
            if raw < floor or allowed is None:
                return 'Climb leg lacks the required model support or open proven segment; discretionary tickets cannot bypass this'
        if chance > allowed+.0005 or chance <= implied:
            return 'Climb leg does not beat its price within its conservative probability cap'
        product *= chance
        dec *= parlay.decimal(price)
    odds = ticket.get('odds')
    if not number(odds) or abs(parlay.american(dec)-odds)>1:
        return 'Climb ticket price must match its captured same-book legs and target band'
    if product <= pricing.break_even(odds):
        return 'Climb ticket does not beat its price after conservative joint support'
    return None


def v3_enabled():
    return os.getenv('KEENROUDY_CLIMB_V3', '1').strip().lower() not in ('0', 'false', 'off', 'no')


def used_chance(raw, fair, segment_hit=None, moneyline=False):
    """The probability allowed to rank a Climb leg, never the raw model claim.

    Moneylines may use at most six points above the two-sided fair market. Other markets need a proven stored
    segment and may use no more than that segment's observed hit rate.
    """
    if not all(isinstance(value, (int, float)) for value in (raw, fair)):
        return None
    if moneyline:
        return min(float(raw), float(fair) + MODEL_LIFT_CAP)
    if not isinstance(segment_hit, (int, float)):
        return None
    return min(float(raw), float(segment_hit))


def segment_hit_rate(ctx, league, market, book, price, side=None):
    """Read the weekly proven-segment result; this function never promotes a segment itself."""
    band = f'{abs(int(price)) // 50 * 50}-{abs(int(price)) // 50 * 50 + 49}'
    keys = (f'{league}/{market}/{book}/{band}', f'{league}/{market}/{book}', f'{league}/{market}')
    segments = ((getattr(ctx, 'policy', None) or {}).get('ladderSegments') or {})
    now = getattr(ctx, 'now', None)
    if now is None or eastern_date(now) >= date(2026, 10, 21):
        import climb_validation
        row = segments.get(climb_validation.segment_key(league, market, side, book, price))
        if not isinstance(row, dict) or row.get('schemaVersion') != 2 or row.get('scope') != 'alternate-offers':
            return None
        try:
            age = now-gates.when(row['checkedAt']) if now else timedelta(days=99)
            if not timedelta(0) <= age <= timedelta(days=8):
                return None
            if row.get('open') is True and row['graded'] >= 150 and 0 < row['hitRate'] <= 1 \
                    and row['hitRate']-row['priceNeeded'] >= .02-1e-12 and row['last100AbovePrice'] >= -1e-12:
                return float(row['hitRate'])
        except (KeyError, TypeError, ValueError):
            return None
        return None
    for key in keys:
        row = segments.get(key)
        if isinstance(row, dict) and row.get('open') is True and (row.get('graded') or 0) >= 150 \
                and isinstance(row.get('hitRate'), (int, float)):
            return float(row['hitRate'])
    return None


def shadow_path(ctx):
    return Path(getattr(ctx, 'root', ROOT)) / 'work' / SHADOW_NAME


def record_shadow(ctx, now, ticket=None, blocked=None, path=None):
    """Private append-only evidence for every Climb check. Public records and cards never read this file."""
    path = Path(path or shadow_path(ctx))
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {'checkedAt': gates.stamp(now), 'status': 'candidate' if ticket and not blocked else 'blocked',
           'blockedBy': blocked, 'result': None}
    if ticket:
        chance = ticket.get('chance')
        reviewed = ticket.get('selectionMethod') == 'sourced-climb-review-v1'
        if reviewed:
            chance = None
        elif not isinstance(chance, (int, float)):
            chance = 1.0
            for leg in ticket.get('legs') or []:
                chance *= float(leg.get('chance') or 0)
        row['ticket'] = {'id': ticket.get('id'), 'book': ticket.get('book'), 'odds': ticket.get('odds'),
                         'selectionMethod': ticket.get('selectionMethod'),
                         'chance': round(chance, 4) if chance is not None else None,
                         'priceNeeded': round(pricing.break_even(ticket['odds']), 4),
                         'edge': round(chance - pricing.break_even(ticket['odds']), 4) if chance is not None else None,
                         'legs': [{'id': leg.get('id'), 'gameId': leg.get('gameId'), 'chance': leg.get('chance'),
                                   'odds': leg.get('odds')} for leg in ticket.get('legs') or []]}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n')
    return row


def stable_role(ctx, athlete, team, league, stat):
    """Ladder roles need more evidence than an ordinary research row.

    Five appearances keeps three-game hot starts and newly promoted roles out. Passing yards additionally require
    five games as that team's primary passer; relief appearances are not a quarterback workload sample. An
    established same-team role from the prior season remains eligible early in a new season.
    """
    athlete, team = str(athlete), str(team)
    established = (athlete, team) in (getattr(ctx, 'established', set()) or set())
    if not established and (getattr(ctx, 'appearances', {}).get(athlete, 0) or 0) < 5:
        return False
    if stat != 'passYds' or established:
        return True
    starts = (getattr(ctx, 'passers', {}) or {}).get(gates.team_key(league, team), [])
    return sum(str(starter) == athlete for starter in starts) >= 5


def rungs(first, latest):
    """Every published rung, oldest first, merged with its latest revision."""
    out = [dict(pick, **latest.get(key, {})) for key, pick in first.items() if pick.get('parlayType') == 'ladder']
    return sorted(out, key=lambda p: (str(p.get('publishedAt') or ''), str(p.get('id'))))


def played(rung):
    """A rung that counts: graded, still open, or pulled before its post. The owner counts every published ladder
    decision (2026-09-28), so a pulled ungraded rung stays open and blocks the next one until its result."""
    if rung.get('result'):
        return True
    if 'before its post went out' in str(rung.get('entryNote') or '') or str(rung.get('entryNote') or '').startswith('Pulled before posting:'):
        return True
    return not rung.get('entryNote') and (rung.get('status') or 'active') == 'active'


def state(first, latest):
    """Where the ladder stands, from the rungs themselves:
    {'run', 'step', 'stake', 'banked', 'saved', 'open', 'history', 'climbs', 'start', 'goal'}.

    A win banks 20% of its return and rides 80%; reaching the goal with the bank plus the next stake finishes the
    climb. A loss starts a new climb at START while the already saved money stays saved; a push or void keeps the
    stake, bank and step."""
    run, step, stake, banked, saved, open_rung = 1, 1, START, 0, 0, None
    history, climbs = [], []
    wagered = returned_total = wins = losses = pushes = voids = 0
    for rung in rungs(first, latest):
        if not played(rung):
            continue
        info = rung.get('ladder') or {}
        result = rung.get('result')
        if not result:
            open_rung = rung
            continue
        rung_stake = int(info.get('stake') or stake)
        wagered += rung_stake
        item = {'id': rung['id'], 'run': info.get('run'), 'step': info.get('step'), 'stake': info.get('stake'),
                'payout': info.get('payout'), 'odds': rung.get('odds'), 'result': result,
                'settledAt': rung.get('settledAt')}
        if result == 'win':
            returned = int(info.get('payout') or stake)
            returned_total += returned
            wins += 1
            before = int(info.get('banked') if info.get('banked') is not None else banked)
            cut, next_stake = split_return(returned)
            after = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else before + cut)
            next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else next_stake)
            saved += max(0, after - before)
            banked, stake, step = after, next_stake, step + 1
            item.update({'banked': before, 'bankedAfter': after, 'nextStake': next_stake})
            if banked + stake >= GOAL:
                climbs.append({'run': run, 'steps': int(info.get('step') or step - 1), 'final': banked + stake,
                               'banked': banked, 'id': rung['id']})
                run, step, stake, banked = run + 1, 1, START, 0
        elif result == 'loss':
            losses += 1
            run, step, stake, banked = run + 1, 1, START, 0
        elif result == 'push':
            returned_total += rung_stake
            pushes += 1
        elif result == 'void':
            returned_total += rung_stake
            voids += 1
        item['ladderTotal'] = {'wagered': wagered, 'returned': returned_total,
                               'net': returned_total - wagered}
        history.append(item)
    accounting = {'wagered': wagered, 'returned': returned_total, 'net': returned_total - wagered,
                  'atRisk': int((open_rung.get('ladder') or {}).get('stake') or stake) if open_rung else 0,
                  'wins': wins, 'losses': losses, 'pushes': pushes, 'voids': voids}
    return {'run': run, 'step': step, 'stake': stake, 'open': open_rung, 'history': history, 'climbs': climbs,
            'banked': banked, 'saved': saved, 'bankPercent': int(BANK_RATE * 100),
            'ridePercent': 100 - int(BANK_RATE * 100), 'start': START, 'goal': GOAL,
            'accounting': accounting}


def saved_through(first, latest, target):
    """Lifetime protected dollars immediately after one rung, for immutable result artwork."""
    saved = 0
    for rung in rungs(first, latest):
        if not played(rung):
            continue
        info = rung.get('ladder') or {}
        if rung.get('result') == 'win':
            before = int(info.get('banked') or 0)
            if info.get('bankedAfter') is not None:
                after = int(info['bankedAfter'])
            else:
                # Early rungs predate the explicit bank fields. Reconstruct the same
                # whole-dollar 80/20 split used by state() so immutable result art and
                # the live feed retain the lifetime bank from those wins.
                cut, _ = split_return(info.get('payout') or info.get('stake') or 0)
                after = before + cut
            saved += max(0, after - before)
        if rung.get('id') == target:
            break
    return saved


def payout(stake, odds):
    return int(round(stake * parlay.decimal(odds)))


def split_return(returned):
    """Whole-dollar 80/20 split: bank 20% of the return and ride the remainder."""
    returned = int(returned)
    bank = int(round(returned * BANK_RATE))
    return bank, returned - bank


def todays_games(games, now, league, exclude=()):
    """The league's games today (Eastern), far enough from kickoff to post a rung before them."""
    day = eastern_date(now)
    return [g for g in games.values() if g.get('league') == league and g.get('state', 'pre') == 'pre' and g['id'] not in set(exclude)
            and eastern_date(gates.when(g['kickoff'])) == day and gates.when(g['kickoff']) > now + LEAD]


def kickoff_windows(games):
    """The one-league game-day pool, ordered by kickoff.

    A rung may combine eligible legs from any games on that Eastern game day.  The open-rung gate prevents a new
    step until every leg has settled, so kickoff proximity is not a safety rule (owner, 2026-10-11).
    """
    ordered = sorted(games, key=lambda game: (gates.when(game['kickoff']), game['id']))
    return [ordered] if ordered else []


def confirmed_at(root=None):
    """gameId -> when the prop feed last read the game's numbers, changed or not (data/prop-odds/sharp-status.json)."""
    path = Path(root or Path(__file__).resolve().parents[1]) / 'data' / 'prop-odds' / 'sharp-status.json'
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('confirmed') or {}
    except (OSError, ValueError):
        return {}


def legs_for_game(game, record, ctx, now, confirmed=None, proven=False):
    """Every easier line in this game our projection clears comfortably, at a price worth a rung, from each book. The
    prices are as of the last time the feed read them (`confirmed`), or when they were stored."""
    snapshot = ctx.snapshot(game['id'])
    if not snapshot or not record:
        return []
    seen = max([record['retrievedAt']] + [at for at in [(confirmed or {}).get(game['id'])] if at and gates.when(at) <= now],
               key=gates.when)
    if now - gates.when(seen) > FRESH:
        return []
    ids = [p['id'] for side in ('home', 'away') for p in ((snapshot.get('players') or {}).get(side) or {}).get('players', [])]
    by_name = {easy_parlay.name_key(ctx.names.get(str(i))): str(i) for i in ids if ctx.names.get(str(i))}
    out = []
    for book_key, book in (record.get('books') or {}).items():
        if book_key not in BOOKS:
            continue
        for stat, players in (book.get('markets') or {}).items():
            if stat not in MARKETS:
                continue
            for name, quote in (players or {}).items():
                athlete = by_name.get(easy_parlay.name_key(name))
                side, player = pricing.player_line(snapshot, athlete) if athlete else (None, None)
                projected = (player or {}).get(pricing.PROJECTED[stat])
                if not projected or player.get('limited') or not side:
                    continue
                if role_sanity.assess(player, getattr(ctx, 'player_logs', {}).get(str(athlete)),
                                      game[side]['id'], stat, game.get('season')):
                    continue
                if not stable_role(ctx, athlete, game[side]['id'], game['league'], stat):
                    continue
                if gates.listed_status(athlete, str(game[side]['id']), ctx) in gates.LISTED:
                    continue
                mean, low, high = projected
                sd = (high - mean) / pricing.Z80
                main = quote.get('line')
                if sd <= 0 or not isinstance(main, (int, float)) or not MAIN_RATIO[0] <= main / max(mean, 1.0) <= MAIN_RATIO[1]:
                    continue
                # Only the main line's own ladder: the feed files some period ladders under the full-game market.
                rungs = [quote] + sharp_odds.consistent(quote)
                offers = [(rung['line'], rung.get(direction), direction) for rung in rungs
                          for direction in ('over', 'under')]
                for point, price, direction in offers:
                    if not isinstance(point, (int, float)) or not isinstance(price, (int, float)):
                        continue
                    price = int(price)
                    if not LEG_PRICES[0] <= price <= LEG_PRICES[1] or float(point) != int(point) + 0.5:
                        continue            # a half point, so the leg can not push
                    above, _, below = pricing.chances(mean, sd, float(point))
                    raw = above if direction == 'over' else below
                    implied = pricing.break_even(price)
                    if raw < RAW_MIN_CHANCE or not MIN_GAP <= raw - implied <= MAX_GAP:
                        continue
                    segment_rate = segment_hit_rate(ctx, game['league'], stat, BOOKS[book_key], price, direction) if proven else None
                    chance = used_chance(raw, implied, segment_rate) if proven else min(raw, implied + MODEL_LIFT_CAP)
                    if chance is None or chance <= implied:
                        continue
                    shown = ctx.names.get(athlete) or name
                    title = (f"{shown} {int(point + 0.5)}+ {pricing.WORDS[stat]}" if direction == 'over'
                             else f"{shown} under {float(point):g} {pricing.WORDS[stat]}")
                    out.append({'id': f"ladder-{game['id']}-{athlete}-{stat}-{float(point):g}" + ('-under' if direction == 'under' else ''),
                                'title': title,
                                'gameId': game['id'], 'athleteId': athlete, 'player': shown, 'market': stat, 'direction': direction,
                                'line': float(point), 'book': BOOKS[book_key], 'odds': price,
                                'chance': round(chance, 3), 'rawChance': round(raw, 3),
                                'implied': round(implied, 3), 'projection': round(mean, 1), 'kickoff': game['kickoff'],
                                'observedAt': seen, 'marketWindow': 'Full game',
                                'alternate': float(point) != float(main)})
    return out


def game_line_legs(game, ctx, now):
    """Exact captured main spreads/totals. No invented game alternates or extra feed requests."""
    record = (getattr(ctx, 'odds', {}) or {}).get(game['id']) or {}
    snapshot = ctx.snapshot(game['id'])
    if not record or not snapshot:
        return []
    out = []
    for key, book in (record.get('books') or {}).items():
        if key not in BOOKS:
            continue
        observed = book.get('updatedAt') or record.get('retrievedAt')
        try:
            if not timedelta(0) <= now - gates.when(observed) <= GAME_FRESH:
                continue
        except (TypeError, ValueError):
            continue
        spread, total = book.get('spread') or {}, book.get('total') or {}
        options = [('spread', 'home', spread.get('home'), spread.get('homePrice')),
                   ('spread', 'away', -spread['home'] if isinstance(spread.get('home'), (int, float)) else None, spread.get('awayPrice')),
                   ('total', 'over', total.get('line'), total.get('over')),
                   ('total', 'under', total.get('line'), total.get('under'))]
        for market, side, line, price in options:
            if not isinstance(line, (int, float)) or not isinstance(price, (int, float)) or isinstance(line, bool) or isinstance(price, bool):
                continue
            if line % 1 != .5 or not LEG_PRICES[0] <= price <= LEG_PRICES[1]:
                continue
            try:
                desk = pricing.price(snapshot, market, side, line, int(price))
            except (KeyError, TypeError, ValueError):
                continue
            rate = segment_hit_rate(ctx, game['league'], market, BOOKS[key], int(price), side)
            chance = used_chance(desk['rawChance'], desk['breakEven'], rate)
            if desk['rawChance'] < MANUAL_RAW_CHANCE or chance is None or chance <= desk['breakEven']:
                continue
            label = (f"{game[side]['short']} {pricing.signed(line)}" if market == 'spread' else
                     f"{game['away']['short']} at {game['home']['short']} {side} {line:g}")
            out.append({'id': f"ladder-{game['id']}-{market}-{side}-{line:g}", 'title': label,
                        'gameId': game['id'], 'marketType': market, 'direction': side, 'line': line,
                        'book': BOOKS[key], 'odds': int(price), 'chance': round(chance, 3),
                        'rawChance': round(desk['rawChance'], 3), 'segmentHitRate': rate,
                        'implied': desk['breakEven'], 'projection': desk['projection'],
                        'kickoff': game['kickoff'], 'observedAt': observed,
                        'marketWindow': 'Full game', 'alternate': False})
    return out


def alternate_spread_legs(game, ctx, now):
    """Captured full-game two-sided alternates; same support gates as manual legs."""
    import game_alternates
    record = (getattr(ctx, 'prop_odds', {}) or {}).get(game['id']) or {}
    snapshot = ctx.snapshot(game['id'])
    if not snapshot:
        return []
    out = []
    for key, side, line, price, observed, _ in game_alternates.quotes(record):
        if key not in BOOKS or not LEG_PRICES[0] <= price <= LEG_PRICES[1]:
            continue
        try:
            if not timedelta(0) <= now-gates.when(observed) <= GAME_FRESH:
                continue
            desk = pricing.price(snapshot, 'spread', side, line, price)
        except (KeyError, TypeError, ValueError):
            continue
        rate = segment_hit_rate(ctx, game['league'], 'spread', BOOKS[key], price, side)
        chance = used_chance(desk['rawChance'], desk['breakEven'], rate)
        if desk['rawChance'] < MANUAL_RAW_CHANCE or chance is None or chance <= desk['breakEven']:
            continue
        out.append(dict(id=f"ladder-{game['id']}-spread-{side}-{line:g}",
            title=f"{game[side]['short']} {pricing.signed(line)}", gameId=game['id'],
            marketType='spread', direction=side, line=line, book=BOOKS[key], odds=price,
            chance=round(chance,3), rawChance=round(desk['rawChance'],3), segmentHitRate=rate,
            implied=desk['breakEven'], projection=desk['projection'], kickoff=game['kickoff'],
            observedAt=observed, marketWindow='Full game', alternate=True))
    return out


def moneyline_legs(game, ctx, now):
    """A fresh exact favorite moneyline whose two-sided price and our winner estimate agree.

    ESPN supplies the current DraftKings pair without an added paid request.  The fair chance is computed from
    both sides at that same book; a one-sided, stale or abnormal pair is unusable.  The stored model may support
    the market, but the run still requires a separate saved factual reason before publishing the rung.
    """
    snapshot = ctx.snapshot(game['id'])
    market = game.get('market') or {}
    observed = game.get('marketRetrievedAt')
    if not snapshot or not observed:
        return []
    try:
        age = now - gates.when(observed)
    except (TypeError, ValueError):
        return []
    if not timedelta(minutes=-1) <= age <= GAME_FRESH:
        return []
    provider = str(market.get('provider') or '').strip()
    provider = build_site.BOOKS.get(provider, provider)
    book = next((name for name in SLUGS if name.lower() == provider.lower()), None)
    if not book:
        return []
    home, away = build_site.american(market.get('homeML')), build_site.american(market.get('awayML'))
    if home is None or away is None:
        return []
    total = pricing.break_even(home) + pricing.break_even(away)
    if not MONEYLINE_PAIR_BAND[0] <= total <= MONEYLINE_PAIR_BAND[1]:
        return []
    out = []
    for side, price, other in (('home', home, away), ('away', away, home)):
        if not LEG_PRICES[0] <= price <= LEG_PRICES[1]:
            continue
        try:
            raw = pricing.price(snapshot, 'moneyline', side, 0, price)['rawChance']
            fair = pricing.fair_chance(price, other)
        except (KeyError, TypeError, ValueError):
            continue
        gap = raw - fair
        if raw < MONEYLINE_MIN_CHANCE or not MONEYLINE_MIN_GAP <= gap <= MAX_GAP:
            continue
        chance = used_chance(raw, fair, moneyline=True)
        team = game[side]
        out.append({'id': f"ladder-{game['id']}-moneyline-{side}",
                    'title': f"{team.get('short') or team.get('abbreviation')} moneyline",
                    'gameId': game['id'], 'marketType': 'moneyline', 'direction': side, 'line': 0,
                    'team': str(team.get('id') or ''), 'book': book, 'odds': int(price),
                    'chance': round(chance, 3), 'rawChance': round(raw, 3),
                    'fairChance': round(fair, 3), 'implied': round(pricing.break_even(price), 3),
                    'projection': round(raw, 3), 'kickoff': game['kickoff'], 'observedAt': observed,
                    'marketWindow': 'Full game', 'alternate': False})
    return out


def strict_legs(legs, policy, now, league):
    """The stricter Climb pool (direction rules, owner 2026-10-07): only the legs whose segment is neither paused nor
    carrying a raised edge bar (`direction.flagged`). The leg chance, leg prices and TARGET are unchanged, so it can
    only remove legs, never add or loosen one, and it lets a segment back in as soon as its own flag clears."""
    import direction
    return [leg for leg in legs if not direction.flagged(policy, direction.leg_segment(leg, league), now)]


def pairs(legs, now=None):
    """Every eligible rung: (book, leg, leg, decimal, price) for two legs from different games at one book whose
    price multiplies inside TARGET."""
    for book, chosen, dec, price in tickets(legs, now):
        if len(chosen) == 2:
            yield book, chosen[0], chosen[1], dec, price


def tickets(legs, now=None):
    """Two to three actual alternates, one book, one leg per game, at the combined target."""
    minimum, target, alternates = shape_policy(now)
    for book in sorted({leg['book'] for leg in legs}):
        mine = [leg for leg in legs if leg['book'] == book and (not alternates or leg.get('alternate') is True)]
        for count in range(minimum, MAX_LEGS+1):
            for chosen in combinations(mine, count):
                if len({leg['gameId'] for leg in chosen}) != count:
                    continue
                dec = 1.0
                for leg in chosen:
                    dec *= parlay.decimal(leg['odds'])
                price = parlay.american(dec)
                if target[0] <= price <= target[1]:
                    yield book, chosen, dec, price


def near_misses(legs, limit=3, now=None):
    """Closest positive-edge tickets outside the rung band, for private/run diagnostics only."""
    rows = []
    minimum, target, alternates = shape_policy(now)
    for book in sorted({leg['book'] for leg in legs}):
        mine = [leg for leg in legs if leg['book'] == book and (not alternates or leg.get('alternate') is True)]
        shapes = [(leg,) for leg in mine] if minimum == 1 else []
        shapes += [(a, b) for a, b in combinations(mine, 2) if a['gameId'] != b['gameId']]
        shapes += [chosen for chosen in combinations(mine, 3) if len({leg['gameId'] for leg in chosen}) == 3]
        for chosen in shapes:
            dec = 1.0
            chance = 1.0
            for leg in chosen:
                dec *= parlay.decimal(leg['odds'])
                chance *= leg['chance']
            price = parlay.american(dec)
            edge = chance - pricing.break_even(price)
            if edge <= 0 or target[0] <= price <= target[1]:
                continue
            distance = target[0] - price if price < target[0] else price - target[1]
            rows.append((distance, -edge, -chance, book, price, round(chance, 4), chosen))
    out = []
    for _, neg_edge, _, book, price, chance, chosen in sorted(rows, key=lambda row: row[:3])[:limit]:
        out.append({'book': book, 'odds': price, 'chance': chance, 'edge': round(-neg_edge, 4),
                    'legs': [leg.get('title') for leg in chosen]})
    return out


def near_miss(legs):
    """Backward-compatible single best near miss."""
    rows = near_misses(legs, 1)
    return rows[0] if rows else None


def build(legs, now=None):
    """The highest conservative joint chance among supported alternate tickets.

    Rank by conservative joint chance, then fewer legs and price edge. A positive joint
    edge is still required; neither a larger raw model gap nor more legs is a safety claim.
    """
    if not legs:
        return None, 'zero supported legs cleared the role, price and proven-segment gates'
    best = None
    for book, chosen, dec, price in tickets(legs, now):
        chance = 1.0
        for leg in chosen:
            chance *= leg['chance']
        chance = round(chance, 4)
        edge = round(chance - pricing.break_even(price), 4)
        if edge <= 0:
            continue
        key = ticket_rank(chance, edge, chosen, price)
        if best is None or key > best[0]:
            selected = sorted(chosen, key=lambda l: (l['kickoff'], l['title']))
            best = (key, {'book': book, 'legs': selected, 'odds': price, 'decimal': round(dec, 3),
                          'gameIds': [l['gameId'] for l in selected],
                          'quotedAt': min(l['observedAt'] for l in selected),
                          'firstKickoff': min(l['kickoff'] for l in selected), 'chance': chance})
    if not best:
        near = near_misses(legs, now=now)
        detail = ('; near misses ' + ' | '.join(
            f"{row['book']} {row['odds']:+d} ({', '.join(row['legs'])}), "
            f"{100 * row['edge']:.1f} points above its price" for row in near)) if near else ''
        minimum, target, alternates = shape_policy(now)
        words = 'two to three supported alternate legs' if alternates else 'one to three supported legs'
        return None, f'no book has {words} that pay {target[0]:+d} to {target[1]:+d}{detail}'
    return best[1], None


def ticket_pick(ticket, league, where, now, games):
    """Attach the climb's dollars and public fields to a validated ticket."""
    first = games.get(ticket['gameIds'][0]) or {}
    day = eastern_date(now)
    stake, banked = where['stake'], where['banked']
    returned = payout(stake, ticket['odds'])
    bank_cut, next_stake = split_return(returned)
    info = {'run': where['run'], 'step': where['step'], 'stake': stake, 'payout': returned,
            'banked': banked, 'bankThisWin': bank_cut, 'bankedAfter': banked + bank_cut,
            'nextStake': next_stake, 'totalAfter': banked + returned,
            'bankPercent': int(BANK_RATE * 100), 'ridePercent': 100 - int(BANK_RATE * 100),
            'start': START, 'goal': GOAL}
    base = (f"{league}-{first.get('season', day.year)}-W{first.get('week', 0)}-ladder-{day:%m%d}-"
            f"c{info['run']}s{info['step']}-{SLUGS[ticket['book']]}")
    sources = set(ticket.get('sources') or [])
    if ticket.get('quoteType', 'capture') == 'capture':
        sources.add(SOURCE)
    sources.update(games[g]['source'] for g in ticket['gameIds'] if g in games and games[g].get('source'))
    return {'id': base,
            'title': f"Ladder step {info['step']}: {len(ticket['legs'])} legs at {ticket['book']}",
            'status': 'active', 'favorite': False, 'parlayType': 'ladder', 'riskUnits': STAKE,
            'ladder': info, 'legs': ticket['legs'], '_league': league,
            'correlation': 'One leg per game, so the book prices the ticket as the legs multiplied.',
            'gameIds': ticket['gameIds'], 'book': ticket['book'], 'odds': ticket['odds'],
            'quotedAt': ticket['quotedAt'], 'priceEstimated': ticket.get('priceEstimated', True),
            # A rung selected before the 8:30 scan can legitimately wait for the
            # 9:15 Discord / 9:30 X window.  Expiring it at the next scan made a
            # fresh morning rung impossible to release.  The release path still
            # refuses it once the actual two-hour freshness limit is reached.
            'expiresAt': gates.stamp(min(gates.when(ticket['quotedAt']) + RELEASE_QUOTE_FRESH,
                                         gates.when(ticket['firstKickoff']), gates.next_slot(now))),
            'quoteType': ticket.get('quoteType', 'capture'), 'confidence': 1,
            'edge': (f"For fun, not value: {len(ticket['legs'])} protected lines with stable roles that our model "
                     f"direction agrees with, at {ticket['book']}'s exact prices, multiplied to "
                     f"{ticket['odds']:+d}. ${stake} rides with ${banked} already banked. A win returns "
                     f"${returned}: ${bank_cut} goes to the bank and ${next_stake} rides next. Bank 20, ride 80."),
            'cutoff': 'A ladder rung is not re-entered. It stands or falls as posted.',
            'sources': sorted(sources)}


def manual_candidate(ctx, games, now, spec):
    """Build one rung from exact sportsbook game-alternate quotes a person just verified.

    This is deliberately not a scraper. The spec records the visible book, line, price, source URL and quote time;
    the model supplies the chance and refuses a leg it does not independently support.
    """
    if not v3_enabled():
        return None, 'Climb v3 is switched off'
    if isinstance(spec, dict) and spec.get('selectionMethod') == 'sourced-climb-review-v1':
        import climb_review
        return climb_review.candidate(ctx, games, now, spec)
    where = state(ctx.first, ctx.latest)
    if where['open']:
        return None, f"{where['open']['id']} is still open; the next rung waits for its result"
    blocked = weekly_refusal(ctx, now)
    if blocked:
        return None, blocked
    minimum, target, alternates = shape_policy(now)
    if not isinstance(spec, dict) or not isinstance(spec.get('legs'), list) or not minimum <= len(spec['legs']) <= MAX_LEGS:
        return None, 'a manual rung needs ' + ('two to three' if alternates else 'one to three') + ' quoted legs'
    book = build_site.BOOKS.get(spec.get('book'), spec.get('book'))
    if book not in SLUGS:
        return None, 'the manual rung needs one supported book'
    quoted = spec.get('quotedAt')
    try:
        age = now - gates.when(quoted)
    except (TypeError, ValueError):
        return None, 'the manual rung needs a valid quote time'
    if not timedelta(minutes=-1) <= age <= FRESH:
        return None, 'the manual sportsbook quotes are stale'
    legs, leagues, game_ids, sources = [], set(), set(), set()
    for row in spec['legs']:
        game = games.get(row.get('gameId'))
        if not game or game.get('state', 'pre') != 'pre' or gates.when(game['kickoff']) <= now + LEAD:
            return None, f"{row.get('gameId')} is missing, started, or too close to kickoff"
        if game['id'] in game_ids:
            return None, 'a rung uses one leg per game'
        if game.get('league') not in ('NFL', 'CFB'):
            return None, 'NBA Climb legs are not ready; NBA research is not ticket approval'
        if eastern_date(gates.when(game['kickoff'])) != eastern_date(now):
            return None, 'a rung uses games on the current Eastern game day'
        market, side = row.get('marketType'), row.get('direction')
        line, price = row.get('line'), row.get('odds')
        allowed = ('home', 'away') if market == 'spread' else ('over', 'under')
        if market not in ('spread', 'total') or side not in allowed:
            return None, 'a manual game leg needs a spread side or total direction'
        # ``int()`` truncates toward zero, so ``int(-1.5) + .5`` is -0.5.
        # Check the doubled value instead so favorite spreads such as -1.5
        # receive the same no-push treatment as +1.5 and game totals.
        twice = float(line) * 2 if isinstance(line, (int, float)) else 0
        if not isinstance(line, (int, float)) or not twice.is_integer() or int(twice) % 2 == 0:
            return None, 'manual game alternates use half-point lines so they cannot push'
        if not isinstance(price, (int, float)) or not LEG_PRICES[0] <= int(price) <= LEG_PRICES[1]:
            return None, f'each manual leg must be priced {LEG_PRICES[0]:+d} to {LEG_PRICES[1]:+d}'
        snapshot = ctx.snapshot(game['id'])
        if not snapshot:
            return None, f"no model snapshot for {game['id']}"
        try:
            desk = pricing.price(snapshot, market, side, float(line), int(price))
        except (ValueError, KeyError):
            return None, f"the model cannot price {game['id']} {market}"
        if desk['rawChance'] < MANUAL_RAW_CHANCE:
            return None, f"the raw model only gives {100 * desk['rawChance']:.1f}% to {game['id']} {market}"
        segment_rate = segment_hit_rate(ctx, game['league'], market, book, int(price), side)
        chance = used_chance(desk['rawChance'], desk['breakEven'], segment_rate)
        if chance is None:
            return None, f'{game["league"]} {market} at {book} is not an open proven Climb segment'
        if chance <= desk['breakEven']:
            return None, f'{game["league"]} {market} does not beat its price after the segment check'
        team = game[side]['short'] if market == 'spread' else f"{game['away']['short']} at {game['home']['short']}"
        title = f"{team} {pricing.signed(float(line))}" if market == 'spread' else f"{team} {side} {pricing.fmt(float(line))}"
        source = row.get('source') or spec.get('source')
        if not str(source or '').startswith('https://'):
            return None, 'every manual quote needs its sportsbook page'
        sources.add(source)
        game_ids.add(game['id'])
        leagues.add(game['league'])
        legs.append({'id': f"ladder-{game['id']}-{market}-{side}-{float(line):g}", 'title': title,
                     'gameId': game['id'], 'marketType': market, 'direction': side, 'line': float(line),
                     'book': book, 'odds': int(price), 'chance': round(chance, 3),
                     'rawChance': round(desk['rawChance'], 3), 'segmentHitRate': round(segment_rate, 3),
                     'implied': desk['breakEven'],
                     'projection': desk['projection'], 'kickoff': game['kickoff'], 'observedAt': quoted,
                     'marketWindow': 'Full game', 'alternate': True})
    if len(leagues) != 1:
        return None, 'a rung stays inside one league'
    dec = 1.0
    for leg in legs:
        dec *= parlay.decimal(leg['odds'])
    price = parlay.american(dec)
    if not target[0] <= price <= target[1]:
        return None, f'the quoted ticket is {price:+d}; the climb targets {target[0]:+d} to {target[1]:+d}'
    chance = 1.0
    for leg in legs:
        chance *= leg['chance']
    if chance <= pricing.break_even(price):
        return None, 'the ticket chance does not beat the price after the segment check'
    ticket = {'book': book, 'legs': legs, 'odds': price, 'decimal': round(dec, 3),
              'gameIds': [leg['gameId'] for leg in legs], 'quotedAt': quoted,
              'firstKickoff': min(l['kickoff'] for l in legs), 'chance': round(chance, 4),
              'priceEstimated': False, 'quoteType': 'sportsbook', 'sources': sorted(sources)}
    return ticket_pick(ticket, leagues.pop(), where, now, games), None


def candidate(ctx, games, now, exclude=()):
    """The next rung as a pick, or (None, reason). Games in `exclude` (the desk has a reason against them) are left off.
    Compare eligible NFL and college tickets; a rung stays inside one league, as a report does."""
    if not v3_enabled():
        return None, 'Climb v3 is switched off'
    where = state(ctx.first, ctx.latest)
    if where['open']:
        return None, f"{where['open']['id']} is still open; the next rung waits for its result"
    blocked = weekly_refusal(ctx, now)
    if blocked:
        return None, blocked
    import direction
    # Two climbs in a row lost at step 1 or 2: the next climb takes the stricter pool (owner, 2026-10-07): no leg from
    # a segment that is paused or has a raised edge bar, with the same leg chance, leg prices and TARGET.
    policy = getattr(ctx, 'policy', None)
    strict = direction.climb_rules(policy, now)
    reasons = []
    supported = []
    for league in ('NFL', 'CFB'):
        today = todays_games(games, now, league, exclude)
        if not today:
            reasons.append(f'{league}: {len(today)} games left today')
            continue
        seen = confirmed_at()
        calibrated = league not in gates.OWN_CALIBRATION or bool(
            ((getattr(ctx, 'policy', None) or {}).get('calibration') or {}).get(f'{league}/prop'))
        if not calibrated:
            reasons.append(f'{league}: player alternates wait for their own calibration; game moneylines still checked')
        for day_pool in kickoff_windows(today):
            legs = [leg for game in day_pool for leg in moneyline_legs(game, ctx, now) + game_line_legs(game, ctx, now) + alternate_spread_legs(game, ctx, now)]
            if calibrated:
                legs += [leg for game in day_pool
                         for leg in legs_for_game(game, ctx.prop_odds.get(game['id']), ctx, now, seen, proven=True)]
            if strict:
                legs = strict_legs(legs, policy, now, league)
            ticket, reason = build(gates.without_straight_players(legs, ctx), now)
            label = gates.when(day_pool[0]['kickoff']).astimezone(gates.EASTERN).strftime('%b %-d game day')
            if not ticket:
                reasons.append(f'{league} {label}: {reason}' + ('; the stricter Climb pool is on' if strict else ''))
                continue
            score = ticket_rank(ticket['chance'], ticket['chance'] - pricing.break_even(ticket['odds']),
                                ticket['legs'], ticket['odds'])
            supported.append((score, ticket, league))
    if supported:
        _, ticket, league = max(supported, key=lambda row: row[0])
        return ticket_pick(ticket, league, where, now, games), None
    return None, '; '.join(reasons) or 'no games today'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--now', help='UTC instant; default now')
    args = parser.parse_args(argv)
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    ctx = gates.Stores().as_of(now)
    where = state(ctx.first, ctx.latest)
    print(f"run {where['run']}, step {where['step']}, ${where['stake']} riding, ${where['banked']} banked; "
          f"{len(where['history'])} rungs played, "
          f"{len(where['climbs'])} climbs finished" + (f"; open: {where['open']['id']}" if where['open'] else ''))
    pick, reason = candidate(ctx, ctx.games, now)
    if pick:
        info = pick['ladder']
        print(f"next rung: {pick['title']} {pick['odds']:+d}: ${info['stake']} to ${info['payout']}; "
              f"a win banks ${info['bankThisWin']} and rides ${info['nextStake']}")
        for leg in pick['legs']:
            print(f"  {leg['title']} {leg['odds']:+d} (ours {100 * leg['chance']:.0f}%, the price {100 * leg['implied']:.0f}%)")
    else:
        print(f'no rung now: {reason}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
