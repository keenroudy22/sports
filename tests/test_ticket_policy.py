import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import easy_parlay
import run

NOW = datetime(2026, 10, 4, 14, tzinfo=timezone.utc)


def context(picks=()):
    return SimpleNamespace(now=NOW, first={p['id']: p for p in picks}, latest={})


def straight(**extra):
    return dict(id='NFL-straight', gameIds=['NFL-1'], athleteId='77', market='rec', line=2.5,
                publishedAt='2026-10-03T17:00Z', **extra)


def ticket(**extra):
    return dict(id='NFL-ticket', league='NFL', gameIds=['NFL-1'],
                legs=[{'gameId': 'NFL-1', 'athleteId': '77', 'market': 'recYds', 'line': 19.5, 'alternate': True}],
                publishedAt='2026-10-04T12:00Z', **extra)


class TicketPolicyTests(unittest.TestCase):
    def test_overlap_is_bidirectional_across_lines_markets_and_publication_dates(self):
        self.assertFalse(gates.player_overlap(ticket(), context([straight()])).ok)
        self.assertFalse(gates.player_overlap(straight(), context([ticket()])).ok)
        self.assertFalse(gates.player_overlap(ticket(parlayType='ladder'), context([straight()])).ok)
        earlier_ticket = dict(ticket(), id='NFL-earlier-ticket')
        self.assertFalse(gates.player_overlap(ticket(parlayType='ladder'), context([earlier_ticket])).ok,
                         'the same player/game cannot be repeated across a longshot and ladder')
        expired = straight(status='expired')
        self.assertFalse(gates.player_overlap(ticket(), context([expired])).ok)

    def test_different_game_player_and_revisions_are_not_false_overlap(self):
        ctx = context([straight()])
        for leg in [{'gameId': 'NFL-2', 'athleteId': '77'}, {'gameId': 'NFL-1', 'athleteId': '88'}]:
            self.assertTrue(gates.player_overlap({'legs': [leg]}, ctx).ok)
        self.assertNotIn(gates.player_overlap, gates.RULES['revision'])
        for kind in ('propLean', 'favorite', 'researched', 'longshot', 'ladder'):
            self.assertIn(gates.player_overlap, gates.RULES[kind])

    def test_legacy_leg_ids_and_filtering_before_selection(self):
        self.assertIsNone(gates.player_exposure('Old text-only leg'))
        old = {'id': 'prop-NFL-1-77-recYds', 'gameId': 'NFL-1'}
        other = {'id': 'prop-NFL-1-88-recYds', 'gameId': 'NFL-1'}
        self.assertEqual(gates.without_straight_players([old, other], context([straight()])), [other])
        self.assertFalse(gates.player_overlap(straight(), context([dict(ticket(), legs=[old])])).ok)

    def test_alternate_exception_is_league_scoped_and_ladder_exempt(self):
        ctx = context([ticket()])
        self.assertFalse(gates.alternate_parlay_frequency({'league': 'NFL', 'parlayType': 'easyProps'}, ctx).ok)
        self.assertTrue(gates.alternate_parlay_frequency({'league': 'CFB', 'parlayType': 'easyProps'}, ctx).ok)
        self.assertTrue(gates.alternate_parlay_frequency(ticket(parlayType='ladder'), ctx).ok)
        self.assertTrue(gates.alternate_parlay_frequency({'league': 'NFL', 'legs': [{'alternate': False}]}, ctx).ok)
        ctx.first['NFL-ticket']['publishedAt'] = gates.stamp(NOW - timedelta(days=7))
        self.assertTrue(gates.alternate_parlay_frequency({'league': 'NFL', 'parlayType': 'easyProps'}, ctx).ok)

    def test_easy_ticket_stops_before_fetch_when_exception_used(self):
        with mock.patch.object(easy_parlay, 'fetch_day') as fetch:
            pick, reason = easy_parlay.candidate(context([ticket()]), {}, NOW)
        self.assertIsNone(pick)
        self.assertIn('seven days', reason)
        fetch.assert_not_called()

    def test_longshot_tries_main_lines_without_shared_player_first(self):
        ctx = context([straight()])
        rows = [{'gameId': 'NFL-1', 'athleteId': '77'}, {'gameId': 'NFL-2', 'athleteId': '88'}]
        with mock.patch.object(run.parlay, 'build', return_value=(None, 'not enough')) as build, \
                mock.patch.object(run, 'longshot_alternates', return_value=[]) as alternates:
            run.longshot_candidate(rows, {}, NOW, 'NFL', ctx=ctx)
        self.assertEqual(build.call_args_list[0].args[0], [rows[1]])
        self.assertEqual(len(build.call_args_list[0].args), 6, 'first attempt has no alternate pool')
        alternates.assert_called_once()
