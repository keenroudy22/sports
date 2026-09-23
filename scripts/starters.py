"""Who starts at quarterback, and when the usual starter did not play. Deterministic, stdlib only.

The box-score store has no depth chart. A team's starter in a game is the passer with the most
attempts; its usual starter as of any moment is the modal starter over its last few games before
that moment. A game is flagged "quarterback out" for a team when its usual starter, known from
earlier games only, recorded no passing line in it. That is a proxy, read after the fact: it also
catches benchings and injuries in warmups, and it misses a starter who played hurt. The live flag
reads the injury report instead: the usual starter listed doubtful or worse.
"""
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features

RECENT = 4          # games that define the usual starter


def starter(game, team):
    """The passer with the most attempts for a team in one stored game, or None."""
    throwers = [p for p in game['players'] if str(p.get('team')) == str(team) and (p.get('att') or 0) > 0]
    if not throwers:
        return None
    return str(max(throwers, key=lambda p: (p.get('att') or 0, str(p['id'])))['id'])


def threw(game, team, pid):
    return any(str(p.get('team')) == str(team) and str(p['id']) == str(pid) and (p.get('att') or 0) > 0
               for p in game['players'])


def usual(recent_starters):
    """The modal starter over recent games, the most recent breaking ties; None with nothing to go on."""
    names = [s for s in recent_starters if s]
    if not names:
        return None
    counts = Counter(names)
    best = max(counts.values())
    return next(s for s in reversed(names) if counts[s] == best)


def qb_out_flags(records, cutoff=None, recent=RECENT):
    """(eventId, team) -> {'usual': pid, 'actual': pid, 'out': bool} for every stored game, in kickoff order.

    The usual starter for a game is read from that team's earlier games only, so nothing leaks
    forward. With a cutoff, only games before it are considered (and flagged).
    """
    flags, history = {}, defaultdict(lambda: deque(maxlen=recent))
    for game in sorted(records, key=lambda g: g['kickoff']):
        if cutoff is not None and features.when(game['kickoff']) >= cutoff:
            break
        for side in ('home', 'away'):
            team = str(game[side]['id'])
            expected = usual(history[team])
            actual = starter(game, team)
            out = expected is not None and not threw(game, team, expected)
            flags[(game['eventId'], team)] = {'usual': expected, 'actual': actual, 'out': out}
            history[team].append(actual)
    return flags


def usual_starter(records, team, cutoff, recent=RECENT):
    """The usual starter for a team as of a moment, from its last `recent` games before it."""
    games = sorted((g for g in records if features.when(g['kickoff']) < cutoff
                    and str(team) in (str(g['home']['id']), str(g['away']['id']))), key=lambda g: g['kickoff'])
    return usual([starter(g, team) for g in games[-recent:]])


def live_qb_out(records, team, ruled_out, cutoff, recent=RECENT):
    """Is the team's usual starter on the ruled-out list (doubtful, out, injured reserve, suspension)?"""
    pid = usual_starter(records, team, cutoff, recent)
    return pid is not None and str(pid) in {str(x) for x in ruled_out}


def count(flags):
    """How often the flag fires, for a tuning file."""
    fired = sum(1 for f in flags.values() if f['out'])
    return {'teamGames': len(flags), 'quarterbackOut': fired}
