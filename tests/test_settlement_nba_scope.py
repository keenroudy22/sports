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
               (isinstance(n,ast.If) and 'nbaPlayerProps' in ast.unparse(n)) or
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
                         args=SimpleNamespace(command='run',dry_run=False))
                exec(code,env)
                trial_grade.assert_called_once_with(now)
                prop_grade.assert_called_once_with(now)
                capture.assert_not_called() # run uses the earlier game capture
                if settle_only:
                    props.assert_not_called();admit.assert_not_called()
                else:
                    props.assert_called_once();admit.assert_called_once()
