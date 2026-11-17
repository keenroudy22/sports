import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gates,run,release_queue

NOW=datetime(2026,10,22,15,30,tzinfo=timezone.utc)

class MoneylineReleaseTests(unittest.TestCase):
    def test_persisted_college_spread_rechecks_current_projection_without_private_cache(self):
        for side, margin, home_line in (('home', 17, -10), ('away', -17, 10)):
            now = datetime(2026,11,17,17,tzinfo=timezone.utc)
            game = {'id':'CFB-g','league':'CFB','state':'pre','kickoff':'2026-11-18T00:00:00Z',
                    'home':{'id':'h'},'away':{'id':'a'}}
            ctx = gates.Context(now=now,games={'CFB-g':game},odds={'CFB-g':{
                'gameId':'CFB-g','retrievedAt':gates.stamp(now),'books':{'draftkings':{
                    'spread':{'home':home_line,'homePrice':-110,'awayPrice':-110}}}}})
            pick = {'id':'spread','gameIds':['CFB-g'],'league':'CFB','marketType':'spread',
                    'direction':side,'line':-10,'book':'DraftKings','odds':-110,
                    'selectionPolicy':gates.TIER_POLICY,'lane':'best_bet','riskUnits':1,
                    'quotedAt':gates.stamp(now),'expiresAt':gates.stamp(now+timedelta(hours=1)),
                    '_desk':{'rawChance':.75,'projection':margin,'push':0}}
            decision = {'id':'spread','decision':'published','planReasons':[
                {'type':'news','class':'A','direction':'for','text':'Synthetic verified opponent role change.'}]}
            with tempfile.TemporaryDirectory() as folder:
                release_queue.enqueue(Path(folder),[('CFB','gamePicks',pick)],{},[decision],
                                      Path(folder),now,games=ctx.games,log=lambda *_:None)
                row = release_queue.load(Path(folder))['plays'][0]
            self.assertNotIn('_desk',row['pick'])
            with self.subTest(side=side), patch.object(gates,'desk_for',return_value=pick['_desk']):
                self.assertIsNone(run.private_release_refusal(row,ctx,now))
            for current in (None, margin/abs(margin)*15.9):
                with self.subTest(side=side,current=current), patch.object(gates,'desk_for',
                        return_value={'rawChance':.75,'projection':current,'push':0}):
                    self.assertIn('6 points',run.private_release_refusal(row,ctx,now))
            ctx.odds['CFB-g']['books']['draftkings']['spread'][side+'Price'] = -120
            with patch.object(gates,'desk_for',return_value=pick['_desk']):
                self.assertIn('exact book/line/price',run.private_release_refusal(row,ctx,now))

    def data(self):
        game={'id':'NFL-g','league':'NFL','state':'pre','kickoff':'2026-10-23T00:15:00Z',
              'marketRetrievedAt':gates.stamp(NOW-timedelta(minutes=5)),
              'market':{'provider':'DraftKings','homeML':'-155','awayML':'+130'},
              'home':{'id':'h'},'away':{'id':'a'}}
        ctx=gates.Context(now=NOW,games={'NFL-g':game})
        pick={'id':'ml','gameIds':['NFL-g'],'league':'NFL','marketType':'moneyline',
              'direction':'away','line':0,'book':'DraftKings','odds':130,
              'selectionPolicy':gates.TIER_POLICY,'lane':'best_bet','riskUnits':1,
              'quotedAt':gates.stamp(NOW-timedelta(minutes=10)),
              'expiresAt':gates.stamp(NOW+timedelta(minutes=30)),
              '_pair':[130,-155]}
        return game,ctx,pick

    def test_persisted_private_moneyline_reloads_both_actual_prices(self):
        game,ctx,pick=self.data()
        with tempfile.TemporaryDirectory() as tmp:
            release_queue.enqueue(Path(tmp),[('NFL','lean',pick)],{},[],Path(tmp),NOW)
            row=release_queue.load(Path(tmp))['plays'][0]
        self.assertNotIn('_pair',row['pick'])
        row['decision']={'planReasons':[{'class':'A','type':'injury','direction':'for',
                                        'text':'Verified opponent starter is ruled out.'}]}
        desk={'rawChance':.534,'chance':.534,'push':0,'projection':.5}
        with patch.object(gates,'desk_for',return_value=desk):
            self.assertIsNone(run.private_release_refusal(row,ctx,NOW))
        self.assertEqual(gates.exact_price_pairs(row['pick'],ctx)[0]['other'],-155)
        self.assertEqual(gates.quotes_for(row['pick'],ctx),[('DraftKings',0,130)])

    def test_missing_stale_future_and_comparison_only_pairs_still_hold(self):
        for change in ('missing-side','missing-time','stale','future','missing-book','comparison'):
            game,ctx,pick=self.data();pick.pop('_pair')
            if change=='missing-side':game['market'].pop('homeML')
            if change=='missing-time':game.pop('marketRetrievedAt')
            if change=='stale':game['marketRetrievedAt']=gates.stamp(NOW-timedelta(hours=3))
            if change=='future':game['marketRetrievedAt']=gates.stamp(NOW+timedelta(minutes=1))
            if change=='missing-book':game['market'].pop('provider')
            if change=='comparison':game['market']['provider']='Hard Rock Bet'
            self.assertEqual(gates.exact_price_pairs(pick,ctx),[],change)

    def test_changed_price_wrong_book_and_wrong_side_never_reuse_saved_chance(self):
        for change in ('price','book','side'):
            game,ctx,pick=self.data();pick.pop('_pair')
            if change=='price':game['market']['awayML']='+125'
            if change=='book':pick['book']='FanDuel'
            if change=='side':pick['direction']='home'
            with patch.object(gates,'desk_for',return_value={'rawChance':.534,'push':0}):
                self.assertIsNone(gates.selection_numbers(pick,ctx),change)
