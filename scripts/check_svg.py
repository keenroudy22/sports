"""Read-only public-copy check for generated card SVGs.

Only visible SVG text nodes are inspected; embedded image data is not copy.
"""
import re
import xml.etree.ElementTree as ET

import voice

RETIRED = re.compile(r'\b(?:PLATES|NO HIDING|Ladder|Not advice|THIS SEASON)\b', re.I)
FOOTER = '21+ · Entertainment only'
SITE = 'keenroudy.com/sports'


def text_nodes(svg):
    root = ET.fromstring(svg)
    return [''.join(node.itertext()).strip() for node in root.iter()
            if node.tag.rsplit('}', 1)[-1] == 'text' and ''.join(node.itertext()).strip()]


def issues(svg):
    nodes = text_nodes(svg)
    found = []
    for node in nodes:
        if RETIRED.search(node):
            found.append(f'retired card copy: {node}')
        # An older receipt's standalone result glyph is a mark, not a dash used as prose.
        spoken = re.sub(r'^–\s+(PUSH|VOID)$', r'\1', node)
        found.extend(f'{problem}: {node}' for problem in voice.card_lint(spoken))
    if not any(FOOTER in node for node in nodes):
        found.append('missing 21+ card footer')
    if not any(SITE in node for node in nodes):
        found.append('missing site URL')
    return found
