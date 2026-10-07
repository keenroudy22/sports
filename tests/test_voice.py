import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post
import discord_post
import pick_card
import voice
import x_post


class VoiceTests(unittest.TestCase):
    def test_ordinals_and_model_support_do_not_invent_direction(self):
        import run
        self.assertEqual([run.ordinal(i) for i in (1,2,3,11,12,13,21,82)],['1st','2nd','3rd','11th','12th','13th','21st','82nd'])
    def test_retired_words_and_punctuation_fail_but_records_and_prices_pass(self):
        for text in ('The desk has insights', 'Kitchen’s closed', 'Analyst notes', 'We never force a play', '82th percentile', 'Ladder 2-1'):
            self.assertTrue(voice.lint(text), text)
        self.assertFalse(voice.lint('Season 35–35. Bijan over 70.5 (-110 FD).'))

    def test_every_prompt_and_teaser_passes_the_public_guard(self):
        for text in (*buffer_post.CONVERSATION, *buffer_post.FUN_TEASERS):
            self.assertFalse(x_post.x_style(text), text)

    def test_send_paths_refuse_bad_text_before_the_network(self):
        never = mock.Mock(side_effect=AssertionError('bad copy reached network'))
        with self.assertRaises(buffer_post.BufferError):
            buffer_post.create_post('The desk has insights', 'x', None, key='fake', send=never)
        with self.assertRaises(discord_post.DiscordError):
            discord_post.send_message('fake', 'The desk has insights', send=never)
        never.assert_not_called()

    def test_new_legacy_card_footers_have_the_age_requirement(self):
        # Each legacy template carries its own footer. Existing immutable art is separate.
        source = (Path(__file__).resolve().parents[1] / 'scripts/pick_card.py').read_text()
        self.assertNotIn('Entertainment only. Not advice.', source)
        self.assertGreaterEqual(source.count('21+ · Entertainment only'), 6)


if __name__ == '__main__':
    unittest.main()
