import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import futures_store as f


class FuturesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.now=datetime(2026,10,5,tzinfo=timezone.utc)
        self.row=dict(type='quote',watchId='test',league='NBA',season='2026',market='championship',selection='Team',book='FanDuel',jurisdiction='IN',source='https://example.test/evidence',observedAt='2026-10-04T10:00:00Z',odds=500,researchSnapshot={'status':'paper'})
    def test_original_movement_and_settlement_are_separate(self):
        self.assertTrue(f.append(self.row,self.root,self.now));self.assertFalse(f.append(self.row,self.root,self.now))
        f.append(dict(self.row,odds=450,observedAt='2026-10-04T12:00:00Z'),self.root,self.now)
        rows=f.report(self.root)
        self.assertEqual(rows[0]['first']['odds'],500);self.assertEqual(rows[0]['latest']['odds'],450)
        f.append(dict(self.row,type='settlement',result='void',settlementEvidence='Book event cancelled',observedAt='2026-10-04T14:00:00Z'),self.root,self.now)
        with self.assertRaises(ValueError): f.append(dict(self.row,odds=400),self.root,self.now)
    def test_missing_price_snapshot_and_changed_identity_fail(self):
        for delta in ({'odds':None},{'source':''},{'researchSnapshot':{}},{'observedAt':'2099-01-01T00:00:00Z'}):
            with self.assertRaises(ValueError): f.append(dict(self.row,**delta),self.root,self.now)
        f.append(self.row,self.root,self.now)
        with self.assertRaises(ValueError): f.append(dict(self.row,book='DraftKings'),self.root,self.now)
    def test_tampering_is_detected(self):
        f.append(self.row,self.root,self.now)
        p=self.root/'paper.jsonl';p.write_text(p.read_text().replace('500','600'))
        with self.assertRaises(ValueError): f.read(self.root)
