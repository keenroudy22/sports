"""Prospective social presentation only; private Climb accounting stays in dollars."""
import math
from datetime import datetime, timezone
import staking

EFFECTIVE = datetime(2026, 10, 25, tzinfo=timezone.utc)


def active(pick):
    for key in ('settledAt', 'publishedAt'):
        try:
            when = datetime.fromisoformat(str(pick.get(key)).replace('Z', '+00:00'))
            if when.tzinfo and when >= EFFECTIVE:
                return True
        except (ValueError, TypeError):
            pass
    return False


def label(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Social units require a known nonnegative amount')
    return f'{value:.2f}'.rstrip('0').rstrip('.') + 'u'


def climb(value):
    # This conversion is the existing exposure rule, never a new starting stake.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Climb amount unavailable')
    return label(value / staking.OWNER_UNIT)
