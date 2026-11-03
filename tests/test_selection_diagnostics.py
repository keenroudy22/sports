import copy,sys,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import desk_performance as desk
import nba_forward_review as nba
import social_learning as social
NOW=datetime(2026,11,3,16,tzinfo=timezone.utc)
class SelectionDiagnosticsTests(unittest.TestCase):
 def test_legacy_priced_rows_are_not_silently_dropped(self):
  r=dict(id='old',league='NFL',season=2026,publishedAt='2026-09-20T12:00:00Z',kickoff='2026-09-20T20:00:00Z',settledAt='2026-09-21T02:00:00Z',result='loss',odds=-110,units=None,riskUnits=None,market='recYds')
  before=copy.deepcopy(r);g=desk.report([r,r,dict(r,id='assumed',priceAssumed=True),dict(r,id='estimated',priceEstimated=True)],NOW)['segments']
  self.assertEqual((g[0]['losses'],g[0]['units'],g[0]['riskedUnits']),(1,-1,1));self.assertEqual(r,before)
 def test_saved_stake_void_and_future_remain_distinct(self):
  r=dict(id='new',league='NFL',season=2026,publishedAt='2026-11-01T12:00:00Z',kickoff='2026-11-01T20:00:00Z',settledAt='2026-11-02T02:00:00Z',result='win',odds=120,riskUnits=.5,posted=True)
  g=desk.report([r,dict(r,id='void',result='void'),dict(r,id='future',settledAt='2026-11-04T02:00:00Z')],NOW)['segments'][0]
  self.assertEqual((g['wins'],g['voids'],g['units'],g['riskedUnits']),(1,1,.6,.5))
 def test_probability_audit_rejects_post_publication_evidence(self):
  r=dict(id='p',gameId='g',result='loss',publishedAt='2026-11-01T12:00:00Z',kickoff='2026-11-01T20:00:00Z',probabilityAtPublication=dict(chance=.6,push=0,evaluatedAt='2026-11-01T11:59:00Z'))
  future=copy.deepcopy(r);future['probabilityAtPublication']['evaluatedAt']='2026-11-01T12:01:00Z'
  out=desk.probability_review([r,future])
  self.assertEqual((out['scored'],out['independentGames'],out['meanForecast'],out['hitRate'],out['brier']),(1,1,.6,0,.36))
  self.assertEqual(out['excluded']['unverifiedPregameClock'],1)
 def sample(self):
  r=dict(id='a',eventId='g',athleteId='p',team='t',stat='pts',season=2027,model='v',retrievedAt='2026-11-01T12:00:00Z',kickoff='2026-11-01T20:00:00Z',line=20.5,book='DraftKings',projection=dict(value=20,minutes=40,rate=.5,window='This season'))
  o=dict(id='a',forecastAt=r['retrievedAt'],retrievedAt='2026-11-02T02:00:00Z',source='https://espn.com/game',model='v',line=20.5,book='DraftKings',projection=20,actual=15,result='miss')
  b=dict(eventId='g',kickoff=r['kickoff'],retrievedAt=o['retrievedAt'],league='NBA',season=2027,seasonType=2,players=[dict(id='p',team='t',dnp=False,stats=dict(min=30,pts=15,fga=12))])
  return r,o,b
 def test_error_attribution_is_explicitly_postgame_not_a_new_forecast(self):
  r,o,b=self.sample();out=nba.summarize([r],[o],NOW,[b])['workloadDiagnostics'];s=out['segments'][0]
  self.assertEqual((s['forecastMAE'],s['withActualMinutesMAE'],s['minutesComponentMAE']),(5,0,5));self.assertAlmostEqual(s['maxIdentityError'],0)
  self.assertEqual(out['inputCoverage']['fields']['potentialAssists'],0)
  self.assertIn('unavailable pregame',out['scope'])
 def test_box_future_corrections_dnp_and_identity_conflicts_cannot_supply_minutes(self):
  r,o,b=self.sample()
  for changes in (dict(retrievedAt='2026-11-04T02:00:00Z'),dict(season=2026),dict(kickoff='2026-11-01T21:00:00Z')):
   self.assertEqual(nba.summarize([r],[o],NOW,[dict(b,**changes)])['workloadDiagnostics']['segments'],[])
  bad=copy.deepcopy(b);bad['players'][0]['dnp']=True
  self.assertEqual(nba.summarize([r],[o],NOW,[bad])['workloadDiagnostics']['segments'],[])
 def test_repeated_books_cannot_inflate_workload_sample(self):
  r,o,b=self.sample();later=dict(r,id='b',book='FanDuel',retrievedAt='2026-11-01T13:00:00Z')
  wrong=dict(o,id='b',book='FanDuel',forecastAt=later['retrievedAt'])
  out=nba.summarize([later,r],[wrong,o],NOW,[b])['workloadDiagnostics']['segments'][0]
  self.assertEqual((out['comparisons'],out['games']),(1,1))
 def test_creative_comparison_uses_first_real_same_age_read_once(self):
  sent=NOW-timedelta(hours=80)
  e=dict(id='x',kind='buffer:play',sentAt=sent.isoformat(),card=True,cardTheme='felt',metricsHistory=[dict(at=(sent+timedelta(hours=h)).isoformat(),metrics={'impressions':v}) for h,v in ((23,10),(26,100),(30,200),(72,9000))])
  row=social.comparable_themes({'posts':[e,e]},NOW)[0]
  self.assertEqual((row['posts'],row['median24hViews'],row['sampleFloorMet']),(1,100,False))
 def test_missing_late_and_future_social_reads_are_not_backfilled(self):
  for hours in (None,10,72,100):
   e=dict(id='x',kind='buffer:play',sentAt=(NOW-timedelta(hours=80)).isoformat(),card=True,metrics={'impressions':99999})
   if hours is not None:e['metricsAt']=(NOW-timedelta(hours=80)+timedelta(hours=hours)).isoformat()
   self.assertEqual(social.comparable_themes({'posts':[e]},NOW),[])
