import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import rehearse


class OfflineRehearsalTests(unittest.TestCase):
    def test_environment_never_inherits_secrets_or_home(self):
        env = rehearse.environment('/tmp/example-rehearsal')
        self.assertEqual(env['KEENROUDY_RESEARCHER'], '0')
        self.assertEqual(env['KEENROUDY_CONF'], '/tmp/example-rehearsal/private')
        self.assertNotIn('HOME', env)
        self.assertNotIn('SHARP_API', env)
        self.assertNotIn('OPENAI_API_KEY', env)

    def test_guard_blocks_network_process_and_external_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = rehearse.OfflineGuard(tmp)
            guard.audit('open', (str(Path(tmp) / 'okay.json'), 'w', os.O_WRONLY))
            for event, args in [('socket.connect', (None, ('localhost', 80))),
                                ('subprocess.Popen', ('curl', [], None, {})),
                                ('open', ('/tmp/not-this-rehearsal.json', 'w', os.O_WRONLY)),
                                ('os.remove', ('/tmp/not-this-rehearsal.json', -1))]:
                with self.assertRaises(OSError):
                    guard.audit(event, args)
            self.assertEqual(guard.denied['network'], 1)
            self.assertEqual(guard.denied['process'], 1)
            self.assertEqual(guard.denied['outsideWrite'], 2)

    def test_symlink_cannot_escape_write_guard(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            (Path(tmp) / 'escape').symlink_to(other)
            with self.assertRaises(PermissionError):
                rehearse.OfflineGuard(tmp).write(Path(tmp) / 'escape' / 'file.json')

    def test_staging_copies_inputs_without_linking_or_generated_pages(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            for name in ('scripts', 'data', 'research', 'site/data', 'site/data/app'):
                (root / name).mkdir(parents=True, exist_ok=True)
            (root / 'data' / 'store.json').write_text('{"original": true}')
            (root / 'site/data/app' / 'old.json').write_text('{}')
            snap = rehearse.stage(root, output)
            (snap / 'data/store.json').write_text('{}')
            self.assertTrue(json.loads((root / 'data/store.json').read_text())['original'])
            self.assertFalse((snap / 'site/data/app').exists())


if __name__ == '__main__':
    unittest.main()
