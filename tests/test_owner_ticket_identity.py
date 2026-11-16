import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gates, community_record

class OwnerTicketIdentityTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,16,23,tzinfo=timezone.utc)
        self.ticket={'id':'community:personal-ticket:2026-11-16-mnf-q1','personalTicket':True,
          'league':'NFL','status':'active','quotedAt':'2026-11-16T22:43:04Z',
          'kickoff':'2026-11-17T01:15Z','title':'MNF 1Q','odds':170,'riskUnits':.25,
          'legs':[{'title':'Omarion Hampton 5+ rushing yards — 1Q','gameId':'NFL-401873065',
                   'athleteId':'4685382','period':'1Q','alternate':True},
                  {'title':'Derrick Henry 20+ rushing yards — 1Q','gameId':'NFL-401873065',
                   'athleteId':'3043078','period':'1Q','alternate':True}]}
        self.ctx=SimpleNamespace(now=self.now,first={},latest={},risk_external={self.ticket['id']:self.ticket})

    def test_owner_quarter_ticket_blocks_same_players_across_market_period_and_book(self):
        for player in ('4685382','3043078'):
            c={'id':'new-straight','gameIds':['NFL-401873065'],'athleteId':player,
               'market':'recYds','period':'full_game','book':'FanDuel'}
            self.assertFalse(gates.player_overlap(c,self.ctx).ok)
            self.assertTrue(gates.player_overlap(dict(c,gameIds=['NFL-OTHER']),self.ctx).ok)
        self.assertTrue(gates.player_overlap(self.ticket,self.ctx).ok)
        self.ticket['status']='withdrawn'
        self.assertTrue(gates.player_overlap(c,self.ctx).ok)

    def test_exact_owner_quote_reserves_only_its_league_weekly_alt_allowance(self):
        c={'id':'next','league':'NFL','legs':[{'alternate':True}]}
        self.assertFalse(gates.alternate_parlay_frequency(c,self.ctx).ok)
        self.assertTrue(gates.alternate_parlay_frequency(dict(c,league='CFB'),self.ctx).ok)
        self.assertTrue(gates.alternate_parlay_frequency(dict(c,parlayType='ladder'),self.ctx).ok)
        self.ticket['quotedAt']=gates.stamp(self.now-timedelta(days=7))
        self.assertTrue(gates.alternate_parlay_frequency(c,self.ctx).ok)

    def test_structured_and_legacy_legs_render_exact_titles_without_nested_private_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            t=dict(self.ticket,legs=[dict(self.ticket['legs'][0],privateSource='never publish'), 'Legacy exact leg'])
            (root/'data/community.json').write_text(json.dumps({'tickets':[t]}))
            (root/'data/x-posted.json').write_text(json.dumps({'posts':[{'id':t['id'],
                'sentAt':'2026-11-16T23:01Z','link':'https://x.com/test/status/123456789'}]}))
            row=community_record.build(root)[0]
            self.assertEqual(row['legs'],[{'title':t['legs'][0]['title']},{'title':'Legacy exact leg'}])
            self.assertNotIn('privateSource',json.dumps(row))
            self.assertEqual(json.loads((root/'data/community.json').read_text())['tickets'][0],t)
