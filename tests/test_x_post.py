import json
import sys
import tempfile
import unittest
from unittest import mock
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


PROP = {'id': 'NFL-2026-W4-p7-over-4-5-rec-dk', 'title': 'Player Seven over 4.5 receptions', 'status': 'active', 'favorite': False,
        'modelLean': True, 'athleteId': '7', 'market': 'rec', 'line': 4.5, 'direction': 'over', 'gameIds': ['CFB-1'],
        'book': 'DraftKings', 'odds': -115, 'projection': 5.8, 'confidence': 3,
        'why': 'Prop lean on our number alone: the over reads 64.1% on the raw curve. He has caught 6 in each of his last 2 games.'}


class DraftTests(unittest.TestCase):
    def test_every_post_has_the_same_shape(self):
        team = x_post.draft(dict(PICK, favorite=False, modelLean=True, projection=31.2), GAME)
        self.assertTrue(team.startswith('🍳 TEAM PROP\nIowa at Michigan under 38.5\n-105 at FanDuel · 1 unit\n\nOur number 31.2 vs the 38.5\n'), team)
        self.assertTrue(team.endswith('\n\n@Playbook #CFB'), team)
        prop = x_post.draft(PROP, {'league': 'NFL'}, reason='He has caught 6 in each of his last 2 games.')
        self.assertEqual(prop, '🍳 PLAYER PROP\nPlayer Seven over 4.5 receptions\n-115 at DraftKings · 1 unit\n\n'
                               'Our number 5.8 vs the 4.5\nHe has caught 6 in each of his last 2 games.\n\n@Playbook #NFL')
        favorite = x_post.draft(PICK, GAME)
        self.assertTrue(favorite.startswith('🍳 TEAM PROP · FAVORITE\n'), favorite)
        for text, pick in ((team, dict(PICK, projection=31.2)), (prop, PROP), (favorite, PICK)):
            self.assertLessEqual(x_post.tweet_length(text), 280)
            self.assertNotIn('http', text, 'no link: the card carries the site')
            self.assertEqual(x_post.guard(text, pick, 'He has caught 6 in each of his last 2 games.' if pick is PROP else None), [], text)

    def test_the_reason_is_the_stored_one_never_the_prose(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reasons.json'
            x_post.save_reasons({PICK['id']: 'Wind is forecast at 18 mph in Ann Arbor.'}, path)
            with mock.patch.object(x_post, 'REASONS', path):
                self.assertIn('Our number 31.2 vs the 38.5\nWind is forecast at 18 mph in Ann Arbor.', x_post.draft(dict(PICK, projection=31.2), GAME))
                other = dict(PICK, id='another', projection=31.2)
                self.assertTrue(x_post.draft(other, GAME).endswith('Our number 31.2 vs the 38.5\n\n@Playbook #CFB'),
                                'no stored reason: the prose is not mined, the post stands on the number')

    def test_lineup_checks_duplicates_and_half_sentences_are_not_reasons(self):
        pick = {'why': 'Model lean, published on our number alone. Our total is 52.3 against 45.5: the over reads 55.8%. '
                       'Checked before publishing: JMU quarterback JC Evans suffered a lower-body injury against Liberty. '
                       'He completed 19 of 27 passes for 246 yards against San Diego State.'}
        self.assertIsNone(x_post.reason_for(pick), 'a model lean with nothing but checks and arithmetic posts on its number')

    def test_arithmetic_words_match_whole_words_only(self):
        self.assertTrue(x_post.plain('The tight end has drawn 7 targets in each of his last 2 games.'))
        self.assertTrue(x_post.plain('Crawford has started every game this season.'))
        self.assertFalse(x_post.plain('The raw read is 61%.'))
        self.assertFalse(x_post.plain('The calibrated chance clears the price.'))

    def test_names_keep_their_suffix_and_a_clean_clause_can_stand_alone(self):
        pick = {'why': 'Prop lean, published on our number alone: our projection is 6.0 against 3.5, so the true chance is lower than that. '
                       'Denver is without WR Marvin Mims Jr. on the inactive list, which sends targets to its first receiver. '
                       'The role is settled by last season, not by this season\'s one game. '
                       'Our number is 16.3 yards against a 32.5 line, and the Rams\' tight end room splits targets with Colby Parkinson.'}
        self.assertIn('Denver is without WR Marvin Mims Jr. on the inactive list, which sends targets to its first receiver.', x_post.sentences(pick['why']))
        denver = {'why': pick['why'].split('Our number is 16.3')[0]}
        self.assertEqual(x_post.reason_for(denver), 'Denver is without WR Marvin Mims Jr. on the inactive list, which sends targets to its first receiver.')
        rams = {'why': pick['why'].split('Denver')[0] + "Our number is 16.3 yards against a 32.5 line, and the Rams' tight end room splits targets with Colby Parkinson."}
        self.assertEqual(x_post.reason_for(rams), "The Rams' tight end room splits targets with Colby Parkinson.")
        self.assertIsNone(x_post.reason_for({'why': 'Duke is 2-0 on the year and v2 has the home margin at 19.1 against a 10-point line.'}),
                          'a model name keeps a sentence off X')
        self.assertIsNone(x_post.reason_for({'why': 'Our number likes the over here, and is the kind that held up yesterday.'}), 'no half sentences')

    def test_the_reason_is_one_plain_sentence_or_none(self):
        self.assertEqual(x_post.reason_for(PICK), 'Wind is forecast at 18 mph in Ann Arbor.', 'the most specific short sentence')
        arithmetic = dict(PICK, why='Model lean, published on our number alone. The over reads 55.3% after the raw 62.7% is shrunk. '
                                    'Our total gap of 7.8 points is at the 95th percentile.')
        self.assertIsNone(x_post.reason_for(arithmetic), 'no stat talk in the timeline')
        text = x_post.draft(dict(arithmetic, projection=31.2), GAME)
        self.assertNotIn('percentile', text)
        self.assertIn('Our number 31.2 vs the 38.5\n\n@Playbook #CFB', text)

    def test_url_counts_as_twenty_three(self):
        self.assertEqual(x_post.tweet_length('hi https://keenroudy.com/sports/#pick/a-very-long-identifier-indeed'), 3 + 23)

    def test_a_long_why_is_trimmed_to_fit(self):
        long = dict(PICK, why=' '.join(['A long reason that goes on for a while and says a great deal about nothing much at all.'] * 6))
        text = x_post.draft(long, GAME)
        self.assertLessEqual(x_post.tweet_length(text), 280)


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.log = {'posts': [{'id': 'posted-before', 'textHash': x_post.text_hash('same words'), 'kind': 'pick'}]}

    def test_refusals(self):
        self.assertIsNone(x_post.refuse(PICK, GAME, self.log, NOW))
        self.assertIsNone(x_post.refuse(dict(PICK, favorite=False, legs=[{'title': 'A'}], parlayType='longshot'), GAME, self.log, NOW), 'the longshot may post')
        for bad, why in ((dict(PICK, favorite=False, modelLean=False), 'only favorites, model leans, prop leans and the longshot'),
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


class ScoreboardPostTests(unittest.TestCase):
    def test_the_weekly_post_reads_only_the_scoreboard(self):
        scoreboard = {'live': [
            {'league': 'CFB', 'model': 'v2.0', 'season': 2026, 'summary': {'side': [36, 34, 1], 'ou': [41, 30, 0], 'closerTotal': [40, 31], 'games': 71, 'totalMiss': 13.01, 'closeTotalMiss': 13.25}},
            {'league': 'NFL', 'model': 'v2.0', 'season': 2026, 'summary': {'side': [8, 7, 0], 'ou': [6, 9, 0], 'closerTotal': [5, 10], 'games': 15, 'totalMiss': 10.7, 'closeTotalMiss': 10.23}},
            {'league': 'NFL', 'model': 'v1', 'season': 2026, 'summary': {'side': [1, 1, 0], 'ou': [1, 1, 0], 'closerTotal': [1, 1], 'totalMiss': 1, 'closeTotalMiss': 1}}]}
        text = x_post.scoreboard_text(scoreboard)
        self.assertIn('College: sides 36-34-1, totals 41-30.', text)
        self.assertIn('NFL: sides 8-7, totals 6-9.', text)
        self.assertIn('5 of 15 totals', text)
        self.assertLessEqual(x_post.tweet_length(text), 280)
        import llm
        self.assertEqual(llm.check_style(text.replace(x_post.SITE, '')), [])
        self.assertTrue(llm.numbers_ok(text, scoreboard)[0])
        self.assertIsNone(x_post.scoreboard_text({'live': []}))


class MediaTests(unittest.TestCase):
    CREDS = {'consumer_key': 'a', 'consumer_secret': 'b', 'token': 'c', 'token_secret': 'd'}

    def test_v2_chunked_upload_in_three_calls(self):
        calls = []

        def send_raw(url, body, headers):
            calls.append((url, headers.get('Content-Type', '').split(';')[0], len(body)))
            self.assertIn('oauth_signature=', headers['Authorization'])
            if url.endswith('/initialize'):
                return 202, json.dumps({'data': {'id': '777'}}).encode()
            if url.endswith('/append'):
                return 204, b''
            return 201, json.dumps({'data': {'id': '777', 'processing_info': None}}).encode()
        self.assertEqual(x_post.upload_media(b'\x89PNG' + b'0' * 100, self.CREDS, send_raw), '777')
        self.assertEqual([c[0].rsplit('/', 1)[-1] for c in calls], ['initialize', 'append', 'finalize'])
        self.assertEqual(calls[1][1], 'multipart/form-data')

    def test_falls_back_to_v1_when_v2_refuses_and_gives_up_when_both_do(self):
        def send_raw(url, body, headers):
            if 'api.x.com' in url:
                return 403, b'{"detail":"no"}'
            return 200, json.dumps({'media_id_string': '888'}).encode()
        self.assertEqual(x_post.upload_media(b'png', self.CREDS, send_raw), '888')
        with self.assertRaises(x_post.Refused):
            x_post.upload_media(b'png', self.CREDS, lambda *a: (403, b'no'))

    def test_a_post_can_carry_media_ids(self):
        sent = {}

        def send(url, body, headers):
            sent.update(body)
            return 201, json.dumps({'data': {'id': '1'}}).encode()
        x_post.post_tweet('hello', self.CREDS, send, media_ids=['777'])
        self.assertEqual(sent['media'], {'media_ids': ['777']})

    def test_multipart_body_is_well_formed(self):
        content_type, body = x_post.multipart({'segment_index': '0'}, {'media': ('card.png', b'PNGDATA', 'image/png')})
        boundary = content_type.split('boundary=')[1]
        self.assertTrue(body.startswith(f'--{boundary}\r\n'.encode()))
        self.assertIn(b'name="segment_index"\r\n\r\n0\r\n', body)
        self.assertIn(b'filename="card.png"\r\nContent-Type: image/png\r\n\r\nPNGDATA\r\n', body)
        self.assertTrue(body.endswith(f'--{boundary}--\r\n'.encode()))


class ReasonTests(unittest.TestCase):
    def test_reasons_put_specific_sentences_first_and_drop_lead_ins(self):
        pick = {'why': 'Model lean, published on our number alone. Nothing sourced argues against it; the number is the reason. '
                       'The market: The total opened 50.5 and is 44.5 at DraftKings, 6 toward the under. '
                       'Our total gap of 7.8 points is at the 95th percentile; gaps this large went 112-58 against the close in 3602 graded games.'}
        reasons = x_post.reasons_for(pick)
        self.assertEqual(reasons[0], 'The total opened 50.5 and is 44.5 at DraftKings, 6 toward the under.', 'the move, its lead-in cut off')
        self.assertTrue(reasons[1].startswith('Our total gap of 7.8 points'), reasons)
        self.assertIsNone(x_post.reason_for(pick), "the line's move is the price's story, not a reason, and the percentile is arithmetic")
        self.assertFalse(any(r.lower().startswith(('model lean', 'nothing sourced', 'the market:')) for r in reasons))

    def test_a_longshot_draft_lists_its_legs(self):
        ticket = {'id': 'NFL-2026-W4-longshot-0927-dk', 'title': '3-leg longshot at DraftKings', 'legs': [{'title': 'Bills at Lions over 44.5'}, {'title': 'Jets +3'}, {'title': 'Player Seven over 4.5 receptions'}],
                  'parlayType': 'longshot', 'riskUnits': 0.25, 'book': 'DraftKings', 'odds': 650,
                  'why': 'Longshot from the board: 3 legs at DraftKings, each at the number our model graded, one per game. A fun ticket at a quarter unit, tracked apart from the straight picks.'}
        text = x_post.draft(ticket, {'league': 'NFL'})
        self.assertEqual(text, '🍳 FUN PARLAY\n3 legs · +650 at DraftKings · ¼ unit\n• Bills at Lions over 44.5\n• Jets +3\n• Player Seven over 4.5 receptions'
                               '\n\nJust for fun.\n\n@Playbook #NFL')
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertEqual(x_post.guard(text, ticket), [], text)
