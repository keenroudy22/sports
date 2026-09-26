"""The desk learning from its own record. Stdlib only.

Every run records what it considered (scripts/learning.py). This module closes the loop:

  grade    every recorded candidate, published or not, once its box score is stored: the result, and the
           closing line value (how far the market moved toward our side by kickoff). Runs every run.
  weekly   Tuesday morning, after Monday night is graded:
           - segments   each league and market (NFL totals, NFL receiving yards, ...) measured on what it
                        published since its last change. Losing to the close with confidence makes it pickier
                        one step; still losing at the cap pauses it. Beating the close, with the near misses
                        it refused beating it too, eases it one step back toward the written rule, never past.
           - props      the raw player chances calibrated against the graded record (every projected player
                        against the DraftKings line and the box score). A calibration ships only when it
                        predicts the later part of the record better than the raw chances do; then a prop must
                        also clear its price on the calibrated chance.
           - gates, judge, researcher, posts, the number: measured and reported; the researcher is told which
             sites keep checking out and which do not, and the post's reason ranking leans toward the kinds
             of reasons people engage with, within bounds, once engagement numbers exist.
           Everything it changes goes into data/learning/policy.json with its evidence, and the week's
           findings into data/learning/REPORT.md.

  python scripts/learn.py grade            grade what can be graded
  python scripts/learn.py backfill         put the season's published picks on the record, once
  python scripts/learn.py weekly [--dry]   the weekly step (--dry: report only, change nothing)
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import features
import learning
import pricing
import scoreboard

ROOT = Path(__file__).resolve().parents[1]
MIN_N = 30            # published, graded plays a segment needs before learning moves it
NEAR_MIN = 20         # near misses needed before a segment eases back
CAL_MIN = 300         # graded prop projections before a calibration may ship
DOMAIN_MIN = 5        # researched facts from a site before it is preferred or avoided
ENGAGE_MIN = 8        # posts with numbers per reason kind before its weight moves
THRESHOLD_RULES = {'lean_edge', 'prop_raw_edge', 'prop_calibrated_value', 'learned_pause'}


# ------------------------------------------------------------------ the store's view of finished games

def store_games():
    records = features.load()
    return {scoreboard.game_id(g): g for g in records}


def close_for(row, game, captures):
    """The closing number for the candidate's own market and side, from the store; None when unknown."""
    if row.get('athleteId'):
        capture = captures.get(game and scoreboard.game_id(game))
        if not capture:
            return None
        main = (capture[1].get(str(row['athleteId'])) or {}).get(row.get('market'))
        return main[0] if main else None
    lines = features.market_lines(game or {})
    if row.get('marketType') == 'spread':
        home = lines.get('closeSpread')
        if home is None:
            return None
        return home if row.get('direction') == 'home' else -home
    return lines.get('closeTotal')


def grade_row(row, games, captures):
    """{result, value, close, clv} for a recorded candidate whose game is in the store; None when it cannot be."""
    import run
    game = games.get((row.get('gameIds') or [None])[0])
    if not game or row.get('legs'):
        return None
    if row.get('athleteId'):
        graded = run.grade_prop(row, game)
        market = 'prop'
    else:
        graded = run.grade_game_pick(row, game)
        market = row.get('marketType') or 'total'
    if not graded:
        return None
    result, _, value = graded
    close = close_for(row, game, captures)
    return {'result': result, 'value': value, 'close': close,
            'clv': learning.clv('spread' if market == 'spread' else 'total', row.get('direction'), row.get('line'), close)}


def grade_pending(now=None, root=learning.STORE, games=None, captures=None):
    """Grade every recorded candidate not graded yet whose game is final in the store. Returns the count."""
    now = now or learning.now_utc()
    seasons = sorted({int(p.stem.split('-')[1]) for p in Path(root).glob('candidates-*.jsonl')})
    pending = {}
    for season in seasons:
        done = {g['id'] for g in learning.read('graded', season, root)}
        for row in learning.read('candidates', season, root):
            if row['id'] not in done and row['id'] not in pending.get(season, {}):
                pending.setdefault(season, {})[row['id']] = row
    if not any(pending.values()):
        return 0
    games = games if games is not None else store_games()
    captures = captures if captures is not None else scoreboard.captured_lines(games)
    total = 0
    for season, rows in pending.items():
        out = []
        for key, row in rows.items():
            graded = grade_row(row, games, captures)
            if graded:
                out.append(dict(graded, id=key, gradedAt=learning.stamp(now)))
        total += learning.append('graded', season, out, root)
    return total


# ------------------------------------------------------------------ the joined record

def joined(root=learning.STORE):
    """One row per candidate: its numbers, its final decision (published if it ever was), every rule it
    failed, and its grade when it has one."""
    out = {}
    for path in sorted(Path(root).glob('candidates-*.jsonl')):
        season = int(path.stem.split('-')[1])
        grades = {g['id']: g for g in learning.read('graded', season, root)}
        for row in learning.read('candidates', season, root):
            seen = out.get(row['id'])
            if seen and seen['decision'] == 'published':
                continue
            merged = dict(row, **{k: v for k, v in (grades.get(row['id']) or {}).items() if k != 'id'})
            if seen and row['decision'] != 'published':
                merged['rules'] = sorted(set(seen.get('rules') or []) | set(row.get('rules') or []))
            out[row['id']] = merged
    return list(out.values())


def record_of(rows):
    counts = {'win': 0, 'loss': 0, 'push': 0}
    units = 0.0
    for row in rows:
        result, odds = row.get('result'), row.get('odds')
        if result in counts:
            counts[result] += 1
        if result == 'win' and isinstance(odds, (int, float)):
            units += pricing.payout(int(odds))
        elif result == 'loss':
            units -= 1
    return {**counts, 'units': round(units, 2)}


def summary(rows):
    graded = [r for r in rows if r.get('result')]
    return {'graded': len(graded), 'record': record_of(graded), 'clv': learning.interval([r.get('clv') for r in graded])}


# ------------------------------------------------------------------ segments

def knob_for(segment):
    return ('prop.minEdge', 'minEdge') if '/prop:' in segment else ('lean.minEdge', 'minEdge')


def since(policy, segment):
    return ((policy.get('segments') or {}).get(segment) or {}).get('since') or ''


def learn_segments(policy, rows, now, dry=False):
    """One step at most per segment per week, each judged only on what happened since its last change."""
    findings, changes = [], []
    by_segment = defaultdict(list)
    for row in rows:
        if row.get('segment') and not row['segment'].endswith('/parlay'):
            by_segment[row['segment']].append(row)
    for segment, seg_rows in sorted(by_segment.items()):
        start = since(policy, segment)
        fresh = [r for r in seg_rows if (r.get('decidedAt') or '') >= start and r.get('result')]
        published = [r for r in fresh if r['decision'] == 'published']
        near = [r for r in fresh if r['decision'] == 'refused' and r.get('rules') and set(r['rules']) <= THRESHOLD_RULES]
        pub, miss = summary(published), summary(near)
        finding = {'segment': segment, 'since': start or None, 'published': pub, 'nearMisses': miss,
                   'minEdge': learning.threshold(policy, knob_for(segment)[0], segment), 'paused': learning.paused(policy, segment)}
        findings.append(finding)
        if dry:
            continue
        knob, field = knob_for(segment)
        clv, near_clv = pub['clv'], miss['clv']
        evidence = {'published': pub, 'nearMisses': miss}
        change = None
        if learning.paused(policy, segment):
            if near_clv and near_clv['n'] >= MIN_N and near_clv['low'] > 0:
                change = learning.set_paused(policy, segment, False, 'what it refused while paused beat the close', evidence, now)
        elif clv and clv['n'] >= MIN_N and clv['high'] < 0:
            change = learning.move(policy, segment, field, knob, +1, 'its plays lost to the closing line', evidence, now)
            if change is None:
                change = learning.set_paused(policy, segment, True, 'still losing to the close at the strictest setting', evidence, now)
        elif (clv and clv['n'] >= MIN_N and clv['low'] > 0 and near_clv and near_clv['n'] >= NEAR_MIN and near_clv['mean'] > 0):
            change = learning.move(policy, segment, field, knob, -1, 'its plays and its near misses beat the closing line', evidence, now)
        if change:
            changes.append(change)
    return findings, changes


# ------------------------------------------------------------------ prop calibration

def prop_rows(games, snapshots, captures):
    """Every projected player against the last DraftKings line before kickoff and the box score: the raw
    chance of the side our number favoured, and whether it came in (pushes left out)."""
    rows = []
    for gid, snapshot in snapshots.items():
        game, capture = games.get(gid), captures.get(gid)
        if not game or not capture:
            continue
        box = {p['id']: p for p in game.get('players') or []}
        for side in ('home', 'away'):
            for player in (snapshot['players'].get(side) or {}).get('players', []):
                lines = capture[1].get(player['id'], {})
                for stat, market in scoreboard.PROP_STATS.items():
                    if stat not in player or market not in lines or player['id'] not in box:
                        continue
                    mean, low, high = player[stat][:3]
                    sd = (high - mean) / pricing.Z80
                    line = lines[market][0]
                    actual = scoreboard.settle_value(box[player['id']], market)
                    if sd <= 0 or actual is None or not isinstance(line, (int, float)) or actual == line:
                        continue
                    over, _, under = pricing.chances(mean, sd, line)
                    if over + under <= 0:
                        continue
                    favours_over = over >= under
                    raw = (over if favours_over else under) / (over + under)
                    rows.append({'league': game['league'], 'market': market, 'kickoff': game['kickoff'], 'raw': raw,
                                 'won': (actual > line) if favours_over else (actual < line)})
    return sorted(rows, key=lambda r: r['kickoff'])


def loglik(rows, k):
    total = 0.0
    for row in rows:
        p = min(max(0.5 + k * (row['raw'] - 0.5), 1e-4), 1 - 1e-4)
        total += math.log(p if row['won'] else 1 - p)
    return total


def fit_k(rows):
    return max((i / 100 for i in range(0, 151)), key=lambda k: loglik(rows, k))


def learn_calibration(policy, rows, now, dry=False):
    """Fit k on the earlier part of the record, test it on the later part against the raw chances and against
    the calibration in use; ship k fitted on everything only when it wins both."""
    findings, changes = [], []
    for league in sorted({r['league'] for r in rows}):
        group = [r for r in rows if r['league'] == league]
        cut = int(len(group) * 0.6)
        train, test = group[:cut], group[cut:]
        key = f'{league}/prop'
        current = ((policy.get('calibration') or {}).get(key) or {}).get('k')
        finding = {'segment': key, 'n': len(group), 'current': current}
        if len(group) < CAL_MIN or not test:
            finding['note'] = f'{len(group)} graded projections; a calibration needs {CAL_MIN}'
            findings.append(finding)
            continue
        k_train = fit_k(train)
        held = {'k': round(loglik(test, k_train), 2), 'raw': round(loglik(test, 1.0), 2)}
        if current is not None:
            held['current'] = round(loglik(test, current), 2)
        k_all = fit_k(group)
        hits = sum(r['won'] for r in group)
        finding.update(kTrain=k_train, kAll=k_all, heldOut=held, hitRate=round(hits / len(group), 3),
                       meanRaw=round(sum(r['raw'] for r in group) / len(group), 3))
        findings.append(finding)
        better = held['k'] > held['raw'] and (current is None or held['k'] > held['current'])
        if dry or not better or k_all == current:
            continue
        policy.setdefault('calibration', {})[key] = {'k': k_all, 'n': len(group), 'at': learning.stamp(now), 'heldOut': held}
        change = {'at': learning.stamp(now), 'segment': key, 'knob': 'calibration', 'from': current, 'to': k_all,
                  'why': 'calibrated chances predicted the later record better than the raw ones', 'evidence': finding}
        policy['history'].append(change)
        changes.append(change)
    return findings, changes


# ------------------------------------------------------------------ the rest of the kitchen

def by_rule(rows):
    """Every rule that refused something, and how what it refused did."""
    groups = defaultdict(list)
    for row in rows:
        if row['decision'] in ('refused', 'held'):
            for rule in row.get('rules') or [row['decision']]:
                groups[rule].append(row)
    return {rule: summary(group) for rule, group in sorted(groups.items())}


def judge_findings(rows):
    held = [r for r in rows if r['decision'] == 'held']
    kinds = defaultdict(list)
    for row in held:
        reason = str(row.get('reason') or '')
        kinds['argues against' if 'argues against' in reason else 'unsure' if 'unsure' in reason else 'rule of thumb'].append(row)
    return {'published': summary([r for r in rows if r['decision'] == 'published']),
            **{kind: summary(group) for kind, group in sorted(kinds.items())}}


def learn_domains(policy, rows, now, dry=False):
    counts = defaultdict(lambda: [0, 0])
    for row in rows:
        for fact in row.get('research') or []:
            if fact.get('domain'):
                counts[fact['domain']][0] += 1
                counts[fact['domain']][1] += bool(fact.get('verified'))
    table = {d: {'facts': n, 'verified': v, 'rate': round(v / n, 2)} for d, (n, v) in sorted(counts.items())}
    prefer = sorted((d for d, t in table.items() if t['facts'] >= DOMAIN_MIN and t['rate'] >= 0.8), key=lambda d: -table[d]['facts'])[:8]
    avoid = sorted(d for d, t in table.items() if t['facts'] >= DOMAIN_MIN and t['rate'] < 0.3)
    changes = []
    old = policy.get('researcher') or {}
    if not dry and (prefer != old.get('preferDomains') or avoid != old.get('avoidDomains')) and (prefer or avoid):
        policy['researcher'] = {'preferDomains': prefer, 'avoidDomains': avoid}
        change = {'at': learning.stamp(now), 'segment': 'researcher', 'knob': 'domains', 'from': old, 'to': policy['researcher'],
                  'why': 'which sites the researcher cites keep checking out', 'evidence': table}
        policy['history'].append(change)
        changes.append(change)
    return table, changes


def engagement(entry):
    metrics = entry.get('metrics') or {}
    views = metrics.get('impressions') or metrics.get('views') or 0
    acts = sum(metrics.get(k) or 0 for k in ('reactions', 'likes', 'reposts', 'comments', 'quotes', 'saves', 'clicks', 'follows'))   # Buffer calls likes reactions
    return (1000.0 * acts / views) if views else None


def learn_reasons(policy, log_book, now, dry=False):
    """Engagement per thousand views by the kind of reason a play post gave; weights move within 0.8 to 1.25."""
    groups = defaultdict(list)
    for entry in log_book.get('posts', []):
        rate = engagement(entry)
        if entry.get('kind') == 'buffer:play' and rate is not None:
            groups[entry.get('reasonKind') or 'none'].append(rate)
    table = {kind: {'posts': len(v), 'perThousand': round(sum(v) / len(v), 2)} for kind, v in sorted(groups.items())}
    everything = [x for v in groups.values() for x in v]
    changes = []
    if dry or len(everything) < 2 * ENGAGE_MIN:
        return table, changes
    overall = sum(everything) / len(everything)
    weights = dict(policy.get('reasonWeights') or {})
    for kind, values in groups.items():
        if kind not in learning.REASON_KINDS or len(values) < ENGAGE_MIN or overall <= 0:
            continue
        ratio = (sum(values) / len(values)) / overall
        target = round(min(max(weights.get(kind, 1.0) * (1 + 0.5 * (ratio - 1)), 0.8), 1.25), 2)
        if abs(target - weights.get(kind, 1.0)) >= 0.02:
            changes.append({'at': learning.stamp(now), 'segment': 'posts', 'knob': f'reasonWeights.{kind}',
                            'from': weights.get(kind, 1.0), 'to': target, 'why': 'engagement per thousand views by reason kind',
                            'evidence': table})
            weights[kind] = target
    if changes:
        policy['reasonWeights'] = weights
        policy['history'].extend(changes)
    return table, changes


EASTERN = ZoneInfo('America/New_York')
HOURS = ((0, 9, 'before 9 AM'), (9, 11, '9 to 11 AM'), (11, 14, '11 AM to 2 PM'), (14, 18, '2 to 6 PM'), (18, 24, 'after 6 PM'))


def post_times(log_book):
    """Engagement per thousand views by the kind of post (play, receipt, menu, book, cashed) and by the Eastern hour it
    went out. A report for the owner, not a knob: after a couple of weeks it says which posts and which times work."""
    kinds, hours = defaultdict(list), defaultdict(list)
    for entry in log_book.get('posts', []):
        rate = engagement(entry)
        sent = entry.get('sentAt') or entry.get('dueAt')
        if rate is None or not str(entry.get('kind') or '').startswith('buffer:') or not sent:
            continue
        kinds[entry['kind'].split(':', 1)[1]].append(rate)
        hour = datetime.fromisoformat(str(sent).replace('Z', '+00:00')).astimezone(EASTERN).hour
        hours[next(name for low, high, name in HOURS if low <= hour < high)].append(rate)
    table = lambda groups: {k: {'posts': len(v), 'perThousand': round(sum(v) / len(v), 2)} for k, v in groups.items()}
    order = [name for _, _, name in HOURS]
    return {'byKind': dict(sorted(table(kinds).items())), 'byHour': dict(sorted(table(hours).items(), key=lambda kv: order.index(kv[0])))}


def model_findings():
    board = json.loads((ROOT / 'site' / 'data' / 'scoreboard.json').read_text(encoding='utf-8')) if (ROOT / 'site' / 'data' / 'scoreboard.json').exists() else {}
    out = {}
    for row in board.get('live') or []:
        s = row.get('summary') or {}
        out[f"{row.get('league')} {row.get('model')}"] = {'games': s.get('games'), 'ourTotalMiss': s.get('totalMiss'),
                                                          'closeTotalMiss': s.get('closeTotalMiss'), 'closerTotal': s.get('closerTotal')}
    return out


# ------------------------------------------------------------------ the week

def weekly(now=None, dry=False, root=learning.STORE, policy_path=None, log_book=None, games=None):
    now = now or learning.now_utc()
    policy_path = policy_path or Path(root) / 'policy.json'
    policy = learning.load_policy(policy_path)
    games = games if games is not None else store_games()
    # DraftKings' NFL lines from ESPN's feed, and college lines from the priced feed (learning calibrates each league apart).
    captures = {**scoreboard.feed_lines(games), **scoreboard.captured_lines(games)}
    grade_pending(now, root, games, captures)
    rows = joined(root)
    if log_book is None:
        import x_post
        log_book = x_post.load_log()
    changes = []
    segments, moved = learn_segments(policy, rows, now, dry)
    changes += moved
    _, snapshots = scoreboard.v2_rows(games)
    calibration, moved = learn_calibration(policy, prop_rows(games, snapshots, captures), now, dry)
    changes += moved
    domains, moved = learn_domains(policy, rows, now, dry)
    changes += moved
    reasons, moved = learn_reasons(policy, log_book, now, dry)
    changes += moved
    report = {'at': learning.stamp(now), 'candidates': len(rows), 'graded': sum(1 for r in rows if r.get('result')),
              'segments': segments, 'calibration': calibration, 'gates': by_rule(rows), 'judge': judge_findings(rows),
              'researcher': domains, 'posts': reasons, 'postTimes': post_times(log_book), 'model': model_findings(), 'changes': changes}
    if not dry:
        learning.save_policy(policy, policy_path)
        boxscores.write_json(Path(root) / 'report.json', report)
        (Path(root) / 'REPORT.md').write_text(markdown(report), encoding='utf-8')
    return report


def fmt_summary(s):
    rec = s['record']
    text = f"{rec['win']}-{rec['loss']}" + (f"-{rec['push']}" if rec['push'] else '') + f", {rec['units']:+.2f}u"
    if s.get('clv'):
        text += f", closing line value {s['clv']['mean']:+.2f} points (90% {s['clv']['low']:+.2f} to {s['clv']['high']:+.2f}, n {s['clv']['n']})"
    return text


def markdown(report):
    lines = [f"# What the kitchen learned, {report['at'][:10]}", '',
             f"{report['candidates']} candidates on record, {report['graded']} graded. Closing line value is how far the "
             "market moved toward our side by kickoff; it is the first thing learning trusts.", '']
    lines += ['## Changes this week', '']
    if report['changes']:
        for c in report['changes']:
            lines.append(f"- **{c['segment']}** {c['knob']}: {c['from']} to {c['to']}. {c['why'][0].upper() + c['why'][1:]}.")
    else:
        lines.append('- None. Not enough new evidence moved anything.')
    lines += ['', '## Segments (published since their last change)', '']
    for s in report['segments']:
        state = 'paused' if s['paused'] else f"min edge {s['minEdge']:g}"
        lines.append(f"- {s['segment']} ({state}): published {fmt_summary(s['published'])}; near misses {fmt_summary(s['nearMisses'])}")
    lines += ['', '## Player chances', '']
    for c in report['calibration']:
        if 'kAll' in c:
            lines.append(f"- {c['segment']}: {c['n']} graded projections; our favoured side came in {100 * c['hitRate']:.1f}% "
                         f"against a raw {100 * c['meanRaw']:.1f}%; best shrink k {c['kAll']:.2f} (in use: {c['current']}).")
        else:
            lines.append(f"- {c['segment']}: {c.get('note')}")
    lines += ['', '## What each rule refused', '']
    for rule, s in report['gates'].items():
        lines.append(f"- {rule}: {s['graded']} graded, {fmt_summary(s)}")
    lines += ['', '## The judge', '']
    for kind, s in report['judge'].items():
        lines.append(f"- {kind}: {s['graded']} graded, {fmt_summary(s)}")
    if report['researcher']:
        lines += ['', '## Sources the researcher cited', '']
        for domain, t in report['researcher'].items():
            lines.append(f"- {domain}: {t['verified']} of {t['facts']} checked out")
    if report['posts']:
        lines += ['', '## Posts', '']
        for kind, t in report['posts'].items():
            lines.append(f"- reason kind {kind}: {t['posts']} posts, {t['perThousand']} engagements per thousand views")
    times = report.get('postTimes') or {}
    if times.get('byKind') or times.get('byHour'):
        lines += ['', '## Which posts and which hours', '']
        for kind, t in (times.get('byKind') or {}).items():
            lines.append(f"- {kind}: {t['posts']} posts, {t['perThousand']} engagements per thousand views")
        for hour, t in (times.get('byHour') or {}).items():
            lines.append(f"- {hour}: {t['posts']} posts, {t['perThousand']} engagements per thousand views")
    if report['model']:
        lines += ['', '## The number against the close (season to date)', '']
        for key, m in report['model'].items():
            lines.append(f"- {key}: {m['games']} games, total miss {m['ourTotalMiss']} vs the close's {m['closeTotalMiss']}")
    return '\n'.join(lines) + '\n'


def backfill(now=None, root=learning.STORE):
    """Put every pick already published this season on the record, once, so learning starts from the real
    history instead of from zero. Numbers come from the pick as published; nothing published is changed."""
    import gates
    import pick_card
    import pricing as _pricing
    now = now or learning.now_utc()
    ctx = gates.Stores().as_of(now)
    known = {r['id'] for p in Path(root).glob('candidates-*.jsonl') for r in boxscores.read_store(p)}
    by_season = defaultdict(list)
    for key, pick in ctx.first.items():
        if key in known or pick.get('historicalImport'):
            continue
        game = ctx.games.get((pick.get('gameIds') or [None])[0]) or {}
        league = pick.get('league') or key.split('-')[0]
        season = game.get('season') or int(key.split('-')[1])
        odds = pick.get('odds')
        market = _pricing.market_of(pick) if pick.get('athleteId') else pick.get('market')
        by_season[season].append({
            'id': key, 'league': league, 'season': season, 'segment': learning.segment_of(dict(pick, league=league, market=market)),
            'kind': pick_card.play_kind(pick), 'title': pick.get('title'), 'marketType': pick.get('marketType'),
            'market': market, 'athleteId': pick.get('athleteId'),
            'direction': str(pick.get('direction') or '').lower() or None, 'line': pick.get('line'), 'odds': odds,
            'book': pick.get('book'), 'gameIds': pick.get('gameIds'), 'kickoff': game.get('kickoff'),
            'legs': len(pick['legs']) if pick.get('legs') else None, 'projection': pick.get('projection'),
            'breakEven': round(_pricing.break_even(int(odds)), 3) if isinstance(odds, (int, float)) and abs(odds) >= 100 else None,
            'confidence': pick.get('confidence'), 'favorite': pick.get('favorite') is True, 'decision': 'published',
            'rules': [], 'reason': None, 'decidedAt': pick.get('publishedAt'), 'backfill': True})
    return sum(learning.append('candidates', season, rows, root) for season, rows in by_season.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('grade', 'weekly', 'backfill'))
    parser.add_argument('--dry', action='store_true', help='weekly: report only, change nothing')
    args = parser.parse_args(argv)
    if args.command == 'grade':
        print(f'{grade_pending()} graded')
        return 0
    if args.command == 'backfill':
        print(f'{backfill()} published picks put on the record; {grade_pending()} graded')
        return 0
    report = weekly(dry=args.dry)
    print(markdown(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
