import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import llm

PICK = {'line': 44.5, 'odds': -110, 'projection': 48.0, 'confidence': 3,
        'edge': 'Chance of over 44.5: 55.3% (raw 62.7%), against 52.4% break-even at -110: +2.9 points, +0.055u per unit.',
        'sources': ['https://www.espn.com/nfl/game/_/gameId/401872932']}


class StyleTests(unittest.TestCase):
    def test_a_clean_text_passes(self):
        self.assertEqual(llm.check_style('Our total is 48 against 44.5. The over reads 55.3%. Confidence 3 of 10.'), [])

    def test_dashes_fail(self):
        self.assertTrue(any('dash' in p for p in llm.check_style('Our number likes the over — by a lot.')))
        self.assertTrue(any('dash' in p for p in llm.check_style('A 2024–25 record.')))

    def test_model_and_version_names_fail(self):
        self.assertTrue(any('version' in p for p in llm.check_style('v2 total 48.0 says over.')))
        self.assertTrue(any('model' in p for p in llm.check_style('Qwen thinks the over hits.')))

    def test_marketing_and_advice_fail(self):
        self.assertTrue(any('marketing' in p for p in llm.check_style('Lock of the week.')))
        self.assertTrue(any('marketing' in p for p in llm.check_style('Hammer the over.')))
        self.assertTrue(any('advice' in p for p in llm.check_style('You should bet this now.')))
        self.assertTrue(any('exclamation' in p for p in llm.check_style('Big game!')))
        self.assertTrue(any('emoji' in p for p in llm.check_style('Over 44.5 \U0001F525')))

    def test_long_sentences_fail(self):
        self.assertTrue(any('sentence' in p for p in llm.check_style('word ' * 60 + '.')))


class NumbersGuardTests(unittest.TestCase):
    def test_numbers_in_normalizes(self):
        self.assertEqual(llm.numbers_in('over 44.50 at -110, a 2-7 week, 55.3%'), {'44.5', '110', '2', '7', '55.3'})
        self.assertEqual(llm.numbers_in('see https://www.espn.com/nfl/game/_/gameId/401872932 now'), set())

    def test_every_number_in_the_text_must_come_from_the_material(self):
        ok, strays = llm.numbers_ok('Our total is 48 against 44.5, 2.9 points clear of what -110 needs. Confidence 3 of 10.', PICK)
        self.assertTrue(ok, strays)
        ok, strays = llm.numbers_ok('The over hits 61.2% of the time and the total is 48.', PICK)
        self.assertFalse(ok)
        self.assertEqual(strays, ['61.2'])

    def test_extra_material_extends_the_allowed_set(self):
        fact = {'claim': 'Kentucky lists 5 out including two corners'}
        self.assertFalse(llm.numbers_ok('Kentucky has 5 out.', PICK)[0])
        self.assertTrue(llm.numbers_ok('Kentucky has 5 out.', PICK, [fact])[0])

    def test_signs_and_percent_do_not_matter(self):
        self.assertTrue(llm.numbers_ok('at +110 or -110, 55.3 percent', PICK)[0])


@unittest.skipUnless(os.environ.get('KEENROUDY_LLM_LIVE') == '1', 'set KEENROUDY_LLM_LIVE=1 to run against Ollama')
class LiveTests(unittest.TestCase):
    """Three fixed prompts against the running model; each answer must pass both guards."""

    def test_live_polish_passes_the_guards(self):
        import llm_tasks
        self.assertTrue(llm.available(), 'Ollama is not running')
        pick = dict(PICK, why='Model lean, published on our number alone. Our total is 48 against 44.5: the over reads 55.3% '
                               'after the raw 62.7% is shrunk by the model\'s record against the close, +2.9 points clear of the '
                               '52.4% that -110 needs. Nothing sourced argues against it; the number is the reason.')
        for _ in range(3):
            text, note = llm_tasks.why_for(pick)
            self.assertEqual(llm_tasks.guarded(text, pick), [], text)


if __name__ == '__main__':
    unittest.main()
