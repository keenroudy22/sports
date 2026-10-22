import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import feed
import research_posts
import voice


class OwnerSocialVoiceTests(unittest.TestCase):
    def test_exact_research_label_allowed_without_guarantee_or_generic_disclaimer_bypass(self):
        self.assertEqual(voice.lint('My NBA scores\nResearch, not a bet.\n#NBA'), [])
        self.assertTrue(voice.lint('Research, not a guaranteed win.'))
        self.assertTrue(voice.lint('Research, not a bet. This is guaranteed.'))

    def test_queued_card_is_frozen_but_unqueued_draft_is_not(self):
        log = {'posts': [{'id': 'nba-projections-2026-10-22', 'card': 'url', 'bufferPostId': 'queued'},
                         {'id': 'research-draft', 'card': 'url'},
                         {'id': 'research-sent', 'card': 'url', 'sentAt': '2026-10-22T12:00Z'}]}
        self.assertEqual(feed.frozen_research_keys(log), {'nba-projections-2026-10-22', 'research-sent'})

    def test_research_preserves_frozen_art_and_missing_original_fails_closed(self):
        now = datetime(2026, 10, 22, 13, tzinfo=timezone.utc)
        choice = {'key': 'research-season-2026-10-22', 'kind': 'season', 'rows': [{}, {}]}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(research_posts, 'load', return_value={'games': []}), \
                 patch.object(research_posts, 'details_for', return_value={}), \
                 patch.object(research_posts, 'teams_for', return_value={}), \
                 patch.object(research_posts, 'select', return_value=choice), \
                 patch('tnf_early_look.ENABLED', False), \
                 patch.object(research_posts.pick_card, 'render') as render:
                path = root / (choice['key'] + '.png')
                path.write_bytes(b'original')
                self.assertEqual(research_posts.render_due(now, root, posted_keys={choice['key']}), {choice['key']: path})
                self.assertEqual(path.read_bytes(), b'original')
                render.assert_not_called()
                path.unlink()
                with self.assertRaisesRegex(ValueError, 'Original frozen research art missing'):
                    research_posts.render_due(now, root, posted_keys={choice['key']})
