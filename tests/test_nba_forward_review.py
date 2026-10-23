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
