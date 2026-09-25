import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_post
import build_site
import featured
import feed
import pick_card
import x_post

NOW = datetime(2026, 9, 26, 10, 45, tzinfo=timezone.utc)          # Saturday 6:45 AM ET
GAMES = {'g1': {'id': 'g1', 'league': 'CFB', 'kickoff': '2026-09-26T19:30Z', 'home': {'short': 'Georgia'}, 'away': {'short': 'Oklahoma'}},
         'g2': {'id': 'g2', 'league': 'CFB', 'kickoff': '2026-09-26T23:00Z', 'home': {'short': 'West Virginia'}, 'away': {'short': 'Oklahoma State'}},
         'early': {'id': 'early', 'league': 'CFB', 'kickoff': '2026-09-26T10:00Z', 'home': {'short': 'A'}, 'away': {'short': 'B'}},
         'sunday': {'id': 'sunday', 'league': 'NFL', 'kickoff': '2026-09-27T17:00Z', 'home': {'short': 'Lions'}, 'away': {'short': 'Bills'}}}


def play(key, game, **over):
    base = {'id': key, 'title': f'{key} over 44.5', 'status': 'active', 'modelLean': True, 'marketType': 'total', 'line': 44.5,
            'direction': 'over', 'gameIds': [game], 'book': 'ESPN BET', 'odds': -105, 'projection': 49.6,
            'publishedAt': '2026-09-24T15:45:00Z', 'league': 'CFB'}
    base.update(over)
    return base


EDGES = {'a': 3.1, 'b': 5.4, 'closed': 9.0, 'started': 9.0, 'sunday': 9.0, 'ticket': 9.0}


def fake_desk(pick, ctx):
    edge = EDGES.get(pick['id'])
    return None if edge is None else {'chance': 0.5 + edge / 100, 'breakEven': 0.5, 'rawChance': 0.5 + edge / 100, 'calibrated': True}


class ChooseTests(unittest.TestCase):
    def world(self):
        first = {'a': play('a', 'g1'), 'b': play('b', 'g2'), 'closed': play('closed', 'g1'), 'started': play('started', 'early'),
                 'sunday': play('sunday', 'sunday', league='NFL'), 'ticket': play('ticket', 'g1', legs=[{'title': 'x'}], parlayType='longshot')}
        latest = {'closed': {'entryNote': 'Closed to new entries: the line moved past the cutoff.'}}
        return SimpleNamespace(first=first, latest=latest, games=GAMES, policy={})

    def test_the_biggest_edge_today_is_named_once_and_never_changes(self):
        ctx = self.world()
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(featured.gates, 'desk_for', side_effect=fake_desk):
            path = Path(folder) / 'featured.json'
            self.assertEqual(featured.choose(ctx, NOW, path, log=lambda *_: None), 'b',
                             'closed, started, tomorrow and parlays never count; the biggest edge wins')
            self.assertEqual(featured.load(path)['2026-09-26']['id'], 'b')
            EDGES['a'] = 20.0
            try:
                self.assertEqual(featured.choose(ctx, NOW, path, log=lambda *_: None), 'b', 'once named, the day keeps it')
            finally:
                EDGES['a'] = 3.1

    def test_a_day_without_plays_names_nothing(self):
        ctx = SimpleNamespace(first={}, latest={}, games=GAMES, policy={})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'featured.json'
            self.assertIsNone(featured.choose(ctx, NOW, path, log=lambda *_: None))
            self.assertFalse(path.exists())

    def test_a_pick_pulled_before_it_posts_is_replaced_once_it_has_posted_never(self):
        """Sep 25: the Pick of the Day (Navy at UAB over) closed at 11:03 AM over the quarterback's ankle, before its
        noon post. The best play left that has not posted takes its place; one that went out keeps the day."""
        ctx = self.world()
        closed = {'entryNote': 'Closed to new entries at 11:03 AM ET, before its post went out: verified reporting argues against it'}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(featured.gates, 'desk_for', side_effect=fake_desk):
            path = Path(folder) / 'featured.json'
            quiet = dict(log=lambda *_: None, log_book={'posts': []})
            self.assertEqual(featured.choose(ctx, NOW, path, **quiet), 'b')
            ctx.latest['b'] = closed
            self.assertEqual(featured.choose(ctx, NOW, path, **quiet), 'a', 'the best play left')
            self.assertEqual(featured.load(path)['2026-09-26'], {'id': 'a', 'chosenAt': '2026-09-26T10:45:00Z', 'edge': 3.1, 'replaced': ['b']})
            self.assertEqual(featured.choose(ctx, NOW, path, **quiet), 'a', 'the replacement stays')
            ctx.latest['a'] = closed
            self.assertIsNone(featured.choose(ctx, NOW, path, **quiet), 'nothing left to take its place')
            self.assertEqual(featured.load(path)['2026-09-26']['id'], 'a', 'the record of the day is left as it was')
        ctx = self.world()
        ctx.latest['b'] = closed
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(featured.gates, 'desk_for', side_effect=fake_desk):
            path = Path(folder) / 'featured.json'
            featured.save({'2026-09-26': {'id': 'b'}}, path)
            sent = {'posts': [{'id': 'b', 'sentAt': '2026-09-26T16:00:05Z'}]}
            self.assertEqual(featured.choose(ctx, NOW, path, log=lambda *_: None, log_book=sent), 'b', 'it went out: the day keeps it')
            sent_a = {'posts': [{'id': 'a', 'sentAt': '2026-09-26T16:10:05Z'}]}
            self.assertIsNone(featured.choose(ctx, NOW, path, log=lambda *_: None, log_book=sent_a),
                              'a play that already went out as a plain post cannot become the Pick of the Day')

    def test_a_player_prop_is_judged_on_its_learned_calibration(self):
        pick = play('p', 'sunday', league='NFL', athleteId='7', market='rec', title='Player Seven over 4.5 receptions')
        desk = {'chance': 0.70, 'rawChance': 0.70, 'breakEven': 0.53, 'calibrated': False}
        with mock.patch.object(featured.gates, 'desk_for', return_value=desk):
            self.assertEqual(featured.strength(pick, None, {'calibration': {'NFL/prop': {'k': 0.13}}}), round(100 * (0.5 + 0.13 * 0.2 - 0.53), 2))
            self.assertEqual(featured.strength(pick, None, {}), 17.0, 'before learning ships a calibration, the raw chance stands')


class PostTests(unittest.TestCase):
    def test_the_pick_of_the_day_posts_first_with_its_own_card_and_label(self):
        first = {'a': play('a', 'g1'), 'b': play('b', 'g2')}
        latest = {k: dict(v) for k, v in first.items()}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'featured.json'
            featured.save({'2026-09-26': {'id': 'b', 'chosenAt': '2026-09-26T10:45:00Z', 'edge': 5.4}}, path)
            with mock.patch.object(featured, 'PATH', path):
                plans = [p for p in buffer_post.plan(first, latest, GAMES, NOW, {'posts': []}) if p[1] == 'play']
        self.assertEqual([p[0] for p in plans], ['b', 'a'], 'the Pick of the Day goes first at noon')
        self.assertTrue(plans[0][2].startswith('🍳 PICK OF THE DAY · TEAM PROP'))
        self.assertTrue(plans[1][2].startswith('🍳 TEAM PROP'))
        self.assertEqual((plans[0][4], plans[1][4]), ('b-potd', 'a'), 'its own card, so no stale copy is ever attached')

    def test_the_label_on_the_card(self):
        self.assertEqual(pick_card.kicker(play('a', 'g1'), featured=True), 'PICK OF THE DAY · TEAM PROP')
        self.assertEqual(pick_card.kicker(play('a', 'g1', favorite=True)), 'TEAM PROP · FAVORITE')
        svgs = []
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(pick_card, 'chrome_path', return_value='chrome'), \
                mock.patch.object(pick_card, 'render', side_effect=lambda svg, path: svgs.append(svg)):
            feed.render_cards([{'guid': 'a-potd', 'pick': play('a', 'g1'), 'game': GAMES['g1'], 'featured': True}], folder, log=lambda *_: None)
        self.assertIn('PICK OF THE DAY', svgs[0])

    def test_scheduling_remembers_the_card_and_the_label(self):
        sent = []
        with mock.patch.object(buffer_post, 'create_post', side_effect=lambda *a, **k: sent.append(a) or 'post-1'), \
                mock.patch.object(buffer_post, 'reachable', return_value=True):
            log_book = buffer_post.schedule([('b', 'play', '🍳 PICK OF THE DAY · TEAM PROP\nb', NOW, 'b-potd')], 'ch', {'posts': []}, NOW, log=lambda *_: None)
        entry = log_book['posts'][0]
        self.assertEqual((entry['cardKey'], entry['featured']), ('b-potd', True))
        self.assertEqual(sent[0][3], 'https://keenroudy.com/sports/data/cards/b-potd.png')

    def test_the_site_marks_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'featured.json'
            featured.save({'2026-09-26': {'id': 'b'}}, path)
            with mock.patch.object(featured, 'PATH', path):
                rows = build_site.board_picks({'a': play('a', 'g1'), 'b': play('b', 'g2')}, {}, {}, {})
        self.assertEqual({r['id']: r['featured'] for r in rows}, {'a': False, 'b': True})


if __name__ == '__main__':
    unittest.main()
