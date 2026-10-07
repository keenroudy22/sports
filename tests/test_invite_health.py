import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import invite_health


class InviteHealthTests(unittest.TestCase):
    def test_real_server_and_permanent_invite(self):
        class Response(io.StringIO):
            def __enter__(self):
                return self
            def __exit__(self, *_):
                self.close()
        def reply(payload):
            return lambda *_args, **_kwargs: Response(json.dumps(payload))
        good = {'code': invite_health.CODE, 'guild': {'id': invite_health.GUILD}, 'expires_at': None}
        self.assertIsNone(invite_health.check(reply(good)))
        self.assertIn('expiry', invite_health.check(reply({**good, 'expires_at': '2026-10-08T00:00:00Z'})))
        self.assertIn('server', invite_health.check(reply({**good, 'guild': {'id': 'wrong'}})))
        self.assertIn('could not', invite_health.check(lambda *_a, **_k: (_ for _ in ()).throw(OSError())))
