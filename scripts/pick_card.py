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
import html
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pricing

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1200, 675
NEUTRAL = '#2b3440'
CREAM, INK = '#f6f1e6', '#141414'
CHROME_CANDIDATES = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                     '/Applications/Chromium.app/Contents/MacOS/Chromium', 'google-chrome', 'google-chrome-stable',
                     'chromium', 'chromium-browser')


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
HEADSHOT = 'https://a.espncdn.com/i/headshots/nfl/players/full/{athlete}.png'
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


def artwork(pick, game, fetch=None):
    """{'kind': 'photo', 'uri'} for an NFL player prop, {'kind': 'logos', 'uris'} for a game line (the side's logo
    on a spread, both teams' on a total), or None for the chef: a parlay, a failed fetch, or the switch off."""
    if not CARD_ART or not game or play_kind(pick) in ('parlay', 'ladder'):
        return None
    fetch = fetch or fetch_data_uri
    league = game.get('league') or str(pick.get('id', '')).split('-')[0]
    if play_kind(pick) == 'player':
        if league != 'NFL' or not pick.get('athleteId'):
            return None
        uri = fetch(HEADSHOT.format(athlete=pick['athleteId']))
        return {'kind': 'photo', 'uri': uri} if uri else None
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
    """What we make it, the way a bettor says it: "We have it at 47." for a total or a player, "We have Duke by 14." for
    a side. Empty without a projection."""
    projection = pick.get('projection')
    if not isinstance(projection, (int, float)) or pick.get('legs'):
        return ''
    direction = str(pick.get('direction') or '').lower()
    if pick.get('marketType') == 'spread' and not (pick.get('athleteId') or pick.get('market')) and game and direction in ('home', 'away'):
        league = game.get('league') or str(pick.get('id', '')).split('-')[0]
        side = game.get(direction) or {}
        other = game.get('away' if direction == 'home' else 'home') or {}
        if abs(projection) < 0.5:
            return 'We have it even.'
        team = side if projection < 0 else other          # the side's own number: -14 is that side by 14
        return f"We have {team_label(team, league)} by {int(round(abs(projection)))}."
    return f'We have it at {plain_number(projection)}.'


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
        return f"80/20 BANKROLL LADDER · STEP {(pick.get('ladder') or {}).get('step', 1)}"
    label = play_label(pick)
    if featured:
        return f'PICK OF THE DAY · {label}'
    return f'{label} · FAVORITE' if pick.get('favorite') is True and play_kind(pick) != 'parlay' else label


TEXT_WIDTH = 640     # pixels the title may use: from the left margin to short of the plate


def ladder_svg(pick, avatar=None):
    """A tall, winding 80/20 progress card. Only the current rung is priced; future checkpoints stay deliberately
    blank because the climb has no promised number of steps or returns."""
    info = pick.get('ladder') or {}
    legs = [short_leg(l.get('title')) for l in (pick.get('legs') or []) if l.get('title')]
    chef = avatar_uri(CHEF) if avatar is None else avatar
    run, step = int(info.get('run') or 1), int(info.get('step') or 1)
    start, goal = dollars(info.get('start') or LADDER[0]), dollars(info.get('goal') or LADDER[1])
    stake_, payout_ = dollars(info.get('stake')), dollars(info.get('payout'))
    banked = int(info.get('banked') or 0)
    returned = int(info.get('payout') or 0)
    bank_this = int(info.get('bankThisWin') if info.get('bankThisWin') is not None else round(returned * .20))
    banked_after = int(info.get('bankedAfter') if info.get('bankedAfter') is not None else banked + bank_this)
    next_stake = int(info.get('nextStake') if info.get('nextStake') is not None else returned - bank_this)
    price = f"{int(pick['odds']):+d}" if isinstance(pick.get('odds'), (int, float)) else ''
    book = str(pick.get('book') or '')
    progress = f'{dollars(banked)} BANKED · {stake_} RIDING'
    leg_rows = ''.join(f'<text x="330" y="{590 + 38 * i}" fill="{CREAM}" font-size="25" font-weight="650">• {esc(fit(leg, 38))}</text>'
                       for i, leg in enumerate(legs[:2]))
    chef_art = (f'<image href="{chef}" x="768" y="988" width="224" height="224" '
                'preserveAspectRatio="xMidYMid meet" clip-path="url(#chefClip)"/>') if chef else ''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">
<defs>
  <linearGradient id="ladderBg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a1c14"/><stop offset="0.72" stop-color="#17100c"/><stop offset="1" stop-color="#3d2a1d"/></linearGradient>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="10" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <clipPath id="chefClip"><circle cx="880" cy="1100" r="112"/></clipPath>
</defs>
<rect width="1080" height="1350" fill="url(#ladderBg)"/>
<rect x="34" y="34" width="1012" height="1282" rx="34" fill="none" stroke="#f28c28" stroke-opacity=".58" stroke-width="3"/>
<circle cx="91" cy="94" r="14" fill="none" stroke="#f28c28" stroke-width="5"/><circle cx="91" cy="94" r="5" fill="#f28c28"/><path d="M105 94h28" stroke="#f28c28" stroke-width="5" stroke-linecap="round"/>
<text x="142" y="116" fill="{CREAM}" font-size="34" font-weight="800" letter-spacing="5">KOOK’N</text>
<text x="986" y="112" fill="#d8d1c6" font-size="22" font-weight="700" letter-spacing="3" text-anchor="end">CLIMB {run}</text>
<text x="540" y="190" fill="{CREAM}" font-size="49" font-weight="900" text-anchor="middle" letter-spacing="2">THE 80/20 BANKROLL LADDER</text>
<text x="540" y="232" fill="#f28c28" font-size="27" font-weight="800" text-anchor="middle" letter-spacing="4">BANK 20 · RIDE 80 · {esc(goal)} GOAL</text>

<path d="M140 315 H810 Q920 315 920 425 Q920 535 810 535 H270 Q160 535 160 645 Q160 755 270 755 H810 Q920 755 920 865 Q920 975 810 975 H270 Q160 975 160 1085 Q160 1185 270 1185 H690" fill="none" stroke="#756b62" stroke-opacity=".55" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M140 315 H810 Q920 315 920 425 Q920 535 810 535 H270" fill="none" stroke="#f28c28" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M140 315 H810 Q920 315 920 425 Q920 535 810 535 H270 Q160 535 160 645 Q160 755 270 755 H810 Q920 755 920 865 Q920 975 810 975 H270 Q160 975 160 1085 Q160 1185 270 1185 H690" fill="none" stroke="{CREAM}" stroke-opacity=".46" stroke-width="3" stroke-dasharray="3 24" stroke-linecap="round"/>

<circle cx="140" cy="315" r="34" fill="#f28c28" stroke="{CREAM}" stroke-width="4"/><text x="140" y="323" fill="#17100c" font-size="22" font-weight="900" text-anchor="middle">{esc(start)}</text><text x="140" y="375" fill="#d8d1c6" font-size="20" font-weight="700" text-anchor="middle" letter-spacing="2">START</text>
<rect x="510" y="273" width="358" height="84" rx="17" fill="#173a2a" stroke="#6fdc8c" stroke-opacity=".7" stroke-width="2"/>
<text x="536" y="307" fill="#a6e8b8" font-size="18" font-weight="800" letter-spacing="2">CLIMB TO DATE</text><text x="536" y="338" fill="{CREAM}" font-size="25" font-weight="900">{esc(progress)}</text>

<circle cx="270" cy="535" r="41" fill="#f28c28" fill-opacity=".22" stroke="#f28c28" stroke-width="5" filter="url(#glow)"/><circle cx="270" cy="535" r="12" fill="#f28c28"/>
<rect x="300" y="478" width="586" height="220" rx="20" fill="#3b2617" stroke="#f28c28" stroke-width="3"/>
<text x="330" y="518" fill="#f28c28" font-size="20" font-weight="900" letter-spacing="3">STEP {step} · TODAY</text>
<text x="850" y="518" fill="#d8d1c6" font-size="21" font-weight="700" text-anchor="end">{esc(price)} AT {esc(book.upper())}</text>
<text x="330" y="561" fill="{CREAM}" font-size="36" font-weight="900">{esc(stake_)} → {esc(payout_)}</text>
{leg_rows}
<text x="330" y="675" fill="#a6e8b8" font-size="21" font-weight="850">WIN: BANK {esc(dollars(bank_this))} · RIDE {esc(dollars(next_stake))}</text>

<g fill="#756b62" stroke="#d8d1c6" stroke-opacity=".55" stroke-width="3"><circle cx="520" cy="755" r="25"/><circle cx="810" cy="755" r="25"/><circle cx="650" cy="975" r="25"/><circle cx="270" cy="975" r="25"/><circle cx="320" cy="1185" r="25"/></g>
<g fill="#d8d1c6" fill-opacity=".72"><circle cx="520" cy="755" r="5"/><circle cx="810" cy="755" r="5"/><circle cx="650" cy="975" r="5"/><circle cx="270" cy="975" r="5"/><circle cx="320" cy="1185" r="5"/></g>
<text x="665" y="730" fill="#d8d1c6" fill-opacity=".65" font-size="21" font-weight="700" text-anchor="middle" letter-spacing="2">FUTURE RUNGS UNLOCK ONE AT A TIME</text>
<path d="M690 1185v-88" stroke="{CREAM}" stroke-width="6" stroke-linecap="round"/><path d="M696 1098h110l-22 30 22 30H696z" fill="#f28c28"/><text x="750" y="1136" fill="#17100c" font-size="22" font-weight="900" text-anchor="middle">{esc(goal)}</text><text x="690" y="1225" fill="#f28c28" font-size="23" font-weight="900" text-anchor="middle" letter-spacing="3">THE GOAL</text>
<circle cx="880" cy="1100" r="134" fill="{CREAM}" fill-opacity=".07"/><circle cx="880" cy="1100" r="115" fill="{CREAM}" fill-opacity=".09" stroke="{CREAM}" stroke-opacity=".4" stroke-width="3"/>{chef_art}
<text x="76" y="1260" fill="{CREAM}" font-size="22" font-weight="750">Bank 20% of every return.</text><text x="76" y="1292" fill="{CREAM}" font-size="22" font-weight="750">Ride 80%. A miss cannot take the bank.</text><text x="1002" y="1260" fill="#d8d1c6" font-size="22" text-anchor="end">keenroudy.com/sports</text><text x="1002" y="1292" fill="#a69d92" font-size="17" text-anchor="end">Entertainment only. Not advice.</text>
</svg>'''


def svg(pick, game=None, record=None, when=None, player_side=None, identities=None, avatar=None, featured=False, art=None):
    """The card. Every number on it is a field of the pick or the record handed in."""
    if play_kind(pick) == 'ladder':
        return ladder_svg(pick, avatar)
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
        f'{"THE CLIMB: " + esc(dollars(LADDER[0])) + " TO " + esc(dollars(LADDER[1])) if rung else "TODAY’S PLATE"}</text>',
        *[f'<text x="80" y="{262 + (title_size + 6) * (i + 1) - 2}" fill="{ink}" font-size="{title_size}" font-weight="800">{esc(text)}</text>'
          for i, text in enumerate(lines)],
        *(ladder_body(pick.get('ladder') or {}, legs, price, book, ink, soft, accent, title_size) if rung else
          parlay_body(legs, price, book, units, ink, soft, accent, title_size) if parlay else [
        f'<text x="80" y="418" fill="{soft}" font-size="26" letter-spacing="1">Served at</text>',
        f'<text x="80" y="470" fill="{ink}" font-size="50" font-weight="800">{esc(price)}<tspan fill="{soft}" font-size="34" font-weight="600" dx="18">{esc(book)}</tspan></text>',
        f'<text x="80" y="530" fill="{ink}" font-size="32">{esc(ours)}</text>']),
        f'<text x="80" y="{HEIGHT - 62}" fill="{ink}" font-size="26" font-weight="700">Graded in public, win or lose. <tspan fill="{soft}" font-weight="400">keenroudy.com/sports</tspan></text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 62}" fill="{soft}" font-size="19" text-anchor="end">Entertainment only. Not advice.</text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 94}" fill="{soft}" font-size="22" text-anchor="end">{esc(record_line)}</text>' if record_line else '',
        '</svg>']
    return '\n'.join(parts)


HOUSE = ('#2a1c14', '#3d2a1d', '#f28c28')      # the kitchen's own colours, for a card that is not on one team
RESULT_MARKS = {'win': ('W', '#6fdc8c'), 'loss': ('L', '#ff7a6b'), 'push': ('P', None), 'void': ('P', None)}


def receipt_svg(receipt, avatar=None):
    """A receipt in the same frame as a play: the kitchen's colours, the record as the title, each play with
    its result where a play's numbers go, and the chef on the plate."""
    chef = avatar_uri(CHEF) if avatar is None else avatar
    primary, other, accent = HOUSE
    ink, soft = CREAM, shade(CREAM, 0.82)
    rows = receipt.get('rows') or []
    shown = rows if len(rows) <= 6 else rows[:5]
    top = 262 + 66 + 4 + 44
    body = []
    for i, (result, text) in enumerate(shown):
        y = top + 36 * i
        if result is None:
            size, limit = (30, 36) if len(text) <= 36 else (24, 48)
            body.append(f'<text x="80" y="{y + 6}" fill="{ink}" font-size="{size}">{esc(fit(text, limit))}</text>')
            continue
        mark, colour = RESULT_MARKS.get(result, ('?', None))
        size, limit = (26, 34) if len(text) <= 34 else (22, 50)
        body.append(f'<text x="80" y="{y}" fill="{colour or soft}" font-size="26" font-weight="800">{mark}</text>')
        body.append(f'<text x="116" y="{y}" fill="{ink}" font-size="{size}">{esc(fit(text, limit))}</text>')
    if len(rows) > len(shown):
        body.append(f'<text x="80" y="{top + 36 * len(shown)}" fill="{soft}" font-size="24">and {len(rows) - len(shown)} more on the site</text>')
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">',
        '<defs>',
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{primary}"/><stop offset="0.72" stop-color="{shade(primary, 0.8)}"/><stop offset="1" stop-color="{other}"/></linearGradient>',
        '</defs>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>',
        *plate(WIDTH - 250, HEIGHT // 2 + 20, chef, False),
        f'<rect x="36" y="36" width="{WIDTH - 72}" height="{HEIGHT - 72}" rx="30" fill="none" stroke="{accent}" stroke-opacity="0.55" stroke-width="3"/>',
        PAN.format(x=72, y=78, s=0.5, c=accent),
        f'<text x="140" y="116" fill="{ink}" font-size="34" font-weight="800" letter-spacing="5">KOOK’N</text>',
        f'<text x="{WIDTH - 80}" y="116" fill="{soft}" font-size="26" font-weight="700" letter-spacing="3" text-anchor="end">{esc(receipt.get("kicker") or "RECEIPTS")}</text>',
        f'<text x="80" y="212" fill="{soft}" font-size="32">{esc(receipt.get("when") or "")}</text>',
        f'<text x="80" y="262" fill="{accent}" font-size="24" font-weight="700" letter-spacing="4">{esc(receipt.get("label") or "")}</text>',
        *[f'<text x="80" y="{262 + (size + 6) * (i + 1) - 2}" fill="{ink}" font-size="{size}" font-weight="800">{esc(text)}</text>'
          for size in [66 if len(receipt.get("title") or "") <= 22 else 54] for i, text in enumerate(title_lines(receipt.get("title") or "", 22, 22))],
        *body,
        f'<text x="80" y="{HEIGHT - 62}" fill="{ink}" font-size="26" font-weight="700">Graded in public, win or lose. <tspan fill="{soft}" font-weight="400">keenroudy.com/sports</tspan></text>',
        f'<text x="{WIDTH - 80}" y="{HEIGHT - 62}" fill="{soft}" font-size="19" text-anchor="end">Entertainment only. Not advice.</text>',
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
    price on the "Served at" line."""
    top = 262 + title_size + 4 + 44
    shown = legs if len(legs) <= 5 else legs[:4]
    rows = [f'<text x="80" y="{top + 34 * i}" fill="{ink}" font-size="26">• {esc(fit(leg, 40))}</text>' for i, leg in enumerate(shown)]
    if len(legs) > len(shown):
        rows.append(f'<text x="80" y="{top + 34 * len(shown)}" fill="{soft}" font-size="24">and {len(legs) - len(shown)} more</text>')
    rows.append(f'<text x="80" y="562" fill="{soft}" font-size="26" letter-spacing="1">Served at <tspan fill="{ink}" font-size="44" '
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
             f'<text x="80" y="562" fill="{soft}" font-size="26" letter-spacing="1">Served at <tspan fill="{ink}" font-size="44" '
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
    text = svg(pick, game, player_side=player_side)
    if args.svg:
        print(text)
        return 0
    out = Path(args.out) if args.out else Path(os.environ.get('KEENROUDY_CONF') or (Path.home() / '.config' / 'keenroudy')) / 'x-drafts' / f'{args.pick_id}.png'
    print(render(text, out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
