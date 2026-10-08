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
        against = {**KING, 'reasoning': {'context': labeled['reasoning']['context'], 'cautions': KING['reasoning']['cautions']}}
        self.assertIsNone(build_site.ticket_why(against),
                          'a Defense line the saved caution says points against the side is never the WHY')
        later = {**KING, 'reasoning': {'context': ['', 'Defense: FIU allows 133 receiving yards a game to WRs.'],
                                       'cautions': ['FIU is allowing 14.5 points per game.']}}
        self.assertEqual(build_site.ticket_why(later), 'FIU allows 133 receiving yards a game to WRs.',
                         'blank context lines are skipped; the first real one is context[0]')
        for empty in ({'reasoning': {}}, {'reason': '  ', 'reasoning': {'context': []}}, {}):
            self.assertIsNone(build_site.ticket_why(empty))

    def test_free_text_is_verbatim_never_cut_into_a_clause(self):
        """Decision 8: free text is printed as saved; only the named templates are reworded."""
        cases = ['Bowling Green cornerback JoJo Johnson, who had 13 pass breakups last season, missed the Iowa State '
                 'game due to injury.',
                 'Bills defensive lineman Ed Oliver left the Patriots game with a knee injury, and cornerback Dee '
                 'Alford left with an ankle injury.',
                 'Arizona and West Virginia both rank in the bottom third in plays per minute; the forecast has '
                 'both offenses under their season scoring averages.']
        for text in cases:
            self.assertEqual(build_site.ticket_why({'reason': text}), text, 'the saved reason, word for word')
            self.assertEqual(build_site.ticket_but({'reasoning': {'cautions': [text]}}), text)
        self.assertEqual(build_site.ticket_why({'reason': '  Two   spaces\nand a break.  '}), 'Two spaces and a break.',
                         'only whitespace is normalized')
        self.assertEqual(build_site.ticket_why({'reason': 'x' * 300}), 'x' * 300, 'length never drops the saved reason')

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
        self.assertEqual(build_site.ticket_but(stat), 'Arizona converted 57.8% of third downs. More text.',
                         'a label prefix comes off; the free text after it stays whole')
        self.assertIsNone(build_site.ticket_but({'risk': 'Only prose, no saved counterpoint.'}),
                          'BUT never falls back to the risk paragraph')

    def test_a_why_that_quotes_a_last_n_count_drops_the_strips_own_last_ten(self):
        """Tuten (NFL-2026-W4-tuten-under-1-5-rec-dk): WHY "Under 1.5 in 8 of his last 10 games." sat over a strip of
        "7 of his last 10", because the desk counts a no-catch game as zero and the site's stored log leaves it blank."""
        game = {'id': 'NFL-1', 'league': 'NFL', 'kickoff': '2026-10-04T17:00Z', 'season': 2026,
                'away': {'id': '30', 'abbreviation': 'JAX'}, 'home': {'id': '11', 'abbreviation': 'IND'}}
        logs = [log(f'e{i}', f'2026-09-{10 + 7 * i}T17:00Z', team='30', pos='RB', rec=v) for i, v in enumerate((1, 2, 2))]
        tuten = {'id': 'NFL-2026-W4-tuten-under-1-5-rec-dk', 'gameId': 'NFL-1', 'athleteId': '4882093', 'market': 'rec',
                 'direction': 'under', 'line': 1.5, 'kickoff': game['kickoff'], 'reason': 'Under 1.5 in 8 of his last 10 games.'}
        plain = {**tuten, 'id': 'x', 'reason': None, 'reasoning': {'context': ['Role: projected for 9.0 carries a game.']}}
        build_site.annotate_tickets([tuten, plain], {'NFL-1': game}, {}, {'NFL': {'player_logs': {'4882093': logs}}}, {})
        self.assertEqual(tuten['ticketWhy'], 'Under 1.5 in 8 of his last 10 games.')
        self.assertNotIn('last10', tuten['hitStrip'], 'one count on the ticket, the desk\'s own')
        self.assertEqual(tuten['hitStrip']['season'], [1, 3])
        self.assertIn('last10', plain['hitStrip'], 'without a quoted count the strip keeps its last-ten line')

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
        hero = build_site.today_hero([pick], NOW, teams={KING['gameId']: TEAMS})
        bet = hero['bets'][0]
        for key in ('side', 'ticketWhy', 'ticketBut', 'gameId'):
            self.assertEqual(bet[key], pick[key], key)
        self.assertEqual(bet['teams'], TEAMS)
        self.assertNotIn('deskRuns', hero, 'internal release times never enter a public payload')
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
        self.logs['9'] = [log(f'g{i}', f'2026-09-{10 + i}T20:00Z', pos='QB', att=30) for i in range(3)]
        game = lambda i, passers: {'eventId': f'g{i}', 'kickoff': f'2026-09-{10 + i}T20:00Z', 'home': {'id': '2229'},
                                   'away': {'id': '99'}, 'players': [{'id': pid, 'team': '2229', 'att': att} for pid, att in passers]}
        records = [game(0, [('9', 30)]), game(1, [('9', 30), ('10', 2)]), game(2, [('10', 40), ('9', 12)]), game(3, [('9', 31)])]
        self.league['CFB']['records'] = records
        self.assertEqual(len(self.build([qb_row])['CFB']['rows']), 1, 'the usual starter: modal top passer, last four games')
        self.league['CFB']['records'] = records[:3] + [game(3, [('10', 33)]), game(4, [('10', 35)])]
        self.assertEqual(self.build([qb_row]), {}, 'a backup who started the most of the last four is the usual starter')
        self.league['CFB']['records'] = []
        self.assertEqual(self.build([qb_row]), {}, 'no stored games: unknown, so off')
        import starters
        self.assertEqual(starters.RECENT, 4, "starters.py's own window decides the usual starter")

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

    def test_the_next_game_day_rides_along_so_the_site_can_roll_forward(self):
        thursday = {**self.row, 'athleteId': '8', 'player': 'Makai Jackson', 'gameId': 'CFB-2', 'kickoff': '2026-10-08T23:30Z'}
        friday = {**self.row, 'athleteId': '9', 'player': 'Friday Guy', 'gameId': 'CFB-3', 'kickoff': '2026-10-09T23:30Z'}
        self.logs['8'] = self.logs['9'] = self.logs['7']
        out = self.build([self.row, thursday, friday])['CFB']
        self.assertEqual((out['day'], [r['player'] for r in out['rows']]), ('2026-10-07', ['Tyson Carter']))
        self.assertEqual((out['next']['day'], [r['player'] for r in out['next']['rows']]), ('2026-10-08', ['Makai Jackson']),
                         'only the game day after the first rides along')
        held = {**thursday, 'roleSuspect': True}
        self.assertNotIn('next', self.build([self.row, held])['CFB'], 'the next day keeps every rule and hold')
        twice = {**thursday, 'stat': 'rec', 'line': 3.5, 'history': [{'value': v} for v in (5, 6, 4, 2, 7)]}
        self.assertEqual(len(self.build([self.row, thursday, twice])['CFB']['next']['rows']), 1, 'one row per player on the next day too')
        self.assertNotIn('next', self.build([self.row])['CFB'], 'one game day: no next block')

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

    def test_last_ten_counts_the_playoffs_like_the_desk_and_never_preseason(self):
        game = {'season': 2026, 'kickoff': '2026-10-07T23:30Z'}
        old = [log(f'o{i}', f'2025-1{i // 5}-{10 + i % 5}T20:00Z', rec=v) for i, v in enumerate((0, 1, 0, 0, 1, 0))]
        for row in old:
            row['season'] = 2025
        wild_card = {**log('wc', '2026-01-11T20:00Z', rec=0), 'season': 2025, 'seasonType': 3}
        preseason = {**log('pre', '2026-08-20T20:00Z', rec=5), 'seasonType': 1}
        logs = old + [wild_card, preseason] + [log(f'e{i}', f'2026-09-0{i + 1}T20:00Z', rec=v) for i, v in enumerate((1, 0, 3, 0))]
        strip = build_site.hit_strip({'market': 'rec', 'line': 1.5, 'direction': 'under', 'kickoff': game['kickoff']}, game, logs)
        self.assertEqual(strip['v'], [1, 0, 3, 0], 'the bars are this regular season only')
        self.assertEqual(strip['season'], [3, 4])
        self.assertEqual(strip['last10'], [9, 10], 'the wild-card game counts in the last ten; the preseason game never does')
        reason_style = [r['stats']['rec'] for r in sorted((r for r in logs if r['seasonType'] != 1), key=lambda r: r['kickoff'])[-10:]]
        self.assertEqual(strip['last10'][0], sum(v < 1.5 for v in reason_style))


class TicketQuoteAndHoldTests(unittest.TestCase):
    """The A-22/A-23 hold on a published play's market, and the one quote every page shows (decision 9)."""
    def setUp(self):
        self.pick = {'id': 'k', 'league': 'CFB', 'gameId': 'CFB-401871066', 'athleteId': '4869443', 'market': 'recYds',
                     'direction': 'over', 'line': 49.5, 'odds': -102, 'book': 'DraftKings', 'kickoff': '2026-10-07T23:30Z'}
        self.row = {'gameId': 'CFB-401871066', 'athleteId': '4869443', 'stat': 'recYds', 'market': 'receiving yards',
                    'direction': 'over', 'line': 49.5, 'odds': -104, 'book': 'DraftKings', 'state': 'open',
                    'observedAt': '2026-10-07T17:37:35Z'}

    def run_(self, rows, pick=None):
        pick = dict(pick or self.pick)
        build_site.annotate_quotes([pick], rows, {}, NOW)
        return pick

    def test_a_clean_market_gets_the_latest_fresh_same_book_quote(self):
        older = {**self.row, 'odds': -110, 'observedAt': '2026-10-07T15:00:00Z'}
        other_book = {**self.row, 'book': 'FanDuel', 'odds': 100}
        out = self.run_([older, self.row, other_book])
        self.assertEqual(out['quote'], {'odds': -104, 'line': 49.5, 'observedAt': '2026-10-07T17:37:35Z'})
        self.assertNotIn('held', out)
        self.assertNotIn('quote', self.run_([{**self.row, 'observedAt': '2026-10-07T13:00:00Z'}]), 'older than four hours')
        self.assertNotIn('quote', self.run_([{**self.row, 'state': 'stale'}]))
        self.assertNotIn('quote', self.run_([{**self.row, 'direction': 'under'}]), 'the other side is never the quote')
        self.assertNotIn('quote', self.run_([self.row], {**self.pick, 'result': 'win'}), 'settled plays carry none')

    def test_tk_king_a_qb_hold_with_a_failed_price_holds_the_play_and_drops_its_quote(self):
        held = {**self.row, 'roleSuspect': True, 'priceSuspect': True, 'roleHold': 'qb', 'grade': None,
                'gradeNote': 'Projection and price under review'}
        out = self.run_([held])
        self.assertEqual(out['held'], {'kind': 'qb'})
        self.assertNotIn('quote', out, 'a held row can never say "Still good to"')

    def test_a_hold_after_delivery_keeps_the_posted_reason_and_historical_chance(self):
        held = {**self.row, 'roleSuspect': True, 'roleHold': 'qb', 'grade': None}
        pick = {**self.pick, 'delivery': {'discordAt': '2026-10-07T16:00:00Z'},
                'ticketWhy': 'I projected 7.3 targets when I posted.',
                'ticketBut': 'His role could shrink.'}
        out = self.run_([held], pick)
        self.assertEqual(out['held'], {'kind': 'qb', 'afterPosting': True})
        self.assertEqual(out['ticketWhy'], pick['ticketWhy'], 'the posted WHY must not be rewritten')
        self.assertEqual(out['ticketBut'], pick['ticketBut'])
        self.assertEqual(out['quote']['odds'], -104, 'a same-book price remains a fact, not an endorsement')

    def test_any_book_either_side_or_a_sibling_volume_market_holds_it(self):
        self.assertEqual(self.run_([self.row, {**self.row, 'book': 'FanDuel', 'priceSuspect': True}])['held'], {'kind': 'price'})
        self.assertEqual(self.run_([self.row, {**self.row, 'direction': 'under', 'roleSuspect': True}])['held'], {'kind': 'role'})
        sibling = {**self.row, 'stat': 'rec', 'market': 'receptions', 'line': 3.5, 'roleSuspect': True, 'roleHold': 'workload',
                   'recentFull': [9, 7, 8], 'recentVolume': 'targets'}
        self.assertEqual(self.run_([self.row, sibling])['held'], {'kind': 'workload', 'recentFull': [9, 7, 8], 'volume': 'targets'},
                         'targets drive both receiving markets, as the player page marks them')
        price_only_sibling = {**sibling, 'roleSuspect': None, 'roleHold': None, 'priceSuspect': True}
        self.assertNotIn('held', self.run_([self.row, price_only_sibling]), "another market's price check is its own")
        other_player = {**self.row, 'athleteId': '1', 'roleSuspect': True}
        self.assertNotIn('held', self.run_([self.row, other_player]))

    def test_game_lines_get_their_quote_by_side(self):
        total = {'id': 't', 'gameId': 'NFL-1', 'marketType': 'total', 'direction': 'under', 'line': 54.5, 'odds': -102,
                 'book': 'DraftKings', 'kickoff': '2026-10-13T00:15Z'}
        rows = [{'gameId': 'NFL-1', 'market': 'total points', 'direction': 'over', 'line': 54.5, 'odds': -118, 'book': 'DraftKings',
                 'state': 'open', 'observedAt': '2026-10-07T16:00:00Z'},
                {'gameId': 'NFL-1', 'market': 'total points', 'direction': 'under', 'line': 54.5, 'odds': -105, 'book': 'DraftKings',
                 'state': 'open', 'observedAt': '2026-10-07T16:00:00Z'}]
        self.assertEqual(self.run_(rows, total)['quote']['odds'], -105)
        spread = {**total, 'id': 's', 'marketType': 'spread', 'direction': 'home', 'line': -3}
        game = {'NFL-1': {'home': {'abbreviation': 'LAR'}, 'away': {'abbreviation': 'BUF'}}}
        spreads = [{'gameId': 'NFL-1', 'market': 'point spread', 'title': 'BUF +3', 'line': 3, 'odds': -110, 'book': 'DraftKings',
                    'state': 'open', 'observedAt': '2026-10-07T16:00:00Z'},
                   {'gameId': 'NFL-1', 'market': 'point spread', 'title': 'LAR -3', 'line': -3, 'odds': -108, 'book': 'DraftKings',
                    'state': 'open', 'observedAt': '2026-10-07T16:00:00Z'}]
        out = dict(spread)
        build_site.annotate_quotes([out], spreads, game, NOW)
        self.assertEqual(out['quote']['odds'], -108, 'a spread row without a side is matched by its team, as the browser does')

    def test_a_held_play_never_quotes_the_projection_the_hold_questions(self):
        """Decision 9: TK King's QB-change hold read Under review while WHY still said 'I project 7.3 targets'."""
        held = {**self.row, 'roleSuspect': True, 'priceSuspect': True, 'roleHold': 'qb'}
        king = {**self.pick, **{k: KING[k] for k in ('reason', 'reasoning', 'position', 'side')},
                'ticketWhy': build_site.ticket_why(KING), 'ticketBut': "FIU's WR defense points against the over."}
        self.assertEqual(king['ticketWhy'], "I project 7.3 targets, NMSU's top WR.")
        out = self.run_([held], king)
        self.assertEqual(out['held'], {'kind': 'qb'})
        self.assertIsNone(out['ticketWhy'], 'the first saved line is the projection under review: the row is left off, '
                          'never replaced by a later line (here the Defense line the BUT says points against the over)')
        self.assertIsNone(build_site.ticket_why(KING, held=True))
        self.assertEqual(out['ticketBut'], "FIU's WR defense points against the over.", 'a counterpoint without a projection stays')
        only_role = {**king, 'reasoning': {'context': [KING['reasoning']['context'][0], 'Usage: our model has him at 62% of snaps.'],
                                           'cautions': []},
                     'ticketBut': 'I project him under 5 targets if the backup starts.'}
        out = self.run_([held], only_role)
        self.assertIsNone(out['ticketWhy'], 'no saved line without a projection: the row is left off')
        self.assertIsNone(out['ticketBut'], 'a projection counterpoint is dropped too')
        reasoned = {**king, 'reason': 'I project 81 yards.', 'ticketWhy': 'I project 81 yards.'}
        self.assertIsNone(self.run_([held], reasoned)['ticketWhy'], 'a saved reason with a projection is left off too')
        safe = {**king, 'reason': 'Over 3.5 in 9 of his last 10 games.', 'ticketWhy': 'Over 3.5 in 9 of his last 10 games.'}
        self.assertEqual(self.run_([held], safe)['ticketWhy'], 'Over 3.5 in 9 of his last 10 games.',
                         'a held play keeps a saved reason that quotes no projection')
        clean = self.run_([self.row], king)
        self.assertEqual(clean['ticketWhy'], "I project 7.3 targets, NMSU's top WR.", 'an unheld play keeps its saved WHY')
        for text in ("I project 7.3 targets, NMSU's top WR.", 'Our chance is 56%.', 'Role: projected for 14.2 carries a game.'):
            self.assertTrue(build_site.held_text(text), text)
        self.assertFalse(build_site.held_text('Over 3.5 in 9 of his last 10 games.'))

    def test_the_build_writes_held_words_before_today_and_the_hero(self):
        import inspect
        self.assertIn('held_words(pick)', inspect.getsource(build_site.annotate_quotes))

    def test_the_hero_carries_the_same_quote_and_hold(self):
        pick = {**self.pick, 'status': 'active', 'displayTitle': 'TK King OVER 49.5 receiving yards', 'held': {'kind': 'qb'}}
        bet = build_site.today_hero([pick], NOW)['bets'][0]
        self.assertEqual(bet['held'], {'kind': 'qb'})
        clean = {**self.pick, 'status': 'active', 'quote': {'odds': -104, 'line': 49.5, 'observedAt': '2026-10-07T17:37:35Z'}}
        self.assertEqual(build_site.today_hero([clean], NOW)['bets'][0]['quote'], clean['quote'])

    def test_the_build_annotates_before_writing_today_and_the_record(self):
        import inspect
        body = inspect.getsource(build_site.build)
        self.assertLess(body.index('annotate_quotes(picks, lines, by_id, now)'), body.index("write(OUT / 'today.json'"))
