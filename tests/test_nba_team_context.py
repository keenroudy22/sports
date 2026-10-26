import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import boxscores
import nba_team_context as n

NOW = datetime(2026, 10, 26, 13, 35, tzinfo=timezone.utc)


def fixture():
    game = dict(providerId='100', status='scheduled', seasonType='regular-season', season=2027,
                kickoff='2026-10-26T23:00:00Z', teams={'home': {'id': '1'}, 'away': {'id': '2'}})
    injuries = dict(season=2027, retrievedAt=boxscores.stamp(NOW),
                    rows=[dict(team='1', athleteId='10', name='Player', status='Out', source='https://example.com/injury')])
    roster = dict(league='NBA', team='1', season=2027, retrievedAt=boxscores.stamp(NOW), players=[{'id': '10'}])
    return {'games': [game]}, injuries, {'1': roster}


def box(event, season=2027, starter=True, minutes=30, dnp=False):
    return dict(eventId=str(event), league='NBA', season=season, seasonType=2,
                kickoff='2026-10-24T23:00:00Z', retrievedAt='2026-10-25T02:00:00Z',
                source='https://example.com/box', teams={'1': {}, '2': {}},
                players=[dict(id='10', team='1', starter=starter, dnp=dnp, stats={'min': minutes})])


class NBATeamContextTests(unittest.TestCase):
    def build(self, boxes, injuries=None, rosters=None):
        slate, inj, roster = fixture()
        return n.build(slate, injuries or inj, boxes, rosters or roster, NOW)

    def person(self, report):
        return report['games'][0]['teams'][0]['injuredPlayers'][0]

    def test_current_and_prior_observed_roles_stay_separate_and_do_not_clear_injury(self):
        boxes = [box(i) for i in range(3)] + [box(i+10, season=2026, starter=False, minutes=12) for i in range(3)]
        original = copy.deepcopy(boxes)
        result = self.build(boxes)
        p = self.person(result)
        self.assertEqual(p['currentSeason']['label'], 'Observed starter')
        self.assertEqual(p['priorSeason']['label'], 'Observed bench player')
        self.assertEqual(p['currentSeason']['averageMinutesInKnownRows'], 30)
        self.assertEqual(p['priorSeason']['averageMinutesInKnownRows'], 12)
        self.assertTrue(p['rosterVerified'])
        self.assertFalse(result['admissionReady'])
        self.assertNotIn('projection', p)
        self.assertNotIn('expectedMinutes', p)
        self.assertEqual(boxes, original)

    def test_missing_box_row_is_not_zero_but_explicit_dnp_is(self):
        missing = box(2); missing['players'] = []
        result = self.build([box(1, dnp=True), missing])
        role = self.person(result)['currentSeason']
        self.assertEqual((role['knownPlayerRows'], role['missingPlayerRows'], role['explicitDNPs']), (1, 1, 1))
        self.assertEqual(role['averageMinutesInKnownRows'], 0)
        self.assertIsNone(role['starts'])
        self.assertIn('Limited', role['label'])

    def test_future_box_correction_and_ambiguous_same_time_versions_are_not_used(self):
        early = box(1)
        future = box(1, minutes=60); future['retrievedAt'] = boxscores.stamp(NOW+timedelta(seconds=1))
        self.assertEqual(self.person(self.build([early, future]))['currentSeason']['averageMinutesInKnownRows'], 30)
        conflict = box(1, minutes=1)
        self.assertIsNone(self.person(self.build([early, conflict]))['currentSeason']['averageMinutesInKnownRows'])

    def test_stale_future_or_wrong_season_injury_evidence_remains_unknown(self):
        for fields in ({'retrievedAt': boxscores.stamp(NOW-timedelta(hours=2))},
                       {'retrievedAt': boxscores.stamp(NOW+timedelta(seconds=1))}, {'season': 2026}):
            _, inj, _ = fixture(); inj.update(fields)
            result = self.build([box(1)], injuries=inj)
            team = result['games'][0]['teams'][0]
            self.assertEqual(team['injuredPlayers'], [])
            self.assertFalse(team['injurySnapshotUsable'])
            self.assertEqual(team['hold'], 'Current injury evidence unavailable')

    def test_roster_mismatch_or_stale_roster_does_not_verify_player_identity(self):
        for fields in ({'team': '999'}, {'season': 2026},
                       {'retrievedAt': boxscores.stamp(NOW-timedelta(days=2))}):
            _, _, roster = fixture(); roster['1'].update(fields)
            self.assertFalse(self.person(self.build([box(1)], rosters=roster))['rosterVerified'])

    def test_started_games_and_other_dates_are_not_prepared(self):
        slate, inj, roster = fixture()
        self.assertEqual(n.build(slate, inj, [], roster, NOW, '2026-10-27')['games'], [])
        slate['games'][0]['kickoff'] = boxscores.stamp(NOW-timedelta(minutes=1))
        self.assertEqual(n.build(slate, inj, [], roster, NOW)['games'], [])
