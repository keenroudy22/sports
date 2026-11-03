import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cbb_picks as cbb
import boxscores
import staking

NOW=datetime(2026,11,3,15,tzinfo=timezone.utc)

def fixture():
    g=dict(id='CBB-123',status='scheduled',seasonType='regular-season',timeConfirmed=True,neutral=False,
        kickoff='2026-11-04T00:00:00Z',season=2027,teams={
            'home':dict(id='1',abbreviation='HOME',name='Home Team'),
            'away':dict(id='2',abbreviation='AWAY',name='Away Team')})
    terms=dict(marketType='total',direction='under',line=150.5,odds=-110,oppositeOdds=-110)
    return dict(id='CBB-20261103-123-under-150-5-dk',eventId=g['id'],game=g,league='CBB',
        selectionMethod=cbb.METHOD,period='full_game',alternate=False,riskUnits=1,
        stakingPolicy=staking.CURRENT_VERSION,**terms,
        quote=dict(**terms,book='DraftKings',verified=True,source='https://sportsbook.draftkings.com/event/test/123',
            receipt='/private/quote.png',checkedAt=boxscores.stamp(NOW)),
        review=dict(reviewer='kookn-desk',approved=True,checkedAt=boxscores.stamp(NOW),why='Current rotation supports a slower matchup.',
            countercase='Hot shooting can beat this total.',availability='Both current team reports reviewed.',sources=[
                dict(teamId=t,url='https://team.example/preview',fact='Current role verified.',checkedAt=boxscores.stamp(NOW)) for t in ('1','2')]))

def context():
    return SimpleNamespace(now=NOW,games={},first={},latest={},risk_external={},risk_games={'CBB-123':fixture()['game']})

class CBBPicksTests(unittest.TestCase):
    def test_long_college_names_render_without_rewriting_fixture(self):
        import nba_trial,pick_card
        p=fixture();p['marketType']='spread';p['direction']='away';p['line']=11.5
        p['game']['teams']['away'].update(name='South Dakota State Jackrabbits',shortName='S Dakota St')
        p['game']['teams']['home'].update(name='Kansas State Wildcats',shortName='Kansas St')
        with tempfile.TemporaryDirectory() as d, patch.object(cbb,'public_rows',return_value=[p]), patch.object(pick_card,'render') as output:
            cbb.render(Path(d))
            svg=output.call_args.args[0]
            self.assertIn('S DAKOTA ST',svg)
            self.assertNotIn('SOUTH DAKOTA STATE JACKRABBITS',svg)
            self.assertEqual(p['game']['teams']['away']['name'],'South Dakota State Jackrabbits')

    def test_source_review_is_distinct_from_probability_approval(self):
        p=fixture();self.assertIsNone(cbb.refusal(p,NOW))
        for k in ('chance','rawChance','fairOdds','expectedValue','calibrated'):
            with self.subTest(k=k):self.assertIsNotNone(cbb.refusal(dict(p,**{k:.6}),NOW))

    def test_stale_wrong_side_missing_team_and_unsupported_market_hold(self):
        for change in ('stale','side','source','team','market','stake','tip'):
            p=fixture()
            if change=='stale':p['quote']['checkedAt']=boxscores.stamp(NOW-timedelta(hours=2))
            if change=='side':p['quote']['direction']='over'
            if change=='source':p['quote']['source']='https://draftkings.com.evil.example/quote'
            if change=='team':p['review']['sources'].pop()
            if change=='market':p['marketType']='player'
            if change=='stake':p['riskUnits']=2
            if change=='tip':p['game']['kickoff']=boxscores.stamp(NOW+timedelta(minutes=5))
            with self.subTest(change=change):self.assertIsNotNone(cbb.refusal(p,NOW))

    def test_original_terms_grade_and_private_quote_stay_separate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=fixture();self.assertEqual(cbb.admit(p,context(),NOW,root),1)
            with self.assertRaises(ValueError):cbb.admit(p,context(),NOW,root)
            public=json.dumps(cbb.payload(root));self.assertNotIn('/private/',public)
            final=dict(eventId='123',type=2,season=2027,kickoff=p['game']['kickoff'],home={'id':'1'},away={'id':'2'},
                       homeScore=80,awayScore=75,source='https://www.espn.com/final',retrievedAt='2026-11-04T03:00:00Z')
            later=datetime(2026,11,4,4,tzinfo=timezone.utc)
            self.assertEqual(cbb.grade(later,root,[final]),1)
            self.assertEqual(cbb.grade(later,root,[final]),0)
            self.assertEqual(cbb.payload(root)['loss'],1)
            self.assertEqual(cbb.payload(root)['units'],-1)
            final['awayScore']=65
            self.assertEqual(cbb.grade(later,root,[final]),1)
            self.assertEqual(cbb.payload(root)['win'],1)
            self.assertEqual(len([r for r in cbb.rows(root) if r['type']=='settle']),2)
            self.assertEqual(cbb.public_rows(root)[0]['odds'],-110)

    def test_future_final_is_not_graded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=fixture();cbb.admit(p,context(),NOW,root)
            f=dict(eventId='123',type=2,season=2027,kickoff=p['game']['kickoff'],home={'id':'1'},away={'id':'2'},
                homeScore=70,awayScore=60,source='https://example.com',retrievedAt='2026-11-04T04:00:00Z')
            self.assertEqual(cbb.grade(NOW,root,[f]),0)

    def test_shared_cap_includes_cbb_and_never_replenishes_after_loss(self):
        with tempfile.TemporaryDirectory() as d:
            ctx=context();ctx.risk_external={'old':dict(id='old',league='NBA',kickoff='2026-11-03T23:00:00Z',riskUnits=3,result='loss')}
            with self.assertRaisesRegex(ValueError,'shared exposure'):cbb.admit(fixture(),ctx,NOW,Path(d))

    def test_delivery_reservation_blocks_ambiguous_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=fixture();cbb.admit(p,context(),NOW,root)
            self.assertTrue(cbb.reserve_delivery(p['id'],NOW,root))
            self.assertFalse(cbb.reserve_delivery(p['id'],NOW,root))
            cbb.delivery_failed(p['id'],NOW,root)
            self.assertTrue(cbb.reserve_delivery(p['id'],NOW,root))

    def test_caption_keeps_exact_terms_units_playbook_and_age(self):
        text=cbb.caption(dict(fixture(),book='DraftKings'))
        self.assertIn('UNDER 150.5',text);self.assertIn('@Playbook',text)
        self.assertIn('21+ only',text);self.assertNotIn('/private/',text)

    def test_discord_queue_requires_live_art_and_preserves_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=fixture();cbb.admit(p,context(),NOW,root);log={'posts':[]}
            with patch('buffer_post.live_card_url',return_value=None):self.assertEqual(cbb.queue_discord(NOW,log,root),0)
            with patch('buffer_post.live_card_url',return_value='https://keenroudy.com/card.png'),patch('buffer_post.ticket_art_live',return_value=True),patch('buffer_post.plain_art_live',return_value=True):
                self.assertEqual(cbb.queue_discord(NOW,log,root),1)
                self.assertEqual(cbb.queue_discord(NOW,log,root),0)
            self.assertEqual(log['posts'][0]['discord']['destination'],'plays')
            self.assertNotIn('sentAt',log['posts'][0])

    def test_canonical_fixture_prevents_wrong_matchup(self):
        with tempfile.TemporaryDirectory() as d:
            p=fixture();p['game']['teams']['home']['id']='other';p['review']['sources'][0]['teamId']='other'
            with self.assertRaisesRegex(ValueError,'fixture'):
                cbb.admit(p,context(),NOW,Path(d))

    def test_result_uses_same_original_discord_destination_once(self):
        import discord_post
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=fixture();cbb.admit(p,context(),NOW,root)
            final=dict(eventId='123',type=2,season=2027,kickoff=p['game']['kickoff'],home={'id':'1'},away={'id':'2'},
                homeScore=80,awayScore=75,source='https://www.espn.com/final',retrievedAt='2026-11-04T03:00:00Z')
            later=datetime(2026,11,4,4,tzinfo=timezone.utc);cbb.grade(later,root,[final])
            log={'posts':[dict(id=p['id'],kind='buffer:cbb-pick',cbbPick=True,discord={'state':'sent','destination':'plays'})]}
            self.assertEqual(cbb.queue_results(log,later,root),1)
            sent=[]
            with patch('discord_post.send_message',side_effect=lambda url,text,**kw:sent.append((url,text))):
                discord_post.mirror_sent(log,later,url='plays',wins_url='wins',research_url='research')
                self.assertEqual(cbb.queue_results(log,later,root),0)
                discord_post.mirror_sent(log,later,url='plays',wins_url='wins',research_url='research')
            self.assertEqual(len(sent),1);self.assertEqual(sent[0][0],'plays')
            self.assertIn('Actual: 155',sent[0][1])

    def test_expired_queued_play_cancels_without_removing_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=fixture();cbb.admit(p,context(),NOW,root)
            later=NOW+timedelta(hours=2);cancel=[]
            e=dict(id=p['id'],kind='buffer:cbb-pick',bufferPostId='post',dueAt=boxscores.stamp(later+timedelta(minutes=10)))
            self.assertTrue(cbb.precheck(later,{'posts':[e]},root,delete=cancel.append))
            self.assertEqual(cancel,['post']);self.assertEqual(len(cbb.public_rows(root)),1)

if __name__=='__main__':unittest.main()
