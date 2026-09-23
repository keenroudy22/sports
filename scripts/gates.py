"""The publishing rules as code. A candidate pick passes every gate or it is not published.

PROMPT.md and RESEARCH.md describe the rules in English. This module is the same rules as
functions, one per rule, each taking a candidate pick and the current board and returning a
Decision: pass, or a refusal with the rule's name and the reason in words. The research run
(scripts/run.py) admits nothing these refuse; scripts/replay_gates.py runs every published pick
back through them as of its publication.

A candidate is the pick as it would be written to a report (RESEARCH.md fields), plus three
private keys the run attaches and the report never carries:

  _desk      the verbatim output of pricing.price() for the pick's line and price
  _quotes    every book's quote for the pick's side: [(book, line, odds)] (else read from the stores)
  _evidence  sourced facts: {kind, direction ('for'|'against'|'neutral'), claim, source, retrievedAt, verified}

Two gates are switches, on by default (FLAGS): QB_GATE refuses a total when either starting
quarterback is doubtful or worse, because the team number has no quarterback input yet;
MARKET_GATE refuses a prop lean in a market where the book's line has been closer to the result
than our projection, read live from site/data/scoreboard.json so it reopens on its own.

Usage: python scripts/gates.py CANDIDATE.json      evaluate one candidate against the live stores
Stdlib only.
"""
import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import features
import integrity
import learning
import pricing
from desk import current as current_snapshot
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
EASTERN = ZoneInfo('America/New_York')
# (hour, minute, weekdays or None for every day); Monday is 0, Sunday is 6. PROMPT.md's table.
SCHEDULE = ((6, 45, None), (8, 30, None), (11, 45, None), (14, 45, (6,)), (17, 30, None),
            (18, 50, (0, 3, 6)), (23, 30, None))
FLAGS = {'QB_GATE': True, 'MARKET_GATE': True}
# Books available in Indiana; a college pick must quote one of them and college player props are not offered.
INDIANA_BOOKS = {'DraftKings', 'FanDuel', 'BetMGM', 'Caesars', 'BetRivers', 'ESPN BET', 'Fanatics', 'bet365',
                 'Hard Rock Bet'}
LISTED = {'questionable', 'doubtful', 'out', 'injured reserve', 'suspension', 'game-time decision'}
QB_OUT = {'doubtful', 'out', 'injured reserve', 'suspension'}
QUOTE_TYPES = {'capture', 'feed', 'page', 'sportsbook'}
STARTED_MARGIN = timedelta(minutes=5)      # a game this close to kickoff cannot be published in time
ONE_BOOK_EXCEPTION = timedelta(hours=3)    # inside this, one book is all there will be
LEAN_EDGE, LEAN_STRONG = 1.0, 2.0          # model lean: points clear of break-even; confidence 3 at 2+
PROP_RAW, PROP_EDGE, PROP_FLOOR = 0.60, 5.0, -200
LEANS_PER_DAY, PROPS_PER_WINDOW, LONGSHOTS_PER_DAY = 4, 3, 1
MARKET_GATE_MIN = 30                       # graded player markets before the scoreboard can close one
TOTAL_RANGE, SPREAD_MAX = (20.0, 100.0), 70.0
BOOK_NAMES = build_site.BOOK_NAMES


@dataclass
class Decision:
    ok: bool
    rule: str
    reason: str
    data: dict = field(default_factory=dict)

    def __str__(self):
        return f"{'pass' if self.ok else 'REFUSED'} {self.rule}: {self.reason}"


@dataclass
class Context:
    """Everything the gates read, as of `now`. Built by context(); tests build it by hand."""
    now: datetime
    games: dict = field(default_factory=dict)          # gameId -> slate game
    odds: dict = field(default_factory=dict)           # gameId -> latest data/odds record at or before now
    prop_odds: dict = field(default_factory=dict)      # gameId -> latest data/prop-odds record at or before now
    snapshots: dict = field(default_factory=dict)      # gameId -> v2 snapshots, oldest first
    injuries: dict = field(default_factory=dict)       # teamId -> {athleteId: {'status', 'position', 'name'}}
    scoreboard: dict = field(default_factory=dict)     # site/data/scoreboard.json
    first: dict = field(default_factory=dict)          # pick id -> first publication (published at or before now)
    latest: dict = field(default_factory=dict)         # pick id -> merged latest fields
    appearances: dict = field(default_factory=lambda: defaultdict(int))   # athleteId -> games this season
    established: set = field(default_factory=set)     # (athleteId, teamId) with 8+ games last season
    names: dict = field(default_factory=dict)          # athleteId -> name
    player_team: dict = field(default_factory=dict)    # athleteId -> teamId in the latest stored game
    starters: dict = field(default_factory=dict)       # teamId -> usual starting quarterback's athleteId
    flags: dict = field(default_factory=lambda: dict(FLAGS))
    policy: dict = field(default_factory=learning.default_policy)   # learned thresholds; the defaults are the written rules

    def snapshot(self, game_id):
        game = self.games.get(game_id)
        if not game:
            return None
        return current_snapshot(self.snapshots.get(game_id, []), game['kickoff'], self.now)


# ------------------------------------------------------------------ time

def when(value):
    return features.when(value)


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def scheduled(day):
    """The run times on an Eastern date, as aware datetimes."""
    for hour, minute, days in SCHEDULE:
        if days is None or day.weekday() in days:
            yield datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN)


def next_slot(now):
    """The first scheduled run strictly after now."""
    local = now.astimezone(EASTERN)
    for offset in range(0, 3):
        day = (local + timedelta(days=offset)).date()
        for moment in scheduled(day):
            if moment > local:
                return moment.astimezone(timezone.utc)
    raise RuntimeError('no scheduled run inside three days')


def window(kickoff):
    """early (before 3:30 PM ET), late (before 7 PM) or night."""
    local = when(kickoff).astimezone(EASTERN)
    minutes = local.hour * 60 + local.minute
    return 'early' if minutes < 15 * 60 + 30 else 'late' if minutes < 19 * 60 else 'night'


def same_day(a, b):
    return eastern_date(when(a) if isinstance(a, str) else a) == eastern_date(when(b) if isinstance(b, str) else b)


# ------------------------------------------------------------------ candidate helpers

def kind_of(pick):
    """favorite, modelLean, propLean, longshot, researched or revision."""
    if pick.get('result') or pick.get('status') in ('settled', 'expired', 'withdrawn') or pick.get('entryNote'):
        return 'revision'
    if pick.get('legs') or pick.get('parlayType'):
        return 'longshot'
    if pick.get('favorite') is True:
        return 'favorite'
    if pick.get('modelLean'):
        return 'propLean' if pick.get('athleteId') else 'modelLean'
    return 'researched'


def game_of(candidate, ctx):
    return ctx.games.get((candidate.get('gameIds') or [None])[0])


def kickoffs(candidate, ctx):
    return [when(ctx.games[g]['kickoff']) for g in candidate.get('gameIds') or [] if g in ctx.games]


def market_key(candidate):
    """spread, total, or the prop market key (recYds, rec, ...)."""
    if candidate.get('marketType') in ('spread', 'total') and not candidate.get('athleteId'):
        return candidate['marketType']
    return pricing.market_of(candidate)


def side_of(candidate):
    return str(candidate.get('direction') or '').lower()


def player_name(candidate, ctx):
    name = ctx.names.get(str(candidate.get('athleteId') or ''))
    if name:
        return name
    title = candidate.get('title') or ''
    for word in (' OVER ', ' UNDER ', ' over ', ' under '):
        if word in title:
            return title.split(word)[0].strip()
    return title


def quotes_for(candidate, ctx, priced_only=False):
    """[(book, line, odds)] for the candidate's side across the latest capture. odds may be None."""
    if candidate.get('_quotes') is not None:
        rows = [tuple(q) if isinstance(q, (list, tuple)) else (q['book'], q['line'], q.get('odds'))
                for q in candidate['_quotes']]
    else:
        rows = []
        game_id = (candidate.get('gameIds') or [None])[0]
        market, side = market_key(candidate), side_of(candidate)
        if candidate.get('athleteId'):
            record = ctx.prop_odds.get(game_id)
            for book, line, over, under in build_site.price_quotes(record, market, player_name(candidate, ctx),
                                                                   candidate.get('line')):
                rows.append((BOOK_NAMES.get(book, book), line, over if side == 'over' else under))
        else:
            record = ctx.odds.get(game_id) or {}
            for book, entry in (record.get('books') or {}).items():
                if market == 'spread' and entry.get('spread'):
                    s = entry['spread']
                    line = s['home'] if side == 'home' else -s['home']
                    rows.append((BOOK_NAMES.get(book, book), line, s.get('homePrice') if side == 'home' else s.get('awayPrice')))
                elif market == 'total' and entry.get('total'):
                    t = entry['total']
                    rows.append((BOOK_NAMES.get(book, book), t['line'], t.get('over') if side == 'over' else t.get('under')))
    if priced_only:
        rows = [r for r in rows if isinstance(r[2], (int, float)) and abs(r[2]) >= 100]
    return rows


def desk_for(candidate, ctx):
    """pricing.price() for the candidate at its own line and price, or None when v2 has no number."""
    if candidate.get('_desk') is not None:
        return candidate['_desk']
    snapshot = ctx.snapshot((candidate.get('gameIds') or [None])[0])
    market, side = market_key(candidate), side_of(candidate)
    if not snapshot or not market or not isinstance(candidate.get('line'), (int, float)) \
            or not isinstance(candidate.get('odds'), (int, float)):
        return None
    try:
        return pricing.price(snapshot, market, side, float(candidate['line']), int(candidate['odds']),
                             candidate.get('athleteId'))
    except (ValueError, KeyError):
        return None


def published_today(ctx, exclude=None):
    """First publications on the Eastern date of ctx.now, at or before ctx.now, other than `exclude`."""
    for key, pick in ctx.first.items():
        if key == exclude or pick.get('historicalImport'):
            continue
        published = pick.get('publishedAt')
        if published and when(published) <= ctx.now and same_day(published, ctx.now):
            yield key, pick


def is_open(key, ctx):
    recent = ctx.latest.get(key, {})
    return not recent.get('result') and recent.get('status', ctx.first[key].get('status')) == 'active'


def team_of(candidate, ctx):
    return ctx.player_team.get(str(candidate.get('athleteId') or ''))


def listed_status(athlete, team, ctx):
    entry = (ctx.injuries.get(str(team)) or {}).get(str(athlete)) if team is not None else None
    if entry is None:
        for block in ctx.injuries.values():
            if str(athlete) in block:
                entry = block[str(athlete)]
                break
    return str((entry or {}).get('status') or '').lower()


# ------------------------------------------------------------------ rules: every pick

def not_started(candidate, ctx):
    """Never publish on a game that has started, or will before the report lands."""
    ids = candidate.get('gameIds') or []
    missing = [g for g in ids if g not in ctx.games]
    if not ids or missing:
        return Decision(False, 'not_started', f"game not in the slate: {', '.join(missing) or 'no gameIds'}")
    soonest = min(kickoffs(candidate, ctx))
    if soonest <= ctx.now + STARTED_MARGIN:
        return Decision(False, 'not_started', f'kickoff {stamp(soonest)} is not after {stamp(ctx.now)} plus '
                                              f'{int(STARTED_MARGIN.total_seconds() // 60)} minutes')
    return Decision(True, 'not_started', f'kickoff {stamp(soonest)}')


def expiry_ok(candidate, ctx):
    """expiresAt is the next scheduled run or kickoff, whichever comes first; quotedAt is not in the future."""
    if not candidate.get('expiresAt') or not candidate.get('quotedAt'):
        return Decision(False, 'expiry_ok', 'missing expiresAt or quotedAt')
    expires, quoted = when(candidate['expiresAt']), when(candidate['quotedAt'])
    if quoted > ctx.now + timedelta(minutes=1):
        return Decision(False, 'expiry_ok', f"quotedAt {candidate['quotedAt']} is after now {stamp(ctx.now)}")
    if expires <= ctx.now:
        return Decision(False, 'expiry_ok', f"expiresAt {candidate['expiresAt']} is not after now")
    starts = kickoffs(candidate, ctx)
    limit = min([next_slot(ctx.now)] + starts)
    if expires > limit + timedelta(minutes=1):
        return Decision(False, 'expiry_ok', f"expiresAt {candidate['expiresAt']} is past the next run or kickoff "
                                            f'{stamp(limit)}', {'limit': stamp(limit)})
    return Decision(True, 'expiry_ok', f'expires {stamp(expires)}, limit {stamp(limit)}')


def price_present(candidate, ctx):
    """A named book, American odds and a quote time; nothing is published without a price."""
    odds = candidate.get('odds')
    if not candidate.get('book'):
        return Decision(False, 'price_present', 'no book named')
    if not isinstance(odds, (int, float)) or abs(odds) < 100:
        return Decision(False, 'price_present', f'odds {odds!r} are not American odds')
    if not candidate.get('quotedAt'):
        return Decision(False, 'price_present', 'no quotedAt')
    if candidate.get('quoteType') not in QUOTE_TYPES:
        return Decision(False, 'price_present', f"quoteType {candidate.get('quoteType')!r} is not one of {sorted(QUOTE_TYPES)}")
    return Decision(True, 'price_present', f"{candidate['book']} {odds:+d}")


def data_sanity(candidate, ctx):
    """A line the game cannot produce is a data error, not an edge."""
    line, market = candidate.get('line'), market_key(candidate)
    if candidate.get('legs'):
        return Decision(True, 'data_sanity', 'parlay legs are checked one by one')
    if not isinstance(line, (int, float)):
        return Decision(False, 'data_sanity', f'line {line!r} is not a number')
    if market == 'total' and not TOTAL_RANGE[0] <= line <= TOTAL_RANGE[1]:
        return Decision(False, 'data_sanity', f'total {line:g} is outside {TOTAL_RANGE[0]:g} to {TOTAL_RANGE[1]:g}')
    if market == 'spread' and abs(line) > SPREAD_MAX:
        return Decision(False, 'data_sanity', f'spread {line:+g} is beyond {SPREAD_MAX:g} points')
    if candidate.get('athleteId'):
        if line < 0:
            return Decision(False, 'data_sanity', f'player line {line:g} is negative')
        if market == 'cmp':
            attempts = quotes_for(dict(candidate, market='att', title=candidate.get('title'), _quotes=None), ctx)
            same = [l for b, l, _ in attempts if b == candidate.get('book')]
            if same and line >= same[0]:
                return Decision(False, 'data_sanity', f"completions line {line:g} is not below the attempts line {same[0]:g} at {candidate['book']}")
    return Decision(True, 'data_sanity', 'line is possible')


def sources_https(candidate, ctx):
    sources = candidate.get('sources') or []
    bad = [s for s in sources if not str(s).startswith('https://')]
    if not sources:
        return Decision(False, 'sources_https', 'no sources')
    if bad:
        return Decision(False, 'sources_https', f'not https: {bad[0]}')
    return Decision(True, 'sources_https', f'{len(sources)} https sources')


def not_duplicate(candidate, ctx):
    """One open pick per market and side, per game or per player."""
    market, side = market_key(candidate), side_of(candidate)
    game_id, athlete = (candidate.get('gameIds') or [None])[0], str(candidate.get('athleteId') or '')
    for key, pick in ctx.first.items():
        if key == candidate.get('id') or pick.get('historicalImport') or pick.get('legs') or not is_open(key, ctx):
            continue
        if when(pick.get('publishedAt') or '1970-01-01T00:00Z') > ctx.now:
            continue
        if athlete:
            if str(pick.get('athleteId') or '') == athlete and market_key(pick) == market:
                return Decision(False, 'not_duplicate', f'{key} is already open on this player and market')
        elif (pick.get('gameIds') or [None])[0] == game_id and market_key(pick) == market and side_of(pick) == side \
                and not pick.get('athleteId'):
            return Decision(False, 'not_duplicate', f'{key} is already open on this game, market and side')
    return Decision(True, 'not_duplicate', 'no open pick on this market')


def cfb_jurisdiction(candidate, ctx):
    """A college pick quotes a book available in Indiana; college player props are not offered there."""
    league = candidate.get('league') or ((game_of(candidate, ctx) or {}).get('league'))
    if league != 'CFB':
        return Decision(True, 'cfb_jurisdiction', 'not a college pick')
    if candidate.get('athleteId'):
        return Decision(False, 'cfb_jurisdiction', 'college player props are not offered in Indiana')
    book = candidate.get('book')
    if book not in INDIANA_BOOKS:
        return Decision(False, 'cfb_jurisdiction', f'{book} is not a book available in Indiana')
    candidate['jurisdictionVerified'] = True
    return Decision(True, 'cfb_jurisdiction', f'{book} is available in Indiana', {'jurisdictionVerified': True})


# ------------------------------------------------------------------ rules: shopping the quote

def one_book(candidate, ctx):
    """When one book alone has posted the market there is nothing to shop; wait, unless kickoff is inside three hours."""
    books = {b for b, _, _ in quotes_for(candidate, ctx)}
    if len(books) >= 2:
        return Decision(True, 'one_book', f"{len(books)} books quote the market: {', '.join(sorted(books))}")
    starts = kickoffs(candidate, ctx)
    if starts and min(starts) - ctx.now <= ONE_BOOK_EXCEPTION:
        return Decision(True, 'one_book', f"only {', '.join(sorted(books)) or 'no book'} has posted, but kickoff is inside "
                                          f'{int(ONE_BOOK_EXCEPTION.total_seconds() // 3600)} hours; say so in the quote note',
                        {'quoteNoteRequired': True, 'books': sorted(books)})
    return Decision(False, 'one_book', f"only {', '.join(sorted(books)) or 'no book'} has posted this market and kickoff is "
                                       f'more than {int(ONE_BOOK_EXCEPTION.total_seconds() // 3600)} hours away',
                    {'books': sorted(books)})


def best_quote_by_ev(candidate, ctx):
    """The pick takes the quote with the best expected value across books, not the best-looking number."""
    snapshot = ctx.snapshot((candidate.get('gameIds') or [None])[0])
    market, side = market_key(candidate), side_of(candidate)
    quotes = quotes_for(candidate, ctx, priced_only=True)
    if not snapshot or not market or not quotes:
        return Decision(True, 'best_quote_by_ev', 'no priced alternatives to compare')
    priced = []
    for book, line, odds in quotes:
        try:
            p = pricing.price(snapshot, market, side, float(line), int(odds), candidate.get('athleteId'))
        except (ValueError, KeyError):
            continue
        priced.append((p['evPerUnit'], book, line, int(odds)))
    if not priced:
        return Decision(True, 'best_quote_by_ev', 'v2 cannot price the alternatives')
    best = max(priced)
    own = desk_for(candidate, ctx)
    own_ev = own['evPerUnit'] if own else None
    if own_ev is None:
        return Decision(True, 'best_quote_by_ev', 'the candidate itself has no model number to compare')
    if best[0] > own_ev + 0.0005 and (best[1], best[2], best[3]) != (candidate.get('book'), candidate.get('line'), candidate.get('odds')):
        return Decision(False, 'best_quote_by_ev', f"{best[1]} {best[2]:g} at {best[3]:+d} is worth {best[0]:+.3f}u against "
                                                   f"{candidate.get('book')} {candidate.get('line'):g} at {candidate.get('odds'):+d} "
                                                   f'at {own_ev:+.3f}u', {'best': {'book': best[1], 'line': best[2], 'odds': best[3], 'evPerUnit': best[0]}})
    return Decision(True, 'best_quote_by_ev', f'{own_ev:+.3f}u is the best expected value on the board')


# ------------------------------------------------------------------ rules: model leans

def lean_is_total(candidate, ctx):
    if candidate.get('marketType') != 'total':
        return Decision(False, 'lean_is_total', f"a model lean is a total, never a {candidate.get('marketType')}")
    return Decision(True, 'lean_is_total', 'total')


def lean_edge(candidate, ctx):
    desk = desk_for(candidate, ctx)
    if not desk:
        return Decision(False, 'lean_edge', 'v2 has no number for this line')
    if not desk.get('calibrated'):
        return Decision(False, 'lean_edge', 'the chance is uncalibrated; a model lean needs a calibrated chance')
    need = max(LEAN_EDGE, learning.threshold(ctx.policy, 'lean.minEdge', learning.segment_of(candidate)))
    if desk['edgePoints'] < need:
        return Decision(False, 'lean_edge', f"{desk['edgePoints']:+.1f} points against break-even; needs {need:+.1f}")
    return Decision(True, 'lean_edge', f"{desk['edgePoints']:+.1f} points clear of break-even", {'edgePoints': desk['edgePoints']})


def lean_confidence(candidate, ctx):
    desk = desk_for(candidate, ctx)
    if not desk:
        return Decision(False, 'lean_confidence', 'v2 has no number for this line')
    want = 3 if desk['edgePoints'] >= LEAN_STRONG else 2
    if candidate.get('confidence') != want:
        return Decision(False, 'lean_confidence', f"confidence {candidate.get('confidence')} at {desk['edgePoints']:+.1f} points; the rule says {want}")
    return Decision(True, 'lean_confidence', f'confidence {want}')


def lean_daily_cap(candidate, ctx):
    today = [k for k, p in published_today(ctx, candidate.get('id'))
             if p.get('modelLean') and not p.get('athleteId') and not p.get('legs')]
    if len(today) >= LEANS_PER_DAY:
        return Decision(False, 'lean_daily_cap', f'{len(today)} model leans already published today; the cap is {LEANS_PER_DAY}')
    return Decision(True, 'lean_daily_cap', f'{len(today)} of {LEANS_PER_DAY} model leans today')


def lean_nothing_against(candidate, ctx):
    against = [f for f in candidate.get('_evidence') or [] if f.get('direction') == 'against']
    if against:
        return Decision(False, 'lean_nothing_against', f"sourced evidence argues against it: {against[0].get('claim')}",
                        {'facts': [f.get('id') for f in against]})
    return Decision(True, 'lean_nothing_against', 'nothing sourced argues against it')


def qb_available(candidate, ctx):
    """No total when either starting quarterback is doubtful or worse: the team number cannot see it."""
    if not ctx.flags.get('QB_GATE', True):
        return Decision(True, 'qb_available', 'gate off by flag')
    if market_key(candidate) != 'total' or candidate.get('athleteId'):
        return Decision(True, 'qb_available', 'not a total')
    game = game_of(candidate, ctx)
    if not game:
        return Decision(False, 'qb_available', 'game not in the slate')
    checked = False
    for side in ('home', 'away'):
        team = str(game[side]['id'])
        if team not in ctx.injuries:
            continue
        checked = True
        starter = ctx.starters.get(team)
        status = listed_status(starter, team, ctx) if starter else ''
        if status in QB_OUT:
            return Decision(False, 'qb_available', f"{game[side]['abbreviation']} starting quarterback "
                                                   f"{ctx.names.get(starter, starter)} is {status}", {'team': team, 'athleteId': starter})
    return Decision(True, 'qb_available', 'both listed starters clear' if checked else 'no injury report for these teams',
                    {'checked': checked})


# ------------------------------------------------------------------ rules: prop leans

def prop_raw_edge(candidate, ctx):
    desk = desk_for(candidate, ctx)
    if not desk:
        return Decision(False, 'prop_raw_edge', 'v2 has no projection for this player and market')
    segment = learning.segment_of(candidate)
    raw_need = max(PROP_RAW, learning.threshold(ctx.policy, 'prop.minRaw', segment))
    edge_need = max(PROP_EDGE, learning.threshold(ctx.policy, 'prop.minEdge', segment))
    if desk['rawChance'] < raw_need:
        return Decision(False, 'prop_raw_edge', f"raw chance {100 * desk['rawChance']:.1f}% is under {100 * raw_need:.0f}%")
    if desk['edgePoints'] < edge_need:
        return Decision(False, 'prop_raw_edge', f"{desk['edgePoints']:+.1f} points against the price; needs {edge_need:+.0f}")
    return Decision(True, 'prop_raw_edge', f"raw {100 * desk['rawChance']:.1f}%, {desk['edgePoints']:+.1f} points")


def learned_pause(candidate, ctx):
    """A segment learning paused: its plays kept losing to the closing line even at the strictest setting."""
    segment = learning.segment_of(candidate)
    if learning.paused(ctx.policy, segment):
        since = ((ctx.policy.get('segments') or {}).get(segment) or {}).get('since')
        return Decision(False, 'learned_pause', f'{segment} is paused by learning since {since}: its plays kept losing to the close')
    return Decision(True, 'learned_pause', f'{segment} is open')


def prop_calibrated_value(candidate, ctx):
    """Once learning has calibrated the raw player chances against the graded record, a prop must clear its
    price on the calibrated chance too. Before that, the written raw-chance rule stands alone."""
    league = candidate.get('league') or str(candidate.get('id', '')).split('-')[0]
    cal = ((ctx.policy.get('calibration') or {}).get(f'{league}/prop') or {})
    k = cal.get('k')
    if k is None:
        return Decision(True, 'prop_calibrated_value', 'no learned calibration for player chances yet')
    desk = desk_for(candidate, ctx)
    if not desk:
        return Decision(False, 'prop_calibrated_value', 'v2 has no projection for this player and market')
    chance = 0.5 + k * (desk['rawChance'] - 0.5)
    edge = 100 * (chance - desk['breakEven'])
    need = learning.threshold(ctx.policy, 'prop.minCalibratedEdge', learning.segment_of(candidate))
    if edge < need:
        return Decision(False, 'prop_calibrated_value',
                        f"calibrated {100 * chance:.1f}% (raw {100 * desk['rawChance']:.1f}% shrunk by k {k:g}, learned from "
                        f"{cal.get('n')} graded projections) is {edge:+.1f} points against the price; needs {need:+.0f}")
    return Decision(True, 'prop_calibrated_value', f'calibrated {100 * chance:.1f}%, {edge:+.1f} points', {'calibratedChance': round(chance, 3)})


def prop_settled_role(candidate, ctx):
    athlete, team = str(candidate.get('athleteId') or ''), team_of(candidate, ctx)
    if build_site.settled_role(athlete, team, ctx.appearances, ctx.established):
        return Decision(True, 'prop_settled_role', f'{ctx.appearances[athlete]} games this season'
                        + ('' if ctx.appearances[athlete] >= 3 else ', settled by last season'))
    return Decision(False, 'prop_settled_role', f'{ctx.appearances[athlete]} games this season and not eight for the same team last season')


def prop_price_floor(candidate, ctx):
    odds = candidate.get('odds')
    if isinstance(odds, (int, float)) and odds < PROP_FLOOR:
        return Decision(False, 'prop_price_floor', f'{odds:+d} is worse than {PROP_FLOOR:+d}')
    return Decision(True, 'prop_price_floor', f'{odds:+d}' if isinstance(odds, (int, float)) else 'no odds')


def prop_window_cap(candidate, ctx):
    game = game_of(candidate, ctx)
    if not game:
        return Decision(False, 'prop_window_cap', 'game not in the slate')
    slot = window(game['kickoff'])
    same = []
    for key, pick in published_today(ctx, candidate.get('id')):
        other = ctx.games.get((pick.get('gameIds') or [None])[0])
        if pick.get('modelLean') and pick.get('athleteId') and other and window(other['kickoff']) == slot \
                and same_day(other['kickoff'], game['kickoff']):
            same.append(key)
    if len(same) >= PROPS_PER_WINDOW:
        return Decision(False, 'prop_window_cap', f'{len(same)} prop leans already in the {slot} window; the cap is {PROPS_PER_WINDOW}')
    return Decision(True, 'prop_window_cap', f'{len(same)} of {PROPS_PER_WINDOW} in the {slot} window')


def prop_one_per_player(candidate, ctx):
    athlete = str(candidate.get('athleteId') or '')
    for key, pick in published_today(ctx, candidate.get('id')):
        if str(pick.get('athleteId') or '') == athlete and pick.get('modelLean'):
            return Decision(False, 'prop_one_per_player', f'{key} is already a lean on this player today')
    return Decision(True, 'prop_one_per_player', 'first lean on this player today')


def prop_not_in_longshot(candidate, ctx):
    athlete = str(candidate.get('athleteId') or '')
    for key, pick in published_today(ctx, candidate.get('id')):
        for leg in pick.get('legs') or []:
            if str(leg.get('athleteId') or '') == athlete or f'-{athlete}-' in str(leg.get('id') or ''):
                return Decision(False, 'prop_not_in_longshot', f"the player is a leg of today's longshot {key}")
    return Decision(True, 'prop_not_in_longshot', "not in today's longshot")


def prop_injury_clear(candidate, ctx):
    athlete = candidate.get('athleteId')
    if not athlete:
        return Decision(True, 'prop_injury_clear', 'no player')
    status = listed_status(athlete, team_of(candidate, ctx), ctx)
    if status in LISTED:
        return Decision(False, 'prop_injury_clear', f'the injury report lists the player {status}')
    return Decision(True, 'prop_injury_clear', 'not listed questionable or worse' if not status else f'listed {status}')


def prop_market_not_trailing(candidate, ctx):
    """No prop lean in a market where the book's line has been closer to the result than our projection."""
    if not ctx.flags.get('MARKET_GATE', True):
        return Decision(True, 'prop_market_not_trailing', 'gate off by flag')
    market = market_key(candidate)
    rows = {m.get('market'): m for m in ((ctx.scoreboard.get('props') or {}).get('markets') or [])}
    row = rows.get(market)
    if not row or (row.get('graded') or 0) < MARKET_GATE_MIN:
        return Decision(True, 'prop_market_not_trailing', f'{market}: under {MARKET_GATE_MIN} graded markets, nothing to go on')
    ours, theirs = row['closerThanLine']
    if ours < theirs:
        return Decision(False, 'prop_market_not_trailing', f"{market}: the line was closer than our projection in "
                                                           f"{theirs} of {row['graded']} graded games", {'closerThanLine': [ours, theirs]})
    return Decision(True, 'prop_market_not_trailing', f"{market}: our projection closer in {ours} of {row['graded']}")


# ------------------------------------------------------------------ rules: favorites, longshots, revisions

def favorite_needs_reason(candidate, ctx):
    """A favorite carries a verified, sourced reason the price is wrong; nothing else is a favorite."""
    if candidate.get('favorite') is not True:
        return Decision(True, 'favorite_needs_reason', 'not a favorite')
    for fact in candidate.get('_evidence') or []:
        if fact.get('direction') == 'for' and fact.get('kind') in ('injury', 'role', 'weather', 'stats') \
                and str(fact.get('source') or '').startswith('https://') and fact.get('retrievedAt') \
                and when(fact['retrievedAt']) <= ctx.now and fact.get('verified') is True:
            return Decision(True, 'favorite_needs_reason', f"{fact['kind']}: {fact.get('claim')}", {'fact': fact.get('id')})
    return Decision(False, 'favorite_needs_reason', 'no verified, sourced reason for the pick')


def longshot_one_per_day(candidate, ctx):
    today = [k for k, p in published_today(ctx, candidate.get('id')) if p.get('parlayType') == 'longshot' or p.get('legs')]
    if len(today) >= LONGSHOTS_PER_DAY:
        return Decision(False, 'longshot_one_per_day', f"{today[0]} is already today's longshot")
    return Decision(True, 'longshot_one_per_day', 'first longshot today')


FROZEN = tuple(dict.fromkeys(integrity.PICK_FIELDS + ('legs', 'riskUnits', 'parlayType')))


def revision_frozen(candidate, ctx):
    """A revision adds fields; it never rewrites what was published."""
    original = ctx.first.get(candidate.get('id'))
    if original is None:
        return Decision(False, 'revision_frozen', f"{candidate.get('id')} was never published; a revision needs an original")
    for key in FROZEN:
        if key == 'publishedAt':
            continue
        before, after = original.get(key), candidate.get(key)
        if before is not None and after is not None and before != after:
            return Decision(False, 'revision_frozen', f'{key} changed from {before!r} to {after!r}; publish a new pick id instead')
    return Decision(True, 'revision_frozen', 'frozen fields unchanged')


# ------------------------------------------------------------------ running the rules

COMMON = (not_started, expiry_ok, price_present, data_sanity, sources_https, not_duplicate, cfb_jurisdiction)
SHOP = (one_book, best_quote_by_ev)
RULES = {
    'modelLean': COMMON + SHOP + (lean_is_total, lean_edge, learned_pause, lean_confidence, lean_daily_cap, lean_nothing_against, qb_available),
    'propLean': COMMON + SHOP + (prop_raw_edge, prop_calibrated_value, learned_pause, prop_settled_role, prop_price_floor, prop_window_cap,
                                 prop_one_per_player, prop_not_in_longshot, prop_injury_clear, prop_market_not_trailing, lean_nothing_against),
    'favorite': COMMON + SHOP + (favorite_needs_reason, lean_nothing_against, qb_available, prop_injury_clear),
    'researched': COMMON + SHOP + (lean_nothing_against, qb_available, prop_injury_clear),
    'longshot': (not_started, expiry_ok, price_present, sources_https, longshot_one_per_day),
    'revision': (revision_frozen,),
}


def evaluate(candidate, ctx, kind=None):
    """Every applicable rule's decision, in order. Nothing short-circuits, so a report can name every problem."""
    kind = kind or kind_of(candidate)
    return [rule(candidate, ctx) for rule in RULES[kind]]


def admit(candidate, ctx, kind=None):
    """(admitted, decisions). Admitted only when every rule passed."""
    decisions = evaluate(candidate, ctx, kind)
    return all(d.ok for d in decisions), decisions


def refusals(decisions):
    return [d for d in decisions if not d.ok]


# ------------------------------------------------------------------ loading the stores

class Stores:
    """Everything on disk the gates read, loaded once; context() slices it as of any instant."""

    def __init__(self, root=ROOT, records=None):
        self.root = Path(root)
        data = root / 'site' / 'data'
        self.slate = build_site.read(data / 'slate.json', {'games': []})
        self.reports = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((root / 'research').glob('*.json'))]
        self.context_file = build_site.read(data / 'research-context.json', {})
        self.scoreboard = build_site.read(data / 'scoreboard.json', {})
        self.odds = build_site.load_store('odds') if root == ROOT else {}
        self.prop_odds = build_site.load_store('prop-odds') if root == ROOT else {}
        self.snapshots = build_site.load_store('forecasts') if root == ROOT else {}
        self.records = records if records is not None else features.load()

    def as_of(self, now, flags=None):
        return context(now, self, flags)


def latest_before(rows, now):
    usable = [r for r in rows if when(r['retrievedAt']) <= now]
    return usable[-1] if usable else None


def injuries_by_team(context_file):
    out = {}
    for league in ('NFL', 'CFB'):
        block = ((context_file.get('leagues') or {}).get(league) or {}).get('teams') or {}
        for team, data in block.items():
            out[str(team)] = {str(p['id']): {'status': p.get('status'), 'position': p.get('position'), 'name': p.get('name')}
                              for p in data.get('players', []) if p.get('id')}
    return out


def roster_facts(records, now):
    """appearances, established, names, player_team and starters from the box-score store as of now."""
    current = {}
    for game in records:
        current[game['league']] = max(current.get(game['league'], 0), game['season'])
    appearances, last_season, names, player_team = defaultdict(int), defaultdict(int), {}, {}
    latest_game, passers = {}, {}
    for game in sorted(records, key=lambda g: g['kickoff']):
        if when(game['kickoff']) > now:
            continue
        season = current[game['league']]
        for player in game['players']:
            pid = str(player['id'])
            if player.get('name'):
                names[pid] = player['name']
            if player.get('team') is not None:
                player_team[pid] = str(player['team'])
            if game['season'] == season:
                appearances[pid] += 1
            elif game['season'] == season - 1 and player.get('team') is not None:
                last_season[(pid, str(player['team']))] += 1
        for side in ('home', 'away'):
            team = str(game[side]['id'])
            throwers = [p for p in game['players'] if str(p.get('team')) == team and (p.get('att') or 0) > 0]
            if throwers:
                latest_game[team] = game['kickoff']
                passers[team] = str(max(throwers, key=lambda p: p.get('att') or 0)['id'])
    established = {key for key, n in last_season.items() if n >= build_site.ESTABLISHED_GAMES}
    return appearances, established, names, player_team, passers


def context(now, stores, flags=None):
    """The gates' view of the world as of `now`, from loaded stores."""
    games = {g['id']: g for g in stores.slate.get('games', []) if g.get('league') in ('NFL', 'CFB')}
    reports = [r for r in stores.reports if r.get('publishedAt') and when(r['publishedAt']) <= now]
    first, latest = build_site.first_publications(reports)
    appearances, established, names, player_team, starters = roster_facts(stores.records, now)
    return Context(now=now, games=games,
                   odds={g: r for g, rows in stores.odds.items() if (r := latest_before(rows, now))},
                   prop_odds={g: r for g, rows in stores.prop_odds.items() if (r := latest_before(rows, now))},
                   snapshots=stores.snapshots, injuries=injuries_by_team(stores.context_file),
                   scoreboard=stores.scoreboard, first=first, latest=latest, appearances=appearances,
                   established=established, names=names, player_team=player_team, starters=starters,
                   flags=dict(FLAGS, **(flags or {})), policy=learning.load_policy(stores.root / 'data' / 'learning' / 'policy.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('candidate', help='JSON file holding one candidate pick (RESEARCH.md fields)')
    parser.add_argument('--now', help='evaluate as of this UTC instant instead of the clock')
    parser.add_argument('--league', help="the candidate's league when the file does not say", choices=('NFL', 'CFB'))
    args = parser.parse_args(argv)
    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    if args.league:
        candidate.setdefault('league', args.league)
    now = when(args.now) if args.now else datetime.now(timezone.utc)
    ctx = Stores().as_of(now)
    ok, decisions = admit(candidate, ctx)
    for decision in decisions:
        print(decision)
    print('ADMITTED' if ok else f'REFUSED on {len(refusals(decisions))} rule(s)')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
