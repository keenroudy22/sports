import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import buffer_post
import gates
import learn
import learning
import researcher
import run
import x_post
from test_gates import context, prop_lean, total_lean

NOW = datetime(2026, 10, 6, 12, 30, tzinfo=timezone.utc)        # a Tuesday, 8:30 AM ET
RECORD = {'league': 'NFL', 'eventId': '1', 'kickoff': '2026-10-04T17:00Z', 'season': 2026,
          'home': {'score': 27, 'short': 'Lions'}, 'away': {'score': 20, 'short': 'Bills'},
          'market': {'close': {'total': 46.5, 'spread': -3.0}}, 'players': [{'id': '77', 'name': 'Player Seven', 'recYds': 70}]}
GAMES = {'NFL-1': RECORD}
CAPTURES = {'NFL-1': ('2026-10-04T16:00:00Z', {'77': {'recYds': [55.5, 50.5]}})}


def row(i, segment='NFL/total', decision='published', clv=-1.0, result='loss', rules=(), at='2026-09-20T12:00:00Z', **over):
    base = {'id': f'c{i}', 'segment': segment, 'decision': decision, 'rules': list(rules), 'decidedAt': at,
            'result': result, 'clv': clv, 'odds': -110}
    base.update(over)
    return base


class GradeTests(unittest.TestCase):
    def test_a_total_a_spread_and_a_prop_grade_against_the_box_score_and_the_close(self):
        total = learn.grade_row({'marketType': 'total', 'direction': 'over', 'line': 44.5, 'gameIds': ['NFL-1']}, GAMES, CAPTURES)
        self.assertEqual((total['result'], total['value'], total['close'], total['clv']), ('win', 47, 46.5, 2.0))
        spread = learn.grade_row({'marketType': 'spread', 'direction': 'away', 'line': 3.5, 'gameIds': ['NFL-1']}, GAMES, CAPTURES)
        self.assertEqual((spread['result'], spread['close'], spread['clv']), ('loss', 3.0, 0.5), 'away +3.5 in a seven-point loss; the close was +3')
        prop = learn.grade_row({'athleteId': '77', 'market': 'recYds', 'direction': 'over', 'line': 49.5, 'gameIds': ['NFL-1']}, GAMES, CAPTURES)
        self.assertEqual((prop['result'], prop['value'], prop['close'], prop['clv']), ('win', 70, 55.5, 6.0))
        self.assertIsNone(learn.grade_row({'marketType': 'total', 'line': 40, 'direction': 'over', 'gameIds': ['NFL-9']}, GAMES, CAPTURES))
        self.assertIsNone(learn.grade_row({'legs': [{}], 'gameIds': ['NFL-1']}, GAMES, CAPTURES), 'tickets are graded by the settle step')

    def test_grade_pending_grades_each_candidate_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            learning.append('candidates', 2026, [{'id': 'a', 'marketType': 'total', 'direction': 'over', 'line': 44.5, 'gameIds': ['NFL-1'], 'decision': 'refused'},
                                                  {'id': 'a', 'marketType': 'total', 'direction': 'over', 'line': 44.5, 'gameIds': ['NFL-1'], 'decision': 'published'},
                                                  {'id': 'b', 'marketType': 'total', 'direction': 'under', 'line': 44.5, 'gameIds': ['NFL-9'], 'decision': 'refused'}], root)
            self.assertEqual(learn.grade_pending(NOW, root, GAMES, CAPTURES), 1, 'b has not finished')
            self.assertEqual(learn.grade_pending(NOW, root, GAMES, CAPTURES), 0)
            rows = {r['id']: r for r in learn.joined(root)}
            self.assertEqual(rows['a']['decision'], 'published', 'published if it ever was')
            self.assertEqual(rows['a']['result'], 'win')
            self.assertNotIn('result', rows['b'])


class SegmentTests(unittest.TestCase):
    def test_losing_to_the_close_makes_a_segment_pickier_then_pauses_it(self):
        policy = learning.default_policy()
        losing = [row(i, clv=-1.0 + 0.1 * (i % 3)) for i in range(30)]
        _, changes = learn.learn_segments(policy, losing, NOW)
        self.assertEqual([(c['knob'], c['to']) for c in changes], [('lean.minEdge', 1.5)])
        self.assertEqual(learn.learn_segments(policy, losing, NOW)[1], [], 'judged again only on what came after the change')
        later = [row(i, clv=-1.0, at='2026-10-07T12:00:00Z') for i in range(30)]
        for _ in range(3):
            learn.learn_segments(policy, [dict(r, decidedAt=learning.stamp(NOW + timedelta(days=1))) for r in later], NOW)
        self.assertEqual(learning.threshold(policy, 'lean.minEdge', 'NFL/total'), 3.0)
        _, changes = learn.learn_segments(policy, [dict(r, decidedAt=learning.stamp(NOW + timedelta(days=9))) for r in later], NOW + timedelta(days=8))
        self.assertEqual(changes[0]['knob'], 'paused')
        self.assertTrue(learning.paused(policy, 'NFL/total'))

    def test_a_paused_segment_reopens_when_what_it_refused_beats_the_close(self):
        policy = learning.default_policy()
        learning.set_paused(policy, 'NFL/total', True, 'x', {}, NOW)
        refused = [row(i, decision='refused', rules=['learned_pause'], clv=1.0 + 0.1 * (i % 2), result='win',
                       at=learning.stamp(NOW + timedelta(days=1))) for i in range(30)]
        _, changes = learn.learn_segments(policy, refused, NOW + timedelta(days=7))
        self.assertEqual((changes[0]['knob'], changes[0]['to']), ('paused', False))

    def test_easing_back_needs_the_plays_and_the_near_misses_to_beat_the_close_and_stops_at_the_written_rule(self):
        policy = learning.default_policy()
        learning.move(policy, 'NFL/total', 'minEdge', 'lean.minEdge', +1, 'x', {}, NOW - timedelta(days=30))
        at = learning.stamp(NOW - timedelta(days=10))
        winning = [row(i, clv=0.8 + 0.1 * (i % 3), result='win', at=at) for i in range(30)]
        near = [row(100 + i, decision='refused', rules=['lean_edge'], clv=0.5, result='win', at=at) for i in range(20)]
        self.assertEqual(learn.learn_segments(policy, winning, NOW)[1], [], 'no near misses, no easing')
        _, changes = learn.learn_segments(policy, winning + near, NOW)
        self.assertEqual((changes[0]['from'], changes[0]['to']), (1.5, 1.0))
        again = [dict(r, decidedAt=learning.stamp(NOW + timedelta(days=1))) for r in winning + near]
        self.assertEqual(learn.learn_segments(policy, again, NOW + timedelta(days=7))[1], [], 'never below the written rule')

    def test_rows_refused_for_other_reasons_are_not_near_misses(self):
        policy = learning.default_policy()
        findings, _ = learn.learn_segments(policy, [row(1, decision='refused', rules=['one_book', 'lean_edge'])], NOW, dry=True)
        self.assertEqual(findings[0]['nearMisses']['graded'], 0)


class CalibrationTests(unittest.TestCase):
    def rows(self, n, raw, hit_every):
        return [{'league': 'NFL', 'market': 'recYds', 'kickoff': f'2026-09-{1 + i % 28:02d}T17:00Z', 'raw': raw, 'won': i % hit_every == 0}
                for i in range(n)]

    def test_an_overconfident_record_ships_a_shrink_and_a_calibrated_one_does_not(self):
        policy = learning.default_policy()
        overconfident = self.rows(400, 0.70, 2)                  # says 70%, comes in 50%
        findings, changes = learn.learn_calibration(policy, overconfident, NOW)
        self.assertEqual(len(changes), 1)
        self.assertLess(policy['calibration']['NFL/prop']['k'], 0.2)
        self.assertGreater(findings[0]['heldOut']['k'], findings[0]['heldOut']['raw'])
        honest = learning.default_policy()
        calibrated = [dict(r, raw=0.75, won=(i % 4 != 0)) for i, r in enumerate(self.rows(400, 0.75, 1))]
        self.assertEqual(learn.learn_calibration(honest, calibrated, NOW)[1], [], 'raw already right: nothing to fix')
        few = learning.default_policy()
        findings, changes = learn.learn_calibration(few, self.rows(100, 0.7, 2), NOW)
        self.assertEqual(changes, [])
        self.assertIn('needs 300', findings[0]['note'])


class OtherLearningTests(unittest.TestCase):
    def test_sites_that_keep_checking_out_are_preferred_and_the_rest_avoided(self):
        policy = learning.default_policy()
        rows = [{'research': [{'domain': 'nfl.com', 'verified': True}] * 6 + [{'domain': 'rumors.example', 'verified': False}] * 5
                 + [{'domain': 'once.example', 'verified': False}]}]
        table, changes = learn.learn_domains(policy, rows, NOW)
        self.assertEqual(policy['researcher'], {'preferDomains': ['nfl.com'], 'avoidDomains': ['rumors.example']})
        self.assertEqual(table['nfl.com']['rate'], 1.0)
        prompt = researcher.prompt_for({'away': {'name': 'Bills'}, 'home': {'name': 'Lions'}, 'league': 'NFL', 'kickoff': 'k'}, 'total', 'over', policy)
        self.assertIn('worth trying first: nfl.com', prompt)
        self.assertIn('do not use them: rumors.example', prompt)

    def test_reason_weights_follow_engagement_within_bounds(self):
        policy = learning.default_policy()
        posts = ([{'kind': 'buffer:play', 'reasonKind': 'injury', 'metrics': {'impressions': 1000, 'reactions': 40}}] * 8
                 + [{'kind': 'buffer:play', 'reasonKind': 'market', 'metrics': {'impressions': 1000, 'likes': 10}}] * 8)
        table, changes = learn.learn_reasons(policy, {'posts': posts}, NOW)
        self.assertEqual(table['injury']['perThousand'], 40.0)
        self.assertGreater(policy['reasonWeights']['injury'], 1.0)
        self.assertLess(policy['reasonWeights']['market'], 1.0)
        self.assertGreaterEqual(policy['reasonWeights']['market'], 0.8)
        self.assertLessEqual(policy['reasonWeights']['injury'], 1.25)
        quiet = learning.default_policy()
        self.assertEqual(learn.learn_reasons(quiet, {'posts': posts[:3]}, NOW)[1], [], 'too few posts to move anything')

    def test_engagement_by_kind_of_post_and_hour_is_reported_not_acted_on(self):
        posts = [{'kind': 'buffer:play', 'sentAt': '2026-09-26T16:00:05Z', 'metrics': {'impressions': 1000, 'reactions': 30}},     # noon ET
                 {'kind': 'buffer:receipt', 'sentAt': '2026-09-26T13:00:05Z', 'metrics': {'impressions': 500, 'likes': 5}},       # 9 AM ET
                 {'kind': 'buffer:cashed', 'sentAt': '2026-09-26T23:40:00Z', 'metrics': {'impressions': 800, 'reposts': 16}},     # 7:40 PM ET
                 {'kind': 'buffer:play', 'sentAt': '2026-09-26T16:10:05Z'},                                                        # no metrics yet
                 {'kind': 'pick', 'postedAt': '2026-09-19T12:30:00Z'}]
        times = learn.post_times({'posts': posts})
        self.assertEqual(times['byKind'], {'cashed': {'posts': 1, 'perThousand': 20.0}, 'play': {'posts': 1, 'perThousand': 30.0},
                                           'receipt': {'posts': 1, 'perThousand': 10.0}})
        self.assertEqual(list(times['byHour']), ['9 to 11 AM', '11 AM to 2 PM', 'after 6 PM'])
        shell = {'at': '2026-10-06T12:30:00Z', 'candidates': 0, 'graded': 0, 'changes': [], 'segments': {}, 'calibration': {},
                 'gates': {}, 'judge': {}, 'researcher': {}, 'posts': {}, 'model': {}, 'postTimes': times}
        self.assertIn('## Which posts and which hours', learn.markdown(shell))
        self.assertIn('- cashed: 1 posts, 20.0 engagements per thousand views', learn.markdown(shell))

    def test_the_week_writes_the_policy_and_a_plain_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            learning.append('candidates', 2026, [{'id': 'a', 'segment': 'NFL/total', 'marketType': 'total', 'direction': 'over', 'line': 44.5,
                                                  'gameIds': ['NFL-1'], 'decision': 'published', 'rules': [], 'decidedAt': '2026-10-04T12:00:00Z', 'odds': -110}], root)
            report = learn.weekly(NOW, dry=True, root=root, log_book={'posts': []}, games=GAMES)
            self.assertFalse((root / 'policy.json').exists(), 'a dry week changes nothing')
            report = learn.weekly(NOW, root=root, log_book={'posts': []}, games=GAMES)
            self.assertTrue((root / 'policy.json').exists())
            text = (root / 'REPORT.md').read_text()
            self.assertIn('What the kitchen learned', text)
            self.assertIn('NFL/total', text)
            self.assertEqual(report['graded'], 1)


class GateTests(unittest.TestCase):
    def test_learned_thresholds_pause_and_calibration_in_the_gates(self):
        self.assertTrue(gates.lean_edge(total_lean(), context()).ok, 'the written rule by default')
        stricter = learning.default_policy()
        stricter['segments']['NFL/total'] = {'minEdge': 3.0}
        refused = gates.lean_edge(total_lean(), context(policy=stricter))
        edge = gates.lean_edge(total_lean(), context()).data['edgePoints']
        self.assertEqual(refused.ok, edge >= 3.0)
        stopped = learning.default_policy()
        stopped['segments']['NFL/total'] = {'paused': True, 'since': '2026-10-06T12:30:00Z'}
        self.assertFalse(gates.learned_pause(total_lean(), context(policy=stopped)).ok)
        self.assertTrue(gates.learned_pause(total_lean(), context()).ok)
        self.assertTrue(gates.prop_calibrated_value(prop_lean(), context()).ok, 'no calibration yet: the written rule alone')
        shrunk = learning.default_policy()
        shrunk['calibration']['NFL/prop'] = {'k': 0.02, 'n': 538}
        verdict = gates.prop_calibrated_value(prop_lean(), context(policy=shrunk))
        self.assertFalse(verdict.ok)
        self.assertIn('538 graded projections', verdict.reason)
        shrunk['calibration']['NFL/prop']['k'] = 1.0
        self.assertTrue(gates.prop_calibrated_value(prop_lean(), context(policy=shrunk)).ok)
        props = learning.default_policy()
        props['segments'][learning.segment_of(prop_lean())] = {'minEdge': 12.0}
        self.assertIn('needs +12', gates.prop_raw_edge(prop_lean(), context(policy=props)).reason if not gates.prop_raw_edge(prop_lean(), context(policy=props)).ok else 'needs +12')


class RecordTests(unittest.TestCase):
    def test_a_decision_record_carries_the_numbers_the_verdict_and_the_sources(self):
        ctx = context()
        candidate = total_lean(_desk={'projection': 48.0, 'chance': 0.55, 'rawChance': 0.6, 'breakEven': 0.524, 'edgePoints': 2.6, 'evPerUnit': 0.05},
                               _evidence=[{'kind': 'weather', 'direction': 'for'}, {'kind': 'injury', 'direction': 'against'}],
                               _verdict={'argues_against': False, 'confidence': 'high', 'fact_ids': ['f1']},
                               _research=[{'source': 'https://www.nfl.com/news/x', 'verified': True, 'kind': 'injury', 'direction': 'for'}])
        rec = run.decision_record(candidate, 'NFL', 'refused', ['lean_daily_cap'], 'cap', NOW, ctx)
        self.assertEqual((rec['segment'], rec['kind'], rec['edgePoints'], rec['decision']), ('NFL/total', 'team', 2.6, 'refused'))
        self.assertEqual(rec['facts'], {'for': 1, 'against': 1, 'kinds': ['injury', 'weather']})
        self.assertEqual(rec['judge'], {'against': False, 'confidence': 'high', 'facts': 1})
        self.assertEqual(rec['research'], [{'domain': 'nfl.com', 'verified': True, 'kind': 'injury', 'direction': 'for'}])
        self.assertEqual(rec['kickoff'], '2026-09-27T17:00Z')
        json.dumps(rec)

    def test_remember_writes_only_changed_decisions_and_never_fails_the_run(self):
        written = []
        rec = {'id': 'a', 'season': 2026, 'decision': 'refused', 'rules': ['lean_edge']}
        slot = datetime(2026, 10, 5, 17, 30, tzinfo=gates.EASTERN)
        with mock.patch.object(learning, 'read', return_value=[dict(rec)]), \
                mock.patch.object(learning, 'append', side_effect=lambda kind, season, rows: written.extend(rows) or len(rows)), \
                mock.patch.object(learn, 'grade_pending', return_value=0):
            status = {'errors': []}
            run.remember([rec, dict(rec, id='b')], NOW, slot, status)
        self.assertEqual([r['id'] for r in written], ['b'], 'a was already on record with the same decision')
        with mock.patch.object(learning, 'read', side_effect=OSError('disk')):
            status = {'errors': []}
            run.remember([rec], NOW, slot, status)
        self.assertIn('learning: OSError', status['errors'][0])


class PostTests(unittest.TestCase):
    def test_reason_kinds_and_weights(self):
        self.assertEqual(x_post.reason_kind('Denver is without WR Marvin Mims Jr. on the inactive list.'), 'injury')
        self.assertEqual(x_post.reason_kind('Saturday is forecast sunny and 68 with no wind called out.'), 'weather')
        self.assertEqual(x_post.reason_kind('The total opened 50.5 and is 44.5 at DraftKings.'), 'market')
        self.assertEqual(x_post.reason_kind(None), 'none')
        text = '🍳 TEAM PROP\nA at B OVER 40.5\n-110 at DraftKings · 1 unit\n\nOur number 44 vs the 40.5\nWind is calm in town.\n\n@Playbook #NFL'
        self.assertEqual(x_post.reason_in(text), 'Wind is calm in town.')
        self.assertIsNone(x_post.reason_in('🍳 TEAM PROP\nA\n-110\n\nOur number 44 vs the 40.5\n\n@Playbook #NFL'))
        pick = {'why': 'Kentucky lists 5 players out. The tight end has drawn 7 targets in each of his last 2 games.'}
        self.assertEqual(x_post.reason_kind(x_post.reason_for(pick, {'role': 1.0, 'injury': 1.0})), 'role', 'most specific wins at equal weight')
        self.assertEqual(x_post.reason_kind(x_post.reason_for(pick, {'role': 0.8, 'injury': 1.25})), 'injury', 'engagement tips it')
        moved = {'why': 'The total opened 50.5 and is now 44.5 at DraftKings, a move of 6 toward the under.'}
        self.assertIsNone(x_post.reason_for(moved), "a line's move is never a post's reason")

    def test_engagement_is_read_once_two_days_after_and_a_missing_permission_is_said_once(self):
        sent = learning.stamp(NOW - timedelta(days=3))
        log_book = {'posts': [{'id': 'a', 'bufferPostId': 'bp1', 'sentAt': sent}, {'id': 'b', 'bufferPostId': 'bp2', 'sentAt': learning.stamp(NOW)}]}
        calls = []

        def send(url, body, headers):
            calls.append(body['variables']['id'])
            return 200, json.dumps({'data': {'post': {'id': 'bp1', 'metrics': [{'type': 'impressions', 'value': 900}, {'type': 'likes', 'value': 12}]}}}).encode()
        self.assertEqual(buffer_post.collect_metrics(log_book, NOW, key='t', send=send, log=lambda *_: None), 1)
        self.assertEqual(log_book['posts'][0]['metrics'], {'impressions': 900, 'likes': 12})
        self.assertEqual(calls, ['bp1'], 'the fresh post waits')
        self.assertEqual(buffer_post.collect_metrics(log_book, NOW, key='t', send=send, log=lambda *_: None), 0, 'read once')
        said = []
        denied = lambda *a: (200, json.dumps({'errors': [{'message': 'Insufficient scope. Required: insights:read.'}]}).encode())
        fresh = {'posts': [dict(p, metricsAt=None) for p in log_book['posts']]}
        self.assertEqual(buffer_post.collect_metrics(fresh, NOW, key='t', send=denied, log=said.append), 0)
        self.assertEqual(len(said), 1)


if __name__ == '__main__':
    unittest.main()
