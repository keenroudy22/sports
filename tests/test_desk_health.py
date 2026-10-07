import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import desk_health as H

NOW = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)


class DeskHealthTests(unittest.TestCase):
    def write(self, root, name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def fixture(self, root):
        self.write(root, 'private/status.json', {'outcome': 'ok', 'finishedAt': '2026-10-05T12:33:00Z',
                   'published': 0,
                   'llm': {'used': True, 'calls': {'calls': 2, 'failures': 0}}, 'localEditor': {'stories': 3}})
        self.write(root, 'site/data/slate.json', {'updatedAt': '2026-10-05T13:00:00Z', 'games': []})
        self.write(root, 'site/data/sports.json', {'updatedAt': '2026-10-05T13:00:00Z', 'leagues': {}})
        self.write(root, 'data/odds/status.json', {'usage': {'at': '2026-10-05T13:00:00Z', 'used': 158, 'remaining': 342}})

    def test_cached_summary_is_private_and_makes_no_network_or_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            self.write(root, 'data/x-posted.json', {'secret': 'never expose', 'posts': [
                {'id': 'bad', 'dueAt': '2026-10-05T13:00:00Z', 'error': 'https://secret-webhook/private-token',
                 'text': 'private body', 'discord': {'state': 'failed', 'error': 'another secret'}}]})
            with mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network')):
                summary = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(summary['localModel']['calls'], 2)
            self.assertEqual(summary['oddsBudget']['remaining'], 342)
            self.assertEqual(summary['deliveriesLast48h']['xFailed'], 1)
            self.assertEqual(summary['deliveriesLast48h']['discordFailed'], 1)
            for secret in ('private-token', 'private body', 'another secret', 'never expose'):
                self.assertNotIn(secret, json.dumps(summary) + H.markdown(summary))

    def test_missing_expected_run_and_active_slate_prices_get_actionable_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            self.write(root, 'private/status.json', {'outcome': 'ok', 'finishedAt': '2026-10-05T10:50:00Z'})
            self.write(root, 'site/data/slate.json', {'updatedAt': '2026-10-05T13:00:00Z', 'games': [
                {'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-05T17:00:00Z'}]})
            result = H.summary(root, root / 'private', root, NOW)
            codes = {r['code'] for r in result['issues']}
            self.assertIn('desk-late', codes)
            self.assertIn('source-NFL multi-book prices', codes)
            self.assertNotIn('source-CFB multi-book prices', codes, 'off-slate old odds are not an urgent failure')

    def test_public_data_budget_warning_is_alerted_without_calling_publish_failed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            app = root / 'site/data/app'
            app.mkdir(parents=True)
            (app / 'today.json').write_bytes(b'x' * 327681)
            result = H.summary(root, root / 'private', root, NOW)
            codes = {row['code'] for row in result['issues']}
            self.assertIn('payload-budget', codes)
            self.assertNotIn('publish-failed', codes)

    def test_old_cancelled_and_future_posts_do_not_become_delivery_failures(self):
        posts = [
            {'dueAt': '2026-10-05T13:00:00Z', 'cancelledAt': '2026-10-05T12:00:00Z', 'precheck': {'result': 'withheld'}},
            {'dueAt': '2026-10-05T16:00:00Z', 'bufferPostId': 'pending', 'discord': {'state': 'pending', 'readyAt': '2026-10-05T15:45:00Z'}},
            {'dueAt': '2026-09-28T13:00:00Z', 'error': 'old'},
            {'dueAt': '2026-10-05T13:00:00Z', 'sentAt': '2026-10-05T13:01:00Z', 'discord': {'state': 'pending'}}]
        result = H.delivery(posts, NOW)
        self.assertEqual((result['xOverdue'], result['xFailed'], result['queued'], result['withheld']), (0, 0, 1, 1))
        self.assertEqual(result['discordOverdue'], 1)

    def test_held_caption_is_deduplicated_and_cleared_after_queueing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            line = '[10:00:00] buffer: research:end-zone:2026-10-05 held back, its text fails the post check: 352 characters\n'
            (root / 'run-2026-10-05.log').write_text(line * 2)
            self.assertEqual(H.held_captions(root, '2026-10-05', []), 1)
            self.assertEqual(H.held_captions(root, '2026-10-05', [{'id': 'research:end-zone:2026-10-05', 'bufferPostId': 'queued'}]), 0)

    def test_missing_pilot_is_not_claimed_delivered_and_uncertain_pilot_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            data = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(data['livePilot']['state'], 'not-exercised')
            self.assertFalse(data['issues'])
            self.write(root, 'private/live-progress.json', {'attempts': [{'state': 'sending', 'text': 'secret'}]})
            data = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(data['livePilot']['state'], 'review-required')
            self.assertIn('pilot-review', {r['code'] for r in data['issues']})

    def test_future_time_and_unverified_budget_are_not_fresh_or_free_credit(self):
        self.assertEqual(H.source('test', '2026-10-06T14:00:00Z', NOW, 4)['state'], 'invalid')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            self.write(root, 'data/odds/status.json', {'usage': {'used': 20, 'remaining': 10000}})
            data = H.summary(root, root / 'private', root, NOW)
            self.assertFalse(data['oddsBudget']['verifiedFromStoredSnapshot'])
            self.assertIsNone(data['oddsBudget']['remaining'])

    def test_monitor_uses_two_observations_then_only_changes_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'health.json'
            data = {'checkedAt': '2026-10-05T14:00:00Z', 'issues': [{'code': 'x-overdue', 'message': 'X delivery is overdue.'}]}
            sent = []
            self.assertEqual(H.monitor(data, path, sent.append), 'quiet')
            self.assertEqual(H.monitor(data, path, sent.append), 'changed')
            self.assertEqual(H.monitor(data, path, sent.append), 'quiet')
            self.assertEqual(len(sent), 1)
            self.assertEqual(H.monitor(dict(data, issues=[]), path, sent.append), 'changed')
            self.assertIn('recovered', sent[-1])
            self.assertEqual(H.monitor(dict(data, issues=[]), path, sent.append), 'quiet')

    def test_html_is_escaped_allowlisted_and_has_no_network_or_script_surface(self):
        from html.parser import HTMLParser

        class Inspect(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags, self.network = [], []

            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)
                self.network += [(key, value) for key, value in attrs
                                 if key in ('href', 'src', 'srcset', 'action') or key.startswith('on')]

        data = {'checkedAt': '<script>alert(1)</script>',
                'issues': [{'code': 'test', 'message': '<img src=x onerror=alert(1)>'}],
                'sources': [{'name': '<iframe src=x>', 'state': 'stale', 'observedAt': '2026-10-05T13:00:00Z',
                             'ageMinutes': 60, 'requiredNow': True}],
                'postBody': 'private body never copied', 'webhook': 'private token never copied'}
        page = H.html_report(data)
        parsed = Inspect()
        parsed.feed(page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', page)
        self.assertNotIn('script', parsed.tags)
        self.assertNotIn('iframe', parsed.tags)
        self.assertFalse(parsed.network)
        self.assertIn("default-src 'none'", page)
        self.assertNotIn('private body never copied', page)
        self.assertNotIn('private token never copied', page)
        self.assertNotIn('http-equiv="refresh"', page)

    def test_monitor_saves_owner_only_html_next_to_private_json_not_public_site(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            data = H.summary(root, root / 'private', root, NOW)
            before = {p: p.read_bytes() for p in (root / 'site').rglob('*') if p.is_file()}
            path = root / 'private/desk-health.json'
            with mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network')):
                self.assertEqual(H.monitor(data, path, mock.Mock()), 'quiet')
            page = path.with_suffix('.html')
            self.assertTrue(page.exists())
            self.assertEqual(page.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            rendered = page.read_text()
            for required in ('2026-10-05T14:00:00Z', 'Football schedule', 'X queued', 'Homepage stories', 'not-exercised'):
                self.assertIn(required, rendered)
            self.assertEqual(before, {p: p.read_bytes() for p in (root / 'site').rglob('*') if p.is_file()})
            self.assertFalse(list(root.rglob('*.tmp')))

    def test_precheck_runs_cached_monitor_even_without_due_plays_and_skips_dry_run(self):
        import run
        from types import SimpleNamespace
        with mock.patch.object(H, 'summary', return_value={'issues': []}) as build, \
                mock.patch.object(H, 'monitor') as monitor, \
                mock.patch('x_post.load_log', return_value={'posts': []}), \
                mock.patch('urllib.request.urlopen', side_effect=AssertionError('no source request')):
            args = SimpleNamespace(now=NOW.isoformat(), dry_run=False)
            self.assertEqual(run.precheck(args), 0)
            build.assert_called_once()
            monitor.assert_called_once()
            args.dry_run = True
            self.assertEqual(run.precheck(args), 0)
            self.assertEqual(monitor.call_count, 1)

    def evidence(self, now=NOW):
        return {'checkedAt': H.gates.stamp(now), 'mode': 'private-cached-only', 'issues': [],
                'desk': {'outcome': 'ok', 'selection': 'no-new-play'},
                'deliveryLogState': 'available',
                'sources': [H.source(name, H.gates.stamp(now), now, limit / 60,
                                     name in ('Football schedule', 'Multi-sport snapshots'))
                            for name, limit in H.SOURCE_LIMITS.items()],
                'deliveriesLast48h': {key: 0 for key in H.DELIVERY_FIELDS}}

    def test_reliability_required_unknowns_count_optional_sources_do_not(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'desk-health-reliability.json'
            data = self.evidence()
            injury = next(row for row in data['sources'] if row['name'] == 'Injury context')
            injury.update(requiredNow=True, state='unknown')
            with mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network')), \
                    mock.patch('subprocess.run', side_effect=AssertionError('no model/process')):
                result = H.record_reliability(data, path, NOW)
            self.assertEqual((result['fresh'], result['eligibleSourceChecks'], result['freshPercent']), (2, 3, 66.67))
            day = result['days'][0]
            self.assertEqual((day['unknown'], day['failed'], day['notRequired']), (1, 0, 10))
            self.assertEqual(day['latestSelection'], 'no-new-play')
            self.assertEqual(day['desk']['ok'], 1)
            self.assertEqual(result['readiness'], 'not-assessed')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_reliability_first_actual_sample_per_window_and_missing_window_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            first = H.record_reliability(self.evidence(), path, NOW)
            saved = path.read_bytes()
            repeated = self.evidence(NOW + timedelta(minutes=10))
            repeated['sources'][0]['state'] = 'failed'
            result = H.record_reliability(repeated, path, NOW + timedelta(minutes=10))
            self.assertEqual(result['recording'], 'already-observed')
            self.assertEqual(path.read_bytes(), saved, 'a retry cannot rewrite the observed window')
            later = NOW + timedelta(hours=1)
            result = H.record_reliability(self.evidence(later), path, later)
            self.assertEqual((result['observedWindows'], result['unobservedWindows']), (2, 1))
            self.assertEqual(result['eligibleSourceChecks'], 4, 'do not fabricate eligibility for missing windows')
            self.assertEqual(first['startedAt'], result['startedAt'])
            view = H.reliability_view(H.reliability_history(path), later + timedelta(minutes=30))
            self.assertEqual(view['expectedWindowsSinceRetainedStart'], 3, 'current unobserved window is still pending')

    def test_reliability_replay_future_incomplete_and_non_live_observations_are_not_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            cases = [self.evidence(NOW - timedelta(minutes=6)), self.evidence(NOW + timedelta(seconds=1)),
                     dict(self.evidence(), mode='dry-run'), dict(self.evidence(), sources=[])]
            for data in cases:
                with self.subTest(data=data):
                    result = H.record_reliability(data, path, NOW)
                    self.assertEqual(result['state'], 'not-started')
                    self.assertIsNone(result['freshPercent'])
                    self.assertFalse(path.exists())

    def test_reliability_daily_delivery_is_snapshot_and_no_play_or_withheld_is_not_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            data = self.evidence()
            data['deliveriesLast48h'].update(withheld=1, xConfirmed=2)
            H.record_reliability(data, path, NOW)
            data['checkedAt'] = H.gates.stamp(NOW + timedelta(minutes=30))
            result = H.record_reliability(data, path, NOW + timedelta(minutes=30))
            row = result['days'][0]
            self.assertEqual(row['latestDeliverySnapshot48h']['xConfirmed'], 2, 'same posts are not counted twice')
            self.assertEqual(row['latestDeliverySnapshot48h']['withheld'], 1)
            self.assertEqual(row['desk'], {'ok': 2, 'late': 0, 'failed': 0, 'unknown': 0})
            self.assertEqual(row['latestSelection'], 'no-new-play')
            data['checkedAt'] = H.gates.stamp(NOW + timedelta(days=1))
            data['desk'] = {'outcome': 'not-ok-or-unknown'}
            result = H.record_reliability(data, path, NOW + timedelta(days=1))
            self.assertEqual(result['daysObserved'], 2)
            self.assertEqual(result['days'][-1]['desk']['unknown'], 1)
            self.assertEqual(result['days'][-1]['latestSelection'], 'unknown')

    def test_reliability_missing_delivery_log_is_unknown_not_zero_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            data = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(data['deliveryLogState'], 'unknown')
            result = H.record_reliability(data, root / 'evidence.json', NOW)
            self.assertTrue(all(value is None for value in result['days'][0]['latestDeliverySnapshot48h'].values()))
            self.write(root, 'data/x-posted.json', {'posts': []})
            data = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(data['deliveryLogState'], 'available')

    def test_reliability_required_failure_staleness_and_invalid_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            data = self.evidence()
            for row, state in zip(data['sources'], ('failed', 'stale', 'invalid')):
                row.update(requiredNow=True, state=state)
            data['issues'] = [{'code': 'desk-failed'}]
            result = H.record_reliability(data, path, NOW)
            row = result['days'][0]
            self.assertEqual((row['failed'], row['stale'], row['invalid'], row['unknown']), (1, 1, 1, 0))
            self.assertEqual(row['desk']['failed'], 1)
            self.assertEqual(result['freshPercent'], 0)

    def test_reliability_rolling_retention_preserves_start_without_backfilled_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            for offset in range(60):
                now = NOW + timedelta(days=offset)
                result = H.record_reliability(self.evidence(now), path, now)
            stored = json.loads(path.read_text())
            self.assertEqual(len(stored['samples']), H.RELIABILITY_DAYS)
            self.assertEqual(result['startedAt'], H.gates.stamp(NOW))
            self.assertEqual(result['retainedFrom'], H.gates.stamp(NOW + timedelta(days=4)))
            self.assertGreater(result['unobservedWindows'], 2500)
            self.assertEqual(result['readiness'], 'not-assessed', 'elapsed days never approve launch')
            self.assertLess(path.stat().st_size, 100000)

    def test_reliability_corrupt_history_is_preserved_and_secrets_are_never_copied(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            data = self.evidence()
            data.update(webhook='secret-token', text='private post', issues=[{'code': 'other', 'message': 'secret error'}])
            data['deliveriesLast48h']['error'] = 'secret-response'
            H.record_reliability(data, path, NOW)
            for secret in ('secret-token', 'private post', 'secret error', 'secret-response'):
                self.assertNotIn(secret, path.read_text())
            path.write_text('{incomplete')
            result = H.record_reliability(data, path, NOW)
            self.assertEqual(result['state'], 'unavailable')
            self.assertEqual(path.read_text(), '{incomplete')

    def test_monitor_records_reliability_without_notifications_or_public_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            data = H.summary(root, root / 'private', root, NOW)
            before = {p: p.read_bytes() for p in (root / 'site').rglob('*') if p.is_file()}
            actual = H.record_reliability
            with mock.patch.object(H, 'record_reliability', side_effect=lambda data, path: actual(data, path, NOW)), \
                    mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network')):
                notify = mock.Mock()
                self.assertEqual(H.monitor(data, root / 'private/desk-health.json', notify), 'quiet')
            notify.assert_not_called()
            journal = root / 'private/desk-health-reliability.json'
            self.assertTrue(journal.is_file())
            rendered = (root / 'private/desk-health.html').read_text()
            for text in ('Prospective reliability evidence', '2/2', 'No-new-play', 'readiness is not assessed'):
                self.assertIn(text, rendered)
            summary = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(summary['reliability']['observedWindows'], 1)
            self.assertIn('2/2', H.markdown(summary))
            self.assertEqual(before, {p: p.read_bytes() for p in (root / 'site').rglob('*') if p.is_file()})
            self.assertFalse(list(root.rglob('*.tmp')))

    def post(self, identity, **values):
        return {'id': identity, 'dueAt': H.gates.stamp(NOW - timedelta(hours=1)),
                'bufferPostId': 'stored-provider-id', **values}

    def test_delivery_cohorts_deduplicate_per_channel_without_summing_snapshots(self):
        sent = self.post('one', sentAt=H.gates.stamp(NOW - timedelta(minutes=59)),
                         discord={'state': 'sent'})
        failed = self.post('two', error='private response', discord={'state': 'failed', 'error': 'private webhook'})
        book = {'posts': [sent, dict(sent), failed]}
        result = H.delivery_cohorts(book, NOW)
        self.assertEqual(result, H.delivery_cohorts(book, NOW), 'repeat checks are deterministic, not accumulated')
        for cohort in result['cohorts']:
            self.assertEqual((cohort['duePosts'], cohort['duplicateRowsIgnored']), (2, 1))
            for counts in cohort['channels'].values():
                self.assertEqual((counts['eligibleDue'], counts['confirmed'], counts['recordedFailure']), (2, 1, 1))
        for secret in ('one', 'two', 'private response', 'private webhook', 'stored-provider-id'):
            self.assertNotIn(secret, json.dumps(result))

    def test_delivery_cohorts_use_due_time_not_sent_time_and_have_exact_boundaries(self):
        rows = [self.post('week-boundary', dueAt=H.gates.stamp(NOW - timedelta(days=7))),
                self.post('before-week', dueAt=H.gates.stamp(NOW - timedelta(days=7, seconds=1))),
                self.post('month-boundary', dueAt=H.gates.stamp(NOW - timedelta(days=28))),
                self.post('old-but-confirmed-now', dueAt=H.gates.stamp(NOW - timedelta(days=29)), sentAt=H.gates.stamp(NOW)),
                self.post('future', dueAt=H.gates.stamp(NOW + timedelta(seconds=1))),
                self.post('exact-now', dueAt=H.gates.stamp(NOW))]
        result = H.delivery_cohorts({'posts': rows}, NOW)
        week, month = result['cohorts']
        self.assertEqual((week['duePosts'], month['duePosts']), (2, 4))
        self.assertEqual((week['futureDuePostsExcluded'], month['futureDuePostsExcluded']), (1, 1))
        self.assertEqual((week['olderDuePostsExcluded'], month['olderDuePostsExcluded']), (3, 1))
        self.assertEqual(week['channels']['x']['pending'], 1)
        self.assertEqual(week['channels']['x']['overdueUnconfirmed'], 1)

    def test_delivery_cohort_holds_and_cancellations_do_not_erase_already_sent_discord(self):
        cancelled = H.gates.stamp(NOW - timedelta(minutes=30))
        rows = [self.post('withheld', precheck={'result': 'withheld'}, cancelledAt=cancelled),
                self.post('cancelled', cancelledAt=cancelled),
                self.post('discord-public-before-pull', cancelledAt=cancelled, precheck={'result': 'withheld'},
                          discord={'state': 'sent', 'sentAt': H.gates.stamp(NOW - timedelta(hours=1, minutes=15))})]
        cohort = H.delivery_cohorts({'posts': rows}, NOW)['cohorts'][0]
        x, discord = cohort['channels']['x'], cohort['channels']['discord']
        self.assertEqual((x['eligibleDue'], x['withheld'], x['cancelled']), (0, 2, 1))
        self.assertEqual((discord['eligibleDue'], discord['confirmed'], discord['withheld'], discord['cancelled']), (1, 1, 1, 1))

    def test_delivery_cohort_unknown_identity_time_and_mirror_eligibility_stay_unknown(self):
        rows = [self.post('', sentAt=H.gates.stamp(NOW)), self.post('no-time', dueAt=None),
                self.post('bad-time', dueAt='not-a-timestamp'), self.post('no-mirror'),
                self.post('no-intent', bufferPostId=None), 'invalid row']
        result = H.delivery_cohorts({'posts': rows}, NOW)
        self.assertEqual(result['state'], 'partial')
        self.assertEqual((result['unknownIdentityRows'], result['unknownDueIdentities'], result['invalidRows']), (1, 2, 1))
        channels = result['cohorts'][0]['channels']
        self.assertEqual((channels['x']['eligibleDue'], channels['x']['unknownEligibility']), (1, 1))
        self.assertEqual((channels['discord']['eligibleDue'], channels['discord']['unknownEligibility']), (0, 2))
        self.assertFalse(channels['x']['knownRowsClassified'])

    def test_delivery_cohort_conflicting_duplicates_are_order_independent_and_unknown(self):
        rows = [self.post('state-conflict'), self.post('state-conflict', sentAt=H.gates.stamp(NOW)),
                self.post('time-conflict'), self.post('time-conflict', dueAt=H.gates.stamp(NOW - timedelta(days=10)))]
        result = H.delivery_cohorts({'posts': rows}, NOW)
        self.assertEqual(result, H.delivery_cohorts({'posts': list(reversed(rows))}, NOW))
        self.assertEqual(result['unknownDueIdentities'], 1)
        x = result['cohorts'][0]['channels']['x']
        self.assertEqual((x['eligibleDue'], x['unknownEligibility'], x['duplicateConflicts']), (0, 1, 1))

    def test_delivery_cohort_future_or_invalid_confirmation_is_not_success(self):
        rows = [self.post('future-time', sentAt=H.gates.stamp(NOW + timedelta(seconds=1)),
                          discord={'state': 'sent', 'sentAt': H.gates.stamp(NOW + timedelta(seconds=1))}),
                self.post('invalid-time', sentAt='bad', discord={'state': 'sent', 'sentAt': 'bad'})]
        channels = H.delivery_cohorts({'posts': rows}, NOW)['cohorts'][0]['channels']
        for counts in channels.values():
            self.assertEqual((counts['eligibleDue'], counts['unknown'], counts['confirmed']), (2, 2, 0))

    def test_delivery_cohort_discord_waits_for_x_without_inventing_a_ready_time(self):
        rows = [self.post('waiting-for-x', discord={'state': 'pending'}),
                self.post('future-ready', discord={'state': 'pending', 'readyAt': H.gates.stamp(NOW + timedelta(minutes=5))}),
                self.post('past-ready', discord={'state': 'pending', 'readyAt': H.gates.stamp(NOW - timedelta(minutes=20))})]
        counts = H.delivery_cohorts({'posts': rows}, NOW)['cohorts'][0]['channels']['discord']
        self.assertEqual((counts['eligibleDue'], counts['pending'], counts['overdueUnconfirmed'], counts['recordedFailure']), (3, 2, 1, 0))

    def test_missing_corrupt_log_has_unknown_cohorts_not_empty_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            data = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(data['deliveryCohorts']['state'], 'unknown')
            path = root / 'data/x-posted.json'
            path.write_text('{broken')
            data = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(data['deliveryCohorts']['state'], 'unknown')
            self.assertEqual(data['deliveryCohorts']['cohorts'], [])
            self.write(root, 'data/x-posted.json', {'posts': []})
            data = H.summary(root, root / 'private', root, NOW)
            self.assertEqual(data['deliveryCohorts']['state'], 'available')
            self.assertEqual(data['deliveryCohorts']['cohorts'][0]['channels']['x']['eligibleDue'], 0)
            self.assertEqual(data['desk']['selection'], 'no-new-play')

    def test_delivery_cohort_html_and_weekly_text_are_private_allowlisted_and_caveated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            self.write(root, 'data/x-posted.json', {'posts': [self.post('private-id', error='secret-error', text='private-text')]})
            before = (root / 'data/x-posted.json').read_bytes()
            with mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network')), \
                    mock.patch('subprocess.run', side_effect=AssertionError('no process/model')):
                data = H.summary(root, root / 'private', root, NOW)
                page, weekly = H.html_report(data), H.markdown(data)
            for secret in ('private-id', 'secret-error', 'private-text', 'stored-provider-id'):
                self.assertNotIn(secret, json.dumps(data) + page + weekly)
            self.assertIn('Distinct scheduled-post outcomes', page)
            self.assertIn('0/1', page)
            self.assertIn('never add them', page)
            self.assertIn('not on-time performance', weekly)
            self.assertIn('No-new-play is not a delivery event', weekly)
            self.assertEqual(before, (root / 'data/x-posted.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
