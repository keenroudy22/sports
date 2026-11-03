import copy,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import nba_dispersion_shadow as n,nba_capture,nba_prop_probability as base
import test_nba_prop_probability as fixtures
NOW=fixtures.NOW

class DispersionTests(unittest.TestCase):
 def test_frozen_volume_scaling_changes_uncertainty_without_altering_mean_or_approval(self):
  fixture=fixtures.ProbabilityStudyTests();training=fixture.training();spec=n.fit(training,'pts',NOW);row=fixture.row();before=copy.deepcopy(row)
  p=n.predict(row,spec,NOW)
  self.assertTrue(n.valid(spec));self.assertEqual(p['chanceOver'],.75);self.assertEqual(row,before)
  self.assertFalse(p['admissionReady']);self.assertNotIn('projection',p)
  self.assertIsNone(n.fit([(dict(r,eventId='same'),o) for r,o in training],'pts',NOW))
  bad=copy.deepcopy(spec);bad['scale']='tuned';bad['specHash']=base.digest({k:v for k,v in bad.items() if k!='specHash'})
  self.assertIsNone(n.predict(row,bad,NOW))
  self.assertIsNone(n.predict(dict(row,eventId='1'),spec,NOW))
  self.assertIsNone(n.predict(dict(row,retrievedAt='2026-10-28T13:00:00Z'),spec,NOW))
 def test_future_outcomes_and_duplicate_quotes_do_not_supply_independent_evidence(self):
  fixture=fixtures.ProbabilityStudyTests();spec=n.fit(fixture.training(),'pts',NOW);row=fixture.row();pred=n.predict(row,spec,NOW)
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   nba_capture.append_changed([spec],root/'dispersion-specs',lambda r:r['id'])
   nba_capture.append_changed([row],root/'player-forecasts',lambda r:r['id'])
   nba_capture.append_changed([pred],root/'dispersion-forecasts',lambda r:r['id'])
   outcome=dict(id='quote',season=2026,retrievedAt='2026-10-29T02:00:00Z',actual=22,result='hit',projection=20,side='over',odds=-110,source='official',forecastAt=row['retrievedAt'],line=20.5,book='draftkings',model=base.BASELINE)
   nba_capture.append_changed([outcome],root/'player-outcomes',lambda r:r['id'])
   self.assertEqual(n.review(root,NOW)[0]['games'],0)
   later=NOW+timedelta(days=1);review=n.review(root,later)[0]
   self.assertEqual((review['games'],review['easternDates']),(1,1));self.assertFalse(review['probabilityEvidenceReady']);self.assertFalse(review['admissionReady'])
   self.assertAlmostEqual(review['brierImprovement'],.1875)
   # Same player/market repeated later cannot turn one game into two cases.
   duplicate=dict(pred,retrievedAt='2026-10-28T14:01:00Z')
   nba_capture.append_changed([duplicate],root/'dispersion-forecasts',lambda r:(r['id'],r['retrievedAt']))
   self.assertEqual(n.review(root,later)[0]['games'],1)
 def test_future_training_evidence_cannot_create_a_specification(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);rows=[];outcomes=[]
   for i in range(30):
    r=dict(fixtures.ProbabilityStudyTests().row(),id=f'q{i}',eventId=str(i),retrievedAt='2026-10-26T14:00:00Z',kickoff='2026-10-27T23:00:00Z')
    rows.append(r);outcomes.append(dict(id=r['id'],season=2026,retrievedAt='2026-10-29T02:00:00Z',actual=22,result='hit',projection=20,side='over',odds=-110,source='official',forecastAt=r['retrievedAt'],line=20.5,book='draftkings',model=base.BASELINE))
   nba_capture.append_changed(rows,root/'player-forecasts',lambda r:r['id'])
   nba_capture.append_changed(outcomes,root/'player-outcomes',lambda r:r['id'])
   self.assertEqual(n.capture(root,NOW)['recorded'],0)
   self.assertFalse((root/'dispersion-specs').exists())
