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
            self.assertTrue(asset_versions.sync(site))
            first = (site / 'app.js').read_text()
            self.assertIn('sha256-' + asset_versions.fingerprint(site / 'app-more.js'), first)
            self.assertFalse(asset_versions.sync(site, check=True))
            (site / 'app-more.js').write_text('second')
            with self.assertRaisesRegex(ValueError, 'fingerprint is stale'):
                asset_versions.sync(site, check=True)
            self.assertTrue(asset_versions.sync(site))
            self.assertNotEqual(first, (site / 'app.js').read_text())


if __name__ == '__main__':
    unittest.main()
