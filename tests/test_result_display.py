import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import result_display
import receipts
import run
import ticket_card
import voice


class ResultDisplayTests(unittest.TestCase):
    def setUp(self):
        # Real Oct 8 TK King settlement shape: ESPN omitted a zero-catch box row,
        # but retained six play-by-play targets for athlete 4869443.
        self.pick = {'id': 'CFB-2026-W6-king-over-49-5-recyds-dk', 'title': 'TK King OVER 49.5 receiving yards',
                     'athleteId': '4869443', 'gameId': 'CFB-401871066', 'marketType': 'prop', 'market': 'recYds',
                     'line': 49.5, 'direction': 'over', 'result': 'loss', 'actualValue': 0,
                     'actual': '4869443: 0 receiving yards'}
        self.game = {'players': [{'id': '4869443', 'pbpTgt': 6}]}

    def test_future_grade_uses_title_name_not_athlete_id(self):
        with patch.object(run.pricing, 'market_of', return_value='recYds'):
            result, actual, value = run.grade_prop(self.pick, self.game)
        self.assertEqual((result, actual, value), ('loss', 'TK King: 0 receiving yards', 0))

    def test_saved_report_is_cleaned_only_for_display(self):
        self.assertEqual(result_display.clean_actual(self.pick), 'TK King: 0 receiving yards')
        self.assertEqual(self.pick['actual'], '4869443: 0 receiving yards')
        self.assertEqual(result_display.detail(self.pick, self.game), '0 catches on 6 targets, 0 yards · missed by 49.5')
        with patch.object(result_display, 'stored_games', return_value={'CFB-401871066': self.game}):
            self.assertEqual(receipts.result_detail(self.pick), '0 catches on 6 targets, 0 yards · missed by 49.5')
            self.assertEqual(ticket_card.final_detail(self.pick), '0 catches on 6 targets, 0 yards · missed by 49.5')
            self.assertFalse(voice.bare_athlete_id(receipts.result_line(self.pick)))

    def test_other_player_stat_lines(self):
        cases = [('rec', {'pbpTgt': 6, 'rec': 0}, '0 catches on 6 targets'),
                 ('rushYds', {'car': 15, 'rushYds': 89}, '89 yards on 15 carries'),
                 ('passYds', {'cmp': 9, 'att': 22, 'passYds': 104}, '9 of 22, 104 yards')]
        for market, player, expected in cases:
            pick = dict(self.pick, market=market)
            with self.subTest(market=market):
                self.assertEqual(result_display.stat_line(pick, {'players': [dict(player, id='4869443')]}), expected)


if __name__ == '__main__':
    unittest.main()
