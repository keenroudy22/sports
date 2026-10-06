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

  /* A descriptive injury angle, never a bet or touchdown probability.  The
     role history says what that slot has received; the current projection
     keeps a newly promoted player from inheriting the label on name alone. */
  const injurySleeperSignal = (evidence, projectedOpportunities) => {
    const role = evidence && evidence.roleUsage;
    const projected = Number(projectedOpportunities);
    if (!role || evidence.group === 'QB' || role.games < 2 || !Number.isFinite(projected)) return null;
    if (Object.values(role.volume || {}).some(value => value == null)) return null;
    if (role.coverage && Object.keys(role.volume || {}).some(k => role.coverage[k] < role.games)) return null;
    const roleOpportunities = Object.values(role.volume || {}).reduce((sum, value) => sum + Number(value || 0), 0);
    const qualifiedRole = role.snapPct >= .15 && roleOpportunities >= 3;
    if (!qualifiedRole) return null;
    if (projected >= 4) return { tier: 'volume', label: 'Sleeper watch', roleOpportunities, projected };
    if (projected >= 1.5 && role.redZone > 0) {
      return { tier: 'dart', label: 'Deep sleeper', roleOpportunities, projected };
    }
    return null;
  };

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
    if (v == null) return LONGEST.has(key) || key === 'snaps' || key === 'snapPct' || /^(rz|i10|i5)/.test(key) ? null : 0;
    return v;
  };
  /* Research views never infer a zero from an absent feed value. Legacy grading keeps cell(). */
  const observedCell = (row, keys, key) => {
    const i = column(keys, key), value = i < 0 ? null : row[i];
    return Number.isFinite(value) ? value : null;
  };
  /* A player's anytime-score history is the sum of recorded rushing and
     receiving touchdowns. It stays a history view: it is never treated as a
     priced sportsbook line unless a real quote is captured separately. */
  const DERIVED_STATS = { anyTD: ['rushTD', 'recTD'] };
  const observedStat = (row, keys, key) => {
    const components = DERIVED_STATS[key];
    if (!components) return observedCell(row, keys, key);
    const values = components.map(component => observedCell(row, keys, component));
    return values.some(Number.isFinite)
      ? values.reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0)
      : null;
  };
  /* Season is the feed's season, not the calendar year of a January game. */
  const playerHistory = (rows, currentSeason, season = 'current', window = 'all', before = null) => {
    const selected = season === 'all' ? null : Number(season === 'current' ? currentSeason : season);
    const limit = {last5:5,last10:10,last20:20}[window];
    const list = (rows || []).filter(row => row[4] === 2 &&
      (season === 'all' || Number.isInteger(selected) && selected > 1900 && Number(row[2]) === selected) &&
      (!before || String(row[1]) < String(before).slice(0,10)))
      .slice().sort((a,b) => String(a[1]).localeCompare(String(b[1])));
    return limit ? list.slice(-limit) : list;
  };
  const statValue = (value, key, digits = 1) => !Number.isFinite(value) ? DASH
    : key === 'snapPct' ? `${Math.round(value * 100)}%` : fixed(value, digits);

  const summarize = values => {
    const list = values.filter(v => v != null && !Number.isNaN(v));
    if (!list.length) return null;
    const sorted = [...list].sort((a, b) => a - b);
    const mid = sorted.length >> 1;
    const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    return { n: list.length, avg: list.reduce((a, b) => a + b, 0) / list.length, median, min: sorted[0], max: sorted[sorted.length - 1] };
  };

  /* Last-N windows counting back from the newest game; short logs report their true n. */
  const windows = (rows, keys, key, sizes = [5, 10, 20], filter = null, read = cell) => {
    const list = (filter ? rows.filter(filter) : rows).slice().sort((a, b) => String(b[1]).localeCompare(String(a[1])));
    const values = list.map(r => read(r, keys, key));
    const out = {};
    for (const size of sizes) out['last' + size] = summarize(values.slice(0, size));
    out.season = null;
    if (list.length) {
      const season = list[0][2];
      out.season = summarize(list.filter(r => r[2] === season).map(r => read(r, keys, key)));
    }
    return out;
  };

  const splits = (rows, keys, key, opponent = null, read = cell) => {
    const pick = test => summarize(rows.filter(test).map(r => read(r, keys, key)));
    const out = { home: pick(r => r[7] === 1), away: pick(r => r[7] === 0), neutral: pick(r => r[7] === -1) };
    if (opponent != null) {
      const meetings = rows.filter(r => String(r[6]) === String(opponent));
      out.vs = { summary: summarize(meetings.map(r => read(r, keys, key))), games: meetings.map(r => ({ eventId: r[0], date: r[1], value: read(r, keys, key) })) };
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
    QB: ['passYds', 'passTD', 'cmp', 'att', 'int', 'rushYds', 'car', 'rushTD', 'scrambles', 'sacks', 'rushLong'],
    RB: ['rushYds', 'car', 'anyTD', 'rushTD', 'recYds', 'rec', 'targets', 'recTD', 'rushLong', 'recLong', 'rzCar', 'i10Car', 'i5Car'],
    FB: ['rushYds', 'car', 'anyTD', 'rushTD', 'recYds', 'rec', 'targets', 'recTD', 'rushLong', 'recLong', 'rzCar', 'i10Car', 'i5Car'],
    WR: ['recYds', 'rec', 'targets', 'anyTD', 'recTD', 'recLong', 'rushYds', 'car', 'rushTD', 'rzTgt', 'i10Tgt'],
    TE: ['recYds', 'rec', 'targets', 'anyTD', 'recTD', 'recLong', 'rzTgt', 'i10Tgt'],
    PK: ['kPts', 'fgm', 'fga', 'xpm'],
  };
  const LABEL = {
    passYds: 'Pass yds', cmp: 'Completions', att: 'Attempts', passTD: 'Pass TD', int: 'INT', sacks: 'Sacked',
    rushYds: 'Rush yds', car: 'Carries', rushTD: 'Rush TD', rushLong: 'Long rush', targets: 'Targets', rec: 'Receptions',
    recYds: 'Rec yds', recTD: 'Rec TD', anyTD: 'Any TD', recLong: 'Long rec', rzTgt: 'RZ targets', i10Tgt: 'Inside-10 tgts',
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
    if (Object.prototype.hasOwnProperty.call(LABEL, row.market)) return PROJECTION_MARKET[row.market] || row.market;
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
    const observed = row => row.coverage?.[pos]?.[stat] ?? row.g;
    const list = Object.entries(rows || {})
      .filter(([, r]) => r && observed(r) >= minGames && Number.isFinite(r[pos]?.[stat]))
      .map(([team, r]) => ({ team, value: r[pos][stat], games: observed(r) }))
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

  /* Equal-return stakes for two outcomes that exhaust the market. This is math only: availability, limits,
     settlement rules and voids still have to be checked in both sportsbook apps. */
  const arbSplit = (first, second, bankroll = 100) => {
    const a = Number(first), b = Number(second), total = Number(bankroll);
    if (!Number.isFinite(a) || !Number.isFinite(b) || a === 0 || b === 0 || !Number.isFinite(total) || total <= 0)
      return { valid: false, reason: 'Enter two non-zero American prices and a positive bankroll.' };
    const d1 = decimal(a), d2 = decimal(b), implied = 1 / d1 + 1 / d2;
    const firstStake = Math.round(total * (1 / d1) / implied * 100) / 100;
    const secondStake = Math.round((total - firstStake) * 100) / 100;
    const returned = Math.min(firstStake * d1, secondStake * d2);
    const profit = returned - total;
    return { valid: true, arb: profit > 0.004, firstStake, secondStake, return: Math.round(returned * 100) / 100,
      profit: Math.round(profit * 100) / 100, roi: Math.round(10000 * profit / total) / 100,
      implied: Math.round(implied * 10000) / 100 };
  };

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

  const ticketText = selected => ["Kook'n Sports: personal draft, not an official ticket",
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
  /* Performance changes the required threshold upstream; it does not erase a sufficiently strong read. */
  const tierOf = g => !g ? 'none' : g.view || g.tier || 'none';
  const gradeOf = (g, note = '', row = null) => {
    if (!g) return { tier: 'none', word: 'No model read', detail: note || '' };
    const pct = x => `${Math.round(100 * x)}%`;
    if (g.unproven) return { tier: 'pass', word: 'Grading first', detail: `our number ${g.projection} · ${pct(g.chance)} on the raw curve · college player numbers get graded against the line before we play them` };
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
    if (typeof g.edge === 'number') parts.push(`${g.edge >= 0 ? '+' : ''}${Number(g.edge).toFixed(1)} point edge`);
    if (g.performanceCaution) parts.push(`recent results raised the required edge to ${Number(g.performanceNeed || 5).toFixed(0)} points`);
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
  /* Confidence and value answer different questions. Confidence orders only fresh, calibrated reads by their
     estimated chance to win; value orders them by how far that chance clears the price. The UI shows both and
     never turns either into a lock score. */
  const confidenceChance = row => typeof ((row.grade || {}).chance) === 'number' ? row.grade.chance
    : typeof row.chance === 'number' ? row.chance : null;
  const confidenceEligible = row => {
    const grade = row.grade || row;
    const tier = row.grade ? tierOf(grade) : row.calibrated === true ? 'lean' : 'none';
    return (row.state == null || row.state === 'open') && confidenceChance(row) != null && grade.calibrated === true
      && !grade.unproven && !grade.thin && !grade.limited
      && ['lean', 'strong'].includes(tier);
  };
  const byConfidence = (a, b) => (Number(confidenceEligible(b)) - Number(confidenceEligible(a)))
    || ((confidenceChance(b) ?? -1) - (confidenceChance(a) ?? -1))
    || (((b.grade || b).edge ?? -1e9) - ((a.grade || a).edge ?? -1e9))
    || String(a.title || a.id).localeCompare(String(b.title || b.id));
  const rankConfidence = rows => {
    const ordered = rows.filter(confidenceEligible).slice().sort(byConfidence);
    const ranks = new Map(ordered.map((row, index) => [row.id, index + 1]));
    return rows.map(row => ranks.has(row.id) ? { ...row, confidenceRank: ranks.get(row.id), confidencePool: ordered.length } : row);
  };
  const category = p => p.kind === 'gamePicks' ? (p.marketType === 'total' ? 'Totals' : 'Spreads')
    : p.kind === 'props' ? 'Straights' : p.kind === 'riskyProps' ? 'Risky lines'
      : p.parlayType === 'longshot' ? 'Longshots' : p.parlayType === 'ladder' ? 'Ladder' : 'Parlays';
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
  const kindOf = p => p.parlayType === 'ladder' ? 'ladder' : p.kind === 'parlays' ? 'longshot' : p.modelLean ? 'model' : 'researched';
  const KIND_WORD = { researched: 'Researched', model: 'Model picks', longshot: 'Longshots', ladder: 'Ladder' };
  /* Picks imported from before the desk recorded prices (the Week 1 props) stay listed with their results but
     are kept out of every total, so a record, its units and its ROI always describe the same priced picks. */
  const isUnpricedImport = p => Boolean(p.historicalImport) && p.odds == null;
  const recordOf = (picks, minimum = 10) => {
    const imported = picks.filter(isUnpricedImport);
    const counted = picks.filter(p => !isUnpricedImport(p));
    const parlays = counted.filter(p => p.kind === 'parlays' && !isLadder(p));
    const straight = counted.filter(p => p.kind !== 'parlays');
    return { ...summarizePicks(straight, minimum),
      imported: imported.length ? summarizePicks(imported, minimum) : null,
      parlays: parlays.length ? summarizePicks(parlays, minimum) : null,
      researched: summarizePicks(straight.filter(p => !p.modelLean), minimum),
      model: summarizePicks(straight.filter(p => p.modelLean), minimum) };
  };
  /* The simple public scorecard: the current model's final pregame calls for the three game markets and player
     props, plus the separately labeled result of the fun tickets that were actually published. Adding records
     preserves pushes and never turns model accuracy into units or profit. */
  const addRecords = records => (records || []).reduce((sum, row) => {
    const r = Array.isArray(row) ? row : [0, 0, 0];
    return [sum[0] + Number(r[0] || 0), sum[1] + Number(r[1] || 0), sum[2] + Number(r[2] || 0)];
  }, [0, 0, 0]);
  const projectionScorecard = (board, picks, league = 'ALL') => {
    const candidates = ((board || {}).live || []).filter(row => row.model === 'v2.0'
      && (league === 'ALL' || row.league === league));
    const latest = candidates.reduce((out, row) => out.set(row.league,
      Math.max(out.get(row.league) ?? -Infinity, Number(row.season))), new Map());
    const live = candidates.filter(row => Number(row.season) === latest.get(row.league));
    const modelRecord = key => addRecords(live.map(row => (row.summary || {})[key]));
    const propMarkets = ((board || {}).props || {}).markets || [];
    const props = league === 'CFB' ? [0, 0, 0] : addRecords(propMarkets.map(row => row.record));
    const tickets = summarizePicks((picks || []).filter(p => (league === 'ALL' || p.league === league)
      && p.kind === 'parlays' && !isLadder(p)), 10);
    const updated = live.map(row => row.updatedThrough).filter(Boolean).sort();
    return {
      spread: modelRecord('side'), moneyline: modelRecord('winner'), total: modelRecord('ou'),
      props, parlays: [tickets.wins, tickets.losses, tickets.pushes],
      games: live.reduce((sum, row) => sum + Number((row.summary || {}).games || 0), 0),
      updatedThrough: updated.at(-1) || (board || {}).updatedThrough || null,
      /* The projection scoreboard's captured player-line comparison is NFL-only today. */
      propsNote: league === 'CFB' ? 'not graded here yet' : 'vs captured line',
    };
  };
  /* The one record, the same on the site and on X: every play we publish, graded win or lose. The record is the
     straight plays at one unit each, at the line and price we published (recorded prices only, never an assumed
     one). Fun parlays (smaller stakes) and the Week 1 legs posted before prices were recorded get their own lines.
     The Pick of the Day record counts the days its post went out. */
  const isParlay = p => p.kind === 'parlays' || Boolean((p.legs || []).length) || Boolean(p.parlayType);
  const recordBreakdown = picks => {
    const straight = picks.filter(p => !isParlay(p));
    const captured = straight.filter(p => !p.priceAssumed && !isUnpricedImport(p) && typeof p.odds === 'number');
    const assumed = straight.filter(p => p.priceAssumed || isUnpricedImport(p));
    // Promotional refunds are not evidence that a losing model pick made money.
    const beforeCredits = captured.map(p => p.earlyExit && p.result === 'loss'
      ? { ...p, earlyExit: false, units: -stakeOf(p) } : p);
    return { all: summarizePicks(straight), captured: summarizePicks(beforeCredits), assumed: summarizePicks(assumed),
      credits: captured.filter(p => p.earlyExit && p.result === 'loss').reduce((sum, p) => sum + stakeOf(p), 0) };
  };
  const cardSchedule = (picks, now = Date.now()) => {
    const today = dayOf(new Date(now).toISOString());
    const active = picks.filter(p => !p.result && !p.historicalImport);
    const day = p => dayOf(p.kickoff);
    return { today: active.filter(p => day(p) === today),
      upcoming: active.filter(p => day(p) && day(p) > today),
      awaiting: active.filter(p => !day(p) || day(p) < today) };
  };
  const modelCaution = game => {
    const margin = game?.v2?.margin, spread = game?.market?.spread;
    if (game?.league !== 'CFB' || typeof margin !== 'number' || typeof spread !== 'number'
      || Math.abs(margin + spread) < 7) return '';
    return 'Large model / market gap. College schedule strength, blowouts and changing roles can distort this estimate—not an automatic edge.';
  };
  /* The Kook'n 80/20 Climb (scripts/ladder.py): bank 20% of every winning return and ride 80% on the next rung.
     The current climb reaches $1,000 on bank plus ride; a miss starts a new $50 climb but cannot take the saved bank.
     It stays outside the straight record, and a rung pulled before its post still counts and waits for its result. */
  const isLadder = p => p.parlayType === 'ladder';
  const LADDER = { start: 50, goal: 1000, bankPercent: 20, ridePercent: 80 };
  const ladderSplit = returned => {
    const gross = Math.round(Number(returned) || 0), bank = Math.round(gross * LADDER.bankPercent / 100);
    return { bank, ride: gross - bank };
  };
  const theLadder = picks => {
    const pulled = p => /before its post went out/.test(p.entryNote || '');
    const rungs = picks.filter(isLadder).filter(p => p.result || pulled(p) || (!p.entryNote && (p.status || 'active') === 'active'))
      .sort((a, b) => String(a.publishedAt || '').localeCompare(String(b.publishedAt || '')) || String(a.id).localeCompare(String(b.id)));
    let run = 1, step = 1, stake = LADDER.start, banked = 0, saved = 0, open = null, best = LADDER.start;
    let wagered = 0, returned = 0, wins = 0, losses = 0, pushes = 0, voids = 0;
    const history = [], climbs = [];
    for (const r of rungs) {
      const info = r.ladder || {};
      if (!r.result) { open = r; continue; }
      const rungStake = Number(info.stake) || stake;
      wagered += rungStake;
      if (r.result === 'win') {
        const gross = Number(info.payout) || stake, split = ladderSplit(gross);
        returned += gross; wins += 1;
        const before = Number.isFinite(Number(info.banked)) ? Number(info.banked) : banked;
        const after = Number.isFinite(Number(info.bankedAfter)) ? Number(info.bankedAfter) : before + split.bank;
        const nextStake = Number.isFinite(Number(info.nextStake)) ? Number(info.nextStake) : split.ride;
        saved += Math.max(0, after - before); banked = after; stake = nextStake; step += 1;
        best = Math.max(best, banked + stake);
        if (banked + stake >= LADDER.goal) {
          climbs.push({ run, steps: step - 1, final: banked + stake, banked });
          run += 1; step = 1; stake = LADDER.start; banked = 0;
        }
      } else if (r.result === 'loss') { losses += 1; run += 1; step = 1; stake = LADDER.start; banked = 0; }
      else if (r.result === 'push') { returned += rungStake; pushes += 1; }
      else if (r.result === 'void') { returned += rungStake; voids += 1; }
      history.push({ ...r, ladderTotal: { wagered, returned, net: returned - wagered } });
    }
    const accounting = { wagered, returned, net: returned - wagered,
      atRisk: open ? Number((open.ladder || {}).stake) || stake : 0, wins, losses, pushes, voids };
    return { run, step, stake, banked, saved, open, history, climbs, best, accounting, ...LADDER };
  };
  const dayOf = iso => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    const e = new Date(d.toLocaleString('en-US', { timeZone: 'America/New_York' }));
    return `${e.getFullYear()}-${String(e.getMonth() + 1).padStart(2, '0')}-${String(e.getDate()).padStart(2, '0')}`;
  };
  const recordPhaseOf = pick => {
    const value = String(pick?.seasonType ?? '').toLowerCase();
    return value === '3' || /post|playoff/.test(value) ? 'playoffs' : 'regular';
  };
  /* A season rollover changes the default slice; it never removes an older published result. "Current" is
     evaluated per league because NFL 2026 and NHL 2027 can be active at the same time. */
  const recordArchive = (picks, selectedSeason = 'current', selectedPhase = 'current') => {
    const rows = Array.isArray(picks) ? picks.slice() : [];
    const seasonOf = pick => Number.isInteger(Number(pick?.season)) && Number(pick.season) >= 1900 && Number(pick.season) <= 2200
      ? Number(pick.season) : null;
    const currentByLeague = {};
    for (const pick of rows) {
      const season = seasonOf(pick), league = String(pick?.league || 'OTHER');
      if (season != null && (currentByLeague[league] == null || season > currentByLeague[league])) currentByLeague[league] = season;
    }
    const validSeason = /^(?:19|20|21)\d{2}$/.test(String(selectedSeason));
    const season = validSeason ? Number(selectedSeason) : ['current', 'all'].includes(selectedSeason) ? selectedSeason : 'current';
    const phase = ['current', 'regular', 'playoffs', 'all'].includes(selectedPhase) ? selectedPhase : 'current';
    const base = rows.filter(pick => {
      const value = seasonOf(pick), current = currentByLeague[String(pick?.league || 'OTHER')];
      if (season === 'all') return true;
      if (season === 'current') return current == null ? value == null : value === current;
      return value === season;
    });
    const phaseByLeague = {};
    for (const league of new Set(rows.map(pick => String(pick?.league || 'OTHER')))) {
      const referenceSeason = season === 'current' ? currentByLeague[league] : season === 'all' ? currentByLeague[league] : season;
      const reference = rows.filter(pick => String(pick?.league || 'OTHER') === league &&
        (referenceSeason == null ? seasonOf(pick) == null : seasonOf(pick) === referenceSeason));
      phaseByLeague[league] = reference.some(pick => recordPhaseOf(pick) === 'playoffs') ? 'playoffs' : 'regular';
    }
    const filtered = phase === 'all' ? base : base.filter(pick => recordPhaseOf(pick) ===
      (phase === 'current' ? phaseByLeague[String(pick?.league || 'OTHER')] || 'regular' : phase));
    return { rows: filtered, seasons: [...new Set(rows.map(seasonOf).filter(value => value != null))].sort((a, b) => b - a),
      currentByLeague, phaseByLeague, selectedSeason: season, selectedPhase: phase,
      unassigned: rows.filter(pick => seasonOf(pick) == null).length };
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
      parlays: summarizePicks(counted.filter(p => isParlay(p) && !isLadder(p)), 10),
      ladder: theLadder(picks),
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

  /* Straight cards lead to their research; multi-game tickets and incomplete imports keep their receipt. */
  const pickResearchRoute = p => {
    if (isParlay(p)) return null;
    if (p.athleteId) {
      return ['NFL', 'CFB'].includes(p.league)
        ? `#player/${p.league}/${encodeURIComponent(p.athleteId)}` : null;
    }
    if (p.kind === 'props') return null;
    return p.gameId ? `#game/${encodeURIComponent(p.gameId)}` : null;
  };

  const LEGACY = { '': 'today', sports: 'today', home: 'today', overview: 'today', charts: 'stats', tools: 'more', props: 'board',
    parlays: 'ticket', lines: 'board', results: 'record', research: 'research', players: 'stats' };
  /* Old links keep working: #game/<id>, #player/<league>/<id>, #record, #players and the rest. */
  const routePath = hash => {
    const parts = String(hash || '').split('?')[0].replace(/^#\/?/, '').split('/').map(value => {
      try { return decodeURIComponent(value); } catch (_) { return ''; }
    });
    let [view, ...rest] = parts;
    view = view || '';
    if (view === 'sport') return { view: 'scores', league: (rest[0] || 'NBA').toUpperCase() };
    if (view === 'player') return { view: 'player', league: (rest[0] || 'NFL').toUpperCase(), id: rest[1] };
    if (view === 'team') return { view: 'team', league: (rest[0] || 'NFL').toUpperCase(), id: rest[1] };
    if (view === 'game') return { view: 'game', id: rest.join('/') };
    if (view === 'trends') return { view: 'trends', id: rest.join('/') };
    /* A shareable pick: the Today page with that pick's card open, so a post can link to the receipt. */
    if (view === 'pick' && rest.length) return { view: 'today', pick: rest.join('/') };
    if (view === 'stats') return { view: 'stats', tab: rest[0] || 'charts' };
    if (view === 'board') return { view: 'board', tab: ['props', 'favorites'].includes(rest[0]) ? rest[0] : 'games' };
    if (view === 'defense') return { view: 'stats', tab: 'defense' };
    /* Scores keeps its deep links as the live view inside Games. */
    if (view === 'scores') return { view: 'scores', league: (rest[0] || 'ALL').toUpperCase() };
    if (view === 'record' && rest[0] === 'trials') return {view:'record',tab:'trials'};
    const known = ['today', 'games', 'stats', 'model', 'record', 'board', 'ticket', 'research', 'arbs', 'lab', 'schedule', 'more', 'saved', 'digest', 'start', 'feedback'];
    if (known.includes(view)) return { view };
    return { view: LEGACY[view] || 'today' };
  };
  const parseRoute = hash => {
    const route = routePath(hash), research = researchContext(hash);
    return research ? {...route,research} : route;
  };

  const trendWindow = (rows, window = 'season') => {
    const size = window === 'last5' ? 5 : window === 'last10' ? 10 : null;
    return rows.map(row => {
      const all = Array.isArray(row.history) ? row.history : [];
      const history = size ? all.slice(-size) : all.slice();
      if (!history.length) return { ...row, history, hits: 0, games: 0, pushes: 0, rate: 0, window };
      const hit = value => row.direction === 'at-least' ? value >= row.line
        : row.direction === 'over' ? value > row.line : value < row.line;
      const hits = history.filter(item => hit(Number(item.value))).length;
      const pushes = row.direction === 'at-least' ? 0 : history.filter(item => Number(item.value) === Number(row.line)).length;
      return { ...row, history, hits, games: history.length, pushes,
        rate: Math.round(1000 * hits / history.length) / 10, window };
    });
  };
  const bestTrendPrices = rows => [...rows.reduce((best, row) => {
    const key = [row.league, row.gameId, row.athleteId, row.stat, row.kind, row.direction, row.line].join('|');
    const old = best.get(key);
    if (!old || (Number.isFinite(Number(row.odds)) && Number(row.odds) > Number(old.odds))) best.set(key, row);
    return best;
  }, new Map()).values()];
  const filterTrends = (rows, filters = {}, now = Date.now()) => rows.filter(r =>
    r.games >= Number(filters.min || 3) && r.hits * 100 >= Number(filters.rate || 80) * r.games &&
    (!filters.league || filters.league === 'ALL' || r.league === filters.league) &&
    (!filters.stat || filters.stat === 'all' || r.stat === filters.stat) &&
    (!filters.kind || filters.kind === 'all' || r.kind === filters.kind) &&
    (filters.day !== 'today' || dayOf(r.kickoff) === dayOf(new Date(now).toISOString())) &&
    (!filters.game || r.gameId === filters.game) && Date.parse(r.kickoff) > now &&
    (r.kind === 'milestone' || (Date.parse(r.observedAt) <= now && now - Date.parse(r.observedAt) <= 4 * 3600000)) &&
    researchMatches(filters.query,r.player,r.team?.name,r.team?.abbr,r.matchup,r.title,LABEL[r.stat],r.stat))
    .sort((a, b) => b.hits / b.games - a.hits / a.games || b.games - a.games || a.player.localeCompare(b.player));

  const deskNotes = (data, league = 'ALL', now = Date.now(), games = []) => {
    if (data?.schemaVersion !== 1 || !Array.isArray(data.rows)) return [];
    const current = new Map(games.map(g => [g.id, g]));
    return data.rows.filter(r => {
      if (!r || typeof r !== 'object') return false;
      const g = current.get(r.gameId);
      return (league === 'ALL' || r.league === league) && Date.parse(r.expiresAt) > now &&
        Date.parse(r.kickoff) > now && Date.parse(r.observedAt) <= now &&
        (!['NFL', 'CFB'].includes(r.league) || (g && g.state === 'pre' && !g.completed)) &&
        typeof r.title === 'string' && typeof r.text === 'string' &&
        /^#(?:game\/(?:NFL|CFB)-\d+|scores\/(?:NBA|WNBA|CBB|MLB|NHL|EPL|MLS))$/.test(r.href);
    }).slice(0, 3);
  };

  /* Browser-local research settings. Unknown saved values fall back to visible, usable controls. */
  const RESEARCH_DEFAULTS = Object.freeze({
    researchQuery:'',
    trendRate:'80', trendStat:'all', trendKind:'main', trendWindow:'season', trendQuery:'', trendDay:'all',
    gamesScope:'upcoming', gamesQuery:'', boardDay:'today', boardScope:'open', boardSort:'best', boardQuery:'', propMarket:'all',
    chartStat:'recYds', chartPos:'all', chartWindow:'season', chartDay:'next', chartQuery:'', chartVenue:'all', chartOpponent:'all',
    recordScope:'straight', recordSeason:'current', recordPhase:'current',
  });
  const RESEARCH_CHOICES = {
    trendRate:['70','80','90','100'], trendStat:['all','rec','recYds','rushYds','passYds','car','att','cmp'],
    trendKind:['main','alternate','milestone'], trendWindow:['season','last10','last5'], trendDay:['all','today'],
    gamesScope:['upcoming','final'], boardDay:['today','week'], boardScope:['open','settled'], boardSort:['best','confidence','time'],
    propMarket:['all','receiving yards','receptions','rushing yards','carries','passing yards'],
    chartStat:Object.keys(LABEL), chartPos:['all','QB','RB','WR','TE','PK'], chartWindow:['season','last10','last5'],
    chartVenue:['all','home','away'], recordScope:['straight','parlays','ladder','all'], recordPhase:['current','regular','playoffs','all'],
  };
  const researchPreferences = values => Object.fromEntries(Object.entries(RESEARCH_DEFAULTS).map(([key,fallback]) => {
    let value=key==='researchQuery' ? values?.researchQuery ?? values?.chartQuery ?? values?.boardQuery ?? values?.trendQuery : values?.[key];
    if(['chartStat','trendStat'].includes(key) && typeof value==='string' && Object.hasOwn(PROJECTION_MARKET,value)) value=PROJECTION_MARKET[value];
    const valid=typeof value==='string' && value.length<=160 && !/[\u0000-\u001f\u007f]/.test(value) && (RESEARCH_CHOICES[key] ? RESEARCH_CHOICES[key].includes(value)
      : key==='chartOpponent' ? /^(?:all|\d{1,12})$/.test(value)
      : key==='chartDay' ? ['all','next'].includes(value) || /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value+'T12:00Z')) && new Date(value+'T12:00Z').toISOString().slice(0,10)===value
      : key==='recordSeason' ? ['current','all'].includes(value) || /^(?:19|20|21)\d{2}$/.test(value)
      : /Query$/.test(key));
    return [key,valid?value:fallback];
  }));
  const researchReset = scope => Object.fromEntries(Object.entries(RESEARCH_DEFAULTS).filter(([key]) =>
    ['charts','trends','lines'].includes(scope) && (key==='researchQuery' || (scope==='charts'?key.startsWith('chart'):scope==='trends'?key.startsWith('trend'):key.startsWith('board')||key==='propMarket'))));

  /* Public research links contain controls only, never captured prices or browser-private tools. */
  const RESEARCH_PARAMS = {
    stats:{stat:'chartStat',sample:'chartWindow',date:'chartDay',position:'chartPos',venue:'chartVenue',opponent:'chartOpponent'},
    board:{market:'propMarket',date:'boardDay',scope:'boardScope',sort:'boardSort'},
    trends:{stat:'trendStat',sample:'trendWindow',date:'trendDay',rate:'trendRate',kind:'trendKind'},
    player:{stat:'stat',season:'playerSeason',sample:'playerWindow'},
  };
  const RESEARCH_SPORTS = ['ALL','NFL','CFB','NBA','WNBA','CBB','MLB','NHL','EPL','MLS'];
  const researchValues = (route, values = {}) => {
    const fields=RESEARCH_PARAMS[route.view];
    if(!fields) return null;
    const clean=researchPreferences(values);
    const result={league:route.view==='player' ? (['NFL','CFB'].includes(route.league)?route.league:'NFL')
      : RESEARCH_SPORTS.includes(values.league)?values.league:'ALL',researchQuery:clean.researchQuery};
    for(const key of Object.values(fields)) {
      if(key==='stat') result[key]=Object.hasOwn(LABEL,values.stat)?(PROJECTION_MARKET[values.stat] || values.stat):'';
      else if(key==='playerSeason') result[key]=['current','all'].includes(values[key]) || /^(?:19|20)\d{2}$/.test(String(values[key])) ? String(values[key]) : 'current';
      else if(key==='playerWindow') result[key]=['all','last5','last10','last20'].includes(values[key])?values[key]:'all';
      else result[key]=clean[key];
    }
    return result;
  };
  const researchContext = hash => {
    const text=String(hash || ''), split=text.indexOf('?'), route=routePath(text), fields=RESEARCH_PARAMS[route.view];
    if(split<0 || !fields || text.length>4096) return null;
    const params=new URLSearchParams(text.slice(split+1)), values={};
    for(const [param,key] of Object.entries({sport:'league',q:'researchQuery',...fields}))
      if(params.getAll(param).length===1) values[key]=params.get(param);
    return researchValues(route,values);
  };
  const researchHash = (hash, values = {}) => {
    const path=String(hash || '#stats').split('?')[0], route=routePath(path), clean=researchValues(route,values);
    if(!clean) return path;
    const params=new URLSearchParams();
    for(const [param,key] of Object.entries({sport:'league',q:'researchQuery',...RESEARCH_PARAMS[route.view]})) params.set(param,clean[key]);
    return `${path}?${params}`;
  };

  /* Alias only stat names already present in the stored schema; no invented combined/TD markets. */
  const searchText = value => String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase()
    .replace(/[’']/g,'').replace(/[^a-z0-9.+-]+/g,' ').trim().replace(/\s+/g,' ');
  const SEARCH_MARKETS = [...MARKET_PHRASES,['passing completions','cmp'],['pass completions','cmp'],
    ['passing touchdowns','passTD'],['rushing touchdowns','rushTD'],['receiving touchdowns','recTD'],
    ...Object.entries(LABEL).map(([key,label])=>[label,PROJECTION_MARKET[key] || key]),
    ...Object.keys(LABEL).filter(key=>/[A-Z]/.test(key)).map(key=>[key,key])]
    .map(([phrase,key])=>[searchText(phrase),key]).sort((a,b)=>b[0].length-a[0].length);
  const searchTerms = value => {
    let text=` ${searchText(value)} `;
    for(const [phrase,key] of SEARCH_MARKETS) {
      // Boundary spaces keep 'carries' and the number 40 from matching parts of other facts.
      text=text.split(` ${phrase} `).join(` @${key.toLowerCase()} `);
    }
    return text.trim().split(/\s+/).filter(Boolean);
  };
  const researchMatches = (query, ...fields) => {
    const wanted=searchTerms(query), terms=fields.flatMap(searchTerms);
    const aliases=SEARCH_MARKETS.filter(([,key])=>terms.includes('@'+key.toLowerCase())).flatMap(([phrase])=>phrase.split(' '));
    const haystack=new Set([...terms,...fields.flatMap(value=>searchText(value).split(' ')),...aliases]);
    return wanted.every(word=>[...haystack].some(token=>token===word || (word.length>3 && !/^[@+\-\d]/.test(word) && token.startsWith(word))));
  };
  const researchStat = (query, supported = Object.keys(LABEL)) => {
    const text=searchText(query);
    if(/\+|\b(?:and|combined|anytime|any time)\b/.test(text)) return null;
    const keys=[...new Set(searchTerms(query).filter(word=>word.startsWith('@')).map(word=>
      supported.find(key=>key.toLowerCase()===word.slice(1))).filter(Boolean))];
    return keys.length===1?keys[0]:null;
  };
  const chartHistory = (rows, key, filters = {}) => {
    const count=filters.chartWindow==='last5'?5:filters.chartWindow==='last10'?10:Infinity;
    return (rows || []).filter(row=>Number.isFinite(row.stats?.[key]) &&
      (!filters.chartVenue || filters.chartVenue==='all' || row.home===(filters.chartVenue==='home'?1:0)) &&
      (!filters.chartOpponent || filters.chartOpponent==='all' || String(row.opp)===filters.chartOpponent))
      .slice().sort((a,b)=>String(a.date).localeCompare(String(b.date))).slice(-count);
  };

  /* One numerical coordinate system for every historical bar and its threshold. */
  const chartGeometry = (values, line = null) => {
    const finite = values.filter(Number.isFinite), threshold = Number.isFinite(line) ? line : null;
    let low = Math.min(0, ...finite, threshold ?? 0), high = Math.max(0, ...finite, threshold ?? 0);
    if (low === high) high = low + 1;
    const pad = (high - low) * .12;
    if (low < 0) low -= pad;
    if (high > 0) high += pad;
    const y = value => 100 * (high - value) / (high - low), zero = y(0);
    return {low, high, zero, line: threshold == null ? null : y(threshold), bars: values.map(value => {
      if (!Number.isFinite(value)) return null;
      const point = y(value);
      return {value, point, top: Math.min(point, zero), height: Math.abs(point - zero)};
    })};
  };
  const thresholdResult = (value, line, direction = 'over', inclusive = false) => {
    if (!Number.isFinite(value) || !Number.isFinite(line)) return 'unknown';
    if (inclusive) return (direction === 'under' ? value <= line : value >= line) ? 'hit' : 'miss';
    if (value === line) return 'push';
    return (direction === 'under' ? value < line : value > line) ? 'hit' : 'miss';
  };
  const quoteStatus = (row, kickoff = null, now = Date.now()) => {
    if (!row) return {kind:'missing', label:'No captured line', current:false};
    const at = Date.parse(row.observedAt || row.quotedAt), age = now - at;
    const started = Date.parse(kickoff || row.kickoff) <= now;
    if (started || row.state === 'closed') return {kind:'started', label:'Saved pregame line', current:false};
    if (!Number.isFinite(row.odds) || row.odds === 0 || ['reference','unpriced'].includes(row.state))
      return {kind:'reference', label:'Reference line · price unverified', current:false};
    if (!Number.isFinite(age) || age < 0 || age > 4 * 3600000 || Date.parse(row.expiresAt) <= now || row.state !== 'open')
      return {kind:'stale', label:'Earlier quote · recheck price', current:false};
    return {kind:'current', label:'Current captured line', current:true};
  };
  const shardOf = (id, shards) => Number(id) % shards;

  const deliveryText = (pick, now = Date.now()) => {
    if (pick.result || pick.historicalImport) return '';
    const d = pick.delivery || {}, parts = [];
    if (d.discordAt) parts.push('Discord sent');
    if (d.xAt) parts.push(`X sent ${whenShort(d.xAt)}`);
    else if (d.cancelled) parts.push('X post cancelled');
    else if (d.failed) parts.push('X delivery needs attention');
    else if (d.xDue) parts.push(Date.parse(d.xDue) > now ? `X scheduled ${whenShort(d.xDue)}` : 'X delivery awaiting confirmation');
    return parts.join(' · ') || 'On the website · social delivery not yet confirmed';
  };

  return { RESEARCH_DEFAULTS, researchPreferences, researchReset, researchContext, researchHash, researchMatches, researchStat, chartHistory, chartGeometry, thresholdResult, quoteStatus, esc, DASH, odds, signed, fixed, pct, when, whenShort, dayLabel, ago, spreadText, modelSpread, leanText, leanTone, injurySleeperSignal, deliveryText, trendWindow, bestTrendPrices, filterTrends, deskNotes,
    column, cell, observedCell, observedStat, playerHistory, statValue, summarize, windows, splits, hits, POSITION_STATS, LABEL, PROJECTION_MARKET, POS_GROUP, marketKey, roleOf,
    rankDefenses, rankOf, rankTone, decimal, american, arbSplit, eligible, summarizeTicket, ticketText,
    unitsFor, stakeOf, recordOf, recordBreakdown, cardSchedule, modelCaution, projectionScorecard, theRecord, recordPhaseOf, recordArchive, isParlay, isLadder, ladderSplit, theLadder, dayOf, isUnpricedImport, summaryOf: summarizePicks, kindOf, KIND_WORD, weekOf, pickState, isOpen, isLongshot, gradeOf, tierOf, byGrade, byConfidence, rankConfidence, category, parseRoute, pickResearchRoute, shardOf, BASE };
});
