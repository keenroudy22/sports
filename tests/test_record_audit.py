import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import record_audit


class RecordAuditTests(unittest.TestCase):
    def test_hosted_reconciliation_reads_the_full_split_record(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml').read_text()
        self.assertIn('python scripts/record_audit.py --today site/data/app/record.json', workflow)

    reports = [{'league': 'NFL', 'publishedAt': '2026-09-01T12:00:00Z', 'props': [
        {'id': 'official', 'gameIds': ['NFL-1'], 'odds': -110}]},
        {'league': 'NFL', 'publishedAt': '2026-09-02T12:00:00Z', 'props': [
            {'id': 'official', 'result': 'win', 'settledAt': '2026-09-02T23:00:00Z', 'units': .91}]}]

    def row(self, **changes):
        return {'id': 'official', 'league': 'NFL', 'publishedAt': '2026-09-01T12:00:00Z',
                'result': 'win', 'settledAt': '2026-09-02T23:00:00Z', 'units': .91, 'season': 2026} | changes

    def test_exact_official_record_passes(self):
        self.assertEqual(record_audit.audit(self.reports, {'picks': [self.row()]}), [])

    def test_personal_ticket_stale_grade_and_missing_season_fail(self):
        issues = record_audit.audit(self.reports, {'picks': [self.row(), self.row(result='loss', season=None),
                                                              self.row(id='personal-social-ticket')]})
        self.assertTrue(any('duplicate public pick id' in issue for issue in issues))
        self.assertTrue(any('non-official pick' in issue for issue in issues))
        self.assertTrue(any('result does not match' in issue for issue in issues))
        self.assertTrue(any('season is missing' in issue for issue in issues))

    def test_missing_official_pick_fails(self):
        self.assertIn('missing public pick: official', record_audit.audit(self.reports, {'picks': []}))


if __name__ == '__main__':
    unittest.main()
