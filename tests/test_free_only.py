"""NBA foundation must remain independent of metered feeds and social senders."""
import re
import unittest
from pathlib import Path


class NBAFreeOnlyTests(unittest.TestCase):
    def test_new_nba_modules_use_only_free_espn_endpoints(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        for name in ('espn_props.py', 'sport_box.py', 'nba_capture.py', 'nba_today.py', 'nba_trial.py'):
            source = (scripts / name).read_text()
            for forbidden in ('the-odds-api.com', 'sharpapi', 'sportsgameodds',
                              'import buffer_post', 'import discord_post'):
                self.assertNotIn(forbidden, source.lower())
            for host in re.findall(r'https?://([a-z.]+)', source):
                self.assertIn(host, {'sports.core.api.espn.com', 'site.api.espn.com'})
