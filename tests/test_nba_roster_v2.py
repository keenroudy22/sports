import copy,sys,unittest
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_roster_model_v2 as m
import nba_roster_validation_v2 as v
from test_nba_roster_model import inputs,AT

class ExposureTests(unittest.TestCase):
    def test_explicit_zero_is_observed_but_missing_minutes_stay_unknown(self):
        roster,boxes,residuals,rows=inputs();b=copy.deepcopy(boxes[-1])
        p=b['players'][0];p.update(dnp=False,stats={'min':0,'pts':0})
        self.assertEqual(m.minutes(p),0);self.assertIsNotNone(m.complete_team(b,'1'))
        p['stats'].pop('min');self.assertIsNone(m.minutes(p));self.assertIsNone(m.complete_team(b,'1'))

    def test_persistent_absence_is_not_subtracted_again(self):
        roster,boxes,residuals,rows=inputs();rot,hold=m.rotation('1',2027,boxes,roster,rows,AT)
        self.assertIsNone(hold)
        feature,hold=m.exposure_context('1',2027,rot,boxes,residuals,AT)
        self.assertIsNone(hold);self.assertEqual(feature['exposure'],0)
        self.assertEqual(feature['sample'],5);self.assertLess(feature['score'],0)

    def test_new_absence_is_feature_from_actual_role_not_a_guessed_penalty(self):
        roster,boxes,residuals,rows=inputs();rows.append(dict(team='1',athleteId='2',status='Out'))
        rot,hold=m.rotation('1',2027,boxes,roster,rows,AT)
        self.assertIsNone(hold)
        feature,hold=m.exposure_context('1',2027,rot,boxes,residuals,AT)
        self.assertIsNone(hold);self.assertLess(feature['exposure'],0)
        self.assertEqual(feature['coreAbsences'][1]['recentMinutes'],[240/9]*3)
        # A future correction cannot revise the forecast's earlier evidence.
        later=copy.deepcopy(boxes[-1]);later['retrievedAt']=(AT+timedelta(hours=1)).isoformat()
        later['players'][1]['stats']['pts']=99
        self.assertEqual(m.exposure_context('1',2027,rot,boxes+[later],residuals,AT)[0],feature)

    def test_missing_core_workload_is_not_zero_filled(self):
        roster,boxes,residuals,rows=inputs();rot,_=m.rotation('1',2027,boxes,roster,rows,AT)
        for b in boxes[-3:]:b['players']=[p for p in b['players'] if p['id']!='1']
        self.assertIn('unknown',m.exposure_context('1',2027,rot,boxes,residuals,AT)[1])

    def test_four_feature_fit_is_bounded_and_never_shrinks_variance(self):
        rows=[((i,j,i/2,j/3),2*i-j) for i in range(-4,5) for j in range(-3,4)]
        fitted=m.fit(rows);self.assertEqual(len(fitted['coefficients']),4)
        comp=dict(score=1.,allowed=0.,exposure=1.,scoreSE=1.,allowedSE=1.,exposureSE=1.)
        feature={'teams':{s:{'comparison':dict(comp)} for s in ('home','away')}}
        baseline=dict(total=220.,margin=2.,sdMargin=12.,sdTotal=18.,homeWinProb=.6)
        out=m.predict(baseline,feature,fitted)
        self.assertGreaterEqual(out['sdMargin'],12);self.assertGreaterEqual(out['sdTotal'],18)
        feature['teams']['home']['comparison']['exposure']=100
        with self.assertRaises(ValueError):m.predict(baseline,feature,fitted)

if __name__=='__main__':unittest.main()

class StudyIntegrityTests(unittest.TestCase):
    def test_v1_source_and_its_failed_result_are_unchanged(self):
        import hashlib,json,nba_roster_model,nba_roster_validation
        root=Path(nba_roster_model.__file__).resolve().parents[1]
        packet=json.loads((root/'data/nba-roster-research/validation.json').read_text())
        self.assertEqual(hashlib.sha256(Path(nba_roster_model.__file__).read_bytes()).hexdigest(),packet['sourceHash'])
        self.assertEqual(hashlib.sha256(Path(nba_roster_model.__file__).read_bytes()+Path(nba_roster_validation.__file__).read_bytes()).hexdigest(),packet['studySourceHash'])
        self.assertEqual(packet['validatedFamilies'],[])

    def test_new_study_is_disjoint_and_retrospective_sources_cannot_clear_live(self):
        import json
        old=json.loads((v.ARCHIVE/'plan.json').read_text())
        new=json.loads((v.STORE/'plan.json').read_text())
        self.assertFalse(set(old['dates'])&set(new['dates']))
        self.assertEqual(len(new['dates']),35)
        self.assertFalse(v.archive_errors())

    def test_current_core_return_is_not_cleared_by_available_status(self):
        roster,boxes,residuals,rows=inputs()
        rows[0]['status']='Available'
        self.assertIn('returning core',m.rotation('1',2027,boxes,roster,rows,AT)[1])

    def test_recent_bench_row_omission_does_not_invent_a_roster_departure(self):
        roster,boxes,residuals,rows=inputs()
        for b in boxes[-3:-1]:
            b['players'].append(dict(id='11',name='Bench player',team='1',starter=False,dnp=False,stats={'min':5,'pts':0}))
            b['players'][-2]['stats']['min']-=5
        rot,hold=m.rotation('1',2027,boxes,{},rows,AT,retrospective=True)
        self.assertIsNone(hold);self.assertIn('11',rot['eligibleIds'])
