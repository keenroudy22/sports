import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import materialize_research


class ResearchIndexTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)
        (root / 'research').mkdir()
        data = root / 'site' / 'data'
        data.mkdir(parents=True)
        game = {'id': 'CFB-test', 'league': 'CFB', 'kickoff': '2026-09-20T23:00:00Z'}
        (data / 'slate.json').write_text(json.dumps({'games': [game]}))
        old = {'league': 'CFB', 'publishedAt': '2026-09-20T10:00:00Z', 'summary': 'Earlier report'}
        new = {'league': 'CFB', 'publishedAt': '2026-09-20T11:00:00Z', 'summary': 'Newly released report'}
        new['gamePicks'] = [{'id': 'CFB-test-over', 'title': 'Test over 50.5', 'status': 'active',
            'why': 'Test evidence', 'risk': 'Test uncertainty', 'sources': ['https://www.espn.com/'],
            'book': 'DraftKings', 'odds': -108, 'quotedAt': '2026-09-20T10:00:00Z',
            'expiresAt': '2026-09-20T22:00:00Z', 'gameIds': ['CFB-test'], 'cutoff': 'Test cutoff',
            'confidence': 2, 'edge': 'Test edge', 'marketType': 'total', 'line': 50.5,
            'direction': 'over', 'jurisdictionVerified': True, 'riskUnits': .5}]
        (root / 'research' / 'old.json').write_text(json.dumps(old))
        (root / 'research' / 'new.json').write_text(json.dumps(new))
        (data / 'research.json').write_text(json.dumps([old]))
        return root, data, [old, new]

    def test_late_report_is_materialized_without_network_or_history_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, data, expected = self.fixture(folder)
            originals = {p: p.read_bytes() for p in (root / 'research').glob('*.json')}
            with patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
                self.assertEqual(materialize_research.build(root)['reports'], 2)
            self.assertEqual(json.loads((data / 'research.json').read_text()), expected)
            import build_site
            first, _ = build_site.first_publications(json.loads((data / 'research.json').read_text()))
            self.assertEqual(first['CFB-test-over']['riskUnits'], .5)
            self.assertEqual(first['CFB-test-over']['line'], 50.5)
            self.assertTrue(all(p.read_bytes() == value for p, value in originals.items()))
            first = (data / 'research.json').read_bytes()
            materialize_research.build(root)
            self.assertEqual((data / 'research.json').read_bytes(), first)

    def test_invalid_new_report_leaves_previous_index_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            root, data, _ = self.fixture(folder)
            original = (data / 'research.json').read_bytes()
            (root / 'research' / 'new.json').write_text('{"league":"invalid"}')
            with self.assertRaises(AssertionError):
                materialize_research.build(root)
            self.assertEqual((data / 'research.json').read_bytes(), original)

    def test_missing_source_directory_never_erases_index(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                materialize_research.build(folder)
