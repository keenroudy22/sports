import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run
import buffer_post


class SlotTests(unittest.TestCase):
    def test_nba_game_and_prop_capture_reuse_six_windows_without_an_afternoon_freshness_hole(self):
        windows = [(6,45),(8,30),(10,0),(11,45),(13,30),(16,0),(17,30),(20,0),(21,0),(23,30)]
        selected = [datetime(2026,10,23,h,m,tzinfo=run.EASTERN) for h,m in windows
                    if run.nba_game_capture_due(datetime(2026,10,23,h,m,tzinfo=run.EASTERN))]
        self.assertEqual([(t.hour,t.minute) for t in selected],[(6,45),(8,30),(11,45),(13,30),(17,30),(21,0)])
        self.assertEqual(len(selected),6)
        self.assertLessEqual(max(b-a for a,b in zip(selected,selected[1:])),timedelta(hours=4))
        self.assertIn(23,run.PAPER_SLOTS,'late paper grading is not removed')
        source=Path(run.__file__).read_text()
        self.assertIn("and 'nbaCapture' not in status and args.command != 'run'", source,
                      'non-run capture fallback cannot duplicate the early run capture')
        self.assertEqual(source.count("status['nbaPlayerProps']=nba_player_props.capture("),1,'one prop capture path')
        self.assertIn("status['nbaPlayerPropGraded'] = nba_player_props.grade(now)",source,'late prop grading is retained')
        self.assertNotIn("slot.hour in PAPER_SLOTS or (slot.hour,slot.minute) in ((6,45),(8,30))",source)

    def test_nba_trial_fallback_cannot_recreate_moved_late_night_capture(self):
        at=lambda h,m:datetime(2026,10,23,h,m,tzinfo=run.EASTERN)
        self.assertFalse(run.nba_trial_needs_capture(at(23,30),{}))
        self.assertFalse(run.nba_trial_needs_capture(at(17,30),{'nbaCapture':{'requests':20}}))
        self.assertTrue(run.nba_trial_needs_capture(at(17,30),{}),'failed daytime capture may retry within existing trial budget')
        self.assertTrue(run.nba_trial_needs_capture(at(16,0),{}),'existing daytime admission refresh is retained')
        self.assertIn('nba_trial_runtime.admission(now, capture=nba_trial_needs_capture(slot, status))',Path(run.__file__).read_text())

    def test_buffer_cooldown_is_delivery_delay_not_permanent_validation_hold(self):
        import release_queue
        now=datetime(2026,10,20,14,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(run,'CONF',Path(folder)),mock.patch.object(run,'alert') as alert:
            release_queue.save(Path(folder),{'plays':[{'id':'climb'}]})
            def runner(*args,**kwargs):raise buffer_post.BufferRateLimited(now+timedelta(hours=1),'24h')
            self.assertEqual(run.release_private_isolated(now,runner=runner,log=lambda *_:None),[])
            row=release_queue.load(Path(folder))['plays'][0]
            self.assertFalse(row.get('held',False));self.assertIn('15:00',row['bufferRetryAt'])
            alert.assert_not_called()
    def test_new_private_card_uses_release_time_before_a_publication_timestamp_exists(self):
        import ticket_card
        now = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)
        pick = {'id': 'NFL-new', 'athleteId': '1', 'market': 'rec'}
        game = {'home': {'id': '10'}, 'away': {'id': '20'}}
        with mock.patch.object(run.pick_card, 'chrome_path', return_value='/Chrome'), \
             mock.patch.object(run.pick_card, 'artwork', return_value={}), \
             mock.patch.object(run.pick_card, 'ticket_enabled', return_value=True) as theme, \
             mock.patch.object(ticket_card, 'straight_svg', return_value='<svg/>') as ticket, \
             mock.patch.object(run.pick_card, 'render'), mock.patch('featured.of_day', return_value=None):
            run.render_private_play_card('NFL-new', pick, game, {}, SimpleNamespace(player_team={'1': '10'}), now, Path('/tmp/unused-private-card.png'))
        theme.assert_called_once_with(pick, moment=now)
        ticket.assert_called_once()
    def test_select_now_command_uses_the_actual_minute_even_outside_a_scheduled_window(self):
        with mock.patch.object(run, 'run', return_value=0) as desk:
            self.assertEqual(run.main(['--select-now', '--now', '2026-10-19T19:12:00Z']), 0)
        args = desk.call_args.args[0]
        self.assertEqual(args.slot, '1512')
        self.assertTrue(args.select_now)
        self.assertIsNone(args.publish_kinds)

    def test_earlier_official_release_is_not_pushed_behind_later_research(self):
        due = datetime(2026, 10, 17, 13, 35, tzinfo=timezone.utc)
        busy = [datetime(2026, 10, 17, 13, 24, tzinfo=timezone.utc),
                datetime(2026, 10, 17, 14, 36, tzinfo=timezone.utc)]
        self.assertEqual(buffer_post.free_slot(due, busy),
                         datetime(2026, 10, 17, 13, 44, tzinfo=timezone.utc))

    def test_results_command_is_a_current_slot_free_feed_settlement_pass(self):
        with mock.patch.object(run, 'run', return_value=0) as desk:
            self.assertEqual(run.main(['results', '--now', '2026-10-13T04:55:00Z']), 0)
        args = desk.call_args.args[0]
        self.assertEqual((args.slot, args.publish_kinds, args.no_llm), ('0055', 'settle,ladder', True))

    def test_every_official_release_lane_gets_a_draft_without_legacy_flags(self):
        for lane in run.PRIMETIME_COVERAGE_LANES:
            self.assertTrue(run.draft_postable({'lane': lane}), lane)
        self.assertTrue(run.draft_postable({'legs': [{'title': 'one'}]}))
        self.assertFalse(run.draft_postable({'lane': 'research', 'favorite': False, 'modelLean': False}))

    def test_slots_map_to_the_prompt_table_in_eastern_time(self):
        self.assertEqual(run.slot_for(datetime(2026, 9, 27, 11, 5, tzinfo=timezone.utc)).strftime('%H%M'), '0645')   # 7:05 ET Sunday
        self.assertEqual(run.slot_for(datetime(2026, 9, 27, 19, 20, tzinfo=timezone.utc)).strftime('%H%M'), '1445')  # 3:20 ET Sunday
        self.assertIsNone(run.slot_for(datetime(2026, 9, 29, 19, 20, tzinfo=timezone.utc)), 'no 14:45 on a Tuesday')
        self.assertIsNone(run.slot_for(datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)), '10:00 ET is between runs')
        self.assertEqual(run.slot_for(datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)).strftime('%Y-%m-%d %H%M'), '2026-09-27 2330')

    def test_slots_across_the_dst_change(self):
        self.assertEqual(run.slot_for(datetime(2026, 11, 1, 11, 50, tzinfo=timezone.utc)).strftime('%H%M'), '0645')  # EST
        self.assertEqual(run.slot_for(datetime(2026, 3, 8, 10, 50, tzinfo=timezone.utc)).strftime('%H%M'), '0645')   # EDT

    def test_forced_slot(self):
        self.assertEqual(run.slot_for(datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc), '1145').strftime('%H%M'), '1145')

    def test_530_rechecks_evening_nfl_and_college_including_a_served_game(self):
        now = datetime(2026, 10, 11, 21, 30, tzinfo=timezone.utc)
        slot = now.astimezone(run.EASTERN)
        games = {
            'NFL-dark': {'id': 'NFL-dark', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-12T00:20:00Z'},
            'NFL-early': {'id': 'NFL-early', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-11T17:00:00Z'},
            'CFB-night': {'id': 'CFB-night', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-12T00:00:00Z'},
        }
        ctx = SimpleNamespace(first={}, latest={})
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-dark', 'CFB-night'})
        ctx.first['posted'] = {'gameIds': ['NFL-dark'], 'status': 'active', 'lane': 'best_bet'}
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-dark', 'CFB-night'},
                         'a second non-contradictory play from the same game remains eligible')
        morning = datetime(2026, 10, 11, 6, 45, tzinfo=run.EASTERN)
        self.assertIsNone(run.official_selection_scope(morning, games, ctx, now))

    def test_friday_college_gets_existing_evening_check_without_opening_future_or_live_games(self):
        now = datetime(2026, 10, 23, 17, 30, tzinfo=run.EASTERN)
        game = {'id': 'CFB-night', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-23T23:00:00Z'}
        games = {'CFB-night': game, 'live': dict(game, id='live', state='in'),
                 'past': dict(game, id='past', kickoff='2026-10-22T23:00:00Z'),
                 'tomorrow': dict(game, id='tomorrow', kickoff='2026-10-24T23:00:00Z'),
                 'nba': dict(game, id='nba', league='NBA')}
        self.assertEqual(run.official_selection_scope(now, games, SimpleNamespace(first={}, latest={}), now), {'CFB-night'})
        with mock.patch.dict(os.environ, {'KEENROUDY_SELECTION_PRIMETIME': '0'}):
            self.assertEqual(run.official_selection_scope(now, games, SimpleNamespace(first={}, latest={}), now), set())

    def test_650_rechecks_the_same_still_dark_primetime_game(self):
        now = datetime(2026, 10, 12, 22, 50, tzinfo=timezone.utc)
        slot = now.astimezone(run.EASTERN)
        games = {
            'NFL-mnf': {'id': 'NFL-mnf', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-13T00:15:00Z'},
            'NFL-done': {'id': 'NFL-done', 'league': 'NFL', 'state': 'post', 'kickoff': '2026-10-12T17:00:00Z'},
        }
        ctx = SimpleNamespace(first={}, latest={})
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-mnf'})
        with mock.patch.dict(os.environ, {'KEENROUDY_SELECTION_PRIMETIME': '0'}):
            self.assertEqual(run.official_selection_scope(slot, games, ctx, now), set())

    def test_withdrawn_unposted_bills_rams_play_does_not_cover_mnf(self):
        now = datetime(2026, 10, 12, 22, 50, tzinfo=timezone.utc)
        slot = now.astimezone(run.EASTERN)
        games = {'NFL-401872994': {'id': 'NFL-401872994', 'league': 'NFL', 'state': 'pre',
                                   'kickoff': '2026-10-13T00:15:00Z'}}
        withdrawn = {'id': 'NFL-2026-W5-buf-lar-under-54-5-dk', 'gameIds': ['NFL-401872994'],
                     'lane': 'best_bet', 'status': 'withdrawn', 'posted': False,
                     'publishedAt': '2026-10-07T13:30:00Z'}
        ctx = SimpleNamespace(first={withdrawn['id']: withdrawn}, latest={}, now=now)
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-401872994'})

    def test_primetime_passes_refresh_sharpapi_before_selection(self):
        for hour, minute in ((17, 30), (18, 50)):
            slot = datetime(2026, 10, 12, hour, minute, tzinfo=run.EASTERN)
            completed = SimpleNamespace(stdout='fresh', stderr='', returncode=0)
            with mock.patch.object(run.subprocess, 'run', return_value=completed) as invoke:
                run.capture(slot, python='python-test')
            scripts = [Path(call.args[0][1]).name for call in invoke.call_args_list]
            self.assertEqual(scripts, ['odds_api.py', 'prop_odds.py', 'sharp_odds.py'])
            self.assertEqual(invoke.call_args_list[-1].kwargs['env']['SHARP_REQUESTS'], '10' if hour == 17 else '15')

    def test_830_pass_refreshes_sharpapi_before_selection(self):
        slot = datetime(2026, 10, 18, 8, 30, tzinfo=run.EASTERN)
        completed = SimpleNamespace(stdout='fresh', stderr='', returncode=0)
        with mock.patch.object(run.subprocess, 'run', return_value=completed) as invoke:
            run.capture(slot, python='python-test')
        scripts = [Path(call.args[0][1]).name for call in invoke.call_args_list]
        self.assertEqual(scripts, ['odds_api.py', 'prop_odds.py', 'sharp_odds.py'])
        self.assertEqual(invoke.call_args_list[-1].kwargs['env']['SHARP_REQUESTS'], '10')

    def test_730_pass_refreshes_prices_and_rechecks_early_games(self):
        now = datetime(2026, 10, 18, 11, 30, tzinfo=timezone.utc)  # 7:30 AM ET
        slot = now.astimezone(run.EASTERN)
        games = {
            'NFL-london': {'id': 'NFL-london', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-18T13:30:00Z'},
            'NFL-noon': {'id': 'NFL-noon', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-18T17:00:00Z'},
        }
        ctx = SimpleNamespace(first={}, latest={})
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-london'})
        completed = SimpleNamespace(stdout='fresh', stderr='', returncode=0)
        with mock.patch.object(run.subprocess, 'run', return_value=completed) as invoke:
            run.capture(slot, python='python-test')
        scripts = [Path(call.args[0][1]).name for call in invoke.call_args_list]
        self.assertEqual(scripts, ['odds_api.py', 'prop_odds.py', 'sharp_odds.py'])
        with mock.patch.dict(os.environ, {'KEENROUDY_SELECTION_0730': '0'}):
            self.assertEqual(run.official_selection_scope(slot, games, ctx, now), set())

    def test_open_climb_leg_does_not_count_as_primetime_coverage(self):
        now = datetime(2026, 10, 11, 22, 50, tzinfo=timezone.utc)
        slot = now.astimezone(run.EASTERN)
        games = {
            'NFL-snf': {'id': 'NFL-snf', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-12T00:20:00Z'},
        }
        ctx = SimpleNamespace(first={
            'climb': {'gameIds': ['NFL-snf'], 'status': 'active', 'lane': 'ladder', 'parlayType': 'ladder'},
            'fun': {'gameIds': ['NFL-snf'], 'status': 'active', 'parlayType': 'longshot'},
        }, latest={})
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-snf'})
        ctx.first['straight'] = {'gameIds': ['NFL-snf'], 'status': 'active', 'lane': 'gut_call'}
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-snf'},
                         'an existing straight does not block another non-contradictory primetime play')

    def test_private_release_refuses_an_expired_quote_before_discord(self):
        now = datetime(2026, 10, 13, 14, 40, tzinfo=timezone.utc)
        row = {'league': 'NFL', 'pick': {'marketType': 'player',
               'quotedAt': '2026-10-13T10:45:00Z', 'expiresAt': '2026-10-13T12:30:00Z'}}
        self.assertIn('expired at', run.private_release_refusal(row, SimpleNamespace(), now))

    def test_one_bad_private_release_is_held_while_the_next_row_continues(self):
        import release_queue
        now = datetime(2026, 10, 13, 14, 40, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(run, 'CONF', Path(folder)), \
                mock.patch.object(run, 'alert'):
            release_queue.save(Path(folder), {'plays': [{'id': 'bad'}, {'id': 'good'}]})
            seen = []

            def runner(_now, log, only):
                key = next(iter(only))
                seen.append(key)
                if key == 'bad':
                    raise AssertionError('invalid private row')
                return [key]

            self.assertEqual(run.release_private_isolated(now, log=lambda *_: None, runner=runner), ['good'])
            stored = release_queue.load(Path(folder))['plays']
            self.assertTrue(next(row for row in stored if row['id'] == 'bad')['held'])
            self.assertEqual(seen, ['bad', 'good'])

    def test_artifact_failure_stays_retryable_while_the_next_row_releases(self):
        import release_queue
        now = datetime(2026, 10, 13, 14, 40, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(run, 'CONF', Path(folder)), \
                mock.patch.object(run, 'alert') as alert:
            release_queue.save(Path(folder), {'plays': [{'id': 'art'}, {'id': 'good'}]})
            seen = []

            def runner(_now, log, only):
                key = next(iter(only))
                seen.append(key)
                if key == 'art':
                    raise run.ReleaseArtifactError('card text is outside the printed margin')
                return [key]

            self.assertEqual(run.release_private_isolated(now, log=lambda *_: None, runner=runner), ['good'])
            stored = release_queue.load(Path(folder))['plays']
            failed = next(row for row in stored if row['id'] == 'art')
            self.assertFalse(failed.get('held', False))
            self.assertEqual(failed['artifactState'], 'recovery-needed')
            self.assertIn('outside the printed margin', failed['artifactError'])
            alert.assert_called_once()
            run.release_private_isolated(now + timedelta(minutes=5), log=lambda *_: None, runner=runner)
            alert.assert_called_once()

    def test_830_selection_pass_rechecks_unserved_noon_and_later_games(self):
        now = datetime(2026, 10, 11, 12, 30, tzinfo=timezone.utc)
        slot = now.astimezone(run.EASTERN)
        games = {
            'NFL-london': {'id': 'NFL-london', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-11T13:30:00Z'},
            'NFL-noon': {'id': 'NFL-noon', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-11T16:00:00Z'},
            'CFB-late': {'id': 'CFB-late', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-11T23:00:00Z'},
        }
        ctx = SimpleNamespace(first={'posted': {'gameIds': ['CFB-late'], 'status': 'active', 'lane': 'best_bet'}}, latest={})
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'NFL-noon', 'CFB-late'})
        with mock.patch.dict(os.environ, {'KEENROUDY_SELECTION_0830': '0'}):
            self.assertEqual(run.official_selection_scope(slot, games, ctx, now), set())

    def test_monday_night_is_screened_in_both_morning_passes_not_only_primetime(self):
        game = {'id': 'NFL-mnf', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-20T00:15:00Z'}
        ctx = SimpleNamespace(first={}, latest={})
        for hour, minute in ((8, 30), (11, 45)):
            now = datetime(2026, 10, 19, hour, minute, tzinfo=run.EASTERN)
            self.assertEqual(run.official_selection_scope(now, {'NFL-mnf': game}, ctx, now), {'NFL-mnf'})

    def test_owner_requested_selection_uses_real_now_without_a_fabricated_primetime_slot(self):
        now = datetime(2026, 10, 19, 13, 20, tzinfo=run.EASTERN)
        game = {'id': 'NFL-mnf', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-20T00:15:00Z'}
        games = {'NFL-mnf': game, 'tomorrow': {**game, 'kickoff': '2026-10-21T00:15:00Z'},
                 'started': {**game, 'kickoff': '2026-10-19T16:00:00Z'}, 'live': {**game, 'state': 'in'}}
        ctx = SimpleNamespace(first={}, latest={})
        self.assertEqual(run.official_selection_scope(now, games, ctx, now), set())
        self.assertEqual(run.official_selection_scope(now, games, ctx, now, True), {'NFL-mnf'})

    def test_college_candidates_use_bounded_web_checks_beyond_raw_top_six(self):
        college = {'league': 'CFB', 'gameIds': ['CFB-late']}
        nfl = {'league': 'NFL', 'gameIds': ['NFL-late']}
        self.assertTrue(run.should_research_candidate(college, 27, 2.0, True))
        self.assertFalse(run.should_research_candidate(nfl, 27, 2.0, True))
        self.assertTrue(run.should_research_candidate(nfl, 2, 2.0, False))
        self.assertTrue(run.should_research_candidate(nfl, 27, 16.0, True))

    def test_research_budget_skips_losing_prices_and_reserves_market_families(self):
        status = {'asked': 0, 'families': {}}
        losing = {'athleteId': '1', '_selection': {'anchoredChance': .49, 'breakEven': .50}}
        self.assertFalse(run.research_slot_available(losing, status))
        for athlete in range(5):
            prop = {'athleteId': str(athlete), '_selection': {'anchoredChance': .55, 'breakEven': .50}}
            self.assertTrue(run.research_slot_available(prop, status))
            status['asked'] += 1
            run.note_research_slot(prop, status)
        sixth = {'athleteId': '6', '_selection': {'anchoredChance': .56, 'breakEven': .50}}
        side = {'marketType': 'spread', '_selection': {'anchoredChance': .56, 'breakEven': .50}}
        total = {'marketType': 'total', '_selection': {'anchoredChance': .56, 'breakEven': .50}}
        self.assertFalse(run.research_slot_available(sixth, status))
        self.assertTrue(run.research_slot_available(side, status))
        self.assertTrue(run.research_slot_available(total, status))

    def test_research_holds_distinguish_bad_price_budget_and_missing_availability(self):
        candidate = {'marketType': 'spread', '_selection': {'anchoredChance': .49, 'breakEven': .50}}
        self.assertIn('does not beat the price', run.research_slot_refusal(candidate, {'asked': 0}))
        candidate['_selection']['anchoredChance'] = .55
        self.assertIn('eight-check', run.research_slot_refusal(candidate, {'asked': 8}))
        self.assertIn('side research allocation', run.research_slot_refusal(candidate, {'asked': 2, 'families': {'side': 2}}))
        self.assertIsNone(run.research_slot_refusal(candidate, {'asked': 0}))

    def test_large_weekend_slate_targets_five_honest_straights(self):
        saturday = datetime(2026, 10, 17).date()
        games = {str(i): {'league': 'CFB', 'kickoff': f'2026-10-17T{16 + i % 8:02d}:00:00Z'}
                 for i in range(12)}
        self.assertEqual(run.straight_target(saturday, games), 5)
        self.assertEqual(run.straight_target(saturday, dict(list(games.items())[:9])), 1)
        self.assertEqual(run.straight_target(datetime(2026, 10, 19).date(), games), 1)

    def test_nfl_side_gets_a_numbered_projection_reason_only_when_materially_through_the_spread(self):
        game = {'id': 'NFL-side', 'league': 'NFL', 'source': 'https://example.test/game',
                'home': {'id': 'GB', 'short': 'Packers'},
                'away': {'id': 'DAL', 'short': 'Cowboys'}}
        ctx = SimpleNamespace(now=datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc), games={'NFL-side': game},
                              odds_history={})
        pick = {'gameIds': ['NFL-side'], 'marketType': 'spread', 'direction': 'home', 'line': -1.0,
                '_desk': {'projection': 3.5}, '_evidence': [], '_research': []}
        reasons = run.plan_reasons(pick, ctx)
        self.assertEqual(reasons[0]['type'], 'projection_edge')
        self.assertEqual(reasons[0]['number']['pointsThrough'], 2.5)
        self.assertIn('Packers -1', reasons[0]['text'])
        self.assertEqual(run.plan_reasons(dict(pick, _desk={'projection': 1.9}), ctx), [])

    def test_large_slate_builds_defense_history_once_per_league(self):
        ctx = run.gates.Context(now=datetime(2026, 10, 17, 12, 30, tzinfo=timezone.utc), records=[{'id': 'stored'}])
        with mock.patch.object(run.features, 'defense_logs', return_value={'1': []}) as build:
            self.assertEqual(run.cached_defense_logs(ctx, 'CFB'), {'1': []})
            self.assertEqual(run.cached_defense_logs(ctx, 'CFB'), {'1': []})
            self.assertEqual(run.cached_defense_logs(ctx, 'NFL'), {'1': []})
        self.assertEqual(build.call_count, 2)

    def test_1145_selection_pass_gives_an_unserved_game_day_one_more_fresh_look(self):
        now = datetime(2026, 10, 15, 15, 45, tzinfo=timezone.utc)
        slot = now.astimezone(run.EASTERN)
        games = {
            'CFB-night': {'id': 'CFB-night', 'league': 'CFB', 'state': 'pre',
                          'kickoff': '2026-10-15T23:30:00Z'},
            'NFL-night': {'id': 'NFL-night', 'league': 'NFL', 'state': 'pre',
                          'kickoff': '2026-10-16T00:15:00Z'},
            'CFB-served': {'id': 'CFB-served', 'league': 'CFB', 'state': 'pre',
                           'kickoff': '2026-10-15T23:30:00Z'},
        }
        ctx = SimpleNamespace(first={
            'posted': {'gameIds': ['CFB-served'], 'status': 'active', 'lane': 'gut_call'}
        }, latest={})
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now),
                         {'CFB-night', 'NFL-night', 'CFB-served'})

    def test_later_weekend_pass_can_fill_five_from_a_game_that_already_has_one(self):
        now = datetime(2026, 10, 17, 12, 30, tzinfo=timezone.utc)
        slot = now.astimezone(run.EASTERN)
        games = {
            'CFB-one': {'id': 'CFB-one', 'league': 'CFB', 'state': 'pre',
                        'kickoff': '2026-10-17T19:30:00Z'},
            'CFB-two': {'id': 'CFB-two', 'league': 'CFB', 'state': 'pre',
                        'kickoff': '2026-10-17T23:00:00Z'},
        }
        ctx = SimpleNamespace(first={
            'first': {'gameIds': ['CFB-one'], 'status': 'active', 'lane': 'hot_plate'}
        }, latest={})
        self.assertEqual(run.official_selection_scope(slot, games, ctx, now), {'CFB-one', 'CFB-two'})


class CandidateCatalogTests(unittest.TestCase):
    def test_price_shops_the_full_capture_when_a_catalog_row_has_only_one_book(self):
        now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        game = {'id': 'CFB-1', 'league': 'CFB', 'season': 2026, 'week': 7,
                'kickoff': '2026-10-15T23:30:00Z',
                'away': {'id': '1', 'abbreviation': 'CSU', 'name': 'Colorado State'},
                'home': {'id': '2', 'abbreviation': 'TXST', 'name': 'Texas State'}}
        odds = {'retrievedAt': now.isoformat(), 'books': {
            'betmgm': {'spread': {'home': 14, 'homePrice': -105, 'awayPrice': -115}},
            'draftkings': {'spread': {'home': 14, 'homePrice': -105, 'awayPrice': -120}},
            'hardrockbet': {'spread': {'home': 13.5, 'homePrice': 100, 'awayPrice': -120}},
        }}
        ctx = SimpleNamespace(games={'CFB-1': game}, snapshot=lambda game_id: {'gameId': game_id},
                              odds={'CFB-1': odds}, prop_odds={}, names={})
        candidate = {'gameIds': ['CFB-1'], 'marketType': 'spread', 'direction': 'home',
                     '_quotes': [('BetMGM', 14, -105)], '_row': {'observedAt': now.isoformat()}}

        def numbers(row, _ctx):
            edge = .016 if row.get('book') == 'DraftKings' else .003
            return {'chance': .52, 'breakEven': .512, 'edgePoints': .8, 'evPerUnit': edge,
                    'calibration': 'test', 'calibrated': True, 'fairChance': .51,
                    'anchoredChance': .52, 'gap': .8, 'calibrationFamily': 'spread'}

        desk = {'projection': -11, 'cutoff': 'Texas State +14 at -105 or better.', 'model': 'v2',
                'snapshotAt': now.isoformat(), 'rawChance': .53, 'push': 0}
        with mock.patch.object(run.pricing, 'price', return_value=desk), \
             mock.patch.object(run.gates, 'calibrated_desk', side_effect=lambda priced, *_: dict(priced)), \
             mock.patch.object(run.gates, 'selection_numbers', side_effect=numbers):
            chosen = run.price(candidate, ctx, now)
        self.assertEqual(chosen['book'], 'DraftKings')
        self.assertEqual(chosen['matchup'], 'Colorado State at Texas State')
        self.assertNotIn('Hard Rock', chosen['quoteNote'])

    def test_opposing_starting_qb_ruled_out_is_a_current_reason_for_a_primetime_side(self):
        now = datetime(2026, 10, 11, 22, 30, tzinfo=timezone.utc)
        game = {'id': 'NFL-401872993', 'league': 'NFL', 'state': 'pre',
                'kickoff': '2026-10-12T00:20:00Z',
                'away': {'id': '33', 'abbreviation': 'BAL'},
                'home': {'id': '1', 'abbreviation': 'ATL'}}
        candidate = {'gameIds': [game['id']], '_league': 'NFL', 'marketType': 'moneyline',
                     'direction': 'home', 'line': 0, 'odds': -110}
        ctx = SimpleNamespace(
            now=now, games={game['id']: game}, starters={'NFL-33': '123'}, player_team={}, odds={},
            odds_history={}, snapshot=lambda _game_id: {}, names={}, prop_odds={}, records=[])
        context_file = {'leagues': {'NFL': {'checkedAt': '2026-10-11T22:20:00Z', 'teams': {
            '33': {'players': [{'id': '123', 'name': 'Lamar Jackson', 'position': 'QB',
                               'status': 'out', 'source': 'https://www.espn.com/'}]}}}}}
        with mock.patch.object(run, 'weather_fact', return_value=None), \
                mock.patch.object(run.market_read, 'read', return_value={}), \
                mock.patch.object(run.market_read, 'sentences', return_value=''):
            facts = run.evidence(candidate, ctx, context_file)
        self.assertEqual(facts[0]['direction'], 'for')
        candidate['_evidence'] = facts
        self.assertEqual(run.plan_reasons(candidate, ctx)[0]['class'], 'A')
        self.assertIn('Lamar Jackson', run.post_reason(candidate, facts, ctx, []))

    def test_spreads_join_the_board_without_turning_off_exact_line_checks(self):
        now = datetime(2026, 10, 8, 13, 0, tzinfo=timezone.utc)
        game = {'id': 'CFB-1', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-08T19:00:00Z'}
        row = {'gameId': 'CFB-1', 'state': 'open', 'gameMarket': True, 'market': 'point spread',
               'side': 'away', 'line': 3.5, 'book': 'FanDuel', 'odds': -110,
               'grade': {'tier': 'strong', 'edge': 6.0, 'raw': 0.60}}
        picks = run.candidates([row], {'CFB-1': game}, now)
        self.assertEqual((len(picks), picks[0]['marketType'], picks[0]['direction'], picks[0]['modelLean']),
                         (1, 'spread', 'away', False))

    def test_plus_money_candidates_are_not_discarded_by_a_raw_hit_rate_floor(self):
        now = datetime(2026, 10, 19, 13, 0, tzinfo=run.EASTERN)
        game = {'id': 'NFL-mnf', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-20T00:15:00Z'}
        prop = {'gameId': game['id'], 'state': 'open', 'athleteId': '77', 'position': 'WR',
                'stat': 'recYds', 'direction': 'over', 'line': 59.5, 'odds': 180, 'book': 'DraftKings',
                'grade': {'raw': .41, 'edge': 2}, 'id': 'plus-prop'}
        side = {**prop, 'athleteId': None, 'gameMarket': True, 'market': 'moneyline', 'side': 'away', 'line': 0, 'id': 'plus-side'}
        picks = run.candidates([prop, side], {game['id']: game}, now)
        self.assertEqual(len(picks), 2, 'both candidates must reach price, reason and injury checks; this is not admission')

    def test_a_future_game_stays_on_the_board_but_cannot_be_admitted_early(self):
        now = datetime(2026, 10, 8, 13, 0, tzinfo=timezone.utc)
        game = {'id': 'CFB-1', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-09T19:00:00Z'}
        row = {'gameId': 'CFB-1', 'state': 'open', 'gameMarket': True, 'market': 'point spread',
               'side': 'away', 'line': 3.5, 'book': 'FanDuel', 'odds': -110,
               'grade': {'tier': 'strong', 'edge': 6.0, 'raw': 0.60}}
        self.assertEqual(run.candidates([row], {'CFB-1': game}, now), [])

    def test_two_numbered_dossier_reasons_and_no_hard_risk(self):
        good = {'reasons': [{'text': 'Our projection is 61.2 yards.'},
                            {'text': 'He cleared 49.5 in 4 of 5 full games.'}], 'risks': []}
        self.assertIsNone(run.dossier_support_issue(good))
        self.assertIsNotNone(run.dossier_support_issue({'reasons': good['reasons'][:1], 'risks': []}))
        self.assertIsNotNone(run.dossier_support_issue(dict(good, risks=[{'text': 'Starter out', 'hard': True}])))

    def test_invalid_strict_catalog_logs_and_skips_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lines.json'
            path.write_text(json.dumps({'count': 2, 'counts': {'NFL': 0, 'CFB': 2},
                                        'files': {'NFL': 'lines-NFL.json', 'CFB': 'lines-CFB.json'}}))
            (path.parent / 'lines-NFL.json').write_text(json.dumps({'league': 'NFL', 'lines': []}))
            messages = []
            self.assertEqual(run.load_candidate_lines(path, messages.append), [])
            self.assertIn('official selection skipped', messages[0])

    def test_ticket_research_uses_remaining_budget_and_stops_at_limit(self):
        ctx = SimpleNamespace(player_team={}, context_file={}, games={'g': {'id': 'g'}}, now=datetime.now(timezone.utc))
        ticket = {'_league': 'NFL', 'legs': [{'id': 'a', 'title': 'A', 'gameId': 'g', 'market': 'moneyline', 'side': 'home'}]}
        budget = {'on': True, 'asked': run.RESEARCH_LIMIT-1}
        reason = {'type': 'news', 'direction': 'for', 'text': 'Verified matchup fact'}
        with mock.patch.object(run, 'evidence', return_value=[]), mock.patch.object(
                run.researcher, 'enabled', return_value=True), mock.patch.object(
                run, 'quarterbacks', return_value={}), mock.patch.object(
                run.researcher, 'research', return_value=([{'claim': 'fact'}], [])) as lookup, mock.patch.object(
                run, 'plan_reasons', side_effect=[[], [reason], []]):
            self.assertEqual(run.attach_ticket_reasons(ticket, ctx, budget), [])
            self.assertEqual(lookup.call_args.args[2], 'home')
            self.assertEqual(budget['asked'], run.RESEARCH_LIMIT)
            self.assertEqual(run.attach_ticket_reasons(ticket, ctx, budget), ['A'])
            self.assertEqual(lookup.call_count, 1)

    def test_fun_ticket_needs_a_saved_reason_on_every_leg_and_can_forbid_replacement(self):
        ticket = {'_league': 'NFL', 'legs': [
            {'id': 'a', 'title': 'A +3', 'gameId': 'NFL-1', 'market': 'point spread', 'side': 'home'},
            {'id': 'b', 'title': 'B over 20.5', 'gameId': 'NFL-2', 'market': 'recYds',
             'side': 'over', 'athleteId': '2'},
        ]}
        ctx = SimpleNamespace(player_team={'2': '20'}, context_file={}, latest={})
        with mock.patch.object(run, 'evidence', return_value=[]), mock.patch.object(
                run, 'plan_reasons', side_effect=[
                    [{'type': 'matchup', 'direction': 'for', 'text': 'A faces the weaker run defense.'}], []]):
            self.assertEqual(run.attach_ticket_reasons(ticket, ctx), ['B over 20.5'])
        self.assertEqual(ticket['legs'][0]['reason'], 'A faces the weaker run defense.')
        self.assertIsNone(ticket['legs'][1]['reason'])
        self.assertTrue(run.ticket_replacement_allowed('ticket', ctx))
        ctx.latest['ticket'] = {'replacementAllowed': False}
        self.assertFalse(run.ticket_replacement_allowed('ticket', ctx))


class GradingTests(unittest.TestCase):
    GAME = {'id': 'NFL-1', 'league': 'NFL', 'kickoff': '2026-09-27T17:00:00Z',
            'home': {'short': 'Lions', 'abbreviation': 'DET', 'score': 27},
            'away': {'short': 'Bills', 'abbreviation': 'BUF', 'score': 24}, 'completed': True}

    def test_spread_and_total_grades(self):
        self.assertEqual(run.grade_game_pick({'marketType': 'spread', 'line': -2.5, 'direction': 'home'}, self.GAME), ('win', 'Bills 24, Lions 27', 3))
        self.assertEqual(run.grade_game_pick({'marketType': 'spread', 'line': -3, 'direction': 'home'}, self.GAME)[0], 'push')
        self.assertEqual(run.grade_game_pick({'marketType': 'spread', 'line': 2.5, 'direction': 'away'}, self.GAME)[0], 'loss')
        self.assertEqual(run.grade_game_pick({'marketType': 'total', 'line': 50.5, 'direction': 'over'}, self.GAME), ('win', 'Bills 24, Lions 27', 51))
        self.assertEqual(run.grade_game_pick({'marketType': 'total', 'line': 51, 'direction': 'under'}, self.GAME)[0], 'push')
        self.assertIsNone(run.grade_game_pick({'marketType': 'total', 'line': 51, 'direction': 'under'}, {'home': {}, 'away': {}}))

    def test_moneyline_grades_both_sides_without_treating_score_as_a_total(self):
        for side, expected in [('home', 'win'), ('away', 'loss')]:
            pick = {'marketType': 'moneyline', 'line': 0, 'direction': side}
            self.assertEqual(run.grade_game_pick(pick, self.GAME)[0], expected)
            tied = dict(self.GAME, away={'short': 'Bills', 'score': 27})
            self.assertEqual(run.grade_game_pick(pick, tied)[0], 'push')
        self.assertIsNone(run.grade_game_pick(dict(pick, direction='over'), self.GAME))

    def test_moneyline_ladder_settles_from_scores_without_player_stats(self):
        games = {key: dict(self.GAME, id=key) for key in ('NFL-1', 'NFL-2')}
        ticket = {'id': 'ladder-ml', 'league': 'NFL', 'gameIds': list(games),
                  'odds': -135, 'parlayType': 'ladder', 'legs': [
                      {'gameId': key, 'marketType': 'moneyline', 'line': 0, 'direction': 'home'}
                      for key in games]}
        ctx = SimpleNamespace(first={ticket['id']: ticket}, latest={})
        def no_box(*args):
            self.fail('Moneylines must not request player stats')
        raw = {ticket['id']: ('parlays', ticket)}
        settled, unclear = run.settle(ctx, raw, games, [], datetime(2026, 10, 18, tzinfo=timezone.utc), fetch=no_box)
        self.assertEqual(unclear, [])
        self.assertEqual(settled[0][2]['result'], 'win')
        ticket['legs'][1]['direction'] = 'away'
        settled, unclear = run.settle(ctx, raw, games, [], datetime(2026, 10, 18, tzinfo=timezone.utc), fetch=no_box)
        self.assertEqual((settled[0][2]['result'], unclear), ('loss', []))
        games['NFL-2']['completed'] = False
        self.assertEqual(run.settle(ctx, raw, games, [], datetime(2026, 10, 18, tzinfo=timezone.utc), fetch=no_box), ([], []))

    def test_prop_grades_from_the_box_score_and_absent_player_is_unclear(self):
        record = {'players': [{'id': '77', 'name': 'Player Seven', 'recYds': 61, 'rec': 5}]}
        pick = {'athleteId': '77', 'market': 'recYds', 'line': 49.5, 'direction': 'over'}
        self.assertEqual(run.grade_prop(pick, record), ('win', 'Player Seven: 61 receiving yards', 61))
        self.assertEqual(run.grade_prop(dict(pick, market='rec', line=5, direction='under'), record)[0], 'push')
        self.assertIsNone(run.grade_prop(dict(pick, athleteId='99'), record))
        self.assertIsNone(run.grade_prop(pick, None))

    def test_leg_shapes(self):
        self.assertEqual(run.leg_pick({'market': 'total points', 'side': 'over', 'line': 44.5})['marketType'], 'total')
        self.assertEqual(run.leg_pick({'marketType': 'spread', 'direction': 'away', 'line': 10.5}),
                         {'marketType': 'spread', 'line': 10.5, 'direction': 'away'})
        leg = run.leg_pick({'id': 'prop-NFL-1-77-recYds', 'market': 'receiving yards', 'side': 'over', 'line': 49.5, 'title': 'P over 49.5 receiving yards'})
        self.assertEqual(leg['athleteId'], '77')

    def test_a_ladder_of_manually_quoted_alternate_spreads_settles_automatically(self):
        games = {
            'CFB-1': {'id': 'CFB-1', 'league': 'CFB', 'completed': True,
                      'away': {'short': 'Pitt', 'score': 35}, 'home': {'short': 'Virginia Tech', 'score': 33}},
            'CFB-2': {'id': 'CFB-2', 'league': 'CFB', 'completed': True,
                      'away': {'short': 'Penn State', 'score': 13}, 'home': {'short': 'Northwestern', 'score': 34}},
        }
        ticket = {'id': 'CFB-ladder', 'league': 'CFB', 'parlayType': 'ladder', 'book': 'FanDuel', 'odds': -178,
                  'gameIds': ['CFB-1', 'CFB-2'],
                  'legs': [{'gameId': 'CFB-1', 'marketType': 'spread', 'direction': 'away', 'line': 10.5,
                            'title': 'Pitt +10.5'},
                           {'gameId': 'CFB-2', 'marketType': 'spread', 'direction': 'home', 'line': 12.5,
                            'title': 'Northwestern +12.5'}],
                  'ladder': {'run': 1, 'step': 2, 'stake': 75, 'payout': 117, 'banked': 19,
                             'bankThisWin': 23, 'bankedAfter': 42, 'nextStake': 94, 'totalAfter': 136}}
        ctx = SimpleNamespace(first={ticket['id']: dict(ticket)}, latest={})
        settled, unclear = run.settle(ctx, {ticket['id']: ('parlays', dict(ticket))}, games, [],
                                        datetime(2026, 10, 3, 10, 45, tzinfo=timezone.utc))
        self.assertEqual(unclear, [])
        self.assertEqual(settled[0][2]['result'], 'win')
        self.assertEqual(settled[0][2]['actual'], 'all 2 legs won')

    def test_a_losing_prop_waits_for_injury_review_and_never_assumes_a_push(self):
        now = datetime(2026, 9, 28, tzinfo=timezone.utc)
        pick = {'id': 'NFL-prop-77', 'league': 'NFL', 'gameIds': ['NFL-1'], 'athleteId': '77',
                'market': 'recYds', 'line': 49.5, 'direction': 'over', 'book': 'FanDuel', 'odds': -110}
        ctx = SimpleNamespace(first={pick['id']: dict(pick)}, latest={}, names={'77': 'Player Seven'})
        raw = {pick['id']: ('props', dict(pick))}
        records = [{'league': 'NFL', 'eventId': '1',
                    'players': [{'id': '77', 'name': 'Player Seven', 'recYds': 12}]}]
        clean = lambda game, player, now=None: {'checked': True, 'facts': [], 'dropped': []}
        settled, unclear = run.settle(ctx, raw, {'NFL-1': self.GAME}, records, now, injury_check=clean)
        self.assertEqual(settled[0][2]['result'], 'loss')
        self.assertEqual(unclear, [])

        injury = {'claim': 'Player Seven left in the first quarter and did not return.',
                  'source': 'https://www.example.com/injury'}
        hurt = lambda game, player, now=None: {'checked': True, 'facts': [injury], 'dropped': []}
        settled, unclear = run.settle(ctx, raw, {'NFL-1': self.GAME}, records, now, injury_check=hurt)
        self.assertEqual(settled, [])
        self.assertTrue(unclear[0]['settlementReview'])
        self.assertIn('no owner action is required', unclear[0]['why'])
        self.assertIn('injury alone is not a push or void', unclear[0]['why'].lower())

        later = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)
        settled, unclear = run.settle(ctx, raw, {'NFL-1': self.GAME}, records, later, injury_check=hurt)
        self.assertEqual(unclear, [])
        self.assertEqual(settled[0][2]['result'], 'loss')
        self.assertIn('no confirmed different FanDuel settlement', settled[0][2]['settlementReason'])
        self.assertEqual(settled[0][2]['settlementReviewSources'], ['https://www.example.com/injury'])
        self.assertEqual(settled[0][2]['injuryPlayers'], ['Player Seven'])

    def test_every_losing_player_leg_is_checked_and_one_injury_pauses_the_whole_parlay(self):
        now = datetime(2026, 9, 28, tzinfo=timezone.utc)
        ticket = {'id': 'NFL-parlay', 'league': 'NFL', 'gameIds': ['NFL-1'], 'book': 'FanDuel', 'odds': 100,
                  'legs': [{'gameId': 'NFL-1', 'athleteId': '77', 'market': 'recYds', 'line': 49.5,
                            'side': 'over', 'title': 'Player Seven 50+ receiving yards'},
                           {'gameId': 'NFL-1', 'athleteId': '88', 'market': 'recYds', 'line': 39.5,
                            'side': 'over', 'title': 'Player Eight 40+ receiving yards'}]}
        ctx = SimpleNamespace(first={ticket['id']: dict(ticket)}, latest={},
                              names={'77': 'Player Seven', '88': 'Player Eight'})
        raw = {ticket['id']: ('parlays', dict(ticket))}
        records = [{'league': 'NFL', 'eventId': '1',
                    'players': [{'id': '77', 'name': 'Player Seven', 'recYds': 12},
                                {'id': '88', 'name': 'Player Eight', 'recYds': 10}]}]
        checked = []

        def hurt(game, player, now=None):
            checked.append(player)
            facts = ([{'claim': 'Player Eight left in the first half and did not return.',
                       'source': 'https://www.example.com/injury'}] if player == 'Player Eight' else [])
            return {'checked': True, 'facts': facts, 'dropped': []}

        settled, unclear = run.settle(ctx, raw, {'NFL-1': self.GAME}, records, now, injury_check=hurt)
        self.assertEqual(settled, [])
        self.assertEqual(checked, ['Player Seven', 'Player Eight'])
        self.assertTrue(unclear[0]['settlementReview'])


class TextTests(unittest.TestCase):
    def test_entry_note_quotes_the_rule_and_the_numbers(self):
        now = datetime(2026, 9, 27, 20, 5, tzinfo=timezone.utc)
        pick = {'line': 31.5, 'odds': -110, 'cutoff': 'OVER 31.5 at -110 or better. Closed at 32+.'}
        note = run.entry_note(now, 'line moved 1 against, from 31.5 to 32.5', pick)
        self.assertTrue(note.startswith('Off the card:'))
        self.assertNotIn('4:05 PM ET', note)
        self.assertIn('from 31.5 to 32.5', note)
        self.assertIn('31.5 and -110', note)
        self.assertIn('graded as posted', note)

    def test_report_names_are_eastern_and_say_what_happened(self):
        now = datetime(2026, 9, 28, 3, 40, tzinfo=timezone.utc)       # 11:40 PM ET Sunday
        slot = run.slot_for(now)
        settled = [('NFL', 'gamePicks', {'id': 'a', 'title': 'A', 'result': 'win', 'status': 'settled'})]
        reports = run.build_reports({'NFL': (settled, [], [])}, slot, now, [], [], [], {'NFL': 4}, False)
        self.assertEqual(list(reports), ['2026-09-27-NFL-2340-settlement.json'])
        self.assertEqual(reports['2026-09-27-NFL-2340-settlement.json']['targetWeek'], 4)
        self.assertIn('Settled 1', reports['2026-09-27-NFL-2340-settlement.json']['summary'])

    def test_a_report_is_never_published_before_the_prices_in_it(self):
        """Sep 26: the 8:30 run started at 12:30:05Z, captured prices at 12:30:06Z and published from them; the report
        said 12:30:05Z and failed validation (quote <= published)."""
        now = datetime(2026, 9, 26, 12, 30, 5, tzinfo=timezone.utc)
        pick = {'id': 'x', 'title': 'USF at BGSU over 48.5', 'status': 'active', 'quotedAt': '2026-09-26T12:30:06Z', 'odds': -110, 'book': 'FanDuel'}
        [report] = run.build_reports({'CFB': ([], [], [('CFB', 'gamePicks', pick)])}, run.slot_for(now), now, [], [], [], {}, False).values()
        self.assertEqual(report['publishedAt'], '2026-09-26T12:30:06Z')
        [quiet] = run.build_reports({'CFB': ([], [], [('CFB', 'gamePicks', dict(pick, quotedAt='2026-09-26T11:00:00Z'))])},
                                    run.slot_for(now), now, [], [], [], {}, False).values()
        self.assertEqual(quiet['publishedAt'], '2026-09-26T12:30:05Z', 'an older quote leaves the run time alone')

    def test_a_quiet_run_writes_no_report(self):
        now = datetime(2026, 9, 29, 15, 50, tzinfo=timezone.utc)
        self.assertEqual(run.build_reports({'NFL': ([], [], [])}, run.slot_for(now), now, [], [], [], {}, False), {})

    def test_private_keys_never_reach_a_report(self):
        now = datetime(2026, 9, 27, 15, 55, tzinfo=timezone.utc)
        pick = {'id': 'p', 'title': 'T', 'book': 'DraftKings', 'odds': -110, 'status': 'active', '_desk': {'x': 1}, '_quotes': []}
        reports = run.build_reports({'NFL': ([], [], [('NFL', 'gamePicks', pick)])}, run.slot_for(now), now, [], [], [], {}, False)
        written = list(reports.values())[0]['gamePicks'][0]
        self.assertNotIn('_desk', written)
        self.assertNotIn('_quotes', written)

    def test_slugs(self):
        self.assertEqual(run.line_slug(44.5), '44-5')
        self.assertEqual(run.line_slug(41.0), '41')
        self.assertEqual(run.line_slug(-16.5), 'minus-16-5')
        self.assertEqual(run.report_slug([], [], [('NFL', 'props', {'athleteId': '1'})]), 'prop-leans')
        self.assertEqual(run.report_slug([], [], [('NFL', 'gamePicks', {})]), 'model-leans')
        self.assertEqual(run.report_slug([1], [1], []), 'run')


class HoldTests(unittest.TestCase):

    def test_a_backup_qb_injury_is_neutral_for_his_teammates(self):
        candidate = {'athleteId': '77', '_team': '10', 'market': 'recYds', 'gameIds': ['NFL-1']}
        game = {'id': 'NFL-1', 'league': 'NFL',
                'home': {'id': '10', 'abbreviation': 'CLE'}, 'away': {'id': '20', 'abbreviation': 'BAL'}}
        context_file = {'leagues': {'NFL': {'checkedAt': '2026-10-11T11:00:00Z', 'teams': {'10': {'players': [
            {'id': '5', 'name': 'Starter Five', 'position': 'QB', 'status': 'Active'},
            {'id': '6', 'name': 'Backup Six', 'position': 'QB', 'status': 'Injured Reserve'},
        ]}}}}}
        ctx = SimpleNamespace(games={'NFL-1': game}, player_team={'77': '10'}, starters={'NFL-10': '5'},
                              now=datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc), snapshots={},
                              snapshot=lambda _: None, odds={})
        facts = run.evidence(candidate, ctx, context_file)
        backup = next(f for f in facts if f['id'] == 'injury-10-6')
        self.assertEqual(backup['direction'], 'neutral')
    def test_holds_on_quarterback_listings(self):
        facts = [{'kind': 'injury', 'position': 'QB', 'team': '10', 'status': 'Questionable', 'claim': 'QB1 (QB, DET) is listed Questionable'}]
        self.assertIsNotNone(run.hold_reason({'marketType': 'total'}, facts))
        self.assertIsNotNone(run.hold_reason({'athleteId': '77', '_team': '10'}, facts))
        self.assertIsNone(run.hold_reason({'athleteId': '77', '_team': '20'}, facts), "the other team's quarterback does not hold a prop")
        self.assertIsNone(run.hold_reason({'marketType': 'total'}, []))
        note = {'origin': 'claude researcher', 'direction': 'against', 'kind': 'role',
                'claim': 'Elic Ayomanor played 28 of 53 offensive snaps (52.8%) in Week 2 against the Eagles.'}
        self.assertIsNone(run.hold_reason({'athleteId': '7'}, [note]), 'a snap count is not news that holds a play')
        out = dict(note, kind='injury', claim='Elic Ayomanor (hamstring) was ruled out for Sunday.')
        self.assertIn('ruled out', run.hold_reason({'athleteId': '7'}, [out]))
        self.assertFalse(run.hard({'kind': 'injury', 'status': 'Questionable', 'claim': 'Tyjae Spears (ankle) is questionable.'}))
        self.assertTrue(run.hard({'kind': 'injury', 'status': 'Doubtful', 'claim': 'JC Evans is listed as doubtful.'}))
        upgraded = {'kind': 'injury', 'status': 'Doubtful',
                    'claim': 'Nebraska running back Jamal Rule was upgraded from doubtful to questionable on Friday.'}
        self.assertFalse(run.hard(upgraded), 'an availability upgrade is not adverse hard news')
        mixed = dict(upgraded, claim='Jamal Rule was upgraded from doubtful to questionable, but the starting QB was ruled out.')
        self.assertTrue(run.hard(mixed), 'separate hard news in the same report still stops the post')
        still_doubtful = dict(upgraded, claim='The running back was upgraded from out to doubtful.')
        self.assertTrue(run.hard(still_doubtful), 'doubtful remains hard news even when it is an improvement')
        heavy = [{'kind': 'injury', 'position': p, 'team': '20', 'status': 'Out', 'claim': ''} for p in ('WR', 'WR', 'TE')]
        self.assertIsNotNone(run.hold_reason({'marketType': 'total'}, heavy))


class GitTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.dir.name)
        env = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}
        self.env = env

        def sh(*args):
            return subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, env=env, check=True)
        sh('init', '-q', '-b', 'main')
        (self.repo / 'research').mkdir()
        (self.repo / 'data' / 'odds').mkdir(parents=True)
        (self.repo / 'site' / 'data').mkdir(parents=True)
        (self.repo / 'site' / 'data' / 'slate.json').write_text('{"a": 1}')
        (self.repo / 'data' / 'odds' / 'nfl.jsonl').write_text('{}\n')
        (self.repo / 'research' / 'old.json').write_text('{}')
        sh('add', '.')
        sh('commit', '-q', '-m', 'base')
        self.sh = sh

    def tearDown(self):
        self.dir.cleanup()

    def runner(self, *args, cwd=None, check=True):
        result = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, env=self.env)
        if check and result.returncode:
            raise run.RunError(result.stderr)
        return result

    def test_silent_market_lab_outputs_are_whitelisted_but_other_site_data_is_not(self):
        self.assertTrue(run.allowed('data/market-lab/mlb-2026.jsonl'))
        self.assertTrue(run.allowed('site/data/market-lab.json'))
        self.assertFalse(run.allowed('site/data/slate.json'))

    def test_commit_whitelist_restores_everything_else(self):
        (self.repo / 'site' / 'data' / 'slate.json').write_text('{"a": 2}')                 # the hosted workflow owns this
        (self.repo / 'data' / 'odds' / 'nfl.jsonl').write_text('{}\n{}\n')                     # a capture
        (self.repo / 'research' / '2026-09-27-NFL-1219-run.json').write_text('{"league": "NFL"}')
        now = datetime(2026, 9, 27, 16, 19, tzinfo=timezone.utc)
        result = run.commit_push(now, run.slot_for(now), {'published': 1, 'settled': 0, 'closed': 0}, push=False, runner=self.runner, cwd=self.repo)
        self.assertEqual(result, {'committed': True, 'pushed': False})
        self.assertEqual((self.repo / 'site' / 'data' / 'slate.json').read_text(), '{"a": 1}', 'restored, not committed')
        log = self.sh('log', '--format=%s').stdout.splitlines()
        self.assertEqual(log[0], 'Refresh research 2026-09-27')
        self.assertEqual(log[1], 'Capture odds 2026-09-27')
        self.assertEqual(self.sh('status', '--porcelain').stdout, '')

    def test_push_rejected_by_the_other_writer_is_rebased_and_the_store_merged(self):
        """The hosted workflow and the desk both appended to the odds store; the desk's push is rejected,
        rebased, the store merged with every record kept, and pushed. Nothing is forced."""
        import boxscores
        side = tempfile.TemporaryDirectory()
        self.addCleanup(side.cleanup)
        origin = Path(side.name) / 'origin.git'
        hosted = Path(side.name) / 'hosted'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(origin)], check=True, capture_output=True)
        self.sh('remote', 'add', 'origin', str(origin))
        self.sh('push', '-q', '-u', 'origin', 'main')
        subprocess.run(['git', 'clone', '-q', '-b', 'main', str(origin), str(hosted)], check=True, capture_output=True, env=self.env)
        store = hosted / 'data' / 'odds'
        with (store / 'nfl.jsonl').open('a') as f:
            f.write('{"gameId": "g", "retrievedAt": "2026-09-27T12:38:00Z", "total": 45}\n')
        boxscores.write_json(store / 'ledger.json', boxscores.ledger(store))
        subprocess.run(['git', '-c', 'user.name=bot', '-c', 'user.email=b@b', 'commit', '-q', '-am', 'hosted capture'], cwd=hosted, check=True, capture_output=True, env=self.env)
        subprocess.run(['git', 'add', 'data/odds/ledger.json'], cwd=hosted, check=True, capture_output=True, env=self.env)
        subprocess.run(['git', '-c', 'user.name=bot', '-c', 'user.email=b@b', 'commit', '-q', '-m', 'hosted ledger'], cwd=hosted, check=True, capture_output=True, env=self.env)
        subprocess.run(['git', 'push', '-q'], cwd=hosted, check=True, capture_output=True, env=self.env)
        mine = self.repo / 'data' / 'odds'
        with (mine / 'nfl.jsonl').open('a') as f:
            f.write('{"gameId": "g", "retrievedAt": "2026-09-27T12:35:00Z", "total": 44.5}\n')
        boxscores.write_json(mine / 'ledger.json', boxscores.ledger(mine))
        (self.repo / 'research' / '2026-09-27-NFL-0830-run.json').write_text('{"league": "NFL"}')
        now = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)
        result = run.commit_push(now, run.slot_for(now), {'published': 1, 'settled': 0, 'closed': 0}, push=True, runner=self.runner, cwd=self.repo)
        self.assertEqual(result, {'committed': True, 'pushed': True})
        self.assertEqual(self.sh('rev-parse', 'HEAD').stdout, self.sh('rev-parse', 'origin/main').stdout, 'pushed, on top of the hosted commits')
        log = self.sh('log', '--format=%s').stdout.splitlines()
        self.assertEqual(log[:4], ['Refresh research 2026-09-27', 'Capture odds 2026-09-27', 'hosted ledger', 'hosted capture'])
        records = boxscores.read_store(mine / 'nfl.jsonl')
        self.assertEqual([r.get('total') for r in records], [None, 45, 44.5], 'both captures kept; the base line has no retrievedAt so the order is by side')
        self.assertEqual(boxscores.verify(mine), [], 'the ledger was recomputed over the merged file')
        self.assertEqual(self.sh('status', '--porcelain').stdout, '')

    def test_commit_log_commits_the_posted_log_alone(self):
        (self.repo / 'data' / 'x-posted.json').write_text('{"posts": []}\n')
        self.sh('add', '.')
        self.sh('commit', '-q', '-m', 'log')
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        self.assertEqual(run.commit_log(now, push=False, runner=self.runner, cwd=self.repo), {'committed': False, 'pushed': False})
        (self.repo / 'data' / 'x-posted.json').write_text('{"posts": [{"id": "a"}]}\n')
        (self.repo / 'research' / 'old.json').write_text('{"not": "this"}')
        self.assertEqual(run.commit_log(now, push=False, runner=self.runner, cwd=self.repo), {'committed': True, 'pushed': False})
        self.assertEqual(self.sh('log', '-1', '--format=%s').stdout.strip(), 'Record posts 2026-09-27')
        self.assertEqual(self.sh('show', '--name-only', '--format=', 'HEAD').stdout.split(), ['data/x-posted.json'])

    def test_sync_commits_captures_a_stopped_run_left_behind(self):
        (self.repo / 'data' / 'odds' / 'nfl.jsonl').write_text('{}\n{"x": 1}\n')
        with self.assertRaises(run.RunError) as caught:        # no remote here, so the rebase step fails after the commit
            run.sync(runner=self.runner)
        self.assertNotIn('modified before the run', str(caught.exception))
        self.assertEqual(self.sh('log', '-1', '--format=%s').stdout.strip(), 'Captures left by a stopped run')
        self.assertEqual(self.sh('status', '--porcelain').stdout, '')

    def test_commit_log_can_deliver_local_notes_without_a_new_post(self):
        folder = self.repo / 'site/data'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'desk-notes.json').write_text('{"rows": []}\n')
        (self.repo / 'research' / 'old.json').write_text('{"not": "this"}')
        now = datetime(2026, 10, 5, 12, 40, tzinfo=timezone.utc)
        self.assertEqual(run.commit_log(now, push=False, runner=self.runner, cwd=self.repo), {'committed': True, 'pushed': False})
        self.assertEqual(self.sh('show', '--name-only', '--format=', 'HEAD').stdout.split(), ['site/data/desk-notes.json'])

    def test_sync_refuses_a_dirty_tree(self):
        (self.repo / 'research' / 'old.json').write_text('{"changed": true}')
        with self.assertRaises(run.RunError):
            run.sync(runner=self.runner)


class JudgeTests(unittest.TestCase):
    """The desk's judge only weighs what can matter, and a hold must name a fact."""

    def ctx(self):
        from types import SimpleNamespace
        return SimpleNamespace(starters={'NFL-10': '5', 'NFL-20': '6'})

    def test_only_facts_that_can_matter_reach_the_judge(self):
        ctx = self.ctx()
        facts = [{'id': 'market-g', 'kind': 'market', 'direction': 'neutral', 'claim': 'moved'},
                 {'id': 'weather-g', 'kind': 'weather', 'direction': 'neutral', 'claim': 'calm'},
                 {'id': 'weather-w', 'kind': 'weather', 'direction': 'against', 'claim': 'wind 22 mph'},
                 {'id': 'injury-10-5', 'kind': 'injury', 'team': '10', 'position': 'QB', 'status': 'Questionable', 'claim': 'QB1 questionable'},
                 {'id': 'injury-10-8', 'kind': 'injury', 'team': '10', 'position': 'QB', 'status': 'Questionable', 'claim': 'QB2 questionable'},
                 {'id': 'injury-20-9', 'kind': 'injury', 'team': '20', 'position': 'WR', 'status': 'Injured Reserve', 'claim': 'WR on IR'},
                 {'id': 'injury-20-77', 'kind': 'injury', 'team': '20', 'position': 'WR', 'status': 'Out', 'claim': 'the prop player out'},
                 {'id': 'web-g-0', 'kind': 'role', 'origin': 'claude researcher', 'direction': 'against', 'claim': 'benched'}]
        total = {'marketType': 'total', 'direction': 'over', '_league': 'NFL'}
        ids = [f['id'] for f in run.relevant_facts(total, facts, ctx)]
        self.assertEqual(ids, ['weather-w', 'injury-10-5', 'web-g-0'], 'the move, calm weather, a backup and IR stay out')
        prop = {'athleteId': '77', '_team': '20', 'market': 'rec', 'direction': 'over', '_league': 'NFL'}
        ids = [f['id'] for f in run.relevant_facts(prop, facts, ctx)]
        self.assertEqual(ids, ['injury-20-77', 'web-g-0'], "a prop weighs its own player and his quarterback, not the other side's")
        three = [{'id': f'injury-20-{i}', 'kind': 'injury', 'team': '20', 'position': 'WR', 'status': 'Out', 'claim': 'x'} for i in range(3)]
        self.assertEqual(len(run.relevant_facts(total, three, ctx)), 3, 'a side missing three skill players matters to a total')
        self.assertEqual(run.relevant_facts(total, three[:2], ctx), [])

    def test_mnf_mariota_out_does_not_block_active_daniels_team(self):
        ctx = SimpleNamespace(starters={'NFL-28': '4426348', 'NFL-25': '4361741'})
        backup = {'id': 'injury-28-2576980', 'kind': 'injury', 'team': '28',
                  'position': 'QB', 'status': 'Out', 'claim': 'Marcus Mariota is out with a knee injury'}
        for candidate in [
            {'marketType': 'spread', 'direction': 'home', '_league': 'NFL'},
            {'marketType': 'total', 'direction': 'under', '_league': 'NFL'},
            {'athleteId': '4697815', '_team': '28', 'market': 'rushYds', 'direction': 'under', '_league': 'NFL'}]:
            self.assertEqual(run.relevant_facts(candidate, [backup], ctx), [])
        starter = {**backup, 'id': 'injury-28-4426348', 'claim': 'Jayden Daniels is out'}
        self.assertEqual(run.relevant_facts({'marketType': 'total', '_league': 'NFL'}, [starter], ctx), [starter])
        self.assertEqual(run.relevant_facts({'marketType': 'total', '_league': 'NFL'}, [backup],
                                           SimpleNamespace(starters={})), [backup],
                         'unknown starter evidence stays cautious rather than guessing a backup')

    def test_no_relevant_fact_no_hold_and_a_hold_names_a_fact(self):
        from unittest import mock
        self.assertIsNone(run.judge({'title': 't'}, [], True))
        facts = [{'id': 'injury-10-5', 'kind': 'injury', 'position': 'QB', 'claim': 'QB1 out'}]
        with mock.patch.object(run.llm_tasks, 'judge_against', return_value={'argues_against': False, 'confidence': 'low', 'fact_ids': [], 'note': 'n'}):
            self.assertIsNone(run.judge({'title': 't'}, facts, True), 'unsure without a fact is not a hold')
        with mock.patch.object(run.llm_tasks, 'judge_against', return_value={'argues_against': True, 'confidence': 'medium', 'fact_ids': ['injury-10-5'], 'note': 'QB out'}):
            self.assertIn('QB out', run.judge({'title': 't'}, facts, True))
        with mock.patch.object(run.llm_tasks, 'judge_against', return_value={'argues_against': True, 'confidence': 'high', 'fact_ids': [], 'note': 'vibes'}):
            self.assertIsNone(run.judge({'title': 't'}, facts, True), 'against without naming a fact does not count')
        web = [{'id': 'web-1', 'origin': 'claude researcher', 'direction': 'against', 'kind': 'injury', 'claim': 'the starter is suspended'}]
        self.assertIn('suspended', run.judge({'title': 't'}, web, False), 'with the model down, verified reporting against it holds')

    def test_the_reasoning_names_what_the_web_check_verified(self):
        facts = [{'kind': 'injury', 'direction': 'neutral', 'verified': True, 'claim': 'Both starting quarterbacks are expected to play.', 'source': 'https://example.com/a'},
                 {'kind': 'stats', 'direction': 'for', 'verified': True, 'claim': 'Iowa averages 30 points.', 'source': 'https://example.com/b'},
                 {'kind': 'role', 'direction': 'against', 'verified': True, 'claim': 'The starter is suspended.', 'source': 'https://example.com/c'},
                 {'kind': 'injury', 'direction': 'neutral', 'verified': False, 'claim': 'Rumour.', 'source': 'https://example.com/d'}]
        self.assertEqual([f['source'] for f in run.checked_facts({'_research': facts})], ['https://example.com/a'],
                         'only verified availability facts that do not argue against the pick')

    def test_game_lean_keeps_verified_statistical_opposition_even_when_not_a_news_hold(self):
        facts = [{'kind': 'stats', 'direction': 'against', 'verified': True, 'origin': 'codex researcher',
                  'claim': 'The Falcons scored 30 points in their last game. More detail.', 'source': 'https://example.com/atl'},
                 {'kind': 'stats', 'direction': 'against', 'verified': True, 'origin': 'codex researcher',
                  'claim': 'The Saints scored 28 points in their last game.', 'source': 'https://example.com/no'},
                 {'kind': 'stats', 'direction': 'against', 'verified': False,
                  'claim': 'An unverified claim.', 'source': 'https://example.com/unverified'}]
        pick = {'id': 'NFL-test', 'title': 'Falcons at Saints under 48', 'gameIds': ['NFL-1'], 'modelLean': True,
                'marketType': 'total', 'direction': 'under', 'line': 48, 'odds': -108, 'confidence': 3,
                '_research': facts, '_evidence': facts[:2], 'sources': []}
        desk = {'projection': 43.4, 'chance': .552, 'rawChance': .625, 'edgePoints': 3.3, 'breakEven': .519}
        ctx = SimpleNamespace(snapshot=lambda _: {}, starters={})
        self.assertEqual(run.relevant_facts(pick, facts[:2], ctx), [], 'historical statistics do not become a new hold')
        with mock.patch.object(run.gates, 'desk_for', return_value=desk):
            run.write_prose(pick, ctx, [])
        self.assertIn('reporting also points against this side', pick['why'])
        self.assertNotIn('Nothing sourced argues against', pick['why'])
        for fact in facts[:2]:
            self.assertEqual(pick['risk'].count(run.first_sentence(fact['claim'])), 1, 'duplicate evidence is not double-counted')
            self.assertIn(fact['source'], pick['sources'])
        self.assertNotIn('unverified claim', pick['risk'])
        self.assertEqual(pick['reasoning']['context'], [])
        self.assertEqual(len(pick['reasoning']['cautions']), 2)
        self.assertTrue(pick['reasoning']['directionsChecked'])
        self.assertNotIn(facts[2]['source'], pick['sources'])
        self.assertIn('not a separate injury or availability hold', pick['risk'])
        self.assertEqual((pick['line'], pick['odds'], pick['confidence']), (48, -108, 3))

    def test_game_lean_without_opposition_does_not_claim_a_universal_all_clear(self):
        pick = {'gameIds': ['NFL-1'], 'marketType': 'total', 'direction': 'under', 'line': 48, 'odds': -108, 'confidence': 3}
        desk = {'projection': 43.4, 'chance': .552, 'rawChance': .625, 'edgePoints': 3.3, 'breakEven': .519}
        with mock.patch.object(run.gates, 'desk_for', return_value=desk):
            run.write_prose(pick, SimpleNamespace(snapshot=lambda _: {}), [])
        self.assertIn('Model lean, our number only.', pick['why'])
        self.assertNotIn('Nothing sourced', pick['why'])
        self.assertNotIn('counterpoint', pick['risk'])

    def test_optional_polish_cannot_erase_verified_counterevidence(self):
        fact = {'kind': 'stats', 'direction': 'against', 'verified': True, 'claim': 'The offense has scored more recently.'}
        pick = {'title': 'Test', 'why': 'The projection supports it, but statistics point against it.',
                'risk': 'Statistical counterpoint: The offense has scored more recently.', '_research': [fact]}
        before = (pick['why'], pick['risk'])
        status = {'llm': {'kept': 0, 'polished': 0}}
        with mock.patch.object(run.llm_tasks, 'why_for') as why, mock.patch.object(run.llm_tasks, 'risk_for') as risk:
            run.polish(pick, [], status)
        why.assert_not_called()
        risk.assert_not_called()
        self.assertEqual((pick['why'], pick['risk']), before)
        self.assertEqual(status['llm'], {'kept': 2, 'polished': 0})

    def test_a_game_line_post_reason_is_a_fact_that_backs_the_play_or_nothing(self):
        from types import SimpleNamespace
        total = {'marketType': 'total', 'direction': 'under', 'line': 43.5, 'gameIds': ['g']}
        facts = [{'origin': 'claude researcher', 'verified': True, 'kind': 'injury', 'direction': 'for',
                  'claim': 'Saints receiver Chris Olave is out with a hamstring injury. He had 9 catches last week.'},
                 {'origin': 'claude researcher', 'verified': True, 'kind': 'stats', 'direction': 'for', 'claim': 'The Saints average 30 points.'},
                 {'origin': 'claude researcher', 'verified': True, 'kind': 'injury', 'direction': 'against',
                  'claim': 'Saints quarterback Tyler Shough leads the league with 662 passing yards.'},
                 {'kind': 'market', 'direction': 'neutral', 'claim': 'The total opened 42.5.'}]
        ctx = SimpleNamespace(games={})
        self.assertEqual(run.post_reason(total, facts, ctx, []), 'Saints receiver Chris Olave is out with a hamstring injury.')
        self.assertIsNone(run.post_reason(total, facts[1:], ctx, []), 'a stats story or a fact against the play is never its reason')
        wind = [{'kind': 'weather', 'direction': 'for', 'claim': 'Forecast at kickoff: wind 18 mph.'}]
        self.assertEqual(run.post_reason(total, wind, ctx, []), 'Forecast at kickoff: wind 18 mph.')
        self.assertIsNone(run.post_reason(dict(total, legs=[{}]), wind, ctx, []))

    def test_every_college_play_needs_the_web_check(self):
        self.assertTrue(run.needs_research({'_league': 'CFB', 'projection': 47.1, 'line': 38.5}))
        self.assertTrue(run.needs_research({'_league': 'CFB', 'projection': 40.0, 'line': 38.5}), 'no college injury feed at any gap')
        self.assertFalse(run.needs_research({'_league': 'NFL', 'projection': 47.1, 'line': 38.5}), 'the NFL has its injury report')
        self.assertFalse(run.needs_research({'_league': 'CFB', 'legs': [{}]}), 'the fun parlay is built from the board')
        self.assertEqual(run.first_sentence("Camden Coleman has started while Evans is out. He completed 19 of 27."),
                         'Camden Coleman has started while Evans is out.')


class PrecheckTests(unittest.TestCase):
    def test_a_lineup_is_confirmed_only_by_an_availability_fact(self):
        self.assertTrue(run.lineup_confirmed([{'kind': 'injury'}]))
        self.assertTrue(run.lineup_confirmed([{'kind': 'stats'}, {'kind': 'role'}]))
        self.assertFalse(run.lineup_confirmed([{'kind': 'stats'}]))
        self.assertFalse(run.lineup_confirmed([]))

    def test_the_window(self):
        now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
        post = lambda key, minutes, **over: dict({'id': key, 'kind': 'buffer:play', 'bufferPostId': 'b', 'dueAt': run.stamp(now + timedelta(minutes=minutes))}, **over)
        log_book = {'posts': [post('soon', 10), post('in', 30), post('edge', 45), post('lower', 15),
                              post('old-window', 150), post('far', 60), post('sent', 30, sentAt='x'),
                              post('gone', 30, cancelledAt='x'), post('done', 30, precheck={'result': 'clear'}),
                              dict(post('receipt', 30), kind='buffer:receipt')]}
        self.assertEqual([e['id'] for e in run.precheck_due(log_book, now)], ['soon', 'in', 'edge', 'lower'])
        log_book['posts'] += [post('past', -1), post('short', 1), post('checked-short', 1, precheck={'result':'clear'})]
        self.assertEqual([e['id'] for e in run.precheck_due(log_book, now)], ['soon','in','edge','lower','short'])

    def test_quiet_when_nothing_is_due(self):
        from types import SimpleNamespace
        from unittest import mock
        import x_post
        with mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(run, 'Lock') as lock:
            self.assertEqual(run.precheck(SimpleNamespace(now=None, dry_run=True, no_llm=True, no_push=True)), 0)
        lock.assert_not_called()

    def test_a_rehearsal_leaves_the_post_log_alone(self):
        from types import SimpleNamespace
        from unittest import mock
        import x_post
        now = datetime(2026, 9, 25, 18, 30, tzinfo=timezone.utc)
        entry = {'id': 'CFB-2026-W4-x', 'kind': 'buffer:play', 'bufferPostId': 'b', 'dueAt': run.stamp(now + timedelta(minutes=90))}
        ctx = SimpleNamespace(first={}, latest={}, player_team={}, names={}, games={})
        stores = mock.MagicMock(reports=[], context_file={})
        stores.as_of.return_value = ctx
        with mock.patch.object(x_post, 'load_log', side_effect=lambda: {'posts': [dict(entry)]}), \
                mock.patch.object(x_post, 'save_log') as save_log, mock.patch.object(run, 'Lock'), \
                mock.patch.object(run, 'sync', side_effect=AssertionError('no sync in a rehearsal')), \
                mock.patch.object(run, 'live_games', return_value={}), mock.patch.object(run.features, 'load', return_value=[]), \
                mock.patch.object(run.gates, 'Stores', return_value=stores), mock.patch.object(run, 'raw_first_publications', return_value={}), \
                mock.patch.object(run, 'live_context', return_value={}), mock.patch.object(run.llm, 'available', return_value=False), \
                mock.patch.object(run, 'close_moves', return_value=([], None)), mock.patch.object(run.desk, 'captures', return_value=[]):
            self.assertEqual(run.precheck(SimpleNamespace(now=run.stamp(now), dry_run=True, no_llm=True, no_push=True)), 0)
        save_log.assert_not_called()

    def test_a_requote_creates_the_new_post_before_the_old_one_goes(self):
        import buffer_post
        from types import SimpleNamespace
        from unittest import mock
        now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
        pick = {'id': 'CFB-2026-W4-x', 'title': 'Iowa at Michigan over 38.5', 'marketType': 'total', 'line': 38.5, 'odds': -105,
                'book': 'ESPN BET', 'direction': 'over', 'gameIds': ['g'], 'projection': 47.1}
        ctx = SimpleNamespace()

        def attempt(fail_delete=()):
            entry = {'id': 'CFB-2026-W4-x', 'bufferPostId': 'old', 'dueAt': '2026-09-26T16:30:00Z',
                     'card': True, 'textHash': 'stale', 'discord': {'state': 'pending'}}
            calls = []

            def delete(post_id, **k):
                calls.append(('delete', post_id))
                if post_id in fail_delete:
                    raise buffer_post.BufferError('refused')
            with mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                    mock.patch.object(buffer_post, 'create_post', side_effect=lambda *a, **k: calls.append(('create', a[3])) or 'new'), \
                    mock.patch.object(buffer_post, 'delete_post', side_effect=delete), \
                    mock.patch.object(run.gates, 'best_now', return_value=('FanDuel', 39.5, -110)), \
                    mock.patch.object(run, 'alert') as alerted:
                try:
                    run.requote(entry, pick, {'id': 'g', 'league': 'CFB'}, ctx, now, log=lambda *_: None)
                except buffer_post.BufferError:
                    pass
            return entry, calls, alerted
        entry, calls, _ = attempt()
        self.assertEqual(calls, [('create', 'https://keenroudy.com/sports/data/cards/CFB-2026-W4-x.png'), ('delete', 'old')])
        self.assertEqual(entry['bufferPostId'], 'new')
        self.assertNotIn('@Playbook', entry['discord']['text'])
        entry, calls, alerted = attempt(fail_delete={'old'})
        self.assertEqual(calls[-1], ('delete', 'new'), 'the old one could not go, so the new one is taken back')
        self.assertEqual(entry['bufferPostId'], 'old')
        alerted.assert_not_called()
        entry, calls, alerted = attempt(fail_delete={'old', 'new'})
        alerted.assert_called_once()

    def test_a_requote_keeps_the_pick_of_the_day_label_and_card(self):
        import buffer_post
        from types import SimpleNamespace
        from unittest import mock
        now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
        pick = {'id': 'CFB-2026-W4-x', 'title': 'Iowa at Michigan over 38.5', 'marketType': 'total', 'line': 38.5, 'odds': -105,
                'book': 'ESPN BET', 'direction': 'over', 'gameIds': ['g'], 'projection': 47.1}
        entry = {'id': 'CFB-2026-W4-x', 'bufferPostId': 'old', 'dueAt': '2026-09-26T16:00:00Z', 'card': True, 'textHash': 'stale',
                 'cardKey': 'CFB-2026-W4-x-potd', 'featured': True}
        created = []
        with mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'create_post', side_effect=lambda *a, **k: created.append(a) or 'new'), \
                mock.patch.object(buffer_post, 'delete_post'), \
                mock.patch.object(run.gates, 'best_now', return_value=('FanDuel', 39.5, -110)):
            run.requote(entry, pick, {'id': 'g', 'league': 'CFB'}, SimpleNamespace(), now, log=lambda *_: None)
        text, _, _, card = created[0]
        self.assertTrue(text.startswith('🍳 Hot Plate (POTD): '), text)
        self.assertIn('Now 39.5 (-110, FanDuel)', text)
        self.assertEqual(card, 'https://keenroudy.com/sports/data/cards/CFB-2026-W4-x-potd.png')

    def test_a_new_pick_of_the_day_already_queued_is_relabeled_once_its_card_is_live(self):
        import buffer_post
        import featured
        from unittest import mock
        now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
        pick = {'id': 'CFB-2026-W4-x', 'title': 'Iowa at Michigan over 38.5', 'marketType': 'total', 'line': 38.5, 'odds': -105,
                'book': 'ESPN BET', 'direction': 'over', 'gameIds': ['g'], 'projection': 47.1}
        ctx = SimpleNamespace(first={pick['id']: pick}, latest={})

        def attempt(live, fail=False):
            entry = {'id': pick['id'], 'kind': 'buffer:play', 'bufferPostId': 'old', 'dueAt': '2026-09-26T16:10:00Z', 'card': True, 'textHash': 'plain'}
            created = []

            def create(*a, **k):
                if fail:
                    raise buffer_post.BufferError('refused')
                created.append(a)
                return 'new'
            with mock.patch.object(featured, 'of_day', return_value=pick['id']), mock.patch.object(buffer_post, 'reachable', return_value=live), \
                    mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                    mock.patch.object(buffer_post, 'create_post', side_effect=create), mock.patch.object(buffer_post, 'delete_post'), \
                    mock.patch.object(run.gates, 'best_now', return_value=None):
                done = run.feature_scheduled({'posts': [entry]}, ctx, {'g': {'id': 'g', 'league': 'CFB'}}, now, log=lambda *_: None)
            return done, entry, created
        done, entry, created = attempt(live=True)
        self.assertTrue(done)
        self.assertEqual((entry['bufferPostId'], entry['featured'], entry['cardKey']), ('new', True, 'CFB-2026-W4-x-potd'))
        self.assertTrue(created[0][0].startswith('🍳 Hot Plate (POTD): '), created[0][0])
        self.assertEqual(created[0][2], datetime(2026, 9, 26, 16, 10, tzinfo=timezone.utc), 'at the time it was queued for')
        done, entry, created = attempt(live=False)
        self.assertEqual((done, entry.get('featured'), created), (False, None, []), 'no card yet: it waits, queued as it was')
        done, entry, _ = attempt(live=True, fail=True)
        self.assertEqual((done, entry['bufferPostId'], entry.get('featured')), (False, 'old', None), 'a refused post leaves the queue as it was')


class AlertTests(unittest.TestCase):
    def test_alerts_push_once_per_six_hours_and_never_without_a_topic(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
            with mock.patch.object(run, 'CONF', Path(folder)), mock.patch.dict(os.environ, {'KEENROUDY_NTFY_TOPIC': 'secret-topic'}):
                self.assertTrue(run.alert('Run stopped', 'git fetch failed', now=now, send=sent.append))
                self.assertFalse(run.alert('Run stopped', 'git fetch failed', now=now + timedelta(hours=1), send=sent.append), 'quiet for six hours')
                self.assertTrue(run.alert('Run stopped', 'git fetch failed', now=now + timedelta(hours=7), send=sent.append))
                self.assertTrue(run.alert('Run stopped', 'something else', now=now, send=sent.append))
            self.assertEqual(len(sent), 3)
            self.assertEqual(sent[0].full_url, 'https://ntfy.sh/secret-topic')
            self.assertIn(b'git fetch failed', sent[0].data)
            with mock.patch.object(run, 'CONF', Path(folder)), mock.patch.dict(os.environ, {'KEENROUDY_NTFY_TOPIC': ''}):
                self.assertFalse(run.alert('x', 'y', now=now, send=lambda r: self.fail('no topic, no push')))


    def test_the_heartbeat_reaches_the_phone_when_something_is_wrong(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            conf = Path(folder) / '.config' / 'keenroudy'
            conf.mkdir(parents=True)
            sent = []
            answer = subprocess.CompletedProcess([], 0, stdout='Logged in to github.com account keenroudy22', stderr='')
            with mock.patch.object(run, 'CONF', conf), \
                    mock.patch.object(run, 'git', lambda *a, **k: subprocess.CompletedProcess([], 0, stdout='', stderr='')), \
                    mock.patch.object(run.subprocess, 'run', lambda *a, **k: answer), \
                    mock.patch('urllib.request.urlopen', side_effect=OSError('refused')), \
                    mock.patch.object(run, 'alert', lambda title, message, **k: sent.append((title, message))):
                self.assertEqual(run.heartbeat(None), 1)
                self.assertEqual(run.heartbeat(None), 1)
                self.assertEqual(len(sent), 1, 'unchanged problems do not repeatedly alert')
            self.assertEqual(sent[0][0], 'KeenRoudy desk needs a look')
            self.assertIn('no run has written status.json yet', sent[0][1])
            self.assertIn('Ollama is not reachable', sent[0][1])
            self.assertTrue((Path(folder) / 'Library' / 'Logs' / 'KeenRoudy' / 'ALERT.txt').exists())

    def test_live_today_staleness_uses_public_generated_time(self):
        from io import BytesIO
        now = datetime(2026, 10, 7, 17, 0, tzinfo=timezone.utc)
        stale = lambda *_args, **_kwargs: BytesIO(b'{"generatedAt":"2026-10-07T13:00:00Z"}')
        fresh = lambda *_args, **_kwargs: BytesIO(b'{"generatedAt":"2026-10-07T16:00:00Z"}')
        self.assertIn('4.0 hours old', run.live_today_staleness(now, stale))
        self.assertIsNone(run.live_today_staleness(now, fresh))

    def test_a_rehearsal_never_overwrites_the_live_status(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(run, 'CONF', Path(folder)):
                run.write_status({'outcome': 'failed: sync', 'dryRun': False})
                run.write_status({'outcome': 'ok', 'dryRun': True})
            self.assertEqual(json.loads((Path(folder) / 'status.json').read_text())['outcome'], 'failed: sync')
            self.assertEqual(json.loads((Path(folder) / 'pending' / 'status.json').read_text())['outcome'], 'ok')


class FetchTests(unittest.TestCase):
    def test_a_fetch_that_races_another_git_client_is_tried_again_and_other_failures_stop_the_run(self):
        from types import SimpleNamespace
        answers = [SimpleNamespace(returncode=1, stdout='', stderr="error: cannot lock ref 'refs/remotes/origin/main': is at b544 but expected 5bfa"),
                   SimpleNamespace(returncode=0, stdout='', stderr='')]
        calls, slept = [], []
        run.fetch(lambda *a, cwd=None, check=True: calls.append(a) or answers.pop(0), sleep=slept.append)
        self.assertEqual(len(calls), 2)
        self.assertEqual(slept, [3])
        broken = lambda *a, cwd=None, check=True: SimpleNamespace(returncode=128, stdout='', stderr='fatal: could not read from remote')
        with self.assertRaises(run.RunError):
            run.fetch(broken, sleep=lambda s: self.fail('a real failure is not retried'))
        always = lambda *a, cwd=None, check=True: SimpleNamespace(returncode=1, stdout='', stderr='cannot lock ref x')
        with self.assertRaises(run.RunError):
            run.fetch(always, attempts=3, sleep=lambda s: None)


class ParlayGuardTests(unittest.TestCase):
    """A fun parlay never carries a leg the desk pulled. On Sep 25 the 12:10 PM longshot went out with Navy at UAB
    over 51.5, the play the desk had closed at 11:03 because Navy's starting quarterback might not play."""
    NOW = datetime(2026, 9, 25, 15, 30, tzinfo=timezone.utc)       # 11:30 AM ET
    GAMES = {g: {'id': g, 'league': 'CFB', 'kickoff': '2026-09-25T23:30Z', 'state': 'pre'} for g in ('army', 'navy', 'iu')}
    NOTE = ("Closed to new entries at 11:03 AM ET, before its post went out: verified reporting argues against it: Navy's "
            "quarterback sprained his ankle and is week-to-week. Stays in the record at 51.5 and -105 and is graded as posted.")

    def world(self, closed=True):
        single = {'id': 'CFB-2026-W4-navy-uab-over-51-5-fd', 'title': 'Navy at UAB over 51.5', 'marketType': 'total', 'line': 51.5,
                  'direction': 'over', 'gameIds': ['navy'], 'odds': -105, 'book': 'FanDuel', 'league': 'CFB', 'status': 'active',
                  'publishedAt': '2026-09-24T11:40:00Z'}
        legs = [{'id': 'game-army-total-over', 'title': 'Army at Temple over 47.5', 'gameId': 'army', 'market': 'total points',
                 'side': 'over', 'line': 47.5, 'odds': -120},
                {'id': 'game-navy-total-over', 'title': 'Navy at UAB over 51.5', 'gameId': 'navy', 'market': 'total points',
                 'side': 'over', 'line': 51.5, 'odds': -105},
                {'id': 'game-iu-home', 'title': 'Indiana -20.5', 'gameId': 'iu', 'market': 'point spread', 'side': 'home',
                 'line': -20.5, 'odds': -110}]
        ticket = {'id': 'CFB-2026-W4-longshot-0925-espnbet', 'title': '3-leg longshot at ESPN BET', 'parlayType': 'longshot', 'legs': legs,
                  'gameIds': ['army', 'navy', 'iu'], 'odds': 583, 'book': 'ESPN BET', 'league': 'CFB', 'status': 'active',
                  'publishedAt': '2026-09-25T10:45:05Z'}
        first = {single['id']: single, ticket['id']: ticket}
        latest = {single['id']: dict(single, status='expired', entryNote=self.NOTE)} if closed else {}
        ctx = SimpleNamespace(first=first, latest=latest, games=self.GAMES, player_team={}, names={}, starters={})
        raw_first = {single['id']: ('gamePicks', dict(single)), ticket['id']: ('parlays', dict(ticket))}
        return ctx, raw_first, ticket, single

    def test_a_ticket_closes_with_a_leg_the_desk_pulled(self):
        ctx, raw_first, ticket, _ = self.world()
        [(league, kind, revision)] = run.parlay_closures(ctx, raw_first, self.GAMES, self.NOW)
        self.assertEqual((league, kind, revision['id'], revision['status']), ('CFB', 'parlays', ticket['id'], 'expired'))
        self.assertIn('its Navy at UAB over 51.5 leg was pulled: verified reporting argues against it', revision['entryNote'])
        self.assertIn('Stays in the record at +583', revision['entryNote'])
        self.assertEqual(revision['legs'], ticket['legs'], 'the ticket stands as written; only its entry closes')
        self.assertEqual(run.parlay_closures(*self.world(closed=False)[:2], self.GAMES, self.NOW), [], 'nothing pulled, nothing closed')
        started = dict(self.GAMES, army=dict(self.GAMES['army'], kickoff='2026-09-25T15:00Z'))
        self.assertEqual(run.parlay_closures(ctx, raw_first, started, self.NOW), [], 'a ticket under way is left to be graded')

    def test_a_leg_matches_the_same_bet_whatever_the_line(self):
        _, _, ticket, single = self.world()
        navy, spread = ticket['legs'][1], ticket['legs'][2]
        self.assertTrue(run.same_bet(run.leg_single(navy, ticket), dict(single, line=53.5)))
        self.assertFalse(run.same_bet(run.leg_single(navy, ticket), dict(single, direction='under')))
        home = {'marketType': 'spread', 'direction': 'home', 'line': -21.5, 'gameIds': ['iu']}
        self.assertTrue(run.same_bet(run.leg_single(spread, ticket), home))
        self.assertFalse(run.same_bet(run.leg_single(spread, ticket), dict(home, direction='away')))
        prop_leg = {'id': 'alt', 'title': 'Player 40+ receiving yards', 'gameId': 'g', 'athleteId': '7', 'market': 'recYds', 'direction': 'over', 'line': 39.5}
        prop = {'athleteId': '7', 'market': 'recYds', 'direction': 'over', 'line': 54.5, 'gameIds': ['g']}
        self.assertTrue(run.same_bet(run.leg_single(prop_leg, {'id': 'easy', 'legs': [prop_leg]}), prop))
        self.assertFalse(run.same_bet(run.leg_single(prop_leg, {'id': 'easy', 'legs': [prop_leg]}), dict(prop, athleteId='8')))

    def test_the_next_ticket_leaves_off_games_with_a_reason_against(self):
        ctx, _, _, _ = self.world()
        screened = [{'gameId': 'wind', 'rule': 'lean_nothing_against', 'reason': 'wind 21 mph'},
                    {'gameId': 'qb', 'rule': 'held', 'reason': 'verified reporting argues against it: the starter is out'},
                    {'gameId': 'unknown', 'rule': 'held', 'reason': 'a college play needs the web check to confirm who is expected to play'},
                    {'gameId': 'book', 'rule': 'one_book', 'reason': 'only DraftKings'}]
        self.assertEqual(run.longshot_exclusions(ctx, screened), {'navy', 'wind', 'qb'})

    def test_october_four_pulled_leg_cannot_reappear_in_a_rushed_replacement(self):
        pulled = {'id': 'NFL-2026-W4-longshot-1004-fd', 'gameIds': ['NFL-401872968', 'other'],
                  'legs': [{'title': 'Packers at Buccaneers over 38.5', 'gameId': 'NFL-401872968'},
                           {'title': 'Other leg', 'gameId': 'other'}]}
        note = '2026-10-04 11:45 ET: its Packers at Buccaneers over 38.5 leg was pulled: quarterback out. Stays in the record.'
        ctx = SimpleNamespace(first={pulled['id']: pulled}, latest={pulled['id']: dict(pulled, status='expired', entryNote=note)})
        self.assertEqual(run.longshot_exclusions(ctx, []), {'NFL-401872968'})
        games = {'other': {'kickoff': '2026-10-04T17:00:00Z'}}
        replacement = {'gameIds': ['other']}
        self.assertFalse(run.replacement_has_last_look(replacement, games, datetime(2026, 10, 4, 15, 45, 5, tzinfo=timezone.utc)))
        self.assertTrue(run.replacement_has_last_look(replacement, games, datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)))

    def test_unchecked_straights_do_not_exclude_whole_games_from_tickets(self):
        ctx, _, _, _ = self.world(closed=False)
        reasons = [
            'the eight-check research budget is used; availability was not checked',
            *[f'the {family} research allocation is used; availability was not checked'
              for family in ('prop', 'side', 'total')],
            'the news researcher is unavailable in this run',
            'the news check returned no verified player-availability evidence; college plays stay held',
            'the current estimated chance does not beat the price; no news lookup was spent',
        ]
        rows = [{'gameId': f'game-{i}', 'rule': 'held', 'reason': reason}
                for i, reason in enumerate(reasons)]
        self.assertEqual(run.longshot_exclusions(ctx, rows), set())
        rows += [{'gameId': 'adverse', 'rule': 'held',
                  'reason': 'the evidence argues against it: starting quarterback out'},
                 {'gameId': 'unknown-hold', 'rule': 'held', 'reason': 'unrecognized hold'},
                 {'gameId': 'injury', 'rule': 'prop_injury_clear', 'reason': reasons[0]}]
        self.assertEqual(run.longshot_exclusions(ctx, rows), {'adverse', 'unknown-hold', 'injury'})

    def test_the_last_look_checks_every_leg(self):
        ctx, _, ticket, _ = self.world(closed=False)
        looked = []

        wind = {'id': 'w1', 'kind': 'weather', 'direction': 'against', 'claim': 'rain and 25 mph wind'}

        def look(single, game, *rest):
            looked.append(single['title'])
            return ('the evidence argues against it: rain and 25 mph wind', [], [wind]) if game['id'] == 'army' else (None, [], [])
        reason = run.parlay_last_look(ticket, ctx, {}, False, {}, self.NOW, look=look)
        self.assertIsNone(reason, 'weather may flag the ticket but only typed hard injury news may pull it')
        soft = {'id': 'r1', 'kind': 'role', 'direction': 'against', 'origin': 'claude researcher', 'verified': True,
                'claim': "Quentin Johnston remains in the Chargers' receiver rotation while Ladd McConkey is the clearest fantasy option."}
        stands = run.parlay_last_look(ticket, ctx, {}, False, {}, self.NOW,
                                      look=lambda single, game, *rest: (f"verified reporting argues against it: {soft['claim']}", [], [soft]))
        self.assertIsNone(stands, 'Sunday 2026-09-27: a rotation note pulled the ladder; soft news never pulls a fun ticket')
        qb = {'id': 'injury-1-9', 'kind': 'injury', 'direction': 'against', 'position': 'QB',
              'status': 'Out', 'claim': 'The starting quarterback is listed Out.'}
        pulled_for_qb = run.parlay_last_look(ticket, ctx, {}, False, {}, self.NOW,
                                             look=lambda single, game, *rest: ('model flag', [], [qb]) if game['id'] == 'army' else (None, [], []))
        self.assertEqual(pulled_for_qb, 'its Army at Temple over 47.5 leg: typed injury report: The starting quarterback is listed Out.')
        looked.clear()
        clear = run.parlay_last_look(ticket, ctx, {}, False, {}, self.NOW, look=lambda *a: (None, [], []))
        self.assertIsNone(clear)
        closing = [dict(self.world()[3], status='expired', entryNote=self.NOTE)]
        pulled = run.parlay_last_look(ticket, ctx, {}, False, {}, self.NOW, closing=closing, look=lambda *a: self.fail('pulled first'))
        self.assertTrue(pulled.startswith('its Navy at UAB over 51.5 leg was pulled'))

    def test_release_pull_reason_ignores_model_and_web_flags(self):
        pick = {'athleteId': '77'}
        web = {'id': 'web-1', 'origin': 'claude researcher', 'kind': 'injury', 'direction': 'against',
               'position': 'QB', 'status': 'Out', 'claim': 'The quarterback was ruled out.'}
        weather = {'id': 'weather-1', 'kind': 'weather', 'direction': 'against', 'claim': 'Wind 25 mph.'}
        self.assertIsNone(run.release_pull_reason(pick, [web, weather]))
        player = {'id': 'injury-10-77', 'kind': 'injury', 'direction': 'against', 'position': 'WR',
                  'status': 'Inactive', 'claim': 'Player 77 is listed Inactive.'}
        self.assertEqual(run.release_pull_reason(pick, [player]), 'typed injury report: Player 77 is listed Inactive.')

    def test_the_price_check_takes_a_ticket_off_when_its_leg_was_pulled(self):
        from unittest import mock
        import x_post
        ctx, raw_first, ticket, _ = self.world()
        entry = {'id': ticket['id'], 'kind': 'buffer:play', 'bufferPostId': 'b', 'dueAt': run.stamp(self.NOW + timedelta(minutes=40))}
        log_book = {'posts': [entry]}
        stores = mock.MagicMock(reports=[], context_file={})
        stores.as_of.return_value = ctx
        lines = []
        with mock.patch.object(x_post, 'load_log', return_value=log_book), mock.patch.object(run, 'Lock'), \
                mock.patch.object(run, 'live_games', return_value=self.GAMES), mock.patch.object(run.features, 'load', return_value=[]), \
                mock.patch.object(run.gates, 'Stores', return_value=stores), mock.patch.object(run, 'raw_first_publications', return_value=raw_first), \
                mock.patch.object(run, 'live_context', return_value={}), mock.patch.object(run.llm, 'available', return_value=False), \
                mock.patch.object(run, 'close_moves', return_value=([], None)), mock.patch.object(run.desk, 'captures', return_value=[]), \
                mock.patch.object(run, 'last_look', side_effect=AssertionError('a pulled leg needs no news check')), \
                mock.patch.object(run, 'log', side_effect=lambda *parts: lines.append(' '.join(map(str, parts)))):
            self.assertEqual(run.precheck(SimpleNamespace(now=run.stamp(self.NOW), dry_run=True, no_llm=True, no_push=True)), 0)
        self.assertEqual(entry['precheck']['result'], 'closed')
        self.assertIn('Navy at UAB over 51.5', entry['precheck']['reason'])
        self.assertTrue(any('closed before its post' in line for line in lines))

    def test_a_run_waits_out_a_price_check_for_the_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.lock'
            held = run.Lock(path).__enter__()
            with self.assertRaises(run.RunError):
                run.Lock(path).__enter__()
            waits = []

            def sleep(seconds):
                waits.append(seconds)
                held.__exit__(None, None, None)          # the price check finishes while the run waits
            waiting = run.Lock(path, wait=60, sleep=sleep).__enter__()
            self.assertEqual(waits, [5])
            waiting.__exit__(None, None, None)
            clock = iter(range(0, 1000, 10))
            blocker = run.Lock(path).__enter__()
            with self.assertRaises(run.RunError):
                run.Lock(path, wait=30, sleep=lambda s: None, clock=lambda: next(clock)).__enter__()
            blocker.__exit__(None, None, None)

    def test_scheduled_run_alerts_when_lock_wait_expires(self):
        args = SimpleNamespace(now='2026-10-07T15:45:00Z', slot='1145', publish_kinds=None, dry_run=False)
        with mock.patch.object(run, 'Lock', side_effect=run.RunError('another run holds the lock')), \
                mock.patch.object(run, 'write_status') as save, mock.patch.object(run, 'alert') as phone:
            self.assertEqual(run.run(args), 1)
        self.assertIn('holds the lock', save.call_args.args[0]['outcome'])
        self.assertIn('holds the lock', phone.call_args.args[1])


class LockedUnitsTests(unittest.TestCase):
    def test_a_refused_straight_on_mnf_does_not_remove_mnf_from_the_climb_pool(self):
        now = datetime(2026, 10, 12, 10, 45, tzinfo=timezone.utc)
        games = {'mnf': {'id': 'mnf', 'league': 'NFL', 'state': 'pre',
                         'kickoff': '2026-10-13T00:15Z'}}
        world = SimpleNamespace(first={}, latest={}, games=games)
        screened = [{'gameId': 'mnf', 'rule': 'prop_injury_clear',
                     'reason': 'one unrelated receiver is listed out'}]
        with mock.patch('ladder.candidate', return_value=(None, 'no supported leg')) as choose, \
                mock.patch('ladder.record_shadow'):
            run.ladder_step(world, games, now, [], [], [], screened)
        choose.assert_called_once_with(world, games, now)

    def test_a_pulled_ladder_step_gets_no_replacement(self):
        ticket = {'id': 'NFL-2026-W3-ladder-0927-fd', '_league': 'NFL', 'title': 'Ladder step 2',
                  'parlayType': 'ladder', 'book': 'FanDuel', 'odds': -110, 'legs': [{}, {}], 'gameIds': ['g1'],
                  'ladder': {'run': 1, 'step': 2, 'stake': 94, 'payout': 180}}
        ctx = SimpleNamespace(first={ticket['id']: {'id': ticket['id']}}, latest={ticket['id']: {
            'entryNote': 'Closed before its post went out: injury', 'result': 'win'}}, games={},
            player_team={}, context_file={})
        published, decided, screened = [], [], []
        refusal = run.gates.Decision(False, 'not_republished', 'the rung already exists')
        with mock.patch('ladder.candidate', return_value=(ticket, None)), \
                mock.patch.object(run, 'evidence', return_value=[]), \
                mock.patch.object(run, 'plan_reasons', return_value=[{'type': 'matchup', 'class': 'B',
                    'direction': 'for', 'text': 'The matchup supports the alternate.'}]), \
                mock.patch.object(run, 'write_prose', side_effect=lambda pick, *_: pick), \
                mock.patch.object(run.gates, 'pulled_before_post', return_value=True), \
                mock.patch.object(run.gates, 'fresh_id', side_effect=AssertionError('the ladder never gets a replacement id')), \
                mock.patch.object(run.gates, 'admit', return_value=(False, [refusal])):
            run.ladder_step(ctx, {}, datetime(2026, 9, 27, 13, 0, tzinfo=timezone.utc), [], published, decided, screened)
        self.assertEqual(ticket['id'], 'NFL-2026-W3-ladder-0927-fd')
        self.assertEqual(published, [])

    def test_a_climb_rung_is_refused_until_every_leg_has_a_saved_research_reason(self):
        ticket = {'id': 'NFL-ladder', '_league': 'NFL', 'title': 'Climb step 1',
                  'parlayType': 'ladder', 'book': 'FanDuel', 'odds': -170,
                  'legs': [{'id': 'a', 'gameId': 'g1', 'title': 'A 40+ receiving yards'},
                           {'id': 'b', 'gameId': 'g2', 'title': 'B 30+ rushing yards'}],
                  'gameIds': ['g1', 'g2'], 'ladder': {'run': 3, 'step': 1, 'stake': 50, 'payout': 79}}
        ctx = SimpleNamespace(first={}, latest={}, games={'g1': {'season': 2026}},
                              player_team={}, context_file={})
        published, decided, screened = [], [], []
        with mock.patch('ladder.candidate', return_value=(ticket, None)), \
                mock.patch.object(run, 'evidence', return_value=[]), \
                mock.patch.object(run, 'plan_reasons', side_effect=[
                    [{'type': 'matchup', 'class': 'B', 'direction': 'for', 'text': 'A faces a bottom-10 defense.'}], []]), \
                mock.patch.object(run.gates, 'admit', side_effect=AssertionError('research refusal comes first')):
            run.ladder_step(ctx, {}, datetime(2026, 10, 9, 17, 30, tzinfo=timezone.utc), [],
                            published, decided, screened)
        self.assertEqual(published, [])
        self.assertEqual(screened[0]['rule'], 'ladder_research')
        self.assertIn('B 30+ rushing yards', screened[0]['reason'])
        self.assertEqual(ticket['legs'][0]['reason'], 'A faces a bottom-10 defense.')

    def test_a_climb_moneyline_uses_the_existing_research_budget_before_admission(self):
        ticket = {'id': 'NFL-ladder', '_league': 'NFL', 'title': 'Climb step 1',
                  'parlayType': 'ladder', 'book': 'DraftKings', 'odds': -240,
                  'legs': [{'id': 'a', 'gameId': 'g1', 'title': 'Patriots moneyline',
                            'marketType': 'moneyline', 'direction': 'home'}],
                  'gameIds': ['g1'], 'ladder': {'run': 3, 'step': 1, 'stake': 50, 'payout': 71}}
        game = {'id': 'g1', 'league': 'NFL', 'away': {'id': 'a', 'short': 'Raiders'},
                'home': {'id': 'h', 'short': 'Patriots'}, 'source': 'https://www.espn.com/nfl/game/g1'}
        ctx = SimpleNamespace(first={}, latest={}, games={'g1': game}, player_team={}, context_file={},
                              now=datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc),
                              passers={}, names={}, odds_history={}, records=[])
        published, decided, screened = [], [], []
        status = {'research': {'on': True, 'asked': 0, 'verified': 0, 'dropped': 0}}
        fact = {'kind': 'role', 'direction': 'for', 'claim': 'New England returns 4 starting linemen.',
                'source': 'https://example.com/report', 'origin': 'codex researcher',
                'retrievedAt': '2026-10-11T10:50:00Z'}
        refusal = run.gates.Decision(False, 'not_republished', 'fixture stops after research')
        with mock.patch('ladder.candidate', return_value=(ticket, None)), \
                mock.patch.object(run, 'evidence', return_value=[]), \
                mock.patch.object(run.researcher, 'enabled', return_value=True), \
                mock.patch.object(run.researcher, 'research', return_value=([fact], [])) as research, \
                mock.patch.object(run, 'write_prose', side_effect=lambda pick, *_: pick), \
                mock.patch.object(run.gates, 'admit', return_value=(False, [refusal])):
            run.ladder_step(ctx, {'g1': game}, datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc), [],
                            published, decided, screened, status=status)
        research.assert_called_once()
        self.assertEqual(status['research'], {'on': True, 'asked': 1, 'verified': 1, 'dropped': 0})
        self.assertEqual(ticket['legs'][0]['reason'], 'New England returns 4 starting linemen.')

    def test_a_graded_play_carries_its_units_at_the_published_price(self):
        self.assertEqual(run.lock_units({'odds': -111, 'result': 'win'})['units'], round(100 / 111, 3))
        self.assertEqual(run.lock_units({'odds': 583, 'result': 'loss', 'riskUnits': 0.25})['units'], -0.25, 'a parlay at its own stake')
        self.assertEqual(run.lock_units({'odds': -110, 'result': 'push'})['units'], 0.0)
        self.assertNotIn('units', run.lock_units({'odds': -110, 'result': 'void'}), 'a void has no units')
        self.assertNotIn('units', run.lock_units({'odds': None, 'result': 'win'}), 'no price, no units')

    def test_a_longshot_that_hits_pings_the_owner_to_pin_it(self):
        ctx = SimpleNamespace(first={'CFB-x-longshot': {'title': '3-leg longshot at ESPN BET', 'legs': [{}, {}, {}], 'odds': 583},
                                     'CFB-y': {'title': 'Iowa at Michigan over 38.5', 'odds': -105}}, latest={})
        plans = [('cashed:CFB-x-longshot', 'cashed', 'text', None, None), ('cashed:CFB-y', 'cashed', 'text', None, None),
                 ('CFB-z', 'play', 'text', None, 'CFB-z')]
        [(title, message)] = run.lotto_pings(plans, ctx)
        self.assertEqual(title, 'Longshot hit: pin it')
        self.assertIn('3-leg longshot at ESPN BET cashed at +583', message)

    def test_the_top_of_the_ladder_pings_the_owner_and_a_rung_has_its_own_words(self):
        top = {'title': 'Ladder step 5: 2 legs at FanDuel', 'parlayType': 'ladder', 'legs': [{}, {}], 'odds': 100,
               'ladder': {'run': 1, 'step': 5, 'stake': 675, 'payout': 850, 'banked': 150, 'bankThisWin': 170,
                          'bankedAfter': 320, 'nextStake': 680, 'totalAfter': 1000, 'bankPercent': 20,
                          'ridePercent': 80, 'start': 50, 'goal': 1000}}
        ctx = SimpleNamespace(first={'NFL-ladder': top, 'NFL-low': dict(top, ladder=dict(top['ladder'], step=2, stake=75,
                                                                                       payout=146, banked=19,
                                                                                       bankThisWin=29, bankedAfter=48,
                                                                                       nextStake=117, totalAfter=165))}, latest={})
        plans = [('cashed:NFL-ladder', 'cashed', 'text', None, None), ('cashed:NFL-low', 'cashed', 'text', None, None)]
        [(title, message)] = run.lotto_pings(plans, ctx)
        self.assertEqual(title, '80/20 Climb complete: pin it')
        self.assertIn('$1,000 from $50 in 5 steps', message)
        rung = run.write_prose(dict(top, book='FanDuel'), ctx, [])
        self.assertIn('$675 rides with $150 banked', rung['why'])
        self.assertIn('bank $170 and ride $680', rung['why'])
        self.assertIn('Every leg has to hit', rung['risk'])
        self.assertIn('cannot take money already banked', rung['risk'])
        game_rung = run.write_prose(dict(top, book='FanDuel', quoteType='capture',
                                       legs=[{'marketType':'spread'}, {'athleteId':'p'}, {'marketType':'spread'}]), ctx, [])
        self.assertIn('3 alternate lines', game_rung['why'])
        self.assertIn('not calibrated price edges', game_rung['risk'])
        self.assertNotIn('player who does not take the field', game_rung['risk'])

    def test_a_scheduled_rung_privately_tells_the_owner_the_ticket_and_release_times(self):
        due = datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc)  # noon Eastern
        ticket = {'id': 'NFL-ladder', 'parlayType': 'ladder', 'odds': -178, 'book': 'FanDuel',
                  'gameIds': ['g1', 'g2'],
                  'legs': [{'title': 'Saquon Barkley 40+ rushing yards'},
                           {'title': 'Amon-Ra St. Brown 4+ receptions'}],
                  'ladder': {'run': 2, 'step': 1, 'stake': 50, 'payout': 78}}
        ctx = SimpleNamespace(first={ticket['id']: ticket}, latest={})
        games = {'g1': {'kickoff': '2026-10-04T17:00:00Z'}, 'g2': {'kickoff': '2026-10-04T20:25:00Z'}}
        [(title, message)] = run.ladder_schedule_pings(
            [(ticket['id'], 'play', 'text', due, ticket['id'])], ctx, games)
        self.assertEqual(title, '80/20 Climb 2 Step 1 scheduled')
        for needle in ('$50 → $78 (-178, FanDuel)', 'Saquon Barkley 40+ rushing yards',
                       'Discord: about 11:45 AM ET', 'X: 12:00 PM ET', 'First kickoff: 1:00 PM ET',
                       'No wager was placed automatically'):
            self.assertIn(needle, message)

    def test_the_football_morning_agenda_lists_every_check_and_current_climb_state(self):
        now = datetime(2026, 10, 4, 10, 45, tzinfo=timezone.utc)  # Sunday 6:45 AM Eastern
        ctx = SimpleNamespace(first={}, latest={})
        games = {'g1': {'league': 'NFL', 'kickoff': '2026-10-04T17:00:00Z'}}
        sent = []
        with mock.patch.object(run, 'alert', side_effect=lambda title, message, **kwargs: sent.append((title, message)) or True):
            self.assertTrue(run.owner_agenda(now, ctx, games))
        self.assertEqual(len(sent), 1)
        self.assertIn('Regular desk checks: 6:45 AM', sent[0][1])
        self.assertIn('Extra Climb scans: 10:00 AM, 1:30 PM, 4:00 PM, 8:00 PM ET', sent[0][1])
        self.assertIn('Climb 1 Step 1 is being checked', sent[0][1])
        self.assertIn('exact legs, cutoff, Discord time and X time', sent[0][1])

    def test_a_queued_text_only_ladder_advance_is_upgraded_when_its_card_arrives(self):
        now = datetime(2026, 10, 3, 10, 45, tzinfo=timezone.utc)
        pick = {'id': 'CFB-ladder', 'parlayType': 'ladder', 'result': 'win',
                'ladder': {'step': 2, 'stake': 75, 'payout': 117}}
        ctx = SimpleNamespace(first={'CFB-ladder': pick}, latest={})
        log_book = {'posts': [{'id': 'cashed:CFB-ladder', 'kind': 'buffer:cashed', 'bufferPostId': 'old',
                               'dueAt': '2026-10-03T13:15:00Z', 'card': False,
                               'discord': {'state': 'pending', 'text': 'Step 2 cashed'}}]}
        with mock.patch('buffer_post.reachable', return_value=True), \
                mock.patch('buffer_post.create_post', return_value='new') as create, \
                mock.patch('buffer_post.delete_post') as delete:
            changed = run.upgrade_ladder_result_cards(log_book, ctx, now, channel={'id': 'x'}, log=lambda *_: None)
        self.assertEqual(changed, 1)
        entry = log_book['posts'][0]
        self.assertEqual(entry['bufferPostId'], 'new')
        self.assertTrue(entry['card'])
        self.assertEqual(entry['cardKey'], 'ladder-result-CFB-ladder')
        self.assertEqual(entry['discord']['image'], 'https://keenroudy.com/sports/data/cards/ladder-result-CFB-ladder.png')
        create.assert_called_once()
        delete.assert_called_once_with('old')

    def test_an_alert_can_open_a_link_and_wait(self):
        sent = []
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'KEENROUDY_NTFY_TOPIC': 'topic'}), \
                mock.patch.object(run, 'CONF', Path(folder)):
            run.alert('Longshot hit: pin it', 'body', click='https://x.com/keenkooks', delay='5m', send=sent.append)
        headers = {k.lower(): v for k, v in sent[0].header_items()}
        self.assertEqual((headers['click'], headers['delay']), ('https://x.com/keenkooks', '5m'))


class AbsorbTests(unittest.TestCase):
    def test_this_runs_settlements_and_closes_reach_the_posting_step(self):
        """A win settled at 11:30 PM gets its cashed post from that run, and a play closed in a run is never queued by it."""
        ctx = SimpleNamespace(latest={'a': {'status': 'active', 'odds': -110}})
        run.absorb(ctx, [('NFL', 'props', {'id': 'a', 'status': 'settled', 'result': 'win', 'settledAt': '2026-09-27T03:30:00Z'}),
                         ('CFB', 'gamePicks', {'id': 'b', 'status': 'expired', 'entryNote': 'Closed to new entries'})])
        self.assertEqual(ctx.latest['a'], {'status': 'settled', 'odds': -110, 'id': 'a', 'result': 'win', 'settledAt': '2026-09-27T03:30:00Z'})
        self.assertEqual(ctx.latest['b']['entryNote'], 'Closed to new entries')


class BufferPostsTests(unittest.TestCase):
    """Hosted art is checked without blocking the shared release lock."""

    def assert_optional_line_catalog_does_not_block_play(self, prepare):
        import buffer_post
        import news_posts
        import x_post
        from unittest import mock
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        ctx = type('Ctx', (), {'first': {}, 'latest': {}, 'player_team': {}})()
        plans = [('a', 'play', 'text', now, 'a')]
        status = {'errors': [], 'x': {}}
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            prepare(out)
            messages = []
            with mock.patch.dict(os.environ, {'BUFFER_TOKEN': 't'}), \
                    mock.patch.object(run.build_site, 'OUT', out), \
                    mock.patch.object(run, 'log', side_effect=messages.append), \
                    mock.patch.object(x_post, 'load_log', return_value={'posts': []}), \
                    mock.patch.object(x_post, 'save_log'), \
                    mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                    mock.patch.object(buffer_post, 'reconcile', return_value=[]), \
                    mock.patch.object(buffer_post, 'plan', return_value=plans), \
                    mock.patch.object(buffer_post, 'daily_limit', return_value=None), \
                    mock.patch.object(news_posts, 'candidates', return_value=[]) as news, \
                    mock.patch.object(buffer_post, 'schedule') as schedule:
                run.buffer_posts(now, ctx, {}, [], status, deploying=False,
                                 sleep=lambda _seconds: self.fail('slept'))
        schedule.assert_called_once()
        self.assertEqual(schedule.call_args[0][0], plans)
        self.assertEqual(status['x']['posted'], 0)
        self.assertEqual(news.call_args.args[2], [])
        self.assertTrue(any('optional use skipped' in message for message in messages))

    def test_missing_prebuild_lines_never_blocks_play_scheduling(self):
        self.assert_optional_line_catalog_does_not_block_play(lambda _out: None)

    def test_broken_line_shard_never_blocks_play_scheduling(self):
        def broken(out):
            (out / 'lines.json').write_text(json.dumps({
                'count': 1,
                'files': {'NFL': 'lines-NFL.json'},
            }))
            (out / 'lines-NFL.json').write_text('{broken json')

        self.assert_optional_line_catalog_does_not_block_play(broken)

    def test_missing_deployed_card_does_not_hold_the_posting_lock(self):
        import buffer_post
        import x_post
        from unittest import mock
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        ctx = type('Ctx', (), {'first': {}, 'latest': {}, 'player_team': {}})()
        plans = [('a', 'play', 'text', now, 'a')]
        answers = iter([False])
        slept, calls = [], []
        status = {'errors': [], 'x': {}}
        with mock.patch.dict(os.environ, {'BUFFER_TOKEN': 't'}), \
                mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(x_post, 'save_log'), \
                mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'reconcile', return_value=[]), \
                mock.patch.object(buffer_post, 'plan', side_effect=lambda *a, **k: calls.append(a[3]) or plans), \
                mock.patch.object(buffer_post, 'daily_limit', return_value={'remaining': 50}), \
                mock.patch.object(buffer_post, 'reachable', side_effect=lambda url: next(answers)), \
                mock.patch.object(buffer_post, 'schedule') as schedule:
            run.buffer_posts(now, ctx, {}, [], status, deploying=True, sleep=slept.append, clock=lambda: 0)
        self.assertEqual(slept, [], 'a hosted graphics wait must not block Discord/private releases')
        self.assertEqual(status['x']['cardsAwaitingDeploy'], 1)
        self.assertEqual(len(calls), 2, 'fresh due times still reach the guarded scheduler')
        schedule.assert_called_once()
        self.assertEqual(schedule.call_args[0][0], plans)
        self.assertEqual(status['errors'], [])

    def test_a_house_card_is_checked_at_its_own_address_and_a_held_post_is_reported(self):
        import buffer_post
        import x_post
        from unittest import mock
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        ctx = type('Ctx', (), {'first': {}, 'latest': {}, 'player_team': {}})()
        menu = 'https://keenroudy.com/sports/img/kitchen-menu-approved.png'
        plans = [('menu:day:2026-09-27', 'menu', 'text', now, menu)]

        def plan(*a, refused=None, **k):
            if refused is not None:
                refused.append(('receipt:day:2026-09-26', ['a sentence runs 241 characters']))
            return plans
        urls, alerts = [], []
        with mock.patch.dict(os.environ, {'BUFFER_TOKEN': 't'}), \
                mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(x_post, 'save_log'), \
                mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'reconcile', return_value=[]), \
                mock.patch.object(buffer_post, 'plan', side_effect=plan), \
                mock.patch.object(buffer_post, 'daily_limit', return_value=None), \
                mock.patch.object(buffer_post, 'reachable', side_effect=lambda url: urls.append(url) or True), \
                mock.patch.object(run, 'alert', side_effect=lambda title, message, **k: alerts.append(message)), \
                mock.patch.object(buffer_post, 'schedule'):
            run.buffer_posts(now, ctx, {}, [], {'errors': [], 'x': {}}, deploying=True, sleep=lambda s: self.fail('no wait for a live house card'), clock=lambda: 0)
        self.assertEqual(urls, [menu])
        self.assertEqual(alerts, ['receipt:day:2026-09-26: a sentence runs 241 characters'])

    def test_no_wait_without_a_deploy(self):
        import buffer_post
        import x_post
        from unittest import mock
        now = datetime(2026, 9, 27, 12, 40, tzinfo=timezone.utc)
        ctx = type('Ctx', (), {'first': {}, 'latest': {}, 'player_team': {}})()
        with mock.patch.dict(os.environ, {'BUFFER_TOKEN': 't'}), \
                mock.patch.object(x_post, 'load_log', return_value={'posts': []}), mock.patch.object(x_post, 'save_log'), \
                mock.patch.object(buffer_post, 'x_channel', return_value={'id': 'ch'}), \
                mock.patch.object(buffer_post, 'reconcile', return_value=[]), \
                mock.patch.object(buffer_post, 'plan', return_value=[('a', 'play', 't', now, 'a')]), \
                mock.patch.object(buffer_post, 'daily_limit', return_value=None), \
                mock.patch.object(buffer_post, 'reachable') as reachable, \
                mock.patch.object(buffer_post, 'schedule') as schedule:
            run.buffer_posts(now, ctx, {}, [], {'errors': [], 'x': {}}, deploying=False, sleep=lambda s: self.fail('slept'))
        reachable.assert_not_called()
        schedule.assert_called_once()


class DiscordMirrorTests(unittest.TestCase):
    def test_expired_result_remains_a_health_miss_without_endless_recovery(self):
        import desk_health,x_post
        now=datetime(2026,10,22,17,tzinfo=timezone.utc)
        data={'picks':[{'id':'old','posted':True,'result':'win','settledAt':'2026-10-21T03:03:48Z'}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'site/data/app/record.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data))
            with mock.patch.object(x_post,'load_log',return_value={'posts':[]}):
                self.assertEqual(run.result_recovery_needed(now,root,root/'private'),0)
            self.assertEqual(desk_health.result_timeliness(data,[],now)['missing'],1)

    def test_missing_result_recovery_is_bounded_and_ignores_a_future_queue(self):
        now = datetime(2026, 10, 18, 13, 15, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            conf = root / 'private'
            record = root / 'site/data/app/record.json'
            record.parent.mkdir(parents=True)
            record.write_text(json.dumps({'picks': [
                {'id': 'win', 'posted': True, 'result': 'win',
                 'settledAt': '2026-10-18T12:45:00Z'}]}))
            import x_post
            with mock.patch.object(x_post, 'load_log', return_value={'posts': []}):
                self.assertEqual(run.result_recovery_needed(now, root, conf), 1)
                run.mark_result_recovery(now, 1, conf)
                self.assertEqual(run.result_recovery_needed(now + timedelta(minutes=5), root, conf), 0)
            queued = {'posts': [{'id': 'cashed:win', 'bufferPostId': 'future',
                                 'dueAt': run.stamp(now + timedelta(minutes=7))}]}
            with mock.patch.object(x_post, 'load_log', return_value=queued):
                self.assertEqual(run.result_recovery_needed(now + timedelta(minutes=16), root, conf), 0)

    def test_only_due_or_sent_pending_entries_wake_the_mirror(self):
        now = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)
        post = lambda **over: dict({'id': 'a', 'bufferPostId': 'b', 'dueAt': run.stamp(now + timedelta(minutes=5)),
                                    'discord': {'state': 'pending', 'text': 'a'}}, **over)
        self.assertFalse(run.mirror_due({'posts': [post()]}, now))
        self.assertTrue(run.mirror_due({'posts': [post(dueAt=run.stamp(now - timedelta(minutes=1)))]}, now))
        self.assertTrue(run.mirror_due({'posts': [post(sentAt=run.stamp(now))]}, now))
        self.assertTrue(run.mirror_due({'posts': [post(discord={'state': 'pending', 'text': 'a',
                                                                 'readyAt': run.stamp(now)})]}, now))
        self.assertFalse(run.mirror_due({'posts': [post(discord={'state': 'pending', 'text': 'a',
                                                                  'readyAt': run.stamp(now + timedelta(minutes=1))})]}, now))
        self.assertFalse(run.mirror_due({'posts': [post(sentAt=run.stamp(now), discord={'state': 'sent'})]}, now))
        self.assertFalse(run.mirror_due({'posts': [post(cancelledAt=run.stamp(now))]}, now))
        self.assertTrue(run.mirror_due({'posts': [post(cancelledAt=run.stamp(now), discord={
            'state': 'sent', 'followup': {'state': 'pending', 'text': 'pulled'}})]}, now))

    def test_a_live_final_wakes_a_no_spend_official_settlement_run(self):
        now = datetime(2026, 10, 11, 2, 45, tzinfo=timezone.utc)
        watcher = SimpleNamespace(
            run_shadow=mock.Mock(return_value={'pendingFinals': ['CFB-play']}),
            mark_official_attempt=mock.Mock())
        progress = SimpleNamespace(run=mock.Mock())
        args = SimpleNamespace(now=run.stamp(now), dry_run=False, no_push=False, no_llm=False,
                               publish_kinds=None, record_screens=True, slot=None, command='mirror')
        with mock.patch.dict(sys.modules, {'live_watch': watcher, 'live_progress': progress}), \
                mock.patch.dict(os.environ, {'KEENROUDY_LIVE_SHADOW': '1', 'BUFFER_TOKEN': ''}, clear=False), \
                mock.patch.object(run, 'run', return_value=0) as official:
            self.assertEqual(run.mirror(args), 0)
        watcher.mark_official_attempt.assert_called_once_with(now)
        settlement = official.call_args.args[0]
        self.assertEqual((settlement.publish_kinds, settlement.no_llm, settlement.record_screens),
                         ('settle', True, False))
        self.assertEqual(settlement.slot, '2245')

    def test_a_missing_result_post_wakes_a_bounded_settlement_retry(self):
        now = datetime(2026, 10, 18, 13, 15, tzinfo=timezone.utc)
        watcher = SimpleNamespace(run_shadow=mock.Mock(return_value={'pendingFinals': []}))
        progress = SimpleNamespace(run=mock.Mock())
        args = SimpleNamespace(now=run.stamp(now), dry_run=False, no_push=False, no_llm=False,
                               publish_kinds=None, record_screens=True, slot=None, command='mirror')
        with mock.patch.dict(sys.modules, {'live_watch': watcher, 'live_progress': progress}), \
                mock.patch.dict(os.environ, {'KEENROUDY_LIVE_SHADOW': '1', 'BUFFER_TOKEN': ''}, clear=False), \
                mock.patch.object(run, 'result_recovery_needed', return_value=1), \
                mock.patch.object(run, 'result_transport_block', return_value=None), \
                mock.patch.object(run, 'mark_result_recovery') as marked, \
                mock.patch.object(run, 'run', return_value=0) as official:
            self.assertEqual(run.mirror(args), 0)
        marked.assert_called_once_with(now, 1)
        settlement = official.call_args.args[0]
        self.assertEqual((settlement.publish_kinds, settlement.no_llm, settlement.record_screens),
                         ('settle', True, False))


if __name__ == '__main__':
    unittest.main()


class CardRankTests(unittest.TestCase):
    def test_near_slate_uses_review_slots_before_monday(self):
        from tests.test_gates import context
        games = {}
        wanted = []
        for key, kickoff, market, edge in (
            ('monday', '2026-10-13T00:15:00Z', 'spread', 8.0),
            ('sunday', '2026-10-11T17:00:00Z', 'spread', 6.0),
            ('saturday', '2026-10-10T19:30:00Z', 'total', 5.0),
            ('thursday', '2026-10-09T00:15:00Z', 'spread', 4.0),
        ):
            games[key] = {'id': key, 'league': 'NFL' if key != 'saturday' else 'CFB',
                          'kickoff': kickoff}
            wanted.append({'id': key, 'gameIds': [key], 'marketType': market,
                           '_league': games[key]['league'], '_row': {'grade': {'edge': edge}}})
        ctx = context(games=games)
        self.assertEqual([c['id'] for c in run.rank_card(wanted, ctx)],
                         ['thursday', 'saturday', 'sunday', 'monday'])

    def test_equal_edges_use_line_id_regardless_of_manifest_order(self):
        from tests.test_gates import context
        now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        game = {'id': 'NFL-1', 'league': 'NFL', 'season': 2026, 'week': 4,
                'state': 'pre', 'kickoff': '2026-10-04T20:00:00Z'}
        rows = [
            {'id': 'z-line', 'league': 'NFL', 'gameId': 'NFL-1', 'state': 'open',
             'gameMarket': True, 'market': 'total points', 'direction': 'over', 'line': 44.5,
             'book': 'FanDuel', 'odds': -110, 'grade': {'tier': 'lean', 'edge': 3.0, 'raw': 0.60}},
            {'id': 'a-line', 'league': 'NFL', 'gameId': 'NFL-1', 'state': 'open',
             'gameMarket': True, 'market': 'total points', 'direction': 'under', 'line': 45.5,
             'book': 'DraftKings', 'odds': -110, 'grade': {'tier': 'lean', 'edge': 3.0, 'raw': 0.60}},
        ]
        first = run.candidates(rows, {'NFL-1': game}, now)
        second = run.candidates(list(reversed(rows)), {'NFL-1': game}, now)
        self.assertEqual([row['_row']['id'] for row in first], ['a-line', 'z-line'])
        self.assertEqual([row['_row']['id'] for row in second], ['a-line', 'z-line'])
        ctx = context()
        self.assertEqual([row['_row']['id'] for row in run.rank_card(first, ctx)], ['a-line', 'z-line'])

    def test_the_card_orders_by_edge_when_performance_cautions_still_clear_the_higher_bar(self):
        import learning
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_gates import context
        policy = learning.default_policy()
        policy['segments']['NFL/total'] = {'paused': True}
        policy['calibration']['NFL/prop'] = {'k': 0.5, 'n': 600}
        ctx = context(policy=policy, scoreboard={'props': {'markets': [{'market': 'recYds', 'graded': 200, 'closerThanLine': [80, 120]}]}})
        total = lambda key, edge, league='NFL': {'id': key, 'marketType': 'total', '_league': league, '_row': {'grade': {'edge': edge}}}
        prop = lambda key, market, raw, needs, odds: {'id': key, 'athleteId': key, 'market': market, '_league': 'NFL',
                                                      '_row': {'odds': odds, 'grade': {'raw': raw, 'needs': needs}}}
        wanted = [total('nfl-total', 4.0), total('cfb-total', 2.0, 'CFB'), prop('rec', 'rec', 0.70, 0.52, -110),
                  prop('yards', 'recYds', 0.80, 0.52, -110), prop('plus', 'rec', 0.90, 0.42, 151)]
        order = [c['id'] for c in run.rank_card(wanted, ctx)]
        self.assertEqual(order, ['plus', 'yards', 'rec', 'nfl-total', 'cfb-total'],
                         'positive-EV plus-money props stay eligible through +200 and the strongest reads lead')


class MirrorClockTests(unittest.TestCase):
    def exercise(self, explicit=False, veto=False):
        import chef_wins, discord_post, nba_editorial, x_post
        start = datetime(2026, 10, 21, 13, 19, 17, tzinfo=timezone.utc)
        after_recovery = start + timedelta(minutes=3)
        after_sync = start + timedelta(minutes=4)
        entry = {'id': 'nba-props-2026-10-21', 'bufferPostId': 'replacement',
                 'postedAt': run.stamp(after_recovery),
                 'dueAt': run.stamp(start + timedelta(hours=2))}
        book = {'posts': [entry]}
        args = SimpleNamespace(now=run.stamp(start) if explicit else None,
                               dry_run=False, no_push=True, slot=None,
                               no_llm=False, publish_kinds=None, record_screens=True)
        clock = mock.Mock()
        wall = [start]
        clock.now.side_effect = lambda *a, **kw: wall[0]
        seen = []
        def current(snapshot, now):
            seen.append(now)
            # The recovery/sync captures are valid at send time but newer than
            # the worker's original clock, as in the Oct 21 cancellation.
            return now >= after_sync and not veto
        with mock.patch.dict(os.environ, {'KEENROUDY_LIVE_SHADOW': '0', 'BUFFER_TOKEN': 'test'}), \
                mock.patch.object(run, 'datetime', clock), \
                mock.patch.object(run, 'result_recovery_needed', return_value=1), \
                mock.patch.object(run, 'result_transport_block', return_value=None), \
                mock.patch.object(run, 'mark_result_recovery'), \
                mock.patch.object(run, 'run', side_effect=lambda *_: wall.__setitem__(0, after_recovery) or 0), \
                mock.patch.object(run, 'Lock'), \
                mock.patch.object(run, 'sync', side_effect=lambda: wall.__setitem__(0, after_sync)), \
                mock.patch.object(run, 'commit_log'), mock.patch.object(run, 'alert'), \
                mock.patch.object(chef_wins, 'pending', return_value=[]), \
                mock.patch.object(discord_post, 'webhook', return_value='test'), \
                mock.patch.object(discord_post, 'mirror_sent', return_value=[]), \
                mock.patch.object(x_post, 'load_log', return_value=book), \
                mock.patch.object(x_post, 'save_log'), \
                mock.patch.object(run, 'private_release_ready', return_value=True), \
                mock.patch.object(run, 'release_private_isolated'), \
                mock.patch.object(nba_editorial, 'stored', return_value=[{'key': entry['id']}]), \
                mock.patch.object(nba_editorial, 'review_ready', return_value=True), \
                mock.patch.object(nba_editorial, 'props_current', side_effect=current), \
                mock.patch.object(buffer_post, 'delete_post') as delete:
            self.assertEqual(run.mirror(args), 0)
        return entry, seen, delete, clock

    def test_recovery_and_sync_refresh_clock_before_replacement_veto(self):
        entry, seen, delete, clock = self.exercise()
        self.assertNotIn('cancelledAt', entry)
        delete.assert_not_called()
        self.assertEqual(seen[-1], datetime(2026, 10, 21, 13, 23, 17, tzinfo=timezone.utc))

    def test_current_clock_still_cancels_a_real_price_or_role_hold(self):
        entry, _, delete, _ = self.exercise(veto=True)
        delete.assert_called_once_with('replacement', key=None, send=buffer_post.http_send)
        self.assertEqual(entry['cancelledAt'], '2026-10-21T13:23:17Z')

    def test_explicit_replay_clock_remains_fixed(self):
        entry, seen, delete, clock = self.exercise(explicit=True)
        self.assertTrue(all(t == datetime(2026, 10, 21, 13, 19, 17, tzinfo=timezone.utc) for t in seen))
        delete.assert_called_once()
        self.assertEqual(entry['cancelledAt'], '2026-10-21T13:19:17Z')
