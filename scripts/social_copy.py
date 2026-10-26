"""Platform-specific copy without changing the wager or its saved X draft."""
import re
from datetime import datetime, timezone

PLAYBOOK_CTA = 'Copy the bet 👇 @Playbook'
AGE_NOTICE = '21+ only'
AGE_VERSION = 'age-20261023'
AGE_EFFECTIVE = datetime(2026, 10, 23, 21, 15, tzinfo=timezone.utc)


def decimal_projection(text):
    """Identify decimal forecast claims, never a sportsbook threshold alone."""
    return bool(re.search(r'(?:I (?:have|project|say)|we (?:project|make)|projected|projection|our (?:number|total)|my (?:number|score|total))[^0-9\n!?]{0,65}\d+\.\d+', str(text or ''), re.I))


def projection_free_reason(text):
    # Omit the entire forecast sentence; rounding a thin edge invents confidence.
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])|\n+', str(text or ''))
    return ' '.join(s for s in sentences if not decimal_projection(s)).strip()


def canonical_caption(text):
    """Visible caption semantics after Buffer's editor paragraph placeholders.

    Only whitespace-only FEFF paragraphs and trailing horizontal whitespace are
    normalized. Never remove invisible characters embedded in actual words.
    """
    lines = str(text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    lines = ['' if not line.strip(' \t\ufeff') else line.rstrip(' \t') for line in lines]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def with_age_notice(text):
    """One caption-only age line; never rewrite graphics or historical records."""
    clean = re.sub(r'(?im)^[ \t]*21\+(?:[ \t]+only)?[.!]?[ \t]*$', '', str(text or ''))
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
    return clean + '\n\n' + AGE_NOTICE if clean else AGE_NOTICE


def age_notice_current(text):
    clean = canonical_caption(text)
    return clean == with_age_notice(clean)


def x_ticket_copy(text, kind, guid='', item=None):
    """Tag actual tickets only. A target-day announcement is not a bet."""
    item = item or {}
    eligible = (kind == 'play' or
                (kind == 'community' and guid.startswith('community:personal-ticket:')
                 and item.get('personalTicket') is True))
    clean = without_playbook(text)
    return with_age_notice(clean + '\n\n' + PLAYBOOK_CTA if eligible else clean)


def without_playbook(text):
    """The betslip bot is tagged only on new X plays, never in Discord mirrors."""
    if re.search(r'(?im)^\s*Copy the bet\s*👇\s*@playbook\s*$', text):
        text = re.sub(r'(?im)^\s*Copy the bet\s*👇\s*@playbook\s*$', '', text).strip()
    if not re.search(r'(?<![\w/])@playbook(?!\w)', text, re.I):
        return text
    clean = re.sub(r'(?<![\w/])@playbook(?!\w)', '', text, flags=re.I)
    clean = '\n'.join(re.sub(r'[ \t]{2,}', ' ', line).strip() for line in clean.splitlines())
    return re.sub(r'\n{3,}', '\n\n', clean).strip()
