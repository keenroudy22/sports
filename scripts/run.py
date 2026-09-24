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
import time
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
import market_read
import parlay
import pick_card
import pricing
import refresh
import researcher
import scoreboard
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
CONF = Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy'))
EASTERN = gates.EASTERN
SLOT_TOLERANCE = timedelta(minutes=40)     # a run that fires this far from a slot still belongs to it
PUBLISH_MARGIN = timedelta(minutes=5)      # nothing is published on a game this close to kickoff
KINDS = ('settle', 'close', 'lean', 'prop', 'longshot', 'favorite')
WHITELIST = ('research/', 'data/odds/', 'data/prop-odds/', 'data/x-posted.json', 'data/x-reasons.json', 'data/learning/')
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


LEFTOVER = ('data/odds/', 'data/prop-odds/', 'data/learning/', 'data/x-posted.json', 'data/x-reasons.json')


def sync(runner=git):
    """Step 1: a clean tree and a rebase onto the hosted workflow's commits. Never force.

    A run that stopped after capturing prices leaves the captures uncommitted; they are real records, so they
    are committed here before the pull. Anything else modified stops the run for a person."""
    dirty = [l for l in runner('status', '--porcelain').stdout.splitlines() if not l.startswith('??')]
    leftover = [l[3:].strip().strip('"') for l in dirty if l[3:].strip().strip('"').startswith(LEFTOVER)]
    others = [l for l in dirty if l[3:].strip().strip('"') not in leftover]
    if others:
        raise RunError(f'tracked files are modified before the run: {others[:5]}')
    if leftover:
        runner('add', '--', *leftover)
        runner('commit', '--quiet', '-m', 'Captures left by a stopped run')
        log(f'committed {len(leftover)} capture file(s) a stopped run left behind')
    rebase_onto_remote(runner)


FETCH_RACE = ('cannot lock ref', 'unable to update local ref', 'is at', '.lock')


def fetch(runner=git, cwd=ROOT, attempts=5, wait=3, sleep=time.sleep):
    """Fetch origin/main. Another git client on this machine (the Claude app refreshes the repository in the
    background) can update the same ref at the same second, and git then refuses with "cannot lock ref"; that
    is a race, not a fault, so wait a moment and fetch again. Anything else stops the run as before."""
    for attempt in range(attempts):
        result = runner('fetch', '--quiet', 'origin', 'main', cwd=cwd, check=False)
        if not result.returncode:
            return
        detail = (result.stderr or result.stdout or '').strip()
        if attempt + 1 == attempts or not any(sign in detail for sign in FETCH_RACE):
            raise RunError(f'git fetch --quiet origin main failed: {detail[:400]}')
        log(f'git fetch raced another git client ({detail[:120]}); trying again in {wait} s')
        sleep(wait)


def rebase_onto_remote(runner=git, cwd=ROOT, attempts=6):
    """Fetch and rebase onto origin/main. When both writers captured prices in the same window the rebase
    stops on the store files; scripts/merge_store.py keeps every record from both sides and recomputes the
    ledger, and the rebase goes on. A conflict anywhere else aborts the rebase and stops the run."""
    import merge_store
    fetch(runner, cwd)
    result = runner('rebase', '--quiet', 'origin/main', cwd=cwd, check=False)
    for _ in range(attempts):
        if not result.returncode:
            return
        resolved, left = merge_store.resolve(cwd=cwd, log=log)
        if left or not resolved:
            runner('rebase', '--abort', cwd=cwd, check=False)
            detail = f'outside the stores: {left[:5]}' if left else (result.stderr or result.stdout).strip()[:300]
            raise RunError(f'rebase onto origin/main conflicted {detail}; the local commits stay for a person')
        result = runner('-c', 'core.editor=true', 'rebase', '--continue', cwd=cwd, check=False)
    runner('rebase', '--abort', cwd=cwd, check=False)
    raise RunError('rebase onto origin/main did not finish')


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
        candidate['title'] = f"{pick_card.team_label(away, game['league'])} at {pick_card.team_label(home, game['league'])} {side} {pricing.fmt(line)}"
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
    # The forecast at kickoff for an outdoor game (scripts/weather.py): from the stored line the hosted
    # workflow appended, else a live read. Wind, rain or cold argue against an over and for an under.
    fact = weather_fact(game, candidate, ctx)
    if fact:
        facts.append(fact)
    # The market read (scripts/market_read.py): the move since open, book disagreement, and where our gap
    # sits among the model's gaps. Evidence beside the number, never inside it.
    block = market_read.read(game, ctx.snapshot(game['id']), ctx.odds.get(game['id']), gap_rows())
    words = market_read.sentences(block)
    if words:
        facts.append({'id': f"market-{game['id']}", 'kind': 'market', 'direction': 'neutral', 'claim': words, 'entities': [],
                      'source': game.get('source'), 'retrievedAt': game.get('marketRetrievedAt') or stamp(ctx.now),
                      'verified': True, 'read': block})
    return facts


_WEATHER = {}


def prime_weather(records):
    """Load the venue table, each home team's usual venue and the stored forecasts once per run."""
    import venues
    import weather
    _WEATHER.clear()
    _WEATHER.update(table=venues.load(), usual=venues.usual_venues(records), stored=weather.stored())


def weather_fact(game, candidate, ctx):
    """The weather fact for a game, from the store first, then a live read; None indoors, unknown or far out."""
    import venues
    import weather
    if not _WEATHER:
        prime_weather(features.load())
    venue = venues.venue_for(game, _WEATHER['table'], _WEATHER['usual'])
    if not venue or venue.get('indoor') is not False or venue.get('lat') is None:
        return None
    side = gates.side_of(candidate) if gates.market_key(candidate) == 'total' else None
    line = _WEATHER['stored'].get(game['id'])
    forecast = line.get('forecast') if line else None
    if not forecast:
        try:
            forecast = weather.forecast_for(venue['lat'], venue['lon'], gates.when(game['kickoff']), now=ctx.now)
        except Exception as error:      # the NWS is a courtesy, never a dependency
            log(f"weather for {game['id']} unavailable ({type(error).__name__})")
            return None
    return weather.fact_for(game, venue, forecast, ctx.now, side)


_GAP_ROWS = []


def gap_rows():
    """The model's walk-forward gaps, loaded once per process."""
    if not _GAP_ROWS:
        _GAP_ROWS.extend(market_read.load_rows())
    return _GAP_ROWS


def hold_reason(candidate, facts):
    """Without a model to weigh the facts, the run holds anything a quarterback listing could turn.

    A quarterback on either team listed at all holds a total; the player's own team's quarterback
    listed holds a prop; three or more skill players out or doubtful on one side holds either.
    """
    web = [f for f in facts if f.get('origin') == 'claude researcher' and f.get('direction') == 'against']
    if web:
        return f"verified reporting argues against it: {web[0]['claim']}"
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


BIG_GAP = 6.0               # a college play this far from the market needs the web check before it is published
AVAILABILITY = ('injury', 'role')     # the kinds of verified fact that say who is expected to play
SKILL_OUT = {'out', 'doubtful'}


def needs_research(candidate):
    """College football has no injury feed the desk can read: ESPN lists a handful of players across all of FBS.
    So every college play waits until the web check has come back with who is expected to play; without it the
    desk would know nothing about injuries at all. (The researcher does not always answer; a play it missed is
    held, not published blind.)"""
    league = candidate.get('_league') or candidate.get('league')
    return league == 'CFB' and not candidate.get('legs')


def relevant_facts(candidate, facts, ctx):
    """The facts that can change what this pick depends on. The line's move is not one: the price is already
    taken at the current number, and backtests show a move away from our number does not hurt our side. Long
    injured reserve is in the projections and the market already. What remains: the player's own listing and
    his starting quarterback for a prop; the starting quarterbacks and a side missing several skill players for
    a total; a weather flag for a total; and everything the web researcher verified."""
    athlete = str(candidate.get('athleteId') or '')
    team = candidate.get('_team')
    total = not athlete
    out, skill = [], defaultdict(list)
    for fact in facts:
        kind = fact.get('kind')
        if fact.get('origin') == 'claude researcher':
            out.append(fact)
            continue
        if kind == 'weather':
            if total and fact.get('direction') in ('for', 'against'):
                out.append(fact)
            continue
        if kind != 'injury':
            continue
        status = str(fact.get('status') or '').lower()
        if status in ('injured reserve', 'active', ''):
            continue
        player = str(fact.get('id', '')).rsplit('-', 1)[-1]
        if athlete and player == athlete:
            out.append(fact)
        elif fact.get('position') == 'QB' and (total or fact.get('team') == team) \
                and (ctx.starters.get(str(fact.get('team'))) == player or status in gates.QB_OUT):
            out.append(fact)
        elif total and fact.get('position') in SKILL and status in SKILL_OUT:
            skill[fact.get('team')].append(fact)
    for group in skill.values():
        if len(group) >= 3:
            out += group
    return out


def judge(candidate, facts, use_llm, status=None):
    """Why the run holds a candidate, or None. Only facts that can matter reach the judge (relevant_facts); with
    none there is nothing to weigh and nothing to hold on. A hold must name a fact: the model's answer counts
    only when it points at one. With the model down, a rule of thumb holds instead."""
    if not facts:
        return None
    if use_llm:
        verdict = llm_tasks.judge_against(candidate, facts)
        candidate['_verdict'] = verdict
        if verdict is not None:
            if status is not None:
                status['llm']['judged'] += 1
            if verdict['argues_against'] and verdict['fact_ids']:
                return f"the evidence argues against it: {verdict['note']}"
            return None
        if status is not None:
            status['llm']['unavailable'] = status['llm'].get('unavailable', 0) + 1
    return hold_reason(candidate, facts)


def decision_record(candidate, league, decision, rules, reason, now, ctx):
    """One line of the learning record: what was considered, on what numbers, and what the desk decided."""
    import learning
    import pick_card
    from urllib.parse import urlparse
    desk = candidate.get('_desk') or {}
    game = ctx.games.get((candidate.get('gameIds') or [None])[0]) or {}
    facts = candidate.get('_evidence') or []
    verdict = candidate.get('_verdict') or {}
    row = dict(candidate, league=league)
    return {'id': candidate.get('id'), 'league': league, 'season': game.get('season') or now.year,
            'segment': learning.segment_of(row), 'kind': pick_card.play_kind(row), 'title': candidate.get('title'),
            'marketType': candidate.get('marketType'), 'market': candidate.get('market'), 'athleteId': candidate.get('athleteId'),
            'direction': candidate.get('direction'), 'line': candidate.get('line'), 'odds': candidate.get('odds'),
            'book': candidate.get('book'), 'gameIds': candidate.get('gameIds'), 'kickoff': game.get('kickoff'),
            'legs': len(candidate['legs']) if candidate.get('legs') else None,
            'projection': desk.get('projection'), 'chance': desk.get('chance'), 'rawChance': desk.get('rawChance'),
            'breakEven': desk.get('breakEven'), 'edgePoints': desk.get('edgePoints'), 'evPerUnit': desk.get('evPerUnit'),
            'confidence': candidate.get('confidence'), 'favorite': candidate.get('favorite') is True,
            'decision': decision, 'rules': list(rules), 'reason': reason, 'decidedAt': stamp(now),
            'facts': {'for': sum(1 for f in facts if f.get('direction') == 'for'),
                      'against': sum(1 for f in facts if f.get('direction') == 'against'),
                      'kinds': sorted({str(f.get('kind')) for f in facts if f.get('kind')})},
            'judge': {'against': verdict.get('argues_against'), 'confidence': verdict.get('confidence'),
                      'facts': len(verdict.get('fact_ids') or [])} if verdict else None,
            'research': [{'domain': urlparse(str(f.get('source') or '')).netloc.lower().removeprefix('www.'),
                          'verified': bool(f.get('verified')), 'kind': f.get('kind'), 'direction': f.get('direction')}
                         for f in candidate.get('_research') or []]}


def remember(decided, now, slot, status):
    """Write this run's decisions to the learning record (only what changed since the last time each candidate
    was decided), grade whatever has finished, and on Tuesday morning run the week's learning. Learning never
    fails a run: its errors are reported and the run goes on."""
    import learn
    import learning
    try:
        fresh = {}
        for row in decided:
            if not row.get('id'):
                continue
            season = row['season']
            if season not in fresh:
                last = {}
                for old in learning.read('candidates', season):
                    last[old['id']] = (old['decision'], tuple(old.get('rules') or []))
                fresh[season] = (last, [])
            last, out = fresh[season]
            key = (row['decision'], tuple(row['rules']))
            if last.get(row['id']) != key:
                last[row['id']] = key
                out.append(row)
        recorded = sum(learning.append('candidates', season, out) for season, (_, out) in fresh.items())
        graded = learn.grade_pending(now)
        status['learning'] = {'recorded': recorded, 'graded': graded}
        log(f'learning: {recorded} decisions recorded, {graded} candidates graded')
        if slot.weekday() == 1 and slot.hour == 8:
            report = learn.weekly(now)
            status['learning']['changes'] = len(report['changes'])
            log(f"learning: weekly step, {len(report['changes'])} changes; see data/learning/REPORT.md")
    except Exception as error:          # the record is worth keeping, never worth a failed run
        status['errors'].append(f'learning: {type(error).__name__}: {error}')
        log(f'learning: {type(error).__name__}: {error}')


RESEARCH_LIMIT = 6          # candidates the web researcher is asked about per run, strongest first
FAVORITE_EDGE = 2.0         # a game-line favorite needs the calibrated chance this many points clear of break-even


def promote(candidate, facts, use_llm, status=None):
    """Should this candidate be a researched favorite? Only with a verified, sourced reason and the model's yes.

    The arithmetic must clear on its own; at least one verified fact must argue for the pick and name two
    people or a weather flag; nothing may argue against; and the model must say, pointing at facts, that the
    reason holds. Without the model there is no judgment, so there is no favorite.
    """
    desk = candidate.get('_desk') or {}
    supporting = [f for f in facts if f.get('direction') == 'for' and f.get('verified') and f.get('kind') in ('injury', 'role', 'weather', 'stats')]
    if not supporting or any(f.get('direction') == 'against' for f in facts):
        return False
    if candidate.get('athleteId'):
        arithmetic = desk.get('rawChance', 0) >= gates.PROP_RAW and desk.get('edgePoints', 0) >= gates.PROP_EDGE
    else:
        arithmetic = bool(desk.get('calibrated')) and desk.get('edgePoints', 0) >= FAVORITE_EDGE
    named = {e for f in supporting if f['kind'] in ('injury', 'role') for e in f.get('entities') or []}
    weather = any(f['kind'] == 'weather' for f in supporting)
    if not arithmetic or not (len(named) >= 2 or weather):
        return False
    if not use_llm:
        return False
    verdict = llm_tasks.judge_for(candidate, facts)
    if status is not None:
        status['llm']['judged'] += 1
    if not verdict or not verdict['supports'] or verdict['confidence'] != 'high' or not verdict['fact_ids']:
        return False
    candidate['favorite'], candidate['modelLean'] = True, False
    candidate['confidence'] = min(6, 4 + (1 if len(named) >= 3 else 0) + (1 if desk.get('edgePoints', 0) >= 3 else 0))
    candidate['_support'] = [f for f in supporting if f['id'] in verdict['fact_ids']] or supporting
    candidate['_supportNote'] = verdict['note']
    return True


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


def post_reason(candidate, facts, ctx, records, weights=None):
    """The one sentence the play's post gives as its reason, chosen now from structured facts, never from prose:
    for a player prop, his own record at this line when it backs the side; for a game line, a verified fact from
    the web check or a weather flag that points the same way as the play. None when nothing backs it: then the
    post stands on the number."""
    import x_post
    if candidate.get('legs'):
        return None
    side, line = gates.side_of(candidate), float(candidate['line'])
    if candidate.get('athleteId'):
        game = ctx.games[candidate['gameIds'][0]]
        logs = features.player_logs([g for g in records if g['league'] == game['league']]).get(str(candidate['athleteId']), [])
        recent = [v for v in (features.value(r, gates.market_key(candidate)) for r in logs[-10:]) if v is not None]
        hits = sum(1 for v in recent if (v > line if side == 'over' else v < line))
        if len(recent) >= 5 and hits / len(recent) >= 0.6:
            return f"{'Over' if side == 'over' else 'Under'} {pricing.fmt(line)} in {hits} of his last {len(recent)} games."
        return None
    backing = [first_sentence(f['claim']) for f in facts if f.get('direction') == 'for' and f.get('claim')
               and (f.get('kind') == 'weather' or (f.get('origin') == 'claude researcher' and f.get('verified')
                                                    and f.get('kind') in ('injury', 'role', 'weather')))]
    return x_post.reason_for({'why': ' '.join(backing)}, weights) if backing else None


def first_sentence(text):
    import x_post
    parts = x_post.sentences(text)
    return (parts[0] if parts else str(text)).rstrip('.') + '.'


def learning_weights():
    import learning
    return learning.load_policy().get('reasonWeights')


def checked_facts(candidate, limit=2):
    """Up to two verified facts from the web check about who is expected to play, for the reasoning and its sources.
    Only facts that do not argue against the pick: one that did would have held it."""
    facts = [f for f in candidate.get('_research') or [] if f.get('verified') and f.get('kind') in AVAILABILITY
             and f.get('direction') != 'against' and f.get('claim')]
    return facts[:limit]


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
    if candidate.get('favorite'):
        claims = ' '.join(f['claim'].rstrip('.') + '.' for f in candidate.get('_support') or [])
        chance = f"{100 * p['chance']:.1f}%" if p.get('calibrated') else f"{100 * p['rawChance']:.1f}% on the raw curve"
        candidate['why'] = (f"Researched pick. {claims} Our number is {p['projection']:g} against {pricing.fmt(line)}, {chance} for the "
                            f"{side}, {p['edgePoints']:+.1f} points clear of the {100 * p['breakEven']:.1f}% that {odds:+d} needs. "
                            f"The sourced reason and the number point the same way.")
        candidate['risk'] = (f"A report can change before kickoff, and a listed player can dress. {sparse}The number still rests on a model the "
                             f"closing line beats on average. Confidence {candidate['confidence']} of 10.")
        sources = list(candidate.get('sources') or [])
        for fact in candidate.get('_support') or []:
            if fact.get('source') and fact['source'] not in sources:
                sources.append(fact['source'])
        candidate['sources'] = sources
        return candidate
    if candidate.get('athleteId'):
        candidate['why'] = (f"Prop lean on our number alone: our projection is {p['projection']:g} against {pricing.fmt(line)} and the "
                            f"{side} reads {100 * p['rawChance']:.1f}% on the raw curve, which has no graded history against a line yet, "
                            f"so the true chance is lower than that. {prop_reasoning(candidate, ctx, records, snapshot)}")
        games_played = ctx.appearances.get(candidate['athleteId'], 0)
        candidate['risk'] = (f"Uncalibrated chance; a player line turns on a handful of touches. {games_played} games this season"
                             f"{'' if games_played >= 3 else ', the role settled by last season'}. A player who does not take the field is "
                             f"voided under the book's rule; one who leaves hurt is graded. Confidence {candidate['confidence']} of 10.")
    else:
        market_words = next((f['claim'] for f in candidate.get('_evidence') or [] if f.get('kind') == 'market'), '')
        checked = checked_facts(candidate)
        candidate['why'] = (f"Model lean, published on our number alone. Our total is {p['projection']:g} against {pricing.fmt(line)}: the "
                            f"{side} reads {100 * p['chance']:.1f}% after the raw {100 * p['rawChance']:.1f}% is shrunk by the model's "
                            f"record against the close, {p['edgePoints']:+.1f} points clear of the {100 * p['breakEven']:.1f}% that "
                            f"{odds:+d} needs. Nothing sourced argues against it; the number is the reason."
                            + ''.join(f" Checked before publishing: {first_sentence(f['claim'])}" for f in checked)
                            + (f" The market: {market_words}" if market_words else ''))
        sources = list(candidate.get('sources') or [])
        for fact in checked:
            if str(fact.get('source') or '').startswith('https://') and fact['source'] not in sources:
                sources.append(fact['source'])
        candidate['sources'] = sources
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
            # Say which check failed, and keep the report for a person to read: an assert without a message
            # otherwise leaves nothing to go on.
            frame = traceback.extract_tb(error.__traceback__)[-1]
            kept = CONF / 'failed' / name
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            raise RunError(f"{name} fails validation at {Path(frame.filename).name}:{frame.lineno} ({frame.line}) {error}; "
                           f"the report is kept at {kept}")
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
    push_with_retry(runner, cwd)
    return {'committed': True, 'pushed': True}


def push_with_retry(runner=git, cwd=ROOT):
    """Push; on rejection rebase onto origin/main (merging the price stores if both sides captured) and try
    again, three times. Never forced."""
    for attempt in range(3):
        result = runner('push', '--quiet', cwd=cwd, check=False)
        if not result.returncode:
            return
        log(f'push rejected (attempt {attempt + 1}); rebasing onto origin/main')
        rebase_onto_remote(runner, cwd=cwd)
    raise RunError('push rejected three times; the commits stay local and the next run rebases them')


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
    prime_weather(records)
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
    decided = []          # every decision this run made, for the learning record
    reasons = {}          # the reason each published play's post will give (data/x-reasons.json)
    # The web researcher reads the news for every play that passes the rules, on the runs that publish.
    research_on = researcher.enabled() and slot.hour not in (6, 23)
    status['research'] = {'on': research_on, 'asked': 0, 'verified': 0, 'dropped': 0}
    for candidate in wanted:
        want = 'prop' if candidate.get('athleteId') else 'lean'
        if want not in kinds:
            continue
        if price(candidate, ctx, now) is None:
            continue
        if candidate['id'] in ctx.first:
            continue            # already on the record: only a settlement or a close revises a published pick
        candidate['_team'] = ctx.player_team.get(candidate.get('athleteId', ''))
        facts = evidence(candidate, ctx, context_file)
        candidate['_evidence'] = facts
        league = candidate['_league']
        write_prose(candidate, ctx, records)
        # The written rules first: a candidate they refuse costs no web research and no model time.
        ok, decisions = gates.admit(dict(candidate, league=league), ctx)
        for decision in decisions:
            if decision.rule == 'one_book' and decision.data.get('quoteNoteRequired'):
                candidate['quoteNote'] += f" {candidate['book']} is the only book with this market; kickoff is inside three hours."
            if decision.rule == 'cfb_jurisdiction' and decision.data.get('jurisdictionVerified'):
                candidate['jurisdictionVerified'] = True
        if not ok:
            first = gates.refusals(decisions)[0]
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'rule': first.rule, 'reason': first.reason})
            decided.append(decision_record(candidate, league, 'refused', [d.rule for d in gates.refusals(decisions)], first.reason, now, ctx))
            continue
        # Then the news: the web researcher reads injury, availability and depth-chart reporting for the play.
        researched = False          # true only when the web check came back with who is expected to play
        if research_on and status['research']['asked'] < RESEARCH_LIMIT:
            game = ctx.games[candidate['gameIds'][0]]
            kept, dropped = researcher.research(game, gates.market_key(candidate), gates.side_of(candidate), now=now,
                                                player=candidate.get('_player') or ctx.names.get(str(candidate.get('athleteId') or '')))
            candidate['_research'] = [dict(f, verified=True) for f in kept] + [dict(f, verified=False) for f in dropped]
            status['research']['asked'] += 1
            status['research']['verified'] += len(kept)
            status['research']['dropped'] += len(dropped)
            facts += kept
            researched = any(f.get('kind') in AVAILABILITY for f in kept)
            log(f"researched {candidate['title']}: {len(kept)} verified facts, {len(dropped)} dropped"
                + ('' if researched else '; none about who is expected to play'))
            if kept:
                write_prose(candidate, ctx, records)
        hold = None
        if needs_research(candidate) and not researched:
            hold = ("a college play needs the web check to confirm who is expected to play before it is published (there is "
                    "no college injury feed), and it has not come back with that")
        hold = hold or judge(candidate, relevant_facts(candidate, facts, ctx), use_llm, status)
        if hold:
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'rule': 'held', 'reason': hold})
            decided.append(decision_record(candidate, league, 'held', ['held'], hold, now, ctx))
            continue
        if research_on and 'favorite' in kinds and promote(candidate, facts, use_llm, status):
            log(f"favorite: {candidate['title']} ({candidate.get('_supportNote')})")
        if use_llm:
            polish(candidate, facts, status)
        # Admitted picks join the day's count so the caps hold within one run.
        kind = 'props' if candidate.get('athleteId') else 'gamePicks'
        ctx.first[candidate['id']] = dict(candidate, league=league, publishedAt=stamp(now), kind=kind)
        ctx.latest[candidate['id']] = dict(candidate)
        published.append((league, kind, candidate))
        decided.append(decision_record(candidate, league, 'published', [], None, now, ctx))
        reason = post_reason(candidate, facts, ctx, records, learning_weights())
        if reason:
            reasons[candidate['id']] = reason
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
                decided.append(decision_record(ticket, league, 'published', [], None, now, ctx))
                break
            decided.append(decision_record(ticket, league, 'refused', [d.rule for d in gates.refusals(decisions)],
                                           gates.refusals(decisions)[0].reason, now, ctx))
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
    drafts(slot, now, ctx, games, settled, status)
    if not args.dry_run:
        if reasons:
            import x_post
            stored = x_post.load_reasons()
            stored.update(reasons)
            x_post.save_reasons(stored)
        remember(decided, now, slot, status)
        git_result = commit_push(now, slot, {'published': len(published), 'settled': len(settled), 'closed': len(closed)},
                                 push=not args.no_push)
        status['git'] = git_result
        log('git:', git_result)
        # Posts are scheduled after the push: the push deploys the cards of anything just published, and a
        # post never goes out without its card.
        buffer_posts(now, ctx, games, closed, status, deploying=bool(git_result.get('pushed')))
        status['git']['posts'] = commit_log(now, push=not args.no_push)
    status.update(outcome='ok', finishedAt=stamp(datetime.now(timezone.utc)))
    write_status(status)
    log(f"done: {len(settled)} settled, {len(closed)} closed, {len(published)} published, {len(screened)} screened")
    for s in screened:
        log(f"  screened {s['title']}: {s['rule']}: {s['reason']}")
    return 0


# ------------------------------------------------------------------ X drafts (review gate: files, never posts)

def drafts(slot, now, ctx, games, settled, status):
    """Write the posts a person may approve: a game-day recap after the last run, the model scoreboard on Tuesdays,
    and a draft for every open favorite. Nothing here posts; scripts/x_post.py post --confirm does."""
    import x_post
    folder = CONF / 'x-drafts'
    folder.mkdir(parents=True, exist_ok=True)
    log_book = x_post.load_log()
    posted = {p['id'] for p in log_book['posts']}
    local = now.astimezone(EASTERN)
    written = []
    if slot.hour == 23 and settled:
        day = eastern_date(now).isoformat()
        if f'recap:day:{day}' not in posted:
            first = dict(ctx.first)
            latest = dict(ctx.latest)
            for league, kind, revision in settled:          # today's settlements count before they are committed
                latest[revision['id']] = dict(latest.get(revision['id'], {}), **revision)
            text = x_post.recap(day, first, latest, games, now)
            if text:
                (folder / f'recap-{day}.txt').write_text(text + '\n', encoding='utf-8')
                written.append(f'recap-{day}')
    if slot.hour == 8 and local.weekday() == 1:              # Tuesday: the week's games are final
        day = eastern_date(now).isoformat()
        if f'scoreboard:week:{day}' not in posted:
            text = x_post.scoreboard_text(load_json(ROOT / 'site' / 'data' / 'scoreboard.json', {}))
            if text:
                (folder / f'scoreboard-{day}.txt').write_text(text + '\n', encoding='utf-8')
                written.append(f'scoreboard-{day}')
    for key, pick in ctx.first.items():
        merged = dict(pick, **ctx.latest.get(key, {}))
        postable = merged.get('favorite') is True or merged.get('modelLean') or merged.get('legs')
        if not postable or merged.get('result') or key in posted:
            continue
        try:
            text, pick_now, game = x_post.do_draft(key, now, ctx.first, ctx.latest, games, out=folder)
            written.append(key)
        except x_post.Refused:
            continue
        try:                                                  # the card is a nicety; a missing browser never stops a run
            import pick_card
            if pick_card.chrome_path():
                team = ctx.player_team.get(str(pick_now.get('athleteId') or ''))
                side = 'home' if team == str(game['home']['id']) else 'away' if team == str(game['away']['id']) else None
                pick_card.render(pick_card.svg(pick_now, game, player_side=side), folder / f'{key}.png')
        except Exception as error:
            log(f'card for {key} not rendered: {error}')
    status['x']['drafted'] = len(written)
    if written:
        log('x drafts written:', ', '.join(written), f'(in {folder})')


# ------------------------------------------------------------------ posting through Buffer

CARD_WAIT = 15 * 60          # seconds to wait for a push's deploy to put the new cards live
CARD_POLL = 30


def buffer_posts(now, ctx, games, closed, status, deploying=False, sleep=time.sleep, clock=time.monotonic):
    """Schedule today's plays through Buffer (scripts/buffer_post.py), record what became of past posts and
    cancel any whose pick closed. Off without a token. When this run just pushed, the deploy that carries the
    new cards takes a few minutes, so the run waits for them (up to 15 minutes) before scheduling; a play whose
    card is still not live waits for the next run."""
    import buffer_post
    import x_post
    if not os.environ.get('BUFFER_TOKEN', '').strip():
        log('buffer: no BUFFER_TOKEN; posts stay as drafts')
        return
    log_book = x_post.load_log()
    try:
        channel = buffer_post.x_channel(wanted='keenkooks')
        for entry in buffer_post.reconcile(log_book, now, log=log):
            status['errors'].append(f"buffer: {entry['id']} failed to post: {entry['error']}")
        buffer_post.collect_metrics(log_book, now, log=log)
        closed_ids = {revision['id'] for _, _, revision in closed}
        if closed_ids:
            buffer_post.cancel_closed(closed_ids, log_book, now, log=log)
        plans = buffer_post.plan(ctx.first, ctx.latest, games, now, log_book, ctx.player_team)
        if plans and deploying:
            waiting = [card for *_, card in plans if card]
            started = clock()
            while waiting and clock() - started < CARD_WAIT:
                waiting = [card for card in waiting if not buffer_post.reachable(f'{buffer_post.CARDS}{card}.png')]
                if waiting:
                    sleep(CARD_POLL)
            if waiting:
                log(f'buffer: {len(waiting)} card(s) still not live after the wait; those plays wait for the next run')
            later = datetime.now(timezone.utc)
            plans = buffer_post.plan(ctx.first, ctx.latest, games, max(now, later), log_book, ctx.player_team)
        limit = buffer_post.daily_limit(channel['id'], eastern_date(now).isoformat())
        if limit and limit.get('remaining') is not None and limit['remaining'] < len(plans):
            log(f"buffer: the channel can take {limit['remaining']} more posts today; scheduling that many")
            plans = plans[:max(0, limit['remaining'])]
        before = len(log_book.get('posts', []))
        buffer_post.schedule(plans, channel['id'], log_book, now, log=log)
        status['x']['posted'] = len(log_book.get('posts', [])) - before
    except (buffer_post.BufferError, buffer_post.MissingToken) as error:
        log(f'buffer: {error}')
        status['errors'].append(f'buffer: {error}')
    x_post.save_log(log_book)


def commit_log(now, push=True, runner=git, cwd=ROOT):
    """Commit the posted log on its own, after the posts are scheduled, and push it."""
    if not runner('status', '--porcelain', '--', 'data/x-posted.json', cwd=cwd).stdout.strip():
        return {'committed': False, 'pushed': False}
    runner('add', '--', 'data/x-posted.json', cwd=cwd)
    runner('commit', '--quiet', '-m', f"Posts {eastern_date(now).isoformat()} {now.astimezone(EASTERN):%H:%M} ET", cwd=cwd)
    if not push:
        return {'committed': True, 'pushed': False}
    push_with_retry(runner, cwd)
    return {'committed': True, 'pushed': True}


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


# ------------------------------------------------------------------ the check before a post goes out

PRECHECK_WINDOW = (timedelta(minutes=15), timedelta(minutes=150))   # posts due this far ahead get their last look
PRECHECK_LAST = timedelta(minutes=45)      # inside this, an unconfirmed college play is withheld rather than retried


def lineup_confirmed(kept):
    """Did the web check come back with who is expected to play?"""
    return any(f.get('kind') in AVAILABILITY for f in kept or [])


def precheck_due(log_book, now):
    low, high = now + PRECHECK_WINDOW[0], now + PRECHECK_WINDOW[1]
    return [e for e in log_book.get('posts', [])
            if e.get('kind') == 'buffer:play' and e.get('bufferPostId') and not e.get('sentAt') and not e.get('cancelledAt')
            and not e.get('deletedAt') and not e.get('precheck') and e.get('dueAt') and low <= gates.when(e['dueAt']) <= high]


def live_context(stored, now, fetch=None):
    """The injury report as ESPN has it right now, in memory; the stored one when the read fails."""
    import research_context
    from urllib.request import urlopen

    def default(url):
        with urlopen(url, timeout=25) as response:
            return json.load(response)
    try:
        return research_context.refresh(stored or {}, fetch or default, stamp(now))
    except Exception as error:          # the stored report is the fallback, never a failure
        log(f'precheck: live injury report unavailable ({type(error).__name__}); using the stored one')
        return stored or {}


def precheck_note(now, reason, pick):
    return (f"Closed to new entries at {et(now)}, before its post went out: {reason}. Stays in the record at "
            f"{pricing.fmt(float(pick['line'])) if pick.get('line') is not None else 'its line'} and {int(pick['odds']):+d} "
            "and is graded as posted.")


def precheck(args):
    """The last look before a scheduled play posts to X: the injury report read live, the latest line, the web
    researcher's news when it is on, and the judge on whatever can matter. A play that no longer stands is taken
    off the queue and closed to new entries on the site with the reason; a play that stands is marked checked.
    Quiet when nothing is due."""
    import buffer_post
    import x_post
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    if not precheck_due(x_post.load_log(), now):
        return 0
    status = {'errors': [], 'llm': {'judged': 0}, 'research': {'asked': 0, 'verified': 0, 'dropped': 0}}
    try:
        with Lock(CONF / 'run.lock'):
            if not args.dry_run:
                sync()
            log_book = x_post.load_log()
            due = precheck_due(log_book, now)
            if not due:
                return 0
            log(f"precheck: {len(due)} post(s) due within {int(PRECHECK_WINDOW[1].total_seconds() // 60)} minutes")
            slate = load_json(ROOT / 'site' / 'data' / 'slate.json', {'games': []})
            games = live_games(now, {g['id']: g for g in slate.get('games', []) if g.get('league') in ('NFL', 'CFB')})
            records = features.load()
            stores = gates.Stores(records=records)
            ctx = stores.as_of(now)
            ctx.games = games
            raw_first = raw_first_publications(stores.reports)
            context_file = live_context(stores.context_file, now)
            use_llm = not args.no_llm and llm.available()
            moved, _ = close_moves(ctx, raw_first, games, desk.captures(), now)
            moved = {revision['id']: (league, kind, revision) for league, kind, revision in moved}
            closures, withheld = [], []
            for entry in due:
                key = entry['id']
                if key not in ctx.first:
                    continue
                pick = dict(ctx.first[key], **ctx.latest.get(key, {}))
                if pick.get('result') or pick.get('entryNote') or (pick.get('status') or 'active') != 'active':
                    entry['precheck'] = {'at': stamp(now), 'result': 'closed already'}
                    closures.append(None)
                    continue
                game = ctx.games.get((pick.get('gameIds') or [None])[0])
                pick['_team'] = ctx.player_team.get(str(pick.get('athleteId') or ''))
                pick['_league'] = pick.get('league') or key.split('-')[0]
                facts = evidence(pick, ctx, context_file)
                kept = []
                if researcher.enabled() and game:
                    kept, dropped = researcher.research(game, gates.market_key(pick), gates.side_of(pick), now=now,
                                                        player=ctx.names.get(str(pick.get('athleteId') or '')))
                    status['research']['asked'] += 1
                    status['research']['verified'] += len(kept)
                    facts += kept
                reason = judge(pick, relevant_facts(pick, facts, ctx), use_llm, status)
                if not reason and needs_research(pick) and not lineup_confirmed(kept):
                    # A college play with nothing checked is not clear, it is unknown: try again at the next half
                    # hour; at the last chance, withhold the post (the pick stays on the site and is graded).
                    if gates.when(entry['dueAt']) - now > PRECHECK_LAST:
                        log(f"precheck: {key} not confirmed yet (the web check came back without who is playing); next half hour")
                        continue
                    entry['precheck'] = {'at': stamp(now), 'result': 'withheld', 'reason': 'the web check could not confirm who is playing'}
                    withheld.append(entry)
                    log(f"precheck: {key} withheld from X: the web check could not confirm who is playing")
                    continue
                if not reason and key in moved:
                    reason = moved[key][2]['entryNote'].split(': ', 1)[1].split('. Published cutoff')[0]
                if reason:
                    kind_key, original = raw_first[key]
                    closures.append((pick['_league'], kind_key, dict(original, status='expired', entryNote=precheck_note(now, reason, original))))
                    entry['precheck'] = {'at': stamp(now), 'result': 'closed', 'reason': reason}
                    log(f"precheck: {key} closed before its post: {reason}")
                else:
                    entry['precheck'] = {'at': stamp(now), 'result': 'clear', 'facts': len(relevant_facts(pick, facts, ctx))}
                    log(f"precheck: {key} clear")
            closures = [c for c in closures if c]
            for entry in withheld:
                if not args.dry_run:
                    try:
                        buffer_post.delete_post(entry['bufferPostId'])
                        entry['cancelledAt'] = stamp(now)
                    except buffer_post.BufferError as error:
                        log(f"precheck: could not withhold {entry['id']}: {error}")
            if closures and not args.dry_run:
                buffer_post.cancel_closed({c[2]['id'] for c in closures}, log_book, now, log=log)
                by_league = defaultdict(lambda: ([], [], []))
                for item in closures:
                    by_league[item[0]][1].append(item)
                reports = build_reports(dict(by_league), now.astimezone(EASTERN), now, [], [], ['precheck before posting'], {}, False)
                validate(reports, stores.reports, games)
                for name, report in reports.items():
                    (ROOT / 'research' / name).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                    log('wrote', ROOT / 'research' / name)
                run_tests()
            x_post.save_log(log_book)
            if not args.dry_run:
                commit_push(now, now.astimezone(EASTERN), {'published': 0, 'settled': 0, 'closed': len(closures)}, push=not args.no_push)
                commit_log(now, push=not args.no_push)
            return 0
    except RunError as error:
        if 'holds the lock' in str(error):
            log('precheck: a run is in progress; the check waits for the next half hour')
            return 0
        log('precheck STOPPED:', error)
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', nargs='?', default='run', choices=('run', 'status', 'heartbeat', 'precheck'))
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
    if args.command == 'precheck':
        return precheck(args)
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
