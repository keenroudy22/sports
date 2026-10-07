"""Render every approved social-card category with the review-only felt override."""
import argparse
import copy
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_card
import felt_cards
import gates
import ladder
import receipts
import record_scope
import research_art
import research_posts
import sheet
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / 'site' / 'data' / 'app' / name).read_text(encoding='utf-8'))


def game_shape(game):
    def team(row):
        row = dict(row or {})
        row.setdefault('abbreviation', row.get('abbr'))
        return row
    return dict(game, away=team(game.get('away')), home=team(game.get('home')))


def review_matchup_choice(games, details, teams):
    """Build a three-row layout fixture only from current stored lines and defense data."""
    rows, used = [], set()
    for game in games:
        detail = details.get(game['id']) or {}
        for line in [*(detail.get('favoriteLines') or []), *(detail.get('modelReads') or [])]:
            key = line.get('sourceId') or line.get('id') or (game['id'], line.get('title'))
            history = ((line.get('history') or {}).get('last') or {})
            matchup = research_posts.defense_context(line, teams.get(game.get('league')))
            if key in used or history.get('games', 0) < 3 or not matchup or not matchup['supports'] \
                    or not isinstance(line.get('odds'), (int, float)) \
                    or line.get('book') not in research_posts.PUBLIC_BOOKS:
                continue
            used.add(key)
            stat = research_posts.STAT_LABEL.get(matchup['stat'], str(matchup['stat']))
            rows.append({'league': game.get('league'), 'gameId': game['id'],
                         'title': line.get('title'), 'athleteId': line.get('athleteId'),
                         'price': f"{research_posts.price(line.get('odds'))} {research_posts.book_short(line.get('book'))}",
                         'metric': f"{history.get('hits', 0)}/{history['games']} exact-line trend",
                         'detail': (f"{line.get('opponentAbbr') or 'Opponent'} allows {matchup['value']:g} "
                                    f"{stat}/game to {matchup['pos']}s · #{matchup['rank']} of {matchup['of']}"),
                         'score': (history.get('rate', 0), history['games'])})
    rows.sort(key=lambda row: (-row['score'][0], -row['score'][1], row['title']))
    return {'kind': 'matchup', 'title': 'MATCHUP TRENDS',
            'kicker': 'EXACT LINE + OPPONENT DEFENSE', 'rows': rows[:3]}


def review_season_choice(games, details):
    """Build a three-row season-board fixture only from current stored season trends."""
    rows, used = [], set()
    for game in games:
        for row in (details.get(game['id']) or {}).get('seasonTrends') or []:
            key = (row.get('league'), row.get('athleteId'))
            if key in used or row.get('kind') != 'main' or row.get('games', 0) < 3 \
                    or not isinstance(row.get('odds'), (int, float)) or row.get('book') not in research_posts.PUBLIC_BOOKS:
                continue
            used.add(key)
            rows.append({**row, 'title': row.get('player'), 'price': row.get('title'),
                         'metric': f"{row.get('hits', 0)}/{row['games']} this season · {row.get('rate', 0):g}% historical",
                         'detail': f"{research_posts.price(row['odds'])} {row['book']} · {row.get('season')} regular season"})
    rows.sort(key=lambda row: (-row.get('hits', 0) / row['games'], -row['games'], str(row.get('title'))))
    return {'kind': 'season', 'title': 'TREND BOARD',
            'kicker': 'CURRENT MAIN LINES · FULL-SEASON HISTORY', 'rows': rows[:3]}


def render(out):
    os.environ['KEENROUDY_CARD_THEME'] = 'felt'
    today, record = load('today.json'), load('record.json')
    now = datetime.fromisoformat(str(today.get('generatedAt')).replace('Z', '+00:00')) if today.get('generatedAt') else datetime.now(timezone.utc)
    games = {row['id']: game_shape(row) for row in today.get('games') or []}
    picks = today.get('picks') or []
    straight = [row for row in picks if not row.get('legs')]
    prop = next(row for row in straight if row.get('athleteId'))
    game_pick = next(row for row in straight if not row.get('athleteId'))
    ticket = next(row for row in picks if row.get('parlayType') not in (None, 'ladder') and row.get('legs'))
    climb = next(row for row in picks if row.get('parlayType') == 'ladder')
    out.mkdir(parents=True, exist_ok=True)
    made = []

    def save(name, svg):
        path = out / name
        pick_card.render(svg, path, size=pick_card.svg_size(svg))
        made.append(path)

    for name, row, featured in (('best-bet-player-prop.png', prop, True),
                                ('best-bet-game-line.png', game_pick, False)):
        game = games.get(row.get('gameId'))
        season = record_scope.summary(record.get('picks') or [], row.get('publishedAt') or now)
        save(name, pick_card.modern_svg(row, game, record=season,
                                        featured=featured, art=pick_card.artwork(row, game)))

    save('fun-ticket.png', pick_card.ticket_svg(
        ticket, games.get(ticket.get('gameId')), art=pick_card.ticket_art(ticket, games)))
    ctx = gates.Stores().as_of(now)
    climb_state = ladder.state(ctx.first, ctx.latest)
    save('climb-open.png', pick_card.ladder_svg(dict(climb, result=None,
                                                     _allClimbsBanked=climb_state['saved'])))
    climb_wins = [row for row in record.get('picks') or []
                  if row.get('parlayType') == 'ladder' and row.get('result') == 'win']
    climb_win = next(row for row in climb_wins if row.get('actual') == 'all 2 legs won')
    save('climb-result.png', pick_card.ladder_result_svg(dict(
        climb_win, _allClimbsBanked=ladder.saved_through(ctx.first, ctx.latest, climb_win['id']))))
    climb_loss = max((row for row in record.get('picks') or []
                      if row.get('parlayType') == 'ladder' and row.get('result') == 'loss'),
                     key=lambda row: row.get('publishedAt') or '')
    save('climb-loss.png', pick_card.ladder_result_svg(dict(
        climb_loss, _allClimbsBanked=ladder.saved_through(ctx.first, ctx.latest, climb_loss['id']))))
    completed = copy.deepcopy(climb_win)
    completed['ladder'].update(step=5, stake=675, payout=850, banked=150,
                               bankThisWin=170, bankedAfter=320, nextStake=680, totalAfter=1000)
    completed['_allClimbsBanked'] = 320
    save('climb-complete.png', pick_card.ladder_result_svg(completed))
    pushed = copy.deepcopy(climb_win)
    pushed.update(result='push', actual='legs: push, push', _allClimbsBanked=42)
    save('climb-push.png', pick_card.ladder_result_svg(pushed))
    voided = copy.deepcopy(pushed)
    voided.update(result='void', actual='legs: void, void')
    save('climb-void.png', pick_card.ladder_result_svg(voided))

    history = receipts.card_history(ctx.first, ctx.latest, ctx.games, now)
    receipt = max((row for row in history if str(row.get('key') or '').startswith('receipt:day:')),
                  key=lambda row: (len(row.get('rows') or []), row.get('when') or ''))
    save('receipt.png', pick_card.receipt_svg(receipt))
    weekly = next((row for row in history
                   if str(row.get('key') or '').startswith('receipt:week:')), None)
    if weekly is None:
        review_day = eastern_date(now)
        wednesday = review_day + timedelta(days=(receipts.WEEKDAY - review_day.weekday()) % 7)
        weekly = receipts.week_receipt(wednesday, ctx.first, ctx.latest, ctx.games,
                                       receipts.counted(ctx.first, ctx.latest), now)
    if not weekly:
        raise RuntimeError('the current stored data could not supply the weekly receipt review')
    save('receipt-weekly.png', pick_card.receipt_svg(weekly))
    six_best = next(row for row in history
                    if sum((len(item) < 4 or item[3] in ('player', 'team')) for item in row.get('rows') or []) >= 6)
    save('receipt-six-best-bets.png', pick_card.receipt_svg(six_best))
    void = next(row for row in record.get('picks') or [] if row.get('result') == 'void')
    save('receipt-void.png', pick_card.receipt_svg({
        'title': '0-0', 'when': 'Void example from the public record',
        'rows': [('void', void.get('displayTitle') or void.get('title'), void.get('actual'), 'player')],
    }))

    cards = list(games.values())
    details = research_posts.details_for(cards)
    teams = research_posts.teams_for(cards)
    choice = (research_posts.matchup_candidate(cards, details, now, teams)
              or research_posts.season_candidate(cards, details, now)
              or research_posts.scorer_candidate(cards, details, now))
    if not choice:
        raise RuntimeError('no real stored research choice is available for the card review')
    choice.update(day=eastern_date(now))
    research_artwork = {}
    for index, row in enumerate(choice.get('rows') or []):
        game = games.get(row.get('gameId'))
        art = pick_card.artwork({'athleteId': row.get('athleteId'), 'league': row.get('league')}, game) if row.get('athleteId') else None
        if art and art.get('uri'):
            research_artwork[index] = art['uri']
    save('research.png', research_art.svg(choice, research_artwork))
    matchup_three = review_matchup_choice(cards, details, teams)
    season_three = review_season_choice(cards, details)
    if len(matchup_three['rows']) != 3 or len(season_three['rows']) != 3:
        raise RuntimeError('the current stored data could not supply both requested three-row review fixtures')
    save('research-matchup-3-row.png', research_art.svg(matchup_three))
    save('research-season-3-row.png', research_art.svg(season_three))

    dates = Counter(eastern_date(gates.when(row['kickoff'])) for row in today.get('games') or []
                    if row.get('league') == 'CFB' and row.get('state', 'pre') == 'pre')
    sheet_day = max(dates, key=lambda day: (len(sheet.pick_games(today.get('games') or [], 'CFB', day)), day))
    sheet_games = sheet.pick_games(today.get('games') or [], 'CFB', sheet_day)
    logos = {}
    for row in sheet_games:
        for side in ('away', 'home'):
            uri = sheet.logo_uri(row, side)
            if uri:
                logos[row['id'], side] = uri
    # Review the stored board as it existed when its newest quote was captured.
    # That verifies the ring treatment without changing or inventing a price.
    observed = []
    for row in sheet_games:
        for value in (row.get('value') or {}).values():
            if value.get('observedAt'):
                observed.append(gates.when(value['observedAt']))
    sheet_now = max(observed) + timedelta(minutes=1) if observed else now
    save('projection-sheet.png', sheet.svg(sheet_games, 'CFB', sheet_day,
                                            sheet_games[0].get('week') if sheet_games else None, logos, sheet_now))
    caution_game = next((row for row in sheet_games
                         if (row.get('away') or {}).get('abbr') == 'UNC'
                         and (row.get('home') or {}).get('abbr') == 'PITT'), None)
    if caution_game:
        value = dict((caution_game.get('value') or {}).get('spread') or {})
        value['collegeGapCaution'] = 11.1
        watch = {caution_game['id']: (1, 'spread', sheet.watch_label(caution_game, 'spread', value), value)}
        save('projection-sheet-caution.png', felt_cards.projection_sheet(
            sheet_games, 'CFB', sheet_day, sheet_games[0].get('week') if sheet_games else None,
            logos, watch))
    return made


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for path in render(args.out):
        print(path)
