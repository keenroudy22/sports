"""The plays as an RSS feed, so a relay with its own X access can post them to @keenkooks. Stdlib only.

X meters posting through its API, so the desk does not post there itself. Instead the site publishes
site/data/feed.xml: one item per post the desk would make, in the same words scripts/x_post.py drafts
(a favorite or a lean with its label, price, our number against the line and the receipt link), plus a
game-day recap once the day is settled and the model scoreboard on Tuesday mornings. Each pick item
carries its card as an image enclosure, rendered by the machine's browser into site/data/cards/ when
one is available (GitHub's runners have Chrome; the Mac has Chrome). Neither the feed nor the cards
are committed; the hosted workflow builds and deploys them with the rest of the page payloads.

A relay posts new items once, when it first sees them. So a play appears in the feed only inside its
posting window: on the day of its game, Eastern, from 9:00 AM until 45 minutes before kickoff, and only
while it is still open. Not so early that the line is a day old, not so late that the game is on. A
recap appears once the day is settled and the scoreboard on Tuesday mornings. Nothing stale can be
posted from it.

  python scripts/feed.py [--out site/data/feed.xml] [--no-cards]
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import gates
import x_post
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'site' / 'data' / 'feed.xml'
CARDS = ROOT / 'site' / 'data' / 'cards'
SITE = x_post.SITE
WINDOW_OPENS = (9, 0)                # Eastern: no plays before 9:00 AM on game day
LEAD = timedelta(minutes=45)         # and none inside 45 minutes of kickoff
RECAP_DAYS = 3
TITLE = 'KeenRoudy Sports plays'
ABOUT = 'Model leans, prop leans and researched picks from keenroudy.com/sports, graded in public. Entertainment only.'


def postable(pick):
    return (pick.get('favorite') is True or bool(pick.get('modelLean'))) and not pick.get('legs') and not pick.get('parlayType')


def in_window(kickoff, now):
    """Game day, Eastern, from 9:00 AM until 45 minutes before kickoff."""
    start = gates.when(kickoff)
    local = now.astimezone(gates.EASTERN)
    if eastern_date(start) != local.date():
        return False
    opens = local.replace(hour=WINDOW_OPENS[0], minute=WINDOW_OPENS[1], second=0, microsecond=0)
    return local >= opens and start - now >= LEAD


def player_side(pick, game, player_team):
    """home or away for a prop's player, from the store's latest team for the athlete; None when unknown."""
    if not pick.get('athleteId') or not game:
        return None
    team = (player_team or {}).get(str(pick['athleteId']))
    if team == str(game['home']['id']):
        return 'home'
    if team == str(game['away']['id']):
        return 'away'
    return None


def pick_items(first, latest, games, now, player_team=None):
    items = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if pick.get('historicalImport') or not postable(merged) or merged.get('result') or merged.get('entryNote'):
            continue
        if (merged.get('status') or 'active') != 'active':
            continue
        published = pick.get('publishedAt')
        game = games.get((pick.get('gameIds') or [None])[0])
        if not published or not game or not in_window(game['kickoff'], now):
            continue
        if merged.get('expiresAt') and gates.when(merged['expiresAt']) <= now - timedelta(hours=12):
            continue        # a quote that expired half a day ago is not this morning's play
        text = x_post.draft(merged, game)
        if x_post.guard(text, merged):
            continue
        local = now.astimezone(gates.EASTERN)
        opened = local.replace(hour=WINDOW_OPENS[0], minute=WINDOW_OPENS[1], second=0, microsecond=0).astimezone(timezone.utc)
        items.append({'guid': key, 'title': x_post.kind_label(merged) + ': ' + str(merged.get('title')),
                      'text': text, 'link': f'{SITE}#pick/{key}', 'pubDate': max(gates.when(published), opened),
                      'pick': merged, 'game': game, 'side': player_side(merged, game, player_team)})
    return items


def recap_items(first, latest, games, now):
    items = []
    for back in range(RECAP_DAYS):
        day = (eastern_date(now) - timedelta(days=back)).isoformat()
        todays = []
        for key, pick in first.items():
            game = games.get((pick.get('gameIds') or [None])[0])
            if game and not pick.get('historicalImport') and eastern_date(gates.when(game['kickoff'])).isoformat() == day:
                todays.append(dict(pick, **latest.get(key, {})))
        if not todays or not all(p.get('result') for p in todays):
            continue
        text = x_post.recap(day, first, latest, games, now)
        if not text:
            continue
        settled_at = max((p.get('settledAt') for p in todays if p.get('settledAt')), default=None)
        items.append({'guid': f'recap:day:{day}', 'title': f"Kitchen's closed for {datetime.fromisoformat(day):%A}: the day's results",
                      'text': text, 'link': f'{SITE}#record', 'pubDate': gates.when(settled_at) if settled_at else now})
    return items


def scoreboard_item(scoreboard, now):
    local = now.astimezone(gates.EASTERN)
    tuesday = local.date() - timedelta(days=(local.weekday() - 1) % 7)
    due = datetime(tuesday.year, tuesday.month, tuesday.day, 8, 30, tzinfo=gates.EASTERN)
    if local < due:
        return None
    text = x_post.scoreboard_text(scoreboard)
    if not text:
        return None
    return {'guid': f'scoreboard:week:{tuesday.isoformat()}', 'title': 'Our number vs the closing line, season to date',
            'text': text, 'link': f'{SITE}#model', 'pubDate': due.astimezone(timezone.utc)}


def render_cards(items, folder=CARDS, log=print):
    """A PNG per pick item, when a browser is on the machine. Returns {guid: path}."""
    import pick_card
    if not pick_card.chrome_path():
        log('no browser for cards; the feed goes out without images')
        return {}
    out = {}
    for item in items:
        if 'pick' not in item:
            continue
        path = Path(folder) / f"{item['guid']}.png"
        try:
            if not path.exists():
                pick_card.render(pick_card.svg(item['pick'], item['game'], player_side=item.get('side')), path)
            out[item['guid']] = path
        except Exception as error:
            log(f"card for {item['guid']} not rendered: {error}")
    return out


def rss(items, cards, now, base=SITE):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">', '<channel>',
             f'<title>{escape(TITLE)}</title>', f'<link>{escape(base)}</link>', f'<description>{escape(ABOUT)}</description>',
             f'<atom:link href="{escape(base + "data/feed.xml")}" rel="self" type="application/rss+xml"/>',
             f'<lastBuildDate>{format_datetime(now)}</lastBuildDate>']
    for item in sorted(items, key=lambda i: i['pubDate'], reverse=True):
        lines += ['<item>', f"<title>{escape(item['title'])}</title>", f"<link>{escape(item['link'])}</link>",
                  f"<guid isPermaLink=\"false\">{escape(item['guid'])}</guid>", f"<pubDate>{format_datetime(item['pubDate'])}</pubDate>",
                  f"<description>{escape(item['text'])}</description>"]
        card = cards.get(item['guid'])
        if card is not None:
            size = Path(card).stat().st_size if Path(card).exists() else 0
            lines.append(f'<enclosure url="{escape(base + "data/cards/" + Path(card).name)}" length="{size}" type="image/png"/>')
        lines.append('</item>')
    lines += ['</channel>', '</rss>', '']
    return '\n'.join(lines)


def build(now=None, out=OUT, cards_folder=CARDS, with_cards=True, log=print):
    now = now or datetime.now(timezone.utc)
    stores = gates.Stores()
    ctx = stores.as_of(now)
    scoreboard = build_site.read(ROOT / 'site' / 'data' / 'scoreboard.json', {})
    items = pick_items(ctx.first, ctx.latest, ctx.games, now, ctx.player_team) + recap_items(ctx.first, ctx.latest, ctx.games, now)
    weekly = scoreboard_item(scoreboard, now)
    if weekly:
        items.append(weekly)
    cards = render_cards(items, cards_folder, log) if with_cards else {}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(rss(items, cards, now), encoding='utf-8')
    log(f'{len(items)} items in the feed ({sum(1 for i in items if "pick" in i)} plays, {len(cards)} cards) -> {out}')
    return items


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--no-cards', action='store_true')
    args = parser.parse_args(argv)
    build(out=Path(args.out), with_cards=not args.no_cards)
    return 0


if __name__ == '__main__':
    sys.exit(main())
