"""Owner's casual voice, without changing facts, stakes or a post's category."""
VERSION = 'casual-20261022'


def finish(text):
    """Exact copy substitutions only; never free-form rewrite a wager or result."""
    replacements = {
        'Not picks yet. Just where my numbers start.': 'Research, not a bet.',
        'Possible outright dogs:': "Dogs I've got my eye on:",
        'A few numbers I keep coming back to:': 'These caught my eye 👀',
        'Early look. These are the numbers that caught my eye:': 'Got my eye on these 👀',
        'Early look at the next football slate.': 'Next slate on my radar 👀',
        'Scoring context, not a forecast.': 'Past scoring, not tonight’s prediction.',
        'Still climbing? ❤️': "Who's riding with me? 🍳",
        "❤️ if you're tailing": "Who's on it with me? 🍳",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def climb_preview(day, start=50, goal=1000):
    """A target-day teaser, never a selected ticket or promised release."""
    if day not in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'):
        raise ValueError('Use a verified weekday')
    return ('80/20 Climb 🍳\n\n'
            f'Got my eye on {day} for the next climb. Looking for two legs I love.\n\n'
            "Who's riding with me?")
