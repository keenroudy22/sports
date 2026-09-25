"""The plays as an RSS feed: the public record of what goes to @keenkooks, and a source for any relay. Stdlib only.

The site publishes site/data/feed.xml: one item per play the desk posts, in the same words
scripts/x_post.py drafts (the kind of play, the play at its price, our number, one plain reason). X gets
plays only: player props, team props and the day's fun parlay. Every open play gets its card as soon as
it is published, rendered by the machine's browser into site/data/cards/ (GitHub's runners have Chrome;
the Mac has Chrome), so the desk can attach it the moment it schedules the post. Neither the feed nor the
cards are committed; the hosted workflow builds and deploys them with the rest of the page payloads.

A play appears in the feed only inside its posting window: on the day of its game, Eastern, from 9:00 AM
until 45 minutes before kickoff, and only while it is still open. Nothing stale can be posted from it.

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
ABOUT = 'Player props, team props and fun parlays from keenroudy.com/sports, graded in public. Entertainment only.'


def postable(pick):
    """Player props, team props and the day's fun parlay: favorites, model leans, prop leans and the longshot."""
    return pick.get('favorite') is True or bool(pick.get('modelLean')) or bool(pick.get('legs')) or pick.get('parlayType') == 'longshot'


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
        # A ticket spans several games; its window follows the first kickoff.
        starts = sorted(games[g]['kickoff'] for g in (pick.get('gameIds') or []) if g in games)
        game = games.get((pick.get('gameIds') or [None])[0])
        if not published or not game or not starts or not in_window(starts[0], now):
            continue
        if merged.get('expiresAt') and gates.when(merged['expiresAt']) <= now - timedelta(hours=12):
            continue        # a quote that expired half a day ago is not this morning's play
        text = x_post.draft(merged, game)
        if x_post.guard(text, merged, x_post.load_reasons().get(key)):
            continue
        local = now.astimezone(gates.EASTERN)
        opened = local.replace(hour=WINDOW_OPENS[0], minute=WINDOW_OPENS[1], second=0, microsecond=0).astimezone(timezone.utc)
        items.append({'guid': key, 'title': x_post.kind_label(merged) + ': ' + str(merged.get('title')),
                      'text': text, 'link': f'{SITE}#pick/{key}', 'pubDate': max(gates.when(published), opened),
                      'pick': merged, 'game': game, 'side': player_side(merged, game, player_team)})
    return items


def card_items(first, latest, games, now, player_team=None):
    """Every open, postable play whose first game has not started: the plays that may still need a card."""
    items = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if pick.get('historicalImport') or not postable(merged) or merged.get('result') or merged.get('entryNote'):
            continue
        if (merged.get('status') or 'active') != 'active':
            continue
        starts = sorted(games[g]['kickoff'] for g in (pick.get('gameIds') or []) if g in games)
        game = games.get((pick.get('gameIds') or [None])[0])
        if not game or not starts or gates.when(starts[0]) <= now:
            continue
        items.append({'guid': key, 'pick': merged, 'game': game, 'side': player_side(merged, game, player_team)})
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
        if 'pick' not in item and 'receipt' not in item:
            continue
        path = Path(folder) / f"{item['guid']}.png"
        try:
            if not path.exists():
                if 'receipt' in item:
                    pick_card.render(pick_card.receipt_svg(item['receipt']), path)
                else:
                    pick_card.render(pick_card.svg(item['pick'], item['game'], player_side=item.get('side'), featured=item.get('featured', False)), path)
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
    # X gets plays only (the owner's call, 2026-09-23), so the feed that mirrors it does too.
    items = pick_items(ctx.first, ctx.latest, ctx.games, now, ctx.player_team)
    # A card for every open play as soon as it is published, not only inside its posting window: the desk
    # schedules the post the moment the card is live, and never posts without one.
    import receipts
    ready = [{'guid': r['card'], 'receipt': r} for r in receipts.ready(ctx.first, ctx.latest, ctx.games, x_post.load_log(), now)]
    plays = card_items(ctx.first, ctx.latest, ctx.games, now, ctx.player_team)
    import featured
    potd = featured.of_day(eastern_date(now).isoformat())
    # The Pick of the Day gets a card of its own, under its own name, so a post can never carry a stale copy.
    plays += [dict(item, guid=f"{item['guid']}-potd", featured=True) for item in plays if item['guid'] == potd]
    cards = render_cards(plays + ready, cards_folder, log) if with_cards else {}
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
