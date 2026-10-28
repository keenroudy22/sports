import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_trial as n
import staking
from test_nba_trial import offer

NOW=datetime(2026,10,28,16,tzinfo=timezone.utc)

class NBAMoneylineAgreementTests(unittest.TestCase):
    def pick(self):
        p=offer();p.update(marketType='moneyline',line=0,direction='away',odds=180,
            oppositeOdds=-210,rawChance=.62,kickoff='2026-10-28T23:00:00Z',
            retrievedAt='2026-10-28T15:00:00Z',modelSnapshot={'homeWinProb':.6,'margin':3.4})
        staking.apply(p,NOW)
        return p

    def test_positive_price_or_spoofed_chance_cannot_override_model_loser(self):
        p=self.pick()
        for chance in (.62,.99):
            p['rawChance']=chance
            holds=n.evaluate(p,[],NOW,preview_sent='2026-10-27T12:00:00Z')
            self.assertIn('moneyline/model direction hold',holds)

    def test_current_winner_required_in_both_score_and_probability(self):
        p=self.pick()
        for chance,margin in ((.4,-3),(.6,3)):
            p.update(direction='away' if chance<.5 else 'home',modelSnapshot={'homeWinProb':chance,'margin':margin})
            self.assertTrue(n.model_agreement(p))
        for chance,margin in ((.4,3),(.6,-3),(.5,0),(None,-3),(True,-3),(float('nan'),-3)):
            p.update(direction='away',modelSnapshot={'homeWinProb':chance,'margin':margin})
            self.assertFalse(n.model_agreement(p))
        p.pop('modelSnapshot');self.assertFalse(n.model_agreement(p))

    def test_historical_and_other_markets_do_not_change(self):
        p=offer();p.update(marketType='moneyline',line=0)
        self.assertNotIn('moneyline/model direction hold',n.evaluate(p,[],datetime(2026,10,20,14,tzinfo=timezone.utc)))
        p=self.pick();p['marketType']='total';self.assertTrue(n.model_agreement(p))
