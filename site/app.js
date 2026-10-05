/* KeenRoudy Sports. Hash-routed views over small page payloads in data/app/.
   The pipeline records every number; this file only lays them out. No framework. */
(() => {
  'use strict';

  const C = window.KRCore;
  const { esc, DASH, odds, signed, fixed, when, whenShort, dayLabel, ago } = C;
  const $ = selector => document.querySelector(selector);

  /* ---------- storage and state ---------- */

  const saved = {
    get(key, fallback) { try { const v = localStorage.getItem('kr:' + key); return v == null ? fallback : JSON.parse(v); } catch (e) { return fallback; } },
    set(key, value) { try { localStorage.setItem('kr:' + key, JSON.stringify(value)); } catch (e) { /* private mode: keep it in memory */ } },
  };

  const state = {
    trendRate: '80', trendStat: 'all', trendKind: 'main', trendWindow: 'season', trendQuery: '', trendDay: 'all',
    league: saved.get('league', 'ALL'),     /* a first visit shows every play, whichever sport it is in */
    gamesScope: 'upcoming', gamesQuery: '', boardDay: 'today', boardScope: 'open', boardSort: 'best', boardQuery: '', boardMode: 'games', propMarket: 'all', playerQuery: '', recordQuery: '',
    chartStat: 'recYds', chartPos: 'all', chartWindow: 'last5', chartDay: 'next', chartQuery: '',
    stat: null, defensePos: 'WR', defenseStat: 'recYds', defenseScope: 'season', defenseOrder: 'soft',
    logSeason: 'all', scoresLeague: 'MLB', scoresDate: null, recordScope: 'all',
    ticket: saved.get('ticket', []), stake: saved.get('stake', { amount: 1, mode: 'units', unit: 10 }),
    arb: saved.get('arb', { first: 298, second: -195, bankroll: 181.55 }),
  };

  const cache = new Map();
  const get = path => {
    if (!cache.has(path)) {
      const request = fetch('data/' + path, { cache: 'no-cache' })
        .then(r => r.ok ? r.json() : Promise.reject(new Error(`${path} returned HTTP ${r.status}`)));
      request.catch(() => cache.delete(path));
      cache.set(path, request);
    }
    return cache.get(path);
  };
  const maybe = path => get(path).catch(() => null);

  const dataLeague = () => state.league === 'CFB' ? 'CFB' : 'NFL';
  const inLeague = row => state.league === 'ALL' || row.league === state.league;
  const leagueName = league => league === 'CFB' ? 'College' : league;

  /* ---------- small fragments ---------- */

  const icon = path => `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
  const ICONS = {
    today: '<path d="M3 12l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    games: '<ellipse cx="12" cy="12" rx="9" ry="6"/><path d="M8 12h8"/>',
    stats: '<path d="M4 19V10"/><path d="M10 19V5"/><path d="M16 19v-6"/><path d="M22 19H2"/>',
    board: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h10"/>',
    model: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
    record: '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"/>',
    more: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
  };
  const TABS = [['today', 'Today'], ['games', 'Games'], ['stats', 'Charts'], ['record', 'Record'], ['more', 'More']];
  const TAB_FOR = { trends: 'today', board: 'today', game: 'games', player: 'stats', team: 'stats', model: 'record', ticket: 'today', research: 'more', scores: 'more', arbs: 'more', lab: 'more', schedule: 'more' };
  const boardTabs = active => `<nav class="board-tabs" aria-label="Lines and plays"><a href="#today" ${active === 'card' ? 'aria-current="page"' : ''}>Plays</a><a href="#board/favorites" ${active === 'favorites' ? 'aria-current="page"' : ''}>Best lines</a><a href="#board" ${active === 'lines' ? 'aria-current="page"' : ''}>Games</a><a href="#board/props" ${active === 'props' ? 'aria-current="page"' : ''}>Props</a><a href="#trends" ${active === 'trends' ? 'aria-current="page"' : ''}>Trends</a></nav>`;
  const scoreTabs = active => `<nav class="board-tabs" aria-label="Scoreboard view"><a href="#record" ${active === 'official' ? 'aria-current="page"' : ''}>Results</a><a href="#model" ${active === 'model' ? 'aria-current="page"' : ''}>Model results</a></nav>`;

  /* The two model generations, in plain words. The data keeps its own version names. */
  const MODEL_NAME = { 'v2.0': 'Our model', v1: 'First model', 'v1 replay': 'First model replay' };
  const modelName = m => MODEL_NAME[m] || m;

  const empty = (title, text, action = '') => `<div class="empty"><h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`;
  const head = (title, text, back = '') => `<div class="page-head">${back}<h1${back ? ' style="margin-top:8px"' : ''}>${esc(title)}</h1>${text ? `<p>${text}</p>` : ''}</div>`;
  const section = (title, body, link = '') => `<div class="section"><div class="section-head"><p class="eyebrow">${esc(title)}</p>${link}</div>${body}</div>`;
  const seg = (key, options, current) => `<div class="seg" role="group">${options.map(([value, label]) =>
    `<button type="button" data-set="${esc(key)}:${esc(value)}" aria-pressed="${String(current) === String(value)}">${esc(label)}</button>`).join('')}</div>`;
  const stat = (label, value, note = '', tone = '') => `<div class="stat"><div class="stat-label">${esc(label)}</div><div class="stat-value num ${tone}">${value}</div>${note ? `<div class="stat-note">${note}</div>` : ''}</div>`;
  /* Teams by name, not by abbreviation: "Coastal", "Rams". */
  const teamName = team => (team && (team.name || team.abbr)) || DASH;
  const teamRow = (team, score) => `<div class="game-team"><span class="game-chip" style="background:${esc(team.color || '#64748b')}"></span><span>${esc(teamName(team))}</span>${score != null ? `<span class="score" style="margin-left:auto">${esc(score)}</span>` : ''}</div>`;
  const plainNumber = x => String(Math.round(Number(x) * 10) / 10);
  /* Our predicted margin in words: "Coastal by 1.7". */
  const ourMargin = (game, margin) => margin == null ? 'no number yet' : Math.abs(margin) < 0.05 ? 'a dead heat'
    : `${teamName(margin > 0 ? game.home : game.away)} by ${Math.abs(margin).toFixed(1)}`;

  /* Our plays, one card each, in the same words as the play's X post: what it is, the play, the price and
     stake, our number against the line, and the one reason the post gives. Tap for the full research. */
  const playKind = p => C.isLadder(p) ? 'Ladder' : (p.legs || []).length || p.parlayType ? 'Fun parlay' : p.athleteId ? 'Player prop' : 'Team prop';
  /* What we project, in the card's and the post's words: "We project 47.1 total points", "We project 4.6 receptions". */
  const MARKET_WORDS = { rec: 'receptions', car: 'carries', recYds: 'receiving yards', rushYds: 'rushing yards', att: 'pass attempts',
    cmp: 'completions', passYds: 'passing yards' };
  const numberText = p => {
    if (typeof p.projection !== 'number' || typeof p.line !== 'number') return '';
    const value = plainNumber(p.projection);
    if (p.athleteId || p.market) { if (MARKET_WORDS[p.market]) return `We project ${value} ${MARKET_WORDS[p.market]}`; }
    else if (p.marketType === 'total' || ['over', 'under'].includes(String(p.direction || '').toLowerCase())) return `We project ${value} total points`;
    return `Our number ${value} vs the ${plainNumber(p.line)}`;
  };
  /* The projection cards' look everywhere a team or a player shows: team logos (the away team, then the home team) or
     the player's photo, from ESPN. A missing image just drops out. */
  const HEADSHOT = { NFL: id => `https://a.espncdn.com/i/headshots/nfl/players/full/${encodeURIComponent(id)}.png`,
    CFB: id => `https://a.espncdn.com/i/headshots/college-football/players/full/${encodeURIComponent(id)}.png` };
  const pic = (src, cls) => src ? `<img class="${cls}" src="${esc(src)}" alt="" loading="lazy" onerror="this.remove()">` : '';
  const gameOf = x => gameIndex.get(x.gameId || (x.gameIds || [])[0]);
  const avatar = (x, size = '') => {
    const league = x.league || String(x.gameId || (x.gameIds || [])[0] || x.id || '').split('-')[0];
    if (x.athleteId && HEADSHOT[league]) return `<span class="ava ava-head ${size}">${pic(HEADSHOT[league](x.athleteId), 'ava-img')}</span>`;
    const g = gameOf(x);
    if (!g || !LOGO[g.league] || !g.away || !g.home) return '';
    return `<span class="ava ava-pair ${size}">${pic(LOGO[g.league](g.away), 'ava-logo')}${pic(LOGO[g.league](g.home), 'ava-logo')}</span>`;
  };
  /* How far our projection clears the line, in the play's direction: positive is our way. */
  const edgeOf = p => {
    const d = String(p.direction || '').toLowerCase();
    if (typeof p.projection !== 'number' || typeof p.line !== 'number' || !['over', 'under'].includes(d)) return null;
    return d === 'over' ? p.projection - p.line : p.line - p.projection;
  };
  /* The numbers a play stands on, in tiles like the projection apps: the posted price, the line, what we project, the edge. */
  const statTiles = p => {
    const cells = [];
    if (p.odds != null) cells.push([p.priceEstimated ? 'Est. price' : 'Posted', odds(p.odds), p.book || '']);
    if (typeof p.line === 'number' && !(p.legs || []).length) cells.push(['Line', plainNumber(p.line), String(p.direction || '').toLowerCase()]);
    if (typeof p.projection === 'number') cells.push(['Projection', plainNumber(p.projection), MARKET_WORDS[p.market] || (p.marketType === 'total' ? 'points' : '')]);
    const e = edgeOf(p);
    if (e != null) cells.push(['Gap', `${e > 0 ? '+' : ''}${plainNumber(e)}`, 'our way']);
    if ((p.legs || []).length) cells.push(['Legs', String(p.legs.length), '']);
    return cells.length ? `<span class="play-stats">${cells.map(([k, v, sub]) => `<span><small>${esc(k)}</small><b class="num${k === 'Edge' ? (v.startsWith('+') ? ' up' : ' down') : ''}">${esc(v)}</b>${sub ? `<em>${esc(sub)}</em>` : ''}</span>`).join('')}</span>` : '';
  };
  const countdown = iso => {
    const ms = Date.parse(iso) - Date.now();
    if (!(ms > 0) || ms >= 24 * 36e5) return '';
    const h = Math.floor(ms / 36e5), m = Math.floor((ms % 36e5) / 6e4);
    return h ? `kicks off in ${h}h ${m}m` : `kicks off in ${m}m`;
  };

  /* ESPN's public scoreboards allow direct browser reads. Use them only for factual score/status refreshes: odds,
     forecasts and picks stay on the desk's timestamped snapshots. A failure quietly falls back to the built page. */
  const LIVE = {
    NFL: ['football', 'nfl', ''], CFB: ['football', 'college-football', '&groups=80&limit=1000'],
    NBA: ['basketball', 'nba', ''], WNBA: ['basketball', 'wnba', ''],
    CBB: ['basketball', 'mens-college-basketball', '&groups=50&limit=1000'],
    MLB: ['baseball', 'mlb', ''], NHL: ['hockey', 'nhl', ''],
    EPL: ['soccer', 'eng.1', ''], MLS: ['soccer', 'usa.1', ''],
  };
  const liveCache = new Map(), LIVE_TTL = 45000;
  const etDay = (offset = 0) => {
    const date = new Date(Date.now() + offset * 86400000);
    const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Indiana/Indianapolis',
      year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date).map(p => [p.type, p.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  };
  const liveState = raw => {
    const type = ((raw || {}).type || {}), name = String(type.name || '').toUpperCase();
    if (name.includes('POSTPONED')) return ['postponed', false, 'pre'];
    if (name.includes('CANCELED') || name.includes('CANCELLED')) return ['cancelled', false, 'pre'];
    if (name.includes('SUSPENDED')) return ['suspended', false, 'in'];
    if (name.includes('DELAYED')) return ['delayed', false, type.state || 'pre'];
    if (type.completed) return ['final', true, 'post'];
    return [type.state === 'in' ? 'in_progress' : 'scheduled', false, type.state || 'pre'];
  };
  const liveEvent = (event, league) => {
    const competition = (event.competitions || [])[0];
    if (!competition) return null;
    const status = competition.status || event.status || {}, [kind, completed, stateName] = liveState(status);
    const teams = {};
    for (const row of competition.competitors || []) {
      const side = row.homeAway, team = row.team || {};
      if (!['home', 'away'].includes(side)) continue;
      const rawScore = row.score && typeof row.score === 'object' ? (row.score.value ?? row.score.displayValue) : row.score;
      const score = ['scheduled', 'postponed', 'cancelled'].includes(kind) || rawScore == null || rawScore === '' ? null : Number(rawScore);
      teams[side] = { id: String(team.id || ''), name: team.displayName || team.name || '', shortName: team.shortDisplayName || team.name || '',
        abbreviation: team.abbreviation || '', logo: team.logo || '', score: Number.isFinite(score) ? score : null };
    }
    if (!teams.home || !teams.away) return null;
    const type = status.type || {};
    return { id: `${league}-${event.id}`, providerId: String(event.id), league, status: kind, completed, state: stateName,
      statusDetail: type.shortDetail || type.description || kind, period: status.period, clock: status.displayClock,
      kickoff: competition.date || event.date, teams };
  };
  const liveSnapshot = async (league, day) => {
    const config = LIVE[league];
    if (!config || !/^\d{4}-\d{2}-\d{2}$/.test(day || '')) return null;
    const key = `${league}:${day}`, prior = liveCache.get(key);
    if (prior && Date.now() - prior.at < LIVE_TTL) return prior;
    /* The web host is the browser-facing mirror. The older site.api host can return an Akamai 403 to ordinary
       cross-site browser requests even while server-side reads still work. */
    const url = `https://site.web.api.espn.com/apis/site/v2/sports/${config[0]}/${config[1]}/scoreboard?dates=${day.replaceAll('-', '')}${config[2]}`;
    const controller = new AbortController(), stop = setTimeout(() => controller.abort(), 6500);
    try {
      const response = await fetch(url, { cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error(`score feed returned ${response.status}`);
      const payload = await response.json();
      if (!Array.isArray(payload.events)) throw new Error('score feed did not return games');
      const value = { at: Date.now(), games: payload.events.map(e => liveEvent(e, league)).filter(Boolean) };
      liveCache.set(key, value);
      return value;
    } catch (error) {
      return prior || null;
    } finally { clearTimeout(stop); }
  };
  const liveFootball = async games => {
    const leagues = [...new Set(games.map(game => game.league).filter(league => ['NFL', 'CFB'].includes(league)))];
    const offsets = state.gamesScope === 'final' ? [0, -1] : [0];
    const snapshots = (await Promise.all(leagues.flatMap(league => offsets.map(offset => liveSnapshot(league, etDay(offset)))))).filter(Boolean);
    const live = new Map(snapshots.flatMap(s => s.games).map(g => [g.id, g]));
    return { refreshed: snapshots.length ? Math.max(...snapshots.map(s => s.at)) : null, games: games.map(game => {
      const now = live.get(game.id); if (!now) return game;
      return { ...game, state: now.state, completed: now.completed, status: now.statusDetail,
        away: { ...game.away, score: now.teams.away.score }, home: { ...game.home, score: now.teams.home.score } };
    }) };
  };
  const liveStamp = refreshed => refreshed ? `<p class="row-meta live-freshness"><span></span>Scores refresh every minute while this page is open.</p>` : '';
  /* Preserve the official pick, but never present an expired quote as a current entry. */
  const playState = p => {
    const raw = C.pickState(p);
    const stale = raw.word === 'Price expired' && !p.entryNote && p.status !== 'expired';
    return { st: raw, stale };
  };
  /* The ladder's climb as a bar on a log scale, so every doubling is the same step: current bank plus ride filled,
     and the total after a win shaded ahead. */
  const money = n => `$${Math.round(Number(n) || 0).toLocaleString('en-US')}`;
  const signedMoney = n => {
    const value = Math.round(Number(n) || 0), dollars = `$${Math.abs(value).toLocaleString('en-US')}`;
    return value > 0 ? `+${dollars}` : value < 0 ? `−${dollars}` : dollars;
  };
  const ladderPct = n => Math.max(0, Math.min(100, 100 * Math.log(Math.max(Number(n) || 50, 50) / 50) / Math.log(1000 / 50)));
  const ladderBar = (stake, payout) => `<span class="ladder-track" role="img" aria-label="${esc(money(stake))} on the way to $1,000">
      <i class="ladder-win" style="width:${ladderPct(payout).toFixed(1)}%"></i><i class="ladder-now" style="width:${ladderPct(stake).toFixed(1)}%"></i></span>
    <span class="ladder-ends"><span>$50</span><span>$1,000</span></span>`;
  const rungMoney = info => {
    const split = C.ladderSplit(info.payout), banked = Number(info.banked) || 0;
    return { banked, bankThisWin: Number(info.bankThisWin) || split.bank,
      bankedAfter: Number(info.bankedAfter) || banked + split.bank, nextStake: Number(info.nextStake) || split.ride };
  };
  const playCard = p => {
    const { st, stale } = playState(p);
    const legs = (p.legs || []).filter(l => typeof l === 'string' || l.title);
    const rung = C.isLadder(p), info = p.ladder || {};
    const lotto = !rung && legs.length && p.odds >= 1000;
    const kind = rung ? `🪜 80/20 Climb · Step ${info.step || 1}` : `${p.featured ? 'Pick of the Day · ' : ''}${lotto ? `🎰 Lotto · ${legs.length} legs` : playKind(p)}`;
    const when = countdown(p.kickoff) || whenShort(p.kickoff || p.publishedAt);
    const title = rung ? `${money(info.stake)} → ${money(info.payout)}` : p.displayTitle || p.title || p.player;
    const route = C.pickResearchRoute(p);
    const action = route ? (p.athleteId ? 'View player stats' : 'View matchup') : 'View pick details';
    const compact = [p.odds != null ? `Posted ${odds(p.odds)}` : '', p.book || '', when].filter(Boolean).join(' · ');
    return `<details class="play${p.featured ? ' play-featured' : ''}${lotto ? ' play-lotto' : ''}${rung ? ' play-ladder' : ''}" style="--rail:${esc(rung ? '#48e8c3' : p.color || 'var(--mint)')}">
      <summary class="play-summary">
      <span class="play-top"><span class="play-kind">${esc(kind)}${p.favorite && !legs.length && !p.featured ? ' · Favorite' : ''}</span>${stale ? '' : `<span class="pill pill-${st.tone}">${esc(st.word)}</span>`}</span>
      <span class="play-hero">${legs.length ? '' : avatar(p, 'ava-lg')}<span class="play-title${rung ? ' num' : ''}">${lotto ? `<span class="lotto-odds num">${esc(odds(p.odds))}</span> ` : ''}${esc(title)}</span></span>
      <span class="play-compact-meta">${esc(compact)}${stale ? ' · check current price' : ''}</span>
      <span class="play-expand-hint"><span>View details</span></span>
      </summary>
      <div class="play-body">
      ${legs.length ? `<span class="play-legs">${legs.map(l => typeof l === 'string' ? `<span class="leg">• ${esc(l)}</span>` : `<span class="leg">${avatar(l, 'ava-sm') || '•'} ${esc(l.title)}</span>`).join('')}</span>` : ''}
      ${rung ? `<span class="play-reason">${money(rungMoney(info).banked)} banked · a win banks ${money(rungMoney(info).bankThisWin)} and rides ${money(rungMoney(info).nextStake)}</span>
      <span class="ladder-bar">${ladderBar((Number(info.banked) || 0) + Number(info.stake || 0), Number(info.totalAfter) || (Number(info.banked) || 0) + Number(info.payout || 0))}</span>` : ''}
      ${statTiles(p)}
      ${p.reason ? `<span class="play-reason">${esc(p.reason)}</span>` : ''}
      ${p.reasoning && p.reasoning.cautions && p.reasoning.cautions.length ? `<span class="play-meta">Watch out: ${esc(p.reasoning.cautions[0])}</span>` : ''}
      <span class="play-meta">${esc(when)}${stale && p.quotedAt ? ` · posted price captured ${esc(ago(p.quotedAt))} · check current price` : ''}</span>
      ${C.deliveryText(p) ? `<span class="play-meta">${esc(C.deliveryText(p))}</span>` : ''}
      <span class="play-actions">${route ? `<a class="play-action" href="${esc(route)}">${action} ›</a>` : ''}<button class="play-details" type="button" data-pick="${esc(p.id)}" aria-label="Pick details: ${esc(title)}">Research</button></span>
      </div>
    </details>`;
  };
  /* The one record (C.theRecord), the way the pick accounts keep it: wins and losses, and units at one unit a play
     at the line and price we published. The units are saved with each result, so they never move once graded. */
  const unitText = u => u == null ? DASH : `${signed(u, 2)}u`;
  const unitTone = u => u > 0.004 ? 'up' : u < -0.004 ? 'down' : '';
  const wl = t => `${t.wins}–${t.losses}${t.pushes ? `–${t.pushes}` : ''}`;
  const played = t => Boolean(t) && t.wins + t.losses + t.pushes > 0;
  const MARKS = { win: '✅', loss: '❌', push: '➖', void: '➖' };
  const dayName = day => {
    if (!day) return 'Last game day';
    if (day === C.dayOf(new Date().toISOString())) return 'Today';
    if (day === C.dayOf(new Date(Date.now() - 864e5).toISOString())) return 'Yesterday';
    const d = new Date(day + 'T12:00:00');
    return Date.now() - d.getTime() < 6 * 864e5 ? d.toLocaleDateString('en-US', { weekday: 'long' }) : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };
  /* The last ten graded plays as dots, oldest first, and a win streak worth a flame. */
  const formDots = picks => {
    const last = picks.filter(p => ['win', 'loss', 'push'].includes(p.result) && !C.isParlay(p) && !C.isUnpricedImport(p))
      .sort((a, b) => String(b.settledAt || b.kickoff || '').localeCompare(String(a.settledAt || a.kickoff || ''))).slice(0, 10).reverse();
    return last.length ? `<span class="dots" aria-label="Last ${last.length}: ${last.map(p => p.result).join(', ')}">${last.map(p => `<i class="dot dot-${p.result}"></i>`).join('')}</span>` : '';
  };
  const recordStrip = (rec, label, picks = []) => {
    const u = rec.season.units;
    const hot = rec.season.streak && rec.season.streak.result === 'win' && rec.season.streak.length >= 2 ? `<span class="streak">🔥 ${rec.season.streak.length} straight</span>` : '';
    return `<a class="record-strip" href="#record"><span class="eyebrow">${esc(label)}</span>
    <span class="num record-big">${wl(rec.season)}</span>${u == null ? '' : `<span class="num record-units ${unitTone(u)}">${unitText(u)}</span><span class="record-note">one unit a play</span>`}${hot}
    <span class="record-form">${formDots(picks)}<span class="row-meta">Every play graded, win or lose ›</span></span></a>`;
  };
  /* Three boxes, the money, then the Pick of the Day and the fun parlays on their own line. */
  const recordBoxes = rec => {
    const rate = t => t && t.hitRate != null ? `${Math.round(t.hitRate)}% won` : '';
    const last = rec.lastDay;
    const box = (label, t, note) => stat(label, played(t) ? wl(t) : DASH, note);
    return `<div class="stats record-boxes">
      ${box(dayName(last && last.day), last, last && last.pending ? `${last.pending} still to play` : rate(last))}
      ${box('This week', rec.week, played(rec.week) ? rate(rec.week) : 'nothing settled yet')}
      ${box('Season', rec.season, rate(rec.season))}</div>`;
  };
  const moneyLine = rec => {
    const u = rec.season.units;
    if (u == null) return '';
    const unpriced = rec.season.unpriced ? ` ${rec.season.unpriced} without a recorded price left out.` : '';
    const assumed = rec.assumed ? ` The ${rec.assumed} graded Week 1 play${rec.assumed === 1 ? '' : 's'} had no recorded price, so ${rec.assumed === 1 ? 'it counts' : 'they count'} at an assumed -115; voids do not affect the record.` : '';
    return `<p class="money-line">Units: <b class="num ${unitTone(u)}">${unitText(u)}</b> <span class="faint">every play at one unit, at the price we published.${esc(unpriced)}${esc(assumed)}</span></p>`;
  };
  const sideLines = rec => {
    const lines = [];
    if (played(rec.potd)) lines.push(`Pick of the Day <b class="num">${wl(rec.potd)}</b>`);
    if (played(rec.parlays)) lines.push(`Fun parlays <b class="num">${wl(rec.parlays)}</b>${rec.parlays.units == null ? '' : ` · <b class="num ${unitTone(rec.parlays.units)}">${unitText(rec.parlays.units)}</b>`} <span class="faint">(smaller stakes, not in the record)</span>`);
    return lines.length ? `<p class="side-lines">${lines.join('<br>')}</p>` : '';
  };
  const theRecordCard = rec => `<div class="card record-card">${recordBoxes(rec)}${moneyLine(rec)}${sideLines(rec)}</div>`;
  /* Five familiar results before the deep tables: model calls for spread, winner, total and player lines, then the
     separately labeled published fun tickets. This is accuracy, not a profit claim. */
  const scorecardCard = (board, picks) => {
    const score = C.projectionScorecard(board, picks, state.league);
    const record = row => `${row[0]}–${row[1]}${row[2] ? `–${row[2]}` : ''}`;
    const rate = row => row[0] + row[1] ? `${Math.round(100 * row[0] / (row[0] + row[1]))}% hit` : 'No results yet';
    const tile = (label, row, note) => `<div class="scorecard-item"><span class="scorecard-label">${esc(label)}</span>
      <strong class="num">${record(row)}</strong><span class="scorecard-rate">${rate(row)}</span><small>${esc(note)}</small></div>`;
    const coverage = [state.league === 'ALL' ? '' : leagueName(dataLeague()), score.games ? `${score.games} graded games` : '',
      score.updatedThrough ? `through ${dayLabel(score.updatedThrough)}` : ''].filter(Boolean).join(' · ');
    return `<div class="card scorecard-card"><div class="scorecard-head"><div><p class="eyebrow">Season scorecard</p>
      <p>Final pregame calls${coverage ? ` · ${esc(coverage)}` : ''}</p></div><a href="#model">Full scoreboard →</a></div>
      <div class="scorecard-grid">${tile('Spread', score.spread, 'vs closing spread')}${tile('Moneyline', score.moneyline, 'projected winners')}
        ${tile('Totals', score.total, 'vs closing total')}${tile('Player props', score.props, score.propsNote)}${tile('Parlays', score.parlays, 'published fun tickets')}</div>
      <p class="scorecard-foot">Pregame results. Parlays are tracked separately.</p></div>`;
  };
  /* The free community is the site's clearest next step: official plays arrive shortly before X, while the
     append-only record stays public here. Keep the claim precise and keep short-lived arb candidates separate. */
  const communityCard = (compact = false) => compact ? `<aside class="community-card community-card-compact card" aria-label="Join the Kook'n Discord">
    <div class="community-compact-copy"><p class="eyebrow">Free Kook'n Discord</p>
      <p>Official plays early. Fast Arb Radar alerts.</p></div>
    <a class="btn btn-primary community-join" href="https://discord.gg/CvNTUUSnNz" target="_blank" rel="noopener">Join Discord ↗</a>
  </aside>` : `<aside class="community-card card" aria-label="Join the Kook'n Discord">
    <div class="community-copy"><p class="eyebrow">Free Kook'n Discord</p><h2>The card lands here first.</h2>
      <p>Official plays and graphics arrive about 10–15 minutes before X. Time-sensitive Arb Radar candidates stay in Discord.</p>
      <div class="community-actions"><a class="btn btn-primary" href="https://discord.gg/CvNTUUSnNz" target="_blank" rel="noopener">Join the free Discord ↗</a><a class="btn" href="#record">See every result</a></div></div>
    <div class="community-proof" aria-label="What the community gets"><span><b>Early</b><small>official plays</small></span><span><b>Fast</b><small>arb alerts</small></span><span><b>Public</b><small>win-or-lose record</small></span></div>
  </aside>`;
  const ladderStatus = L => {
    const open = L.open, info = (open && open.ladder) || {}, last = L.history[L.history.length - 1];
    if (open) return `Step ${info.step || L.step} is live`;
    if (last && last.result === 'win') return `Step ${(last.ladder || {}).step || L.step - 1} cashed · Step ${L.step} is being checked · not posted yet`;
    if (last && last.result === 'loss') return `The last climb ended · Step 1 is being checked · not posted yet`;
    return L.history.length ? `Step ${L.step} is being checked · not posted yet` : 'The first rung waits for two clean games';
  };
  const ladderRows = (L, limit = 8) => L.history.slice().reverse().slice(0, limit).map(r => {
    const info = r.ladder || {}, total = r.ladderTotal || {};
    const paid = r.result === 'win' ? money(info.payout) : r.result === 'loss' ? '$0' : money(info.stake);
    return `<button class="row" type="button" data-pick="${esc(r.id)}">
      <span class="row-main"><span class="row-top"><span class="row-name">${MARKS[r.result] || '•'} Step ${esc(info.step || '')}</span><span class="row-meta">${esc(whenShort(r.kickoff || r.publishedAt))}</span></span>
      <span class="row-meta ladder-lines">${esc((r.legs || []).map(l => l.title).filter(Boolean).join(' · '))}</span></span>
      <span class="row-price"><span class="row-odds num ${r.result === 'win' ? 'up' : r.result === 'loss' ? 'down' : ''}">${esc(money(info.stake))} → ${esc(paid)}</span><span class="row-book">${r.result === 'win' ? `bank +${esc(money(rungMoney(info).bankThisWin))}` : `${esc(r.book || '')} ${esc(odds(r.odds))}`}</span>
      <span class="row-meta ladder-running ${Number(total.net) > 0 ? 'up' : Number(total.net) < 0 ? 'down' : ''}">Running ${esc(signedMoney(total.net))}</span></span></button>`;
  }).join('');
  const ladderLedger = L => {
    const a = L.accounting || {}, record = `${Number(a.wins) || 0}–${Number(a.losses) || 0}${a.pushes ? `–${a.pushes}` : ''}`;
    return `<div class="ladder-ledger" aria-label="All-time ladder totals">
      <span><small>Rungs</small><b class="num">${esc(record)}</b></span>
      <span><small>Settled stake</small><b class="num">${money(a.wagered)}</b></span>
      <span><small>Returned</small><b class="num">${money(a.returned)}</b></span>
      <span><small>Net</small><b class="num ${Number(a.net) > 0 ? 'up' : Number(a.net) < 0 ? 'down' : ''}">${esc(signedMoney(a.net))}</b></span>
      ${a.atRisk ? `<span class="ladder-live"><small>Live now</small><b class="num">${money(a.atRisk)}</b></span>` : ''}
    </div>`;
  };
  const ladderHistory = L => {
    const rows = ladderRows(L);
    return rows ? `<details class="ladder-history"><summary>Past steps <span>${L.history.length} · ${esc(signedMoney((L.accounting || {}).net))} overall</span></summary><div class="rows ladder-rows">${rows}</div></details>` : '';
  };
  /* The ladder in one compact block near the top, so a phone sees what cashed, what is next and the past lines. */
  const ladderStrip = L => {
    const open = L.open, info = (open && open.ladder) || {};
    const riding = Number(open ? info.stake : L.stake), banked = Number(open ? info.banked : L.banked) || 0;
    const text = `${ladderStatus(L)} · ${money(banked)} banked`;
    const after = open ? Number(info.totalAfter) || banked + Number(info.payout || 0) : banked + riding;
    return `<div class="record-strip ladder-strip"><span class="eyebrow">🪜 80/20 Climb · climb ${esc(L.run)}</span>
      <span class="num record-big ladder-big">${money(riding)}</span><span class="record-note">${esc(text)}</span>
      <span class="ladder-bar">${ladderBar(banked + riding, after)}</span>${ladderLedger(L)}${ladderHistory(L)}</div>`;
  };
  /* The Kook'n 80/20 Climb (C.theLadder): where the bankroll ladder stands, its bank, and the rungs played so far. */
  const ladderCard = L => {
    const open = L.open, info = (open && open.ladder) || {};
    const riding = Number(open ? info.stake : L.stake), banked = Number(open ? info.banked : L.banked) || 0;
    const status = `${ladderStatus(L)} · ${money(banked)} banked`;
    const best = L.climbs.length ? Math.max(...L.climbs.map(c => c.final)) : null;
    return `<div class="card ladder-card">
      <div class="ladder-head"><span class="ladder-title">🪜 The Kook’n 80/20 Climb</span><span class="pill pill-ladder">Climb ${esc(L.run)}</span></div>
      <p class="ladder-pitch">Bank 20% of every winning return. Ride 80%. A miss cannot take the bank.</p>
      <div class="ladder-now-line"><b class="num">${money(riding)} ${open ? 'riding' : 'next stake'}</b><span>${esc(status)}</span></div>
      <span class="ladder-bar">${ladderBar(banked + riding, open ? Number(info.totalAfter) || banked + Number(info.payout || 0) : banked + riding)}</span>
      ${ladderLedger(L)}
      ${ladderHistory(L)}
      <p class="row-meta ladder-note">${L.climbs.length ? `Climbs finished: ${L.climbs.length}, best ${money(best)}. ` : ''}${L.saved ? `${money(L.saved)} banked across wins. ` : ''}Bank 20%. Ride 80%. A loss cannot touch the bank.</p>
    </div>`;
  };
  const external = (url, label) => /^https:\/\//.test(url || '') ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : '';
  const espnGame = id => { const [league, event] = String(id).split('-'); return `https://www.espn.com/${league === 'CFB' ? 'college-football' : 'nfl'}/game/_/gameId/${event}`; };

  const hasLean = game => { const lean = C.leanText(game); return Boolean(game.fcs || (lean && (lean.side || lean.total))); };
  /* Same colors as the board: green only on a solid sample, amber for a thin one or a small gap. */
  const leanChips = (game, strong = 3) => {
    if (game.fcs) return '<span class="row-meta">FBS vs FCS: our number is not reliable here</span>';
    const lean = C.leanText(game);
    if (!lean || (!lean.side && !lean.total)) return '<span class="row-meta">no model call</span>';
    const thin = Boolean((game.v2 || {}).sparse);
    const m = game.market || {}, raw = game.lean || {};
    const pct = c => c == null ? '' : ` · ${Math.round(100 * c)}%`;
    const chip = (text, chance, caution) => `<span class="lean ${C.leanTone(chance, thin)}">${esc(text)}${caution ? ' · higher bar' : ''}</span>`;
    const sideTeam = raw.side === 'home' ? game.home : game.away;
    const sideLine = m.spread == null ? '' : ` ${C.spreadText('', raw.side === 'home' ? m.spread : -m.spread).trim()}`;
    const side = lean.side ? chip(`Our side: ${teamName(sideTeam)}${sideLine}${pct(lean.side.chance)}`, lean.side.chance, raw.spreadCaution) : '';
    const total = lean.total ? chip(`Our total: ${lean.total.direction} ${m.total ?? ''}${pct(lean.total.chance)}`, lean.total.chance, raw.totalCaution) : '';
    return `<span class="leans">${side}${total}</span>`;
  };

  /* Once a game kicks off the real score is the headline number and the forecast moves to the small line. */
  /* One game as a projection card, the way the projection posts lay it out: both teams with their logos, our
     projected score big in the middle with the total and kickoff, our win probability as a bar in the teams'
     colours, and our spread and total against the market's with the side our number likes. Once a game starts the
     real score takes the middle and ours moves to the small line. Names wrap under their logos, never cut off. */
  const LOGO = { CFB: t => `https://a.espncdn.com/i/teamlogos/ncaa/500/${encodeURIComponent(t.id)}.png`,
    NFL: t => `https://a.espncdn.com/i/teamlogos/nfl/500/${encodeURIComponent(String(t.abbr || '').toLowerCase())}.png` };
  const DULL = '#64748b';
  const inkOn = hex => { const m = /^#?([0-9a-f]{6})$/i.exec(hex || ''); if (!m) return '#fff';
    const n = parseInt(m[1], 16); return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255 > 0.6 ? '#0a0d13' : '#fff'; };
  const projTeam = (game, team, showRanks = false) => {
    const rank = showRanks && team.strength;
    const ranks = rank ? `<span class="proj-ranks" title="Current ${esc(leagueName(game.league))} model rank out of ${rank.teams}; No. 1 is strongest"><span>OFF <b>#${rank.offense}</b></span><span>DEF <b>#${rank.defense}</b></span></span>` : '';
    return `<span class="proj-team">${LOGO[game.league] && team.id ? `<img class="proj-logo" src="${esc(LOGO[game.league](team))}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : '<span class="proj-logo"></span>'}
      <span class="proj-name">${esc(teamName(team))}</span><span class="proj-abbr">${esc(team.abbr || '')}</span>${ranks}</span>`;
  };
  const projCard = (game, showRanks = false) => {
    const v2 = game.v2, m = game.market || {}, raw = game.lean || {};
    const final = game.completed, live = !final && game.state === 'in';
    const scores = (final || live) && game.away.score != null && game.home.score != null;
    const label = final ? 'Final' : live ? 'Live' : 'Projected';
    const score = scores ? `${game.away.score}<span class="faint"> – </span>${game.home.score}`
      : v2 ? `${fixed(v2.away, 1)}<span class="faint"> – </span>${fixed(v2.home, 1)}` : DASH;
    const total = scores ? (v2 ? `we had ${fixed(v2.away, 0)}–${fixed(v2.home, 0)}` : '') : v2 && v2.total != null ? `Total ${fixed(v2.total, 1)}` : 'no number yet';
    const home = typeof (v2 || {}).winProb === 'number' ? v2.winProb : null;
    /* The teams' own colours; a near-black one uses its alternate so the bar shows on the dark card. */
    const light = hex => { const m = /^#?([0-9a-f]{6})$/i.exec(hex || ''); if (!m) return 0; const n = parseInt(m[1], 16);
      return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255; };
    const pickColor = t => { const c = (t.color || '').toLowerCase(); return c && light(c) < 0.1 && t.alt && light(t.alt) < 0.9 ? t.alt : c; };
    let colors = [pickColor(game.away), pickColor(game.home)];
    if (colors.some(c => !c || c === DULL || light(c) < 0.1) || colors[0] === colors[1]) colors = ['#38bdf8', '#5eeaa4'];
    const bar = home == null || game.fcs ? '' : `<span class="proj-bar" role="img" aria-label="Estimated win probability: ${esc(teamName(game.away))} ${100 - Math.round(100 * home)}%, ${esc(teamName(game.home))} ${Math.round(100 * home)}%">
        <span style="width:${(100 * (1 - home)).toFixed(1)}%;background:${esc(colors[0])};color:${inkOn(colors[0])}">${100 - Math.round(100 * home)}%</span><span style="width:${(100 * home).toFixed(1)}%;background:${esc(colors[1])};color:${inkOn(colors[1])}">${Math.round(100 * home)}%</span></span>
      <span class="proj-bar-labels"><span>${esc(game.away.abbr || '')}</span><span>Estimated win chance</span><span>${esc(game.home.abbr || '')}</span></span>`;
    const lean = C.leanText(game) || {};
    const fav = spread => spread == null ? DASH : Math.abs(spread) < 0.05 ? 'Pick' : `${esc((spread < 0 ? game.home : game.away).abbr)} -${Math.abs(spread)}`;
    const ours = v2 && v2.margin != null ? (Math.abs(v2.margin) < 0.05 ? 'Even' : `${esc((v2.margin > 0 ? game.home : game.away).abbr)} by ${Math.abs(v2.margin).toFixed(1)}`) : DASH;
    const sideTeam = raw.side === 'home' ? game.home : game.away;
    const sideLine = m.spread == null ? '' : ` ${C.spreadText('', raw.side === 'home' ? m.spread : -m.spread).trim()}`;
    const pick = (text, chance, caution) => chance == null ? '<span class="faint">no lean</span>'
      : `<span class="lean ${C.leanTone(chance, Boolean((v2 || {}).sparse))}">${text} · ${Math.round(100 * chance)}%${caution ? ' · higher bar' : ''}</span>`;
    const lines = scores || game.fcs || !v2 ? '' : `<span class="proj-lines">
        <span class="proj-line proj-line-head"><span></span><span>Ours</span><span>Line</span><span>Our side</span></span>
        <span class="proj-line"><span>Spread</span><span>${ours}</span><span>${fav(m.spread)}</span><span>${lean.side ? pick(`${esc(sideTeam.abbr)}${esc(sideLine)}`, lean.side.chance, raw.spreadCaution) : '<span class="faint">no lean</span>'}</span></span>
        <span class="proj-line"><span>Total</span><span>${v2.total != null ? fixed(v2.total, 1) : DASH}</span><span>${m.total ?? DASH}</span><span>${lean.total ? pick(`${lean.total.direction} ${m.total ?? ''}`, lean.total.chance, raw.totalCaution) : '<span class="faint">no lean</span>'}</span></span>
      </span>`;
    return `<a class="proj${live ? ' proj-live' : ''}" href="#game/${esc(game.id)}">
      <span class="proj-top">${projTeam(game, game.away, showRanks)}
        <span class="proj-mid"><span class="proj-label">${label}</span><span class="proj-score num">${score}</span><span class="proj-total">${esc(total)}</span>
          <span class="proj-when">${esc(whenShort(game.kickoff))}</span></span>
        ${projTeam(game, game.home, showRanks)}</span>
      ${game.fcs ? '<span class="proj-note">FBS vs FCS: our number is not reliable here</span>' : bar}${lines}
      ${!scores && C.modelCaution(game) ? `<span class="proj-note">${esc(C.modelCaution(game))}</span>` : ''}
    </a>`;
  };
  const projGrid = (games, showRanks = false) => `<div class="projs">${games.map(game => projCard(game, showRanks)).join('')}</div>`;

  const gameRow = game => {
    const m = game.market || {}, v2 = game.v2, v1 = game.v1;
    const final = game.completed;
    const started = final || game.state === 'in';
    const scores = started && game.away.score != null && game.home.score != null;
    const forecast = v2 ? `${fixed(v2.away, 0)}–${fixed(v2.home, 0)}` : v1 ? `${v1.away}–${v1.home}` : DASH;
    const model = v2 ? `our score · ${esc(ourMargin(game, v2.margin))}` : v1 ? 'first model only' : 'no number yet';
    return `<a class="game-row" href="#game/${esc(game.id)}">
      <span class="game-teams">${teamRow(game.away, scores ? game.away.score : null)}${teamRow(game.home, scores ? game.home.score : null)}</span>
      <span class="game-mid">${esc(whenShort(game.kickoff))}${final ? ' · <b>Final</b>' : started ? ' · <b class="live">In play</b>' : ''}${started && m.spread == null && m.total == null ? '' : `<br>
        Line <b>${m.spread != null ? esc(`${teamName(game.home)} ${C.spreadText('', m.spread).trim()}`) : DASH}</b> · <b>${m.total != null ? 'Total ' + esc(m.total) : 'no total'}</b>`}</span>
      <span class="game-model"><span class="num">${scores ? `${game.away.score}–${game.home.score}` : forecast}</span><div class="row-meta">${scores ? (v2 || v1 ? `we had ${esc(forecast)}` : 'no number') : model}</div></span>
      ${!started && hasLean(game) ? `<span class="game-leans">${leanChips(game)}</span>` : ''}
    </a>`;
  };

  const pickRow = pick => {
    const tone = pick.result === 'win' ? 'var(--green)' : pick.result === 'loss' ? 'var(--rose)' : 'var(--mint)';
    return `<button class="row" type="button" data-pick="${esc(pick.id)}">
      <span class="row-rail" style="background:${pick.result ? tone : esc(pick.color || 'var(--mint)')}"></span>
      <span class="row-main"><span class="row-top">${avatar(pick, 'ava-row')}<span class="row-name">${pick.result && MARKS[pick.result] ? MARKS[pick.result] + ' ' : ''}${esc(pick.displayTitle || pick.title || pick.player)}</span>
        ${pick.favorite ? '<span class="pill pill-ours">Favorite</span>' : ''}${pick.modelLean ? '<span class="pill pill-reference">Model pick</span>' : ''}${pick.earlyExit ? '<span class="pill pill-closed">Early exit credit</span>' : ''}${C.isLongshot(pick) ? '<span class="pill pill-stale">Longshot</span>' : ''}${pick.historicalImport ? '<span class="pill pill-reference">Imported</span>' : ''}
        <span class="pill pill-${playState(pick).st.tone}">${esc(playState(pick).st.word)}</span></span>
        <span class="row-market">${pick.actual ? esc(pick.actual) : (pick.legs || []).length ? `${pick.legs.length} legs` : numberText(pick) ? esc(numberText(pick)) : pick.projection != null ? 'We project ' + esc(pick.projection) : ''}</span>
        <span class="row-meta">${esc(whenShort(pick.kickoff || pick.publishedAt))}${pick.quotedAt ? ' · price from ' + esc(ago(pick.quotedAt)) : ''}</span></span>
      ${pick.odds == null && pick.historicalImport ? '<span class="row-price"><span class="row-book">price not recorded</span></span>'
        : `<span class="row-price"><span class="row-odds num">${odds(pick.odds)}</span><span class="row-book">${esc(pick.book || 'No book')}</span></span>`}
    </button>`;
  };

  /* ---------- today ---------- */

  const upcoming = games => games.filter(g => !g.completed && g.state === 'pre').sort((a, b) => a.kickoff.localeCompare(b.kickoff));
  const slate = games => {
    const rows = upcoming(games);
    if (!rows.length) return rows;
    const cutoff = Date.parse(rows[0].kickoff) + 72 * 3600 * 1000;
    return rows.filter(g => Date.parse(g.kickoff) <= cutoff);
  };
  const disagreement = g => Math.max(Math.abs((g.lean || {}).spread || 0), Math.abs((g.lean || {}).total || 0));

  /* The board's best priced reads for the day, or the next day with lines: the Today page's opener. */
  const bestOnBoard = board => {
    /* Only lines our number actually leans on; a list called "we like" never shows a no-edge row. */
    const rows = ((board || {}).lines || []).filter(inLeague)
      .filter(l => l.state === 'open' && l.grade && ['lean', 'strong'].includes(C.tierOf(l.grade)) && Date.parse(l.kickoff) > Date.now());
    if (!rows.length) return { rows: [], games: [], players: [], day: null };   // every caller reads all three lists
    const todayLabel = dayLabel(new Date().toISOString());
    const soonest = rows.slice().sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0];
    const day = rows.some(l => dayLabel(l.kickoff) === todayLabel) ? todayLabel : dayLabel(soonest.kickoff);
    const onDay = C.rankConfidence(rows.filter(l => dayLabel(l.kickoff) === day).sort(C.byGrade));
    return { rows: onDay.slice(0, 6), games: onDay.filter(l => !l.athleteId).slice(0, 4), players: onDay.filter(l => l.athleteId).slice(0, 4),
      day: day === todayLabel ? null : day };
  };

  /* Where the market has moved from its opening number, biggest first, and whether it moved toward our number. */
  const lineMoves = games => {
    const now = Date.now();
    const out = [];
    for (const g of games) {
      if (g.completed || g.state !== 'pre' || Date.parse(g.kickoff) <= now) continue;
      const m = g.market || {}, lean = g.lean || {};
      if (m.spread != null && m.spreadOpen != null && Math.abs(m.spread - m.spreadOpen) >= 1) {
        const towardAway = m.spread > m.spreadOpen;
        out.push({ game: g, size: Math.abs(m.spread - m.spreadOpen), agrees: lean.side ? (lean.side === 'away') === towardAway : null,
          text: `${teamName(g.home)} went from ${C.spreadText('', m.spreadOpen).trim()} to ${C.spreadText('', m.spread).trim()}`, note: `the line moved toward ${teamName(towardAway ? g.away : g.home)}` });
      }
      if (m.total != null && m.totalOpen != null && Math.abs(m.total - m.totalOpen) >= 1) {
        const down = m.total < m.totalOpen;
        out.push({ game: g, size: Math.abs(m.total - m.totalOpen), agrees: lean.total != null && lean.total !== 0 ? (lean.total < 0) === down : null,
          text: `Total went from ${m.totalOpen} to ${m.total}`, note: down ? `down ${(m.totalOpen - m.total).toFixed(1).replace(/\.0$/, '')}` : `up ${(m.total - m.totalOpen).toFixed(1).replace(/\.0$/, '')}` });
      }
    }
    return out.sort((a, b) => b.size - a.size).slice(0, 6);
  };
  const moveRow = mv => `<div class="row" style="cursor:default"><span class="row-rail" style="background:${mv.agrees === true ? 'var(--green)' : mv.agrees === false ? 'var(--amber)' : 'var(--line)'}"></span>
      <span class="row-main"><span class="row-top">${avatar({ gameId: mv.game.id }, 'ava-row')}<span class="row-name"><a href="#game/${esc(mv.game.id)}">${esc(teamName(mv.game.away))} at ${esc(teamName(mv.game.home))}</a></span></span>
        <span class="row-market">${esc(mv.text)} · ${esc(mv.note)}</span>
        <span class="row-meta">${esc(whenShort(mv.game.kickoff))}${mv.agrees === true ? ' · moved toward our number' : mv.agrees === false ? ' · moved away from our number' : ''}</span></span></div>`;
  /* Picks settled in the last day and a half, newest first: the morning-after scorecard. */
  const lastGameDay = picks => picks.filter(p => p.result && p.settledAt && !p.historicalImport && Date.now() - Date.parse(p.settledAt) < 40 * 3600 * 1000)
    .sort((a, b) => String(b.settledAt).localeCompare(String(a.settledAt)));

  const currentUpset = game => game.upsetWatch && game.state === 'pre' && !game.completed &&
    Date.parse(game.kickoff) > Date.now() && Date.now() >= Date.parse(game.upsetWatch.observedAt) &&
    Date.now() - Date.parse(game.upsetWatch.observedAt) <= 4 * 3600000;
  const upsetRow = (game, rank = null) => {
    const w = game.upsetWatch;
    const reasons = (w.reasons || []).slice(0, 4);
    const warnings = w.warnings || ['Check the current price, weather and lineup news.'];
    return `<a class="row upset-row" href="#game/${esc(game.id)}"><span class="row-main"><span class="row-top"><span class="row-name">${esc(w.team)} · ${odds(w.odds)} ML</span>${rank === 1 ? '<span class="pill pill-upset">Top upset signal</span>' : rank ? `<span class="pill pill-reference">#${rank} upset signal</span>` : ''}</span>
      <span class="row-market">Our chance ${C.pct(w.modelChance)} · market ${C.pct(w.marketChanceNoVig)}</span>
      ${reasons.length ? `<span class="upset-why"><b>Why</b>${reasons.map(reason => `<span>• ${esc(reason)}</span>`).join('')}</span>` : ''}
      <span class="row-meta">${esc(whenShort(game.kickoff))} · ${esc(w.book)} · opposing ML ${odds(w.opponentOdds)} · captured ${esc(ago(w.observedAt))}</span>
      <span class="row-meta upset-warning">${warnings.map(esc).join(' · ')}</span></span></a>`;
  };
  const underdogSpreads = board => {
    const rows = ((board || {}).lines || []).filter(inLeague).filter(line => {
      const grade = line.grade || {};
      return line.gameMarket && line.market === 'point spread' && Number(line.line) > 0 && line.state === 'open' &&
        ['lean', 'strong'].includes(C.tierOf(grade)) && Date.parse(line.kickoff) > Date.now();
    });
    if (!rows.length) return [];
    const nextDay = dayLabel(rows.slice().sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0].kickoff);
    return C.rankConfidence(rows.filter(line => dayLabel(line.kickoff) === nextDay).sort(C.byGrade)).slice(0, 4);
  };
  const underdogWatch = (games, board) => {
    const outright = games.filter(currentUpset)
      .sort((a, b) => ((b.upsetWatch.modelChance - b.upsetWatch.marketChanceNoVig) - (a.upsetWatch.modelChance - a.upsetWatch.marketChanceNoVig)))
      .slice(0, 4);
    const spreads = underdogSpreads(board);
    const block = (title, note, body) => `<div class="card underdog-block"><div class="section-head"><div><p class="eyebrow">${esc(title)}</p><p class="row-meta">${esc(note)}</p></div></div>${body}</div>`;
    return section('Underdog Watch',
      `<p class="row-meta" style="margin:0 0 8px">Outright upsets and spread covers are listed separately.</p>` +
      block('Outright upset candidates', 'Moneyline outlook.',
        outright.length ? `<div class="rows">${outright.map((game, index) => upsetRow(game, index + 1)).join('')}</div>` : empty('No fresh outright candidate', 'No underdog stands out at the current price.')) +
      block('Underdog spread value', 'Covering does not mean winning outright.',
        spreads.length ? `<div class="rows">${spreads.map(lineRow).join('')}</div>` : empty('No spread highlighted', 'No underdog spread stands out at the current price.')),
      '<a href="#games">All games →</a>');
  };
  const matchupResearch = (card, detail) => {
    if (!detail || card.state !== 'pre' || Date.parse(card.kickoff) <= Date.now()) return '';
    const trendKeys = new Set();
    const trends = C.filterTrends(detail.seasonTrends || [], { rate: 80, min: 3 }).filter(l => {
      const key = `${l.athleteId}/${l.stat}`;
      if (trendKeys.has(key)) return false;
      trendKeys.add(key); return true;
    }).slice(0, 6);
    const scorers = (detail.scorerResearch || []).filter(s => {
      const age = Date.now() - Date.parse(s.roleSnapshotAt);
      return age >= 0 && age <= 7 * 86400000;
    });
    return (currentUpset(card) ? section('Upset Watch · research', `<div class="card">${upsetRow(card)}</div>`) : '') +
      section('Matchup trends', trends.length ? `<div class="card"><div class="rows">${trends.map(l =>
        `<a class="row" href="#player/${esc(card.league)}/${esc(l.athleteId)}"><span class="row-main"><span class="row-name">${esc(l.player)} · ${esc(l.title)}</span>
          <span class="row-market">${l.hits}/${l.games} this season · ${l.rate}%${l.games < 5 ? ' · small sample' : ''}</span>
          <span class="row-meta">${l.kind === 'milestone' ? 'Stat milestone' : `${odds(l.odds)} ${esc(l.book)}`}</span></span></a>`).join('')}</div></div>`
        : '<p class="row-meta">No 80% trends with at least three games.</p>') +
      section('Touchdown watch', `<p class="row-meta">Red-zone and inside-the-10 opportunities this season. Verify the latest availability.</p>` +
        (scorers.length ? `<div class="card"><div class="rows">${scorers.map(s => `<a class="row" href="#player/${esc(card.league)}/${esc(s.athleteId)}"><span class="row-main"><span class="row-name">${esc(s.player)}</span>
          <span class="row-market">${s.redZone} red-zone carries + targets · ${s.inside10} inside the 10 · ${s.touchdowns} rushing/receiving TDs</span>
          <span class="row-meta">${s.touchdowns} TDs · ${s.games} games tracked · ${esc(s.priceStatus)}</span></span></a>`).join('')}</div></div>`
        : empty('No touchdown watch yet', 'Not enough recent usage is available.'))) +
      `<div class="card menu"><a href="#trends/${esc(card.id)}"><span>Season trends →</span><small>70 / 80 / 90 / 100% · main lines and alternates</small></a></div>`;
  };

  async function viewToday() {
    const [data, board, scoreboard] = await Promise.all([get('app/today.json'), maybe('app/lines.json'), maybe('scoreboard.json')]);
    markPicks(data.picks.filter(inLeague).filter(p => !p.result && !p.historicalImport));
    const settledRecently = lastGameDay(data.picks.filter(inLeague));
    const recent = C.summaryOf(settledRecently.filter(p => !C.isParlay(p) && !C.isUnpricedImport(p)));
    const liveNow = await liveFootball(data.games.filter(inLeague));
    const games = liveNow.games;
    const best = bestOnBoard(board);
    const now = slate(games);
    const playing = games.filter(g => !g.completed && g.state === 'in');
    const first = now[0];
    const picks = data.picks.filter(inLeague);
    const live = picks.filter(p => !p.result && !p.historicalImport)
      .sort((a, b) => (Boolean(b.featured) - Boolean(a.featured)) || (C.isOpen(b) - C.isOpen(a)) || String(a.kickoff).localeCompare(String(b.kickoff)));
    const todayLabel = dayLabel(new Date().toISOString());
    const title = !first ? 'No games scheduled' : dayLabel(first.kickoff) === todayLabel ? todayLabel : `Next slate: ${dayLabel(first.kickoff)}`;
    gameIndex = new Map(games.map(g => [g.id, g]));
    const ladder = C.theLadder(data.picks);
    /* The Climb is its own top-level feature. Removing it from the ordinary schedule prevents duplicate cards. */
    const scheduled = C.cardSchedule(live.filter(p => !C.isLadder(p)));
    const todayGames = games.filter(g => C.dayOf(g.kickoff) === C.dayOf(new Date().toISOString()));
    return `${head('Today', `${esc(todayLabel)} · ${todayGames.length} game${todayGames.length === 1 ? '' : 's'}${state.league === 'ALL' ? '' : ` · ${esc(leagueName(state.league))}`}. Plays and top lines, all in one place.`)}
      ${liveStamp(liveNow.refreshed)}
      ${boardTabs('card')}
      ${section('The 80/20 Climb', ladder.open ? `<div class="plays plays-ladder">${playCard(ladder.open)}</div>${ladderLedger(ladder)}${ladderHistory(ladder)}` : ladderStrip(ladder), '<a href="#record">Climb record →</a>')}
      ${scorecardCard(scoreboard || {}, data.picks)}
      ${section("Today's plays", scheduled.today.length ? `<div class="plays">${scheduled.today.map(playCard).join('')}</div>`
        : empty('Nothing posted yet', 'New plays appear here when they are released.'), '<a href="#record">Every result →</a>')}
      ${scheduled.upcoming.length ? `<details class="card upcoming-card"><summary>Upcoming official plays · ${scheduled.upcoming.length}<span>Separate from today’s card</span></summary><div class="plays">${scheduled.upcoming.map(playCard).join('')}</div></details>` : ''}
      ${scheduled.awaiting.length ? `<details class="card upcoming-card"><summary>Awaiting settlement · ${scheduled.awaiting.length}</summary><div class="plays">${scheduled.awaiting.map(playCard).join('')}</div></details>` : ''}
      <div class="two-col"><div>
        <div class="research-heading"><p class="eyebrow">More to explore</p><h2>Lines and trends</h2><p>Game lines, player props and matchup trends.</p></div>
        ${underdogWatch(now, board)}
        ${best.games.length ? section(best.day ? `Game lines · ${esc(best.day)}` : 'Game lines',
          `<div class="card"><div class="rows">${best.games.map(lineRow).join('')}</div></div>`,
          '<a href="#board">All game lines →</a>') : ''}
        ${best.players.length ? section(best.day ? `Player props · ${esc(best.day)}` : 'Player props',
          `<div class="card"><div class="rows">${best.players.map(lineRow).join('')}</div></div>`,
          '<a href="#board/props">All player props →</a>') : ''}
        ${!best.rows.length ? empty('No highlighted lines right now', 'Browse every available line and projection.', '<a class="btn" href="#board">View game lines</a>') : ''}
        ${playing.length ? section(`In play now${playing.length > 6 ? ` (${playing.length})` : ''}`, projGrid(playing.slice(0, 6)), '<a href="#games">All games →</a>') : ''}
        ${settledRecently.length ? `<details class="card upcoming-card recent-results"><summary>Last game day · ${played(recent) ? wl(recent) : 'parlays only'}${recent.units == null ? '' : ` · ${unitText(recent.units)}`}<span><a href="#record">Full record →</a></span></summary><div class="rows">${settledRecently.map(pickRow).join('')}</div></details>` : ''}
      </div><div>
        ${communityCard(true)}
        <nav class="discovery" aria-label="Explore Kook'n"><a href="#scores/MLB"><b>Scores</b><small>7 leagues</small></a><a href="#lab"><b>Kook'n Lab</b><small>What is being tested</small></a><a href="#arbs"><b>Arb Radar</b><small>Calculator and rules</small></a></nav>
      </div></div>`;
  }

  const modelCard = model => {
    const rows = ((model || {}).live || []).filter(inLeague);
    const back = ((model || {}).backtest || []).filter(inLeague).filter(r => r.model !== 'v1 replay' && r.season === 2025);
    const line = r => { const winners = r.summary.winner || [0, 0, 0], decided = winners[0] + winners[1], hit = decided ? Math.round(100 * winners[0] / decided) + '%' : DASH; return `<div class="row" style="cursor:default"><span class="row-main"><span class="row-top"><span class="row-name">${esc(leagueName(r.league))} ${esc(modelName(r.model))}</span><span class="row-meta">${esc(r.season)}${r.backtest ? ' backtest' : ' live'}</span></span>
      <span class="row-market"><b>Projected winners ${winners[0]}–${winners[1]}${winners[2] ? `–${winners[2]}` : ''} · ${hit} right</b></span>
      <span class="row-market">Missed the final margin by ${fixed(r.summary.marginMiss)} points a game; the closing line missed by ${fixed(r.summary.closeMarginMiss)} · against the closing line ${r.summary.side[0]}–${r.summary.side[1]}</span>
      <span class="row-meta">${r.summary.games} graded games · projected winners are separate from posted bets</span></span></div>`; };
    return `<div class="card"><div class="rows">${rows.map(line).join('') || '<div class="row" style="cursor:default"><span class="row-main"><span class="row-name">No live grades yet</span><span class="row-meta" style="display:block">Forecasts are graded once their games finish.</span></span></div>'}
      ${back.map(r => line({ ...r, backtest: true })).join('')}</div></div>`;
  };

  const freshnessCard = data => {
    const f = data.freshness || {};
    const item = (label, iso) => `<div><span>${esc(label)}</span><strong style="font-size:12px">${esc(ago(iso))}</strong></div>`;
    return `<div class="card" style="padding:12px"><div class="kv">${item('Schedule & lines', f.slate)}${item('Box scores', f.boxscores)}${item('Model', f.forecasts)}${item('Injuries', f.injuries)}${item('Prop lines', f.props)}</div>
      ${(data.health || []).filter(h => h.status !== 'current').map(h => `<p class="row-meta">${esc(h.component)}: ${esc(h.status)} at build. ${esc(h.fallback)}</p>`).join('')}
      <p class="row-meta" style="margin:10px 2px 0">Hosted refreshes run through the day and can run late. These are the latest successful checks, not a live feed.</p></div>`;
  };

  /* ---------- games ---------- */

  async function viewGames() {
    const data = await get('app/today.json');
    const liveNow = await liveFootball(data.games.filter(inLeague));
    let games = liveNow.games;
    /* Upcoming keeps games that have kicked off but are not final, or they would show up nowhere. */
    games = state.gamesScope === 'final' ? games.filter(g => g.completed).sort((a, b) => b.kickoff.localeCompare(a.kickoff))
      : games.filter(g => !g.completed).sort((a, b) => a.kickoff.localeCompare(b.kickoff));
    const gq = state.gamesQuery.trim().toLowerCase();
    if (gq) games = games.filter(g => [g.home.abbr, g.home.name, g.away.abbr, g.away.name].some(v => String(v || '').toLowerCase().includes(gq)));
    const groups = new Map();
    for (const g of games) { const day = dayLabel(g.kickoff); if (!groups.has(day)) groups.set(day, []); groups.get(day).push(g); }
    gameIndex = new Map(data.games.map(g => [g.id, g]));
    return `${head('Games', 'Scores, projections, lines and team strength. No. 1 is strongest.')}${liveStamp(liveNow.refreshed)}
      <div class="toolbar">${seg('gamesScope', [['upcoming', 'Upcoming'], ['final', 'Recent finals']], state.gamesScope)}</div>
      <input class="search" type="search" data-input="gamesQuery" placeholder="Find a team" value="${esc(state.gamesQuery)}" aria-label="Find a team">
      ${games.length ? [...groups].map(([day, rows]) => section(day, projGrid(rows, true))).join('')
        : empty(gq ? 'No game matches' : state.gamesScope === 'final' ? 'No recent finals' : 'No upcoming games', gq ? 'Try a team abbreviation or name.' : 'Nothing in this league inside the current window.')}`;
  }

  /* ---------- one game ---------- */

  const modelReadsSection = (card, detail) => {
    if (!detail) return '';
    const archived = card.completed || card.state !== 'pre' || Date.parse(card.kickoff) <= Date.now();
    const reads = detail.modelReads || [];
    if (!reads.length) return '';
    const render = line => {
      const history = line.history && line.history.season;
      const fresh = Date.now() - Date.parse(line.observedAt) >= 0 && Date.now() - Date.parse(line.observedAt) <= 4 * 3600000;
      const price = archived ? 'Pregame comparison · not a live line' : fresh && line.odds != null ? `${C.odds(line.odds)} ${line.book || ''}` : 'Check current price';
      const warnings = line.warnings || [];
      return `<article class="card model-read"><span class="eyebrow">${archived ? 'Pregame line' : line.performanceCaution ? 'Line to consider · caution' : 'Line to consider'}</span>
        <h3>${line.athleteId ? `<a href="#player/${esc(card.league)}/${esc(line.athleteId)}">${esc(line.title)} →</a>` : esc(line.title)}</h3>
        <p class="model-read-comparison">${esc(line.comparison)}</p>
        <p class="row-meta">${esc(price)} · ${esc(ago(line.observedAt))}</p>
        ${history ? `<p class="row-meta">${history.hits}/${history.games} this season at this line${history.games < 5 ? ' · small sample' : ''}</p>` : ''}
        ${warnings.length ? `<p class="row-meta model-read-caution">${esc(warnings[0])}</p>` : ''}
        ${warnings.length > 1 ? `<details><summary>More context</summary>${warnings.slice(1).map(w => `<p class="row-meta">${esc(w)}</p>`).join('')}</details>` : ''}</article>`;
    };
    return section(archived ? 'Saved pregame lines' : 'More lines', `<div class="model-read-grid">${reads.slice(0, 2).map(render).join('')}</div>` +
      (reads.length > 2 ? `<details class="model-read-more"><summary>See ${reads.length - 2} more</summary><div class="model-read-grid">${reads.slice(2).map(render).join('')}</div></details>` : ''));
  };

  const favoriteLinesSection = (card, detail) => {
    if (card.completed || !detail) return '';
    const favorites = C.rankConfidence(detail.favoriteLines || []);
    if (!favorites.length) return section('Lines we like', '<p class="row-meta compact-note">No highlighted line at the current price. More lines are below.</p>');
    const renderLine = (line, i) => {
      const player = line.kind === 'player';
      const chance = line.chance != null ? `Chance ${Math.round(100 * line.chance)}%` : '';
      const need = line.needs != null ? `Price needs ${Math.round(100 * line.needs)}%` : '';
      const priceEdge = typeof line.edge === 'number' ? `${signed(line.edge)} pts vs price` : '';
      let comparison = '';
      if (typeof line.line === 'number' && typeof line.projection === 'number') {
        if (line.market === 'point spread') {
          const team = String(line.title || '').split(' ')[0];
          const modelLine = line.side === 'home' ? -line.projection : line.projection;
          comparison = `Line ${team} ${signed(line.line)} · Projection ${team} ${signed(modelLine)}`;
        } else {
          const gap = line.projection - line.line;
          comparison = `Line ${fixed(line.line)} · Projection ${fixed(line.projection)} (${fixed(Math.abs(gap))} ${gap >= 0 ? 'higher' : 'lower'})`;
        }
      }
      const detailText = [comparison, chance, need, priceEdge]
        .filter(Boolean).join(' · ');
      const history = line.history || {};
      const rate = (label, value) => value && value.games ? `${value.hits}/${value.games} (${value.rate}%) ${label}` : '';
      const historyText = [rate(`last ${history.last ? history.last.games : 0}`, history.last), rate('this season', history.season)]
        .filter(Boolean).join(' · ');
      const confidence = line.confidenceRank && line.confidenceRank <= 5 ? (line.confidenceRank === 1 ? 'Highest confidence' : `#${line.confidenceRank} confidence`) : '';
      return `<div class="row favorite-line" style="cursor:default"><span class="row-rail" style="background:var(--mint)"></span>
        <span class="row-main"><span class="row-top"><span class="pill pill-ours">#${i + 1} value</span>${confidence ? `<span class="pill pill-confidence">${esc(confidence)}</span>` : ''}<span class="row-name">${esc(line.title)}</span>${line.team ? `<span class="row-meta">${esc(line.team)}</span>` : ''}${line.alternate ? '<span class="pill pill-reference">Alternate</span>' : ''}</span>
        <span class="row-market">${esc(detailText)}</span>${historyText ? `<span class="row-meta favorite-history">${esc(historyText)}</span>` : ''}<span class="row-meta">Updated ${esc(ago(line.observedAt))}</span></span>
        <span class="row-price"><span class="row-odds num">${esc(C.odds(line.odds))}</span><span class="row-book">${esc(line.book)}</span></span></div>`;
    };
    const groups = [['Spreads', favorites.filter(l => l.market === 'point spread')],
      ['Game totals', favorites.filter(l => l.kind === 'game' && l.market !== 'point spread')],
      ['Player props', favorites.filter(l => l.kind === 'player')]];
    return section('Lines we like', groups.filter(([, rows]) => rows.length).map(([name, rows]) =>
      `<h3 class="eyebrow">${esc(name)}</h3><div class="card favorite-lines"><div class="rows">${rows.map(renderLine).join('')}</div></div>`).join('') + `
      <p class="row-meta favorite-note">Fresh prices. Official plays are labeled separately.</p>`);
  };

  async function viewGame(route) {
    const [today, detail] = await Promise.all([get('app/today.json'), maybe(`app/games/${route.id}.json`)]);
    let card = detail || today.games.find(g => g.id === route.id);
    const back = '<a class="back" href="#games">← Games</a>';
    if (!card) {
      return `${head('Game not in the current window', 'This page covers games from three days back to eight days ahead.', back)}
        <div class="inline-links">${external(espnGame(route.id), 'ESPN game page')}<a href="#model">Model scoreboard →</a></div>`;
    }
    const liveNow = await liveFootball([card]);
    card = liveNow.games[0];
    const league = card.league;
    const teams = await maybe(`app/teams/${league}.json`);
    const m = card.market || {}, v2 = card.v2;
    const f = detail && detail.forecast;
    const final = card.completed && detail && detail.final;
    const title = `${card.away.abbr} @ ${card.home.abbr}`;
    const status = card.completed ? `Final ${card.away.abbr} ${card.away.score}, ${card.home.abbr} ${card.home.score}` : esc(when(card.kickoff));
    const win = v2 ? (v2.winProb >= 0.5 ? `${card.home.abbr} ${Math.round(100 * v2.winProb)}%` : `${card.away.abbr} ${Math.round(100 * (1 - v2.winProb))}%`) : DASH;
    let html = `${head(title, `${status}${card.neutral ? ' · neutral site' : ''} · ${esc(leagueName(league))}`, back)}${liveStamp(liveNow.refreshed)}
      ${favoriteLinesSection(card, detail)}
      ${modelReadsSection(card, detail)}
      ${!card.completed && C.modelCaution(card) ? `<div class="notice">${esc(C.modelCaution(card))}</div>` : ''}
      <div class="stats">
        ${stat('Our score', v2 ? `${fixed(v2.away, 0)}–${fixed(v2.home, 0)}` : DASH, v2 ? `${esc(card.away.abbr)} ${fixed(v2.away)}, ${esc(card.home.abbr)} ${fixed(v2.home)}` : 'no number yet')}
        ${stat('Win chance', win, v2 ? 'our estimate' : '')}
        ${stat('Our spread', v2 ? esc(C.modelSpread(card.home.abbr, card.away.abbr, v2.margin)) : DASH, v2 && v2.range ? `80%: ${signed(v2.range.margin[0])} to ${signed(v2.range.margin[1])} (home)` : '')}
        ${stat('Market spread', m.spread != null ? esc(C.spreadText(card.home.abbr, m.spread)) : DASH, m.spreadOpen != null && m.spreadOpen !== m.spread ? `opened ${esc(C.spreadText(card.home.abbr, m.spreadOpen))}` : esc(m.book || ''))}
        ${stat('Our total', v2 ? fixed(v2.total) : DASH, v2 && v2.range ? `80%: ${fixed(v2.range.total[0])} to ${fixed(v2.range.total[1])}` : '')}
        ${stat('Market total', m.total != null ? esc(m.total) : DASH, m.totalOpen != null && m.totalOpen !== m.total ? `opened ${esc(m.totalOpen)}` : esc(m.book || ''))}
      </div>
      ${card.lean && !card.completed ? `<div style="margin-top:10px">${leanChips(card)}</div>` : ''}
      ${v2 && v2.sparse ? '<div class="notice" style="margin-top:12px"><strong>Thin history.</strong> One of these teams has fewer than three games this season, so this forecast leans on last season and the league average.</div>' : ''}`;
    if (final) html += finalSection(card, detail, teams);
    html += matchupResearch(card, detail);
    if (f) {
      html += depthChartSection(card, detail);
      html += projectionSection(card, detail);
    } else if (!card.completed) {
      html += section('Player projections', empty('No projections yet', 'Player projections are not available for this game yet.'));
    }
    html += matchupSection(card, detail, teams);
    html += formSection(card, detail, teams);
    if (detail) html += injurySection(card, detail);
    if (detail && (detail.picks.length || detail.lines.length)) {
      html += section('Our picks and lines in this game', `<div class="card"><div class="rows">${detail.picks.map(pickRow).join('')}${detail.lines.map(lineRow).join('')}</div></div>`);
    }
    html += `<div class="section inline-links">${external(espnGame(card.id), 'ESPN game page')}<a href="#team/${esc(league)}/${esc(card.away.id)}">${esc(card.away.abbr)} team page</a><a href="#team/${esc(league)}/${esc(card.home.id)}">${esc(card.home.abbr)} team page</a></div>`;
    return html;
  }

  const finalSection = (card, detail, teams) => {
    const fin = detail.final;
    const periods = fin.periods || {};
    const quarter = periods.home && periods.away ? `<div class="table-wrap" style="margin-bottom:10px"><table class="data"><thead><tr><th>Team</th>${periods.home.map((_, i) => `<th>${i < 4 ? 'Q' + (i + 1) : 'OT'}</th>`).join('')}<th>Final</th></tr></thead><tbody>
      <tr><td>${esc(card.away.abbr)}</td>${periods.away.map(v => `<td>${v}</td>`).join('')}<td><b>${fin.away}</b></td></tr>
      <tr><td>${esc(card.home.abbr)}</td>${periods.home.map(v => `<td>${v}</td>`).join('')}<td><b>${fin.home}</b></td></tr></tbody></table></div>` : '';
    const close = fin.close || {};
    const grades = (detail.grades || []).map(g => `<tr><td>${esc(g.model)}</td><td>${signed(g.margin)}</td><td>${fixed(g.total)}</td><td>${g.side ? esc(g.side) : DASH}</td><td>${g.ou ? esc(g.ou) : DASH}</td></tr>`).join('');
    const names = id => ((teams || {}).teams || {})[id] ? teams.teams[id].abbr : id;
    const leaders = (fin.leaders || []).map(p => `<tr><td><a href="#player/${esc(card.league)}/${esc(p.id)}">${esc(p.name)}</a><span class="sub">${esc(names(p.team))} ${esc(p.pos || '')}</span></td><td>${esc(Object.entries(p.line).map(([k, v]) => `${v} ${C.LABEL[k] || k}`).join(' · '))}</td></tr>`).join('');
    return section('Final', `${quarter}
      <div class="stats" style="margin-bottom:10px">${stat('Closing spread', close.spread != null ? esc(C.spreadText(card.home.abbr, close.spread)) : DASH, esc(fin.provider || ''))}${stat('Closing total', close.total != null ? esc(close.total) : DASH, esc(fin.provider || ''))}${stat('Result', `${signed(fin.home - fin.away, 0)}`, `home margin · ${fin.home + fin.away} total`)}</div>
      ${grades ? `<div class="table-wrap" style="margin-bottom:10px"><table class="data"><caption>Graded against the close</caption><thead><tr><th>Model</th><th>Home margin</th><th>Total</th><th>Side</th><th>O/U</th></tr></thead><tbody>${grades}</tbody></table></div>` : ''}
      ${leaders ? `<div class="table-wrap"><table class="data"><caption>Leaders</caption><tbody>${leaders}</tbody></table></div>` : ''}
      <div class="inline-links" style="margin-top:10px">${external(fin.source, 'ESPN box score')}</div>`);
  };

  const PROJ_COLS = [['targets', 'Tgt'], ['receptions', 'Rec'], ['recYds', 'Rec yds'], ['carries', 'Car'], ['rushYds', 'Rush yds'], ['att', 'Att'], ['cmp', 'Cmp'], ['passYds', 'Pass yds']];

  const HARD_INJURY = /out|doubtful|suspension/i;
  const opportunity = p => (p.carries ? p.carries[0] : 0) + (p.targets ? p.targets[0] : 0) + (p.att ? p.att[0] : 0);
  const workload = p => [['carries', 'carries'], ['targets', 'targets'], ['att', 'attempts']]
    .filter(([key]) => p && p[key] && p[key][0] >= .5).map(([key, label]) => `${fixed(p[key][0])} ${label}`).join(' + ');
  const roleUsageText = (usage, subject) => {
    if (!usage) return '';
    const labels = { car: 'carries', tgt: 'targets', att: 'pass attempts' };
    const volume = Object.entries(usage.volume || {}).map(([key, value]) => value == null ? `${labels[key] || key} unavailable` : `${fixed(value)} ${labels[key] || key} (${(usage.coverage || {})[key] ?? usage.games}/${usage.games} games observed)`);
    const redLabel = /^(RB|FB)$/.test(usage.group) ? ['red-zone carry', 'red-zone carries']
      : usage.group === 'QB' ? ['red-zone pass attempt', 'red-zone pass attempts'] : ['red-zone target', 'red-zone targets'];
    const scoring = [usage.redZone == null ? 'Red-zone data unavailable' : `${usage.redZone} ${redLabel[usage.redZone === 1 ? 0 : 1]} in ${usage.redZoneGames} of ${usage.redZoneObserved ?? usage.games} observed games`];
    if (usage.inside10 != null) scoring.push(`${usage.inside10} inside the 10`);
    if (usage.touchdowns != null) scoring.push(`${usage.touchdowns} TD${usage.touchdowns === 1 ? '' : 's'} (${usage.touchdownObserved ?? usage.games}/${usage.games} games observed)`);
    return `<p class="depth-history"><b>${esc(subject)}</b> · ${Math.round(100 * usage.snapPct)}% snaps${volume.length ? ` · ${esc(volume.join(' · '))}` : ''}<br><span>${esc(scoring.join(' · '))}</span></p>`;
  };

  const sleeperText = (evidence, next, projection, abbr) => {
    if (!evidence || !projection) return '';
    const signal = C.injurySleeperSignal(evidence, opportunity(projection));
    if (!signal) return '';
    const role = evidence.roleUsage;
    const redKind = /^(RB|FB)$/.test(evidence.group) ? 'carry' : 'target';
    const volumeKind = /^(RB|FB)$/.test(evidence.group) ? 'opportunities (carries + targets)' : 'targets';
    const roleLine = `${abbr} ${evidence.role} has averaged ${fixed(signal.roleOpportunities)} ${volumeKind} and ${Math.round(100 * role.snapPct)}% of snaps`;
    const redLine = role.redZone ? `, with ${role.redZone} red-zone ${redKind}${role.redZone === 1 ? '' : 's'} in ${role.redZoneGames} of ${role.games} games` : '';
    const verdict = signal.tier === 'volume'
      ? `The adjusted model gives ${next.name} ${fixed(signal.projected)} opportunities, enough to monitor his lines once a real price is available.`
      : `The adjusted model gives ${next.name} only ${fixed(signal.projected)} opportunities, so this is a long-shot touchdown dart—not a volume prop.`;
    return `<div class="depth-sleeper depth-sleeper-${esc(signal.tier)}"><div><span class="pill">${esc(signal.label)}</span> <b>${esc(next.name)}</b></div><p>${esc(roleLine + redLine)}. ${esc(verdict)} <span>Sneaky angle, not an official play.</span></p></div>`;
  };

  const depthChartSection = (card, detail) => {
    if (card.league !== 'NFL' || !detail || !detail.forecast) return '';
    const cards = [];
    for (const side of ['away', 'home']) {
      const team = detail.teams[side] || {};
      const chart = team.depthChart;
      if (!chart || !chart.positions || !chart.positions.length) continue;
      const injuries = (team.injuries || []).filter(p => HARD_INJURY.test(p.status || '') && /^(QB|RB|FB|WR|TE)$/.test(p.position || ''));
      const unavailable = new Set(injuries.map(p => String(p.id)));
      const projections = ((detail.forecast.players[side] || {}).players || []);
      for (const hurt of injuries) {
        const slot = chart.positions.find(position => position.players.some(p => String(p.id) === String(hurt.id)));
        if (!slot) continue;
        const index = slot.players.findIndex(p => String(p.id) === String(hurt.id));
        const next = slot.players.slice(index + 1).find(p => !unavailable.has(String(p.id)));
        if (!next) continue;
        const group = slot.group === 'FB' ? 'RB' : slot.group;
        const role = projections.filter(p => (p.pos === 'FB' ? 'RB' : p.pos) === group).sort((a, b) => opportunity(b) - opportunity(a));
        const relevant = [];
        for (const player of [...role.slice(0, 1), role.find(p => String(p.id) === String(next.id))].filter(Boolean)) {
          if (!relevant.some(p => p.id === player.id)) relevant.push(player);
        }
        const order = slot.players.map((p, i) => {
          const isOut = unavailable.has(String(p.id));
          const isNext = String(p.id) === String(next.id);
          return `<a class="depth-person ${isOut ? 'depth-out' : ''} ${isNext ? 'depth-next' : ''}" href="#player/${esc(card.league)}/${esc(p.id)}"><b>${esc(slot.label)}${i + 1}</b> ${esc(p.name)}${isOut ? ' · OUT' : isNext ? ' · NEXT UP' : ''}</a>`;
        }).join('<span class="depth-arrow">→</span>');
        const adjusted = relevant.map(p => `<a href="#player/${esc(card.league)}/${esc(p.id)}">${esc(p.name)}</a> ${esc(workload(p) || 'role below projection threshold')}`).join(' · ');
        const evidence = (team.depthUsage || {})[String(hurt.id)];
        const roleEvidence = evidence ? roleUsageText({...evidence.roleUsage, group: evidence.group},
          `${card[side].abbr} ${evidence.role} actual role this season (${evidence.roleUsage.games} games)`) : '';
        const playerEvidence = evidence && evidence.playerUsage ? roleUsageText({...evidence.playerUsage, group: evidence.group},
          `${next.name} himself this season (${evidence.playerUsage.games} games)`) : '';
        const nextProjection = role.find(p => String(p.id) === String(next.id));
        const sleeper = sleeperText(evidence, next, nextProjection, card[side].abbr);
        cards.push(`<div class="card depth-card"><div class="depth-head"><span><span class="pill pill-out">${esc(hurt.status)}</span> <b>${esc(hurt.name)}</b> <span class="row-meta">${esc(hurt.injury || 'injury not listed')}</span></span><span class="row-meta">${esc(card[side].abbr)}</span></div>
          <p class="depth-move"><b>${esc(next.name)}</b> moves from ${esc(slot.label)}${index + 2} to ${esc(slot.label)}${index + 1} on ESPN's listed order.</p>
          <div class="depth-line">${order}</div>${roleEvidence}${playerEvidence}${adjusted ? `<p class="depth-work"><b>Tonight's model:</b> ${adjusted}</p>` : ''}${sleeper}</div>`);
      }
    }
    if (!cards.length) return '';
    const checkedAt = ['away', 'home']
      .map(side => detail.teams[side].depthChart?.checkedAt)
      .filter(Boolean)
      .sort()
      .pop();
    return section('Next up after injuries', `<div class="grid-2">${cards.join('')}</div>
      <p class="row-meta depth-note">Depth chart and recent usage. Checked ${esc(ago(checkedAt))}. Touchdown angles are for reference.</p>`);
  };

  const projectionSection = (card, detail) => {
    const f = detail.forecast;
    const lines = (detail.props || {}).lines || {};
    const table = side => {
      const block = f.players[side] || {};
      const team = card[side];
      const players = block.players || [];
      if (!players.length) return empty(`${team.abbr}: no projections`, 'Not enough recent games for this team.');
      const cols = PROJ_COLS.filter(([key]) => players.some(p => p[key]));
      const vol = block.volume || {};
      return `<div class="table-wrap"><table class="data"><caption>${esc(team.abbr)} · ${fixed(vol.plays, 0)} plays, ${Math.round(100 * (vol.passRate || 0))}% pass</caption>
        <thead><tr><th>Player</th>${cols.map(([, label]) => `<th>${label}</th>`).join('')}</tr></thead><tbody>
        ${players.map(p => `<tr><td><a href="#player/${esc(card.league)}/${esc(p.id)}">${esc(p.name)}</a><span class="sub">${esc(p.pos)}</span></td>${cols.map(([key]) => {
          const value = p[key];
          if (!value) return `<td class="faint">${DASH}</td>`;
          const market = (lines[p.id] || {})[C.PROJECTION_MARKET[key]];
          const gap = market ? value[0] - market[0] : null;
          return `<td title="80% range ${value[1]} to ${value[2]}">${fixed(value[0])}${market ? `<span class="sub ${gap > 0 ? 'up' : gap < 0 ? 'down' : ''}">line ${market[0]} (${signed(gap)})</span>` : `<span class="sub">${value[1]}–${value[2]}</span>`}</td>`;
        }).join('')}</tr>`).join('')}</tbody></table></div>`;
    };
    const props = detail.props;
    return section('Player projections', `<div class="grid-2">${table('away')}${table('home')}</div>
      <p class="row-meta" style="margin:8px 2px 0">Projected averages with 80% ranges. ${props ? `Lines updated ${esc(ago(props.capturedAt))}. Green is above the line; red is below.` : 'No comparison lines are available yet.'}</p>`);
  };

  const MATCHUP = [['QB', 'passYds'], ['RB', 'rushYds'], ['WR', 'recYds'], ['TE', 'recYds']];
  const matchupSection = (card, detail, teams) => {
    if (!teams || !teams.defense) return '';
    const rows = teams.defense.rows || {};
    if (!Object.keys(rows).length) return '';
    const side = (offense, defense) => `<div class="table-wrap"><table class="data"><caption>${esc(offense.abbr)} offense vs ${esc(defense.abbr)} defense</caption>
      <thead><tr><th>Position</th><th>Allowed per game</th><th>Rank</th></tr></thead><tbody>
      ${MATCHUP.map(([pos, key]) => {
        const hit = C.rankOf(rows, defense.id, pos, key);
        if (!hit) return `<tr><td>${pos} ${esc(C.LABEL[key])}</td><td class="faint">${DASH}</td><td></td></tr>`;
        const tone = C.rankTone(hit.rank, hit.of);
        return `<tr><td>${pos} ${esc(C.LABEL[key])}</td><td>${fixed(hit.value)}</td><td><span class="rank ${tone === 'soft' ? 'rank-soft' : tone === 'tough' ? 'rank-tough' : ''}">${hit.rank}/${hit.of}</span></td></tr>`;
      }).join('')}</tbody></table></div>`;
    return section('Matchup: what each defense allows', `<div class="grid-2">${side(card.away, card.home)}${side(card.home, card.away)}</div>
      <p class="row-meta" style="margin:8px 2px 0">This season, regular season only. Rank 1 allows the least. Green marks defenses that allow the most, red the least. Position groups combine every player at that position.</p>`, '<a href="#stats/defense">All defenses →</a>');
  };

  const formSection = (card, detail, teams) => {
    if (!detail || !detail.teams) return '';
    const name = id => ((teams || {}).teams || {})[id] ? teams.teams[id].abbr : id;
    const table = side => {
      const form = detail.teams[side].form || [];
      if (!form.length) return empty(`${card[side].abbr}: no stored games`, 'Form appears after the team’s first stored game.');
      return `<div class="table-wrap"><table class="data"><caption>${esc(card[side].abbr)} last ${form.length}</caption><thead><tr><th>Game</th><th>Score</th><th>Yds</th><th>Allowed</th><th>Success</th><th>TO</th></tr></thead><tbody>
        ${form.map(g => `<tr><td><a href="#game/${esc(g.gameId)}">${esc(g.date.slice(5))} ${g.home === false ? '@' : 'vs'} ${esc(name(g.opp))}</a></td><td class="${g.pf > g.pa ? 'up' : g.pf < g.pa ? 'down' : ''}">${g.pf}–${g.pa}</td><td>${g.yards ?? DASH}</td><td>${g.yardsAllowed ?? DASH}</td><td>${g.success != null ? Math.round(100 * g.success) + '%' : DASH}</td><td>${g.turnovers ?? DASH}</td></tr>`).join('')}</tbody></table></div>`;
    };
    return section('Recent form', `<div class="grid-2">${table('away')}${table('home')}</div>`);
  };

  const injurySection = (card, detail) => {
    const block = side => {
      const list = detail.teams[side].injuries || [];
      if (!list.length) return `<p class="row-meta">${esc(card[side].abbr)}: nobody listed. A missing listing is not proof of health.</p>`;
      return `<div class="card"><div class="rows">${list.map(p => `<div class="row" style="cursor:default"><span class="row-main"><span class="row-top"><span class="row-name">${esc(p.name)}</span><span class="row-meta">${esc(p.position || '')}</span>
        <span class="pill ${/out|reserve/i.test(p.status) ? 'pill-out' : 'pill-q'}">${esc(p.status)}</span></span><span class="row-meta">${esc(p.injury || 'injury not listed')} · reported ${esc(ago(p.reportedAt))}</span></span></div>`).join('')}</div></div>`;
    };
    if (card.league !== 'NFL') return section('Injuries', '<p class="row-meta">College injury reports are not covered by the feed. Check team sources before relying on a projection.</p>');
    return section('Injury report', `<div class="grid-2"><div><p class="eyebrow">${esc(card.away.abbr)}</p>${block('away')}</div><div><p class="eyebrow">${esc(card.home.abbr)}</p>${block('home')}</div></div>`);
  };

  const RAIL = { strong: 'var(--green)', lean: 'var(--amber)' };
  const lineText = v => v === 0 ? 'PK' : `${v > 0 ? '+' : ''}${Math.round(v * 10) / 10}`;
  /* Our open picks, keyed the way board rows are keyed, so the board can mark them. */
  let pickKeys = new Map();
  const pickKey = p => p.athleteId ? `prop-${p.gameId}-${p.athleteId}-${String(p.marketType || p.market || '').replace(/\s+/g, '')}`
    : p.marketType === 'total' ? `game-${p.gameId}-${p.direction}` : p.marketType === 'spread' ? `game-${p.gameId}-${p.direction}` : null;
  const rowKey = row => row.athleteId ? `prop-${row.gameId}-${row.athleteId}-${String(row.market || '').replace(/\s+/g, '')}` : row.id;
  const markPicks = picks => { pickKeys = new Map(); for (const p of picks) { if (!p.result && C.isOpen(p)) { const k = pickKey(p); if (k) pickKeys.set(k, p); } } };

  /* Game ids to games, set by each page that shows board rows, so a line reads with team names:
     "Liberty at Coastal Over 50.5" and "Coastal +2.5" instead of "LIB @ CCU over 50.5" and "CCU +2.5". */
  let gameIndex = new Map();
  const escapeRe = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const niceTitle = row => {
    if (row.player) return row.player;
    let t = String(row.title || 'Line');
    const g = gameIndex.get(row.gameId);
    if (g && g.away && g.home) {
      t = t.replace(`${g.away.abbr} @ ${g.home.abbr}`, `${teamName(g.away)} at ${teamName(g.home)}`);
      for (const team of [g.away, g.home]) if (team.abbr) t = t.replace(new RegExp(`^${escapeRe(team.abbr)}(?= [-+]|$| PK)`), teamName(team));
    }
    return t.replace(/ over /, ' Over ').replace(/ under /, ' Under ');
  };

  /* Our chance as a bar, with a tick where the price needs it to be to break even. */
  const chanceBar = (chance, needs, tier) => `<span class="cbar" aria-hidden="true"><span class="cbar-fill cbar-${esc(tier)}" style="width:${Math.max(2, Math.min(100, 100 * chance)).toFixed(0)}%"></span>${typeof needs === 'number' ? `<span class="cbar-mark" style="left:${(100 * needs).toFixed(1)}%"></span>` : ''}</span>`;

  const lineRow = row => {
    const inTicket = state.ticket.some(t => t.id === row.id);
    const ours = pickKeys.get(rowKey(row)) || pickKeys.get(row.id);
    const g = C.gradeOf(row.grade, row.gradeNote, row);
    const open = row.state === 'open';
    const graded = open || Boolean(row.athleteId);   /* player lines have no price but do have a read */
    const books = row.books || [];
    const confidence = row.confidenceRank && row.confidenceRank <= 5 ? (row.confidenceRank === 1 ? 'Highest confidence' : `#${row.confidenceRank} confidence`) : '';
    const gradeDetail = row.grade && typeof row.grade.chance === 'number'
      ? `${Math.round(100 * row.grade.chance)}% our chance · ${typeof row.grade.needs === 'number' ? `${Math.round(100 * row.grade.needs)}% needed` : 'projection only'}`
      : row.grade && typeof row.grade.projection === 'number' && typeof row.line === 'number'
        ? `Projection ${fixed(row.grade.projection)} · line ${fixed(row.line)}` : '';
    return `<div class="row${open ? '' : ' row-closed'}${row.athleteId ? ' row-prop' : ''}"${row.athleteId ? ` data-prop="${esc(row.id)}" role="button" tabindex="0"` : ' style="cursor:default"'}>
      <span class="row-rail" style="background:${graded && RAIL[g.tier] || 'var(--line)'}"></span>
      <span class="row-main"><span class="row-top">${avatar(row, 'ava-row')}<span class="row-name">${esc(niceTitle(row))}</span>${row.position ? `<span class="row-meta">${esc(row.position)}</span>` : ''}${ours ? '<span class="pill pill-ours">Our pick</span>' : ''}${confidence ? `<span class="pill pill-confidence">${esc(confidence)}</span>` : ''}
        ${!open ? `<span class="pill pill-${esc(row.state)}">${esc({ stale: 'Recheck price', closed: 'Closed', unpriced: 'No price', reference: 'Unverified price' }[row.state] || row.state)}</span>` : ''}
        ${row.move && typeof row.line === 'number' ? `<span class="move">opened ${esc(lineText(row.line - row.move))}</span>` : ''}</span>
        ${row.player ? `<span class="row-market">${esc([row.direction, row.line, row.market].filter(v => v != null && v !== '').join(' '))}</span>` : ''}
        ${graded ? `<span class="grade grade-${g.tier}"><b>${esc(g.word)}</b>${gradeDetail ? `<span>${esc(gradeDetail)}</span>` : ''}</span>` : ''}
        ${graded && row.grade && typeof row.grade.chance === 'number' ? chanceBar(row.grade.chance, row.grade.needs, g.tier) : ''}
        <span class="row-meta">${esc(whenShort(row.kickoff))}${row.observedAt ? ' · price checked ' + esc(ago(row.observedAt)) : ''}${row.athleteId ? '<span class="more"> · last 10 and matchup ›</span>' : ''}</span></span>
      <span class="row-price"><span class="row-odds num">${odds(row.odds)}</span><span class="row-book">${row.book ? `at ${esc(row.book)}` : 'No book'}${books.length > 1 ? `<br>best of ${books.length} books` : ''}</span></span>
      ${row.state === 'open' && row.odds != null ? `<button class="add" type="button" data-add="${esc(row.id)}" aria-pressed="${inTicket}" aria-label="${inTicket ? 'Remove from ticket' : 'Add to ticket'}">${inTicket ? '✓' : '+'}</button>` : ''}
    </div>`;
  };

  /* ---------- stats: players, defenses, teams ---------- */

  async function viewStats(route) {
    const league = dataLeague();
    const tab = route.tab === 'players' ? 'search' : route.tab || 'charts';
    const note = state.league === 'ALL' ? '<p class="row-meta">Stats are per league; showing NFL. Switch to College above.</p>' : '';
    const tabs = `<div class="toolbar"><div class="seg" role="group">${[['charts', 'Player charts'], ['search', 'Search'], ['defense', 'Defenses'], ['teams', 'Teams']].map(([id, label]) =>
      `<a class="chip" style="display:inline-flex;align-items:center" href="#stats/${id}" aria-pressed="${tab === id}">${label}</a>`).join('')}</div></div>`;
    if (tab === 'defense') return head('Defense vs position', `What each ${leagueName(league)} defense allows per game, by position group.`) + note + tabs + await defenseView(league);
    if (tab === 'teams') return head('Teams', `${leagueName(league)} teams with stored games.`) + note + tabs + await teamsList(league);
    if (tab === 'search') return head('Player search', `Find any ${leagueName(league)} player and open their complete game log.`) + note + tabs + await playerSearch(league);
    return head('Player charts', `Every stat, game by game. Pick a matchup, position and sample, then tap a player for the full log.`) + note + tabs + await playerCharts(league);
  }

  const CHART_STATS = ['passYds', 'cmp', 'att', 'passTD', 'int', 'sacks', 'scrambles',
    'rushYds', 'car', 'rushTD', 'rushLong', 'rzCar', 'i10Car', 'i5Car',
    'recYds', 'rec', 'targets', 'recTD', 'recLong', 'rzTgt', 'i10Tgt',
    'fumLost', 'fgm', 'fga', 'xpm', 'kPts', 'snaps', 'snapPct'];

  const chartHas = (player, key) => Object.prototype.hasOwnProperty.call(player.projection || {}, key)
    || Object.prototype.hasOwnProperty.call(player.lines || {}, key)
    || (player.rows || []).some(row => Object.prototype.hasOwnProperty.call(row.stats || {}, key));

  const chartRows = (player, key) => {
    const count = state.chartWindow === 'last5' ? 5 : state.chartWindow === 'last10' ? 10 : 100;
    return (player.rows || []).filter(row => typeof (row.stats || {})[key] === 'number').slice(-count);
  };

  const miniPlayerChart = (player, key) => {
    const rows = chartRows(player, key), values = rows.map(row => row.stats[key]);
    const current = (player.lines || {})[key], line = current && typeof current.line === 'number' ? current.line : null;
    const projection = typeof (player.projection || {})[key] === 'number' ? player.projection[key] : null;
    const max = Math.max(line || 0, projection || 0, ...values, 1);
    const bars = rows.map((row, i) => { const value = values[i];
      const tone = line == null ? '' : value > line ? 'over' : value < line ? 'under' : 'push';
      const shown = key === 'snapPct' ? `${Math.round(100 * value)}%` : Number.isInteger(value) ? value : fixed(value);
      return `<span class="mini-col" title="${esc(row.date)}: ${esc(shown)}"><b>${esc(shown)}</b><i class="${tone}" style="height:${Math.max(3, Math.round(58 * value / max))}px"></i><small>${esc(row.date.slice(5))}</small></span>`;
    }).join('');
    const marker = line == null ? '' : `<span class="mini-line" style="bottom:${Math.min(92, Math.max(2, 100 * line / max)).toFixed(1)}%"><b>${esc(line)}</b></span>`;
    const avg = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
    const hits = line == null ? '' : `${values.filter(value => value > line).length}/${values.length} over`;
    return `<span class="player-chart-numbers">
        <span><small>Current line</small><b class="num">${line == null ? DASH : esc(line)}</b><em>${current ? `${esc(current.book || '')} ${odds(current.odds)}` : 'not posted'}</em></span>
        <span><small>Our number</small><b class="num">${projection == null ? DASH : fixed(projection)}</b><em>${esc(C.LABEL[key] || key)}</em></span>
        <span><small>${hits ? 'Recent' : 'Average'}</small><b class="num">${hits || (avg == null ? DASH : fixed(avg))}</b><em>${values.length} game${values.length === 1 ? '' : 's'}</em></span>
      </span><span class="mini-chart" role="img" aria-label="${esc(player.name)} ${esc(C.LABEL[key] || key)} by game">${bars || '<span class="mini-empty">No games yet</span>'}${marker}</span>`;
  };

  const playerChartCard = (player, key, league) => `<a class="player-chart-card" href="#player/${league}/${esc(player.id)}">
    <span class="player-chart-head">${pic(HEADSHOT[league](player.id), 'player-chart-photo')}<span><b>${esc(player.name)}</b><small>${esc(player.pos || '')}</small></span><span class="player-chart-arrow">›</span></span>
    ${miniPlayerChart(player, key)}</a>`;

  const chartTeam = (team, game, players, key, league) => {
    if (!players.length) return '';
    const logoTeam = { id: team.id, abbr: team.abbreviation };
    return `<div class="chart-team"><div class="chart-team-head">${pic(LOGO[league](logoTeam), 'chart-team-logo')}<span><b>${esc(team.name || team.abbreviation)}</b><small>${players.length} player${players.length === 1 ? '' : 's'}</small></span></div>
      <div class="player-chart-grid">${players.map(player => playerChartCard(player, key, league)).join('')}</div></div>`;
  };

  async function playerCharts(league) {
    const data = await maybe(`app/player-charts/${league}.json`);
    if (!data || !data.games || !data.games.length) return empty('No upcoming player charts', 'Charts appear when the next matchup and player roles are available.');
    const available = new Set(CHART_STATS.filter(key => data.players.some(player => chartHas(player, key))));
    const key = available.has(state.chartStat) ? state.chartStat : [...available][0];
    if (!key) return empty('No player stats yet', 'Charts appear after the first stored game.');
    const days = [...new Set(data.games.map(game => game.day))];
    const selectedDay = state.chartDay === 'all' ? 'all' : days.includes(state.chartDay) ? state.chartDay : days[0];
    const query = state.chartQuery.trim().toLowerCase();
    const playerOk = player => chartHas(player, key) && (state.chartPos === 'all' || player.pos === state.chartPos
      || (state.chartPos === 'RB' && player.pos === 'FB'))
      && (!query || `${player.name} ${player.pos || ''}`.toLowerCase().includes(query));
    const games = data.games.filter(game => selectedDay === 'all' || game.day === selectedDay);
    const shownGames = new Set(games.map(game => game.id));
    const shownPlayers = data.players.filter(player => shownGames.has(player.gameId) && playerOk(player));
    const cards = games.map(game => {
      const players = data.players.filter(player => player.gameId === game.id && playerOk(player));
      const order = (a, b) => (Number(Boolean((b.lines || {})[key])) - Number(Boolean((a.lines || {})[key])))
        || ((b.projection || {})[key] || 0) - ((a.projection || {})[key] || 0) || String(a.name).localeCompare(String(b.name));
      const away = players.filter(player => player.side === 'away').sort(order);
      const home = players.filter(player => player.side === 'home').sort(order);
      if (!away.length && !home.length) return '';
      return `<section class="chart-matchup"><div class="chart-matchup-head"><span><b>${esc(game.away.abbreviation)} at ${esc(game.home.abbreviation)}</b><small>${esc(whenShort(game.kickoff))}</small></span><a href="#game/${esc(game.id)}">Game page →</a></div>
        <div class="chart-team-grid">${chartTeam(game.away, game, away, key, league)}${chartTeam(game.home, game, home, key, league)}</div></section>`;
    }).filter(Boolean).join('');
    const dateOptions = [['next', 'Next slate'], ['all', 'All upcoming'], ...days.map(value => [value, dayLabel(value + 'T17:00:00Z')])];
    return `<div class="chart-controls card"><div class="chart-selects"><label>Stat<select class="pick" data-select="chartStat">${CHART_STATS.filter(stat => available.has(stat)).map(stat => `<option value="${stat}" ${stat === key ? 'selected' : ''}>${esc(C.LABEL[stat] || stat)}</option>`).join('')}</select></label>
        <label>Games<select class="pick" data-select="chartDay">${dateOptions.map(([value, label]) => `<option value="${value}" ${state.chartDay === value ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></label></div>
      <div class="toolbar">${seg('chartPos', [['all', 'All'], ['QB', 'QB'], ['RB', 'RB'], ['WR', 'WR'], ['TE', 'TE'], ['PK', 'K']], state.chartPos)}${seg('chartWindow', [['last5', 'Last 5'], ['last10', 'Last 10'], ['season', 'Season']], state.chartWindow)}</div>
      <input class="search" type="search" data-input="chartQuery" placeholder="Search this slate" value="${esc(state.chartQuery)}" aria-label="Search player charts"></div>
      <p class="row-meta chart-count">${shownPlayers.length} players with ${esc(C.LABEL[key] || key)} data · ${esc(state.chartWindow === 'season' ? String(data.season) + ' season' : state.chartWindow === 'last10' ? 'last 10 games' : 'last 5 games')}</p>
      ${cards || empty('No matching players', 'Try another stat, position, date or search.')}`;
  }

  async function playerSearch(league) {
    const index = await get(`app/players/${league}.json`);
    return `<input class="search" type="search" data-input="playerQuery" placeholder="Search ${esc(index.players.length.toLocaleString())} players by name" value="${esc(state.playerQuery)}" aria-label="Search players" autocomplete="off">
      <div id="player-results">${playerResults(index, league)}</div>`;
  }

  const LEADER_LABELS = { passYds: 'Passing yards', rushYds: 'Rushing yards', recYds: 'Receiving yards', rec: 'Receptions' };
  /* With no search typed, the page shows who is leading rather than an empty box. */
  const leaderBoards = (index, league) => {
    const boards = index.leaders || {};
    const keys = Object.keys(LEADER_LABELS).filter(k => (boards[k] || []).length);
    if (!keys.length) return '';
    return `<div class="two-col">${keys.map(k => section(`${LEADER_LABELS[k]}${index.season ? ` · ${esc(index.season)}` : ''}`,
      `<div class="card results">${boards[k].map((p, i) => `<a href="#player/${league}/${esc(p[0])}"><span><b>${i + 1}. ${esc(p[1])}</b> <small>${esc(p[2] || '')}</small></span><small class="num">${fixed(p[3], 0)}<span class="faint"> · ${p[4]} game${p[4] === 1 ? '' : 's'}</span></small></a>`).join('')}</div>`)).join('')}</div>`;
  };

  const playerResults = (index, league) => {
    const query = state.playerQuery.trim().toLowerCase();
    if (query.length < 2) return leaderBoards(index, league)
      || empty('Search for a player', 'Type at least two letters of a name. Every player with a stat line in the last two seasons is here, with every game stored since 2023.');
    const words = query.split(/\s+/);
    const found = index.players.filter(p => words.every(w => String(p[1]).toLowerCase().includes(w)))
      .sort((a, b) => String(b[5]).localeCompare(String(a[5])) || b[6] - a[6]).slice(0, 40);
    if (!found.length) return empty('No player by that name', 'Check the spelling, or switch leagues.');
    return `<div class="card results">${found.map(p => `<a href="#player/${league}/${esc(p[0])}"><span><b>${esc(p[1])}</b> <small>${esc(p[2] || '')} · ${esc(p[4] || '')}</small></span><small>${p[6]} games · last ${esc(p[5])}</small></a>`).join('')}</div>`;
  };

  const DEFENSE_STATS = { QB: ['passYds', 'passTD', 'att', 'cmp', 'int', 'sacks', 'rushYds'], RB: ['rushYds', 'car', 'rushTD', 'recYds', 'rec', 'targets'],
    WR: ['recYds', 'rec', 'targets', 'recTD'], TE: ['recYds', 'rec', 'targets', 'recTD'] };

  async function defenseView(league) {
    const data = await get(`app/teams/${league}.json`);
    const pos = state.defensePos, stats = DEFENSE_STATS[pos];
    const key = stats.includes(state.defenseStat) ? state.defenseStat : stats[0];
    const scope = state.defenseScope;
    const rows = scope === 'last5' ? data.defense.last5 : scope === 'prior' ? data.defense.prior.rows : data.defense.rows;
    const season = scope === 'prior' ? data.defense.prior.season : data.defense.season;
    let ranked = C.rankDefenses(rows, pos, key, 1);
    if (league === 'CFB') ranked = C.rankDefenses(Object.fromEntries(Object.entries(rows).filter(([team]) => (data.teams[team] || {}).fbs)), pos, key, 1);
    const max = Math.max(1, ...ranked.map(r => r.value));
    const ordered = state.defenseOrder === 'soft' ? [...ranked].reverse() : ranked;
    return `<div class="toolbar">${seg('defensePos', [['QB', 'QB'], ['RB', 'RB'], ['WR', 'WR'], ['TE', 'TE']], pos)}
        <select class="pick" data-select="defenseStat" aria-label="Stat">${stats.map(s => `<option value="${s}" ${s === key ? 'selected' : ''}>${esc(C.LABEL[s])}</option>`).join('')}</select>
        ${seg('defenseScope', [['season', String(data.defense.season)], ['last5', 'Last 5'], ['prior', String(data.defense.prior.season)]], scope)}
        ${seg('defenseOrder', [['soft', 'Most allowed'], ['tough', 'Least allowed']], state.defenseOrder)}</div>
      ${ranked.length ? `<div class="table-wrap"><table class="data"><caption>${esc(pos)} ${esc(C.LABEL[key])} allowed per game · ${esc(season)} regular season${scope === 'last5' ? ', each team’s last 5' : ''}</caption>
        <thead><tr><th>Defense</th><th>Rank</th><th>Games</th><th>Per game</th></tr></thead><tbody>
        ${ordered.map(r => { const team = data.teams[r.team] || {}; return `<tr><td><a href="#team/${league}/${esc(r.team)}">${esc(team.short || team.name || team.abbr || r.team)}</a></td><td><span class="rank">${r.rank}/${ranked.length}</span></td><td>${r.games}</td>
          <td><span class="barcell">${fixed(r.value)}<i style="width:${Math.round(60 * r.value / max)}px"></i></span></td></tr>`; }).join('')}</tbody></table></div>`
        : empty('No games yet', 'Rankings appear once teams have played.')}
      <p class="row-meta" style="margin:8px 2px 0">Rank 1 allows the least. Position groups sum every player at the position; college targets come from play-by-play. Small samples early in the season swing hard.</p>`;
  }

  async function teamsList(league) {
    const data = await get(`app/teams/${league}.json`);
    const list = Object.entries(data.teams).filter(([, t]) => league === 'NFL' || t.fbs)
      .sort((a, b) => String(a[1].name || a[1].abbr).localeCompare(String(b[1].name || b[1].abbr)));
    return `<div class="card results">${list.map(([id, t]) => `<a href="#team/${league}/${esc(id)}"><span><b>${esc(t.name || t.abbr)}</b></span><small>${esc(t.abbr || '')}</small></a>`).join('')}</div>`;
  }

  /* ---------- one player ---------- */

  async function nextGameFor(teamId, league) {
    const today = await get('app/today.json');
    const game = upcoming(today.games).find(g => g.league === league && (g.home.id === String(teamId) || g.away.id === String(teamId)));
    if (!game) return null;
    const detail = await maybe(`app/games/${game.id}.json`);
    return { game, detail, side: game.home.id === String(teamId) ? 'home' : 'away' };
  }

  async function viewPlayer(route) {
    const league = route.league === 'CFB' ? 'CFB' : 'NFL';
    const index = await get(`app/players/${league}.json`);
    const entry = index.players.find(p => String(p[0]) === String(route.id));
    const back = '<a class="back" href="#stats">← Player charts</a>';
    if (!entry) return head('Player not found', 'No stored games for this player in this league.', back);
    const shard = await get(`app/players/${league}/${C.shardOf(route.id, index.shards)}.json`);
    const data = shard.players[route.id];
    const keys = shard.keys;
    const rows = data.rows;
    const pos = data.pos;
    const options = [...new Set([...(C.POSITION_STATS[pos] || C.POSITION_STATS.WR), 'snapPct'])].filter(k => keys.includes(k) && rows.some(r => C.cell(r, keys, k)));
    const key = options.includes(state.stat) ? state.stat : options[0] || (C.POSITION_STATS[pos] || C.POSITION_STATS.WR)[0];
    const [teams, next] = await Promise.all([get(`app/teams/${league}.json`), nextGameFor(entry[3], league)]);
    const team = teams.teams[entry[3]] || {};
    const abbr = id => (teams.teams[id] || {}).abbr || id;
    let projection = null, line = null, lineLabel = 'DraftKings line';
    if (next && next.detail && next.detail.forecast) {
      const block = next.detail.forecast.players[next.side] || {};
      projection = (block.players || []).find(p => String(p.id) === String(route.id)) || null;
      const captured = ((next.detail.props || {}).lines || {})[route.id];
      if (captured && captured[key]) line = captured[key][0];
    }
    /* The board's priced line beats the feed's unpriced one when both exist. */
    const board = next ? await maybe('app/lines.json') : null;
    const priced = ((board || {}).lines || []).find(r => String(r.athleteId) === String(route.id) && r.state === 'open' && C.marketKey(r) === key);
    if (priced && typeof priced.line === 'number') { line = priced.line; lineLabel = `${priced.book} line`; }
    const win = C.windows(rows, keys, key);
    const recent = [...rows].sort((a, b) => String(b[1]).localeCompare(String(a[1]))).slice(0, 20).reverse();
    const values = recent.map(r => C.cell(r, keys, key));
    const opponent = next ? (next.side === 'home' ? next.game.away.id : next.game.home.id) : null;
    const vsNext = next ? C.splits(rows, keys, key, opponent).vs : null;
    const split = C.splits(rows, keys, key);
    const group = C.POS_GROUP[pos];
    const allow = next && group ? C.rankOf((teams.defense || {}).rows || {}, opponent, group, key) : null;
    const allowTone = allow ? C.rankTone(allow.rank, allow.of) : 'neutral';
    const tile = (label, s) => stat(label, s ? fixed(s.avg) : DASH, s ? `n ${s.n} · median ${fixed(s.median)} · ${fixed(s.min, 0)} to ${fixed(s.max, 0)}` : 'no games');
    const projKey = { rec: 'receptions', car: 'carries' }[key] || key;
    const over = w => { if (line == null) return ''; const h = C.hits(values.slice(-w), line); return `${h.over} of ${h.n} over in the last ${h.n}`; };
    return `${back}<div class="page-head who"><span class="badge" style="background:${esc(team.color || 'var(--raised)')}">${esc(pos || '?')}</span>
        <div><h1>${esc(data.name)}</h1><p>${esc(pos || '')} · <a href="#team/${league}/${esc(entry[3])}">${esc(team.name || entry[4] || '')}</a> · ${rows.length} stored games since ${esc(String(rows[0][1]).slice(0, 4))}</p></div></div>
      <div class="toolbar"><div class="seg" role="group">${options.map(k => `<button type="button" data-set="stat:${k}" aria-pressed="${k === key}">${esc(C.LABEL[k] || k)}</button>`).join('')}</div></div>
      <div class="tiles">${tile('Last 5', win.last5)}${tile('Last 10', win.last10)}${tile('Last 20', win.last20)}${tile('This season', win.season)}</div>
      ${next ? section(`Next: ${next.side === 'home' ? 'vs' : '@'} ${abbr(opponent)} · ${whenShort(next.game.kickoff)}`,
        `<div class="stats">${stat('Projection', projection && projection[projKey] ? fixed(projection[projKey][0]) : DASH, projection && projection[projKey] ? `80%: ${projection[projKey][1]} to ${projection[projKey][2]}` : 'none for this stat')}
          ${stat(lineLabel, line != null ? esc(line) : DASH, line != null ? over(10) : 'none captured')}
          ${stat(`${esc(abbr(opponent))} vs ${esc(group || pos || '')}s`, allow ? fixed(allow.value) : DASH, allow ? `${esc(C.LABEL[key] || key)} a game · ${ordinal(allow.rank)} of ${allow.of}, 1st allows the least` : 'not tracked by position', allowTone === 'soft' ? 'up' : allowTone === 'tough' ? 'down' : '')}
          ${stat('Vs this opponent', vsNext && vsNext.summary ? fixed(vsNext.summary.avg) : DASH, vsNext && vsNext.summary ? `${vsNext.summary.n} meeting${vsNext.summary.n === 1 ? '' : 's'} since 2023` : 'no meetings stored')}</div>`,
        `<a href="#game/${esc(next.game.id)}">Game page →</a>`) : ''}
      ${section(`Last ${values.length} games · ${C.LABEL[key] || key}`, chart(recent, values, line, abbr))}
      ${section('Splits', `<div class="stats">${stat('Home', split.home ? fixed(split.home.avg) : DASH, split.home ? `n ${split.home.n}` : '')}${stat('Away', split.away ? fixed(split.away.avg) : DASH, split.away ? `n ${split.away.n}` : '')}${split.neutral ? stat('Neutral site', fixed(split.neutral.avg), `n ${split.neutral.n}`) : ''}</div>`)}
      ${section('Game log', gameLog(rows, keys, pos, abbr, league))}
      <p class="row-meta" style="margin-top:10px">Averages use stored regular-season games. Tap any bar for the full game page.</p>`;
  }

  const chart = (recent, values, line, abbr) => {
    if (!values.some(v => v != null)) return empty('No values for this stat', 'Try another stat.');
    const max = Math.max(line || 0, ...values.filter(v => v != null), 1);
    const bars = recent.map((r, i) => {
      const v = values[i];
      const cls = line == null || v == null ? '' : v > line ? 'over' : v < line ? 'under' : 'push';
      const height = v == null ? 0 : Math.max(2, Math.round(78 * v / max));
      const shown = v == null ? '' : Number.isInteger(v) ? String(v) : v < 1 ? Math.round(100 * v) + '%' : fixed(v);
      return `<div class="col" title="${esc(r[1])} ${r[7] === 0 ? '@' : 'vs'} ${esc(abbr(r[6]))}: ${v ?? 'no value'}"><span class="v">${esc(shown)}</span><span class="b ${cls}" style="height:${height}%"></span><span class="x">${esc(abbr(r[6]))}</span></div>`;
    }).join('');
    const marker = line != null ? `<div class="line" style="bottom:calc(6px + 13px + (100% - 43px) * ${(0.78 * line / max).toFixed(3)})"><span>line ${esc(line)}</span></div>` : '';
    return `<div class="card"><div class="chart" role="img" aria-label="Recent games">${bars}${marker}</div></div>`;
  };

  const LOG_COLS = { QB: ['cmp', 'att', 'passYds', 'passTD', 'int', 'car', 'rushYds', 'rushTD'], RB: ['car', 'rushYds', 'rushTD', 'targets', 'rec', 'recYds', 'rzCar'],
    WR: ['targets', 'rec', 'recYds', 'recTD', 'recLong', 'rzTgt'], TE: ['targets', 'rec', 'recYds', 'recTD', 'recLong', 'rzTgt'], PK: ['fgm', 'fga', 'xpm', 'kPts'] };

  const gameLog = (rows, keys, pos, abbr, league) => {
    const cols = [...(LOG_COLS[pos] || LOG_COLS.WR), ...(keys.includes('snapPct') && rows.some(r => C.cell(r, keys, 'snapPct') != null) ? ['snapPct'] : [])];
    const seasons = [...new Set(rows.map(r => r[2]))].sort((a, b) => b - a);
    const season = seasons.includes(Number(state.logSeason)) ? Number(state.logSeason) : null;
    const list = rows.filter(r => season == null || r[2] === season).sort((a, b) => String(b[1]).localeCompare(String(a[1])));
    return `<div class="toolbar">${seg('logSeason', [['all', 'All'], ...seasons.map(s => [String(s), String(s)])], season == null ? 'all' : String(season))}</div>
      <div class="table-wrap"><table class="data"><thead><tr><th>Game</th>${cols.map(c => `<th>${esc(C.LABEL[c] || c)}</th>`).join('')}</tr></thead><tbody>
      ${list.map(r => `<tr><td><a href="#game/${league}-${esc(r[0])}">${esc(r[1])}</a><span class="sub">${r[7] === 0 ? '@' : r[7] === -1 ? 'vs (neutral)' : 'vs'} ${esc(abbr(r[6]))}${r[4] === 3 ? ' · postseason' : ''}</span></td>
        ${cols.map(c => { const v = C.cell(r, keys, c); return `<td>${v == null ? DASH : c === 'snapPct' ? Math.round(100 * v) + '%' : esc(v)}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>`;
  };

  /* ---------- one team ---------- */

  async function viewTeam(route) {
    const league = route.league === 'CFB' ? 'CFB' : 'NFL';
    const [teams, team, index] = await Promise.all([get(`app/teams/${league}.json`), maybe(`app/teams/${league}/${route.id}.json`), get(`app/players/${league}.json`)]);
    const back = '<a class="back" href="#stats/teams">← Teams</a>';
    if (!team) return head('Team not found', 'No stored games for this team.', back);
    const abbr = id => (teams.teams[id] || {}).abbr || id;
    const season = teams.defense.season;
    const games = team.games.filter(g => g.season === season);
    const wins = games.filter(g => g.pf > g.pa).length, losses = games.filter(g => g.pf < g.pa).length;
    const cover = g => {
      if (!g.close || g.close.spread == null || g.home == null) return DASH;
      const line = g.home ? g.close.spread : -g.close.spread;
      const margin = g.pf - g.pa + line;
      return margin > 0 ? 'Covered' : margin < 0 ? 'Missed' : 'Push';
    };
    const roster = index.players.filter(p => String(p[3]) === String(route.id) && String(p[5]).slice(0, 4) >= String(season)).sort((a, b) => b[6] - a[6]).slice(0, 30);
    const allowed = team.defense.filter(d => d.season === season).reverse();
    return `${back}<div class="page-head who"><span class="badge" style="background:${esc(team.color || 'var(--raised)')}">${esc(team.abbr || '')}</span>
        <div><h1>${esc(team.name || team.abbr)}</h1><p>${esc(season)}: ${wins}–${losses} · ${esc(leagueName(league))}</p></div></div>
      ${section('Results', games.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>Game</th><th>Score</th><th>Close</th><th>ATS</th><th>Yds</th><th>Allowed</th></tr></thead><tbody>
        ${[...games].reverse().map(g => `<tr><td><a href="#game/${esc(g.gameId)}">${esc(g.date)}</a><span class="sub">${g.home === false ? '@' : g.home === null ? 'neutral' : 'vs'} ${esc(abbr(g.opp))}</span></td>
          <td class="${g.pf > g.pa ? 'up' : 'down'}">${g.pf}–${g.pa}</td><td>${g.close && g.close.spread != null ? signed(g.home === false ? -g.close.spread : g.close.spread) : DASH}</td><td>${cover(g)}</td><td>${g.off.yards ?? DASH}</td><td>${g.def.yards ?? DASH}</td></tr>`).join('')}</tbody></table></div>` : empty('No games yet', 'Results appear after the first game.'))}
      ${section('What this defense allowed', allowed.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>Game</th><th>QB pass yds</th><th>RB rush yds</th><th>WR rec yds</th><th>TE rec yds</th></tr></thead><tbody>
        ${allowed.map(d => `<tr><td><a href="#game/${esc(d.gameId)}">${esc(d.date)}</a><span class="sub">${esc(abbr(d.opp))}</span></td><td>${(d.allowed.QB || {}).passYds ?? 0}</td><td>${(d.allowed.RB || {}).rushYds ?? 0}</td><td>${(d.allowed.WR || {}).recYds ?? 0}</td><td>${(d.allowed.TE || {}).recYds ?? 0}</td></tr>`).join('')}</tbody></table></div>` : empty('Nothing yet', 'Appears after the first game.'), '<a href="#stats/defense">Rankings →</a>')}
      ${section('Players this season', roster.length ? `<div class="card results">${roster.map(p => `<a href="#player/${league}/${esc(p[0])}"><span><b>${esc(p[1])}</b> <small>${esc(p[2] || '')}</small></span><small>${p[6]} games stored</small></a>`).join('')}</div>` : empty('No players yet', 'Players appear after their first stat line.'))}`;
  }

  /* ---------- model scoreboard ---------- */

  async function viewModel() {
    const [board, today] = await Promise.all([get('scoreboard.json'), get('app/today.json')]);
    const live = (board.live || []).filter(inLeague);
    const back = (board.backtest || []).filter(inLeague);
    const rec = r => `${r[0]}–${r[1]}${r[2] ? '–' + r[2] : ''}`;
    const rate = r => r[0] + r[1] ? Math.round(100 * r[0] / (r[0] + r[1])) + '%' : DASH;
    const table = (rows, caption) => `<div class="table-wrap"><table class="data"><caption>${caption}</caption><thead><tr><th>Model</th><th>Games</th><th>Projected winner</th><th>Vs close</th><th>Margin miss</th><th>Close miss</th><th>Totals</th><th>Total miss</th><th>Closer</th><th>Line moved our way</th><th>80% held</th></tr></thead><tbody>
      ${rows.map(r => { const s = r.summary, winners = s.winner || [0, 0, 0]; return `<tr><td>${esc(leagueName(r.league))} ${esc(modelName(r.model))}<span class="sub">${esc(r.season)}</span></td><td>${s.games}</td><td>${rec(winners)}<span class="sub">${rate(winners)} right</span></td><td>${rec(s.side)}<span class="sub">${rate(s.side)}</span></td>
        <td>${fixed(s.marginMiss)}</td><td>${fixed(s.closeMarginMiss)}</td><td>${rec(s.ou)}<span class="sub">${rate(s.ou)}</span></td><td>${fixed(s.totalMiss)}<span class="sub">close ${fixed(s.closeTotalMiss)}</span></td>
        <td>${rate(s.closerMargin)}</td><td>${rate(s.movedToward)}</td><td>${s.within80 != null ? Math.round(100 * s.within80) + '%' : DASH}</td></tr>`; }).join('')}</tbody></table></div>`;
    const weeks = rows => rows.map(r => `<details class="card" style="padding:0 12px;margin-top:8px"><summary style="padding:12px 0;cursor:pointer;font-size:13px;font-weight:600">${esc(leagueName(r.league))} ${esc(modelName(r.model))} ${esc(r.season)} by week</summary>
      <div class="table-wrap" style="margin-bottom:12px"><table class="data"><thead><tr><th>Week</th><th>Games</th><th>Projected winner</th><th>Vs close</th><th>Margin miss</th><th>Close miss</th><th>Totals</th></tr></thead><tbody>
      ${r.weeks.map(w => `<tr><td>${esc(w.week === 'post' ? 'Postseason' : 'Week ' + w.week)}</td><td>${w.games}</td><td>${rec(w.winner || [0, 0, 0])}<span class="sub">${rate(w.winner || [0, 0, 0])} right</span></td><td>${rec(w.side)}</td><td>${fixed(w.marginMiss)}</td><td>${fixed(w.closeMarginMiss)}</td><td>${rec(w.ou)}</td></tr>`).join('')}</tbody></table></div></details>`).join('');
    const props = (board.props || {}).markets || [];
    const picks = (board.picks || {}).rows || [];
    return `${head('Model results', 'Every pregame forecast, graded after the game.')}
      ${scoreTabs('model')}
      ${scorecardCard(board, today.picks)}
      <div class="notice notice-model">Winner, spread and total results use the final pregame forecast. Official plays remain separate.</div>
      ${section('Live record', live.length ? table(live, 'Published before kickoff') + weeks(live) : empty('Nothing graded yet', 'Live grades start when the first numbers reach kickoff.'))}
      ${section('Backtests', back.length ? table(back, 'Retrospective walk-forward, never published') + weeks(back) : empty('No backtests', ''))}
      ${section('Player projections vs DraftKings lines', props.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>Market</th><th>Graded</th><th>Record</th><th>Closer than line</th><th>Projection miss</th><th>Line miss</th></tr></thead><tbody>
        ${props.map(p => `<tr><td>${esc(C.LABEL[p.market] || p.market)}</td><td>${p.graded}</td><td>${rec(p.record)}</td><td>${rate(p.closerThanLine)}</td><td>${fixed(p.projectionMiss)}</td><td>${fixed(p.lineMiss)}</td></tr>`).join('')}</tbody></table></div>`
        : empty('Nothing graded yet', 'NFL projections are compared with the last DraftKings line captured before kickoff once games finish.'))}
      ${section('Closing-line value on our picks', picks.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>Pick</th><th>Posted</th><th>Last before kickoff</th><th>CLV</th><th>Result</th></tr></thead><tbody>
        ${picks.map(p => `<tr><td>${esc(p.title)}<span class="sub">${esc(p.book || '')} ${odds(p.postedOdds)}</span></td><td>${p.postedLine ?? DASH}</td><td>${p.closeLine ?? DASH}${p.closeAt ? `<span class="sub">${esc(p.closeSource)} · ${esc(p.minutesBeforeKickoff)} min before</span>` : ''}</td>
          <td class="${p.clv > 0 ? 'up' : p.clv < 0 ? 'down' : ''}">${p.clv == null ? DASH : signed(p.clv)}</td><td>${esc(p.result || 'pending')}</td></tr>`).join('')}</tbody></table></div>` : empty('No picks yet', ''))}`;
  }

  /* ---------- the record ---------- */

  async function viewRecord() {
    const [data, board] = await Promise.all([get('app/today.json'), maybe('scoreboard.json')]);
    const clv = new Map((((board || {}).picks || {}).rows || []).map(r => [r.id, r]));
    const league = data.picks.filter(inLeague);
    gameIndex = new Map(data.games.map(g => [g.id, g]));
    const rec = C.theRecord(league);
    const accounting = C.recordBreakdown(league);
    const rq = state.recordQuery.trim().toLowerCase();
    const matches = p => !rq || [p.title, p.displayTitle, p.player, p.kind, p.result, p.book].some(v => String(v || '').toLowerCase().includes(rq));
    const newest = (a, b) => String(b.settledAt || b.publishedAt).localeCompare(String(a.settledAt || a.publishedAt));
    const settled = league.filter(p => p.result && !C.isUnpricedImport(p) && matches(p)).sort(newest);
    const imported = league.filter(p => p.result && C.isUnpricedImport(p)).sort(newest);
    /* The numbers behind the record, for anyone who wants them: the same plays, cut by sport, kind, week and market. */
    const counted = league.filter(p => !C.isUnpricedImport(p));
    const straight = counted.filter(p => !C.isParlay(p));
    const scoped = data.picks.filter(p => !C.isUnpricedImport(p) && !C.isParlay(p));
    const leagues = [['NFL', 'NFL'], ['CFB', 'College']].map(([id, name]) => [name, C.summaryOf(scoped.filter(p => p.league === id))]);
    const kinds = [['Researched plays', straight.filter(p => !p.modelLean)], ['Model plays', straight.filter(p => p.modelLean)],
      ['Fun parlays', counted.filter(p => C.isParlay(p) && !C.isLadder(p))]].map(([name, rows]) => [name, C.summaryOf(rows)]);
    const weeks = [...new Set(straight.map(p => C.weekOf(p.kickoff || p.publishedAt)).filter(Boolean))].sort().reverse()
      .map(w => [w, C.summaryOf(straight.filter(p => C.weekOf(p.kickoff || p.publishedAt) === w))]);
    const weekLabel = w => { const d = new Date(w + 'T12:00:00'); const e = new Date(d); e.setDate(d.getDate() + 6);
      return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} to ${e.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`; };
    const MARKET_NAME = { Totals: 'Game totals', Spreads: 'Spreads', Straights: 'Player props', 'Risky lines': 'Risky player lines' };
    const types = [...new Set(straight.map(C.category))].map(name => [MARKET_NAME[name] || name, C.summaryOf(straight.filter(p => C.category(p) === name))]);
    const table = (first, rows) => `<div class="table-wrap"><table class="data"><thead><tr><th>${esc(first)}</th><th>W–L–P</th><th>Units</th><th>Pending</th></tr></thead><tbody>${rows.map(([name, t]) =>
      `<tr><th scope="row">${esc(name)}</th><td class="num">${t.wins}–${t.losses}–${t.pushes}</td><td class="num ${unitTone(t.units)}">${unitText(t.units)}</td><td class="num">${t.pending}</td></tr>`).join('')}</tbody></table></div>`;
    return `${head('The record', `Every play we publish, graded win or lose. The same numbers go out on X.${state.league === 'ALL' ? '' : ` ${esc(leagueName(dataLeague()))} shown; switch sports at the top.`}`)}
      ${scoreTabs('official')}
      <div class="card transparent-record"><p class="eyebrow">All published straight plays · ${wl(accounting.all)}</p><div class="stats">
        ${stat('Captured prices', wl(accounting.captured), `${unitText(accounting.captured.units)} before promo credits`)}
        ${stat('Historical / assumed', wl(accounting.assumed), `${unitText(accounting.assumed.units)} at assumed prices`)}
        ${stat('Promo credits', unitText(accounting.credits), 'separate from betting returns')}
      </div><p class="row-meta">Same outcomes, separated price provenance. Parlays and the Climb remain separate.</p></div>
      <details class="card"><summary>Legacy combined totals · includes assumed prices and credits</summary>${theRecordCard(rec)}</details>
      ${section('The ladder', ladderCard(C.theLadder(data.picks)))}
      ${section('Every play', `<input class="search" type="search" data-input="recordQuery" placeholder="Search by player, team or market" value="${esc(state.recordQuery)}" aria-label="Search the plays">
        ${settled.length ? settledWeeks(settled, clv, Boolean(rq), weekLabel) : empty(rq ? 'No play matches' : 'Nothing settled yet', rq ? 'Try a player, a team or a market.' : 'Plays show here once their games are final.')}`)}
      <details class="card more-numbers"><summary>More numbers · legacy combined accounting</summary><div class="more-body"><p class="row-meta">These breakdowns include historical assumed prices and promotional credits. Use the captured-price headline above for returns before credits.</p>
        ${section('By sport', table('Sport', leagues))}
        ${section('By kind', table('Kind', kinds) + '<p class="row-meta" style="margin:8px 2px 0">Researched plays are backed by a checked news fact. Model plays go out on our number alone. Fun parlays are smaller tickets, just for fun, and stay out of the record.</p>')}
        ${weeks.length ? section('By week', table('Week', weeks.map(([w, t]) => [weekLabel(w), t]))) : ''}
        ${types.length > 1 ? section('By market', table('Market', types)) : ''}
        <p class="row-meta" style="margin:4px 2px 0">CLV compares the number we took with the last betting line before kickoff. Positive means we got a better number than the market closed at, which tends to show up before wins do.</p>
      </div></details>
      ${rec.imported ? `<details class="card week"><summary><span>Week 1 hand-posted legs (no prices)</span><span class="row-meta">${wl(rec.imported)}${rec.imported.voids ? `, ${rec.imported.voids} void` : ''} · not counted</span></summary>
        <div class="rows">${imported.map(p => settledRow(p, null)).join('')}</div></details>` : ''}`;
  }

  /* One settled play on one line: ✅ or ❌, the play, what happened, the price it was graded at and the units it won
     or lost. Tap for the full card. */
  const settledRow = (p, c) => {
    const u = C.unitsFor(p);
    const what = [p.actual ? String(typeof p.actual === 'string' ? p.actual : JSON.stringify(p.actual)).split(/[.;]\s/)[0] : '', c && c.clv != null ? `CLV ${signed(c.clv)}` : ''].filter(Boolean).join(' · ');
    return `<button class="row" type="button" data-pick="${esc(p.id)}">
      <span class="row-rail" style="background:${p.result === 'win' ? 'var(--green)' : p.result === 'loss' ? 'var(--rose)' : 'var(--line)'}"></span>
      <span class="row-main"><span class="row-top">${avatar(p, 'ava-row')}<span class="row-name">${MARKS[p.result] ? MARKS[p.result] + ' ' : ''}${esc(p.displayTitle || p.title || p.player)}</span>${p.featured && p.posted ? '<span class="pill pill-ours">Pick of the Day</span>' : ''}${p.earlyExit ? '<span class="pill pill-closed">Early exit credit</span>' : ''}${C.isLadder(p) ? '<span class="pill pill-ladder">Ladder</span>' : C.isParlay(p) ? '<span class="pill pill-stale">Fun parlay</span>' : ''}${p.historicalImport ? '<span class="pill pill-reference">Week 1</span>' : ''}</span>
        <span class="row-meta clamp">${esc(whenShort(p.kickoff || p.publishedAt))}${what ? ' · ' + esc(what) : ''}</span></span>
      ${C.isLadder(p) ? `<span class="row-price"><span class="row-odds num ${p.result === 'win' ? 'up' : p.result === 'loss' ? 'down' : ''}">${esc(money((p.ladder || {}).stake))} → ${esc(p.result === 'win' ? money((p.ladder || {}).payout) : p.result === 'loss' ? '$0' : money((p.ladder || {}).stake))}</span><span class="row-book">${esc(p.book || '')} ${odds(p.odds)}</span></span>`
        : `<span class="row-price"><span class="row-odds num ${unitTone(u)}">${u == null ? (p.odds == null ? '' : odds(p.odds)) : unitText(u)}</span><span class="row-book">${p.odds == null ? 'no price recorded' : p.priceAssumed ? `${odds(p.odds)} assumed` : `${esc(p.book || '')} ${odds(p.odds)}`}</span></span>`}
    </button>`;
  };
  /* Settled plays by week, newest first: this week open, the rest folded with their record, so the list never sprawls. */
  const settledWeeks = (settled, clv, searching, weekLabel) => {
    const byWeek = new Map();
    for (const p of settled) { const w = C.weekOf(p.kickoff || p.settledAt || p.publishedAt) || '0000-00-00'; if (!byWeek.has(w)) byWeek.set(w, []); byWeek.get(w).push(p); }
    return [...byWeek].sort((a, b) => b[0].localeCompare(a[0])).map(([w, rows], i) => {
      const t = C.summaryOf(rows.filter(p => !C.isParlay(p)));
      const label = w === '0000-00-00' ? 'Undated' : weekLabel(w);
      return `<details class="card week"${i === 0 || searching ? ' open' : ''}><summary><span>${esc(label)}</span><span class="row-meta">${played(t) ? wl(t) : 'fun parlays only'}${t.units == null ? '' : ` · ${unitText(t.units)}`} · ${rows.length} play${rows.length === 1 ? '' : 's'}</span></summary>
        <div class="rows">${rows.map(p => settledRow(p, clv.get(p.id))).join('')}</div></details>`;
    }).join('');
  };

  /* ---------- board and tickets ---------- */

  const PROP_MARKETS = [['all', 'All props'], ['receiving yards', 'Rec yards'], ['receptions', 'Receptions'], ['rushing yards', 'Rush yards'],
    ['carries', 'Carries'], ['passing yards', 'Pass yards']];

  async function viewBoard(route) {
    if (route && route.tab && route.tab !== state.boardMode) state.boardMode = route.tab;
    const [data, today] = await Promise.all([get('app/lines.json'), maybe('app/today.json')]);
    const ourPicks = ((today || {}).picks || []).filter(inLeague).filter(p => !p.result && !p.historicalImport)
      .sort((a, b) => (C.isOpen(b) - C.isOpen(a)) || String(a.kickoff).localeCompare(String(b.kickoff)));
    markPicks(ourPicks);
    const all = data.lines.filter(inLeague);
    const favorites = state.boardMode === 'favorites';
    const props = state.boardMode === 'props';
    const query = state.boardQuery.trim().toLowerCase();
    let shown = all.filter(l => favorites ? true : props ? Boolean(l.athleteId) : !l.athleteId)
      .filter(l => state.boardScope === 'settled' ? l.state === 'closed' : ['open', 'reference', 'unpriced'].includes(l.state));
    if (favorites) shown = shown.filter(l => l.state === 'open' && l.odds != null && l.grade && l.grade.calibrated
      && ['lean', 'strong'].includes(C.tierOf(l.grade)));
    if (props && state.propMarket !== 'all') shown = shown.filter(l => l.market === state.propMarket);
    if (query) shown = shown.filter(l => `${l.player || ''} ${l.title || ''} ${l.market || ''}`.toLowerCase().includes(query));
    /* Today first. With nothing left today, the next day that has lines stands in, and the header says so. */
    const todayLabel = dayLabel(new Date().toISOString());
    let dayNote = '';
    if (state.boardDay === 'today') {
      const upcomingLines = shown.filter(l => Date.parse(l.kickoff) > Date.now()).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
      const todayLines = upcomingLines.filter(l => dayLabel(l.kickoff) === todayLabel);
      if (todayLines.length) shown = todayLines;
      else if (upcomingLines.length) { const next = dayLabel(upcomingLines[0].kickoff); shown = upcomingLines.filter(l => dayLabel(l.kickoff) === next); dayNote = `Nothing left today; showing ${next}.`; }
      else shown = [];
    }
    const rank = { open: 0, reference: 1, stale: 2, unpriced: 3, closed: 4 };
    const byKickoff = (a, b) => String(a.kickoff).localeCompare(String(b.kickoff)) || String(a.player || a.title).localeCompare(String(b.player || b.title));
    shown = C.rankConfidence(shown);
    shown.sort((a, b) => (rank[a.state] - rank[b.state]) || (state.boardSort === 'best' ? C.byGrade(a, b) : 0)
      || (state.boardSort === 'confidence' ? C.byConfidence(a, b) : 0) || byKickoff(a, b));
    gameIndex = new Map(((today || {}).games || []).map(g => [g.id, g]));
    const valued = shown.filter(l => l.state === 'open' && l.grade && l.grade.calibrated && ['lean', 'strong'].includes(C.tierOf(l.grade))).length;
    const priced = shown.filter(l => l.state === 'open').length;
    const intro = favorites
      ? `${shown.length} current line${shown.length === 1 ? '' : 's'} clear our price checks.`
      : props
      ? `${shown.length} player lines${priced ? ` · ${priced} priced` : ''} · ${valued} highlighted.`
      : `${shown.length} game lines · ${valued} highlighted.`;
    /* By kickoff, lines group under their game so a slate reads top to bottom. */
    const groups = state.boardSort === 'time' ? [...shown.reduce((m, l) => { const k = l.gameId || 'other'; if (!m.has(k)) m.set(k, []); m.get(k).push(l); return m; }, new Map())] : null;
    /* A group's name comes from any row that spells out the matchup; a spread row only names one side. */
    const gameHead = rows => { const g = gameIndex.get(rows[0].gameId); const named = rows.map(r => String(r.title || '')).find(t => t.includes(' @ '));
      const name = g && g.away && g.home ? `${teamName(g.away)} at ${teamName(g.home)}` : named ? named.split(/ (over|under) /)[0] : rows.map(r => String(r.title || '').split(' ')[0]).filter((v, i, a) => a.indexOf(v) === i).join(' vs ');
      return `<p class="eyebrow" style="margin:12px 2px 6px">${esc(name)} · ${esc(whenShort(rows[0].kickoff))}</p>`; };
    const body = !shown.length ? empty(favorites ? 'No best line right now' : 'Nothing here yet', favorites
      ? 'Prices move. Check back when a line clears every current check.'
      : props ? 'Player lines land once the book posts them and a price is captured.' : 'Try another search or day.')
      : groups ? groups.map(([, rows]) => `${gameHead(rows)}<div class="card"><div class="rows">${rows.map(lineRow).join('')}</div></div>`).join('')
        : `<div class="card"><div class="rows">${shown.slice(0, 250).map(lineRow).join('')}</div></div>`;
    return `${head(favorites ? 'Best lines' : props ? 'Player props' : 'Game lines', intro)}
      ${boardTabs(favorites ? 'favorites' : props ? 'props' : 'lines')}
      <div class="toolbar">${seg('boardDay', [['today', 'Today'], ['week', 'This week']], state.boardDay)}${seg('boardSort', [['best', 'Best value'], ['confidence', 'Confidence'], ['time', 'By kickoff']], state.boardSort)}${seg('boardScope', [['open', 'Upcoming'], ['settled', 'Started']], state.boardScope)}</div>
      ${props ? `<div class="toolbar">${seg('propMarket', PROP_MARKETS, state.propMarket)}</div>` : ''}
      <p class="row-meta"><a href="#today">Official plays →</a> ${favorites ? 'These are the strongest current references, not posted plays.' : 'Everything below is for reference unless labeled as a play.'}</p>
      ${dayNote ? `<p class="row-meta" style="margin:0 0 8px">${esc(dayNote)}</p>` : ''}
      <details class="explainer"><summary>How to read the board</summary>
      <p class="row-meta" style="margin:8px 0 10px">Green rows are lines we like at the shown price. Confidence ranks the chance of winning; value ranks the difference between our estimate and the price. Tap a player for history and matchup. Nothing is official unless it is labeled as a play.</p></details>
      <input class="search" type="search" data-input="boardQuery" placeholder="Player, team or market" value="${esc(state.boardQuery)}" aria-label="Search lines">
      <div id="board-rows">${body}</div>
      <p class="row-meta" style="margin-top:10px">Tap + to save a line on this device.</p>`;
  }

  async function viewTicket() {
    const data = await get('app/lines.json');
    const current = new Map(data.lines.map(l => [l.id, l]));
    const rows = state.ticket.map(item => {
      const now = current.get(item.id);
      if (!now) return { ...item, state: 'closed', missing: true };
      return { ...now, changed: now.odds !== item.odds || now.line !== item.line, previous: item };
    });
    const summary = C.summarizeTicket(rows.filter(r => !r.changed), state.stake.amount, state.stake.mode, state.stake.unit);
    const money = n => '$' + Number(n).toFixed(2);
    return `${head('Your ticket', 'A personal draft that stays on this device. It is not a pick and never enters the record.')}
      ${rows.length ? `<div class="card"><div class="rows">${rows.map(r => `<div class="row" style="cursor:default"><span class="row-main"><span class="row-top"><span class="row-name">${esc(r.player || r.title)}</span>
          ${r.missing ? '<span class="pill pill-closed">Gone</span>' : r.changed ? '<span class="pill pill-stale">Price changed</span>' : ''}</span>
          <span class="row-market">${esc([r.direction, r.line, r.market].filter(v => v != null && v !== '').join(' '))}</span>
          <span class="row-meta">${esc(r.book || '')} ${odds(r.odds)}${r.changed ? ` · was ${esc(odds(r.previous.odds))}${r.previous.line !== r.line ? ' at ' + esc(r.previous.line) : ''}` : ''}</span></span>
          ${r.changed ? `<button class="btn" type="button" data-accept="${esc(r.id)}" style="align-self:center;margin-right:6px">Accept</button>` : ''}
          <button class="add" type="button" data-add="${esc(r.id)}" aria-pressed="true" aria-label="Remove">×</button></div>`).join('')}</div></div>` : empty('Your ticket is empty', 'Add current, priced lines from the board.', '<a class="btn" href="#board">Open the board</a>')}
      ${rows.length ? section('Stake', `<div class="card" style="padding:14px"><div class="toolbar">${seg('stakeMode', [['units', 'Units'], ['money', 'Dollars']], state.stake.mode)}</div>
        <div class="stats"><label class="field">Stake<input type="number" min="0" step="0.5" inputmode="decimal" data-stake="amount" value="${esc(state.stake.amount)}"></label>
        ${state.stake.mode === 'units' ? `<label class="field">Dollars per unit<input type="number" min="0" step="1" inputmode="decimal" data-stake="unit" value="${esc(state.stake.unit)}"></label>` : ''}</div>
        <div id="ticket-summary" style="margin-top:12px">${ticketSummary(summary, money)}</div>
        <div class="toolbar" style="margin-top:12px"><button class="btn" type="button" data-copy-ticket>Copy ticket text</button><button class="btn" type="button" data-clear-ticket>Clear</button></div></div>`) : ''}`;
  }

  const ticketSummary = (summary, money) => summary.available
    ? `<div class="stats">${stat('Illustrative price', odds(summary.odds), `${summary.decimal.toFixed(2)} decimal`)}${stat('Profit', summary.dollars ? money(summary.dollars.profit) : summary.profit.toFixed(2), summary.dollars ? `${summary.profit.toFixed(2)}u` : 'on your stake')}${stat('Return', summary.dollars ? money(summary.dollars.total) : summary.total.toFixed(2), 'stake included')}</div><p class="row-meta" style="margin:8px 0 0">${esc(summary.reason)}</p>`
    : `<div class="notice">${esc(summary.reason)}</div>`;

  /* ---------- research ---------- */

  async function viewResearch() {
    const [data, today] = await Promise.all([get('app/research.json'), get('app/today.json')]);
    const league = dataLeague();
    const inj = data.injuries[league] || {};
    const teams = Object.entries(inj.teams || {}).sort((a, b) => String(a[1].name).localeCompare(String(b[1].name)));
    const notes = data.notes.filter(n => state.league === 'ALL' || n.league === state.league);
    const gameName = id => { const g = today.games.find(x => x.id === id); return g ? `${g.away.abbr} @ ${g.home.abbr}` : id; };
    const text = item => typeof item === 'string' ? item : item.text || item.summary || JSON.stringify(item);
    const changes = data.changes.filter(c => c.league === league).slice(-12).reverse();
    return `${head('Research desk', 'Injuries, status changes and matchup notes.')}
      ${section(`${leagueName(league)} injury report`, league === 'CFB' ? '<p class="row-meta">College injury updates are limited. Verify with team reports.</p>' : teams.length ? `<div class="card"><div class="rows">${teams.map(([, t]) => `<details class="row" style="display:block;cursor:default"><summary style="padding:12px;cursor:pointer"><b>${esc(t.name)}</b> <span class="row-meta">${t.players.length} listed</span></summary>
          <div style="padding:0 12px 12px">${t.players.map(p => `<div class="row-meta" style="padding:3px 0"><span class="pill ${/out|reserve/i.test(p.status) ? 'pill-out' : 'pill-q'}">${esc(p.status)}</span> <b style="color:var(--text)">${esc(p.name)}</b> ${esc(p.position || '')} · ${esc(p.injury || 'not listed')} · ${esc(ago(p.reportedAt))}</div>`).join('')}</div></details>`).join('')}</div></div>
          <p class="row-meta" style="margin-top:8px">Updated ${esc(ago(inj.checkedAt))}.</p>` : empty('Nobody listed', 'No recent injury updates.'))}
      ${changes.length ? section('Status changes', `<div class="card"><div class="rows">${changes.map(c => `<div class="row" style="cursor:default"><span class="row-main"><span class="row-name">${esc(c.name)}</span><span class="row-market">${esc(c.from)} → ${esc(c.to)}</span><span class="row-meta">${esc(ago(c.observedAt))}</span></span></div>`).join('')}</div></div>`) : ''}
      ${section('Analyst notes', notes.length ? notes.map(n => `<div class="card" style="padding:14px;margin-bottom:8px"><p class="eyebrow">${esc(leagueName(n.league))} · ${esc(when(n.publishedAt))}</p>
          ${n.takeaways.length ? `<ul class="list">${n.takeaways.map(t => `<li>${esc(text(t))}</li>`).join('')}</ul>` : ''}
          ${n.weeklyReview.length ? `<p class="eyebrow" style="margin-top:10px">Review</p><ul class="list">${n.weeklyReview.map(t => `<li>${esc(text(t))}</li>`).join('')}</ul>` : ''}
          ${n.watch.length ? `<p class="eyebrow" style="margin-top:10px">Watching</p><ul class="list">${n.watch.map(w => `<li><b>${esc(w.title)}</b>${w.gameId ? ` (<a href="#game/${esc(w.gameId)}">${esc(gameName(w.gameId))}</a>)` : ''}: ${esc(w.why || '')}${w.needs ? ` <span class="faint">Needs: ${esc(Array.isArray(w.needs) ? w.needs.join('; ') : w.needs)}</span>` : ''}</li>`).join('')}</ul>` : ''}</div>`).join('')
        : empty('No notes yet', 'Notes appear when the research run publishes.'))}`;
  }

  /* ---------- multi-sport scores ---------- */

  const SCORE_LEAGUES = ['NBA', 'WNBA', 'CBB', 'MLB', 'NHL', 'EPL', 'MLS'];
  const SCORE_NAMES = { NBA: 'NBA', WNBA: 'WNBA', CBB: 'College hoops', MLB: 'MLB', NHL: 'NHL', EPL: 'Premier League', MLS: 'MLS' };

  async function viewScores(route) {
    const data = await get('sports.json');
    const league = SCORE_LEAGUES.includes(route.league) ? route.league : state.scoresLeague;
    const block = (data.leagues || {})[league] || {};
    const stored = (block.games || []).slice().sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    const days = [...new Set(stored.map(g => g.date))];
    const day = days.includes(state.scoresDate) ? state.scoresDate : days[0];
    const snapshot = day ? await liveSnapshot(league, day) : null;
    const fresh = new Map(((snapshot || {}).games || []).map(g => [g.providerId, g]));
    const games = stored.map(g => { const now = fresh.get(String(g.providerId)); return now ? { ...g, status: now.status,
      statusDetail: now.statusDetail, period: now.period, clock: now.clock,
      scores: { away: now.teams.away.score, home: now.teams.home.score }, updatedAt: new Date(snapshot.at).toISOString() } : g; });
    const shown = games.filter(g => g.date === day);
    const side = (team, score) => `<div class="game-team">${team.logo ? `<img class="score-logo" src="${esc(team.logo)}" alt="">` : ''}<span>${esc(team.abbreviation || team.shortName || DASH)}</span>${score != null ? `<span class="score" style="margin-left:auto">${esc(score)}</span>` : ''}</div>`;
    const chips = SCORE_LEAGUES.map(key => `<a class="chip" href="#scores/${key}" aria-pressed="${league === key}" style="display:inline-flex;align-items:center">${esc(SCORE_NAMES[key])}</a>`).join('');
    return `${head(`${SCORE_NAMES[league] || league} scores`, 'Schedules and scores. No picks are implied.')}${liveStamp(snapshot && snapshot.at)}
      <div class="toolbar"><div class="seg score-leagues" role="group">${chips}</div>
        ${days.length ? seg('scoresDate', days.map(d => [d, new Date(d + 'T12:00:00Z').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' })]), day) : ''}</div>
      ${shown.length ? `<div class="card">${shown.map(g => `<div class="game-row"><span class="game-teams score-teams">${side(g.teams.away, (g.scores || {}).away)}${side(g.teams.home, (g.scores || {}).home)}</span>
          <span class="game-mid">${esc(g.statusDetail || g.status)}</span>${external((g.source || {}).url, 'ESPN')}</div>`).join('')}</div>`
        : empty(`No ${league} games in the window`, block.status === 'ok' ? 'The provider returned no games for these dates.' : 'The feed is unavailable; the last good data is kept.')}`;
  }

  /* ---------- the multi-sport buildout ---------- */

  async function viewLab() {
    const [data, market] = await Promise.all([get('sports.json'), maybe('market-lab.json')]);
    const available = data.leagues || {};
    const progress = league => {
      const row = ((market || {}).leagues || {})[league];
      if (!row || !row.gamesQuoted) return 'Market capture armed; waiting for the next supplied pregame line.';
      return `${row.gamesQuoted} game${row.gamesQuoted === 1 ? '' : 's'} quoted · ${row.snapshots} changed snapshot${row.snapshots === 1 ? '' : 's'} · ${row.gamesGraded} final${row.gamesGraded === 1 ? '' : 's'} joined`;
    };
    const stage = (league, name, status, tone, copy, labProgress = '') => {
      const block = available[league] || {};
      const count = (block.games || []).length;
      const feed = block.status === 'ok' ? `${count} game${count === 1 ? '' : 's'} in the three-day window` : 'score feed waiting';
      return `<article class="lab-card card"><div class="lab-card-head"><h3>${esc(name)}</h3><span class="pill ${tone}">${esc(status)}</span></div><p>${esc(copy)}</p>${labProgress ? `<p class="lab-progress">${esc(labProgress)}</p>` : ''}<a href="#scores/${league}">${esc(feed)} →</a></article>`;
    };
    return `${head("Kook'n Lab", 'New sports and features in progress.')}
      <div class="lab-hero card"><p class="eyebrow">Coming next</p><h2>More sports. Same clear card.</h2><p>Football is live. Basketball and the next group of sports are being prepared before they join the public card.</p></div>
      ${section('Live-game updates', `<div class="card"><div class="row" style="cursor:default"><span class="row-main"><span class="row-top"><span class="row-name">Play progress</span><span class="pill pill-q">Testing</span></span><span class="row-market">Early hits, close calls and finals are being tested for clean live updates.</span></span></div></div>`)}
      ${section('Football experiments', `<div class="lab-grid">
        <article class="lab-card card"><div class="lab-card-head"><h3>Team totals</h3><span class="pill pill-q">Testing</span></div><p>Team total lines and projections are being added to game pages.</p></article>
        <article class="lab-card card"><div class="lab-card-head"><h3>Touchdown scorers</h3><span class="pill pill-q">Testing</span></div><p>Touchdown watch is live on game pages. Priced scorer cards are coming later.</p></article>
        <article class="lab-card card"><div class="lab-card-head"><h3>Alternate-line streaks</h3><span class="pill pill-reference">Planned</span></div><p>Main-line trends are live. More verified alternate lines are next.</p></article>
      </div>`)}
      ${section('Across every season', `<div class="lab-grid">
        <article class="lab-card card"><div class="lab-card-head"><h3>Season futures</h3><span class="pill pill-reference">Planned</span></div><p>Championship, division or conference, playoff and season-total markets will get their own preseason tracker as each sport is added.</p><p class="lab-progress">Original price, book, date and every later move will be preserved. Research watches stay separate from official plays.</p></article>
      </div>`)}
      ${section('In the kitchen', `<div class="lab-grid">
        ${stage('NBA', 'NBA', 'Testing', 'pill-q', 'Lines, projections and results are being prepared for the regular season.')}
        ${stage('CBB', 'College basketball', 'Testing', 'pill-q', 'College totals are being prepared for November.')}
        ${stage('EPL', 'Premier League', 'Research', 'pill-closed', 'Soccer coverage is being evaluated for a future card.')}
        ${stage('MLB', 'MLB', 'Building', 'pill-q', 'Pregame lines and final scores are being collected for a future launch.', progress('MLB'))}
        ${stage('NHL', 'NHL', 'Building', 'pill-q', 'Pregame lines and final scores are being collected for a future launch.', progress('NHL'))}
        ${stage('WNBA', 'WNBA', 'Score center', 'pill-reference', 'Schedules and results are live. More features are planned.')}
        ${stage('MLS', 'MLS', 'Score center', 'pill-reference', 'Schedules and results are live. More features are planned.')}
      </div>`)}
      <div class="notice">A new sport joins the public card only after a full private trial and owner approval.</div>`;
  }

  /* ---------- Discord radar, public calculator ---------- */

  const dollars = value => {
    const n = Number(value);
    return Number.isFinite(n) ? `${n < 0 ? '−' : ''}$${Math.abs(n).toFixed(2)}` : DASH;
  };
  const arbSummary = result => {
    if (!result.valid) return `<div class="arb-result arb-wait"><p class="eyebrow">Waiting for prices</p><h3>Enter both sides</h3><p>${esc(result.reason)}</p></div>`;
    const title = result.arb ? 'The math shows an arb' : 'These prices are not an arb';
    const note = result.arb
      ? `${dollars(result.profit)} remains if either side wins and both bets are accepted and settled as expected.`
      : `The implied chances total ${result.implied.toFixed(2)}%. They must be below 100% for a locked return.`;
    return `<div class="arb-result ${result.arb ? 'arb-yes' : 'arb-no'}"><p class="eyebrow">${result.arb ? 'Positive split' : 'No locked return'}</p><h3>${title}</h3>
      <div class="stats arb-stats">${stat('Side A stake', dollars(result.firstStake))}${stat('Side B stake', dollars(result.secondStake))}${stat('Lowest return', dollars(result.return))}${stat(result.arb ? 'Difference' : 'Shortfall', dollars(result.profit), `${result.roi > 0 ? '+' : ''}${result.roi.toFixed(2)}%`)}</div>
      <p>${esc(note)}</p></div>`;
  };

  function viewArbs() {
    const result = C.arbSplit(state.arb.first, state.arb.second, state.arb.bankroll);
    return `${head("Kook'n Arb Radar", 'Two books. Every outcome covered. Exact math—with the catches left in.')}
      <div class="arb-hero card"><div><span class="radar-dot" aria-hidden="true"></span><span class="pill pill-reference">Discord alerts</span></div>
        <h2>We scan. We verify. We do not chase stale numbers.</h2>
        <p>The radar sends time-sensitive candidates only to Discord. A candidate never becomes a Kook’n play, and this page never claims a price is still available.</p>
        <div class="arb-guard"><span><b>Exact markets</b><small>Same event, period and line</small></span><span><b>Different books</b><small>Both sides priced from feeds</small></span><span><b>Human check</b><small>Apps, limits and rules first</small></span></div>
      </div>
      ${section('Check the math', `<div class="card arb-calc"><div class="arb-fields">
          <label class="field">Side A American odds<input inputmode="numeric" type="number" step="1" data-arb="first" value="${esc(state.arb.first)}" aria-label="Side A American odds"></label>
          <label class="field">Side B American odds<input inputmode="numeric" type="number" step="1" data-arb="second" value="${esc(state.arb.second)}" aria-label="Side B American odds"></label>
          <label class="field">Total bankroll<input inputmode="decimal" type="number" min="0.01" step="0.01" data-arb="bankroll" value="${esc(state.arb.bankroll)}" aria-label="Total bankroll"></label>
        </div><div id="arb-summary">${arbSummary(result)}</div></div>`)}
      ${section('The non-negotiables', `<div class="card arb-rules"><ol><li><b>Exact means exact.</b> Same event, market, period and line. A middle is not labeled an arb.</li>
        <li><b>Both bets must still exist.</b> Prices can disappear before the second bet is accepted.</li>
        <li><b>Settlement rules must match.</b> Voids, limits, account restrictions and different house rules can break the math.</li>
        <li><b>No automatic wagering.</b> The radar never touches a sportsbook account or places a bet.</li></ol></div>`)}
      <div class="notice arb-notice"><strong>Entertainment and calculation only.</strong> This calculator does not know whether either price is available to you. Verify the exact event, market, line, period, price, limits and settlement rules in both apps before doing anything.</div>`;
  }

  /* ---------- more ---------- */

  async function viewTrends(route) {
    const data = await get('app/trends.json');
    const windowed = C.trendWindow(C.bestTrendPrices(data.rows || []), state.trendWindow);
    const rows = C.filterTrends(windowed, { rate: state.trendRate, stat: state.trendStat,
      kind: state.trendKind, min: 3, league: state.league, query: state.trendQuery, game: route.id,
      day: route.id ? 'all' : state.trendDay });
    const select = (key, title, options) => `<label>${title}<select data-select="${key}">${options.map(([v, t]) => `<option value="${v}" ${state[key] === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>`;
    const windowLabel = state.trendWindow === 'last5' ? 'Last 5' : state.trendWindow === 'last10' ? 'Last 10' : 'This season';
    const cards = rows.slice(0, 150).map(r => `<article class="card trend-card">
      <div class="trend-top"><a href="#player/${esc(r.league)}/${esc(r.athleteId)}"><img class="trend-photo" src="https://a.espncdn.com/i/headshots/${r.league === 'NFL' ? 'nfl' : 'college-football'}/players/full/${esc(r.athleteId)}.png" alt="" loading="lazy"><b>${esc(r.player)}</b></a><span class="trend-rate">${r.rate}%<small>${r.hits}/${r.games} games</small></span></div>
      <h2>${esc(r.title)}</h2><p class="row-meta">${esc(r.team.name || r.team.abbr || '')} · ${esc(windowLabel)}${r.injuryStatus ? ` · Injury report: ${esc(r.injuryStatus)}` : ''}</p>
      <p>${r.kind === 'milestone' ? '<span class="pill">Stat milestone</span> <span class="row-meta">No verified price</span>' : `<span class="pill pill-ours">${r.kind === 'alternate' ? 'Alternate' : 'Main line'}</span> <b>${odds(r.odds)} ${esc(r.book)}</b> <span class="row-meta">captured ${esc(ago(r.observedAt))} · verify in book</span>`}</p>
      <a class="row-meta" href="#game/${esc(r.gameId)}">${esc(r.matchup)} · ${esc(whenShort(r.kickoff))} →</a>
      <details><summary>See ${esc(windowLabel.toLowerCase())}: ${r.hits}/${r.games} hit${r.games < 5 ? ' · small sample' : ''}</summary><p class="row-meta">Recorded regular-season appearances, not head-to-head history. Missing appearances are not assumed played. Injury exits count when a stat is recorded. ${r.pushes ? `${r.pushes} statistical ties counted in the denominator, not as hits.` : ''}</p><div class="trend-log">${r.history.map(h => `<span><small>${esc(h.date)}</small><b>${h.value}</b></span>`).join('')}</div><p class="row-meta">Check current role, injury status and opponent strength, especially in college.</p><a href="#player/${esc(r.league)}/${esc(r.athleteId)}">Full player research →</a></details>
    </article>`).join('');
    return `${head('Trends', 'Main lines first. Switch the history window to see what has held up lately.')}${boardTabs('trends')}
      <div class="card trend-controls">
        <div class="trend-filter-group"><p class="eyebrow">Hit rate</p>${seg('trendRate', [['70','70%+'],['80','80%+'],['90','90%+'],['100','100%']], state.trendRate)}</div>
        <div class="trend-filter-group"><p class="eyebrow">History</p>${seg('trendWindow', [['season','This season'],['last10','Last 10'],['last5','Last 5']], state.trendWindow)}</div>
        <div class="trend-filter-group"><p class="eyebrow">Line</p>${seg('trendKind', [['main','Main lines'],['alternate','Alternates'],['milestone','Milestones']], state.trendKind)}</div>
        <div class="trend-selects">${select('trendStat','Stat',[['all','All stats'],['rec','Receptions'],['recYds','Receiving yards'],['rushYds','Rushing yards'],['passYds','Passing yards'],['car','Carries'],['att','Pass attempts'],['cmp','Completions']])}</div>
      ${route.id ? '' : `<div class="trend-filter-group"><p class="eyebrow">Games</p>${seg('trendDay', [['all','All upcoming'],['today','Today']], state.trendDay)}</div>`}<input aria-label="Search players or teams" placeholder="Search player or team" data-input="trendQuery" value="${esc(state.trendQuery)}"></div>
      <p class="row-meta">${rows.length} ${state.trendKind === 'main' ? 'main-line ' : ''}trend${rows.length === 1 ? '' : 's'} · ${esc(windowLabel)} · updated ${esc(ago(data.generatedAt))}. Verify current prices.${route.id ? ' <a href="#trends">Show all games →</a>' : ''}</p>
      <details class="card trend-method"><summary>How to read this</summary><p>The fraction is exact for the selected history window. 100% means the player cleared the listed number in every recorded game shown—not that it is guaranteed next game. Main lines and alternates require a recent sportsbook quote; milestones are unpriced stats.</p></details>
      ${cards ? `<div class="trend-grid">${cards}</div>${rows.length > 150 ? '<p class="row-meta">Showing the first 150. Narrow by stat, player or line type to see more.</p>' : ''}` : empty('No trends match these filters', 'Try another history window, hit rate, stat or line type. Missing and old quotes stay hidden.')}`;
  }

  async function viewMore() {
    const data = await maybe('app/today.json');
    const count = state.ticket.length;
    const link = (href, label, note) => `<a href="${href}"${href.startsWith('http') ? ' target="_blank" rel="noopener"' : ''}><span>${label}</span><small>${note}</small></a>`;
    return `${head('More', '')}${communityCard()}
      <div class="card menu">${link('https://discord.gg/CvNTUUSnNz', 'Join the Discord', 'Confirmed plays early plus time-sensitive arb alerts')}${link('https://x.com/keenkooks', 'Follow on X', '@keenkooks')}${link('#lab', "Kook'n Lab", 'What’s coming next')}${link('#arbs', "Kook'n Arb Radar", 'Discord alerts and public calculator')}${link('#model', 'Model results', 'Pregame forecasts graded after the game')}${link('#ticket', 'Your ticket', count ? `${count} line${count === 1 ? '' : 's'}` : 'Parlay builder')}
      ${link('#trends', 'Season trends', '70 / 80 / 90 / 100% historical lines')}${link('#research', 'Research desk', 'Injuries and analyst notes')}${link('#scores/MLB', 'All sports scores', 'NBA, WNBA, college hoops, MLB, NHL, Premier League and MLS')}${link('#schedule', 'Posting schedule', 'When plays, research and results appear')}</div>
      ${data ? section('Data status', freshnessCard(data)) : ''}
      <div class="section card" style="padding:14px"><p class="prose" style="margin:0"><b>About Kook'n.</b> Plays, lines, projections and results in one place. Every official play is graded publicly. For entertainment only.</p></div>`;
  }

  async function viewSchedule() {
    const row = (time, title, note) => `<div class="row schedule-row" style="cursor:default"><span class="schedule-time num">${esc(time)}</span><span class="row-main"><span class="row-name">${esc(title)}</span><span class="row-meta">${esc(note)}</span></span></div>`;
    return `${head('Posting schedule', 'The rhythm is fixed. A play still has to clear its line, price and news checks.')}
      ${section('Every game day', `<div class="card"><div class="rows">
        ${row('8:45 AM', 'Today’s menu', 'Only when approved plays are already ready.')}
        ${row('9:00 AM', 'Results', 'The prior card, win or lose. Wednesday also includes the weekly recap.')}
        ${row('10:00 AM', 'Saveable slate sheet', 'College Saturday and NFL Sunday.')}
        ${row('10:30 AM', 'Research', 'One useful trend, matchup, injury or underdog card when evidence qualifies.')}
        ${row('Around noon', 'Official plays', 'Earlier kickoffs move up. Discord normally sees confirmed plays 10–15 minutes before X.')}
        ${row('After results', 'Cashed and Climb updates', 'Wins may post after settlement. Losses stay in the public receipt.')}
        ${row('6:00 PM', 'Quiet-day record', 'Used only when nothing more useful posted that day.')}
      </div></div>`)}
      ${section('80/20 Climb', `<div class="card"><div class="rows">
        ${row('10:00 AM', 'Rung scan', 'A ticket posts only when two independent legs qualify.')}
        ${row('1:30 PM', 'Rung scan', 'A settled rung may advance the same day.')}
        ${row('4:00 PM', 'Rung scan', 'Later slates stay available without forcing a step.')}
        ${row('8:00 PM', 'Rung scan', 'The last scheduled daily check.')}
      </div></div>`)}
      <div class="notice"><b>What “scheduled” means.</b> These are release windows, not promised picks. Prices can move and news can pull a queued play. Discord is the first alert for confirmed plays; X carries the public post and every result.</div>`;
  }

  /* ---------- pick details ---------- */

  async function openPick(id) {
    const [data, board] = await Promise.all([get('app/today.json'), maybe('scoreboard.json')]);
    const p = data.picks.find(x => x.id === id);
    if (!p) return;
    const clv = (((board || {}).picks || {}).rows || []).find(r => r.id === id);
    const dialog = $('#detail');
    const hostOf = (url, i) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch (e) { return 'Source ' + (i + 1); } };
    /* Reports are hand-written JSON: a field may be text, a list or an object. Show whichever it is as text. */
    const prose = v => v == null ? '' : typeof v === 'string' ? v : Array.isArray(v) ? v.map(prose).join(' · ')
      : typeof v === 'object' ? Object.entries(v).map(([k, x]) => `${k}: ${prose(x)}`).join(' · ') : String(v);
    const leg = l => typeof l === 'string' ? l : l.title || [l.player, l.direction, l.line, l.market].filter(x => x != null && x !== '').join(' ');
    const closed = !p.result && !p.historicalImport && C.pickState(p).tone === 'closed';
    const started = p.kickoff && Date.parse(p.kickoff) <= Date.now();
    const frozen = p.probabilityAtPublication;
    const reasoning = p.reasoning;
    const evidenceNote = reasoning ? `<h4>History and matchup</h4><p>${esc(reasoning.history || '')}</p><ul>${(reasoning.context || []).map(s => `<li>${esc(s)}</li>`).join('')}</ul><p class="row-meta">${esc(reasoning.historyNote || '')}</p>` : '';
    const probabilityNote = frozen && frozen.calibrated
      ? `<h4>Price snapshot</h4><div class="kv"><div><span>Estimate</span><strong>${(100 * frozen.chance).toFixed(1)}%</strong></div><div><span>Price needs</span><strong>${(100 * frozen.breakEven).toFixed(1)}%</strong></div><div><span>Difference</span><strong>${signed(frozen.edgePoints)} pts</strong></div></div><p class="row-meta">Saved when posted.</p>`
      : '';
    dialog.innerHTML = `<div class="detail-inner"><div class="detail-head"><div><div class="row-top">${p.result ? `<span class="pill pill-${p.result === 'win' ? 'win' : p.result === 'loss' ? 'loss' : 'closed'}">${esc(p.result)}</span>` : '<span class="pill pill-ours">Our pick</span>'}</div>
      <h3 style="margin:7px 0 0;font-size:17px">${esc(p.title)}</h3><p class="row-meta" style="margin:4px 0 0">${esc(when(p.kickoff || p.publishedAt))}</p></div><button class="close" type="button" data-close aria-label="Close">×</button></div>
      <div class="detail-body"><div class="kv"><div><span>Price</span><strong>${esc(p.book || 'No book')} ${odds(p.odds)}</strong></div><div><span>We project</span><strong>${p.projection ?? DASH}</strong></div><div><span>Quoted</span><strong style="font-size:12px">${esc(ago(p.quotedAt))}</strong></div></div>
      ${p.priceAssumed ? `<div class="notice" style="margin-top:12px"><strong>Price assumed.</strong> ${esc(p.priceNote || 'No price was recorded for this play, so it counts at an assumed -115.')}</div>` : ''}
      ${closed ? `<div class="notice" style="margin-top:12px"><strong>Closed to new entries.</strong> ${esc(prose(p.entryNote) || (p.status === 'withdrawn' ? 'Withdrawn before kickoff.' : started ? 'The game has started.' : 'The quote has expired.'))} The original is still graded at its published price.</div>` : ''}
      ${clv && clv.clv != null ? `<div class="notice" style="margin-top:12px"><strong>Closing line value ${signed(clv.clv)}.</strong> We posted ${clv.postedLine ?? DASH} and the last number before kickoff was ${clv.closeLine ?? DASH}. ${clv.clv > 0 ? 'We got the better number, which is the part we control.' : clv.clv < 0 ? 'The market moved to a better number after we posted.' : 'We matched the close.'}</div>` : ''}
      ${(p.legs || []).length ? `<h4>Legs</h4><ul style="margin:0;padding-left:18px">${p.legs.map(l => `<li>${esc(leg(l))}</li>`).join('')}</ul>` : ''}${p.correlation ? `<h4>How the legs relate</h4><p>${esc(prose(p.correlation))}</p>` : ''}
      ${probabilityNote}${evidenceNote}${p.priceEstimated ? '<p>Combined odds are estimated from captured leg prices. Verify the actual ticket price at the sportsbook.</p>' : ''}
      ${p.cutoff ? `<h4>Cutoff</h4><p>${esc(prose(p.cutoff))}</p>` : ''}${p.why ? `<h4>Reason</h4><p>${esc(prose(p.why))}</p>` : ''}${p.risk ? `<h4>Risk</h4><p>${esc(prose(p.risk))}</p>` : ''}${p.edge ? `<h4>Edge</h4><p>${esc(prose(p.edge))}</p>` : ''}
      ${p.actual ? `<h4>Result</h4><p>${esc(prose(p.actual))}</p>` : ''}${p.settlementReason ? `<p>${esc(prose(p.settlementReason))}</p>` : ''}
      ${(p.sources || []).length ? `<h4>Sources</h4><div class="sources">${p.sources.filter(s => /^https:/.test(s)).map((s, i) => `<a href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(hostOf(s, i))} ↗</a>`).join('')}</div>` : ''}
      ${p.athleteId ? '<div data-context><p class="row-meta">Loading the last ten games and the matchup…</p></div>' : ''}
      <p class="row-meta" style="margin-top:14px">${C.isParlay(p) ? 'A fun parlay: a smaller stake, kept out of the record.' : 'Graded at one unit, at the line and price we published.'} The original price is kept for grading even after the line moves.</p></div></div>`;
    dialog.showModal();
    if (p.athleteId) {
      const html = await propContext(p);
      const box = dialog.querySelector('[data-context]');
      if (box) box.innerHTML = html;
    }
  }

  /* ---------- a player line in context ---------- */

  const ordinal = n => n === 1 ? '1st' : n === 2 ? '2nd' : n === 3 ? '3rd' : `${n}th`;
  const newestFirst = rows => [...rows].sort((a, b) => String(b[1]).localeCompare(String(a[1])));

  /* Everything a person wants beside a player line: the last ten games against the number, where the
     player sits on his team, and what this defense has given up to the position. Built on demand from
     the same shards the player pages use, so the card never shows a number the site cannot show elsewhere.
     For a game already played it shows only what was known before kickoff. */
  async function propContext(row) {
    const league = row.league === 'CFB' || String(row.gameId || '').startsWith('CFB') ? 'CFB' : 'NFL';
    const key = C.marketKey(row);
    const direction = String(row.direction || '').toLowerCase() === 'under' ? 'under' : 'over';
    const [index, teams, game] = await Promise.all([maybe(`app/players/${league}.json`), maybe(`app/teams/${league}.json`),
      row.gameId ? maybe(`app/games/${row.gameId}.json`) : null]);
    if (!index || !teams) return '<p class="row-meta">Player history is unavailable right now.</p>';
    const shard = await maybe(`app/players/${league}/${C.shardOf(row.athleteId, index.shards)}.json`);
    const data = shard && shard.players[row.athleteId];
    const keys = shard ? shard.keys : [];
    const kickoffDay = row.kickoff ? String(row.kickoff).slice(0, 10) : null;
    const rows = data ? data.rows.filter(r => !kickoffDay || String(r[1]) < kickoffDay) : [];
    const abbr = id => (teams.teams[id] || {}).abbr || id;
    const latest = newestFirst(rows)[0];
    const teamId = latest ? String(latest[5]) : null;
    const pos = C.POS_GROUP[row.position] || C.POS_GROUP[data ? data.pos : ''] || null;
    const side = game && game.home && teamId === String(game.home.id) ? 'home' : game && game.away && teamId === String(game.away.id) ? 'away' : null;
    const opp = side ? String(game[side === 'home' ? 'away' : 'home'].id) : null;
    const line = typeof row.line === 'number' ? row.line : null;
    const label = (C.LABEL[key] || row.market || 'this stat').toLowerCase();

    /* the last ten */
    const recent = newestFirst(rows).slice(0, 10).reverse();
    const values = recent.map(r => C.cell(r, keys, key));
    const win = key && rows.length ? C.windows(rows, keys, key) : {};
    const hitWords = h => h && h.n ? `${direction === 'under' ? h.under : h.over} of ${h.n} ${direction}` : null;
    const h10 = line != null ? C.hits(values, line) : null, h5 = line != null ? C.hits(values.slice(-5), line) : null;
    const formLine = [hitWords(h10) ? `${hitWords(h10)} ${line}` : null, hitWords(h5) ? `${hitWords(h5)} in the last 5` : null,
      win.last10 ? `last 10 average ${fixed(win.last10.avg)}` : null, win.season ? `this season ${fixed(win.season.avg)}` : null].filter(Boolean).join(' · ');

    /* the role */
    const block = side && game.forecast ? (game.forecast.players[side] || {}) : {};
    const role = C.roleOf(block.players || [], row.athleteId, pos, key);
    const me = (block.players || []).find(p => String(p.id) === String(row.athleteId));
    const season = index.season;
    const thisSeason = rows.filter(r => r[2] === season).length;
    const lastSeason = teamId ? rows.filter(r => r[2] === season - 1 && String(r[5]) === teamId).length : 0;
    const snap = latest ? C.cell(latest, keys, 'snapPct') : null;
    const roleBits = [pos ? `${pos}${teamId ? ' · ' + abbr(teamId) : ''}` : null,
      role ? `${ordinal(role.rank)} of ${role.of} ${pos}s by projected ${(C.LABEL[role.stat] || role.stat).toLowerCase()} (${fixed(role.volume)})` : null,
      `${thisSeason} game${thisSeason === 1 ? '' : 's'} this season${lastSeason ? `, ${lastSeason} for ${abbr(teamId)} last season` : ''}`,
      snap != null ? `${Math.round(100 * snap)}% of snaps last game` : null,
      (row.grade && row.grade.limited) || (me && me.limited) ? 'questionable on the report' : null].filter(Boolean);

    /* the defense */
    const dRows = (teams.defense || {}).rows || {};
    const rank = opp && pos && key ? C.rankOf(dRows, opp, pos, key) : null;
    const last5 = opp && pos && key ? ((((teams.defense || {}).last5 || {})[opp] || {})[pos] || {})[key] : null;
    const prior = opp && pos && key ? C.rankOf(((teams.defense || {}).prior || {}).rows || {}, opp, pos, key) : null;
    const tone = rank ? C.rankTone(rank.rank, rank.of) : 'neutral';
    const oppFile = opp ? await maybe(`app/teams/${league}/${opp}.json`) : null;
    const allowed = oppFile ? (oppFile.defense || []).filter(d => d.season === (teams.defense || {}).season && (!kickoffDay || d.date < kickoffDay)) : [];
    const homeOf = new Map((oppFile ? oppFile.games || [] : []).map(g => [g.gameId, g.home]));
    const dRecent = allowed.map(d => [d.gameId, d.date, d.season, d.week, 2, opp, d.opp, homeOf.get(d.gameId) === false ? 0 : homeOf.get(d.gameId) == null ? -1 : 1]);
    const dValues = allowed.map(d => pos && d.allowed[pos] && d.allowed[pos][key] != null ? d.allowed[pos][key] : null);
    const vs = opp && key && rows.length ? C.splits(rows, keys, key, opp).vs : null;
    const rankWord = tone === 'soft' ? 'among the most generous' : tone === 'tough' ? 'among the stingiest' : 'middle of the pack';

    return `<h4>Last ${values.length || 10} games · ${esc(C.LABEL[key] || row.market || '')}</h4>
      ${values.length ? chart(recent, values, line, abbr) : empty('No games stored yet', kickoffDay ? 'Nothing recorded for this player before this game.' : 'The first stat line appears after a game.')}
      ${formLine ? `<p>${esc(formLine)}. History, not a probability.</p>` : ''}
      <h4>Role</h4><p>${esc(roleBits.join(' · '))}.</p>
      ${opp ? `<h4>What ${esc(abbr(opp))} allows ${esc(pos || '')}s</h4>
        ${rank ? `<p>${esc(abbr(opp))} allow <b>${fixed(rank.value)}</b> ${esc(label)} a game to ${esc(pos)}s this season, <span class="${tone === 'soft' ? 'up' : tone === 'tough' ? 'down' : ''}">${ordinal(rank.rank)} of ${rank.of}</span> where 1st allows the least: ${rankWord}${last5 != null && ((dRows[opp] || {}).g || 0) > 5 ? `. ${fixed(last5)} a game over their last 5` : ''}${prior ? `. Last season ${fixed(prior.value)} a game, ${ordinal(prior.rank)} of ${prior.of}` : ''}.</p>` : `<p>The defense table does not track ${esc(label)} by position.</p>`}
        ${dValues.some(v => v != null) ? chart(dRecent, dValues, null, abbr) + `<p class="row-meta">Every ${esc(pos)} on the opposing side combined, game by game this season.</p>` : ''}
        ${vs && vs.summary ? `<p>${esc(data.name)} against ${esc(abbr(opp))}: ${fixed(vs.summary.avg)} ${esc(label)} a game over ${vs.summary.n} stored meeting${vs.summary.n === 1 ? '' : 's'}.</p>` : ''}` : ''}
      <p class="row-meta" style="margin-top:12px"><a href="#player/${league}/${esc(row.athleteId)}">Player page →</a>${row.gameId ? ` · <a href="#game/${esc(row.gameId)}">Game page →</a>` : ''}</p>`;
  }

  /* One player line from the board: the price and our read, then the last ten games, the role and the matchup. */
  async function openProp(id) {
    const data = await get('app/lines.json');
    const row = (data.lines || []).find(l => l.id === id);
    if (!row) return;
    const g = C.gradeOf(row.grade, row.gradeNote, row);
    const ours = pickKeys.get(rowKey(row)) || pickKeys.get(row.id);
    const books = row.books || [];
    const pct = v => v == null ? DASH : Math.round(100 * v) + '%';
    const dialog = $('#detail');
    dialog.innerHTML = `<div class="detail-inner"><div class="detail-head"><div><div class="row-top">${row.state === 'open' ? `<span class="pill pill-${['lean', 'strong'].includes(g.tier) ? 'ours' : 'reference'}">${esc(g.word)}</span>` : `<span class="pill pill-${esc(row.state)}">${esc({ stale: 'Recheck price', closed: 'Closed', unpriced: 'No price', reference: 'Unverified price' }[row.state] || row.state)}</span>`}${ours ? `<span class="pill pill-ours">${ours.modelLean ? 'Our model lean' : 'Our pick'}</span>` : ''}</div>
      <h3 style="margin:7px 0 0;font-size:17px">${esc(row.title)}</h3><p class="row-meta" style="margin:4px 0 0">${esc(when(row.kickoff))}${row.position ? ' · ' + esc(row.position) : ''}</p></div><button class="close" type="button" data-close aria-label="Close">×</button></div>
      <div class="detail-body"><div class="kv"><div><span>Price</span><strong>${esc(row.book || 'No book')} ${odds(row.odds)}</strong></div><div><span>Our number</span><strong>${row.grade && row.grade.projection != null ? esc(row.grade.projection) : DASH}</strong></div><div><span>Chance</span><strong>${pct(row.grade && row.grade.chance)}</strong></div><div><span>Needs</span><strong>${pct(row.grade && row.grade.needs)}</strong></div></div>
      ${g.detail ? `<p style="margin-top:10px">${esc(g.detail)}.</p>` : ''}
      ${books.length > 1 ? `<p class="row-meta">${books.map(q => `${esc(q.book)} ${esc(q.line)} ${odds(q.odds)}`).join(' · ')}</p>` : ''}
      <div data-context><p class="row-meta">Loading the last ten games and the matchup…</p></div></div></div>`;
    dialog.showModal();
    const html = await propContext(row);
    const box = dialog.querySelector('[data-context]');
    if (box) box.innerHTML = html;
  }

  /* ---------- shell ---------- */

  const VIEWS = { today: viewToday, games: viewGames, game: viewGame, stats: viewStats, player: viewPlayer, team: viewTeam,
    model: viewModel, record: viewRecord, board: viewBoard, ticket: viewTicket, research: viewResearch, scores: viewScores,
    arbs: viewArbs, lab: viewLab, schedule: viewSchedule, more: viewMore, trends: viewTrends };
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-set^="boardMode:"]');
    if (button) { const mode = button.dataset.set.split(':')[1]; state.boardMode = mode; location.hash = mode === 'props' ? '#board/props' : '#board'; }
  });

  function chrome(route) {
    const active = TAB_FOR[route.view] || route.view;
    $('#tabs').innerHTML = TABS.map(([id, label]) => `<a href="#${id}" ${active === id ? 'aria-current="page"' : ''}>${icon(ICONS[id])}<span>${label}</span></a>`).join('');
    $('#leagues').innerHTML = [['NFL', 'NFL'], ['CFB', 'College'], ['ALL', 'All']].map(([value, label]) =>
      `<button type="button" data-league="${value}" aria-pressed="${state.league === value}">${label}</button>`).join('');
    const bar = $('#ticket-bar');
    const show = state.ticket.length > 0 && route.view !== 'ticket';
    bar.hidden = !show;
    if (show) bar.innerHTML = `<span>Ticket · ${state.ticket.length} line${state.ticket.length === 1 ? '' : 's'}</span><span>Open →</span>`;
  }

  let token = 0;
  async function render() {
    const route = C.parseRoute(location.hash);
    const mine = ++token;
    chrome(route);
    const view = $('#view');
    const slow = setTimeout(() => { if (mine === token) view.innerHTML = '<div class="loading">Loading…</div>'; }, 120);
    try {
      const html = await (VIEWS[route.view] || viewToday)(route);
      if (mine !== token) return;
      view.innerHTML = html;
      if (route.pick) openPick(route.pick);
    } catch (error) {
      if (mine !== token) return;
      view.innerHTML = `<div class="empty" style="margin-top:32px"><h3>Could not load this page</h3><p>${esc(error.message)}</p><button class="btn" type="button" data-retry>Try again</button></div>`;
    } finally {
      clearTimeout(slow);
    }
  }

  const saveTicket = () => saved.set('ticket', state.ticket);

  async function toggleLine(id) {
    const existing = state.ticket.findIndex(t => t.id === id);
    if (existing >= 0) state.ticket.splice(existing, 1);
    else {
      const data = await get('app/lines.json');
      const row = data.lines.find(l => l.id === id);
      if (row) state.ticket.push({ id: row.id, title: row.title, player: row.player, market: row.market, line: row.line, direction: row.direction,
        odds: row.odds, book: row.book, gameId: row.gameId, kickoff: row.kickoff, expiresAt: row.expiresAt, observedAt: row.observedAt, state: row.state });
    }
    saveTicket();
    render();
  }

  document.addEventListener('click', event => {
    const target = event.target;
    const league = target.closest('[data-league]');
    if (league) { state.league = league.dataset.league; saved.set('league', state.league); render(); return; }
    const setter = target.closest('[data-set]');
    if (setter) {
      const [key, value] = setter.dataset.set.split(':');
      if (key === 'stakeMode') { state.stake.mode = value; saved.set('stake', state.stake); } else state[key] = value;
      render();
      return;
    }
    const add = target.closest('[data-add]');
    if (add) { toggleLine(add.dataset.add); return; }
    const accept = target.closest('[data-accept]');
    if (accept) {
      get('app/lines.json').then(data => {
        const row = data.lines.find(l => l.id === accept.dataset.accept);
        const item = state.ticket.find(t => t.id === accept.dataset.accept);
        if (row && item) Object.assign(item, { odds: row.odds, line: row.line, observedAt: row.observedAt, state: row.state, expiresAt: row.expiresAt });
        saveTicket();
        render();
      });
      return;
    }
    if (target.closest('[data-copy-ticket]')) {
      const text = C.ticketText(state.ticket);
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject(new Error('no clipboard')))
        .then(() => { target.textContent = 'Copied'; }).catch(() => { window.prompt('Copy the ticket text:', text); });
      return;
    }
    if (target.closest('[data-clear-ticket]')) { state.ticket = []; saveTicket(); render(); return; }
    if (target.closest('[data-retry]')) { cache.clear(); render(); return; }
    if (target.closest('[data-close]')) {
      $('#detail').close();
      /* Closing a shared pick's card leaves the reader on Today, not on a link that would reopen it. */
      if (/^#\/?pick\//.test(location.hash)) history.replaceState(null, '', '#today');
      return;
    }
    const prop = target.closest('[data-prop]');
    if (prop) { openProp(prop.dataset.prop); return; }
    const pick = target.closest('[data-pick]');
    if (pick) openPick(pick.dataset.pick);
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const prop = event.target && event.target.closest ? event.target.closest('[data-prop]') : null;
    if (prop && event.target === prop) { event.preventDefault(); openProp(prop.dataset.prop); }
  });

  document.addEventListener('change', event => {
    const select = event.target.closest('[data-select]');
    if (select) { state[select.dataset.select] = select.value; render(); }
  });

  document.addEventListener('input', event => {
    const field = event.target;
    if (field.dataset.arb) {
      state.arb[field.dataset.arb] = field.value;
      saved.set('arb', state.arb);
      const box = $('#arb-summary');
      if (box) box.innerHTML = arbSummary(C.arbSplit(state.arb.first, state.arb.second, state.arb.bankroll));
    } else if (field.dataset.input === 'playerQuery') {
      state.playerQuery = field.value;
      get(`app/players/${dataLeague()}.json`).then(index => { const box = $('#player-results'); if (box) box.innerHTML = playerResults(index, dataLeague()); });
    } else if (field.dataset.input) {
      const key = field.dataset.input;
      state[key] = field.value;
      const caret = field.selectionStart;
      render().then(() => { const box = document.querySelector(`[data-input="${key}"]`); if (box) { box.focus(); box.setSelectionRange(caret, caret); } });
    } else if (field.dataset.stake) {
      state.stake[field.dataset.stake] = Number(field.value);
      saved.set('stake', state.stake);
      get('app/lines.json').then(data => {
        const current = new Map(data.lines.map(l => [l.id, l]));
        const rows = state.ticket.map(t => current.get(t.id) || { ...t, state: 'closed' });
        const box = $('#ticket-summary');
        if (box) box.innerHTML = ticketSummary(C.summarizeTicket(rows, state.stake.amount, state.stake.mode, state.stake.unit), n => '$' + Number(n).toFixed(2));
      });
    }
  });

  window.addEventListener('hashchange', () => { render().then(() => window.scrollTo(0, 0)); });
  setInterval(() => {
    const route = C.parseRoute(location.hash);
    if (!document.hidden && ['today', 'games', 'game', 'scores'].includes(route.view) && !document.activeElement.matches('input, select, textarea')) render();
  }, 60000);
  render();
})();
