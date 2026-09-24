import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post
import gates
import pick_card
import receipts

GAMES = {'sun': {'id': 'sun', 'league': 'NFL', 'kickoff': '2026-09-27T17:00Z', 'home': {'short': 'Lions'}, 'away': {'short': 'Bills'}},     # Sun 1:00 PM ET
         'sun2': {'id': 'sun2', 'league': 'NFL', 'kickoff': '2026-09-27T20:25Z', 'home': {'short': 'Rams'}, 'away': {'short': 'Jets'}},
         'mon': {'id': 'mon', 'league': 'NFL', 'kickoff': '2026-09-29T00:15Z', 'home': {'short': 'Chiefs'}, 'away': {'short': 'Colts'}},   # Mon 8:15 PM ET
         'thu': {'id': 'thu', 'league': 'NFL', 'kickoff': '2026-09-25T00:15Z', 'home': {'short': 'Eagles'}, 'away': {'short': 'Giants'}}}  # Thu 8:15 PM ET


def pick(key, game, **over):
    base = {'id': f'NFL-2026-W4-{key}', 'title': f'{key} over 44.5', 'status': 'active', 'modelLean': True, 'favorite': False,
            'marketType': 'total', 'line': 44.5, 'direction': 'over', 'gameIds': [game], 'book': 'DraftKings', 'odds': -110,
            'projection': 48.0, 'publishedAt': '2026-09-20T12:00:00Z'}
    base.update(over)
    return base


def world():
    first = {p['id']: p for p in (
        pick('a', 'sun', title='Player Seven over 4.5 receptions', athleteId='7', market='rec', odds=100),
        pick('b', 'sun2', title='Jets at Rams over 44.5'),
        pick('c', 'sun', title='3-leg parlay', legs=[{'title': 'x'}, {'title': 'y'}, {'title': 'z'}], parlayType='longshot', riskUnits=0.25, odds=600),
        pick('quiet', 'sun', title='Not posted over 40.5'),
        pick('m', 'mon', title='Colts at Chiefs under 47.5', direction='under'),
        pick('t', 'thu', title='Giants at Eagles over 41.5'))}
    latest = {'NFL-2026-W4-a': {'result': 'win'}, 'NFL-2026-W4-b': {'result': 'loss'}, 'NFL-2026-W4-c': {'result': 'loss'},
              'NFL-2026-W4-quiet': {'result': 'win'}, 'NFL-2026-W4-t': {'result': 'win'}}
    log = {'posts': [{'id': f'NFL-2026-W4-{k}', 'kind': 'buffer:play', 'sentAt': '2026-09-27T14:00:00Z'} for k in ('a', 'b', 'c', 'm', 't')]
           + [{'id': 'NFL-2026-W4-quiet', 'kind': 'buffer:play', 'cancelledAt': '2026-09-27T13:00:00Z'}]}
    return first, latest, log


MONDAY_MORNING = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)       # Mon 8:30 AM ET


class ReceiptTests(unittest.TestCase):
    def test_only_plays_that_went_out_count(self):
        first, latest, log = world()
        log['posts'].append({'id': 'NFL-2026-W4-b', 'kind': 'buffer:play', 'sentAt': 'x', 'deletedAt': 'y'})
        self.assertEqual(receipts.served({'posts': log['posts'][:1]}), {'NFL-2026-W4-a'})
        self.assertNotIn('NFL-2026-W4-quiet', receipts.served(log), 'a cancelled post was never served')
        hand = {'posts': [{'id': 'CFB-2026-W3-hand', 'kind': 'pick', 'postedAt': '2026-09-19T12:30:00Z', 'tweetId': None}]}
        self.assertEqual(receipts.served(hand), {'CFB-2026-W3-hand'}, 'a play posted by hand counts in the book')

    def test_a_receipt_names_the_play_as_its_post_did(self):
        game = {'id': 'g', 'league': 'CFB', 'kickoff': '2026-09-26T22:30Z',
                'away': {'id': '2117', 'short': 'C Michigan', 'abbreviation': 'CMU', 'school': 'Central Michigan'},
                'home': {'id': '2390', 'short': 'Miami', 'abbreviation': 'MIA', 'school': 'Miami'}}
        play = {'id': 'CFB-2026-W4-cmu-mia-under-54-br', 'title': 'C Michigan at Miami under 54', 'marketType': 'total', 'gameIds': ['g']}
        self.assertEqual(receipts.label(play, {'g': game}), 'Central Michigan at Miami (FL) under 54')

    def test_the_morning_after_lists_every_served_play_with_its_result(self):
        first, latest, log = world()
        found = receipts.ready(first, latest, GAMES, log, MONDAY_MORNING)
        self.assertEqual([r['key'] for r in found], ['receipt:day:2026-09-27'])
        sunday = found[0]
        self.assertEqual(sunday['text'], '🍳 RECEIPTS · SUNDAY\n1-2 · -0.25u\n\n'
                                         '✅ Player Seven over 4.5 receptions\n❌ Jets at Rams over 44.5\n❌ 3-leg parlay\n\n'
                                         'Graded in public, win or lose.\n#NFL')
        self.assertEqual(sunday['due'].astimezone(gates.EASTERN).strftime('%a %H:%M'), 'Mon 09:00')
        self.assertEqual(sunday['card'], 'receipt-day-2026-09-27')
        self.assertEqual(receipts.guard(sunday), [])

    def test_not_until_every_served_play_is_settled_and_not_after_the_evening(self):
        first, latest, log = world()
        del latest['NFL-2026-W4-b']
        self.assertEqual(receipts.ready(first, latest, GAMES, log, MONDAY_MORNING), [], 'one play still open')
        first, latest, log = world()
        late = datetime(2026, 9, 29, 0, 30, tzinfo=timezone.utc)              # Mon 8:30 PM ET
        self.assertEqual(receipts.ready(first, latest, GAMES, log, late), [], 'too late to be yesterday')

    def test_wednesday_adds_the_week_by_kind(self):
        first, latest, log = world()
        latest['NFL-2026-W4-m'] = {'result': 'push'}
        wednesday = datetime(2026, 9, 30, 12, 30, tzinfo=timezone.utc)        # Wed 8:30 AM ET
        found = {r['key']: r for r in receipts.ready(first, latest, GAMES, log, wednesday)}
        self.assertEqual(sorted(found), ['receipt:week:2026-09-29'])
        week = found['receipt:week:2026-09-29']
        self.assertEqual(week['text'], '🍳 RECEIPTS · THE WEEK\n2-2-1 · +0.66u\n\n'
                                       'Player props 1-0 · +1.00u\nTeam props 1-1-1 · -0.09u\nParlays 0-1 · -0.25u\n\n'
                                       'Graded in public, win or lose.\n#NFL')
        self.assertEqual(week['due'].astimezone(gates.EASTERN).strftime('%a %H:%M'), 'Wed 09:00')
        self.assertEqual(week['when'], 'Sep 23 to Sep 29')

    def test_the_receipt_card_is_the_same_frame(self):
        first, latest, log = world()
        card = pick_card.receipt_svg(receipts.ready(first, latest, GAMES, log, MONDAY_MORNING)[0], avatar='data:image/png;base64,AAAA')
        for needle in ('RECEIPTS', 'KOOK’N', 'YESTERDAY’S PLATES', 'Sunday, Sep 27', '1-2 · -0.25u', '>W<', '>L<',
                       'Player Seven over 4.5 receptions', 'clip-path="url(#plate)"', 'Graded in public', 'Entertainment only. Not advice.'):
            self.assertIn(needle, card, needle)
        self.assertNotIn('Confidence', card)

    def test_the_receipt_goes_out_at_nine_ahead_of_the_mornings_plays(self):
        first, latest, log = world()
        noon = {'noon': {'id': 'noon', 'league': 'NFL', 'kickoff': '2026-09-28T16:00Z', 'home': {'short': 'A'}, 'away': {'short': 'B'}}}
        first['NFL-2026-W4-n'] = pick('n', 'noon', title='B at A over 40.5')
        log['posts'] = [e for e in log['posts'] if e['id'] != 'NFL-2026-W4-m']         # tonight's play has not gone out yet
        plans = buffer_post.plan(first, latest, dict(GAMES, **noon), MONDAY_MORNING, log)
        got = [(p[0], p[1], p[3].astimezone(gates.EASTERN).strftime('%H:%M'), p[4]) for p in plans]
        self.assertEqual(got[0][:3], ('menu:day:2026-09-28', 'menu', '08:45'))
        self.assertEqual(got[1], ('receipt:day:2026-09-27', 'receipt', '09:00', 'receipt-day-2026-09-27'))
        self.assertEqual(got[2][:3], ('NFL-2026-W4-n', 'play', '09:10'))
        self.assertEqual(got[3][:3], ('NFL-2026-W4-m', 'play', '17:15'), 'the Monday night play three hours out')
        log['posts'].append({'id': 'receipt:day:2026-09-27', 'kind': 'buffer:receipt'})
        self.assertNotIn('receipt:day:2026-09-27', [p[0] for p in buffer_post.plan(first, latest, dict(GAMES, **noon), MONDAY_MORNING, log)])


class DailyTests(unittest.TestCase):
    def test_the_menu_names_the_games_and_times_never_the_side(self):
        first, latest, log = world()
        first['NFL-2026-W4-m2'] = pick('m2', 'mon', title='Player Nine OVER 60.5 receiving yards', athleteId='9', market='recYds')
        post = receipts.menu(first, latest, GAMES, log, MONDAY_MORNING)
        self.assertEqual(post['text'], "🍳 TODAY'S MENU\n2 plates on the stove today:\n• Colts at Chiefs, 8:15 PM\n\n"
                                       'Each one drops three hours before kickoff.\n#NFL')
        self.assertNotIn('under', post['text'].lower())
        self.assertNotIn('Nine', post['text'], 'the player is not named before his post')
        self.assertEqual(post['due'].astimezone(gates.EASTERN).strftime('%H:%M'), '08:45')
        self.assertIsNone(receipts.menu(first, latest, GAMES, log, datetime(2026, 9, 29, 12, 30, tzinfo=timezone.utc)), 'no plays, no menu')

    def test_a_busy_saturday_menu_is_not_refused_as_one_long_sentence(self):
        text = ("🍳 TODAY'S MENU\n6 plates on the stove today:\n• Iowa at Michigan, 3:30 PM\n• Oklahoma at Georgia, 3:30 PM\n"
                "• UConn at Miami (OH), 3:30 PM\n• James Madison at Old Dominion, 6:00 PM\nand 2 more on the site\n\n"
                "Each one drops three hours before kickoff.\n#CFB")
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_the_book_fills_an_empty_evening_and_only_then(self):
        first, latest, log = world()
        tuesday_evening = datetime(2026, 9, 29, 21, 30, tzinfo=timezone.utc)      # Tue 5:30 PM ET
        post = receipts.book(first, latest, GAMES, log, tuesday_evening)
        self.assertEqual(post['text'].split('\n')[:2], ['🍳 THE BOOK', 'Season: 2-2 · +0.66u'])
        self.assertIn('Player props 1-0 · +1.00u', post['text'])
        self.assertEqual(post['due'].astimezone(gates.EASTERN).strftime('%a %H:%M'), 'Tue 18:00')
        self.assertIsNone(receipts.book(first, latest, GAMES, log, datetime(2026, 9, 29, 14, 0, tzinfo=timezone.utc)), 'not before 5 PM')
        busy = dict(log, posts=log['posts'] + [{'id': 'r', 'kind': 'buffer:receipt', 'dueAt': '2026-09-29T13:00:00Z'}])
        self.assertIsNone(receipts.book(first, latest, GAMES, busy, tuesday_evening), 'the day already had a post')
        self.assertIsNone(receipts.book(first, latest, GAMES, {'posts': []}, tuesday_evening), 'nothing served, nothing to show')
        only = {'posts': [p for p in log['posts'] if p['id'] == 'NFL-2026-W4-a']}
        lone = receipts.book(first, latest, GAMES, only, tuesday_evening)['text']
        self.assertEqual(lone.count('1-0'), 1, 'one kind of play: no line repeating the season')


if __name__ == '__main__':
    unittest.main()
