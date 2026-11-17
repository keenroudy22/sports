import copy
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from tests.test_prop_ticket_release import prepared, case
import gates
import nba_fun_record as record
import receipts
import staking


class NbaFunRecordTests(unittest.TestCase):
    def test_receipt_before_publication_and_append_only_graded_correction(self):
        spec, ctx, pick, packet = prepared('NBA-alts')
        admitted = ctx.now
        sent = admitted + timedelta(minutes=1)
        pick['publishedAt'] = gates.stamp(sent)
        post = {'id': pick['id'], 'kind': 'buffer:play', 'bufferPostId': 'queued-only'}
        _, evidence, final = case('NBA-alts')
        packet['settlementEvidence'] = evidence
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'delivery receipt'):
                record.publish(root, pick, [post], sent)
            self.assertFalse((root / record.PATH).exists())
            post['discord'] = {'state': 'sent', 'sentAt': gates.stamp(sent),
                               'messageId': '123456789012345678', 'attachmentState': 'attached',
                               'attachmentReceipt': 'https://cdn.discordapp.com/fixture'}
            self.assertTrue(record.publish(root, pick, [post], sent))
            self.assertFalse(record.publish(root, pick, [post], sent))
            self.assertEqual(record.public_rows(root, [], sent), [])
            [public] = record.public_rows(root, [post], sent)
            self.assertEqual(public['delivery']['discordAt'], gates.stamp(sent))
            self.assertEqual(public['kind'], 'parlays')
            self.assertEqual(receipts.unit_fun_rows(sent, log_book={'posts': [post]}, root=root), [public])
            path = root / record.PATH
            original_bytes = path.read_bytes()
            self.assertNotIn(b'fixture.combined', original_bytes)
            self.assertNotIn(b'attachmentReceipt', original_bytes)
            self.assertNotIn(b'ticketQuote', original_bytes)
            self.assertEqual(staking.external(root, sent)[0][pick['id']]['riskUnits'], .25)
            ctx.risk_external = staking.external(root, sent)[0]
            ctx.now = sent
            self.assertFalse(gates.longshot_one_per_day(dict(pick, id='different'), ctx).ok)
            evidence['legs'][0]['injuryReview'] = 'unknown'
            with self.assertRaisesRegex(ValueError, 'injury/early-exit'):
                record.settle(root, pick['id'], [post], packet, final)
            self.assertEqual(path.read_bytes(), original_bytes)
            evidence['legs'][0]['injuryReview'] = 'clear'
            self.assertTrue(record.settle(root, pick['id'], [post], packet, final))
            self.assertFalse(record.settle(root, pick['id'], [post], packet, final+timedelta(minutes=1)))
            self.assertEqual(record.rows(root, final)[pick['id']]['settlementLegActuals'], [3, 3, 3])
            self.assertIn('points', record.rows(root, final)[pick['id']]['actual'])
            correction = copy.deepcopy(packet)
            correction['settlementEvidence']['legs'][0].update(actual=2, result='loss')
            correction['settlementEvidence']['bookSettlement'].update(result='loss', settledOdds=None)
            corrected = final+timedelta(minutes=2)
            self.assertTrue(record.settle(root, pick['id'], [post], correction, corrected))
            self.assertTrue(path.read_bytes().startswith(original_bytes))
            self.assertEqual(len(path.read_text().splitlines()),3)
            original, first, latest = map(json.loads,path.read_text().splitlines())
            self.assertEqual((original['odds'],first['result'],latest['result']), (425,'win','loss'))
            self.assertEqual(record.rows(root, final)[pick['id']]['result'], 'win')
            self.assertEqual(record.rows(root, corrected)[pick['id']]['units'], -.25)
            self.assertEqual(latest['correctedAt'], gates.stamp(corrected))
