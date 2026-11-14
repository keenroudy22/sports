"""Stored results retry delivery without capturing, grading or rendering."""
import sys
import unittest
import tempfile
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run

class StoredRetryTests(unittest.TestCase):
    def exercise(self, hold=None, reachable=True, nba=(), remaining=2):
        now=datetime(2026,10,31,4,50,tzinfo=timezone.utc)
        result=('cashed:one','cashed','saved terms',now,'result-one')
        ctx=SimpleNamespace(first={'one':{'odds':-110}},latest={'one':{'result':'win'}},player_team={})
        with ExitStack() as s:
            mocks={}
            for name,value in [('run.result_transport_block',hold),('gates.Stores',SimpleNamespace(as_of=lambda _:ctx)),
                ('run.load_json',{'games':[]}),('buffer_post.plan',[result,('research:x','research','x',now,'x')]),
                ('buffer_post.reachable',reachable),('buffer_post.x_channel',{'id':'channel'}),
                ('cbb_picks.plans',[]),('nba_results.plans',list(nba)),
                ('buffer_post.daily_limit',{'remaining':remaining}),('buffer_post.schedule',None),
                ('run.mark_result_recovery',None),('run.run',None)]:
                mocks[name]=s.enter_context(patch(name,return_value=value))
            run.retry_stored_results(now,{'posts':[]})
        return mocks,result
    def test_held_transport_spends_no_discovery(self):
        mocks,_=self.exercise(hold='cap')
        for name in ('buffer_post.plan','buffer_post.x_channel','buffer_post.schedule','run.run'):
            mocks[name].assert_not_called()
    def test_missing_art_spends_no_discovery_or_cooldown(self):
        mocks,_=self.exercise(reachable=False)
        for name in ('buffer_post.x_channel','buffer_post.schedule','run.mark_result_recovery','run.run'):
            mocks[name].assert_not_called()
    def test_only_result_reaches_existing_scheduler(self):
        mocks,result=self.exercise()
        self.assertEqual(mocks['buffer_post.schedule'].call_args.args[0],[result])
        self.assertEqual(mocks['buffer_post.schedule'].call_args.kwargs['items']['one']['result'],'win')
        mocks['run.run'].assert_not_called()

    def test_nba_final_uses_existing_scheduler_and_respects_transport_limit(self):
        now=datetime(2026,10,31,4,50,tzinfo=timezone.utc)
        final=('receipt:nba:NBA-one:0123456789','receipt','nba final',now,'nba-one')
        mocks,football=self.exercise(nba=[final])
        self.assertEqual(mocks['nba_results.plans'].call_args.kwargs['reserved'],[football])
        self.assertEqual(mocks['buffer_post.schedule'].call_args.args[0],[football,final])
        mocks['run.run'].assert_not_called()
        blocked,_=self.exercise(hold='cap',nba=[final])
        blocked['nba_results.plans'].assert_not_called()
        blocked['buffer_post.schedule'].assert_not_called()
        one,_=self.exercise(nba=[final],remaining=1)
        self.assertEqual(len(one['buffer_post.schedule'].call_args.args[0]),1)

    def test_missing_nba_final_wakes_recovery_without_a_football_record(self):
        now=datetime(2026,10,31,4,50,tzinfo=timezone.utc)
        final=('receipt:nba:NBA-one:0123456789','receipt','nba final',now,'nba-one')
        with tempfile.TemporaryDirectory() as folder, patch('x_post.load_log',return_value={'posts':[]}), \
                patch('cbb_picks.plans',return_value=[]), patch('nba_results.plans',return_value=[final]) as plans:
            root=Path(folder)
            self.assertEqual(run.result_recovery_needed(now,root,root/'private'),1)
            self.assertEqual(plans.call_args.args[2],root/'data/nba-trial')
            run.mark_result_recovery(now,1,root/'private')
            self.assertEqual(run.result_recovery_needed(now,root,root/'private'),0)
