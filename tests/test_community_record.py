import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import community_record as record


class CommunityRecordTests(unittest.TestCase):
    def test_actual_cash_at_fifty_dollars_per_unit_never_uses_original_voided_odds(self):
        self.assertEqual(record.accounting({'result':'win','stakeDollars':10,'returnDollars':159.30,'unitDollars':50})['units'], 2.986)
        paid = record.accounting({'result':'win','stakeDollars':15,'returnDollars':83.65,'unitDollars':50,'odds':654})
        self.assertEqual(paid['units'],1.373);self.assertEqual(paid['riskUnits'],.3)
        self.assertEqual(record.accounting({'result':'loss','stakeDollars':5,'returnDollars':0,'unitDollars':50})['units'],-.1)
        self.assertEqual(record.accounting({'result':'void','stakeDollars':5,'returnDollars':5,'unitDollars':50})['units'],0)
        for changes in ({'returnDollars':None},{'unitDollars':0},{'stakeDollars':True},{'returnDollars':-1},{'returnDollars':10}):
            with self.assertRaises(ValueError):
                record.accounting({'result':'win','stakeDollars':10,'returnDollars':159.30,'unitDollars':50}|changes)

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

    def test_personal_straight_keeps_market_and_no_stake_is_inferred(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'data').mkdir()
            ticket = {'id': 'personal-side', 'title': 'James Madison -11.5', 'league': 'CFB',
                      'kind': 'spreads', 'odds': -115, 'personalTicket': True,
                      'kickoff': '2026-10-22T23:00:00Z', 'legs': ['James Madison -11.5']}
            (root / 'data/community.json').write_text(json.dumps({'tickets': [ticket]}))
            post = {'id': ticket['id'], 'sentAt': '2026-10-22T17:00:00Z', 'link': 'https://x.com/a/status/2'}
            (root / 'data/x-posted.json').write_text(json.dumps({'posts': [post]}))
            row = record.build(root)[0]
            self.assertEqual(row['kind'], 'spreads')
            self.assertEqual(row['lane'], 'personal')
            self.assertIsNone(row['riskUnits'])
            self.assertIsNone(row['units'])
            self.assertNotIn('stakeDollars', row)
            # Older one-leg personal darts were stored in the parlay namespace;
            # retain their original prop classification when adding new sides.
            ticket['kind'] = 'parlays'
            (root / 'data/community.json').write_text(json.dumps({'tickets': [ticket]}))
            self.assertEqual(record.build(root)[0]['kind'], 'props')
