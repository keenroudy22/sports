import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import venues
import weather

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
KICKOFF = datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc)
POINTS = {'properties': {'forecastHourly': 'https://api.weather.gov/gridpoints/GRR/1,1/forecast/hourly'}}
HOURLY = {'properties': {'updateTime': '2026-09-24T11:00:00+00:00', 'periods': [
    {'startTime': '2026-09-27T12:00:00-04:00', 'endTime': '2026-09-27T13:00:00-04:00', 'temperature': 61, 'windSpeed': '10 to 15 mph',
     'windDirection': 'W', 'windGust': '25 mph', 'probabilityOfPrecipitation': {'value': 10}, 'shortForecast': 'Mostly Sunny'},
    {'startTime': '2026-09-27T13:00:00-04:00', 'endTime': '2026-09-27T14:00:00-04:00', 'temperature': 63, 'windSpeed': '20 mph',
     'windDirection': 'W', 'windGust': '30 mph', 'probabilityOfPrecipitation': {'value': 5}, 'shortForecast': 'Sunny'}]}}
ESPN_VENUE = {'fullName': 'Ford Field', 'indoor': True, 'grass': False, 'address': {'city': 'Detroit', 'state': 'MI', 'country': 'USA'}}
GEOCODE = {'results': [{'name': 'Detroit', 'country_code': 'US', 'admin1': 'Michigan', 'latitude': 42.33143, 'longitude': -83.04575, 'population': 670031},
                       {'name': 'Detroit', 'country_code': 'US', 'admin1': 'Oregon', 'latitude': 44.7, 'longitude': -122.1, 'population': 200}]}


def fake_fetch(url, timeout=20, headers=None):
    if 'api.weather.gov/points' in url:
        return POINTS
    if 'forecast/hourly' in url:
        return HOURLY
    if 'venues/' in url:
        return ESPN_VENUE
    if 'geocoding-api' in url:
        return GEOCODE
    raise AssertionError(url)


class ForecastTests(unittest.TestCase):
    def test_the_kickoff_hour_is_read_with_the_top_of_a_wind_range(self):
        forecast = weather.forecast_for(42.33, -83.05, KICKOFF, fake_fetch, NOW)
        self.assertEqual(forecast['windMph'], 20)
        self.assertEqual(forecast['gustMph'], 30)
        self.assertEqual(forecast['precipProb'], 5)
        self.assertEqual(forecast['tempF'], 63)
        self.assertEqual(forecast['periodStart'], '2026-09-27T13:00:00-04:00')
        self.assertEqual(forecast['source'], POINTS['properties']['forecastHourly'])
        self.assertEqual(weather.mph('10 to 15 mph'), 15)
        self.assertIsNone(weather.mph(None))

    def test_beyond_the_horizon_or_outside_the_periods_is_none(self):
        self.assertIsNone(weather.forecast_for(42.33, -83.05, NOW + timedelta(days=9), fake_fetch, NOW))
        self.assertIsNone(weather.forecast_for(42.33, -83.05, NOW + timedelta(days=1), fake_fetch, NOW), 'no period covers that hour')

    def test_what_matters_and_the_fact_direction_follow_the_side(self):
        forecast = weather.forecast_for(42.33, -83.05, KICKOFF, fake_fetch, NOW)
        self.assertEqual(weather.matters(forecast), 'wind 20 mph')
        self.assertIsNone(weather.matters({'windMph': 8, 'precipProb': 10, 'tempF': 60}))
        self.assertEqual(weather.matters({'windMph': 8, 'precipProb': 70, 'tempF': 20}), '70% chance of precipitation, 20 degrees')
        venue = {'name': 'Ford Field'}
        game = {'id': 'NFL-1'}
        self.assertEqual(weather.fact_for(game, venue, forecast, NOW, 'over')['direction'], 'against')
        self.assertEqual(weather.fact_for(game, venue, forecast, NOW, 'under')['direction'], 'for')
        self.assertEqual(weather.fact_for(game, venue, forecast, NOW, 'home')['direction'], 'neutral')
        calm = weather.fact_for(game, venue, {'windMph': 5, 'precipProb': 0, 'tempF': 70, 'source': 'https://x', 'shortForecast': 'Clear'}, NOW, 'over')
        self.assertEqual(calm['direction'], 'neutral')
        self.assertIn('wind 20 mph gusting 30 from the W, 5% chance of precipitation, 63 degrees, sunny.', weather.fact_for(game, venue, forecast, NOW)['claim'])
        self.assertIsNone(weather.fact_for(game, venue, None, NOW))


class VenueTests(unittest.TestCase):
    def test_describe_and_geocode_prefer_the_us_city_in_the_right_state(self):
        entry = venues.describe('NFL', '3727', fake_fetch)
        self.assertEqual(entry['name'], 'Ford Field')
        self.assertTrue(entry['indoor'])
        point = venues.geocode('Detroit', 'MI', fake_fetch)
        self.assertAlmostEqual(point['lat'], 42.3314, places=3)
        self.assertAlmostEqual(point['lon'], -83.0458, places=3)
        self.assertIsNone(venues.geocode('Detroit', 'ZZ', fake_fetch), 'an unknown state matches nothing')
        self.assertIsNone(venues.geocode(None, 'MI', fake_fetch))

    def test_build_adds_only_missing_venues_and_lists_the_unplaced(self):
        records = [{'league': 'NFL', 'venue': {'id': '3727', 'name': 'Ford Field'}, 'home': {'id': '8'}, 'neutral': False},
                   {'league': 'NFL', 'venue': {'id': '1', 'name': 'Known'}, 'home': {'id': '9'}, 'neutral': False}]
        table, review = venues.build(records, table={'NFL-1': {'id': '1', 'lat': 1.0, 'lon': 1.0, 'indoor': False}}, fetch=fake_fetch, log=lambda *_: None, pause=0)
        self.assertEqual(set(table), {'NFL-1', 'NFL-3727'})
        self.assertTrue(table['NFL-3727']['indoor'])
        self.assertEqual(table['NFL-3727']['lat'], 42.3314)
        self.assertEqual(review, [])

        def failing(url, timeout=20, headers=None):
            raise OSError('down')
        table, review = venues.build([{'league': 'CFB', 'venue': {'id': '5', 'name': 'X'}, 'home': {'id': '1'}, 'neutral': False}], table={}, fetch=failing, log=lambda *_: None, pause=0)
        self.assertIsNone(table['CFB-5']['lat'])
        self.assertEqual(review[0]['key'], 'CFB-5')

    def test_venue_for_uses_the_slate_venue_then_the_home_teams_usual_one(self):
        records = [{'league': 'NFL', 'venue': {'id': '3727'}, 'home': {'id': '8'}, 'neutral': False},
                   {'league': 'NFL', 'venue': {'id': '3727'}, 'home': {'id': '8'}, 'neutral': False},
                   {'league': 'NFL', 'venue': {'id': '99'}, 'home': {'id': '8'}, 'neutral': True}]
        usual = venues.usual_venues(records)
        self.assertEqual(usual[('NFL', '8')], '3727')
        table = {'NFL-3727': {'id': '3727', 'name': 'Ford Field'}, 'NFL-42': {'id': '42', 'name': 'Elsewhere'}}
        self.assertEqual(venues.venue_for({'league': 'NFL', 'home': {'id': '8'}, 'venue': {'id': '42'}}, table, usual)['name'], 'Elsewhere')
        self.assertEqual(venues.venue_for({'league': 'NFL', 'home': {'id': '8'}}, table, usual)['name'], 'Ford Field')
        self.assertIsNone(venues.venue_for({'league': 'NFL', 'home': {'id': '8'}, 'neutral': True}, table, usual), 'a neutral site without a venue is unknown')


if __name__ == '__main__':
    unittest.main()
