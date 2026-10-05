"""Original Kook'n research layout. Presentation only; every row comes from approved evidence."""
import html
import textwrap


def history_strip(row, x, y, width=720):
    """Aggregate outcomes, never a fabricated chronological streak or forecast."""
    hits, games, pushes = (row.get(key) for key in ('hits', 'games', 'pushes'))
    if any(not isinstance(value, int) or isinstance(value, bool) for value in (hits, games, pushes)) \
            or games < 1 or hits < 0 or pushes < 0 or hits + pushes > games:
        return ''
    misses = games - hits - pushes
    counts = [('hit', hits, '#50edbb'), ('miss', misses, '#ff7987'), ('push', pushes, '#8296a4')]
    blocks, offset = [], x
    for label, count, color in counts:
        if count:
            size = width * count / games
            blocks.append(f'<rect data-outcome="{label}" x="{offset:.2f}" y="{y}" width="{size:.2f}" '
                          f'height="10" fill="{color}"/>')
            offset += size
    legend = f'{hits} hit · {misses} missed' + (f' · {pushes} pushed' if pushes else '')
    return ('<g data-history="aggregate"><title>Historical outcomes, not game order or a forecast</title>'
            + ''.join(blocks)
            + f'<text x="{x}" y="{y + 37}" font-size="19" fill="#a7bdca">{html.escape(legend)}</text></g>')


def svg(choice, art=None):
    art = art or {}
    esc = lambda value: html.escape(str(value or ''), quote=True)
    accent = choice['accent']
    def wrapped(value,width,size):
        return textwrap.wrap(str(value or ''),width=max(12,int(width/(size*.57))),break_on_hyphens=False)
    def text(value,x,y,width,size,color='#f5faff',weight=700):
        words=wrapped(value,width,size)
        return ''.join(f'<text x="{x}" y="{y+i*(size+8)}" font-size="{size}" fill="{color}" font-weight="{weight}">{esc(line)}</text>' for i,line in enumerate(words))
    hero = next((uri for uri in art.values() if uri),None)
    header_art = f'<image href="{esc(hero)}" x="635" y="112" width="410" height="300" opacity=".55" preserveAspectRatio="xMidYMax meet"/>' if hero else ''
    rows=choice['rows']
    blocks=[]
    y=445
    for i,row in enumerate(rows):
        content=[]
        baseline=y+45
        for field,size,color,weight in [('title',30,'#f5faff',700),('price',32,accent,850),('metric',24,'#f5faff',700),('detail',20,'#a7bdca',500)]:
            content.append(text(row[field],72,baseline,748,size,color,weight))
            baseline += max(1,len(wrapped(row[field],748,size)))*(size+8)+14
        historical = history_strip(row, 72, baseline - 1)
        if historical:
            content.append(historical)
            baseline += 54
        row_h=max(230,baseline-y+8)
        image=f'<image href="{esc(art[i])}" x="845" y="{y+34}" width="160" height="160" preserveAspectRatio="xMidYMid meet"/>' if art.get(i) else ''
        blocks.append(f'<g data-row="{i}"><rect x="44" y="{y}" width="992" height="{row_h}" rx="18" fill="#10212e" stroke="#2a424f"/>'
          +f'<rect x="44" y="{y+24}" width="4" height="{row_h-48}" rx="2" fill="{accent}"/>'
          +''.join(content)+image+'</g>')
        y += row_h+16
    height=max(1350,y+150)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{height}" viewBox="0 0 1080 {height}" font-family="Helvetica Neue,Helvetica,Arial,sans-serif">
<defs><linearGradient id="research-bg" x2="1" y2="1"><stop stop-color="#070e16"/><stop offset="1" stop-color="#112b39"/></linearGradient></defs>
<rect width="1080" height="{height}" fill="url(#research-bg)"/><path d="M850 0H1080V410H630Z" fill="{accent}" opacity=".07"/>
<circle cx="61" cy="70" r="14" fill="none" stroke="{accent}" stroke-width="4"/><path d="M75 70h28" stroke="{accent}" stroke-width="4"/>
<text x="117" y="83" fill="#f5faff" font-size="32" font-weight="850" letter-spacing="5">KOOK’N</text>
<text x="1034" y="80" text-anchor="end" fill="#a7bdca" font-size="19" letter-spacing="2">RESEARCH · NOT A PLAY</text>
{header_art}
{text(choice['title'],44,192,625,60,'#f5faff',850)}
{text(choice['kicker'],46,362,970,21,accent)}
{''.join(blocks)}
<text x="44" y="{height-98}" fill="{accent}" font-size="27" font-weight="750">Explore the numbers → keenroudy.com/sports</text>
<text x="44" y="{height-56}" fill="#a7bdca" font-size="21">Historical evidence, not guaranteed outcomes. Check current prices.</text>
<text x="44" y="{height-24}" fill="#a7bdca" font-size="18">Entertainment only.</text>
</svg>'''
