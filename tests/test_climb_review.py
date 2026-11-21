import copy
import sys
import unittest
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import climb_review as review
import gates
import ladder
import refresh
import run
import social_style
import ticket_card
import x_post

NOW = datetime(2026, 10, 31, 13, tzinfo=timezone.utc)


def fixture():
    legs = []
    games = {}
    for i in range(2):
        gid = f'g{i}'
        games[gid] = dict(id=gid, league='CFB', season=2026, week=9, state='pre',
                         kickoff='2026-10-31T16:00Z', home=dict(short='Home'), away=dict(short='Away'))
        legs.append(dict(id=f'l{i}', title='Home +7.5', gameId=gid,
            marketType='spread', direction='home', line=7.5, mainLine=-2.5,
            marketWindow='Full game', alternate=True, odds=-425, book='DraftKings',
            observedAt='2026-10-31T12:55Z', kickoff=games[gid]['kickoff'],
            source='https://sportsbook.draftkings.com/event/example/1',
            researchCase=dict(why='Current rushing matchup supports taking the points.',
                risk='A turnover could erase the cushion.', availability='Current team preview checked; no new absence reported, not a guarantee.',
                sources=[dict(url='https://example.edu/news/preview',fact='Current starting quarterback is listed in the preview.',checkedAt='2026-10-31T12:50Z')])) )
    ticket = dict(selectionMethod=review.METHOD, book='DraftKings', odds=-190,
        legs=legs, gameIds=list(games), quotedAt='2026-10-31T12:55Z',
        researchReview=dict(method=review.METHOD,reviewer='kookn-desk',reviewedAt='2026-10-31T12:56Z',
            ticketVerified=True,ticketSource='https://sportsbook.draftkings.com/leagues/football/ncaaf',
            receipt='Private screenshot of both exact legs and combined price.'))
    return ticket, SimpleNamespace(now=NOW,games=games,first={},latest={})


class ReviewedClimbTests(unittest.TestCase):
    def test_full_rollover_one_and_two_leg_public_path_excludes_private_review(self):
        now = ladder.FULL_ROLLOVER_FROM + timedelta(hours=9)
        for single in (True, False):
            ticket, ctx = fixture()
            ctx.now = now
            for i in range(4):
                gid = f'old-{i}'
                ctx.first[gid] = dict(id=gid, parlayType='ladder', result='loss',
                                      publishedAt=f'2026-11-{10+i:02}T14:00Z')
            ticket['quotedAt'] = '2026-11-21T13:55Z'
            ticket['odds'] = -220.0 if single else -210
            ticket['researchReview'].update(reviewedAt='2026-11-21T13:58Z', unboosted=True)
            if single:
                ticket['legs'] = ticket['legs'][:1]
            else:
                ctx.games['g1']['league'] = 'NFL'
            for leg in ticket['legs']:
                ctx.games[leg['gameId']]['kickoff'] = '2026-11-21T17:00Z'
                leg.update(odds=-220 if single else -465, observedAt=ticket['quotedAt'],
                           kickoff='2026-11-21T17:00Z', receipt='private leg receipt')
                leg['researchCase']['sources'][0]['checkedAt'] = '2026-11-21T13:54Z'
            pick, held = ladder.manual_candidate(ctx, ctx.games, now, ticket)
            self.assertIsNone(held)
            admitted, decisions = gates.admit(dict(pick, league='CFB'), ctx)
            self.assertTrue(admitted, [decision.reason for decision in gates.refusals(decisions)])
            self.assertIsNone(run.private_release_refusal({'pick': pick, 'league': 'CFB'}, ctx, now))
            self.assertIn('expired', run.private_release_refusal({'pick': pick}, ctx, now + timedelta(hours=2)))
            edited = dict(pick, ladder=dict(pick['ladder'], nextStake=50))
            self.assertFalse(gates.ladder_selective(edited, ctx).ok)
            self.assertEqual((pick['ladder']['stake'], pick['ladder']['nextStake']),
                             (50, 72.73 if single else 73.81))
            run.write_prose(pick, ctx, [])
            pick.update(publishedAt=gates.stamp(now), jurisdictionVerified=True)
            caption = x_post.draft(pick, ctx.games['g0'], history=[])
            self.assertFalse(x_post.guard(caption, pick, now=now))
            self.assertIn('Full return rides.', caption)
            self.assertIn('$50 to $1,000 Climb · Step 1', caption)
            self.assertIn('$50 → $72.73' if single else '$50 → $73.81', caption)
            challenge = social_style.challenge_amounts(pick)
            self.assertTrue(social_style.issues(caption))
            self.assertFalse(social_style.issues(caption, challenge=challenge))
            self.assertTrue(social_style.issues(caption.replace('$50 →', '2u →'), challenge=challenge))
            self.assertTrue(social_style.issues(caption + '\n$576.97', challenge=challenge))
            svg = ticket_card.climb_svg(pick, ctx.games, art=[None] * len(ticket['legs']))
            self.assertFalse(social_style.issues(svg, graphic=True, challenge=challenge))
            self.assertIn('$1,000', svg)
            self.assertIn('$72.73' if single else '$73.81', svg)
            svg = ticket_card.climb_result_svg(dict(pick, result='win'), ctx.games,
                                               art=[None] * len(ticket['legs']))
            self.assertIn('ROLLS TO STEP 2', svg)
            import receipts
            final = '\n'.join(receipts.ladder_result(dict(pick, result='win')))
            self.assertIn('$72.73 back' if single else '$73.81 back', final)
            self.assertFalse(social_style.issues(final, challenge=challenge))
            with tempfile.TemporaryDirectory() as conf:
                public = review.public_pick(pick, conf)
                self.assertEqual(public, review.public_pick(pick, conf))
                self.assertTrue((Path(conf) / 'climb-reviews' / f"{pick['id']}.json").is_file())
            self.assertNotIn('researchReview', public)
            self.assertTrue(all('receipt' not in leg and 'researchCase' not in leg for leg in public['legs']))
            with patch.object(refresh, 'datetime', wraps=datetime) as clock:
                clock.now.return_value = now
                refresh.validate_report({'league': 'CFB', 'publishedAt': pick['publishedAt'],
                                         'parlays': [public]}, ctx.games)
            games = {f"{game['league']}-{i}": dict(game, completed=True,
                     away=dict(game['away'], score=20), home=dict(game['home'], score=17))
                     for i, game in enumerate(ctx.games.values())}
            legs = [dict(leg, gameId=gid) for leg, gid in zip(public['legs'], games)]
            final = dict(public, league='CFB', legs=legs, gameIds=[leg['gameId'] for leg in legs])
            graded, unclear = run.settle(SimpleNamespace(first={final['id']: final}, latest={}),
                                         {final['id']: ('parlays', final)}, games, [], now + timedelta(hours=12))
            self.assertFalse(unclear)
            self.assertEqual(graded[0][2]['result'], 'win')
            self.assertEqual(graded[0][2]['ladder'], public['ladder'])
            ticket['researchReview']['unboosted'] = False
            self.assertIn('unboosted', ladder.manual_candidate(ctx, ctx.games, now, ticket)[1])

    def test_separate_route_needs_no_manufactured_probability_and_retains_case(self):
        ticket, ctx = fixture()
        pick, error = ladder.manual_candidate(ctx,ctx.games,NOW,ticket)
        self.assertIsNone(error)
        self.assertNotIn('chance',pick)
        self.assertIsNone(ladder.support_refusal(pick,ctx))
        run.write_prose(pick,ctx,[])
        self.assertIn('rushing matchup',pick['why'])
        self.assertIn('turnover',pick['risk'])
        self.assertNotIn('projection clears',pick['why'])
        self.assertEqual(pick['researchReview'],ticket['researchReview'])
        self.assertTrue(gates.ladder_selective(pick,ctx).ok)
        self.assertNotIn('proven-segment',gates.ladder_supported(pick,ctx).reason)
        self.assertTrue(gates.expiry_ok(pick,ctx).ok)
        bad=dict(pick,expiresAt='2026-10-31T15:50Z')
        self.assertFalse(gates.expiry_ok(bad,ctx).ok)
        with tempfile.TemporaryDirectory() as folder:
            shadow=ladder.record_shadow(ctx,NOW,ticket=pick,path=Path(folder)/'shadow.jsonl')
        self.assertIsNone(shadow['ticket']['chance'])
        self.assertIsNone(shadow['ticket']['edge'])

    def test_mixed_league_rungs_require_the_prospective_sourced_review(self):
        ticket, ctx = fixture()
        pick, error = ladder.manual_candidate(ctx, ctx.games, NOW, ticket)
        self.assertIsNone(error)
        ctx.games[pick['gameIds'][0]]['league'] = 'NFL'
        self.assertFalse(gates.ladder_selective(pick, ctx).ok)
        ctx.now = ladder.MIXED_REVIEW_FROM
        self.assertTrue(gates.ladder_selective(pick, ctx).ok)
        self.assertFalse(gates.ladder_selective(dict(pick, selectionMethod='automatic'), ctx).ok)
        ctx.games[pick['gameIds'][0]]['league'] = 'NBA'
        self.assertFalse(gates.ladder_selective(pick, ctx).ok)

    def test_bad_price_receipt_and_probability_claims_are_refused(self):
        for mutate in (
            lambda t:t.update(odds=-175),
            lambda t:t.update(chance=.9),
            lambda t:t['legs'][0].update(chance=.9),
            lambda t:t['researchReview'].update(ticketVerified=False),
            lambda t:t['researchReview'].update(receipt=''),
            lambda t:t['researchReview'].update(ticketSource='https://draftkings.com.evil.invalid/'),
            lambda t:t['legs'][0].update(book='FanDuel'),
            lambda t:t['legs'][0].update(mainLine=7.5),
            lambda t:t['legs'][0].update(marketWindow='1Q'),
            lambda t:t['legs'][0].update(title='Away -7.5'),
            lambda t:t['legs'][0].update(kickoff='2026-10-31T20:00Z'),
        ):
            ticket,ctx=fixture();mutate(ticket)
            self.assertIsNotNone(review.refusal(ticket,ctx))

    def test_missing_risk_future_source_and_stale_review_are_refused(self):
        for mutate in (
            lambda t:t['legs'][0]['researchCase'].update(risk=''),
            lambda t:t['legs'][0]['researchCase'].update(availability=''),
            lambda t:t['legs'][0]['researchCase'].update(sources=[]),
            lambda t:t['legs'][0]['researchCase']['sources'][0].update(checkedAt='2026-10-31T13:01Z'),
            lambda t:t['researchReview'].update(reviewedAt='2026-10-31T10:00Z'),
            lambda t:t['legs'][0].update(observedAt='2026-10-31T13:01Z'),
        ):
            ticket,ctx=fixture();mutate(ticket)
            self.assertIsNotNone(review.refusal(ticket,ctx))

    def test_same_game_started_and_unsupported_nba_are_refused(self):
        ticket,ctx=fixture();ticket['legs'][1]['gameId']='g0'
        self.assertIsNotNone(review.refusal(ticket,ctx))
        ticket,ctx=fixture();ctx.games['g0']['state']='in'
        self.assertIsNotNone(review.refusal(ticket,ctx))
        ticket,ctx=fixture();ctx.games['g0']['league']='NBA'
        self.assertIsNotNone(review.refusal(ticket,ctx))

    def test_historical_replay_open_climb_weekly_cap_and_kill_switch_survive(self):
        ticket,ctx=fixture();ctx.now=review.EFFECTIVE-timedelta(seconds=1)
        self.assertIsNotNone(review.refusal(ticket,ctx))
        ticket,ctx=fixture()
        with patch.object(ladder,'state',return_value={'open':{'id':'open'}}):
            self.assertIsNone(ladder.manual_candidate(ctx,ctx.games,NOW,ticket)[0])
        with patch.object(ladder,'weekly_refusal',return_value='weekly cap'):
            self.assertIsNone(ladder.manual_candidate(ctx,ctx.games,NOW,ticket)[0])
        with patch.object(ladder,'v3_enabled',return_value=False):
            self.assertIsNone(ladder.manual_candidate(ctx,ctx.games,NOW,ticket)[0])

    def test_reviewed_slot_after_weekly_cap_and_same_day_reservation(self):
        ticket, ctx = fixture()
        history = {
            f'rung-{day}': {'parlayType': 'ladder', 'publishedAt': f'2026-10-{day}T15:00Z'}
            for day in (26, 27, 28)
        }
        empty_state = ladder.state({}, {})
        ctx.first = history
        with patch.object(ladder, 'state', return_value=empty_state):
            self.assertIn('weekly Climb limit', review.candidate(ctx, ctx.games, NOW, ticket)[1])
            with patch.object(ladder, 'REVIEWED_DAILY_FROM', NOW):
                pick, held = review.candidate(ctx, ctx.games, NOW, ticket)
                self.assertIsNone(held)
                self.assertTrue(gates.ladder_selective(pick, ctx).ok)
                self.assertFalse(gates.ladder_selective(dict(pick, selectionMethod=None), ctx).ok)
                ctx.first[pick['id']] = dict(pick, publishedAt=NOW.isoformat(), _pendingRelease=True)
                self.assertTrue(gates.ladder_selective(pick, ctx).ok)
                self.assertFalse(gates.ladder_selective(dict(pick, id='second-book'), ctx).ok)
                self.assertIn('privately reserved', review.candidate(ctx, ctx.games, NOW, ticket)[1])

    def test_release_rechecks_and_review_is_frozen(self):
        ticket,ctx=fixture();pick,_=ladder.manual_candidate(ctx,ctx.games,NOW,ticket)
        self.assertIsNone(run.private_release_refusal(dict(pick=pick,league='CFB',discordSentAt='already'),ctx,NOW))
        changed=copy.deepcopy(pick);changed['researchReview']['ticketVerified']=False
        self.assertIsNotNone(run.private_release_refusal(dict(pick=changed,league='CFB',discordSentAt='already'),ctx,NOW))
        ctx.first[pick['id']]=pick
        self.assertFalse(gates.revision_frozen(changed,ctx).ok)

    def test_fast_queue_reuses_exact_review_and_normal_gates_without_a_capture(self):
        ticket,ctx=fixture()
        import release_queue
        import x_post
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(gates,'admit',return_value=(True,[])) as admit, \
             patch.object(x_post,'do_draft') as draft, \
             patch.object(run,'render_private_play_card') as render, \
             patch.object(run,'capture',side_effect=AssertionError('no capture')), \
             patch.object(run.build_site,'build',side_effect=AssertionError('no board rebuild')), \
             patch.object(ladder,'record_shadow'):
            pick,error=review.enqueue(ticket,ctx,NOW,Path(folder))
            self.assertIsNone(error)
            admit.assert_called_once()
            draft.assert_called_once()
            render.assert_called_once()
            self.assertEqual(render.call_args.args[1]['publishedAt'],gates.stamp(NOW))
            row=release_queue.load(folder)['plays'][0]
            self.assertEqual(row['pick']['researchReview'],ticket['researchReview'])
            self.assertNotIn('discordSentAt',row)
            self.assertNotIn('publicPath',row)
            self.assertEqual(row['id'],pick['id'])
            self.assertIsNone(review.enqueue(ticket,ctx,NOW,Path(folder))[0])

    def test_owner_roll_split_is_prospective_and_reconciles_current_rung(self):
        ticket, _ = fixture()
        where = {'run': 4, 'step': 3, 'stake': 76, 'banked': 34}
        ticket['stakeAdjustment'] = {
            'method': ladder.OWNER_ROLL_SPLIT, 'approvedAt': '2026-11-07',
            'priorStake': 76, 'nextStake': 25, 'additionalBank': 51,
            'priorBank': 34, 'bankedAfter': 85,
        }
        stake, banked, adjustment = ladder.prospective_stake(where, ticket)
        self.assertEqual((stake, banked), (25, 85))
        self.assertEqual(adjustment['additionalBank'], 51)
        ticket['stakeAdjustment']['additionalBank'] = 50
        with self.assertRaises(ValueError):
            ladder.prospective_stake(where, ticket)

    def test_render_outage_retains_private_admission_for_existing_recovery(self):
        ticket,ctx=fixture()
        import release_queue
        import x_post
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(gates,'admit',return_value=(True,[])), \
             patch.object(x_post,'do_draft'), \
             patch.object(run,'render_private_play_card',side_effect=run.ReleaseArtifactError('renderer unavailable')), \
             patch.object(ladder,'record_shadow'), patch.object(run,'log'):
            old=Path(folder)/'x-drafts'/'CFB-2026-W9-ladder-1031-c1s1-dk.png'
            old.parent.mkdir(parents=True)
            old.write_bytes(b'old-price-image')
            release_queue.save(folder,{'plays':[{'id':'expired', 'pick':{'expiresAt':'2026-10-31T12:00Z'}}]})
            pick,error=review.enqueue(ticket,ctx,NOW,Path(folder))
            self.assertIsNone(error)
            row=release_queue.load(folder)['plays'][0]
            self.assertEqual(row['id'],pick['id'])
            self.assertEqual(row['artifactState'],'recovery-needed')
            self.assertNotIn('discordSentAt',row)
            self.assertFalse(old.exists())
            self.assertIn('card',row['artifactMissing'])
            self.assertNotIn('expired',[r['id'] for r in release_queue.load(folder)['plays']])


if __name__ == '__main__':
    unittest.main()
