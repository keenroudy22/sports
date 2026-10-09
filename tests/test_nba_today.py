import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_capture,nba_today,boxscores
from test_espn_props import game,board,NOW

class NBAEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
 def test_injury_id_comes_from_espn_link_and_comments_never_enter_store(self):
  payload={'injuries':[{'id':'1','injuries':[{'status':'Out','shortComment':'private prose','athlete':{'displayName':'Real Player','links':[{'href':'https://www.espn.com/nba/player/_/id/123/real-player'}]}}]}]}
  rows=nba_capture.injuries(payload,2027,'2026-10-09T00:00:00Z')
  self.assertEqual(rows[0]['athleteId'],'123');self.assertNotIn('shortComment',str(rows));self.assertNotIn('private prose',str(rows))
 def test_budget_stops_three_errors_and_has_domain_guard(self):
  def bad(url):raise OSError('offline')
  b=nba_capture.Budget(fetch=bad,sleep=lambda _:None)
  for _ in range(3):
   with self.assertRaises(OSError):b(nba_capture.INJURIES)
  with self.assertRaises(TimeoutError):b(nba_capture.INJURIES)
  self.assertEqual(b.requests,3)
  with self.assertRaises(ValueError):nba_capture.Budget(sleep=lambda _:None)('https://bad.example/')
 def test_last_good_slate_survives_failure(self):
  (self.root/'slate.json').write_text('{"games":[],"retrievedAt":"good"}')
  def bad(url):raise OSError('offline')
  result=nba_capture.step(NOW,root=self.root,budget=nba_capture.Budget(fetch=bad,sleep=lambda _:None),clock=lambda:NOW)
  self.assertEqual(json.loads((self.root/'slate.json').read_text())['retrievedAt'],'good')
  self.assertEqual(result['quotes'],0)
 def test_regular_box_only_historical_label_and_no_prep_from_old_season(self):
  boxes=[]
  for i in range(5):
   boxes.append({'eventId':str(i),'season':2026,'seasonType':2,'kickoff':f'2026-04-{10+i:02d}T00:00:00Z','players':[{'id':'1','name':'Real','team':'1','dnp':False,'stats':{'pts':20,'min':30}}]})
  boxes.append({'eventId':'post','season':2026,'seasonType':3,'kickoff':'2026-06-01T00:00:00Z','players':[{'id':'1','name':'Real','team':'1','dnp':False,'stats':{'pts':99,'min':30}}]})
  data=nba_today.build(NOW,root=self.root,boxes=boxes)
  self.assertEqual(data['trends'][0]['average'],20);self.assertEqual(data['trends'][0]['window'],'Last season · regular season');self.assertEqual(data['prep'],[])
 def test_missing_stat_and_dnp_never_inflate_history(self):
  boxes=[{'eventId':str(i),'season':2027,'seasonType':2,'kickoff':f'2026-10-{10+i:02d}T00:00:00Z','players':[{'id':'1','name':'Real','team':'1','dnp':i==0,'stats':{'pts':20} if i<2 else {}}]} for i in range(4)]
  self.assertEqual(nba_today.build(NOW,root=self.root,boxes=boxes)['trends'],[])
 def test_fresh_two_sided_quote_and_research_projection(self):
  g=game();g['id']='NBA-1';g['teams']={'home':{'id':'1'},'away':{'id':'2'}};g['seasonType']='regular-season';g['scores']={'home':None,'away':None}
  (self.root/'slate.json').write_text(json.dumps({'retrievedAt':boxscores.stamp(NOW),'games':[g]}))
  nba_capture.append_changed([{'eventId':'1','book':'DraftKings','season':2027,'retrievedAt':boxscores.stamp(NOW),'current':{'total':{'line':220.5,'over':-110,'under':-110}}}],self.root/'quotes',lambda r:r['eventId'])
  class Model:
   def predict(self,*args):return {'margin':4,'total':224,'sparse':True}
  data=nba_today.build(NOW,root=self.root,boxes=[],model_factory=lambda *args:Model())
  self.assertEqual(data['games'][0]['projection']['home'],114);self.assertEqual(data['games'][0]['totalQuote']['under'],-110)
  later=nba_today.build(NOW+timedelta(hours=5),root=self.root,boxes=[],model_factory=lambda *args:Model())
  self.assertNotIn('totalQuote',later['games'][0])
 def test_changed_store_and_ledger_refuse_tampering(self):
  rows=[{'eventId':'1','season':2027,'value':1,'retrievedAt':'a'}]
  root=self.root/'store';self.assertEqual(nba_capture.append_changed(rows,root,lambda r:r['eventId']),1)
  self.assertEqual(nba_capture.append_changed([{**rows[0],'retrievedAt':'b'}],root,lambda r:r['eventId']),0)
  p=root/'nba-2027.jsonl';p.write_text(p.read_text().replace('"value":1','"value":2'))
  with self.assertRaises(ValueError):nba_capture.append_changed(rows,root,lambda r:r['eventId'])
 def test_hosted_writer_is_schedule_only_and_existing_sports_unchanged(self):
  workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/publish.yml').read_text()
  part=workflow.split('Collect NBA final player boxes')[1].split('- name:')[0]
  self.assertIn("if: github.event_name == 'schedule'",part)
  import market_lab
  self.assertEqual(market_lab.LEAGUES,('MLB','NHL'))

if __name__=='__main__':unittest.main()
