import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chef_picks as chef
import gates
import run
import test_play_tiers

class ChefEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ctx=gates.Context(datetime(2026,12,10,tzinfo=timezone.utc))
        self.pick={'id':'new','league':'CFB','market':'rec','athleteId':'1','modelVersion':'v2.0',
                   'direction':'over','odds':-110,'gameIds':['new']}
        self.rows=[];self.grades=[]
        spec=chef.specification(self.pick,self.ctx)
        for i in range(40):
            kickoff=chef.FROM+timedelta(days=i+1)
            self.rows.append(dict(self.pick,id=str(i),gameIds=[str(i)],chance=.60,fairChance=.50,
                decidedAt=(kickoff-timedelta(hours=1)).isoformat(),quotedAt=(kickoff-timedelta(hours=1,minutes=5)).isoformat(),
                kickoff=kickoff.isoformat(),probabilitySpec=spec))
            self.grades.append(dict(id=str(i),result='loss' if i%4==0 else 'win',gradedAt=(kickoff+timedelta(hours=4)).isoformat()))
    def evidence(self,**kw):
        return chef.evidence(self.pick,self.ctx,{'anchoredChance':.60},kw.get('rows',self.rows),kw.get('grades',self.grades))
    def test_forward_evidence_and_buffer_at_actual_price(self):
        result=self.evidence();self.assertTrue(result['ok']);self.assertEqual(result['n'],40)
        self.assertEqual(result['errorAllowance'],.02);self.assertGreater(result['evPerUnit'],0)
        self.pick['odds']=-200;self.assertFalse(self.evidence()['ok'])
    def test_duplicate_books_players_and_repeats_cannot_inflate_games(self):
        self.assertEqual(self.evidence(rows=self.rows+self.rows)['n'],40)
        rows=copy.deepcopy(self.rows)
        for r in rows:r['gameIds']=['one-game']
        self.assertFalse(self.evidence(rows=rows)['ok'])
    def test_legacy_future_postgame_and_changed_model_not_evidence(self):
        for key,value in [('probabilitySpec','old'),('decidedAt','2026-12-11T00:00Z'),('quotedAt',None)]:
            rows=copy.deepcopy(self.rows)
            for r in rows:r[key]=value
            self.assertEqual(self.evidence(rows=rows)['n'],0)
        self.pick['modelVersion']='changed';self.assertEqual(self.evidence()['n'],0)
        grades=copy.deepcopy(self.grades)
        for g in grades:g['gradedAt']='2027-01-01T00:00Z'
        self.assertEqual(self.evidence(grades=grades)['n'],0)
    def test_worse_than_market_or_overconfident_probabilities_hold(self):
        grades=copy.deepcopy(self.grades)
        for i,g in enumerate(grades):g['result']='win' if i%2 else 'loss'
        self.assertFalse(self.evidence(grades=grades)['ok'])
    def test_actual_chooser_falls_back_without_upgrading_stake(self):
        fixture=test_play_tiers.PlayTierTests();fixture.setUp();fixture.ctx.now=self.ctx.now
        pick=fixture.pick(chance=.60,gap=6,modelVersion='v2.0')
        with patch.object(gates.spot,'for_candidate',return_value={'spotHit':.6,'n':40}),patch.object(chef,'evidence',return_value={'ok':False,'reason':'not enough forward evidence'}):
            self.assertTrue(run.choose_straight_tier(pick,fixture.ctx).ok)
        self.assertEqual((pick['lane'],pick['riskUnits']),('best_bet',.5))
        with patch.object(gates.spot,'for_candidate',return_value={'spotHit':.6,'n':40}),patch.object(chef,'evidence',return_value={'ok':True,'reason':'ok','policy':chef.VERSION}):
            self.assertTrue(run.choose_straight_tier(pick,fixture.ctx).ok)
        self.assertEqual((pick['lane'],pick['riskUnits']),('chef_pick',1))
        self.assertEqual(pick['chefEvidence']['policy'],chef.VERSION)

    def test_gate_rechecks_proof_and_grandfathers_only_trusted_published_history(self):
        fixture=test_play_tiers.PlayTierTests();fixture.setUp();fixture.ctx.now=self.ctx.now
        pick=fixture.pick(chance=.60,gap=6,modelVersion='v2.0')
        pick['chefEvidence']={'ok':True,'policy':chef.VERSION}
        with patch.object(gates.spot,'for_candidate',return_value={'spotHit':.6,'n':40}),patch.object(chef,'evidence',return_value={'ok':False,'reason':'held'}) as check:
            self.assertFalse(gates.selection_verdict(pick,fixture.ctx,'chef_pick').ok)
            check.assert_called_once()
            fixture.ctx.first[pick['id']]=dict(pick,publishedAt='2026-10-20T00:00Z')
            self.assertTrue(gates.selection_verdict(pick,fixture.ctx,'chef_pick').ok)
    def test_decision_record_saves_probability_spec_before_outcome(self):
        fixture=test_play_tiers.PlayTierTests();fixture.setUp();fixture.ctx.now=self.ctx.now
        pick=fixture.pick(chance=.60,gap=6,modelVersion='v2.0')
        fixture.ctx.games['NFL-game']={'kickoff':'2026-12-11T00:00Z','season':2026}
        row=run.decision_record(pick,'NFL','refused',[],'test',self.ctx.now,fixture.ctx)
        self.assertEqual(row['probabilityPolicy'],chef.VERSION)
        self.assertEqual(row['probabilitySpec'],chef.specification(pick,fixture.ctx))
        self.assertEqual(row['chance'],.60)

    def test_price_comparison_requires_same_book_exact_line_near_kickoff(self):
        p=dict(self.pick,kickoff='2026-12-01T23:00Z',quotedAt='2026-12-01T18:00Z',book='FanDuel',line=2.5,odds=110)
        q=dict(book='fanduel',line=2.5,direction='over',odds=-110,otherOdds=-110,retrievedAt='2026-12-01T22:45Z',source='https://source.test')
        r=chef.price_comparison(p,[q],self.ctx.now)
        self.assertGreater(r['edgePoints'],0);self.assertEqual(r['minutesBeforeKickoff'],15)
        for key,value in [('book','DraftKings'),('line',3.5),('retrievedAt','2026-12-01T23:05Z'),('retrievedAt','2026-12-01T20:00Z'),('direction','under')]:
            self.assertIsNone(chef.price_comparison(p,[dict(q,**{key:value})],self.ctx.now))
        self.assertIsNone(chef.price_comparison(p,[q,dict(q,odds=100)],self.ctx.now))
        self.assertIsNone(chef.price_comparison(p,[q],chef.instant('2026-12-01T22:59Z')))

    def test_build_record_exports_the_policy_and_price_comparison(self):
        import build_site
        p=dict(self.pick,lane='chef_pick',season=2026,quotedAt='2026-10-28T18:00Z',
               title='Player OVER 2.5 catches',line=2.5,book='FanDuel',chefEvidence={'policy':chef.VERSION,'n':40})
        with patch.object(chef,'stored_price_comparison',return_value={'odds':-110,'edgePoints':2.0}) as check:
            row=build_site.board_picks({'new':p},{},{'new':{'season':2026,'kickoff':'2026-10-28T23:00Z'}},{},self.ctx.now)[0]
        self.assertEqual(row['chefEvidence']['policy'],chef.VERSION)
        self.assertEqual(row['chefPriceComparison']['odds'],-110)
        self.assertEqual(check.call_args.args[1],self.ctx.now)

    def test_caption_guard_requires_the_frozen_proof_at_this_price(self):
        import x_post
        p=dict(self.pick,lane='chef_pick',riskUnits=1,selectionPolicy=gates.TIER_POLICY,
            publishedAt=self.ctx.now.isoformat(),probabilityAtPublication={'chance':.6,'breakEven':.524,'probabilitySpec':chef.specification(self.pick,self.ctx)})
        self.assertTrue(chef.publication_issues(p))
        p['chefEvidence']=self.evidence();self.assertEqual(chef.publication_issues(p),[])
        p['odds']=-200;self.assertTrue(chef.publication_issues(p))
        p['publishedAt']='2026-10-20T00:00Z';p.pop('chefEvidence');self.assertEqual(chef.publication_issues(p),[])
