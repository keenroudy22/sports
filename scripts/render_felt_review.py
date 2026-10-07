"""Render every approved social-card category with the review-only felt override."""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_card
import research_art
import sheet

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
        save(name, pick_card.modern_svg(row, game, record=row.get('recordAsOfPublication'),
                                        featured=featured, art=pick_card.artwork(row, game)))

    save('fun-ticket.png', pick_card.ticket_svg(
        ticket, games.get(ticket.get('gameId')), art=pick_card.ticket_art(ticket, games)))
    save('climb-open.png', pick_card.ladder_svg(dict(climb, result=None)))
    save('climb-result.png', pick_card.ladder_result_svg(climb))

    settled = sorted((row for row in record.get('picks') or [] if row.get('result') in ('win', 'loss', 'push')),
                     key=lambda row: row.get('settledAt') or '', reverse=True)[:4]
    receipt = {'key': 'receipt:day:review', 'due': '2099-01-01T14:00:00Z',
               'title': f"{sum(r['result'] == 'win' for r in settled)}-{sum(r['result'] == 'loss' for r in settled)}",
               'when': 'Latest graded card',
               'rows': [(row['result'], row.get('displayTitle') or row.get('title'),
                         str(row.get('actual') or 'Final on the public record')) for row in settled]}
    save('receipt.png', pick_card.receipt_svg(receipt))

    choice = {'day': '2099-01-01', 'title': 'MATCHUP RESEARCH', 'kicker': 'EXACT MAIN LINE',
              'kind': 'matchup', 'accent': '#20C774',
              'rows': [{'title': prop.get('displayTitle') or prop['title'],
                        'price': f"{prop['odds']:+d} {prop['book']}",
                        'metric': 'Current-season history plus opponent context',
                        'detail': 'Research category · current price'}]}
    prop_art = pick_card.artwork(prop, games.get(prop.get('gameId'))) or {}
    save('research.png', research_art.svg(choice, {0: prop_art.get('uri')} if prop_art.get('uri') else {}))

    sheet_games = [row for row in today.get('games') or []
                   if row.get('league') == 'CFB' and row.get('v2') and (row.get('market') or {}).get('total') is not None
                   and not row.get('fcs')][:6]
    logos = {}
    for row in sheet_games:
        for side in ('away', 'home'):
            uri = sheet.logo_uri(row, side)
            if uri:
                logos[row['id'], side] = uri
    save('projection-sheet.png', sheet.svg(sheet_games, 'CFB', date(2099, 1, 3),
                                            sheet_games[0].get('week') if sheet_games else None, logos))
    return made


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for path in render(args.out):
        print(path)
