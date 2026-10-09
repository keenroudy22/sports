import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tnf_early_look as early
import research_posts


NOW = datetime(2026, 10, 7, 21, 30, tzinfo=timezone.utc)  # Wednesday 5:30 PM ET
GAME = {'id': 'NFL-tnf', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-09T00:15:00Z',
        'away': {'name': 'Buccaneers'}, 'home': {'name': 'Cowboys'}}


def line(name='Cade Otton over 3.5 receptions', *, ident='one', odds=105, edge=3.0):
    return {'id': ident, 'title': name, 'gameId': GAME['id'], 'league': 'NFL', 'state': 'open',
            'marketWindow': 'Full game', 'book': 'DraftKings', 'odds': odds, 'line': 3.5,
            'athleteId': ident, 'observedAt': '2026-10-07T21:00:00Z',
            'grade': {'calibrated': True, 'thin': False, 'limited': False, 'tier': 'pass',
                      'chance': .53, 'needs': .488, 'edge': edge,
                      'snapshotAt': '2026-10-07T21:00:00Z'}}


class TnfEarlyLookTests(unittest.TestCase):
    def test_wednesday_night_requires_two_fresh_lines_and_uses_thursday_cap(self):
        result = early.select({'games': [GAME]}, [line(), line('Ryan Flournoy over 3.5 receptions', ident='two', edge=5.0)], NOW)
        self.assertEqual([row['id'] for row in result['rows']], ['two', 'one'])
        self.assertEqual(result['key'], 'research:tnf-early:2026-10-08')
        self.assertEqual(result['due'].astimezone(early.gates.EASTERN).hour, 19)
        self.assertIn('Buccaneers/Cowboys early numbers:', early.caption(result))
        self.assertNotIn('Best bets drop tomorrow.', early.caption(result))
        self.assertIsNone(early.select({'games': [GAME]}, [line()], NOW))

    def test_role_price_staleness_and_nonpublic_books_cannot_enter(self):
        good = line()
        second = line(ident='second')
        bad_role = dict(line(ident='held'), roleSuspect=True, grade=None, gradeNote='Projection under review')
        bad_price = line(ident='wild', odds=1800)
        bad_book = dict(line(ident='hardrock'), book='hardrockbet')
        stale = dict(line(ident='old'), observedAt='2026-10-07T18:00:00Z')
        thin = line(ident='thin')
        thin['grade']['thin'] = True
        result = early.select({'games': [GAME]}, [good, second, bad_role, bad_price, bad_book, stale, thin], NOW)
        self.assertEqual({row['id'] for row in result['rows']}, {'one', 'second'})

    def test_only_wednesday_night_before_the_window(self):
        rows = [line(), line(ident='second')]
        self.assertIsNone(early.select({'games': [GAME]}, rows, datetime(2026, 10, 8, 21, tzinfo=timezone.utc)))
        self.assertIsNone(early.select({'games': [GAME]}, rows, datetime(2026, 10, 7, 23, 11, tzinfo=timezone.utc)))

    def test_review_cards_use_research_label_and_no_helpline(self):
        rows = [line(), line(ident='two'), line(ident='three'), line(ident='four')]
        result = early.select({'games': [GAME]}, rows, NOW)
        for builder in (early.list_card, early.spotlight_card):
            svg = builder(result, fetch=lambda url: None).svg()
            self.assertIn('TNF EARLY LOOK', svg)
            self.assertIn('RESEARCH', svg)
            self.assertNotIn('1-800-', svg)

    def test_post_stays_off_until_review_and_counts_against_thursday_research(self):
        rows = [line(), line(ident='two')]
        with patch.object(research_posts, 'load', return_value={'games': [GAME]}), \
                patch.object(research_posts, 'load_lines', return_value=rows), \
                patch.object(research_posts, 'details_for', return_value={}), \
                patch.object(research_posts, 'teams_for', return_value={}):
            self.assertIsNone(research_posts.post({}, NOW))
            with patch.object(early, 'ENABLED', True):
                post = research_posts.post({}, NOW)
        self.assertEqual(post['key'], 'research:tnf-early:2026-10-08')
        self.assertEqual(post['kind'], 'research')
        self.assertEqual(post['countsFor'].isoformat(), '2026-10-08')
        self.assertNotIn('@Playbook', post['text'])
        self.assertTrue(research_posts.already_posted({'posts': [{'id': post['key']}]},
                                                       datetime(2026, 10, 8, tzinfo=timezone.utc).date()))
        self.assertFalse(research_posts.already_posted({'posts': [{'id': 'research:season:2026-10-07'}]},
                                                        post['countsFor']))


if __name__ == '__main__':
    unittest.main()
