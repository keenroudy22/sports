"""A card for one play in the kitchen's colours: the team we lean on, as SVG from the pick's own fields.

The repo stays standard library: the SVG is plain text written here. Turning it into the PNG that X
will show is done by a headless browser on the machine (Chrome on the Mac Studio or a GitHub runner),
which is a system tool, not a Python package. The PNG is never committed.

The card wears the colours of the side the play is on: the team a spread backs, the player's team for a
prop, the home team for a total with the away team's colour at the edge. Colours come from the slate
(ESPN's team colours) with the site's own table as the fallback. The theme is the kitchen: KOOK'N, the
pan, a plate served at a book.

  python scripts/pick_card.py PICK_ID [--out FILE.png] [--svg]
"""
import argparse
import hashlib
import html
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pricing
import felt_cards

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1200, 675
NEUTRAL = '#2b3440'
CREAM, INK = '#f6f1e6', '#141414'
CHROME_CANDIDATES = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                     '/Applications/Chromium.app/Contents/MacOS/Chromium', 'google-chrome', 'google-chrome-stable',
                     'chromium', 'chromium-browser')

# Set only after the owner approves the rendered set. The environment override is for isolated previews and rollback.
FELT_FROM = None
# Owner-delegated cutover, Oct 8: reviewed real renders; no published image is rebuilt.
# The explicit Eastern instant is valid only if the verified deploy finishes by 1:30 PM.
TICKET_FROM = '2026-10-08T14:00:00-04:00'


def _theme_time(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=ZoneInfo('America/New_York'))
    if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
        return datetime(value.year, value.month, value.day, tzinfo=ZoneInfo('America/New_York'))
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else result.replace(tzinfo=ZoneInfo('America/New_York'))
    except (TypeError, ValueError):
        return None


def _cutover_time(value):
    """A production switch requires an explicit timezone offset."""
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return result if result.tzinfo is not None else None


def felt_enabled(item=None, moment=None):
    """Theme by publication time. The explicit preview switch never changes a published record."""
    forced = os.environ.get('KEENROUDY_CARD_THEME', '').lower()
    if forced in ('felt', 'legacy'):
        return forced == 'felt'
    cutover = os.environ.get('KEENROUDY_FELT_FROM') or FELT_FROM
    if not cutover:
        return False
    source = moment
    if source is None and isinstance(item, dict):
        source = next((item.get(key) for key in ('publishedAt', 'settledAt', 'due', 'day', 'capturedAt')
                       if item.get(key)), None)
        if source is None:
            source = str(item.get('key') or item.get('card') or '').rsplit(':', 1)[-1]
    when, start = _theme_time(source), _cutover_time(cutover)
    return bool(when and start and when >= start)


def ticket_enabled(item=None, moment=None):
    """Select new art by its original publication time, never by rebuild time."""
    cutover = os.environ.get('KEENROUDY_TICKET_FROM') or TICKET_FROM
    if not cutover:
        return False
    source = moment
    if source is None and isinstance(item, dict):
        source = next((item.get(key) for key in ('publishedAt', 'settledAt', 'due', 'day', 'capturedAt')
                       if item.get(key)), None)
    when, start = _theme_time(source), _cutover_time(cutover)
    return bool(when and start and when >= start)


def card_theme(moment=None, item=None):
    """Production-renderer label saved with each image post for like-category comparisons.

    Preview and Mac-only environment overrides do not relabel hosted art. The production cutover constant is the
    renderer's shared decision, and the supplied moment is when that artifact entered the publishing flow.
    """
    source = moment
    if source is None and isinstance(item, dict):
        source = next((item.get(key) for key in ('publishedAt', 'settledAt', 'due', 'day', 'capturedAt')
                       if item.get(key)), None)
    when, ticket_start = _theme_time(source), _cutover_time(TICKET_FROM)
    if when and ticket_start and when >= ticket_start:
        return 'ticket'
    start = _cutover_time(FELT_FROM)
    return 'felt' if when and start and when >= start else 'legacy'


def felt_game(game):
    if not game:
        return None
    def team(row):
        row = dict(row or {})
        row.setdefault('abbr', row.get('abbreviation'))
        return row
    return dict(game, away=team(game.get('away')), home=team(game.get('home')))


def felt_when(game):
    if not (game or {}).get('kickoff'):
        return ''
    try:
        from zoneinfo import ZoneInfo
        local = datetime.fromisoformat(game['kickoff'].replace('Z', '+00:00')).astimezone(
            ZoneInfo('America/Indiana/Indianapolis'))
        return f'{local:%a %-I:%M %p} ET'
    except (ValueError, TypeError):
        return ''


def chrome_path():
    override = os.environ.get('KEENROUDY_CHROME')
    if override:
        return override
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def esc(text):
    return html.escape(str(text if text is not None else ''), quote=True)


def fit(text, limit):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


# ------------------------------------------------------------------ colour

def hex_rgb(value):
    value = str(value or '').lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return hex_rgb(NEUTRAL)


def luminance(value):
    r, g, b = (c / 255 for c in hex_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def shade(value, factor):
    """The colour scaled toward black (factor < 1) or white (factor > 1)."""
    r, g, b = hex_rgb(value)
    if factor <= 1:
        r, g, b = (int(c * factor) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * (factor - 1)) for c in (r, g, b))
    return '#{:02x}{:02x}{:02x}'.format(*(max(0, min(255, c)) for c in (r, g, b)))


def team_colors(game, side, identities=None):
    """(primary, alternate) for one side of a game: the slate's colours, else the site's table, else neutral."""
    team = (game or {}).get(side) or {}
    primary = team.get('color')
    if not primary:
        try:
            import build_site
            primary = build_site.color((game or {}).get('league'), team.get('abbreviation'), identities or {})
        except Exception:
            primary = None
    primary = primary if primary and primary.lower() not in ('#64748b',) else NEUTRAL
    return primary, team.get('alternateColor') or shade(primary, 0.55)


def side_for(pick, game, player_side=None):
    """Which side the play is on: the spread's team, the player's team, or the home team for a total."""
    if pick.get('athleteId'):
        return player_side or 'home'
    direction = str(pick.get('direction') or '').lower()
    if pick.get('marketType') == 'spread' and direction in ('home', 'away'):
        return direction
    return 'home'


# ------------------------------------------------------------------ the card

PAN = ('<g transform="translate({x},{y}) scale({s})" fill="none" stroke="{c}" stroke-width="7" stroke-linecap="round">'
       '<circle cx="34" cy="34" r="26"/><path d="M60 34 H108"/><circle cx="34" cy="34" r="12" stroke-width="4" stroke-opacity="0.6"/></g>')
AVATAR = ROOT / 'site' / 'kookn.jpg'     # the @keenkooks profile picture, the kitchen's face
CHEF = ROOT / 'site' / 'kookn-chef.png'  # the same chef cut out of that picture (macOS subject lifting), served on the plate


def avatar_uri(path=AVATAR):
    """The avatar as a data URI, so the SVG renders anywhere; None when the file is not there."""
    import base64
    path = Path(path)
    if not path.exists():
        return None
    mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def badge(x, y, r, uri, ring):
    """A round badge holding the avatar, with a ring in the accent colour."""
    return (f'<defs><clipPath id="badge"><circle cx="{x}" cy="{y}" r="{r}"/></clipPath></defs>'
            f'<image href="{uri}" x="{x - r}" y="{y - r}" width="{2 * r}" height="{2 * r}" clip-path="url(#badge)" preserveAspectRatio="xMidYMid slice"/>'
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{ring}" stroke-width="4"/>')


# What sits on the plate: the player's photo on a player prop, the teams' logos on a game line, the chef on a parlay
# and on anything whose image cannot be fetched. The photos are ESPN's and the logos are the teams' marks; set
# KEENROUDY_CARD_ART=0 (or CARD_ART = False) to serve every card with the chef again.
CARD_ART = os.environ.get('KEENROUDY_CARD_ART', '1') != '0'
HEADSHOT = 'https://a.espncdn.com/i/headshots/{sport}/players/full/{athlete}.png'
LOGO = {'NFL': 'https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png', 'CFB': 'https://a.espncdn.com/i/teamlogos/ncaa/500/{id}.png'}


def fetch_data_uri(url, timeout=10):
    """An image by URL as a data URI, so the rendered card never depends on the network; None on any failure."""
    import base64
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            kind = response.headers.get('Content-Type', '')
            body = response.read()
    except Exception:
        return None
    if not kind.startswith('image/') or len(body) < 200:
        return None
    return f'data:{kind.split(";")[0]};base64,' + base64.b64encode(body).decode('ascii')


def logo_url(team, league):
    if league == 'NFL' and team.get('abbreviation'):
        return LOGO['NFL'].format(abbr=str(team['abbreviation']).lower())
    if league == 'CFB' and team.get('id'):
        return LOGO['CFB'].format(id=team['id'])
    return None


def artwork(pick, game, fetch=None, player_side=None):
    """{'kind': 'photo', 'uri'} for an NFL/college player prop, {'kind': 'logos', 'uris'} for a game line (the side's logo
    on a spread, both teams' on a total), or None for the chef: a parlay, a failed fetch, or the switch off."""
    if not CARD_ART or play_kind(pick) in ('parlay', 'ladder'):
        return None
    fetch = fetch or fetch_data_uri
    league = (game or {}).get('league') or str(pick.get('id', '')).split('-')[0]
    if play_kind(pick) == 'player':
        if league not in ('NFL', 'CFB') or not pick.get('athleteId'):
            return None
        url = HEADSHOT.format(sport='nfl' if league == 'NFL' else 'college-football', athlete=pick['athleteId'])
        uri = fetch(url) or fetch(url)
        if uri:
            return {'kind': 'photo', 'uri': uri}
        if game and player_side in ('home', 'away'):
            side = player_side
            team_url = logo_url(game.get(side) or {}, league) if side else None
            badge = fetch(team_url) if team_url else None
            if badge:
                return {'kind': 'logos', 'uris': [badge], 'fallback': 'no-headshot'}
        return None
    if not game:
        return None
    direction = str(pick.get('direction') or '').lower()
    sides = [direction] if pick.get('marketType') == 'spread' and direction in ('home', 'away') else ['away', 'home']
    urls = [logo_url(game.get(side) or {}, league) for side in sides]
    uris = [fetch(url) for url in urls if url]
    return {'kind': 'logos', 'uris': uris} if len(uris) == len(sides) and all(uris) else None


def plate(cx, cy, uri, light, art=None):
    """The plate every card serves on. The chef: the cutout scaled past the rim so the edges of the source picture
    fall outside. A player: his photo standing on the rim. A game line: the logos, side by side on a total."""
    r, size = 178, 380
    parts = [f'<circle cx="{cx}" cy="{cy}" r="215" fill="{CREAM}" fill-opacity="{0.10 if not light else 0.35}"/>',
             f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{CREAM}" fill-opacity="{0.16 if not light else 0.45}"/>']
    kind = (art or {}).get('kind')
    if kind == 'photo':
        w, h = 430, 312                          # ESPN headshots are 350 by 254: shoulders on the rim, face centred
        parts += [f'<defs><clipPath id="plate"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>',
                  f'<image href="{art["uri"]}" x="{cx - w // 2}" y="{cy + r - h}" width="{w}" height="{h}" clip-path="url(#plate)" preserveAspectRatio="xMidYMax meet"/>']
    elif kind == 'logos':
        uris = art['uris']
        if len(uris) == 1:
            parts.append(f'<image href="{uris[0]}" x="{cx - 120}" y="{cy - 120}" width="240" height="240" preserveAspectRatio="xMidYMid meet"/>')
        else:
            parts += [f'<image href="{uris[0]}" x="{cx - 150}" y="{cy - 82}" width="138" height="138" preserveAspectRatio="xMidYMid meet"/>',
                      f'<image href="{uris[1]}" x="{cx + 12}" y="{cy - 82}" width="138" height="138" preserveAspectRatio="xMidYMid meet"/>',
                      f'<text x="{cx}" y="{cy + 96}" fill="{INK if light else CREAM}" fill-opacity="0.8" font-size="24" font-weight="700" text-anchor="middle" letter-spacing="3">AT</text>']
    elif uri:
        parts += [f'<defs><clipPath id="plate"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>',
                  f'<image href="{uri}" x="{cx - 195}" y="{cy - r - 22}" width="{size}" height="{size}" clip-path="url(#plate)"/>']
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CREAM}" stroke-opacity="{0.35 if not light else 0.6}" stroke-width="4"/>')
    return parts


SCHOOL_NAMES = {'2390': 'Miami (FL)'}      # ESPN calls the Hurricanes plain "Miami"; the RedHawks are "Miami (OH)"


def team_label(team, league):
    """A college team by its school ("Central Michigan", not "C Michigan"); an NFL team by its short name."""
    if not team:
        return ''
    if league == 'CFB':
        return SCHOOL_NAMES.get(str(team.get('id'))) or team.get('school') or team.get('short') or team.get('abbreviation') or ''
    return team.get('short') or team.get('abbreviation') or ''


def display_title(pick, game):
    """The pick's title with each team named as team_label names it. The published title is never changed; this is
    only how a post and a card say it."""
    title = str(pick.get('title') or '')
    if pick.get('athleteId') or pick.get('legs'):
        return title
    for word in ('OVER', 'UNDER'):                      # a team play says over and under in lowercase, every time
        title = title.replace(f' {word} ', f' {word.lower()} ')
    if not game:
        return title
    league = game.get('league') or str(pick.get('id', '')).split('-')[0]
    away, home = game.get('away') or {}, game.get('home') or {}
    # A game total always names the matchup from the slate and keeps only the market suffix from the
    # append-only published title. This repairs old public typos such as "Stateate" and a repeated
    # "(FL)" without rewriting the record that produced them.
    if pick.get('marketType') == 'total' or str(pick.get('direction') or '').lower() in ('over', 'under'):
        low = title.lower()
        for word in ('over', 'under'):
            marker = f' {word} '
            # Rebuild only from human team names. Some small fixtures and incomplete feeds have abbreviations only;
            # in that case the already-readable published matchup is better than "IOWA at MICH".
            named = lambda team: SCHOOL_NAMES.get(str(team.get('id'))) or team.get('school') or team.get('short')
            if marker in low and named(away) and named(home):
                suffix = title[low.index(marker) + len(marker):]
                return f'{team_label(away, league)} at {team_label(home, league)} {word} {suffix}'
    names = lambda team: sorted({x for x in (team_label(team, league), team.get('school'), team.get('short'), team.get('abbreviation')) if x},
                                key=len, reverse=True)      # the posted name first: "Miami (FL)" is not "Miami" plus " (FL)"
    for a in names(away):
        for h in names(home):
            lead = f'{a} at {h}'
            # Whole names only: "New Mexico St" is not the start of "New Mexico State" (2026-09-26 posted "Stateate").
            if title.startswith(lead) and title[len(lead):len(lead) + 1] in ('', ' '):
                return f'{team_label(away, league)} at {team_label(home, league)}' + title[len(lead):]
    return title


SHORT_WORDS = (('receiving yards', 'rec yds'), ('rushing yards', 'rush yds'), ('passing yards', 'pass yds'),
               ('pass attempts', 'pass att'))


def short_words(text):
    for long_, short in SHORT_WORDS:
        text = text.replace(long_, short)
    return text


def short_leg(title):
    """A leg the way a bettor types it: "Iowa/Michigan over 38.5", "Drake London 40+ rec yds"."""
    text = str(title or '')
    for word in ('OVER', 'UNDER'):
        text = text.replace(f' {word} ', f' {word.lower()} ')
    if ' at ' in text and (' over ' in text or ' under ' in text):
        text = text.replace(' at ', '/', 1)
    return short_words(text)


def short_title(pick, game=None):
    """The play the way a bettor types it: "Iowa/Michigan over 38.5", "Duke -10 vs Stanford", "Jeremiyah Love over
    85.5 rush yds". Only how a post says it; the published title never changes."""
    return short_leg(display_title(pick, game))


def plain_number(value):
    """47.1 reads 47 and 96.8 reads 97; under ten it keeps its tenth (4.6 receptions)."""
    return str(int(round(value))) if abs(value) >= 10 else f'{round(value, 1):g}'


def our_number(pick, game=None):
    """The posted model number in the owner's first-person voice; empty without a projection."""
    projection = pick.get('projection')
    if not isinstance(projection, (int, float)) or pick.get('legs'):
        return ''
    direction = str(pick.get('direction') or '').lower()
    if pick.get('marketType') == 'spread' and not (pick.get('athleteId') or pick.get('market')) and game and direction in ('home', 'away'):
        league = game.get('league') or str(pick.get('id', '')).split('-')[0]
        side = game.get(direction) or {}
        other = game.get('away' if direction == 'home' else 'home') or {}
        if abs(projection) < 0.5:
            return 'I have it even.'
        team = side if projection < 0 else other          # the side's own number: -14 is that side by 14
        return f"I have {team_label(team, league)} by {int(round(abs(projection)))}."
    return f'I have it at {plain_number(projection)}.'


FRACTIONS = {0.25: '¼', 0.5: '½', 0.75: '¾'}


def stake(pick):
    """Units at risk, as the site's record counts them (site/core.js stakeOf): riskUnits, else one."""
    try:
        risk = float(pick.get('riskUnits'))
    except (TypeError, ValueError):
        return 1.0
    return risk if risk > 0 else 1.0


def units_label(pick):
    amount = stake(pick)
    if amount in FRACTIONS:
        return f'{FRACTIONS[amount]} unit'
    return f'{amount:g} unit' + ('' if amount == 1 else 's')


def number_line(pick):
    """What we project, in plain words, the same on the card and in the post: "We project 47.1 total points" for a
    game total, "We project 4.6 receptions" for a player. A side keeps "Our number -14 vs the -10"."""
    projection, line = pick.get('projection'), pick.get('line')
    if not isinstance(projection, (int, float)) or not isinstance(line, (int, float)):
        return ''
    value = pricing.fmt(float(projection))
    if pick.get('athleteId') or pick.get('market'):
        words = pricing.WORDS.get(pricing.market_of(pick))
        if words:
            return f"We project {value} {words}"
    elif pick.get('marketType') == 'total' or str(pick.get('direction') or '').lower() in ('over', 'under'):
        return f"We project {value} total points"
    return f"Our number {value} vs the {pricing.fmt(float(line))}"


KINDS = {'player': 'PLAYER PROP', 'parlay': 'FUN PARLAY', 'ladder': 'LADDER'}
LOTTO = 1000


def play_kind(pick):
    """The internal kind used for ordering: player props, game lines (sides and totals), fun parlays and the ladder's
    rungs (scripts/ladder.py), which keep their own count in dollars."""
    if pick.get('parlayType') == 'ladder':
        return 'ladder'
    if pick.get('legs') or pick.get('parlayType'):
        return 'parlay'
    return 'player' if pick.get('athleteId') or pick.get('market') else 'team'


def play_label(pick):
    """The precise public label. A whole-game side or total is a game line, not a team prop."""
    kind = play_kind(pick)
    if kind == 'parlay':
        if pick.get('parlayType') == 'easyProps':
            return 'EASY PROPS'
        return 'LOTTO TICKET' if isinstance(pick.get('odds'), (int, float)) and pick['odds'] >= LOTTO else 'LONGSHOT'
    if kind != 'team':
        return KINDS[kind]
    market = str(pick.get('marketType') or '').lower()
    direction = str(pick.get('direction') or '').lower()
    if market == 'total' or direction in ('over', 'under'):
        return 'GAME TOTAL'
    if market == 'spread' or direction in ('home', 'away'):
        return 'GAME SPREAD'
    return 'GAME LINE'


def kicker(pick, featured=False):
    """The label every card and every post leads with; the day's Pick of the Day and a researched favorite say so."""
    if play_kind(pick) == 'ladder':
        return f"80/20 CLIMB · STEP {(pick.get('ladder') or {}).get('step', 1)}"
    label = play_label(pick)
    if featured:
        return f'HOT PLATE (POTD) · {label}'
    return f'{label} · FAVORITE' if pick.get('favorite') is True and play_kind(pick) != 'parlay' else label


TEXT_WIDTH = 640     # pixels the title may use: from the left margin to short of the plate


def ticket_leg_parts(title):
    """Split display text only; never infer a different line, direction or market."""
    title = str(title or '').strip()
    match = re.match(r'^(.*?)\s+(over|under)\s+([+-]?\d+(?:\.\d+)?)\b\s*(.*)$', title, re.I)
    if match:
        name, direction, line, market = match.groups()
        return name, f'{direction.upper()} {line}', market
    match = re.match(r'^(.*?)\s+(\d+(?:\.\d+)?\+)\s+(.+)$', title)
    if match:
        return match.groups()
    match = re.match(r'^(.*?)\s+([+-]\d+(?:\.\d+)?|ML|moneyline)$', title, re.I)
    if match:
        return match.group(1), match.group(2), ''
    return '', title, ''                 # unfamiliar markets retain the complete published wording


TICKET_STYLES = (
    {'accent': '#54edbf', 'accent2': '#32cfff', 'bg': '#07111e', 'bg2': '#102c38', 'row': '#102230', 'edge': '#284653'},
    {'accent': '#32cfff', 'accent2': '#54edbf', 'bg': '#071322', 'bg2': '#0d2941', 'row': '#0d2234', 'edge': '#23516b'},
    {'accent': '#72f2c0', 'accent2': '#65d8ff', 'bg': '#061018', 'bg2': '#12313b', 'row': '#10262d', 'edge': '#2d535a'},
)


def ticket_style(pick, style=None):
    """A stable visual rotation: rerendering one published ticket never changes its look."""
    if style is None:
        digest = hashlib.sha256(str(pick.get('id') or pick.get('title') or '').encode('utf-8')).digest()
        style = digest[0]
    return TICKET_STYLES[int(style) % len(TICKET_STYLES)]


def leg_athlete_id(leg):
    return str(leg.get('athleteId') or (re.match(r'prop-[A-Z]+-\d+-(\d+)-', str(leg.get('id') or '')) or ('', ''))[1] or '')


def ticket_art(pick, games=None, player_team=None, fetch=None):
    """One real player photo or relevant team mark per leg, with a safe empty fallback."""
    fetch = fetch or fetch_data_uri
    games, player_team = games or {}, player_team or {}
    league = str(pick.get('league') or pick.get('id') or '').split('-')[0]
    result = []
    for leg in pick.get('legs') or []:
        athlete = leg_athlete_id(leg)
        uri = fetch(HEADSHOT.format(sport='nfl' if league == 'NFL' else 'college-football', athlete=athlete)) if athlete and league in ('NFL', 'CFB') else None
        if uri:
            result.append({'kind': 'photo', 'uri': uri})
            continue
        game = games.get(leg.get('gameId')) or {}
        side = str(leg.get('direction') or leg.get('side') or '').lower()
        teams = [game.get(side)] if side in ('home', 'away') else [game.get('away'), game.get('home')]
        if athlete and player_team:
            team_id = str(player_team.get(athlete) or '')
            teams = [team for team in teams if team and str(team.get('id')) == team_id] or teams
        uris = [fetch(url) for team in teams if team and (url := logo_url(team, league))]
        uris = [value for value in uris if value]
        result.append({'kind': 'logos', 'uris': uris[:2]} if uris else None)
    return result


def ticket_leg_art(index, art, y, height, accent):
    item = art[index] if index < len(art) else None
    if not item:
        return ''
    uris = [item['uri']] if item.get('kind') == 'photo' and item.get('uri') else item.get('uris') or []
    if not uris:
        return ''
    clip = f'legArt{index}'
    if len(uris) == 1:
        return (f'<defs><clipPath id="{clip}"><rect x="760" y="{y + 4}" width="272" height="{height - 8}" rx="20"/></clipPath>'
                f'<linearGradient id="legFade{index}" x1="0" x2="1"><stop stop-color="#102230" stop-opacity=".95"/><stop offset=".45" stop-color="#102230" stop-opacity=".18"/><stop offset="1" stop-color="#102230" stop-opacity="0"/></linearGradient></defs>'
                f'<image href="{uris[0]}" x="772" y="{y + 10}" width="250" height="{height - 14}" clip-path="url(#{clip})" preserveAspectRatio="xMidYMax meet"/>'
                f'<rect x="742" y="{y + 4}" width="160" height="{height - 8}" fill="url(#legFade{index})"/>')
    logo_y = y + max(18, (height - 124) // 2)
    return (f'<image href="{uris[0]}" x="806" y="{logo_y}" width="104" height="104" preserveAspectRatio="xMidYMid meet"/>'
            f'<image href="{uris[1]}" x="914" y="{logo_y}" width="104" height="104" preserveAspectRatio="xMidYMid meet"/>')


def ticket_svg(pick, game=None, avatar=None, art=None, style=None):
    """Phone-first fun tickets: full-width legs, no truncated wagers or oversized artwork."""
    if felt_enabled(pick):
        display = dict(pick)
        context = f"{len(set(pick.get('gameIds') or [])) or len(pick.get('legs') or [])} games"
        if (game or {}).get('kickoff'):
            try:
                from zoneinfo import ZoneInfo
                local = datetime.fromisoformat(game['kickoff'].replace('Z', '+00:00')).astimezone(
                    ZoneInfo('America/New_York'))
                context += f' · {local:%a %b %-d}'
            except (ValueError, TypeError):
                pass
        display['_timing'] = context
        return felt_cards.fun_ticket_card(display, play_label(pick).title(), art)
    legs = pick.get('legs') or []
    art = art or []
    colors = ticket_style(pick, style)
    accent, accent2 = colors['accent'], colors['accent2']
    rows = []
    y = 252
    for index, leg in enumerate(legs, 1):
        name, line, market = ticket_leg_parts(leg.get('title') or 'Leg details unavailable')
        names = textwrap.wrap(name, 27) if name else []
        lines = textwrap.wrap(line, 19)
        markets = textwrap.wrap(market, 44) if market else []
        height = 56 + len(names) * 52 + len(lines) * 88 + len(markets) * 40
        rows.append(f'<g data-leg="{index}"><rect x="44" y="{y}" width="992" height="{height}" rx="24" fill="{colors["row"]}" stroke="{colors["edge"]}" stroke-width="2"/>')
        rows.append(f'<rect x="44" y="{y + 25}" width="6" height="{height - 50}" rx="3" fill="{accent}"/>')
        rows.append(ticket_leg_art(index - 1, art, y, height, accent2))
        rows.append(f'<text x="1003" y="{y + 38}" text-anchor="end" fill="#b8cbd5" font-size="20" font-weight="800">0{index}</text>')
        baseline = y + 24
        for name_line in names:
            baseline += 52
            rows.append(f'<text x="82" y="{baseline}" fill="#f5faff" font-size="46" font-weight="750">{esc(name_line)}</text>')
        for line_part in lines:
            baseline += 88
            rows.append(f'<text x="78" y="{baseline}" fill="{accent}" font-size="80" font-weight="900" letter-spacing="-2">{esc(line_part)}</text>')
        for market_line in markets:
            baseline += 40
            rows.append(f'<text x="82" y="{baseline}" fill="#c4d7e2" font-size="32" font-weight="550">{esc(market_line)}</text>')
        rows.append('</g>')
        y += height + 18
    height = y + 140
    price = f"{int(pick['odds']):+d}" if isinstance(pick.get('odds'), (int, float)) else '—'
    context = f"{len(set(pick.get('gameIds') or [])) or len(legs)} games"
    if (game or {}).get('kickoff'):
        try:
            from zoneinfo import ZoneInfo
            local = datetime.fromisoformat(game['kickoff'].replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York'))
            context += f' · {local:%a %b %-d}'
        except (ValueError, TypeError):
            pass
    chef = avatar_uri(CHEF) if avatar is None else avatar
    small_chef = badge(983, 66, 34, chef, '#54edbf') if chef else ''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{height}" viewBox="0 0 1080 {height}" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">
<defs><linearGradient id="ticketBg" x2="1" y2="1"><stop stop-color="{colors['bg']}"/><stop offset="1" stop-color="{colors['bg2']}"/></linearGradient><pattern id="ticketGrid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="{accent2}" stroke-opacity=".035"/></pattern></defs>
<rect width="1080" height="{height}" fill="url(#ticketBg)"/>
<rect width="1080" height="{height}" fill="url(#ticketGrid)"/>
<rect width="1080" height="8" fill="{accent}"/><rect x="0" y="8" width="360" height="4" fill="{accent2}"/>
{PAN.format(x=44, y=44, s=.48, c=accent)}
<text x="108" y="78" fill="#f5faff" font-size="32" font-weight="800" letter-spacing="5">KOOK’N</text>
{small_chef}
<text x="44" y="155" fill="#f5faff" font-size="46" font-weight="850">{esc(play_label(pick))}</text>
<text x="44" y="202" fill="#a7c1cf" font-size="29">{esc(context)}</text>
<text x="1036" y="158" text-anchor="end" fill="{accent}" font-size="66" font-weight="900">{esc(price)}</text>
<text x="1036" y="202" text-anchor="end" fill="#f5faff" font-size="30" font-weight="650">{esc(pick.get('book') or 'Book unavailable')}</text>
{''.join(rows)}
<text x="44" y="{y + 30}" fill="#f5faff" font-size="29" font-weight="750">{len(legs)} LEGS. ONE TICKET.</text>
<text x="44" y="{y + 72}" fill="#a7c1cf" font-size="26">Graded in public, win or lose.</text>
<text x="44" y="{y + 110}" fill="{accent}" font-size="25" font-weight="650">keenroudy.com/sports</text>
<text x="1036" y="{y + 110}" text-anchor="end" fill="#a7c1cf" font-size="22">21+ · Entertainment only</text>
</svg>'''


def ladder_track(step, completed, goal, complete=False):
    """A compact persistent path: finished rungs get checks, the next/current rung is called out, and future
    checkpoints stay anonymous because real prices determine how many steps the climb will take."""
    step, completed = max(1, int(step or 1)), max(0, int(completed or 0))
    visible = min(15, max(7, step + (0 if complete else 2)))
    left, right, y = 104, 850, 374
    gap = (right - left) / max(1, visible - 1)
    nodes = []
    for index in range(1, visible + 1):
        x = left + (index - 1) * gap
        if index <= completed:
            nodes.append(f'<g data-rung="{index}"><circle cx="{x:.1f}" cy="{y}" r="25" fill="#5eeaa4"/>'
                         f'<text x="{x:.1f}" y="{y + 9}" text-anchor="middle" fill="#07131d" font-size="28" font-weight="950">✓</text>'
                         f'<text x="{x:.1f}" y="{y + 52}" text-anchor="middle" fill="#5eeaa4" font-size="17" font-weight="850">{index}</text></g>')
        elif not complete and index == step:
            nodes.append(f'<g data-rung="{index}"><circle cx="{x:.1f}" cy="{y}" r="29" fill="#102b38" stroke="#2ed8ff" stroke-width="5"/>'
                         f'<text x="{x:.1f}" y="{y + 8}" text-anchor="middle" fill="#f4efe7" font-size="22" font-weight="950">{index}</text>'
                         f'<text x="{x:.1f}" y="{y - 45}" text-anchor="middle" fill="#2ed8ff" font-size="16" font-weight="900" letter-spacing="2">NEXT</text></g>')
        else:
            nodes.append(f'<circle cx="{x:.1f}" cy="{y}" r="13" fill="#718896" fill-opacity=".30"/>')
    goal_x = 970
    goal_mark = ('<circle cx="970" cy="374" r="29" fill="#5eeaa4"/>'
                 '<text x="970" y="383" text-anchor="middle" fill="#07131d" font-size="28" font-weight="950">✓</text>' if complete else
                 '<path d="M950 404v-74" stroke="#f4efe7" stroke-width="5" stroke-linecap="round"/>'
                 '<path d="M955 332h76l-16 23 16 23h-76z" fill="#5eeaa4"/>')
    filled = goal_x if complete else left + (right - left) * max(0, min(completed - 1, visible - 1)) / max(1, visible - 1)
    return (f'<g data-zone="ladder-track"><path d="M{left} {y}H{goal_x}" stroke="#718896" stroke-opacity=".28" stroke-width="10" stroke-linecap="round"/>'
            f'<path d="M{left} {y}H{filled:.1f}" stroke="#5eeaa4" stroke-width="10" stroke-linecap="round"/>'
            f'{"".join(nodes)}{goal_mark}<text x="970" y="442" text-anchor="middle" fill="#5eeaa4" font-size="20" font-weight="900">{esc(dollars(goal))}</text></g>')


def ladder_svg(pick, avatar=None):
    """The open rung: the whole climb is visible, prior rungs are checked, and the wager dominates."""
    info = pick.get('ladder') or {}
    if felt_enabled(pick):
        return felt_cards.climb_card(pick, info.get('run', 1), info.get('step', 1),
                                     info.get('stake', 0), info.get('payout', 0), info.get('banked', 0))
    legs = [short_leg(l.get('title')) for l in (pick.get('legs') or []) if l.get('title')]
    chef = avatar_uri(CHEF) if avatar is None else avatar
    run, step = int(info.get('run') or 1), int(info.get('step') or 1)
    start, goal = int(info.get('start') or LADDER[0]), int(info.get('goal') or LADDER[1])
    stake, returned, banked = int(info.get('stake') or 0), int(info.get('payout') or 0), int(info.get('banked') or 0)
    bank_this = int(info.get('bankThisWin') if info.get('bankThisWin') is not None else round(returned * .20))
    next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else returned - bank_this)
    price = f"{int(pick['odds']):+d}" if isinstance(pick.get('odds'), (int, float)) else ''
    book = str(pick.get('book') or '')
    leg_blocks = []
    for index, leg in enumerate(legs[:2]):
        y = 744 + index * 132
        leg_blocks.append(f'<rect x="74" y="{y}" width="932" height="108" rx="20" fill="#102330" stroke="#2c4c5b" stroke-width="2"/>'
                          f'<text x="108" y="{y + 67}" fill="{CREAM}" font-size="33" font-weight="850">{esc(fit(leg, 48))}</text>')
    chef_art = (f'<image href="{chef}" x="918" y="55" width="100" height="100" preserveAspectRatio="xMidYMid meet"/>') if chef else ''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">
<defs><linearGradient id="ladderBg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#07131d"/><stop offset="1" stop-color="#0a2b37"/></linearGradient></defs>
<rect width="1080" height="1350" fill="url(#ladderBg)"/><rect x="30" y="30" width="1020" height="1290" rx="34" fill="none" stroke="#5eeaa4" stroke-opacity=".48" stroke-width="3"/><rect x="30" y="30" width="1020" height="9" rx="4" fill="#5eeaa4"/>
{PAN.format(x=58, y=67, s=.44, c='#5eeaa4')}<text x="118" y="101" fill="{CREAM}" font-size="31" font-weight="900" letter-spacing="5">KOOK’N</text>
<text x="880" y="101" fill="#9eb8c7" font-size="21" font-weight="850" letter-spacing="3" text-anchor="end">CLIMB {run}</text>{chef_art}
<text x="56" y="210" fill="{CREAM}" font-size="66" font-weight="950">80/20 CLIMB</text>
<text x="60" y="265" fill="#5eeaa4" font-size="30" font-weight="900">{esc(dollars(start))} → {esc(dollars(goal))}</text>
<text x="1020" y="265" fill="#c2d3dc" font-size="25" font-weight="800" text-anchor="end">{esc(dollars(banked))} BANKED · {esc(dollars(stake))} RIDING</text>
{ladder_track(step, step - 1, goal)}
<rect x="56" y="500" width="968" height="660" rx="28" fill="#0e202c" stroke="#5eeaa4" stroke-width="3"/>
<text x="84" y="560" fill="#5eeaa4" font-size="26" font-weight="950" letter-spacing="3">STEP {step}</text>
<text x="996" y="560" fill="#c2d3dc" font-size="24" font-weight="800" text-anchor="end">{esc(price)} · {esc(book.upper())}</text>
<text x="84" y="660" fill="{CREAM}" font-size="78" font-weight="950">{esc(dollars(stake))} → {esc(dollars(returned))}</text>
{''.join(leg_blocks)}
<text x="84" y="1084" fill="#5eeaa4" font-size="29" font-weight="900">WIN: {esc(dollars(bank_this))} TO BANK · {esc(dollars(next_stake))} RIDES</text>
<text x="56" y="1280" fill="#5eeaa4" font-size="23" font-weight="800">keenroudy.com/sports</text><text x="1024" y="1280" fill="#9eb8c7" font-size="17" text-anchor="end">21+ · Entertainment only</text>
</svg>'''


def ladder_result_svg(pick, avatar=None):
    """The same climb after settlement: prior rungs stay checked and the next rung is obvious."""
    if felt_enabled(pick):
        return felt_cards.climb_result_card(pick)
    info = pick.get('ladder') or {}
    result = str(pick.get('result') or 'win').lower()
    run, step = int(info.get('run') or 1), int(info.get('step') or 1)
    start, goal = int(info.get('start') or LADDER[0]), int(info.get('goal') or LADDER[1])
    stake, returned = int(info.get('stake') or 0), int(info.get('payout') or 0)
    banked = int(info.get('banked') or 0)
    bank_this = int(info.get('bankThisWin') if info.get('bankThisWin') is not None else round(returned * .20))
    banked_after = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else banked + bank_this)
    next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else returned - bank_this)
    total = int(info.get('totalAfter') if info.get('totalAfter') is not None else banked_after + next_stake)
    complete = result == 'win' and total >= goal
    if complete:
        headline, hero, accent = 'CLIMB COMPLETE', f'{dollars(start)} → {dollars(total)}', '#5eeaa4'
        tiles = [('BANKED', dollars(banked_after)), ('STEPS', str(step)), ('NEXT CLIMB', dollars(start))]
        completed, active = step, step
    elif result == 'win':
        headline, hero, accent = f'STEP {step} CASHED', f'{dollars(stake)} → {dollars(returned)}', '#5eeaa4'
        tiles = [('BANKED', dollars(banked_after)), (f'STEP {step + 1}', f'{dollars(next_stake)} RIDES')]
        completed, active = step, step + 1
    elif result == 'loss':
        headline, hero, accent = f'STEP {step} MISSED', f'{dollars(banked)} SAVED', '#ff7283'
        tiles = [('BANKED', dollars(banked)), ('NEXT CLIMB', dollars(start))]
        completed, active = max(0, step - 1), 1
    else:
        headline, hero, accent = f'STEP {step} PUSH', f'{dollars(stake)} RIDES', '#68c1ff'
        tiles = [('BANKED', dollars(banked)), (f'STEP {step}', dollars(stake))]
        completed, active = max(0, step - 1), step

    actual = str(pick.get('actual') or '').lower()
    if actual.startswith('legs:'):
        leg_results = [part.strip() for part in actual.split(':', 1)[1].split(',')]
    elif result == 'win':
        leg_results = ['win'] * len(pick.get('legs') or [])
    else:
        leg_results = []
    leg_blocks = []
    for index, leg in enumerate((pick.get('legs') or [])[:2], 1):
        title = short_leg(str(leg.get('title') or 'Leg details unavailable'))
        wrapped = textwrap.wrap(title, width=42, break_long_words=False, break_on_hyphens=False) or [title]
        if len(wrapped) > 2:
            wrapped = [wrapped[0], fit(' '.join(wrapped[1:]), 48)]
        y = 584 + (index - 1) * 120
        leg_result = leg_results[index - 1] if index <= len(leg_results) else result
        mark = {'win': '✓', 'loss': '×', 'push': '–', 'void': '–'}.get(leg_result, '•')
        leg_accent = {'win': '#5eeaa4', 'loss': '#ff7283', 'push': '#68c1ff', 'void': '#68c1ff'}.get(leg_result, accent)
        leg_blocks += [
            f'<g data-zone="leg-{index}"><rect x="56" y="{y}" width="968" height="102" rx="20" fill="#102330" stroke="{leg_accent}" stroke-opacity=".30" stroke-width="2"/>',
            f'<circle cx="104" cy="{y + 55}" r="25" fill="{leg_accent}" fill-opacity=".14" stroke="{leg_accent}" stroke-width="3"/>',
            f'<text x="104" y="{y + 65}" text-anchor="middle" fill="{leg_accent}" font-size="31" font-weight="950">{mark}</text>',
        ]
        font = 31 if len(wrapped) == 1 else 27
        first_y = y + (65 if len(wrapped) == 1 else 45)
        leg_blocks += [f'<text x="154" y="{first_y + 34 * line}" fill="{CREAM}" font-size="{font}" font-weight="800">{esc(part)}</text>'
                       for line, part in enumerate(wrapped)]
        leg_blocks.append('</g>')

    tile_blocks = []
    for index, (label, value) in enumerate(tiles):
        width = 468 if len(tiles) == 2 else 304
        gap = 32 if len(tiles) == 2 else 24
        x = 56 + index * (width + gap)
        tile_blocks += [
            f'<g data-zone="accounting-{index}"><rect x="{x}" y="854" width="{width}" height="154" rx="22" fill="#102330" stroke="#284a5c" stroke-width="2"/>',
            f'<text x="{x + 26}" y="900" fill="#9eb8c7" font-size="18" font-weight="850" letter-spacing="2.5">{esc(label)}</text>',
            f'<text x="{x + 26}" y="972" fill="{accent}" font-size="48" font-weight="950">{esc(value)}</text></g>',
        ]
    chef = avatar_uri(CHEF) if avatar is None else avatar
    chef_art = (f'<image href="{chef}" x="918" y="55" width="100" height="100" preserveAspectRatio="xMidYMid meet"/>') if chef else ''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">
<defs>
  <linearGradient id="resultBg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#07131d"/><stop offset=".72" stop-color="#081b27"/><stop offset="1" stop-color="#0b3440"/></linearGradient>
</defs>
<rect width="1080" height="1350" fill="url(#resultBg)"/>
<rect x="28" y="28" width="1024" height="1294" rx="34" fill="none" stroke="{accent}" stroke-opacity=".44" stroke-width="3"/>
<rect x="28" y="28" width="1024" height="9" rx="4" fill="{accent}"/>
{PAN.format(x=56, y=64, s=.44, c=accent)}
<text x="116" y="97" fill="{CREAM}" font-size="31" font-weight="900" letter-spacing="5">KOOK’N</text>
<text x="870" y="97" text-anchor="end" fill="#9eb8c7" font-size="21" font-weight="850" letter-spacing="3">CLIMB {run}</text>
{chef_art}
<g data-zone="headline"><text x="56" y="210" fill="{accent}" font-size="67" font-weight="950">{esc(headline)}</text>
<text x="56" y="302" fill="{CREAM}" font-size="78" font-weight="950">{esc(hero)}</text></g>
{ladder_track(active, completed, goal, complete)}
{''.join(leg_blocks)}
{''.join(tile_blocks)}
<line x1="56" y1="1240" x2="1024" y2="1240" stroke="{accent}" stroke-opacity=".24" stroke-width="2"/>
<text x="56" y="1292" fill="{accent}" font-size="23" font-weight="800">keenroudy.com/sports</text><text x="1024" y="1292" text-anchor="end" fill="#9eb8c7" font-size="17">21+ · Entertainment only</text>
</svg>'''


def svg(pick, game=None, record=None, when=None, player_side=None, identities=None, avatar=None, featured=False, art=None):
    """The card. Every number on it is a field of the pick or the record handed in."""
    if play_kind(pick) == 'ladder':
        return ladder_svg(pick, avatar)
    if play_kind(pick) == 'parlay':
        return ticket_svg(pick, game, avatar, art)
    chef = avatar_uri(CHEF) if avatar is None else avatar
    side = side_for(pick, game, player_side)
    primary, alternate = team_colors(game, side, identities)
    other, _ = team_colors(game, 'away' if side == 'home' else 'home', identities)
    if play_kind(pick) == 'ladder':          # the ladder is the kitchen's own, whichever games carry the rung
        primary, other, alternate = HOUSE
    light = luminance(primary) > 0.55
    ink = INK if light else CREAM
    soft = shade(INK, 1.35) if light else shade(CREAM, 0.82)
    accent = alternate if abs(luminance(alternate) - luminance(primary)) > 0.25 else (INK if light else CREAM)
    title = display_title(pick, game)
    price = f"{int(pick['odds']):+d}" if isinstance(pick.get('odds'), (int, float)) else ''
    book = pick.get('book') or ''
    label = kicker(pick, featured)
    rung = play_kind(pick) == 'ladder'
    parlay = play_kind(pick) in ('parlay', 'ladder')
    legs = [str(l.get('title') or '') for l in (pick.get('legs') or []) if l.get('title')]
    if parlay:
        word = ('ladder' if rung else 'easy props' if pick.get('parlayType') == 'easyProps' else
                'lotto' if isinstance(pick.get('odds'), (int, float)) and pick['odds'] >= LOTTO else 'longshot')
        title = f"{len(pick.get('legs') or [])}-leg {word}"
    if rung:
        info = pick.get('ladder') or {}
        title = f"{dollars(info.get('stake'))} → {dollars(info.get('payout'))}"
    matchup = ''
    if game:
        away, home = game.get('away') or {}, game.get('home') or {}
        league = game.get('league') or str(pick.get('id', '')).split('-')[0]
        matchup = f"{team_label(away, league)} at {team_label(home, league)}".strip()
        if game.get('kickoff'):
            try:
                moment = datetime.fromisoformat(str(game['kickoff']).replace('Z', '+00:00'))
                from zoneinfo import ZoneInfo
                local = moment.astimezone(ZoneInfo('America/New_York'))
                matchup += f" · {local:%a %-I:%M %p} ET"
                if parlay:          # a ticket spans games: say how many and which day, not one game's name
                    matchup = f"{len(set(pick.get('gameIds') or [])) or len(legs)} games · {local:%a %b %-d}"
            except ValueError:
                pass
    ours = number_line(pick)
    units = units_label(pick)
    record_line = ''
    if record:
        record_line = f"Record {record.get('wins', 0)}-{record.get('losses', 0)}" + (f"-{record['pushes']}" if record.get('pushes') else '')
    lines = title_lines(title)
    # As big as fits beside the plate: the words end before the plate's rim, whatever the plate holds.
    title_size = max(36, min(66 if len(lines) == 1 else 50, int(TEXT_WIDTH / (0.56 * max(len(line) for line in lines)))))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">',
        '<defs>',
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{primary}"/><stop offset="0.72" stop-color="{shade(primary, 0.8)}"/><stop offset="1" stop-color="{other}"/></linearGradient>',
        '</defs>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>',
        # the plate the play is served on, the chef in it: the same on every card
        *plate(WIDTH - 250, HEIGHT // 2 + 20, chef, light, art),
        f'<rect x="36" y="36" width="{WIDTH - 72}" height="{HEIGHT - 72}" rx="30" fill="none" stroke="{accent}" stroke-opacity="0.55" stroke-width="3"/>',
        PAN.format(x=72, y=78, s=0.5, c=accent),
        f'<text x="140" y="116" fill="{ink}" font-size="34" font-weight="800" letter-spacing="5">KOOK’N</text>',
        f'<text x="{WIDTH - 80}" y="116" fill="{soft}" font-size="26" font-weight="700" letter-spacing="3" text-anchor="end">{esc(label)}</text>',
        f'<text x="80" y="212" fill="{soft}" font-size="32">{esc(matchup)}</text>',
        f'<text x="80" y="262" fill="{accent}" font-size="24" font-weight="700" letter-spacing="4">'
        f'{"THE CLIMB: " + esc(dollars(LADDER[0])) + " TO " + esc(dollars(LADDER[1])) if rung else "BEST BET"}</text>',
        *[f'<text x="80" y="{262 + (title_size + 6) * (i + 1) - 2}" fill="{ink}" font-size="{title_size}" font-weight="800">{esc(text)}</text>'
          for i, text in enumerate(lines)],
        *(ladder_body(pick.get('ladder') or {}, legs, price, book, ink, soft, accent, title_size) if rung else
          parlay_body(legs, price, book, units, ink, soft, accent, title_size) if parlay else [
        f'<text x="80" y="418" fill="{soft}" font-size="26" letter-spacing="1">Book</text>',
        f'<text x="80" y="470" fill="{ink}" font-size="50" font-weight="800">{esc(price)}<tspan fill="{soft}" font-size="34" font-weight="600" dx="18">{esc(book)}</tspan></text>',
        f'<text x="80" y="530" fill="{ink}" font-size="32">{esc(ours)}</text>']),
        f'<text x="80" y="{HEIGHT - 62}" fill="{ink}" font-size="26" font-weight="700">Graded in public, win or lose. <tspan fill="{soft}" font-weight="400">keenroudy.com/sports</tspan></text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 62}" fill="{soft}" font-size="19" text-anchor="end">21+ · Entertainment only</text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 94}" fill="{soft}" font-size="22" text-anchor="end">{esc(record_line)}</text>' if record_line else '',
        '</svg>']
    return '\n'.join(parts)


HOUSE = ('#08131d', '#10313a', '#5eeaa4')      # Kook'n navy and mint, for cards that are not tied to one team
RESULT_MARKS = {'win': ('W', '#6fdc8c'), 'loss': ('L', '#ff7a6b'), 'push': ('P', None), 'void': ('P', None)}


def modern_svg(pick, game=None, record=None, when=None, player_side=None, identities=None, avatar=None, featured=False, art=None):
    """2026-10 visual system: full portraits, exact big lines, generous fixed zones. No new facts."""
    if play_kind(pick) in ('ladder', 'parlay'):
        return svg(pick, game, record, when, player_side, identities, avatar, featured, art)
    if felt_enabled(pick, when):
        display = dict(pick, displayTitle=display_title(pick, game), _when=felt_when(game), _number=number_line(pick))
        if isinstance(record, dict):
            season = f"{record.get('wins', 0)}–{record.get('losses', 0)}"
            if record.get('pushes'):
                season += f"–{record['pushes']}"
        else:
            season = record
        return felt_cards.play_card(display, felt_game(game), season, featured, art)
    theme = ticket_style(pick)
    accent, ink, dim = theme['accent'], '#f5faff', '#aac0cf'
    name, selection, market = ticket_leg_parts(display_title(pick, game))
    def lines(value, x, y, width, size, color, weight=750, max_lines=None):
        words = textwrap.wrap(str(value or ''), width=max(12, int(width/(size*.56))), break_long_words=True, break_on_hyphens=False)
        while max_lines and len(words) > max_lines and size > 16:
            size -= 1
            words = textwrap.wrap(str(value or ''), width=max(12, int(width/(size*.56))), break_long_words=True, break_on_hyphens=False)
        return ''.join(f'<text x="{x}" y="{y+i*(size+10)}" fill="{color}" font-size="{size}" font-weight="{weight}">{esc(word)}</text>' for i,word in enumerate(words))
    picture = ''
    if (art or {}).get('kind') == 'photo':
        picture = f'<image href="{esc(art["uri"])}" x="550" y="145" width="500" height="365" preserveAspectRatio="xMidYMax meet"/>'
    elif (art or {}).get('kind') == 'logos':
        picture = ''.join(f'<image href="{esc(uri)}" x="{580+i*210}" y="210" width="200" height="200" preserveAspectRatio="xMidYMid meet"/>' for i,uri in enumerate(art['uris']))
    else:
        chef = avatar_uri(CHEF) if avatar is None else avatar
        if chef: picture = f'<image href="{esc(chef)}" x="710" y="205" width="260" height="270" preserveAspectRatio="xMidYMid meet" opacity=".8"/>'
    matchup = ''
    if game:
        matchup = f"{team_label(game.get('away') or {}, game.get('league'))} at {team_label(game.get('home') or {}, game.get('league'))}"
        if game.get('kickoff'):
            try:
                from zoneinfo import ZoneInfo
                dt = datetime.fromisoformat(game['kickoff'].replace('Z','+00:00')).astimezone(ZoneInfo('America/Indiana/Indianapolis'))
                matchup += f' · {dt:%a %-I:%M %p} ET'
            except (ValueError,TypeError): pass
    price = f"{int(pick['odds']):+d}" if isinstance(pick.get('odds'),(int,float)) else 'No price'
    main_size = min(106, max(48, int(950/(max(1,len(selection))*.59))))
    name_size = min(58,max(36,int(470/(max(1,min(20,len(name)))*.56))))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">
<defs><linearGradient id="modern-bg" x2="1" y2="1"><stop stop-color="{theme['bg']}"/><stop offset="1" stop-color="{theme['bg2']}"/></linearGradient><linearGradient id="portrait-fade" x2="0" y2="1"><stop stop-color="{theme['bg']}" stop-opacity="0"/><stop offset="1" stop-color="{theme['bg']}"/></linearGradient></defs>
<rect width="1080" height="1350" fill="url(#modern-bg)"/><path d="M800 0L1080 0L1080 530L470 530Z" fill="{accent}" opacity=".06"/>
{PAN.format(x=48,y=50,s=.45,c=accent)}<text x="115" y="86" fill="{ink}" font-size="34" font-weight="850" letter-spacing="5">KOOK’N</text>
<text x="1024" y="84" fill="{dim}" font-size="21" text-anchor="end" letter-spacing="3">THE LINE</text>
{picture}<rect x="540" y="430" width="540" height="85" fill="url(#portrait-fade)"/>
{lines('HOT PLATE (POTD)' if featured else play_label(pick),56,170,490,23,accent)}
{lines(name,56,254,475,name_size,ink,850,max_lines=3)}
<path d="M56 522H1024" stroke="{accent}" stroke-width="3"/>
<g data-zone="selection">{lines(selection,56,660,970,main_size,accent,900,max_lines=1)}{lines(market,60,728,940,38,ink,max_lines=1)}</g>
{lines(matchup,60,820,945,27,dim,500,max_lines=2)}
<rect x="56" y="886" width="460" height="215" rx="20" fill="{theme['row']}" stroke="{theme['edge']}"/>
<text x="82" y="927" fill="{dim}" font-size="20" letter-spacing="3">POSTED PRICE</text><text x="82" y="1007" fill="{ink}" font-size="72" font-weight="850">{esc(price)}</text>
{lines(pick.get('book') or '',82,1060,410,28,dim,max_lines=1)}
<rect x="536" y="886" width="488" height="215" rx="20" fill="{theme['row']}" stroke="{theme['edge']}"/>
<text x="562" y="927" fill="{dim}" font-size="20" letter-spacing="3">OUR NUMBER</text>
{lines(number_line(pick) or 'No projection shown',562,984,426,31,ink,max_lines=3)}
<text x="56" y="1202" fill="{ink}" font-size="28" font-weight="750">Every play graded in public.</text>
<text x="56" y="1252" fill="{accent}" font-size="27" font-weight="700">keenroudy.com/sports</text>
<text x="56" y="1304" fill="{dim}" font-size="19">21+ · Entertainment only</text>
</svg>'''


def receipt_svg(receipt, avatar=None):
    """A tall, shareable result report: the record leads, then every play gets room for its final or parlay sweat."""
    if felt_enabled(receipt):
        return felt_cards.receipt_from_existing(receipt)
    chef = avatar_uri(CHEF) if avatar is None else avatar
    primary, other, accent = HOUSE
    ink, soft, raised = CREAM, '#9eb1bf', '#102330'
    rows = receipt.get('rows') or []
    shown = rows if len(rows) <= 6 else rows[:5]
    wins = sum(1 for row in rows if row and row[0] == 'win')
    losses = sum(1 for row in rows if row and row[0] == 'loss')
    # Weekly cards have category rows instead of W/L rows, so their title supplies the overall record.
    if not wins and not losses:
        try:
            title_record = [int(piece) for piece in str(receipt.get('title') or '').split('-')[:2]]
            wins, losses = title_record
        except (TypeError, ValueError):
            pass
    if losses > wins:
        primary, other, accent = '#151323', '#3a162d', '#ff7283'
    elif wins > losses:
        primary, other, accent = '#071a20', '#0d4a43', '#5eeaa4'
    else:
        primary, other, accent = '#0a1828', '#173856', '#68c1ff'
    single = len(shown) == 1 and shown[0][0] in RESULT_MARKS
    top = 555 if single else 475
    row_h = 230 if single else min(176, 690 // max(len(shown), 1))
    box_h = row_h - 12
    body = []
    for i, row in enumerate(shown):
        result, text = row[:2]
        detail = row[2] if len(row) > 2 else ''
        y = top + row_h * i
        tone = RESULT_MARKS.get(result, ('', accent))[1] if result else accent
        middle = y + box_h // 2
        body.append(f'<rect x="56" y="{y}" width="968" height="{box_h}" rx="18" fill="{raised}" stroke="{tone or accent}" stroke-opacity=".28" stroke-width="2"/>')
        if result is None:
            size, limit = (30, 42) if len(text) <= 42 else (25, 55)
            body.append(f'<circle cx="91" cy="{middle}" r="13" fill="{accent}"/>')
            body.append(f'<text x="122" y="{middle + 10}" fill="{ink}" font-size="{size}" font-weight="750">{esc(fit(text, limit))}</text>')
            continue
        mark, colour = RESULT_MARKS.get(result, ('?', None))
        size, limit = ((35, 39) if len(text) <= 39 else (28, 50)) if single else ((28, 45) if len(text) <= 45 else (23, 57))
        circle_x, circle_r = (112, 38) if single else (98, 27)
        text_x = 178 if single else 144
        body.append(f'<circle cx="{circle_x}" cy="{middle}" r="{circle_r}" fill="{colour or soft}" fill-opacity=".15" stroke="{colour or soft}" stroke-width="3"/>')
        body.append(f'<text x="{circle_x}" y="{middle + (13 if single else 9)}" fill="{colour or soft}" font-size="{38 if single else 27}" font-weight="900" text-anchor="middle">{mark}</text>')
        body.append(f'<text x="{text_x}" y="{middle + (-10 if detail else 12)}" fill="{ink}" font-size="{size}" font-weight="800">{esc(fit(text, limit))}</text>')
        if detail:
            body.append(f'<text x="{text_x}" y="{middle + (38 if single else 29)}" fill="{soft}" font-size="{25 if single else 20}" font-weight="600">{esc(fit(detail, 55 if single else 70))}</text>')
    if len(rows) > len(shown):
        body.append(f'<text x="540" y="{top + row_h * len(shown) + 18}" fill="{soft}" font-size="21" text-anchor="middle">+ {len(rows) - len(shown)} more graded on the site</text>')
    if single:
        hero = 'ALL GREEN.' if wins and not losses else 'BACK TO WORK.' if losses and not wins else 'THE RECEIPT.'
        sub = 'The win is on the record.' if wins and not losses else 'The miss is on the record.' if losses and not wins else 'Every result stays on the record.'
        body += [
            f'<rect x="56" y="838" width="968" height="154" rx="24" fill="{accent}" fill-opacity=".10" stroke="{accent}" stroke-opacity=".55" stroke-width="3"/>',
            f'<text x="88" y="903" fill="{accent}" font-size="54" font-weight="950" letter-spacing="-1">{hero}</text>',
            f'<text x="88" y="956" fill="{ink}" font-size="25" font-weight="700">{sub}</text>',
        ]
    summary = receipt.get('summary') or {}
    accounting = receipt.get('accounting') or {}
    straight, fun = summary.get('straight'), summary.get('fun')
    chips = []
    if accounting.get('assumed') or accounting.get('promotionalCredits'):
        chips.append(f'<text x="56" y="460" fill="{soft}" font-size="17">Captured: {esc(accounting.get("captured") or "none")} · assumed history: {esc(accounting.get("assumed") or "none")} · promo credits: {accounting.get("promotionalCredits", 0)}</text>')
    if straight:
        chips += [f'<rect x="56" y="366" width="330" height="76" rx="16" fill="{raised}" stroke="#284253" stroke-width="2"/>',
                  f'<text x="78" y="395" fill="{soft}" font-size="17" font-weight="800" letter-spacing="2">STRAIGHT PLAYS</text>',
                  f'<text x="78" y="428" fill="{ink}" font-size="31" font-weight="900">{esc(straight)}</text>']
    if fun:
        x = 408 if straight else 56
        chips += [f'<rect x="{x}" y="366" width="350" height="76" rx="16" fill="{raised}" stroke="{accent}" stroke-opacity=".35" stroke-width="2"/>',
                  f'<text x="{x + 22}" y="395" fill="{soft}" font-size="17" font-weight="800" letter-spacing="2">FUN TICKETS · 0.25U</text>',
                  f'<text x="{x + 22}" y="428" fill="{ink}" font-size="31" font-weight="900">{esc(fun)}</text>']
    chef_art = (f'<defs><clipPath id="receiptChef"><circle cx="930" cy="176" r="88"/></clipPath></defs>'
                f'<circle cx="930" cy="176" r="98" fill="{accent}" fill-opacity=".09" stroke="{accent}" stroke-opacity=".55" stroke-width="3"/>'
                f'<image href="{chef}" x="842" y="88" width="176" height="176" clip-path="url(#receiptChef)" preserveAspectRatio="xMidYMid meet"/>') if chef else ''
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">',
        '<defs>',
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{primary}"/><stop offset="0.68" stop-color="#071018"/><stop offset="1" stop-color="{other}"/></linearGradient>',
        '<pattern id="dots" width="34" height="34" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.4" fill="#5eeaa4" fill-opacity=".07"/></pattern>',
        '</defs>',
        '<rect width="1080" height="1350" fill="url(#bg)"/>',
        '<rect width="1080" height="1350" fill="url(#dots)"/>',
        f'<rect x="28" y="28" width="1024" height="1294" rx="34" fill="none" stroke="{accent}" stroke-opacity=".42" stroke-width="3"/>',
        f'<rect x="28" y="28" width="1024" height="9" rx="4" fill="{accent}"/>',
        PAN.format(x=56, y=76, s=0.44, c=accent),
        f'<text x="116" y="109" fill="{ink}" font-size="31" font-weight="900" letter-spacing="5">KOOK’N</text>',
        f'<text x="790" y="106" fill="{soft}" font-size="18" font-weight="800" letter-spacing="4" text-anchor="end">FINAL REPORT</text>',
        f'<text x="56" y="171" fill="{accent}" font-size="22" font-weight="850" letter-spacing="5">{esc(receipt.get("label") or "FINAL REPORT")}</text>',
        f'<text x="56" y="218" fill="{soft}" font-size="27" font-weight="650">{esc(receipt.get("when") or "")}</text>',
        f'<text x="56" y="324" fill="{ink}" font-size="{112 if len(receipt.get("title") or "") <= 8 else 68 if len(receipt.get("title") or "") <= 18 else 50}" font-weight="950" letter-spacing="-3">{esc(receipt.get("title") or "")}</text>',
        chef_art,
        *chips,
        *body,
        f'<line x1="56" y1="1227" x2="1024" y2="1227" stroke="{accent}" stroke-opacity=".23" stroke-width="2"/>',
        f'<text x="56" y="1270" fill="{ink}" font-size="24" font-weight="800">KOOK’N RESULTS</text>',
        f'<text x="56" y="1300" fill="{soft}" font-size="20">Full record + details at keenroudy.com/sports</text>',
        f'<text x="1024" y="1300" fill="{soft}" font-size="17" text-anchor="end">21+ · Entertainment only</text>',
        '</svg>']
    return '\n'.join(parts)


def title_lines(title, width=26, limit=22):
    """The play on one line, or on two when it is long: a player's name above the line he is on
    ("Courtland Sutton" / "OVER 3.5 receptions"), else split at the word nearest the middle."""
    if len(title) <= limit:
        return [title]
    words = title.split()
    cut = next((i for i, w in enumerate(words) if w.lower() in ('over', 'under') and i > 0), None)
    if cut is None:
        best, cut = None, 1
        for i in range(1, len(words)):
            gap = abs(len(' '.join(words[:i])) - len(' '.join(words[i:])))
            if best is None or gap < best:
                best, cut = gap, i
    return [fit(' '.join(words[:cut]), width + 6), fit(' '.join(words[cut:]), width + 6)]


def parlay_body(legs, price, book, units, ink, soft, accent, title_size):
    """A parlay in the same frame as every other card: its legs where a single play's numbers go, and its
    price on the "Book" line."""
    top = 262 + title_size + 4 + 44
    shown = legs if len(legs) <= 5 else legs[:4]
    rows = [f'<text x="80" y="{top + 34 * i}" fill="{ink}" font-size="26">• {esc(fit(leg, 40))}</text>' for i, leg in enumerate(shown)]
    if len(legs) > len(shown):
        rows.append(f'<text x="80" y="{top + 34 * len(shown)}" fill="{soft}" font-size="24">and {len(legs) - len(shown)} more</text>')
    rows.append(f'<text x="80" y="562" fill="{soft}" font-size="26" letter-spacing="1">Book <tspan fill="{ink}" font-size="44" '
                f'font-weight="800" letter-spacing="0" dx="8">{esc(price)}</tspan><tspan fill="{soft}" font-size="30" font-weight="600" '
                f'letter-spacing="0" dx="14">{esc(book)}</tspan></text>')
    return rows


LADDER = (50, 1000)          # the ladder's start and goal in dollars (scripts/ladder.py START, GOAL)


def dollars(amount):
    try:
        return f'${int(amount):,}'
    except (TypeError, ValueError):
        return ''


def ladder_body(info, legs, price, book, ink, soft, accent, title_size):
    """A rung in the same frame: its two legs, the climb from $50 to $1,000 as a bar (a log scale, so every doubling is
    the same step), filled to the stake riding with what a win makes it shaded after, and the price."""
    top = 262 + title_size + 4 + 44
    rows = [f'<text x="80" y="{top + 34 * i}" fill="{ink}" font-size="26">• {esc(fit(leg, 40))}</text>' for i, leg in enumerate(legs[:3])]
    x0, x1, y = 80, 660, top + 34 * len(legs[:3]) + 18

    def at(amount):
        try:
            share = math.log(max(float(amount), LADDER[0]) / LADDER[0]) / math.log(LADDER[1] / LADDER[0])
        except (TypeError, ValueError):
            share = 0.0
        return x0 + (x1 - x0) * max(0.0, min(1.0, share))

    now_x = at((info.get('banked') or 0) + (info.get('stake') or 0))
    win_x = at(info.get('totalAfter') if info.get('totalAfter') is not None else
               (info.get('banked') or 0) + (info.get('payout') or 0))
    rows += [f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="14" rx="7" fill="{soft}" fill-opacity="0.28"/>',
             f'<rect x="{x0}" y="{y}" width="{max(14.0, win_x - x0):.0f}" height="14" rx="7" fill="{accent}" fill-opacity="0.45"/>',
             f'<rect x="{x0}" y="{y}" width="{max(14.0, now_x - x0):.0f}" height="14" rx="7" fill="{accent}"/>',
             f'<text x="{x0}" y="{y + 42}" fill="{soft}" font-size="22">{esc(dollars(LADDER[0]))}</text>',
             f'<text x="{x1}" y="{y + 42}" fill="{soft}" font-size="22" text-anchor="end">{esc(dollars(LADDER[1]))}</text>',
             f'<text x="80" y="562" fill="{soft}" font-size="26" letter-spacing="1">Book <tspan fill="{ink}" font-size="44" '
             f'font-weight="800" letter-spacing="0" dx="8">{esc(price)}</tspan><tspan fill="{soft}" font-size="30" font-weight="600" '
             f'letter-spacing="0" dx="14">{esc(book)}</tspan></text>']
    return rows


def render(svg_text, out, chrome=None, timeout=45, size=None):
    """Rasterize the SVG to a PNG with the machine's headless browser. Raises when there is none.

    Chrome writes the screenshot and then, on this machine, does not exit on its own, so the file is
    watched for and the browser is stopped once the file has stopped growing.
    """
    import time
    chrome = chrome or chrome_path()
    if not chrome:
        raise RuntimeError('no headless browser on this machine; set KEENROUDY_CHROME to a Chrome or Chromium binary')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / 'card.html'
        page.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;background:{NEUTRAL}}}'
                        f'svg{{display:block}}</style></head><body>{svg_text}</body></html>', encoding='utf-8')
        dimensions = size or svg_size(svg_text)
        process = subprocess.Popen([chrome, '--headless', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                                    '--disable-extensions', '--no-first-run', '--virtual-time-budget=2000',
                                    f'--user-data-dir={folder}/profile', '--window-size={},{}'.format(*dimensions),
                                    f'--screenshot={out}', page.as_uri()],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline, last_size, stable = time.time() + timeout, -1, 0
        try:
            while time.time() < deadline:
                if process.poll() is not None and out.exists():
                    break
                size = out.stat().st_size if out.exists() else -1
                stable = stable + 1 if size > 0 and size == last_size else 0
                last_size = size
                if stable >= 3:            # three checks without growth: the file is complete
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError('browser render failed: no screenshot was written')
    return out


def svg_size(svg_text):
    """The SVG's declared pixel dimensions, so tall house cards are not cropped by the rasterizer."""
    match = re.search(r'<svg\b[^>]*\bwidth="(\d+)"[^>]*\bheight="(\d+)"', svg_text)
    return (int(match.group(1)), int(match.group(2))) if match else (WIDTH, HEIGHT)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('pick_id')
    parser.add_argument('--out', help='PNG path; default the sports config folder')
    parser.add_argument('--svg', action='store_true', help='print the SVG instead of rendering')
    parser.add_argument('--featured', action='store_true', help='preview the Pick of the Day treatment')
    parser.add_argument('--ticket-style', type=int, choices=range(len(TICKET_STYLES)), help='preview one ticket treatment (0-2)')
    args = parser.parse_args(argv)
    import gates
    stores = gates.Stores()
    ctx = stores.as_of(datetime.now(timezone.utc))
    pick = ctx.first.get(args.pick_id)
    if not pick:
        sys.exit(f'{args.pick_id} is not in research/')
    game = ctx.games.get((pick.get('gameIds') or [None])[0])
    player_side = None
    if pick.get('athleteId') and game:
        team = ctx.player_team.get(str(pick['athleteId']))
        player_side = 'home' if team == str(game['home']['id']) else 'away' if team == str(game['away']['id']) else None
    card_art = ticket_art(pick, ctx.games, ctx.player_team) if play_kind(pick) == 'parlay' else artwork(pick, game)
    text = (ticket_svg(pick, game, art=card_art, style=args.ticket_style) if play_kind(pick) == 'parlay' and args.ticket_style is not None
            else modern_svg(pick, game, player_side=player_side, art=card_art, featured=args.featured))
    if args.svg:
        if args.out:
            Path(args.out).write_text(text)
            print(args.out)
        else:
            print(text)
        return 0
    out = Path(args.out) if args.out else Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy')) / 'x-drafts' / f'{args.pick_id}.png'
    print(render(text, out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
