import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import boxscores,nba_capture,nba_opportunities as n,next_day_prep
NOW=datetime(2026,11,3,20,tzinfo=timezone.utc)


def packet(kind='passing',window='season'):
    cells=['Test Player','BOS','5','3','2','30.0']+(['40','30','4','1','8','9','5','10','12'] if kind=='passing' else ['7','2','30','12','50','1','60','6'])
    if window=='last3':cells[2:5]=['3','2','1']
    return dict(source=f'https://www.nba.com/stats/players/{kind}'+('?LastNGames=3' if window=='last3' else ''),
        observedAt='2026-11-03T19:00:00Z',controls=dict(season='2026-27',seasonType='Regular Season',perMode='Per Game',segment='Last 3 Games' if window=='last3' else 'All Season Segments',page='All'),
        headers=n.HEADERS[kind],rows=[dict(cells=cells,playerUrl='/stats/player/123/'+('rebounds-dash/' if kind=='rebounding' else '')+'?Season=2026-27&SeasonType=Regular Season')])


def roster():
    return dict(league='NBA',team='2',season=2027,retrievedAt='2026-11-03T19:00:00Z',abbreviation='BOS',players=[dict(id='9',name='Test Player',active=True)])


class OpportunityTests(unittest.TestCase):
    def tables(self):
        return {(2027,k,w):n.normalize(packet(k,w),NOW) for k in n.HEADERS for w in ('season','last3')}

    def test_intake_preserves_original_clock_is_idempotent_and_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);packets=[packet(),packet(window='last3')];before=copy.deepcopy(packets)
            self.assertEqual(n.ingest(packets,NOW,root),2)
            self.assertEqual(n.ingest(packets,NOW,root),0)
            self.assertEqual(packets,before)
            rows=n.observations(root,NOW);self.assertEqual(len(rows),2)
            self.assertEqual(rows[(2027,'passing','season')]['retrievedAt'],packets[0]['observedAt'])
            self.assertEqual(boxscores.verify(root/'tracking'),[])
            bad=packet('rebounding');bad['controls']['page']='1'
            with self.assertRaises(ValueError):n.ingest([packet('rebounding','last3'),bad],NOW,root)
            self.assertEqual(len(n.observations(root,NOW)),2)

    def test_observed_rounded_zero_minutes_are_retained_without_a_rate_division(self):
        p=packet();p['rows'][0]['cells'][5]='0.0'
        row=n.normalize(p,NOW)['rows'][0]
        self.assertEqual(row['minutes'],0)
        self.assertEqual(row['metrics']['potentialAssists'],8)
        self.assertNotIn('perMinute',row)

    def test_wrong_filters_source_future_stale_columns_and_nonfinite_hold(self):
        for change in ('future','stale','source','season','mode','window','page','headers','nan','sample','identity','duplicate'):
            p=copy.deepcopy(packet())
            if change=='future':p['observedAt']='2026-11-03T20:01:00Z'
            elif change=='stale':p['observedAt']='2026-11-01T19:00:00Z'
            elif change=='source':p['source']='https://evil.example/stats/players/passing'
            elif change=='season':p['controls']['season']='2025-26'
            elif change=='mode':p['controls']['perMode']='Totals'
            elif change=='window':p['source']+='?LastNGames=5'
            elif change=='page':p['controls']['page']='1'
            elif change=='headers':p['headers']=list(reversed(p['headers']))
            elif change=='nan':p['rows'][0]['cells'][10]='NaN'
            elif change=='sample':p['rows'][0]['cells'][2]='2'
            elif change=='identity':p['rows'][0]['playerUrl']=p['rows'][0]['playerUrl'].replace('2026-27','2025-26')
            elif change=='duplicate':p['rows']*=2
            with self.subTest(change=change),self.assertRaises(ValueError):n.normalize(p,NOW)

    def test_exact_identity_current_team_and_same_nba_id_required(self):
        tables=self.tables();r=roster()
        self.assertEqual(len(n.context('9','2',2027,r,tables,NOW)),2)
        for broken in (dict(r,team='3'),dict(r,identityOnly=True),dict(r,season=2026),dict(r,retrievedAt='2026-11-01T19:00:00Z'),dict(r,abbreviation='NYK')):
            self.assertEqual(n.context('9','2',2027,broken,tables,NOW),[])
        broken=copy.deepcopy(tables);broken[(2027,'passing','last3')]['rows'][0]['nbaId']='999'
        self.assertEqual([c['kind'] for c in n.context('9','2',2027,r,broken,NOW)],['rebounding'])
        duplicate=copy.deepcopy(r);duplicate['players'].append(dict(id='10',name='Test Player',active=True))
        self.assertEqual(n.context('9','2',2027,duplicate,tables,NOW),[])

    def test_observed_opportunities_never_convert_to_probability_or_clearance(self):
        tables=self.tables();tables[(2027,'passing','last3')]['rows'][0]['metrics']['assists']=9
        c=n.context('9','2',2027,roster(),tables,NOW)[0]
        self.assertTrue(c['analysisOnly']);self.assertFalse(c['admissionReady'])
        self.assertIn('definitions/coverage',' '.join(c['warnings']))
        self.assertNotIn('probability',c);self.assertNotIn('expectedMinutes',c)
        self.assertEqual(c['recent']['metrics']['assists'],9)

    def test_future_correction_and_conflicting_same_clock_cannot_replace_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);n.ingest([packet()],NOW,root)
            future=n.normalize(packet(),NOW);future['retrievedAt']='2026-11-03T21:00:00Z'
            nba_capture.append_changed([future],root/'tracking',lambda r:(r['kind'],r['window'],r['retrievedAt']))
            self.assertEqual(len(n.observations(root,NOW)),1)
            self.assertEqual(len(n.observations(root,NOW+timedelta(days=2))),0)

    def test_next_day_research_failure_does_not_erase_other_prep(self):
        p=dict(targetDate='2026-11-04',nba={'games':12})
        def broken(*args,**kwargs):raise ValueError('source unavailable')
        result=next_day_prep.attach_opportunities(p,NOW,Path('/unused'),builder=broken)
        self.assertEqual(result['nba']['games'],12)
        self.assertFalse(result['nba']['opportunityResearch']['admissionReady'])

    def test_slate_role_research_preserves_unsubmitted_report_and_missing_quotes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'nba-capture';(root/'rosters').mkdir(parents=True);r=roster()
            boxscores.write_json(root/'rosters/2.json',r)
            game=dict(providerId='55',season=2027,kickoff='2026-11-05T00:00:00Z',status='scheduled',seasonType='regular-season',teams={'away':dict(id='2',abbreviation='BOS'),'home':dict(id='3',abbreviation='NOP')})
            boxscores.write_json(root/'slate.json',dict(retrievedAt='2026-11-03T19:00:00Z',games=[game]))
            n.ingest([packet(),packet(window='last3')],NOW,root)
            report=n.from_stores(NOW,root,'2026-11-04');self.assertEqual(report['players'],1)
            row=report['rows'][0];self.assertTrue(row['availabilityHold']);self.assertEqual(row['prices'],[])
            self.assertFalse(row['admissionReady']);self.assertEqual(row['currentRole']['games'],0)

if __name__=='__main__':unittest.main()
