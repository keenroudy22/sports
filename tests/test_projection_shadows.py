import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import projection_shadows
import reasoned_edges


NOW = datetime(2026, 10, 14, 18, tzinfo=timezone.utc)


def game(event, kickoff, team='2229', season=2026, qb='kohl', qb_att=40, player='kohl', value=40):
    return {'eventId': event, 'league': 'CFB', 'season': season, 'seasonType': 2, 'week': 1,
            'kickoff': kickoff, 'home': {'id': team}, 'away': {'id': 'opp'}, 'quality': {'plays': 'ok'},
            'players': [{'id': qb, 'name': 'QB', 'team': team, 'pos': 'QB', 'att': qb_att,
                         'cmp': 20, 'passYds': 200},
                        *([] if player == qb else [{'id': player, 'name': 'Player', 'team': team,
                                                   'pos': 'WR', 'pbpTgt': value, 'rec': value / 2,
                                                   'recYds': value * 6}])],
            'teams': {team: {'points': 20}, 'opp': {'points': 10}}, 'sources': {'page': 'test'}}


class ProjectionShadowTests(unittest.TestCase):
    def context(self, records, player='kohl', team='2229', starter='kohl'):
        forecast = {'id': player, 'name': 'Player', 'pos': 'QB' if player == 'kohl' else 'WR',
                    'att': [23.7, 10, 40], 'passYds': [167, 80, 260],
                    'targets': [8, 3, 13], 'receptions': [4, 1, 7], 'recYds': [50, 15, 90]}
        snapshot = {'gameId': 'CFB-next', 'league': 'CFB', 'publishedAt': '2026-10-14T17:00:00Z',
                    'players': {'home': {'players': [forecast]}, 'away': {'players': []}}}
        return SimpleNamespace(now=NOW, records=records, games={'CFB-next': {'id': 'CFB-next', 'league': 'CFB',
            'season': 2026, 'kickoff': '2026-10-15T00:00:00Z', 'home': {'id': team}, 'away': {'id': 'opp'}}},
            player_team={player: team}, starters={f'CFB-{team}': starter}, policy={},
            snapshot=lambda game_id: snapshot, prop_odds={}, odds={})

    def test_kohl_partial_and_old_team_games_do_not_drive_shadow(self):
        records = [
            game('old', '2025-10-01T00:00:00Z', team='other', qb='kohl', qb_att=5, value=5),
            game('g1', '2026-09-20T00:00:00Z', qb_att=50, value=50),
            game('g2', '2026-09-27T00:00:00Z', qb_att=36, value=36),
            game('partial', '2026-10-01T00:00:00Z', qb='marker', qb_att=38, player='kohl', value=4),
            game('g3', '2026-10-05T00:00:00Z', qb_att=43, value=43)]
        ctx = self.context(records)
        pick = {'id': 'kohl', 'league': 'CFB', 'athleteId': 'kohl', 'market': 'att',
                'direction': 'under', 'line': 33.5, 'odds': -110, 'book': 'DraftKings',
                'gameIds': ['CFB-next'], 'projection': 23.7, 'quotedAt': '2026-10-14T17:00:00Z'}
        row = projection_shadows.shadow(pick, ctx)
        self.assertGreaterEqual(row['currentTeamFullGame'], 33)
        self.assertEqual(row['fullOrMissedGames'], 3)
        self.assertFalse(row['publicEffect'])
        ctx.player_team['marker'] = '2229'
        marker = dict(pick, id='marker', athleteId='marker', projection=8)
        self.assertLessEqual(projection_shadows.shadow(marker, ctx)['currentTeamFullGame'], 3)

    def test_damante_king_same_qb_and_missing_game_variants_are_logged_privately(self):
        records = [game('g1', '2026-09-20T00:00:00Z', team='166', qb='damante', qb_att=30,
                        player='king', value=8),
                   game('g2', '2026-09-27T00:00:00Z', team='166', qb='damante', qb_att=28,
                        player='king', value=7),
                   game('g3', '2026-10-04T00:00:00Z', team='166', qb='hed', qb_att=30,
                        player='king', value=2)]
        ctx = self.context(records, player='king', team='166', starter='damante')
        pick = {'id': 'king', 'league': 'CFB', 'athleteId': 'king', 'market': 'recYds',
                'direction': 'over', 'line': 49.5, 'odds': -110, 'book': 'DraftKings',
                'gameIds': ['CFB-next'], 'projection': 35, 'quotedAt': '2026-10-14T17:00:00Z'}
        row = projection_shadows.shadow(pick, ctx)
        self.assertGreater(row['sameQBProjection'], row['liveProjection'])
        with tempfile.TemporaryDirectory() as folder:
            path, manifest = Path(folder) / 'rows.jsonl', Path(folder) / 'ledger.json'
            self.assertEqual(projection_shadows.capture([pick], ctx, path, manifest), 1)
            self.assertEqual(projection_shadows.capture([pick], ctx, path, manifest), 0)
            self.assertEqual(projection_shadows.report(path)['status'], 'inconclusive')

    def test_nfl_receivers_share_the_same_private_path_for_javonte_and_bucky(self):
        for player in ('javonte', 'bucky'):
            with self.subTest(player=player):
                records = [dict(game('g1', '2026-09-20T00:00:00Z', team='nfl', qb='backup', qb_att=25,
                                     player=player, value=6), league='NFL'),
                           dict(game('g2', '2026-09-27T00:00:00Z', team='nfl', qb='backup', qb_att=30,
                                     player=player, value=5), league='NFL')]
                for row in records:
                    row['league'] = 'NFL'
                ctx = self.context(records, player=player, team='nfl', starter='backup')
                ctx.games['CFB-next']['league'] = 'NFL'
                ctx.snapshot('CFB-next')['league'] = 'NFL'
                pick = {'id': player, 'league': 'NFL', 'athleteId': player, 'market': 'rec',
                        'direction': 'over', 'line': 2.5, 'odds': -110, 'book': 'DraftKings',
                        'gameIds': ['CFB-next'], 'projection': 3, 'quotedAt': '2026-10-14T17:00:00Z'}
                self.assertIsNotNone(projection_shadows.shadow(pick, ctx))

    def test_finished_shadow_gets_actual_error_and_same_book_close(self):
        final = game('final', '2026-10-14T17:00:00Z', team='166', qb='damante', qb_att=30,
                     player='king', value=8)
        ctx = self.context([final], player='king', team='166', starter='damante')
        ctx.games = {}
        ctx.prop_odds_history = {'CFB-final': [
            {'retrievedAt': '2026-10-14T15:00:00Z', 'books': {'draftkings': {'title': 'DraftKings',
             'markets': {'recYds': {'Player': {'line': 49.5, 'over': -110, 'under': -110}}}}}}]}
        row = {'type': 'shadow', 'id': 'one', 'candidate': {
            'id': 'king', 'league': 'CFB', 'title': 'Player OVER 49.5 receiving yards',
            'athleteId': 'king', 'market': 'recYds', 'direction': 'over', 'line': 49.5,
            'odds': -110, 'book': 'DraftKings', 'gameIds': ['CFB-final'],
            'kickoff': '2026-10-14T17:00:00Z'}, 'liveProjection': 50,
            'currentTeamFullGame': 48, 'walkForwardMedian': 45, 'sameQBProjection': 55}
        with tempfile.TemporaryDirectory() as folder:
            path, manifest = Path(folder) / 'rows.jsonl', Path(folder) / 'ledger.json'
            reasoned_edges.append([row], path, manifest)
            self.assertEqual(projection_shadows.settle(ctx, NOW, path, manifest), 1)
            grade = reasoned_edges.rows(path)[-1]
            self.assertEqual(grade['actual'], 48)
            self.assertEqual(grade['sameBookClose'], 49.5)
            self.assertEqual(grade['absoluteError']['sameQBProjection'], 7)

    def test_daniels_partial_cameo_is_not_a_full_rushing_game(self):
        records = [game('g1', '2026-09-20T00:00:00Z', team='27', qb='daniels', qb_att=25,
                        player='daniels', value=25),
                   game('g2', '2026-09-27T00:00:00Z', team='27', qb='daniels', qb_att=28,
                        player='daniels', value=28)]
        for row, carries, yards in zip(records, (8, 1), (44, 2)):
            qb = row['players'][0]
            qb.update(car=carries, rushYds=yards)
        ctx = self.context(records, player='daniels', team='27', starter='daniels')
        pick = {'id': 'daniels-rush', 'league': 'CFB', 'athleteId': 'daniels', 'market': 'rushYds',
                'direction': 'over', 'line': 25.5, 'odds': -110, 'book': 'DraftKings',
                'gameIds': ['CFB-next'], 'projection': 15, 'quotedAt': '2026-10-14T17:00:00Z'}
        row = projection_shadows.shadow(pick, ctx)
        self.assertEqual(row['fullOrMissedGames'], 1)
        self.assertEqual(row['currentTeamFullGame'], 44)


if __name__ == '__main__':
    unittest.main()
