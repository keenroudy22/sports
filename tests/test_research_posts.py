import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import receipts
import research_posts as R


NOW = datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc)  # 10 AM ET


def game(watch=None):
    row = {'id': 'CFB-1', 'league': 'CFB', 'kickoff': '2026-10-03T17:00:00Z', 'state': 'pre',
           'away': {'id': '1', 'abbr': 'FAV', 'name': 'Favorite'},
           'home': {'id': '2', 'abbr': 'DOG', 'name': 'Underdog'}}
    if watch:
        row['upsetWatch'] = watch
    return row


def projected_game(*, kickoff='2026-10-04T17:00:00Z', observed='2026-10-03T13:30:00Z'):
    return dict(game(), kickoff=kickoff,
                v2={'away': 24.5, 'home': 20.0, 'total': 44.5},
                market={'total': 41.5, 'retrievedAt': observed, 'book': 'FanDuel'})


class ResearchPostTests(unittest.TestCase):
    def test_end_zone_names_anytime_and_first_td_leans_and_followup_waits_for_a_verified_score(self):
        detail = {'scorerResearch': [
            {'player': 'First Scorer', 'athleteId': '101', 'games': 4, 'teamGames': 4,
             'inside10': 8, 'redZone': 12, 'touchdowns': 3, 'projectedOpportunities': 8,
             'roleSnapshotAt': '2026-10-03T13:00:00Z'},
            {'player': 'Second Scorer', 'athleteId': '202', 'games': 4, 'teamGames': 4,
             'inside10': 4, 'redZone': 10, 'touchdowns': 2, 'projectedOpportunities': 7,
             'roleSnapshotAt': '2026-10-03T13:00:00Z'},
        ]}
        choice = R.scorer_candidate([game()], {'CFB-1': detail}, NOW)
        self.assertEqual([row.get('tdLean', False) for row in choice['rows']], [True, False])
        self.assertEqual([row.get('firstTdDart', False) for row in choice['rows']], [True, False])
        self.assertIn('Anytime TD lean + first TD dart: First Scorer.', choice['text'])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            record = {'eventId': '1', 'players': [{'id': '101', 'rushTD': 1, 'recTD': 0}]}
            (root / 'cfb-2026.jsonl').write_text(__import__('json').dumps(record) + '\n')
            log = {'posts': [{'id': 'research:end-zone:2026-10-03', 'kind': 'buffer:research',
                              'sentAt': '2026-10-03T14:30:00Z',
                              'research': {'type': 'td-lean', 'player': 'First Scorer', 'athleteId': '101',
                                           'gameId': 'CFB-1', 'league': 'CFB',
                                           'kickoff': '2026-10-03T17:00:00Z'}}]}
            later = datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc)
            posts = R.touchdown_followups(log, later, box_root=root)
            self.assertEqual(len(posts), 1)
            self.assertIn('First Scorer found the end zone', posts[0]['text'])
            self.assertIn('TD lean', posts[0]['text'])
            log['posts'].append({'id': posts[0]['key']})
            self.assertEqual(R.touchdown_followups(log, later, box_root=root), [])

    def test_end_zone_can_track_two_distinct_calls_in_one_followup(self):
        log = {'posts': [{'id': 'research:end-zone:2026-10-03', 'kind': 'buffer:research',
                          'sentAt': '2026-10-03T14:30:00Z', 'research': {'type': 'td-lean', 'leans': [
                              {'player': 'Anytime Player', 'athleteId': '101', 'gameId': 'CFB-1',
                               'league': 'CFB', 'kickoff': '2026-10-03T17:00:00Z', 'anytime': True},
                              {'player': 'First Dart', 'athleteId': '202', 'gameId': 'CFB-1',
                               'league': 'CFB', 'kickoff': '2026-10-03T17:00:00Z', 'firstTd': True},
                          ]}}]}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            record = {'eventId': '1', 'players': [
                {'id': '101', 'rushTD': 1, 'recTD': 0}, {'id': '202', 'rushTD': 0, 'recTD': 1}]}
            (root / 'cfb-2026.jsonl').write_text(__import__('json').dumps(record) + '\n')
            posts = R.touchdown_followups(log, datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc), box_root=root)
        self.assertEqual(len(posts), 1)
        self.assertIn('Anytime Player and First Dart found the end zone', posts[0]['text'])
        self.assertIn('End-Zone Work call', posts[0]['text'])
        self.assertNotIn('first-TD dart', posts[0]['text'])

    def test_thursday_primetime_research_is_not_buried_by_other_games(self):
        now = datetime(2026, 10, 15, 12, 30, tzinfo=timezone.utc)  # Thu 8:30 AM ET
        college = dict(game(), kickoff='2026-10-15T23:30:00Z')
        tnf = {'id': 'NFL-tnf', 'league': 'NFL', 'kickoff': '2026-10-16T00:15:00Z',
               'state': 'pre', 'away': {'abbr': 'SEA'}, 'home': {'abbr': 'DEN'}}
        focused = {'kind': 'end-zone', 'rows': [
            {'gameId': 'NFL-tnf', 'kickoff': tnf['kickoff']},
            {'gameId': 'NFL-tnf', 'kickoff': tnf['kickoff']}], 'text': 'TNF work'}
        college_card = {'kind': 'season', 'rows': [
            {'gameId': 'CFB-1', 'kickoff': college['kickoff']},
            {'gameId': 'CFB-1', 'kickoff': college['kickoff']}], 'text': 'college'}
        logs = []
        with mock.patch.object(R, 'prep_candidate', return_value=None), \
             mock.patch.object(R, 'matchup_candidate', return_value=None), \
             mock.patch.object(R, 'scorer_candidate', side_effect=lambda games, *_: focused if games == [tnf] else None), \
             mock.patch.object(R, 'season_candidate', return_value=college_card):
            choice = R.select({'games': [college, tnf]}, {}, now, log=logs.append)
        self.assertEqual(choice['kind'], 'end-zone')
        self.assertEqual({row['gameId'] for row in choice['rows']}, {'NFL-tnf'})
        self.assertIn('research focus: TNF end-zone eligible: 2 rows', logs)

    def test_fallback_logs_each_attempt_and_stops_at_first_eligible_card(self):
        season = {'kind': 'season', 'rows': [{'kickoff': game()['kickoff']}] * 2}
        logs = []
        with mock.patch.object(R, 'prep_candidate', return_value=None), \
             mock.patch.object(R, 'season_candidate', return_value=season), \
             mock.patch.object(R, 'upset_candidate') as later:
            chosen = R.select({'games': [game()]}, {}, NOW, log=logs.append)
        self.assertEqual(chosen['kind'], 'season')
        self.assertEqual(logs, ['research rules: prep held — NFL: no current-day Prep List | CFB: no current-day Prep List',
                                'research fallback: prep held: no eligible card',
                                'research fallback: season eligible: 2 rows'])
        later.assert_not_called()

    def test_dark_fallback_logs_all_five_approved_categories(self):
        logs = []
        with mock.patch.object(R, 'prep_candidate', return_value=None), \
             mock.patch.object(R, 'season_candidate', return_value=None), \
             mock.patch.object(R, 'upset_candidate', return_value=None), \
             mock.patch.object(R, 'spread_dog_candidate', return_value=None), \
             mock.patch.object(R, 'matchup_candidate', return_value=None), \
             mock.patch.object(R, 'scorer_candidate', return_value=None):
            self.assertIsNone(R.select({'games': [game()]}, {}, NOW, log=logs.append))
        self.assertEqual(logs[0], 'research rules: prep held — NFL: no current-day Prep List | CFB: no current-day Prep List')
        self.assertEqual(logs[1:], [f'research fallback: {kind} held: no eligible card'
                                  for kind in ('prep', 'season', 'upset', 'matchup', 'end-zone')] +
                                 ['research fallback: numbers held: no stored projections'])

    def test_off_day_uses_the_next_slate_and_casual_verified_numbers(self):
        data = {'games': [projected_game()]}
        logs = []
        with mock.patch.object(R, 'season_candidate', return_value=None), \
             mock.patch.object(R, 'upset_candidate', return_value=None), \
             mock.patch.object(R, 'spread_dog_candidate', return_value=None), \
             mock.patch.object(R, 'matchup_candidate', return_value=None), \
             mock.patch.object(R, 'scorer_candidate', return_value=None):
            choice = R.select(data, {'CFB-1': {}}, NOW, log=logs.append)
        self.assertEqual(choice['kind'], 'numbers')
        self.assertTrue(choice['offDay'])
        self.assertEqual(choice['firstKickoff'].isoformat(), '2026-10-04T17:00:00+00:00')
        self.assertIn('my total 44.5, Vegas 41.5', choice['text'])
        self.assertIn('Not picks yet.', choice['text'])
        self.assertNotIn('AI', choice['text'])
        self.assertTrue(any(line == 'research fallback: numbers eligible: 1 rows' for line in logs))

    def test_numbers_fallback_never_prints_an_old_book_line(self):
        old = projected_game(observed='2026-10-02T13:00:00Z')
        choice = R.numbers_candidate([old], NOW)
        self.assertFalse(choice['usesPrice'])
        self.assertEqual(choice['title'], 'NEXT SLATE')
        self.assertNotIn('Vegas', choice['text'])
        self.assertIn('my score 24.5–20', choice['text'])

    def test_numbers_card_uses_plain_total_label_and_keeps_the_gap(self):
        import ticket_card
        choice = R.numbers_candidate([
            projected_game(),
            projected_game(kickoff='2026-10-04T20:00:00Z'),
        ], NOW)
        svg = ticket_card.research_list_svg(choice)
        self.assertIn('MY TOTAL', svg)
        self.assertIn('44.5', svg)
        self.assertIn('Vegas total 41.5', svg)
        self.assertIn('+3.0 vs Vegas', svg)

    def test_off_day_post_uses_the_daily_slot_and_future_kickoff_deadline(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            payload = Path(folder) / 'today.json'
            payload.write_text(json.dumps({'games': [projected_game()]}))
            with mock.patch.object(R, 'season_candidate', return_value=None), \
                 mock.patch.object(R, 'upset_candidate', return_value=None), \
                 mock.patch.object(R, 'spread_dog_candidate', return_value=None), \
                 mock.patch.object(R, 'matchup_candidate', return_value=None), \
                 mock.patch.object(R, 'scorer_candidate', return_value=None):
                post = R.post({}, NOW, payload, Path(folder), Path(folder) / 'none')
            self.assertEqual(post['key'], 'research:numbers:2026-10-03')
            self.assertEqual(post['due'].isoformat(), '2026-10-03T14:30:00+00:00')
            self.assertIsNone(post['card'])

    def test_one_game_numbers_post_is_text_only_instead_of_padding_the_card(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            payload = Path(folder) / 'today.json'
            payload.write_text(json.dumps({'games': [projected_game()]}))
            with mock.patch.object(R, 'season_candidate', return_value=None), \
                 mock.patch.object(R, 'upset_candidate', return_value=None), \
                 mock.patch.object(R, 'spread_dog_candidate', return_value=None), \
                 mock.patch.object(R, 'matchup_candidate', return_value=None), \
                 mock.patch.object(R, 'scorer_candidate', return_value=None):
                rendered = R.render_due(NOW, Path(folder) / 'cards', payload, Path(folder), Path(folder) / 'none')
            self.assertEqual(rendered, {})

    def test_prep_refusal_counts_use_the_same_rules_as_admission(self):
        row = {'league': 'CFB', 'book': 'FanDuel', 'odds': -110, 'clears': True,
               'projection': 55, 'observedAt': '2026-10-03T13:00:00Z',
               'kickoff': '2026-10-03T17:00:00Z'}
        rows = [row, dict(row, observedAt='2026-10-02T13:00:00Z'),
                dict(row, opponentAdjustment={'supports': False, 'against': True}),
                dict(row, kickoff='2026-10-03T14:30:00Z')]
        data = {'prep': {'CFB': {'day': '2026-10-03', 'rows': rows}}}
        reason = R.prep_diagnostics(data, NOW)
        self.assertIn('CFB: 1 eligible rows; requires 3', reason)
        self.assertIn('1 price missing, future or older than four hours', reason)
        self.assertIn('1 opponent-adjusted history does not support the side', reason)
        self.assertIn('1 missing kickoff or inside 45-minute cutoff', reason)
        self.assertIsNone(R.prep_candidate(data, NOW))

    def test_post_names_price_and_kickoff_refusals_independently(self):
        import json
        for observed, kickoff, expected in (
            ('2026-10-03T10:01:00Z', '2026-10-03T17:00:00Z', 'four-hour price expiry'),
            ('2026-10-03T13:00:00Z', '2026-10-03T14:46:00Z', '45-minute kickoff cutoff'),
        ):
            choice = {'kind': 'matchup', 'day': NOW.astimezone(R.gates.EASTERN).date(),
                      'firstKickoff': R.when(kickoff), 'rows': [{'observedAt': observed}],
                      'text': 'Research', 'key': 'fixture'}
            with tempfile.TemporaryDirectory() as folder:
                payload = Path(folder) / 'today.json'
                payload.write_text(json.dumps({'games': []}))
                logs = []
                with mock.patch.object(R, 'select', return_value=choice):
                    self.assertIsNone(R.post([], NOW, data_path=payload, detail_root=folder,
                                            lines_path=Path(folder) / 'none', log=logs.append))
                self.assertEqual(logs, [f'research: skipped matchup — {expected}'])
    def test_every_research_family_uses_the_ticket_list_after_cutover(self):
        import json
        now = datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)
        choice = {'kind': 'season', 'key': 'research-season-2026-10-09',
                  'title': 'TRENDS', 'kicker': 'OPPONENT-ADJUSTED',
                  'day': now.astimezone(R.gates.EASTERN).date(),
                  'firstKickoff': datetime(2026, 10, 9, 21, 0, tzinfo=timezone.utc),
                  'rows': [{'gameId': 'CFB-1', 'title': 'Player over 49.5 rec yds',
                            'price': '-110 FanDuel', 'metric': '7/10', 'detail': 'Defense #19',
                            'hits': 7, 'games': 10, 'observedAt': '2026-10-09T13:30:00Z'}],
                  'text': 'Trend research'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = root / 'today.json'
            payload.write_text(json.dumps({'games': []}))
            with mock.patch.object(R, 'select', return_value=choice), \
                 mock.patch.object(R.pick_card, 'ticket_enabled', return_value=True), \
                 mock.patch('ticket_card.research_list_svg', return_value='<svg/>') as art, \
                 mock.patch('pick_card.render', side_effect=lambda _svg, path: Path(path).write_bytes(b'png')):
                logs = []
                post = R.post([], now, data_path=payload, detail_root=root, lines_path=root / 'none', log=logs.append)
                self.assertEqual(post['card'], choice['key'])
                cards = R.render_due(now, root, data_path=payload, detail_root=root,
                                     lines_path=root / 'none', fetch=lambda _: None)
                self.assertIn(choice['key'], cards)
                art.assert_called_once()
                self.assertTrue(any(line.startswith('research: scheduled season') for line in logs))

    def test_fallback_order_and_exact_skip_log(self):
        data = {'games': [game()]}
        choices = {
            'prep_candidate': None, 'season_candidate': {'kind': 'season', 'rows': [
                {'kickoff': game()['kickoff']}, {'kickoff': game()['kickoff']}], 'text': 'trends'},
            'upset_candidate': {'kind': 'upset'}, 'spread_dog_candidate': {'kind': 'spread-dog'},
            'matchup_candidate': {'kind': 'matchup'}, 'scorer_candidate': {'kind': 'end-zone'},
        }
        patches = [mock.patch.object(R, name, return_value=value) for name, value in choices.items()]
        for patch in patches: patch.start()
        try:
            selected = R.select(data, {'CFB-1': {}}, NOW)
            self.assertEqual(selected['kind'], 'season')
        finally:
            for patch in reversed(patches): patch.stop()

    def test_confirmed_learning_order_can_move_a_mature_family(self):
        data = {'games': [game()]}
        season = {'kind': 'season', 'rows': [{'kickoff': game()['kickoff']}] * 2, 'text': 'trends'}
        matchup = {'kind': 'matchup', 'rows': [{'kickoff': game()['kickoff']}] * 2, 'text': 'matchup'}
        with mock.patch.object(R, 'prep_candidate', return_value=None), \
             mock.patch.object(R, 'season_candidate', return_value=season), \
             mock.patch.object(R, 'upset_candidate', return_value=None), \
             mock.patch.object(R, 'spread_dog_candidate', return_value=None), \
             mock.patch.object(R, 'matchup_candidate', return_value=matchup), \
             mock.patch.object(R, 'scorer_candidate', return_value=None):
            chosen = R.select(data, {'CFB-1': {}}, NOW,
                              order=['matchup', 'prep', 'season', 'upset', 'end-zone'])
        self.assertEqual(chosen['kind'], 'matchup')
        with tempfile.TemporaryDirectory() as folder:
            payload = Path(folder) / 'today.json'
            payload.write_text(__import__('json').dumps({'games': []}))
            logs = []
            self.assertIsNone(R.post({}, NOW, payload, Path(folder), Path(folder) / 'none', log=logs.append))
            self.assertEqual(logs, ['research: skipped — no stored football game in the next seven days'])

    def test_prep_list_takes_one_research_slot_only_with_three_fresh_checked_rows(self):
        now = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)  # 9 AM Eastern
        rows = [{'league': 'CFB', 'player': f'Player {i}', 'athleteId': str(1000 + i),
                 'gameId': 'CFB-1', 'kickoff': '2026-10-03T17:00:00Z',
                 'observedAt': '2026-10-03T12:30:00Z', 'book': 'FanDuel', 'odds': -115,
                 'line': 49.5, 'direction': 'over', 'stat': 'recYds', 'hits': 6, 'games': 6,
                 'clears': True, 'projection': 57.2}
                for i in range(3)]
        data = {'games': [game()], 'prep': {'CFB': {'day': '2026-10-03', 'rows': rows}}}
        choice = R.select(data, {'CFB-1': {}}, now)
        self.assertEqual(choice['kind'], 'prep')
        self.assertIn('Player 0 over 49.5 rec yds -115 FD · my number 57.2, line 49.5 · 6/6', choice['text'])
        self.assertIn('Lines that keep clearing today:', choice['text'])
        self.assertLessEqual(len(choice['text']), 280)
        self.assertEqual(receipts.guard({'text': choice['text']}), [])
        with tempfile.TemporaryDirectory() as folder:
            payload = Path(folder) / 'today.json'
            payload.write_text(__import__('json').dumps(data))
            post = R.post([], now, data_path=payload, detail_root=Path(folder), lines_path=Path(folder) / 'none')
            self.assertEqual(post['due'].isoformat(), '2026-10-03T13:30:00+00:00')
            self.assertEqual(post['kind'], 'research')
            with mock.patch('ticket_card.prep_svg', return_value='<svg/>') as art, \
                 mock.patch('pick_card.render', side_effect=lambda _svg, path: Path(path).write_bytes(b'png')):
                cards = R.render_due(now, folder, data_path=payload, detail_root=Path(folder),
                                     lines_path=Path(folder) / 'none', fetch=lambda _: None)
            self.assertIn(choice['key'], cards)
            art.assert_called_once()
            early = {'games': [dict(game(), kickoff='2026-10-03T14:00:00Z')],
                     'prep': {'CFB': {'day': '2026-10-03', 'rows': [dict(row, kickoff='2026-10-03T14:00:00Z') for row in rows]}}}
            payload.write_text(__import__('json').dumps(early))
            self.assertIsNone(R.post([], now, data_path=payload, detail_root=Path(folder),
                                     lines_path=Path(folder) / 'none'),
                              'a scheduled research post cannot land after its 45-minute cutoff')
        data['prep']['CFB']['rows'] = rows[:2]
        self.assertIsNone(R.prep_candidate(data, now))
        data['prep']['CFB']['rows'] = [dict(row, observedAt='2026-10-02T12:30:00Z') for row in rows]
        self.assertIsNone(R.prep_candidate(data, now))

    def test_split_college_defense_payload_is_followed_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'teams'
            root.mkdir()
            (root / 'CFB.json').write_text('{"teams":{},"defenseFile":"teams/CFB-defense.json"}')
            (root / 'CFB-defense.json').write_text('{"defense":{"rows":{"2":{"RB":{"rushYds":200}}}}}')
            payload = R.teams_for([{'league': 'CFB'}], root)['CFB']
            self.assertEqual(payload['defense']['rows']['2']['RB']['rushYds'], 200)
            (root / 'CFB.json').write_text('{"teams":{},"defenseFile":"../../private.json"}')
            self.assertNotIn('defense', R.teams_for([{'league': 'CFB'}], root)['CFB'])

    def test_long_captions_keep_whole_exact_preview_rows_and_all_graphic_evidence(self):
        from copy import deepcopy
        import x_post
        rows = [{'title': name, 'price': f'{i + 3} inside the 10', 'metric': f'{i + 8} red-zone opportunities',
                 'detail': '3 rush/rec TDs | 3/3 games observed', 'league': 'NFL', 'book': 'FanDuel'}
                for i, name in enumerate(('Bijan Robinson', 'Juwan Johnson', 'Tyler Shough', 'Chris Olave'))]
        original = deepcopy(rows)
        choice = {'kind': 'end-zone', 'title': 'END-ZONE WORK', 'text': 'x' * 352, 'rows': rows}
        text = R.bounded_caption(choice)
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertIn('Bijan Robinson: 8 red-zone', text)
        for row in rows:
            self.assertIn(row['title'], text)
        self.assertIn('8 red-zone', text)
        self.assertRegex(text, r'3 inside (?:the )?10')
        self.assertNotIn('not official', text.lower())
        self.assertNotIn('save this', text.lower())
        self.assertEqual(choice['rows'], original)
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_end_zone_caption_preserves_distinct_calls_and_all_facts_when_they_fit(self):
        from copy import deepcopy
        import x_post
        rows = [
            {'title': 'First Scorer', 'metric': '12 red-zone opportunities', 'price': '8 inside the 10',
             'firstTdDart': True, 'league': 'NFL'},
            {'title': 'Anytime Player', 'metric': '9 red-zone opportunities', 'price': '4 inside the 10',
             'tdLean': True, 'league': 'NFL'},
            {'title': 'Other Player', 'metric': '7 red-zone opportunities', 'price': '2 inside the 10', 'league': 'NFL'}]
        original = deepcopy(rows)
        text = R.bounded_caption({'kind': 'end-zone', 'rows': rows, 'text': 'original'})
        self.assertIn('First Scorer (first TD dart)', text)
        self.assertIn('Anytime Player (anytime TD lean)', text)
        self.assertNotIn('My TD lean: First Scorer', text)
        for row in rows:
            self.assertIn(row['title'], text)
        self.assertIn('12 red-zone', text)
        self.assertRegex(text, r'8 inside (?:the )?10')
        self.assertEqual(rows, original)
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_end_zone_long_caption_keeps_both_calls_without_inventing_a_call(self):
        import x_post
        rows = [
            {'title': 'First Scorer', 'metric': '12 red-zone opportunities', 'price': '8 inside the 10',
             'firstTdDart': True, 'league': 'NFL'},
            {'title': 'Anytime Player', 'metric': '9 red-zone opportunities', 'price': '4 inside the 10',
             'tdLean': True, 'league': 'NFL'},
            *[{'title': 'Long Background Player Name ' + str(i), 'metric': '7 red-zone opportunities',
               'price': '2 inside the 10', 'league': 'NFL'} for i in range(4)]]
        text = R.bounded_caption({'kind': 'end-zone', 'rows': rows, 'text': 'original'})
        self.assertIn('Anytime TD lean: Anytime Player', text)
        self.assertIn('First TD dart: First Scorer', text)
        self.assertNotIn('My TD lean: First Scorer', text)
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_each_research_family_has_a_bounded_fallback_even_for_long_names(self):
        import x_post
        for kind in ('end-zone', 'matchup', 'season', 'upset', 'spread-dog', 'numbers'):
            with self.subTest(kind=kind):
                choice = {'kind': kind, 'title': '90%+ TREND BOARD', 'text': 'x' * 900,
                          'rows': [{'title': 'Very Long Exact Player Name ' * 20, 'price': 'over 19.5 (-110)',
                                    'metric': '9/10 this season', 'book': 'FanDuel', 'league': 'NFL'}]}
                text = R.bounded_caption(choice)
                self.assertLessEqual(x_post.tweet_length(text), 280)
                self.assertNotIn('Very Long', text, 'never slice an impossible exact line in half')
                self.assertIn('Details on the card', text)
                self.assertNotIn('not official', text.lower())
                self.assertEqual(receipts.guard({'text': text}), [])
        self.assertEqual(R.bounded_caption({'text': 'Already short.'}), 'Already short.')

    def test_fresh_upset_has_priority_and_is_plainly_not_a_play(self):
        watch = {'side': 'home', 'team': 'Underdog', 'odds': 160, 'opponentOdds': -192,
                 'book': 'DraftKings', 'observedAt': '2026-10-03T13:30:00Z',
                 'modelChance': .60, 'marketChanceNoVig': .369,
                 'projectedFor': 27, 'projectedAgainst': 23, 'spreadGap': 7.5,
                 'reasons': ['Our score has Underdog by 4', "Underdog's offense rates 2.1 points above average"]}
        second = dict(game(watch), id='CFB-2')
        choice = R.select({'games': [game(watch), second]}, {'CFB-1': {}, 'CFB-2': {}}, NOW)
        self.assertEqual(choice['kind'], 'upset')
        self.assertIn('Underdog +160 ML (DK)', choice['text'])
        self.assertIn('Possible outright dogs:', choice['text'])
        self.assertNotIn('more on the card', choice['text'])
        self.assertNotIn('not official', choice['text'].lower())
        self.assertEqual(choice['rows'][0]['metric'], 'Our score DOG 27–23 FAV')
        self.assertIn('7.5-pt gap vs spread', choice['rows'][0]['detail'])
        self.assertIn("offense rates 2.1 points above average", choice['rows'][0]['reason'])
        post = {'text': choice['text']}
        self.assertEqual(receipts.guard(post), [])

    def test_upset_caption_names_each_team_instead_of_hiding_a_row_count(self):
        choice = {'kind': 'upset', 'title': 'UNDERDOG WATCH', 'text': 'x' * 900,
                  'rows': [
                      {'title': 'Eagles', 'price': '+140 ML', 'book': 'DraftKings', 'league': 'NFL'},
                      {'title': 'Buccaneers', 'price': '+120 ML', 'book': 'DraftKings', 'league': 'NFL'},
                  ]}
        text = R.bounded_caption(choice)
        self.assertEqual(text, '\n'.join(['🐕 UNDERDOG WATCH', 'Possible outright dogs:',
                                          'Eagles +140 ML (DK)', 'Buccaneers +120 ML (DK)', '#NFL']))
        self.assertNotRegex(text, r'\+\d+ more on the card')
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_matchup_and_end_zone_are_fallbacks_not_streak_guarantees(self):
        detail = {'favoriteLines': [{'id': 'runner', 'sourceId': 'runner', 'kind': 'player',
                                     'title': 'Runner over 55.5 rushing yards', 'athleteId': '7',
                                     'book': 'FanDuel', 'odds': -110, 'projection': 70,
                                     'team': '1', 'teamAbbr': 'FAV', 'opponent': '2', 'opponentAbbr': 'DOG',
                                     'position': 'RB', 'stat': 'rushYds', 'direction': 'over',
                                     'edge': 3.0, 'observedAt': '2026-10-03T13:00:00Z',
                                     'history': {'last': {'hits': 8, 'games': 10, 'rate': 80}}}],
                  'scorerResearch': [{'player': 'Runner', 'athleteId': '7', 'games': 4, 'teamGames': 4,
                                      'redZone': 12, 'inside10': 7, 'touchdowns': 3,
                                      'roleSnapshotAt': '2026-10-02T12:00:00Z'}]}
        teams = {'CFB': {'defense': {'rows': {
            '2': {'RB': {'rushYds': 200}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '3': {'RB': {'rushYds': 100}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '4': {'RB': {'rushYds': 50}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
        }}}}
        second = dict(game(), id='CFB-2')
        detail2 = __import__('copy').deepcopy(detail)
        detail2['favoriteLines'][0]['id'] = detail2['favoriteLines'][0]['sourceId'] = 'runner-2'
        choice = R.select({'games': [game(), second]}, {'CFB-1': detail, 'CFB-2': detail2}, NOW, teams=teams)
        self.assertEqual(choice['kind'], 'matchup')
        self.assertIn('Runner over 55.5 rushing yards', choice['text'])
        self.assertIn('8/10 at this line · DOG #3/3 vs RB rush yds', choice['text'])
        self.assertEqual(choice['title'], 'MATCHUP TRENDS')
        self.assertEqual(receipts.guard({'text': choice['text']}), [])
        detail['favoriteLines'][0]['history']['last']['rate'] = 70
        detail2['favoriteLines'][0]['history']['last']['rate'] = 70
        choice = R.select({'games': [game(), second]}, {'CFB-1': detail, 'CFB-2': detail2}, NOW, teams=teams)
        self.assertEqual(choice['kind'], 'end-zone')
        self.assertIn('12 red-zone opportunities · 7 inside the 10', choice['text'])

    def test_matchup_trends_rank_cfb_blowout_context_down_without_changing_the_line(self):
        safe = game()
        safe['id'] = 'CFB-safe'
        safe['v2'] = {'away': 27, 'home': 24}
        risk = game()
        risk['id'] = 'CFB-risk'
        risk['v2'] = {'away': 10, 'home': 35}
        def line(name, source, game_id, hits):
            return {'id': source, 'sourceId': source, 'kind': 'player', 'title': name,
                    'athleteId': source, 'book': 'FanDuel', 'odds': -110, 'projection': 70,
                    'team': '1', 'teamAbbr': 'FAV', 'opponent': '2', 'opponentAbbr': 'DOG',
                    'position': 'RB', 'stat': 'rushYds', 'direction': 'over', 'edge': 3.0,
                    'observedAt': '2026-10-03T13:00:00Z',
                    'history': {'last': {'hits': hits, 'games': 10, 'rate': hits * 10},
                                'season': {'hits': 3, 'games': 4, 'rate': 75}}}
        details = {'CFB-safe': {'favoriteLines': [line('Safe over 55.5 rushing yards', 'safe', 'CFB-safe', 8)]},
                   'CFB-risk': {'favoriteLines': [line('Risk over 55.5 rushing yards', 'risk', 'CFB-risk', 10)]}}
        teams = {'CFB': {'defense': {'rows': {
            '2': {'RB': {'rushYds': 200}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '3': {'RB': {'rushYds': 100}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
            '4': {'RB': {'rushYds': 50}, 'coverage': {'RB': {'rushYds': 4}}, 'g': 4},
        }}}}
        choice = R.matchup_candidate([risk, safe], details, NOW, teams)
        self.assertEqual([row['title'] for row in choice['rows']],
                         ['Safe over 55.5 rushing yards', 'Risk over 55.5 rushing yards'])
        self.assertTrue(choice['rows'][1]['scriptRisk'])
        self.assertEqual((choice['rows'][0]['seasonHits'], choice['rows'][0]['seasonGames']), (3, 4))
        self.assertIn('FAV projected 25-pt dog', choice['rows'][1]['detail'])
        self.assertIn('CFB big-underdog usage is ranked down', choice['text'])

    def test_spread_dogs_are_cover_watches_not_upset_calls(self):
        line = {'gameId': 'CFB-1', 'gameMarket': True, 'market': 'point spread', 'state': 'open',
                'line': 8.5, 'odds': -105, 'book': 'ESPN BET', 'side': 'home',
                'observedAt': '2026-10-03T13:30:00Z',
                'grade': {'tier': 'lean', 'chance': .54, 'needs': .512, 'edge': 2.8, 'projection': 1.0}}
        second = dict(game(), id='CFB-2')
        line2 = dict(line, gameId='CFB-2')
        choice = R.select({'games': [game(), second]}, {'CFB-1': {}, 'CFB-2': {}}, NOW, [line, line2])
        self.assertEqual(choice['kind'], 'spread-dog')
        self.assertIn('Underdog +8.5 (-105) theScore Bet', choice['text'])
        self.assertNotIn('not an upset', choice['text'].lower())
        self.assertIn('Underdog +8.5 (-105)', choice['text'])

        line['book'] = 'theScore Bet'
        line2['book'] = 'theScore Bet'
        choice = R.select({'games': [game(), second]}, {'CFB-1': {}, 'CFB-2': {}}, NOW, [line, line2])
        self.assertEqual(choice['kind'], 'spread-dog')
        self.assertIn('Underdog +8.5 (-105) theScore Bet', choice['text'])

    def test_post_window_and_card_are_stale_safe(self):
        watch = {'side': 'home', 'team': 'Underdog', 'odds': 160, 'opponentOdds': -192,
                 'book': 'DraftKings', 'observedAt': '2026-10-03T13:30:00Z',
                 'modelChance': .60, 'marketChanceNoVig': .369}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'games').mkdir()
            second = dict(game(watch), id='CFB-2')
            (root / 'today.json').write_text(__import__('json').dumps({'games': [game(watch), second]}))
            (root / 'games' / 'CFB-1.json').write_text('{}')
            (root / 'games' / 'CFB-2.json').write_text('{}')
            post = R.post({}, NOW, root / 'today.json', root / 'games')
            self.assertEqual((post['kind'], post['card']), ('research', 'research-upset-2026-10-03'))
            self.assertEqual(post['due'], datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc))
            choice = R.select({'games': [game(watch), second]}, {'CFB-1': {}, 'CFB-2': {}}, NOW)
            import ticket_card
            card = ticket_card.research_list_svg(choice)
            self.assertIn('UNDERDOG WATCH', card)
            self.assertIn('RESEARCH · NOT A BET', card)
            self.assertNotIn('SLATE RESEARCH', card)
            for ugly in ('#8b4513', '#a0522d', '#cd853f'):
                self.assertNotIn(ugly, card.lower())


if __name__ == '__main__':
    unittest.main()
