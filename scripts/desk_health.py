"""Private, cached-only desk health. No provider calls, public payload or secrets.

This module emits a small allowlisted summary rather than copying logs, webhook
responses or post bodies. A refresh age is observation age, never feed latency.
"""
import argparse
import fcntl
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gates

ROOT = Path(__file__).resolve().parents[1]
CONF = Path.home() / '.config/keenroudy'
LOGS = Path.home() / 'Library/Logs/KeenRoudy'
LEAGUES = ('NBA', 'WNBA', 'CBB', 'MLB', 'NHL', 'EPL', 'MLS')
RELIABILITY_DAYS = 56
SOURCE_LIMITS = {'Football schedule': 360, 'Injury context': 360, 'Multi-sport snapshots': 360,
                 **{f'{league} score snapshot': 360 for league in LEAGUES},
                 'NFL multi-book prices': 240, 'CFB multi-book prices': 240, 'Sharp prop capture': 240}
SOURCE_STATES = ('fresh', 'stale', 'failed', 'unknown', 'invalid')
DELIVERY_FIELDS = ('queued', 'xOverdue', 'xFailed', 'discordOverdue', 'discordFailed',
                   'withheld', 'xConfirmed', 'discordConfirmed', 'heldCaptions')


def read(path):
    try:
        if Path(path).stat().st_size > 8 * 1024 * 1024:
            return {}
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def moment(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def stamp(value):
    parsed = moment(value)
    return gates.stamp(parsed) if parsed else None


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 10**9 else None


def source(name, observed, now, hours, required=False, failed=False):
    seen = moment(observed)
    age = (now - seen).total_seconds() if seen else None
    state = 'unknown' if age is None else 'invalid' if age < -60 else 'stale' if age > hours * 3600 else 'fresh'
    if failed:
        state = 'failed'
    return {'name': name, 'state': state, 'observedAt': stamp(observed),
            'ageMinutes': round(max(0, age) / 60) if age is not None else None,
            'maxAgeMinutes': hours * 60, 'requiredNow': required}


def half_hour(now):
    utc = now.astimezone(timezone.utc)
    return utc.replace(minute=utc.minute // 30 * 30, second=0, microsecond=0)


def reliability_sample(data, now):
    """Allowlisted prospective observation; never accept a replay as today's evidence."""
    checked = moment(data.get('checkedAt'))
    if data.get('mode') != 'private-cached-only' or not checked or not 0 <= (now - checked).total_seconds() <= 300:
        return None
    checks = data.get('sources') or []
    if (not isinstance(checks, list) or any(not isinstance(row, dict) for row in checks) or
            len(checks) != len(SOURCE_LIMITS) or {row.get('name') for row in checks} != set(SOURCE_LIMITS)):
        return None
    states = {}
    for row in checks:
        if not isinstance(row.get('requiredNow'), bool) or row.get('maxAgeMinutes') != SOURCE_LIMITS[row['name']]:
            return None
        state = row.get('state')
        states[row['name']] = state if state in SOURCE_STATES else 'unknown'
        if not row['requiredNow']:
            states[row['name']] = 'not-required'
    codes = {row.get('code') for row in data.get('issues') or []}
    desk = data.get('desk') or {}
    desk_state = ('failed' if 'desk-failed' in codes else 'unknown' if
                  'desk-missing' in codes or desk.get('outcome') != 'ok' else
                  'late' if 'desk-late' in codes else 'ok')
    decision = desk.get('selection')
    if desk_state not in ('ok', 'late') or decision not in ('published', 'no-new-play'):
        decision = 'unknown'
    deliveries = (data.get('deliveriesLast48h') or {}) if data.get('deliveryLogState') == 'available' else {}
    return {'window': gates.stamp(half_hour(checked)), 'observedAt': gates.stamp(checked),
            'sources': states, 'desk': desk_state, 'selection': decision,
            'deliverySnapshot48h': {key: number(deliveries.get(key)) for key in DELIVERY_FIELDS}}


def reliability_view(journal, now=None):
    """Daily sampled evidence, not an uptime, delivery-success or readiness claim.

    Required unknowns remain in the freshness denominator. Optional sources are
    excluded. Missing monitor windows have unknown eligibility, so show them as
    coverage gaps rather than inventing source checks or successful observations.
    """
    now = now or datetime.now(timezone.utc)
    samples = journal.get('samples') or []
    if not samples:
        return {'state': 'not-started', 'days': [], 'observedWindows': 0, 'eligibleSourceChecks': 0,
                'fresh': 0, 'freshPercent': None, 'readiness': 'not-assessed'}
    days = {}
    for sample in samples:
        day = moment(sample['window']).astimezone(gates.EASTERN).date().isoformat()
        if day not in days:
            days[day] = {'date': day, 'observedWindows': 0, 'eligibleSourceChecks': 0,
                         **{state: 0 for state in SOURCE_STATES}, 'notRequired': 0,
                         'desk': {state: 0 for state in ('ok', 'late', 'failed', 'unknown')}}
        row = days[day]
        row['observedWindows'] += 1
        for state in sample['sources'].values():
            if state == 'not-required':
                row['notRequired'] += 1
            else:
                row['eligibleSourceChecks'] += 1
                row[state] += 1
        row['desk'][sample['desk']] += 1
        # These are last-seen snapshots, not additive event or play counts.
        row['latestSelection'] = sample['selection']
        row['latestDeliverySnapshot48h'] = sample['deliverySnapshot48h']
    for row in days.values():
        row['freshPercent'] = round(100 * row['fresh'] / row['eligibleSourceChecks'], 2) if row['eligibleSourceChecks'] else None
    current = half_hour(now)
    first = moment(samples[0]['window'])
    expected = max(0, int((current - first).total_seconds() // 1800))
    if any(moment(sample['window']) == current for sample in samples):
        expected += 1  # Include the current partial window only once actually observed.
    eligible = sum(row['eligibleSourceChecks'] for row in days.values())
    fresh = sum(row['fresh'] for row in days.values())
    return {'state': 'collecting', 'startedAt': journal['startedAt'],
            'retainedFrom': samples[0]['observedAt'], 'lastObservedAt': samples[-1]['observedAt'],
            'retentionDays': RELIABILITY_DAYS, 'daysObserved': len(days),
            'observedWindows': len(samples), 'expectedWindowsSinceRetainedStart': expected,
            'unobservedWindows': max(0, expected - len(samples)),
            'eligibleSourceChecks': eligible, 'fresh': fresh,
            'freshPercent': round(100 * fresh / eligible, 2) if eligible else None,
            'readiness': 'not-assessed', 'days': list(days.values())}


def reliability_history(path):
    """Reject unreadable/incompatible history; do not silently reset prior evidence."""
    path = Path(path)
    if not path.exists():
        return {}
    journal = read(path)
    samples = journal.get('samples')
    if (journal.get('version') != 1 or journal.get('sourceLimitsMinutes') != SOURCE_LIMITS or
            not moment(journal.get('startedAt')) or not isinstance(samples, list) or
            not samples or len(samples) > RELIABILITY_DAYS * 48 + 1):
        raise ValueError('reliability history unavailable or incompatible')
    previous = None
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError('invalid reliability sample')
        window, seen = moment(sample.get('window')), moment(sample.get('observedAt'))
        states = sample.get('sources') or {}
        deliveries = sample.get('deliverySnapshot48h')
        if (not window or not seen or half_hour(seen) != window or (previous and window <= previous) or
                set(sample) != {'window', 'observedAt', 'sources', 'desk', 'selection', 'deliverySnapshot48h'} or
                not isinstance(states, dict) or set(states) != set(SOURCE_LIMITS) or
                any(state not in (*SOURCE_STATES, 'not-required') for state in states.values()) or
                sample.get('desk') not in ('ok', 'late', 'failed', 'unknown') or
                sample.get('selection') not in ('published', 'no-new-play', 'unknown') or
                not isinstance(deliveries, dict) or set(deliveries) != set(DELIVERY_FIELDS) or
                any(value is not None and number(value) is None for value in deliveries.values())):
            raise ValueError('invalid reliability sample')
        previous = window
    return journal


def record_reliability(data, path, now=None):
    """Called under the existing monitor lock; one immutable sample per 30-minute window."""
    now = now or datetime.now(timezone.utc)
    path = Path(path)
    try:
        journal = reliability_history(path)
        sample = reliability_sample(data, now)
        if sample is None:
            return {**reliability_view(journal, now), 'recording': 'skipped-invalid-or-replayed-observation'}
        samples = journal.get('samples') or []
        if samples and moment(sample['window']) <= moment(samples[-1]['window']):
            return {**reliability_view(journal, now), 'recording': 'already-observed'}
        cutoff = half_hour(now) - timedelta(days=RELIABILITY_DAYS)
        samples = [row for row in samples if moment(row['window']) > cutoff] + [sample]
        journal = {'version': 1, 'startedAt': journal.get('startedAt') or sample['observedAt'],
                   'sourceLimitsMinutes': SOURCE_LIMITS, 'samples': samples}
        temporary = path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as handle:
            temporary.chmod(0o600)  # Restrict the empty file before writing private evidence.
            handle.write(json.dumps(journal, separators=(',', ':')) + '\n')
        temporary.replace(path)
        return {**reliability_view(journal, now), 'recording': 'recorded'}
    except (OSError, ValueError, TypeError, KeyError):
        # Measurement failure must not change existing health alerts or erase history.
        return {'state': 'unavailable', 'readiness': 'not-assessed', 'days': [],
                'recording': 'local-history-needs-review'}


def held_captions(logs, day, posts):
    """Distinct still-unscheduled caption failures in today's log, no raw log text."""
    resolved = {str(p.get('id')) for p in posts if isinstance(p, dict)
                and (p.get('bufferPostId') or p.get('sentAt') or p.get('cancelledAt'))}
    try:
        with (Path(logs) / f'run-{day}.log').open('rb') as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 1024 * 1024))
            text = handle.read().decode('utf-8', 'replace')
    except OSError:
        return 0
    ids = re.findall(r'buffer: ([^\n]{1,180}) held back, its text fails the post check: \d+ characters', text)
    return len(set(ids) - resolved)


def delivery(posts, now):
    counts = {'queued': 0, 'xOverdue': 0, 'xFailed': 0, 'discordOverdue': 0,
              'discordFailed': 0, 'withheld': 0, 'xConfirmed': 0, 'discordConfirmed': 0}
    for p in posts:
        if not isinstance(p, dict):
            continue
        due, sent = moment(p.get('dueAt')), moment(p.get('sentAt'))
        recent = max((v for v in (due, sent) if v), default=None)
        if not recent or recent < now - timedelta(hours=48) or recent > now + timedelta(days=8):
            continue
        if (p.get('precheck') or {}).get('result') == 'withheld':
            counts['withheld'] += 1
        if p.get('cancelledAt') or p.get('deletedAt'):
            continue
        if sent:
            counts['xConfirmed'] += 1
        elif p.get('error'):
            counts['xFailed'] += 1
        elif due and due < now - timedelta(minutes=15):
            counts['xOverdue'] += 1
        elif p.get('bufferPostId'):
            counts['queued'] += 1
        mirror = p.get('discord') or {}
        if not isinstance(mirror, dict):
            continue
        if mirror.get('state') == 'sent':
            counts['discordConfirmed'] += 1
        elif mirror.get('state') in ('failed', 'error') or mirror.get('error'):
            counts['discordFailed'] += 1
        elif mirror.get('state') == 'pending':
            ready = moment(mirror.get('readyAt')) or sent
            if ready and ready < now - timedelta(minutes=15):
                counts['discordOverdue'] += 1
    return counts


def summary(root=ROOT, conf=CONF, logs=LOGS, now=None, book=None):
    now = now or datetime.now(timezone.utc)
    root, conf = Path(root), Path(conf)
    state = read(conf / 'status.json')
    post_book = book if book is not None else read(root / 'data/x-posted.json')
    posts = post_book.get('posts') or []
    posts = posts if isinstance(posts, list) else []
    issues = []

    def issue(code, label):
        issues.append({'code': code, 'message': label})

    finished = moment(state.get('finishedAt'))
    local = now.astimezone(gates.EASTERN)
    # Forty-five minutes allows the documented slot tolerance plus ordinary run time.
    expected = max(slot for delta in (-1, 0) for slot in gates.scheduled((local + timedelta(days=delta)).date())
                   if slot <= local - timedelta(minutes=45))
    if not state:
        issue('desk-missing', 'No cached desk-run status is available.')
    elif str(state.get('outcome', '')).startswith(('failed', 'crashed')):
        issue('desk-failed', 'The latest desk run failed; inspect its private log.')
    elif not finished or finished < expected or finished > now + timedelta(minutes=1):
        issue('desk-late', 'No completed desk run is recorded after the latest expected slot.')

    slate = read(root / 'site/data/slate.json')
    active = set()
    for game in slate.get('games') or []:
        kickoff = moment(game.get('kickoff'))
        if game.get('league') in ('NFL', 'CFB') and game.get('state') == 'pre' and kickoff and now < kickoff <= now + timedelta(hours=6):
            active.add(game['league'])
    checks = [source('Football schedule', slate.get('updatedAt'), now, 6, True),
              source('Injury context', read(root / 'site/data/research-context.json').get('updatedAt'), now, 6, bool(active))]
    sports = read(root / 'site/data/sports.json')
    checks.append(source('Multi-sport snapshots', sports.get('updatedAt'), now, 6, True))
    for league in LEAGUES:
        block = (sports.get('leagues') or {}).get(league) or {}
        upcoming = any(moment(g.get('kickoff')) and now - timedelta(hours=5) < moment(g['kickoff']) < now + timedelta(hours=6)
                       for g in block.get('games') or [])
        checks.append(source(f'{league} score snapshot', block.get('lastSuccessfulAt'), now, 6,
                             upcoming, block.get('status') not in (None, 'ok')))
    odds = read(root / 'data/odds/status.json')
    for league in ('NFL', 'CFB'):
        checks.append(source(f'{league} multi-book prices', ((odds.get('leagues') or {}).get(league) or {}).get('lastAt'),
                             now, 4, league in active))
    checks.append(source('Sharp prop capture', read(root / 'data/prop-odds/sharp-status.json').get('at'), now, 4, bool(active)))
    for check in checks:
        if check['requiredNow'] and check['state'] != 'fresh':
            issue('source-' + check['name'], f"{check['name']} needs a freshness check before the nearby slate.")

    counts = delivery(posts, now)
    counts['heldCaptions'] = held_captions(logs, local.date().isoformat(), posts)
    labels = {'xOverdue': 'X delivery is overdue and unconfirmed.', 'xFailed': 'An X delivery has a recorded failure.',
              'discordOverdue': 'Discord delivery is overdue and unconfirmed.', 'discordFailed': 'A Discord delivery has a recorded failure.',
              'heldCaptions': 'Research copy was held for length and has not been queued.'}
    for field, label in labels.items():
        if counts[field]:
            issue('delivery-' + field, label)
    watch = read(conf / 'live-watch.json')
    pilot = read(conf / 'live-progress.json')
    attempts = pilot.get('attempts') or []
    attempted = len(attempts)
    uncertain = any(not isinstance(a, dict) or a.get('state') != 'sent' for a in attempts)
    if attempted >= 3 or uncertain or pilot.get('reviewRequestedAt'):
        issue('pilot-review', 'The live-update pilot needs owner review before more sends.')
    usage = odds.get('usage') or {}
    used, remaining = number(usage.get('used')), number(usage.get('remaining'))
    verified = used is not None and remaining is not None and used + remaining == 500
    if verified and remaining <= 48:
        issue('odds-reserve', 'The stored Odds API balance is near the protected free reserve.')
    published = number(state.get('published')) if state.get('outcome') == 'ok' else None
    try:
        reliability = reliability_view(reliability_history(conf / 'desk-health-reliability.json'), now)
    except (OSError, ValueError, TypeError, KeyError):
        reliability = {'state': 'unavailable', 'readiness': 'not-assessed', 'days': []}
    return {'checkedAt': gates.stamp(now), 'mode': 'private-cached-only', 'issues': issues,
            'desk': {'outcome': 'ok' if state.get('outcome') == 'ok' else 'not-ok-or-unknown',
                     'finishedAt': stamp(state.get('finishedAt')), 'expectedSlot': gates.stamp(expected),
                     'selection': 'unknown' if published is None else 'published' if published else 'no-new-play'},
            'reliability': reliability,
            'sources': checks, 'deliveriesLast48h': counts,
            'deliveryLogState': 'available' if isinstance(post_book.get('posts'), list) else 'unknown',
            'oddsBudget': {'observedAt': stamp(usage.get('at')), 'used': used if verified else None,
                           'remaining': remaining if verified else None, 'verifiedFromStoredSnapshot': verified},
            'localModel': {'usedLastRun': (state.get('llm') or {}).get('used') is True,
                           'calls': number(((state.get('llm') or {}).get('calls') or {}).get('calls')),
                           'failures': number(((state.get('llm') or {}).get('calls') or {}).get('failures')),
                           'homepageStories': number((state.get('localEditor') or {}).get('stories'))},
            'livePilot': {'lastObserverAt': stamp(watch.get('lastPollAt')), 'attempts': attempted,
                          'state': 'review-required' if attempted >= 3 or uncertain else 'not-exercised' if not attempted else 'in-pilot'}}


def markdown(data):
    lines = ['## Private desk health', '', f"Cached evidence checked {data['checkedAt']}. No new feed calls."]
    lines += ['PROBLEM: ' + row['message'] for row in data['issues']]
    if not data['issues']:
        lines.append('No actionable issue found in the available cached checks; this is not a live service guarantee.')
    lines.append(f"Last completed desk run: {data['desk']['finishedAt'] or 'unknown'}.")
    for row in data['sources']:
        lines.append(f"{row['name']}: {row['state']}; last successful observation {row['observedAt'] or 'unknown'}.")
    counts = data['deliveriesLast48h']
    lines.append('Delivery evidence (48h): ' + ', '.join(f'{key} {value}' for key, value in counts.items()) + '.')
    lines.append('Stored delivery log: ' + data.get('deliveryLogState', 'unknown') + '; missing evidence is not a successful delivery.')
    budget = data['oddsBudget']
    lines.append(f"Stored Odds API budget: {budget['used']} used, {budget['remaining']} remaining; observed {budget['observedAt'] or 'unknown'}.")
    llm = data['localModel']
    lines.append(f"Local model last run: {llm['calls']} calls, {llm['failures']} failures; {llm['homepageStories']} homepage stories.")
    lines.append(f"Live Discord pilot: {data['livePilot']['state']}; {data['livePilot']['attempts']} attempts. X remains off.")
    evidence = data.get('reliability') or {}
    lines.append('Reliability history: ' + str(evidence.get('state', 'not-started')) + '. Readiness is not assessed.')
    if evidence.get('state') == 'collecting':
        lines.append(f"Sampled required-source freshness: {evidence['fresh']}/{evidence['eligibleSourceChecks']} "
                     f"({evidence['freshPercent']}%); {evidence['observedWindows']} observed half-hours, "
                     f"{evidence['unobservedWindows']} unobserved since the retained start.")
        lines.append('Unknown required checks are in the denominator. Missing windows are not successes. '
                     'Delivery snapshots are not summed; no-new-play is not a delivery failure.')
    return '\n'.join(lines) + '\n'


def html_report(data):
    """Allowlisted local-only companion; no scripts, links, assets or raw payloads."""
    def text(value):
        return html.escape('Unknown' if value is None else str(value), quote=True)

    def rows(pairs):
        return ''.join(f'<tr><th scope="row">{text(label)}</th><td>{text(value)}</td></tr>'
                       for label, value in pairs)

    issues = data.get('issues') or []
    notices = ('<ul>' + ''.join(f'<li>{text(row.get("message"))}</li>' for row in issues) + '</ul>') if issues else \
        '<p>No actionable issue found in the cached checks. This is not a live service guarantee.</p>'
    source_rows = ''.join('<tr>' + ''.join(f'<td>{text(value)}</td>' for value in (
        row.get('name'), row.get('state'), row.get('observedAt'), row.get('ageMinutes'),
        'Yes' if row.get('requiredNow') else 'No')) + '</tr>' for row in data.get('sources') or [])
    desk, budget = data.get('desk') or {}, data.get('oddsBudget') or {}
    local, pilot = data.get('localModel') or {}, data.get('livePilot') or {}
    delivery_labels = {'queued': 'X queued', 'xOverdue': 'X overdue', 'xFailed': 'X failed',
                       'discordOverdue': 'Discord overdue', 'discordFailed': 'Discord failed',
                       'withheld': 'Withheld', 'xConfirmed': 'X confirmed',
                       'discordConfirmed': 'Discord confirmed', 'heldCaptions': 'Caption length holds'}
    deliveries = data.get('deliveriesLast48h') or {}
    evidence = data.get('reliability') or {}
    evidence_rows = ''.join('<tr>' + ''.join(f'<td>{text(value)}</td>' for value in (
        row.get('date'), row.get('observedWindows'),
        f"{row.get('fresh')}/{row.get('eligibleSourceChecks')}", row.get('stale'), row.get('failed'),
        row.get('unknown'), row.get('invalid'))) + '</tr>' for row in evidence.get('days') or [])
    reliability = f'''<section><h2>Prospective reliability evidence</h2>
<p>{text(evidence.get('state', 'not-started'))} · readiness is not assessed. First observation: {text(evidence.get('startedAt'))}.</p>
<table>{rows([('Retained observed half-hours', evidence.get('observedWindows')),
              ('Unobserved half-hours since retained start', evidence.get('unobservedWindows')),
              ('Required-source checks', evidence.get('eligibleSourceChecks')),
              ('Fresh required-source checks', evidence.get('fresh')),
              ('Fresh percent of observed required checks', evidence.get('freshPercent'))])}</table>
<p>One actual sample per half-hour, retained for 56 days. Unknown required checks count in the denominator;
optional sources do not. Missing windows are unobserved, not successes. The current half-hour stays pending until
observed or finished. These are cached freshness checks, not feed latency, uptime or a four-week approval.</p>
<div class="scroll"><table><thead><tr><th>Eastern date</th><th>Samples</th><th>Fresh/required</th><th>Stale</th><th>Failed</th><th>Unknown</th><th>Invalid time</th></tr></thead><tbody>{evidence_rows}</tbody></table></div>
<p>Delivery figures remain last-48-hour snapshots, never added across observations. No-new-play and withheld decisions
are not technical failures. Display incidents and grading reconciliation still need separate review.</p></section>'''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Kook’n · Private desk health</title>
<style>body{{margin:0;background:#0b141c;color:#e9f2f6;font:16px/1.5 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:28px 20px}}h1{{font-size:28px;margin:8px 0}}h2{{font-size:20px;margin:0 0 12px}}p{{color:#b5c8d5}}section{{padding:20px;background:#142330;border:1px solid #314a5b;border-radius:12px;margin:18px 0}}.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:9px 8px;border-bottom:1px solid #314a5b;overflow-wrap:anywhere}}thead th{{color:#81e2bc}}th{{font-weight:600}}.private{{color:#81e2bc;font-size:13px;letter-spacing:.08em}}time{{font-variant-numeric:tabular-nums}}@media(max-width:600px){{main{{padding:16px 10px}}section{{padding:14px}}th,td{{font-size:14px;padding:8px 5px}}}}</style>
</head><body><main><div class="private">LOCAL ONLY · PRIVATE OPERATIONS</div>
<h1>Desk health</h1><p>Updated at <time>{text(data.get('checkedAt'))}</time> · cached evidence only.</p>
<p>This page does not refresh feeds or send posts. Reload to see the next saved snapshot.</p>
<section><h2>Needs attention</h2>{notices}</section>
<section><h2>Desk run</h2><table>{rows([('Latest outcome', desk.get('outcome')), ('Finished at', desk.get('finishedAt')), ('Expected slot', desk.get('expectedSlot'))])}</table></section>
<section><h2>Source observations</h2><p>Age is time since the stored observation, not measured feed latency.</p><div class="scroll"><table><thead><tr><th>Source</th><th>Status</th><th>Observed at</th><th>Age (minutes)</th><th>Required now</th></tr></thead><tbody>{source_rows}</tbody></table></div></section>
{reliability}
<section><h2>Delivery evidence · last 48 hours</h2><p>Stored log: {text(data.get('deliveryLogState', 'unknown'))}. Missing evidence is not a successful delivery.</p><table>{rows((label, deliveries.get(key)) for key, label in delivery_labels.items())}</table></section>
<section><h2>Stored free odds budget</h2><table>{rows([('Verified stored balance', 'Yes' if budget.get('verifiedFromStoredSnapshot') else 'No'), ('Observed at', budget.get('observedAt')), ('Used', budget.get('used')), ('Remaining', budget.get('remaining'))])}</table></section>
<section><h2>Local model · last run</h2><table>{rows([('Used', 'Yes' if local.get('usedLastRun') else 'No'), ('Calls', local.get('calls')), ('Failures', local.get('failures')), ('Homepage stories', local.get('homepageStories'))])}</table></section>
<section><h2>Live-update pilot</h2><table>{rows([('Status', pilot.get('state')), ('Attempts', pilot.get('attempts')), ('Last observer check', pilot.get('lastObserverAt'))])}</table><p>X live updates remain off. No attempts means the delivery pilot is not yet validated.</p></section>
</main></body></html>'''


def monitor(data, state_path, notify):
    """Private snapshot plus stable change-only alerts, on an existing job's clock.

    Require two matching problem sets before alerting, avoiding transient reads
    while another desk job atomically replaces its captures. Counts/timestamps do
    not churn the alert key. Recovery is reported once, after an alerted issue.
    """
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 'busy'
        prior = read(path)
        codes = sorted(row['code'] for row in data['issues'])
        consecutive = min(2, int(prior.get('consecutive', 0)) + 1) if prior.get('observed') == codes else 1
        alerted = prior.get('alerted') or []
        message = None
        if codes and consecutive >= 2 and codes != alerted:
            message = '\n'.join(row['message'] for row in data['issues'])
            alerted = codes
        elif not codes and alerted:
            message = 'The previously reported cached desk-health checks have recovered.'
            alerted = []
        # Uses the same existing job/lock. No additional notification, source call
        # or write to any public store; repeated windows do not inflate counts.
        data = dict(data, reliability=record_reliability(
            data, path.with_name(path.stem + '-reliability.json')))
        saved = {'observed': codes, 'consecutive': consecutive, 'alerted': alerted, 'summary': data}
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(saved, indent=2) + '\n', encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(path)
        page = path.with_suffix('.html')
        temporary = page.with_suffix('.html.tmp')
        temporary.write_text(html_report(data), encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(page)
        if message:
            notify(message)
        return 'changed' if message else 'quiet'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    data = summary()
    print(json.dumps(data, indent=2) if args.json else markdown(data))
