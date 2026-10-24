import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_quarter_workload as workload


def fixture(overtime=False):
    players = [dict(id=f'{team}{n}', team=team, starter=n<5, dnp=False,
                    stats={'min': 48 if n<5 else 0}) for team in ('a','b') for n in range(6)]
    by_id = {p['id']:p for p in players}
    by_id['a0']['stats']['min']=18
    by_id['a5']['stats']['min']=30
    plays=[]
    def play(q,clock,kind='End Period',ids=()):
        sequence=len(plays)+1
        plays.append(dict(id=str(sequence),sequenceNumber=str(sequence),period={'number':q},
                          clock={'displayValue':clock},type={'text':kind},team={'id':'a'},
                          participants=[{'athlete':{'id':i}} for i in ids]))
    play(1,'12:00','Jumpball')
    play(1,'6:00','Substitution',('a5','a0'))
    play(1,'0.0')
    play(2,'0.0') # continuous lineup across periods, never reset to starters
    play(3,'12:00','Substitution',('a0','a5'))
    play(3,'0.0')
    play(4,'12:00','Substitution',('a5','a0'))
    play(4,'0.0')
    if overtime:
        play(5,'0.0')
        for p in players:
            if p['id'] in {'a1','a2','a3','a4','a5','b0','b1','b2','b3','b4'}:
                p['stats']['min']+=5
    return {'players':players,'teams':{'a':{},'b':{}}}, {'plays':plays}


class WorkloadTests(unittest.TestCase):
    def test_lineups_reconcile_q2_bench_role_and_keep_overtime_separate(self):
        box,payload=fixture(True);before=copy.deepcopy(payload)
        rows,hold=workload.extract(payload,box)
        self.assertIsNone(hold)
        self.assertEqual(rows['a0']['1']['minutes'],6)
        self.assertEqual(rows['a0']['2'],{'minutes':0,'participation':'not-observed'})
        self.assertEqual(rows['a5']['2'],{'minutes':12,'participation':'observed'})
        self.assertEqual(rows['a5']['5']['minutes'],5)
        self.assertEqual(payload,before)
        self.assertEqual(workload.extract({'plays':payload['plays']+[payload['plays'][0]]},box)[0],rows)
        self.assertEqual(workload.extract({'plays':list(reversed(payload['plays']))},box)[0],rows)

    def test_missing_substitution_end_or_identity_holds_entire_workload(self):
        box,payload=fixture()
        variants=[]
        for index in (1,2,3):
            changed=copy.deepcopy(payload);changed['plays'].pop(index);variants.append(changed)
        for field,value in [('sequenceNumber','?'),('clock',{'displayValue':'99:00'}),
                            ('participants',[{'athlete':{'id':'unknown'}}])]:
            changed=copy.deepcopy(payload);changed['plays'][1][field]=value;variants.append(changed)
        for changed in variants:
            rows,hold=workload.extract(changed,box)
            self.assertEqual(rows,{})
            self.assertIsNotNone(hold)

    def test_bad_starters_dnp_box_mismatch_and_action_off_court_hold(self):
        box,payload=fixture()
        for change in ({'starter':False},{'dnp':True},{'stats':{'min':30}}):
            changed=copy.deepcopy(box);changed['players'][0].update(change)
            self.assertIsNotNone(workload.extract(payload,changed)[1])
        changed=copy.deepcopy(payload)
        changed['plays'][3].update(scoringPlay=True,participants=[{'athlete':{'id':'a0'}}])
        self.assertIn('on-court',workload.extract(changed,box)[1])

