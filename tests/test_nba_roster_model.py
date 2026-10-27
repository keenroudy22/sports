import copy
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_roster_model as m
import nba_roster_validation as v
import nba_official_availability as official
import nba_capture
from test_nba_official_availability import fixtures,TEXT,REPORTED,NOW,SOURCE

AT=datetime(2026,10,27,16,tzinfo=timezone.utc)


def inputs():
    roster=dict(team='1',season=2027,retrievedAt='2026-10-27T14:00:00Z',
        players=[dict(id=str(i),name='Player '+str(i),active=True) for i in range(1,11)])
    boxes=[];residuals=[]
    for i in range(10):
        kickoff=AT-timedelta(days=12-i)
        out=i>=3
        players=[dict(id=str(p),team='1',name='Player '+str(p),starter=p<=5,dnp=out and p==1,
                      stats={'min':0 if out and p==1 else 240/9 if out else 24,
                             'pts':0 if out and p==1 else 20 if out and p==2 else 10}) for p in range(1,11)]
        boxes.append(dict(eventId='NBA-'+str(i),league='NBA',season=2027,seasonType=2,
            kickoff=kickoff.isoformat(),retrievedAt=(kickoff+timedelta(hours=3)).isoformat(),
            teams={'1':{'score':100},'2':{'score':110}},players=players))
        residuals.append(dict(eventId=str(i),team='1',forecastAt=(kickoff-timedelta(hours=6)).isoformat(),scoreResidual=-4+i*.1,allowedResidual=2))
    return roster,boxes,residuals,[dict(team='1',athleteId='1',status='Out')]


class RosterModelTests(unittest.TestCase):
    def test_current_out_rotation_reconciles_and_uses_supported_comparisons(self):
        roster,boxes,residuals,rows=inputs()
        rot,hold=m.rotation('1',2027,boxes,roster,rows,AT)
        self.assertIsNone(hold);self.assertNotIn('1',rot['weights']);self.assertAlmostEqual(sum(rot['weights'].values()),240)
        self.assertEqual(rot['coreOut'],['1'])
        matched,hold=m.matched('1',2027,rot,boxes,residuals,AT)
        self.assertIsNone(hold);self.assertEqual(matched['sample'],7);self.assertLess(matched['score'],0)
        self.assertTrue(all(r['overlap']>=.9 for r in matched['matches']))

    def test_missing_row_never_becomes_zero_or_an_absence(self):
        roster,boxes,residuals,rows=inputs()
        for b in boxes:b['players']=[p for p in b['players'] if p['id']!='2']
        self.assertIn('Incomplete',m.rotation('1',2027,boxes,roster,rows,AT)[1])
        roster,boxes,residuals,rows=inputs();rot,_=m.rotation('1',2027,boxes,roster,rows,AT)
        for b in boxes[3:]:b['players']=[p for p in b['players'] if p['id']!='1']
        self.assertIsNone(m.matched('1',2027,rot,boxes,residuals,AT)[0])
        for b,r in zip(boxes,residuals):r.update(verifiedOut=['1'],absenceReportAt=(datetime.fromisoformat(b['kickoff'])-timedelta(hours=1)).isoformat(),absenceSource=SOURCE)
        self.assertEqual(m.matched('1',2027,rot,boxes,residuals,AT)[0]['sample'],7)

    def test_future_and_late_corrected_boxes_do_not_change_current_features(self):
        roster,boxes,residuals,rows=inputs();original=m.rotation('1',2027,boxes,roster,rows,AT)[0]
        correction=copy.deepcopy(boxes[-1]);correction['retrievedAt']=(AT+timedelta(hours=1)).isoformat();correction['players'][1]['stats']['min']=50
        future=copy.deepcopy(boxes[-1]);future.update(eventId='future',kickoff=(AT+timedelta(hours=2)).isoformat(),retrievedAt=(AT+timedelta(hours=5)).isoformat())
        self.assertEqual(m.rotation('1',2027,boxes+[correction,future],roster,rows,AT)[0],original)

    def test_unknown_status_stale_roster_and_unknown_minutes_hold(self):
        roster,boxes,residuals,rows=inputs()
        for status in ('Questionable','Probable','Doubtful','unknown'):
            self.assertIn('Unresolved',m.rotation('1',2027,boxes,roster,[dict(rows[0],status=status)],AT)[1])
        bad=copy.deepcopy(roster);bad.pop('retrievedAt')
        self.assertIn('roster',m.rotation('1',2027,boxes,bad,rows,AT)[1])
        bad=copy.deepcopy(boxes);bad[-1]['players'][1]['stats']['min']=float('nan')
        self.assertIn('Incomplete',m.rotation('1',2027,bad,roster,rows,AT)[1])

    def test_fixed_ridge_and_bounds_cannot_invent_confidence_or_extrapolate(self):
        training=[((float(i),float(j)),2*i-j) for i in range(-4,5) for j in range(-3,4)]
        fitted=m.fit(training)
        comparison=dict(score=1.,allowed=-1.,scoreSE=2.,allowedSE=3.)
        feature=dict(teams={s:dict(comparison=comparison) for s in ('home','away')})
        baseline=dict(total=220.,margin=3.,sdMargin=12.,sdTotal=18.,homeWinProb=.6)
        p=m.predict(baseline,feature,fitted)
        self.assertGreaterEqual(p['sdMargin'],12);self.assertGreaterEqual(p['sdTotal'],18)
        self.assertNotEqual(p['total'],baseline['total']);self.assertNotEqual(p['homeWinProb'],.6)
        self.assertEqual(baseline['total'],220)
        feature['teams']['home']['comparison']=dict(comparison,score=100)
        with self.assertRaises(ValueError):m.predict(baseline,feature,fitted)

    def test_archived_identity_mapping_cannot_clear_current_availability(self):
        games,rosters=fixtures()
        for roster in rosters.values():roster.update(identityOnly=True)
        report=official.parse(TEXT,games,rosters,REPORTED,AT,SOURCE,archive=True)
        report.update(season=2027)
        self.assertTrue(report['archive']);self.assertTrue(report['analysisOnly'])
        snapshot=dict(official=report,rows=[],gameAvailability=official.merge([],report,games))
        self.assertTrue(nba_capture.availability_for_game(snapshot,games[0],AT,max_hours=24)[1])
        self.assertIn('Archived report',m.features(games[0],report,{},[],[],AT)[1][0])

    def test_day_clustered_uncertainty_is_deterministic_and_not_one_row_one_game(self):
        values=[1.,2.,3.,4.,5.];days=['a','b','c','d','e']
        self.assertEqual(v.confidence(values,days),v.confidence(values,days))
        self.assertEqual(v.confidence(values,['a']*5),[None,None])


class RosterRuntimeTests(unittest.TestCase):
    def test_promotion_uses_measured_proof_not_ready_flag(self):
        import nba_roster_runtime as rt
        check=dict(trainGames=40,testGames=40,quotedGames=35,trainCoreAbsenceGames=12,
            testCoreAbsenceGames=12,scheduledTestGames=100,improvement95=[.1,.8],
            adjustedMAEOnQuotedGames=8.,quotedLineMAE=9.,baselineBrier=.24,adjustedBrier=.23,
            baselineWinnerBrier=.2,adjustedWinnerBrier=.19)
        packet=dict(version=m.VERSION,policy=m.POLICY,qualityGates=v.QUALITY_GATES,
            coefficients=[.1,.2],checks={k:copy.deepcopy(check) for k in ('margin','total')})
        self.assertEqual(rt.quality(packet),['margin','total'])
        self.assertEqual(rt.quality(None),[])
        self.assertEqual(rt.quality(dict(packet,coefficients=None)),[])
        for key,value in [('testGames',0),('improvement95',[]),('improvement95',[float('nan'),1]),
                          ('adjustedBrier',.25),('trainCoreAbsenceGames',0),('quotedGames',2)]:
            bad=copy.deepcopy(packet);bad['validatedFamilies']=['margin','total']
            for c in bad['checks'].values():c[key]=value
            self.assertEqual(rt.quality(bad),[],key)
        packet['checks']['margin']['adjustedWinnerBrier']=.3
        self.assertEqual(rt.quality(packet),['total'])

    def test_public_and_selection_use_only_the_same_validated_family(self):
        import nba_roster_runtime as rt
        baseline=dict(total=220,margin=2,sdTotal=18,sdMargin=12,homeWinProb=.6)
        adjusted=dict(total=215,margin=5,sdTotal=19,sdMargin=13,homeWinProb=.7)
        self.assertEqual(rt.apply_validated(baseline,dict(prediction=adjusted,validatedFamilies=[])),(baseline,[]))
        result,families=rt.apply_validated(baseline,dict(prediction=adjusted,validatedFamilies=['total']))
        self.assertEqual(result['total'],215);self.assertEqual(result['margin'],2)
        self.assertEqual(result['homeWinProb'],.6);self.assertEqual(families,['total'])
        adjusted['homeWinProb']=float('nan')
        result,families=rt.apply_validated(baseline,dict(prediction=adjusted,validatedFamilies=['margin']))
        self.assertEqual(result,baseline);self.assertEqual(families,[])

    def test_conditional_archive_status_never_clears_current_status(self):
        roster,boxes,residuals,rows=inputs()
        rows.append(dict(team='1',athleteId='2',status='Questionable'))
        self.assertIn('Unresolved',m.rotation('1',2027,boxes,roster,rows,AT)[1])
        rotation,hold=m.rotation('1',2027,boxes,roster,rows,AT,retrospective=True)
        self.assertIsNone(hold);self.assertEqual(rotation['unresolved'],['2'])
        self.assertTrue(rotation['conditionalAvailable'])

    def test_unknown_reserve_is_named_and_large_unknown_workload_holds(self):
        roster,boxes,residuals,rows=inputs()
        roster['players'].append(dict(id='11',name='New reserve',active=True))
        rotation,hold=m.rotation('1',2027,boxes,roster,rows,AT)
        self.assertIsNone(hold);self.assertIn('11',rotation['unmodeledReserveIds'])
        self.assertNotIn('11',rotation['weights'])
        self.assertAlmostEqual(sum(rotation['weights'].values())+rotation['reserveMinutes'],240)

    def test_future_or_malformed_validation_and_replay_cannot_write_context(self):
        import tempfile,json
        import nba_roster_runtime as rt
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for clock in ('garbage',(AT+timedelta(days=1)).isoformat()):
                (root/'validation.json').write_text(json.dumps(dict(createdAt=clock)))
                self.assertEqual(rt.extend_context(AT,root),0)
                self.assertFalse((root/'residual-forward').exists())
                self.assertIsNone(rt.current({}, {}, AT,root,root)['prediction'])

    def test_forward_outcomes_are_separate_idempotent_and_correctable(self):
        import tempfile
        import nba_roster_runtime as rt
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);roster,boxes,residuals,rows=inputs();final=boxes[-1]
            final['teams']['1']['home']=True;final['teams']['2']['home']=False
            forecast=dict(league='NBA',season=2027,eventId='9',capturedAt='2026-10-01T00:00:00Z',
                baseline=dict(total=200,margin=0),prediction=dict(total=205,margin=-5))
            nba_capture.append_changed([forecast],root/'forward',lambda r:r['eventId'])
            self.assertEqual(rt.grade(AT,root,[final]),1)
            self.assertEqual(rt.grade(AT,root,[final]),0)
            self.assertEqual(rt.summary(root)['gradedGames'],1)
            final=copy.deepcopy(final);final['retrievedAt']=AT.isoformat();final['teams']['2']['score']=111
            self.assertEqual(rt.grade(AT,root,[final]),1)
            self.assertEqual(rt.summary(root)['gradedGames'],1)
            self.assertFalse((root/'nba-trial').exists())

class RosterAdmissionIntegrationTests(unittest.TestCase):
    def test_known_out_needs_matching_validated_family_unresolved_still_holds(self):
        import tempfile,json
        from unittest.mock import patch
        import nba_trial_runtime as rt
        game=dict(id='NBA-1',providerId='1',season=2027,seasonType='regular-season',status='scheduled',
            kickoff='2026-10-27T23:00:00Z',teams={s:dict(id=i,abbreviation=i) for s,i in [('home','1'),('away','2')]})
        baseline=dict(total=210,sdTotal=20,margin=2,sdMargin=12,homeWinProb=.55)
        class Model:
            def predict(self,*args):return baseline
        history=[dict(season=2026,type=2,kickoff=f'2026-04-{10+i:02d}T00:00:00Z',
            home={'id':'1'},away={'id':'2'},homeScore=100,awayScore=100) for i in range(5)]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'slate.json').write_text(json.dumps({'games':[game]}))
            (root/'injuries-current.json').write_text(json.dumps(dict(season=2027,retrievedAt=AT.isoformat())))
            nba_capture.append_changed([dict(league='NBA',season=2027,eventId='1',book='DraftKings',retrievedAt=AT.isoformat(),
                source='https://sports.core.api.espn.com/nba/odds',current={'total':dict(line=225.5,over=-110,under=-110)})],root/'quotes',lambda r:r['eventId'])
            rows=[dict(team='1',status='Out')]
            with patch.object(nba_capture,'availability_for_game',return_value=(rows,{})),patch.object(rt.nba_roster_runtime,'current') as current:
                current.return_value=dict(holds=['Failed historical support'],validatedFamilies=[],prediction=dict(baseline,total=205))
                self.assertEqual(rt.candidates(AT,root,lambda *args:Model(),history),[])
                current.return_value=dict(holds=[],validatedFamilies=['total'],prediction=dict(baseline,total=205))
                candidates=rt.candidates(AT,root,lambda *args:Model(),history)
                self.assertEqual(len(candidates),1);self.assertEqual(candidates[0]['model'],m.VERSION)
                self.assertEqual(candidates[0]['projection'],205)
                rows[0]['status']='Questionable';current.reset_mock()
                self.assertEqual(rt.candidates(AT,root,lambda *args:Model(),history),[])
                current.assert_not_called()

if __name__=='__main__':unittest.main()
