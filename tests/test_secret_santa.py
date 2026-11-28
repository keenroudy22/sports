import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import secret_santa


class SecretSantaTests(unittest.TestCase):
    def setUp(self):
        self.play, = json.loads((ROOT / 'data/secret-santa.json').read_text())[:1]
        self.start = self.play['startsAt']
        self.now = datetime(2026, 11, 25, 4, tzinfo=timezone.utc)
        self.game = dict(
            league='CFB', eventId='401866471', kickoff=self.start,
            home={'id': '2711', 'score': 17}, away={'id': '193', 'score': 20},
            retrievedAt='2026-11-25T02:55:00Z',
            sources={'page': 'https://www.espn.com/college-football/boxscore/_/gameId/401866471'},
        )

    def test_open_step_uses_paper_balance_and_half_up_payout(self):
        view = secret_santa.build([self.play], [], {}, self.now)
        self.assertEqual(view['balance'], 2000)
        self.assertEqual(view['current']['winReturn'], 2460)
        self.assertEqual(view['history'], [])

    def test_later_step_uses_settled_full_return(self):
        later = dict(self.play, eventId='2', startsAt='2026-11-25T03:50:00Z', checkedAt='2026-11-25T03:05:00Z')
        view = secret_santa.build([self.play, later], [self.game], {}, self.now)
        self.assertEqual(view['wins'], 1)
        self.assertEqual(view['current']['balance'], 2460)
        too_soon = dict(later, checkedAt='2026-11-25T02:50:00Z')
        self.assertIsNone(secret_santa.build([self.play, too_soon], [self.game], {}, self.now)['current'])

    def test_loss_ends_run_and_unverified_fixture_stays_open(self):
        loss = dict(self.game, away={'id': '193', 'score': 21})
        view = secret_santa.build([self.play], [loss], {}, self.now)
        self.assertTrue(view['closed'])
        self.assertEqual(view['balance'], 0)
        for unverified in (dict(loss, away={'id': '194', 'score': 21}), dict(loss, retrievedAt='2026-11-25T06:00:00Z')):
            self.assertIsNotNone(secret_santa.build([self.play], [unverified], {}, self.now)['current'])

    def test_push_keeps_the_balance(self):
        play = dict(self.play, line=3)
        view = secret_santa.build([play], [self.game], {}, self.now)
        self.assertEqual(view['pushes'], 1)
        self.assertEqual(view['balance'], 2000)

    def test_receiving_alt_uses_the_exact_player_stat_and_official_final(self):
        play = dict(self.play, market='player', side='over', line=24.5, stat='recYds',
                    athleteId='5127885', teamId=self.play['homeId'])
        player = dict(id=play['athleteId'], team=play['teamId'], recYds=25)
        def build(rows, **changes):
            return secret_santa.build([dict(play, **changes)], [dict(self.game, players=rows)], {}, self.now)
        for yards, result in [(25, 'win'), (24, 'loss'), (0, 'loss')]:
            view = build([dict(player, recYds=yards)])
            self.assertEqual((view['history'][0]['result'], view['history'][0]['score']),
                             (result, f'{yards} receiving yards'))
        self.assertEqual(build([player], line=25, side='under')['pushes'], 1)
        for rows in [[], [dict(player, id='2')], [dict(player, team=play['awayId'])],
                     [dict(player, dnp=True)], [dict(player, recYds=None)], [player, player]]:
            self.assertIsNotNone(build(rows)['current'])
        for changes in [dict(teamId='0'), dict(stat='yards'), dict(league='NBA'), dict(athleteId='')]:
            with self.assertRaises(ValueError):
                build([player], **changes)

    def test_owner_restart_preserves_the_loss_and_funds_a_new_step(self):
        restart = {'restartAfter': self.play['eventId']}
        loss = dict(self.game, away={'id': '193', 'score': 21})
        view = secret_santa.build([self.play, restart], [loss], {}, self.now)
        self.assertEqual((view['run'], view['balance'], view['losses']), (2, 2000, 0))
        self.assertFalse(view['closed'])
        self.assertIsNone(view['current'])
        self.assertEqual([(row['run'], row['step'], row['result']) for row in view['history']], [(1, 1, 'loss')])

        later = dict(self.play, eventId='2', startsAt='2026-11-25T03:50:00Z', checkedAt='2026-11-25T03:05:00Z')
        view = secret_santa.build([self.play, restart, later], [loss], {}, self.now)
        self.assertEqual((view['current']['run'], view['current']['step'], view['current']['balance']), (2, 1, 2000))

    def test_restart_requires_the_named_official_loss(self):
        restart = {'restartAfter': self.play['eventId']}
        self.assertEqual(secret_santa.build([self.play, restart], [], {}, self.now)['run'], 1)
        self.assertEqual(secret_santa.build([self.play, restart], [self.game], {}, self.now)['run'], 1)
        loss = dict(self.game, away={'id': '193', 'score': 21})
        self.assertTrue(secret_santa.build([self.play, {'restartAfter': '999'}], [loss], {}, self.now)['closed'])

    def test_espn_hoops_final_without_source_field_settles_houston_step(self):
        entries = json.loads((ROOT / 'data/secret-santa.json').read_text())[:3]
        loss = dict(self.game, away={'id': '193', 'score': 21})
        final = dict(eventId='401909323', kickoff='2026-11-26T01:30Z',
                     retrievedAt='2026-11-26T04:34:23Z', state='post', type=2,
                     home={'id': '10'}, away={'id': '21'}, homeScore=116, awayScore=104)
        now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
        view = secret_santa.build(entries, [loss], {'NBA': [final]}, now)
        self.assertEqual((view['run'], view['wins'], view['balance']), (2, 1, 2472))
        self.assertIsNone(view['current'])
        self.assertEqual(view['history'][-1]['resultUrl'],
                         'https://www.espn.com/nba/boxscore/_/gameId/401909323')
        scheduled = dict(final, state='pre')
        self.assertEqual(secret_santa.build(entries, [loss], {'NBA': [scheduled]}, now)['wins'], 0)

    def test_pregame_withdrawal_preserves_original_and_does_not_consume_a_step(self):
        action = dict(withdrawBeforeKickoff=self.play['eventId'],
                      withdrawnAt='2026-11-24T23:00:00Z', reason='The original price did not qualify.')
        before = datetime(2026, 11, 24, 22, tzinfo=timezone.utc)
        self.assertEqual(secret_santa.build([self.play, action], [], {}, before)['current']['step'], 1)
        view = secret_santa.build([self.play, action], [self.game], {}, self.now)
        self.assertEqual((view['balance'], view['wins'], view['losses'], view['pushes']), (2000, 0, 0, 0))
        self.assertIsNone(view['current'])
        self.assertEqual(view['passToday'], action['reason'])
        self.assertEqual(view['history'][0]['result'], 'withdrawn')
        self.assertEqual(view['history'][0]['odds'], self.play['odds'])
        new_play = dict(self.play, eventId='2', startsAt='2026-11-25T02:00:00Z', checkedAt='2026-11-24T23:15:00Z')
        replacement = secret_santa.build([self.play, action, new_play], [self.game], {}, self.now)
        self.assertEqual(replacement['current']['step'], 1)
        self.assertIsNone(replacement['passToday'])
        with self.assertRaises(ValueError):
            secret_santa.build([self.play, dict(action, withdrawnAt=self.start)], [], {}, self.now)


class SecretSantaPairTests(unittest.TestCase):
    def setUp(self):
        SecretSantaTests.setUp(self)
        self.gilmer_loss = dict(self.game, away={'id': '193', 'score': 21})
        self.marker = {'format': secret_santa.PAIR_FORMAT, 'restartAfter':self.play['eventId'],
                       'openedAt':'2026-11-25T03:00:00Z'}
        self.prefix = [self.play, self.marker]
        self.now = datetime(2026, 11, 26, 5, tzinfo=timezone.utc)
        self.check = '2026-11-25T12:00:00Z'
        self.start = '2026-11-25T20:00:00Z'
        book_url = 'https://sportsbook.fanduel.com/football/example'
        src = 'https://www.espn.com/example'
        review = dict(checkedAt=self.check, workload='16 carries', availability='starting and active',
                      matchup='opponent conceded 90 on 18 carries', countercase='late substitution',
                      roleSource=src, availabilitySource=src, matchupSource=src)
        fb = dict(league='CFB',eventId='500',awayId='1',homeId='2',athleteId='3',teamId='1',
                  startsAt=self.start,stat='rushYds',side='over',line=39.5,odds=-400,book='FanDuel',
                  selection='Runner 40+ rushing',matchup='Away at Home',quoteUrl=book_url,review=review)
        nba = dict(fb,league='NBA',eventId='600',athleteId='4',stat='reb',line=3.5,
                   selection='Center 4+ rebounds')
        self.pair = dict(legs=[fb,nba],checkedAt=self.check,book='FanDuel',odds=-178,unboosted=True,
                         quoteVerified=True,quoteUrl=book_url,reason='Both have the reviewed workload.')
        self.fb_game = dict(self.game,eventId='500',kickoff=self.start,away={'id':'1','score':21},
                            home={'id':'2','score':28},retrievedAt='2026-11-25T23:20Z',
                            players=[dict(id='3',team='1',rushYds=45)])
        self.nba_game = dict(self.fb_game,league='NBA',eventId='600',state='post',type=2,homeScore=110,awayScore=100)
        self.box = dict(league='NBA',eventId='NBA-600',kickoff=self.start,teams={'1':{},'2':{}},
                        players=[dict(id='4',team='1',stats={'reb':4})],retrievedAt='2026-11-25T23:30Z',source=src)

    def view(self, plays=None, boxes=None):
        return secret_santa.build(self.prefix + ([self.pair] if plays is None else plays),
                                  [self.gilmer_loss,self.fb_game],{'NBA':[self.nba_game]},
                                  self.now,[self.box] if boxes is None else boxes)

    def test_pair_plan_and_legacy_history(self):
        v=self.view([]); self.assertEqual((v['balance'],v['run'],v['history'][0]['result']), (2000,2,'loss'))
        balance=v['balance']
        for _ in range(v['planWins']):
            balance=secret_santa.return_on_win(balance,v['targetOdds'])
        self.assertEqual(balance, 1090971)
        self.assertEqual(self.view([dict(self.pair, odds=-270)])['balance'], 2741)
        self.assertEqual(secret_santa.return_on_win(2000,120),4400)

    def test_settles_both_official_fixtures_once(self):
        v=self.view();self.assertEqual((v['wins'],v['balance'],v['current']),(1,3124,None))
        self.assertEqual([g['score'] for g in v['history'][-1]['legs']],['45 rushing yards','4 rebounds'])
        self.assertEqual(self.view(boxes=[])['current']['winReturn'],3124)
        self.box['players'][0]['dnp']=True
        self.assertEqual(self.view()['balance'],2500)
        self.fb_game['players'][0]['dnp']=True
        self.assertEqual(self.view()['pushes'],1)
        self.fb_game['players']=[dict(id='3',team='1',rushYds=39)]
        self.assertTrue(self.view()['closed'])

    def test_research_and_quote_validation(self):
        for changes in [dict(legs=self.pair['legs'][:1]),dict(odds=-271),dict(quoteVerified=False),
                        dict(unboosted=False),dict(quoteUrl='https://example.com/')]:
            with self.assertRaises(ValueError):
                self.view([dict(self.pair,**changes)])
        for changes in [dict(book='DraftKings'),dict(startsAt=self.check),
                        dict(review=dict(self.pair['legs'][0]['review'],availabilitySource='')),
                        dict(review=dict(self.pair['legs'][0]['review'],checkedAt='2026-11-25T09:00Z'))]:
            with self.assertRaises(ValueError):
                self.view([dict(self.pair,legs=[dict(self.pair['legs'][0],**changes),self.pair['legs'][1]])])
        with self.assertRaises(ValueError):
            self.view([dict(self.pair,legs=[self.pair['legs'][0],dict(self.pair['legs'][0],athleteId='5')])])
        with self.assertRaises(ValueError):
            self.view([self.pair,self.pair])
