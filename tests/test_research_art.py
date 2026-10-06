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

    def test_compact_x_layout_keeps_exact_counts_without_repeating_player_art(self):
        row = {'title': 'Example Player', 'price': 'Under 40.5 receiving yards',
               'metric': '8/10 this season · 80% historical', 'detail': '2026 regular season',
               'hits': 8, 'games': 10, 'pushes': 0}
        choice = {'title': 'SEASON TRENDS', 'kicker': 'EXACT MAIN LINES', 'accent': '#50edbb',
                  'rows': [row] * 4}
        svg = research_art.svg(choice, {0: 'data:image/png;base64,TEST', 1: 'data:image/png;base64,TEST'})
        root = ET.fromstring(svg)
        self.assertEqual(svg.count('data-history="aggregate"'), 0, 'four-row cards stay compact instead of faking tiny bars')
        self.assertEqual(svg.count('8/10 this season'), 4)
        self.assertEqual((int(root.get('width')), int(root.get('height'))), (1200, 675))
        self.assertEqual(svg.count('<image'), 1, 'one portrait is a hero, never repeated beside the same line')
        self.assertIn('Under 40.5 receiving yards', svg)

    def test_single_line_is_the_visual_hero_and_retains_aggregate_history(self):
        row = {'title': 'Landry Lyddy under 215.5 passing yards', 'price': '-114 FD',
               'metric': '8/10 last games', 'detail': 'Projection 145.3 | exact main line',
               'hits': 8, 'games': 10, 'pushes': 0}
        svg = research_art.svg({'title': 'MATCHUP MENU', 'kicker': 'EXACT-LINE HISTORY',
                                'accent': '#6fc2f0', 'rows': [row]}, {0: 'data:image/png;base64,TEST'})
        self.assertEqual(svg.count('<image'), 1)
        self.assertIn('font-size="40"', svg)
        self.assertIn('font-size="50"', svg)
        self.assertIn('data-history="aggregate"', svg)


if __name__ == '__main__':
    unittest.main()
