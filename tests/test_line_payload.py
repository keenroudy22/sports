import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import line_payload


class LinePayloadTests(unittest.TestCase):
    def test_split_manifest_reassembles_every_candidate_without_display_fields(self):
        rows = [
            {'id': 'n1', 'league': 'NFL', 'book': 'ESPN BET', 'line': 41.5},
            {'id': 'c1', 'league': 'CFB', 'book': 'FanDuel', 'line': -3.5},
            {'id': 'c2', 'league': 'CFB', 'book': 'DraftKings', 'line': 52.5},
        ]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = line_payload.manifest(rows, '2026-10-07T04:00:00Z')
            (root / 'lines.json').write_text(json.dumps(manifest))
            for league, name in manifest['files'].items():
                shard = {'league': league, 'lines': [row for row in rows if row['league'] == league]}
                (root / name).write_text(json.dumps(shard))
            loaded = line_payload.load(root / 'lines.json')
            self.assertEqual({row['id']: row for row in loaded}, {row['id']: row for row in rows})
            self.assertEqual(len(loaded), manifest['count'])

    def test_missing_or_incomplete_shard_fails_closed_for_candidate_readers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lines.json'
            path.write_text(json.dumps({'count': 1, 'files': {'NFL': 'lines-NFL.json', 'CFB': 'lines-CFB.json'}}))
            (path.parent / 'lines-NFL.json').write_text(json.dumps({'league': 'NFL', 'lines': []}))
            with self.assertRaises(FileNotFoundError):
                line_payload.load(path)

    def test_legacy_monolith_remains_readable_for_old_fixtures(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lines.json'
            path.write_text(json.dumps({'lines': [{'id': 'old', 'league': 'NFL'}]}))
            self.assertEqual(line_payload.load(path)[0]['id'], 'old')

    def test_optional_reader_keeps_the_prebuild_empty_catalog_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lines.json'
            messages = []
            self.assertEqual(line_payload.load(path, strict=False, log=messages.append), [])
            self.assertIn('optional use skipped', messages[0])
            with self.assertRaises(FileNotFoundError):
                line_payload.load(path)

    def test_optional_reader_falls_back_on_bad_shard_and_count(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lines.json'
            path.write_text(json.dumps({'count': 2, 'files': {'NFL': 'lines-NFL.json'}}))
            (path.parent / 'lines-NFL.json').write_text(json.dumps({'league': 'NFL', 'lines': [{'id': 'n1', 'league': 'CFB'}]}))
            messages = []
            self.assertEqual(line_payload.load(path, strict=False, log=messages.append), [])
            self.assertIn('row outside NFL', messages[0])
            (path.parent / 'lines-NFL.json').write_text(json.dumps({'league': 'NFL', 'lines': [{'id': 'n1', 'league': 'NFL'}]}))
            messages.clear()
            self.assertEqual(line_payload.load(path, strict=False, log=messages.append), [])
            self.assertIn('manifest says 2 rows', messages[0])


if __name__ == '__main__':
    unittest.main()
