import copy
import sys
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'tests'))
import prop_ticket_review as R
import prop_ticket_settlement as S
from test_prop_ticket_review import fixture


def case(family='MNF'):
    spec, games, before = fixture(family)
    now = before + timedelta(hours=8)
    original = R.review(spec, games, before)
    rows = [{'terms': S.identity(leg), 'result': 'win', 'actual': 3,
             'participation': 'played', 'injuryReview': 'clear', 'final': True,
             'checkedAt': now.isoformat(), 'source': 'https://www.espn.com/fixture-final'} for leg in spec['legs']]
    evidence = {'originalReview': original, 'legs': rows,
                'bookSettlement': {'verified': True, 'receipt': 'Synthetic private settlement',
                                   'book': spec['book'], 'termsFingerprint': R.fingerprint(spec),
                                   'source': 'https://sportsbook.draftkings.com/fixture-settled',
                                   'checkedAt': now.isoformat(), 'jurisdiction': 'IN',
                                   'ruleVersion': 'synthetic-rule-version',
                                   'rulesSource': 'https://sportsbook.draftkings.com/fixture-rules',
                                   'result': 'win', 'settledOdds': spec['odds']}}
    return spec, evidence, now


def void(row):
    row.update(result='void', actual=None, participation='did-not-play',
               voidReason='Synthetic book DNP decision', bookDecisionReceipt='Synthetic private void receipt')


class PropTicketSettlementTests(unittest.TestCase):
    def test_frozen_rules_clock_accepts_only_same_rounded_second(self):
        frozen='2026-11-25T18:23:54Z'
        self.assertTrue(S.original_rules_clock('2026-11-25T18:23:54.515411Z',frozen))
        self.assertFalse(S.original_rules_clock('2026-11-25T18:23:55Z',frozen))
        self.assertFalse(S.original_rules_clock('2026-11-25T18:23:54.515411Z',
                                              '2026-11-25T18:23:54.100000Z'))
        self.assertFalse(S.original_rules_clock('2026-11-24T18:23:53Z',frozen))
        self.assertFalse(S.original_rules_clock(None,frozen))

    def test_original_joint_price_drives_private_units_across_families(self):
        for family in R.FAMILIES:
            spec, evidence, now = case(family)
            result = S.review(spec, evidence, now)
            self.assertEqual(result['state'], 'settled-private', result)
            self.assertEqual(result['units'], 1.2775 if family == 'CFB-alts' else 1.0625)
            self.assertFalse(result['releaseReady'])
            self.assertFalse(result['recordWriteAllowed'])
            self.assertEqual(result['providerRequests'], 0)
            self.assertNotIn('Synthetic private', str(result))

    def test_first_quarter_does_not_grade_from_full_game_or_incomplete_actuals(self):
        spec, evidence, now = case()
        spec.update(parlayStyle='first-quarter', odds=548)
        for leg, row in zip(spec['legs'], evidence['legs']):
            leg['period'] = 'first_quarter'
            row.update(terms=S.identity(leg), actualPeriod='first_quarter', periodComplete=True)
        spec['ticketQuote']['terms'] = R.terms(spec)
        fingerprint = R.fingerprint(spec)
        evidence['originalReview']['termsFingerprint'] = fingerprint
        evidence['bookSettlement'].update(termsFingerprint=fingerprint, settledOdds=548)
        self.assertAlmostEqual(S.review(spec, evidence, now)['units'], 1.37)

        evidence['legs'][0]['actualPeriod'] = 'full_game'
        self.assertEqual(S.review(spec, evidence, now)['state'], 'held')
        evidence['legs'][0].update(actualPeriod='first_quarter', periodComplete=False)
        self.assertEqual(S.review(spec, evidence, now)['state'], 'held')

    def test_losing_and_all_void_tickets_use_original_stake(self):
        spec, evidence, now = case()
        evidence['legs'][0].update(actual=1, result='loss')
        evidence['bookSettlement']['result'] = 'loss'
        self.assertEqual(S.review(spec, evidence, now)['units'], -.25)
        void(evidence['legs'][1])
        self.assertEqual(S.review(spec, evidence, now)['units'], -.25)
        for row in evidence['legs']:void(row)
        evidence['bookSettlement']['result'] = 'void'
        self.assertEqual(S.review(spec, evidence, now)['units'], 0)

    def test_void_or_push_does_not_divide_the_original_sgp_price(self):
        for removal in ('void', 'push'):
            spec, evidence, now = case()
            if removal == 'void':void(evidence['legs'][0])
            else:
                spec['legs'][0]['line'] = 2
                spec['ticketQuote']['terms'] = R.terms(spec)
                evidence['originalReview']['termsFingerprint'] = R.fingerprint(spec)
                evidence['bookSettlement']['termsFingerprint'] = R.fingerprint(spec)
                evidence['legs'][0].update(terms=S.identity(spec['legs'][0]), result='push', actual=2)
            held = S.review(spec, evidence, now)
            self.assertEqual(held['state'], 'held')
            self.assertNotIn('units', held)
            self.assertTrue(any('book-repriced' in reason for reason in held['holds']))
            evidence['reducedQuote'] = {'verified': True, 'receipt': 'Synthetic reduced price',
                'originalTermsFingerprint': R.fingerprint(spec), 'book': spec['book'],
                'remainingLegs': [S.identity(leg) for leg in spec['legs'][1:]],
                'source': 'https://sportsbook.draftkings.com/fixture-reprice',
                'checkedAt': now.isoformat(), 'odds': 180, 'priceEstimated': False}
            evidence['bookSettlement']['settledOdds'] = 180
            evidence['reducedQuote']['checkedAt'] = spec['ticketQuote']['checkedAt']
            held = S.review(spec, evidence, now)
            self.assertEqual(held['state'], 'held')
            self.assertTrue(any('book-repriced' in reason for reason in held['holds']))
            evidence['reducedQuote']['checkedAt'] = now.isoformat()
            result = S.review(spec, evidence, now)
            self.assertEqual(result['state'], 'settled-private', result)
            self.assertEqual(result['units'], .45)
            evidence['reducedQuote']['remainingLegs'][0]['athleteId'] = 'wrong-player'
            self.assertEqual(S.review(spec, evidence, now)['state'], 'held')

    def test_changed_original_or_receipt_is_held(self):
        mutations = [lambda s,e: s.update(odds=500),
                     lambda s,e: s['legs'][0].update(line=1.5),
                     lambda s,e: e['bookSettlement'].update(termsFingerprint='different'),
                     lambda s,e: e['bookSettlement'].update(source='https://draftkings.com.evil.invalid/'),
                     lambda s,e: e['bookSettlement'].update(jurisdiction=''),
                     lambda s,e: e['bookSettlement'].update(jurisdiction='OH'),
                     lambda s,e: e['bookSettlement'].update(ruleVersion=''),
                     lambda s,e: e['bookSettlement'].update(result='loss'),
                     lambda s,e: e['bookSettlement'].update(settledOdds=600),
                     lambda s,e: e['originalReview'].update(state='held')]
        for mutate in mutations:
            spec, evidence, now = case(); mutate(spec,evidence)
            self.assertEqual(S.review(spec,evidence,now)['state'], 'held')

    def test_unresolved_injury_participation_or_wrong_stat_never_grades(self):
        for changes in ({'injuryReview':'unknown'}, {'participation':'unknown'},
                        {'actual':False}, {'actual':1}, {'actual':3.5}, {'actual':-1}, {'final':False},
                        {'injuryReview':'book-resolved'}, {'checkedAt':'2099-01-01T00:00:00Z'}):
            spec,evidence,now=case(); evidence['legs'][0].update(changes)
            result=S.review(spec,evidence,now)
            self.assertEqual(result['state'],'held', result)
            self.assertNotIn('units',result)
        spec,evidence,now=case();evidence['legs'][0]['terms']['market']='rushYds'
        self.assertEqual(S.review(spec,evidence,now)['state'],'held')

    def test_books_actual_protected_void_requires_remaining_joint_quote(self):
        spec,evidence,now=case();void(evidence['legs'][0])
        evidence['legs'][0].update(participation='played',injuryReview='book-resolved')
        self.assertEqual(S.review(spec,evidence,now)['state'],'held')
        del evidence['legs'][0]['bookDecisionReceipt']
        self.assertTrue(any('void reason' in h for h in S.review(spec,evidence,now)['holds']))

    def test_missing_or_nonterminal_leg_is_held_without_modifying_inputs(self):
        spec,evidence,now=case();evidence['legs'].pop();before=copy.deepcopy((spec,evidence))
        self.assertEqual(S.review(spec,evidence,now)['state'],'held')
        self.assertEqual((spec,evidence),before)

    def test_malformed_packets_and_pregame_terminal_evidence_hold(self):
        spec,evidence,now=case()
        for malformed in (None, [], dict(spec,legs=['bad']), dict(spec,family='unknown')):
            self.assertEqual(S.review(malformed,evidence,now)['state'],'held')
        for key in ('bookSettlement','originalReview'):
            bad=copy.deepcopy(evidence);bad[key]=['bad']
            self.assertEqual(S.review(spec,bad,now)['state'],'held')
        bad=copy.deepcopy(spec);bad['legs'][0]['line']=None
        self.assertEqual(S.review(bad,evidence,now)['state'],'held')
        evidence['legs'][0]['checkedAt']=spec['ticketQuote']['checkedAt']
        self.assertTrue(any('predate kickoff' in h for h in S.review(spec,evidence,now)['holds']))


if __name__ == '__main__':unittest.main()
