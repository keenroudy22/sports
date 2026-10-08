"""Deterministic public-copy lint. Stored records are never rewritten."""
import re

BANNED = re.compile(r"\b(?:delve|leverage|robust|seamless|comprehensive|unlock|elevate|crucial|empower|game-changer|insights|desk|plates|the owner|analyst notes)\b|"
                    r"kitchen.s closed|history does not predict|no hiding|we never force a play|an empty list beats a forced one|that keeps the chance honest|"
                    r"not just .+? but|\bhere.s\b|\bconfidence \d+ of 10\b|\b(?:\d+th of 1|\d*1th|\d*2th|\d*3th)\b|"
                    r"\bwe (?:have it|project)\b|(?<!hot plate \()\bPOTD:|if you.re climbing|\bplated\.|that.s why we bank|one miss can", re.I)


def lint(text):
    clean = str(text or '')
    problems = []
    if BANNED.search(clean):
        problems.append('retired public wording')
    if re.search(r'\bplate\b|served at', re.sub(r'Hot Plate \(POTD\)', 'POTD', clean, flags=re.I), re.I):
        problems.append('retired kitchen label outside Hot Plate (POTD)')
    if re.search(r'(?<!80/20 )\bLadder\b', clean, re.I):
        problems.append('use 80/20 Climb')
    if re.search(r'—|(?<!\d)–|–(?!\d)', clean):
        problems.append('dash used as punctuation')
    if re.search(r'(?:·[^\n]*){4}', clean):
        problems.append('too many middle-dot clauses')
    return problems
