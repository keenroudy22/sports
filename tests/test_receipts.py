import sys
import unittest
from datetime import datetime, timedelta, timezone
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
        self.assertEqual(receipts.served(hand), {'CFB-2026-W3-hand'}, 'a play posted by hand went out')

    def test_one_record_counts_every_published_play_whether_or_not_it_went_out(self):
        first, _, _ = world()
        first['NFL-2026-W1-leg'] = pick('leg', 'sun', historicalImport=True, odds=None)
        first['NFL-2026-W1-priced'] = pick('priced', 'sun', historicalImport=True)
        ids = receipts.counted(first)
        self.assertIn('NFL-2026-W4-quiet', ids, 'pulled before its post went out: still in the record, graded as posted')
        self.assertNotIn('NFL-2026-W1-leg', ids, 'the Week 1 legs imported without a price are kept apart')
        self.assertIn('NFL-2026-W1-priced', ids)

    def test_a_receipt_names_the_play_as_its_post_did(self):
        game = {'id': 'g', 'league': 'CFB', 'kickoff': '2026-09-26T22:30Z',
                'away': {'id': '2117', 'short': 'C Michigan', 'abbreviation': 'CMU', 'school': 'Central Michigan'},
                'home': {'id': '2390', 'short': 'Miami', 'abbreviation': 'MIA', 'school': 'Miami'}}
        play = {'id': 'CFB-2026-W4-cmu-mia-under-54-br', 'title': 'C Michigan at Miami under 54', 'marketType': 'total', 'gameIds': ['g']}
        self.assertEqual(receipts.label(play, {'g': game}), 'Central Michigan at Miami (FL) under 54')

    def test_the_morning_after_lists_every_play_with_its_result_and_no_units(self):
        first, latest, log = world()
        found = receipts.ready(first, latest, GAMES, log, MONDAY_MORNING)
        self.assertEqual([r['key'] for r in found], ['receipt:day:2026-09-27'])
        sunday = found[0]
        self.assertEqual(sunday['text'], '🍳 RECEIPTS · SUNDAY\n2-1\n\n'
                                         '✅ Player Seven over 4.5 receptions\n❌ Jets at Rams over 44.5\n✅ Not posted over 40.5\n'
                                         '❌ 3-leg fun parlay\n\nGraded in public, win or lose.\n#NFL',
                         'the record is the straight plays; the fun parlay is listed but not counted in it')
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
        self.assertEqual(week['text'], '🍳 RECEIPTS · THE WEEK\nSep 23 to Sep 29: 3-1-1\n\n'
                                       'Player props 1-0\nTeam props 2-1-1\nFun parlays 0-1\n\n'
                                       'Graded in public, win or lose.\n#NFL')
        self.assertEqual(week['due'].astimezone(gates.EASTERN).strftime('%a %H:%M'), 'Wed 09:00')
        self.assertEqual(week['when'], 'Sep 23 to Sep 29')

    def test_the_receipt_card_is_the_same_frame(self):
        first, latest, log = world()
        card = pick_card.receipt_svg(receipts.ready(first, latest, GAMES, log, MONDAY_MORNING)[0], avatar='data:image/png;base64,AAAA')
        for needle in ('RECEIPTS', 'KOOK’N', 'YESTERDAY’S PLATES', 'Sunday, Sep 27', '>2-1<', '>W<', '>L<',
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
        self.assertEqual(got[0], ('receipt:day:2026-09-27+menu:day:2026-09-28', 'receipt', '09:00', 'receipt-day-2026-09-27'),
                         'one morning post: the receipt carries the menu')
        self.assertIn('Today: 2 plates on the stove. Pick of the Day goes out around noon.', plans[0][2])
        self.assertTrue(plans[0][2].startswith('🍳 RECEIPTS · SUNDAY\n2-1\n\n✅ Player Seven'), plans[0][2])
        self.assertEqual(got[1][:3], ('NFL-2026-W4-n', 'play', '10:00'), 'a noon kickoff posts two hours ahead')
        self.assertEqual(got[2][:3], ('NFL-2026-W4-m', 'play', '12:00'), 'the Monday night play goes out at midday')
        log['posts'].append({'id': 'receipt:day:2026-09-27+menu:day:2026-09-28', 'kind': 'buffer:receipt'})
        again = [p[0] for p in buffer_post.plan(first, latest, dict(GAMES, **noon), MONDAY_MORNING, log)]
        self.assertFalse([k for k in again if k.startswith(('receipt:', 'menu:'))], 'neither goes out again on its own')
        log['posts'][-1] = {'id': 'receipt:day:2026-09-27', 'kind': 'buffer:receipt'}
        alone = [p[:2] for p in buffer_post.plan(first, latest, dict(GAMES, **noon), MONDAY_MORNING, log)]
        self.assertIn(('menu:day:2026-09-28', 'menu'), alone, 'a receipt that already went out leaves the menu to go alone')


class CashedTests(unittest.TestCase):
    """A win that went out on X gets its own post as it settles, quoting the original; losses wait for the receipt."""
    SUNDAY_EVENING = datetime(2026, 9, 27, 22, 0, tzinfo=timezone.utc)          # Sun 6:00 PM ET

    def world(self):
        first, latest, log = world()
        latest['NFL-2026-W4-a'] = {'result': 'win', 'settledAt': '2026-09-27T21:30:00Z'}
        latest['NFL-2026-W4-b'] = {'result': 'loss', 'settledAt': '2026-09-27T21:30:00Z'}
        latest['NFL-2026-W4-c'] = {'result': 'win', 'settledAt': '2026-09-27T21:30:00Z'}
        for entry in log['posts']:
            entry['tweetId'] = f"20{entry['id'][-1]}"
        return first, latest, log

    def test_a_win_that_went_out_is_cashed_with_its_post_quoted(self):
        first, latest, log = self.world()
        posts = {p['key']: p for p in receipts.cashed(first, latest, GAMES, log, self.SUNDAY_EVENING)}
        self.assertEqual(sorted(posts), ['cashed:NFL-2026-W4-a', 'cashed:NFL-2026-W4-c'], 'wins only; the loss waits for the receipt')
        self.assertEqual(posts['cashed:NFL-2026-W4-a']['text'],
                         '✅ CASHED\nPlayer Seven over 4.5 receptions\n+100 at DraftKings\n\n#NFL\nhttps://x.com/keenkooks/status/20a')
        self.assertTrue(posts['cashed:NFL-2026-W4-c']['text'].startswith('✅ FUN PARLAY CASHED\n3 legs · +600 at DraftKings'))
        self.assertIsNone(posts['cashed:NFL-2026-W4-a']['card'], 'text only: the quoted post carries the card')
        self.assertEqual(receipts.guard(posts['cashed:NFL-2026-W4-a']), [])
        log['posts'][0]['featured'] = True
        self.assertTrue(receipts.cashed(first, latest, GAMES, log, self.SUNDAY_EVENING)[0]['text'].startswith('✅ PICK OF THE DAY CASHED'))

    def test_not_overnight_not_late_and_not_a_play_that_never_went_out(self):
        first, latest, log = self.world()
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)), [], '2 AM: the receipt carries it')
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, self.SUNDAY_EVENING + timedelta(hours=4)), [], 'three hours on, it is old news')
        for entry in log['posts']:
            entry.pop('tweetId')
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, self.SUNDAY_EVENING), [], 'never went out, nothing to quote')

    def test_the_planner_sends_it_once_right_away(self):
        first, latest, log = self.world()
        plans = [p for p in buffer_post.plan(first, latest, GAMES, self.SUNDAY_EVENING, log) if p[1] == 'cashed']
        self.assertEqual([(p[0], p[4]) for p in plans], [('cashed:NFL-2026-W4-a', None), ('cashed:NFL-2026-W4-c', None)])
        self.assertLessEqual(plans[0][3] - self.SUNDAY_EVENING, timedelta(minutes=5), 'as it settles, not the next morning')
        log['posts'].append({'id': 'cashed:NFL-2026-W4-a', 'kind': 'buffer:cashed'})
        again = [p[0] for p in buffer_post.plan(first, latest, GAMES, self.SUNDAY_EVENING, log) if p[1] == 'cashed']
        self.assertEqual(again, ['cashed:NFL-2026-W4-c'])


class DailyTests(unittest.TestCase):
    def test_the_menu_names_the_games_and_times_never_the_side(self):
        first, latest, log = world()
        first['NFL-2026-W4-m2'] = pick('m2', 'mon', title='Player Nine OVER 60.5 receiving yards', athleteId='9', market='recYds')
        post = receipts.menu(first, latest, GAMES, log, MONDAY_MORNING)
        self.assertEqual(post['text'], "🍳 TODAY'S MENU\n2 plates on the stove today:\n• Colts at Chiefs, 8:15 PM\n\n"
                                       'Pick of the Day and the rest go out around noon.\n#NFL')
        self.assertNotIn('under', post['text'].lower())
        self.assertNotIn('Nine', post['text'], 'the player is not named before his post')
        self.assertEqual(post['due'].astimezone(gates.EASTERN).strftime('%H:%M'), '08:45')
        self.assertIsNone(receipts.menu(first, latest, GAMES, log, datetime(2026, 9, 29, 12, 30, tzinfo=timezone.utc)), 'no plays, no menu')

    def test_a_busy_saturday_menu_is_not_refused_as_one_long_sentence(self):
        text = ("🍳 TODAY'S MENU\n6 plates on the stove today:\n• Iowa at Michigan, 3:30 PM\n• Oklahoma at Georgia, 3:30 PM\n"
                "• UConn at Miami (OH), 3:30 PM\n• James Madison at Old Dominion, 6:00 PM\nand 2 more on the site\n\n"
                "Pick of the Day and the rest go out around noon.\n#CFB")
        self.assertEqual(receipts.guard({'text': text}), [])

    def test_the_book_fills_an_empty_evening_and_only_then(self):
        first, latest, log = world()
        tuesday_evening = datetime(2026, 9, 29, 21, 30, tzinfo=timezone.utc)      # Tue 5:30 PM ET
        post = receipts.book(first, latest, GAMES, log, tuesday_evening)
        self.assertEqual(post['text'].split('\n')[:2], ['🍳 THE BOOK', 'Season through Sep 28: 3-1'])
        wednesday = receipts.book(first, latest, GAMES, log, tuesday_evening + timedelta(days=1))
        self.assertNotEqual(wednesday['text'], post['text'], 'a quiet day after a quiet day never repeats the same post')
        self.assertIn('Player props 1-0\nTeam props 2-1\nFun parlays 0-1', post['text'])
        self.assertNotIn('u\n', post['text'].replace('\n\n', '\n'), 'no units anywhere')
        self.assertEqual(post['due'].astimezone(gates.EASTERN).strftime('%a %H:%M'), 'Tue 18:00')
        self.assertIsNone(receipts.book(first, latest, GAMES, log, datetime(2026, 9, 29, 14, 0, tzinfo=timezone.utc)), 'not before 5 PM')
        busy = dict(log, posts=log['posts'] + [{'id': 'r', 'kind': 'buffer:receipt', 'dueAt': '2026-09-29T13:00:00Z'}])
        self.assertIsNone(receipts.book(first, latest, GAMES, busy, tuesday_evening), 'the day already had a post')
        self.assertIsNone(receipts.book(first, {}, GAMES, {'posts': []}, tuesday_evening), 'nothing settled, nothing to show')
        only = {k: v for k, v in first.items() if k == 'NFL-2026-W4-a'}
        lone = receipts.book(only, latest, GAMES, {'posts': []}, tuesday_evening)['text']
        self.assertEqual(lone.count('1-0'), 1, 'one kind of play: no line repeating the season')


if __name__ == '__main__':
    unittest.main()
