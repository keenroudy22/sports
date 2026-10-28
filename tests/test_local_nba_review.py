import json,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import local_nba_review as review
import llm
class LocalNBAReviewTests(unittest.TestCase):
    def setUp(self):
        self.packet={'facts':[{'id':'f0','kind':'support','text':'Observed starts, not a confirmed lineup','sources':['https://www.espn.com/']},
                              {'id':'f1','kind':'challenge','text':'Workload unknown','sources':['https://www.nba.com/']}], 'researchOnly':True}
    def test_only_sourced_excerpts_are_returned_without_invented_prose(self):
        with patch.object(llm,'draft_json',return_value={'support':['f0'],'challenge':['f1']}) as call:
            result=review.evaluate(self.packet)
        self.assertEqual(result['status'],'local-reviewed')
        self.assertEqual(result['support'][0],self.packet['facts'][0])
        self.assertEqual(call.call_args.kwargs['timeout'],12)
    def test_unknown_mistyped_or_wrong_direction_ids_cannot_clear_holds(self):
        for bad in ({'support':['f1'],'challenge':[]},{'support':['invented'],'challenge':[]},
                    {'support':[],'challenge':[],'odds':-110},{'support':[['f0']],'challenge':[]}):
            with patch.object(llm,'draft_json',return_value=bad): result=review.evaluate(self.packet)
            self.assertEqual(result['status'],'evidence-only')
            self.assertEqual(result['challenge'],[self.packet['facts'][1]])
    def test_omitted_model_challenge_never_hides_the_original_hold(self):
        with patch.object(llm,'draft_json',return_value={'support':[],'challenge':[]}):
            result=review.evaluate(self.packet)
        self.assertEqual(result['challenge'],[self.packet['facts'][1]])
    def test_timeout_preserves_hold_and_does_not_retry(self):
        with patch.object(llm,'draft_json',side_effect=llm.LLMUnavailable('busy')) as call:
            result=review.evaluate(self.packet)
        self.assertEqual(call.call_count,1)
        self.assertEqual(result['status'],'evidence-only')
        self.assertEqual(len(result['challenge']),1)
    def test_runtime_review_follows_buffer_scheduling_and_is_not_used_for_admission(self):
        import run
        source=Path(run.__file__).read_text()
        start=source.index('        owner_agenda(now, ctx, games)')
        end=source.index("    status.update(outcome='ok'",start)
        body=source[start:end]
        self.assertIn('local_nba_review.run',body)
        self.assertIn("not getattr(args,'now',None)",body)
        self.assertNotIn('admission(',body)
    def test_future_or_non_primary_prop_is_not_a_packet_fact(self):
        data={'rows':[{'stat':'pra'},{'stat':'pts','kickoff':'2026-10-27T00:00:00Z','sourceAt':'2026-10-27T00:00:00Z'}]}
        self.assertEqual(review.packet(data,datetime(2026,10,28,tzinfo=timezone.utc))['facts'],[])
