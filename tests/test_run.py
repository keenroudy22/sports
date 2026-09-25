import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(origin)], check=True, capture_output=True)
        self.sh('remote', 'add', 'origin', str(origin))
        self.sh('push', '-q', '-u', 'origin', 'main')
        subprocess.run(['git', 'clone', '-q', '-b', 'main', str(origin), str(hosted)], check=True, capture_output=True, env=self.env)
        store = hosted / 'data' / 'odds'
        with (store / 'nfl.jsonl').open('a') as f:
            f.write('{"gameId": "g", "retrievedAt": "2026-09-27T12:38:00Z", "total": 45}\n')
        boxscores.write_json(store / 'ledger.json', boxscores.ledger(store))
        subprocess.run(['git', '-c', 'user.name=bot', '-c', 'user.email=b@b', 'commit', '-q', '-am', 'hosted capture'], cwd=hosted, check=True, capture_output=True, env=self.env)
        subprocess.run(['git', 'add', 'data/odds/ledger.json'], cwd=hosted, check=True, capture_output=True, env=self.env)
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

    def test_commit_log_commits_the_posted_log_alone(self):
        (self.repo / 'data' / 'x-posted.json').write_text('{"posts": []}\n')
        self.sh('add', '.')
        self.sh('commit', '-q', '-m', 'log')
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        self.assertEqual(run.commit_log(now, push=False, runner=self.runner, cwd=self.repo), {'committed': False, 'pushed': False})
        (self.repo / 'data' / 'x-posted.json').write_text('{"posts": [{"id": "a"}]}\n')
        (self.repo / 'research' / 'old.json').write_text('{"not": "this"}')
        self.assertEqual(run.commit_log(now, push=False, runner=self.runner, cwd=self.repo), {'committed': True, 'pushed': False})
        self.assertEqual(self.sh('log', '-1', '--format=%s').stdout.strip(), 'Posts 2026-09-27 08:40 ET')
        self.assertEqual(self.sh('show', '--name-only', '--format=', 'HEAD').stdout.split(), ['data/x-posted.json'])

    def test_sync_commits_captures_a_stopped_run_left_behind(self):
        (self.repo / 'data' / 'odds' / 'nfl.jsonl').write_text('{}\n{"x": 1}\n')
        with self.assertRaises(run.RunError) as caught:        # no remote here, so the rebase step fails after the commit
            run.sync(runner=self.runner)
        self.assertNotIn('modified before the run', str(caught.exception))
        self.assertEqual(self.sh('log', '-1', '--format=%s').stdout.strip(), 'Captures left by a stopped run')
        self.assertEqual(self.sh('status', '--porcelain').stdout, '')

    def test_sync_refuses_a_dirty_tree(self):
        (self.repo / 'research' / 'old.json').write_text('{"changed": true}')
        with self.assertRaises(run.RunError):
            run.sync(runner=self.runner)


class JudgeTests(unittest.TestCase):
    """The desk's judge only weighs what can matter, and a hold must name a fact."""

    def ctx(self):
        from types import SimpleNamespace
        return SimpleNamespace(starters={'NFL-10': '5', 'NFL-20': '6'})

    def test_only_facts_that_can_matter_reach_the_judge(self):
        ctx = self.ctx()
        facts = [{'id': 'market-g', 'kind': 'market', 'direction': 'neutral', 'claim': 'moved'},
                 {'id': 'weather-g', 'kind': 'weather', 'direction': 'neutral', 'claim': 'calm'},
                 {'id': 'weather-w', 'kind': 'weather', 'direction': 'against', 'claim': 'wind 22 mph'},
                 {'id': 'injury-10-5', 'kind': 'injury', 'team': '10', 'position': 'QB', 'status': 'Questionable', 'claim': 'QB1 questionable'},
                 {'id': 'injury-10-8', 'kind': 'injury', 'team': '10', 'position': 'QB', 'status': 'Questionable', 'claim': 'QB2 questionable'},
                 {'id': 'injury-20-9', 'kind': 'injury', 'team': '20', 'position': 'WR', 'status': 'Injured Reserve', 'claim': 'WR on IR'},
                 {'id': 'injury-20-77', 'kind': 'injury', 'team': '20', 'position': 'WR', 'status': 'Out', 'claim': 'the prop player out'},
                 {'id': 'web-g-0', 'kind': 'role', 'origin': 'claude researcher', 'direction': 'against', 'claim': 'benched'}]
        total = {'marketType': 'total', 'direction': 'over', '_league': 'NFL'}
        ids = [f['id'] for f in run.relevant_facts(total, facts, ctx)]
        self.assertEqual(ids, ['weather-w', 'injury-10-5', 'web-g-0'], 'the move, calm weather, a backup and IR stay out')
        prop = {'athleteId': '77', '_team': '20', 'market': 'rec', 'direction': 'over', '_league': 'NFL'}
        ids = [f['id'] for f in run.relevant_facts(prop, facts, ctx)]
        self.assertEqual(ids, ['injury-20-77', 'web-g-0'], "a prop weighs its own player and his quarterback, not the other side's")
        three = [{'id': f'injury-20-{i}', 'kind': 'injury', 'team': '20', 'position': 'WR', 'status': 'Out', 'claim': 'x'} for i in range(3)]
        self.assertEqual(len(run.relevant_facts(total, three, ctx)), 3, 'a side missing three skill players matters to a total')
        self.assertEqual(run.relevant_facts(total, three[:2], ctx), [])

    def test_no_relevant_fact_no_hold_and_a_hold_names_a_fact(self):
        from unittest import mock
        self.assertIsNone(run.judge({'title': 't'}, [], True))
        facts = [{'id': 'injury-10-5', 'kind': 'injury', 'position': 'QB', 'claim': 'QB1 out'}]
        with mock.patch.object(run.llm_tasks, 'judge_against', return_value={'argues_against': False, 'confidence': 'low', 'fact_ids': [], 'note': 'n'}):
            self.assertIsNone(run.judge({'title': 't'}, facts, True), 'unsure without a fact is not a hold')
        with mock.patch.object(run.llm_tasks, 'judge_against', return_value={'argues_against': True, 'confidence': 'medium', 'fact_ids': ['injury-10-5'], 'note': 'QB out'}):
            self.assertIn('QB out', run.judge({'title': 't'}, facts, True))
        with mock.patch.object(run.llm_tasks, 'judge_against', return_value={'argues_against': True, 'confidence': 'high', 'fact_ids': [], 'note': 'vibes'}):
            self.assertIsNone(run.judge({'title': 't'}, facts, True), 'against without naming a fact does not count')
        web = [{'id': 'web-1', 'origin': 'claude researcher', 'direction': 'against', 'kind': 'injury', 'claim': 'the starter is suspended'}]
        self.assertIn('suspended', run.judge({'title': 't'}, web, False), 'with the model down, verified reporting against it holds')

    def test_the_reasoning_names_what_the_web_check_verified(self):
        facts = [{'kind': 'injury', 'direction': 'neutral', 'verified': True, 'claim': 'Both starting quarterbacks are expected to play.', 'source': 'https://example.com/a'},
                 {'kind': 'stats', 'direction': 'for', 'verified': True, 'claim': 'Iowa averages 30 points.', 'source': 'https://example.com/b'},
                 {'kind': 'role', 'direction': 'against', 'verified': True, 'claim': 'The starter is suspended.', 'source': 'https://example.com/c'},
                 {'kind': 'injury', 'direction': 'neutral', 'verified': False, 'claim': 'Rumour.', 'source': 'https://example.com/d'}]
        self.assertEqual([f['source'] for f in run.checked_facts({'_research': facts})], ['https://example.com/a'],
                         'only verified availability facts that do not argue against the pick')

    def test_a_game_line_post_reason_is_a_fact_that_backs_the_play_or_nothing(self):
        from types import SimpleNamespace
        total = {'marketType': 'total', 'direction': 'under', 'line': 43.5, 'gameIds': ['g']}
        facts = [{'origin': 'claude researcher', 'verified': True, 'kind': 'injury', 'direction': 'for',
                  'claim': 'Saints receiver Chris Olave is out with a hamstring injury. He had 9 catches last week.'},
                 {'origin': 'claude researcher', 'verified': True, 'kind': 'stats', 'direction': 'for', 'claim': 'The Saints average 30 points.'},
                 {'origin': 'claude researcher', 'verified': True, 'kind': 'injury', 'direction': 'against',
                  'claim': 'Saints quarterback Tyler Shough leads the league with 662 passing yards.'},
                 {'kind': 'market', 'direction': 'neutral', 'claim': 'The total opened 42.5.'}]
        ctx = SimpleNamespace(games={})
        self.assertEqual(run.post_reason(total, facts, ctx, []), 'Saints receiver Chris Olave is out with a hamstring injury.')
        self.assertIsNone(run.post_reason(total, facts[1:], ctx, []), 'a stats story or a fact against the play is never its reason')
        wind = [{'kind': 'weather', 'direction': 'for', 'claim': 'Forecast at kickoff: wind 18 mph.'}]
        self.assertEqual(run.post_reason(total, wind, ctx, []), 'Forecast at kickoff: wind 18 mph.')
        self.assertIsNone(run.post_reason(dict(total, legs=[{}]), wind, ctx, []))

    def test_every_college_play_needs_the_web_check(self):
        self.assertTrue(run.needs_research({'_league': 'CFB', 'projection': 47.1, 'line': 38.5}))
        self.assertTrue(run.needs_research({'_league': 'CFB', 'projection': 40.0, 'line': 38.5}), 'no college injury feed at any gap')
        self.assertFalse(run.needs_research({'_league': 'NFL', 'projection': 47.1, 'line': 38.5}), 'the NFL has its injury report')
        self.assertFalse(run.needs_research({'_league': 'CFB', 'legs': [{}]}), 'the fun parlay is built from the board')
        self.assertEqual(run.first_sentence("Camden Coleman has started while Evans is out. He completed 19 of 27."),
                         'Camden Coleman has started while Evans is out.')


class PrecheckTests(unittest.TestCase):
    def test_a_lineup_is_confirmed_only_by_an_availability_fact(self):
        self.assertTrue(run.lineup_confirmed([{'kind': 'injury'}]))
        self.assertTrue(run.lineup_confirmed([{'kind': 'stats'}, {'kind': 'role'}]))
        self.assertFalse(run.lineup_confirmed([{'kind': 'stats'}]))
        self.assertFalse(run.lineup_confirmed([]))

    def test_the_window(self):
        now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
        post = lambda key, minutes, **over: dict({'id': key, 'kind': 'buffer:play', 'bufferPostId': 'b', 'dueAt': run.stamp(now + timedelta(minutes=minutes))}, **over)
        log_book = {'posts': [post('soon', 10), post('in', 60), post('edge', 150), post('far', 200), post('sent', 60, sentAt='x'),
                              post('gone', 60, cancelledAt='x'), post('done', 60, precheck={'result': 'clear'}),
                              dict(post('receipt', 60), kind='buffer:receipt')]}
        self.assertEqual([e['id'] for e in run.precheck_due(log_book, now)], ['in', 'edge'])

    def test_quiet_when_nothing_is_due(self):
        from types import SimpleNamespace
        from unittest import mock
        import x_post
        with mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(run, 'Lock') as lock:
            self.assertEqual(run.precheck(SimpleNamespace(now=None, dry_run=True, no_llm=True, no_push=True)), 0)
        lock.assert_not_called()

    def test_a_rehearsal_leaves_the_post_log_alone(self):
        from types import SimpleNamespace
        from unittest import mock
        import x_post
        now = datetime(2026, 9, 25, 18, 30, tzinfo=timezone.utc)
        entry = {'id': 'CFB-2026-W4-x', 'kind': 'buffer:play', 'bufferPostId': 'b', 'dueAt': run.stamp(now + timedelta(minutes=90))}
        ctx = SimpleNamespace(first={}, latest={}, player_team={}, names={}, games={})
        stores = mock.MagicMock(reports=[], context_file={})
        stores.as_of.return_value = ctx
        with mock.patch.object(x_post, 'load_log', side_effect=lambda: {'posts': [dict(entry)]}), \
                mock.patch.object(x_post, 'save_log') as save_log, mock.patch.object(run, 'Lock'), \
                mock.patch.object(run, 'sync', side_effect=AssertionError('no sync in a rehearsal')), \
                mock.patch.object(run, 'live_games', return_value={}), mock.patch.object(run.features, 'load', return_value=[]), \
                mock.patch.object(run.gates, 'Stores', return_value=stores), mock.patch.object(run, 'raw_first_publications', return_value={}), \
                mock.patch.object(run, 'live_context', return_value={}), mock.patch.object(run.llm, 'available', return_value=False), \
                mock.patch.object(run, 'close_moves', return_value=([], None)), mock.patch.object(run.desk, 'captures', return_value=[]):
            self.assertEqual(run.precheck(SimpleNamespace(now=run.stamp(now), dry_run=True, no_llm=True, no_push=True)), 0)
        save_log.assert_not_called()

    def test_a_requote_creates_the_new_post_before_the_old_one_goes(self):
        import buffer_post
        from types import SimpleNamespace
        from unittest import mock
        now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
        pick = {'id': 'CFB-2026-W4-x', 'title': 'Iowa at Michigan over 38.5', 'marketType': 'total', 'line': 38.5, 'odds': -105,
                'book': 'ESPN BET', 'direction': 'over', 'gameIds': ['g'], 'projection': 47.1}
        ctx = SimpleNamespace()

        def attempt(fail_delete=()):
            entry = {'id': 'CFB-2026-W4-x', 'bufferPostId': 'old', 'dueAt': '2026-09-26T16:30:00Z', 'card': True, 'textHash': 'stale'}
            calls = []

            def delete(post_id, **k):
                calls.append(('delete', post_id))
                if post_id in fail_delete:
                    raise buffer_post.BufferError('refused')
            with mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                    mock.patch.object(buffer_post, 'create_post', side_effect=lambda *a, **k: calls.append(('create', a[3])) or 'new'), \
                    mock.patch.object(buffer_post, 'delete_post', side_effect=delete), \
                    mock.patch.object(run.gates, 'best_now', return_value=('FanDuel', 39.5, -110)), \
                    mock.patch.object(run, 'alert') as alerted:
                try:
                    run.requote(entry, pick, {'id': 'g', 'league': 'CFB'}, ctx, now, log=lambda *_: None)
                except buffer_post.BufferError:
                    pass
            return entry, calls, alerted
        entry, calls, _ = attempt()
        self.assertEqual(calls, [('create', 'https://keenroudy.com/sports/data/cards/CFB-2026-W4-x.png'), ('delete', 'old')])
        self.assertEqual(entry['bufferPostId'], 'new')
        entry, calls, alerted = attempt(fail_delete={'old'})
        self.assertEqual(calls[-1], ('delete', 'new'), 'the old one could not go, so the new one is taken back')
        self.assertEqual(entry['bufferPostId'], 'old')
        alerted.assert_not_called()
        entry, calls, alerted = attempt(fail_delete={'old', 'new'})
        alerted.assert_called_once()

    def test_a_requote_keeps_the_pick_of_the_day_label_and_card(self):
        import buffer_post
        from types import SimpleNamespace
        from unittest import mock
        now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
        pick = {'id': 'CFB-2026-W4-x', 'title': 'Iowa at Michigan over 38.5', 'marketType': 'total', 'line': 38.5, 'odds': -105,
                'book': 'ESPN BET', 'direction': 'over', 'gameIds': ['g'], 'projection': 47.1}
        entry = {'id': 'CFB-2026-W4-x', 'bufferPostId': 'old', 'dueAt': '2026-09-26T16:00:00Z', 'card': True, 'textHash': 'stale',
                 'cardKey': 'CFB-2026-W4-x-potd', 'featured': True}
        created = []
        with mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'create_post', side_effect=lambda *a, **k: created.append(a) or 'new'), \
                mock.patch.object(buffer_post, 'delete_post'), \
                mock.patch.object(run.gates, 'best_now', return_value=('FanDuel', 39.5, -110)):
            run.requote(entry, pick, {'id': 'g', 'league': 'CFB'}, SimpleNamespace(), now, log=lambda *_: None)
        text, _, _, card = created[0]
        self.assertTrue(text.startswith('🍳 PICK OF THE DAY · TEAM PROP'))
        self.assertIn('Now: 39.5 at -110, FanDuel', text)
        self.assertEqual(card, 'https://keenroudy.com/sports/data/cards/CFB-2026-W4-x-potd.png')


class AlertTests(unittest.TestCase):
    def test_alerts_push_once_per_six_hours_and_never_without_a_topic(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
            with mock.patch.object(run, 'CONF', Path(folder)), mock.patch.dict(os.environ, {'KEENROUDY_NTFY_TOPIC': 'secret-topic'}):
                self.assertTrue(run.alert('Run stopped', 'git fetch failed', now=now, send=sent.append))
                self.assertFalse(run.alert('Run stopped', 'git fetch failed', now=now + timedelta(hours=1), send=sent.append), 'quiet for six hours')
                self.assertTrue(run.alert('Run stopped', 'git fetch failed', now=now + timedelta(hours=7), send=sent.append))
                self.assertTrue(run.alert('Run stopped', 'something else', now=now, send=sent.append))
            self.assertEqual(len(sent), 3)
            self.assertEqual(sent[0].full_url, 'https://ntfy.sh/secret-topic')
            self.assertIn(b'git fetch failed', sent[0].data)
            with mock.patch.object(run, 'CONF', Path(folder)), mock.patch.dict(os.environ, {'KEENROUDY_NTFY_TOPIC': ''}):
                self.assertFalse(run.alert('x', 'y', now=now, send=lambda r: self.fail('no topic, no push')))


    def test_the_heartbeat_reaches_the_phone_when_something_is_wrong(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            conf = Path(folder) / '.config' / 'keenroudy'
            conf.mkdir(parents=True)
            sent = []
            answer = subprocess.CompletedProcess([], 0, stdout='Logged in to github.com account keenroudy22', stderr='')
            with mock.patch.object(run, 'CONF', conf), \
                    mock.patch.object(run, 'git', lambda *a, **k: subprocess.CompletedProcess([], 0, stdout='', stderr='')), \
                    mock.patch.object(run.subprocess, 'run', lambda *a, **k: answer), \
                    mock.patch('urllib.request.urlopen', side_effect=OSError('refused')), \
                    mock.patch.object(run, 'alert', lambda title, message, **k: sent.append((title, message))):
                self.assertEqual(run.heartbeat(None), 1)
            self.assertEqual(sent[0][0], 'KeenRoudy desk needs a look')
            self.assertIn('no run has written status.json yet', sent[0][1])
            self.assertIn('Ollama is not reachable', sent[0][1])
            self.assertTrue((Path(folder) / 'Library' / 'Logs' / 'KeenRoudy' / 'ALERT.txt').exists())

    def test_a_rehearsal_never_overwrites_the_live_status(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(run, 'CONF', Path(folder)):
                run.write_status({'outcome': 'failed: sync', 'dryRun': False})
                run.write_status({'outcome': 'ok', 'dryRun': True})
            self.assertEqual(json.loads((Path(folder) / 'status.json').read_text())['outcome'], 'failed: sync')
            self.assertEqual(json.loads((Path(folder) / 'pending' / 'status.json').read_text())['outcome'], 'ok')


class FetchTests(unittest.TestCase):
    def test_a_fetch_that_races_another_git_client_is_tried_again_and_other_failures_stop_the_run(self):
        from types import SimpleNamespace
        answers = [SimpleNamespace(returncode=1, stdout='', stderr="error: cannot lock ref 'refs/remotes/origin/main': is at b544 but expected 5bfa"),
                   SimpleNamespace(returncode=0, stdout='', stderr='')]
        calls, slept = [], []
        run.fetch(lambda *a, cwd=None, check=True: calls.append(a) or answers.pop(0), sleep=slept.append)
        self.assertEqual(len(calls), 2)
        self.assertEqual(slept, [3])
        broken = lambda *a, cwd=None, check=True: SimpleNamespace(returncode=128, stdout='', stderr='fatal: could not read from remote')
        with self.assertRaises(run.RunError):
            run.fetch(broken, sleep=lambda s: self.fail('a real failure is not retried'))
        always = lambda *a, cwd=None, check=True: SimpleNamespace(returncode=1, stdout='', stderr='cannot lock ref x')
        with self.assertRaises(run.RunError):
            run.fetch(always, attempts=3, sleep=lambda s: None)


class BufferPostsTests(unittest.TestCase):
    """After a push the run waits for the new cards to go live, then plans again and schedules."""

    def test_waits_for_the_deployed_cards_then_schedules(self):
        import buffer_post
        import x_post
        from unittest import mock
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        ctx = type('Ctx', (), {'first': {}, 'latest': {}, 'player_team': {}})()
        plans = [('a', 'play', 'text', now, 'a')]
        answers = iter([False, False, True])
        slept, calls = [], []
        status = {'errors': [], 'x': {}}
        with mock.patch.dict(os.environ, {'BUFFER_TOKEN': 't'}), \
                mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(x_post, 'save_log'), \
                mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'reconcile', return_value=[]), \
                mock.patch.object(buffer_post, 'plan', side_effect=lambda *a, **k: calls.append(a[3]) or plans), \
                mock.patch.object(buffer_post, 'daily_limit', return_value={'remaining': 50}), \
                mock.patch.object(buffer_post, 'reachable', side_effect=lambda url: next(answers)), \
                mock.patch.object(buffer_post, 'schedule') as schedule:
            run.buffer_posts(now, ctx, {}, [], status, deploying=True, sleep=slept.append, clock=lambda: 0)
        self.assertEqual(len(slept), 2, 'polled until the card answered')
        self.assertEqual(len(calls), 2, 'planned again after the wait, so due times are not in the past')
        schedule.assert_called_once()
        self.assertEqual(schedule.call_args[0][0], plans)
        self.assertEqual(status['errors'], [])

    def test_a_house_card_is_checked_at_its_own_address_and_a_held_post_is_reported(self):
        import buffer_post
        import x_post
        from unittest import mock
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        ctx = type('Ctx', (), {'first': {}, 'latest': {}, 'player_team': {}})()
        menu = 'https://keenroudy.com/sports/img/kitchen-menu.png'
        plans = [('menu:day:2026-09-27', 'menu', 'text', now, menu)]

        def plan(*a, refused=None, **k):
            if refused is not None:
                refused.append(('receipt:day:2026-09-26', ['a sentence runs 241 characters']))
            return plans
        urls, alerts = [], []
        with mock.patch.dict(os.environ, {'BUFFER_TOKEN': 't'}), \
                mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(x_post, 'save_log'), \
                mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'reconcile', return_value=[]), \
                mock.patch.object(buffer_post, 'plan', side_effect=plan), \
                mock.patch.object(buffer_post, 'daily_limit', return_value=None), \
                mock.patch.object(buffer_post, 'reachable', side_effect=lambda url: urls.append(url) or True), \
                mock.patch.object(run, 'alert', side_effect=lambda title, message, **k: alerts.append(message)), \
                mock.patch.object(buffer_post, 'schedule'):
            run.buffer_posts(now, ctx, {}, [], {'errors': [], 'x': {}}, deploying=True, sleep=lambda s: self.fail('no wait for a live house card'), clock=lambda: 0)
        self.assertEqual(urls, [menu])
        self.assertEqual(alerts, ['receipt:day:2026-09-26: a sentence runs 241 characters'])

    def test_no_wait_without_a_deploy(self):
        import buffer_post
        import x_post
        from unittest import mock
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        ctx = type('Ctx', (), {'first': {}, 'latest': {}, 'player_team': {}})()
        with mock.patch.dict(os.environ, {'BUFFER_TOKEN': 't'}), \
                mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(x_post, 'save_log'), \
                mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'reconcile', return_value=[]), \
                mock.patch.object(buffer_post, 'plan', return_value=[('a', 'play', 't', now, 'a')]), \
                mock.patch.object(buffer_post, 'daily_limit', return_value=None), \
                mock.patch.object(buffer_post, 'reachable') as reachable, \
                mock.patch.object(buffer_post, 'schedule') as schedule:
            run.buffer_posts(now, ctx, {}, [], {'errors': [], 'x': {}}, deploying=False, sleep=lambda s: self.fail('slept'))
        reachable.assert_not_called()
        schedule.assert_called_once()


if __name__ == '__main__':
    unittest.main()
