"""A quota-blocked X result must not wake an idle Git writer every five minutes."""
import copy
import os
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run,discord_post,nba_trial_runtime,chef_wins,x_post
NOW=datetime(2026,10,30,16,tzinfo=timezone.utc)


class IdleMirrorTests(unittest.TestCase):
 def test_sent_and_cancelled_discord_rows_do_not_count_as_work(self):
  book={'posts':[{'id':'sent','discord':{'state':'sent'}},
                 {'id':'old','cancelledAt':'2026-10-01T00:00:00Z','discord':{'state':'pending','readyAt':'2026-10-01T00:00:00Z'}}]}
  with patch.object(run.gates,'Stores') as stores,patch.object(run,'load_json',return_value={'games':[]}),patch.object(discord_post,'queue_results'):
   stores.return_value.as_of.return_value=SimpleNamespace(first={},latest={})
   self.assertFalse(run.stored_discord_work_due(NOW,book))

 def test_a_new_stored_grade_wakes_recovery_without_mutating_the_caller(self):
  book={'posts':[{'id':'grade','discord':{'state':'sent'}}]};original=copy.deepcopy(book)
  def grade(candidate,*args):candidate['posts'][0]['discord']['result']={'state':'pending'}
  with patch.object(run.gates,'Stores') as stores,patch.object(run,'load_json',return_value={'games':[]}),patch.object(discord_post,'queue_results',side_effect=grade):
   stores.return_value.as_of.return_value=SimpleNamespace(first={},latest={})
   self.assertTrue(run.stored_discord_work_due(NOW,book))
  self.assertEqual(book,original)

 def test_unknown_stored_evidence_does_not_silently_suppress_recovery(self):
  with patch.object(run.gates,'Stores',side_effect=OSError('stored read unavailable')):
   self.assertTrue(run.stored_discord_work_due(NOW,{'posts':[]}))

 def test_blocked_x_with_no_discord_work_returns_before_lock_sync_or_rebuild(self):
  args=SimpleNamespace(now=NOW.isoformat(),dry_run=False,no_push=True)
  with patch.dict(os.environ,{'KEENROUDY_LIVE_SHADOW':'0','BUFFER_TOKEN':'fixture'}), \
       patch.object(run,'result_recovery_needed',return_value=0),patch.object(run,'result_transport_block',return_value='local cap'), \
       patch.object(chef_wins,'pending',return_value=[]),patch.object(discord_post,'webhook',return_value='https://discord.invalid'), \
       patch.object(x_post,'load_log',return_value={'posts':[]}),patch.object(nba_trial_runtime,'discord_delivery_due',return_value=False), \
       patch.object(run,'private_release_ready',return_value=False),patch.object(run,'stored_discord_work_due',return_value=False), \
       patch.object(run,'Lock') as lock,patch.object(run,'sync') as sync,patch.object(run,'run') as rebuild,patch.object(run,'log'):
   self.assertEqual(run.mirror(args),0)
  lock.assert_not_called();sync.assert_not_called();rebuild.assert_not_called()

 def test_real_discord_result_still_recovers_while_x_is_blocked(self):
  args=SimpleNamespace(now=NOW.isoformat(),dry_run=False,no_push=True)
  book={'posts':[{'id':'grade','discord':{'state':'sent'}}]}
  def queue(candidate,*args):candidate['posts'][0]['discord']['result']={'state':'pending'};return 1
  def deliver(candidate,*args,**kwargs):candidate['posts'][0]['discord']['result']['state']='sent';return []
  with patch.dict(os.environ,{'KEENROUDY_LIVE_SHADOW':'0','BUFFER_TOKEN':'fixture'}), \
       patch.object(run,'result_recovery_needed',return_value=1),patch.object(run,'result_transport_block',return_value='local cap'), \
       patch.object(chef_wins,'pending',return_value=[]),patch.object(discord_post,'webhook',return_value='https://discord.invalid'), \
       patch.object(x_post,'load_log',return_value=book),patch.object(x_post,'save_log'), \
       patch.object(nba_trial_runtime,'discord_delivery_due',return_value=False), \
       patch.object(run,'private_release_ready',return_value=False),patch.object(run,'stored_discord_work_due',return_value=True), \
       patch.object(run,'Lock'),patch.object(run,'sync') as sync,patch.object(run,'run') as rebuild,patch.object(run,'commit_log'), \
       patch.object(run.gates,'Stores'),patch.object(run,'load_json',return_value={'games':[]}), \
       patch.object(discord_post,'queue_results',side_effect=queue),patch.object(discord_post,'mirror_sent',side_effect=deliver), \
       patch('buffer_post.reconcile') as api,patch.object(run,'log'):
   self.assertEqual(run.mirror(args),0)
  self.assertEqual(book['posts'][0]['discord']['result']['state'],'sent')
  sync.assert_called_once();api.assert_not_called();rebuild.assert_not_called()

 def test_missing_slate_does_not_hide_a_stored_result(self):
  with patch.object(run.gates,'Stores'),patch.object(run,'load_json',return_value=None):
   self.assertTrue(run.stored_discord_work_due(NOW,{'posts':[]}))
