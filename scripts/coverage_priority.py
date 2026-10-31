"""Prospective owner coverage priority; never a probability or admission override."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EFFECTIVE = datetime(2026, 10, 30, 12, 48, 32, tzinfo=timezone.utc)
EASTERN = ZoneInfo('America/New_York')


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
    if league in ('NBA', 'NFL'):
        return 0
    if league == 'CFB':
        try:
            start = datetime.fromisoformat(kickoff.replace('Z', '+00:00')) if isinstance(kickoff, str) else kickoff
            if start is not None and start.tzinfo is not None and start.astimezone(EASTERN).weekday() >= 5:
                return 0
        except (ValueError, TypeError, AttributeError):
            pass
    return 1


def candidate_tier(candidate, ctx, league=None):
    game = ctx.games.get((candidate.get('gameIds') or [candidate.get('gameId')])[0]) or {}
    return tier(league or candidate.get('league') or candidate.get('_league') or game.get('league'),
                game.get('kickoff') or candidate.get('kickoff'), ctx.now)
