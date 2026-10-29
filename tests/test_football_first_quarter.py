import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import football_first_quarter as q
import boxscores as bx


def play(pid, quarter, yards, role='rusher', aid='10', kind='Rush'):
    return {'id': str(pid), 'period': {'number': quarter}, 'type': {'text': kind},
            'statYardage': yards, 'start': {'team': {'$ref': '/teams/1'}},
            'participants': [{'type': role, 'athlete': {'$ref': '/athletes/' + aid}}]}


class FirstQuarterTests(unittest.TestCase):
    def setUp(self):
        self.plays = {'count': 4, 'items': [play(1,1,-2), play(2,2,12),
            {**play(3,1,8,'passer','20','Pass Reception'), 'participants': [
                {'type':'passer','athlete':{'$ref':'/athletes/20'}},
                {'type':'receiver','athlete':{'$ref':'/athletes/30'}}]},
            {**play(4,1,0,aid='40'), 'start':{'team':{'$ref':'/teams/2'}}}]}
        self.box = {'10': {'car':2,'rushYds':10}, '30': {'rec':1,'recYds':8},
                    '40': {'car':1,'rushYds':0}}
        self.teams = {'1':{'plays':3},'2':{'plays':1}}

    def test_period_splits_preserve_negative_and_zero_not_full_game(self):
        out=q.extract(self.plays,self.box,self.teams)
        self.assertEqual(out['10']['rushYds'],-2)
        self.assertEqual(out['40']['rushYds'],0)
        self.assertEqual(out['30']['recYds'],8)
        self.assertEqual(out['10']['rec'],0)
        self.assertEqual(self.box['10']['rushYds'],10)

    def test_missing_period_duplicate_partial_and_wrong_team_hold(self):
        for change in ('period','duplicate','partial','team'):
            p=copy.deepcopy(self.plays)
            if change=='period':p['items'][0].pop('period')
            if change=='duplicate':p['items'][1]['id']='1'
            if change=='partial':p['items'].pop()
            if change=='team':p['items'][0]['start']['team']['$ref']='/teams/99'
            self.assertEqual(q.extract(p,self.box,self.teams),{},change)

    def test_failed_player_family_is_unknown_others_remain(self):
        box=copy.deepcopy(self.box);box['10']['rushYds']=11
        out=q.extract(self.plays,box,self.teams)
        self.assertNotIn('rushYds',out['10'])
        self.assertEqual(out['30']['recYds'],8)

    def test_overtime_stays_out_of_first_quarter(self):
        self.plays['items'][1]['period']['number']=5
        self.assertEqual(q.extract(self.plays,self.box,self.teams)['10']['rushYds'],-2)

    def test_unavailable_play_feed_is_not_a_zero_sample(self):
        self.assertEqual(q.extract(None,self.box,self.teams),{})
        p=copy.deepcopy(self.plays);p['items'][3]['period']['number']=2
        self.assertEqual(q.extract(p,self.box,self.teams),{})

    def test_touchdown_with_appended_conversion_counts_only_touchdown(self):
        p=copy.deepcopy(self.plays)
        td=p['items'][2]
        td.update(type={'text':'Passing Touchdown'}, scoringType={'name':'touchdown'},
                  text='Pass for 8 yards, TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. Runner rushes. ATTEMPT SUCCEEDS.')
        td['participants'].append({'type':'patScorer','athlete':{'$ref':'/athletes/10'}})
        out=q.extract(p,self.box,self.teams)
        self.assertEqual(out['30']['recYds'],8)
        self.assertEqual(out['10']['car'],1)
        self.assertEqual(out['10']['rushYds'],-2)
        td['type']={'text':'Two-Point Conversion'}
        self.assertEqual(q.extract(p,self.box,self.teams),{})

    def test_ambiguous_snap_uses_exact_same_play_provider_stats(self):
        p=copy.deepcopy(self.plays)
        snap=p['items'][0]
        base='https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/100/competitions/100/plays/1'
        snap['participants'].append({'type':'passer','athlete':{'$ref':'/athletes/10'}})
        snap['participants'][0]['playStatistics']={'$ref':base+'/participants/10/statistics/0'}
        snap['teamParticipants']=[{'type':'offense','team':{'$ref':'/teams/1'},'playStatistics':{'$ref':base+'/teams/1/statistics/0'}}]
        def data(owner, values):
            return {'play':{'$ref':base},owner:{'$ref':'/athletes/10' if owner=='athlete' else '/teams/1'},
                    'splits':{'name':'play','categories':[{'stats':[{'name':k,'value':v} for k,v in values.items()]}]}}
        calls=[]
        def fetch(url):
            calls.append(url)
            return data('team',{'totalOffensivePlays':1}) if '/teams/' in url else data('athlete',{'rushingAttempts':1,'rushingYards':-2,'receptions':0,'receivingYards':0})
        out,evidence=q.resolve(p,self.box,self.teams,fetch)
        self.assertEqual(out['10']['rushYds'],-2)
        self.assertTrue(q.complete(self.box,out))
        self.assertEqual(len(calls),2)
        self.assertEqual(q.extract(p,self.box,self.teams,evidence),out)
        # A foreign host never becomes a request, and the missing split stays unknown.
        snap['teamParticipants'][0]['playStatistics']['$ref']='https://example.com/secret'
        calls.clear();out,_=q.resolve(p,self.box,self.teams,fetch)
        self.assertEqual(out,{})
        self.assertEqual(calls,[])

    def test_replay_spot_duplicate_requires_identical_snap_not_clock_alone(self):
        p=copy.deepcopy(self.plays)
        first=p['items'][0]
        first.update(text='Rush. The ball spot was assisted by replay.',wallclock='2026-09-01T17:00:00Z',drive={'$ref':'/drives/1'},clock={'value':800},statYardage=2)
        duplicate=copy.deepcopy(first);duplicate['id']='5'
        p['items'].append(duplicate);p['count']=5
        box=copy.deepcopy(self.box);box['10']['rushYds']=14
        self.assertEqual(q.extract(p,box,self.teams)['10']['rushYds'],2)
        duplicate['start']={'team':{'$ref':'/teams/1'},'down':2}
        self.assertEqual(q.extract(p,box,self.teams),{})

    def test_automatic_repair_appends_once_and_backs_off_held_games(self):
        import tempfile
        from datetime import datetime,timezone,timedelta
        now=datetime(2026,10,29,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            old={'league':'NFL','eventId':'100','season':2026,'seasonType':2,'kickoff':'2026-09-01T17:00:00Z',
                 'retrievedAt':'2026-09-02T12:00:00Z','revision':1,'teams':self.teams,
                 'players':[dict(id=aid,**stats) for aid,stats in self.box.items()],
                 'sources':{'plays':'https://example.org/plays'},'quality':{'plays':'ok','odds':'ok'}}
            old['hash']=bx.content_hash(old)
            bx.append(bx.store_path('NFL',2026,root),[old]);bx.write_json(root/'ledger.json',bx.ledger(root))
            status={};calls=[]
            def fetch(url):calls.append(url);return self.plays
            self.assertEqual(q.repair(status,now,root,fetch=fetch,log=lambda _:None),1)
            enriched=bx.stored(root)['100']
            self.assertEqual(enriched['officialRetrievedAt'],old['retrievedAt'])
            self.assertEqual(enriched['retrievedAt'],old['retrievedAt'])
            self.assertEqual(enriched['quarterCapturedAt'],bx.stamp(now))
            self.assertEqual(bx.due('100',old['kickoff'],{'100':enriched},{},now),'recheck')
            self.assertEqual(q.repair(status,now,root,fetch=fetch,log=lambda _:None),0)
            self.assertEqual(len(calls),1)
            self.assertEqual(bx.verify(root),[])
            # A second held game is retried after a day, not every scheduled run.
            old.update(eventId='101');old['hash']=bx.content_hash(old)
            bx.append(bx.store_path('NFL',2026,root),[old]);bx.write_json(root/'ledger.json',bx.ledger(root))
            held=[]
            def empty(url):held.append(url);return {}
            q.repair(status,now,root,fetch=empty,log=lambda _:None)
            q.repair(status,now+timedelta(hours=1),root,fetch=empty,log=lambda _:None)
            self.assertEqual(len(held),1)
            self.assertEqual(status['quarterRepair']['101']['state'],'held')
            q.repair(status,now+timedelta(days=1),root,fetch=empty,log=lambda _:None)
            self.assertEqual(len(held),2)

    def test_supplement_reads_are_bounded_and_wrong_play_responses_hold(self):
        import re
        p={'items':[],'count':200}
        for i in range(200):
            snap=play(i+1,1,2)
            snap['participants'].append({'type':'passer','athlete':{'$ref':'/athletes/10'}})
            snap['teamParticipants']=[{'type':'offense','team':{'$ref':'/teams/1'},'playStatistics':{'$ref':f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/100/competitions/100/plays/{i+1}/teams/1/statistics/0'}}]
            p['items'].append(snap)
        calls=[]
        def fetch(url):
            calls.append(url);pid=re.search(r'/plays/(\d+)/',url)[1]
            return {'play':{'$ref':'/plays/'+pid},'team':{'$ref':'/teams/1'},'splits':{'name':'play','categories':[{'stats':[{'name':'totalOffensivePlays','value':0}]}]}}
        d={};out,_=q.resolve(p,self.box,self.teams,fetch,d)
        self.assertEqual(out,{})
        self.assertEqual(len(calls),192)
        self.assertIn('request limit',d['error'])
        def wrong(url):
            result=fetch(url);result['play']['$ref']='/plays/999';return result
        out,_=q.resolve(p,self.box,self.teams,wrong)
        self.assertEqual(out,{})

    def test_lateral_recipient_gets_yards_without_a_manufactured_catch(self):
        p=copy.deepcopy(self.plays);box=copy.deepcopy(self.box)
        box['30']['team']='1';box['50']={'team':'1','rec':0,'recYds':5}
        snap=p['items'][2];snap.update(text='Pass complete. Lateral to teammate for 5 yards.',statYardage=13)
        base='https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/100/competitions/100/plays/3'
        snap['participants'].append({'type':'other','athlete':{'$ref':'/athletes/50'}})
        for v in snap['participants']:
            aid=bx.ref_id(v['athlete'],'athletes');v['playStatistics']={'$ref':base+f'/participants/{aid}/statistics/0'}
        snap['teamParticipants']=[{'type':'offense','team':{'$ref':'/teams/1'},'playStatistics':{'$ref':base+'/teams/1/statistics/0'}}]
        def fetch(url):
            if '/teams/' in url:owner='team';aid='1';values={'totalOffensivePlays':1}
            else:
                owner='athlete';aid=url.split('/participants/')[1].split('/')[0]
                values={'rushingAttempts':0,'rushingYards':0,'receptions':int(aid=='30'),'receivingYards':8 if aid=='30' else 5 if aid=='50' else 0}
            return {'play':{'$ref':base},owner:{'$ref':('/teams/' if owner=='team' else '/athletes/')+aid},'splits':{'name':'play','categories':[{'stats':[{'name':k,'value':v} for k,v in values.items()]}]}}
        out,_=q.resolve(p,box,self.teams,fetch)
        self.assertEqual(out['30']['rec'],1)
        self.assertEqual(out['30']['recYds'],8)
        self.assertEqual(out['50']['rec'],0)
        self.assertEqual(out['50']['recYds'],5)

    def test_bounded_backfill_rejects_fanout_before_network(self):
        with self.assertRaises(ValueError):q.backfill([str(n) for n in range(7)])
        with self.assertRaises(ValueError):q.backfill(['1','1'])

    def test_player_payload_keeps_q1_separate_from_full_game_and_source_clock(self):
        import build_site
        from datetime import datetime, timezone
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fakegames import game
        g=game('1',datetime(2026,9,7,17,tzinfo=timezone.utc),'A','B',24,17,
               players=[{'id':'10','name':'Player','pos':'RB','team':'A','car':12,'rushYds':70}])
        g['league']='NFL';g['firstQuarter']={'10':{'car':2,'rushYds':-1}}
        g['retrievedAt']='2026-09-08T12:00:00Z'
        _, shards, _, _=build_site.build_players('NFL',[g],{}, {})
        player=shards[10 % build_site.SHARDS['NFL']]['10']
        self.assertEqual(player['firstQuarter'][0]['stats']['rushYds'],-1)
        self.assertEqual(player['firstQuarter'][0]['checkedAt'],g['retrievedAt'])
        self.assertEqual(player['rows'][0][8+list(build_site.LOG_KEYS).index('rushYds')],70)
        self.assertEqual(build_site.build_players('CFB',[{**g,'league':'CFB'}],{}, {})[1][10 % build_site.SHARDS['CFB']]['10']['firstQuarter'], [])
