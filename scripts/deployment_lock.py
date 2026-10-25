"""Keep slow release verification outside the desk's publication lock.

The caller verifies a fixed candidate against a recorded production head. Promotion
must abort and repeat verification if either head changed while the desk worked.
"""
import fcntl
import subprocess
from contextlib import contextmanager


def head(path):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip()


@contextmanager
def promotion_lock(lock_path, production, candidate, tested_base, tested_candidate):
    with open(lock_path, 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if head(production) != tested_base or head(candidate) != tested_candidate:
            raise RuntimeError('Release inputs changed; release lock and repeat verification')
        yield
