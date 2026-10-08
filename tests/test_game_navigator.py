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
        self.assertEqual(nav['look'], 'Total 53.5 vs my 50.5', 'a 3-point total gap outranks the spread gap text')
        only_spread = {**CARD, 'v2': {'margin': 14.6, 'total': 53}}
        self.assertEqual(game_context.navigator(GAME, only_spread, [], [], NOW, conferences={})['look'], 'AUB +4 vs my -14.6')
        official = game_context.navigator(GAME, CARD, [], [{'gameId': 'CFB-1', 'publishedAt': '2026-10-07T12:00Z'}], NOW, conferences={})
        self.assertEqual(official['look'], 'Best bet posted')
        even = {**CARD, 'market': {**CARD['market'], 'spread': -3}, 'v2': {'margin': 2, 'total': 53}}
        self.assertEqual(game_context.navigator(GAME, even, [], [], NOW, conferences={})['look'], 'Even matchup')
        blow = {**CARD, 'market': {**CARD['market'], 'spread': -28, 'total': 55}, 'v2': {'margin': 27, 'total': 55}}
        self.assertEqual(game_context.navigator(GAME, blow, [], [], NOW, conferences={})['look'], 'Props carry garbage-time risk')
        self.assertIsNone(game_context.navigator({**GAME, 'state': 'post'}, CARD, [], [], NOW, conferences={})['look'])

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
        only_total = {**CARD, 'v2': {'margin': 4, 'total': 50.5}}
        result = game_context.why_differ(GAME, only_total, None, {}, {}, {}, [], NOW)
        self.assertEqual(result['kind'], 'total')
        self.assertIsNone(result['markets']['spread'])
        self.assertLessEqual(len(result['text']), 220)

    def test_card_prints_the_lead_and_at_most_two_supporting_drivers(self):
        log = [{'kickoff': f'2026-10-0{i}T16:00Z', 'pointsFor': 24, 'pointsAgainst': 14, 'opp': 'x'} for i in (1, 2, 3)]
        result = game_context.why_differ(GAME, CARD, None, {'2229': log, '2': log}, {}, {}, [], NOW)
        supporting = [d for d in result['drivers'] if d['direction'] > 0]
        self.assertGreaterEqual(len(supporting), 3)
        sentences = [s for s in re.split(r'(?<=\.)\s+', result['text']) if s]
        self.assertEqual(sentences[0], 'I have FIU by 14.6, the book has 4.')
        flipped = {**CARD, 'market': {**CARD['market'], 'spread': 3}}
        self.assertTrue(game_context.why_differ(GAME, flipped, None, {}, {}, {}, [], NOW)['text'].startswith('I have FIU by 14.6, the book has Auburn by 3.'))
        self.assertEqual(len(sentences), 3, 'lead plus exactly two drivers')
        self.assertEqual(sentences[1:], [d['text'] for d in supporting[:2]])

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
    def test_card_path_only_for_plays_that_went_out(self):
        posted = {'id': 'NFL-2026-W4-x', 'posted': True, 'result': 'win'}
        self.assertEqual(build_site.record_card(posted), 'data/cards/NFL-2026-W4-x.png')
        discord = {'id': 'CFB-2026-W6-y', 'delivery': {'discordAt': '2026-10-04T15:57:35Z'}}
        self.assertEqual(build_site.record_card(discord), 'data/cards/CFB-2026-W6-y.png')
        self.assertIsNone(build_site.record_card({'id': 'quiet', 'result': 'loss'}))
        self.assertIsNone(build_site.record_card({'id': 'old', 'posted': True, 'historicalImport': True}))
        self.assertIsNone(build_site.record_card({'id': '../escape', 'posted': True}))


if __name__ == '__main__':
    unittest.main()
