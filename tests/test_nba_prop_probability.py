import copy
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nba_prop_probability as n
import nba_capture

NOW = datetime(2026, 10, 28, 14, tzinfo=timezone.utc)


class ProbabilityStudyTests(unittest.TestCase):
    def training(self):
        return [(dict(id=str(i), eventId=str(i), stat='pts', projection={'value': 20}), {'actual': 22}) for i in range(30)]

    def row(self):
        return dict(id='quote', season=2026, retrievedAt='2026-10-28T14:00:00Z',
            kickoff='2026-10-28T23:00:00Z', eventId='future', athleteId='1', stat='pts',
            model=n.BASELINE, projection={'value': 20}, book='draftkings', line=20.5, over=-110, under=-110, side='over', odds=-110)

    def test_frozen_spec_equal_game_weight_and_future_only(self):
        training = self.training()
        self.assertIsNone(n.fit(training[:29], 'pts', NOW))
        spec = n.fit(training, 'pts', NOW)
        self.assertFalse(spec['admissionReady'])
        self.assertEqual(len(spec['trainingEvents']), 30)
        r = self.row()
        p = n.predict(r, spec, NOW)
        self.assertEqual(p['chanceOver'], .75)
        self.assertEqual(p['marketOver'], .5)
        self.assertFalse(p['admissionReady'])
        for change in ({'retrievedAt': '2026-10-28T13:00:00Z'}, {'eventId': '1'}, {'hold': 'injury'},
                       {'line': 20}, {'over': None}, {'stat': 'ast'}, {'model': 'other'}, {'over': float('nan')}):
            self.assertIsNone(n.predict(dict(r, **change), spec, NOW), change)
        bad = copy.deepcopy(spec); bad['implementationHash']='changed'; bad['specHash']=n.digest({k:v for k,v in bad.items() if k!='specHash'})
        self.assertIsNone(n.predict(r, bad, NOW))
        bad = copy.deepcopy(spec); bad['residuals']['0'] = [100]
        self.assertIsNone(n.predict(r, bad, NOW))

    def test_many_players_in_one_game_cannot_meet_training_requirement(self):
        repeated = [(dict(r, eventId='one'), o) for r, o in self.training()]
        self.assertIsNone(n.fit(repeated, 'pts', NOW))

    def test_no_future_outcomes_or_training_game_can_supply_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = n.fit(self.training(), 'pts', NOW)
            p = n.predict(self.row(), spec, NOW)
            nba_capture.append_changed([spec], root/'probability-specs', lambda r:r['id'])
            nba_capture.append_changed([p], root/'probability-forecasts', lambda r:r['id'])
            outcome = dict(id='quote', season=2026, retrievedAt='2026-10-29T02:00:00Z',
                actual=22, result='hit', projection=20, side='over', odds=-110, source='official', forecastAt=p['forecastAt'], line=20.5, book='draftkings', model=n.BASELINE)
            nba_capture.append_changed([outcome], root/'player-outcomes', lambda r:r['id'])
            self.assertEqual(n.review(root, NOW), [])
            review = n.review(root, datetime(2026,10,29,3,tzinfo=timezone.utc))
            self.assertEqual(review[0]['games'], 1)
            self.assertEqual(review[0]['easternDates'], 1)
            self.assertFalse(review[0]['admissionReady'])
            self.assertAlmostEqual(review[0]['brierImprovement'], .1875)

    def test_custom_replay_capture_cannot_write_probability_study(self):
        source = (Path(__file__).resolve().parents[1]/'scripts/nba_player_props.py').read_text()
        self.assertIn('if fetch is sharp_odds.fetch:', source)

    def test_price_choice_is_fixed_before_actual_and_counts_loss(self):
        p=n.predict(self.row(),n.fit(self.training(),'pts',NOW),NOW)
        win=n.shadow_price(p,1);loss=n.shadow_price(p,0)
        self.assertEqual(win['side'],loss['side'])
        self.assertEqual(loss['net'],-1)
        self.assertAlmostEqual(win['net'],100/110)
        p.update(chanceOver=.5)
        self.assertIsNone(n.shadow_price(p,1))

    def test_thirty_players_from_one_game_are_not_thirty_games(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=n.fit(self.training(),'pts',NOW)
            nba_capture.append_changed([spec],root/'probability-specs',lambda r:r['id'])
            ps=[];outs=[]
            for i in range(30):
                row=dict(self.row(),id='q'+str(i),athleteId=str(i))
                p=n.predict(row,spec,NOW);ps.append(p)
                outs.append(dict(id=row['id'],season=2026,retrievedAt='2026-10-29T02:00:00Z',
                    actual=22,result='hit',projection=20,side='over',odds=-110,source='official',
                    forecastAt=p['forecastAt'],line=20.5,book='draftkings',model=n.BASELINE))
            nba_capture.append_changed(ps,root/'probability-forecasts',lambda r:r['id'])
            nba_capture.append_changed(outs,root/'player-outcomes',lambda r:r['id'])
            result=n.review(root,datetime(2026,10,29,3,tzinfo=timezone.utc))[0]
            self.assertEqual(result['games'],1)
            self.assertEqual(result['pricedGames'],1)
            self.assertFalse(result['evidenceReady'])
            self.assertFalse(result['admissionReady'])
            self.assertIn('Fewer than30 untouched test games',result['evidenceHolds'])

    def test_sufficient_favorable_shadow_evidence_still_cannot_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=n.fit(self.training(),'pts',NOW)
            nba_capture.append_changed([spec],root/'probability-specs',lambda r:r['id'])
            forecasts=[];outcomes=[]
            for i in range(30):
                at=NOW+timedelta(days=i//5)
                row=dict(self.row(),id='q'+str(i),eventId='future'+str(i),
                    retrievedAt=n.boxscores.stamp(at),kickoff=n.boxscores.stamp(at+timedelta(hours=9)))
                p=n.predict(row,spec,at);forecasts.append(p)
                outcomes.append(dict(id=row['id'],season=2026,retrievedAt=n.boxscores.stamp(at+timedelta(hours=12)),
                    actual=22,result='hit',projection=20,side='over',odds=-110,source='official',
                    forecastAt=p['forecastAt'],line=20.5,book='draftkings',model=n.BASELINE))
            nba_capture.append_changed(forecasts,root/'probability-forecasts',lambda r:r['id'])
            nba_capture.append_changed(outcomes,root/'player-outcomes',lambda r:r['id'])
            result=n.review(root,NOW+timedelta(days=7))[0]
            self.assertEqual(result['games'],30)
            self.assertEqual(result['easternDates'],6)
            self.assertTrue(result['evidenceReady'])
            self.assertFalse(result['admissionReady'])
            self.assertGreater(result['rawStatReturnLower95'],0)
            # Changing the specification, even with a recomputed saved digest,
            # cannot borrow an old method's apparent result.
            changed=dict(spec,marketAnchor=.1)
            changed['specHash']=n.digest({k:v for k,v in changed.items() if k!='specHash'})
            self.assertFalse(n.valid_spec(changed))
