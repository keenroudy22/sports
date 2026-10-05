import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_editor as editor
import llm
import run

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = {'id': 'NFL-123', 'league': 'NFL', 'kickoff': '2026-10-06T00:15:00Z',
                     'state': 'pre', 'away': {'abbr': 'ATL'}, 'home': {'abbr': 'NO'}}
        self.trend = {'player': 'Player One', 'title': 'Over 3.5 receptions', 'games': 4, 'hits': 3,
                      'kind': 'main', 'odds': -110, 'book': 'FanDuel', 'observedAt': NOW.isoformat()}
        self.usage = {'player': 'Player Two', 'games': 3, 'redZone': 9, 'inside10': 4,
                      'roleSnapshotAt': NOW.isoformat()}
        self.write()

    def write(self, generated=None):
        editor.save(self.root / 'app/today.json', {'generatedAt': generated or NOW.isoformat(), 'games': [self.game]})
        editor.save(self.root / 'app/games/NFL-123.json', {'seasonTrends': [self.trend], 'scorerResearch': [self.usage]})

    def prepare(self, now=NOW, ask=None, **kw):
        return editor.prepare(now, self.root, self.root / 'public.json', self.root / 'state.json', ask, **kw)

    def test_exact_facts_one_local_call_and_no_rewrites(self):
        ask = mock.Mock(return_value={'stories': ['E0', 'E1']})
        self.assertEqual(self.prepare(ask=ask)['status'], 'updated')
        rows = editor.read(self.root / 'public.json')['rows']
        self.assertIn('3/4 recorded games', rows[0]['text'])
        self.assertIn('FanDuel -110 captured', rows[0]['text'])
        self.assertIn('9 red-zone', rows[1]['text'])
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(ask.call_args.kwargs['timeout'], 180)
        self.assertEqual(ask.call_args.kwargs['kind'], 'homepage-editor')

    def test_bad_ids_or_model_failure_cannot_publish(self):
        for result in ({'stories': ['E999']}, {'stories': [{'id': 'E0'}]}, {'stories': []}, 'bad'):
            self.assertIsNone(editor.select(editor.candidates(self.root, NOW), lambda *a, **k: result))
        def fail(*a, **k):
            raise llm.LLMUnavailable('busy')
        self.assertEqual(self.prepare(ask=fail)['status'], 'local-unavailable-or-invalid')
        self.assertFalse((self.root / 'public.json').exists())
        self.assertEqual(self.prepare(ask=fail)['status'], 'cooldown')

    def test_stale_prices_injuries_small_samples_alternates_and_kickoff(self):
        original = dict(self.trend)
        for change in ({'observedAt': (NOW-timedelta(hours=5)).isoformat()}, {'games': 2, 'hits': 2},
                       {'kind': 'alternate'}, {'injuryStatus': 'Out'}, {'odds': None}, {'hits': 1}):
            self.trend = dict(original, **change)
            self.write()
            self.assertFalse(any(r['kind'] == 'trend' for r in editor.candidates(self.root, NOW)))
        self.game['state'] = 'in'
        self.write()
        self.assertEqual(editor.candidates(self.root, NOW), [])

    def test_stale_sources_and_disabled_mode_make_no_call(self):
        self.write((NOW-timedelta(hours=5)).isoformat())
        ask = mock.Mock()
        self.assertEqual(self.prepare(ask=ask)['status'], 'no-fresh-facts')
        self.assertEqual(self.prepare(ask=ask, enabled=False)['status'], 'disabled')
        ask.assert_not_called()

    def test_unchanged_facts_refresh_source_expiry_without_another_call(self):
        ask = mock.Mock(return_value={'stories': ['E0']})
        self.prepare(ask=ask)
        self.trend['observedAt'] = (NOW+timedelta(hours=2)).isoformat()
        self.write((NOW+timedelta(hours=2)).isoformat())
        self.assertEqual(self.prepare(NOW+timedelta(hours=2), ask)['status'], 'unchanged')
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(editor.read(self.root/'public.json')['rows'][0]['observedAt'], self.trend['observedAt'])

    def test_one_player_not_repeated(self):
        rows = editor.candidates(self.root, NOW)
        rows[1]['player'] = rows[0]['player']
        self.assertEqual(len(editor.select(rows, lambda *a, **k: {'stories': ['E0', 'E0', 'E1']})), 1)

    def test_duplicate_books_do_not_crowd_out_another_player(self):
        editor.save(self.root / 'app/games/NFL-123.json', {'seasonTrends': [self.trend,
                    dict(self.trend, odds=-120, book='DraftKings'), dict(self.trend, player='Player Three')]})
        rows = editor.candidates(self.root, NOW)
        self.assertEqual([r['player'] for r in rows], ['Player One', 'Player Three'])
        self.assertIn('FanDuel -110', rows[0]['text'])

    def test_multiple_sports_require_confirmed_fresh_schedule(self):
        fixture = {'id': 'NHL-22', 'kickoff': '2026-10-06T02:00:00Z', 'status': 'scheduled',
                   'timeConfirmed': True, 'updatedAt': NOW.isoformat(),
                   'teams': {'away': {'abbreviation': 'A'}, 'home': {'abbreviation': 'B'}}}
        editor.save(self.root / 'sports.json', {'leagues': {'NHL': {'status': 'ok', 'games': [fixture]}}})
        rows = editor.candidates(self.root, NOW)
        self.assertEqual(rows[-1]['href'], '#scores/NHL')
        fixture['timeConfirmed'] = False
        editor.save(self.root / 'sports.json', {'leagues': {'NHL': {'status': 'ok', 'games': [fixture]}}})
        self.assertFalse(any(r['kind'] == 'schedule' for r in editor.candidates(self.root, NOW)))

    def test_optional_failure_never_stops_run_and_paths_are_recoverable(self):
        with mock.patch('local_editor.prepare', side_effect=OSError('disk')):
            status = {}
            run.homepage_editor(NOW, status)
        self.assertEqual(status['localEditor']['status'], 'error')
        self.assertTrue(run.allowed('site/data/desk-notes.json'))
        self.assertTrue('site/data/desk-notes.json'.startswith(run.LEFTOVER))
        source = Path(run.__file__).read_text()
        self.assertLess(source.index('buffer_posts(now, ctx'), source.index('homepage_editor(now, status, enabled=use_llm)'))

    def test_sports_request_keeps_warm_without_changing_shared_server_settings(self):
        def transport(url, body, headers, timeout):
            self.assertEqual(body['keep_alive'], llm.KEEP_ALIVE)
            self.assertEqual(url, 'http://localhost:11434/api/chat')
            return json.dumps({'message': {'content': '{"stories":["E0"]}'}})
        self.assertEqual(llm.draft_json('Select', 'facts', {}, send=transport, base='http://localhost:11434'), {'stories':['E0']})


if __name__ == '__main__':
    unittest.main()
