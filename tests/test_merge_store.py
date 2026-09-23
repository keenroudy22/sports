import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import boxscores
import merge_store as ms


def rec(game, at, total):
    return json.dumps({'gameId': game, 'retrievedAt': at, 'total': total}, sort_keys=True)


ENV = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t',
       'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'}     # the runner has no global identity; neither does this


def git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True, env=ENV)


def commit(cwd, message):
    git(cwd, 'add', '-A')
    git(cwd, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '-m', message)


def write_store(root, lines, status):
    store = root / 'data' / 'odds'
    store.mkdir(parents=True, exist_ok=True)
    (store / 'nfl-2026.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    boxscores.write_json(store / 'status.json', status)
    boxscores.write_json(store / 'ledger.json', boxscores.ledger(store))


class PureTests(unittest.TestCase):
    def test_lines_from_both_sides_once_in_retrieval_order(self):
        base = rec('g1', '2026-09-26T12:00:00Z', 44) + '\n'
        ours = base + rec('g1', '2026-09-26T12:38:00Z', 45) + '\n'
        theirs = base + rec('g1', '2026-09-26T12:35:00Z', 44.5) + '\n'
        merged = ms.merge_lines(base, ours, theirs)
        self.assertEqual([json.loads(l)['total'] for l in merged], [44, 44.5, 45])
        self.assertEqual(ms.merge_lines(base, ours, ours), ms.lines_of(ours), 'identical sides add nothing')

    def test_status_takes_the_later_side_and_the_stricter_budget(self):
        ours = json.dumps({'leagues': {'NFL': {'count': 2, 'day': '2026-09-26', 'lastAt': '2026-09-26T12:38:00Z'}},
                           'usage': {'at': '2026-09-26T12:38:00Z', 'remaining': 430, 'used': 70}})
        theirs = json.dumps({'leagues': {'NFL': {'count': 3, 'day': '2026-09-26', 'lastAt': '2026-09-26T12:35:00Z'}},
                             'usage': {'at': '2026-09-26T12:35:00Z', 'remaining': 428, 'used': 72}})
        merged = ms.merge_status(ours, theirs)
        self.assertEqual(merged['usage']['at'], '2026-09-26T12:38:00Z', 'the later capture is the base')
        self.assertEqual(merged['leagues']['NFL']['count'], 3, 'the larger count of the same day')
        self.assertEqual((merged['usage']['remaining'], merged['usage']['used']), (428, 72))
        self.assertEqual(ms.merge_status(None, theirs), json.loads(theirs))


class RebaseTests(unittest.TestCase):
    """A real rebase between two writers that both appended, resolved without losing a record."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q', '-b', 'main')
        write_store(self.root, [rec('g1', '2026-09-26T12:00:00Z', 44)],
                    {'leagues': {'NFL': {'count': 1, 'day': '2026-09-26'}}, 'usage': {'at': '2026-09-26T12:00:00Z', 'remaining': 440, 'used': 60}})
        (self.root / 'note.txt').write_text('base\n')
        commit(self.root, 'base')

    def tearDown(self):
        self.tmp.cleanup()

    def store(self):
        return self.root / 'data' / 'odds'

    def test_both_sides_records_survive_and_the_ledger_verifies(self):
        git(self.root, 'checkout', '-q', '-b', 'desk')
        write_store(self.root, [rec('g1', '2026-09-26T12:00:00Z', 44), rec('g1', '2026-09-26T12:35:00Z', 44.5)],
                    {'leagues': {'NFL': {'count': 2, 'day': '2026-09-26'}}, 'usage': {'at': '2026-09-26T12:35:00Z', 'remaining': 439, 'used': 61}})
        commit(self.root, 'desk capture')
        git(self.root, 'checkout', '-q', 'main')
        write_store(self.root, [rec('g1', '2026-09-26T12:00:00Z', 44), rec('g1', '2026-09-26T12:38:00Z', 45)],
                    {'leagues': {'NFL': {'count': 2, 'day': '2026-09-26'}}, 'usage': {'at': '2026-09-26T12:38:00Z', 'remaining': 439, 'used': 61}})
        commit(self.root, 'hosted capture')
        git(self.root, 'checkout', '-q', 'desk')
        stopped = subprocess.run(['git', 'rebase', 'main'], cwd=self.root, capture_output=True, text=True, env=ENV)
        self.assertNotEqual(stopped.returncode, 0, 'the rebase must stop on the store')
        resolved, left = ms.resolve(self.root, log=lambda *_: None)
        self.assertEqual(left, [])
        self.assertEqual(sorted(resolved), ['data/odds/ledger.json', 'data/odds/nfl-2026.jsonl', 'data/odds/status.json'])
        subprocess.run(['git', '-c', 'core.editor=true', 'rebase', '--continue'], cwd=self.root, capture_output=True, text=True, check=True, env=ENV)
        records = boxscores.read_store(self.store() / 'nfl-2026.jsonl')
        self.assertEqual([r['total'] for r in records], [44, 44.5, 45], 'both captures, in retrieval order')
        self.assertEqual(boxscores.verify(self.store()), [], 'the ledger matches the merged file')
        status = json.loads((self.store() / 'status.json').read_text())
        self.assertEqual((status['leagues']['NFL']['count'], status['usage']['remaining']), (2, 439))
        self.assertEqual(ms.unmerged(self.root), [])
        log = git(self.root, 'log', '--format=%s').stdout.split()
        self.assertEqual(log[0], 'desk')

    def test_a_conflict_outside_the_stores_is_left_for_the_caller(self):
        git(self.root, 'checkout', '-q', '-b', 'desk')
        (self.root / 'note.txt').write_text('desk\n')
        commit(self.root, 'desk note')
        git(self.root, 'checkout', '-q', 'main')
        (self.root / 'note.txt').write_text('hosted\n')
        commit(self.root, 'hosted note')
        git(self.root, 'checkout', '-q', 'desk')
        subprocess.run(['git', 'rebase', 'main'], cwd=self.root, capture_output=True, text=True, env=ENV)
        resolved, left = ms.resolve(self.root, log=lambda *_: None)
        self.assertEqual((resolved, left), ([], ['note.txt']))
        git(self.root, 'rebase', '--abort')


if __name__ == '__main__':
    unittest.main()
