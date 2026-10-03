import sys
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research_views as R

NOW = datetime(2026, 10, 2, 15, tzinfo=timezone.utc)


class ResearchViewsTests(unittest.TestCase):
    def card(self):
        return {'state': 'pre', 'kickoff': '2026-10-03T17:00:00Z', 'league': 'CFB',
                'home': {'name': 'Home'}, 'away': {'name': 'Away'},
                'v2': {'home': 27.0, 'away': 23.0, 'margin': 4.0,
                       'winProb': .6, 'publishedAt': '2026-10-02T12:00:00Z'},
                'market': {'homeML': 160, 'awayML': -192, 'book': 'DraftKings',
                           'spread': 3.5, 'spreadMove': 4.0, 'retrievedAt': '2026-10-02T14:00:00Z'}}

    def test_upsets_are_outright_not_cover_leans(self):
        card = self.card()
        snapshot = {'inputs': {'ratings': {'home': {'margin': {'off': 2.2, 'def': -1.4}},
                                                   'away': {'margin': {'off': -1.3, 'def': 1.8}}}}}
        watch = R.upset_watch(card, NOW, snapshot)
        self.assertEqual(watch['side'], 'home')
        self.assertEqual((watch['modelMargin'], watch['marketSpread'], watch['spreadGap']), (4.0, 3.5, 7.5))
        self.assertTrue(any(reason.startswith('Our score has Home 27.0, Away 23.0') for reason in watch['reasons']))
        self.assertTrue(any("Home's offense" in reason for reason in watch['reasons']))
        self.assertTrue(any('spread has moved 4 points' in warning for warning in watch['warnings']))
        card['v2']['winProb'] = .4
        self.assertIsNone(R.upset_watch(card, NOW))
        card['market'].update(homeML=-192, awayML=160)
        self.assertEqual(R.upset_watch(card, NOW)['side'], 'away')

    def test_missing_stale_future_thin_and_started_do_not_qualify(self):
        mutations = [('market', 'awayML', None), ('market', 'homeML', float('nan')),
                     ('market', 'retrievedAt', '2026-10-01T14:00:00Z'),
                     ('market', 'retrievedAt', '2026-10-03T14:00:00Z'), ('v2', 'sparse', True),
                     ('v2', 'publishedAt', '2026-09-30T00:00:00Z')]
        for group, key, value in mutations:
            card = self.card()
            card[group][key] = value
            self.assertIsNone(R.upset_watch(card, NOW))
        for key, value in [('fcs', True), ('completed', True), ('state', 'in')]:
            card = self.card()
            card[key] = value
            self.assertIsNone(R.upset_watch(card, NOW))

    def test_scorer_work_does_not_count_passing_tds_or_missing_pbp(self):
        game = {'state': 'pre', 'kickoff': '2026-10-03T17:00:00Z', 'season': 2026,
                'home': {'id': '1'}, 'away': {'id': '2'}}
        snapshot = {'publishedAt': '2026-10-02T12:00:00Z',
                    'players': {'home': {'players': [{'id': 'q', 'pos': 'QB', 'carries': [4]}]}}}
        records = [{'season': 2026, 'seasonType': 2, 'kickoff': f'2026-09-{d:02}T17:00:00Z',
                    'teams': {'1': {}}, 'quality': {'plays': 'ok'},
                    'players': [{'id': 'q', 'team': '1', 'passTD': 4, 'rzCar': 2, 'i10Car': 1, 'rushTD': 1}]}
                   for d in (1, 8, 15)]
        result = R.scorer_research(game, snapshot, records, {'q': 'Quarterback'}, NOW)
        self.assertEqual(result[0]['touchdowns'], 3)
        self.assertEqual(result[0]['redZone'], 6)
        self.assertEqual(result[0]['roleSnapshotAt'], snapshot['publishedAt'])
        old_snapshot = deepcopy(snapshot)
        old_snapshot['publishedAt'] = '2026-09-01T00:00:00Z'
        self.assertEqual(R.scorer_research(game, old_snapshot, records, {}, NOW), [])
        records[0]['quality']['plays'] = 'failed'
        self.assertEqual(R.scorer_research(game, snapshot, records, {}, NOW), [])

    def test_health_missing_and_future_are_not_current(self):
        rows = R.health({'slate': None, 'props': '2026-10-03T00:00:00Z'}, NOW)
        self.assertEqual([r['status'] for r in rows], ['missing', 'stale'])
