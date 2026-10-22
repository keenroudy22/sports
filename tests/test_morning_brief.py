import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import morning_brief as m
import buffer_post as b

class MorningBriefTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,22,11,tzinfo=timezone.utc)
        self.row=dict(league='CFB',title='Example over 40.5',line=40.5,odds=-110,book='FanDuel',
            projection=45,observedAt='2026-10-22T10:45:00Z',kickoff='2026-10-22T23:00:00Z',
            missing='Player/QB availability still needs verification.',day='2026-10-22',
            capturedAt='2026-10-22T11:00:00Z',text='Morning lean')
    def test_current_ignores_malformed_and_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'2026-10-22-1.json').write_text(json.dumps(self.row))
            (root/'2026-10-22-2.json').write_text('{bad')
            (root/'2026-10-22-3.json').write_text(json.dumps(dict(self.row,observedAt='2026-10-21T10:00:00Z')))
            self.assertEqual(m.current(self.now,root),self.row)
            self.assertIsNone(m.current(self.now.replace(hour=16),root))
    def test_official_suppresses_lean(self):
        self.assertIsNone(m.choose(self.now,[],[],{},True))
    def test_climb_and_fun_tickets_do_not_suppress_a_morning_lean(self):
        ticket=('CFB','parlays',dict(parlayType='ladder',legs=[{},{}]))
        self.assertFalse(m.has_official_straight([ticket]))
        self.assertFalse(m.has_official_straight([('NBA','parlays',dict(legs=[{},{}]))]))
        self.assertTrue(m.has_official_straight([ticket,('NFL','picks',dict(id='best'))]))
    def test_catalog_identity_matches_canonical_name_not_wrong_market_or_book(self):
        row=dict(self.row,id='game-NFL-401873010-away-ml',gameId='NFL-401873010',league='NFL',
                 title='NE moneyline',line=0,grade=dict(projection=3.0,calibrated=True,edge=3))
        screen=dict(gameId=row['gameId'],title='New England Patriots MONEYLINE',lineId=row['id'],
                    line=0,book=row['book'],rule='held',reason='availability')
        self.assertIsNotNone(m.choose(self.now,[row],[screen],{}))
        for changed in (dict(screen,lineId='game-NFL-401873010-home-ml'),dict(screen,line=3.5),
                        dict(screen,book='DraftKings'),dict(screen,gameId='NFL-other')):
            self.assertIsNone(m.choose(self.now,[row],[changed],{}))
    def test_unmatched_or_negative_football_not_promoted(self):
        row=dict(self.row,gameId='CFB-1',grade=dict(projection=45,calibrated=True,edge=2))
        self.assertIsNone(m.choose(self.now,[row],[],{}))
        hold=dict(gameId='CFB-1',title=row['title'],rule='held',reason='availability')
        self.assertIn('availability',m.choose(self.now,[row],[hold],{})['missing'])
        row['grade']['edge']=-1
        self.assertIsNone(m.choose(self.now,[row],[hold],{}))
    def test_new_snapshot_can_follow_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as d, patch('line_payload.load',return_value=[]), patch('nba_today.build',return_value={}), patch.object(m,'choose',return_value=self.row):
            self.assertTrue(m.prepare(self.now,[],root=d))
            self.assertTrue(m.prepare(self.now.replace(minute=30),[],root=d))
            self.assertEqual(len(list(Path(d).glob('*.json'))),2)
    def test_no_extra_daily_research_identity(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'2026-10-22.json').write_text(json.dumps(self.row))
            self.assertEqual(m.post(self.now,d)['key'],'research:morning:2026-10-22')
    def test_priority_never_moves_sent_or_official(self):
        rows=[dict(id='p',kind='buffer:play',dueAt='2026-10-22T11:15:00Z',bufferPostId='1'),
              dict(id='r',kind='buffer:research',sentAt='2026-10-22T11:00:00Z',dueAt='2026-10-22T11:15:00Z',bufferPostId='2')]
        with patch.object(b,'graphql',side_effect=AssertionError('must not request')):
            self.assertEqual(b.yield_optional({'posts':rows},self.now.replace(minute=15),self.now,'c'),[])
