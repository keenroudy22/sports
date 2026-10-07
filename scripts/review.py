"""The weekly review: recorded evidence prioritized locally, with explicit opt-in Codex review.

The owner moved the desk's AI work to OpenAI on 2026-09-28 and wanted the Monday review as a scheduled routine
there. A launchd job (deployment/mac/com.keenroudy.sports.review.plist, Monday 9:30 AM Eastern) runs this script:
it gathers the week from the desk's own records (the run logs, the post log, the record, the ladder, the hosted
runs, the price timing), hands that packet to a bounded local extractive brief (or `--codex` explicitly),
saves the plain-words review to ~/Library/Logs/KeenRoudy/review-<date>.md, and sends its opening to the phone. It
changes nothing: a defect it finds is described with the fix, and the owner asks Codex to make it.

  python scripts/review.py [--since YYYY-MM-DD] [--no-codex] [--no-push]
Stdlib only.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates
from sports_refresh import eastern_date

ROOT = Path(__file__).resolve().parents[1]
LOGS = Path.home() / 'Library' / 'Logs' / 'KeenRoudy'
PROBLEMS = re.compile(r'STOPPED|CRASHED|Traceback|held back|not scheduled|failed to post|holds the lock|closed before its post')
GH = {'GH_CONFIG_DIR': str(Path.home() / '.config' / 'keenroudy' / 'gh'), 'GIT_CONFIG_NOSYSTEM': '1'}
PROMPT = """You are writing the KeenRoudy Sports desk's weekly review for its owner. AGENTS.md in this folder has the
desk's rules and the owner's current decisions; read its "Weekly review", "The owner's current rules" and "When
something breaks" sections, and DESK.md where you need detail. Below is this week's packet, gathered by code from the
desk's own records. Using only the packet and the repository (read-only: change nothing, run nothing that writes),
write the review:

1. One line: did the week run cleanly?
2. A short table of each day's posts: what went out, when, and what happened to anything that did not.
3. The week's record: straight plays won and lost with units; fun parlays; the ladder in dollars.
4. Reach: what post types earned attention in the settled Buffer metrics. Say when the sample is small.
5. What broke, why, and the exact fix you would make (the file and the function), without making it.
6. At most three recommendations.

Plain words, short sentences, no jargon, no em dashes, they/them for the owner. Entertainment only: never phrase
anything as betting advice.

PACKET
"""
DEFAULT_CODEX_MODEL = 'gpt-6-sol'
DEFAULT_CODEX_REASONING = 'medium'


def private_weekly_delivery(text, day, env=None, state_path=None, metadata=None, send=None):
    """Opt-in owner-only destination; never fall back to the public plays webhook.

    A human must verify the channel's private permissions before setting the
    confirmation flag. Webhook metadata verifies destination identity, not ACLs.
    Reserve before sending; an uncertain send needs review, never an auto retry.
    No environment value, response body or URL is returned or logged.
    """
    values = os.environ if env is None else env
    url = str(values.get('DISCORD_REVIEW_WEBHOOK_URL') or '').strip()
    channel = str(values.get('DISCORD_REVIEW_CHANNEL_ID') or '').strip()
    verified = values.get('KEENROUDY_REVIEW_DISCORD_PRIVATE_VERIFIED') == '1'
    if not url:
        return 'not-configured'
    if not verified or not re.fullmatch(r'\d{15,22}', channel):
        return 'private-destination-not-verified'
    if not re.fullmatch(r'https://discord\.com/api/webhooks/\d{15,22}/[A-Za-z0-9_-]+', url) \
            or url in {values.get('DISCORD_WEBHOOK_URL'), values.get('DISCORD_WINS_WEBHOOK_URL'),
                       values.get('DISCORD_ARB_WEBHOOK_URL')}:
        return 'private-destination-refused'
    path = Path(state_path or (Path.home() / '.config/keenroudy/review-discord.json'))
    path.parent.mkdir(parents=True, exist_ok=True)

    def save(value):
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)

    def identify(target):
        with urlopen(Request(target, headers={'User-Agent': 'KooknSports/1.0'}), timeout=10) as response:
            return json.load(response)

    with path.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 'busy'
        try:
            state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        except (OSError, ValueError):
            return 'delivery-review-required'
        if not isinstance(state, dict) or not isinstance(state.get('attempts', {}), dict):
            return 'delivery-review-required'
        attempts = state.get('attempts') or {}
        if any(not isinstance(row, dict) for row in attempts.values()):
            return 'delivery-review-required'
        key = str(day)
        if key in attempts:
            return 'already-sent' if attempts[key].get('state') == 'sent' else 'delivery-review-required'
        if any(row.get('state') != 'sent' for row in attempts.values()):
            return 'delivery-review-required'
        try:
            identity = (metadata or identify)(url)
            if str(identity.get('channel_id')) != channel or not identity.get('guild_id'):
                return 'private-destination-mismatch'
            # Different webhook tokens can still target the same public channel.
            # Refuse that easy configuration mistake using source identities,
            # never by printing or persisting a webhook URL.
            for public_url in {values.get('DISCORD_WEBHOOK_URL'), values.get('DISCORD_WINS_WEBHOOK_URL'),
                               values.get('DISCORD_ARB_WEBHOOK_URL')} - {None, ''}:
                public_identity = (metadata or identify)(public_url)
                public_channel = public_identity.get('channel_id')
                if not public_channel:
                    return 'private-destination-unavailable'
                if str(public_channel) == channel:
                    return 'private-destination-refused'
        except Exception:
            return 'private-destination-unavailable'
        # One bounded excerpt. The complete report remains on the owner's Mac.
        excerpt = text.strip()
        if len(excerpt) > 1650:
            excerpt = excerpt[:1650].rsplit('\n', 1)[0] + '\nFull report is saved on the Mac.'
        body = {'username': "Kook'n Private Desk", 'content': f"Private weekly review · {day}\n\n{excerpt}",
                'allowed_mentions': {'parse': []}}
        attempts[key] = {'state': 'sending', 'destination': hashlib.sha256(channel.encode()).hexdigest()[:16],
                         'at': gates.stamp(datetime.now(timezone.utc))}
        state['attempts'] = attempts
        save(state)
        try:
            import discord_post
            code, raw = (send or discord_post.http_send)(url + '?wait=true', body,
                         {'Content-Type': 'application/json', 'User-Agent': 'KooknSports/1.0'})
            result = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            if code != 200 or not isinstance(result, dict) or not result.get('id') or str(result.get('channel_id')) != channel:
                return 'delivery-review-required'
            attempts[key]['state'] = 'sent'
            save(state)
            return 'sent'
        except Exception:
            return 'delivery-review-required'


def period(now, since=None):
    """(first, last) Eastern dates the review covers: the week that ends today, or from `since`."""
    last = eastern_date(now)
    return (date.fromisoformat(since) if since else last - timedelta(days=6)), last


def days(first, last):
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def run_lines(first, last, logs=LOGS, cap=15):
    """{date: {'runs', 'done', 'problems'}} from the desk's run logs."""
    out = {}
    for day in days(first, last):
        path = Path(logs) / f'run-{day.isoformat()}.log'
        try:
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        out[day] = {'runs': sum(1 for line in lines if 'run for the ' in line),
                    'done': [line for line in lines if '] done: ' in line],
                    'problems': [line[:300] for line in lines if PROBLEMS.search(line)][:cap]}
    return out


def post_rows(log_book, first, last):
    """Every post due in the period: (Eastern time, id, kind, what happened)."""
    rows = []
    for entry in log_book.get('posts', []):
        if not entry.get('dueAt'):
            continue
        due = gates.when(entry['dueAt'])
        if not first <= eastern_date(due) <= last:
            continue
        if entry.get('cancelledAt'):
            what = f"pulled before posting: {((entry.get('precheck') or {}).get('reason') or 'closed')[:160]}"
        elif entry.get('error'):
            what = f"failed: {str(entry['error'])[:160]}"
        elif entry.get('tweetId') or entry.get('sentAt'):
            what = f"went out (tweet {entry.get('tweetId') or '?'})"
        else:
            what = 'scheduled, not confirmed yet'
        rows.append((due, (due.astimezone(gates.EASTERN).strftime('%a %b %-d %-I:%M %p'), entry['id'], entry.get('kind', ''), what)))
    return [row for _, row in sorted(rows, key=lambda r: r[0])]


def post_metrics(log_book, first, last):
    """Settled Buffer reach for posts sent in the period, overall and by kind.

    Buffer's engagementRate includes interactions its per-action fields do not expose, so aggregate it as an
    impression-weighted rate instead of rebuilding a smaller, misleading numerator. Metrics arrive once, 48 hours
    after a post; the packet says how many posts are measured so a young sample cannot sound conclusive.
    """
    groups = {'all': []}
    for entry in log_book.get('posts', []):
        sent, metrics = entry.get('sentAt'), entry.get('metrics') or {}
        if not sent or not metrics or not first <= eastern_date(gates.when(sent)) <= last:
            continue
        views = metrics.get('impressions') or metrics.get('views') or 0
        if not views:
            continue
        row = (views, metrics.get('engagementRate'))
        groups['all'].append(row)
        groups.setdefault(str(entry.get('kind') or 'unknown').removeprefix('buffer:'), []).append(row)

    def summarize(rows):
        views = sum(row[0] for row in rows)
        rated = [(v, r) for v, r in rows if isinstance(r, (int, float))]
        rate = round(sum(v * r for v, r in rated) / sum(v for v, _ in rated), 2) if rated else None
        return {'posts': len(rows), 'impressions': views, 'engagementRate': rate}

    return {kind: summarize(rows) for kind, rows in groups.items() if rows}


def post_theme_metrics(log_book, first, last):
    """Compare creative themes only inside the same settled Buffer post category."""
    groups = {}
    for entry in log_book.get('posts', []):
        sent, metrics = entry.get('sentAt'), entry.get('metrics') or {}
        if not sent or not first <= eastern_date(gates.when(sent)) <= last:
            continue
        views = metrics.get('impressions') or metrics.get('views') or 0
        if not views:
            continue
        category = str(entry.get('kind') or 'unknown').removeprefix('buffer:')
        if entry.get('cardTheme') == 'none' or entry.get('card') is False:
            continue
        theme = entry.get('cardTheme') if entry.get('cardTheme') in ('legacy', 'felt') else 'legacy'
        groups.setdefault((category, theme), []).append((views, metrics.get('engagementRate')))
    out = []
    for (category, theme), rows in sorted(groups.items()):
        views = sum(row[0] for row in rows)
        rated = [(v, r) for v, r in rows if isinstance(r, (int, float))]
        rate = round(sum(v * r for v, r in rated) / sum(v for v, _ in rated), 2) if rated else None
        out.append({'category': category, 'theme': theme, 'posts': len(rows), 'impressions': views,
                    'engagementRate': rate, 'smallSample': len(rows) < 8})
    return out


def learning_packet(report_path=None, shadow_root=None):
    """Latest local weekly-learning and silent-shadow evidence for the Monday packet."""
    report_path = Path(report_path or ROOT / 'data/learning/report.json')
    shadow_root = Path(shadow_root or ROOT / 'data/learning')
    lines = ['', '## Learning and silent results shadows']
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        lines.append(f"- latest calibration/learning update: {report.get('at') or 'unknown'}; "
                     f"{len(report.get('changes') or [])} learning-policy changes")
        lines.append(f"- candidates: {report.get('candidates', 0)} raw; "
                     f"{report.get('distinctCandidates', report.get('candidates', 0))} distinct")
        for row in report.get('cardThemes') or []:
            note = ' (small sample)' if row.get('smallSample') else ''
            lines.append(f"  - {row.get('category')} / {row.get('theme')}: {row.get('posts')} posts, "
                         f"{row.get('perThousand')} engagements per thousand views{note}")
    except (OSError, ValueError, AttributeError):
        lines.append('- latest learning report unavailable')
    shadows = []
    for path in sorted(shadow_root.glob('shadow-*.jsonl')):
        try:
            shadows += [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        except (OSError, ValueError):
            continue
    if shadows:
        latest = max(str(row.get('at') or '') for row in shadows)
        proposals = sorted(row.get('proposal') for row in shadows if row.get('at') == latest and row.get('proposal'))
        lines.append(f"- latest silent shadow: {latest}; proposals {', '.join(proposals) or 'none'}; no public effects")
    else:
        lines.append('- no silent results shadow has completed yet')
    return '\n'.join(lines) + '\n'


def direction_packet(now, first, last, record=None, games=(), policy=None, rows=None):
    """The "Direction changes" box and the owner ping lines (owner, 2026-10-07). Read-only: it lists the moves the
    weekly learning run applied in the period, previews what the next run would change on today's evidence, and
    never applies anything."""
    import direction
    import learning
    policy = policy if policy is not None else learning.load_policy()
    applied = [e for e in policy.get('history') or [] if e.get('engine') == 'direction' and e.get('at')
               and first <= eastern_date(gates.when(e['at'])) <= last]
    notes, preview = [], []
    try:
        if rows is None:
            import learn
            rows = learn.joined()
        first_picks, latest = record or ({}, {})
        found = direction.evaluate(policy, direction.evidence(rows, first_picks, latest, games, None,
                                                              policy=policy, now=now), now)
        preview = [m for m in found if not m.get('reportOnly')]
        notes = [m for m in found if m.get('reportOnly')]
    except Exception as error:          # the review still stands; it says the preview is missing
        notes = [{'sentence': f'Direction preview unavailable: {type(error).__name__}.'}]
    text = direction.markdown(applied, preview, direction.standing(policy, now), notes)
    return text, direction.ping(applied)


def record(first_picks, latest, first, last):
    """The week's settled plays in the one-record terms: straight plays, fun parlays and ladder rungs apart."""
    import x_post
    straight = {'win': 0, 'loss': 0, 'push': 0, 'units': 0.0}
    fun, rungs, lines = {'win': 0, 'loss': 0}, [], []
    for key, pick in first_picks.items():
        merged = dict(pick, **latest.get(key, {}))
        if not merged.get('settledAt') or merged.get('result') not in ('win', 'loss', 'push', 'void'):
            continue
        if not first <= eastern_date(gates.when(merged['settledAt'])) <= last:
            continue
        result = merged['result']
        if merged.get('parlayType') == 'ladder':
            info = merged.get('ladder') or {}
            rungs.append(f"step {info.get('step')} ${info.get('stake')} to ${info.get('payout')}: {result}")
        elif merged.get('legs') or merged.get('parlayType'):
            if result in fun:
                fun[result] += 1
        else:
            if result in straight:
                straight[result] += 1
            units = merged.get('units') if isinstance(merged.get('units'), (int, float)) else x_post.units_for(merged)
            straight['units'] += units or 0.0
        lines.append(f"{result:<5} {merged.get('title')} ({merged.get('odds')} {merged.get('book')})")
    straight['units'] = round(straight['units'], 2)
    return straight, fun, rungs, sorted(lines)


def hosted_runs(first, runner=subprocess.run):
    """The GitHub publish runs since `first`: counts by result and each failure's useful detail.

    The desk can run close to two hundred workflows in a week, so the old 100-run window silently
    dropped the start of busy weeks.  GitHub filters before applying the limit; one thousand is well
    above the desk's weekly schedule without asking for old history.  Failed runs get one extra cheap
    lookup so the review can name the link and the step that needs attention.
    """
    try:
        fields = 'conclusion,createdAt,event,displayTitle,databaseId,url'
        result = runner(['gh', 'run', 'list', '-R', 'keenroudy22/sports', '--created', f'>={first.isoformat()}',
                         '-L', '1000', '--json', fields],
                        capture_output=True, text=True, timeout=60, env={**os.environ, **GH})
        runs = json.loads(result.stdout or '[]')
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    runs = [r for r in runs if r.get('createdAt', '')[:10] >= first.isoformat()]
    counts = {}
    for r in runs:
        counts[r.get('conclusion') or 'running'] = counts.get(r.get('conclusion') or 'running', 0) + 1
    failed = []
    for run in (r for r in runs if r.get('conclusion') == 'failure'):
        link = run.get('url') or ''
        steps = []
        if run.get('databaseId') is not None:
            try:
                detail = runner(['gh', 'run', 'view', str(run['databaseId']), '-R', 'keenroudy22/sports',
                                 '--json', 'jobs,url'], capture_output=True, text=True, timeout=60,
                                env={**os.environ, **GH})
                payload = json.loads(detail.stdout or '{}')
                link = payload.get('url') or link
                for job in payload.get('jobs') or []:
                    for step in job.get('steps') or []:
                        if step.get('conclusion') == 'failure':
                            steps.append(f"{job.get('name') or 'job'} / {step.get('name') or 'step'}")
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
        text = f"{run['createdAt']} {run.get('event')}: {run.get('displayTitle')}"
        if steps:
            text += f" | failed step: {', '.join(steps)}"
        if link:
            text += f" | {link}"
        failed.append(text)
    return counts, failed


def timing(first, runner=subprocess.run):
    try:
        result = runner([sys.executable, str(ROOT / 'scripts' / 'line_timing.py'), '--since', first.isoformat()],
                        capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        return '\n'.join((result.stdout or '').strip().splitlines()[-4:])
    except (OSError, subprocess.TimeoutExpired):
        return ''


def packet(first, last, runs, posts, week, hosted, line_timing, ladder_now, alert_file, reach=None, theme_reach=None):
    straight, fun, rungs, lines = week
    out = [f'# Week of {first:%b %-d} to {last:%b %-d}, {last.year}', '', '## Desk runs (from the run logs, times UTC)']
    for day, info in sorted(runs.items()):
        out.append(f"- {day:%a %b %-d}: {info['runs']} runs")
        out += [f"  - {line}" for line in info['done']]
        out += [f"  - PROBLEM: {line}" for line in info['problems']]
    out += ['', '## X posts (Eastern)'] + [f'- {when} | {key} | {kind} | {what}' for when, key, kind, what in posts]
    out += ['', '## Record for plays settled this week',
            f"- Straight plays: {straight['win']}-{straight['loss']}-{straight['push']}, {straight['units']:+.2f} units",
            f"- Fun parlays: {fun['win']}-{fun['loss']}",
            f"- Ladder rungs: {'; '.join(rungs) or 'none settled'}; now: {ladder_now}"]
    out += [f'  - {line}' for line in lines]
    out += ['', '## X reach (Buffer metrics settle after 48 hours)']
    if not reach:
        out.append('- no posts in this period have settled metrics yet')
    else:
        overall = reach.get('all') or {}
        rate = overall.get('engagementRate')
        out.append(f"- measured posts: {overall.get('posts', 0)}; impressions: {overall.get('impressions', 0)}; "
                   f"engagement rate: {f'{rate:.2f}%' if rate is not None else 'not available'}")
        for kind, result in sorted((reach or {}).items()):
            if kind == 'all':
                continue
            rate = result.get('engagementRate')
            out.append(f"  - {kind}: {result['posts']} posts, {result['impressions']} impressions, "
                       f"{f'{rate:.2f}%' if rate is not None else 'rate not available'}")
    out += ['', '## Card creative by post category']
    if not theme_reach:
        out.append('- no settled theme sample in this period')
    else:
        for result in theme_reach:
            rate = result.get('engagementRate')
            caveat = ' (small sample)' if result.get('smallSample') else ''
            out.append(f"- {result['category']} / {result['theme']}: {result['posts']} posts, "
                       f"{result['impressions']} impressions, "
                       f"{f'{rate:.2f}%' if rate is not None else 'rate not available'}{caveat}")
    if hosted is None:
        out += ['', '## GitHub publish runs', '- could not be read (gh)']
    else:
        counts, failed = hosted
        out += ['', '## GitHub publish runs', f'- {counts}'] + [f'  - FAILED {f}' for f in failed]
    out += ['', '## Posting time and the price (scripts/line_timing.py)', line_timing or '- nothing measured',
            '', '## Alerts', f"- ALERT.txt present: {'yes' if alert_file.exists() else 'no'}"]
    return '\n'.join(out) + '\n'


def ask_codex(text, out, runner=subprocess.run, timeout=900):
    """Codex's review (its last message) or None. Read-only, no web search, in the repository, one session."""
    model = os.environ.get('KEENROUDY_REVIEW_MODEL', '').strip() or DEFAULT_CODEX_MODEL
    reasoning = os.environ.get('KEENROUDY_REVIEW_REASONING', '').strip().lower()
    reasoning = reasoning if reasoning in ('low', 'medium', 'high', 'xhigh', 'max') else DEFAULT_CODEX_REASONING
    command = ['codex', 'exec', '--ephemeral', '--model', model, '--config', f'model_reasoning_effort="{reasoning}"',
               '--sandbox', 'read-only', '--config', 'approval_policy="never"',
               '--cd', str(ROOT), '--output-last-message', str(out), PROMPT + text]
    try:
        runner(command, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        return Path(out).read_text(encoding='utf-8')
    except (OSError, subprocess.TimeoutExpired):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--since', help='first Eastern date to cover (default: six days before today)')
    parser.add_argument('--no-codex', action='store_true', help='write the packet only')
    parser.add_argument('--codex', action='store_true', help='explicitly use the cloud review instead of the local brief')
    parser.add_argument('--no-push', action='store_true', help='do not send the phone alert')
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    first, last = period(now, args.since)
    import ladder
    import x_post
    stores = gates.Stores()
    ctx = stores.as_of(now)
    where = ladder.state(ctx.first, ctx.latest)
    ladder_now = f"climb {where['run']}, step {where['step']}, ${where['stake']} riding" + (f", open {where['open']['id']}" if where['open'] else '')
    log_book = x_post.load_log()
    text = packet(first, last, run_lines(first, last), post_rows(log_book, first, last),
                  record(ctx.first, ctx.latest, first, last), hosted_runs(first), timing(first), ladder_now,
                  LOGS / 'ALERT.txt', post_metrics(log_book, first, last), post_theme_metrics(log_book, first, last))
    text += learning_packet()
    direction_text, direction_ping = direction_packet(now, first, last, (ctx.first, ctx.latest), stores.records)
    text += '\n' + direction_text
    import desk_health
    # Put current verified operational facts into the same bounded local brief;
    # this adds no model call and reads no secrets or provider endpoints.
    health = desk_health.summary(root=ROOT, logs=LOGS, now=now, book=log_book)
    text = desk_health.markdown(health) + '\n' + text
    sgo = health.get('sgoEvaluation') or {}
    odds = health.get('oddsBudget') or {}
    counts = health.get('requestCounts') or {}
    free_plan = '\n'.join((
        '## Free-plan usage',
        f"- Odds API: {odds.get('used') if odds.get('used') is not None else 'unknown'}/500 credits at {odds.get('observedAt') or 'unknown'}; local stop 476.",
        f"- SharpAPI Free: {counts.get('sharp', 0)} counted requests this month; 12/minute cap. Counter may cover only part of the month.",
        f"- SportsGameOdds evaluation: {sgo.get('usedBefore') if sgo.get('usedBefore') is not None else 'unknown'}/2500 at {sgo.get('observedAt') or 'unknown'}; local stop 1800.",
        f"- Buffer Free: {counts.get('buffer', 0)} counted requests this month; local stop 2700 of the 3000-request allowance. Counter may cover only part of the month.",
        '- GitHub Actions: public repository; billed usage not available from this packet.',
        '- Cloudflare: Free plan; usage not available from this packet.',
        '- Codex/researcher: ChatGPT plan; account usage not available from this packet.',
    ))
    text += '\n' + free_plan + '\n'
    import product_followthrough
    product_status = product_followthrough.read_status(root=ROOT, now=now)
    # Keep the entire dated queue in the packet, including packet-only runs.
    # This fixed local read adds no model/provider call or work execution.
    text = f"Official plays not scheduled: {health.get('officialUnscheduled', 0)}\n\n" + product_followthrough.packet(product_status) + '\n' + text
    import market_review
    try:
        text += '\n' + market_review.markdown(market_review.from_stores())
    except Exception as error:
        text += f'\nProp formula review unavailable: {type(error).__name__}.\n'
    LOGS.mkdir(parents=True, exist_ok=True)
    packet_path, review_path = LOGS / f'review-packet-{last.isoformat()}.md', LOGS / f'review-{last.isoformat()}.md'
    packet_path.write_text(text, encoding='utf-8')
    print(f'packet: {packet_path}')
    if args.no_codex:
        return 0
    import local_brief
    import llm
    llm.reset_calls()
    review = ask_codex(text, review_path) if args.codex else local_brief.brief(text)
    if not review:
        print('review unavailable; the evidence packet stands alone (no automatic cloud fallback)')
        review = 'The summary was unavailable. The complete recorded facts follow.\n'
    # The model may choose other operational highlights, but cannot omit pending
    # work from the saved review or either existing private notification excerpt.
    review = f"Official plays not scheduled: {health.get('officialUnscheduled', 0)}\n\n" + product_followthrough.brief(product_status) + '\n\n' + review
    if direction_ping:      # one line per change and a single link, ahead of anything the model chose
        review = 'Direction changes this week:\n' + direction_ping + '\n\n' + review
    review_path.write_text(review + '\n\n' + text, encoding='utf-8')
    (LOGS / f'review-routing-{last.isoformat()}.json').write_text(json.dumps({
        'engine': 'codex' if args.codex else 'local', 'localCalls': llm.call_stats(),
        'cloudFallback': False}, indent=2) + '\n', encoding='utf-8')
    print(f'review: {review_path}')
    if not args.no_push:
        import run
        run.alert('KeenRoudy weekly review', review[:1800] + f'\n\nFull review on the Mac: {review_path}', priority='default')
        delivery = private_weekly_delivery(review, last.isoformat())
        print(f'private Discord review: {delivery}')
        if delivery == 'delivery-review-required':
            run.alert('Kook\'n private review needs a check', 'Private Discord review delivery was uncertain. Check the channel before any retry.', priority='default')
    return 0


if __name__ == '__main__':
    sys.exit(main())
