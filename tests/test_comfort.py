import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import comfort


def row(key, game, odds=-250, fair=.70, raw=.74, book='DraftKings'):
    return {'id': key, 'gameIds': [game], 'marketType': 'moneyline', 'direction': 'home',
            'title': f'{key} MONEYLINE', 'odds': odds, 'book': book, 'quotedAt': '2026-10-09T10:00:00Z',
            '_selection': {'fairChance': fair, 'rawChance': raw, 'gap': 100 * (raw - fair)},
            '_planReasons': [{'type': 'line_move', 'direction': 'for', 'text': 'Moved 20 cents.'}]}


class ComfortTests(unittest.TestCase):
    def test_two_different_games_and_required_primetime_leg(self):
        ticket = comfort.build([row('a', 'NFL-a'), row('b', 'NFL-b'), row('c', 'NFL-c', book='FanDuel')], 'NFL-a')
        self.assertEqual(ticket['gameIds'], ['NFL-a', 'NFL-b'])
        self.assertTrue(-200 <= ticket['odds'] <= 120)

    def test_refuses_thin_fair_chance_or_missing_reason(self):
        weak = row('a', 'NFL-a', fair=.69)
        blank = dict(row('b', 'NFL-b'), _planReasons=[])
        self.assertIsNone(comfort.build([weak, blank]))


if __name__ == '__main__':
    unittest.main()
