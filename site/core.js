/* KeenRoudy Sports core: formatting, stat windows, ranks, ticket and record math,
   routes. Pure functions with no DOM access, shared by the browser app and the
   Node tests. Every number shown comes from the pipeline's payloads; this file
   only summarizes them. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.KRCore = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---------- text ---------- */

  const esc = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const DASH = '–';  // en dash for empty cells and ranges
  const odds = value => value == null || value === '' ? DASH : (Number(value) > 0 ? '+' + Number(value) : String(value));
  const signed = (value, places = 1) => {
    if (value == null || Number.isNaN(Number(value))) return DASH;
    const n = Number(value);
    const text = Number.isInteger(n) && places === 0 ? String(n) : n.toFixed(places);
    return n > 0 ? '+' + text : text;
  };
  const fixed = (value, places = 1) => value == null || Number.isNaN(Number(value)) ? DASH : Number(value).toFixed(places);
  const pct = (value, places = 0) => value == null ? DASH : (100 * value).toFixed(places) + '%';

  const ET = 'America/New_York';
  /* new Date(null) is 1970, not missing. */
  const date = iso => { if (iso == null || iso === '') return null; const d = new Date(iso); return Number.isNaN(d.getTime()) ? null : d; };
  const when = iso => {
    const d = date(iso);
    return d ? d.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: ET }) + ' ET' : '';
  };
  const whenShort = iso => {
    const d = date(iso);
    return d ? d.toLocaleString('en-US', { weekday: 'short', month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: ET }).replace(',', '') : '';
  };
  const dayLabel = iso => {
    const d = date(iso);
    return d ? d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', timeZone: ET }) : '';
  };
  const ago = (iso, now = Date.now()) => {
    const d = date(iso);
    if (!d) return 'time not recorded';
    const mins = Math.round((now - d.getTime()) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + ' min ago';
    const hours = Math.round(mins / 60);
    if (hours < 24) return hours + (hours === 1 ? ' hour ago' : ' hours ago');
    const days = Math.round(hours / 24);
    return days + (days === 1 ? ' day ago' : ' days ago');
  };

  /* A home spread as the book writes it: -3.5 means the home team gives 3.5. */
  const spreadText = (abbr, spread) => spread == null ? DASH : `${abbr} ${spread > 0 ? '+' : ''}${spread === 0 ? 'PK' : spread}`;

  /* The model's margin written as a spread for the side it favors. */
  const modelSpread = (home, away, margin) => {
    if (margin == null) return DASH;
    if (Math.abs(margin) < 0.05) return 'Even';
    return margin > 0 ? `${home} -${Math.abs(margin).toFixed(1)}` : `${away} -${Math.abs(margin).toFixed(1)}`;
  };

  /* Where the model sits against the market, in plain words. */
  const leanText = (game, threshold = 0) => {
    const lean = game && game.lean;
    if (!lean) return null;
    const out = {};
    if (lean.spread != null && Math.abs(lean.spread) >= threshold && lean.side) {
      out.side = { team: lean.side === 'home' ? game.home.abbr : game.away.abbr, points: Math.abs(lean.spread), chance: lean.spreadChance ?? null };
    }
    if (lean.total != null && Math.abs(lean.total) >= threshold && lean.total !== 0) {
      out.total = { direction: lean.total > 0 ? 'Over' : 'Under', points: Math.abs(lean.total), chance: lean.totalChance ?? null };
    }
    return out;
  };
  /* A chip's color is its calibrated chance against a standard -110 price: the same bar as the board. */
  const leanTone = (chance, thin) => chance == null ? '' : chance >= 0.574 && !thin ? 'lean-strong' : chance >= 0.544 ? 'lean-mild' : '';

  /* ---------- stat windows ---------- */

  /* Log rows are arrays: [eventId, date, season, week, seasonType, team, opp, home, ...stats]. */
  const BASE = 8;
  const column = (keys, key) => { const i = keys.indexOf(key); return i < 0 ? -1 : BASE + i; };
  const LONGEST = new Set(['rushLong', 'recLong']);
  /* A listed player without a counting stat recorded none; longest plays and snaps have no zero. */
  const cell = (row, keys, key) => {
    const i = column(keys, key);
    if (i < 0) return null;
    const v = row[i];
    if (v == null) return LONGEST.has(key) || key === 'snaps' || key === 'snapPct' ? null : 0;
    return v;
  };

  const summarize = values => {
    const list = values.filter(v => v != null && !Number.isNaN(v));
    if (!list.length) return null;
    const sorted = [...list].sort((a, b) => a - b);
    const mid = sorted.length >> 1;
    const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    return { n: list.length, avg: list.reduce((a, b) => a + b, 0) / list.length, median, min: sorted[0], max: sorted[sorted.length - 1] };
  };

  /* Last-N windows counting back from the newest game; short logs report their true n. */
  const windows = (rows, keys, key, sizes = [5, 10, 20], filter = null) => {
    const list = (filter ? rows.filter(filter) : rows).slice().sort((a, b) => String(b[1]).localeCompare(String(a[1])));
    const values = list.map(r => cell(r, keys, key));
    const out = {};
    for (const size of sizes) out['last' + size] = summarize(values.slice(0, size));
    out.season = null;
    if (list.length) {
      const season = list[0][2];
      out.season = summarize(list.filter(r => r[2] === season).map(r => cell(r, keys, key)));
    }
    return out;
  };

  const splits = (rows, keys, key, opponent = null) => {
    const pick = test => summarize(rows.filter(test).map(r => cell(r, keys, key)));
    const out = { home: pick(r => r[7] === 1), away: pick(r => r[7] === 0), neutral: pick(r => r[7] === -1) };
    if (opponent != null) {
      const meetings = rows.filter(r => String(r[6]) === String(opponent));
      out.vs = { summary: summarize(meetings.map(r => cell(r, keys, key))), games: meetings.map(r => ({ eventId: r[0], date: r[1], value: cell(r, keys, key) })) };
    }
    return out;
  };

  /* Over/under counts against a line, for describing history (not a probability). */
  const hits = (values, line) => {
    const list = values.filter(v => v != null);
    return { over: list.filter(v => v > line).length, under: list.filter(v => v < line).length, push: list.filter(v => v === line).length, n: list.length };
  };

  /* Which stats matter for a position, in display order. */
  const POSITION_STATS = {
    QB: ['passYds', 'cmp', 'att', 'passTD', 'int', 'rushYds', 'car'],
    RB: ['rushYds', 'car', 'recYds', 'rec', 'targets', 'rzCar'],
    FB: ['rushYds', 'car', 'recYds', 'rec', 'targets'],
    WR: ['recYds', 'rec', 'targets', 'rzTgt', 'recLong'],
    TE: ['recYds', 'rec', 'targets', 'rzTgt', 'recLong'],
    PK: ['kPts', 'fgm', 'fga', 'xpm'],
  };
  const LABEL = {
    passYds: 'Pass yds', cmp: 'Completions', att: 'Attempts', passTD: 'Pass TD', int: 'INT', sacks: 'Sacked',
    rushYds: 'Rush yds', car: 'Carries', rushTD: 'Rush TD', rushLong: 'Long rush', targets: 'Targets', rec: 'Receptions',
    recYds: 'Rec yds', recTD: 'Rec TD', recLong: 'Long rec', rzTgt: 'RZ targets', i10Tgt: 'Inside-10 tgts',
    rzCar: 'RZ carries', i10Car: 'Inside-10 car', i5Car: 'Inside-5 car', scrambles: 'Scrambles', fumLost: 'Fum lost',
    fgm: 'FG made', fga: 'FG att', xpm: 'XP made', kPts: 'Kick pts', snaps: 'Snaps', snapPct: 'Snap %',
    receptions: 'Receptions', carries: 'Carries',
  };
  /* Projection stats and the prop market key each lines up with. */
  const PROJECTION_MARKET = { receptions: 'rec', recYds: 'recYds', carries: 'car', rushYds: 'rushYds', att: 'att', cmp: 'cmp', passYds: 'passYds' };
  /* The defense table groups positions four ways; a fullback's carries count against the run defense. */
  const POS_GROUP = { QB: 'QB', RB: 'RB', FB: 'RB', WR: 'WR', TE: 'TE' };
  /* The stat behind a market's words, most specific phrase first so "rushing attempts" never reads as pass attempts. */
  const MARKET_PHRASES = [['receiving yards', 'recYds'], ['rushing yards', 'rushYds'], ['passing yards', 'passYds'], ['pass yards', 'passYds'],
    ['rushing attempts', 'car'], ['rush attempts', 'car'], ['carries', 'car'], ['receptions', 'rec'], ['completions', 'cmp'],
    ['pass attempts', 'att'], ['passing attempts', 'att']];
  const marketKey = row => {
    if (!row) return null;
    if (row.stat) return row.stat;
    const text = String(row.market || row.title || '').toLowerCase();
    const hit = MARKET_PHRASES.find(([phrase]) => text.includes(phrase));
    return hit ? hit[1] : null;
  };
  /* Where a player sits among teammates at his position, by the projected volume behind a market:
     targets for a receiving line, carries for a rushing line, attempts for a passing line. */
  const VOLUME_FOR = { recYds: 'targets', rec: 'targets', rushYds: 'carries', car: 'carries', passYds: 'att', att: 'att', cmp: 'att' };
  const roleOf = (players, athleteId, pos, key) => {
    const stat = VOLUME_FOR[key];
    if (!stat || !pos) return null;
    const group = (players || []).filter(p => POS_GROUP[p.pos] === pos && p[stat] && p[stat][0] > 0)
      .sort((a, b) => b[stat][0] - a[stat][0]);
    const i = group.findIndex(p => String(p.id) === String(athleteId));
    if (i < 0) return null;
    return { rank: i + 1, of: group.length, stat, volume: group[i][stat][0] };
  };

  /* ---------- defense ranks ---------- */

  /* Rank defenses by what they allow; 1 allows the least. Ties share a rank. */
  const rankDefenses = (rows, pos, stat, minGames = 1) => {
    const list = Object.entries(rows || {})
      .filter(([, r]) => r && r.g >= minGames && r[pos] && r[pos][stat] != null)
      .map(([team, r]) => ({ team, value: r[pos][stat], games: r.g }))
      .sort((a, b) => a.value - b.value || String(a.team).localeCompare(String(b.team)));
    let rank = 0, previous = null;
    list.forEach((row, i) => { if (row.value !== previous) { rank = i + 1; previous = row.value; } row.rank = rank; });
    return list;
  };
  const rankOf = (rows, team, pos, stat) => {
    const list = rankDefenses(rows, pos, stat);
    const hit = list.find(r => String(r.team) === String(team));
    return hit ? { rank: hit.rank, of: list.length, value: hit.value } : null;
  };
  /* Tone for a rank from the offense's point of view: a generous defense is good news. */
  const rankTone = (rank, of) => !rank || !of ? 'neutral' : rank > of * 2 / 3 ? 'soft' : rank <= of / 3 ? 'tough' : 'neutral';

  /* ---------- tickets ---------- */

  const decimal = price => { const n = Number(price); return n > 0 ? 1 + n / 100 : 1 + 100 / Math.abs(n); };
  const american = value => value >= 2 ? Math.round((value - 1) * 100) : Math.round(-100 / (value - 1));
  const bookName = book => String(book || '').replace(/\s+/g, '').toLowerCase();

  const eligible = (row, now) => row.state === 'open' && row.odds != null
    && (!row.expiresAt || Date.parse(row.expiresAt) > now) && (!row.kickoff || Date.parse(row.kickoff) > now);

  /* An illustrative parlay from separate-game quotes at one book. The sportsbook
     sets the real ticket price; same-game legs need its correlated price. */
  const summarizeTicket = (selected, stake = 1, mode = 'units', unitValue = 1, now = Date.now()) => {
    const risk = Number(stake), value = Number(unitValue), units = mode === 'units';
    let reason = '';
    if (selected.length < 2) reason = 'Add at least two lines to build a ticket.';
    else if (selected.some(row => !eligible(row, now))) reason = 'Every leg needs a current, priced sportsbook quote before kickoff.';
    else if (new Set(selected.map(row => bookName(row.book))).size !== 1) reason = 'Mixed sportsbooks need one combined sportsbook quote.';
    else if (new Set(selected.map(row => row.gameId)).size !== selected.length) reason = 'Same-game legs need the sportsbook’s own parlay price.';
    else if (!(risk > 0) || (units && !(value > 0))) reason = 'Enter a positive stake and a dollar value per unit.';
    if (reason) return { available: false, reason };
    const price = selected.reduce((n, row) => n * decimal(row.odds), 1);
    const profit = risk * (price - 1);
    return { available: true, odds: american(price), decimal: price, stake: risk, profit, total: risk * price,
      dollars: units ? { stake: risk * value, profit: profit * value, total: risk * price * value } : null,
      reason: 'Illustrative: separate-game quotes multiplied. The sportsbook sets the actual ticket price.' };
  };

  const ticketText = selected => ['KeenRoudy Sports: personal draft, not an official ticket',
    ...selected.map((row, i) => `${i + 1}. ${row.title || row.player || 'Line'} | ${row.book || 'Book unavailable'} ${odds(row.odds)} | seen ${row.observedAt || 'time unavailable'}`),
    'Check every market, price and the sportsbook’s ticket total yourself.'].join('\n');

  /* ---------- the record ---------- */

  /* A pick is staked at one unit unless it recorded its own size. Parlays never carry a full unit. */
  const stakeOf = pick => { const r = Number(pick.riskUnits); return Number.isFinite(r) && r > 0 ? r : 1; };
  const unitsFor = pick => {
    if (!pick.odds || !['win', 'loss', 'push'].includes(pick.result)) return null;
    /* Units saved with the result when the play was graded stand as written; older plays are summed the same way. */
    if (typeof pick.units === 'number' && Number.isFinite(pick.units) && !pick.earlyExit) return pick.units;
    const stake = stakeOf(pick);
    if (pick.result === 'win') return stake * (pick.odds > 0 ? pick.odds / 100 : 100 / Math.abs(pick.odds));
    /* The book credited the stake back after a first-half injury, so the money came home: zero units,
       the same as a push, while the win-loss line keeps the loss the model earned. */
    if (pick.result === 'loss' && pick.earlyExit) return 0;
    return pick.result === 'loss' ? -stake : 0;
  };
  /* Units and ROI use recorded original prices only; a result without one stays in the win-loss
     record and out of returns. No price is ever assumed. ROI waits for ten priced picks. */
  /* Where a pick stands, in words. Color only backs the word up; red is kept for losses. */
  const RESULT_WORD = { win: 'Won', loss: 'Lost', push: 'Push', void: 'Void' };
  const pickState = (p, now = Date.now()) => {
    if (p.result) return { word: RESULT_WORD[p.result] || p.result, tone: p.result === 'win' ? 'win' : p.result === 'loss' ? 'loss' : 'closed' };
    if (p.historicalImport) return { word: 'Unsettled', tone: 'closed' };
    if (p.status === 'withdrawn') return { word: 'Withdrawn', tone: 'closed' };
    /* Pulled over news before its post went out: that stays the word through kickoff, until it is graded. */
    if (/before its post went out/.test(p.entryNote || '')) return { word: 'Pulled', tone: 'closed' };
    if (p.kickoff && Date.parse(p.kickoff) <= now) return { word: 'In play', tone: 'reference' };
    if (p.entryNote) return { word: 'Line moved', tone: 'closed' };
    if (p.status === 'expired' || (p.expiresAt && Date.parse(p.expiresAt) <= now)) return { word: 'Price expired', tone: 'closed' };
    return { word: 'Open', tone: 'open' };
  };
  /* Open to new entries: unsettled, not closed by a revision, quote unexpired, game not started. */
  const isOpen = (p, now = Date.now()) => pickState(p, now).tone === 'open';
  const isLongshot = p => p.kind === 'riskyProps' || p.parlayType === 'longshot';

  /* A board line's model grade: the word leads, the numbers say why. "Value" is what bettors call positive
     expected value (+EV): our chance beats what the price needs to break even. */
  const GRADE_WORD = { strong: 'Good value', lean: 'Some value', pass: 'No value' };
  /* The verdict the site shows: paused markets never read as value; a calibrated view outranks the raw tier. */
  const tierOf = g => !g ? 'none' : g.paused ? 'pass' : g.view || g.tier || 'none';
  const gradeOf = (g, note = '', row = null) => {
    if (!g) return { tier: 'none', word: 'No model read', detail: note || '' };
    const pct = x => `${Math.round(100 * x)}%`;
    if (g.paused) return { tier: 'pass', word: 'Paused', detail: `${pct(g.chance)} our chance · our record on these bets trails the market, so we sit them out` };
    const tier = tierOf(g);
    /* A player line carries no price, so there is no edge to state: show the projection against
       the number, which side that favours, and how little history it rests on. */
    if (g.needs == null && g.projection != null) {
      const side = (row || {}).direction ? ` ${(row || {}).direction}` : '';
      const parts = [`our number ${g.projection} against ${(row || {}).line ?? 'the line'}`, `${pct(g.chance)}${side}`];
      if (g.limited) parts.push('questionable on the report');
      if (g.games != null) parts.push(`${g.games} game${g.games === 1 ? '' : 's'} this season`);
      return { tier, word: tier === 'lean' ? 'Leans our way' : g.limited ? 'Questionable' : g.thin ? 'Too early to tell' : 'Close to the line',
        detail: parts.join(' · ') };
    }
    const parts = [`${pct(g.chance)} our chance${g.push >= 0.01 ? `, ${pct(g.push)} push` : ''}`,
      g.needs == null ? 'no price yet' : `${pct(g.needs)} to break even`];
    if (g.thin) parts.push('few games so far');
    if (g.limited) parts.push('questionable on the report');
    if (g.calibrated === false) parts.push('raw number');
    /* A thin sample with a real gap is not "no value": it is a read we will not trust on one or two games. */
    const word = tier === 'pass' && g.thin && g.edge != null && g.edge >= 2 ? 'Too early to tell' : GRADE_WORD[tier] || GRADE_WORD.pass;
    return { tier, word, detail: parts.join(' · ') };
  };
  const TIER_ORDER = { strong: 0, lean: 1, pass: 2, none: 3 };
  /* Best first: tier, then a solid sample before a thin one, then the size of the edge. */
  const byGrade = (a, b) => (TIER_ORDER[tierOf(a.grade)] - TIER_ORDER[tierOf(b.grade)])
    || (Boolean((a.grade || {}).thin) - Boolean((b.grade || {}).thin))
    || (((b.grade || {}).edge ?? -1e9) - ((a.grade || {}).edge ?? -1e9));
  const category = p => p.kind === 'gamePicks' ? (p.marketType === 'total' ? 'Totals' : 'Spreads')
    : p.kind === 'props' ? 'Straights' : p.kind === 'riskyProps' ? 'Risky lines'
      : p.parlayType === 'longshot' ? 'Longshots' : 'Parlays';
  const summarizePicks = (picks, minimum) => {
    const settled = picks.filter(p => ['win', 'loss', 'push', 'void'].includes(p.result));
    const priced = picks.filter(p => unitsFor(p) != null);
    const units = priced.reduce((sum, p) => sum + unitsFor(p), 0);
    const staked = priced.reduce((sum, p) => sum + stakeOf(p), 0);
    const wins = settled.filter(p => p.result === 'win').length, losses = settled.filter(p => p.result === 'loss').length;
    const graded = settled.filter(p => p.result === 'win' || p.result === 'loss')
      .sort((a, b) => String(a.settledAt || a.kickoff || '').localeCompare(String(b.settledAt || b.kickoff || '')));
    let streak = null;
    for (let i = graded.length - 1; i >= 0 && (!streak || graded[i].result === streak.result); i--) {
      streak = { result: graded[i].result, length: (streak ? streak.length : 0) + 1 };
    }
    return { wins, losses, pushes: settled.filter(p => p.result === 'push').length, voids: settled.filter(p => p.result === 'void').length, streak,
      pending: picks.filter(p => !p.result).length, hitRate: wins + losses ? 100 * wins / (wins + losses) : null,
      priced: priced.length, pricedWins: priced.filter(p => p.result === 'win').length, pricedLosses: priced.filter(p => p.result === 'loss').length,
      unpriced: settled.filter(p => p.result !== 'void').length - priced.length, staked,
      earlyExits: picks.filter(p => p.earlyExit).length,
      units: priced.length ? units : null, roi: priced.length >= minimum && staked > 0 ? 100 * units / staked : null, roiMinimum: minimum };
  };
  /* Parlays are staked at their own size, never a full unit, so they are summarized apart and never
     folded into the straight-pick units. ROI is profit against what was actually risked. */
  /* Three kinds of pick, tracked apart: researched picks, the model's own leans, and longshot parlays. */
  const kindOf = p => p.kind === 'parlays' ? 'longshot' : p.modelLean ? 'model' : 'researched';
  const KIND_WORD = { researched: 'Researched', model: 'Model picks', longshot: 'Longshots' };
  /* Picks imported from before the desk recorded prices (the Week 1 props) stay listed with their results but
     are kept out of every total, so a record, its units and its ROI always describe the same priced picks. */
  const isUnpricedImport = p => Boolean(p.historicalImport) && p.odds == null;
  const recordOf = (picks, minimum = 10) => {
    const imported = picks.filter(isUnpricedImport);
    const counted = picks.filter(p => !isUnpricedImport(p));
    const parlays = counted.filter(p => p.kind === 'parlays');
    const straight = counted.filter(p => p.kind !== 'parlays');
    return { ...summarizePicks(straight, minimum),
      imported: imported.length ? summarizePicks(imported, minimum) : null,
      parlays: parlays.length ? summarizePicks(parlays, minimum) : null,
      researched: summarizePicks(straight.filter(p => !p.modelLean), minimum),
      model: summarizePicks(straight.filter(p => p.modelLean), minimum) };
  };
  /* The one record, the same on the site and on X: every play we publish, graded win or lose. The record is the
     straight plays at one unit each, at the line and price we published (recorded prices only, never an assumed
     one). Fun parlays (smaller stakes) and the Week 1 legs posted before prices were recorded get their own lines.
     The Pick of the Day record counts the days its post went out. */
  const isParlay = p => p.kind === 'parlays' || Boolean((p.legs || []).length) || Boolean(p.parlayType);
  const dayOf = iso => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    const e = new Date(d.toLocaleString('en-US', { timeZone: 'America/New_York' }));
    return `${e.getFullYear()}-${String(e.getMonth() + 1).padStart(2, '0')}-${String(e.getDate()).padStart(2, '0')}`;
  };
  const theRecord = (picks, now = Date.now()) => {
    const when = p => p.kickoff || p.publishedAt;
    const imported = picks.filter(isUnpricedImport);
    const counted = picks.filter(p => !isUnpricedImport(p));
    const straight = counted.filter(p => !isParlay(p));
    const days = [...new Set(straight.filter(p => ['win', 'loss', 'push', 'void'].includes(p.result)).map(p => dayOf(when(p))).filter(Boolean))].sort();
    const last = days.length ? days[days.length - 1] : null;
    const week = weekOf(new Date(now).toISOString());
    return {
      season: summarizePicks(straight, 10),
      week: summarizePicks(straight.filter(p => weekOf(when(p)) === week), 10),
      lastDay: last ? { day: last, ...summarizePicks(straight.filter(p => dayOf(when(p)) === last), 10) } : null,
      potd: summarizePicks(straight.filter(p => p.featured && p.posted), 10),
      parlays: summarizePicks(counted.filter(isParlay), 10),
      imported: imported.length ? summarizePicks(imported, 10) : null,
      /* Graded plays whose price was never recorded and is assumed (the Week 1 lines, at -115): the site says so. */
      assumed: straight.filter(p => p.priceAssumed && ['win', 'loss', 'push'].includes(p.result)).length,
    };
  };
  /* Football weeks run Thursday to Monday, so a week starts on Tuesday, Eastern. */
  const weekOf = iso => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    const eastern = new Date(d.toLocaleString('en-US', { timeZone: 'America/New_York' }));
    const back = (eastern.getDay() + 5) % 7;   // days since Tuesday
    eastern.setDate(eastern.getDate() - back);
    return `${eastern.getFullYear()}-${String(eastern.getMonth() + 1).padStart(2, '0')}-${String(eastern.getDate()).padStart(2, '0')}`;
  };

  /* ---------- routes ---------- */

  const LEGACY = { '': 'today', sports: 'today', home: 'today', overview: 'today', scores: 'games', props: 'board',
    parlays: 'ticket', lines: 'board', results: 'record', research: 'research', players: 'stats' };
  /* Old links keep working: #game/<id>, #player/<league>/<id>, #record, #players and the rest. */
  const parseRoute = hash => {
    const parts = String(hash || '').replace(/^#\/?/, '').split('/').map(decodeURIComponent);
    let [view, ...rest] = parts;
    view = view || '';
    if (view === 'sport') return { view: 'scores', league: (rest[0] || 'NBA').toUpperCase() };
    if (view === 'player') return { view: 'player', league: (rest[0] || 'NFL').toUpperCase(), id: rest[1] };
    if (view === 'team') return { view: 'team', league: (rest[0] || 'NFL').toUpperCase(), id: rest[1] };
    if (view === 'game') return { view: 'game', id: rest.join('/') };
    /* A shareable pick: the Today page with that pick's card open, so a post can link to the receipt. */
    if (view === 'pick' && rest.length) return { view: 'today', pick: rest.join('/') };
    if (view === 'stats') return { view: 'stats', tab: rest[0] || 'players' };
    if (view === 'board') return { view: 'board', tab: rest[0] === 'props' ? 'props' : 'games' };
    if (view === 'defense') return { view: 'stats', tab: 'defense' };
    /* Bare #scores was the old football board; only #scores/<league> is the other-sports page. */
    if (view === 'scores' && rest[0]) return { view: 'scores', league: rest[0].toUpperCase() };
    const known = ['today', 'games', 'stats', 'model', 'record', 'board', 'ticket', 'research', 'more'];
    if (known.includes(view)) return { view };
    return { view: LEGACY[view] || 'today' };
  };

  const shardOf = (id, shards) => Number(id) % shards;

  return { esc, DASH, odds, signed, fixed, pct, when, whenShort, dayLabel, ago, spreadText, modelSpread, leanText, leanTone,
    column, cell, summarize, windows, splits, hits, POSITION_STATS, LABEL, PROJECTION_MARKET, POS_GROUP, marketKey, roleOf,
    rankDefenses, rankOf, rankTone, decimal, american, eligible, summarizeTicket, ticketText,
    unitsFor, stakeOf, recordOf, theRecord, isParlay, dayOf, isUnpricedImport, summaryOf: summarizePicks, kindOf, KIND_WORD, weekOf, pickState, isOpen, isLongshot, gradeOf, tierOf, byGrade, category, parseRoute, shardOf, BASE };
});
