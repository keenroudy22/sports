"""How much of last season's team is still here, from the box-score store. Deterministic, stdlib only.

The score model discounts last season with one number per league (priorWeight). That treats a team
that returned everyone and a team that lost six starters and its coordinator the same way. This module
measures, per team and per side of the ball, the share of last season's usage that belongs to players
who have appeared for the team this season, strictly as of a cutoff:

  offense  attempts, carries and targets in last season's box scores; a player counts as returned once
           he has a line for the team in a game that kicked off before the cutoff (both leagues)
  defense  needs snap counts, which the store holds for NFL skill players only, so it is None for now

Before a team's first game of the season nothing is known and the value is None, which the model reads
as the league average, so continuity changes nothing until the games say something. It never reads
transactions, depth charts or rosters: appearances only, with no future leakage.
"""
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features


def touches(player, league, has_plays=True):
    """Attempts, carries and targets on one box-score line."""
    unified = features.unified(player, league, has_plays)
    return (player.get('att') or 0) + (player.get('car') or 0) + (unified.get('targets') or 0)


def offense_usage(records, season):
    """team -> {player: touches} over one season's stored games."""
    usage = defaultdict(lambda: defaultdict(float))
    for game in records:
        if game['season'] != season:
            continue
        has_plays = game.get('quality', {}).get('plays') == 'ok'
        for player in game['players']:
            team = player.get('team')
            if team is None:
                continue
            used = touches(player, game['league'], has_plays)
            if used:
                usage[str(team)][str(player['id'])] += used
    return {team: dict(players) for team, players in usage.items()}


def appeared(records, season, cutoff):
    """team -> players with a box-score line for the team this season, in games kicked off before the cutoff."""
    seen = defaultdict(set)
    for game in records:
        if game['season'] != season or features.when(game['kickoff']) >= cutoff:
            continue
        for player in game['players']:
            if player.get('team') is not None:
                seen[str(player['team'])].add(str(player['id']))
    return dict(seen)


def offense_continuity(records, season, cutoff):
    """team -> share of last season's offensive usage by players who have appeared this season, or None.

    None before the team's first game of the season (nothing is known yet) and for a team with no
    stored usage last season (nothing to return to).
    """
    last = offense_usage(records, season - 1)
    here = appeared(records, season, cutoff)
    out = {}
    for team, usage in last.items():
        total = sum(usage.values())
        if team not in here or not total:
            out[team] = None
            continue
        out[team] = sum(v for pid, v in usage.items() if pid in here[team]) / total
    return out


def continuity(records, season, cutoff):
    """team -> {'off': share or None, 'def': None}; defense waits for defensive snap counts in the store."""
    offense = offense_continuity(records, season, cutoff)
    return {team: {'off': value, 'def': None} for team, value in offense.items()}


def league_mean(table, side='off'):
    values = [v[side] for v in table.values() if v.get(side) is not None]
    return statistics.mean(values) if values else None


def summary(table):
    """A short, honest account of what the table knows, for a snapshot's inputs."""
    known = [v['off'] for v in table.values() if v['off'] is not None]
    return {'teams': len(table), 'known': len(known),
            'offenseMean': round(statistics.mean(known), 3) if known else None,
            'offenseLow': round(min(known), 3) if known else None, 'offenseHigh': round(max(known), 3) if known else None,
            'defense': 'not measured: the store holds no defensive lines'}
