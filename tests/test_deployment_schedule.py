import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PrecheckScheduleTests(unittest.TestCase):
    def test_regular_desk_checks_climb_before_the_early_game_window(self):
        path = ROOT / 'deployment/mac/com.keenroudy.sports.run.plist'
        with path.open('rb') as source:
            job = plistlib.load(source)
        args = job['ProgramArguments']
        kinds = args[args.index('--publish-kinds') + 1].split(',')
        self.assertEqual(set(kinds), {'settle', 'close', 'lean', 'prop', 'longshot', 'ladder'})
        slots = job['StartCalendarInterval']
        self.assertIn({'Hour': 6, 'Minute': 45}, slots)
        self.assertEqual(job['EnvironmentVariables']['TZ'], 'America/New_York')

    def test_precheck_is_anchored_to_five_and_thirty_five_past_each_hour(self):
        path = ROOT / 'deployment/mac/com.keenroudy.sports.precheck.plist'
        with path.open('rb') as source:
            job = plistlib.load(source)
        self.assertNotIn('StartInterval', job)
        self.assertEqual(job['StartCalendarInterval'], [{'Minute': 5}, {'Minute': 35}])
        self.assertEqual(job['EnvironmentVariables']['TZ'], 'America/New_York')


if __name__ == '__main__':
    unittest.main()
