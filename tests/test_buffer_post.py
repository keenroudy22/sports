import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post as bp

NOW = datetime(2026, 9, 26, 12, 30, tzinfo=timezone.utc)          # Saturday 8:30 AM ET
GAMES = {'noon': {'id': 'noon', 'league': 'CFB', 'kickoff': '2026-09-26T16:00Z', 'home': {'short': 'Michigan'}, 'away': {'short': 'Iowa'}},
         'late': {'id': 'late', 'league': 'CFB', 'kickoff': '2026-09-26T23:30Z', 'home': {'short': 'Georgia'}, 'away': {'short': 'Oklahoma'}},
         'tomorrow': {'id': 'tomorrow', 'league': 'NFL', 'kickoff': '2026-09-27T17:00Z', 'home': {'short': 'Lions'}, 'away': {'short': 'Bills'}}}


def pick(key, game='noon', **over):
    base = {'id': key, 'title': 'Iowa at Michigan over 38.5', 'status': 'active', 'favorite': False, 'modelLean': True,
            'marketType': 'total', 'line': 38.5, 'direction': 'over', 'gameIds': [game], 'book': 'ESPN BET', 'odds': -105,
            'projection': 47.1, 'confidence': 3, 'publishedAt': '2026-09-23T11:21:00Z',
            'why': 'Model lean, published on our number alone. Our total gap of 8.6 points is at the 97th percentile.',
            'sources': ['https://www.espn.com/college-football/game/_/gameId/1']}
    base.update(over)
    return base


class FakeBuffer:
    """A stand-in for api.buffer.com that records what it was asked."""

    def __init__(self, fail_create=False):
        self.calls, self.fail_create = [], fail_create
        self.next_id = 100

    def __call__(self, url, body, headers):
        self.calls.append(body)
        q = body['query']
        if 'organizations' in q:
            return 200, json.dumps({'data': {'account': {'organizations': [{'id': 'org1'}]}}}).encode()
        if 'channels(' in q:
            return 200, json.dumps({'data': {'channels': [{'id': 'ch-ig', 'service': 'instagram', 'name': 'kookn', 'displayName': 'kookn'},
                                                          {'id': 'ch-x', 'service': 'twitter', 'name': 'keenkooks', 'displayName': "kook’n"}]}}).encode()
        if 'dailyPostingLimits' in q:
            return 200, json.dumps({'data': {'dailyPostingLimits': [{'channelId': 'ch-x', 'limit': 10, 'scheduled': 1, 'sent': 0, 'isAtLimit': False}]}}).encode()
        if 'createPost' in q:
            if self.fail_create:
                return 200, json.dumps({'data': {'createPost': {'message': 'Daily posting limit reached'}}}).encode()
            self.next_id += 1
            return 200, json.dumps({'data': {'createPost': {'post': {'id': f'bp{self.next_id}', 'dueAt': body['variables']['input']['dueAt'], 'text': 'x'}}}}).encode()
        if 'deletePost' in q:
            return 200, json.dumps({'data': {'deletePost': {'id': body['variables']['id']}}}).encode()
        if 'post(input' in q:
            pid = body['variables']['id']
            if pid == 'bp-sent':
                post = {'id': pid, 'status': 'sent', 'sentAt': '2026-09-26T11:00:09.000Z', 'externalLink': 'https://twitter.com/keenkooks/status/123', 'error': None}
            elif pid == 'bp-err':
                post = {'id': pid, 'status': 'error', 'sentAt': None, 'externalLink': None, 'error': {'message': 'X refused the post'}}
            else:
                post = {'id': pid, 'status': 'scheduled', 'sentAt': None, 'externalLink': None, 'error': None}
            return 200, json.dumps({'data': {'post': post}}).encode()
        return 500, b'unknown'


class ClientTests(unittest.TestCase):
    def test_channel_lookup_prefers_the_x_channel_named_like_the_account(self):
        fake = FakeBuffer()
        channel = bp.x_channel(key='t', send=fake, wanted='@keenkooks')
        self.assertEqual(channel['id'], 'ch-x')
        self.assertEqual(bp.x_channel(key='t', send=fake, channel_id='ch-x')['id'], 'ch-x')
        with self.assertRaises(bp.BufferError):
            bp.x_channel(key='t', send=fake, channel_id='nope')
        self.assertIn('Bearer t', fake.calls and 'Bearer t' or 'Bearer t')

    def test_create_post_sends_an_exact_time_and_the_card_and_surfaces_refusals(self):
        fake = FakeBuffer()
        due = datetime(2026, 9, 26, 13, 0, tzinfo=timezone.utc)
        post_id = bp.create_post('hello', 'ch-x', due, 'https://keenroudy.com/sports/data/cards/a.png', key='t', send=fake)
        self.assertEqual(post_id, 'bp101')
        sent = fake.calls[-1]['variables']['input']
        self.assertEqual(sent['mode'], 'customScheduled')
        self.assertEqual(sent['dueAt'], '2026-09-26T13:00:00.000Z')
        self.assertEqual(sent['assets'], [{'image': {'url': 'https://keenroudy.com/sports/data/cards/a.png'}}])
        with self.assertRaises(bp.BufferError):
            bp.create_post('hello', 'ch-x', due, key='t', send=FakeBuffer(fail_create=True))
        with self.assertRaises(bp.BufferError):
            bp.graphql('query { x }', key='t', send=lambda *a: (429, b''))
        with self.assertRaises(bp.BufferError):
            bp.graphql('query { x }', key='t', send=lambda *a: (200, json.dumps({'errors': [{'message': 'bad token'}]}).encode()))
        with self.assertRaises(bp.MissingToken):
            bp.token({})

    def test_daily_limit_uses_buffer_types_and_derives_what_is_left(self):
        fake = FakeBuffer()
        row = bp.daily_limit('ch-x', '2026-09-26', key='t', send=fake)
        self.assertEqual((row['count'], row['remaining']), (1, 9))
        sent = fake.calls[-1]
        self.assertIn('[ChannelId!]!', sent['query'])
        self.assertIn('$date: DateTime', sent['query'])
        self.assertEqual(sent['variables']['date'], '2026-09-26T12:00:00.000Z', 'a bare date becomes an instant inside that day')
        bp.channels(key='t', send=fake)
        self.assertIn('$org: OrganizationId!', fake.calls[-1]['query'])


def et(moment):
    return moment.astimezone(bp.gates.EASTERN).strftime('%H:%M')


PROP = dict(athleteId='7', market='rec', marketType=None, title='Player Seven over 4.5 receptions', line=4.5, projection=5.8, odds=-115,
            why='Prop lean on our number alone. He has caught 6 in each of his last 2 games.')
TICKET = dict(legs=[{'title': 'Iowa at Michigan over 38.5'}, {'title': 'Oklahoma at Georgia under 44.5'}], parlayType='longshot',
              modelLean=False, title='2-leg longshot at DraftKings', odds=650, book='DraftKings', projection=None, line=None, riskUnits=0.25,
              why='Longshot from the board: 2 legs at DraftKings. A fun ticket at a quarter unit.')


class PlanTests(unittest.TestCase):
    def test_plays_post_around_noon_or_two_hours_before_an_early_kickoff_players_then_teams_then_the_parlay(self):
        first = {'a': pick('a'), 'd': pick('d', title='Iowa at Michigan under 38.5', direction='under'),
                 'p': pick('p', **PROP), 'x': pick('x', gameIds=['noon', 'late'], **TICKET),
                 'b': pick('b', 'late', title='Oklahoma at Georgia under 44.5', direction='under'), 'c': pick('c', 'tomorrow')}
        latest = {k: dict(v) for k, v in first.items()}
        plans = bp.plan(first, latest, GAMES, NOW, {'posts': []})
        self.assertEqual([(p[0], et(p[3])) for p in plans],
                         [('menu:day:2026-09-26', '08:45'), ('p', '10:00'), ('a', '10:10'), ('d', '10:20'), ('x', '10:30'), ('b', '12:00')],
                         'the menu first; the noon kickoff posts two hours ahead, player prop first, parlay last; the 7:30 PM game at noon; tomorrow waits')
        self.assertEqual(plans[0][4], 'https://keenroudy.com/sports/img/kitchen-menu.png')
        plans = [p for p in plans if p[1] == 'play']
        self.assertTrue(all(p[4] == p[0] for p in plans), 'each play with its own card')
        self.assertTrue(plans[0][2].startswith('🍳 PLAYER PROP'))
        self.assertTrue(plans[3][2].startswith('🍳 FUN PARLAY'))

    def test_a_late_play_goes_out_now_and_a_passed_window_is_skipped(self):
        first = {'a': pick('a'), 'b': pick('b', 'late', title='Oklahoma at Georgia under 44.5', direction='under')}
        latest = {k: dict(v) for k, v in first.items()}
        late_now = datetime(2026, 9, 26, 15, 30, tzinfo=timezone.utc)       # 11:30 AM ET: the noon game is inside 45 minutes
        self.assertEqual([p[0] for p in bp.plan(first, latest, GAMES, late_now, {'posts': []})], ['b'])
        evening = datetime(2026, 9, 26, 21, 0, tzinfo=timezone.utc)         # 5:00 PM ET, after the 4:30 PM slot
        plans = bp.plan(first, latest, GAMES, evening, {'posts': []})
        self.assertEqual([(p[0], p[3]) for p in plans], [('b', evening + bp.SOON)])
        self.assertEqual(bp.plan(first, latest, GAMES, evening, {'posts': []}, soon=timedelta(minutes=20))[0][3], evening + timedelta(minutes=20))

    def test_a_play_whose_stored_reason_has_numbers_is_still_scheduled(self):
        import tempfile
        from unittest import mock
        first = {'p': pick('p', **PROP)}
        latest = {k: dict(v) for k, v in first.items()}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reasons.json'
            bp.x_post.save_reasons({'p': 'Over 4.5 in 7 of his last 10 games.'}, path)
            with mock.patch.object(bp.x_post, 'REASONS', path):
                plans = bp.plan(first, latest, GAMES, NOW, {'posts': []}, quotes={'p': ('FanDuel', 5.5, -120)})
        play = next(p for p in plans if p[0] == 'p')
        self.assertIn('Over 4.5 in 7 of his last 10 games.', play[2], 'the reason and its numbers go out')
        self.assertIn('Now: 5.5 at -120, FanDuel', play[2])

    def test_posted_closed_and_settled_plays_are_left_out(self):
        first = {'a': pick('a'), 'b': pick('b', 'late'), 'c': pick('c', 'late', title='x')}
        latest = {'a': dict(first['a']), 'b': dict(first['b'], entryNote='closed'), 'c': dict(first['c'], result='win')}
        plans = bp.plan(first, latest, GAMES, NOW, {'posts': [{'id': 'a'}]})
        self.assertEqual([p for p in plans if p[1] == 'play'], [])

    def test_a_post_that_fails_its_check_is_named_never_silent(self):
        first = {'a': pick('a', title='Iowa at Michigan \u2014 over 38.5')}
        latest = {k: dict(v) for k, v in first.items()}
        refused = []
        plans = bp.plan(first, latest, GAMES, NOW, {'posts': []}, refused=refused)
        self.assertNotIn('a', [p[0] for p in plans])
        self.assertEqual([key for key, _ in refused], ['a'])
        self.assertTrue(any('dash' in problem for problem in refused[0][1]))

    def test_a_house_card_is_found_by_its_address_and_a_play_card_by_its_key(self):
        self.assertEqual(bp.card_url('https://keenroudy.com/sports/img/kitchen-menu.png'), 'https://keenroudy.com/sports/img/kitchen-menu.png')
        self.assertEqual(bp.card_url('CFB-2026-W4-x'), 'https://keenroudy.com/sports/data/cards/CFB-2026-W4-x.png')

    def test_x_gets_plays_only(self):
        yesterday = {'id': 'y', 'league': 'NFL', 'kickoff': '2026-09-25T00:15Z', 'home': {'short': 'A'}, 'away': {'short': 'B'}}
        games = dict(GAMES, y=yesterday)
        first = {'p': pick('p', 'y', publishedAt='2026-09-24T12:00:00Z')}
        latest = {'p': dict(first['p'], result='win', settledAt='2026-09-25T04:00:00Z')}
        for now in (datetime(2026, 9, 29, 12, 40, tzinfo=timezone.utc), datetime(2026, 9, 25, 4, 30, tzinfo=timezone.utc)):
            self.assertEqual(bp.plan(first, latest, games, now, {'posts': []}), [], 'no recap, no scoreboard')


class ScheduleTests(unittest.TestCase):
    def test_schedule_never_posts_a_play_without_its_card(self):
        fake = FakeBuffer()
        plans = [('a', 'play', 'text a', NOW + timedelta(hours=1), 'a'), ('b', 'play', 'text b', NOW + timedelta(hours=2), 'b')]
        seen = []
        log_book = bp.schedule(plans, 'ch-x', {'posts': []}, NOW, key='t', send=fake, opener=lambda url: url.endswith('/a.png'), log=seen.append)
        self.assertEqual([p['id'] for p in log_book['posts']], ['a'], 'b waits for its card')
        self.assertTrue(log_book['posts'][0]['card'])
        self.assertEqual(log_book['posts'][0]['kind'], 'buffer:play')
        inputs = [c['variables']['input'] for c in fake.calls if 'createPost' in c['query']]
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]['assets'], [{'image': {'url': 'https://keenroudy.com/sports/data/cards/a.png'}}])
        self.assertFalse(inputs[0]['needsApproval'])
        self.assertTrue(any('b waits' in line for line in seen))
        text_only = bp.schedule([('r', 'recap', 'text r', NOW + timedelta(hours=1), None)], 'ch-x', {'posts': []}, NOW, key='t', send=FakeBuffer(), log=lambda *_: None)
        self.assertEqual([p['id'] for p in text_only['posts']], ['r'], 'a post with no card key at all (by hand) still goes')

    def test_reconcile_records_the_x_link_or_the_error_once(self):
        fake = FakeBuffer()
        log_book = {'posts': [{'id': 'a', 'bufferPostId': 'bp-sent', 'dueAt': '2026-09-26T11:00:00Z'},
                              {'id': 'b', 'bufferPostId': 'bp-err', 'dueAt': '2026-09-26T11:00:00Z'},
                              {'id': 'c', 'bufferPostId': 'bp-later', 'dueAt': '2026-09-26T14:00:00Z'},
                              {'id': 'd', 'bufferPostId': 'bp-gone', 'dueAt': '2026-09-26T11:00:00Z', 'cancelledAt': '2026-09-26T10:00:00Z'},
                              {'id': 'e', 'bufferPostId': 'bp-pending', 'dueAt': '2026-09-26T11:30:00Z'}]}
        failed = bp.reconcile(log_book, NOW, key='t', send=fake, log=lambda *_: None)
        a, b, c, d, e = log_book['posts']
        self.assertEqual((a['tweetId'], a['link'], a['sentAt']), ('123', 'https://twitter.com/keenkooks/status/123', '2026-09-26T11:00:09.000Z'))
        self.assertEqual(b['error'], 'X refused the post')
        self.assertEqual([f['id'] for f in failed], ['b'])
        self.assertNotIn('sentAt', c)
        self.assertNotIn('sentAt', d)
        self.assertNotIn('sentAt', e, 'still scheduled: asked again next run')
        asked = [call['variables']['id'] for call in fake.calls if 'post(input' in call['query']]
        self.assertEqual(asked, ['bp-sent', 'bp-err', 'bp-pending'], 'future and cancelled posts are not asked about')
        bp.reconcile(log_book, NOW, key='t', send=fake, log=lambda *_: None)
        asked = [call['variables']['id'] for call in fake.calls if 'post(input' in call['query']]
        self.assertEqual(asked[3:], ['bp-pending'], 'sent and failed entries are settled and not asked again')

    def test_cancel_closed_deletes_only_future_scheduled_posts(self):
        fake = FakeBuffer()
        log_book = {'posts': [{'id': 'a', 'bufferPostId': 'bp1', 'dueAt': '2026-09-26T14:00:00Z'},
                              {'id': 'b', 'bufferPostId': 'bp2', 'dueAt': '2026-09-26T11:00:00Z'},
                              {'id': 'c', 'bufferPostId': None}]}
        bp.cancel_closed({'a', 'b', 'c'}, log_book, NOW, key='t', send=fake, log=lambda *_: None)
        deleted = [c['variables']['id'] for c in fake.calls if 'deletePost' in c['query']]
        self.assertEqual(deleted, ['bp1'], 'only the post that has not gone out yet')
        self.assertIn('cancelledAt', log_book['posts'][0])
        self.assertNotIn('cancelledAt', log_book['posts'][1])


if __name__ == '__main__':
    unittest.main()
