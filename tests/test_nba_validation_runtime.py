import copy,json,sys,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import boxscores,nba_capture,nba_validation_runtime as n,nba_prop_release
NOW=datetime(2026,11,4,12,45,tzinfo=timezone.utc)

class CompletionTests(unittest.TestCase):
 def setup_root(self,folder,quote_override=None):
  root=Path(folder);now=boxscores.stamp(NOW)
  injury=dict(season=2027,retrievedAt='2026-11-04T12:05:00Z',official=dict(observedMethod='Reviewed ordinary-browser official PDF',browserPdfSha256='a'*64,reportedAt='2026-11-04T12:30:00Z',retrievedAt='2026-11-04T12:40:00Z',source='https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-04_07_30AM.pdf'))
  boxscores.write_json(root/'injuries-current.json',injury)
  capture=dict(league='NBA',season=2027,slot='2026-11-04T12:00:00Z',retrievedAt='2026-11-04T12:03:00Z',scheduled=True)
  nba_capture.append_changed([capture],root/'observations',lambda r:r['slot'])
  quote=dict(league='NBA',season=2027,eventId='1',athleteId='2',stat='ast',book='DraftKings',sourceAt='2026-11-04T12:35:00Z',retrievedAt='2026-11-04T12:36:00Z',source='https://sharpapi.io',sideVerified=True,kind='main')
  quote.update(quote_override or {})
  nba_capture.append_changed([quote],root/'player-quotes',lambda r:(r['eventId'],r['athleteId'],r['stat'],r['book']))
  return root,injury,capture,quote
 def test_actual_current_completion_is_once_only_and_preserves_frozen_protocol(self):
  before=nba_prop_release.implementation_hash()
  with tempfile.TemporaryDirectory() as folder:
   root,injury,capture,quote=self.setup_root(folder)
   with patch.object(n.props,'record_forward',return_value=3) as record,patch.object(n.props,'grade',return_value=0),patch.object(nba_prop_release,'freeze',return_value=0),patch.object(n.probability,'capture',return_value={'recorded':2}):
    result=n.finish(root,NOW)
    self.assertEqual(result['state'],'completed');self.assertEqual(result['requests'],0)
    self.assertEqual(result['scheduledSlot'],capture['slot']);self.assertEqual(result['retrievedAt'],boxscores.stamp(NOW))
    record.assert_called_once_with(NOW,root,eligible_quotes={('1','2','ast','DraftKings',quote['sourceAt'])})
    self.assertEqual(n.finish(root,NOW+timedelta(minutes=1))['state'],'already-completed');self.assertEqual(record.call_count,1)
   self.assertEqual(nba_prop_release.implementation_hash(),before)
 def test_stale_future_unscheduled_provider_or_missing_pdf_never_create_forecasts(self):
  for case in ('stale-provider','future-report','missing-pdf','stale-quote','unscheduled','before-start'):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as folder:
    root,injury,capture,quote=self.setup_root(folder);clock=NOW
    if case=='stale-provider':injury['retrievedAt']='2026-11-04T08:00:00Z'
    elif case=='future-report':injury['official']['retrievedAt']='2026-11-04T12:46:00Z'
    elif case=='missing-pdf':injury['official'].pop('browserPdfSha256')
    elif case=='stale-quote':quote['sourceAt']='2026-11-04T10:00:00Z'
    elif case=='future-quote':quote['retrievedAt']='2026-11-04T12:46:00Z'
    elif case=='before-report-price':quote['sourceAt']='2026-11-04T12:20:00Z'
    elif case=='unscheduled':capture['scheduled']=False
    else:clock=n.START-timedelta(seconds=1)
    boxscores.write_json(root/'injuries-current.json',injury)
    if case=='unscheduled':
     nba_capture.append_changed([capture],root/'observations',lambda r:r['slot'])
    if 'quote' in case or case=='before-report-price':
     nba_capture.append_changed([quote],root/'player-quotes',lambda r:(r['eventId'],r['athleteId'],r['stat'],r['book']))
    with patch.object(n.props,'record_forward') as record:
     result=n.finish(root,clock);self.assertEqual(result['state'],'held');record.assert_not_called()
 def test_report_published_after_old_price_cannot_supply_price_proof(self):
  with tempfile.TemporaryDirectory() as folder:
   root,injury,capture,quote=self.setup_root(folder,quote_override={'sourceAt':'2026-11-04T12:20:00Z','retrievedAt':'2026-11-04T12:25:00Z'})
   with patch.object(n.props,'record_forward') as record:
    self.assertEqual(n.finish(root,NOW)['state'],'held');record.assert_not_called()
 def test_download_after_report_does_not_refresh_pre_report_price(self):
  with tempfile.TemporaryDirectory() as folder:
   root,_,_,_=self.setup_root(folder,quote_override={'sourceAt':'2026-11-04T12:20:00Z'})
   with patch.object(n.props,'record_forward') as record:
    self.assertEqual(n.finish(root,NOW)['state'],'held');record.assert_not_called()
 def test_source_clock_after_download_cannot_create_evidence(self):
  with tempfile.TemporaryDirectory() as folder:
   root,_,_,_=self.setup_root(folder,quote_override={'sourceAt':'2026-11-04T12:37:00Z'})
   with patch.object(n.props,'record_forward') as record:
    self.assertEqual(n.finish(root,NOW)['state'],'held');record.assert_not_called()
 def test_filter_leaves_ordinary_capture_unchanged_and_never_records_unmatched_quotes(self):
  rows=[]
  for athlete in ('2','3'):
   rows.append(dict(eventId='1',athleteId=athlete,stat='ast',book='DraftKings',sourceAt='2026-11-04T12:35:00Z',
    projection=dict(model='nba-minutes-rate-v1',season=2027,window='This season',value=4),kickoff='2026-11-05T00:00:00Z'))
  with tempfile.TemporaryDirectory() as folder,patch.object(n.props,'build',return_value={'rows':rows}):
   root=Path(folder)
   eligible={('1','2','ast','DraftKings',rows[0]['sourceAt'])}
   self.assertEqual(n.props.record_forward(NOW,root,eligible_quotes=eligible),1)
   self.assertEqual(n.props.record_forward(NOW,root,eligible_quotes=eligible),0)
   self.assertEqual([r['athleteId'] for r in n.probability.read(root/'player-forecasts')],['2'])
   self.assertEqual(n.props.record_forward(NOW,root),1)
