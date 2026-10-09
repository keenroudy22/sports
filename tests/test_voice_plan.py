import json
import sys
import unittest
from unittest import mock
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import voice
import voice_pick
import x_post
import discord_post
import buffer_post
import receipts


class PlanVoiceTests(unittest.TestCase):
    def test_complete_kill_list_and_allowed_words(self):
        banned = list(voice.WHOLE_WORD_BANS) + list(voice.PHRASE_BANS) + [
            'Model 61%', '+4.3 edge', '$0 banked', '4869443', 'Stateate', '(FL) (FL)', 'Reply if you agree?'
        ]
        for text in banned:
            self.assertTrue(voice.lint(text), text)
        for text in ('run game', 'run defense', 'run it back', 'Bucs run the ball',
                     'Both teams run 70+ plays a game', 'edge rusher', 'Sweated that one.'):
            self.assertFalse(voice.lint(text), text)

    def test_every_send_path_fails_closed_on_the_kill_list(self):
        bad = 'This is an official play.'
        with self.assertRaises(x_post.Refused):
            x_post.post_tweet(bad, {}, send=lambda *_: self.fail('X transport must not run'))
        with self.assertRaises(buffer_post.BufferError):
            buffer_post.create_post(bad, 'channel', datetime(2026, 10, 9, tzinfo=timezone.utc),
                                    send=lambda *_: self.fail('Buffer transport must not run'))
        with self.assertRaises(discord_post.DiscordError):
            discord_post.send_message('secret', bad, send=lambda *_: self.fail('Discord transport must not run'))

    def test_owner_written_pools_have_required_depth(self):
        pool = voice_pick.pools()
        self.assertGreaterEqual(len(pool['playShapes']), 4)
        for key in ('totals', 'spreads', 'props'):
            self.assertGreaterEqual(len(pool['numberLines'][key]), 3)
        self.assertGreaterEqual(len(pool['asks']), 3)
        self.assertIn('', pool['asks'])
        self.assertGreaterEqual(len(pool['saves']), 3)
        self.assertIn('', pool['saves'])

    def test_shape_c_fires_for_tk_king_size_gap_and_one_prefix_wins(self):
        pick = {'id': 'CFB-tk', 'player': 'TK King', 'athleteId': '1', 'market': 'recYds',
                'marketType': 'player', 'title': 'TK King over 49.5 receiving yards', 'direction': 'over',
                'line': 49.5, 'projection': 68, 'odds': -110, 'book': 'DraftKings', 'lane': 'upset',
                'why': 'He averaged 8 targets a game in his last 3.'}
        game = {'league': 'CFB', 'kickoff': '2026-10-10T23:30:00Z', 'away': {'name': 'A'}, 'home': {'name': 'B'}}
        text = x_post.draft(pick, game, featured=True, history=[])
        self.assertIn('Book says 49.5. I say 68.', text)
        self.assertEqual(text.count('Hot Plate (POTD)'), 1)
        self.assertNotIn('Upset pick:', text)
        self.assertFalse(voice.lint(text), text)

    def test_variety_limits_shapes_and_asks(self):
        history = []
        for i in range(100):
            day = (date(2026, 1, 5) + timedelta(days=i)).isoformat()
            shape = voice_pick.choose_shape(f'p{i}', day, history=history)
            ask = voice_pick.choose_slot('ask', f'p{i}', day, history=history)
            if history:
                self.assertNotEqual(shape, history[-1]['copyVariant'])
                self.assertNotEqual(ask, history[-1]['ask'])
            history.append({'kind': 'play', 'series': 'play', 'postedAt': day + 'T12:00:00Z',
                            'copyVariant': shape, 'ask': ask})
        weeks = {}
        for row in history:
            weeks.setdefault(voice_pick.week_key(row['postedAt']), []).append(row)
        for week in weeks.values():
            for shape in 'ABCD':
                self.assertLessEqual(sum(row['copyVariant'] == shape for row in week), max(1, int(len(week) * .4)))

    def test_result_reactions_follow_the_settled_margin(self):
        base = {'id': 'p', 'title': 'Player over 49.5 receiving yards', 'market': 'recYds',
                'athleteId': '1', 'direction': 'over', 'line': 49.5, 'result': 'win'}
        with mock.patch('result_display.stat_line', return_value='75 yards on 8 catches'):
            self.assertTrue(receipts.win_reaction(dict(base, actualValue=75)).startswith('Not close. ✅'))
            self.assertTrue(receipts.win_reaction(dict(base, actualValue=52)).startswith('Sweated that one. ✅'))
            self.assertTrue(receipts.win_reaction(dict(base, direction='under', actualValue=20)).startswith('✅ Player'))
            self.assertTrue(receipts.win_reaction(dict(base, actualValue=60, lateCrossing=True)).startswith('Took till the 4th. ✅'))


if __name__ == '__main__':
    unittest.main()
