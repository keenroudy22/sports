import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sharp_odds


NOW = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)


def game(gid, kickoff, home, away, league='NFL'):
    return {'id': gid, 'league': league, 'season': 2026, 'state': 'pre', 'kickoff': kickoff,
            'home': {'name': home, 'abbreviation': home[:3].upper()}, 'away': {'name': away, 'abbreviation': away[:3].upper()}}


def row(book, market, player, side, line, price, home='LV Raiders', away='LAC Chargers', start='2026-09-20T20:05:00Z', **extra):
    return {'sportsbook': book, 'market_type': market, 'player_name': player, 'selection': side.title(), 'selection_type': side,
            'line': line, 'odds_american': price, 'home_team': home, 'away_team': away, 'event_start_time': start,
            'is_main_line': not extra.get('is_alternate_line', False), 'is_player_prop': True, **extra}


class MappingTests(unittest.TestCase):
    def test_market_types_map_to_the_desk_keys(self):
        cases = {'player_passing_yards': 'passYds', 'player_pass_yds': 'passYds', 'player_rushing_yards': 'rushYds',
                 'player_receiving_yards': 'recYds', 'player_receptions': 'rec', 'player_rush_attempts': 'car',
                 'player_pass_attempts': 'att', 'player_pass_completions': 'cmp', 'player_longest_reception': None,
                 'player_anytime_td': None, 'total_points': None}
        for market, key in cases.items():
            self.assertEqual(sharp_odds.market_key(market), key, market)

    def test_college_teams_named_by_school_alone_find_their_game(self):
        games = [dict(game('CFB-1', '2026-09-26T19:30Z', 'Georgia Bulldogs', 'Oklahoma Sooners', 'CFB'),
                      home={'name': 'Georgia Bulldogs', 'school': 'Georgia'}, away={'name': 'Oklahoma Sooners', 'school': 'Oklahoma'}),
                 dict(game('CFB-2', '2026-09-26T19:00Z', 'Wyoming Cowboys', "Hawai'i Rainbow Warriors", 'CFB'),
                      home={'name': 'Wyoming Cowboys', 'school': 'Wyoming'}, away={'name': "Hawai'i Rainbow Warriors", 'school': "Hawai'i"}),
                 dict(game('CFB-3', '2026-09-26T19:30Z', 'Iowa State Cyclones', 'Oklahoma State Cowboys', 'CFB'),
                      home={'name': 'Iowa State Cyclones', 'school': 'Iowa State'}, away={'name': 'Oklahoma State Cowboys', 'school': 'Oklahoma State'})]
        row = lambda away, home: {'away_team': away, 'home_team': home, 'event_start_time': '2026-09-26T19:30:00Z'}
        self.assertEqual(sharp_odds.find_game(row('Oklahoma', 'Georgia'), games)['id'], 'CFB-1')
        self.assertEqual(sharp_odds.find_game(row('Hawaii', 'Wyoming'), games)['id'], 'CFB-2')
        self.assertIsNone(sharp_odds.find_game(row('Oklahoma', 'Iowa State'), games), 'Oklahoma is not Oklahoma State')

    def test_combined_and_longest_markets_are_not_the_plain_stat(self):
        for market in ('player_passing_+_rushing_yards', 'player_rushing_+_receiving_yards', 'player_longest_passing_completion',
                       'player_longest_rush', 'player_rush_and_receiving_yards'):
            self.assertIsNone(sharp_odds.market_key(market), market)

    def test_team_spellings_match_across_the_two_feeds(self):
        self.assertTrue(sharp_odds.same_team('Las Vegas Raiders', 'LV Raiders'))
        self.assertTrue(sharp_odds.same_team('Los Angeles Chargers', 'LA Chargers'))
        self.assertTrue(sharp_odds.same_team('Texas A&M Aggies', 'Texas A&M Aggies'))
        self.assertTrue(sharp_odds.same_team('Southern Miss Golden Eagles', 'Southern Mississippi Golden Eagles'))
        self.assertFalse(sharp_odds.same_team('Michigan Wolverines', 'Michigan State Spartans'))
        self.assertFalse(sharp_odds.same_team('New York Giants', 'New York Jets'))


class QuoteTests(unittest.TestCase):
    slate = [game('NFL-1', '2026-09-20T20:05Z', 'Los Angeles Chargers', 'Las Vegas Raiders')]

    def rows(self):
        g = self.slate[0]
        return [(g, row('draftkings', 'player_rushing_yards', 'Ashton Jeanty', 'over', 66.5, -115)),
                (g, row('draftkings', 'player_rushing_yards', 'Ashton Jeanty', 'under', 66.5, -105)),
                (g, row('draftkings', 'player_rushing_yards', 'Ashton Jeanty', 'over', 80.5, 180, is_alternate_line=True)),
                (g, row('fanduel', 'player_rushing_yards', 'Ashton Jeanty', 'over', 65.5, -112)),
                (g, row('fanduel', 'player_anytime_td', 'Ashton Jeanty', 'yes', None, 150)),
                (g, row('fanduel', 'player_receptions', 'Ladd McConkey', 'over', 4.5, -118, is_alternate_line=True))]

    def test_main_lines_and_alternates_are_kept_apart_and_the_rest_dropped(self):
        quotes = sharp_odds.quotes_from(self.rows())
        dk = quotes['NFL-1']['draftkings']['rushYds']['Ashton Jeanty']
        self.assertEqual((dk['line'], dk['over'], dk['under']), (66.5, -115, -105))
        self.assertEqual(dk['alternates'], [{'line': 80.5, 'over': 180}])
        self.assertEqual(quotes['NFL-1']['fanduel']['rushYds']['Ashton Jeanty'], {'line': 65.5, 'over': -112}, 'a one-sided flagged main stands')
        self.assertNotIn('rec', quotes['NFL-1']['fanduel'], 'an alternate with no main number is not a quote')

    def test_the_main_number_is_the_two_sided_rung_nearest_even_money_whatever_the_flag_says(self):
        g = self.slate[0]
        rows = [(g, row('draftkings', 'player_receiving_yards', 'Tre Tucker', 'over', 14.5, 235)),
                (g, row('draftkings', 'player_receiving_yards', 'Tre Tucker', 'over', 35.5, -110, is_alternate_line=True)),
                (g, row('draftkings', 'player_receiving_yards', 'Tre Tucker', 'under', 35.5, -114, is_alternate_line=True)),
                (g, row('draftkings', 'player_receiving_yards', 'Tre Tucker', 'over', 49.5, 300, is_alternate_line=True))]
        q = sharp_odds.quotes_from(rows)['NFL-1']['draftkings']['recYds']['Tre Tucker']
        self.assertEqual((q['line'], q['over'], q['under']), (35.5, -110, -114))
        self.assertEqual([a['line'] for a in q['alternates']], [49.5], 'the +235 rung below the main line is out of order: another market')

    def test_a_period_ladder_filed_under_the_full_game_market_is_dropped(self):
        # DraftKings' Mahomes passing yards on 2026-09-26: rungs from 14.5 to 49.5 and 69.5 to 139.5 beside a 222.5 main.
        quote = {'line': 222.5, 'over': -113, 'under': -111, 'alternates': [
            {'line': 14.5, 'over': -205}, {'line': 19.5, 'over': -125}, {'line': 49.5, 'over': 1300}, {'line': 69.5, 'over': -215},
            {'line': 139.5, 'over': 1300}, {'line': 199.5, 'over': -200}, {'line': 174.5, 'over': -390}, {'line': 249.5, 'over': 172},
            {'line': 274.5, 'over': 290}, {'line': 244.5, 'over': -111}]}
        self.assertEqual([a['line'] for a in sharp_odds.consistent(quote)], [174.5, 199.5, 244.5, 249.5, 274.5],
                         'down from the main line the over only gets shorter, up from it only longer; the first rung out of order ends the walk')
        self.assertEqual(sharp_odds.consistent({'line': None, 'alternates': quote['alternates']}), [])

    def test_the_event_list_asks_for_upcoming_games_at_the_two_books(self):
        seen = {}

        def fetch(path, key, **params):
            seen.update(params, path=path)
            return {'data': [{'id': 'e1'}]}
        self.assertEqual(sharp_odds.events('nfl', 'k', fetch=fetch), [{'id': 'e1'}])
        self.assertEqual((seen['path'], seen['league'], seen['sportsbook'], seen['status']), ('/events', 'nfl', 'draftkings,fanduel', 'upcoming'))

    def test_a_completions_line_above_the_attempts_line_is_not_a_quote(self):
        g = self.slate[0]
        rows = [(g, row('draftkings', 'player_pass_attempts', 'Jaxson Dart', 'over', 31.5, -104)),
                (g, row('draftkings', 'player_pass_attempts', 'Jaxson Dart', 'under', 31.5, -122)),
                (g, row('draftkings', 'player_pass_completions', 'Jaxson Dart', 'over', 34.5, -114)),
                (g, row('draftkings', 'player_pass_completions', 'Jaxson Dart', 'under', 34.5, -113)),
                (g, row('draftkings', 'player_pass_completions', 'Jaxson Dart', 'over', 19.5, -120, is_alternate_line=True))]
        book = sharp_odds.quotes_from(rows)['NFL-1']['draftkings']
        self.assertEqual(book['cmp']['Jaxson Dart']['line'], 19.5, 'the rung below attempts becomes the number')
        self.assertIn(34.5, [a['line'] for a in book['cmp']['Jaxson Dart']['alternates']])
        without = [r for r in rows if r[1].get('line') != 19.5]
        self.assertNotIn('cmp', sharp_odds.quotes_from(without)['NFL-1']['draftkings'], 'no plausible rung means no completions quote')

    def test_the_slate_game_is_found_from_either_orientation(self):
        g = self.slate[0]
        self.assertIs(sharp_odds.find_game(row('draftkings', 'x', 'p', 'over', 1, -110), self.slate), g)
        flipped = row('draftkings', 'x', 'p', 'over', 1, -110, home='LAC Chargers', away='LV Raiders')
        self.assertIs(sharp_odds.find_game(flipped, self.slate), g)
        elsewhere = row('draftkings', 'x', 'p', 'over', 1, -110, start='2026-09-21T20:05:00Z')
        self.assertIsNone(sharp_odds.find_game(elsewhere, self.slate), 'a kickoff a day off is another game')

    def test_a_capture_merges_over_the_other_feeds_books_and_writes_once(self):
        g = self.slate[0]
        calls = []

        def fetch(path, key, **params):
            calls.append((path, params.get('event_id'), params.get('cursor')))
            if path == '/events':
                return {'data': [{'id': 'ev1', 'home_team': 'LAC Chargers', 'away_team': 'LV Raiders', 'event_start_time': '2026-09-20T20:05:00Z'}]}
            return {'data': [r for _, r in self.rows()], 'pagination': {'has_more': False}}

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            earlier = {'league': 'NFL', 'gameId': 'NFL-1', 'season': 2026, 'kickoff': g['kickoff'], 'retrievedAt': '2026-09-20T12:00:00Z',
                       'source': 'x', 'books': {'betmgm': {'title': 'BetMGM', 'markets': {'rushYds': {'Ashton Jeanty': {'line': 66.5, 'over': -110, 'under': -110}}}},
                                                'draftkings': {'title': 'DraftKings', 'markets': {'rushYds': {'Ashton Jeanty': {'line': 64.5, 'over': -110}}}}}}
            earlier['hash'] = sharp_odds.boxscores.content_hash(earlier)
            sharp_odds.boxscores.append(root / 'nfl-2026.jsonl', [earlier])
            n = sharp_odds.capture({'games': self.slate}, NOW, 'secret', fetch=fetch, sleep=lambda s: None, root=root, log=lambda *a: None)
            self.assertEqual(n, 1)
            self.assertIn(('/odds', 'ev1', None), calls, 'props are requested one game at a time by event id')
            status = json.loads((root / 'sharp-status.json').read_text(encoding='utf-8'))
            self.assertEqual(status['leagues']['NFL']['eventsMatched'], 1)
            self.assertNotIn('secret', json.dumps(status))
            stored = [json.loads(l) for l in (root / 'nfl-2026.jsonl').read_text(encoding='utf-8').splitlines()]
            books = stored[-1]['books']
            self.assertEqual(sorted(books), ['betmgm', 'draftkings', 'fanduel'], 'BetMGM from the other feed rides along')
            self.assertEqual(books['draftkings']['markets']['rushYds']['Ashton Jeanty']['line'], 66.5, 'this feed replaces its own book')
            self.assertNotIn('secret', (root / 'nfl-2026.jsonl').read_text(encoding='utf-8'))
            n = sharp_odds.capture({'games': self.slate}, NOW, 'secret', fetch=fetch, sleep=lambda s: None, root=root, log=lambda *a: None)
            self.assertEqual(n, 0, 'unchanged numbers are not appended again')


if __name__ == '__main__':
    unittest.main()
