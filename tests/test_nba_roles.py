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
    def test_receipt_clock_excludes_later_corrections_missing_times_and_conflicts(self):
        _,_,_,boxes=fixtures.fixture()
        original=boxes[0]
        correction=copy.deepcopy(original)
        correction['retrievedAt']=boxscores.stamp(NOW+timedelta(seconds=1))
        correction['players'][0]['stats']['pts']=999
        for rows in (boxes+[correction], [correction]+boxes):
            self.assertEqual(len(n.available_boxes(rows,NOW)),10)
            self.assertEqual(props.history(rows,'123',NOW)[0]['stats']['pts'],24)
        missing=dict(original);missing.pop('retrievedAt')
        self.assertEqual(n.available_boxes([missing],NOW),[])
        conflict=copy.deepcopy(original);conflict['players'][0]['stats']['pts']=0
        self.assertEqual(n.available_boxes([original,conflict],NOW),[])
        current=dict(original,eventId='new',season=2027,kickoff='2026-10-19T00:00:00Z',
                     retrievedAt=correction['retrievedAt'])
        self.assertEqual(n.current_role(review(),boxes+[current],NOW)[0]['games'],0)

    def test_current_workload_uses_current_team_regular_season_not_preseason_or_future(self):
        _,_,_,boxes=fixtures.fixture()
        q=review()
        for i,minutes in enumerate((28,32)):
            boxes.append(dict(boxes[-1],eventId=f'new{i}',season=2027,
                              kickoff=f'2026-10-{18+i}T00:00:00Z',
                              players=[dict(boxes[-1]['players'][0],starter=True,stats={'pts':20,'min':minutes})]))
        boxes += [dict(boxes[-1],eventId='pre',seasonType=1),
                  dict(boxes[-1],eventId='future',kickoff='2026-10-21T00:00:00Z')]
        role,hold=n.current_role(q,boxes,NOW)
        self.assertIsNone(hold);self.assertEqual(role['minutes'],[28,32])
        self.assertEqual((role['games'],role['starts'],role['medianMinutes']),(2,2,30))
        self.assertNotIn('expectedMinutes',role)

    def test_changed_starter_and_latest_dnp_hold_without_a_new_numeric_review(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);boxes=fixtures.NBAPlayerPropTests().write(root)
            for b in boxes:b['players'][0]['starter']=False
            boxes.append(dict(boxes[-1],eventId='new',season=2027,kickoff='2026-10-19T00:00:00Z',
                              players=[dict(boxes[-1]['players'][0],starter=True)]))
            held=props.build(NOW,root,boxes)['rows'][0]
            self.assertIsNone(held['projection']);self.assertIn('Starting role changed',held['hold'])
            self.assertEqual(held['currentRole']['starts'],1)
            n.record(review(),NOW,root)
            adjusted=props.build(NOW,root,boxes)['rows'][0]
            self.assertEqual(adjusted['projection']['minutes'],20)
            self.assertEqual(adjusted['projection']['model'],'nba-minutes-rate-reviewed-v1')
            boxes[-1]['players'][0]['dnp']=True
            self.assertIn('Did not play',n.current_role(review(),boxes,NOW)[1])

    def test_quote_cannot_reuse_a_roster_for_a_different_team_or_rescheduled_game(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);boxes=fixtures.NBAPlayerPropTests().write(root)
            import json
            path=root/'rosters/8.json';roster=json.loads(path.read_text());roster['team']='999'
            boxscores.write_json(path,roster)
            self.assertIn('roster',props.build(NOW,root,boxes)['rows'][0]['hold'])
            roster['team']='8';boxscores.write_json(path,roster)
            path=root/'slate.json';slate=json.loads(path.read_text());slate['games'][0]['kickoff']='2026-10-20T20:00:00Z'
            boxscores.write_json(path,slate)
            self.assertIsNone(props.build(NOW,root,boxes)['rows'][0]['projection'])

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
