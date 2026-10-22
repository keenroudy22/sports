import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import boxscores
import climb_validation as v
import ladder
import learn

NOW = datetime(2026, 10, 22, 1, tzinfo=timezone.utc)


def fixture():
    game = dict(league='CFB', eventId='1', season=2026, kickoff='2026-10-20T23:00:00Z',
                retrievedAt='2026-10-21T04:00:00Z', sources={'page': 'https://www.espn.com/game/1'},
                players=[dict(id='p', name='Player One', recYds=20)])
    capture = dict(gameId='CFB-1', retrievedAt='2026-10-20T20:00:00Z', books={
        'fanduel': {'markets': {'recYds': {'Player One': dict(line=30.5, over=-110, under=-110,
            alternates=[dict(line=10.5, over=-200, under=150), dict(line=15.5, over=-210, under=155)])}}}})
    return game, capture


def graded(n=150, wins=150):
    return [dict(id=str(i), segment='CFB/recYds/over/FanDuel/200-249', kickoff=f'{i:06}',
                 odds=-200, result='win' if i < wins else 'loss', revision=str(i)) for i in range(n)]


class ValidationTests(unittest.TestCase):
    def test_latest_capture_one_rung_per_player_band_not_repeated_prices(self):
        game, capture = fixture()
        rows = v.offers([capture]*20, {'CFB-1': game}, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['line'], 15.5)
        later = copy.deepcopy(capture)
        later['retrievedAt'] = '2026-10-20T21:00:00Z'
        later['books']['fanduel']['markets']['recYds']['Player One']['alternates'] = [dict(line=10.5, over=-220)]
        rows = v.offers([later, capture], {'CFB-1': game}, NOW)
        self.assertEqual((len(rows), rows[0]['line'], rows[0]['odds']), (1, 10.5, -220))

    def test_future_inplay_wrong_period_suspended_and_foreign_ladders_excluded(self):
        game, capture = fixture()
        bad = [dict(capture, retrievedAt=game['kickoff']), dict(capture, state='live'),
               dict(capture, marketWindow='First quarter'), dict(capture, suspended=True),
               dict(capture, retrievedAt='2026-10-20T01:00:00Z')]
        self.assertEqual(v.offers(bad, {'CFB-1': game}, NOW), [])
        quote = capture['books']['fanduel']['markets']['recYds']['Player One']
        quote['alternates'] = [dict(line=25.5, over=110), dict(line=10.5, over=-220)]
        self.assertEqual(v.offers([capture], {'CFB-1': game}, NOW), [])

    def test_actual_stats_asof_and_unknown_never_guessed_zero(self):
        game, capture = fixture()
        rows = v.offers([capture], {'CFB-1': game}, NOW)
        self.assertEqual(v.grade(rows, {'CFB-1': game}, NOW)[0]['result'], 'win')
        changed = dict(game, retrievedAt='2026-10-23T00:00:00Z')
        self.assertEqual(v.grade(rows, {'CFB-1': changed}, NOW), [])
        game['players'][0].pop('recYds')
        row = v.grade(rows, {'CFB-1': game}, NOW)[0]
        self.assertIsNone(row['actual']); self.assertIsNone(row['result'])
        self.assertFalse(next(iter(v.summarize([row]*150, NOW).values()))['open'])

    def test_150_and_two_point_and_last100_requirements(self):
        self.assertFalse(next(iter(v.summarize(graded(149,149), NOW).values()))['open'])
        self.assertTrue(next(iter(v.summarize(graded(), NOW).values()))['open'])
        self.assertFalse(next(iter(v.summarize(graded(150,101), NOW).values()))['open'])
        self.assertFalse(next(iter(v.summarize(graded(1100,1000), NOW).values()))['open'])
        rows = graded()
        for i in range(100): rows[i]['result'] = None
        self.assertFalse(next(iter(v.summarize(rows, NOW).values()))['open'])

    def test_exact_side_book_band_reader_and_expiry(self):
        summary = v.summarize(graded(), NOW)
        ctx = SimpleNamespace(now=NOW, policy={'ladderSegments': summary})
        self.assertEqual(ladder.segment_hit_rate(ctx,'CFB','recYds','FanDuel',-210,'over'),1)
        for book, price, side in [('DraftKings',-210,'over'),('FanDuel',-260,'over'),('FanDuel',-210,'under')]:
            self.assertIsNone(ladder.segment_hit_rate(ctx,'CFB','recYds',book,price,side))
        ctx.now += timedelta(days=9)
        self.assertIsNone(ladder.segment_hit_rate(ctx,'CFB','recYds','FanDuel',-210,'over'))
        ctx.policy['ladderSegments']={'CFB/recYds/FanDuel':dict(open=True,graded=1000,hitRate=.99)}
        self.assertIsNone(ladder.segment_hit_rate(ctx,'CFB','recYds','FanDuel',-210,'over'))

    def test_refresh_is_append_only_idempotent_dry_and_uses_asof_box_version(self):
        game, capture = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); store=root/'data/learning'
            for name, rows in [('boxscores',[game,dict(game,retrievedAt='2026-10-23T00:00:00Z')]),('prop-odds',[capture])]:
                path=root/'data'/name/'cfb-2026.jsonl';path.parent.mkdir(parents=True)
                path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            policy={'ladderSegments':{'legacy':dict(open=True)},'history':[]}
            before=copy.deepcopy(policy)
            report=v.refresh(policy,NOW,root,store,dry=True)
            self.assertEqual(report['graded'],1);self.assertEqual(policy,before);self.assertFalse(store.exists())
            self.assertEqual(v.refresh(policy,NOW,root,store)['added'],1)
            saved=(store/'climb-offers-2026.jsonl').read_bytes()
            self.assertEqual(v.refresh(policy,NOW,root,store)['added'],0)
            self.assertEqual((store/'climb-offers-2026.jsonl').read_bytes(),saved)
            self.assertEqual(boxscores.verify(store),[])
            self.assertNotIn('legacy',policy['ladderSegments'])
            corrected=copy.deepcopy(game)
            corrected['players'][0]['recYds']=0
            corrected['retrievedAt']='2026-10-22T00:00:00Z'
            path=root/'data/boxscores/cfb-2026.jsonl'
            with path.open('a') as f:f.write(json.dumps(corrected)+'\n')
            self.assertEqual(v.refresh(policy,NOW,root,store)['added'],1)
            revised=(store/'climb-offers-2026.jsonl').read_bytes()
            self.assertTrue(revised.startswith(saved))
            self.assertEqual(json.loads(revised.decode().splitlines()[-1])['result'],'loss')

    def test_weekly_invokes_validation_writer(self):
        game,capture=fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=root/'data/learning'
            for name,rows in [('boxscores',[game]),('prop-odds',[capture])]:
                path=root/'data'/name/'cfb-2026.jsonl';path.parent.mkdir(parents=True)
                path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            report=learn.weekly(NOW,root=store,log_book={'posts':[]},games={},record=({},{}))
            self.assertEqual(report['climbValidation']['graded'],1)
            self.assertTrue((store/'climb-offers-2026.jsonl').exists())
            self.assertIn('Climb/alternate-offers',learn.markdown(report))
