"""Exercise the real desk dry-run against an isolated copy of stored inputs, offline.

Unlike run.py --dry-run alone, this command cannot fetch facts, spend API credits,
launch a model/browser, or write to the live desk. It is not a fresh-price/news check.
Artifacts stay in a newly created temporary folder for inspection.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, TypeError):
        return False


def stage(root, workspace):
    """Copy inputs, never link them: builders may remove/rebuild their output tree."""
    root, workspace = Path(root), Path(workspace)
    snapshot = workspace / 'snapshot'
    snapshot.mkdir()
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store')
    for name in ('scripts', 'data', 'research'):
        shutil.copytree(root / name, snapshot / name, ignore=ignore)
    shutil.copytree(root / 'site' / 'data', snapshot / 'site' / 'data',
                    ignore=shutil.ignore_patterns('app', 'cards', '__pycache__', '.DS_Store'))
    (workspace / 'offline-rehearsal.json').write_text(json.dumps({'source': str(root.resolve())}) + '\n')
    return snapshot


def environment(workspace):
    """Do not inherit credentials, model overrides or the owner's production config."""
    return {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'en_US.UTF-8',
            'TZ': 'America/Indiana/Indianapolis', 'PYTHONDONTWRITEBYTECODE': '1',
            'KEENROUDY_CONF': str(Path(workspace) / 'private'), 'KEENROUDY_RESEARCHER': '0',
            'KEENROUDY_LOCAL_EDITOR': '0', 'KEENROUDY_LLM_POLISH': '0'}


class OfflineGuard:
    """Defense in depth after staging: no network/processes and no outside writes.

    This is a narrow rehearsal guard for trusted repository code, not a sandbox for
    untrusted programs. The isolated child receives no production secrets.
    """
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.denied = {'network': 0, 'process': 0, 'outsideWrite': 0, 'privateRead': 0}

    def write(self, path):
        if isinstance(path, int):
            return  # Existing stdout/stderr descriptors; no external descriptor is supplied.
        if not inside(path, self.workspace):
            self.denied['outsideWrite'] += 1
            raise PermissionError('offline rehearsal refused a write outside its temporary workspace')

    def audit(self, event, args):
        if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.sendto'):
            self.denied['network'] += 1
            raise OSError('offline rehearsal: network disabled')
        if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.exec'):
            self.denied['process'] += 1
            raise OSError('offline rehearsal: child processes disabled')
        if event == 'open':
            path, mode, flags = args
            if isinstance(path, int):
                return
            target = Path(path).resolve()
            private = Path.home() / '.config' / 'keenroudy'
            if inside(target, private):
                self.denied['privateRead'] += 1
                raise PermissionError('offline rehearsal cannot read production private state')
            writing = (any(c in str(mode or '') for c in 'wax+') or
                       bool((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
            if writing:
                self.write(target)
        elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.chown', 'os.truncate', 'os.utime'):
            self.write(args[0])
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            self.write(args[0])
            self.write(args[1])

    def unavailable(self, request, *args, **kwargs):
        self.denied['network'] += 1
        # Never include a full URL or query in logs, even in a secret-free child.
        url = getattr(request, 'full_url', request)
        host = urlsplit(str(url)).hostname or 'source'
        raise OSError(f'offline rehearsal: {host} unavailable; use saved evidence')


def worker(workspace, slot, now=None):
    workspace = Path(workspace).resolve()
    if ROOT != workspace / 'snapshot' or not (workspace / 'offline-rehearsal.json').is_file():
        raise ValueError('worker must run from its staged snapshot')
    guard = OfflineGuard(workspace)
    sys.addaudithook(guard.audit)
    import urllib.request
    urllib.request.urlopen = guard.unavailable
    sys.path.insert(0, str(ROOT / 'scripts'))
    import run
    # Draft wording still runs. Browser/card rendering is tested separately and is
    # intentionally absent from this no-process, no-network rehearsal.
    run.pick_card.chrome_path = lambda: None
    argv = ['run', '--dry-run', '--no-llm', '--slot', slot, '--record-screens']
    if now:
        argv += ['--now', now]
    code = run.main(argv)
    status_path = workspace / 'private' / 'pending' / 'status.json'
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    result = {'exitCode': code, 'outcome': status.get('outcome', 'missing status'),
              'scope': 'real _run; stored inputs only; no fresh availability/price validation',
              'blocked': guard.denied, 'status': str(status_path), 'workspace': str(workspace)}
    # Missing state or a write attempted outside the copy is a failed rehearsal,
    # even if an optional production-code catch swallowed the refusal.
    if status.get('outcome') != 'ok' or guard.denied['outsideWrite'] or guard.denied['privateRead']:
        code = code or 1
    result['exitCode'] = code
    (workspace / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--slot', required=True, help='HHMM Eastern; use the current scheduled window')
    parser.add_argument('--now', help='optional recorded UTC instant; future instants are refused')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if len(args.slot) != 4 or not args.slot.isdigit() or int(args.slot[:2]) > 23 or int(args.slot[2:]) > 59:
        parser.error('--slot must be HHMM')
    if args.now:
        try:
            instant = datetime.fromisoformat(args.now.replace('Z', '+00:00'))
            if instant.tzinfo is None or instant > datetime.now(timezone.utc):
                raise ValueError
        except ValueError:
            parser.error('--now must be a timezone-aware instant no later than now')
    if args.worker:
        return worker(args.worker, args.slot, args.now)
    workspace = Path(tempfile.mkdtemp(prefix='kookn-rehearsal-')).resolve()
    snapshot = stage(ROOT, workspace)
    argv = [sys.executable, str(snapshot / 'scripts' / 'rehearse.py'), '--worker', str(workspace), '--slot', args.slot]
    if args.now:
        argv += ['--now', args.now]
    print(f'Offline rehearsal artifacts: {workspace}', flush=True)
    with (workspace / 'rehearsal.log').open('w') as log:
        result = subprocess.run(argv, cwd=snapshot, env=environment(workspace), stdout=log, stderr=subprocess.STDOUT)
    print(f'Exit {result.returncode}; log: {workspace / "rehearsal.log"}')
    if (workspace / 'result.json').exists():
        print((workspace / 'result.json').read_text())
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
