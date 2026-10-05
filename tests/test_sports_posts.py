import sys
import tempfile
import json
import unittest
import os
from unittest.mock import patch
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sports_posts as s
import receipts
import discord_post


class SportsPostsTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,5,21,30,tzinfo=timezone.utc)
        self.game={'id':'NHL-1','league':'NHL','timeConfirmed':True,'kickoff':'2026-10-06T02:00:00Z','status':'scheduled','updatedAt':'2026-10-05T21:00:00Z',
                   'teams':{'away':{'abbreviation':'PHI'},'home':{'abbreviation':'TB'}}}
        self.data={'leagues':{'NHL':{'status':'ok','games':[self.game]}}}
    def test_late_slate_is_factual_short_and_not_a_pick(self):
        row=s.choose(self.data,self.now)
        self.assertIsNotNone(row);self.assertIn('10:00 PM ET',row['text'])
        self.assertNotIn('@Playbook',row['text']);self.assertEqual(receipts.guard(row),[])
        self.assertIn('Schedules, not picks',s.svg(row))
    def test_stale_started_empty_and_late_fail_closed(self):
        self.game['updatedAt']='2026-10-04T10:00:00Z';self.assertIsNone(s.choose(self.data,self.now))
        self.game['updatedAt']='2026-10-05T21:00:00Z';self.game['status']='in_progress';self.assertIsNone(s.choose(self.data,self.now))
        self.assertIsNone(s.choose(self.data,datetime(2026,10,6,1,tzinfo=timezone.utc)))
    def test_freezes_one_card_per_day(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, KEENROUDY_SPORTS_SOCIAL='1'):
            path=Path(folder)/'sports.json';path.write_text(json.dumps(self.data))
            root=Path(folder)/'out'
            self.assertTrue(s.prepare(self.now,path,root));self.assertFalse(s.prepare(self.now,path,root))
            post=s.post(self.now,root);self.assertEqual(post['kind'],'sports')

    def test_website_first_social_hold_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(s.prepare(self.now))
            self.assertIsNone(s.post(self.now))
