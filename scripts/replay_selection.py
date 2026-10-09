"""Replay the October 9 owner-plan selection rules over stored candidates.

No network calls. Historical rows use their exact stored two-sided quote where
available; a row without one is not made eligible.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site
import features
import pricing
import role_sanity
import spot

ROOT = Path(__file__).resolve().parents[1]
EASTERN = ZoneInfo('America/New_York')


def when(value):
    return features.when(value)


def player_name(row):
    return re.split(r'\s+(?:OVER|UNDER)\s+', row.get('title') or '', maxsplit=1)[0]


def exact_pairs(row, odds_store, prop_store):
    game = (row.get('gameIds') or [None])[0]
    decided = when(row['decidedAt'])
    store = prop_store if row.get('athleteId') else odds_store
    captures = [capture for capture in store.get(game, [])
                if capture.get('retrievedAt') and when(capture['retrievedAt']) <= decided]
    if not captures:
        return []
    capture = captures[-1]
    side, line = row.get('direction'), row.get('line')
    out = []
    if row.get('athleteId'):
        for book, quoted_line, over, under in build_site.price_quotes(
                capture, row.get('market'), player_name(row), line):
            if quoted_line != line:
                continue
            selected, other = (over, under) if side == 'over' else (under, over)
            if isinstance(selected, (int, float)) and isinstance(other, (int, float)):
                out.append({'book': build_site.BOOK_NAMES.get(book, book), 'side': selected, 'other': other,
                            'retrievedAt': capture.get('retrievedAt')})
        return out
    market = row.get('marketType')
    for name, entry in (capture.get('books') or {}).items():
        offer = (entry or {}).get('total' if market == 'total' else 'spread') or {}
        if market == 'total' and offer.get('line') == line:
            selected, other = ((offer.get('over'), offer.get('under')) if side == 'over'
                               else (offer.get('under'), offer.get('over')))
        elif market == 'spread' and isinstance(offer.get('home'), (int, float)):
            selected_side = side or ('home' if float(line) == float(offer['home']) else 'away')
            own_line = offer['home'] if selected_side == 'home' else -offer['home']
            if own_line != line:
                continue
            selected, other = ((offer.get('homePrice'), offer.get('awayPrice')) if selected_side == 'home'
                               else (offer.get('awayPrice'), offer.get('homePrice')))
        else:
            continue
        if isinstance(selected, (int, float)) and isinstance(other, (int, float)):
            out.append({'book': build_site.BOOK_NAMES.get(name, name), 'side': selected, 'other': other,
                        'retrievedAt': capture.get('retrievedAt')})
    return out


def exact_pair(row, odds_store, prop_store):
    own = role_sanity.book_key(row.get('book'))
    pair = next((item for item in exact_pairs(row, odds_store, prop_store)
                 if role_sanity.book_key(item['book']) == own and item['side'] == row.get('odds')), None)
    return (pair['side'], pair['other']) if pair else None


def line_move_reason(row, odds_store, prop_store):
    """Did the same stored book move at least a point or 15 cents toward this side?"""
    game = (row.get('gameIds') or [None])[0]
    decided = when(row['decidedAt'])
    book_key = role_sanity.book_key(row.get('book'))
    side, market = row.get('direction'), row.get('market') or row.get('marketType')
    values = []
    for capture in (prop_store if row.get('athleteId') else odds_store).get(game, []):
        if not capture.get('retrievedAt') or when(capture['retrievedAt']) > decided:
            continue
        if row.get('athleteId'):
            quote = next((q for q in build_site.price_quotes(capture, market, player_name(row))
                          if role_sanity.book_key(build_site.BOOK_NAMES.get(q[0], q[0])) == book_key), None)
            if not quote:
                continue
            _, line, over, under = quote
            price = over if side == 'over' else under
        else:
            entry = next((value for name, value in (capture.get('books') or {}).items()
                          if role_sanity.book_key(build_site.BOOK_NAMES.get(name, name)) == book_key), None)
            offer = (entry or {}).get('total' if market == 'total' else 'spread') or {}
            if market == 'total':
                line, price = offer.get('line'), offer.get(side)
            else:
                chosen = side or ('home' if row.get('line') == offer.get('home') else 'away')
                line = offer.get('home') if chosen == 'home' else -offer.get('home', 0)
                price = offer.get('homePrice' if chosen == 'home' else 'awayPrice')
        if isinstance(line, (int, float)) and isinstance(price, (int, float)):
            values.append((float(line), int(price)))
    if len(values) < 2:
        return False
    first, current = values[0], values[-1]
    line_move = (current[0] - first[0]) * (1 if side == 'over' else -1)
    cents_move = pricing.cents(first[1]) - pricing.cents(current[1])
    return line_move >= 1 or cents_move >= 15


def has_reason(row, gap, player_logs, records, games, odds_store, prop_store):
    if line_move_reason(row, odds_store, prop_store):
        return True, 'class_a', 'line_move'
    research = [fact for fact in row.get('research') or []
                if fact.get('verified') and fact.get('direction') == 'for']
    if any(fact.get('kind') in ('injury', 'role', 'weather') for fact in research):
        return True, 'class_a', 'news'
    kinds = set((row.get('facts') or {}).get('kinds') or [])
    if (row.get('facts') or {}).get('for', 0) and kinds & {'injury', 'role', 'weather'}:
        kind = next(iter(kinds & {'injury', 'role', 'weather'}))
        return True, 'class_a', {'injury': 'injury_role', 'role': 'injury_role'}.get(kind, kind)
    if gap <= 12 and (row.get('facts') or {}).get('for', 0):
        return True, 'class_b', 'matchup'
    if row.get('athleteId') and gap <= 12 and isinstance(row.get('line'), (int, float)):
        before = when(row['decidedAt'])
        logs = [game for game in player_logs.get(str(row['athleteId']), [])
                if when(game.get('kickoff')) < before]
        values = [features.value(game, row.get('market')) for game in logs]
        values = [value for value in values if isinstance(value, (int, float))]
        recent = values[-10:]
        side, line = row.get('direction'), float(row['line'])
        hit = lambda value: value > line if side == 'over' else value < line
        season = [features.value(game, row.get('market')) for game in logs
                  if game.get('season') == row.get('season')]
        season = [value for value in season if isinstance(value, (int, float))]
        if len(recent) >= 10 and sum(map(hit, recent)) >= 7 and season \
                and sum(map(hit, season)) / len(season) >= .60:
            return True, 'class_b', 'hit_strip'
        game_rows = {str(game['eventId']): game for game in records}
        volume_key = ('pbpTgt' if row.get('market') in ('rec', 'recYds') else
                      'car' if row.get('market') in ('car', 'rushYds') else
                      'att' if row.get('market') in ('att', 'cmp', 'passYds') else None)
        team_key = 'att' if volume_key in ('pbpTgt', 'att') else 'rushAtt'
        shares = []
        for log in logs:
            source = game_rows.get(str(log.get('eventId')))
            stats = log.get('stats') or {}
            total = ((source or {}).get('teams') or {}).get(str(log.get('team')), {}).get(team_key)
            volume = stats.get(volume_key) if volume_key else None
            if isinstance(volume, (int, float)) and isinstance(total, (int, float)) and total > 0:
                shares.append(volume / total)
        if len(shares) >= 4:
            recent_share = sum(shares[-3:]) / 3
            season_share = sum(shares) / len(shares)
            change = recent_share / season_share - 1 if season_share else 0
            if (side == 'over' and change >= .20) or (side == 'under' and change <= -.20):
                return True, 'class_b', 'usage_trend'
        game = games.get((row.get('gameIds') or [None])[0])
        latest = logs[-1] if logs else None
        if game and latest and latest.get('pos') in ('QB', 'RB', 'WR', 'TE'):
            team = str(latest.get('team'))
            opponent = next((str(game[side]['id']) for side in ('home', 'away')
                             if str(game[side]['id']) != team), None)
            stat = f"{latest['pos']}.{row.get('market')}"
            table = features.defense_table(features.defense_logs(records, before=before), stat,
                                           season=row.get('season'))
            own = next((item for item in table if str(item['defense']) == opponent), None)
            count = 10 if row.get('league') == 'NFL' else 25
            if own and ((side == 'over' and own['rank'] > len(table) - count)
                        or (side == 'under' and own['rank'] <= count)):
                return True, 'class_b', 'matchup'
    return False, None, None


def candidates(start, end):
    rows = []
    for path in sorted((ROOT / 'data' / 'learning').glob('candidates-*.jsonl')):
        rows.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
    odds, props = build_site.load_store('odds'), build_site.load_store('prop-odds')
    grades = {row['id']: row for path in sorted((ROOT / 'data' / 'learning').glob('graded-*.jsonl'))
              for row in (json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip())}
    records = features.load()
    player_logs = features.player_logs(records)
    games = {f"{game['league']}-{game['eventId']}": game for game in records}
    latest = {}
    for row in rows:
        day = when(row.get('kickoff')).astimezone(EASTERN).date() if row.get('kickoff') else None
        if day is None or not start <= day <= end or row.get('kind') == 'parlay':
            continue
        key = (day, (row.get('gameIds') or [None])[0], row.get('athleteId'), row.get('market') or row.get('marketType'), row.get('direction'))
        if key not in latest or row.get('decidedAt', '') > latest[key].get('decidedAt', ''):
            latest[key] = row
    history = spot.load()
    out = []
    for row in latest.values():
        held = set(row.get('rules') or []) & {'player_projection_sanity', 'qb-change-recent', 'qb_change_recent',
                                               'prop_settled_role', 'prop_injury_clear'}
        if held or re.search(r'role under review|QB-change|starting-QB', str(row.get('reason') or ''), re.I):
            continue
        pair = exact_pair(row, odds, props)
        raw = row.get('rawChance')
        if not pair or not isinstance(raw, (int, float)) or not isinstance(row.get('odds'), (int, float)):
            continue
        fair = pricing.fair_chance(*pair)
        gap = 100 * (raw - fair)
        pairs = exact_pairs(row, odds, props)
        own = next((item for item in pairs if role_sanity.book_key(item['book']) == role_sanity.book_key(row.get('book'))
                    and item['side'] == row.get('odds')), None)
        if not own:
            continue
        implied_sum = pricing.break_even(own['side']) + pricing.break_even(own['other'])
        age = when(row['decidedAt']) - when(own['retrievedAt'])
        if len(pairs) == 1 and not (age.total_seconds() <= 7200 and 1.03 <= implied_sum <= 1.09 and gap <= 15):
            continue
        if gap > 15 and not any(item is not own and abs(pricing.fair_chance(item['side'], item['other']) - fair) <= .10
                                for item in pairs):
            continue
        reason, reason_class, reason_type = has_reason(row, gap, player_logs, records, games, odds, props)
        base = dict(row, fairChance=fair, gap=gap, reasonClass=reason_class, reasonType=reason_type,
                    exactBookCount=len({item['book'] for item in pairs}), quoteAgeSeconds=age.total_seconds())
        price_ok = (-200 <= row['odds'] <= 200) if row.get('marketType') == 'moneyline' else -160 <= row['odds'] <= 150
        gut = price_ok and raw >= .55 and 3 <= gap < 25 and reason
        # Acceptance applies the plan's launch-day segment evidence to each
        # historical board; it does not pretend the segment was known then.
        sample = spot.summarize(history, base) if gut else None
        best = gut and raw >= .58 and gap >= 6 and (gap < 20 or reason_class == 'class_a') \
            and sample is not None and sample['spotHit'] >= pricing.break_even(row['odds']) - .01
        grade = grades.get(row.get('id')) or {}
        base.update(gut=bool(gut), best=bool(best), spot=sample, result=grade.get('result'))
        out.append(base)
    return out


def replay(start, end):
    rows = candidates(start, end)
    by_day = defaultdict(list)
    for row in rows:
        by_day[when(row['kickoff']).astimezone(EASTERN).date()].append(row)
    report = []
    day = start
    while day <= end:
        day_rows = by_day.get(day, [])
        best = sorted((row for row in day_rows if row['best']), key=lambda r: (-r['gap'], r['id']))
        chosen = best[:5 if day.weekday() in (5, 6) else 2]
        if not chosen:
            gut = sorted((row for row in day_rows if row['gut']), key=lambda r: (-r['gap'], r['id']))
            chosen = gut[:1]
        prime = {row['gameIds'][0] for row in day_rows if row.get('league') == 'NFL'
                 if when(row['kickoff']).astimezone(EASTERN).time() >= time(19)}
        covered = {row['gameIds'][0] for row in chosen}
        for game in sorted(prime - covered):
            fallback = next((row for row in sorted(day_rows, key=lambda r: (-r['gap'], r['id']))
                             if row['gameIds'][0] == game and row['gut']), None)
            if fallback:
                chosen.append(fallback)
        report.append({'date': day.isoformat(), 'candidateCount': len(day_rows),
                       'plays': [{'id': row['id'], 'title': row['title'],
                                  'lane': 'best_bet' if row['best'] else 'gut_call',
                                  'gap': round(row['gap'], 1), 'reason': row.get('reasonType'),
                                  'exactBookCount': row.get('exactBookCount'),
                                  'quoteAgeSeconds': row.get('quoteAgeSeconds'),
                                  'result': row.get('result')}
                                 for row in chosen],
                       'footballDay': bool(day_rows), 'dark': bool(day_rows and not chosen)})
        day = day.fromordinal(day.toordinal() + 1)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--from', dest='start', default='2026-10-01')
    parser.add_argument('--to', dest='end', default='2026-10-09')
    parser.add_argument('--json')
    parser.add_argument('--assert-every-day', action='store_true')
    args = parser.parse_args(argv)
    start, end = datetime.fromisoformat(args.start).date(), datetime.fromisoformat(args.end).date()
    report = replay(start, end)
    for row in report:
        label = ' / '.join(f"{play['lane']}: {play['title']} [{play['reason']}; {play['result'] or 'pending'}]"
                           for play in row['plays']) or 'NO PLAY'
        print(f"{row['date']} | {label}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if args.assert_every_day and any(row['dark'] for row in report):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
