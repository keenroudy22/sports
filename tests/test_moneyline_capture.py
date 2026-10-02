import unittest
from scripts import refresh


class MoneylineCaptureTests(unittest.TestCase):
    def test_same_provider_current_moneylines_only(self):
        event = {'id': '1', 'date': '2026-10-04T17:00:00Z', 'season': {'year': 2026, 'type': 2},
                 'status': {'type': {'state': 'pre', 'description': 'Scheduled'}},
                 'competitions': [{'competitors': [
                     {'homeAway': side, 'team': {'id': side, 'displayName': side}}
                     for side in ('home', 'away')], 'odds': [
                         {'provider': {'displayName': 'DraftKings'}, 'moneyline': {
                             'home': {'close': {'odds': '+160'}, 'open': {'odds': '+200'}},
                             'away': {'close': {'odds': '-192'}}}},
                         {'provider': {'displayName': 'Other'}, 'moneyline': {'home': {'close': {'odds': '+180'}}}}]}]}
        market = refresh.normalize(event, 'NFL')['market']
        self.assertEqual((market['provider'], market['homeML'], market['awayML']), ('DraftKings', '+160', '-192'))
        del event['competitions'][0]['odds'][0]['moneyline']['away']['close']
        self.assertIsNone(refresh.normalize(event, 'NFL')['market']['awayML'])
