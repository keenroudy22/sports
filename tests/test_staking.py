import sys
import unittest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import staking
import gates
import run
import nba_trial
import release_queue

NOW = datetime(2026, 10, 23, 18, tzinfo=timezone.utc)


def pick(key='new', units=.5, **extra):
    return dict(id=key, kickoff='2026-10-23T23:00:00Z', riskUnits=units, **extra)


def context(**extra):
    return SimpleNamespace(now=NOW, games={}, first={}, risk_external={}, risk_games={}, **extra)


class StakingTests(unittest.TestCase):
    def test_regular_nba_and_football_share_the_straight_count_ceiling(self):
        ctx=context();ctx.now=datetime(2026,10,28,19,tzinfo=timezone.utc)
        make=lambda key,league:dict(pick(key,league=league),kickoff='2026-10-28T23:00:00Z')
        ctx.games={str(i):make(str(i),'NBA') for i in range(12)}
        ctx.first={str(i):make(str(i),'CFB') for i in range(8)}
        self.assertIn('straight-count cap is 8',staking.check(make('NBA-new','NBA'),ctx))
        ctx.risk_external={'NBA-open':make('NBA-open','NBA')}
        ctx.first.pop('7')
        self.assertIn('straight-count cap is 8',staking.check(make('CFB-new','CFB'),ctx))
        ctx.first.pop('6')
        self.assertIsNone(staking.check(make('NBA-new','NBA'),ctx))
        ctx.games={};ctx.first={str(i):make(str(i),'CFB') for i in range(4)}
        self.assertIn('straight-count cap is 5',staking.check(make('NBA-new','NBA'),ctx))
        ctx.risk_external={'personal':dict(make('personal','NBA'),personalTicket=True, riskUnits=.25)}
        self.assertIsNone(staking.check(make('NBA-new','NBA'),ctx))
    def test_prospective_stakes_and_legacy_results(self):
        for lane, old, new in [('best_bet', 1, .5), ('chef_pick', 2, 1)]:
            row = pick(lane=lane, units=old)
            self.assertEqual(staking.expected(row), old)
            self.assertEqual(staking.apply(dict(row), NOW)['riskUnits'], new)
            self.assertEqual(staking.apply(dict(row), NOW.replace(day=22)), row)
            self.assertEqual(row['riskUnits'], old)

    def test_shared_cap_counts_settled_and_private_rows_without_recycling(self):
        ctx = context()
        ctx.first = {'old': pick('old', 1, result='win'), 'pending': pick('pending', 1, _pendingRelease=True)}
        ctx.risk_external = {'nba': pick('nba', .5), 'fun': pick('fun', .25, result='cashout')}
        self.assertIn('exceeds 3u', staking.check(pick(), ctx))
        self.assertIsNone(staking.check(pick(units=.25), ctx))

    def test_self_and_duplicate_reservations_not_double_counted(self):
        ctx = context()
        ctx.first = {'new': pick(), 'old': pick('old', 2.5)}
        ctx.risk_external = {'old': pick('old', 2.5)}
        self.assertIsNone(staking.check(pick(), ctx))

    def test_previous_day_and_withdrawn_private_do_not_consume(self):
        ctx = context()
        ctx.first = {'yesterday': dict(pick('yesterday', 9), kickoff='2026-10-23T02:00:00Z'),
                     'held': pick('held', 9, _pendingRelease=True, held=True)}
        self.assertIsNone(staking.check(pick(), ctx))

    def test_climb_actual_dollars_and_unknown_stakes(self):
        self.assertEqual(staking.units(pick(parlayType='ladder', ladder={'stake': 50})), 2)
        ctx = context()
        ctx.first = {'climb': pick('climb', parlayType='ladder', ladder={'stake': 75})}
        self.assertIn('exceeds 3u', staking.check(pick(), ctx))
        for value in (None, '50', True, float('nan'), -1):
            self.assertIsNone(staking.units(pick(parlayType='ladder', ladder={'stake': value})))
        ctx.first = {'personal': pick('personal', None)}
        self.assertIn('stake unknown', staking.check(pick(), ctx))

    def test_big_slate_includes_nba_and_weekends(self):
        on = NOW.date()
        games = {str(i): dict(pick(), league='NBA') for i in range(8)}
        self.assertEqual(staking.limit(on, games), 5)
        games.pop('0')
        self.assertEqual(staking.limit(on, games), 3)
        self.assertEqual(staking.limit(on.replace(day=24), {}), 5)

    def test_missing_day_is_not_a_budget_bypass(self):
        self.assertIn('missing game day', staking.check({'riskUnits': .5}, context()))

    def test_pending_art_is_regenerated_but_already_sent_stake_is_immutable(self):
        row = {'id': 'new', 'pick': pick(units=1, lane='best_bet'), 'caption': 'old',
               'card': 'old.png', 'precheckedAt': '2026-10-23T14:00:00Z'}
        ctx = context(latest={})
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(run, 'CONF', Path(folder)):
            release_queue.save(Path(folder), {'plays': [row]})
            updated = run.normalize_private_stake(row, ctx, NOW)
            self.assertEqual(updated['pick']['riskUnits'], .5)
            self.assertIsNone(updated['caption'])
            self.assertIsNone(updated['precheckedAt'])
            self.assertTrue(updated['card'].endswith('-staking-v1.png'))
            self.assertEqual(ctx.first['new']['riskUnits'], .5)
            sent = dict(row, discordSentAt='2026-10-23T14:00:00Z')
            self.assertEqual(run.normalize_private_stake(sent, ctx, NOW), sent)

    def test_nba_publication_cannot_bypass_football_exposure(self):
        offer = pick(league='NBA', season=2027, seasonType=2, marketType='total',
            line=221.5, odds=-110, oppositeOdds=-110, book='DraftKings',
            retrievedAt='2026-10-23T17:00:00Z', rawChance=.60,
            source='https://www.espn.com/nba/', sideVerified=True,
            exactLineVerified=True, roleChecked=True, stakingPolicy=staking.VERSION)
        ctx = context()
        ctx.first = {'football': pick('football', 3)}
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(gates, 'Stores') as stores, \
                mock.patch.object(release_queue, 'merge_context'):
            stores.return_value.as_of.return_value = ctx
            root = Path(folder) / 'data' / 'nba-trial'
            with self.assertRaisesRegex(ValueError, 'shared exposure:'):
                nba_trial.record_publish(offer, NOW, root, preview_sent='2026-10-23T12:00:00Z')
            self.assertFalse(root.exists())

    def test_nba_grading_uses_each_original_stake(self):
        rows = [{'id': 'old', 'type': 'publish', 'odds': 100, 'riskUnits': 1},
                {'id': 'new', 'type': 'publish', 'odds': 100, 'riskUnits': .5},
                {'id': 'old', 'type': 'settle', 'result': 'win', 'source': 'ESPN'},
                {'id': 'new', 'type': 'settle', 'result': 'loss', 'source': 'ESPN'}]
        self.assertEqual(nba_trial.snapshot(rows)['units'], .5)

    def test_pending_release_requires_latest_exact_price(self):
        row = {'league': 'CFB', 'pick': pick(book='DraftKings', odds=-108,
               quotedAt='2026-10-23T14:25:00Z', expiresAt='2026-10-23T21:30:00Z')}
        with mock.patch.object(gates, 'totals_policy', return_value=gates.Decision(True, 'test', 'ok')), \
                mock.patch.object(gates, 'exact_price_pairs', return_value=[{'book': 'DraftKings', 'side': -110}]):
            self.assertIn('latest capture', run.private_release_refusal(row, context(), NOW))
        with mock.patch.object(gates, 'totals_policy', return_value=gates.Decision(True, 'test', 'ok')), \
                mock.patch.object(gates, 'exact_price_pairs', return_value=[{'book': 'DraftKings', 'side': -108}]):
            self.assertIsNone(run.private_release_refusal(row, context(), NOW))


if __name__ == '__main__':
    unittest.main()
