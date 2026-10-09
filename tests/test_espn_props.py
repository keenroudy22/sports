import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import boxscores
import espn_props as ep

FIXTURES = Path(__file__).parent / 'fixtures' / 'espn'
NOW = datetime(2026, 10, 20, 19, tzinfo=timezone.utc)


def item(name, odds, target, display=None, athlete='1'):
    base = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/'
    return {'athlete': {'$ref': base + f'seasons/2027/athletes/{athlete}?lang=en'},
            'competition': {'$ref': base + 'events/1/competitions/1?lang=en'},
            'provider': {'$ref': base + 'casinos/100?lang=en'},
            'type': {'name': name}, 'odds': {'american': {'value': odds}},
            'current': {'target': {'value': target, 'displayValue': display or str(target)}},
            'lastUpdated': '2099-01-01T00:00Z'}


def board():
    return {'pageCount': 1, 'pageIndex': 1, 'items': [item('Total Points', -110, 10.5),
            item('Total Points', -120, 10.5), item('Points Milestones', -120, 11, '11+')]}


def game(event='1'):
    return {'league': 'NBA', 'providerId': event, 'season': 2027, 'seasonType': 'regular-season',
            'kickoff': (NOW + timedelta(hours=2)).isoformat(), 'status': 'scheduled'}


class ParsingTests(unittest.TestCase):
    def test_real_board_proves_over_second_and_all_prices_match_milestones(self):
        payload = json.loads((FIXTURES / 'nba-401859967-props.json').read_text())
        rows, status = ep.parse(payload)
        self.assertEqual(status['verifiedPairs'], 49)
        self.assertEqual(status['orderContradictions'], 3)
        self.assertEqual(status['unverifiedPairs'], 127)
        for row in rows:
            if row['sideVerified']:
                self.assertTrue(.99 <= ep.implied(row['over']) + ep.implied(row['under']) <= 1.15)
            else:
                self.assertNotIn('over', row)
                self.assertNotIn('under', row)

    def test_over_second_is_identified_without_order_assumption(self):
        rows, stats = ep.parse(board())
        self.assertEqual((rows[0]['over'], rows[0]['under']), (-120, -110))
        self.assertEqual(stats['orderContradictions'], 1)

    def test_missing_ambiguous_equal_and_bad_pair_prices_never_escape(self):
        cases = []
        missing = board(); missing['items'].pop(); cases.append(missing)
        equal = board(); equal['items'][0]['odds']['american']['value'] = -120; cases.append(equal)
        ambiguous = board(); ambiguous['items'].append(item('Points Milestones', -110, 11, '11+')); cases.append(ambiguous)
        insane = board(); insane['items'][0]['odds']['american']['value'] = -900; cases.append(insane)
        for payload in cases:
            with self.subTest(payload=payload):
                rows, _ = ep.parse(payload)
                self.assertFalse(rows[0]['sideVerified'])
                self.assertNotIn('over', rows[0])
                self.assertNotIn('under', rows[0])

    def test_integer_line_extra_side_unknown_market_and_wrong_identity(self):
        cases = []
        extra = board(); extra['items'].append(extra['items'][0]); cases.append(extra)
        integer = board()
        for row in integer['items'][:2]: row['current']['target']['value'] = 10
        cases.append(integer)
        wrong = board()
        for row in wrong['items']: row['provider']['$ref'] = row['provider']['$ref'].replace('/100?', '/58?')
        cases.append(wrong)
        unknown = board()
        for row in unknown['items']: row['type']['name'] = 'First scorer'
        cases.append(unknown)
        for payload in cases:
            self.assertEqual(ep.parse(payload)[0], [])

    def test_fractional_nan_boolean_and_small_odds_are_refused(self):
        for value in (True, 'NaN', -99, -110.5):
            payload = board()
            payload['items'][0]['odds']['american']['value'] = value
            self.assertEqual(ep.parse(payload)[0], [])


class CaptureTests(unittest.TestCase):
    def capture(self, games=None, fetch=None, clock=None, **kwargs):
        return ep.capture(games or [game()], fetch=fetch or (lambda url: board()),
                          clock=clock or (lambda: NOW), sleep=lambda gap: None, root=self.root, **kwargs)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_retrieval_clock_not_provider_clock_and_repeat_dedup(self):
        self.assertEqual(self.capture()['captured'], 1)
        self.assertEqual(self.capture()['captured'], 0)
        row = boxscores.read_store(self.root / 'nba-2027.jsonl')[0]
        self.assertEqual(row['retrievedAt'], boxscores.stamp(NOW))
        self.assertEqual(row['season'], 2027)
        self.assertEqual(boxscores.verify(self.root), [])

    def test_board_finishing_at_kickoff_is_dropped(self):
        ticks = iter([NOW, NOW + timedelta(hours=2)])
        result = self.capture(clock=lambda: next(ticks))
        self.assertEqual((result['late'], result['captured']), (1, 0))

    def test_failed_second_page_drops_entire_board(self):
        first = board(); first['pageCount'] = 2
        def fetch(url):
            if 'page=2' in url: raise OSError('unavailable')
            return first
        self.assertEqual(self.capture(fetch=fetch)['captured'], 0)
        self.assertFalse(list(self.root.glob('*.jsonl')))

    def test_complete_pages_can_join_split_pair(self):
        def fetch(url):
            full = board()
            if 'page=1' in url: return {'pageIndex': 1, 'pageCount': 2, 'items': full['items'][:1]}
            return {'pageIndex': 2, 'pageCount': 2, 'items': full['items'][1:]}
        result = self.capture(fetch=fetch)
        self.assertEqual((result['requests'], result['captured']), (2, 1))

    def test_missing_page_wrong_competition_and_excess_pages_hold(self):
        for edit in ('pageIndex', 'pageCount', 'competition'):
            payload = board()
            if edit == 'pageIndex': payload[edit] = 2
            elif edit == 'pageCount': payload[edit] = 4
            else: payload['items'][0]['competition']['$ref'] = 'wrong'
            self.assertEqual(self.capture(fetch=lambda url: payload)['captured'], 0)

    def test_incomplete_advertised_count_refuses_board(self):
        payload = board(); payload['count'] = 4
        self.assertEqual(self.capture(fetch=lambda url: payload)['captured'], 0)

    def test_three_errors_stop_and_existing_data_survives(self):
        self.capture()
        original = (self.root / 'nba-2027.jsonl').read_bytes()
        def fetch(url): raise OSError('unavailable')
        result = self.capture(games=[game(str(i)) for i in range(5)], fetch=fetch)
        self.assertEqual(result['requests'], 3)
        self.assertEqual((self.root / 'nba-2027.jsonl').read_bytes(), original)

    def test_cap_and_timebox(self):
        self.assertEqual(self.capture(games=[game(str(i)) for i in range(5)], limit=2)['boards'], 2)
        self.assertEqual(self.capture(seconds=0)['requests'], 0)

    def test_football_live_late_next_date_naive_and_far_games_are_skipped(self):
        cases = []
        for field, value in [('league', 'NFL'), ('status', 'in_progress'),
                             ('kickoff', NOW.isoformat()),
                             ('kickoff', (NOW + timedelta(days=1)).isoformat()),
                             ('kickoff', '2026-10-20T21:00:00'),
                             ('kickoff', (NOW + timedelta(hours=11)).isoformat())]:
            row = game(); row[field] = value; cases.append(row)
        self.assertEqual(self.capture(games=cases)['requests'], 0)

    def test_store_tampering_refuses_append(self):
        self.capture()
        path = self.root / 'nba-2027.jsonl'
        path.write_text(path.read_text().replace('10.5', '11.5'))
        original = path.read_bytes()
        self.assertEqual(self.capture()['errors'], 1)
        self.assertEqual(path.read_bytes(), original)

    def test_changed_quote_appends_without_rewriting(self):
        self.capture()
        path = self.root / 'nba-2027.jsonl'; original = path.read_bytes()
        payload = board(); payload['items'][0]['odds']['american']['value'] = -105
        self.assertEqual(self.capture(fetch=lambda url: payload)['captured'], 1)
        self.assertTrue(path.read_bytes().startswith(original))
        self.assertEqual(boxscores.verify(self.root), [])


if __name__ == '__main__': unittest.main()
