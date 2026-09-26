import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import line_timing as lt

OVER = {'direction': 'over', 'marketType': 'total'}
UNDER = {'direction': 'under', 'marketType': 'total'}
SIDE = {'direction': 'home', 'marketType': 'spread'}


class PriceTests(unittest.TestCase):
    def test_cents_are_counted_across_even_money(self):
        self.assertEqual(lt.cents(-110) - lt.cents(-120), 10)
        self.assertEqual(lt.cents(105) - lt.cents(-105), 10, '-105 to +105 is ten cents')
        self.assertEqual(lt.cents(110) - lt.cents(100), 10)

    def test_which_way_is_worse_depends_on_the_side(self):
        self.assertEqual(lt.moved_against(OVER, (51.5, -105), (52.5, -105)), (1.0, None), 'a higher total hurts an over')
        self.assertEqual(lt.moved_against(UNDER, (51.5, -105), (52.5, -105)), (-1.0, None), 'and helps an under')
        self.assertEqual(lt.moved_against(SIDE, (-10.0, -110), (-11.0, -110)), (1.0, None), 'laying more points hurts a side')
        self.assertEqual(lt.moved_against(OVER, (38.5, -105), (38.5, -115)), (0.0, 10), 'the same number at a worse price')

    def test_the_verdict_uses_half_a_point_or_ten_cents(self):
        self.assertEqual(lt.verdict(0.5, None), 'worse')
        self.assertEqual(lt.verdict(0.0, 10), 'worse')
        self.assertEqual(lt.verdict(0.0, 4), 'about the same')
        self.assertEqual(lt.verdict(-0.5, None), 'better')
        self.assertEqual(lt.verdict(0.0, -10), 'better')


class TimingTests(unittest.TestCase):
    def test_the_post_time_is_the_real_one_or_the_rule(self):
        kickoff = datetime(2026, 9, 26, 19, 30, tzinfo=timezone.utc)                 # Sat 3:30 PM ET
        self.assertEqual(lt.post_time({'sentAt': '2026-09-26T16:00:05Z'}, kickoff), (gates.when('2026-09-26T16:00:05Z'), 'posted'))
        self.assertEqual(lt.post_time({'dueAt': '2026-09-26T16:10:00Z'}, kickoff)[1], 'scheduled')
        rule, kind = lt.post_time(None, kickoff)
        self.assertEqual((rule.astimezone(gates.EASTERN).strftime('%a %H:%M'), kind), ('Sat 12:00', 'rule'))
        early, _ = lt.post_time(None, datetime(2026, 9, 26, 16, 0, tzinfo=timezone.utc))   # a noon kickoff
        self.assertEqual(early.astimezone(gates.EASTERN).strftime('%H:%M'), '10:00', 'two hours ahead of an early game')

    def test_the_summary_says_what_the_rule_says(self):
        row = lambda v: {'atPost': {'verdict': v, 'points': 1.0 if v == 'worse' else 0.0}}
        self.assertIn('Post earlier', lt.summary([row('worse'), row('worse'), row('about the same')])['says'])
        self.assertIn('Noon is fine', lt.summary([row('worse'), row('better'), row('about the same')])['says'])
        self.assertIn('Nothing to measure yet', lt.summary([{}])['says'])

    def test_a_post_still_to_come_is_not_measured(self):
        pick = {'id': 'CFB-x', 'title': 'Iowa at Michigan over 38.5', 'line': 38.5, 'odds': -105, 'book': 'ESPN BET',
                'direction': 'over', 'marketType': 'total', 'gameIds': ['g'], 'publishedAt': '2026-09-23T11:21:00Z', 'league': 'CFB'}
        now = datetime(2026, 9, 26, 2, 0, tzinfo=timezone.utc)                        # Friday night, before Saturday's noon post
        ctx = SimpleNamespace(first={'CFB-x': pick}, games={'g': {'kickoff': '2026-09-26T19:30Z'}}, odds={}, prop_odds={})
        stores = SimpleNamespace(as_of=lambda moment: ctx)
        [row] = lt.measure(stores, now, log_book={'posts': []})
        self.assertNotIn('atPost', row)
        self.assertEqual(row['postKind'], 'rule')


if __name__ == '__main__':
    unittest.main()
