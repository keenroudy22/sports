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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import arbs
import build_site
import line_payload
import desk
import dossier
import features
import feed
import gates
import llm
import llm_tasks
import market_read
import model_v2
import parlay
import pick_card
import post_windows
import pricing
import projection_shadows
import role_sanity
import refresh
import researcher
import reasoned_edges
import scoreboard
import season_trends
import sgo_shadow
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
CONF = Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy'))
EASTERN = gates.EASTERN
SLOT_TOLERANCE = timedelta(minutes=40)     # a run that fires this far from a slot still belongs to it
PUBLISH_MARGIN = timedelta(minutes=5)      # nothing is published on a game this close to kickoff
KINDS = ('settle', 'close', 'lean', 'prop', 'longshot', 'ladder', 'favorite')
LADDER_SCAN_TIMES = ((10, 0), (13, 30), (16, 0), (20, 0))
WHITELIST = ('data/morning-brief/', 'data/nba-editorial/', 'research/', 'data/odds/', 'data/prop-odds/', 'data/release-cards/', 'data/x-posted.json', 'data/x-reasons.json', 'data/learning/',
             'data/paper/', 'data/hoops/', 'data/nba-capture/', 'data/nba-roster-research/', 'data/nba-roster-exposure-v2/', 'data/nba-roster-exposure-v2-study/', 'data/nba-roster-confirmation-v2/', 'data/nba-roster-confirmation-v3/', 'data/nba-trial/', 'data/market-lab/', 'site/data/market-lab.json', 'data/featured.json', 'data/sports-social/', 'site/data/desk-notes.json')
BOOK_SLUG = {'DraftKings': 'dk', 'FanDuel': 'fd', 'BetMGM': 'mgm', 'Caesars': 'czr', 'BetRivers': 'br',
             'ESPN BET': 'espnbet', 'Fanatics': 'fan'}
VOLUME = {'recYds': 'targets', 'rec': 'targets', 'rushYds': 'carries', 'car': 'carries',
          'passYds': 'att', 'cmp': 'att', 'att': 'att'}
SKILL = {'QB', 'RB', 'FB', 'WR', 'TE', 'OT', 'OG', 'C', 'G', 'T', 'OL'}
LONGSHOT_TARGET = 500
REPLACEMENT_REVIEW_LEAD = timedelta(minutes=45)  # leave one scheduled last look before a replacement can post
SETTLEMENT_REVIEW_WINDOW = timedelta(hours=12)  # through the next morning for injury news/book notices to catch up


class RunError(Exception):
    """A step that stops the run; the reason is reported and nothing further is written."""


class ReleaseArtifactError(Exception):
    """A private play remains queued until its caption and card can be rebuilt."""


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


RUN_LOCK_WAIT = 15 * 60      # seconds a scheduled run waits out a price check before giving up its slot


class Lock:
    """One desk process at a time. A scheduled run waits (up to `wait` seconds) for a price check to finish rather
    than lose its slot; the price check itself never waits, it tries again at the next half hour."""

    def __init__(self, path, wait=0, poll=5, sleep=time.sleep, clock=time.monotonic):
        self.path, self.handle = Path(path), None
        self.wait, self.poll, self.sleep, self.clock = wait, poll, sleep, clock

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, 'w')
        deadline = self.clock() + self.wait
        while True:
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if self.clock() >= deadline:
                    self.handle.close()
                    raise RunError('another run holds the lock')
                self.sleep(self.poll)

    def __exit__(self, *exc):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def git(*args, cwd=ROOT, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode:
        raise RunError(f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()[:400]}")
    return result


LEFTOVER = ('data/morning-brief/', 'data/nba-editorial/', 'data/odds/', 'data/prop-odds/', 'data/learning/', 'data/x-posted.json', 'data/x-reasons.json', 'data/paper/', 'data/hoops/', 'data/nba-capture/', 'data/nba-roster-research/', 'data/nba-roster-exposure-v2/', 'data/nba-roster-exposure-v2-study/', 'data/nba-roster-confirmation-v2/', 'data/nba-roster-confirmation-v3/', 'data/nba-trial/',
            'data/market-lab/', 'site/data/market-lab.json', 'data/featured.json', 'data/sports-social/', 'site/data/desk-notes.json')


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
    """Fetch origin/main. Another git client on this machine (a desktop app can refresh the repository in the
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


def sharp_capture_allowance(slot):
    """Split the same daily 30 reads across early, follow-up and evening checks.

    Existing Sunday early-game and primetime extras keep their own 15 reads.
    No new worker, paid request or larger daily allowance is introduced.
    """
    window = (slot.hour, slot.minute) if slot else None
    if window in ((6, 45), (8, 30), (17, 30)):
        return 10
    return 15 if window in ((7, 30), (18, 50)) else 0


def capture(slot=None, python=sys.executable):
    """Step 1, continued: price captures when their budget allows. They print why they skip."""
    notes = []
    scripts = ['odds_api.py', 'prop_odds.py']
    if sharp_capture_allowance(slot):
        scripts.append('sharp_odds.py')
    for script in scripts:
        env = None
        if script == 'sharp_odds.py':
            env = dict(os.environ, SHARP_REQUESTS=str(sharp_capture_allowance(slot)))
        result = subprocess.run([python, str(ROOT / 'scripts' / script)], cwd=ROOT, capture_output=True, text=True,
                                env=env)
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
    """(result, actual, actualValue) for a spread, total or moneyline against the final score."""
    home, away = score(game, 'home'), score(game, 'away')
    if home is None or away is None:
        return None
    line, direction = float(pick['line']), str(pick.get('direction') or '').lower()
    actual = f"{game['away'].get('short') or game['away'].get('abbreviation')} {away}, {game['home'].get('short') or game['home'].get('abbreviation')} {home}"
    if pick.get('marketType') == 'moneyline':
        if direction not in ('home', 'away'):
            return None
        margin = home - away if direction == 'home' else away - home
        return ('win' if margin > 0 else 'push' if margin == 0 else 'loss'), actual, margin
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
    import result_display
    name = result_display.player_name(pick, player)
    return result, f"{name}: {value:g} {words}", value


def leg_pick(leg):
    """A parlay leg as the pick shape grade_game_pick and grade_prop read."""
    market = str(leg.get('market') or '')
    market_type = str(leg.get('marketType') or '')
    if market_type in ('spread', 'total', 'moneyline') or market in ('point spread', 'total points', 'moneyline'):
        return {'marketType': market_type or ('spread' if market == 'point spread' else 'moneyline' if market == 'moneyline' else 'total'), 'line': leg.get('line'),
                'direction': leg.get('side') or leg.get('direction')}
    athlete = leg.get('athleteId') or (re.match(r'prop-[A-Z]+-\d+-(\d+)-', str(leg.get('id') or '')) or [None, None])[1]
    return {'athleteId': athlete, 'market': market, 'title': leg.get('title'), 'line': leg.get('line'),
            'direction': leg.get('side') or leg.get('direction')}


def settle(ctx, raw_first, games, records, now, fetch=boxscores.fetch_game, injury_check=None):
    """Revisions for every unsettled pick whose game is final. Unclear outcomes are reported, not guessed.

    Every raw player-prop loss gets a sourced postgame injury check. An injury can change a book's settlement, but
    never does so by assumption: evidence pauses the grade through the next morning. If no official protection can
    be confirmed by then, the public record uses the final stats and remains correctable by a later dated revision.
    """
    revisions, unclear = [], []
    by_event = {f"{g['league']}-{g['eventId']}": g for g in records}
    fetched = {}
    injury_cache = {}

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

    def review_loss(prop, game, book):
        athlete = str(prop.get('athleteId') or '')
        player = (getattr(ctx, 'names', {}) or {}).get(athlete) or prop.get('player') or prop.get('title') or athlete
        cache_key = (game.get('id'), athlete)
        if cache_key not in injury_cache:
            check = injury_check or (researcher.settlement_injury if researcher.enabled() else None)
            if check is None:
                injury_cache[cache_key] = {'checked': False, 'facts': [], 'dropped': []}
            else:
                try:
                    injury_cache[cache_key] = check(game, player, now=now)
                except Exception as error:
                    log(f'settlement injury check for {player} unavailable ({type(error).__name__})')
                    injury_cache[cache_key] = {'checked': False, 'facts': [], 'dropped': []}
        review = injury_cache[cache_key]
        kickoff = gates.when(game['kickoff']) if game.get('kickoff') else None
        deadline = kickoff + SETTLEMENT_REVIEW_WINDOW if kickoff else now
        waiting = now < deadline
        wait_text = (f'holding through {et(deadline)} while public settlement evidence catches up; '
                     'no owner action is required')
        fallback = (f'Postgame injury review found no confirmed different {book} settlement by {et(deadline)}; '
                    'graded from the official stats and subject to a later dated correction.')
        if not review.get('checked'):
            return ({'pending': True, 'why': f'postgame injury check for {player} did not complete; {wait_text}',
                     'sources': []} if waiting else {'pending': False, 'note': fallback, 'sources': []})
        if review.get('dropped'):
            sources = [f.get('source') for f in review['dropped'] if f.get('source')]
            return ({'pending': True, 'why': f'a possible postgame injury report for {player} could not be verified; {wait_text}',
                     'sources': sources} if waiting else {'pending': False, 'note': fallback, 'sources': sources})
        if review.get('facts'):
            claims = ' '.join(f['claim'] for f in review['facts'])
            sources = [f['source'] for f in review['facts']]
            return ({'pending': True, 'why': f'{claims} {wait_text}. Injury alone is not a push or void.',
                     'sources': sources, 'injuryPlayers': [player]} if waiting else
                    {'pending': False, 'note': f'{claims} {fallback}', 'sources': sources,
                     'injuryPlayers': [player]})
        return None

    for key, pick in ctx.first.items():
        recent = ctx.latest.get(key, {})
        if pick.get('historicalImport') or recent.get('result') or recent.get('status') in ('settled', 'withdrawn', 'historical'):
            continue
        ids = pick.get('gameIds') or []
        played = [games.get(g) for g in ids]
        if not ids or not all(g and g.get('completed') for g in played):
            continue
        kind, original = raw_first[key]
        league, reason, review_notes, review_sources, injury_players = pick.get('league'), None, [], [], []
        if kind == 'parlays':
            results, pending = [], []
            for leg in original.get('legs') or []:
                shaped, game = leg_pick(leg), games.get(leg.get('gameId'))
                graded = grade_game_pick(shaped, game) if shaped.get('marketType') else grade_prop(shaped, record_for(game)) if game else None
                results.append(graded[0] if graded else None)
                if graded and graded[0] == 'loss' and not shaped.get('marketType'):
                    review = review_loss(shaped, game, original.get('book') or 'the listed book')
                    if review:
                        if review['pending']:
                            pending.append(review)
                        else:
                            review_notes.append(review['note'])
                            review_sources.extend(review['sources'])
                            injury_players.extend(review.get('injuryPlayers') or [])
            if pending:
                unclear.append({'id': key, 'why': ' '.join(review['why'] for review in pending),
                                'sources': list(dict.fromkeys(source for review in pending
                                                             for source in review['sources'])),
                                'settlementReview': True})
                continue
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
        if kind in ('props', 'riskyProps') and result == 'loss':
            review = review_loss(original, played[0], original.get('book') or 'the listed book')
            if review and review['pending']:
                unclear.append({'id': key, 'why': review['why'], 'sources': review['sources'],
                                'settlementReview': True})
                continue
            if review:
                review_notes.append(review['note'])
                review_sources.extend(review['sources'])
                injury_players.extend(review.get('injuryPlayers') or [])
        if review_notes:
            reason = ' '.join(filter(None, [reason, *review_notes]))
        revision = dict(original, status='settled', result=result, actual=actual, settledAt=stamp(now),
                        resultSource=box_url(league, ids[0].split('-', 1)[1]))
        if value is not None:
            revision['actualValue'] = value
        if reason:
            revision['settlementReason'] = reason
        if review_sources:
            revision['settlementReviewSources'] = list(dict.fromkeys(review_sources))
        if injury_players:
            revision['injuryPlayers'] = list(dict.fromkeys(injury_players))
        lock_units(revision)
        revisions.append((league, kind, revision))
    return revisions, unclear


def lock_units(revision):
    """Write the units a graded play won or lost into its settlement, at its posted line, price and risk stake
    (one unit only when no explicit stake was saved; a push zero), so units stay saved with the result and never
    move when the code that sums them does."""
    import x_post
    units = x_post.units_for(revision)
    if units is not None:
        revision['units'] = round(units, 3)
    return revision


# ------------------------------------------------------------------ step 3: close moves

def entry_note(now, breaks, pick):
    return (f"Off the card: {str(breaks).rstrip('. ')}. Published cutoff: {str(pick.get('cutoff') or 'as posted').rstrip('. ')}. "
            f"Stays in the record at {pricing.fmt(float(pick['line'])) if pick.get('line') is not None else 'its line'} and "
            f"{int(pick['odds']):+d} and is graded as posted.")


def absorb(ctx, revisions):
    """This run's settlements and closes, seen by every later step of the run: a play that closed is not queued, a
    win that settled gets its cashed post now rather than at the next run."""
    for _, _, revision in revisions:
        ctx.latest[revision['id']] = dict(ctx.latest.get(revision['id'], {}), **revision)


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


# A fun parlay never carries a leg the desk has pulled: the same game, market and side as a single play that
# closed (its line moved past the cutoff, or the news turned against it) closes the ticket too, and the games
# the desk has a sourced reason against are left off the next ticket.
AGAINST_RULES = ('lean_nothing_against', 'qb_available', 'prop_injury_clear')
UNCONFIRMED = 'a college play needs the web check'      # a hold for want of news, not a reason against the game


def closed_reason(note):
    """What closed a play, from its entryNote, without the time stamp or the record's tail."""
    text = str(note or '')
    for marker in ('Pulled before posting: ', 'Off the card: ', 'before its post went out: ', ' ET: '):
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    for tail in ('. Published cutoff', '. Stays in the record'):
        text = text.split(tail, 1)[0]
    return text.strip().rstrip('.')


def leg_single(leg, parlay):
    """A parlay leg as a single play on its game: what a closed single is matched against and what the last look
    checks before the ticket posts."""
    league = parlay.get('league') or parlay.get('_league') or str(parlay.get('id', '')).split('-')[0]
    return dict(leg_pick(leg), id=f"{parlay.get('id')}/{leg.get('id')}", title=leg.get('title'), gameIds=[leg.get('gameId')],
                odds=leg.get('odds'), book=leg.get('book') or parlay.get('book'), league=league, _league=league)


def same_bet(a, b):
    """The same game, market, side and player, whatever the line."""
    return (a.get('gameIds') or [None])[0] == (b.get('gameIds') or [None])[0] and gates.market_key(a) == gates.market_key(b) \
        and gates.side_of(a) == gates.side_of(b) and str(a.get('athleteId') or '') == str(b.get('athleteId') or '')


def closed_singles(ctx, closing=()):
    """[(single play, why it closed)] for every single play closed to new entries: in the record, and `closing`,
    the revisions this pass is writing."""
    out = {}
    for key, pick in ctx.first.items():
        merged = dict(pick, **ctx.latest.get(key, {}))
        if not pick.get('historicalImport') and not merged.get('legs') and not merged.get('parlayType') and merged.get('entryNote'):
            out[key] = (merged, closed_reason(merged['entryNote']))
    for revision in closing:
        if not revision.get('legs') and not revision.get('parlayType') and revision.get('entryNote'):
            out[revision['id']] = (revision, closed_reason(revision['entryNote']))
    return list(out.values())


def pulled_leg(parlay, ctx, closing=()):
    """(leg, why) for the first leg of a parlay that is a single play the desk has closed, or None."""
    closed = closed_singles(ctx, closing)
    for leg in parlay.get('legs') or []:
        single = leg_single(leg, parlay)
        why = next((reason for other, reason in closed if same_bet(single, other)), None)
        if why is not None:
            return leg, why
    return None


def parlay_note(now, reason, pick, before_post=False):
    label = 'Pulled before posting:' if before_post else 'Off the card:'
    return f"{label} {str(reason).rstrip('. ')}. Stays in the record at {int(pick['odds']):+d} and is graded as posted."


def parlay_closures(ctx, raw_first, games, now, closing=()):
    """Revisions closing every open fun parlay, not yet under way, that carries a leg the desk has pulled."""
    out = []
    for key, pick in ctx.first.items():
        merged = dict(pick, **ctx.latest.get(key, {}))
        if not merged.get('legs') or key not in raw_first or merged.get('result') or merged.get('entryNote') \
                or (merged.get('status') or 'active') != 'active':
            continue
        starts = [gates.when(games[g]['kickoff']) for g in merged.get('gameIds') or [] if g in games]
        if not starts or min(starts) <= now:
            continue
        hit = pulled_leg(merged, ctx, closing)
        if hit:
            kind_key, original = raw_first[key]
            reason = f"its {hit[0].get('title')} leg was pulled: {hit[1]}"
            out.append((merged.get('league') or key.split('-')[0], kind_key, dict(original, status='expired', entryNote=parlay_note(now, reason, original))))
    return out


def longshot_exclusions(ctx, screened, closing=()):
    """Game ids a fun parlay leaves off: games where the desk closed a single play, and games this run found a
    sourced reason against (weather, a quarterback, verified reporting)."""
    out = {(pick.get('gameIds') or [None])[0] for pick, _ in closed_singles(ctx, closing)}
    # A precheck can pull one parlay leg without closing a corresponding single.
    # Keep that game's line out of every replacement; the Oct 4 QB-out ticket
    # otherwise selected the same Packers/Buccaneers total a second time.
    for key, original in ctx.first.items():
        out.update(flagged_parlay_leg_games(dict(original, **ctx.latest.get(key, {}))))
    for revision in closing:
        out.update(flagged_parlay_leg_games(revision))
    for row in screened:
        rule, reason = row.get('rule'), str(row.get('reason') or '')
        # A missing lookup is not adverse evidence about the whole game.
        # Ticket construction still requires each leg's supporting reason and
        # ordinary admission/release checks; this grants no research clearance.
        unchecked = reason.startswith((
            UNCONFIRMED,
            'the eight-check research budget is used;',
            'the prop research allocation is used;',
            'the side research allocation is used;',
            'the total research allocation is used;',
            'the news researcher is unavailable in this run',
            'the news check returned no verified player-availability evidence;',
            'the current estimated chance does not beat the price; no news lookup was spent',
        ))
        if rule in AGAINST_RULES or (rule == 'held' and not unchecked):
            out.add(row.get('gameId'))
    return {g for g in out if g}


def flagged_parlay_leg_games(pick):
    """Games of specifically named legs pulled by a sourced last-look note."""
    if not pick.get('legs') or not pick.get('entryNote'):
        return set()
    note = closed_reason(pick['entryNote'])
    match = re.search(r'\bits\s+(.+?)\s+leg(?:\s+was\s+pulled\b|\s*:)', note, re.I)
    if not match:
        return set()
    wanted = ' '.join(match.group(1).lower().split())
    return {leg.get('gameId') for leg in pick['legs']
            if ' '.join(str(leg.get('title') or '').lower().split()) == wanted and leg.get('gameId')}


def replacement_has_last_look(ticket, games, now):
    """A replacement needs room for a scheduled precheck and the 45-minute kickoff cutoff."""
    starts = [gates.when(games[game_id]['kickoff']) for game_id in ticket.get('gameIds') or [] if game_id in games]
    return bool(starts and now + REPLACEMENT_REVIEW_LEAD <= min(starts) - post_windows.LEAD)


# ------------------------------------------------------------------ steps 4 to 7: candidates, prices, facts

def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-')


def line_slug(line):
    return f'{float(line):g}'.replace('.', '-').replace('-', 'minus-', 1) if float(line) < 0 else f'{float(line):g}'.replace('.', '-')


def candidates(lines, games, now):
    """Game-day board rows our number likes, as unpriced candidate picks.

    The board may carry the whole weekend, but the owner-plan admission run may
    only create a play on the Eastern day that game kicks off.
    """
    out = []
    today = eastern_date(now)
    for row in lines:
        game = games.get(row.get('gameId'))
        grade = row.get('grade') or {}
        if not game or row.get('state') != 'open' or game.get('state') != 'pre' or not grade:
            continue
        if eastern_date(gates.when(game['kickoff'])) != today:
            continue
        if gates.when(game['kickoff']) <= now + PUBLISH_MARGIN:
            continue
        books = [(q['book'], q['line'], q.get('odds')) for q in row.get('books') or []
                 if isinstance(q.get('odds'), (int, float))] or [(row['book'], row['line'], row.get('odds'))]
        if row.get('gameMarket'):
            if row.get('market') not in ('total points', 'point spread', 'moneyline'):
                continue
            spread, moneyline = row['market'] == 'point spread', row['market'] == 'moneyline'
            direction = row.get('side') if (spread or moneyline) else row['direction']
            out.append({'status': 'active', 'favorite': False, 'modelLean': not spread,
                        'marketType': 'moneyline' if moneyline else 'spread' if spread else 'total',
                        'line': row['line'], 'direction': direction, 'gameIds': [game['id']],
                        '_league': game['league'], '_row': row, '_quotes': books,
                        '_pair': (row.get('odds'), row.get('oppositeOdds')) if moneyline else None})
        elif row.get('athleteId'):
            out.append({'status': 'active', 'favorite': False, 'modelLean': True, 'position': row.get('position'),
                        'athleteId': str(row['athleteId']), 'market': row.get('stat') or pricing.market_of(row),
                        'line': row['line'], 'direction': row['direction'], 'gameIds': [game['id']],
                        '_league': game['league'], '_player': row.get('player'), '_row': row, '_quotes': books})
    # The strongest reads first, so a daily cap admits the best of them.
    out.sort(key=lambda c: (-((c['_row'].get('grade') or {}).get('edge') or 0),
                            str(c['_row'].get('id') or '')))
    return out


def load_candidate_lines(path, logger=log):
    """Fail closed without taking settlement, cards, or the rest of the desk run down."""
    try:
        return line_payload.load(path)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        logger(f'line catalog unavailable; official selection skipped: {exc}')
        return []


def dossier_support_issue(case):
    """Two independent numbered facts are required before a straight joins the public record."""
    reasons = {str(row.get('text') or '').strip() for row in (case.get('reasons') or [])
               if isinstance(row, dict) and re.search(r'\d', str(row.get('text') or ''))}
    if len(reasons) < 2:
        return 'fewer than two numbered supporting reasons in the case file'
    if any(row.get('hard') for row in (case.get('risks') or []) if isinstance(row, dict)):
        return 'the case file has a hard risk'
    return None


CARD_PROP_PRICES = (-160, 200)     # positive-EV props remain eligible through +200
                                   # toward 50% (the calibration) overstates a plus-money over the market prices at 42%
PROVISIONAL_K = 0.2                # a league's player chances before learning has calibrated them (the NFL's is 0.13)


def rank_card(wanted, ctx):
    """The card's candidates, best first: by our calibrated number against the price (a player's chance shrunk by the
    league's learned k, or PROVISIONAL_K before there is one). Recent underperformance raises the required edge;
    it does not automatically remove a line. Card size is a ceiling, never a quota. The direction rules (owner,
    2026-10-07) add their raised bar, send a segment paused as a best bet to the back, and let a winning segment
    rank first among the lines that clear their bar, inside the same caps."""
    import direction
    import learning
    def score(c):
        row, league = c['_row'], c['_league']
        grade = row.get('grade') or {}
        pick = dict(c, league=league)
        if c.get('athleteId'):
            raw, needs = grade.get('raw'), grade.get('needs')
            k = ((ctx.policy.get('calibration') or {}).get(f'{league}/prop') or {}).get('k')
            k = PROVISIONAL_K if k is None else k
            edge = 100 * (0.5 + k * (raw - 0.5) - needs) if raw is not None and needs is not None else -99.0
            behind = gates.trailing_prop_market(pick, ctx) is not None
        else:
            edge, behind = float(grade.get('edge') or -99.0), False
        segment = learning.segment_of(pick)
        cautious = learning.paused(ctx.policy, segment) or behind
        need = gates.PERFORMANCE_PROP_EDGE if c.get('athleteId') and cautious else \
               gates.PERFORMANCE_GAME_EDGE if cautious else 0
        need += direction.edge_raise(ctx.policy, segment, ctx.now)
        stopped = direction.paused(ctx.policy, segment, ctx.now)
        first = direction.priority(ctx.policy, segment, ctx.now)
        trust = direction.trust(ctx.policy, segment)
        c['_rank'] = {'edge': round(edge, 1), 'performanceCaution': cautious, 'requiredEdge': need}
        market_priority = 0 if c.get('athleteId') else 1 if c.get('marketType') in ('spread', 'moneyline') else 2
        # Price and news-review capacity is finite. Check the next slate before
        # spending those slots on a later Monday game; within a game day, keep
        # the owner's props/sides/totals priority and the usual value order.
        day = gates.slate_day(c, ctx) or date.max
        return (bool(stopped or edge <= 0 or edge < need), day, market_priority, not first, -trust, -edge,
                str(c.get('id') or row.get('id') or ''))
    kept = [c for c in wanted if not c.get('athleteId')
            or isinstance(c['_row'].get('odds'), (int, float)) and CARD_PROP_PRICES[0] <= c['_row']['odds'] <= CARD_PROP_PRICES[1]]
    return sorted(kept, key=score)


def readable_leg(leg, games):
    """A leg the way a post says it: "Iowa at Michigan over 38.5", "Coastal +2.5". None when it cannot say."""
    import pick_card
    game = games.get(leg.get('gameId'))
    if not game or not isinstance(leg.get('line'), (int, float)):
        return None
    league, side = game.get('league'), str(leg.get('side') or '').lower()
    if leg.get('market') == 'total points' and side in ('over', 'under'):
        return f"{pick_card.team_label(game.get('away'), league)} at {pick_card.team_label(game.get('home'), league)} {side} {pricing.fmt(float(leg['line']))}"
    if leg.get('market') == 'point spread' and side in ('home', 'away'):
        return f"{pick_card.team_label(game.get(side), league)} {pricing.signed(float(leg['line']))}"
    return None


def longshot_alternates(ctx, games, now, league, exclude=()):
    """True SharpAPI alternate rungs for a lotto/longshot, with no new network calls or credits."""
    if ctx is None or not getattr(ctx, 'prop_odds', None):
        return []
    if league in gates.OWN_CALIBRATION and not (((getattr(ctx, 'policy', None) or {}).get('calibration') or {}).get(f'{league}/prop')):
        return []
    import ladder
    seen = ladder.confirmed_at()
    today = ladder.todays_games(games, now, league, exclude)
    legs = [leg for game in today for leg in ladder.legs_for_game(game, ctx.prop_odds.get(game['id']), ctx, now, seen)]
    return [dict(leg, league=league) for leg in legs if leg.get('alternate') is True]


def longshot_candidate(lines, games, now, league, exclude=(), ctx=None):
    # Main lines first. Remove player exposure before ranking, so another eligible leg can replace it.
    lines = gates.without_straight_players(lines, ctx) if ctx is not None else lines
    import direction
    # Owner Oct. 11: a small pregame fun ticket, +500 to +1500, 3-4 legs,
    # one book/different games and at most one total. Every leg gets its own
    # saved reason below before the ticket may publish.
    policy = getattr(ctx, 'policy', None)
    shape = direction.fun_shape(policy, now) if ctx is not None else None
    target, options = 500, {'max_legs': 4, 'price_range': (500, 1500), 'max_totals': 1}
    # Prospective owner reset; historical replays retain their original shape.
    if eastern_date(now).isoformat() >= '2026-10-23':
        target = 400
        options.update(min_legs=4, max_legs=8, price_range=(400, 1000))
    if shape:
        options['max_legs'] = min(options['max_legs'], shape['legs'][1])
        lines = direction.fun_legs(policy, lines, now, league)
    ticket, reason = parlay.build(lines, now, None, target, league, exclude, **options)
    if not ticket and ctx is not None and gates.alternate_parlay_frequency({'league': league, 'parlayType': 'easyProps'}, ctx).ok:
        alternates = gates.without_straight_players(longshot_alternates(ctx, games, now, league, exclude), ctx)
        if shape:
            alternates = direction.fun_legs(policy, alternates, now, league)
        ticket, reason = parlay.build(lines, now, None, target, league, exclude, alternates, **options)
    if not ticket:
        return None, reason
    for leg in ticket['legs']:
        if leg.get('market') == 'point spread' and not leg.get('side'):
            leg['side'] = 'home'          # the board's spread row is the home side unless it names the away side
        leg['title'] = readable_leg(leg, games) or leg['title']
    first = games.get(ticket['gameIds'][0]) or {}
    day = eastern_date(now)
    return {'id': f"{league}-{first.get('season', day.year)}-W{first.get('week', 0)}-longshot-{day:%m%d}-{BOOK_SLUG.get(ticket['book'], slug(ticket['book']))}",
            'title': f"{len(ticket['legs'])}-leg longshot at {ticket['book']}", 'status': 'active', 'favorite': False,
            'parlayType': 'longshot', 'riskUnits': parlay.STAKE, 'legs': ticket['legs'],
            'correlation': 'One leg per game, so the ticket treats the legs as independent; its chance is their product.',
            'gameIds': ticket['gameIds'], '_league': league, 'book': ticket['book'], 'odds': ticket['odds'],
            'quotedAt': ticket['quotedAt'], 'quoteType': 'capture', 'confidence': 1, 'priceEstimated': True,
            'expiresAt': stamp(min(gates.next_slot(now), gates.when(ticket['firstKickoff']))),
            'edge': (f"Estimated combined price from captured leg odds; verify the sportsbook's ticket price. Our chance {100 * ticket['fairChance']:.1f}% against {100 * ticket['breakEven']:.1f}% break-even at "
                     f"{ticket['odds']:+d}: {ticket['evPerUnit']:+.3f}u per unit staked, {parlay.STAKE}u at risk."),
            'cutoff': 'A longshot is not re-entered. It stands or falls as posted.',
            'sources': sorted(({games[g]['source'] for g in ticket['gameIds'] if g in games and games[g].get('source')}
                               | {row['source'] for row in lines if row.get('id') in {l['id'] for l in ticket['legs']} and row.get('source')}
                               | ({'https://sharpapi.io/'} if any(l.get('alternate') for l in ticket['legs']) else set())))}, None


def attach_ticket_reasons(ticket, ctx, research_status=None):
    """Save one directional, sourced reason per fun-ticket leg; list legs that do not have one."""
    missing = []
    league = ticket.get('_league') or ticket.get('league')
    for leg in ticket.get('legs') or []:
        case = dict(leg, gameIds=[leg.get('gameId')], _league=league,
                    direction=leg.get('direction') or leg.get('side'),
                    _team=(getattr(ctx, 'player_team', {}) or {}).get(str(leg.get('athleteId') or '')),
                    _player=leg.get('player'))
        try:
            case['_evidence'] = evidence(case, ctx, getattr(ctx, 'context_file', {}) or {})
            saved = plan_reasons(case, ctx)
        except (KeyError, TypeError, ValueError, AttributeError):
            saved = []
        if (not any(r.get('direction') == 'for' and r.get('text') for r in saved)
                and research_status is not None and research_status.get('on')
                and researcher.enabled() and research_status.get('asked', 0) < RESEARCH_LIMIT):
            game = ctx.games.get(leg.get('gameId'))
            if game:
                research_status['asked'] = research_status.get('asked', 0) + 1
                try:
                    kept, dropped = researcher.research(
                        game, gates.market_key(case), gates.side_of(case), now=ctx.now,
                        player=case.get('_player'), quarterbacks=quarterbacks(game, ctx))
                except (OSError, TypeError, ValueError, AttributeError):
                    kept, dropped = [], []
                case['_research'] = [dict(f, verified=True) for f in kept] + [dict(f, verified=False) for f in dropped]
                research_status['verified'] = research_status.get('verified', 0) + len(kept)
                research_status['dropped'] = research_status.get('dropped', 0) + len(dropped)
                saved = plan_reasons(case, ctx)
                log(f"researched parlay leg {leg.get('title')}: {len(kept)} verified facts, {len(dropped)} dropped")
        leg['reasons'] = saved
        leg['reason'] = next((row.get('text') for row in saved
                              if row.get('direction') == 'for' and row.get('text')), None)
        if not leg['reason']:
            missing.append(leg.get('title') or leg.get('id') or 'leg')
    return missing


def ticket_replacement_allowed(ticket_id, ctx):
    return (ctx.latest.get(ticket_id) or {}).get('replacementAllowed') is not False


def choose_straight_tier(candidate, ctx):
    """Prospective owner hierarchy; ordinary safety and card-cap gates still apply."""
    chef = gates.selection_verdict(candidate, ctx, 'chef_pick')
    if chef.ok:
        if chef.data.get('chefEvidence'):
            candidate['chefEvidence'] = chef.data['chefEvidence']
        candidate.update(lane='chef_pick', riskUnits=2)
        gates.staking.apply(candidate, ctx.now)
        return chef
    candidate.pop('chefEvidence', None)
    regular = gates.selection_verdict(candidate, ctx, 'best_bet')
    if regular.ok:
        candidate.update(lane='best_bet', riskUnits=1)
        gates.staking.apply(candidate, ctx.now)
    return regular


def price(candidate, ctx, now):
    """Take the quote with the best expected value; copy the desk's numbers verbatim."""
    game = ctx.games[candidate['gameIds'][0]]
    snapshot = ctx.snapshot(game['id'])
    market, side = gates.market_key(candidate), gates.side_of(candidate)
    if not snapshot or not market:
        return None
    # A catalog row can carry only the quote that produced that row.  Shop the
    # full current capture too, otherwise an incomplete row can be refused by
    # best_quote_by_ev even though the usable better quote is sitting in the
    # same odds snapshot.
    available = list(candidate.get('_quotes') or [])
    available += gates.quotes_for(dict(candidate, _quotes=None), ctx, priced_only=True)
    seen_quotes = set()
    priced = []
    for book, line, odds in available:
        quote_key = (role_sanity.book_key(book), line, odds)
        if quote_key in seen_quotes:
            continue
        seen_quotes.add(quote_key)
        if not gates.official_quote_book(book):
            continue
        if not isinstance(odds, (int, float)) or abs(odds) < 100:
            continue
        if candidate.get('athleteId') and (odds < -400 or odds > 400):
            continue
        if candidate.get('athleteId'):
            record = ctx.prop_odds.get(game['id'])
            quotes = build_site.price_quotes(record, market, candidate.get('_player') or gates.player_name(candidate, ctx), line)
            if role_sanity.quote_issue(quotes, book, line, side, odds):
                continue
        try:
            p = gates.calibrated_desk(pricing.price(snapshot, market, side, float(line), int(odds), candidate.get('athleteId')), candidate, ctx)
        except (ValueError, KeyError):
            continue
        if candidate.get('athleteId'):
            pair = next((q for q in quotes if role_sanity.book_key(q[0]) == role_sanity.book_key(book)
                         and q[1] == line), None)
            other = pair[3] if pair and side == 'over' else pair[2] if pair else None
            fair = pricing.fair_chance(odds, other) if isinstance(other, (int, float)) else None
            if role_sanity.price_suspect(odds, p.get('rawChance'), fair=fair):
                continue
        probe = dict(candidate, book=book, line=float(line), odds=int(odds), _desk=p)
        if candidate.get('athleteId') and isinstance(other, (int, float)):
            probe['_pair'] = (int(odds), int(other))
        numbers = gates.selection_numbers(probe, ctx)
        if not numbers:
            continue
        p = dict(p, **{key: numbers[key] for key in
                       ('chance', 'breakEven', 'edgePoints', 'evPerUnit', 'calibration', 'calibrated')})
        p['edge'] = (f"Price-checked chance {p['chance']:.1%} against the exact two-sided price; "
                     f"{p['breakEven']:.1%} needed at {int(odds):+d}: {p['edgePoints']:+.1f} percentage points.")
        priced.append((p['evPerUnit'], book, float(line), int(odds), p, numbers))
    if not priced:
        return None
    _, book, line, odds, p, selection = max(priced, key=lambda q: (q[0], q[1]))
    row = candidate.get('_row') or {}
    books = sorted({b for b, _, _ in available if gates.official_quote_book(b)})
    seen = row.get('observedAt') or stamp(now)
    note = f"{book}'s number and price from the {et(seen)} capture across {len(books)} book{'s' if len(books) != 1 else ''}"
    note += ', the best expected value on the board for this side.' if len(books) > 1 else f'; {book} is the only book with this market so far.'
    kickoff = gates.when(game['kickoff'])
    candidate.update(book=book, line=line, odds=odds, _desk=p, projection=p['projection'], edge=p['edge'],
                     cutoff=p['cutoff'], modelVersion=p['model'], snapshotAt=p['snapshotAt'], quotedAt=seen,
                     quoteType='capture', quoteNote=note, expiresAt=stamp(min(gates.next_slot(now), kickoff)))
    selection = gates.selection_numbers(candidate, ctx)
    if not selection:
        return None
    candidate['_selection'] = selection
    # Version every new football admission. Already-public plays retain their
    # original lane and stake; the policy is never retrofitted onto the record.
    if not candidate.get('publishedAt') and game.get('league') in ('NFL', 'CFB'):
        candidate.update(selectionPolicy=gates.TIER_POLICY, lane='best_bet', riskUnits=1)
        gates.staking.apply(candidate, now)
    p = dict(p, **{key: selection[key] for key in
                   ('chance', 'breakEven', 'edgePoints', 'evPerUnit', 'calibration', 'calibrated')})
    candidate['_desk'] = p
    candidate['edge'] = p['edge']
    candidate['probabilityAtPublication'] = {key: p.get(key) for key in
        ('rawChance', 'chance', 'calibrated', 'calibration', 'calibrationN', 'push', 'breakEven', 'edgePoints', 'evPerUnit', 'snapshotAt')}
    import chef_picks
    candidate['probabilityAtPublication']['probabilitySpec'] = chef_picks.specification(candidate, ctx)
    candidate['probabilityAtPublication']['evaluatedAt'] = stamp(now)
    candidate['probabilityAtPublication'].update(fairChance=round(selection['fairChance'], 3),
                                                 anchoredChance=selection['anchoredChance'],
                                                 gap=round(selection['gap'], 1),
                                                 calibrationFamily=selection['calibrationFamily'])
    if selection.get('calibrationMethod'):
        candidate['probabilityAtPublication']['calibrationMethod'] = selection['calibrationMethod']
    away, home = game['away'], game['home']
    candidate['matchup'] = f"{away.get('name') or away.get('abbreviation')} at {home.get('name') or home.get('abbreviation')}"
    if candidate.get('athleteId'):
        words = pricing.WORDS[market]
        name = candidate.get('_player') or ctx.names.get(candidate['athleteId'], 'Player')
        candidate['title'] = f"{name} {side.upper()} {pricing.fmt(line)} {words}"
        last = slug(name.split()[-1] if name.split() and name != 'Player' else candidate['athleteId'])
        candidate['id'] = f"{game['league']}-{game['season']}-W{game.get('week', 0)}-{last}-{side}-{line_slug(line)}-{market.lower()}-{BOOK_SLUG.get(book, slug(book))}"
        candidate['confidence'] = 2
    else:
        candidate['title'] = (f"{pick_card.team_label(game[side], game['league'])} MONEYLINE"
                              if market == 'moneyline' else
                              f"{pick_card.team_label(game[side], game['league'])} {pricing.signed(line)}"
                              if market == 'spread' else
                              f"{pick_card.team_label(away, game['league'])} at {pick_card.team_label(home, game['league'])} {side} {pricing.fmt(line)}")
        candidate['id'] = (f"{game['league']}-{game['season']}-W{game.get('week', 0)}-{away['abbreviation'].lower()}-"
                           f"{home['abbreviation'].lower()}-{('spread-' if market == 'spread' else 'ml-' if market == 'moneyline' else '')}{side}-{line_slug(line)}-{BOOK_SLUG.get(book, slug(book))}")
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
            elif (player.get('position') == 'QB' and status in gates.QB_OUT
                  and str(player.get('id')) == str(ctx.starters.get(gates.team_key(game['league'], team)) or '')):
                if market in ('spread', 'moneyline') and not athlete:
                    direction = 'against' if candidate.get('direction') == side else 'for'
                elif market == 'total' or ctx.player_team.get(athlete) == team:
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


def plan_reasons(candidate, ctx):
    """Directional reasons in the exact owner-plan shape, from stored facts only."""
    import market_support
    now = stamp(ctx.now)
    reasons = []
    for fact in [*(candidate.get('_evidence') or []), *(candidate.get('_research') or [])]:
        if fact.get('direction') != 'for' or not (fact.get('claim') or fact.get('text')):
            continue
        if not market_support.allowed(candidate, fact.get('text') or fact.get('claim'), ctx.now):
            continue
        kind = fact.get('kind') or fact.get('type')
        reason_type = 'news' if researcher.from_web(fact) else {
            'injury': 'injury_role', 'role': 'injury_role', 'weather': 'weather',
        }.get(kind, kind)
        if reason_type not in gates.CLASS_A_REASONS | {'matchup', 'usage_trend', 'pace', 'hit_strip'}:
            continue
        reasons.append({'type': reason_type, 'class': 'A' if reason_type in gates.CLASS_A_REASONS else 'B',
                        'direction': 'for', 'text': fact.get('text') or fact.get('claim'),
                        'number': fact.get('numbers'), 'source': fact.get('source'),
                        'observedAt': fact.get('observedAt') or fact.get('retrievedAt') or now})
    # A current, quantified model-versus-market difference is itself a real
    # reason for an NFL side.  Earlier code accepted only injury/news Class A
    # facts here, which made ordinary positive-value Sunday spreads impossible
    # even after the owner approved them as 0.5u Full Sends.  Keep this bounded:
    # the model margin must sit at least one point through the posted spread;
    # selection_verdict still requires positive value at a fresh two-sided price.
    market = gates.market_key(candidate)
    desk = candidate.get('_desk') or {}
    game = ctx.games.get((candidate.get('gameIds') or [None])[0]) or {}
    side = gates.side_of(candidate)
    projection = desk.get('projection')
    line = candidate.get('line')
    if market == 'spread' and side in ('home', 'away') \
            and isinstance(projection, (int, float)) and isinstance(line, (int, float)):
        through = projection + line if side == 'home' else -projection + line
        if through >= 1.0:
            team = pick_card.team_label(game.get(side) or {}, game.get('league'))
            book_line = pricing.signed(float(line))
            model_line = pricing.signed(float(-projection if side == 'home' else projection))
            reasons.append({'type': 'projection_edge', 'class': 'B', 'direction': 'for',
                            'text': f"The book has {team} {book_line}; my margin makes it {team} {model_line}.",
                            'number': {'bookLine': float(line), 'modelLine': float(-projection if side == 'home' else projection),
                                       'pointsThrough': round(through, 1)},
                            'source': game.get('source'), 'observedAt': now})
    if candidate.get('athleteId'):
        line, side, market = float(candidate['line']), gates.side_of(candidate), gates.market_key(candidate)
        game = ctx.games[candidate['gameIds'][0]]
        team = str(candidate.get('_team') or '')
        logs = [row for row in ctx.player_logs.get(str(candidate['athleteId']), [])
                if row.get('season') == game.get('season') and (not team or str(row.get('team')) == team)]
        adjusted_history = season_trends.history(logs, market, game.get('season'), ctx.now, team,
                                                 ctx.records, candidate.get('athleteId'))
        position = features.GROUP.get(next((row.get('pos') for row in reversed(logs) if row.get('pos')), None))
        opponent = next((str(game[where]['id']) for where in ('home', 'away')
                         if str(game[where]['id']) != team), None)
        opponent_adjustment = None
        if adjusted_history and position and opponent and side in ('over', 'under'):
            fbs = {str(value) for value in model_v2.fbs_teams(ctx.records)} if game.get('league') == 'CFB' else set()
            adjusted_history, _dvp, _splits, opponent_adjustment = season_trends.opponent_context(
                adjusted_history, line, side, game.get('league'),
                cached_defense_logs(ctx, game.get('league')),
                position, market, game.get('season'), gates.when(game['kickoff']), opponent, fbs)
        values = [row['value'] for row in adjusted_history]
        if game.get('league') == 'CFB':
            values = [row['value'] for row in adjusted_history if row.get('opponentQuality') != 'fcs']
        recent = values[-10:]
        hit = lambda value: value > line if side == 'over' else value < line
        season_hits, recent_hits = sum(map(hit, values)), sum(map(hit, recent))
        if opponent_adjustment and opponent_adjustment.get('against'):
            reasons.append({'type': 'matchup', 'class': 'B', 'direction': 'against',
                            'text': 'Most of this trend came against FCS or bottom-30 defenses; tonight is a top-30 defense.',
                            'number': opponent_adjustment, 'source': game.get('source'), 'observedAt': now})
        elif (not opponent_adjustment or opponent_adjustment.get('supports')) and len(recent) >= 7 \
                and recent_hits >= 7 and values and season_hits / len(values) >= .60:
            fill = ' including last season' if any(row.get('priorSeason') for row in adjusted_history) else ''
            reasons.append({'type': 'hit_strip', 'class': 'B', 'direction': 'for',
                            'text': f'{side.title()} {pricing.fmt(line)} in {recent_hits} of his last {len(recent)} comparable games{fill}.',
                            'number': {'recentHits': recent_hits, 'recentGames': len(recent),
                                       'seasonHits': season_hits, 'seasonGames': len(values)},
                            'source': game.get('source'), 'observedAt': logs[-1].get('kickoff') if logs else now})
        volume_key = ('pbpTgt' if market in ('rec', 'recYds') else 'car' if market in ('car', 'rushYds')
                      else 'att' if market in ('att', 'cmp', 'passYds') else None)
        team_key = 'att' if volume_key in ('pbpTgt', 'att') else 'rushAtt'
        stored_games = {str(item.get('eventId')): item for item in ctx.records}
        shares = []
        for log_row in logs:
            source_game = stored_games.get(str(log_row.get('eventId')))
            total = (((source_game or {}).get('teams') or {}).get(str(log_row.get('team'))) or {}).get(team_key)
            volume = (log_row.get('stats') or {}).get(volume_key) if volume_key else None
            if isinstance(volume, (int, float)) and isinstance(total, (int, float)) and total > 0:
                shares.append(volume / total)
        if len(shares) >= 4:
            recent_share, season_share = sum(shares[-3:]) / 3, sum(shares) / len(shares)
            change = recent_share / season_share - 1 if season_share else 0
            if (side == 'over' and change >= .20) or (side == 'under' and change <= -.20):
                reasons.append({'type': 'usage_trend', 'class': 'B', 'direction': 'for',
                                'text': f"Usage share is {recent_share:.1%} over the last 3, versus {season_share:.1%} this season.",
                                'number': {'last3Share': recent_share, 'seasonShare': season_share},
                                'source': game.get('source'), 'observedAt': logs[-1].get('kickoff') if logs else now})
        latest_log = logs[-1] if logs else None
        if latest_log and latest_log.get('pos') in ('QB', 'RB', 'WR', 'TE'):
            opponent = next((str(game[where]['id']) for where in ('home', 'away')
                             if str(game[where]['id']) != str(latest_log.get('team'))), None)
            table = [row for row in features.defense_table(cached_defense_logs(ctx, game.get('league')),
                                                           f"{latest_log['pos']}.{market}", season=game.get('season'))
                     if row.get('n', 0) >= 3]
            table.sort(key=lambda row: (row['avg'], row['defense']))
            for rank, row in enumerate(table, 1):
                row['rank'] = rank
            own = next((item for item in table if str(item['defense']) == opponent), None)
            count = 10 if game.get('league') == 'NFL' else 25
            if own and ((side == 'over' and own['rank'] > len(table) - count)
                        or (side == 'under' and own['rank'] <= count)):
                adjective = 'most' if side == 'over' else 'fewest'
                display_rank = len(table) - own['rank'] + 1 if side == 'over' else own['rank']
                reasons.append({'type': 'matchup', 'class': 'B', 'direction': 'for',
                                'text': f"The opponent allows the {ordinal(display_rank)}-{adjective} {pricing.WORDS.get(market, market)} to {latest_log['pos']}s.",
                                'number': {'rank': own['rank'], 'teams': len(table), 'average': own['avg']},
                                'source': game.get('source'), 'observedAt': now})
        history = sorted((row for row in ctx.prop_odds_history.get(candidate['gameIds'][0], [])
                          if row.get('retrievedAt') and gates.when(row['retrievedAt']) <= ctx.now),
                         key=lambda row: row['retrievedAt'])
        book_key = role_sanity.book_key(candidate.get('book'))
        values = []
        for capture in history:
            quote = next((q for q in build_site.price_quotes(capture, market,
                          candidate.get('_player') or gates.player_name(candidate, ctx))
                          if role_sanity.book_key(build_site.BOOK_NAMES.get(q[0], q[0])) == book_key), None)
            if quote:
                _, quoted_line, over, under = quote
                price = over if side == 'over' else under
                if isinstance(price, (int, float)):
                    values.append((float(quoted_line), int(price), capture['retrievedAt']))
        if len(values) >= 2:
            first, current = values[0], values[-1]
            line_toward = (current[0] - first[0]) * (1 if side == 'over' else -1)
            cents_toward = pricing.cents(first[1]) - pricing.cents(current[1])
            if line_toward >= 1 or cents_toward >= 15:
                reasons.append({'type': 'line_move', 'class': 'A', 'direction': 'for',
                                'text': f"{candidate['book']} moved toward this side from {first[0]:g} to {current[0]:g}.",
                                'number': {'firstLine': first[0], 'currentLine': current[0],
                                           'centsToward': cents_toward},
                                'source': candidate.get('sources', [None])[0], 'observedAt': current[2]})
    else:
        history = sorted((row for row in ctx.odds_history.get(candidate['gameIds'][0], [])
                          if row.get('retrievedAt') and gates.when(row['retrievedAt']) <= ctx.now),
                         key=lambda row: row['retrievedAt'])
        book_key = role_sanity.book_key(candidate.get('book'))
        quoted = []
        market, side = gates.market_key(candidate), gates.side_of(candidate)
        for capture in history:
            entry = next((value for name, value in (capture.get('books') or {}).items()
                          if role_sanity.book_key(build_site.BOOK_NAMES.get(name, name)) == book_key), None)
            offer = (entry or {}).get('total' if market == 'total' else 'spread') or {}
            if market == 'total' and side in ('over', 'under') and isinstance(offer.get('line'), (int, float)):
                quoted.append((offer['line'], offer.get(side), capture['retrievedAt']))
            elif market == 'spread' and side in ('home', 'away') and isinstance(offer.get('home'), (int, float)):
                quoted.append((offer['home'] if side == 'home' else -offer['home'],
                               offer.get('homePrice' if side == 'home' else 'awayPrice'), capture['retrievedAt']))
        if len(quoted) >= 2:
            first, current = quoted[0], quoted[-1]
            line_toward = (current[0] - first[0]) * (1 if market == 'total' and side == 'over' else -1)
            cents_toward = pricing.cents(first[1]) - pricing.cents(current[1]) \
                if isinstance(first[1], (int, float)) and isinstance(current[1], (int, float)) else 0
            if line_toward >= 1 or cents_toward >= 15:
                reasons.append({'type': 'line_move', 'class': 'A', 'direction': 'for',
                                'text': f"{candidate['book']} moved toward this side from {first[0]:g} to {current[0]:g}.",
                                'number': {'firstLine': first[0], 'currentLine': current[0],
                                           'centsToward': cents_toward}, 'source': candidate.get('sources', [None])[0],
                                'observedAt': current[2]})
    # Deterministic de-duplication keeps the same reasons in the run, replay and dossier.
    return list({(row['type'], row['text']): row for row in reasons}.values())


def cached_defense_logs(ctx, league):
    """Build the expensive opponent-position history once per league and run."""
    cache = ctx.__dict__.setdefault('_defense_logs_cache', {})
    if league not in cache:
        cache[league] = features.defense_logs(ctx.records, before=ctx.now, league=league)
    return cache[league]


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


HARD_NEWS = re.compile(r"\b(ruled out|will not (?:play|start|dress|travel)|won'?t (?:play|start|dress|travel)|"
                       r"not expected to (?:play|start)|inactive|suspended|suspension|benched|demoted|"
                       r"lost (?:the|his|her|their) (?:starting )?(?:job|role)|did not travel|out for (?:the )?(?:game|season|week|year)|"
                       r"placed on (?:injured reserve|ir)|doubtful|season-ending)\b", re.IGNORECASE)
AVAILABILITY_UPGRADE = re.compile(
    r"\bupgraded from\s+(?:out|doubtful|questionable|probable)\s+to\s+(?:questionable|probable|available|active)\b",
    re.IGNORECASE,
)


def hard(fact):
    """News that changes who plays: out, doubtful, inactive, suspended, benched; or a flagged forecast. "Questionable",
    a snap share or a fantasy note is not (2026-09-27: all three NFL fun tickets were pulled on notes like those)."""
    if fact.get('kind') == 'weather':
        return fact.get('direction') == 'against'
    if fact.get('kind') not in ('injury', 'role'):
        return False
    claim = str(fact.get('claim') or '')
    # A status word inside a positive update is historical context, not current bad news. On 2026-10-03
    # "upgraded from doubtful to questionable" wrongly pulled Climb Step 3 before its post.
    cleaned = AVAILABILITY_UPGRADE.sub('', claim)
    improved = cleaned != claim
    if not improved and str(fact.get('status') or '').lower() in gates.QB_OUT | {'inactive'}:
        return True
    return bool(HARD_NEWS.search(cleaned))


def hold_reason(candidate, facts):
    """Without a model to weigh the facts, the run holds anything a quarterback listing could turn.

    A quarterback on either team listed at all holds a total; the player's own team's quarterback
    listed holds a prop; three or more skill players out or doubtful on one side holds either; and web reporting
    holds only when it is hard news (`hard`), never a rotation note or a snap count.
    """
    web = [f for f in facts if researcher.from_web(f) and f.get('direction') == 'against' and hard(f)]
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


def should_research_candidate(candidate, candidate_rank, gap, class_a):
    """Spend the bounded news checks on every eligible college candidate in order.

    College availability is a hard publication gate.  Limiting the web check to
    only the first six raw board rows meant later candidates were guaranteed to
    fail for missing the very check required to clear them.  The daily lookup
    ceiling still bounds cost; this only makes those slots follow the eligible
    ranked candidates instead of the pre-gate board positions.
    """
    return needs_research(candidate) or gap > 15 or (candidate_rank < 6 and not class_a)


def relevant_facts(candidate, facts, ctx):
    """The facts that can change what this pick depends on. The line's move is not one: the price is already
    taken at the current number, and backtests show a move away from our number does not hurt our side. Long
    injured reserve is in the projections and the market already. What remains: the player's own listing and
    his starting quarterback for a prop; the starting quarterbacks and a side missing several skill players for
    a total; a weather flag for a total; and verified web injury, role and weather reporting.
    Statistical stories remain context, not separate news holds; filtering one does not disprove it."""
    athlete = str(candidate.get('athleteId') or '')
    team = candidate.get('_team')
    league = candidate.get('_league') or candidate.get('league') or str(candidate.get('id', '')).split('-')[0]
    total = not athlete
    out, skill = [], defaultdict(list)
    for fact in facts:
        kind = fact.get('kind')
        if researcher.from_web(fact):
            if kind in ('injury', 'role', 'weather'):   # statistical reporting is context, not a separate news hold
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
                and (ctx.starters.get(gates.team_key(league, fact.get('team'))) == player
                     or (not ctx.starters.get(gates.team_key(league, fact.get('team'))) and status in gates.QB_OUT)):
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
    selection = candidate.get('_selectionDecision') or candidate.get('_selection') or {}
    import chef_picks
    return {'id': candidate.get('id'), 'league': league, 'season': game.get('season') or now.year,
            'segment': learning.segment_of(row), 'kind': pick_card.play_kind(row), 'title': candidate.get('title'),
            'marketType': candidate.get('marketType'), 'market': candidate.get('market'), 'athleteId': candidate.get('athleteId'),
            'direction': candidate.get('direction'), 'line': candidate.get('line'), 'odds': candidate.get('odds'),
            'book': candidate.get('book'), 'gameIds': candidate.get('gameIds'), 'kickoff': game.get('kickoff'),
            'legs': len(candidate['legs']) if candidate.get('legs') else None,
            'projection': desk.get('projection'), 'chance': selection.get('anchoredChance', desk.get('chance')),
            'rawChance': desk.get('rawChance'), 'breakEven': selection.get('breakEven', desk.get('breakEven')),
            'edgePoints': selection.get('edgePoints', desk.get('edgePoints')),
            'evPerUnit': selection.get('evPerUnit', desk.get('evPerUnit')),
            'confidence': candidate.get('confidence'), 'favorite': candidate.get('favorite') is True,
            'lane': candidate.get('lane'), 'fairChance': selection.get('fairChance'),
            'probabilitySpec': chef_picks.specification(row, ctx),
            'probabilityPolicy': chef_picks.VERSION, 'modelVersion': candidate.get('modelVersion'),
            'gap': selection.get('gap'), 'kitchenScore': candidate.get('_kitchenScore'),
            'planReasons': selection.get('reasons') or candidate.get('_planReasons'),
            'reasons': selection.get('reasons') or candidate.get('_planReasons') or [],
            'decision': decision, 'rules': list(rules), 'reason': reason, 'decidedAt': stamp(now),
            'quotedAt': candidate.get('quotedAt'),
            'facts': {'for': sum(1 for f in facts if f.get('direction') == 'for'),
                      'against': sum(1 for f in facts if f.get('direction') == 'against'),
                      'kinds': sorted({str(f.get('kind')) for f in facts if f.get('kind')})},
            'judge': {'against': verdict.get('argues_against'), 'confidence': verdict.get('confidence'),
                      'facts': len(verdict.get('fact_ids') or [])} if verdict else None,
            'research': [{'domain': urlparse(str(f.get('source') or '')).netloc.lower().removeprefix('www.'),
                          'verified': bool(f.get('verified')), 'kind': f.get('kind'), 'direction': f.get('direction')}
                         for f in candidate.get('_research') or []]}


PAPER_SLOTS = (11, 17, 21, 23)  # silent expansion trials include West Coast and overnight finals


def nba_game_capture_due(slot):
    """Six planned game/prop capture opportunities; late pregame work moves to lunch.

    Keep morning/late-slate coverage and the same free-feed request/time caps.
    The 13:30 Climb worker already runs; no added daily window or paper slot.
    Prop and trial grading still run in the late-night worker.
    """
    return slot.hour in (11, 13, 17, 21) or (slot.hour, slot.minute) in ((6, 45), (8, 30))


def nba_trial_needs_capture(slot, status):
    """Keep existing admission retries, but do not recreate the moved 23:30 capture."""
    return slot.hour != 23 and 'nbaCapture' not in status


def record_nba_roster_capture(args,status):
    # Same existing capture, zero extra feed requests; shadow never admits plays.
    if getattr(args,'no_push',True):return
    import nba_roster_runtime
    try:
        status['nbaRosterContextAdded']=nba_roster_runtime.extend_context(datetime.now(timezone.utc),root=ROOT/'data/nba-roster-research',capture_root=ROOT/'data/nba-capture')
        status['nbaRosterForward']=nba_roster_runtime.record_forward(datetime.now(timezone.utc),root=ROOT/'data/nba-roster-research',capture_root=ROOT/'data/nba-capture')
    except Exception as error:
        status['errors'].append(f'NBA roster research: {type(error).__name__}: {error}')


def early_nba_selection(args, now, slot, status):
    """Use the existing game capture before lengthy football news checks.

    Player research and grading stay later. This moves work, not feed budgets,
    trial limits or evidence gates; admission itself uses the post-capture clock.
    """
    if args.dry_run or args.command != 'run' or not nba_game_capture_due(slot):
        return
    if os.environ.get('KEENROUDY_SPORTS_CAPTURE', '1') == '0':
        return
    try:
        import nba_capture
        status['nbaCapture'] = nba_capture.step(now, scheduled=True)
        log(f"NBA capture: {status['nbaCapture']}")
        record_nba_roster_capture(args,status)
    except Exception as error:
        status['errors'].append(f'nba capture: {type(error).__name__}: {error}')
    try:
        import nba_trial_runtime
        status['nbaTrial'] = nba_trial_runtime.admission(now, capture=nba_trial_needs_capture(slot, status))
        log(f"NBA Trial: {status['nbaTrial']}")
    except Exception as error:
        status['nbaTrial'] = {'state': 'error', 'reason': type(error).__name__}
        status['errors'].append(f'NBA Trial: {type(error).__name__}: {error}')


def current_run_time(args, started):
    """Refresh live eligibility after lock/feed delays; keep explicit replay clocks."""
    if args.dry_run or getattr(args, 'now', None):
        return started
    return max(started, datetime.now(timezone.utc))


def release_before_background(args, status):
    """Release through the same transactional gates while the caller holds the lock."""
    if args.dry_run or args.no_push:
        return
    now = datetime.now(timezone.utc)
    if private_release_ready(now):
        status['releasedBeforeBackground'] = release_private_isolated(now)


def paper_trials(now, slot, status):
    """Silent expansion work: basketball paper picks plus MLB/NHL market evidence. Publish nothing."""
    if slot.hour not in PAPER_SLOTS:
        return
    import sports_posts
    status['sportsSocialPrepared'] = sports_posts.prepare(now)
    try:
        import paper
        result = paper.step(now, log=log)
        status['paper'] = result
        if result.get('recorded') or result.get('graded'):
            log(f"paper trials: {result.get('recorded', 0)} recorded, {result.get('graded', 0)} graded")
    except Exception as error:
        status['errors'].append(f'paper: {type(error).__name__}: {error}')
        log(f'paper: {type(error).__name__}: {error}')
    try:
        import market_lab
        result = market_lab.step(now, log=log)
        status['marketLab'] = result
        if result.get('captured') or result.get('graded'):
            log(f"market lab: {result.get('captured', 0)} changed quotes, {result.get('graded', 0)} finals")
    except Exception as error:
        status['errors'].append(f'market lab: {type(error).__name__}: {error}')
        log(f'market lab: {type(error).__name__}: {error}')


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
        if slot.hour == 23 and slot.minute == 30:
            shadowed = learn.shadow_step(now)
            if shadowed:
                status['learning']['shadows'] = shadowed
                log(f'learning: {shadowed} silent results shadows recorded')
        if slot.weekday() == 1 and slot.hour == 8:
            report = learn.weekly(now)
            status['learning']['changes'] = len(report['changes'])
            log(f"learning: weekly step, {len(report['changes'])} changes; see data/learning/REPORT.md")
            if report.get('directionError'):        # the rest of the week's learning was still saved
                status['learning']['directionError'] = report['directionError']
                status['errors'].append(f"learning: direction rules: {report['directionError']}")
                log(f"learning: direction rules skipped this week ({report['directionError']}); nothing changed direction")
            import direction
            alert("Kook'n Tuesday learning note", learn.owner_note(report, now),
                  priority='default', click=direction.REPORT_LINK)
    except Exception as error:          # the record is worth keeping, never worth a failed run
        status['errors'].append(f'learning: {type(error).__name__}: {error}')
        log(f'learning: {type(error).__name__}: {error}')


RESEARCH_LIMIT = 8          # owner-plan daily news lookups, strongest first
RESEARCH_FAMILY_LIMITS = {'prop': 5, 'side': 2, 'total': 1}


def straight_target(day, games):
    """Minimum honest straight-card depth for a large Saturday/Sunday slate."""
    slate = sum(1 for game in games.values()
                if game.get('league') in ('NFL', 'CFB')
                and eastern_date(gates.when(game['kickoff'])) == day)
    return 5 if day and day.weekday() in (5, 6) and slate >= 10 else 1


def research_family(candidate):
    if candidate.get('athleteId'):
        return 'prop'
    return 'total' if gates.market_key(candidate) == 'total' else 'side'


def research_slot_refusal(candidate, research_status, reclaim=False):
    """Keep the small web budget on positive-value rows and spread it across the board.

    A large college slate used to spend every lookup on the first eight props,
    including rows whose anchored chance did not beat the price. That made all
    later sides fail the availability gate without ever being checked.
    """
    if research_status.get('asked', 0) >= RESEARCH_LIMIT:
        return 'the eight-check research budget is used; availability was not checked'
    numbers = candidate.get('_selection') or {}
    chance = numbers.get('anchoredChance')
    needed = numbers.get('breakEven')
    if isinstance(chance, (int, float)) and isinstance(needed, (int, float)) and chance <= needed:
        return 'the current estimated chance does not beat the price; no news lookup was spent'
    family = research_family(candidate)
    used = (research_status.get('families') or {}).get(family, 0)
    if not reclaim and used >= RESEARCH_FAMILY_LIMITS[family]:
        return f'the {family} research allocation is used; availability was not checked'
    return None


def research_passes(wanted, deferred):
    """Reserve each family's first pass, then reuse only unspent lookup capacity."""
    for rank, candidate in enumerate(wanted):
        yield rank, candidate, False
    for rank, candidate in deferred:
        yield rank, candidate, True


def research_slot_available(candidate, research_status):
    return research_slot_refusal(candidate, research_status) is None


def note_research_slot(candidate, research_status):
    family = research_family(candidate)
    families = research_status.setdefault('families', {})
    families[family] = families.get(family, 0) + 1
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
    if verified_opposition(candidate, facts):
        # The number/style guards cannot prove that a rewrite preserved an
        # opposing fact. Keep the factual caution instead of making that bet.
        status['llm']['kept'] += 2
        log(f"  why/risk templates kept for {candidate.get('title')}: verified opposing evidence")
        return
    for key, task in (('why', llm_tasks.why_for), ('risk', llm_tasks.risk_for)):
        text, note = task(candidate, facts)
        candidate[key] = text
        status['llm']['polished' if note == 'polished' else 'kept'] += 1
        if note != 'polished':
            log(f"  {key} template kept for {candidate.get('title')}: {note}")


# ------------------------------------------------------------------ step 8: prose

def ordinal(value):
    value = int(value)
    suffix = 'th' if 10 <= value % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')
    return f'{value}{suffix}'


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
    cautions = []
    if recent and hits / len(recent) < 0.5:
        cautions.append(f'Only {hits} of the last {len(recent)} games cleared this side of the line; recent results oppose it.')
    if len(recent) < 5:
        cautions.append('Fewer than five stored games at this line; history is limited.')
    team_side, player = pricing.player_line(snapshot, athlete)
    volume = VOLUME.get(market)
    if team_side and player and volume:
        mates = [(p.get(volume, [0])[0], p['id']) for p in snapshot['players'][team_side]['players']
                 if features.GROUP.get(p.get('pos')) == features.GROUP.get(player.get('pos')) and p.get(volume)]
        mates.sort(reverse=True)
        rank = next((i for i, (_, pid) in enumerate(mates, 1) if pid == athlete), None)
        if rank and len(mates) >= 3:
            parts.append(f"Role: {rank}{'st' if rank == 1 else 'nd' if rank == 2 else 'rd' if rank == 3 else 'th'} of {len(mates)} "
                         f"{game[team_side]['abbreviation']} {features.GROUP.get(player.get('pos'))}s by projected {volume}, {player[volume][0]:.1f} a game.")
        elif player.get(volume):
            parts.append(f"Role: projected for {player[volume][0]:.1f} {volume} a game.")
        opponent = game['away' if team_side == 'home' else 'home']
        group = features.GROUP.get(player.get('pos'))
        table = features.defense_table(features.defense_logs(league_records), f'{group}.{market}', season=game['season'])
        if game['league'] == 'CFB':
            import model_v2
            fbs = model_v2.fbs_teams([r for r in league_records if r.get('season', 0) >= game['season'] - 1])
            table = [r for r in table if str(r['defense']) in {str(team) for team in fbs}]
            for value in table:
                value['rank'] = 1 + sum(other['avg'] < value['avg'] for other in table)
        row = next((r for r in table if str(r['defense']) == str(opponent['id'])), None)
        if row:
            parts.append(f"Defense: {opponent['abbreviation']} allows {row['avg']:g} {pricing.WORDS[market]} a game to {group}s, "
                         f"{ordinal(row['rank'])}-stingiest of {len(table)} this season.")
            if (side == 'under' and row['rank'] > len(table) * 0.75) or (side == 'over' and row['rank'] <= len(table) * 0.25):
                cautions.append("The defense leans against this side (that's the whole position group, not just him).")
    for fact in candidate.get('_research') or []:
        if fact.get('verified') and fact.get('direction') == 'against' and fact.get('claim'):
            cautions.append(first_sentence(fact['claim']))
    candidate['reasoning'] = {'history': parts[0], 'context': parts[1:], 'cautions': list(dict.fromkeys(cautions)),
                              'historyNote': 'Past hit rate is context, not the predicted chance; opponents and roles can change.'}
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
               and (f.get('kind') == 'weather' or (f.get('kind') == 'injury' and f.get('verified'))
                    or (researcher.from_web(f) and f.get('verified')
                        and f.get('kind') in ('injury', 'role', 'weather')))]
    return x_post.reason_for({'why': ' '.join(backing)}, weights) if backing else None


def first_sentence(text):
    import x_post
    parts = x_post.sentences(text)
    return (parts[0] if parts else str(text)).rstrip('.') + '.'


def quarterbacks(game, ctx):
    """Each team's starting passers this season, latest first, by name: the researcher is asked about them."""
    out = {}
    for side in ('away', 'home'):
        seen = ctx.passers.get(gates.team_key(game['league'], game[side]['id'])) or []
        names = []
        for pid in reversed(seen):
            name = ctx.names.get(str(pid))
            if name and name not in names:
                names.append(name)
        out[pick_card.team_label(game[side], game['league'])] = names[:3]
    return out


def learning_weights():
    import learning
    return learning.load_policy().get('reasonWeights')


def checked_facts(candidate, limit=2):
    """Up to two verified facts from the web check about who is expected to play, for the reasoning and its sources.
    Only facts that do not argue against the pick: one that did would have held it."""
    facts = [f for f in candidate.get('_research') or [] if f.get('verified') and f.get('kind') in AVAILABILITY
             and f.get('direction') != 'against' and f.get('claim')]
    return facts[:limit]


def verified_opposition(candidate, facts=()):
    """Verified opposing reporting stays visible even when it is not a news hold."""
    out, seen = [], set()
    for fact in [*(candidate.get('_research') or []), *(candidate.get('_evidence') or []), *facts]:
        if not isinstance(fact, dict) or fact.get('verified') is not True or fact.get('direction') != 'against':
            continue
        key = (fact.get('kind'), fact.get('claim'), fact.get('source'))
        if key not in seen:
            out.append(fact)
            seen.add(key)
    return out


def write_prose(candidate, ctx, records):
    """Template why and risk from the pick's own numbers. A model may polish these later; it never adds a number."""
    if candidate.get('legs'):       # a parlay has no single line or side: its words come first, before any are read
        if candidate.get('parlayType') == 'ladder':
            info = candidate['ladder']
            game_lines = any(leg.get('marketType') in ('spread', 'total', 'moneyline') and not leg.get('athleteId') for leg in candidate['legs'])
            candidate['why'] = (f"Ladder step {info['step']}: {len(candidate['legs'])} alternate lines at {candidate['book']}, one per game, each one our projection "
                                f"clears comfortably. ${info['stake']} rides with ${info['banked']} banked. A win returns ${info['payout']}: "
                                f"bank ${info['bankThisWin']} and ride ${info['nextStake']} on the next step. Kept apart from the record, in dollars.")
            candidate['risk'] = ('Every leg has to hit; one miss ends the climb, but it cannot take money already banked. '
                                 + ('College score models are uncertain and their raw alternate-spread chances are not calibrated price edges. '
                                    if game_lines else 'Our player chances are tuned for main lines, so these legs are not value. ')
                                 + "This is the fun of the climb; the book's official settlement controls, and a person settles the rung.")
            return candidate
        if candidate.get('parlayType') == 'easyProps':
            candidate['why'] = (f"Easy props, for fun: {len(candidate['legs'])} legs at {candidate['book']}, one per game, each an easier line "
                                f"our projection clears comfortably. A quarter unit, tracked with the longshots, apart from the straight picks.")
            candidate['risk'] = ('Every leg has to hit; one miss sinks the ticket. Our player chances are tuned for main lines, so these legs '
                                 'are not value, just fun. A player who does not take the field voids his leg; a verified book protection '
                                 'may also remove an injury leg, and the book\'s official settlement controls.')
        else:
            alternate = any(leg.get('alternate') for leg in candidate['legs'])
            source = 'the board and feed-priced alternates' if alternate else 'the board'
            candidate['why'] = (f"Longshot from {source}: {len(candidate['legs'])} legs at {candidate['book']}, each at the number our "
                                f"model graded, one per game. A fun ticket at a quarter unit, tracked apart from the straight picks.")
            candidate['risk'] = 'Most longshots lose. The legs are treated as independent; any one miss sinks the ticket.'
        return candidate
    p = gates.desk_for(candidate, ctx) or {}
    snapshot = ctx.snapshot(candidate['gameIds'][0])
    side, line, odds = gates.side_of(candidate), float(candidate['line']), int(candidate['odds'])
    sparse = 'A team with under three games this season thins the read. ' if snapshot and snapshot.get('sparse') else ''
    if candidate.get('favorite'):
        claims = ' '.join(f['claim'].rstrip('.') + '.' for f in candidate.get('_support') or [])
        chance = f"{100 * p['chance']:.1f}%" if p.get('calibrated') else f"{100 * p['rawChance']:.1f}% on the raw curve"
        comparison = (f"Price-checked win chance {p['chance']:.1%}; {odds:+d} needs {p['breakEven']:.1%}. "
                      if gates.market_key(candidate) == 'moneyline' else
                      f"Our number is {p['projection']:g} against {pricing.fmt(line)}, {chance} for the "
                      f"{side}, {p['edgePoints']:+.1f} points clear of the {100 * p['breakEven']:.1f}% that {odds:+d} needs. ")
        candidate['why'] = (f"Researched pick. {claims} " + comparison +
                            f"The sourced reason and the number point the same way.")
        candidate['risk'] = (f"A report can change before kickoff, and a listed player can dress. {sparse}The number still rests on a model the "
                             f"closing line beats on average.")
        sources = list(candidate.get('sources') or [])
        for fact in candidate.get('_support') or []:
            if fact.get('source') and fact['source'] not in sources:
                sources.append(fact['source'])
        candidate['sources'] = sources
        return candidate
    if candidate.get('athleteId'):
        chance_text = (f"{p['chance']:.1%} after adjustment from the raw {p['rawChance']:.1%}" if p.get('calibrated')
                       else f"{p['rawChance']:.1%} on an uncalibrated curve; not eligible as an official play")
        candidate['why'] = (f"Prop lean: our projection is {p['projection']:g} against {pricing.fmt(line)}. The "
                            f"{side} reads {chance_text}; {pricing.break_even(odds):.1%} is needed at {odds:+d}. "
                            f"{prop_reasoning(candidate, ctx, records, snapshot)}")
        games_played = ctx.appearances.get(candidate['athleteId'], 0)
        candidate['risk'] = (f"An estimated chance, not a guarantee; a player line turns on a handful of touches. {games_played} games this season"
                             f"{'' if games_played >= 3 else ', the role settled by last season'}. A player who does not take the field is "
                             f"voided; an in-game injury is graded unless a verified book protection applies.")
        cautions = (candidate.get('reasoning') or {}).get('cautions') or []
        if cautions:
            candidate['risk'] = ' '.join(cautions) + ' ' + candidate['risk']
        for fact in candidate.get('_research') or []:
            if fact.get('verified') and str(fact.get('source') or '').startswith('https://'):
                candidate['sources'] = list(dict.fromkeys([*(candidate.get('sources') or []), fact['source']]))
    else:
        market_words = next((f['claim'] for f in candidate.get('_evidence') or [] if f.get('kind') == 'market'), '')
        checked = checked_facts(candidate)
        opposing_stats = [f for f in verified_opposition(candidate) if f.get('kind') == 'stats' and f.get('claim')]
        caution = (' Verified statistical reporting also points against this side; see the counterpoints below.') if opposing_stats else ''
        number_label = 'home margin' if gates.market_key(candidate) == 'spread' else 'total'
        comparison = (f"Price-checked win chance {p['chance']:.1%}; {odds:+d} needs {p['breakEven']:.1%}."
                      if gates.market_key(candidate) == 'moneyline' else
                      f"Model lean, our number only. We have the {number_label} at {p['projection']:g}; the book is at {pricing.fmt(line)}. "
                      f"That makes the {side} {100 * p['chance']:.1f}%, and {odds:+d} needs {100 * p['breakEven']:.1f}%.")
        candidate['why'] = (comparison
                            + caution
                            + ''.join(f" Checked before publishing: {first_sentence(f['claim'])}" for f in checked)
                            + (f" The market: {market_words}" if market_words else ''))
        sources = list(candidate.get('sources') or [])
        for fact in checked + opposing_stats[:2]:
            if str(fact.get('source') or '').startswith('https://') and fact['source'] not in sources:
                sources.append(fact['source'])
        candidate['sources'] = sources
        candidate['risk'] = (f"It's our number against the market's, and the closing line usually beats ours, so a gap this big often "
                             f"means we're missing something. {sparse}")
        supplied = candidate.get('_evidence') or []
        candidate['reasoning'] = {'context': [first_sentence(f['claim']) for f in supplied
                                              if f.get('verified') and f.get('direction') == 'for' and f.get('claim')],
                                  'cautions': [first_sentence(f['claim']) for f in supplied
                                               if f.get('verified') and f.get('direction') == 'against' and f.get('claim')],
                                  'directionsChecked': True}
        if opposing_stats:
            counterpoints = ' '.join(f"Statistical counterpoint: {first_sentence(f['claim'])}" for f in opposing_stats[:2])
            additional = f' {len(opposing_stats) - 2} more verified statistical counterpoints.' if len(opposing_stats) > 2 else ''
            candidate['risk'] = (counterpoints + additional + ' Historical stats remain context, not a separate injury or availability hold. '
                                 + candidate['risk'])
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
    day = now.astimezone(EASTERN)
    lines = [f"Research update for {day:%b} {day.day}:"]
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
        # Published no earlier than the newest price in it: a run that captures prices after it starts and publishes
        # from that capture has a quote a second or two past its own start (Sep 26 8:30 run, quote <= published).
        quoted = [gates.when(p['quotedAt']) for _, _, p in published if p.get('quotedAt')]
        report = {'league': league, 'publishedAt': stamp(max([now] + quoted))}
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
    # Full software suites run on deployment/CI, not before every ticket send.
    # Runtime still validates every exact report, price, stake, news and caption.
    try:
        py = subprocess.run([python, 'scripts/release_checks.py'], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        raise RunError('release checks exceeded 120 seconds; retry on the next delivery pass') from error
    if py.returncode:
        raise RunError('unit tests failed:\n' + py.stderr[-1500:])
    try:
        node = subprocess.run(['node', '--test', *sorted(str(p) for p in (ROOT / 'tests').glob('*.test.js'))], cwd=ROOT, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as error:
        raise RunError('release frontend checks exceeded 60 seconds; retry on the next delivery pass') from error
    if node.returncode:
        raise RunError('node tests failed:\n' + (node.stderr or node.stdout)[-1500:])


PRIMETIME_COVERAGE_LANES = gates.OFFICIAL_STRAIGHT_LANES


def official_coverage_game_ids(ctx):
    """Games genuinely served by a public official lane.

    Fun tickets and Climb rungs can mention a primetime game, but neither is
    the straight-play coverage promised for that game.
    """
    covered = set()
    for key, first in ctx.first.items():
        if not gates.occupies_game(first, ctx.latest.get(key), getattr(ctx, 'now', None)):
            continue
        pick = dict(first, **ctx.latest.get(key, {}))
        covered.update(pick.get('gameIds') or [])
    return covered


def official_selection_scope(slot, games, ctx, now, select_now=False):
    """Game ids eligible for this run's official selection.

    ``None`` means the ordinary 6:45 game-day board.  The 7:30 run gives early
    international games a second fresh-price look before their 8:30 post target.
    The 8:30 and 11:45 runs get the post-capture board for every noon-or-later game that has not
    started; the 5:30/6:50 runs get the primetime NFL/CFB board after fresh prop
    capture.  A game that already has one straight stays eligible because the
    owner allows multiple non-contradictory plays from one game.  Duplicate,
    contradiction and daily-card gates still bound every release.
    """
    if select_now:
        return {game['id'] for game in games.values()
                if game.get('league') in ('NFL', 'CFB') and game.get('state') == 'pre'
                and eastern_date(gates.when(game['kickoff'])) == eastern_date(now)
                and gates.when(game['kickoff']) > now}
    if slot.hour == 6 and slot.minute == 45:
        return None
    today = eastern_date(now)
    if (slot.hour, slot.minute) == (7, 30):
        if os.environ.get('KEENROUDY_SELECTION_0730', '1').strip().lower() in ('0', 'false', 'off', 'no'):
            return set()
        return {game['id'] for game in games.values()
                if game.get('league') in ('NFL', 'CFB') and game.get('state') == 'pre'
                and eastern_date(gates.when(game['kickoff'])) == today
                and gates.when(game['kickoff']).astimezone(EASTERN).hour < 12}
    if (slot.hour, slot.minute) in ((8, 30), (11, 45)):
        if os.environ.get('KEENROUDY_SELECTION_0830', '1').strip().lower() in ('0', 'false', 'off', 'no'):
            return set()
        return {game['id'] for game in games.values()
                if game.get('league') in ('NFL', 'CFB') and game.get('state') == 'pre'
                and eastern_date(gates.when(game['kickoff'])) == today
                and gates.when(game['kickoff']).astimezone(EASTERN).hour >= 12}
    if os.environ.get('KEENROUDY_SELECTION_PRIMETIME', '1').strip().lower() in ('0', 'false', 'off', 'no'):
        return set()
    if (slot.hour, slot.minute) not in ((17, 30), (18, 50)):
        return set()
    return {game['id'] for game in games.values()
            if game.get('league') in ('NFL', 'CFB') and game.get('state') == 'pre'
            and eastern_date(gates.when(game['kickoff'])) == today
            and gates.when(game['kickoff']) > now
            and gates.when(game['kickoff']).astimezone(EASTERN).hour >= 19}


def allowed(path):
    return any(path == w.rstrip('/') or path.startswith(w) for w in WHITELIST)


def easy_parlay_step(ctx, games, now, records, published, decided, screened, spend=True, exclude=(), league='NFL'):
    """The day's easy player-prop parlay from stored SharpAPI alternates, with no Odds API spend."""
    import easy_parlay
    try:
        ticket, reason = easy_parlay.sharp_candidate(ctx, games, now, league=league, exclude=exclude)
    except Exception as error:
        log(f'{league} easy parlay skipped ({type(error).__name__}: {error})')
        return
    if not ticket:
        log(f'{league} easy parlay: {reason}')
        return
    ticket['id'] = gates.fresh_id(ticket['id'], ctx) if gates.pulled_before_post(ticket['id'], ctx) else ticket['id']
    write_prose(ticket, ctx, records)
    ok, decisions = gates.admit(dict(ticket, league=league), ctx)
    if ok:
        if any(d.rule == 'cfb_jurisdiction' and (d.data or {}).get('jurisdictionVerified') for d in decisions):
            ticket['jurisdictionVerified'] = True     # a college ticket at a book available in Indiana
        ticket['dossier'] = dossier.ticket(ticket, now)
        ctx.first[ticket['id']] = dict(ticket, league=league, publishedAt=stamp(now), kind='parlays')
        published.append((league, 'parlays', ticket))
        decided.append(decision_record(ticket, league, 'published', [], None, now, ctx))
        log(f"{league} easy parlay: {ticket['title']} {ticket['odds']:+d}: " + ' / '.join(l['title'] for l in ticket['legs']))
        return
    refusal = gates.refusals(decisions)[0]
    decided.append(decision_record(ticket, league, 'refused', [d.rule for d in gates.refusals(decisions)], refusal.reason, now, ctx))
    screened.append({'league': league, 'gameId': ticket['gameIds'][0], 'title': ticket['title'], 'rule': refusal.rule, 'reason': refusal.reason})


def ladder_step(ctx, games, now, records, published, decided, screened, manual=None, status=None):
    """The ladder's next rung (scripts/ladder.py), through its leg-level gates. Never fails a run.

    A refusal on one straight candidate cannot erase that candidate's entire
    game from the Climb pool. The Climb checks its own player, price, injury
    and research rules on each proposed leg.
    """
    import ladder
    try:
        import climb_prep
        prep = climb_prep.prepare(ctx, now)
        boxscores.write_json(Path(getattr(ctx, 'root', ROOT)) / 'work' / 'climb-prep.json', prep)
    except Exception as error:
        log(f'next-day Climb prep failed ({type(error).__name__}); current-day selection continues')
    try:
        ticket, reason = (ladder.manual_candidate(ctx, games, now, manual) if manual
                          else ladder.candidate(ctx, games, now))
    except Exception as error:
        log(f'ladder skipped ({type(error).__name__}: {error})')
        try:
            ladder.record_shadow(ctx, now, blocked=f'{type(error).__name__}: {error}')
        except OSError:
            pass
        return
    if not ticket:
        log(f'ladder: {reason}')
        try:
            ladder.record_shadow(ctx, now, blocked=reason)
        except OSError:
            pass
        return
    league = ticket['_league']
    # Price and projection agreement make an alternate eligible, but they are
    # not research by themselves. Save a factual reason on every rung leg so
    # the route and the pre-post review can explain exactly why it is there.
    missing = []
    research_status = (status or {}).get('research') if isinstance(status, dict) else None
    for leg in ticket.get('legs') or []:
        case = dict(leg, gameIds=[leg.get('gameId')], _league=league,
                    _team=(getattr(ctx, 'player_team', {}) or {}).get(str(leg.get('athleteId') or '')),
                    _player=leg.get('player'))
        try:
            case['_evidence'] = evidence(case, ctx, getattr(ctx, 'context_file', {}) or {})
            saved = plan_reasons(case, ctx)
        except (KeyError, TypeError, ValueError, AttributeError):
            saved = []
        # Main-moneyline rungs are deliberately not justified by the model gap alone.  When the normal stored
        # evidence has no supporting fact, spend one of the day's existing research lookups on that exact leg.
        # The researcher returns sourced facts only; verification and plan_reasons still decide whether any count.
        has_reason = any(row.get('direction') == 'for' and row.get('text') for row in saved)
        can_research = researcher.enabled() and research_status is not None \
            and research_status.get('asked', 0) < RESEARCH_LIMIT
        if not has_reason and can_research:
            game = games.get(leg.get('gameId'))
            if game:
                try:
                    kept, dropped = researcher.research(
                        game, gates.market_key(case), gates.side_of(case), now=now,
                        player=case.get('_player'), quarterbacks=quarterbacks(game, ctx))
                except (OSError, TypeError, ValueError, AttributeError):
                    kept, dropped = [], []
                case['_research'] = [dict(f, verified=True) for f in kept] + [dict(f, verified=False) for f in dropped]
                research_status['asked'] = research_status.get('asked', 0) + 1
                research_status['verified'] = research_status.get('verified', 0) + len(kept)
                research_status['dropped'] = research_status.get('dropped', 0) + len(dropped)
                saved = plan_reasons(case, ctx)
                log(f"researched Climb leg {leg.get('title')}: {len(kept)} verified facts, {len(dropped)} dropped")
        leg['reasons'] = saved
        leg['reason'] = next((row.get('text') for row in saved if row.get('direction') == 'for'
                              and row.get('text')), None)
        if not leg['reason']:
            missing.append(leg.get('title') or leg.get('id') or 'leg')
    if missing:
        reason = 'no saved research reason for ' + ', '.join(missing)
        log(f'ladder: {reason}')
        try:
            ladder.record_shadow(ctx, now, ticket=ticket, blocked=reason)
        except OSError:
            pass
        screened.append({'league': league, 'gameId': ticket['gameIds'][0], 'title': ticket['title'],
                         'rule': 'ladder_research', 'reason': reason})
        decided.append(decision_record(ticket, league, 'refused', ['ladder_research'], reason, now, ctx))
        return
    write_prose(ticket, ctx, records)
    ok, decisions = gates.admit(dict(ticket, league=league), ctx)
    if ok:
        if any(d.rule == 'cfb_jurisdiction' and (d.data or {}).get('jurisdictionVerified') for d in decisions):
            ticket['jurisdictionVerified'] = True     # a college rung at a book available in Indiana
        ticket['dossier'] = dossier.ticket(ticket, now)
        ctx.first[ticket['id']] = dict(ticket, league=league, publishedAt=stamp(now), kind='parlays')
        published.append((league, 'parlays', ticket))
        decided.append(decision_record(ticket, league, 'published', [], None, now, ctx))
        info = ticket['ladder']
        log(f"ladder: step {info['step']} {ticket['odds']:+d} at {ticket['book']}, ${info['stake']} to ${info['payout']}; "
            f"bank ${info['bankThisWin']}, ride ${info['nextStake']}: "
            + ' / '.join(l['title'] for l in ticket['legs']))
        try:
            ladder.record_shadow(ctx, now, ticket=ticket)
        except OSError:
            pass
        return
    refusal = gates.refusals(decisions)[0]
    try:
        ladder.record_shadow(ctx, now, ticket=ticket, blocked=f'{refusal.rule}: {refusal.reason}')
    except OSError:
        pass
    decided.append(decision_record(ticket, league, 'refused', [d.rule for d in gates.refusals(decisions)], refusal.reason, now, ctx))
    screened.append({'league': league, 'gameId': ticket['gameIds'][0], 'title': ticket['title'], 'rule': refusal.rule, 'reason': refusal.reason})


def pick_of_the_day(now, ctx, status, current=None, write=True):
    """Name today's Pick of the Day (scripts/featured.py) before the push, so its card is rendered by the deploy
    the push starts. Never fails a run."""
    try:
        import featured
        status['pickOfTheDay'] = featured.choose(ctx, now, write=write, log=log, current=current)
    except Exception as error:
        log(f'pick of the day not chosen ({type(error).__name__}: {error})')


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
        runner('commit', '--quiet', '-m', f"Capture odds {eastern_date(now).isoformat()}", cwd=cwd)
    if research:
        runner('add', '--', *research, cwd=cwd)
        message = f"Refresh research {eastern_date(now).isoformat()}"
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
    """The run's outcome for the heartbeat and `run.py status`. A rehearsal (--dry-run) writes beside its reports
    in pending/, so it can never paper over a real run that failed."""
    if (status.get('llm') or {}).get('used'):
        status['llm']['calls'] = llm.call_stats()
    path = path or (CONF / 'pending' / 'status.json' if status.get('dryRun') else CONF / 'status.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=1, default=str) + '\n', encoding='utf-8')


def mark_admitted_pending(ctx, admitted):
    """Keep a newly built admission private without assuming it was already in every store view.

    Ticket builders add their enriched row to ``first`` before release.  A brand-new
    Climb rung has no matching ``latest`` row yet, so seed that view from ``first``
    instead of letting the whole desk run crash while marking it pending.
    """
    for _, _, candidate in admitted:
        candidate['_pendingRelease'] = True
        key = candidate.get('id')
        if not key:
            continue
        first = ctx.first.setdefault(key, dict(candidate))
        first['_pendingRelease'] = True
        latest = ctx.latest.setdefault(key, dict(first))
        latest['_pendingRelease'] = True


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
        with Lock(CONF / 'run.lock', wait=0 if args.dry_run else RUN_LOCK_WAIT):
            return _run(args, now, slot, kinds, status)
    except RunError as error:
        log('STOPPED:', error)
        status.update(outcome=f'failed: {error}', finishedAt=stamp(datetime.now(timezone.utc)))
        status['errors'].append(str(error))
        write_status(status)
        # A scheduled slot lost after the full lock wait is actionable too.
        if not args.dry_run:
            alert(f"KeenRoudy {slot.strftime('%-I:%M %p')} run stopped", str(error)[:600])
        return 1
    except Exception:
        text = traceback.format_exc()
        log('CRASHED:\n' + text)
        status.update(outcome='crashed', finishedAt=stamp(datetime.now(timezone.utc)))
        status['errors'].append(text[-1500:])
        write_status(status)
        if not args.dry_run:
            alert(f"KeenRoudy {slot.strftime('%-I:%M %p')} run crashed", text.strip().splitlines()[-1][:600])
        return 2


def _run(args, now, slot, kinds, status):
    log(f"run for the {slot.strftime('%-I:%M %p')} ET slot at {et(now)}" + (' (dry run)' if args.dry_run else ''))
    # Results also keeps the stored-price Climb scan. That extra kind must not
    # turn a free settlement pass into a new pregame capture/admission window.
    settle_only = args.command == 'results' or kinds == {'settle'}
    if not args.dry_run:
        sync()
        status['checks'].append('synced')
        captures = ['settlement scan: no odds or prop requests'] if settle_only else capture(slot)
    else:
        captures = ['dry run: no capture']
    for note in captures:
        log(note)
    now = current_run_time(args, now)
    if not settle_only:
        early_nba_selection(args, now, slot, status)
    try:
        opportunities = arbs.scan(ROOT, now)
    except Exception as error:  # an optional private alert can never stop grading or publishing
        opportunities = []
        log(f'arb radar unavailable ({type(error).__name__}); the desk continues')
    import discord_post
    status['arbs'] = {'found': len(opportunities), 'alerted': 0, 'destination': 'Discord'}
    for hit in opportunities[:3]:
        log(f"arb radar: {hit['label']} {hit['roi']:.2f}%")
        if args.dry_run:
            continue
        try:
            if discord_post.send_arb_alert(arbs.message(hit), arbs.alert_id(hit), now,
                                           CONF / 'arb-discord-alerts.json'):
                status['arbs']['alerted'] += 1
        except discord_post.DiscordError as error:  # an optional alert can never stop the desk
            log(f'arb radar Discord alert not sent: {error}')
    slate = load_json(ROOT / 'site' / 'data' / 'slate.json', {'games': []})
    if not args.dry_run and not settle_only:
        try:
            shadow = sgo_shadow.sample(slate, now)
            status['sgoShadow'] = shadow
            if shadow['sampled']:
                log(f"SportsGameOdds shadow: {shadow['events']} events, {shadow['candidates']} candidates; "
                    f"usage was {shadow['usage']}/{shadow['limit']}; team-total calibration "
                    f"captured {shadow.get('teamTotalsCaptured', 0)}, graded "
                    f"{shadow.get('teamTotalsGradedNow', 0)}, "
                    f"lifetime {shadow.get('teamTotals', {}).get('record', '0-0')} "
                    f"({shadow.get('teamTotals', {}).get('units', 0):+.2f}u)")
            elif 'not configured' not in shadow['reason']:
                log('SportsGameOdds shadow skipped:', shadow['reason'])
        except Exception as error:  # an optional evaluation feed can never stop the desk
            status['sgoShadow'] = {'sampled': False, 'error': type(error).__name__}
            log(f'SportsGameOdds shadow unavailable ({type(error).__name__}); the desk continues')
    slate_games = {g['id']: g for g in slate.get('games', []) if g.get('league') in ('NFL', 'CFB')}
    games = live_games(now, slate_games)
    records = features.load()
    settlement_records = records
    if settle_only:
        # The per-game summary often reports Final before ESPN's day scoreboard.
        # Reuse the five-minute watcher's verified summary so grading is prompt.
        import live_watch
        watched = live_watch.final_records()
        live_watch.overlay_finals(games, watched)
        settlement_records = live_watch.settlement_records(records, watched)
    now = current_run_time(args, now)
    status['selectionAsOf'] = stamp(now)
    stores = gates.Stores(records=records)
    ctx = stores.as_of(now)
    ctx.games = games
    prime_weather(records)
    raw_first = raw_first_publications(stores.reports)
    context_file = stores.context_file
    settled, closed, published, screened, unclear = [], [], [], [], []
    llm.reset_calls()
    use_llm = not args.no_llm and llm.available()
    polish_on = use_llm and llm.polish_enabled()
    status['llm'] = {'used': use_llm, 'model': llm.model_name() if use_llm else None,
                     'judgeModel': llm.model_name() if use_llm else None,
                     'writingModel': llm.fast_model_name() if polish_on else None,
                     'polishEnabled': polish_on,
                     'polished': 0, 'kept': 0, 'judged': 0}
    log('local models:', (f"judgment {llm.model_name()} at {llm.base_url()}; "
                          + (f"writing {llm.fast_model_name()}" if polish_on else 'verified templates kept')
                          if use_llm else 'off' if args.no_llm else 'not reachable; templates and rules only'))

    if 'settle' in kinds:
        settled, unclear = settle(ctx, raw_first, games, settlement_records, now)
        for u in unclear:
            u['league'] = ctx.first[u['id']].get('league')
        log(f'settled {len(settled)}, unclear {len(unclear)}')
        reviews = [u for u in unclear if u.get('settlementReview')]
        if reviews and not args.dry_run:
            alert("Kook'n settlement review in progress",
                  '\n'.join(f"{u['id']}: {u['why']}" for u in reviews)[:1800], priority='default')
    if 'close' in kinds:
        closed, checks = close_moves(ctx, raw_first, games, desk.captures(), now)
        closed += parlay_closures(ctx, raw_first, games, now, closing=[revision for _, _, revision in closed])
        status['checks'] += [f'CHECK {k}: no comparable current line' for k in checks]
        log(f'closed {len(closed)}, to check by hand {len(checks)}')
    absorb(ctx, settled + closed)

    # Admissions which have not reached Discord remain private, but still
    # occupy duplicate/card-cap space on later selection passes.  An expired
    # private price is reopened first so this pass can evaluate the fresh quote.
    import release_queue
    release_queue.reopen_expired(CONF, now, log=log)
    release_queue.merge_context(ctx, CONF)

    build_site.build(now)
    lines = load_candidate_lines(build_site.OUT / 'lines.json')
    selection_scope = official_selection_scope(slot, games, ctx, now, getattr(args, 'select_now', False))
    selection_run = selection_scope is None or bool(selection_scope)
    wanted = rank_card(candidates(lines, games, now), ctx) if selection_run else []
    if selection_scope is not None:
        wanted = [candidate for candidate in wanted if candidate['gameIds'][0] in selection_scope]
    if not selection_run:
        log('owner plan: this slot is settlement/research only; selection runs at the game-day and primetime checks')
    elif selection_scope is not None:
        label = 'early-game' if (slot.hour, slot.minute) == (7, 30) else \
            'later game-day' if (slot.hour, slot.minute) in ((8, 30), (11, 45)) else 'primetime'
        log(f"{label} recheck after fresh prices: {len(selection_scope)} game(s)")
    log(f'{len(wanted)} candidates on the board')
    decided = []          # every decision this run made, for the learning record
    reasons = {}          # the reason each published play's post will give (data/x-reasons.json)
    # The web researcher reads the news for every play that passes the rules, on the runs that publish.
    research_on = researcher.enabled() and selection_run
    status['research'] = {'on': research_on, 'asked': 0, 'verified': 0, 'dropped': 0, 'families': {}}
    potd_market = []      # fresh priced board markets; only matching official singles can receive the POTD label
    best_pool = []        # fully checked rows; ranked by the logged Kitchen score before publication
    gut_pool = []         # fully checked fallbacks; chosen only after every Best bet has been considered
    safer_pool = []       # fully honest moneyline legs; combined only when a day has no Best bet
    deferred_research = []
    for candidate_rank, candidate, reclaim_research in research_passes(wanted, deferred_research):
        want = 'prop' if candidate.get('athleteId') else 'lean'
        if want not in kinds:
            continue
        if price(candidate, ctx, now) is None:
            continue
        if candidate['_league'] != 'NFL' or gates.market_key(candidate) != 'total':
            potd_market.append(dict(candidate))
        if candidate['id'] in ctx.first:
            continue            # already on the record: only a settlement or a close revises a published pick
        candidate['_team'] = ctx.player_team.get(candidate.get('athleteId', ''))
        candidate['_primetimeFallback'] = bool(
            selection_scope is not None and (slot.hour, slot.minute) in ((17, 30), (18, 50))
            and candidate.get('_league') == 'NFL' and candidate['gameIds'][0] in selection_scope)
        facts = evidence(candidate, ctx, context_file)
        candidate['_evidence'] = facts
        league = candidate['_league']
        write_prose(candidate, ctx, records)
        # The written rules first: a candidate they refuse costs no web research and no model time.
        ok, decisions = gates.admit(dict(candidate, league=league), ctx)
        for decision in decisions:
            if decision.rule == 'one_book' and decision.data.get('quoteNoteRequired'):
                candidate['quoteNote'] += f" {candidate['book']} is the only book with this market; its paired game-day price passed the check."
            if decision.rule == 'cfb_jurisdiction' and decision.data.get('jurisdictionVerified'):
                candidate['jurisdictionVerified'] = True
        if not ok:
            first = gates.refusals(decisions)[0]
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'lineId': (candidate.get('_row') or {}).get('id'), 'line': candidate.get('line'), 'book': candidate.get('book'),
                             'rule': first.rule, 'reason': first.reason})
            decided.append(decision_record(candidate, league, 'refused', [d.rule for d in gates.refusals(decisions)], first.reason, now, ctx))
            continue
        # Then the news: the web researcher reads injury, availability and depth-chart reporting for the play.
        researched = False          # true only when the web check came back with who is expected to play
        pre_reasons = plan_reasons(candidate, ctx)
        gap = (candidate.get('_selection') or {}).get('gap', 0)
        class_a = any(row.get('class') == 'A' and row.get('direction') == 'for' for row in pre_reasons)
        needs_market_check = should_research_candidate(candidate, candidate_rank, gap, class_a)
        research_block = (research_slot_refusal(candidate, status['research'], reclaim=reclaim_research) if research_on
                          else 'the news researcher is unavailable in this run')
        if (needs_market_check and not reclaim_research and research_block
                and 'research allocation is used' in research_block):
            deferred_research.append((candidate_rank, candidate))
            continue
        if research_on and needs_market_check and research_block is None:
            game = ctx.games[candidate['gameIds'][0]]
            kept, dropped = researcher.research(game, gates.market_key(candidate), gates.side_of(candidate), now=now,
                                                player=candidate.get('_player') or ctx.names.get(str(candidate.get('athleteId') or '')),
                                                quarterbacks=quarterbacks(game, ctx))
            candidate['_research'] = [dict(f, verified=True) for f in kept] + [dict(f, verified=False) for f in dropped]
            status['research']['asked'] += 1
            note_research_slot(candidate, status['research'])
            if reclaim_research:
                status['research']['reallocated'] = status['research'].get('reallocated', 0) + 1
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
            hold = research_block or 'the news check returned no verified player-availability evidence; college plays stay held'
        hold = hold or judge(candidate, relevant_facts(candidate, facts, ctx), use_llm, status)
        if hold:
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'lineId': (candidate.get('_row') or {}).get('id'), 'line': candidate.get('line'), 'book': candidate.get('book'),
                             'rule': 'held', 'reason': hold})
            decided.append(decision_record(candidate, league, 'held', ['held'], hold, now, ctx))
            continue
        if research_on and 'favorite' in kinds and promote(candidate, facts, use_llm, status):
            log(f"favorite: {candidate['title']} ({candidate.get('_supportNote')})")
        if polish_on:
            polish(candidate, facts, status)
        # The case file is built from this run's already-checked facts and stored captures;
        # it spends no additional research or odds requests. A broken optional source
        # must not withhold an otherwise admitted play.
        headline_reason = post_reason(candidate, facts, ctx, records, learning_weights())
        game = ctx.games[candidate['gameIds'][0]]
        try:
            candidate['dossier'] = dossier.build(
                candidate, game, ctx, records, now,
                captures=[*(stores.odds.get(game['id']) or []), *(stores.prop_odds.get(game['id']) or [])],
                weather_row=_WEATHER.get('stored', {}).get(game['id']), headline_reason=headline_reason)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            log(f"dossier partial for {candidate['id']}: {type(error).__name__}")
            candidate['dossier'] = dossier.empty(candidate)
        candidate['_planReasons'] = plan_reasons(candidate, ctx)
        if candidate.get('marketType') == 'moneyline':
            safer_pool.append((league, candidate))
        if candidate.get('selectionPolicy') == gates.TIER_POLICY:
            best = choose_straight_tier(candidate, ctx)
            if best.ok:
                candidate['_selectionDecision'] = best.data
                candidate['_kitchenScore'] = gates.kitchen_score(candidate, ctx, best.data)
                best_pool.append((league, candidate))
            else:
                screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                                 'lineId': (candidate.get('_row') or {}).get('id'), 'line': candidate.get('line'), 'book': candidate.get('book'),
                                 'rule': best.rule, 'reason': best.reason})
                decided.append(decision_record(candidate, league, 'refused', [best.rule], best.reason, now, ctx))
            continue
        best = gates.selection_verdict(candidate, ctx, 'best_bet')
        if not best.ok:
            gut = gates.selection_verdict(candidate, ctx, 'gut_call')
            if gut.ok:
                candidate['_selectionDecision'] = gut.data
                gut_pool.append((league, candidate, best))
                continue
            refusal = gut if best.reason.startswith('NFL sides remain in shadow') else best
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'lineId': (candidate.get('_row') or {}).get('id'), 'line': candidate.get('line'), 'book': candidate.get('book'),
                             'rule': refusal.rule, 'reason': refusal.reason})
            decided.append(decision_record(candidate, league, 'refused', [refusal.rule], refusal.reason, now, ctx))
            continue
        candidate['_selectionDecision'] = best.data
        candidate['_kitchenScore'] = gates.kitchen_score(candidate, ctx, best.data)
        best_pool.append((league, candidate))
    # The card is ordered by the owner-plan score, not by calibrated chance.
    # Apply capacity again as rows join the in-run record.
    hot_days = {gates.slate_day(pick, ctx) for pick in ctx.first.values()
                if pick.get('lane') == 'hot_plate' or pick.get('favorite') is True}
    for league, candidate in sorted(best_pool, key=lambda item: (-item[1]['_kitchenScore']['total'], item[1]['id'])):
        duplicate = gates.not_duplicate(candidate, ctx)
        cap = gates.card_cap(candidate, ctx)
        if not duplicate.ok or not cap.ok:
            refusal = duplicate if not duplicate.ok else cap
            screened.append({'league': league, 'gameId': candidate['gameIds'][0], 'title': candidate['title'],
                             'lineId': (candidate.get('_row') or {}).get('id'), 'line': candidate.get('line'), 'book': candidate.get('book'),
                             'rule': refusal.rule, 'reason': refusal.reason})
            decided.append(decision_record(candidate, league, 'refused', [refusal.rule], refusal.reason, now, ctx))
            continue
        day = gates.slate_day(candidate, ctx)
        if candidate.get('selectionPolicy') == gates.TIER_POLICY:
            candidate['favorite'] = candidate['lane'] == 'chef_pick'
        else:
            candidate['lane'] = 'hot_plate' if day not in hot_days else 'best_bet'
            candidate['favorite'] = candidate['lane'] == 'hot_plate'
            candidate['riskUnits'] = 1
            gates.staking.apply(candidate, now)
        hot_days.add(day)
        kind = 'props' if candidate.get('athleteId') else 'gamePicks'
        ctx.first[candidate['id']] = dict(candidate, league=league, publishedAt=stamp(now), kind=kind)
        ctx.latest[candidate['id']] = dict(candidate)
        published.append((league, kind, candidate))
        decided.append(decision_record(candidate, league, 'published', [], None, now, ctx))
        log(f"kitchen score {candidate['id']}: {candidate['_kitchenScore']}")
        reason = next((row.get('text') for row in candidate['dossier']['reasons'] if row.get('text')), None)
        if reason:
            reasons[candidate['id']] = reason
    # A large weekend slate gets up to the owner's five-play floor from fully
    # checked positive-value fallbacks after every Best bet is considered.
    # Every primetime NFL game also gets its own eligible fallback.
    days_with_play = {gates.slate_day(pick, ctx) for _, _, pick in published if not pick.get('legs')}
    straight_counts = defaultdict(int)
    for key, first in ctx.first.items():
        pick = dict(first, **(ctx.latest.get(key) or {}))
        if pick.get('lane') not in gates.OFFICIAL_STRAIGHT_LANES or pick.get('held') \
                or pick.get('withdrawn') or pick.get('pulledBeforePost') or pick.get('status') != 'active':
            continue
        straight_counts[gates.slate_day(pick, ctx)] += 1
    existing_games = official_coverage_game_ids(ctx)
    today = eastern_date(now)
    prime_games = {game['id'] for game in games.values() if selection_run and game.get('league') == 'NFL'
                   and game.get('state') == 'pre' and eastern_date(gates.when(game['kickoff'])) == today
                   and gates.when(game['kickoff']).astimezone(gates.EASTERN).hour >= 19}
    selected_guts = []
    for league, candidate, best_refusal in sorted(gut_pool, key=lambda item: (
            -gates.kitchen_score(item[1], ctx, item[1]['_selectionDecision'])['total'], item[1]['id'])):
        game_id = candidate['gameIds'][0]
        day = gates.slate_day(candidate, ctx)
        need_prime = game_id in prime_games and game_id not in existing_games \
            and all(game_id not in pick['gameIds'] for _, pick, _ in selected_guts)
        selected_on_day = sum(gates.slate_day(pick, ctx) == day for _, pick, _ in selected_guts)
        need_day = straight_counts[day] + selected_on_day < straight_target(day, games)
        if need_prime or need_day:
            duplicate = gates.not_duplicate(candidate, ctx)
            cap = gates.card_cap(candidate, ctx)
            if not duplicate.ok or not cap.ok:
                continue
            candidate['lane'] = 'gut_call'
            candidate['riskUnits'] = .5
            candidate['_kitchenScore'] = gates.kitchen_score(candidate, ctx, candidate['_selectionDecision'])
            selected_guts.append((league, candidate, best_refusal))
    selected_gut_ids = {candidate['id'] for _, candidate, _ in selected_guts}
    for league, candidate, best_refusal in gut_pool:
        if candidate['id'] not in selected_gut_ids:
            decided.append(decision_record(candidate, league, 'refused', [best_refusal.rule],
                                           f'{best_refusal.reason}; Gut call qualified but ranked outside the card',
                                           now, ctx))
    for league, candidate, best_refusal in selected_guts:
        kind = 'props' if candidate.get('athleteId') else 'gamePicks'
        ctx.first[candidate['id']] = dict(candidate, league=league, publishedAt=stamp(now), kind=kind)
        ctx.latest[candidate['id']] = dict(candidate)
        published.append((league, kind, candidate))
        decided.append(decision_record(candidate, league, 'published', [best_refusal.rule],
                                       f'Gut call after Best bet refusal: {best_refusal.reason}', now, ctx))
        reason = next((row.get('text') for row in candidate['dossier']['reasons'] if row.get('text')), None)
        if reason:
            reasons[candidate['id']] = reason
    # If a football day still has no straight play, try the approved two-favorite
    # Safer combo. It is its own lane and never enters the Best bets headline.
    import comfort
    open_days = sorted({gates.slate_day(candidate, ctx) for _, candidate in safer_pool if gates.slate_day(candidate, ctx)})
    for day in open_days:
        if day in days_with_play or any(gates.slate_day(pick, ctx) == day for _, pick, _ in selected_guts):
            continue
        ticket = comfort.build([candidate for _, candidate in safer_pool if gates.slate_day(candidate, ctx) == day])
        if not ticket:
            continue
        first_game = games[ticket['gameIds'][0]]
        ticket.update({'id': f"{first_game['league']}-{first_game.get('season', day.year)}-safer-{day:%m%d}-dk",
                       'title': f"Safer combo · {len(ticket['legs'])} favorites", 'status': 'active',
                       'favorite': False, 'lane': 'safer_combo', 'parlayType': 'comfort',
                       'riskUnits': 1, 'quoteType': 'capture', 'publishedAt': stamp(now),
                       'expiresAt': stamp(min(gates.when(games[g]['kickoff']) for g in ticket['gameIds'])),
                       'sources': sorted({games[g]['source'] for g in ticket['gameIds'] if games[g].get('source')})})
        risk = gates.daily_exposure(ticket, ctx)
        if not risk.ok:
            log(f"Safer combo: {risk.reason}")
            continue
        ctx.first[ticket['id']] = dict(ticket, kind='parlays', league=first_game['league'])
        ctx.latest[ticket['id']] = dict(ticket)
        published.append((first_game['league'], 'parlays', ticket))
        decided.append(decision_record(ticket, first_game['league'], 'published', [], None, now, ctx))
        days_with_play.add(day)
    covered = existing_games | {game_id for _, _, pick in published for game_id in pick.get('gameIds') or []}
    for game_id in sorted(prime_games - covered):
        message = f'primetime dark: no priced market passed gates ({game_id})'
        log(message)
        if not args.dry_run:
            alert("Kook'n primetime play missing", message, priority='high')
    if 'longshot' in kinds:
        exclude = longshot_exclusions(ctx, screened, [revision for _, _, revision in closed])
        for league in ('NFL', 'CFB'):
            ticket, reason = longshot_candidate(lines, games, now, league, exclude, ctx)
            if not ticket:
                log(f'{league} longshot: {reason}')
                continue
            if gates.pulled_before_post(ticket['id'], ctx):
                if not ticket_replacement_allowed(ticket['id'], ctx):
                    log(f"{league} longshot: owner closed today's ticket with no replacement")
                    continue
                if not replacement_has_last_look(ticket, games, now):
                    log(f"{league} longshot: replacement has no last-look X window; not publishing")
                    screened.append({'league': league, 'gameId': (ticket.get('gameIds') or [None])[0],
                                     'title': ticket['title'], 'rule': 'replacement_window',
                                     'reason': 'a replacement needs one last look and must post before kickoff minus 45 minutes'})
                    continue
                ticket['replacementOf'] = ticket['id']
                ticket['id'] = gates.fresh_id(ticket['id'], ctx)       # the day's first was pulled before its post
            missing = attach_ticket_reasons(ticket, ctx, status.get('research'))
            if missing:
                reason = 'no saved leg reason for ' + ', '.join(missing)
                log(f'{league} longshot: {reason}')
                screened.append({'league': league, 'gameId': ticket['gameIds'][0], 'title': ticket['title'],
                                 'rule': 'ticket_research', 'reason': reason})
                decided.append(decision_record(ticket, league, 'refused', ['ticket_research'], reason, now, ctx))
                continue
            write_prose(ticket, ctx, records)
            ok, decisions = gates.admit(dict(ticket, league=league), ctx)
            if ok:
                if any(d.rule == 'cfb_jurisdiction' and (d.data or {}).get('jurisdictionVerified') for d in decisions):
                    ticket['jurisdictionVerified'] = True     # a college ticket at a book available in Indiana
                ticket['dossier'] = dossier.ticket(ticket, now)
                ctx.first[ticket['id']] = dict(ticket, league=league, publishedAt=stamp(now), kind='parlays')
                published.append((league, 'parlays', ticket))
                decided.append(decision_record(ticket, league, 'published', [], None, now, ctx))
                break
            decided.append(decision_record(ticket, league, 'refused', [d.rule for d in gates.refusals(decisions)],
                                           gates.refusals(decisions)[0].reason, now, ctx))
            screened.append({'league': league, 'gameId': ticket['gameIds'][0], 'title': ticket['title'],
                             'rule': gates.refusals(decisions)[0].rule, 'reason': gates.refusals(decisions)[0].reason})
        easy_parlay_step(ctx, games, now, records, published, decided, screened, spend=not args.dry_run, exclude=exclude)
        if eastern_date(now).weekday() == 5:          # a college Saturday gets its alternate-line parlay too
            easy_parlay_step(ctx, games, now, records, published, decided, screened, exclude=exclude, league='CFB')
    if 'ladder' in kinds:
        exclude = longshot_exclusions(ctx, screened, [revision for _, _, revision in closed])
        manual_ladder = load_json(Path(args.ladder_spec), None) if args.ladder_spec else None
        ladder_step(ctx, games, now, records, published, decided, screened, manual=manual_ladder,
                    status=status)

    # A selection is only an admission here.  It becomes a public report when
    # the Discord-first delivery job releases it; until then it lives solely
    # under ~/.config/keenroudy/pending/.
    admitted = list(published)
    mark_admitted_pending(ctx, admitted)
    published = []

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
    status.update(settled=len(settled), closed=len(closed), published=len(published), admitted=len(admitted),
                  screened=screened, unclear=unclear,
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
    drafts(slot, now, ctx, games, settled, status, admitted=admitted, reasons=reasons)
    if not args.dry_run:
        admitted_ids = release_queue.enqueue(CONF, admitted, reasons, decided, CONF / 'x-drafts', now,
                                             games=games, log=log)
        if admitted_ids:
            log('private admissions:', ', '.join(admitted_ids))
        release_before_background(args, status)
        try:
            shadow = reasoned_edges.step(decided, ctx, now)
            status['reasonedEdges'] = shadow
            log(f"reasoned edges: {shadow['captured']} triggers, {shadow['graded']} grades; private shadow only")
        except Exception as error:
            status['errors'].append(f'reasoned edges: {type(error).__name__}: {error}')
            log(f'reasoned edges unavailable ({type(error).__name__}); the desk continues')
        try:
            projection_shadow = projection_shadows.step(decided, ctx, now)
            status['projectionShadows'] = projection_shadow
            log(f"projection shadows: {projection_shadow['captured']} captured, "
                f"{projection_shadow['graded']} graded; private comparison only")
        except Exception as error:
            status['errors'].append(f'projection shadows: {type(error).__name__}: {error}')
            log(f'projection shadows unavailable ({type(error).__name__}); the desk continues')
        admission_keys = {candidate.get('id') for _, _, candidate in admitted}
        public_decisions = [row for row in decided if row.get('id') not in admission_keys]
        remember(public_decisions, now, slot, status)
        paper_trials(now, slot, status)
        if (not settle_only and os.environ.get('KEENROUDY_SPORTS_CAPTURE','1')!='0' and nba_game_capture_due(slot)
                and 'nbaCapture' not in status and args.command != 'run'):
            try:
                import nba_capture
                status['nbaCapture'] = nba_capture.step(now, scheduled=True)
                log(f"NBA capture: {status['nbaCapture']}")
                record_nba_roster_capture(args,status)
            except Exception as error:
                status['errors'].append(f'nba capture: {type(error).__name__}: {error}')
                log(f'NBA capture: {type(error).__name__}: {error}')
        if not settle_only and os.environ.get('KEENROUDY_SPORTS_CAPTURE','1')!='0' and nba_game_capture_due(slot):
            try:
                import nba_player_props
                status['nbaPlayerProps']=nba_player_props.capture(now if args.dry_run else datetime.now(timezone.utc))
                log(f"NBA player props: {status['nbaPlayerProps']}")
            except Exception as error:
                status['errors'].append(f'NBA player props: {type(error).__name__}: {error}')
        try:
            import nba_editorial
            # Feed receipts are newer than this run's start. Use the real
            # post-capture instant, or their future-time guard would suppress
            # every freshly captured morning post. Rehearsals retain their clock.
            status['nbaEditorialPrepared'] = nba_editorial.prepare(now if args.dry_run else datetime.now(timezone.utc))
        except Exception as error:
            status['errors'].append(f'NBA editorial: {type(error).__name__}: {error}')
            log(f'NBA editorial unavailable: {type(error).__name__}: {error}')
        try:
            import nba_trial_runtime
            status['nbaTrialGraded'] = nba_trial_runtime.grade(now)
            import nba_player_props
            status['nbaPlayerPropGraded'] = nba_player_props.grade(now)
            if not args.dry_run and not getattr(args,'no_push',True):
                import nba_roster_runtime
                try:
                    status['nbaRosterGraded']=nba_roster_runtime.grade(now,root=ROOT/'data/nba-roster-research',boxes=[r for p in (ROOT/'data/sport-box').glob('nba-*.jsonl') for r in __import__('boxscores').read_store(p)])
                except Exception as error:
                    status['errors'].append(f'NBA roster research grade: {type(error).__name__}: {error}')
            if args.command == 'run' and 'nbaTrial' not in status and not settle_only:
                status['nbaTrial'] = nba_trial_runtime.admission(now, capture=nba_trial_needs_capture(slot, status))
        except Exception as error:
            status['errors'].append(f'NBA Trial: {type(error).__name__}: {error}')
        if slot.hour in (21,23):
            try:
                import next_day_prep
                import nba_player_props
                prep_now=datetime.now(timezone.utc)
                slate_path=ROOT/'data'/'nba-capture'/'slate.json'
                nba_slate=json.loads(slate_path.read_text()) if slate_path.exists() else {}
                prep=next_day_prep.prepare(games,lines,nba_slate,nba_player_props.build(prep_now,limit=None),prep_now)
                next_day_prep.attach_team_context(prep, prep_now, ROOT/'data'/'nba-capture')
                boxscores.write_json(ROOT/'work'/'next-day-prep.json',prep)
                status['nextDayPrepared']={'targetDate':prep['targetDate'],'footballGames':prep['football']['games'],
                                          'nbaGames':prep['nba']['games'],'nbaPropRows':prep['nba']['freshPropRows']}
                log(f"next-day prep: {status['nextDayPrepared']}")
            except Exception as error:
                status['errors'].append(f'next-day prep: {type(error).__name__}: {error}')
                log(f'next-day prep unavailable ({type(error).__name__}); delivery continues')
        try:
            import morning_brief
            public_today=any(not dict(p,**ctx.latest.get(k,{})).get('result') and not p.get('parlayType')
                and any(g in games and eastern_date(gates.when(games[g]['kickoff']))==eastern_date(now)
                        for g in p.get('gameIds',[])) for k,p in ctx.first.items())
            status['morningBriefPrepared']=morning_brief.prepare(
                now if args.dry_run else datetime.now(timezone.utc),screened,
                official=bool(morning_brief.has_official_straight(admitted) or public_today))
        except Exception as error:
            status['errors'].append(f'morning brief: {type(error).__name__}: {error}')
        # The lane is fixed at admission, but the public feature store cannot
        # reveal an unreleased play.
        pick_of_the_day(now, ctx, status, current=potd_market, write=not bool(admitted))
        git_result = commit_push(now, slot, {'published': len(published), 'settled': len(settled), 'closed': len(closed)},
                                 push=not args.no_push)
        status['git'] = git_result
        log('git:', git_result)
        # Posts are scheduled after the push: the push deploys the cards of anything just published, and a
        # post never goes out without its card.
        buffer_posts(now if args.dry_run else datetime.now(timezone.utc), ctx, games, closed, status,
                     deploying=bool(git_result.get('pushed')))
        owner_agenda(now, ctx, games)
        # Optional local editorial work comes AFTER official scheduling, never in its critical path.
        homepage_editor(now, status, enabled=use_llm)
        status['git']['posts'] = commit_log(now, push=not args.no_push)
    status.update(outcome='ok', finishedAt=stamp(datetime.now(timezone.utc)))
    write_status(status)
    log(f"done: {len(settled)} settled, {len(closed)} closed, {len(published)} published, {len(screened)} screened")
    for s in screened:
        log(f"  screened {s['title']}: {s['rule']}: {s['reason']}")
    return 0


# ------------------------------------------------------------------ X drafts (review gate: files, never posts)

def drafts(slot, now, ctx, games, settled, status, admitted=(), reasons=None):
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
    # Newly admitted rows are deliberately not in the public reports yet. They
    # still need private copy and art before enqueue; otherwise a good selection
    # can reach the queue with no card and stop the whole desk run.
    draft_first, draft_latest = dict(ctx.first), dict(ctx.latest)
    for _, _, candidate in admitted:
        key = candidate.get('id')
        if key and key not in draft_first:
            draft_first[key] = candidate
            draft_latest[key] = candidate
    for key, pick in draft_first.items():
        merged = dict(pick, **draft_latest.get(key, {}))
        postable = draft_postable(merged)
        if not postable or merged.get('result') or key in posted:
            continue
        try:
            text, pick_now, game = x_post.do_draft(
                key, now, draft_first, draft_latest, games, out=folder,
                reason=(reasons or {}).get(key))
            written.append(key)
        except x_post.Refused:
            continue
        try:                                                  # the queue retries this if the first render fails
            render_private_play_card(key, pick_now, game, games, ctx, now, folder / f'{key}.png')
        except Exception as error:
            log(f'card for {key} not rendered: {error}')
    status['x']['drafted'] = len(written)
    if written:
        log('x drafts written:', ', '.join(written), f'(in {folder})')


def draft_postable(pick):
    """Return whether an admitted item needs release copy and card art.

    Gut calls and safer combos receive their lane after ranking, so they need
    not carry the older favorite/modelLean discovery flags. Every official
    lane must still be rendered before it enters the private release queue.
    """
    return bool(pick.get('favorite') is True or pick.get('modelLean') or pick.get('legs')
                or pick.get('lane') in PRIMETIME_COVERAGE_LANES)


# ------------------------------------------------------------------ posting through Buffer

def buffer_posts(now, ctx, games, closed, status, deploying=False, sleep=time.sleep, clock=time.monotonic):
    """Schedule today's plays through Buffer (scripts/buffer_post.py), record what became of past posts and
    cancel any whose pick closed. Off without a token. Missing hosted cards retry
    on the next existing pass; never hold the shared posting lock waiting for a
    deployment. The scheduler still refuses every unavailable required card."""
    import buffer_post
    import discord_post
    import x_post
    if not os.environ.get('BUFFER_TOKEN', '').strip():
        log('buffer: no BUFFER_TOKEN; posts stay as drafts')
        return
    log_book = x_post.load_log()
    try:
        for entry in buffer_post.reconcile(log_book, now, log=log):
            status['errors'].append(f"buffer: {entry['id']} failed to post: {entry['error']}")
            alert('KeenRoudy post did not go out', f"{entry['id']}: {entry['error']}")
        queued_results = discord_post.queue_results(log_book, ctx.first, ctx.latest, games, now)
        if queued_results:
            log(f'discord: queued {queued_results} official result update(s)')
        for entry in discord_post.mirror_sent(log_book, now, log=log):
            status['errors'].append(f"discord: {entry['id']} failed to mirror: {entry['error']}")
            alert("Kook'n Discord post did not go out", f"{entry['id']}: {entry['error']}")
        closed_ids = {revision['id'] for _, _, revision in closed}
        if closed_ids:
            buffer_post.cancel_closed(closed_ids, log_book, now, log=log)
        quotes = now_quotes(ctx, games, now)
        refused = []
        import news_posts
        # Posting tests and recovery tools can call this helper without a built
        # site. The primary candidate path above remains strict; optional news
        # enrichment keeps its historical empty-catalog fallback.
        lines = line_payload.load(build_site.OUT / 'lines.json', strict=False, log=log)
        news = news_posts.candidates(ctx, features.load(), lines, now, log_book, games=games)
        plans = buffer_post.plan(ctx.first, ctx.latest, games, now, log_book, ctx.player_team, quotes=quotes,
                                 refused=refused, news=news, log=log)
        for key, problems in refused:
            if 'has no X window' in problems:
                log(f'buffer: {key} has no X window')
            else:
                log(f"buffer: {key} held back, its text fails the post check: {'; '.join(problems)}")
                alert('KeenRoudy post held back', f"{key}: {'; '.join(problems)}")
        import nba_trial_runtime
        plans += nba_trial_runtime.social_plans(now, log_book, reserved=plans)
        upgrades = pending_ladder_result_cards(log_book, ctx, now)
        if deploying and (plans or upgrades):
            cards = [card for *_, card in plans if card] + list(upgrades.values())
            waiting = [card for card in cards if not buffer_post.reachable(buffer_post.card_url(card))]
            if waiting:
                status['x']['cardsAwaitingDeploy'] = len(waiting)
                log(f'buffer: {len(waiting)} card(s) await deployment; next existing pass retries without blocking delivery')
            later = datetime.now(timezone.utc)
            plans = buffer_post.plan(ctx.first, ctx.latest, games, max(now, later), log_book, ctx.player_team,
                                     quotes=quotes, news=news, log=log)
            plans += nba_trial_runtime.social_plans(max(now, later), log_book, reserved=plans)
        # A Buffer discovery/limit outage must not prevent already-authorized
        # Discord delivery above. Empty plans need neither metered lookup.
        channel = buffer_post.x_channel(wanted='keenkooks') if plans or upgrades else None
        limit = buffer_post.daily_limit(channel['id'], eastern_date(now).isoformat()) if plans else None
        if limit and limit.get('remaining') is not None and limit['remaining'] < len(plans):
            log(f"buffer: the channel can take {limit['remaining']} more posts today; scheduling that many")
            plans = buffer_post.fit_limit(plans, limit['remaining'])
        before = len(log_book.get('posts', []))
        schedule_stats = {}
        theme_items = {key: dict(value, **ctx.latest.get(key, {})) for key, value in ctx.first.items()}
        for item in theme_items.values():
            starts = [games[gid]['kickoff'] for gid in item.get('gameIds') or [] if gid in games]
            if starts:
                item['kickoff'] = min(starts)
        if plans:
            buffer_post.schedule(plans, channel['id'], log_book, now, log=log, stats=schedule_stats, items=theme_items)
        status['x']['posted'] = len(log_book.get('posts', [])) - before
        status['x']['officialUnscheduled'] = schedule_stats.get('officialNotScheduled', 0) + len({key for key, problems in refused if 'has no X window' in problems})
        missing = buffer_post.chosen_not_posted(ctx.first, ctx.latest, games, log_book, now)
        status['x']['chosenNotPosted'] = len(missing)
        status['x']['chosenNotPostedIds'] = missing
        scheduled = {entry['id'] for entry in log_book.get('posts', [])[before:]}
        for title, message in ladder_schedule_pings([p for p in plans if p[0] in scheduled], ctx, games):
            alert(title, message, click='https://keenroudy.com/sports/#ladder')
        for title, message in lotto_pings([p for p in plans if p[0] in scheduled], ctx):
            alert(title, message, click=f'https://x.com/{receipts_handle()}', delay='5m')
        feature_scheduled(log_book, ctx, games, now)
        upgrade_ladder_result_cards(log_book, ctx, now, channel=channel)
        # Publishing and result repairs get the allowance before optional stats.
        buffer_post.collect_metrics(log_book, now, log=log)
    except (buffer_post.BufferError, buffer_post.MissingToken) as error:
        log(f'buffer: {error}')
        status['errors'].append(f'buffer: {error}')
    x_post.save_log(log_book)


def mirror_due(log_book, now):
    """Is there an X result or Discord-first delivery the lightweight job should handle?"""
    import nba_editorial
    import buffer_post
    for entry in log_book.get('posts', []):
        if buffer_post.style_audit_due(entry, now):
            return True
        if nba_editorial.veto_pending(entry,now):
            return True
        if entry.get('cancelledAt') or entry.get('deletedAt'):
            followup = (entry.get('discord') or {}).get('followup') or {}
            if followup.get('state') == 'pending':
                return True
            continue
        mirror = entry.get('discord') or {}
        if (mirror.get('result') or {}).get('state') == 'pending':
            return True
        if mirror.get('state') == 'pending' and mirror.get('readyAt') and gates.when(mirror['readyAt']) <= now:
            return True
        if entry.get('sentAt') and mirror.get('state') == 'pending':
            return True
        if entry.get('bufferPostId') and not entry.get('sentAt') and not entry.get('error') and entry.get('dueAt') \
                and gates.when(entry['dueAt']) <= now:
            return True
    return False


def private_release_ready(now):
    """A private admission is close enough to its morning X slot to release."""
    import release_queue
    for row in release_queue.load(CONF).get('plays', []):
        if row.get('held'):
            continue
        pick = row.get('pick') or {}
        starts = [gates.when(value) for value in row.get('kickoffs') or []]
        # New queue rows normally use the live game table below.  Persisted
        # kickoffs make this cheap check work without loading public stores.
        if starts:
            target = post_windows.target(row.get('league'), min(starts))
            if now >= target - post_windows.DISCORD_PLAY_LEAD:
                return True
        elif row.get('discordSentAt') or row.get('publicPath'):
            return True
    return False


RESULT_RECOVERY_GAP = timedelta(minutes=15)


def result_recovery_needed(now, root=ROOT, conf=CONF):
    """Retry a settled win/near miss whose Cooked/Burnt post was never queued.

    The ordinary result job remains the primary path.  This is the five-minute
    mirror's bounded recovery path: a future scheduled post is healthy, an
    overdue or absent one is retried at most once per fifteen minutes.
    """
    import desk_health
    import x_post
    log_book = x_post.load_log()
    record = load_json(Path(root) / 'site/data/app/record.json', {})
    # The health report retains historical delivery misses. Recovery must only
    # wake for results that receipts.cashed can still publish, otherwise one
    # expired result rebuilds the whole desk every fifteen minutes forever.
    import receipts
    if isinstance(record, dict) and isinstance(record.get('picks'), list):
        record = dict(record, picks=[p for p in record['picks']
            if isinstance(p, dict) and desk_health.moment(p.get('settledAt')) and
            now - (receipts.LADDER_CASHED_FRESH if p.get('ladder') or p.get('kind') == 'ladder'
                   else receipts.CASHED_FRESH) < desk_health.moment(p['settledAt']) <= now])
    result = desk_health.result_timeliness(
        record,
        log_book.get('posts', []) if isinstance(log_book, dict) else [], now)
    if result.get('state') != 'available' or not result.get('missing'):
        return 0
    state = load_json(Path(conf) / 'result-recovery.json', {})
    last = state.get('attemptedAt')
    if last:
        try:
            if now - gates.when(last) < RESULT_RECOVERY_GAP:
                return 0
        except (TypeError, ValueError):
            pass
    return int(result['missing'])


def mark_result_recovery(now, count, conf=CONF):
    path = Path(conf) / 'result-recovery.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'attemptedAt': stamp(now), 'missing': int(count)}, indent=1) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def _private_card(path):
    data = Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('private release card is not a PNG')
    return data, 'image/png', 'kookn-card.png'


def render_private_play_card(key, pick, game, games, ctx, now, target):
    """Render one immutable pre-release card from the selected row's saved facts."""
    if not pick_card.chrome_path():
        raise ReleaseArtifactError('Chrome is unavailable for the release card')
    team = ctx.player_team.get(str(pick.get('athleteId') or ''))
    side = 'home' if team == str(game['home']['id']) else 'away' if team == str(game['away']['id']) else None
    import featured
    art = pick_card.artwork(pick, game)
    is_featured = pick.get('lane') == 'hot_plate' or featured.of_day(eastern_date(now).isoformat()) == key
    if pick_card.ticket_enabled(pick, moment=now):
        import ticket_card
        kind = pick_card.play_kind(pick)
        if kind == 'ladder':
            svg = ticket_card.climb_svg(pick, games, ctx.player_team)
        elif kind == 'parlay':
            svg = ticket_card.fun_svg(pick, games, ctx.player_team)
        else:
            svg = ticket_card.straight_svg(pick, game, player_side=side,
                                           featured=is_featured, art=art)
    else:
        svg = pick_card.modern_svg(pick, game, player_side=side, featured=is_featured, art=art)
    pick_card.render(svg, target)


def recover_private_release_artifacts(row, ctx, games, now):
    """Rebuild a queued play's missing private caption/card before any public send."""
    import release_queue
    import x_post
    import social_style

    key = row.get('id')
    pick = dict(row.get('pick') or {})
    game = games.get((pick.get('gameIds') or [None])[0])
    if not key or not game:
        raise ReleaseArtifactError('the selected game is unavailable for artifact recovery')
    changes = {}
    try:
        caption = str(row.get('caption') or '').strip()
        unpublished = not row.get('discordSentAt') and not row.get('publicPath')
        if not caption or (unpublished and social_style.active(now) and social_style.issues(caption)):
            first = dict(ctx.first)
            latest = dict(ctx.latest)
            first[key] = dict(pick)
            latest[key] = dict(pick)
            folder = CONF / 'x-drafts'
            folder.mkdir(parents=True, exist_ok=True)
            caption, _, _ = x_post.do_draft(key, now, first, latest, games, out=folder,
                                            reason=row.get('reason'))
            changes['caption'] = caption
        card = Path(row.get('card') or (release_queue.cards(CONF) / f'{key}.png'))
        valid_card = card.is_file() and card.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
        if unpublished and social_style.active(now):
            valid_card = valid_card and social_style.current_png(card)
        if not valid_card:
            card.parent.mkdir(parents=True, exist_ok=True)
            render_private_play_card(key, pick, game, games, ctx, now, card)
            changes['card'] = str(card)
    except ReleaseArtifactError:
        raise
    except Exception as error:
        raise ReleaseArtifactError(f'{type(error).__name__}: {error}') from error
    if changes or row.get('artifactState'):
        changes.update(artifactState='ready', artifactMissing=[], artifactError=None,
                       artifactRecoveredAt=stamp(now))
        row = release_queue.update(CONF, key, **changes)
        log(f'release: {key} private caption/card ready')
    return row


def normalize_private_stake(row, ctx, now):
    """Version only never-public admissions and force fresh, unposted art."""
    if row.get('discordSentAt') or row.get('publicPath') or not gates.staking.active(now):
        return row
    import release_queue
    pick = dict(row.get('pick') or {})
    revised = gates.staking.apply(dict(pick), now)
    if revised == pick:
        return row
    key = row['id']
    row = release_queue.update(CONF, key, pick=revised, caption=None,
        card=str(release_queue.cards(CONF) / f'{key}-staking-v1.png'), precheckedAt=None)
    ctx.first[key] = dict(revised, _pendingRelease=True)
    ctx.latest[key] = dict(ctx.first[key])
    return row


def private_release_refusal(row, ctx, now):
    """Return the release-time reason a private admission must be withdrawn.

    Admission is not permission to publish an expired price later.  Policy is
    checked again here as well, so an older queued row cannot bypass a newly
    effective market rule.
    """
    pick = dict(row.get('pick') or {}, league=row.get('league'))
    try:
        quoted = gates.when(pick.get('quotedAt'))
        expires = gates.when(pick.get('expiresAt'))
    except (TypeError, ValueError):
        return 'its saved quote has no valid release window'
    if not quoted <= now < expires:
        return f"its saved quote expired at {expires.astimezone(EASTERN):%-I:%M %p} ET"
    if gates.staking.active(now) and not row.get('discordSentAt') and not row.get('publicPath'):
        risk = gates.daily_exposure(pick, ctx)
        if not risk.ok:
            return risk.reason
        if not pick.get('legs') and not pick.get('parlayType'):
            fresh = gates.fresh_quote(pick, ctx)
            if not fresh.ok:
                return fresh.reason
            if not any(pair.get('book') == pick.get('book') and pair.get('side') == pick.get('odds')
                       for pair in gates.exact_price_pairs(pick, ctx)):
                return 'its exact book/line/price no longer matches the latest capture; fresh selection required'
    policy = gates.totals_policy(pick, ctx)
    if not policy.ok:
        return policy.reason
    if pick.get('legs') and pick.get('parlayType') in (None, 'longshot'):
        policy = gates.longshot_shape(pick, ctx)
        if not policy.ok:
            return policy.reason
    if pick.get('parlayType') == 'ladder':
        for rule in (gates.ladder_selective, gates.ladder_supported):
            policy = rule(pick, ctx)
            if not policy.ok:
                return policy.reason
    if pick.get('selectionPolicy') == gates.TIER_POLICY:
        expected = gates.staking.expected(pick) if pick.get('lane') in ('best_bet', 'chef_pick') else None
        if expected is None or pick.get('riskUnits') != expected:
            return 'its selected tier and stake do not match'
        probe = dict(pick, _planReasons=(row.get('decision') or {}).get('planReasons') or [])
        probe.pop('_selection', None)
        probe.pop('_desk', None)
        verdict = gates.selection_verdict(probe, ctx, pick['lane'])
        if not verdict.ok:
            return f'its current tier price check failed: {verdict.reason}'
    return None


def release_private(now, log=log, only=None, review_only=False):
    """Release due admissions Discord → public record → Buffer/X.

    Each state transition is persisted outside Git first.  A retry therefore
    resumes after the last confirmed external action instead of duplicating it.
    """
    import buffer_post
    import discord_post
    import featured
    import learning
    import release_queue
    import x_post

    book = release_queue.load(CONF)
    if not book.get('plays'):
        return []
    stores = gates.Stores(records=features.load())
    ctx = stores.as_of(now)
    slate = load_json(ROOT / 'site' / 'data' / 'slate.json', {'games': []})
    release_queue.merge_context(ctx, CONF)
    ctx.games = live_games(now, {g['id']: g for g in slate.get('games', []) if g.get('league') in ('NFL', 'CFB')})
    log_book = x_post.load_log()
    # X discovery is transport work, never a prerequisite for Discord/site.
    channel = None
    channel_error = None
    released = []
    busy = buffer_post.taken(log_book, now)
    for row in list(book['plays']):
        key = row.get('id')
        if only is not None and key not in only:
            continue
        web_attempt = next((e for e in log_book.get('posts', [])
                            if e.get('id') == key and e.get('webDelivery')), None)
        if web_attempt and not review_only:
            if web_attempt.get('sentAt'):
                release_queue.remove(CONF, key)
                released.append(key)
            else:
                log(f'buffer: {key} has an unresolved attended attempt; no API retry')
            continue
        pick = dict(row.get('pick') or {})
        game = ctx.games.get((pick.get('gameIds') or [None])[0])
        starts = sorted(gates.when(ctx.games[g]['kickoff']) for g in pick.get('gameIds') or [] if g in ctx.games)
        if not key or not starts or row.get('held'):
            continue
        if (not review_only and row.get('discordSentAt') and row.get('publicPath')
                and not row.get('bufferPostId')):
            # The public release is complete. An unchanged X transport hold
            # must not rerun news/tests/builds under the posting lock every5min.
            # All ordinary checks run again once an actual X send is possible.
            blocked = buffer_post.rate_backoff(now) or buffer_post.quota.buffer_block_reason(now=now, essential=True)
            if blocked:
                log(f'buffer: {key} already released on Discord/site; X transport held: {blocked}')
                continue
        row = normalize_private_stake(row, ctx, now)
        pick = dict(row.get('pick') or {})
        refusal = private_release_refusal(row, ctx, now)
        if refusal:
            release_queue.remove(CONF, key)
            if not row.get('discordSentAt') and not row.get('publicPath'):
                ctx.first.pop(key, None)
                ctx.latest.pop(key, None)
            log(f'release: {key} withdrawn before public release: {refusal}')
            alert("Kook'n play withdrawn before release", f'{key}: {refusal}')
            continue
        kickoff = starts[0]
        target = post_windows.target(row.get('league'), kickoff) + post_windows.jitter(key)
        due = max(target, now + post_windows.DISCORD_PLAY_LEAD)
        if not review_only and now >= target-post_windows.DISCORD_PLAY_LEAD and not row.get('bufferPostId'):
            try:
                if channel_error:
                    raise buffer_post.BufferError(channel_error)
                channel = channel or buffer_post.x_channel(wanted='keenkooks')
                moved=buffer_post.yield_optional(log_book,due,now,channel['id'])
                if moved:log(f'release: routine posts moved behind fresh play: {moved}')
            except (buffer_post.BufferError, buffer_post.MissingToken) as error:
                channel_error = str(error)
                log(f'release: optional queue move failed; keeping official release active: {error}')
            finally:
                # Persist even a restored replacement identity after an API refusal.
                x_post.save_log(log_book)
            busy=buffer_post.taken(log_book,now)
        # Find the first open slot from this play's own target.  A later
        # research/community post must not push an earlier official release
        # behind it; free_slot already preserves spacing around every post.
        due = buffer_post.free_slot(due, busy)
        if due > post_windows.deadline(row.get('league'), kickoff, now, bool(pick.get('replacementOf'))):
            release_queue.update(CONF, key, held=True, heldAt=stamp(now),
                                 holdReason='no Discord-first X slot before kickoff')
            log(f'release: {key} moved to the near-miss log: no Discord-first X slot before kickoff')
            continue
        if not post_windows.public_release_open(now, target):
            continue

        row = recover_private_release_artifacts(row, ctx, ctx.games, now)
        pick = dict(row.get('pick') or {})

        # Deterministic hard-news precheck.  A model concern never withdraws
        # an admitted play, but typed out/doubtful/inactive news still does.
        if not row.get('precheckedAt') or now - gates.when(row['precheckedAt']) > timedelta(minutes=15):
            context_file = live_context(stores.context_file, now)
            check_status = {'llm': {'judged': 0},
                            'research': {'asked': 0, 'verified': 0, 'dropped': 0}}
            if pick.get('legs') or pick.get('parlayType'):
                reason = parlay_last_look(dict(pick, _league=row.get('league')), ctx, context_file,
                                          False, check_status, now)
            else:
                case = dict(pick, _league=row.get('league'),
                            _team=ctx.player_team.get(str(pick.get('athleteId') or '')))
                _, _, facts = last_look(case, game, ctx, context_file, False,
                                        check_status, now)
                reason = release_pull_reason(case, relevant_facts(case, facts, ctx))
            if reason:
                release_queue.update(CONF, key, held=True, heldAt=stamp(now), holdReason=reason)
                log(f'release: {key} held by hard news: {reason}')
                continue
            release_queue.update(CONF, key, precheckedAt=stamp(now))

        from social_copy import x_ticket_copy, AGE_VERSION
        text = x_ticket_copy(str(row.get('caption') or '').strip(), 'play', key, pick)
        if x_post.guard(text, pick, x_post.reason_in(text)):
            release_queue.update(CONF, key, held=True, heldAt=stamp(now), holdReason='caption guard')
            log(f'release: {key} held: caption guard failed')
            continue

        published_at = row.get('discordSentAt') or stamp(now)
        public_pick = dict(pick, publishedAt=published_at)
        report = {'league': row['league'], 'publishedAt': published_at, 'summary':
                  f"Released 1: {public_pick.get('title')} {int(public_pick.get('odds')):+d} at {public_pick.get('book')}.",
                  'takeaways': [], row['kind']: [public_pick]}
        # Prove the exact public row before the first external send.  A bad row
        # stays private and the isolated wrapper moves on to every other row.
        validate({'private-release.json': report}, stores.reports, ctx.games)
        import social_style
        if social_style.active(now):
            style_problems = social_style.release_issues(text, Path(row['card']))
            if style_problems:
                raise ReleaseArtifactError('; '.join(style_problems))
        run_tests()

        if review_only:
            if not row.get('discordSentAt') or not row.get('publicPath'):
                raise RunError('Attended web review requires an already-public Discord release')
            released.append(dict(id=key, text=text, card=row['card'], dueAt=stamp(due),
                                 pick=pick, reviewedAt=stamp(now)))
            continue

        if not row.get('discordSentAt'):
            receipt = discord_post.send_message(
                discord_post.webhook(), text, f'private:{key}',
                fetch=lambda _url, p=row['card']: _private_card(p), return_receipt=True)
            row = release_queue.update(CONF, key, discordSentAt=published_at, discordReceipt=receipt or {})
            log(f'discord: {key} released before X')

        # Public delivery is real even when Buffer cannot accept a post. Save
        # that receipt before the public report, without inventing an X schedule.
        entry = next((e for e in log_book.get('posts', []) if e.get('id') == key), None)
        if entry is None:
            sent_at = row['discordSentAt']
            entry = {'id': key, 'postedAt': sent_at,
                     'textHash': x_post.text_hash(text), 'kind': 'buffer:play', 'card': True,
                     'cardTheme': 'ticket', 'reasonKind': x_post.reason_kind(x_post.reason_in(text)),
                     'copyVariant': x_post.copy_variant(text),
                     'discord': {'state': 'sent', 'sentAt': sent_at, 'beforeX': True, 'text': text,
                                 'image': buffer_post.card_url(key)}}
            entry.update(cardKey=key)
            if social_style.active(now):
                entry.update(queuedText=text, socialStyleVersion=social_style.VERSION, socialAgeVersion=AGE_VERSION)
            log_book.setdefault('posts', []).append(entry)
            x_post.save_log(log_book)

        if not row.get('publicPath'):
            safe = re.sub(r'[^A-Za-z0-9-]+', '-', key).strip('-')[:72]
            name = f"{eastern_date(now).isoformat()}-{row['league']}-{now.astimezone(EASTERN):%H%M}-release-{safe}.json"
            target_path = ROOT / 'research' / name
            if target_path.exists():
                existing = json.loads(target_path.read_text(encoding='utf-8'))
                existing_ids = {item.get('id') for values in existing.values() if isinstance(values, list)
                                for item in values if isinstance(item, dict)}
                if key not in existing_ids:
                    raise RunError(f'private release report name collision: {name}')
            else:
                target_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            # Bootstrap the first hosted build with the exact Discord attachment.
            # Once live, ordinary builds can restore the same bytes from the site.
            release_queue.archive_card(row['card'], ROOT, key)
            if row.get('reason'):
                reasons = x_post.load_reasons()
                reasons[key] = row['reason']
                x_post.save_reasons(reasons)
            decision = dict(row.get('decision') or {})
            if decision:
                decision.update(decision='published', decidedAt=published_at)
                season = decision.get('season') or now.year
                exists = any(old.get('id') == key and old.get('decision') == 'published'
                             and old.get('decidedAt') == published_at for old in learning.read('candidates', season))
                if not exists:
                    learning.append('candidates', season, [decision])
            if public_pick.get('lane') in ('hot_plate', 'chef_pick'):
                featured_rows = featured.load()
                featured_rows[eastern_date(now).isoformat()] = {'id': key, 'chosenAt': published_at,
                                                                 'score': (public_pick.get('kitchenScore') or {}).get('total')}
                featured.save(featured_rows)
            result = commit_push(now, now.astimezone(EASTERN), {'published': 1, 'settled': 0, 'closed': 0})
            log('release record:', result)
            row = release_queue.update(CONF, key, publicPath=str(target_path.relative_to(ROOT)),
                                       publicPushedAt=stamp(datetime.now(timezone.utc)))

        if not row.get('bufferPostId'):
            if channel_error:
                log(f'buffer: {key} released on Discord/site; X waits: {channel_error}')
                continue
            if channel is None:
                try:
                    channel = buffer_post.x_channel(wanted='keenkooks')
                except (buffer_post.BufferError, buffer_post.MissingToken) as error:
                    channel_error = str(error)
                    log(f'buffer: {key} released on Discord/site; X waits: {error}')
                    continue
            image = (row.get('discordReceipt') or {}).get('image')
            if not image:
                image = buffer_post.card_url(key)
                if not buffer_post.reachable(image):
                    log(f'buffer: {key} waits for its released site card')
                    continue
            post_id = buffer_post.create_post(text, channel['id'], due, image, essential=True)
            row = release_queue.update(CONF, key, bufferPostId=post_id, dueAt=stamp(due), bufferImage=image)

        entry.update(dueAt=row['dueAt'], bufferPostId=row['bufferPostId'], bufferImage=row.get('bufferImage'))
        x_post.save_log(log_book)
        commit_log(now, push=True)
        release_queue.remove(CONF, key)
        released.append(key)
        busy.append(due)
        log(f'buffer: {key} scheduled after Discord release for {due.astimezone(EASTERN):%-I:%M %p} ET')
    return released


def release_private_isolated(now, log=log, runner=None):
    """Release each queued play independently so one malformed row cannot stop Discord."""
    import release_queue
    import buffer_post
    runner = runner or release_private
    released = []
    keys = [row.get('id') for row in release_queue.load(CONF).get('plays', [])
            if row.get('id') and not row.get('held')]
    for key in keys:
        try:
            released.extend(runner(now, log=log, only={key}))
        except buffer_post.BufferRateLimited as error:
            release_queue.update(CONF, key, bufferRetryAt=stamp(error.retry_at),
                                 deliveryDelay=str(error))
            log(f'release: {key} waits for Buffer until {stamp(error.retry_at)}; not a validation failure')
            break
        except ReleaseArtifactError as error:
            message = str(error)
            try:
                row = next((item for item in release_queue.load(CONF).get('plays', [])
                            if item.get('id') == key), {})
                first = not row.get('artifactError')
                release_queue.update(CONF, key, artifactState='recovery-needed', artifactError=message,
                                     artifactTriedAt=stamp(now))
            except KeyError:
                first = False
            log(f'release: {key} waits for private artifact recovery: {message}')
            if first:
                alert("Kook'n release artifact needs recovery", f'{key}: {message[:500]}')
        except Exception as error:
            message = f'{type(error).__name__}: {error}'
            try:
                release_queue.update(CONF, key, held=True, heldAt=stamp(now),
                                     holdReason=f'release validation failed: {message[:300]}')
            except KeyError:
                pass
            log(f'release: {key} isolated after failure: {message}')
            alert("Kook'n private play held", f'{key}: {message[:500]}')
    return released


def result_transport_block(now):
    import quota
    import buffer_post
    return quota.buffer_block_reason(now=now, essential=True) or buffer_post.rate_backoff(now)


def mirror(args):
    """Every five minutes, observe public plays, send due Discord-first plays and mirror the rest from Buffer."""
    import buffer_post
    import chef_wins
    import discord_post
    import x_post
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    shadow_result = {}
    if os.environ.get('KEENROUDY_LIVE_SHADOW', '1').strip() != '0':
        try:
            import live_watch
            shadow_result = live_watch.run_shadow(now=now, persist=not args.dry_run, log=log)
            if not args.dry_run:
                import live_progress
                live_progress.run(now=now, log=log,
                                  notify=lambda text: alert("Kook'n live-update pilot", text))
        except Exception as error:
            # Shadow evidence can never interrupt official delivery.
            log(f'live shadow unavailable ({type(error).__name__})')
    pending_finals = shadow_result.get('pendingFinals') or []
    if pending_finals and not args.dry_run:
        # A verified final should not wait for a scheduled full desk run.  The
        # settlement-only path spends no odds credits and admits no new plays.
        import copy
        import live_watch
        live_watch.mark_official_attempt(now)
        settlement_args = copy.copy(args)
        settlement_args.command = 'run'
        settlement_args.slot = now.astimezone(EASTERN).strftime('%H%M')
        settlement_args.no_llm = True
        settlement_args.publish_kinds = 'settle'
        settlement_args.record_screens = False
        log('official settlement scan:', ', '.join(pending_finals))
        result = run(settlement_args)
        if result:
            return result
    missing_results = result_recovery_needed(now)
    result_transport_hold = result_transport_block(now) if missing_results else None
    if missing_results and result_transport_hold:
        log(f'result recovery: X held without a desk rebuild: {result_transport_hold}; Discord remains independent')
    if missing_results and not result_transport_hold and not args.dry_run:
        # The result is already in the append-only public record; this pass
        # rebuilds and recreates only the missing result delivery.  It spends
        # no odds credits and uses no model call.
        import copy
        mark_result_recovery(now, missing_results)
        settlement_args = copy.copy(args)
        settlement_args.command = 'run'
        settlement_args.slot = now.astimezone(EASTERN).strftime('%H%M')
        settlement_args.no_llm = True
        settlement_args.publish_kinds = 'settle'
        settlement_args.record_screens = False
        log(f'result recovery scan: {missing_results} settled result post(s) absent or overdue')
        result = run(settlement_args)
        if result:
            return result
    # Recovery can refresh inputs minutes after this worker started. Use the
    # current clock so those valid captures are not mistaken for future data.
    if not args.now:
        now = datetime.now(timezone.utc)
    chef_waiting = bool(chef_wins.pending())
    social_ready = bool(os.environ.get('BUFFER_TOKEN', '').strip() and
                        (discord_post.webhook() or discord_post.wins_webhook()))
    if not social_ready and not chef_waiting:
        return 0
    if not chef_waiting and not result_transport_hold and not mirror_due(x_post.load_log(), now) and not private_release_ready(now):
        return 0
    if args.dry_run:
        log('discord mirror: work is due; dry run sends nothing')
        return 0
    failed = []
    try:
        with Lock(CONF / 'run.lock'):
            if chef_waiting:
                chef_wins.run(now, url=discord_post.wins_webhook(),
                              notify=lambda title, body: alert(title, body), log=log)
            if not social_ready:
                return 1 if failed else 0
            if not args.dry_run:
                sync()
            if not args.now:
                now = datetime.now(timezone.utc)
            log_book = x_post.load_log()
            if result_transport_hold:
                # These grades are already public. Read stored evidence only;
                # do not re-capture, re-grade, rebuild or call Buffer to deliver
                # an independent official Discord result.
                ctx = gates.Stores().as_of(now)
                slate = load_json(ROOT / 'site/data/slate.json', {'games': []})
                games = {g['id']: g for g in slate.get('games', [])}
                discord_post.queue_results(log_book, ctx.first, ctx.latest, games, now)
                x_post.save_log(log_book)
            if private_release_ready(now):
                release_private_isolated(now)
                log_book = x_post.load_log()
            if not mirror_due(log_book, now):
                return 0
            for entry in ([] if result_transport_hold else buffer_post.reconcile(log_book, now, log=log)):
                failed.append(f"X: {entry['id']}: {entry['error']}")
                alert("Kook'n post did not go out", f"{entry['id']}: {entry['error']}")
            for entry in discord_post.mirror_sent(log_book, now, log=log):
                failed.append(f"Discord: {entry['id']}: {entry['error']}")
                alert("Kook'n Discord post did not go out", f"{entry['id']}: {entry['error']}")
            x_post.save_log(log_book)
            commit_log(now, push=not args.no_push)
    except RunError as error:
        if 'holds the lock' in str(error):
            log('discord mirror: a run is in progress; trying again in five minutes')
            return 0
        log('discord mirror STOPPED:', error)
        alert("Kook'n Discord mirror stopped", str(error)[:600])
        return 1
    return 1 if failed else 0


def receipts_handle():
    import receipts
    return receipts.HANDLE


def ladder_schedule_pings(plans, ctx, games):
    """Private phone notice for every newly scheduled rung: the exact ticket and both public release times."""
    out = []
    for key, kind, _, due, _ in plans:
        pick = dict(ctx.first.get(key) or {}, **ctx.latest.get(key, {}))
        if kind != 'play' or pick.get('parlayType') != 'ladder':
            continue
        info = pick.get('ladder') or {}
        starts = [gates.when(games[g]['kickoff']) for g in pick.get('gameIds') or [] if g in games]
        lines = '\n'.join(f"• {leg.get('title')}" for leg in pick.get('legs') or [])
        message = (f"{pick_card.dollars(info.get('stake'))} → {pick_card.dollars(info.get('payout'))} "
                   f"({int(pick.get('odds')):+d}, {pick.get('book')})\n{lines}\n"
                   f"Discord: about {et(due - timedelta(minutes=15))}\nX: {et(due)}"
                   + (f"\nFirst kickoff: {et(min(starts))}" if starts else '')
                   + "\nNo wager was placed automatically; use the listed line and price cutoff.")
        out.append((f"80/20 Climb {info.get('run', 1)} Step {info.get('step', 1)} scheduled", message))
    return out


def owner_agenda(now, ctx, games):
    """One private morning schedule on football days; exact rung details get a second alert when they qualify."""
    local = now.astimezone(EASTERN)
    if local.hour != 6:
        return False
    day = eastern_date(now)
    slate = [g for g in games.values() if g.get('league') in ('NFL', 'CFB')
             and eastern_date(gates.when(g.get('kickoff'))) == day]
    if not slate:
        return False
    import ladder
    where = ladder.state(ctx.first, ctx.latest)
    if where['open']:
        info = where['open'].get('ladder') or {}
        climb = f"Climb {info.get('run', where['run'])} Step {info.get('step', where['step'])} is open; the next waits for its result."
    else:
        climb = (f"Climb {where['run']} Step {where['step']} is being checked—not posted yet. "
                 f"{pick_card.dollars(where['stake'])} riding; {pick_card.dollars(where['banked'])} banked in this climb.")
    regular = ', '.join(moment.strftime('%-I:%M %p') for moment in gates.scheduled(day))
    extra = ', '.join(datetime(2000, 1, 1, hour, minute).strftime('%-I:%M %p') for hour, minute in LADDER_SCAN_TIMES)
    message = (f"{len(slate)} football games today.\nRegular desk checks: {regular} ET.\n"
               f"Extra Climb scans: {extra} ET.\n{climb}\n"
               "A qualifying rung triggers another phone alert with its exact legs, cutoff, Discord time and X time. No forced rung.")
    return alert(f"Kook'n schedule · {day:%a %b} {day.day}", message, priority='default', now=now,
                 click='https://keenroudy.com/sports/')


def lotto_pings(plans, ctx):
    """A fun parlay that hit is the post worth pinning (the owner pins the big ones by hand): (title, message) for each
    cashed parlay just scheduled. The ping lands five minutes later, when the cashed post is at the top of the profile."""
    import pick_card
    out = []
    for key, kind, *_ in plans:
        if kind != 'cashed':
            continue
        pick_id = key.split(':', 1)[1]
        pick = dict(ctx.first.get(pick_id) or {}, **ctx.latest.get(pick_id, {}))
        if pick and pick_card.play_kind(pick) == 'parlay' and isinstance(pick.get('odds'), (int, float)):
            out.append(('Longshot hit: pin it', f"{pick.get('title') or 'The fun parlay'} cashed at {int(pick['odds']):+d}. "
                        "The CASHED post is at the top of the profile: tap to open it, then ... and Pin to your profile."))
        info = pick.get('ladder') or {}
        if pick and pick_card.play_kind(pick) == 'ladder' and (info.get('totalAfter') or info.get('payout') or 0) >= (info.get('goal') or 1000):
            final = info.get('totalAfter') or info.get('payout')
            out.append(('80/20 Climb complete: pin it', f"The Kook'n 80/20 Climb reached ${final:,} from ${info.get('start', 50)} in "
                        f"{info.get('step', 1)} steps. The LADDER COMPLETE post is at the top of the profile: tap to open it, then ... "
                        "and Pin to your profile."))
    return out


def feature_scheduled(log_book, ctx, games, now, log=log):
    """A Pick of the Day named after its play was queued as a plain play (the first choice was pulled before it
    posted): the queued post is replaced by the Pick of the Day post, at the same time, once its card is live.
    Until then it stays queued as it was. Returns True when it was relabeled."""
    import buffer_post
    import featured
    key = featured.of_day(eastern_date(now).isoformat())
    entry = next((e for e in log_book.get('posts', []) if key and e.get('id') == key and e.get('kind') == 'buffer:play'
                  and e.get('bufferPostId') and not e.get('sentAt') and not e.get('cancelledAt') and not e.get('featured')
                  and (e.get('discord') or {}).get('state') != 'sent'), None)
    if not entry or key not in ctx.first or not entry.get('dueAt') or gates.when(entry['dueAt']) <= now + buffer_post.SOON:
        return False
    card = f'{key}-potd'
    if not buffer_post.reachable(buffer_post.card_url(card)):
        log(f'buffer: {key} is the Pick of the Day now; its card is not live yet, so its post is relabeled at the next run')
        return False
    pick = dict(ctx.first[key], **ctx.latest.get(key, {}))
    game = games.get((pick.get('gameIds') or [None])[0])
    before = dict(entry)
    entry.update(featured=True, cardKey=card, card=True)
    try:
        if requote(entry, pick, game, ctx, now, log=log):
            log(f'buffer: {key} goes out as the Pick of the Day')
            return True
    except buffer_post.BufferError as error:
        log(f'buffer: {key} not relabeled as the Pick of the Day: {error}')
    entry.clear()
    entry.update(before)
    return False


def pending_ladder_result_cards(log_book, ctx, now):
    """Queued Climb result posts that predate their graphic, keyed by post id.

    Normal runs schedule the result only after its card is live. This also repairs an already-queued text-only
    advancement when settlement and the hosted card arrive later, without creating a second public post.
    """
    import buffer_post
    import pick_card
    import receipts
    out = {}
    for entry in log_book.get('posts', []):
        if entry.get('kind') != 'buffer:cashed' or entry.get('card') or not entry.get('bufferPostId'):
            continue
        if entry.get('sentAt') or entry.get('cancelledAt') or entry.get('deletedAt') or entry.get('error'):
            continue
        if not entry.get('dueAt') or gates.when(entry['dueAt']) <= now + buffer_post.SOON:
            continue
        key = str(entry.get('id') or '')
        pick_id = next((key[len(prefix):] for prefix in ('cashed:', 'ladder-loss:', 'ladder-push:', 'ladder-void:')
                        if key.startswith(prefix)), '')
        if pick_id not in ctx.first:
            continue
        pick = dict(ctx.first[pick_id], **ctx.latest.get(pick_id, {}))
        if pick_card.play_kind(pick) == 'ladder' and pick.get('result') in ('win', 'loss', 'push', 'void'):
            out[key] = receipts.ladder_result_card_key(pick_id)
    return out


def upgrade_ladder_result_cards(log_book, ctx, now, channel=None, log=log):
    """Safely replace a future text-only Climb result with the same post plus its now-live card."""
    import buffer_post
    import x_post
    wanted = pending_ladder_result_cards(log_book, ctx, now)
    if not wanted:
        return 0
    channel = channel or buffer_post.x_channel(wanted='keenkooks')
    changed = 0
    for entry in log_book.get('posts', []):
        card_key = wanted.get(entry.get('id'))
        if not card_key:
            continue
        card = buffer_post.card_url(card_key)
        if not buffer_post.reachable(card):
            log(f"buffer: {entry['id']} still waits for its Climb result card")
            continue
        text = str((entry.get('discord') or {}).get('text') or '')
        if not text:
            log(f"buffer: {entry['id']} cannot attach its Climb result card: saved text is missing")
            continue
        new_id = buffer_post.create_post(text, channel['id'], gates.when(entry['dueAt']), card)
        try:
            buffer_post.delete_post(entry['bufferPostId'])
        except buffer_post.BufferError:
            try:
                buffer_post.delete_post(new_id)
            except buffer_post.BufferError:
                alert('KeenRoudy post may go out twice',
                      f"{entry['id']}: both {entry['bufferPostId']} and {new_id} are scheduled; delete one in Buffer")
            raise
        entry.update(bufferPostId=new_id, card=True, cardKey=card_key, cardAttachedAt=stamp(now),
                     textHash=x_post.text_hash(text))
        mirror = entry.get('discord') or {}
        if mirror.get('state') == 'pending':
            mirror['image'] = card
            entry['discord'] = mirror
        changed += 1
        log(f"buffer: {entry['id']} upgraded with its Climb result card")
    return changed


def now_quotes(ctx, games, now):
    """The best number available now for each open play whose game is today, for the post to show."""
    import receipts
    return {p['id']: q for p in receipts.todays_plays(ctx.first, ctx.latest, games, now) if (q := gates.best_now(p, ctx))}


def requote(entry, pick, game, ctx, now, log=log):
    """At the last look, rewrite a scheduled post whose number has moved since it was scheduled: the new post shows
    the number available now. Buffer has no edit here, so the post is deleted and scheduled again at the same time
    with the same card. Returns True when it was replaced."""
    import buffer_post
    import x_post
    if (entry.get('discord') or {}).get('state') == 'sent':
        log(f"precheck: {entry['id']} is already public in Discord; X keeps the same posted number")
        return False
    text = x_post.draft(pick, game, learning_weights(), now_quote=gates.best_now(pick, ctx), featured=bool(entry.get('featured')))
    if x_post.text_hash(text) == entry.get('textHash'):
        return False
    channel = buffer_post.x_channel(wanted='keenkooks')
    card = buffer_post.card_url(entry.get('cardKey') or entry['id']) if entry.get('card') else None
    due = max(gates.when(entry['dueAt']), buffer_post.discord_first_due(now))
    if game.get('kickoff') and due > gates.when(game['kickoff']) - post_windows.LEAD:
        log(f"precheck: {entry['id']} cannot move its X time and keep the Discord lead before kickoff")
        return False
    # The new post first, then the old one out: a failed create leaves the post as scheduled, and a failed delete
    # takes the new one back, so the play goes out once either way.
    new_id = buffer_post.create_post(text, channel['id'], due, card)
    try:
        buffer_post.delete_post(entry['bufferPostId'])
    except buffer_post.BufferError:
        try:
            buffer_post.delete_post(new_id)
        except buffer_post.BufferError:
            alert('KeenRoudy post may go out twice', f"{entry['id']}: both {entry['bufferPostId']} and {new_id} are scheduled; delete one in Buffer")
        raise
    entry['bufferPostId'] = new_id
    entry['dueAt'] = stamp(due)
    entry['textHash'] = x_post.text_hash(text)
    entry['requotedAt'] = stamp(now)
    mirror = entry.get('discord') or {}
    if mirror.get('state') == 'pending':
        mirror['text'] = buffer_post.without_playbook(text)
        mirror['readyAt'] = stamp(max(now, due - buffer_post.DISCORD_PLAY_LEAD))
        if card:
            mirror['image'] = card
        entry['discord'] = mirror
    log(f"precheck: {entry['id']} rescheduled with the number available now")
    return True


def homepage_editor(now, status, enabled=True):
    """Noncritical, local-only research selection. Never holds up a play or settlement."""
    try:
        import local_editor
        status['localEditor'] = local_editor.prepare(now, enabled=enabled)
    except Exception as error:
        status['localEditor'] = {'status': 'error', 'error': type(error).__name__}
    log('homepage editor:', status['localEditor'])


def commit_log(now, push=True, runner=git, cwd=ROOT):
    """Commit delivery evidence and the optional local homepage notes after scheduling."""
    paths = ('data/x-posted.json', 'site/data/desk-notes.json', 'data/nba-capture/', 'data/nba-trial/')
    changed = [p for p in paths if runner('status', '--porcelain', '--', p, cwd=cwd).stdout.strip()]
    if not changed:
        return {'committed': False, 'pushed': False}
    runner('add', '--', *changed, cwd=cwd)
    runner('commit', '--quiet', '-m', f"Record posts {eastern_date(now).isoformat()}", cwd=cwd)
    if not push:
        return {'committed': True, 'pushed': False}
    push_with_retry(runner, cwd)
    return {'committed': True, 'pushed': True}


# ------------------------------------------------------------------ status and heartbeat

NTFY = 'https://ntfy.sh/'
ALERT_QUIET = timedelta(hours=6)       # the same alert is not repeated inside this


def alert(title, message, priority='high', now=None, send=None, click=None, delay=None):
    """A push to the owner's phone through ntfy (free; a private topic in KEENROUDY_NTFY_TOPIC, which the ntfy app
    subscribes to). Only what went wrong and when: never a key, never a value from the env file. The same alert is
    sent once per six hours. Silent when no topic is set; a failed push never fails anything."""
    import hashlib
    import urllib.request
    topic = os.environ.get('KEENROUDY_NTFY_TOPIC', '').strip()
    if not topic:
        return False
    now = now or datetime.now(timezone.utc)
    sent_path = CONF / 'alerts.json'
    sent = load_json(sent_path, {})
    key = hashlib.sha256(f'{title}|{message}'.encode()).hexdigest()[:16]
    if key in sent and now - gates.when(sent[key]) < ALERT_QUIET:
        return False
    body = f'{message}\n\n{et(now)}'.encode('utf-8')
    headers = {'Title': title.encode('ascii', 'ignore').decode(), 'Priority': priority, 'Tags': 'cook'}
    if click:
        headers['Click'] = click            # tapping the notification opens this link
    if delay:
        headers['Delay'] = delay            # ntfy holds it this long ("5m"), so the post it points at is up
    request = urllib.request.Request(NTFY + topic, data=body, method='POST', headers=headers)
    try:
        (send or (lambda r: urllib.request.urlopen(r, timeout=10).read()))(request)
    except Exception as error:
        log(f'alert not sent ({type(error).__name__})')
        return False
    sent = {k: v for k, v in sent.items() if now - gates.when(v) < timedelta(days=2)}
    sent[key] = stamp(now)
    CONF.mkdir(parents=True, exist_ok=True)
    (sent_path).write_text(json.dumps(sent, indent=1) + '\n', encoding='utf-8')
    return True


def live_today_staleness(now, open_url=None):
    """Check the public payload itself; a fresh local build is not proof the live site refreshed."""
    import urllib.request
    open_url = open_url or urllib.request.urlopen
    try:
        with open_url('https://keenroudy.com/sports/data/app/today.json', timeout=5) as response:
            generated = json.load(response).get('generatedAt')
        age = now - gates.when(generated)
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return None  # the ordinary delivery checks distinguish outages from a verified stale payload
    if age > timedelta(hours=3):
        return f'live Today data is {round(age.total_seconds() / 3600, 1)} hours old'
    return None


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
    # Cached-only product checks share the existing change-only alert path. Never
    # call a provider or emit raw post bodies, credentials or network errors here.
    try:
        import desk_health
        health = desk_health.summary(root=ROOT, conf=CONF, logs=Path.home() / 'Library/Logs/KeenRoudy', now=now)
        problems.extend(row['message'] for row in health['issues'])
    except Exception:
        problems.append('cached desk-health checks could not be read')
    import invite_health
    invite_issue = invite_health.check()
    if invite_issue:
        problems.append(invite_issue)
    if stale := live_today_staleness(now):
        problems.append(stale)
    alert_file = CONF.parent.parent / 'Library' / 'Logs' / 'KeenRoudy' / 'ALERT.txt'
    transition_path = CONF / 'heartbeat-state.json'
    previous = load_json(transition_path, {}) or {}
    if not isinstance(previous, dict):
        previous = {}
    changed = sorted(problems) != previous.get('problems', [])
    transition_path.parent.mkdir(parents=True, exist_ok=True)
    transition_path.write_text(json.dumps({'problems': sorted(problems), 'checkedAt': stamp(now)}))
    if problems:
        text = f"KeenRoudy Sports heartbeat {stamp(now)}\n" + '\n'.join(f'- {p}' for p in problems) + '\n'
        alert_file.parent.mkdir(parents=True, exist_ok=True)
        alert_file.write_text(text, encoding='utf-8')
        if changed:
            subprocess.run(['osascript', '-e', f'display notification "{problems[0]}" with title "KeenRoudy Sports"'], capture_output=True)
            alert('KeenRoudy desk needs a look', '\n'.join(f'- {p}' for p in problems))
        print(text)
        return 1
    if alert_file.exists():
        alert_file.unlink()
    if changed and previous.get('problems'):
        alert('KeenRoudy desk recovered', 'The checks that previously failed are clear again.')
    print('heartbeat: all clear')
    return 0


def show_status(args):
    status = load_json(CONF / 'status.json', None)
    import desk_health
    shown = dict(status or {})
    shown['deskHealth'] = desk_health.summary(root=ROOT, conf=CONF)
    print(json.dumps(shown, indent=1))
    return 0


# ------------------------------------------------------------------ the check before a post goes out

PRECHECK_WINDOW = (timedelta(minutes=15), timedelta(minutes=45))    # closer to Discord release; same one-check budget
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
    return (f"Pulled before posting: {str(reason).rstrip('. ')}. Stays in the record at "
            f"{pricing.fmt(float(pick['line'])) if pick.get('line') is not None else 'its line'} and {int(pick['odds']):+d} "
            "and is graded as posted.")


def last_look(pick, game, ctx, context_file, use_llm, status, now):
    """The news check on one play, or one leg of a parlay, before it posts: the injury report read live, the
    forecast, the web researcher's news when it is on, then the judge on whatever can matter.
    Returns (why it should not go out or None, the researcher's verified facts, every fact)."""
    facts = evidence(pick, ctx, context_file)
    kept = []
    if researcher.enabled() and game:
        kept, dropped = researcher.research(game, gates.market_key(pick), gates.side_of(pick), now=now,
                                            player=ctx.names.get(str(pick.get('athleteId') or '')),
                                            quarterbacks=quarterbacks(game, ctx))
        status['research']['asked'] += 1
        status['research']['verified'] += len(kept)
        facts += kept
    return judge(pick, relevant_facts(pick, facts, ctx), use_llm, status), kept, facts


def release_pull_reason(pick, facts):
    """A released play is pulled only by the typed injury feed.

    Research and the local judge may flag a concern for the log, but they do not
    erase an admitted play. The only release-stopping facts are deterministic
    hard news on the player himself or his starting quarterback.
    """
    athlete = str(pick.get('athleteId') or '')
    for fact in facts or []:
        if researcher.from_web(fact) or fact.get('kind') != 'injury' or fact.get('direction') != 'against' or not hard(fact):
            continue
        fact_player = str(fact.get('id') or '').rsplit('-', 1)[-1]
        if fact.get('position') == 'QB' or (athlete and fact_player == athlete):
            return f"typed injury report: {fact.get('claim')}"
    return None


def parlay_last_look(pick, ctx, context_file, use_llm, status, now, closing=(), look=None):
    """Why a fun parlay should not post, or None.

    A previously closed leg or deterministic typed injury news on a leg may stop
    it. Research/model concerns are logged but cannot pull an admitted ticket.
    """
    hit = pulled_leg(pick, ctx, closing)
    if hit:
        return f"its {hit[0].get('title')} leg was pulled: {hit[1]}"
    look = look or last_look
    for leg in pick.get('legs') or []:
        single = leg_single(leg, pick)
        game = ctx.games.get(single['gameIds'][0])
        if not game:
            continue
        single['_team'] = ctx.player_team.get(str(single.get('athleteId') or ''))
        flag, _, facts = look(single, game, ctx, context_file, use_llm, status, now)
        reason = release_pull_reason(single, relevant_facts(single, facts, ctx))
        if flag and not reason:
            log(f"precheck: {pick.get('id')}: its {leg.get('title')} leg stands; model flag logged: {flag}")
        if reason:
            return f"its {leg.get('title')} leg: {reason}"
    return None


def precheck(args):
    """The last look before a scheduled play posts to X.

    The live typed injury feed can pull a play for deterministic hard news on
    its player or starting quarterback. Research/model concerns and price moves
    are logged only; the admitted play otherwise keeps its posted number.
    """
    import buffer_post
    import x_post
    now = gates.when(args.now) if args.now else datetime.now(timezone.utc)
    # Reuse the existing half-hour clock even when no play is due. Private,
    # cached-only checks cannot block the actual pre-post review.
    if not args.dry_run:
        try:
            import desk_health
            health = desk_health.summary(root=ROOT, conf=CONF, now=now)
            desk_health.monitor(health, CONF / 'desk-health.json',
                                lambda message: alert("Kook'n desk health", message, priority='default'))
        except Exception:
            log('cached desk-health check unavailable; pre-post review continues')
    if not precheck_due(x_post.load_log(), now):
        return 0
    status = {'errors': [], 'llm': {'judged': 0}, 'research': {'asked': 0, 'verified': 0, 'dropped': 0}}
    try:
        with Lock(CONF / 'run.lock'):
            if not args.dry_run:
                sync()
            log_book = x_post.load_log()
            if not args.dry_run:
                import nba_trial_runtime
                if nba_trial_runtime.precheck(now, log_book):
                    x_post.save_log(log_book)
                    commit_log(now, push=not args.no_push)
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
            closures, parlays = [], []
            for entry in due:
                key = entry['id']
                if key not in ctx.first:
                    continue
                pick = dict(ctx.first[key], **ctx.latest.get(key, {}))
                if pick.get('result') or pick.get('entryNote') or (pick.get('status') or 'active') != 'active':
                    entry['precheck'] = {'at': stamp(now), 'result': 'closed already'}
                    closures.append(None)
                    continue
                pick['_league'] = pick.get('league') or key.split('-')[0]
                if pick.get('legs') or pick.get('parlayType'):
                    parlays.append((entry, pick))       # after the single plays, so a leg pulled just now counts
                    continue
                game = ctx.games.get((pick.get('gameIds') or [None])[0])
                pick['_team'] = ctx.player_team.get(str(pick.get('athleteId') or ''))
                flag, kept, facts = last_look(pick, game, ctx, context_file, use_llm, status, now)
                reason = release_pull_reason(pick, relevant_facts(pick, facts, ctx))
                if flag and not reason:
                    log(f"precheck: {key} stands; model flag logged: {flag}")
                if needs_research(pick) and not lineup_confirmed(kept):
                    log(f"precheck: {key} has no new lineup confirmation; the admitted play stands")
                if reason:
                    kind_key, original = raw_first[key]
                    closures.append((pick['_league'], kind_key, dict(original, status='expired', entryNote=precheck_note(now, reason, original))))
                    entry['precheck'] = {'at': stamp(now), 'result': 'closed', 'reason': reason}
                    log(f"precheck: {key} closed before its post: {reason}")
                else:
                    entry['precheck'] = {'at': stamp(now), 'result': 'clear', 'facts': len(relevant_facts(pick, facts, ctx))}
                    log(f"precheck: {key} clear")
                    if not args.dry_run and game:
                        try:
                            requote(entry, pick, game, ctx, now)
                        except Exception as error:        # the post stands as scheduled; the number is only context
                            log(f"precheck: {key} not rescheduled with the number now ({type(error).__name__}: {error})")
            closures = [c for c in closures if c]
            for entry, pick in parlays:
                # Every leg gets the look a single play gets; a leg the desk has pulled closes the ticket.
                reason = parlay_last_look(pick, ctx, context_file, use_llm, status, now,
                                          closing=[c[2] for c in closures])
                if reason:
                    kind_key, original = raw_first[entry['id']]
                    closures.append((pick['_league'], kind_key, dict(original, status='expired',
                                                                     entryNote=parlay_note(now, reason, original, before_post=True))))
                    entry['precheck'] = {'at': stamp(now), 'result': 'closed', 'reason': reason}
                    log(f"precheck: {entry['id']} closed before its post: {reason}")
                else:
                    entry['precheck'] = {'at': stamp(now), 'result': 'clear', 'note': f"every leg checked ({len(pick['legs'])})"}
                    log(f"precheck: {entry['id']} clear: every leg checked")
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
            if args.dry_run:
                log('precheck: dry run; the post log is left as it was, so the real check still looks at these')
            else:
                x_post.save_log(log_book)
                commit_push(now, now.astimezone(EASTERN), {'published': 0, 'settled': 0, 'closed': len(closures)}, push=not args.no_push)
                commit_log(now, push=not args.no_push)
            return 0
    except RunError as error:
        if 'holds the lock' in str(error):
            log('precheck: a run is in progress; the check waits for the next half hour')
            return 0
        log('precheck STOPPED:', error)
        alert('KeenRoudy pre-post check stopped', str(error)[:600])
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', nargs='?', default='run', choices=('run', 'ladder', 'results', 'status', 'heartbeat', 'precheck', 'mirror'))
    parser.add_argument('--slot', help='force the run slot, HHMM Eastern')
    parser.add_argument('--now', help='pretend it is this UTC instant')
    parser.add_argument('--dry-run', action='store_true', help='no sync, capture, git; reports go to the pending folder')
    parser.add_argument('--no-llm', action='store_true', help='templates only, no local model')
    parser.add_argument('--no-push', action='store_true', help='commit but do not push')
    parser.add_argument('--record-screens', action='store_true', help='list screened candidates in the report')
    parser.add_argument('--select-now', action='store_true', help='owner-requested game-day selection after normal price refresh; never bypasses admission or release checks')
    parser.add_argument('--publish-kinds', help=f"comma list of {','.join(KINDS)}; default all")
    parser.add_argument('--ladder-spec', help='exact sportsbook quotes for a person-approved ladder rung')
    args = parser.parse_args(argv)
    if args.select_now:
        moment = gates.when(args.now) if args.now else datetime.now(timezone.utc)
        args.slot = moment.astimezone(EASTERN).strftime('%H%M')
    if args.command == 'heartbeat':
        return heartbeat(args)
    if args.command == 'status':
        return show_status(args)
    if args.command == 'precheck':
        return precheck(args)
    if args.command == 'mirror':
        return mirror(args)
    if args.command == 'results':
        # Free-feed settlement pass. It never captures odds or props, but it
        # grades finals, rebuilds the site, queues Cooked/Burnt reactions and
        # immediately gives a newly settled Climb its next stored-price scan.
        moment = gates.when(args.now) if args.now else datetime.now(timezone.utc)
        args.slot = moment.astimezone(EASTERN).strftime('%H%M')
        args.no_llm = True
        args.publish_kinds = 'settle,ladder'
    if args.command == 'ladder':
        # A lightweight extra scan: deterministic templates, settlement plus the Climb only. The ordinary free-feed
        # guards still cap every capture, and the same run lock prevents overlap with the full desk.
        moment = gates.when(args.now) if args.now else datetime.now(timezone.utc)
        args.slot = moment.astimezone(EASTERN).strftime('%H%M')
        args.no_llm = True
        args.publish_kinds = 'settle,ladder'
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
