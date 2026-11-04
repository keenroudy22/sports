import copy,json,sys,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import boxscores,nba_capture,nba_morning_health as n,desk_health
NOW=datetime(2026,11,5,14,5,tzinfo=timezone.utc)


class MorningHealthTests(unittest.TestCase):
 def fixture(self,folder,failed=True):
  root=Path(folder)
  boxscores.write_json(root/'slate.json',dict(games=[dict(kickoff='2026-11-06T00:00:00Z')]))
  capture=dict(league='NBA',season=2027,scheduled=True,slot='2026-11-05T13:31:00Z',retrievedAt='2026-11-05T13:33:00Z',
   errors=['official-availability-unavailable'] if failed else [],props={'errors':0})
  return root,capture
 def append(self,root,capture):nba_capture.append_changed([capture],root/'observations',lambda r:r['slot'])
 def completion(self,root,**changes):
  row=dict(id='receipt',league='NBA',season=2027,state='completed',scheduledSlot='2026-11-05T13:31:00Z',reportObservedAt='2026-11-05T13:35:00Z',retrievedAt='2026-11-05T13:40:00Z',forwardRecorded=0,probabilityRecorded=0)
  row.update(changes);nba_capture.append_changed([row],root/'source-completions',lambda r:r['id'])
 def test_missing_real_capture_is_pending_then_overdue(self):
  with tempfile.TemporaryDirectory() as folder:
   root,_=self.fixture(folder)
   self.assertEqual(n.status(root,NOW-timedelta(minutes=40))['issues'],[])
   self.assertEqual(n.status(root,NOW)['issues'][0]['code'],'nba-morning-missing')
 def test_actual_pdf_recovery_can_complete_with_zero_candidates_without_promoting_a_model(self):
  with tempfile.TemporaryDirectory() as folder:
   root,c=self.fixture(folder);self.append(root,c);self.completion(root)
   r=n.status(root,NOW);self.assertEqual(r['state'],'recovered');self.assertEqual(r['forwardRecorded'],0)
   self.assertEqual(r['issues'],[]);self.assertNotIn('admissionReady',r)
 def test_future_wrong_slot_and_pre_capture_report_do_not_clear_a_failed_morning(self):
  for changes in ({'retrievedAt':'2026-11-05T14:10:00Z'},{'scheduledSlot':'2026-11-04T13:31:00Z'},{'reportObservedAt':'2026-11-05T13:30:00Z'}):
   with self.subTest(changes=changes),tempfile.TemporaryDirectory() as folder:
    root,c=self.fixture(folder);self.append(root,c);self.completion(root,**changes)
    r=n.status(root,NOW);self.assertEqual(r['state'],'source-recovery-needed');self.assertTrue(r['issues'])
 def test_unscheduled_future_or_early_captures_cannot_replace_the_real_slot(self):
  for changes in ({'scheduled':False},{'retrievedAt':'2026-11-05T14:10:00Z'},{'slot':'2026-11-05T13:15:00Z'}):
   with self.subTest(changes=changes),tempfile.TemporaryDirectory() as folder:
    root,c=self.fixture(folder,False);c.update(changes);self.append(root,c)
    self.assertEqual(n.status(root,NOW)['state'],'missing')
 def test_other_capture_errors_and_late_recovery_remain_visible(self):
  with tempfile.TemporaryDirectory() as folder:
   root,c=self.fixture(folder);c['errors'].append('quote-unavailable');self.append(root,c);self.completion(root)
   self.assertEqual(n.status(root,NOW)['state'],'capture-failed')
  with tempfile.TemporaryDirectory() as folder:
   root,c=self.fixture(folder);self.append(root,c);self.completion(root,retrievedAt='2026-11-05T14:01:00Z')
   self.assertEqual(n.status(root,NOW)['state'],'recovered-late')
 def test_direct_capture_is_observed_not_bet_approval_and_tampering_fails(self):
  with tempfile.TemporaryDirectory() as folder:
   root,c=self.fixture(folder,False);self.append(root,c)
   self.assertEqual(n.status(root,NOW)['state'],'capture-recorded')
   file=next((root/'observations').glob('*.jsonl'));file.write_text(file.read_text().replace('13:31','13:32'))
   self.assertEqual(n.status(root,NOW)['state'],'invalid')
 def test_overall_success_cannot_hide_stale_official_report(self):
  from tests.test_desk_health import DeskHealthTests
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);f=DeskHealthTests();f.fixture(root)
   f.write(root,'private/status.json',{'outcome':'ok','finishedAt':NOW.isoformat()})
   store=root/'data/nba-capture';store.mkdir(parents=True);boxscores.write_json(store/'slate.json',dict(games=[dict(kickoff='2026-11-05T18:00:00Z')]))
   boxscores.write_json(store/'injuries-current.json',dict(retrievedAt=boxscores.stamp(NOW),official=dict(retrievedAt=boxscores.stamp(NOW),reportedAt='2026-11-05T12:00:00Z')))
   result=desk_health.summary(root,root/'private',root,NOW)
   row=next(s for s in result['nbaSources'] if s['name']=='NBA official availability')
   self.assertEqual(row['state'],'stale');self.assertEqual(result['nbaMorning']['state'],'missing')
   self.assertIn('source-NBA official availability',{r['code'] for r in result['issues']})
   self.assertEqual({r['name'] for r in result['sources']},set(desk_health.SOURCE_LIMITS))
   self.assertIsNotNone(desk_health.reliability_sample(result,NOW),'Existing reliability observations remain valid without a journal reset')
 def test_real_on_time_retry_is_distinguished_from_a_future_or_late_receipt(self):
  with tempfile.TemporaryDirectory() as folder:
   root,c=self.fixture(folder);self.append(root,c)
   retry=dict(c,slot='2026-11-05T13:45:00Z',retrievedAt='2026-11-05T13:47:00Z',errors=[]);self.append(root,retry)
   result=n.status(root,NOW);self.assertEqual(result['state'],'capture-recorded');self.assertEqual(result['attempts'],2)
  with tempfile.TemporaryDirectory() as folder:
   root,c=self.fixture(folder,False);c['retrievedAt']='2026-11-05T14:01:00Z';self.append(root,c)
   self.assertEqual(n.status(root,NOW)['state'],'capture-late')
 def test_a_nearby_nba_game_with_missing_capture_store_is_not_silent_success(self):
  from tests.test_desk_health import DeskHealthTests
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);f=DeskHealthTests();f.fixture(root)
   f.write(root,'site/data/sports.json',{'updatedAt':boxscores.stamp(NOW),'leagues':{'NBA':{'games':[{'kickoff':'2026-11-06T00:00:00Z'}]}}})
   result=desk_health.summary(root,root/'private',root,NOW)
   self.assertIn('nba-morning-unknown',{r['code'] for r in result['issues']})
