import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post as bp
import community_record
import desk_health
import publication_guard
import result_display
import settlement_audit
import discord_post

NOW = datetime(2026, 11, 16, 18, tzinfo=timezone.utc)


class ReliabilityBoundaries(unittest.TestCase):
    def test_public_ticket_projection_preserves_private_ledger_and_unit_math(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'data').mkdir()
            ticket = dict(id='ticket', title='Two legs', league='NFL', kickoff='2026-11-16T17:00Z',
                          legs=['A', 'B'], stakeDollars=10, potentialReturnDollars=100,
                          betId='private-id', note='private note', unknownPrivateField='secret', odds=900)
            (root/'data/community.json').write_text(json.dumps({'tickets':[ticket]}))
            (root/'data/x-posted.json').write_text(json.dumps({'posts':[dict(id='ticket',sentAt='2026-11-16T16:00Z',link='https://x.com/a/status/1')]}))
            path=root/'data/community-results.jsonl'
            community_record.append(dict(id='ticket',result='win',settledAt='2026-11-16T18:00Z',source='/private/receipt',
                                         stakeDollars=10,returnDollars=100,unitDollars=50,note='$10 returned $100; bet ID private-id'),path)
            original=path.read_bytes(); row=community_record.build(root)[0]
            self.assertEqual((row['units'],row['riskUnits']),(1.8,.2))
            self.assertFalse(publication_guard.contains_private_key(row))
            self.assertNotIn('private',json.dumps(row)); self.assertNotIn('$',json.dumps(row))
            self.assertEqual(path.read_bytes(),original)
            self.assertTrue(publication_guard.contains_private_key({'nested':[{'returnDollars':100}]}))

    def test_quarantined_money_image_cannot_return_under_another_filename(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'index.html').write_text('<title>Test</title>')
            image=root/'img/tickets/renamed.png'; image.parent.mkdir(parents=True)
            data=b'private ticket fixture'; image.write_bytes(data)
            with patch.object(publication_guard,'PRIVATE_IMAGE_HASHES',frozenset((hashlib.sha256(data).hexdigest(),))):
                self.assertEqual(publication_guard.audit(root)['issues'],
                    [{'file':'img/tickets/renamed.png','reason':'personal-money-image'}])

    def test_current_repository_contains_only_public_community_sources(self):
        self.assertEqual(community_record.source_privacy_issues(), [])
        self.assertTrue((community_record.ROOT/'data/community-settlements.jsonl').is_file())

    def test_default_accounting_append_is_private_and_public_projection_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'public'; private=Path(folder)/'private'
            row=dict(id='ticket',result='win',settledAt='2026-11-16T18:00Z',source='private receipt',
                     stakeDollars=10,returnDollars=100,unitDollars=50,note='$10 wager; bet ID private')
            with patch.object(community_record,'ROOT',root),patch.object(community_record,'private_root',return_value=private):
                self.assertTrue(community_record.append(row))
                self.assertFalse(community_record.append(row))
            original=private/'community-results.jsonl'
            self.assertEqual(json.loads(original.read_text()),row)
            public=(root/'data/community-settlements.jsonl').read_text()
            self.assertEqual(len(public.splitlines()),1)
            self.assertNotIn('Dollars',public);self.assertNotIn('$',public);self.assertNotIn('private receipt',public)
            self.assertEqual(json.loads(public)['units'],1.8)
            self.assertFalse((root/'data/community-results.jsonl').exists())

    def test_stat_revision_cannot_mix_caption_and_margin_versions(self):
        pick=dict(id='daniels',athleteId='1',market='car',actualValue=10,line=5.5,direction='under',result='loss')
        game={'players':[{'id':'1','car':11,'rushYds':50}]}
        self.assertEqual(result_display.detail(pick,game),'10 carries · missed by 4.5')
        corrected=dict(pick,actualValue=11,settlementStats={'car':11,'rushYds':50})
        self.assertEqual(result_display.detail(corrected,game),'11 carries · missed by 5.5')
        # A later dated correction can inherit older context through the record merge.
        stale_snapshot=dict(corrected,settlementStats={'car':10,'rushYds':50})
        self.assertEqual(result_display.detail(stale_snapshot,game),'11 carries · missed by 5.5')
        dorwart=dict(pick,market='recYds',actualValue=21,line=49.5,result='win',settlementStats={'recYds':21,'rec':2,'tgt':3})
        self.assertEqual(result_display.detail(dorwart,game),'2 catches on 3 targets, 21 yards · cleared by 28.5')
        game.update(league='NFL',eventId='2')
        self.assertEqual(len(settlement_audit.drift([dict(pick,gameId='NFL-2')],[game])),1)
        self.assertEqual(settlement_audit.drift([dict(corrected,gameId='NFL-2')],[game]),[])

    def test_sent_missing_media_is_flagged_and_never_reposted(self):
        row=dict(id='pick',kind='buffer:play',card=True,bufferPostId='buffer1',dueAt='2026-11-16T17:00Z')
        post=dict(status='sent',sentAt='2026-11-16T17:01Z',externalLink='https://x.com/keenkooks/status/123',assets=[])
        with patch.object(bp,'audit_pending_style',return_value=[]),patch.object(bp,'graphql',return_value={'post':post}) as query:
            failures=bp.reconcile({'posts':[row]},NOW,log=lambda *_:None)
            self.assertEqual(row['mediaReceipt']['state'],'missing');self.assertEqual(len(failures),1)
            bp.reconcile({'posts':[row]},NOW,log=lambda *_:None)
            self.assertEqual(query.call_count,1)
        self.assertNotIn('error',row)
        self.assertEqual(desk_health.delivery([row],NOW)['xMediaMissing'],1)
        bp.record_sent_evidence(row,{**post,'assets':[{'source':'https://cdn.buffer.com/image.png','mimeType':'image/png'}]},NOW)
        self.assertEqual(row['mediaReceipt']['state'],'attached')
        bp.record_sent_evidence(row,{},NOW)
        self.assertEqual(row['mediaReceipt']['state'],'unverified')

    def test_sent_flag_without_time_or_image_never_fabricates_receipt(self):
        row=dict(id='pick',kind='buffer:play',card=True,bufferPostId='buffer1',dueAt='2026-11-16T17:00Z')
        with patch.object(bp,'audit_pending_style',return_value=[]),patch.object(bp,'graphql',return_value={'post':{'status':'sent'}}):
            self.assertEqual(len(bp.reconcile({'posts':[row]},NOW,log=lambda *_:None)),1)
        self.assertNotIn('sentAt',row)
        self.assertEqual(row['deliveryReceipt']['state'],'unverified')
        self.assertEqual(desk_health.delivery_outcome({'sentAt':'2026-11-16T17:00Z'},'x',NOW),'unknown')
        self.assertEqual(desk_health.delivery_outcome({'discord':{'state':'sent'}},'discord',NOW),'unknown')

    def test_corrected_art_gets_new_url_and_does_not_create_another_post(self):
        import receipts
        pick=dict(id='pick',result='win',kind='props')
        old=receipts.result_card_key(pick)
        new=receipts.result_card_key(dict(pick,correctedAt='2026-11-16T18:00Z'))
        self.assertNotEqual(old,new)
        self.assertIn('-correction-',new)

    def test_discord_receipt_is_saved_without_duplicate_send(self):
        row=dict(id='pick',kind='buffer:play',discord=dict(state='pending',readyAt='2026-11-16T17:00Z',text='Pick'))
        with patch.object(discord_post,'send_message',return_value={'id':'message1','image':'https://cdn.discordapp.com/card.png'}) as send:
            discord_post.mirror_sent({'posts':[row]},NOW,url='plays',log=lambda *_:None)
            discord_post.mirror_sent({'posts':[row]},NOW,url='plays',log=lambda *_:None)
            self.assertEqual(send.call_count,1)
            self.assertTrue(send.call_args.kwargs['return_receipt'])
        self.assertEqual(row['discord']['messageId'],'message1')
        self.assertEqual(row['discord']['attachmentReceipt'],'https://cdn.discordapp.com/card.png')

    def test_discord_embed_fallback_is_not_a_verified_durable_attachment(self):
        row=dict(id='pick',kind='buffer:play',discord=dict(state='pending',readyAt='2026-11-16T17:00Z',
                 text='Pick',image='https://keenroudy.com/card.png'))
        with patch.object(discord_post,'send_message',return_value={'id':'message1','image':None}) as send:
            discord_post.mirror_sent({'posts':[row]},NOW,url='plays',log=lambda *_:None)
            discord_post.mirror_sent({'posts':[row]},NOW,url='plays',log=lambda *_:None)
            self.assertEqual(send.call_count,1)
        self.assertEqual(row['discord']['attachmentState'],'missing')
        self.assertEqual(desk_health.delivery([row],NOW)['discordMediaMissing'],1)
        row['discord'].pop('attachmentState')
        self.assertEqual(desk_health.delivery([row],NOW)['discordMediaUnverified'],1)

    def test_one_minute_quote_window_alerts_before_thirty_minute_delay(self):
        import nba_trial_runtime, cbb_picks
        play=dict(id='nba',publishedAt='2026-11-16T17:59Z',kickoff='2026-11-16T23:00Z',
                  sourceReview={'quote':{'checkedAt':'2026-11-16T17:01Z'}})
        post=dict(id='nba',kind='buffer:nba-trial',nbaPick=True,discord={'state':'sent','sentAt':'2026-11-16T17:59Z','messageId':'1'})
        with patch.object(nba_trial_runtime,'public_rows',return_value=[play]),patch.object(cbb_picks,'public_rows',return_value=[]):
            gap=desk_health.basketball_missing_originals(Path('.'),[post],NOW)['nba']
            self.assertEqual(gap['deadline'],'2026-11-16T18:01:00Z')
            self.assertEqual(gap['state'],'awaiting')
            expired=desk_health.basketball_missing_originals(Path('.'),[post],NOW.replace(minute=2))['nba']
            self.assertEqual(expired['state'],'expired')

if __name__=='__main__': unittest.main()
