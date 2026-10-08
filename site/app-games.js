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
  views.games = async route => {
    const tab = route.tab || 'upcoming';
    if (route.league) setLeague(route.league);
    const tabs = `<div class="chip-scroll">${segLinks([['#games', 'Upcoming', 'upcoming'], ['#games/live', 'Live & scores', 'live'], ['#games/final', 'Finals', 'final']], tab)}</div>`;
    const top = `${head('Games', tab === 'live' ? 'Live and scores' : tab === 'final' ? 'Recent finals' : 'Upcoming games', tab === 'upcoming' ? "Our projected score and win chance for every game, and how our number compares with the market. Off and Def are our model's team ranks; #1 is best." : tab === 'live' ? 'Every sport we track. Scores refresh about every minute while this page is open.' : 'How our projected scores compared with the finals.')}${tabs}`;
    if (tab === 'live') return top + await gamesLive();
    const today = await get('app/today.json');
    if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${empty('Football only for projections', `${esc(LEAGUE_NAME[state.league])} has live scores here, not projections yet. Some sports also run a paper trial. <a href="#games/live">See live scores</a> or <a href="#record/trials">the trial record</a>.`, 'research')}`;
    const merged = withLive((today.games || []).filter(inLeague));
    let games = merged.games;
    const q = state.games.q.trim().toLowerCase();
    if (q) games = games.filter(g => [g.home.abbr, g.home.name, g.away.abbr, g.away.name].some(v => String(v || '').toLowerCase().includes(q)));
    const search = `<div class="grow"><label class="sr" for="gq">Find a team</label><input id="gq" class="search" type="search" placeholder="Find a team" value="${esc(state.games.q)}" data-input="gq" autocomplete="off" maxlength="80"></div>`;
    const byDay = (list, newest) => {
      const days = new Map();
      list.forEach(g => { const d = dayLabel(g.kickoff); if (!days.has(d)) days.set(d, []); days.get(d).push(g); });
      return [...days.entries()].map(([d, l]) => `<p class="eyebrow" style="margin:18px 0 10px">${esc(d)}</p><div class="projs">${l.map(g => projCard(g)).join('')}</div>`).join('');
    };
    if (tab === 'final') {
      games = games.filter(g => g.completed).sort((a, b) => String(b.kickoff).localeCompare(String(a.kickoff)));
      const shown = state.games.all ? games : games.slice(0, 60);
      return `${top}<div class="toolbar">${search}</div>${liveStamp(merged.refreshed)}${shown.length ? byDay(shown, true) : empty(q ? 'No final matches' : 'No recent finals', q ? 'Try a team name or abbreviation.' : 'Finals from the last few days appear here.', 'games')}
        ${games.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-all-games>Show all ${games.length} finals</button></p>` : ''}`;
    }
    games = games.filter(g => !g.completed).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    const s = state.games.sort, onDay = d => games.filter(g => C.dayOf(g.kickoff) === d);
    /* One day at a time: the next day with a game still to kick off, unless the reader picks another. */
    const dayKeys = [...new Set(games.map(g => C.dayOf(g.kickoff)))].sort();
    const day = state.games.upDay === 'all' || dayKeys.includes(state.games.upDay) ? state.games.upDay : dayKeys.find(d => onDay(d).some(g => Date.parse(g.kickoff) > Date.now())) || dayKeys[0];
    const toolbar = `<div class="toolbar">${dayKeys.length > 1 ? `<div class="chip-scroll">${seg('gup', [...dayKeys.map(d => [d, `${whenShort(onDay(d)[0].kickoff).split(',')[0]} · ${onDay(d).length}`]), ['all', `All · ${games.length}`]], day)}</div>` : ''}<button type="button" class="chip" data-flag-games aria-pressed="${s === 'gap'}">Biggest gap first</button>${search}</div>`;
    if (!games.length) return `${top}${toolbar}${empty(q ? 'No game matches' : 'No upcoming games', q ? 'Try a team name or abbreviation.' : 'Nothing in this league inside the current window.', 'games')}`;
    let list = q || day === 'all' ? games : onDay(day);
    const next = q || day === 'all' ? null : dayKeys[dayKeys.indexOf(day) + 1];
    const nextBtn = next ? `<p style="margin-top:12px"><button type="button" class="btn" data-set="gup:${next}">Next: ${esc(dayLabel(onDay(next)[0].kickoff))} · ${onDay(next).length} games →</button></p>` : '';
    if (s === 'gap') {
      list = list.slice().sort((a, b) => gapScore(b) - gapScore(a) || String(a.kickoff).localeCompare(String(b.kickoff)));
      const shown = state.games.all ? list : list.slice(0, 20);
      return `${top}${toolbar}<p class="small muted" style="margin-bottom:10px">Ranked by how unusual the gap between our number and the market is, against every stored game. A gap is a reason to look, not a bet.</p>${liveStamp(merged.refreshed)}
        <div class="projs">${shown.map(g => projCard(g)).join('')}</div>
        ${list.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-all-games>Show all ${list.length} games</button></p>` : nextBtn}`;
    }
    return `${top}${toolbar}${liveStamp(merged.refreshed)}${byDay(list)}${nextBtn}`;
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
    const picks = (today.picks || []).filter(p => p.gameId === g.id || (p.gameIds || []).includes(g.id));
    const qbText = ['away', 'home'].flatMap(side => ((detail.teams || {})[side]?.injuries || []).filter(p => p.position === 'QB' && /out|doubtful|questionable|inactive/i.test(p.status || '')).map(p => `${p.name || p.player || g[side].abbr} ${p.status}`)).join('; ');
    const header = projCard({ ...g, v2: model, lean: detail.lean || fromSlate.lean, marketRead: detail.marketRead || fromSlate.marketRead }, { big: true, link: false }) + (qbText ? `<p class=caution>QB news: ${esc(qbText)}</p>` : '');
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
      const src = { ...f, id: f.sourceId || f.id, gameId: g.id, league: g.league, kickoff: g.kickoff };
      const vm = { id: f.sourceId || f.id, title: niceTitle(f.title), market: marketLabel(f), league: g.league, kickoff: g.kickoff, odds: f.odds, book: bookLabel(f.book), bestOdds: null, booksCount: 1,
        age: quoteAge(f.observedAt, g.kickoff, now, { odds: f.odds, state: 'open' }), chance: f.chance, needs: f.needs, edge: round1(f.edge), fair: fairAmerican(f.chance), otherLines: [], gameId: g.id, clears: true,
        athleteId: f.athleteId, stat: f.stat || C.marketKey(f), line: f.line, direction: f.direction || f.side, player: f.player, isProp: f.kind === 'player', alternate: f.alternate,
        sub: [historyWords(f.history), dm ? `${dm.pos} matchup: ${dm.rank} of ${dm.of}${dm.tone === 'soft' ? ', soft' : dm.tone === 'tough' ? ', tough' : ''}` : ''].filter(Boolean).join(' · '), extraFa, src };
      return boardRow(vm);
    }).join('')}</div>` : `<p class="muted small">${pregame ? 'No current line in this game passes our price check right now. ' : 'Lines close at kickoff. Saved pregame lines are below.'}</p>`;

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
        ${script ? `<span class="red">${esc(script)}</span>` : ''}${(r.warnings || [])[0] ? `<span class="red">${esc(r.warnings[0])}</span>` : ''}</div><span class="small muted" style="text-align:right">${esc(price)}</span></div>`;
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
    const modelBlock = `<div class="card"><div class="vs" style="grid-template-columns:auto 1fr 1fr;font-size:15px"><span class="h"></span><span class="h">Our number</span><span class="h">${g.market ? `Book line${bookLabel(m.book) ? ` (${esc(bookLabel(m.book))})` : ''}` : 'No book line recorded'}</span>
      <span class="k">Score</span><span class="num">${esc(g.away.abbr)} ${esc(C.fixed(model.away))} – ${esc(g.home.abbr)} ${esc(C.fixed(model.home))}</span><span class="muted">–</span>
      <span class="k">Favorite</span><span class="num">${esc(fav2)}</span><span class="num">${esc(mFav)}</span>
      <span class="k">Spread</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, model.margin))}</span><span class="num">${esc(favSpread(g.home.abbr, g.away.abbr, m.spread))}${m.spreadOpen != null && m.spreadOpen !== m.spread ? ` <span class="muted small">(opened ${esc(favSpread(g.home.abbr, g.away.abbr, m.spreadOpen))})</span>` : ''}</span>
      <span class="k">Total</span><span class="num">${esc(C.fixed(model.total))}</span><span class="num">${esc(C.fixed(m.total))}${m.totalOpen != null && m.totalOpen !== m.total ? ` <span class="muted small">(opened ${esc(m.totalOpen)})</span>` : ''}</span></div>
      ${range ? `<p class="chart-cap">${esc(rangeWords(g, range))}</p>` : ''}
      ${gapWords(gap.margin) || gapWords(gap.total) ? `<p class="chart-cap">In past-season backtests, ${gapWords(gap.margin) ? `spread gaps at least this large went ${gapWords(gap.margin)} against the closing line` : ''}${gapWords(gap.margin) && gapWords(gap.total) ? ', and ' : ''}${gapWords(gap.total) ? `total gaps went ${gapWords(gap.total)}` : ''}. Not a live record, and a gap is not a bet. <a href="#record/model">Model record →</a></p>` : ''}
      ${caution ? `<p class="caution" style="margin-top:6px">${esc(caution)}</p>` : ''}</div>`;

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
    const projHtml = (detail.forecast || {}).players ? section('Player projections', `<div style="display:grid;gap:16px">${['away', 'home'].map(side => { const n = ((((detail.forecast || {}).players || {})[side] || {}).players || []).length;
      return n ? `<details class="more-box" data-box="proj:${side}"${typeof matchMedia === 'function' && matchMedia('(min-width: 760px)').matches ? ' open' : ''}><summary>${esc(g[side].abbr)} player projections · ${n} players</summary>${projTable(side)}</details>` : projTable(side); }).join('')}</div>`, '', `Our average, with the likely range underneath. ${detail.props && detail.props.capturedAt ? `Where we saw a line (${esc(ago(detail.props.capturedAt))}) it shows instead, with ▲ when we are above it and ▼ when below.` : 'No comparison lines recorded yet.'}`)
      : pregame ? section('Player projections', '<p class="muted small">Player projections are not available for this game yet.</p>') : '';

    /* What each defense allows, by position. */
    const defRows = ((teams || {}).defense || {}).rows || {};
    const defRowsL = defenseRows(teams, g.league);
    const matchupSide = (offense, defense) => `<div class="card"><p class="eyebrow" style="margin-bottom:6px">${esc(offense.abbr)} offense vs ${esc(defense.abbr)} defense</p><table class="t"><thead><tr><th>Position</th><th class="n">Allowed a game</th><th class="n">Rank</th></tr></thead><tbody>${MATCHUP.map(([pos, key]) => {
      const r = C.rankOf(defRowsL, defense.id, pos, key);
      const tone = r ? C.rankTone(r.rank, r.of) : '';
      return `<tr><td>${esc(pos)} ${esc((C.LABEL[key] || key).toLowerCase())}</td><td class="n">${r ? esc(C.fixed(r.value)) : '–'}</td><td class="n">${r ? `<span class="rank ${tone}">${esc(r.rank)}/${esc(r.of)}</span>` : ''}</td></tr>`;
    }).join('')}</tbody></table></div>`;
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

    return `${back}${head(g.league === 'CFB' ? 'College football' : 'NFL', title, '')}${header}${actions}${liveStamp(liveNow.refreshed)}
      ${picks.length ? section('Our plays in this game', `<div class="tickets">${picks.map(p => ticket(p)).join('')}</div>`) : ''}
      ${finalHtml}
      ${pregame ? section('Lines we like', favHtml, '', 'Current prices where our estimated chance is above what the price needs. Research, not extra best bets.') : ''}
      ${edgesHtml ? section('Matchup lines', edgesHtml, '<span class="small muted">Research, not posted plays</span>', 'Our projection, this-season hit rate at the exact line, and the opponent defense in one view. College game-script cautions rank lower.') : ''}
      ${othersHtml ? `<section class="section">${othersHtml}</section>` : ''}
      ${final && detail.final ? '' : section('Model vs market', modelBlock)}
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
      ${section('Upcoming and recent', `<div class="projs">${games.map(g => projCard(g)).join('') || '<p class="muted">No games in the current window.</p>'}</div>`)}
      ${section('This season', results, '', 'Close is the closing spread for this team. ATS is whether they covered it.')}
      ${ranks.length ? section('What this defense allows', `<div class="kpis">${ranks.map(([pos, r]) => { const tone = C.rankTone(r.rank, r.of); return `<div class="kpi"><small>${esc(pos)} ${pos === 'QB' ? 'pass' : pos === 'RB' ? 'rush' : 'rec'} yds</small><b class="num ${tone === 'soft' ? 'green' : tone === 'tough' ? 'red' : ''}">${esc(C.fixed(r.value))}</b><span>rank ${esc(r.rank)} of ${esc(r.of)}${tone === 'soft' ? ' · soft' : tone === 'tough' ? ' · tough' : ''}</span></div>`; }).join('')}</div>
        ${allowed.length ? `<details class="more-box" style="margin-top:12px"><summary>Game by game</summary><div class="table-wrap"><table class="t"><thead><tr><th>Game</th><th class="n">QB pass yds</th><th class="n">RB rush yds</th><th class="n">WR rec yds</th><th class="n">TE rec yds</th></tr></thead><tbody>${allowed.map(d => `<tr><td><a href="#game/${esc(d.gameId)}">${esc(String(d.date).slice(5))}</a> ${esc(abbr(d.opp))}</td><td class="n">${esc((d.allowed.QB || {}).passYds ?? '–')}</td><td class="n">${esc((d.allowed.RB || {}).rushYds ?? '–')}</td><td class="n">${esc((d.allowed.WR || {}).recYds ?? '–')}</td><td class="n">${esc((d.allowed.TE || {}).recYds ?? '–')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}`,
        `<a class="more" href="#research/players?view=defense&pl=${esc(league)}">All defenses →</a>`, 'Per game this season. Rank 1 allows the least.') : ''}
      ${section('Players this season', roster.length ? `<div class="list-links cols">${roster.map(p => `<a href="#player/${esc(league)}/${esc(p[0])}"><span class="with-art">${headshot(league, p[0], 'sm', team)}<span><b>${esc(p[1])}</b> <span class="muted small">${esc(p[2] || '')}</span></span></span><small>${esc(p[6] || 0)} game${Number(p[6]) === 1 ? '' : 's'} stored →</small></a>`).join('')}</div>` : '<p class="muted small">Players appear after their first stat line.</p>')}`;
  };
  views.gamesLive = gamesLive;
  return views;
});
