"""Keep explicitly period-scoped quotes out of full-game models and settlements.

Absent period metadata retains the established full-game feed contract. Explicit
unknown metadata fails closed; this cannot detect a provider's unlabelled error.
This is not a quarter-market collector or a period projection model.
"""
import re

PERIOD = re.compile(r'(?:^|[^a-z0-9])(?:q[1-4]|[1-4]q|h[12]|[12]h|ot|quarter\d*|half\d*|period\d*|overtime|regulation)(?:$|[^a-z0-9])')
FULL = {'full game', 'full match', 'entire game', 'game', 'match'}
FIELDS = ('period', 'period_name', 'period_type', 'period_number', 'quarter', 'half', 'market_period', 'marketWindow')


def full_game(row):
    market = str(row.get('market_type') or '').lower()
    if PERIOD.search(market):
        return False
    for key in FIELDS:
        value = row.get(key)
        if value is None or value == '':
            continue
        if not isinstance(value, str) or re.sub(r'[_-]+', ' ', value.strip().lower()) not in FULL:
            return False
    return True
