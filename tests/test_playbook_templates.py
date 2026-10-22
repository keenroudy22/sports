import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import social_copy
import buffer_post


class PlaybookTemplateTests(unittest.TestCase):
    def test_ticket_tag_once_and_discord_has_no_dangling_cta(self):
        for kind, guid, item in [('play', 'best-bet', {}), ('play', 'climb', {}),
                                ('community', 'community:personal-ticket:test', {'personalTicket': True})]:
            with self.subTest(kind=kind, guid=guid):
                text = social_copy.x_ticket_copy('A 20+ points\nB 6+ rebounds\n@Playbook #NBA', kind, guid, item)
                self.assertEqual(text.count('@Playbook'), 1)
                self.assertEqual(social_copy.x_ticket_copy(text, kind, guid, item), text)
                mirror = social_copy.without_playbook(text)
                self.assertNotIn('Copy the bet', mirror)
                self.assertNotIn('@Playbook', mirror)
                self.assertIn('A 20+ points\nB 6+ rebounds', mirror)

    def test_non_tickets_never_tagged(self):
        for kind in ('research', 'conversation', 'cashed', 'recap', 'community'):
            text = social_copy.x_ticket_copy('Update\n@Playbook', kind, 'climb-target:Friday')
            self.assertNotIn('@Playbook', text)

    def test_actual_owner_schedule_tags_x_not_discord(self):
        now = datetime(2026, 10, 22, 20, tzinfo=timezone.utc)
        guid = 'community:personal-ticket:test'
        item = dict(personalTicket=True, odds=500, book='FanDuel', legs=['A 20+ points','B 6+ rebounds'])
        with patch.object(buffer_post, 'create_post', return_value='test') as send:
            result = buffer_post.schedule([(guid,'community','old',now+timedelta(hours=1),None)],
                                          'channel',{'posts':[]},now,items={guid:item},log=lambda *_:None)
        self.assertTrue(send.call_args.args[0].endswith(social_copy.PLAYBOOK_CTA))
        mirror = result['posts'][0]['discord']['text']
        self.assertNotIn('@Playbook',mirror)
        self.assertNotIn('Copy the bet',mirror)
        self.assertIn('A 20+ points\nB 6+ rebounds',mirror)
