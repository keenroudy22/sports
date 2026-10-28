import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_forward_review as review

NOW = datetime(2026, 10, 23, 18, tzinfo=timezone.utc)


def forecast(key='first', **extra):
    row = dict(id=key, eventId='game', athleteId='player', stat='pts', model='v1',
        retrievedAt='2026-10-22T12:00:00Z', kickoff='2026-10-22T23:00:00Z',
        book='DraftKings', projection={'value': 25}, line=20.5)
    return dict(row, **extra)


def outcome(row, actual=20, **extra):
    return dict(dict(id=row['id'], retrievedAt='2026-10-23T02:00:00Z',
        forecastAt=row['retrievedAt'], source='https://www.espn.com/nba/',
        model=row['model'], line=row['line'], book=row['book'],
        projection=row['projection']['value'], actual=actual, result='miss'), **extra)


class ForwardReviewTests(unittest.TestCase):
    def test_game_balanced_check_cannot_count_many_players_as_many_games(self):
        rows=[forecast(str(i),athleteId=str(i),side='over',odds=-110) for i in range(20)]
        result=review.summarize(rows,[outcome(r,actual=25,result='hit',side='over',odds=-110) for r in rows],NOW)
        check=result['segments'][0]['independentCheck']
        self.assertEqual((check['games'],check['gameDays'],check['pricedGames']),(1,1,1))
        self.assertFalse(check['trialEligible'])
        self.assertLess(check['gameBalancedShadowReturn'],1)

    def test_observed_minutes_shadow_is_not_pooled_with_analyst_review(self):
        a=forecast('a',model='nba-minutes-rate-reviewed-v1',season=2027,
            projection=dict(value=18,baselineValue=25,baselineMinutes=30))
        b=forecast('b',model='nba-current-role-minutes-shadow-v1',season=2027,
            projection=dict(value=22,baselineValue=24,baselineMinutes=30))
        result=review.summarize([a,b],[outcome(a),outcome(b)],NOW)
        rows=result['reviewedMinutes']
        self.assertEqual(len(rows),2)
        self.assertEqual({r['comparisons'] for r in rows},{1})
        self.assertEqual({r['model'] for r in rows},{a['model'],b['model']})

    def test_reviewed_minutes_compare_frozen_baseline_without_reconstructing_prices(self):
        a = forecast(model='nba-minutes-rate-reviewed-v1', season=2027,
            projection=dict(value=18, baselineValue=25, baselineMinutes=30))
        result = review.summarize([a], [outcome(a)], NOW)
        row = result['reviewedMinutes'][0]
        self.assertEqual((row['baselineMAE'],row['reviewedMAE'],row['games']), (5,2,1))
        self.assertNotIn('shadowNetUnits',row)
        self.assertNotIn('odds',row)
        a['projection'].pop('baselineValue')
        self.assertEqual(review.summarize([a], [outcome(a)], NOW)['reviewedMinutes'], [])

    def test_matched_models_use_same_inputs_without_selecting_winning_sides(self):
        a = forecast(model='baseline', side='over', odds=-110, season=2027)
        b = forecast('reviewed', model='reviewed', side='under', odds=-105, season=2027, projection={'value': 18})
        report = review.summarize([a,b], [outcome(a, side='over', odds=-110),
            outcome(b, side='under', odds=-105, result='hit')], NOW)
        pair = report['pairedModels'][0]
        self.assertEqual((pair['modelAMAE'], pair['modelBMAE'], pair['comparisons'], pair['games']), (5,2,1,1))
        self.assertEqual(report, review.summarize([b,a], [outcome(b, side='under', odds=-105, result='hit'),
            outcome(a, side='over', odds=-110)], NOW))

    def test_different_capture_or_book_or_line_is_not_a_matched_comparison(self):
        a = forecast(model='a')
        for change in (dict(retrievedAt='2026-10-22T13:00:00Z'), dict(book='FanDuel'), dict(line=21.5)):
            b = forecast('b', model='b', **change)
            result = review.summarize([a,b], [outcome(a),outcome(b)], NOW)
            self.assertEqual(result['graded'], 2)
            self.assertEqual(result['pairedModels'], [])

    def test_disagreeing_results_do_not_produce_a_model_comparison(self):
        a, b = forecast(model='a'), forecast('b', model='b')
        result = review.summarize([a,b], [outcome(a),outcome(b, actual=19)], NOW)
        self.assertEqual(result['pairedModels'], [])

    def test_shadow_uses_frozen_price_side_and_never_assumes_missing_price(self):
        a = forecast(odds=-200, side='under', season=2027)
        b = forecast('b', athleteId='other', odds=150, side='over', season=2027)
        c = forecast('c', athleteId='third')
        report = review.summarize([a,b,c], [outcome(a, actual=20, result='hit', odds=-200, side='under'),
            outcome(b, actual=25, result='hit', odds=150, side='over'), outcome(c)], NOW)
        new = next(s for s in report['segments'] if s['season'] == 2027)['pricedShadow']
        self.assertEqual(new['hits'], 2)
        self.assertEqual(new['shadowNetUnits'], 2)
        self.assertEqual(new['netPerUnitStaked'], 1)
        for change in ({'odds':-110}, {'side':'over'}, {'result':'miss'}):
            bad = outcome(a, actual=20, result='hit', odds=-200, side='under') | change
            self.assertEqual(review.summarize([a], [bad], NOW)['segments'][0]['pricedShadow']['excluded'], 1)

    def test_book_duplicates_and_input_order_cannot_cherry_pick_the_result(self):
        first = forecast()
        later = forecast('later', book='FanDuel', retrievedAt='2026-10-22T13:00:00Z', projection={'value': 20})
        rows = [first, later]
        results = [outcome(first), outcome(later)]
        saved = copy.deepcopy(rows)
        a = review.summarize(rows, results, NOW)
        self.assertEqual(a, review.summarize(rows[::-1], results[::-1], NOW))
        self.assertEqual(a['graded'], 1)
        self.assertEqual(a['segments'][0]['modelMAE'], 5)
        self.assertEqual(a['segments'][0]['lineMAE'], .5)
        self.assertEqual(rows, saved)

    def test_missing_first_outcome_cannot_be_replaced_by_later_winning_book(self):
        a, b = forecast(), forecast('later', retrievedAt='2026-10-22T13:00:00Z')
        result = review.summarize([a,b], [outcome(b)], NOW)
        self.assertEqual(result['graded'], 0)
        self.assertEqual(result['missingOrUnusable'], 1)

    def test_late_forecasts_future_or_mismatched_outcomes_are_not_evidence(self):
        late = forecast(retrievedAt='2026-10-23T00:00:00Z')
        self.assertEqual(review.summarize([late], [outcome(late)], NOW)['rejected'], 1)
        row = forecast()
        for change in ({'retrievedAt':'2026-10-24T02:00:00Z'}, {'model':'different'},
                       {'actual':float('nan')}, {'source':None}, {'projection':99}, {'result':'dnp'}):
            self.assertEqual(review.summarize([row], [outcome(row, **change)], NOW)['graded'], 0)

    def test_stats_stay_separate_and_game_counts_show_correlation(self):
        a, b = forecast(), forecast('reb', stat='reb', projection={'value': 5}, line=4.5)
        result = review.summarize([a,b], [outcome(a),outcome(b, actual=4)], NOW)
        self.assertEqual((result['graded'],result['games'],result['playerGames']), (2,1,1))
        self.assertEqual(len(result['segments']), 2)
        self.assertIn('no automatic promotion', review.markdown(result))
        self.assertIn('not profitability', review.markdown(result))


if __name__ == '__main__':
    unittest.main()
