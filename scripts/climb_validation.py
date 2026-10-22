"""Weekly Climb alternate-offer validation from immutable captures and official final boxes.

No network, fitted model, retrospective player-role selection or public-record writes.
One last pregame offer per player/market/side/book/price-band; additional rungs and
repeated captures cannot inflate the sample. Missing outcomes count against opening,
never as wins or guessed zeroes. Current admission still checks model, role and news.
"""
import hashlib
import json
import math
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import boxscores
import easy_parlay
import features
import learning
import pricing
import sharp_odds

ROOT = Path(__file__).resolve().parents[1]
BOOKS = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel'}
MARKETS = {'recYds', 'rushYds', 'rec', 'passYds', 'car', 'att', 'cmp'}
VERSION = 2


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def segment_key(league, market, side, book, price):
    band = abs(int(price)) // 50 * 50
    return f'{league}/{market}/{side}/{book}/{band}-{band+49}'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def offers(captures, games, now):
    """Choose without consulting any result; latest quote then closest-to-main rung.

    Only known full-game stored schema, the main's consistent ladder, half-points,
    and actual pre-kickoff prices within 12h enter. Unknown/suspended periods hold.
    """
    chosen = {}
    for capture in captures:
        game = games.get(capture.get('gameId'))
        if not game or game.get('league') not in ('NFL', 'CFB'):
            continue
        try:
            at, kickoff = features.when(capture['retrievedAt']), features.when(game['kickoff'])
            if not timedelta(0) < kickoff-at <= timedelta(hours=12) or at > now:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        if capture.get('state', 'pre') != 'pre' or capture.get('suspended') \
                or capture.get('marketWindow', 'Full game') != 'Full game':
            continue
        capture_hash = digest(capture)
        for book_key, book in (capture.get('books') or {}).items():
            if book_key not in BOOKS or book.get('suspended') or book.get('state', 'open') != 'open':
                continue
            for market, players in (book.get('markets') or {}).items():
                if market not in MARKETS:
                    continue
                for name, quote in players.items():
                    main = quote.get('line')
                    if not number(main) or quote.get('suspended') or quote.get('state', 'open') != 'open' \
                            or quote.get('marketWindow', 'Full game') != 'Full game':
                        continue
                    for rung in sharp_odds.consistent(quote):
                        point = rung.get('line')
                        if not number(point) or point < 0 or point % 1 != .5 or rung.get('suspended') \
                                or rung.get('state', 'open') != 'open':
                            continue
                        for side in ('over', 'under'):
                            price = rung.get(side)
                            if not number(price) or int(price) != price or not -900 <= price <= -180:
                                continue
                            segment = segment_key(game['league'], market, side, BOOKS[book_key], price)
                            player = easy_parlay.name_key(name)
                            if not player:
                                continue
                            key = (capture['gameId'], player, segment)
                            rank = (at, -abs(point-main), -point, -price)
                            if key in chosen and chosen[key][0] >= rank:
                                continue
                            row = dict(gameId=capture['gameId'], player=player, market=market,
                                       side=side, book=BOOKS[book_key], line=point, odds=int(price),
                                       segment=segment, observedAt=learning.stamp(at),
                                       kickoff=game['kickoff'], season=game['season'])
                            row['id'] = digest(key)
                            row['captureHash'] = capture_hash
                            chosen[key] = (rank, row)
    return sorted((r for _, r in chosen.values()), key=lambda r: (r['kickoff'], r['id']))


def grade(rows, games, now):
    out = []
    hashes = {}
    for offer in rows:
        game = games[offer['gameId']]
        # Box-score store accepts only official finals. Respect its retrieval time;
        # never let a later correction leak into an earlier replay.
        if features.when(game['retrievedAt']) > now or features.when(game['kickoff'])+timedelta(hours=8) > now:
            continue
        matches = [p for p in game.get('players', [])
                   if easy_parlay.name_key(p.get('name')) == offer['player']]
        actual = matches[0].get(offer['market']) if len(matches) == 1 else None
        actual = actual if number(actual) else None
        # Unavailable/DNP/ambiguous stats are unknown, not a book-settled win.
        result = (('win' if (actual > offer['line'] if offer['side'] == 'over'
                            else actual < offer['line']) else 'loss') if actual is not None else None)
        if offer['gameId'] not in hashes:
            hashes[offer['gameId']] = digest(game)
        row = dict(offer, actual=actual, result=result, boxHash=hashes[offer['gameId']],
                   boxAt=game['retrievedAt'], source=(game.get('sources') or {}).get('page'),
                   gradedAt=learning.stamp(now), schemaVersion=VERSION)
        row['revision'] = digest({k: v for k, v in row.items() if k != 'gradedAt'})
        out.append(row)
    return out


def summarize(rows, now):
    groups = defaultdict(list)
    for row in rows:
        groups[row['segment']].append(row)
    out = {}
    for key, sample in sorted(groups.items()):
        sample.sort(key=lambda r: (r['kickoff'], r['id']))
        wins = sum(r['result'] == 'win' for r in sample)
        graded = sum(r['result'] in ('win', 'loss') for r in sample)
        need = sum(pricing.break_even(r['odds']) for r in sample)/len(sample)
        hit = wins/len(sample)  # lower bound: missing outcomes cannot improve proof
        recent = sample[-100:]
        last = sum((r['result'] == 'win')-pricing.break_even(r['odds']) for r in recent)/len(recent)
        out[key] = dict(schemaVersion=VERSION, scope='alternate-offers', open=(graded >= 150 and
                        hit-need >= .02-1e-12 and len(recent) == 100 and last >= -1e-12),
                        offered=len(sample), graded=graded, unknown=len(sample)-graded,
                        hitRate=hit, priceNeeded=need, abovePrice=hit-need,
                        last100AbovePrice=last, checkedAt=learning.stamp(now),
                        evidenceHash=digest([r['revision'] for r in sample]))
    return out


def refresh(policy, now, root=ROOT, store=learning.STORE, dry=False):
    """The sole weekly writer, also callable once for a repair/backfill under run lock."""
    root, store = Path(root), Path(store)
    for directory in (root/'data/boxscores', root/'data/prop-odds'):
        problems = boxscores.verify(directory) if directory.exists() else []
        if problems:
            raise ValueError('Climb validation source integrity failed: '+str(directory))
    # Select the last box version actually known at the evaluation instant.
    games = {}
    for path in sorted((root/'data/boxscores').glob('*.jsonl')):
        for game in boxscores.read_store(path):
            if features.when(game['retrievedAt']) <= now:
                gid = f"{game['league']}-{game['eventId']}"
                if gid not in games or features.when(game['retrievedAt']) > features.when(games[gid]['retrievedAt']):
                    games[gid] = game
    captures = (r for path in sorted((root/'data/prop-odds').glob('*.jsonl')) for r in boxscores.read_store(path))
    rows = grade(offers(captures, games, now), games, now)
    segments = summarize(rows, now)
    existing = {r['revision'] for path in store.glob('climb-offers-*.jsonl') for r in boxscores.read_store(path)}
    new = [r for r in rows if r['revision'] not in existing]
    if not dry:
        for season in sorted({r['season'] for r in new}):
            learning.append('climb-offers', season, [r for r in new if r['season'] == season], store)
        previous = policy.get('ladderSegments') or {}
        if previous != segments:
            policy.setdefault('history', []).append(dict(at=learning.stamp(now), knob='ladderSegments',
                why='weekly stored pregame alternate offers versus official final boxes',
                fromOpen=sorted(k for k, r in previous.items() if r.get('open')),
                toOpen=sorted(k for k, r in segments.items() if r.get('open')),
                evidence=dict(offered=len(rows), added=len(new), open=sum(r['open'] for r in segments.values()),
                              hash=digest(segments))))
        policy['ladderSegments'] = segments  # absent/legacy segments close, never retain unproven open keys
    return dict(offered=len(rows), graded=sum(r['result'] is not None for r in rows),
                unknown=sum(r['result'] is None for r in rows), added=len(new),
                segments=len(segments), open=sum(r['open'] for r in segments.values()))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='write grades and policy; caller must hold desk run lock')
    args = parser.parse_args()
    policy = learning.load_policy()
    report = refresh(policy, learning.now_utc(), dry=not args.apply)
    if args.apply:
        learning.save_policy(policy)
    print(json.dumps(report, sort_keys=True))
