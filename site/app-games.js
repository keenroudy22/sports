'use strict';
/* Lazily loaded Games pages: the slate (with the college navigator), live scores, finals, the game page and the team page.
   app.js supplies the shared, already-tested view helpers; this bundle stays out of the first-load shell. */
(function (root, factory) {
  root.KRGames = factory;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (ctx) {
  const { C, L, state, esc, head, section, empty, seg, segLinks, FOOTBALL, LEAGUE_NAME, teamDirectory, maybe, get, indexGames, withLive,
    defenseRows, defGames, defenseVerdict, projCard, teamMark, headshot, whenShort, dayLabel, bookLabel, ago, niceTitle, oddsText, isNum, inLeague,
    watchButton, setLeague, liveStamp, liveFor, LIVE, gapScore, STAT_WORD, favSpread, marketLabel, quoteAge, round1, fairAmerican, boardRow,
    matchupSignals, researchPrice, pctText, currentUpset, upsetRow, heavyFavorite, trendText, opponentTrendText, historyChart, ticket, ticketButton, etDay,
    pickVM, resultLine, odd } = ctx;
  const views = {};
  /* Navigator, "why" and badge styles arrive with this bundle, so the first-load shell stays inside its budget. */
  const GAMES_CSS = ".tier { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font: 700 12px/1 var(--font-display); letter-spacing: .08em; text-transform: uppercase; border: 1px solid var(--line-strong); color: var(--chalk); white-space: nowrap; }\n"
    + ".tier::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--dim); }\n.tier.competitive::before { background: var(--kookd); } .tier.lean::before { background: var(--chalk); } .tier.mismatch::before { background: var(--dim); } .tier.blowout::before { background: var(--burnt); }\n"
    + ".pc-plain { font: 500 14px/1.4 var(--font-body); color: var(--chalk); border-top: 1px solid var(--line); padding-top: 8px; }\n"
    + ".pc-bet { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px 10px; font: 500 14px/1.3 var(--font-body); color: var(--dim); }\n.pc-bet b { display: block; font: 700 12px/1 var(--font-display); letter-spacing: .1em; text-transform: uppercase; color: var(--dim); margin-bottom: 3px; }\n.pc-bet .v { color: var(--chalk); font-weight: 600; }\n.pc-bet .flag { display: block; color: var(--burnt-text); font-weight: 600; }\n.pc-bet .age, .pc-bet-h { grid-column: 1 / -1; font-size: 13px; }\n.pc-bet-h { font: 700 12px/1 var(--font-display); letter-spacing: .1em; text-transform: uppercase; color: var(--kookd); }\n"
    + ".pc-why { font: 500 14px/1.45 var(--font-body); color: var(--chalk); border-top: 1px dashed rgba(169, 192, 179, .28); padding-top: 8px; }\n.pc-why a { white-space: nowrap; font-weight: 700; display: inline-flex; align-items: center; min-height: var(--tap); }\n.pc-why.muted { color: var(--dim); }\n"
    + ".kt-worth-strip { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(196px, 1fr); gap: 10px; margin: 10px 0 6px; padding-bottom: 6px; }\n.kt-worth-card { display: grid; gap: 4px; align-content: start; padding: 10px 12px; background: var(--felt); border: 1px solid var(--line); border-radius: var(--radius); color: var(--chalk); min-width: 0; }\n.kt-worth-card:hover { text-decoration: none; border-color: var(--line-strong); }\n.kt-worth-card .wc-t { font: 700 15px/1.1 var(--font-display); letter-spacing: .03em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n.kt-worth-card b { font: 500 14px/1.3 var(--font-body); color: var(--kookd); }\n.kt-worth-card small { font-size: 13px; color: var(--dim); }\n"
    + ".nav-bar { display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: center; margin: 0 0 12px; }\n.nav-bar .select { min-height: 38px; padding: 6px 10px; }\n"
    + ".today-game-list { display:grid; gap:8px; margin-top:10px; }\n.today-game-row { position:relative; display:grid; grid-template-columns:minmax(0,1fr) auto 16px; align-items:center; gap:10px; min-height:82px; padding:10px 12px; border:1px solid var(--line); border-radius:13px; background:linear-gradient(135deg,rgba(20,43,30,.95),rgba(8,22,15,.98)); color:var(--chalk); }\n.today-game-row:hover { border-color:var(--line-strong); text-decoration:none; }\n.today-game-row.is-live { border-color:rgba(32,199,116,.55); }\n.today-game-matchup { display:grid; grid-template-columns:minmax(0,1fr) 18px minmax(0,1fr); align-items:center; gap:5px; min-width:0; }\n.today-game-team { display:flex; align-items:center; gap:7px; min-width:0; }\n.today-game-team > span:last-child { display:grid; min-width:0; }\n.today-game-team b { overflow:hidden; font-size:14px; line-height:1.15; text-overflow:ellipsis; white-space:nowrap; }\n.today-game-team small { margin-top:2px; color:var(--dim); font-size:12px; }\n.today-game-at { color:var(--dim); font:700 12px/1 var(--font-display); text-align:center; text-transform:uppercase; }\n.today-game-read { display:grid; justify-items:end; min-width:98px; text-align:right; }\n.today-game-read small { color:var(--dim); font-size:12px; line-height:1.2; }\n.today-game-read b { margin-top:3px; font:700 21px/1 var(--font-display); }\n.today-game-read > span { margin-top:3px; color:var(--dim); font-size:12px; line-height:1.2; }\n.today-game-arrow { color:var(--kookd); font-size:24px; }\n@media(max-width:420px){.today-game-row{grid-template-columns:minmax(0,1fr) auto 12px;gap:6px;padding:9px}.today-game-matchup{grid-template-columns:minmax(0,1fr);gap:4px}.today-game-at{display:none}.today-game-team .tm{width:25px;height:25px}.today-game-team b{font-size:13px}.today-game-team small{display:none}.today-game-read{min-width:88px}}\n"
    + ".kt-why .vs { grid-template-columns: auto 1fr 1fr auto; font-size: 15px; }\n.kt-why .vs .num { font-variant-numeric: tabular-nums; }\n.kt-drivers { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }\n.kt-drivers li { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 8px; font: 500 15px/1.45 var(--font-body); }\n.kt-drivers li::before { content: '↑'; color: var(--kookd); font-weight: 700; text-align: center; }\n.kt-drivers li.against::before { content: '↓'; color: var(--burnt-text); }\n.kt-drivers li small { display: inline; color: var(--dim); font-size: 13px; }\n.kt-drivers li.mk { display: block; font: 700 12px/1 var(--font-display); letter-spacing: .12em; text-transform: uppercase; color: var(--dim); margin: 10px 0 2px; }\n.kt-drivers li.mk::before { content: none; }\n.kt-why:focus { outline: none; }\n.kt-why, .section[id] { scroll-margin-top: 64px; }\n"
    + ".kt-why-note { margin-top: 12px; padding: 10px 12px; border-left: 3px solid var(--burnt); background: var(--burnt-soft); font: 500 14px/1.4 var(--font-body); }\n.kt-why-foot { margin-top: 12px; font: 500 14px/1.45 var(--font-body); color: var(--dim); }\n"
    + ".matchup-pick-list { display:grid; gap:8px; }\n.matchup-pick { display:grid; grid-template-columns:minmax(0,1fr) auto; grid-template-areas:'title state' 'terms state' 'numbers numbers'; gap:4px 12px; padding:12px 14px; border:1px solid var(--line); border-radius:12px; background:rgba(9,23,16,.86); }\n.matchup-pick-title { grid-area:title; min-width:0; font:700 17px/1.2 var(--font-body); color:var(--chalk); }\n.matchup-pick-terms { grid-area:terms; color:var(--dim); font-size:13px; }\n.matchup-pick-state { grid-area:state; align-self:center; padding:4px 8px; border-radius:999px; background:rgba(242,247,244,.1); color:var(--chalk); font:700 12px/1 var(--font-body); }\n.matchup-pick.is-win .matchup-pick-state { background:var(--kookd-soft); color:#70e9aa; }\n.matchup-pick.is-loss .matchup-pick-state { background:var(--burnt-soft); color:var(--burnt-text); }\n.matchup-pick-numbers { grid-area:numbers; display:flex; flex-wrap:wrap; gap:5px 14px; margin-top:4px; padding-top:7px; border-top:1px solid rgba(169,192,179,.13); color:var(--dim); font-size:12px; }\n.matchup-pick-numbers b { color:var(--chalk); }\n.matchup-ticket-more { margin-top:8px; }\n.matchup-ticket-more .tickets { margin-top:10px; }\n@media(max-width:420px){.matchup-pick{grid-template-columns:minmax(0,1fr) auto;padding:11px}.matchup-pick-title{font-size:16px}.matchup-pick-numbers{gap:4px 10px}}\n"
    + ".prop-teams { display:grid; gap:14px; min-width:0; max-width:100%; }\n.prop-team { margin:0; min-width:0; max-width:100%; }\n.prop-team > .table-wrap, .prop-team > .prop-market-more { min-width:0; max-width:100%; }\n.prop-team > summary { min-height:48px; display:flex; align-items:center; gap:9px; font:700 17px/1.2 var(--font-display); }\n.prop-compare { min-width:630px; table-layout:fixed; }\n.prop-compare th:first-child { width:220px; position:sticky; left:0; z-index:2; background:var(--felt); }\n.prop-compare thead th:first-child { z-index:3; }\n.prop-compare th.prop-player { width:220px; padding:12px; overflow:hidden; white-space:normal; }\n.prop-compare td { width:190px; vertical-align:top; padding:10px; }\n.prop-player-head { display:flex; align-items:baseline; gap:7px; min-width:0; }\n.prop-player-head a { min-width:0; overflow-wrap:anywhere; font-weight:700; line-height:1.2; }\n.prop-player-head .prop-pos { flex:none; color:var(--dim); font-size:12px; }\n.prop-player .badge { display:inline-flex; max-width:100%; margin:6px 0 0; overflow:hidden; text-overflow:ellipsis; }\n.prop-min { display:grid; gap:2px; margin-top:7px; color:var(--dim); font:500 12px/1.3 var(--font-body); }\n.prop-min b { color:var(--chalk); font-size:12px; }\n.prop-min span { display:block; overflow-wrap:anywhere; }\n.prop-cell { display:grid; gap:5px; min-height:74px; padding:2px; color:var(--chalk); }\n.prop-cell:hover { text-decoration:none; }\n.prop-cell span { color:var(--dim); font:500 12px/1.3 var(--font-body); }\n.prop-vs { display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:center; gap:7px; padding-bottom:5px; border-bottom:1px solid rgba(169,192,179,.14); }\n.prop-vs > span:not(.prop-vs-mark) { display:grid; gap:2px; min-width:0; }\n.prop-vs > span:last-child { text-align:right; }\n.prop-vs .prop-vs-label { color:var(--dim); font:700 10px/1 var(--font-display); letter-spacing:.08em; text-transform:uppercase; }\n.prop-vs b { color:var(--chalk); font:700 20px/1 var(--font-display); font-variant-numeric:tabular-nums; }\n.prop-vs .prop-vs-mark { color:var(--dim); font:700 10px/1 var(--font-display); text-transform:uppercase; }\n.prop-cell.prop-held .prop-vs > span:last-child b { color:var(--burnt-text); }\n.prop-cell .prop-gap { display:flex; align-items:baseline; justify-content:space-between; gap:6px; color:var(--dim); }\n.prop-cell .prop-gap b { color:var(--chalk); font:700 14px/1 var(--font-display); }\n.prop-cell .prop-price { color:#d8e4dd; }\n.prop-cell .prop-price.is-missing { color:var(--dim); }\n.prop-cell .lean-tag, .prop-cell .pick-tag { justify-self:start; margin-top:2px; padding:3px 6px; border-radius:999px; color:#70e9aa; background:var(--kookd-soft); font-weight:700; }\n.prop-cell .pick-tag { color:var(--chalk); background:rgba(242,247,244,.12); }\n.prop-cell.liked { margin:-6px; padding:7px; border:1px solid var(--kookd); border-radius:8px; background:rgba(32,201,117,.07); }\n.prop-cell.official { border-color:var(--chalk); }\n.prop-market-more { margin-top:10px; }\n.prop-team-note { margin:0 0 9px; color:var(--dim); font-size:12px; }\n.prop-position + .prop-position { margin-top:10px; }\n.prop-depth-more { margin:6px 0 2px; border:0; background:transparent; }\n.prop-depth-more > summary { min-height:38px; color:var(--kookd); font-size:13px; }\n.prop-depth-more[open] > summary { margin-bottom:8px; }\n.prop-depth-more .prop-compare { min-width:820px; }\n.prop-legend { display:flex; flex-wrap:wrap; gap:7px 14px; margin:8px 0 12px; color:var(--dim); font-size:12px; }\n.prop-legend b { color:var(--chalk); }\n.prop-legend .lean-key { padding:3px 7px; border:1px solid var(--kookd); border-radius:999px; color:#70e9aa; background:rgba(32,201,117,.07); }\n@media (max-width: 520px) { .prop-compare { min-width:0; } .prop-compare th:first-child, .prop-compare th.prop-player { width:168px; } .prop-compare td { width:184px; } }\n"
    + ".prop-player-head { flex-wrap:wrap; }\n@media (max-width:760px) { .prop-team > .table-wrap, .prop-position > .table-wrap, .prop-depth-more > .table-wrap { overflow:visible; } .prop-team > summary { position:sticky; top:52px; z-index:4; margin:0 -4px 8px; padding:0 7px; border-radius:8px; background:rgba(9,24,16,.97); } .prop-compare { display:block; min-width:0; width:100%; } .prop-compare caption { padding:5px 2px 7px !important; color:var(--kookd); font-weight:700; text-transform:uppercase; letter-spacing:.06em; } .prop-compare thead { display:none; } .prop-compare tbody { display:grid; gap:10px; } .prop-compare tr { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); border:1px solid var(--line); border-radius:12px; background:rgba(7,18,13,.7); overflow:hidden; } .prop-compare th:first-child, .prop-compare th.prop-player { position:static; grid-column:1/-1; width:auto; padding:11px 12px; border:0; border-bottom:1px solid var(--line); background:rgba(20,43,30,.92); } .prop-compare td { display:block; width:auto; min-width:0; padding:9px 8px; border:0; border-right:1px solid rgba(169,192,179,.12); } .prop-compare td:last-child { border-right:0; } .prop-compare td::before { content:attr(data-stat); display:block; margin-bottom:6px; color:var(--kookd); font:700 11px/1 var(--font-display); letter-spacing:.08em; text-transform:uppercase; } .prop-cell { min-height:0; gap:4px; } .prop-cell span { font-size:11px; line-height:1.25; } .prop-vs { gap:4px; padding-bottom:5px; } .prop-vs b { font-size:18px; } .prop-vs .prop-vs-label, .prop-vs .prop-vs-mark { font-size:9px; } .prop-cell.liked { margin:-4px; padding:5px; box-shadow:inset 3px 0 0 var(--kookd); } .prop-player .badge { margin:0 0 0 7px; } .prop-min { display:flex; flex-wrap:wrap; justify-content:space-between; gap:3px 10px; margin-top:7px; } .prop-min b, .prop-min span { flex:0 1 auto; min-width:0; text-align:left; overflow-wrap:normal; } }\n@media (max-width:420px) { .prop-compare tr { grid-template-columns:repeat(2,minmax(0,1fr)); } .prop-compare td:nth-child(4) { grid-column:1/-1; border-top:1px solid rgba(169,192,179,.12); } }\n"
    + `.cbb-slate { list-style:none; padding:0; margin:12px 0; border:1px solid var(--line); border-radius:var(--radius); background:var(--felt); }
      .cbb-slate li + li { border-top:1px solid var(--line); }
      .cbb-slate-row { display:grid; grid-template-columns:minmax(0,1.75fr) minmax(0,1fr) minmax(0,1.3fr) minmax(0,.85fr);
        gap:12px; align-items:start; padding:12px 14px; color:var(--chalk); font-variant-numeric:tabular-nums; }
      .cbb-slate-row:hover { background:var(--felt-high); text-decoration:none; }
      .cbb-slate-row:hover .cbb-slate-matchup b { text-decoration:underline; }
      .cbb-slate-row:focus-visible { outline-offset:-3px; }
      .cbb-slate-row span { display:grid; gap:3px; min-width:0; overflow-wrap:anywhere; }
      .cbb-slate-row small { font-size:12px; line-height:1.25; color:var(--dim); }
      .cbb-slate-row b { font-size:14px; line-height:1.25; }
      @media (max-width:600px) {
        .cbb-slate-row { grid-template-columns:minmax(0,1fr) minmax(0,1.25fr) minmax(0,.8fr); gap:8px; padding:11px; }
        .cbb-slate-matchup { grid-column:1/-1; }
      }
      @media (max-width:359px) { .pc-bet { grid-template-columns:1fr 1fr; } }`;
  if (typeof document !== 'undefined' && document.head && document.createElement && !(document.getElementById && document.getElementById('kr-games-css'))) {
    const style = document.createElement('style'); style.id = 'kr-games-css'; style.textContent = GAMES_CSS; document.head.appendChild(style);
  }
  /* ---------- the college slate navigator (owner, Oct 7, item 30): research grouping, never a play ---------- */
  const TIER_WORD = { competitive: 'Competitive', lean: 'Lean', mismatch: 'Mismatch', blowout: 'Blowout' };
  const WINDOW_WORD = { noon: 'Noon', afternoon: '3:30', night: 'Night' };
  /* The tier comes from the book's spread; the number is the model gap: how far my number sits from that line. */
  const gapNum = n => C.fixed(Math.abs(n), Math.abs(n) % 1 ? 1 : 0);
  const tierBadge = g => {
    if (!g.tier || !isNum(Number((g.market || {}).spread))) return '';
    const gap = g.gap && isNum(Number(g.gap.difference)) ? Number(g.gap.difference) : null;
    return `<span class="tier ${esc(g.tier)}" title="Tier by the book spread (${esc(favSpread(g.home.abbr, g.away.abbr, g.market.spread))}): competitive to 7, lean to 14, mismatch to 21, blowout past that.${gap == null ? '' : ` Gap ${esc(gapNum(gap))}: how far my number sits from that line.`}">${esc(TIER_WORD[g.tier])}${gap == null ? '' : ` · gap ${esc(gapNum(gap))}`}</span>`;
  };
  /* The same lean the card's My side column shows: a side or total only when its chance clears the price bar. */
  const leanWord = (g, which) => {
    const lean = C.leanText(g) || {}, m = g.market || {}, thin = Boolean((g.v2 || {}).sparse);
    const live = part => Boolean(part && part.chance != null && C.leanTone(part.chance, thin));
    if (which === 'spread') return live(lean.side) ? `${lean.side.team} ${C.signed(lean.side.team === g.home.abbr ? m.spread : -m.spread, 1).replace(/\.0$/, '')}` : 'no lean';
    return live(lean.total) && m.total != null ? `${lean.total.direction} ${m.total}` : 'no lean';
  };
  /* The research rows under a projection card: tier, the plain strength gap, what is bettable, and the specific reason. */
  const cardExtras = (g, now = Date.now()) => {
    if (g.completed || g.state === 'in') return {};
    const m = g.market || {}, parts = g.bettableParts || {};
    const fresh = m.retrievedAt ? quoteAge(m.retrievedAt, g.kickoff, now, { odds: -110, state: 'open' }) : null;
    const props = Number(parts.props) || 0;
    const bet = m.spread == null && m.total == null ? '' : `<div class="pc-bet"><span class="pc-bet-h">What's bettable · research</span><span><b>Spread</b><span class="v">${esc(leanWord(g, 'spread'))}</span></span><span><b>Total</b><span class="v">${esc(leanWord(g, 'total'))}</span></span><span><b>Props</b><span class="v">${props ? `${props} priced` : 'none priced'}</span>${g.garbageTime ? '<span class="flag">Garbage-time risk</span>' : ''}</span>${fresh ? `<span class="age">${esc(fresh.label)}</span>` : ''}</div>`;
    const w = g.whyDiffer;
    const why = !w ? '' : w.stale ? `<p class="pc-why muted">${esc(w.text)}</p>` : w.text ? `<p class="pc-why">${esc(w.text)} <a href="#game/${esc(g.id)}#why">Dig deeper ›</a></p>` : '';
    return { badge: tierBadge(g), extra: `${g.plainGap ? `<p class="pc-plain">${esc(g.plainGap)}</p>` : ''}${bet}${why}` };
  };
  const navCard = (g, opts = {}) => {
    if (g.cbbSource) return cbbGameCard(g.cbbSource);
    if (g.nbaSource) return nbaGameCard(g.nbaSource);
    const { badge, extra } = cardExtras(g);
    const market = g.market || {};
    const forecastAt = g.v2?.publishedAt;
    const modelAge = forecastAt ? `<p class="small muted">Projection · ${esc(whenShort(forecastAt))}</p>` : '';
    const priceAge = market.retrievedAt ? quoteAge(market.retrievedAt, g.kickoff, Date.now(), { odds: -110, state: 'open' }) : null;
    const currentPrice = priceAge && ['fresh', 'aging'].includes(priceAge.kind);
    const checked = market.retrievedAt ? `<p class="small ${currentPrice ? 'muted' : 'caution'}">${currentPrice ? '' : 'Reference price · '}${esc(bookLabel(market.book) || 'Book')} · checked ${esc(ago(market.retrievedAt))}</p>` : '';
    return projCard(g, { ...opts, badge, extra: checked + modelAge + (extra ? `<details class="more-box"><summary>Matchup notes</summary>${extra}</details>` : '') });
  };
  const projectionCards = (games, render, label, limit = 6) => {
    const first = games.slice(0, limit).map(g => render(g)).join('');
    const rest = games.slice(limit);
    return `<div class="projs">${first}</div>${rest.length ? `<details class="more-box"><summary>All ${games.length} ${esc(label)} games</summary><div class="projs">${rest.map(g => render(g)).join('')}</div></details>` : ''}`;
  };
  const byBettable = (a, b) => (Number(b.bettable) || 0) - (Number(a.bettable) || 0) || String(a.kickoff).localeCompare(String(b.kickoff)) || String(a.id).localeCompare(String(b.id));
  const worthStrip = list => {
    const top = list.filter(g => g.league === 'CFB' && !g.completed).slice().sort(byBettable).slice(0, 6);
    if (!top.length) return '';
    return `<section class="section" style="margin:8px 0 18px" aria-labelledby="worth-h"><div class="section-head"><h2 id="worth-h" style="white-space:nowrap">Worth your time</h2><span class="kt-kind">Research · the one thing to check</span></div>
      <div class="chip-scroll"><div class="kt-worth-strip">${top.map(g => `<a class="kt-worth-card" href="#game/${esc(g.id)}"><span class="wc-t">${esc(g.away.abbr)} at ${esc(g.home.abbr)}</span><b>${esc(g.look || g.plainGap || 'Take a look')}</b><small>${esc([TIER_WORD[g.tier], whenShort(g.kickoff).split(', ').pop(), !(g.bettableParts || {}).official ? 'Research lean · not a bet' : ''].filter(Boolean).join(' · '))}</small></a>`).join('')}</div></div></section>`;
  };
  const gameTabs = tab => `<div class="chip-scroll">${segLinks([['#games', 'Upcoming', 'upcoming'], ['#games/live', 'Live & scores', 'live'], ['#games/final', 'Finals', 'final']], tab)}</div>`;
  const teamSearch = () => `<div class="grow"><label class="sr" for="gq">Find a team</label><input id="gq" class="search" type="search" placeholder="Find a team" value="${esc(state.games.q || '')}" data-input="gq" autocomplete="off" maxlength="80"></div>`;
  const projectionWindow = (rows, newest = false) => {
    const q=String(state.games.q || '').trim().toLowerCase();
    const matches=rows.filter(g=>!q || ['home','away'].some(side=>Object.values(g.teams[side] || {}).some(v=>String(v).toLowerCase().includes(q))));
    const days=[...new Set(matches.map(g=>C.dayOf(g.kickoff)))].sort();
    const day=state.games.upDay==='all' || days.includes(state.games.upDay) ? state.games.upDay : newest ? days[days.length-1] : days[0];
    const labels=days.map(d=>[d,`${dayLabel(matches.find(g=>C.dayOf(g.kickoff)===d).kickoff)} · ${matches.filter(g=>C.dayOf(g.kickoff)===d).length}`]);
    return {rows:q || day==='all' ? matches : matches.filter(g=>C.dayOf(g.kickoff)===day),html:`<div class="toolbar">${days.length>1 ? `<div class="chip-scroll">${seg('gup',[...labels,['all',`All · ${matches.length}`]],day)}</div>`:''}${teamSearch()}</div>`};
  };
  const freshCbbSpread = (game, now = Date.now()) => {
    const age = now - Date.parse(game.spreadQuote?.observedAt);
    return age >= 0 && age <= 14400000 && Date.parse(game.kickoff) > now ? game.spreadQuote : null;
  };
  const cbbGameCard = (g, link = true) => {
    const name=t=>t.shortName || t.name || t.abbreviation;
    const season=y=>Number.isInteger(y) ? `${y-1}–${String(y).slice(-2)}` : '';
    const stat=s=>!s || !s.games ? 'No recorded games' : `${esc(s.wins)}–${esc(s.losses)} · ${esc(s.ppg)} scored / ${esc(s.allowed)} allowed · ${esc(s.games)} games`;
    const p=g.projection,h=g.teams.home,a=g.teams.away;
    const stats=['away','home'].map(side=>{const t=g.teams[side],s=(g.stats || {})[side] || {},c=s.current || {},prior=s.prior || {};return `<div><b>${esc(name(t))}</b><p class="small">This season · ${esc(season(c.season))}: ${stat(c)}</p><p class="small muted">Prior season · ${esc(season(prior.season))}: ${stat(prior)}</p></div>`;}).join('');
    const quote = g.firstTotal;
    const home = h.abbreviation || name(h), away = a.abbreviation || name(a);
    const margin = isNum(p.margin) ? p.margin : isNum(p.home) && isNum(p.away) ? p.home - p.away : null;
    const book = freshCbbSpread(g);
    const bookSpread = book ? C.modelSpread(home, away, -book.homeLine) : 'Unavailable';
    const spreadGap = book && margin != null ? margin + book.homeLine : null;
    const spreadDifference = spreadGap == null ? '—' : Math.abs(spreadGap) < .05 ? 'Same number'
      : `${C.fixed(Math.abs(spreadGap), 1)} toward ${spreadGap > 0 ? home : away}`;
    const difference = isNum(p.total) && isNum(quote?.line) ? C.fixed(p.total - quote.line, 1) : null;
    const first = `<div class="pc-lines nba-comparison"><span class="h"></span><span class="h">Kook’n</span><span class="h">Book</span><span class="h">Difference</span>
      <span class="k">Spread</span><span>${esc(C.modelSpread(home, away, margin))}</span><span>${esc(bookSpread)}</span><span>${esc(spreadDifference)}</span>
      <span class="k">Total</span><span>${esc(C.fixed(p.total, 1))}</span><span>${quote ? esc(quote.line) : 'Unavailable'}</span><span>${difference === null ? '—' : esc(difference)}</span></div>
      ${book ? `<p class="small muted">Spread · ${esc(book.book)} via ESPN · checked ${esc(whenShort(book.observedAt))}<br>${esc(C.spreadText(home, book.homeLine))} (${esc(oddsText(book.homeOdds))}) · ${esc(C.spreadText(away, book.awayLine))} (${esc(oddsText(book.awayOdds))})</p>` : ''}
      ${quote ? `<p class="small muted">First recorded total · ${esc(quote.book)} · ${esc(whenShort(quote.capturedAt))}. Historical quote, not a live offer.</p>` : ''}`;
    const team=t=>({id:t.id,name:name(t),abbr:t.abbreviation || name(t),logo:t.logo});
    return projCard({id:g.id,league:'CBB',kickoff:g.kickoff,neutral:p.neutral,state:'pre',home:team(h),away:team(a),v2:{home:p.home,away:p.away,total:p.total,sparse:p.sparse,winProb:p.winProb}}, {link,ranks:false,barLabel:'Baseline model win chance',extra:`${first}<details class="more-box"><summary>Team stats & model context</summary><p class="small muted">${p.neutral ? 'Neutral court' : 'Home court included'} · Not roster/injury adjusted</p>${stats}</details>`});
  };
  const cbbSlateRow = game => {
    const {away, home} = game.teams;
    const abbr = team => team.abbreviation || team.shortName || team.name;
    const name = team => team.shortName || team.name || abbr(team);
    const margin = game.projection?.margin ?? (isNum(game.projection?.home) && isNum(game.projection?.away)
      ? game.projection.home - game.projection.away : null);
    const spread = number => C.modelSpread(abbr(home), abbr(away), number);
    const quote = freshCbbSpread(game);
    const bookSpread = quote ? spread(-quote.homeLine) : 'Unavailable';
    const favoriteOdds = quote && (quote.homeLine < 0 ? quote.homeOdds : quote.awayLine < 0 ? quote.awayOdds : null);
    const total = isNum(game.projection?.total) ? C.fixed(game.projection.total, 1) : '—';
    return `<li><a class="cbb-slate-row" href="#game/${esc(game.id)}">
      <span class="cbb-slate-matchup"><b>${esc(name(away))} at ${esc(name(home))}</b><small>${esc(whenShort(game.kickoff))}</small></span>
      <span><small>Kook’n spread</small><b>${esc(spread(margin))}</b></span>
      <span><small>Book spread</small><b>${esc(bookSpread)}${isNum(favoriteOdds) ? ` · ${esc(oddsText(favoriteOdds))}` : ''}</b>${quote ? `<small>${esc(bookLabel(quote.book))}</small>` : ''}</span>
      <span><small>Kook’n total</small><b>${esc(total)}</b></span></a></li>`;
  };
  const BBALL_PRIMARY = [['pts','PTS'],['reb','REB'],['ast','AST']];
  const BBALL_EXTRA = [['fg3m','3PM'],['pra','PRA'],['pa','P+A'],['pr','P+R'],['ra','R+A']];
  const basketballStat = row => row.stat || ({points:'pts',rebounds:'reb',assists:'ast',threes:'fg3m'}[String(row.statName || '').toLowerCase()]);
  const isBasketballTeam = (row, team) => {
    if (row.team && team.id) return String(row.team) === String(team.id);
    return (row.teamAbbr && team.abbreviation && row.teamAbbr.toLowerCase() === team.abbreviation.toLowerCase())
      || (row.teamName && team.name && row.teamName.toLowerCase() === team.name.toLowerCase());
  };
  const basketballStatus = rows => {
    const holds = rows.map(row => row.hold).filter(Boolean);
    const availability = holds.map(text => /^Availability:\s*(.+)/i.exec(text)).find(Boolean);
    if (availability) return { word: availability[1], warn: !/^(available|active)$/i.test(availability[1].trim()) };
    if (holds.some(text => /report not submitted/i.test(text))) return { word: 'Report pending', warn: true };
    if (holds.some(text => /identity needs verification/i.test(text))) return { word: 'Status unverified', warn: true };
    if (holds.some(text => /role|minutes/i.test(text))) return { word: 'Role review', warn: true };
    if (rows.some(C.basketballAvailabilityHold)) return { word: 'Status unverified', warn: true };
    return rows.some(row => row.availabilityReportedAt) ? { word: 'Status checked', warn: false } : null;
  };
  const basketballMatchupProps = (league, game, picks, index, props) => {
    const gameRows = (props?.rows || []).filter(row => String(row.eventId) === String(game.providerId || String(game.id).replace(/^(?:NBA|CBB)-/, '')));
    const now = Date.now(), tip = Date.parse(game.kickoff);
    const pregame = (!game.status || game.status === 'scheduled') && tip > now;
    const posted = picks.filter(play => play.league === league && play.gameId === game.id
      && play.posted === true && !play.result && play.athleteId);
    const officialQuote = (row, stat) => row && posted.find(play => String(play.athleteId) === String(row.athleteId)
      && play.stat === stat && play.line === row.line && bookLabel(play.book) === bookLabel(row.book)
      && ['over', 'under'].includes(play.direction) && isNum(play.odds) && play.odds === row[play.direction]);
    const isFresh = row => {
      const age = now - Date.parse(row?.sourceAt);
      return pregame && age >= 0 && age <= 4 * 3600000;
    };
    const isLean = row => Boolean(row?.favorite && !row.hold && isFresh(row));
    const recentBoxCutoff = Number.isFinite(tip) ? new Date(tip - 30 * 86400000).toISOString().slice(0, 10) : '';
    const teams = ['away','home'].map(side => game.teams[side]);
    const teamPlayers = team => {
      const members = new Map();
      for (const entry of index.players || []) if (String(entry[3]) === String(team.id)) members.set(String(entry[0]), { id:String(entry[0]), name:entry[1], pos:entry[2], entry, stats:new Map() });
      for (const row of gameRows) {
        if (!isBasketballTeam(row, team)) continue;
        const key = String(row.athleteId || row.name);
        const player = members.get(key) || { id:row.athleteId || null, name:row.name, pos:null, entry:null, stats:new Map() };
        const stat = basketballStat(row);
        const previous = player.stats.get(stat);
        if (stat && (!previous || (!officialQuote(previous, stat) && officialQuote(row, stat)))) {
          player.stats.set(stat, row);
        }
        members.set(key, player);
      }
      const priority = player => [...player.stats.entries()].reduce((score,[stat,row]) => score + (officialQuote(row, stat) ? 100 : 0) + (isLean(row) ? 50 : 0) + (isNum(row.line) ? 20 : 0), 0);
      return [...members.values()].filter(player => player.stats.size || player.entry?.[7]?.values
        || (league === 'CBB' && recentBoxCutoff && player.entry?.[5] >= recentBoxCutoff))
        .sort((a,b) => priority(b)-priority(a) || Number(Boolean(b.stats.size))-Number(Boolean(a.stats.size))
          || Number(b.entry?.[7]?.minutes || 0)-Number(a.entry?.[7]?.minutes || 0)
          || String(b.entry?.[5] || '').localeCompare(String(a.entry?.[5] || '')) || String(a.name).localeCompare(String(b.name)));
    };
    const playerLine = (player, stat) => {
      const row = player.stats.get(stat), summary = player.entry?.[7] || null;
      const held = !pregame || Boolean(row?.hold) || [...player.stats.values()].some(C.basketballAvailabilityHold);
      const projection = held ? null : row ? row.projection?.value : summary?.values?.[stat];
      const line = isNum(row?.line) ? Number(row.line) : null;
      const official = officialQuote(row, stat);
      const direction = (official?.direction || row?.side) === 'under' ? 'under' : 'over';
      const href = player.id ? esc(C.playerLineHref({ league, athleteId: player.id, stat, line, direction, book: bookLabel(row?.book), gameId: game.id })) : '';
      const gap = isNum(projection) && line != null ? projection-line : null;
      const range = !held && isNum(row?.projection?.low) && isNum(row?.projection?.high) ? `${C.fixed(row.projection.low)}–${C.fixed(row.projection.high)}` : null;
      const recent = isNum(summary?.recent?.[stat]) ? `L5 avg ${C.fixed(summary.recent[stat])}` : row?.last5?.games && (row.side || 'over') === direction ? `L5 ${row.last5.hits}/${row.last5.games} ${direction}` : null;
      const price = line == null ? 'Book line unavailable' : [isNum(row.over) || isNum(row.under) ? `O ${isNum(row.over) ? oddsText(row.over) : '—'} / U ${isNum(row.under) ? oddsText(row.under) : '—'}` : '', row.book ? bookLabel(row.book) : ''].filter(Boolean).join(' · ');
      const liked = !official && !held && isLean(row);
      const body = `<span class="prop-vs"><span><span class="prop-vs-label">${line != null && !isFresh(row) ? 'Earlier line' : 'Book'}</span><b>${line == null ? '—' : esc(line)}</b></span><span class="prop-vs-mark">vs</span><span><span class="prop-vs-label">Kook’n</span><b>${isNum(projection) ? esc(C.fixed(projection)) : 'Held'}</b></span></span>${gap == null ? '' : `<span class="prop-gap">Projection gap <b>${gap > 0 ? '+' : ''}${esc(C.fixed(gap))}</b></span>`}${price ? `<span class="prop-price${line == null ? ' is-missing' : ''}">${esc(price)}</span>` : ''}${range ? `<span class="prop-range">Kook’n range ${esc(range)}</span>` : ''}${recent ? `<span class="prop-recent">${esc(recent)}</span>` : ''}${row?.sourceAt ? `<span class="prop-checked">${isFresh(row) ? 'Checked' : 'Earlier quote · checked'} ${esc(ago(row.sourceAt))}</span>` : ''}${official ? '<span class="pick-tag">Official pick</span>' : liked ? '<span class="lean-tag">Research lean</span>' : ''}`;
      return href ? `<a class="prop-cell${liked ? ' liked' : ''}${official ? ' official' : ''}" href="${href}">${body}</a>` : `<span class="prop-cell">${body}</span>`;
    };
    const table = (team, players, stats) => `<div class="table-wrap"><table class="t prop-compare"><thead><tr><th>Player · role</th>${stats.map(([,label]) => `<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${players.map(player => {
      const rows = [...player.stats.values()], status = basketballStatus(rows), role = rows.find(row => row.currentRole)?.currentRole, summary = player.entry?.[7];
      const projectedMinutes = !pregame || rows.some(C.basketballAvailabilityHold) ? null
        : rows.find(row => !row.hold && isNum(row.projection?.minutes))?.projection?.minutes ?? summary?.minutes;
      const minuteList = role?.minutes || summary?.recentMinutes || [];
      return `<tr><th class="prop-player"><span class="prop-player-head"><a href="${player.id ? `#player/${league}/${esc(player.id)}?stat=pts` : '#research/players'}">${esc(player.name)}</a><span class="prop-pos">${esc(player.pos || 'Position unavailable')}</span>${status ? `<span class="badge ${status.warn ? 'warn' : 'research'}">${esc(status.word)}</span>` : ''}</span><span class="prop-min"><b>${isNum(projectedMinutes) ? `Kook’n minutes ${esc(C.fixed(projectedMinutes))}` : 'Minutes projection held'}</b>${minuteList.length ? `<span>Recent ${minuteList.slice(-3).map(value => esc(C.fixed(value,0))).join(' · ')}</span>` : ''}</span></th>${stats.map(([stat,label]) => `<td data-stat="${esc(label)}">${playerLine(player,stat)}</td>`).join('')}</tr>`;
    }).join('')}</tbody></table></div>`;
    const blocks = teams.map(team => {
      const players = teamPlayers(team), extra = players.some(player => BBALL_EXTRA.some(([stat]) => player.stats.has(stat) || isNum(player.entry?.[7]?.values?.[stat])));
      const featured = players.slice(0,5), depth = players.slice(5);
      return `<details class="more-box prop-team" open><summary>${teamMark(team,'sm',league)} ${esc(team.name || team.abbreviation)} · ${players.length} players</summary>${players.length ? `<p class="prop-team-note">Priced lines, research leans and highest-minute roles first.</p>${table(team,featured,BBALL_PRIMARY)}${depth.length ? `<details class="more-box prop-depth-more"><summary>Show ${depth.length} more ${esc(team.abbreviation || '')} player${depth.length === 1 ? '' : 's'}</summary>${table(team,depth,BBALL_PRIMARY)}</details>` : ''}` : '<p class="small muted">No verified player projection or price is stored for this team yet.</p>'}${extra ? `<details class="more-box prop-market-more"><summary>Threes & combo markets</summary>${table(team,players,BBALL_EXTRA)}</details>` : ''}</details>`;
    }).join('');
    const checked = gameRows.map(row => row.sourceAt).filter(Boolean).sort().pop();
    return section('Player props & projections', `<p class="small"><b>Book line vs Kook’n projection.</b> Tap a stat to open its recent-game chart at that exact line.</p><div class="prop-legend"><span>Gap = Kook’n minus the book</span><span class="lean-key"><b>Green</b> research lean · not a pick</span></div><div class="prop-teams">${blocks}</div>`, '', `${league === 'NBA' ? 'Availability, minutes and current prices appear only when verified.' : 'Official box scores power the CBB baseline; unavailable prices stay unavailable.'} ${checked ? `Latest price check ${esc(ago(checked))}.` : 'No verified player price is stored for this matchup.'}`);
  };
  views.cbbPicks = (data, onlyToday = false) => {
    const r = data.picks || {}, all = r.plays || [];
    const plays = all.filter(p => !onlyToday || C.dayOf(p.kickoff) === etDay());
    if (!plays.length && onlyToday) return '';
    return `<section class="section" id="cbb-picks"><h2>CBB picks</h2><p>${esc(r.win || 0)}–${esc(r.loss || 0)} · ${esc(Number(r.units || 0).toFixed(2))}u</p><p class="small muted">${esc(r.note || 'Sourced desk picks, separate from model research and fun tickets.')}</p><div class="projs">${plays.map(p => {
      const t = p.game.teams, pick = p.marketType === 'total' ? `${p.direction.toUpperCase()} ${p.line}` : `${t[p.direction].abbreviation} ${p.line > 0 ? '+' : ''}${p.line}`;
      return `<article class="card" id="${esc(p.id)}"><p class="eyebrow">CBB PICK · 1u</p><h3>${esc(t.away.name)} at ${esc(t.home.name)}</h3><h2>${esc(pick)}</h2><p>${esc(p.odds > 0 ? '+' + p.odds : p.odds)} · ${esc(p.book)}</p><p>${esc(p.reason)}</p><details><summary>What could beat it</summary><p>${esc(p.countercase)}</p></details><p class="small">${esc(p.result ? p.result.toUpperCase() + ' · ' + (p.marketType === 'total' ? 'Game total: ' : t[p.direction].abbreviation + ' scoring margin: ') + p.actual : 'Open')} · Posted ${esc(whenShort(p.publishedAt))}</p><a href="data/cards/${esc(p.id.toLowerCase())}.png" target="_blank" rel="noopener">Original card ›</a></article>`;
    }).join('')}</div>${plays.length ? '' : '<p>No CBB straight posted yet.</p>'}<a href="#record?sport=CBB">Every CBB pick ›</a></section>`;
  };
  views.cbbToday = async (opts = {}) => {
    let data;
    try { data = await get('app/cbb.json'); }
    catch (_) { return head('College basketball', 'CBB projections & stats', 'Research, not picks.') + (opts.gamesPage ? gameTabs('upcoming') : '') + '<p>CBB research could not be loaded. Please try again.</p>'; }
    const available=(data.games || []).filter(g=>g.kickoff && Date.parse(g.kickoff)>Date.now());
    const window=projectionWindow(available),rows=window.rows,projected=rows.filter(g=>g.projection);
    const groups = new Map();
    for (const s of data.sheets || []) if (rows.some(g => g.date === s.date)) {
      if (!groups.has(s.date)) groups.set(s.date, []);
      groups.get(s.date).push(s);
    }
    const sheets = [...groups].map(([day, list], i) => `<details><summary>${esc(day)} · ${esc(list.length)} sheets</summary><div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:10px 0">${list.map(s => `<a class="btn" style="white-space:normal" href="data/app/${esc(s.file)}?v=${esc(encodeURIComponent(data.generatedAt || data.checkedAt || 'current'))}" target="_blank" rel="noopener">Sheet ${esc(s.page)}/${esc(s.pages)}</a>`).join('')}</div></details>`).join('');
    const availableCount = rows.filter(game => freshCbbSpread(game)).length;
    return head('College basketball', 'CBB projections & stats', `${rows.length} game${rows.length === 1 ? '' : 's'} · ${projected.length} projected · ${availableCount} with a fresh spread`)
      + `${opts.gamesPage ? gameTabs('upcoming') : views.cbbPicks(data, true)}
        ${!data.scheduleFresh ? '<p>Schedule update needed. Projections are held.</p>' : ''}
        ${window.html}
        ${rows.length ? `<ul class="cbb-slate" aria-label="College basketball matchups">${rows.map(cbbSlateRow).join('')}</ul>` : '<p>No upcoming games match this view.</p>'}
        ${sheets ? `<details class="more-box"><summary>Projection sheets</summary>${sheets}</details>` : ''}
        ${data.note ? `<details class="more-box"><summary>About these projections</summary><p class="small muted">${esc(data.note)}</p></details>` : ''}
        <p><a href="#games/live?sport=CBB">Live scores & finals ›</a> · <a href="#record?sport=CBB">CBB Results ›</a></p>`;
  };
  views.games = async route => {
    const tab = route.tab || 'upcoming';
    if (route.league) setLeague(route.league);
    if (state.league === 'CBB' && tab === 'upcoming') return views.cbbToday({gamesPage:true});
    const tabs = gameTabs(tab);
    const football = FOOTBALL.includes(state.league) || state.league === 'ALL';
    const intro = tab === 'live' ? 'Scores refresh about once a minute.' : tab === 'final' ? 'Final scores vs. our projections.' : football || state.league === 'NBA' ? 'Projected scores and the latest lines we captured.' : 'Scores and schedules.';
    const top = `${head('Games', tab === 'live' ? 'Live and scores' : tab === 'final' ? 'Recent finals' : 'Upcoming games', intro)}${tabs}`;
    if (tab === 'live') return top + await gamesLive();
    if (state.league === 'NBA') {
      let data;
      try { data=await get('app/nba.json'); }
      catch (_) { return `${head('NBA Games','NBA games & projections','Research, not best bets.')}${tabs}<p>NBA research could not be loaded. Please try again.</p>`; }
      const window=projectionWindow((data.games || []).filter(g => tab === 'final' ? g.status === 'final' : g.status !== 'final' && Date.parse(g.kickoff) >= Date.now()),tab==='final');
      const rows=window.rows;
      return `${head('NBA Games', tab === 'final' ? 'NBA finals' : 'NBA games & projections', 'Kook’n projections vs. sportsbook lines.')}${tabs}${window.html}${nbaProjectionContext(rows)}<div class="projs">${rows.map(g => nbaGameCard(g)).join('')}</div>${rows.length ? '' : '<p class="small muted">No matching NBA games are stored.</p>'}<p><a href="#today?sport=NBA">NBA plays, player lines & trends ›</a></p>`;
    }
    if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${await gamesLive({status:tab==='final' ? 'final' : 'scheduled'})}`;
    const [today,nba,cbb]=await Promise.all([get('app/today.json'),state.league==='ALL' ? maybe('app/nba.json') : null,state.league==='ALL' ? maybe('app/cbb.json') : null]);
    const merged = withLive((today.games || []).filter(inLeague));
    const nbaRows = (nba?.games || []).map(g => ({id:g.id,league:'NBA',kickoff:g.kickoff,completed:g.status === 'final',home:{...g.teams.home,abbr:g.teams.home.abbreviation},away:{...g.teams.away,abbr:g.teams.away.abbreviation},nbaSource:g}));
    const cbbRows=(cbb?.games || []).filter(g=>g.projection && Date.parse(g.kickoff)>Date.now()).map(g=>({id:g.id,league:'CBB',kickoff:g.kickoff,home:{...g.teams.home,abbr:g.teams.home.abbreviation},away:{...g.teams.away,abbr:g.teams.away.abbreviation},cbbSource:g}));
    let games = [...new Map([...merged.games,...nbaRows,...cbbRows].map(g => [g.id,g])).values()];
    const q = state.games.q.trim().toLowerCase();
    if (q) games = games.filter(g => [g.home.abbr, g.home.name, g.away.abbr, g.away.name].some(v => String(v || '').toLowerCase().includes(q)));
    const search = `<div class="grow"><label class="sr" for="gq">Find a team</label><input id="gq" class="search" type="search" placeholder="Find a team" value="${esc(state.games.q)}" data-input="gq" autocomplete="off" maxlength="80"></div>`;
    const byDay = (list, title = null) => {
      const days = new Map();
      list.forEach(g => { const d = dayLabel(g.kickoff); if (!days.has(d)) days.set(d, []); days.get(d).push(g); });
      return [...days.entries()].map(([d, l]) => `<p class="eyebrow" style="margin:18px 0 10px">${esc(title ? `${title} · ${d}` : d)}</p><div class="projs">${l.map(g => navCard(g, { compact: true, ranks: false })).join('')}</div>`).join('');
    };
    if (tab === 'final') {
      games = games.filter(g => g.completed).sort((a, b) => String(b.kickoff).localeCompare(String(a.kickoff)));
      const shown = state.games.all ? games : games.slice(0, 60);
      return `${top}<div class="toolbar">${search}</div>${liveStamp(merged.refreshed)}${shown.length ? byDay(shown) : empty(q ? 'No final matches' : 'No recent finals', q ? 'Try a team name or abbreviation.' : 'Finals from the last few days appear here.', 'games')}
        ${games.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-all-games>Show all ${games.length} finals</button></p>` : ''}`;
    }
    games = games.filter(g => !g.completed).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    const onDay = d => games.filter(g => C.dayOf(g.kickoff) === d);
    /* One day at a time: the next day with a game still to kick off, unless the reader picks another. */
    const dayKeys = [...new Set(games.map(g => C.dayOf(g.kickoff)))].sort();
    const day = state.games.upDay === 'all' || dayKeys.includes(state.games.upDay) ? state.games.upDay : dayKeys.find(d => onDay(d).some(g => Date.parse(g.kickoff) > Date.now())) || dayKeys[0];
    const toolbar = `<div class="toolbar">${dayKeys.length > 1 ? `<div class="chip-scroll">${seg('gup', [...dayKeys.map(d => [d, `${whenShort(onDay(d)[0].kickoff).split(',')[0]} · ${onDay(d).length}`]), ['all', `All · ${games.length}`]], day)}</div>` : ''}${search}</div>`;
    if (!games.length) return `${top}${toolbar}${empty(q ? 'No game matches' : 'No upcoming games', q ? 'Try a team name or abbreviation.' : 'Nothing in this league inside the current window.', 'games')}`;
    const list = q || day === 'all' ? games : onDay(day);
    const next = q || day === 'all' ? null : dayKeys[dayKeys.indexOf(day) + 1];
    const nextBtn = next ? `<p style="margin-top:12px"><button type="button" class="btn" data-set="gup:${next}">Next: ${esc(dayLabel(onDay(next)[0].kickoff))} · ${onDay(next).length} games →</button></p>` : '';
    /* College navigator: window, close-games and conference filters, bettable-first order. NFL keeps kickoff order with the same badges. */
    const college = list.some(g => g.league === 'CFB');
    const nav = state.games.nav || { window: 'all', close: false, conf: 'all' };
    const confs = [...new Set(list.flatMap(g => [(g.conference || {}).home, (g.conference || {}).away]).filter(Boolean))].sort();
    const chosenConf = confs.includes(nav.conf) ? nav.conf : 'all';
    const filtered = !college ? list : list.filter(g => g.league !== 'CFB' || (nav.window === 'all' || g.window === nav.window) && (!nav.close || g.tier === 'competitive')
      && (chosenConf === 'all' || [(g.conference || {}).home, (g.conference || {}).away].includes(chosenConf)));
    const sort = college && state.games.sort !== 'kickoff' ? 'bettable' : 'kickoff';
    const controls = !college ? '' : `<div class="nav-bar" role="group" aria-label="College slate filters"><div class="chip-scroll">${seg('gnav', [['window=all', 'All'], ['window=noon', 'Noon'], ['window=afternoon', '3:30'], ['window=night', 'Night']], `window=${nav.window}`)}</div>
      <button type="button" class="chip" data-set="gnav:close=1" aria-pressed="${Boolean(nav.close)}">Close games only</button>
      ${confs.length > 1 ? `<label class="sr" for="gconf">Conference</label><select id="gconf" class="select" data-select="gconf"><option value="all"${chosenConf === 'all' ? ' selected' : ''}>All conferences</option>${confs.map(c => `<option value="${esc(c)}"${c === chosenConf ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select>` : ''}
      ${seg('gsort', [['bettable', 'Bettable'], ['kickoff', 'Kickoff']], sort)}</div>`;
    const nbaList = filtered.filter(g => g.league === 'NBA');
    const nbaSection = nbaList.length ? `<section class="section" id="games-nba"><h2>NBA</h2><p class="small muted">Team projections and current book totals.</p>${nbaProjectionContext(nbaList.map(g => g.nbaSource))}${projectionCards(nbaList, navCard, 'NBA', q ? nbaList.length : 6)}<p><a href="#research/lines?sport=NBA">NBA player lines & trends ›</a></p></section>` : '';
    const cbbList = filtered.filter(g => g.cbbSource);
    const cbbSection = cbbList.length ? `<section class="section" id="games-cbb"><h2>College hoops</h2><p class="small muted">Kook vs Book spreads and totals.</p>${projectionCards(cbbList, navCard, 'CBB', q ? cbbList.length : 6)}</section>` : '';
    const sportJumps = state.league === 'ALL' ? `<nav class="chip-scroll" aria-label="Jump to sport">${filtered.some(g => g.league === 'NFL') ? '<a class="btn small" href="#games-football">NFL</a>' : ''}${college ? '<a class="btn small" href="#games-college">College football</a>' : ''}${nbaList.length ? '<a class="btn small" href="#games-nba">NBA</a>' : ''}${cbbList.length ? '<a class="btn small" href="#games-cbb">College hoops</a>' : ''}</nav>` : '';
    const stamp = liveStamp(merged.refreshed) + (state.league === 'ALL' && !nba ? '<p class="small muted">NBA data is unavailable right now. Football remains available.</p>' : '');
    if (!filtered.length) return `${top}${toolbar}${controls}${stamp}${empty('No game matches these filters', 'Try another window or conference, or turn off close games only.', 'games')}${nextBtn}`;
    const strip = college ? `<details class="more-box"><summary>More college research</summary>${worthStrip(filtered)}</details>` : '';
    if (sort === 'bettable') {
      const nfl = filtered.filter(g => g.league === 'NFL'), cfb = filtered.filter(g => g.league === 'CFB').sort(byBettable);
      const shown = state.games.all || q ? cfb : cfb.slice(0, 8);
      return `${top}${toolbar}${sportJumps}${controls ? `<details class="more-box"><summary>College filters & sorting</summary>${controls}</details>` : ''}${strip}${stamp}${nfl.length ? `<section id="games-football">${byDay(nfl, 'NFL')}</section>` : ''}
        <section id="games-college"><h2 style="margin-top:18px">College football</h2><p class="eyebrow">College · most bettable first</p><p class="small muted" style="margin:-6px 0 10px">Ranked for research.</p>
        <div class="projs">${shown.map(g => navCard(g, { compact: true, ranks: false })).join('')}</div>
        ${cfb.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-all-games>Show all ${cfb.length} games</button></p>` : nextBtn}</section>${nbaSection}${cbbSection}`;
    }
    return `${top}${toolbar}${controls}${strip}${stamp}${nbaSection}${byDay(filtered.filter(g => g.league !== 'NBA'))}${nextBtn}`;
  };
  const LIVE_WORD = { in_progress: 'Live', final: 'Final', scheduled: 'Scheduled', postponed: 'Postponed', delayed: 'Delayed', suspended: 'Suspended', cancelled: 'Cancelled', canceled: 'Cancelled' };
  const gamesLive = async (opts = {}) => {
    const [sports, todayRaw, history] = await Promise.all([maybe('sports.json'), maybe('app/today.json'), maybe('market-lab.json')]);
    const today = todayRaw || {};
    const day = opts.day || (state.games.day && [etDay(-1), etDay(), etDay(1)].includes(state.games.day) ? state.games.day : etDay());
    const leagues = state.league === 'ALL' ? Object.keys(LIVE) : [state.league];
    const status = opts.status || (opts.day ? 'all' : state.games.status);
    const controls = `<div class="toolbar">${seg('gday', [[etDay(-1), 'Yesterday'], [etDay(), 'Today'], [etDay(1), 'Tomorrow']], day)}${opts.status ? '' : seg('gstatus', [['all', 'All'], ['live', 'Live'], ['final', 'Final']], status)}${teamSearch()}</div>`;
    let failed = 0;
    const recent = (game, league) => {
      if (!['MLB', 'NHL'].includes(league)) return '';
      const teams = game.teams || {};
      const parts = ['away', 'home'].map(side => {
        const team = teams[side] || {};
        const rows = ((history || {}).recentResults || []).filter(row => row.league === league
          && Date.parse(row.kickoff) < Date.parse(game.kickoff)
          && [row.home?.id, row.away?.id].map(String).includes(String(team.id))).slice(0, 5).reverse();
        if (!rows.length) return '';
        return `<div><b>${esc(team.abbreviation || team.abbr || '')} · last ${rows.length} stored</b><div class="pill-row">${rows.map(row => {
          const home = String(row.home.id) === String(team.id), scored = home ? row.homeScore : row.awayScore;
          const allowed = home ? row.awayScore : row.homeScore, opponent = home ? row.away : row.home;
          return `<span class="pill"><small>${esc((opponent.abbreviation || opponent.shortName || '').slice(0, 12))}</small> <b class="${scored > allowed ? 'green' : scored < allowed ? 'red' : ''}">${esc(scored)}–${esc(allowed)}</b> <small>${esc(dayLabel(row.kickoff))}</small></span>`;
        }).join('')}</div></div>`;
      }).filter(Boolean);
      return parts.length ? `<details class="more-box" data-box="history:${esc(game.id)}" style="margin:-4px 0 8px"><summary>Recent team results</summary><div>${parts.join('')}<p class="small muted" style="margin-top:6px">Recorded finals only, not a complete season. Includes any preseason games we have.</p></div></details>` : '';
    };
    const blocks = leagues.map(league => {
      let stored;
      if (FOOTBALL.includes(league)) stored = (today.games || []).filter(g => g.league === league).map(g => { const pp = !g.completed && /postpon|cancel/i.test(String(g.status || ''));
        return { id: g.id, providerId: g.id.split('-').slice(1).join('-'), league, kickoff: g.kickoff, date: L.dayOf(g.kickoff), status: g.completed ? 'final' : pp ? (/cancel/i.test(g.status) ? 'cancelled' : 'postponed') : g.state === 'in' ? 'in_progress' : 'scheduled',
          statusDetail: g.status, teams: { home: { ...g.home, abbreviation: g.home.abbr, score: pp ? null : g.home.score }, away: { ...g.away, abbreviation: g.away.abbr, score: pp ? null : g.away.score } } }; });
      else stored = (((sports || {}).leagues || {})[league] || {}).games || [];
      stored = stored.filter(g => (g.date || L.dayOf(g.kickoff)) === day);
      /* Ask the scoreboard for every sport and day shown, even when nothing is stored yet. */
      const snap = liveFor(league, day);
      if (snap && snap.failed && !snap.at) failed += 1;
      let merged = snap ? L.mergeGames(stored.map(g => ({ ...g, date: g.date || day })), snap, day) : stored;
      const isLive = g => ['in_progress', 'delayed', 'suspended'].includes(g.status) || g.state === 'in';
      const isFinal = g => g.status === 'final' || g.completed;
      const q=String(state.games.q || '').trim().toLowerCase();
      if(q) merged=merged.filter(g=>['home','away'].some(side=>Object.values((g.teams || {})[side] || {}).some(v=>String(v).toLowerCase().includes(q))));
      if(status==='scheduled') merged=merged.filter(g=>g.status==='scheduled' && Date.parse(g.kickoff)>Date.now());
      if (status === 'live') merged = merged.filter(isLive);
      if (status === 'final') merged = merged.filter(isFinal);
      if (!merged.length) return '';
      return section(LEAGUE_NAME[league] || league, `${liveStamp(snap ? { ...snap, asked: true } : { asked: true })}<div class="games-list">${merged.map(g => {
        const teams = g.teams || {};
        const sc = g.scores || {};
        const scoreOf = side => sc[side] ?? teams[side]?.score ?? null;
        const live = isLive(g), final = isFinal(g);
        const t = side => ({ name: teams[side]?.name || teams[side]?.shortName, abbr: teams[side]?.abbreviation || teams[side]?.abbr, color: teams[side]?.color, logo: teams[side]?.logo, id: teams[side]?.id });
        const word = final ? (g.statusDetail && g.statusDetail !== 'Final' ? g.statusDetail : 'Final') : live ? (g.statusDetail || 'Live') : g.status && g.status !== 'scheduled' ? (LIVE_WORD[g.status] || g.statusDetail || g.status) : whenShort(g.kickoff);
        return `<div class="game-row" style="grid-template-columns:minmax(0,1fr) auto"><div class="teams"><div class="team">${teamMark(t('away'), 'sm', league)}<span class="name">${esc(t('away').name || '')}</span><span class="score num">${esc(scoreOf('away') ?? '')}</span></div><div class="team">${teamMark(t('home'), 'sm', league)}<span class="name">${esc(t('home').name || '')}</span><span class="score num">${esc(scoreOf('home') ?? '')}</span></div></div>
          <p class="game-meta" style="align-self:center;text-align:right">${live ? '<span class="live-dot"></span>' : ''}${esc(word)}${FOOTBALL.includes(league) ? `<br><a href="#game/${esc(g.id)}">Game page</a>` : g.source && /^https:\/\//.test(g.source.url || '') ? `<br><a href="${esc(g.source.url)}" target="_blank" rel="noopener">ESPN ↗</a>` : ''}</p></div>
          ${g.status === 'scheduled' && g.pregameOdds && snap && L.freshness(snap) === 'fresh' && Date.parse(g.kickoff) > Date.now() ? `<details class="more-box" data-box="pregame:${esc(g.id)}" style="margin:-4px 0 8px"><summary>Pregame lines · ${esc(g.pregameOdds.book)}</summary><div class="pill-row">${g.pregameOdds.rows.map(r => `<span class="pill">${esc(['away', 'home'].includes(r.side) ? ((g.teams || {})[r.side] || {}).abbreviation || r.side : r.side === 'over' ? 'Over' : 'Under')} ${esc(r.market)} ${r.line != null ? esc(r.market === 'Spread' ? C.signed(r.line) : r.line) + ' ' : ''}<b>${esc(oddsText(r.price))}</b></span>`).join('')}</div><p class="small muted" style="margin-top:6px">ESPN-supplied pregame quotes · checked ${esc(ago(new Date(snap.at).toISOString()))}. Book update time unavailable. Confirm in your sportsbook; these are not in-play odds or picks.</p></details>` : ''}${recent(g, league)}`;
      }).join('')}</div>`);
    }).join('');
    const none = failed === leagues.length ? empty('Score feed unavailable', 'The live scoreboard did not answer. Saved scores show when we have them. <button type="button" class="btn small" data-retry>Try again</button>', 'games')
      : empty(status === 'all' ? `No games ${day === etDay() ? 'today' : day === etDay(-1) ? 'yesterday' : 'tomorrow'}` : `No ${status} games`, 'Nothing on the schedule for this sport and filter.', 'games');
    return `${opts.day ? '' : controls}${blocks || `<div style="margin-top:14px">${none}</div>`}`;
  };

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
  const basketballScoreCard = (game, league) => {
    const final = game.status === 'final';
    const live = ['in_progress', 'delayed', 'suspended'].includes(game.status);
    const pastTip = Date.parse(game.kickoff) <= Date.now();
    const word = final || live || game.status && game.status !== 'scheduled'
      ? game.statusDetail || LIVE_WORD[game.status] || (final ? 'Final' : 'Live')
      : pastTip ? 'Score update pending' : game.hold || 'Team projection unavailable';
    const team = side => {
      const t = game.teams[side];
      return { ...t, abbr:t.abbreviation, score:final || live ? game.scores?.[side] ?? t.score : null };
    };
    return projCard({id:game.id, league, kickoff:game.kickoff, home:team('home'), away:team('away'),
      state:live ? 'in' : 'pre', completed:final, status:live ? word : ''}, {link:false, ranks:false})
      + `<p class="small muted">${esc(word)} · <a href="#games/live?sport=${league}">Live &amp; scores ›</a></p>`;
  };
  views.game = async route => {
    const back = '<a class="back" href="#games">← Games</a>';
    const league = /^(NBA|CBB)-/.exec(route.id)?.[1];
    if (league) {
      const dataRequest = get(`app/${league.toLowerCase()}.json`).catch(() => null);
      const [data, playerIndex, rows, picks] = await Promise.all([
        dataRequest,
        get(`app/players/${league}.json`).catch(() => ({players:[]})),
        league === 'NBA' ? dataRequest.then(data => C.nbaMatchupProps(get, data, route.id)) : Promise.resolve({rows:[]}),
        league === 'NBA' ? ctx.allPicks().catch(() => []) : Promise.resolve([])]);
      const research = data?.games?.find(g => g.id === route.id);
      const stored = research ? null : (await maybe('sports.json'))?.leagues?.[league]?.games?.find(g => g.id === route.id);
      const game = research || stored;
      if (!game) return head(league, 'Matchup unavailable', 'This game is outside the stored schedule.', back);
      const title = `${game.teams.away.name} at ${game.teams.home.name}`;
      const top = head(league, title, esc(whenShort(game.kickoff)), back);
      const card = research && league === 'NBA' ? nbaGameCard(research, false)
        : research?.projection ? cbbGameCard(research, false) : basketballScoreCard(game, league);
      return top + card + basketballMatchupProps(league, game, picks, playerIndex, rows);
    }
    let detail;
    try { detail = await get(`app/games/${route.id}.json`); } catch (e) {
      return head('', 'Game page not available', 'Game pages cover NFL and college football for games from about three days back to eight days ahead. <a href="#games/live">Live scores</a> cover every sport.', back);
    }
    const [today, teams, playerIndex] = await Promise.all([
      get('app/today.json'),
      teamDirectory(detail.league),
      get(`app/players/${detail.league}.json`).catch(() => ({players:[]}))]);
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
    const header = projCard({ ...g, v2: model, lean: detail.lean || fromSlate.lean, marketRead: detail.marketRead || fromSlate.marketRead }, { big: true, link: false, ...(pregame ? cardExtras({ ...g, whyDiffer: why }, now) : {}) }) + (qbText ? `<p class=caution>QB news: ${esc(qbText)}</p>` : '');
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
      const linePlayers = (playerIndex?.players || [])
        .filter(entry => String(entry[3] || '') === String(g[side].id || '') || String(entry[4] || '').toLowerCase() === String(g[side].abbr || '').toLowerCase())
        .filter(entry => /^(QB|RB|FB|WR|TE)$/.test(entry[2] || '') && Object.keys(lines[String(entry[0])] || {}).some(stat => lineStats.has(stat)))
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
        const v = player[key], stat = projectionMarket(key);
        if (!usableProjection(player,key)) return '<span class="prop-cell prop-held"><span class="prop-vs"><span><span class="prop-vs-label">Book</span><b>—</b></span><span class="prop-vs-mark">vs</span><span><span class="prop-vs-label">Kook’n</span><b>Held</b></span></span><span>Projection unavailable</span></span>';
        const market = (lines[player.id] || {})[stat], line = market && isNum(market[0]) ? Number(market[0]) : null;
        const exact = row => line != null && String(row.athleteId) === String(player.id)
          && C.marketKey(row) === stat && row.line === line;
        const reads = (detail.modelReads || []).filter(exact);
        const catalog = (detail.lines || []).filter(exact);
        const read = fav.find(exact) || reads.find(currentQuote) || catalog.find(currentQuote)
          || reads.find(row => isNum(row.odds)) || catalog.find(row => isNum(row.odds)) || reads[0] || catalog[0];
        const checked = read?.observedAt || (line != null ? detail.props?.capturedAt : null);
        const direction = String(read?.direction || 'over').toLowerCase() === 'under' ? 'under' : 'over';
        const gapV = line == null ? null : v[0]-line;
        const liked = fav.includes(read);
        const official = isNum(read?.odds) && picks.some(row => exact(row) && row.posted === true && !row.result
          && row.direction === direction && row.odds === read.odds && bookLabel(row.book) === bookLabel(read.book));
        const book = bookLabel(read?.book || detail.props?.provider);
        const href = esc(C.playerLineHref({ league: g.league, athleteId: player.id, stat, line, direction, book, gameId: g.id }));
        const price = line == null ? 'Book line unavailable' : [isNum(read?.odds) ? `${direction === 'under' ? 'U' : 'O'} ${oddsText(read.odds)}` : 'Odds unavailable', book].filter(Boolean).join(' · ');
        const saved = isNum(read?.odds) && !C.quoteStatus({ ...read, state: read.state || 'open' }, g.kickoff, now).current;
        return `<a class="prop-cell${liked ? ' liked' : ''}${official ? ' official' : ''}" href="${href}" title="Open the exact recent-game chart"><span class="prop-vs"><span><span class="prop-vs-label">Book</span><b>${line == null ? '—' : esc(line)}</b></span><span class="prop-vs-mark">vs</span><span><span class="prop-vs-label">Kook’n</span><b>${esc(C.fixed(v[0]))}</b></span></span>${gapV == null ? '' : `<span class="prop-gap">Projection gap <b>${gapV > 0 ? '+' : ''}${esc(C.fixed(gapV))}</b></span>`}${price ? `<span class="prop-price${line == null ? ' is-missing' : ''}">${esc(price)}</span>` : ''}<span class="prop-range">Kook’n range ${esc(C.fixed(v[1],0))}–${esc(C.fixed(v[2],0))}</span>${checked ? `<span class="prop-checked">${saved ? 'Earlier quote · checked' : 'Checked'} ${esc(ago(checked))}</span>` : ''}${official ? '<span class="pick-tag">Official pick</span>' : liked ? '<span class="lean-tag">Research lean</span>' : ''}</a>`;
      };
      const table = (pos, players) => {
        if (!players.length) return '';
        const hasLine = (player, key) => {
          const market = (lines[player.id] || {})[projectionMarket(key)];
          return market && isNum(market[0]);
        };
        const cols = POSITION_PROJ[pos].filter(([key]) => players.some(player => usableProjection(player,key) || player.unavailable && hasLine(player,key)));
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
          if (player.unavailable) return `<tr>${playerHead}${tableCols.map(([key]) => {
            const stat = projectionMarket(key), market = (lines[player.id] || {})[stat], line = market && isNum(market[0]) ? Number(market[0]) : null;
            const href = esc(C.playerLineHref({ league: g.league, athleteId: player.id, stat, line, direction: 'over',
              book: bookLabel(detail.props?.provider), gameId: g.id }));
            const label = tableCols.find(([candidate]) => candidate === key)?.[1] || key;
            return `<td data-stat="${esc(label)}"><a class="prop-cell prop-held" href="${href}" title="Open recent-game history"><span class="prop-vs"><span><span class="prop-vs-label">Book</span><b>${line == null ? '—' : esc(line)}</b></span><span class="prop-vs-mark">vs</span><span><span class="prop-vs-label">Kook’n</span><b>Held</b></span></span><span class="prop-price${line == null ? ' is-missing' : ''}">${line == null ? 'Book line unavailable' : 'Reference line · no active projection'}</span><span>${esc(player.status || 'Unavailable')} · no edge</span>${line != null && detail.props?.capturedAt ? `<span class="prop-checked">Checked ${esc(ago(detail.props.capturedAt))}</span>` : ''}</a></td>`;
          }).join('')}</tr>`;
          return `<tr>${playerHead}${tableCols.map(([key,label]) => `<td data-stat="${esc(label)}">${statCell(player,key)}</td>`).join('')}</tr>`;
        }).join('')}</tbody></table></div>`;
        const featured = ordered.filter(player => shownCols.some(([key]) => usableProjection(player,key))).slice(0,2);
        const featuredIds = new Set(featured.map(player => String(player.id || player.name)));
        const depth = ordered.filter(player => !featuredIds.has(String(player.id || player.name)));
        const visibleUnavailable = unavailable.filter(player => shownCols.some(([key]) => hasLine(player,key))).slice(0,1);
        const visibleUnavailableIds = new Set(visibleUnavailable.map(player => String(player.id || player.name)));
        const hiddenUnavailable = unavailable.filter(player => !visibleUnavailableIds.has(String(player.id || player.name)));
        const primaryRows = [...featured, ...visibleUnavailable];
        const extras = secondaryCols.length || depth.length || hiddenUnavailable.length;
        const extraRows = depth.length + hiddenUnavailable.length;
        return `<div class="prop-position">${primaryRows.length ? renderTable(primaryRows, `${pos} · featured`) : ''}${extras ? `<details class="more-box prop-depth-more"><summary>More ${esc(pos)} players &amp; markets${extraRows ? ` · ${extraRows}` : ''}</summary>${secondaryCols.length && featured.length ? renderTable(featured, `${pos} · more markets`, secondaryCols) : ''}${depth.length ? renderTable(depth, `${pos} · depth`, cols) : ''}${hiddenUnavailable.length ? renderTable(hiddenUnavailable, `${pos} · unavailable`, cols) : ''}</details>` : ''}</div>`;
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
  views.team = async route => {
    const league = route.league;
    const back = `<a class="back" href="#research/players?view=defense&pl=${esc(league)}">← Defenses</a>`;
    const [teams, detail, today, index] = await Promise.all([teamDirectory(league), maybe(`app/teams/${league}/${route.id}.json`), get('app/today.json'), maybe(`app/players/${league}.json`)]);
    indexGames(today);
    const team = detail || ((teams || {}).teams || {})[route.id];
    if (!team) return head('', 'Team not found', 'No stored games for this team.', back);
    const abbr = id => (((teams || {}).teams || {})[id] || {}).abbr || id;
    const season = ((teams || {}).defense || {}).season || index?.season;
    const played = ((detail || {}).games || []).filter(g => g.season === season);
    const wins = played.filter(g => g.pf > g.pa).length, losses = played.filter(g => g.pf < g.pa).length, ties = played.filter(g => g.pf === g.pa).length;
    const cover = g => {
      if (!g.close || g.close.spread == null || g.home == null) return null;
      const m = g.pf - g.pa + (g.home ? g.close.spread : -g.close.spread);
      return m > 0 ? 'Covered' : m < 0 ? 'Missed' : 'Push';
    };
    const ats = played.map(cover).filter(Boolean);
    const atsText = ats.length ? `${ats.filter(x => x === 'Covered').length}–${ats.filter(x => x === 'Missed').length}${ats.includes('Push') ? `–${ats.filter(x => x === 'Push').length}` : ''} against the spread` : '';
    const games = withLive((today.games || []).filter(g => g.league === league && [g.home.id, g.away.id].includes(String(route.id))).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))).games;
    const ranks = ['WR', 'RB', 'TE', 'QB'].map(pos => [pos, C.rankOf(defenseRows(teams, league), route.id, pos, pos === 'QB' ? 'passYds' : pos === 'RB' ? 'rushYds' : 'recYds')]).filter(([, r]) => r);
    const roster = ((index || {}).players || []).filter(p => String(p[3]) === String(route.id) && String(p[5] || '') >= `${season}-08-01`).sort((a, b) => (b[6] || 0) - (a[6] || 0)).slice(0, 40);
    const allowed = ((detail || {}).defense || []).filter(d => d.season === season).slice().reverse();
    const results = played.length ? `<div class="table-wrap"><table class="t"><thead><tr><th>Game</th><th class="n">Score</th><th class="n">Close</th><th class="n">ATS</th><th class="n">Yds</th><th class="n">Allowed</th></tr></thead><tbody>${played.slice().reverse().map(g => {
      const c = cover(g);
      return `<tr><td><a href="#game/${esc(g.gameId)}">${esc(String(g.date).slice(5))}</a> ${g.home === false ? '@' : g.home === null ? 'neutral' : 'vs'} ${esc(abbr(g.opp))}</td><td class="n ${g.pf > g.pa ? 'green' : g.pf < g.pa ? 'red' : ''}">${g.pf > g.pa ? 'W' : g.pf < g.pa ? 'L' : 'T'} ${esc(g.pf)}–${esc(g.pa)}</td>
        <td class="n">${g.close && g.close.spread != null && g.home != null ? esc(C.signed(g.home === false ? -g.close.spread : g.close.spread)) : '<span class="muted" title="Neutral site: the listed home side was not stored">–</span>'}</td><td class="n ${c === 'Covered' ? 'green' : c === 'Missed' ? 'red' : ''}">${esc(c || '–')}</td><td class="n">${esc((g.off || {}).yards ?? '–')}</td><td class="n">${esc((g.def || {}).yards ?? '–')}</td></tr>`;
    }).join('')}</tbody></table></div>` : `<p class="muted small">${detail ? 'Results appear after the first game.' : 'Game-by-game results are stored for FBS teams only.'}</p>`;
    return `${back}<div class="page-head" style="display:flex;gap:14px;align-items:center">${teamMark({ ...team, id: route.id }, 'xl', league)}<div><p class="eyebrow">${esc(league === 'CFB' ? 'College football' : 'NFL')}</p><h1>${esc(team.name)}</h1>
        <p class="sub">${played.length ? `${esc(season)}: <b>${wins}–${losses}${ties ? `–${ties}` : ''}</b>${atsText ? ` · ${esc(atsText)}` : ''}` : `${esc(season || '')} season`}</p></div></div>
      ${section('Upcoming and recent', `<div class="projs">${games.map(g => navCard(g)).join('') || '<p class="muted">No games in the current window.</p>'}</div>`)}
      ${section('This season', results, '', 'Close is the closing spread for this team. ATS is whether they covered it.')}
      ${ranks.length ? section('What this defense allows', `<div class="kpis">${ranks.map(([pos, r]) => { const tone = C.rankTone(r.rank, r.of); return `<div class="kpi"><small>${esc(pos)} ${pos === 'QB' ? 'pass' : pos === 'RB' ? 'rush' : 'rec'} yds</small><b class="num ${tone === 'soft' ? 'green' : tone === 'tough' ? 'red' : ''}">${esc(C.fixed(r.value))}</b><span>rank ${esc(r.rank)} of ${esc(r.of)}${tone === 'soft' ? ' · soft' : tone === 'tough' ? ' · tough' : ''}</span></div>`; }).join('')}</div>
        ${allowed.length ? `<details class="more-box" style="margin-top:12px"><summary>Game by game</summary><div class="table-wrap"><table class="t"><thead><tr><th>Game</th><th class="n">QB pass yds</th><th class="n">RB rush yds</th><th class="n">WR rec yds</th><th class="n">TE rec yds</th></tr></thead><tbody>${allowed.map(d => `<tr><td><a href="#game/${esc(d.gameId)}">${esc(String(d.date).slice(5))}</a> ${esc(abbr(d.opp))}</td><td class="n">${esc((d.allowed.QB || {}).passYds ?? '–')}</td><td class="n">${esc((d.allowed.RB || {}).rushYds ?? '–')}</td><td class="n">${esc((d.allowed.WR || {}).recYds ?? '–')}</td><td class="n">${esc((d.allowed.TE || {}).recYds ?? '–')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}`,
        `<a class="more" href="#research/players?view=defense&pl=${esc(league)}">All defenses →</a>`, 'Per game this season. Rank 1 allows the least.') : ''}
      ${section('Players this season', roster.length ? `<div class="list-links cols">${roster.map(p => `<a href="#player/${esc(league)}/${esc(p[0])}"><span class="with-art">${headshot(league, p[0], 'sm', team)}<span><b>${esc(p[1])}</b> <span class="muted small">${esc(p[2] || '')}</span></span></span><small>${esc(p[6] || 0)} game${Number(p[6]) === 1 ? '' : 's'} stored →</small></a>`).join('')}</div>` : '<p class="muted small">Players appear after their first stat line.</p>')}`;
  };
  views.gamesLive = gamesLive;
  function nbaTrialSection(data, readiness = '') {
    const trial = data.trial || {};
    const plays = (trial.plays || []).slice().reverse();
    const open = plays.filter(p => !p.result);
    const past = plays.filter(p => !open.includes(p));
    const ticket = p => {
      const side = p.marketType === 'player' ? `${p.player} ${p.direction} ${p.line} ${{pts:'points',reb:'rebounds',ast:'assists'}[p.stat] || ''}` : p.marketType === 'total' ? `${p.direction} ${p.line}` : p.marketType === 'moneyline' ? `${p.teams[p.direction].abbreviation} moneyline` : `${p.teams[p.direction].abbreviation} ${C.signed(p.line)}`;
return `<article class="card" style="margin-top:12px"><h3>${p.athleteId ? `<a href="#player/NBA/${esc(p.athleteId)}${p.stat ? `?stat=${esc(p.stat)}` : ''}">${esc(p.teams.away.abbreviation)} at ${esc(p.teams.home.abbreviation)} · ${esc(side)}</a>` : `${esc(p.teams.away.abbreviation)} at ${esc(p.teams.home.abbreviation)} · ${esc(side)}`}</h3><p>${esc(oddsText(p.odds))} ${esc(bookLabel(p.book))} · ${C.stakeOf(p)}u · ${esc(whenShort(p.kickoff))}</p><p class="small">${p.result ? `${esc(p.result)}${p.actual == null ? '' : ` · final ${esc(p.actual)}`}` : 'Open in the NBA record.'}</p>${p.athleteId ? `<p><a href="#player/NBA/${esc(p.athleteId)}${p.stat ? `?stat=${esc(p.stat)}` : ''}">Last 5, Last 10 & full player chart →</a></p>` : ''}<p class="small muted">Original published price; check your book.</p><img src="${esc(p.card)}" alt="NBA ticket" loading="lazy" style="max-width:100%;height:auto"></article>`;
    };
    return `<section class="kt-page-sec" id="nba-plays"><h2>Today's plays <span class="badge">NBA picks</span></h2>${open.length ? open.map(ticket).join('') : `<p class="small">${esc(String(trial.note || 'No NBA play has been posted.').replace(/NBA Trial/g, 'NBA picks'))}</p>`}<p class="small muted">New NBA picks use 1u within the shared daily exposure limit.</p><details class="more-box"><summary>NBA record: ${esc(trial.record?.win || 0)}–${esc(trial.record?.loss || 0)} · ${esc(Number(trial.record?.units || 0).toFixed(2))}u</summary><p class="small">${esc(trial.record?.graded || 0)} graded</p>${readiness}${past.map(ticket).join('')}${(trial.seasons || []).length > 1 ? trial.seasons.map(s => `<p>${esc(s.season-1)}–${esc(String(s.season).slice(-2))} · ${s.stage === 3 ? 'Playoffs' : 'Regular season'} · ${esc(s.record.win)}–${esc(s.record.loss)} · ${esc(Number(s.record.units).toFixed(2))}u</p>`).join('') : ''}</details></section>`;
  }
  const nbaProjectionContext = games => games.some(g => g.projection?.sparse && g.status !== 'final') ? '<p class="small muted nba-history">Early-season projections draw on last season’s team ratings while this season’s results build.</p>' : '';
  const nbaGameCard = (g, link = true) => {
    // The schedule snapshot can lag tipoff. Never show a cached pregame
    // projection as if the matchup were still upcoming, or invent a live score.
    if (g.status === 'scheduled' && Date.parse(g.kickoff) <= Date.now()) {
      const team = side => `<div class="pc-team">${teamMark(g.teams[side], 'md', 'NBA')}<b>${esc(g.teams[side].name || g.teams[side].abbreviation)}</b></div>`;
      return `<div class="proj"><div class="pc-meta"><span>${esc(whenShort(g.kickoff))} · NBA</span></div><div class="pc-top">${team('away')}<div class="pc-mid"><small>Update pending</small><b class="num">–</b><span>Tip time passed</span></div>${team('home')}</div><p class="small muted">The stored schedule has not updated. <a href="#games/live?sport=NBA">Check Live & scores ›</a></p></div>`;
    }
    const fresh = q => q && g.status === 'scheduled' && Date.now() < Date.parse(g.kickoff) && Date.now()-Date.parse(q.retrievedAt) >= 0 && Date.now()-Date.parse(q.retrievedAt) <= 14400000;
    const quote = fresh(g.totalQuote) ? g.totalQuote : null, spread = fresh(g.spreadQuote) ? g.spreadQuote : null, ml = fresh(g.moneylineQuote) ? g.moneylineQuote : null;
    const p = g.projection || {}, home = g.teams.home.abbreviation, away = g.teams.away.abbreviation;
    const margin = isNum(p.margin) ? p.margin : isNum(p.home) && isNum(p.away) ? Math.round((p.home-p.away)*10)/10 : null;
    const gap = n => Math.abs(n) < .05 ? 'Same number' : `${C.fixed(Math.abs(n),1)} ${n > 0 ? 'higher' : 'lower'}`;
    const comparison = g.status !== 'scheduled' ? '' : `<div class="pc-lines nba-comparison"><span class="h"></span><span class="h">Kook’n</span><span class="h">Book</span><span class="h">Difference</span>
      <span class="k">Spread</span><span>${margin == null ? '—' : esc(C.modelSpread(home,away,margin))}</span><span>${spread ? esc(C.modelSpread(home,away,-spread.homeLine)) : 'Unavailable'}</span><span>${spread && margin != null ? Math.abs(margin+spread.homeLine) < .05 ? 'Same number' : `${esc(C.fixed(Math.abs(margin+spread.homeLine),1))} toward ${esc(margin+spread.homeLine > 0 ? home : away)}` : '—'}</span>
      <span class="k">Total</span><span>${isNum(p.total) ? esc(C.fixed(p.total,1)) : '—'}</span><span>${quote ? esc(quote.line) : 'Unavailable'}</span><span>${quote && isNum(p.total) ? esc(gap(p.total-quote.line)) : '—'}</span></div>`;
    const prices = [spread ? `${home} ${C.signed(spread.homeLine)} (${oddsText(spread.home)}) · ${away} ${C.signed(spread.awayLine)} (${oddsText(spread.away)}) · ${bookLabel(spread.book)} · ${whenShort(spread.retrievedAt)}` : '',
      quote ? `Book total ${quote.line} · over ${oddsText(quote.over)} / under ${oddsText(quote.under)} · ${bookLabel(quote.book)} · ${whenShort(quote.retrievedAt)}` : '',
      ml ? `Moneyline: ${home} ${oddsText(ml.home)} · ${away} ${oddsText(ml.away)} · ${bookLabel(ml.book)} · ${whenShort(ml.retrievedAt)}` : ''].filter(Boolean);
    const extra = comparison + (prices.length ? `<p class="pc-why small">${prices.map(esc).join('<br>')}<br>Prices seen at the times above.</p>` : '') + (g.status === 'scheduled' ? '<p class="small muted">Projection differences, not picks or win probabilities. Missing or older-than-four-hour prices are not shown.</p>' : '');
    const team = side => ({...g.teams[side], abbr:g.teams[side].abbreviation, score:g.scores?.[side]});
    // Reuse football's bar with the stored score-model probability, never a
    // probability inferred from the score ratio, prices or projection gap.
    const v2 = {...p}; delete v2.margin;
    if (g.status !== 'scheduled') delete v2.winProb;
    const roster = g.status === 'scheduled' && g.rosterContext ? `<p class="small muted">${esc(g.rosterContext.note)}${g.rosterContext.holds?.length ? ' ' + g.rosterContext.holds.map(esc).join(' · ') : ''}</p>` : '';
    const adjustedMargin = g.rosterContext?.adjustedMarkets?.includes('margin');
    const modelNote = isNum(v2.winProb) && v2.winProb >= 0 && v2.winProb <= 1 ? `<p class="small muted">Model win chance is a score-model estimate; ${adjustedMargin ? 'validated roster adjustment applied; not a bet.' : 'not injury-adjusted or a bet.'}</p>` : '';
    return projCard({id:g.id,league:'NBA',kickoff:g.kickoff,home:team('home'),away:team('away'),state:g.status === 'in_progress' ? 'in' : 'pre',completed:g.status === 'final',v2},{link:link !== false,ranks:false,barLabel:'Model win chance',extra:comparison + (g.status === 'scheduled' && g.rosterContext?.holds?.length ? `<p class="small caution">${esc(g.rosterContext.holds.join(' · '))}</p>` : '') + (prices.length ? `<p class="small muted">${esc(bookLabel((spread || quote || ml).book))} · checked ${esc(ago((spread || quote || ml).retrievedAt))}</p>` : '<p class="small muted">No fresh book price.</p>') + `<details class="more-box"><summary>Prices & availability</summary>${extra.slice(comparison.length)}${roster}${modelNote}</details>`});
  };
  const nbaSummaryGame = g => {
    const p = g.projection || {}, delayed = g.status === 'scheduled' && Date.parse(g.kickoff) <= Date.now();
    const live = g.status === 'in_progress', final = g.status === 'final';
    const hasScore = (live || final) && isNum(g.scores?.away) && isNum(g.scores?.home);
    const label = delayed ? 'Update pending' : live ? 'Live' : final ? 'Final' : whenShort(g.kickoff);
    const score = delayed ? '—' : hasScore ? `${g.scores.away}–${g.scores.home}` : isNum(p.away) && isNum(p.home) ? `${C.fixed(p.away,0)}–${C.fixed(p.home,0)}` : '—';
    const freshTotal = g.totalQuote && g.status === 'scheduled' && Date.now() < Date.parse(g.kickoff) && Date.now()-Date.parse(g.totalQuote.retrievedAt) >= 0 && Date.now()-Date.parse(g.totalQuote.retrievedAt) <= 14400000;
    const note = delayed ? 'Tip time passed' : hasScore && isNum(p.away) ? `Kook’n had ${C.fixed(p.away,0)}–${C.fixed(p.home,0)}` : isNum(p.total) ? `Kook’n total ${C.fixed(p.total,1)}${freshTotal ? ` · Book ${g.totalQuote.line}` : ''}` : 'Projection pending';
    const team = side => { const t = g.teams[side]; return `<span class="today-game-team">${teamMark(t,'sm','NBA')}<span><b>${esc(t.name || t.displayName || t.abbreviation)}</b><small>${esc(t.abbreviation || '')}</small></span></span>`; };
    return `<a class="today-game-row${live ? ' is-live' : ''}" href="${delayed ? '#games/live?sport=NBA' : `#game/${esc(g.id)}`}"><span class="today-game-matchup">${team('away')}<span class="today-game-at">at</span>${team('home')}</span><span class="today-game-read"><small>${esc(label)}</small><b class="num">${esc(score)}</b><span>${esc(note)}</span></span><span class="today-game-arrow" aria-hidden="true">›</span></a>`;
  };
  views.nbaSummary = (data, { showPicks = true } = {}) => {
    const games = (data.games || []).filter(g => C.dayOf(g.kickoff) === etDay());
    const open = (data.trial?.plays || []).filter(p => !p.result && C.dayOf(p.kickoff) === etDay());
    if (!games.length && !open.length) return '';
    const picks = showPicks ? (open.length ? `${open.length} posted NBA pick${open.length === 1 ? '' : 's'} today. ` : 'No NBA play posted yet. ') : '';
    return `<section class="kt-sec" id="today-nba"><div class="kt-focus-head"><h2>Today’s NBA</h2><a href="#today?sport=NBA">NBA plays, props & trends ›</a></div><p class="small">${picks}${games.length} game${games.length === 1 ? '' : 's'} · tap a matchup for Kook vs Book.</p>${showPicks && open.length ? nbaTrialSection({...data,trial:{...data.trial,plays:open}}) : ''}${nbaProjectionContext(games)}${games.length ? `<div class="today-game-list">${games.slice(0,3).map(nbaSummaryGame).join('')}</div>` : ''}<a class="more" href="#today?sport=NBA">${games.length > 3 ? `See all ${games.length} NBA games` : 'Open NBA Today'} ›</a></section>`;
  };
  views.nbaToday = async (opts = {}) => {
    let data = opts.data || await get('app/nba.json');
    const matches = (...values) => !opts.q || C.researchMatches(opts.q, ...values);
    const mode = opts.mode || 'lines';
    const showGames = !opts.embedded || mode === 'lines' && opts.type !== 'props';
    const showProps = !opts.embedded || mode === 'players' || mode === 'lines' && opts.type !== 'games';
    const showTrends = !opts.embedded || mode === 'trends';
    if (showProps && data.playerPropsFile === 'nba-props.json' && !Array.isArray(data.playerProps?.rows)) {
      try {
        const props = await get('app/nba-props.json');
        if (!Array.isArray(props.rows)) throw new Error('Missing prop rows');
        data = { ...data, playerProps: props };
      } catch (_) {
        data = { ...data, playerProps: { ...data.playerProps, rows: [], note: 'Player comparisons could not be loaded. Refresh to retry; no missing estimate is shown.' } };
      }
    }
    const todayGames = (data.games || []).filter(g => C.dayOf(g.kickoff) === etDay());
    const focusDay = todayGames.length ? etDay() : (data.games || []).filter(g => Date.parse(g.kickoff) > Date.now()).map(g => C.dayOf(g.kickoff)).sort()[0];
    const focusGames = (data.games || []).filter(g => C.dayOf(g.kickoff) === focusDay);
    const teamsToday = new Set(focusGames.flatMap(g => Object.values(g.teams).map(t => String(t.id))));
    const laterGames = (data.games || []).filter(g => C.dayOf(g.kickoff) > (focusDay || etDay()));
    const games = focusGames.filter(g => matches(...Object.values(g.teams).flatMap(t => [t.name,t.displayName,t.abbreviation]))).map(g => nbaGameCard(g)).join('');
    const trends = (data.trends || []).filter(r => matches(r.name,r.statName)).map(r => `<article class="card" style="margin-top:12px"><p class="eyebrow">${esc(r.window)} · ${esc(r.season-1)}–${esc(String(r.season).slice(-2))}</p><h3>${esc(r.name)} · ${esc(r.statName)}</h3><p>${esc(r.average)} average across ${esc(r.games)} recorded games</p><p class="small muted" style="overflow-wrap:anywhere">Game log: ${esc(r.values.join(' · '))}</p><p class="tiny muted">${esc(r.dates[0])} through ${esc(r.dates.at(-1))}. Recorded appearances only.</p></article>`).join('');
    const prep = (data.prep || []).map(r => `<div class="receipt"><div><b>${esc(r.name)} over ${esc(r.line)} ${esc(r.statName || r.stat)}</b><span>${esc(r.hits)} of ${esc(r.games)} · ${esc(oddsText(r.over))} ${esc(bookLabel(r.book))} · Research</span></div></div>`).join('');
    const ready = data.readiness;
    const propAvailability = data.playerProps?.availabilityAt ? `<p class="small muted">Player availability checked ${esc(whenShort(data.playerProps.availabilityAt))}. Recheck before playing; these are research baselines.</p>` : '';
    const readiness = ready ? `<details class="more-box"><summary>NBA picks · model research</summary><p class="small">${esc(ready.cleanCaptureDays)}/${esc(ready.cleanCaptureDaysRequired)} clean capture days · ${esc(ready.paperGraded)}/${esc(ready.paperGradesRequired)} paper grades</p><p class="small muted">Saved pregame forecasts and later outcomes are tracked separately from posted picks. Player approval is checked separately for points, rebounds and assists.</p></details>` : '';
    const live = opts.embedded || opts.game ? '' : await views.gamesLive({day:etDay()});
    const playerProps = (data.playerProps?.rows || []).filter(r => (!opts.game || String(r.eventId) === String(opts.game.providerId)) && matches(r.name,r.teamName,r.statName) && (opts.game || !focusDay || C.dayOf(r.kickoff) === focusDay) && Date.now() < Date.parse(r.kickoff) && Date.now()-Date.parse(r.sourceAt) >= 0 && Date.now()-Date.parse(r.sourceAt) <= 14400000).map(r => `<article class="card" style="margin-top:12px;min-width:0;overflow-wrap:anywhere">
      <p class="eyebrow">${esc(r.teamName)} · ${esc(whenShort(r.kickoff))}${r.favorite ? ' · FAVORITE PROP · RESEARCH' : ''}</p>${String(r.photo || '').startsWith('https://a.espncdn.com/') ? `<img src="${esc(r.photo)}" alt="" loading="lazy" style="float:right;width:48px;height:48px;object-fit:cover;border-radius:50%;margin:0 0 8px 8px">` : ''}<h3><a href="#player/NBA/${esc(r.athleteId)}?stat=${esc(r.stat)}">${esc(r.name)} · ${esc(r.statName)}</a></h3>
      <p>Book line ${esc(r.line)} · over ${esc(oddsText(r.over))} / under ${esc(oddsText(r.under))} · ${esc(bookLabel(r.book))}</p>
      ${r.currentRole?.games ? `<p class="small"><b>This season’s workload:</b> ${r.currentRole.minutes.map(m => esc(m)).join(' / ')} minutes in the last ${esc(r.currentRole.games)} recorded game${r.currentRole.games === 1 ? '' : 's'}${Number.isInteger(r.currentRole.starts) ? ` · ${esc(r.currentRole.starts)} start${r.currentRole.starts === 1 ? '' : 's'}` : ''}.</p><p class="tiny muted">${String(r.currentRole.source || '').startsWith('https://') ? `<a href="${esc(r.currentRole.source)}" target="_blank" rel="noopener">Latest game ${esc(whenShort(r.currentRole.asOf))}</a>` : esc(whenShort(r.currentRole.asOf))}. Observed workload, not tonight’s confirmed minutes.</p>` : '<p class="small muted">No current-season workload recorded yet.</p>'}
      ${(r.opportunityContext || []).filter(c => c.analysisOnly === true && c.admissionReady === false && ['passing','rebounding'].includes(c.kind) && isNum(c.season?.games) && isNum(c.recent?.games)).map(c => {
        const key = c.kind === 'passing' ? 'potentialAssists' : 'reboundChances';
        const label = c.kind === 'passing' ? 'potential assists' : 'rebound chances';
        const base = c.season.metrics?.[key], recent = c.recent.metrics?.[key];
        if (!isNum(base) || !isNum(recent)) return '';
        return `<div class="small" style="margin-top:8px"><b>Observed opportunities:</b> ${esc(recent)} ${label} per game across ${esc(c.recent.games)} recent tracked games · season ${esc(base)} across ${esc(c.season.games)} tracked games.<p class="tiny muted">Checked ${esc(whenShort(c.observedAt))}. Recent games overlap the season sample. Opportunity counts are not a projection or chance to cash.</p>${(c.warnings || []).some(w => String(w).includes('definitions/coverage')) ? '<p class="tiny muted">Assist definitions or tracking coverage differ; no conversion rate calculated.</p>' : ''}</div>`;
      }).join('')}
      ${r.roleReview ? `<div class="small" style="margin-top:8px"><b>Tonight’s role: ${esc(r.roleReview.headline)}</b><p>${esc(r.roleReview.explanation)}</p><p class="tiny muted">Reviewed ${esc(whenShort(r.roleReview.checkedAt))} · ${r.roleReview.sources.map(s => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a>`).join(' · ')}</p></div>` : ''}
      ${r.projection ? `<p style="margin-top:8px"><b>${r.projection.minutesBasis ? 'News-aware estimate' : 'Historical baseline'}: ${esc(r.projection.value)}</b> · ${esc(r.projection.minutes)} ${r.projection.minutesBasis === 'analyst-estimate' ? 'estimated' : r.projection.minutesBasis ? 'reported' : 'baseline'} minutes</p>
      ${r.projection.minutesBasis ? `<p class="small muted">Old baseline: ${esc(r.projection.baselineValue)} at ${esc(r.projection.baselineMinutes)} minutes. ${r.projection.minutesBasis === 'analyst-estimate' ? 'My minutes estimate, not a coach-announced limit.' : 'Minutes based on the linked report.'} The scoring/rebounding rate still comes from the history below.</p>` : '<p class="small muted">Historical minutes and production, not a confirmed workload for tonight.</p>'}
      <p class="small">${esc(r.side)} ${esc(r.line)} · my number is ${esc(Math.abs(r.gap))} ${r.gap > 0 ? 'above' : 'below'} the line.</p>
      <p class="small muted">${esc(r.projection.window)} · ${esc(r.projection.season-1)}–${esc(String(r.projection.season).slice(-2))} · ${esc(r.projection.sample)} full-role games. Historical scaled range ${esc(r.projection.low)}–${esc(r.projection.high)}, not a prediction interval.</p>
      <p class="small">Exact-line ${esc(r.side)} hits: last 5 ${esc(r.last5.hits)}/${esc(r.last5.games)} · last 10 ${esc(r.last10.hits)}/${esc(r.last10.games)} · recorded season ${esc(r.seasonHistory.hits)}/${esc(r.seasonHistory.games)}</p>
      <p class="small">${esc(r.projection.minutes)} ${r.projection.minutesBasis ? 'reviewed' : 'baseline'} minutes × ${esc(r.projection.rate)} ${esc(r.statName)} per minute from ${esc(r.projection.sample)} full-role games.</p>` : `<p class="small" style="margin-top:8px">${esc(r.hold || 'Projection unavailable')}</p>`}
      ${C.nbaTicketLines && ticketButton ? `<div class="btn-row" style="margin-top:10px">${C.nbaTicketLines([r]).filter(l => l.state === 'open').map(l => ticketButton(l.id, l.title, l.direction)).join('')}<a class="btn small" href="#ticket">Compare my ticket →</a></div><p class="tiny muted">Personal draft only; no validated NBA EV estimate.</p>` : ''}
      <p><a href="#player/NBA/${esc(r.athleteId)}?stat=${esc(r.stat)}">Last 5, Last 10 & full player chart →</a></p><p class="tiny muted">Prices seen ${esc(whenShort(r.sourceAt))}${r.rosterAt ? ` · Roster checked ${esc(whenShort(r.rosterAt))}` : ''} · <a href="https://sharpapi.io">SharpAPI</a> / ESPN game logs</p></article>`);
    if (opts.game) return `${nbaGameCard(opts.game, false)}<section class="section"><h2>Player projections vs lines</h2>
      ${propAvailability}${playerProps.join('') || '<p>No fresh player prices for this matchup.</p>'}</section>`;
    const trial = nbaTrialSection(data, readiness);
    const brief = data.morningBrief;
    const morning = !opts.research && !opts.embedded && brief?.league === 'NBA' && !(data.trial?.plays || []).some(p => !p.result)
      && C.dayOf(brief.kickoff) === etDay() && Date.parse(brief.kickoff) > Date.now()
      && Date.now() - Date.parse(brief.observedAt) >= 0 && Date.now() - Date.parse(brief.observedAt) <= 4 * 3600000
      ? `<section class="kt-page-sec"><h2>Strongest morning lean</h2><p class="small" style="white-space:pre-line;overflow-wrap:anywhere">${esc(brief.text)}</p><p class="tiny muted">Checked ${esc(whenShort(brief.capturedAt))}</p></section>` : '';
    return `${opts.embedded ? '<section class="kt-page-sec" id="research-nba"><h2>NBA research</h2><p class="small muted">Separate historical samples and research baselines, not ranked against football’s price-check scores.</p>' : head(opts.research ? 'NBA Research' : 'NBA Today', opts.research ? 'NBA projections, props & trends' : data.heading || 'NBA Today')}<p class="small">${focusDay === etDay() ? 'Today’s NBA' : focusDay ? `Next NBA slate · ${esc(dayLabel(focusGames[0].kickoff))}` : 'NBA'} · ${esc(focusGames.length)} game${focusGames.length === 1 ? '' : 's'}. ${opts.research ? 'Research only; posted plays are on NBA Today.' : 'Posted plays first, then matchups and player lines.'}</p>${opts.embedded ? '<p><a href="#research/lines?sport=NBA">Full NBA research ›</a></p>' : opts.research ? '<p><a href="#today?sport=NBA">NBA Today & posted plays ›</a></p>'+readiness : trial}
      ${morning}${!data.scheduleFresh ? '<p class="small muted">Schedule update unavailable. These are the last stored games.</p>' : ''}
      ${showGames ? `<section class="kt-page-sec"><h2>Matchups & projections</h2><p class="small muted">Research projections · compare my totals with the book below.</p>${nbaProjectionContext(focusGames)}<div class="projs">${games || '<p class="small muted">No NBA matchups match this view.</p>'}</div></section>` : ''}
      ${showProps ? `<section class="kt-page-sec"><h2>Player projections vs lines</h2><p class="small muted">${esc(data.playerProps?.note || 'Research baselines with exact-line history and current book prices.')}</p>${propAvailability}${playerProps.length ? playerProps.slice(0,3).join('') : '<p class="small muted">No fresh, verified player prices match this view. Stale prices are hidden.</p>'}${playerProps.length > 3 ? `<details class="more-box"><summary>All ${playerProps.length} fresh prop comparisons</summary>${playerProps.slice(3).join('')}</details>` : ''}${(data.playerProps?.holds || []).length ? `<details class="more-box"><summary>Why some players have no projection</summary>${data.playerProps.holds.filter(r => matches(r.name)).map(r => `<p class="small"><b>${esc(r.name)}</b> · ${esc(r.reason)}</p>`).join('')}</details>` : ''}</section>` : ''}
      ${showTrends ? `<section class="kt-page-sec"><h2>Team trends</h2>${(data.teamTrends || []).filter(r => matches(r.team.name,r.team.displayName,r.team.abbreviation) && (!teamsToday.size || teamsToday.has(String(r.team.id)))).map(r => `<article class="card" style="margin-top:12px"><p class="eyebrow">${esc(r.window)} · REGULAR SEASON · ${esc(r.season-1)}–${esc(String(r.season).slice(-2))}</p><h3>${teamMark(r.team,'sm','NBA')} ${esc(r.team.name || r.team.displayName || r.team.abbreviation)}</h3><p>${esc(r.points)} scored · ${esc(r.allowed)} allowed per game</p><p class="small muted">Last ${esc(r.games)} recorded games · ${esc(whenShort(r.first))} through ${esc(whenShort(r.last))}. Team history, not a player projection.</p></article>`).join('') || '<p class="small muted">No team trends match this view.</p>'}</section>` : ''}
      ${opts.embedded ? `${mode === 'news' ? `${propAvailability}<p class="small muted">NBA availability is shown with the player research; no separate NBA news feed is published here.</p>` : ''}${showTrends || mode === 'players' ? `<details class="more-box"><summary>Recorded NBA player history</summary>${trends || '<p class="small muted">No recorded player history matches this view.</p>'}</details>` : ''}</section>` : `
      ${(data.editorial || []).length ? `<section class="kt-page-sec"><h2>NBA research cards</h2>${data.editorial.map(r => `<article class="card" style="margin-top:12px"><h3>${esc(r.title)} · ${esc(r.day)}</h3><p class="small" style="white-space:pre-line;overflow-wrap:anywhere">${esc(r.text)}</p><a href="${esc(r.card)}">Open research graphic ↗</a></article>`).join('')}</section>` : ''}
      <details class="more-box"><summary>More recorded player history</summary>${trends || '<p class="small muted">Player game logs are being collected. Current-season trends need at least three recorded games.</p>'}</details>
      ${laterGames.length ? `<details class="more-box"><summary>Upcoming NBA · ${laterGames.length} games after this slate</summary><div class="projs">${laterGames.map(g => nbaGameCard(g)).join('')}</div></details>` : ''}
      <section class="kt-page-sec"><h2>Prep List <span class="badge research">Research</span></h2>${prep || `<p class="small muted">${esc(data.prepNote)}</p>`}</section>
      <section class="kt-page-sec">${live}</section>`}`;
  };
  return views;
});
