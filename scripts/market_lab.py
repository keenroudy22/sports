"""Silent MLB and NHL market capture: real pregame prices first, models later.

The score center already knows when games happen. This module adds the evidence a future
baseball or hockey model must be judged against: the first DraftKings pregame market the
desk sees, every changed snapshot before the game, and the final score. It does not make a
prediction, grade a pick, publish a post or call a metered odds service.

Records are append-only in data/market-lab/<league>-<season>.jsonl with a ledger. A quote
contains only fields supplied by ESPN's public DraftKings feed. A grade is only the final
score; sport- and book-specific bet settlement is deliberately deferred.

  python scripts/market_lab.py step
  python scripts/market_lab.py report
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import sports_refresh
from boxscores import line

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'market-lab'
PUBLIC = ROOT / 'site' / 'data' / 'market-lab.json'
LEAGUES = ('MLB', 'NHL')
AHEAD = timedelta(hours=36)
# Three prior dates recover finals after a short outage; two future dates cover the capture window.
DAY_OFFSETS = tuple(range(-3, 3))
PREFERRED = ('DraftKings', 'ESPN BET', 'FanDuel')


def path_for(league, season, root=STORE):
    return Path(root) / f'{league.lower()}-{season}.jsonl'


def read_all(root=STORE):
    rows = []
    for path in sorted(Path(root).glob('*.jsonl')):
        rows.extend(boxscores.read_store(path))
    return rows


def append(rows, root=STORE):
    """Append rows by league-season and refresh the integrity ledger."""
    if not rows:
        return 0
    root = Path(root)
    problems = boxscores.verify(root) if root.exists() else []
    if problems:
        raise ValueError('refusing to append to a market lab whose records changed: ' + '; '.join(problems))
    grouped = {}
    for row in rows:
        grouped.setdefault(path_for(row['league'], row['season'], root), []).append(row)
    for path, batch in sorted(grouped.items()):
        boxscores.append(path, batch)
    boxscores.write_json(root / 'ledger.json', boxscores.ledger(root))
    return len(rows)


def scoreboards(league, now, fetch=boxscores.fetch_json):
    """Normalized scheduled and final games around `now`, preserving provider event IDs."""
    games = {}
    for offset in DAY_OFFSETS:
        day = sports_refresh.eastern_date(now + timedelta(days=offset))
        url = sports_refresh.endpoint(league, day)
        try:
            payload = fetch(url)
            rows = sports_refresh.normalize(payload, league, now, url)
        except Exception:
            continue
        for game in rows:
            games[game['id']] = game
    return sorted(games.values(), key=lambda game: (game['kickoff'], game['id']))


def odds_url(league, event_id):
    config = sports_refresh.LEAGUES[league]
    return (f"https://sports.core.api.espn.com/v2/sports/{config['sport']}/leagues/{config['slug']}"
            f"/events/{event_id}/competitions/{event_id}/odds")


def american(value):
    """An American price from a feed object or scalar, never a synthesized price."""
    if isinstance(value, dict):
        value = value.get('american', value.get('alternateDisplayValue'))
    try:
        text = str(value).strip().replace('+', '')
        number = float(text)
        return int(number) if number.is_integer() and number != 0 else None
    except (TypeError, ValueError):
        return None


def number(value):
    value = line(value)
    return round(value, 2) if value is not None else None


def books(payload):
    """One pregame item per real book; live and projection feeds are excluded."""
    found = {}
    for item in (payload or {}).get('items') or []:
        provider = item.get('provider') or {}
        name, pid = str(provider.get('name') or ''), str(provider.get('id') or '')
        if 'live' in name.lower() or not pid.isdigit() or int(pid) >= 1000:
            continue
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip() or pid
        found.setdefault(name, item)
    return found


def side(team, phase, fallback_line=None):
    """One team's moneyline and run/puck line at `phase`, only when the feed supplies them."""
    block = team.get(phase) or (team.get('close') if phase == 'current' else {}) or {}
    spread_line = number(block.get('pointSpread'))
    if spread_line is None:
        spread_line = number(fallback_line)
    out = {
        'moneyline': american(block.get('moneyLine')) or (american(team.get('moneyLine')) if phase == 'current' else None),
        'spreadLine': spread_line,
        'spreadPrice': american(block.get('spread')) or (american(team.get('spreadOdds')) if phase == 'current' else None),
    }
    return {key: value for key, value in out.items() if value is not None}


def snapshot(item, phase='current'):
    """Full-game market snapshot from one book; missing fields remain missing."""
    block = item.get(phase) or (item.get('close') if phase == 'current' else {}) or {}
    total_line = number(block.get('total'))
    if total_line is None:
        total_line = number(item.get('overUnder') if phase == 'current' else item.get('initialOverUnder'))
    if total_line is not None and total_line <= 0:   # ESPN uses zero for an absent initial market
        total_line = None
    total = {'line': total_line,
             'over': american(block.get('over')) or (american(item.get('overOdds')) if phase == 'current' else None),
             'under': american(block.get('under')) or (american(item.get('underOdds')) if phase == 'current' else None)}
    total = {key: value for key, value in total.items() if value is not None}
    home_fallback = item.get('spread') if phase == 'current' else item.get('initialSpread')
    home_line = number(home_fallback)
    if phase == 'open' and home_line == 0:           # zero is an absent MLB/NHL run/puck line, not pick'em
        home_line = None
    away_line = -home_line if home_line is not None else None
    markets = {
        'total': total,
        'home': side(item.get('homeTeamOdds') or {}, phase, home_line),
        'away': side(item.get('awayTeamOdds') or {}, phase, away_line),
    }
    return {key: value for key, value in markets.items() if value}


def quote(league, event_id, fetch=boxscores.fetch_json):
    """The preferred book's current and opening full-game markets, or None."""
    try:
        payload = fetch(odds_url(league, event_id))
    except Exception:
        return None
    available = books(payload)
    for name in list(PREFERRED) + sorted(set(available) - set(PREFERRED)):
        item = available.get(name)
        if not item:
            continue
        current = snapshot(item, 'current')
        if current:
            return {'book': name, 'current': current, 'open': snapshot(item, 'open')}
    return None


def quote_key(row):
    return json.dumps({'book': row.get('book'), 'current': row.get('current'), 'open': row.get('open')}, sort_keys=True)


def phase(value):
    text = str(value or '').lower()
    if 'post' in text or 'playoff' in text or text == '3':
        return 'playoffs'
    if 'regular' in text or text == '2':
        return 'regular'
    return 'unclassified'


def step(now=None, fetch=boxscores.fetch_json, root=STORE, public=PUBLIC, log=print):
    """Capture changed pregame markets and final scores; publish nothing."""
    now = now or datetime.now(timezone.utc)
    existing = read_all(root)
    last_quote, graded = {}, {row['gameId'] for row in existing if row.get('type') == 'grade'}
    for row in existing:
        if row.get('type') == 'quote':
            last_quote[row['gameId']] = row
    out, game_counts = [], {league: {'quoted': 0, 'graded': 0} for league in LEAGUES}
    for league in LEAGUES:
        for game in scoreboards(league, now, fetch):
            kickoff = datetime.fromisoformat(game['kickoff'].replace('Z', '+00:00'))
            if game['status'] == 'scheduled' and now < kickoff <= now + AHEAD:
                captured = quote(league, game['providerId'], fetch)
                if not captured:
                    continue
                row = {'type': 'quote', 'gameId': game['id'], 'league': league, 'season': game['season'],
                       'seasonType': game.get('seasonType'),
                       'kickoff': game['kickoff'], 'capturedAt': boxscores.stamp(now), 'book': captured['book'],
                       'home': game['teams']['home'], 'away': game['teams']['away'],
                       'current': captured['current'], 'open': captured['open']}
                previous = last_quote.get(game['id'])
                if previous is None or quote_key(previous) != quote_key(row):
                    out.append(row)
                    last_quote[game['id']] = row
                    game_counts[league]['quoted'] += 1
            elif game['status'] == 'final' and game['id'] in last_quote and game['id'] not in graded:
                scores = game.get('scores') or {}
                if scores.get('home') is None or scores.get('away') is None:
                    continue
                out.append({'type': 'grade', 'gameId': game['id'], 'league': league, 'season': game['season'],
                            'seasonType': game.get('seasonType'),
                            'kickoff': game['kickoff'], 'gradedAt': boxscores.stamp(now),
                            'homeScore': scores['home'], 'awayScore': scores['away'],
                            'statusDetail': game.get('statusDetail')})
                graded.add(game['id'])
                game_counts[league]['graded'] += 1
    append(out, root)
    report(root, public, now)
    if out:
        log('market lab: ' + ', '.join(f"{league} {counts['quoted']} quotes, {counts['graded']} finals"
                                       for league, counts in game_counts.items()))
    return {'captured': sum(x['quoted'] for x in game_counts.values()),
            'graded': sum(x['graded'] for x in game_counts.values()), 'leagues': game_counts}


def report(root=STORE, public=PUBLIC, now=None):
    """Human and site summaries of capture coverage, never model performance."""
    now = now or datetime.now(timezone.utc)
    rows = read_all(root)
    data = {'updatedAt': boxscores.stamp(now), 'leagues': {}}
    quotes_by_game = {r['gameId']:r for r in rows if r.get('type')=='quote'}
    data['recentResults'] = []
    for result in sorted((r for r in rows if r.get('type')=='grade'), key=lambda r:r['kickoff'], reverse=True)[:100]:
        original=quotes_by_game.get(result['gameId'])
        if original:
            data['recentResults'].append({**result,'home':original['home'],'away':original['away']})
    lines = ['# MLB and NHL market lab', '',
             'Pregame prices and final scores captured silently. No predictions or published plays.', '']
    for league in LEAGUES:
        mine = [row for row in rows if row.get('league') == league]
        quotes = [row for row in mine if row.get('type') == 'quote']
        grades = [row for row in mine if row.get('type') == 'grade']
        games = {row['gameId'] for row in quotes}
        totals = sum(bool((row.get('current') or {}).get('total')) for row in quotes)
        moneylines = sum(bool((row.get('current') or {}).get('home', {}).get('moneyline') is not None and
                              (row.get('current') or {}).get('away', {}).get('moneyline') is not None) for row in quotes)
        summary = {'status': 'capturing', 'gamesQuoted': len(games), 'snapshots': len(quotes),
                   'gamesGraded': len({row['gameId'] for row in grades}),
                   'totalSnapshots': totals, 'moneylineSnapshots': moneylines}
        groups = {}
        for row in mine:
            if not isinstance(row.get('season'), int):
                continue
            groups.setdefault((row['season'], phase(row.get('seasonType'))), []).append(row)
        summary['seasons'] = []
        for (season, stage), items in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1]), reverse=True):
            stage_quotes = [row for row in items if row.get('type') == 'quote']
            stage_grades = [row for row in items if row.get('type') == 'grade']
            summary['seasons'].append({'season': season, 'phase': stage,
                                       'gamesQuoted': len({row['gameId'] for row in stage_quotes}),
                                       'gamesGraded': len({row['gameId'] for row in stage_grades})})
        data['leagues'][league] = summary
        lines.append(f"- **{league}**: {summary['gamesQuoted']} games quoted, {summary['snapshots']} changed snapshots, "
                     f"{summary['gamesGraded']} finals joined; totals on {totals} snapshots, both moneylines on {moneylines}.")
    if not rows:
        lines.append('- Capture is armed; the first record waits for an upcoming game with a supplied DraftKings market.')
    text = '\n'.join(lines) + '\n'
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'REPORT.md').write_text(text, encoding='utf-8')
    public = Path(public)
    public.parent.mkdir(parents=True, exist_ok=True)
    boxscores.write_json(public, data)
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('step', 'report'))
    args = parser.parse_args(argv)
    if args.command == 'report':
        print(report())
        return 0
    print(step())
    return 0


if __name__ == '__main__':
    sys.exit(main())
