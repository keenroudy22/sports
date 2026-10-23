import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gates
import parlay
import run


class PostingResetTests(unittest.TestCase):
    def test_new_lotto_shape_boundaries_and_separate_climb(self):
        ctx = SimpleNamespace(now=datetime(2026, 10, 23, 14, tzinfo=timezone.utc))
        for count in (3, 4, 8, 9):
            for price in (399, 400, 1000, 1001):
                self.assertEqual(gates.longshot_shape({'parlayType':'longshot','legs':[{}]*count,'odds':price}, ctx).ok,
                                 4 <= count <= 8 and 400 <= price <= 1000)
        self.assertTrue(gates.longshot_shape({'parlayType':'ladder','legs':[{},{}],'odds':-180},ctx).ok)
        ctx.now = datetime(2026, 10, 22, 14, tzinfo=timezone.utc)
        self.assertTrue(gates.longshot_shape({'legs':[{}]*3,'odds':700},ctx).ok)

    def test_live_constructor_uses_new_envelope_without_fetching(self):
        now = datetime(2026,10,23,14,tzinfo=timezone.utc)
        with patch.object(run.parlay,'build',return_value=(None,'no supported ticket')) as build:
            result, reason = run.longshot_candidate([],{},now,'CFB')
        self.assertIsNone(result)
        self.assertEqual(build.call_args.kwargs['min_legs'],4)
        self.assertEqual(build.call_args.kwargs['max_legs'],8)
        self.assertEqual(build.call_args.kwargs['price_range'],(400,1000))

    def test_active_risk_limit_cannot_be_raised_by_new_minimum(self):
        result, reason = parlay.build([],datetime.now(timezone.utc),min_legs=4,max_legs=3)
        self.assertIsNone(result)
        self.assertIn('risk limit',reason)

    def test_eight_leg_construction_is_bounded_and_keeps_games_distinct(self):
        now = datetime(2026,10,23,14,tzinfo=timezone.utc)
        rows = [{'id':str(i),'gameId':str(i),'league':'NFL','state':'open','title':f'Team {i} over 1.5',
                 'line':1.5,'odds':-300,'book':'FanDuel','market':'receiving yards','kickoff':'2026-10-23T23:00:00Z',
                 'observedAt':'2026-10-23T13:50:00Z','grade':{'chance':.8,'tier':'lean'}} for i in range(12)]
        ticket, reason = parlay.build(rows,now,min_legs=4,max_legs=8,target=400,price_range=(400,1000),max_totals=1)
        self.assertIsNone(reason)
        self.assertTrue(4 <= len(ticket['legs']) <= 8)
        self.assertEqual(len(ticket['gameIds']),len(set(ticket['gameIds'])))
        self.assertTrue(400 <= ticket['odds'] <= 1000)
