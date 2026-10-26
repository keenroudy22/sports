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
    def relevant_fixture(self):
        now=datetime(2026,10,24,13,tzinfo=timezone.utc)
        data,history=fixture()
        data['sourceAt']=boxscores.stamp(now)
        for i,g in enumerate(data['games']):
            g['kickoff']=f'2026-10-24T{22+i}:00:00Z'
            g['totalQuote']={'line':220+i,'over':-110,'under':-110,'book':'DraftKings','retrievedAt':boxscores.stamp(now)}
        return now,data,history

    def test_new_social_trends_use_ranked_current_matchups_not_prior_season_averages(self):
        now,data,h=self.relevant_fixture()
        rows=n.choices(data,now,h)
        watch=next(r for r in rows if r['family']=='trends')
        self.assertEqual(watch['title'],'NBA LINES I’M WATCHING')
        self.assertEqual(watch['rows'][0]['gap'],5.3)
        self.assertIn('my total about 225',watch['text'])
        self.assertIn('Research, not a bet.',watch['text'])
        self.assertNotIn('last season',watch['text'])
        self.assertNotIn('scored /',watch['text'])
        self.assertEqual(x_post.x_style(watch['text']), [])
        self.assertEqual(n.relevance_issues(watch,now),[])
        self.assertLessEqual(x_post.tweet_length(watch['text']),x_post.LIMIT)
        self.assertTrue(n.team_trends(data['games'],now,h))  # website history remains available

    def test_missing_stale_or_future_quotes_do_not_fall_back_to_history_social(self):
        now,data,h=self.relevant_fixture()
        for at in (None,boxscores.stamp(now-timedelta(hours=5)),boxscores.stamp(now+timedelta(minutes=1))):
            for g in data['games']:g['totalQuote']['retrievedAt']=at
            self.assertFalse(any(r['family']=='trends' for r in n.choices(data,now,h)))
        self.assertTrue(n.relevance_issues({'family':'trends','rows':[]},now))

    def test_player_research_requires_game_specific_sourced_current_role(self):
        now,_,_=self.relevant_fixture()
        row={'eventId':'1','athleteId':'2','team':'3','kickoff':'2026-10-24T23:00:00Z'}
        snapshot={'family':'props','evidence':[row]}
        self.assertTrue(n.relevance_issues(snapshot,now))
        row['roleReview']={**row,'checkedAt':boxscores.stamp(now),'headline':'Starting role confirmed',
                           'sources':[{'url':'https://www.nba.com/','label':'Team report'}]}
        self.assertEqual(n.relevance_issues(snapshot,now),[])
        for field,value in [('eventId','wrong'),('checkedAt',boxscores.stamp(now-timedelta(days=2))),('hold','Minutes uncertain')]:
            changed=copy.deepcopy(snapshot);changed['evidence'][0]['roleReview'][field]=value
            self.assertTrue(n.relevance_issues(changed,now))

    def test_watch_rechecks_exact_quote_and_does_not_schedule_overnight_price(self):
        now,data,h=self.relevant_fixture()
        watch=next(r for r in n.choices(data,now,h) if r['family']=='trends')
        quotes=[dict(eventId=g['id'],book='DraftKings',retrievedAt=boxscores.stamp(now),
                     current={'total':{k:g['totalQuote'][k] for k in ('line','over','under')}}) for g in data['games']]
        self.assertTrue(n.watch_current(watch,now,quotes))
        quotes[0]['current']['total']['line']+=1
        self.assertFalse(n.watch_current(watch,now,quotes))
        tonight=now-timedelta(hours=14)
        data['sourceAt']=boxscores.stamp(tonight)
        for g in data['games']:g['totalQuote']['retrievedAt']=boxscores.stamp(tonight)
        self.assertFalse(any(r['family']=='trends' for r in n.choices(data,tonight,h)))

    def test_queued_history_is_cancelled_only_after_provider_confirms_private(self):
        import buffer_post
        now,_,_=self.relevant_fixture()
        old={'key':'nba-trends-2026-10-24','family':'trends','rows':[]}
        for status,deleted in [('scheduled',True),('sent',False),('unknown',False)]:
            entry={'id':old['key'],'kind':'buffer:research','bufferPostId':'test',
                   'dueAt':boxscores.stamp(now+timedelta(hours=1))}
            with patch.object(n,'stored',return_value=[old]),patch.object(buffer_post,'graphql',return_value={'post':{'status':status,'text':'NBA research'}}),\
                 patch.object(buffer_post,'delete_post') as delete:
                buffer_post.audit_pending_style({'posts':[entry]},now,log=lambda *_:None,items={})
                self.assertEqual(delete.called,deleted)
            if deleted:self.assertTrue(entry['socialStyleAudit']['needsRevision'])
            if status=='sent':self.assertIn('sentAt',entry)

    def test_new_prop_caption_leads_with_line_number_and_current_role(self):
        now,_,_=self.relevant_fixture()
        players=[]
        for i in (1,2):
            row=dict(eventId='1',athleteId=str(i),team='3',kickoff='2026-10-24T23:00:00Z',
                name=f'Player {i}',teamName='Team',teamAbbr='TM',favorite=True,stat='reb',statName='rebounds',
                sourceAt=boxscores.stamp(now),book='DraftKings',side='over',line=5.5,odds=-110,
                last10={'hits':7,'games':10},projection={'value':7,'window':'Last season','minutes':30,'minutesBasis':'analyst-estimate'})
            row['roleReview']={k:row[k] for k in ('eventId','athleteId','team','kickoff')}
            row['roleReview'].update(checkedAt=boxscores.stamp(now),headline='Starting tonight',sources=[{'url':'https://www.nba.com/'}])
            players.append(row)
        data={'sourceAt':boxscores.stamp(now),'playerProps':{'rows':players}}
        post=n.prop_choice(data,now)
        self.assertIsNotNone(post)
        self.assertIn('Starting tonight',post['text'])
        self.assertIn('estimated min',post['text'])
        self.assertIn('Last season',post['text'])  # source window disclosed, not disguised
        for row in players:row.pop('roleReview')
        self.assertIsNone(n.prop_choice(data,now))

    def test_invalid_never_queued_prop_draft_gets_append_only_revision(self):
        now=datetime(2026,10,20,13,tzinfo=timezone.utc)
        old=dict(key='nba-props-2026-10-20',family='props',capturedAt=boxscores.stamp(now-timedelta(minutes=20)),
                 stale=boxscores.stamp(now+timedelta(hours=2)),text='Old research',rows=[])
        new=dict(old,capturedAt=boxscores.stamp(now),text='Reviewed research')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/(old['key']+'.json')
            path.write_text(json.dumps(old));original=path.read_bytes()
            with patch.object(n,'prop_choice',return_value=new),patch.object(n,'choices',return_value=[]),\
                 patch.object(n,'props_current',return_value=False),patch.object(x_post,'load_log',return_value={'posts':[]}):
                self.assertEqual(n.prepare(now,root,{}),[old['key']])
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(n.stored(root)[0]['text'],'Reviewed research')
            with patch.object(n,'prop_choice',return_value=new),patch.object(n,'choices',return_value=[]),\
                 patch.object(n,'props_current',return_value=False),patch.object(x_post,'load_log',return_value={'posts':[{'id':old['key'],'bufferPostId':'queued'}]}):
                self.assertEqual(n.prepare(now+timedelta(seconds=1),root,{}),[])
            self.assertEqual(len(list(root.glob('*.json'))),2)

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
    def test_plain_trends_explain_averages_and_new_roster_limit(self):
        data,h=fixture();r=n.choices(data,NOW,h)[1]
        self.assertEqual(r['right_label'],'AVG POINTS')
        self.assertIn('Scoring context, not a forecast.',r['text'])
        self.assertIn('Research, not a bet.',r['text'])
        for row in r['rows']:
            self.assertEqual(row['right'],str(row['history']['points']).removesuffix('.0'))
            self.assertEqual(row['detail'],'Last 10 games · last season')
            self.assertIn('per game',row['line'])
            self.assertIn('given up per game',row['caption'])
        self.assertNotIn('SAMPLE',json.dumps(r))
        self.assertNotIn('10 G',json.dumps(r))
        self.assertLessEqual(x_post.tweet_length(r['text']),x_post.LIMIT)
    def test_current_season_trends_never_claim_last_season_or_blend(self):
        data,h=fixture()
        current=[{**r,'season':2027,'kickoff':f'2026-10-{i%10+1:02}T00:00:00Z'} for i,r in enumerate(h)]
        r=n.choices(data,NOW,h+current)[1]
        self.assertIn('current season',r['text'])
        self.assertNotIn('last season',r['text'])
        self.assertTrue(all('current season' in row['detail'] for row in r['rows']))
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

    def test_new_research_is_plain_link_free_and_preserves_factual_windows(self):
        data,history=fixture()
        for row in n.choices(data,NOW,history):
            self.assertIn('Research, not a bet.',row['text'])
            self.assertNotIn('keenroudy.com',row['text'])
            self.assertNotIn('Early estimate',json.dumps(row))
            self.assertEqual(x_post.x_style(row['text']),[])
        self.assertIn('last season',n.choices(data,NOW,history)[1]['text'])

    def test_posted_nba_art_is_never_redrawn_after_copy_changes(self):
        data,history=fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);n.prepare(NOW,root,data,history)
            keys={r['key'] for r in n.stored(root)}
            for key in keys:
                (root/f'{key}.png').write_bytes(b'original sent art')
            with patch.object(n.pick_card,'render') as render:
                n.render_due(NOW,root,root,posted_keys=keys)
            render.assert_not_called()
            self.assertTrue(all((root/f'{key}.png').read_bytes()==b'original sent art' for key in keys))
            for key in keys:
                (root/f'{key}.png').unlink()
            with self.assertRaisesRegex(ValueError,'Original posted NBA art missing'):
                n.render_due(NOW,root,root,posted_keys=keys)
