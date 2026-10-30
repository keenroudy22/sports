"""Coverage may improve; admission, cost and delivery guards cannot weaken."""
import inspect
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run
import nba_capture
import nba_trial_runtime


class MorningThroughputTests(unittest.TestCase):
    def test_early_props_reallocate_existing_daily_reads_without_increasing_them(self):
        at = lambda h, m: datetime(2026, 10, 24, h, m, tzinfo=run.EASTERN)
        self.assertEqual(sum(run.sharp_capture_allowance(at(h, m)) for h, m in
                             [(6, 45), (8, 30), (17, 30)]), 30)
        self.assertEqual(run.sharp_capture_allowance(at(6, 45)), 10)
        self.assertEqual(run.sharp_capture_allowance(at(7, 30)), 15)
        self.assertEqual(run.sharp_capture_allowance(at(18, 50)), 15)
        self.assertEqual(run.sharp_capture_allowance(at(11, 45)), 0)
        completed = SimpleNamespace(stdout='fresh', stderr='', returncode=0)
        with mock.patch.object(run.subprocess, 'run', return_value=completed) as invoke:
            run.capture(at(6, 45), python='fixture')
        self.assertEqual(Path(invoke.call_args_list[-1].args[0][1]).name, 'sharp_odds.py')
        self.assertEqual(invoke.call_args_list[-1].kwargs['env']['SHARP_REQUESTS'], '10')

    def test_fresh_feed_receipts_are_not_future_data_after_a_slow_capture(self):
        started = datetime(2026, 10, 24, 10, 45, tzinfo=timezone.utc)
        checked = datetime(2026, 10, 24, 10, 49, tzinfo=timezone.utc)
        row = {'retrievedAt': '2026-10-24T10:48:00Z', 'id': 'fresh'}
        with mock.patch.object(run, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = checked
            live = run.current_run_time(SimpleNamespace(dry_run=False, now=None), started)
            self.assertEqual(live, checked)
            self.assertEqual(run.current_run_time(SimpleNamespace(dry_run=True), started), started)
            self.assertEqual(run.current_run_time(SimpleNamespace(dry_run=False, now='replay'), started), started)
        self.assertIsNone(run.gates.latest_before([row], started))
        self.assertEqual(run.gates.latest_before([row], live), row)
        source = inspect.getsource(run._run)
        self.assertLess(source.index("status['selectionAsOf']"), source.index('stores.as_of(now)'))

    def test_unused_family_slots_reach_other_markets_only_after_reserved_pass(self):
        status = {'asked': 0, 'families': {}}
        candidates = [{'id': str(i), 'marketType': 'spread',
                       '_selection': {'anchoredChance': .58, 'breakEven': .52}} for i in range(12)]
        candidates += [{'id': 'prop', 'athleteId': '7'}, {'id': 'total', 'marketType': 'total'}]
        deferred, checked, held = [], [], []
        for rank, candidate, reclaim in run.research_passes(candidates, deferred):
            refusal = run.research_slot_refusal(candidate, status, reclaim=reclaim)
            if refusal and 'research allocation is used' in refusal and not reclaim:
                deferred.append((rank, candidate)); continue
            if refusal:
                held.append(candidate['id']); continue
            checked.append(candidate['id'])
            status['asked'] += 1
            run.note_research_slot(candidate, status)
        self.assertEqual(checked, ['0', '1', 'prop', 'total', '2', '3', '4', '5'])
        self.assertEqual(status['asked'], run.RESEARCH_LIMIT)
        self.assertEqual(len(set(checked + held)), len(candidates))

    def test_reallocation_never_overrides_bad_price_or_total_lookup_ceiling(self):
        row = {'marketType': 'spread', '_selection': {'anchoredChance': .50, 'breakEven': .53}}
        self.assertIn('does not beat', run.research_slot_refusal(row, {'asked': 2}, reclaim=True))
        row['_selection']['anchoredChance'] = .60
        self.assertIn('eight-check', run.research_slot_refusal(row, {'asked': 8}, reclaim=True))

    def test_nba_uses_same_capture_before_football_research_and_does_not_recapture(self):
        now = datetime(2026, 10, 24, 10, 45, tzinfo=timezone.utc)
        status = {'errors': []}
        args = SimpleNamespace(command='run', dry_run=False)
        calls = []
        with mock.patch.dict(os.environ, {'KEENROUDY_SPORTS_CAPTURE': '1'}), \
             mock.patch.object(nba_capture, 'step', side_effect=lambda *a, **k: calls.append('capture') or {}), \
             mock.patch.object(nba_trial_runtime, 'admission', side_effect=lambda *a, **k: calls.append(k) or {'state': 'held'}), \
             mock.patch.object(run, 'log'):
            run.early_nba_selection(args, now, now.astimezone(run.EASTERN), status)
        self.assertEqual(calls, ['capture', {'capture': False}])
        self.assertEqual(status['nbaTrial']['state'], 'held')
        source = inspect.getsource(run._run)
        self.assertLess(source.index('early_nba_selection('), source.index('for candidate_rank'))
        self.assertIn("nba_admission_worker(args,now) and 'nbaTrial' not in status", source)

    def test_capture_failure_retains_bounded_existing_trial_retry(self):
        now = datetime(2026, 10, 24, 10, 45, tzinfo=timezone.utc)
        status = {'errors': []}
        with mock.patch.dict(os.environ, {'KEENROUDY_SPORTS_CAPTURE': '1'}), \
             mock.patch.object(nba_capture, 'step', side_effect=ValueError('offline')), \
             mock.patch.object(nba_trial_runtime, 'admission', return_value={'state': 'held'}) as admission, \
             mock.patch.object(run, 'log'):
            run.early_nba_selection(SimpleNamespace(command='run', dry_run=False), now,
                                    now.astimezone(run.EASTERN), status)
        admission.assert_called_once_with(now, capture=True)
        self.assertEqual(len(status['errors']), 1)

    def test_rehearsal_and_non_run_workers_do_not_take_early_capture(self):
        now = datetime(2026, 10, 24, 10, 45, tzinfo=timezone.utc)
        with mock.patch.object(nba_capture, 'step') as capture:
            for command, dry in [('run', True), ('ladder', False), ('results', False)]:
                run.early_nba_selection(SimpleNamespace(command=command, dry_run=dry), now,
                                        now.astimezone(run.EASTERN), {'errors': []})
        capture.assert_not_called()

    def test_release_uses_real_clock_and_existing_transaction_before_background_work(self):
        status = {}
        with mock.patch.object(run, 'private_release_ready', return_value=True), \
             mock.patch.object(run, 'release_private_isolated', return_value=['qualified']) as release:
            run.release_before_background(SimpleNamespace(dry_run=False, no_push=False), status)
        self.assertEqual(status['releasedBeforeBackground'], ['qualified'])
        self.assertEqual(release.call_args.args[0].tzinfo, timezone.utc)
        source = inspect.getsource(run._run)
        self.assertLess(source.index('release_queue.enqueue('), source.index('release_before_background('))
        self.assertLess(source.index('release_before_background('), source.index('reasoned_edges.step('))
        self.assertLess(source.index('release_before_background('), source.index('paper_trials(now'))

    def test_rehearsal_and_no_push_cannot_release(self):
        with mock.patch.object(run, 'release_private_isolated') as release:
            for dry, no_push in [(True, False), (False, True)]:
                run.release_before_background(SimpleNamespace(dry_run=dry, no_push=no_push), {})
        release.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class AfternoonNBAAdmissionTests(unittest.TestCase):
    def test_existing_afternoon_capture_can_select_without_new_feed_calls(self):
        import nba_player_props
        now=datetime(2026,10,30,17,34,tzinfo=timezone.utc)
        args=SimpleNamespace(command='ladder',dry_run=False,no_push=False,now=None)
        status={'errors':[]}
        with mock.patch.dict(os.environ,{'KEENROUDY_SPORTS_CAPTURE':'1'}), \
             mock.patch.object(nba_player_props,'capture',return_value={'paired':12}) as capture, \
             mock.patch.object(nba_trial_runtime,'admission',return_value={'state':'held'}) as admit, \
             mock.patch.object(run,'log'):
            run.capture_nba_props_and_select(args,now,status)
        capture.assert_called_once()
        admit.assert_called_once()
        self.assertEqual(admit.call_args.kwargs,{'capture':False,'markets':{'player'}})
        self.assertTrue(run.nba_admission_worker(args,now))

    def test_historical_and_non_afternoon_climb_workers_keep_their_scope(self):
        args=SimpleNamespace(command='ladder')
        for at in (datetime(2026,10,29,17,30,tzinfo=timezone.utc),
                   datetime(2026,10,30,14,0,tzinfo=timezone.utc),
                   datetime(2026,10,30,20,0,tzinfo=timezone.utc)):
            self.assertFalse(run.nba_admission_worker(args,at))
        self.assertTrue(run.nba_admission_worker(SimpleNamespace(command='run'),datetime(2026,10,29,17,30,tzinfo=timezone.utc)))
        self.assertFalse(run.nba_admission_worker(SimpleNamespace(command='results'),datetime(2026,10,30,17,30,tzinfo=timezone.utc)))
