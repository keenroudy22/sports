"""The weekly review on GPT: the week's facts gathered by code, read and summed up by Codex, sent to the owner.

The owner moved the desk's AI work to OpenAI on 2026-09-28 and wanted the Monday review as a scheduled routine
there. A launchd job (deployment/mac/com.keenroudy.sports.review.plist, Monday 9:30 AM Eastern) runs this script:
it gathers the week from the desk's own records (the run logs, the post log, the record, the ladder, the hosted
runs, the price timing), hands that packet to `codex exec` (the owner's ChatGPT plan, read-only, no web search),
saves the plain-words review to ~/Library/Logs/KeenRoudy/review-<date>.md, and sends its opening to the phone. It
changes nothing: a defect it finds is described with the fix, and the owner asks Codex to make it.

  python scripts/review.py [--since YYYY-MM-DD] [--no-codex] [--no-push]
Stdlib only.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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
4. What broke, why, and the exact fix you would make (the file and the function), without making it.
5. At most three recommendations.

Plain words, short sentences, no jargon, no em dashes, they/them for the owner. Entertainment only: never phrase
anything as betting advice.

PACKET
"""


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
    """The GitHub publish runs since `first`: counts by result and the failures."""
    try:
        result = runner(['gh', 'run', 'list', '-R', 'keenroudy22/sports', '-L', '100', '--json', 'conclusion,createdAt,event,displayTitle'],
                        capture_output=True, text=True, timeout=60, env={**os.environ, **GH})
        runs = json.loads(result.stdout or '[]')
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    runs = [r for r in runs if r.get('createdAt', '')[:10] >= first.isoformat()]
    counts = {}
    for r in runs:
        counts[r.get('conclusion') or 'running'] = counts.get(r.get('conclusion') or 'running', 0) + 1
    failed = [f"{r['createdAt']} {r.get('event')}: {r.get('displayTitle')}" for r in runs if r.get('conclusion') == 'failure']
    return counts, failed[:10]


def timing(first, runner=subprocess.run):
    try:
        result = runner([sys.executable, str(ROOT / 'scripts' / 'line_timing.py'), '--since', first.isoformat()],
                        capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        return '\n'.join((result.stdout or '').strip().splitlines()[-4:])
    except (OSError, subprocess.TimeoutExpired):
        return ''


def packet(first, last, runs, posts, week, hosted, line_timing, ladder_now, alert_file):
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
    command = ['codex', 'exec', '--ephemeral', '--sandbox', 'read-only', '--config', 'approval_policy="never"',
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
    parser.add_argument('--no-push', action='store_true', help='do not send the phone alert')
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    first, last = period(now, args.since)
    import ladder
    import x_post
    ctx = gates.Stores().as_of(now)
    where = ladder.state(ctx.first, ctx.latest)
    ladder_now = f"climb {where['run']}, step {where['step']}, ${where['stake']} riding" + (f", open {where['open']['id']}" if where['open'] else '')
    text = packet(first, last, run_lines(first, last), post_rows(x_post.load_log(), first, last),
                  record(ctx.first, ctx.latest, first, last), hosted_runs(first), timing(first), ladder_now, LOGS / 'ALERT.txt')
    LOGS.mkdir(parents=True, exist_ok=True)
    packet_path, review_path = LOGS / f'review-packet-{last.isoformat()}.md', LOGS / f'review-{last.isoformat()}.md'
    packet_path.write_text(text, encoding='utf-8')
    print(f'packet: {packet_path}')
    if args.no_codex:
        return 0
    review = ask_codex(text, review_path)
    if not review:
        print('codex did not answer; the packet stands alone')
        review = 'Codex did not answer this week. The facts are in ' + str(packet_path)
        review_path.write_text(review + '\n', encoding='utf-8')
    print(f'review: {review_path}')
    if not args.no_push:
        import run
        run.alert('KeenRoudy weekly review', review[:1800] + f'\n\nFull review on the Mac: {review_path}', priority='default')
    return 0


if __name__ == '__main__':
    sys.exit(main())
