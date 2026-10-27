import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import social_voice
import social_style
import x_post
import buffer_post
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class SocialVoiceTests(unittest.TestCase):
    def test_live_schedule_uses_same_voice_on_both_channels(self):
        now = datetime(2026, 10, 22, 20, tzinfo=timezone.utc)
        old = "A 20+ points (-110, FanDuel)\n\n❤️ if you're tailing"
        with patch.object(buffer_post, 'create_post', return_value='test') as send:
            log = buffer_post.schedule([('test', 'play', old, now + timedelta(hours=1), None)],
                                      'x', {'posts': []}, now, log=lambda *_: None)
        expected = social_voice.finish(old)
        self.assertEqual(send.call_args.args[0], expected + '\n\nCopy the bet 👇 @Playbook\n\n21+ only')
        self.assertEqual(log['posts'][0]['discord']['text'], expected + '\n\n21+ only')

    def test_old_queued_caption_rechecked_sent_post_preserved(self):
        now = datetime(2026, 10, 22, 20, tzinfo=timezone.utc)
        row = dict(bufferPostId='test', dueAt='2026-10-23T14:00:00Z',
                   socialStyleVersion=social_style.VERSION, queuedText="Still climbing? ❤️")
        self.assertTrue(buffer_post.style_audit_due(row, now))
        self.assertFalse(buffer_post.style_audit_due(dict(row, sentAt='2026-10-22T19:00:00Z'), now))

    def test_preview_is_human_not_promised_ticket(self):
        text = social_voice.climb_preview('Friday')
        self.assertIn('80/20 Climb', text)
        self.assertNotIn('$', text)
        self.assertIn('Got my eye on Friday', text)
        self.assertIn('Looking for two legs I love.', text)
        self.assertFalse(x_post.x_style(text))
        self.assertFalse(social_style.issues(text))
        self.assertLessEqual(x_post.tweet_length(text), 280)

    def test_facts_and_leg_lines_are_unchanged(self):
        text = "My ticket +668 boosted (+446 before boost)\n\nA 20+ points\nB 6+ rebounds\n\n❤️ if you're tailing"
        got = social_voice.finish(text)
        self.assertEqual(got.split('\n\n')[:2], text.split('\n\n')[:2])
        self.assertEqual(social_voice.finish(got), got)

    def test_losses_and_research_not_promoted(self):
        for text in ('Lost. 0-2 tonight.', 'Research, not a bet.', 'Last season: 8 of 10.'):
            self.assertEqual(social_voice.finish(text), text)
        self.assertEqual(social_voice.finish('Not picks yet. Just where my numbers start.'), 'Research, not a bet.')

    def test_status_report_rejected_but_hype_allowed(self):
        self.assertTrue(social_style.issues("Next Climb target: Friday. I'll post it when it qualifies."))
        self.assertFalse(x_post.x_style("Let's ride 🍳"))
        self.assertTrue(x_post.x_style('Guaranteed free money'))
