"""app/today-hero.json: Today's first paint for the owner's 10-second visit (DIRECTION-RULES section 5)."""
import inspect
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import ladder
import payload_budget
import publication_guard

NOW = datetime(2026, 10, 10, 14, tzinfo=timezone.utc)          # Saturday 10:00 AM Eastern


def pick(pid, **fields):
    row = {'id': pid, 'league': 'NFL', 'kind': 'props', 'title': f'{pid} title', 'displayTitle': f'{pid} over 49.5',
           'market': 'recYds', 'marketType': 'prop', 'athleteId': '9', 'position': 'WR', 'line': 49.5,
           'direction': 'over', 'odds': -110, 'book': 'FanDuel', 'kickoff': '2026-10-10T20:00Z', 'status': 'active',
           'favorite': False, 'modelLean': True, 'featured': False, 'publishedAt': '2026-10-10T13:00:00Z',
           'expiresAt': '2026-10-10T19:00:00Z', 'cutoffOdds': -124, 'cutoffLine': 49.5, 'entryNote': None,
           'result': None, 'historicalImport': False, 'legs': None, 'parlayType': None, 'riskUnits': None,
           'why': 'Long saved reasoning that the hero never copies.', 'reasons': ['Role: first read.'],
           'probabilityAtPublication': {'chance': .56, 'breakEven': .524, 'rawChance': .61, 'calibrated': True}}
    row.update(fields)
    return row


def rung(pid, published, result=None, **ladder_fields):
    return pick(pid, kind='parlays', parlayType='ladder', legs=['A 50+', 'B 40+'], publishedAt=published,
                result=result, ladder=ladder_fields, odds=-150)


class TodayHeroTests(unittest.TestCase):
    def test_todays_unsettled_best_bets_lead_with_price_book_kickoff_and_card(self):
        picks = [
            pick('NFL-late', kickoff='2026-10-11T00:20Z'),
            pick('NFL-potd', featured=True, kickoff='2026-10-10T23:00Z'),
            pick('CFB-total', league='CFB', kind='gamePicks', market=None, marketType='total', athleteId=None,
                 position=None, kickoff='2026-10-10T16:00Z'),
            pick('CFB-moved', league='CFB', kickoff='2026-10-10T19:30Z', status='expired',
                 entryNote='Closed to new entries at 11:45 AM ET: total moved 3 against.'),
            pick('NFL-pulled', entryNote='Pulled over news before its post went out.'),
            pick('NFL-withdrawn', status='withdrawn'),
            pick('NFL-graded', result='win', kickoff='2026-10-10T13:00Z'),
            pick('NFL-fun', kind='parlays', legs=['x', 'y'], parlayType='longshot'),
            rung('NFL-rung', '2026-10-10T12:00:00Z', stake=50, step=1, run=1),
            pick('NFL-import', historicalImport=True),
            pick('NFL-tomorrow', kickoff='2026-10-11T17:00Z'),
        ]
        hero = build_site.today_hero(picks, NOW, potd='NFL-potd')
        self.assertEqual(hero['day'], '2026-10-10')
        self.assertEqual([b['id'] for b in hero['bets']], ['NFL-potd', 'CFB-total', 'CFB-moved', 'NFL-late'],
                         "Pick of the Day first, then kickoff; Saturday's 8:20 PM ET game is still Saturday")
        potd = hero['bets'][0]
        self.assertEqual((potd['displayTitle'], potd['odds'], potd['book'], potd['kickoff']),
                         ('NFL-potd over 49.5', -110, 'FanDuel', '2026-10-10T23:00Z'))
        self.assertTrue(potd['featured'])
        self.assertEqual(potd['card'], 'data/cards/NFL-potd-potd.png')
        self.assertEqual(potd['probabilityAtPublication'], {'chance': .56, 'breakEven': .524})
        self.assertNotIn('why', potd)
        self.assertNotIn('status', potd, 'an active play needs no status field')
        by_id = {b['id']: b for b in hero['bets']}
        self.assertEqual(by_id['CFB-total']['card'], 'data/cards/CFB-total.png')
        self.assertNotIn('card', by_id['CFB-moved'], 'feed.py draws no card for a play closed to new entries')
        self.assertEqual(by_id['CFB-moved']['status'], 'expired')
        self.assertIn('entryNote', by_id['CFB-moved'], 'the site still labels it off the card')
        self.assertEqual(hero['more'], 0)

    def test_no_card_once_the_game_starts_and_ids_must_be_public_file_names(self):
        started = pick('NFL-started', kickoff='2026-10-10T13:30Z')
        self.assertIsNone(build_site.hero_card(started, NOW))
        self.assertIsNone(build_site.hero_card(pick('../escape'), NOW))
        self.assertIsNone(build_site.hero_card(pick('NFL-research', modelLean=False, favorite=False), NOW),
                          'feed.postable draws no card for a row it would not post')
        card = build_site.hero_card(pick('NFL-open'), NOW)
        self.assertTrue(publication_guard.allowed_path(Path(card)), card)

    def test_with_no_bet_today_the_next_game_day_still_on_the_card(self):
        picks = [pick('CFB-mon-moved', kickoff='2026-10-12T23:00Z', entryNote='Closed to new entries: line moved.'),
                 pick('CFB-mon', kickoff='2026-10-12T23:30Z'),
                 pick('CFB-tue', kickoff='2026-10-13T23:30Z'),
                 pick('NFL-yesterday', kickoff='2026-10-09T23:00Z')]
        hero = build_site.today_hero(picks, NOW)
        self.assertEqual([b['id'] for b in hero['bets']], ['CFB-mon'])
        self.assertEqual(build_site.today_hero([pick('NFL-yesterday', kickoff='2026-10-09T23:00Z')], NOW)['bets'], [],
                         'an ungraded play from yesterday is waiting on a result, not today\'s bet')

    def test_a_league_with_no_bet_today_brings_its_own_next_game_day(self):
        """A saved NFL filter on an all-college day sees the NFL play the full card leads with, not an empty hero."""
        picks = [pick('CFB-today', league='CFB', kickoff='2026-10-10T19:30Z'),
                 pick('NFL-mon-moved', kickoff='2026-10-13T00:15Z', entryNote='Closed to new entries: line moved.'),
                 pick('NFL-mon', kickoff='2026-10-13T00:20Z', featured=True),
                 pick('NFL-thu-next-week', kickoff='2026-10-16T00:15Z'),
                 pick('CFB-thu', league='CFB', kickoff='2026-10-15T23:30Z')]
        hero = build_site.today_hero(picks, NOW)
        self.assertEqual([b['id'] for b in hero['bets']], ['CFB-today', 'NFL-mon'],
                         "today's college play first, then the NFL's next on-the-card day; CFB already has today")
        self.assertEqual(hero['more'], 0)
        none_today = build_site.today_hero([p for p in picks if p['id'] != 'CFB-today'], NOW)
        self.assertEqual([b['id'] for b in none_today['bets']], ['NFL-mon', 'CFB-thu'],
                         'with no bet today each league brings its next game day; the page shows the earliest')

    def test_a_size_trim_drops_another_days_play_before_any_of_todays(self):
        today = [pick(f'CFB-2026-W6-very-long-player-name-over-149-5-receiving-yards-{i:02d}-dk', league='CFB',
                      displayTitle='A Very Long Player Name ' * 3 + f'over 149.5 receiving yards {i}',
                      kickoff=f'2026-10-10T{16 + i:02d}:00Z') for i in range(6)]
        later = pick('NFL-2026-W6-monday-night-very-long-player-name-over-149-5-receiving-yards-dk',
                     featured=True, kickoff='2026-10-13T00:15Z')
        hero = build_site.today_hero(today + [later], NOW)
        ids = [b['id'] for b in hero['bets']]
        size = len(json.dumps(hero, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode())
        self.assertLessEqual(size, build_site.HERO_BYTES)
        self.assertGreater(hero['more'], 0, 'this slate is built to need a trim')
        self.assertNotIn(later['id'], ids, "another day's play goes first, even a featured one")
        self.assertEqual(ids, [p['id'] for p in today][:len(ids)], "today's plays stay in kickoff order")
        self.assertEqual(len(ids) + hero['more'], 7)

    def test_climb_status_walks_the_rungs_exactly_like_ladder_state(self):
        cases = {
            'open third step': [rung('r1', '2026-09-27T12:00:00Z', 'win', stake=50, payout=94, step=1, run=1),
                                rung('r2', '2026-10-02T12:00:00Z', 'win', stake=75, payout=117, banked=19,
                                     bankedAfter=42, nextStake=94, step=2, run=1),
                                rung('r3', '2026-10-10T12:00:00Z', None, stake=94, banked=42, step=3, run=1)],
            'after a loss': [rung('r1', '2026-09-27T12:00:00Z', 'win', stake=50, payout=94, step=1, run=1),
                             rung('r2', '2026-10-02T12:00:00Z', 'loss', stake=75, banked=19, step=2, run=1)],
            'pulled rung still counts': [rung('r1', '2026-10-02T12:00:00Z', 'win', stake=50, payout=80, step=1, run=1,
                                              ) | {'entryNote': 'Closed at 8:44 AM ET, before its post went out.'}],
            'closed rung does not count': [rung('r1', '2026-10-02T12:00:00Z', None, stake=50, step=1)
                                           | {'entryNote': 'Line moved.'}],
            'reaches the goal': [rung('r1', '2026-10-02T12:00:00Z', 'win', stake=700, payout=1100, banked=200,
                                      step=7, run=1)],
            'push keeps the step': [rung('r1', '2026-10-02T12:00:00Z', 'push', stake=50, step=1, run=1)],
            'no rungs yet': [],
        }
        for name, rungs in cases.items():
            with self.subTest(name):
                first = {r['id']: r for r in rungs}
                truth = ladder.state(first, {})
                hero = build_site.hero_climb(rungs + [pick('NFL-straight')])
                self.assertEqual((hero['run'], hero['step'], hero['settled']),
                                 (truth['run'], truth['step'], len(truth['history'])))
                info = (truth['open'] or {}).get('ladder') or {}
                self.assertEqual(hero['riding'], int(info.get('stake') or truth['stake']))
                self.assertEqual(hero['banked'], int(info['banked']) if truth['open'] and 'banked' in info else truth['banked'])
                self.assertEqual(bool(hero.get('open')), bool(truth['open']))
                if truth['history']:
                    self.assertEqual(hero['last']['result'], truth['history'][-1]['result'])
                else:
                    self.assertNotIn('last', hero)

    def test_last_game_day_counts_straight_best_bets_like_today(self):
        picks = [pick('a', result='win', kickoff='2026-10-09T23:00Z', units=.91),
                 pick('b', result='loss', kickoff='2026-10-10T00:15Z', league='CFB'),
                 pick('c', result='loss', kickoff='2026-10-09T17:00Z', earlyExit=True),
                 pick('d', result='push', kickoff='2026-10-09T18:00Z', odds=110),
                 pick('e', result='win', kickoff='2026-10-09T19:00Z', odds=150, riskUnits=2),
                 pick('fun', result='win', kickoff='2026-10-09T20:00Z', kind='parlays', legs=['x'], parlayType='longshot'),
                 pick('old', result='win', kickoff='2026-10-09T21:00Z', historicalImport=True),
                 pick('earlier', result='win', kickoff='2026-10-08T23:00Z'),
                 pick('today', result='loss', kickoff='2026-10-10T13:00Z')]
        last = build_site.today_hero(picks, NOW)['last']
        self.assertEqual({k: last['ALL'][k] for k in ('day', 'wins', 'losses', 'pushes')},
                         {'day': '2026-10-09', 'wins': 2, 'losses': 2, 'pushes': 1},
                         "Friday 8:15 PM ET is Friday; today's graded play is not the last game day")
        self.assertEqual(last['ALL']['kickoff'], '2026-10-10T00:15Z')
        self.assertAlmostEqual(last['ALL']['units'], .91 - 1 + 0 + 0 + 3)
        self.assertEqual((last['CFB']['wins'], last['CFB']['losses']), (0, 1))
        self.assertEqual((last['NFL']['wins'], last['NFL']['losses'], last['NFL']['pushes']), (2, 1, 1))
        self.assertEqual(build_site.today_hero([], NOW)['last'], {})

    def test_a_crowded_slate_stays_under_the_reviewed_budget(self):
        picks = [pick(f'NFL-2026-W5-very-long-player-name-over-149-5-receiving-yards-{i:02d}-dk',
                      displayTitle='A Very Long Player Name ' * 3 + f'over 149.5 receiving yards {i}',
                      entryNote='Closed to new entries at 11:45 AM ET: line moved past our limit. ' * 2 if i % 2 else None,
                      kickoff=f'2026-10-10T{16 + i % 8:02d}:00Z') for i in range(20)]
        hero = build_site.today_hero(picks, NOW)
        size = len(json.dumps(hero, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode())
        self.assertLessEqual(size, build_site.HERO_BYTES)
        self.assertLess(build_site.HERO_BYTES, payload_budget.LIMITS['today-hero'])
        self.assertLessEqual(payload_budget.LIMITS['today-hero'], 4 * 1024)
        self.assertGreater(len(hero['bets']), 0)
        self.assertEqual(len(hero['bets']) + hero['more'], 20, 'every dropped play is counted for the full card')

    def test_the_build_writes_the_hero_beside_today_and_the_guard_reviews_it(self):
        body = inspect.getsource(build_site.build)
        self.assertLess(body.index("'today.json'"), body.index("'today-hero.json'"))
        self.assertIn('featured_store.of_day(eastern_date(now).isoformat())', body)
        self.assertTrue(publication_guard.allowed_path(Path('data/app/today-hero.json')))
        self.assertFalse(publication_guard.allowed_path(Path('data/app/today-hero-full.json')))
        docs = (Path(__file__).resolve().parents[1] / 'docs/PUBLIC-PAYLOADS.md').read_text()
        self.assertIn('`data/app/today-hero.json`', docs)


if __name__ == '__main__':
    unittest.main()
