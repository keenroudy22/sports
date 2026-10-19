"""Prospective owner-approved tiers; never promote an already-posted stake."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import pricing
import record_scope
import run
import x_post


class PlayTierTests(unittest.TestCase):
    def setUp(self):
        self.ctx = gates.Context(datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc))
        self.reason = {'type': 'line_move', 'class': 'A', 'direction': 'for', 'text': 'The book moved toward the under.'}

    def pick(self, chance=.53, gap=2, **extra):
        pick = {'id': 'NFL-new', 'league': 'NFL', 'athleteId': '1', 'market': 'rushYds',
                'direction': 'under', 'line': 44.5, 'odds': -110, 'gameIds': ['NFL-game'],
                'selectionPolicy': gates.TIER_POLICY, 'lane': 'best_bet', 'riskUnits': 1,
                '_selection': {'rawChance': .69, 'chance': chance, 'anchoredChance': chance,
                               'fairChance': chance-gap/100, 'gap': gap, 'breakEven': pricing.break_even(-110)},
                '_planReasons': [self.reason]}
        return dict(pick, **extra)

    def test_regular_positive_value_does_not_need_four_points_or_a_spot_sample(self):
        pick = self.pick(chance=.525, gap=.2)
        with patch.object(gates.spot, 'for_candidate', return_value=None):
            decision = run.choose_straight_tier(pick, self.ctx)
        self.assertTrue(decision.ok)
        self.assertEqual((pick['lane'], pick['riskUnits']), ('best_bet', 1))

    def test_chef_preserves_old_strict_gate_and_gets_two_units(self):
        pick = self.pick(chance=.56, gap=6)
        with patch.object(gates.spot, 'for_candidate', return_value={'spotHit': .55, 'n': 40}):
            self.assertTrue(run.choose_straight_tier(pick, self.ctx).ok)
        self.assertEqual((pick['lane'], pick['riskUnits']), ('chef_pick', 2))

    def test_bad_observed_spot_keeps_it_regular_not_chef(self):
        pick = self.pick(chance=.56, gap=6)
        with patch.object(gates.spot, 'for_candidate', return_value={'spotHit': .45, 'n': 40}):
            self.assertTrue(run.choose_straight_tier(pick, self.ctx).ok)
        self.assertEqual((pick['lane'], pick['riskUnits']), ('best_bet', 1))

    def test_negative_value_and_missing_reason_fail_both_tiers(self):
        for pick in (self.pick(chance=.52), self.pick(_planReasons=[])):
            self.assertFalse(run.choose_straight_tier(pick, self.ctx).ok)

    def test_nfl_total_pause_and_strong_nfl_side_reason_remain(self):
        total = self.pick(athleteId=None, market=None, marketType='total')
        self.assertFalse(run.choose_straight_tier(total, self.ctx).ok)
        side = self.pick(athleteId=None, market=None, marketType='spread', direction='away')
        self.assertTrue(run.choose_straight_tier(side, self.ctx).ok)
        self.assertEqual(side['riskUnits'], 1)
        self.assertFalse(run.choose_straight_tier(dict(side, _planReasons=[]), self.ctx).ok)

    def test_legacy_strict_and_half_unit_lanes_are_not_reclassified(self):
        old = self.pick(lane='gut_call', riskUnits=.5)
        old.pop('selectionPolicy')
        self.assertFalse(gates.selection_verdict(old, self.ctx, 'best_bet').ok)
        self.assertTrue(gates.selection_verdict(old, self.ctx, 'gut_call').ok)
        self.assertEqual(old['riskUnits'], .5)
        self.assertEqual(x_post._play_prefix(old, {}, False), '🔥 Full Send: ')

    def test_new_prefixes_override_legacy_featured_label_and_stake_mismatch_is_blocked(self):
        chef = self.pick(lane='chef_pick', riskUnits=2)
        self.assertEqual(x_post._play_prefix(chef, {}, True), "🍳 Chef's Pick: ")
        self.assertEqual(x_post._play_prefix(self.pick(), {}, True), 'Best Bet: ')
        bad = dict(chef, riskUnits=1)
        self.assertIn('play tier and published stake do not match', x_post.guard('Player under 44.5', bad))

    def test_new_chef_counts_in_headline_but_old_half_unit_stays_separate(self):
        base = {'posted': True, 'kickoff': '2026-10-20T00:15Z'}
        self.assertTrue(record_scope.is_headline(dict(base, lane='chef_pick')))
        self.assertFalse(record_scope.is_headline(dict(base, lane='gut_call', riskUnits=.5)))

    def test_revisions_cannot_upgrade_a_published_stake_or_lane(self):
        old = self.pick(lane='gut_call', riskUnits=.5)
        self.ctx.first[old['id']] = old
        self.assertFalse(gates.revision_frozen(dict(old, lane='best_bet', riskUnits=1), self.ctx).ok)

    def test_private_release_rechecks_the_new_tier_at_the_current_price(self):
        pick = self.pick(lane='chef_pick', riskUnits=2, quotedAt='2026-10-19T19:55Z', expiresAt='2026-10-19T21:30Z')
        row = {'pick': pick, 'league': 'NFL', 'decision': {'planReasons': [self.reason]}}
        with patch.object(gates, 'totals_policy', return_value=gates.Decision(True, 'total', 'ok')), \
             patch.object(gates, 'selection_verdict', return_value=gates.Decision(False, 'plan_selection', 'no current exact pair')) as check:
            self.assertIn('no current exact pair', run.private_release_refusal(row, self.ctx, self.ctx.now))
        checked = check.call_args.args[0]
        self.assertNotIn('_selection', checked)
        self.assertEqual(checked['_planReasons'], [self.reason])


if __name__ == '__main__':
    unittest.main()
