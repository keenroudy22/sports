"""Run both suites from only the current Git-visible files, without built page payloads."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def visible_files(root=ROOT):
    root = Path(root)
    try:
        output = subprocess.check_output(
            ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            cwd=root,
            stderr=subprocess.DEVNULL,
        )
        return [Path(raw.decode()) for raw in output.split(b'\0') if raw]
    except subprocess.CalledProcessError:
        # The exported fixture intentionally has no .git directory.  Re-exporting
        # it in its own test should use that already-clean tree, not fail because
        # Git metadata was deliberately left behind.
        return [
            path.relative_to(root)
            for path in root.rglob('*')
            if path.is_file()
            and '.git' not in path.parts
            and '__pycache__' not in path.parts
            and path.suffix not in {'.pyc', '.pyo'}
        ]


def export(root, destination):
    root, destination = Path(root), Path(destination)
    for relative in visible_files(root):
        if relative.parts[:3] == ('site', 'data', 'app'):
            continue
        source, target = root / relative, destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
    generated = destination / 'site/data/app'
    if generated.exists():
        raise RuntimeError(f'clean export unexpectedly contains {generated}')
    return destination


def run(root=ROOT):
    with tempfile.TemporaryDirectory(prefix='kookn-clean-export-') as folder:
        checkout = export(root, Path(folder))
        environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                       cwd=checkout, env=environment, check=True)
        node_tests = sorted(str(path.relative_to(checkout)) for path in (checkout / 'tests').glob('*.test.js'))
        if not node_tests:
            raise RuntimeError('clean export contains no frontend tests')
        subprocess.run(['node', '--test', *node_tests], cwd=checkout, env=environment, check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
