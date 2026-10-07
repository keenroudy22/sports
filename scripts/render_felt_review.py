"""Render every approved social-card category with the review-only felt override."""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_card
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
    save('climb-result.png', pick_card.ladder_result_svg(dict(climb,
                                                              _allClimbsBanked=ladder.saved_through(ctx.first, ctx.latest, climb['id']))))

    history = receipts.card_history(ctx.first, ctx.latest, ctx.games, now)
    next_day = eastern_date(now) + timedelta(days=1)
    weekly = (receipts.week_receipt(next_day, ctx.first, ctx.latest, ctx.games,
                                    receipts.counted(ctx.first, ctx.latest), now)
              if next_day.weekday() == receipts.WEEKDAY else None)
    receipt = weekly or max(history, key=lambda row: (len(row.get('rows') or []), row.get('when') or ''))
    save('receipt.png', pick_card.receipt_svg(receipt))

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
    return made


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for path in render(args.out):
        print(path)
