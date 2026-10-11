import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_queue
import run


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
