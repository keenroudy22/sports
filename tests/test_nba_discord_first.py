"""Qualified NBA Discord delivery survives a held X API without duplicate receipts."""
import copy
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_trial_runtime as rt
import nba_capture
import buffer_post as b
import discord_post as d
import x_post

NOW=datetime(2026,10,30,17,0,tzinfo=timezone.utc)
GUID='NBA-trial-2026-10-30-123-total'
TEXT='🏀 NBA Picks\nAway at Home\nUNDER 220.5 (-110, DraftKings)\n\nBoth teams have been scoring below this total.\n#NBA'
PLAY={'id':GUID,'kickoff':'2026-10-30T23:00:00Z','publishedAt':'2026-10-30T16:50:00Z',
      'marketType':'total','direction':'under','line':220.5,'odds':-110,'book':'DraftKings',
      'reasons':['Both teams have been scoring below this total.'],
      'game':{'teams':{'away':{'id':'1','abbreviation':'A','name':'Away'},'home':{'id':'2','abbreviation':'H','name':'Home'}}}}
PLAN=(GUID,'nba-trial',TEXT,NOW+timedelta(minutes=15),GUID.lower())
IMAGE='https://keenroudy.com/sports/data/cards/'+GUID.lower()+'.png'


class NBADiscordFirstTests(unittest.TestCase):
 def guards(self):
  from contextlib import ExitStack
  stack=ExitStack()
  stack.enter_context(patch.object(rt,'public_rows',return_value=[copy.deepcopy(PLAY)]))
  stack.enter_context(patch.object(rt,'current_match',return_value=True))
  stack.enter_context(patch.object(b,'live_card_url',return_value=IMAGE))
  stack.enter_context(patch.object(b,'ticket_art_live',return_value=True))
  stack.enter_context(patch.object(b,'plain_art_live',return_value=True))
  return stack

 def test_delivers_once_without_buffer_calls_and_keeps_x_pending(self):
  book={'posts':[]}
  with self.guards(),patch.object(b,'graphql',side_effect=AssertionError('no Buffer API')),patch.object(d,'send_message') as send:
   self.assertEqual(rt.queue_discord_first(NOW,book,[PLAN]),1)
   self.assertNotIn('bufferPostId',book['posts'][0])
   d.mirror_sent(book,NOW,url='https://discord.invalid/plays',wins_url='',research_url='',log=lambda *_:None)
   self.assertEqual(book['posts'][0]['discord']['state'],'sent')
   self.assertNotIn('@Playbook',send.call_args.args[1])
   self.assertNotIn('sentAt',book['posts'][0])
   self.assertEqual(rt.queue_discord_first(NOW,book,[PLAN]),0)
   d.mirror_sent(book,NOW,url='https://discord.invalid/plays',wins_url='',research_url='',log=lambda *_:None)
   send.assert_called_once()

 def test_unknown_current_evidence_or_missing_live_art_cannot_release(self):
  for model_ok,art_ok in ((False,True),(True,False)):
   book={'posts':[]}
   with self.guards(),patch.object(rt,'current_match',return_value=model_ok),patch.object(b,'live_card_url',return_value=IMAGE if art_ok else None):
    self.assertEqual(rt.queue_discord_first(NOW,book,[PLAN]),0)
   self.assertEqual(book['posts'],[])

 def test_discord_only_row_does_not_hide_later_x_plan_or_refresh_prices(self):
  book={'posts':[]}
  with self.guards(),patch.object(rt,'review_ready',return_value=True),patch.object(nba_capture,'step') as capture:
   rt.queue_discord_first(NOW,book,[PLAN])
   plans=rt.social_plans(NOW,book,refresh=False)
   self.assertEqual(len(plans),1)
   self.assertEqual(plans[0][0],GUID)
   capture.assert_not_called()
   book['posts'][0]['bufferPostId']='confirmed-buffer'
   self.assertEqual(rt.social_plans(NOW,book,refresh=False),[])

 def test_later_buffer_success_upgrades_same_row_preserving_discord_receipt(self):
  book={'posts':[]}
  with self.guards():rt.queue_discord_first(NOW,book,[PLAN])
  original=copy.deepcopy(book['posts'][0])
  book['posts'][0]['discord'].update(state='sent',sentAt='2026-10-30T17:00:00Z')
  saved=copy.deepcopy(book['posts'][0]['discord'])
  with self.guards(),patch.object(rt,'reserve_delivery',return_value=True),patch.object(b,'create_post',return_value='buffer-confirmed'):
   b.schedule([PLAN],'channel',book,NOW,log=lambda *_:None)
  self.assertEqual(len(book['posts']),1)
  self.assertEqual(book['posts'][0]['bufferPostId'],'buffer-confirmed')
  self.assertEqual(book['posts'][0]['discord'],saved)
  self.assertFalse(book['posts'][0]['nbaDiscordOnly'])
  self.assertEqual(book['posts'][0]['queuedText'],original['queuedText'])
  self.assertEqual(book['posts'][0]['textHash'],x_post.text_hash(original['queuedText']))

 def test_no_new_discord_first_behavior_for_historical_trial(self):
  old=datetime(2026,10,20,17,tzinfo=timezone.utc)
  with self.guards():self.assertEqual(rt.queue_discord_first(old,{'posts':[]},[PLAN]),0)

 def test_card_deployment_retry_uses_existing_mirror_without_a_quote_capture(self):
  book={'posts':[]}
  with self.guards(),patch.object(rt,'review_ready',return_value=True),patch.object(nba_capture,'step') as capture:
   self.assertTrue(rt.discord_delivery_due(NOW,book))
   with patch.object(b,'live_card_url',return_value=None):
    self.assertEqual(rt.queue_discord_first(NOW,book,rt.social_plans(NOW,book,refresh=False)),0)
   self.assertTrue(rt.discord_delivery_due(NOW,book))
   self.assertEqual(rt.queue_discord_first(NOW,book,rt.social_plans(NOW,book,refresh=False)),1)
   self.assertFalse(rt.discord_delivery_due(NOW,book))
   capture.assert_not_called()

 def test_discord_only_play_keeps_result_grading_without_an_x_receipt(self):
  book={'posts':[]}
  with self.guards():rt.queue_discord_first(NOW,book,[PLAN])
  book['posts'][0]['discord'].update(state='sent',sentAt='2026-10-30T17:00:00Z')
  final=dict(PLAY,result='loss',actual=230,settledAt='2026-10-31T02:00:00Z',riskUnits=1)
  self.assertEqual(rt.queue_discord_results(book,NOW+timedelta(hours=10),plays=[final]),1)
  self.assertEqual(book['posts'][0]['discord']['result']['state'],'pending')
  self.assertIn('-1.00u',book['posts'][0]['discord']['result']['text'])
  self.assertNotIn('bufferPostId',book['posts'][0])

 def test_buffer_discovery_failure_cannot_skip_or_erase_discord_delivery(self):
  import os
  from types import SimpleNamespace
  import run
  book={'posts':[]};status={'x':{},'errors':[]}
  with self.guards(),patch.dict(os.environ,{'BUFFER_TOKEN':'fixture'}), \
       patch.object(rt,'social_plans',return_value=[PLAN]), \
       patch.object(x_post,'load_log',return_value=book),patch.object(x_post,'save_log') as save, \
       patch.object(d,'queue_results',return_value=0),patch.object(d,'send_message') as send, \
       patch.object(d,'webhook',return_value='https://discord.invalid/plays'), \
       patch.object(b,'reconcile',side_effect=b.BufferError('local cap reached')),patch.object(run,'log'):
   run.buffer_posts(NOW,SimpleNamespace(first={},latest={}),{},[],status)
  send.assert_called_once()
  self.assertEqual(book['posts'][0]['discord']['state'],'sent')
  self.assertNotIn('sentAt',book['posts'][0])
  self.assertNotIn('bufferPostId',book['posts'][0])
  save.assert_called_once_with(book)
  self.assertIn('local cap reached',status['errors'][0])
