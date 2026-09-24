"""Paper trials: plays recorded but never published, graded in the open, so a market proves itself first.

The basketball model is less accurate than the closing line in every market (docs/HOOPS.md), but in totals the
line moves toward our number from the open: graded at the opening number our side won about 53% in both backtest
seasons. That is the one basketball signal worth a trial. This module runs it without publishing anything:

  record   before each game, the first total the desk sees for it (DraftKings through ESPN's odds feed: the
           opening number and the current one, with prices) and our number, for every game; a game where our
           number is at least LEAN points from the line is a paper play on that side.
  grade    after the game: the result at the number recorded, and the closing line value against the books'
           consensus close the basketball store keeps.
  report   data/paper/REPORT.md: the paper record by league at the number recorded and at the opener.

Everything lives in data/paper/<league>-<season>.jsonl (records and grades, append-only, with a ledger). The
desk's runs call step() on its evening and midday slots; it does nothing outside the seasons. Promoting a trial
to published picks is a person's decision, made on the graded record.

  python scripts/paper.py step           refresh finals, record upcoming games, grade, report
  python scripts/paper.py report         print the report
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boxscores
import hoops_model
import hoops_store
import learning
from boxscores import line as parse_line

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'paper'
LEAGUES = ('NBA', 'CBB')
AHEAD = timedelta(hours=36)            # games tipping off this soon are recorded
PREFERRED = ('DraftKings', 'ESPN BET', 'FanDuel')   # the book whose number is recorded, first found


def path_for(league, season, root=STORE):
    return Path(root) / f'{league.lower()}-{season}.jsonl'


def read(league, season, root=STORE):
    return boxscores.read_store(path_for(league, season, root))


def append(league, season, rows, root=STORE):
    """Append-only with the store's ledger, like every other store."""
    if not rows:
        return 0
    root = Path(root)
    problems = boxscores.verify(root) if root.exists() else []
    if problems:
        raise ValueError('refusing to append to a paper store whose recorded lines changed: ' + '; '.join(problems))
    boxscores.append(path_for(league, season, root), rows)
    boxscores.write_json(root / 'ledger.json', boxscores.ledger(root))
    return len(rows)


# ------------------------------------------------------------------ upcoming games and their lines

def upcoming(league, now, fetch=hoops_store.fetch_json):
    """Regular-season and postseason games tipping off within AHEAD, as {id, eventId, season, kickoff, neutral, home, away}."""
    out = []
    days = sorted({(now + timedelta(hours=h)).date() for h in (0, 12, 24, 36)})
    for day in days:
        try:
            payload = fetch(hoops_store.scoreboard_url(league, day))
        except Exception:
            continue
        for event in payload.get('events') or []:
            competition = (event.get('competitions') or [{}])[0]
            status = (competition.get('status') or event.get('status') or {}).get('type') or {}
            season = event.get('season') or {}
            if status.get('state') != 'pre' or season.get('type') not in hoops_store.SEASON_TYPES:
                continue
            kickoff = event.get('date') or competition.get('date')
            if not kickoff or not now < hoops_model.when(kickoff) <= now + AHEAD:
                continue
            sides = {c.get('homeAway'): c for c in competition.get('competitors', [])}
            if set(sides) != {'home', 'away'}:
                continue
            home, away = hoops_store.team(sides['home']), hoops_store.team(sides['away'])
            if not home.get('id') or not away.get('id'):
                continue
            event_id = str(event['id'])
            out.append({'id': f'{league}-{event_id}', 'eventId': event_id, 'season': int(season['year']), 'kickoff': kickoff,
                        'neutral': bool(competition.get('neutralSite')), 'home': home, 'away': away})
    unique = {g['id']: g for g in out}
    return sorted(unique.values(), key=lambda g: g['kickoff'])


def american(value):
    try:
        return int(str((value or {}).get('american') or '').replace('+', ''))
    except (TypeError, ValueError):
        return None


def current_line(league, event_id, fetch=hoops_store.fetch_json):
    """{'book', 'open', 'now', 'over', 'under'}: one book's opening and current total with the current prices, the
    first of PREFERRED that has a current total; None when no book has one."""
    try:
        payload = fetch(hoops_store.odds_url(league, event_id))
    except Exception:
        return None
    books = hoops_store.book_items(payload)
    for name in list(PREFERRED) + sorted(set(books) - set(PREFERRED)):
        item = books.get(name)
        if not item:
            continue
        current = item.get('current') or {}
        now_total = parse_line(current.get('total')) if current.get('total') else None
        if now_total is None and isinstance(item.get('overUnder'), (int, float)):
            now_total = float(item['overUnder'])
        low, high = hoops_store.PLAUSIBLE['total']
        if now_total is None or not low <= now_total <= high:
            continue
        open_total = hoops_store.book_line(item, 'open')[0]
        return {'book': name, 'open': open_total, 'now': now_total, 'over': american(current.get('over')),
                'under': american(current.get('under'))}
    return None


# ------------------------------------------------------------------ the model's number

def chosen_params(league):
    try:
        return json.loads((ROOT / 'data' / 'model' / f'hoops-{league.lower()}.json').read_text(encoding='utf-8'))['chosen']
    except (OSError, ValueError, KeyError):
        return hoops_model.PARAMS[league]


def model_for(league, season, now, records=None):
    """The tuned model as of now, rated from every stored game before now and last season's closing ratings."""
    games = hoops_model.prepare(records if records is not None else hoops_store.load(league))
    params = chosen_params(league)
    prior = hoops_model.season_prior(league, games, season, params)
    return hoops_model.Model(league, games, now, season, params, prior)


# ------------------------------------------------------------------ record, grade, report

def record(now, fetch=hoops_store.fetch_json, root=STORE, models=None, log=print):
    """The first line the desk sees for each upcoming game, our number, and whether it is a paper play."""
    written = 0
    for league in LEAGUES:
        games = upcoming(league, now, fetch)
        if not games:
            continue
        seasons = {g['season'] for g in games}
        seen = {r['gameId'] for s in seasons for r in read(league, s, root) if r.get('type') == 'record'}
        todo = [g for g in games if g['id'] not in seen]
        if not todo:
            continue
        rows = defaultdict(list)
        for game in todo:
            quote = current_line(league, game['eventId'], fetch)
            if not quote:
                continue
            try:
                model = (models or {}).get((league, game['season'])) or model_for(league, game['season'], now)
                if models is not None:
                    models[(league, game['season'])] = model
                ours = model.predict(game['home']['id'], game['away']['id'], game['neutral'])
            except Exception as error:          # nothing to rate from yet: say so and record nothing
                log(f'paper {league}: no number for {game["id"]} ({type(error).__name__})')
                continue
            if not isinstance(ours.get('total'), (int, float)):
                continue
            gap = round(ours['total'] - quote['now'], 2)
            side = 'over' if gap > 0 else 'under'
            lean = abs(gap) >= hoops_model.LEAN[league]
            rows[game['season']].append({
                'type': 'record', 'gameId': game['id'], 'league': league, 'season': game['season'], 'kickoff': game['kickoff'],
                'home': game['home'].get('abbreviation'), 'away': game['away'].get('abbreviation'), 'capturedAt': learning.stamp(now),
                'book': quote['book'], 'line': quote['now'], 'open': quote['open'], 'ours': round(ours['total'], 1),
                'sd': round(ours.get('sdTotal') or 0, 1), 'sparse': bool(ours.get('sparse')), 'gap': gap, 'side': side,
                'price': quote['over'] if side == 'over' else quote['under'], 'lean': lean})
        for season, out in rows.items():
            written += append(league, season, out, root)
        if rows:
            log(f"paper {league}: {sum(len(v) for v in rows.values())} games recorded, "
                f"{sum(r['lean'] for v in rows.values() for r in v)} paper plays")
    return written


def settle(value, line, side):
    if value == line:
        return 'push'
    return 'win' if (value > line) == (side == 'over') else 'loss'


def grade(now, root=STORE, finals=None):
    """Grade every recorded game whose final the basketball store holds: at the number recorded, at the opener,
    and the closing line value against the consensus close."""
    written = 0
    for path in sorted(Path(root).glob('*.jsonl')):
        league, season = path.stem.split('-')[0].upper(), int(path.stem.split('-')[1])
        rows = read(league, season, root)
        done = {r['gameId'] for r in rows if r.get('type') == 'grade'}
        pending = [r for r in rows if r.get('type') == 'record' and r['gameId'] not in done]
        if not pending:
            continue
        final = finals.get(league) if finals is not None else {r['id']: r for r in hoops_store.load(league, {season})}
        out = []
        for rec in pending:
            game = (final or {}).get(rec['gameId'])
            if not game:
                continue
            total = game['homeScore'] + game['awayScore']
            close = (game.get('close') or {}).get('total')
            out.append({'type': 'grade', 'gameId': rec['gameId'], 'actual': total,
                        'result': settle(total, rec['line'], rec['side']),
                        'resultAtOpen': settle(total, rec['open'], rec['side']) if isinstance(rec.get('open'), (int, float)) else None,
                        'close': close, 'clv': learning.clv('total', rec['side'], rec['line'], close), 'gradedAt': learning.stamp(now)})
        written += append(league, season, out, root)
    return written


def joined(root=STORE):
    out = []
    for path in sorted(Path(root).glob('*.jsonl')):
        league, season = path.stem.split('-')[0].upper(), int(path.stem.split('-')[1])
        rows = read(league, season, root)
        grades = {r['gameId']: r for r in rows if r.get('type') == 'grade'}
        for rec in rows:
            if rec.get('type') == 'record':
                out.append(dict(rec, **{k: v for k, v in (grades.get(rec['gameId']) or {}).items() if k not in ('type', 'gameId')}))
    return out


def units(rows, key='result'):
    total = 0.0
    for row in rows:
        price = row.get('price') if isinstance(row.get('price'), int) else -110
        if row.get(key) == 'win':
            total += price / 100 if price > 0 else 100 / -price
        elif row.get(key) == 'loss':
            total -= 1
    return round(total, 2)


def summary(rows, key='result'):
    wins = sum(1 for r in rows if r.get(key) == 'win')
    losses = sum(1 for r in rows if r.get(key) == 'loss')
    pushes = sum(1 for r in rows if r.get(key) == 'push')
    rate = wins / (wins + losses) if wins + losses else None
    return {'record': f'{wins}-{losses}' + (f'-{pushes}' if pushes else ''), 'rate': round(rate, 3) if rate is not None else None,
            'units': units(rows, key), 'clv': learning.interval([r.get('clv') for r in rows if r.get(key)])}


def report(root=STORE):
    rows = joined(root)
    lines = ['# Paper trials', '', 'Recorded before each game, graded after; nothing here is published. A -110 price needs 52.4%.', '']
    for league in LEAGUES:
        mine = [r for r in rows if r['league'] == league]
        if not mine:
            continue
        plays = [r for r in mine if r['lean'] and r.get('result')]
        s, o = summary(plays), summary(plays, 'resultAtOpen')
        clv = s['clv']
        lines.append(f"- **{league} totals**: {len(mine)} games recorded, {len(plays)} paper plays graded. At the number "
                     f"recorded {s['record']} ({'' if s['rate'] is None else f'{100 * s['rate']:.1f}%, '}{s['units']:+.2f}u); at the "
                     f"opener {o['record']}; closing line value "
                     + (f"{clv['mean']:+.2f} points (90% {clv['low']:+.2f} to {clv['high']:+.2f})." if clv else 'not yet.'))
    if len(lines) == 4:
        lines.append('- Nothing recorded yet: the trials start with the seasons (NBA 20 October, college 1 November).')
    text = '\n'.join(lines) + '\n'
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / 'REPORT.md').write_text(text, encoding='utf-8')
    return text


def in_season(now):
    """Inside either league's season window (the basketball store's own calendar)."""
    month_day = (now.month, now.day)
    for (start, end) in hoops_store.WINDOW.values():
        if start <= month_day or month_day <= end:
            return True
    return False


def step(now=None, fetch=hoops_store.fetch_json, root=STORE, log=print):
    """One pass: new finals into the basketball store, today's and tomorrow's games recorded, the finished graded,
    the report rewritten. Quiet outside the seasons."""
    now = now or datetime.now(timezone.utc)
    if not in_season(now):
        return {'recorded': 0, 'graded': 0, 'skipped': 'out of season'}
    hoops_store.refresh(list(LEAGUES), days_back=2, fetch=fetch, log=log)
    recorded = record(now, fetch, root, {}, log)
    graded = grade(now, root)
    report(root)
    return {'recorded': recorded, 'graded': graded}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('step', 'report'))
    args = parser.parse_args(argv)
    if args.command == 'report':
        print(report())
        return 0
    print(step())
    return 0


if __name__ == '__main__':
    sys.exit(main())
