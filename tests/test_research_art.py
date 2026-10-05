import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research_art


class ResearchArtTests(unittest.TestCase):
    def test_histogram_is_aggregate_not_a_fake_game_sequence(self):
        text = research_art.history_strip({'hits': 8, 'games': 10, 'pushes': 1}, 72, 500)
        tree = ET.fromstring(text)
        bars = {row.get('data-outcome'): float(row.get('width')) for row in tree.findall('rect')}
        self.assertEqual(bars, {'hit': 576, 'miss': 72, 'push': 72})
        self.assertIn('8 hit · 1 missed · 1 pushed', text)
        self.assertIn('not game order or a forecast', text)
        self.assertIn('#50edbb', text)
        self.assertIn('#ff7987', text)

    def test_unknown_or_invalid_counts_never_make_a_bar(self):
        for row in ({}, {'hits': 4, 'games': 5}, {'hits': 6, 'games': 5, 'pushes': 0},
                    {'hits': 5, 'games': 5, 'pushes': 1}, {'hits': True, 'games': 5, 'pushes': 0},
                    {'hits': 0, 'games': 0, 'pushes': 0}):
            self.assertEqual(research_art.history_strip(row, 0, 0), '')

    def test_layout_grows_for_history_without_covering_exact_counts(self):
        row = {'title': 'Example Player', 'price': 'Under 40.5 receiving yards',
               'metric': '8/10 this season · 80% historical', 'detail': '2026 regular season',
               'hits': 8, 'games': 10, 'pushes': 0}
        choice = {'title': 'SEASON TRENDS', 'kicker': 'EXACT MAIN LINES', 'accent': '#50edbb',
                  'rows': [row] * 4}
        svg = research_art.svg(choice)
        root = ET.fromstring(svg)
        self.assertEqual(svg.count('data-history="aggregate"'), 4)
        self.assertEqual(svg.count('8/10 this season'), 4)
        self.assertGreater(int(root.get('height')), 1350)
        self.assertIn('Under 40.5 receiving yards', svg)


if __name__ == '__main__':
    unittest.main()
