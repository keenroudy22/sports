import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_svg
import pick_card
import ticket_card


ROW = ('win', 'TK King over 49.5 receiving yards', '64 receiving yards', 'player')


class CardCopyTests(unittest.TestCase):
    def test_visible_nodes_only_and_retired_words_are_rejected(self):
        svg = '<svg><image href="data:image/png;base64,PLATES"/><text>21+ · Entertainment only</text><text>keenroudy.com/sports</text></svg>'
        self.assertEqual(check_svg.issues(svg), [])
        self.assertTrue(check_svg.issues(svg.replace('<text>keenroudy.com/sports</text>', '<text>NO HIDING</text>')))

    def test_legacy_and_felt_receipts_keep_clean_public_copy(self):
        for result in ('win', 'loss', 'push'):
            receipt = {'title': '1-0' if result == 'win' else '0-1', 'when': 'Thursday, Oct 8',
                       'rows': [(result, ROW[1], ROW[2], ROW[3])]}
            for felt in (False, True):
                with self.subTest(result=result, felt=felt), patch.object(pick_card, 'felt_enabled', return_value=felt):
                    self.assertEqual(check_svg.issues(pick_card.receipt_svg(receipt)), [])
        six = {'title': '3-3', 'when': 'Saturday, Oct 10', 'rows':
               [('win' if i % 2 else 'loss', f'Player {i} over 49.5 yards', '64 yards', 'player') for i in range(6)]}
        for felt in (False, True):
            with self.subTest(six=felt), patch.object(pick_card, 'felt_enabled', return_value=felt):
                self.assertEqual(check_svg.issues(pick_card.receipt_svg(six)), [])

    def test_kitchen_play_and_final_have_approved_footer_and_words(self):
        game = {'league': 'CFB', 'kickoff': '2026-10-09T23:00:00Z',
                'away': {'id': '1', 'abbreviation': 'IOWA'}, 'home': {'id': '2', 'abbreviation': 'WASH'}}
        pick = {'id': 'sample', 'title': 'Iowa at Washington over 41.5', 'marketType': 'total',
                'direction': 'over', 'line': 41.5, 'odds': -110, 'book': 'DraftKings', 'riskUnits': 1}
        with patch.object(pick_card, 'fetch_data_uri', return_value=None):
            svg = ticket_card.straight_svg(pick, game)
        self.assertEqual(check_svg.issues(svg), [])
        final = ticket_card.final_svg([dict(pick, result='win', actual='Iowa 24, Washington 22', units=0.91)], '2026-10-09')
        self.assertEqual(check_svg.issues(final), [])

    def test_every_kitchen_card_family_has_clean_visible_copy(self):
        game = {'league': 'CFB', 'kickoff': '2026-10-09T23:00:00Z',
                'away': {'id': '1', 'abbreviation': 'IOWA'}, 'home': {'id': '2', 'abbreviation': 'WASH'}}
        legs = [{'title': 'Iowa over 17.5 points', 'odds': -160, 'gameId': 'g', 'kickoff': game['kickoff']},
                {'title': 'Washington over 14.5 points', 'odds': -170, 'gameId': 'g', 'kickoff': game['kickoff']}]
        art = [{'kind': 'logos', 'uris': ['data:image/png;base64,TEST', 'data:image/png;base64,TEST']} for _ in legs]
        fun = {'id': 'fun', 'parlayType': 'longshot', 'odds': 185, 'book': 'FanDuel', 'riskUnits': .25, 'legs': legs}
        rung = dict(fun, id='rung', parlayType='ladder', ladder={'run': 1, 'step': 1, 'stake': 50,
            'payout': 93, 'banked': 0, 'bankThisWin': 19, 'nextStake': 74})
        cooked = {'id': 'cooked', 'title': 'Player over 49.5 receiving yards', 'athleteId': '7',
                  'market': 'recYds', 'direction': 'over', 'line': 49.5, 'odds': -110, 'book': 'FanDuel',
                  'result': 'win', 'actualValue': 67, 'units': .91}
        prep = {'day': '2026-10-09', 'rows': [{'league': 'CFB', 'athleteId': '7', 'player': 'Player',
            'teamColor': '#112233', 'stat': 'recYds', 'direction': 'over', 'line': 49.5,
            'odds': -110, 'book': 'FanDuel', 'hits': 4, 'games': 5, 'clears': True}]}
        photo = 'data:image/png;base64,' + base64.b64encode((Path(__file__).resolve().parents[1] / 'site/kookn-mark.png').read_bytes()).decode('ascii')
        cards = [ticket_card.fun_svg(fun, {'g': game}, art=art),
                 ticket_card.climb_svg(rung, {'g': game}, art=art),
                 ticket_card.climb_result_svg(dict(rung, result='win', actual='all 2 legs won'), {'g': game}, art=art),
                 ticket_card.cooked_svg(cooked, dict(game, players=[{'id': '7', 'team': '1'}]),
                                        art={'kind': 'photo', 'uri': photo},
                                        player_side='away', fetch=lambda _: photo),
                 ticket_card.prep_svg(prep, fetch=lambda _: None)]
        for index, svg in enumerate(cards):
            with self.subTest(family=index):
                self.assertEqual(check_svg.issues(svg), [])


if __name__ == '__main__':
    unittest.main()
