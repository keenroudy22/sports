"""New study cannot promote thin evidence or alter already-exposed cases."""
import copy, hashlib, json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_roster_model_v2 as old
import nba_roster_model_v3 as model
import nba_roster_validation_v2 as study
import nba_roster_confirmation as prior
import nba_roster_confirmation_v3 as confirmation
import nba_roster_runtime_v3 as runtime
import boxscores
from test_nba_roster_model import inputs, AT

class ConfirmationTests(unittest.TestCase):
    def test_frozen_coefficients_separate_cases_and_measured_failure(self):
        packet=confirmation.read(confirmation.STORE/'validation.json')
        original=confirmation.read(study.STORE/'validation.json')
        self.assertEqual(packet['coefficients'],original['coefficients'])
        self.assertEqual(packet['featureBounds'],original['featureBounds'])
        self.assertEqual(packet['fittedArtifactHash'],hashlib.sha256((study.STORE/'validation.json').read_bytes()).hexdigest())
        self.assertEqual(packet['validatedFamilies'],[])
        self.assertEqual(runtime.quality(packet),[])
        bad=copy.deepcopy(packet);bad['validatedFamilies']=['margin','total']
        self.assertEqual(runtime.quality(bad),[])
        self.assertEqual(len(packet['plan']['targets']),131)
        self.assertEqual(set(packet['plan']['targets']) & set(packet['plan']['excludedPreviouslyForecastable']),set())
        self.assertEqual(packet['plan']['targets'],confirmation.read(prior.STORE/'plan.json')['targets'])
        self.assertFalse(confirmation.archive_errors())
    def test_v3_preserves_feature_values_for_original_exposed_supported_games(self):
        rows=confirmation.read(study.STORE/'test-comparisons.json')['rows']
        packets=study.packets();boxes=confirmation.boxes()
        context=confirmation.read(study.STORE/'residual-context.json')['rows']
        records={str(r['eventId']):r for r in confirmation.hoops_store.load('NBA')}
        plan=confirmation.read(study.STORE/'plan.json')
        for row in rows:
            record=records[row['eventId']]
            day=study.boxscores.instant(record['kickoff']).astimezone(study.EASTERN).date().isoformat()
            packet=next(p for p in packets.values() if p.get('day')==day)
            game=study.game(record);clock=boxscores.instant(packet['reportedAt'])
            a,ha=old.features(game,packet,{},boxes,context,clock,retrospective=True)
            b,hb=model.features(game,packet,{},boxes,context,clock,retrospective=True)
            self.assertEqual(ha,hb)
            self.assertEqual(a,b)
    def test_starter_return_stays_held_and_explicit_zero_is_observed(self):
        roster,boxes,residuals,rows=inputs();rows[0]['status']='Available'
        self.assertIn('returning core',model.rotation('1',2027,boxes,roster,rows,AT)[1])
        p=copy.deepcopy(boxes[-1]['players'][0]);p.update(dnp=False,stats={'min':0,'pts':0})
        self.assertEqual(model.minutes(p),0);p['stats']['min']=None;self.assertIsNone(model.minutes(p))

    def test_newer_unknown_report_does_not_reuse_old_absence_proof(self):
        team=dict(eventId='1',team='2',submitted=True,unmapped=[],rows=[dict(athleteId='p',status='Out')])
        old=dict(retrievedAt='2026-10-27T18:00Z',reportedAt='2026-10-27T17:45Z',source='https://nba.com/old',teams=[team])
        self.assertEqual(runtime.absence_evidence([old],'1','2')['verifiedOut'],['p'])
        for teams in ([],[dict(team,submitted=False)],[dict(team,unmapped=['unknown'])]):
            new=dict(old,retrievedAt='2026-10-27T19:00Z',teams=teams)
            result=runtime.absence_evidence([new,old],'1','2')
            self.assertEqual(result['verifiedOut'],[]);self.assertFalse(result['absenceVerified'])

    def test_replay_clock_cannot_write_authoritative_forward_rows(self):
        import run
        from types import SimpleNamespace
        from unittest.mock import patch
        with patch.object(run.nba_trial_runtime if hasattr(run,'nba_trial_runtime') else runtime,'record_forward',create=True) as unused:
            run.record_nba_roster_capture(SimpleNamespace(no_push=False,now='2026-10-27T17:30Z'),{'errors':[]})
            unused.assert_not_called()
