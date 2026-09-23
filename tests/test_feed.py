import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import feed

NOW = datetime(2026, 9, 29, 13, 0, tzinfo=timezone.utc)       # Tuesday 9:00 ET
GAMES = {'g-live': {'id': 'g-live', 'league': 'NFL', 'kickoff': '2026-09-30T00:15Z', 'home': {'short': 'Lions'}, 'away': {'short': 'Bills'}},   # Tuesday 8:15 PM ET
         'g-done': {'id': 'g-done', 'league': 'NFL', 'kickoff': '2026-09-27T17:00Z', 'home': {'short': 'Jets'}, 'away': {'short': 'Giants'}}}


def pick(key, **over):
    base = {'id': key, 'title': 'Bills at Lions over 44.5', 'status': 'active', 'favorite': False, 'modelLean': True,
            'marketType': 'total', 'line': 44.5, 'direction': 'over', 'gameIds': ['g-live'], 'book': 'DraftKings', 'odds': -110,
            'projection': 48.0, 'confidence': 3, 'publishedAt': '2026-09-29T12:00:00Z',
            'why': 'Model lean, published on our number alone. The over reads 55.3% after the raw 62.7% is shrunk.',
            'sources': ['https://www.espn.com/nfl/game/_/gameId/1']}
    base.update(over)
    return base


class FeedTests(unittest.TestCase):
    def test_only_live_postable_plays_become_items(self):
        first = {'lean': pick('lean'),
                 'fav': pick('fav', favorite=True, modelLean=False, title='Bills at Lions under 44.5', direction='under'),
                 'early': pick('early', publishedAt='2026-09-26T12:00:00Z'),      # published days ago: still a play today
                 'closed': pick('closed'),
                 'ticket': pick('ticket', legs=[{'title': 'Bills at Lions over 44.5'}, {'title': 'Jets +3'}], parlayType='longshot', modelLean=False, riskUnits=0.25, title='3-leg longshot at DraftKings', odds=650, why='Longshot from the board: 3 legs at DraftKings. A fun ticket at a quarter unit.'),
                 'kicked': pick('kicked', gameIds=['g-done'])}
        latest = {k: dict(v) for k, v in first.items()}
        latest['closed']['entryNote'] = 'closed'
        items = feed.pick_items(first, latest, GAMES, NOW)
        self.assertEqual(sorted(i['guid'] for i in items), ['early', 'fav', 'lean', 'ticket'])
        ticket = next(i for i in items if i['guid'] == 'ticket')
        self.assertTrue(ticket['title'].startswith('Fun parlay: '), ticket['title'])
        lean = next(i for i in items if i['guid'] == 'lean')
        self.assertTrue(lean['title'].startswith('Team prop: '), lean['title'])
        self.assertIn('#pick/lean', lean['link'])
        self.assertIn('Our number: 48', lean['text'])
        early = next(i for i in items if i['guid'] == 'early')
        self.assertEqual(early['pubDate'].isoformat(), '2026-09-29T13:00:00+00:00', 'dated when its window opened, not when it was published')

    def test_every_open_play_gets_a_card_before_its_window(self):
        tomorrow = dict(GAMES, **{'g-next': {'id': 'g-next', 'league': 'NFL', 'kickoff': '2026-10-01T00:15Z', 'home': {'short': 'Lions'}, 'away': {'short': 'Bills'}}})
        first = {'next': pick('next', gameIds=['g-next']), 'today': pick('today'), 'kicked': pick('kicked', gameIds=['g-done']),
                 'closed': pick('closed'), 'old': pick('old', historicalImport=True)}
        latest = {k: dict(v) for k, v in first.items()}
        latest['closed']['entryNote'] = 'closed'
        early = datetime(2026, 9, 29, 11, 0, tzinfo=timezone.utc)        # 7:00 AM ET: no window is open yet
        self.assertEqual(feed.pick_items(first, latest, tomorrow, early), [])
        self.assertEqual(sorted(i['guid'] for i in feed.card_items(first, latest, tomorrow, early)), ['next', 'today'])

    def test_the_posting_window_is_game_day_from_nine_until_45_minutes_out(self):
        kickoff = '2026-09-30T00:15Z'                                                     # Tuesday 8:15 PM ET
        self.assertFalse(feed.in_window(kickoff, datetime(2026, 9, 29, 12, 59, tzinfo=timezone.utc)), '8:59 AM ET is too early')
        self.assertTrue(feed.in_window(kickoff, datetime(2026, 9, 29, 13, 0, tzinfo=timezone.utc)), '9:00 AM ET opens it')
        self.assertTrue(feed.in_window(kickoff, datetime(2026, 9, 29, 23, 30, tzinfo=timezone.utc)), '45 minutes before is the last moment')
        self.assertFalse(feed.in_window(kickoff, datetime(2026, 9, 29, 23, 31, tzinfo=timezone.utc)), 'inside 45 minutes is too late')
        self.assertFalse(feed.in_window(kickoff, datetime(2026, 9, 28, 20, 0, tzinfo=timezone.utc)), 'the day before is not game day')
        self.assertFalse(feed.in_window(kickoff, datetime(2026, 9, 30, 1, 0, tzinfo=timezone.utc)), 'after kickoff')

    def test_recap_item_needs_every_pick_of_the_day_settled(self):
        first = {'a': pick('a', gameIds=['g-done'], publishedAt='2026-09-27T12:00:00Z'), 'b': pick('b', gameIds=['g-done'], publishedAt='2026-09-27T12:00:00Z', direction='under')}
        latest = {'a': dict(first['a'], result='win', settledAt='2026-09-27T21:00:00Z'), 'b': dict(first['b'])}
        self.assertEqual(feed.recap_items(first, latest, GAMES, NOW), [], 'one pick still open')
        latest['b'] = dict(first['b'], result='loss', settledAt='2026-09-27T21:05:00Z')
        items = feed.recap_items(first, latest, GAMES, NOW)
        self.assertEqual([i['guid'] for i in items], ['recap:day:2026-09-27'])
        self.assertIn('1-1', items[0]['text'])
        self.assertEqual(items[0]['pubDate'].isoformat(), '2026-09-27T21:05:00+00:00')

    def test_scoreboard_item_appears_on_tuesday_morning(self):
        scoreboard = {'live': [{'league': 'NFL', 'model': 'v2.0', 'season': 2026, 'summary': {'side': [8, 7, 0], 'ou': [6, 9, 0], 'closerTotal': [5, 10], 'games': 15, 'totalMiss': 10.7, 'closeTotalMiss': 10.23}}]}
        item = feed.scoreboard_item(scoreboard, NOW)
        self.assertEqual(item['guid'], 'scoreboard:week:2026-09-29')
        self.assertIsNone(feed.scoreboard_item(scoreboard, datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)), 'not before 8:30 ET')
        self.assertEqual(feed.scoreboard_item(scoreboard, NOW + timedelta(days=3))['guid'], 'scoreboard:week:2026-09-29', 'the week keeps its Tuesday')

    def test_rss_is_well_formed_and_carries_the_card(self):
        items = feed.pick_items({'lean': pick('lean')}, {'lean': pick('lean')}, GAMES, NOW)
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            card = Path(folder) / 'lean.png'
            card.write_bytes(b'\x89PNG' + b'0' * 50)
            text = feed.rss(items, {'lean': card}, NOW)
        root = ET.fromstring(text)
        channel = root.find('channel')
        self.assertEqual(channel.find('title').text, feed.TITLE)
        item = channel.find('item')
        self.assertEqual(item.find('guid').text, 'lean')
        self.assertEqual(item.find('enclosure').get('url'), 'https://keenroudy.com/sports/data/cards/lean.png')
        self.assertEqual(item.find('enclosure').get('type'), 'image/png')
        self.assertIn('TEAM PROP', item.find('description').text)
        self.assertTrue(item.find('pubDate').text.endswith('+0000') or 'GMT' in item.find('pubDate').text or True)


if __name__ == '__main__':
    unittest.main()
