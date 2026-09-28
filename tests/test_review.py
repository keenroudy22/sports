import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import review


class ReviewTests(unittest.TestCase):
    def test_the_packet_carries_the_runs_the_posts_the_record_and_problems(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'run-2026-09-27.log').write_text(
                '[10:45:06] run for the 6:45 AM ET slot at 6:45 AM ET\n[10:53:13] done: 4 settled, 0 closed, 3 published, 191 screened\n'
                '[12:46:43] precheck: NFL-x closed before its post: soft news\n[13:00:00] nothing to see\n')
            runs = review.run_lines(date(2026, 9, 27), date(2026, 9, 27), logs=folder)
        self.assertEqual(runs[date(2026, 9, 27)]['runs'], 1)
        self.assertEqual(len(runs[date(2026, 9, 27)]['problems']), 1)
        log_book = {'posts': [
            {'id': 'a', 'kind': 'buffer:play', 'dueAt': '2026-09-27T15:00:00Z', 'tweetId': '1', 'sentAt': '2026-09-27T15:00:02Z'},
            {'id': 'b', 'kind': 'buffer:play', 'dueAt': '2026-09-27T15:10:00Z', 'cancelledAt': '2026-09-27T12:48:53Z',
             'precheck': {'reason': 'soft news'}},
            {'id': 'old', 'kind': 'buffer:play', 'dueAt': '2026-09-01T15:00:00Z'}]}
        posts = review.post_rows(log_book, date(2026, 9, 21), date(2026, 9, 28))
        self.assertEqual([p[1] for p in posts], ['a', 'b'])
        self.assertIn('pulled before posting: soft news', posts[1][3])
        first = {'w': {'title': 'Iowa/Michigan over 38.5', 'odds': -105, 'book': 'ESPN BET', 'publishedAt': '2026-09-26T10:45:00Z'},
                 'l': {'title': 'X under 44.5', 'odds': -110, 'book': 'FanDuel', 'publishedAt': '2026-09-26T10:45:00Z'},
                 'p': {'title': '3-leg longshot', 'legs': [{}, {}, {}], 'parlayType': 'longshot', 'odds': 600, 'riskUnits': 0.25}}
        latest = {'w': {'result': 'win', 'settledAt': '2026-09-27T03:00:00Z', 'units': 0.952},
                  'l': {'result': 'loss', 'settledAt': '2026-09-27T03:00:00Z', 'units': -1.0},
                  'p': {'result': 'loss', 'settledAt': '2026-09-27T03:00:00Z'}}
        week = review.record(first, latest, date(2026, 9, 21), date(2026, 9, 28))
        self.assertEqual(week[0], {'win': 1, 'loss': 1, 'push': 0, 'units': -0.05})
        self.assertEqual(week[1], {'win': 0, 'loss': 1})
        text = review.packet(date(2026, 9, 21), date(2026, 9, 28), runs, posts, week, ({'success': 3}, []), '', 'climb 1, step 1',
                             Path('/nonexistent/ALERT.txt'))
        for needle in ('## Desk runs', 'PROBLEM: [12:46:43]', '## X posts', 'Straight plays: 1-1-0, -0.05 units', 'Fun parlays: 0-1',
                       "{'success': 3}", 'ALERT.txt present: no'):
            self.assertIn(needle, text)

    def test_codex_reads_only(self):
        seen = {}

        def codex(command, **kwargs):
            seen['command'] = command
            Path(command[command.index('--output-last-message') + 1]).write_text('The week ran cleanly.')
        with tempfile.TemporaryDirectory() as folder:
            text = review.ask_codex('packet', Path(folder) / 'review.md', runner=codex)
        self.assertEqual(text, 'The week ran cleanly.')
        command = seen['command']
        self.assertEqual(command[command.index('--sandbox') + 1], 'read-only')
        self.assertNotIn('web_search="live"', command, 'the review reads the packet, not the web')
        self.assertTrue(command[-1].startswith(review.PROMPT[:40]) and command[-1].endswith('packet'))


if __name__ == '__main__':
    unittest.main()
