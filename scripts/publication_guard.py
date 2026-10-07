"""Read-only boundary check of the exact static website folder before upload.

This is not a paywall, source-license review, or general secret detector. It
prevents unreviewed file families, known private desk artifacts and recognizable
credentials from silently becoming public. Never echo a matched value.
"""
import argparse
import json
import os
import re
from pathlib import Path

ROOT_FILES = {'.nojekyll', 'index.html', 'app.css', 'app.js', 'app-more.js', 'core.js', 'live.js', 'personal.js',
              'favicon.svg', 'kookn-chef.png', 'kookn.jpg', 'kookn-mark.png'}
DATA_FILES = {'slate.json', 'research-context.json', 'desk-notes.json', 'sports.json',
              'research.json', 'scoreboard.json', 'player-history.json', 'opponent-history.json',
              'market-lab.json', 'market-lines.json', 'depth-charts.json', 'player-identity.json',
              'scoreboard-games.json', 'forecasts.json', 'feed.xml'}
APP_FILES = {'today.json', 'record.json', 'lines.json', 'lines-NFL.json', 'lines-CFB.json',
             'research.json', 'sport-research.json'}
PRIVATE_NAMES = {'env', '.env', 'desk-health.html', 'desk-health.json', 'desk-health-state.json',
                 'desk-reliability.json', 'reliability-history.json', 'live-watch.json',
                 'live-progress.json', 'x-posted.json', 'status.json', 'policy.json',
                 'featured.json', 'review-packet.md'}
PRIVATE_DIRS = {'.git', '.config', 'pending', 'failed', 'x-drafts', 'learning', 'private'}
PRIVATE_KEYS = {'apikey', 'accesstoken', 'refreshtoken', 'clientsecret', 'password',
                'webhookurl', 'discordwebhookurl', 'discordreviewwebhookurl',
                'authorization', 'privatekey', 'bufferaccesstoken'}
TEXT_SUFFIXES = {'.html', '.css', '.js', '.json', '.xml', '.svg'}
MAX_TEXT_BYTES = 64 * 1024 * 1024
PATTERNS = (
    re.compile(r'https?://(?:[^/\s]*\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/\d+/[^\s"<>]+', re.I),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}'),
    re.compile(r'(?i)[?&](?:api[_-]?key|access[_-]?token|client[_-]?secret)=[^&\s"<>]{8,}'),
    re.compile(r'(?:/Users/[^/\s]+/\.config/keenroudy|/home/[^/\s]+/\.config/keenroudy)'),
)


def allowed_path(relative):
    parts = relative.parts
    if len(parts) == 1:
        return parts[0] in ROOT_FILES
    if any(p.startswith('.') or p.lower() in PRIVATE_DIRS for p in parts):
        return False
    if any(p.lower() in PRIVATE_NAMES or p.lower().startswith(('review-packet-', 'review-20')) for p in parts):
        return False
    value = relative.as_posix()
    if parts[0] == 'img':
        return relative.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
    if len(parts) == 2 and parts[0] == 'data':
        return parts[1] in DATA_FILES
    if len(parts) == 3 and parts[:2] == ('data', 'cards'):
        return bool(re.fullmatch(r'[A-Za-z0-9_.-]+\.(png|svg)', parts[2]))
    if parts[:2] != ('data', 'app'):
        return False
    if len(parts) == 3:
        return parts[2] in APP_FILES
    return bool(re.fullmatch(r'data/app/(?:games/(?:NFL|CFB)-[A-Za-z0-9_-]+|'
                             r'player-charts/(?:NFL|CFB)|players/(?:NFL|CFB)(?:/\d+)?|'
                             r'teams/(?:NFL|CFB)(?:/\d+)?|teams/CFB-defense|'
                             r'trends/(?:index|(?:NFL|CFB)-\d{4}-\d{2}-\d{2}(?:-milestones)?(?:-part-[1-9]\d*)?))\.json', value))


def contains_private_key(value):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r'[^a-z0-9]', '', str(key).lower())
            if normalized in PRIVATE_KEYS or contains_private_key(child):
                return True
    elif isinstance(value, list):
        return any(contains_private_key(item) for item in value)
    return False


def audit(folder):
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        return {'filesChecked': 0, 'bytesChecked': 0, 'issues': [{'file': '.', 'reason': 'invalid-site-root'}]}
    issues, files, size = [], 0, 0

    def issue(relative, reason):
        issues.append({'file': relative.as_posix(), 'reason': reason})

    def walk_error(_error):
        issues.append({'file': '.', 'reason': 'unreadable-directory'})

    for parent, directories, filenames in os.walk(folder, followlinks=False, onerror=walk_error):
        for name in list(directories):
            path = Path(parent) / name
            relative = path.relative_to(folder)
            if path.is_symlink() or name.startswith('.') or name.lower() in PRIVATE_DIRS:
                issue(relative, 'private-or-linked-directory')
                directories.remove(name)
        for name in sorted(filenames):
            path = Path(parent) / name
            relative = path.relative_to(folder)
            files += 1
            if path.is_symlink():
                issue(relative, 'linked-file')
                continue
            if not allowed_path(relative):
                issue(relative, 'unreviewed-public-path')
                continue
            try:
                length = path.stat().st_size
                size += length
                if path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                if length > MAX_TEXT_BYTES:
                    issue(relative, 'text-too-large-to-check')
                    continue
                text = path.read_text(encoding='utf-8')
                if any(pattern.search(text) for pattern in PATTERNS):
                    issue(relative, 'private-value-pattern')
                if path.suffix.lower() == '.json':
                    try:
                        payload = json.loads(text)
                        if contains_private_key(payload):
                            issue(relative, 'private-payload-field')
                    except (ValueError, RecursionError):
                        issue(relative, 'invalid-json')
            except (OSError, UnicodeError):
                issue(relative, 'unreadable-file')
    if not (folder / 'index.html').is_file():
        issue(Path('index.html'), 'missing-entry-point')
    return {'filesChecked': files, 'bytesChecked': size, 'issues': issues}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1] / 'site')
    args = parser.parse_args(argv)
    result = audit(args.site)
    print(json.dumps(result, sort_keys=True))
    return 1 if result['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
