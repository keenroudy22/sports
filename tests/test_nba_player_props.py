import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_player_props as n
import nba_capture,boxscores,nba_editorial

NOW=datetime(2026,10,20,12,30,tzinfo=timezone.utc)
STAMP=boxscores.stamp(NOW)


def fixture():
    teams={'home':{'id':'8','name':'Detroit Pistons','abbreviation':'DET'},
           'away':{'id':'2','name':'Boston Celtics','abbreviation':'BOS'}}
    game={'providerId':'100','season':2027,'status':'scheduled','seasonType':'regular-season',
          'kickoff':'2026-10-20T19:00:00Z','teams':teams}
    rosters={t['id']:{'team':t['id'],'season':2027,'retrievedAt':STAMP,'players':[]} for t in teams.values()}
    rosters['8']['players']=[{'id':'123','name':'Real Player','active':True}]
    base={'league':'nba','is_live':False,'is_active':True,'is_player_prop':True,'is_main_line':True,
          'sportsbook':'draftkings','market_type':'player_points','line':19.5,
          'timestamp':STAMP,'event_start_time':game['kickoff'],'home_team':'Detroit Pistons',
          'away_team':'Boston Celtics','player_name':'Real Player'}
    rows=[dict(base,selection_type='over',odds_american=-110),dict(base,selection_type='under',odds_american=-110)]
    boxes=[{'eventId':str(i),'season':2026,'seasonType':2,'kickoff':f'2026-04-{i+1:02}T00:00:00Z',
            'players':[{'id':'123','name':'Real Player','team':'8','dnp':False,
                        'stats':{'pts':24,'min':30,'ast':5,'reb':6}}]} for i in range(10)]
    return game,rosters,rows,boxes


class NBAPlayerPropTests(unittest.TestCase):
    def test_exact_pair_roster_and_price(self):
        g,r,rows,_=fixture();q,_=n.fold(rows,[g],r,NOW)
        self.assertEqual(len(q),1);self.assertEqual(q[0]['athleteId'],'123')
        self.assertEqual(q[0]['line'],19.5);self.assertEqual(q[0]['book'],'DraftKings')
        self.assertEqual(n.fold(rows[:1],[g],r,NOW)[0],[])
        self.assertEqual(n.fold(rows+[dict(rows[0],odds_american=-115)],[g],r,NOW)[0],[])
    def test_ambiguous_wrong_event_stale_roster_and_bad_prices_block(self):
        g,r,rows,_=fixture()
        for field,value in [('league','nfl'),('is_live',True),('is_active',False),('line',float('nan')),
                            ('is_alternate_line',True),('is_impossible_scoreline',True),
                            ('is_stale_pregame_price',True),('odds_american',-800),
                            ('timestamp','2026-10-19T00:00:00Z'),('home_team','Other team'),
                            ('event_start_time','2026-10-20T23:00:00Z')]:
            self.assertEqual(n.fold([dict(row,**{field:value}) for row in rows],[g],r,NOW)[0],[],field)
        r['2']['players']=copy.deepcopy(r['8']['players'])
        self.assertEqual(n.fold(rows,[g],r,NOW)[0],[])
        r['2']['players']=[];r['2']['retrievedAt']='2026-10-18T00:00:00Z'
        self.assertEqual(n.fold(rows,[g],r,NOW)[0],[])
    def test_pair_margin_and_main_rung_are_not_array_order(self):
        g,r,rows,_=fixture()
        extra=[dict(rows[0],line=14.5,odds_american=-350),dict(rows[1],line=14.5,odds_american=250)]
        q,_=n.fold(extra+list(reversed(rows)),[g],r,NOW)
        self.assertEqual(q[0]['line'],19.5)
        self.assertEqual(n.fold([dict(rows[0],odds_american=-400),rows[1]],[g],r,NOW)[0],[])
    def test_roster_requires_exact_team_season_and_unique_identity(self):
        p={'season':{'year':2027},'team':{'id':'8'},'athletes':[{'id':'123','displayName':'Real Player','active':False}]}
        self.assertFalse(n.roster(p,'8',2027,STAMP)['players'][0]['active'])
        p['athletes'][0].pop('active')
        self.assertFalse(n.roster(p,'8',2027,STAMP)['players'][0]['active'])
        p['athletes'][0]['status']={'type':'active'}
        self.assertTrue(n.roster(p,'8',2027,STAMP)['players'][0]['active'])
        for team,season in [('2',2027),('8',2026)]:
            with self.assertRaises(ValueError):n.roster(p,team,season,STAMP)
        p['athletes']*=2
        with self.assertRaises(ValueError):n.roster(p,'8',2027,STAMP)
    def test_baseline_is_minutes_times_own_rate_and_never_uses_line(self):
        _,_,_,boxes=fixture();logs=n.history(boxes,'123',NOW)
        p,hold=n.forecast(logs,'8',2027,'pts')
        self.assertIsNone(hold);self.assertEqual((p['value'],p['minutes'],p['rate']),(24,30,.8))
        self.assertEqual(p['window'],'Last season');self.assertEqual(p['season'],2026)
        self.assertNotIn('probability',p)
    def test_future_preseason_postseason_dnp_duplicates_excluded(self):
        _,_,_,b=fixture();base=n.history(b,'123',NOW)
        noisy=b+[b[0],dict(b[0],eventId='future',kickoff='2026-11-01T00:00:00Z'),
                 dict(b[0],eventId='pre',seasonType=1),dict(b[0],eventId='post',seasonType=3),
                 dict(b[0],eventId='dnp',players=[dict(b[0]['players'][0],dnp=True)])]
        self.assertEqual(n.history(noisy,'123',NOW),base)
    def test_changed_team_and_minutes_collapse_hold(self):
        _,_,_,b=fixture();logs=n.history(b,'123',NOW)
        self.assertIn('Changed teams',n.forecast(logs,'2',2027,'pts')[1])
        for h in logs[-3:]:h['stats']['min']=4
        self.assertIn('minutes fell',n.forecast(logs,'8',2027,'pts')[1])
    def test_partial_games_stay_in_hit_rates_not_full_role_rate(self):
        _,_,_,b=fixture();logs=n.history(b,'123',NOW)
        logs[0]['stats']={'pts':0,'min':2}
        p,_=n.forecast(logs,'8',2027,'pts');self.assertEqual(p['sample'],9)
        hits=n.hit_rate(logs,'pts',19.5,'over',10)
        self.assertEqual((hits['hits'],hits['games']),(9,10))
        self.assertEqual(n.hit_rate(logs,'pts',24,'under',5)['push'],5)
    def test_missing_nan_low_minutes_and_thin_samples_do_not_forecast(self):
        _,_,_,b=fixture();logs=n.history(b,'123',NOW)
        self.assertIsNone(n.forecast(logs[:4],'8',2027,'pts')[0])
        for h in logs:h['stats']['pts']=float('nan')
        self.assertIsNone(n.forecast(logs,'8',2027,'pts')[0])
        for h in logs:h['stats']={'pts':5,'min':5}
        self.assertIsNone(n.forecast(logs,'8',2027,'pts')[0])
    def test_current_season_is_not_blended_with_prior(self):
        _,_,_,b=fixture();logs=n.history(b,'123',NOW)
        new=[dict(h,season=2027,stats={'pts':12,'min':30}) for h in logs[:5]]
        p,_=n.forecast(logs+new,'8',2027,'pts')
        self.assertEqual((p['value'],p['season']),(12,2027))
    def write(self,root):
        g,r,rows,b=fixture();q,_=n.fold(rows,[g],r,NOW)
        boxscores.write_json(root/'slate.json',{'retrievedAt':STAMP,'games':[g]})
        boxscores.write_json(root/'injuries-current.json',{'retrievedAt':STAMP,'rows':[]})
        (root/'rosters').mkdir()
        for team,p in r.items():boxscores.write_json(root/'rosters'/f'{team}.json',p)
        nba_capture.append_changed(q,root/'player-quotes',lambda x:x['athleteId'])
        return b
    def test_public_rows_explain_projection_price_hit_sample_and_injury_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);b=self.write(root);q=n.build(NOW,root,b)['rows'][0]
            self.assertTrue(q['favorite']);self.assertEqual(q['projection']['value'],24)
            self.assertEqual(q['last10']['hits'],10);self.assertEqual(q['side'],'over')
            boxscores.write_json(root/'injuries-current.json',{'retrievedAt':STAMP,'rows':[{'athleteId':'123','status':'Out'}]})
            q=n.build(NOW,root,b)['rows'][0];self.assertIsNone(q['projection']);self.assertNotIn('favorite',q)
            self.assertIn('Out',q['hold'])
            self.assertEqual(n.build(NOW+timedelta(hours=5),root,b)['rows'],[])
    def test_stale_availability_holds_without_hiding_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);b=self.write(root)
            q=n.build(NOW+timedelta(hours=2),root,b)['rows'][0]
            self.assertIsNone(q['projection']);self.assertIn('Availability',q['hold'])
    def test_capture_has_free_bounded_book_fairness_and_append_only_store(self):
        g,r,rows,_=fixture();calls=[];waits=[]
        def feed(path,key,**params):
            calls.append(params)
            return {'data':[dict(x,sportsbook=params['sportsbook']) for x in rows],
                    'pagination':{'has_more':True,'next_cursor':str(len(calls))}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            boxscores.write_json(root/'slate.json',{'retrievedAt':STAMP,'games':[g]})
            (root/'rosters').mkdir()
            for team,p in r.items():boxscores.write_json(root/'rosters'/f'{team}.json',p)
            result=n.capture(NOW,root,fetch=feed,sleep=waits.append,key='fixture')
            self.assertEqual(result['requests'],12);self.assertTrue(result['partial'])
            self.assertEqual([c['sportsbook'] for c in calls[:2]],['draftkings','fanduel'])
            self.assertEqual(waits,[5.2]*12);self.assertEqual(result['paired'],2)
            self.assertEqual(boxscores.verify(root/'player-quotes'),[])
    def test_no_key_is_no_request(self):
        self.assertEqual(n.capture(NOW,key='')['requests'],0)
    def test_new_capture_cannot_be_read_with_run_start_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);b=self.write(root)
            self.assertEqual(n.build(NOW-timedelta(seconds=1),root,b)['rows'],[])
            self.assertTrue(n.build(NOW,root,b)['rows'][0]['projection'])
        import run
        source=Path(run.__file__).read_text()
        self.assertIn('nba_editorial.prepare(now if args.dry_run else datetime.now(timezone.utc))',source)
        self.assertIn('nba_player_props.capture(now if args.dry_run else datetime.now(timezone.utc))',source)
    def test_forward_forecast_is_frozen_and_grade_uses_matching_final_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);b=self.write(root)
            self.assertEqual(n.record_forward(NOW,root,b),1)
            self.assertEqual(n.record_forward(NOW,root,b),0)
            final=dict(b[-1],eventId='NBA-100',league='NBA',season=2027,kickoff='2026-10-20T19:00:00Z')
            self.assertEqual(n.grade(NOW,root,[final]),0)
            self.assertEqual(n.grade(NOW+timedelta(hours=10),root,[final]),1)
            self.assertEqual(n.grade(NOW+timedelta(hours=11),root,[final]),0)
            outcome=n.saved(root/'player-outcomes')[0]
            self.assertEqual((outcome['actual'],outcome['result']),(24,'hit'))
            self.assertEqual(boxscores.verify(root/'player-forecasts'),[])
    def test_walk_forward_error_is_unchanged_by_later_held_out_results(self):
        _,_,_,b=fixture();b=[dict(x,league='NBA') for x in b]
        result=n.evaluate(b)
        self.assertGreater(result['predictions'],0);self.assertEqual(result['meanAbsoluteError'],0)
        self.assertIn('no historical prices',result['scope'])
        self.assertEqual(n.evaluate(b[:5])['predictions'],0)
    def test_prop_social_freezes_only_after_morning_refresh_and_lists_every_player(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);b=self.write(root);q=n.build(NOW,root,b)['rows'][0]
            other=dict(q,name='Other Player',athleteId='456')
            data={'sourceAt':STAMP,'playerProps':{'rows':[q,other]}}
            row=nba_editorial.prop_choice(data,NOW)
            self.assertIsNotNone(row);self.assertEqual(row['due'],'2026-10-20T13:15:00Z')
            self.assertIn('Real Player',row['text']);self.assertIn('Other Player',row['text'])
            self.assertIn('Last season',row['text']);self.assertNotIn('100%',row['text'])
            self.assertIsNone(nba_editorial.prop_choice(data,NOW-timedelta(days=1)))
            with patch.object(n,'build',return_value={'rows':[q,other]}):self.assertTrue(nba_editorial.props_current(row,NOW))
            with patch.object(n,'build',return_value={'rows':[dict(q,hold='Out'),other]}):self.assertFalse(nba_editorial.props_current(row,NOW))


if __name__=='__main__':unittest.main()
