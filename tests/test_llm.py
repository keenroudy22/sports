import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import llm
import llm_tasks


def completion(text):
    return json.dumps({'message': {'content': text}}).encode()


def chat(payload):
    return completion(json.dumps(payload))


class ClientTests(unittest.TestCase):
    def test_draft_returns_the_text_with_thinking_off_and_stripped(self):
        sent = {}

        def send(url, body, headers, timeout):
            sent.update(url=url, body=body)
            return completion('<think>hmm</think>\nOur number likes the over.')
        self.assertEqual(llm.draft('sys', 'user', send=send, model='m', base='http://x'), 'Our number likes the over.')
        self.assertEqual(sent['url'], 'http://x/api/chat')
        self.assertEqual(sent['body']['model'], 'm')
        self.assertFalse(sent['body']['think'])
        self.assertEqual(sent['body']['options']['num_predict'], 400)
        self.assertEqual(sent['body']['messages'][0]['role'], 'system')

    def test_unreachable_and_malformed_raise(self):
        def refused(url, body, headers, timeout):
            raise llm.LLMUnavailable('connection refused')
        with self.assertRaises(llm.LLMUnavailable):
            llm.draft('s', 'u', send=refused)
        with self.assertRaises(llm.LLMUnavailable):
            llm.draft('s', 'u', send=lambda *a: b'not json')
        with self.assertRaises(llm.LLMUnavailable):
            llm.draft('s', 'u', send=lambda *a: completion(''))

    def test_draft_json_constrains_and_parses(self):
        sent = {}

        def send(url, body, headers, timeout):
            sent.update(url=url, body=body)
            return chat({'argues_against': True, 'confidence': 'high', 'fact_ids': ['f1'], 'note': 'qb out'})
        out = llm.draft_json('s', 'u', llm_tasks.JUDGE_SCHEMA, send=send, base='http://x')
        self.assertTrue(out['argues_against'])
        self.assertEqual(sent['url'], 'http://x/api/chat')
        self.assertEqual(sent['body']['format'], llm_tasks.JUDGE_SCHEMA)
        self.assertFalse(sent['body']['think'])
        with self.assertRaises(llm.LLMUnavailable):
            llm.draft_json('s', 'u', {}, send=lambda *a: json.dumps({'message': {'content': 'nope'}}).encode())


PICK = {'id': 'NFL-2026-W4-buf-det-over-44-5-dk', 'title': 'Bills at Lions over 44.5', 'line': 44.5, 'odds': -110,
        'projection': 48.0, 'confidence': 3, 'book': 'DraftKings',
        'edge': 'v2 total 48.0 (80% range 32.6 to 63.4). Chance of over 44.5: 55.3% (raw 62.7% shrunk), against 52.4% break-even at -110: +2.9 points, +0.055u per unit.',
        'why': 'Model lean, published on our number alone. Our total is 48 against 44.5: the over reads 55.3% after the raw 62.7% is shrunk by the model\'s record against the close, +2.9 points clear of the 52.4% that -110 needs.',
        'sources': ['https://www.espn.com/nfl/game/_/gameId/401872932'],
        '_desk': {'chance': 0.553, 'rawChance': 0.627, 'breakEven': 0.524, 'edgePoints': 2.9, 'evPerUnit': 0.055}}


class TaskTests(unittest.TestCase):
    def test_polish_keeps_a_clean_rewrite(self):
        text, note = llm_tasks.why_for(PICK, send=lambda *a: completion('Our total is 48 against 44.5. The over reads 55.3%, 2.9 points clear of what -110 needs.'))
        self.assertEqual(note, 'polished')
        self.assertIn('55.3%', text)

    def test_polish_falls_back_to_the_template_after_two_failed_tries(self):
        calls = []

        def send(url, body, headers, timeout):
            calls.append(body['messages'][1]['content'])
            return completion('A lock at 61.2% — hammer it.')
        text, note = llm_tasks.why_for(PICK, send=send)
        self.assertEqual(text, PICK['why'])
        self.assertTrue(note.startswith('template kept'))
        self.assertEqual(len(calls), 2)
        self.assertIn('previous attempt failed', calls[1])

    def test_polish_survives_an_unavailable_model(self):
        def down(*a):
            raise llm.LLMUnavailable('down')
        text, note = llm_tasks.risk_for(dict(PICK, risk='Rests on the model alone. Confidence 3 of 10.'), send=down)
        self.assertEqual(text, 'Rests on the model alone. Confidence 3 of 10.')
        self.assertIn('unavailable', note)

    def test_judge_drops_unknown_fact_ids_and_downgrades_an_unsupported_against(self):
        facts = [{'id': 'f1', 'claim': 'QB1 is Doubtful', 'source': 'https://x'}]
        verdict = llm_tasks.judge_against(PICK, facts, send=lambda *a: chat({'argues_against': True, 'confidence': 'high', 'fact_ids': ['f1', 'ghost'], 'note': 'qb'}))
        self.assertEqual(verdict['fact_ids'], ['f1'])
        self.assertEqual(verdict['confidence'], 'high')
        weak = llm_tasks.judge_against(PICK, facts, send=lambda *a: chat({'argues_against': True, 'confidence': 'high', 'fact_ids': [], 'note': 'feel'}))
        self.assertEqual(weak['confidence'], 'low')
        self.assertIsNone(llm_tasks.judge_against(PICK, facts, send=lambda *a: chat({'argues_against': 'maybe', 'confidence': 'high', 'fact_ids': [], 'note': ''})))

        def down(*a):
            raise llm.LLMUnavailable('down')
        self.assertIsNone(llm_tasks.judge_against(PICK, facts, send=down))


if __name__ == '__main__':
    unittest.main()
