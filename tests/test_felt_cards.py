import base64
import copy
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

PHOTO_URI = ('data:image/png;base64,'
             + base64.b64encode((ROOT / 'site' / 'kookn-chef.png').read_bytes()).decode('ascii'))


def chrome_dump(page, profile, timeout=20):
    """Return dump-dom output even when macOS Chrome stays alive afterward."""
    output_path = page.with_suffix('.dom.html')
    with output_path.open('w', encoding='utf-8') as output:
        process = subprocess.Popen(
            [pick_card.chrome_path(), '--headless', '--disable-gpu', '--no-sandbox',
             '--disable-extensions', '--no-first-run', '--virtual-time-budget=3000',
             f'--user-data-dir={profile}', '--dump-dom', page.as_uri()],
            stdout=output, stderr=subprocess.DEVNULL, text=True)
        deadline, last_size, stable = time.time() + timeout, -1, 0
        try:
            while time.time() < deadline:
                output.flush()
                size = output_path.stat().st_size if output_path.exists() else -1
                stable = stable + 1 if size > 0 and size == last_size else 0
                last_size = size
                if process.poll() is not None or stable >= 3:
                    break
                time.sleep(.25)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    return output_path.read_text(encoding='utf-8')

import felt_cards
import pick_card
import research_art
import sheet


GAME = {
    'league': 'NFL',
    'kickoff': '2026-10-08T00:15:00Z',
    'away': {'id': '1', 'abbreviation': 'BUF', 'short': 'Bills', 'color': '#00338D'},
    'home': {'id': '2', 'abbreviation': 'LAR', 'short': 'Rams', 'color': '#003594'},
}
PICK = {
    'id': 'NFL-2026-W5-buf-lar-under-54-5-dk',
    'title': 'Buffalo at Los Angeles under 54.5',
    'displayTitle': 'Buffalo at Los Angeles under 54.5',
    'marketType': 'total',
    'direction': 'under',
    'line': 54.5,
    'projection': 49.8,
    'odds': -110,
    'book': 'DraftKings',
    'publishedAt': '2026-10-07T04:05:00Z',
    'probabilityAtPublication': {'chance': .57, 'breakEven': .524, 'calibrated': True},
}


class FeltCardTests(unittest.TestCase):
    def felt(self):
        return mock.patch.dict(os.environ, {'KEENROUDY_CARD_THEME': 'felt'})

    def valid(self, text):
        ET.fromstring(text)
        self.assertEqual(pick_card.svg_size(text), (1080, 1350))
        self.assertIn('@font-face', text)
        self.assertIn('Barlow Condensed', text)
        self.assertIn('DM Sans', text)
        self.assertIn(felt_cards.FELT_NIGHT, text)
        self.assertIn('21+ · Entertainment only', text)

    def test_cutover_uses_publication_time_and_has_a_preview_override(self):
        with mock.patch.object(pick_card, 'FELT_FROM', '2026-10-07T04:00:00Z'):
            self.assertFalse(pick_card.felt_enabled({'publishedAt': '2026-10-07T03:59:59Z'}))
            self.assertTrue(pick_card.felt_enabled(PICK))
        with self.felt():
            self.assertTrue(pick_card.felt_enabled({}))
        self.assertIsNone(pick_card.FELT_FROM, 'renders are review-only until the dated cutover is approved')
        self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'legacy')
        with mock.patch.object(pick_card, 'FELT_FROM', '2026-10-07T04:00:00Z'):
            self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'felt')
        with mock.patch.object(pick_card, 'FELT_FROM', '2026-10-07'):
            self.assertTrue(pick_card.felt_enabled(PICK), 'a date-only cutover is timezone-safe')
            self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'felt')
        with mock.patch.dict(os.environ, {'KEENROUDY_FELT_FROM': '2026-10-01'}, clear=False):
            self.assertEqual(pick_card.card_theme(PICK['publishedAt']), 'legacy',
                             'a Mac-only override cannot relabel the hosted renderer')

    def test_every_felt_builder_renders_with_embedded_ofl_fonts(self):
        ticket = {
            'id': 'ticket', 'parlayType': 'longshot', 'odds': 750, 'book': 'FanDuel',
            'publishedAt': PICK['publishedAt'],
            'legs': [{'title': 'Josh Allen 225+ passing yards'}, {'title': 'Puka Nacua 50+ receiving yards'}],
        }
        climb = {
            'id': 'climb', 'parlayType': 'ladder', 'odds': 105, 'book': 'FanDuel',
            'publishedAt': PICK['publishedAt'], 'result': 'win',
            'legs': ticket['legs'],
            'ladder': {'run': 1, 'step': 2, 'stake': 75, 'payout': 154, 'banked': 19, 'bankedAfter': 50},
        }
        receipt = {
            'key': 'receipt:day:2026-10-07', 'due': '2026-10-08T13:00:00Z',
            'title': '1-1', 'when': 'Wednesday, Oct 7',
            'rows': [('win', 'Josh Allen over 224.5 passing yards', 'Final 267'),
                     ('loss', 'Puka Nacua over 69.5 receiving yards', 'Final 62')],
        }
        research = {
            'day': '2026-10-07', 'title': 'MATCHUP RESEARCH', 'kicker': 'EXACT MAIN LINES',
            'kind': 'matchup', 'accent': '#20C774',
            'rows': [{'title': 'Josh Allen over 224.5 passing yards', 'price': '-110 FanDuel',
                      'metric': '4/5 this season', 'detail': 'Fresh exact line'}],
        }
        with self.felt():
            cards = [
                pick_card.modern_svg(PICK, GAME, record={'wins': 2, 'losses': 4},
                                     art={'kind': 'logos', 'uris': ['data:image/png;base64,AA',
                                                                    'data:image/png;base64,BB']}),
                pick_card.ticket_svg(ticket),
                pick_card.ladder_svg(climb),
                pick_card.ladder_result_svg(dict(climb, settledAt='2026-10-08T03:30:00Z')),
                pick_card.receipt_svg(receipt),
                research_art.svg(research, {0: 'data:image/png;base64,AA'}),
            ]
        for card in cards:
            self.valid(card)

    def test_font_files_ship_with_their_ofl_licenses(self):
        for name in ('BarlowCondensed-Bold.ttf', 'DMSans-Variable.ttf',
                     'OFL-BarlowCondensed.txt', 'OFL-DMSans.txt'):
            self.assertGreater((ROOT / 'scripts' / 'fonts' / name).stat().st_size, 1000)

    def test_open_ticket_stub_is_neutral_and_receipt_uses_the_supplied_straight_headline(self):
        with self.felt():
            play = pick_card.modern_svg(PICK, GAME, record={'wins': 35, 'losses': 35})
            receipt = pick_card.receipt_svg({
                'title': '2-3', 'when': 'Sunday, Oct 4', 'season': '35–35',
                'rows': [('loss', 'One under 1.5 receptions', 'Final: 2', 'player'),
                         ('win', 'Two under 2.5 receptions', 'Final: 1', 'player'),
                         ('win', 'Three over 3.5 receptions', 'Final: 4', 'player'),
                         ('loss', 'Four under 48', 'Final: 57', 'team'),
                         ('loss', 'Five under 48.5', 'Final: 55', 'team'),
                         ('win', '80/20 Climb step 2', '$75 → $117', 'ladder'),
                         ('loss', '3-leg parlay', '2/3 legs hit', 'parlay')],
            })
        self.assertIn('data-zone="open-stub"', play)
        self.assertIn(f'data-zone="open-stub" x="826"', play)
        self.assertIn(f'fill="{felt_cards.FELT_RAISED}"', play)
        self.assertIn('SEASON 35–35', play)
        self.assertIn('>BEST BETS<', receipt)
        self.assertIn('>2–3<', receipt)
        self.assertIn('SEASON 35–35', receipt)
        self.assertIn('TRACKED APART · FUN TICKETS 0–1 · CLIMB STEP 2 ✓', receipt)
        self.assertIn('data-zone="tracked-divider"', receipt)
        self.assertNotIn('+2 MORE ON THE PUBLIC RECORD', receipt)
        self.assertNotIn('SEASON 2-3', receipt)
        root = ET.fromstring(play)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        label = root.find(".//s:g[@data-zone='chance-label']/s:text", namespace)
        self.assertIsNotNone(label)
        self.assertLessEqual(float(label.attrib['font-size']), 24)

    def test_play_card_wraps_a_long_manual_selection_without_dropping_words(self):
        title = 'San Diego State +7.5 vs Oregon State in Corvallis'
        with self.felt():
            card = pick_card.modern_svg(dict(PICK, displayTitle=title, title=title), GAME)
        self.valid(card)
        for word in title.upper().split():
            self.assertIn(word, card)
        self.assertNotIn('…', card)
        root = ET.fromstring(card)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        lines = [node.text for node in root.findall(".//s:g[@data-zone='play-selection']/s:text", namespace)]
        self.assertTrue(any('STATE\u00a0+7.5' in line for line in lines),
                        'a spread number must stay with its team instead of sitting alone')

    @unittest.skipUnless(pick_card.chrome_path(), 'needs a browser to measure the embedded card font')
    def test_play_card_text_zones_fit_real_matchups_and_clear_a_player_photo(self):
        matchups = (('James Madison', 'Georgia Southern', 'JMU', 'GASO'),
                    ('Sacramento State', 'Bowling Green', 'SAC', 'BGSU'),
                    ('Oklahoma State', 'West Virginia', 'OKST', 'WVU'))
        cards = []
        with self.felt():
            for index, (away, home, away_abbr, home_abbr) in enumerate(matchups, 1):
                subject = f'{away} at {home}'
                title = f'{subject} under 54.5'
                game = {
                    'league': 'CFB', 'kickoff': '2026-10-10T16:00:00Z',
                    'away': {'id': f'a{index}', 'school': away, 'short': away,
                             'abbreviation': away_abbr, 'color': '#111111'},
                    'home': {'id': f'h{index}', 'school': home, 'short': home,
                             'abbreviation': home_abbr, 'color': '#222222'},
                }
                pick = dict(PICK, id=f'CFB-{index}-total', title=title, displayTitle=title,
                            athleteId=None, player=None)
                cards.append(pick_card.modern_svg(pick, game, record={'wins': 35, 'losses': 35}))
            player = "Na'eem Abdul-Rahim Gladding"
            title = f'{player} over 64.5 receiving yards'
            cards.append(pick_card.modern_svg(
                dict(PICK, id='CFB-long-player', title=title, displayTitle=title,
                     marketType='receiving_yards', direction='over', athleteId='long-player', player=player),
                game, record={'wins': 35, 'losses': 35},
                art={'kind': 'photo', 'uri': PHOTO_URI}))
            passer = 'Jaron-Keawe Sagapolutele'
            pass_title = f'{passer} under 249.5 passing yards'
            cards.append(pick_card.modern_svg(
                dict(PICK, id='CFB-long-passer', title=pass_title, displayTitle=pass_title,
                     marketType='passing_yards', direction='under', athleteId='long-passer', player=passer),
                game, record={'wins': 35, 'losses': 35},
                art={'kind': 'photo', 'uri': PHOTO_URI}))
            receiver = 'Kamaehu Kopa-Kaawalauole'
            long_title = f'{receiver} under 249.5 passing attempts'
            cards.append(pick_card.modern_svg(
                dict(PICK, id='CFB-two-line-ticket', title=long_title, displayTitle=long_title,
                     marketType='passing_attempts', direction='under', athleteId='long-receiver',
                     player=receiver),
                game, record={'wins': 35, 'losses': 35},
                art={'kind': 'photo', 'uri': PHOTO_URI}))
            receptions_title = f'{receiver} under 2.5 receptions'
            cards.append(pick_card.modern_svg(
                dict(PICK, id='CFB-long-receptions', title=receptions_title,
                     displayTitle=receptions_title, marketType='receptions', direction='under',
                     athleteId='long-receptions', player=receiver),
                game, record={'wins': 35, 'losses': 35},
                art={'kind': 'photo', 'uri': PHOTO_URI}))
            completions_title = f'{passer} over 22.5 completions'
            cards.append(pick_card.modern_svg(
                dict(PICK, id='CFB-long-completions', title=completions_title,
                     displayTitle=completions_title, marketType='completions', direction='over',
                     athleteId='long-completions', player=passer),
                game, record={'wins': 35, 'losses': 35},
                art={'kind': 'photo', 'uri': PHOTO_URI}))

        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / 'measure.html'
            script = """
<script>
document.fonts.ready.then(() => {
  const box = (node) => {
    const value = node.getBBox();
    return {text: node.textContent, left: value.x, top: value.y,
            right: value.x + value.width, bottom: value.y + value.height};
  };
  const rows = [...document.querySelectorAll('body > svg')].map((card) => {
    const subject = [...card.querySelectorAll('[data-zone="play-subject"] text')].map(box);
    const selection = [...card.querySelectorAll('[data-zone="play-selection"] text')].map(box);
    const season = card.querySelector('[data-zone="season-strip"] text');
    const ticket = card.querySelector('[data-zone="play-ticket"]');
    return {photo: !!card.querySelector('[data-zone="player-photo"]'), subject, selection,
            season: season && box(season), ticket: ticket && box(ticket)};
  });
  document.body.textContent = JSON.stringify(rows);
  document.body.dataset.measured = '1';
});
</script>"""
            page.write_text('<!doctype html><meta charset="utf-8"><body>'
                            + ''.join(cards) + script + '</body>', encoding='utf-8')
            dom = chrome_dump(page, Path(folder) / 'chrome-profile')
        match = re.search(r'<body data-measured="1">(.*?)</body>', dom, re.S)
        self.assertIsNotNone(match, dom[-500:])
        measured = json.loads(html.unescape(match.group(1)))
        self.assertEqual(len(measured), 8)
        for card in measured:
            self.assertTrue(card['subject'], card)
            self.assertTrue(card['selection'], card)
            self.assertIsNotNone(card['season'], card)
            self.assertIsNotNone(card['ticket'], card)
            for row in card['subject'] + card['selection'] + [card['season']]:
                self.assertLessEqual(row['right'], 1016, row)
            self.assertGreaterEqual(card['season']['top'], card['ticket']['bottom'] + 12, card)
        for card in measured:
            if card['photo']:
                self.assertLessEqual(card['subject'][0]['right'], 830, card)
        self.assertEqual(len(measured[-4]['selection']), 1,
                         'UNDER 249.5 PASS YDS should fit one line before wrapping')
        self.assertEqual(len(measured[-3]['selection']), 2,
                         'the strip clearance must also cover a genuinely two-line selection')
        for card in measured[-2:]:
            self.assertEqual(len(card['subject']), 2,
                             'the market-width regression must use a two-line CFB name')

    def test_last_climb_checkpoint_moves_now_and_again_clear_of_the_goal_flag(self):
        open_rung = {'id': 'near-goal', 'parlayType': 'ladder', 'odds': -110, 'book': 'FanDuel',
                     'legs': [{'title': 'One 10+ yards'}, {'title': 'Two 10+ yards'}],
                     'ladder': {'run': 3, 'step': 5, 'stake': 75, 'payout': 146,
                                'banked': 600, 'start': 50, 'goal': 1000}}
        result_rung = dict(open_rung, actual='all 2 legs won')
        cards = []
        with self.felt():
            cards.append(pick_card.ladder_svg(open_rung))
            cards.append(pick_card.ladder_result_svg(dict(
                result_rung, result='win',
                ladder=dict(open_rung['ladder'], bankedAfter=650, nextStake=100,
                            totalAfter=750))))
            for result in ('push', 'void'):
                cards.append(pick_card.ladder_result_svg(dict(
                    result_rung, result=result, actual=f'legs: {result}, {result}')))

        namespace = {'s': 'http://www.w3.org/2000/svg'}
        for card in cards:
            root = ET.fromstring(card)
            label = root.find(".//s:g[@data-zone='climb-current-label'][@data-checkpoint='1000']/s:text",
                              namespace)
            flag = root.find(".//s:path[@data-zone='climb-goal-flag']", namespace)
            self.assertIsNotNone(label)
            self.assertIsNotNone(flag)
            pole_x = float(re.match(r'M([0-9.]+)', flag.attrib['d']).group(1))
            self.assertEqual(label.attrib.get('text-anchor'), 'end')
            self.assertLessEqual(float(label.attrib['x']), pole_x - 52)

    def test_research_climb_and_longshot_preserve_public_rules(self):
        ticket = {'id': 't', 'parlayType': 'longshot', 'odds': 700, 'book': 'FanDuel',
                  'gameIds': ['g', 'g2', 'g3', 'g4', 'g5'],
                  'legs': [{'title': 'Game over 40.5'}]}
        choice = {'kind': 'matchup', 'title': 'MATCHUP TRENDS', 'kicker': 'EXACT LINE + OPPONENT DEFENSE',
                  'rows': [{'title': 'Bucky Irving over 13.5 carries', 'price': '-107 DK',
                            'metric': '8/10 exact-line trend', 'detail': 'DAL allows 24.2 carries/game to RBs',
                            'kickoff': '2026-10-09T00:15:00Z', 'matchupLabel': 'TB at DAL',
                            'opponentAbbr': 'DAL', 'statLabel': 'carries', 'hits': 8, 'games': 10,
                            'seasonHits': 3, 'seasonGames': 4,
                            'historyValues': [16, 18, 12, 20, 15, 22, 14, 19, 8, 17],
                            'matchup': {'rank': 23, 'of': 32, 'pos': 'RB', 'stat': 'car',
                                        'value': 24.2, 'supports': True}}]}
        climb = {'id': 'c', 'parlayType': 'ladder', 'odds': -173, 'book': 'FanDuel',
                 '_allClimbsBanked': 42, 'legs': [{'title': 'One 10+ yards'}, {'title': 'Two 10+ yards'}],
                 'ladder': {'run': 3, 'step': 1, 'stake': 50, 'payout': 79, 'banked': 0, 'start': 50},
                 'result': 'loss', 'actual': 'legs: loss, win'}
        with self.felt():
            longshot = pick_card.ticket_svg(ticket, GAME, art=[{'kind': 'logos', 'uris': ['data:image/png;base64,AA', 'data:image/png;base64,BB']}])
            research = research_art.svg(choice)
            open_climb = pick_card.ladder_svg(dict(climb, result=None))
            result = pick_card.ladder_result_svg(climb)
        self.assertNotIn('#B49BE0', longshot)
        self.assertEqual(longshot.count('<image href="data:image/png;base64,'), 2)
        self.assertIn('5 games · Wed Oct 7', longshot)
        self.assertIn('Over 13.5 in 8 of his last 10 games', research)
        root = ET.fromstring(research)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        defense = root.findall(".//s:g[@data-zone='research-defense']/s:text", namespace)
        self.assertEqual(' '.join(node.text for node in defense),
                         'DAL allows 24.2 carries a game to RBs, 23rd of 32')
        self.assertIn('LAST 10 GAMES', research)
        self.assertIn('fill="' + felt_cards.BURNT + '"', research)
        self.assertIn('3 of 4 this season', research)
        self.assertNotIn('8 of 10 this season', research)
        self.assertEqual(research.count('8/10'), 0)
        self.assertNotIn('EXACT-LINE PROOF', research)
        self.assertNotIn('PROOF POINT', research)
        self.assertNotIn('POSITIVE RESEARCH LABEL', research)
        self.assertIn('ALL CLIMBS  $42 BANKED', open_climb)
        self.assertIn('NEXT  $50 RESTART', result)
        self.assertNotIn('AGAIN', result)
        self.assertIn('$1,000', result)
        self.assertIn('>✗<', result)
        self.assertIn('>✓<', result)

    def test_weekly_receipt_uses_category_records_without_push_badges(self):
        weekly = {
            'title': '7-7', 'when': 'Sep 30 to Oct 6', 'season': '35–35',
            'rows': [(None, 'Player props 6-2', '', 'player'),
                     (None, 'Game lines 1-5', '', 'team'),
                     (None, 'Fun parlays 0-5', '', 'parlay'),
                     (None, 'Ladder 1-2', '', 'ladder')],
        }
        with self.felt():
            card = pick_card.receipt_svg(weekly)
        self.valid(card)
        self.assertIn('>BEST BETS<', card)
        self.assertIn('>7–7<', card)
        self.assertEqual(card.count('data-zone="category-record"'), 4)
        self.assertIn('>PLAYER PROPS<', card)
        self.assertIn('>GAME LINES<', card)
        self.assertIn('>FUN TICKETS<', card)
        self.assertIn('>80/20 CLIMB<', card)
        self.assertIn('TRACKED APART FROM BEST BETS', card)
        self.assertIn('data-zone="tracked-divider"', card)
        self.assertNotIn('PUSH', card)
        self.assertNotIn('>LADDER<', card)

    def test_daily_receipt_keeps_hidden_best_bet_outcomes_and_void_is_not_a_push(self):
        rows = [('win', f'Best bet {index}', f'Final {index}', 'player') for index in range(5)]
        rows += [('loss', 'Sixth best bet', 'Final miss', 'team'),
                 ('void', 'Void best bet', 'Did not participate', 'team'),
                 ('loss', 'Three-leg ticket', '2/3 legs hit', 'parlay')]
        with self.felt():
            card = pick_card.receipt_svg({'title': '5-1', 'when': 'Saturday, Oct 3', 'rows': rows})
        self.assertIn('+2 BEST BETS · 1 MISSED · 1 VOID', card)
        self.assertIn('TRACKED APART · FUN TICKETS 0–1', card)
        self.assertNotIn('MORE RESULT', card)
        self.assertNotIn('RESULT · TRACKED APART', card)

        with self.felt():
            void = pick_card.receipt_svg({'title': '0-0', 'when': 'Sunday, Oct 4',
                                          'rows': [('void', 'Brock Bowers over 60 receiving yards',
                                                    'Inactive scratch', 'player')]})
        self.assertIn('– VOID', void)
        self.assertNotIn('– PUSH', void)

    def test_daily_receipt_keeps_every_same_day_climb_rung(self):
        rows = [('win', f'Best bet {index}', f'Final {index}', 'player') for index in range(5)]
        rows += [('win', '80/20 Climb #2 step 1', '$50 → $79', 'ladder'),
                 ('loss', '80/20 Climb #2 step 2', 'One leg missed', 'ladder')]
        with self.felt():
            card = pick_card.receipt_svg({'title': '5-0', 'when': 'Sunday, Oct 4', 'rows': rows})
        self.assertIn('TRACKED APART · CLIMB #2 STEP 1 ✓ · STEP 2 ✗', card)
        self.assertEqual(card.count('STEP 1'), 1)
        self.assertEqual(card.count('STEP 2'), 1)

    def test_daily_receipt_fits_long_cfb_titles_and_final_scores_without_cutting(self):
        title = 'Appalachian State/Coastal Carolina under 61.5'
        detail = 'Final: Appalachian State 31, Coastal Carolina 28'
        rows = [('loss', title, detail, 'team'),
                ('win', 'Short result one', 'Final: 24–17', 'team'),
                ('loss', 'Short result two', 'Final: 21–28', 'team'),
                ('win', 'Short result three', 'Final: 31–10', 'team')]
        with self.felt():
            card = pick_card.receipt_svg({'title': '2-2', 'when': 'Sunday, Oct 11',
                                          'season': '37–37', 'rows': rows})
        self.valid(card)
        root = ET.fromstring(card)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        title_groups = root.findall(".//s:g[@data-zone='receipt-title']", namespace)
        detail_groups = root.findall(".//s:g[@data-zone='receipt-detail']", namespace)
        self.assertEqual(title, ' '.join(node.text for node in title_groups[0]))
        self.assertEqual(detail, ' '.join(node.text for node in detail_groups[0]))
        self.assertNotIn('…', ''.join(node.text or '' for node in title_groups[0]))
        self.assertNotIn('…', ''.join(node.text or '' for node in detail_groups[0]))

    def test_daily_receipt_without_best_bets_uses_the_matching_public_label(self):
        with self.felt():
            fun = pick_card.receipt_svg({
                'title': 'Fun parlays 0-3', 'when': 'Monday, Oct 5',
                'rows': [('loss', 'Three-leg ticket', '2/3 legs hit', 'parlay')],
            })
            climb = pick_card.receipt_svg({
                'title': 'Ladder 1-2', 'when': 'Monday, Oct 5',
                'rows': [('loss', '80/20 Climb step 1', 'One leg hit', 'ladder')],
            })
        self.assertIn('>FUN TICKETS<', fun)
        self.assertIn('>0–3<', fun)
        self.assertNotIn('>BEST BETS<', fun)
        self.assertIn('>80/20 CLIMB<', climb)
        self.assertIn('>1–2<', climb)
        self.assertNotIn('>BEST BETS<', climb)
        self.assertNotIn('>LADDER<', climb)

    def test_winning_and_complete_climb_cards_keep_leg_marks_and_next_money(self):
        rung = {'id': 'c', 'parlayType': 'ladder', 'result': 'win', 'actual': 'all 2 legs won',
                '_allClimbsBanked': 42,
                'legs': [{'title': 'Pitt +10.5'}, {'title': 'Northwestern +12.5'}],
                'ladder': {'run': 1, 'step': 2, 'stake': 75, 'payout': 117, 'banked': 19,
                           'bankThisWin': 23, 'bankedAfter': 42, 'nextStake': 94, 'totalAfter': 136,
                           'start': 50, 'goal': 1000}}
        with self.felt():
            win = pick_card.ladder_result_svg(rung)
            complete = pick_card.ladder_result_svg(dict(
                rung, ladder=dict(rung['ladder'], step=5, stake=675, payout=850, banked=150,
                                  bankThisWin=170, bankedAfter=320, nextStake=680, totalAfter=1000)))
        self.assertEqual(win.count('data-zone="leg-mark" data-result="win"'), 2)
        self.assertNotIn('data-zone="leg-mark" data-result="unknown"', win)
        self.assertIn('STEP 3 · $94 RIDES', win)
        for value in ('CLIMB COMPLETE', '$50 → $1,000', 'FINAL BANK $320', 'NEXT $50 CLIMB'):
            self.assertIn(value, complete)

    def test_push_and_void_climb_cards_keep_the_same_step_and_stake(self):
        rung = {'id': 'c', 'parlayType': 'ladder', 'actual': 'legs: push, push',
                '_allClimbsBanked': 42,
                'legs': [{'title': 'Pitt +10.5'}, {'title': 'Northwestern +12.5'}],
                'ladder': {'run': 2, 'step': 2, 'stake': 75, 'payout': 75, 'banked': 19,
                           'start': 50, 'goal': 1000}}
        with self.felt():
            push = pick_card.ladder_result_svg(dict(rung, result='push'))
            void = pick_card.ladder_result_svg(dict(rung, result='void', actual='legs: void, void'))
        self.assertIn('– PUSH', push)
        self.assertIn('STEP 2 AGAIN · $75 RIDES', push)
        self.assertIn('$75 RETURNS', push)
        self.assertIn('– VOID', void)
        self.assertNotIn('– PUSH', void)
        self.assertIn('STEP 2 AGAIN · $75 RIDES', void)

    def test_multi_row_research_never_silently_slices_public_copy(self):
        rows = []
        for index in range(3):
            title = ("Marvin Harrison Jr. over 64.5 receiving yards" if index == 0 else
                     f'Full player number {index} under 38.5 receiving yards')
            rows.append({'title': title,
                         'price': f'−114 theScore Bet row {index}',
                         'metric': f'8/10 exact-line trend over the complete last 10 games row {index}',
                         'hits': 8, 'games': 10,
                         'opponentAbbr': 'GAST' if index == 0 else 'Opponent',
                         'statLabel': 'receiving yards',
                         'matchup': {'value': 37.25, 'rank': 4, 'of': 134,
                                     'pos': 'TE', 'stat': 'receiving yards'},
                         'scriptRisk': index == 0, 'projectedMargin': -17.5 if index == 0 else 3,
                         'detail': (f'Opponent allows 37.25 receiving yards a game to tight ends, 4th of 134 row {index}'
                                    + (' · GAST projected 17.5-pt dog' if index == 0 else ''))})
        choice = {'kind': 'matchup', 'title': 'MATCHUP TRENDS', 'rows': rows}
        with self.felt():
            card = research_art.svg(choice)
        self.valid(card)
        for row in rows:
            for word in row['title'].split():
                self.assertIn(word, card)
            self.assertIn(row['price'], card)
        self.assertEqual(card.count('data-zone="research-title"'), 3)
        self.assertEqual(card.count('data-zone="research-price"'), 3)
        self.assertIn('Over 64.5 in 8 of his last 10 games', card)
        self.assertIn('Under 38.5 in 8 of his last 10 games', card)
        self.assertNotIn('exact-line trend', card)
        self.assertIn('GAME-SCRIPT CAUTION · GAST projected 17.5-pt dog', card)
        root = ET.fromstring(card)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        titles = root.findall(".//s:g[@data-zone='research-title']/s:text", namespace)
        self.assertTrue(all(float(node.attrib['font-size']) >= 32 for node in titles))
        cautions = root.findall(".//s:g[@data-zone='research-detail']/s:text", namespace)
        self.assertEqual(['GAME-SCRIPT CAUTION · GAST projected 17.5-pt dog'],
                         [node.text for node in cautions])

    def test_single_row_research_keeps_full_title_caution_and_fits_defense(self):
        title = 'Khijohnn Cummings-Coleman over 64.5 receiving yards'
        detail = 'GAME-SCRIPT CAUTION · projected to lose by 18 points'
        defense = {'rank': 134, 'of': 134, 'pos': 'WR', 'stat': 'pass attempts',
                   'value': 47.2, 'supports': True}
        choice = {'kind': 'matchup', 'title': 'MATCHUP TRENDS',
                  'rows': [{'title': title, 'price': '−110 FanDuel', 'hits': 8, 'games': 10,
                            'detail': detail, 'opponentAbbr': 'SOUTHERN MISSISSIPPI',
                            'statLabel': 'pass attempts', 'matchup': defense,
                            'matchupLabel': 'ARIZONA at SOUTHERN MISSISSIPPI'}]}
        with self.felt():
            card = research_art.svg(choice, {0: PHOTO_URI})
        self.valid(card)
        for word in title.split():
            self.assertIn(word, card)
        self.assertIn(detail, card)
        self.assertIn('data-zone="research-defense"', card)
        self.assertIn('data-zone="research-detail"', card)
        root = ET.fromstring(card)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        defense_nodes = root.findall(".//s:g[@data-zone='research-defense']/s:text", namespace)
        self.assertEqual(' '.join(node.text for node in defense_nodes),
                         'SOUTHERN MISSISSIPPI allows 47.2 pass attempts a game to WRs, 134th of 134')
        title_nodes = root.findall(".//s:g[@data-zone='research-title']/s:text", namespace)
        self.assertLessEqual(len(title_nodes), 3)
        self.assertEqual(' '.join(node.text for node in title_nodes), title)
        self.assertIn('data-zone="research-photo"', card)

        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / 'measure-research.html'
            page.write_text('''<!doctype html><meta charset="utf-8"><body>''' + card + '''
<script>
document.fonts.ready.then(() => {
  const ring = document.querySelector('[data-zone="research-photo"] circle:last-child').getBBox();
  const title = [...document.querySelectorAll('[data-zone="research-title"] text')].map((node) => {
    const box = node.getBBox();
    return {text: node.textContent, left: box.x, top: box.y,
            right: box.x + box.width, bottom: box.y + box.height};
  });
  document.body.textContent = JSON.stringify({ring: {left: ring.x, top: ring.y,
    right: ring.x + ring.width, bottom: ring.y + ring.height}, title});
  document.body.dataset.measured = '1';
});
</script></body>''', encoding='utf-8')
            dom = chrome_dump(page, Path(folder) / 'chrome-profile')
        match = re.search(r'<body data-measured="1">(.*?)</body>', dom, re.S)
        self.assertIsNotNone(match, dom[-500:])
        measured = json.loads(html.unescape(match.group(1)))
        for row in measured['title']:
            vertically_overlaps = (row['top'] < measured['ring']['bottom']
                                   and row['bottom'] > measured['ring']['top'])
            if vertically_overlaps:
                self.assertLessEqual(row['right'], measured['ring']['left'] - 10, measured)

    def test_season_board_gives_exact_lines_a_readable_full_width_row(self):
        rows = [{'title': name, 'price': line, 'metric': '3/3 this season',
                 'detail': '−110 FanDuel · 2026 regular season'}
                for name, line in (('Adam Damante', 'Under 211.5 passing yards'),
                                   ('Ted Hurst III', 'Over 21.5 receiving yards'),
                                   ('Ja\'Marr Chase', 'Over 84.5 receiving yards'))]
        with self.felt():
            card = research_art.svg({'kind': 'season', 'title': 'TREND BOARD', 'rows': rows})
        self.valid(card)
        root = ET.fromstring(card)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        prices = root.findall(".//s:g[@data-zone='research-price']/s:text", namespace)
        self.assertEqual(len(prices), 3)
        self.assertTrue(all(float(node.attrib['font-size']) >= 32 for node in prices))
        self.assertTrue(all(node.attrib['x'] == '98' for node in prices))
        for row in rows:
            self.assertIn(row['price'], card)

    def test_felt_projection_sheet_is_native_and_uses_the_real_date(self):
        game = {'id': 'g', 'league': 'CFB', 'week': 6,
                'away': {'abbr': 'NMSU'}, 'home': {'abbr': 'FIU'},
                'v2': {'away': 20.1, 'home': 27.3, 'margin': 7.2, 'total': 47.4},
                'market': {'spread': -6.5, 'total': 48.5},
                'value': {'spread': {'side': 'home', 'line': -3.5, 'odds': 100,
                                     'book': 'theScore Bet', 'edge': 3.8, 'chance': .538, 'needs': .5,
                                     'tier': 'lean', 'thin': False,
                                     'observedAt': '2026-10-10T13:00:00Z'}}}
        from datetime import date
        with self.felt():
            card = sheet.svg([game], 'CFB', date(2026, 10, 10), 6,
                             now=datetime(2026, 10, 10, 14, tzinfo=timezone.utc))
        self.valid(card)
        self.assertIn('Saturday, October 10', card)
        self.assertIn('LIKE #1  FIU -3.5 +100 theScore Bet', card)
        self.assertIn('20.1–27.3', card)
        self.assertIn('rings name the lines we like · watches, not picks', card)
        self.assertIn('theScore Bet', card)
        self.assertNotIn('ESPN', card)
        self.assertNotIn('Mint:', card)
        self.assertNotIn('January 3', card)
        self.assertIn(f'fill="{felt_cards.CHALK}"', card)

    def test_compact_projection_sheet_keeps_ring_caution_and_text_inside_tiles(self):
        from datetime import date
        template = {'league': 'CFB', 'week': 6,
                    'away': {'abbr': 'UNC'}, 'home': {'abbr': 'PITT'},
                    'v2': {'away': 19.2, 'home': 31.1, 'margin': 11.9, 'total': 50.3},
                    'lean': {'spread': 11.1},
                    'market': {'spread': -3.5, 'total': 49.5},
                    'value': {}}
        games = []
        for index in range(16):
            row = copy.deepcopy(template)
            row['id'] = f'g{index}'
            row['away']['abbr'] = 'HAW' if index == 15 else f'A{index}'
            row['home']['abbr'] = 'ASU' if index == 15 else f'H{index}'
            games.append(row)
        games[0]['away']['abbr'] = 'UNC'
        games[0]['home']['abbr'] = 'PITT'
        games[0]['value']['spread'] = {'side': 'home', 'line': -3.5, 'odds': -105,
                                             'book': 'theScore Bet', 'edge': 4.2, 'chance': .552,
                                             'needs': .512, 'tier': 'lean', 'thin': False,
                                             'observedAt': '2026-10-10T13:00:00Z'}
        with self.felt():
            card = sheet.svg(games, 'CFB', date(2026, 10, 10), 6,
                             now=datetime(2026, 10, 10, 14, tzinfo=timezone.utc))
        self.valid(card)
        self.assertIn('LIKE #1  PITT -3.5 −105 theScore Bet', card)
        self.assertIn('11.1-PT GAP · CAUTION', card)
        self.assertIn(f'fill="{felt_cards.KOOKD}"', card)
        self.assertIn(f'>19.2–31.1</text>', card)
        self.assertNotIn('>SCORE<', card)
        self.assertNotIn('>BR<', card)
        self.assertLessEqual(felt_cards.fit_size('SPREAD  OUR PITT −11.9  ·  MARKET PITT -3.5 −105 theScore Bet',
                                                 23, 430), 23)
        card_h = (1198 - 250) / 8 - 4
        geometry = felt_cards.sheet_row_geometry(card_h, True)
        self.assertGreaterEqual(geometry['spread'] - geometry['caution'], geometry['cautionSize'] + 7)
        self.assertGreaterEqual(geometry['total'] - geometry['spread'], 21)
        self.assertLessEqual(geometry['total'] + 8, card_h)

    def test_eleven_and_twelve_game_sheet_cautions_stay_inside_their_tiles(self):
        for games in (11, 12):
            rows = (games + 1) // 2
            card_h = (1198 - 250) / rows - 12
            geometry = felt_cards.sheet_row_geometry(card_h, True)
            self.assertGreater(geometry['spread'], geometry['caution'])
            self.assertGreater(geometry['total'], geometry['spread'])
            self.assertLessEqual(geometry['total'] + 8, card_h)
            self.assertLessEqual(geometry['caution'] + geometry['cautionSize'], card_h)

    def test_projection_sheet_geometry_stays_inside_tiles_for_every_supported_row_count(self):
        for rows in range(1, 9):
            gap = 4 if rows >= 7 else 12
            card_h = (1198 - 250) / rows - gap
            with self.subTest(rows=rows, card_h=card_h):
                geometry = felt_cards.sheet_row_geometry(card_h, True)
                self.assertLessEqual(geometry['total'], card_h - 8)
                self.assertGreater(geometry['total'], geometry['spread'])
                if geometry['caution'] < geometry['spread']:
                    self.assertGreaterEqual(geometry['spread'] - geometry['caution'],
                                            geometry['cautionSize'] + 7)
                else:
                    self.assertGreaterEqual(geometry['caution'] - geometry['total'], 20)
                    self.assertLessEqual(geometry['caution'] + geometry['cautionSize'], card_h)

    def test_four_letter_team_fallback_fits_its_badge(self):
        chip = felt_cards.team_chip(40, 40, {'abbr': 'NMSU'}, 34)
        self.assertIn('font-size="19"', chip)


if __name__ == '__main__':
    unittest.main()
