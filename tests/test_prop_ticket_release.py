import copy
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
import gates
import prop_ticket_release as P
import prop_ticket_review as R
import prop_ticket_settlement as S
import run
import release_queue
import x_post
import ticket_card
import discord_post
import desk_health
import buffer_post
import receipts
from test_prop_ticket_review import fixture
from test_prop_ticket_settlement import case, void


def prepared(family='MNF'):
    spec,games,now=fixture(family)
    spec['settlementPolicy']={'verified':True,'book':spec['book'],'jurisdiction':'IN',
        'source':'https://sportsbook.draftkings.com/fixture-rules','ruleVersion':'synthetic-test',
        'receipt':'Private rule evidence','checkedAt':now.isoformat(),
        **{k:'Synthetic reviewed rule, never a factual sportsbook policy.'
           for k in ('participation','pushVoid','earlyExit','reprice')}}
    ctx=SimpleNamespace(now=now,games=games,first={},latest={},risk_external={},risk_games={},root=ROOT)
    pick,held=P.candidate(spec,ctx,now)
    assert not held,held
    packet={'originalSpec':copy.deepcopy(spec),'originalReview':R.review(spec,games,now),
            'admittedAt':now.isoformat(),'checks':[copy.deepcopy(spec)],'settlementEvidence':None}
    return spec,ctx,pick,packet


class PropTicketReleaseTests(unittest.TestCase):
    def test_prospective_frequency_exception_keeps_admission_and_exposure_guards(self):
        spec,ctx,pick,packet=prepared('TNF')
        ctx.first={'monday':{'league':'NFL','publishedAt':(ctx.now-timedelta(days=3)).isoformat(),
                            'legs':[{'alternate':True}],'parlayType':'longshot','result':'loss'}}
        self.assertTrue(gates.alternate_parlay_frequency(pick,ctx).ok)
        with tempfile.TemporaryDirectory() as conf, patch.object(P,'CONF',Path(conf)):
            self.assertFalse(gates.reviewed_prop_ticket(pick,ctx).ok, 'a method label is not admission')
            P.save(pick['id'],packet,conf)
            self.assertTrue(gates.reviewed_prop_ticket(pick,ctx).ok)
            ctx.risk_external={'other':{'id':'other','riskUnits':5,'gameIds':['NFL-1']}}
            self.assertIn('exposure',P.refusal(pick,ctx,packet=packet))
            ctx.risk_external={'reserved':{'legs':[spec['legs'][0]],'_pendingRelease':True}}
            self.assertIn('already reserves',P.refusal(pick,ctx,packet=packet))

    def test_frequency_exception_does_not_widen_legacy_or_historical_tickets(self):
        spec,ctx,pick,packet=prepared('TNF')
        ctx.first={'prior':{'league':'NFL','publishedAt':(ctx.now-timedelta(days=4)).isoformat(),
                           'legs':[{'alternate':True}],'parlayType':'longshot'}}
        for change in ({'selectionMethod':None}, {'family':'unsupported'}, {'riskUnits':1},
                       {'parlayType':'easyProps'}, {'family':'NBA-alts'},
                       {'publishedAt':'2026-11-16T20:00:00Z'}):
            with self.subTest(change=change):
                self.assertFalse(gates.alternate_parlay_frequency(dict(pick,**change),ctx).ok)

    def test_shared_candidates_keep_exact_joint_terms_and_private_evidence_out(self):
        for family in R.FAMILIES:
            spec,ctx,pick,packet=prepared(family)
            self.assertEqual(R.terms(pick),R.terms(spec))
            self.assertEqual(pick['odds'],425)
            self.assertEqual(pick['riskUnits'],.25)
            self.assertNotIn('Synthetic private',json.dumps(pick))
            self.assertNotIn('Private synthetic',json.dumps(pick))
            self.assertNotIn('ticketQuote',pick)
            with patch.object(R, 'nba_participation', return_value=None):
                self.assertIsNone(P.refusal(pick,ctx,packet=packet))
            original=copy.deepcopy(pick)
            run.write_prose(pick,ctx,[])
            self.assertEqual(pick,original)

    def test_send_requires_post_admission_recheck_and_same_exact_terms(self):
        spec,ctx,pick,packet=prepared()
        packet['checks']=[]
        self.assertIn('send check',P.refusal(pick,ctx,packet=packet))
        self.assertIsNone(P.refusal(pick,ctx,packet=packet,phase='admit'))
        packet['checks']=[copy.deepcopy(spec)]
        packet['admittedAt']=(ctx.now+timedelta(minutes=1)).isoformat()
        self.assertIn('after admission',P.refusal(pick,ctx,packet=packet))
        packet['admittedAt']=ctx.now.isoformat()
        for mutate in (lambda p:p.update(odds=450),lambda p:p['legs'][0].update(line=1.5),
                       lambda p:p['legs'][0].update(athleteId='different')):
            changed=copy.deepcopy(pick);mutate(changed)
            self.assertIn('terms changed',P.refusal(changed,ctx,packet=packet))
        packet['checks'][-1]['odds']=500
        self.assertIn('differs',P.refusal(pick,ctx,packet=packet))

    def test_missing_or_wrong_book_rules_block_initial_candidate(self):
        for change in ({}, {'verified':False}, {'jurisdiction':'unknown'},
                       {'source':'https://unrelated.invalid/rules'}, {'reprice':''}):
            spec,ctx,pick,packet=prepared()
            if not change:spec.pop('settlementPolicy')
            else:spec['settlementPolicy'].update(change)
            candidate,held=P.candidate(spec,ctx,ctx.now)
            self.assertIsNone(candidate)
            self.assertIn('book-specific',held)

    def test_stale_and_newly_unavailable_players_hold_rechecks(self):
        spec,ctx,pick,packet=prepared()
        packet['checks'][-1]['legs'][0]['review']['availability']['status']='inactive'
        self.assertIn('availability',P.refusal(pick,ctx,packet=packet))
        packet['checks']=[copy.deepcopy(spec)]
        self.assertIn('Fresh visible',P.refusal(pick,ctx,ctx.now+timedelta(minutes=61),packet=packet))

    def test_external_owner_ticket_blocks_repeated_player_and_weekly_alt(self):
        spec,ctx,pick,packet=prepared()
        ctx.risk_external={'owner':{'id':'owner','league':'NFL','personalTicket':True,
            'status':'active','quotedAt':ctx.now.isoformat(),'riskUnits':.25,
            'kickoff':spec['legs'][0]['kickoff'],'legs':[spec['legs'][0]]}}
        held=P.refusal(pick,ctx,packet=packet)
        self.assertIn('no repeated exposure',held)
        self.assertIn('within seven days',held)

    def test_own_reservation_does_not_block_recheck_but_other_risk_does(self):
        spec,ctx,pick,packet=prepared()
        ctx.first[pick['id']]=dict(pick,publishedAt=ctx.now.isoformat(),_pendingRelease=True)
        self.assertIsNone(P.refusal(pick,ctx,packet=packet))
        ctx.risk_external={'other':{'id':'other','riskUnits':5,'gameIds':['NFL-1']}}
        self.assertIn('exposure',P.refusal(pick,ctx,packet=packet))

    def test_recheck_appends_and_never_changes_original_or_accepts_new_price(self):
        spec,ctx,pick,packet=prepared()
        with tempfile.TemporaryDirectory() as conf:
            P.save(pick['id'],packet,conf)
            P.recheck(pick['id'],spec,ctx,ctx.now,conf)
            saved=P.load(pick['id'],conf)
            self.assertEqual(saved['originalSpec'],packet['originalSpec'])
            self.assertEqual(len(saved['checks']),2)
            changed=copy.deepcopy(spec);changed['odds']=500
            with self.assertRaisesRegex(ValueError,'every original term'):
                P.recheck(pick['id'],changed,ctx,ctx.now,conf)
            self.assertEqual(P.load(pick['id'],conf),saved)
            self.assertEqual(P.path(pick['id'],conf).stat().st_mode & 0o777,0o600)

    def test_real_admission_and_release_gates_require_saved_evidence(self):
        spec,ctx,pick,packet=prepared()
        with tempfile.TemporaryDirectory() as conf:
            with patch.object(P,'CONF',Path(conf)):
                self.assertFalse(gates.reviewed_prop_ticket(pick,ctx).ok)
                P.save(pick['id'],packet,conf)
                self.assertTrue(gates.reviewed_prop_ticket(pick,ctx).ok)
                with patch.object(run,'CONF',Path(conf)):
                    self.assertIsNone(run.private_release_refusal({'league':'NFL','pick':pick},ctx,ctx.now))
                    packet['checks']=[];P.save(pick['id'],packet,conf)
                    self.assertIn('send check',run.private_release_refusal({'league':'NFL','pick':pick},ctx,ctx.now))

    def test_nba_queue_holds_when_current_participation_is_unavailable(self):
        spec,ctx,pick,packet=prepared('NBA-alts')
        with tempfile.TemporaryDirectory() as conf:
            ctx.root = Path(conf)
            actual,held=P.enqueue(spec,ctx,ctx.now,conf)
            self.assertIsNone(actual)
            self.assertIn('participation snapshot unavailable',held)
            self.assertFalse(list(Path(conf).iterdir()))

    def test_actual_queue_and_draft_remain_private_until_rechecked(self):
        spec,ctx,pick,packet=prepared()
        with tempfile.TemporaryDirectory() as conf, patch.object(P,'CONF',Path(conf)), \
                patch.object(run,'CONF',Path(conf)), \
                patch.object(x_post,'load_log',return_value={'posts':[]}), \
                patch.object(run,'render_private_play_card',side_effect=RuntimeError('Synthetic renderer outage')):
            actual,held=P.enqueue(spec,ctx,ctx.now,conf)
            self.assertIsNone(held)
            queued=release_queue.load(conf)['plays']
            self.assertEqual(len(queued),1)
            self.assertEqual(queued[0]['artifactMissing'],['card'])
            for leg in spec['legs']:
                self.assertIn(leg['player']+' over 2.5 catches',queued[0]['caption'])
            self.assertEqual(P.load(pick['id'],conf)['checks'],[])
            self.assertIsNone(P.enqueue(spec,ctx,ctx.now,conf)[0])
            with patch.object(gates,'Stores') as stores, patch.object(run.features,'load',return_value=[]), \
                    patch.object(run,'live_games',return_value=ctx.games), \
                    patch('receipts.prior_day_results_hold',return_value=None), \
                    patch('typefully_backup.config',return_value=None), \
                    patch.object(run,'private_release_refusal') as gate, \
                    patch.object(buffer_post,'x_channel') as channel:
                stores.return_value.as_of.return_value=ctx
                self.assertEqual(run.release_private(ctx.now,log=lambda *_:None),[])
                gate.assert_not_called()
                channel.assert_not_called()
            self.assertEqual(len(release_queue.load(conf)['plays']),1)
            P.recheck(pick['id'],spec,ctx,ctx.now,conf)
            self.assertIsNone(P.refusal(pick,ctx,conf=conf))

    def test_direct_buffer_route_cannot_skip_recheck_by_omitting_item(self):
        spec,ctx,pick,packet=prepared()
        packet['checks']=[]
        ctx.first[pick['id']]=pick
        for items in ({}, {pick['id']:pick}):
            sender=Mock(side_effect=AssertionError('Must not call Buffer'))
            logs=[]
            with patch.object(gates,'Stores') as stores, patch.object(P,'load',return_value=packet), \
                    patch('receipts.prior_day_results_hold',return_value=None):
                stores.return_value.as_of.return_value=ctx
                buffer_post.schedule([(pick['id'],'play','Synthetic ticket',ctx.now+timedelta(minutes=20),pick['id'])],
                    'synthetic-channel',{'posts':[]},ctx.now,items=items,send=sender,log=logs.append)
            sender.assert_not_called()
            self.assertTrue(any('send check' in line for line in logs),logs)

    def test_malformed_private_evidence_holds_without_stopping_other_plays(self):
        spec,ctx,pick,packet=prepared()
        for change in ({'originalSpec':{'legs':[None]}}, {'checks':[{'legs':'bad'}]},
                       {'checks':[dict(spec,ticketQuote=['bad'])]}):
            broken=dict(packet,**change)
            self.assertTrue(P.refusal(pick,ctx,packet=broken))
        broken=dict(packet,settlementEvidence=['bad'])
        result,held=P.settlement_revision(pick,ctx.now,packet=broken)
        self.assertIsNone(result)
        self.assertIn('held',held)

    def test_ordinary_worker_never_auto_grades_this_sgp_without_book_review(self):
        spec,ctx,pick,packet=prepared()
        now=ctx.now+timedelta(hours=8)
        ctx.first={pick['id']:dict(pick)}
        games={k:dict(g,completed=True,state='post') for k,g in ctx.games.items()}
        with patch.object(P,'load',return_value=packet),patch.object(run,'grade_prop') as generic:
            rows,unclear=run.settle(ctx,{pick['id']:('parlays',pick)},games,[],now)
        self.assertEqual(rows,[])
        self.assertIn('book settlement',unclear[0]['why'])
        generic.assert_not_called()

    def test_normal_final_stats_can_grade_without_an_owner_wager_receipt(self):
        spec,ctx,pick,packet=prepared()
        _,evidence,now=case()
        evidence['basis']='official-stats-and-rules'
        evidence['statSettlement']=evidence.pop('bookSettlement')
        receipt=evidence['statSettlement']
        receipt.update(source=spec['settlementPolicy']['source'],
                       ruleVersion=spec['settlementPolicy']['ruleVersion'])
        receipt.pop('result');receipt.pop('settledOdds')
        packet['settlementEvidence']=evidence
        revised,held=P.settlement_revision(pick,now,packet=packet)
        self.assertIsNone(held)
        self.assertEqual(revised['result'],'win')
        self.assertEqual(revised['units'],1.062)
        self.assertEqual(revised['settlementBasis'],'official-stats-and-rules')
        self.assertIn('clean sweep',receipts.result_detail(revised))
        self.assertNotIn('Synthetic private',json.dumps(revised))
        evidence['legs'][0].update(result='loss',actual=1)
        self.assertEqual(P.settlement_revision(pick,now,packet=packet)[0]['units'],-.25)
        for changes in ({'injuryReview':'unknown'}, {'injuryReview':'book-resolved','bookDecisionReceipt':'synthetic'},
                        {'participation':'did-not-play'}, {'result':'void','voidReason':'synthetic','bookDecisionReceipt':'synthetic'}):
            broken=copy.deepcopy(packet);broken['settlementEvidence']['legs'][0].update(changes)
            self.assertIsNone(P.settlement_revision(pick,now,packet=broken)[0])
        receipt['ruleVersion']='different-rules'
        self.assertIsNone(P.settlement_revision(pick,now,packet=packet)[0])

    def test_verified_reduced_joint_price_survives_normal_settlement_worker(self):
        spec,evidence,now=case()
        _,ctx,pick,packet=prepared()
        void(evidence['legs'][0])
        packet['settlementEvidence']=evidence
        revised,held=P.settlement_revision(pick,now,packet=packet)
        self.assertIsNone(revised)
        self.assertIn('book-repriced',held)
        evidence['reducedQuote']={'verified':True,'receipt':'Private reduced quote',
            'originalTermsFingerprint':R.fingerprint(spec),'book':spec['book'],
            'remainingLegs':[S.identity(l) for l in spec['legs'][1:]],
            'source':'https://sportsbook.draftkings.com/fixture-reprice','checkedAt':now.isoformat(),
            'odds':180,'priceEstimated':False}
        evidence['bookSettlement']['settledOdds']=180
        ctx.first={pick['id']:dict(pick)}
        games={k:dict(g,completed=True,state='post') for k,g in ctx.games.items()}
        before=copy.deepcopy(pick)
        with patch.object(P,'load',return_value=packet):
            rows,unclear=run.settle(ctx,{pick['id']:('parlays',pick)},games,[],now)
        self.assertEqual(unclear,[])
        self.assertEqual(rows[0][2]['units'],.45)
        self.assertEqual(rows[0][2]['odds'],425)
        self.assertEqual(rows[0][2]['settledOdds'],180)
        self.assertIn('leg voided',receipts.result_detail(rows[0][2]))
        self.assertNotIn('Private reduced quote',json.dumps(rows))
        self.assertEqual(pick,before)

        row = rows[0][2]
        post = dict(id=pick['id'], kind='buffer:play', tweetId='123456789012',
                    sentAt=packet['admittedAt'], discord={'state':'sent', 'messageId':'123456789012'})
        log = {'posts':[post]}
        with patch.object(receipts, 'unit_fun_rows', return_value=[]):
            [final] = receipts.cashed(ctx.first, {pick['id']:row}, games, log, now)
            self.assertEqual(discord_post.queue_results(log, ctx.first, {pick['id']:row}, games, now), 1)
        self.assertIn('original +425 · settled +180', final['text'])
        self.assertEqual(receipts.guard(final), [])
        self.assertIn('settled at +180', post['discord']['result']['text'])
        self.assertEqual(post['discord']['result']['cardKey'], final['card'])
        self.assertNotIn('None', row['actual'])
        art = ticket_card.fun_final_svg(row)
        self.assertIn('original +425 · settled +180', art)
        self.assertIn('NET +0.45u', art)
        for legacy in (dict(row, settlementBasis=None), dict(row, selectionMethod=None)):
            self.assertIsNone(receipts.repriced_odds(legacy))
            self.assertNotIn('settled', receipts.fun_final_price(legacy))

    def test_all_void_football_tickets_keep_record_art_and_follow_current_social_policy(self):
        for family in ('MNF', 'TNF'):
            with self.subTest(family=family):
                _,ctx,pick,packet = prepared(family)
                _,evidence,now = case(family)
                for leg in evidence['legs']:
                    void(leg)
                evidence['bookSettlement']['result'] = 'void'
                packet['settlementEvidence'] = evidence
                row,hold = P.settlement_revision(pick,now,packet=packet)
                self.assertIsNone(hold)
                first,latest = {pick['id']:pick},{pick['id']:row}
                post = dict(id=pick['id'],kind='buffer:play',tweetId='123456789012',sentAt=packet['admittedAt'])
                log = {'posts':[post]}
                with patch.object(receipts,'unit_fun_rows',return_value=[]):
                    plans = receipts.cashed(first,latest,ctx.games,log,now)
                    [card] = receipts.result_cards(first,latest,ctx.games,now,log)
                self.assertIn('TICKET VOID',ticket_card.fun_final_svg(row))
                if family == 'TNF':  # This fixture settles after the Nov 19 social policy change.
                    self.assertEqual(plans, [])
                    health=desk_health.result_timeliness({'picks':[dict(row,posted=True)]},[post],now,individual_only=True)
                    self.assertEqual(health['missing'],0)
                    continue
                [plan] = plans
                self.assertEqual(card['card'],plan['card'])
                self.assertEqual(buffer_post.quote_tweet_id(log,plan['key']),post['tweetId'])
                self.assertIn('legs voided',plan['text'])
                self.assertNotIn('0/0',plan['text'])
                self.assertNotIn('cashed',plan['text'])
                health=desk_health.result_timeliness({'picks':[dict(row,posted=True)]},[post],now,individual_only=True)
                self.assertEqual(health['missing'],1)

    def test_injury_deadline_needs_fresh_review_and_preserves_result_disclosure(self):
        spec,ctx,pick,packet=prepared()
        _,evidence,_=case()
        deadline=gates.when(spec['legs'][0]['kickoff'])+timedelta(hours=12)
        evidence['basis']='official-stats-and-rules'
        evidence['statSettlement']=evidence.pop('bookSettlement')
        receipt=evidence['statSettlement']
        receipt.update(source=spec['settlementPolicy']['source'],
                       ruleVersion=spec['settlementPolicy']['ruleVersion'],checkedAt=deadline.isoformat())
        row=evidence['legs'][0]
        row.update(result='loss',actual=1,injuryReview='deadline-stats',
                   injuryEvidence={'status':'verified-injury','checkedAt':deadline.isoformat(),
                       'differentBookDecisionKnown':False,
                       'note':'Synthetic player left injured and did not return; no different book decision found.',
                       'sources':['https://www.espn.com/fixture-injury']})
        packet['settlementEvidence']=evidence
        self.assertIsNone(P.settlement_revision(pick,deadline-timedelta(seconds=1),packet=packet)[0])
        revised,held=P.settlement_revision(pick,deadline,packet=packet)
        self.assertIsNone(held)
        self.assertEqual(revised['units'],-.25)
        self.assertEqual(revised['injuryPlayers'],[spec['legs'][0]['player']])
        self.assertIn('left hurt',receipts.result_detail(revised))
        self.assertIn('missed by one leg',receipts.result_detail(revised))
        self.assertIn('left injured',revised['settlementReason'])
        self.assertIn('https://www.espn.com/fixture-injury',revised['settlementReviewSources'])
        for changes in ({'differentBookDecisionKnown':True}, {'sources':[]},
                        {'checkedAt':(deadline-timedelta(seconds=1)).isoformat()}, {'note':''}):
            broken=copy.deepcopy(packet)
            broken['settlementEvidence']['legs'][0]['injuryEvidence'].update(changes)
            self.assertIsNone(P.settlement_revision(pick,deadline,packet=broken)[0])
        row['injuryEvidence']['status']='unresolved'
        revised,held=P.settlement_revision(pick,deadline,packet=packet)
        self.assertIsNone(held)
        self.assertEqual(revised['injuryPlayers'],[])
        row.update(result='void',actual=None)
        self.assertIsNone(P.settlement_revision(pick,deadline,packet=packet)[0])


if __name__=='__main__':unittest.main()
