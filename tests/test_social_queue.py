import json
import io
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post as bp
import social_style as style
import run

NOW = datetime(2026, 10, 22, 15, tzinfo=timezone.utc)


class QueueStyleTests(unittest.TestCase):
    def entry(self, **changes):
        return dict(id='nba-trends-2026-10-22', bufferPostId='old', kind='buffer:research',
                    postedAt='2026-10-22T00:37:11Z', dueAt='2026-10-22T16:00:00Z',
                    card=True, cardKey='nba-trends-2026-10-22',
                    discord={'state':'pending', 'text':'NBA trends. Research, not a bet.',
                             'image':'https://keenroudy.com/sports/data/cards/old.png'}, **changes)

    def provider(self, status='scheduled', text=None, fail=False):
        calls=[]
        def send(url, body, headers):
            calls.append(body)
            if fail:
                raise bp.BufferError('provider unavailable')
            if 'deletePost' in body['query']:
                return 200, json.dumps({'data':{'deletePost':{'id':'old'}}}).encode()
            return 200, json.dumps({'data':{'post':{'id':'old','status':status,'text':text,
                'sentAt':'2026-10-22T14:05:45Z' if status=='sent' else None,
                'externalLink':'https://x.com/keenkooks/status/123' if status=='sent' else None}}}).encode()
        return send,calls

    def test_copy_preserves_proof_links_factual_windows_and_estimated_minutes(self):
        self.assertFalse(style.issues('Last season, 10 games. Estimated 33 minutes. Research, not a bet.'))
        self.assertFalse(style.issues('Cashed. https://x.com/keenkooks/status/123'))
        for text in ['Full board: keenroudy.com/sports/#today', 'Early score estimates.',
                     'New rosters can change it.', '21+ · Entertainment only']:
            self.assertTrue(style.issues(text), text)

    def test_png_attestation_only_for_a_fresh_clean_native_source(self):
        raw=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+b'\0'*13+b'\0'*4+b'rest'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'card.png';path.write_bytes(raw)
            self.assertFalse(style.mark(path,'<svg><text>21+ · Entertainment only</text></svg>'))
            self.assertEqual(path.read_bytes(),raw)
            self.assertTrue(style.mark(path,'<svg><text>RESEARCH · NOT A BET</text></svg>'))
            self.assertIn(style.MARKER,path.read_bytes()[:256])
            self.assertTrue(path.read_bytes().endswith(b'rest'))

    def test_overnight_queued_bad_caption_cancelled_without_rewriting_original(self):
        e=self.entry();original='NBA trends\nFull board: keenroudy.com/sports/#today'
        e['discord']['text']=original
        send,calls=self.provider(text=original)
        failed=bp.audit_pending_style({'posts':[e]},NOW,key='t',send=send,art_check=lambda _:True,items={},log=lambda *_:None)
        self.assertEqual(failed,[e]);self.assertIn('cancelledAt',e)
        self.assertEqual(e['discord']['text'],original)
        self.assertEqual(e['bufferPostId'],'old')
        self.assertTrue(e['socialStyleAudit']['needsRevision'])
        self.assertEqual(sum('deletePost' in c['query'] for c in calls),1)

    def test_old_graphic_is_not_cleared_by_clean_caption_or_a_future_due_time(self):
        e=self.entry();send,calls=self.provider()
        bp.audit_pending_style({'posts':[e]},NOW,key='t',send=send,art_check=lambda _:False,items={},log=lambda *_:None)
        self.assertIn('cancelledAt',e)
        self.assertTrue(any('deletePost' in c['query'] for c in calls))
        self.assertFalse(bp.style_audit_due(e,NOW))

    def test_already_sent_never_deleted_even_when_local_log_lags(self):
        e=self.entry();send,calls=self.provider('sent', 'Full board: keenroudy.com/sports')
        bp.audit_pending_style({'posts':[e]},NOW,key='t',send=send,items={},log=lambda *_:None)
        self.assertEqual(e['tweetId'],'123');self.assertNotIn('cancelledAt',e)
        self.assertFalse(any('deletePost' in c['query'] for c in calls))

    def test_unknown_state_and_provider_failure_never_delete(self):
        for status,fail in [('publishing',False),('scheduled',True)]:
            e=self.entry();send,calls=self.provider(status,fail=fail)
            bp.audit_pending_style({'posts':[e]},NOW,key='t',send=send,items={},log=lambda *_:None)
            self.assertEqual(e['socialStyleAudit']['state'],'unverified')
            self.assertNotIn('cancelledAt',e)
            self.assertFalse(any('deletePost' in c['query'] for c in calls))

    def test_registered_owner_proof_is_exempt_from_house_art_marker(self):
        key='community:personal-ticket:2026-10-22-tnf-q1'
        url='https://keenroudy.com/sports/img/tickets/personal-tnf-q1-2026-10-22.png'
        e=self.entry();e.update(id=key,kind='buffer:community',cardKey=url)
        e['discord']['image']=url
        send,_=self.provider()
        bp.audit_pending_style({'posts':[e]},NOW,key='t',send=send,art_check=lambda _:False,
            items={key:{'personalTicket':True,'card':'img/tickets/personal-tnf-q1-2026-10-22.png'}},log=lambda *_:None)
        self.assertEqual(e['socialStyleAudit']['state'],'clear')
        self.assertEqual(e['socialStyleVersion'],style.VERSION)

    def test_current_post_rechecks_actual_provider_caption_near_release(self):
        e=self.entry(socialStyleVersion=style.VERSION,queuedText='Clean text')
        e['dueAt']='2026-10-22T15:20:00Z'
        send,_=self.provider(text='Full board: keenroudy.com/sports')
        bp.audit_pending_style({'posts':[e]},NOW,key='t',send=send,art_check=lambda _:True,items={},log=lambda *_:None)
        self.assertIn('cancelledAt',e)

    def test_existing_five_minute_mirror_wakes_for_unaudited_future_posts(self):
        self.assertTrue(run.mirror_due({'posts':[self.entry()]},NOW))
        e=self.entry(socialStyleVersion=style.VERSION)
        e['socialStyleAudit']={'checkedAt':bp.gates.stamp(NOW),'state':'clear'}
        self.assertFalse(bp.style_audit_due(e,NOW))

    def test_new_schedule_refuses_old_copy_before_provider_creation(self):
        calls=[]
        bp.schedule([('r','research','Full board: keenroudy.com/sports',NOW+timedelta(hours=1),None)],
                    'channel',{'posts':[]},NOW,key='t',send=lambda *a:calls.append(a),log=lambda *_:None)
        self.assertFalse(calls)

    def test_live_art_checks_actual_png_marker_not_url_or_age(self):
        for raw, expected in [(b'\x89PNG\r\n\x1a\n' + style.MARKER, True),
                              (b'\x89PNG\r\n\x1a\nold footer', False),
                              (style.MARKER, False)]:
            with patch.object(bp.urllib.request, 'urlopen', return_value=io.BytesIO(raw)):
                self.assertEqual(bp.plain_art_live('https://example.com/new.png'), expected)

    def test_new_schedule_refuses_stale_house_art_before_provider_creation(self):
        calls=[]
        with patch.object(bp, 'live_card_url', return_value='https://example.com/card.png'), \
             patch.object(bp, 'ticket_art_live', return_value=True), \
             patch.object(bp, 'plain_art_live', return_value=False):
            bp.schedule([('r','research','Research, not a bet.',NOW+timedelta(hours=1),'card')],
                        'channel',{'posts':[]},NOW,key='t',send=lambda *a:calls.append(a),log=lambda *_:None)
        self.assertFalse(calls)
