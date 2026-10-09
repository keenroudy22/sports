"""Deterministic public-copy lint. Stored records are never rewritten."""
import re

import public_copy

BARE_ATHLETE_ID = re.compile(r'(?m)(?:^|:\s*|>\s*)\d{5,}:')
BARE_LONG_NUMBER = re.compile(r'(?<![\w/.-])\d{5,}(?![\w/.-])')

WHOLE_WORD_BANS = (
    'vig', 'implied', 'break-even', 'breakeven', 'EV', 'CLV', 'calibrated', 'selection', 'captured', 'lock',
    'guaranteed', 'hammer', 'smash', 'no-brainer', 'delve', 'unlock', 'elevate', 'leverage', 'robust',
    'seamless', 'insights', 'crucial', 'game-changer', 'honest', 'honesty',
)
PHRASE_BANS = (
    'not an official play', 'official play', 'not a TD pick', 'not a prediction', 'Usage, not a TD pick',
    'Opportunity, not TD probability', 'Research only', 'Research, not', 'Check current prices',
    'History does not predict', 'Full details', 'on the graphic', 'Mint rings', '| market', 'Our raw model',
    'current screen', 'checked before grading', 'at the posted', 'next run', 'this run', 'desk run', 'the desk',
    'scan time', 'our edge', 'edge:', "That's why we bank", "One miss can't", 'free money', 'Plated.',
    'Best bets drop', 'We have it at', 'From Claude', "Here's", 'dive in', 'buckle up', 'trust the process',
    "let's ride", "let's go", 'graded in public', 'even the burnt',
)
WORD_BANS = re.compile(r'(?i)(?<![\w-])(?:' + '|'.join(re.escape(word) for word in WHOLE_WORD_BANS) + r')(?![\w-])')
MODEL_PERCENT = re.compile(r'(?i)\bmodel\s+\d+(?:\.\d+)?%')
EDGE_NUMBER = re.compile(r'(?i)\+\d+(?:\.\d+)?\s+edge\b')
ZERO_DOLLARS = re.compile(r'(?<!\d)\$0\b')
DOUBLED_WORD_END = re.compile(r'(?i)\b[A-Za-z]*([A-Za-z]{3,})\1\b')
REPEATED_PAREN = re.compile(r'(\([^()]+\))(?:\s+\1)+', re.I)


def bare_athlete_id(text):
    return bool(BARE_ATHLETE_ID.search(str(text or '')))

BANNED = re.compile(r"\b(?:delve|leverage|robust|seamless|comprehensive|unlock|elevate|crucial|empower|game-changer|insights|desk|plates|the owner|analyst notes)\b|"
                    r"kitchen.s closed|history does not predict|no hiding|we never force a play|an empty list beats a forced one|that keeps the chance honest|"
                    r"not just .+? but|\bhere.s\b|\bconfidence \d+ of 10\b|\b(?:\d+th of 1|\d*1th|\d*2th|\d*3th)\b|"
                    r"\bwe (?:have it|project)\b|(?<!hot plate \()\bPOTD:|if you.re climbing|\bplated\.|that.s why we bank|one miss can", re.I)


def lint(text):
    clean = str(text or '')
    problems = []
    if bare_athlete_id(clean):
        problems.append('bare athlete id in public copy')
    elif BARE_LONG_NUMBER.search(clean):
        problems.append('bare long number in public copy')
    if BANNED.search(clean):
        problems.append('retired public wording')
    if public_copy.issues(clean):
        problems.append('private publishing copy')
    if re.search(r'\bplate\b|served at', re.sub(r'Hot Plate \(POTD\)', 'POTD', clean, flags=re.I), re.I):
        problems.append('retired kitchen label outside Hot Plate (POTD)')
    if re.search(r'(?<!80/20 )\bLadder\b', clean, re.I):
        problems.append('use 80/20 Climb')
    if re.search(r'—|(?<!\d)–|–(?!\d)', clean):
        problems.append('dash used as punctuation')
    if re.search(r'(?:·[^\n]*){4}', clean):
        problems.append('too many middle-dot clauses')
    if WORD_BANS.search(clean):
        problems.append('caption kill-list word')
    if any(phrase.casefold() in clean.casefold() for phrase in PHRASE_BANS) or MODEL_PERCENT.search(clean) \
            or EDGE_NUMBER.search(clean) or ZERO_DOLLARS.search(clean):
        problems.append('caption kill-list phrase')
    if DOUBLED_WORD_END.search(clean) or REPEATED_PAREN.search(clean):
        problems.append('duplicated public wording')
    if re.search(r'(?im)\brepl(?:y|ies|ied|ying)\b[^.!?]*\?\s*(?:$|\n)', clean):
        problems.append('reply question')
    bangs = clean.count('!')
    if bangs and '✅' not in clean and not clean.lstrip().startswith('🪜'):
        problems.append('exclamation mark outside a win or Climb post')
    elif bangs > 1:
        problems.append('too many exclamation marks')
    return problems


def card_lint(text):
    """Shared safety checks for card text, without caption-only word-bank rules.

    The Oct. 9 kill list governs captions and Discord copy. A card may still need
    literal record labels such as "$0 banked"; it must never expose private copy,
    an athlete id, or retired card language.
    """
    caption_only = {
        'caption kill-list word', 'caption kill-list phrase', 'reply question',
        'exclamation mark outside a win or Climb post', 'too many exclamation marks',
        'duplicated public wording',
    }
    return [problem for problem in lint(text) if problem not in caption_only]
