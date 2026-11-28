import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post
import research_posts
import research_views


class ScorerAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 28, 14, tzinfo=timezone.utc)
        self.game = {'id': 'CFB-123', 'league': 'CFB', 'kickoff': '2026-11-28T17:00:00Z'}
        self.rows = [{'athleteId': str(i), 'player': name, 'games': 7, 'teamGames': 8,
                      'redZone': 26, 'inside10': 14, 'roleSnapshotAt': self.now.isoformat()}
                     for i, name in enumerate(('First runner', 'Second runner', 'Third runner'), 1)]
        self.proof = {p['athleteId']: {'status': 'available', 'name': p['player'], 'role': 'Starting back',
                                      'source': 'https://goairforcefalcons.com/gameday', 'kickoff': self.game['kickoff'],
                                      'checkedAt': self.now.isoformat()} for p in self.rows}
        self.detail = {self.game['id']: {'scorerResearch': self.rows}}
        self.metadata = {'cardKey': 'card', 'players': [
            {'title': p['player'], 'gameId': self.game['id'], 'athleteId': p['athleteId'],
             'kickoff': self.game['kickoff']} for p in self.rows]}
        self.checked = patch.object(research_views, 'scorer_checks', return_value={self.game['id']: self.proof})
        self.checked.start()
        self.addCleanup(self.checked.stop)

    def test_candidate_requires_positive_evidence_for_every_player(self):
        self.proof['1']['status'] = 'out for season'
        del self.proof['2']
        choice = research_posts.scorer_candidate([self.game], self.detail, self.now)
        self.assertEqual([p['title'] for p in choice['rows']], ['Third runner'])
        for key, value in [('checkedAt', '2026-11-27T14:00Z'), ('kickoff', '2026-11-28T19:00Z'),
                           ('name', 'Other player'), ('role', ''), ('source', '')]:
            with self.subTest(key=key), patch.dict(self.proof['3'], {key: value}):
                self.assertIsNone(research_posts.scorer_candidate([self.game], self.detail, self.now))

    def test_expiry_in_queue_and_later_exclusion_of_non_headliner(self):
        entry = {'id': 'research:end-zone:2026-11-28', 'dueAt': self.now.isoformat(),
                 'cardKey': 'card', 'research': self.metadata}
        with patch.object(research_posts, 'details_for', return_value=self.detail):
            self.assertEqual(buffer_post.queued_relevance_issues(entry, self.now), [])
            self.assertTrue(buffer_post.queued_relevance_issues(dict(entry, cardKey='old-art'), self.now))
            self.assertTrue(buffer_post.queued_relevance_issues(dict(entry, research={'leans': []}), self.now))
            self.proof['3']['checkedAt'] = (self.now - timedelta(hours=3, minutes=55)).isoformat()
            due = self.now + timedelta(minutes=10)
            self.assertTrue(buffer_post.queued_relevance_issues(dict(entry, dueAt=due.isoformat()), self.now))
            self.proof['3']['status'] = 'questionable'
            self.assertIn('Third runner', buffer_post.queued_relevance_issues(entry, self.now)[0])
            self.proof['3']['status'] = 'available'
            self.rows.pop()
            self.assertIn('Third runner', buffer_post.queued_relevance_issues(entry, self.now)[0])

    def test_site_excludes_injury_even_when_prior_review_and_projection_pass(self):
        game = dict(self.game, state='pre', season=2026, home={'id': '4'}, away={'id': '5'})
        snapshot = {'publishedAt': self.now.isoformat(), 'players': {'home': {'players': [
            {'id': '1', 'pos': 'RB', 'carries': [12]}]}}}
        records = [{'season': 2026, 'seasonType': 2, 'kickoff': f'2026-11-{day:02d}T17:00Z',
                    'teams': {'4': {}}, 'quality': {'plays': 'ok'},
                    'players': [{'id': '1', 'team': '4', 'rzCar': 5, 'i10Car': 2}]} for day in (1, 8, 15)]
        args = (game, snapshot, records, {'1': 'First runner'}, self.now)
        self.assertEqual(len(research_views.scorer_research(*args)), 1)
        self.assertEqual(research_views.scorer_research(*args, injuries={'4': [{'id': '1', 'status': 'Out'}]}), [])
