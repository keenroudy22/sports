"""Owner focus changes capacity order, never prices, proof or historical results."""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import coverage_priority as focus
import run
import nba_capture
import nba_trial_runtime


class CoveragePriorityTests(unittest.TestCase):
    def test_eastern_game_day_and_effective_clock(self):
        now = focus.EFFECTIVE
        # Saturday UTC is still Friday evening in Indiana.
        self.assertEqual(focus.tier('CFB', '2026-10-31T01:00:00Z', now), 1)
        self.assertEqual(focus.tier('CFB', '2026-11-01T01:00:00Z', now), 0)
        self.assertEqual(focus.tier('CFB', '2026-11-02T01:00:00Z', now), 0)
        self.assertEqual(focus.tier('CFB', '2026-11-03T01:00:00Z', now), 1)
        for league in ('NFL', 'NBA'):
            self.assertEqual(focus.tier(league, '2026-10-30T23:00:00Z', now), 0)
        self.assertEqual(focus.tier('CFB', None, now), 1)
        self.assertEqual(focus.tier('CFB', 'bad', now), 1)
        self.assertEqual(focus.tier('CFB', '2026-10-30T23:00:00Z', now-timedelta(seconds=1)), 0)

    def test_finite_football_research_reviews_weekend_before_weekday(self):
        from tests.test_gates import context
        games = {
            'friday': dict(league='CFB', kickoff='2026-10-30T23:00:00Z'),
            'saturday': dict(league='CFB', kickoff='2026-10-31T19:00:00Z'),
            'sunday': dict(league='NFL', kickoff='2026-11-01T18:00:00Z'),
        }
        rows = [dict(id=key, gameIds=[key], marketType='spread', _league=g['league'],
                     _row={'grade': {'edge': 5}}) for key, g in games.items()]
        ctx = context(games=games)
        ctx.now = focus.EFFECTIVE
        self.assertEqual([r['id'] for r in run.rank_card(rows, ctx)], ['saturday', 'sunday', 'friday'])
        ctx.now = focus.EFFECTIVE-timedelta(seconds=1)
        self.assertEqual([r['id'] for r in run.rank_card(rows, ctx)], ['friday', 'saturday', 'sunday'])

    def test_new_focus_prioritizes_primary_sports_and_makes_weekday_college_research_only(self):
        import gates
        from tests.test_gates import context
        now=focus.PROPS_FOCUS_FROM
        saturday='2026-10-31T19:00:00Z';friday='2026-11-07T01:00:00Z'
        self.assertEqual(focus.tier('NFL',saturday,now),0)
        self.assertEqual(focus.tier('NBA',saturday,now),0)
        self.assertEqual(focus.tier('CFB',saturday,now),1)
        self.assertEqual(focus.tier('CFB',friday,now),4)
        self.assertLess(focus.tier('CFB',saturday,now),focus.tier('NFL','2026-11-01T18:00:00Z',now))
        self.assertFalse(focus.research_only('CFB','2026-11-01T18:00:00Z',now))
        ctx=context(games={'college':dict(league='CFB',kickoff=friday)})
        ctx.now=now
        candidate=dict(league='CFB',gameIds=['college'],kickoff=friday)
        self.assertFalse(gates.owner_coverage(candidate,ctx).ok)
        for kind in ('modelLean','propLean','favorite','researched','longshot','ladder'):
            self.assertIn(gates.owner_coverage,gates.RULES[kind])
        self.assertNotIn(gates.owner_coverage,gates.RULES['revision'])
        ctx.now=now-timedelta(seconds=1)
        self.assertTrue(gates.owner_coverage(candidate,ctx).ok)
        ctx.now=now;ctx.games['college']['kickoff']=saturday
        self.assertTrue(gates.owner_coverage(candidate,ctx).ok)
        self.assertFalse(focus.research_only('NFL',friday,now))
        ctx.games['college']['kickoff']=friday
        candidate['id']='already-public'
        ctx.first['already-public']={'publishedAt':(now-timedelta(seconds=1)).isoformat()}
        self.assertTrue(gates.owner_coverage(candidate,ctx).ok)

    def test_nba_prop_preference_preserves_every_admission_check_and_falls_through_when_held(self):
        import tempfile
        from contextlib import ExitStack
        import buffer_post
        import nba_trial
        now=focus.PROPS_FOCUS_FROM+timedelta(hours=1)
        offers=[dict(id='game',marketType='moneyline'),dict(id='prop',marketType='player')]
        for held,expected in ((False,'prop'),(True,'game')):
            with ExitStack() as stack, tempfile.TemporaryDirectory() as folder:
                clock=stack.enter_context(patch.object(nba_trial_runtime,'datetime',wraps=datetime));clock.now.return_value=now
                stack.enter_context(patch.dict(os.environ,{'BUFFER_TOKEN':'fixture'}))
                stack.enter_context(patch.object(nba_trial_runtime,'review_ready',return_value=True))
                stack.enter_context(patch.object(nba_trial_runtime,'rows',return_value=[]))
                stack.enter_context(patch.object(nba_trial_runtime,'candidates',return_value=offers))
                stack.enter_context(patch.object(buffer_post,'pending_scheduled',return_value=0))
                stack.enter_context(patch.object(buffer_post,'day_count',return_value=0))
                stack.enter_context(patch.object(nba_trial.staking,'apply'))
                checked=stack.enter_context(patch.object(nba_trial,'evaluate',side_effect=lambda offer,*a,**k:['role hold'] if held and offer['id']=='prop' else []))
                published=stack.enter_context(patch.object(nba_trial,'record_publish'))
                result=nba_trial_runtime.admission(now,root=Path(folder),log_book={'posts':[]},review={},capture=False)
            self.assertEqual(result['id'],expected)
            self.assertEqual(checked.call_args_list[0].args[0]['id'],'prop')
            self.assertEqual(published.call_args.args[0]['id'],expected)

    def test_prop_capture_moves_to_existing_early_slot_with_failure_no_second_attempt(self):
        now = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)
        args = SimpleNamespace(command='run', dry_run=False, now=None, no_push=False)
        status = {'errors': []}
        with patch.dict(os.environ, {'KEENROUDY_SPORTS_CAPTURE': '1'}), \
             patch.object(nba_capture, 'step', return_value={}), \
             patch.object(run, 'record_nba_roster_capture'), \
             patch.object(nba_trial_runtime, 'admission', return_value={'state': 'held'}), \
             patch.object(run, 'capture_nba_props_and_select', side_effect=ValueError('offline')) as props, \
             patch.object(run, 'log'):
            run.early_nba_selection(args, now, now.astimezone(run.EASTERN), status)
        props.assert_called_once_with(args, now, status)
        self.assertTrue(status['nbaPropsEarlyAttempted'])
        self.assertEqual(len(status['errors']), 1)

    def test_no_new_capture_windows_or_capture_when_disabled(self):
        now = datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc)
        args = SimpleNamespace(command='run', dry_run=False)
        with patch.object(run, 'capture_nba_props_and_select') as props:
            run.early_nba_selection(args, now, now.astimezone(run.EASTERN), {'errors': []})
            with patch.dict(os.environ, {'KEENROUDY_SPORTS_CAPTURE': '0'}):
                run.early_nba_selection(args, now, now.replace(hour=13).astimezone(run.EASTERN), {'errors': []})
        props.assert_not_called()

    def test_one_quote_request_prioritizes_nfl_over_weeknight_cfb(self):
        import tempfile
        import sharp_odds
        now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        games = [dict(id='CFB-1', league='CFB', state='pre', kickoff='2026-11-02T23:00:00Z'),
                 dict(id='NFL-1', league='NFL', state='pre', kickoff='2026-11-03T01:00:00Z')]
        for game in games:
            game.update(home={'name': 'Home'}, away={'name': 'Away'})
        calls = []
        def fetch(path, key, **params):
            calls.append((path, params['league']))
            return {'data': []}
        with tempfile.TemporaryDirectory() as folder:
            sharp_odds.capture({'games': games}, now, 'fixture', fetch=fetch,
                               sleep=lambda _: None, root=Path(folder), log=lambda *args: None, requests=1)
        self.assertEqual(calls, [('/events', 'nfl')])

    def test_morning_research_prefers_valid_nba_watch_but_retains_cfb_if_none(self):
        import morning_brief
        now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
        row = dict(id='line', gameId='CFB-1', league='CFB', title='Team over 40.5', line=40.5,
                   odds=-110, book='FanDuel', observedAt='2026-11-03T11:45:00Z',
                   kickoff='2026-11-03T23:00:00Z', grade=dict(projection=45, calibrated=True, edge=2))
        screened = [dict(gameId='CFB-1', title=row['title'], rule='held', reason='availability')]
        nba = {'playerProps': {'availabilityAt': row['observedAt'], 'rows': [dict(
            favorite=True, roleReview={'checkedAt': row['observedAt']}, sourceAt=row['observedAt'],
            projection={'value': 22, 'minutes': 32}, line=20.5, odds=-110, kickoff=row['kickoff'],
            name='Player', side='over', statName='points', book='DraftKings')]}}
        watch = morning_brief.choose(now, [row], screened, nba)
        self.assertEqual(watch['league'], 'NBA')
        self.assertIn('still need testing', watch['missing'])
        self.assertEqual(morning_brief.choose(now, [row], screened, {})['league'], 'CFB')
