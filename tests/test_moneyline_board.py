import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_site

class MoneylineBoardTests(unittest.TestCase):
    def test_multibook_spread_capture_does_not_hide_moneyline_pair(self):
        now=datetime(2026,10,22,11,tzinfo=timezone.utc)
        game=dict(id='NFL-fixture',league='NFL',state='pre',kickoff='2026-10-23T00:15:00Z',
            home={'abbreviation':'CHI'},away={'abbreviation':'NE'},
            marketRetrievedAt='2026-10-22T10:55:00Z',market=dict(provider='DraftKings',
            spread='-3',spreadOdds='-110',total=50.5,overOdds='-110',underOdds='-110',homeML='-155',awayML='+130'))
        record=dict(retrievedAt='2026-10-22T10:50:00Z',books={'draftkings':dict(title='DraftKings',
            spread=dict(home=-3,homePrice=-110,awayPrice=-110),total=dict(line=50.5,over=-110,under=-110))})
        rows=build_site.game_market_lines({'games':[game]},now,{'NFL-fixture':record})
        ml=[r for r in rows if r['market']=='moneyline']
        self.assertEqual(len(ml),2)
        away=next(r for r in ml if r['side']=='away')
        self.assertEqual((away['odds'],away['oppositeOdds'],away['observedAt']),(130,-155,'2026-10-22T10:55:00Z'))
        self.assertEqual(len([r for r in rows if r['market']=='point spread']),2)
        self.assertEqual(len([r for r in rows if r['market']=='total points']),2)
        self.assertEqual(len({r['id'] for r in rows}),len(rows))
        game['market'].pop('awayML')
        self.assertFalse(any(r['market']=='moneyline' for r in build_site.game_market_lines({'games':[game]},now,{'NFL-fixture':record})))
