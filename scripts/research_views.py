"""Deterministic research views, never candidates or publications. No network or LLM."""
import math
from datetime import datetime, timedelta, timezone


def moment(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else None
    except (TypeError, AttributeError, ValueError):
        return None


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def implied(odds):
    if not finite(odds) or abs(odds) < 100:
        return None
    return 100 / (100 + odds) if odds > 0 else -odds / (100 - odds)


def upset_watch(card, now):
    market, model = card.get('market') or {}, card.get('v2') or {}
    seen, start = moment(market.get('retrievedAt')), moment(card.get('kickoff'))
    h, a = implied(market.get('homeML')), implied(market.get('awayML'))
    chance = model.get('winProb')
    forecast_at = moment(model.get('publishedAt'))
    if card.get('state') != 'pre' or card.get('completed') or card.get('fcs') or model.get('sparse') \
            or not seen or not start or start <= now or not timedelta(0) <= now - seen <= timedelta(hours=4) \
            or h is None or a is None or h == a or not market.get('book') \
            or not forecast_at or not timedelta(0) <= now - forecast_at <= timedelta(hours=24) \
            or not finite(chance) or not 0 < chance < 1 or chance == .5:
        return None
    side = 'home' if h < a else 'away'
    p = chance if side == 'home' else 1 - chance
    if p <= .5:
        return None
    return {'side': side, 'team': card[side]['name'], 'odds': market[f'{side}ML'],
            'opponentOdds': market['awayML' if side == 'home' else 'homeML'],
            'book': market['book'], 'observedAt': market['retrievedAt'],
            'modelChance': p, 'marketChanceNoVig': (h if side == 'home' else a) / (h + a),
            'label': 'Upset Watch', 'official': False,
            'caution': 'Raw winner estimate, not a calibrated moneyline edge. Check schedule strength and current roles.'}


def scorer_research(game, snapshot, records, names, now):
    """Rank observed current-season scoring opportunities, not touchdown probabilities.

    Missing play-by-play is excluded, not zero-filled. Pass TDs never count as
    anytime scorer TDs. Current model participation required; injured/limited omitted.
    """
    start = moment(game.get('kickoff'))
    published = moment((snapshot or {}).get('publishedAt'))
    if game.get('state') != 'pre' or not start or start <= now or not snapshot or not published \
            or not timedelta(0) <= now - published <= timedelta(days=7):
        return []
    rows = []
    for side in ('home', 'away'):
        team = str(game[side]['id'])
        history = [r for r in records if r.get('season') == game.get('season') and r.get('seasonType') == 2
                   and moment(r.get('kickoff')) and moment(r['kickoff']) < min(start, now)
                   and team in r.get('teams', {})]
        for player in ((snapshot.get('players') or {}).get(side) or {}).get('players', []):
            if player.get('limited') or player.get('pos') not in ('QB', 'RB', 'FB', 'WR', 'TE'):
                continue
            volume = sum((player.get(k) or [0])[0] or 0 for k in ('targets', 'carries'))
            if volume < 3:
                continue
            pid = str(player['id'])
            samples = []
            for record in history:
                if (record.get('quality') or {}).get('plays') != 'ok':
                    continue
                stat = next((p for p in record.get('players', []) if str(p.get('id')) == pid
                             and str(p.get('team')) == team), None)
                if stat:
                    samples.append(stat)
            if len(samples) < 3:
                continue
            red = sum((p.get('rzCar') or 0) + (p.get('rzTgt') or 0) for p in samples)
            inside = sum((p.get('i10Car') or 0) + (p.get('i10Tgt') or 0) for p in samples)
            if red < 3:
                continue
            rows.append({'athleteId': pid, 'player': names.get(pid, pid), 'side': side, 'games': len(samples),
                         'teamGames': len(history), 'redZone': red, 'inside10': inside,
                         'touchdowns': sum((p.get('rushTD') or 0) + (p.get('recTD') or 0) for p in samples),
                         'projectedOpportunities': round(volume, 1), 'roleSnapshotAt': snapshot['publishedAt'],
                         'priceStatus': 'No verified TD price',
                         'label': 'Scoring opportunity watch', 'official': False})
    return sorted(rows, key=lambda r: (-r['inside10'] / r['games'], -r['redZone'] / r['games'], r['athleteId']))[:4]


def health(freshness, now):
    limits = {'slate': 4, 'boxscores': 48, 'forecasts': 24, 'injuries': 12, 'props': 12}
    return [{'component': key, 'observedAt': value,
             'status': 'missing' if not moment(value) else
             'stale' if not timedelta(0) <= now - moment(value) <= timedelta(hours=limits[key]) else 'current',
             'fallback': 'Stored history remains visible; check source age before relying on it.'}
            for key, value in freshness.items() if key in limits]
