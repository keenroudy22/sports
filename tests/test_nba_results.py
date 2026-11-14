import sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_results as n,buffer_post,nba_trial_runtime as rt
NOW=datetime(2026,11,11,13,tzinfo=timezone.utc)
PLAY=dict(id='NBA-reviewed-1-7-pts-over-dk',marketType='player',player='Test Player',stat='pts',
 direction='over',line=7.5,odds=101,riskUnits=1,book='DraftKings',result='win',actual=8,
 settledAt='2026-11-11T05:00:00Z')

class NBAResults(unittest.TestCase):
 def test_original_quote_and_both_outcomes_and_no_duplicate(self):
  for result,actual in [('win',8),('loss',7),('push',7.5),('void',None)]:
   play=dict(PLAY,result=result,actual=actual)
   book={'posts':[dict(id=play['id'],sentAt='2026-11-10T17:52:00Z',tweetId='123456789')]}
   with patch.object(rt,'public_rows',return_value=[play]):
    plans=n.plans(NOW,book,Path('/unused'))
    self.assertEqual(len(plans),1)
    self.assertEqual(buffer_post.quote_tweet_id(book,plans[0][0]),'123456789')
    self.assertNotIn('https://',plans[0][2])
    book['posts'].append(dict(id=plans[0][0]))
    self.assertEqual(n.plans(NOW,book,Path('/unused')),[])
 def test_missing_cancelled_and_future_receipts_stay_out(self):
  for entry in [dict(id=PLAY['id']),dict(id=PLAY['id'],tweetId='123456789',sentAt='x',deletedAt='x')]:
   with patch.object(rt,'public_rows',return_value=[PLAY]):
    self.assertEqual(n.plans(NOW,{'posts':[entry]},Path('/unused')),[])
  self.assertFalse(n.eligible(dict(PLAY,settledAt=(NOW+timedelta(seconds=1)).isoformat()),NOW))
 def test_original_stake_and_correction_signature(self):
  self.assertEqual(n.net(dict(PLAY,riskUnits=2)),2.02)
  self.assertEqual(n.net(dict(PLAY,result='loss',riskUnits=2)),-2)
  self.assertNotEqual(n.key(PLAY),n.key(dict(PLAY,result='loss',actual=7)))
 def test_results_do_not_need_pregame_model_approval(self):
  book={'posts':[dict(id=PLAY['id'],sentAt='2026-11-10T17:52:00Z',tweetId='123456789')]}
  with patch.object(rt,'public_rows',return_value=[PLAY]),patch.object(rt,'review_ready',return_value=False),patch.object(rt.nba_capture,'step') as capture:
   self.assertEqual(len(rt.social_plans(NOW,book)),1)
   capture.assert_not_called()

 def test_individual_finals_use_existing_result_spacing_after_reserved_posts(self):
  other=dict(PLAY,id='NBA-reviewed-2-8-pts-over-dk')
  book={'posts':[dict(id=p['id'],sentAt='2026-11-10T17:52:00Z',tweetId='123456789') for p in (PLAY,other)]}
  reserved=[('morning','receipt','morning',NOW+timedelta(minutes=5),'morning')]
  with patch.object(rt,'public_rows',return_value=[PLAY,other]):
   due=[row[3] for row in n.plans(NOW,book,Path('/unused'),reserved=reserved)]
  self.assertEqual(due,[NOW+timedelta(minutes=15),NOW+timedelta(minutes=25)])
