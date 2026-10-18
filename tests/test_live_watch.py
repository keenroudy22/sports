import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import live_watch as L


NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


def summary(yards=55, completed=False):
    return {'header': {'competitions': [{'competitors': [
                {'homeAway': 'away', 'score': '10', 'team': {'id': '1', 'abbreviation': 'AWY'}},
                {'homeAway': 'home', 'score': '14', 'team': {'id': '2', 'abbreviation': 'HME'}}],
            'status': {'period': 2, 'displayClock': '4:10', 'type': {'state': 'post' if completed else 'in',
                       'completed': completed, 'shortDetail': 'Final' if completed else '4:10 - 2nd'}}}]},
            'boxscore': {'players': [{'team': {'id': '2'}, 'statistics': [{'name': 'receiving',
                'keys': ['receptions', 'receivingYards', 'receivingTouchdowns', 'longReception', 'receivingTargets'],
                'athletes': [{'athlete': {'id': '7', 'displayName': 'Receiver'},
                              'stats': ['4', str(yards), '0', '22', '6']}]}]}]}}


class LiveWatchTests(unittest.TestCase):
    def setUp(self):
        self.pick = {'id': 'p', 'gameIds': ['NFL-1'], 'athleteId': '7', 'market': 'receiving yards',
                     'direction': 'over', 'line': 49.5, 'odds': -110, 'title': 'Receiver over 49.5 receiving yards'}
        self.ctx = SimpleNamespace(first={'p': self.pick}, latest={}, games={})
        self.games = {'NFL-1': {'id': 'NFL-1', 'league': 'NFL', 'kickoff': '2026-10-03T17:00:00Z'}}
        self.log = {'posts': [{'id': 'p', 'kind': 'buffer:play', 'sentAt': '2026-10-03T16:00:00Z',
                               'discord': {'state': 'sent'}}]}

    def test_shadow_records_crossing_correction_and_final_without_posting(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'live.json'
            first = L.run_shadow(self.ctx, self.games, self.log, NOW, state,
                                 fetch=lambda _: summary(55), log=lambda *_: None)
            self.assertEqual(first['events'][0]['kind'], 'hit-early')
            self.assertEqual(json.loads(state.read_text())['mode'], 'shadow')
            calls = []
            quiet = L.run_shadow(self.ctx, self.games, self.log, NOW + timedelta(minutes=2), state,
                                 fetch=lambda u: calls.append(u), log=lambda *_: None)
            self.assertEqual((quiet['reason'], calls), ('cadence', []))
            corrected = L.run_shadow(self.ctx, self.games, self.log, NOW + timedelta(minutes=5), state,
                                     fetch=lambda _: summary(45), log=lambda *_: None)
            self.assertEqual({e['kind'] for e in corrected['events']}, {'close', 'correction'})
            final = L.run_shadow(self.ctx, self.games, self.log, NOW + timedelta(minutes=10), state,
                                 fetch=lambda _: summary(55, completed=True), log=lambda *_: None)
            self.assertEqual(final['events'][0]['kind'], 'final-win')

    def test_moneyline_final_reaches_grader_without_player_stats(self):
        self.pick = {'id': 'p', 'gameIds': ['NFL-1'], 'legs': [
            {'id': 'ml', 'gameId': 'NFL-1', 'marketType': 'moneyline', 'direction': 'home', 'line': 0}]}
        self.ctx.first = {'p': self.pick}
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'live.json'
            live = L.run_shadow(self.ctx, self.games, self.log, NOW, state,
                                fetch=lambda _: summary(), log=lambda *_: None)
            self.assertFalse(any(e['kind'] == 'hit-early' for e in live['events']))
            final = L.run_shadow(self.ctx, self.games, self.log, NOW + timedelta(minutes=5), state,
                                 fetch=lambda _: summary(completed=True), log=lambda *_: None)
            self.assertEqual(final['pendingFinals'], ['p'])
            self.assertEqual(final['events'][0]['kind'], 'final-win')
            self.assertEqual(L.progress({'marketType': 'moneyline', 'direction': 'away', 'line': 0},
                                       L.final_records(state)[0])['state'], 'final-loss')

    def test_only_public_plays_are_tracked(self):
        self.log['posts'][0].pop('sentAt')
        self.log['posts'][0]['discord'] = {'state': 'pending'}
        self.assertEqual(L.tracked(self.ctx, self.games, self.log, NOW), [])

    def test_outage_cannot_duplicate_an_early_hit_and_official_result_reconciles(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state.json'
            L.run_shadow(self.ctx,self.games,self.log,NOW,state,fetch=lambda _:summary(),log=lambda *_:None)
            def offline(_): raise OSError('offline')
            L.run_shadow(self.ctx,self.games,self.log,NOW+timedelta(minutes=5),state,fetch=offline,log=lambda *_:None)
            self.assertEqual(json.loads(state.read_text())['health']['unavailable'],1)
            result=L.run_shadow(self.ctx,self.games,self.log,NOW+timedelta(minutes=10),state,fetch=lambda _:summary(),log=lambda *_:None)
            self.assertEqual(result['events'],[])
            self.ctx.latest={'p':{'result':'win','settledAt':'2026-10-03T21:00:00Z'}}
            L.run_shadow(self.ctx,self.games,self.log,NOW+timedelta(hours=4),state,fetch=lambda _:summary(),log=lambda *_:None)
            self.assertEqual(json.loads(state.read_text())['settlements']['p']['result'],'win')

    def test_a_verified_final_is_handed_to_the_official_grader(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'state.json'
            result = L.run_shadow(self.ctx, self.games, self.log, NOW, state,
                                  fetch=lambda _: summary(55, completed=True), log=lambda *_: None)
            self.assertEqual(result['pendingFinals'], ['p'])
            records = L.final_records(state)
            self.assertTrue(records[0]['completed'])
            history = []
            grading = L.settlement_records(history, records)
            # Exercise the crashed roster path with the same summary-only final.
            self.assertNotIn('season', grading[0])
            self.assertEqual(L.gates.roster_facts(history, NOW)[4], {})
            self.assertEqual(L.desk_run.grade_prop(self.pick, grading[0])[0], 'win')
            self.assertEqual(history, [])
            games = {'NFL-1': {'id': 'NFL-1', 'league': 'NFL', 'away': {}, 'home': {}}}
            L.overlay_finals(games, records)
            self.assertEqual((games['NFL-1']['completed'], games['NFL-1']['away']['score'],
                              games['NFL-1']['home']['score']), (True, 10, 14))
            L.mark_official_attempt(NOW, state)
            quiet = L.run_shadow(self.ctx, self.games, self.log, NOW + timedelta(minutes=5), state,
                                 fetch=lambda _: summary(55, completed=True), log=lambda *_: None)
            self.assertEqual(quiet['pendingFinals'], [])

    def test_settlement_records_keep_captured_box_score_and_ignore_unfinished(self):
        stored = {'league': 'NFL', 'eventId': '1', 'season': 2026}
        observed = {'league': 'NFL', 'eventId': '1', 'completed': True}
        unfinished = {'league': 'NFL', 'eventId': '2', 'completed': False}
        history = [stored]
        self.assertEqual(L.settlement_records(history, [observed, unfinished]), history)
        self.assertEqual(history, [stored])


if __name__ == '__main__':
    unittest.main()
