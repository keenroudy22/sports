import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_brief
import llm


class BriefTests(unittest.TestCase):
    def test_exact_evidence_and_bounded_local_call(self):
        def ask(system, packet, schema, **kw):
            self.assertEqual(kw['timeout'], 180)
            self.assertNotIn('codex', kw)
            return {'highlights':['E0'], 'actions':['delivery']}
        result = local_brief.brief('3 wins\nfailed delivery ABC\n4 losses', ask)
        self.assertIn('failed delivery ABC', result)
        self.assertNotIn('3 wins', result)

    def test_hallucinated_evidence_and_timeout_fail_closed(self):
        self.assertIsNone(local_brief.brief('one fact', lambda *a,**kw: {'highlights':['E999'],'actions':[]}))
        self.assertIsNone(local_brief.brief('one fact', lambda *a,**kw: {'highlights':['E0'],'actions':['publish']}))
        def unavailable(*a,**kw): raise llm.LLMUnavailable('offline')
        self.assertIsNone(local_brief.brief('one fact', unavailable))
