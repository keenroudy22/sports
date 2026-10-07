/* Kook'n redesign prototype (Hybrid A + B, casino felt).
   Plain-English best bets on Today, one sortable Research board, honest Record.
   Every number comes from the pipeline's payloads; this file lays them out and does small, tested math.
   Works in the browser (window.Kookn) and in Node (require) so the model functions are unit tested. */
(function (root, factory) {
  const api = factory(root.KRCore, root.KRLive, root.KRPersonal);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else {
    root.Kookn = api;
    if (typeof document !== 'undefined') {
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => api.boot());
      else api.boot();
    }
  }
})(typeof self !== 'undefined' ? self : globalThis, function (C, L, P) {
  'use strict';

  /* =====================================================================
     MODEL: pure functions. No DOM. Unit tested in redesign/tests.
     ===================================================================== */

  const round1 = x => Math.round(x * 10) / 10;
  const isNum = x => typeof x === 'number' && Number.isFinite(x);

  /* What a price needs to break even (no vig removed: this is the bettor's real bar). */
  const breakEven = odds => {
    const n = Number(odds);
    if (!Number.isFinite(n) || n === 0 || Math.abs(n) < 100) return null;
    return n > 0 ? 100 / (n + 100) : -n / (-n + 100);
  };
  /* The American price that matches a chance exactly: our "fair price". */
  const fairAmerican = chance => {
    if (!isNum(chance) || chance <= 0 || chance >= 1) return null;
    return chance >= 0.5 ? -Math.round(100 * chance / (1 - chance)) : Math.round(100 * (1 - chance) / chance);
  };
  const edgePoints = (chance, needs) => isNum(chance) && isNum(needs) ? round1(100 * (chance - needs)) : null;
  const pctText = x => isNum(x) ? `${Math.round(100 * x)}%` : '–';
  const oddsText = x => x == null || x === '' || !Number.isFinite(Number(x)) ? '–' : Number(x) > 0 ? `+${Number(x)}` : String(Number(x));

  /* Price age in plain words. Fresh ≤ 60 min, aging ≤ 4 h (the site's existing current-quote limit), else stale. */
  const quoteAge = (observedAt, kickoff, now = Date.now(), extra = {}) => {
    const at = Date.parse(observedAt);
    if (kickoff && Date.parse(kickoff) <= now) return { kind: 'started', minutes: null, label: 'Game started · saved pregame price' };
    if (extra.odds == null || extra.state === 'unpriced' || extra.state === 'reference') return { kind: 'unpriced', minutes: null, label: 'No price captured' };
    if (extra.expiresAt && Date.parse(extra.expiresAt) <= now) return { kind: 'stale', minutes: null, label: 'Old price · check your book' };
    if (!Number.isFinite(at)) return { kind: 'stale', minutes: null, label: 'Price time unknown · check your book' };
    const minutes = Math.max(0, Math.round((now - at) / 60000));
    const ago = minutes < 1 ? 'just now' : minutes < 60 ? `${minutes} min ago` : `${Math.round(minutes / 60)} h ago`;
    if (minutes <= 60) return { kind: 'fresh', minutes, label: `Price checked ${ago}` };
    if (minutes <= 240) return { kind: 'aging', minutes, label: `Price checked ${ago}` };
    return { kind: 'stale', minutes, label: `Old price (${ago}) · check your book` };
  };

  /* Sportsbook names as bettors know them. ESPN BET became theScore Bet on Dec 1, 2025. */
  const BOOKS = { draftkings: 'DraftKings', fanduel: 'FanDuel', betmgm: 'BetMGM', betrivers: 'BetRivers', caesars: 'Caesars',
    fanatics: 'Fanatics', hardrockbet: 'Hard Rock Bet', hardrock: 'Hard Rock Bet', espnbet: 'theScore Bet', thescorebet: 'theScore Bet',
    bet365: 'bet365', ballybet: 'Bally Bet', pinnacle: 'Pinnacle', kalshi: 'Kalshi', prizepicks: 'PrizePicks', underdog: 'Underdog' };
  const bookLabel = name => {
    const raw = String(name || '').trim();
    if (!raw || /unavailable/i.test(raw)) return null;
    return BOOKS[raw.toLowerCase().replace(/[^a-z0-9]/g, '')] || raw;
  };

  /* The book a play was posted at, as it was posted. ESPN BET plays keep that name, with today's name alongside. */
  const postedBook = name => /^espn ?bet$/i.test(String(name || '').trim()) ? 'ESPN BET (now theScore Bet)' : bookLabel(name) || (name ? String(name) : null);

  const STAT_WORD = { recYds: 'receiving yards', rec: 'receptions', rushYds: 'rushing yards', car: 'carries', passYds: 'passing yards',
    att: 'pass attempts', cmp: 'completions', passTD: 'passing TDs', anyTD: 'anytime TD', rushTD: 'rushing TDs', recTD: 'receiving TDs' };
  const isParlayLike = row => Boolean(row && ((row.legs || []).length || row.parlayType || row.kind === 'parlays'));
  /* One honest label per market. Game totals are game totals, never "team props". */
  const marketLabel = row => {
    if (!row) return '';
    if (row.parlayType === 'ladder') return '80/20 Climb';
    if (isParlayLike(row)) return 'Fun ticket';
    const market = String(row.market || row.marketType || '').toLowerCase();
    if (row.athleteId || row.player || STAT_WORD[row.market] || /yards|receptions|carries|attempts|completions|touchdown/.test(market)) {
      const word = STAT_WORD[row.market] || STAT_WORD[row.stat] || market || 'player line';
      return `Player prop · ${word}`;
    }
    if (row.kind === 'props' || row.kind === 'riskyProps') {
      const k = C ? C.marketKey(row) : null;
      return `Player prop · ${STAT_WORD[k] || (/touchdown|\btd\b/i.test(row.title || row.displayTitle || '') ? 'anytime TD' : 'player line')}`;
    }
    if (/team total/.test(market)) return 'Team total';
    if (/total/.test(market) || row.marketType === 'total' || (!row.athleteId && ['over', 'under'].includes(String(row.direction || '').toLowerCase()))) return 'Game total';
    if (/spread/.test(market) || row.marketType === 'spread') return 'Spread';
    if (/moneyline|winner/.test(market) || row.marketType === 'moneyline') return 'Moneyline';
    return 'Game line';
  };
  const niceTitle = text => String(text || '').replace(/\b(OVER|UNDER)\b/g, m => m.toLowerCase()).replace(/\s+/g, ' ').trim();

  /* The "why" and "watch out" lines, from the play's own published words. Counterpoints never become a "why". */
  const sentences = text => String(text || '').split(/(?<=[.!?])\s+(?=[A-Z0-9"“])/).map(s => s.trim()).filter(Boolean);
  const WHY_PREFIX = /^(Role:|Defense:|Checked before publishing:|Weather:|Injury:|Matchup:|Volume:|Usage:)/;
  /* A hit count is history, not a reason: it is shown on its own neutral line, never as support. */
  const HISTORY_SENTENCE = /^(Last \d+ games?:|This season:|Season:)/i;
  const WHY_SKIP = /\braw\b|adjust|needed at|is needed|percentage points|projection is|reads \d|estimate|guarantee|confidence \d/i;
  /* Never a reason, whatever its prefix: uncalibrated chances and untested numbers. */
  const NEVER_WHY = /\d+(\.\d+)?% likely|tested against a line|uncalibrated|probably lower|true chance is|breaks even at|\b\d+ of (his|her|their|its)?\s*last \d+\b|\bin \d+ of (his|her|their|its) last \d+/i;
  /* Context, not support: shown with a neutral bullet, never a green check. */
  const CONTEXT = /^(Role|Defense|Matchup|Weather|Injury|Volume|Usage|Checked before publishing):/;
  const WATCH_SKIP = /not a guarantee|does not take the field|confidence \d+ of 10|games? this season\.?$|voided|in-game injury|handful of touches|estimated chance/i;
  const whyLines = pick => {
    const out = [];
    if (pick && pick.reason && !/against this side/i.test(pick.reason) && !HISTORY_SENTENCE.test(pick.reason) && !NEVER_WHY.test(pick.reason)) out.push(String(pick.reason).trim());
    for (const s of sentences(pick && pick.why)) {
      if (out.length >= 2) break;
      if (/against this side/i.test(s) || HISTORY_SENTENCE.test(s) || NEVER_WHY.test(s)) continue;
      /* A defense line that the play's own caution says points against this side is not support. */
      if (/^Defense:/.test(s) && /positional allowance points against|defense (points|leans) against/i.test(String(pick.risk || ''))) continue;
      if (WHY_PREFIX.test(s) || !WHY_SKIP.test(s)) out.push(s.replace(/^Prop lean:\s*/i, ''));
    }
    return out.filter(s => (!WHY_SKIP.test(s) || WHY_PREFIX.test(s)) && !NEVER_WHY.test(s)).slice(0, 2);
  };
  const historyLine = pick => sentences(pick && pick.why).find(x => HISTORY_SENTENCE.test(x))
    || (pick && pick.reason && /\b\d+ of (his|her|their|its)?\s*last \d+\b|\bin \d+ of (his|her|their|its) last \d+/i.test(pick.reason) ? String(pick.reason).trim() : null)
    || ((pick && pick.reasoning && pick.reasoning.history) || null);
  const watchLine = pick => {
    const list = [...sentences(pick && pick.risk), ...((pick && pick.reasoning && pick.reasoning.cautions) || [])];
    const hit = list.find(s => !WATCH_SKIP.test(s) && !/^Our (number|projection) is [\d.]+\.?$/i.test(s));
    return hit ? hit.replace(/^Statistical counterpoint:\s*/i, '') : null;
  };

  /* The chain from our raw number to the chance we show, in words (the card face never shows the raw projection). */
  const howWeGotIt = pick => {
    const pap = (pick && pick.probabilityAtPublication) || {};
    const parts = [];
    if (isNum(pick && pick.projection) && isNum(pick && pick.line)) parts.push(`Our model's middle estimate is ${round1(pick.projection)} against the ${pick.line} line.`);
    if (isNum(pap.rawChance) && isNum(pap.chance)) {
      parts.push(`On its own the model says ${pctText(pap.rawChance)}. We adjust that to ${pctText(pap.chance)}${isNum(pap.calibration) ? `, keeping ${Math.round(100 * pap.calibration)}% of the model's lean` : ''}${isNum(pap.calibrationN) ? `, a setting learned from ${pap.calibrationN} graded lines` : ''}.`);
      if (isNum(pap.calibration) && pap.calibration < 0.5) parts.push('Our raw model runs hot in this market, so we discount it heavily. That keeps the chance honest.');
    }
    const needs = isNum(pap.breakEven) ? pap.breakEven : breakEven(pick && pick.odds);
    if (isNum(pap.chance) && isNum(needs)) parts.push(`At ${oddsText(pick.odds)} the price needs ${pctText(needs)}. That leaves an edge of ${edgePoints(pap.chance, needs) > 0 ? '+' : ''}${edgePoints(pap.chance, needs)} points.`);
    return parts;
  };

  /* A best bet, fun ticket or Climb rung as a view model. */
  const pickVM = (pick, now = Date.now()) => {
    const pap = pick.probabilityAtPublication || {};
    const chance = isNum(pap.chance) ? pap.chance : null;
    const needs = isNum(pap.breakEven) ? pap.breakEven : breakEven(pick.odds);
    const edge = isNum(pap.edgePoints) ? round1(pap.edgePoints) : edgePoints(chance, needs);
    const state = C ? C.pickState(pick, now) : { word: '', tone: '' };
    const kind = pick.parlayType === 'ladder' ? 'climb' : isParlayLike(pick) ? 'fun' : 'best';
    const result = pick.result;
    /* What a reader can still do with this play. "Open": the price is live. "Expired": still on the card and graded at
       the posted price, but that price is older than our freshness limit. "Closed": the desk closed it to new entries
       (line moved past its limit), pulled or withdrew it, or the game started. Only an open play gets the pitch. */
    const word = state.word;
    const mode = result ? 'settled' : state.tone === 'open' ? 'open' : word === 'Price expired' ? 'expired' : 'closed';
    const standing = mode === 'expired';
    const book = postedBook(pick.book);
    const at = `${oddsText(pick.odds)}${pick.book ? ` (${book})` : ''}`;
    const status = result ? word : mode === 'expired' ? 'Posted price may be gone' : word === 'Line moved' ? 'Closed to new entries' : word === 'Pulled' ? 'Pulled before posting' : word;
    const statusNote = mode === 'expired' ? `Still on the card and graded at ${at}, the price we posted. That price is older than our freshness limit, so check your book before playing it.`
      : word === 'Line moved' ? (/graded/i.test(pick.entryNote || '') ? String(pick.entryNote).replace(/\.\.+/g, '.').trim()
        : `${pick.entryNote ? String(pick.entryNote).trim() + ' ' : 'Closed to new entries. '}It is still graded at ${pick.line != null && !isParlayLike(pick) ? `${pick.line} ` : ''}${at}, the price we posted.`)
        : word === 'Pulled' ? (/graded/i.test(pick.entryNote || '') ? String(pick.entryNote).replace(/\.\.+/g, '.').trim() : `${pick.entryNote ? String(pick.entryNote).replace(/\.\.+/g, '.').trim() : 'Pulled over news before its post went out.'} It still counts and is graded at ${at}.`)
          : word === 'Withdrawn' ? `Withdrawn before kickoff.${pick.entryNote ? ' ' + pick.entryNote : ''}`
            : word === 'In play' ? (Date.parse(pick.kickoff) < now - 4 * 3600000 ? `Game over or running late · awaiting the result. Graded at ${at}, the price we posted.` : `In play. Graded at ${at}, the price we posted.`) : '';
    /* One line for compact tickets. */
    const graded = `graded at ${pick.line != null && !isParlayLike(pick) && word === 'Line moved' ? `${pick.line} ` : ''}${at}`;
    const awaitingResult = word === 'In play' && Date.parse(pick.kickoff) < now - 4 * 3600000;
    const statusShort = awaitingResult ? `Awaiting result · ${graded}` : mode === 'expired' ? `Old price · ${graded}` : word === 'Line moved' ? `Closed to new entries · ${graded}` : word === 'Pulled' ? `Pulled before posting · ${graded}`
      : word === 'Withdrawn' ? 'Withdrawn before kickoff' : word === 'In play' ? `In play · ${graded}` : '';
    const stub = result === 'win' ? { cls: 'hit', big: '✓', small: 'Hit' }
      : result === 'loss' ? { cls: 'miss', big: '✗', small: 'Miss' }
        : result === 'push' || result === 'void' ? { cls: 'push', big: '–', small: result === 'void' ? 'Void' : 'Push' }
          : kind !== 'best' ? { cls: mode === 'open' ? 'fun' : 'closed', big: oddsText(pick.odds), small: mode === 'open' ? (kind === 'climb' ? 'Climb' : 'Fun') : mode === 'expired' ? 'Old price' : awaitingResult ? 'Awaiting result' : status }
            : mode === 'open' && chance != null ? { cls: 'open', big: pctText(chance), small: 'our chance' }
              : mode === 'open' ? { cls: 'open', big: oddsText(pick.odds), small: 'posted price' }
                : mode === 'expired' && chance != null ? { cls: 'closed', big: pctText(chance), small: 'at posted price' }
                  : mode === 'expired' ? { cls: 'closed', big: oddsText(pick.odds), small: 'posted price' }
                    : { cls: 'closed', big: '•', small: awaitingResult ? 'Awaiting result' : status || 'Closed' };
    return {
      id: pick.id, kind, league: pick.league, title: niceTitle(pick.displayTitle || pick.title), market: marketLabel(pick),
      odds: pick.odds, book: pick.book ? book : null, chance, needs, edge, fair: fairAmerican(chance),
      calibrated: pap.calibrated !== false && chance != null, why: whyLines(pick), watch: watchLine(pick), history: historyLine(pick),
      state, mode, status, statusNote, statusShort, standing, stub, kickoff: pick.kickoff, featured: Boolean(pick.featured), posted: Boolean(pick.posted),
      estimated: Boolean(pick.priceEstimated), assumed: Boolean(pick.priceAssumed), lotto: kind === 'fun' && Number(pick.odds) >= 1000,
      legs: (pick.legs || []).map(leg => niceTitle(typeof leg === 'string' ? leg : leg.title || leg.displayTitle || leg.selection || leg.player || '')).filter(Boolean),
      href: `#pick/${encodeURIComponent(pick.id)}`, result,
    };
  };

  /* A research line (lines.json row) as a view model. Best price only compares quotes at the same line. */
  const lineVM = (row, now = Date.now()) => {
    const g = row.grade || {};
    const needs = isNum(g.needs) ? g.needs : breakEven(row.odds);
    const chance = isNum(g.chance) ? g.chance : null;
    const sameLine = (row.books || []).filter(b => Number(b.line) === Number(row.line) && bookLabel(b.book) && isNum(Number(b.odds)) && !/hard ?rock/i.test(b.book));
    const others = (row.books || []).filter(b => Number(b.line) !== Number(row.line) && bookLabel(b.book));
    const best = sameLine.slice().sort((a, b) => Number(b.odds) - Number(a.odds))[0];
    const age = quoteAge(row.observedAt, row.kickoff, now, { odds: row.odds, state: row.state, expiresAt: row.expiresAt });
    return {
      id: row.id, title: niceTitle(row.title), league: row.league, gameId: row.gameId, athleteId: row.athleteId || null,
      player: row.player || null, stat: row.stat || (C ? C.marketKey(row) : null), market: marketLabel(row), direction: row.direction || row.side || null,
      line: row.line, odds: row.odds, book: bookLabel(row.book), kickoff: row.kickoff, state: row.state,
      bestOdds: best ? Number(best.odds) : null, bestBook: best ? bookLabel(best.book) : null, booksCount: sameLine.length,
      otherLines: others.map(b => ({ book: bookLabel(b.book), line: b.line, odds: b.odds })),
      chance, needs, edge: isNum(g.edge) ? round1(g.edge) : edgePoints(chance, needs), fair: fairAmerican(chance),
      position: row.position || null, tier: g.view || g.tier || 'none', thin: Boolean(g.thin), limited: Boolean(g.limited), calibrated: g.calibrated === true,
      caution: Boolean(g.performanceCaution), age, raw: g.raw, projection: g.projection, isProp: Boolean(row.athleteId || row.player),
      key: officialKey(row), opened: isNum(row.opened) ? row.opened : isNum(row.move) && isNum(row.line) ? round1(row.line - row.move) : null, src: row,
    };
  };
  /* The key a best bet and a board line share: market and side, so a player's receptions pick never badges his yards. */
  let gameLookup = null;
  const officialKey = row => {
    let dir = String(row.direction || row.side || '').toLowerCase();
    if (!dir && !row.athleteId && /spread/i.test(String(row.marketType || row.market || '')) && gameLookup) {
      const g = gameLookup(row.gameId), team = String(row.title || '').trim().split(/\s+/)[0];
      if (g && team) dir = team === (g.home || {}).abbr ? 'home' : team === (g.away || {}).abbr ? 'away' : '';
    }
    if (row.athleteId) return ['prop', row.gameId, row.athleteId, C ? C.marketKey(row) : row.market, dir].join('|');
    const m = String(row.marketType || row.market || '').toLowerCase();
    return [/spread/.test(m) ? 'spread' : /total/.test(m) ? 'total' : /money|winner/.test(m) ? 'ml' : m, row.gameId, dir].join('|');
  };
  const onBoard = (vm, now = Date.now()) => vm.state === 'open' && isNum(Number(vm.odds)) && Math.abs(Number(vm.odds)) >= 100 && vm.book && Date.parse(vm.kickoff) > now;
  const hasValue = vm => vm.calibrated && ['lean', 'strong'].includes(vm.tier) && !vm.thin && !vm.limited && isNum(vm.edge) && vm.edge > 0;
  /* One row per player, stat and side (or game market and side): keep the strongest edge, count the rest. */
  const collapse = rows => {
    const groups = new Map();
    for (const r of rows) {
      const key = [r.gameId, r.athleteId || r.player || '', r.isProp ? r.stat : r.market, String(r.direction || '').toLowerCase()].join('|');
      const prev = groups.get(key);
      if (!prev) groups.set(key, { ...r, alternates: 0 });
      else {
        const better = (r.edge ?? -99) > (prev.edge ?? -99) ? r : prev;
        groups.set(key, { ...better, alternates: prev.alternates + 1 });
      }
    }
    return [...groups.values()];
  };
  const SORTS = {
    edge: (a, b) => (b.edge ?? -99) - (a.edge ?? -99) || Date.parse(a.kickoff) - Date.parse(b.kickoff),
    chance: (a, b) => (b.chance ?? -1) - (a.chance ?? -1) || (b.edge ?? -99) - (a.edge ?? -99),
    kickoff: (a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff) || String(a.gameId).localeCompare(String(b.gameId)) || (b.edge ?? -99) - (a.edge ?? -99),
  };
  /* Heavy favorites: a "100%" trend at −900 still needs 90% to break even. Hidden unless asked for. */
  const heavyFavorite = odds => { const need = breakEven(odds); return need != null && need > 0.8; };
  const trendText = row => {
    const need = breakEven(row.odds);
    return `${row.hits} of ${row.games}${need != null ? ` · price needs ${pctText(need)}` : ' · no price captured'}`;
  };

  /* Games: rank by how unusual our gap with the market is (percentile against every stored game), not raw points. */
  const gapScore = game => {
    const gap = (game.marketRead || {}).ourGap || {};
    const values = [gap.margin, gap.total].map(x => x && isNum(x.percentile) ? x.percentile : null).filter(x => x != null);
    if (!values.length || game.fcs || (game.v2 || {}).sparse || !game.market) return -1;
    return Math.max(...values);
  };

  /* Record: cumulative units at captured prices (same rule as recordBreakdown().captured: credits excluded). */
  const cumulativeUnits = (picks, unitsFor) => {
    const rows = picks.filter(p => !isParlayLike(p) && !p.priceAssumed && typeof p.odds === 'number' && ['win', 'loss', 'push'].includes(p.result))
      .map(p => p.earlyExit && p.result === 'loss' ? { ...p, earlyExit: false, units: -1 * (Number(p.riskUnits) > 0 ? Number(p.riskUnits) : 1) } : p)
      .sort((a, b) => String(a.settledAt || a.kickoff).localeCompare(String(b.settledAt || b.kickoff)));
    let total = 0;
    return rows.map(p => { total += unitsFor(p) || 0; return { id: p.id, at: p.settledAt || p.kickoff, units: Math.round(total * 100) / 100 }; });
  };
  const clvSummary = rows => {
    const measured = (rows || []).filter(r => isNum(r.clv));
    return { measured: measured.length, beat: measured.filter(r => r.clv > 0).length, tied: measured.filter(r => r.clv === 0).length,
      lost: measured.filter(r => r.clv < 0).length, avg: measured.length ? round1(measured.reduce((s, r) => s + r.clv, 0) / measured.length * 10) / 10 : null };
  };

  /* Routes. New grammar first; every old link (core.js routePath/LEGACY) lands on its new screen. */
  const MORE_PAGES = ['start', 'saved', 'arbs', 'lab', 'schedule', 'feedback', 'status', 'responsible', 'glossary'];
  const parseHash = hash => {
    const raw = String(hash || '').replace(/^#\/?/, '');
    const cut = raw.indexOf('?');
    const path = cut < 0 ? raw : raw.slice(0, cut), query = cut < 0 ? '' : raw.slice(cut + 1);
    const parts = path.split('/').map(v => { try { return decodeURIComponent(v); } catch (_) { return ''; } });
    return { parts, params: new URLSearchParams(query) };
  };
  const resolve = hash => {
    const { parts, params } = parseHash(hash);
    const [v = '', a = '', b = ''] = parts;
    const rest = parts.slice(1).join('/');
    const q = params.get('q') || '';
    switch (v) {
      case '': case 'today': case 'sports': case 'home': case 'overview': case 'digest': return { view: 'today', league: params.get('sport') ? params.get('sport').toUpperCase() : null };
      case 'pick': return rest ? { view: 'pick', id: rest } : { view: 'today' };
      case 'research': {
        const mode = ['lines', 'trends', 'players', 'news'].includes(a) ? a : 'lines';
        return { view: 'research', mode, type: params.get('type') || null, sort: params.get('sort') || null, q, game: params.get('game') || null, sub: params.get('view') || null, rate: params.get('rate') || null,
          league: params.get('sport') ? params.get('sport').toUpperCase() : null };
      }
      /* Old board links carried their own filters (best, market, sport, sort); keep what still means something. */
      case 'board': return { view: 'research', mode: 'lines', type: a === 'props' ? 'props' : a === 'favorites' ? 'all' : 'games',
        sort: a === 'favorites' || params.get('best') ? 'edge' : (params.get('sort') === 'time' ? 'kickoff' : params.get('sort') === 'confidence' ? 'chance' : null),
        q: q || (params.get('market') && params.get('market') !== 'all' ? params.get('market') : ''), league: params.get('sport') ? params.get('sport').toUpperCase() : null, legacy: true };
      case 'lines': return { view: 'research', mode: 'lines', type: 'all', legacy: true };
      case 'props': return { view: 'research', mode: 'lines', type: 'props', legacy: true };
      /* Old shared research links keep their controls (C.researchContext validates every value). */
      case 'trends': return { view: 'research', mode: 'trends', game: rest || null, q, league: params.get('sport') ? params.get('sport').toUpperCase() : null, legacy: true,
        ctx: [...params.keys()].length && C && C.researchContext ? C.researchContext(`#trends?${params}`) : null };
      case 'stats': case 'charts': case 'players': return { view: 'research', mode: 'players', sub: a === 'defense' ? 'defense' : a === 'teams' ? 'teams' : q ? 'search' : null, q,
        league: params.get('sport') ? params.get('sport').toUpperCase() : null, legacy: true, ctx: [...params.keys()].length && C && C.researchContext ? C.researchContext(`#stats?${params}`) : null };
      case 'defense': return { view: 'research', mode: 'players', sub: 'defense', legacy: true };
      case 'games': return { view: 'games', tab: ['live', 'final'].includes(a) ? a : 'upcoming', league: params.get('sport') ? params.get('sport').toUpperCase() : null };
      case 'scores': return { view: 'games', tab: 'live', league: a ? a.toUpperCase() : 'ALL', legacy: true };
      case 'sport': return { view: 'games', tab: 'live', league: (a || 'NBA').toUpperCase(), legacy: true };
      case 'game': return rest ? { view: 'game', id: rest } : { view: 'games', tab: 'upcoming' };
      case 'player': return { view: 'player', league: (a || 'NFL').toUpperCase() === 'CFB' ? 'CFB' : 'NFL', id: b,
        stat: params.get('stat') || null, season: params.get('season') || null, sample: params.get('sample') || null };
      case 'team': return { view: 'team', league: (a || 'NFL').toUpperCase() === 'CFB' ? 'CFB' : 'NFL', id: b };
      case 'record': return { view: 'record', tab: ['fun', 'climb', 'model', 'trials'].includes(a) ? a : 'official' };
      case 'results': return { view: 'record', tab: 'official', legacy: true };
      case 'model': return { view: 'record', tab: 'model', legacy: true };
      case 'more': case 'tools': return { view: 'more' };
      case 'ticket': case 'parlays': return { view: 'ticket' };
      default: return MORE_PAGES.includes(v) ? { view: v } : { view: 'today' };
    }
  };
  /* The new address for a legacy link. Shareable deep links (#pick, #game, #player, #team) never change. */
  const canonical = route => {
    if (!route.legacy) return null;
    if (route.view === 'research') {
      const params = new URLSearchParams();
      if (route.type && route.type !== 'all') params.set('type', route.type);
      if (route.sort) params.set('sort', route.sort);
      if (route.q) params.set('q', route.q);
      if (route.game) params.set('game', route.game);
      if (route.sub) params.set('view', route.sub);
      if (route.league && route.league !== 'ALL') params.set('sport', route.league);
      const tail = params.toString();
      return `#research${route.mode === 'lines' ? '' : '/' + route.mode}${tail ? '?' + tail : ''}`;
    }
    if (route.view === 'games') return `#games/live${route.league && route.league !== 'ALL' ? '?sport=' + route.league : ''}`;
    if (route.view === 'record') return route.tab === 'official' ? '#record' : `#record/${route.tab}`;
    return null;
  };
  const TAB_OF = { today: 'today', pick: 'today', research: 'research', games: 'games', game: 'games', team: 'games', player: 'research',
    record: 'record', more: 'more', ticket: 'more' };
  MORE_PAGES.forEach(p => { TAB_OF[p] = 'more'; });
  TAB_OF.lab = 'record';

  const model = { breakEven, fairAmerican, edgePoints, pctText, oddsText, quoteAge, bookLabel, postedBook, marketLabel, niceTitle, sentences,
    whyLines, watchLine, historyLine, howWeGotIt, pickVM, lineVM, officialKey, onBoard, hasValue, collapse, SORTS, heavyFavorite, trendText, gapScore,
    cumulativeUnits, clvSummary, parseHash, resolve, canonical, TAB_OF, MORE_PAGES, isParlayLike };

  if (typeof document === 'undefined') return { model };

  /* =====================================================================
     BROWSER: data, state, views.
     ===================================================================== */

  const { esc, when, whenShort, dayLabel, ago } = C;
  const $ = s => document.querySelector(s);

  const saved = {
    get(key, fallback) { try { const v = localStorage.getItem('kr:' + key); return v == null ? fallback : JSON.parse(v); } catch (e) { return fallback; } },
    set(key, value) { try { localStorage.setItem('kr:' + key, JSON.stringify(value)); } catch (e) { /* private mode */ } },
  };
  const BOARD_DEFAULT = { type: 'all', sort: 'edge', fresh: true, value: true, limit: 40 };
  const boardSaved = saved.get('board', {});
  const state = {
    league: P.league(saved.get('league', 'ALL')),
    board: { ...BOARD_DEFAULT, ...(boardSaved && typeof boardSaved === 'object' ? boardSaved : {}), limit: 40 },
    q: '', trends: { rate: '80', window: 'season', kind: 'main', heavy: true, stat: 'all', day: 'all', limit: 40 },
    players: { q: '', pos: 'WR', stat: 'recYds', scope: 'season', order: 'soft', sub: 'matchup', game: 'next', chartStat: 'recYds', chartPos: 'all', chartWindow: 'season', linesOnly: true },
    games: { sort: 'kickoff', all: false, q: '', day: null, status: 'all' }, player: { key: null, stat: null, season: 'current', window: 'all' },
    record: { season: 'current', phase: 'current', q: '' },
    watchlist: (Array.isArray(saved.get('watchlist', [])) ? saved.get('watchlist', []) : []).filter(r => r && typeof r.key === 'string' && /^#(player|game)\//.test(r.href)).slice(0, 100),
    ticket: Array.isArray(saved.get('ticket', [])) ? saved.get('ticket', []).filter(r => r && typeof r.id === 'string').slice(0, 20) : [],
    stake: { amount: 1, mode: 'units', unit: 10, ...(saved.get('stake', null) && typeof saved.get('stake', null) === 'object' ? saved.get('stake', {}) : {}) },
    arb: { first: 150, second: -130, bankroll: 100, ...(saved.get('arb', null) && typeof saved.get('arb', null) === 'object' ? saved.get('arb', {}) : {}) },
  };
  const saveBoard = () => { const { limit, ...rest } = state.board; saved.set('board', rest); };
  /* Research controls persist under the old site's kr:research-preferences key, in its shape. */
  (() => {
    if (!C.researchPreferences) return;
    const raw = saved.get('research-preferences', {});
    const pr = C.researchPreferences(raw && typeof raw === 'object' ? raw : {});
    Object.assign(state.trends, { rate: pr.trendRate, stat: pr.trendStat || 'all', kind: pr.trendKind, window: pr.trendWindow, day: pr.trendDay });
    Object.assign(state.players, { chartStat: pr.chartStat, chartPos: pr.chartPos, chartWindow: pr.chartWindow });
  })();
  const savePrefs = () => {
    const raw = saved.get('research-preferences', {});
    saved.set('research-preferences', { ...(raw && typeof raw === 'object' ? raw : {}), trendRate: state.trends.rate, trendStat: state.trends.stat, trendKind: state.trends.kind,
      trendWindow: state.trends.window, trendDay: state.trends.day, chartStat: state.players.chartStat, chartPos: state.players.chartPos, chartWindow: state.players.chartWindow });
  };
  /* Team ids and free-text searches don't carry between sports, so a sport change clears them (as the old site did). */
  const setLeague = value => {
    const next = P.league(String(value || '').toUpperCase());
    if (next === state.league) return;
    state.league = next; saved.set('league', next);
    state.q = ''; state.players.q = ''; state.games.q = ''; state.record.q = ''; state.players.game = 'next';
  };
  /* Section-level page counts for the optional feedback note. Names only, never searches or players. */
  const countVisit = view => {
    const raw = saved.get('usage', {});
    const usage = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
    usage[view] = Math.min(10000, (Number(usage[view]) || 0) + 1);
    saved.set('usage', usage);
  };

  /* Production reads only the payloads built beside this application. */
  const bases = ['data/'];
  let base = null;
  const fetchJSON = async path => {
    const order = base ? [base, ...bases.filter(b => b !== base)] : bases;
    let error;
    for (const b of order) {
      try {
        const r = await fetch(b + path, { cache: 'no-cache' });
        if (!r.ok) throw new Error(`${path} returned ${r.status}`);
        const json = await r.json();
        base = b; return json;
      } catch (e) { error = e; }
    }
    throw error;
  };
  const cache = new Map();
  const get = path => {
    const hit = cache.get(path);
    if (hit && Date.now() - hit.at < 300000) return hit.promise;
    const promise = fetchJSON(path);
    promise.catch(() => cache.delete(path));
    cache.set(path, { at: Date.now(), promise });
    return promise;
  };
  /* A missing optional file is remembered for five minutes, so it is not re-requested on every render. */
  const missing = new Map();
  const maybe = path => {
    const at = missing.get(path);
    if (at && Date.now() - at < 300000) return Promise.resolve(null);
    return get(path).catch(() => { missing.set(path, Date.now()); return null; });
  };
  /* Every published play. After the planned payload split (C3), today.json keeps open plays plus 72 hours and
     record.json holds the history; until then record.json is absent and today.json has everything. */
  const allPicks = async () => {
    const today = await get('app/today.json');
    const record = today.historyFile ? await maybe(`app/${String(today.historyFile).replace(/[^a-z0-9._-]/gi, '')}`) : null;
    if (!record || !Array.isArray(record.picks)) return today.picks || [];
    const byId = new Map(record.picks.map(p => [p.id, p]));
    (today.picks || []).forEach(p => byId.set(p.id, p));
    return [...byId.values()];
  };

  const inLeague = row => state.league === 'ALL' || row.league === state.league;
  const FOOTBALL = ['NFL', 'CFB'];
  const LEAGUE_NAME = { ALL: 'All sports', NFL: 'NFL', CFB: 'College football', NBA: 'NBA', WNBA: 'WNBA', CBB: 'College hoops', MLB: 'MLB', NHL: 'NHL', EPL: 'Premier League', MLS: 'MLS' };
  const todayISO = () => new Date().toISOString();
  const etDay = (offset = 0) => C.dayOf(new Date(Date.now() + offset * 86400000).toISOString());

  /* ---------- fragments ---------- */
  const ICON = {
    today: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
    research: '<path d="M4 19V11"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19H2"/>',
    games: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M12 5v14M3 12h18"/>',
    record: '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"/>',
    more: '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    hat: '<path d="M7 18h10v-4H7z"/><path d="M7 14c-2.5 0-4-1.8-4-4a4 4 0 0 1 5-3.9A4.5 4.5 0 0 1 16 6a4 4 0 0 1 5 4c0 2.2-1.5 4-4 4"/>',
    check: '<path d="M5 12l5 5 9-10"/>',
  };
  const svg = (name, size = 22) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[name]}</svg>`;
  const TABS = [['today', 'Today'], ['research', 'Research'], ['games', 'Games'], ['record', 'Record'], ['more', 'More']];
  const head = (eyebrow, title, sub = '', back = '') => `${back}<div class="page-head">${eyebrow ? `<p class="eyebrow">${esc(eyebrow)}</p>` : ''}<h1>${esc(title)}</h1>${sub ? `<p class="sub">${sub}</p>` : ''}</div>`;
  const section = (title, body, link = '', note = '') => `<section class="section"><div class="section-head"><h2>${esc(title)}</h2>${link}</div>${note ? `<p class="section-note">${note}</p>` : ''}${body}</section>`;
  const empty = (title, text, icon = 'clock') => `<div class="empty">${svg(icon, 34)}<div><h3>${esc(title)}</h3><p>${text}</p></div></div>`;
  const SEG_LABEL = { type: 'Line type', trendRate: 'Hit rate', trendWindow: 'History window', trendKind: 'Line kind', trendDay: 'Games', cpos: 'Position', cwin: 'History window', psub: 'Players view', pos: 'Position', dscope: 'Sample', dorder: 'Order',
    gsort: 'Sort games', gday: 'Day', gstatus: 'Game status', pstat: 'Stat', pwin: 'Sample', stakeMode: 'Stake in' };
  const seg = (key, options, current) => `<div class="seg" role="group" aria-label="${esc(SEG_LABEL[key] || key)}">${options.map(([value, label]) =>
    `<button type="button" data-set="${esc(key)}:${esc(value)}" aria-pressed="${String(current) === String(value)}">${esc(label)}</button>`).join('')}</div>`;
  const segLinks = (options, current) => `<nav class="seg" aria-label="Sections">${options.map(([href, label, key]) =>
    `<a href="${esc(href)}" ${key === current ? 'aria-current="page"' : ''}>${esc(label)}</a>`).join('')}</nav>`;
  /* The market spread written for the favorite, like our own number, so both cells name the same team. */
  const favSpread = (home, away, spread) => !isNum(Number(spread)) || spread === null ? '–' : Math.abs(spread) < 0.25 ? 'Pick' : spread < 0 ? `${home} ${spread}` : `${away} -${spread}`;
  const units = u => isNum(u) ? `${u > 0 ? '+' : u < 0 ? '−' : ''}${Math.abs(u).toFixed(2)}u` : '–';
  const wl = s => s ? `${s.wins}–${s.losses}${s.pushes ? `–${s.pushes}` : ''}` : '–';
  const luminance = hex => {
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ''));
    if (!m) return 0;
    const [r, g, b] = [0, 2, 4].map(i => parseInt(m[1].slice(i, i + 2), 16) / 255).map(c => c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  /* Team logos and player photos (owner's call, 2026-10-06): ESPN art as on the old site, with the team-color badge
     underneath as the fallback whenever an image is missing or fails to load. */
  const HEADSHOT = { NFL: id => `https://a.espncdn.com/i/headshots/nfl/players/full/${encodeURIComponent(id)}.png`,
    CFB: id => `https://a.espncdn.com/i/headshots/college-football/players/full/${encodeURIComponent(id)}.png` };
  const logoUrl = (team, league) => {
    if (!team) return null;
    if (/^https:\/\/a\.espncdn\.com\//.test(team.logo || '')) return team.logo;
    if (league === 'NFL' && (team.abbr || team.abbreviation)) return `https://a.espncdn.com/i/teamlogos/nfl/500/${encodeURIComponent(String(team.abbr || team.abbreviation).toLowerCase())}.png`;
    if (league === 'CFB' && /^\d+$/.test(String(team.id || ''))) return `https://a.espncdn.com/i/teamlogos/ncaa/500/${encodeURIComponent(team.id)}.png`;
    return null;
  };
  const teamMark = (team, size = '', league = null) => {
    if (!team) return '';
    const color = /^#[0-9a-f]{6}$/i.test(team.color || '') ? team.color : '#3D5447';
    const ink = luminance(color) > 0.179 ? '#07120D' : '#FFFFFF';
    const abbr = String(team.abbr || team.abbreviation || team.short || team.name || '?').slice(0, 4);
    const logo = logoUrl(team, league);
    return `<span class="tm ${size}${logo ? ' has-logo' : ''}" style="--tc:${esc(color)};--tt:${ink}" aria-hidden="true">${logo ? `<img src="${esc(logo)}" alt="" loading="lazy">` : ''}<em>${esc(abbr)}</em></span>`;
  };
  const headshot = (league, athleteId, size = '', fallbackTeam = null, label = '') => {
    const src = athleteId && HEADSHOT[league] ? HEADSHOT[league](athleteId) : null;
    const color = fallbackTeam && /^#[0-9a-f]{6}$/i.test(fallbackTeam.color || '') ? fallbackTeam.color : '#15301F';
    return `<span class="ava ${size}" style="--tc:${esc(color)}" aria-hidden="true">${src ? `<img src="${esc(src)}" alt="" loading="lazy">` : ''}<em>${esc(label)}</em></span>`;
  };
  /* A pick or line's art: the player's photo on a prop, both teams' logos on a game line. */
  const GAMES = new Map();
  const indexGames = today => { (today && today.games || []).forEach(g => GAMES.set(g.id, g)); gameLookup = id => GAMES.get(id); };
  const artFor = (row, size = '') => {
    const league = row.league || String(row.gameId || '').split('-')[0];
    const initials = String(row.player || '').split(/\s+/).filter(w => /^[A-Z]/.test(w)).slice(0, 2).map(w => w[0]).join('');
    if (row.athleteId && HEADSHOT[league]) return headshot(league, row.athleteId, size, null, row.position || initials);
    const g = GAMES.get(row.gameId || (row.gameIds || [])[0]);
    if (!g) return '';
    return `<span class="ava-pair ${size}">${teamMark(g.away, 'sm', g.league)}${teamMark(g.home, 'sm', g.league)}</span>`;
  };
  const meter = (chance, needs, felt = false) => isNum(chance) && isNum(needs)
    ? `<div class="meter${felt ? ' felt' : ''}" role="img" aria-label="Our chance ${pctText(chance)}. The price needs ${pctText(needs)}."><i style="width:${Math.max(2, Math.min(100, 100 * chance)).toFixed(1)}%"></i><em style="left:calc(${(100 * needs).toFixed(1)}% - 1px)"></em></div>`
    : '';

  /* ☆ Save for lines, players and games, with the same keys and shapes the old site stored. */
  const watchCandidates = new Map();
  const watchButton = (item, cls = 'btn small') => {
    watchCandidates.set(item.key, item);
    const on = state.watchlist.some(r => r.key === item.key);
    return `<button type="button" class="${cls}" data-watch="${esc(item.key)}" aria-pressed="${on}" aria-label="${on ? 'Unsave' : 'Save'} ${esc(item.title)}">${on ? '★ Saved' : '☆ Save'}</button>`;
  };
  const onTicket = id => state.ticket.some(r => r.id === id);
  const ticketButton = (id, title) => `<button type="button" class="btn small" data-add-line="${esc(id)}" aria-pressed="${onTicket(id)}" aria-label="${onTicket(id) ? 'Remove from' : 'Add to'} my ticket: ${esc(title || 'line')}">${onTicket(id) ? '✓ On ticket' : '+ Ticket'}</button>`;

  /* The ticket: the hero of Today. */
  const watchKey = vm => 'pick:' + vm.id;
  const countdown = iso => {
    const ms = Date.parse(iso) - Date.now();
    if (!(ms > 0) || ms > 24 * 3600000) return '';
    if (ms < 60000) return 'kicks off in under a minute';
    const mins = Math.ceil(ms / 60000), h = Math.floor(mins / 60), m = mins % 60;
    return `kicks off in ${h ? `${h}h ` : ''}${m}m`;
  };
  /* Whole percents, unless rounding would make our chance and the price's need look equal. */
  const pctPair = (a, b) => Math.abs(Math.round(100 * a) - Math.round(100 * b)) >= 2 ? [pctText(a), pctText(b)] : [`${(100 * a).toFixed(1)}%`, `${(100 * b).toFixed(1)}%`];
  const ticket = (pick, opts = {}) => {
    const vm = pickVM(pick);
    const compact = opts.compact;
    const tag = vm.featured ? 'Pick of the Day' : vm.kind === 'climb' ? '80/20 Climb' : vm.kind === 'fun' ? (vm.lotto ? 'Fun ticket · Lotto' : 'Fun ticket') : 'Best bet';
    const priced = vm.kind === 'best' && vm.chance != null && vm.needs != null && vm.calibrated;
    const [c, n] = priced ? pctPair(vm.chance, vm.needs) : ['', ''];
    const plain = priced && vm.mode === 'open'
      ? `<p class="plain">We think this hits <strong>${c}</strong> of the time. At ${esc(oddsText(vm.odds))} you only need ${n}.</p>${meter(vm.chance, vm.needs)}`
      : priced && vm.mode === 'expired' && !compact ? `<p class="plain">When we posted it at ${esc(oddsText(vm.odds))}, we had this at <strong>${c}</strong>. That price needed ${n}.</p>${meter(vm.chance, vm.needs)}`
        : vm.legs.length ? `<p class="plain">${vm.legs.length} legs · ${vm.kind === 'climb' ? 'tracked in dollars, apart from the best-bet record' : 'tracked apart from the best-bet record'}.</p>` : '';
    const facts = vm.kind === 'best' && !compact && vm.fair != null && vm.mode !== 'closed'
      ? `<div class="facts"><div><small>Fair price</small><b class="num">${esc(oddsText(vm.fair))}</b></div><div><small>Edge</small><b class="num">${vm.edge > 0 ? '+' : ''}${esc(vm.edge)} pts</b></div><div><small>Status</small><b>${esc(vm.mode === 'expired' ? 'Old price' : vm.status)}</b></div></div>` : '';
    const why = !compact && vm.mode !== 'closed' && (vm.why.length || vm.watch) ? `<ul class="why">${vm.why.map(x => `<li${CONTEXT.test(x) ? ' class="ctx"' : ''}>${esc(x)}</li>`).join('')}${vm.watch ? `<li class="watch">${esc(vm.watch)}</li>` : ''}</ul>` : '';
    /* The hit chart counts only games before this one once it has kicked off, so a receipt shows what was known. */
    const started = Date.parse(pick.kickoff) <= Date.now();
    const chart = !compact && vm.kind === 'best' && pick.athleteId && FOOTBALL.includes(pick.league) && C.marketKey(pick) ? `<div class="ticket-chart" data-prop-history data-league="${esc(pick.league)}" data-athlete="${esc(pick.athleteId)}" data-stat="${esc(C.marketKey(pick))}" data-line="${esc(pick.line)}" data-dir="${esc(pick.direction || 'over')}" data-game="${esc(pick.gameId || '')}" data-before="${pick.result || started ? esc(C.dayOf(pick.kickoff) || '') : ''}"></div>` : '';
    const hist = !compact && !chart && vm.history ? `<p class="meta"><b>History:</b> ${esc(vm.history.replace(/^Last (\d+) games?:/i, 'last $1 games (can include last season):').replace(/^(This season|Season):/i, 'this season:'))} ${esc((pick.reasoning || {}).historyNote || 'History, not a probability.')}</p>` : '';
    const legs = !compact && vm.legs.length ? `<ul class="why legs">${vm.legs.slice(0, 8).map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '';
    const isSaved = state.watchlist.some(r => r.key === watchKey(vm));
    const clock = countdown(vm.kickoff);
    /* What the Details fold holds, in a few words, so a reader knows whether to open it. */
    const moreHint = [why ? 'why' : '', chart ? 'hit chart' : hist ? 'history' : '', facts ? 'fair price' : '', legs ? 'legs' : '', !facts && !why && !legs ? 'status' : ''].filter(Boolean).join(' · ');
    return `<article class="ticket${compact ? ' compact' : ''}${vm.mode === 'closed' ? ' is-closed' : ''}" aria-label="${esc(tag)}: ${esc(vm.title)}">
      <div class="ticket-body">
        <div class="ticket-top"><span class="tag${vm.kind !== 'best' ? ' fun' : ''}">${esc(tag)}</span><span>${esc(clock || whenShort(vm.kickoff))}</span></div>
        <div class="ticket-rule"></div>
        <div class="t-head">${artFor(pick, compact ? '' : 'md')}<div><h3>${opts.onPage ? esc(vm.title) : `<a href="${esc(vm.href)}">${esc(vm.title)}</a>`}</h3>
        <p class="market">${esc(vm.market)}${vm.league ? ` · ${esc(vm.league === 'CFB' ? 'College' : vm.league)}` : ''}</p></div></div>
        <div class="price"><b class="num">${esc(oddsText(vm.odds))}</b><span>${vm.estimated ? 'est. · ' : ''}${esc(vm.book || '')}${vm.mode !== 'open' && !vm.result ? ' · posted price' : ''}</span></div>
        ${plain}${vm.statusShort ? `<p class="meta strong">${esc(vm.statusShort)}</p>` : ''}
        ${compact ? '' : `<details class="t-more" data-box="t:${esc(pick.id)}"${opts.onPage ? ' open' : ''}><summary>Details<span>${esc(moreHint)}</span></summary>
          ${facts}${why}${hist}${chart}${legs}
          ${vm.estimated ? '<p class="meta">Combined odds are estimated from the captured leg prices. Check the real ticket price at your book.</p>' : ''}
          ${vm.statusNote ? `<p class="meta${vm.mode === 'closed' ? ' strong' : ''}">${esc(vm.statusNote)}</p>` : ''}<p class="meta">${esc(C.deliveryText(pick) || '')}</p></details>
        <div class="actions">${opts.onPage ? '' : `<a class="btn small" href="${esc(vm.href)}">How we got this</a>`}<button type="button" class="btn small" data-watch-pick="${esc(pick.id)}" aria-pressed="${isSaved}" aria-label="${isSaved ? 'Unsave' : 'Save'} ${esc(vm.title)}">${isSaved ? '★ Saved' : '☆ Save'}</button></div>`}
      </div>
      <div class="stub ${esc(vm.stub.cls)}" role="img" aria-label="${esc(vm.stub.small)}${vm.stub.big && vm.stub.big.length > 1 ? ' ' + esc(vm.stub.big) : ''}"><b aria-hidden="true">${esc(vm.stub.big)}</b><small aria-hidden="true">${esc(vm.stub.small)}</small></div>
    </article>`;
  };

  /* ROI at posted prices: units over plays staked (one unit each), only once ten priced plays are graded. */
  const roiOf = cap => cap.priced >= 10 && cap.staked > 0 && isNum(cap.units) ? 100 * cap.units / cap.staked : null;
  /* Owner decisions still open (HANDOFF §7 R7 and §13): closing-line value as a headline number and a public ROI.
     Until the owner says yes, CLV stays on Model vs market and the receipts, and ROI is not shown. */
  const OWNER_FLAGS = { clvHeadline: false, roi: false };
  const kpiStrip = (picks, board, rows = null, label = null) => {
    const archive = rows ? null : C.recordArchive(picks);
    const scoped = rows || archive.rows;
    const straight = scoped.filter(p => !C.isParlay(p));
    const rec = C.recordBreakdown(straight);
    rec.captured.roi = OWNER_FLAGS.roi ? roiOf(rec.captured) : null;
    const ids = new Set(scoped.map(p => p.id));
    const clv = clvSummary((((board || {}).picks || {}).rows || []).filter(r => ids.has(r.id)));
    const graded = rec.all.wins + rec.all.losses + rec.all.pushes;
    const playoffs = archive && Object.values(archive.phaseByLeague).length && Object.values(archive.phaseByLeague).every(v => v === 'playoffs');
    const potd = C.summaryOf(straight.filter(p => p.featured && p.posted && !C.isUnpricedImport(p)), 1);
    const mixed = archive && new Set(Object.values(archive.phaseByLeague)).size > 1;
    const head = label || (playoffs ? 'Playoff record' : mixed ? 'Record · current stages' : 'Season record');
    return { rec, clv, graded, label: head, html: `<div class="kpis">
      <div class="kpi"><small>${esc(head)}</small><b class="num">${esc(wl(rec.all))}</b><span>every best bet, win or lose</span></div>
      <div class="kpi"><small>Units</small><b class="num ${rec.captured.units < 0 ? 'red' : rec.captured.units > 0 ? 'green' : ''}">${esc(units(rec.captured.units))}</b><span>at the prices we posted${rec.captured.roi != null ? ` · ROI ${rec.captured.roi > 0 ? '+' : ''}${rec.captured.roi.toFixed(1)}%` : ''}</span></div>
      ${OWNER_FLAGS.clvHeadline ? `<div class="kpi"><small>Beat the closing line</small><b class="num">${clv.measured ? `${clv.beat} of ${clv.measured}` : '–'}</b><span>${clv.measured ? `${clv.tied} tied · ${clv.lost} lost` : 'not measured yet'}</span></div>`
        : `<div class="kpi"><small>Pick of the Day</small><b class="num">${esc(wl(potd))}</b><span>one featured play a day</span></div>`}
      <div class="kpi"><small>Graded in public</small><b class="num">${graded}</b><span>plays in this view</span></div></div>` };
  };

  /* ---------- live scores (factual refresh only; odds and picks stay on the desk's snapshots) ---------- */
  const LIVE = { NFL: ['football', 'nfl', ''], CFB: ['football', 'college-football', '&groups=80&limit=1000'], NBA: ['basketball', 'nba', ''],
    WNBA: ['basketball', 'wnba', ''], CBB: ['basketball', 'mens-college-basketball', '&groups=50&limit=1000'], MLB: ['baseball', 'mlb', ''],
    NHL: ['hockey', 'nhl', ''], EPL: ['soccer', 'eng.1', ''], MLS: ['soccer', 'usa.1', ''] };
  let liveTimer = null;
  const liveCache = L.createCache({ fetcher: (...args) => fetch(...args), changed: () => { clearTimeout(liveTimer); liveTimer = setTimeout(() => refreshPage(), 150); } });
  /* ESPN's status, including postponed, cancelled, delayed and suspended (ported from the old liveState). */
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
    const comp = (event.competitions || [])[0];
    if (!comp) return null;
    const status = comp.status || event.status || {}, type = status.type || {};
    const [kind, completed, stateName] = liveState(status);
    const teams = {};
    for (const row of comp.competitors || []) {
      if (!['home', 'away'].includes(row.homeAway)) continue;
      const raw = row.score && typeof row.score === 'object' ? (row.score.value ?? row.score.displayValue) : row.score;
      const score = ['scheduled', 'postponed', 'cancelled'].includes(kind) || raw == null || raw === '' ? null : Number(raw);
      teams[row.homeAway] = { id: String((row.team || {}).id || ''), name: (row.team || {}).displayName || '', abbreviation: (row.team || {}).abbreviation || '', color: (row.team || {}).color ? '#' + row.team.color : null, logo: (row.team || {}).logo || '', score: isNum(score) ? score : null };
    }
    if (!teams.home || !teams.away) return null;
    return { id: `${league}-${event.id}`, providerId: String(event.id), league, status: kind, completed, state: stateName,
      statusDetail: type.shortDetail || type.description || '', kickoff: comp.date || event.date, teams, pregameOdds: L.pregameOdds ? L.pregameOdds(comp, kind) : null,
      source: { url: (event.links || []).find(link => /^https:\/\/(www\.)?espn\.com\//.test(link.href || ''))?.href || '' } };
  };
  const liveFor = (league, day) => {
    const cfg = LIVE[league];
    if (!cfg) return null;
    const url = `https://site.web.api.espn.com/apis/site/v2/sports/${cfg[0]}/${cfg[1]}/scoreboard?dates=${day.replaceAll('-', '')}${cfg[2]}`;
    return liveCache.read(`${league}:${day}`, url, e => liveEvent(e, league));
  };

  /* Live football scores merged into our stored games (today, yesterday and anything in progress), like the old site. */
  const withLive = games => {
    const days = [...new Set([etDay(), etDay(-1), ...games.filter(g => g.state === 'in').map(g => C.dayOf(g.kickoff))])].slice(0, 3);
    const leagues = [...new Set(games.filter(g => FOOTBALL.includes(g.league) && (days.includes(C.dayOf(g.kickoff)) || g.state === 'in')).map(g => g.league))];
    const snaps = leagues.flatMap(l => days.map(d => liveFor(l, d))).filter(Boolean);
    const live = new Map(snaps.flatMap(x => x.games || []).map(g => [g.id, g]));
    const ok = snaps.filter(x => x.at);
    const refreshed = { at: ok.length ? Math.min(...ok.map(x => x.at)) : null, failed: snaps.some(x => x.failed), asked: leagues.length > 0 };
    return { refreshed, games: games.map(g0 => {
      /* The stored feed copies ESPN's postponed state as 'post' with 0–0; never read that as a final. */
      const g = !g0.completed && /postpon|cancel/i.test(String(g0.status || '')) ? { ...g0, state: 'pre', statusWord: /cancel/i.test(g0.status) ? 'Cancelled' : 'Postponed', away: { ...g0.away, score: null }, home: { ...g0.home, score: null } } : g0;
      const n = live.get(g.id);
      if (!n) return g;
      /* Postponed or cancelled: say so, keep our projection, never draw a 0–0 final. */
      if (['postponed', 'cancelled'].includes(n.status)) return { ...g, state: 'pre', completed: false, statusWord: n.status === 'postponed' ? 'Postponed' : 'Cancelled', away: { ...g.away, score: null }, home: { ...g.home, score: null } };
      if (!['in_progress', 'final', 'delayed', 'suspended'].includes(n.status)) return g;
      return { ...g, state: n.state, completed: n.completed, status: n.statusDetail || g.status,
        away: { ...g.away, score: n.teams.away.score }, home: { ...g.home, score: n.teams.home.score } };
    }) };
  };
  const liveStamp = snap => {
    if (!snap || (!snap.asked && !snap.at)) return '';
    const f = L.freshness(snap);
    const at = snap.at ? ago(new Date(snap.at).toISOString()) : '';
    return `<p class="small muted live-stamp" role="status"><span class="status-dot${f === 'fresh' ? '' : ' old'}"></span>${f === 'fresh' ? `Scores checked ${esc(at)} · refreshes about every minute`
      : snap.at ? `Score refresh unavailable · last checked ${esc(at)}` : snap.failed ? 'Score feed unavailable · saved scores shown' : 'Checking scores · saved scores shown until connected'}</p>`;
  };

  /* =====================================================================
     VIEWS
     ===================================================================== */

  const VIEWS = {};

  /* ---------- Today (A: plain English) ---------- */
  const money = n => `$${Math.round(Number(n) || 0).toLocaleString('en-US')}`;
  const signedMoney = n => { const v = Math.round(Number(n) || 0); return `${v > 0 ? '+' : v < 0 ? '−' : ''}$${Math.abs(v).toLocaleString('en-US')}`; };
  /* The Climb in one compact block: what cashed, what's next, the ledger and every past step's exact lines. */
  const climbStatus = lad => {
    const open = lad.open, info = (open && open.ladder) || {}, last = lad.history[lad.history.length - 1];
    if (open) return `Step ${info.step || lad.step} is live`;
    if (last && last.result === 'win') return `Step ${(last.ladder || {}).step || lad.step - 1} cashed · Step ${lad.step} is being checked · not posted yet`;
    if (last && last.result === 'loss') return 'The last climb ended · Step 1 is being checked · not posted yet';
    return lad.history.length ? `Step ${lad.step} is being checked · not posted yet` : 'The first step waits for two clean games';
  };
  const climbStrip = lad => {
    const open = lad.open, info = (open && open.ladder) || {};
    const riding = Number(open ? info.stake : lad.stake) || 50, banked = Number(open ? info.banked : lad.banked) || 0;
    const a = lad.accounting || {};
    const pct = n => Math.max(3, Math.min(100, 100 * Math.log(Math.max(50, Number(n) || 50) / 50) / Math.log(20)));
    const past = lad.history.slice().reverse().map(r => {
      const i = r.ladder || {}, total = r.ladderTotal || {};
      const paid = r.result === 'win' ? money(i.payout) : r.result === 'loss' ? '$0' : money(i.stake);
      return `<div class="receipt"><span class="r-mark ${r.result === 'win' ? 'hit' : r.result === 'loss' ? 'miss' : 'push'}" aria-hidden="true">${r.result === 'win' ? '✓' : r.result === 'loss' ? '✗' : '–'}</span><div><b><span class="sr">${r.result === 'win' ? 'Hit' : r.result === 'loss' ? 'Miss' : 'Push'}: </span><a class="plain-link" href="#pick/${esc(encodeURIComponent(r.id))}">Step ${esc(i.step || '')}</a> · ${esc(whenShort(r.kickoff || r.publishedAt))}</b><span>${esc((r.legs || []).map(l => typeof l === 'string' ? l : l.title).filter(Boolean).map(niceTitle).join(' · '))}</span></div>
        <span class="u ${r.result === 'win' ? 'green' : r.result === 'loss' ? 'red' : 'muted'}">${esc(money(i.stake))} → ${esc(paid)}<br><span class="tiny muted">running ${esc(signedMoney(total.net))}</span></span></div>`;
    }).join('');
    return `<div class="card on-felt climb"><p class="eyebrow green">80/20 Climb · climb #${esc(lad.run)}</p>
      <p style="margin-top:4px"><b class="num" style="font-size:28px">${money(riding)}</b> <span class="small">${esc(climbStatus(lad))} · ${money(banked)} banked</span></p>
      <div class="ladder" role="img" aria-label="${esc(money(banked + riding))} of $1,000"><i style="width:${pct(banked + riding).toFixed(1)}%"></i></div>
      <div class="ladder-ends"><span>$50 start</span><span>${money(banked + riding)} now</span><span>$1,000 goal</span></div>
      <p class="small muted" style="margin-top:8px">Steps ${esc(a.wins || 0)}–${esc(a.losses || 0)} · settled stake ${money(a.wagered)} · returned ${money(a.returned)} · net <span class="${a.net < 0 ? 'red' : a.net > 0 ? 'green' : ''}">${esc(signedMoney(a.net))}</span>${a.atRisk ? ` · live now ${money(a.atRisk)}` : ''}</p>
      ${past ? `<details class="more-box" style="margin-top:10px"><summary>Past steps · ${lad.history.length} · ${esc(signedMoney(a.net))} overall</summary><div class="receipts">${past}</div></details>` : ''}
      <p class="small muted" style="margin-top:8px">Win: bank 20%, ride 80%. A miss starts a new $50 climb; banked money stays banked. <a href="#record/climb">Climb history →</a></p></div>`;
  };
  const currentUpset = (g, now) => g.upsetWatch && g.state === 'pre' && !g.completed && Date.parse(g.kickoff) > now
    && now >= Date.parse(g.upsetWatch.observedAt) && now - Date.parse(g.upsetWatch.observedAt) <= 4 * 3600000;
  const upsetRow = (g, rank) => {
    const w = g.upsetWatch;
    return `<a class="card" style="display:block;color:inherit" href="#game/${esc(g.id)}"><p><b>${esc(w.team)} · ${esc(oddsText(w.odds))} to win outright</b>${rank === 1 ? ' <span class="badge research">Top upset signal</span>' : ''}</p>
      <p class="small" style="margin-top:2px">Our chance ${pctText(w.modelChance)} · market (no vig) ${pctText(w.marketChanceNoVig)}</p>
      ${(w.reasons || []).length ? `<ul class="fa" style="margin-top:6px">${w.reasons.slice(0, 4).map(r => `<li class="for">${esc(r)}</li>`).join('')}</ul>` : ''}
      <p class="small muted" style="margin-top:6px">${esc(whenShort(g.kickoff))} · ${esc(bookLabel(w.book) || w.book || '')} · opposing ML ${esc(oddsText(w.opponentOdds))} · captured ${esc(ago(w.observedAt))}</p>
      <p class="small red" style="margin-top:2px">${esc((w.warnings || [w.caution || 'Raw winner estimate, not a calibrated moneyline edge.']).join(' · '))}</p></a>`;
  };
  const communityCard = () => `<aside class="card on-felt community" aria-label="Join the Kook'n Discord"><div><p class="eyebrow green">Free Kook'n Discord</p><p style="margin-top:4px"><b>Best bets land here about 10–15 minutes before X.</b> Time-sensitive arb candidates stay in Discord. Every result stays public here.</p></div><a class="btn primary" href="https://discord.gg/CvNTUUSnNz" target="_blank" rel="noopener">Join the free Discord ↗</a></aside>`;
  /* Sports without best bets get their own honest Today: scores and their trial, never football substituted. */
  const sportToday = async () => {
    const [lab, trials] = await Promise.all([maybe('market-lab.json'), maybe('app/sport-research.json')]);
    const lg = state.league;
    const card = trialCard(lg, lab, trials);
    const scores = await gamesLive({ day: etDay() });
    const hasTrial = ((trials || {}).leagues || {})[lg], hasLab = ((lab || {}).leagues || {})[lg];
    const status = hasTrial ? 'in a paper trial, not official picks' : hasLab ? 'collecting data for a future model, not picks' : 'scores only for now: no picks or research yet';
    return `${head(dayLabel(todayISO()), `${LEAGUE_NAME[lg]} · Today`, hasTrial || hasLab ? 'No best bets in this sport. Scores and research are below.' : 'No best bets in this sport. Scores are below.')}
      <div class="card on-felt" style="margin-bottom:14px"><p class="small"><b>${esc(LEAGUE_NAME[lg])} is ${esc(status)}.</b> No football data is substituted. <a href="#record/trials">All sports' status →</a></p></div>
      <div style="margin-bottom:14px">${card}</div>
      ${scores}<p class="small" style="margin-top:12px"><a href="#games/live">All scores →</a></p>`;
  };
  VIEWS.today = async route => {
    if (route && route.league && location.hash !== appliedHash) { appliedHash = location.hash; setLeague(route.league); }
    if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return sportToday();
    const [today, board, notes, lines, sports, every] = await Promise.all([get('app/today.json'), maybe('scoreboard.json'), maybe('desk-notes.json'), maybe('app/lines.json'), state.league === 'ALL' ? maybe('sports.json') : null, allPicks()]);
    indexGames(today);
    const now = Date.now();
    const all = every;
    const picks = all.filter(inLeague);
    const sched = C.cardSchedule(picks, now);
    const pulled = p => p.status === 'withdrawn' || /before its post went out/.test(p.entryNote || '');
    const order = (a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)) || String(a.kickoff).localeCompare(String(b.kickoff));
    const bets = sched.today.filter(p => !C.isParlay(p) && !pulled(p)).sort(order);
    const upcoming = sched.upcoming.filter(p => !C.isParlay(p) && !pulled(p)).sort(order);
    const gone = [...sched.today, ...sched.upcoming, ...sched.awaiting].filter(p => !C.isLadder(p) && pulled(p));
    const awaiting = sched.awaiting.filter(p => !C.isLadder(p) && !pulled(p));
    const fun = [...sched.today, ...sched.upcoming].filter(p => C.isParlay(p) && !C.isLadder(p) && !pulled(p));
    const ladder = C.theLadder(all);
    const games = (today.games || []).filter(inLeague);
    const todays = games.filter(g => C.dayOf(g.kickoff) === etDay());
    const k = kpiStrip(all.filter(inLeague), board);

    const onboarded = saved.get('onboarded', false);
    const onboard = onboarded ? '' : `<div class="onboard" role="note">
      <div><b><span class="step-n">1</span>Best bets are our picks</b><span>Posted with the price, the book and our honest chance.</span></div>
      <div><b><span class="step-n">2</span>Research is the data</b><span>Every line we track, sorted by edge. Not a pick unless it says Best bet.</span></div>
      <div><b><span class="step-n">3</span>Every result is graded</b><span>Green ticket hit, red ticket missed. Nothing is hidden.</span></div>
      <button type="button" class="btn small" data-dismiss-onboard>Got it</button></div>`;

    const et = Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hourCycle: 'h23' }).format(new Date(now)));
    const reason = !todays.length ? 'No covered games today' : todays.every(g => Date.parse(g.kickoff) <= now) ? "Today's games have already started"
      : "Nothing for today's games has cleared our price checks yet";
    const nextGame = games.filter(g => Date.parse(g.kickoff) > now && C.dayOf(g.kickoff) > etDay()).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0];
    const nextWindow = et < 12 && todays.some(g => Date.parse(g.kickoff) > now) ? 'The next release window is around noon ET, about two hours before the earliest kickoff.'
      : nextGame ? `The next release window is around noon ET on ${dayLabel(nextGame.kickoff)}, or about two hours before an earlier kickoff.` : 'No covered games are scheduled yet.';
    const byDay = new Map();
    upcoming.forEach(p => { const d = C.dayOf(p.kickoff); if (!byDay.has(d)) byDay.set(d, []); byDay.get(d).push(p); });
    const days = [...byDay.entries()];
    const climb = climbStrip(ladder);
    const rungHere = ladder.open && (state.league === 'ALL' || ladder.open.league === state.league);
    const climbOpen = rungHere ? `<div class="tickets">${ticket(ladder.open)}</div>` : '';
    /* Order on the card: Pick of the Day, then the Climb, then the rest (the owner's phone-first rule). */
    /* Pick of the Day, then a live Climb step, then the rest. An unposted Climb is a small status after the card. */
    const climbStatusBox = `<details class="more-box climb-status" data-box="climb-status"><summary>80/20 Climb · ${esc(climbStatus(ladder))} · ${money(ladder.banked)} banked</summary>${climb}</details>`;
    const heroList = list => { const potd = list.filter(p => p.featured), rest = list.filter(p => !p.featured);
      return `${potd.length ? `<div class="tickets wide">${potd.map(p => ticket(p)).join('')}</div>` : ''}${rungHere ? `<div style="margin:14px 0">${climbOpen}${climb}</div>` : ''}${rest.length ? `<div class="tickets wide"${potd.length ? ' style="margin-top:14px"' : ''}>${rest.map(p => ticket(p)).join('')}</div>` : ''}${rungHere ? '' : `<div style="margin-top:14px">${climbStatusBox}</div>`}`; };
    const graded = picks.filter(p => p.result && !p.historicalImport && !C.isParlay(p) && C.dayOf(p.kickoff));
    const lastDay = graded.map(p => C.dayOf(p.kickoff)).filter(d => d < etDay()).sort().pop();
    const recent = lastDay ? graded.filter(p => C.dayOf(p.kickoff) === lastDay).sort((a, b) => String(b.kickoff).localeCompare(String(a.kickoff))) : [];
    const gradedToday = graded.filter(p => C.dayOf(p.kickoff) === etDay());
    let heroTitle, heroSub, heroHtml, laterHtml = '';
    if (bets.length) {
      heroTitle = "Today's best bets";
      heroSub = `${bets.length} best bet${bets.length === 1 ? '' : 's'} today${state.league !== 'ALL' ? ` in ${esc(LEAGUE_NAME[state.league])}` : ''}.`;
      heroHtml = heroList(bets) + (gradedToday.length ? `<p class="eyebrow" style="margin:16px 0 8px">Already graded today</p><div class="receipts">${gradedToday.map(p => receipt(p, new Map(((board || {}).picks || {}).rows?.map(r => [r.id, r.clv]) || []))).join('')}</div>` : '');
      laterHtml = days.map(([, list]) => `<p class="eyebrow" style="margin:14px 0 8px">${esc(dayLabel(list[0].kickoff))}</p><div class="tickets wide">${list.map(p => ticket(p, { compact: true })).join('')}</div>`).join('');
    } else if (gradedToday.length) {
      const gsum = C.summaryOf(gradedToday.filter(p => !C.isUnpricedImport(p)), 1);
      heroTitle = "Today's best bets · graded";
      heroSub = `${gradedToday.length} best bet${gradedToday.length === 1 ? '' : 's'} today, already graded: ${esc(wl(gsum))} · ${esc(units(gsum.units))}.${days.length ? ` The next ${days[0][1].length === 1 ? 'one is' : 'ones are'} posted for ${esc(dayLabel(days[0][1][0].kickoff))}.` : ''}`;
      heroHtml = `<div class="receipts">${gradedToday.map(p => receipt(p, new Map(((board || {}).picks || {}).rows?.map(r => [r.id, r.clv]) || []))).join('')}</div>${days.length ? `<div class="tickets wide" style="margin-top:14px">${days[0][1].map(p => ticket(p)).join('')}</div>` : ''}<div style="margin-top:14px">${rungHere ? climbOpen + climb : climbStatusBox}</div>`;
      laterHtml = days.slice(1).map(([, list]) => `<p class="eyebrow" style="margin:14px 0 8px">${esc(dayLabel(list[0].kickoff))}</p><div class="tickets wide">${list.map(p => ticket(p, { compact: true })).join('')}</div>`).join('');
    } else if (days.length) {
      const [, first] = days[0];
      heroTitle = first.length === 1 ? 'Next best bet' : 'Next best bets';
      heroSub = `${esc(reason)}. ${first.length === 1 ? 'The next one is' : 'The next ones are'} already posted for ${esc(dayLabel(first[0].kickoff))}.`;
      heroHtml = heroList(first);
      laterHtml = days.slice(1).map(([, list]) => `<p class="eyebrow" style="margin:14px 0 8px">${esc(dayLabel(list[0].kickoff))}</p><div class="tickets wide">${list.map(p => ticket(p, { compact: true })).join('')}</div>`).join('');
    } else {
      heroTitle = "Today's best bets";
      heroSub = 'Free daily picks with the price, the book and our honest chance.';
      heroHtml = `${empty('No best bet yet', `${esc(reason)}. We never force a play. ${esc(nextWindow)} That's a window, not a promise. <a href="#research">See the research board →</a> · <a href="#schedule">Release schedule</a>`)}<div style="margin-top:14px">${rungHere ? climbOpen + climb : climbStatusBox}</div>`;
    }

    /* Last game day: yesterday's hits and misses, right under the card. */
    const clvById = new Map(((board || {}).picks || {}).rows?.map(r => [r.id, r.clv]) || []);
    const recentSum = C.summaryOf(recent.filter(p => !C.isUnpricedImport(p)), 1);
    const recentHtml = recent.length ? `<details class="more-box"><summary>Last game day · ${esc(dayLabel(recent[0].kickoff))} · ${esc(wl(recentSum))} · ${esc(units(recentSum.units))}</summary><div class="receipts">${recent.map(p => receipt(p, clvById)).join('')}</div><p class="small" style="margin-top:8px"><a href="#record">Full record →</a></p></details>` : '';

    /* Anything already on the card (open or not) stays out of "Worth a look". */
    const official = new Set(picks.filter(p => !p.result && !p.historicalImport && !C.isParlay(p)).map(officialKey));
    const gameIndex = new Map((today.games || []).map(g => [g.id, g]));
    const withGame = vm => { const g = gameIndex.get(vm.gameId); vm.matchup = g ? `${g.away.abbr} at ${g.home.abbr}` : null; return vm; };
    const current = vm => vm.age.kind === 'fresh' || vm.age.kind === 'aging';
    const lineRows = lines ? (lines.lines || []).map(r => withGame(lineVM(r, now))).filter(vm => inLeague(vm) && onBoard(vm, now) && current(vm)) : [];
    const research = collapse(lineRows.filter(vm => hasValue(vm) && !official.has(vm.key))).sort(SORTS.edge).slice(0, 3);
    const notesList = C.deskNotes(notes, state.league, now, today.games || []);
    const worth = research.length || notesList.length ? `${research.length ? `<div class="board">${research.map(vm => boardRow(vm, false)).join('')}</div>` : ''}
      ${notesList.length ? `<div class="grid two" style="margin-top:10px">${notesList.map(n => { const g = gameIndex.get(n.gameId);
        return `<details class="more-box"><summary>${esc(n.label || 'Research note')} · ${esc(n.title)}</summary><div><p class="small">${esc(n.text)}</p><p class="small muted" style="margin-top:6px">${g ? `${esc(g.away.abbr)} at ${esc(g.home.abbr)} · ` : ''}${esc(whenShort(n.kickoff))} · as of ${esc(ago(n.observedAt))}</p><p class="small" style="margin-top:6px"><a href="${esc(n.href)}">Explore →</a></p></div></details>`; }).join('')}</div>` : ''}`
      : empty('Nothing worth a look right now', 'No current, priced research line clears our value bar. The board stays empty instead of filling space.', 'research');

    /* Underdog watch: fresh outright candidates (both moneylines within four hours), and spread covers kept apart. */
    const upsets = games.filter(g => currentUpset(g, now)).sort((a, b) => (b.upsetWatch.modelChance - b.upsetWatch.marketChanceNoVig) - (a.upsetWatch.modelChance - a.upsetWatch.marketChanceNoVig)).slice(0, 4);
    const dogSpreads = lineRows.filter(vm => !vm.isProp && /spread/i.test(vm.market) && Number(vm.line) > 0 && hasValue(vm));
    const firstDay = dogSpreads.length ? C.dayOf(dogSpreads.slice().sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0].kickoff) : null;
    const spreadRows = dogSpreads.filter(vm => C.dayOf(vm.kickoff) === firstDay).sort(SORTS.edge).slice(0, 4);
    const upsetHtml = upsets.length || spreadRows.length ? `<p class="eyebrow" style="margin-bottom:8px">Outright upset candidates</p>${upsets.length ? `<div class="grid two">${upsets.map((g, i) => upsetRow(g, i + 1)).join('')}</div>` : '<p class="muted small">No fresh outright candidate.</p>'}
      <p class="eyebrow" style="margin:16px 0 4px">Underdog spread value</p><p class="small muted" style="margin-bottom:8px">Covering does not mean winning outright.</p>${spreadRows.length ? `<div class="board">${spreadRows.map(vm => boardRow(vm, false)).join('')}</div>` : '<p class="muted small">No spread highlighted.</p>'}`
      : '<p class="muted small">No current outright-upset or underdog-spread highlight.</p>';

    /* Today's games: what's live first, with scores refreshed from the free scoreboard. */
    const liveToday = withLive(games.filter(g => C.dayOf(g.kickoff) === etDay() || (!g.completed && (g.state === 'in' || C.dayOf(g.kickoff) === etDay(-1)))));
    liveToday.games = liveToday.games.filter(g => C.dayOf(g.kickoff) === etDay() || g.state === 'in');
    const rank = g => g.state === 'in' ? 0 : !g.completed ? 1 : 2;
    const tonight = liveToday.games.slice().sort((a, b) => rank(a) - rank(b) || String(a.kickoff).localeCompare(String(b.kickoff))).slice(0, 6);
    const tonightHtml = tonight.length ? `${liveStamp(liveToday.refreshed)}<div class="projs">${tonight.map(g => projCard(g, { ranks: false })).join('')}</div>${liveToday.games.length > tonight.length ? `<p class="small" style="margin-top:10px"><a href="#games">All ${liveToday.games.length} games today →</a></p>` : ''}` : `<p class="muted small">No covered football games today. <a href="#games/live">Scores for every sport</a></p>`;
    const sportsHtml = state.league === 'ALL' ? `<details class="more-box"><summary>More sports · scores and research for nine leagues</summary><div class="pill-row" style="padding-top:4px">${Object.keys(LIVE).map(key => { const n = ((((sports || {}).leagues || {})[key] || {}).games || []).filter(g => g.date === etDay()).length;
      return `<a class="pill" href="#today?sport=${esc(key)}">${esc(LEAGUE_NAME[key])}${FOOTBALL.includes(key) ? '' : ` · ${n} today`} →</a>`; }).join('')}</div></details>` : '';

    return `${onboard}
      ${head(dayLabel(todayISO()), heroTitle, heroSub)}
      <div class="proof"><a class="pill" href="#record">${esc(k.label === 'Season record' ? 'Season' : k.label === 'Playoff record' ? 'Playoffs' : 'This stage')} <b class="num">${esc(wl(k.rec.all))}</b></a>${isNum(k.rec.captured.units) ? `<a class="pill ${k.rec.captured.units < 0 ? 'bad' : k.rec.captured.units > 0 ? 'good' : ''}" href="#record">${esc(units(k.rec.captured.units))} at posted prices</a>` : ''}${OWNER_FLAGS.clvHeadline && k.clv.measured ? `<a class="pill" href="#record/model">Beat the closing line ${k.clv.beat} of ${k.clv.measured}</a>` : ''}<a class="pill good" href="#record">Every play graded →</a></div>
      <section class="section">${heroHtml}</section>
      ${recentHtml ? `<section class="section">${recentHtml}</section>` : ''}
      ${laterHtml ? section('Also on the card', laterHtml, '<a class="more" href="#record">Every result →</a>', 'Already posted. Prices can move before kickoff, so check your book.') : ''}
      ${awaiting.length ? section('Waiting on results', `<div class="tickets">${awaiting.map(p => ticket(p, { compact: true })).join('')}</div>`, '', 'Games are over or running late; grading follows the final.') : ''}
      ${gone.length ? `<details class="more-box"><summary>Pulled before kickoff · ${gone.length}</summary><div class="tickets" style="padding-top:6px">${gone.map(p => ticket(p, { compact: true })).join('')}</div></details>` : ''}
      ${communityCard()}
      ${fun.length ? section('Fun tickets', `<div class="tickets">${fun.map(p => ticket(p)).join('')}</div>`, '', 'For fun at a smaller stake. Tracked separately, never in the best-bet record.') : ''}
      ${section('Worth a look', worth, '<a class="more" href="#research">Full research board →</a>', 'Research, not best bets. Current prices that clear our value bar.')}
      ${section('Underdog watch', upsetHtml, '<a class="more" href="#games">All games →</a>', 'Outright upset research: our raw winner estimate against the market. Not a best bet.')}
      ${section('Today\'s games', tonightHtml, '<a class="more" href="#games/live">Live scores →</a>')}
      ${sportsHtml}`;
  };

  /* ---------- a single best bet ---------- */
  VIEWS.pick = async route => {
    const [today, board] = await Promise.all([get('app/today.json'), maybe('scoreboard.json')]);
    indexGames(today);
    let pick = (today.picks || []).find(p => p.id === route.id);
    if (!pick) pick = (await allPicks()).find(p => p.id === route.id);
    const back = '<a class="back" href="#today">← Today</a>';
    if (!pick) return head('', 'Play not found', 'This play is not in the current window. Every published play stays on the <a href="#record">record</a>.', back);
    const vm = pickVM(pick);
    const how = howWeGotIt(pick);
    const prose = v => v == null ? '' : typeof v === 'string' ? v : Array.isArray(v) ? v.map(prose).join(' · ') : typeof v === 'object' ? Object.entries(v).map(([k, x]) => `${k}: ${prose(x)}`).join(' · ') : String(v);
    const host = (u, i) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (_) { return `Source ${i + 1}`; } };
    const sources = (pick.sources || []).filter(x => /^https:\/\//.test(x));
    const clv = (((board || {}).picks || {}).rows || []).find(r => r.id === pick.id);
    const research = C.pickResearchRoute ? C.pickResearchRoute(pick) : null;
    const game = (today.games || []).find(g => g.id === pick.gameId);
    const notices = [
      pick.priceAssumed ? `<b>Price assumed.</b> ${esc(pick.priceNote || 'No price was recorded for this play, so it counts at an assumed −115.')}` : '',
      vm.estimated ? '<b>Estimated price.</b> Combined odds are estimated from the captured leg prices. Check the real ticket price at your book.' : '',
      clv && clv.clv != null ? `<b>Closing-line value: ${esc(clvWords(clv.clv))}.</b> We posted ${esc(clv.postedLine ?? '–')} at ${esc(oddsText(clv.postedOdds))} and the last number before kickoff was ${esc(clv.closeLine ?? '–')}${clv.closeOdds != null ? ` at ${esc(oddsText(clv.closeOdds))}` : ''}. ${clv.clv > 0 ? 'We got the better number, which is the part we control.' : clv.clv < 0 ? 'The market moved to a better number after we posted.' : ''}` : '',
      pick.earlyExit ? '<b>Early-exit credit.</b> A book promo refunded this loss. The headline record still counts it as −1u; credits are shown separately.' : '',
    ].filter(Boolean);
    const result = pick.result ? `<div class="card"><p><b>${esc(vm.status)}</b>${pick.actual ? ` · ${esc(prose(pick.actual))}` : ''}</p>${pick.settlementReason ? `<p class="small muted" style="margin-top:4px">${esc(prose(pick.settlementReason))}</p>` : ''}${pick.settledAt ? `<p class="small muted" style="margin-top:4px">Settled ${esc(when(pick.settledAt))}</p>` : ''}</div>` : '';
    const chanceTitle = vm.chance != null ? `How we got ${pctText(vm.chance)}` : 'How we got this';
    const projected = game && !C.isParlay(pick) && !pick.athleteId ? section('Our projected score now', `<p class="small muted" style="margin-bottom:8px">When posted: our number ${isNum(pick.projection) ? esc(C.fixed(pick.projection)) : '–'} against the ${esc(pick.line ?? '–')} line${vm.chance != null ? ` (${pctText(vm.chance)} our chance)` : ''}. The card below is today's model and market.</p>${projCard(game, { link: true, sideLabel: 'Current lean' })}`) : '';
    return `${back}${head(vm.market, vm.title, `${esc(when(vm.kickoff))}${pick.quotedAt ? ` · price quoted ${esc(ago(pick.quotedAt))}` : ''}`)}
      <div class="tickets">${ticket(pick, { onPage: true })}</div>
      ${result ? section('Result', result) : ''}
      ${notices.length ? `<div class="card on-felt" style="margin-top:14px;display:grid;gap:8px">${notices.map(n => `<p class="small">${n}</p>`).join('')}</div>` : ''}
      ${how.length ? section(chanceTitle, `<div class="card"><ul class="fa">${how.map(x => `<li class="for">${esc(x)}</li>`).join('')}</ul><p class="small muted" style="margin-top:6px">Saved when posted: our chance ${vm.chance != null ? `${(100 * vm.chance).toFixed(1)}%` : '–'} · price needs ${vm.needs != null ? `${(100 * vm.needs).toFixed(1)}%` : '–'} · difference ${vm.edge != null ? `${vm.edge > 0 ? '+' : ''}${vm.edge} pts` : '–'}.</p></div>`)
        : vm.kind === 'best' && isNum(pick.projection) ? section('Our number', `<div class="card"><p>We project ${esc(C.fixed(pick.projection))} against the ${esc(pick.line)} line. No calibrated chance was stored for this play.</p></div>`) : ''}
      ${projected}
      ${vm.legs.length ? section('Legs', `<div class="card"><ul class="fa">${vm.legs.map(l => `<li>${esc(l)}</li>`).join('')}</ul>${pick.correlation ? `<p class="small muted" style="margin-top:8px"><b>How the legs relate:</b> ${esc(prose(pick.correlation))}</p>` : ''}</div>`) : ''}
      ${pick.why || pick.risk ? section('The full read', `<div class="grid two"><div class="card"><p class="eyebrow green">Why</p><p style="margin-top:6px">${esc(prose(pick.why))}</p>${(pick.reasoning || {}).historyNote ? `<p class="small muted" style="margin-top:6px">${esc(pick.reasoning.historyNote)}</p>` : ''}</div><div class="card"><p class="eyebrow">What could go wrong</p><p style="margin-top:6px">${esc(prose(pick.risk))}</p></div></div>`) : ''}
      ${pick.cutoff ? section(vm.mode === 'open' ? 'Price we would still play' : vm.kind === 'best' ? 'Posted cutoff' : 'Entry rule', `<div class="card"><p>${esc(prose(pick.cutoff))}</p></div>`) : ''}
      <div class="btn-row">${research ? `<a class="btn" href="${esc(research)}">Player and matchup research</a>` : ''}${pick.gameId && game ? `<a class="btn" href="#game/${esc(pick.gameId)}">Game page</a>` : ''}<a class="btn" href="#record">Every result</a></div>
      ${sources.length ? `<p class="small muted" style="margin-top:14px">Sources: ${sources.map((x, i) => `<a href="${esc(x)}" target="_blank" rel="noopener noreferrer">${esc(host(x, i))} ↗</a>`).join(' · ')}</p>` : ''}
      <p class="small muted" style="margin-top:10px">${C.isParlay(pick) ? (C.isLadder(pick) ? 'A Climb step, tracked in dollars apart from the best-bet record.' : 'A fun ticket at a smaller stake, kept out of the best-bet record.') : pick.priceAssumed ? 'Graded at one unit at an assumed −115; no price was recorded when it was posted.' : 'Graded at one unit, at the line and price we posted.'} The posted price is kept for grading even after the line moves.</p>`;
  };

  /* ---------- Research (B: one pro board) ---------- */
  const boardRow = (vm, expandable = true) => {
    const price = vm.bestOdds != null && vm.bestOdds > Number(vm.odds) ? `${oddsText(vm.bestOdds)}` : oddsText(vm.odds);
    const book = vm.bestOdds != null && vm.bestOdds > Number(vm.odds) ? vm.bestBook : vm.book;
    const ageCls = vm.age.kind === 'fresh' ? '' : 'stale';
    const badge = vm.official ? `<span class="badge best">Best bet${vm.officialLine != null && Number(vm.officialLine) !== Number(vm.line) ? ` at ${esc(vm.officialLine)}` : ''}</span>`
      : vm.onCard ? `<span class="badge research" title="Posted at ${esc(oddsText(vm.onCard.odds))}${vm.onCard.line != null ? `, line ${esc(vm.onCard.line)}` : ''} and graded there">On the card${vm.onCard.line != null && Number(vm.onCard.line) !== Number(vm.line) ? ` at ${esc(vm.onCard.line)}` : ''}</span>` : '';
    const summary = `<div class="row-main">
      <div class="row-title with-art">${artFor(vm, 'sm')}<div><b>${esc(vm.title)}${badge}${vm.alternate ? '<span class="badge research">Alternate</span>' : ''}</b><span>${esc(vm.market)}${vm.position ? ` · ${esc(vm.position)}` : ''}${vm.matchup && !vm.isProp ? ` · ${esc(vm.matchup)}` : ''} · ${esc(vm.league === 'CFB' ? 'College' : vm.league)} · ${esc(whenShort(vm.kickoff))}</span>${vm.sub ? `<span>${esc(vm.sub)}</span>` : ''}</div></div>
      <div class="row-price"><b class="num">${esc(price)}</b><span class="${ageCls}">${esc(book || '')}${vm.booksCount > 1 ? ` · ${vm.booksCount} books` : ''}${vm.age.kind !== 'fresh' ? ` · ${esc(vm.age.label)}` : ''}${isNum(vm.opened) && vm.opened !== Number(vm.line) ? ` · opened ${esc(vm.opened)}` : ''}</span></div>
      <div class="row-meter on-felt">${meter(vm.chance, vm.needs, true)}<span>${pctText(vm.chance)} our chance · ${pctText(vm.needs)} needed</span></div>
      <div class="row-edge ${vm.edge > 0 ? '' : 'neg'}">${vm.edge != null ? `${vm.edge > 0 ? '+' : ''}${vm.edge}` : '–'}<small class="lbl"> edge</small></div>
      <div class="row-fair num"><small class="lbl">fair </small>${esc(oddsText(vm.fair))}</div></div>`;
    if (!expandable) return `<a href="#research?q=${encodeURIComponent(vm.player || vm.title)}" style="color:inherit;display:block;border-bottom:1px solid var(--line)">${summary}</a>`;
    const fa = [...(vm.extraFa || [])];
    if (vm.chance != null && vm.needs != null) fa.push([vm.chance > vm.needs ? 'for' : 'against', vm.chance > vm.needs ? `Our chance ${pctText(vm.chance)} beats the ${pctText(vm.needs)} this price needs.` : `Our chance ${pctText(vm.chance)} does not clear the ${pctText(vm.needs)} this price needs.`]);
    if (vm.otherLines.length) fa.push(['against', `Books disagree on the number: ${vm.otherLines.slice(0, 3).map(b => `${b.book} ${b.line}`).join(', ')}.`]);
    if (vm.thin) fa.push(['against', 'Few games so far. We trust this read less.']);
    if (vm.limited) fa.push(['against', 'Listed as questionable on the injury report.']);
    if (vm.caution) fa.push(['against', 'Recent results in this market raised the bar we use.']);
    if (vm.age.kind !== 'fresh') fa.push(['against', vm.age.label + '.']);
    return `<details data-row="${esc(vm.id)}" data-market="${vm.isProp ? 'prop' : /total/i.test(vm.market) ? 'total' : 'spread'}" data-proj="${esc(vm.projection ?? '')}" data-game="${esc(vm.gameId || '')}" data-athlete="${esc(vm.athleteId || '')}" data-stat="${esc(vm.stat || '')}" data-line="${esc(vm.line)}" data-dir="${esc(vm.direction || '')}">
      <summary>${summary}</summary>
      <div class="row-detail"><div data-chart><p class="small muted">Loading history…</p></div>
        <div><ul class="fa">${fa.map(([c, t]) => `<li class="${c}">${esc(t)}</li>`).join('')}</ul>
          ${vm.src && (vm.src.books || []).filter(b => bookLabel(b.book)).length > 1 ? `<p class="small" style="margin-top:8px"><b>Every book we captured:</b> ${(vm.src.books || []).filter(b => bookLabel(b.book) && isNum(Number(b.odds))).sort((a, b) => Number(b.odds) - Number(a.odds)).map(b => `${esc(bookLabel(b.book))} ${esc(oddsText(b.odds))}${Number(b.line) !== Number(vm.line) ? ` at ${esc(b.line)}` : ''}${/hard ?rock/i.test(b.book) ? ' (comparison only)' : ''}`).join(' · ')}</p>` : ''}
          <p class="small muted" style="margin-top:8px">${esc(vm.age.label)}.${vm.alternates ? ` ${vm.alternates} other line${vm.alternates === 1 ? '' : 's'} for this market hidden.` : ''}</p>
          <div class="btn-row" style="margin-top:10px">${vm.athleteId ? `<a class="btn small" href="#player/${esc(vm.league)}/${esc(vm.athleteId)}${vm.stat ? `?stat=${esc(vm.stat)}` : ''}">Player page</a>` : ''}${vm.gameId ? `<a class="btn small" href="#game/${esc(vm.gameId)}">Game page</a>` : ''}${vm.src ? ticketButton(vm.id, vm.title) : ''}${vm.src ? watchButton(P.snapshot({ ...vm.src, direction: vm.src.direction || vm.src.side || null })) : ''}</div></div></div>
    </details>`;
  };
  /* A link that reopens this exact view, in the old site's shareable format (the resolver maps it back). */
  const researchShare = (mode, route = {}) => {
    const base = { league: state.league, researchQuery: state.q };
    if (mode === 'trends' && C.researchHash) return C.researchHash(route.game ? `#trends/${encodeURIComponent(route.game)}` : '#trends', { ...base, trendStat: state.trends.stat, trendWindow: state.trends.window, trendDay: state.trends.day, trendRate: state.trends.rate, trendKind: state.trends.kind });
    if (mode === 'players' && C.researchHash) {
      const pg = state.players.game || 'next';
      return C.researchHash(state.players.sub === 'defense' ? '#stats/defense' : state.players.sub === 'teams' ? '#stats/teams' : '#stats', { ...base, researchQuery: state.players.q, chartStat: state.players.chartStat, chartPos: state.players.chartPos, chartWindow: state.players.chartWindow,
        chartDay: pg.startsWith('day:') ? pg.slice(4) : pg === 'all' ? 'all' : 'next' });
    }
    const q = new URLSearchParams();
    if (state.board.type !== 'all') q.set('type', state.board.type);
    if (state.board.sort !== 'edge') q.set('sort', state.board.sort);
    if (state.q) q.set('q', state.q);
    if (state.league !== 'ALL') q.set('sport', state.league);
    return `#research${mode === 'news' ? '/news' : ''}${String(q) ? '?' + q : ''}`;
  };
  const researchHead = async (mode, picks, board, route = {}) => {
    const k = kpiStrip(picks, board);
    const titles = { lines: `Every line, ${{ edge: 'sorted by edge', chance: 'most likely first', kickoff: 'by kickoff' }[state.board.sort] || 'sorted by edge'}`, trends: 'Hit-rate trends', players: 'Players and matchups', news: 'Injuries and news' };
    return `${head('Research', titles[mode] || titles.lines, 'Edge is how far our chance clears what the price needs. Research is not a best bet unless it is labeled <span class="badge best">Best bet</span>.')}
      ${k.html}<div class="toolbar" style="justify-content:space-between">${segLinks([['#research', 'Lines', 'lines'], ['#research/trends', 'Trends', 'trends'], ['#research/players', 'Players', 'players'], ['#research/news', 'News', 'news']], mode)}<a class="btn small" href="${esc(researchShare(mode, route))}" data-copy-link>Copy research link</a></div>`;
  };
  /* A link's filters apply once, when it is opened. After that the reader's own choices win, even on refresh. */
  let appliedHash = null;
  const NOT_YET = l => !FOOTBALL.includes(l) && l !== 'ALL';
  const notYet = () => empty(`${LEAGUE_NAME[state.league]} research is not available yet`, `Lines, trends and player research cover the NFL and college football. No football data is substituted. <a href="#games/live">Live scores</a> cover every sport, and new sports collect evidence in <a href="#record/trials">trials</a>.`, 'research');
  VIEWS.research = async route => {
    if (location.hash !== appliedHash) {
      appliedHash = location.hash;
      if (route.league) setLeague(route.league);
      if (route.type) state.board.type = route.type;
      if (route.sort && SORTS[route.sort]) state.board.sort = route.sort;
      if (route.q) { if (route.mode === 'players') { state.players.q = route.q; state.players.sub = 'search'; } else state.q = route.q; }
      if (route.sub && ['defense', 'teams', 'search', 'matchup'].includes(route.sub)) state.players.sub = route.sub;
      if (route.rate && ['70', '80', '90', '100'].includes(route.rate)) state.trends.rate = route.rate;
    }
    const [today, board, every] = await Promise.all([get('app/today.json'), maybe('scoreboard.json'), allPicks()]);
    indexGames(today);
    const picks = every.filter(inLeague);
    const top = await researchHead(route.mode, picks, board, route);
    if (NOT_YET(state.league)) return top + notYet();
    const filtering = state.q ? `<p class="small" style="margin:0 0 10px">Filtering for <b>${esc(state.q)}</b> · <button type="button" class="linkish" data-clear-q>Clear</button></p>` : '';
    if (route.mode === 'trends') return top + filtering + await researchTrends(route);
    if (route.mode === 'players') return top + await researchPlayers(route);
    if (route.mode === 'news') return top + await researchNews();
    const lines = await get('app/lines.json');
    const now = Date.now();
    const posted = new Map((today.picks || []).filter(p => !p.result && !p.historicalImport && !C.isParlay(p)).map(p => [officialKey(p), p]));
    const b = state.board;
    let rows = (lines.lines || []).map(r => lineVM(r, now)).filter(vm => onBoard(vm, now) && inLeague(vm));
    const gameIndex = new Map((today.games || []).map(g => [g.id, g]));
    rows.forEach(vm => { const pk = posted.get(vm.key); vm.official = Boolean(pk && C.isOpen(pk)); vm.officialLine = pk ? pk.line : null; vm.onCard = pk && !vm.official ? pk : null; const g = gameIndex.get(vm.gameId); vm.matchup = g ? `${g.away.abbr} at ${g.home.abbr}` : null; vm.teams = g ? [g.away.name, g.home.name, g.away.abbr, g.home.abbr] : []; });
    const total = rows.length;
    if (b.type === 'props') rows = rows.filter(vm => vm.isProp);
    if (b.type === 'games') rows = rows.filter(vm => !vm.isProp);
    if (b.fresh) rows = rows.filter(vm => vm.age.kind === 'fresh' || vm.age.kind === 'aging');
    if (b.value) rows = rows.filter(vm => hasValue(vm) || vm.official);
    if (state.q) rows = rows.filter(vm => C.researchMatches(state.q, vm.title, vm.player, vm.market, vm.league, vm.matchup, ...vm.teams));
    rows = collapse(rows).sort(SORTS[b.sort] || SORTS.edge);
    const shown = rows.slice(0, b.limit);
    /* By kickoff, rows sit under their game. */
    const grouped = b.sort === 'kickoff' ? shown.map((vm, i) => `${i === 0 || shown[i - 1].gameId !== vm.gameId ? `<div class="board-group">${vm.matchup ? `${esc(vm.matchup)} · ` : ''}${esc(whenShort(vm.kickoff))}</div>` : ''}${boardRow(vm)}`).join('') : shown.map(vm => boardRow(vm)).join('');
    /* Player lines the book has posted without a price we captured: research only, listed apart, never ranked. */
    const unpriced = b.value || b.type === 'games' ? [] : (lines.lines || []).filter(r => r.state === 'unpriced' && (r.athleteId || r.player) && isNum(Number(r.line)) && r.line !== null && Date.parse(r.kickoff) > now && inLeague(r)
      && (!state.q || C.researchMatches(state.q, r.title, r.player, r.market, r.league)));
    const list = shown.length ? `<div class="board"><div class="board-head"><span>Line</span><span>Best price</span><span>Our chance vs needed</span><span>Edge</span><span>Fair</span></div>${grouped}</div>
      ${rows.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-more-rows>Show ${Math.min(40, rows.length - shown.length)} more</button></p>` : ''}`
      : empty('No lines match', b.value ? 'Nothing fresh clears the value bar with these filters. Turn off "Value only" to see every priced line.' : 'Try another sport or clear the search.', 'research');
    return `${top}
      <div class="toolbar">${seg('type', [['all', 'All'], ['props', 'Player props'], ['games', 'Game lines']], b.type)}
        <div class="chips"><button type="button" class="chip" data-flag="fresh" aria-pressed="${b.fresh}">Fresh prices</button><button type="button" class="chip" data-flag="value" aria-pressed="${b.value}">Value only</button></div>
        <label class="sr" for="sort">Sort</label><select id="sort" class="select" data-select="sort"><option value="edge"${b.sort === 'edge' ? ' selected' : ''}>Sort: edge</option><option value="chance"${b.sort === 'chance' ? ' selected' : ''}>Sort: most likely</option><option value="kickoff"${b.sort === 'kickoff' ? ' selected' : ''}>Sort: kickoff</option></select>
        <div class="grow"><label class="sr" for="q">Search</label><input id="q" class="search" type="search" placeholder="Player, team or market" value="${esc(state.q)}" data-input="q" autocomplete="off"></div></div>
      <p class="small muted" style="margin-bottom:10px">${rows.length} of ${total} priced lines${b.value ? ' · value only' : ''}${b.fresh ? ' · fresh prices' : ''}. Tap a row for history and the case for and against.</p>
      ${list}
      ${unpriced.length ? `<details class="more-box" data-box="unpriced" style="margin-top:12px"><summary>Player lines with no price yet · ${unpriced.length}</summary><div class="receipts">${unpriced.slice(0, 60).map(r => `<div class="receipt" style="grid-template-columns:minmax(0,1fr) auto"><div><b>${r.athleteId ? `<a class="plain-link" href="#player/${esc(r.league)}/${esc(r.athleteId)}?stat=${esc(C.marketKey(r) || '')}">${esc(niceTitle(r.title))}</a>` : esc(niceTitle(r.title))}</b><span>${esc(marketLabel(r))} · ${esc(whenShort(r.kickoff))}${isNum((r.grade || {}).projection) ? ` · our middle estimate ${esc(C.fixed(r.grade.projection))}` : ''}</span></div><span class="small muted">No price yet</span></div>`).join('')}</div><p class="small muted" style="margin-top:8px">The book lists these lines, but we have not captured a price, so there is no chance, edge or fair price yet.</p></details>` : ''}`;
  };

  /* Bars against the line. Every game in the selection is drawn (the strip scrolls sideways on a phone), negative
     values hang below a zero rule, and "at least" milestones count a tie as a hit, the same way their trend counts. */
  const historyChart = (values, labels, line, direction, opts = {}) => {
    const nums = values.filter(isNum);
    if (!nums.length) return '<p class="small muted">No recorded games yet.</p>';
    const hasLine = isNum(line);
    const geo = C.chartGeometry(values, hasLine ? line : null);
    const atLeast = String(direction || '').toLowerCase() === 'at-least';
    const dir = String(direction || 'over').toLowerCase() === 'under' ? 'under' : 'over';
    const titles = opts.titles || [];
    let hit = 0, miss = 0, tie = 0;
    const cols = values.map((v, i) => {
      const res = hasLine ? C.thresholdResult(v, line, dir, atLeast) : 'unknown';
      if (res === 'hit') hit += 1; else if (res === 'miss') miss += 1; else if (res === 'push') tie += 1;
      const bar = geo.bars[i];
      const title = titles[i] ? ` title="${esc(titles[i])}"` : '';
      if (!bar) return `<div class="col"${title}><div class="bar unknown" style="top:${(geo.zero - 1.5).toFixed(1)}%;height:1.5%"></div></div>`;
      const neg = bar.value < 0;
      return `<div class="col"${title}><div class="bar ${res}${neg ? ' neg' : ''}" style="top:${bar.top.toFixed(1)}%;height:${Math.max(1.5, bar.height).toFixed(1)}%"><span>${esc(opts.format ? opts.format(v) : C.fixed(v, Number.isInteger(v) ? 0 : 1))}</span></div></div>`;
    }).join('');
    const zero = geo.low < 0 ? `<div class="zero" style="top:${geo.zero.toFixed(1)}%"></div>` : '';
    const lineEl = geo.line != null ? `<div class="line" style="top:${geo.line.toFixed(1)}%"><span>${esc(line)}</span></div>` : '';
    const word = atLeast ? `at least ${line}` : `${dir} ${line}`;
    const cap = hasLine ? `${hit} of ${hit + miss + tie} ${word}${tie ? ` · ${tie} tied` : ''}. History, not a probability.` : 'No line captured, so bars are not colored.';
    return `<div class="chart-wrap${geo.low < 0 ? ' has-neg' : ''}"><div class="chart" role="img" aria-label="${esc(cap)}">${zero}${lineEl}${cols}</div>
      <div class="chart-x">${labels.map(l => `<span>${esc(l)}</span>`).join('')}</div></div><p class="chart-cap">${esc(cap)}${hasLine ? ' Green cleared it, red missed, gray tied or not recorded.' : ''}</p>`;
  };
  /* A defense's rank for this player's position and stat, in words, with a tone word so color is never the only cue. */
  /* A defense that allows more is good news for the player, except for stats that hurt him. */
  const BAD_FOR_PLAYER = new Set(['int', 'sacks', 'fumLost']);
  const toneFor = (rank, of, stat) => { const t = C.rankTone(rank, of); return BAD_FOR_PLAYER.has(stat) ? (t === 'soft' ? 'tough' : t === 'tough' ? 'soft' : t) : t; };
  /* College ranks count FBS defenses only, the same set as the Defenses table. */
  const defenseRows = (teams, league) => { const rows = ((teams || {}).defense || {}).rows || {};
    return league === 'CFB' ? Object.fromEntries(Object.entries(rows).filter(([id]) => (((teams || {}).teams || {})[id] || {}).fbs)) : rows; };
  const defenseWords = (teams, oppId, pos, stat, league = null) => {
    const group = C.POS_GROUP[pos];
    const r = group && teams && teams.defense ? C.rankOf(defenseRows(teams, league), oppId, group, stat) : null;
    if (!r) return null;
    const tone = toneFor(r.rank, r.of, stat);
    const name = ((teams.teams || {})[oppId] || {}).abbr || 'Opponent';
    return { tone, text: `${name} allows ${C.fixed(r.value)} ${(STAT_WORD[stat] || C.LABEL[stat] || stat).toLowerCase()} a game to ${group}s · ${r.rank} of ${r.of}${league === 'CFB' ? ' FBS defenses' : ''} (1 allows the least)${tone === 'soft' ? ' · soft matchup' : tone === 'tough' ? ' · tough matchup' : ''}` };
  };
  /* The player's own stored games this season against a line, plus the opponent's defense. For a game already
     played, only games before it count, so the picture is what was known at kickoff. */
  const propHistory = async (league, athlete, stat, line, dir, gameId, before = null, projection = null) => {
    const [index, teams, today] = await Promise.all([get(`app/players/${league}.json`), maybe(`app/teams/${league}.json`), get('app/today.json')]);
    const shard = await get(`app/players/${league}/${C.shardOf(athlete, index.shards)}.json`);
    const data = (shard.players || {})[athlete];
    const g = (today.games || []).find(x => x.id === gameId);
    if (!data || !stat) return `<p class="small muted">No stored game history for this line yet. <a href="#player/${esc(league)}/${esc(athlete)}">Open the player page</a>.</p>`;
    const read = r => C.observedStat(r, shard.keys, stat);
    const season = (g && g.season) || index.season;
    const rows = C.playerHistory(data.rows, season, 'current', 'all', before);
    if (!rows.length) return `<p class="small muted">No games stored this season${before ? ' before this game' : ''}. <a href="#player/${esc(league)}/${esc(athlete)}">Open the player page</a> for earlier seasons.</p>`;
    const abbr = id => (((teams || {}).teams || {})[id] || {}).abbr || id;
    const last = rows.slice(-10);
    const side = String(dir).toLowerCase() === 'under' ? 'under' : 'over';
    const h10 = C.hits(last.map(read), line), hs = C.hits(rows.map(read), line);
    const teamId = String((index.players || []).find(p => String(p[0]) === String(athlete))?.[3] || '');
    const opp = g ? (String(g.home.id) === teamId ? g.away : g.home) : null;
    /* No hindsight: once the game has kicked off, today's defense table already includes it. */
    const dw = opp && !before && (!g || Date.parse(g.kickoff) > Date.now()) ? defenseWords(teams, opp.id, data.pos, stat, league) : null;
    const avg = list => { const v = list.map(read).filter(isNum); return { text: v.length ? C.fixed(v.reduce((a, b) => a + b, 0) / v.length) : '–', n: v.length }; };
    const a10 = avg(last), aS = avg(rows);
    return `<p class="eyebrow" style="margin-bottom:4px">This season vs ${esc(line)}${before ? ' · before this game' : ''}</p>
      ${historyChart(last.map(read), last.map(r => `${String(r[1]).slice(5)}\n${r[7] === 0 ? '@' : ''}${abbr(r[6])}`), line, side, { titles: last.map(r => `${r[1]} ${r[7] === 0 ? 'at' : 'vs'} ${abbr(r[6])}`) })}
      <p class="small" style="margin-top:6px"><b>${h10[side]} of ${h10.n}</b> last ${h10.n} · <b>${hs[side]} of ${hs.n}</b> this season${hs.n < 5 ? ' · small sample' : ''} · average ${esc(a10.text)} last ${a10.n}, ${esc(aS.text)} this season</p>
      ${isNum(projection) ? `<p class="small muted" style="margin-top:2px">Our middle estimate for this game: ${esc(C.fixed(projection))}. We shrink it before showing a chance.</p>` : ''}
      ${dw ? `<p class="small ${dw.tone === 'soft' ? 'green' : dw.tone === 'tough' ? 'red' : 'muted'}" style="margin-top:4px">${esc(dw.text)}</p>` : ''}
      <p class="small" style="margin-top:6px"><a href="#player/${esc(league)}/${esc(athlete)}?stat=${esc(stat)}">Full player page →</a></p>`;
  };
  const loadRowDetail = async el => {
    const box = el.querySelector('[data-chart]');
    if (!box || box.dataset.loaded) return;
    box.dataset.loaded = '1';
    const gameId = el.dataset.game, athlete = el.dataset.athlete, stat = el.dataset.stat, line = Number(el.dataset.line), dir = el.dataset.dir;
    const league = String(gameId).split('-')[0];
    try {
      if (athlete && FOOTBALL.includes(league)) { box.innerHTML = await propHistory(league, athlete, stat, line, dir, gameId, null, el.dataset.proj === '' ? null : Number(el.dataset.proj)); return; }
      const today = await get('app/today.json');
      const g = (today.games || []).find(x => x.id === gameId);
      if (!g) { box.innerHTML = '<p class="small muted">No model read stored for this game.</p>'; return; }
      const gap = (g.marketRead || {}).ourGap || {};
      const isTotal = el.dataset.market === 'total';
      const read = isTotal ? gap.total : gap.margin;
      box.innerHTML = `<div class="vs"><span class="h"></span><span class="h">Ours</span><span class="h">Market</span>
        <span class="k">Spread</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, (g.v2 || {}).margin))}</span><span class="num">${esc(favSpread(g.home.abbr, g.away.abbr, (g.market || {}).spread))}</span>
        <span class="k">Total</span><span class="num">${esc(C.fixed((g.v2 || {}).total))}</span><span class="num">${esc(C.fixed((g.market || {}).total))}</span></div>
        ${read && read.gapsThisLargeVsClose ? `<p class="chart-cap">In past-season backtests, gaps at least this large went ${esc(Number(read.gapsThisLargeVsClose[0]).toLocaleString('en-US'))}–${esc(Number(read.gapsThisLargeVsClose[1]).toLocaleString('en-US'))} against the closing line. Not a live record, and a gap is not a bet.</p>` : ''}`;
    } catch (e) { box.innerHTML = '<p class="small muted">History unavailable right now.</p>'; }
  };

  const TREND_STATS = [['all', 'All stats'], ['rec', 'Receptions'], ['recYds', 'Receiving yards'], ['rushYds', 'Rushing yards'], ['passYds', 'Passing yards'], ['car', 'Carries'], ['att', 'Pass attempts'], ['cmp', 'Completions']];
  const researchTrends = async route => {
    const data = await get('app/trends.json');
    const t = state.trends;
    let rows = C.trendWindow(C.bestTrendPrices((data.rows || []).map(r => r.team && !r.team.abbr && r.team.abbreviation ? { ...r, team: { ...r.team, abbr: r.team.abbreviation } } : r)), t.window);
    rows = C.filterTrends(rows, { min: 3, rate: t.rate, league: state.league, stat: t.stat || 'all', kind: t.kind, day: route.game ? 'all' : (t.day || 'all'), game: route.game || null, query: state.q });
    const heavyCount = rows.filter(r => heavyFavorite(r.odds)).length;
    if (!t.heavy) rows = rows.filter(r => !heavyFavorite(r.odds));
    const limit = t.limit || 40;
    const shown = rows.slice(0, limit);
    const windowLabel = t.window === 'last5' ? 'last 5 this season' : t.window === 'last10' ? 'last 10 this season' : 'this season';
    const list = shown.length ? `<div class="grid two">${shown.map(r => {
      const hist = r.history || [];
      const atLeast = r.kind === 'milestone' || r.direction === 'at-least';
      const dir = atLeast ? 'at-least' : r.direction === 'under' ? 'under' : 'over';
      const what = atLeast ? `${r.line}+ ${STAT_WORD[r.stat] || r.stat}` : `${r.direction === 'under' ? 'Under' : 'Over'} ${r.line} ${STAT_WORD[r.stat] || r.stat}`;
      const price = r.kind === 'milestone' ? '<span class="badge research">Stat milestone</span> <span class="small muted">No verified price</span>'
        : `<span class="badge research">${r.kind === 'alternate' ? 'Alternate' : 'Main line'}</span> <b>${esc(oddsText(r.odds))}</b> ${esc(bookLabel(r.book) || '')} <span class="small muted">· captured ${esc(ago(r.observedAt))} · verify in book</span>`;
      const playerHref = `#player/${esc(r.league)}/${esc(r.athleteId)}?stat=${esc(r.stat)}`;
      return `<div class="card"><div class="with-art" style="margin-bottom:4px">${headshot(r.league, r.athleteId, 'sm')}<p><a href="${playerHref}"><b>${esc(r.player || '')}</b></a> <span class="muted small">${esc(r.team?.abbr || r.team?.name || '')}</span>${heavyFavorite(r.odds) ? ' <span class="badge warn">Heavy favorite</span>' : ''}</p></div>
        <p style="font-weight:600">${esc(what)}</p>
        <p class="small" style="margin:2px 0">${price}</p>
        <p class="small muted">${esc(trendText(r))} · ${esc(windowLabel)}${r.games < 5 ? ' · small sample' : ''}${r.injuryStatus ? ` · Injury report: ${esc(r.injuryStatus)}` : ''}</p>
        ${historyChart(hist.map(h => Number(h.value)), hist.map(h => String(h.date || '').slice(5)), r.line, dir, { titles: hist.map(h => String(h.date || '')) })}
        <p class="small"><a href="#game/${esc(r.gameId)}">${esc(r.matchup || 'Game')} · ${esc(whenShort(r.kickoff))} →</a></p></div>`;
    }).join('')}</div>${rows.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-more-trends>Show ${Math.min(40, rows.length - shown.length)} more</button></p>` : ''}`
      : empty('No trends match', 'Try a lower hit rate, another history window or stat, or clear the search. Old and missing prices stay hidden.', 'research');
    return `<div class="toolbar">${seg('trendRate', [['70', '70%+'], ['80', '80%+'], ['90', '90%+'], ['100', '100%']], t.rate)}
        ${seg('trendWindow', [['season', 'Season'], ['last10', 'Last 10'], ['last5', 'Last 5']], t.window)}
        ${seg('trendKind', [['main', 'Main lines'], ['alternate', 'Alternates'], ['milestone', 'Milestones']], t.kind)}</div>
      <div class="toolbar"><label class="sr" for="tstat">Stat</label><select id="tstat" class="select" data-select="trendStat">${TREND_STATS.map(([k, l]) => `<option value="${k}"${(t.stat || 'all') === k ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
        ${route.game ? '' : seg('trendDay', [['all', 'All upcoming'], ['today', 'Today']], t.day || 'all')}
        <button type="button" class="chip" data-flag-trend="heavy" aria-pressed="${!t.heavy}">Hide heavy favorites${heavyCount ? ` (${heavyCount})` : ''}</button>
        <div class="grow"><label class="sr" for="tq">Search</label><input id="tq" class="search" type="search" placeholder="Player, team or market" value="${esc(state.q)}" data-input="q" autocomplete="off" maxlength="160"></div></div>
      <p class="small muted" style="margin-bottom:10px">${shown.length} of ${rows.length} trend${rows.length === 1 ? '' : 's'} · updated ${esc(ago(data.generatedAt))} · verify prices.${route.game ? ' <a href="#research/trends">Show all games →</a>' : ''} How often a player cleared a line in recorded regular-season games. History is not a probability, and a 4-of-4 run at −900 still needs 90% to break even.</p>${list}`;
  };

  /* Research · Players: the props.cash-style matchup charts (every player in a game, bars vs the line), search and
     defense-vs-position. Same data as the old Charts page (player-charts/<L>.json). */
  const CHART_STATS = [['recYds', 'Rec yds'], ['rec', 'Receptions'], ['targets', 'Targets'], ['rushYds', 'Rush yds'], ['car', 'Carries'],
    ['passYds', 'Pass yds'], ['cmp', 'Completions'], ['att', 'Pass att'], ['passTD', 'Pass TD'], ['rushTD', 'Rush TD'], ['recTD', 'Rec TD'], ['recLong', 'Long rec'], ['rushLong', 'Long rush'], ['kPts', 'Kick pts']];
  const chartHas = (pl, key) => Object.prototype.hasOwnProperty.call(pl.projection || {}, key) || Object.prototype.hasOwnProperty.call(pl.lines || {}, key)
    || (pl.rows || []).some(r => Object.prototype.hasOwnProperty.call(r.stats || {}, key));
  const matchupCharts = async league => {
    const data = await maybe(`app/player-charts/${league}.json`);
    if (!data) return empty('Matchup charts unavailable', 'The chart data did not load. Search players or open Defenses instead. <button type="button" class="btn small" data-retry>Try again</button>', 'research');
    const p = state.players;
    const games = (data.games || []).slice().sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    if (!games.length) return empty('No upcoming games', 'Matchup charts return when the next slate is posted.', 'research');
    const nextDay = games[0].day;
    const days = [...new Set(games.map(g => g.day))];
    /* A chosen game that has started (or a stale saved choice) falls back to the next slate, and says so. */
    let note = '';
    if (!['next', 'all'].includes(p.game) && !p.game.startsWith('day:') && !games.some(g => g.id === p.game)) { p.game = 'next'; note = 'That game has started, so this shows the next slate.'; }
    if (p.game.startsWith('day:') && !days.includes(p.game.slice(4))) { p.game = 'next'; note = 'That date has passed, so this shows the next slate.'; }
    const chosen = p.game === 'next' ? games.filter(g => g.day === nextDay) : p.game === 'all' ? games : p.game.startsWith('day:') ? games.filter(g => g.day === p.game.slice(4)) : games.filter(g => g.id === p.game);
    const pos = p.chartPos;
    const inPos = pl => pos === 'all' || pl.pos === pos || (pos === 'RB' && pl.pos === 'FB');
    const ids = new Set(chosen.map(g => g.id));
    const pool = (data.players || []).filter(pl => ids.has(pl.gameId) && inPos(pl));
    const stats = CHART_STATS.filter(([k]) => pool.some(pl => chartHas(pl, k)));
    const DEF_STAT = { QB: 'passYds', RB: 'rushYds', WR: 'recYds', TE: 'recYds', PK: 'kPts' };
    const natural = pos === 'all' || (C.POSITION_STATS[pos === 'PK' ? 'PK' : pos] || []).includes(p.chartStat);
    const key = natural && stats.some(([k]) => k === p.chartStat) ? p.chartStat : ((stats.find(([k]) => k === DEF_STAT[pos]) || stats[0] || [p.chartStat])[0]);
    const cards = g => ['away', 'home'].map(side => {
      const team = g[side];
      let list = (data.players || []).filter(pl => pl.gameId === g.id && pl.side === side && chartHas(pl, key) && inPos(pl));
      if (p.linesOnly) list = list.filter(pl => (pl.lines || {})[key] && isNum(pl.lines[key].line));
      list.sort((a, b) => ((b.projection || {})[key] ?? -1) - ((a.projection || {})[key] ?? -1));
      if (!list.length) return '';
      const t = { ...team, abbr: team.abbreviation };
      return `<div style="margin-top:10px"><div class="with-art" style="margin-bottom:8px">${teamMark(t, 'sm', league)}<b>${esc(team.name)}</b><span class="muted small">${list.length} player${list.length === 1 ? '' : 's'}</span></div>
        <div class="grid two">${list.map(pl => {
          const rows = C.chartHistory(pl.rows, key, { chartWindow: p.chartWindow });
          const values = rows.map(r => r.stats[key]);
          const cur = (pl.lines || {})[key];
          const line = cur && isNum(cur.line) ? cur.line : null;
          const dir = cur && cur.direction === 'under' ? 'under' : 'over';
          const status = C.quoteStatus(cur, g.kickoff);
          const proj = (pl.projection || {})[key];
          return `<a class="card" style="color:inherit;display:block" href="#player/${esc(league)}/${esc(pl.id)}?stat=${esc(key)}"><div class="with-art">${headshot(league, pl.id, 'sm', null, pl.pos)}<div><b>${esc(pl.name)}</b> <span class="muted small">${esc(pl.pos || '')}</span></div></div>
            <div class="kpis" style="grid-template-columns:repeat(3,minmax(0,1fr));margin:8px 0 4px"><div class="kpi" style="padding:8px"><small>${status.current ? 'Line' : 'Reference line'}</small><b class="num" style="font-size:22px">${line == null ? '–' : esc(C.statValue(line, key))}</b><span>${line == null ? 'none captured' : esc(dir)}</span></div>
              <div class="kpi" style="padding:8px"><small>Our average estimate</small><b class="num" style="font-size:22px">${esc(C.statValue(proj, key))}</b><span>${esc(C.LABEL[key] || key)}</span></div>
              <div class="kpi" style="padding:8px"><small>Hit rate</small><b class="num" style="font-size:22px">${line == null ? '–' : `${values.filter(v => C.thresholdResult(v, line, dir) === 'hit').length}/${values.length}`}</b><span>${values.length} games</span></div></div>
            <p class="tiny muted">${esc(status.label)}${cur && cur.book ? ` · ${esc(bookLabel(cur.book) || cur.book)}` : ''}${cur && isNum(cur.odds) ? ` ${esc(oddsText(cur.odds))}` : ''}${cur && cur.observedAt ? ` · ${esc(ago(cur.observedAt))}` : ''}</p>
            ${historyChart(values, rows.map(r => String(r.date).slice(5)), line, dir)}</a>`;
        }).join('')}</div></div>`;
    }).join('');
    const gameOptions = `<option value="next"${p.game === 'next' ? ' selected' : ''}>Next slate · ${esc(dayLabel(games[0].kickoff))}</option><option value="all"${p.game === 'all' ? ' selected' : ''}>All upcoming · ${games.length} games</option>${days.slice(1).map(d => { const g0 = games.find(g => g.day === d); return `<option value="day:${esc(d)}"${p.game === 'day:' + d ? ' selected' : ''}>${esc(dayLabel(g0.kickoff))}</option>`; }).join('')}${games.map(g => `<option value="${esc(g.id)}"${p.game === g.id ? ' selected' : ''}>${esc(g.away.abbreviation)} at ${esc(g.home.abbreviation)} · ${esc(whenShort(g.kickoff))}</option>`).join('')}`;
    return `<div class="toolbar"><label class="sr" for="cstat">Stat</label><select id="cstat" class="select" data-select="chartStat">${(stats.length ? stats : CHART_STATS).map(([k, l]) => `<option value="${k}"${k === key ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
        <label class="sr" for="cgame">Games</label><select id="cgame" class="select" data-select="chartGame">${gameOptions}</select>
        ${seg('cpos', [['all', 'All'], ['QB', 'QB'], ['RB', 'RB'], ['WR', 'WR'], ['TE', 'TE'], ['PK', 'K']], pos)}${seg('cwin', [['last5', 'Last 5'], ['last10', 'Last 10'], ['season', 'Season']], p.chartWindow)}
        <button type="button" class="chip" data-flag-players="linesOnly" aria-pressed="${p.linesOnly}">Only players with a line</button></div>
      ${note ? `<p class="small" style="margin-bottom:6px">${esc(note)}</p>` : ''}<p class="small muted" style="margin-bottom:6px">Every player in the matchup with their recent games against the captured line. Green cleared it, red missed. History is not a probability. Tap a player for the full log.</p>
      ${chosen.map(g => `<section class="section" style="margin:14px 0"><div class="section-head"><h2>${esc(g.away.abbreviation)} at ${esc(g.home.abbreviation)}</h2><a class="more" href="#game/${esc(g.id)}">Game page →</a></div><p class="section-note">${esc(when(g.kickoff))}</p>${cards(g) || '<p class="muted small">No players with this stat and filter.</p>'}</section>`).join('')}`;
  };

  const DEFENSE_STATS = { QB: ['passYds', 'passTD', 'att', 'cmp', 'int', 'sacks', 'rushYds'], RB: ['rushYds', 'car', 'rushTD', 'recYds', 'rec', 'targets'],
    WR: ['recYds', 'rec', 'targets', 'recTD'], TE: ['recYds', 'rec', 'targets', 'recTD'] };
  const researchPlayers = async route => {
    const league = state.league === 'CFB' ? 'CFB' : 'NFL';
    const p = state.players;
    const subTabs = seg('psub', [['matchup', 'By matchup'], ['search', 'Search'], ['defense', 'Defenses'], ['teams', 'Teams']], p.sub);
    const intro = `<p class="small muted" style="margin:10px 0">Showing ${league === 'CFB' ? 'college football' : 'NFL'}. Switch sport at the top.</p>`;
    if (p.sub === 'matchup') return `<div class="toolbar">${subTabs}</div>${intro}${await matchupCharts(league)}`;
    const [index, teams] = await Promise.all([get(`app/players/${league}.json`), maybe(`app/teams/${league}.json`)]);
    const teamOf = id => ((teams || {}).teams || {})[id] || {};
    if (p.sub === 'teams') {
      const list = Object.entries((teams || {}).teams || {}).filter(([, t]) => league === 'NFL' || t.fbs)
        .sort((a, b) => String(a[1].name || a[1].abbr).localeCompare(String(b[1].name || b[1].abbr)));
      return `<div class="toolbar">${subTabs}</div>${intro}${list.length ? `<div class="list-links cols">${list.map(([id, t]) => `<a href="#team/${league}/${esc(id)}"><span class="with-art">${teamMark({ ...t, id }, 'sm', league)}<b>${esc(t.name || t.abbr)}</b></span><small>${esc(t.abbr || '')} →</small></a>`).join('')}</div>` : empty('Teams unavailable', 'Try again later.', 'research')}`;
    }
    if (p.sub === 'defense') {
      if (!teams || !teams.defense) return `<div class="toolbar">${subTabs}</div>${empty('Defense table unavailable', 'Try again later.', 'research')}`;
      const stats = DEFENSE_STATS[p.pos] || DEFENSE_STATS.WR;
      const key = stats.includes(p.stat) ? p.stat : stats[0];
      const def = teams.defense;
      const prior = def.prior || {};
      const scope = p.scope === 'prior' && !prior.rows ? 'season' : p.scope;
      let rows = scope === 'last5' ? def.last5 || {} : scope === 'prior' ? prior.rows : def.rows || {};
      if (league === 'CFB') rows = Object.fromEntries(Object.entries(rows).filter(([team]) => teamOf(team).fbs));
      const ranked = C.rankDefenses(rows, p.pos, key, 1);
      const ordered = p.order === 'soft' ? ranked.slice().reverse() : ranked;
      const max = Math.max(1, ...ranked.map(r => r.value));
      const season = scope === 'prior' ? prior.season : def.season;
      return `<div class="toolbar">${subTabs}</div>${intro}
        <div class="toolbar">${seg('pos', [['QB', 'QB'], ['RB', 'RB'], ['WR', 'WR'], ['TE', 'TE']], p.pos)}
          <label class="sr" for="dstat">Stat</label><select id="dstat" class="select" data-select="defStat">${stats.map(k => `<option value="${k}"${k === key ? ' selected' : ''}>${esc(C.LABEL[k] || k)}</option>`).join('')}</select>
          ${seg('dscope', [['season', String(def.season || 'Season')], ['last5', 'Last 5'], ...(prior.rows ? [['prior', String(prior.season)]] : [])], scope)}
          ${seg('dorder', [['soft', 'Most allowed'], ['tough', 'Least allowed']], p.order)}</div>
        ${ranked.length ? `<div class="table-wrap"><table class="t"><caption class="sr">${esc(p.pos)} ${esc(C.LABEL[key] || key)} allowed per game</caption><thead><tr><th>Defense</th><th class="n">Rank</th><th class="n">Games</th><th class="n">Per game</th></tr></thead><tbody>
          ${ordered.map(r => { const t = teamOf(r.team); const tone = toneFor(r.rank, ranked.length, key); return `<tr><td><span class="with-art">${teamMark({ ...t, id: r.team }, 'sm', league)}<a href="#team/${esc(league)}/${esc(r.team)}">${esc(t.short || t.name || t.abbr || r.team)}</a></span></td>
            <td class="n"><span class="rank ${tone}">${esc(r.rank)}/${ranked.length}</span></td><td class="n muted">${esc(r.games ?? '–')}</td><td class="n"><span class="barcell">${esc(C.fixed(r.value))}<i style="width:${Math.round(60 * r.value / max)}px"></i></span></td></tr>`; }).join('')}</tbody></table></div>`
          : empty('No games yet', 'Rankings appear once teams have played.', 'research')}
        <p class="small muted" style="margin-top:8px">${esc(p.pos)} ${esc((C.LABEL[key] || key).toLowerCase())} allowed per game · ${esc(season || '')} regular season${scope === 'last5' ? ", each team's last 5" : ''}. Rank 1 allows the least. Position groups add up every player at the position${league === 'CFB' ? '; FBS teams only, and college targets come from play-by-play' : ''}. Small early-season samples swing hard.</p>`;
    }
    let body;
    if (p.q) {
      const hits = (index.players || []).filter(row => C.researchMatches(p.q, row[1], row[4], row[2], teamOf(row[3]).abbr, teamOf(row[3]).name))
        .sort((a, b) => String(b[5] || '').localeCompare(String(a[5] || '')) || (b[6] || 0) - (a[6] || 0)).slice(0, 30);
      body = hits.length ? `<div class="list-links">${hits.map(row => `<a href="#player/${league}/${esc(row[0])}"><span class="with-art">${headshot(league, row[0], 'sm', teamOf(row[3]))}<span><b>${esc(row[1])}</b> <span class="muted small">${esc(row[2])} · ${esc(row[4] || teamOf(row[3]).abbr || '')}</span></span></span><small>${esc(row[6] || 0)} games · last ${esc(row[5] || '–')} →</small></a>`).join('')}</div>`
        : empty('No players found', 'Check the spelling, try a team, or switch sport at the top.', 'research');
    } else {
      const leaders = index.leaders || {};
      body = `<div class="grid two">${[['recYds', 'Receiving yards'], ['rushYds', 'Rushing yards'], ['passYds', 'Passing yards'], ['rec', 'Receptions']].filter(([k]) => leaders[k]).map(([k, label]) =>
        `<div class="card"><p class="eyebrow" style="margin-bottom:6px">Season leaders · ${esc(label)}</p><table class="t"><tbody>${leaders[k].slice(0, 8).map((r, i) => `<tr><td class="n muted" style="width:28px">${i + 1}</td><td><span class="with-art">${headshot(league, r[0], 'sm')}<span><a href="#player/${league}/${esc(r[0])}?stat=${k}">${esc(r[1])}</a> <span class="muted small">${esc(r[2])}</span></span></span></td><td class="n">${esc(C.fixed(r[3], 0))}${r[4] != null ? `<br><span class="tiny muted">${esc(r[4])} g</span>` : ''}</td></tr>`).join('')}</tbody></table></div>`).join('')}</div>`;
    }
    return `<div class="toolbar">${subTabs}</div><div class="toolbar"><div class="grow"><label class="sr" for="pq">Find a player</label><input id="pq" class="search" type="search" placeholder="Find a ${league === 'CFB' ? 'college' : 'NFL'} player or team" value="${esc(p.q)}" data-input="pq" autocomplete="off" maxlength="160"></div></div>${intro}${body}`;
  };

  const researchNews = async () => {
    const [data, today] = await Promise.all([maybe('app/research.json'), get('app/today.json')]);
    if (!data) return empty('News unavailable', 'The injury feed did not load. <button type="button" class="btn small" data-retry>Try again</button>', 'research');
    const league = state.league === 'CFB' ? 'CFB' : 'NFL';
    const changes = (data.changes || []).filter(c => state.league === 'ALL' || c.league === state.league)
      .slice().sort((a, b) => String(b.observedAt).localeCompare(String(a.observedAt))).slice(0, 30);
    const inj = (data.injuries || {})[league] || {};
    const teams = Object.entries(inj.teams || {}).sort((a, b) => String(a[1].name).localeCompare(String(b[1].name)));
    const notes = (data.notes || []).filter(n => state.league === 'ALL' || n.league === state.league);
    const gameName = id => { const g = (today.games || []).find(x => x.id === id); return g ? `${g.away.abbr} at ${g.home.abbr}` : id; };
    const text = item => typeof item === 'string' ? item : item.text || item.summary || '';
    const chip = status => `<span class="badge ${/out|reserve|doubtful/i.test(status) ? 'warn' : 'research'}">${esc(status)}</span>`;
    return `${section('Status changes', changes.length ? `<div class="board">${changes.map(c => `<div class="row-main" style="grid-template-columns:minmax(0,2fr) minmax(0,1fr)"><div class="row-title"><b>${esc(c.name)}</b><span>${esc(c.league)}${(((data.injuries || {})[c.league] || {}).teams || {})[c.teamId] ? ` · ${esc(data.injuries[c.league].teams[c.teamId].name)}` : ''} · ${esc(ago(c.observedAt))}</span></div><div><span class="muted">${esc(c.from)}</span> → <b>${esc(c.to)}</b></div></div>`).join('')}</div>` : '<p class="muted">No recent changes.</p>', '', 'Newest first. Provider-listed injuries only. Not confirmed starters.')}
      ${league === 'CFB' ? section('College injuries', '<p class="muted small">College injury reports are limited in the feed. Verify with team reports before relying on a projection.</p>')
        : section('NFL injury report', teams.length ? `<div class="grid two">${teams.map(([, t]) => `<details class="more-box"><summary>${esc(t.name)} · ${t.players.length} listed</summary><div>${t.players.map(p => `<p class="small" style="padding:3px 0">${chip(p.status)} <b>${esc(p.name)}</b> ${esc(p.position || '')} · ${esc(p.injury || 'injury not listed')}${p.reportedAt ? ` · reported ${esc(ago(p.reportedAt))}` : ''}</p>`).join('')}</div></details>`).join('')}</div>` : empty('Nobody listed', 'No recent injury updates.', 'research'), '', inj.checkedAt ? `Updated ${esc(ago(inj.checkedAt))}. A missing listing is not proof of health.` : 'A missing listing is not proof of health.')}
      ${section('Analyst notes', notes.length ? notes.map(n => `<div class="card" style="margin-bottom:10px"><p class="eyebrow">${esc(LEAGUE_NAME[n.league] || n.league)} · ${esc(when(n.publishedAt))}</p>
          ${(n.takeaways || []).length ? `<ul class="fa" style="margin-top:6px">${n.takeaways.map(t => `<li class="for">${esc(text(t))}</li>`).join('')}</ul>` : ''}
          ${(n.weeklyReview || []).length ? `<p class="eyebrow" style="margin-top:10px">Review</p><ul class="fa">${n.weeklyReview.map(t => `<li>${esc(text(t))}</li>`).join('')}</ul>` : ''}
          ${(n.watch || []).length ? `<p class="eyebrow" style="margin-top:10px">Watching</p><ul class="fa">${n.watch.map(w => `<li><b>${esc(w.title)}</b>${w.gameId ? ` (<a href="#game/${esc(w.gameId)}">${esc(gameName(w.gameId))}</a>)` : ''}: ${esc(w.why || '')}${w.needs ? ` <span class="muted">Needs: ${esc(Array.isArray(w.needs) ? w.needs.join('; ') : w.needs)}</span>` : ''}</li>`).join('')}</ul>` : ''}</div>`).join('')
        : '<p class="muted small">No notes right now. Notes appear when the research run publishes them.</p>')}`;
  };

  /* ---------- Games ---------- */
  /* The projection card the owner loved on the old site, kept front and center: projected score, total, team strength
     ranks, the win-chance bar in team colors, then ours vs the market with our side (or "no lean"). */
  const barColor = t => {
    const c = /^#[0-9a-f]{6}$/i.test((t || {}).color || '') ? t.color : null;
    if (c && luminance(c) < 0.012 && /^#[0-9a-f]{6}$/i.test(t.alt || '') && luminance(t.alt) < 0.8) return t.alt;
    return c;
  };
  const projCard = (g, opts = {}) => {
    const v2 = g.v2 || {}, m = g.market || {}, raw = g.lean || {};
    const final = Boolean(g.completed), live = !final && g.state === 'in' && !g.statusWord;
    const hasScore = (final || live) && g.away.score != null && g.home.score != null;
    const label = final ? 'Final' : live ? 'Live' : 'Projected';
    const score = hasScore ? `${esc(g.away.score)}<i> – </i>${esc(g.home.score)}` : isNum(v2.away) ? `${C.fixed(v2.away, 1)}<i> – </i>${C.fixed(v2.home, 1)}` : '–';
    const sub = hasScore ? (isNum(v2.away) ? `We had ${C.fixed(v2.away, 0)}–${C.fixed(v2.home, 0)}` : '') : isNum(v2.total) ? `Total ${C.fixed(v2.total, 1)}` : 'No number yet';
    const team = t => `<div class="pc-team">${teamMark(t, opts.big ? 'lg' : 'md', g.league)}<b>${esc(t.name || t.abbr)}</b>${t.strength && opts.ranks !== false ? `<span title="Our model's offense and defense ranks${t.strength.teams ? ` out of ${esc(t.strength.teams)}` : ''}. #1 is best.">Off #${esc(t.strength.offense)} · Def #${esc(t.strength.defense)}</span>` : ''}</div>`;
    const home = isNum(v2.winProb) ? v2.winProb : null;
    let colors = [barColor(g.away), barColor(g.home)];
    if (colors.some(c => !c) || colors[0] === colors[1]) colors = ['#A9C0B3', '#20C774'];
    const ink = c => luminance(c) > 0.179 ? '#07120D' : '#FFFFFF';
    const bar = home == null || g.fcs || hasScore ? '' : `<div class="pc-bar" role="img" aria-label="Estimated win chance: ${esc(g.away.name)} ${100 - Math.round(100 * home)}%, ${esc(g.home.name)} ${Math.round(100 * home)}%"><span style="width:${(100 * (1 - home)).toFixed(1)}%;background:${esc(colors[0])};color:${ink(colors[0])}">${100 - Math.round(100 * home)}%</span><span style="width:${(100 * home).toFixed(1)}%;background:${esc(colors[1])};color:${ink(colors[1])}">${Math.round(100 * home)}%</span></div><div class="pc-bar-labels"><span>${esc(g.away.abbr)}</span><span>Estimated win chance</span><span>${esc(g.home.abbr)}</span></div>`;
    const lean = C.leanText(g) || {};
    const sideTeam = raw.side === 'home' ? g.home : g.away;
    const sideLine = m.spread == null ? '' : ` ${C.spreadText('', raw.side === 'home' ? m.spread : -m.spread).trim()}`;
    const ourSide = (text, chance, caution) => { const tone = chance == null ? '' : C.leanTone(chance, Boolean(v2.sparse));
      return !tone ? '<span class="muted">No lean</span>' : `<span class="lean ${tone}">${esc(text)} · ${pctText(chance)}${tone === 'lean-mild' ? ' · slight' : ''}${caution ? ' · higher bar' : ''}</span>`; };
    const lines = hasScore || g.fcs || !isNum(v2.margin) ? '' : `<div class="pc-lines"><span class="h"></span><span class="h">Ours</span><span class="h">Market</span><span class="h">${esc(opts.sideLabel || 'Our side')}</span>
      <span class="k">Spread</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, v2.margin))}</span><span class="num">${esc(favSpread(g.home.abbr, g.away.abbr, m.spread))}</span><span>${lean.side ? ourSide(`${sideTeam.abbr}${sideLine}`, lean.side.chance, raw.spreadCaution) : '<span class="muted">No lean</span>'}</span>
      <span class="k">Total</span><span class="num">${esc(C.fixed(v2.total, 1))}</span><span class="num">${esc(C.fixed(m.total, 1))}</span><span>${lean.total ? ourSide(`${lean.total.direction} ${m.total ?? ''}`, lean.total.chance, raw.totalCaution) : '<span class="muted">No lean</span>'}</span></div>`;
    const gap = gapScore(g);
    const note = g.fcs ? 'FBS vs FCS: our number is not reliable here.' : hasScore ? ''
      : [C.modelCaution(g), v2.sparse ? 'Thin history: a team has fewer than three games, so this leans on last season.' : ''].filter(Boolean).join(' ');
    const tag = opts.link === false ? 'div' : 'a';
    return `<${tag} class="proj${opts.big ? ' big' : ''}${live ? ' live' : ''}"${opts.link === false ? '' : ` href="#game/${esc(g.id)}"`}>
      <div class="pc-meta"><span>${live ? '<span class="live-dot"></span>' : ''}${esc(g.statusWord ? `${g.statusWord} · was ${whenShort(g.kickoff)}` : final ? `${/OT/.test(g.status || '') ? g.status : 'Final'} · ${whenShort(g.kickoff).split(',')[0]}` : live ? (g.status || 'Live') : whenShort(g.kickoff))} · ${esc(g.league === 'CFB' ? 'College' : g.league)}${g.neutral ? ' · neutral site' : ''}</span>${!hasScore && gap >= 80 ? `<span class="gap-chip big">Bigger gap than ${gap}% of games</span>` : ''}</div>
      <div class="pc-top">${team(g.away)}<div class="pc-mid"><small>${label}</small><b class="num">${score}</b><span>${esc(sub)}</span></div>${team(g.home)}</div>
      ${bar}${lines}${note ? `<p class="caution">${esc(note)}</p>` : ''}</${tag}>`;
  };
  const gameRow = g => projCard(g);

  VIEWS.games = async route => {
    const tab = route.tab || 'upcoming';
    if (route.league) setLeague(route.league);
    const tabs = segLinks([['#games', 'Upcoming', 'upcoming'], ['#games/live', 'Live & scores', 'live'], ['#games/final', 'Finals', 'final']], tab);
    const top = `${head('Games', tab === 'live' ? 'Live and scores' : tab === 'final' ? 'Recent finals' : 'Upcoming games', tab === 'upcoming' ? 'Our projected score for every game, with the win chance and how our number compares with the market.' : tab === 'live' ? 'Every sport we track. Scores refresh about every minute while this page is open.' : 'How our projected scores compared with the finals.')}${tabs}`;
    if (tab === 'live') return top + await gamesLive();
    const today = await get('app/today.json');
    if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${empty('Football only for projections', `${esc(LEAGUE_NAME[state.league])} has live scores here, not projections yet. Some sports also run a paper trial. No football data is substituted. <a href="#games/live">See live scores</a> or <a href="#record/trials">the trial record</a>.`, 'research')}`;
    const merged = withLive((today.games || []).filter(inLeague));
    let games = merged.games;
    const q = state.games.q.trim().toLowerCase();
    if (q) games = games.filter(g => [g.home.abbr, g.home.name, g.away.abbr, g.away.name].some(v => String(v || '').toLowerCase().includes(q)));
    const search = `<div class="grow"><label class="sr" for="gq">Find a team</label><input id="gq" class="search" type="search" placeholder="Find a team" value="${esc(state.games.q)}" data-input="gq" autocomplete="off" maxlength="80"></div>`;
    const note = '<p class="small muted" style="margin:0 0 10px">Off and Def are our model\'s team ranks; #1 is best. The bar is our estimated win chance.</p>';
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
    games = games.filter(g => !g.completed);
    const s = state.games.sort;
    const toolbar = `<div class="toolbar">${seg('gsort', [['kickoff', 'By day'], ['gap', 'Biggest gap']], s)}${search}</div>`;
    if (!games.length) return `${top}${toolbar}${empty(q ? 'No game matches' : 'No upcoming games', q ? 'Try a team name or abbreviation.' : 'Nothing in this league inside the current window.', 'games')}`;
    if (s === 'gap') {
      games.sort((a, b) => gapScore(b) - gapScore(a) || String(a.kickoff).localeCompare(String(b.kickoff)));
      const shown = state.games.all ? games : games.slice(0, 20);
      return `${top}${toolbar}<p class="small muted" style="margin-bottom:10px">Ranked by how unusual the gap between our number and the market is, against every stored game. A gap is a reason to look, not a bet.</p>${note}${liveStamp(merged.refreshed)}
        <div class="projs">${shown.map(g => projCard(g)).join('')}</div>
        ${games.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-all-games>Show all ${games.length} games</button></p>` : ''}`;
    }
    games.sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    return `${top}${toolbar}${note}${liveStamp(merged.refreshed)}${byDay(games)}`;
  };
  const LIVE_WORD = { in_progress: 'Live', final: 'Final', scheduled: 'Scheduled', postponed: 'Postponed', delayed: 'Delayed', suspended: 'Suspended', cancelled: 'Cancelled', canceled: 'Cancelled' };
  const gamesLive = async (opts = {}) => {
    const [sports, todayRaw] = await Promise.all([maybe('sports.json'), maybe('app/today.json')]);
    const today = todayRaw || {};
    const day = opts.day || (state.games.day && [etDay(-1), etDay(), etDay(1)].includes(state.games.day) ? state.games.day : etDay());
    const leagues = state.league === 'ALL' ? Object.keys(LIVE) : [state.league];
    const status = opts.day ? 'all' : state.games.status;
    const controls = `<div class="toolbar">${seg('gday', [[etDay(-1), 'Yesterday'], [etDay(), 'Today'], [etDay(1), 'Tomorrow']], day)}${seg('gstatus', [['all', 'All'], ['live', 'Live'], ['final', 'Final']], status)}</div>`;
    let failed = 0;
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
          ${g.status === 'scheduled' && g.pregameOdds && snap && L.freshness(snap) === 'fresh' && Date.parse(g.kickoff) > Date.now() ? `<details class="more-box" data-box="pregame:${esc(g.id)}" style="margin:-4px 0 8px"><summary>Pregame lines · ${esc(g.pregameOdds.book)}</summary><div class="pill-row">${g.pregameOdds.rows.map(r => `<span class="pill">${esc(['away', 'home'].includes(r.side) ? ((g.teams || {})[r.side] || {}).abbreviation || r.side : r.side === 'over' ? 'Over' : 'Under')} ${esc(r.market)} ${r.line != null ? esc(r.market === 'Spread' ? C.signed(r.line) : r.line) + ' ' : ''}<b>${esc(oddsText(r.price))}</b></span>`).join('')}</div><p class="small muted" style="margin-top:6px">ESPN-supplied pregame quotes · checked ${esc(ago(new Date(snap.at).toISOString()))}. Book update time unavailable. Confirm in your sportsbook; these are not in-play odds or picks.</p></details>` : ''}`;
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
    const games = rows[line.opponent]?.coverage?.[pos]?.[stat] ?? rows[line.opponent]?.g ?? 0;
    const tone = C.rankTone(rank.rank, rank.of);
    return { ...rank, games, pos, stat, tone, text: `${line.opponentAbbr || 'Opponent'} allows ${C.fixed(rank.value)} ${(STAT_WORD[stat] || C.LABEL[stat] || stat).toLowerCase()} a game to ${pos}s · ${rank.rank} of ${rank.of} (1 allows the least) · ${games} games`,
      supports: games >= 3 && ((dir === 'over' && tone === 'soft') || (dir === 'under' && tone === 'tough')),
      opposes: games >= 3 && ((dir === 'over' && tone === 'tough') || (dir === 'under' && tone === 'soft')) };
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

  VIEWS.game = async route => {
    const back = '<a class="back" href="#games">← Games</a>';
    let detail;
    try { detail = await get(`app/games/${route.id}.json`); } catch (e) {
      return head('', 'Game page not available', 'Game pages cover NFL and college football for games from about three days back to eight days ahead. <a href="#games/live">Live scores</a> cover every sport.', back);
    }
    const [today, teams] = await Promise.all([get('app/today.json'), maybe(`app/teams/${detail.league}.json`)]);
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
    const header = projCard({ ...g, v2: model, lean: detail.lean || fromSlate.lean, marketRead: detail.marketRead || fromSlate.marketRead }, { big: true, link: false });
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
      if (isNum(f.projection) && isNum(f.line) && f.market !== 'point spread') extraFa.push(['for', `Our middle estimate is ${C.fixed(f.projection)} against the ${f.line} line.`]);
      if (dm) extraFa.push([dm.supports ? 'for' : dm.opposes ? 'against' : 'ctx', dm.text + '.']);
      if (script) extraFa.push(['against', script]);
      const src = { ...f, id: f.sourceId || f.id, gameId: g.id, league: g.league, kickoff: g.kickoff };
      const vm = { id: f.sourceId || f.id, title: niceTitle(f.title), market: marketLabel(f), league: g.league, kickoff: g.kickoff, odds: f.odds, book: bookLabel(f.book), bestOdds: null, booksCount: 1,
        age: quoteAge(f.observedAt, g.kickoff, now, { odds: f.odds, state: 'open' }), chance: f.chance, needs: f.needs, edge: round1(f.edge), fair: fairAmerican(f.chance), otherLines: [], gameId: g.id,
        athleteId: f.athleteId, stat: f.stat || C.marketKey(f), line: f.line, direction: f.direction || f.side, player: f.player, isProp: f.kind === 'player', alternate: f.alternate,
        sub: [historyWords(f.history), dm ? `${dm.pos} matchup: ${dm.rank} of ${dm.of}${dm.tone === 'soft' ? ', soft' : dm.tone === 'tough' ? ', tough' : ''}` : ''].filter(Boolean).join(' · '), extraFa, src };
      return boardRow(vm);
    }).join('')}</div>` : `<p class="muted small">${pregame ? 'No fresh, priced line in this game clears our value bar right now. An empty list beats a forced one.' : 'Lines close at kickoff. Saved pregame lines are below.'}</p>`;

    /* Matchup edges and every other line the model read. */
    const reads = detail.modelReads || [];
    const favIds = new Set(fav.map(f => f.sourceId));
    const currentRead = r => r.odds != null && now - Date.parse(r.observedAt) >= 0 && now - Date.parse(r.observedAt) <= 4 * 3600000;
    const edges = pregame ? reads.map(r => {
      const hist = r.history && r.history.season, dm = defenseMatch(r, teams, g.league), script = scriptCaution(g, r, model);
      const trend = Boolean(hist && hist.games >= 3 && hist.rate >= 70), thin = (r.warnings || []).some(w => /small sample/i.test(w));
      return { r, hist, dm, script, trend, thin, signals: 1 + Number(trend) + Number(Boolean(dm && dm.supports)) };
    }).filter(x => x.r.kind === 'player' && currentRead(x.r) && !x.thin && !favIds.has(x.r.sourceId) && x.signals >= 2)
      .sort((a, b) => Number(Boolean(a.script)) - Number(Boolean(b.script)) || b.signals - a.signals || Number(Boolean(b.dm && b.dm.supports)) - Number(Boolean(a.dm && a.dm.supports)) || (b.hist?.rate || 0) - (a.hist?.rate || 0) || String(a.r.title).localeCompare(String(b.r.title))).slice(0, 4) : [];
    const edgeIds = new Set(edges.map(x => x.r.id));
    const edgesHtml = edges.length ? `<div class="grid two">${edges.map(({ r, hist, dm, script, trend, signals }) => `<div class="card">
        <div style="display:flex;justify-content:space-between;gap:8px"><span class="badge research" style="margin:0">${signals} of 3 signals</span><span class="num"><b>${esc(oddsText(r.odds))}</b> <span class="small muted">${esc(bookLabel(r.book) || '')}</span></span></div>
        <p style="margin-top:6px"><a href="#player/${esc(g.league)}/${esc(r.athleteId)}?stat=${esc(C.marketKey(r) || '')}"><b>${esc(niceTitle(r.title))} →</b></a></p>
        <p class="small">${esc(r.comparison || '')}</p>
        <div class="pill-row" style="margin:6px 0"><span class="pill">Model</span>${trend ? `<span class="pill">${esc(hist.rate)}% trend</span>` : ''}${dm && dm.supports ? '<span class="pill good">Matchup</span>' : dm && dm.opposes ? '<span class="pill bad">Defense disagrees</span>' : ''}${script ? '<span class="pill bad">Game-script caution</span>' : ''}</div>
        ${hist ? `<p class="small muted"><b>${esc(hist.hits)} of ${esc(hist.games)}</b> this season at this line</p>` : ''}${dm ? `<p class="small muted">${esc(dm.text)}</p>` : ''}${script ? `<p class="small red">${esc(script)}</p>` : ''}
        <p class="small muted">Checked ${esc(ago(r.observedAt))}</p></div>`).join('')}</div>` : '';
    const others = reads.filter(r => !favIds.has(r.sourceId) && !edgeIds.has(r.id));
    const readRow = r => {
      const hist = r.history && r.history.season;
      const script = r.kind === 'player' ? scriptCaution(g, r, model) : null;
      const price = !pregame ? 'Pregame comparison · not a live line' : currentRead(r) ? `${oddsText(r.odds)} ${bookLabel(r.book) || ''}` : 'No current price · check your book';
      return `<div class="receipt" style="grid-template-columns:minmax(0,1fr) auto"><div><b>${r.athleteId ? `<a href="#player/${esc(g.league)}/${esc(r.athleteId)}?stat=${esc(C.marketKey(r) || '')}">${esc(niceTitle(r.title))}</a>` : esc(niceTitle(r.title))}</b>
        <span>${esc(r.comparison || '')}</span><span>${hist ? `${esc(hist.hits)} of ${esc(hist.games)} this season at this line${hist.games < 5 ? ' · small sample' : ''} · ` : ''}${r.observedAt ? `checked ${esc(ago(r.observedAt))}` : ''}</span>
        ${script ? `<span class="red">${esc(script)}</span>` : ''}${(r.warnings || [])[0] ? `<span class="red">${esc(r.warnings[0])}</span>` : ''}</div><span class="small muted" style="text-align:right">${esc(price)}</span></div>`;
    };
    const othersHtml = others.length ? `<details class="more-box"><summary>Every line in this game · ${others.length}</summary><div class="receipts">${others.map(readRow).join('')}</div></details>` : '';

    /* Model vs market. */
    const range = model.range || (detail.forecast || {}).range;
    const fav2 = isNum(model.winProb) ? (model.winProb >= 0.5 ? `${g.home.abbr} ${pctText(model.winProb)}` : `${g.away.abbr} ${pctText(1 - model.winProb)}`) : '–';
    const mFav = isNum(m.homeML) && isNum(m.awayML) ? (m.homeML <= m.awayML ? `${g.home.abbr} ${oddsText(m.homeML)}` : `${g.away.abbr} ${oddsText(m.awayML)}`) : m.homeML != null ? `${g.home.abbr} ${oddsText(m.homeML)}` : '–';
    const gap = (detail.marketRead || fromSlate.marketRead || {}).ourGap || {};
    const caution = g.fcs ? 'FBS vs FCS: our number is not reliable here.' : [C.modelCaution({ ...g, v2: model }), model.sparse ? 'Thin history: one of these teams has fewer than three games this season, so this forecast leans on last season and the league average.' : ''].filter(Boolean).join(' ');
    const gapWords = r => r && r.gapsThisLargeVsClose ? `${Number(r.gapsThisLargeVsClose[0]).toLocaleString('en-US')}–${Number(r.gapsThisLargeVsClose[1]).toLocaleString('en-US')}` : null;
    const modelBlock = `<div class="card"><div class="vs" style="grid-template-columns:auto 1fr 1fr;font-size:15px"><span class="h"></span><span class="h">Our number</span><span class="h">${g.market ? `Market${bookLabel(m.book) ? ` (${esc(bookLabel(m.book))})` : ''}` : 'Market · none captured'}</span>
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
      <p class="small muted">${esc(trendText(t))}${t.games < 5 ? ' · small sample' : ''} · ${esc(oddsText(t.odds))} ${esc(bookLabel(t.book) || '')} · captured ${esc(ago(t.observedAt))}</p>${historyChart(t.history.map(h => Number(h.value)), t.history.map(h => String(h.date).slice(5)), t.line, t.direction === 'under' ? 'under' : 'over')}</div>`).join('')}</div>`,
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
          if (!Array.isArray(v)) return '<td class="n muted">–</td>';
          const market = (lines[p.id] || {})[C.PROJECTION_MARKET[k]];
          const gapV = market ? v[0] - market[0] : null;
          return `<td class="n" title="80% range ${esc(v[1])} to ${esc(v[2])}">${esc(C.fixed(v[0]))}<br>${market ? `<span class="tiny muted">line ${esc(market[0])} ${gapV > 0 ? '▲' : gapV < 0 ? '▼' : ''}${esc(C.signed(gapV))}</span>` : `<span class="tiny muted">${esc(C.fixed(v[1], 0))}–${esc(C.fixed(v[2], 0))}</span>`}</td>`;
        }).join('')}</tr>`).join('')}</tbody></table></div>`;
    };
    const projHtml = (detail.forecast || {}).players ? section('Player projections', `<div style="display:grid;gap:16px">${projTable('away')}${projTable('home')}</div>`, '', `Our middle estimate, with the 80% range underneath. ${detail.props && detail.props.capturedAt ? `Where a line was captured (${esc(ago(detail.props.capturedAt))}) it shows instead, with ▲ when we are above it and ▼ when below.` : 'No comparison lines captured yet.'}`)
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
      `<a class="more" href="#research/players?view=defense&sport=${esc(g.league)}">All defenses →</a>`, 'This season, regular season only. Rank 1 allows the least. Green marks a defense that gives up a lot (soft), red one that gives up little (tough).') : '';

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
    const injuryHtml = g.league === 'NFL' ? section('Injury report', `<div class="grid two">${injBlock('away')}${injBlock('home')}</div>`, '', 'Provider-listed injuries. Verify the latest availability before relying on a projection.')
      : section('Injuries', '<p class="small muted">College injury reports are not covered by the feed. Check team sources before relying on a projection.</p>');

    /* Touchdown watch: recent role snapshots only, before kickoff. */
    const tdw = pregame ? (detail.scorerResearch || []).filter(r => r.roleSnapshotAt && now - Date.parse(r.roleSnapshotAt) >= 0 && now - Date.parse(r.roleSnapshotAt) <= 7 * 86400000 && (r.games ?? 0) >= 3).slice(0, 5) : [];
    const tdAt = tdw.map(r => r.roleSnapshotAt).sort().pop();
    const tdHtml = tdw.length ? section('Touchdown watch', `<div class="board">${tdw.map(r => `<div class="row-main" style="grid-template-columns:minmax(0,2fr) minmax(0,1.2fr)"><div class="row-title with-art">${headshot(g.league, r.athleteId, 'sm')}<div>${r.athleteId ? `<a href="#player/${esc(g.league)}/${esc(r.athleteId)}"><b>${esc(r.player)}</b></a>` : `<b>${esc(r.player)}</b>`}<span>${esc(r.redZone)} red-zone carries + targets · ${esc(r.inside10)} inside the 10</span></div></div><div class="small muted">${esc(r.touchdowns)} TDs in ${esc(r.games)} games · ${esc(r.priceStatus || 'no verified TD price')}</div></div>`).join('')}</div>`, '', `Scoring opportunity, not a touchdown probability or a play. Role data as of ${esc(tdAt ? ago(tdAt) : '–')}. Verify the latest availability.`) : '';

    return `${back}${head(g.league === 'CFB' ? 'College football' : 'NFL', title, '')}${header}${actions}${liveStamp(liveNow.refreshed)}
      ${picks.length ? section('Our plays in this game', `<div class="tickets">${picks.map(p => ticket(p)).join('')}</div>`) : ''}
      ${finalHtml}
      ${pregame ? section('Lines we like', favHtml, '', 'Fresh, priced lines our calibrated board likes, ranked by edge. Research, not extra best bets.') : ''}
      ${edgesHtml ? section('Matchup edges', edgesHtml, '<span class="small muted">Research, not posted plays</span>', 'Our projection, this-season hit rate at the exact line, and the opponent defense in one view. College game-script cautions rank lower.') : ''}
      ${othersHtml ? `<section class="section">${othersHtml}</section>` : ''}
      ${final && detail.final ? '' : section('Model vs market', modelBlock)}
      ${upsetHtml}${trendsHtml}${depthHtml}${projHtml}${matchupHtml}
      ${section('Recent form', `<div class="grid two">${form('away')}${form('home')}</div>`)}
      ${injuryHtml}${tdHtml}`;
  };

  /* ---------- player page ---------- */
  const LOG_COLS = { QB: ['cmp', 'att', 'passYds', 'passTD', 'int', 'car', 'rushYds', 'rushTD'],
    RB: ['car', 'rushYds', 'anyTD', 'targets', 'rec', 'recYds', 'rzCar'], FB: ['car', 'rushYds', 'anyTD', 'targets', 'rec', 'recYds', 'rzCar'],
    WR: ['targets', 'rec', 'recYds', 'anyTD', 'recLong', 'rzTgt'], TE: ['targets', 'rec', 'recYds', 'anyTD', 'recLong', 'rzTgt'], PK: ['fgm', 'fga', 'xpm', 'kPts'] };
  const PROJ_KEY = { rec: 'receptions', car: 'carries' };
  VIEWS.player = async route => {
    const league = route.league;
    const back = `<a class="back" href="#research/players?sport=${esc(league)}">← Players</a>`;
    const index = await get(`app/players/${league}.json`);
    const entry = (index.players || []).find(p => String(p[0]) === String(route.id));
    if (!entry) return head('', 'Player not found', 'No stored games for this player in this league.', back);
    const [shard, teams, today, lines] = await Promise.all([get(`app/players/${league}/${C.shardOf(route.id, index.shards)}.json`), maybe(`app/teams/${league}.json`), get('app/today.json'), maybe('app/lines.json')]);
    const data = shard.players[route.id];
    const keys = shard.keys, rows = data.rows, pos = data.pos;
    const read = (row, stat) => C.observedStat(row, keys, stat);
    /* A new player starts fresh, unless the link carried a stat, season or sample. */
    const pkey = `${league}:${route.id}`;
    const carries = route.stat || route.season || route.sample;
    if (state.player.key !== pkey || (carries && state.player.hash !== location.hash)) {
      state.player.key = pkey;
      state.player.hash = location.hash;
      state.player.stat = route.stat || null;
      state.player.season = route.season || 'current';
      state.player.window = ['all', 'last5', 'last10', 'last20'].includes(route.sample) ? route.sample : 'all';
    }
    const options = [...new Set([...(C.POSITION_STATS[pos] || C.POSITION_STATS.WR), 'snapPct'])].filter(stat => rows.some(r => isNum(read(r, stat))));
    if (state.player.stat && C.LABEL[state.player.stat] && !options.includes(state.player.stat)) options.push(state.player.stat);
    const stat = options.includes(state.player.stat) ? state.player.stat : options[0] || (C.POSITION_STATS[pos] || C.POSITION_STATS.WR)[0];
    const team = ((teams || {}).teams || {})[entry[3]] || { name: entry[4] };
    const abbr = id => (((teams || {}).teams || {})[id] || {}).abbr || id;
    const now = Date.now();
    const next = (today.games || []).filter(g => g.league === league && !g.completed && Date.parse(g.kickoff) > now && [g.home.id, g.away.id].includes(String(entry[3])))
      .sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0];
    const side = next ? (String(next.home.id) === String(entry[3]) ? 'home' : 'away') : null;
    const nextDetail = next ? await maybe(`app/games/${next.id}.json`) : null;

    /* Season and sample: Last 5/10/20 always count inside the chosen season. */
    const currentSeason = (next && next.season) || index.season || ((teams || {}).defense || {}).season;
    const seasons = [...new Set(rows.filter(r => r[4] === 2).map(r => Number(r[2])))].sort((a, b) => b - a);
    if (!['current', 'all'].includes(state.player.season) && !seasons.includes(Number(state.player.season))) state.player.season = 'current';
    const scope = state.player.season, win = state.player.window;
    const scopeLabel = scope === 'all' ? 'All seasons' : `${scope === 'current' ? currentSeason : scope} season`;
    const recent = C.playerHistory(rows, currentSeason, scope, win);
    const thisSeason = C.playerHistory(rows, currentSeason);
    const values = recent.map(r => read(r, stat));

    /* The line: the board's priced quote first, else the captured reference line from the game feed. */
    const pricedRows = next && lines ? (lines.lines || []).filter(r => String(r.athleteId) === String(route.id) && r.gameId === next.id && C.marketKey(r) === stat) : [];
    const priced = pricedRows.map(r => lineVM(r, now)).filter(vm => onBoard(vm, now) && (vm.age.kind === 'fresh' || vm.age.kind === 'aging')).sort((a, b) => (b.edge ?? -99) - (a.edge ?? -99))[0] || null;
    const latest = pricedRows.slice().sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))[0];
    const captured = (((nextDetail || {}).props || {}).lines || {})[route.id];
    const refLine = captured && isNum((captured[stat] || [])[0]) ? captured[stat][0] : null;
    const quote = priced ? priced.src : latest || (refLine != null ? { line: refLine, state: 'reference', book: (((nextDetail || {}).props) || {}).provider || null, observedAt: (((nextDetail || {}).props) || {}).capturedAt || null } : null);
    const line = quote && isNum(Number(quote.line)) ? Number(quote.line) : null;
    const lineStatus = next ? C.quoteStatus(quote, next.kickoff) : null;
    const dir = String((quote || {}).direction || 'over').toLowerCase() === 'under' ? 'under' : 'over';
    const h = line != null ? C.hits(values, line) : null;

    const opp = next ? (side === 'home' ? next.away : next.home) : null;
    const group = C.POS_GROUP[pos];
    const allow = opp && group && teams ? C.rankOf(defenseRows(teams, league), opp.id, group, stat) : null;
    const tone = allow ? toneFor(allow.rank, allow.of, stat) : 'neutral';
    const vs = opp ? C.splits(recent, keys, stat, opp.id, (row, k, s2) => read(row, s2)).vs : null;
    const proj = side && nextDetail && nextDetail.forecast ? ((((nextDetail.forecast.players || {})[side] || {}).players || []).find(p => String(p.id) === String(route.id)) || null) : null;
    const projV = proj ? proj[PROJ_KEY[stat] || stat] : null;
    const summary = C.summarize(values);
    const split = C.splits(recent, keys, stat, null, (row, k, s2) => read(row, s2));
    const valueText = v => C.statValue(v, stat);
    const word = (C.LABEL[stat] || stat).toLowerCase();

    const nextCard = next ? `<div class="card" style="margin-bottom:16px"><p><b>Next: ${side === 'home' ? 'vs' : 'at'} ${esc(opp.name)}</b> · ${esc(when(next.kickoff))} · <a href="#game/${esc(next.id)}">Game page →</a></p>
      <div class="kpis" style="margin-top:10px">
        <div class="kpi"><small>Our middle estimate</small><b class="num">${Array.isArray(projV) ? esc(valueText(projV[0])) : '–'}</b><span>${Array.isArray(projV) ? `80%: ${esc(valueText(projV[1]))} to ${esc(valueText(projV[2]))}` : `none for ${esc(word)}`}</span></div>
        <div class="kpi"><small>${esc(lineStatus && lineStatus.current ? 'Line' : 'Reference line')}</small><b class="num">${line != null ? `${dir === 'under' ? 'Under' : 'Over'} ${esc(valueText(line))}` : '–'}</b><span>${line == null ? 'none captured' : h && h.n ? `${h[dir]} of ${h.n} ${dir} in this selection` : 'no recorded games in this selection'}</span></div>
        <div class="kpi"><small>${esc(opp.abbr || 'Opponent')} vs ${esc(group || pos || '')}s</small><b class="num ${tone === 'soft' ? 'green' : tone === 'tough' ? 'red' : ''}">${allow ? esc(valueText(allow.value)) : '–'}</b><span>${allow ? `${esc(word)} a game · ${allow.rank} of ${allow.of}${tone === 'soft' ? ' · soft matchup' : tone === 'tough' ? ' · tough matchup' : ''}` : 'not tracked by position'}</span></div>
        <div class="kpi"><small>Vs ${esc(opp.abbr || 'this opponent')}</small><b class="num">${vs && vs.summary ? esc(valueText(vs.summary.avg)) : '–'}</b><span>${vs && vs.summary ? `${vs.summary.n} meeting${vs.summary.n === 1 ? '' : 's'} in this selection` : 'no meetings in this selection'}</span></div></div>
      ${priced ? `<p class="small" style="margin-top:10px">${esc(priced.title)} · <b>${esc(oddsText(priced.odds))}</b> ${esc(priced.book || '')} · ${pctText(priced.chance)} our chance vs ${pctText(priced.needs)} needed · edge ${priced.edge > 0 ? '+' : ''}${esc(priced.edge ?? '–')}${priced.thin ? ' · thin sample' : ''}${!priced.calibrated ? ' · not calibrated' : ''}</p>${meter(priced.chance, priced.needs, true)}` : ''}
      ${lineStatus ? `<p class="small muted" style="margin-top:6px">${esc(lineStatus.label)}${quote && quote.book && bookLabel(quote.book) ? ` · ${esc(bookLabel(quote.book))}` : ''}${quote && quote.observedAt ? ` · ${esc(ago(quote.observedAt))}` : ''}${!priced && line != null && !/reference/i.test(lineStatus.label) ? ' · a reference line, not a price' : ''}</p>` : ''}</div>` : '';

    const seasonSelect = `<label class="sr" for="psea">Season</label><select id="psea" class="select" data-select="playerSeason"><option value="current"${scope === 'current' ? ' selected' : ''}>This season · ${esc(currentSeason ?? '')}</option>${seasons.filter(x => x !== Number(currentSeason)).map(x => `<option value="${x}"${String(x) === String(scope) ? ' selected' : ''}>${x}</option>`).join('')}<option value="all"${scope === 'all' ? ' selected' : ''}>All seasons</option></select>`;
    const showing = `${scopeLabel} · ${recent.length} game${recent.length === 1 ? '' : 's'}${win === 'all' ? '' : ` · last ${win.replace('last', '')}`} · ${C.LABEL[stat] || stat}`;
    const cols = [...(LOG_COLS[pos] || LOG_COLS.WR), ...(keys.includes('snapPct') && rows.some(r => C.observedCell(r, keys, 'snapPct') != null) ? ['snapPct'] : [])];
    const log = recent.slice().sort((a, b) => String(b[1]).localeCompare(String(a[1])));
    const where = r => r[7] === 0 ? '@' : r[7] === -1 ? 'vs (neutral)' : 'vs';
    const shareHref = `#player/${league}/${encodeURIComponent(route.id)}?stat=${encodeURIComponent(stat)}${scope !== 'current' ? `&season=${encodeURIComponent(scope)}` : ''}${win !== 'all' ? `&sample=${win}` : ''}`;

    return `${back}<div class="page-head" style="display:flex;gap:14px;align-items:center">${headshot(league, route.id, 'xl', team, pos || '')}<div><p class="eyebrow">${esc(pos || '')} · <a href="#team/${esc(league)}/${esc(entry[3])}">${esc(team.name || entry[4] || '')}</a> · ${thisSeason.length} game${thisSeason.length === 1 ? '' : 's'} this season</p><h1>${esc(data.name)}</h1></div></div>
      <div class="btn-row" style="margin-bottom:14px">${watchButton({ type: 'player', key: `player:${league}:${route.id}`, title: data.name, league, href: `#player/${league}/${route.id}` })}<a class="btn small" href="${esc(shareHref)}" data-copy-link>Link to this view</a></div>
      ${nextCard}
      <div class="toolbar"><div class="chip-scroll">${seg('pstat', options.map(k => [k, C.LABEL[k] || k]), stat)}</div></div>
      <div class="toolbar">${seasonSelect}${seg('pwin', [['all', 'All games'], ['last5', 'Last 5'], ['last10', 'Last 10'], ['last20', 'Last 20']], win)}</div>
      <p class="small muted" style="margin:-4px 0 10px">Showing ${esc(showing)}</p>
      ${recent.length ? `<div class="card">${historyChart(values, recent.map(r => `${new Set(recent.map(x => x[2])).size > 1 ? `'${String(r[1]).slice(2, 4)} ` : ''}${String(r[1]).slice(5)}\n${r[7] === 0 ? '@' : ''}${abbr(r[6])}`), line, dir, { titles: recent.map(r => `${r[1]} ${where(r)} ${abbr(r[6])}`), format: v => C.statValue(v, stat, Number.isInteger(v) ? 0 : 1) })}</div>`
        : `<div class="card">${empty('No games in this selection', 'No stored games this season yet. Earlier seasons are below.', 'research')}<p class="btn-row" style="margin-top:8px">${seasons.filter(x => x !== Number(currentSeason)).slice(0, 1).map(x => `<button type="button" class="btn small" data-set="pseason:${x}">Show ${x}</button>`).join('')}<button type="button" class="btn small" data-set="pseason:all">All seasons</button></p></div>`}
      <div class="kpis" style="margin-top:14px"><div class="kpi"><small>Average</small><b class="num">${esc(summary ? valueText(summary.avg) : '–')}</b><span>${esc(C.LABEL[stat] || stat)}</span></div><div class="kpi"><small>Median</small><b class="num">${esc(summary ? valueText(summary.median) : '–')}</b><span>selected games</span></div>
        <div class="kpi"><small>Hit count</small><b class="num">${h && h.n ? `${h[dir]}/${h.n}` : '–'}</b><span>${line == null ? 'no captured line' : `${dir} ${esc(valueText(line))}${h && h.push ? ` · ${h.push} tied` : ''}`}</span></div>
        <div class="kpi"><small>Games</small><b class="num">${recent.length}</b><span>${summary && summary.n < recent.length ? `${summary.n} with this stat recorded` : esc(scopeLabel)}</span></div></div>
      ${section('Splits', `<div class="kpis"><div class="kpi"><small>Home</small><b class="num">${esc(split.home ? valueText(split.home.avg) : '–')}</b><span>${split.home ? split.home.n : 0} game${split.home && split.home.n === 1 ? '' : 's'}</span></div><div class="kpi"><small>Away</small><b class="num">${esc(split.away ? valueText(split.away.avg) : '–')}</b><span>${split.away ? split.away.n : 0} game${split.away && split.away.n === 1 ? '' : 's'}</span></div>${split.neutral ? `<div class="kpi"><small>Neutral site</small><b class="num">${esc(valueText(split.neutral.avg))}</b><span>${split.neutral.n} game${split.neutral.n === 1 ? '' : 's'}</span></div>` : ''}</div>`)}
      ${section('Game log', log.length ? `<div class="table-wrap"><table class="t"><thead><tr><th>Game</th>${cols.map(k => `<th class="n">${esc(C.LABEL[k] || k)}</th>`).join('')}</tr></thead><tbody>${log.map(r =>
        `<tr><td><a href="#game/${esc(league)}-${esc(r[0])}">${esc(r[1])}</a><br><span class="tiny muted">${esc(where(r))} ${esc(abbr(r[6]))}${r[4] === 3 ? ' · postseason' : ''}</span></td>${cols.map(k => { const v = C.observedStat(r, keys, k); return `<td class="n">${v == null ? '<span class="muted">–</span>' : k === 'snapPct' ? Math.round(100 * v) + '%' : esc(v)}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>` : '<p class="muted small">No games in this selection.</p>', '', 'Regular season. A dash means not recorded, never zero.')}`;
  };

  /* ---------- team page ---------- */
  VIEWS.team = async route => {
    const league = route.league;
    const back = `<a class="back" href="#research/players?view=teams&sport=${esc(league)}">← Teams</a>`;
    const [teams, detail, today, index] = await Promise.all([maybe(`app/teams/${league}.json`), maybe(`app/teams/${league}/${route.id}.json`), get('app/today.json'), maybe(`app/players/${league}.json`)]);
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
        `<a class="more" href="#research/players?view=defense&sport=${esc(league)}">All defenses →</a>`, 'Per game this season. Rank 1 allows the least.') : ''}
      ${section('Players this season', roster.length ? `<div class="list-links cols">${roster.map(p => `<a href="#player/${esc(league)}/${esc(p[0])}"><span class="with-art">${headshot(league, p[0], 'sm', team)}<span><b>${esc(p[1])}</b> <span class="muted small">${esc(p[2] || '')}</span></span></span><small>${esc(p[6] || 0)} game${Number(p[6]) === 1 ? '' : 's'} stored →</small></a>`).join('')}</div>` : '<p class="muted small">Players appear after their first stat line.</p>')}`;
  };

  /* ---------- Record ---------- */
  const unitsChart = points => {
    if (points.length < 2) return '';
    const w = 600, h = 170, pad = 22, padL = 40;
    const vals = points.map(p => p.units);
    const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
    const span = hi - lo || 1;
    const x = i => padL + (w - padL - pad) * i / (points.length - 1);
    const y = v => pad + (h - 2 * pad) * (hi - v) / span;
    const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p.units).toFixed(1)}`).join(' ');
    const end = points[points.length - 1].units;
    return `<svg class="units-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Units over the season, ending at ${units(end)}"><line x1="${padL}" x2="${w - pad}" y1="${y(0).toFixed(1)}" y2="${y(0).toFixed(1)}" stroke="#3D7356" stroke-dasharray="4 4"/><path d="${path}" fill="none" stroke="${end < 0 ? '#FF6B75' : '#20C774'}" stroke-width="3" stroke-linejoin="round"/><circle cx="${x(points.length - 1).toFixed(1)}" cy="${y(end).toFixed(1)}" r="5" fill="${end < 0 ? '#FF6B75' : '#20C774'}"/><text x="${(x(points.length - 1) - 6).toFixed(1)}" y="${(y(end) - 10).toFixed(1)}" text-anchor="end" fill="#F2F7F4" font-size="14" font-family="DM Sans, sans-serif">${esc(units(end))}</text><text x="4" y="${(y(0) + 4).toFixed(1)}" fill="#A9C0B3" font-size="12" font-family="DM Sans, sans-serif">0u</text></svg>`;
  };
  const clvWords = clv => !isNum(clv) ? '' : clv > 0 ? `beat the close by ${C.fixed(clv, 1)}` : clv < 0 ? `lost ${C.fixed(Math.abs(clv), 1)} to the close` : 'matched the close';
  const receipt = (p, clvById) => {
    const vm = pickVM(p);
    const mark = p.result === 'win' ? ['hit', '✓', 'Hit'] : p.result === 'loss' ? ['miss', '✗', 'Miss'] : p.result === 'push' ? ['push', '–', 'Push'] : p.result === 'void' ? ['push', '–', 'Void'] : ['open', '•', vm.status || 'Open'];
    const u = C.unitsFor(p);
    const assumed = Boolean(p.priceAssumed || C.isUnpricedImport(p));
    const clv = clvById.get(p.id);
    const price = p.odds == null ? 'no price recorded' : assumed ? `${oddsText(p.odds)} assumed · no price recorded` : `${oddsText(p.odds)} ${/^espn ?bet$/i.test(String(p.book || '').trim()) ? 'ESPN BET' : bookLabel(p.book) || ''}`;
    const actual = p.actual != null ? String(typeof p.actual === 'object' ? Object.entries(p.actual).map(([k, v]) => `${k} ${v}`).join(', ') : p.actual).split(/[.;]\s/)[0] : '';
    const meta = [price, whenShort(p.kickoff || p.publishedAt), p.featured ? 'Pick of the Day' : '', clvWords(clv), actual ? `result ${actual}` : '', p.earlyExit ? 'early-exit credit (counts −1u in the headline)' : ''].filter(Boolean).join(' · ');
    const right = p.result ? (u == null ? '' : assumed ? `<span class="u muted" title="${esc(p.priceNote || 'No price was recorded, so this counts at an assumed −115.')}">(${esc(units(u))})</span>` : `<span class="u ${u > 0 ? 'green' : u < 0 ? 'red' : 'muted'}">${esc(units(u))}</span>`)
      : `<span class="u muted small">${esc(vm.status || 'Open')}</span>`;
    return `<div class="receipt"><span class="r-mark ${mark[0]}" aria-hidden="true">${mark[1]}</span><div><b><span class="sr">${esc(mark[2])}: </span><a href="#pick/${esc(encodeURIComponent(p.id))}" class="plain-link">${esc(niceTitle(p.displayTitle || p.title))}</a></b><span>${esc(meta)}</span></div>${right}</div>`;
  };
  /* The Climb in dollars: stake to payout, the bank after a win, and the running total. */
  const climbRow = p => {
    const info = p.ladder || {};
    const mark = p.result === 'win' ? ['hit', '✓', 'Hit'] : p.result === 'loss' ? ['miss', '✗', 'Miss'] : p.result ? ['push', '–', 'Push'] : ['open', '•', 'Open'];
    const money = n => `$${Math.round(Number(n) || 0).toLocaleString('en-US')}`;
    const net = (p.ladderTotal || {}).net;
    const paid = p.result === 'win' ? money(info.payout) : p.result === 'loss' ? '$0' : money(info.stake);
    const bankWin = p.result === 'win' ? (isNum(Number(info.bankedAfter)) && isNum(Number(info.banked)) && info.bankedAfter != null ? Number(info.bankedAfter) - Number(info.banked) : Number(info.bankThisWin) || C.ladderSplit(info.payout).bank) : null;
    const bank = bankWin != null ? ` · bank +${money(bankWin)}` : '';
    return `<div class="receipt"><span class="r-mark ${mark[0]}" aria-hidden="true">${mark[1]}</span><div><b><span class="sr">${esc(mark[2])}: </span><a class="plain-link" href="#pick/${esc(encodeURIComponent(p.id))}">Step ${esc(info.step || '?')}${info.run ? ` · climb #${esc(info.run)}` : ''}</a></b><span>${esc((p.legs || []).map(l => typeof l === 'string' ? l : l.title).filter(Boolean).map(niceTitle).join(' · ') || niceTitle(p.displayTitle || p.title || ''))}</span><span>${esc(oddsText(p.odds))} ${esc(bookLabel(p.book) || '')} · ${esc(whenShort(p.kickoff || p.publishedAt))}</span></div>
      <span class="u ${p.result === 'win' ? 'green' : p.result === 'loss' ? 'red' : 'muted'}">${esc(money(info.stake))} → ${esc(paid)}<br><span class="tiny muted">${esc(bank.replace(' · ', ''))}${isNum(net) ? `${bank ? ' · ' : ''}running ${net < 0 ? '−' : '+'}${money(Math.abs(net))}` : ''}</span></span></div>`;
  };
  const tableOf = (first, rows) => `<div class="table-wrap"><table class="t"><thead><tr><th>${esc(first)}</th><th class="n">W–L–P</th><th class="n">Units</th><th class="n">Pending</th></tr></thead><tbody>${rows.map(([name, t]) =>
    `<tr><td>${esc(name)}</td><td class="n">${t.wins}–${t.losses}–${t.pushes}</td><td class="n ${t.units < 0 ? 'red' : t.units > 0 ? 'green' : ''}">${esc(units(t.units))}</td><td class="n">${t.pending}</td></tr>`).join('')}</tbody></table></div>`;
  const weekLabel = w => { const d = new Date(w + 'T12:00:00'); const e = new Date(d); e.setDate(d.getDate() + 6);
    return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} to ${e.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`; };
  const MODEL_NAME = { 'v2.0': 'Our model', v1: 'First model', 'v1 replay': 'First model replay' };
  const rec3 = r => r ? `${r[0]}–${r[1]}${r[2] ? '–' + r[2] : ''}` : '–';
  const rate = r => r && r[0] + r[1] ? `${Math.round(100 * r[0] / (r[0] + r[1]))}%` : '–';

  /* One sport's research status: a paper trial, data collection or scores only. Shared by Today and Record › Trials. */
  const trialCard = (lg, lab, trials) => {
    const market = ((lab || {}).leagues || {})[lg], trial = ((trials || {}).leagues || {})[lg];
    if (!market && !trial && (!lab || !trials)) return `<div class="card"><p class="eyebrow">${esc(LEAGUE_NAME[lg] || lg)}</p><p class="small muted" style="margin-top:6px">Trial data is unavailable right now. <button type="button" class="btn small" data-retry>Try again</button></p></div>`;
    if (!market && !trial) return `<div class="card"><p class="eyebrow">${esc(LEAGUE_NAME[lg] || lg)} <span class="badge research">Scores only</span></p><p class="small" style="margin-top:6px">Schedules and scores are live. No model record or projections yet.</p><p class="small" style="margin-top:8px"><a href="#games/live?sport=${esc(lg)}">Live scores →</a></p></div>`;
    const count = (trial && trial.record) || {}, graded = (count.win || 0) + (count.loss || 0) + (count.push || 0);
    const status = trial ? 'Trial model' : 'Collecting data';
    const body = trial ? `<p style="margin-top:6px"><b class="num">${graded ? `${count.win}–${count.loss}${count.push ? '–' + count.push : ''}` : 'Pending'}</b> <span class="small muted">trial totals record · ${esc(trial.recorded || 0)} projections saved</span></p><p class="small muted">${graded ? `${graded} trial leans graded at their saved lines. Not official plays.` : 'No graded trial leans yet. The record starts with saved pregame projections, never backfilled results.'}</p>`
      : `<p style="margin-top:6px">${esc(market.gamesQuoted)} games with saved lines · ${esc(market.gamesGraded)} finals linked</p><p class="small muted">Collected games, not prediction wins. Building the history a model needs.</p>`;
    const upcoming = ((trial || {}).upcoming || []).filter(r => Date.parse(r.kickoff) > Date.now());
    const seasons = (trial || market || {}).seasons || [];
    return `<div class="card"><p class="eyebrow">${esc(LEAGUE_NAME[lg] || lg)} <span class="badge ${trial ? 'trial' : 'research'}">${esc(status)}</span></p>${body}
      ${upcoming.length ? `<div class="receipts" style="margin-top:8px">${upcoming.slice(0, 8).map(r => `<div class="receipt" style="grid-template-columns:minmax(0,1fr)"><div><b>${esc(r.away)} at ${esc(r.home)}</b><span>Projected total ${esc(r.projection)} · saved line ${esc(r.line)} · ${esc(whenShort(r.kickoff))} · captured ${esc(whenShort(r.capturedAt))}${r.sparse ? ' · thin history' : ''}</span></div></div>`).join('')}</div>` : ''}
      ${seasons.length ? `<details class="more-box" data-box="trial-history:${esc(lg)}" style="margin-top:8px"><summary>Season history</summary><div class="table-wrap"><table class="t"><tbody>${seasons.map(row => `<tr><td>${esc(row.season)} · ${row.phase === 'playoffs' ? 'Playoffs' : row.phase === 'regular' ? 'Regular season' : 'Stage not captured'}</td><td class="n">${trial ? `${esc(row.recorded)} saved` : `${esc(row.gamesQuoted || 0)} quoted in this stage`}</td><td class="n">${trial ? (() => { const r = row.record || {}; const n = (r.win || 0) + (r.loss || 0) + (r.push || 0); return n ? `${r.win || 0}–${r.loss || 0}${r.push ? '–' + r.push : ''}` : 'Pending'; })() : `${esc(row.gamesGraded || 0)} finals`}</td></tr>`).join('')}</tbody></table></div>${trial ? '' : '<p class="small muted" style="margin-top:6px">A game captured in more than one stage is counted in each.</p>'}</details>` : ''}
      <p class="small" style="margin-top:8px"><a href="#games/live?sport=${esc(lg)}">Live scores →</a></p></div>`;
  };
  VIEWS.record = async route => {
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
    const k = kpiStrip(all, board, rows, kLabel);
    const tabs = segLinks([['#record', 'Best bets', 'official'], ['#record/fun', 'Fun tickets', 'fun'], ['#record/climb', 'Climb', 'climb'], ['#record/model', 'Model vs market', 'model'], ['#record/trials', 'Trials', 'trials']], tab);
    const top = `${head('The record', 'Every play, graded in public', `Win or lose, at the price and book we posted. Nothing is deleted. Fun tickets and the Climb are tracked separately.${state.league !== 'ALL' ? ` Showing ${esc(LEAGUE_NAME[state.league])}; switch sport at the top.` : ''}`)}`;
    const clvById = new Map(((board || {}).picks || {}).rows?.map(r => [r.id, r.clv]) || []);
    const pickers = `<div class="toolbar"><label class="sr" for="rs">Season</label><select id="rs" class="select" data-select="season">${[['current', curSeasonLabel], ...archive.seasons.map(v => [String(v), String(v)]), ['all', 'All seasons']].map(([v, l]) => `<option value="${esc(v)}"${String(archive.selectedSeason) === v ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
      <label class="sr" for="rp">Stage</label><select id="rp" class="select" data-select="phase">${[['current', curPhaseLabel], ['regular', 'Regular season'], ['playoffs', 'Playoffs'], ['all', 'Full season']].map(([v, l]) => `<option value="${v}"${archive.selectedPhase === v ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select></div>
      <p class="small muted" style="margin:-4px 0 12px">Showing ${esc(seasonLabel)} · ${esc(phaseLabel)}. A new season or the first playoff play starts a fresh default view; older results stay in the archive.</p>`;
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
      const recNow = C.theRecord(rows);
      const open = straight.filter(p => !p.result && !p.historicalImport).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
      const imported = straight.filter(p => p.result && C.isUnpricedImport(p));
      const settled = straight.filter(p => p.result && !C.isUnpricedImport(p) && matches(p)).sort((a, b) => String(b.kickoff || b.settledAt).localeCompare(String(a.kickoff || a.settledAt)));
      const strip = [recNow.potd && recNow.potd.wins + recNow.potd.losses ? `Pick of the Day ${wl(recNow.potd)}` : '', recNow.lastDay ? `Last game day ${wl(recNow.lastDay)}` : '', `This week ${wl(recNow.week)}`].filter(Boolean).join(' · ');
      const counted = rows.filter(p => !C.isUnpricedImport(p));
      const st = counted.filter(p => !C.isParlay(p));
      const MARKET_NAME = { Totals: 'Game totals', Spreads: 'Spreads', Straights: 'Player props', 'Risky lines': 'Risky player lines' };
      const byWeek = [...new Set(st.map(p => C.weekOf(p.kickoff || p.publishedAt)).filter(Boolean))].sort().reverse().map(w => [weekLabel(w), C.summaryOf(st.filter(p => C.weekOf(p.kickoff || p.publishedAt) === w))]);
      const archiveGroups = new Map();
      for (const p of all) { if (!Number.isInteger(Number(p.season))) continue; const key = [p.league, p.season, C.recordPhaseOf(p)].join('|'); if (!archiveGroups.has(key)) archiveGroups.set(key, []); archiveGroups.get(key).push(p); }
      const compact = items => { const t = C.summaryOf(items); return items.length ? `${wl(t)}${t.pending ? ` · ${t.pending} pending` : ''}` : '—'; };
      const archiveRows = [...archiveGroups].sort((a, b) => b[0].localeCompare(a[0])).map(([key, items]) => { const [lg, season, phase] = key.split('|');
        return [`${lg} ${season} · ${phase === 'playoffs' ? 'Playoffs' : 'Regular season'}`, compact(items.filter(p => !C.isParlay(p) && !C.isUnpricedImport(p))), compact(items.filter(p => C.isParlay(p) && !C.isLadder(p) && !C.isUnpricedImport(p))), compact(items.filter(C.isLadder))]; });
      return `${top}${pickers}${k.html}${strip ? `<p class="small muted" style="margin:10px 0 0">${esc(strip)}</p>` : ''}${tabs}
        ${section('Units over the season', `<div class="card">${unitsChart(points) || '<p class="muted small">Not enough graded plays yet.</p>'}<p class="chart-cap">${esc(wl(rec.captured))} at captured prices · ${esc(units(rec.captured.units))}${rec.captured.roi != null ? ` · ROI ${rec.captured.roi > 0 ? '+' : ''}${rec.captured.roi.toFixed(1)}%` : ''}. ${rec.assumed.wins + rec.assumed.losses ? `${esc(wl(rec.assumed))} more from before prices were recorded, counted at an assumed −115 and kept out of the units line.` : ''}${rec.credits ? ` Promo credits of ${rec.credits}u are not counted as winnings.` : ''}</p></div>`)}
        ${open.length ? section('Waiting on results', `<div class="receipts">${open.map(p => receipt(p, clvById)).join('')}</div>`, '', 'Graded at the price we posted, even if the price has moved since.') : ''}
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
      return `${top}${pickers}${tabs}<div class="kpis"><div class="kpi"><small>Fun tickets</small><b class="num">${esc(wl(s))}</b><span>longshots at a smaller stake</span></div><div class="kpi"><small>Units</small><b class="num ${s.units < 0 ? 'red' : 'green'}">${esc(units(s.units))}</b><span>recorded ticket stakes · never in the best-bet record</span></div><div class="kpi"><small>Pending</small><b class="num">${s.pending}</b><span>not settled</span></div></div>
        ${open.length ? section('Waiting on results', `<div class="receipts">${open.map(p => receipt(p, clvById)).join('')}</div>`) : ''}
        ${section('Every fun ticket', `${search}${settled.length ? weeksOf(settled, p => receipt(p, clvById), 'fun') : '<p class="muted">No fun tickets match.</p>'}`)}`;
    }
    if (tab === 'climb') {
      if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${tabs}${empty(`No Climb for ${LEAGUE_NAME[state.league]}`, 'The 80/20 Climb uses NFL and college football legs. No football data is substituted here. Switch to All sports, NFL or College football to see it.', 'research')}`;
      const lad = C.theLadder(every);
      const acc = lad.accounting;
      const money = n => `$${Math.round(Number(n) || 0).toLocaleString('en-US')}`;
      return `${top}${tabs}<div class="kpis"><div class="kpi"><small>Current climb</small><b class="num">#${esc(lad.run)} · step ${esc(lad.step)}</b><span>${money(lad.banked + lad.stake)} of $1,000</span></div><div class="kpi"><small>Steps</small><b class="num">${esc(acc.wins)}–${esc(acc.losses)}</b><span>won–lost</span></div><div class="kpi"><small>Banked across wins</small><b class="num">${money(lad.saved)}</b><span>stays banked after a miss</span></div><div class="kpi"><small>Best climb</small><b class="num">${money(lad.best)}</b><span>highest bank + ride</span></div>
        <div class="kpi"><small>Wagered</small><b class="num">${money(acc.wagered)}</b><span>returned ${money(acc.returned)}</span></div><div class="kpi"><small>Net</small><b class="num ${acc.net < 0 ? 'red' : 'green'}">${acc.net < 0 ? '−' : '+'}${money(Math.abs(acc.net))}</b><span>lifetime, in dollars</span></div></div>
        <div class="card" style="margin-top:14px"><p>Bank 20% of every winning return and ride 80% on the next step. A miss ends the climb and starts a new $50 one; banked money stays banked. A new step is never guaranteed.</p>${lad.open ? `<p class="small" style="margin-top:6px">A step is open now. <a href="#today">See Today</a>.</p>` : '<p class="small muted" style="margin-top:6px">Next step: being checked · not posted yet.</p>'}</div>
        ${section('Past steps', `<div class="receipts">${lad.history.slice().reverse().map(climbRow).join('') || '<p class="muted">No settled steps yet.</p>'}</div>`, '', `The Climb keeps its own run history and spans NFL and college legs, so it is shown whole; changing the season view does not change an active run.${lad.climbs.length ? ` Climbs finished: ${lad.climbs.length}.` : ''}`)}`;
    }
    if (tab === 'model') {
      if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') return `${top}${tabs}${empty(`${LEAGUE_NAME[state.league]} is in research, not official picks yet`, 'No football data is substituted. <a href="#record/trials">See its trial →</a>', 'research')}`;
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
        <div class="kpis"><div class="kpi"><small>Spread vs close</small><b class="num">${esc(rate(card.spread))}</b><span>${esc(card.spread.join('–'))}</span></div><div class="kpi"><small>Totals vs close</small><b class="num">${esc(rate(card.total))}</b><span>${esc(card.total.join('–'))}</span></div><div class="kpi"><small>Player props vs line</small><b class="num">${esc(rate(card.props))}</b><span>${esc(card.props.join('–'))} · ${esc(card.propsNote)}</span></div><div class="kpi"><small>Picks beat the close</small><b class="num">${clv.measured ? `${clv.beat}/${clv.measured}` : '–'}</b><span>${clv.measured ? `${clv.tied} tied · ${clv.lost} lost` : ''}</span></div></div>
        <p class="small muted" style="margin-top:8px">${esc(card.games)} graded games · through ${esc(card.updatedThrough ? dayLabel(card.updatedThrough) : '–')} · final pregame forecast. Projected winners went ${esc(card.moneyline.join('–'))}; that's not a betting result, since there's no price and favorites usually win.</p>
        ${live.length ? section('Live record, by league', modelTable(live) + weeksTable(live), '', 'Published before kickoff. Miss = average points off the final. When the close misses by less, the market was the better forecast.') : ''}
        ${back.length ? `<details class="more-box" data-box="backtests"><summary>Backtests (never published) · ${back.length}</summary><div>${modelTable(back)}<p class="small muted" style="margin-top:6px">${esc(((board || {}).method || {}).backtest || 'Retrospective walk-forward. Never published, so it is evidence about the method, not a record.')}</p></div></details>` : ''}
        ${markets.length ? section('NFL player projections vs the DraftKings line', `<div class="table-wrap"><table class="t"><thead><tr><th>Market</th><th class="n">Graded</th><th class="n">Record</th><th class="n">Closer than line</th><th class="n">Our miss</th><th class="n">Line miss</th></tr></thead><tbody>${markets.map(r => `<tr><td>${esc(C.LABEL[r.market] || r.market)}</td><td class="n">${esc(r.graded)}</td><td class="n">${esc(rec3(r.record))}</td><td class="n">${rate(r.closerThanLine)}</td><td class="n">${esc(C.fixed(r.projectionMiss))}</td><td class="n">${esc(C.fixed(r.lineMiss))}</td></tr>`).join('')}</tbody></table></div>`, '',
          `Honest read: the line was the closer forecast in ${closer} of ${markets.length} markets. That is why we shrink our raw numbers before showing a chance.`) : ''}
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

  /* My ticket: legs are re-checked against the current board every time, so a gone or moved price is never priced. */
  const ticketRows = async () => {
    const data = await maybe('app/lines.json');
    if (!data) { const rows = state.ticket.map(item => ({ ...item, unchecked: true })); rows.unchecked = true; return rows; }
    const current = new Map(((data.lines) || []).map(l => [l.id, l]));
    const now = Date.now();
    return state.ticket.map(item => {
      const row = current.get(item.id);
      if (!row) return { ...item, state: 'closed', missing: true };
      const changed = Number(row.odds) !== Number(item.odds) || Number(row.line) !== Number(item.line) || bookLabel(row.book) !== bookLabel(item.book);
      const closed = !C.eligible(row, now);
      return { ...row, changed: changed && !closed, closed, started: Date.parse(row.kickoff) <= now, previous: item };
    });
  };
  const ticketSummary = rows => {
    if (rows.unchecked) return `<p class="small muted">Couldn't re-check prices right now, so no total is shown. <button type="button" class="btn small" data-retry>Try again</button></p>`;
    const live = rows.filter(r => !r.changed && !r.missing && !r.closed);
    const nChanged = rows.filter(r => r.changed).length, nGone = rows.filter(r => r.missing || r.closed).length;
    const sum = C.summarizeTicket(live, Number(state.stake.amount) || 0, state.stake.mode, Number(state.stake.unit) || 0);
    const heldText = `${nChanged ? `${nChanged} leg${nChanged === 1 ? ' has' : 's have'} a changed price: accept or remove ${nChanged === 1 ? 'it' : 'them'}. ` : ''}${nGone ? `${nGone} leg${nGone === 1 ? ' is' : 's are'} gone, closed or started: remove ${nGone === 1 ? 'it' : 'them'}. ` : ''}`;
    if (!sum.available) return `<p class="small muted">${esc(heldText + sum.reason)}</p>`;
    const money = n => '$' + Number(n).toFixed(2);
    const u = state.stake.mode === 'units';
    return `<div class="kpis"><div class="kpi"><small>Illustrative price</small><b class="num">${esc(oddsText(sum.odds))}</b><span>${sum.decimal.toFixed(2)} decimal</span></div>
      <div class="kpi"><small>Profit</small><b class="num">${u ? `${sum.profit.toFixed(2)}u` : money(sum.profit)}</b><span>${u && sum.dollars ? money(sum.dollars.profit) : 'on your stake'}</span></div>
      <div class="kpi"><small>Return</small><b class="num">${u ? `${sum.total.toFixed(2)}u` : money(sum.total)}</b><span>${u && sum.dollars ? `${money(sum.dollars.total)} · ` : ''}stake included</span></div></div>
      <p class="small muted" style="margin-top:8px">${esc(heldText + sum.reason)}</p>`;
  };
  const arbFor = a => [a.first, a.second].every(v => Math.abs(Number(v)) >= 100) ? C.arbSplit(a.first, a.second, a.bankroll) : { valid: false, reason: 'Enter American odds like −110 or +150 for both sides.' };
  const arbSummary = r => {
    if (!r.valid) return `<div class="card on-felt" style="margin-top:14px"><p class="eyebrow">Waiting for prices</p><h3 style="margin-top:4px">Enter both sides</h3><p class="small muted" style="margin-top:4px">${esc(r.reason)}</p></div>`;
    const money = n => `${n < 0 ? '−' : ''}$${Math.abs(n).toFixed(2)}`;
    return `<div style="margin-top:14px"><p class="eyebrow ${r.arb ? 'green' : ''}">${r.arb ? 'Positive split' : 'No locked return'}</p><h3 style="margin-top:4px">${r.arb ? 'The math shows an arb' : 'These prices are not an arb'}</h3>
      <div class="kpis" style="margin-top:10px"><div class="kpi"><small>Side A stake</small><b class="num">${money(r.firstStake)}</b></div><div class="kpi"><small>Side B stake</small><b class="num">${money(r.secondStake)}</b></div><div class="kpi"><small>Lowest return</small><b class="num">${money(r.return)}</b></div><div class="kpi"><small>${r.arb ? 'Difference' : 'Shortfall'}</small><b class="num ${r.arb ? 'green' : 'red'}">${money(r.profit)}</b><span>${r.roi > 0 ? '+' : ''}${Number(r.roi).toFixed(2)}%</span></div></div>
      <p class="small" style="margin-top:8px">${r.arb ? `${money(r.profit)} remains if either side wins and both bets are accepted and settled as expected.` : `The implied chances total ${Number(r.implied).toFixed(2)}%. They must be below 100% for a locked return.`}</p></div>`;
  };

  /* ---------- More ---------- */
  VIEWS.more = async () => `${head('More', 'Tools and help', '')}
    <div class="list-links">
      <a href="#start"><span><b>Start here</b><br><span class="small muted">How to read a best bet in 30 seconds, plus the glossary</span></span><small>→</small></a>
      <a href="#saved"><span><b>Saved</b></span><small>${state.watchlist.length} saved →</small></a>
      <a href="#ticket"><span><b>My ticket</b><br><span class="small muted">A personal draft, never a pick</span></span><small>${state.ticket.length} legs →</small></a>
      <a href="#arbs"><span><b>Arb calculator</b><br><span class="small muted">Exact two-book stake math</span></span><small>→</small></a>
      <a href="#research/news"><span><b>Injuries and news</b><br><span class="small muted">Status changes, the injury report and analyst notes</span></span><small>→</small></a>
      <a href="#games/live"><span><b>All sports scores</b><br><span class="small muted">Football, basketball, baseball, hockey and soccer</span></span><small>→</small></a>
      <a href="#schedule"><span><b>Release schedule</b><br><span class="small muted">When best bets, research and results post</span></span><small>→</small></a>
      <a href="#record/trials"><span><b>Lab and trials</b><br><span class="small muted">New sports collecting evidence</span></span><small>→</small></a>
      <a href="#status"><span><b>Data status</b></span><small>→</small></a>
      <a href="https://discord.gg/CvNTUUSnNz" target="_blank" rel="noopener"><span><b>Free Kook'n Discord</b><br><span class="small muted">Best bets land here about 10–15 minutes before X</span></span><small>↗</small></a>
      <a href="https://x.com/keenkooks" target="_blank" rel="noopener"><span><b>Follow on X</b></span><small>@keenkooks ↗</small></a>
      <a href="#feedback"><span><b>Feedback</b></span><small>→</small></a>
      <a href="#responsible"><span><b>Responsible gaming</b></span><small>→</small></a>
    </div>`;
  VIEWS.glossary = async () => VIEWS.start();
  VIEWS.start = async () => `<a class="back" href="#more">← More</a>${head('Start here', 'How to read a best bet', 'Thirty seconds, then you know everything on the page.')}
    <div class="tickets"><article class="ticket"><div class="ticket-body"><div class="ticket-top"><span class="tag">Best bet</span><span>Example</span></div><div class="ticket-rule"></div><h3>Player over 49.5 receiving yards</h3><p class="market">Player prop · receiving yards</p><div class="price"><b>−110</b><span>DraftKings</span></div>
      <p class="plain">We think this hits <strong>56%</strong> of the time. At −110 you only need 52%.</p>${meter(0.56, 0.524)}<div class="meter-labels"><span>0%</span><span>needs 52%</span><span>100%</span></div></div><div class="stub open"><b>56%</b><small>our chance</small></div></article>
      <div class="card"><ol style="margin:0;padding-left:18px;display:grid;gap:8px"><li><b>The price and book.</b> −110 at DraftKings is what we saw when we posted. Check your own book; prices move.</li><li><b>Our chance vs what the price needs.</b> The green bar is our chance. The black tick is the break-even point for that price. Green past the tick means value.</li><li><b>Edge and fair price.</b> Edge is the gap in percentage points. Fair price is what the odds would be if our chance were exactly right.</li><li><b>Graded in public.</b> A green ticket hit, a red ticket missed, gray pushed. Every result stays on the Record.</li></ol></div></div>
    ${section('Two ways to use Kook\'n', `<div class="grid two"><div class="card"><p class="eyebrow green">The quick route</p><h3 style="margin-top:4px">Our best bets</h3><p class="small" style="margin-top:4px">Open Today for the posted best bets and the Climb. Tap a ticket for how we got the number.</p><p style="margin-top:8px"><a class="btn small" href="#today">See Today →</a></p></div>
      <div class="card"><p class="eyebrow green">Do your own research</p><h3 style="margin-top:4px">The research board</h3><p class="small" style="margin-top:4px">Every line sorted by edge, hit-rate trends, matchup charts and defenses. Save players or lines to compare later.</p><p style="margin-top:8px"><a class="btn small" href="#research">Open Research →</a></p></div></div>`)}
    ${section('Inside the free Discord', `<div class="card"><p><b>Plays & Results:</b> best bets and settled results. Best bets usually land here 10–15 minutes before X.</p><p style="margin-top:6px"><b>General chat:</b> games, questions and feedback. <b>Wins & Bad Beats:</b> your tickets and stories.</p><p class="small muted" style="margin-top:6px">Research is not a best bet. A historical hit rate is not a promise. Check the exact line and price yourself.</p><p style="margin-top:10px"><a class="btn primary small" href="https://discord.gg/CvNTUUSnNz" target="_blank" rel="noopener">Join the Discord ↗</a></p></div>`)}
    ${section('Glossary', `<dl class="glossary card">
      <dt>Best bet</dt><dd>An official Kook'n play. It counts in the public record at one unit, at the price and book we posted.</dd>
      <dt>Pick of the Day</dt><dd>The one best bet we feature each day. Its record is shown on the Record page.</dd>
      <dt>Research</dt><dd>Lines we track and grade but did not post. Useful context, not picks.</dd>
      <dt>Unit (u)</dt><dd>One standard stake. +1.00u means you won one stake; −1.00u means you lost one.</dd>
      <dt>Break-even</dt><dd>How often a bet must win to not lose money at that price. −110 needs 52.4%.</dd>
      <dt>Edge</dt><dd>Our chance minus the break-even chance, in percentage points.</dd>
      <dt>Fair price</dt><dd>The odds that match our chance exactly. If the book pays better than fair, that is value.</dd>
      <dt>Closing line</dt><dd>The final number before kickoff. Beating it more often than not is the best early sign of real skill.</dd>
      <dt>Posted price may be gone</dt><dd>The price we posted is older than our freshness limit. The play still counts at the posted price; check your book for today's.</dd>
      <dt>Fun ticket</dt><dd>A longshot parlay at a smaller stake, tracked separately from the record.</dd>
      <dt>The 80/20 Climb</dt><dd>A $50 to $1,000 challenge. A step posts only when two independent legs qualify. A winning return is split 20% banked and 80% carried to the next step. A losing step loses only its active stake; money already banked stays banked, and a new $50 climb starts. A new step is never guaranteed.</dd>
      <dt>Trial</dt><dd>A new sport collecting evidence on paper. Never a best bet until it earns a release and the owner approves it.</dd></dl>`)}
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
  VIEWS.saved = async () => {
    const [lines, every, todayS] = await Promise.all([maybe('app/lines.json'), allPicks(), maybe('app/today.json')]);
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
  VIEWS.ticket = async () => {
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
      : empty('Your ticket is empty', 'Add priced lines from the <a href="#research">research board</a> with + Ticket.', 'check')}`;
  };
  VIEWS.arbs = async () => {
    const a = state.arb;
    return `<a class="back" href="#more">← More</a>${head('Arb calculator', 'Two books, every outcome covered', 'Exact stake math, with the catches left in. Time-sensitive arb candidates go to the free Discord, never to this page. An arb candidate is never a best bet and never enters the record.')}
      <div class="card"><div class="arb-form"><label>Side A American odds<input class="search" type="text" inputmode="text" pattern="[-+]?[0-9]*" autocomplete="off" value="${esc(a.first)}" data-arb="first"></label><label>Side B American odds<input class="search" type="text" inputmode="text" pattern="[-+]?[0-9]*" autocomplete="off" value="${esc(a.second)}" data-arb="second"></label><label>Total bankroll ($)<input class="search" type="number" min="0.01" step="0.01" inputmode="decimal" value="${esc(a.bankroll)}" data-arb="bankroll"></label></div>
      <div id="arb-summary" aria-live="polite">${arbSummary(arbFor(a))}</div></div>
      ${section('The rules', `<div class="card"><ol style="margin:0;padding-left:18px;display:grid;gap:8px"><li><b>Exact means exact.</b> Same event, market, period and line. A middle is not an arb.</li><li><b>Both bets must still exist.</b> A price can disappear before the second bet is accepted.</li><li><b>Settlement rules must match.</b> Voids, limits, account restrictions and different house rules can break the math.</li><li><b>No automatic betting.</b> Kook'n never touches a sportsbook account or places a bet.</li></ol></div>`)}
      <div class="card on-felt"><p class="small"><b>Entertainment and calculation only.</b> This calculator does not know whether either price is available to you. Verify the exact event, market, line, period, price, limits and settlement rules in both apps before doing anything.</p></div>`;
  };
  VIEWS.lab = async () => VIEWS.record({ tab: 'trials' });
  VIEWS.schedule = async () => {
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
  VIEWS.status = async () => {
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
  VIEWS.feedback = async () => `<a class="back" href="#more">← More</a>${head('Feedback', 'What helped, what got in the way', 'Nothing is sent automatically. Prepare your note here, copy it, and send it to us privately on Discord.')}
    <div class="card"><div class="arb-form"><label>Area<select id="fb-area" class="select"><option>Today / best bets</option><option>Research</option><option>Games / scores</option><option>Record</option><option>Saved / ticket</option><option>Discord</option><option>Something else</option></select></label>
      <label>Experience<select id="fb-rating" class="select"><option>Useful</option><option>Confusing</option><option>Something broke</option><option>Feature idea</option></select></label></div>
      <label class="sr" for="fb">Your feedback</label><textarea id="fb" class="search" rows="5" maxlength="1200" style="min-height:120px;margin-top:10px" placeholder="What were you trying to do?"></textarea>
      <label class="small" style="display:flex;gap:8px;align-items:center;margin-top:8px"><input type="checkbox" id="fb-usage"> Include my page-visit counts (section names only)</label>
      <div class="btn-row" style="margin-top:10px"><button type="button" class="btn primary" data-prepare-feedback>Prepare message</button></div>
      <p class="small muted" style="margin-top:8px">Counts stay in this browser and contain no player names, searches or account details. Don't include account or payment details.</p>
      <div id="fb-out" aria-live="polite" style="margin-top:10px"></div></div>`;
  VIEWS.responsible = async () => `<a class="back" href="#more">← More</a>${head('Responsible gaming', 'Play for fun, play within limits', '')}
    <div class="card" style="display:grid;gap:10px"><p><b>21+ where legal.</b> Kook'n is research and entertainment. Nothing here is betting advice or a guarantee, and no pick is ever certain.</p>
      <p>Set a budget before you play and treat it as the cost of entertainment. Never chase losses.</p>
      <p><b>Gambling problem? Call 1-800-MY-RESET</b> (1-800-697-3738), the National Problem Gambling Helpline. It's free, confidential and open 24/7. 1-800-522-4700 also works.</p>
      <p class="small muted">Kook'n is not a sportsbook and never places bets. Prices shown are snapshots from licensed books and can change at any time.</p></div>`;

  /* =====================================================================
     ROUTER AND EVENTS
     ===================================================================== */

  let lastHash = null;
  const chrome = route => {
    const active = TAB_OF[route.view] || 'today';
    const links = TABS.map(([key, label]) => `<a href="#${key}" ${key === active ? 'aria-current="page"' : ''}>${svg(key)}<span>${esc(label)}</span></a>`).join('');
    $('#tabbar').innerHTML = links;
    $('#top-tabs').innerHTML = TABS.map(([key, label]) => `<a href="#${key}" ${key === active ? 'aria-current="page"' : ''}>${esc(label)}</a>`).join('');
    const sel = $('#league');
    if (!sel.options.length) sel.innerHTML = Object.entries(LEAGUE_NAME).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
    sel.value = state.league;
    let bar = $('#ticket-bar');
    if (!bar) { bar = document.createElement('a'); bar.id = 'ticket-bar'; bar.className = 'ticket-bar'; bar.href = '#ticket'; document.body.appendChild(bar); }
    const show = state.ticket.length > 0 && route.view !== 'ticket';
    bar.hidden = !show;
    document.body.classList.toggle('has-ticket-bar', show);
    if (show) bar.innerHTML = `<span>My ticket · ${state.ticket.length} leg${state.ticket.length === 1 ? '' : 's'}</span><span>Open →</span>`;
  };
  /* Controls carried by an old shared link (#stats?stat=…&position=…, #trends?rate=…&kind=…). */
  const applyContext = route => {
    const c = route.ctx;
    if (route.mode === 'players') {
      if (c.chartStat) state.players.chartStat = c.chartStat;
      if (c.chartPos) state.players.chartPos = c.chartPos;
      if (c.chartWindow) state.players.chartWindow = c.chartWindow;
      if (c.chartDay) state.players.game = c.chartDay === 'all' || c.chartDay === 'next' ? c.chartDay : `day:${c.chartDay}`;
      if (c.researchQuery) { state.players.q = c.researchQuery; state.players.sub = 'search'; }
    } else if (route.mode === 'trends') {
      if (c.trendStat) state.trends.stat = c.trendStat; if (c.trendWindow) state.trends.window = c.trendWindow;
      if (c.trendRate) state.trends.rate = c.trendRate; if (c.trendKind) state.trends.kind = c.trendKind; if (c.trendDay) state.trends.day = c.trendDay;
      if (c.researchQuery) state.q = c.researchQuery;
    }
  };
  /* A ticket's hit chart, loaded once, when it is first visible. */
  const loadPropBox = box => {
    if (box.dataset.loaded) return;
    box.dataset.loaded = '1';
    const d = box.dataset;
    box.innerHTML = '<p class="small muted">Loading history…</p>';
    propHistory(d.league, d.athlete, d.stat, Number(d.line), d.dir, d.game, d.before || null).then(html => { box.innerHTML = html; }).catch(() => { box.innerHTML = '<p class="small muted">History unavailable right now.</p>'; });
  };
  /* A newer render always wins: a slow fetch from an older one never paints over it. */
  let renderToken = 0, rendering = false;
  async function render(soft = false) {
    const token = ++renderToken;
    const savedY = (history.state || {}).scroll;
    rendering = true;
    let route = resolve(location.hash);
    if (route.legacy && route.league) setLeague(route.league);
    if (route.legacy && route.ctx) applyContext(route);
    const next = canonical(route);
    if (next && next !== location.hash) { try { history.replaceState(null, '', next); } catch (_) { /* rate limited */ } route = resolve(next); }
    chrome(route);
    const view = $('#view');
    const focusKey = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.input : null;
    const caret = focusKey ? document.activeElement.selectionStart : null;
    /* Keep keyboard focus on the control that was used, and keep open dropdowns open, across a soft re-render. */
    const ae = document.activeElement;
    const focusSel = soft && ae && ae !== document.body && !focusKey ? (ae.id ? `#${CSS.escape(ae.id)}` : ['set', 'flag', 'flagTrend', 'flagPlayers', 'select', 'watch', 'watchPick', 'addLine', 'accept', 'removeLeg'].map(k => ae.dataset && ae.dataset[k] != null ? `[data-${k.replace(/[A-Z]/g, m => '-' + m.toLowerCase())}="${CSS.escape(ae.dataset[k])}"]` : null).find(Boolean)) : null;
    const openRows = [...document.querySelectorAll('details[open][data-row]')].map(d => d.dataset.row);
    const sideScroll = soft ? [...document.querySelectorAll('#view .chart-wrap, #view .table-wrap, #view .chip-scroll')].map(e => e.scrollLeft) : [];
    const boxes = soft ? new Map([...document.querySelectorAll('details[data-box]')].map(d => [d.dataset.box, d.open])) : new Map();
    const openBoxes = soft ? [...document.querySelectorAll('details[open]:not([data-row]):not([data-box]) > summary')].map(x => x.textContent.trim()) : [];
    const slow = soft ? null : setTimeout(() => { if (token === renderToken) view.innerHTML = '<p class="loading muted" role="status">Loading…</p>'; }, 150);
    let html;
    try {
      html = await (VIEWS[route.view] || VIEWS.today)(route);
    } catch (e) {
      html = empty('Something did not load', `The data for this page is unavailable right now (${esc(e.message || e)}). <button type="button" class="btn small" data-retry>Try again</button>`, 'clock');
    }
    clearTimeout(slow);
    if (token !== renderToken) return;
    rendering = false;
    const navigated = location.hash !== lastHash;
    view.innerHTML = html;
    if ($('#league').value !== state.league) $('#league').value = state.league;
    if (navigated) countVisit(route.view);
    for (const id of openRows) { const d = document.querySelector(`details[data-row="${CSS.escape(id)}"]`); if (d) { d.open = true; loadRowDetail(d); } }
    for (const box of document.querySelectorAll('[data-prop-history]')) if (!box.closest('details:not([open])')) loadPropBox(box);
    if (focusKey) { const el = document.querySelector(`[data-input="${focusKey}"]`); if (el) { el.focus(); try { el.setSelectionRange(caret, caret); } catch (_) { /* number inputs */ } } }
    if (sideScroll.length) [...document.querySelectorAll('#view .chart-wrap, #view .table-wrap, #view .chip-scroll')].forEach((e, i) => { if (sideScroll[i]) e.scrollLeft = sideScroll[i]; });
    if (focusSel) { const el = document.querySelector(focusSel); if (el) { el.focus({ preventScroll: true }); if (el.closest('.chip-scroll')) el.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } }
    for (const d of document.querySelectorAll('details[data-box]')) if (boxes.has(d.dataset.box)) d.open = boxes.get(d.dataset.box);
    if (openBoxes.length) for (const sum of document.querySelectorAll('details:not([data-row]):not([data-box]) > summary')) { if (openBoxes.includes(sum.textContent.trim())) sum.parentElement.open = true; }
    const h1 = view.querySelector('h1');
    document.title = `${h1 ? h1.textContent : 'Kook\'n'} · Kook'n`;
    if (navigated) { window.scrollTo(0, isNum(savedY) ? savedY : 0); if (h1) { h1.setAttribute('tabindex', '-1'); h1.focus({ preventScroll: true }); } }
    lastHash = location.hash;
  }
  const toast = text => {
    const el = document.createElement('div'); el.className = 'toast'; el.setAttribute('role', 'status'); el.textContent = text;
    document.body.appendChild(el); setTimeout(() => el.remove(), 1800);
  };
  let inputTimer = null;
  /* What the sport picker should open: the same tab in the new sport, or the list a sport-specific page belongs to. */
  const sportDestination = route => {
    if (route.view === 'games') return `#games${route.tab && route.tab !== 'upcoming' ? '/' + route.tab : ''}${state.league !== 'ALL' ? '?sport=' + state.league : ''}`;
    if (route.view === 'game' || route.view === 'team') return '#games';
    if (route.view === 'player') return '#research/players';
    if (route.view === 'today' && route.league) return '#today';
    if (route.view === 'research' && (route.league || route.game)) return `#research${route.mode === 'lines' ? '' : '/' + route.mode}`;
    return null;
  };
  /* Background refresh: live pages only, never while someone is typing or picking. Data keeps its 5-minute cache;
     the re-render re-checks price ages and live scores. */
  const LIVE_VIEWS = new Set(['today', 'pick', 'games', 'game', 'team', 'research', 'record', 'player', 'saved', 'ticket']);
  const refreshPage = () => {
    if (document.hidden) return;
    const route = resolve(location.hash);
    if (!LIVE_VIEWS.has(route.view) || (route.view === 'research' && !['lines', 'trends'].includes(route.mode))) return;
    const a = document.activeElement;
    if (a && a.matches && a.matches('input, select, textarea')) return;
    render(true);
  };
  const toggleWatch = item => {
    if (!item) return;
    const i = state.watchlist.findIndex(r => r.key === item.key);
    if (i >= 0) state.watchlist.splice(i, 1);
    else if (state.watchlist.length >= 100) { toast('100 saved · remove one first'); return; }
    else state.watchlist.unshift({ ...item, savedAt: new Date().toISOString() });
    saved.set('watchlist', state.watchlist.slice(0, 100));
    render(true);
  };
  const ticketLeg = row => ({ id: row.id, title: row.title, player: row.player || null, market: row.market || null, direction: row.direction || null, line: row.line,
    odds: row.odds, book: row.book, gameId: row.gameId, kickoff: row.kickoff, state: row.state, expiresAt: row.expiresAt, observedAt: row.observedAt });
  function boot() {
    document.addEventListener('error', event => {
      const img = event.target;
      if (img instanceof HTMLImageElement && img.closest('.tm, .ava')) { const box = img.parentElement; img.remove(); box.classList.remove('has-logo'); box.classList.add('no-img'); }
    }, true);
    window.addEventListener('hashchange', () => { appliedHash = null; state.player.hash = null; render(); });
    const skip = document.querySelector('.skip');
    if (skip) skip.addEventListener('click', e => { e.preventDefault(); const v = $('#view'); v.setAttribute('tabindex', '-1'); v.focus(); });
    /* Back and forward return to where you were: the scroll position rides on the history entry. */
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    let scrollFrame = null;
    /* Saved after 200 ms of scroll idle, never while a page is still loading (its height is not final yet). */
    window.addEventListener('scroll', () => { clearTimeout(scrollFrame); scrollFrame = setTimeout(() => { if (rendering) return; try { history.replaceState({ ...(history.state || {}), scroll: window.scrollY }, '', location.href); } catch (_) { /* rate limited */ } }, 200); }, { passive: true });
    document.addEventListener('click', async event => {
      const t = event.target.closest('button, [data-set]');
      if (!t) return;
      const d = t.dataset;
      if (d.set) {
        if (t.tagName === 'A') return;
        const [key, value] = d.set.split(':');
        const SETTERS = {
          type: v => { state.board.type = v; saveBoard(); }, trendRate: v => { state.trends.rate = v; }, trendWindow: v => { state.trends.window = v; }, trendKind: v => { state.trends.kind = v; }, trendDay: v => { state.trends.day = v; },
          pos: v => { state.players.pos = v; }, psub: v => { state.players.sub = v; }, cpos: v => { state.players.chartPos = v; }, cwin: v => { state.players.chartWindow = v; },
          dstat: v => { state.players.stat = v; }, dscope: v => { state.players.scope = v; }, dorder: v => { state.players.order = v; },
          gsort: v => { state.games.sort = v; }, gday: v => { state.games.day = v; }, gstatus: v => { state.games.status = v; },
          pstat: v => { state.player.stat = v; }, pwin: v => { state.player.window = v; }, pseason: v => { state.player.season = v; }, stakeMode: v => { state.stake.mode = v; saved.set('stake', state.stake); },
        };
        if (SETTERS[key]) SETTERS[key](value);
        if (['trendRate', 'trendWindow', 'trendKind', 'trendDay', 'cpos', 'cwin'].includes(key)) savePrefs();
        render(true); return;
      }
      if (d.flag) { state.board[d.flag] = !state.board[d.flag]; saveBoard(); render(true); return; }
      if (d.flagTrend) { state.trends.heavy = !state.trends.heavy; render(true); return; }
      if (d.flagPlayers) { state.players.linesOnly = !state.players.linesOnly; render(true); return; }
      if ('moreRows' in d) { state.board.limit += 40; render(true); return; }
      if ('moreTrends' in d) { state.trends.limit = (state.trends.limit || 40) + 40; render(true); return; }
      if ('allGames' in d) { state.games.all = true; render(true); return; }
      if ('clearQ' in d) { state.q = ''; render(true); return; }
      if ('retry' in d) { cache.clear(); missing.clear(); if (liveCache.rows) liveCache.rows.clear(); render(); return; }
      if ('dismissOnboard' in d) { saved.set('onboarded', true); render(true); return; }
      if (d.watch) { toggleWatch(watchCandidates.get(d.watch)); return; }
      if (d.watchPick) {
        const pick = (await allPicks()).find(p => p.id === d.watchPick);
        if (!pick) { toast('This play is not available to save'); return; }
        toggleWatch({ ...P.snapshot(pick), type: 'pick', key: 'pick:' + pick.id, pickId: pick.id, okey: officialKey(pick), title: niceTitle(pick.displayTitle || pick.title), href: pick.athleteId ? `#player/${pick.league}/${pick.athleteId}` : `#game/${pick.gameId}` });
        return;
      }
      if (d.unsave) { state.watchlist = state.watchlist.filter(r => r.key !== d.unsave); saved.set('watchlist', state.watchlist); render(true); return; }
      if (d.addLine) {
        const i = state.ticket.findIndex(r => r.id === d.addLine);
        if (i >= 0) { state.ticket.splice(i, 1); saved.set('ticket', state.ticket); toast('Removed from your ticket'); render(true); return; }
        const lines = await get('app/lines.json');
        const row = (lines.lines || []).find(r => r.id === d.addLine);
        if (!row) { toast('This price is no longer on the board'); return; }
        state.ticket.push(ticketLeg(row)); saved.set('ticket', state.ticket); toast('Added to your ticket'); render(true);
        return;
      }
      if (d.accept) {
        const lines = await get('app/lines.json');
        const row = (lines.lines || []).find(r => r.id === d.accept);
        const i = state.ticket.findIndex(r => r.id === d.accept);
        if (row && i >= 0) { state.ticket[i] = ticketLeg(row); saved.set('ticket', state.ticket); }
        render(true); return;
      }
      if (d.removeLeg != null) { state.ticket.splice(Number(d.removeLeg), 1); saved.set('ticket', state.ticket); render(true); return; }
      if ('clearTicket' in d) { state.ticket = []; saved.set('ticket', state.ticket); render(true); return; }
      if ('copyTicket' in d) {
        const checked = await ticketRows();
        const text = C.ticketText(checked.map(r => ({ ...r, book: bookLabel(r.book) || r.book, title: `${r.title || r.player || 'Line'}${r.missing ? ' [gone]' : r.started ? ' [started]' : r.closed ? ' [closed]' : r.changed ? ' [price changed]' : r.unchecked ? ' [not re-checked]' : ''}` })));
        try { await navigator.clipboard.writeText(text); toast('Ticket copied'); } catch (_) { window.prompt('Copy the ticket text:', text); }
        return;
      }
      if ('prepareFeedback' in d) {
        const area = ($('#fb-area') || {}).value || '', rating = ($('#fb-rating') || {}).value || '';
        const comment = (($('#fb') || {}).value || '').slice(0, 1200).trim();
        const usage = ($('#fb-usage') || {}).checked ? Object.entries(saved.get('usage', {}) || {}).map(([k, v]) => `${k} ${v}`).join(', ') : '';
        const text = [`Kook'n feedback`, `Area: ${area}`, `Experience: ${rating}`, comment ? `Comment: ${comment}` : '', usage ? `Page visits: ${usage}` : ''].filter(Boolean).join('\n');
        const out = $('#fb-out');
        if (out) out.innerHTML = `<label class="sr" for="fb-text">Your message</label><textarea id="fb-text" class="search" rows="6" readonly>${esc(text)}</textarea><div class="btn-row" style="margin-top:8px"><button type="button" class="btn primary" data-copy-feedback>Copy message</button><a class="btn" href="https://discord.gg/CvNTUUSnNz" target="_blank" rel="noopener">Open Discord ↗</a></div>`;
        return;
      }
      if ('copyFeedback' in d) {
        const text = ($('#fb-text') || {}).value || '';
        try { await navigator.clipboard.writeText(text); toast('Copied. Paste it in Discord.'); } catch (_) { const box = $('#fb-text'); if (box) { box.focus(); box.select(); } toast('Select the text and copy it'); }
      }
    });
    document.addEventListener('click', async event => {
      const link = event.target.closest('[data-copy-link]');
      if (!link) return;
      event.preventDefault();
      const url = `${location.origin}${location.pathname}${link.getAttribute('href')}`;
      try { await navigator.clipboard.writeText(url); toast('Link copied'); } catch (_) { window.prompt('Copy this link:', url); }
    });
    document.addEventListener('toggle', event => {
      const el = event.target;
      if (!el.matches || !el.open) return;
      if (el.matches('details[data-row]')) loadRowDetail(el);
      if (el.matches('details.t-more')) el.querySelectorAll('[data-prop-history]').forEach(loadPropBox);
    }, true);
    document.addEventListener('input', event => {
      const el = event.target;
      if (el.dataset.input) {
        clearTimeout(inputTimer);
        const SET = { q: v => { state.q = v; }, pq: v => { state.players.q = v; }, gq: v => { state.games.q = v; }, rq: v => { state.record.q = v; } };
        inputTimer = setTimeout(() => { (SET[el.dataset.input] || (() => {}))(el.value); render(true); }, 220);
      }
      /* The calculators update only their result box, so typing is never interrupted. */
      if (el.dataset.arb) {
        state.arb[el.dataset.arb] = el.value; saved.set('arb', state.arb);
        const box = $('#arb-summary'); if (box) box.innerHTML = arbSummary(arbFor(state.arb));
      }
      if (el.dataset.stake) {
        state.stake[el.dataset.stake] = Number(el.value); saved.set('stake', state.stake);
        ticketRows().then(rows => { const box = $('#ticket-summary'); if (box) box.innerHTML = ticketSummary(rows); });
      }
    });
    document.addEventListener('change', event => {
      const el = event.target;
      if (el.id === 'league') {
        setLeague(el.value);
        const dest = sportDestination(resolve(location.hash));
        el.blur();
        if (dest && dest !== location.hash) location.hash = dest; else render(true);
        return;
      }
      const SELECTS = { sort: v => { state.board.sort = v; saveBoard(); }, season: v => { state.record.season = v; }, phase: v => { state.record.phase = v; },
        chartStat: v => { state.players.chartStat = v; }, trendStat: v => { state.trends.stat = v; }, chartGame: v => { state.players.game = v; }, playerSeason: v => { state.player.season = v; }, defStat: v => { state.players.stat = v; } };
      if (el.dataset.select && SELECTS[el.dataset.select]) { SELECTS[el.dataset.select](el.value); if (['chartStat', 'trendStat'].includes(el.dataset.select)) savePrefs(); render(true); }
    });
    setInterval(refreshPage, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshPage(); });
    render();
  }

  return { model, boot };
});
