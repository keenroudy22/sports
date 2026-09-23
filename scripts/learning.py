"""The desk's memory and the rules it learns by. Stdlib only.

Every piece of the desk makes decisions: the number prices a line, the gates admit or refuse it, the judge
holds it or lets it through, the post goes out at a time with a reason. This module keeps the record that lets
each of those be measured and, within limits written here, adjusted:

  data/learning/candidates-<season>.jsonl   every candidate the desk considered, published or not, with the
                                            numbers it was decided on and the decision (append-only, ledgered)
  data/learning/graded-<season>.jsonl       each candidate's result once its game is final, and its closing
                                            line value: how far the market moved toward our side by kickoff
  data/learning/policy.json                 the thresholds learning may move, each with a floor, a cap and a
                                            step, and the history of every move with its evidence

Closing line value (CLV) is the signal learning trusts first. Wins and losses take hundreds of plays to mean
anything; whether the market closed toward our number shows within dozens. A segment that keeps losing to the
close gets pickier; one that keeps beating it, with the near misses beating it too, gets back toward the
written rule. Learning never goes below the rules written in PROMPT.md (every floor is the written rule), never
touches a published pick, and every move it makes is a line in policy.json's history that says why.
"""
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'learning'
POLICY = STORE / 'policy.json'

# ------------------------------------------------------------------ the policy

DEFAULT_KNOBS = {
    # The written rules are the floors: learning can make the desk pickier than PROMPT.md, never looser.
    'lean.minEdge': {'value': 1.0, 'floor': 1.0, 'cap': 3.0, 'step': 0.5,
                     'about': 'Points a model lean must clear break-even by (calibrated chance, in points).'},
    'prop.minEdge': {'value': 5.0, 'floor': 5.0, 'cap': 12.0, 'step': 1.0,
                     'about': 'Points a prop lean\'s raw chance must clear its price by.'},
    'prop.minRaw': {'value': 0.60, 'floor': 0.60, 'cap': 0.70, 'step': 0.02,
                    'about': 'The raw chance a prop lean must reach.'},
    'prop.minCalibratedEdge': {'value': 0.0, 'floor': 0.0, 'cap': 5.0, 'step': 1.0,
                               'about': 'Points a prop\'s learned, calibrated chance must clear its price by.'},
}
REASON_KINDS = ('injury', 'weather', 'market', 'stats', 'role', 'other')


def default_policy():
    return {'version': 1,
            'knobs': {name: dict(knob) for name, knob in DEFAULT_KNOBS.items()},
            'segments': {},                      # "NFL/prop:recYds": {"minEdge": 7.0, "paused": false, "since": "..."}
            'calibration': {},                   # "NFL/prop": {"k": 0.13, "n": 538, "heldOut": {...}}
            'reasonWeights': {kind: 1.0 for kind in REASON_KINDS},
            'researcher': {'preferDomains': [], 'avoidDomains': []},
            'history': []}


def load_policy(path=POLICY):
    """The policy on disk merged over the defaults, so a new knob starts at its written rule."""
    policy = default_policy()
    try:
        stored = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return policy
    for name, knob in (stored.get('knobs') or {}).items():
        if name in policy['knobs'] and isinstance(knob, dict) and isinstance(knob.get('value'), (int, float)):
            base = policy['knobs'][name]
            base['value'] = min(max(float(knob['value']), base['floor']), base['cap'])
    for key in ('segments', 'calibration', 'reasonWeights', 'researcher'):
        if isinstance(stored.get(key), dict):
            policy[key].update(stored[key])
    policy['history'] = list(stored.get('history') or [])
    return policy


def save_policy(policy, path=POLICY):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    boxscores.write_json(Path(path), policy)


def threshold(policy, knob, segment=None):
    """A knob's value for a segment: the segment's own learned value when it has one, never below the knob's."""
    base = (policy or default_policy())['knobs'][knob]
    value = base['value']
    field = knob.split('.', 1)[1]
    own = ((policy or {}).get('segments') or {}).get(segment or '', {}).get(field)
    if isinstance(own, (int, float)):
        value = max(value, min(float(own), base['cap']))
    return value


def paused(policy, segment):
    return bool(((policy or {}).get('segments') or {}).get(segment or '', {}).get('paused'))


def move(policy, segment, field, knob, direction, why, evidence, now):
    """Move a segment's value one step up (+1) or down (-1) within its knob's floor and cap. Returns the change or None."""
    base = policy['knobs'][knob]
    seg = policy['segments'].setdefault(segment, {})
    current = float(seg.get(field, base['value']))
    target = round(min(max(current + direction * base['step'], base['floor']), base['cap']), 4)
    if target == current:
        return None
    seg[field] = target
    seg['since'] = stamp(now)
    change = {'at': stamp(now), 'segment': segment, 'knob': knob, 'from': current, 'to': target, 'why': why, 'evidence': evidence}
    policy['history'].append(change)
    return change


def set_paused(policy, segment, value, why, evidence, now):
    seg = policy['segments'].setdefault(segment, {})
    if bool(seg.get('paused')) == value:
        return None
    seg['paused'] = value
    seg['since'] = stamp(now)
    change = {'at': stamp(now), 'segment': segment, 'knob': 'paused', 'from': not value, 'to': value, 'why': why, 'evidence': evidence}
    policy['history'].append(change)
    return change


# ------------------------------------------------------------------ the store

def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def path_for(kind, season, root=STORE):
    return Path(root) / f'{kind}-{season}.jsonl'


def read(kind, season, root=STORE):
    return boxscores.read_store(path_for(kind, season, root))


def append(kind, season, records, root=STORE):
    """Append-only, with the same ledger every other store keeps: a changed line stops the writer."""
    if not records:
        return 0
    root = Path(root)
    problems = boxscores.verify(root) if root.exists() else []
    if problems:
        raise ValueError('refusing to append to a learning store whose recorded lines changed: ' + '; '.join(problems))
    boxscores.append(path_for(kind, season, root), records)
    boxscores.write_json(root / 'ledger.json', boxscores.ledger(root))
    return len(records)


# ------------------------------------------------------------------ the arithmetic

def clv(market, direction, line, close):
    """Points the market moved toward our side between our number and the close; None when either is missing.

    Totals and props: an over gains when the close is higher than our line, an under when it is lower.
    Spreads: our side's line against the close for the same side (home -3 closing -4.5 is +1.5)."""
    if not isinstance(line, (int, float)) or not isinstance(close, (int, float)):
        return None
    if market == 'spread':
        return round(float(line) - float(close), 2)
    if direction == 'over':
        return round(float(close) - float(line), 2)
    if direction == 'under':
        return round(float(line) - float(close), 2)
    return None


def interval(values, level=0.90, draws=1000, seed=7):
    """Mean and a bootstrap interval, seeded so the same record always gives the same answer."""
    values = [float(v) for v in values if isinstance(v, (int, float))]
    if not values:
        return None
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(draws))
    low = means[int((1 - level) / 2 * draws)]
    high = means[min(draws - 1, int((1 + level) / 2 * draws))]
    return {'n': len(values), 'mean': round(statistics.fmean(values), 3), 'low': round(low, 3), 'high': round(high, 3)}


def segment_of(row):
    """League and market: "NFL/total", "CFB/spread", "NFL/prop:recYds", "NFL/parlay"."""
    league = row.get('league') or str(row.get('id', '')).split('-')[0]
    if row.get('legs') or row.get('parlayType') or row.get('kind') == 'parlay':
        return f'{league}/parlay'
    if row.get('athleteId') or row.get('market'):
        return f"{league}/prop:{row.get('market') or row.get('marketKey') or 'unknown'}"
    return f"{league}/{row.get('marketType') or 'unknown'}"


def now_utc():
    return datetime.now(timezone.utc)
