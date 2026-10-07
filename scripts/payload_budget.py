"""Fail the publish when phone-first public payloads regress past reviewed size ceilings."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
LIMITS = {
    'shell-gzip': 92 * 1024,
    'today': 320 * 1024,
    'lines': 768 * 1024,
    'trend-shard': 2 * 1024 * 1024,
    'cfb-teams': 256 * 1024,
    'cfb-defense': 512 * 1024,
}


def check(site=SITE):
    site = Path(site)
    issues = []
    shell = sum(len(gzip.compress((site / name).read_bytes(), mtime=0)) for name in ('index.html', 'app.css', 'app.js'))
    if shell > LIMITS['shell-gzip']:
        issues.append(f'shell-gzip:{shell}>{LIMITS["shell-gzip"]}')
    files = {
        'today': site / 'data/app/today.json',
        'lines': site / 'data/app/lines.json',
        'cfb-teams': site / 'data/app/teams/CFB.json',
        'cfb-defense': site / 'data/app/teams/CFB-defense.json',
    }
    for name, path in files.items():
        if not path.is_file():
            issues.append(f'{name}:missing')
        elif path.stat().st_size > LIMITS[name]:
            issues.append(f'{name}:{path.stat().st_size}>{LIMITS[name]}')
    trends = site / 'data/app/trends'
    index = trends / 'index.json'
    if not index.is_file():
        issues.append('trends-index:missing')
    if (site / 'data/app/trends.json').exists():
        issues.append('trends-monolith:present')
    for path in trends.glob('*.json') if trends.is_dir() else ():
        if path.name != 'index.json' and path.stat().st_size > LIMITS['trend-shard']:
            issues.append(f'trend-shard:{path.name}:{path.stat().st_size}>{LIMITS["trend-shard"]}')
    return {'shellGzip': shell, 'issues': issues}


def main():
    result = check()
    print(json.dumps(result, sort_keys=True))
    return 1 if result['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
