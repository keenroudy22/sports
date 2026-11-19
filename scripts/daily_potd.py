"""One immutable daily designation, counted only after original public delivery."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LABEL = "Chef's Pick · POTD"
EASTERN = ZoneInfo('America/New_York')


def fingerprint(play):
    # Original IDs bind the selection; including the posted book, price and
    # stake also rejects an accidental change by a delivery or results adapter.
    if not play.get('id') or not play.get('book') or type(play.get('odds')) not in (int, float):
        return None
    units = play.get('riskUnits')
    if type(units) not in (int, float) or units <= 0:
        return None
    terms = [play['id'], play['book'], float(play['odds']), float(units)]
    return hashlib.sha256(json.dumps(terms, separators=(',', ':')).encode()).hexdigest()


def entries(root=ROOT):
    path = Path(root) / 'data/daily-chef-designations.json'
    return json.loads(path.read_text()) if path.exists() else {}


def designation(play, root=ROOT):
    clock = play.get('kickoff') or (play.get('game') or {}).get('kickoff') or play.get('publishedAt')
    if not clock or play.get('legs') or play.get('parlayType'):
        return None
    try:
        on = datetime.fromisoformat(str(clock).replace('Z', '+00:00')).astimezone(EASTERN).date().isoformat()
    except ValueError:
        return None
    row = entries(root).get(on)
    return on if row and row['termsHash'] == fingerprint(play) else None


def reserve(report, decision, root, now):
    selected = decision.get('selectedId')
    item = next((r for r in report['rows'] if r['terms']['id'] == selected and r['state'] == 'reviewable'), None)
    if not item or decision['state'] != 'reviewed':
        raise ValueError('A current favorite with an unsent original is required')
    digest = fingerprint(item['terms'])
    if not digest:
        raise ValueError('Original book, price and stake required')
    on = report['day']
    existing = entries(root)
    if on in existing:
        if existing[on]['termsHash'] != digest:
            raise ValueError('The daily favorite was already designated')
        return
    existing[on] = dict(termsHash=digest, designatedAt=now.isoformat())
    path = Path(root) / 'data/daily-chef-designations.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(existing, indent=2, sort_keys=True)+'\n')
    tmp.replace(path)


def mark_delivered(plays, posts, root, now):
    import receipts
    by_id = {}
    for entry in posts:
        disc = entry.get('discord') or {}
        channels = []
        if entry.get('link') and entry.get('sentAt'):
            channels.append((entry['sentAt'], entry.get('queuedText')))
        if receipts.confirmed_discord(disc):
            channels.append((disc['sentAt'], disc.get('text')))
        for sent, text in channels:
            if not (text or '').startswith((LABEL+'\n', '🍳 '+LABEL+'\n', '🏀 '+LABEL+'\n')):
                continue
            at = datetime.fromisoformat(sent.replace('Z','+00:00'))
            if at <= now:
                by_id.setdefault(entry['id'], []).append(at)
    chosen = entries(root)
    for play in plays:
        if play.get('id') not in by_id:
            continue
        on = designation(play, root)
        if on and min(by_id[play['id']]) >= datetime.fromisoformat(chosen[on]['designatedAt']):
            play['dailyChefDay'] = on


def card_key(play):
    key = play['id'].lower()
    return key + '-potd' if designation(play) else key
