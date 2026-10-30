"""NBA foundation must remain independent of metered feeds and social senders."""
import re
import unittest
from pathlib import Path


class NBAFreeOnlyTests(unittest.TestCase):
    def test_new_nba_modules_use_only_approved_free_endpoints(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        for name in ('espn_props.py', 'sport_box.py', 'nba_capture.py', 'nba_official_availability.py', 'nba_today.py', 'nba_trial.py'):
            source = (scripts / name).read_text()
            for forbidden in ('the-odds-api.com', 'sharpapi', 'sportsgameodds',
                              'import buffer_post', 'import discord_post'):
                self.assertNotIn(forbidden, source.lower())
            allowed={'sports.core.api.espn.com', 'site.api.espn.com'}
            if name in ('nba_capture.py','nba_official_availability.py'):
                allowed.update({'ak-static.cms.nba.com','official.nba.com'})
            if name == 'nba_capture.py':
                # Public contact URI in the identified reader, never a fetch endpoint.
                allowed.add('keenroudy.com')
            # Also inspect literal URL guards containing escaped regex dots.
            for host in re.findall(r'https?://([a-z0-9.-]+)', source.replace(r'\.', '.')):
                self.assertIn(host, allowed)
