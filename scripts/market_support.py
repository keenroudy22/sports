"""Reject explicit cross-stat supporting claims without inventing causal links.

This narrow contradiction guard is not a probability model or proof that an
otherwise accepted sentence supports a bet. Original published copy is retained.
"""
import re
from datetime import datetime, timezone

START = datetime(2026, 10, 26, 14, 35, tzinfo=timezone.utc)
RECEIVING = r'\b(?:receiv\w*|receptions?|catches|targets?|routes?|checkdowns?|check-downs?)\b'
RUSHING = r'\b(?:rush(?:ing)?(?: yards?| attempts?)?|carries|carry|ground game|hand(?:ing)? (?:the )?ball)\b'
PASSING = r'\b(?:pass(?:ing)?(?: yards?| attempts?)?|completions?|throws?|dropbacks?)\b'


def prospective(pick, now=None):
    value = pick.get('publishedAt')
    if not value and now is None:
        return True
    try:
        at = datetime.fromisoformat(str(value).replace('Z', '+00:00')) if value else now
        return at is not None and at.tzinfo is not None and at >= START
    except (ValueError, TypeError):
        return True


def mismatch(pick, text):
    if not pick.get('athleteId'):
        return None
    stat = pick.get('market') or pick.get('stat')
    text = str(text or '').lower()
    receiving, rushing, passing = (bool(re.search(pattern, text)) for pattern in (RECEIVING, RUSHING, PASSING))
    if stat in ('rec', 'recYds') and rushing and not receiving:
        return 'rushing work alone does not support a receiving prop'
    if stat in ('car', 'rushYds') and receiving and not rushing:
        return 'receiving work alone does not support a rushing prop'
    if stat in ('att', 'cmp', 'passYds') and rushing and not passing:
        return 'rushing work alone does not support a passing prop'
    return None


def allowed(pick, text, now=None):
    return not prospective(pick, now) or mismatch(pick, text) is None
