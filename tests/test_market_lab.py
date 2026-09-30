import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import market_lab


def event(state='pre', completed=False, kickoff='2026-09-29T22:00:00Z'):
    return {'id': '55', 'date': kickoff, 'season': {'year': 2026, 'type': 2, 'slug': 'regular-season'},
            'competitions': [{'date': kickoff, 'timeValid': True,
                'status': {'type': {'name': 'STATUS_FINAL' if completed else 'STATUS_SCHEDULED',
                                    'state': state, 'completed': completed,
                                    'shortDetail': 'Final' if completed else 'Scheduled'}},
                'competitors': [
                    {'homeAway': 'away', 'team': {'id': '1', 'displayName': 'Away', 'abbreviation': 'AWY'},
                     'score': '3' if completed else '0'},
                    {'homeAway': 'home', 'team': {'id': '2', 'displayName': 'Home', 'abbreviation': 'HME'},
                     'score': '5' if completed else '0'}]}]}


def odds(total=8.5):
    return {'items': [
        {'provider': {'id': '200', 'name': 'DraftKings - Live Odds'}, 'overUnder': 7.5},
        {'provider': {'id': '100', 'name': 'DraftKings'}, 'overUnder': total,
         'overOdds': -105, 'underOdds': -115,
         'open': {'total': {'american': '8.0'}, 'over': {'american': '-110'}, 'under': {'american': '-110'}},
         'homeTeamOdds': {'moneyLine': -145, 'spreadOdds': 130,
             'current': {'pointSpread': {'american': '-1.5'}, 'moneyLine': {'american': '-145'}, 'spread': {'american': '+130'}},
             'open': {'pointSpread': {'american': '-1.5'}, 'moneyLine': {'american': '-135'}, 'spread': {'american': '+135'}}},
         'awayTeamOdds': {'moneyLine': 125, 'spreadOdds': -150,
             'current': {'pointSpread': {'american': '+1.5'}, 'moneyLine': {'american': '+125'}, 'spread': {'american': '-150'}},
             'open': {'pointSpread': {'american': '+1.5'}, 'moneyLine': {'american': '+120'}, 'spread': {'american': '-155'}}}}
    ]}


class Feed:
    def __init__(self):
        self.finished = False
        self.total = 8.5
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if '/odds' in url:
            return odds(self.total)
        if '/sports/baseball/mlb/' in url:
            return {'leagues': [{'abbreviation': 'MLB'}],
                    'events': [event('post', True)] if self.finished else [event()]}
        return {'leagues': [{'abbreviation': 'NHL'}], 'events': []}


class MarketLabTests(unittest.TestCase):
    def test_pregame_snapshot_uses_the_real_book_and_ignores_live_odds(self):
        captured = market_lab.quote('MLB', '55', lambda _: odds())
        self.assertEqual(captured['book'], 'DraftKings')
        self.assertEqual(captured['current']['total'], {'line': 8.5, 'over': -105, 'under': -115})
        self.assertEqual(captured['current']['home'], {'moneyline': -145, 'spreadLine': -1.5, 'spreadPrice': 130})
        self.assertEqual(captured['open']['away']['moneyline'], 120)

    def test_changed_quotes_and_final_scores_are_append_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'store'
            public = Path(folder) / 'public.json'
            feed = Feed()
            before = datetime(2026, 9, 29, 20, 0, tzinfo=timezone.utc)
            first = market_lab.step(before, feed, root, public, log=lambda *_: None)
            self.assertEqual((first['captured'], first['graded']), (1, 0))
            self.assertEqual(market_lab.step(before, feed, root, public, log=lambda *_: None)['captured'], 0,
                             'an unchanged observation is not appended')
            feed.total = 9.0
            self.assertEqual(market_lab.step(before, feed, root, public, log=lambda *_: None)['captured'], 1)
            feed.finished = True
            after = datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)
            self.assertEqual(market_lab.step(after, feed, root, public, log=lambda *_: None)['graded'], 1)
            self.assertEqual(market_lab.step(after, feed, root, public, log=lambda *_: None)['graded'], 0)
            rows = market_lab.read_all(root)
            self.assertEqual([row['type'] for row in rows], ['quote', 'quote', 'grade'])
            self.assertEqual((rows[-1]['awayScore'], rows[-1]['homeScore']), (3, 5))
            summary = json.loads(public.read_text())['leagues']['MLB']
            self.assertEqual((summary['gamesQuoted'], summary['snapshots'], summary['gamesGraded']), (1, 2, 1))
            self.assertEqual(market_lab.append([], root), 0)

    def test_bad_or_missing_prices_create_no_quote(self):
        self.assertIsNone(market_lab.quote('NHL', '55', lambda _: {'items': []}))
        self.assertIsNone(market_lab.quote('NHL', '55', lambda _: (_ for _ in ()).throw(OSError('down'))))
        missing = {'provider': {'id': '100', 'name': 'DraftKings'}, 'overUnder': 6.5,
                   'initialOverUnder': 0, 'initialSpread': 0}
        self.assertEqual(market_lab.snapshot(missing, 'open'), {}, 'feed zero sentinels are not real lines')


if __name__ == '__main__':
    unittest.main()
