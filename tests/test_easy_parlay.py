import sys
import tempfile
import unittest
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import easy_parlay
import gates

NOW = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)          # Sunday 8:30 AM ET


def game(gid, away, home, kickoff='2026-09-27T17:00Z'):
    return {'id': gid, 'league': 'NFL', 'state': 'pre', 'kickoff': kickoff, 'season': 2026, 'week': 4,
            'source': f'https://www.espn.com/nfl/game/_/gameId/{gid}',
            'away': {'id': f'{gid}a', 'short': away, 'abbreviation': away[:3].upper()},
            'home': {'id': f'{gid}h', 'short': home, 'abbreviation': home[:3].upper()}}


GAMES = {'g1': game('g1', 'Bills', 'Lions'), 'g2': game('g2', 'Jets', 'Rams'), 'g3': game('g3', 'Colts', 'Chiefs'),
         'late': game('late', 'Bears', 'Packers', '2026-09-27T13:15Z')}      # 9:15 AM ET: too close to post before


def snapshot(gid, pid):
    return {'gameId': gid, 'league': 'NFL', 'players': {'home': {'players': [
        {'id': pid, 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5], 'receptions': [5.8, 3.5, 8.1]},
        {'id': pid + 'q', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5], 'limited': True},
        {'id': pid + 'n', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': {'players': []}}}


def ctx():
    names = {}
    for gid in ('g1', 'g2', 'g3'):
        names.update({f'{gid}p': f'Player {gid.upper()}', f'{gid}pq': f'Hurt {gid.upper()}', f'{gid}pn': f'Rookie {gid.upper()}'})
    appearances = defaultdict(int, {f'{gid}p': 3 for gid in ('g1', 'g2', 'g3')})
    appearances.update({f'{gid}pq': 3 for gid in ('g1', 'g2', 'g3')})         # the rookies have one game: unsettled
    return SimpleNamespace(snapshot=lambda gid: snapshot(gid, f'{gid}p') if gid in ('g1', 'g2', 'g3') else None,
                           names=names, appearances=appearances, established=set(), first={}, latest={}, policy={})


def books(gid, price=-250):
    over = lambda who, point, p: {'name': 'Over', 'description': who, 'point': point, 'price': p}
    return [{'key': 'draftkings', 'last_update': '2026-09-27T12:20:00Z', 'markets': [
        {'key': 'player_reception_yds_alternate', 'outcomes': [
            over(f'Player {gid.upper()}', 39.5, price),          # 91% on our numbers against 71%: the leg
            over(f'Player {gid.upper()}', 19.5, -900),            # too short a price to be worth a place
            over(f'Player {gid.upper()}', 69.5, +100),            # a coin flip on our numbers
            over(f'Hurt {gid.upper()}', 39.5, price),              # questionable on the report
            over(f'Rookie {gid.upper()}', 39.5, price),            # role not settled
            over('Somebody Else', 39.5, price),                   # not in our projections
            {'name': 'Under', 'description': f'Player {gid.upper()}', 'point': 39.5, 'price': 200}]}]}]


class LegTests(unittest.TestCase):
    def test_only_easy_lines_we_clear_comfortably_at_a_sane_price(self):
        legs = easy_parlay.legs_for_game(GAMES['g1'], books('g1'), ctx(), NOW)
        self.assertEqual([(l['title'], l['odds']) for l in legs], [('Player G1 40+ receiving yards', -250)])
        leg = legs[0]
        self.assertEqual((leg['athleteId'], leg['market'], leg['direction'], leg['line'], leg['book']), ('g1p', 'recYds', 'over', 39.5, 'DraftKings'))
        self.assertGreaterEqual(leg['chance'], easy_parlay.MIN_CHANCE)
        self.assertEqual(easy_parlay.name_key('Kenneth Walker III'), easy_parlay.name_key('Kenneth Walker'))

    def test_one_leg_per_game_three_games_one_book_priced_as_multiplied(self):
        legs = [leg for gid in ('g1', 'g2', 'g3') for leg in easy_parlay.legs_for_game(GAMES[gid], books(gid), ctx(), NOW)]
        ticket, reason = easy_parlay.build(legs)
        self.assertIsNone(reason)
        self.assertEqual((len(ticket['legs']), ticket['book']), (3, 'DraftKings'))
        self.assertEqual(len(set(ticket['gameIds'])), 3)
        self.assertEqual(ticket['odds'], 174, 'three legs at -250 multiply to 2.744, +174 as books round')
        few, why = easy_parlay.build(legs[:2])
        self.assertIsNone(few)
        self.assertIn('no book has 3 games', why)


class CandidateTests(unittest.TestCase):
    def fake_get(self, calls):
        events = [{'id': f'e-{gid}', 'commence_time': '2026-09-27T17:00:00Z', 'away_team': f'Buffalo {GAMES[gid]["away"]["short"]}',
                   'home_team': f'Detroit {GAMES[gid]["home"]["short"]}'} for gid in ('g1', 'g2', 'g3')]

        def get(url):
            calls.append(url)
            if url.split('?')[0].endswith('/events'):
                return events, {}
            gid = url.split('/events/e-')[1].split('/')[0]
            return {'bookmakers': books(gid)}, {'x-requests-remaining': '400'}
        return get

    def test_the_ticket_is_a_quarter_unit_fun_parlay_that_never_claims_value(self):
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            pick, reason = easy_parlay.candidate(ctx(), GAMES, NOW, key='k', get=self.fake_get(calls), cache=folder, remaining=400, log=lambda *_: None)
            self.assertIsNone(reason)
            self.assertEqual((pick['parlayType'], pick['riskUnits'], pick['odds'], pick['book']), ('easyProps', 0.25, 174, 'DraftKings'))
            self.assertTrue(pick['edge'].startswith('For fun, not value'))
            self.assertIn('https://the-odds-api.com/', pick['sources'])
            self.assertNotIn('k', ' '.join(pick['sources']).split('the-odds-api.com')[1], 'the key never reaches the record')
            self.assertEqual(len(calls), 4, 'the event list, then one call per game')
            easy_parlay.candidate(ctx(), GAMES, NOW, key='k', get=self.fake_get(calls), cache=folder, remaining=400, log=lambda *_: None)
            self.assertEqual(len(calls), 4, 'a fresh cache is not fetched again')

    def test_a_game_the_desk_has_a_reason_against_is_left_off(self):
        with tempfile.TemporaryDirectory() as folder:
            pick, reason = easy_parlay.candidate(ctx(), GAMES, NOW, key='k', get=lambda url: self.fail('nothing to fetch'), cache=folder,
                                                 remaining=400, log=lambda *_: None, exclude={'g1'})
        self.assertIsNone(pick)
        self.assertIn('only 2 NFL games', reason)

    def test_the_reserve_and_a_rehearsal_never_spend(self):
        with tempfile.TemporaryDirectory() as folder:
            pick, reason = easy_parlay.candidate(ctx(), GAMES, NOW, key='k', get=lambda url: self.fail('spent into the reserve'),
                                                 cache=folder, remaining=easy_parlay.RESERVE + 2, log=lambda *_: None)
            self.assertIsNone(pick)
            pick, _ = easy_parlay.candidate(ctx(), GAMES, NOW, key='k', get=lambda url: self.fail('a rehearsal spent'),
                                            cache=folder, remaining=400, log=lambda *_: None, spend=False)
            self.assertIsNone(pick)


class ExpiryTests(unittest.TestCase):
    """A fun parlay carries an expiry the gates accept: the next run or the first kickoff, whichever comes first."""

    def test_both_parlays_pass_the_expiry_gate(self):
        import run
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            pick, _ = easy_parlay.candidate(ctx(), GAMES, NOW, key='k', get=CandidateTests().fake_get(calls), cache=folder,
                                            remaining=400, log=lambda *_: None)
        context = SimpleNamespace(now=NOW, games=GAMES, first={}, latest={})
        self.assertTrue(gates.expiry_ok(pick, context).ok, gates.expiry_ok(pick, context).reason)
        row = lambda gid: {'id': f'line-{gid}', 'title': f'{gid} over 44.5', 'gameId': gid, 'league': 'NFL', 'state': 'open', 'odds': -110,
                           'grade': {'chance': 0.56}, 'kickoff': GAMES[gid]['kickoff'], 'market': 'total points', 'direction': 'over',
                           'line': 44.5, 'book': 'DraftKings', 'observedAt': '2026-09-27T12:00:00Z'}
        ticket, reason = run.longshot_candidate([row(g) for g in ('g1', 'g2', 'g3')], GAMES, NOW, 'NFL')
        self.assertIsNone(reason)
        self.assertTrue(gates.expiry_ok(ticket, context).ok, gates.expiry_ok(ticket, context).reason)
        self.assertEqual(sorted(l['title'] for l in ticket['legs']), ['Bills at Lions over 44.5', 'Colts at Chiefs over 44.5', 'Jets at Rams over 44.5'],
                         'legs read the way a post says them')
        spread = dict(row('g1'), id='game-g1-spread', title='LIO -3.5', market='point spread', direction=None, line=-3.5)
        ticket, _ = run.longshot_candidate([spread, row('g2'), row('g3')], GAMES, NOW, 'NFL')
        leg = next(l for l in ticket['legs'] if l['market'] == 'point spread')
        self.assertEqual((leg['side'], leg['title']), ('home', 'Lions -3.5'), 'a home spread is named and graded as the home side')
        final = dict(GAMES['g1'], home=dict(GAMES['g1']['home'], score=27), away=dict(GAMES['g1']['away'], score=20))
        self.assertEqual(run.grade_game_pick(run.leg_pick(leg), final)[0], 'win', 'Lions by 7 cover -3.5')


class ProseTests(unittest.TestCase):
    def test_a_parlay_gets_its_words_without_a_line_or_a_side(self):
        import run
        for kind, needle in (('longshot', 'Longshot from the board'), ('easyProps', 'Easy props, for fun')):
            ticket = {'id': 'x', 'parlayType': kind, 'legs': [{}, {}, {}], 'book': 'FanDuel', 'odds': 215, 'gameIds': ['g1']}
            out = run.write_prose(ticket, SimpleNamespace(snapshot=lambda gid: None), [])
            self.assertTrue(out['why'].startswith(needle))
            self.assertIn('one miss sinks the ticket', out['risk'])


class GateTests(unittest.TestCase):
    def test_one_of_each_kind_of_fun_parlay_a_day(self):
        published = {'NFL-longshot': {'id': 'NFL-longshot', 'parlayType': 'longshot', 'legs': [{}], 'publishedAt': '2026-09-27T12:35:00Z'}}
        context = SimpleNamespace(first=published, latest={}, now=NOW.replace(hour=13))
        easy = {'id': 'NFL-easy', 'parlayType': 'easyProps', 'legs': [{}]}
        self.assertTrue(gates.longshot_one_per_day(easy, context).ok, 'the easy parlay rides beside the longshot')
        context.first['NFL-easy-1'] = dict(easy, id='NFL-easy-1', publishedAt='2026-09-27T12:40:00Z')
        refused = gates.longshot_one_per_day(easy, context)
        self.assertFalse(refused.ok)
        self.assertIn("today's easy parlay", refused.reason)
        self.assertFalse(gates.longshot_one_per_day({'id': 'x', 'parlayType': 'longshot', 'legs': [{}]}, context).ok)


if __name__ == '__main__':
    unittest.main()
