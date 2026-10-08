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
        for text in ('The desk has insights', 'Kitchen’s closed', 'Analyst notes', 'We never force a play', '82th percentile', 'Ladder 2-1',
                     'We have it at 47.', 'We project 200 yards.', 'POTD: The line', "If you're climbing", 'Plated.',
                     "That's why we bank it.", 'One miss can change everything.'):
            self.assertTrue(voice.lint(text), text)
        self.assertFalse(voice.lint('🍳 Hot Plate (POTD): a real priced line.'))
        self.assertFalse(voice.lint('Season 35–35. Bijan over 70.5 (-110 FD).'))

    def test_send_paths_refuse_bad_text_before_the_network(self):
        never = mock.Mock(side_effect=AssertionError('bad copy reached network'))
        with self.assertRaises(buffer_post.BufferError):
            buffer_post.create_post('The desk has insights', 'x', None, key='fake', send=never)
        with self.assertRaises(discord_post.DiscordError):
            discord_post.send_message('fake', 'The desk has insights', send=never)
        never.assert_not_called()

    def test_bare_athlete_id_never_reaches_any_public_send_or_card(self):
        for text in ('4869443: 0 receiving yards', 'Final: 4869443: 0 receiving yards'):
            self.assertTrue(voice.lint(text))
            never = mock.Mock(side_effect=AssertionError('bare id reached network'))
            with self.assertRaises(buffer_post.BufferError):
                buffer_post.create_post(text, 'x', None, key='fake', send=never)
            with self.assertRaises(discord_post.DiscordError):
                discord_post.send_message('fake', text, send=never)
            with self.assertRaises(x_post.Refused):
                x_post.post_tweet(text, {}, send=never)
            never.assert_not_called()
        with self.assertRaises(ValueError):
            pick_card.render('<svg><text>4869443: 0 receiving yards</text></svg>', '/tmp/never-render.png')

    def test_new_legacy_card_footers_have_the_age_requirement(self):
        # Each legacy template carries its own footer. Existing immutable art is separate.
        source = (Path(__file__).resolve().parents[1] / 'scripts/pick_card.py').read_text()
        self.assertNotIn('Entertainment only. Not advice.', source)
        self.assertGreaterEqual(source.count('21+ · Entertainment only'), 6)


if __name__ == '__main__':
    unittest.main()
