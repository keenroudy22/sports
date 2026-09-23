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


class PlanTests(unittest.TestCase):
    def test_plays_are_spaced_from_the_window_open_and_skip_the_ones_whose_window_passed(self):
        first = {'a': pick('a'), 'b': pick('b', 'late', title='Oklahoma at Georgia under 44.5', direction='under'),
                 'c': pick('c', 'tomorrow'), 'd': pick('d', 'noon', title='Iowa at Michigan under 38.5', direction='under')}
        latest = {k: dict(v) for k, v in first.items()}
        plans = bp.plan(first, latest, GAMES, NOW, {'posts': []})
        kinds = [(p[0], p[3].astimezone(bp.gates.EASTERN).strftime('%H:%M')) for p in plans]
        self.assertEqual(kinds, [('a', '09:00'), ('d', '09:08'), ('b', '09:16')], 'today only, kickoff order, eight minutes apart from 9:00')
        late_now = datetime(2026, 9, 26, 15, 30, tzinfo=timezone.utc)       # 11:30 AM ET: noon games are inside 45 minutes
        plans = bp.plan(first, latest, GAMES, late_now, {'posts': []})
        self.assertEqual([p[0] for p in plans], ['b'], 'the noon plays are too late; the evening one posts now')
        self.assertEqual(plans[0][3], late_now + bp.SOON)

    def test_posted_closed_and_settled_plays_are_left_out(self):
        first = {'a': pick('a'), 'b': pick('b', 'late'), 'c': pick('c', 'late', title='x')}
        latest = {'a': dict(first['a']), 'b': dict(first['b'], entryNote='closed'), 'c': dict(first['c'], result='win')}
        plans = bp.plan(first, latest, GAMES, NOW, {'posts': [{'id': 'a'}]})
        self.assertEqual(plans, [])

    def test_recap_and_scoreboard_get_their_mornings(self):
        yesterday = {'id': 'y', 'league': 'NFL', 'kickoff': '2026-09-25T00:15Z', 'home': {'short': 'A'}, 'away': {'short': 'B'}}
        games = dict(GAMES, y=yesterday)
        first = {'p': pick('p', 'y', publishedAt='2026-09-24T12:00:00Z')}
        latest = {'p': dict(first['p'], result='win', settledAt='2026-09-25T04:00:00Z')}
        scoreboard = {'live': [{'league': 'NFL', 'model': 'v2.0', 'season': 2026, 'summary': {'side': [8, 7, 0], 'ou': [6, 9, 0], 'closerTotal': [5, 10], 'games': 15, 'totalMiss': 10.7, 'closeTotalMiss': 10.23}}]}
        tuesday = datetime(2026, 9, 29, 12, 40, tzinfo=timezone.utc)      # Tuesday 8:40 ET
        plans = bp.plan(first, latest, games, tuesday, {'posts': []}, scoreboard)
        kinds = {p[1]: p[3].astimezone(bp.gates.EASTERN).strftime('%a %H:%M') for p in plans}
        self.assertEqual(kinds.get('scoreboard'), 'Tue 09:00')
        night = datetime(2026, 9, 25, 4, 30, tzinfo=timezone.utc)        # 12:30 AM ET Friday: Thursday night's game just settled
        plans = bp.plan(first, latest, games, night, {'posts': []})
        recap = next(p for p in plans if p[1] == 'recap')
        self.assertEqual(recap[0], 'recap:day:2026-09-24')
        self.assertEqual(recap[3].astimezone(bp.gates.EASTERN).strftime('%a %H:%M'), 'Fri 08:00', 'the recap waits for the morning')


class ScheduleTests(unittest.TestCase):
    def test_schedule_logs_each_post_and_attaches_the_card_only_when_it_is_deployed(self):
        fake = FakeBuffer()
        plans = [('a', 'play', 'text a', NOW + timedelta(hours=1), 'a'), ('b', 'play', 'text b', NOW + timedelta(hours=2), 'b')]
        log_book = bp.schedule(plans, 'ch-x', {'posts': []}, NOW, key='t', send=fake, opener=lambda url: url.endswith('/a.png'), log=lambda *_: None)
        self.assertEqual([p['id'] for p in log_book['posts']], ['a', 'b'])
        self.assertTrue(log_book['posts'][0]['card'])
        self.assertFalse(log_book['posts'][1]['card'])
        self.assertEqual(log_book['posts'][0]['kind'], 'buffer:play')
        inputs = [c['variables']['input'] for c in fake.calls if 'createPost' in c['query']]
        self.assertEqual(inputs[0]['assets'], [{'image': {'url': 'https://keenroudy.com/sports/data/cards/a.png'}}])
        self.assertEqual(inputs[1]['assets'], [], 'Buffer requires the list even when the post is text only')
        self.assertFalse(inputs[1]['needsApproval'])

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
