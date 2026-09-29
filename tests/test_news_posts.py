import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import news_posts

NOW = datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc)
REPORTED = '2026-10-01T15:00:00Z'
GAME = {'id': 'NFL-1', 'league': 'NFL', 'season': 2026, 'state': 'pre', 'kickoff': '2026-10-02T00:15:00Z',
        'away': {'id': '1', 'abbreviation': 'PHI'}, 'home': {'id': '2', 'abbreviation': 'CHI'}}
OLD = {'gameId': 'NFL-1', 'publishedAt': '2026-10-01T14:00:00Z',
       'players': {'away': {'players': [
           {'id': '7', 'pos': 'WR', 'targets': [10.0, 5.0, 15.0]},
           {'id': '8', 'pos': 'WR', 'targets': [7.0, 3.0, 11.0], 'recYds': [68.0, 20.0, 116.0]}]},
                   'home': {'players': []}}, 'inputs': {'ruledOut': {'away': [], 'home': []}}}
NEW = {'gameId': 'NFL-1', 'publishedAt': '2026-10-01T15:30:00Z',
       'players': {'away': {'players': [
           {'id': '8', 'pos': 'WR', 'targets': [10.0, 5.0, 15.0], 'recYds': [88.0, 30.0, 146.0]}]},
                   'home': {'players': []}}, 'inputs': {'ruledOut': {'away': ['7'], 'home': []}}}
LINE = {'gameId': 'NFL-1', 'state': 'open', 'athleteId': '8', 'player': 'DeVonta Smith', 'position': 'WR',
        'stat': 'recYds', 'market': 'receiving yards', 'direction': 'over', 'line': 71.5, 'odds': -112,
        'book': 'DraftKings', 'observedAt': '2026-10-01T15:45:00Z',
        'grade': {'view': 'lean', 'limited': False, 'edge': 4.2, 'snapshotAt': '2026-10-01T15:30:00Z'}}


def context(injured='7'):
    injury = {'name': 'A.J. Brown', 'position': 'WR', 'status': 'Out', 'injury': 'Hamstring',
              'reportedAt': REPORTED, 'source': 'https://www.espn.com/nfl/player/_/id/7/aj-brown'}
    ctx = SimpleNamespace(games={'NFL-1': GAME}, snapshots={'NFL-1': [OLD, NEW]}, starters={},
                          injuries={'NFL-1': {injured: injury}})
    ctx.snapshot = lambda gid: NEW
    return ctx


def defense_game():
    return {'eventId': 'old', 'league': 'NFL', 'season': 2026, 'seasonType': 2, 'week': 1,
            'kickoff': '2026-09-20T17:00:00Z', 'neutral': False,
            'home': {'id': '2', 'score': 20}, 'away': {'id': '3', 'score': 17},
            'teams': {'2': {'points': 20}, '3': {'points': 17}},
            'players': [{'id': '20', 'team': '3', 'name': 'Receiver', 'pos': 'WR',
                         'rec': 8, 'recYds': 120, 'tgt': 11}], 'quality': {'plays': 'ok'},
            'sources': {'page': 'https://www.espn.com/nfl/boxscore/_/gameId/old'}}


class InjuryPostTests(unittest.TestCase):
    def test_verified_star_news_gets_a_post_injury_prop_and_matchup_stat(self):
        posts = news_posts.candidates(context(), [defense_game()], [LINE], NOW, {'posts': []})
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post['key'], 'news:NFL-1:7:out')
        self.assertIn('ESPN lists A.J. Brown OUT', post['text'])
        self.assertIn('DeVonta Smith over 71.5 receiving yards (-112, DraftKings)', post['text'])
        self.assertIn('CHI allows 120 receiving yards/game to WRs through 1 game.', post['text'])
        self.assertIn('Board lean, not a posted play.', post['text'])
        self.assertLessEqual(news_posts.x_post.tweet_length(post['text']), 280)

    def test_stale_prices_stale_news_and_duplicates_do_not_post(self):
        stale_price = dict(LINE, observedAt='2026-10-01T14:45:00Z')
        self.assertEqual(news_posts.candidates(context(), [], [stale_price], NOW, {'posts': []}), [])
        logged = {'posts': [{'id': 'news:NFL-1:7:out'}]}
        self.assertEqual(news_posts.candidates(context(), [], [LINE], NOW, logged), [])
        full_day = {'posts': [{'id': 'n1', 'kind': 'buffer:news', 'dueAt': '2026-10-01T13:00:00Z'},
                              {'id': 'n2', 'kind': 'buffer:news', 'dueAt': '2026-10-01T14:00:00Z'}]}
        self.assertEqual(news_posts.candidates(context(), [], [LINE], NOW, full_day), [])
        stale = context()
        stale.injuries['NFL-1']['7'] = dict(stale.injuries['NFL-1']['7'], reportedAt='2026-09-30T15:00:00Z')
        self.assertEqual(news_posts.candidates(stale, [], [LINE], NOW, {'posts': []}), [])

    def test_a_depth_player_and_a_projection_that_did_not_remove_the_star_do_not_post(self):
        depth = context('8')
        depth.injuries['NFL-1']['8'] = dict(depth.injuries['NFL-1']['8'], name='Depth Receiver')
        self.assertEqual(news_posts.candidates(depth, [], [LINE], NOW, {'posts': []}), [])
        unchanged = context()
        unchanged.snapshot = lambda gid: OLD
        self.assertEqual(news_posts.candidates(unchanged, [], [LINE], NOW, {'posts': []}), [])


if __name__ == '__main__':
    unittest.main()
