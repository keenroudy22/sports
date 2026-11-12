import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import betslips


NOW = datetime(2026, 11, 12, 17, tzinfo=timezone.utc)


def pick(**changes):
    row = {'id': 'NFL-test', 'title': 'Saquon Barkley over 72.5 rushing yards',
           'displayTitle': 'Saquon Barkley over 72.5 rushing yards', 'book': 'DraftKings',
           'odds': -110, 'line': 72.5, 'direction': 'over', 'market': 'rushYds',
           'gameId': 'NFL-1', 'gameIds': ['NFL-1'], 'kickoff': '2026-11-13T01:15:00Z',
           'status': 'active'}
    row.update(changes)
    return row


class FakeClient:
    def __init__(self, results):
        self.results = list(results)
        self.submitted = []

    def submit(self, text):
        self.submitted.append(text)
        return '00000000-0000-4000-8000-000000000001'

    def status(self, request_id):
        return self.results.pop(0)


class BetslipTests(unittest.TestCase):
    def test_parlay_prompt_keeps_every_leg_and_forbids_substitution(self):
        row = pick(id='parlay', odds=450, legs=[{'title': 'Eagles moneyline'}, {'title': 'Over 44.5'}])
        text = betslips.prompt_for(row)
        self.assertIn('exact DraftKings parlay', text)
        self.assertIn('1. Eagles moneyline', text)
        self.assertIn('2. Over 44.5', text)
        self.assertIn('Do not substitute', text)
        self.assertNotIn('$', text)

    def test_only_full_same_book_match_becomes_public(self):
        row = pick(id='parlay', legs=['Eagles moneyline', 'Over 44.5'])
        response = {'status': 'Complete', 'betSlips': [
            {'book': 'FanDuel', 'legsRequested': 2, 'legsMatched': 2,
             'deepLink': 'https://example.com/fd', 'betslipBets': [{}, {}]},
            {'book': 'DraftKings', 'legsRequested': 2, 'legsMatched': 1,
             'deepLink': 'https://example.com/partial', 'betslipBets': [{}]},
        ]}
        with self.assertRaises(betslips.BetslipError):
            betslips.complete_result(response, row)
        response['betSlips'][1].update(legsMatched=2, deepLink='https://www.gambly.com/deeplink/slip/ok',
                                       betslipBets=[{'description': 'Eagles ML'}, {'description': 'Over 44.5'}])
        result = betslips.complete_result(response, row, '2026-11-12T17:00:00Z')
        self.assertEqual((result['book'], result['legsMatched']), ('DraftKings', 2))
        self.assertEqual(result['url'], 'https://www.gambly.com/deeplink/slip/ok')

    def test_public_link_requires_current_selection_fingerprint(self):
        row = pick()
        ready = betslips.complete_result({'status': 'Complete', 'betSlips': [{
            'book': 'DraftKings', 'legsRequested': 1, 'legsMatched': 1,
            'deepLink': 'https://www.gambly.com/deeplink/slip/one', 'betslipBets': [{'points': 72.5}],
        }]}, row, '2026-11-12T17:00:00Z')
        store = {'slips': {row['id']: ready}}
        self.assertEqual(betslips.public_for(row, NOW, store)['url'], ready['url'])
        self.assertIsNone(betslips.public_for({**row, 'line': 73.5}, NOW, store))
        self.assertIsNone(betslips.public_for({**row, 'result': 'win'}, NOW, store))

    def test_refresh_resumes_pending_and_writes_only_safe_public_result(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder) / 'betslips.json'
            pending = Path(folder) / 'pending.json'
            client = FakeClient([
                {'status': 'Processing'},
                {'status': 'Complete', 'shareUrl': 'https://www.gambly.com/share/one', 'betSlips': [{
                    'book': 'DraftKings', 'legsRequested': 1, 'legsMatched': 1, 'overallOdds': -108,
                    'deepLink': 'https://www.gambly.com/deeplink/slip/one',
                    'betslipBets': [{'description': 'Saquon over 72.5', 'points': 72.5, 'odds': -108}],
                }]},
            ])
            result = betslips.refresh_pick(pick(), NOW, client, store, pending, deadline=5, sleeper=lambda _: None)
            self.assertEqual(result['state'], 'ready')
            public = json.loads(store.read_text())
            saved = public['slips']['NFL-test']
            self.assertNotIn('requestId', json.dumps(public))
            self.assertEqual(saved['legsMatched'], saved['legsRequested'])
            self.assertEqual(len(client.submitted), 1)
            self.assertEqual(json.loads(pending.read_text())['requests'], {})

    def test_bad_or_credentialed_urls_never_publish(self):
        self.assertIsNone(betslips.safe_url('http://gambly.com/a'))
        self.assertIsNone(betslips.safe_url('https://user:secret@gambly.com/a'))
        self.assertIsNone(betslips.safe_url('https://localhost/a'))
        self.assertEqual(betslips.safe_url('https://gambly.com/a'), 'https://gambly.com/a')


if __name__ == '__main__':
    unittest.main()
