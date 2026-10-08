"""College slate navigator and game explanations (owner, 2026-10-07, items 28 and 30): wording, both markets, numbers."""

import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import game_context

NOW = datetime(2026, 10, 7, 20, tzinfo=timezone.utc)
BANNED = re.compile(r'\b(desk|scan|scans|automated|pipeline|calibration|model weights)\b', re.I)
GAME = {'id': 'CFB-1', 'league': 'CFB', 'state': 'pre', 'kickoff': '2026-10-10T16:00:00Z',
        'home': {'id': '2229'}, 'away': {'id': '2'}}
CARD = {'id': 'CFB-1', 'home': {'id': '2229', 'name': 'FIU', 'abbr': 'FIU', 'strength': {'offense': 9, 'defense': 22, 'teams': 136}},
        'away': {'id': '2', 'name': 'Auburn', 'abbr': 'AUB', 'strength': {'offense': 84, 'defense': 102, 'teams': 136}},
        'market': {'spread': -4, 'total': 53.5, 'spreadOpen': -3, 'totalOpen': 52.5, 'book': 'DraftKings',
                   'retrievedAt': '2026-10-07T19:30:00Z'},
        'v2': {'margin': 14.6, 'total': 50.5}}


def every_text(block):
    out = []
    if not block:
        return out
    out.append(block.get('text') or '')
    for d in block.get('drivers') or []:
        out.append(d['text'])
    for m in (block.get('markets') or {}).values():
        for d in (m or {}).get('drivers') or []:
            out.append(d['text'])
    return out


class PlainGapTests(unittest.TestCase):
    def test_blowout_lean_and_even_wordings(self):
        blow = {**CARD, 'market': {**CARD['market'], 'spread': -28}, 'v2': {'margin': 24, 'total': 55}}
        nav = game_context.navigator(GAME, blow, [], [], NOW, conferences={})
        self.assertEqual(nav['plainGap'], 'FIU is 24 points better by my numbers and the book has them by 28. Starters may sit early.')
        self.assertEqual(nav['tier'], 'blowout')
        self.assertTrue(nav['garbageTime'])
        disagree = {**CARD, 'market': {**CARD['market'], 'spread': 3}, 'v2': {'margin': 5, 'total': 55}}
        nav = game_context.navigator(GAME, disagree, [], [], NOW, conferences={})
        self.assertEqual(nav['plainGap'], 'FIU is 5 points better by my numbers but the book has Auburn by 3.')
        even = {**CARD, 'market': {**CARD['market'], 'spread': -3}, 'v2': {'margin': 2, 'total': 55}}
        nav = game_context.navigator(GAME, even, [], [], NOW, conferences={})
        self.assertEqual(nav['plainGap'], 'Even matchup by my numbers (gap 2) and the book is close (3): sides and totals are live here.')
        self.assertNotIn('Starters may sit early', nav['plainGap'])
        for text in (nav['plainGap'], nav['look']):
            self.assertIsNone(BANNED.search(text or ''), text)

    def test_look_line_follows_the_checked_parts(self):
        nav = game_context.navigator(GAME, CARD, [], [], NOW, conferences={})
        self.assertEqual(nav['look'], 'AUB +4 vs my +14.6', 'the larger gap leads: 10.6 on the spread beats 3 on the total')
        bigger_total = {**CARD, 'v2': {'margin': 14.6, 'total': 41.5}}
        self.assertEqual(game_context.navigator(GAME, bigger_total, [], [], NOW, conferences={})['look'], 'Total 53.5 vs my 41.5')
        only_spread = {**CARD, 'v2': {'margin': 14.6, 'total': 53}}
        self.assertEqual(game_context.navigator(GAME, only_spread, [], [], NOW, conferences={})['look'], 'AUB +4 vs my +14.6')
        fcs = {**only_spread, 'fcs': True}
        nav = game_context.navigator(GAME, fcs, [], [], NOW, conferences={})
        self.assertEqual(nav['look'], 'Even matchup', 'an FBS-vs-FCS game never cites my number')
        self.assertEqual(nav['bettable'], game_context.navigator(GAME, {**fcs, 'v2': {'margin': 4, 'total': 53}}, [], [], NOW, conferences={})['bettable'],
                         'my number against the book adds nothing to the FCS score')
        official = game_context.navigator(GAME, CARD, [], [{'gameId': 'CFB-1', 'publishedAt': '2026-10-07T12:00Z'}], NOW, conferences={})
        self.assertEqual(official['look'], 'Best bet posted')
        even = {**CARD, 'market': {**CARD['market'], 'spread': -3}, 'v2': {'margin': 2, 'total': 53}}
        self.assertEqual(game_context.navigator(GAME, even, [], [], NOW, conferences={})['look'], 'Even matchup')
        blow = {**CARD, 'market': {**CARD['market'], 'spread': -28, 'total': 55}, 'v2': {'margin': 27, 'total': 55}}
        self.assertEqual(game_context.navigator(GAME, blow, [], [], NOW, conferences={})['look'], 'Props carry garbage-time risk')
        self.assertIsNone(game_context.navigator({**GAME, 'state': 'post'}, CARD, [], [], NOW, conferences={})['look'])

    def test_dog_line_keeps_the_book_convention_for_home_and_away_dogs(self):
        # Away dog I also have losing: WYO at SJSU, book SJSU -6, my SJSU by 9.5.
        away = {'home': {'abbr': 'SJSU'}, 'away': {'abbr': 'WYO'}}
        self.assertEqual(game_context.dog_line(away, -6, 9.5), 'WYO +6 vs my +9.5')
        # Home dog I make the favorite: EMU at AKR, book AKR +7, my Akron by 1.4.
        home = {'home': {'abbr': 'AKR'}, 'away': {'abbr': 'EMU'}}
        self.assertEqual(game_context.dog_line(home, 7, 1.4), 'AKR +7 vs my -1.4')
        # Home dog I have losing by more: ILL at MSU, book MSU +2.5, my Illinois by 4.
        self.assertEqual(game_context.dog_line({'home': {'abbr': 'MSU'}, 'away': {'abbr': 'ILL'}}, 2.5, -4), 'MSU +2.5 vs my +4')
        # Away dog I make the favorite.
        self.assertEqual(game_context.dog_line(away, -3, -2), 'WYO +3 vs my -2')
        self.assertEqual(game_context.dog_line(away, -3, 0), 'WYO +3 vs my 0')

    def test_the_spread_pair_counts_the_captured_main_line_and_the_total_needs_both_sides(self):
        fresh = '2026-10-07T19:40:00Z'
        spread_row = {'gameId': 'CFB-1', 'market': 'point spread', 'state': 'open', 'book': 'DraftKings', 'line': -4,
                      'odds': -105, 'direction': None, 'side': None, 'gameMarket': True, 'observedAt': fresh}
        over = {'gameId': 'CFB-1', 'market': 'total points', 'state': 'open', 'book': 'DraftKings', 'line': 53.5,
                'odds': -110, 'direction': 'over', 'observedAt': fresh}
        under = {**over, 'direction': 'under'}
        parts = game_context.navigator(GAME, CARD, [spread_row, over, under], [], NOW, conferences={})['bettableParts']
        self.assertTrue(parts['spread'], 'the one captured main-line row is the book pricing both sides')
        self.assertTrue(parts['total'])
        parts = game_context.navigator(GAME, CARD, [spread_row, over], [], NOW, conferences={})['bettableParts']
        self.assertFalse(parts['total'], 'an over without its under is not a pair')
        one_sided = {**spread_row, 'gameMarket': False}
        self.assertFalse(game_context.navigator(GAME, CARD, [one_sided], [], NOW, conferences={})['bettableParts']['spread'],
                         'a lone quote that is not the game market does not count')
        stale = {**spread_row, 'observedAt': '2026-10-07T10:00:00Z'}
        self.assertFalse(game_context.navigator(GAME, CARD, [stale], [], NOW, conferences={})['bettableParts']['spread'])
        both = game_context.navigator(GAME, {**CARD, 'v2': {'margin': 4, 'total': 53}}, [spread_row, over, under], [], NOW, conferences={})
        self.assertEqual(both['look'], 'Fresh spread and total')

    def test_nfl_nicknames_take_plural_grammar(self):
        nfl = {**GAME, 'league': 'NFL'}
        card = {**CARD, 'home': {**CARD['home'], 'name': 'Cowboys'}, 'away': {**CARD['away'], 'name': 'Buccaneers'}}
        nav = game_context.navigator(nfl, card, [], [], NOW, conferences={})
        self.assertEqual(nav['plainGap'], 'Cowboys are 14.6 points better by my numbers and the book has them by 4.')
        result = game_context.why_differ(nfl, card, None, {}, {}, {}, [], NOW)
        self.assertEqual(result['drivers'][0]['text'], "Cowboys' offense ranks 9 of 136; Buccaneers' defense ranks 102.")
        self.assertEqual(game_context.navigator(GAME, CARD, [], [], NOW, conferences={})['plainGap'],
                         'FIU is 14.6 points better by my numbers and the book has them by 4.')
        self.assertEqual(game_context._an(81), 'an')
        self.assertEqual(game_context._an(65), 'a')
        self.assertEqual(game_context._an(18), 'an')
        self.assertEqual(game_context._an(100), 'a')

    def test_conference_comes_from_the_game_or_the_stored_table(self):
        table = {'2229': 'CUSA', '2': 'SEC'}
        nav = game_context.navigator(GAME, CARD, [], [], NOW, conferences=table)
        self.assertEqual(nav['conference'], {'home': 'CUSA', 'away': 'SEC'})
        explicit = {**GAME, 'home': {'id': '2229', 'conference': 'ACC'}}
        self.assertEqual(game_context.navigator(explicit, CARD, [], [], NOW, conferences=table)['conference']['home'], 'ACC')
        nfl = {**GAME, 'league': 'NFL'}
        self.assertEqual(game_context.navigator(nfl, CARD, [], [], NOW, conferences=table)['conference'], {'home': None, 'away': None})
        stored = game_context.stored_conferences()
        self.assertGreater(len(stored), 100, 'the dated ESPN standings table covers FBS')
        self.assertEqual(stored.get('2229'), 'CUSA')
        self.assertEqual(game_context.stored_conferences('/nonexistent/table.json'), {})


class WhyDifferTests(unittest.TestCase):
    def test_both_markets_get_their_own_drivers_and_the_larger_gap_leads(self):
        result = game_context.why_differ(GAME, CARD, None, {}, {}, {}, [], NOW)
        self.assertEqual(result['kind'], 'spread')
        self.assertEqual(set(result['markets']), {'spread', 'total'})
        self.assertEqual(result['markets']['spread']['gap'], 10.6)
        self.assertEqual(result['markets']['total']['gap'], -3.0)
        self.assertEqual(result['markets']['total']['ours'], 50.5)
        self.assertEqual(result['markets']['total']['book'], 53.5)
        self.assertTrue(result['markets']['total']['drivers'], 'the total has its own ratings driver')
        self.assertTrue(all('numbers' in d for d in result['drivers'] + result['markets']['total']['drivers']))
        self.assertEqual(result['drivers'][0]['numbers'], [9, 136, 102])
        self.assertEqual(result['drivers'][0]['direction'], 1, 'offense 9 against defense 102 pushes my way')
        only_total = {**CARD, 'v2': {'margin': 4, 'total': 50.5}}
        result = game_context.why_differ(GAME, only_total, None, {}, {}, {}, [], NOW)
        self.assertEqual(result['kind'], 'total')
        self.assertIsNone(result['markets']['spread'])
        self.assertLessEqual(len(result['text']), 220)

    def test_card_prints_the_lead_and_the_two_heaviest_drivers_whichever_way_they_push(self):
        log = [{'kickoff': f'2026-10-0{i}T16:00Z', 'pointsFor': 24, 'pointsAgainst': 14, 'opp': 'x'} for i in (1, 2, 3)]
        result = game_context.why_differ(GAME, CARD, None, {'2229': log, '2': log}, {}, {}, [], NOW)
        self.assertGreaterEqual(len(result['drivers']), 3)
        sentences = [s for s in re.split(r'(?<=\.)\s+', result['text']) if s]
        self.assertEqual(sentences[0], 'I have FIU by 14.6, the book has 4.')
        flipped = {**CARD, 'market': {**CARD['market'], 'spread': 3}}
        self.assertTrue(game_context.why_differ(GAME, flipped, None, {}, {}, {}, [], NOW)['text'].startswith('I have FIU by 14.6, the book has Auburn by 3.'))
        self.assertEqual(len(sentences), 3, 'lead plus exactly two drivers')
        heaviest = sorted(result['drivers'], key=lambda d: (-abs(d['weight']), d['text']))[:2]
        self.assertEqual(sentences[1:], [d['text'] for d in heaviest])
        # A heavier against-driver is printed, marked as against, instead of being dropped for a lighter supporter.
        drivers = [{'text': 'DraftKings moved the total from 50.5 to 44.5.', 'direction': -1, 'weight': 6.0, 'numbers': [50.5, 44.5]},
                   {'text': "Georgia Tech's last three games totaled 69, 55, 61.", 'direction': 1, 'weight': 5.7, 'numbers': [69, 55, 61]},
                   {'text': "Duke's last three games totaled 58, 42, 69.", 'direction': 1, 'weight': 2.1, 'numbers': [58, 42, 69]}]
        text = game_context.card_text('I have 55.1, the book has 44.5.', drivers)
        self.assertEqual(text, "I have 55.1, the book has 44.5. Against that: DraftKings moved the total from 50.5 to 44.5. "
                               "Georgia Tech's last three games totaled 69, 55, 61.")
        self.assertLessEqual(len(text), game_context.CARD_TEXT)
        self.assertIsNone(game_context.card_text('Lead.', []))

    def test_ratings_drivers_point_the_way_the_ranks_actually_push(self):
        # Spread: the side my number likes (home, gap > 0) has the worse offense than the defense it faces: against.
        weak = {**CARD, 'home': {**CARD['home'], 'strength': {'offense': 115, 'defense': 60, 'teams': 136}},
                'away': {**CARD['away'], 'strength': {'offense': 50, 'defense': 74, 'teams': 136}}}
        result = game_context.why_differ(GAME, weak, None, {}, {}, {}, [], NOW)
        ratings = next(d for d in result['markets']['spread']['drivers'] if 'offense ranks' in d['text'])
        self.assertEqual(ratings['text'], "FIU's offense ranks 115 of 136; Auburn's defense ranks 74.")
        self.assertEqual(ratings['direction'], -1)
        # Total under lean (my 50.5 against 53.5): the best defense here ranks 60 of 136, better than the median: support.
        total = next(d for d in result['markets']['total']['drivers'] if 'defense ranks' in d['text'] and 'by my numbers' in d['text'])
        self.assertEqual(total['text'], "FIU's defense ranks 60 of 136 by my numbers.")
        self.assertEqual(total['direction'], 1)
        # Over lean citing a defense better than the median argues against the over (IOWA at WASH, defense 28 of 136).
        over = {**CARD, 'v2': {'margin': 4, 'total': 58.5}, 'home': {**CARD['home'], 'strength': {'offense': 62, 'defense': 28, 'teams': 136}},
                'away': {**CARD['away'], 'strength': {'offense': 40, 'defense': 20, 'teams': 136}}}
        result = game_context.why_differ(GAME, over, None, {}, {}, {}, [], NOW)
        total = next(d for d in result['drivers'] if 'defense ranks' in d['text'])
        self.assertEqual(total['text'], "FIU's defense ranks 28 of 136 by my numbers.")
        self.assertEqual(total['direction'], -1)
        self.assertEqual(result['text'], "I have 58.5, the book has 53.5. Against that: FIU's defense ranks 28 of 136 by my numbers. "
                                         'DraftKings moved the total from 52.5 to 53.5.', 'the heavier against-driver prints first, marked')
        # Over lean citing a defense ranked 84 of 136: support.
        soft = {**over, 'home': {**CARD['home'], 'strength': {'offense': 62, 'defense': 84, 'teams': 136}}}
        total = next(d for d in game_context.why_differ(GAME, soft, None, {}, {}, {}, [], NOW)['drivers'] if 'defense ranks' in d['text'])
        self.assertEqual(total['direction'], 1)

    def test_blowout_flag_names_the_actual_result(self):
        log = [{'kickoff': '2026-09-19T19:30:00Z', 'pointsFor': 55, 'pointsAgainst': 0, 'opp': 'x'},
               {'kickoff': '2026-09-26T16:00:00Z', 'pointsFor': 24, 'pointsAgainst': 20, 'opp': 'x'},
               {'kickoff': '2026-10-03T16:00:00Z', 'pointsFor': 21, 'pointsAgainst': 17, 'opp': 'x'}]
        result = game_context.why_differ(GAME, CARD, None, {'2229': log}, {}, {}, [], NOW)
        flag = next(d for d in result['drivers'] if d.get('flag') == 'blowout')
        self.assertEqual(flag['text'], 'FIU won by 55 on Sep 19; one lopsided score can swing a rating.')
        self.assertEqual(flag['numbers'], [55])
        self.assertEqual(flag['direction'], -1)
        lost = [{**r, 'pointsFor': r['pointsAgainst'], 'pointsAgainst': r['pointsFor']} for r in log]
        result = game_context.why_differ(GAME, CARD, None, {'2': lost}, {}, {}, [], NOW)
        flag = next(d for d in result['drivers'] if d.get('flag') == 'blowout')
        self.assertEqual(flag['text'], 'Auburn lost by 55 on Sep 19; one lopsided score can swing a rating.')
        self.assertNotIn('28-point', ' '.join(every_text(result)))

    def test_card_summary_keeps_the_sentence_and_leaves_drivers_to_the_game_page(self):
        result = game_context.why_differ(GAME, CARD, None, {}, {}, {}, [], NOW)
        summary = game_context.card_summary(result)
        self.assertEqual(set(summary), {'stale', 'kind', 'ours', 'book', 'gap', 'text', 'caution'})
        self.assertEqual(summary['text'], result['text'])
        self.assertIsNone(game_context.card_summary(None))
        stale = {'stale': True, 'text': game_context.STALE_TEXT, 'drivers': []}
        self.assertEqual(game_context.card_summary(stale), {'stale': True, 'text': game_context.STALE_TEXT})

    def test_stale_line_prints_only_the_staleness_line(self):
        stale = {**CARD, 'market': {**CARD['market'], 'retrievedAt': '2026-10-06T15:00Z'}}
        result = game_context.why_differ(GAME, stale, None, {}, {}, {}, [], NOW)
        self.assertEqual(result, {'stale': True, 'text': game_context.STALE_TEXT, 'drivers': []})
        self.assertNotIn('markets', result)

    def test_pace_driver_uses_the_snapshot_and_stored_plays(self):
        card = {**CARD, 'v2': {'margin': 4, 'total': 58.5}}
        snapshot = {'players': {'home': {'volume': {'plays': 78}}, 'away': {'volume': {'plays': 76}}}}
        logs = {team: [{'kickoff': f'2026-10-0{i}T16:00Z', 'pointsFor': 30, 'pointsAgainst': 27, 'opp': 'x',
                        'offense': {'pbp': {'plays': 68}}} for i in (1, 2, 3)] for team in ('2229', '2')}
        result = game_context.why_differ(GAME, card, snapshot, logs, {}, {}, [], NOW)
        pace = [d for d in result['drivers'] if 'plays' in d['text']]
        self.assertEqual(len(pace), 1)
        self.assertEqual(pace[0]['text'], 'I project about 154 plays; these two teams have averaged 136 together this season.')
        self.assertEqual(pace[0]['numbers'], [154, 136])
        under = {**CARD, 'v2': {'margin': 4, 'total': 48.5}}
        self.assertFalse([d for d in game_context.why_differ(GAME, under, snapshot, logs, {}, {}, [], NOW)['drivers'] if 'plays' in d['text']],
                         'a faster pace never argues for an under lean')

    def test_no_banned_public_words_in_any_template(self):
        log = [{'kickoff': f'2026-10-0{i}T16:00Z', 'pointsFor': 45, 'pointsAgainst': 10, 'opp': 'x'} for i in (1, 2, 3)]
        ranks = {'x': {'offense': 120, 'defense': 125, 'teams': 136}, '2229': CARD['home']['strength']}
        weather = {'forecast': {'issuedAt': '2026-10-07T18:00Z', 'periodStart': GAME['kickoff'], 'windMph': 19, 'precipProb': 65}}
        rows = [{'gameId': 'CFB-1', 'roleHold': 'qb'}]
        nfl_game = {**GAME, 'league': 'NFL'}
        injuries = {'2229': [{'name': 'Some QB', 'position': 'QB', 'status': 'Out'}]}
        for g in (GAME, nfl_game):
            result = game_context.why_differ(g, CARD, None, {'2229': log, '2': log}, ranks, injuries, rows, NOW, weather)
            for text in every_text(result):
                self.assertIsNone(BANNED.search(text), text)
                self.assertNotIn('far from the book line', text)
        self.assertIn('qb_change', {d.get('flag') for d in result['drivers']})
        self.assertIn('injury', {d.get('flag') for d in result['drivers']})


class RecordCardTests(unittest.TestCase):
    def test_card_path_only_for_open_plays_that_went_out(self):
        open_play = {'id': 'NFL-2026-W4-x', 'posted': True, 'favorite': True}
        self.assertEqual(build_site.record_card(open_play), 'data/cards/NFL-2026-W4-x.png')
        discord = {'id': 'CFB-2026-W6-y', 'delivery': {'discordAt': '2026-10-04T15:57:35Z'}, 'modelLean': 'over'}
        self.assertEqual(build_site.record_card(discord), 'data/cards/CFB-2026-W6-y.png')
        ticket = {'id': 'CFB-2026-W5-ladder-1002-fd', 'posted': True, 'legs': ['a', 'b']}
        self.assertEqual(build_site.record_card(ticket), 'data/cards/CFB-2026-W5-ladder-1002-fd.png')
        # Graded plays lose their image on the hosted build (feed.py draws open plays only): no link, not a 404.
        self.assertIsNone(build_site.record_card({**open_play, 'result': 'win'}))
        self.assertIsNone(build_site.record_card({**ticket, 'result': 'loss'}))
        self.assertIsNone(build_site.record_card({**open_play, 'status': 'pulled'}))
        self.assertIsNone(build_site.record_card({**open_play, 'entryNote': 'closed by precheck'}))
        self.assertIsNone(build_site.record_card({'id': 'quiet', 'favorite': True}), 'no delivery evidence, no card')
        self.assertIsNone(build_site.record_card({'id': 'unpostable', 'posted': True}), 'not a postable kind')
        self.assertIsNone(build_site.record_card({'id': 'old', 'posted': True, 'favorite': True, 'historicalImport': True}))
        self.assertIsNone(build_site.record_card({'id': '../escape', 'posted': True, 'favorite': True}))


if __name__ == '__main__':
    unittest.main()
