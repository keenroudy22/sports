import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_reviewed_props as n
import nba_trial
import nba_trial_runtime
import staking
import nba_prop_release

NOW = datetime(2026, 11, 10, 17, tzinfo=timezone.utc)


class ReviewedNBAProps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = dict(id='NBA-1', providerId='1', season=2027, seasonType='regular-season',
                         kickoff='2026-11-11T00:00:00Z', status='scheduled',
                         teams={'home': {'id':'1'}, 'away': {'id':'2'}})
        (self.root/'slate.json').write_text(json.dumps({'games':[self.game]}))
        (self.root/'injuries-current.json').write_text(json.dumps({'official':{'reportedAt':'2026-11-10T16:30:00Z'}}))
        self.play = dict(id='NBA-reviewed-1-7-pts-over-dk', selectionMethod=n.METHOD, model=n.METHOD,
            league='NBA',season=2027,seasonType=2,eventId='NBA-1',game=self.game,kickoff=self.game['kickoff'],
            athleteId='7',team='1',player='Test Player',stat='pts',period='full_game',marketType='player',
            direction='over',line=15.5,odds=-110,oppositeOdds=-110,book='DraftKings',
            retrievedAt='2026-11-10T16:45:00Z',rawChance=None,chance=None,calibrated=False,
            riskUnits=1,roleChecked=True,sideVerified=True,exactLineVerified=True,
            source='https://www.nba.com/team/news',reasons=['Starting minutes remain stable against a short-handed frontcourt.'])
        staking.apply(self.play,NOW)
        self.play['sourceReview']=dict(approved=True,reviewer='kookn-desk',checkedAt='2026-11-10T16:50:00Z',
            why=self.play['reasons'][0],role='Three starts with stable minutes and no announced restriction.',
            matchup='Opponent frontcourt availability creates a documented matchup change.',
            countercase='A blowout or foul trouble could shorten his usual rotation.',
            sources=[dict(kind=k,url='https://www.nba.com/team/news',checkedAt='2026-11-10T16:40:00Z',
                          fact='Current sourced facts about this specific role and matchup.') for k in ('role','matchup')],
            quote=dict(verified=True,receipt='private reviewed screenshot',url='https://sportsbook.draftkings.com/event/1',
                       checkedAt='2026-11-10T16:45:00Z',**{k:self.play[k] for k in ('athleteId','stat','line','direction','odds','oppositeOdds')}))
        self.current={**{k:self.play[k] for k in ('eventId','athleteId','team','stat','line','book')},
                      'name':'Test Player','hold':None,'over':-110,'under':-110,'sourceAt':'2026-11-10T16:45:00Z',
                      'currentRole':{'games':3,'medianMinutes':28}}
        self.avail=patch.object(n.nba_capture,'availability_for_game',return_value=([],{}));self.avail.start();self.addCleanup(self.avail.stop)

    def refusal(self,play=None,current=None,now=NOW):
        return n.refusal(play or self.play,now,root=self.root,current=[current or self.current])

    def test_valid_sourced_review_has_no_probability(self):
        self.assertIsNone(self.refusal())
        self.assertIsNone(self.play['rawChance'])

    def test_probability_claim_never_bypasses_validation(self):
        for key,value in [('chance',.7),('rawChance',.7),('calibrated',True),('expectedValue',.1),('propEvidence',{})]:
            p=copy.deepcopy(self.play);p[key]=value;self.assertIsNotNone(self.refusal(p))

    def test_stale_future_review_and_quote_fail(self):
        for field in ('checkedAt','quote'):
            for stamp in ('2026-11-10T14:00:00Z','2026-11-10T18:00:00Z'):
                p=copy.deepcopy(self.play)
                if field=='quote':p['sourceReview']['quote']['checkedAt']=stamp
                else:p['sourceReview']['checkedAt']=stamp
                self.assertIsNotNone(self.refusal(p))

    def test_current_role_price_and_identity_holds(self):
        for key,value in [('hold','minutes restriction'),('over',-120),('name','Another Player'),('line',16.5),
                          ('currentRole',{'games':2,'medianMinutes':28}),('sourceAt','2026-11-10T14:00:00Z')]:
            self.assertIsNotNone(self.refusal(current={**self.current,key:value}))

    def test_incomplete_sources_and_unsupported_market_fail(self):
        p=copy.deepcopy(self.play);p['sourceReview']['sources']=p['sourceReview']['sources'][:1]
        self.assertIsNotNone(self.refusal(p))
        for key,value in [('book','FanDuel'),('period','1Q'),('stat','pra')]:
            self.assertIsNotNone(self.refusal({**self.play,key:value}))

    def test_new_report_requires_initial_review_but_unchanged_send_still_checks_status(self):
        (self.root/'injuries-current.json').write_text(json.dumps({'official':{'reportedAt':'2026-11-10T16:55:00Z'}}))
        self.assertIsNotNone(self.refusal())
        self.play['publishedAt']='2026-11-10T16:51:00Z'
        self.assertIsNone(n.refusal(self.play,NOW,root=self.root,current=[self.current],send_recheck=True))
        with patch.object(n.nba_capture,'availability_for_game',return_value=([{'athleteId':'7','status':'Questionable'}],{})):
            self.assertIsNotNone(n.refusal(self.play,NOW,root=self.root,current=[self.current],send_recheck=True))

    def test_delayed_send_uses_fresh_current_evidence_without_rewriting_original_review(self):
        later=NOW+timedelta(hours=2)
        self.play['publishedAt']='2026-11-10T16:51:00Z'
        current={**self.current,'sourceAt':'2026-11-10T18:55:00Z',
                 'currentRole':{**self.current['currentRole'],'receivedAt':'2026-11-10T18:54:00Z'}}
        self.assertIsNone(n.refusal(self.play,later,root=self.root,current=[current],send_recheck=True))
        self.assertIsNotNone(n.refusal(self.play,later,root=self.root,current=[current],send_recheck=False))

    def test_delayed_send_accepts_same_line_at_a_better_price_but_not_worse(self):
        self.play['publishedAt']='2026-11-10T16:51:00Z'
        better={**self.current,'over':-109,'under':-111}
        self.assertIsNone(n.refusal(self.play,NOW,root=self.root,current=[better],send_recheck=True))
        self.assertIsNotNone(n.refusal(self.play,NOW,root=self.root,current=[better],send_recheck=False))
        worse={**self.current,'over':-111,'under':-109}
        self.assertIsNotNone(n.refusal(self.play,NOW,root=self.root,current=[worse],send_recheck=True))

    def test_current_official_participation_required(self):
        with patch.object(n.nba_capture,'availability_for_game',return_value=([{'athleteId':'7','status':'Questionable'}],{})):
            self.assertIsNotNone(self.refusal())
        with patch.object(n.nba_capture,'availability_for_game',return_value=([],{'1':'not submitted'})):
            self.assertIsNotNone(self.refusal())

    def test_normal_stakes_duplicates_and_game_caps_remain(self):
        with patch.object(n,'refusal',return_value=None):
            self.assertEqual(nba_trial.evaluate(self.play,[],NOW),[])
            self.assertIn('stake policy mismatch',nba_trial.evaluate({**self.play,'riskUnits':2},[],NOW))
            self.assertIn('one NBA pick per game',nba_trial.evaluate(self.play,[{**self.play,'id':'old','type':'publish'}],NOW))
        self.assertTrue(nba_trial.evaluate(self.play,[],NOW))

    def test_current_match_cannot_skip_send_time_review(self):
        with patch.object(nba_trial_runtime,'rows',return_value=[]),patch.object(n,'refusal',return_value='new injury'):
            self.assertFalse(nba_trial_runtime.current_match(self.play,NOW))

    def test_immutable_original_without_transient_flags_rechecks_and_delivers(self):
        p=copy.deepcopy(self.play);p['publishedAt']='2026-11-10T16:51:00Z'
        for key in ('sideVerified','exactLineVerified','roleChecked'):p.pop(key)
        original=copy.deepcopy(p)
        with patch.object(nba_trial_runtime,'rows',return_value=[p]),patch.object(n,'refusal',return_value=None):
            self.assertTrue(nba_trial_runtime.current_match(p,NOW))
        self.assertEqual(p,original)
        with patch.object(nba_trial_runtime,'rows',return_value=[p]),patch.object(n,'refusal',return_value='new injury'):
            self.assertFalse(nba_trial_runtime.current_match(p,NOW))
        p['sourceReview']['quote']['odds']=-120
        with patch.object(nba_trial_runtime,'rows',return_value=[p]),patch.object(n,'refusal',return_value=None):
            self.assertFalse(nba_trial_runtime.current_match(p,NOW))

    def test_future_original_never_triggers_capture_in_dated_planner(self):
        p=copy.deepcopy(self.play);p['publishedAt']='2026-11-10T16:51:00Z'
        with patch.object(nba_trial_runtime,'review_ready',return_value=True),patch.object(nba_trial_runtime,'public_rows',return_value=[p]),patch.object(nba_trial_runtime.nba_capture,'step') as capture:
            self.assertEqual(nba_trial_runtime.social_plans(NOW-timedelta(days=1),{'posts':[]}),[])
        capture.assert_not_called()

    def test_reviewed_morning_prop_does_not_wait_for_old_nine_thirty_clock(self):
        now=datetime(2026,11,11,13,35,tzinfo=timezone.utc)
        p=copy.deepcopy(self.play)
        p.update(kickoff='2026-11-12T00:00:00Z',publishedAt='2026-11-11T13:34:00Z',
            reasons=['He has played 34, 35 and 33 minutes in his last three starts.'])
        p['game']['teams']={'home':{'id':'1','abbreviation':'NYK','name':'Knicks'},'away':{'id':'2','abbreviation':'MIL','name':'Bucks'}}
        with patch.object(nba_trial_runtime,'review_ready',return_value=True),patch.object(nba_trial_runtime,'public_rows',return_value=[p]),patch.object(nba_trial_runtime,'current_match',return_value=True):
            plans=nba_trial_runtime.social_plans(now,{'posts':[]},refresh=False)
        self.assertEqual(len(plans),1)
        self.assertEqual(plans[0][3],now+timedelta(minutes=15))

    def test_frozen_probability_adapter_hash_is_unchanged(self):
        self.assertEqual(nba_prop_release.implementation_hash(),
                         '432249595222a8c66cf336af85928d440fccd721da08596a2aef8cfc946f75ef')

    def test_original_review_is_saved_and_repeat_publication_refused(self):
        ledger=self.root/'ledger';ledger.mkdir()
        with patch.object(n,'refusal',return_value=None),patch.object(staking,'active',return_value=False):
            self.play['riskUnits']=staking.expected(self.play)
            self.assertEqual(nba_trial.record_publish(self.play,NOW,ledger),1)
            with self.assertRaises(ValueError):nba_trial.record_publish(self.play,NOW,ledger)
        saved=nba_trial_runtime.public_rows(ledger)[0]
        self.assertEqual(saved['sourceReview'],self.play['sourceReview'])
        self.assertEqual(saved['selectionMethod'],n.METHOD)
        self.assertIsNone(saved['rawChance'])
        self.assertTrue(n.audit_original(saved))
        self.assertFalse(n.audit_original({**saved,'sourceReview':{}}))
        self.assertFalse(n.audit_original({**saved,'chance':.8}))

    def test_official_result_uses_original_line_and_preserves_loss_window(self):
        play={**self.play,'publishedAt':NOW.isoformat()}
        final=dict(league='NBA',season=2027,seasonType=2,eventId='NBA-1',kickoff=play['kickoff'],
                   retrievedAt='2026-11-11T03:00:00Z',source='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=1',
                   players=[dict(id='7',team='1',dnp=False,stats={'pts':20})])
        later=NOW+timedelta(hours=12)
        result=nba_prop_release.grade(play,final,later,self.root,check=lambda *a,**k: {})
        self.assertEqual(result['result'],'win');self.assertEqual(result['actual'],20)
        final['players'][0]['stats']['pts']=10
        self.assertIsNone(nba_prop_release.grade(play,final,later,self.root,check=lambda *a,**k: {}))
        result=nba_prop_release.grade(play,final,later+timedelta(hours=12),self.root,check=lambda *a,**k: {})
        self.assertEqual(result['result'],'loss')


if __name__=='__main__':
    unittest.main()
