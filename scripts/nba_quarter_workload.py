"""Reconstruct period minutes from the same official final-summary input.

Research evidence, not expected minutes, a void decision or a parlay model.
Any incomplete timeline, impossible lineup or unreconciled box holds the game.
"""
import math
import re
from collections import defaultdict


def extract(payload, box):
    players = {p['id']: p for p in box['players']}
    if len(players) != len(box['players']):
        return {}, 'duplicate player identity'
    lineups = {team: {key for key, p in players.items()
                      if p['team'] == team and p.get('starter') is True and not p.get('dnp')}
               for team in box['teams']}
    if len(lineups) != 2 or any(len(ids) != 5 for ids in lineups.values()):
        return {}, 'five verified starters per team required'
    periods, seen = defaultdict(list), {}
    for play in payload.get('plays') or []:
        key = play.get('id')
        if not key or key in seen and seen[key] != play:
            return {}, 'missing or conflicting play identity'
        if key in seen:
            continue
        seen[key] = play
        q = (play.get('period') or {}).get('number')
        clock_text = str((play.get('clock') or {}).get('displayValue', ''))
        clock = re.fullmatch(r'(\d{1,2}):([0-5]\d(?:\.\d+)?)', clock_text)
        short_clock = re.fullmatch(r'\d{1,2}(?:\.\d+)?', clock_text)
        sequence = str(play.get('sequenceNumber', ''))
        if type(q) is not int or not 1 <= q <= 20 or not (clock or short_clock) or not sequence.isdigit():
            return {}, 'period, clock or sequence unavailable'
        seconds = int(clock[1])*60+float(clock[2]) if clock else float(clock_text)
        if not clock and seconds >= 60:
            return {}, 'invalid seconds-only clock'
        if seconds > (720 if q <= 4 else 300):
            return {}, 'clock outside period'
        periods[q].append((int(sequence), seconds, play))
    if not periods or set(periods) != set(range(1, max(periods)+1)) or max(periods) < 4:
        return {}, 'incomplete period coverage'
    minutes, touched, sequences = defaultdict(lambda: defaultdict(float)), defaultdict(set), set()
    for q in sorted(periods):
        previous = 720 if q <= 4 else 300
        # Corrected actions can receive a later sequence number. The explicit
        # period clock orders time; sequence breaks ties at the same stoppage.
        rows = sorted(periods[q], key=lambda row: (-row[1], row[0]))
        if rows[-1][1] != 0:
            return {}, 'period end missing'
        for sequence, seconds, play in rows:
            if sequence in sequences or seconds > previous:
                return {}, 'ambiguous timeline'
            sequences.add(sequence)
            for ids in lineups.values():
                for athlete in ids:
                    minutes[athlete][q] += (previous-seconds)/60
                    if previous > seconds:
                        touched[athlete].add(q)
            previous = seconds
            kind = (play.get('type') or {}).get('text')
            ids = [str((p.get('athlete') or {}).get('id')) for p in play.get('participants') or []]
            if kind == 'Substitution':
                team = str((play.get('team') or {}).get('id'))
                if (len(ids) != 2 or team not in lineups or ids[0] in lineups[team]
                        or ids[1] not in lineups[team]
                        or any(i not in players or players[i]['team'] != team or players[i].get('dnp') for i in ids)):
                    return {}, 'substitution does not match current lineup'
                lineups[team].remove(ids[1])
                lineups[team].add(ids[0])
            elif play.get('scoringPlay') or play.get('shootingPlay'):
                # Assisters and shooters must both be on court. Bench technical
                # fouls are deliberately not treated as participation evidence.
                if not ids or any(i not in players or i not in lineups.get(players[i]['team'], set()) for i in ids):
                    return {}, 'on-court action conflicts with lineup'
                for athlete in ids:
                    touched[athlete].add(q)
    for athlete, player in players.items():
        actual = player.get('stats', {}).get('min')
        if player.get('dnp'):
            if sum(minutes[athlete].values()) or touched[athlete]:
                return {}, 'DNP conflicts with participation'
            continue
        # ESPN commonly rounds box minutes to a whole minute. The reconstruction
        # retains exact clocks; tolerate only that documented display precision.
        if (type(actual) not in (int, float) or not math.isfinite(actual)
                or abs(actual-sum(minutes[athlete].values())) > (1 if actual == int(actual) else 1/60)+1e-8):
            return {}, 'reconstructed minutes do not reconcile to box'
    return {athlete: {str(q): {'minutes': round(minutes[athlete][q], 3),
                              'participation': 'observed' if q in touched[athlete] else 'not-observed'}
                      for q in sorted(periods)} for athlete in players}, None
