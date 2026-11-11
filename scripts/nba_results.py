"""Individual NBA prop Finals from immutable original terms and actual grades."""
import hashlib
from datetime import timedelta
from pathlib import Path
import boxscores


def key(play):
    digest=hashlib.sha256(f"{play['result']}:{play.get('actual')}".encode()).hexdigest()[:10]
    return f"receipt:nba:{play['id']}:{digest}"


def net(play):
    return play['riskUnits']*((100/-play['odds'] if play['odds']<0 else play['odds']/100)
        if play['result']=='win' else -1 if play['result']=='loss' else 0)


def caption(play):
    import nba_prop_release
    mark={'win':'✅','loss':'❌','push':'➖','void':'➖'}[play['result']]
    actual='Did not play' if play.get('actual') is None else f"Final: {play['actual']:g} {nba_prop_release.STATS[play['stat']]}"
    return f"{mark} {nba_prop_release.selection(play)}\n{actual} · {net(play):+.2f}u\n#NBA"


def eligible(play,now):
    return (play.get('marketType')=='player' and play.get('result') in ('win','loss','push','void')
        and now-timedelta(days=3)<=boxscores.instant(play['settledAt'])<=now)


def plans(now,book,root,reserved=()):
    import buffer_post,nba_trial_runtime
    busy=buffer_post.taken(book,now)+[p[3] for p in reserved];out=[]
    for play in nba_trial_runtime.public_rows(root):
        if not eligible(play,now):continue
        guid=key(play)
        if any(e.get('id')==guid for e in book.get('posts',[])):continue
        # Native quote can only target a confirmed, still-live original.
        if not buffer_post.quote_tweet_id(book,guid):continue
        due=buffer_post.free_slot(now,busy)
        out.append((guid,'receipt',caption(play),due,guid.replace(':','-').lower()));busy.append(due)
    return out


def render(play,folder):
    import nba_prop_release,pick_card,ticket_cards
    target=Path(folder)/(key(play).replace(':','-').lower()+'.png')
    if target.exists():return
    if play['result'] in ('win','loss'):
        data=dict(player=play['player'],side=play['direction'].upper(),line=f"{play['line']:g}",
            market=play['stat'],odds=play['odds'],book=play['book'],final=f"{play['actual']:g}",
            margin=f"{abs(play['actual']-play['line']):g}",photo=nba_prop_release.player_headshot(play),
            team_logo=str(Path(__file__).resolve().parents[1]/'site/kookn-mark.png'),
            close_line='',chip='BEST BET · FINAL',
            **({'units_won':net(play)} if play['result']=='win' else {'units_lost':net(play)}))
        card=ticket_cards.cooked_card(data) if play['result']=='win' else ticket_cards.burnt_card(data)
    else:
        detail='Did not play' if play.get('actual') is None else f"Final: {play['actual']:g} {nba_prop_release.STATS[play['stat']]}"
        card=ticket_cards.final_card(dict(headline='NBA '+play['result'].upper(),row_label='NBA PICKS',net_units=0,combined=True,
            rows=[dict(title=nba_prop_release.selection(play),detail=detail+f" · {play['odds']:+d} {play['book']}",result=play['result'],unit_text='0.00u')]))
    pick_card.render(card.svg(),target)
