"""Private roster/injury evidence packet; no forecast, admission or feed call.

Historical minutes/starts describe observed games, not tonight's confirmed role.
An absent box row is unknown; only an explicit DNP supplies zero minutes.
This does not clear the Trial's injury hold or infer points from box plus/minus.
"""
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boxscores
import gates
import nba_capture
import nba_roles


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def fresh(value, now, hours):
    try:
        return timedelta(0) <= now-boxscores.instant(value) <= timedelta(hours=hours)
    except (TypeError, ValueError):
        return False


def observed_role(boxes, team, athlete, season):
    window = [b for b in boxes if b['season'] == season and team in b.get('teams', {})][-5:]
    known, starts, minutes, sources = [], [], [], []
    for b in window:
        players = [p for p in b.get('players', []) if p.get('id') == athlete and p.get('team') == team]
        if len(players) != 1:
            continue
        p = players[0]
        value = 0 if p.get('dnp') is True else p.get('stats', {}).get('min')
        if not finite(value) or not 0 <= value <= 60:
            continue
        known.append(p)
        minutes.append(value)
        if type(p.get('starter')) is bool and not p.get('dnp'):
            starts.append(p['starter'])
        sources.append(dict(eventId=b['eventId'], kickoff=b['kickoff'],
                            receivedAt=b['retrievedAt'], source=b.get('source')))
    label = 'Limited or missing starting-role evidence'
    if len(starts) >= 3:
        label = ('Observed starter' if all(starts) else 'Observed bench player'
                 if not any(starts) else 'Observed mixed starting role')
    return dict(season=season, teamGames=len(window), knownPlayerRows=len(known),
                missingPlayerRows=len(window)-len(known),
                explicitDNPs=sum(p.get('dnp') is True for p in known),
                playedGames=sum(not p.get('dnp') for p in known),
                averageMinutesInKnownRows=round(sum(minutes)/len(minutes), 2) if minutes else None,
                starts=sum(starts) if starts else None, startObservations=len(starts),
                label=label, sources=sources)


def build(slate, injuries, boxes, rosters, now, target_date=None):
    target = str(target_date or gates.eastern_date(now))
    available = nba_roles.available_boxes(boxes, now)
    injury_fresh = fresh(injuries.get('retrievedAt'), now, 1)
    games = []
    for game in slate.get('games', []):
        try:
            if (game.get('status') != 'scheduled' or game.get('seasonType') != 'regular-season'
                    or boxscores.instant(game['kickoff']) <= now
                    or str(gates.eastern_date(boxscores.instant(game['kickoff']))) != target):
                continue
            season = game['season']
            teams = []
            for team in game['teams'].values():
                tid = team['id']
                roster = rosters.get(tid, {})
                roster_fresh = (roster.get('team') == tid and roster.get('season') == season
                                and roster.get('league') == 'NBA'
                                and fresh(roster.get('retrievedAt'), now, 24))
                roster_ids = {p.get('id') for p in roster.get('players', [])} if roster_fresh else set()
                # Never use future/stale injury observations to describe a current hold.
                rows = [r for r in injuries.get('rows', []) if r.get('team') == tid and nba_capture.blocks_availability(r.get('status'))]
                usable = injury_fresh and injuries.get('season') == season
                people = []
                for r in rows if usable else []:
                    athlete = r.get('athleteId')
                    people.append(dict(athleteId=athlete, name=r.get('name'), status=r['status'],
                        rosterVerified=roster_fresh and athlete in roster_ids,
                        currentSeason=observed_role(available, tid, athlete, season),
                        priorSeason=observed_role(available, tid, athlete, season-1),
                        injurySource=r.get('source'), injuryObservedAt=injuries.get('retrievedAt')))
                teams.append(dict(team=tid, name=team.get('name') or team.get('abbreviation'),
                    rosterVerified=bool(roster_fresh), rosterObservedAt=roster.get('retrievedAt'),
                    injurySnapshotUsable=usable, injuredPlayers=people,
                    hold='Team score model is not injury/roster adjusted' if people else
                         'Current injury evidence unavailable' if not usable else None))
            games.append(dict(eventId=game.get('providerId'), kickoff=game['kickoff'], teams=teams))
        except (KeyError, TypeError, ValueError):
            continue
    return dict(asOf=gates.stamp(now), targetDate=target, analysisOnly=True, admissionReady=False,
        games=games, injuryObservedAt=injuries.get('retrievedAt'),
        note='Observed roles only; no expected minutes, points adjustment, price edge or injury clearance.',
        nextAction='Review current roster and replacement workload, then evaluate a separate chronological team model before promotion.')


def from_stores(now, root=nba_capture.STORE, target_date=None):
    root = Path(root)
    def read(path, fallback):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return fallback
    rosters = {p.stem: read(p, {}) for p in (root/'rosters').glob('*.json')}
    boxes = [r for p in (root.parent/'sport-box').glob('nba-*.jsonl') for r in boxscores.read_store(p)]
    return build(read(root/'slate.json', {}), read(root/'injuries-current.json', {}),
                 boxes, rosters, now, target_date)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-date')
    parser.add_argument('--output', default='work/nba-team-context.json')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    report = from_stores(now, target_date=args.target_date)
    boxscores.write_json(Path(args.output), report)
    print(json.dumps(dict(path=args.output, games=len(report['games']), admissionReady=False)))
