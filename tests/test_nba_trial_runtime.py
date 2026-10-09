import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_trial_runtime as rt
import nba_trial as nt
import nba_capture,boxscores
from test_nba_trial import offer,NOW

class TrialRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
 def review(self):return {'delivered':True,'vetoed':False,'sentAt':'2026-10-09T22:00:00Z','pngSHA256':hashlib.sha256((rt.ROOT/'design/final/nba-trial-preview.png').read_bytes()).hexdigest()}
 def test_opening_review_hash_and_veto_fail_closed(self):
  self.assertTrue(rt.review_ready(NOW,self.review()))
  self.assertFalse(rt.review_ready(NOW-timedelta(days=11),self.review()))
  r=self.review();r['vetoed']=True;self.assertFalse(rt.review_ready(NOW,r))
  r=self.review();r['pngSHA256']='wrong';self.assertFalse(rt.review_ready(NOW,r))
  with patch.dict('os.environ',{'KEENROUDY_NBA_TRIAL':'0'}):self.assertFalse(rt.review_ready(NOW,self.review()))
 def test_integer_line_excludes_push_and_unknown_variance_holds(self):
  self.assertLess(rt.total_chance(220,20,220,'under'),.5)
  self.assertAlmostEqual(rt.total_chance(220,20,220.5,'under')+rt.total_chance(220,20,220.5,'over'),1)
  with self.assertRaises(ValueError):rt.total_chance(220,0,220.5,'under')
 def test_support_uses_actual_regular_season_and_never_opposing_numbers(self):
  game={'season':2027,'teams':{'home':{'id':'1','abbreviation':'A'},'away':{'id':'2','abbreviation':'B'}}}
  history=[{'season':2026,'type':2,'kickoff':f'2026-04-{10+i:02d}T00:00:00Z','home':{'id':'1'},'away':{'id':'2'},'homeScore':100,'awayScore':100} for i in range(5)]
  self.assertEqual(len(rt.support(game,220.5,'under',history,NOW)),2)
  self.assertEqual(rt.support(game,220.5,'over',history,NOW),[])
 def test_publication_keeps_game_metadata_and_grades_only_known_matching_final(self):
  play={**offer(),'eventId':'NBA-1','direction':'under','game':{'teams':{}},'reasons':['Source 1','Source 2'],'projection':210.,'model':'hoops-v1'}
  nt.record_publish(play,NOW,self.root,preview_sent='2026-10-09T22:00:00Z')
  self.assertEqual(rt.public_rows(self.root)[0]['eventId'],'NBA-1')
  boxes=self.root/'boxes';boxes.mkdir()
  final={'eventId':'NBA-1','seasonType':2,'kickoff':play['kickoff'],'teams':{'1':{'score':100},'2':{'score':101}},'source':'https://site.api.espn.com/nba/summary'}
  boxscores.append(boxes/'nba-2027.jsonl',[final])
  self.assertEqual(rt.grade(NOW+timedelta(days=1),self.root,boxes),1)
  self.assertEqual(rt.grade(NOW+timedelta(days=1),self.root,boxes),0)
  self.assertEqual(nt.snapshot(rt.rows(self.root))['win'],1)
  boxscores.append(boxes/'nba-2027.jsonl',[{**final,'teams':{'1':{'score':120},'2':{'score':121}}}])
  self.assertEqual(rt.grade(NOW+timedelta(days=2),self.root,boxes),1)
  self.assertEqual(nt.snapshot(rt.rows(self.root))['loss'],1)
 def test_candidates_require_known_variance_support_and_clear_current_injuries(self):
  root=self.root/'capture';root.mkdir()
  game={'id':'NBA-1','providerId':'1','league':'NBA','season':2027,'seasonType':'regular-season','kickoff':'2026-10-20T23:00:00Z','status':'scheduled','timeConfirmed':True,'teams':{'home':{'id':'1','abbreviation':'A'},'away':{'id':'2','abbreviation':'B'}}}
  (root/'slate.json').write_text(json.dumps({'games':[game]}))
  snapshot={'retrievedAt':'2026-10-20T13:00:00Z','season':2027,'rows':[]}
  (root/'injuries-current.json').write_text(json.dumps(snapshot))
  quote={'eventId':'1','book':'DraftKings','season':2027,'retrievedAt':'2026-10-20T13:00:00Z','source':'https://sports.core.api.espn.com/nba/odds','current':{'total':{'line':221.5,'over':-110,'under':-110}}}
  nba_capture.append_changed([quote],root/'quotes',lambda r:r['eventId'])
  history=[{'season':2026,'type':2,'kickoff':f'2026-04-{10+i:02d}T00:00:00Z','home':{'id':'1'},'away':{'id':'2'},'homeScore':100,'awayScore':100} for i in range(5)]
  class Model:
   def predict(self,*a):return {'total':210,'sdTotal':20}
  result=rt.candidates(NOW,root,lambda *a:Model(),history)
  self.assertEqual(len(result),1);self.assertFalse(nt.evaluate(result[0],[],NOW,preview_sent='2026-10-09T22:00:00Z'))
  snapshot['rows']=[{'team':'1','status':'Out'}]
  (root/'injuries-current.json').write_text(json.dumps(snapshot))
  self.assertEqual(rt.candidates(NOW,root,lambda *a:Model(),history),[])
 def test_reserve_delivery_is_once_even_without_buffer_ack(self):
  play={**offer(),'eventId':'NBA-1','direction':'under'}
  nt.record_publish(play,NOW,self.root,preview_sent='2026-10-09T22:00:00Z')
  self.assertTrue(rt.reserve_delivery(play['id'],NOW,self.root))
  self.assertFalse(rt.reserve_delivery(play['id'],NOW,self.root))
 def test_admission_is_one_per_day_and_respects_football_queue_reserve(self):
  play={**offer(),'eventId':'NBA-1','direction':'under','game':{'teams':{}},'reasons':['Source 1','Source 2'],'projection':210.,'model':'hoops-v1'}
  with patch.dict('os.environ',{'BUFFER_TOKEN':'fixture-token'}),patch.object(rt,'candidates',return_value=[play]):
   result=rt.admission(NOW,root=self.root,review=self.review(),log_book={'posts':[]},capture=False)
   self.assertEqual(result['state'],'admitted')
   self.assertEqual(rt.admission(NOW,root=self.root,review=self.review(),log_book={'posts':[]},capture=False)['reason'],'one NBA Trial per day')
  other=self.root/'other';other.mkdir()
  busy={'posts':[{'bufferPostId':str(i),'dueAt':'2026-10-20T15:00:00Z'} for i in range(7)]}
  with patch.dict('os.environ',{'BUFFER_TOKEN':'fixture-token'}),patch.object(rt,'candidates',side_effect=AssertionError('No candidate call under pressure')):
   self.assertEqual(rt.admission(NOW,root=other,review=self.review(),log_book=busy,capture=False)['reason'],'football queue reserve')
 def test_trial_audit_catches_missing_public_play_and_wrong_units(self):
  import nba_trial_audit
  play={**offer(),'eventId':'NBA-1','direction':'under','game':{'teams':{}},'reasons':['Source 1','Source 2'],'projection':210.,'model':'hoops-v1'}
  nt.record_publish(play,NOW,self.root,preview_sent='2026-10-09T22:00:00Z')
  record=nt.snapshot(rt.rows(self.root))
  good={'trial':{'record':record,'plays':[{'id':play['id']}]}}
  self.assertEqual(nba_trial_audit.audit(good,self.root)['issues'],[])
  good['trial']['plays']=[];self.assertTrue(nba_trial_audit.audit(good,self.root)['issues'])
  good['trial']['record']['units']=4;self.assertTrue(nba_trial_audit.audit(good,self.root)['issues'])
 def test_no_network_or_admission_before_opening(self):
  with patch.object(nba_capture,'step',side_effect=AssertionError('no call')):
   self.assertEqual(rt.admission(NOW-timedelta(days=11),root=self.root,review=self.review())['state'],'held')
 def test_precheck_price_or_role_hold_cancels_without_erasing_record(self):
  book={'posts':[{'id':'NBA-1','kind':'buffer:nba-trial','bufferPostId':'123','dueAt':'2026-10-20T14:30:00Z'}]}
  calls=[]
  with patch.object(rt,'public_rows',return_value=[{'id':'NBA-1'}]),patch.object(rt,'review_ready',return_value=True),patch.object(rt,'current_match',return_value=False):
   self.assertTrue(rt.precheck(NOW,book,refresh=False,delete=calls.append))
  self.assertEqual(calls,['123']);self.assertIn('cancelledAt',book['posts'][0])
 def test_late_send_uses_reserved_football_slots_and_has_no_discord_payload(self):
  import buffer_post
  play={**offer(),'publishedAt':'2026-10-20T13:00:00Z','eventId':'NBA-1','direction':'under','projection':210.,'reasons':['Last season, A scored 100.0 a game across its last five recorded regular-season games.'],'game':{'teams':{'home':{'abbreviation':'A'},'away':{'abbreviation':'B'}}}}
  with patch.object(rt,'public_rows',return_value=[play]),patch.object(rt,'review_ready',return_value=True),patch.object(rt,'current_match',return_value=True),patch.object(nba_capture,'step',return_value={}):
   plans=rt.social_plans(NOW,{'posts':[]},root=self.root,reserved=[('football','play','text',NOW+timedelta(minutes=15),'card')])
  self.assertEqual(plans[0][1],'nba-trial');self.assertGreaterEqual(plans[0][3],NOW+timedelta(minutes=25))
  self.assertIn('NBA Trial',plans[0][2]);self.assertNotIn('1u',plans[0][2])

if __name__=='__main__':unittest.main()
