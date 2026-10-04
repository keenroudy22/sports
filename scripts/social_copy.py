"""Platform-specific copy without changing the wager or its saved X draft."""
import re


def without_playbook(text):
    """The betslip bot is tagged only on new X plays, never in Discord mirrors."""
    if not re.search(r'(?<![\w/])@playbook(?!\w)', text, re.I):
        return text
    clean = re.sub(r'(?<![\w/])@playbook(?!\w)', '', text, flags=re.I)
    clean = '\n'.join(re.sub(r'[ \t]{2,}', ' ', line).strip() for line in clean.splitlines())
    return re.sub(r'\n{3,}', '\n\n', clean).strip()
