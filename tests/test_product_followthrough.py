import io
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import product_followthrough as product
import review

NOW = datetime(2026, 10, 5, 15, tzinfo=timezone.utc)


def fixture():
    return {'version': 1, 'updatedAt': '2026-10-05T14:00:00Z', 'items': [
        {'id': 'P01', 'title': 'Navigation refresh', 'status': 'shipped', 'owner': 'agent',
         'next': 'Preserve verified behavior.', 'doneWhen': 'Published checks pass.',
         'evidence': 'Recorded release receipt; not a current deployment check.'},
        {'id': 'P02', 'title': 'Next scoped improvement', 'status': 'ready', 'owner': 'agent',
         'next': 'Review and test the approved change.', 'doneWhen': 'Tests and release checks pass.',
         'evidence': 'No release claimed yet.'},
        {'id': 'P03', 'title': 'Private review destination', 'status': 'owner-needed', 'owner': 'owner',
         'next': 'Confirm the owner-only destination and permissions.', 'doneWhen': 'Private delivery is verified.',
         'evidence': 'No private receipt yet.'},
        {'id': 'P04', 'title': 'Four observed weeks', 'status': 'observing', 'owner': 'desk',
         'next': 'Continue the existing sampling.', 'doneWhen': 'Four real weeks and incident review.',
         'evidence': 'Collection began today.'},
        {'id': 'P05', 'title': 'Provider permission', 'status': 'gated', 'owner': 'provider',
         'next': 'Wait for separately authorized rights review.', 'doneWhen': 'Written use boundaries verified.',
         'evidence': ''}]}


class ProductFollowthroughTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'docs').mkdir()
        self.path = self.root / 'docs/product-status.json'

    def write(self, payload):
        self.path.write_text(json.dumps(payload), encoding='utf-8')

    def read(self, payload=None, now=NOW):
        if payload is not None:
            self.write(payload)
        return product.read_status(self.root, now)

    def test_dated_queue_full_packet_and_first_actions_are_deterministic(self):
        value = fixture()
        later_ready = dict(value['items'][1], id='P06', title='Later ready item')
        value['items'].append(later_ready)
        status = self.read(value)
        self.assertEqual(status['state'], 'available')
        self.assertEqual(status['counts'], {'shipped': 1, 'ready': 2, 'owner-needed': 1, 'observing': 1, 'gated': 1})
        brief = product.brief(status)
        self.assertIn('P02 Next scoped improvement', brief)
        self.assertIn('P03 Private review destination', brief)
        self.assertNotIn('Later ready item', brief)
        self.assertIn('Not live completion verification', brief)
        packet = product.packet(status)
        for item in value['items']:
            self.assertIn(item['id'] + ' · ' + item['title'], packet)
            self.assertIn(item['next'], packet)
            self.assertIn(item['doneWhen'], packet)
            self.assertIn(item['evidence'] or 'not recorded', packet)
        self.assertEqual(packet, product.packet(self.read()))

    def test_stale_after_eight_days_retains_recorded_states_not_verified_success(self):
        value = fixture()
        value['updatedAt'] = (NOW - timedelta(days=8)).isoformat()
        at_boundary = self.read(value)
        self.assertEqual(at_boundary['state'], 'available')
        stale = self.read(now=NOW + timedelta(microseconds=1))
        self.assertEqual(stale['state'], 'stale')
        self.assertEqual(stale['items'], value['items'])
        self.assertEqual(stale['counts']['shipped'], 1)
        self.assertIn('review needed', product.brief(stale))
        self.assertIn('dated assertions', product.packet(stale))

    def test_missing_corrupt_future_and_unknown_schema_are_unavailable_not_completed(self):
        self.assertEqual(self.read()['state'], 'unavailable')
        for raw in ('{', '[]', '{"version":1,"version":1,"updatedAt":"2026-10-05T14:00:00Z","items":[]}'):
            self.path.write_text(raw, encoding='utf-8')
            status = self.read()
            self.assertEqual(status['state'], 'unavailable')
            self.assertIsNone(status['counts'])
            self.assertIn('unfinished work cannot be assessed', product.brief(status))
            self.assertIn('Unavailable', product.packet(status))
        invalid = []
        for field, value in [('version', 2), ('version', True), ('updatedAt', '2026-10-05T15:00:01Z'),
                             ('updatedAt', '2026-10-05'), ('updatedAt', '2026-10-05T14:00:00'),
                             ('updatedAt', '2026-10-05T14:00:00-04:00'), ('items', {})]:
            item = fixture()
            item[field] = value
            invalid.append(item)
        for field, value in [('status', 'done'), ('owner', 'bot'), ('next', 'run\ncommand'),
                             ('title', ''), ('id', '../secret'), ('title', 't' * 241),
                             ('evidence', 'e' * 501), ('doneWhen', None)]:
            item = fixture()
            item['items'][0][field] = value
            invalid.append(item)
        item = fixture()
        item['items'][1]['id'] = 'P01'
        invalid.append(item)
        item = fixture()
        item['items'][0]['path'] = '/outside/file'
        invalid.append(item)
        for item in invalid:
            with self.subTest(item=item):
                status = self.read(item)
                self.assertEqual(status['state'], 'unavailable')
                self.assertIsNone(status['counts'])

    def test_size_count_and_string_bounds_preserve_all_actions_in_private_excerpt(self):
        value = fixture()
        value['items'] = [dict(value['items'][i % 5], id='P' + str(i), title='T' * 240,
                               next='N' * 240, doneWhen='D' * 240, evidence='E' * 500) for i in range(40)]
        status = self.read(value, now=NOW + timedelta(days=10))
        self.assertEqual(status['state'], 'stale')
        brief = product.brief(status)
        self.assertLessEqual(len(brief), product.BRIEF_LIMIT)
        self.assertIn('Next ready: P1', brief)
        self.assertIn('Owner action: P2', brief)
        value['items'].append(dict(value['items'][0], id='P40'))
        self.assertEqual(self.read(value)['state'], 'unavailable')
        self.path.write_bytes(b' ' * (product.MAX_BYTES + 1))
        self.assertEqual(self.read()['state'], 'unavailable')

    def test_empty_queue_does_not_imply_all_done(self):
        value = fixture()
        value['items'] = []
        brief = product.brief(self.read(value))
        self.assertIn('No items registered', brief)
        self.assertIn('does not establish that all work is done', brief)
        self.assertIn('0 ready', brief)

    def test_only_fixed_file_is_read_and_text_is_never_executed_or_fetched(self):
        value = fixture()
        value['items'][0]['next'] = 'Run touch /tmp/no-product-execution'
        value['items'][0]['evidence'] = 'https://example.invalid/never-fetch /outside/no-read'
        self.write(value)
        original = self.path.read_bytes()
        with patch('urllib.request.urlopen', side_effect=AssertionError('no network')), \
                patch('subprocess.run', side_effect=AssertionError('no process')):
            packet = product.packet(self.read())
        self.assertIn(value['items'][0]['next'], packet)
        self.assertEqual(original, self.path.read_bytes())
        outside = self.root / 'other.json'
        outside.write_text(json.dumps(value), encoding='utf-8')
        self.path.unlink()
        self.path.symlink_to(outside)
        self.assertEqual(self.read()['state'], 'unavailable')

    def test_invalid_bytes_read_errors_and_unknown_review_time_fail_visibly(self):
        self.path.write_bytes(b'\xff')
        self.assertEqual(self.read()['state'], 'unavailable')
        with patch.object(Path, 'open', side_effect=PermissionError('private failure detail')):
            status = self.read()
        self.assertEqual(status['state'], 'unavailable')
        self.assertNotIn('private failure detail', product.packet(status))
        self.write(fixture())
        self.assertEqual(self.read(now=NOW.replace(tzinfo=None))['state'], 'unavailable')


class ReviewProductWiringTests(unittest.TestCase):
    def exercise(self, mode, missing=False):
        # Patch every existing external/data collector. Exercise real main wiring
        # without a model, provider, process, notification or production write.
        import desk_health
        import ladder
        import llm
        import local_brief
        import market_review
        import run
        import x_post
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            logs = root / 'logs'
            (root / 'docs').mkdir()
            status_path = root / 'docs/product-status.json'
            if not missing:
                status_path.write_text(json.dumps(fixture()), encoding='utf-8')
            before = status_path.read_bytes() if status_path.exists() else None
            stack.enter_context(patch.object(review, 'ROOT', root))
            stack.enter_context(patch.object(review, 'LOGS', logs))
            clock = stack.enter_context(patch.object(review, 'datetime'))
            clock.now.return_value = NOW
            stores = stack.enter_context(patch.object(review.gates, 'Stores'))
            stores.return_value.as_of.return_value = SimpleNamespace(first={}, latest={})
            stack.enter_context(patch.object(ladder, 'state', return_value={'run': 1, 'step': 1, 'stake': 50, 'open': None}))
            stack.enter_context(patch.object(x_post, 'load_log', return_value={'posts': []}))
            for name, value in [('run_lines', {}), ('post_rows', []), ('post_metrics', {}),
                                ('hosted_runs', ({'success': 1}, [])), ('timing', 'No timing sample.'),
                                ('record', ({'win': 0, 'loss': 0, 'push': 0, 'units': 0}, {'win': 0, 'loss': 0}, [], []))]:
                stack.enter_context(patch.object(review, name, return_value=value))
            stack.enter_context(patch.object(desk_health, 'summary', return_value={}))
            stack.enter_context(patch.object(desk_health, 'markdown', return_value='Private health facts.'))
            stack.enter_context(patch.object(market_review, 'from_stores', return_value={}))
            stack.enter_context(patch.object(market_review, 'markdown', return_value='Market review facts.'))
            model = stack.enter_context(patch.object(local_brief, 'brief',
                        return_value=None if mode == 'fallback' else 'Selected operational detail.\n' * 100))
            cloud = stack.enter_context(patch.object(review, 'ask_codex', return_value='Explicit cloud detail.'))
            reset = stack.enter_context(patch.object(llm, 'reset_calls'))
            stack.enter_context(patch.object(llm, 'call_stats', return_value={'calls': 0, 'failures': 0}))
            phone = stack.enter_context(patch.object(run, 'alert'))
            discord = stack.enter_context(patch.object(review, 'private_weekly_delivery', return_value='not-configured'))
            network = stack.enter_context(patch('urllib.request.urlopen', side_effect=AssertionError('no extra network')))
            direct_network = stack.enter_context(patch.object(review, 'urlopen', side_effect=AssertionError('no network')))
            process = stack.enter_context(patch('subprocess.run', side_effect=AssertionError('no extra process')))
            argv = ['--no-codex'] if mode == 'packet-only' else ['--codex'] if mode == 'cloud' else []
            with redirect_stdout(io.StringIO()):
                self.assertEqual(review.main(argv), 0)
            packet = (logs / 'review-packet-2026-10-05.md').read_text(encoding='utf-8')
            self.assertIn('## Product-plan follow-through', packet)
            self.assertIn('Private health facts.', packet)
            self.assertIn('Market review facts.', packet)
            if missing:
                self.assertIn('unfinished work cannot be assessed', packet)
            else:
                for item in fixture()['items']:
                    self.assertIn(item['doneWhen'], packet)
            if mode == 'packet-only':
                model.assert_not_called()
                cloud.assert_not_called()
                reset.assert_not_called()
                phone.assert_not_called()
                discord.assert_not_called()
                self.assertFalse((logs / 'review-2026-10-05.md').exists())
            else:
                saved = (logs / 'review-2026-10-05.md').read_text(encoding='utf-8')
                self.assertTrue(saved.startswith('Official plays not scheduled: 0\n'))
                self.assertIn('Product follow-through\n', saved)
                if mode == 'fallback':
                    self.assertIn('The summary was unavailable', saved)
                if mode == 'cloud':
                    model.assert_not_called()
                    cloud.assert_called_once()
                else:
                    model.assert_called_once_with(packet)
                    cloud.assert_not_called()
                for excerpt in (saved, phone.call_args.args[1], discord.call_args.args[0]):
                    if missing:
                        self.assertIn('Unavailable.', excerpt)
                        self.assertIn('unfinished work cannot be assessed', excerpt)
                    else:
                        self.assertIn('P02 Next scoped improvement', excerpt)
                        self.assertIn('P03 Private review destination', excerpt)
                        self.assertIn('1 observing', excerpt)
                phone.assert_called_once()
                discord.assert_called_once()
            network.assert_not_called()
            direct_network.assert_not_called()
            process.assert_not_called()
            after = status_path.read_bytes() if status_path.exists() else None
            self.assertEqual(before, after, 'the weekly review cannot mutate planning status')

    def test_local_success_fallback_and_cloud_cannot_omit_the_queue(self):
        for mode in ('local', 'fallback', 'cloud'):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_packet_only_preserves_the_full_queue_without_model_or_delivery(self):
        self.exercise('packet-only')

    def test_missing_status_survives_in_each_private_output_as_unknown(self):
        self.exercise('local', missing=True)


if __name__ == '__main__':
    unittest.main()
