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
    def test_long_captions_keep_whole_exact_preview_rows_and_all_graphic_evidence(self):
        from copy import deepcopy
        import x_post
        rows = [{'title': name, 'price': f'{i + 3} inside the 10', 'metric': f'{i + 8} red-zone opportunities',
                 'detail': '3 rush/rec TDs | 3/3 games observed', 'league': 'NFL', 'book': 'FanDuel'}
                for i, name in enumerate(('Bijan Robinson', 'Juwan Johnson', 'Tyler Shough', 'Chris Olave'))]
        original = deepcopy(rows)
        choice = {'kind': 'end-zone', 'title': 'END-ZONE WORK', 'text': 'x' * 352, 'rows': rows}
        text = R.bounded_caption(choice)
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertIn('Bijan Robinson', text)
        self.assertIn('8 red-zone opportunities · 3 inside the 10', text)
        self.assertNotIn('not official', text.lower())
        self.assertNotIn('save this', text.lower())
        self.assertEqual(choice['rows'], original)
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_each_research_family_has_a_bounded_fallback_even_for_long_names(self):
        import x_post
        for kind in ('end-zone', 'matchup', 'season', 'upset', 'spread-dog'):
            with self.subTest(kind=kind):
                choice = {'kind': kind, 'title': '90%+ TREND BOARD', 'text': 'x' * 900,
                          'rows': [{'title': 'Very Long Exact Player Name ' * 20, 'price': 'over 19.5 (-110)',
                                    'metric': '9/10 this season', 'book': 'FanDuel', 'league': 'NFL'}]}
                text = R.bounded_caption(choice)
                self.assertLessEqual(x_post.tweet_length(text), 280)
                self.assertNotIn('Very Long', text, 'never slice an impossible exact line in half')
                self.assertIn('Details on the card', text)
                self.assertNotIn('not official', text.lower())
                self.assertEqual(receipts.guard({'text': text}), [])
        self.assertEqual(R.bounded_caption({'text': 'Already short.'}), 'Already short.')

    def test_fresh_upset_has_priority_and_is_plainly_not_a_play(self):
        watch = {'side': 'home', 'team': 'Underdog', 'odds': 160, 'opponentOdds': -192,
                 'book': 'DraftKings', 'observedAt': '2026-10-03T13:30:00Z',
                 'modelChance': .60, 'marketChanceNoVig': .369,
                 'projectedFor': 27, 'projectedAgainst': 23, 'spreadGap': 7.5,
                 'reasons': ['Our score has Underdog by 4', "Underdog's offense rates 2.1 points above average"]}
        choice = R.select({'games': [game(watch)]}, {'CFB-1': {}}, NOW)
        self.assertEqual(choice['kind'], 'upset')
        self.assertIn('Underdog +160 ML (DK)', choice['text'])
        self.assertIn('Model 60% | market 37%', choice['text'])
        self.assertNotIn('not official', choice['text'].lower())
        self.assertEqual(choice['rows'][0]['metric'], 'Our score DOG 27–23 FAV')
        self.assertIn('7.5-pt gap vs spread', choice['rows'][0]['detail'])
        self.assertIn("offense rates 2.1 points above average", choice['rows'][0]['reason'])
        post = {'text': choice['text']}
        self.assertEqual(receipts.guard(post), [])

    def test_matchup_and_end_zone_are_fallbacks_not_streak_guarantees(self):
        detail = {'favoriteLines': [{'id': 'runner', 'sourceId': 'runner', 'kind': 'player',
                                     'title': 'Runner over 55.5 rushing yards', 'athleteId': '7',
                                     'book': 'FanDuel', 'odds': -110, 'projection': 70,
                                     'team': '1', 'teamAbbr': 'FAV', 'opponent': '2', 'opponentAbbr': 'DOG',
                                     'position': 'RB', 'stat': 'rushYds', 'direction': 'over',
                                     'edge': 3.0, 'observedAt': '2026-10-03T13:00:00Z',
                                     'history': {'last': {'hits': 8, 'games': 10, 'rate': 80}}}],
                  'scorerResearch': [{'player': 'Runner', 'athleteId': '7', 'games': 4, 'teamGames': 4,
                                      'redZone': 12, 'inside10': 7, 'touchdowns': 3,
                                      'roleSnapshotAt': '2026-10-02T12:00:00Z'}]}
        teams = {'CFB': {'defense': {'rows': {
            '2': {'RB': {'rushYds': 200}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '3': {'RB': {'rushYds': 100}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '4': {'RB': {'rushYds': 50}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
        }}}}
        choice = R.select({'games': [game()]}, {'CFB-1': detail}, NOW, teams=teams)
        self.assertEqual(choice['kind'], 'matchup')
        self.assertIn('Runner over 55.5 rushing yards', choice['text'])
        self.assertIn('8/10 at this line · DOG #3/3 vs RB rush yds', choice['text'])
        self.assertEqual(choice['title'], 'MATCHUP TRENDS')
        self.assertEqual(receipts.guard({'text': choice['text']}), [])
        detail['favoriteLines'][0]['history']['last']['rate'] = 70
        choice = R.select({'games': [game()]}, {'CFB-1': detail}, NOW, teams=teams)
        self.assertEqual(choice['kind'], 'end-zone')
        self.assertIn('12 red-zone opportunities · 7 inside the 10', choice['text'])

    def test_matchup_trends_rank_cfb_blowout_context_down_without_changing_the_line(self):
        safe = game()
        safe['id'] = 'CFB-safe'
        safe['v2'] = {'away': 27, 'home': 24}
        risk = game()
        risk['id'] = 'CFB-risk'
        risk['v2'] = {'away': 10, 'home': 35}
        def line(name, source, game_id, hits):
            return {'id': source, 'sourceId': source, 'kind': 'player', 'title': name,
                    'athleteId': source, 'book': 'FanDuel', 'odds': -110, 'projection': 70,
                    'team': '1', 'teamAbbr': 'FAV', 'opponent': '2', 'opponentAbbr': 'DOG',
                    'position': 'RB', 'stat': 'rushYds', 'direction': 'over', 'edge': 3.0,
                    'observedAt': '2026-10-03T13:00:00Z',
                    'history': {'last': {'hits': hits, 'games': 10, 'rate': hits * 10},
                                'season': {'hits': 3, 'games': 4, 'rate': 75}}}
        details = {'CFB-safe': {'favoriteLines': [line('Safe over 55.5 rushing yards', 'safe', 'CFB-safe', 8)]},
                   'CFB-risk': {'favoriteLines': [line('Risk over 55.5 rushing yards', 'risk', 'CFB-risk', 10)]}}
        teams = {'CFB': {'defense': {'rows': {
            '2': {'RB': {'rushYds': 200}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '3': {'RB': {'rushYds': 100}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '4': {'RB': {'rushYds': 50}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
        }}}}
        choice = R.matchup_candidate([risk, safe], details, NOW, teams)
        self.assertEqual([row['title'] for row in choice['rows']],
                         ['Safe over 55.5 rushing yards', 'Risk over 55.5 rushing yards'])
        self.assertTrue(choice['rows'][1]['scriptRisk'])
        self.assertEqual((choice['rows'][0]['seasonHits'], choice['rows'][0]['seasonGames']), (3, 4))
        self.assertIn('FAV projected 25-pt dog', choice['rows'][1]['detail'])
        self.assertIn('CFB big-underdog usage is ranked down', choice['text'])

    def test_spread_dogs_are_cover_watches_not_upset_calls(self):
        line = {'gameId': 'CFB-1', 'gameMarket': True, 'market': 'point spread', 'state': 'open',
                'line': 8.5, 'odds': -105, 'book': 'ESPN BET', 'side': 'home',
                'observedAt': '2026-10-03T13:30:00Z',
                'grade': {'tier': 'lean', 'chance': .54, 'needs': .512, 'edge': 2.8, 'projection': 1.0}}
        choice = R.select({'games': [game()]}, {'CFB-1': {}}, NOW, [line])
        self.assertEqual(choice['kind'], 'spread-dog')
        self.assertIn('Underdog +8.5 (-105) ESPN', choice['text'])
        self.assertNotIn('not an upset', choice['text'].lower())
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
            self.assertIn('UNDERDOG RESEARCH', card)
            self.assertNotIn('NOT A PLAY', card)
            for ugly in ('#8b4513', '#a0522d', '#cd853f'):
                self.assertNotIn(ugly, card.lower())


if __name__ == '__main__':
    unittest.main()
