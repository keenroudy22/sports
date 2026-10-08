import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dossier
import gates


NOW = datetime(2026, 10, 7, 22, tzinfo=timezone.utc)
GAME = {'id': 'NFL-1', 'league': 'NFL', 'season': 2026, 'kickoff': '2026-10-08T00:00:00Z',
        'home': {'id': '1', 'name': 'Home', 'abbreviation': 'HME'},
        'away': {'id': '2', 'name': 'Away', 'abbreviation': 'AWY'}}


class DossierTests(unittest.TestCase):
    def context(self):
        return gates.Context(now=NOW, games={GAME['id']: GAME}, injuries={
            'NFL-2': {'9': {'name': 'Away receiver', 'status': 'out', 'source': 'https://espn.example/injury',
                            'reportedAt': '2026-10-07T18:00:00Z'}}})

    def test_game_case_uses_checked_facts_weather_and_two_book_history(self):
        candidate = {'id': 'one', 'gameIds': [GAME['id']], 'marketType': 'total', 'direction': 'under',
                     'line': 48.5, 'odds': -110, 'book': 'FanDuel', 'projection': 43.2,
                     'quotedAt': '2026-10-07T21:00:00Z',
                     '_research': [{'claim': 'Starting receiver is out.', 'direction': 'for', 'kind': 'injury',
                                    'source': 'https://espn.example/injury', 'retrievedAt': '2026-10-07T21:00:00Z',
                                    'verified': True},
                                   {'claim': 'The opponent has scored 30+ twice.', 'direction': 'against',
                                    'kind': 'stats', 'verified': True}]}
        captures = [
            {'gameId': GAME['id'], 'retrievedAt': '2026-10-07T12:00:00Z', 'books': {
                'draftkings': {'total': {'line': 49.5, 'under': -110}},
                'fanduel': {'total': {'line': 49.5, 'under': -115}}}},
            {'gameId': GAME['id'], 'retrievedAt': '2026-10-07T21:00:00Z', 'books': {
                'draftkings': {'total': {'line': 48.5, 'under': -112}},
                'fanduel': {'total': {'line': 48.5, 'under': -110}}}}]
        forecast = {'source': 'https://weather.gov/hourly', 'forecast': {
            'source': 'https://weather.gov/hourly', 'windMph': 18, 'tempF': 50,
            'windDirection': 'NW', 'precipProb': 20, 'issuedAt': '2026-10-07T21:00:00Z'}}
        row = dossier.build(candidate, GAME, self.context(), [], NOW, captures=captures, weather_row=forecast)
        self.assertIsNone(row['line']['books']['DraftKings']['open'])
        self.assertEqual(row['line']['books']['DraftKings']['firstCaptured']['line'], 49.5)
        self.assertEqual(row['line']['books']['FanDuel']['now']['price'], -110)
        self.assertTrue(any('18 mph' in x['text'] for x in row['reasons']))
        self.assertTrue(any('30+' in x['text'] for x in row['risks']))
        self.assertFalse(any('30+' in x['text'] for x in row['reasons']))
        self.assertTrue(any('receiver' in x['text'] for x in row['reports']))
        self.assertEqual(row['weather']['windDirection'], 'NW')
        self.assertTrue(all(key in row for key in ('reasons', 'risks', 'reports', 'weather', 'line', 'ours',
                                                  'history', 'sources')))

    def test_failed_research_stays_partial_and_opposing_projection_is_risk(self):
        candidate = {'id': 'two', 'gameIds': [GAME['id']], 'marketType': 'total', 'direction': 'over',
                     'line': 48.5, 'odds': -110, 'book': 'DraftKings', 'projection': 43.2,
                     '_research': [{'claim': 'Unsupported claim', 'direction': 'for', 'verified': False}]}
        row = dossier.build(candidate, GAME, self.context(), [], NOW)
        self.assertTrue(row['partial'])
        self.assertEqual(row['reasons'], [])
        self.assertTrue(any('43.2' in x['text'] for x in row['risks']))
        self.assertNotIn('Unsupported', str(row))

    def test_college_no_injury_report_is_explicit_not_invented(self):
        game = dict(GAME, id='CFB-1', league='CFB')
        ctx = gates.Context(now=NOW, games={game['id']: game})
        candidate = {'id': 'three', 'gameIds': [game['id']], 'marketType': 'total', 'direction': 'under',
                     'line': 51.5, 'odds': -110, 'book': 'FanDuel'}
        row = dossier.build(candidate, game, ctx, [], NOW)
        self.assertIn('thin', row['reports'][0]['text'])
        self.assertEqual(row['line']['books'], {'DraftKings': None, 'FanDuel': None})

    def test_ticket_lists_real_legs_without_inventing_hit_rates(self):
        row = dossier.ticket({'book': 'FanDuel', 'odds': 522, 'why': 'Two easier lines, one per game.',
                              'risk': 'Both legs have to hit.', 'legs': [
                                  {'gameId': 'NFL-1', 'title': 'Home +6.5', 'line': 6.5, 'odds': -160},
                                  {'gameId': 'NFL-2', 'title': 'Away over 17.5', 'line': 17.5, 'odds': -150}]}, NOW)
        self.assertEqual(len(row['line']['legs']), 2)
        self.assertTrue(row['partial'])
        self.assertNotIn('chance', str(row).lower())


if __name__ == '__main__':
    unittest.main()
