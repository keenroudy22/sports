'use strict';
/* Lazily loaded Games pages: the slate (with the college navigator), live scores, finals, the game page and the team page.
   app.js supplies the shared, already-tested view helpers; this bundle stays out of the first-load shell. */
(function (root, factory) {
  root.KRGames = factory;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (ctx) {
  const { C, L, state, esc, head, section, empty, seg, segLinks, FOOTBALL, LEAGUE_NAME, teamDirectory, maybe, get, indexGames, withLive,
    defenseRows, defGames, defenseVerdict, projCard, teamMark, headshot, whenShort, dayLabel, bookLabel, ago, niceTitle, oddsText, isNum, inLeague,
    watchButton, setLeague, liveStamp, liveFor, LIVE, gapScore, STAT_WORD, favSpread, marketLabel, quoteAge, round1, fairAmerican, boardRow,
    matchupSignals, researchPrice, pctText, currentUpset, upsetRow, heavyFavorite, trendText, historyChart, ticket, etDay } = ctx;
  const views = {};
  /* Navigator, "why" and badge styles arrive with this bundle, so the first-load shell stays inside its budget. */
  const GAMES_CSS = ".tier { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font: 700 12px/1 var(--font-display); letter-spacing: .08em; text-transform: uppercase; border: 1px solid var(--line-strong); color: var(--chalk); white-space: nowrap; }\n"
    + ".tier::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--dim); }\n.tier.competitive::before { background: var(--kookd); } .tier.lean::before { background: var(--chalk); } .tier.mismatch::before { background: var(--dim); } .tier.blowout::before { background: var(--burnt); }\n"
    + ".pc-plain { font: 500 14px/1.4 var(--font-body); color: var(--chalk); border-top: 1px solid var(--line); padding-top: 8px; }\n"
    + ".pc-bet { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px 10px; font: 500 14px/1.3 var(--font-body); color: var(--dim); }\n.pc-bet b { display: block; font: 700 12px/1 var(--font-display); letter-spacing: .1em; text-transform: uppercase; color: var(--dim); margin-bottom: 3px; }\n.pc-bet .v { color: var(--chalk); font-weight: 600; }\n.pc-bet .flag { display: block; color: var(--burnt-text); font-weight: 600; }\n.pc-bet .age, .pc-bet-h { grid-column: 1 / -1; font-size: 13px; }\n.pc-bet-h { font: 700 12px/1 var(--font-display); letter-spacing: .1em; text-transform: uppercase; color: var(--kookd); }\n"
    + ".pc-why { font: 500 14px/1.45 var(--font-body); color: var(--chalk); border-top: 1px dashed rgba(169, 192, 179, .28); padding-top: 8px; }\n.pc-why a { white-space: nowrap; font-weight: 700; display: inline-flex; align-items: center; min-height: var(--tap); }\n.pc-why.muted { color: var(--dim); }\n"
    + ".kt-worth-strip { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(196px, 1fr); gap: 10px; margin: 10px 0 6px; padding-bottom: 6px; }\n.kt-worth-card { display: grid; gap: 4px; align-content: start; padding: 10px 12px; background: var(--felt); border: 1px solid var(--line); border-radius: var(--radius); color: var(--chalk); min-width: 0; }\n.kt-worth-card:hover { text-decoration: none; border-color: var(--line-strong); }\n.kt-worth-card .wc-t { font: 700 15px/1.1 var(--font-display); letter-spacing: .03em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n.kt-worth-card b { font: 500 14px/1.3 var(--font-body); color: var(--kookd); }\n.kt-worth-card small { font-size: 13px; color: var(--dim); }\n"
    + ".nav-bar { display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: center; margin: 0 0 12px; }\n.nav-bar .select { min-height: 38px; padding: 6px 10px; }\n"
    + ".kt-why .vs { grid-template-columns: auto 1fr 1fr auto; font-size: 15px; }\n.kt-why .vs .num { font-variant-numeric: tabular-nums; }\n.kt-drivers { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }\n.kt-drivers li { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 8px; font: 500 15px/1.45 var(--font-body); }\n.kt-drivers li::before { content: '↑'; color: var(--kookd); font-weight: 700; text-align: center; }\n.kt-drivers li.against::before { content: '↓'; color: var(--burnt-text); }\n.kt-drivers li small { display: inline; color: var(--dim); font-size: 13px; }\n.kt-drivers li.mk { display: block; font: 700 12px/1 var(--font-display); letter-spacing: .12em; text-transform: uppercase; color: var(--dim); margin: 10px 0 2px; }\n.kt-drivers li.mk::before { content: none; }\n.kt-why:focus { outline: none; }\n.kt-why, .section[id] { scroll-margin-top: 64px; }\n"
    + ".kt-why-note { margin-top: 12px; padding: 10px 12px; border-left: 3px solid var(--burnt); background: var(--burnt-soft); font: 500 14px/1.4 var(--font-body); }\n.kt-why-foot { margin-top: 12px; font: 500 14px/1.45 var(--font-body); color: var(--dim); }\n"
    + "@media (max-width: 359px) { .pc-bet { grid-template-columns: 1fr 1fr; } }";
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
  const navCard = (g, opts = {}) => projCard(g, { ...cardExtras(g), ...opts });
  const byBettable = (a, b) => (Number(b.bettable) || 0) - (Number(a.bettable) || 0) || String(a.kickoff).localeCompare(String(b.kickoff)) || String(a.id).localeCompare(String(b.id));
  const worthStrip = list => {
    const top = list.filter(g => g.league === 'CFB' && !g.completed).slice().sort(byBettable).slice(0, 6);
    if (!top.length) return '';
    return `<section class="section" style="margin:8px 0 18px" aria-labelledby="worth-h"><div class="section-head"><h2 id="worth-h" style="white-space:nowrap">Worth your time</h2><span class="kt-kind">Research · the one thing to check</span></div>
      <div class="chip-scroll"><div class="kt-worth-strip">${top.map(g => `<a class="kt-worth-card" href="#game/${esc(g.id)}"><span class="wc-t">${esc(g.away.abbr)} at ${esc(g.home.abbr)}</span><b>${esc(g.look || g.plainGap || 'Take a look')}</b><small>${esc([TIER_WORD[g.tier], whenShort(g.kickoff).split(', ').pop()].filter(Boolean).join(' · '))}</small></a>`).join('')}</div></div></section>`;
  };
  views.games = async route => {
    const tab = route.tab || 'upcoming';
    if (route.league) setLeague(route.league);
    const tabs = `<div class="chip-scroll">${segLinks([['#games', 'Upcoming', 'upcoming'], ['#games/live', 'Live & scores', 'live'], ['#games/final', 'Finals', 'final']], tab)}</div>`;
    const top = `${head('Games', tab === 'live' ? 'Live and scores' : tab === 'final' ? 'Recent finals' : 'Upcoming games', tab === 'upcoming' ? "My projected score and win chance for every game, and how my number compares with the book. Off and Def are my team ranks; #1 is best. Research, not best bets." : tab === 'live' ? 'Every sport I track. Scores refresh about every minute while this page is open.' : 'How my projected scores compared with the finals.')}${tabs}`;
    if (tab === 'live') return top + await gamesLive();
    const today = await get('app/today.json');
    if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${empty('Football only for projections', `${esc(LEAGUE_NAME[state.league])} has live scores here, not projections yet. Some sports also run a paper trial. <a href="#games/live">See live scores</a> or <a href="#record/trials">the trial record</a>.`, 'research')}`;
    const merged = withLive((today.games || []).filter(inLeague));
    let games = merged.games;
    const q = state.games.q.trim().toLowerCase();
    if (q) games = games.filter(g => [g.home.abbr, g.home.name, g.away.abbr, g.away.name].some(v => String(v || '').toLowerCase().includes(q)));
    const search = `<div class="grow"><label class="sr" for="gq">Find a team</label><input id="gq" class="search" type="search" placeholder="Find a team" value="${esc(state.games.q)}" data-input="gq" autocomplete="off" maxlength="80"></div>`;
    const byDay = (list, title = null) => {
      const days = new Map();
      list.forEach(g => { const d = dayLabel(g.kickoff); if (!days.has(d)) days.set(d, []); days.get(d).push(g); });
      return [...days.entries()].map(([d, l]) => `<p class="eyebrow" style="margin:18px 0 10px">${esc(title ? `${title} · ${d}` : d)}</p><div class="projs">${l.map(g => navCard(g)).join('')}</div>`).join('');
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
    const filtered = !college ? list : list.filter(g => (nav.window === 'all' || g.window === nav.window) && (!nav.close || g.tier === 'competitive')
      && (chosenConf === 'all' || [(g.conference || {}).home, (g.conference || {}).away].includes(chosenConf)));
    const sort = college && state.games.sort !== 'kickoff' ? 'bettable' : 'kickoff';
    const controls = !college ? '' : `<div class="nav-bar" role="group" aria-label="College slate filters"><div class="chip-scroll">${seg('gnav', [['window=all', 'All'], ['window=noon', 'Noon'], ['window=afternoon', '3:30'], ['window=night', 'Night']], `window=${nav.window}`)}</div>
      <button type="button" class="chip" data-set="gnav:close=1" aria-pressed="${Boolean(nav.close)}">Close games only</button>
      ${confs.length > 1 ? `<label class="sr" for="gconf">Conference</label><select id="gconf" class="select" data-select="gconf"><option value="all"${chosenConf === 'all' ? ' selected' : ''}>All conferences</option>${confs.map(c => `<option value="${esc(c)}"${c === chosenConf ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select>` : ''}
      ${seg('gsort', [['bettable', 'Bettable'], ['kickoff', 'Kickoff']], sort)}</div>`;
    const stamp = liveStamp(merged.refreshed);
    if (!filtered.length) return `${top}${toolbar}${controls}${stamp}${empty('No game matches these filters', 'Try another window or conference, or turn off close games only.', 'games')}${nextBtn}`;
    const strip = college ? worthStrip(filtered) : '';
    if (sort === 'bettable') {
      const nfl = filtered.filter(g => g.league !== 'CFB'), cfb = filtered.filter(g => g.league === 'CFB').sort(byBettable);
      const shown = state.games.all ? cfb : cfb.slice(0, 24);
      return `${top}${toolbar}${controls}${strip}${stamp}${nfl.length ? byDay(nfl, 'NFL') : ''}
        <p class="eyebrow" style="margin:18px 0 10px">College · most bettable first</p><p class="small muted" style="margin:-6px 0 10px">Fresh two-sided lines, competitiveness, how far my number sits from the book and any best bet, upset watch or priced props. A high score is a reason to look, not a bet.</p>
        <div class="projs">${shown.map(g => navCard(g)).join('')}</div>
        ${cfb.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-all-games>Show all ${cfb.length} games</button></p>` : nextBtn}`;
    }
    return `${top}${toolbar}${controls}${strip}${stamp}${byDay(filtered)}${nextBtn}`;
  };
  const LIVE_WORD = { in_progress: 'Live', final: 'Final', scheduled: 'Scheduled', postponed: 'Postponed', delayed: 'Delayed', suspended: 'Suspended', cancelled: 'Cancelled', canceled: 'Cancelled' };
  const gamesLive = async (opts = {}) => {
    const [sports, todayRaw, history] = await Promise.all([maybe('sports.json'), maybe('app/today.json'), maybe('market-lab.json')]);
    const today = todayRaw || {};
    const day = opts.day || (state.games.day && [etDay(-1), etDay(), etDay(1)].includes(state.games.day) ? state.games.day : etDay());
    const leagues = state.league === 'ALL' ? Object.keys(LIVE) : [state.league];
    const status = opts.day ? 'all' : state.games.status;
    const controls = `<div class="toolbar">${seg('gday', [[etDay(-1), 'Yesterday'], [etDay(), 'Today'], [etDay(1), 'Tomorrow']], day)}${seg('gstatus', [['all', 'All'], ['live', 'Live'], ['final', 'Final']], status)}</div>`;
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
  views.game = async route => {
    const back = '<a class="back" href="#games">← Games</a>';
    let detail;
    try { detail = await get(`app/games/${route.id}.json`); } catch (e) {
      return head('', 'Game page not available', 'Game pages cover NFL and college football for games from about three days back to eight days ahead. <a href="#games/live">Live scores</a> cover every sport.', back);
    }
    const [today, teams] = await Promise.all([get('app/today.json'), teamDirectory(detail.league)]);
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
    const fav = pregame ? (detail.favoriteLines || []).filter(f => C.quoteStatus({ ...f, state: 'open' }, g.kickoff, now).current).sort((a, b) => (b.edge ?? 0) - (a.edge ?? 0)) : [];
    const favHtml = fav.length ? `<div class="board">${fav.map(f => {
      const dm = f.kind === 'player' ? defenseMatch(f, teams, g.league) : null;
      const script = f.kind === 'player' ? scriptCaution(g, f, model) : null;
      const extraFa = [];
      if (isNum(f.projection) && isNum(f.line) && f.market !== 'point spread') extraFa.push(['for', `Our average is ${C.fixed(f.projection)} against the ${f.line} line.`]);
      if (dm) extraFa.push([dm.supports ? 'for' : dm.opposes ? 'against' : 'ctx', dm.text + '.']);
      if (script) extraFa.push(['against', script]);
      if (f.kind === 'player' && g.garbageTime) extraFa.push(['against', GARBAGE]);
      const src = { ...f, id: f.sourceId || f.id, gameId: g.id, league: g.league, kickoff: g.kickoff };
      const vm = { id: f.sourceId || f.id, title: niceTitle(f.title), market: marketLabel(f), league: g.league, kickoff: g.kickoff, odds: f.odds, book: bookLabel(f.book), bestOdds: null, booksCount: 1,
        age: quoteAge(f.observedAt, g.kickoff, now, { odds: f.odds, state: 'open' }), chance: f.chance, needs: f.needs, edge: round1(f.edge), fair: fairAmerican(f.chance), otherLines: [], gameId: g.id, clears: true,
        athleteId: f.athleteId, stat: f.stat || C.marketKey(f), line: f.line, direction: f.direction || f.side, player: f.player, isProp: f.kind === 'player', alternate: f.alternate,
        sub: [historyWords(f.history), dm ? `${dm.pos} matchup: ${dm.rank} of ${dm.of}${dm.tone === 'soft' ? ', soft' : dm.tone === 'tough' ? ', tough' : ''}` : ''].filter(Boolean).join(' · '), extraFa, src };
      return boardRow(vm);
    }).join('')}</div>` : `<p class="muted small">${pregame ? 'No current line in this game passes my price check right now. ' : 'Lines close at kickoff. Saved pregame lines are below.'}</p>`;

    /* Put the card and the line status before the large projection. A game with no play must not look empty,
       but a difference between my number and the book is not itself a bet or a supported lean. */
    const postedHtml = picks.length ? section('Our plays in this game', `<div class="tickets">${picks.map(p => ticket(p)).join('')}</div>`) : '';
    const marketFresh = pregame && m.retrievedAt && Number.isFinite(Date.parse(m.retrievedAt))
      && now >= Date.parse(m.retrievedAt) && now - Date.parse(m.retrievedAt) <= 4 * 3600000;
    const bookSpread = isNum(m.spread) ? favSpread(g.home.abbr, g.away.abbr, m.spread) : 'not recorded';
    const ourSpread = isNum(model.margin) ? C.modelSpread(g.home.abbr, g.away.abbr, model.margin) : 'not available';
    const linePreview = pregame ? `<section class="game-front" aria-label="Bets and lines for this game">
      ${!picks.length ? '<p class="game-front-status">No official bet in this game.</p>' : ''}
      <p class="eyebrow">Book lines vs my numbers · research</p>
      <div class="game-front-grid"><p><b>Spread</b><span>${esc(bookSpread)} book · ${esc(ourSpread)} mine</span></p>
        <p><b>Total</b><span>${esc(isNum(m.total) ? C.fixed(m.total) : 'not recorded')} book · ${esc(isNum(model.total) ? C.fixed(model.total) : 'not available')} mine</span></p></div>
      <p class="small muted">${marketFresh ? `${esc(bookLabel(m.book) || 'Book')} · checked ${esc(ago(m.retrievedAt))}` : 'Last recorded lines · check a current price at your book'}.</p>
      ${fav.length ? `<p class="game-front-watch"><b>Price-checked lines worth a look:</b> ${fav.slice(0, 2).map(f => `${esc(niceTitle(f.title))} · ${esc(oddsText(f.odds))} ${esc(bookLabel(f.book) || '')}`).join(' · ')}${fav.length > 2 ? ` · +${fav.length - 2} more` : ''}. <a href="#game/${esc(g.id)}#lines-we-like">See the research ›</a></p>`
        : `<p class="game-front-watch">${picks.length ? 'No additional current research line clears my price check. The posted ticket above stays on the record.' : 'No price-checked lean clears my bar here.'} <a href="#game/${esc(g.id)}#model-vs">See the full comparison ›</a></p>`}
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
    const modelBlock = `<div class="card"><div class="vs" style="grid-template-columns:auto 1fr 1fr;font-size:15px"><span class="h"></span><span class="h">My number</span><span class="h">${g.market ? `Book line${bookLabel(m.book) ? ` (${esc(bookLabel(m.book))})` : ''}` : 'No book line recorded'}</span>
      <span class="k">Score</span><span class="num">${esc(g.away.abbr)} ${esc(C.fixed(model.away))} – ${esc(g.home.abbr)} ${esc(C.fixed(model.home))}</span><span class="muted">–</span>
      <span class="k">Favorite</span><span class="num">${esc(fav2)}</span><span class="num">${esc(mFav)}</span>
      <span class="k">Spread</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, model.margin))}</span><span class="num">${esc(favSpread(g.home.abbr, g.away.abbr, m.spread))}${m.spreadOpen != null && m.spreadOpen !== m.spread ? ` <span class="muted small">(opened ${esc(favSpread(g.home.abbr, g.away.abbr, m.spreadOpen))})</span>` : ''}</span>
      <span class="k">Total</span><span class="num">${esc(C.fixed(model.total))}</span><span class="num">${esc(C.fixed(m.total))}${m.totalOpen != null && m.totalOpen !== m.total ? ` <span class="muted small">(opened ${esc(m.totalOpen)})</span>` : ''}</span></div>
      ${range ? `<p class="chart-cap">${esc(rangeWords(g, range))}</p>` : ''}
      ${gapWords(gap.margin) || gapWords(gap.total) ? `<p class="chart-cap">In past-season backtests, ${gapWords(gap.margin) ? `spread gaps at least this large went ${gapWords(gap.margin)} against the closing line` : ''}${gapWords(gap.margin) && gapWords(gap.total) ? ', and ' : ''}${gapWords(gap.total) ? `total gaps went ${gapWords(gap.total)}` : ''}. Not a live record, and a gap is not a bet. <a href="#record/model">Model record →</a></p>` : ''}
      ${caution ? `<p class="caution" style="margin-top:6px">${esc(caution)}</p>` : ''}${why && !final ? `<p class="small" style="margin-top:8px"><a href="#game/${esc(g.id)}#why">Why my number differs ›</a></p>` : ''}</div>`;

    /* Underdog watch. */
    const uGame = { ...g, state: g.state || 'pre', upsetWatch: detail.upsetWatch || fromSlate.upsetWatch };
    const upsetHtml = pregame && currentUpset(uGame, now) ? section('Underdog watch', upsetRow(uGame, null), '', 'Outright upset research: our raw winner estimate against the market. Not an official play.') : '';

    /* Season trends in this game: main lines, current prices, no heavy favorites. */
    const trends = C.filterTrends(C.bestTrendPrices(detail.seasonTrends || []), { game: g.id, kind: 'main', min: 3, rate: 80 }).filter(t => !heavyFavorite(t.odds)).slice(0, 6);
    const trendsHtml = trends.length ? section('Season trends in this game', `<div class="grid two">${trends.map(t => `<div class="card"><a href="#player/${esc(g.league)}/${esc(t.athleteId)}?stat=${esc(t.stat)}"><b>${esc(t.player)}</b></a> <span class="muted small">${esc(t.direction === 'under' ? 'Under' : 'Over')} ${esc(t.line)} ${esc(STAT_WORD[t.stat] || t.stat)}</span>
      <p class="small muted">${esc(trendText(t))}${t.games < 5 ? ' · small sample' : ''} · ${esc(oddsText(t.odds))} ${esc(bookLabel(t.book) || '')} · price checked ${esc(ago(t.observedAt))}</p>${historyChart(t.history.map(h => Number(h.value)), t.history.map(h => String(h.date).slice(5)), t.line, t.direction === 'under' ? 'under' : 'over')}</div>`).join('')}</div>`,
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
          const order = slot.players.map((p, k) => `<a class="pill${out.has(String(p.id)) ? ' bad' : String(p.id) === String(next.id) ? ' good' : ''}" href="#player/NFL/${esc(p.id)}">${esc(slot.label)}${k + 1} ${esc(p.name)}${out.has(String(p.id)) ? ' · OUT' : String(p.id) === String(next.id) ? ' · NEXT UP' : ''}</a>`).join('');
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
    const projTable = side => {
      const block = (((detail.forecast || {}).players || {})[side]) || {};
      const list = block.players || [];
      if (!list.length) return `<p class="muted small">${esc(g[side].abbr)}: not enough recent games for projections.</p>`;
      const cols = PROJ_COLS.filter(([k]) => list.some(p => p[k]));
      const vol = block.volume || {};
      return `<div class="table-wrap"><table class="t"><caption class="small muted" style="text-align:left;padding-bottom:6px">${esc(g[side].abbr)}${isNum(vol.plays) ? ` · ${C.fixed(vol.plays, 0)} plays, ${Math.round(100 * (vol.passRate || 0))}% pass` : ''}</caption>
        <thead><tr><th>Player</th>${cols.map(([, l]) => `<th class="n">${esc(l)}</th>`).join('')}</tr></thead><tbody>${list.map(p => `<tr><td><span class="with-art">${headshot(g.league, p.id, 'sm')}<span><a href="#player/${esc(g.league)}/${esc(p.id)}">${esc(p.name)}</a> <span class="muted tiny">${esc(p.pos)}</span></span></span></td>${cols.map(([k]) => {
          const v = p[k];
          if ((p.underReview || []).includes(k)) return '<td class="n muted">Projection under review</td>';
          if (!Array.isArray(v)) return '<td class="n muted">–</td>';
          const market = (lines[p.id] || {})[C.PROJECTION_MARKET[k]];
          const gapV = market ? v[0] - market[0] : null;
          return `<td class="n" title="80% range ${esc(v[1])} to ${esc(v[2])}">${esc(C.fixed(v[0]))}<br>${market ? `<span class="tiny muted">line ${esc(market[0])} ${gapV > 0 ? '▲' : gapV < 0 ? '▼' : ''}${esc(C.signed(gapV))}</span>` : `<span class="tiny muted">${esc(C.fixed(v[1], 0))}–${esc(C.fixed(v[2], 0))}</span>`}</td>`;
        }).join('')}</tr>`).join('')}</tbody></table></div>`;
    };
    const projHtml = (detail.forecast || {}).players ? section('Player projections', `<div style="display:grid;gap:16px;grid-template-columns:minmax(0,1fr)">${['away', 'home'].map(side => { const n = ((((detail.forecast || {}).players || {})[side] || {}).players || []).length;
      return n ? `<details class="more-box" style="min-width:0" data-box="proj:${side}"${typeof matchMedia === 'function' && matchMedia('(min-width: 760px)').matches ? ' open' : ''}><summary>${esc(g[side].abbr)} player projections · ${n} players</summary>${projTable(side)}</details>` : projTable(side); }).join('')}</div>`, '', `My average, with the likely range underneath. ${detail.props && detail.props.capturedAt ? `Where I saw a line (${esc(ago(detail.props.capturedAt))}) it shows instead, with ▲ when I am above it and ▼ when below.` : 'No comparison lines recorded yet.'}${g.garbageTime ? ` <b class="red">${GARBAGE}</b> The spread is 21 points or more, so starters may sit early.` : ''}`)
      : pregame ? section('Player projections', '<p class="muted small">Player projections are not available for this game yet.</p>') : '';

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
      return `<div class="card"><p class="eyebrow" style="margin-bottom:6px">${esc(g[side].abbr)}</p>${list.map(p => `<p class="small" style="padding:3px 0"><span class="badge ${/out|reserve|doubtful/i.test(p.status) ? 'warn' : 'research'}" style="margin:0 6px 0 0">${esc(p.status)}</span><b>${esc(p.name)}</b> ${esc(p.position || '')} · ${esc(p.injury || 'injury not listed')}${p.reportedAt ? ` · reported ${esc(ago(p.reportedAt))}` : ''}</p>`).join('')}</div>`;
    };
    const injuryHtml = g.league === 'NFL' ? section('Injury report', `<div class="grid two">${injBlock('away')}${injBlock('home')}</div>`, '', 'ESPN injury list. Check the latest before you lean on a projection.')
      : section('Injuries', '<p class="small muted">College injury reports are not covered by the feed. Check team sources before relying on a projection.</p>');

    /* Touchdown watch: recent role snapshots only, before kickoff. */
    const tdw = pregame ? (detail.scorerResearch || []).filter(r => r.roleSnapshotAt && now - Date.parse(r.roleSnapshotAt) >= 0 && now - Date.parse(r.roleSnapshotAt) <= 7 * 86400000 && (r.games ?? 0) >= 3).slice(0, 5) : [];
    const tdAt = tdw.map(r => r.roleSnapshotAt).sort().pop();
    const tdHtml = tdw.length ? section('Touchdown watch', `<div class="board">${tdw.map(r => `<div class="row-main" style="grid-template-columns:minmax(0,2fr) minmax(0,1.2fr)"><div class="row-title with-art">${headshot(g.league, r.athleteId, 'sm')}<div>${r.athleteId ? `<a href="#player/${esc(g.league)}/${esc(r.athleteId)}"><b>${esc(r.player)}</b></a>` : `<b>${esc(r.player)}</b>`}<span>${esc(r.redZone)} red-zone carries + targets · ${esc(r.inside10)} inside the 10</span></div></div><div class="small muted">${esc(r.touchdowns)} TDs in ${esc(r.games)} games · ${esc(r.priceStatus || 'no verified TD price')}</div></div>`).join('')}</div>`, '', `Scoring opportunity, not a touchdown probability or a play. Role data as of ${esc(tdAt ? ago(tdAt) : '–')}. Verify the latest availability.`) : '';

    return `${back}${head(g.league === 'CFB' ? 'College football' : 'NFL', title, '')}${postedHtml}${linePreview}${header}${actions}${liveStamp(liveNow.refreshed)}
      ${finalHtml}
      ${whySection(g, why, final)}
      ${pregame ? anchored('lines-we-like', section('Lines we like', favHtml, why && !final ? `<a class="more" href="#game/${esc(g.id)}#why">Why my number differs →</a>` : '', 'Current prices where my estimated chance is above what the price needs. Research, not extra best bets.')) : ''}
      ${edgesHtml ? section('Matchup lines', edgesHtml, '<span class="small muted">Research, not posted plays</span>', 'Our projection, this-season hit rate at the exact line, and the opponent defense in one view. College game-script cautions rank lower.') : ''}
      ${othersHtml ? `<section class="section">${othersHtml}</section>` : ''}
      ${final && detail.final ? '' : anchored('model-vs', section('Model vs market', modelBlock))}
      ${upsetHtml}${trendsHtml}${depthHtml}${projHtml}${matchupHtml}
      ${section('Recent form', `<div class="grid two">${form('away')}${form('home')}</div>`)}
      ${injuryHtml}${tdHtml}`;
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
  views.nbaToday = async () => {
    const data = await get('app/nba.json');
    const label = g => `${g.teams.away.abbreviation} at ${g.teams.home.abbreviation}`;
    const games = (data.games || []).slice().sort((a,b) => Number(a.seasonType === 'preseason') - Number(b.seasonType === 'preseason') || a.kickoff.localeCompare(b.kickoff)).map(g => `<article class="card" style="margin-top:12px"><p class="eyebrow">${esc(g.seasonType === 'preseason' ? 'Preseason' : 'NBA')} · ${esc(whenShort(g.kickoff))}</p><h3>${esc(label(g))}</h3>
      ${g.status === 'final' ? `<p>Final: ${esc(g.scores?.away ?? '–')}–${esc(g.scores?.home ?? '–')}</p>` : `<p class="small muted">${esc(g.status === 'in_progress' ? 'In progress · live scores below' : 'Scheduled')}</p>`}
      ${g.projection ? `<p style="margin-top:8px">Research projection: ${esc(g.teams.away.abbreviation)} ${esc(g.projection.away)} · ${esc(g.teams.home.abbreviation)} ${esc(g.projection.home)}</p><p class="small muted">${g.projection.sparse ? 'Early-season number, built from last season’s team ratings.' : 'Team model projection.'} This is research, not a best bet.</p>` : ''}
      ${g.totalQuote ? `<p class="small" style="margin-top:8px">Total ${esc(g.totalQuote.line)} · over ${esc(oddsText(g.totalQuote.over))} / under ${esc(oddsText(g.totalQuote.under))} · ${esc(bookLabel(g.totalQuote.book))}</p><p class="tiny muted">Prices seen ${esc(whenShort(g.totalQuote.retrievedAt))}</p>` : ''}</article>`).join('');
    const trends = (data.trends || []).map(r => `<article class="card" style="margin-top:12px"><p class="eyebrow">${esc(r.window)} · ${esc(r.season-1)}–${esc(String(r.season).slice(-2))}</p><h3>${esc(r.name)} · ${esc(r.statName)}</h3><p>${esc(r.average)} average across ${esc(r.games)} recorded games</p><p class="small muted" style="overflow-wrap:anywhere">Game log: ${esc(r.values.join(' · '))}</p><p class="tiny muted">${esc(r.dates[0])} through ${esc(r.dates.at(-1))}. Recorded appearances only.</p></article>`).join('');
    const prep = (data.prep || []).map(r => `<div class="receipt"><div><b>${esc(r.name)} over ${esc(r.line)} ${esc(r.stat)}</b><span>${esc(r.hits)} of ${esc(r.games)} · ${esc(oddsText(r.over))} ${esc(bookLabel(r.book))} · Research</span></div></div>`).join('');
    const live = await views.gamesLive({day:etDay()});
    return `${head('NBA Today', data.heading || 'NBA Today')}<p class="small">Scores, team projections and player research. No NBA best bet has been posted.</p>
      ${!data.scheduleFresh ? '<p class="small muted">Schedule update unavailable. These are the last stored games.</p>' : ''}
      <section class="kt-page-sec"><h2>Matchups & projections</h2>${games || '<p class="small muted">No upcoming NBA matchup is stored yet.</p>'}</section>
      <section class="kt-page-sec"><h2>Player trends</h2>${trends || '<p class="small muted">Player game logs are being collected. Current-season trends need at least three recorded games.</p>'}</section>
      <section class="kt-page-sec"><h2>Prep List <span class="badge research">Research</span></h2>${prep || `<p class="small muted">${esc(data.prepNote)}</p>`}</section>
      <section class="kt-page-sec"><h2>NBA Trial</h2><p class="small">${esc(data.trial.note)}</p><p class="small">NBA Trial record: ${esc(data.trial.record?.win || 0)}–${esc(data.trial.record?.loss || 0)} · ${esc(Number(data.trial.record?.units || 0).toFixed(2))}u · ${esc(data.trial.record?.graded || 0)} graded</p><p class="small muted">Separate record · at most one labeled 1u straight play a day. A day without a qualifying play is valid.</p></section>
      <section class="kt-page-sec">${live}</section>`;
  };
  return views;
});
