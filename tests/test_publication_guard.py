import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publication_guard as guard


class PublicationGuardTests(unittest.TestCase):
    def test_reviewed_paths_and_old_public_evidence_remain_allowed(self):
        for path in ('.nojekyll', 'index.html', 'app-more.js', 'kookn-mark.png', 'data/research.json', 'data/forecasts.json', 'data/app/today.json', 'data/app/today-hero.json',
                     'data/app/record.json', 'data/app/lines.json', 'data/app/lines-NFL.json',
                     'data/app/lines-CFB.json', 'data/app/trends/index.json',
                     'data/app/trends/NFL-2026-10-08.json', 'data/app/trends/CFB-2026-10-10-milestones.json',
                     'data/app/trends/CFB-2026-10-10-milestones-part-2.json',
                     'data/app/players/NFL/3.json', 'data/app/player-charts/CFB.json',
                     'data/app/teams/NFL/12.json', 'data/app/teams/NFL.json', 'data/app/teams/CFB-defense.json',
                     'data/app/games/NFL-401872979.json', 'data/cards/research-2026-10-05.png',
                     'img/wins/personal-win.jpg', 'data/feed.xml'):
            self.assertTrue(guard.allowed_path(Path(path)), path)

    def test_unreviewed_and_private_artifacts_fail_closed(self):
        for path in ('env', '.env', 'data/desk-health.json', 'data/desk-reliability.json',
                     'data/x-posted.json', 'data/app/policy.json', 'data/app/status.json',
                     'data/app/teams/NFL/../../private.json', 'data/cards/private.zip',
                     'img/.config/card.png', 'data/new-feed.json', 'data/app/trends.json',
                     'data/app/trends/NBA-2026-10-08.json', 'data/app/trends/NFL-all.json', 'archive/review-packet.md'):
            self.assertFalse(guard.allowed_path(Path(path)), path)

    def test_retired_preview_paths_are_not_public(self):
        for path in ('next/index.html', 'next/app.css', 'next/app.js', 'next/data.json',
                     'next/AUDIT.md', 'next/nested/app.js', 'next/.env'):
            self.assertFalse(guard.allowed_path(Path(path)), path)

    def test_public_facts_and_source_links_are_not_credentials(self):
        payload = {'id': 'pick-1', 'odds': -108, 'raw': .625, 'chance': .552,
                   'why': 'Saved supporting and opposing evidence.', 'sources': ['https://www.espn.com/nfl/']}
        self.assertFalse(guard.contains_private_key(payload))

    def test_nested_credentials_block_even_empty_to_reject_schema(self):
        for field in ('apiKey', 'access_token', 'client-secret', 'discordReviewWebhookUrl', 'password'):
            self.assertTrue(guard.contains_private_key({'rows': [{'nested': {field: None}}]}), field)

    def test_audit_is_read_only_and_never_prints_matched_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'index.html').write_text('<title>Site</title>')
            (root / 'data').mkdir()
            secret = 'private-example-not-a-real-secret'
            path = root / 'data/research.json'
            original = json.dumps({'rows': [{'accessToken': secret}]})
            path.write_text(original)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = guard.main(['--site', tmp])
            self.assertEqual(status, 1)
            self.assertNotIn(secret, output.getvalue())
            self.assertEqual(path.read_text(), original)
            self.assertEqual(json.loads(output.getvalue())['issues'][0]['reason'], 'private-payload-field')

    def test_known_credential_urls_and_private_paths_are_blocked(self):
        values = ['https://discord.com/api/webhooks/123/fake-private-value',
                  'https://example.test/data?apiKey=fake-private-value',
                  '/Users/example/.config/keenroudy/env', '-----BEGIN PRIVATE KEY-----']
        for value in values:
            self.assertTrue(any(p.search(value) for p in guard.PATTERNS), value)

    def test_symlinks_and_malformed_json_are_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'index.html').write_text('<title>Site</title>')
            (root / 'data').mkdir()
            (root / 'data/research.json').write_text('{bad')
            (root / 'app.js').symlink_to('/nonexistent/private-secret')
            result = guard.audit(root)
            self.assertEqual({x['reason'] for x in result['issues']}, {'linked-file', 'invalid-json'})

    def test_hosted_gate_runs_after_build_and_before_upload(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml').read_text()
        self.assertLess(workflow.index('python scripts/feed.py'), workflow.index('python scripts/publication_guard.py'))
        self.assertLess(workflow.index('python scripts/publication_guard.py'), workflow.index('actions/upload-pages-artifact@'))


if __name__ == '__main__':
    unittest.main()
