import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import receipts
import research_posts as R


NOW = datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc)  # 10 AM ET


def game(watch=None):
    row = {'id': 'CFB-1', 'league': 'CFB', 'kickoff': '2026-10-03T17:00:00Z', 'state': 'pre',
           'away': {'id': '1', 'abbr': 'FAV', 'name': 'Favorite'},
           'home': {'id': '2', 'abbr': 'DOG', 'name': 'Underdog'}}
    if watch:
        row['upsetWatch'] = watch
    return row


class ResearchPostTests(unittest.TestCase):
    def test_fresh_upset_has_priority_and_is_plainly_not_a_play(self):
        watch = {'side': 'home', 'team': 'Underdog', 'odds': 160, 'opponentOdds': -192,
                 'book': 'DraftKings', 'observedAt': '2026-10-03T13:30:00Z',
                 'modelChance': .60, 'marketChanceNoVig': .369}
        choice = R.select({'games': [game(watch)]}, {'CFB-1': {}}, NOW)
        self.assertEqual(choice['kind'], 'upset')
        self.assertIn('Underdog +160 ML (DK) | model 60% | market 37%', choice['text'])
        self.assertIn('Research only, not official plays.', choice['text'])
        post = {'text': choice['text']}
        self.assertEqual(receipts.guard(post), [])

    def test_matchup_and_end_zone_are_fallbacks_not_streak_guarantees(self):
        detail = {'favoriteLines': [{'title': 'Runner over 55.5 rushing yards', 'athleteId': '7',
                                     'book': 'FanDuel', 'odds': -110, 'projection': 70,
                                     'edge': 3.0, 'observedAt': '2026-10-03T13:00:00Z',
                                     'history': {'last': {'hits': 8, 'games': 10, 'rate': 80}}}],
                  'scorerResearch': [{'player': 'Runner', 'athleteId': '7', 'games': 4, 'teamGames': 4,
                                      'redZone': 12, 'inside10': 7, 'touchdowns': 3,
                                      'roleSnapshotAt': '2026-10-02T12:00:00Z'}]}
        choice = R.select({'games': [game()]}, {'CFB-1': detail}, NOW)
        self.assertEqual(choice['kind'], 'matchup')
        self.assertIn('History does not predict the next game', choice['text'])
        self.assertEqual(receipts.guard({'text': choice['text']}), [])
        detail['favoriteLines'][0]['history']['last']['rate'] = 70
        choice = R.select({'games': [game()]}, {'CFB-1': detail}, NOW)
        self.assertEqual(choice['kind'], 'end-zone')
        self.assertIn('not TD probability', choice['text'])

    def test_spread_dogs_are_cover_watches_not_upset_calls(self):
        line = {'gameId': 'CFB-1', 'gameMarket': True, 'market': 'point spread', 'state': 'open',
                'line': 8.5, 'odds': -105, 'book': 'ESPN BET', 'side': 'home',
                'observedAt': '2026-10-03T13:30:00Z',
                'grade': {'tier': 'lean', 'chance': .54, 'needs': .512, 'edge': 2.8, 'projection': 1.0}}
        choice = R.select({'games': [game()]}, {'CFB-1': {}}, NOW, [line])
        self.assertEqual(choice['kind'], 'spread-dog')
        self.assertIn('Cover research, not an upset call', choice['text'])
        self.assertIn('Underdog +8.5 (-105)', choice['text'])

    def test_post_window_and_card_are_stale_safe(self):
        watch = {'side': 'home', 'team': 'Underdog', 'odds': 160, 'opponentOdds': -192,
                 'book': 'DraftKings', 'observedAt': '2026-10-03T13:30:00Z',
                 'modelChance': .60, 'marketChanceNoVig': .369}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'games').mkdir()
            (root / 'today.json').write_text(__import__('json').dumps({'games': [game(watch)]}))
            (root / 'games' / 'CFB-1.json').write_text('{}')
            post = R.post({}, NOW, root / 'today.json', root / 'games')
            self.assertEqual((post['kind'], post['card']), ('research', 'research-upset-2026-10-03'))
            self.assertEqual(post['due'], datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc))
            choice = R.select({'games': [game(watch)]}, {'CFB-1': {}}, NOW)
            card = R.svg(choice)
            self.assertIn('UNDERDOG WATCH', card)
            self.assertIn('RESEARCH · NOT A PLAY', card)
            for ugly in ('#8b4513', '#a0522d', '#cd853f'):
                self.assertNotIn(ugly, card.lower())


if __name__ == '__main__':
    unittest.main()
