import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import market_read as mr

GAME = {'id': 'NFL-1', 'league': 'NFL', 'kickoff': '2026-09-27T17:00Z', 'marketRetrievedAt': '2026-09-26T12:00Z',
        'home': {'id': '10', 'abbreviation': 'DET'}, 'away': {'id': '20', 'abbreviation': 'BUF'},
        'market': {'provider': 'Draft Kings', 'spread': '-5.5', 'spreadOdds': '-110', 'spreadOpen': '-7.5',
                   'total': 47.5, 'totalOpen': 'o44.5', 'overOdds': '-110', 'underOdds': '-110'}}
RECORD = {'retrievedAt': '2026-09-26T13:00Z',
          'books': {'draftkings': {'spread': {'home': -5.5}, 'total': {'line': 47.5}},
                    'fanduel': {'spread': {'home': -6}, 'total': {'line': 47.5}},
                    'betmgm': {'spread': {'home': -5}, 'total': {'line': 48.5}}}}
SNAPSHOT = {'margin': 2.4, 'total': 50.6}
ROWS = [{'league': 'NFL', 'margin': m, 'closeMargin': 0.0, 'side': s, 'total': t, 'closeTotal': 40.0, 'ou': o}
        for m, s, t, o in ((1, 'W', 41, 'W'), (2, 'L', 42, 'L'), (3, 'W', 43, 'W'), (4, 'L', 44, 'L'), (8, 'W', 48, 'L'))] \
    + [{'league': 'CFB', 'margin': 30, 'closeMargin': 0.0, 'side': 'W', 'total': 70, 'closeTotal': 40.0, 'ou': 'W'}]


class MarketReadTests(unittest.TestCase):
    def test_open_to_now_reads_the_move_and_its_direction(self):
        moves = mr.open_to_now(GAME)
        self.assertEqual(moves['book'], 'DraftKings')
        self.assertEqual(moves['spread'], {'open': -7.5, 'now': -5.5, 'move': 2.0, 'toward': 'away'})
        self.assertEqual(moves['total'], {'open': 44.5, 'now': 47.5, 'move': 3.0, 'toward': 'over'})
        self.assertIsNone(mr.open_to_now({'market': None}))

    def test_disagreement_lists_books_range_and_middle(self):
        books = mr.disagreement(RECORD)
        self.assertEqual(books['spread']['books'], {'BetMGM': -5, 'DraftKings': -5.5, 'FanDuel': -6})
        self.assertEqual(books['spread']['range'], 1.0)
        self.assertEqual(books['spread']['consensus'], -5.5)
        self.assertEqual(books['total']['range'], 1.0)
        self.assertEqual(books['total']['consensus'], 47.5)
        self.assertIsNone(mr.disagreement(None))

    def test_gap_percentile_uses_the_league_and_the_side_the_model_took(self):
        g = mr.gap_percentile(ROWS, 'NFL', 'margin', 3.5)
        self.assertEqual(g['n'], 5)
        self.assertEqual(g['percentile'], 60, 'three of five gaps were smaller')
        self.assertEqual(g['gapsThisLargeVsClose'], [1, 1], 'the 4 and the 8: one won, one lost')
        self.assertEqual(mr.gap_percentile(ROWS, 'NFL', 'total', -8.0)['gapsThisLargeVsClose'], [0, 1])
        self.assertIsNone(mr.gap_percentile(ROWS, 'MLB', 'margin', 1.0))
        self.assertIsNone(mr.gap_percentile(ROWS, 'NFL', 'margin', None))

    def test_read_assembles_the_block_and_the_words_carry_only_its_numbers(self):
        block = mr.read(GAME, SNAPSHOT, RECORD, ROWS, events=[{'kind': 'injury', 'text': 'x', 'source': 'https://e', 'retrievedAt': '2026-09-26T12:00Z'}])
        self.assertEqual(block['ourGap']['margin']['line'], 5.5)
        self.assertEqual(block['ourGap']['margin']['gap'], -3.1, 'our margin 2.4 against a close of 5.5')
        self.assertEqual(block['ourGap']['total']['gap'], 3.1)
        self.assertEqual(len(block['events']), 1)
        text = mr.sentences(block)
        self.assertIn('opened -7.5 and is -5.5', text)
        self.assertIn('3 books span', text)
        self.assertIn('percentile', text)
        import llm
        self.assertEqual(llm.check_style(text), [])
        self.assertTrue(llm.numbers_ok(text, block)[0], llm.numbers_ok(text, block)[1])

    def test_read_without_a_snapshot_or_capture_still_reads_the_move(self):
        block = mr.read(GAME, None, None, ROWS)
        self.assertIsNone(block['ourGap'])
        self.assertIsNone(block['books'])
        self.assertEqual(block['moves']['total']['move'], 3.0)


if __name__ == '__main__':
    unittest.main()
