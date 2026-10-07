"""Keep lazy browser assets keyed to their bytes, not a hand-maintained number."""
import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
DECLARATION = re.compile(r"const MORE_ASSET = 'app-more\.js\?v=[^']+';")


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def expected(site=SITE):
    site = Path(site)
    return f"const MORE_ASSET = 'app-more.js?v=sha256-{fingerprint(site / 'app-more.js')}';"


def sync(site=SITE, check=False):
    site = Path(site)
    app = site / 'app.js'
    source = app.read_text(encoding='utf-8')
    wanted = expected(site)
    matches = DECLARATION.findall(source)
    if len(matches) != 1:
        raise ValueError(f'{app}: expected one MORE_ASSET declaration, found {len(matches)}')
    if matches[0] == wanted:
        return False
    if check:
        raise ValueError(f'{app}: app-more.js content fingerprint is stale')
    app.write_text(DECLARATION.sub(wanted, source), encoding='utf-8', newline='\n')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    changed = sync(check=args.check)
    print('app-more.js fingerprint ' + ('updated' if changed else 'current'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
