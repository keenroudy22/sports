"""Deterministic choices from the owner-written caption pools. No generated public prose."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOLS = ROOT / 'data' / 'voice' / 'pools.json'


def pools(path=POOLS):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def index(key, size):
    if size <= 0:
        raise ValueError('caption pool is empty')
    return int(hashlib.sha1(str(key).encode('utf-8')).hexdigest(), 16) % size


def pick(values, key):
    values = list(values)
    return values[index(key, len(values))]


def _same_series(history, series):
    return [row for row in history or [] if (row.get('series') or row.get('kind')) == series]


def week_key(value):
    try:
        day = date.fromisoformat(str(value)[:10])
    except ValueError:
        return str(value)[:10]
    return (day - timedelta(days=day.weekday())).isoformat()


def choose_shape(post_id, day, series='play', history=None, required=None):
    """Choose A-D while enforcing cooldowns and the weekly 40% ceiling."""
    if required:
        return required
    recent = _same_series(history, series)
    week = week_key(day)
    weekly = [row.get('copyVariant') for row in recent
              if week_key(row.get('postedAt') or row.get('day') or '') == week]
    last = recent[-1].get('copyVariant') if recent else None
    order = ['A', 'B', 'C', 'D']
    start = index(f'{post_id}:{day}:shape', len(order))
    ordered = order[start:] + order[:start]
    total = len(weekly) + 1
    eligible = [shape for shape in ordered if shape != last and (weekly.count(shape) + 1) / total <= 0.40
                and (shape != 'D' or (weekly.count('D') + 1) / total <= 0.25)]
    if eligible:
        return eligible[0]
    least = Counter(weekly)
    return min(order, key=lambda shape: (least[shape], max((i for i, row in enumerate(recent)
                                                            if row.get('copyVariant') == shape), default=-1)))


def choose_slot(name, post_id, day, history=None, series='play', values=None):
    pool_name = {'ask': 'asks', 'save': 'saves'}.get(name, name)
    values = list(values if values is not None else pools()[pool_name])
    recent = _same_series(history, series)
    previous = next((row.get(name) for row in reversed(recent) if row.get(name) is not None), None)
    ordered = values[index(f'{post_id}:{day}:{name}', len(values)):] + values[:index(f'{post_id}:{day}:{name}', len(values))]
    return next((value for value in ordered if value != previous), ordered[0])


def five_word_overlap(text, history, series='play'):
    words = str(text or '').casefold().split()
    runs = {' '.join(words[i:i + 5]) for i in range(max(0, len(words) - 4))}
    for row in _same_series(history, series)[-10:]:
        old = str(row.get('freeText') or '').casefold().split()
        if runs & {' '.join(old[i:i + 5]) for i in range(max(0, len(old) - 4))}:
            return True
    return False


def detect_shape(text):
    lines = [line.strip() for line in str(text or '').splitlines() if line.strip()]
    if any(line.startswith('Book says ') for line in lines):
        return 'C'
    if lines and '(' not in lines[0] and len(lines) > 1 and '(' in lines[1]:
        return 'B'
    if not any('❤️' in line for line in lines):
        return 'D'
    return 'A'
