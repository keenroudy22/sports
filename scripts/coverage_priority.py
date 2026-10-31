"""Prospective owner coverage priority; never a probability or admission override."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EFFECTIVE = datetime(2026, 10, 30, 12, 48, 32, tzinfo=timezone.utc)
EASTERN = ZoneInfo('America/New_York')
PROPS_FOCUS_FROM = datetime(2026,10,31,11,25,tzinfo=timezone.utc)


def active(now):
    return now >= EFFECTIVE


def tier(league, kickoff, now):
    """NBA/NFL and Saturday/Sunday CFB first, then weekday CFB.

    Use the game's Eastern date, not the worker's weekday or its UTC date.
    Historical runs retain their original ordering. Unknown dates never earn
    weekend priority; this helper cannot authorize a play or manufacture a quote.
    """
    if not active(now):
        return 0
    day = kickoff_day(kickoff)
    future = day is not None and day > now.astimezone(EASTERN).date()
    if league in ('NBA', 'NFL'):
        return 2 if now >= PROPS_FOCUS_FROM and future else 0
    if league == 'CFB' and day is not None and day.weekday() >= 5:
        return (3 if future else 1) if now >= PROPS_FOCUS_FROM else 0
    return 4 if now >= PROPS_FOCUS_FROM else 1


def kickoff_day(kickoff):
    try:
        start = datetime.fromisoformat(kickoff.replace('Z', '+00:00')) if isinstance(kickoff, str) else kickoff
        return start.astimezone(EASTERN).date() if start is not None and start.tzinfo is not None else None
    except (ValueError,TypeError,AttributeError):
        return None


def research_only(league, kickoff, now):
    day=kickoff_day(kickoff)
    return now >= PROPS_FOCUS_FROM and league == 'CFB' and (day is None or day.weekday() < 5)


def candidate_tier(candidate, ctx, league=None):
    game = ctx.games.get((candidate.get('gameIds') or [candidate.get('gameId')])[0]) or {}
    return tier(league or candidate.get('league') or candidate.get('_league') or game.get('league'),
                game.get('kickoff') or candidate.get('kickoff'), ctx.now)
