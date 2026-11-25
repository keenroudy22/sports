import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import secret_santa


class SecretSantaTests(unittest.TestCase):
    def setUp(self):
        self.play, = json.loads((ROOT / 'data/secret-santa.json').read_text())[:1]
        self.start = self.play['startsAt']
        self.now = datetime(2026, 11, 25, 4, tzinfo=timezone.utc)
        self.game = dict(
            league='CFB', eventId='401866471', kickoff=self.start,
            home={'id': '2711', 'score': 17}, away={'id': '193', 'score': 20},
            retrievedAt='2026-11-25T02:55:00Z',
            sources={'page': 'https://www.espn.com/college-football/boxscore/_/gameId/401866471'},
        )

    def test_open_step_uses_paper_balance_and_half_up_payout(self):
        view = secret_santa.build([self.play], [], {}, self.now)
        self.assertEqual(view['balance'], 2000)
        self.assertEqual(view['current']['winReturn'], 2460)
        self.assertEqual(view['history'], [])

    def test_later_step_uses_settled_full_return(self):
        later = dict(self.play, eventId='2', startsAt='2026-11-25T03:50:00Z', checkedAt='2026-11-25T03:05:00Z')
        view = secret_santa.build([self.play, later], [self.game], {}, self.now)
        self.assertEqual(view['wins'], 1)
        self.assertEqual(view['current']['balance'], 2460)
        too_soon = dict(later, checkedAt='2026-11-25T02:50:00Z')
        self.assertIsNone(secret_santa.build([self.play, too_soon], [self.game], {}, self.now)['current'])

    def test_loss_ends_run_and_unverified_fixture_stays_open(self):
        loss = dict(self.game, away={'id': '193', 'score': 21})
        view = secret_santa.build([self.play], [loss], {}, self.now)
        self.assertTrue(view['closed'])
        self.assertEqual(view['balance'], 0)
        for unverified in (dict(loss, away={'id': '194', 'score': 21}), dict(loss, retrievedAt='2026-11-25T06:00:00Z')):
            self.assertIsNotNone(secret_santa.build([self.play], [unverified], {}, self.now)['current'])

    def test_push_keeps_the_balance(self):
        play = dict(self.play, line=3)
        view = secret_santa.build([play], [self.game], {}, self.now)
        self.assertEqual(view['pushes'], 1)
        self.assertEqual(view['balance'], 2000)

    def test_owner_restart_preserves_the_loss_and_funds_a_new_step(self):
        restart = {'restartAfter': self.play['eventId']}
        loss = dict(self.game, away={'id': '193', 'score': 21})
        view = secret_santa.build([self.play, restart], [loss], {}, self.now)
        self.assertEqual((view['run'], view['balance'], view['losses']), (2, 2000, 0))
        self.assertFalse(view['closed'])
        self.assertIsNone(view['current'])
        self.assertEqual([(row['run'], row['step'], row['result']) for row in view['history']], [(1, 1, 'loss')])

        later = dict(self.play, eventId='2', startsAt='2026-11-25T03:50:00Z', checkedAt='2026-11-25T03:05:00Z')
        view = secret_santa.build([self.play, restart, later], [loss], {}, self.now)
        self.assertEqual((view['current']['run'], view['current']['step'], view['current']['balance']), (2, 1, 2000))

    def test_restart_requires_the_named_official_loss(self):
        restart = {'restartAfter': self.play['eventId']}
        self.assertEqual(secret_santa.build([self.play, restart], [], {}, self.now)['run'], 1)
        self.assertEqual(secret_santa.build([self.play, restart], [self.game], {}, self.now)['run'], 1)
        loss = dict(self.game, away={'id': '193', 'score': 21})
        self.assertTrue(secret_santa.build([self.play, {'restartAfter': '999'}], [loss], {}, self.now)['closed'])
