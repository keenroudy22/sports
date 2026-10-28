"""Owner's model-winner requirement cannot be bypassed by cached value claims."""
import copy
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gates
from test_gates import context,total_lean,SNAPSHOT,GAME

NOW=datetime(2026,10,27,18,tzinfo=timezone.utc)


def inputs(home=.599,margin=3.4):
    snap=dict(SNAPSHOT,homeWinProb=home,margin=margin,publishedAt='2026-10-27T16:00:00Z',kickoff='2026-10-27T23:00:00Z')
    ctx=context(now=NOW,games={'NFL-1':dict(GAME,kickoff=snap['kickoff'])},snapshots={'NFL-1':[snap]})
    pick=total_lean(marketType='moneyline',direction='away',line=0,odds=180,
        selectionPolicy=gates.TIER_POLICY,
        _selection=dict(rawChance=.401,fairChance=.343,anchoredChance=.363,breakEven=1/2.8,gap=2),
        _planReasons=[dict(type='injury_role',**{'class':'A'},direction='for',text='Opposing starter is out.')])
    return pick,ctx


class MoneylineAgreementTests(unittest.TestCase):
    def test_sam_houston_shape_cannot_be_best_bet_even_with_positive_ev(self):
        pick,ctx=inputs()
        for lane in ('best_bet','chef_pick','hot_plate'):
            verdict=gates.selection_verdict(pick,ctx,lane)
            self.assertFalse(verdict.ok);self.assertEqual(verdict.rule,'moneyline_projection_agreement')
        spoof=dict(pick,_selection=dict(pick['_selection'],rawChance=.9,anchoredChance=.8))
        self.assertFalse(gates.selection_verdict(spoof,ctx).ok)

    def test_model_loser_is_rejected_before_spending_web_research(self):
        import run
        pick,ctx=inputs()
        self.assertEqual(run.pre_research_refusal(pick,ctx).rule,'moneyline_projection_agreement')
        pick,ctx=inputs(home=.4,margin=-3)
        self.assertIsNone(run.pre_research_refusal(pick,ctx))
        self.assertIsNone(run.pre_research_refusal(dict(pick,marketType='total'),ctx))
        self.assertIsNone(run.pre_research_refusal(dict(pick,selectionPolicy=None),ctx))

    def test_model_favorite_at_plus_money_remains_eligible_but_not_automatic(self):
        pick,ctx=inputs(home=.4,margin=-3)
        self.assertTrue(gates.moneyline_projection_agreement(pick,ctx).ok)
        pick['_selection']=dict(rawChance=.6,fairChance=.343,anchoredChance=.43,breakEven=1/2.8,gap=8.7)
        self.assertTrue(gates.selection_verdict(pick,ctx).ok)
        pick['_selection']['anchoredChance']=.35
        self.assertFalse(gates.selection_verdict(pick,ctx).ok)

    def test_inconsistent_tied_missing_and_invalid_forecasts_hold(self):
        for chance,margin in ((.5,0),(.4,3),(.6,-3),(None,-3),(float('nan'),-3),(True,-3),(.4,float('inf'))):
            pick,ctx=inputs(home=chance,margin=margin)
            self.assertFalse(gates.moneyline_projection_agreement(pick,ctx).ok,(chance,margin))
        pick,ctx=inputs();ctx.snapshots={}
        self.assertFalse(gates.moneyline_projection_agreement(pick,ctx).ok)

    def test_private_queued_release_rechecks_model_not_saved_positive_value(self):
        import run
        from types import SimpleNamespace
        pick,ctx=inputs();pick.update(quotedAt='2026-10-27T17:00:00Z',
            expiresAt='2026-10-27T21:00:00Z',riskUnits=.5,stakingPolicy=gates.staking.VERSION)
        row=dict(pick=pick,league='NFL',decision={'planReasons':pick['_planReasons']})
        with patch.object(gates,'daily_exposure',return_value=SimpleNamespace(ok=True)), \
             patch.object(gates,'fresh_quote',return_value=SimpleNamespace(ok=True)), \
             patch.object(gates,'exact_price_pairs',return_value=[dict(book='DraftKings',side=180)]):
            reason=run.private_release_refusal(row,ctx,NOW)
        self.assertIn('not the current projected winner',reason)

    def test_history_other_markets_and_fun_lanes_are_unchanged(self):
        pick,ctx=inputs();ctx.now=gates.MONEYLINE_ALIGNMENT_FROM.replace(hour=16)
        self.assertTrue(gates.moneyline_projection_agreement(pick,ctx).ok)
        ctx.now=NOW
        for market in ('spread','total'):
            self.assertTrue(gates.moneyline_projection_agreement(dict(pick,marketType=market),ctx).ok)
        self.assertTrue(gates.moneyline_projection_agreement(pick,ctx,'gut_call').ok)

if __name__=='__main__':unittest.main()
