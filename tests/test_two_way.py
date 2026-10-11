import copy
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import direction
import learn
import learning
import two_way


NOW = datetime(2026, 10, 13, 12, 30, tzinfo=timezone.utc)


def rows(n, wins, segment='NFL/total', clv=-.2, rules=()):
    out = []
    for i in range(n):
        out.append({'id': f'p{i}', 'segment': segment, 'league': segment.split('/')[0],
                    'gameIds': [f'g{i}'], 'direction': 'over', 'decision': 'published',
                    'decidedAt': f'2026-10-{(i % 9) + 1:02d}T12:00:00Z', 'odds': -110,
                    'result': 'win' if i < wins else 'loss', 'clv': clv, 'rules': list(rules)})
    return out


class TwoWayLearningTests(unittest.TestCase):
    def test_bad_price_role_and_25_point_gap_rows_never_train(self):
        dirty = rows(3, 3)
        dirty[0]['rules'] = ['role_sanity']
        dirty[1]['rules'] = ['price-sanity']
        dirty[2]['gap'] = 25
        self.assertEqual(two_way.distinct(dirty), [])

    def test_a_signal_waits_for_two_consecutive_tuesdays_and_moves_both_ways(self):
        policy = learning.default_policy()
        losing = rows(50, 15)
        found, applied = two_way.step(policy, losing, NOW)
        self.assertTrue(found)
        self.assertEqual(applied, [])
        self.assertIn('trust:NFL/total', policy['twoWay']['pending'])
        _, applied = two_way.step(policy, losing, NOW + timedelta(days=7))
        self.assertEqual([row['undoKey'] for row in applied], ['trust:NFL/total', 'gap:NFL/total'])
        self.assertEqual(two_way.trust(policy, 'NFL/total'), .95)
        self.assertEqual(two_way.gap_floor(policy, 'NFL/total'), 2)

        winning = rows(50, 35, clv=.2)
        two_way.step(policy, winning, NOW + timedelta(days=14))
        _, eased = two_way.step(policy, winning, NOW + timedelta(days=21))
        self.assertIn('trust:NFL/total', [row['undoKey'] for row in eased])
        self.assertIn('gap:NFL/total', [row['undoKey'] for row in eased])
        self.assertGreater(two_way.trust(policy, 'NFL/total'), .95)
        self.assertEqual(two_way.gap_floor(policy, 'NFL/total'), 0)

    def test_pause_uses_60_rows_and_negative_80_percent_upper_bound(self):
        policy = learning.default_policy()
        sample = rows(60, 20)
        two_way.step(policy, sample, NOW)
        _, applied = two_way.step(policy, sample, NOW + timedelta(days=7))
        self.assertIn('pause:NFL/total', [row['undoKey'] for row in applied])
        self.assertTrue(direction.paused(policy, 'NFL/total', NOW + timedelta(days=7)))

    def test_kill_switch_observes_without_saving_pending_or_moving(self):
        policy = learning.default_policy()
        with mock.patch.dict(os.environ, {'KEENROUDY_TWO_WAY_LEARNING': '0'}):
            found, applied = two_way.step(policy, rows(50, 15), NOW)
        self.assertTrue(found)
        self.assertEqual(applied, [])
        self.assertEqual(policy.get('twoWay', {}).get('pending'), {})

    def test_reason_weight_can_turn_off_and_back_on_only_after_confirmation(self):
        policy = learning.default_policy()
        bad = rows(80, 20, segment='NFL/prop:recYds')
        for row in bad:
            row['reasons'] = [{'type': 'stats'}]
        two_way.step(policy, bad, NOW)
        _, applied = two_way.step(policy, bad, NOW + timedelta(days=7))
        self.assertIn('reason:stats', [row['undoKey'] for row in applied])
        self.assertEqual(policy['reasonWeights']['stats'], 0)

        good = rows(60, 40, segment='NFL/prop:recYds', clv=.2)
        for row in good:
            row['reasons'] = [{'type': 'stats'}]
        two_way.step(policy, good, NOW + timedelta(days=14))
        _, applied = two_way.step(policy, good, NOW + timedelta(days=21))
        self.assertIn('reason:stats', [row['undoKey'] for row in applied])
        self.assertGreater(policy['reasonWeights']['stats'], 0)

    def test_saved_plan_reasons_train_the_reason_weight(self):
        policy = learning.default_policy()
        bad = rows(80, 20, segment='NFL/prop:recYds')
        for row in bad:
            row['planReasons'] = [{'type': 'stats'}]
        two_way.step(policy, bad, NOW)
        _, applied = two_way.step(policy, bad, NOW + timedelta(days=7))
        self.assertIn('reason:stats', [row['undoKey'] for row in applied])
        self.assertEqual(policy['reasonWeights']['stats'], 0)

    def test_tuesday_note_is_ten_lines_and_names_undo_keys_or_the_hold(self):
        report = {'graded': 50, 'segments': [{'published': {'graded': 20}}],
                  'engagementScorecard': {'measuredPosts': 8, 'overall': {'perThousand': 5.2},
                                          'byKind': {'play': {'perThousand': 6.1}, 'research': {'perThousand': 2.0}}},
                  'direction': {'applied': [], 'standing': []}, 'weekLanes': {}, 'climb': {},
                  'twoWay': {'applied': [], 'pending': {'trust:NFL/total': {'sentence': 'wait'}}, 'disabled': False}}
        note = learn.owner_note(report, NOW)
        self.assertEqual(len(note.strip().splitlines()), 10)
        self.assertIn('second Tuesday', note)
        self.assertIn('Owner needed:', note)
        self.assertIn('Audience:', note)

    def test_policy_loader_and_readers_clamp_hand_edited_values(self):
        policy = learning.default_policy()
        policy['twoWay'] = {'segments': {'NFL/total': {'trust': 9, 'gapFloor': 99, 'paused': True}}}
        self.assertEqual(two_way.trust(policy, 'NFL/total'), 1.25)
        self.assertEqual(two_way.gap_floor(policy, 'NFL/total'), 10)
        self.assertTrue(direction.paused(policy, 'NFL/total', NOW))
        self.assertEqual(direction.edge_raise(policy, 'NFL/total', NOW), 10)

    def test_research_order_needs_eight_posts_and_grades_then_two_tuesdays(self):
        policy = learning.default_policy()
        posts = []
        grades = []
        for kind, hits, acts in (('prep', 4, 1), ('season', 7, 2)):
            for i in range(8):
                posts.append({'id': f'research:{kind}:d{i}', 'metrics': {'impressions': 100, 'likes': acts}})
                grades.append({'id': f'research:{kind}:d{i}', 'result': 'win' if i < hits else 'loss'})
        found, applied = two_way.step(policy, [], NOW, log_book={'posts': posts}, research_grades=grades)
        self.assertIn('research-order', [row['key'] for row in found])
        self.assertEqual(applied, [])
        _, applied = two_way.step(policy, [], NOW + timedelta(days=7),
                                  log_book={'posts': posts}, research_grades=grades)
        self.assertIn('research-order', [row['undoKey'] for row in applied])
        self.assertEqual(policy['twoWay']['researchOrder'][:2], ['season', 'prep'])

    def test_research_order_holds_when_either_evidence_side_is_small(self):
        policy = learning.default_policy()
        posts = [{'id': f'research:prep:d{i}', 'metrics': {'impressions': 100, 'likes': 1}} for i in range(8)]
        self.assertIsNone(two_way.research_signal(policy, {'posts': posts}, []))


if __name__ == '__main__':
    unittest.main()
