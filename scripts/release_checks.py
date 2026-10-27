"""Bounded runtime release checks. Full suites remain mandatory at deployment.

Exact current price, exposure, hard news, report schema and caption/art checks
still execute on every ticket in run.release_private. These regressions protect
that boundary without running unrelated model experiments under the send lock.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    'test_integrity', 'test_gates', 'test_staking', 'test_release_queue',
    'test_moneyline_release', 'test_post_windows', 'test_parlay_caption',
    'test_social_age_notice', 'test_discord_post', 'test_record_audit',
    'test_publication_guard', 'test_chef_picks',
)


def suite(root=ROOT):
    tests = Path(root) / 'tests'
    missing = [name for name in MODULES if not (tests / (name + '.py')).is_file()]
    if missing:
        raise RuntimeError('Missing mandatory release tests: ' + ', '.join(missing))
    sys.path.insert(0, str(tests))
    return unittest.defaultTestLoader.loadTestsFromNames(MODULES)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=1).run(suite())
    raise SystemExit(0 if result.wasSuccessful() else 1)
