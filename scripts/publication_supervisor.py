"""Bounded self-repair when the hosted Today card falls behind production.

This checks only Kook'n's committed public payload and its hosted copy.  It does
not capture a price, select a play, edit a record or call a sports provider.
After the normal deployment grace period, one mismatch can dispatch the
publish-only workflow twice per production revision, at least 45 minutes apart.
"""
import json
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


PUBLIC_TODAY = 'https://keenroudy.com/sports/data/app/today.json'
DEPLOY_GRACE = timedelta(minutes=15)
RETRY_COOLDOWN = timedelta(minutes=45)
MAX_RETRIES = 2
WORKFLOW = 'publish.yml'
REPOSITORY = 'keenroudy22/sports'
PICK_FIELDS = ('id', 'displayTitle', 'line', 'odds', 'book', 'status', 'riskUnits',
               'kickoff', 'expiresAt', 'entryNote')


def moment(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, TypeError, ValueError):
        return {}


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=1) + '\n', encoding='utf-8')
    temporary.chmod(0o600)
    temporary.replace(path)


def observation(conf, result, now):
    """Persist one change-only operator signal without changing repair state."""
    path = Path(conf) / 'publication-recovery-alert.json'
    prior = read(path)
    state = result.get('state')
    quiet = state in ('healthy', 'deploying', 'repair-waiting')
    key = None if quiet else f"{state}:{result.get('attempts', '')}"
    notified = prior.get('notified')
    notify = bool(key and key != notified)
    answer = dict(result, notify=notify)
    if state == 'healthy' and notified:
        answer['notify'] = True
        answer['issue'] = 'The hosted Today card recovered and matches production again.'
        notified = None
    elif notify:
        notified = key
    write(path, {'observed': state, 'notified': notified, 'checkedAt': stamp(now)})
    return answer


def current_picks(payload):
    """Exact durable terms for every published, unsettled play in Today."""
    rows = payload.get('picks') if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    result = []
    for pick in rows:
        if not isinstance(pick, dict) or not pick.get('id') or not pick.get('posted') or pick.get('result'):
            continue
        result.append(tuple(pick.get(field) for field in PICK_FIELDS))
    return sorted(result, key=lambda row: str(row[0]))


def inspect(root, now=None, open_url=None):
    """Return one truthful hosted/publication state without changing anything."""
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    local = read(root / 'site/data/app/today.json')
    local_at = moment(local.get('generatedAt'))
    local_picks = current_picks(local)
    if local_at is None or local_picks is None:
        return {'state': 'local-invalid', 'repairable': False,
                'issue': 'Production Today data is unavailable or invalid; publish-only recovery was not attempted.'}
    try:
        opener = open_url or urllib.request.urlopen
        request = urllib.request.Request(PUBLIC_TODAY, headers={'User-Agent': 'KooknSports/1.0'})
        with opener(request, timeout=8) as response:
            remote = json.load(response)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {'state': 'host-unreachable', 'repairable': False,
                'issue': 'The hosted Today payload could not be verified; publish-only recovery was not attempted.'}
    remote_at = moment(remote.get('generatedAt'))
    remote_picks = current_picks(remote)
    if remote_at is None or remote_picks is None:
        return {'state': 'host-invalid', 'repairable': True,
                'issue': 'The hosted Today payload is invalid and needs a publish-only recovery.'}
    mismatch = remote_picks != local_picks
    local_age = now - local_at
    remote_age = now - remote_at
    local_ahead = local_at - remote_at > timedelta(minutes=10)
    if mismatch or (remote_age > timedelta(hours=3) and local_age <= timedelta(hours=3) and local_ahead):
        # Do not race the normal push deployment. Its measured hosted path is
        # currently about eight minutes; fifteen leaves a clear failure margin.
        if local_age < DEPLOY_GRACE:
            return {'state': 'deploying', 'repairable': False, 'issue': None,
                    'localGeneratedAt': stamp(local_at), 'hostedGeneratedAt': stamp(remote_at)}
        detail = ('published play terms differ from production' if mismatch else
                  f'hosted Today data is {round(remote_age.total_seconds() / 3600, 1)} hours old')
        return {'state': 'behind', 'repairable': True,
                'issue': f'The hosted Today card is behind: {detail}.',
                'localGeneratedAt': stamp(local_at), 'hostedGeneratedAt': stamp(remote_at)}
    if remote_age > timedelta(hours=3):
        return {'state': 'source-stale', 'repairable': False,
                'issue': f'Today source data is {round(local_age.total_seconds() / 3600, 1)} hours old; a provider refresh is required, not a republish.',
                'localGeneratedAt': stamp(local_at), 'hostedGeneratedAt': stamp(remote_at)}
    return {'state': 'healthy', 'repairable': False, 'issue': None,
            'localGeneratedAt': stamp(local_at), 'hostedGeneratedAt': stamp(remote_at)}


def revision(root, check_output=None):
    output = (check_output or subprocess.check_output)(
        ['git', 'rev-parse', 'HEAD'], cwd=Path(root), text=True)
    return output.strip()


def supervise(root, conf, now=None, open_url=None, run=None, check_output=None):
    """Inspect and, when safe, dispatch one bounded stored-evidence republish."""
    root, conf = Path(root), Path(conf)
    now = now or datetime.now(timezone.utc)
    health = inspect(root, now, open_url)
    state_path = conf / 'publication-recovery.json'
    prior = read(state_path)
    if health['state'] == 'healthy':
        if prior and prior.get('state') != 'recovered':
            write(state_path, {**prior, 'state': 'recovered', 'recoveredAt': stamp(now)})
        return observation(conf, health, now)
    if not health.get('repairable'):
        return observation(conf, health, now)
    try:
        head = revision(root, check_output)
    except (OSError, subprocess.SubprocessError):
        return observation(conf, {**health, 'state': 'repair-failed',
                           'issue': health['issue'] + ' The production revision could not be verified.'}, now)
    attempts = prior.get('attempts', 0) if prior.get('revision') == head else 0
    last = moment(prior.get('lastAttemptAt')) if prior.get('revision') == head else None
    if last and now - last < RETRY_COOLDOWN:
        return observation(conf, {**health, 'state': 'repair-waiting', 'attempts': attempts,
                           'issue': health['issue'] + ' A bounded recovery is already in its verification window.'}, now)
    if attempts >= MAX_RETRIES:
        return observation(conf, {**health, 'state': 'repair-exhausted', 'attempts': attempts,
                           'issue': health['issue'] + ' Two automatic recoveries failed; operator attention is required.'}, now)
    command = ['gh', 'workflow', 'run', WORKFLOW, '--repo', REPOSITORY, '--ref', 'main',
               '-f', 'publish_only=true']
    answer = (run or subprocess.run)(command, cwd=root, capture_output=True, text=True)
    attempts += 1
    saved = {'revision': head, 'attempts': attempts, 'lastAttemptAt': stamp(now),
             'state': 'dispatched' if answer.returncode == 0 else 'dispatch-failed'}
    write(state_path, saved)
    if answer.returncode:
        return observation(conf, {**health, 'state': 'repair-failed', 'attempts': attempts,
                           'issue': health['issue'] + ' The publish-only recovery could not be dispatched.'}, now)
    return observation(conf, {**health, 'state': 'repair-dispatched', 'attempts': attempts,
                       'issue': health['issue'] + ' Kook’n automatically dispatched a publish-only recovery.'}, now)

