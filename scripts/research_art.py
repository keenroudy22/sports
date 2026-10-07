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
    import pick_card
    if pick_card.felt_enabled(choice, choice.get('day')):
        import felt_cards
        return felt_cards.research_choice_card(choice, art)
    art = art or {}
    esc = lambda value: html.escape(str(value or ''), quote=True)
    accent = choice['accent']
    def wrapped(value,width,size):
        return textwrap.wrap(str(value or ''),width=max(12,int(width/(size*.57))),break_on_hyphens=False)
    def text(value,x,y,width,size,color='#f5faff',weight=700):
        words=wrapped(value,width,size)
        return ''.join(f'<text x="{x}" y="{y+i*(size+8)}" font-size="{size}" fill="{color}" font-weight="{weight}">{esc(line)}</text>' for i,line in enumerate(words))
    hero = next((uri for uri in art.values() if uri),None)
    label = {'upset': 'UNDERDOG RESEARCH', 'spread-dog': 'SPREAD RESEARCH',
             'matchup': 'MATCHUP RESEARCH', 'season': 'TREND RESEARCH',
             'end-zone': 'SCORER RESEARCH'}.get(choice.get('kind'), 'SLATE RESEARCH')
    hero_art = f'<image href="{esc(hero)}" x="838" y="126" width="350" height="438" opacity=".82" preserveAspectRatio="xMidYMax meet"/>' if hero else ''
    rows=choice['rows'][:4]
    blocks=[]
    top, bottom, gap = 226, 558, 10
    row_h=(bottom-top-gap*(len(rows)-1))/max(1,len(rows))
    for i,row in enumerate(rows):
        y=top+i*(row_h+gap)
        content=[]
        if len(rows)==1:
            title_size=40
            title_lines=wrapped(row['title'],700,title_size)
            baseline=y+55
            content.append(text(row['title'],70,baseline,700,title_size,'#f5faff',850))
            baseline += len(title_lines)*(title_size+8)+10
            content.append(text(row['price'],70,baseline,700,50,accent,900))
            baseline += max(1,len(wrapped(row['price'],700,50)))*58+8
            content.append(text(row['metric'],70,baseline,700,27,'#f5faff',750))
            baseline += max(1,len(wrapped(row['metric'],700,27)))*35+5
            content.append(text(row['detail'],70,baseline,700,20,'#a7bdca',500))
            history_y=min(y+row_h-48,baseline+32)
            historical=history_strip(row,70,history_y,700)
            if historical:
                content.append(historical)
        else:
            title_size=max(17,min(25,int(500/max(1,.57*len(str(row['title']))))))
            content.append(f'<text x="70" y="{y+32}" fill="#f5faff" font-size="{title_size}" font-weight="800">{esc(row["title"])}</text>')
            content.append(f'<text x="800" y="{y+32}" text-anchor="end" fill="{accent}" font-size="27" font-weight="900">{esc(row["price"])}</text>')
            content.append(f'<text x="70" y="{y+60}" fill="#f5faff" font-size="18" font-weight="700">{esc(row["metric"])}</text>')
            if row_h>=100:
                content.append(f'<text x="800" y="{y+60}" text-anchor="end" fill="#a7bdca" font-size="16">{esc(row["detail"])}</text>')
        blocks.append(f'<g data-row="{i}"><rect x="44" y="{y:.1f}" width="780" height="{row_h:.1f}" rx="16" fill="#10212e" stroke="#2a424f"/>'
          +f'<rect x="44" y="{y+18:.1f}" width="5" height="{max(24,row_h-36):.1f}" rx="3" fill="{accent}"/>'
          +''.join(content)+'</g>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" font-family="Helvetica Neue,Helvetica,Arial,sans-serif">
<defs><linearGradient id="research-bg" x2="1" y2="1"><stop stop-color="#070e16"/><stop offset="1" stop-color="#112b39"/></linearGradient></defs>
<rect width="1200" height="675" fill="url(#research-bg)"/><path d="M980 0H1200V585H790Z" fill="{accent}" opacity=".08"/>
<circle cx="61" cy="70" r="14" fill="none" stroke="{accent}" stroke-width="4"/><path d="M75 70h28" stroke="{accent}" stroke-width="4"/>
<text x="117" y="83" fill="#f5faff" font-size="32" font-weight="850" letter-spacing="5">KOOK’N</text>
<text x="1156" y="80" text-anchor="end" fill="#a7bdca" font-size="18" letter-spacing="2">{label}</text>
{hero_art}
{text(choice['title'],44,154,745,52,'#f5faff',850)}
{text(choice['kicker'],46,204,745,19,accent)}
{''.join(blocks)}
<text x="44" y="622" fill="{accent}" font-size="23" font-weight="750">keenroudy.com/sports</text>
<text x="1156" y="622" text-anchor="end" fill="#a7bdca" font-size="16">21+ · Entertainment only</text>
</svg>'''
