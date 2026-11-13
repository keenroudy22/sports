import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sport_box


class NBASummaryTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((Path(__file__).parent / 'fixtures/espn/nba-401859967-summary.json').read_text())

    def extract(self):
        return sport_box.extract(self.payload, '401859967', '2026-10-09T18:00:00Z')

    def test_real_final_keys_dnp_and_postseason_are_preserved(self):
        row = self.extract()
        self.assertEqual((row['season'], row['seasonType'], len(row['players'])), (2026, 3, 30))
        og = next(p for p in row['players'] if p['id'] == '3934719')
        self.assertEqual(og['stats']['pts'], 11)
        self.assertEqual((og['stats']['fgm'], og['stats']['fga'], og['stats']['fg3m']), (3, 11, 1))
        self.assertEqual(og['stats']['pra'], 19)
        self.assertEqual(og['stats']['min'], 33)
        self.assertEqual(og['group'], 'F')
        self.assertTrue(all(p['stats'] == {} for p in row['players'] if p['dnp']))

    def test_missing_stat_does_not_create_zero_or_combination(self):
        group = self.payload['boxscore']['players'][0]['statistics'][0]
        group['athletes'][0]['stats'][group['keys'].index('points')] = '--'
        stats = self.extract()['players'][0]['stats']
        self.assertNotIn('pts', stats); self.assertNotIn('pra', stats)

    def test_keys_drive_stats_even_after_column_reorder(self):
        group = self.payload['boxscore']['players'][0]['statistics'][0]
        group['keys'].reverse()
        for a in group['athletes']: a['stats'].reverse()
        self.assertEqual(self.extract()['players'][0]['stats']['pts'], 11)

    def test_minutes_seconds(self):
        group = self.payload['boxscore']['players'][0]['statistics'][0]
        group['athletes'][0]['stats'][0] = '33:30'
        self.assertEqual(self.extract()['players'][0]['stats']['min'], 33.5)

    def test_mismatched_event_league_unfinished_and_missing_columns_refused(self):
        original = copy.deepcopy(self.payload)
        for edit in ('event', 'league', 'unfinished', 'columns', 'duplicate'):
            self.payload = copy.deepcopy(original)
            if edit == 'event': self.payload['header']['id'] = '123'
            elif edit == 'league': self.payload['header']['league']['slug'] = 'nfl'
            elif edit == 'unfinished': self.payload['header']['competitions'][0]['status']['type']['completed'] = False
            elif edit == 'columns': self.payload['boxscore']['players'][0]['statistics'][0]['athletes'][0]['stats'].pop()
            else:
                group = self.payload['boxscore']['players'][0]['statistics'][0]
                group['athletes'].append(group['athletes'][0])
            with self.assertRaises(ValueError): self.extract()

    def test_preseason_is_flagged_never_reclassified(self):
        self.payload['header']['season'] = {'year': 2027, 'type': 1}
        self.assertEqual(self.extract()['seasonType'], 1)

    def test_college_box_uses_the_same_verified_stat_contract(self):
        self.payload['header']['league'] = {'id': '41', 'slug': 'mens-college-basketball'}
        row = sport_box.extract(self.payload, '401859967', '2026-10-09T18:00:00Z', 'CBB')
        self.assertEqual((row['league'], row['eventId']), ('CBB', 'CBB-401859967'))
        self.assertIn('/mens-college-basketball/summary?', row['source'])
        self.assertNotIn('quarterEvidence', row)
        self.assertEqual(row['players'][0]['stats']['pts'], 11)

    def test_college_box_rejects_an_nba_identity(self):
        with self.assertRaises(ValueError):
            sport_box.extract(self.payload, '401859967', '2026-10-09T18:00:00Z', 'CBB')

    def test_college_capture_covers_later_matchups_before_deepening_early_ones(self):
        now = datetime(2026, 11, 13, 15, tzinfo=timezone.utc)
        games = [
            {'id': str(i), 'season': 2027, 'status': 'scheduled', 'kickoff': '2026-11-14T00:00:00Z',
             'teams': {'away': {'id': str(i)}, 'home': {'id': str(100 + i)}}}
            for i in range(10)
        ]
        history = [
            {'eventId': f'{depth}{i}', 'season': 2027, 'away': {'id': str(i)}, 'home': {'id': str(100 + i)}}
            for depth in range(3) for i in range(10)
        ]
        history.insert(0, {**history[0], 'eventId': 'old', 'season': 2026})
        ordered = sport_box.cbb_capture_order(games, history, {'CBB-00': {}}, now)
        self.assertEqual(ordered[:9], [f'0{i}' for i in range(1, 10)])
        self.assertEqual(ordered[9], '10')
        self.assertNotIn('old', ordered)
        self.assertEqual(len(ordered), len(set(ordered)))


if __name__ == '__main__': unittest.main()
