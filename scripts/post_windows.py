"""Shared, owner-approved X windows. Pure time math, no posting or feeds."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/New_York')
LEAD = timedelta(minutes=45)
SPACING = timedelta(minutes=10)
SOON = timedelta(minutes=2)


def instant(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def international(league, kickoff):
    local = instant(kickoff).astimezone(EASTERN)
    return league == 'NFL' and (local.hour, local.minute) == (9, 30)


def opens(league, kickoff):
    local = instant(kickoff).astimezone(EASTERN)
    hour, minute = (8, 30) if international(league, kickoff) else (9, 0)
    return local.replace(hour=hour, minute=minute, second=0, microsecond=0).astimezone(timezone.utc)


def target(league, kickoff):
    start = instant(kickoff)
    if international(league, start):
        return opens(league, start)
    noon = start.astimezone(EASTERN).replace(hour=12, minute=0, second=0, microsecond=0)
    return max(min(noon.astimezone(timezone.utc), start - timedelta(hours=2)), opens(league, start))


def reachable(league, kickoff, now, occupied=0):
    return max(target(league, kickoff) + SPACING * occupied, instant(now) + SOON) <= instant(kickoff) - LEAD
