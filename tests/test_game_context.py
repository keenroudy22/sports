"""Existing-store context for game explanations and the college slate navigator."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import game_context


NOW = datetime(2026, 10, 7, 20, tzinfo=timezone.utc)
GAME = {'id': 'CFB-1', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-10T16:00:00Z',
        'home': {'id': '1', 'conference': 'ACC', 'rank': 9}, 'away': {'id': '2', 'conference': 'Sun Belt'}}
CARD = {'id': 'CFB-1', 'home': {'id': '1', 'name': 'Pitt', 'strength': {'offense': 9, 'defense': 22, 'teams': 136}},
        'away': {'id': '2', 'name': 'Georgia State', 'strength': {'offense': 84, 'defense': 102, 'teams': 136}},
        'market': {'spread': -4, 'total': 53.5, 'spreadOpen': -3, 'totalOpen': 52.5,
                   'book': 'DraftKings', 'retrievedAt': '2026-10-07T19:30:00Z'},
        'v2': {'margin': 14.6, 'total': 50.5}}


def row(market, side, line, athlete=None, **other):
    return {'gameId': 'CFB-1', 'market': market, 'direction': side, 'line': line, 'book': 'DraftKings',
            'odds': -110, 'observedAt': '2026-10-07T19:30:00Z', 'state': 'open',
            **({'athleteId': athlete, 'stat': 'recYds'} if athlete else {}), **other}


class NavigatorTests(unittest.TestCase):
    def test_tier_window_gap_and_stable_bettable_parts(self):
        rows = [row('total points', 'over', 53.5), row('total points', 'under', 53.5)]
        nav = game_context.navigator(GAME, CARD, rows, [], NOW)
        self.assertEqual(nav['tier'], 'competitive')
        self.assertEqual(nav['window'], 'noon')
        self.assertEqual(nav['gap'], {'model': 14.6, 'book': 4.0, 'difference': 10.6})
        self.assertEqual(nav['conference']['home'], 'ACC')
        self.assertTrue(nav['bettableParts']['total'])
        self.assertFalse(nav['bettableParts']['spread'], 'a lone side is not a priced pair')
        self.assertIsInstance(nav['bettable'], int)
        self.assertEqual(nav, game_context.navigator(GAME, CARD, list(reversed(rows)), [], NOW))

    def test_blown_out_prop_flag_and_window_boundaries(self):
        for spread, tier in ((-7, 'competitive'), (-10, 'lean'), (-17, 'mismatch'), (-21, 'blowout')):
            card = {**CARD, 'market': {**CARD['market'], 'spread': spread}}
            nav = game_context.navigator(GAME, card, [], [], NOW)
            self.assertEqual(nav['tier'], tier)
            self.assertEqual(nav['garbageTime'], abs(spread) >= 21)
        for kickoff, window in (('2026-10-10T19:30:00Z', 'afternoon'),
                                ('2026-10-10T23:00:00Z', 'night')):
            self.assertEqual(game_context.navigator({**GAME, 'kickoff': kickoff}, CARD, [], [], NOW)['window'], window)

    def test_old_price_never_raises_bettable_price_score(self):
        old = {**CARD, 'market': {**CARD['market'], 'retrievedAt': '2026-10-06T19:00:00Z'}}
        nav = game_context.navigator(GAME, old, [row('total points', 'over', 53.5),
                                                   row('total points', 'under', 53.5)], [], NOW)
        self.assertFalse(nav['bettableParts']['total'])
        self.assertIn('older than four hours', nav['plainGap'])


class WhyDifferTests(unittest.TestCase):
    def test_spread_uses_real_ranks_and_soft_schedule_caution(self):
        log = [{'kickoff': '2026-10-01T16:00Z', 'pointsFor': 20, 'pointsAgainst': 10, 'opp': 'x'},
               {'kickoff': '2026-10-02T16:00Z', 'pointsFor': 25, 'pointsAgainst': 12, 'opp': 'y'},
               {'kickoff': '2026-10-03T16:00Z', 'pointsFor': 30, 'pointsAgainst': 13, 'opp': 'z'}]
        ranks = {key: {'offense': 100, 'defense': 110, 'teams': 136} for key in ('x', 'y', 'z')}
        ranks['1'] = CARD['home']['strength']
        result = game_context.why_differ(GAME, CARD, None, {'1': log}, ranks, {}, [], NOW)
        self.assertEqual(result['kind'], 'spread')
        self.assertIn("Pitt's offense ranks 9 of 136", result['text'])
        self.assertTrue(any(d.get('flag') == 'soft_schedule' for d in result['drivers']))
        self.assertLessEqual(len(result['text']), 220)
        self.assertNotIn('pipeline', result['text'].lower())

    def test_total_recent_scores_qb_news_and_stale_line(self):
        card = {**CARD, 'market': {**CARD['market'], 'spread': -14, 'total': 57.5},
                'v2': {**CARD['v2'], 'margin': 14, 'total': 50.5}}
        log = [{'kickoff': f'2026-10-0{i}T16:00Z', 'pointsFor': 20, 'pointsAgainst': 18,
                'opp': 'x'} for i in (1, 2, 3)]
        result = game_context.why_differ(GAME, card, None, {'1': log}, {}, {},
                                         [row('receiving yards', 'over', 49.5, '5', roleHold='qb')], NOW)
        self.assertEqual(result['kind'], 'total')
        self.assertIn('38, 38, 38', result['text'])
        self.assertEqual(result['caution'], 'Recent quarterback changes put receiving roles in this game under review.')
        stale = {**card, 'market': {**card['market'], 'retrievedAt': '2026-10-06T15:00Z'}}
        self.assertEqual(game_context.why_differ(GAME, stale, None, {}, {}, {}, [], NOW),
                         {'stale': True, 'text': 'The book line is older than four hours; check a current price.',
                          'drivers': []})
        close = {**CARD, 'v2': {**CARD['v2'], 'margin': 4, 'total': 53}}
        self.assertIsNone(game_context.why_differ(GAME, close, None, {}, {}, {}, [], NOW))

    def test_kickoff_weather_uses_only_a_recent_stored_forecast(self):
        card = {**CARD, 'market': {**CARD['market'], 'spread': -14, 'total': 57.5},
                'v2': {**CARD['v2'], 'margin': 14, 'total': 50.5}}
        weather = {'forecast': {'issuedAt': '2026-10-07T18:00Z', 'periodStart': GAME['kickoff'],
                                'windMph': 19, 'precipProb': 65}}
        result = game_context.why_differ(GAME, card, None, {}, {}, {}, [], NOW, weather)
        self.assertTrue(any(d.get('flag') == 'weather' for d in result['drivers']))
        old = {'forecast': {**weather['forecast'], 'issuedAt': '2026-10-05T18:00Z'}}
        result = game_context.why_differ(GAME, card, None, {}, {}, {}, [], NOW, old)
        self.assertFalse(any(d.get('flag') == 'weather' for d in result['drivers']))


if __name__ == '__main__':
    unittest.main()
