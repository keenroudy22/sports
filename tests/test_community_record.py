import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import community_record as record


class CommunityRecordTests(unittest.TestCase):
    def test_pregame_once_separate_no_fabricated_units_and_append_correction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'data').mkdir()
            ticket = {'id': 'ticket', 'title': 'Two-leg ticket', 'league': 'NFL', 'odds': 654,
                      'kickoff': '2026-10-20T00:16:00Z', 'legs': ['A', 'B']}
            (root/'data/community.json').write_text(json.dumps({'tickets': [ticket]}))
            post = {'id': 'ticket', 'sentAt': '2026-10-19T17:00:00Z', 'link': 'https://x.com/a/status/1'}
            (root/'data/x-posted.json').write_text(json.dumps({'posts': [post, post]}))
            journal = root/'data/community-results.jsonl'
            win = {'id': 'ticket', 'result': 'win', 'settledAt': '2026-10-20T12:00:00Z', 'source': 'verified final', 'note': 'One leg voided; adjusted price unknown'}
            self.assertTrue(record.append(win, journal)); self.assertFalse(record.append(win, journal))
            rows = record.build(root)
            self.assertEqual(len(rows), 1); self.assertEqual(rows[0]['result'], 'win')
            self.assertEqual(rows[0]['lane'], 'personal'); self.assertTrue(rows[0]['accountingUnknown'])
            self.assertIsNone(rows[0]['units']); self.assertIsNone(rows[0]['riskUnits'])
            loss = dict(win, result='loss', settledAt='2026-10-20T13:00:00Z')
            record.append(loss, journal)
            self.assertEqual(record.build(root)[0]['result'], 'loss')
            self.assertEqual(len(journal.read_text().splitlines()), 2)
            (root/'data/x-posted.json').write_text(json.dumps({'posts': [dict(post, sentAt='2026-10-20T03:00:00Z')]}))
            self.assertEqual(record.build(root), [])

    def test_incomplete_settlement_rejected(self):
        with self.assertRaises(ValueError):
            record.append({'id': 'x', 'result': 'win'})
