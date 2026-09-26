import sys
import unittest
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import ladder

NOW = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)          # Sunday 8:30 AM ET


def game(gid, away, home, kickoff='2026-09-27T17:00Z', league='NFL'):
    return {'id': gid, 'league': league, 'state': 'pre', 'kickoff': kickoff, 'season': 2026, 'week': 4,
            'source': f'https://www.espn.com/nfl/game/_/gameId/{gid}',
            'away': {'id': f'{gid}a', 'short': away, 'abbreviation': away[:3].upper()},
            'home': {'id': f'{gid}h', 'short': home, 'abbreviation': home[:3].upper()}}


GAMES = {'g1': game('g1', 'Bills', 'Lions'), 'g2': game('g2', 'Jets', 'Rams'),
         'late': game('late', 'Bears', 'Packers', '2026-09-27T13:15Z')}      # 9:15 AM ET: too close to post a rung before


def snapshot(gid):
    return {'gameId': gid, 'league': 'NFL', 'players': {'home': {'players': [
        {'id': f'{gid}p', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5], 'receptions': [5.8, 3.5, 8.1]},
        {'id': f'{gid}q', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5], 'limited': True},
        {'id': f'{gid}r', 'pos': 'WR', 'recYds': [70.0, 40.5, 99.5]}]}, 'away': {'players': []}}}


def ctx(first=None, latest=None, prop_odds=None, injuries=None):
    names, appearances = {}, defaultdict(int)
    for gid in ('g1', 'g2'):
        names.update({f'{gid}p': f'Player {gid.upper()}', f'{gid}q': f'Hurt {gid.upper()}', f'{gid}r': f'Rookie {gid.upper()}'})
        appearances.update({f'{gid}p': 3, f'{gid}q': 3})               # the rookies have no games: unsettled
    return SimpleNamespace(snapshot=lambda gid: snapshot(gid) if gid in ('g1', 'g2') else None, names=names,
                           appearances=appearances, established=set(), injuries=injuries or {}, first=first or {},
                           latest=latest or {}, policy={}, prop_odds=prop_odds if prop_odds is not None else {g: record(g) for g in ('g1', 'g2')})


def record(gid, price=-300, retrieved='2026-09-27T12:10:00Z'):
    ladder_rungs = [{'line': 39.5, 'over': price},        # 91% on our numbers against 75%: the leg
                    {'line': 29.5, 'over': -150},          # out of order below it: another market's rung
                    {'line': 24.5, 'over': -900},          # never reached: the walk stopped at 29.5
                    {'line': 89.5, 'over': 250}]           # a long shot on our numbers
    quote = lambda: {'line': 64.5, 'over': -115, 'under': -105, 'alternates': [dict(r) for r in ladder_rungs]}
    return {'gameId': gid, 'retrievedAt': retrieved, 'books': {'draftkings': {'markets': {'recYds': {
        f'Player {gid.upper()}': quote(), f'Hurt {gid.upper()}': quote(), f'Rookie {gid.upper()}': quote(),
        'Somebody Else': quote()}}}, 'betmgm': {'markets': {'recYds': {f'Player {gid.upper()}': quote()}}}}}


def rung(key, published, step, stake, payout, result=None, run=1, **over):
    pick = {'id': key, 'parlayType': 'ladder', 'publishedAt': published, 'status': 'active', 'odds': 100, 'book': 'FanDuel',
            'ladder': {'run': run, 'step': step, 'stake': stake, 'payout': payout, 'start': 50, 'goal': 1000},
            'legs': [{'title': 'A 40+ receiving yards'}, {'title': 'B 50+ rushing yards'}]}
    latest = dict(pick, **over)
    if result:
        latest.update(result=result, status='settled', settledAt=published)
    return pick, latest


def book_of(*rungs):
    first, latest = {}, {}
    for pick, recent in rungs:
        first[pick['id']], latest[pick['id']] = pick, recent
    return first, latest


class StateTests(unittest.TestCase):
    def test_a_win_rolls_the_payout_a_loss_starts_over_and_a_pulled_rung_never_counts(self):
        first, latest = book_of(rung('r1', '2026-09-27T12:30:00Z', 1, 50, 96, 'win'),
                                rung('r2', '2026-09-28T12:30:00Z', 2, 96, 187, 'loss'),
                                rung('r3', '2026-10-01T12:30:00Z', 1, 50, 99, entryNote='Closed before its post went out', status='expired'),
                                rung('r4', '2026-10-03T12:30:00Z', 1, 50, 97, run=2))
        where = ladder.state(first, latest)
        self.assertEqual((where['run'], where['step'], where['stake']), (2, 1, 50))
        self.assertEqual(where['open']['id'], 'r4')
        self.assertEqual([h['id'] for h in where['history']], ['r1', 'r2'], 'the pulled rung is not in the climb')

    def test_the_goal_finishes_a_climb_and_a_push_keeps_the_stake(self):
        first, latest = book_of(rung('a', '2026-09-27T12:30:00Z', 4, 540, 1062, 'win'),
                                rung('b', '2026-09-28T12:30:00Z', 1, 50, 98, 'push', run=2))
        where = ladder.state(first, latest)
        self.assertEqual(where['climbs'], [{'run': 1, 'steps': 4, 'final': 1062, 'id': 'a'}])
        self.assertEqual((where['run'], where['step'], where['stake'], where['open']), (2, 1, 50, None))

    def test_payout_is_whole_dollars(self):
        self.assertEqual(ladder.payout(50, -108), 96)
        self.assertEqual(ladder.payout(96, 125), 216)


class LegTests(unittest.TestCase):
    def test_only_the_main_lines_own_ladder_at_a_sane_price_for_a_settled_healthy_player(self):
        legs = ladder.legs_for_game(GAMES['g1'], record('g1'), ctx(), NOW)
        self.assertEqual([(l['title'], l['odds'], l['book']) for l in legs], [('Player G1 40+ receiving yards', -300, 'DraftKings')])
        leg = legs[0]
        self.assertEqual((leg['athleteId'], leg['market'], leg['direction'], leg['line']), ('g1p', 'recYds', 'over', 39.5))
        self.assertTrue(ladder.MIN_GAP <= leg['chance'] - leg['implied'] <= ladder.MAX_GAP)

    def test_a_listed_player_a_stale_capture_and_a_book_far_off_our_number_are_left_off(self):
        listed = ctx(injuries={'NFL-g1h': {'g1p': {'status': 'Questionable'}}})
        self.assertEqual(ladder.legs_for_game(GAMES['g1'], record('g1'), listed, NOW), [])
        self.assertEqual(ladder.legs_for_game(GAMES['g1'], record('g1', retrieved='2026-09-26T20:00:00Z'), ctx(), NOW), [])
        self.assertEqual(ladder.legs_for_game(GAMES['g1'], record('g1', price=-150), ctx(), NOW), [],
                         '91% against 60% is a gap no book leaves on an easy line: a data or role problem')


class BuildTests(unittest.TestCase):
    def test_two_games_one_book_about_even_money(self):
        legs = [leg for gid in ('g1', 'g2') for leg in ladder.legs_for_game(GAMES[gid], record(gid), ctx(), NOW)]
        ticket, reason = ladder.build(legs)
        self.assertIsNone(reason)
        self.assertEqual((ticket['book'], ticket['odds'], sorted(ticket['gameIds'])), ('DraftKings', -129, ['g1', 'g2']))
        none, why = ladder.build(legs[:1])
        self.assertIsNone(none)
        self.assertIn('two games', why)

    def test_the_rung_carries_the_climb_and_waits_while_one_is_open(self):
        pick, reason = ladder.candidate(ctx(), GAMES, NOW)
        self.assertIsNone(reason)
        self.assertEqual(pick['id'], 'NFL-2026-W4-ladder-0927-dk')
        self.assertEqual((pick['parlayType'], pick['odds'], pick['book']), ('ladder', -129, 'DraftKings'))
        self.assertEqual(pick['ladder'], {'run': 1, 'step': 1, 'stake': 50, 'payout': 89, 'start': 50, 'goal': 1000})
        self.assertEqual(pick['expiresAt'], '2026-09-27T15:45:00Z', 'the next run, before the first kickoff')
        self.assertIn('https://sharpapi.io/', pick['sources'])
        first, latest = book_of(rung('open', '2026-09-26T12:30:00Z', 1, 50, 96))
        none, why = ladder.candidate(ctx(first, latest), GAMES, NOW)
        self.assertIsNone(none)
        self.assertIn('still open', why)
        self.assertIn('0 games left today', ladder.candidate(ctx(), {'late': GAMES['late']}, NOW)[1])


class GateTests(unittest.TestCase):
    def test_one_rung_open_at_a_time_and_one_played_a_day(self):
        pick, _ = ladder.candidate(ctx(), GAMES, NOW)
        self.assertEqual(gates.kind_of(pick), 'ladder')
        view = lambda first, latest: SimpleNamespace(first=first, latest=latest, now=NOW)
        self.assertTrue(gates.ladder_one_rung(pick, view({}, {})).ok)
        first, latest = book_of(rung('open', '2026-09-26T12:30:00Z', 1, 50, 96))
        self.assertIn('still open', gates.ladder_one_rung(pick, view(first, latest)).reason)
        first, latest = book_of(rung('today', '2026-09-27T11:00:00Z', 1, 50, 96, 'win'))
        self.assertIn("today's rung", gates.ladder_one_rung(pick, view(first, latest)).reason)
        first, latest = book_of(rung('pulled', '2026-09-27T11:00:00Z', 1, 50, 96, entryNote='pulled', status='expired'),
                                rung('yesterday', '2026-09-26T11:00:00Z', 1, 50, 96, 'loss'))
        self.assertTrue(gates.ladder_one_rung(pick, view(first, latest)).ok, 'a pulled rung and yesterday\'s graded one leave today free')


if __name__ == '__main__':
    unittest.main()
