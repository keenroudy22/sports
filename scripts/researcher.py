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
Market being considered: {market}.

Look only at: official team or league injury and availability reports, the teams' own sites, and established
beat reporting (major outlets or the local paper that covers the team). For each fact that a reasonable
person would say bears on this market, give:
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


def prompt_for(game, market, side, policy=None):
    """The prompt, plus what learning has found about sources: sites whose facts kept checking out come first,
    sites whose facts kept failing the check are left out."""
    away, home = game.get('away') or {}, game.get('home') or {}
    text = PROMPT.format(away=away.get('name') or away.get('abbreviation'), home=home.get('name') or home.get('abbreviation'),
                         league=game.get('league'), kickoff=game.get('kickoff'), market=market, side=side)
    if policy is None:
        import learning
        policy = learning.load_policy()
    learned = policy.get('researcher') or {}
    if learned.get('preferDomains'):
        text += '\n\nSites whose facts have checked out for us before, worth trying first: ' + ', '.join(learned['preferDomains']) + '.'
    if learned.get('avoidDomains'):
        text += '\nSites whose facts have not checked out for us; do not use them: ' + ', '.join(learned['avoidDomains']) + '.'
    return text


def run_claude(prompt, runner=subprocess.run, timeout=420, max_turns=8):
    """The `claude -p` JSON result text, or None when the command fails or is missing."""
    command = ['claude', '-p', prompt, '--output-format', 'json', '--allowedTools', 'WebSearch,WebFetch',
               '--max-turns', str(max_turns)]
    try:
        result = runner(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return result.stdout
    return payload.get('result') if isinstance(payload, dict) else result.stdout


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
    return dict(fact, verified=True)


def research(game, market, side, runner=subprocess.run, opener=None, now=None):
    """Verified facts for one game and market. Empty when the researcher is silent or nothing survives."""
    now = now or datetime.now(timezone.utc)
    answer = run_claude(prompt_for(game, market, side), runner)
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
