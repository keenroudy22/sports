import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_editorial as n
import receipts,boxscores,discord_post,research_posts,x_post

NOW=datetime(2026,10,19,21,tzinfo=timezone.utc)


def fixture():
    teams=[{'id':str(i),'abbreviation':name,'name':name+' Team'} for i,name in enumerate(['BOS','DET','PHI','NY'],1)]
    games=[{'id':str(i),'season':2027,'seasonType':'regular-season','status':'scheduled',
            'kickoff':f'2026-10-20T{19+i:02}:00:00Z','teams':{'away':teams[i*2],'home':teams[i*2+1]},
            'projection':{'away':110.1,'home':115.2,'total':225.3}} for i in range(2)]
    history=[{'season':2026,'type':2,'state':'post','kickoff':f'2026-04-{i+1:02}T00:00:00Z',
              'home':g['teams']['home'],'away':g['teams']['away'],'homeScore':120,'awayScore':110}
             for g in games for i in range(10)]
    return {'sourceAt':boxscores.stamp(NOW),'games':games},history


class NBAEditorialTests(unittest.TestCase):
    def test_two_early_posts_real_numbers_and_all_card_names_in_words(self):
        data,history=fixture();rows=n.choices(data,NOW,history)
        self.assertEqual(len(rows),2)
        self.assertEqual([r['due'] for r in rows],['2026-10-20T12:00:00Z','2026-10-20T14:00:00Z'])
        for r in rows:
            self.assertEqual(receipts.guard(r),[])
            self.assertNotIn('@Playbook',r['text'])
            for source in r['rows']:
                self.assertIn(source['caption'],r['text'])
        self.assertIn('last season',rows[1]['text'])
        self.assertNotIn('100%',rows[1]['text'])
    def test_future_postseason_missing_and_unplayed_history_never_counts(self):
        data,h=fixture();base=n.team_trends(data['games'],NOW,h)
        h.extend([{**h[0],'type':3,'homeScore':999},{**h[0],'kickoff':'2026-12-01T00:00:00Z'},
                  {**h[0],'state':'pre'},{**h[0],'homeScore':None}])
        self.assertEqual(base,n.team_trends(data['games'],NOW,h))
        self.assertEqual(base[0]['points'],110)
        self.assertEqual(base[0]['games'],10)
    def test_current_window_requires_five_and_never_blends_seasons(self):
        data,h=fixture()
        current=[{**r,'season':2027,'kickoff':f'2026-10-{i+1:02}T00:00:00Z','awayScore':140} for i,r in enumerate(h[:4])]
        self.assertEqual(n.team_trends(data['games'],NOW,h+current)[0]['season'],2026)
        current.append({**current[0],'kickoff':'2026-10-05T00:00:00Z'})
        r=n.team_trends(data['games'],NOW,h+current)[0]
        self.assertEqual((r['season'],r['points'],r['games']),(2027,140,5))
    def test_stale_future_source_started_preseason_nan_and_late_fail_closed(self):
        data,h=fixture()
        for stamp in ['2026-10-17T00:00:00Z','2026-10-20T00:00:00Z']:
            self.assertEqual(n.choices({**data,'sourceAt':stamp},NOW,h),[])
        for g in data['games']:g['seasonType']='preseason'
        self.assertEqual(n.choices(data,NOW,h),[])
        data,h=fixture()
        for g in data['games']:g['projection']['home']=float('nan')
        self.assertEqual(n.choices(data,NOW,h),[])
        data,h=fixture();late=datetime(2026,10,20,18,tzinfo=timezone.utc)
        self.assertEqual(n.choices({**data,'sourceAt':boxscores.stamp(late)},late,h),[])
    def test_single_game_still_produces_two_team_projection_rows(self):
        data,h=fixture();data['games']=data['games'][:1]
        self.assertEqual(len(n.choices(data,NOW,h)[0]['rows']),2)
    def test_frozen_snapshot_and_retention_and_no_duplicate_slot(self):
        data,h=fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(len(n.prepare(NOW,root,data,h)),2)
            before={p.name:p.read_bytes() for p in root.glob('*.json')}
            data['games'][0]['projection']['home']=100
            self.assertEqual(n.prepare(NOW,root,data,h),[])
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.glob('*.json')})
            self.assertEqual(n.posts(NOW,root,{}),[])
            self.assertEqual(len(n.posts(NOW,root,{'delivered':True,'sentAt':boxscores.stamp(NOW)})),2)
            self.assertEqual(n.posts(NOW+timedelta(days=2),root),[])
    def test_preview_veto_and_two_hour_window_are_real(self):
        for r in [{},{'delivered':True,'sentAt':boxscores.stamp(NOW),'vetoed':True},
                  {'delivered':False,'sentAt':boxscores.stamp(NOW)}]:
            self.assertFalse(n.review_ready(NOW+timedelta(hours=3),r))
        r={'delivered':True,'sentAt':boxscores.stamp(NOW)}
        self.assertFalse(n.review_ready(NOW+timedelta(minutes=119),r))
        self.assertTrue(n.review_ready(NOW+timedelta(hours=2),r))
    def test_veto_wakes_mirror_before_due_and_cancels_only_unsent_nba_research(self):
        import run,buffer_post
        entry={'id':'nba-projections-2026-10-20','bufferPostId':'fake','dueAt':'2026-10-20T12:00:00Z'}
        log={'posts':[entry]}
        with patch.object(n,'review_ready',return_value=False),patch.object(buffer_post,'delete_post') as delete:
            self.assertTrue(run.mirror_due(log,NOW))
            buffer_post.reconcile(log,NOW,log=lambda *_:None)
            delete.assert_called_once()
        self.assertIn('cancelledAt',entry)
        entry.pop('cancelledAt');entry['sentAt']=boxscores.stamp(NOW)
        self.assertFalse(n.veto_pending(entry))
        entry.pop('sentAt');entry['dueAt']=boxscores.stamp(NOW-timedelta(minutes=1))
        self.assertFalse(n.veto_pending(entry,NOW))
        entry.pop('dueAt');self.assertFalse(n.veto_pending(entry,NOW))
    def test_nba_does_not_consume_football_research_slot(self):
        from datetime import date
        self.assertFalse(research_posts.already_posted({'posts':[{'id':'nba-trends-2026-10-20'}]},date(2026,10,20)))
    def test_research_mirror_only_after_x_and_never_to_plays(self):
        entry={'id':'nba-trends-2026-10-20','kind':'buffer:research','dueAt':boxscores.stamp(NOW),
               'discord':{'state':'pending','destination':'research','text':'NBA team history'}}
        log={'posts':[entry]};calls=[]
        send=lambda url,text,image=None,**kw:calls.append((url,text))
        with patch.object(discord_post,'send_message',side_effect=send):
            discord_post.mirror_sent(log,NOW,url='plays',research_url='research')
            self.assertEqual(calls,[])
            entry.update(sentAt=boxscores.stamp(NOW),link='https://x.com/keenkooks/status/1')
            discord_post.mirror_sent(log,NOW,url='plays',research_url='research')
        self.assertEqual(calls[0][0],'research')
        self.assertIn('RESEARCH · NOT A BEST BET',calls[0][1])
    def test_renderer_uses_ticket_qa_and_never_fetches_book_or_new_feed(self):
        data,h=fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);n.prepare(NOW,root,data,h)
            captured=[]
            with patch.object(n.pick_card,'render',side_effect=lambda svg,path:captured.append(svg)):
                self.assertEqual(len(n.render_due(NOW,root,root,fetch=lambda _:None)),2)
            self.assertTrue(all('RESEARCH' in svg and 'NBA' in svg for svg in captured))
            self.assertEqual(n.render_due(NOW+timedelta(days=9),root,root),{})
