"""The forecast at kickoff for outdoor games, from the National Weather Service. Stdlib only.

Wind is the one weather input that moves a total, and the score model does not carry it. This reads
the NWS hourly forecast for the venue's point (data/venues.json) and takes the hour that covers
kickoff: wind, gusts, chance of precipitation, temperature and the short forecast. Forecasts reach
about six and a half days out; a game beyond that has none yet. Domes get nothing.

Appended to data/weather/<league>-<season>.jsonl when a game's forecast changes, so the record shows
what was known and when; the research run reads the latest line and falls back to a live read.

  python scripts/weather.py            append forecasts for upcoming outdoor games (the hosted workflow)
  python scripts/weather.py GAME_ID    print the live forecast for one game
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import features
import venues

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'weather'
POINTS = 'https://api.weather.gov/points/{lat:.4f},{lon:.4f}'
USER_AGENT = 'KeenRoudySports/1.0 (+https://keenroudy.com/sports/)'   # the NWS asks every client to identify itself
HORIZON = timedelta(hours=156)
WINDY, SOAKED, FRIGID = 15, 60, 25    # mph, per cent chance, degrees F: where a forecast starts to matter for a total
PAUSE = 0.3


def fetch_json(url, timeout=20):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/geo+json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def mph(text):
    """'5 mph' or '10 to 15 mph' -> the top number."""
    numbers = [int(n) for n in re.findall(r'\d+', str(text or ''))]
    return max(numbers) if numbers else None


def period_at(periods, kickoff):
    """The hourly period whose hour covers the kickoff, or None."""
    for period in periods:
        start = features.when(period['startTime'])
        end = features.when(period['endTime']) if period.get('endTime') else start + timedelta(hours=1)
        if start <= kickoff < end:
            return period
    return None


def forecast_for(lat, lon, kickoff, fetch=fetch_json, now=None):
    """The kickoff-hour forecast for a point, or None when it is beyond the horizon or unavailable."""
    now = now or datetime.now(timezone.utc)
    if kickoff > now + HORIZON:
        return None
    points = fetch(POINTS.format(lat=lat, lon=lon))
    hourly_url = points['properties']['forecastHourly']
    hourly = fetch(hourly_url)
    period = period_at(hourly['properties']['periods'], kickoff)
    if not period:
        return None
    precip = (period.get('probabilityOfPrecipitation') or {}).get('value')
    return {'windMph': mph(period.get('windSpeed')), 'gustMph': mph(period.get('windGust')), 'windDirection': period.get('windDirection'),
            'precipProb': precip, 'tempF': period.get('temperature'), 'shortForecast': period.get('shortForecast'),
            'periodStart': period['startTime'], 'issuedAt': (hourly['properties'].get('updateTime') or hourly['properties'].get('generatedAt')),
            'source': hourly_url}


def matters(forecast):
    """Why a forecast bears on a total, in words, or None when it does not."""
    if not forecast:
        return None
    reasons = []
    if (forecast.get('windMph') or 0) >= WINDY:
        reasons.append(f"wind {forecast['windMph']} mph")
    if (forecast.get('precipProb') or 0) >= SOAKED:
        reasons.append(f"{forecast['precipProb']}% chance of precipitation")
    if forecast.get('tempF') is not None and forecast['tempF'] <= FRIGID:
        reasons.append(f"{forecast['tempF']} degrees")
    return ', '.join(reasons) or None


def claim(venue, forecast):
    parts = [f"Forecast at kickoff at {venue.get('name')}: wind {forecast.get('windMph')} mph"]
    if forecast.get('gustMph'):
        parts[0] += f" gusting {forecast['gustMph']}"
    if forecast.get('windDirection'):
        parts[0] += f" from the {forecast['windDirection']}"
    if forecast.get('precipProb') is not None:
        parts.append(f"{forecast['precipProb']}% chance of precipitation")
    if forecast.get('tempF') is not None:
        parts.append(f"{forecast['tempF']} degrees")
    if forecast.get('shortForecast'):
        parts.append(str(forecast['shortForecast']).lower())
    return ', '.join(parts) + '.'


def fact_for(game, venue, forecast, now, side=None):
    """A weather fact for the research run. Direction follows the total's side when the forecast matters."""
    if not forecast or not venue:
        return None
    why = matters(forecast)
    direction = 'neutral'
    if why and side in ('over', 'under'):
        direction = 'for' if side == 'under' else 'against'
    return {'id': f"weather-{game['id']}", 'kind': 'weather', 'direction': direction, 'claim': claim(venue, forecast),
            'entities': [], 'source': forecast['source'], 'retrievedAt': features.when(now).isoformat().replace('+00:00', 'Z') if isinstance(now, str) else now.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'verified': True, 'matters': why, 'forecast': forecast}


def stored(root=STORE):
    """gameId -> latest stored forecast line."""
    out = {}
    for path in sorted(Path(root).glob('*.jsonl')):
        for line in boxscores.read_store(path):
            out[line['gameId']] = line
    return out


def upcoming_outdoor(slate, table, usual, now):
    for game in slate.get('games', []):
        if game.get('league') not in ('NFL', 'CFB') or game.get('state') != 'pre':
            continue
        kickoff = features.when(game['kickoff'])
        if not now < kickoff <= now + HORIZON:
            continue
        venue = venues.venue_for(game, table, usual)
        # The NWS covers the United States and nothing else; an outdoor game abroad gets no forecast here.
        if venue and venue.get('indoor') is False and venue.get('lat') is not None \
                and str(venue.get('country') or 'USA').upper() in venues.US:
            yield game, venue


def changed(new, old):
    if old is None:
        return True
    keys = ('windMph', 'gustMph', 'precipProb', 'tempF', 'shortForecast')
    return any((new.get('forecast') or {}).get(k) != (old.get('forecast') or {}).get(k) for k in keys)


def publish(now=None, root=STORE, slate=None, table=None, records=None, fetch=fetch_json, log=print, pause=PAUSE):
    now = now or datetime.now(timezone.utc)
    slate = slate if slate is not None else json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
    table = table if table is not None else venues.load()
    records = records if records is not None else features.load()
    usual = venues.usual_venues(records)
    existing = stored(root)
    new = []
    for game, venue in upcoming_outdoor(slate, table, usual, now):
        try:
            forecast = forecast_for(venue['lat'], venue['lon'], features.when(game['kickoff']), fetch, now)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            log(f"{game['id']}: forecast unavailable ({type(error).__name__})")
            continue
        if not forecast:
            continue
        line = {'gameId': game['id'], 'league': game['league'], 'season': game['season'], 'kickoff': game['kickoff'],
                'venue': {'id': venue.get('id'), 'name': venue.get('name')}, 'retrievedAt': now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
                'forecast': forecast, 'source': forecast['source']}
        if changed(line, existing.get(game['id'])):
            new.append(line)
        time.sleep(pause)
    written = {}
    for season in sorted({l['season'] for l in new}):
        for league in ('NFL', 'CFB'):
            batch = sorted((l for l in new if l['season'] == season and l['league'] == league), key=lambda l: (l['kickoff'], l['gameId']))
            if batch:
                boxscores.append(boxscores.store_path(league, season, Path(root)), batch)
                written[f'{league.lower()}-{season}.jsonl'] = len(batch)
    log(f'{sum(written.values())} new forecast lines {written or ""}')
    return written


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        slate = json.loads((ROOT / 'site' / 'data' / 'slate.json').read_text(encoding='utf-8'))
        game = next((g for g in slate.get('games', []) if g['id'] == argv[0]), None)
        if not game:
            sys.exit(f'{argv[0]} is not in the slate')
        table, records = venues.load(), features.load(leagues=(game['league'],))
        venue = venues.venue_for(game, table, venues.usual_venues(records))
        if not venue:
            sys.exit('no venue in the table for this game')
        if venue.get('indoor'):
            print(f"{venue['name']} is indoors; no forecast matters")
            return 0
        forecast = forecast_for(venue['lat'], venue['lon'], features.when(game['kickoff']))
        print(json.dumps({'venue': venue, 'forecast': forecast}, indent=1))
        if forecast:
            print('\n' + claim(venue, forecast), f"(matters: {matters(forecast) or 'no'})")
        return 0
    problems = boxscores.verify(STORE) if STORE.exists() else []
    if problems:
        sys.exit('Refusing to append to a weather store whose recorded lines changed:\n  ' + '\n  '.join(problems))
    STORE.mkdir(parents=True, exist_ok=True)
    publish()
    boxscores.write_json(STORE / 'ledger.json', boxscores.ledger(STORE))
    return 0


if __name__ == '__main__':
    sys.exit(main())
