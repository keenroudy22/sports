import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import buffer_post as bp
import featured
import feed
import gates
import post_windows as W
from test_buffer_post import FakeBuffer, pick

NOW = datetime(2026, 10, 11, 10, 45, tzinfo=timezone.utc)
START = '2026-10-11T13:30:00Z'
GAME = {'id':'NFL-intl', 'league':'NFL', 'kickoff':START,
        'away':{'short':'Eagles'}, 'home':{'short':'Jaguars'}}


class WindowTests(unittest.TestCase):
    def test_international_best_bet_and_ticket_have_the_eight_thirty_window(self):
        p=pick('intl', 'NFL-intl', league='NFL', title='Eagles at Jaguars over 48.5', line=48.5)
        with mock.patch.object(bp.receipts, 'house_posts', return_value=[]):
            plans=bp.plan({'intl':p},{'intl':p},{'NFL-intl':GAME},NOW,{'posts':[]})
        self.assertEqual(plans[0][3], datetime(2026,10,11,12,30,tzinfo=timezone.utc))
        self.assertTrue(feed.in_window(START, plans[0][3], 'NFL'))
        self.assertTrue(gates.x_window(p,SimpleNamespace(now=NOW,games={'NFL-intl':GAME},first={},latest={})).ok)
        self.assertTrue(featured.todays_plays({'intl':p},{}, {'NFL-intl':GAME},NOW.astimezone(gates.EASTERN).date(),NOW))
        ticket=dict(p, id='ticket', legs=[{'title':'leg'}], parlayType='longshot')
        self.assertTrue(gates.x_window(ticket,SimpleNamespace(now=NOW,games={'NFL-intl':GAME},first={},latest={})).ok)

    def test_unreachable_window_is_refused_at_admission_and_named_in_the_plan(self):
        p=pick('intl','NFL-intl',league='NFL')
        late=datetime(2026,10,11,12,44,tzinfo=timezone.utc)
        ctx=SimpleNamespace(now=late,games={'NFL-intl':GAME},first={},latest={})
        self.assertFalse(gates.x_window(p,ctx).ok)
        self.assertEqual(featured.todays_plays({'intl':p},{},ctx.games,late.astimezone(gates.EASTERN).date(),late),[])
        refused=[]
        with mock.patch.object(bp.receipts,'house_posts',return_value=[]):
            self.assertEqual(bp.plan({'intl':p},{},ctx.games,late,{'posts':[]},refused=refused),[])
        self.assertIn(('intl',['has no X window']),refused)
        for kind in ('favorite','propLean','modelLean','longshot','ladder'):
            if kind in gates.RULES:
                self.assertIn(gates.x_window,gates.RULES[kind])

    def test_late_admission_needs_a_real_discord_first_slot(self):
        p=pick('intl','NFL-intl',league='NFL')
        late=datetime(2026,10,11,12,25,tzinfo=timezone.utc)
        ctx=SimpleNamespace(now=late,games={'NFL-intl':GAME},first={},latest={})
        self.assertEqual(bp.discord_first_due(late), datetime(2026,10,11,12,50,tzinfo=timezone.utc))
        self.assertFalse(gates.x_window(p,ctx).ok)
        refused=[]
        with mock.patch.object(bp.receipts,'house_posts',return_value=[]):
            self.assertEqual(bp.plan({'intl':p},{},ctx.games,late,{'posts':[]},refused=refused),[])
        self.assertIn(('intl',['has no X window']),refused)

    def test_third_international_play_cannot_enter_a_two_slot_window(self):
        p=pick('third','NFL-intl',league='NFL')
        first={str(i):dict(p,id=str(i)) for i in range(2)}
        ctx=SimpleNamespace(now=NOW,games={'NFL-intl':GAME},first=first,latest={})
        self.assertFalse(gates.x_window(p,ctx).ok)

    def test_buffer_results_are_essential_and_tenth_slot_stays_free(self):
        book={'posts':[{'id':str(i),'bufferPostId':str(i),'dueAt':(NOW+timedelta(hours=3)).isoformat()} for i in range(7)]}
        plans=[('optional','research','Research',NOW+timedelta(minutes=5),None),
               ('win','cashed','Win',NOW+timedelta(minutes=10),None),
               ('play','play','Play',NOW+timedelta(minutes=20),None)]
        bp.schedule(plans,'x',book,NOW,key='test',send=FakeBuffer(),log=lambda *_:None)
        self.assertEqual([p['id'] for p in book['posts'][7:]],['win','play'])
        self.assertEqual(len(book['posts']),9)

    def test_normal_games_post_at_nine_thirty_and_early_games_at_eight_thirty(self):
        self.assertEqual(W.target('NFL','2026-10-11T17:00:00Z'), datetime(2026,10,11,13,30,tzinfo=timezone.utc))
        self.assertEqual(W.target('CFB','2026-10-10T23:00:00Z'), datetime(2026,10,10,13,30,tzinfo=timezone.utc))
        self.assertEqual(W.target('CFB', START), datetime(2026,10,11,12,30,tzinfo=timezone.utc))

    def test_night_games_target_the_morning_of_game_day(self):
        self.assertEqual(W.target('NFL', '2026-10-09T00:15:00Z'), datetime(2026, 10, 8, 13, 30, tzinfo=timezone.utc))
        self.assertEqual(W.target('CFB', '2026-10-11T01:00:00Z'), datetime(2026, 10, 10, 13, 30, tzinfo=timezone.utc))


if __name__=='__main__': unittest.main()
