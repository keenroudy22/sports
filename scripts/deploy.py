"""Verify code releases outside the posting lock, then promote exactly tested heads.

Run from sports-dev after committing reviewed changes. This does not confirm
hosted publication or live mobile rendering; those remain required afterwards.
"""
import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

import deployment_lock

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, 'GH_CONFIG_DIR': '/Users/keen/.config/keenroudy/gh',
       'GIT_CONFIG_NOSYSTEM': '1'}


def command(args, cwd):
    print('RELEASE CHECK', ' '.join(map(str, args)), flush=True)
    subprocess.run(args, cwd=cwd, env=ENV, check=True)


def clean(path):
    state = subprocess.check_output(['git', 'status', '--porcelain'], cwd=path,
                                    env=ENV, text=True)
    if state.strip():
        raise RuntimeError(f'{path} is dirty; changes preserved, release stopped')


def synchronize(production, candidate):
    # Existing conflict resolver preserves both immutable-store writers. Unknown
    # conflicts stop with local commits intact; never reset either checkout.
    import run
    def git(*args, cwd=production, check=True):
        result = subprocess.run(['git', *args], cwd=cwd, env=ENV,
                                capture_output=True, text=True)
        if check and result.returncode:
            raise run.RunError(f'git failed: {(result.stderr or result.stdout).strip()[:400]}')
        return result
    run.rebase_onto_remote(runner=git, cwd=production)
    command(['git', 'rebase', '--quiet', deployment_lock.head(production)], candidate)


def rehearsal_slot(now):
    clock = now.astimezone(ZoneInfo('America/Indiana/Indianapolis'))
    recent = clock.replace(minute=55 if clock.minute >= 55 or clock.minute < 25 else 25)
    if clock.minute < 25:
        recent -= timedelta(hours=1)
    return recent.strftime('%H%M')


def verify(candidate):
    python = sys.executable
    node_tests = sorted(str(p.relative_to(candidate)) for p in (candidate/'tests').glob('*.test.js'))
    if not node_tests:
        raise RuntimeError('No frontend tests found; release stopped')
    plans = [[python, '-m', 'unittest', 'discover', '-s', 'tests'],
             ['node', '--test', *node_tests], [python, 'scripts/clean_export_tests.py']]
    plans += [[python, 'scripts/' + name] for name in
              ('materialize_research.py', 'build_site.py', 'feed.py', 'payload_budget.py')]
    plans += [[python, 'scripts/record_audit.py', '--today', 'site/data/app/record.json'],
              [python, 'scripts/nba_trial_audit.py'], [python, 'scripts/publication_guard.py'],
              [python, 'scripts/asset_versions.py', '--check'],
              [python, '-m', 'unittest', 'tests.test_check_svg'],
              [python, 'scripts/rehearse.py', '--slot', rehearsal_slot(datetime.now().astimezone())]]
    for args in plans:
        command(args, candidate)
    # Generated tracked-index changes must be reviewed/committed before retry,
    # never silently bundled into an already-tested revision.
    clean(candidate)


def promote(production, tested_candidate):
    command(['git', 'merge', '--quiet', '--ff-only', tested_candidate], production)
    # A rejected push leaves the tested merge intact. The next attempt rebases
    # both writers and repeats every gate before another promotion/push.
    command(['git', 'push', '--quiet', 'origin', 'main'], production)


def release(production, candidate, locks, *, attempts=3, synchronize=synchronize,
            verify=verify, promote=promote):
    production, candidate, locks = Path(production), Path(candidate), Path(locks)
    if not 1 <= attempts <= 3:
        raise ValueError('Release requires one to three bounded attempts')
    with deployment_lock.bounded_lock(locks/'release.lock'):
        for attempt in range(attempts):
            with deployment_lock.bounded_lock(locks/'run.lock'):
                clean(production)
                clean(candidate)
                synchronize(production, candidate)
                clean(production)
                clean(candidate)
                tested_base = deployment_lock.head(production)
                tested_candidate = deployment_lock.head(candidate)
            verify(candidate)
            with deployment_lock.bounded_lock(locks/'run.lock'):
                clean(production)
                clean(candidate)
                if (deployment_lock.head(production) != tested_base or
                        deployment_lock.head(candidate) != tested_candidate):
                    print('Release inputs advanced; repeating all gates', flush=True)
                    continue
                try:
                    promote(production, tested_candidate)
                except subprocess.CalledProcessError as error:
                    # Only a rejected push is retryable. Failed merges/checks
                    # stop; no unchecked state can become a successful receipt.
                    if list(error.cmd[:2]) != ['git', 'push']:
                        raise
                    print('Push rejected; preserving both writers and revalidating', flush=True)
                    continue
                receipt = dict(state='pushed-needs-hosted-live', testedBase=tested_base,
                               testedCandidate=tested_candidate, attempts=attempt + 1)
                print(json.dumps(receipt), flush=True)
                return receipt
    raise RuntimeError('Three release races; local commits preserved, hosted/live unverified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', type=Path, default=Path('/Users/keen/Projects/sports'))
    parser.add_argument('--candidate', type=Path, default=ROOT)
    parser.add_argument('--locks', type=Path, default=Path('/Users/keen/.config/keenroudy'))
    args = parser.parse_args()
    release(args.production, args.candidate, args.locks)
