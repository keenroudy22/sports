"""Kitchen Ticket website data (OWNER-DECISIONS 2026-10-07 item 22): every word and row Today shows is chosen at
build time from saved fields, never written or selected in the browser."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import direction
import publication_guard
import role_sanity
import voice

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 7, 18, tzinfo=timezone.utc)          # Wednesday 2:00 PM Eastern
TEAMS = {'away': {'id': '166', 'abbr': 'NMSU', 'name': 'New Mexico St', 'color': '#7e141b', 'alt': '#231f20'},
         'home': {'id': '2229', 'abbr': 'FIU', 'name': 'FIU', 'color': '#091f3f', 'alt': '#c3993f'}}
KING = {'id': 'CFB-2026-W6-king-over-49-5-recyds-dk', 'league': 'CFB', 'kind': 'props', 'athleteId': '4869443',
        'position': 'WR', 'direction': 'over', 'line': 49.5, 'market': 'recYds', 'gameId': 'CFB-401871066',
        'reason': None, 'side': 'away',
        'reasoning': {'context': ['Role: 1st of 1 NMSU WRs by projected targets, 7.3 a game.',
                                  'Defense: FIU allows 133 receiving yards a game to WRs, 55 of 235 this season (1 is stingiest).'],
                      'cautions': ["The opponent's positional allowance points against this side. It covers the whole "
                                   'position group, not just this player.',
                                   'FIU is allowing 14.5 points per game and has not allowed more than 20 points in a game '
                                   'this season.']}}


class TicketWordsTests(unittest.TestCase):
    def test_why_is_the_saved_reason_else_the_first_context_line_else_nothing(self):
        self.assertEqual(build_site.ticket_why({**KING, 'reason': 'Over 3.5 in 9 of his last 10 games.'}),
                         'Over 3.5 in 9 of his last 10 games.', 'the saved reason wins, verbatim')
        self.assertEqual(build_site.ticket_why(KING), "I project 7.3 targets, NMSU's top WR.",
                         'the known Role template, shortened deterministically')
        second = {**KING, 'reasoning': {'context': ['Role: 2nd of 4 MINN WRs by projected targets, 5.1 a game.']}}
        self.assertEqual(build_site.ticket_why(second), 'I project 5.1 targets, No. 2 among MINN WRs.')
        plain = {**KING, 'reasoning': {'context': ['Role: projected for 14.2 carries a game.']}}
        self.assertEqual(build_site.ticket_why(plain), 'I project 14.2 carries.')
        qb = {**KING, 'reasoning': {'context': ['Role: projected for 31.0 att a game.']}}
        self.assertEqual(build_site.ticket_why(qb), 'I project 31 pass attempts.')
        labeled = {**KING, 'reasoning': {'context': ['Defense: FIU allows 133 receiving yards a game to WRs.']}}
        self.assertEqual(build_site.ticket_why(labeled), 'FIU allows 133 receiving yards a game to WRs.')
        for empty in ({'reasoning': {}}, {'reason': '  ', 'reasoning': {'context': []}}, {}):
            self.assertIsNone(build_site.ticket_why(empty))

    def test_long_reasons_keep_the_first_clause_and_never_cut_a_word(self):
        long = ('Bills defensive lineman Ed Oliver left the Patriots game with a knee injury, and cornerback Dee '
                'Alford left with an ankle injury.')
        self.assertEqual(build_site.ticket_why({'reason': long}),
                         'Bills defensive lineman Ed Oliver left the Patriots game with a knee injury.')
        self.assertIsNone(build_site.ticket_why({'reason': 'x' * 120}), 'no clause boundary: the row is left off')

    def test_ticket_words_pass_the_public_copy_guard_or_are_left_off(self):
        for bad in ("Here's the desk insight: this one is a lock.", 'This is a guarantee.', 'Our model says 61% likely.'):
            self.assertIsNone(build_site.ticket_why({'reason': bad}), bad)
            self.assertIsNone(build_site.ticket_but({'reasoning': {'cautions': [bad]}}), bad)
        for text in (build_site.ticket_why(KING), build_site.ticket_but(KING, TEAMS)):
            self.assertEqual(voice.lint(text), [], text)

    def test_but_is_the_first_saved_counterpoint_with_known_templates_shortened(self):
        self.assertEqual(build_site.ticket_but(KING, TEAMS), "FIU's WR defense points against the over.")
        self.assertEqual(build_site.ticket_but({**KING, 'side': None}, TEAMS),
                         "The opponent's positional allowance points against this side.",
                         'without the player\'s side the saved sentence stands on its own')
        later = {**KING, 'reasoning': {'cautions': KING['reasoning']['cautions'][1:]}}
        self.assertEqual(build_site.ticket_but(later, TEAMS), 'No team has scored over 20 on FIU.')
        few = {'reasoning': {'cautions': ['Only 4 of the last 10 games cleared this side of the line; recent results oppose it.']}}
        self.assertEqual(build_site.ticket_but(few), 'Only 4 of his last 10 games cleared this line.')
        thin = {'reasoning': {'cautions': ['Fewer than five stored games at this line; history is limited.']}}
        self.assertEqual(build_site.ticket_but(thin), 'Fewer than five games at this line.')
        stat = {'reasoning': {'cautions': ['Statistical counterpoint: Arizona converted 57.8% of third downs. More text.']}}
        self.assertEqual(build_site.ticket_but(stat), 'Arizona converted 57.8% of third downs.')
        self.assertIsNone(build_site.ticket_but({'risk': 'Only prose, no saved counterpoint.'}),
                          'BUT never falls back to the risk paragraph')

    def test_annotate_sets_side_and_words_and_returns_the_game_teams(self):
        game = {'id': 'CFB-401871066', 'league': 'CFB', 'kickoff': '2026-10-07T23:30Z',
                'away': {'id': '166', 'abbreviation': 'NMSU', 'color': '7e141b', 'alternateColor': '231f20'},
                'home': {'id': '2229', 'abbreviation': 'FIU', 'color': '091f3f', 'alternateColor': 'c3993f'}}
        snapshot = {'publishedAt': '2026-10-05T03:32:35Z',
                    'players': {'away': {'players': [{'id': '4869443', 'pos': 'WR'}]}, 'home': {'players': []}}}
        spread = {'id': 's', 'gameId': game['id'], 'marketType': 'spread', 'direction': 'home', 'reasoning': {}}
        fun = {'id': 'f', 'gameId': game['id'], 'legs': ['a', 'b'], 'parlayType': 'longshot'}
        picks = [dict(KING, side=None), spread, fun]
        teams = build_site.annotate_tickets(picks, {game['id']: game}, {game['id']: [snapshot]}, {}, {})
        self.assertEqual(picks[0]['side'], 'away')
        self.assertEqual(picks[0]['ticketBut'], "FIU's WR defense points against the over.")
        self.assertEqual(picks[1]['side'], 'home')
        self.assertNotIn('ticketWhy', fun, 'fun tickets and Climb rungs carry no ticket words')
        self.assertEqual(teams[game['id']]['away']['abbr'], 'NMSU')
        self.assertEqual(teams[game['id']]['home']['color'], '#091f3f')
        fallback = {**KING, 'side': None}
        logs = {'CFB': {'player_logs': {'4869443': [{'team': '166', 'kickoff': '2026-09-26T22:00Z'}]}}}
        build_site.annotate_tickets([fallback], {game['id']: game}, {}, logs, {})
        self.assertEqual(fallback['side'], 'away', 'with no forecast, the player\'s last stored team decides')


class DateLineAndRunsTests(unittest.TestCase):
    def test_desk_runs_come_from_the_launchd_job(self):
        runs = build_site.desk_runs()
        daily = [(r['h'], r['m']) for r in runs if 'wd' not in r]
        self.assertEqual(daily, [(6, 45), (8, 30), (11, 45), (17, 30), (21, 0), (23, 30)])
        self.assertIn({'h': 14, 'm': 45, 'wd': 0}, runs, 'the Sunday 2:45 PM run')
        self.assertEqual(build_site.desk_runs(ROOT / 'missing.plist'), [])

    def test_last_slate_and_season_record_follow_the_site_rules(self):
        picks = [{'id': 'a', 'league': 'NFL', 'result': 'loss', 'kickoff': '2026-10-06T00:15Z', 'odds': -108,
                  'season': 2026, 'seasonType': 2, 'publishedAt': '2026-10-05T15:00:00Z'},
                 {'id': 'b', 'league': 'CFB', 'result': 'win', 'kickoff': '2026-10-03T16:00Z', 'odds': -110,
                  'season': 2026, 'seasonType': 2, 'publishedAt': '2026-10-03T12:00:00Z'},
                 {'id': 'c', 'league': 'CFB', 'result': 'win', 'kickoff': '2026-10-03T16:00Z', 'odds': 120,
                  'legs': ['x'], 'parlayType': 'longshot', 'season': 2026}]
        last = build_site.last_slates(picks, '2026-10-07')
        self.assertEqual((last['ALL']['day'], last['ALL']['wins'], last['ALL']['losses']), ('2026-10-05', 0, 1))
        self.assertEqual((last['CFB']['wins'], last['CFB']['losses']), (1, 0), 'a fun ticket is not a best bet')
        season = build_site.season_records(picks, NOW)
        self.assertEqual((season['ALL']['wins'], season['ALL']['losses'], season['ALL']['playoffs']), (1, 1, False))

    def test_hero_carries_the_ticket_fields_and_stays_inside_its_budget(self):
        pick = {**KING, 'kickoff': '2026-10-07T23:30Z', 'odds': -102, 'book': 'DraftKings', 'status': 'active',
                'displayTitle': 'TK King OVER 49.5 receiving yards', 'featured': True, 'modelLean': True,
                'ticketWhy': "I project 7.3 targets, NMSU's top WR.", 'ticketBut': "FIU's WR defense points against the over.",
                'publishedAt': '2026-10-06T15:45:05Z', 'season': 2026, 'seasonType': 2}
        hero = build_site.today_hero([pick], NOW, teams={KING['gameId']: TEAMS}, runs=[{'h': 17, 'm': 30}])
        bet = hero['bets'][0]
        for key in ('side', 'ticketWhy', 'ticketBut', 'gameId'):
            self.assertEqual(bet[key], pick[key], key)
        self.assertEqual(bet['teams'], TEAMS)
        self.assertEqual(hero['deskRuns'], [{'h': 17, 'm': 30}])
        self.assertIn('ALL', hero['season'])
        self.assertIn('net', hero['climb'])
        self.assertLess(len(json.dumps(hero)), build_site.HERO_BYTES)


def log(event, kickoff, team='2229', pos='WR', **stats):
    return {'eventId': event, 'kickoff': kickoff, 'team': team, 'pos': pos, 'season': 2026, 'seasonType': 2,
            'stats': stats}


class PrepListTests(unittest.TestCase):
    def setUp(self):
        hist = [{'value': v} for v in (60, 72, 55, 80, 41)]          # 4 of 5 over 49.5
        self.row = {'kind': 'main', 'league': 'CFB', 'season': 2026, 'gameId': 'CFB-1', 'kickoff': '2026-10-07T23:30Z',
                    'athleteId': '7', 'player': 'Tyson Carter', 'stat': 'recYds', 'direction': 'over', 'line': 49.5,
                    'odds': -114, 'book': 'FanDuel', 'observedAt': '2026-10-07T17:30:00Z', 'history': hist,
                    'team': {'id': '2229', 'abbreviation': 'FIU', 'color': '#091f3f'}}
        self.logs = {'7': [log('e1', '2026-09-12T20:00Z', pbpTgt=6), log('e2', '2026-09-19T20:00Z', pbpTgt=7),
                           log('e3', '2026-09-26T20:00Z', pbpTgt=5)]}
        self.league = {'CFB': {'player_logs': self.logs}}
        self.rules = dict(direction.PREP_BASE, dropped=[], clearsOnly=False)

    def build(self, rows, lines=(), picks=(), rules=None):
        return build_site.prep_list(rows, list(lines), list(picks), self.league, NOW, rules or self.rules)

    def test_a_qualifying_row_carries_only_saved_facts(self):
        line = {**self.row, 'athleteId': '7', 'grade': {'calibrated': True, 'view': 'lean', 'edge': 2.1}}
        out = self.build([self.row], [line])
        row = out['CFB']['rows'][0]
        self.assertEqual(out['CFB']['day'], '2026-10-07')
        self.assertEqual((row['player'], row['team'], row['pos'], row['hits'], row['games'], row['clears']),
                         ('Tyson Carter', 'FIU', 'WR', 4, 5, True))
        self.assertFalse(self.build([self.row])['CFB']['rows'][0]['clears'], 'no matching grade: history only')

    def test_every_hold_and_playbook_exclusion_keeps_a_row_off(self):
        cases = {
            'role hold on the row': {'roleSuspect': True},
            'price hold on the row': {'priceSuspect': True},
            'injury report': {'injuryStatus': 'Questionable'},
            'alternate line': {'kind': 'alternate'},
            'shorter than -200': {'odds': -210},
            'not a public book': {'book': 'hardrockbet'},
            'stale quote': {'observedAt': '2026-10-07T13:00:00Z'},
            'half-point line': {'line': 0.5, 'stat': 'rec'},
            'under the floor': {'line': 24.5},
            'four games only': {'history': self.row['history'][:4]},
            'three of five': {'history': [{'value': v} for v in (60, 30, 55, 20, 41)]},
            'started': {'kickoff': '2026-10-07T17:00Z'},
        }
        for name, change in cases.items():
            self.assertEqual(self.build([{**self.row, **change}]), {}, name)
        held_line = {'gameId': 'CFB-1', 'athleteId': '7', 'stat': 'recYds', 'roleSuspect': True}
        self.assertEqual(self.build([self.row], [held_line]), {}, 'a hold on any book for that market')
        open_play = {'id': 'p', 'gameId': 'CFB-1', 'athleteId': '7', 'market': 'recYds', 'direction': 'under'}
        self.assertEqual(self.build([self.row], picks=[open_play]), {}, 'an open best bet on either side')
        self.assertEqual(self.build([self.row], rules=dict(self.rules, dropped=['recYds'])), {}, 'a dropped stat')
        self.assertEqual(self.build([self.row], rules=dict(self.rules, clearsOnly=True)), {}, 'clears-only')

    def test_role_floors_from_stored_box_scores(self):
        self.logs['7'][-1]['stats'] = {'pbpTgt': 1}                 # 14 targets over three games: under five a game
        self.assertEqual(self.build([self.row]), {})
        self.logs['7'] = self.logs['7'][:2]
        self.assertEqual(self.build([self.row]), {}, 'fewer than three current-team games: unknown, so off')
        qb_row = {**self.row, 'athleteId': '9', 'stat': 'cmp', 'line': 16.5, 'player': 'Caden Creel'}
        starter = [log(f'g{i}', f'2026-09-{10 + i}T20:00Z', pos='QB', att=30) for i in range(3)]
        backup = [log('g2', '2026-09-12T20:00Z', pos='QB', att=40)]
        self.logs.update({'9': starter, '10': backup})
        self.assertEqual(len(self.build([qb_row])['CFB']['rows']), 1, 'the usual starter: top passer in 2 of 3')
        self.logs['10'] = [log('g1', '2026-09-11T20:00Z', pos='QB', att=40), log('g2', '2026-09-12T20:00Z', pos='QB', att=40)]
        self.assertEqual(self.build([qb_row]), {}, 'a backup who started two of three is the usual starter instead')

    def test_order_one_row_per_player_and_the_next_game_day(self):
        perfect = {**self.row, 'athleteId': '8', 'player': 'Maguire Anderson',
                   'history': [{'value': v} for v in (87, 98, 139, 58, 80)]}
        self.logs['8'] = self.logs['7']
        second_stat = {**self.row, 'stat': 'rec', 'line': 3.5, 'history': [{'value': v} for v in (5, 6, 4, 2, 7)]}
        rows = self.build([self.row, perfect, second_stat])['CFB']['rows']
        self.assertEqual([r['player'] for r in rows], ['Maguire Anderson', 'Tyson Carter'], 'hits/games, then one per player')
        saturday = {**self.row, 'kickoff': '2026-10-10T16:00Z'}
        out = self.build([saturday])
        self.assertEqual(out['CFB']['day'], '2026-10-10', 'no row today: the next game day that has one')

    def test_the_build_writes_prep_into_today_and_keeps_the_guard_narrow(self):
        import inspect
        body = inspect.getsource(build_site.build)
        self.assertIn("'prep': prep", body)
        self.assertIn('prep_list(trends, lines, picks, league_data, now)', body)
        self.assertFalse(publication_guard.allowed_path(Path('data/app/prep-top.json')), 'no new file family')


class RoleHoldFieldTests(unittest.TestCase):
    def test_guard_names_the_hold_and_quotes_the_real_recent_volumes(self):
        logs = [log(f'e{i}', f'2026-09-{10 + i}T20:00Z', pos='QB', att=a) for i, a in enumerate((50, 36, 43))]
        caution = role_sanity.assess({'att': [23.7]}, logs, '2229', 'passYds', 2026)
        self.assertEqual(caution['recentFull'], [50, 36, 43])
        game = {'id': 'CFB-1', 'league': 'CFB', 'kickoff': '2026-10-07T23:30Z', 'season': 2026,
                'home': {'id': '2229'}, 'away': {'id': '166'}}
        snapshot = {'publishedAt': '2026-10-06T00:00:00Z',
                    'players': {'home': {'players': [{'id': '4870883', 'pos': 'QB', 'att': [23.7]}]}, 'away': {'players': []}}}
        row = {'id': 'r', 'gameId': 'CFB-1', 'athleteId': '4870883', 'stat': 'passYds', 'state': 'open', 'odds': -114,
               'grade': {'chance': .55, 'calibrated': True}}
        league_data = {'CFB': {'player_logs': {'4870883': logs}}}
        build_site.guard_player_lines([row], {'CFB-1': game}, {'CFB-1': [snapshot]}, league_data, NOW, logger=lambda *_: None)
        self.assertEqual((row['roleHold'], row['recentFull'], row['recentVolume']), ('workload', [50, 36, 43], 'att'))
        self.assertIsNone(row['grade'])


if __name__ == '__main__':
    unittest.main()


class TeamPanelFixtureTests(unittest.TestCase):
    """tests/fixtures/team-panels.json is the table the browser's teamPanel() is checked against (Node test)."""

    def test_the_fixture_is_ticket_kit_team_panel_over_every_nfl_and_college_pair(self):
        import ticket_kit
        fixture = json.loads((ROOT / 'tests/fixtures/team-panels.json').read_text(encoding='utf-8'))
        norm = lambda c: ('#' + str(c).strip().lower().lstrip('#')) if c and len(str(c).strip().lstrip('#')) == 6 else ''
        college = json.loads((ROOT / 'data/team-colors-cfb.json').read_text(encoding='utf-8'))['teams']
        wanted = {f"{norm(t.get('color'))}|{norm(t.get('alternateColor'))}" for t in college.values()}
        wanted |= {f'{norm(c)}|{norm(a)}' for c, a in fixture['nfl'].values()}
        self.assertEqual(len(fixture['nfl']), 32)
        self.assertLessEqual(wanted, set(fixture['panels']), 'every stored NFL and college colour pair is covered')
        for key, panel in fixture['panels'].items():
            primary, alternate = key.split('|')
            self.assertEqual(list(ticket_kit.team_panel(primary or None, alternate or None)), panel, key)


class HitStripTests(unittest.TestCase):
    def test_the_strip_is_this_seasons_last_five_before_kickoff_with_both_counts(self):
        game = {'season': 2026, 'kickoff': '2026-10-07T23:30Z'}
        logs = [log('old', '2025-11-01T20:00Z', recYds=80), log('old2', '2025-11-08T20:00Z', recYds=10)]
        logs[0]['season'] = logs[1]['season'] = 2025
        logs += [log(f'e{i}', f'2026-09-0{i + 1}T20:00Z', recYds=v) for i, v in enumerate((12, 78, 94, 67, 26, 21))]
        logs.append(log('later', '2026-10-08T20:00Z', recYds=200))
        strip = build_site.hit_strip({'market': 'recYds', 'line': 49.5, 'direction': 'over', 'kickoff': game['kickoff']}, game, logs)
        self.assertEqual(strip, {'v': [78, 94, 67, 26, 21], 'season': [3, 6], 'last10': [4, 8]})
        self.assertIsNone(build_site.hit_strip({'market': 'recYds', 'line': None, 'direction': 'over'}, game, logs))
        self.assertIsNone(build_site.hit_strip({'market': 'recYds', 'line': 49.5, 'direction': 'over',
                                                'kickoff': game['kickoff']}, {'season': 2027}, logs))
