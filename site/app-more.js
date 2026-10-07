'use strict';
/* Lazily loaded secondary pages. app.js supplies the shared, already-tested view helpers. */
(function (root, factory) {
  root.KRMore = factory;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (ctx) {
  const { C, P, state, esc, head, section, empty, seg, segLinks, FOOTBALL, LEAGUE_NAME,
    teamDirectory, maybe, get, indexGames, withLive, defenseRows, projCard, teamMark, headshot, when, whenShort,
    dayLabel, bookLabel, ago, niceTitle, allPicks, lineData, saved, oddsText, units, wl, roiOf, tableOf, weekLabel, MODEL_NAME,
    rec3, rate, trialCard, receipt, climbRow, cumulativeUnits, OWNER_FLAGS, kpiStrip, clvSummary, unitsChart,
    ticketRows, ticketSummary, arbFor, arbSummary, moreGroup, officialKey, isNum, inLeague, pickVM, meter } = ctx;
  const views = {};
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
      ${section('Upcoming and recent', `<div class="projs">${games.map(g => projCard(g)).join('') || '<p class="muted">No games in the current window.</p>'}</div>`)}
      ${section('This season', results, '', 'Close is the closing spread for this team. ATS is whether they covered it.')}
      ${ranks.length ? section('What this defense allows', `<div class="kpis">${ranks.map(([pos, r]) => { const tone = C.rankTone(r.rank, r.of); return `<div class="kpi"><small>${esc(pos)} ${pos === 'QB' ? 'pass' : pos === 'RB' ? 'rush' : 'rec'} yds</small><b class="num ${tone === 'soft' ? 'green' : tone === 'tough' ? 'red' : ''}">${esc(C.fixed(r.value))}</b><span>rank ${esc(r.rank)} of ${esc(r.of)}${tone === 'soft' ? ' · soft' : tone === 'tough' ? ' · tough' : ''}</span></div>`; }).join('')}</div>
        ${allowed.length ? `<details class="more-box" style="margin-top:12px"><summary>Game by game</summary><div class="table-wrap"><table class="t"><thead><tr><th>Game</th><th class="n">QB pass yds</th><th class="n">RB rush yds</th><th class="n">WR rec yds</th><th class="n">TE rec yds</th></tr></thead><tbody>${allowed.map(d => `<tr><td><a href="#game/${esc(d.gameId)}">${esc(String(d.date).slice(5))}</a> ${esc(abbr(d.opp))}</td><td class="n">${esc((d.allowed.QB || {}).passYds ?? '–')}</td><td class="n">${esc((d.allowed.RB || {}).rushYds ?? '–')}</td><td class="n">${esc((d.allowed.WR || {}).recYds ?? '–')}</td><td class="n">${esc((d.allowed.TE || {}).recYds ?? '–')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}`,
        `<a class="more" href="#research/players?view=defense&pl=${esc(league)}">All defenses →</a>`, 'Per game this season. Rank 1 allows the least.') : ''}
      ${section('Players this season', roster.length ? `<div class="list-links cols">${roster.map(p => `<a href="#player/${esc(league)}/${esc(p[0])}"><span class="with-art">${headshot(league, p[0], 'sm', team)}<span><b>${esc(p[1])}</b> <span class="muted small">${esc(p[2] || '')}</span></span></span><small>${esc(p[6] || 0)} game${Number(p[6]) === 1 ? '' : 's'} stored →</small></a>`).join('')}</div>` : '<p class="muted small">Players appear after their first stat line.</p>')}`;
  };

  views.record = async route => {
    const tab = route.tab || 'official';
    const [today, board, lab, trials, every] = await Promise.all([get('app/today.json'), maybe('scoreboard.json'), tab === 'trials' ? maybe('market-lab.json') : null, tab === 'trials' ? maybe('app/sport-research.json') : null, allPicks()]);
    indexGames(today);
    const all = every.filter(inLeague);
    const archive = C.recordArchive(all, state.record.season, state.record.phase);
    const rows = archive.rows;
    const sel = state.league === 'ALL' ? null : state.league;
    const curSeasons = [...new Set(Object.entries(archive.currentByLeague).filter(([k]) => !sel || k === sel).map(([, v]) => v))];
    const curPhases = [...new Set(Object.entries(archive.phaseByLeague).filter(([k]) => !sel || k === sel).map(([, v]) => v))];
    const curSeasonLabel = curSeasons.length === 1 ? `This season · ${curSeasons[0]}` : 'Current seasons';
    const curPhaseLabel = curPhases.length === 1 ? `Current stage · ${curPhases[0] === 'playoffs' ? 'Playoffs' : 'Regular season'}` : 'Current stages';
    const seasonLabel = archive.selectedSeason === 'current' ? curSeasonLabel.replace('This season · ', '') : archive.selectedSeason === 'all' ? 'All seasons' : String(archive.selectedSeason);
    const phaseLabel = archive.selectedPhase === 'current' ? curPhaseLabel.replace('Current stage · ', '') : archive.selectedPhase === 'all' ? 'Full season' : archive.selectedPhase === 'playoffs' ? 'Playoffs' : 'Regular season';
    const kLabel = `Record · ${archive.selectedSeason === 'all' ? 'all seasons' : seasonLabel} · ${phaseLabel}`;
    const showSeason = archive.seasons.length > 1, hasPlayoffs = all.some(p => C.recordPhaseOf(p) === 'playoffs');
    const nonDefault = state.record.season !== 'current' || state.record.phase !== 'current';
    const k = kpiStrip(all, board, rows, nonDefault ? kLabel : curPhases.length === 1 && curPhases[0] === 'playoffs' ? 'Playoff record' : 'Season record');
    const tabs = `<div class="toolbar"><div class="chip-scroll">${segLinks([['#record', 'Best bets', 'official'], ['#record/fun', 'Fun', 'fun'], ['#record/climb', 'Climb', 'climb'], ['#record/model', 'Model', 'model'], ['#record/trials', 'Trials', 'trials']], tab)}</div></div>`;
    const top = `${head('The record', 'Every play, graded in public', `Win or lose, at the price and book we posted. Nothing is deleted.${state.league !== 'ALL' ? ` Showing ${esc(LEAGUE_NAME[state.league])}.` : ''}`)}`;
    const clvById = new Map(((board || {}).picks || {}).rows?.map(r => [r.id, r.clv]) || []);
    const pickers = !showSeason && !hasPlayoffs ? '' : `<div class="toolbar">${showSeason ? `<label class="sr" for="rs">Season</label><select id="rs" class="select" data-select="season">${[['current', curSeasonLabel], ...archive.seasons.filter(v => curSeasons.length !== 1 || String(v) !== String(curSeasons[0])).map(v => [String(v), String(v)]), ['all', 'All seasons']].map(([v, l]) => `<option value="${esc(v)}"${String(archive.selectedSeason) === v ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>` : ''}
      ${hasPlayoffs ? `<label class="sr" for="rp">Stage</label><select id="rp" class="select" data-select="phase">${[['current', curPhaseLabel], ['regular', 'Regular season'], ['playoffs', 'Playoffs'], ['all', 'Full season']].filter(([v]) => curPhases.length !== 1 || v !== curPhases[0]).map(([v, l]) => `<option value="${v}"${archive.selectedPhase === v ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>` : ''}</div>
      ${nonDefault ? `<p class="small muted" style="margin:-4px 0 12px">Showing ${esc(seasonLabel)} · ${esc(phaseLabel)}. A new season or the first playoff play starts a fresh default view; older results stay in the archive.</p>` : ''}`;
    const rq = state.record.q.trim().toLowerCase();
    const matches = p => !rq || [p.title, p.displayTitle, p.player, p.kind, p.result, p.book, bookLabel(p.book)].some(v => String(v || '').toLowerCase().includes(rq));
    const search = `<div class="toolbar"><div class="grow"><label class="sr" for="rq">Search the plays</label><input id="rq" class="search" type="search" placeholder="Search by player, team or market" value="${esc(state.record.q)}" data-input="rq" autocomplete="off" maxlength="160"></div></div>`;
    const weeksOf = (list, renderRow, scope) => {
      const byWeek = new Map();
      list.forEach(p => { const w = C.weekOf(p.kickoff || p.settledAt || p.publishedAt) || '0000-00-00'; if (!byWeek.has(w)) byWeek.set(w, []); byWeek.get(w).push(p); });
      return [...byWeek].sort((a, b) => b[0].localeCompare(a[0])).map(([w, items], i) => {
        const t = C.summaryOf(items, 10);
        const br = C.recordBreakdown(items.filter(p => !C.isParlay(p)));
        const fun = scope === 'fun';
        const label = w === '0000-00-00' ? 'Undated' : `Week of ${weekLabel(w)}`;
        const assumedNote = !fun && br.assumed.wins + br.assumed.losses ? ` · incl. ${wl(br.assumed)} at assumed −115` : '';
        const sum = `${scope === 'climb' ? '' : `${wl(t)} · ${units(fun ? t.units : br.captured.units)}${assumedNote} · `}${items.length} ${scope === 'climb' ? 'step' : 'play'}${items.length === 1 ? '' : 's'}`;
        return `<details class="week" data-box="week:${esc(w)}${rq ? ':q' : ''}"${i === 0 || rq ? ' open' : ''}><summary class="week-head"><span><b>${esc(label)}</b></span><span>${esc(sum)}</span></summary><div class="receipts">${items.map(renderRow).join('')}</div></details>`;
      }).join('');
    };

    if (tab === 'official') {
      const straight = rows.filter(p => !C.isParlay(p));
      const rec = C.recordBreakdown(straight);
      rec.captured.roi = OWNER_FLAGS.roi ? roiOf(rec.captured) : null;
      const points = cumulativeUnits(straight, C.unitsFor);
      const open = straight.filter(p => !p.result && !p.historicalImport).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
      const imported = straight.filter(p => p.result && C.isUnpricedImport(p));
      const settled = straight.filter(p => p.result && !C.isUnpricedImport(p) && matches(p)).sort((a, b) => String(b.kickoff || b.settledAt).localeCompare(String(a.kickoff || a.settledAt)));
      const counted = rows.filter(p => !C.isUnpricedImport(p));
      const st = counted.filter(p => !C.isParlay(p));
      const MARKET_NAME = { Totals: 'Game totals', Spreads: 'Spreads', Straights: 'Player props', 'Risky lines': 'Risky player lines' };
      const byWeek = [...new Set(st.map(p => C.weekOf(p.kickoff || p.publishedAt)).filter(Boolean))].sort().reverse().map(w => [weekLabel(w), C.summaryOf(st.filter(p => C.weekOf(p.kickoff || p.publishedAt) === w))]);
      const archiveGroups = new Map();
      for (const p of all) { if (!Number.isInteger(Number(p.season))) continue; const key = [p.league, p.season, C.recordPhaseOf(p)].join('|'); if (!archiveGroups.has(key)) archiveGroups.set(key, []); archiveGroups.get(key).push(p); }
      const compact = items => { const t = C.summaryOf(items); return items.length ? `${wl(t)}${t.pending ? ` · ${t.pending} pending` : ''}` : '—'; };
      const archiveRows = [...archiveGroups].sort((a, b) => b[0].localeCompare(a[0])).map(([key, items]) => { const [lg, season, phase] = key.split('|');
        return [`${lg} ${season} · ${phase === 'playoffs' ? 'Playoffs' : 'Regular season'}`, compact(items.filter(p => !C.isParlay(p) && !C.isUnpricedImport(p))), compact(items.filter(p => C.isParlay(p) && !C.isLadder(p) && !C.isUnpricedImport(p))), compact(items.filter(C.isLadder))]; });
      return `${top}${tabs}${pickers}${k.html}
        ${section('Units over the season', `<div class="card">${unitsChart(points) || '<p class="muted small">Not enough graded plays yet.</p>'}<p class="chart-cap">${esc(wl(rec.captured))} at posted prices · ${esc(units(rec.captured.units))}${rec.captured.roi != null ? ` · ROI ${rec.captured.roi > 0 ? '+' : ''}${rec.captured.roi.toFixed(1)}%` : ''}. ${rec.assumed.wins + rec.assumed.losses ? `${esc(wl(rec.assumed))} more from before prices were recorded, counted at an assumed −115 and kept out of the units line.` : ''}${rec.credits ? ` Promo credits of ${rec.credits}u are not counted as winnings.` : ''}</p></div>`)}
        ${open.length ? section('Not graded yet', `<div class="receipts">${open.map(p => receipt(p, clvById)).join('')}</div>`, '', 'Graded at the price we posted, even if the price has moved since.') : ''}
        ${section('Every result', `${search}${settled.length ? weeksOf(settled, p => receipt(p, clvById)) : `<p class="muted">${rq ? 'No play matches. Try a player, a team or a market.' : 'Nothing settled yet. Plays show here once their games are final.'}</p>`}`)}
        ${imported.length ? `<details class="more-box"><summary>Week 1 hand-posted legs (no prices) · ${esc(wl(C.summaryOf(imported)))} · not counted</summary><div class="receipts">${imported.map(p => receipt(p, clvById)).join('')}</div></details>` : ''}
        <details class="more-box" data-box="more-numbers" style="margin-top:12px"><summary>More numbers</summary><div><p class="small muted" style="margin-bottom:8px">Same plays, cut different ways. These include assumed prices and promo credits; the units line above does not.</p>
          <p class="eyebrow" style="margin:10px 0 6px">By sport</p>${tableOf('Sport', [['NFL', C.summaryOf(st.filter(p => p.league === 'NFL'))], ['College', C.summaryOf(st.filter(p => p.league === 'CFB'))]])}
          <p class="eyebrow" style="margin:14px 0 6px">By kind</p>${tableOf('Kind', [['Researched plays', C.summaryOf(st.filter(p => !p.modelLean))], ['Model plays', C.summaryOf(st.filter(p => p.modelLean))], ['Fun tickets', C.summaryOf(counted.filter(p => C.isParlay(p) && !C.isLadder(p)))]])}
          <p class="small muted" style="margin-top:6px">Researched plays are backed by a checked news fact. Model plays go out on our number alone.</p>
          ${[...new Set(st.map(C.category))].length > 1 ? `<p class="eyebrow" style="margin:14px 0 6px">By market</p>${tableOf('Market', [...new Set(st.map(C.category))].map(n => [MARKET_NAME[n] || n, C.summaryOf(st.filter(p => C.category(p) === n))]))}` : ''}
          ${byWeek.length ? `<p class="eyebrow" style="margin:14px 0 6px">By week</p>${tableOf('Week', byWeek)}` : ''}</div></details>
        ${archiveRows.length ? `<details class="more-box" data-box="archive" style="margin-top:12px"><summary>Season archive</summary><div><p class="small muted" style="margin-bottom:8px">Official posted results only. Personal tickets never enter these totals.</p><div class="table-wrap"><table class="t"><thead><tr><th>Season</th><th class="n">Best bets</th><th class="n">Fun tickets</th><th class="n">Climb steps</th></tr></thead><tbody>${archiveRows.map(r => `<tr><td>${esc(r[0])}</td><td class="n">${esc(r[1])}</td><td class="n">${esc(r[2])}</td><td class="n">${esc(r[3])}</td></tr>`).join('')}</tbody></table></div></div></details>` : ''}`;
    }
    if (tab === 'fun') {
      const fun = rows.filter(p => C.isParlay(p) && !C.isLadder(p) && !C.isUnpricedImport(p));
      const s = C.summaryOf(fun, 10);
      const settled = fun.filter(p => p.result && matches(p)).sort((a, b) => String(b.kickoff).localeCompare(String(a.kickoff)));
      const open = fun.filter(p => !p.result);
      return `${top}${tabs}${pickers}<div class="kpis"><div class="kpi"><small>Fun tickets</small><b class="num">${esc(wl(s))}</b><span>longshots at a smaller stake</span></div><div class="kpi"><small>Units</small><b class="num ${s.units < 0 ? 'red' : 'green'}">${esc(units(s.units))}</b><span>recorded ticket stakes · never in the best-bet record</span></div><div class="kpi"><small>Pending</small><b class="num">${s.pending}</b><span>not settled</span></div></div>
        ${open.length ? section('Not graded yet', `<div class="receipts">${open.map(p => receipt(p, clvById)).join('')}</div>`) : ''}
        ${section('Every fun ticket', `${search}${settled.length ? weeksOf(settled, p => receipt(p, clvById), 'fun') : '<p class="muted">No fun tickets match.</p>'}`)}`;
    }
    if (tab === 'climb') {
      if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${tabs}${empty(`No Climb for ${LEAGUE_NAME[state.league]}`, 'The 80/20 Climb uses NFL and college football legs. No football data is substituted here. Switch to All sports, NFL or College football to see it.', 'research')}`;
      const lad = C.theLadder(every);
      const acc = lad.accounting;
      const money = n => `$${Math.round(Number(n) || 0).toLocaleString('en-US')}`;
      return `${top}${tabs}<div class="kpis"><div class="kpi"><small>Current climb</small><b class="num">#${esc(lad.run)} · step ${esc(lad.step)}</b><span>${money(lad.banked + lad.stake)} of $1,000</span></div><div class="kpi"><small>Steps</small><b class="num">${esc(acc.wins)}–${esc(acc.losses)}</b><span>won–lost</span></div><div class="kpi"><small>Banked so far</small><b class="num">${money(lad.saved)}</b><span>across every climb · stays banked after a miss</span></div><div class="kpi"><small>Best climb</small><b class="num">${money(lad.best)}</b><span>highest bank + ride</span></div>
        <div class="kpi"><small>Wagered</small><b class="num">${money(acc.wagered)}</b><span>returned ${money(acc.returned)}</span></div><div class="kpi"><small>Net</small><b class="num ${acc.net < 0 ? 'red' : 'green'}">${acc.net < 0 ? '−' : '+'}${money(Math.abs(acc.net))}</b><span>lifetime, in dollars</span></div></div>
        <div class="card" style="margin-top:14px"><p>Bank 20% of every winning return and ride 80% on the next step. A miss ends the climb and starts a new $50 one; banked money stays banked. A new step is never guaranteed.</p>${lad.open ? `<p class="small" style="margin-top:6px">A step is open now. <a href="#today">See Today</a>.</p>` : '<p class="small muted" style="margin-top:6px">Next step: being checked · not posted yet.</p>'}</div>
        ${section('Past steps', `<div class="receipts">${lad.history.slice().reverse().map(climbRow).join('') || '<p class="muted">No settled steps yet.</p>'}</div>`, '', `The Climb keeps its own run history and spans NFL and college legs, so it is shown whole; changing the season view does not change an active run.${lad.climbs.length ? ` Climbs finished: ${lad.climbs.length}.` : ''}`)}`;
    }
    if (tab === 'model') {
      if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${tabs}${empty(`${LEAGUE_NAME[state.league]} is in research, not official picks yet`, '<a href="#record/trials">See its trial →</a>', 'research')}`;
      const card = C.projectionScorecard(board, every, FOOTBALL.includes(state.league) ? state.league : 'ALL');
      const live = ((board || {}).live || []).filter(inLeague);
      const back = ((board || {}).backtest || []).filter(inLeague);
      const markets = state.league === 'CFB' ? [] : (((board || {}).props || {}).markets || []);
      const clvRows = (((board || {}).picks || {}).rows || []).filter(inLeague);
      const clv = clvSummary(clvRows);
      const closer = markets.filter(r => isNum(r.lineMiss) && isNum(r.projectionMiss) && r.lineMiss < r.projectionMiss).length;
      const modelTable = list => `<div class="table-wrap"><table class="t"><thead><tr><th>Model</th><th class="n">Games</th><th class="n">Winner</th><th class="n">Spread vs close</th><th class="n">Margin miss</th><th class="n">Close miss</th><th class="n">Totals vs close</th><th class="n">Total miss</th><th class="n">Closer than line</th><th class="n">Line moved our way</th><th class="n">80% range held</th></tr></thead><tbody>${list.map(r => { const s = r.summary || {};
        return `<tr><td>${esc(r.league === 'CFB' ? 'College' : r.league)} · ${esc(MODEL_NAME[r.model] || r.model)}<br><span class="tiny muted">${esc(r.season)}</span></td><td class="n">${esc(s.games)}</td><td class="n">${(s.winner || []).reduce((a, b) => a + b, 0) ? `${esc(rec3(s.winner))}<br><span class="tiny muted">${rate(s.winner)}</span>` : '<span class="muted" title="Not computed for this sample">–</span>'}</td><td class="n">${esc(rec3(s.side))}<br><span class="tiny muted">${rate(s.side)}</span></td><td class="n">${esc(C.fixed(s.marginMiss))}</td><td class="n">${esc(C.fixed(s.closeMarginMiss))}</td>
          <td class="n">${esc(rec3(s.ou))}<br><span class="tiny muted">${rate(s.ou)}</span></td><td class="n">${esc(C.fixed(s.totalMiss))}<br><span class="tiny muted">close ${esc(C.fixed(s.closeTotalMiss))}</span></td><td class="n">${rate(s.closerMargin)}</td><td class="n">${rate(s.movedToward)}</td><td class="n">${s.within80 != null ? Math.round(100 * s.within80) + '%' : '–'}</td></tr>`; }).join('')}</tbody></table></div>`;
      const weeksTable = list => list.filter(r => (r.weeks || []).length).map(r => `<details class="more-box" style="margin-top:8px"><summary>${esc(r.league === 'CFB' ? 'College' : r.league)} · ${esc(MODEL_NAME[r.model] || r.model)} · ${esc(r.season)} by week</summary><div class="table-wrap"><table class="t"><thead><tr><th>Week</th><th class="n">Games</th><th class="n">Winner</th><th class="n">Spread vs close</th><th class="n">Margin miss</th><th class="n">Close miss</th><th class="n">Totals vs close</th></tr></thead><tbody>${r.weeks.map(w =>
        `<tr><td>${esc(w.week === 'post' ? 'Postseason' : 'Week ' + w.week)}</td><td class="n">${esc(w.games)}</td><td class="n">${esc(rec3(w.winner))} <span class="tiny muted">${rate(w.winner)}</span></td><td class="n">${esc(rec3(w.side))}</td><td class="n">${esc(C.fixed(w.marginMiss))}</td><td class="n">${esc(C.fixed(w.closeMarginMiss))}</td><td class="n">${esc(rec3(w.ou))}</td></tr>`).join('')}</tbody></table></div></details>`).join('');
      return `${top}${tabs}<p class="muted small" style="margin-bottom:12px">How the model's final pregame calls did against the closing line. This is model accuracy, not betting profit. Break-even at a standard −110 price is 52.4%. Official plays are graded separately.</p>
        <div class="kpis"><div class="kpi"><small>Spread vs close</small><b class="num">${esc(rate(card.spread))}</b><span>${esc(card.spread.join('–'))}</span></div><div class="kpi"><small>Projected winners</small><b class="num">${esc(rate(card.moneyline))}</b><span>${esc(card.moneyline.join('–'))} · no price</span></div><div class="kpi"><small>Totals vs close</small><b class="num">${esc(rate(card.total))}</b><span>${esc(card.total.join('–'))}</span></div><div class="kpi"><small>Player props vs line</small><b class="num">${esc(rate(card.props))}</b><span>${esc(card.props.join('–'))} · ${esc(card.propsNote)}</span></div><div class="kpi"><small>Fun tickets</small><b class="num">${esc(rate(card.parlays))}</b><span>${esc(card.parlays.join('–'))} · tracked apart</span></div><div class="kpi"><small>Picks beat the close</small><b class="num">${clv.measured ? `${clv.beat}/${clv.measured}` : '–'}</b><span>${clv.measured ? `${clv.tied} tied · ${clv.lost} lost` : ''}</span></div></div>
        <p class="small muted" style="margin-top:8px">${esc(card.games)} graded games · through ${esc(card.updatedThrough ? dayLabel(card.updatedThrough) : '–')} · final pregame forecast. Projected winners are accuracy only, not a betting result, since there is no price and favorites usually win. Fun tickets are published results, tracked separately from best bets.</p>
        ${live.length ? section('Live record, by league', modelTable(live) + weeksTable(live), '', 'Published before kickoff. Miss = average points off the final. When the close misses by less, the market was the better forecast.') : ''}
        ${back.length ? `<details class="more-box" data-box="backtests"><summary>Backtests (never published) · ${back.length}</summary><div>${modelTable(back)}<p class="small muted" style="margin-top:6px">${esc(((board || {}).method || {}).backtest || 'Retrospective walk-forward. Never published, so it is evidence about the method, not a record.')}</p></div></details>` : ''}
        ${markets.length ? section('NFL player projections vs the DraftKings line', `<div class="table-wrap"><table class="t"><thead><tr><th>Market</th><th class="n">Graded</th><th class="n">Record</th><th class="n">Closer than line</th><th class="n">Our miss</th><th class="n">Line miss</th></tr></thead><tbody>${markets.map(r => `<tr><td>${esc(C.LABEL[r.market] || r.market)}</td><td class="n">${esc(r.graded)}</td><td class="n">${esc(rec3(r.record))}</td><td class="n">${rate(r.closerThanLine)}</td><td class="n">${esc(C.fixed(r.projectionMiss))}</td><td class="n">${esc(C.fixed(r.lineMiss))}</td></tr>`).join('')}</tbody></table></div>`, '',
          `The book line beat our projection in ${closer} of ${markets.length} markets. That is why we cut our raw numbers down before showing a chance.`) : ''}
        ${clvRows.length ? `<details class="more-box" data-box="clv"><summary>Closing-line value, play by play · ${clvRows.length}</summary><p class="small muted" style="margin:0 0 8px">${esc(((board || {}).method || {}).clv || 'Posted line vs the last comparable line before kickoff, in points, positive when better.')} Beating the close more often than not is the earliest sign of real skill; it is not a result.</p><div class="table-wrap"><table class="t"><thead><tr><th>Play</th><th class="n">Posted</th><th class="n">Last before kickoff</th><th class="n">CLV</th><th>Result</th></tr></thead><tbody>${clvRows.map(r => `<tr><td>${esc(niceTitle(r.title))}<br><span class="tiny muted">${esc(/^espn ?bet$/i.test(String(r.book || '').trim()) ? 'ESPN BET' : bookLabel(r.book) || '')} ${esc(oddsText(r.postedOdds))}</span></td><td class="n">${esc(r.postedLine ?? '–')}</td><td class="n">${esc(r.closeLine ?? '–')}${r.closeAt ? `<br><span class="tiny muted">${esc(r.closeSource || '')} · ${esc(r.minutesBeforeKickoff)} min before</span>` : ''}</td><td class="n ${r.clv > 0 ? 'green' : r.clv < 0 ? 'red' : ''}">${r.clv == null ? '–' : esc(C.signed(r.clv))}</td><td>${esc(r.result || 'pending')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}`;
    }
    /* Trials: new sports collecting evidence, never official plays. */
    const leagues = ['NBA', 'WNBA', 'CBB', 'MLB', 'NHL', 'EPL', 'MLS'].filter(l => state.league === 'ALL' || state.league === l);
    if (!leagues.length) return `${top}${tabs}${empty('No trial in this view', 'Football has its own record. Pick another sport at the top, or see the model results.', 'research')}<p><a href="#record/model">Model vs market →</a></p>`;
    if (!lab && !trials) return `${top}${tabs}${empty('Trial data did not load', 'The trial and data-collection files are unavailable right now. <button type="button" class="btn small" data-retry>Try again</button>', 'research')}`;
    const cards = leagues.map(lg => trialCard(lg, lab, trials)).join('');
    return `${top}${tabs}<p class="muted small" style="margin-bottom:12px">New sports run as paper trials first. Nothing here is a best bet, and nothing joins the public card or socials without a full trial and the owner's approval.</p>
      <div class="grid two">${cards || (lab || trials ? '' : '<p class="muted">Trial data did not load. <button type="button" class="btn small" data-retry>Try again</button></p>')}</div>`;
  };

  views.more = async () => `${head('More', 'Tools and help', '')}
    ${moreGroup('New here', `<a href="#start"><span><b>Start here</b><br><span class="small muted">How to read a best bet in 30 seconds, plus the glossary</span></span><small>→</small></a>
      <a href="https://discord.gg/ZnjubjsBPM" target="_blank" rel="noopener"><span><b>Free Kook'n Discord</b><br><span class="small muted">Best bets land here about 10–15 minutes before X</span></span><small>↗</small></a>
      <a href="https://x.com/keenkooks" target="_blank" rel="noopener"><span><b>Follow on X</b></span><small>@keenkooks ↗</small></a>`)}
    ${moreGroup('Yours', `<a href="#saved"><span><b>Saved</b></span><small>${state.watchlist.length} saved →</small></a>
      <a href="#ticket"><span><b>My ticket</b><br><span class="small muted">A personal draft, never a pick</span></span><small>${state.ticket.length} legs →</small></a>`)}
    ${moreGroup('Tools', `<a href="#arbs"><span><b>Arb calculator</b><br><span class="small muted">Exact two-book stake math</span></span><small>→</small></a>
      <a href="#schedule"><span><b>Release schedule</b><br><span class="small muted">When best bets, research and results post</span></span><small>→</small></a>
      <a href="#status"><span><b>Data status</b><br><span class="small muted">How fresh prices and scores are</span></span><small>→</small></a>`)}
    ${moreGroup('Help', `<a href="#feedback"><span><b>Feedback</b></span><small>→</small></a>
      <a href="#responsible"><span><b>Responsible gaming</b></span><small>→</small></a>`)}`;
  views.glossary = async () => views.start();
  views.start = async () => `<a class="back" href="#more">← More</a>${head('Start here', 'How to read a best bet', 'Thirty seconds, then you know everything on the page.')}
    <div class="tickets"><article class="ticket"><div class="ticket-body"><div class="ticket-top"><span class="tag">Best bet</span><span>Example</span></div><div class="ticket-rule"></div><h3>Player over 49.5 receiving yards</h3><p class="market">Player prop · receiving yards</p><div class="price"><b>−110</b><span>DraftKings</span></div>
      <p class="plain">We think this hits <strong>56%</strong> of the time. At −110 you only need 52%.</p>${meter(0.56, 0.524)}<div class="meter-labels"><span>0%</span><span>needs 52%</span><span>100%</span></div></div><div class="stub open"><b>56%</b><small>our chance</small></div></article>
      <div class="card"><ol style="margin:0;padding-left:18px;display:grid;gap:8px"><li><b>The price and book.</b> −110 at DraftKings is what we saw when we posted. Check your own book; prices move.</li><li><b>Our chance vs what the price needs.</b> The green bar is our chance. The black tick is the break-even point for that price. Green past the tick means value.</li><li><b>Edge and fair price.</b> Edge is the gap in percentage points. Fair price is what the odds would be if our chance were exactly right.</li><li><b>Graded in public.</b> A green ticket hit, a red ticket missed, gray pushed. Every result stays on the Record.</li></ol></div></div>
    ${section('Two ways to use Kook\'n', `<div class="grid two"><div class="card"><p class="eyebrow green">The quick route</p><h3 style="margin-top:4px">Our best bets</h3><p class="small" style="margin-top:4px">Open Today for the posted best bets and the Climb. Tap a ticket for how we got the number.</p><p style="margin-top:8px"><a class="btn small" href="#today">See Today →</a></p></div>
      <div class="card"><p class="eyebrow green">Do your own research</p><h3 style="margin-top:4px">The research board</h3><p class="small" style="margin-top:4px">Every line sorted by edge, hit-rate trends, matchup charts and defenses. Save players or lines to compare later.</p><p style="margin-top:8px"><a class="btn small" href="#research/lines">Open Research →</a></p></div></div>`)}
    ${section('Inside the free Discord', `<div class="card"><p><b>Plays & Results:</b> posted plays only. Best bets usually land here 10–15 minutes before X.</p><p style="margin-top:6px"><b>General chat:</b> games, questions and feedback. <b>Wins & Bad Beats:</b> wins and close misses.</p><p class="small muted" style="margin-top:6px">Research is not a best bet. A historical hit rate is not a promise. Check the exact line and price yourself.</p><p style="margin-top:10px"><a class="btn primary small" href="https://discord.gg/ZnjubjsBPM" target="_blank" rel="noopener">Join the Discord ↗</a></p></div>`)}
    ${section('Glossary', `<dl class="glossary card">
      <dt>Best bet</dt><dd>An official Kook'n play. It counts in the public record at one unit, at the price and book we posted.</dd>
      <dt>Pick of the Day</dt><dd>The one best bet we feature each day. Its record is shown on the Record page.</dd>
      <dt>Research</dt><dd>Lines we track and grade but did not post. Useful context, not picks.</dd>
      <dt>Unit (u)</dt><dd>One standard stake. +1.00u means you won one stake; −1.00u means you lost one.</dd>
      <dt>Break-even</dt><dd>How often a bet must win to not lose money at that price. −110 needs 52.4%.</dd>
      <dt>Edge</dt><dd>Our chance minus the break-even chance, in percentage points.</dd>
      <dt>Fair price</dt><dd>The odds that match our chance exactly. If the book pays better than fair, that is value.</dd>
      <dt>Closing line</dt><dd>The final number before kickoff. Beating it more often than not is the best early sign of real skill.</dd>
      <dt>Old price</dt><dd>The price we posted is older than our freshness limit. The play still counts at the posted price; check your book for today's.</dd>
      <dt>Fun ticket</dt><dd>A longshot parlay at a smaller stake, tracked separately from the record.</dd>
      <dt>The 80/20 Climb</dt><dd>A $50 to $1,000 challenge. A step posts only when two independent legs qualify. A winning return is split 20% banked and 80% carried to the next step. A losing step loses only its active stake; money already banked stays banked, and a new $50 climb starts. A new step is never guaranteed.</dd>
      <dt>Trial</dt><dd>A new sport collecting evidence on paper. Never a best bet until it earns a release and it earns approval.</dd></dl>`)}
    <p class="small"><a href="#record">Every published result →</a> · <a href="#feedback">Give feedback →</a></p>`;
  /* A saved best bet follows its own market on the board (same game, player, stat or market and side), same book first. */
  const pickChange = (saved, rows, now = Date.now()) => {
    if (Date.parse(saved.kickoff) <= now) return { state: 'started', text: 'Game started · saved quote is not live' };
    const okey = saved.okey || officialKey(saved);
    const live = rows.filter(r => officialKey(r) === okey && r.state === 'open' && isNum(Number(r.odds)) && now - Date.parse(r.observedAt) >= 0 && now - Date.parse(r.observedAt) <= 4 * 3600000)
      .sort((a, b) => Number(bookLabel(b.book) === bookLabel(saved.book)) - Number(bookLabel(a.book) === bookLabel(saved.book)) || Number(Number(b.line) === Number(saved.line)) - Number(Number(a.line) === Number(saved.line)) || Date.parse(b.observedAt) - Date.parse(a.observedAt));
    const current = live[0];
    if (!current) return { state: 'unavailable', text: 'No fresh matching quote · check your book' };
    const moved = Number(current.line) !== Number(saved.line) || Number(current.odds) !== Number(saved.odds) || bookLabel(current.book) !== bookLabel(saved.book);
    return { state: moved ? 'changed' : 'same', text: moved ? 'Changed since you saved it' : 'Same as your saved quote', current };
  };
  views.saved = async () => {
    const [lines, every, todayS] = await Promise.all([lineData('ALL'), allPicks(), maybe('app/today.json')]);
    if (todayS) indexGames(todayS);
    const rows = (lines || {}).lines || [];
    const byId = new Map(every.map(p => [p.id, p]));
    /* Spread rows carry their side in `side`; saved lines key on it so the two sides never match each other. */
    const sidedRows = rows.map(r => r.direction || !r.side ? r : { ...r, direction: r.side });
    const priceText = r => r && r.odds != null ? `${oddsText(r.odds)}${r.line != null ? ` at ${r.line}` : ''} ${bookLabel(r.book) || ''}`.trim() : '–';
    return `<a class="back" href="#more">← More</a>${head('Saved', 'Your saved lines, players and games', 'Stored only in this browser. No account, no alerts. Up to 100.')}
      ${state.watchlist.length ? `<div class="receipts">${state.watchlist.map(s => { const isPick = String(s.key || '').startsWith('pick:');
        const pick = isPick ? byId.get(s.pickId || String(s.key).slice(5)) : null;
        const pvm = pick ? pickVM(pick) : null;
        const c = !lines && !(pick && pick.result) ? { state: 'unchecked', text: "Couldn't re-check prices right now" } : pick && pick.result ? { state: 'settled', text: `${pvm.status}${pick.actual ? ` · ${typeof pick.actual === 'string' ? pick.actual : ''}` : ''}` }
          : pick && (C.isParlay(pick) || Date.parse(pick.kickoff) <= Date.now()) ? { state: 'reference', text: Date.parse(pick.kickoff) <= Date.now() ? 'Waiting on result' : 'Tracked as posted' }
            : isPick ? (() => { const pc = pickChange(s, rows); return pvm && pvm.mode !== 'open' ? { ...pc, text: `${pvm.status} · ${pc.text.replace('since you saved it', 'since posted')}` } : { ...pc, text: pc.text.replace('since you saved it', 'since posted') }; })() : P.changes(s, sidedRows);
        const kind = isPick ? (pvm ? { best: 'Best bet', fun: 'Fun ticket', climb: '80/20 Climb' }[pvm.kind] : 'Best bet') : s.type === 'line' ? 'Line' : s.type === 'player' ? 'Player' : s.type === 'game' ? 'Game' : 'Saved';
        const href = isPick && s.pickId ? `#pick/${encodeURIComponent(s.pickId)}` : /^#(player|game)\//.test(s.href) ? s.href : '#today';
        return `<div class="receipt" style="grid-template-columns:40px minmax(0,1fr) auto"><span class="r-mark open">★</span><div><b><a href="${esc(href)}" class="plain-link">${esc(niceTitle(s.title))}</a></b><span>${esc(kind)}${s.league ? ` · ${esc(s.league)}` : ''} · ${esc(c.text)}</span>
          ${s.type === 'line' || (isPick && !['settled', 'reference'].includes(c.state)) ? `<span>${isPick ? 'Posted' : 'When saved'}: ${esc(priceText(s))}${s.observedAt ? ` · ${esc(ago(s.observedAt))}` : ''}</span><span>Latest: ${c.state === 'unchecked' ? 'not re-checked · <button type="button" class="linkish" data-retry>Try again</button>' : c.current ? esc(priceText(c.current)) : 'no fresh quote · check your book'}</span>` : ''}</div>
          <button type="button" class="btn small" data-unsave="${esc(s.key)}" aria-label="Remove ${esc(s.title)}">Remove</button></div>`; }).join('')}</div>`
      : empty('Nothing saved yet', 'Tap ☆ Save on a best bet, a research row, a player page or a game page.', 'check')}`;
  };
  views.ticket = async () => {
    const rows = await ticketRows();
    const st = state.stake;
    return `<a class="back" href="#more">← More</a>${head('My ticket', 'A personal draft', 'It stays on this device. It is not a pick and never enters the record. Prices are re-checked against the board every time you open it.')}
      ${rows.length ? `<div class="receipts">${rows.map((r, i) => `<div class="receipt" style="grid-template-columns:40px minmax(0,1fr) auto"><span class="r-mark ${r.missing || r.closed ? 'miss' : r.changed ? 'push' : 'open'}" aria-hidden="true">${i + 1}</span><div><b>${esc(niceTitle(r.title || r.player))}${r.unchecked ? '' : r.missing ? ' <span class="badge warn">Gone</span>' : r.started ? ' <span class="badge warn">Started</span>' : r.closed ? ' <span class="badge warn">Closed</span>' : r.changed ? ' <span class="badge warn">Price changed</span>' : ''}</b>
          <span>${esc(oddsText(r.odds))} ${esc(bookLabel(r.book) || '')} · ${esc(whenShort(r.kickoff))}${r.changed ? ` · was ${esc(oddsText(r.previous.odds))}${bookLabel(r.previous.book) !== bookLabel(r.book) ? ` ${esc(bookLabel(r.previous.book) || '')}` : ''}${Number(r.previous.line) !== Number(r.line) ? ` at ${esc(r.previous.line)}, now at ${esc(r.line)}` : ''}` : ''}${r.missing ? ' · no longer on the board' : ''}</span></div>
          <span class="btn-row" style="justify-content:flex-end">${r.changed ? `<button type="button" class="btn small" data-accept="${esc(r.id)}">Accept</button>` : ''}<button type="button" class="btn small" data-remove-leg="${i}" aria-label="Remove ${esc(r.title || 'leg')}">Remove</button></span></div>`).join('')}</div>
        ${section('Stake', `<div class="card"><div class="toolbar">${seg('stakeMode', [['units', 'Units'], ['money', 'Dollars']], st.mode)}</div>
          <div class="arb-form"><label>Stake${st.mode === 'units' ? ' (units)' : ' ($)'}<input class="search" type="number" min="0" step="0.5" inputmode="decimal" data-stake="amount" value="${esc(st.amount)}"></label>${st.mode === 'units' ? `<label>Dollars per unit<input class="search" type="number" min="0" step="1" inputmode="decimal" data-stake="unit" value="${esc(st.unit)}"></label>` : ''}</div>
          <div id="ticket-summary" style="margin-top:12px">${ticketSummary(rows)}</div>
          <div class="btn-row" style="margin-top:12px"><button type="button" class="btn" data-copy-ticket>Copy ticket text</button><button type="button" class="btn" data-clear-ticket>Clear ticket</button></div></div>`)}`
      : empty('Your ticket is empty', 'Add priced lines from the <a href="#research/lines">research board</a> with + Ticket.', 'check')}`;
  };
  views.arbs = async () => {
    const a = state.arb;
    return `<a class="back" href="#more">← More</a>${head('Arb calculator', 'Two books, every outcome covered', 'Exact stake math, with the catches left in. Time-sensitive arb candidates go to the free Discord, never to this page. An arb candidate is never a best bet and never enters the record.')}
      <div class="card"><div class="arb-form"><label>Side A American odds<input class="search" type="text" inputmode="text" pattern="[-+]?[0-9]*" autocomplete="off" value="${esc(a.first)}" data-arb="first"></label><label>Side B American odds<input class="search" type="text" inputmode="text" pattern="[-+]?[0-9]*" autocomplete="off" value="${esc(a.second)}" data-arb="second"></label><label>Total bankroll ($)<input class="search" type="number" min="0.01" step="0.01" inputmode="decimal" value="${esc(a.bankroll)}" data-arb="bankroll"></label></div>
      <div id="arb-summary" aria-live="polite">${arbSummary(arbFor(a))}</div></div>
      ${section('The rules', `<div class="card"><ol style="margin:0;padding-left:18px;display:grid;gap:8px"><li><b>Exact means exact.</b> Same event, market, period and line. A middle is not an arb.</li><li><b>Both bets must still exist.</b> A price can disappear before the second bet is accepted.</li><li><b>Settlement rules must match.</b> Voids, limits, account restrictions and different house rules can break the math.</li><li><b>No automatic betting.</b> Kook'n never touches a sportsbook account or places a bet.</li></ol></div>`)}
      <div class="card on-felt"><p class="small"><b>Entertainment and calculation only.</b> This calculator does not know whether either price is available to you. Verify the exact event, market, line, period, price, limits and settlement rules in both apps before doing anything.</p></div>`;
  };
  views.lab = async () => views.record({ tab: 'trials' });
  views.schedule = async () => {
    const row = (time, title, note) => `<tr><td class="num" style="white-space:nowrap"><b>${esc(time)}</b></td><td><b>${esc(title)}</b><br><span class="small muted">${esc(note)}</span></td></tr>`;
    return `<a class="back" href="#more">← More</a>${head('Release schedule', 'When things post', 'All times Eastern. Windows, not promises: a play still has to clear its line, price and news checks.')}
    ${section('Every game day', `<div class="table-wrap"><table class="t"><tbody>
      ${row('8:45 AM', "Today's menu", 'Only when approved best bets are already ready.')}
      ${row('9:00 AM', 'Results', "Yesterday's best bets, win or lose. Wednesdays add the weekly recap.")}
      ${row('10:00 AM', 'Save-this sheet', 'College Saturday and NFL Sunday.')}
      ${row('10:30 AM', 'Research card', 'One trend, matchup, injury or underdog card when the evidence qualifies.')}
      ${row('Around noon', 'Best bets', 'About two hours before the earliest kickoff; earlier kickoffs move it up. Discord usually gets them 10–15 minutes before X.')}
      ${row('After games', 'Hits and Climb updates', 'Wins can post after they settle. Misses always stay on the record.')}
      ${row('6:00 PM', 'Quiet-day record', 'Only when nothing more useful posted that day.')}</tbody></table></div>`)}
    ${section('When a Climb step can post', `<div class="table-wrap"><table class="t"><tbody>
      ${row('10:00 AM', 'Climb check', 'A step posts only when two independent legs qualify.')}
      ${row('1:30 PM', 'Climb check', 'A settled step can advance the same day.')}
      ${row('4:00 PM', 'Climb check', 'Later slates stay open without forcing a step.')}
      ${row('8:00 PM', 'Climb check', 'The last scheduled check of the day.')}</tbody></table></div>`)}
    ${section('Behind the scenes', `<div class="table-wrap"><table class="t"><tbody>
      ${row('Daily', 'Data and price checks', '6:45 AM, 8:30 AM, 11:45 AM, 5:30 PM, 9:00 PM and 11:30 PM. Late games and overnight results stay in the rotation.')}
      ${row('Football days', 'Extra checks', 'Sunday 2:45 PM. Sunday, Monday and Thursday 6:50 PM. On weekend evening slates, one of the five card places stays open until 4 PM.')}
      ${row('Every 5 min', 'Delivery checks', 'Discord delivery and quiet live-score checks. Public live updates are still being tested.')}
      ${row('Every 30 min', 'Pre-post review', 'Queued plays are re-checked against stored prices and current news before release. Not a live sportsbook feed.')}</tbody></table></div>`)}
    <div class="card on-felt"><p class="small"><b>What "scheduled" means.</b> These are release windows, not promised picks. Prices move and news can pull a queued play. Discord gets confirmed best bets first; X carries the public post and every result.</p></div>`;
  };
  views.status = async () => {
    const today = await get('app/today.json');
    const NAME = { slate: 'Schedule and lines', forecasts: 'Model forecasts', props: 'Prop lines', injuries: 'Injuries', boxscores: 'Box scores' };
    const WORD = { current: 'Current', late: 'Late', stale: 'Late', failed: 'Failed', error: 'Failed' };
    const health = (today.health || []).length ? today.health : Object.entries(today.freshness || {}).map(([component, observedAt]) => ({ component, observedAt, status: observedAt ? 'current' : 'unknown' }));
    const LIM = { slate: 4, boxscores: 48, forecasts: 24, injuries: 12, props: 12 };
    health.forEach(h => { h.late = !h.observedAt || (LIM[h.component] && Date.now() - Date.parse(h.observedAt) > LIM[h.component] * 3600000); });
    const off = health.filter(h => h.status !== 'current' || h.late);
    return `<a class="back" href="#more">← More</a>${head('Data status', 'How fresh is everything', 'The latest successful checks. Hosted refreshes run through the day and can run late.')}
      <div class="table-wrap"><table class="t"><tbody>${health.map(h => { const word = !h.observedAt ? 'Unknown' : h.status === 'current' && h.late ? 'Late' : (WORD[h.status] || 'Unknown');
        return `<tr><td>${esc(NAME[h.component] || h.component)}</td><td class="n"><span class="status-dot${word === 'Current' ? '' : ' old'}"></span>${esc(word)}</td><td class="n muted">${esc(h.observedAt ? ago(h.observedAt) : 'no time recorded')}</td></tr>`; }).join('')}</tbody></table></div>
      ${off.length ? `<div class="card on-felt" style="margin-top:12px">${off.map(h => `<p class="small"><b>${esc(NAME[h.component] || h.component)}:</b> ${esc(h.fallback || 'Check source age before relying on it.')}</p>`).join('')}</div>` : ''}
      <p class="small muted" style="margin-top:10px">Live scores come straight from ESPN's public scoreboard in your browser. Prices and picks always come from our time-stamped snapshots.</p>`;
  };
  views.feedback = async () => `<a class="back" href="#more">← More</a>${head('Feedback', 'What helped, what got in the way', 'Nothing is sent automatically. Prepare your note here, copy it, and send it to us privately on Discord.')}
    <div class="card"><div class="arb-form"><label>Area<select id="fb-area" class="select"><option>Today / best bets</option><option>Research</option><option>Games / scores</option><option>Record</option><option>Saved / ticket</option><option>Discord</option><option>Something else</option></select></label>
      <label>Experience<select id="fb-rating" class="select"><option>Useful</option><option>Confusing</option><option>Something broke</option><option>Feature idea</option></select></label></div>
      <label class="sr" for="fb">Your feedback</label><textarea id="fb" class="search" rows="5" maxlength="1200" style="min-height:120px;margin-top:10px" placeholder="What were you trying to do?"></textarea>
      <label class="small" style="display:flex;gap:8px;align-items:center;margin-top:8px"><input type="checkbox" id="fb-usage"> Include my page-visit counts (section names only)</label>
      <div class="btn-row" style="margin-top:10px"><button type="button" class="btn primary" data-prepare-feedback>Prepare message</button></div>
      <p class="small muted" style="margin-top:8px">Counts stay in this browser and contain no player names, searches or account details. Don't include account or payment details.</p>
      <div id="fb-out" aria-live="polite" style="margin-top:10px"></div></div>`;
  views.responsible = async () => `<a class="back" href="#more">← More</a>${head('Responsible gaming', 'Play for fun, play within limits', '')}
    <div class="card" style="display:grid;gap:10px"><p><b>21+ where legal.</b> Kook'n is research and entertainment. Nothing here is betting advice or a guarantee, and no pick is ever certain.</p>
      <p>Set a budget before you play and treat it as the cost of entertainment. Never chase losses.</p>
      <p><b>Gambling problem? Call 1-800-MY-RESET</b> (1-800-697-3738), the National Problem Gambling Helpline. It's free, confidential and open 24/7. 1-800-522-4700 also works.</p>
      <p class="small muted">Kook'n is not a sportsbook and never places bets. Prices shown are snapshots from licensed books and can change at any time.</p></div>`;


  return views;
});
