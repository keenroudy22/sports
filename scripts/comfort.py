"""Build the owner-plan Safer combo from already-vetted moneyline candidates."""
from itertools import combinations

import parlay


def eligible(candidate):
    numbers = candidate.get('_selection') or {}
    reasons = candidate.get('_planReasons') or []
    return candidate.get('marketType') == 'moneyline' \
        and numbers.get('fairChance', 0) >= .70 \
        and numbers.get('rawChance', 0) >= numbers.get('fairChance', 1) + .03 \
        and bool([row for row in reasons if row.get('direction') == 'for'])


def build(candidates, required_game=None):
    """Return the best two-game, same-book combo in the approved price band."""
    rows = [row for row in candidates if eligible(row)]
    tickets = []
    for left, right in combinations(rows, 2):
        if left['gameIds'][0] == right['gameIds'][0] or left.get('book') != right.get('book'):
            continue
        games = {left['gameIds'][0], right['gameIds'][0]}
        if required_game and required_game not in games:
            continue
        price = parlay.american(parlay.decimal(left['odds']) * parlay.decimal(right['odds']))
        if not -200 <= price <= 120:
            continue
        tickets.append((sum(row['_selection']['gap'] for row in (left, right)), price, left, right))
    if not tickets:
        return None
    _, price, left, right = max(tickets, key=lambda row: (row[0], -abs(row[1]), row[2]['id'], row[3]['id']))
    legs = []
    for row in (left, right):
        legs.append({'id': row['id'], 'gameId': row['gameIds'][0], 'title': row['title'],
                     'market': 'moneyline', 'side': row['direction'], 'line': 0,
                     'odds': row['odds'], 'book': row['book'],
                     'fairChance': row['_selection']['fairChance'],
                     'chance': row['_selection']['rawChance'], 'reasons': row['_planReasons']})
    return {'odds': price, 'book': left['book'], 'legs': legs,
            'gameIds': [left['gameIds'][0], right['gameIds'][0]],
            'quotedAt': min(left['quotedAt'], right['quotedAt'])}
