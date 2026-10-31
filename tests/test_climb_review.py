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
import run

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

    def test_render_outage_retains_private_admission_for_existing_recovery(self):
        ticket,ctx=fixture()
        import release_queue
        import x_post
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(gates,'admit',return_value=(True,[])), \
             patch.object(x_post,'do_draft'), \
             patch.object(run,'render_private_play_card',side_effect=run.ReleaseArtifactError('renderer unavailable')), \
             patch.object(ladder,'record_shadow'), patch.object(run,'log'):
            pick,error=review.enqueue(ticket,ctx,NOW,Path(folder))
            self.assertIsNone(error)
            row=release_queue.load(folder)['plays'][0]
            self.assertEqual(row['id'],pick['id'])
            self.assertEqual(row['artifactState'],'recovery-needed')
            self.assertNotIn('discordSentAt',row)


if __name__ == '__main__':
    unittest.main()
