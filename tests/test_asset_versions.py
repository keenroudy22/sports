import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import asset_versions


class AssetVersionTests(unittest.TestCase):
    def test_html_invalidates_main_bundle_and_its_lazy_manifest_together(self):
        with tempfile.TemporaryDirectory() as folder:
            site=Path(folder)
            (site/'app-games.js').write_text('games')
            (site/'app.js').write_text("const GAMES_ASSET = 'app-games.js?v=old';\n")
            (site/'index.html').write_text('<script src="app.js?v=206" defer></script>')
            self.assertEqual(asset_versions.sync(site),['app-games.js','app.js'])
            html=(site/'index.html').read_text()
            self.assertIn('sha256-'+asset_versions.fingerprint(site/'app.js'),html)
            self.assertEqual(asset_versions.sync(site,check=True),[])
            for filename in ('app.js','app-games.js'):
                with (site/filename).open('a') as f:f.write('// changed')
                with self.assertRaisesRegex(ValueError,'fingerprint is stale'):asset_versions.sync(site,check=True)
                asset_versions.sync(site)
                self.assertNotEqual((site/'index.html').read_text(),html)
                html=(site/'index.html').read_text()
            (site/'index.html').write_text('<html></html>')
            with self.assertRaisesRegex(ValueError,'expected one versioned app.js'):asset_versions.sync(site)

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

    def test_core_bundle_is_invalidated_when_its_exported_api_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            site=Path(folder)
            (site/'app.js').write_text('app')
            (site/'core.js').write_text('core')
            (site/'index.html').write_text('<script src="core.js?v=78"></script><script src="app.js?v=old"></script>')
            self.assertEqual(asset_versions.sync(site),['app.js','core.js'])
            (site/'core.js').write_text('core exports changed')
            with self.assertRaisesRegex(ValueError,'core.js content fingerprint is stale'):
                asset_versions.sync(site,check=True)
            self.assertEqual(asset_versions.sync(site),['core.js'])
            self.assertIn('core.js?v=sha256-'+asset_versions.fingerprint(site/'core.js'),(site/'index.html').read_text())

if __name__ == '__main__':
    unittest.main()
