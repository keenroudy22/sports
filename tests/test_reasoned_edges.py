import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reasoned_edges


NOW = datetime(2026, 10, 14, 18, tzinfo=timezone.utc)


def game_capture(at, line, book='DraftKings'):
    return {'retrievedAt': at, 'books': {'draftkings': {'title': book,
            'total': {'line': line, 'over': -110, 'under': -110}}}}


def prop_capture(at, player, market, line):
    return {'retrievedAt': at, 'books': {'draftkings': {'title': 'DraftKings', 'markets': {
            market: {player: {'line': line, 'over': -110, 'under': -110}}}}}}


class ReasonedEdgesTests(unittest.TestCase):
    def context(self):
        return SimpleNamespace(now=NOW,
            games={'CFB-1': {'id': 'CFB-1', 'league': 'CFB', 'kickoff': '2026-10-15T00:00:00Z',
                             'home': {'id': '10'}, 'away': {'id': '20'}}},
            odds_history={'CFB-1': [game_capture('2026-10-12T12:00:00Z', 51.5),
                                    game_capture('2026-10-14T17:00:00Z', 47.5)]},
            prop_odds_history={}, player_logs={}, player_team={}, records=[], injuries={})

    def test_cfb_opener_wind_and_news_reasons_are_silent_and_named(self):
        ctx = self.context()
        ctx.injuries = {'CFB-10': {'qb': {'name': 'QB One', 'position': 'QB', 'status': 'out',
                                          'reportedAt': '2026-10-14T16:00:00Z'}}}
        pick = {'id': 'CFB-under', 'league': 'CFB', 'season': 2026, 'title': 'Under 47.5',
                'marketType': 'total', 'direction': 'under', 'line': 47.5, 'odds': -110,
                'book': 'DraftKings', 'gameIds': ['CFB-1']}
        found = reasoned_edges.detect([pick], ctx, {'CFB-1': {
            'retrievedAt': '2026-10-14T16:30:00Z', 'forecast': {'windMph': 18}}})
        self.assertEqual({row['reasonType'] for row in found}, {'cfb_opener_move'})
        self.assertTrue(all(row['publicEffect'] is False for row in found))

        # News uses a stable line, not the four-point movement above.
        ctx.odds_history['CFB-1'] = [game_capture('2026-10-14T15:00:00Z', 51.5),
                                     game_capture('2026-10-14T16:00:00Z', 47.5),
                                     game_capture('2026-10-14T16:45:00Z', 47.5),
                                     game_capture('2026-10-14T17:00:00Z', 47.5)]
        news = reasoned_edges.detect([pick], ctx, {'CFB-1': {
            'retrievedAt': '2026-10-14T16:30:00Z', 'forecast': {'windMph': 18}}})
        self.assertTrue({'news_not_in_number', 'wind_not_in_total'} <=
                        {row['reasonType'] for row in news})

    def test_receiving_role_fade_and_projection_gap_use_stored_history(self):
        ctx = self.context()
        player = 'Receiver One'
        ctx.prop_odds_history = {'CFB-1': [prop_capture('2026-10-13T12:00:00Z', player, 'recYds', 50.5),
                                           prop_capture('2026-10-14T17:00:00Z', player, 'recYds', 50.5)]}
        logs, records = [], []
        for index, targets in enumerate((2, 2, 2, 5, 5, 5), 1):
            event = f'g{index}'
            logs.append({'eventId': event, 'seasonType': 2, 'team': '10', 'stats': {'targets': targets}})
            records.append({'eventId': event, 'league': 'CFB', 'quality': {'plays': 'ok'},
                            'players': [{'id': '99', 'team': '10', 'pbpTgt': targets},
                                        {'id': '88', 'team': '10', 'pbpTgt': 10 - targets}]})
        ctx.player_logs = {'99': logs}
        ctx.player_team = {'99': '10'}
        ctx.records = records
        under = {'id': 'role-under', 'league': 'CFB', 'season': 2026, 'title': player + ' UNDER 50.5',
                 'athleteId': '99', 'player': player, 'market': 'recYds', 'direction': 'under',
                 'line': 50.5, 'odds': -110, 'book': 'DraftKings', 'gameIds': ['CFB-1'], 'projection': 43}
        over = dict(under, id='projection-over', direction='over', projection=58)
        kinds = {row['reasonType'] for row in reasoned_edges.detect([under, over], ctx, {})}
        self.assertIn('receiving_role_overreaction', kinds)
        self.assertIn('projection_vs_first_capture', kinds)

    def test_role_change_ignores_an_old_team_and_trigger_keeps_kickoff_for_close(self):
        ctx = self.context()
        ctx.now = datetime(2026, 10, 14, 23, 45, tzinfo=timezone.utc)
        player = 'Receiver One'
        ctx.prop_odds_history = {'CFB-1': [prop_capture('2026-10-13T12:00:00Z', player, 'recYds', 50.5),
                                           prop_capture('2026-10-14T23:30:00Z', player, 'recYds', 49.5)]}
        ctx.player_team = {'99': '10'}
        ctx.player_logs = {'99': [
            {'eventId': 'old1', 'seasonType': 2, 'team': 'old', 'stats': {'targets': 10}},
            {'eventId': 'old2', 'seasonType': 2, 'team': 'old', 'stats': {'targets': 10}},
            {'eventId': 'old3', 'seasonType': 2, 'team': 'old', 'stats': {'targets': 10}},
            *[{'eventId': f'g{i}', 'seasonType': 2, 'team': '10', 'stats': {'targets': value}}
              for i, value in enumerate((2, 2, 2, 5, 5, 5), 1)]]}
        ctx.records = [
            {'eventId': f'g{i}', 'league': 'CFB', 'quality': {'plays': 'ok'},
             'players': [{'id': '99', 'team': '10', 'pbpTgt': value},
                         {'id': '88', 'team': '10', 'pbpTgt': 10 - value}]}
            for i, value in enumerate((2, 2, 2, 5, 5, 5), 1)]
        pick = {'id': 'role-under', 'league': 'CFB', 'season': 2026,
                'title': player + ' UNDER 50.5', 'athleteId': '99', 'player': player,
                'market': 'recYds', 'direction': 'under', 'line': 50.5, 'odds': -110,
                'book': 'DraftKings', 'gameIds': ['CFB-1'],
                'kickoff': '2026-10-15T00:00:00Z', 'projection': 43}
        found = reasoned_edges.detect([pick], ctx, {})
        role = next(row for row in found if row['reasonType'] == 'receiving_role_overreaction')
        self.assertEqual(role['candidate']['kickoff'], pick['kickoff'])
        ctx.games = {}
        close = reasoned_edges.same_book_close(role, ctx)
        self.assertEqual(close[1][0], 49.5)

    def test_private_ledger_is_deduplicated_checked_and_reports_inconclusive(self):
        ctx = self.context()
        pick = {'id': 'CFB-under', 'league': 'CFB', 'season': 2026, 'title': 'Under 47.5',
                'marketType': 'total', 'direction': 'under', 'line': 47.5, 'odds': -110,
                'book': 'DraftKings', 'gameIds': ['CFB-1']}
        found = reasoned_edges.detect([pick], ctx, {})
        with tempfile.TemporaryDirectory() as folder:
            path, manifest = Path(folder) / 'rows.jsonl', Path(folder) / 'ledger.json'
            self.assertEqual(reasoned_edges.append(found, path, manifest), 1)
            self.assertEqual(reasoned_edges.append(found, path, manifest), 0)
            table = reasoned_edges.report(path)
            row = next(row for row in table if row['type'] == 'cfb_opener_move')
            self.assertEqual((row['rows'], row['finding']), (1, 'inconclusive'))
            path.write_text(path.read_text() + '{}\n')
            with self.assertRaisesRegex(ValueError, 'changed'):
                reasoned_edges.append([dict(found[0], id='different')], path, manifest)


if __name__ == '__main__':
    unittest.main()
