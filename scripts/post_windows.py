"""Shared, owner-approved X windows. Pure time math, no posting or feeds."""
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/New_York')
LEAD = timedelta(minutes=45)
SPACING = timedelta(minutes=20)
SOON = timedelta(minutes=2)
DISCORD_PLAY_LEAD = timedelta(minutes=15)
DISCORD_DELIVERY_CADENCE = timedelta(minutes=5)


def instant(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def international(league, kickoff):
    local = instant(kickoff).astimezone(EASTERN)
    return local.hour * 60 + local.minute < 10 * 60 + 30


def opens(league, kickoff):
    local = instant(kickoff).astimezone(EASTERN)
    hour, minute = (8, 30) if international(league, kickoff) else (9, 30)
    return local.replace(hour=hour, minute=minute, second=0, microsecond=0).astimezone(timezone.utc)


def target(league, kickoff):
    start = instant(kickoff)
    return opens(league, start)


def jitter(post_id):
    """Stable zero-to-six-minute shift, so posts do not read like a clocked bot."""
    return timedelta(minutes=int(hashlib.sha1(str(post_id).encode('utf-8')).hexdigest(), 16) % 7)


def delivery_ready(now):
    """First twenty-minute X slot that leaves time for the Discord-first delivery."""
    earliest = instant(now).astimezone(timezone.utc) + DISCORD_PLAY_LEAD + DISCORD_DELIVERY_CADENCE + SOON
    tick = int(SPACING.total_seconds())
    return datetime.fromtimestamp(((int(earliest.timestamp()) + tick - 1) // tick) * tick, tz=timezone.utc)


def reachable(league, kickoff, now, occupied=0):
    return max(target(league, kickoff) + SPACING * occupied, delivery_ready(now)) <= instant(kickoff) - LEAD
