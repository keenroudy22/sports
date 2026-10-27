"""Keep slow release verification outside the desk's publication lock.

The caller verifies a fixed candidate against a recorded production head. Promotion
must abort and repeat verification if either head changed while the desk worked.
"""
import fcntl
import subprocess
import time
from contextlib import contextmanager


def head(path):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip()


@contextmanager
def bounded_lock(lock_path, timeout=900, *, clock=time.monotonic, sleep=time.sleep):
    """Wait for a legitimate holder without stealing its lock or waiting forever."""
    deadline = clock() + timeout
    with open(lock_path, 'a') as handle:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                remaining = deadline - clock()
                if remaining <= 0:
                    raise TimeoutError(f'Lock occupied for {timeout}s: {lock_path}')
                sleep(min(5, remaining))
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def promotion_lock(lock_path, production, candidate, tested_base, tested_candidate):
    with open(lock_path, 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if head(production) != tested_base or head(candidate) != tested_candidate:
            raise RuntimeError('Release inputs changed; release lock and repeat verification')
        yield
