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


class ResearchPostTests(unittest.TestCase):
    def test_unconverted_research_is_held_after_ticket_cutover(self):
        import json
        now = datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)
        choice = {'kind': 'season', 'key': 'research-season-2026-10-09',
                  'day': now.astimezone(R.gates.EASTERN).date(),
                  'firstKickoff': datetime(2026, 10, 9, 21, 0, tzinfo=timezone.utc),
                  'rows': [{'observedAt': '2026-10-09T13:30:00Z'}], 'text': 'Trend research'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = root / 'today.json'
            payload.write_text(json.dumps({'games': []}))
            with mock.patch.object(R, 'select', return_value=choice), \
                 mock.patch.object(R.pick_card, 'ticket_enabled', return_value=True), \
                 mock.patch.object(R, 'svg', side_effect=AssertionError('old art must not render')):
                self.assertIsNone(R.post([], now, data_path=payload, detail_root=root, lines_path=root / 'none'))
                self.assertEqual(R.render_due(now, root, data_path=payload, detail_root=root,
                                              lines_path=root / 'none'), {})

    def test_requested_tnf_ticket_is_one_game_only_and_expires_before_kickoff(self):
        import json
        now = datetime(2026, 10, 8, 22, 40, tzinfo=timezone.utc)
        game_row = {'id': 'NFL-401872980', 'league': 'NFL', 'kickoff': '2026-10-09T00:15:00Z',
                    'state': 'pre', 'away': {'abbr': 'TB'}, 'home': {'abbr': 'DAL'}}
        detail = {'scorerResearch': [
            {'player': 'Javonte Williams', 'athleteId': '4429111', 'roleSnapshotAt': '2026-10-08T20:00:00Z',
             'games': 4, 'teamGames': 4, 'inside10': 12, 'redZone': 21, 'touchdowns': 3}]}
        data = {'games': [game_row]}
        choice = R.owner_tnf_ticket(data, {game_row['id']: detail}, now)
        self.assertEqual(choice['key'], 'research-end-zone-tnf-ticket-2026-10-08')
        self.assertIn('not a TD pick or official play', choice['text'])
        self.assertIsNone(R.owner_tnf_ticket(data, {game_row['id']: detail},
                                              datetime(2026, 10, 9, 0, 5, tzinfo=timezone.utc)))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = root / 'today.json'
            payload.write_text(json.dumps(data))
            (root / f"{game_row['id']}.json").write_text(json.dumps(detail))
            self.assertIsNone(R.post([], now, data_path=payload, detail_root=root, lines_path=root / 'none'),
                              'the new card is not a public-post approval by itself')
            with mock.patch.dict('os.environ', {'KEENROUDY_TNF_TICKET_APPROVED': '1'}):
                post = R.post([], now, data_path=payload, detail_root=root, lines_path=root / 'none')
            self.assertEqual(post['card'], choice['key'])
            self.assertEqual(post['due'].isoformat(), '2026-10-08T23:00:00+00:00')
            with mock.patch.dict('os.environ', {'KEENROUDY_TNF_TICKET_APPROVED': '1'}):
                late = R.post([], datetime(2026, 10, 8, 23, 20, tzinfo=timezone.utc),
                              data_path=payload, detail_root=root, lines_path=root / 'none')
            self.assertEqual(late['due'].isoformat(), '2026-10-08T23:22:00+00:00')
            with mock.patch('ticket_card.end_zone_svg', return_value='<svg/>') as art, \
                 mock.patch('pick_card.render', side_effect=lambda _svg, path: Path(path).write_bytes(b'png')):
                cards = R.render_due(now, root, data_path=payload, detail_root=root,
                                     lines_path=root / 'none', fetch=lambda _: None)
            self.assertIn(choice['key'], cards)
            art.assert_called_once()

    def test_prep_list_takes_one_research_slot_only_with_three_fresh_checked_rows(self):
        now = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)  # 9 AM Eastern
        rows = [{'league': 'CFB', 'player': f'Player {i}', 'athleteId': str(1000 + i),
                 'gameId': 'CFB-1', 'kickoff': '2026-10-03T17:00:00Z',
                 'observedAt': '2026-10-03T12:30:00Z', 'book': 'FanDuel', 'odds': -115,
                 'line': 49.5, 'direction': 'over', 'stat': 'recYds', 'hits': 6, 'games': 6}
                for i in range(3)]
        data = {'games': [game()], 'prep': {'CFB': {'day': '2026-10-03', 'rows': rows}}}
        choice = R.select(data, {'CFB-1': {}}, now)
        self.assertEqual(choice['kind'], 'prep')
        self.assertIn('Player 0 over 49.5 rec yds (-115, FanDuel)', choice['text'])
        self.assertIn('Save it for kickoff', choice['text'])
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
        self.assertIn('Bijan Robinson', text)
        self.assertIn('8 red-zone opportunities · 3 inside the 10', text)
        self.assertNotIn('not official', text.lower())
        self.assertNotIn('save this', text.lower())
        self.assertEqual(choice['rows'], original)
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_each_research_family_has_a_bounded_fallback_even_for_long_names(self):
        import x_post
        for kind in ('end-zone', 'matchup', 'season', 'upset', 'spread-dog'):
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
        choice = R.select({'games': [game(watch)]}, {'CFB-1': {}}, NOW)
        self.assertEqual(choice['kind'], 'upset')
        self.assertIn('Underdog +160 ML (DK)', choice['text'])
        self.assertIn('Model 60% | market 37%', choice['text'])
        self.assertNotIn('not official', choice['text'].lower())
        self.assertEqual(choice['rows'][0]['metric'], 'Our score DOG 27–23 FAV')
        self.assertIn('7.5-pt gap vs spread', choice['rows'][0]['detail'])
        self.assertIn("offense rates 2.1 points above average", choice['rows'][0]['reason'])
        post = {'text': choice['text']}
        self.assertEqual(receipts.guard(post), [])

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
        choice = R.select({'games': [game()]}, {'CFB-1': detail}, NOW, teams=teams)
        self.assertEqual(choice['kind'], 'matchup')
        self.assertIn('Runner over 55.5 rushing yards', choice['text'])
        self.assertIn('8/10 at this line · DOG #3/3 vs RB rush yds', choice['text'])
        self.assertEqual(choice['title'], 'MATCHUP TRENDS')
        self.assertEqual(receipts.guard({'text': choice['text']}), [])
        detail['favoriteLines'][0]['history']['last']['rate'] = 70
        choice = R.select({'games': [game()]}, {'CFB-1': detail}, NOW, teams=teams)
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
        choice = R.select({'games': [game()]}, {'CFB-1': {}}, NOW, [line])
        self.assertEqual(choice['kind'], 'spread-dog')
        self.assertIn('Underdog +8.5 (-105) ESPN', choice['text'])
        self.assertNotIn('not an upset', choice['text'].lower())
        self.assertIn('Underdog +8.5 (-105)', choice['text'])

        line['book'] = 'theScore Bet'
        choice = R.select({'games': [game()]}, {'CFB-1': {}}, NOW, [line])
        self.assertEqual(choice['kind'], 'spread-dog')
        self.assertIn('Underdog +8.5 (-105) ESPN', choice['text'])

    def test_post_window_and_card_are_stale_safe(self):
        watch = {'side': 'home', 'team': 'Underdog', 'odds': 160, 'opponentOdds': -192,
                 'book': 'DraftKings', 'observedAt': '2026-10-03T13:30:00Z',
                 'modelChance': .60, 'marketChanceNoVig': .369}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'games').mkdir()
            (root / 'today.json').write_text(__import__('json').dumps({'games': [game(watch)]}))
            (root / 'games' / 'CFB-1.json').write_text('{}')
            post = R.post({}, NOW, root / 'today.json', root / 'games')
            self.assertEqual((post['kind'], post['card']), ('research', 'research-upset-2026-10-03'))
            self.assertEqual(post['due'], datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc))
            choice = R.select({'games': [game(watch)]}, {'CFB-1': {}}, NOW)
            card = R.svg(choice)
            self.assertIn('UNDERDOG WATCH', card)
            self.assertIn('UNDERDOG RESEARCH', card)
            self.assertNotIn('NOT A PLAY', card)
            for ugly in ('#8b4513', '#a0522d', '#cd853f'):
                self.assertNotIn(ugly, card.lower())


if __name__ == '__main__':
    unittest.main()
