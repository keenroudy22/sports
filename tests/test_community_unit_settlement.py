import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import community_unit_settlement as unit
import community_record as record
import receipts
import ticket_card
import buffer_post
from prop_ticket_settlement import identity


def fixture():
    now = datetime(2026, 11, 17, 4, tzinfo=timezone.utc)
    ticket = {'id': 'community:personal-ticket:synthetic', 'league': 'NFL', 'kind': 'parlays',
              'title': 'Synthetic quarter ticket', 'book': 'DraftKings', 'riskUnits': .25,
              'odds': 168, 'kickoff': '2026-11-17T01:15:00Z', 'legs': []}
    for i, line in enumerate((4.5, 19.5)):
        ticket['legs'].append({'gameId': 'NFL-synthetic', 'athleteId': str(i),
            'player': 'Synthetic Player '+str(i), 'market': 'rushYds', 'direction': 'over',
            'line': line, 'period': '1Q', 'book': ticket['book'], 'kickoff': ticket['kickoff'],
            'milestone': line+.5,
            'title': 'Synthetic quarter rushing yards'})
    post = {'id': ticket['id'], 'sentAt': '2026-11-17T01:00:00Z',
            'link': 'https://x.com/synthetic/status/123456789'}
    evidence = {'original': {'ticket': copy.deepcopy(ticket), 'checkedAt': '2026-11-17T00:50:00Z',
                   'quoteReceipt': 'Private synthetic book quote; not real evidence',
                   'quoteSource': 'https://sportsbook.draftkings.com/synthetic'},
        'checkedAt': now.isoformat(), 'differentBookDecisionKnown': False,
        'rules': {'verified': True, 'book': ticket['book'], 'jurisdiction': 'IN',
                  'source': 'https://sportsbook.draftkings.com/synthetic-rules',
                  'checkedAt': now.isoformat(), 'ruleVersion': 'synthetic-test',
                  'receipt': 'Private synthetic rules; not real book rules',
                  **{k: 'Synthetic reviewed rule used only by this test fixture.'
                     for k in ('participation', 'period', 'earlyExit', 'pushVoid')}},
        'legs': [{'terms': identity(leg), 'final': True, 'completedPeriod': '1Q',
                  'source': 'https://www.espn.com/synthetic-final', 'checkedAt': now.isoformat(),
                  'participation': 'played', 'injuryReview': 'clear', 'actual': 25, 'result': 'win'}
                 for leg in ticket['legs']]}
    return ticket, evidence, [post], now


class CommunityUnitSettlementTests(unittest.TestCase):
    def test_exact_published_allocation_is_not_a_cash_receipt(self):
        ticket, evidence, posts, now = fixture()
        result, held = unit.review(ticket, evidence, posts, now)
        self.assertIsNone(held)
        self.assertEqual(result['units'], .42)
        self.assertEqual(result['settlementBasis'], unit.BASIS)
        self.assertNotIn('Private synthetic', json.dumps(result))
        self.assertNotIn('returnDollars', result)
        self.assertEqual(result['settlementLegResults'], ['win', 'win'])
        self.assertIn('25 rushing yards (1Q; win)', result['actual'])
        evidence['legs'][1].update(actual=15, result='loss')
        result, held = unit.review(ticket, evidence, posts, now)
        self.assertIsNone(held)
        self.assertEqual(result['units'], -.25)
        public = dict(ticket, **result)
        self.assertTrue(receipts.has_fun_final(public))
        self.assertIn('missed by one leg', receipts.result_detail(public))

    def test_no_assumed_stake_or_after_the_fact_ticket(self):
        ticket, evidence, posts, now = fixture()
        for value in (None, 0, True, 1, .5):
            changed = copy.deepcopy(ticket); changed['riskUnits'] = value
            self.assertIsNone(unit.review(changed, evidence, posts, now)[0])
        for change in ({'sentAt': now.isoformat()}, {'link': None}, {'cancelledAt': now.isoformat()}):
            self.assertIsNone(unit.review(ticket, evidence, [dict(posts[0], **change)], now)[0])
        self.assertIsNone(unit.review(ticket, evidence, [], now)[0])
        changed = copy.deepcopy(ticket); changed['odds'] = 200
        self.assertIsNone(unit.review(changed, evidence, posts, now)[0])

    def test_period_final_actual_and_identity_are_required(self):
        ticket, evidence, posts, now = fixture()
        for change in ({'completedPeriod': 'full_game'}, {'final': False}, {'actual': None},
                       {'actual': True}, {'actual': 4.2}, {'result': 'loss'},
                       {'participation': 'did-not-play'}, {'injuryReview': 'unknown'},
                       {'source': ''}, {'terms': {}}, {'checkedAt': '2026-11-17T01:00:00Z'}):
            bad = copy.deepcopy(evidence); bad['legs'][0].update(change)
            self.assertIsNone(unit.review(ticket, bad, posts, now)[0], change)
        for field in ('checkedAt',):
            bad = copy.deepcopy(evidence);bad[field] = (now+timedelta(seconds=1)).isoformat()
            self.assertIsNone(unit.review(ticket, bad, posts, now)[0])
        self.assertIsNone(unit.review(ticket, dict(evidence, legs=[]), posts, now)[0])

    def test_void_protection_and_missing_rules_hold_instead_of_inventing_return(self):
        ticket, evidence, posts, now = fixture()
        for change in ({'differentBookDecisionKnown': True}, {'differentBookDecisionKnown': None},
                       {'cashout': True}, {'paidProtection': True}, {'reducedQuote': {'odds': 110}},
                       {'bookAdjusted': True}, {'rules': {}}):
            self.assertIsNone(unit.review(ticket, dict(evidence, **change), posts, now)[0])
        bad = copy.deepcopy(evidence);bad['legs'][0]['result'] = 'void'
        self.assertIsNone(unit.review(ticket, bad, posts, now)[0])
        bad = copy.deepcopy(evidence);bad['rules']['jurisdiction'] = 'different'
        self.assertIsNone(unit.review(ticket, bad, posts, now)[0])

    def test_full_game_nba_and_nfl_retain_exact_period(self):
        for league, market in (('NFL', 'recYds'), ('NBA', 'pts')):
            ticket, evidence, posts, now = fixture()
            ticket['league'] = league
            for leg, row in zip(ticket['legs'], evidence['legs']):
                leg.update(period='full_game', market=market)
                row.update(terms=identity(leg), completedPeriod='full_game')
            evidence['original']['ticket'] = copy.deepcopy(ticket)
            self.assertIsNone(unit.review(ticket, evidence, posts, now)[1])
            evidence['legs'][0]['completedPeriod'] = '1Q'
            self.assertIsNone(unit.review(ticket, evidence, posts, now)[0])

    def test_append_is_private_deduplicated_and_corrections_preserve_history(self):
        ticket, evidence, posts, now = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'public'; private = Path(folder)/'private'
            (root/'data').mkdir(parents=True)
            original = json.dumps({'tickets': [ticket]})
            (root/'data/community.json').write_text(original)
            (root/'data/x-posted.json').write_text(json.dumps({'posts': posts}))
            result, added = unit.append(ticket['id'], evidence, now, root=root, private=private)
            self.assertTrue(added)
            self.assertFalse(unit.append(ticket['id'], evidence, now, root=root, private=private)[1])
            journal = private/'community-unit-results.jsonl'
            self.assertEqual(journal.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(journal.read_text().splitlines()), 1)
            self.assertEqual(record.source_privacy_issues(root), [])
            row = record.build(root)[0]
            self.assertEqual(row['units'], .42)
            self.assertTrue(receipts.has_fun_final(row))
            self.assertEqual(row['card'], 'data/cards/'+receipts.result_card_key(row)+'.png')
            self.assertNotIn('Private synthetic', (root/'data/community-settlements.jsonl').read_text())
            correction = copy.deepcopy(evidence)
            correction['checkedAt'] = (now+timedelta(minutes=1)).isoformat()
            correction['legs'][1].update(actual=15, result='loss')
            unit.append(ticket['id'], correction, now+timedelta(minutes=1), root=root, private=private)
            self.assertEqual(record.build(root)[0]['units'], -.25)
            self.assertEqual(len(journal.read_text().splitlines()), 2)
            self.assertEqual((root/'data/community.json').read_text(), original)
            # An old retry cannot undo the correction or create a third append.
            unit.append(ticket['id'], evidence, now+timedelta(minutes=2), root=root, private=private)
            self.assertEqual(record.build(root)[0]['units'], -.25)
            bad = copy.deepcopy(evidence);bad['legs'][0]['actual'] = 30
            with self.assertRaisesRegex(ValueError, 'later verified review'):
                unit.append(ticket['id'], bad, now+timedelta(minutes=2), root=root, private=private)

    def test_public_projection_rejects_tampered_return_and_private_fields(self):
        ticket, evidence, posts, now = fixture()
        result, _ = unit.review(ticket, evidence, posts, now)
        for change in ({'settlementBasis': 'cash'}, {'settlementLegResults': ['loss']},
                       {'actual': 'Private bet ID 123'}, {'stakeDollars': 10}):
            with self.assertRaises(ValueError):
                record.public_accounting(dict(result, **change))

    def test_five_minute_recovery_reads_new_unit_grade_before_site_rebuild(self):
        import run
        import x_post
        ticket, evidence, posts, now = fixture()
        posts[0].update(kind='buffer:community', tweetId='123456789')
        evidence['legs'][1].update(actual=0, result='loss')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); private = root/'private'
            (root/'data').mkdir()
            (root/'data/community.json').write_text(json.dumps({'tickets': [ticket]}))
            (root/'data/x-posted.json').write_text(json.dumps({'posts': posts}))
            unit.append(ticket['id'], evidence, now, root=root, private=private)
            with patch.object(x_post, 'load_log', return_value={'posts': posts}):
                self.assertEqual(run.result_recovery_needed(now, root, private), 1)
                posts.append({'id': 'burnt:'+ticket['id'], 'bufferPostId': 'scheduled',
                              'dueAt': (now+timedelta(minutes=2)).isoformat()})
                self.assertEqual(run.result_recovery_needed(now, root, private), 0)
                posts[-1].update(sentAt=(now+timedelta(minutes=2)).isoformat(), tweetId='987654321')
                self.assertEqual(run.result_recovery_needed(now+timedelta(minutes=3), root, private), 0)

    def test_actual_result_planner_card_and_results_first_barrier_include_ticket(self):
        ticket, evidence, posts, now = fixture()
        posts[0].update(kind='buffer:community', tweetId='123456789',
                        discord={'state': 'sent', 'sentAt': posts[0]['sentAt'], 'messageId': '1234'})
        result, _ = unit.review(ticket, evidence, posts, now)
        play = dict(ticket, **result, publishedAt=posts[0]['sentAt'])
        book = {'posts': posts}
        tomorrow = now + timedelta(hours=12)
        with patch.object(receipts, 'unit_fun_rows', return_value=[play]):
            plans = receipts.cashed({}, {}, {}, book, now)
            self.assertEqual(len(plans), 1)
            self.assertEqual(buffer_post.quote_tweet_id(book, plans[0]['key']), posts[0]['tweetId'])
            self.assertNotIn('https://', plans[0]['text'])
            self.assertIn('clean sweep', receipts.result_detail(play))
            cards = receipts.result_cards({}, {}, {}, now, book)
            self.assertEqual(cards[0]['pick'], play)
            self.assertNotIn(':', cards[0]['card'])
            svg = ticket_card.fun_final_svg(play)
            self.assertIn('Synthetic Player 0', svg)
            self.assertIn('Synthetic Player 1', svg)
            self.assertIn('NET +0.42u', svg)
            self.assertIn('+168 DraftKings', svg)
            self.assertIn('Synthetic Player 0 5+', svg)
            self.assertIn('Synthetic Player 1 20+', svg)
            recap = receipts.day_receipt(now.astimezone(receipts.gates.EASTERN).date(), {}, {}, {}, set(), tomorrow, book)
            self.assertEqual(recap['pickIds'], [play['id']])
            self.assertIn('NET +0.42u', ticket_card.daily_result_svg(recap['dailyRows'], '2026-11-16'))
            self.assertIn('individual Final', receipts.prior_day_results_hold({}, {}, {}, book, tomorrow))
            book['posts'].append({'id': plans[0]['key'], 'sentAt': now.isoformat(), 'tweetId': '987654321',
                                 'discord': {'state': 'sent', 'sentAt': now.isoformat(), 'messageId': '5678'}})
            self.assertIn('ready but not delivered', receipts.prior_day_results_hold({}, {}, {}, book, tomorrow))
            book['posts'].append({'id': recap['key'], 'resultPickIds': recap['pickIds'],
                                 'sentAt': tomorrow.isoformat(), 'tweetId': '987654322',
                                 'discord': {'state': 'sent', 'sentAt': tomorrow.isoformat()}})
            self.assertIsNone(receipts.prior_day_results_hold({}, {}, {}, book, tomorrow))


if __name__ == '__main__':
    unittest.main()
