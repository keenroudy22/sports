import sys,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_trial as nt
NOW=datetime(2026,10,20,14,tzinfo=timezone.utc)
def offer():return dict(id='NBA-trial-1',league='NBA',season=2027,seasonType=2,kickoff='2026-10-20T23:00:00Z',retrievedAt='2026-10-20T13:00:00Z',marketType='total',book='DraftKings',line=221.5,odds=-110,oppositeOdds=-110,sideVerified=True,exactLineVerified=True,roleChecked=True,rawChance=.59,riskUnits=1,source='https://www.espn.com/nba/')
class TrialTests(unittest.TestCase):
 def test_owner_cutover_removes_trial_daily_limit_without_weakening_value_or_identity(self):
  moment=datetime(2026,10,28,19,tzinfo=timezone.utc)
  row=offer();row.update(id='NBA-new',eventId='NBA-6',kickoff='2026-10-28T23:00:00Z',
      retrievedAt='2026-10-28T18:30:00Z',riskUnits=.5,stakingPolicy=nt.staking.VERSION)
  previous=[dict(row,id=f'NBA-{i}',eventId=f'NBA-{i}',type='publish') for i in range(4)]
  check=lambda offer=row,rows=previous:nt.evaluate(offer,rows,moment,preview_sent='2026-10-20T10:00:00Z')
  self.assertEqual(check(),[])
  self.assertEqual(nt.evaluate(row,previous,moment),[])
  self.assertIn('NBA daily pick cap',check(rows=previous+[dict(previous[0],id='fifth')]))
  self.assertIn('one NBA pick per game',check(offer=dict(row,eventId='NBA-1')))
  self.assertIn('edge hold',check(offer=dict(row,rawChance=.53)))
  self.assertIn('role/price hold',check(offer=dict(row,injuryHold=True)))
  self.assertIn('verified game identity required',check(offer=dict(row,eventId=None)))
  self.assertIn('stake policy mismatch',check(offer=dict(row,riskUnits=1)))
  self.assertEqual(nt.nba_pick_policy.label(moment),'NBA Picks')
  self.assertEqual(nt.nba_pick_policy.label(NOW),'NBA Trial')
 def evaluate(self,row=None,rows=None,**kw):return nt.evaluate(row or offer(),rows or [],NOW,preview_sent='2026-10-20T10:00:00Z',**kw)
 def test_raw_exact_price_floor_and_one_unit(self):
  self.assertEqual(self.evaluate(),[])
  for key,value in [('rawChance',.58),('riskUnits',2),('roleChecked',False),('sideVerified',False),('exactLineVerified',False),('priceHold',True),('injuryHold',True),('book','FanDuel')]:
   row=offer();row[key]=value;self.assertTrue(self.evaluate(row))
  for market,line in [('spread',-3.5),('moneyline',0)]:
   row=offer();row.update(marketType=market,line=line);self.assertEqual(self.evaluate(row),[])
  row=offer();row.update(marketType='total',line=-1);self.assertIn('line/source hold',self.evaluate(row))
  row=offer();row.update(marketType='moneyline',line=1);self.assertIn('line/source hold',self.evaluate(row))
 def test_low_price_still_needs_raw_chance_56(self):
  row=offer();row.update(odds=110,oppositeOdds=-110,rawChance=.55);self.assertIn('chance hold',self.evaluate(row))
 def test_calibration_must_be_verified_before_four_point_bar(self):
  row=offer();row.update(calibrated=True,chance=.565,rawChance=.58)
  self.assertIn('edge hold',self.evaluate(row));self.assertEqual(self.evaluate(row,calibration_verified=True),[])
 def test_today_and_first_veto_gate(self):
  self.assertIn('opening-night hold',nt.evaluate(offer(),[],NOW-timedelta(days=11),preview_sent='2026-10-01T00:00:00Z'))
  self.assertIn('first-card veto hold',nt.evaluate(offer(),[],NOW,preview_sent='2026-10-20T13:00:00Z'))
 def test_daily_cap_stale_quote_and_missing_opposite(self):
  self.assertIn('one play per day',self.evaluate(rows=[{**offer(),'type':'publish'}]))
  row=offer();row['retrievedAt']='2026-10-20T08:00:00Z';self.assertIn('price freshness hold',self.evaluate(row))
  row=offer();del row['oppositeOdds'];self.assertIn('missing verified evidence',self.evaluate(row))
 def test_separate_record_pause_and_review_need_real_graded_evidence(self):
  rows=[]
  for i in range(30):rows += [{'id':str(i),'type':'publish','odds':-110},{'id':str(i),'type':'settle','result':'loss','source':'ESPN final'}]
  self.assertTrue(nt.snapshot(rows)['paused']);self.assertFalse(nt.snapshot(rows)['promotionReview'])
  for row in rows:
   if row['type']=='settle':row['result']='win'
  self.assertTrue(nt.snapshot(rows)['promotionReview']);self.assertFalse(nt.snapshot(rows)['paused'])
  for row in rows:
   if row['type']=='settle':row.pop('source')
  self.assertEqual(nt.snapshot(rows)['graded'],0)
 def test_preview_uses_real_pair_and_never_calls_it_a_best_bet(self):
  game={'kickoff':'2026-10-20T23:00:00Z','teams':{'home':{'abbreviation':'NY','name':'New York Knicks'},'away':{'abbreviation':'SA','name':'San Antonio Spurs'}}}
  quote={'book':'DraftKings','retrievedAt':'2026-10-09T21:00:00Z','current':{'total':{'line':220.5,'over':-110,'under':-110}}}
  svg=nt.preview_svg(game,quote)
  self.assertIn('NBA TRIAL PREVIEW',svg);self.assertNotIn('BEST BET',svg);self.assertNotIn('ORDER UP',svg);self.assertTrue('NO PLAY' in svg and 'POSTED' in svg)
  quote['current']['total']['under']=-900
  with self.assertRaises(ValueError):nt.preview_svg(game,quote)
 def test_side_card_names_the_team_and_exact_market(self):
  game={'kickoff':'2026-10-20T23:00:00Z','teams':{'home':{'abbreviation':'NY','name':'New York Knicks'},'away':{'abbreviation':'SA','name':'San Antonio Spurs'}}}
  current={'home':{'moneyline':-120,'spreadLine':-2.5,'spreadPrice':-110},'away':{'moneyline':105,'spreadLine':2.5,'spreadPrice':-110}}
  money=nt.preview_svg(game,{'book':'DraftKings','retrievedAt':'2026-10-20T13:00:00Z','current':current},preview=False,direction='home',market='moneyline',line=0,odds=-120,reason='New York won four of five.')
  spread=nt.preview_svg(game,{'book':'DraftKings','retrievedAt':'2026-10-20T13:00:00Z','current':current},preview=False,direction='away',market='spread',line=2.5,odds=-110,reason='San Antonio covered four of five.')
  self.assertIn('NY MONEYLINE',money);self.assertIn('SA +2.5',spread)
if __name__=='__main__':unittest.main()
