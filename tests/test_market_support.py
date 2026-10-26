import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import market_support as ms
import x_post

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
WRONG = 'Dallas expects to recommit to handing the ball to Javonte Williams against Philadelphia.'


class MarketSupportTests(unittest.TestCase):
    def pick(self, **values):
        return dict(athleteId='p', market='rec', publishedAt=NOW.isoformat(), **values)

    def test_real_rushing_claim_is_not_receiving_support(self):
        self.assertFalse(ms.allowed(self.pick(), WRONG))
        self.assertFalse(ms.allowed(dict(athleteId='p', market='rec'), WRONG))
        self.assertFalse(ms.allowed(dict(athleteId='p', market='rec', publishedAt='bad'), WRONG))
        self.assertFalse(ms.allowed(dict(athleteId='p', title='Javonte Williams over 2.5 catches'), WRONG))
        for market in ('rec', 'recYds'):
            self.assertIsNotNone(ms.mismatch(dict(athleteId='p', market=market), 'More rushing attempts are expected.'))

    def test_preserve_relevant_receiving_evidence_and_indirect_context(self):
        for claim in ('Williams has more receiving routes despite fewer carries.',
                      'Dallas expects more checkdowns to Williams.',
                      'Over 2.5 in seven of his last ten games.',
                      'The starting quarterback is healthy.'):
            self.assertTrue(ms.allowed(self.pick(), claim))

    def test_symmetric_stat_mismatches_and_team_plays(self):
        self.assertIsNotNone(ms.mismatch(dict(athleteId='p', market='car'), 'His receiving targets have increased.'))
        self.assertIsNotNone(ms.mismatch(dict(athleteId='p', market='passYds'), 'They expect more rushing attempts.'))
        self.assertIsNone(ms.mismatch(dict(marketType='total'), WRONG))

    def test_original_publication_copy_and_input_stay_unchanged(self):
        pick = self.pick()
        pick['publishedAt'] = '2026-10-26T12:47:22Z'
        original = copy.deepcopy(pick)
        self.assertTrue(ms.allowed(pick, WRONG, NOW))
        self.assertEqual(x_post._choose_reason(pick, WRONG, [], '2026-10-26'), WRONG)
        self.assertEqual(pick, original)

    def test_caption_does_not_shorten_mismatched_claim_into_support(self):
        self.assertIsNone(x_post._choose_reason(self.pick(), WRONG, [], '2026-10-27'))
        claim = 'Williams has run receiving routes on more passing downs this week.'
        self.assertEqual(x_post._choose_reason(self.pick(), claim, [], '2026-10-27'), claim)

    def test_admission_refuses_mismatch_without_raising_probability_floor(self):
        pick = self.pick(league='NFL', odds=110, selectionPolicy=gates.TIER_POLICY,
            _selection=dict(rawChance=.6, anchoredChance=.56, fairChance=.5, gap=6, breakEven=100/210),
            _planReasons=[dict(type='news', direction='for', text=WRONG)])
        ctx = SimpleNamespace(now=NOW)
        result = gates.selection_verdict(pick, ctx, 'best_bet')
        self.assertFalse(result.ok)
        self.assertIn('supporting reason', result.reason)
        pick['_planReasons'][0]['text'] = 'Williams is running more receiving routes.'
        self.assertTrue(gates.selection_verdict(pick, ctx, 'best_bet').ok)
