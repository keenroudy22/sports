import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import market_review


class MarketReviewTests(unittest.TestCase):
    def rows(self):
        return [{'league': 'NFL', 'market': market, 'kickoff': f'2026-09-{day:02d}T17:00Z',
                 'raw': .8, 'won': i % 2 == 0} for day in range(1, 11) for market in ('rec', 'rushYds') for i in range(25)]

    def test_dates_never_overlap_and_input_order_cannot_leak(self):
        rows = list(reversed(self.rows()))
        train, test = market_review.split_dates(rows)
        self.assertLess(max(r['kickoff'] for r in train), min(r['kickoff'] for r in test))
        self.assertFalse({r['kickoff'][:10] for r in train} & {r['kickoff'][:10] for r in test})
        self.assertEqual(market_review.audit(rows), market_review.audit(list(reversed(rows))))

    def test_future_results_cannot_change_fitted_coefficients(self):
        original = market_review.audit(self.rows())
        changed = copy.deepcopy(self.rows())
        for row in changed:
            if row['kickoff'][:10] >= '2026-09-07':
                row['won'] = True
        second = market_review.audit(changed)
        for a, b in zip(original['markets'], second['markets']):
            for key in ('leagueK', 'marketK', 'pooledK'):
                self.assertEqual(a[key], b[key])
            self.assertNotEqual(a['pooled']['observed'], b['pooled']['observed'])

    def test_thin_history_does_not_nominate_a_formula(self):
        report = market_review.audit(self.rows()[:25])
        self.assertEqual(report['markets'][0]['status'], 'insufficient history')
        self.assertIsNone(report['markets'][0]['pooled'])
        self.assertEqual(market_review.audit([{'raw': float('nan')}])['excluded'], 1)

    def test_probability_error_and_pooling(self):
        scored = market_review.scores([{'raw': .8, 'won': True}, {'raw': .8, 'won': False}], 0)
        self.assertEqual(scored['brier'], .25)
        self.assertAlmostEqual(scored['logLoss'], .69314718056)
        for row in market_review.audit(self.rows())['markets']:
            self.assertGreaterEqual(row['pooledK'], min(row['leagueK'], row['marketK']) - 1e-6)
            self.assertLessEqual(row['pooledK'], max(row['leagueK'], row['marketK']) + 1e-6)
