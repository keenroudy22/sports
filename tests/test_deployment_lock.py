import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deployment_lock


class PromotionTests(unittest.TestCase):
    def test_changed_production_prevents_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(deployment_lock, 'head', return_value='new'):
                with self.assertRaisesRegex(RuntimeError, 'repeat verification'):
                    with deployment_lock.promotion_lock(Path(folder)/'lock', 'prod', 'dev', 'old', 'tested'):
                        self.fail('stale candidate promoted')

    def test_unchanged_tested_heads_allow_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(deployment_lock, 'head', side_effect=['base', 'tested']):
                with deployment_lock.promotion_lock(Path(folder)/'lock', 'prod', 'dev', 'base', 'tested'):
                    pass
