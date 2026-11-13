"""Build unfurled share links for picks backed by the public record."""
import json
import re
from html import escape

PICK_ID = re.compile(r'(?:NFL|CFB|NBA|CBB)-[A-Za-z0-9_-]{1,140}')
PNG = b'\x89PNG\r\n\x1a\n'
MARKER = '<!-- Generated Kook’n pick share page -->'


def shareable(pick):
    return (pick.get('posted') is True and not pick.get('historicalImport')
            and PICK_ID.fullmatch(str(pick.get('id') or '')))


def preview_image(site, pick):
    for path in (pick.get('card'), f"data/cards/{pick['id'].lower()}.png",
                 f"data/cards/{pick['id']}.png"):
        if not path or not re.fullmatch(r'data/cards/[A-Za-z0-9_-]+\.png', path):
            continue
        file = site / path
        if file.is_file() and not file.is_symlink():
            with file.open('rb') as stream:
                if stream.read(8) == PNG:
                    return path
    return 'img/og-default.png'


def page(pick, url, destination, image):
    title = escape(str(pick.get('displayTitle') or pick.get('title') or 'Kook’n pick'))
    price = pick.get('odds')
    price = f'{price:+g}' if type(price) in (int, float) and not pick.get('priceAssumed') else ''
    book = str(pick.get('displayBook') or pick.get('book') or '') if price else ''
    result = {'win': 'Won', 'loss': 'Lost', 'push': 'Push', 'void': 'Void'}.get(pick.get('result'))
    description = escape(' · '.join(filter(None, (price, book, result, 'Kook’n Sports public record'))))
    return f"""<!doctype html>
{MARKER}
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Kook’n</title>
<link rel="canonical" href="{escape(url)}">
<meta name="description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title} | Kook’n">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{escape(url)}">
<meta property="og:image" content="{escape(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0;url={escape(destination)}">
</head><body><main><h1>{title}</h1><p>{description}</p>
<p><a href="{escape(destination)}">Open the full pick and result</a></p></main></body></html>
"""


def build(site, base_url):
    record = site / 'data/app/record.json'
    if not record.is_file():
        return 0
    data = json.loads(record.read_text(encoding='utf-8'))
    picks = {pick['id']: pick for ledger in ('picks', 'nbaPicks', 'cbbPicks')
             for pick in data.get(ledger, []) if shareable(pick)}
    folder = site / 'p'
    if folder.is_symlink():
        raise ValueError('Generated share directory cannot be a symlink')
    folder.mkdir(exist_ok=True)
    for file in folder.glob('*.html'):
        if (PICK_ID.fullmatch(file.stem) and file.stem not in picks and not file.is_symlink()
                and MARKER in file.read_text(encoding='utf-8')[:150]):
            file.unlink()
    for pick_id, pick in picks.items():
        path = f'p/{pick_id}.html'
        destination = f'{base_url}#pick/{pick_id}'
        html = page(pick, base_url + path, destination, base_url + preview_image(site, pick))
        target = site / path
        if target.is_symlink():
            raise ValueError(f'Unexpected link in generated share pages: {path}')
        target.write_text(html, encoding='utf-8')
    return len(picks)
