import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cbb_today as c
NOW=datetime(2026,11,2,15,tzinfo=timezone.utc)
G=dict(id='CBB-1',date='2026-11-02',season=2027,kickoff='2026-11-02T23:00Z',status='scheduled',neutral=True,teams={
    'home':dict(id='1',name='Home',shortName='Home',abbreviation='H'),
    'away':dict(id='2',name='Away',shortName='Away',abbreviation='A')})
class Model:
    def key(self,k):return k
    def predict(self,h,a,neutral):
        assert neutral is True
        return dict(margin=4,total=140,sparse=True,homeWinProb=.62)
class CbbTests(unittest.TestCase):
    def build(self,games=None,records=None,checked='2026-11-02T14:00Z',factory=None,local_spreads=None):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'site/data';p.mkdir(parents=True)
            (p/'sports.json').write_text(json.dumps({'leagues':{'CBB':dict(status='ok',checkedAt=checked,games=games or [G])}}))
            if local_spreads is not None:
                paper=Path(t)/'data/paper';paper.mkdir(parents=True)
                (paper/'cbb-spreads.json').write_text(json.dumps(local_spreads))
            return c.build(NOW,Path(t),records=records or [],model_factory=factory or (lambda *a,**k:Model()))
    def test_neutral_projection_and_unknown_stats_are_not_zero(self):
        g=self.build()['games'][0]
        self.assertEqual(g['projection']['home'],72)
        self.assertIsNone(g['stats']['home']['current']['ppg'])
        self.assertEqual(g['stats']['home']['current']['games'],0)
    def test_probability_uses_model_output_and_missing_invalid_stays_unknown(self):
        self.assertEqual(self.build()['games'][0]['projection']['winProb'],.62)
        for chance in (None,True,-.1,1.1,float('nan')):
            class Missing(Model):
                def predict(self,*a):return dict(margin=4,total=140,homeWinProb=chance)
            self.assertNotIn('winProb',self.build(factory=lambda *a,**k:Missing())['games'][0]['projection'])
    def test_unknown_venue_stale_schedule_and_past_tip_never_project(self):
        for g,checked in [(dict(G,neutral=None),'2026-11-02T14:00Z'),(G,'2026-10-30T14:00Z')]:
            self.assertNotIn('projection',self.build([g],checked=checked)['games'][0])
        self.assertEqual(self.build([dict(G,kickoff='2026-11-02T14:00Z')])['games'],[])
    def test_cbb_spread_uses_its_own_observation_time(self):
        spread = dict(book='DraftKings', observedAt='2026-11-02T12:00Z', homeLine=-3.5,
                      awayLine=3.5, homeOdds=-108, awayOdds=-112)
        game = dict(G, spreadQuote=dict(spread, link='ignored'))
        self.assertEqual(self.build([game])['games'][0]['spreadQuote'], spread)
        for observed in ('2026-11-02T10:59Z', '2026-11-02T15:01Z', '2026-11-02T14:00', None):
            game['spreadQuote']['observedAt'] = observed
            self.assertNotIn('spreadQuote', self.build([game])['games'][0])
        self.assertNotIn('spreadQuote', self.build([dict(game, timeConfirmed=False)])['games'][0])

    def test_local_spread_matches_the_schedule_and_keeps_the_newest_quote(self):
        local = dict(book='DraftKings', observedAt='2026-11-02T14:55Z', homeLine=-4.5,
                     awayLine=4.5, homeOdds=-115, awayOdds=-105)
        hosted = dict(local, observedAt='2026-11-02T14:00Z', homeLine=-3.5, awayLine=3.5)
        game = dict(G, spreadQuote=hosted)
        captured = dict(kickoff='2026-11-02T23:00:00Z', teams={'home':'1','away':'2'}, spreadQuote=local)
        def quote(offer, schedule=game):
            return self.build([schedule],local_spreads={G['id']:offer})['games'][0].get('spreadQuote')
        self.assertEqual(quote(captured),local)
        self.assertEqual(quote(captured,G),local)
        self.assertEqual(quote(dict(captured,teams={'home':'2','away':'1'})),hosted)
        self.assertEqual(quote(dict(captured,kickoff='2026-11-02T22:00Z')),hosted)
        self.assertEqual(quote(dict(captured,spreadQuote=dict(local,observedAt='2026-11-02T10:55Z'))),hosted)
        self.assertEqual(quote(dict(captured,spreadQuote=dict(local,observedAt='2026-11-02T15:01Z'))),hosted)

    def test_sparse_unmapped_school_is_not_average_division_one(self):
        class Unknown(Model):
            def key(self,k):return '~small'
        g=self.build(factory=lambda *a,**k:Unknown())['games'][0]
        self.assertNotIn('projection',g)
    def test_future_received_finals_cannot_supply_stats_or_model_inputs(self):
        r=dict(season=2027,type=2,kickoff='2026-11-01T15:00Z',retrievedAt='2026-11-02T16:00Z',home={'id':'1'},away={'id':'2'},homeScore=80,awayScore=70)
        def factory(*a,**k):self.assertEqual(k['records'],[]);return Model()
        self.assertEqual(self.build(records=[r],factory=factory)['games'][0]['stats']['home']['current']['games'],0)
    def test_prior_and_current_stats_keep_separate_samples(self):
        r=dict(season=2026,type=2,kickoff='2026-01-01T15:00Z',retrievedAt='2026-01-01T18:00Z',home={'id':'1'},away={'id':'2'},homeScore=80,awayScore=70)
        s=self.build(records=[r])['games'][0]['stats']['home']
        self.assertEqual(s['prior']['ppg'],80);self.assertIsNone(s['current']['ppg'])
    def test_sheets_paginate_and_never_export_unavailable_projection(self):
        g=self.build()['games'][0];data={'games':[dict(g,id=str(i)) for i in range(25)]+[dict(G,hold='unavailable')]}
        files,links=c.exports(data)
        self.assertEqual([x['games'] for x in links],[12,12,1])
        self.assertIn('06:00 PM ET',next(iter(files.values())))
        self.assertIn('not injury/roster adjusted',next(iter(files.values())))
