import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_capture
import nba_official_availability as official

NOW=datetime(2026,10,30,17,15,tzinfo=timezone.utc)
PDF='https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-30_01_00PM.pdf'
OLD=PDF.replace('01_00PM','06_00AM')
TEXT='''Injury Report: 10/30/26 01:00 PM
Game Date    Game Time    Matchup    Team    Player Name    Current Status    Reason
10/30/2026    07:30 (ET)    BKN@BOS    Brooklyn Nets    None
    Boston Celtics    None
'''
GAME=dict(providerId='1',season=2027,kickoff='2026-10-30T23:30:00Z',teams={
    'away':dict(id='17',name='Brooklyn Nets',abbreviation='BKN'),
    'home':dict(id='2',name='Boston Celtics',abbreviation='BOS')})

class PublishedReportTests(unittest.TestCase):
    def test_selects_newest_actual_link_not_guessed_previous_quarter(self):
        html=f'<a href="{OLD}">old</a><a href="{PDF}">report</a>'
        source,at=official.published_report(html,NOW+timedelta(minutes=15))
        self.assertEqual(source,PDF)
        self.assertEqual(at,NOW-timedelta(minutes=15))
        self.assertNotEqual(source,official.report_url(NOW+timedelta(minutes=15))[0])

    def test_filters_foreign_links_queries_fragments_invalid_times_and_nonanchors(self):
        bad=[PDF.replace('ak-static.cms.nba.com','evil.invalid'),PDF+'?secret=1',PDF+'#x',PDF.replace('01_00PM','99_99PM'),'http:'+PDF[6:]]
        html=''.join(f'<a href="{x}">no</a>' for x in bad)+f'<script>"{PDF}"</script>'
        with self.assertRaises(official.PublishedReportUnavailable):official.published_report(html,NOW)

    def test_stale_future_and_empty_listings_never_fetch_pdf(self):
        for href in (OLD,PDF.replace('01_00PM','02_00PM'),''):
            calls=[]
            def fetch(url):calls.append(url);return f'<a href="{href}">report</a>'
            budget=nba_capture.Budget(fetch=fetch,sleep=lambda _:None)
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(official.PublishedReportUnavailable):official.capture(budget,[GAME],root,NOW,clock=lambda:NOW)
            self.assertEqual(calls,[official.index_url(NOW)])

    def test_linked_pdf_uses_one_shared_budget_and_preserves_real_report_clock(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            return f'<a href="{PDF}">report</a>' if url==official.index_url(NOW) else b'%PDF-1.4'
        budget=nba_capture.Budget(requests=2,fetch=fetch,sleep=lambda _:None)
        with tempfile.TemporaryDirectory() as root,patch.object(official,'extract',return_value=TEXT):
            result=official.capture(budget,[GAME],root,NOW,clock=lambda:NOW)
        self.assertEqual(calls,[official.index_url(NOW),PDF])
        self.assertEqual(result['reportedAt'],'2026-10-30T17:00:00Z')
        self.assertFalse(official.merge([],result,[GAME])['1']['teamHolds'])
        self.assertEqual(result['discovery']['source'],official.index_url(NOW))
        with self.assertRaises(TimeoutError):budget(nba_capture.INJURIES)

    def test_pdf_clock_must_match_selected_link_without_retry(self):
        calls=[]
        def fetch(url):calls.append(url);return f'<a href="{PDF}">report</a>' if not url.endswith('.pdf') else b'%PDF-1.4'
        with tempfile.TemporaryDirectory() as root,patch.object(official,'extract',return_value=TEXT.replace('01:00 PM','12:45 PM')):
            with self.assertRaises(ValueError):official.capture(nba_capture.Budget(fetch=fetch,sleep=lambda _:None),[GAME],root,NOW,clock=lambda:NOW)
        self.assertEqual(sum(x.endswith('.pdf') for x in calls),1)

    def test_index_domain_size_and_request_limits_are_enforced(self):
        budget=nba_capture.Budget(fetch=lambda _:'x'*1_000_001,sleep=lambda _:None)
        with self.assertRaises(ValueError):budget.report_index(official.index_url(NOW))
        budget=nba_capture.Budget(fetch=lambda _:'<html></html>',sleep=lambda _:None)
        for url in ('https://evil.invalid/index','https://keenroudy.com/sports/','https://official.nba.com/other',official.index_url(NOW)+'?x=1'):
            with self.assertRaises(ValueError):budget.report_index(url)
        self.assertEqual(budget.requests,0)

    def test_stale_listing_failure_records_latest_actual_clock_not_false_healthy_report(self):
        with self.assertRaises(official.PublishedReportUnavailable) as caught:official.published_report(f'<a href="{OLD}">old</a>',NOW)
        result=official.failure(caught.exception,NOW)
        self.assertEqual(result['state'],'unavailable')
        self.assertEqual(result['source'],official.index_url(NOW))
        self.assertEqual(result['latestPublishedAt'],'2026-10-30T10:00:00Z')
        self.assertNotIn('teams',result)

    def test_native_reader_identifies_itself_and_rejects_foreign_redirect(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.__enter__.return_value=response
        response.read.return_value=b'<html></html>';response.geturl.return_value=official.index_url(NOW)+'/'
        with patch.object(nba_capture,'urlopen',return_value=response) as opened:
            budget=nba_capture.Budget(sleep=lambda _:None)
            self.assertEqual(budget.report_index(official.index_url(NOW)),'<html></html>')
            request=opened.call_args.args[0]
            self.assertEqual(request.full_url,official.index_url(NOW))
            self.assertIn('KooknResearch/1.0',request.get_header('User-agent'))
            self.assertEqual(budget.requests,1)
        response.geturl.return_value='https://evil.invalid/'
        with patch.object(nba_capture,'urlopen',return_value=response):
            with self.assertRaises(ValueError):nba_capture.Budget(sleep=lambda _:None).report_index(official.index_url(NOW))

    def test_season_page_tracks_october_boundary(self):
        self.assertTrue(official.index_url(NOW).endswith('2026-27-season'))
        self.assertTrue(official.index_url(datetime(2027,3,1,tzinfo=timezone.utc)).endswith('2026-27-season'))

    def test_old_captures_keep_the_original_single_report_protocol(self):
        self.assertGreater(official.PUBLISHED_LINKS_FROM,datetime(2026,10,29,23,tzinfo=timezone.utc))
        self.assertEqual(official.report_url(datetime(2026,10,27,12,30,tzinfo=timezone.utc))[0].split('_')[-2:],['08','15AM.pdf'])
