"""Exercise the actual NBA background branches with all feed effects mocked."""
import ast
import inspect
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run
import nba_capture
import nba_player_props
import nba_trial_runtime

class SettlementScopeTests(unittest.TestCase):
    def test_recovery_grades_without_pregame_capture_or_admission(self):
        tree=ast.parse(inspect.getsource(run._run))
        background=next(n for n in tree.body[0].body if isinstance(n,ast.If) and
                        any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and
                            x.func.attr=='enqueue' for x in ast.walk(n)))
        nodes=[n for n in background.body if
               (isinstance(n,ast.If) and 'nbaCapture' in ast.unparse(n)) or
               (isinstance(n,ast.If) and 'capture_nba_props_and_select' in ast.unparse(n)) or
               (isinstance(n,ast.Try) and 'nbaTrialGraded' in ast.unparse(n))]
        self.assertEqual(len(nodes),3)
        code=compile(ast.Module(body=nodes,type_ignores=[]),'<actual NBA branches>','exec')
        now=datetime(2026,10,26,1,30,tzinfo=timezone.utc)
        for settle_only in (True,False):
            with self.subTest(settle_only=settle_only), patch.object(nba_capture,'step') as capture, \
                 patch.object(nba_player_props,'capture') as props, \
                 patch.object(nba_trial_runtime,'admission') as admit, \
                 patch.object(nba_trial_runtime,'grade') as trial_grade, \
                 patch.object(nba_player_props,'grade') as prop_grade:
                env=dict(run.__dict__,settle_only=settle_only,now=now,
                         slot=now.astimezone(run.EASTERN),status={'errors':[]},
                         args=SimpleNamespace(command='run',dry_run=False,no_push=False,now='explicit-replay'))
                exec(code,env)
                trial_grade.assert_called_once_with(now)
                prop_grade.assert_called_once_with(now)
                capture.assert_not_called() # run uses the earlier game capture
                if settle_only:
                    props.assert_not_called();admit.assert_not_called()
                else:
                    props.assert_called_once();admit.assert_called_once()

    def test_actual_results_command_retains_grading_and_climb_without_pregame_feeds(self):
        # Replay the production dispatch and effectful branches, with all external
        # effects mocked. In particular, use the real settle,ladder kinds rather
        # than the singleton recovery scope that previously hid this regression.
        from unittest.mock import MagicMock
        import live_watch
        tree = ast.parse(inspect.getsource(run._run)).body[0].body
        background = next(n for n in tree if isinstance(n, ast.If) and
                          any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                              and x.func.attr == 'enqueue' for x in ast.walk(n)))
        effects = [n for n in background.body if
                   (isinstance(n, ast.If) and 'nbaCapture' in ast.unparse(n)) or
                   (isinstance(n, ast.If) and 'capture_nba_props_and_select' in ast.unparse(n)) or
                   (isinstance(n, ast.Try) and 'nbaTrialGraded' in ast.unparse(n))]
        climb = next(n for n in tree if isinstance(n, ast.If) and ast.unparse(n.test) == "'ladder' in kinds")
        code = compile(ast.Module(body=[climb, *effects], type_ignores=[]), '<actual results branches>', 'exec')
        class ReachedBuild(Exception):
            pass
        for command, clock in [('results', '2026-10-27T04:25:00Z'),
                               ('results', '2026-10-27T21:25:00Z'),
                               ('results', '2026-10-27T21:55:00Z'),
                               ('ladder', '2026-10-27T17:30:00Z')]:
            with self.subTest(command=command, clock=clock), patch.object(run, 'run', return_value=0) as dispatch:
                self.assertEqual(run.main([command, '--now', clock]), 0)
                args = dispatch.call_args.args[0]
            now = run.gates.when(clock)
            slot = now.astimezone(run.EASTERN)
            kinds = set(args.publish_kinds.split(','))
            status = {'checks': [], 'errors': []}
            ctx = SimpleNamespace(first={}, latest={}, games={})
            stores = MagicMock(reports=[], context_file={})
            stores.as_of.return_value = ctx
            with patch.object(run, 'sync'), patch.object(run, 'log'), \
                 patch.object(run, 'capture', return_value=[]) as football, \
                 patch.object(run, 'early_nba_selection') as early, \
                 patch.object(run.arbs, 'scan', return_value=[]), \
                 patch.object(run.sgo_shadow, 'sample', return_value={'sampled': False, 'reason': 'not configured'}) as sgo, \
                 patch.object(run, 'load_json', return_value={'games': []}), \
                 patch.object(run, 'live_games', return_value={}) as finals, \
                 patch.object(run.features, 'load', return_value=[]), \
                 patch.object(run.gates, 'Stores', return_value=stores), \
                 patch.object(run, 'prime_weather'), patch.object(run, 'raw_first_publications', return_value={}), \
                 patch.object(run, 'settle', return_value=([], [])) as grade, \
                 patch.object(live_watch, 'final_records', return_value={}) as watched, \
                 patch.object(live_watch, 'overlay_finals') as overlay, \
                 patch.object(live_watch, 'settlement_records', return_value=[]), \
                 patch('release_queue.reopen_expired'), patch('release_queue.merge_context'), \
                 patch.object(run.build_site, 'build', side_effect=ReachedBuild):
                with self.assertRaises(ReachedBuild):
                    run._run(args, now, slot, kinds, status)
                finals.assert_called_once()
                grade.assert_called_once()
                if command == 'results':
                    football.assert_not_called(); early.assert_not_called(); sgo.assert_not_called()
                    watched.assert_called_once(); overlay.assert_called_once()
                else:
                    football.assert_called_once(); early.assert_called_once(); sgo.assert_called_once()
            with patch.object(nba_capture, 'step') as capture, \
                 patch.object(nba_player_props, 'capture') as props, \
                 patch.object(nba_trial_runtime, 'admission') as admit, \
                 patch.object(nba_trial_runtime, 'grade') as trial_grade, \
                 patch.object(nba_player_props, 'grade') as prop_grade, \
                 patch.object(run, 'ladder_step') as ladder, \
                 patch.object(run, 'longshot_exclusions', return_value=set()):
                env = dict(run.__dict__, settle_only=command == 'results', args=args, now=now,
                           slot=slot, kinds=kinds, status=status, ctx=ctx, games={}, records=[],
                           published=[], decided=[], screened=[], closed=[])
                exec(code, env)
                ladder.assert_called_once()
                trial_grade.assert_called_once_with(now); prop_grade.assert_called_once_with(now)
                admit.assert_not_called()
                if command == 'results':
                    capture.assert_not_called(); props.assert_not_called()
                else:
                    capture.assert_called_once(); props.assert_called_once()
