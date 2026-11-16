"""Detect later official stat revisions without silently rewriting a settled bet."""
import math

MARKETS = frozenset(('car', 'rushYds', 'rec', 'recYds', 'cmp', 'att', 'passYds'))


def drift(picks, games):
    by_id = {f"{g['league']}-{g['eventId']}": g for g in games}
    out = []
    for pick in picks:
        market, saved = pick.get('market'), pick.get('actualValue')
        if (market not in MARKETS or pick.get('result') not in ('win', 'loss')
                or not isinstance(saved, (int, float)) or isinstance(saved, bool)
                or pick.get('period') or pick.get('marketWindow')):
            continue
        game = by_id.get(pick.get('gameId') or (pick.get('gameIds') or [None])[0], {})
        player = next((p for p in game.get('players', [])
                       if str(p.get('id')) == str(pick.get('athleteId'))), {})
        current = player.get(market)
        if isinstance(current, (int, float)) and not isinstance(current, bool) and math.isfinite(current) and current != saved:
            out.append({'id': pick['id'], 'market': market, 'settledValue': saved,
                        'currentBoxValue': current, 'state': 'needs-dated-correction',
                        'resultSource': pick.get('resultSource')})
    return out
