import copy,json,sys,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import boxscores,nba_capture,nba_prop_probability as p,nba_prop_release as n
import nba_trial as nt,nba_trial_runtime as rt

START=datetime(2026,10,28,15,tzinfo=timezone.utc)
NOW=datetime(2026,11,5,15,tzinfo=timezone.utc)

class PropReleaseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)/'nba-capture';self.root.mkdir()
 def study(self,loser=False,half=True):
  training=[(dict(id=str(i),eventId=str(i),stat='pts',projection={'value':20}),{'actual':22}) for i in range(30)]
  spec=p.fit(training,'pts',START);nba_capture.append_changed([spec],self.root/'probability-specs',lambda r:r['id'])
  n.freeze(self.root,START)
  for i in range(30):
   at=START+timedelta(days=1+i//5);event=str(1000+i);actual=10 if loser and i==0 else 22
   r=dict(id='q'+event,season=2027,league='NBA',eventId=event,athleteId='2',team='3',stat='pts',
    retrievedAt=boxscores.stamp(at),kickoff=boxscores.stamp(at+timedelta(hours=9)),model=p.BASELINE,
    projection={'value':20},book='DraftKings',line=20.5,over=-110,under=-110,side='over',odds=-110)
   pred=p.predict(r,spec,at)
   outcome=dict(id=r['id'],season=2027,retrievedAt=boxscores.stamp(at+timedelta(hours=12)),actual=actual,
    result='hit' if actual>20.5 else 'miss',projection=20,side='over',odds=-110,source='official',
    forecastAt=r['retrievedAt'],line=20.5,book='DraftKings',model=p.BASELINE)
   final=dict(league='NBA',season=2027,seasonType=2,eventId='NBA-'+event,kickoff=r['kickoff'],
    retrievedAt=outcome['retrievedAt'],source=f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event}',
    players=[dict(id='2',team='3',dnp=False,stats={'pts':actual},quarters={str(q):{'minutes':5 if half or q<3 else 0} for q in range(1,5)})],
    quarterWorkloadEvidence={'status':'reconciled'})
   for row,folder,key in ((r,'player-forecasts','id'),(pred,'probability-forecasts','id'),(outcome,'player-outcomes','id')):
    nba_capture.append_changed([row],self.root/folder,lambda x,k=key:x[k])
   nba_capture.append_changed([final],self.root.parent/'sport-box',lambda x:x['eventId'])
  return spec
 def live(self):
  game=dict(id='NBA-9000',providerId='9000',league='NBA',season=2027,seasonType='regular-season',status='scheduled',
   kickoff='2026-11-06T00:00:00Z',teams={'home':{'id':'3','name':'Home','abbreviation':'HOM'},'away':{'id':'4','name':'Away','abbreviation':'AWY'}})
  row=dict(eventId='9000',athleteId='2',name='Real Player',team='3',stat='pts',line=20.5,
   book='DraftKings',over=-110,under=-110,side='over',odds=-110,sourceAt='2026-11-05T14:55:00Z',kickoff=game['kickoff'],
   projection={'value':22,'model':p.BASELINE,'window':'This season','minutes':30},hold=None,
   currentRole={'games':3,'starts':3,'receivedAt':'2026-11-04T12:00:00Z','source':'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=8999'},
   availabilitySource='https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-05_10_45AM.pdf')
  boxscores.write_json(self.root/'slate.json',{'games':[game]})
  boxscores.write_json(self.root/'injuries-current.json',{'retrievedAt':'2026-11-05T14:58:00Z','official':{'reportedAt':'2026-11-05T14:45:00Z'}})
  return game,row
 def candidate(self):
  spec=self.study();game,row=self.live()
  evidence=dict(adapter=n.VERSION,stat='pts',specHash=spec['specHash'],probabilityAllowance=.02,evidenceHash='fixture')
  with patch.object(n,'proof',side_effect=lambda stat,*a:evidence if stat=='pts' else None),patch.object(n.props,'build',return_value={'rows':[row]}),patch.object(nba_capture,'availability_for_game',return_value=([],{})):
   offers=n.candidates(NOW,self.root)
  self.assertEqual(len(offers),1)
  nt.staking.apply(offers[0],NOW)
  return offers[0]
 def test_unapproved_model_and_missing_protocol_cannot_emit_candidates(self):
  self.assertIsNone(n.proof('pts',NOW,self.root));self.assertEqual(n.candidates(NOW,self.root),[])
  self.study();self.assertIsNone(n.proof('pts',START,self.root))
 def test_real_frozen_probability_and_book_evidence_unlock_only_supported_stat(self):
  self.study();good=n.proof('pts',NOW,self.root)
  self.assertIsNotNone(good);self.assertEqual((good['games'],good['easternDates']),(30,6))
  self.assertGreater(good['bookReturnLower95'],0)
  self.assertIsNone(n.proof('ast',NOW,self.root))
 def test_held_losing_book_case_cannot_be_removed_to_make_a_pass(self):
  self.study(loser=True,half=False)
  self.assertTrue(p.review(self.root,NOW)[0]['evidenceReady'])
  self.assertIsNone(n.proof('pts',NOW,self.root))
 def test_priced_loss_counts_and_independent_denominator_is_preserved(self):
  self.study(loser=True,half=True)
  proof=n.proof('pts',NOW,self.root)
  self.assertEqual(proof['games'],30);self.assertGreater(proof['bookReturnLower95'],0)
 def test_future_finals_cannot_supply_book_profit_proof(self):
  self.study();self.assertIsNone(n.proof('pts',START+timedelta(days=2),self.root))
 def test_verified_candidate_has_original_terms_and_no_forecast_in_card(self):
  offer=self.candidate();self.assertEqual(offer['riskUnits'],.5)
  self.assertEqual(n.selection(offer),'Real Player OVER 20.5 points')
  svg=n.card(offer)
  for term in ('REAL','PLAYER','20.5','POINTS','DRAFTKINGS','0.5u'):self.assertIn(term,svg)
  self.assertNotIn('BOOK SAYS',svg);self.assertNotIn('I HAVE IT',svg)
 def test_caller_flags_cannot_bypass_prop_evidence(self):
  offer=self.candidate()
  with patch.object(n,'candidates',return_value=[]):
   self.assertIn('NBA prop evidence/current-source hold',nt.evaluate(offer,[],NOW,calibration_verified=True))
  with patch.object(n,'candidates',return_value=[offer]):
   self.assertEqual(nt.evaluate(offer,[],NOW),[])
   for field,value in [('line',21.5),('odds',100),('athleteId','9'),('stat','pra'),('player','Wrong Player'),('riskUnits',1),('lane','chef_pick'),('paidProtection',True),('allAction',True)]:
    self.assertIn('NBA prop evidence/current-source hold',nt.evaluate(dict(offer,**{field:value}),[],NOW))
   self.assertIn('prop market identity hold',nt.evaluate(dict(offer,marketType='total'),[],NOW))
 def test_live_rechecks_stale_prices_and_injuries_even_with_approved_proof(self):
  spec=self.study();_,row=self.live();evidence={'specHash':spec['specHash'],'probabilityAllowance':.02}
  with patch.object(n,'proof',return_value=evidence),patch.object(n.props,'build',return_value={'rows':[row]}),patch.object(nba_capture,'availability_for_game',return_value=([],{})):
   initial=n.candidates(NOW,self.root);self.assertEqual(len(initial),1)
   row['roleReview']=initial[0]['roleReview']
   for starts in (2,None,False):
    row['currentRole']['starts']=starts;self.assertEqual(n.candidates(NOW,self.root),[])
   row['currentRole']['starts']=3
   row['sourceAt']='2026-11-05T12:00:00Z';self.assertEqual(n.candidates(NOW,self.root),[])
   row['sourceAt']='2026-11-05T14:55:00Z';row['hold']='changed role';self.assertEqual(n.candidates(NOW,self.root),[])
 def test_publication_and_actual_grade_keep_nba_record_separate_and_immutable(self):
  offer=self.candidate();trial=self.root.parent/'nba-trial'
  with patch.object(n,'candidates',return_value=[offer]):
   self.assertEqual(nt.record_publish(offer,NOW,trial),1)
   with self.assertRaises(ValueError):nt.record_publish(offer,NOW,trial)
  saved=rt.public_rows(trial)[0]
  self.assertEqual(saved['propEvidence'],offer['propEvidence']);self.assertEqual(saved['athleteId'],'2')
  final=dict(league='NBA',season=2027,seasonType=2,eventId='NBA-9000',kickoff=offer['kickoff'],retrievedAt='2026-11-06T03:00:00Z',
   source='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=9000',players=[dict(id='2',team='3',dnp=False,stats={'pts':22})])
  boxroot=self.root.parent/'sport-box';nba_capture.append_changed([final],boxroot,lambda r:r['eventId'])
  later=NOW+timedelta(days=1)
  self.assertEqual(rt.grade(later,trial,boxroot),1);self.assertEqual(rt.grade(later,trial,boxroot),0)
  self.assertEqual(nt.snapshot(rt.rows(trial))['win'],1)
  self.assertAlmostEqual(nt.snapshot(rt.rows(trial))['units'],.455,places=3)
 def test_public_loss_injury_check_holds_and_typed_fallback_is_not_book_proof(self):
  offer=dict(self.candidate(),publishedAt=boxscores.stamp(NOW))
  final=dict(league='NBA',season=2027,seasonType=2,eventId='NBA-9000',kickoff=offer['kickoff'],retrievedAt='2026-11-06T03:00:00Z',
   source='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=9000',players=[dict(id='2',team='3',dnp=False,stats={'pts':10})])
  early=datetime(2026,11,6,4,tzinfo=timezone.utc)
  self.assertIsNone(n.grade(offer,final,early,self.root,check=lambda *a,**k:{}))
  result=n.grade(offer,final,early+timedelta(hours=10),self.root,check=lambda *a,**k: {})
  self.assertEqual(result['result'],'loss');self.assertEqual(result['bookSettlement']['state'],'fallback')
 def test_discord_grade_uses_player_stat_and_void_does_not_become_loss(self):
  offer=dict(self.candidate(),result='void',actual=None,settledAt=boxscores.stamp(NOW))
  log={'posts':[{'id':offer['id'],'kind':'buffer:nba-trial','nbaPick':True,'discord':{'state':'sent','messageId':'1'}}]}
  self.assertEqual(rt.queue_discord_results(log,NOW,[offer]),1)
  text=log['posts'][0]['discord']['result']['text']
  for term in ('Real Player OVER 20.5 points','VOID','Did not play','+0.00u'):self.assertIn(term,text)
  self.assertEqual(rt.queue_discord_results(log,NOW,[offer]),0)
 def test_delivery_rehearsal_uses_playbook_spacing_image_and_plays_channel_once(self):
  import buffer_post as bp,discord_post
  from test_buffer_post import FakeBuffer
  offer=dict(self.candidate(),publishedAt=boxscores.stamp(NOW),series='NBA Picks')
  with patch.object(rt,'public_rows',return_value=[offer]),patch.object(rt,'review_ready',return_value=True),patch.object(rt,'current_match',return_value=True),patch.object(nba_capture,'step',return_value={}),patch.object(rt,'datetime',wraps=datetime) as clock:
   clock.now.return_value=NOW
   plans=rt.social_plans(NOW,{'posts':[]})
  self.assertEqual(len(plans),1);self.assertIn('Real Player OVER 20.5 points',plans[0][2])
  self.assertIn('\n\n',plans[0][2]);self.assertNotIn('22.0',plans[0][2])
  fake=FakeBuffer()
  with patch.object(rt,'reserve_delivery',return_value=True),patch.object(bp,'ticket_art_live',return_value=True),patch.object(bp,'plain_art_live',return_value=True):
   book=bp.schedule(plans,'x',{'posts':[]},NOW,key='fixture',send=fake,opener=lambda *_:True,log=lambda *_:None)
  self.assertEqual(len(book['posts']),1);entry=book['posts'][0]
  self.assertIn('@Playbook',entry['queuedText']);self.assertTrue(entry['queuedText'].endswith('21+ only'))
  self.assertEqual(entry['discord']['destination'],'plays');self.assertNotIn('@Playbook',entry['discord']['text'])
  self.assertTrue(entry['discord']['text'].endswith('21+ only'));self.assertTrue(entry['discord']['image'].endswith(offer['id'].lower()+'.png'))
  with patch.object(rt,'public_rows',return_value=[offer]),patch.object(rt,'current_match',return_value=False),patch.object(discord_post,'send_message') as send:
   discord_post.mirror_sent(book,plans[0][3],url='plays',wins_url='wins',log=lambda *_:None);send.assert_not_called()
  with patch.object(rt,'public_rows',return_value=[offer]),patch.object(rt,'current_match',return_value=True),patch.object(discord_post,'send_message') as send:
   discord_post.mirror_sent(book,plans[0][3],url='plays',wins_url='wins',log=lambda *_:None)
   discord_post.mirror_sent(book,plans[0][3],url='plays',wins_url='wins',log=lambda *_:None)
   self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.args[0],'plays')
 def test_held_prop_cannot_reserve_a_buffer_send_attempt(self):
  offer=self.candidate();trial=self.root.parent/'nba-trial'
  with patch.object(n,'candidates',return_value=[offer]):nt.record_publish(offer,NOW,trial)
  with patch.object(rt,'current_match',return_value=False):self.assertFalse(rt.reserve_delivery(offer['id'],NOW,trial))
  self.assertFalse(any(r['type']=='send-attempt' for r in rt.rows(trial)))
  with patch.object(rt,'current_match',return_value=True):
   self.assertTrue(rt.reserve_delivery(offer['id'],NOW,trial));self.assertFalse(rt.reserve_delivery(offer['id'],NOW,trial))
 def test_prop_correction_preserves_the_sent_discord_receipt(self):
  offer=dict(self.candidate(),result='loss',actual=19,settledAt=boxscores.stamp(NOW))
  book={'posts':[{'id':offer['id'],'kind':'buffer:nba-trial','nbaPick':True,'discord':{'state':'sent'}}]}
  self.assertEqual(rt.queue_discord_results(book,NOW,[offer]),1)
  sent=book['posts'][0]['discord']['result'];sent.update(state='sent',messageId='original-result')
  changed=dict(offer,result='void')
  self.assertEqual(rt.queue_discord_results(book,NOW,[changed]),1)
  mirror=book['posts'][0]['discord']
  self.assertEqual(mirror['previousResults'][0]['messageId'],'original-result')
  self.assertTrue(mirror['result']['text'].startswith('CORRECTION\n'))
  self.assertEqual(rt.queue_discord_results(book,NOW,[changed]),0)
 def test_prop_admission_keeps_shared_nba_count_and_same_game_limits(self):
  offer=self.candidate()
  prior=[dict(offer,id=f'previous-{i}',eventId=f'NBA-{i}',type='publish') for i in range(5)]
  with patch.object(n,'candidates',return_value=[offer]):
   self.assertIn('NBA daily pick cap',nt.evaluate(offer,prior,NOW))
   self.assertIn('one NBA pick per game',nt.evaluate(offer,[dict(prior[0],eventId=offer['eventId'])],NOW))
 def test_unapproved_lane_does_not_scan_large_settlement_history(self):
  with patch.object(n.probability,'review',side_effect=AssertionError('No study before a protocol')),patch.object(n.boxscores,'verify') as verify:
   self.assertIsNone(n.proof('pts',NOW,self.root));verify.assert_not_called()
 def test_card_only_changes_do_not_reset_the_frozen_admission_protocol(self):
  self.study();before=n.implementation_hash()
  with patch.object(n,'card',return_value='new presentation only'):
   self.assertEqual(n.implementation_hash(),before)
   self.assertIsNotNone(n.proof('pts',NOW,self.root))
 def test_long_player_and_research_copy_fit_after_required_x_footer(self):
  import buffer_post as bp,social_voice,x_post
  offer=dict(self.candidate(),player='Nickeil Alexander-Walker',publishedAt=boxscores.stamp(NOW),series='NBA Picks',
      reasons=['A very long verified research explanation. '*12,n.ROLE_REASON])
  with patch.object(rt,'public_rows',return_value=[offer]),patch.object(rt,'review_ready',return_value=True),patch.object(rt,'current_match',return_value=True),patch.object(nba_capture,'step',return_value={}),patch.object(rt,'datetime',wraps=datetime) as clock:
   clock.now.return_value=NOW;plans=rt.social_plans(NOW,{'posts':[]})
  self.assertEqual(len(plans),1)
  final=bp.x_ticket_copy(social_voice.finish(plans[0][2]),'play',offer['id'])
  self.assertLessEqual(x_post.tweet_length(final),280)
  for term in ('Nickeil Alexander-Walker OVER 20.5 points','-110','DraftKings','@Playbook','21+ only','AWY at HOM'):
   self.assertIn(term,final)
