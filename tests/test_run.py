import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run


class SlotTests(unittest.TestCase):
    def test_slots_map_to_the_prompt_table_in_eastern_time(self):
        self.assertEqual(run.slot_for(datetime(2026, 9, 27, 11, 5, tzinfo=timezone.utc)).strftime('%H%M'), '0645')   # 7:05 ET Sunday
        self.assertEqual(run.slot_for(datetime(2026, 9, 27, 19, 20, tzinfo=timezone.utc)).strftime('%H%M'), '1445')  # 3:20 ET Sunday
        self.assertIsNone(run.slot_for(datetime(2026, 9, 29, 19, 20, tzinfo=timezone.utc)), 'no 14:45 on a Tuesday')
        self.assertIsNone(run.slot_for(datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)), '10:00 ET is between runs')
        self.assertEqual(run.slot_for(datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)).strftime('%Y-%m-%d %H%M'), '2026-09-27 2330')

    def test_slots_across_the_dst_change(self):
        self.assertEqual(run.slot_for(datetime(2026, 11, 1, 11, 50, tzinfo=timezone.utc)).strftime('%H%M'), '0645')  # EST
        self.assertEqual(run.slot_for(datetime(2026, 3, 8, 10, 50, tzinfo=timezone.utc)).strftime('%H%M'), '0645')   # EDT

    def test_forced_slot(self):
        self.assertEqual(run.slot_for(datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc), '1145').strftime('%H%M'), '1145')


class GradingTests(unittest.TestCase):
    GAME = {'id': 'NFL-1', 'league': 'NFL', 'home': {'short': 'Lions', 'abbreviation': 'DET', 'score': 27},
            'away': {'short': 'Bills', 'abbreviation': 'BUF', 'score': 24}, 'completed': True}

    def test_spread_and_total_grades(self):
        self.assertEqual(run.grade_game_pick({'marketType': 'spread', 'line': -2.5, 'direction': 'home'}, self.GAME), ('win', 'Bills 24, Lions 27', 3))
        self.assertEqual(run.grade_game_pick({'marketType': 'spread', 'line': -3, 'direction': 'home'}, self.GAME)[0], 'push')
        self.assertEqual(run.grade_game_pick({'marketType': 'spread', 'line': 2.5, 'direction': 'away'}, self.GAME)[0], 'loss')
        self.assertEqual(run.grade_game_pick({'marketType': 'total', 'line': 50.5, 'direction': 'over'}, self.GAME), ('win', 'Bills 24, Lions 27', 51))
        self.assertEqual(run.grade_game_pick({'marketType': 'total', 'line': 51, 'direction': 'under'}, self.GAME)[0], 'push')
        self.assertIsNone(run.grade_game_pick({'marketType': 'total', 'line': 51, 'direction': 'under'}, {'home': {}, 'away': {}}))

    def test_prop_grades_from_the_box_score_and_absent_player_is_unclear(self):
        record = {'players': [{'id': '77', 'name': 'Player Seven', 'recYds': 61, 'rec': 5}]}
        pick = {'athleteId': '77', 'market': 'recYds', 'line': 49.5, 'direction': 'over'}
        self.assertEqual(run.grade_prop(pick, record), ('win', 'Player Seven: 61 receiving yards', 61))
        self.assertEqual(run.grade_prop(dict(pick, market='rec', line=5, direction='under'), record)[0], 'push')
        self.assertIsNone(run.grade_prop(dict(pick, athleteId='99'), record))
        self.assertIsNone(run.grade_prop(pick, None))

    def test_leg_shapes(self):
        self.assertEqual(run.leg_pick({'market': 'total points', 'side': 'over', 'line': 44.5})['marketType'], 'total')
        leg = run.leg_pick({'id': 'prop-NFL-1-77-recYds', 'market': 'receiving yards', 'side': 'over', 'line': 49.5, 'title': 'P over 49.5 receiving yards'})
        self.assertEqual(leg['athleteId'], '77')


class TextTests(unittest.TestCase):
    def test_entry_note_quotes_the_rule_and_the_numbers(self):
        now = datetime(2026, 9, 27, 20, 5, tzinfo=timezone.utc)
        pick = {'line': 31.5, 'odds': -110, 'cutoff': 'OVER 31.5 at -110 or better. Closed at 32+.'}
        note = run.entry_note(now, 'line moved 1 against, from 31.5 to 32.5', pick)
        self.assertIn('4:05 PM ET', note)
        self.assertIn('from 31.5 to 32.5', note)
        self.assertIn('31.5 and -110', note)
        self.assertIn('graded as posted', note)

    def test_report_names_are_eastern_and_say_what_happened(self):
        now = datetime(2026, 9, 28, 3, 40, tzinfo=timezone.utc)       # 11:40 PM ET Sunday
        slot = run.slot_for(now)
        settled = [('NFL', 'gamePicks', {'id': 'a', 'title': 'A', 'result': 'win', 'status': 'settled'})]
        reports = run.build_reports({'NFL': (settled, [], [])}, slot, now, [], [], [], {'NFL': 4}, False)
        self.assertEqual(list(reports), ['2026-09-27-NFL-2340-settlement.json'])
        self.assertEqual(reports['2026-09-27-NFL-2340-settlement.json']['targetWeek'], 4)
        self.assertIn('Settled 1', reports['2026-09-27-NFL-2340-settlement.json']['summary'])

    def test_a_quiet_run_writes_no_report(self):
        now = datetime(2026, 9, 29, 15, 50, tzinfo=timezone.utc)
        self.assertEqual(run.build_reports({'NFL': ([], [], [])}, run.slot_for(now), now, [], [], [], {}, False), {})

    def test_private_keys_never_reach_a_report(self):
        now = datetime(2026, 9, 27, 15, 55, tzinfo=timezone.utc)
        pick = {'id': 'p', 'title': 'T', 'book': 'DraftKings', 'odds': -110, 'status': 'active', '_desk': {'x': 1}, '_quotes': []}
        reports = run.build_reports({'NFL': ([], [], [('NFL', 'gamePicks', pick)])}, run.slot_for(now), now, [], [], [], {}, False)
        written = list(reports.values())[0]['gamePicks'][0]
        self.assertNotIn('_desk', written)
        self.assertNotIn('_quotes', written)

    def test_slugs(self):
        self.assertEqual(run.line_slug(44.5), '44-5')
        self.assertEqual(run.line_slug(41.0), '41')
        self.assertEqual(run.line_slug(-16.5), 'minus-16-5')
        self.assertEqual(run.report_slug([], [], [('NFL', 'props', {'athleteId': '1'})]), 'prop-leans')
        self.assertEqual(run.report_slug([], [], [('NFL', 'gamePicks', {})]), 'model-leans')
        self.assertEqual(run.report_slug([1], [1], []), 'run')


class HoldTests(unittest.TestCase):
    def test_holds_on_quarterback_listings(self):
        facts = [{'kind': 'injury', 'position': 'QB', 'team': '10', 'status': 'Questionable', 'claim': 'QB1 (QB, DET) is listed Questionable'}]
        self.assertIsNotNone(run.hold_reason({'marketType': 'total'}, facts))
        self.assertIsNotNone(run.hold_reason({'athleteId': '77', '_team': '10'}, facts))
        self.assertIsNone(run.hold_reason({'athleteId': '77', '_team': '20'}, facts), "the other team's quarterback does not hold a prop")
        self.assertIsNone(run.hold_reason({'marketType': 'total'}, []))
        heavy = [{'kind': 'injury', 'position': p, 'team': '20', 'status': 'Out', 'claim': ''} for p in ('WR', 'WR', 'TE')]
        self.assertIsNotNone(run.hold_reason({'marketType': 'total'}, heavy))


class GitTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.dir.name)
        env = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}
        self.env = env

        def sh(*args):
            return subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, env=env, check=True)
        sh('init', '-q', '-b', 'main')
        (self.repo / 'research').mkdir()
        (self.repo / 'data' / 'odds').mkdir(parents=True)
        (self.repo / 'site' / 'data').mkdir(parents=True)
        (self.repo / 'site' / 'data' / 'slate.json').write_text('{"a": 1}')
        (self.repo / 'data' / 'odds' / 'nfl.jsonl').write_text('{}\n')
        (self.repo / 'research' / 'old.json').write_text('{}')
        sh('add', '.')
        sh('commit', '-q', '-m', 'base')
        self.sh = sh

    def tearDown(self):
        self.dir.cleanup()

    def runner(self, *args, cwd=None, check=True):
        result = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, env=self.env)
        if check and result.returncode:
            raise run.RunError(result.stderr)
        return result

    def test_commit_whitelist_restores_everything_else(self):
        (self.repo / 'site' / 'data' / 'slate.json').write_text('{"a": 2}')                 # the hosted workflow owns this
        (self.repo / 'data' / 'odds' / 'nfl.jsonl').write_text('{}\n{}\n')                     # a capture
        (self.repo / 'research' / '2026-09-27-NFL-1219-run.json').write_text('{"league": "NFL"}')
        now = datetime(2026, 9, 27, 16, 19, tzinfo=timezone.utc)
        result = run.commit_push(now, run.slot_for(now), {'published': 1, 'settled': 0, 'closed': 0}, push=False, runner=self.runner, cwd=self.repo)
        self.assertEqual(result, {'committed': True, 'pushed': False})
        self.assertEqual((self.repo / 'site' / 'data' / 'slate.json').read_text(), '{"a": 1}', 'restored, not committed')
        log = self.sh('log', '--format=%s').stdout.splitlines()
        self.assertEqual(log[0], 'Research 2026-09-27 12:19 ET: 1 published, 0 settled, 0 closed')
        self.assertEqual(log[1], 'Odds capture 2026-09-27 12:19 ET')
        self.assertEqual(self.sh('status', '--porcelain').stdout, '')

    def test_push_rejected_by_the_other_writer_is_rebased_and_the_store_merged(self):
        """The hosted workflow and the desk both appended to the odds store; the desk's push is rejected,
        rebased, the store merged with every record kept, and pushed. Nothing is forced."""
        import boxscores
        side = tempfile.TemporaryDirectory()
        self.addCleanup(side.cleanup)
        origin = Path(side.name) / 'origin.git'
        hosted = Path(side.name) / 'hosted'
        subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True, capture_output=True)
        self.sh('remote', 'add', 'origin', str(origin))
        self.sh('push', '-q', '-u', 'origin', 'main')
        subprocess.run(['git', 'clone', '-q', str(origin), str(hosted)], check=True, capture_output=True, env=self.env)
        store = hosted / 'data' / 'odds'
        with (store / 'nfl.jsonl').open('a') as f:
            f.write('{"gameId": "g", "retrievedAt": "2026-09-27T12:38:00Z", "total": 45}\n')
        boxscores.write_json(store / 'ledger.json', boxscores.ledger(store))
        subprocess.run(['git', '-c', 'user.name=bot', '-c', 'user.email=b@b', 'commit', '-q', '-am', 'hosted capture'], cwd=hosted, check=True, capture_output=True, env=self.env)
        subprocess.run(['git', 'add', 'data/odds/ledger.json'], cwd=hosted, check=True, capture_output=True)
        subprocess.run(['git', '-c', 'user.name=bot', '-c', 'user.email=b@b', 'commit', '-q', '-m', 'hosted ledger'], cwd=hosted, check=True, capture_output=True, env=self.env)
        subprocess.run(['git', 'push', '-q'], cwd=hosted, check=True, capture_output=True, env=self.env)
        mine = self.repo / 'data' / 'odds'
        with (mine / 'nfl.jsonl').open('a') as f:
            f.write('{"gameId": "g", "retrievedAt": "2026-09-27T12:35:00Z", "total": 44.5}\n')
        boxscores.write_json(mine / 'ledger.json', boxscores.ledger(mine))
        (self.repo / 'research' / '2026-09-27-NFL-0830-run.json').write_text('{"league": "NFL"}')
        now = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)
        result = run.commit_push(now, run.slot_for(now), {'published': 1, 'settled': 0, 'closed': 0}, push=True, runner=self.runner, cwd=self.repo)
        self.assertEqual(result, {'committed': True, 'pushed': True})
        self.assertEqual(self.sh('rev-parse', 'HEAD').stdout, self.sh('rev-parse', 'origin/main').stdout, 'pushed, on top of the hosted commits')
        log = self.sh('log', '--format=%s').stdout.splitlines()
        self.assertEqual(log[:4], ['Research 2026-09-27 08:30 ET: 1 published, 0 settled, 0 closed', 'Odds capture 2026-09-27 08:30 ET', 'hosted ledger', 'hosted capture'])
        records = boxscores.read_store(mine / 'nfl.jsonl')
        self.assertEqual([r.get('total') for r in records], [None, 45, 44.5], 'both captures kept; the base line has no retrievedAt so the order is by side')
        self.assertEqual(boxscores.verify(mine), [], 'the ledger was recomputed over the merged file')
        self.assertEqual(self.sh('status', '--porcelain').stdout, '')

    def test_sync_refuses_a_dirty_tree(self):
        (self.repo / 'research' / 'old.json').write_text('{"changed": true}')
        with self.assertRaises(run.RunError):
            run.sync(runner=self.runner)


if __name__ == '__main__':
    unittest.main()
