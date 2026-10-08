"""Keep lazy browser assets keyed to their bytes, not a hand-maintained number."""
import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
BUNDLES = (('MORE_ASSET', 'app-more.js'), ('GAMES_ASSET', 'app-games.js'))


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def declaration(constant, name):
    return re.compile(rf"const {constant} = '{re.escape(name)}\?v=[^']+';")


def expected(site=SITE, constant='MORE_ASSET', name='app-more.js'):
    site = Path(site)
    return f"const {constant} = '{name}?v=sha256-{fingerprint(site / name)}';"


def sync(site=SITE, check=False):
    """Rewrite every stale declaration; return the names of the bundles whose version changed."""
    site = Path(site)
    app = site / 'app.js'
    source = app.read_text(encoding='utf-8')
    changed = []
    for constant, name in BUNDLES:
        if not (site / name).is_file():
            continue
        pattern = declaration(constant, name)
        wanted = expected(site, constant, name)
        matches = pattern.findall(source)
        if len(matches) != 1:
            raise ValueError(f'{app}: expected one {constant} declaration, found {len(matches)}')
        if matches[0] == wanted:
            continue
        if check:
            raise ValueError(f'{app}: {name} content fingerprint is stale')
        source = pattern.sub(wanted, source)
        changed.append(name)
    if changed:
        app.write_text(source, encoding='utf-8', newline='\n')
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    changed = sync(check=args.check)
    print('lazy bundle fingerprints ' + (f"updated: {', '.join(changed)}" if changed else 'current'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
