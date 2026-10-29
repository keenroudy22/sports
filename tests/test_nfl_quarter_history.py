import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nfl_quarter_history as q
import boxscores as bx


class QuarterFallbackTests(unittest.TestCase):
    def setUp(self):
        self.record={'league':'NFL','eventId':'100','season':2026,'seasonType':2,
          'kickoff':'2026-09-01T17:00:00Z','retrievedAt':'2026-09-02T12:00:00Z','revision':1,
          'home':{'id':'1','abbreviation':'A','score':10},'away':{'id':'2','abbreviation':'B','score':3},
          'teams':{'1':{'plays':3},'2':{'plays':1}},'sources':{'plays':'https://example.org/plays'},
          'players':[{'id':'10','team':'1','car':2,'rushYds':10},{'id':'30','team':'1','rec':1,'recYds':8},{'id':'40','team':'2','car':1,'rushYds':0}]}
        self.cross={f'G{x}':x for x in ['10','30','40']}
        base={'game_date':'2026-09-01','game_id':'2026_01_B_A','home_team':'A','away_team':'B','home_score':'10','away_score':'3',
              'season_type':'REG','season':'2026','two_point_attempt':'0','rush_attempt':'0','pass_attempt':'0','sack':'0','complete_pass':'0'}
        self.rows=[dict(base,play_id='1',qtr='1',posteam='A',rush_attempt='1',rusher_player_id='G10',rushing_yards='-2'),
                   dict(base,play_id='2',qtr='2',posteam='A',rush_attempt='1',rusher_player_id='G10',rushing_yards='12'),
                   dict(base,play_id='3',qtr='1',posteam='A',pass_attempt='1',complete_pass='1',receiver_player_id='G30',receiving_yards='8'),
                   dict(base,play_id='4',qtr='1',posteam='B',rush_attempt='1',rusher_player_id='G40',rushing_yards='0')]

    def test_full_game_reconciliation_preserves_zero_negative_and_overtime(self):
        out,holds=q.extract(self.rows,self.record,self.cross)
        self.assertEqual(holds,[]);self.assertEqual(out['10']['rushYds'],-2)
        self.assertEqual(out['40']['rushYds'],0)
        self.rows[1]['qtr']='5'
        self.assertEqual(q.extract(self.rows,self.record,self.cross)[0]['10']['rushYds'],-2)
        self.rows[0]['rushing_yards']='NA'
        self.assertEqual(q.extract(self.rows,self.record,self.cross)[0],{})

    def test_partial_duplicate_wrong_team_future_type_and_unknown_player_hold(self):
        for change in ['partial','duplicate','team','postseason','player','period','final','date']:
            rows=copy.deepcopy(self.rows)
            if change=='partial':rows.pop()
            if change=='duplicate':rows.append(rows[0])
            if change=='team':rows[0]['home_team']='C'
            if change=='postseason':rows[0]['season_type']='POST'
            if change=='player':rows[0]['rusher_player_id']='unknown'
            if change=='period':rows[0]['qtr']='NA'
            if change=='final':rows[0]['home_score']='11'
            if change=='date':rows[0]['game_date']='2026-09-02'
            self.assertEqual(q.extract(rows,self.record,self.cross)[0],{},change)

    def test_one_failed_family_does_not_hide_other_players(self):
        record=copy.deepcopy(self.record);record['players'][0]['rushYds']=11
        out,holds=q.extract(self.rows,record,self.cross)
        self.assertNotIn('rushYds',out['10']);self.assertEqual(out['30']['recYds'],8)
        self.assertEqual(holds,['10:car full-game mismatch'])
        # Even an asserted zero proof cannot excuse a nonzero Q1 or wrong count.
        out,_=q.extract(self.rows,record,self.cross,{('10','car')})
        self.assertNotIn('rushYds',out['10'])
        rows=copy.deepcopy(self.rows);rows[0]['qtr']='2'
        d={};out,holds=q.extract(rows,record,self.cross,{('10','car')},d)
        self.assertEqual(out['10']['car'],0);self.assertEqual(out['10']['rushYds'],0)
        self.assertEqual(holds,[]);self.assertTrue(d['zeroActivityExceptions'])
        record['players'][0]['car']=3
        self.assertNotIn('rushYds',q.extract(rows,record,self.cross,{('10','car')})[0]['10'])

    def test_lateral_yards_are_not_an_extra_catch_or_play(self):
        rows=copy.deepcopy(self.rows);record=copy.deepcopy(self.record)
        rows[2].update(lateral_reception='1',lateral_receiver_player_id='G50',lateral_receiving_yards='5')
        record['players'].append({'id':'50','team':'1','rec':0,'recYds':5})
        cross=dict(self.cross,G50='50')
        out,holds=q.extract(rows,record,cross)
        self.assertEqual(holds,[]);self.assertEqual(out['50']['rec'],0);self.assertEqual(out['50']['recYds'],5)
        rows.append(dict(rows[2],play_id='5',two_point_attempt='1'))
        self.assertEqual(q.extract(rows,record,cross)[0],out)

    def test_append_is_idempotent_and_keeps_prior_full_game_and_capture_age(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=copy.deepcopy(self.record);old['hash']=bx.content_hash(old)
            bx.append(bx.store_path('NFL',2026,root),[old]);bx.write_json(root/'ledger.json',bx.ledger(root))
            players=[{'gsis_id':g,'espn_id':e} for g,e in self.cross.items()]
            schedule=[{'espn':'100','game_id':'2026_01_B_A'}];now=datetime(2026,10,29,tzinfo=timezone.utc)
            result=q.refresh(2026,self.rows,players,schedule,root,now)
            self.assertEqual(result[0]['state'],'complete')
            new=bx.stored(root)['100'];self.assertEqual(new['players'],old['players']);self.assertEqual(new['teams'],old['teams'])
            self.assertEqual(new['retrievedAt'],old['retrievedAt']);self.assertEqual(new['officialRetrievedAt'],old['retrievedAt'])
            path=bx.store_path('NFL',2026,root);before=path.read_bytes()
            q.refresh(2026,self.rows,players,schedule,root,now)
            self.assertEqual(path.read_bytes(),before);self.assertEqual(bx.verify(root),[])
            self.assertEqual(json.loads(before.splitlines()[0]),old)
            # A temporarily missing season artifact retains verified stored splits.
            self.assertEqual(q.refresh(2026,[],players,schedule,root,now)[0]['state'],'held')
            self.assertEqual(path.read_bytes(),before)

    def test_independent_zero_proof_rejects_a_q1_rush_or_unknown_feed(self):
        from tests.test_football_first_quarter import play
        p={'count':4,'items':[play(1,2,-2),play(2,2,12),
           {**play(3,1,8,'passer','20','Pass Reception'),'participants':[{'type':'passer','athlete':{'$ref':'/athletes/20'}},{'type':'receiver','athlete':{'$ref':'/athletes/30'}}]},
           {**play(4,1,0,aid='40'),'start':{'team':{'$ref':'/teams/2'}}}]}
        self.assertTrue(q.no_first_quarter_activity(p,self.record,'10','car'))
        p['items'][0]['period']['number']=1
        self.assertFalse(q.no_first_quarter_activity(p,self.record,'10','car'))
        self.assertFalse(q.no_first_quarter_activity({},self.record,'10','car'))
    def test_existing_scheduled_job_reuses_crosswalk_and_schedule_and_keeps_failure_nonfatal(self):
        import contextlib,io
        from unittest.mock import patch
        import nflverse
        current=datetime.now(timezone.utc)
        season=current.year if current.month>=7 else current.year-1
        calls=[]
        def download(url):calls.append(url);return []
        def refresh(seasons,fetch,now):
            fetch(nflverse.GAMES);fetch(nflverse.PLAYERS)
            return {},[]
        with tempfile.TemporaryDirectory() as directory, patch.object(nflverse,'STORE',Path(directory)), patch.object(nflverse,'download',side_effect=download), patch.object(nflverse,'refresh',side_effect=refresh), patch.object(bx,'verify',return_value=[]), patch.object(bx,'ledger',return_value={}), patch.object(bx,'write_json'), patch.object(q,'refresh',return_value=[]) as fallback, contextlib.redirect_stdout(io.StringIO()):
            nflverse.main([])
            self.assertEqual(calls.count(nflverse.GAMES),1)
            self.assertEqual(calls.count(nflverse.PLAYERS),1)
            self.assertEqual(calls.count(q.PBP.format(season=season)),1)
            fallback.assert_called_once()
            fallback.reset_mock();calls.clear()
            def unavailable(url):
                if url==q.PBP.format(season=season):raise OSError('temporary provider outage')
                return download(url)
            with patch.object(nflverse,'download',side_effect=unavailable):
                nflverse.main([])
            fallback.assert_not_called()


    def test_official_recheck_preserves_verified_quarters_only_if_underlying_facts_match(self):
        old=copy.deepcopy(self.record);old['firstQuarter']=q.extract(self.rows,old,self.cross)[0]
        old.update(quarterProvider='nflverse',quarterCapturedAt='2026-10-29T12:00:00Z')
        current=copy.deepcopy(self.record);current['retrievedAt']='2026-10-30T12:00:00Z'
        bx.retain_quarter_history(old,current)
        self.assertEqual(current['firstQuarter'],old['firstQuarter'])
        self.assertEqual(current['retrievedAt'],'2026-10-30T12:00:00Z')
        self.assertEqual(current['players'],self.record['players'])
        corrected=copy.deepcopy(self.record);corrected['players'][0]['rushYds']=11
        bx.retain_quarter_history(old,corrected)
        self.assertNotIn('firstQuarter',corrected)
        incomplete=copy.deepcopy(old);incomplete['firstQuarter']['10'].pop('rushYds')
        target=copy.deepcopy(self.record);bx.retain_quarter_history(incomplete,target)
        self.assertNotIn('firstQuarter',target)

    def test_saved_zero_receipt_survives_independent_source_outage_but_not_new_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=copy.deepcopy(self.record)
            rows=copy.deepcopy(self.rows);rows[0]['qtr']='2'
            old['players'][0]['rushYds']=11
            proofs={('10','car')};d={}
            old['firstQuarter']=q.extract(rows,old,self.cross,proofs,d)[0]
            d.update(zeroActivitySource=old['sources']['plays'],zeroActivitySourceHash='a'*64)
            old.update(quarterProvider='nflverse',quarterDiagnostics=d,quarterHolds=[])
            old['hash']=bx.content_hash(old);bx.append(bx.store_path('NFL',2026,root),[old]);bx.write_json(root/'ledger.json',bx.ledger(root))
            players=[{'gsis_id':g,'espn_id':e} for g,e in self.cross.items()]
            schedule=[{'espn':'100','game_id':'2026_01_B_A'}];now=datetime(2026,10,29,tzinfo=timezone.utc)
            def down(url):raise OSError('source unavailable')
            result=q.refresh(2026,rows,players,schedule,root,now,proof_fetch=down)
            self.assertEqual(result[0]['state'],'complete')
            self.assertEqual(bx.stored(root)['100']['firstQuarter']['10']['rushYds'],0)
            rows[0]['qtr']='1'
            result=q.refresh(2026,rows,players,schedule,root,now,proof_fetch=down)
            self.assertEqual(result[0]['state'],'partial')
            self.assertNotIn('rushYds',bx.stored(root)['100']['firstQuarter']['10'])
