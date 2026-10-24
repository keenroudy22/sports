import copy
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_quarters as q
import nba_player_props
import boxscores
from test_nba_player_props import fixture, NOW


class QuarterTests(unittest.TestCase):
    def test_capture_keeps_period_prices_in_their_own_verified_store(self):
        game, rosters, rows, _ = fixture()
        calls=[]
        def feed(path,key,**params):
            calls.append(params)
            market = 'player_points' if params['market']=='props' else q.REQUEST_MARKET
            return {'data':[dict(r,market_type=market,sportsbook=params['sportsbook']) for r in rows]}
        with tempfile.TemporaryDirectory() as folder, patch.object(nba_player_props,'record_forward',return_value=0), patch.object(nba_player_props,'grade',return_value=0):
            root=Path(folder)
            boxscores.write_json(root/'slate.json',{'retrievedAt':boxscores.stamp(NOW),'games':[game]})
            (root/'rosters').mkdir()
            for team,row in rosters.items():boxscores.write_json(root/'rosters'/f'{team}.json',row)
            result=nba_player_props.capture(NOW,root,fetch=feed,sleep=lambda _:None,key='fixture')
            self.assertEqual(result['requests'],4)
            self.assertEqual(result['quarterPaired'],2)
            self.assertEqual(result['paired'],2)
            self.assertFalse(result['quarterPartial'])
            main=nba_player_props.saved(root/'player-quotes')
            quarters=nba_player_props.saved(root/'quarter-quotes')
            self.assertTrue(all('quarter' not in r for r in main))
            self.assertTrue(all(r['quarter']==1 and r['researchOnly'] for r in quarters))
            self.assertEqual(boxscores.verify(root/'quarter-quotes'),[])
            replay=nba_player_props.capture(NOW,root,fetch=feed,sleep=lambda _:None,key='fixture')
            self.assertEqual(replay['quarterCaptured'],0)

    def test_exact_period_pairs_keep_alternates_separate_and_cannot_enter_full_game(self):
        game, rosters, rows, _ = fixture()
        rows = [dict(r, market_type='1st_quarter_player_points', line=4.5) for r in rows]
        rows += [dict(r, line=2.5, is_alternate_line=True) for r in rows]
        paired = q.fold(rows, [game], rosters, NOW)
        self.assertEqual(len(paired), 2)
        self.assertEqual({r['kind'] for r in paired}, {'quarter-main', 'quarter-alternate'})
        self.assertTrue(all(r['quarter'] == 1 and r['researchOnly'] for r in paired))
        self.assertEqual(nba_player_props.fold(rows, [game], rosters, NOW)[0], [])
        self.assertEqual(q.fold(rows[:1], [game], rosters, NOW), [])
        self.assertEqual(q.fold([rows[0], dict(rows[1], market_type='2nd_quarter_player_points')], [game], rosters, NOW), [])

    def test_conflicting_periods_and_wrong_player_fail_closed(self):
        game, rosters, rows, _ = fixture()
        rows = [dict(r, market_type='1st_quarter_player_points') for r in rows]
        for field,value in [('quarter',2),('half',1),('period','full game'),('player_name','Unknown'),('is_live',True)]:
            self.assertEqual(q.fold([dict(r,**{field:value}) for r in rows], [game], rosters, NOW), [], field)
        self.assertIsNone(q.period_market({'market_type':'player_points'}))
        self.assertIsNone(q.period_market({'market_type':'3rd_quarter_player_points'}))

    def box(self):
        box={'eventId':'NBA-100','season':2027,'seasonType':2,'teams':{'8':{'score':6},'2':{'score':0}},
             'players':[{'id':'123','team':'8','stats':{'pts':6},'dnp':False}]}
        plays=[{'id':str(i),'period':{'number':i},'scoringPlay':True,'scoreValue':1 if i!=2 else 2,
                'team':{'id':'8'},'participants':[{'athlete':{'id':'123'}}]} for i in range(1,6)]
        return box, {'plays':plays}

    def test_official_period_totals_reconcile_with_overtime_separate(self):
        box,payload=self.box();saved=copy.deepcopy(payload)
        result,hold=q.points(payload,box)
        self.assertIsNone(hold)
        self.assertEqual([result['123'][str(i)]['pts'] for i in (1,2,5)], [1,2,1])
        self.assertEqual(payload,saved)
        self.assertEqual(q.points({'plays':payload['plays']+[payload['plays'][0]]},box)[0],result)
        box['players'][0]['quarters']=result['123']
        box.update(quarterEvidence={'status':'reconciled'},kickoff='2026-10-20T19:00:00Z',retrievedAt='2026-10-20T22:00:00Z',
            source='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=100')
        quote={'eventId':'100','athleteId':'123','team':'8','season':2027,'quarter':1,'stat':'pts','line':1.5,
               'kickoff':box['kickoff'],'retrievedAt':'2026-10-20T18:00:00Z'}
        self.assertEqual(q.compare(quote,box,'over')['result'],'miss')
        self.assertEqual(q.compare(dict(quote,quarter=2),box,'over')['result'],'hit')
        self.assertEqual(q.compare(dict(quote,line=1),box,'over')['result'],'push')
        self.assertIsNone(q.compare(dict(quote,quarter=5),box,'over'))
        self.assertIsNone(q.compare(dict(quote,eventId='other'),box,'over'))
        self.assertIsNone(q.compare(dict(quote,retrievedAt='2026-10-20T20:00:00Z'),box,'over'))
        self.assertIsNone(q.compare(quote,dict(box,quarterEvidence={'status':'held'}),'over'))
        box['players'][0]['dnp']=True
        self.assertIsNone(q.compare(quote,box,'under'))

    def test_partial_conflicting_unknown_scoring_never_becomes_zero(self):
        box,payload=self.box()
        variants=[{'plays':[]}, {'plays':payload['plays'][1:]},
            {'plays':payload['plays']+[dict(payload['plays'][0],scoreValue=3)]}]
        for field,value in [('participants',[]),('team',{'id':'2'}),('period',{'number':None})]:
            changed=copy.deepcopy(payload);changed['plays'][0][field]=value;variants.append(changed)
        for changed in variants:
            result,hold=q.points(changed,box)
            self.assertEqual(result,{})
            self.assertIsNotNone(hold)

    def test_capture_reuses_allowance_and_hosted_box_reuses_same_summary(self):
        source=Path(nba_player_props.__file__).read_text()
        self.assertIn("market=nba_quarters.REQUEST_MARKET",source)
        self.assertIn('if count>=12',source)
        self.assertIn("root/'quarter-quotes'",source)
        self.assertNotIn('quarter-quotes',source.split('def build(')[1].split('def record_forward')[0])

