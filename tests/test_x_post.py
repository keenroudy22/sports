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
        'probabilityAtPublication': {'chance': .56, 'breakEven': .535, 'calibrated': True},
        'why': 'Prop lean on our number alone: the over reads 64.1% on the raw curve. He has caught 6 in each of his last 2 games.'}


class DraftTests(unittest.TestCase):
    def test_night_football_caption_names_the_window(self):
        saturday = dict(GAME, kickoff='2026-10-11T00:15:00Z')
        self.assertTrue(x_post.draft(PICK, saturday).startswith('Saturday night: '))
        sunday = dict(GAME, league='NFL', kickoff='2026-10-12T00:20:00Z')
        self.assertNotIn('SNF:', x_post.draft(dict(PICK, id='NFL-night'), sunday))
        thursday = dict(GAME, league='NFL', kickoff='2026-10-09T00:15:00Z')
        hot = x_post.draft(dict(PICK, id='NFL-hot', projection=31.2), thursday, featured=True,
                           reason='Over 38.5 in 4 of his last 5 games.')
        self.assertTrue(hot.startswith('🍳 Hot Plate (POTD): '), hot)
        self.assertIn("Book says 38.5. I have it at 31, so I'm on the under.", hot)
        self.assertIn('Over 38.5 in 4 of his last 5 games.', hot)
        self.assertTrue(any(hot.endswith(f'{ask}\n@Playbook #NFL') for ask in
                            ("❤️ if you're tailing", "❤️ if you're on it", "❤️ if you're riding with me")))

    def test_every_post_is_the_play_the_price_and_our_number_in_a_few_words(self):
        with mock.patch.object(x_post, 'load_reasons', return_value={}):
            team = x_post.draft(dict(PICK, favorite=False, modelLean=True, projection=31.2), GAME)
        self.assertIn("Iowa/Michigan under 38.5 (-105, FanDuel)", team)
        self.assertIn("Book says 38.5. I have it at 31, so I'm on the under.", team)
        self.assertTrue(team.endswith('@Playbook #CFB'))
        prop = x_post.draft(PROP, {'league': 'NFL'}, reason='He has caught 6 in each of his last 2 games.')
        self.assertIn('Player Seven over 4.5 catches (-115, DraftKings)', prop)
        self.assertIn("Book says 4.5. I have it at 5.8, so I'm on the over.", prop)
        self.assertIn('He has caught 6 in each of his last 2 games.', prop)
        self.assertTrue(x_post.reason_in(prop).endswith('He has caught 6 in each of his last 2 games.'))
        with mock.patch.object(x_post, 'load_reasons', return_value={}):
            potd = x_post.draft(PICK, GAME, featured=True)
        self.assertTrue(potd.startswith('🍳 Hot Plate (POTD): Iowa/Michigan under 38.5 (-105, FanDuel)\n'), potd)
        for text, pick in ((team, dict(PICK, projection=31.2)), (prop, PROP), (potd, PICK)):
            self.assertLessEqual(x_post.tweet_length(text), 280)
            self.assertNotIn('http', text, 'no link: the card carries the site')
            self.assertEqual('🍳' in text, text == potd)
            self.assertEqual(x_post.guard(text, pick), [], text)

    def test_tweets_spell_out_player_and_team_names_for_search(self):
        game = {'league': 'NFL', 'kickoff': '2026-10-19T00:20:00Z',
                'away': {'name': 'Detroit Lions', 'short': 'Lions'},
                'home': {'name': 'Buffalo Bills', 'short': 'Bills'}}
        prop = dict(PROP, gameIds=['NFL-1'])
        text = x_post.draft(prop, game, reason='He cleared this line in 7 of his last 10 games.')
        self.assertIn('Player Seven over 4.5 catches · Detroit Lions at Buffalo Bills', text)
        total = x_post.draft(dict(PICK, id='NFL-total', projection=42.0), game, reason='Wind is forecast at 18 mph.')
        self.assertIn('Detroit Lions at Buffalo Bills under 38.5', total)

    def test_a_side_says_who_we_have_by_how_much(self):
        side = dict(PICK, marketType='spread', direction='home', line=-3.0, title='Iowa at Michigan -3', projection=-7.4)
        game = dict(GAME, home={'abbreviation': 'MICH', 'school': 'Michigan'}, away={'abbreviation': 'IOWA', 'school': 'Iowa'})
        text = x_post.draft(side, game)
        self.assertIn("Book says -3. I have it at -7.4, so I'm on this side.", text)
        self.assertEqual(x_post.guard(text, side), [])
        opposite = x_post.draft(dict(side, projection=2.6), game)
        self.assertIn("Book says -3. I have it at 2.6, so I'm on this side.", opposite,
                      'the number plainly shows when our side crosses zero')

    def test_moneyline_never_prints_zero_as_a_book_line_or_a_dangling_reason(self):
        game = {'league': 'NFL', 'kickoff': '2026-10-19T00:20:00Z',
                'away': {'name': 'Dallas Cowboys', 'short': 'Cowboys'},
                'home': {'name': 'Green Bay Packers', 'short': 'Packers'}}
        pick = dict(PICK, id='NFL-2026-W6-dal-gb-ml-home-0-dk', lane='gut_call',
                    title='Packers MONEYLINE', marketType='moneyline', direction='home', line=0,
                    odds=-112, book='DraftKings', projection=.60,
                    probabilityAtPublication={'chance': .55, 'breakEven': .528, 'calibrated': True},
                    reasons=['Dallas is without its starting left tackle.'])
        text = x_post.draft(pick, game, reason='has been ruled out.')
        self.assertIn('packers moneyline', text.lower())
        self.assertIn('Dallas is without its starting left tackle.', text)
        self.assertNotIn('Book says 0', text)
        self.assertNotIn('has been ruled out.', text)
        self.assertEqual(x_post.guard(text, pick, x_post.reason_in(text)), [])

    def test_short_reason_keeps_a_complete_injury_sentence_instead_of_a_noun_fragment(self):
        reason = 'Cowboys cornerback Cobie Durant and tackle Drew Shelton are out with hamstring injuries.'
        self.assertEqual(x_post._short_reason(reason), reason)

    def test_the_post_shows_the_number_available_now_when_it_moved(self):
        pick = dict(PICK, favorite=False, modelLean=True, projection=31.2)
        moved = x_post.draft(pick, GAME, reason='', now_quote=('DraftKings', 37.5, -110))
        self.assertIn('(-105, FanDuel)\nNow 37.5 (-110, DraftKings)\n', moved)
        self.assertEqual(x_post.guard(moved, pick, None, ('DraftKings', 37.5, -110)), [])
        same = x_post.draft(pick, GAME, reason='', now_quote=('FanDuel', 38.5, -105))
        self.assertNotIn('Now', same, 'unchanged: nothing to add')
        spread = x_post.draft(dict(pick, marketType='spread', direction='home', line=-3.0, title='Iowa at Michigan -3'), GAME,
                              reason='', now_quote=('DraftKings', -3.5, -110))
        self.assertIn('Now -3.5 (-110, DraftKings)', spread)

    def test_a_stored_supporting_reason_reaches_the_post(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reasons.json'
            x_post.save_reasons({PICK['id']: 'Wind is forecast at 18 mph in Ann Arbor.'}, path)
            with mock.patch.object(x_post, 'REASONS', path):
                self.assertIn('Wind is forecast at 18 mph in Ann Arbor.', x_post.draft(dict(PICK, projection=31.2), GAME))

    def test_model_number_is_not_repeated_as_the_supporting_reason(self):
        pick = dict(PROP, lane='gut_call', dossier={'reasons': [
            {'text': 'Book says 4.5. I say 5.8.'},
            {'text': 'He cleared this line in 4 of his last 5 full games.'},
        ]})
        text = x_post.draft(pick, {'league': 'NFL'}, reason='Book says 4.5. I say 5.8.')
        self.assertEqual(text.count('Book says '), 1)
        self.assertIn('He cleared this line in 4 of his last 5 full games.', text)
        self.assertEqual(x_post.guard(text, pick, x_post.reason_in(text)), [])

    def test_kittle_release_keeps_a_complete_verified_clause_and_numeric_team_identity(self):
        game = {'league': 'NFL', 'home': {'name': 'San Francisco 49ers'}, 'away': {'name': 'Washington Commanders'}}
        fact = ('Deebo Samuel Sr. is out with a hamstring injury, while Mike Evans is questionable with rib '
                'and Achilles injuries and Christian Kirk is questionable with a calf injury.')
        pick = dict(PROP, title='George Kittle over 5.5 receptions', line=5.5, projection=6.3, odds=102,
                    book='FanDuel', lane='gut_call', matchup='Washington Commanders at San Francisco 49ers',
                    dossier={'reasons': [{'text': 'Book says 5.5. I say 6.3.'}, {'text': fact}]},
                    probabilityAtPublication={'chance': .511, 'breakEven': .495})
        with mock.patch.object(x_post, 'load_log', return_value={'posts': []}):
            text = x_post.draft(pick, game, reason='Book says 5.5. I say 6.3.')
        self.assertIn('San Francisco 49ers', text)
        self.assertIn('Deebo Samuel Sr. is out with a hamstring injury.', text)
        self.assertEqual(x_post.guard(text, pick, x_post.reason_in(text)), [])
        self.assertIn('numbers not in the pick: 99', x_post.guard(text + '\n99 yards.', pick, x_post.reason_in(text)))

    def test_a_missing_saved_reason_uses_verified_pick_evidence_or_holds(self):
        supported = dict(PROP, lane='gut_call', reasons=['He cleared this line in 4 of his last 5 full games.'])
        with mock.patch.object(x_post, 'load_reasons', return_value={}):
            text = x_post.draft(supported, {'league': 'NFL'})
        self.assertIn('He cleared this line in 4 of his last 5 full games.', text)
        self.assertEqual(x_post.guard(text, supported, x_post.reason_in(text)), [])

        unsupported = dict(PROP, lane='gut_call', why='The projection is the only reason.', hitStrip={})
        with mock.patch.object(x_post, 'load_reasons', return_value={}):
            held = x_post.draft(unsupported, {'league': 'NFL'})
        self.assertIn('play has no supporting reason', x_post.guard(held, unsupported, x_post.reason_in(held)))

    def test_new_lane_play_is_held_without_a_reason_and_maps_the_current_book_brand(self):
        play = dict(PICK, lane='gut_call', riskUnits=.5, book='ESPN BET', projection=31.2,
                    probabilityAtPublication={'chance': .54, 'breakEven': .512, 'calibrated': True})
        text = x_post.draft(play, GAME, reason='Wind is forecast at 18 mph in Ann Arbor.')
        self.assertTrue(text.startswith('🔥 Full Send: '), text)
        self.assertNotIn('Gut call', text)
        self.assertIn('theScore Bet', text)
        self.assertNotIn('ESPN BET', text)
        self.assertEqual(x_post.guard(text, play, x_post.reason_in(text)), [])
        no_reason = x_post.draft(play, GAME, reason='')
        self.assertIn('play has no supporting reason', x_post.guard(no_reason, play, None))

    def test_send_guard_refuses_a_public_play_whose_chance_does_not_beat_the_price(self):
        reason = 'Wind is forecast at 18 mph in Ann Arbor.'
        base = dict(PICK, lane='best_bet', projection=31.2,
                    probabilityAtPublication={'chance': .520, 'breakEven': .526, 'calibrated': True})
        text = x_post.draft(base, GAME, reason=reason)
        self.assertTrue(any('does not beat the price need' in problem
                            for problem in x_post.guard(text, base, reason)))
        equal = dict(base, probabilityAtPublication={'chance': .515, 'breakEven': .515, 'calibrated': True})
        self.assertTrue(any('does not beat the price need' in problem
                            for problem in x_post.guard(text, equal, reason)))
        plus = dict(base, odds=180,
                    probabilityAtPublication={'chance': .410, 'breakEven': round(1 / 2.8, 3), 'calibrated': True})
        self.assertEqual(x_post.guard(x_post.draft(plus, GAME, reason=reason), plus, reason), [])

    def test_no_reason_is_invented_from_unlabelled_or_opposing_prose(self):
        with mock.patch.object(x_post, 'load_reasons', return_value={}):
            text = x_post.draft(dict(PROP, why='The opponent allows 8 catches, which argues against our under.'), {'league': 'NFL'})
        self.assertNotIn('opponent allows', text)

    def test_exact_line_hit_strip_can_supply_a_numbered_reason(self):
        backed = dict(PROP, hitStrip={'season': [3, 5], 'last10': [7, 10]})
        with mock.patch.object(x_post, 'load_reasons', return_value={}):
            text = x_post.draft(backed, {'league': 'NFL'})
        self.assertIn('Over 4.5 in 3 of 5 this season.', text)
        self.assertEqual(x_post.reason_kind(x_post.reason_in(text)), 'stats')

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

    def test_long_verified_reason_never_becomes_a_dangling_half_sentence(self):
        reason = ('DK Metcalf was removed from the Steelers injury report Saturday and has no injury '
                  'designation after being listed with an illness.')
        self.assertEqual(x_post._short_reason(reason),
                         'DK Metcalf was removed from the Steelers injury report Saturday.')
        self.assertNotIn('and has.', x_post._short_reason(reason))
        arithmetic = dict(PICK, why='Model lean, published on our number alone. The over reads 55.3% after the raw 62.7% is shrunk. '
                                    'Our total gap of 7.8 points is at the 95th percentile.')
        self.assertIsNone(x_post.reason_for(arithmetic), 'no stat talk in the timeline')
        text = x_post.draft(dict(arithmetic, projection=31.2), GAME)
        self.assertNotIn('percentile', text)
        self.assertIn("Book says 38.5. I have it at 31, so I'm on the under.", text)
        self.assertTrue(text.endswith('@Playbook #CFB'))

    def test_url_counts_as_twenty_three(self):
        self.assertEqual(x_post.tweet_length('hi https://keenroudy.com/sports/#pick/a-very-long-identifier-indeed'), 3 + 23)

    def test_a_long_why_is_trimmed_to_fit(self):
        long = dict(PICK, why=' '.join(['A long reason that goes on for a while and says a great deal about nothing much at all.'] * 6))
        text = x_post.draft(long, GAME)
        self.assertLessEqual(x_post.tweet_length(text), 280)


class FunPostTests(unittest.TestCase):
    RUNG = {'id': 'NFL-2026-W4-ladder-0927-fd', 'title': 'Ladder step 2: 2 legs at FanDuel', 'status': 'active', 'parlayType': 'ladder',
            'riskUnits': 0.25, 'odds': 95, 'book': 'FanDuel', 'gameIds': ['NFL-1'],
            'legs': [{'title': 'Drake London 40+ receiving yards'}, {'title': 'Bijan Robinson 50+ rushing yards'}],
            'ladder': {'run': 1, 'step': 2, 'stake': 75, 'payout': 146, 'banked': 19, 'bankThisWin': 29,
                       'bankedAfter': 48, 'nextStake': 117, 'totalAfter': 165, 'bankPercent': 20,
                       'ridePercent': 80, 'start': 50, 'goal': 1000}}

    def test_a_ladder_rung_leads_with_its_step_and_the_money_riding(self):
        text = x_post.draft(self.RUNG, {'league': 'NFL'})
        self.assertEqual(text, "$50 → $1,000 · 80/20 CLIMB · STEP 2\n$75 → $146 (+95, FanDuel)\nStep 1 cashed. $19 in the bank.\n\nDrake London 40+ rec yds\n"
                               "Bijan Robinson 50+ rush yds\n\nStill climbing? ❤️\n@Playbook #NFL")
        self.assertEqual(x_post.guard(text, self.RUNG), [], 'every dollar and percentage is the rung\'s own number')
        second = dict(self.RUNG, ladder=dict(self.RUNG['ladder'], run=2, step=1, stake=50, payout=98, banked=0,
                                             bankThisWin=20, bankedAfter=20, nextStake=78, totalAfter=98))
        self.assertTrue(x_post.draft(second, {'league': 'NFL'}).startswith("$50 → $1,000 · 80/20 CLIMB · STEP 1\n$50 → $98"))
        self.assertNotIn('Climb #', x_post.draft(second, {'league': 'NFL'}))

    def test_a_fun_parlay_leads_with_its_price(self):
        ticket = {'odds': 2506, 'parlayType': 'longshot', 'book': 'FanDuel', 'legs': [{}, {}, {}, {}, {}]}
        self.assertEqual(x_post.parlay_head(ticket, 'CFB'), "🎰 +2506 Chef's Special (FanDuel)")
        self.assertEqual(x_post.parlay_head(dict(ticket, odds=583), 'NFL'), "🎰 +583 Chef's Special (FanDuel)")

    def test_a_safer_combo_uses_its_own_exact_shape(self):
        ticket = {'id': 'NFL-safer', 'league': 'NFL', 'lane': 'safer_combo', 'parlayType': 'comfort',
                  'book': 'DraftKings', 'odds': -150, 'legs': [
                      {'title': 'Bills moneyline', 'reasons': ['Bills won 8 of their last 10.']},
                      {'title': 'Rams moneyline', 'reasons': ['Rams won 7 of their last 9.']}],
                  'riskUnits': 1}
        text = x_post.draft(ticket, {'league': 'NFL'})
        self.assertEqual(text, '🛡️ Safer combo (-150, DraftKings)\n\nBills moneyline\nRams moneyline\n\n'
                               'Bills won 8 of their last 10.\n@Playbook #NFL')
        self.assertEqual(x_post.guard(text, ticket), [])


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
            self.assertEqual(again['posts'][0]['cardTheme'], 'none')

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
        self.assertEqual(x_post.units_for({'odds': 255, 'result': 'win', 'riskUnits': 0.25, 'units': 0.346}), 0.346,
                         'a corrected or repriced settlement keeps the book result that was saved')

    def test_recap_text(self):
        games = {'g1': {'kickoff': '2026-09-26T17:00Z'}, 'g2': {'kickoff': '2026-09-26T20:00Z'}, 'g3': {'kickoff': '2026-09-27T17:00Z'}}
        first = {'a': {'id': 'a', 'title': 'A over 40', 'favorite': True, 'odds': -110, 'gameIds': ['g1']},
                 'b': {'id': 'b', 'title': 'B under 50', 'modelLean': True, 'odds': -105, 'gameIds': ['g2']},
                 'c': {'id': 'c', 'title': 'C tomorrow', 'odds': -110, 'gameIds': ['g3']}}
        latest = {'a': {'result': 'win'}, 'b': {'result': 'loss'}, 'c': {'result': 'win'}}
        text = x_post.recap('2026-09-26', first, latest, games, NOW)
        self.assertIn('Saturday went 1-1', text)
        self.assertNotIn('u)', text, 'no units in anything a follower reads')
        self.assertIn('✅ A over 40', text)
        self.assertIn('❌ B under 50', text)
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
        self.assertEqual(text, "🎰 +650 Chef's Special (DraftKings)\n\nBills/Lions over 44.5\nJets +3\nPlayer Seven over 4.5 catches\n\n$10 → $75"
                               "\n\n❤️ if you're tailing\n@Playbook #NFL")
        self.assertLessEqual(x_post.tweet_length(text), 280)
        self.assertEqual(x_post.guard(text, ticket), [], text)
