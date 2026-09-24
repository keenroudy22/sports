"""Web-sourced facts for a candidate pick, from a headless Claude Code run, verified before anyone uses them.

The local model reads what the pipeline hands it. It cannot read the web. Researched favorites need
what the web says: an official availability report, a beat reporter on a role change, a forecast for
an outdoor game. This module asks the `claude` command line, running headless with only web search
and web fetch, for structured facts about one game, each with a source URL. Nothing it says is used
until verify() has fetched the URL itself and found every named person on the page. Unverified facts
are dropped, never argued from. It is off unless KEENROUDY_RESEARCHER=claude is set.

  python scripts/researcher.py GAME_ID [--market total|spread|recYds ...]
Stdlib only.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates

ROOT = Path(__file__).resolve().parents[1]
KINDS = ('injury', 'role', 'weather', 'stats')
DIRECTIONS = ('for', 'against', 'neutral')
MAX_FACTS = 8
USER_AGENT = 'KeenRoudySports/1.0 (+https://keenroudy.com/sports/)'

PROMPT = """You are a research assistant for a small football stats site. Find sourced facts about ONE game and return
them as JSON. You never predict, never recommend, never compute a number, and never invent a source.

Game: {away} at {home}, {league}, kickoff {kickoff}.
Market being considered: {market}.{player_line}

First find who is expected to play: each team's starting quarterback and whether he is healthy, suspended or
benched; key starters listed out, doubtful or questionable; and, for a player market, that player's own status and
role this week. Then anything else a reasonable person would say bears on this market. College teams often do
not publish injury reports, so the local beat reporting and the teams' own depth charts and press conferences
matter most there.

Look only at: official team or league injury and availability reports, the teams' own sites, and established
beat reporting (major outlets or the local paper that covers the team). Prefer reporting from the last four days.
You have room for about eight searches or page reads. Answer with what you have found by then; an answer with
two solid facts is worth more than a search that never finishes.
For each fact, give:
  kind: one of injury, role, weather, stats
  direction: "for" if it argues the market's price is wrong in the direction of "{side}", "against" if it argues
             the other way, "neutral" if it matters but does not point either way
  claim: one plain sentence, no opinion, with the numbers exactly as the source states them
  entities: the full names of the people the claim is about (players, coaches); empty for weather
  source: the exact https URL you read the fact on
  publishedAt: the date the source gives, if any

Return ONLY this JSON, nothing else:
{{"facts": [{{"kind": "...", "direction": "...", "claim": "...", "entities": ["..."], "source": "https://...", "publishedAt": "..."}}]}}
If you find nothing solid, return {{"facts": []}}."""


def enabled(env=None):
    return (env if env is not None else os.environ).get('KEENROUDY_RESEARCHER', '').strip().lower() == 'claude'


def prompt_for(game, market, side, policy=None, player=None, quarterbacks=None):
    """The prompt, plus what learning has found about sources: sites whose facts kept checking out come first,
    sites whose facts kept failing the check are left out."""
    away, home = game.get('away') or {}, game.get('home') or {}
    text = PROMPT.format(away=away.get('name') or away.get('abbreviation'), home=home.get('name') or home.get('abbreviation'),
                         league=game.get('league'), kickoff=game.get('kickoff'), market=market, side=side,
                         player_line=(f'\nPlayer: {player}.' if player else '') + quarterback_line(quarterbacks))
    if policy is None:
        import learning
        policy = learning.load_policy()
    learned = policy.get('researcher') or {}
    if learned.get('preferDomains'):
        text += '\n\nSites whose facts have checked out for us before, worth trying first: ' + ', '.join(learned['preferDomains']) + '.'
    if learned.get('avoidDomains'):
        text += '\nSites whose facts have not checked out for us; do not use them: ' + ', '.join(learned['avoidDomains']) + '.'
    return text


MAX_TURNS = 12              # web steps before the researcher must answer
# The researcher runs apart from everything else on the machine: its own empty folder (no project context, no
# memory, no instruction files), web search and page reads as its only tools, no other tool servers, and a system
# prompt that makes it a researcher and nothing else. Run from the repository with the default prompt, it had
# picked up the folder's context and spent its turns trying to run code instead of researching.
SANDBOX = Path.home() / '.config' / 'keenroudy' / 'research'
SYSTEM = ('You are a careful sports news researcher. Your only job is to answer the research request you are given, '
          'using web search and web page reads, and to return exactly the JSON it asks for. You have no other tools '
          'and no other task: never write code, run commands, or discuss anything but the request.')
ISOLATION = ['--tools', 'WebSearch,WebFetch', '--allowedTools', 'WebSearch,WebFetch', '--strict-mcp-config',
             '--system-prompt', SYSTEM]
FINISH = ('Stop researching now. Return ONLY the JSON object described at the start, with the facts you have '
          'already found (an empty list if none). No searching, no prose.')


def quarterback_line(quarterbacks):
    """The quarterbacks to ask about by name: everyone who has started for each team this season, latest first."""
    parts = [f"{team}: {', '.join(names)}" for team, names in (quarterbacks or {}).items() if names]
    if not parts:
        return ''
    return ('\nQuarterbacks who have started this season (latest first), whose status you must confirm first: '
            + '; '.join(parts) + '.')


def run_claude(prompt, runner=subprocess.run, timeout=420, max_turns=MAX_TURNS):
    """The `claude -p` JSON result text, or None when the command fails or is missing.

    A researcher that runs out of turns while still searching has found things but not written them down; its
    session is resumed once with an instruction to answer now, so the search is not thrown away."""
    command = ['claude', '-p', prompt, '--output-format', 'json', *ISOLATION, '--max-turns', str(max_turns)]
    payload = _claude(command, runner, timeout)
    if isinstance(payload, dict) and payload.get('subtype') == 'error_max_turns' and payload.get('session_id'):
        payload = _claude(['claude', '-p', FINISH, '--resume', payload['session_id'], '--output-format', 'json',
                           *ISOLATION, '--max-turns', '2'], runner, timeout=180)
    if isinstance(payload, dict):
        return payload.get('result')
    return payload


def _claude(command, runner, timeout):
    """The parsed JSON the command printed (even on a non-zero exit, which is how a turn limit ends), its raw text
    when it is not JSON, or None when nothing came back."""
    SANDBOX.mkdir(parents=True, exist_ok=True)
    try:
        result = runner(command, capture_output=True, text=True, timeout=timeout, cwd=str(SANDBOX))
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return None if result.returncode else result.stdout


def extract(text):
    """The facts list from the model's answer, tolerating prose around the JSON."""
    if not text:
        return []
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(text[start:end + 1])
    except ValueError:
        return []
    facts = payload.get('facts') if isinstance(payload, dict) else None
    return [f for f in (facts or []) if isinstance(f, dict)][:MAX_FACTS]


def shape(fact, game_id, index, now):
    """A fact in the run's shape, unverified, with anything malformed dropped."""
    kind = str(fact.get('kind') or '').lower()
    direction = str(fact.get('direction') or '').lower()
    source = str(fact.get('source') or '')
    claim = str(fact.get('claim') or '').strip()
    entities = [str(e).strip() for e in (fact.get('entities') or []) if str(e).strip()]
    if kind not in KINDS or direction not in DIRECTIONS or not source.startswith('https://') or not claim:
        return None
    return {'id': f'web-{game_id}-{index}', 'kind': kind, 'direction': direction, 'claim': claim[:400], 'entities': entities[:6],
            'source': source, 'publishedAt': fact.get('publishedAt'), 'retrievedAt': gates.stamp(now), 'verified': False,
            'origin': 'claude researcher'}


def fetch_text(url, opener=None, timeout=20):
    """The visible text of a page, or None when it cannot be read."""
    try:
        if opener:
            raw = opener(url)
        else:
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    return None
                raw = response.read(2_000_000)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    text = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else str(raw)
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return html.unescape(re.sub(r'\s+', ' ', text)).lower()


def verify(fact, opener=None):
    """Fetch the source and require every named person's surname on the page; weather needs the page alone."""
    page = fetch_text(fact['source'], opener)
    if page is None:
        return dict(fact, verified=False, verifyNote='source could not be read')
    missing = [name for name in fact.get('entities') or [] if name.split()[-1].lower() not in page]
    if missing:
        return dict(fact, verified=False, verifyNote=f"not on the page: {', '.join(missing)}")
    if fact['kind'] in ('injury', 'role') and not fact.get('entities'):
        return dict(fact, verified=False, verifyNote='an injury or role fact must name someone')
    if fact['kind'] in ('injury', 'role') and not status_near_name(fact, page):
        return dict(fact, verified=False, verifyNote="the page does not put the claim's status next to the name")
    return dict(fact, verified=True)


STATUS_WORDS = ('out', 'doubtful', 'questionable', 'probable', 'injur', 'hurt', 'suspend', 'ruled', 'return',
                'practice', 'limited', 'start', 'starter', 'starting', 'backup', 'bench', 'available', 'active',
                'inactive', 'reserve', 'surgery', 'concussion', 'protocol', 'sidelined', 'expected to play',
                'will not play', 'did not', 'depth chart', 'game-time', 'week-to-week', 'day-to-day', 'season-ending')
NEAR = 300                  # characters either side of the name


def status_near_name(fact, page):
    """An injury or lineup claim counts only when a status word from the claim itself sits within a few hundred
    characters of the person's surname on the page. A name somewhere on a long page is not enough."""
    claim = str(fact.get('claim') or '').lower()
    words = [w for w in STATUS_WORDS if re.search(r'\b' + re.escape(w), claim)]
    if not words:
        return True         # the claim names no status to look for; the name check stands alone
    for name in fact.get('entities') or []:
        surname = name.split()[-1].lower()
        for match in re.finditer(re.escape(surname), page):
            window = page[max(0, match.start() - NEAR):match.end() + NEAR]
            if any(re.search(r'\b' + re.escape(w), window) for w in words):
                return True
    return False


def research(game, market, side, runner=subprocess.run, opener=None, now=None, player=None, quarterbacks=None):
    """Verified facts for one game and market. Empty when the researcher is silent or nothing survives."""
    now = now or datetime.now(timezone.utc)
    answer = run_claude(prompt_for(game, market, side, player=player, quarterbacks=quarterbacks), runner)
    shaped = [s for s in (shape(f, game['id'], i, now) for i, f in enumerate(extract(answer))) if s]
    checked = [verify(f, opener) for f in shaped]
    return [f for f in checked if f['verified']], [f for f in checked if not f['verified']]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('game_id')
    parser.add_argument('--market', default='total')
    parser.add_argument('--side', default='over')
    args = parser.parse_args(argv)
    slate = json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
    game = next((g for g in slate.get('games', []) if g['id'] == args.game_id), None)
    if not game:
        sys.exit(f'{args.game_id} is not in the slate')
    kept, dropped = research(game, args.market, args.side)
    print(f'{len(kept)} verified facts, {len(dropped)} dropped')
    for fact in kept:
        print(f"  [{fact['direction']}] {fact['kind']}: {fact['claim']}\n      {fact['source']}")
    for fact in dropped:
        print(f"  dropped ({fact.get('verifyNote')}): {fact['claim'][:100]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
