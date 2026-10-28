import copy,sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_prop_settlement as n

NOW=datetime(2026,10,30,12,tzinfo=timezone.utc)
class NBAPropSettlementTests(unittest.TestCase):
    def data(self):
        p=dict(league='NBA',book='DraftKings',stat='pts',period='full_game',side='over',line=20.5,
            retrievedAt='2026-10-29T15:00:00Z',kickoff='2026-10-29T23:00:00Z',eventId='1',athleteId='2',team='3')
        player=dict(id='2',team='3',dnp=False,stats={'pts':10},quarters={str(i):{'minutes':6 if i<3 else 0} for i in range(1,5)})
        f=dict(league='NBA',seasonType=2,eventId='NBA-1',kickoff=p['kickoff'],retrievedAt='2026-10-30T02:00:00Z',
            players=[player],quarterWorkloadEvidence={'status':'reconciled'},source='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=1')
        review=dict(checked=True,source='https://www.nba.com/news/injury',eventId='1',athleteId='2',checkedAt='2026-10-30T02:30:00Z',status='injured',cause='injury',
            gameEndedAt='2026-10-30T01:30:00Z',statementAt='2026-10-30T01:40:00Z',statementSource='https://www.nba.com/team/news/injury')
        return p,f,review
    def test_primary_book_injury_void_is_distinct_from_raw_loss(self):
        p,f,r=self.data();out=n.evaluate(p,f,NOW,r)
        self.assertEqual(out['result'],'void');self.assertEqual(out['actual'],10)
        p['side']='under';p['line']=5.5
        self.assertEqual(n.evaluate(p,f,NOW,r)['result'],'loss')
    def test_dnp_and_crossed_over_are_not_injury_losses(self):
        p,f,r=self.data();f['players'][0]['dnp']=True
        self.assertEqual(n.evaluate(p,f,NOW)['result'],'void')
        f['players'][0]['dnp']=False;f['players'][0]['stats']['pts']=25
        self.assertEqual(n.evaluate(p,f,NOW)['result'],'win')
    def test_missing_participation_statement_or_book_terms_never_invent_void(self):
        p,f,r=self.data();early=datetime(2026,10,30,3,tzinfo=timezone.utc)
        self.assertEqual(n.evaluate(p,f,early)['state'],'held')
        for change in ({'statementSource':'https://unverified.example/news'},{'statementAt':'2026-10-30T05:00:00Z'},{'athleteId':'other'}):
            self.assertEqual(n.evaluate(p,f,early,dict(r,**change))['state'],'held')
        for field,value in [('book','FanDuel'),('period','Q1'),('stat','pra'),('paidProtection',True),('retrievedAt','2026-10-27T15:00:00Z')]:
            self.assertEqual(n.evaluate(dict(p,**{field:value}),f,NOW,r)['state'],'held')
        f['players'][0]['quarters'].pop('3')
        self.assertEqual(n.evaluate(p,f,NOW,r)['state'],'held')
    def test_returning_in_second_half_or_clean_review_uses_actual_result(self):
        p,f,r=self.data();f['players'][0]['quarters']['3']['minutes']=1
        self.assertEqual(n.evaluate(p,f,NOW,r)['result'],'loss')
        r['status']='no-injury'
        self.assertEqual(n.evaluate(p,f,datetime(2026,10,30,3,tzinfo=timezone.utc),r)['result'],'loss')
    def test_other_game_or_future_final_cannot_grade(self):
        p,f,r=self.data();f['eventId']='NBA-999'
        self.assertEqual(n.evaluate(p,f,NOW,r)['state'],'held')
        f['eventId']='NBA-1';f['retrievedAt']='2026-11-01T00:00:00Z'
        self.assertEqual(n.evaluate(p,f,NOW,r)['state'],'held')
