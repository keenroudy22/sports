import copy
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import boxscores, nba_roles as n, nba_player_props as props
import test_nba_player_props as fixtures
NOW=fixtures.NOW


def review():
    return dict(eventId='100',athleteId='123',team='8',season=2027,kickoff='2026-10-20T19:00:00Z',
                checkedAt=boxscores.stamp(NOW),kind='analyst-estimate',minutes=20,
                headline='Bench role',explanation='My conservative estimate from recent bench work, not a coach limit.',
                sources=[dict(url='https://example.com/current-report',label='Current report')])


class RoleTests(unittest.TestCase):
    def test_reviewed_minutes_change_research_not_history_or_probability(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);boxes=fixtures.NBAPlayerPropTests().write(root)
            before=props.build(NOW,root,boxes)['rows'][0]
            self.assertEqual(n.record(review(),NOW,root),1)
            self.assertEqual(n.record(review(),NOW,root),0)
            after=props.build(NOW,root,boxes)['rows'][0]
            p=after['projection']
            self.assertEqual((p['value'],p['minutes'],p['baselineValue'],p['baselineMinutes']),(16,20,24,30))
            self.assertEqual(p['minutesBasis'],'analyst-estimate')
            self.assertEqual(after['last10']['values'],before['last10']['values'])
            self.assertEqual(after['side'],'under')
            self.assertNotIn('probability',p)
            self.assertEqual(boxscores.verify(root/'role-reviews'),[])
    def test_role_only_does_not_invent_minutes_and_injury_hold_always_wins(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);boxes=fixtures.NBAPlayerPropTests().write(root)
            r=review();r['kind']='role-only';r.pop('minutes')
            n.record(r,NOW,root)
            after=props.build(NOW,root,boxes)['rows'][0]
            self.assertEqual(after['projection']['value'],24)
            self.assertNotIn('minutesBasis',after['projection'])
            boxscores.write_json(root/'injuries-current.json',dict(retrievedAt=boxscores.stamp(NOW),rows=[dict(athleteId='123',status='Out')]))
            after=props.build(NOW,root,boxes)['rows'][0]
            self.assertIsNone(after['projection']);self.assertNotIn('favorite',after)
    def test_invalid_or_future_minutes_never_change_a_projection(self):
        for minutes in (True,0,49,float('nan')):
            r=review();r['minutes']=minutes
            with self.assertRaises(ValueError):n.validate(r)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r=review();r['checkedAt']=boxscores.stamp(NOW+timedelta(seconds=1))
            with self.assertRaises(ValueError):n.record(r,NOW,root)
        r=review();r['sources'][0]['url']='javascript:alert(1)'
        with self.assertRaises(ValueError):n.validate(r)
    def test_wrong_game_team_and_expired_review_never_reuse_minutes(self):
        q={k:review()[k] for k in ('eventId','athleteId','team','season','kickoff')}
        p={'value':24,'minutes':30,'rate':.8,'low':15,'high':30}
        for key,value in [('eventId','999'),('team','2'),('season',2026),('kickoff','2026-10-21T19:00:00Z')]:
            r=review();r[key]=value
            self.assertTrue(n.apply(p,q,r,NOW)[2]);self.assertEqual(n.apply(p,q,r,NOW)[0],p)
        self.assertTrue(n.apply(p,q,review(),NOW+timedelta(days=1))[2])
    def test_forward_versions_stay_separate_and_original_bytes_are_immutable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);boxes=fixtures.NBAPlayerPropTests().write(root)
            self.assertEqual(props.record_forward(NOW,root,boxes),1)
            old=props.saved(root/'player-forecasts')[0]
            n.record(review(),NOW,root)
            self.assertEqual(props.record_forward(NOW,root,boxes),1)
            rows=props.saved(root/'player-forecasts')
            self.assertEqual(rows[0],old)
            self.assertNotEqual(rows[0]['id'],rows[1]['id'])
            self.assertEqual(props.record_forward(NOW,root,boxes),0)
    def test_new_starting_role_can_hold_old_bench_baseline_without_injury_override(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);boxes=fixtures.NBAPlayerPropTests().write(root)
            r=review();r.update(kind='role-only',hold='New starting role; workload estimate needed');r.pop('minutes')
            n.record(r,NOW,root)
            after=props.build(NOW,root,boxes)['rows'][0]
            self.assertIsNone(after['projection']);self.assertEqual(after['hold'],r['hold'])
            self.assertNotIn('favorite',after)
    def test_display_cap_prioritizes_tonight_and_shares_slots_across_games(self):
        row=lambda event,kickoff,name:dict(eventId=event,kickoff=kickoff,name=name)
        a=row('1','2026-10-20T23:00:00Z','A')
        b=row('2','2026-10-21T01:30:00Z','B')
        tomorrow=row('3','2026-10-21T23:00:00Z','Tomorrow')
        rows=[tomorrow,dict(a,name='A1'),dict(a,name='A2'),dict(a,name='A3'),b]
        chosen=props.display_rows(rows,3)
        self.assertEqual([r['name'] for r in chosen],['A1','A2','B'])
        self.assertEqual(props.display_rows(rows,None),rows)
        self.assertEqual(len(props.display_rows(rows,60)),5)
        duplicates=[dict(a,athleteId='10',stat=str(i)) for i in range(50)]
        reviewed=[dict(a,athleteId=str(i),name=str(i),roleReview={'headline':'Reviewed'}) for i in range(20,24)]
        chosen=props.display_rows(duplicates+reviewed+[b],6)
        self.assertTrue(all(r in chosen for r in reviewed))
        self.assertIn(b,chosen)
