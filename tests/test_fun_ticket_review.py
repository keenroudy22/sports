import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fun_ticket_review as review
import gates
import run

NOW = datetime(2026, 11, 13, 16, 10, tzinfo=timezone.utc)


def fixture(count=3, style='short'):
    games = {}
    legs = []
    price = -200 if style == 'short' else -150
    for index in range(count):
        game_id = f'g{index}'
        kickoff = f'2026-11-13T2{index}:00:00Z' if index < 4 else '2026-11-13T23:30:00Z'
        games[game_id] = {'id': game_id, 'league': 'CFB', 'season': 2026, 'week': 11,
                          'state': 'pre', 'kickoff': kickoff,
                          'home': {'short': f'Home{index}'}, 'away': {'short': f'Away{index}'}}
        legs.append({'id': f'l{index}', 'title': f'Home{index} +4.5', 'gameId': game_id,
                     'marketType': 'spread', 'direction': 'home', 'line': 4.5, 'mainLine': -3.5,
                     'marketWindow': 'Full game', 'alternate': True, 'odds': price,
                     'book': 'DraftKings', 'observedAt': '2026-11-13T16:05:00Z',
                     'kickoff': kickoff, 'source': 'https://sportsbook.draftkings.com/leagues/football/ncaaf',
                     'researchCase': {'why': 'Current matchup and role support the cushion.',
                         'risk': 'Turnovers can erase the cushion.',
                         'availability': 'Current team availability reviewed; no guarantee.',
                         'sources': [{'url': 'https://example.edu/news/preview',
                                     'fact': 'The current starter is listed in the preview.',
                                     'checkedAt': '2026-11-13T16:00:00Z'}]}})
    decimal = 1.0
    for _ in legs:
        decimal *= 1 + 100 / abs(price)
    odds = round((decimal - 1) * 100)
    spec = {'book': 'DraftKings', 'odds': odds, 'parlayStyle': style, 'legs': legs,
            'quotedAt': '2026-11-13T16:05:00Z',
            'researchReview': {'method': review.METHOD, 'reviewer': 'kookn-desk',
                'reviewedAt': '2026-11-13T16:06:00Z', 'ticketVerified': True,
                'ticketSource': 'https://sportsbook.draftkings.com/leagues/football/ncaaf',
                'receipt': 'Private screenshot with exact legs and combined price.'}}
    return spec, SimpleNamespace(now=NOW, games=games)


class FunTicketReviewTests(unittest.TestCase):
    def test_exact_short_ticket_becomes_reviewed_candidate_without_ev_claim(self):
        spec, ctx = fixture()
        pick, held = review.candidate(ctx, NOW, spec)
        self.assertIsNone(held)
        self.assertEqual((pick['parlayStyle'], pick['quoteType'], pick['priceEstimated']),
                         ('short', 'sportsbook', False))
        self.assertEqual(pick['ticketReceipt'], spec['researchReview']['receipt'])
        self.assertNotIn('chance', pick)
        self.assertIn('No validated win probability', pick['edge'])
        run.write_prose(pick, ctx, [])
        self.assertIn('Current matchup', pick['why'])
        self.assertIn('Every leg must hit', pick['risk'])
        self.assertTrue(gates.longshot_exact_ticket(pick, ctx).ok)

    def test_exact_six_leg_lotto_has_its_own_shape(self):
        spec, ctx = fixture(6, 'lotto')
        pick, held = review.candidate(ctx, NOW, spec)
        self.assertIsNone(held)
        self.assertEqual((len(pick['legs']), pick['parlayStyle']), (6, 'lotto'))
        self.assertTrue(gates.longshot_shape(pick, ctx).ok)

    def test_estimated_wrong_shape_same_game_and_missing_research_are_held(self):
        mutations = (
            lambda spec: spec.update(odds=999),
            lambda spec: spec.update(parlayStyle='lotto'),
            lambda spec: spec['legs'][1].update(gameId='g0'),
            lambda spec: spec['legs'][0]['researchCase'].update(risk=''),
            lambda spec: spec['researchReview'].update(receipt=''),
            lambda spec: spec['researchReview'].update(ticketSource='https://draftkings.com.evil.invalid/'),
            lambda spec: spec['legs'][0].update(mainLine=5.5),
        )
        for mutate in mutations:
            spec, ctx = fixture()
            mutate(spec)
            with self.subTest(spec=spec):
                self.assertIsNotNone(review.refusal(dict(spec, gameIds=[leg['gameId'] for leg in spec['legs']],
                                                         parlayType='longshot'), ctx))

    def test_release_rechecks_review_and_exact_price(self):
        spec, ctx = fixture()
        pick, _ = review.candidate(ctx, NOW, spec)
        row = {'pick': pick, 'league': 'CFB', 'discordSentAt': 'already'}
        self.assertIsNone(run.private_release_refusal(row, ctx, NOW))
        changed = copy.deepcopy(row)
        changed['pick']['researchReview']['ticketVerified'] = False
        self.assertIsNotNone(run.private_release_refusal(changed, ctx, NOW))
        changed = copy.deepcopy(row)
        changed['pick']['priceEstimated'] = True
        self.assertIsNotNone(run.private_release_refusal(changed, ctx, NOW))


if __name__ == '__main__':
    unittest.main()
