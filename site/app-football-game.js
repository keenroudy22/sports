'use strict';
/* NFL and college football matchup pages. */
(function (root, factory) {
  root.KRFootballGame = factory;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (ctx) {
  const { C, L, state, esc, head, section, empty, teamDirectory, get, indexGames, withLive, defenseRows,
    defGames, defenseVerdict, projCard, headshot, whenShort, bookLabel, ago, niceTitle, oddsText, isNum,
    watchButton, liveStamp, STAT_WORD, favSpread, marketLabel, quoteAge, round1, fairAmerican, boardRow,
    matchupSignals, researchPrice, pctText, currentUpset, upsetRow, heavyFavorite, trendText,
    opponentTrendText, historyChart, ticket, pickVM, resultLine, odd } = ctx;
  const FOOTBALL_GAME_CSS = `.kt-why .vs { grid-template-columns: auto 1fr 1fr auto; font-size: 15px; }
.kt-why .vs .num { font-variant-numeric: tabular-nums; }
.kt-drivers { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.kt-drivers li { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 8px; font: 500 15px/1.45 var(--font-body); }
.kt-drivers li::before { content: '↑'; color: var(--kookd); font-weight: 700; text-align: center; }
.kt-drivers li.against::before { content: '↓'; color: var(--burnt-text); }
.kt-drivers li small { display: inline; color: var(--dim); font-size: 13px; }
.kt-drivers li.mk { display: block; font: 700 12px/1 var(--font-display); letter-spacing: .12em; text-transform: uppercase; color: var(--dim); margin: 10px 0 2px; }
.kt-drivers li.mk::before { content: none; }
.kt-why:focus { outline: none; }
.kt-why, .section[id] { scroll-margin-top: 64px; }
.kt-why-note { margin-top: 12px; padding: 10px 12px; border-left: 3px solid var(--burnt); background: var(--burnt-soft); font: 500 14px/1.4 var(--font-body); }
.kt-why-foot { margin-top: 12px; font: 500 14px/1.45 var(--font-body); color: var(--dim); }
`;
  if (typeof document !== 'undefined' && document.head && document.createElement && !(document.getElementById && document.getElementById('kr-football-game-css'))) {
    const style = document.createElement('style'); style.id = 'kr-football-game-css'; style.textContent = FOOTBALL_GAME_CSS; document.head.appendChild(style);
  }
  /* ---------- game page ---------- */
  const PROJ_COLS = [['targets', 'Tgt'], ['receptions', 'Rec'], ['recYds', 'Rec yds'], ['carries', 'Car'], ['rushYds', 'Rush yds'], ['att', 'Att'], ['cmp', 'Cmp'], ['passYds', 'Pass yds']];
  const MATCHUP = [['QB', 'passYds'], ['RB', 'rushYds'], ['WR', 'recYds'], ['TE', 'recYds']];
  const HARD_INJURY = /out|doubtful|suspension|reserve/i;
  const opportunity = p => (p.carries ? p.carries[0] : 0) + (p.targets ? p.targets[0] : 0) + (p.att ? p.att[0] : 0);
  const workload = p => [['carries', 'carries'], ['targets', 'targets'], ['att', 'attempts']].filter(([k]) => p && p[k] && p[k][0] >= 0.5).map(([k, l]) => `${C.fixed(p[k][0])} ${l}`).join(' + ');
  /* A depth role's actual season usage (snaps, volume with coverage, red-zone and inside-10 work, TDs), as the old site showed. */
  const roleUsageText = (u, subject) => {
    if (!u) return '';
    const labels = { car: 'carries', tgt: 'targets', att: 'pass attempts' };
    const vol = Object.entries(u.volume || {}).map(([k, v]) => v == null ? `${labels[k] || k} unavailable` : `${C.fixed(v)} ${labels[k] || k} (${(u.coverage || {})[k] ?? u.games}/${u.games} games observed)`);
    const red = /^(RB|FB)$/.test(u.group) ? ['red-zone carry', 'red-zone carries'] : u.group === 'QB' ? ['red-zone pass attempt', 'red-zone pass attempts'] : ['red-zone target', 'red-zone targets'];
    const scoring = [u.redZone == null ? 'Red-zone data unavailable' : `${u.redZone} ${red[u.redZone === 1 ? 0 : 1]} in ${u.redZoneGames} of ${u.redZoneObserved ?? u.games} observed games`];
    if (u.inside10 != null) scoring.push(`${u.inside10} inside the 10`);
    if (u.touchdowns != null) scoring.push(`${u.touchdowns} TD${u.touchdowns === 1 ? '' : 's'} (${u.touchdownObserved ?? u.games}/${u.games} games observed)`);
    return `<p class="small" style="margin-top:6px"><b>${esc(subject)}</b> · ${Math.round(100 * (u.snapPct || 0))}% snaps${vol.length ? ` · ${esc(vol.join(' · '))}` : ''}<br><span class="muted">${esc(scoring.join(' · '))}</span></p>`;
  };
  /* Sleeper watch / Deep sleeper: only when the role's history and the adjusted projection both show it (C.injurySleeperSignal). */
  const sleeperText = (ev, next, proj, abbr) => {
    if (!ev || !proj || !C.injurySleeperSignal) return '';
    const sig = C.injurySleeperSignal(ev, opportunity(proj));
    if (!sig) return '';
    const role = ev.roleUsage || {};
    const redKind = /^(RB|FB)$/.test(ev.group) ? 'carry' : 'target';
    const volKind = /^(RB|FB)$/.test(ev.group) ? 'opportunities (carries + targets)' : 'targets';
    const roleLine = `${abbr} ${ev.role} has averaged ${C.fixed(sig.roleOpportunities)} ${volKind} and ${Math.round(100 * (role.snapPct || 0))}% of snaps`;
    const redLine = role.redZone ? `, with ${role.redZone} red-zone ${redKind}${role.redZone === 1 ? '' : 's'} in ${role.redZoneGames} of ${role.games} games` : '';
    const verdict = sig.tier === 'volume' ? `The adjusted model gives ${next.name} ${C.fixed(sig.projected)} opportunities, enough to watch his lines once a real price is available.`
      : `The adjusted model gives ${next.name} only ${C.fixed(sig.projected)} opportunities, so this is a long-shot touchdown dart, not a volume prop.`;
    return `<div class="card on-felt" style="margin-top:8px;padding:10px 12px"><p class="small"><span class="badge research" style="margin:0 6px 0 0">${esc(sig.label)}</span><b>${esc(next.name)}</b></p><p class="small" style="margin-top:4px">${esc(roleLine + redLine)}. ${esc(verdict)} <span class="muted">Sneaky angle, not an official play.</span></p></div>`;
  };
  const espnGame = g => `https://www.espn.com/${g.league === 'NFL' ? 'nfl' : 'college-football'}/game/_/gameId/${encodeURIComponent(String(g.id).split('-').slice(1).join('-'))}`;
  /* Does the opponent's defense agree with a player line? Same rule as the old Matchup edges. */
  const defenseMatch = (line, teams, league = null) => {
    const rows = defenseRows(teams, league), pos = C.POS_GROUP[line.position], stat = C.marketKey(line);
    const dir = String(line.direction || '').toLowerCase();
    if (!line.opponent || !pos || !stat || !['over', 'under'].includes(dir)) return null;
    const rank = C.rankOf(rows, line.opponent, pos, stat);
    if (!rank) return null;
    const games = defGames(rows, line.opponent, pos, stat);
    const tone = C.rankTone(rank.rank, rank.of), v = defenseVerdict(tone, dir, games);
    return { ...rank, games, pos, stat, tone, text: `${line.opponentAbbr || 'Opponent'} allows ${C.fixed(rank.value)} ${(STAT_WORD[stat] || C.LABEL[stat] || stat).toLowerCase()} a game to ${pos}s · ${rank.rank} of ${rank.of} (1 allows the least) · ${games} games`,
      supports: v === 'supports', opposes: v === 'opposes' };
  };
  /* College usage changes in a lopsided game; flag a player whose team we project to trail by 14+. */
  const scriptCaution = (g, line, model) => {
    if (g.league !== 'CFB' || !line.team || !model || !isNum(model.away) || !isNum(model.home)) return null;
    const team = String(line.team);
    const margin = team === String(g.away.id) ? model.away - model.home : team === String(g.home.id) ? model.home - model.away : null;
    if (!isNum(margin) || margin > -14) return null;
    return `Our score projects ${line.teamAbbr || 'this team'} behind by ${C.fixed(Math.abs(margin))} points. College usage can change in a lopsided game.`;
  };
  const historyWords = h => {
    if (!h) return '';
    const part = (v, label) => v && v.games ? `${v.hits} of ${v.games} ${label}` : '';
    return [part(h.last, `last ${(h.last || {}).games || ''}`.trim()), part(h.season, 'this season')].filter(Boolean).join(' · ');
  };
  const rangeWords = (g, range) => {
    if (!range || !Array.isArray(range.margin)) return '';
    const side = v => v < 0 ? `${g.away.abbr} by ${C.fixed(Math.abs(v), 1)}` : v > 0 ? `${g.home.abbr} by ${C.fixed(v, 1)}` : 'a tie';
    return `80% range: ${side(range.margin[0])} to ${side(range.margin[1])}${Array.isArray(range.total) ? `; total ${C.fixed(range.total[0], 0)} to ${C.fixed(range.total[1], 0)} points` : ''}.`;
  };

  const GARBAGE = 'Garbage-time risk: spread 21+.';
  const anchored = (id, html) => html.replace('<section class="section">', `<section class="section" id="${id}">`);
  /* "Why my number differs" (owner, Oct 7, item 28): my number, the book, the gap and every stored-data driver, by weight.
     The numbers each driver used stay in the JSON for tests; the sentence already carries them.
     A note appears only when a concrete flag fired. A stale line prints only the staleness line. Research, never a play. */
  const whySection = (g, why, final) => {
    if (!why || final) return '';
    const kind = `<span class="kt-kind">Research</span>`;
    if (why.stale) return `<section class="section kt-why" id="why" aria-labelledby="why-h"><div class="section-head"><h2 id="why-h">Why my number differs</h2>${kind}</div><p class="small muted">${esc(why.text)}</p></section>`;
    const markets = why.markets || { [why.kind]: why };
    const row = (label, block, ours, book) => !block ? '' : `<span class="k">${label}</span><span class="num">${esc(ours)}</span><span class="num">${esc(book)}</span><span class="num ${block.gap > 0 ? 'green' : 'red'}">${esc(C.signed(block.gap, 1))}</span>`;
    const table = `<div class="vs"><span class="h"></span><span class="h">My number</span><span class="h">Book${bookLabel((g.market || {}).book) ? ` (${esc(bookLabel(g.market.book))})` : ''}</span><span class="h">Gap</span>
      ${row('Spread', markets.spread, markets.spread ? C.modelSpread(g.home.abbr, g.away.abbr, markets.spread.ours) : '', markets.spread ? favSpread(g.home.abbr, g.away.abbr, -markets.spread.book) : '')}
      ${row('Total', markets.total, markets.total ? C.fixed(markets.total.ours, 1) : '', markets.total ? C.fixed(markets.total.book, 1) : '')}</div>`;
    const both = Boolean(markets.spread && markets.total);
    const list = Object.entries(markets).filter(([, b]) => b && (b.drivers || []).length).map(([k, b]) => `${both ? `<li class="mk" role="presentation">${k === 'spread' ? 'Spread' : 'Total'}</li>` : ''}${b.drivers.slice().sort((x, y) => y.weight - x.weight).map(d => `<li class="${d.direction > 0 ? 'for' : 'against'}"><span>${esc(d.text)}</span></li>`).join('')}`).join('');
    const flagged = Object.values(markets).flatMap(b => ((b || {}).drivers || []).filter(d => d.flag)).sort((x, y) => y.weight - x.weight)[0];
    return `<section class="section kt-why" id="why" aria-labelledby="why-h"><div class="section-head"><h2 id="why-h">Why my number differs</h2>${kind}</div>
      <div class="card">${table}${list ? `<ul class="kt-drivers">${list}</ul>` : '<p class="small muted" style="margin-top:10px">No stored driver explains this gap yet.</p>'}
      ${flagged ? `<p class="kt-why-note">${esc(flagged.text)}</p>` : ''}
      <p class="kt-why-foot">This is my projection against the book's line. It is research; best bets go through separate price checks. <a href="#game/${esc(g.id)}#model-vs">Model vs market ›</a> · <a href="#game/${esc(g.id)}#lines-we-like">Lines we like ›</a></p></div></section>`;
  };
  const numberQuick = (g, why, value, final) => {
    if (!why || why.stale || final) return '';
    const markets = why.markets || { [why.kind]: why };
    const key = why.kind && markets[why.kind] ? why.kind : (markets.spread ? 'spread' : markets.total ? 'total' : null);
    const block = key && markets[key];
    if (!block) return '';
    const mine = key === 'spread' ? C.modelSpread(g.home.abbr, g.away.abbr, block.ours) : C.fixed(block.ours, 1);
    const vegas = key === 'spread' ? favSpread(g.home.abbr, g.away.abbr, -block.book) : C.fixed(block.book, 1);
    const priced = (value || {})[key] || null;
    const clears = priced && isNum(priced.chance) && isNum(priced.needs) && priced.chance > priced.needs;
    const status = priced ? (clears ? 'Price clears the betting bar' : 'Research lean only — not a bet') : 'Research lean — no current price check';
    const chance = priced && isNum(priced.chance) && isNum(priced.needs)
      ? `<span>My chance <b>${esc(C.fixed(priced.chance * 100, 1))}%</b></span><span>Price needs <b>${esc(C.fixed(priced.needs * 100, 1))}%</b></span>` : '';
    return `<section class="section kt-number-quick" aria-labelledby="number-quick-h"><div class="section-head"><h2 id="number-quick-h">My number vs Vegas</h2><span class="kt-kind">Research</span></div>
      <div class="card"><div class="kt-number-grid"><span><small>My number</small><b>${esc(mine)}</b></span><span><small>Vegas</small><b>${esc(vegas)}</b></span><span><small>Difference</small><b>${esc(C.fixed(Math.abs(block.gap), 1))} points</b></span></div>
      <p class="kt-number-status ${clears ? 'green' : ''}"><b>${esc(status)}</b></p>${chance ? `<div class="kt-number-chance">${chance}</div>` : ''}
      <p class="small" style="margin-top:8px"><a href="#game/${esc(g.id)}#why">See why the numbers differ ›</a></p></div></section>`;
  };
  const game = async route => {
    const back = '<a class="back" href="#games">← Games</a>';
    let detail;
    try { detail = await get(`app/games/${route.id}.json`); } catch (e) {
      return head('', 'Game page not available', 'Game pages cover NFL and college football for games from about three days back to eight days ahead. <a href="#games/live">Live scores</a> cover every sport.', back);
    }
    const [today, teams, marketPlayers] = await Promise.all([
      get('app/today.json'),
      teamDirectory(detail.league),
      Array.isArray(detail.marketPlayers) ? detail.marketPlayers
        : get(`app/players/${detail.league}.json`).then(index => index.players || [], () => [])]);
    indexGames(today);
    const now = Date.now();
    const fromSlate = (today.games || []).find(x => x.id === detail.id) || {};
    const liveNow = withLive([{ ...fromSlate, ...detail }]);
    const g = liveNow.games[0];
    const model = fromSlate.v2 || detail.v2 || {};
    const m = g.market || {};
    const final = Boolean(g.completed);
    const pregame = !final && g.state !== 'in' && Date.parse(g.kickoff) > now;
    const title = `${g.away.abbr} at ${g.home.abbr}`;
    /* today.json is a short, fast window; the game's own payload retains its published plays. Prefer a newer
       Today row when both contain the same id, without losing an older or farther-out game-page ticket. */
    /* A matchup page owns only plays wholly tied to that matchup. A multi-game fun ticket may contain one leg
       here, but it belongs on Today, its ticket page and Record, never under "Our plays in this game". */
    const gamePick = p => {
      if (!p) return false;
      const ids = [...new Set([...(p.gameIds || []), ...(p.gameId ? [p.gameId] : [])].filter(Boolean).map(String))];
      return ids.length === 1 && ids[0] === String(g.id);
    };
    const pickById = new Map();
    for (const p of [...(detail.picks || []), ...(today.picks || [])]) if (gamePick(p) && p.id) pickById.set(p.id, p);
    const picks = [...pickById.values()];
    const qbText = ['away', 'home'].flatMap(side => ((detail.teams || {})[side]?.injuries || []).filter(p => p.position === 'QB' && /out|doubtful|questionable|inactive/i.test(p.status || '')).map(p => `${p.name || p.player || g[side].abbr} ${p.status}`)).join('; ');
    const why = detail.whyDiffer || fromSlate.whyDiffer || null;
    const header = projCard({ ...g, v2: model, lean: detail.lean || fromSlate.lean, marketRead: detail.marketRead || fromSlate.marketRead }, { big: true, link: false, ...(pregame ? C.matchupCardExtras({ ...g, whyDiffer: why }, { quoteAge, favSpread }, now) : {}) }) + (qbText ? `<p class=caution>QB news: ${esc(qbText)}</p>` : '');
    const quickNumber = numberQuick(g, why, detail.value || fromSlate.value || {}, final);
    const actions = `<div class="btn-row" style="margin:12px 0 4px">${watchButton({ type: 'game', key: 'game:' + g.id, title, league: g.league, href: '#game/' + g.id, kickoff: g.kickoff })}
      <a class="btn small" href="#team/${esc(g.league)}/${esc(g.away.id)}">${esc(g.away.abbr)} team page</a><a class="btn small" href="#team/${esc(g.league)}/${esc(g.home.id)}">${esc(g.home.abbr)} team page</a>
      <a class="btn small" href="${esc(espnGame(g))}" target="_blank" rel="noopener">ESPN game page ↗</a></div>`;

    /* The final, with how our number did. */
    let finalHtml = '';
    if (final && detail.final) {
      const fin = detail.final, close = fin.close || {}, periods = fin.periods || {};
      const abbrOf = id => (((teams || {}).teams || {})[id] || {}).abbr || (String(id) === String(g.home.id) ? g.home.abbr : String(id) === String(g.away.id) ? g.away.abbr : id);
      const quarters = periods.home && periods.away ? `<div class="table-wrap"><table class="t"><thead><tr><th>Team</th>${periods.home.map((_, i) => `<th class="n">${i < 4 ? 'Q' + (i + 1) : 'OT'}</th>`).join('')}<th class="n">Final</th></tr></thead><tbody>
        <tr><td>${esc(g.away.abbr)}</td>${periods.away.map(v => `<td class="n">${esc(v)}</td>`).join('')}<td class="n"><b>${esc(fin.away)}</b></td></tr><tr><td>${esc(g.home.abbr)}</td>${periods.home.map(v => `<td class="n">${esc(v)}</td>`).join('')}<td class="n"><b>${esc(fin.home)}</b></td></tr></tbody></table></div>` : '';
      const grades = (detail.grades || []).filter(r => r.model === 'v2.0' || r.model === (model.model || 'v2.0'));
      const gr = grades[0];
      const word = r => r === 'W' ? '<b class="green">✓ right</b>' : r === 'L' ? '<b class="red">✗ wrong</b>' : r === 'P' ? 'push' : '–';
      const seenL = new Set();
      const leaders = ['passing', 'rushing', 'receiving'].flatMap(k => { const out = []; for (const p of (fin.leaders || []).filter(x => x.kind === k)) { if (out.length >= 2 || seenL.has(String(p.id))) continue; seenL.add(String(p.id)); out.push(p); } return out; }).map(p => `<tr><td><span class="with-art">${headshot(g.league, p.id, 'sm')}<span><a href="#player/${esc(g.league)}/${esc(p.id)}">${esc(p.name)}</a> <span class="muted tiny">${esc(abbrOf(p.team))} ${esc(p.pos || '')}</span></span></span></td><td class="small">${esc(Object.entries(p.line || {}).map(([k, v]) => `${v} ${(C.LABEL[k] || k).toLowerCase()}`).join(' · '))}</td></tr>`).join('');
      finalHtml = section('How our number did', `<div class="card">
        <div class="vs" style="grid-template-columns:auto 1fr 1fr 1fr;font-size:15px"><span class="h"></span><span class="h">We had</span><span class="h">Closing line</span><span class="h">Final</span>
          <span class="k">Score</span><span class="num">${isNum(model.away) ? `${esc(g.away.abbr)} ${esc(C.fixed(model.away, 0))}–${esc(C.fixed(model.home, 0))} ${esc(g.home.abbr)}` : '–'}</span><span class="muted">–</span><span class="num">${esc(g.away.abbr)} ${esc(fin.away)}–${esc(fin.home)} ${esc(g.home.abbr)}</span>
          <span class="k">Spread</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, model.margin))}</span><span class="num">${esc(favSpread(g.home.abbr, g.away.abbr, close.spread))}</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, fin.home - fin.away))}${gr ? ` · ${word(gr.side)}` : ''}</span>
          <span class="k">Total</span><span class="num">${esc(C.fixed(model.total))}</span><span class="num">${esc(C.fixed(close.total))}</span><span class="num">${esc(fin.home + fin.away)}${gr ? ` · ${word(gr.ou)}` : ''}</span></div>
        <p class="chart-cap">Right or wrong against the closing line${gr && gr.closerMargin != null ? `. Our margin was ${gr.closerMargin ? 'closer than' : 'not closer than'} the line, our total ${gr.closerTotal ? 'closer than' : 'not closer than'} the line` : ''}. Model accuracy, not a betting result.</p></div>
        ${quarters ? `<div style="margin-top:12px">${quarters}</div>` : ''}
        ${leaders ? `<div class="table-wrap" style="margin-top:12px"><table class="t"><caption class="eyebrow" style="text-align:left;padding-bottom:6px">Leaders</caption><tbody>${leaders}</tbody></table></div>` : ''}
        ${/^https:\/\//.test(fin.source || '') ? `<p class="small" style="margin-top:8px"><a href="${esc(fin.source)}" target="_blank" rel="noopener">ESPN box score ↗</a></p>` : ''}`);
    }

    /* Lines we like: fresh, priced, calibrated, with the history and the defense behind each. */
    const currentQuote = f => C.quoteStatus({ ...f, state: 'open' }, g.kickoff, now).current;
    const fav = pregame ? (detail.favoriteLines || []).filter(f => currentQuote(f)
      && !(isNum(f.chance) && isNum(f.needs) && f.chance <= f.needs)).sort((a, b) => (b.edge ?? 0) - (a.edge ?? 0)) : [];
    // Preserve the exact refusal when a saved favorite expires or no priced read qualifies.
    // A below-price direction must never inherit the favorites panel's positive-value heading.
    const blocked = [...(detail.favoriteLines || []), ...(detail.modelReads || [])]
      .sort((a, b) => Number(currentQuote(b)) - Number(currentQuote(a)) || (b.edge ?? -999) - (a.edge ?? -999))[0];
    const blocker = !blocked ? 'No captured main-line price and supported probability are available for this game.'
      : `${niceTitle(blocked.title)} · ${oddsText(blocked.odds)} ${bookLabel(blocked.book) || ''}: ` +
        (!isNum(blocked.odds) || !Number.isFinite(Date.parse(blocked.observedAt)) ? 'a verified quote with a capture time is missing.'
          : !currentQuote(blocked) ? `the quote captured ${whenShort(blocked.observedAt)} is outside the current-price window; a fresh matching price is required.`
          : isNum(blocked.chance) && isNum(blocked.needs) && blocked.chance <= blocked.needs
            ? `our chance is ${pctText(blocked.chance)}; this price needs ${pctText(blocked.needs)}. It does not pass the price check.`
          : (blocked.warnings || []).length ? blocked.warnings.join(' ')
          : blocked.holdReason || (isNum(blocked.chance) && isNum(blocked.needs)
            ? `our chance is ${pctText(blocked.chance)}; this price needs ${pctText(blocked.needs)}, below the research bar.`
            : 'a supported probability is unavailable; the price cannot be cleared.'));
    const favHtml = fav.length ? `<div class="board">${fav.map(f => {
      const dm = f.kind === 'player' ? defenseMatch(f, teams, g.league) : null;
      const script = f.kind === 'player' ? scriptCaution(g, f, model) : null;
      const extraFa = [];
      if (isNum(f.projection) && isNum(f.line) && f.market !== 'point spread') extraFa.push(['for', `Our average is ${C.fixed(f.projection)} against the ${f.line} line.`]);
      if (dm) extraFa.push([dm.supports ? 'for' : dm.opposes ? 'against' : 'ctx', dm.text + '.']);
      if (script) extraFa.push(['against', script]);
      if (f.kind === 'player' && g.garbageTime) extraFa.push(['against', GARBAGE]);
      if (f.holdReason) extraFa.push(['against', f.holdReason]);
      const src = { ...f, id: f.sourceId || f.id, gameId: g.id, league: g.league, kickoff: g.kickoff };
      const vm = { id: f.sourceId || f.id, title: niceTitle(f.title), market: marketLabel(f), league: g.league, kickoff: g.kickoff, odds: f.odds, book: bookLabel(f.book), bestOdds: null, booksCount: 1,
        age: quoteAge(f.observedAt, g.kickoff, now, { odds: f.odds, state: 'open' }), chance: f.chance, needs: f.needs, edge: round1(f.edge), fair: fairAmerican(f.chance), otherLines: [], gameId: g.id, clears: true,
        athleteId: f.athleteId, stat: f.stat || C.marketKey(f), line: f.line, direction: f.direction || f.side, player: f.player, isProp: f.kind === 'player', alternate: f.alternate,
        sub: [f.belowBar ? 'Strongest current lean · not a best bet' : '', historyWords(f.history), dm ? `${dm.pos} matchup: ${dm.rank} of ${dm.of}${dm.tone === 'soft' ? ', soft' : dm.tone === 'tough' ? ', tough' : ''}` : ''].filter(Boolean).join(' · '), extraFa, src,
        clears: !f.belowBar };
      return boardRow(vm);
    }).join('')}</div>` : `<p class="muted small">${pregame ? esc(blocker) : 'Lines close at kickoff. Saved pregame lines are below.'}</p>`;

    /* Put the card and the line status before the large projection. A game with no play must not look empty,
       but a difference between my number and the book is not itself a bet or a supported lean. */
    const pickStatus = p => p.result === 'win' ? 'Hit' : p.result === 'loss' ? 'Miss' : p.result === 'push' ? 'Push' : p.result === 'void' ? 'Void' : 'Official pick';
    const matchupPick = p => {
      const vm = pickVM(p), detail = p.result ? resultLine(p) : '';
      const comparison = isNum(p.line) && isNum(p.projection) ? `<span>Book <b>${esc(C.fixed(p.line))}</b></span><span>Kook’n <b>${esc(C.fixed(p.projection))}</b></span><span>Gap <b>${Number(p.projection) - Number(p.line) > 0 ? '+' : ''}${esc(C.fixed(Number(p.projection) - Number(p.line)))}</b></span>` : '';
      return `<article class="matchup-pick${p.result ? ` is-${esc(p.result)}` : ''}"><a class="matchup-pick-title" href="${esc(vm.href)}">${esc(vm.title)}</a><span class="matchup-pick-state">${esc(pickStatus(p))}</span><span class="matchup-pick-terms">${esc(odd(vm.odds))}${vm.book ? ` · ${esc(vm.book)}` : ''}${detail ? ` · ${esc(detail)}` : ''}</span>${comparison ? `<span class="matchup-pick-numbers">${comparison}</span>` : ''}</article>`;
    };
    const postedHtml = picks.length ? section('Official picks in this game', `<div class="matchup-pick-list">${picks.map(matchupPick).join('')}</div><details class="more-box matchup-ticket-more"><summary>View original ticket${picks.length === 1 ? '' : 's'}</summary><div class="tickets">${picks.map(p => ticket(p, { compact: true })).join('')}</div></details>`) : '';
    const marketFresh = pregame && m.retrievedAt && Number.isFinite(Date.parse(m.retrievedAt))
      && now >= Date.parse(m.retrievedAt) && now - Date.parse(m.retrievedAt) <= 4 * 3600000;
    const linePreview = pregame ? `<section class="game-front" aria-label="Bets and lines for this game">
      <div class="game-front-head"><p class="game-front-status">${picks.length ? 'Official pick is listed above.' : 'No official bet in this game.'}</p><p class="small muted">${marketFresh ? `${esc(bookLabel(m.book) || 'Book')} · checked ${esc(ago(m.retrievedAt))}` : 'Reference lines · check a current price'}.</p></div>
      <p class="eyebrow" style="margin-top:8px">Kook vs Book · current research</p>
      ${fav.length ? `<p class="game-front-watch"><b>${fav.every(f => f.belowBar) ? 'What I like most here (research only):' : 'Price-checked lines worth a look:'}</b> ${fav.slice(0, 2).map(f => `${esc(niceTitle(f.title))} · ${esc(oddsText(f.odds))} ${esc(bookLabel(f.book) || '')}`).join(' · ')}${fav.length > 2 ? ` · +${fav.length - 2} more` : ''}. <a href="#game/${esc(g.id)}#lines-we-like">See the research ›</a></p>`
        : `<p class="game-front-watch">${picks.length ? 'No additional current research line clears my price check. The posted ticket above stays on the record. ' : ''}${esc(blocker)} <a href="#game/${esc(g.id)}#model-vs">See the full comparison ›</a></p>`}
      </section>` : '';

    /* Matchup edges and every other line the model read. */
    const reads = detail.modelReads || [];
    const favIds = new Set(fav.map(f => f.sourceId));
    const currentRead = r => r.odds != null && now - Date.parse(r.observedAt) >= 0 && now - Date.parse(r.observedAt) <= 4 * 3600000;
    const edges = pregame ? reads.map(r => {
      const hist = r.history && r.history.season, dm = defenseMatch(r, teams, g.league), script = scriptCaution(g, r, model);
      const trend = Boolean(hist && hist.games >= 3 && hist.rate >= 70), thin = (r.warnings || []).some(w => /small sample/i.test(w));
      return { r, hist, dm, script, trend, thin, signals: matchupSignals(r, trend, dm && dm.supports) };
    }).filter(x => x.r.kind === 'player' && currentRead(x.r) && x.r.clearsPrice === true && !x.thin && !favIds.has(x.r.sourceId) && x.signals >= 2)
      .sort((a, b) => Number(Boolean(a.script)) - Number(Boolean(b.script)) || b.signals - a.signals || Number(Boolean(b.dm && b.dm.supports)) - Number(Boolean(a.dm && a.dm.supports)) || (b.hist?.rate || 0) - (a.hist?.rate || 0) || String(a.r.title).localeCompare(String(b.r.title))).slice(0, 4) : [];
    const edgeIds = new Set(edges.map(x => x.r.id));
    const edgesHtml = edges.length ? `<div class="grid two">${edges.map(({ r, hist, dm, script, trend, signals }) => `<div class="card">
        <div style="display:flex;justify-content:space-between;gap:8px"><span class="badge research" style="margin:0">${signals} of 3 signals</span><span class="num"><b>${esc(oddsText(r.odds))}</b> <span class="small muted">${esc(bookLabel(r.book) || '')}</span></span></div>
        <p style="margin-top:6px"><a href="#player/${esc(g.league)}/${esc(r.athleteId)}?stat=${esc(C.marketKey(r) || '')}"><b>${esc(niceTitle(r.title))} →</b></a></p>
        <p class="small">${esc(r.comparison || '')}</p>
        <p class="small">${esc(researchPrice(r))}</p>
        <div class="pill-row" style="margin:6px 0"><span class="pill">Model</span>${trend ? `<span class="pill">${esc(hist.rate)}% trend</span>` : ''}${dm && dm.supports ? '<span class="pill good">Matchup</span>' : dm && dm.opposes ? '<span class="pill bad">Defense disagrees</span>' : ''}${script ? '<span class="pill bad">Game-script caution</span>' : ''}</div>
        ${hist ? `<p class="small muted"><b>${esc(hist.hits)} of ${esc(hist.games)}</b> this season at this line</p>` : ''}${dm ? `<p class="small muted">${esc(dm.text)}</p>` : ''}${script ? `<p class="small red">${esc(script)}</p>` : ''}
        <p class="small muted">Checked ${esc(ago(r.observedAt))}</p></div>`).join('')}</div>` : '';
    const others = reads.filter(r => !favIds.has(r.sourceId) && !edgeIds.has(r.id));
    const readRow = r => {
      const hist = r.history && r.history.season;
      const script = r.kind === 'player' ? scriptCaution(g, r, model) : null;
      const price = !pregame ? 'Pregame comparison · not a live line' : currentRead(r) ? `${oddsText(r.odds)} ${bookLabel(r.book) || ''}` : 'No current price · check your book';
      return `<div class="receipt" style="grid-template-columns:minmax(0,1fr) auto"><div><b>${r.athleteId ? `<a href="#player/${esc(g.league)}/${esc(r.athleteId)}?stat=${esc(C.marketKey(r) || '')}">${esc(niceTitle(r.title))}</a>` : esc(niceTitle(r.title))}</b>
        <span>${esc(r.comparison || '')}</span><span>${esc(researchPrice(r))}</span><span>${hist ? `${esc(hist.hits)} of ${esc(hist.games)} this season at this line${hist.games < 5 ? ' · small sample' : ''} · ` : ''}${r.observedAt ? `checked ${esc(ago(r.observedAt))}` : ''}</span>
        ${script ? `<span class="red">${esc(script)}</span>` : ''}${r.kind === 'player' && g.garbageTime ? `<span class="red">${GARBAGE}</span>` : ''}${(r.warnings || [])[0] ? `<span class="red">${esc(r.warnings[0])}</span>` : ''}</div><span class="small muted" style="text-align:right">${esc(price)}</span></div>`;
    };
    const historyOnly = others.filter(r => r.kind === 'player' && !r.clearsPrice);
    const otherPriced = others.filter(r => !historyOnly.includes(r));
    const othersHtml = `${historyOnly.length ? `<details class="more-box"><summary>History only · our chance does not beat this price · ${historyOnly.length}</summary><div class="receipts">${historyOnly.map(readRow).join('')}</div></details>` : ''}${otherPriced.length ? `<details class="more-box"><summary>Every other line · ${otherPriced.length}</summary><div class="receipts">${otherPriced.map(readRow).join('')}</div></details>` : ''}`;

    /* Model vs market. */
    const range = model.range || (detail.forecast || {}).range;
    const fav2 = isNum(model.winProb) ? (model.winProb >= 0.5 ? `${g.home.abbr} ${pctText(model.winProb)}` : `${g.away.abbr} ${pctText(1 - model.winProb)}`) : '–';
    const mFav = isNum(m.homeML) && isNum(m.awayML) ? (m.homeML <= m.awayML ? `${g.home.abbr} ${oddsText(m.homeML)}` : `${g.away.abbr} ${oddsText(m.awayML)}`) : m.homeML != null ? `${g.home.abbr} ${oddsText(m.homeML)}` : '–';
    const gap = (detail.marketRead || fromSlate.marketRead || {}).ourGap || {};
    const caution = g.fcs ? 'FBS vs FCS: my number is not reliable here.' : model.sparse ? 'Thin history: one of these teams has fewer than three games this season, so this forecast leans on last season and the league average.' : '';
    const gapWords = r => r && r.gapsThisLargeVsClose ? `${Number(r.gapsThisLargeVsClose[0]).toLocaleString('en-US')}–${Number(r.gapsThisLargeVsClose[1]).toLocaleString('en-US')}` : null;
    const modelBlock = `<div class="card"><div class="vs" style="grid-template-columns:auto 1fr 1fr;font-size:15px"><span class="h"></span><span class="h">Kook’n line</span><span class="h">${g.market ? `Book line${bookLabel(m.book) ? ` (${esc(bookLabel(m.book))})` : ''}` : 'No book line recorded'}</span>
      <span class="k">Score</span><span class="num">${esc(g.away.abbr)} ${esc(C.fixed(model.away))} – ${esc(g.home.abbr)} ${esc(C.fixed(model.home))}</span><span class="muted">–</span>
      <span class="k">Favorite</span><span class="num">${esc(fav2)}</span><span class="num">${esc(mFav)}</span>
      <span class="k">Spread</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, model.margin))}</span><span class="num">${esc(favSpread(g.home.abbr, g.away.abbr, m.spread))}${isNum(m.spreadOdds) ? ` <span class="muted small">(${esc(g.home.abbr)} ${esc(oddsText(m.spreadOdds))})</span>` : ''}${m.spreadOpen != null && m.spreadOpen !== m.spread ? ` <span class="muted small">(opened ${esc(favSpread(g.home.abbr, g.away.abbr, m.spreadOpen))})</span>` : ''}</span>
      <span class="k">Total</span><span class="num">${esc(C.fixed(model.total))}</span><span class="num">${esc(C.fixed(m.total))}${isNum(m.overOdds) && isNum(m.underOdds) ? ` <span class="muted small">(O ${esc(oddsText(m.overOdds))} / U ${esc(oddsText(m.underOdds))})</span>` : ''}${m.totalOpen != null && m.totalOpen !== m.total ? ` <span class="muted small">(opened ${esc(m.totalOpen)})</span>` : ''}</span></div>
      ${range ? `<p class="chart-cap">${esc(rangeWords(g, range))}</p>` : ''}
      ${gapWords(gap.margin) || gapWords(gap.total) ? `<p class="chart-cap">In past-season backtests, ${gapWords(gap.margin) ? `spread gaps at least this large went ${gapWords(gap.margin)} against the closing line` : ''}${gapWords(gap.margin) && gapWords(gap.total) ? ', and ' : ''}${gapWords(gap.total) ? `total gaps went ${gapWords(gap.total)}` : ''}. Not a live record, and a gap is not a bet. <a href="#record/model">Model record →</a></p>` : ''}
      ${caution ? `<p class="caution" style="margin-top:6px">${esc(caution)}</p>` : ''}${why && !final ? `<p class="small" style="margin-top:8px"><a href="#game/${esc(g.id)}#why">Why my number differs ›</a></p>` : ''}</div>`;

    /* Underdog watch. */
    const uGame = { ...g, state: g.state || 'pre', upsetWatch: detail.upsetWatch || fromSlate.upsetWatch };
    const upsetHtml = pregame && currentUpset(uGame, now) ? section('Underdog watch', upsetRow(uGame, null), '', 'Outright upset research: our raw winner estimate against the market. Not an official play.') : '';

    /* Season trends in this game: main lines, current prices, no heavy favorites. */
    const trends = C.filterTrends(C.bestTrendPrices(detail.seasonTrends || []), { game: g.id, kind: 'main', min: 3, rate: 80 }).filter(t => !heavyFavorite(t.odds)).slice(0, 6);
    const trendsHtml = trends.length ? section('Season trends in this game', `<div class="grid two game-trend-grid">${trends.map(t => `<div class="card"><a href="#player/${esc(g.league)}/${esc(t.athleteId)}?stat=${esc(t.stat)}"><b>${esc(t.player)}</b></a> <span class="muted small">${esc(t.direction === 'under' ? 'Under' : 'Over')} ${esc(t.line)} ${esc(STAT_WORD[t.stat] || t.stat)}</span>
      <p class="small muted">${esc(trendText(t))}${t.games < 5 ? ' · small sample' : ''} · ${esc(oddsText(t.odds))} ${esc(bookLabel(t.book) || '')} · price checked ${esc(ago(t.observedAt))}</p>${opponentTrendText(t) ? `<p class="small ${t.opponentAdjustment?.against ? 'red' : 'muted'}">${esc(opponentTrendText(t))}</p>` : ''}${historyChart(t.history.map(h => Number(h.value)), t.history.map(h => String(h.date).slice(5)), t.line, t.direction === 'under' ? 'under' : 'over')}</div>`).join('')}</div>`,
      `<a class="more" href="#research/trends?game=${esc(g.id)}">All trends for this game →</a>`, 'Main lines with a current price hit at least 80% of the time, better than −400, at least three games. History, not a probability.') : '';

    /* Next up after injuries (NFL depth charts). */
    let depthHtml = '';
    if (g.league === 'NFL' && detail.forecast && pregame) {
      const cards = [];
      for (const side of ['away', 'home']) {
        const team = (detail.teams || {})[side] || {};
        const chart = team.depthChart;
        if (!chart || !(chart.positions || []).length) continue;
        const hurt = (team.injuries || []).filter(p => HARD_INJURY.test(p.status || '') && /^(QB|RB|FB|WR|TE)$/.test(p.position || ''));
        const out = new Set(hurt.map(p => String(p.id)));
        for (const slot of chart.positions || []) for (const player of slot.players || []) {
          if ((player.availability || {}).unavailable) out.add(String(player.id));
        }
        const projections = (((detail.forecast.players || {})[side] || {}).players) || [];
        for (const h of hurt) {
          const slot = chart.positions.find(pos => pos.players.some(p => String(p.id) === String(h.id)));
          if (!slot) continue;
          const i = slot.players.findIndex(p => String(p.id) === String(h.id));
          const next = slot.players.slice(i + 1).find(p => !out.has(String(p.id)));
          if (!next) continue;
          const group = slot.group === 'FB' ? 'RB' : slot.group;
          const role = projections.filter(p => (p.pos === 'FB' ? 'RB' : p.pos) === group).sort((a, b) => opportunity(b) - opportunity(a));
          const shown = [...new Set([role[0], role.find(p => String(p.id) === String(next.id))].filter(Boolean))];
          const order = slot.players.map((p, k) => `<a class="pill${out.has(String(p.id)) ? ' bad' : String(p.id) === String(next.id) ? ' good' : ''}" href="#player/NFL/${esc(p.id)}">${esc(slot.label)}${k + 1} ${esc(p.name)}${out.has(String(p.id)) ? ` · ${esc((p.availability || {}).status || 'OUT').toUpperCase()}` : String(p.id) === String(next.id) ? ' · NEXT UP' : ''}</a>`).join('');
          cards.push(`<div class="card"><p><span class="badge warn" style="margin:0">${esc(h.status)}</span> <b>${esc(h.name)}</b> <span class="small muted">${esc(h.injury || 'injury not listed')} · ${esc(g[side].abbr)}</span></p>
            <p class="small" style="margin-top:6px"><b>${esc(next.name)}</b> moves from ${esc(slot.label)}${slot.players.indexOf(next) + 1} to ${esc(slot.label)}${i + 1} on ESPN's listed order.</p>
            <div class="pill-row" style="margin:8px 0">${order}</div>
            ${(() => { const ev = (team.depthUsage || {})[String(h.id)]; if (!ev) return ''; return roleUsageText({ ...ev.roleUsage, group: ev.group }, `${g[side].abbr} ${ev.role} actual role this season (${(ev.roleUsage || {}).games} games)`) + (ev.playerUsage ? roleUsageText({ ...ev.playerUsage, group: ev.group }, `${next.name} himself this season (${ev.playerUsage.games} games)`) : ''); })()}
            ${shown.length ? `<p class="small muted" style="margin-top:6px">Our model for this game: ${shown.map(p => `<a href="#player/NFL/${esc(p.id)}">${esc(p.name)}</a> ${esc(workload(p) || 'role below projection threshold')}`).join(' · ')}</p>` : ''}
            ${sleeperText((team.depthUsage || {})[String(h.id)], next, role.find(p => String(p.id) === String(next.id)), g[side].abbr)}</div>`);
        }
      }
      const checked = ['away', 'home'].map(side => (((detail.teams || {})[side] || {}).depthChart || {}).checkedAt).filter(Boolean).sort().pop();
      if (cards.length) depthHtml = section('Next up after injuries', `<div class="grid two">${cards.join('')}</div>`, '', `Depth chart and recent usage. Checked ${esc(checked ? ago(checked) : 'recently')}. Touchdown angles are for reference, not official plays.`);
    }

    /* Player projections with the captured line and our gap. */
    const lines = (detail.props || {}).lines || {};
    const validComparison = row => isNum(row.line) && !row.alternate && !row.roleSuspect && !row.priceSuspect && !row.roleHold;
    const hasCurrentPrice = row => pregame && validComparison(row)
      && C.quoteStatus({ ...row, state: row.state || 'open' }, g.kickoff, now).current;
    const propMarkets = new Map();
    for (const row of [...(detail.lines || []), ...(detail.modelReads || [])]) {
      const stat = C.marketKey(row);
      if (!row.athleteId || !stat || !validComparison(row)) continue;
      const key = `${row.athleteId}:${stat}`;
      if (!propMarkets.has(key)) propMarkets.set(key, []);
      propMarkets.get(key).push(row);
    }
    const propRows = (id, stat) => propMarkets.get(`${id}:${stat}`) || [];
    const referenceLine = (id, stat) => (lines[id] || {})[stat]?.[0];
    const hasComparison = (id, stat) => isNum(referenceLine(id, stat)) || propRows(id, stat).some(hasCurrentPrice);
    const usableProjection = (p, k) => !(p.underReview || []).includes(k)
      && Array.isArray(p[k]) && p[k].length === 3 && p[k].every(isNum);
    const projectionPlayers = side => (((((detail.forecast || {}).players || {})[side]) || {}).players || [])
      .filter(p => PROJ_COLS.some(([k]) => usableProjection(p, k)));
    const unavailablePlayers = side => {
      const shown = new Set(projectionPlayers(side).flatMap(player => [String(player.id || ''), String(player.name || '').toLowerCase()]));
      const injuries = (((detail.teams || {})[side] || {}).injuries || [])
        .filter(player => HARD_INJURY.test(player.status || '') && /^(QB|RB|FB|WR|TE)$/.test(player.position || ''))
        .filter(player => !shown.has(String(player.id || '')) && !shown.has(String(player.name || '').toLowerCase()))
        .map(player => ({ ...player, pos: player.position, unavailable: true }));
      const held = new Set(injuries.flatMap(player => [String(player.id || ''), String(player.name || '').toLowerCase()]));
      const lineStats = new Set(['att','cmp','passYds','car','rushYds','tgt','rec','recYds']);
      const linePlayers = marketPlayers
        .filter(entry => String(entry[3] || '') === String(g[side].id || '') || String(entry[4] || '').toLowerCase() === String(g[side].abbr || '').toLowerCase())
        .filter(entry => /^(QB|RB|FB|WR|TE)$/.test(entry[2] || '') && [...lineStats].some(stat => hasComparison(entry[0], stat)))
        .filter(entry => !shown.has(String(entry[0])) && !shown.has(String(entry[1] || '').toLowerCase())
          && !held.has(String(entry[0])) && !held.has(String(entry[1] || '').toLowerCase()))
        .map(entry => ({ id:String(entry[0]), name:entry[1], pos:entry[2], status:'Projection unavailable', unavailable:true, lineOnly:true }));
      return [...injuries, ...linePlayers];
    };
    const displayedPlayers = side => [...unavailablePlayers(side), ...projectionPlayers(side)];
    const POSITION_PROJ = {
      QB: [['att','Att'],['cmp','Cmp'],['passYds','Pass yds']],
      RB: [['carries','Car'],['rushYds','Rush yds'],['targets','Tgt'],['recYds','Rec yds']],
      WR: [['targets','Tgt'],['receptions','Rec'],['recYds','Rec yds']],
      TE: [['targets','Tgt'],['receptions','Rec'],['recYds','Rec yds']]
    };
    const PRIMARY_POSITION_PROJ = {
      QB: ['passYds','att'],
      RB: ['rushYds','carries'],
      WR: ['receptions','recYds'],
      TE: ['receptions','recYds']
    };
    const projTable = side => {
      const block = (((detail.forecast || {}).players || {})[side]) || {};
      const list = displayedPlayers(side);
      if (!list.length) return '';
      const vol = block.volume || {};
      const injuries = (((detail.teams || {})[side] || {}).injuries || []);
      const inferredPos = player => player.pos || (usableProjection(player,'att') || usableProjection(player,'cmp') || usableProjection(player,'passYds') ? 'QB'
        : usableProjection(player,'carries') || usableProjection(player,'rushYds') ? 'RB'
          : usableProjection(player,'targets') || usableProjection(player,'receptions') || usableProjection(player,'recYds') ? 'WR' : null);
      const group = pos => list.filter(player => (inferredPos(player) === 'FB' ? 'RB' : inferredPos(player)) === pos);
      const projectionMarket = key => key === 'targets' ? 'tgt' : C.PROJECTION_MARKET[key];
      const statCell = (player, key) => {
        const stat = projectionMarket(key);
        const v = player.unavailable || !usableProjection(player,key) ? null : player[key];
        const reference = v || player.unavailable ? referenceLine(player.id, stat) : null;
        const exactMarket = row => String(row.athleteId) === String(player.id) && C.marketKey(row) === stat;
        const exactPick = row => picks.some(p => exactMarket(p) && p.posted === true
          && !p.result && p.line === row.line && p.direction === row.direction
          && p.odds === row.odds && bookLabel(p.book) === bookLabel(row.book));
        const rows = propRows(player.id, stat);
        const current = rows.filter(hasCurrentPrice).sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt)
          || Number(b.line === reference) - Number(a.line === reference));
        const likedQuote = v && fav.find(row => exactMarket(row) && hasCurrentPrice(row));
        const read = (!player.unavailable || player.lineOnly ? current.find(exactPick) || likedQuote || current[0] : null)
          || (v && rows.find(row => row.line === reference && isNum(row.odds)));
        const line = read ? read.line : isNum(reference) ? reference : null;
        const checked = read?.observedAt || (line != null ? detail.props?.capturedAt : null);
        const direction = String(read?.direction || 'over').toLowerCase() === 'under' ? 'under' : 'over';
        const gap = v && line != null ? v[0]-line : null;
        const official = Boolean(read && hasCurrentPrice(read) && exactPick(read));
        const liked = !official && Boolean(read && read === likedQuote);
        const book = bookLabel(read?.book || detail.props?.provider);
        const href = esc(C.playerLineHref({ league:g.league, athleteId:player.id, stat, line, direction, book, gameId:g.id }));
        const price = line == null ? '' : [isNum(read?.odds) ? `${direction === 'under' ? 'U' : 'O'} ${oddsText(read.odds)}`
          : player.unavailable && !player.lineOnly ? 'Reference line · no active projection' : 'Odds unavailable', book].filter(Boolean).join(' · ');
        const earlier = read && !hasCurrentPrice(read);
        return `<a class="prop-cell${v ? '' : ' prop-held'}${liked ? ' liked' : ''}${official ? ' official' : ''}" href="${href}" title="Open recent-game chart"><span class="prop-vs"><span><span class="prop-vs-label">${earlier ? 'Earlier line' : 'Book'}</span><b>${line == null ? '—' : esc(line)}</b></span><span class="prop-vs-mark">vs</span><span><span class="prop-vs-label">Kook’n</span><b>${v ? esc(C.fixed(v[0])) : 'Held'}</b></span></span>${gap == null ? '' : `<span class="prop-gap">Projection gap <b>${gap > 0 ? '+' : ''}${esc(C.fixed(gap))}</b></span>`}<span class="prop-price${line == null ? ' is-missing' : ''}">${esc(price)}</span>${v ? `<span class="prop-range">Kook’n range ${esc(C.fixed(v[1],0))}–${esc(C.fixed(v[2],0))}</span>` : `<span>${esc(player.reviewReasons?.[key] ? 'Projection under review' : player.status || 'Projection unavailable')}${player.unavailable ? ' · no edge' : ''}</span>`}${checked ? `<span class="prop-checked">${earlier ? 'Earlier quote · checked' : 'Checked'} ${esc(ago(checked))}</span>` : ''}${official ? '<span class="pick-tag">Official pick</span>' : liked ? '<span class="lean-tag">Research lean</span>' : ''}</a>`;
      };
      const table = (pos, players) => {
        if (!players.length) return '';
        const hasLine = (player, key) => {
          const stat = projectionMarket(key);
          return (player.unavailable && isNum(referenceLine(player.id, stat)))
            || ((!player.unavailable || player.lineOnly) && propRows(player.id, stat).some(hasCurrentPrice));
        };
        const cols = POSITION_PROJ[pos].filter(([key]) => players.some(player => usableProjection(player,key) || hasLine(player,key)));
        const active = players.filter(player => !player.unavailable && cols.some(([key]) => usableProjection(player,key) || hasLine(player,key)));
        const unavailable = players.filter(player => player.unavailable);
        if (!active.length && !unavailable.length) return '';
        const primaryKeys = PRIMARY_POSITION_PROJ[pos] || [];
        const shownCols = primaryKeys.map(key => cols.find(([candidate]) => candidate === key)).filter(Boolean);
        if (!shownCols.length) shownCols.push(...cols.slice(0,2));
        const secondaryCols = cols.filter(([key]) => !shownCols.some(([shown]) => shown === key));
        const playerPriority = player => cols.reduce((score,[key]) => score + (hasLine(player,key) ? 20 : 0)
          + (fav.some(row => String(row.athleteId) === String(player.id) && C.marketKey(row) === projectionMarket(key)) ? 50 : 0)
          + (picks.some(row => String(row.athleteId) === String(player.id) && C.marketKey(row) === projectionMarket(key)) ? 100 : 0), 0);
        const ordered = active.slice().sort((a,b) => playerPriority(b)-playerPriority(a) || opportunity(b)-opportunity(a));
        const renderTable = (rows, caption, tableCols = shownCols) => `<div class="table-wrap"><table class="t prop-compare"><caption class="small muted" style="text-align:left;padding-bottom:6px">${esc(caption)}</caption><thead><tr><th>Player</th>${tableCols.map(([,label]) => `<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${rows.map(player => {
          const injury = injuries.find(row => String(row.id || '') === String(player.id) || String(row.name || '') === String(player.name));
          const playerHead = `<th class="prop-player"><span class="with-art">${headshot(g.league,player.id,'sm')}<span><span class="prop-player-head"><a href="#player/${esc(g.league)}/${esc(player.id)}">${esc(player.name)}</a><span class="prop-pos">${esc(inferredPos(player) || 'Position unavailable')}</span></span>${injury ? `<span class="badge ${HARD_INJURY.test(injury.status || '') ? 'warn' : 'research'}">${esc(injury.status || 'Listed')}</span>` : player.lineOnly ? '<span class="badge research">Projection held</span>' : ''}</span></span></th>`;
          return `<tr>${playerHead}${tableCols.map(([key,label]) => `<td data-stat="${esc(label)}">${statCell(player,key)}</td>`).join('')}</tr>`;
        }).join('')}</tbody></table></div>`;
        const featured = ordered.filter(player => shownCols.some(([key]) => usableProjection(player,key) || hasLine(player,key))).slice(0,2);
        const featuredIds = new Set(featured.map(player => String(player.id || player.name)));
        const depth = ordered.filter(player => !featuredIds.has(String(player.id || player.name)));
        const visibleUnavailable = unavailable.filter(player => shownCols.some(([key]) => hasLine(player,key))).slice(0,1);
        const visibleUnavailableIds = new Set(visibleUnavailable.map(player => String(player.id || player.name)));
        const hiddenUnavailable = unavailable.filter(player => !visibleUnavailableIds.has(String(player.id || player.name)));
        const primaryRows = [...featured, ...visibleUnavailable];
        const extraFeatured = primaryRows.filter(player => secondaryCols.some(([key]) => usableProjection(player,key) || hasLine(player,key)));
        const extras = extraFeatured.length || depth.length || hiddenUnavailable.length;
        const extraRows = depth.length + hiddenUnavailable.length;
        return `<div class="prop-position">${primaryRows.length ? renderTable(primaryRows, `${pos} · featured`) : ''}${extras ? `<details class="more-box prop-depth-more"><summary>More ${esc(pos)} players &amp; markets${extraRows ? ` · ${extraRows}` : ''}</summary>${extraFeatured.length ? renderTable(extraFeatured, `${pos} · more markets`, secondaryCols) : ''}${depth.length ? renderTable(depth, `${pos} · depth`, cols) : ''}${hiddenUnavailable.length ? renderTable(hiddenUnavailable, `${pos} · unavailable`, cols) : ''}</details>` : ''}</div>`;
      };
      return `<p class="small muted">${esc(g[side].abbr)}${isNum(vol.plays) ? ` · ${C.fixed(vol.plays,0)} projected plays · ${Math.round(100*(vol.passRate || 0))}% pass` : ''} · featured players and popular markets first</p>${['QB','RB','WR','TE'].map(pos => table(pos,group(pos))).join('')}`;
    };
    const projHtml = ['away', 'home'].some(side => displayedPlayers(side).length) ? section('Player props & projections', `<p class="small"><b>Book line vs Kook’n projection.</b> Featured players and popular markets first. Tap a stat for its chart.</p><div class="prop-legend"><span>Gap = Kook’n minus the book</span><span class="lean-key"><b>Green</b> research lean · not a pick</span></div><div style="display:grid;gap:16px;grid-template-columns:minmax(0,1fr)">${['away', 'home'].map(side => displayedPlayers(side).length ? `<details class="more-box" style="min-width:0" data-box="proj:${side}"${typeof matchMedia === 'function' && matchMedia('(min-width: 760px)').matches ? ' open' : ''}><summary>${esc(g[side].abbr)} player props · ${displayedPlayers(side).length}</summary>${projTable(side)}</details>` : '').join('')}</div>`, '', `Research only. Range means model uncertainty. ${detail.props && detail.props.capturedAt ? `Lines checked ${esc(ago(detail.props.capturedAt))}.` : 'No comparison lines recorded yet.'} Green is a research lean, not an official pick.${g.garbageTime ? ` <b class="red">${GARBAGE}</b> Starters may sit early.` : ''}`)
      : '';

    const alternateRows = pregame ? (detail.alternateLines || []).filter(r => C.quoteStatus({ ...r, state: 'open' }, g.kickoff, now).current) : [];
    const alternatePlayers = [...new Set(alternateRows.map(r => r.player))];
    const alternateHtml = pregame ? section('Alternate lines vs my numbers', alternateRows.length
      ? alternatePlayers.map(player => `<details class="more-box"><summary>${esc(player)} · ${alternateRows.filter(r => r.player === player).length} priced alternates</summary><div class="grid two">${alternateRows.filter(r => r.player === player).map(r => {
        const dm = defenseMatch(r, teams, g.league);
        return `<article class="card"><h3>${esc(niceTitle(r.title))}</h3><p><b>${esc(oddsText(r.odds))} ${esc(bookLabel(r.book))}</b> · checked ${esc(ago(r.observedAt))}</p><p style="margin-top:8px"><b>My average: ${esc(C.fixed(r.projection))} · Book line: ${esc(r.line)}</b></p><p class="small">${esc(historyWords(r.history) || 'No saved exact-line history yet.')}</p>${(r.reasons || []).map(reason => `<p class="small" style="margin-top:6px">${esc(reason)}</p>`).join('')}${dm ? `<p class="small" style="margin-top:6px">${esc(dm.text)}.</p>` : ''}<p class="small muted" style="margin-top:8px">Research only · check the price. Historical hits are not a predicted hit rate; your book sets the combined parlay odds.</p></article>`;
      }).join('')}</div></details>`).join('')
      : '<p class="muted small">No fresh, verified alternate prices with a usable player projection are available for this game yet.</p>', '', 'Actual captured alternate prices alongside my projected average and results against that exact line. Each leg keeps its own book and price.') : '';

    /* What each defense allows, by position. */
    const defRows = ((teams || {}).defense || {}).rows || {};
    const defRowsL = defenseRows(teams, g.league);
    const matchupSide = (offense, defense) => `<div class="card" style="min-width:0"><p class="eyebrow" style="margin-bottom:6px">${esc(offense.abbr)} offense vs ${esc(defense.abbr)} defense</p><div class="table-wrap"><table class="t"><thead><tr><th>Position</th><th class="n">Allowed a game</th><th class="n">Rank</th></tr></thead><tbody>${MATCHUP.map(([pos, key]) => {
      const r = C.rankOf(defRowsL, defense.id, pos, key);
      const tone = r ? C.rankTone(r.rank, r.of) : '';
      return `<tr><td>${esc(pos)} ${esc((C.LABEL[key] || key).toLowerCase())}</td><td class="n">${r ? esc(C.fixed(r.value)) : '–'}</td><td class="n">${r ? `<span class="rank ${tone}">${esc(r.rank)}/${esc(r.of)}</span>` : ''}</td></tr>`;
    }).join('')}</tbody></table></div></div>`;
    const matchupHtml = Object.keys(defRows).length ? section('Matchup: what each defense allows', `<div class="grid two">${matchupSide(g.away, g.home)}${matchupSide(g.home, g.away)}</div>`,
      `<a class="more" href="#research/players?view=defense&pl=${esc(g.league)}">All defenses →</a>`, 'This season, regular season only. Rank 1 allows the least. Green marks a defense that gives up a lot (soft), red one that gives up little (tough).') : '';

    /* Recent form. */
    const abbrOf = id => (((teams || {}).teams || {})[id] || {}).abbr || id;
    const form = side => {
      const rows = (((detail.teams || {})[side]) || {}).form || [];
      if (!rows.length) return `<p class="muted small">${esc(g[side].abbr)}: no stored games yet.</p>`;
      return `<div class="table-wrap"><table class="t"><caption class="small muted" style="text-align:left;padding-bottom:6px">${esc(g[side].name)} · last ${rows.length}</caption><thead><tr><th>Game</th><th class="n">Score</th><th class="n">Yds</th><th class="n">Allowed</th><th class="n">Success</th><th class="n">TO</th></tr></thead><tbody>${rows.map(r =>
        `<tr><td>${r.gameId ? `<a href="#game/${esc(r.gameId)}">` : ''}${esc(String(r.date).slice(5))} ${r.home === false ? '@' : 'vs'} ${esc(abbrOf(r.opp))}${r.gameId ? '</a>' : ''}</td><td class="n ${r.pf > r.pa ? 'green' : r.pf < r.pa ? 'red' : ''}">${r.pf > r.pa ? 'W' : r.pf < r.pa ? 'L' : 'T'} ${esc(r.pf)}–${esc(r.pa)}</td><td class="n">${esc(r.yards ?? '–')}</td><td class="n">${esc(r.yardsAllowed ?? '–')}</td><td class="n">${r.success != null ? Math.round(100 * r.success) + '%' : '–'}</td><td class="n">${esc(r.turnovers ?? '–')}</td></tr>`).join('')}</tbody></table></div>`;
    };

    /* Injuries. */
    const injBlock = side => {
      const list = (((detail.teams || {})[side]) || {}).injuries || [];
      if (!list.length) return `<p class="small muted">${esc(g[side].abbr)}: nobody listed. A missing listing is not proof of health.</p>`;
      const groups = [['Listed starters', 'starter'], ['Depth / rotation', 'depth'], ['Role unconfirmed', 'unknown']];
      return `<div class="card"><p class="eyebrow" style="margin-bottom:6px">${esc(g[side].abbr)}</p>${groups.map(([label, role]) => {
        const rows = list.filter(p => (['starter', 'depth'].includes(p.depthRole) ? p.depthRole : 'unknown') === role);
        return rows.length ? `<h3>${label} · ${rows.length}</h3>${rows.map(p => `<p class="small" style="padding:3px 0"><span class="badge ${/out|reserve|doubtful/i.test(p.status) ? 'warn' : 'research'}" style="margin:0 6px 0 0">${esc(p.status)}</span><b>${esc(p.name)}</b> ${esc(p.position || '')} · ${esc(p.injury || 'injury not listed')}${p.reportedAt ? ` · reported ${esc(ago(p.reportedAt))}` : ''}${p.roleCheckedAt ? ` · role checked ${esc(ago(p.roleCheckedAt))}` : ''}</p>`).join('')}` : '';
      }).join('')}</div>`;
    };
    const injuryHtml = g.league === 'NFL' ? section('Injury report', `<div class="grid two">${injBlock('away')}${injBlock('home')}</div>`, '', 'Listed starters lead their position on ESPN’s depth chart, not confirmed tonight. Depth players are listed behind them; unmatched or old roles stay unconfirmed. Losing several players at one position can hurt depth, but does not automatically make a bet.')
      : section('Injuries', '<p class="small muted">College injury reports are not covered by the feed. Check team sources before relying on a projection.</p>');

    /* Touchdown watch: recent role snapshots only, before kickoff. */
    const tdw = pregame ? (detail.scorerResearch || []).filter(r => r.roleSnapshotAt && now - Date.parse(r.roleSnapshotAt) >= 0 && now - Date.parse(r.roleSnapshotAt) <= 7 * 86400000 && (r.games ?? 0) >= 3).slice(0, 5) : [];
    const tdAt = tdw.map(r => r.roleSnapshotAt).sort().pop();
    const touchdownSide = side => {
      const rows = tdw.filter(r => r.side === side);
      return `<div class="card"><h3>${esc(g[side].name)}</h3>${rows.length ? rows.map(r =>
        `<p class="small"><a href="#player/${esc(g.league)}/${esc(r.athleteId)}"><b>${esc(r.player)}</b></a><br>
        ${esc(r.redZone)} red-zone carries + targets · ${esc(r.inside10)} inside the 10<br>
        ${esc(r.touchdowns)} TDs in ${esc(r.games)} games · ${esc(r.priceStatus || 'No verified TD price')}</p>`
      ).join('') : '<p class="small muted">No verified opportunity rows.</p>'}</div>`;
    };
    const tdHtml = tdw.length ? section('Touchdown opportunities', `<div class="grid two">${touchdownSide('away')}${touchdownSide('home')}</div>`, '',
      `Scoring opportunity research. Role data as of ${esc(ago(tdAt))}.`) : '';
    const sheet = pregame ? anchored('model-vs', section("Kook’n Prediction", modelBlock,
      `<a class="more" href="#game/${esc(g.id)}#model-vs" data-copy-link>Copy matchup link</a>`,
      'Projected score, spread and total compared with the captured market.')) : '';

    return `${back}${head(g.league === 'CFB' ? 'College football' : 'NFL', title, '')}${header}${postedHtml}${linePreview}${quickNumber}${sheet}${tdHtml}${actions}${liveStamp(liveNow.refreshed)}
      ${finalHtml}
      ${whySection(g, why, final)}
      ${pregame ? anchored('lines-we-like', section('Lines we like', favHtml, why && !final ? `<a class="more" href="#game/${esc(g.id)}#why">Why my number differs →</a>` : '', fav.length ? 'Current prices where my estimated chance is above what the price needs. Research, not extra best bets.' : 'Research held until the stated check clears. Not an official play.')) : ''}
      ${edgesHtml ? section('Matchup lines', edgesHtml, '<span class="small muted">Research, not posted plays</span>', 'Our projection, this-season hit rate at the exact line, and the opponent defense in one view. College game-script cautions rank lower.') : ''}
      ${othersHtml ? `<section class="section">${othersHtml}</section>` : ''}
      ${pregame || (final && detail.final) ? '' : anchored('model-vs', section('Model vs market', modelBlock))}
      ${upsetHtml}${trendsHtml}${depthHtml}${projHtml}${alternateHtml}${matchupHtml}
      ${section('Recent form', `<div class="grid two">${form('away')}${form('home')}</div>`)}
      ${injuryHtml}`;
  };
  return { game };
});
