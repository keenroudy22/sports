"""Revalidate the final artifact if another writer changed inputs after its build.

No capture, model fitting, push or scheduling. The workflow passes its own local
pre-push commit, not an instruction or path from a report/provider response.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(changed, python=sys.executable, node_tests=()):
    if not changed:
        return []
    source = any(p.startswith(('scripts/', '.github/', 'data/policy/'))
        or p in ('data/learning/policy.json', 'docs/product-status.json')
        or (p.startswith(('site/', 'tests/')) and p.endswith(('.py', '.js', '.html', '.css')))
        for p in changed)
    result = []
    if source:
        result.extend([[python, '-m', 'unittest', 'discover', '-s', 'tests'],
                       ['node', '--test', *node_tests]])
    result.extend([[python, 'scripts/materialize_research.py'],
        [python, 'scripts/build_site.py'], [python, 'scripts/feed.py'],
        [python, 'scripts/payload_budget.py'],
        [python, 'scripts/record_audit.py', '--today', 'site/data/app/record.json'],
        [python, 'scripts/nba_trial_audit.py'], [python, 'scripts/asset_versions.py', '--check'],
        [python, 'scripts/publication_guard.py']])
    return result


def verify(base, root=ROOT, output=subprocess.check_output, run=subprocess.run):
    if not re.fullmatch(r'[0-9a-f]{40}', base):
        raise ValueError('Expected the pre-push commit SHA')
    root = Path(root)
    changed = output(['git', 'diff', '--name-only', base, 'HEAD'], cwd=root, text=True).splitlines()
    tests = [str(p.relative_to(root)) for p in sorted((root/'tests').glob('*.test.js'))]
    plan = commands(changed, node_tests=tests)
    for command in plan:
        print('POST-REBASE VERIFY', ' '.join(command), flush=True)
        run(command, cwd=root, check=True)
    head = output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    result = dict(verifiedHead=head, upstreamChangedFiles=len(changed), repeatedChecks=len(plan))
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    verify(sys.argv[1])
