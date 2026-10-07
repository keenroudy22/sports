"""Render real, unposted Kitchen Ticket previews for owner/Claude review only.

No record, site, Buffer, Discord, or production card is changed.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed
import featured
import gates
import pick_card
import receipts
import ticket_card
import ticket_climb_map
import ticket_kit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    stores = gates.Stores().as_of(now)
    items = feed.card_items(stores.first, stores.latest, stores.games, now, stores.player_team)
    potd_id = featured.of_day(now.astimezone(ZoneInfo('America/New_York')).date().isoformat())
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for item in items:
        if pick_card.play_kind(item['pick']) not in ('player', 'team'):
            continue
        pick = item['pick']
        art = pick_card.artwork(pick, item['game'], player_side=item.get('side'))
        if pick_card.play_kind(pick) == 'player' and pick.get('athleteId') and (art or {}).get('kind') != 'photo':
            print(f"WARNING: ESPN headshot unavailable after retry for {pick.get('id')}; badge fallback", file=sys.stderr)
        svg = ticket_card.straight_svg(pick, item['game'], featured=item.get('featured', False),
                                       player_side=item.get('side'), art=art)
        png = args.out / f"{item['guid']}.png"
        pick_card.render(svg, png)
        if png.stat().st_size > 5_000_000:
            raise SystemExit(f'{png.name} exceeds the X image limit')
        manifest.append({'id': item['guid'], 'title': pick.get('title'), 'athleteId': pick.get('athleteId'),
                         'photo': (art or {}).get('kind') == 'photo', 'path': str(png), 'bytes': png.stat().st_size})
        print(str(png))
        if item['guid'] == potd_id:
            hot = args.out / f"{item['guid']}-potd.png"
            hot_svg = ticket_card.straight_svg(pick, item['game'], featured=True,
                                               player_side=item.get('side'), art=art)
            pick_card.render(hot_svg, hot)
            manifest.append({'id': item['guid'], 'kind': 'potd', 'title': pick.get('title'),
                             'photo': (art or {}).get('kind') == 'photo', 'path': str(hot), 'bytes': hot.stat().st_size})
            print(str(hot))
    fun = sorted((pick for pick in stores.first.values()
                  if pick.get('parlayType') in ('longshot', 'lotto', 'easy') and pick.get('legs')
                  and all(isinstance(leg, dict) and isinstance(leg.get('odds'), (int, float)) for leg in pick['legs'])),
                 key=lambda pick: str(pick.get('publishedAt') or ''), reverse=True)
    if fun:
        pick = fun[0]
        png = args.out / f"{pick['id']}-fun.png"
        pick_card.render(ticket_card.fun_svg(pick, stores.games, stores.player_team), png)
        if png.stat().st_size > 5_000_000:
            raise SystemExit(f'{png.name} exceeds the X image limit')
        manifest.append({'id': pick['id'], 'title': pick.get('title'), 'kind': 'fun',
                         'path': str(png), 'bytes': png.stat().st_size})
        print(str(png))
    climb = stores.first.get('CFB-2026-W5-ladder-1003-fd')
    if climb:
        png = args.out / f"{climb['id']}-climb.png"
        pick_card.render(ticket_card.climb_svg(climb, stores.games, stores.player_team), png)
        manifest.append({'id': climb['id'], 'title': climb.get('title'), 'kind': 'climb',
                         'path': str(png), 'bytes': png.stat().st_size})
        print(str(png))
    # These are settled public plays; the cards are private previews, never posts.
    cooked_id = 'NFL-2026-W4-flournoy-over-3-5-rec-fd'
    if cooked_id in stores.first and cooked_id in stores.latest:
        won = dict(stores.first[cooked_id], **stores.latest[cooked_id])
        game = stores.games[won['gameIds'][0]]
        player_team_id = str(stores.player_team.get(str(won['athleteId'])))
        player_side = next((side for side in ('away', 'home') if str(game[side]['id']) == player_team_id), None)
        png = args.out / f'{cooked_id}-cooked.png'
        pick_card.render(ticket_card.cooked_svg(won, game, player_side=player_side), png)
        manifest.append({'kind': 'cooked', 'id': cooked_id, 'units': ticket_card.cooked_data(won, game, player_side=player_side)['units_won'],
                         'path': str(png), 'bytes': png.stat().st_size})
        print(str(png))
    from datetime import date
    day = date(2026, 10, 3)
    ids = receipts.counted(stores.first, stores.latest)
    day_rows = receipts.plays_between(stores.first, stores.latest, stores.games, ids, day, day)
    if day_rows:
        png = args.out / 'final-2026-10-03.png'
        pick_card.render(ticket_card.final_svg(day_rows, day.isoformat()), png)
        manifest.append({'kind': 'final', 'source': 'Oct 3 settled straight plays; fun and Climb tracked apart',
                         'path': str(png), 'bytes': png.stat().st_size})
        print(str(png))
    # Rehearse the no-headshot branch on a real recorded wager by simulating ESPN's photo 404.
    # The final manifest calls out the simulation; no record or live fetch is altered.
    fallback_id = 'NFL-2026-W4-flournoy-over-3-5-rec-fd'
    if fallback_id in stores.first:
        pick = stores.first[fallback_id]
        game = stores.games[pick['gameIds'][0]]
        player_team_id = str(stores.player_team.get(str(pick['athleteId'])))
        player_side = next((side for side in ('away', 'home') if str(game[side]['id']) == player_team_id), None)
        art = pick_card.artwork(pick, game, player_side=player_side,
                                fetch=lambda url: None if '/headshots/' in url else pick_card.fetch_data_uri(url))
        if art.get('kind') != 'logos':
            raise SystemExit('No-headshot fallback did not produce a team badge')
        print(f"WARNING: ESPN headshot unavailable after retry for {pick['id']}; badge fallback", file=sys.stderr)
        png = args.out / f'{fallback_id}-photo-unavailable-simulation.png'
        pick_card.render(ticket_card.straight_svg(pick, game, art=art, player_side=player_side), png)
        manifest.append({'kind': 'photo-fallback-simulation', 'id': fallback_id,
                         'path': str(png), 'bytes': png.stat().st_size})
        print(str(png))
    map_data = ticket_climb_map.from_ledger(stores.first, stores.latest)
    map_card = ticket_climb_map.climb_map(map_data)
    problems = ticket_kit.qa(map_card, 'climb-map')
    if problems:
        raise SystemExit('; '.join(problems))
    map_png = args.out / 'climb-map-real-ledger.png'
    pick_card.render(map_card.svg(), map_png)
    manifest.append({'kind': 'climb-map', 'source': 'ladder ledger plus labeled -160 plan',
                     'path': str(map_png), 'bytes': map_png.stat().st_size})
    print(str(map_png))
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if not manifest:
        raise SystemExit('No real open straight plays to preview')


if __name__ == '__main__':
    main()
