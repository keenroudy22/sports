import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import public_copy
import publication_guard


class PublicCopyTests(unittest.TestCase):
    def test_reader_words_fail_but_real_sports_words_do_not(self):
        for text in ('desk run', 'next run', 'The desk', 'the owner', 'scan', 'scans', 'pipeline',
                     'Scheduled check', 'Ladder step 2', 'Closed to new entries at 11:45 AM ET'):
            self.assertTrue(public_copy.issues(text), text)
        for text in ('Inactives post at 6:45 PM', 'Valdes-Scantling', 'No automatic betting',
                     'not automatically a good price', '2026-10-08T12:00:00Z'):
            self.assertFalse(public_copy.issues(text), text)

    def test_private_timing_fields_fail_even_when_empty(self):
        for value in ({'deskRuns': []}, {'nested': {'StartCalendarInterval': {}}},
                      {'runs': [{'h': 8, 'm': 30}]}):
            self.assertTrue(public_copy.timing_keys(value))
        self.assertFalse(public_copy.timing_keys({'runs': 4, 'score': '6-3'}))

    def test_guard_rejects_public_clock_copy_without_echoing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'index.html').write_text('No automatic betting', encoding='utf-8')
            (root / 'app.js').write_text('The desk runs at 6:45 AM', encoding='utf-8')
            (root / 'data/app').mkdir(parents=True)
            (root / 'data/app/today.json').write_text('{"deskRuns":[]}', encoding='utf-8')
            found = publication_guard.audit(root)['issues']
            self.assertEqual({(row['file'], row['reason']) for row in found},
                             {('app.js', 'schedule-or-automation-copy'),
                              ('data/app/today.json', 'schedule-or-automation-copy'),
                              ('data/app/today.json', 'schedule-or-automation-field')})

    def test_shipped_shell_and_current_payloads_have_no_private_copy(self):
        paths = [ROOT / 'site' / name for name in ('index.html', 'app.js', 'app-more.js', 'app-games.js',
                                                  'core.js', 'live.js', 'personal.js')]
        paths += [ROOT / 'site/data/app' / name for name in ('today.json', 'today-hero.json', 'record.json')]
        paths.append(ROOT / 'site/data/feed.xml')
        for path in paths:
            if path.exists():
                self.assertFalse(public_copy.issues(path.read_text(encoding='utf-8')), str(path))
