import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import arbs

NOW = datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc)


def book(title, updated='2026-09-29T17:58:00Z', **markets):
    return {'title': title, 'updatedAt': updated, **markets}


class MathTests(unittest.TestCase):
    def test_equal_return_stakes_produce_a_real_locked_profit(self):
        split = arbs.allocation(298, -195, 181.55)
        self.assertAlmostEqual(split['firstStake'], 50, delta=.02)
        self.assertAlmostEqual(split['secondStake'], 131.55, delta=.02)
        self.assertAlmostEqual(split['profit'], 17.45, delta=.03)
        self.assertAlmostEqual(split['roi'], 9.61, delta=.02)

    def test_the_example_free_roll_is_not_called_guaranteed_profit(self):
        result = arbs.boost(298, 50, -195)
        self.assertEqual(result['freeRollHedge'], 97.5)
        self.assertEqual(result['freeRollDownside'], 0)
        self.assertEqual(result['freeRollUpside'], 51.5)
        self.assertEqual(result['equalHedge'], 131.55)
        self.assertEqual(result['lockedProfit'], 17.45)


class ScanTests(unittest.TestCase):
    def test_an_exact_total_arb_is_found_and_a_middle_is_not_mislabeled(self):
        record = {'gameId': 'NFL-1', 'kickoff': '2026-09-30T00:00:00Z', 'retrievedAt': '2026-09-29T17:59:00Z',
                  'books': {
                      'fanduel': book('FanDuel', total={'line': 41.5, 'over': 120, 'under': -140}),
                      'hardrockbet': book('Hard Rock Bet', total={'line': 41.5, 'over': -130, 'under': 115})}}
        hits = arbs.game_arbs(record, NOW, 'Bears at Lions')
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]['first']['book'], hits[0]['second']['book']), ('FanDuel', 'Hard Rock Bet'))
        self.assertGreater(hits[0]['profit'], 8)
        middle = {'gameId': 'NFL-1', 'kickoff': record['kickoff'], 'retrievedAt': record['retrievedAt'], 'books': {
            'fanduel': book('FanDuel', total={'line': 40.5, 'over': 120, 'under': -140}),
            'hardrockbet': book('Hard Rock Bet', total={'line': 42.5, 'over': -130, 'under': 115})}}
        self.assertEqual(arbs.game_arbs(middle, NOW), [], 'different lines can middle, but do not guarantee both outcomes')

    def test_a_player_prop_needs_the_same_half_point_market_and_fresh_quotes(self):
        base = {'gameId': 'NFL-1', 'kickoff': '2026-09-30T00:00:00Z', 'retrievedAt': '2026-09-29T17:59:00Z'}
        record = dict(base, books={
            'fanduel': book('FanDuel', markets={'rec': {'Kalif Raymond': {'line': 3.5, 'over': 125, 'under': -150}}}),
            'hardrockbet': book('Hard Rock Bet', markets={'rec': {'Kalif Raymond': {'line': 3.5, 'over': -145, 'under': 120}}})})
        hits = arbs.prop_arbs(record, NOW)
        self.assertEqual(len(hits), 1)
        stale = dict(record, books={**record['books'], 'hardrockbet': book('Hard Rock Bet', '2026-09-29T17:20:00Z',
            markets={'rec': {'Kalif Raymond': {'line': 3.5, 'over': -145, 'under': 120}}})})
        self.assertEqual(arbs.prop_arbs(stale, NOW), [])
        whole = dict(record, books={
            'fanduel': book('FanDuel', markets={'rec': {'Kalif Raymond': {'line': 4, 'over': 125, 'under': -150}}}),
            'hardrockbet': book('Hard Rock Bet', markets={'rec': {'Kalif Raymond': {'line': 4, 'over': -145, 'under': 120}}})})
        self.assertEqual(arbs.prop_arbs(whole, NOW), [], 'a whole-number over/under can push and is not exhaustive')

    def test_started_or_stale_records_are_silent(self):
        record = {'gameId': 'NFL-1', 'kickoff': '2026-09-29T17:00:00Z', 'retrievedAt': '2026-09-29T17:59:00Z', 'books': {}}
        self.assertEqual(arbs.game_arbs(record, NOW), [])
        record.update(kickoff='2026-09-30T00:00:00Z', retrievedAt='2026-09-29T17:00:00Z')
        self.assertEqual(arbs.game_arbs(record, NOW), [])


if __name__ == '__main__':
    unittest.main()
