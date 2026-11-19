import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import daily_potd as potd


class DailyPickTests(unittest.TestCase):
    def test_only_reviewed_unsent_original_can_claim_day_and_only_delivery_counts(self):
        now = datetime(2026, 11, 19, 16, tzinfo=timezone.utc)
        orig = dict(id='NBA-original', kickoff='2026-11-20T01:00Z', book='DraftKings', odds=-110, riskUnits=1)
        report = dict(day='2026-11-19', rows=[dict(state='reviewable', terms=orig)])
        decision = dict(state='reviewed', selectedId=orig['id'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            potd.reserve(report, decision, root, now)
            potd.reserve(report, decision, root, now)
            self.assertEqual(potd.designation(orig, root), report['day'])
            other = dict(orig, odds=-114)
            self.assertIsNone(potd.designation(other, root))
            with self.assertRaises(ValueError):
                potd.reserve(dict(report, rows=[dict(state='reviewable', terms=other)]), decision, root, now)
            with self.assertRaises(ValueError):
                potd.reserve(dict(report, rows=[dict(state='public', terms=orig)]), decision, root, now)
            post = dict(id=orig['id'], queuedText='🍳 '+potd.LABEL+'\nThe play')
            potd.mark_delivered([orig], [post], root, now)
            self.assertNotIn('dailyChefDay', orig)
            post['discord'] = dict(state='sent', sentAt=now.isoformat(), messageId='123456789', text=post['queuedText'])
            potd.mark_delivered([orig], [post], root, now)
            self.assertEqual(orig['dailyChefDay'], report['day'])
