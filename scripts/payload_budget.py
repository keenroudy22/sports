"""Protect the app shell and report oversized public data without stopping delivery.

The shell is required to start the site, so its reviewed gzip ceiling remains a
hard publish gate. Data payloads are independently fetched and may grow on a
large slate; those breaches are warnings surfaced to desk health, never a reason
to skip card rendering or a deployment.
"""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
LIMITS = {
    'shell-gzip': 92 * 1024,
    'lazy-more-gzip': 32 * 1024,
    'today': 320 * 1024,
    'lines': 768 * 1024,
    'trend-shard': 2 * 1024 * 1024,
    'cfb-teams': 256 * 1024,
    'cfb-defense': 512 * 1024,
}
SHELL_FILES = ('index.html', 'app.css', 'app.js')
NEAR_FRACTION = .90


def size_warning(name, size, limit):
    if size > limit:
        return f'{name}:{size}>{limit}'
    if size >= int(limit * NEAR_FRACTION):
        return f'{name}:{size}/{limit}:near'
    return None


def check(site=SITE):
    site = Path(site)
    issues, warnings = [], []
    shell = 0
    for name in SHELL_FILES:
        path = site / name
        if not path.is_file():
            issues.append(f'shell:{name}:missing')
        else:
            shell += len(gzip.compress(path.read_bytes(), mtime=0))
    if shell > LIMITS['shell-gzip']:
        issues.append(f'shell-gzip:{shell}>{LIMITS["shell-gzip"]}')
    more = site / 'app-more.js'
    lazy_more = 0
    if not more.is_file():
        warnings.append('lazy-more-gzip:missing')
    else:
        lazy_more = len(gzip.compress(more.read_bytes(), mtime=0))
        warning = size_warning('lazy-more-gzip', lazy_more, LIMITS['lazy-more-gzip'])
        if warning:
            warnings.append(warning)
    files = {
        'today': site / 'data/app/today.json',
        'lines-NFL': site / 'data/app/lines-NFL.json',
        'lines-CFB': site / 'data/app/lines-CFB.json',
        'cfb-teams': site / 'data/app/teams/CFB.json',
        'cfb-defense': site / 'data/app/teams/CFB-defense.json',
    }
    for name, path in files.items():
        limit = LIMITS['lines'] if name.startswith('lines-') else LIMITS[name]
        if not path.is_file():
            warnings.append(f'{name}:missing')
        else:
            warning = size_warning(name, path.stat().st_size, limit)
            if warning:
                warnings.append(warning)
    trends = site / 'data/app/trends'
    index = trends / 'index.json'
    if not index.is_file():
        warnings.append('trends-index:missing')
    if (site / 'data/app/trends.json').exists():
        warnings.append('trends-monolith:present')
    for path in trends.glob('*.json') if trends.is_dir() else ():
        if path.name != 'index.json':
            warning = size_warning(f'trend-shard:{path.name}', path.stat().st_size, LIMITS['trend-shard'])
            if warning:
                warnings.append(warning)
    return {'shellGzip': shell, 'lazyMoreGzip': lazy_more, 'issues': issues, 'warnings': warnings}


def main(site=SITE):
    result = check(site)
    print(json.dumps(result, sort_keys=True))
    for warning in result['warnings']:
        print(f'::warning title=Phone-first data budget::{warning}')
    return 1 if result['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
