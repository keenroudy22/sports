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
    latest = {'NFL-2026-W4-a': {'result': 'win'}, 'NFL-2026-W4-b': {'result': 'loss'},
              'NFL-2026-W4-c': {'result': 'loss', 'actual': 'legs: win, loss, win'},
              'NFL-2026-W4-quiet': {'result': 'win'}, 'NFL-2026-W4-t': {'result': 'win'}}
    log = {'posts': [{'id': f'NFL-2026-W4-{k}', 'kind': 'buffer:play', 'sentAt': '2026-09-27T14:00:00Z'} for k in ('a', 'b', 'c', 'm', 't')]
           + [{'id': 'NFL-2026-W4-quiet', 'kind': 'buffer:play', 'cancelledAt': '2026-09-27T13:00:00Z'}]}
    return first, latest, log


MONDAY_MORNING = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)       # Mon 8:30 AM ET


class ReceiptTests(unittest.TestCase):
    def test_long_leftovers_keep_losses_before_wins(self):
        rows = [pick(f'w{i}', 'sun', title=f'Long School Name Number {i} over 149.5 passing yards',
                     athleteId=str(i), market='pass_yds', result='win')
                for i in range(5)]
        rows += [pick('loss', 'sun', title='Long School Name Number Six under 149.5 passing yards',
                      athleteId='six', market='pass_yds', result='loss')]
        text = receipts.fit_result_rows(rows, 'Leftovers: Saturday: 5-1', '#CFB', GAMES)
        self.assertIn('❌ Long School Name Number Six', text)
        self.assertNotIn('✅ Long School Name Number 4', text)
        self.assertIn('wins, 0 losses on card', text)
        self.assertLessEqual(receipts.x_post.tweet_length(text), receipts.x_post.LIMIT)

    def test_accounting_keeps_assumed_prices_and_credits_separate(self):
        rows = [pick('a', 'sun', result='win'), pick('b', 'sun', result='loss', earlyExit=True),
                pick('c', 'sun', result='win', priceAssumed=True)]
        result = receipts.accounting(rows)
        self.assertEqual(result['captured'], '1-1')
        self.assertEqual(result['assumed'], '1-0')
        self.assertEqual(result['promotionalCredits'], 1)

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
        self.assertIn('NFL-2026-W1-leg', receipts.counted(first, {'NFL-2026-W1-leg': {'odds': -115, 'priceAssumed': True}}),
                      'a Week 1 line a later report priced (assumed -115) counts')

    def test_a_receipt_names_the_play_as_its_post_did(self):
        game = {'id': 'g', 'league': 'CFB', 'kickoff': '2026-09-26T22:30Z',
                'away': {'id': '2117', 'short': 'C Michigan', 'abbreviation': 'CMU', 'school': 'Central Michigan'},
                'home': {'id': '2390', 'short': 'Miami', 'abbreviation': 'MIA', 'school': 'Miami'}}
        play = {'id': 'CFB-2026-W4-cmu-mia-under-54-br', 'title': 'C Michigan at Miami under 54', 'marketType': 'total', 'gameIds': ['g']}
        self.assertEqual(receipts.label(play, {'g': game}), 'Central Michigan/Miami (FL) under 54')

    def test_the_morning_after_lists_every_play_with_its_result_and_the_smaller_fun_stake(self):
        first, latest, log = world()
        found = receipts.ready(first, latest, GAMES, log, MONDAY_MORNING)
        self.assertEqual([r['key'] for r in found], ['receipt:day:2026-09-27'])
        sunday = found[0]
        self.assertEqual(sunday['text'], 'Sunday: 2-1.\n'
                                         '✅ Player Seven over 4.5 catches\n❌ Jets/Rams over 44.5\n✅ Bills/Lions over 40.5\n'
                                         '❌ 3-leg parlay · 0.25u · 2/3 legs hit · missed by one leg\n\n#NFL',
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
        self.assertEqual(week['text'], 'The week (Sep 23 to Sep 29): 3-1-1\n'
                                   'Player props 1-0\nGame lines 2-1-1\nFun parlays 0-1 · 0.25u\n\n#NFL')
        self.assertEqual(week['due'].astimezone(gates.EASTERN).strftime('%a %H:%M'), 'Wed 09:00')
        self.assertEqual(week['when'], 'Sep 23 to Sep 29')

    def test_recent_receipt_cards_survive_after_the_posting_window(self):
        first, latest, log = world()
        latest['NFL-2026-W4-m'] = {'result': 'push'}
        wednesday = datetime(2026, 9, 30, 20, 30, tzinfo=timezone.utc)
        cards = {r['card'] for r in receipts.card_history(first, latest, GAMES, wednesday)}
        self.assertIn('receipt-day-2026-09-27', cards)
        self.assertIn('receipt-week-2026-09-29', cards)

    def test_retained_receipt_keeps_the_season_record_from_its_due_time(self):
        first = {
            'early': pick('early', 'sun', publishedAt='2026-09-27T12:00:00Z'),
            'late': pick('late', 'sun', publishedAt='2026-09-27T12:05:00Z'),
        }
        latest = {
            'early': {'result': 'win', 'settledAt': '2026-09-28T12:30:00Z'},
            'late': {'result': 'loss', 'settledAt': '2026-09-28T14:00:00Z'},
        }
        receipt = receipts.day_receipt(datetime(2026, 9, 27).date(), first, latest, GAMES,
                                       set(first), datetime(2026, 10, 6, tzinfo=timezone.utc))
        self.assertEqual(receipt['season'], '1–0', 'a later rebuild cannot advance the retained season headline')

    def test_the_receipt_card_is_the_same_frame(self):
        first, latest, log = world()
        card = pick_card.receipt_svg(receipts.ready(first, latest, GAMES, log, MONDAY_MORNING)[0], avatar='data:image/png;base64,AAAA')
        for needle in ('FINAL REPORT', 'KOOK’N', 'FINAL', 'Sunday, Sep 27', '>2-1<', '>W<', '>L<',
                       'Player Seven over 4.5 catches', 'missed by one leg', 'FUN TICKETS · 0.25U',
                       'clip-path="url(#receiptChef)"', 'KOOK’N RESULTS', '21+ · Entertainment only'):
            self.assertIn(needle, card, needle)
        self.assertNotIn('Confidence', card)

    def test_a_protected_injury_void_is_not_called_a_missed_leg(self):
        ticket = pick('protected', 'sun', parlayType='easyProps', result='win', riskUnits=0.25,
                      actual='legs: win, void, win', odds=255)
        detail = receipts.result_detail(ticket)
        self.assertEqual(detail, '0.25u · 2/2 live legs hit · 1 leg voided')
        self.assertNotIn('missed', detail)

    def test_a_verified_in_game_injury_is_named_on_the_final_receipt(self):
        straight = pick('hurt', 'sun', result='loss', actual='Player Seven: 12 receiving yards',
                        injuryPlayers=['Player Seven'])
        self.assertEqual(receipts.result_detail(straight),
                         'Final: Player Seven: 12 receiving yards · left hurt')
        ticket = pick('hurt-parlay', 'sun', parlayType='easyProps', result='loss', riskUnits=0.25,
                      actual='legs: win, loss, win', injuryPlayers=['Player Seven'])
        self.assertEqual(receipts.result_detail(ticket),
                         'Player Seven left hurt · 0.25u · 2/3 legs hit · missed by one leg')
        card = pick_card.receipt_svg({'title': '0-1', 'when': 'Sunday, Sep 27', 'label': 'YESTERDAY\'S PLATES',
                                      'rows': [('loss', 'Player Seven over 49.5 receiving yards',
                                                receipts.result_detail(straight))]}, avatar='')
        self.assertIn('Final: Player Seven: 12 receiving yards · left hurt', card)

    def test_a_receipt_keeps_a_long_game_total_readable(self):
        receipt = {'title': '5-5', 'when': 'Saturday, Sep 26', 'label': 'YESTERDAY\'S PLATES',
                   'rows': [('loss', 'Central Michigan/Miami (FL) under 53.5')]}
        card = pick_card.receipt_svg(receipt, avatar='')
        self.assertIn('Central Michigan/Miami (FL) under 53.5', card)
        self.assertNotIn('under 53…', card)
        self.assertIn('font-size="22"', card, 'long rows shrink before they are shortened')

    def test_the_receipt_goes_out_at_nine_ahead_of_the_mornings_plays(self):
        first, latest, log = world()
        noon = {'noon': {'id': 'noon', 'league': 'NFL', 'kickoff': '2026-09-28T16:00Z', 'home': {'short': 'A'}, 'away': {'short': 'B'}}}
        first['NFL-2026-W4-n'] = pick('n', 'noon', title='B at A over 40.5')
        log['posts'] = [e for e in log['posts'] if e['id'] != 'NFL-2026-W4-m']         # tonight's play has not gone out yet
        plans = buffer_post.plan(first, latest, dict(GAMES, **noon), MONDAY_MORNING, log)
        got = [(p[0], p[1], p[3].astimezone(gates.EASTERN).strftime('%H:%M'), p[4]) for p in plans]
        self.assertEqual(got[0], ('receipt:day:2026-09-27', 'receipt', '09:01', 'receipt-day-2026-09-27'))
        self.assertNotIn('Today:', plans[0][2])
        self.assertTrue(plans[0][2].startswith('Sunday: 2-1.\n✅ Player Seven'), plans[0][2])
        self.assertEqual(plans[0][2].count('Player Seven'), 1, 'each play once')
        self.assertEqual(got[1][:3], ('NFL-2026-W4-n', 'play', '09:31'), 'the first play follows the receipt')
        self.assertEqual(got[2][:3], ('NFL-2026-W4-m', 'play', '09:51'), 'night games join the same morning batch')
        log['posts'].append({'id': 'receipt:day:2026-09-27', 'kind': 'buffer:receipt'})
        again = [p[0] for p in buffer_post.plan(first, latest, dict(GAMES, **noon), MONDAY_MORNING, log)]
        self.assertFalse([k for k in again if k.startswith(('receipt:', 'menu:'))], 'neither goes out again on its own')
        alone = [p[:2] for p in buffer_post.plan(first, latest, dict(GAMES, **noon), MONDAY_MORNING, log)]
        self.assertFalse(any(kind == 'menu' for _, kind in alone), 'no standalone menu remains')


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
                         '✅ Player Seven over 4.5 catches.\n#NFL\nhttps://x.com/keenkooks/status/20a')
        self.assertTrue(posts['cashed:NFL-2026-W4-c']['text'].startswith('✅ +600 3-leg parlay cashed (DraftKings)\n'))
        self.assertIsNone(posts['cashed:NFL-2026-W4-a']['card'], 'text only: the quoted post carries the card')
        self.assertEqual(receipts.guard(posts['cashed:NFL-2026-W4-a']), [])
        log['posts'][0]['featured'] = True
        self.assertTrue(receipts.cashed(first, latest, GAMES, log, self.SUNDAY_EVENING)[0]['text'].startswith('✅ Player Seven'))

    def test_not_overnight_not_late_and_not_a_play_that_never_went_out(self):
        first, latest, log = self.world()
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)), [], '2 AM: the receipt carries it')
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, self.SUNDAY_EVENING + timedelta(hours=4)), [], 'three hours on, it is old news')
        for entry in log['posts']:
            entry.pop('tweetId')
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, self.SUNDAY_EVENING), [], 'never went out, nothing to quote')

    def test_fresh_morning_win_queues_after_quiet_hours_before_it_expires(self):
        first, latest, log = self.world()
        now = datetime(2026, 9, 28, 10, 45, tzinfo=timezone.utc)
        latest['NFL-2026-W4-a']['settledAt'] = '2026-09-28T10:45:00Z'
        [post] = receipts.cashed(first, latest, GAMES, log, now)
        self.assertEqual(post['due'].astimezone(gates.EASTERN).strftime('%H:%M'), '09:05')
        self.assertLess(post['due'], post['stale'])
        plans = [p for p in buffer_post.plan(first, latest, GAMES, now, log) if p[1] == 'cashed']
        self.assertEqual([p[0] for p in plans], [post['key']])
        self.assertGreaterEqual(plans[0][3], post['due'])
        self.assertLess(plans[0][3], post['stale'])
        log['posts'].append({'id': post['key'], 'kind': 'buffer:cashed'})
        self.assertFalse([p for p in buffer_post.plan(first, latest, GAMES, now, log) if p[1] == 'cashed'])
        latest['NFL-2026-W4-a']['settledAt'] = '2026-09-28T04:30:00Z'
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, now), [], 'expired overnight win stays in the receipt')

    def test_the_planner_sends_it_once_right_away(self):
        first, latest, log = self.world()
        plans = [p for p in buffer_post.plan(first, latest, GAMES, self.SUNDAY_EVENING, log) if p[1] == 'cashed']
        self.assertEqual([(p[0], p[4]) for p in plans], [('cashed:NFL-2026-W4-a', None), ('cashed:NFL-2026-W4-c', None)])
        self.assertLessEqual(plans[0][3] - self.SUNDAY_EVENING, timedelta(minutes=6), 'as it settles, plus bounded jitter')
        log['posts'].append({'id': 'cashed:NFL-2026-W4-a', 'kind': 'buffer:cashed'})
        again = [p[0] for p in buffer_post.plan(first, latest, GAMES, self.SUNDAY_EVENING, log) if p[1] == 'cashed']
        self.assertEqual(again, ['cashed:NFL-2026-W4-c'])


class LadderReceiptTests(unittest.TestCase):
    RUNG = dict(title='Ladder step 2: 2 legs at FanDuel', parlayType='ladder', riskUnits=0.25, odds=95, book='FanDuel',
                legs=[{'title': 'A 40+ receiving yards'}, {'title': 'B 50+ rushing yards'}],
                ladder={'run': 1, 'step': 2, 'stake': 75, 'payout': 146, 'banked': 19, 'bankThisWin': 29,
                        'bankedAfter': 48, 'nextStake': 117, 'totalAfter': 165, 'bankPercent': 20,
                        'ridePercent': 80, 'start': 50, 'goal': 1000})

    def test_a_rung_is_named_by_its_step_and_money_and_kept_off_the_straight_record(self):
        rung = pick('l', 'sun', **self.RUNG, result='win')
        self.assertEqual(receipts.label(rung), '80/20 Climb step 2 ($75 → $146)')
        straight = pick('s', 'sun', result='loss')
        self.assertEqual(receipts.headline([rung, straight]), '0-1', 'the ladder is not a straight play')
        self.assertEqual(receipts.headline([rung]), '80/20 Climb 1-0')
        self.assertIn(('80/20 Climb', '1-0'), receipts.by_kind([rung, straight]))

    def test_a_cashed_rung_names_the_next_step_and_the_top_of_the_ladder_says_so(self):
        head, body = receipts.ladder_cashed(pick('l', 'sun', **self.RUNG))
        self.assertEqual((head, body), ('Step 2 cashed ✅ $146 back.', '$29 to the bank, $117 rides on step 3.'))
        top = dict(self.RUNG, ladder=dict(self.RUNG['ladder'], step=5, stake=675, payout=850, banked=150,
                                          bankThisWin=170, bankedAfter=320, nextStake=680, totalAfter=1000))
        head, body = receipts.ladder_cashed(pick('l', 'sun', **top))
        self.assertEqual((head, body), ('🪜 80/20 Climb complete: $50 → $1,000 in 5 steps', '$320 banked along the way.'))

    def test_an_overnight_ladder_win_queues_a_morning_result_card_instead_of_expiring(self):
        rung = pick('ladder', 'sun', **self.RUNG)
        rung['id'] = 'NFL-2026-W4-ladder'
        first = {rung['id']: rung}
        latest = {rung['id']: {'result': 'win', 'settledAt': '2026-09-28T04:00:00Z'}}
        log = {'posts': [{'id': rung['id'], 'kind': 'buffer:play', 'tweetId': '123'}]}
        morning_run = datetime(2026, 9, 28, 10, 45, tzinfo=timezone.utc)  # 6:45 AM ET
        [post] = receipts.cashed(first, latest, GAMES, log, morning_run)
        self.assertEqual(post['card'], 'ladder-result-NFL-2026-W4-ladder')
        self.assertEqual(post['due'].astimezone(gates.EASTERN).strftime('%H:%M'), '09:05')
        self.assertGreater(post['stale'], post['due'])
        self.assertIn('$117 rides on step 3', post['text'])
        [card] = receipts.ladder_result_cards(first, latest, morning_run)
        self.assertEqual(card['card'], post['card'])
        self.assertEqual(card['pick']['result'], 'win')

    def test_a_ladder_loss_waits_for_final_or_leftovers(self):
        rung = pick('ladder', 'sun', **self.RUNG)
        rung['id'] = 'NFL-2026-W4-ladder-loss'
        first = {rung['id']: rung}
        latest = {rung['id']: {'result': 'loss', 'actual': 'legs: win, loss',
                               'settledAt': '2026-09-28T01:00:00Z'}}
        log = {'posts': [{'id': rung['id'], 'kind': 'buffer:play', 'tweetId': '123'}]}
        now = datetime(2026, 9, 28, 1, 15, tzinfo=timezone.utc)
        self.assertEqual(receipts.cashed(first, latest, GAMES, log, now), [])


class DailyTests(unittest.TestCase):
    def test_the_book_fills_an_empty_evening_and_only_then(self):
        first, latest, log = world()
        tuesday_evening = datetime(2026, 9, 29, 21, 30, tzinfo=timezone.utc)      # Tue 5:30 PM ET
        post = receipts.book(first, latest, GAMES, log, tuesday_evening)
        self.assertEqual(post['text'].split('\n')[:2], ['Season through Sep 28: 3-1', 'Player props 1-0'])
        wednesday = receipts.book(first, latest, GAMES, log, tuesday_evening + timedelta(days=1))
        self.assertNotEqual(wednesday['text'], post['text'], 'a quiet day after a quiet day never repeats the same post')
        self.assertIn('Player props 1-0\nGame lines 2-1\nFun parlays 0-1 · 0.25u', post['text'])
        self.assertEqual(post['text'].count('0.25u'), 1, 'only the fun ticket names its smaller stake')
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
