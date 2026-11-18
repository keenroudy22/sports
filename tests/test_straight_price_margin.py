"""Regression for the Nov 18 UMass admission and the queued-release price recheck."""
import unittest
from datetime import timedelta
from unittest.mock import patch

from test_moneyline_projection_agreement import gates, inputs
import run


class StraightPriceMarginTests(unittest.TestCase):
    def setUp(self):
        self.pick, self.ctx = inputs(home=.32, margin=-7)
        self.pick.update(league='CFB', odds=-170, lane='best_bet', riskUnits=1)
        self.numbers = dict(rawChance=.684, fairChance=.604, anchoredChance=.632,
                            breakEven=.63, gap=2.8)
        self.pick['_selection'] = self.numbers
        self.ctx.now = gates.STRAIGHT_PRICE_MARGIN_FROM

    def test_original_admission_and_prospective_refusal(self):
        self.ctx.now -= timedelta(seconds=1)
        self.assertTrue(gates.selection_verdict(self.pick, self.ctx).ok)
        self.ctx.now += timedelta(seconds=1)
        for lane in ('best_bet', 'chef_pick'):
            decision = gates.selection_verdict(self.pick, self.ctx, lane)
            self.assertEqual(decision.rule, 'straight_price_margin')
            self.assertIn('0.24 points', decision.reason)

    def test_minimum_margin_uses_offered_odds_even_with_stale_cached_break_even(self):
        for odds, points in ((-110, 2), (-150, 2), (-151, 3), (-170, 3), (125, 2)):
            self.pick['odds'] = odds
            minimum = gates.pricing.break_even(odds) + points / 100
            self.numbers.update(anchoredChance=minimum - .00001, breakEven=.35)
            self.assertFalse(gates.selection_verdict(self.pick, self.ctx).ok)
            self.numbers['anchoredChance'] = minimum
            self.assertTrue(gates.selection_verdict(self.pick, self.ctx).ok)

    def test_site_keeps_original_odds_and_withholds_unearned_live_price_guidance(self):
        import build_site
        pick = dict(marketType='moneyline', odds=-170, probabilityAtPublication=self.numbers,
                    cutoff=gates.pricing.cutoff('moneyline', 'home', 0, -170))
        self.assertEqual(build_site.cutoff_fields(pick)['cutoffOdds'], -184)
        held = build_site.cutoff_fields(pick, current_straight=True)
        self.assertTrue(held['priceMarginHold'])
        self.assertIsNone(held['cutoff'])
        self.assertIsNone(held['cutoffOdds'])
        self.numbers['anchoredChance'] = .68
        self.assertEqual(build_site.cutoff_fields(pick, current_straight=True)['cutoffOdds'], -170)
        pick['cutoff'] = gates.pricing.cutoff('moneyline', 'home', 0, -170, price_tolerance=1)
        self.assertEqual(build_site.cutoff_fields(pick)['cutoffOdds'], -170)

    def test_private_release_discards_old_approval_and_checks_actual_price(self):
        self.pick.update(quotedAt='2026-11-18T19:00:00Z', expiresAt='2026-11-18T19:30:00Z')
        self.pick['_selection'] = {**self.numbers, 'anchoredChance': .70}
        row = dict(pick=self.pick, league='CFB', decision={'planReasons': self.pick['_planReasons']})
        ok = gates.Decision(True, 'test', '')
        with patch.object(gates, 'daily_exposure', return_value=ok), \
             patch.object(gates, 'fresh_quote', return_value=ok), \
             patch.object(gates, 'exact_price_pairs', return_value=[dict(book=self.pick['book'], side=-170)]), \
             patch.object(gates, 'selection_numbers', return_value=self.numbers) as rebuild:
            self.assertIn('0.24 points', run.private_release_refusal(row, self.ctx, self.ctx.now))
        self.assertNotIn('_selection', rebuild.call_args.args[0])
