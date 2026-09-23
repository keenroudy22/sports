"""The scheduled research run, in code. PROMPT.md's twelve steps, deterministic where they can be.

  python scripts/run.py [--slot HHMM] [--now ISO] [--dry-run] [--no-llm] [--no-push]
                        [--record-screens] [--publish-kinds settle,close,lean,prop,longshot,favorite]
  python scripts/run.py status
  python scripts/run.py heartbeat

Each run: sync the clone, capture prices, settle finals, close picks whose line moved, build the
board, read the candidates our number likes, price each at the quote with the best expected value,
gather sourced facts, hold anything the facts argue against, run every candidate through the gates
(scripts/gates.py), write one report per league touched, validate, commit and push. The numbers all
come from scripts/pricing.py and the stores; the prose is written from templates, and a local model
may polish it later (scripts/llm_tasks.py) but never adds a number.

A quiet run writes nothing: no report unless something settled, closed or was published. Nothing
here edits an existing file in research/ or touches a ledger. Stdlib only.
"""
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import build_site
import desk
import features
import gates
import llm
import llm_tasks
import parlay
import pricing
import refresh
import scoreboard
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
CONF = Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy'))
EASTERN = gates.EASTERN
SLOT_TOLERANCE = timedelta(minutes=40)     # a run that fires this far from a slot still belongs to it
PUBLISH_MARGIN = timedelta(minutes=5)      # nothing is published on a game this close to kickoff
KINDS = ('settle', 'close', 'lean', 'prop', 'longshot', 'favorite')
WHITELIST = ('research/', 'data/odds/', 'data/prop-odds/', 'data/x-posted.json')
BOOK_SLUG = {'DraftKings': 'dk', 'FanDuel': 'fd', 'BetMGM': 'mgm', 'Caesars': 'czr', 'BetRivers': 'br',
             'ESPN BET': 'espnbet', 'Fanatics': 'fan'}
VOLUME = {'recYds': 'targets', 'rec': 'targets', 'rushYds': 'carries', 'car': 'carries',
          'passYds': 'att', 'cmp': 'att', 'att': 'att'}
SKILL = {'QB', 'RB', 'FB', 'WR', 'TE', 'OT', 'OG', 'C', 'G', 'T', 'OL'}
LONGSHOT_TARGET = 500


class RunError(Exception):
    """A step that stops the run; the reason is reported and nothing further is written."""


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def et(moment, fmt='%-I:%M %p ET'):
    return gates.when(moment).astimezone(EASTERN).strftime(fmt) if isinstance(moment, str) else moment.astimezone(EASTERN).strftime(fmt)


def log(*parts):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]", *parts, flush=True)


# ------------------------------------------------------------------ slot, lock, git

def slot_for(now, forced=None):
    """The scheduled run this instant belongs to, as an Eastern datetime, or None when none is near."""
    local = now.astimezone(EASTERN)
    if forced:
        hour, minute = int(forced[:2]), int(forced[2:])
        return local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    best = None
    for offset in (-1, 0, 1):
        day = (local + timedelta(days=offset)).date()
        for moment in gates.scheduled(day):
            gap = abs(local - moment)
            if gap <= SLOT_TOLERANCE and (best is None or gap < best[0]):
                best = (gap, moment)
    return best[1] if best else None


class Lock:
    def __init__(self, path):
        self.path, self.handle = Path(path), None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, 'w')
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            raise RunError('another run holds the lock')
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def git(*args, cwd=ROOT, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode:
        raise RunError(f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()[:400]}")
    return result


def sync(runner=git):
    """Step 1: a clean tree and a rebase onto the hosted workflow's commits. Never force."""
    dirty = [l for l in runner('status', '--porcelain').stdout.splitlines() if not l.startswith('??')]
    if dirty:
        raise RunError(f'tracked files are modified before the run: {dirty[:5]}')
    runner('pull', '--rebase', '--quiet')


def capture(python=sys.executable):
    """Step 1, continued: price captures when their budget allows. They print why they skip."""
    notes = []
    for script in ('odds_api.py', 'prop_odds.py'):
        result = subprocess.run([python, str(ROOT / 'scripts' / script)], cwd=ROOT, capture_output=True, text=True)
        text = (result.stdout + result.stderr).strip()
        notes.append(f'{script}: {text.splitlines()[-1] if text else "ok"}' + (f' (exit {result.returncode})' if result.returncode else ''))
    return notes


# ------------------------------------------------------------------ games and stores

def fetch_days(league, days, opener=None):
    """ESPN's public scoreboard, one request per day; a date range that touches today is refused with a 400."""
    import urllib.request
    opener = opener or (lambda url: json.load(urllib.request.urlopen(url, timeout=30)))
    slug = 'nfl' if league == 'NFL' else 'college-football'
    events = {}
    for day in days:
        url = f'https://site.api.espn.com/apis/site/v2/sports/football/{slug}/scoreboard?dates={day:%Y%m%d}&limit=1000'
        if league == 'CFB':
            url += '&groups=80'
        for event in opener(url).get('events') or []:
            events[event['id']] = event
    return list(events.values())


def live_games(now, slate_games, opener=None):
    """The slate with fresh state and scores for games from yesterday to two days out. Never written."""
    games = dict(slate_games)
    days = [(now + timedelta(days=d)).astimezone(EASTERN).date() for d in range(-1, 3)]
    for league in ('NFL', 'CFB'):
        try:
            events = fetch_days(league, days, opener)
        except Exception as error:  # network or provider; the pulled slate stands
            log(f'live {league} scoreboard unavailable ({type(error).__name__}); using the pulled slate')
            continue
        for event in events:
            try:
                game = refresh.normalize(event, league)
            except (KeyError, ValueError, TypeError):
                continue
            if game['id'] in games:
                games[game['id']] = dict(games[game['id']], **{k: game[k] for k in ('state', 'completed', 'status', 'home', 'away')})
                if game.get('market'):
                    games[game['id']]['market'] = game['market']
                    games[game['id']]['marketRetrievedAt'] = stamp(now)
    return games


def score(game, side):
    value = (game.get(side) or {}).get('score')
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def raw_first_publications(reports):
    """Pick id -> (kind, the pick exactly as first written), so a revision starts from the record's own words."""
    out = {}
    for report in sorted(reports, key=lambda r: r.get('publishedAt') or ''):
        for kind in ('props', 'riskyProps', 'gamePicks', 'parlays'):
            for pick in report.get(kind) or []:
                if pick.get('id') and pick['id'] not in out:
                    out[pick['id']] = (kind, dict(pick))
    return out


# ------------------------------------------------------------------ step 2: settle

def box_url(league, event_id):
    return f"https://www.espn.com/{'nfl' if league == 'NFL' else 'college-football'}/boxscore/_/gameId/{event_id}"


def grade_game_pick(pick, game):
    """(result, actual, actualValue) for a spread or total against the final score."""
    home, away = score(game, 'home'), score(game, 'away')
    if home is None or away is None:
        return None
    line, direction = float(pick['line']), str(pick.get('direction') or '').lower()
    actual = f"{game['away'].get('short') or game['away'].get('abbreviation')} {away}, {game['home'].get('short') or game['home'].get('abbreviation')} {home}"
    if pick.get('marketType') == 'spread':
        margin = (home - away) if direction == 'home' else (away - home)
        cover = margin + line
        result = 'win' if cover > 0 else 'push' if cover == 0 else 'loss'
        return result, actual, margin
    total = home + away
    if direction == 'over':
        result = 'win' if total > line else 'push' if total == line else 'loss'
    else:
        result = 'win' if total < line else 'push' if total == line else 'loss'
    return result, actual, total


def grade_prop(pick, record):
    """(result, actual, actualValue) from the box score, or None when the player has no line in it."""
    if not record:
        return None
    athlete = str(pick.get('athleteId') or '')
    player = next((p for p in record.get('players', []) if str(p.get('id')) == athlete), None)
    if player is None:
        return None
    stat = pricing.market_of(pick)
    value = scoreboard.settle_value(player, stat)
    if value is None:
        return None
    line, direction = float(pick['line']), str(pick.get('direction') or '').lower()
    if direction == 'over':
        result = 'win' if value > line else 'push' if value == line else 'loss'
    else:
        result = 'win' if value < line else 'push' if value == line else 'loss'
    words = pricing.WORDS.get(stat, stat)
    return result, f"{player.get('name') or athlete}: {value:g} {words}", value


def leg_pick(leg):
    """A parlay leg as the pick shape grade_game_pick and grade_prop read."""
    market = str(leg.get('market') or '')
    if market in ('point spread', 'total points'):
        return {'marketType': 'spread' if market == 'point spread' else 'total', 'line': leg.get('line'),
                'direction': leg.get('side') or leg.get('direction')}
    athlete = leg.get('athleteId') or (re.match(r'prop-[A-Z]+-\d+-(\d+)-', str(leg.get('id') or '')) or [None, None])[1]
    return {'athleteId': athlete, 'market': market, 'title': leg.get('title'), 'line': leg.get('line'),
            'direction': leg.get('side') or leg.get('direction')}


def settle(ctx, raw_first, games, records, now, fetch=boxscores.fetch_game):
    """Revisions for every unsettled pick whose game is final. Unclear outcomes are reported, not guessed."""
    revisions, unclear = [], []
    by_event = {f"{g['league']}-{g['eventId']}": g for g in records}
    fetched = {}

    def record_for(game):
        key = game['id']
        if key in by_event:
            return by_event[key]
        if key not in fetched:
            try:
                fetched[key] = fetch(game['league'], key.split('-', 1)[1])
            except Exception as error:
                log(f'box score for {key} unavailable ({type(error).__name__})')
                fetched[key] = None
        return fetched[key]

    for key, pick in ctx.first.items():
        recent = ctx.latest.get(key, {})
        if pick.get('historicalImport') or recent.get('result') or recent.get('status') in ('settled', 'withdrawn', 'historical'):
            continue
        ids = pick.get('gameIds') or []
        played = [games.get(g) for g in ids]
        if not ids or not all(g and g.get('completed') for g in played):
            continue
        kind, original = raw_first[key]
        league, reason = pick.get('league'), None
        if kind == 'parlays':
            results = []
            for leg in original.get('legs') or []:
                shaped, game = leg_pick(leg), games.get(leg.get('gameId'))
                graded = grade_game_pick(shaped, game) if shaped.get('marketType') else grade_prop(shaped, record_for(game)) if game else None
                results.append(graded[0] if graded else None)
            if any(r == 'loss' for r in results):
                graded, reason = ('loss', f"legs: {', '.join(r or 'unclear' for r in results)}", None), 'One leg lost; the ticket loses.'
            elif all(r == 'win' for r in results):
                graded, reason = ('win', f"all {len(results)} legs won", None), 'Every leg won.'
            else:
                graded = None
        elif kind == 'gamePicks':
            graded = grade_game_pick(original, played[0])
        else:
            graded = grade_prop(original, record_for(played[0]))
        if not graded:
            unclear.append({'id': key, 'why': 'no line for the player in the box score, or a leg that pushed; a person decides'})
            continue
        result, actual, value = graded
        revision = dict(original, status='settled', result=result, actual=actual, settledAt=stamp(now),
                        resultSource=box_url(league, ids[0].split('-', 1)[1]))
        if value is not None:
            revision['actualValue'] = value
        if reason:
            revision['settlementReason'] = reason
        revisions.append((league, kind, revision))
    return revisions, unclear


# ------------------------------------------------------------------ step 3: close moves

def entry_note(now, breaks, pick):
    return (f"Closed to new entries at {et(now)}: {breaks}. Published cutoff: {pick.get('cutoff') or 'as posted'}. "
            f"Stays in the record at {pricing.fmt(float(pick['line'])) if pick.get('line') is not None else 'its line'} and "
            f"{int(pick['odds']):+d} and is graded as posted.")


def close_moves(ctx, raw_first, games, boards, now):
    """Revisions marking picks closed to new entries, from the feed (desk.moves) and the pick's own book."""
    picks = build_site.board_picks(ctx.first, ctx.latest, games, {})
    for row in picks:
        original = ctx.first[row['id']]
        row['marketType'], row['market'] = original.get('marketType'), original.get('market')
    rows = {r['id']: r for r in desk.moves(picks, games, boards, now)}
    revisions, checks = [], []
    for key, row in rows.items():
        pick = ctx.first[key]
        breaks = row['breaks'] if row['breaks'] != 'no comparable current line' else None
        # The pick's own book: the same number at a worse price, or the number moved, in the latest capture.
        kind = 'prop' if pick.get('athleteId') else pick.get('marketType')
        for book, line, odds in gates.quotes_for(dict(pick, _quotes=None), ctx):
            if book != pick.get('book') or pick.get('line') is None:
                continue
            moved = desk.breaks(kind, gates.side_of(pick), float(pick['line']), line, pick.get('odds'), odds)
            if moved:
                breaks = breaks or f'{moved} at {book}'
        if breaks:
            kind_key, original = raw_first[key]
            revisions.append((pick.get('league'), kind_key, dict(original, status='expired', entryNote=entry_note(now, breaks, original))))
        elif row['breaks'] == 'no comparable current line':
            checks.append(key)
    return revisions, checks


# ------------------------------------------------------------------ steps 4 to 7: candidates, prices, facts

def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-')


def line_slug(line):
    return f'{float(line):g}'.replace('.', '-').replace('-', 'minus-', 1) if float(line) < 0 else f'{float(line):g}'.replace('.', '-')


def candidates(lines, games, now):
    """Board rows our number likes, as unpriced candidate picks."""
    out = []
    for row in lines:
        game = games.get(row.get('gameId'))
        grade = row.get('grade') or {}
        if not game or row.get('state') != 'open' or game.get('state') != 'pre' or not grade:
            continue
        if gates.when(game['kickoff']) <= now + PUBLISH_MARGIN:
            continue
        books = [(q['book'], q['line'], q.get('odds')) for q in row.get('books') or []
                 if isinstance(q.get('odds'), (int, float))] or [(row['book'], row['line'], row.get('odds'))]
        if row.get('gameMarket'):
            if row.get('market') != 'total points' or grade.get('tier') not in ('lean', 'strong'):
                continue
            out.append({'status': 'active', 'favorite': False, 'modelLean': True, 'marketType': 'total',
                        'line': row['line'], 'direction': row['direction'], 'gameIds': [game['id']],
                        '_league': game['league'], '_row': row, '_quotes': books})
        elif row.get('athleteId') and grade.get('tier') == 'lean':
            out.append({'status': 'active', 'favorite': False, 'modelLean': True, 'position': row.get('position'),
                        'athleteId': str(row['athleteId']), 'market': row.get('stat') or pricing.market_of(row),
                        'line': row['line'], 'direction': row['direction'], 'gameIds': [game['id']],
                        '_league': game['league'], '_player': row.get('player'), '_row': row, '_quotes': books})
    # The strongest reads first, so a daily cap admits the best of them.
    out.sort(key=lambda c: -((c['_row'].get('grade') or {}).get('edge') or 0))
    return out


def longshot_candidate(lines, games, now, league, exclude=()):
    ticket, reason = parlay.build(lines, now, None, LONGSHOT_TARGET, league, exclude)
    if not ticket:
        return None, reason
    first = games.get(ticket['gameIds'][0]) or {}
    day = eastern_date(now)
    return {'id': f"{league}-{first.get('season', day.year)}-W{first.get('week', 0)}-longshot-{day:%m%d}-{BOOK_SLUG.get(ticket['book'], slug(ticket['book']))}",
            'title': f"{len(ticket['legs'])}-leg longshot at {ticket['book']}", 'status': 'active', 'favorite': False,
            'parlayType': 'longshot', 'riskUnits': parlay.STAKE, 'legs': ticket['legs'],
            'correlation': 'One leg per game, so the ticket treats the legs as independent; its chance is their product.',
            'gameIds': ticket['gameIds'], '_league': league, 'book': ticket['book'], 'odds': ticket['odds'],
            'quotedAt': ticket['quotedAt'], 'quoteType': 'capture', 'confidence': 1,
            'edge': (f"Our chance {100 * ticket['fairChance']:.1f}% against {100 * ticket['breakEven']:.1f}% break-even at "
                     f"{ticket['odds']:+d}: {ticket['evPerUnit']:+.3f}u per unit staked, {parlay.STAKE}u at risk."),
            'cutoff': 'A longshot is not re-entered. It stands or falls as posted.',
            'sources': sorted({games[g]['source'] for g in ticket['gameIds'] if g in games and games[g].get('source')} | {row['source'] for row in lines if row.get('id') in {l['id'] for l in ticket['legs']} and row.get('source')})}, None


def price(candidate, ctx, now):
    """Take the quote with the best expected value; copy the desk's numbers verbatim."""
    game = ctx.games[candidate['gameIds'][0]]
    snapshot = ctx.snapshot(game['id'])
    market, side = gates.market_key(candidate), gates.side_of(candidate)
    if not snapshot or not market:
        return None
    priced = []
    for book, line, odds in candidate.get('_quotes') or []:
        if not isinstance(odds, (int, float)) or abs(odds) < 100:
            continue
        try:
            p = pricing.price(snapshot, market, side, float(line), int(odds), candidate.get('athleteId'))
        except (ValueError, KeyError):
            continue
        priced.append((p['evPerUnit'], book, float(line), int(odds), p))
    if not priced:
        return None
    _, book, line, odds, p = max(priced, key=lambda q: (q[0], q[1]))
    row = candidate.get('_row') or {}
    books = sorted({b for b, _, _ in candidate.get('_quotes') or []})
    seen = row.get('observedAt') or stamp(now)
    note = f"{book}'s number and price from the {et(seen)} capture across {len(books)} book{'s' if len(books) != 1 else ''}"
    note += ', the best expected value on the board for this side.' if len(books) > 1 else f'; {book} is the only book with this market so far.'
    kickoff = gates.when(game['kickoff'])
    candidate.update(book=book, line=line, odds=odds, _desk=p, projection=p['projection'], edge=p['edge'],
                     cutoff=p['cutoff'], modelVersion=p['model'], snapshotAt=p['snapshotAt'], quotedAt=seen,
                     quoteType='capture', quoteNote=note, expiresAt=stamp(min(gates.next_slot(now), kickoff)))
    away, home = game['away'], game['home']
    if candidate.get('athleteId'):
        words = pricing.WORDS[market]
        name = candidate.get('_player') or ctx.names.get(candidate['athleteId'], 'Player')
        candidate['title'] = f"{name} {side.upper()} {pricing.fmt(line)} {words}"
        last = slug(name.split()[-1] if name.split() and name != 'Player' else candidate['athleteId'])
        candidate['id'] = f"{game['league']}-{game['season']}-W{game.get('week', 0)}-{last}-{side}-{line_slug(line)}-{market.lower()}-{BOOK_SLUG.get(book, slug(book))}"
        candidate['confidence'] = 2
    else:
        candidate['title'] = f"{away.get('short') or away['abbreviation']} at {home.get('short') or home['abbreviation']} {side} {pricing.fmt(line)}"
        candidate['id'] = (f"{game['league']}-{game['season']}-W{game.get('week', 0)}-{away['abbreviation'].lower()}-"
                           f"{home['abbreviation'].lower()}-{side}-{line_slug(line)}-{BOOK_SLUG.get(book, slug(book))}")
        candidate['confidence'] = 3 if p['edgePoints'] >= gates.LEAN_STRONG else 2
    sources = [game.get('source')] if game.get('source') else []
    if row.get('source'):
        sources.append(str(row['source']).split(' ')[0])
    candidate['sources'] = [s for s in sources if s and s.startswith('https://')] or [f"https://www.espn.com/{'nfl' if game['league'] == 'NFL' else 'college-football'}/game/_/gameId/{game['id'].split('-', 1)[1]}"]
    return candidate


def evidence(candidate, ctx, context_file):
    """Sourced facts about the game: injury listings from ESPN's report and the line's move since open."""
    game = ctx.games[candidate['gameIds'][0]]
    facts = []
    checked = ((context_file.get('leagues') or {}).get(game['league']) or {}).get('checkedAt')
    athlete, market = str(candidate.get('athleteId') or ''), gates.market_key(candidate)
    for side in ('home', 'away'):
        team = str(game[side]['id'])
        block = ((((context_file.get('leagues') or {}).get(game['league']) or {}).get('teams') or {}).get(team) or {})
        for player in block.get('players', []):
            status = str(player.get('status') or '').lower()
            if not status or status == 'active':
                continue
            direction = 'neutral'
            if str(player.get('id')) == athlete:
                direction = 'against'
            elif player.get('position') == 'QB' and status in gates.QB_OUT and (market == 'total' or ctx.player_team.get(athlete) == team):
                direction = 'against'
            claim = f"{player.get('name')} ({player.get('position')}, {game[side]['abbreviation']}) is listed {player.get('status')}"
            if player.get('injury'):
                claim += f", {player['injury']}"
            facts.append({'id': f"injury-{team}-{player.get('id')}", 'kind': 'injury', 'direction': direction, 'claim': claim,
                          'entities': [player.get('name')], 'team': team, 'position': player.get('position'),
                          'status': player.get('status'), 'source': player.get('source') or game.get('source'),
                          'retrievedAt': player.get('reportedAt') or checked or stamp(ctx.now), 'verified': True})
    m = build_site.market(game) or {}
    if m.get('total') is not None and m.get('totalOpen') is not None and game.get('marketRetrievedAt'):
        move = round(m['total'] - m['totalOpen'], 1)
        facts.append({'id': f"market-{game['id']}-total", 'kind': 'market', 'direction': 'neutral',
                      'claim': f"The total opened {pricing.fmt(m['totalOpen'])} and is {pricing.fmt(m['total'])} at {m.get('book')} ({move:+g})",
                      'entities': [], 'source': game.get('source'), 'retrievedAt': game['marketRetrievedAt'], 'verified': True})
    return facts


def hold_reason(candidate, facts):
    """Without a model to weigh the facts, the run holds anything a quarterback listing could turn.

    A quarterback on either team listed at all holds a total; the player's own team's quarterback
    listed holds a prop; three or more skill players out or doubtful on one side holds either.
    """
    game_qbs = [f for f in facts if f.get('kind') == 'injury' and f.get('position') == 'QB']
    if not candidate.get('athleteId') and game_qbs:
        return f"quarterback listed: {game_qbs[0]['claim']}"
    team = candidate.get('_team')
    if candidate.get('athleteId') and any(f['team'] == team for f in game_qbs):
        return f"the player's quarterback is listed: {next(f['claim'] for f in game_qbs if f['team'] == team)}"
    out = defaultdict(int)
    for fact in facts:
        if fact.get('kind') == 'injury' and fact.get('position') in SKILL and str(fact.get('status', '')).lower() in gates.QB_OUT:
            out[fact['team']] += 1
    heavy = [team for team, n in out.items() if n >= 3]
    if heavy:
        return f'{out[heavy[0]]} skill players out or doubtful on one side'
    return None


def judge(candidate, facts, use_llm, status=None):
    """Why the run holds a candidate, or None. The model weighs the facts when it is up; a rule of thumb when not.

    The model's word counts only when it points at a fact. Unsure means hold: a lean the facts might
    turn is not worth publishing on the number alone.
    """
    if use_llm:
        verdict = llm_tasks.judge_against(candidate, facts)
        if verdict is not None:
            if status is not None:
                status['llm']['judged'] += 1
            if verdict['argues_against'] and verdict['fact_ids']:
                return f"the evidence argues against it: {verdict['note']}"
            if verdict['confidence'] == 'low':
                return f"the judge is unsure: {verdict['note']}"
            return None
        if status is not None:
            status['llm']['unavailable'] = status['llm'].get('unavailable', 0) + 1
    return hold_reason(candidate, facts)


def polish(candidate, facts, status):
    """The model's rewrite of the templated why and risk, through both guards; the template stands otherwise."""
    for key, task in (('why', llm_tasks.why_for), ('risk', llm_tasks.risk_for)):
        text, note = task(candidate, facts)
        candidate[key] = text
        status['llm']['polished' if note == 'polished' else 'kept'] += 1
        if note != 'polished':
            log(f"  {key} template kept for {candidate.get('title')}: {note}")


# ------------------------------------------------------------------ step 8: prose

def prop_reasoning(candidate, ctx, records, snapshot):
    """Last 10 at the number, the player's place among teammates by projected volume, and what the defense allows."""
    athlete, market, side = str(candidate['athleteId']), gates.market_key(candidate), gates.side_of(candidate)
    line = float(candidate['line'])
    game = ctx.games[candidate['gameIds'][0]]
    league_records = [g for g in records if g['league'] == game['league']]
    logs = features.player_logs(league_records).get(athlete, [])
    recent = [features.value(r, market) for r in logs[-10:]]
    recent = [v for v in recent if v is not None]
    hits = sum(1 for v in recent if (v > line if side == 'over' else v < line))
    parts = [f"Last {len(recent)} games: {hits} of {len(recent)} {side} {pricing.fmt(line)}." if recent else 'No stored games for the player yet.']
    team_side, player = pricing.player_line(snapshot, athlete)
    volume = VOLUME.get(market)
    if team_side and player and volume:
        mates = [(p.get(volume, [0])[0], p['id']) for p in snapshot['players'][team_side]['players']
                 if features.GROUP.get(p.get('pos')) == features.GROUP.get(player.get('pos')) and p.get(volume)]
        mates.sort(reverse=True)
        rank = next((i for i, (_, pid) in enumerate(mates, 1) if pid == athlete), None)
        if rank:
            parts.append(f"Role: {rank}{'st' if rank == 1 else 'nd' if rank == 2 else 'rd' if rank == 3 else 'th'} of {len(mates)} "
                         f"{game[team_side]['abbreviation']} {features.GROUP.get(player.get('pos'))}s by projected {volume}, {player[volume][0]:.1f} a game.")
        opponent = game['away' if team_side == 'home' else 'home']
        group = features.GROUP.get(player.get('pos'))
        table = features.defense_table(features.defense_logs(league_records), f'{group}.{market}', season=game['season'])
        row = next((r for r in table if str(r['defense']) == str(opponent['id'])), None)
        if row:
            parts.append(f"Defense: {opponent['abbreviation']} allows {row['avg']:g} {pricing.WORDS[market]} a game to {group}s, "
                         f"{row['rank']} of {len(table)} this season (1 is stingiest).")
    return ' '.join(parts)


def write_prose(candidate, ctx, records):
    """Template why and risk from the pick's own numbers. A model may polish these later; it never adds a number."""
    p = candidate.get('_desk') or {}
    snapshot = ctx.snapshot(candidate['gameIds'][0])
    side, line, odds = gates.side_of(candidate), float(candidate['line']), int(candidate['odds'])
    if candidate.get('legs'):
        candidate['why'] = (f"Longshot from the board: {len(candidate['legs'])} legs at {candidate['book']}, each at the number our "
                            f"model graded, one per game. A fun ticket at a quarter unit, tracked apart from the straight picks.")
        candidate['risk'] = 'Most longshots lose. The legs are treated as independent; any one miss sinks the ticket. Confidence 1 of 10.'
        return candidate
    sparse = 'A team with under three games this season thins the read. ' if snapshot and snapshot.get('sparse') else ''
    if candidate.get('athleteId'):
        candidate['why'] = (f"Prop lean on our number alone: our projection is {p['projection']:g} against {pricing.fmt(line)} and the "
                            f"{side} reads {100 * p['rawChance']:.1f}% on the raw curve, which has no graded history against a line yet, "
                            f"so the true chance is lower than that. {prop_reasoning(candidate, ctx, records, snapshot)}")
        games_played = ctx.appearances.get(candidate['athleteId'], 0)
        candidate['risk'] = (f"Uncalibrated chance; a player line turns on a handful of touches. {games_played} games this season"
                             f"{'' if games_played >= 3 else ', the role settled by last season'}. A player who does not take the field is "
                             f"voided under the book's rule; one who leaves hurt is graded. Confidence {candidate['confidence']} of 10.")
    else:
        candidate['why'] = (f"Model lean, published on our number alone. Our total is {p['projection']:g} against {pricing.fmt(line)}: the "
                            f"{side} reads {100 * p['chance']:.1f}% after the raw {100 * p['rawChance']:.1f}% is shrunk by the model's "
                            f"record against the close, {p['edgePoints']:+.1f} points clear of the {100 * p['breakEven']:.1f}% that "
                            f"{odds:+d} needs. Nothing sourced argues against it; the number is the reason.")
        candidate['risk'] = (f"It rests on the model alone, and the closing line beats our number on average, so a gap this size is more "
                             f"often our error than the market's. {sparse}Confidence {candidate['confidence']} of 10.")
    return candidate


# ------------------------------------------------------------------ steps 8 to 11: reports, validation, git

def report_slug(settled, closed, published):
    kinds = set()
    for _, kind, pick in published:
        kinds.add('longshot' if pick.get('legs') else 'prop-leans' if pick.get('athleteId') else 'model-leans')
    if len(kinds) == 1 and not settled and not closed:
        return kinds.pop()
    if settled and not closed and not published:
        return 'settlement'
    if closed and not settled and not published:
        return 'closes'
    return 'run'


def summary_text(slot, now, settled, closed, published, screened, unclear, captures):
    lines = [f"{slot.strftime('%-I:%M %p')} ET run, published at {et(now)}."]
    lines.append(f"Settled {len(settled)}: " + '; '.join(f"{p.get('title')} {p['result']}" for _, _, p in settled) + '.' if settled else 'Nothing to settle.')
    lines.append(f"Closed {len(closed)}: " + '; '.join(p.get('title') or p['id'] for _, _, p in closed) + '.' if closed else 'Nothing to close.')
    if published:
        lines.append(f"Published {len(published)}: " + '; '.join(f"{p['title']} {p['odds']:+d} at {p['book']}" for _, _, p in published) + '.')
    else:
        lines.append('Nothing published.')
    if screened:
        shown = '; '.join(f"{s['title']} ({s['rule']})" for s in screened[:8])
        more = f'; and {len(screened) - 8} more' if len(screened) > 8 else ''
        lines.append(f'Screened and passed on {len(screened)}: {shown}{more}.')
    if unclear:
        lines.append(f"Awaiting a person: {', '.join(u['id'] for u in unclear)}.")
    notes = [c for c in captures if not c.endswith(': ok') and 'dry run' not in c]
    if notes:
        lines.append(' '.join(notes))
    return ' '.join(lines)


def build_reports(league_items, slot, now, screened, unclear, captures, target_weeks, record_screens):
    """One report per league that has something to say."""
    reports = {}
    for league, (settled, closed, published) in league_items.items():
        if not settled and not closed and not published:
            continue
        report = {'league': league, 'publishedAt': stamp(now)}
        if target_weeks.get(league) is not None:
            report['targetWeek'] = target_weeks[league]
        own_screened = [s for s in screened if s['league'] == league]
        report['summary'] = summary_text(slot, now, settled, closed, published, own_screened, [u for u in unclear if u.get('league') == league], captures)
        report['takeaways'] = []
        for kind in ('props', 'riskyProps', 'gamePicks', 'parlays'):
            picks = [p for _, k, p in settled + closed + published if k == kind]
            if picks:
                report[kind] = [{k: v for k, v in p.items() if not k.startswith('_')} for p in picks]
        if record_screens and own_screened:
            report['screened'] = [{k: s[k] for k in ('gameId', 'title', 'rule', 'reason')} for s in own_screened]
        name = f"{eastern_date(now).isoformat()}-{league}-{now.astimezone(EASTERN):%H%M}-{report_slug(settled, closed, published)}.json"
        reports[name] = report
    return reports


def validate(new_reports, all_reports, games):
    for name, report in new_reports.items():
        try:
            refresh.validate_report(json.loads(json.dumps(report)), games)
        except AssertionError as error:
            raise RunError(f'{name} fails validation: {error}')
    try:
        refresh.validate_ledger([json.loads(json.dumps(r)) for r in all_reports + list(new_reports.values())])
    except AssertionError as error:
        raise RunError(f'the record would change: {error}')


def run_tests(python=sys.executable):
    py = subprocess.run([python, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=ROOT, capture_output=True, text=True)
    if py.returncode:
        raise RunError('unit tests failed:\n' + py.stderr[-1500:])
    node = subprocess.run(['node', '--test', *sorted(str(p) for p in (ROOT / 'tests').glob('*.test.js'))], cwd=ROOT, capture_output=True, text=True)
    if node.returncode:
        raise RunError('node tests failed:\n' + (node.stderr or node.stdout)[-1500:])


def allowed(path):
    return any(path == w.rstrip('/') or path.startswith(w) for w in WHITELIST)


def commit_push(now, slot, counts, push=True, runner=git, cwd=ROOT):
    """Commit only whitelisted paths, in two commits, then push; rebase once on rejection, never force."""
    changed = []
    for line in runner('status', '--porcelain', cwd=cwd).stdout.splitlines():
        path = line[3:].strip().strip('"')
        if allowed(path):
            changed.append(path)
        elif not line.startswith('??'):
            runner('restore', '--worktree', '--', path, cwd=cwd, check=False)
    captures = [p for p in changed if p.startswith('data/')]
    research = [p for p in changed if not p.startswith('data/')]
    if captures:
        runner('add', '--', *captures, cwd=cwd)
        runner('commit', '--quiet', '-m', f"Odds capture {eastern_date(now).isoformat()} {now.astimezone(EASTERN):%H:%M} ET", cwd=cwd)
    if research:
        runner('add', '--', *research, cwd=cwd)
        message = (f"Research {eastern_date(now).isoformat()} {now.astimezone(EASTERN):%H:%M} ET: {counts['published']} published, "
                   f"{counts['settled']} settled, {counts['closed']} closed")
        runner('commit', '--quiet', '-m', message, cwd=cwd)
    if not push or not (captures or research):
        return {'committed': bool(captures or research), 'pushed': False}
    result = runner('push', '--quiet', cwd=cwd, check=False)
    if result.returncode:
        rebase = runner('pull', '--rebase', '--quiet', cwd=cwd, check=False)
        if rebase.returncode:
            runner('rebase', '--abort', cwd=cwd, check=False)
            raise RunError('push rejected and the rebase conflicted; the commits stay local for the next run')
        runner('push', '--quiet', cwd=cwd)
    return {'committed': True, 'pushed': True}


# ------------------------------------------------------------------ the run

def load_json(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback


def write_status(status, path=None):
    path = path or CONF / 'status.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=1, default=str) + '\n', encoding='utf-8')


def run(args):
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    slot = slot_for(now, args.slot)
    status = {'startedAt': stamp(now), 'slot': slot.strftime('%H%M') if slot else None, 'dryRun': args.dry_run,
              'outcome': 'started', 'settled': 0, 'closed': 0, 'published': 0, 'screened': [], 'unclear': [], 'errors': [],
              'checks': [], 'llm': {'used': False}, 'x': {'drafted': 0, 'posted': 0}}
    if slot is None:
        log('no scheduled run within 40 minutes of', et(now), '; nothing to do')
        status['outcome'] = 'unscheduled'
        write_status(status)
        return 0
    kinds = set(args.publish_kinds.split(',')) if args.publish_kinds else set(KINDS)
    try:
        with Lock(CONF / 'run.lock'):
            return _run(args, now, slot, kinds, status)
    except RunError as error:
        log('STOPPED:', error)
        status.update(outcome=f'failed: {error}', finishedAt=stamp(datetime.now(timezone.utc)))
        status['errors'].append(str(error))
        write_status(status)
        return 1
    except Exception:
        text = traceback.format_exc()
        log('CRASHED:\n' + text)
        status.update(outcome='crashed', finishedAt=stamp(datetime.now(timezone.utc)))
        status['errors'].append(text[-1500:])
        write_status(status)
        return 2


def _run(args, now, slot, kinds, status):
    log(f"run for the {slot.strftime('%-I:%M %p')} ET slot at {et(now)}" + (' (dry run)' if args.dry_run else ''))
    if not args.dry_run:
        sync()
        status['checks'].append('synced')
        captures = capture()
    else:
        captures = ['dry run: no capture']
    for note in captures:
        log(note)
    slate = load_json(ROOT / 'site' / 'data' / 'slate.json', {'games': []})
    slate_games = {g['id']: g for g in slate.get('games', []) if g.get('league') in ('NFL', 'CFB')}
    games = live_games(now, slate_games)
    records = features.load()
    stores = gates.Stores(records=records)
    ctx = stores.as_of(now)
    ctx.games = games
    raw_first = raw_first_publications(stores.reports)
    context_file = stores.context_file
    settled, closed, published, screened, unclear = [], [], [], [], []
    use_llm = not args.no_llm and llm.available()
    status['llm'] = {'used': use_llm, 'model': llm.model_name() if use_llm else None, 'polished': 0, 'kept': 0, 'judged': 0}
    log('local model:', f"{llm.model_name()} at {llm.base_url()}" if use_llm else 'off' if args.no_llm else 'not reachable; templates only')

    if 'settle' in kinds:
        settled, unclear = settle(ctx, raw_first, games, records, now)
        for u in unclear:
            u['league'] = ctx.first[u['id']].get('league')
        log(f'settled {len(settled)}, unclear {len(unclear)}')
    if 'close' in kinds:
        closed, checks = close_moves(ctx, raw_first, games, desk.captures(), now)
        status['checks'] += [f'CHECK {k}: no comparable current line' for k in checks]
        log(f'closed {len(closed)}, to check by hand {len(checks)}')

    build_site.build(now)
    lines = load_json(build_site.OUT / 'lines.json', {'lines': []})['lines']
    wanted = candidates(lines, games, now)
    log(f'{len(wanted)} candidates on the board')
    for candidate in wanted:
        want = 'prop' if candidate.get('athleteId') else 'lean'
        if want not in kinds:
            continue
        if price(candidate, ctx, now) is None:
            continue
        candidate['_team'] = ctx.player_team.get(candidate.get('athleteId', ''))
        facts = evidence(candidate, ctx, context_file)
        candidate['_evidence'] = facts
        hold = judge(candidate, facts, use_llm, status)
        league = candidate['_league']
        if hold:
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'rule': 'held', 'reason': hold})
            continue
        write_prose(candidate, ctx, records)
        ok, decisions = gates.admit(dict(candidate, league=league), ctx)
        if ok and use_llm:
            polish(candidate, facts, status)
        for decision in decisions:
            if decision.rule == 'one_book' and decision.data.get('quoteNoteRequired'):
                candidate['quoteNote'] += f" {candidate['book']} is the only book with this market; kickoff is inside three hours."
            if decision.rule == 'cfb_jurisdiction' and decision.data.get('jurisdictionVerified'):
                candidate['jurisdictionVerified'] = True
        if not ok:
            first = gates.refusals(decisions)[0]
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'rule': first.rule, 'reason': first.reason})
            continue
        # Admitted picks join the day's count so the caps hold within one run.
        kind = 'props' if candidate.get('athleteId') else 'gamePicks'
        ctx.first[candidate['id']] = dict(candidate, league=league, publishedAt=stamp(now), kind=kind)
        ctx.latest[candidate['id']] = dict(candidate)
        published.append((league, kind, candidate))
    if 'longshot' in kinds:
        for league in ('NFL', 'CFB'):
            ticket, reason = longshot_candidate(lines, games, now, league)
            if not ticket:
                log(f'{league} longshot: {reason}')
                continue
            write_prose(ticket, ctx, records)
            ok, decisions = gates.admit(dict(ticket, league=league), ctx)
            if ok:
                ctx.first[ticket['id']] = dict(ticket, league=league, publishedAt=stamp(now), kind='parlays')
                published.append((league, 'parlays', ticket))
                break
            screened.append({'league': league, 'gameId': ticket['gameIds'][0], 'title': ticket['title'],
                             'rule': gates.refusals(decisions)[0].rule, 'reason': gates.refusals(decisions)[0].reason})

    by_league = defaultdict(lambda: ([], [], []))
    for item in settled:
        by_league[item[0]][0].append(item)
    for item in closed:
        by_league[item[0]][1].append(item)
    for item in published:
        by_league[item[0]][2].append(item)
    target_weeks = {}
    for league in by_league:
        weeks = [games[g]['week'] for g in games if games[g]['league'] == league and games[g].get('state') == 'pre' and 'week' in games[g]]
        target_weeks[league] = min(weeks) if weeks else None
    reports = build_reports(dict(by_league), slot, now, screened, unclear, captures, target_weeks, args.record_screens)
    status.update(settled=len(settled), closed=len(closed), published=len(published), screened=screened, unclear=unclear,
                  reports=list(reports))
    if not reports:
        log('quiet run: nothing settled, closed or published; no report written')
    else:
        validate(reports, stores.reports, games)
        out = (CONF / 'pending') if args.dry_run else (ROOT / 'research')
        out.mkdir(parents=True, exist_ok=True)
        for name, report in reports.items():
            target = out / name
            if target.exists():
                target = out / name.replace('.json', '-2.json')
            target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            log('wrote', target)
        if not args.dry_run:
            run_tests()
            status['checks'].append('tests green')
    if not args.dry_run:
        git_result = commit_push(now, slot, {'published': len(published), 'settled': len(settled), 'closed': len(closed)},
                                 push=not args.no_push)
        status['git'] = git_result
        log('git:', git_result)
    status.update(outcome='ok', finishedAt=stamp(datetime.now(timezone.utc)))
    write_status(status)
    log(f"done: {len(settled)} settled, {len(closed)} closed, {len(published)} published, {len(screened)} screened")
    for s in screened:
        log(f"  screened {s['title']}: {s['rule']}: {s['reason']}")
    return 0


# ------------------------------------------------------------------ status and heartbeat

def heartbeat(args):
    """Speak only when something is wrong."""
    now = datetime.now(timezone.utc)
    problems = []
    status = load_json(CONF / 'status.json', None)
    if not status:
        problems.append('no run has written status.json yet')
    else:
        if str(status.get('outcome', '')).startswith(('failed', 'crashed')):
            problems.append(f"last run {status.get('outcome')}")
        finished = status.get('finishedAt')
        if not finished or now - gates.when(finished) > timedelta(hours=26):
            problems.append(f"no run finished in 26 hours (last {finished or 'never'})")
    dirty = git('status', '--porcelain', check=False).stdout.splitlines()
    if [l for l in dirty if not l.startswith('??')]:
        problems.append('tracked files are modified in the clone')
    account = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True, env={**os.environ, 'GH_CONFIG_DIR': str(CONF / 'gh')})
    if 'keenroudy22' not in (account.stdout + account.stderr):
        problems.append('gh is not logged in as keenroudy22 in the sports config dir')
    try:
        import urllib.request
        urllib.request.urlopen('http://localhost:11434/api/version', timeout=3).read()
    except Exception:
        problems.append('Ollama is not reachable')
    zone = os.path.realpath('/etc/localtime')
    if not any(z in zone for z in ('New_York', 'Indianapolis', 'Detroit', 'US/Eastern', 'EST5EDT')):
        problems.append(f'the machine is not on Eastern time ({zone})')
    alert = CONF.parent.parent / 'Library' / 'Logs' / 'KeenRoudy' / 'ALERT.txt'
    if problems:
        text = f"KeenRoudy Sports heartbeat {stamp(now)}\n" + '\n'.join(f'- {p}' for p in problems) + '\n'
        alert.parent.mkdir(parents=True, exist_ok=True)
        alert.write_text(text, encoding='utf-8')
        subprocess.run(['osascript', '-e', f'display notification "{problems[0]}" with title "KeenRoudy Sports"'], capture_output=True)
        print(text)
        return 1
    if alert.exists():
        alert.unlink()
    print('heartbeat: all clear')
    return 0


def show_status(args):
    status = load_json(CONF / 'status.json', None)
    print(json.dumps(status, indent=1) if status else 'no status yet')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', nargs='?', default='run', choices=('run', 'status', 'heartbeat'))
    parser.add_argument('--slot', help='force the run slot, HHMM Eastern')
    parser.add_argument('--now', help='pretend it is this UTC instant')
    parser.add_argument('--dry-run', action='store_true', help='no sync, capture, git; reports go to the pending folder')
    parser.add_argument('--no-llm', action='store_true', help='templates only, no local model')
    parser.add_argument('--no-push', action='store_true', help='commit but do not push')
    parser.add_argument('--record-screens', action='store_true', help='list screened candidates in the report')
    parser.add_argument('--publish-kinds', help=f"comma list of {','.join(KINDS)}; default all")
    args = parser.parse_args(argv)
    if args.command == 'heartbeat':
        return heartbeat(args)
    if args.command == 'status':
        return show_status(args)
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
