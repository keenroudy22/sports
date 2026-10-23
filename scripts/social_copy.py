"""Platform-specific copy without changing the wager or its saved X draft."""
import re
from datetime import datetime, timezone

PLAYBOOK_CTA = 'Copy the bet 👇 @Playbook'
AGE_NOTICE = '21+ only'
AGE_VERSION = 'age-20261023'
AGE_EFFECTIVE = datetime(2026, 10, 23, 21, 15, tzinfo=timezone.utc)


def with_age_notice(text):
    """One caption-only age line; never rewrite graphics or historical records."""
    clean = re.sub(r'(?im)^[ \t]*21\+(?:[ \t]+only)?[.!]?[ \t]*$', '', str(text or ''))
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
    return clean + '\n\n' + AGE_NOTICE if clean else AGE_NOTICE


def age_notice_current(text):
    return str(text or '') == with_age_notice(text)


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
