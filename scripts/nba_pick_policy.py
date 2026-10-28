"""Prospective owner-directed NBA picks; historical trial terms stay frozen."""
from datetime import datetime, timezone

EFFECTIVE = datetime(2026, 10, 28, 18, 42, 40, tzinfo=timezone.utc)


def active(now=None):
    return (now or datetime.now(timezone.utc)) >= EFFECTIVE


def label(now=None):
    return 'NBA Picks' if active(now) else 'NBA Trial'


def daily_cap(now):
    return 5 if active(now) else 1
