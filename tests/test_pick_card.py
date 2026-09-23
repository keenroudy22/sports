import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pick_card

PICK = {'id': 'CFB-2026-W5-iowa-michigan-under-38-5-fd', 'title': 'Iowa at Michigan under 38.5', 'favorite': True,
        'book': 'FanDuel', 'odds': -105, 'projection': 31.2, 'line': 38.5, 'confidence': 6}
GAME = {'kickoff': '2026-09-26T19:30Z', 'home': {'short': 'Michigan'}, 'away': {'short': 'Iowa'}}


class CardTests(unittest.TestCase):
    def test_the_svg_carries_the_picks_fields_and_escapes_markup(self):
        text = pick_card.svg(PICK, GAME, {'wins': 3, 'losses': 1, 'units': 1.98})
        for needle in ('Iowa at Michigan under 38.5', '-105', 'FanDuel', 'Our number 31.2', 'line 38.5', 'FAVORITE',
                       'Iowa at Michigan', 'Sat 3:30 PM ET', 'Record 3-1', '+1.98u', 'Confidence 6 of 10', 'keenroudy.com/sports'):
            self.assertIn(needle, text, needle)
        nasty = pick_card.svg(dict(PICK, title='A&M <script> under 40', book='B&B'))
        self.assertIn('A&amp;M &lt;script&gt; under 40', nasty)
        self.assertNotIn('<script>', nasty)
        self.assertIn('MODEL LEAN', pick_card.svg(dict(PICK, favorite=False, modelLean=True)))

    def test_long_titles_are_trimmed(self):
        text = pick_card.svg(dict(PICK, title='A very long pick title that would never fit on one line of a card'))
        self.assertIn('…', text)

    @unittest.skipUnless(os.environ.get('KEENROUDY_CARD_LIVE') == '1' and pick_card.chrome_path(), 'needs a browser and KEENROUDY_CARD_LIVE=1')
    def test_render_makes_a_png_with_the_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            out = pick_card.render(pick_card.svg(PICK, GAME), Path(folder) / 'card.png')
            self.assertGreater(out.stat().st_size, 10_000)
            self.assertEqual(out.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')


if __name__ == '__main__':
    unittest.main()
