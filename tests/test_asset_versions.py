import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import asset_versions


class AssetVersionTests(unittest.TestCase):
    def test_lazy_bundle_version_is_derived_from_its_content(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / 'app-more.js').write_text('first')
            (site / 'app.js').write_text("const MORE_ASSET = 'app-more.js?v=old';\n")
            self.assertEqual(asset_versions.sync(site), ['app-more.js'])
            first = (site / 'app.js').read_text()
            self.assertIn('sha256-' + asset_versions.fingerprint(site / 'app-more.js'), first)
            self.assertEqual(asset_versions.sync(site, check=True), [])
            (site / 'app-more.js').write_text('second')
            with self.assertRaisesRegex(ValueError, 'fingerprint is stale'):
                asset_versions.sync(site, check=True)
            self.assertEqual(asset_versions.sync(site), ['app-more.js'])
            self.assertNotEqual(first, (site / 'app.js').read_text())

    def test_every_lazy_bundle_has_its_own_declaration(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / 'app-more.js').write_text('more')
            (site / 'app-games.js').write_text('games')
            (site / 'app.js').write_text("const MORE_ASSET = 'app-more.js?v=old';\nconst GAMES_ASSET = 'app-games.js?v=old';\n")
            self.assertEqual(asset_versions.sync(site), ['app-more.js', 'app-games.js'])
            source = (site / 'app.js').read_text()
            self.assertIn(f"const GAMES_ASSET = 'app-games.js?v=sha256-{asset_versions.fingerprint(site / 'app-games.js')}';", source)
            (site / 'app-games.js').write_text('games changed')
            with self.assertRaisesRegex(ValueError, 'app-games.js content fingerprint is stale'):
                asset_versions.sync(site, check=True)
            self.assertEqual(asset_versions.sync(site), ['app-games.js'])
            (site / 'app.js').write_text("const MORE_ASSET = 'app-more.js?v=old';\n")
            with self.assertRaisesRegex(ValueError, 'expected one GAMES_ASSET declaration'):
                asset_versions.sync(site)


if __name__ == '__main__':
    unittest.main()
