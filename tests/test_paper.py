import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import paper

NOW = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)        # opening week, 11 AM ET


def event(eid, date, state='pre', season_type=2, home='BOS', away='NYK'):
    return {'id': eid, 'date': date, 'season': {'year': 2027, 'type': season_type},
            'competitions': [{'status': {'type': {'state': state}}, 'neutralSite': False,
                              'competitors': [{'homeAway': 'home', 'team': {'id': '2', 'abbreviation': home}},
                                              {'homeAway': 'away', 'team': {'id': '18', 'abbreviation': away}}]}]}


def odds_payload(total_now=221.5, total_open=219.5):
    def book(pid, name, now):
        return {'provider': {'id': pid, 'name': name},
                'open': {'total': {'american': str(total_open)}},
                'current': {'total': {'american': str(now)}, 'over': {'american': '-112'}, 'under': {'american': '-108'}}}
    return {'items': [book('1001', 'ESPN BET - Live Odds', 230.5), book('58', 'ESPN BET', total_now + 1), book('40', 'DraftKings', total_now)]}


class FakeFetch:
    def __init__(self, events, payload=None):
        self.events, self.payload, self.urls = events, payload or odds_payload(), []

    def __call__(self, url):
        self.urls.append(url)
        if 'scoreboard' in url:
            return {'events': self.events if url.endswith('20261021&limit=1000') else []}
        return self.payload


class FakeModel:
    def __init__(self, total):
        self.total = total

    def predict(self, home, away, neutral=False):
        return {'total': self.total, 'sdTotal': 18.0, 'sparse': False}


class PaperTests(unittest.TestCase):
    def test_only_regular_season_games_about_to_tip_are_upcoming(self):
        fetch = FakeFetch([event('1', '2026-10-21T23:30Z'), event('2', '2026-10-21T23:30Z', state='post'),
                           event('3', '2026-10-24T23:30Z'), event('4', '2026-10-21T23:30Z', season_type=1)])
        self.assertEqual([g['id'] for g in paper.upcoming('NBA', NOW, fetch)], ['NBA-1'])

    def test_the_line_is_draftkings_now_with_its_opener_and_prices(self):
        quote = paper.current_line('NBA', '1', FakeFetch([], odds_payload()))
        self.assertEqual(quote, {'book': 'DraftKings', 'open': 219.5, 'now': 221.5, 'over': -112, 'under': -108})

    def test_a_game_is_recorded_once_and_is_a_paper_play_past_the_lean(self):
        with tempfile.TemporaryDirectory() as folder:
            fetch = FakeFetch([event('1', '2026-10-21T23:30Z'), event('5', '2026-10-21T23:30Z', home='LAL', away='GSW')])
            models = {('NBA', 2027): FakeModel(225.0)}
            self.assertEqual(paper.record(NOW, fetch, folder, models, log=lambda *_: None), 2)
            self.assertEqual(paper.record(NOW, fetch, folder, models, log=lambda *_: None), 0, 'first capture only')
            rows = paper.read('NBA', 2027, folder)
            self.assertEqual((rows[0]['line'], rows[0]['open'], rows[0]['side'], rows[0]['price'], rows[0]['lean']), (221.5, 219.5, 'over', -112, True))
            self.assertEqual(rows[0]['gap'], 3.5)
            close = {'NBA': {'NBA-1': {'homeScore': 120, 'awayScore': 110, 'close': {'total': 223.5}},
                             'NBA-5': {'homeScore': 100, 'awayScore': 101, 'close': {'total': 220.0}}}}
            self.assertEqual(paper.grade(NOW, folder, close), 2)
            self.assertEqual(paper.grade(NOW, folder, close), 0, 'graded once')
            joined = {r['gameId']: r for r in paper.joined(folder)}
            self.assertEqual((joined['NBA-1']['result'], joined['NBA-1']['resultAtOpen'], joined['NBA-1']['clv']), ('win', 'win', 2.0))
            self.assertEqual(joined['NBA-5']['result'], 'loss')
            text = paper.report(folder)
            self.assertIn('**NBA totals**: 2 games recorded, 2 paper plays graded. At the number recorded 1-1', text)

    def test_nothing_runs_out_of_season(self):
        self.assertFalse(paper.in_season(datetime(2026, 9, 24, tzinfo=timezone.utc)))
        self.assertTrue(paper.in_season(datetime(2026, 10, 25, tzinfo=timezone.utc)))
        self.assertTrue(paper.in_season(datetime(2027, 1, 15, tzinfo=timezone.utc)))
        self.assertFalse(paper.in_season(datetime(2027, 7, 15, tzinfo=timezone.utc)))
        self.assertEqual(paper.step(datetime(2026, 9, 24, tzinfo=timezone.utc), fetch=lambda url: self.fail('no requests out of season'))['skipped'],
                         'out of season')


if __name__ == '__main__':
    unittest.main()
