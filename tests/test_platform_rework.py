import sys,unittest,tempfile,json,shutil
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import desk_performance,schedule_audit
ROOT=Path(__file__).resolve().parents[1]
class PlatformReworkTests(unittest.TestCase):
 def test_withdrawal_stays_counted_but_personal_and_assumed_do_not(self):
  base=dict(id='x',league='CFB',season=2026,seasonType=2,lane='best_bet',marketType='moneyline',
   publishedAt='2026-10-27T12:00:00Z',kickoff='2026-10-28T00:00:00Z',settledAt='2026-10-28T03:00:00Z',
   result='loss',units=-0.5,riskUnits=0.5,odds=180,delivery={'xAt':'2026-10-27T12:10:00Z'},
   entryNote='We withdrew the recommendation.')
  rows=[base,dict(base,id='personal',community=True),dict(base,id='parlay',legs=['a']),
        dict(base,id='trial',lane='nba_trial'),dict(base,id='import',historicalImport=True,priceAssumed=True),base]
  r=desk_performance.report(rows,datetime(2026,10,28,12,tzinfo=timezone.utc))
  self.assertEqual(len(r['segments']),1)
  self.assertEqual((r['segments'][0]['losses'],r['segments'][0]['units']),(1,-0.5))
  self.assertEqual(desk_performance.report(rows,datetime(2026,10,27,23,tzinfo=timezone.utc))['segments'],[])
 def test_schedule_audit_no_network_and_detects_installed_drift(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d)
   for p in (ROOT/'deployment/mac').glob('*.plist'):shutil.copy(p,d/p.name)
   r=schedule_audit.audit(ROOT,d)
   self.assertEqual(r['issues'],[]);self.assertEqual(r['networkCalls'],0)
   (d/'com.keenroudy.sports.precheck.plist').unlink()
   self.assertIn('Installed schedule differs: precheck',schedule_audit.audit(ROOT,d)['issues'])
 def test_promotion_credit_not_added_to_captured_result(self):
  p=dict(id='x',league='CFB',season=2026,lane='best_bet',publishedAt='2026-10-27T12:00:00Z',
   kickoff='2026-10-28T00:00:00Z',settledAt='2026-10-28T03:00:00Z',result='loss',units=0,
   earlyExit=True,riskUnits=0.5,odds=-110,posted=True)
  self.assertEqual(desk_performance.report([p],datetime(2026,10,28,12,tzinfo=timezone.utc))['segments'][0]['units'],-0.5)
