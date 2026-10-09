"""Pick of the Day: on each game day the desk names one play, the one its numbers like most, posts it first,
gives it its own card and leads the site with it.

"Likes most" is the calibrated edge at the fresh board quote captured during the designation run: our chance at
that current line and price (for a player prop, shrunk by the calibration learning shipped) minus what the price
needs to break even. Only open official singles whose game is that day, has not started and still has a matching
fresh board market count, never a parlay or a new extra pick. The choice is made once, at the first run of the day
that has a currently qualifying play, and never changes once it has posted, so the post, its card and the site
always agree. A pick the last look pulls before its post goes out is replaced by the best fresh play left.
It lives in data/featured.json ({"YYYY-MM-DD": {"id", "chosenAt", "edge", "replaced"?}}), committed by the desk.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates
import post_windows
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'data' / 'featured.json'
LABEL = 'PICK OF THE DAY'


def load(path=None):
    try:
        data = json.loads(Path(path or PATH).read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(featured, path=None):
    target = Path(path or PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(sorted(featured.items())), indent=1) + '\n', encoding='utf-8')


def of_day(day, featured=None):
    """The id named for an Eastern date ('2026-09-26' or a date), or None."""
    entry = (load() if featured is None else featured).get(str(day)) or {}
    return entry.get('id')


def todays_plays(first, latest, games, day, now):
    """Open, postable single plays whose first game is on `day` (Eastern) and has not kicked off."""
    import feed
    out = []
    for key, pick in first.items():
        merged = dict(pick, **latest.get(key, {}))
        if pick.get('historicalImport') or merged.get('legs') or merged.get('parlayType') or not feed.postable(merged):
            continue
        if merged.get('result') or merged.get('entryNote') or (merged.get('status') or 'active') != 'active':
            continue
        starts = sorted(games[g]['kickoff'] for g in (merged.get('gameIds') or []) if g in games)
        if not starts or eastern_date(gates.when(starts[0])) != day or gates.when(starts[0]) <= now:
            continue
        if not post_windows.reachable(pick.get('league') or (games.get((pick.get('gameIds') or [None])[0]) or {}).get('league'), starts[0], now):
            continue
        out.append((key, merged, gates.when(starts[0])))
    return out


def strength(pick, ctx, policy=None):
    """Points our calibrated chance clears the break-even by, or None when the desk has no number for it."""
    desk = gates.desk_for(pick, ctx)
    if not desk:
        return None
    chance = desk['chance']
    if pick.get('athleteId') and not desk.get('calibrated'):
        league = pick.get('league') or str(pick.get('id', '')).split('-')[0]
        k = (((policy if policy is not None else getattr(ctx, 'policy', {}) or {}).get('calibration') or {})
             .get(f'{league}/prop') or {}).get('k')
        if k is not None:
            chance = 0.5 + k * (desk['rawChance'] - 0.5)
    return round(100 * (chance - desk['breakEven']), 2)


def pulled(key, ctx, log_book):
    """Did the named play close before its post went out? Once it has posted it is the day's pick, win or lose."""
    if any(p.get('id') == key and p.get('sentAt') for p in (log_book or {}).get('posts', [])):
        return False
    merged = dict(ctx.first.get(key) or {}, **(ctx.latest.get(key) or {}))
    return bool(merged) and not merged.get('result') and bool(merged.get('entryNote') or (merged.get('status') or 'active') != 'active')


def signature(pick):
    """The market identity used to pair an official play with today's fresh board quote."""
    return ((pick.get('gameIds') or [None])[0], str(pick.get('athleteId') or ''),
            gates.market_key(pick), gates.side_of(pick))


def choose(ctx, now, path=None, policy=None, write=True, log=print, log_book=None, current=None):
    """Name today's Pick of the Day if it is not named yet; return its id (or None on a day without plays).

    Named once, it stays, unless it closes before its post goes out (the last look pulled it): then the best play
    left that has not posted takes its place, and the day's entry keeps the ones it replaced.

    When ``current`` is supplied, a first-time designation must have a matching fresh board market. Every open
    official single is scored from that current quote, rather than from the price saved when it was published.
    A current market that is not an official play cannot become POTD or create an extra pick."""
    day = eastern_date(now)
    featured = load(path)
    entry = featured.get(day.isoformat()) or {}
    named = entry.get('id')
    if log_book is None:
        import x_post
        log_book = x_post.load_log()
    if named and not pulled(named, ctx, log_book):
        return named
    sent = {p.get('id') for p in log_book.get('posts', []) if p.get('sentAt')}
    passed = set(entry.get('replaced') or []) | ({named} if named else set())
    planned = [(key, pick, kickoff) for key, pick, kickoff in
               todays_plays(ctx.first, ctx.latest, ctx.games, day, now)
               if pick.get('lane') == 'hot_plate' and key not in passed and key not in sent]
    if planned:
        key, pick, _ = planned[0]
        score = ((pick.get('_kitchenScore') or {}).get('total'))
        featured[day.isoformat()] = dict({'id': key, 'chosenAt': gates.stamp(now), 'score': score},
                                         **({'replaced': sorted(passed)} if passed else {}))
        if write:
            save(featured, path)
        log(f'pick of the day {day.isoformat()}: {key} (owner-plan Kitchen score {score})')
        return key
    fresh = None
    if current is not None:
        fresh = {}
        for pick in current:
            edge = strength(pick, ctx, policy)
            if edge is None or edge < 5.0:
                continue
            key = signature(pick)
            if key not in fresh or edge > fresh[key][0]:
                fresh[key] = (edge, pick)
    scored = []
    for key, pick, kickoff in todays_plays(ctx.first, ctx.latest, ctx.games, day, now):
        if key in passed or key in sent:
            continue
        edge = fresh.get(signature(pick), (None, None))[0] if fresh is not None else strength(pick, ctx, policy)
        if edge is not None and edge >= 5.0:
            scored.append((edge, -kickoff.timestamp(), key))
    if not scored:
        if named:
            log(f'pick of the day {day.isoformat()}: {named} was pulled before it posted, and no other play today can take its place')
        return None
    edge, _, key = max(scored)                 # the biggest edge; on a tie, the earlier kickoff
    comparison = ({'comparisonAt': gates.stamp(now), 'compared': len(scored)} if fresh is not None else {})
    featured[day.isoformat()] = dict({'id': key, 'chosenAt': gates.stamp(now), 'edge': edge}, **comparison,
                                     **({'replaced': sorted(passed)} if passed else {}))
    if write:
        save(featured, path)
    log(f'pick of the day {day.isoformat()}: {key} ({edge:+.1f} points over break-even)'
        + (f', fresh comparison of {len(scored)} official single' + ('s' if len(scored) != 1 else '') if fresh is not None else '')
        + (f', in place of {named}, pulled before it posted' if named else ''))
    return key
