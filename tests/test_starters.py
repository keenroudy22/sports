import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fakegames
import starters

STRENGTH = {'A': 8, 'B': 3, 'C': 0, 'D': -3}


def passer(team, pid, att):
    return {'id': pid, 'team': team, 'pos': 'QB', 'att': att, 'cmp': att // 2, 'passYds': att * 7}


def season(a_passers):
    """Eight weeks; team A's passers per week from `a_passers` (list of lists of (pid, att)); others steady."""
    games = fakegames.season(STRENGTH, weeks=8)
    by_week = {}
    for game in games:
        by_week.setdefault(game['week'], []).append(game)
    for week, week_games in by_week.items():
        for game in week_games:
            for side in ('home', 'away'):
                team = game[side]['id']
                if team == 'A':
                    game['players'] += [passer('A', pid, att) for pid, att in a_passers[week - 1]]
                else:
                    game['players'].append(passer(team, f'{team}-qb', 32))
    return games


class StarterTests(unittest.TestCase):
    def test_the_starter_is_the_passer_with_the_most_attempts(self):
        game = {'players': [passer('A', 'A1', 30), passer('A', 'A2', 3), passer('B', 'B1', 28)]}
        self.assertEqual(starters.starter(game, 'A'), 'A1')
        self.assertEqual(starters.starter(game, 'B'), 'B1')
        self.assertIsNone(starters.starter(game, 'C'))

    def test_usual_is_the_mode_with_the_most_recent_breaking_ties(self):
        self.assertEqual(starters.usual(['A1', 'A1', 'A2', 'A2']), 'A2')
        self.assertEqual(starters.usual(['A1', 'A2', 'A1', 'A2', 'A1']), 'A1')
        self.assertIsNone(starters.usual([None, None]))

    def test_the_flag_fires_only_when_the_usual_starter_did_not_throw(self):
        # Weeks 1 to 4: A1 starts. Week 5: A1 is hurt, A2 starts. Week 6: A1 back but pulled early (5 attempts).
        # Weeks 7 and 8: A2 starts for good.
        games = season([[('A1', 30)]] * 4 + [[('A2', 28)], [('A1', 5), ('A2', 22)], [('A2', 30)], [('A2', 31)]])
        flags = starters.qb_out_flags(games)
        by_week = {}
        for game in games:
            if 'A' in (game['home']['id'], game['away']['id']):
                by_week[game['week']] = flags[(game['eventId'], 'A')]
        self.assertIsNone(by_week[1]['usual'], 'nothing is known before the first game')
        self.assertFalse(by_week[1]['out'])
        self.assertEqual(by_week[5]['usual'], 'A1')
        self.assertTrue(by_week[5]['out'], 'the usual starter recorded no passing line')
        self.assertFalse(by_week[6]['out'], 'a starter who threw, even briefly, was not out')
        self.assertEqual(by_week[8]['usual'], 'A2', 'by week 8 the mode of the last four games is A2')
        self.assertFalse(by_week[8]['out'])
        self.assertEqual(starters.count(flags)['quarterbackOut'], 1)
        self.assertTrue(all(not f['out'] for (_, team), f in flags.items() if team != 'A'))

    def test_the_cutoff_hides_later_games(self):
        games = season([[('A1', 30)]] * 8)
        cutoff = starters.features.when(games[4]['kickoff'])
        flags = starters.qb_out_flags(games, cutoff)
        self.assertTrue(all(starters.features.when(next(g for g in games if g['eventId'] == e)['kickoff']) < cutoff
                            for (e, _) in flags))

    def test_usual_starter_and_the_live_flag(self):
        games = season([[('A1', 30)]] * 4 + [[('A2', 28)]] * 4)
        end = starters.features.when(games[-1]['kickoff']) + timedelta(days=1)
        self.assertEqual(starters.usual_starter(games, 'A', end), 'A2')
        mid = starters.features.when(games[4 * 2]['kickoff'])          # before week 5
        self.assertEqual(starters.usual_starter(games, 'A', mid), 'A1')
        self.assertTrue(starters.live_qb_out(games, 'A', {'A2', 'X'}, end))
        self.assertFalse(starters.live_qb_out(games, 'A', {'A1'}, end), 'the old starter being out is not the usual one out')
        self.assertFalse(starters.live_qb_out(games, 'Z', {'A2'}, end), 'no history, no flag')


if __name__ == '__main__':
    unittest.main()
