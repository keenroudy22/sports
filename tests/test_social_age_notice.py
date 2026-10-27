import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post as bp
import discord_post
import social_copy as copy
import social_style

NOW = datetime(2026, 10, 23, 22, tzinfo=timezone.utc)


class SocialAgeNoticeTests(unittest.TestCase):
    def test_buffer_editor_placeholders_are_not_a_missing_age_line(self):
        clean = 'Player over 21.5 points\n\nCopy the bet 👇 @Playbook\n\n21+ only'
        editor = 'Player over 21.5 points\r\n\ufeff\r\n\r\nCopy the bet 👇 @Playbook\r\n\ufeff\r\n\r\n21+ only '
        self.assertEqual(copy.canonical_caption(editor),clean)
        self.assertTrue(copy.age_notice_current(editor))
        for bad in ('Player over 21.5 points',clean+'\n21+ only',clean.replace('21+ only','2\ufeff1+ only')):
            self.assertFalse(copy.age_notice_current(bad))

    def test_pending_editor_caption_is_not_cancelled_for_whitespace(self):
        clean = 'NFL tonight.\n\n21+ only'
        row = dict(id='research:test',kind='buffer:research',bufferPostId='scheduled',
                   dueAt='2026-10-24T01:00:00Z',socialAgeVersion='old')
        with patch.object(bp,'graphql',return_value={'post':{'status':'scheduled','text':'NFL tonight.\n\ufeff\n\n21+ only '}}), \
             patch.object(bp,'delete_post') as delete:
            self.assertEqual(bp.audit_pending_style({'posts':[row]},NOW),[])
        delete.assert_not_called()
        self.assertEqual(row['queuedText'],clean)
        self.assertEqual(row['socialStyleAudit']['state'],'clear')

    def test_one_age_line_preserves_legs_prices_and_stat_thresholds(self):
        original = 'My card +500 FanDuel\n\nA 21+ points\nB 6+ rebounds'
        for tail in ('', '\n\n21+', '\n\n21+ only\n\n21+ only'):
            result = copy.with_age_notice(original + tail)
            self.assertEqual(result, original + '\n\n21+ only')
            self.assertEqual(copy.with_age_notice(result), result)
            self.assertFalse(social_style.issues(result))

    def test_every_x_category_gets_notice_without_extra_ticket_tags(self):
        for kind in ('play', 'community', 'research', 'conversation', 'cashed', 'recap', 'sheet', 'nba-trial'):
            result = copy.x_ticket_copy('A current update', kind, 'example')
            self.assertTrue(result.endswith('\n\n21+ only'), kind)
            self.assertEqual('@Playbook' in result, kind == 'play')

    def test_buffer_boundary_adds_notice_and_refuses_overflow_without_truncation(self):
        calls = []
        def send(url, body, headers):
            calls.append(body)
            return 200, json.dumps({'data': {'createPost': {'post': {'id': 'new'}}}}).encode()
        bp.create_post('Current research', 'channel', NOW, key='test', send=send)
        self.assertEqual(calls[0]['variables']['input']['text'], 'Current research\n\n21+ only')
        with self.assertRaises(bp.BufferError):
            bp.create_post('a' * 280, 'channel', NOW, key='test', send=send)
        self.assertEqual(len(calls), 1)

    def test_discord_boundary_adds_once_and_preserves_stored_draft(self):
        calls = []
        text = 'A 21+ points\nB 6+ rebounds\n\nCopy the bet 👇 @Playbook\n\n21+ only'
        discord_post.send_message('test', text, send=lambda url, body, headers: (calls.append(body) or (204, b'')))
        self.assertEqual(calls[0]['content'], 'A 21+ points\nB 6+ rebounds\n\n21+ only')
        self.assertIn('@Playbook', text)

    def test_owner_winning_slip_intake_uses_the_same_notice(self):
        import chef_wins
        self.assertTrue(copy.age_notice_current(chef_wins.TEXT))
        self.assertEqual(chef_wins.TEXT.count('21+'), 1)

    def test_age_line_is_not_a_reason_or_an_unsupported_wager_number(self):
        import x_post
        pick = {'id': 'test', 'title': 'Team under 40.5', 'line': 40.5,
                'odds': -110, 'book': 'FanDuel', 'direction': 'under', 'marketType': 'total'}
        text = copy.x_ticket_copy('Team under 40.5 (-110, FanDuel)', 'play')
        self.assertIsNone(x_post.reason_in(text))
        self.assertFalse(any('numbers not in the pick' in issue for issue in x_post.guard(text, pick)))
        self.assertTrue(any('numbers not in the pick' in issue
                            for issue in x_post.guard(text + '\nHe had 21 yards.', pick)))

    def test_old_private_caption_reaudited_but_sent_or_unknown_never_deleted(self):
        for status in ('scheduled', 'sent', 'publishing'):
            entry = {'id': 'research:test', 'kind': 'buffer:research', 'bufferPostId': 'old',
                     'dueAt': '2026-10-24T14:00:00Z', 'socialStyleVersion': social_style.VERSION,
                     'queuedText': 'Current research'}
            calls = []
            def send(url, body, headers):
                calls.append(body['query'])
                if 'deletePost' in body['query']:
                    return 200, json.dumps({'data': {'deletePost': {'id': 'old'}}}).encode()
                return 200, json.dumps({'data': {'post': {'id': 'old', 'status': status,
                                                          'text': 'Current research'}}}).encode()
            self.assertTrue(bp.style_audit_due(entry, NOW))
            bp.audit_pending_style({'posts': [entry]}, NOW, key='test', send=send, items={}, log=lambda *_: None)
            self.assertEqual(any('deletePost' in query for query in calls), status == 'scheduled')
            self.assertEqual(entry['queuedText'], 'Current research')
            self.assertEqual('cancelledAt' in entry, status == 'scheduled')

    def test_current_caption_passes_queue_audit_without_changing_art_version(self):
        entry = {'id': 'research:test', 'bufferPostId': 'old', 'dueAt': '2026-10-24T14:00:00Z'}
        with patch.object(bp, 'graphql', return_value={'post': {'status': 'scheduled', 'text': 'Current research\n\n21+ only'}}):
            self.assertFalse(bp.audit_pending_style({'posts': [entry]}, NOW, items={}, log=lambda *_: None))
        self.assertEqual(entry['socialAgeVersion'], copy.AGE_VERSION)
        self.assertFalse(bp.style_audit_due(entry, NOW))
        self.assertEqual(social_style.VERSION, 'units-only-no-decimal-20261027')
