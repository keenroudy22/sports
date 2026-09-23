"""Where games are played: a venue table with roof and coordinates, built from free sources. Stdlib only.

The box-score store names a venue for every game (id, name, grass) but says nothing about a roof or a
place. Weather needs both: an outdoor venue and a point to ask the forecast for. This builds
data/venues.json from ESPN's venue endpoint (name, city, state, indoor) and Open-Meteo's geocoder (a
point for the city; free, no key), one entry per venue id seen in the store or the slate, and only for
ids not already in the table, so a run costs a few requests at most. A venue the geocoder cannot place
is written with `lat: null` and listed in data/venues-review.json for a person.

  python scripts/venues.py [--limit N]
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'data' / 'venues.json'
REVIEW = ROOT / 'data' / 'venues-review.json'
ESPN = 'https://sports.core.api.espn.com/v2/sports/football/leagues/{slug}/venues/{id}'
GEOCODE = 'https://geocoding-api.open-meteo.com/v1/search?name={name}&count=10&language=en&format=json'
SLUG = {'NFL': 'nfl', 'CFB': 'college-football'}
STATES = {'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California', 'CO': 'Colorado',
          'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
          'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine',
          'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
          'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
          'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
          'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee',
          'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
          'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'}
PAUSE = 0.25


def fetch_json(url, timeout=20, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def load(path=TABLE):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else {}


def save(table, path=TABLE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(dict(sorted(table.items())), indent=1, ensure_ascii=False) + '\n', encoding='utf-8')


def seen_venues(records, slate=None):
    """(league, venue id) -> name, from every stored game and every slate game that names one."""
    out = {}
    for game in records:
        venue = game.get('venue') or {}
        if venue.get('id'):
            out[(game['league'], str(venue['id']))] = venue.get('name')
    for game in (slate or {}).get('games', []):
        venue = game.get('venue') or {}
        if venue.get('id') and game.get('league') in SLUG:
            out.setdefault((game['league'], str(venue['id'])), venue.get('name'))
    return out


def describe(league, venue_id, fetch=fetch_json):
    """ESPN's venue record: name, city, state, indoor, grass."""
    payload = fetch(ESPN.format(slug=SLUG[league], id=venue_id))
    address = payload.get('address') or {}
    return {'name': payload.get('fullName') or payload.get('name'), 'city': address.get('city'), 'state': address.get('state'),
            'country': address.get('country') or 'USA', 'indoor': bool(payload.get('indoor')), 'grass': payload.get('grass'),
            'espn': ESPN.format(slug=SLUG[league], id=venue_id)}


US = {'USA', 'US', 'UNITED STATES', 'UNITED STATES OF AMERICA'}


def geocode(city, state, fetch=fetch_json, country='USA'):
    """A point for the city: in the US, the result in the right state; abroad, the biggest place in that country."""
    if not city:
        return None
    payload = fetch(GEOCODE.format(name=urllib.parse.quote(city)))
    results = payload.get('results') or []
    domestic = str(country or 'USA').upper() in US
    if domestic:
        want = STATES.get((state or '').upper(), state or '')
        ranked = sorted(results, key=lambda r: (r.get('country_code') != 'US', (r.get('admin1') or '') != want, -(r.get('population') or 0)))
        best = ranked[0] if ranked else None
        if not best or best.get('country_code') != 'US' or (want and (best.get('admin1') or '') != want):
            return None
    else:
        abroad = [r for r in results if str(r.get('country') or '').upper() == str(country).upper() or
                  str(r.get('country_code') or '').upper() == str(country).upper()]
        best = max(abroad, key=lambda r: r.get('population') or 0) if abroad else None
        if not best:
            return None
    return {'lat': round(best['latitude'], 4), 'lon': round(best['longitude'], 4),
            'place': f"{best.get('name')}, {best.get('admin1') or best.get('country')}",
            'geocoder': 'https://open-meteo.com/en/docs/geocoding-api'}


def build(records, slate=None, table=None, fetch=fetch_json, limit=None, log=print, pause=PAUSE):
    """Add every venue the store or slate names that the table lacks. Returns (table, review list)."""
    table = dict(table if table is not None else load())
    review = []
    added = 0
    for (league, venue_id), name in sorted(seen_venues(records, slate).items()):
        key = f'{league}-{venue_id}'
        if key in table:
            continue
        if limit is not None and added >= limit:
            break
        entry = {'id': venue_id, 'league': league, 'name': name, 'checkedAt': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        try:
            entry.update(describe(league, venue_id, fetch))
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            entry.update({'indoor': None, 'error': f'espn: {type(error).__name__}'})
        point = None
        if entry.get('city'):
            try:
                point = geocode(entry['city'], entry.get('state'), fetch, entry.get('country') or 'USA')
            except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
                entry['error'] = f'geocode: {type(error).__name__}'
        entry.update(point or {'lat': None, 'lon': None})
        if entry.get('lat') is None or entry.get('indoor') is None:
            review.append({'key': key, 'name': entry.get('name'), 'city': entry.get('city'), 'state': entry.get('state'),
                           'why': entry.get('error') or 'no point for the city'})
        table[key] = entry
        added += 1
        log(f"{key} {entry.get('name')}: {'indoor' if entry.get('indoor') else 'outdoor'}, {entry.get('place') or 'no point'}")
        time.sleep(pause)
    return table, review


def usual_venues(records):
    """(league, home team id) -> the venue id of most of its stored home games; a stand-in when the slate names none."""
    counts = {}
    for game in records:
        venue = game.get('venue') or {}
        if venue.get('id') and not game.get('neutral'):
            key = (game['league'], str(game['home']['id']))
            counts.setdefault(key, {}).setdefault(str(venue['id']), 0)
            counts[key][str(venue['id'])] += 1
    return {key: max(ids, key=ids.get) for key, ids in counts.items()}


def venue_for(game, table, usual=None):
    """The table entry for a slate game: its own venue when the slate names one, else the home team's usual one."""
    venue = (game.get('venue') or {}).get('id')
    if venue:
        return table.get(f"{game['league']}-{venue}")
    if game.get('neutral') or not usual:
        return None
    usual_id = usual.get((game['league'], str(game['home']['id'])))
    return table.get(f"{game['league']}-{usual_id}") if usual_id else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--limit', type=int, help='add at most this many venues this run')
    args = parser.parse_args(argv)
    import features
    records = features.load()
    slate = json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
    table, review = build(records, slate, limit=args.limit)
    save(table)
    existing = load(REVIEW) if REVIEW.exists() else []
    if review or existing:
        keep = [r for r in (existing if isinstance(existing, list) else []) if table.get(r['key'], {}).get('lat') is None]
        REVIEW.write_text(json.dumps(keep + review, indent=1) + '\n', encoding='utf-8')
    placed = sum(1 for v in table.values() if v.get('lat') is not None)
    print(f'{len(table)} venues, {placed} with a point, {sum(1 for v in table.values() if v.get("indoor"))} indoor; {len(review)} for review')
    return 0


if __name__ == '__main__':
    sys.exit(main())
