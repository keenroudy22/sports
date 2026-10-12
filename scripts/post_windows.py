"""Shared, owner-approved X windows. Pure time math, no posting or feeds."""
import hashlib
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/New_York')
LEAD = timedelta(minutes=45)
SPACING = timedelta(minutes=20)
SOON = timedelta(minutes=2)
DISCORD_PLAY_LEAD = timedelta(minutes=15)
DISCORD_DELIVERY_CADENCE = timedelta(minutes=5)
LATE_CARD_X_DELAY = timedelta(minutes=10)
LATE_CARD_LEAD = timedelta(minutes=15)


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


def late_card_due(now):
    """Recovery slot for an already chosen play whose required card became live late.

    Discord is released immediately by the normal mirror and X follows roughly ten
    minutes later. This is not an admission window for a new play.
    """
    value = instant(now).astimezone(timezone.utc) + LATE_CARD_X_DELAY
    return value.replace(second=0, microsecond=0) + (timedelta(minutes=1) if value.second or value.microsecond else timedelta())


def late_card_reachable(kickoff, now):
    return late_card_due(now) <= instant(kickoff) - LATE_CARD_LEAD


def deadline(league, kickoff, now, replacement=False):
    """Late NFL night admissions keep a real Discord lead and 15 minutes before kickoff.

    The owner approved late game-day delivery on Oct 8, retained by Autopilot.
    Early games, daytime plays and replacements retain their ordinary deadline.
    """
    start, current = instant(kickoff), instant(now)
    local_start, local_now = start.astimezone(EASTERN), current.astimezone(EASTERN)
    enabled = os.environ.get('KEENROUDY_LATE_PRIMETIME_WINDOW', '1').strip().lower() not in ('0', 'false', 'off', 'no')
    late = (enabled and not replacement and league == 'NFL' and
            local_start.date() == local_now.date() and local_start.hour >= 19 and local_now.hour >= 17)
    return start - (LATE_CARD_LEAD if late else LEAD)


def reachable(league, kickoff, now, occupied=0, replacement=False):
    return max(target(league, kickoff) + SPACING * occupied, delivery_ready(now)) <= deadline(league, kickoff, now, replacement)
