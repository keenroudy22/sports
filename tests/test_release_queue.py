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

    def test_missing_private_card_holds_one_admission_without_crashing_the_run(self):
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
            self.assertEqual(added, [])
            self.assertEqual(release_queue.load(root)['plays'], [])
            self.assertEqual(messages, [f"private admission held: {pick['id']}: release card was not rendered"])

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
                'athleteId': '3930086', 'gameIds': ['NFL-401872994']}
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
