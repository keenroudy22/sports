import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuity
import fakegames
import model_v2

STRENGTH = {'A': 8, 'B': 3, 'C': 0, 'D': -3, 'E': -8, 'F': 0}
EXACT = {'margin': {'halfLife': 10000, 'ridge': 0.01, 'priorWeight': 1.0, 'eloWeight': 0.0},
         'total': {'halfLife': 10000, 'ridge': 0.01, 'priorWeight': 1.0, 'blend': 1.0},
         'sdMargin': 13.0, 'sdTotal': 13.0, 'pace': 65.0}


def lines(team, suffix, att=30, car=15, tgt=8):
    """Three offensive lines for a team: a passer, a runner and a receiver, named by suffix."""
    return [{'id': f'{team}-qb{suffix}', 'team': team, 'pos': 'QB', 'att': att, 'cmp': 20, 'passYds': 240},
            {'id': f'{team}-rb{suffix}', 'team': team, 'pos': 'RB', 'car': car, 'rushYds': 60},
            {'id': f'{team}-wr{suffix}', 'team': team, 'pos': 'WR', 'tgt': tgt, 'rec': 5, 'recYds': 70}]


def two_seasons(turnover=(), weeks_now=2, strength_now=None):
    """A full 2024 season, then `weeks_now` weeks of 2025. Teams in `turnover` field an all-new roster in 2025."""
    last = fakegames.season(STRENGTH, weeks=10, year=2024, start=fakegames.START - timedelta(days=365))
    now = fakegames.season(strength_now or STRENGTH, weeks=weeks_now, year=2025, first_event=1000)
    for game in last:
        for side in ('home', 'away'):
            game['players'] += lines(game[side]['id'], '')
    for game in now:
        for side in ('home', 'away'):
            team = game[side]['id']
            game['players'] += lines(team, '-new' if team in turnover else '')
    return last + now


class UsageTests(unittest.TestCase):
    def test_usage_counts_attempts_carries_and_targets_by_team_and_season(self):
        games = two_seasons()
        usage = continuity.offense_usage(games, 2024)
        self.assertEqual(usage['A']['A-qb'], 30 * 10)
        self.assertEqual(usage['A']['A-rb'], 15 * 10)
        self.assertEqual(usage['A']['A-wr'], 8 * 10)
        self.assertNotIn('A-qb-new', usage['A'])

    def test_continuity_is_none_before_the_first_game_and_uses_only_games_before_the_cutoff(self):
        games = two_seasons(turnover={'A'})
        first_2025 = min(model_v2.features.when(g['kickoff']) for g in games if g['season'] == 2025)
        before = continuity.offense_continuity(games, 2025, first_2025)
        self.assertTrue(all(v is None for v in before.values()), 'nothing is known before a game is played')
        after = continuity.offense_continuity(games, 2025, first_2025 + timedelta(days=1))
        self.assertEqual(after['A'], 0.0, 'an all-new roster returns none of last season')
        self.assertEqual(after['B'], 1.0, 'a returned roster keeps all of it')
        table = continuity.continuity(games, 2025, first_2025 + timedelta(days=1))
        self.assertIsNone(table['A']['def'], 'defense is not measured yet')
        self.assertEqual(continuity.summary(table)['known'], 6)

    def test_a_partial_return_is_the_returning_share_of_usage(self):
        games = two_seasons()
        cutoff = model_v2.features.when(games[-1]['kickoff']) + timedelta(days=1)
        # In 2025 team C's receiver is new; the passer and runner are back: (300 + 150) / (300 + 150 + 80).
        for game in games:
            if game['season'] == 2025:
                for player in game['players']:
                    if player['id'] == 'C-wr':
                        player['id'] = 'C-wr-new'
        self.assertAlmostEqual(continuity.offense_continuity(games, 2025, cutoff)['C'], 450 / 530, places=6)


class ModelTests(unittest.TestCase):
    def test_zero_continuity_is_v2_exactly(self):
        games = two_seasons(turnover={'A'})
        cutoff = model_v2.features.when(games[-1]['kickoff']) + timedelta(days=1)
        plain = model_v2.Model('NFL', games, cutoff, 2025, EXACT)
        zero = {**EXACT, 'margin': {**EXACT['margin'], 'continuity': 0.0}}
        same = model_v2.Model('NFL', games, cutoff, 2025, zero)
        for team in STRENGTH:
            self.assertAlmostEqual(plain.predict(team, 'F')['margin'], same.predict(team, 'F')['margin'], places=9)
        self.assertEqual(plain.roster, {}, 'v2.0 parameters never measure continuity')

    def test_a_rebuilt_team_keeps_less_of_last_season(self):
        # A was +8 in 2024 and is -8 in 2025 with an all-new roster; the others are unchanged.
        games = two_seasons(turnover={'A'}, weeks_now=3, strength_now={**STRENGTH, 'A': -8})
        cutoff = model_v2.features.when(games[-1]['kickoff']) + timedelta(days=1)
        params = {**EXACT, 'margin': {**EXACT['margin'], 'priorWeight': 0.6}}
        plain = model_v2.Model('NFL', games, cutoff, 2025, params).predict('A', 'C')['margin']
        bent_params = {**params, 'margin': {**params['margin'], 'continuity': 2.0}}
        bent_model = model_v2.Model('NFL', games, cutoff, 2025, bent_params)
        bent = bent_model.predict('A', 'C')['margin']
        self.assertLess(bent, plain, 'less of the strong 2024 survives for a team that returned nobody')
        self.assertEqual(bent_model.roster['A']['off'], 0.0)
        self.assertEqual(bent_model.roster['B']['off'], 1.0)


if __name__ == '__main__':
    unittest.main()
