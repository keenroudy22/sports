import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_queue
import run
import x_post


NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


class ReleaseQueueTests(unittest.TestCase):
    def test_new_climb_rung_without_latest_row_is_marked_pending(self):
        rung = {'id': 'CFB-2026-W7-ladder-1017-c3s2-dk', 'title': '80/20 Climb #3 · Step 2'}
        ctx = SimpleNamespace(first={rung['id']: dict(rung, league='CFB', kind='parlays')}, latest={})

        run.mark_admitted_pending(ctx, [('CFB', 'parlays', rung)])

        self.assertTrue(rung['_pendingRelease'])
        self.assertTrue(ctx.first[rung['id']]['_pendingRelease'])
        self.assertTrue(ctx.latest[rung['id']]['_pendingRelease'])
        self.assertEqual(ctx.latest[rung['id']]['kind'], 'parlays')

    def test_released_card_archive_preserves_exact_png_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'private.png'
            original = b'\x89PNG\r\n\x1a\n' + b'private Kitchen Ticket bytes' * 8
            source.write_bytes(original)
            target = release_queue.archive_card(source, root, 'NFL-2026-W5-knox-over-12-5-recyds-dk')
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(target, root / 'data' / 'release-cards' /
                             'NFL-2026-W5-knox-over-12-5-recyds-dk.png')

    def test_admission_stays_private_and_merges_only_into_process_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            drafts = root / 'drafts'
            drafts.mkdir()
            (drafts / 'play.txt').write_text('The play\n\nA real reason.\n', encoding='utf-8')
            (drafts / 'play.png').write_bytes(b'\x89PNG\r\n\x1a\nprivate art')
            pick = {'id': 'play', 'title': 'Player over 20.5', 'odds': -110, 'book': 'DraftKings',
                    'gameIds': ['NFL-1'], 'publishedAt': '2026-10-11T12:00:00Z'}
            games = {'NFL-1': {'kickoff': '2026-10-11T17:00:00Z'}}
            added = release_queue.enqueue(root, [('NFL', 'props', pick)], {'play': 'A real reason.'},
                                          [{'id': 'play', 'decision': 'published', 'season': 2026}], drafts,
                                          NOW, games=games)
            self.assertEqual(added, ['play'])
            stored = release_queue.load(root)['plays'][0]
            self.assertNotIn('publishedAt', stored['pick'])
            self.assertEqual(stored['kickoffs'], ['2026-10-11T17:00:00Z'])
            self.assertTrue(Path(stored['card']).exists())
            ctx = SimpleNamespace(first={}, latest={})
            release_queue.merge_context(ctx, root)
            self.assertTrue(ctx.first['play']['_pendingRelease'])
            self.assertEqual(ctx.first['play']['publishedAt'], '2026-10-11T12:00:00Z')

    def test_missing_private_card_stays_queued_for_five_minute_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            drafts = root / 'drafts'
            drafts.mkdir()
            (drafts / 'NFL-2026-W5-knox-over-12-5-recyds-dk.txt').write_text('Knox over 12.5\n', encoding='utf-8')
            pick = {'id': 'NFL-2026-W5-knox-over-12-5-recyds-dk', 'title': 'Dawson Knox OVER 12.5 receiving yards',
                    'odds': -110, 'book': 'DraftKings', 'gameIds': ['NFL-401872994']}
            messages = []
            added = release_queue.enqueue(root, [('NFL', 'props', pick)], {pick['id']: 'real reason'},
                                          [{'id': pick['id'], 'decision': 'published'}], drafts, NOW,
                                          games={'NFL-401872994': {'kickoff': '2026-10-13T00:15:00Z'}},
                                          log=messages.append)
            self.assertEqual(added, [pick['id']])
            stored = release_queue.load(root)['plays'][0]
            self.assertEqual(stored['artifactState'], 'recovery-needed')
            self.assertEqual(stored['artifactMissing'], ['card'])
            self.assertEqual(messages, [f"private admission queued for artifact recovery: {pick['id']}: missing card"])

    def test_missing_caption_and_card_are_both_kept_visible_for_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            drafts = root / 'drafts'
            drafts.mkdir()
            pick = {'id': 'play', 'title': 'Packers MONEYLINE', 'marketType': 'moneyline',
                    'odds': -108, 'book': 'DraftKings', 'gameIds': ['NFL-1']}
            added = release_queue.enqueue(root, [('NFL', 'gamePicks', pick)], {'play': 'Verified injury reason.'},
                                          [{'id': 'play', 'decision': 'published'}], drafts, NOW,
                                          games={'NFL-1': {'kickoff': '2026-10-11T17:00:00Z'}}, log=lambda *_: None)
            self.assertEqual(added, ['play'])
            stored = release_queue.load(root)['plays'][0]
            self.assertIsNone(stored['caption'])
            self.assertEqual(stored['artifactMissing'], ['card', 'caption'])
            self.assertEqual(stored['kickoffs'], ['2026-10-11T17:00:00Z'])

    def test_five_minute_worker_rebuilds_missing_artifacts_and_clears_recovery_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            key = 'play'
            pick = {'id': key, 'title': 'Packers MONEYLINE', 'marketType': 'moneyline',
                    'odds': -108, 'book': 'DraftKings', 'gameIds': ['NFL-1']}
            card = release_queue.cards(root) / f'{key}.png'
            release_queue.save(root, {'plays': [{'id': key, 'league': 'NFL', 'kind': 'gamePicks',
                                                 'pick': pick, 'reason': 'Verified injury reason.',
                                                 'caption': None, 'card': str(card),
                                                 'artifactState': 'recovery-needed'}]})
            game = {'id': 'NFL-1', 'league': 'NFL', 'kickoff': '2026-10-11T17:00:00Z',
                    'away': {'id': '1'}, 'home': {'id': '2'}}
            ctx = SimpleNamespace(first={}, latest={}, player_team={})

            def render(_key, _pick, _game, _games, _ctx, _now, target):
                Path(target).write_bytes(b'\x89PNG\r\n\x1a\nrecovered')

            with mock.patch.object(run, 'CONF', root), \
                    mock.patch.object(x_post, 'do_draft', return_value=('Full Send\nVerified injury reason.', pick, game)), \
                    mock.patch.object(run, 'render_private_play_card', side_effect=render):
                recovered = run.recover_private_release_artifacts(
                    release_queue.load(root)['plays'][0], ctx, {'NFL-1': game}, NOW)

            self.assertEqual(recovered['artifactState'], 'ready')
            self.assertEqual(recovered['artifactMissing'], [])
            self.assertIn('Verified injury reason.', recovered['caption'])
            self.assertTrue(card.is_file())

    def test_new_admission_not_yet_in_public_context_still_gets_a_private_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pick = {'id': 'NFL-2026-W5-knox-over-12-5-recyds-dk', 'title': 'Dawson Knox OVER 12.5 receiving yards',
                    'odds': -110, 'book': 'DraftKings', 'gameIds': ['NFL-401872994'], 'lane': 'best_bet'}
            game = {'id': 'NFL-401872994', 'league': 'NFL', 'kickoff': '2026-10-13T00:15:00Z',
                    'away': {'id': '2'}, 'home': {'id': '14'}}
            ctx = SimpleNamespace(first={}, latest={}, player_team={})
            status = {'x': {}}

            def draft(key, now, first, latest, games, out=None, reason=None):
                self.assertIn(pick['id'], first)
                self.assertEqual(reason, 'Bills injuries open targets for Johnson.')
                Path(out, f'{key}.txt').write_text('Book says 12.5. I say 20.\n', encoding='utf-8')
                return 'Book says 12.5. I say 20.', first[key], games['NFL-401872994']

            with mock.patch.object(run, 'CONF', root), mock.patch.object(x_post, 'load_log', return_value={'posts': []}), \
                    mock.patch.object(x_post, 'do_draft', side_effect=draft), \
                    mock.patch('pick_card.chrome_path', return_value=None):
                run.drafts(NOW.astimezone(run.EASTERN), NOW, ctx, {'NFL-401872994': game}, [], status,
                           admitted=[('NFL', 'props', pick)],
                           reasons={pick['id']: 'Bills injuries open targets for Johnson.'})
            self.assertTrue((root / 'x-drafts' / f"{pick['id']}.txt").is_file())
            self.assertEqual(status['x']['drafted'], 1)

    def test_new_admission_uses_its_verified_reason_before_the_public_reason_store_exists(self):
        pick = {'id': 'NFL-2026-W5-knox-over-12-5-recyds-dk',
                'title': 'Dawson Knox OVER 12.5 receiving yards', 'lane': 'hot_plate',
                'favorite': True, 'status': 'active', 'odds': -109, 'book': 'DraftKings',
                'line': 12.5, 'projection': 19.4, 'market': 'recYds', 'marketType': 'player',
                'athleteId': '3930086', 'gameIds': ['NFL-401872994'],
                'probabilityAtPublication': {'chance': .55, 'breakEven': .522, 'calibrated': True}}
        game = {'id': 'NFL-401872994', 'league': 'NFL', 'kickoff': '2026-10-13T00:15:00Z',
                'away': {'id': '2', 'name': 'Bills'}, 'home': {'id': '14', 'name': 'Rams'}}
        reason = 'Buffalo ruled a starting receiver out, opening more short targets.'
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(x_post, 'load_log', return_value={'posts': []}), \
                mock.patch.object(x_post, 'load_reasons', return_value={}):
            text, _, _ = x_post.do_draft(pick['id'], NOW, {pick['id']: pick}, {pick['id']: pick},
                                         {'NFL-401872994': game}, out=Path(folder), reason=reason)
            self.assertIn(reason, text)
            self.assertTrue((Path(folder) / f"{pick['id']}.txt").is_file())

    def test_update_and_remove_are_atomic_state_transitions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = release_queue.path(root)
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({'plays': [{'id': 'one'}, {'id': 'two'}]}), encoding='utf-8')
            release_queue.update(root, 'one', discordSentAt='now')
            self.assertEqual(release_queue.load(root)['plays'][0]['discordSentAt'], 'now')
            release_queue.remove(root, 'one')
            self.assertEqual([row['id'] for row in release_queue.load(root)['plays']], ['two'])

    def test_expired_unreleased_admission_reopens_for_fresh_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release_queue.save(root, {'plays': [
                {'id': 'stale', 'pick': {'expiresAt': '2026-10-11T11:59:00Z'}},
                {'id': 'live', 'pick': {'expiresAt': '2026-10-11T12:01:00Z'}},
                {'id': 'sent', 'discordSentAt': '2026-10-11T11:58:00Z',
                 'pick': {'expiresAt': '2026-10-11T11:59:00Z'}},
            ]})
            messages = []
            self.assertEqual(release_queue.reopen_expired(root, NOW, log=messages.append), ['stale'])
            self.assertEqual([row['id'] for row in release_queue.load(root)['plays']], ['live', 'sent'])
            self.assertEqual(messages, ['private admission reopened for a fresh price: stale'])

    def test_delivery_clock_reads_the_private_kickoff_without_a_public_row(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release_queue.save(root, {'plays': [{'id': 'one', 'league': 'NFL',
                                                 'kickoffs': ['2026-10-11T17:00:00Z'], 'pick': {}}]})
            original = run.CONF
            try:
                run.CONF = root
                self.assertFalse(run.private_release_ready(datetime(2026, 10, 11, 13, 14, tzinfo=timezone.utc)))
                self.assertTrue(run.private_release_ready(datetime(2026, 10, 11, 13, 15, tzinfo=timezone.utc)))
            finally:
                run.CONF = original


if __name__ == '__main__':
    unittest.main()
