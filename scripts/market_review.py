"""Offline prop-market review. Stored pregame forecasts only; no API calls or live weight changes.

Compare a league shrink with a market shrink pooled toward that league. Split by whole kickoff dates,
so correlated props from the same game cannot cross the boundary. A retrospective pass nominates a
formula for a future shadow trial; it is not proof of profitable bets or an untouched future holdout.
"""
import json
import math

PRIOR_ROWS = 300
MIN_TRAIN = 100
MIN_TEST = 50


def split_dates(rows):
    days = sorted({r['kickoff'][:10] for r in rows})
    if len(days) < 2:
        return list(rows), []
    boundary = days[max(1, min(len(days) - 1, int(len(days) * 0.6)))]
    return ([r for r in rows if r['kickoff'][:10] < boundary],
            [r for r in rows if r['kickoff'][:10] >= boundary])


def probability(raw, k):
    return min(1 - 1e-6, max(1e-6, 0.5 + k * (raw - 0.5)))


def scores(rows, k):
    if not rows:
        return None
    probabilities = [probability(r['raw'], k) for r in rows]
    return {'n': len(rows), 'brier': sum((p - int(r['won'])) ** 2 for p, r in zip(probabilities, rows)) / len(rows),
            'logLoss': -sum(math.log(p if r['won'] else 1 - p) for p, r in zip(probabilities, rows)) / len(rows),
            'predicted': sum(probabilities) / len(rows), 'observed': sum(r['won'] for r in rows) / len(rows)}


def fit(rows):
    if not rows:
        return 0.0
    return min((i / 100 for i in range(101)), key=lambda k: scores(rows, k)['logLoss'])


def audit(rows):
    """One comparison per league/market; no policy mutation. Invalid rows are excluded explicitly."""
    valid = [r for r in rows if isinstance(r.get('raw'), (int, float)) and math.isfinite(r['raw'])
             and 0 <= r['raw'] <= 1 and isinstance(r.get('won'), bool)
             and r.get('league') and r.get('market') and r.get('kickoff')]
    findings = []
    for league in sorted({r['league'] for r in valid}):
        group = [r for r in valid if r['league'] == league]
        train, test = split_dates(group)
        league_k = fit(train)
        for market in sorted({r['market'] for r in group}):
            earlier = [r for r in train if r['market'] == market]
            later = [r for r in test if r['market'] == market]
            weight = len(earlier) / (len(earlier) + PRIOR_ROWS)
            market_k = fit(earlier)
            pooled_k = weight * market_k + (1 - weight) * league_k
            train_days = len({r['kickoff'][:10] for r in earlier})
            test_days = len({r['kickoff'][:10] for r in later})
            eligible = len(earlier) >= MIN_TRAIN and len(later) >= MIN_TEST and train_days >= 4 and test_days >= 2
            base, candidate = scores(later, league_k), scores(later, pooled_k)
            improved = bool(eligible and candidate['brier'] < base['brier'] and candidate['logLoss'] < base['logLoss'])
            findings.append({'segment': f'{league}/prop:{market}', 'trainN': len(earlier), 'testN': len(later),
                             'trainDays': train_days, 'testDays': test_days,
                             'trainThrough': max((r['kickoff'] for r in earlier), default=None),
                             'testFrom': min((r['kickoff'] for r in later), default=None),
                             'leagueK': league_k, 'marketK': market_k, 'pooledK': round(pooled_k, 6),
                             'raw': scores(later, 1.0), 'league': base, 'pooled': candidate,
                             'status': 'shadow candidate' if improved else 'keep league formula' if eligible else 'insufficient history'})
    return {'formula': 'p = 0.5 + k * (raw - 0.5); k = w*k_market + (1-w)*k_league; w = n_train/(n_train+300)',
            'evaluation': 'Earlier 60% of kickoff dates train; later dates test. Both error scores must improve. '
                          'Repeated retrospective evaluation; future shadow results required before promotion. '
                          'Counts are prop observations, not independent games; no ROI claim without captured prices.',
            'excluded': len(rows) - len(valid), 'markets': findings}


def from_stores():
    import learn
    import scoreboard
    games = learn.store_games()
    captures = {**scoreboard.feed_lines(games), **scoreboard.captured_lines(games)}
    _, snapshots = scoreboard.v2_rows(games)
    return audit(learn.prop_rows(games, snapshots, captures))


def markdown(report):
    lines = ['## Prop formula review', '', report['evaluation'], '', report['formula'], '']
    for row in report['markets']:
        base, candidate = row['league'], row['pooled']
        errors = (f"; later-game squared probability error {base['brier']:.4f} league / {candidate['brier']:.4f} pooled"
                  if base else '')
        lines.append(f"- {row['segment']}: {row['trainN']} earlier / {row['testN']} later observations{errors}; {row['status']}.")
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    print(json.dumps(from_stores(), indent=2))
