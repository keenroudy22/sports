import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PrecheckScheduleTests(unittest.TestCase):
    def test_precheck_is_anchored_to_five_and_thirty_five_past_each_hour(self):
        path = ROOT / 'deployment/mac/com.keenroudy.sports.precheck.plist'
        with path.open('rb') as source:
            job = plistlib.load(source)
        self.assertNotIn('StartInterval', job)
        self.assertEqual(job['StartCalendarInterval'], [{'Minute': 5}, {'Minute': 35}])
        self.assertEqual(job['EnvironmentVariables']['TZ'], 'America/New_York')


if __name__ == '__main__':
    unittest.main()
