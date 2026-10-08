"""The plays as an RSS feed: the public record of what goes to @keenkooks, and a source for any relay. Stdlib only.

The site publishes site/data/feed.xml: a rolling 30-day public record of first publications and daily receipts.
X still gets only the existing postable categories through Buffer; it does not consume this feed. Every open play gets its card as soon as
it is published, rendered by the machine's browser into site/data/cards/ (GitHub's runners have Chrome;
the Mac has Chrome), so the desk can attach it the moment it schedules the post. Neither the feed nor the
cards are committed; the hosted workflow builds and deploys them with the rest of the page payloads.

A play appears in the feed only inside its posting window: on the day of its game, Eastern, from 9:00 AM
until 45 minutes before kickoff, and only while it is still open. Nothing stale can be posted from it.

  python scripts/feed.py [--out site/data/feed.xml] [--no-cards]
"""
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import gates
import pick_card
import x_post
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'site' / 'data' / 'feed.xml'
CARDS = ROOT / 'site' / 'data' / 'cards'
SITE = x_post.SITE
WINDOW_OPENS = (9, 0)                # Eastern: no plays before 9:00 AM on game day
LEAD = timedelta(minutes=45)         # and none inside 45 minutes of kickoff
RECAP_DAYS = 30
TITLE = "Kook'n"
ABOUT = 'Player props, game lines and fun parlays from keenroudy.com/sports, graded in public. Entertainment only.'
PNG = b'\x89PNG\r\n\x1a\n'


def posted_card_keys(log_book):
    """Card filenames already attached to confirmed X or Discord posts."""
    keys = set()
    for entry in log_book.get('posts') or []:
        if not isinstance(entry, dict) or not entry.get('card'):
            continue
        if not (entry.get('sentAt') or (entry.get('discord') or {}).get('sentAt')):
            continue
        key = entry.get('cardKey') or entry.get('id')
        if isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_.:-]+', key):
            keys.add(key)
    return keys


def restore_posted_cards(folder, keys, fetch=None):
    """Never regenerate a confirmed attachment under a newer theme after an Actions cache miss."""
    folder = Path(folder)
    fetch = fetch or (lambda url: urllib.request.urlopen(
        urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; KooknCardArchive/1.0)'}),
        timeout=12).read())
    for key in sorted(keys):
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+', str(key)):
            raise RuntimeError(f'invalid posted card name: {key!r}')
        path = folder / f'{key}.png'
        if path.exists():
            if not path.read_bytes().startswith(PNG):
                raise RuntimeError(f'posted card cache is not a PNG: {key}')
            continue
        try:
            data = fetch(f'{SITE}data/cards/{key}.png')
        except Exception as error:
            raise RuntimeError(f'posted card could not be restored without changing its art: {key}') from error
        if not isinstance(data, bytes) or not data.startswith(PNG) or not 64 <= len(data) <= 10 * 1024 * 1024:
            raise RuntimeError(f'posted card recovery returned invalid PNG bytes: {key}')
        folder.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.restore.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)


def play_title(pick):
    """Public RSS title from the priced, published item, not old internal category names."""
    kind = pick_card.play_kind(pick)
    if kind == 'ladder':
        step = (pick.get('ladder') or {}).get('step') or 1
        title = f"80/20 Climb · step {step} · {len(pick.get('legs') or [])} legs at {pick.get('book') or 'the posted book'}"
    elif kind == 'parlay':
        odds = pick.get('odds')
        price = f'{int(odds):+d}' if isinstance(odds, (int, float)) else 'posted price'
        title = f"Chef's Special {price}: {len(pick.get('legs') or [])} legs at {pick.get('book') or 'the posted book'}"
    else:
        title = x_post.kind_label(pick) + ': ' + str(pick.get('title'))
    return title + (' (replacement)' if pick.get('replacementOf') else '')


def postable(pick):
    """Player props, game lines and the day's fun parlay: favorites, model leans, prop leans and the longshot."""
    return pick.get('favorite') is True or bool(pick.get('modelLean')) or bool(pick.get('legs')) or pick.get('parlayType') == 'longshot'


def in_window(kickoff, now, league=None):
    """Game day, Eastern, from 9:00 AM until 45 minutes before kickoff."""
    start = gates.when(kickoff)
    local = now.astimezone(gates.EASTERN)
    if eastern_date(start) != local.date():
        return False
    import post_windows
    opens = post_windows.opens(league, kickoff).astimezone(gates.EASTERN)
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
        if not published or not game or not starts or not in_window(starts[0], now, pick.get('league') or game.get('league')):
            continue
        if merged.get('expiresAt') and gates.when(merged['expiresAt']) <= now - timedelta(hours=12):
            continue        # a quote that expired half a day ago is not this morning's play
        text = x_post.draft(merged, game)
        if x_post.guard(text, merged, x_post.reason_in(text)):
            continue
        local = now.astimezone(gates.EASTERN)
        import post_windows
        opened = post_windows.opens(pick.get('league') or game.get('league'), starts[0])
        items.append({'guid': key, 'title': play_title(merged),
                      'text': text, 'link': f'{SITE}#pick/{key}', 'pubDate': max(gates.when(published), opened),
                      'pick': merged, 'game': game, 'side': player_side(merged, game, player_team)})
    return items


def publication_items(first, games, now):
    """Every official first publication from the rolling 30-day public record, with its original guid."""
    cutoff = now - timedelta(days=30)
    items, reasons = [], x_post.load_reasons()
    for key, pick in first.items():
        published = pick.get('publishedAt')
        at = gates.when(published) if published else None
        game = games.get((pick.get('gameIds') or [pick.get('gameId')])[0])
        if pick.get('historicalImport') or not at or not cutoff <= at <= now or not game:
            continue
        public_pick = dict(pick)
        if public_pick.get('legs'):
            public_pick['legs'] = [{'title': leg} if isinstance(leg, str) else leg for leg in public_pick['legs']]
        text = x_post.draft(public_pick, game)
        if x_post.guard(text, public_pick, x_post.reason_in(text)):
            continue
        items.append({'guid': key, 'title': play_title(pick),
                      'text': text, 'link': f'{SITE}#pick/{key}', 'pubDate': at,
                      'pick': public_pick, 'game': game})
    return items


def card_items(first, latest, games, now, player_team=None, restored=()):
    """Every open, postable play whose first game has not started: the plays that may still need a card.

    A post restored after a false precheck closure keeps its card too. Otherwise the hosted rebuild sees the
    historical closure, deletes the image, and Buffer cannot fetch the graphic for the corrected delivery.
    """
    restored = set(restored or ())
    items = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if pick.get('historicalImport') or not postable(merged) or merged.get('result') \
                or (merged.get('entryNote') and key not in restored):
            continue
        if (merged.get('status') or 'active') != 'active' and key not in restored:
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
        items.append({'guid': f'recap:day:{day}', 'title': f"{datetime.fromisoformat(day):%A}: the results",
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


def render_cards(items, folder=CARDS, log=print, games=None, player_team=None, posted_keys=()):
    """A PNG per pick item, when a browser is on the machine. Returns {guid: path}."""
    import pick_card
    import ticket_card
    posted_keys = set(posted_keys)
    restore_posted_cards(folder, posted_keys)
    if not pick_card.chrome_path():
        log('no browser for cards; the feed goes out without images')
        return {}
    out = {}
    for item in items:
        if 'pick' not in item and 'receipt' not in item and 'ladderResult' not in item:
            continue
        path = Path(folder) / f"{item['guid']}.png"
        try:
            source = item.get('ladderResult') or item.get('receipt') or item.get('pick') or {}
            # A card cached before the cutover is not proof that an unposted play has new art.
            # Rebuild eligible cards; confirmed attachments above are immutable.
            refresh_ticket = item['guid'] not in posted_keys and pick_card.ticket_enabled(source)
            if not path.exists() or refresh_ticket:
                if 'ladderResult' in item:
                    pick = item['ladderResult']
                    svg = (ticket_card.climb_result_svg(pick, games or {}, player_team)
                           if pick_card.ticket_enabled(moment=pick.get('settledAt')) else pick_card.ladder_result_svg(pick))
                    pick_card.render(svg, path)
                elif 'receipt' in item:
                    receipt = item['receipt']
                    # Weekly category summaries are not individual settled plays; retain their existing
                    # reviewed renderer until a category-specific Kitchen receipt has been reviewed.
                    svg = (ticket_card.final_svg(item['receiptPicks'], item['receiptDay'])
                           if pick_card.ticket_enabled(receipt) and item.get('receiptPicks') else
                           pick_card.receipt_svg(receipt))
                    pick_card.render(svg, path)
                else:
                    art = (pick_card.ticket_art(item['pick'], games, player_team) if pick_card.play_kind(item['pick']) in ('parlay', 'ladder')
                           else pick_card.artwork(item['pick'], item['game'], player_side=item.get('side')))
                    if (pick_card.play_kind(item['pick']) == 'player' and item['pick'].get('athleteId')
                            and (art or {}).get('kind') != 'photo'):
                        fallback = 'team badge fallback' if (art or {}).get('kind') == 'logos' else 'no verified team badge'
                        log(f"WARNING: ESPN headshot unavailable after retry for player-prop card {item['pick'].get('id')}; {fallback}")
                    pick = item['pick']
                    if pick_card.ticket_enabled(pick):
                        kind = pick_card.play_kind(pick)
                        if kind == 'ladder':
                            svg = ticket_card.climb_svg(pick, games or {}, player_team, art=art)
                        elif kind == 'parlay':
                            svg = ticket_card.fun_svg(pick, games or {}, player_team, art=art)
                        else:
                            svg = ticket_card.straight_svg(pick, item['game'], player_side=item.get('side'),
                                                           featured=item.get('featured', False), art=art)
                    else:
                        svg = pick_card.modern_svg(pick, item['game'], record=item.get('record'),
                                                   player_side=item.get('side'), featured=item.get('featured', False), art=art)
                    pick_card.render(svg, path)
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
    # The feed is archival. Buffer independently uses postable(), so this does not expand X delivery.
    import voice
    candidates = publication_items(ctx.first, ctx.games, now) + recap_items(ctx.first, ctx.latest, ctx.games, now)
    items = []
    for item in candidates:
        if voice.lint(item.get('title')) or voice.lint(item.get('text')):
            log(f"feed: {item['guid']} omitted; public copy needs review")
        else:
            items.append(item)
    # A card for every open play as soon as it is published, not only inside its posting window: the desk
    # schedules the post the moment the card is live, and never posts without one.
    import receipts
    # Keep recent receipt images in every build. Discord normally uploads a permanent copy, but retaining these
    # URLs repairs old embeds and gives a failed delivery several days to retry without losing its card.
    ready = []
    for r in receipts.card_history(ctx.first, ctx.latest, ctx.games, now):
        item = {'guid': r['card'], 'receipt': r}
        if r['card'].startswith('receipt-day-'):
            from datetime import date
            day = date.fromisoformat(r['card'].removeprefix('receipt-day-'))
            item['receiptDay'] = day.isoformat()
            item['receiptPicks'] = receipts.plays_between(ctx.first, ctx.latest, ctx.games,
                                                           receipts.counted(ctx.first, ctx.latest), day, day)
        ready.append(item)
    import ladder
    climb = ladder.state(ctx.first, ctx.latest)
    ready += [{'guid': r['card'], 'ladderResult': dict(r['pick'],
               _allClimbsBanked=ladder.saved_through(ctx.first, ctx.latest, r['pick']['id']))}
              for r in receipts.ladder_result_cards(ctx.first, ctx.latest, now)]
    try:
        post_log = x_post.load_log()
        restored = {entry.get('id') for entry in post_log.get('posts', [])
                    if entry.get('restoredAt') and not entry.get('cancelledAt') and not entry.get('deletedAt')}
    except (OSError, ValueError):
        post_log = {}
        restored = set()
    plays = card_items(ctx.first, ctx.latest, ctx.games, now, ctx.player_team, restored)
    for item in plays:
        item['record'] = receipts.season_as_of(ctx.first, ctx.latest, item['pick'].get('publishedAt') or now)
        if item['pick'].get('parlayType') == 'ladder':
            item['pick'] = dict(item['pick'], _allClimbsBanked=climb['saved'])
    import featured
    potd = featured.of_day(eastern_date(now).isoformat())
    # The Pick of the Day gets a card of its own, under its own name, so a post can never carry a stale copy.
    plays += [dict(item, guid=f"{item['guid']}-potd", featured=True) for item in plays if item['guid'] == potd]
    cards = render_cards(plays + ready, cards_folder, log, ctx.games, ctx.player_team,
                         posted_keys=posted_card_keys(post_log)) if with_cards else {}
    if with_cards:
        import sheet          # the weekly projections sheet on its league's day, from the page payloads just built
        cards.update(sheet.render_due(now, cards_folder, log=log))
        import research_posts # at most one evidence-first research card for the current slate
        cards.update(research_posts.render_due(now, cards_folder, log=log))
        import sports_posts
        cards.update(sports_posts.render_due(now, cards_folder, log=log))
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
