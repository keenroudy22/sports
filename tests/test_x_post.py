import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import x_post

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
GAME = {'id': 'CFB-1', 'league': 'CFB', 'kickoff': '2026-09-26T19:30Z', 'home': {'abbreviation': 'MICH'}, 'away': {'abbreviation': 'IOWA'}}
PICK = {'id': 'CFB-2026-W5-iowa-michigan-under-38-5-fd', 'title': 'Iowa at Michigan under 38.5', 'status': 'active',
        'favorite': True, 'marketType': 'total', 'line': 38.5, 'direction': 'under', 'gameIds': ['CFB-1'],
        'book': 'FanDuel', 'odds': -105, 'expiresAt': '2026-09-26T19:30:00Z', 'confidence': 6,
        'why': 'Researched pick. Michigan lists 4 starters out on offense, including the starting quarterback. '
               'Iowa has allowed 13 points a game over its last 3. Wind is forecast at 18 mph in Ann Arbor.',
        'sources': ['https://www.espn.com/college-football/game/_/gameId/1']}


class OAuthTests(unittest.TestCase):
    def test_signature_matches_the_documented_example(self):
        # The worked example from X's own OAuth 1.0a signing guide.
        creds = {'consumer_key': 'xvz1evFS4wEEPTGEFPHBog', 'consumer_secret': 'kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw',
                 'token': '370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb', 'token_secret': 'LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE'}
        header = x_post.oauth_header('POST', 'https://api.twitter.com/1.1/statuses/update.json', creds,
                                     {'include_entities': 'true', 'status': 'Hello Ladies + Gentlemen, a signed OAuth request!'},
                                     nonce='kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg', timestamp=1318622958)
        self.assertIn('oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"', header)
        self.assertTrue(header.startswith('OAuth '))

    def test_percent_encoding_is_rfc_3986(self):
        self.assertEqual(x_post.percent_encode('Ladies + Gentlemen'), 'Ladies%20%2B%20Gentlemen')
        self.assertEqual(x_post.percent_encode('~-._'), '~-._')

    def test_credentials_name_missing_keys_without_values(self):
        with self.assertRaises(x_post.MissingCredentials) as caught:
            x_post.credentials({'X_API_KEY': 'k', 'X_API_SECRET': 's'})
        self.assertIn('X_ACCESS_TOKEN', str(caught.exception))
        self.assertNotIn('k', str(caught.exception).split(':')[1].replace('X_ACCESS_TOKEN', '').replace('X_ACCESS_SECRET', ''))


class DraftTests(unittest.TestCase):
    def test_draft_is_short_has_no_dashes_and_uses_only_the_picks_numbers(self):
        text = x_post.draft(PICK, GAME)
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertIn('Iowa at Michigan under 38.5 (-105, FanDuel)', text)
        self.assertIn('https://keenroudy.com/sports/#pick/CFB-2026-W5-iowa-michigan-under-38-5-fd', text)
        self.assertNotIn('Researched pick.', text)
        self.assertEqual(x_post.guard(text, PICK), [], text)

    def test_url_counts_as_twenty_three(self):
        self.assertEqual(x_post.tweet_length('hi https://keenroudy.com/sports/#pick/a-very-long-identifier-indeed'), 3 + 23)

    def test_a_long_why_is_trimmed_to_fit(self):
        long = dict(PICK, why=' '.join(['A long reason that goes on for a while and says a great deal about nothing much at all.'] * 6))
        text = x_post.draft(long, GAME)
        self.assertLessEqual(x_post.tweet_length(text), 280)

    def test_opener_is_stable_per_pick(self):
        self.assertEqual(x_post.opener_for('a'), x_post.opener_for('a'))
        self.assertIn(x_post.opener_for('a'), x_post.OPENERS)


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.log = {'posts': [{'id': 'posted-before', 'textHash': x_post.text_hash('same words'), 'kind': 'pick'}]}

    def test_refusals(self):
        self.assertIsNone(x_post.refuse(PICK, GAME, self.log, NOW))
        for bad, why in ((dict(PICK, favorite=False), 'not a favorite'),
                         (dict(PICK, status='settled', result='win'), 'not open'),
                         (dict(PICK, entryNote='closed'), 'closed'),
                         (dict(PICK, expiresAt='2026-09-26T14:00:00Z'), 'expired'),
                         (dict(PICK, id='posted-before'), 'already posted')):
            with self.assertRaises(x_post.Refused, msg=why) as caught:
                x_post.refuse(bad, GAME, self.log, NOW)
            self.assertIn(why, str(caught.exception))
        with self.assertRaises(x_post.Refused):
            x_post.refuse(PICK, dict(GAME, kickoff='2026-09-26T14:00Z'), self.log, NOW)
        with self.assertRaises(x_post.Refused):
            x_post.refuse(PICK, GAME, self.log, NOW, text='same words')
        with self.assertRaises(x_post.Refused):
            x_post.refuse(PICK, None, self.log, NOW)


class PostTests(unittest.TestCase):
    def test_post_appends_the_log_through_a_fake_transport(self):
        creds = {'consumer_key': 'a', 'consumer_secret': 'b', 'token': 'c', 'token_secret': 'd'}
        sent = {}

        def send(url, body, headers):
            sent.update(url=url, body=body, auth=headers['Authorization'])
            return 201, json.dumps({'data': {'id': '12345', 'text': body['text']}}).encode()
        tweet_id = x_post.post_tweet('hello', creds, send)
        self.assertEqual(tweet_id, '12345')
        self.assertEqual(sent['url'], x_post.API)
        self.assertIn('oauth_signature=', sent['auth'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'x-posted.json'
            log = x_post.record(x_post.load_log(path), 'p1', 'hello', tweet_id, 'pick', NOW)
            x_post.save_log(log, path)
            again = x_post.load_log(path)
            self.assertEqual(again['posts'][0]['id'], 'p1')
            self.assertEqual(again['posts'][0]['tweetId'], '12345')
            self.assertEqual(again['posts'][0]['textHash'], x_post.text_hash('hello'))

    def test_duplicate_and_errors_are_refused(self):
        creds = {'consumer_key': 'a', 'consumer_secret': 'b', 'token': 'c', 'token_secret': 'd'}
        with self.assertRaises(x_post.Refused) as caught:
            x_post.post_tweet('x', creds, lambda *a: (403, b'{"detail":"You are not allowed to create a Tweet with duplicate content."}'))
        self.assertIn('duplicate', str(caught.exception))
        with self.assertRaises(x_post.Refused):
            x_post.post_tweet('x', creds, lambda *a: (401, b'Unauthorized'))

    def test_seeded_log_holds_the_two_hand_posts(self):
        log = x_post.load_log()
        self.assertEqual({p['id'] for p in log['posts']} & {'CFB-2026-W3-tamu-minus-16-5-vs-uk-dk', 'CFB-2026-W3-duke-minus-10-vs-stan-dk'},
                         {'CFB-2026-W3-tamu-minus-16-5-vs-uk-dk', 'CFB-2026-W3-duke-minus-10-vs-stan-dk'})


class RecapTests(unittest.TestCase):
    def test_units_mirror_core_js(self):
        self.assertEqual(x_post.units_for({'odds': -110, 'result': 'win'}), round(100 / 110, 3))
        self.assertEqual(x_post.units_for({'odds': -110, 'result': 'loss'}), -1)
        self.assertEqual(x_post.units_for({'odds': -110, 'result': 'loss', 'earlyExit': True}), 0.0)
        self.assertEqual(x_post.units_for({'odds': -110, 'result': 'push'}), 0.0)
        self.assertIsNone(x_post.units_for({'odds': -110, 'result': 'void'}), 'void carries no units')
        self.assertIsNone(x_post.units_for({'result': 'win'}), 'no price, no units')
        self.assertEqual(x_post.units_for({'odds': 500, 'result': 'win', 'riskUnits': 0.25}), 1.25)

    def test_recap_text(self):
        games = {'g1': {'kickoff': '2026-09-26T17:00Z'}, 'g2': {'kickoff': '2026-09-26T20:00Z'}, 'g3': {'kickoff': '2026-09-27T17:00Z'}}
        first = {'a': {'id': 'a', 'title': 'A over 40', 'favorite': True, 'odds': -110, 'gameIds': ['g1']},
                 'b': {'id': 'b', 'title': 'B under 50', 'modelLean': True, 'odds': -105, 'gameIds': ['g2']},
                 'c': {'id': 'c', 'title': 'C tomorrow', 'odds': -110, 'gameIds': ['g3']}}
        latest = {'a': {'result': 'win'}, 'b': {'result': 'loss'}, 'c': {'result': 'win'}}
        text = x_post.recap('2026-09-26', first, latest, games, NOW)
        self.assertIn('Favorites 1-0 (+0.91u)', text)
        self.assertIn('Everything on the record 1-1 (-0.09u)', text)
        self.assertIn('Hit: A over 40.', text)
        self.assertIn('Missed: B under 50.', text)
        self.assertNotIn('C tomorrow', text)
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertIsNone(x_post.recap('2026-09-28', first, latest, games, NOW))


if __name__ == '__main__':
    unittest.main()
