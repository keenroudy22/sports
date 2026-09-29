import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sgo_shadow

NOW = datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc)
SLATE = {'games': [{'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-09-30T00:00:00Z'}]}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def usage(used=20, maximum=2500):
    return {'data': {'rateLimits': {'per-month': {'currentIntervalEntities': used,
            'maxEntitiesPerInterval': maximum, 'currentIntervalEndTime': '2026-10-29T00:00:00Z'}}}}


def odd(odd_id, opposing, side, books, entity='all', bet='ou', market='Game total'):
    return {'oddID': odd_id, 'opposingOddID': opposing, 'statID': 'points', 'statEntityID': entity,
            'periodID': 'game', 'betTypeID': bet, 'sideID': side, 'marketName': market, 'byBookmaker': books}


def quote(price, line=41.5, updated='2026-09-29T17:55:00Z'):
    return {'odds': str(price), 'overUnder': str(line), 'available': True, 'lastUpdatedAt': updated}


class BudgetTests(unittest.TestCase):
    def test_unknown_or_nonfree_ceiling_fails_closed(self):
        self.assertIn('numeric', sgo_shadow.due({}, SLATE, NOW, None))
        self.assertIn('not the confirmed free-tier', sgo_shadow.due({}, SLATE, NOW, (0, 100000, None)))
        self.assertIn('reserve', sgo_shadow.due({}, SLATE, NOW, (1795, 2500, None)))

    def test_gap_and_daily_cap_prevent_excess_calls(self):
        state = {'lastAt': '2026-09-29T14:00:00Z'}
        self.assertIn('six-hour', sgo_shadow.due(state, SLATE, NOW, (20, 2500, None)))
        state = {'day': '2026-09-29', 'dayCount': 30}
        self.assertIn('daily cap', sgo_shadow.due(state, SLATE, NOW, (20, 2500, None)))

    def test_no_key_makes_no_request(self):
        called = []
        result = sgo_shadow.sample(SLATE, NOW, key='', opener=lambda *a, **k: called.append(a))
        self.assertFalse(result['sampled'])
        self.assertEqual(called, [])

    def test_usage_is_checked_and_key_is_only_in_header(self):
        calls = []
        payloads = [usage(), {'data': []}]

        def opener(request, timeout):
            calls.append(request)
            return Response(json.dumps(payloads.pop(0)).encode())

        with tempfile.TemporaryDirectory() as folder:
            result = sgo_shadow.sample(SLATE, NOW, key='top-secret', state_path=Path(folder) / 'state.json', opener=opener)
        self.assertTrue(result['sampled'])
        self.assertEqual(len(calls), 2)
        self.assertNotIn('top-secret', calls[0].full_url + calls[1].full_url)
        self.assertEqual(calls[0].get_header('X-api-key'), 'top-secret')
        self.assertIn('limit=10', calls[1].full_url)
        self.assertIn('includeAltLines=true', calls[1].full_url)
        self.assertIn('includeOpposingOdds=true', calls[1].full_url)


class CandidateTests(unittest.TestCase):
    def test_exact_fresh_complements_are_measured(self):
        over_id, under_id = 'points-all-game-ou-over', 'points-all-game-ou-under'
        event = {'eventID': 'event-1', 'status': {'started': False}, 'odds': {
            over_id: odd(over_id, under_id, 'over', {'fanduel': quote(120)}),
            under_id: odd(under_id, over_id, 'under', {'draftkings': quote(115)})}}
        hits = sgo_shadow.event_candidates(event, NOW)
        self.assertEqual(len(hits), 1)
        self.assertGreater(hits[0]['roi'], 8)

    def test_different_lines_stale_quotes_and_same_book_are_not_arbs(self):
        over_id, under_id = 'points-all-game-ou-over', 'points-all-game-ou-under'

        def event(first, second):
            return {'eventID': 'event-1', 'status': {}, 'odds': {
                over_id: odd(over_id, under_id, 'over', first),
                under_id: odd(under_id, over_id, 'under', second)}}

        self.assertEqual(sgo_shadow.event_candidates(event({'fanduel': quote(120, 40.5)},
                                                           {'draftkings': quote(115, 42.5)}), NOW), [])
        self.assertEqual(sgo_shadow.event_candidates(event({'fanduel': quote(120)},
                                                           {'draftkings': quote(115, updated='2026-09-29T17:00:00Z')}), NOW), [])
        self.assertEqual(sgo_shadow.event_candidates(event({'fanduel': quote(120)},
                                                           {'fanduel': quote(115)}), NOW), [])

    def test_whole_number_player_total_is_rejected_even_in_alt_lines(self):
        over_id, under_id = 'receptions-PLAYER_NFL-game-ou-over', 'receptions-PLAYER_NFL-game-ou-under'
        a = quote(-105, 4)
        b = quote(115, 4)
        event = {'eventID': 'event-1', 'status': {}, 'odds': {
            over_id: odd(over_id, under_id, 'over', {'fanduel': a}, entity='PLAYER_NFL', market='Player receptions'),
            under_id: odd(under_id, over_id, 'under', {'draftkings': b}, entity='PLAYER_NFL', market='Player receptions')}}
        self.assertEqual(sgo_shadow.event_candidates(event, NOW), [])

    def test_saved_candidate_summary_has_verification_details_not_the_full_feed(self):
        hit = {'gameId': 'event-1', 'label': 'Game total', 'line': 41.5, 'roi': 2.4,
               'first': {'book': 'FanDuel', 'side': 'over', 'price': 105, 'updatedAt': 'now', 'deeplink': 'secret'},
               'second': {'book': 'DraftKings', 'side': 'under', 'price': 102, 'updatedAt': 'now', 'deeplink': 'secret'}}
        saved = sgo_shadow.candidate_summary(hit)
        self.assertEqual(saved['first']['book'], 'FanDuel')
        self.assertNotIn('deeplink', saved['first'])


if __name__ == '__main__':
    unittest.main()
