import sys, unittest, copy
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import direction as d
class ResetTests(unittest.TestCase):
 def test_saved_rules_are_inert_after_reset_without_rewriting_history(self):
  p={'direction':{'card':{'weekendCap':3,'since':'2026-10-01T00:00:00Z','until':'2026-11-17T00:00:00Z'},'funTickets':{'active':True,'since':'2026-10-01T00:00:00Z','until':'2026-11-17T00:00:00Z'}},'history':[{'original':'retained'}]}; before=copy.deepcopy(p)
  old=datetime(2026,10,30,tzinfo=timezone.utc); now=datetime(2026,11,3,tzinfo=timezone.utc)
  self.assertEqual(d.weekend_cap(p,old,5),3); self.assertIsNotNone(d.fun_shape(p,old))
  self.assertEqual(d.weekend_cap(p,now,5),5); self.assertIsNone(d.fun_shape(p,now)); self.assertEqual(p,before)
 def test_cached_moves_cannot_reapply_prescriptions(self):
  p={}; now=datetime(2026,11,3,tzinfo=timezone.utc)
  self.assertEqual(d.apply(p,[{'key':'card'},{'key':'fun'}],now),[]); self.assertEqual(p['history'],[])
 def test_evaluation_is_diagnostic_and_has_no_ping(self):
  import test_direction as t
  now=datetime(2026,11,3,tzinfo=timezone.utc)
  rows=t.record(24,36,at=now-timedelta(days=5))
  moves=d.evaluate({}, {'rows':rows},now)
  card=[m for m in moves if m['key']=='card']; self.assertTrue(card); self.assertTrue(card[0]['reportOnly']); self.assertEqual(d.ping(card),'')
