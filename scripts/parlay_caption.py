"""One leg per line; never compress a ticket into a paragraph to fit X."""
import re


def layout(heading, legs, footer=''):
    rows = [str(leg).strip() for leg in legs]
    if not rows or any(not row or '\n' in row or '\r' in row for row in rows):
        raise ValueError('Each parlay leg needs one nonempty line')
    return '\n\n'.join(part for part in (heading.strip(), '\n'.join(rows), footer.strip()) if part)


def owner_ticket(item):
    """Build from stored legs, not an operator's comma-separated summary."""
    legs = item.get('legs') or []
    rows = [leg.get('title', '') if isinstance(leg, dict) else leg for leg in legs]
    # Abbreviate only explicit market words; retain names, thresholds and periods.
    replacements = {'first-quarter': '1Q', 'rushing yards': 'rush yds',
                    'receiving yards': 'rec yds', 'passing yards': 'pass yds',
                    'receptions': 'catches', 'alternate spread': 'alt spread',
                    'moneyline': 'ML'}
    for old, new in replacements.items():
        rows = [re.sub(r'\b' + re.escape(old) + r'\b', new, row, flags=re.I) for row in rows]
    heading = f"My {len(rows)}-leg parlay · {int(item['odds']):+d} {item['book']}"
    if item.get('priceBoosted'):
        heading += f" boosted ({int(item['baseOdds']):+d} before boost)"
    return layout(heading, rows)
