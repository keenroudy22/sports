"""Render sample felt cards from real published data. Python standard library + the desk's renderer.

  python3 redesign/social/render_samples.py            # live site data, saved to fixtures/ for repeatable renders
  python3 redesign/social/render_samples.py --offline  # reuse fixtures/
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
import cards  # noqa: E402

LIVE = 'https://keenroudy.com/sports/data/'
FONTS = ('<style>@import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700'
         '&amp;family=DM+Sans:wght@600;700&amp;display=block");</style>')
STAT_WORD = {'recYds': 'rec yds', 'rushYds': 'rush yds', 'passYds': 'pass yds', 'rec': 'receptions', 'car': 'carries'}


def load(name, offline):
    path = HERE / 'fixtures' / name.replace('/', '-')
    if offline:
        return json.loads(path.read_text())
    request = urllib.request.Request(LIVE + name, headers={'User-Agent': 'Mozilla/5.0 kookn-redesign-samples'})
    data = json.loads(urllib.request.urlopen(request, timeout=30).read())
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def when(iso):
    d = datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(timezone.utc)
    # Eastern (EDT, UTC-4) is close enough for a sample label.
    hour = (d.hour - 4) % 24
    return f"{d.strftime('%a')} {hour % 12 or 12}:{d.minute:02d} {'PM' if hour >= 12 else 'AM'} ET"


def main(offline=False):
    import pick_card
    today = load('app/today.json', offline)
    trends = load('app/trends.json', offline)
    games = {g['id']: g for g in today['games']}
    picks = today['picks']
    straight = [p for p in picks if p.get('kind') != 'parlays' and not p.get('legs')]
    settled = [p for p in straight if p.get('result') in ('win', 'loss', 'push')]
    season = f"{sum(p['result'] == 'win' for p in settled)}–{sum(p['result'] == 'loss' for p in settled)}"
    out = HERE / 'samples'
    out.mkdir(exist_ok=True)
    made = []

    def save(name, svg):
        pick_card.render(svg.replace('viewBox="0 0 1080 1350">', 'viewBox="0 0 1080 1350">' + FONTS, 1), out / name, size=(1080, 1350))
        made.append(name)

    open_pick = next((p for p in straight if not p.get('result') and (p.get('probabilityAtPublication') or {}).get('chance')), None)
    def art_for(pick):
        game = games.get(pick.get('gameId'))
        if not game:
            return None
        mapped = {'league': game['league'], 'away': {'abbreviation': game['away']['abbr'], 'id': game['away']['id']},
                  'home': {'abbreviation': game['home']['abbr'], 'id': game['home']['id']}}
        return pick_card.artwork(pick, mapped)
    if open_pick:
        open_pick = {**open_pick, '_when': when(open_pick['kickoff'])}
        save('play-card.png', cards.play_card(open_pick, games.get(open_pick.get('gameId')), season, featured=False, art=art_for(open_pick)))
    game_pick = next((p for p in straight if not p.get('result') and not p.get('athleteId') and p.get('gameId') in games), None)
    if game_pick:
        game_pick = {**game_pick, '_when': when(game_pick['kickoff'])}
        save('play-card-game-line.png', cards.play_card(game_pick, games.get(game_pick['gameId']), season, art=art_for(game_pick)))
    def et_day(iso):
        d = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return (d.timestamp() - 4 * 3600)
    from datetime import timedelta
    et = lambda iso: (datetime.fromisoformat(iso.replace('Z', '+00:00')) - timedelta(hours=4)).date()
    last_day = max(et(p['kickoff']) for p in settled if p.get('kickoff'))
    day_rows = [p for p in settled if p.get('kickoff') and et(p['kickoff']) == last_day][:5]
    for p in day_rows:
        game = games.get(p.get('gameId')) or {}
        if game.get('completed') and not p.get('athleteId'):
            p['_final'] = f"Final {game['away']['abbr']} {game['away'].get('score')}, {game['home']['abbr']} {game['home'].get('score')}"
    save('receipt.png', cards.receipt_card(last_day.strftime('%A, %b %-d'), day_rows, season))
    fun = next((p for p in sorted(picks, key=lambda p: p.get('publishedAt') or '', reverse=True) if p.get('kind') == 'parlays' and p.get('parlayType') != 'ladder' and p.get('legs')), None)
    if fun:
        save('fun-ticket.png', cards.fun_ticket_card({**fun, '_hook': f"{fun.get('league', '')} longshot"}))
    priced = [r for r in trends.get('rows', []) if r.get('kind') == 'main' and r.get('odds') is not None and r.get('games', 0) >= 3 and r.get('history')]
    if priced:
        row = max(priced, key=lambda r: (r['hits'] / r['games'], r['games']))
        save('research.png', cards.research_card({**row, 'statWord': STAT_WORD.get(row.get('stat'), row.get('stat'))}))
    rung = next((p for p in sorted(picks, key=lambda p: p.get('publishedAt') or '', reverse=True) if p.get('parlayType') == 'ladder'), None)
    if rung:
        info = rung.get('ladder') or {}
        save('climb.png', cards.climb_card(rung, info.get('run', 1), info.get('step', 1), info.get('stake', 50), info.get('payout', 0), info.get('banked', 0)))
    return made


if __name__ == '__main__':
    print('rendered:', ', '.join(main('--offline' in sys.argv)))
