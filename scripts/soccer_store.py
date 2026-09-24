"""Soccer results and prices from football-data.co.uk, one line per match.

football-data.co.uk publishes a free CSV per league and season with the final score, shots and
bookmaker prices: 1X2 (home, draw, away), over/under 2.5 goals and the Asian handicap, both as
first collected and at the close. Each played match becomes one compact JSON line:

  id          EPL-2025-08-15-liverpool-bournemouth (league, date, home, away)
  season      "2025-26" for the Premier League, "2025" for MLS
  date, time  as the file gives them, UK local time; kickoff is the same moment in UTC
  home, away  football-data's team names (data/soccer/teams.json maps them to ESPN)
  close       the closing prices: Pinnacle where the file has them, else the market average,
              with the book each market came from under `books`
  open        the same from the first collection (Friday afternoon for a weekend game,
              Tuesday afternoon for a midweek one), which is when the desk would bet
  closeAvg, openAvg   the market average, the price a typical book offered

Prices are decimal odds exactly as published. A market the file leaves blank is left out,
never filled in. MLS's file carries closing 1X2 prices only: no totals, no handicap, no opening
prices. football-data has no Champions League file; the Champions League appears only in the
ESPN team map, so a Premier League club's European game can be paired with the model later.

The store is data/soccer/<league>.jsonl, append-only like the box-score store: a line is never
edited, a later read with different content appends a revision (the last line for an id wins),
and data/soccer/ledger.json hashes the lines each file holds. Running again with nothing new
appends nothing.

Usage:
  python scripts/soccer_store.py                          the current EPL and MLS seasons
  python scripts/soccer_store.py --backfill EPL 2016 2026 seasons by starting year
  python scripts/soccer_store.py --backfill MLS 2016 2026
  python scripts/soccer_store.py teams                    the ESPN team map for current clubs
Stdlib only.
"""
import argparse
import csv
import io
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'soccer'
TEAMS = STORE / 'teams.json'
BASE = 'https://www.football-data.co.uk/'
LEAGUES = {'EPL': {'file': 'E0', 'espn': 'eng.1', 'split': True},
           'MLS': {'url': BASE + 'new/USA.csv', 'espn': 'usa.1', 'split': False}}
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer/'
ESPN_LEAGUES = {'EPL': 'eng.1', 'MLS': 'usa.1', 'UCL': 'uefa.champions'}

# Where each market's prices come from, most trusted first: (book, columns...). Pinnacle is the
# sharpest price in the files; the market average is what a typical book offered. The 2016-17 to
# 2018-19 files carry Betbrain's average instead of the market average and no closing totals or
# handicap. The notes (football-data.co.uk/notes.txt) name PH/PD/PA as an older Pinnacle spelling.
ONE_X_TWO = {'close': (('Pinnacle', 'PSCH', 'PSCD', 'PSCA'), ('Average', 'AvgCH', 'AvgCD', 'AvgCA')),
             'open': (('Pinnacle', 'PSH', 'PSD', 'PSA'), ('Pinnacle', 'PH', 'PD', 'PA'),
                      ('Average', 'AvgH', 'AvgD', 'AvgA'), ('Average', 'BbAvH', 'BbAvD', 'BbAvA'))}
TOTALS = {'close': (('Pinnacle', 'PC>2.5', 'PC<2.5'), ('Average', 'AvgC>2.5', 'AvgC<2.5')),
          'open': (('Pinnacle', 'P>2.5', 'P<2.5'), ('Average', 'Avg>2.5', 'Avg<2.5'),
                   ('Average', 'BbAv>2.5', 'BbAv<2.5'))}
# The handicap is the home side's (-0.75 means the home side gives three quarters of a goal).
HANDICAP = {'close': (('AHCh',), (('Pinnacle', 'PCAHH', 'PCAHA'), ('Average', 'AvgCAHH', 'AvgCAHA'))),
            'open': (('AHh', 'BbAHh'), (('Pinnacle', 'PAHH', 'PAHA'), ('Average', 'AvgAHH', 'AvgAHA'),
                                        ('Average', 'BbAvAHH', 'BbAvAHA')))}

# football-data spelling -> ESPN displayName, hand-checked against ESPN's team lists on 2026-09-24.
# Names that already agree once accents, "FC" and punctuation are dropped need no entry.
ALIASES = {
    'EPL': {'Man City': 'Manchester City', 'Man United': 'Manchester United', "Nott'm Forest": 'Nottingham Forest',
            'Newcastle': 'Newcastle United', 'Tottenham': 'Tottenham Hotspur', 'Wolves': 'Wolverhampton Wanderers',
            'West Ham': 'West Ham United', 'Brighton': 'Brighton & Hove Albion', 'Leeds': 'Leeds United',
            'Leicester': 'Leicester City', 'Ipswich': 'Ipswich Town', 'Hull': 'Hull City', 'Coventry': 'Coventry City',
            'Bournemouth': 'AFC Bournemouth', 'Luton': 'Luton Town', 'Norwich': 'Norwich City',
            'Cardiff': 'Cardiff City', 'Stoke': 'Stoke City', 'Swansea': 'Swansea City',
            'West Brom': 'West Bromwich Albion', 'Huddersfield': 'Huddersfield Town', 'Sheffield United': 'Sheffield United'},
    'MLS': {'Atlanta Utd': 'Atlanta United FC', 'CF Montreal': 'CF Montréal', 'Charlotte': 'Charlotte FC',
            'Chicago Fire': 'Chicago Fire FC', 'DC United': 'D.C. United', 'Houston Dynamo': 'Houston Dynamo FC',
            'Inter Miami': 'Inter Miami CF', 'Los Angeles FC': 'LAFC', 'Los Angeles Galaxy': 'LA Galaxy',
            'Minnesota United': 'Minnesota United FC', 'New York City': 'New York City FC',
            'New York Red Bulls': 'Red Bull New York', 'Orlando City': 'Orlando City SC',
            'Seattle Sounders': 'Seattle Sounders FC', 'St. Louis City': 'St. Louis CITY SC'},
}


def stamp(moment):
    return boxscores.stamp(moment)


def fetch_text(url, attempts=3, pause=2.0):
    """The file as text, with Python's default User-Agent. Retries throttling and server errors."""
    for attempt in range(attempts):
        try:
            with urlopen(url, timeout=60) as response:
                return response.read().decode('utf-8-sig', errors='replace')
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == attempts - 1:
                raise
        time.sleep(pause * (attempt + 1))


# ---------------------------------------------------------------- parsing

def season_label(league, start_year):
    """EPL 2025 -> '2025-26'; MLS 2025 -> '2025'."""
    start_year = int(start_year)
    return f'{start_year}-{(start_year + 1) % 100:02d}' if LEAGUES[league]['split'] else str(start_year)


def season_url(league, start_year):
    if LEAGUES[league]['split']:
        code = f'{start_year % 100:02d}{(start_year + 1) % 100:02d}'
        return f'{BASE}mmz4281/{code}/{LEAGUES[league]["file"]}.csv'
    return LEAGUES[league]['url']


def current_start_year(league, today):
    """The season in play on `today`: the Premier League's starts in August, MLS's in February."""
    if LEAGUES[league]['split']:
        return today.year if today.month >= 7 else today.year - 1
    return today.year


def parse_date(text):
    """dd/mm/yy or dd/mm/yyyy (both appear in the files) -> date, or None."""
    found = re.fullmatch(r'\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*', str(text or ''))
    if not found:
        return None
    day, month, year = (int(found.group(i)) for i in (1, 2, 3))
    year += 2000 if year < 100 else 0
    try:
        return date(year, month, day)
    except ValueError:
        return None


def last_sunday(year, month):
    moment = date(year, month + 1, 1) - timedelta(days=1)
    return moment - timedelta(days=(moment.weekday() + 1) % 7)


def uk_to_utc(day, clock):
    """A UK wall-clock time as UTC. British Summer Time runs from 01:00 UTC on the last Sunday of March
    to 01:00 UTC on the last Sunday of October (the rule since 1996); football-data's times are UK time."""
    found = re.fullmatch(r'\s*(\d{1,2}):(\d{2})\s*', str(clock or ''))
    if not day or not found:
        return None
    local = datetime(day.year, day.month, day.day, int(found.group(1)), int(found.group(2)), tzinfo=timezone.utc)
    start = datetime.combine(last_sunday(day.year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(last_sunday(day.year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    summer = start + timedelta(hours=1) <= local < end + timedelta(hours=1)
    return local - timedelta(hours=1) if summer else local


def goals(value):
    text = str(value if value is not None else '').strip()
    return int(text) if re.fullmatch(r'\d+', text) else None


def number(value):
    text = str(value if value is not None else '').strip()
    return float(text) if re.fullmatch(r'-?\d+(\.\d+)?', text) else None


def decimal(value):
    """Decimal odds above 1.0, or None. Blanks, zeros and text are missing, never guessed."""
    parsed = number(value)
    return parsed if parsed is not None and parsed > 1.0 else None


def handicap(value):
    """A handicap on the quarter-goal grid, or None."""
    parsed = number(value)
    return parsed if parsed is not None and abs(parsed * 4 - round(parsed * 4)) < 1e-9 else None


def first_priced(row, options):
    """The first (book, prices) whose every column holds valid odds."""
    for book, *columns in options:
        prices = [decimal(row.get(column)) for column in columns]
        if all(price is not None for price in prices):
            return book, prices
    return None, None


def prices(row, when, average_only=False):
    """One moment's 1X2, total and handicap prices from a CSV row; {} when the file has none."""
    def usable(options):
        return tuple(o for o in options if o[0] == 'Average') if average_only else options

    out, books = {}, {}
    book, found = first_priced(row, usable(ONE_X_TWO[when]))
    if found:
        out.update(home=found[0], draw=found[1], away=found[2])
        books['1x2'] = book
    book, found = first_priced(row, usable(TOTALS[when]))
    if found:
        out.update(over25=found[0], under25=found[1])
        books['total'] = book
    line_columns, options = HANDICAP[when]
    for column in line_columns:
        line = handicap(row.get(column))
        if line is None:
            continue
        # A Betbrain line goes with Betbrain's prices only; the market line with the others.
        paired = [o for o in usable(options) if o[1].startswith('BbAv') == column.startswith('Bb')]
        book, found = first_priced(row, paired)
        if found:
            out.update(ahLine=line, ahHome=found[0], ahAway=found[1])
            books['ah'] = book
            break
    if out and not average_only:
        out['books'] = books
    return out


def slug(text):
    plain = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '-', plain.lower()).strip('-')


def match_id(league, day, home, away):
    return f'{league}-{day.isoformat()}-{slug(home)}-{slug(away)}'


def build_record(row, league, season, source, retrieved_at):
    """One played match as a compact record, or None for a blank or unplayed row."""
    home = (row.get('HomeTeam') or row.get('Home') or '').strip()
    away = (row.get('AwayTeam') or row.get('Away') or '').strip()
    day = parse_date(row.get('Date'))
    home_goals = goals(row.get('FTHG') if row.get('FTHG') not in (None, '') else row.get('HG'))
    away_goals = goals(row.get('FTAG') if row.get('FTAG') not in (None, '') else row.get('AG'))
    if not home or not away or not day or home_goals is None or away_goals is None:
        return None
    clock = (row.get('Time') or '').strip() or None
    kickoff = uk_to_utc(day, clock)
    record = {'id': match_id(league, day, home, away), 'league': league, 'season': season,
              'date': day.isoformat(), 'home': home, 'away': away, 'homeGoals': home_goals, 'awayGoals': away_goals}
    if clock and kickoff:
        record['time'] = clock
        record['kickoff'] = stamp(kickoff)
    shots = {key: goals(row.get(column)) for key, column in
             (('home', 'HS'), ('away', 'AS'), ('homeTarget', 'HST'), ('awayTarget', 'AST'))}
    if shots['home'] is not None and shots['away'] is not None:
        record['shots'] = {k: v for k, v in shots.items() if v is not None}
    xg = number(row.get('HxG')), number(row.get('AxG'))
    if None not in xg:
        record['xg'] = {'home': xg[0], 'away': xg[1]}
    for when in ('close', 'open'):
        primary, average = prices(row, when), prices(row, when, average_only=True)
        if primary:
            record[when] = primary
        if average:
            record[f'{when}Avg'] = average
    record['source'] = source
    record['retrievedAt'] = retrieved_at
    record['hash'] = boxscores.content_hash(record)
    return record


def parse_csv(text, league, source, retrieved_at, start_year=None, seasons=None):
    """Records from one football-data CSV. A split-season file names its season by `start_year`;
    MLS's single file carries a Season column, filtered to `seasons` (start years) when given."""
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    records, seen = [], set()
    for row in reader:
        row = {(k or '').strip(): (v or '') if not isinstance(v, list) else '' for k, v in row.items()}
        if LEAGUES[league]['split']:
            season = season_label(league, start_year)
        else:
            year = goals(row.get('Season'))
            if year is None or (seasons is not None and year not in seasons):
                continue
            season = str(year)
        record = build_record(row, league, season, source, retrieved_at)
        if record and record['id'] not in seen:
            seen.add(record['id'])
            records.append(record)
    return records


# ---------------------------------------------------------------- the store

def store_path(league, root=STORE):
    return root / f'{league.lower()}.jsonl'


def load(league, root=STORE):
    """The current version of every stored match, oldest first."""
    latest = {}
    for record in boxscores.read_store(store_path(league, root)):
        latest[record['id']] = record
    return sorted(latest.values(), key=lambda r: (r.get('kickoff') or r['date'] + 'T12:00:00Z', r['id']))


def update(league, records, root=STORE):
    """Append new matches and changed ones (as revisions). Returns (new, revised)."""
    existing = {record['id']: record for record in boxscores.read_store(store_path(league, root))}
    fresh, counts = [], Counter()
    for record in sorted(records, key=lambda r: (r.get('kickoff') or r['date'], r['id'])):
        previous = existing.get(record['id'])
        if previous and previous['hash'] == record['hash']:
            continue
        if previous:
            record = dict(record, revision=previous.get('revision', 1) + 1)
        counts['revised' if previous else 'new'] += 1
        fresh.append(record)
        existing[record['id']] = record
    boxscores.append(store_path(league, root), fresh)
    root.mkdir(parents=True, exist_ok=True)
    boxscores.write_json(root / 'ledger.json', boxscores.ledger(root))
    return counts['new'], counts['revised']


def collect(league, start_years, fetch=fetch_text, clock=None):
    """Records for the given seasons, read from football-data (one request per file)."""
    retrieved = stamp(clock() if clock else datetime.now(timezone.utc))
    if LEAGUES[league]['split']:
        out = []
        for year in start_years:
            url = season_url(league, year)
            out += parse_csv(fetch(url), league, url, retrieved, start_year=year)
        return out
    url = season_url(league, None)
    return parse_csv(fetch(url), league, url, retrieved, seasons=set(start_years))


# ---------------------------------------------------------------- ESPN team map

def plain(name):
    """A team name made comparable: no accents, punctuation, 'FC'/'AFC'/'SC' or '&'."""
    text = unicodedata.normalize('NFKD', str(name or '')).encode('ascii', 'ignore').decode('ascii').lower()
    text = text.replace('&', ' and ')
    words = [w for w in re.sub(r'[^a-z0-9]+', ' ', text).split() if w not in ('fc', 'afc', 'sc', 'cf')]
    return ' '.join(words)


def espn_teams(league, fetch=boxscores.fetch_json, days=28, today=None):
    """ESPN's clubs for a league: the teams list, else every club on the last `days` scoreboards."""
    slug_ = ESPN_LEAGUES[league]
    try:
        payload = fetch(f'{ESPN}{slug_}/teams')
        teams = [item['team'] for item in payload['sports'][0]['leagues'][0]['teams']]
        if teams:
            return teams
    except (HTTPError, URLError, OSError, KeyError, IndexError, ValueError):
        pass
    found, today = {}, today or datetime.now(timezone.utc).date()
    for back in range(days):
        day = (today - timedelta(days=back)).strftime('%Y%m%d')
        for event in fetch(f'{ESPN}{slug_}/scoreboard?dates={day}').get('events', []):
            for competitor in event.get('competitions', [{}])[0].get('competitors', []):
                team = competitor.get('team') or {}
                if team.get('id'):
                    found[str(team['id'])] = team
    return list(found.values())


def identity(team):
    color = team.get('color')
    alternate = team.get('alternateColor')
    return {'espnId': str(team['id']), 'abbreviation': team.get('abbreviation'), 'espnName': team.get('displayName'),
            'shortName': team.get('shortDisplayName'), 'color': f'#{color.lower()}' if color else None,
            'alternateColor': f'#{alternate.lower()}' if alternate else None, 'logo': team.get('logo')}


def match_names(league, names, teams):
    """football-data names -> ESPN team, by the alias table, then an exact plain-name match, then a
    unique containment ("Brentford" in "Brentford FC"). Returns (matched, unmatched names)."""
    by_plain = {}
    for team in teams:
        for field in ('displayName', 'shortDisplayName', 'name', 'location'):
            if team.get(field):
                by_plain.setdefault(plain(team[field]), {})[str(team['id'])] = team
    matched, unmatched = {}, []
    for name in sorted(names):
        wanted = plain(ALIASES.get(league, {}).get(name, name))
        exact = by_plain.get(wanted, {})
        if len(exact) == 1:
            matched[name] = next(iter(exact.values()))
            continue
        loose = {}
        for key, candidates in by_plain.items():
            if wanted and (f' {wanted} ' in f' {key} ' or f' {key} ' in f' {wanted} '):
                loose.update(candidates)
        if len(loose) == 1:
            matched[name] = next(iter(loose.values()))
        else:
            unmatched.append(name)
    return matched, unmatched


def team_map(root=STORE, fetch=boxscores.fetch_json, today=None):
    """The current season's clubs in each league with ESPN's id, abbreviation and colours.

    Champions League clubs are listed by ESPN id, with the Premier League name of any English club,
    so a European night can be paired with the domestic model. Anything unmatched is listed for a person.
    """
    today = today or datetime.now(timezone.utc).date()
    out = {'builtAt': stamp(datetime.now(timezone.utc)), 'leagues': {}, 'unmatched': {}}
    for league in LEAGUES:
        season = season_label(league, current_start_year(league, today))
        names = {r[side] for r in load(league, root) if r['season'] == season for side in ('home', 'away')}
        matched, unmatched = match_names(league, names, espn_teams(league, fetch, today=today))
        out['leagues'][league] = {'season': season, 'espn': ESPN_LEAGUES[league],
                                  'teams': {name: identity(team) for name, team in sorted(matched.items())}}
        if unmatched:
            out['unmatched'][league] = unmatched
    epl_by_id = {v['espnId']: name for name, v in out['leagues']['EPL']['teams'].items()}
    ucl = {}
    for team in espn_teams('UCL', fetch, today=today):
        entry = identity(team)
        if entry['espnId'] in epl_by_id:
            entry['footballData'] = {'EPL': epl_by_id[entry['espnId']]}
        ucl[entry['espnId']] = entry
    out['leagues']['UCL'] = {'season': season_label('EPL', current_start_year('EPL', today)),
                             'espn': ESPN_LEAGUES['UCL'], 'teams': dict(sorted(ucl.items()))}
    return out


def from_espn(team_map_, league, espn_id):
    """The football-data name for an ESPN team id in a league, or None."""
    for name, entry in (team_map_.get('leagues', {}).get(league, {}).get('teams') or {}).items():
        if entry.get('espnId') == str(espn_id):
            return entry.get('footballData', {}).get('EPL', name) if league == 'UCL' else name
    return None


# ---------------------------------------------------------------- command line

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('command', nargs='?', default='update', choices=('update', 'teams'))
    parser.add_argument('--backfill', nargs=3, metavar=('LEAGUE', 'FIRST', 'LAST'),
                        help='seasons by starting year, e.g. EPL 2016 2026')
    args = parser.parse_args(argv)
    problems = boxscores.verify(STORE)
    if problems:
        sys.exit('Refusing to append to a store whose recorded lines changed:\n  ' + '\n  '.join(problems))
    if args.command == 'teams':
        result = team_map()
        STORE.mkdir(parents=True, exist_ok=True)
        boxscores.write_json(TEAMS, result)
        sizes = {k: len(v['teams']) for k, v in result['leagues'].items()}
        print(f'Team map: {sizes}; unmatched {result["unmatched"] or "none"}')
        return
    today = datetime.now(timezone.utc).date()
    if args.backfill:
        league, first, last = args.backfill[0].upper(), int(args.backfill[1]), int(args.backfill[2])
        plans = {league: range(first, last + 1)}
    else:
        plans = {league: [current_start_year(league, today)] for league in LEAGUES}
    for league, years in plans.items():
        records = collect(league, list(years))
        new, revised = update(league, records)
        seasons = Counter(r['season'] for r in records)
        print(f'{league}: read {len(records)} matches {dict(sorted(seasons.items()))}; appended {new} new, {revised} revised')


if __name__ == '__main__':
    main()
