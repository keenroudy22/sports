"""Shared current-season/current-stage straight record math for generated artwork.

This mirrors the public site's ``recordArchive(..., current, current)`` and
``recordBreakdown(...).all`` rules.  It does not alter the append-only record;
it only supplies the same headline to cards at a particular publication time.
"""
from datetime import datetime


RESULTS = ('win', 'loss', 'push', 'void')


def instant(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def season_of(pick):
    try:
        value = int(pick.get('season'))
    except (TypeError, ValueError, AttributeError):
        return None
    return value if 1900 <= value <= 2200 else None


def league_of(pick):
    value = str(pick.get('league') or '').strip()
    return value or str(pick.get('id') or 'OTHER').split('-', 1)[0] or 'OTHER'


def phase_of(pick):
    value = str(pick.get('seasonType') if pick.get('seasonType') is not None else pick.get('stage') or '').lower()
    return 'playoffs' if value == '3' or 'post' in value or 'playoff' in value else 'regular'


def is_parlay(pick):
    return bool(pick.get('legs')) or bool(pick.get('parlayType')) or pick.get('kind') == 'parlays'


def is_unpriced_import(pick):
    return bool(pick.get('historicalImport')) and pick.get('odds') is None


def is_headline(pick):
    return not pick.get('lane') or pick.get('lane') in ('best_bet', 'hot_plate')


def current_rows(rows, at):
    """Current season/stage rows that were public by ``at``, matching the site default."""
    at = instant(at) if not isinstance(at, datetime) else at
    visible = []
    for pick in rows:
        published = instant(pick.get('publishedAt'))
        if at and published and published > at:
            continue
        if is_unpriced_import(pick):
            continue
        visible.append(pick)
    current = {}
    for pick in visible:
        season, league = season_of(pick), league_of(pick)
        if season is not None and (current.get(league) is None or season > current[league]):
            current[league] = season
    base = [pick for pick in visible
            if current.get(league_of(pick)) is None
            or season_of(pick) == current[league_of(pick)]]
    phase = {}
    for pick in base:
        league = league_of(pick)
        phase.setdefault(league, 'regular')
        if phase_of(pick) == 'playoffs':
            phase[league] = 'playoffs'
    return [pick for pick in base if phase_of(pick) == phase.get(league_of(pick), 'regular')]


def summary(rows, at):
    """The site's current Season W/L/P/V headline as it stood at ``at``."""
    at = instant(at) if not isinstance(at, datetime) else at
    settled = []
    for pick in current_rows(rows, at):
        if is_parlay(pick) or not is_headline(pick) or pick.get('result') not in RESULTS:
            continue
        # Priced Week 1 imports arrived as already-final rows and do not all carry a
        # separate settledAt.  Their publication time is when they entered the
        # public record, so it is the correct as-of boundary for those rows.
        when = instant(pick.get('settledAt') or (pick.get('publishedAt') if pick.get('historicalImport') else None))
        if at and (not when or when > at):
            continue
        settled.append(pick)
    keys = {'win': 'wins', 'loss': 'losses', 'push': 'pushes', 'void': 'voids'}
    return {keys[name]: sum(pick.get('result') == name for pick in settled)
            for name in RESULTS}


def merged_summary(first, latest, at):
    return summary([dict(pick, **(latest.get(key) or {})) for key, pick in first.items()], at)


def text(value):
    result = f"{int(value.get('wins', 0))}–{int(value.get('losses', 0))}"
    if value.get('pushes'):
        result += f"–{int(value['pushes'])}"
    return result
