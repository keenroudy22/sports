"""Useful, verified injury angles for X. Stdlib only.

An injury post is deliberately harder to create than an ordinary headline:

* ESPN has listed a top skill player out, doubtful or inactive recently;
* a newer player projection explicitly removed that player and redistributed the role;
* a sportsbook price captured after the news is on the board; and
* the recalculated projection still leans to one side of that price.

That lets the desk explain a real prop angle without treating stale projections or
an unpriced replacement role as a play. The post is a board read, not part of the
published-play record. Buffer handles spacing, the daily ceiling and Discord.
"""
from datetime import timedelta

import features
import gates
import pricing
import x_post

FRESH = timedelta(hours=12)
LEAD = timedelta(minutes=20)
MAX_PER_DAY = 2
HARD = {'out', 'doubtful', 'inactive', 'suspension', 'injured reserve'}
SKILL = {'QB', 'RB', 'WR', 'TE'}


def mean(player, stat):
    value = player.get(stat)
    if isinstance(value, (list, tuple)) and value:
        return float(value[0] or 0)
    if isinstance(value, dict):
        return float(value.get('mean') or 0)
    return 0.0


def side_player(snapshot, side, athlete):
    block = ((snapshot.get('players') or {}).get(side) or {}) if snapshot else {}
    return next((p for p in block.get('players') or [] if str(p.get('id')) == str(athlete)), None)


def usage(player):
    pos = player.get('pos')
    if pos == 'QB':
        return mean(player, 'att')
    if pos == 'RB':
        return mean(player, 'carries') + mean(player, 'targets')
    return mean(player, 'targets')


def star_before(ctx, game, side, athlete, reported):
    """Was this the team's highest-usage player at his position before the news?"""
    snapshots = [s for s in ctx.snapshots.get(game['id'], []) if gates.when(s.get('publishedAt')) <= reported]
    old = snapshots[-1] if snapshots else None
    player = side_player(old, side, athlete)
    if not player or player.get('pos') not in SKILL:
        return False
    if player.get('pos') == 'QB' and str(ctx.starters.get(gates.team_key(game['league'], game[side]['id']))) == str(athlete):
        return True
    peers = [p for p in ((((old or {}).get('players') or {}).get(side) or {}).get('players') or [])
             if p.get('pos') == player.get('pos')]
    return bool(peers) and usage(player) == max(usage(p) for p in peers) and usage(player) > 0


def fresh_after(ctx, game, side, athlete, reported):
    """Latest public projection, only when it was rebuilt after and includes this absence."""
    snapshot = ctx.snapshot(game['id'])
    if not snapshot or gates.when(snapshot.get('publishedAt')) < reported:
        return None
    removed = (((snapshot.get('inputs') or {}).get('ruledOut') or {}).get(side) or [])
    return snapshot if str(athlete) in {str(p) for p in removed} else None


def player_side(snapshot, athlete):
    for side in ('home', 'away'):
        if side_player(snapshot, side, athlete):
            return side
    return None


def prop_angle(lines, game, snapshot, injured, team_side, reported):
    """Best positively graded, post-news price for a healthy teammate."""
    choices = []
    for row in lines:
        grade = row.get('grade') or {}
        athlete = str(row.get('athleteId') or '')
        if row.get('gameId') != game['id'] or row.get('state') != 'open' or not athlete or athlete == str(injured):
            continue
        if row.get('position') not in SKILL or player_side(snapshot, athlete) != team_side:
            continue
        if grade.get('view') != 'lean' or grade.get('limited') or not isinstance(row.get('odds'), (int, float)):
            continue
        if not row.get('observedAt') or gates.when(row['observedAt']) < reported:
            continue
        if not grade.get('snapshotAt') or gates.when(grade['snapshotAt']) < reported:
            continue
        choices.append(row)
    return max(choices, key=lambda row: float((row.get('grade') or {}).get('edge') or 0), default=None)


def defense_note(records, game, team_side, angle):
    group, stat = features.GROUP.get(angle.get('position')), angle.get('stat')
    if not group or not stat:
        return ''
    opponent = game['away' if team_side == 'home' else 'home']
    rows = features.defense_table(features.defense_logs(records), f'{group}.{stat}', season=game['season'])
    row = next((r for r in rows if str(r['defense']) == str(opponent['id'])), None)
    if not row:
        return ''
    return (f"{opponent['abbreviation']} allows {row['avg']:g} {pricing.WORDS[stat]}/game to {group}s "
            f"through {row['n']} game{'s' if row['n'] != 1 else ''}.")


def text(injury, game, angle, note):
    status = str(injury['status']).upper()
    matchup = f"{game['away']['abbreviation']} at {game['home']['abbreviation']}"
    prop = (f"{angle['player']} {str(angle['direction']).lower()} {pricing.fmt(float(angle['line']))} "
            f"{angle['market']} ({int(angle['odds']):+d}, {angle['book']})")
    body = (f"🚨 ESPN lists {injury['name']} {status} for {matchup}.\n\n"
            f"Fresh board: {prop}.\n"
            f"{note + chr(10) if note else ''}\n"
            "Board lean, not a posted play. Take it or pass? #NFL")
    return body


def candidates(ctx, records, lines, now, log_book, games=None):
    """At most two new injury-angle posts, newest news first."""
    posted = {str(p.get('id')) for p in log_book.get('posts', [])}
    today = now.astimezone(gates.EASTERN).date()
    used = sum(1 for p in log_book.get('posts', []) if p.get('kind') == 'buffer:news' and p.get('dueAt')
               and not p.get('cancelledAt') and not p.get('deletedAt')
               and gates.when(p['dueAt']).astimezone(gates.EASTERN).date() == today)
    out = []
    for game in (games if games is not None else getattr(ctx, 'games', {})).values():
        kickoff = gates.when(game['kickoff'])
        if game.get('league') != 'NFL' or game.get('state') != 'pre' or not now < kickoff - LEAD:
            continue
        for side in ('home', 'away'):
            injuries = ctx.injuries.get(gates.team_key('NFL', game[side]['id']), {})
            for athlete, injury in injuries.items():
                status = str(injury.get('status') or '').lower()
                source, raw_reported = str(injury.get('source') or ''), injury.get('reportedAt')
                if status not in HARD or injury.get('position') not in SKILL or not source.startswith('https://www.espn.com/') or not raw_reported:
                    continue
                try:
                    reported = gates.when(raw_reported)
                except (TypeError, ValueError):
                    continue
                if reported > now or now - reported > FRESH or not star_before(ctx, game, side, athlete, reported):
                    continue
                key = f"news:{game['id']}:{athlete}:{status.replace(' ', '-')}"
                if key in posted:
                    continue
                snapshot = fresh_after(ctx, game, side, athlete, reported)
                angle = prop_angle(lines, game, snapshot, athlete, side, reported) if snapshot else None
                if not angle:
                    continue
                copy = text(injury, game, angle, defense_note(records, game, side, angle))
                if x_post.tweet_length(copy) > 280:
                    copy = text(injury, game, angle, '')
                if x_post.tweet_length(copy) <= 280:
                    out.append({'key': key, 'kind': 'news', 'text': copy, 'target': now,
                                'deadline': kickoff - LEAD, 'reportedAt': raw_reported, 'source': source})
    out.sort(key=lambda p: gates.when(p['reportedAt']), reverse=True)
    return out[:max(0, MAX_PER_DAY - used)]
