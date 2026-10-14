import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chef_wins


NOW = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)
IMAGE_BYTES = {
    '.png': b'\x89PNG\r\n\x1a\nvalid',
    '.jpg': b'\xff\xd8\xffvalid',
    '.webp': b'RIFF\x04\x00\x00\x00WEBPvalid',
    '.gif': b'GIF89avalid',
}


class ChefWinsTests(unittest.TestCase):
    def test_images_post_once_by_hash_skip_nonimages_and_stop_at_three(self):
        sent = []
        def send(url, body, headers):
            sent.append((url, body, headers))
            return 204, b''
        with tempfile.TemporaryDirectory() as folder:
            root, state = Path(folder), Path(folder) / 'work' / 'seen.json'
            for name in ('a.png', 'b.jpg', 'c.webp', 'd.gif'):
                (root / name).write_bytes(IMAGE_BYTES[Path(name).suffix])
            (root / 'ignore.txt').write_text('not an image')
            (root / 'renamed.png').write_text('also not an image')
            first = chef_wins.run(NOW, root, state, url='wins', send=send, log=lambda *_: None)
            self.assertEqual(first, {'posted': 3, 'held': 1})
            self.assertEqual(len(sent), 3)
            self.assertTrue(all(chef_wins.TEXT.encode() in body for _, body, _ in sent))
            # A renamed duplicate is already seen; the fourth unique image can post tomorrow.
            (root / 'copy.png').write_bytes((root / 'a.png').read_bytes())
            later = datetime(2026, 10, 15, 15, tzinfo=timezone.utc)
            second = chef_wins.run(later, root, state, url='wins', send=send, log=lambda *_: None)
            self.assertEqual(second['posted'], 1)
            self.assertEqual(len(sent), 4)

    def test_missing_webhook_holds_and_alerts_once(self):
        alerts = []
        with tempfile.TemporaryDirectory() as folder:
            root, state = Path(folder), Path(folder) / 'work' / 'seen.json'
            (root / 'winner.png').write_bytes(IMAGE_BYTES['.png'])
            for _ in range(2):
                result = chef_wins.run(NOW, root, state, url='', notify=lambda *args: alerts.append(args),
                                       log=lambda *_: None)
                self.assertEqual(result, {'posted': 0, 'held': 1})
            self.assertEqual(len(alerts), 1)


if __name__ == '__main__':
    unittest.main()
