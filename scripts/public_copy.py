"""Words that cannot appear in a hosted page or outbound public message.

The check is deliberately word-bounded: a player's name and ordinary phrases
such as "No automatic betting" are not claims about the publishing system.
"""
import re


BANNED = re.compile(
    r"\b(?:launchd|pipeline|deskRuns|desk runs?|next run|automated|automation|"
    r"I look again|hosted refresh|every 5 min|every 30 min|climb check|"
    r"behind the scenes|pre-post review|delivery checks|release schedule|"
    r"data status|scans?|scheduled check|the desk|the owner|kitchen.s closed|"
    r"ladder step)\b|closed to new entries at \d{1,2}:\d{2}", re.I)


def issues(text):
    return bool(BANNED.search(str(text or '')))


def timing_keys(value):
    if isinstance(value, list):
        return any(timing_keys(child) for child in value)
    if not isinstance(value, dict):
        return False
    for key, child in value.items():
        name = re.sub(r'[^a-z]', '', str(key).lower())
        if name in ('deskruns', 'launchd', 'startcalendarinterval'):
            return True
        if name == 'runs' and isinstance(child, list) and any(
                isinstance(row, dict) and {'h', 'm'} <= set(row) for row in child):
            return True
        if timing_keys(child):
            return True
    return False
