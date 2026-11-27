import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prop_ticket_review as R

NOW = datetime(2026, 11, 16, 20, 0, tzinfo=timezone.utc)
AT = NOW.isoformat()
SOURCE = 'https://sportsbook.draftkings.com/event/test-fixture'


def fixture(family='MNF', *, days=0):
    if family == 'CFB-alts':
        return college_fixture()
    league = 'NBA' if family == 'NBA-alts' else 'NFL'
    now = NOW + timedelta(days=days) + (timedelta(days=3) if family == 'TNF' else timedelta())
    at = now.isoformat()
    kick = (now + timedelta(hours=4)).isoformat()
    games = {f'{league}-1': {'id': f'{league}-1', 'league': league, 'state': 'pre', 'kickoff': kick}}
    legs = []
    for i in range(3):
        game = f'{league}-1'
        evidence = {'reviewer': 'kookn-desk', 'approved': True, 'checkedAt': at,
                    'role': 'Fixture: current starter with stable opportunity.',
                    'matchup': 'Fixture: relevant opponent opportunity evidence.',
                    'why': 'Fixture: workload supports the exact cushioned line.',
                    'countercase': 'Fixture: a low-volume game can sink all three legs.',
                    'availability': {'status': 'active', 'athleteId': str(i), 'gameId': game,
                                     'checkedAt': at, 'source': 'https://www.espn.com/test'},
                    'sources': [{'kind': kind, 'fact': 'Synthetic fixture evidence, never a real pick.',
                                 'url': 'https://www.espn.com/test', 'checkedAt': at}
                                for kind in ('role', 'matchup', 'availability')]}
        legs.append({'gameId': game, 'athleteId': str(i), 'player': f'Fixture Player {i}',
                     'kickoff': kick, 'market': 'pts' if league == 'NBA' else 'rec',
                     'direction': 'over', 'line': 2.5, 'mainLine': 4.5,
                     'period': 'full_game', 'alternate': True, 'odds': -200,
                     'book': 'DraftKings', 'observedAt': at, 'source': SOURCE, 'review': evidence})
    spec = {'family': family, 'parlayStyle': 'short', 'book': 'DraftKings', 'odds': 425,
            'priceEstimated': False, 'legs': legs,
            'correlationReview': {'checkedAt': at, 'sharedScript': 'Fixture: pace creates shared opportunity.',
                                  'failureCase': 'Fixture: slow pace suppresses every player.'}}
    spec['ticketQuote'] = {'verified': True, 'receipt': 'Private synthetic test receipt',
                           'source': SOURCE, 'checkedAt': at, 'terms': R.terms(spec)}
    return spec, games, now


def college_fixture(style='lotto', count=7, odds=511):
    spec, _, now = fixture(days=11)
    template = spec['legs'][0]
    games = {}
    spec.update(family='CFB-alts', parlayStyle=style, odds=odds, legs=[])
    for i in range(count):
        game = f'CFB-{i}'
        leg = copy.deepcopy(template)
        leg.update(gameId=game, athleteId=str(i), player=f'Player {i}', market='recYds')
        leg['review']['availability'].update(gameId=game, athleteId=str(i))
        games[game] = dict(id=game, league='CFB', state='pre', kickoff=leg['kickoff'])
        spec['legs'].append(leg)
    spec['ticketQuote']['terms'] = R.terms(spec)
    return spec, games, now


class PropTicketWorkbenchTests(unittest.TestCase):
    def test_daily_double_uses_verified_two_leg_joint_quote(self):
        spec, games, now = fixture('NBA-alts')
        spec.update(parlayStyle='daily-double', odds=-105, legs=spec['legs'][:2])
        self.assertEqual(R.review(spec, games, now)['state'], 'held')
        spec['ticketQuote']['terms'] = R.terms(spec)
        reviewed = R.review(spec, games, now)
        self.assertEqual(reviewed['state'], 'reviewed-private', reviewed['holds'])
        self.assertIn('Daily Double · -105', reviewed['caption'])

    def test_reviewed_nba_ticket_can_use_early_window(self):
        import post_windows
        pick = {'family': 'NBA-alts', 'selectionMethod': R.METHOD}
        kickoff = '2026-11-28T00:00:00Z'
        early = post_windows.private_play_target('NBA', kickoff, pick)
        self.assertEqual(early.isoformat(), '2026-11-27T11:45:00+00:00')
        self.assertEqual(post_windows.private_play_target('NBA', kickoff, {}),
                         post_windows.target('NBA', kickoff))

    def test_college_cross_game_alternates_require_exact_current_quotes(self):
        for style, count, odds in [('daily-double', 2, 114), ('lotto', 7, 511)]:
            spec, games, now = college_fixture(style, count, odds)
            result = R.review(spec, games, now)
            self.assertEqual(result['state'], 'reviewed-private', result['holds'])
            self.assertEqual(R.review(dict(spec, priceEstimated=True), games, now)['state'], 'held')
            below = dict(spec, odds=499 if style == 'lotto' else 116)
            below['ticketQuote'] = dict(spec['ticketQuote'], terms=R.terms(below))
            self.assertEqual(R.review(below, games, now)['state'], 'held')
            spec['legs'][1]['gameId'] = spec['legs'][0]['gameId']
            spec['legs'][1]['review']['availability']['gameId'] = spec['legs'][0]['gameId']
            spec['ticketQuote']['terms'] = R.terms(spec)
            self.assertIn('College alternate tickets require distinct games', R.review(spec, games, now)['holds'])

    def test_first_quarter_requires_exact_joint_price_and_an_all_quarter_ticket(self):
        spec, games, now = fixture('MNF')
        spec.update(parlayStyle='first-quarter', odds=548)
        for leg in spec['legs']:
            leg['period'] = 'first_quarter'
        spec['ticketQuote']['terms'] = R.terms(spec)
        result = R.review(spec, games, now)
        self.assertEqual(result['state'], 'reviewed-private', result)
        self.assertIn('MNF 1Q parlay', result['caption'])
        self.assertIn('1Q ', result['caption'])

        for price, period in ((499, 'first_quarter'), (548, 'full_game')):
            spec['odds'] = price
            spec['legs'][0]['period'] = period
            spec['ticketQuote']['terms'] = R.terms(spec)
            self.assertEqual(R.review(spec, games, now)['state'], 'held')

    def test_long_ticket_keeps_full_name_direction_threshold_and_market(self):
        import parlay_caption
        cases = [('over', 7.5, 'rushYds', 'Daniel Jones O7.5 rush yds'),
                 ('under', 3.5, 'rec', 'Dalton Schultz U3.5 rec')]
        for side, line, market, expected in cases:
            player = expected.rsplit(' ' + side[0].upper(), 1)[0]
            leg = dict(player=player, direction=side, market=market, line=line)
            self.assertEqual(parlay_caption.compact_prop(leg), expected)

    def test_reviewed_families_are_private_and_keep_book_joint_price(self):
        for family in ('MNF', 'TNF', 'NBA-alts'):
            spec, games, now = fixture(family)
            result = R.review(spec, games, now)
            with self.subTest(family=family):
                self.assertEqual(result['state'], 'reviewed-private', result)
                self.assertFalse(result['releaseReady'])
                self.assertEqual(len(result['releaseHolds']), 2)
                self.assertIn('+425 DraftKings', result['caption'])
                self.assertNotIn('chance', result)
                self.assertEqual(len(result['caption'].split('\n\n')[1].splitlines()), 3)
                # Independent leg multiplication yields +237.5, deliberately
                # unlike the observed joint price. The workbench must retain +425.
                self.assertIn('no multiplication', result['jointPriceBasis'])

    def test_exact_receipt_rejects_changed_terms_or_stale_price(self):
        mutations = [lambda s: s.update(odds=500),
                     lambda s: s['legs'][0].update(line=3.5),
                     lambda s: s['legs'][0].update(athleteId='different'),
                     lambda s: s['ticketQuote'].update(checkedAt='2026-11-15T20:00:00Z'),
                     lambda s: s['ticketQuote'].update(source='https://draftkings.com.evil.invalid/'),
                     lambda s: s['ticketQuote'].update(receipt=''),
                     lambda s: s.update(priceEstimated=True)]
        for mutate in mutations:
            spec, games, now = fixture()
            mutate(spec)
            with self.subTest(spec=spec):
                self.assertEqual(R.review(spec, games, now)['state'], 'held')

    def test_unresolved_roles_periods_sources_and_probabilities_hold(self):
        mutations = [lambda s: s['legs'][0]['review']['availability'].update(status='questionable'),
                     lambda s: s['legs'][0]['review'].update(countercase=''),
                     lambda s: s['legs'][0]['review'].update(sources=[]),
                     lambda s: s['legs'][0].update(period='first_quarter'),
                     lambda s: s['legs'][0].update(market='touchdowns'),
                     lambda s: s.update(chance=.75),
                     lambda s: s['legs'][0].update(rawChance=.9),
                     lambda s: s.update(correlationReview={}),
                     lambda s: s['legs'][0].update(mainLine=1.5),
                     lambda s: s.update(riskUnits=1),
                     lambda s: s.update(priceBoosted=True)]
        for mutate in mutations:
            spec, games, now = fixture()
            mutate(spec)
            spec['ticketQuote']['terms'] = R.terms(spec)
            with self.subTest(spec=spec):
                self.assertEqual(R.review(spec, games, now)['state'], 'held')

    def test_game_day_deadline_and_nba_actual_alternate_required(self):
        spec, games, now = fixture('NBA-alts')
        spec['legs'][0]['alternate'] = False
        spec['ticketQuote']['terms'] = R.terms(spec)
        self.assertTrue(any('observed priced alternate' in h for h in R.review(spec, games, now)['holds']))
        spec, games, now = fixture()
        for when in (now + timedelta(hours=4), now + timedelta(days=1)):
            self.assertEqual(R.review(spec, games, when)['state'], 'held')
        spec['family'] = 'TNF'
        self.assertEqual(R.review(spec, games, now)['state'], 'held')

    def test_duplicate_player_and_existing_exposure_are_held(self):
        spec, games, now = fixture()
        first = {'original': {'id': 'original', 'league': 'NFL', 'publishedAt': AT, 'lane': 'best_bet',
                             'gameIds': ['NFL-1'], 'athleteId': '0', 'status': 'active',
                             'expiresAt': (now + timedelta(hours=3)).isoformat()}}
        result = R.review(spec, games, now, first=first)
        self.assertTrue(any('repeated exposure' in h for h in result['holds']), result)
        spec['legs'][1]['athleteId'] = '0'
        self.assertTrue(any('unique named player' in h for h in R.review(spec, games, now)['holds']))

    def test_open_ticket_and_private_reservation_also_hold_repeated_players(self):
        spec, games, now = fixture()
        for existing in ({'legs': [spec['legs'][0]], 'parlayType': 'ladder'},
                         {'legs': [spec['legs'][0]], '_pendingRelease': True}):
            result = R.review(spec, games, now, first={'reserved': existing})
            self.assertTrue(any('already reserves' in h for h in result['holds']), result)

    def test_existing_alternate_frequency_is_not_widened(self):
        spec, games, now = fixture()
        first = {'old': {'league': 'NFL', 'publishedAt': (now-timedelta(days=2)).isoformat(),
                         'legs': [{'alternate': True}], 'parlayType': 'longshot'}}
        result = R.review(spec, games, now, first=first)
        self.assertTrue(any('within seven days' in h for h in result['holds']), result)

    def test_reviewed_nba_next_day_and_tnf_after_mnf_use_daily_limits(self):
        for family, days in (('NBA-alts', 1), ('NBA-alts', 2), ('TNF', 0), ('MNF', 7)):
            spec, games, now = fixture(family, days=days)
            league = R.FAMILIES[family][0]
            first = {'prior': {'league': league, 'publishedAt': (now-timedelta(days=1)).isoformat(),
                              'legs': [{'alternate': True}], 'parlayType': 'longshot',
                              'parlayStyle': 'short', 'result': 'loss'}}
            with self.subTest(family=family, days=days):
                result = R.review(spec, games, now, first=first)
                self.assertEqual(result['state'], 'reviewed-private', result)
                first['prior']['publishedAt'] = (now-timedelta(minutes=20)).isoformat()
                result = R.review(spec, games, now, first=first)
                self.assertTrue(any("already today's short parlay" in h for h in result['holds']), result)

    def test_regular_alts_still_require_current_price_and_available_players(self):
        for mutate in (lambda s: s['ticketQuote'].update(checkedAt=AT),
                       lambda s: s['legs'][0]['review']['availability'].update(status='out'),
                       lambda s: s.update(odds=600)):
            spec, games, now = fixture('NBA-alts', days=1)
            mutate(spec)
            self.assertEqual(R.review(spec, games, now)['state'], 'held')

    def test_health_summary_is_bounded_private_and_contains_no_ticket_secrets(self):
        spec, games, now = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'prop-ticket-reviews'
            path.mkdir()
            (path/'valid.json').write_text(json.dumps(spec))
            (path/'invalid.json').write_text('broken')
            result = R.summary(folder, games, now)
            self.assertEqual(result['counts'], {'reviewed-private': 1, 'held': 0, 'invalid': 1})
            self.assertEqual(result['providerRequests'], 0)
            self.assertFalse(result['releaseReady'])
            self.assertNotIn('synthetic test receipt', json.dumps(result))
            self.assertNotIn('Fixture Player', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
