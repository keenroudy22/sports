'use strict';
/* Lazily loaded Games pages: the slate (with the college navigator), live scores, finals, the game page and the team page.
   app.js supplies the shared, already-tested view helpers; this bundle stays out of the first-load shell. */
(function (root, factory) {
  root.KRGames = factory;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (ctx) {
  const { C, L, state, esc, head, section, empty, seg, segLinks, FOOTBALL, LEAGUE_NAME, teamDirectory,
    maybe, get, indexGames, withLive, defenseRows, projCard, teamMark, headshot, whenShort, dayLabel,
    bookLabel, ago, oddsText, isNum, inLeague, setLeague, liveStamp, liveFor, LIVE, favSpread, quoteAge,
    ticket, ticketButton, etDay } = ctx;
  const views = {};
  /* Navigator, "why" and badge styles arrive with this bundle, so the first-load shell stays inside its budget. */
  const GAMES_CSS = ".kt-worth-strip { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(196px, 1fr); gap: 10px; margin: 10px 0 6px; padding-bottom: 6px; }\n.kt-worth-card { display: grid; gap: 4px; align-content: start; padding: 10px 12px; background: var(--felt); border: 1px solid var(--line); border-radius: var(--radius); color: var(--chalk); min-width: 0; }\n.kt-worth-card:hover { text-decoration: none; border-color: var(--line-strong); }\n.kt-worth-card .wc-t { font: 700 15px/1.1 var(--font-display); letter-spacing: .03em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n.kt-worth-card b { font: 500 14px/1.3 var(--font-body); color: var(--kookd); }\n.kt-worth-card small { font-size: 13px; color: var(--dim); }\n"
    + ".nav-bar { display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: center; margin: 0 0 12px; }\n.nav-bar .select { min-height: 38px; padding: 6px 10px; }\n"
    + ".today-game-list { display:grid; gap:8px; margin-top:10px; }\n.today-game-row { position:relative; display:grid; grid-template-columns:minmax(0,1fr) auto 16px; align-items:center; gap:10px; min-height:82px; padding:10px 12px; border:1px solid var(--line); border-radius:13px; background:linear-gradient(135deg,rgba(20,43,30,.95),rgba(8,22,15,.98)); color:var(--chalk); }\n.today-game-row:hover { border-color:var(--line-strong); text-decoration:none; }\n.today-game-row.is-live { border-color:rgba(32,199,116,.55); }\n.today-game-matchup { display:grid; grid-template-columns:minmax(0,1fr) 18px minmax(0,1fr); align-items:center; gap:5px; min-width:0; }\n.today-game-team { display:flex; align-items:center; gap:7px; min-width:0; }\n.today-game-team > span:last-child { display:grid; min-width:0; }\n.today-game-team b { overflow:hidden; font-size:14px; line-height:1.15; text-overflow:ellipsis; white-space:nowrap; }\n.today-game-team small { margin-top:2px; color:var(--dim); font-size:12px; }\n.today-game-at { color:var(--dim); font:700 12px/1 var(--font-display); text-align:center; text-transform:uppercase; }\n.today-game-read { display:grid; justify-items:end; min-width:98px; text-align:right; }\n.today-game-read small { color:var(--dim); font-size:12px; line-height:1.2; }\n.today-game-read b { margin-top:3px; font:700 21px/1 var(--font-display); }\n.today-game-read > span { margin-top:3px; color:var(--dim); font-size:12px; line-height:1.2; }\n.today-game-arrow { color:var(--kookd); font-size:24px; }\n@media(max-width:420px){.today-game-row{grid-template-columns:minmax(0,1fr) auto 12px;gap:6px;padding:9px}.today-game-matchup{grid-template-columns:minmax(0,1fr);gap:4px}.today-game-at{display:none}.today-game-team .tm{width:25px;height:25px}.today-game-team b{font-size:13px}.today-game-team small{display:none}.today-game-read{min-width:88px}}\n"
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
    `;
  if (typeof document !== 'undefined' && document.head && document.createElement && !(document.getElementById && document.getElementById('kr-games-css'))) {
    const style = document.createElement('style'); style.id = 'kr-games-css'; style.textContent = GAMES_CSS; document.head.appendChild(style);
  }
  /* ---------- the college slate navigator (owner, Oct 7, item 30): research grouping, never a play ---------- */
  const WINDOW_WORD = { noon: 'Noon', afternoon: '3:30', night: 'Night' };
  const navCard = (g, opts = {}) => {
    if (g.cbbSource) return cbbGameCard(g.cbbSource);
    if (g.nbaSource) return nbaGameCard(g.nbaSource);
    const { badge, extra } = C.matchupCardExtras(g, { quoteAge, favSpread });
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
      <div class="chip-scroll"><div class="kt-worth-strip">${top.map(g => `<a class="kt-worth-card" href="#game/${esc(g.id)}"><span class="wc-t">${esc(g.away.abbr)} at ${esc(g.home.abbr)}</span><b>${esc(g.look || g.plainGap || 'Take a look')}</b><small>${esc([C.TIER_WORD[g.tier], whenShort(g.kickoff).split(', ').pop(), !(g.bettableParts || {}).official ? 'Research lean · not a bet' : ''].filter(Boolean).join(' · '))}</small></a>`).join('')}</div></div></section>`;
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
      && (play.stat || play.market) === stat && play.line === row.line && bookLabel(play.book) === bookLabel(row.book)
      && ['over', 'under'].includes(play.direction) && isNum(play.odds) && play.odds === row[play.direction]);
    const isFresh = row => {
      const age = now - Date.parse(row?.sourceAt);
      return pregame && age >= 0 && age <= 4 * 3600000;
    };
    const isLean = row => Boolean(row?.favorite && !row.hold && isFresh(row));
    const matchupDay = Number.isFinite(tip) ? C.dayOf(game.kickoff) : '';
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
        || (recentBoxCutoff && player.entry?.[5] >= recentBoxCutoff && player.entry?.[5] <= matchupDay))
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
      const price = line == null ? '' : [isNum(row.over) || isNum(row.under) ? `O ${isNum(row.over) ? oddsText(row.over) : '—'} / U ${isNum(row.under) ? oddsText(row.under) : '—'}` : '', row.book ? bookLabel(row.book) : ''].filter(Boolean).join(' · ');
      const liked = !official && !held && isLean(row);
      const body = `<span class="prop-vs"><span><span class="prop-vs-label">${line != null && !isFresh(row) ? 'Earlier line' : 'Book'}</span><b${line == null ? ' aria-label="Book line unavailable"' : ''}>${line == null ? '—' : esc(line)}</b></span><span class="prop-vs-mark">vs</span><span><span class="prop-vs-label">Kook’n</span><b>${isNum(projection) ? esc(C.fixed(projection)) : 'Held'}</b></span></span>${gap == null ? '' : `<span class="prop-gap">Projection gap <b>${gap > 0 ? '+' : ''}${esc(C.fixed(gap))}</b></span>`}${price ? `<span class="prop-price">${esc(price)}</span>` : ''}${range ? `<span class="prop-range">Kook’n range ${esc(range)}</span>` : ''}${recent ? `<span class="prop-recent">${esc(recent)}</span>` : ''}${row?.sourceAt ? `<span class="prop-checked">${isFresh(row) ? 'Checked' : 'Earlier quote · checked'} ${esc(ago(row.sourceAt))}</span>` : ''}${official ? '<span class="pick-tag">Official pick</span>' : liked ? '<span class="lean-tag">Research lean</span>' : ''}`;
      return href ? `<a class="prop-cell${liked ? ' liked' : ''}${official ? ' official' : ''}" href="${href}">${body}</a>` : `<span class="prop-cell">${body}</span>`;
    };
    const table = (players, stats) => `<div class="table-wrap"><table class="t prop-compare"><thead><tr><th>Player · role</th>${stats.map(([,label]) => `<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${players.map(player => {
      const rows = [...player.stats.values()], status = basketballStatus(rows), role = rows.find(row => row.currentRole)?.currentRole, summary = player.entry?.[7];
      const projectedMinutes = !pregame || rows.some(C.basketballAvailabilityHold) ? null
        : rows.find(row => !row.hold && isNum(row.projection?.minutes))?.projection?.minutes ?? summary?.minutes;
      const minuteList = role?.minutes?.length ? role.minutes : summary?.recentMinutes || player.entry?.[8] || [];
      return `<tr><th class="prop-player"><span class="prop-player-head"><a href="${player.id ? `#player/${league}/${esc(player.id)}?stat=pts` : '#research/players'}">${esc(player.name)}</a><span class="prop-pos">${esc(player.pos || 'Position unavailable')}</span>${status ? `<span class="badge ${status.warn ? 'warn' : 'research'}">${esc(status.word)}</span>` : ''}</span><span class="prop-min"><b>${isNum(projectedMinutes) ? `Kook’n minutes ${esc(C.fixed(projectedMinutes))}` : 'Minutes projection held'}</b>${minuteList.length ? `<span>Recent ${minuteList.slice(-3).map(value => esc(C.fixed(value,0))).join(' · ')}</span>` : ''}</span></th>${stats.map(([stat,label]) => `<td data-stat="${esc(label)}">${playerLine(player,stat)}</td>`).join('')}</tr>`;
    }).join('')}</tbody></table></div>`;
    const blocks = teams.map(team => {
      const players = teamPlayers(team);
      const featured = players.slice(0,5), depth = players.slice(5);
      const extraPlayers = players.filter(player => BBALL_EXTRA.some(([stat]) => player.stats.has(stat) || isNum(player.entry?.[7]?.values?.[stat])));
      return `<details class="more-box prop-team" open><summary>${teamMark(team,'sm',league)} ${esc(team.name || team.abbreviation)} · ${players.length} players</summary>${players.length ? `<p class="prop-team-note">Priced lines, research leans and highest-minute roles first.</p>${table(featured,BBALL_PRIMARY)}${depth.length ? `<details class="more-box prop-depth-more"><summary>Show ${depth.length} more ${esc(team.abbreviation || '')} player${depth.length === 1 ? '' : 's'}</summary>${table(depth,BBALL_PRIMARY)}</details>` : ''}` : '<p class="small muted">No recent player logs, projections or prices are available for this team.</p>'}${extraPlayers.length ? `<details class="more-box prop-market-more"><summary>Threes & combo markets</summary>${table(extraPlayers,BBALL_EXTRA)}</details>` : ''}</details>`;
    }).join('');
    const checked = gameRows.map(row => row.sourceAt).filter(Boolean).sort().pop();
    return section('Player props & projections', `<p class="small"><b>Book line vs Kook’n projection.</b> Tap a stat to open its recent-game chart at that exact line.</p><div class="prop-legend"><span>Gap = Kook’n minus the book</span><span class="lean-key"><b>Green</b> research lean · not a pick</span></div><div class="prop-teams">${blocks}</div>`, '', `${league === 'NBA' ? 'A dash under Book means no captured line.' : 'Official box scores power the CBB baseline. A dash under Book means no captured line.'} ${checked ? `Latest price check ${esc(ago(checked))}.` : 'No verified player price is stored for this matchup.'}`);
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
    const browsing = Boolean(String(state.games.q || '').trim());
    const shown = opts.preview && !browsing ? rows.slice(0, 6) : rows;
    const slateLabel = shown.length < rows.length ? `View all ${rows.length} matchups` : 'Full college hoops slate';
    const tools = opts.preview ? `<div class="btn-row"><a class="btn small" href="#games/upcoming?sport=CBB">${slateLabel}</a><a class="btn small" href="#edges?sport=CBB&amp;type=games">Compare spreads</a><a class="btn small" href="#research/players?sport=CBB">Player charts</a></div>` : '';
    return head('College basketball', 'CBB projections & stats', `${rows.length} game${rows.length === 1 ? '' : 's'} · ${projected.length} projected · ${availableCount} with a fresh spread`)
      + `${opts.gamesPage ? gameTabs('upcoming') : views.cbbPicks(data, true)}
        ${tools}
        ${!data.scheduleFresh ? '<p>Schedule update needed. Projections are held.</p>' : ''}
        ${window.html}
        ${rows.length ? `<ul class="cbb-slate" aria-label="College basketball matchups">${shown.map(cbbSlateRow).join('')}</ul>` : '<p>No upcoming games match this view.</p>'}
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
      const matchup = await get(`app/games/${route.id}.json`).catch(() => null);
      let game, research, playerIndex, rows, picks;
      if (matchup?.game?.id === route.id && Array.isArray(matchup.players) && Array.isArray(matchup.picks)
          && Array.isArray(matchup.matchupPropEvents)) {
        ({ game, picks } = matchup);
        research = matchup.research ? game : null;
        playerIndex = matchup;
        rows = league === 'NBA' ? await C.nbaMatchupProps(get, matchup, route.id) : { rows: [] };
      } else {
        // Keep the matchup available during mixed-version deploys and for older saved links.
        const dataRequest = get(`app/${league.toLowerCase()}.json`).catch(() => null);
        const [data, index, props, records] = await Promise.all([
          dataRequest,
          get(`app/players/${league}.json`).catch(() => ({players:[]})),
          league === 'NBA' ? dataRequest.then(data => C.nbaMatchupProps(get, data, route.id)) : {rows:[]},
          league === 'NBA' ? ctx.allPicks().catch(() => []) : []]);
        research = data?.games?.find(g => g.id === route.id);
        game = research || (await maybe('sports.json'))?.leagues?.[league]?.games?.find(g => g.id === route.id);
        playerIndex = index;
        rows = props;
        picks = records;
      }
      if (!game) return head(league, 'Matchup unavailable', 'This game is outside the stored schedule.', back);
      const title = `${game.teams.away.name} at ${game.teams.home.name}`;
      const top = head(league, title, esc(whenShort(game.kickoff)), back);
      const card = research && league === 'NBA' ? nbaGameCard(research, false)
        : research?.projection ? cbbGameCard(research, false) : basketballScoreCard(game, league);
      return top + card + basketballMatchupProps(league, game, picks, playerIndex, rows);
    }
    return head('', 'Game page not available', 'This matchup is outside the stored basketball schedule.', back);
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
  views.basketballEdges = async (league, { type, q, preview = false, limit = 40 } = {}) => {
    const [schedule, props] = await Promise.all([
      maybe(`app/${league.toLowerCase()}.json`),
      league === 'NBA' && type !== 'games' ? maybe('app/nba-props.json') : null,
    ]);
    const now = Date.now();
    const matches = (...fields) => !q || C.researchMatches(q, ...fields);
    const upcoming = (kickoff, observedAt) => Date.parse(kickoff) > now
      && now - Date.parse(observedAt) >= 0 && now - Date.parse(observedAt) <= 14400000;
    const validOdds = value => isNum(value) && Math.abs(value) >= 100;
    const games = (schedule?.games || []).filter(g => !g.status || g.status === 'scheduled');
    const teams = g => [g.teams.away, g.teams.home].map(t => t.abbreviation || t.name);
    const title = g => teams(g).join(' at ');
    const comparisons = [];
    for (const g of games) {
      if (type === 'props' || !g.projection) continue;
      const [away,home] = teams(g), p = g.projection;
      const margin = p.margin ?? (isNum(p.home) && isNum(p.away) ? p.home-p.away : null);
      const spread = league === 'NBA' ? g.spreadQuote : freshCbbSpread(g, now);
      const observedAt = spread?.observedAt || spread?.retrievedAt;
      if (spread?.book && upcoming(g.kickoff, observedAt) && isNum(margin) && isNum(spread.homeLine)
          && validOdds(spread.homeOdds ?? spread.home) && validOdds(spread.awayOdds ?? spread.away)
          && matches(title(g), ...Object.values(g.teams).map(t => t.name), league, 'spread')) {
        const gap = margin + spread.homeLine;
        const homePrice = oddsText(spread.homeOdds ?? spread.home), awayPrice = oddsText(spread.awayOdds ?? spread.away);
        const price = spread.homeLine === 0 ? `${home} ${homePrice} / ${away} ${awayPrice}` : spread.homeLine < 0 ? homePrice : awayPrice;
        comparisons.push({ name:title(g), market:'Spread', model:C.modelSpread(home,away,margin),
          line:C.modelSpread(home,away,-spread.homeLine), price, book:spread.book, observedAt,
          gap:Math.abs(gap), difference:Math.abs(gap)<.05 ? 'Same line' : `${C.fixed(Math.abs(gap))} toward ${gap>0 ? home : away}`, href:`#game/${g.id}` });
      }
      const total = league === 'NBA' && g.totalQuote;
      if (total?.book && upcoming(g.kickoff, total.retrievedAt) && isNum(total.line) && isNum(p.total)
          && validOdds(total.over) && validOdds(total.under)
          && matches(title(g), ...Object.values(g.teams).map(t => t.name), league, 'total')) {
        const gap = p.total-total.line;
        comparisons.push({ name:title(g), market:'Total', model:C.fixed(p.total), line:total.line,
          price:`O ${oddsText(total.over)} / U ${oddsText(total.under)}`, book:total.book, observedAt:total.retrievedAt,
          gap:Math.abs(gap), difference:`${gap>0 ? '+' : ''}${C.fixed(gap)}`, href:`#game/${g.id}` });
      }
    }
    const gameById = new Map(games.map(g => [String(g.providerId || g.id?.replace(/^NBA-/, '')), g]));
    // Search and the dedicated NBA tab share the same complete data as the charts.
    const fullQuotes = league === 'NBA' && type !== 'games' && (!preview || q)
      ? await C.nbaUpcomingProps(get, schedule, now) : null;
    const quotes = fullQuotes ?? props?.rows ?? [];
    const playerRows = [];
    for (const row of quotes) {
      const game = gameById.get(String(row.eventId)), dir = row.side;
      if (!game || !row.athleteId || !row.stat || !row.book || !['over','under'].includes(dir) || row.hold
          || !isNum(row.line) || !isNum(row.projection?.value) || !validOdds(row[dir])
          || Date.parse(game.kickoff) !== Date.parse(row.kickoff) || !upcoming(game.kickoff, row.sourceAt)
          || !matches(row.name,row.teamName,row.teamAbbr,row.statName,title(game),league)) continue;
      const gap = row.projection.value-row.line;
      playerRows.push({ name:row.name, market:row.statName || row.stat, model:C.fixed(row.projection.value), line:row.line,
        price:`${dir==='under' ? 'U' : 'O'} ${oddsText(row[dir])}`, book:row.book, observedAt:row.sourceAt,
        gap:Math.abs(gap), difference:`${gap>0 ? '+' : ''}${C.fixed(gap)}`, liked:row.favorite === true, history:C.nbaPropHistory(row, dir),
        href:C.playerLineHref({league,athleteId:row.athleteId,stat:row.stat,line:row.line,direction:dir,book:bookLabel(row.book),gameId:game.id}) });
    }
    const list = rows => rows.length ? `<ul class="edge-comparisons">${rows.map(r => `<li><a class="edge-comparison${r.liked ? ' is-lean' : ''}" href="${esc(r.href)}">
      <span><b>${esc(r.name)}</b><small>${esc(r.market)}${r.liked ? ' · Research lean' : ''}</small></span>
      <span><small>Kook’n</small><b>${esc(r.model)}</b></span>
      <span><small>Book · ${esc(bookLabel(r.book))}</small><b>${esc(r.line)} · ${esc(r.price)}</b><small>Checked ${esc(ago(r.observedAt))}</small></span>
      <span><small>Projection gap</small><b>${esc(r.difference)}</b>${r.history ? `<small>History · ${esc(r.history)}</small>` : ''}</span></a></li>`).join('')}</ul>` : '';
    const group = (heading, rows) => {
      if (!rows.length) return '';
      const shown = preview ? 3 : limit;
      return `<h3>${heading} · ${rows.length}</h3>${list(rows.slice(0,shown))}${rows.length > shown ? preview
        ? `<p><a href="#edges?sport=${league}&amp;type=${heading === 'Player props' ? 'props' : 'games'}${q ? `&amp;q=${esc(encodeURIComponent(q))}` : ''}">View all ${rows.length} ${heading.toLowerCase()} ›</a></p>`
        : `<p><button class="btn small" type="button" data-more-rows>Show ${Math.min(40, rows.length-shown)} more ${heading.toLowerCase()}</button></p>` : ''}`;
    };
    const matchups = group('Matchup lines', comparisons.sort((a,b) => b.gap-a.gap));
    const players = group('Player props', playerRows.sort((a,b) => Number(b.liked)-Number(a.liked) || b.gap-a.gap));
    const missing = type !== 'games' && !players ? league === 'CBB' ? 'CBB player prices are unavailable.' : 'No verified NBA player prices and projections match this view.' : '';
    return section(league === 'NBA' ? 'NBA' : 'College Hoops', `${matchups}${players}
      ${!matchups && type !== 'props' ? '<p class="small muted">No fresh matchup comparisons match this view.</p>' : ''}
      ${missing ? `<p class="small muted">${missing} <a href="#research/players?sport=${league}">Browse player charts ›</a></p>` : ''}
      ${(!schedule || league === 'NBA' && type !== 'games' && !props) ? '<p class="small muted">Some comparison data is unavailable. Refresh to retry.</p>' : ''}`,
      '', 'Research · projection gaps in stat units.');
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
    const playerProps = (data.playerProps?.rows || []).filter(r => (!opts.game || String(r.eventId) === String(opts.game.providerId)) && matches(r.name,r.teamName,r.statName) && (opts.game || !focusDay || C.dayOf(r.kickoff) === focusDay) && Date.now() < Date.parse(r.kickoff) && Date.now()-Date.parse(r.sourceAt) >= 0 && Date.now()-Date.parse(r.sourceAt) <= 14400000).map(r => {
      const chartHref = C.playerLineHref({league:'NBA',athleteId:r.athleteId,stat:r.stat,line:r.line,direction:r.side || 'over',book:bookLabel(r.book),gameId:r.eventId ? `NBA-${r.eventId}` : null});
      return `<article class="card" style="margin-top:12px;min-width:0;overflow-wrap:anywhere">
      <p class="eyebrow">${esc(r.teamName)} · ${esc(whenShort(r.kickoff))}${r.favorite ? ' · FAVORITE PROP · RESEARCH' : ''}</p>${String(r.photo || '').startsWith('https://a.espncdn.com/') ? `<img src="${esc(r.photo)}" alt="" loading="lazy" style="float:right;width:48px;height:48px;object-fit:cover;border-radius:50%;margin:0 0 8px 8px">` : ''}<h3><a href="${esc(chartHref)}">${esc(r.name)} · ${esc(r.statName)}</a></h3>
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
      <p><a href="${esc(chartHref)}">Last 5, Last 10 & full player chart →</a></p><p class="tiny muted">Prices seen ${esc(whenShort(r.sourceAt))}${r.rosterAt ? ` · Roster checked ${esc(whenShort(r.rosterAt))}` : ''} · <a href="https://sharpapi.io">SharpAPI</a> / ESPN game logs</p></article>`; });
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
